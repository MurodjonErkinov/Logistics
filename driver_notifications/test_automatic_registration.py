from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from authentication.models import RegistrationVerification
from .models import Preference, TelegramAccount


class AutomaticRegistrationMigrationTests(TestCase):
    def migrate(self):
        module = import_module("driver_notifications.migrations.0004_automatic_registration_notifications")
        module.automatic_registration_notifications(apps, SimpleNamespace(connection=connection))

    def test_recovers_only_consumed_verified_phone_and_preserves_scheduling(self):
        user = get_user_model().objects.create_user(username="verified", phone_number="+998901234567", role="driver")
        Preference.objects.create(owner=user, telegram_enabled=False, quiet_start="22:00", quiet_end="07:00", partial_interval_minutes=15)
        RegistrationVerification.objects.create(phone_number=user.phone_number, requested_at=timezone.now(), expires_at=timezone.now(), consumed_at=timezone.now(), chat_id=123)
        self.migrate()
        self.assertEqual(TelegramAccount.objects.get(owner=user).chat_id, 123)
        pref = Preference.objects.get(owner=user)
        self.assertTrue(pref.telegram_enabled)
        self.assertEqual(pref.partial_interval_minutes, 15)
        self.assertEqual(str(pref.quiet_start), "22:00:00")
        self.migrate()
        self.assertEqual(TelegramAccount.objects.count(), 1)

    def test_does_not_steal_chat_from_other_user_or_link_unverified_phone(self):
        existing = get_user_model().objects.create_user(username="existing")
        TelegramAccount.objects.create(owner=existing, chat_id=123)
        verified = get_user_model().objects.create_user(username="verified", phone_number="+998901234567")
        RegistrationVerification.objects.create(phone_number=verified.phone_number, requested_at=timezone.now(), expires_at=timezone.now(), consumed_at=timezone.now(), chat_id=123)
        unverified = get_user_model().objects.create_user(username="unverified", phone_number="+998909999999")
        RegistrationVerification.objects.create(phone_number=unverified.phone_number, requested_at=timezone.now(), expires_at=timezone.now(), chat_id=456)
        self.migrate()
        self.assertEqual(TelegramAccount.objects.get(chat_id=123).owner, existing)
        self.assertFalse(TelegramAccount.objects.filter(owner__in=[verified, unverified]).exists())

    def test_registration_chat_replaces_a_legacy_manual_link_and_clears_old_chat_ui(self):
        user = get_user_model().objects.create_user(username="verified", phone_number="+998901234567", role="driver")
        TelegramAccount.objects.create(owner=user, chat_id=999, ui={"message_id": 88}, state={"flow": "preferences", "index": 1})
        RegistrationVerification.objects.create(phone_number=user.phone_number, requested_at=timezone.now(), expires_at=timezone.now(), consumed_at=timezone.now(), chat_id=123)
        self.migrate()
        account = TelegramAccount.objects.get(owner=user)
        self.assertEqual(account.chat_id, 123)
        self.assertEqual(account.state, {})
        self.assertEqual(account.ui, {})
