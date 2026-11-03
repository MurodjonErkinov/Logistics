from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Load, LoadClaim


class LoadClaimTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.driver = users.objects.create_user(username="driver", role="driver")
        self.other = users.objects.create_user(username="other_driver", role="driver")
        self.sender = users.objects.create_user(username="sender", role="dispatcher")
        self.load = Load.objects.create(posted_by=self.sender, origin="Toshkent", destination="Namangan", cargo_name="Meva", vehicle_type="Tent", weight_tons=5, contact_phone="901234567")
        self.client = APIClient()
        self.url = f"/api/cargo/loads/{self.load.pk}/claim/"

    def claim(self, user=None, **body):
        self.client.force_authenticate(user=user or self.driver)
        return self.client.post(self.url, {"confirmed_contact": True, **body}, format="json")

    def test_driver_must_explicitly_confirm_contact(self):
        for value in (None, False, "true", 1):
            with self.subTest(value=value):
                self.assertEqual(self.claim(confirmed_contact=value).status_code, 400)
        self.assertFalse(LoadClaim.objects.exists())
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 400)
        self.assertEqual(self.claim().status_code, 201)

    def test_multiple_drivers_and_duplicate_clicks(self):
        first = self.claim()
        self.assertTrue(first.data["is_claimed"])
        self.assertEqual(first.data["claim_count"], 1)
        self.assertIsNotNone(first.data["claimed_at"])
        self.assertEqual(self.claim().status_code, 200)
        second = self.claim(self.other)
        self.assertEqual(second.data["claim_count"], 2)
        self.assertEqual(LoadClaim.objects.count(), 2)
        self.load.refresh_from_db()
        self.assertEqual(self.load.status, "open")

    def test_only_drivers_can_take_someone_elses_load(self):
        self.assertEqual(self.client.post(self.url, {"confirmed_contact": True}).status_code, 401)
        self.assertEqual(self.claim(self.sender).status_code, 403)
        self.load.posted_by = self.driver
        self.load.save()
        self.assertEqual(self.claim().status_code, 400)
        self.assertFalse(LoadClaim.objects.exists())

    def test_taken_list_is_personal_and_does_not_grant_edit_permission(self):
        self.claim()
        self.assertEqual([l["id"] for l in self.client.get("/api/cargo/loads/?claimed=1").data], [self.load.pk])
        self.assertEqual(self.client.patch(f"/api/cargo/loads/{self.load.pk}/", {"status": "closed"}).status_code, 403)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/cargo/loads/?claimed=1").data, [])
        detail = self.client.get(f"/api/cargo/loads/{self.load.pk}/").data
        self.assertEqual(detail["claim_count"], 1)
        self.assertFalse(detail["is_claimed"])
        self.assertIsNone(detail["claimed_at"])
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/cargo/loads/?claimed=1").status_code, 401)

    def test_closed_load_cannot_be_taken_but_existing_claim_remains(self):
        self.claim()
        self.load.status = "closed"
        self.load.save()
        self.assertEqual(self.claim(self.other).status_code, 400)
        self.assertEqual(self.claim().status_code, 200)
        self.assertEqual(len(self.client.get("/api/cargo/loads/?claimed=1").data), 1)

    def test_expired_telegram_listing_stays_in_claiming_drivers_cabinet(self):
        from telegram_import.models import TelegramPost, TelegramLoad

        now = timezone.now()
        post = TelegramPost.objects.create(chat_id=-100123, message_id=10, group_name="@loads", text="Yuk", posted_at=now, expires_at=now+timedelta(days=1), status="imported")
        entry = TelegramLoad.objects.create(post=post, position=1, load=self.load, status="imported", expires_at=post.expires_at)
        self.assertEqual(self.claim().status_code, 201)
        entry.expires_at = now - timedelta(seconds=1)
        entry.save()
        self.assertEqual(self.client.get(f"/api/cargo/loads/{self.load.pk}/").status_code, 200)
        self.assertEqual(len(self.client.get("/api/cargo/loads/?claimed=1").data), 1)
        from telegram_import.service import delete_expired_loads

        self.assertEqual(delete_expired_loads(), 0)
        self.load.refresh_from_db()
        self.assertEqual(self.load.status, "closed")
        self.assertTrue(LoadClaim.objects.filter(load=self.load, driver=self.driver).exists())
        self.assertEqual(self.claim(self.other).status_code, 404)
