from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import TelegramAccount, Ticket, Vehicle
from .telegram import handle_update, save_ticket, ticket_state


class SharedTicketTests(TestCase):
    def setUp(self):
        self.driver = get_user_model().objects.create_user(username="shared_driver", role="driver")
        self.other = get_user_model().objects.create_user(username="other_driver", role="driver")
        self.vehicle = Vehicle.objects.create(owner=self.driver, name="Volvo", kind="tent", capacity_tons=20)
        self.account = TelegramAccount.objects.create(owner=self.driver, chat_id=123)
        self.client = APIClient()
        self.client.force_authenticate(self.driver)
        self.data = {"title": "Saytdagi tiket", "vehicle": self.vehicle.pk, "origins": [{"name": "Toshkent", "lat": 41.3, "lon": 69.2}, {"name": "Chirchiq"}], "destinations": [{"name": "Namangan"}, {"name": "Samarqand"}], "route_mode": "alternatives"}

    def assert_short_defaults(self, ticket):
        self.assertEqual(ticket.status, "active")
        self.assertEqual(ticket.match_mode, "route")
        self.assertEqual(ticket.available_tons, self.vehicle.capacity_tons)
        self.assertEqual(ticket.min_price, 0)
        self.assertEqual(ticket.waypoints, [])
        self.assertEqual(ticket.current_location["name"], ticket.origins[0]["name"])
        self.assertAlmostEqual((ticket.expires_at-ticket.ready_at).total_seconds(), timedelta(days=7).total_seconds())

    @patch("driver_notifications.telegram.call", return_value={"message_id": 10})
    def test_site_ticket_is_immediately_listed_in_bot(self, call):
        response = self.client.post("/api/driver/tickets/simple/", self.data, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        ticket = Ticket.objects.get(pk=response.data["id"])
        self.assert_short_defaults(ticket)
        self.assertEqual(len(ticket.origins), 2)
        self.assertEqual(len(ticket.destinations), 2)
        handle_update({"message": {"chat": {"id": 123, "type": "private"}, "from": {"id": 123}, "text": "/tickets"}})
        self.assertTrue(any("Saytdagi tiket" in c.kwargs.get("text", "") for c in call.call_args_list))
        handle_update({"message": {"chat": {"id": 123, "type": "private"}, "from": {"id": 123}, "text": f"/edit {ticket.pk}"}})
        self.account.refresh_from_db()
        self.assertEqual(self.account.state["instance"], ticket.pk)
        self.assertEqual(self.account.state["data"]["origins"][0]["name"], "Toshkent")

    @patch("driver_notifications.telegram.call", return_value={"message_id": 10})
    def test_bot_created_ticket_is_the_same_record_on_site_and_can_be_edited(self, call):
        self.account.state = ticket_state()
        self.account.state["data"] = {**self.data, "title": "Botdagi tiket", "route_mode": "anywhere"}
        self.account.save()
        save_ticket(self.account)
        ticket = Ticket.objects.get()
        self.assert_short_defaults(ticket)
        self.assertEqual(ticket.destinations, [])
        site = self.client.get("/api/driver/tickets/")
        self.assertEqual(site.data[0]["id"], ticket.pk)
        edit = self.client.patch(f"/api/driver/tickets/{ticket.pk}/simple/", {**self.data, "title": "Saytda yangilandi"}, format="json")
        self.assertEqual(edit.status_code, 200, edit.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.title, "Saytda yangilandi")
        self.assertEqual(Ticket.objects.count(), 1)
        handle_update({"message": {"chat": {"id": 123, "type": "private"}, "from": {"id": 123}, "text": "/tickets"}})
        self.assertTrue(any("Saytda yangilandi" in c.kwargs.get("text", "") for c in call.call_args_list))

    def test_anywhere_ignores_destination_and_hidden_custom_settings(self):
        response = self.client.post("/api/driver/tickets/simple/", {**self.data, "route_mode": "anywhere", "min_price": "999", "available_tons": "1", "match_mode": "full"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        ticket = Ticket.objects.get()
        self.assert_short_defaults(ticket)
        self.assertEqual(ticket.destinations, [])

    def test_owner_isolation_and_required_route_validation(self):
        response = self.client.post("/api/driver/tickets/simple/", self.data, format="json")
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/driver/tickets/").data, [])
        self.assertEqual(self.client.patch(f"/api/driver/tickets/{response.data['id']}/simple/", self.data, format="json").status_code, 404)
        self.assertEqual(self.client.post("/api/driver/tickets/simple/", self.data, format="json").status_code, 400)
        self.client.force_authenticate(self.driver)
        self.assertEqual(self.client.post("/api/driver/tickets/simple/", {**self.data, "origins": []}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/driver/tickets/simple/", {**self.data, "destinations": []}, format="json").status_code, 400)
