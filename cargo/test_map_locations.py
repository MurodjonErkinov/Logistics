import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase

from .map_locations import city_point, load_map_points


@patch("cargo.map_locations.time.sleep")
class MapLocationTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("cargo.map_locations.urllib.request.urlopen")
    def test_city_search_is_cached_and_marked_approximate(self, open_url, sleep):
        payload = {"features": [{"geometry": {"coordinates": [71.67, 40.99]}, "properties": {"name": "Namangan", "country": "Uzbekistan"}}]}
        open_url.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        first = city_point("Namangan")
        self.assertEqual(first["lat"], 40.99)
        self.assertTrue(first["approximate"])
        self.assertEqual(city_point("Namangan"), first)
        open_url.assert_called_once()

    @patch("cargo.map_locations.urllib.request.urlopen", side_effect=OSError("offline"))
    def test_unavailable_service_returns_no_false_coordinates(self, open_url, sleep):
        self.assertIsNone(city_point("Unknown city"))
        self.assertIsNone(city_point("Unknown city"))
        open_url.assert_called_once()

    @patch("cargo.map_locations.city_point")
    def test_existing_coordinates_do_not_call_external_service(self, search, sleep):
        load = SimpleNamespace(origin="A", destination="B", origin_lat=41, origin_lon=69, destination_lat=40, destination_lon=71)
        result = load_map_points(load)
        self.assertFalse(result["origin"]["approximate"])
        self.assertEqual(result["destination"]["lon"], 71)
        search.assert_not_called()
