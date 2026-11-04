import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from .city_search import CitySearchUnavailable, search_cities


class CitySearchTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("cargo.city_search.urllib.request.urlopen")
    def test_worldwide_results_keep_country_and_are_cached_by_language(self, open_url):
        feature = {"properties": {"name": "Berlin", "state": "Berlin", "country": "Germany", "countrycode": "DE", "osm_type": "N", "osm_id": 42}, "geometry": {"coordinates": [13.4, 52.5]}}
        open_url.return_value.__enter__.return_value.read.return_value = json.dumps({"features": [feature, feature]}).encode()
        first = search_cities("Ber", "en")
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["description"], "Germany")
        self.assertEqual(first[0]["country_code"], "DE")
        self.assertEqual(first[0]["lat"], 52.5)
        self.assertEqual(search_cities("ber", "en"), first)
        open_url.assert_called_once()
        params = parse_qs(urlparse(open_url.call_args.args[0].full_url).query)
        self.assertEqual(params["layer"], ["city", "locality", "state"])
        search_cities("Ber", "ru")
        self.assertEqual(open_url.call_count, 2)

    @patch("cargo.city_search.urllib.request.urlopen")
    def test_empty_results_and_invalid_coordinates_are_not_invented(self, open_url):
        open_url.return_value.__enter__.return_value.read.return_value = json.dumps({"features": [{"properties": {"name": "Invalid"}, "geometry": {"coordinates": [200, 95]}}]}).encode()
        self.assertEqual(search_cities("Unknown"), [])
        self.assertEqual(search_cities("Unknown"), [])
        open_url.assert_called_once()

    @patch("cargo.city_search.urllib.request.urlopen", side_effect=OSError("Offline"))
    def test_failed_provider_returns_controlled_error(self, open_url):
        with self.assertRaises(CitySearchUnavailable):
            search_cities("Toshkent")

    @patch("cargo.city_views.search_cities", return_value=[])
    def test_public_endpoint_rejects_oversized_query_and_skips_one_letter(self, search):
        client = APIClient()
        self.assertEqual(client.get("/api/cargo/cities/?q=T").data, [])
        self.assertEqual(client.get("/api/cargo/cities/", {"q": "x" * 151}).status_code, 400)
        search.assert_not_called()
        self.assertEqual(client.get("/api/cargo/cities/", {"q": "  Москва ", "lang": "ru"}).status_code, 200)
        search.assert_called_once_with("Москва", "default")

    @patch("cargo.city_views.search_cities", side_effect=CitySearchUnavailable)
    def test_public_endpoint_reports_outage(self, search):
        self.assertEqual(APIClient().get("/api/cargo/cities/?q=Berlin").status_code, 503)
