from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .locations import LocationError, SafeRedirects, checked_url, coordinates_from_url, parse_location
from .models import TelegramAccount, Ticket, Vehicle
from .serializers import TicketSerializer
from .telegram import TICKET_STEPS, handle_update


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

    def start_at(self, key, data=None):
        self.account.state = {"flow": "ticket", "index": TICKET_STEPS.index(key), "data": data or {}}
        self.account.save()

    def test_current_location_accepts_map_link(self, call):
        self.start_at("current_location")
        self.send("https://yandex.ru/maps/?whatshere%5Bpoint%5D=69.2,41.3")
        self.assertEqual(self.account.state["data"]["current_location"]["lat"], 41.3)
        self.assertEqual(self.account.state["index"], TICKET_STEPS.index("origins"))

    def test_collect_multiple_locations_and_skip_coordinate_prompt(self, call):
        self.start_at("origins")
        self.send(location={"latitude": 41.3, "longitude": 69.2})
        self.assertIn("pending_place", self.account.state)
        self.send("Toshkent")
        self.send("Chirchiq https://www.google.com/maps/search/?api=1&query=41.47,69.58")
        self.assertEqual(len(self.account.state["data"]["origins"]), 2)
        self.send("Tayyor")
        self.assertEqual(self.account.state["index"], TICKET_STEPS.index("origin_radius"))
        self.assertNotIn("pending_place", self.account.state)
        self.assertEqual(self.account.state["data"]["origins"][1]["lon"], 69.58)

    def test_named_cities_receive_points_one_by_one_and_skip(self, call):
        self.start_at("origins")
        self.send("Toshkent, Chirchiq")
        self.send(location={"latitude": 41.3, "longitude": 69.2})
        self.assertEqual(self.account.state["point_index"], 1)
        self.assertIn("Chirchiq", call.call_args.kwargs["text"])
        self.send("O‘tkazib yuborish")
        self.assertEqual(self.account.state["index"], TICKET_STEPS.index("origin_radius"))
        self.assertIn("lat", self.account.state["data"]["origins"][0])
        self.assertNotIn("lat", self.account.state["data"]["origins"][1])

    def test_mixed_collected_places_target_correct_missing_point(self, call):
        self.start_at("destinations")
        self.send("Toshkent https://yandex.ru/maps/?ll=69.2,41.3")
        self.send("Chirchiq")
        self.send("Tayyor")
        self.assertEqual(self.account.state["point_index"], 1)
        self.send("https://www.google.com/maps/search/?api=1&query=41.47,69.58")
        places = self.account.state["data"]["destinations"]
        self.assertEqual(places[0]["lat"], 41.3)
        self.assertEqual(places[1]["lat"], 41.47)
        self.assertEqual(self.account.state["index"], TICKET_STEPS.index("prices"))

    def test_map_source_and_coordinates_saved_to_ticket(self, call):
        link = "https://www.google.com/maps/search/?api=1&query=41.3,69.2"
        from .locations import parse_location
        place = parse_location("Toshkent " + link)
        data = {"title": "Xarita", "vehicle": self.vehicle.pk, "origins": [place], "destinations": [{"name": "Samarqand"}], "ready_at": timezone.now().isoformat(), "expires_at": (timezone.now()+timedelta(days=1)).isoformat(), "available_tons": "20", "min_price": "0"}
        serializer = TicketSerializer(data=data, context={"request": SimpleNamespace(user=self.driver)})
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save(owner=self.driver)
        self.assertEqual(ticket.origins[0]["source_url"], link)
        self.assertEqual(ticket.origins[0]["lat"], 41.3)

    def test_invalid_link_keeps_step(self, call):
        self.start_at("destination_points", {"destinations": [{"name": "Toshkent"}]})
        self.send("https://localhost/maps")
        self.assertEqual(self.account.state["index"], TICKET_STEPS.index("destination_points"))
        self.assertNotIn("lat", self.account.state["data"]["destinations"][0])
        self.assertIn("Telegram", call.call_args.kwargs["text"])

    def test_back_and_cancel_clear_pending_location(self, call):
        self.start_at("waypoints")
        self.send(location={"latitude": 41.3, "longitude": 69.2})
        self.send("/back")
        self.assertNotIn("pending_place", self.account.state)
        self.send("/cancel")
        self.assertEqual(self.account.state, {})

    def test_complete_ticket_wizard_with_telegram_and_map_locations(self, call):
        for text in ("/ticket", "Xaritadan tiket", str(self.vehicle.pk)):
            self.send(text)
        self.send(location={"latitude": 41.3, "longitude": 69.2})
        self.send(location={"latitude": 41.31, "longitude": 69.21})
        self.send("Toshkent")
        self.send("Tayyor")
        self.send("25")
        self.send("alternatives")
        self.send("Samarqand https://yandex.ru/maps/?whatshere%5Bpoint%5D=66.96,39.65")
        self.send("Tayyor")
        for text in ("2000000", "2", "1", "30", "-", "168", "20", "yoq", "UZS", "trip", "2000000", "any_two"):
            self.send(text)
        self.send("Jizzax https://www.google.com/maps/search/?api=1&query=40.12,67.84")
        self.send("Tayyor")
        self.send("-")
        self.send("ha")
        self.assertEqual(self.account.state, {})
        ticket = Ticket.objects.get(title="Xaritadan tiket")
        self.assertEqual(ticket.current_location["lat"], 41.3)
        self.assertEqual(ticket.origins[0]["name"], "Toshkent")
        self.assertEqual(ticket.origins[0]["lat"], 41.31)
        self.assertEqual(ticket.destinations[0]["lon"], 66.96)
        self.assertEqual(ticket.waypoints[0]["lat"], 40.12)
