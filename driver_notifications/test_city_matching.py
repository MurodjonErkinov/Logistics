from django.test import SimpleTestCase

from .matching import place_matches


class CityMatchingTests(SimpleTestCase):
    def test_common_city_spellings(self):
        groups = [
            ("Toshkent", "Tashkent", "ТАШКЕНТ", "Toshken", "Tashken", "Ташкен"),
            ("Samarqand", "Samarkand", "Самарканд"),
            ("Farg‘ona", "Fergana", "Фергана", "Farg'ona"),
            ("Qo‘qon", "Kokand", "Коканд"),
            ("Andijon", "Andijan", "Андижан"),
            ("Chirchiq", "Chirchik", "Чирчик"),
            ("Xiva", "Khiva", "Хива"),
        ]
        for group in groups:
            for spelling in group:
                with self.subTest(spelling=spelling):
                    self.assertTrue(place_matches({"name": group[0]}, {"name": spelling}))

    def test_different_cities_do_not_match(self):
        self.assertFalse(place_matches({"name": "Toshkent"}, {"name": "Samarqand"}))
