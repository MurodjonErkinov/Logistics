from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .locations import LocationError, SafeRedirects, checked_url, coordinates_from_url, parse_location
from .models import TelegramAccount, Ticket, Vehicle
from .telegram import TICKET_FLOW_VERSION, TICKET_STEPS, handle_update


class LocationParserTests(SimpleTestCase):
    def test_telegram_location_and_venue(self):
        for message in ({"location": {"latitude": 41.3, "longitude": 69.2}}, {"venue": {"title": "Ombor", "location": {"latitude": 41.3, "longitude": 69.2}}}):
            with self.subTest(message=message):
                place = parse_location("", message)
                self.assertEqual((place["lat"], place["lon"]), (41.3, 69.2))

    def test_google_coordinates_and_selected_pin_over_viewport(self):
        urls = ["https://www.google.com/maps/search/?api=1&query=41.3%2C69.2", "https://maps.google.com/?q=41.3,69.2", "https://www.google.com/maps/place/Warehouse/@40,68,12z/data=!3d41.3!4d69.2", "https://www.google.com/maps/@41.3,69.2,15z"]
        for url in urls:
            with self.subTest(url=url):
                point = coordinates_from_url(url)
                self.assertEqual((point["lat"], point["lon"]), (41.3, 69.2))
        self.assertIsNone(coordinates_from_url("https://www.google.com/maps/place/Warehouse/@40,68,12z"))

    def test_yandex_coordinate_order_and_pin_priority(self):
        urls = ["https://yandex.ru/maps/?ll=69.2%2C41.3", "https://yandex.com/maps/?ll=68,40&whatshere%5Bpoint%5D=69.2%2C41.3", "https://yandex.uz/maps/?pt=69.2,41.3,pm2rdm"]
        for url in urls:
            with self.subTest(url=url):
                point = coordinates_from_url(url)
                self.assertEqual((point["lat"], point["lon"]), (41.3, 69.2))
        self.assertIsNone(coordinates_from_url("https://yandex.ru/maps/org/123/?ll=68,40"))

    @patch("driver_notifications.locations.urllib.request.build_opener")
    def test_short_links_resolve_and_keep_original_url(self, build):
        response = MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "https://www.google.com/maps/place/X/data=!3d41.3!4d69.2"
        build.return_value.open.return_value = response
        place = parse_location("Toshkent https://maps.app.goo.gl/example")
        self.assertEqual(place["name"], "Toshkent")
        self.assertEqual(place["lat"], 41.3)
        self.assertEqual(place["source_url"], "https://maps.app.goo.gl/example")
        build.return_value.open.assert_called_once()

    def test_unsafe_urls_and_redirects_rejected(self):
        for url in ["http://127.0.0.1/", "https://localhost/maps", "https://www.google.com.evil.test/maps", "https://user:pass@www.google.com/maps", "https://www.google.com:444/maps", "https://www.google.com/search?q=x"]:
            with self.subTest(url=url), self.assertRaises(LocationError):
                checked_url(url)
        with self.assertRaises(LocationError):
            SafeRedirects().redirect_request(None, None, 302, "", {}, "http://127.0.0.1/")
        for value in ("91,69", "41,181"):
            with self.assertRaises(LocationError):
                parse_location(value)

    @patch("driver_notifications.locations.urllib.request.build_opener")
    def test_missing_pin_does_not_invent_coordinates(self, build):
        response = MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "https://www.google.com/maps/place/X/@40,68,12z"
        response.read.return_value = b"<html>No coordinates</html>"
        build.return_value.open.return_value = response
        with self.assertRaises(LocationError):
            parse_location("https://maps.app.goo.gl/example")


@patch("driver_notifications.telegram.reverse_place", side_effect=lambda lat, lon: {"name": "Toshkent" if lat > 40.5 else "Samarqand", "address": f"Address {lat}, {lon}", "geocoded": True})
@patch("driver_notifications.telegram.call", return_value={"message_id": 1})
class BotLocationTests(TestCase):
    def setUp(self):
        self.driver = get_user_model().objects.create_user(username="location_driver", role="driver")
        self.vehicle = Vehicle.objects.create(owner=self.driver, name="Tent", kind="tent", capacity_tons=20)
        self.account = TelegramAccount.objects.create(owner=self.driver, chat_id=123)

    def send(self, text=None, location=None, venue=None):
        message = {"chat": {"id": 123, "type": "private"}, "from": {"id": 123}}
        if text is not None:
            message["text"] = text
        if location:
            message["location"] = location
        if venue:
            message["venue"] = venue
        handle_update({"message": message})
        self.account.refresh_from_db()

    def tap(self, action):
        self.account.refresh_from_db()
        payload = next(v for v in self.account.ui["actions"].values() if v == action or v.endswith(":" + action))
        handle_update({"callback_query": {"id": "q", "from": {"id": 123}, "data": payload, "message": {"chat": {"id": 123, "type": "private"}, "message_id": 1}}})
        self.account.refresh_from_db()

    def start_at(self, key, data=None):
        self.account.state = {"flow": "ticket", "version": TICKET_FLOW_VERSION, "index": TICKET_STEPS.index(key), "data": data or {}}
        self.account.save()

    def begin(self):
        for text in ("/ticket", "Xaritadan tiket", str(self.vehicle.pk)):
            self.send(text)

    def test_multiple_locations_resolve_names_without_city_question(self, call, reverse):
        self.begin()
        self.send(location={"latitude": 41.3, "longitude": 69.2})
        self.assertNotIn("pending_place", self.account.state)
        self.assertEqual(self.account.state["data"]["origins"][0]["name"], "Toshkent")
        markup = next(c.kwargs["reply_markup"] for c in reversed(call.call_args_list) if c.args[0] == "sendMessage")
        self.assertIn("inline_keyboard", markup)
        self.tap("add_place")
        self.send("https://www.google.com/maps/search/?api=1&query=41.47,69.58")
        self.tap("done")
        self.send("https://yandex.ru/maps/?whatshere%5Bpoint%5D=66.96,39.65")
        self.tap("add_place")
        self.send(location={"latitude": 39.7, "longitude": 66.9})
        self.assertFalse(Ticket.objects.exists())
        self.tap("done")
        self.assertEqual(self.account.state, {})
        ticket = Ticket.objects.get()
        self.assertEqual(len(ticket.origins), 2)
        self.assertEqual(len(ticket.destinations), 2)
        self.assertEqual(ticket.origins[1]["source_url"], "https://www.google.com/maps/search/?api=1&query=41.47,69.58")
        self.assertEqual(ticket.destinations[0]["name"], "Samarqand")
        self.assertEqual(ticket.destinations[0]["lon"], 66.96)
        self.assertIn("address", ticket.destinations[0])
        self.assertEqual(ticket.available_tons, self.vehicle.capacity_tons)
        self.assertEqual(ticket.match_mode, "route")
        self.assertEqual(ticket.min_price, 0)
        self.assertLess(abs((ticket.expires_at - ticket.ready_at).total_seconds() - 7*86400), 1)

    def test_anywhere_saves_immediately_without_extra_steps(self, call, reverse):
        self.begin()
        self.send(venue={"title": "Ombor", "location": {"latitude": 41.3, "longitude": 69.2}})
        self.tap("done")
        self.tap("anywhere")
        self.assertEqual(self.account.state, {})
        ticket = Ticket.objects.get()
        self.assertEqual(ticket.route_mode, "anywhere")
        self.assertEqual(ticket.destinations, [])
        self.assertEqual(ticket.origins[0]["name"], "Toshkent")

    def test_repeated_save_callback_does_not_create_a_second_ticket(self, call, reverse):
        self.begin()
        self.send(location={"latitude": 41.3, "longitude": 69.2})
        self.tap("done")
        payload = next(v for v in self.account.ui["actions"].values() if v.endswith(":anywhere"))
        for _ in range(2):
            handle_update({"callback_query": {"id": "q", "from": {"id": 123}, "data": payload, "message": {"chat": {"id": 123, "type": "private"}, "message_id": 1}}})
        self.assertEqual(Ticket.objects.count(), 1)

    def test_geocoder_failure_keeps_location_step_and_does_not_save_gps(self, call, reverse):
        reverse.side_effect = LocationError("geocoding")
        self.begin()
        self.send(location={"latitude": 41.3, "longitude": 69.2})
        self.assertEqual(self.account.state["index"], TICKET_STEPS.index("origins"))
        self.assertFalse(self.account.state["data"].get("origins"))
        self.assertFalse(Ticket.objects.exists())
        self.assertNotIn("pending_place", self.account.state)

    def test_repeated_location_is_not_duplicated_and_limit_is_enforced(self, call, reverse):
        self.begin()
        for _ in range(2):
            self.send(location={"latitude": 41.3, "longitude": 69.2})
        self.assertEqual(len(self.account.state["data"]["origins"]), 1)
        for i in range(1, 11):
            self.send(location={"latitude": 41.3+i/100, "longitude": 69.2})
        self.assertEqual(len(self.account.state["data"]["origins"]), 10)

    def test_invalid_link_and_empty_origin_cannot_advance(self, call, reverse):
        self.begin()
        for text in ("done", "anywhere", "Toshkent", "https://localhost/maps"):
            self.send(text)
        self.assertEqual(self.account.state["index"], TICKET_STEPS.index("origins"))
        self.assertFalse(Ticket.objects.exists())
        reverse.assert_not_called()

    def test_only_own_vehicle_can_be_selected(self, call, reverse):
        other = get_user_model().objects.create_user(username="other_driver", role="driver")
        vehicle = Vehicle.objects.create(owner=other, name="Other", kind="tent", capacity_tons=20)
        self.send("/ticket")
        self.send("Test")
        self.send(str(vehicle.pk))
        self.assertEqual(self.account.state["index"], TICKET_STEPS.index("vehicle"))
        self.assertNotIn("vehicle", self.account.state["data"])

    def test_new_vehicle_returns_to_ticket_without_losing_title(self, call, reverse):
        self.send("/ticket")
        self.send("Test")
        self.tap("nav:vehicle")
        for text in ("Isuzu", "van", "5", "-", "-", "ha"):
            self.send(text)
        self.assertEqual(self.account.state["flow"], "ticket")
        self.assertEqual(self.account.state["data"]["title"], "Test")
        self.assertEqual(self.account.state["index"], TICKET_STEPS.index("origins"))
        self.assertEqual(Vehicle.objects.get(pk=self.account.state["data"]["vehicle"]).name, "Isuzu")

    def test_old_flow_state_restarts_safely_after_deploy(self, call, reverse):
        self.account.state = {"flow": "ticket", "index": 20, "data": {"title": "Old"}}
        self.account.save()
        self.send("hello")
        self.assertEqual(self.account.state["version"], TICKET_FLOW_VERSION)
        self.assertEqual(self.account.state["index"], 0)

    def test_multiple_pickups_and_destinations_match_all_chosen_combinations(self, call, reverse):
        from cargo.models import Load
        from .matching import evaluate

        reverse.side_effect = lambda lat, lon: {"name": {41.3: "Toshkent", 41.47: "Chirchiq", 39.65: "Samarqand", 39.77: "Buxoro"}[lat], "geocoded": True}
        self.begin()
        for lat in (41.3, 41.47):
            self.send(location={"latitude": lat, "longitude": 69.2})
        self.tap("done")
        for lat in (39.65, 39.77):
            self.send(location={"latitude": lat, "longitude": 66.9})
        self.tap("done")
        ticket = Ticket.objects.get()
        sender = get_user_model().objects.create_user(username="multi_shipper")
        load = Load(posted_by=sender, cargo_name="Yuk", vehicle_type="Tent", weight_tons=10)
        for origin in ("Toshkent", "Chirchiq"):
            for destination in ("Samarqand", "Buxoro"):
                load.origin, load.destination = origin, destination
                self.assertTrue(evaluate(ticket, load)["checks"]["route"])
        load.destination = "Namangan"
        self.assertIsNone(evaluate(ticket, load))

    def test_anywhere_still_requires_a_chosen_pickup(self, call, reverse):
        from cargo.models import Load
        from .matching import evaluate

        self.begin()
        self.send(location={"latitude": 41.3, "longitude": 69.2})
        self.tap("done")
        self.tap("anywhere")
        ticket = Ticket.objects.get()
        sender = get_user_model().objects.create_user(username="anywhere_shipper")
        load = Load(posted_by=sender, origin="Tashkent", destination="Nukus", cargo_name="Yuk", vehicle_type="Tent", weight_tons=10)
        self.assertIsNotNone(evaluate(ticket, load))
        load.origin = "Buxoro"
        self.assertIsNone(evaluate(ticket, load))

    def test_bot_ticket_matches_on_site_and_delivers_in_telegram(self, call, reverse):
        from cargo.models import Load
        from rest_framework.test import APIClient
        from .delivery import deliver
        from .models import Notification
        from .service import scan_ticket
        from .matching import evaluate

        sender = get_user_model().objects.create_user(username="shipper", role="dispatcher")
        matching = Load.objects.create(posted_by=sender, origin="Ташкент", destination="Самарканд", cargo_name="Sement", vehicle_type="Tent", weight_tons=10, contact_phone="998901234567")
        wrong_route = Load.objects.create(posted_by=sender, origin="Nukus", destination="Самарканд", cargo_name="Sement", vehicle_type="Tent", weight_tons=10, contact_phone="998901234567")
        wrong_vehicle = Load.objects.create(posted_by=sender, origin="Ташкент", destination="Самарканд", cargo_name="Sement", vehicle_type="Refrigerator", weight_tons=10, contact_phone="998901234567")
        overweight = Load.objects.create(posted_by=sender, origin="Ташкент", destination="Самарканд", cargo_name="Sement", vehicle_type="Tent", weight_tons=25, contact_phone="998901234567")
        self.begin()
        self.send(location={"latitude": 41.3, "longitude": 69.2})
        self.tap("done")
        self.send(location={"latitude": 39.65, "longitude": 66.96})
        self.tap("done")
        ticket = Ticket.objects.get()
        self.assertIsNotNone(evaluate(ticket, matching))
        for load in (wrong_route, wrong_vehicle, overweight):
            self.assertIsNone(evaluate(ticket, load))
        note = Notification.objects.get(kind="match")
        self.assertEqual(note.load_id, matching.pk)
        self.assertLessEqual(note.deliver_after, timezone.now())
        client = APIClient()
        client.force_authenticate(self.driver)
        self.assertEqual(client.get("/api/driver/tickets/").data[0]["id"], ticket.pk)
        self.assertEqual(client.get("/api/driver/notifications/unread/").data["count"], 2)
        with patch("driver_notifications.delivery.call", return_value={"message_id": 44}) as send:
            deliver()
            deliver()
        note.refresh_from_db()
        self.assertIsNotNone(note.sent_at)
        self.assertTrue(any("Ташкент" in c.kwargs.get("text", "") for c in send.call_args_list))
        later = Load.objects.create(posted_by=sender, origin="Toshkent", destination="Samarqand", cargo_name="Yangi yuk", vehicle_type="Tent", weight_tons=5, contact_phone="998901234567", currency="USD", price_amount=100)
        scan_ticket(ticket.pk)
        self.assertTrue(Notification.objects.filter(kind="match", load=later).exists())
