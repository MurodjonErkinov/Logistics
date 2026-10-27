from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .maintenance import close_stale_loads
from .models import Load


class StaleLoadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="owner")

    def load(self, updated_days_ago=0, pickup_days=None):
        load = Load.objects.create(
            posted_by=self.user, origin="Andijon", destination="Namangan", cargo_name="Un",
            vehicle_type="Tent", weight_tons=5, contact_phone="938086599",
            pickup_date=None if pickup_days is None else timezone.localdate() + timedelta(days=pickup_days),
        )
        Load.objects.filter(pk=load.pk).update(updated_at=timezone.now() - timedelta(days=updated_days_ago))
        return load

    def status(self, load):
        load.refresh_from_db()
        return load.status

    def test_closes_untouched_and_past_pickup_loads(self):
        fresh = self.load(updated_days_ago=13)
        untouched = self.load(updated_days_ago=15)
        past_pickup = self.load(updated_days_ago=2, pickup_days=-1)
        future_pickup = self.load(updated_days_ago=2, pickup_days=1)
        self.assertEqual(close_stale_loads(), 2)
        self.assertEqual(self.status(fresh), "open")
        self.assertEqual(self.status(untouched), "closed")
        self.assertEqual(self.status(past_pickup), "closed")
        self.assertEqual(self.status(future_pickup), "open")

    def test_reopened_load_stays_open_for_the_rest_of_the_day(self):
        reopened = self.load(updated_days_ago=0, pickup_days=-1)
        self.assertEqual(close_stale_loads(), 0)
        self.assertEqual(self.status(reopened), "open")
