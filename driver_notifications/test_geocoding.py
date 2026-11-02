import json
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase

from .geocoding import reverse_place
from .locations import LocationError


@patch("driver_notifications.geocoding.time.sleep")
@patch("driver_notifications.geocoding.urllib.request.urlopen")
class ReverseGeocodingTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def response(self, open_url, properties):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({"features": [{"properties": properties}]}).encode()
        open_url.return_value = response

    def test_city_and_address_are_cached_without_replacing_coordinates(self, open_url, sleep):
        self.response(open_url, {"name": "Warehouse", "street": "Test street", "city": "Tashkent", "country": "Uzbekistan"})
        first = reverse_place(41.3, 69.2)
        self.assertEqual(first["name"], "Tashkent")
        self.assertIn("Test street", first["address"])
        self.assertEqual(reverse_place(41.3, 69.2), first)
        open_url.assert_called_once()
        request = open_url.call_args.args[0]
        self.assertIn("lat=41.3", request.full_url)
        self.assertIn("lon=69.2", request.full_url)
        self.assertIn("YukFlow", request.get_header("User-agent"))

    def test_settlement_feature_without_city_is_accepted(self, open_url, sleep):
        self.response(open_url, {"name": "Chirchiq", "osm_value": "town"})
        self.assertEqual(reverse_place(41.47, 69.58)["name"], "Chirchiq")

    def test_unidentified_building_does_not_become_a_city(self, open_url, sleep):
        self.response(open_url, {"name": "Warehouse", "osm_value": "building"})
        with self.assertRaises(LocationError):
            reverse_place(41.3, 69.2)

    def test_network_and_empty_result_are_recoverable(self, open_url, sleep):
        open_url.side_effect = OSError("offline")
        with self.assertRaises(LocationError):
            reverse_place(41.3, 69.2)
        open_url.side_effect = None
        self.response(open_url, {})
        open_url.return_value.read.return_value = b'{"features": []}'
        with self.assertRaises(LocationError):
            reverse_place(41.3, 69.2)
