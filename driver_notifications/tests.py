from datetime import timedelta, time
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from cargo.models import Load
from .delivery import deliver, quiet
from .matching import evaluate
from .models import LinkToken, MatchState, Notification, Preference, TelegramAccount, Ticket, Vehicle
from .serializers import TicketSerializer
from .service import bind_account, new_link, scan_all, scan_ticket
from .telegram import BotError, callback, handle_update


class DriverTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.driver = User.objects.create_user(username="driver", role="driver")
        self.other = User.objects.create_user(username="other", role="driver")
        self.sender = User.objects.create_user(username="sender", role="user")
        self.vehicle = Vehicle.objects.create(owner=self.driver, name="Tent 01", kind="tent", capacity_tons=20)
        self.client = APIClient()
        self.client.force_authenticate(self.driver)
        self.data = {"title": "Toshkentdan", "vehicle": self.vehicle.pk, "origins": [{"name": "Toshkent"}], "destinations": [{"name": "Samarqand", "min_price": "2000000"}, {"name": "Buxoro", "min_price": "4000000", "priority": 2}], "ready_at": timezone.now().isoformat(), "expires_at": (timezone.now()+timedelta(days=7)).isoformat(), "available_tons": "20", "min_price": "2000000", "currency": "UZS", "price_basis": "trip", "match_mode": "any_two"}
        self.load = Load.objects.create(posted_by=self.sender, origin="Ташкент", destination="Самарканд", cargo_name="Sement", vehicle_type="Тент", weight_tons=10, price_amount=2500000, currency="UZS", contact_phone="938086599", pickup_date=timezone.localdate()+timedelta(days=1))

    def ticket(self, **kwargs):
        s = TicketSerializer(data={**self.data, **kwargs}, context={"request": SimpleNamespace(user=self.driver)})
        s.is_valid(raise_exception=True)
        return s.save(owner=self.driver)

    def test_create_matches_existing_and_cross_owner_isolation(self):
        result = self.client.post("/api/driver/tickets/", self.data, format="json")
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(Notification.objects.count(), 2)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/driver/tickets/").data, [])
        self.assertEqual(self.client.patch(f"/api/driver/tickets/{result.data['id']}/", {"status": "closed"}).status_code, 404)
        self.assertEqual(self.client.post(f"/api/driver/notifications/{Notification.objects.first().pk}/read/").status_code, 404)
        self.assertEqual(self.client.post("/api/driver/tickets/", self.data, format="json").status_code, 400)

    def test_only_active_driver_has_access(self):
        self.client.force_authenticate(self.sender)
        self.assertEqual(self.client.get("/api/driver/vehicles/").status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/driver/tickets/").status_code, 401)

    def test_vehicle_capacity_and_time_validation(self):
        for data in ({"available_tons": "21"}, {"expires_at": timezone.now().isoformat()}, {"origins": []}, {"origins": [{"name": "Toshkent", "lat": 41}]}):
            with self.subTest(data=data):
                self.assertEqual(self.client.post("/api/driver/tickets/", {**self.data, **data}, format="json").status_code, 400)

    def test_vehicle_delete_is_protected(self):
        self.ticket()
        self.assertEqual(self.client.delete(f"/api/driver/vehicles/{self.vehicle.pk}/").status_code, 409)

    def test_multiple_destinations_prices_priorities_and_unknown_price(self):
        ticket = self.ticket()
        self.assertEqual(evaluate(ticket, self.load)["level"], "full")
        self.load.destination="Buxoro"
        result = evaluate(ticket, self.load)
        self.assertFalse(result["checks"]["price"])
        self.assertEqual(result["priority"], 2)
        self.load.price_amount=None
        self.assertIsNone(evaluate(ticket,self.load)["checks"]["price"])

    def test_any_two_accepts_wrong_route_and_flags_overweight(self):
        ticket=self.ticket()
        self.load.origin="Nukus"
        self.load.weight_tons=25
        result=evaluate(ticket,self.load)
        self.assertIsNotNone(result)
        self.assertFalse(result["checks"]["route"])
        self.assertFalse(result["checks"]["capacity"])
        self.assertEqual(result["level"], "partial")
        ticket.match_mode="route"
        self.assertIsNone(evaluate(ticket,self.load))

    def test_per_ton_and_currency_are_not_confused(self):
        ticket=self.ticket(price_basis="ton", destinations=[{"name":"Samarqand","min_price":"300000"}])
        self.assertFalse(evaluate(ticket,self.load)["checks"]["price"])
        self.load.price_basis="ton"
        self.load.price_amount=400000
        self.assertTrue(evaluate(ticket,self.load)["checks"]["price"])
        self.load.currency="USD"
        self.assertFalse(evaluate(ticket,self.load)["checks"]["price"])

    def test_radius_needs_coordinates_and_calculates_distance(self):
        ticket=self.ticket(origins=[{"name":"Toshkent","lat":41.3,"lon":69.2,"radius_km":50}])
        self.assertIsNone(evaluate(ticket,self.load)["checks"]["route"])
        self.load.origin_lat=41.31; self.load.origin_lon=69.21
        ticket.current_location={"name":"GPS","lat":41.3,"lon":69.2}
        result=evaluate(ticket,self.load)
        self.assertTrue(result["checks"]["route"])
        self.assertGreater(result["distance_km"], 0)
        self.assertLess(result["distance_km"], 5)

    def test_ordered_route_allows_forward_dogruz_only(self):
        ticket=self.ticket(route_mode="ordered", partial_load=True, destinations=[{"name":"Buxoro"}], waypoints=[{"name":"Samarqand"}], match_mode="route")
        self.load.origin="Samarqand"; self.load.destination="Buxoro"
        self.assertIsNotNone(evaluate(ticket,self.load))
        self.load.origin="Buxoro"; self.load.destination="Samarqand"
        self.assertIsNone(evaluate(ticket,self.load))

    def test_dedup_price_change_pause_and_dismiss(self):
        ticket=self.ticket()
        scan_ticket(ticket.pk); scan_ticket(ticket.pk)
        self.assertEqual(Notification.objects.count(),1)
        self.load.price_amount=3000000; self.load.save()
        scan_ticket(ticket.pk)
        self.assertEqual(Notification.objects.count(),2)
        self.assertEqual(Notification.objects.first().kind,"price")
        ticket.status="paused"; ticket.save()
        self.load.price_amount=4000000; self.load.save()
        scan_ticket(ticket.pk)
        self.assertEqual(Notification.objects.count(),2)
        ticket.status="active"; ticket.save()
        MatchState.objects.update(dismissed=True)
        scan_ticket(ticket.pk)
        self.assertEqual(Notification.objects.count(),2)

    def test_new_load_and_closed_deleted_loads(self):
        ticket=self.ticket(); scan_ticket(ticket.pk)
        self.load.status="closed"; self.load.save(); scan_ticket(ticket.pk)
        self.assertTrue(Notification.objects.filter(kind="match").get().obsolete)
        self.assertEqual(Notification.objects.filter(kind="unavailable").count(),1)
        scan_ticket(ticket.pk)
        self.assertEqual(Notification.objects.filter(kind="unavailable").count(),1)
        self.load.delete()
        self.assertIsNone(Notification.objects.filter(kind="match").get().load_id)

    def test_expiry_reminder_and_return_trip(self):
        ticket=self.ticket(expires_at=(timezone.now()+timedelta(hours=1)).isoformat())
        scan_ticket(ticket.pk); scan_ticket(ticket.pk)
        self.assertEqual(Notification.objects.filter(kind="expiring").count(),1)
        Ticket.objects.filter(pk=ticket.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        scan_ticket(ticket.pk)
        self.assertEqual(Notification.objects.filter(kind="expired").count(),1)
        reply=self.client.post(f"/api/driver/tickets/{ticket.pk}/return-trip/", {}, format="json")
        self.assertEqual(reply.status_code,201,reply.data)
        self.assertEqual(reply.data["status"],"paused")
        self.assertEqual(reply.data["destinations"][0]["name"],"Toshkent")

    def test_one_time_binding_and_wrong_chat_protection(self):
        token=new_link(self.driver)
        account=bind_account(token,123)
        self.assertEqual(account.owner,self.driver)
        self.assertIsNone(bind_account(token,456))
        self.assertIsNone(bind_account(new_link(self.other),123))
        token=new_link(self.other)
        LinkToken.objects.filter(owner=self.other).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertIsNone(bind_account(token,999))

    def test_quiet_hours_overnight(self):
        pref=Preference.objects.create(owner=self.driver,quiet_start=time(22),quiet_end=time(7))
        now=timezone.now().replace(hour=20,minute=0)
        self.assertTrue(quiet(pref,now))
        self.assertFalse(quiet(pref,now.replace(hour=9)))

    @patch("driver_notifications.delivery.call", return_value={"message_id":12})
    def test_delivery_digest_and_retry(self, send):
        TelegramAccount.objects.create(owner=self.driver,chat_id=123)
        pref=Preference.objects.create(owner=self.driver,partial_interval_minutes=30)
        ticket=self.ticket(); self.load.price_amount=None; self.load.save(); scan_ticket(ticket.pk)
        deliver(); send.assert_not_called()
        Notification.objects.update(deliver_after=timezone.now()-timedelta(seconds=1))
        deliver(); self.assertEqual(send.call_count,1)
        deliver(); self.assertEqual(send.call_count,1)
        self.assertIsNotNone(Notification.objects.first().sent_at)

    @patch("driver_notifications.delivery.call", side_effect=BotError(429,120))
    def test_telegram_failure_does_not_lose_site_notification(self, send):
        TelegramAccount.objects.create(owner=self.driver,chat_id=123)
        ticket=self.ticket();scan_ticket(ticket.pk);deliver()
        note=Notification.objects.get()
        self.assertIsNone(note.sent_at); self.assertEqual(note.attempts,1)
        self.assertGreater(note.deliver_after,timezone.now())
        self.assertEqual(self.client.get("/api/driver/notifications/unread/").data["count"],1)

    @patch("driver_notifications.telegram.call",return_value={"message_id":1})
    def test_bot_wizard_saves_vehicle_and_ticket(self, call):
        TelegramAccount.objects.create(owner=self.driver,chat_id=123)
        def message(text):
            handle_update({"message":{"chat":{"id":123,"type":"private"},"from":{"id":123},"text":text}})
        for text in ["/vehicle","Volvo","tent","20","80","01A123AA","ha"]:
            message(text)
        self.assertEqual(Vehicle.objects.filter(owner=self.driver).count(),2)
        for text in ["/ticket","Bot tiket",str(self.vehicle.pk),"Toshkent","Toshkent","-","0","alternatives","Samarqand, Buxoro","-","2000000, 4000000","1, 2","1, 2","0, 0","-","168","20","yoq","UZS","trip","2000000","any_two","-","-","ha"]:
            message(text)
        self.assertEqual(Ticket.objects.filter(title="Bot tiket").count(),1)
        self.assertEqual(len(Ticket.objects.get().destinations),2)

    @patch("driver_notifications.telegram.call",return_value={"message_id":1})
    def test_bot_callback_cannot_change_other_driver_ticket(self, call):
        account=TelegramAccount.objects.create(owner=self.other,chat_id=456)
        ticket=self.ticket()
        callback(account,{"data":f"close:{ticket.pk}","id":"q"})
        ticket.refresh_from_db();self.assertEqual(ticket.status,"active")

    @patch("driver_notifications.telegram.call", return_value={"message_id": 1})
    def test_bot_return_trip_is_owned_and_paused(self, call):
        TelegramAccount.objects.create(owner=self.driver, chat_id=123)
        ticket = self.ticket()
        handle_update({"message": {"chat": {"id": 123, "type": "private"}, "from": {"id": 123}, "text": f"/return {ticket.pk}"}})
        self.assertEqual(Ticket.objects.count(), 2)
        self.assertEqual(Ticket.objects.exclude(pk=ticket.pk).get().status, "paused")

    def test_vehicle_catalog_crud_and_canonical_matching(self):
        result = self.client.post("/api/driver/vehicles/", {"name": "Sovutgich", "kind": "isothermal", "size_class": "3XL", "capacity_tons": "8"}, format="json")
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(result.data["size_class"], "3XL")
        self.assertEqual(self.client.patch(f"/api/driver/vehicles/{result.data['id']}/", {"kind": "invalid"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"/api/driver/vehicles/{result.data['id']}/", {"kind": "lowbed", "size_class": "CUSTOM"}, format="json").status_code, 200)
        ticket = self.ticket()
        self.load.vehicle_kind = "isothermal"
        self.assertFalse(evaluate(ticket, self.load)["checks"]["vehicle"])
        ticket.vehicle.kind = "isothermal"
        self.assertTrue(evaluate(ticket, self.load)["checks"]["vehicle"])

    def test_load_vehicle_fields_and_legacy_edit(self):
        self.client.force_authenticate(self.sender)
        endpoint = f"/api/cargo/loads/{self.load.pk}/"
        result = self.client.patch(endpoint, {"vehicle_kind": "refrigerator", "vehicle_size": "3XL"}, format="json")
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["vehicle_type"], "Refrijerator · 3XL")
        self.assertEqual(self.client.patch(endpoint, {"vehicle_size": "wrong"}, format="json").status_code, 400)
        result = self.client.patch(endpoint, {"vehicle_type": "Maxsus transport"}, format="json")
        self.assertEqual(result.data["vehicle_kind"], "")
        self.assertEqual(result.data["vehicle_size"], "")
