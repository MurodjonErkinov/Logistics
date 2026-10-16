import os
import uuid
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from driver_notifications.models import TelegramAccount
from driver_notifications.telegram import BotError, handle_update
from .models import RegistrationVerification
from .verification import code_digest, new_verification, register_verified_user


@patch.dict(os.environ, {"DRIVER_BOT_TOKEN": "test-token", "DRIVER_BOT_USERNAME": "YukFlowTestBot"})
@patch("driver_notifications.telegram.call", return_value={"message_id": 55})
class RegistrationVerificationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.phone = "+998901234567"
        self.account = {"username": "new_person", "password": "AnUnusualPass471!", "phone_number": self.phone, "role": "driver"}

    def start(self, phone=None):
        response = self.client.post("/api/auth/registration-code/", {"phone_number": phone or self.phone}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.account["verification_id"] = response.data["verification_id"]
        self.assertIn("?start=reg_", response.data["bot_url"])
        return RegistrationVerification.objects.get(verification_id=response.data["verification_id"])

    def message(self, **parts):
        handle_update({"message": {"chat": {"id": 123, "type": "private"}, "from": {"id": 123}, "message_id": 10, **parts}})

    def issue(self):
        row = self.start()
        self.message(text=f"/start reg_{row.verification_id.hex}")
        with patch("authentication.telegram_verification.secrets.randbelow", return_value=123456):
            self.message(contact={"user_id": 123, "phone_number": self.phone.lstrip("+")})
        self.account["verification_code"] = "123456"
        return row

    def register(self):
        return self.client.post("/api/auth/register/", self.account, format="json")

    def test_registration_requires_phone_and_telegram_code(self, call):
        response = self.register()
        self.assertEqual(response.status_code, 400)
        self.assertIn("verification_code", response.data)
        self.assertFalse(get_user_model().objects.exists())

    def test_both_roles_register_once_and_link_telegram(self, call):
        for role in ("driver", "dispatcher"):
            with self.subTest(role=role):
                row = self.issue()
                self.account["role"] = role
                result = self.register()
                self.assertEqual(result.status_code, 201, result.data)
                self.assertNotIn("verification_code", result.data)
                self.assertNotIn("verification_id", result.data)
                user = get_user_model().objects.get()
                self.assertEqual(user.phone_number, self.phone)
                self.assertEqual(user.role, role)
                self.assertEqual(TelegramAccount.objects.get(owner=user).chat_id, 123)
                row.refresh_from_db()
                self.assertIsNotNone(row.consumed_at)
                self.assertEqual(row.code_digest, "")
                self.account["username"] = "second_person"
                self.assertEqual(self.register().status_code, 400)
                get_user_model().objects.all().delete()
                RegistrationVerification.objects.all().delete()
                self.account["username"] = "new_person"
                cache.clear()

    def test_other_contact_and_wrong_phone_cannot_issue_code(self, call):
        row = self.start()
        self.message(text=f"/start reg_{row.verification_id.hex}")
        for contact in ({"user_id": 456, "phone_number": self.phone}, {"user_id": 123, "phone_number": "+998999999999"}):
            self.message(contact=contact)
            row.refresh_from_db()
            self.assertEqual(row.code_digest, "")
        self.account["verification_code"] = "123456"
        self.assertEqual(self.register().status_code, 400)
        self.message(text=self.phone)
        row.refresh_from_db()
        self.assertEqual(row.code_digest, "")

    def test_five_wrong_guesses_lock_code_and_survive_validation_errors(self, call):
        row = self.issue()
        self.account["verification_code"] = "111111"
        for _ in range(5):
            self.assertEqual(self.register().status_code, 400)
        row.refresh_from_db()
        self.assertEqual(row.attempts, 5)
        self.account["verification_code"] = "123456"
        self.assertEqual(self.register().status_code, 400)
        self.assertFalse(get_user_model().objects.exists())

    def test_expired_wrong_phone_and_forged_ids_fail(self, call):
        row = self.issue()
        self.account["verification_id"] = str(uuid.uuid4())
        self.assertEqual(self.register().status_code, 400)
        self.account["verification_id"] = str(row.verification_id)
        self.account["phone_number"] = "+998999999999"
        self.assertEqual(self.register().status_code, 400)
        self.account["phone_number"] = self.phone
        row.expires_at = timezone.now() - timedelta(seconds=1)
        row.save()
        self.assertEqual(self.register().status_code, 400)

    def test_resend_cooldown_revokes_previous_code_and_link(self, call):
        row = self.issue()
        old_id = row.verification_id
        response = self.client.post("/api/auth/registration-code/", {"phone_number": self.phone}, format="json")
        self.assertEqual(response.status_code, 429)
        row.requested_at -= timedelta(minutes=2)
        row.save()
        fresh = self.start()
        self.assertNotEqual(fresh.verification_id, old_id)
        self.assertEqual(fresh.code_digest, "")
        self.account["verification_id"] = str(old_id)
        self.assertEqual(self.register().status_code, 400)

    def test_code_hash_only_and_duplicate_contact_does_not_rotate(self, call):
        row = self.issue()
        row.refresh_from_db()
        self.assertNotIn("123456", row.code_digest)
        digest = row.code_digest
        call.reset_mock()
        self.message(contact={"user_id": 123, "phone_number": self.phone})
        row.refresh_from_db()
        self.assertEqual(row.code_digest, digest)
        self.assertFalse(any(c.args[0] == "sendMessage" for c in call.call_args_list))

    def test_already_registered_phone_or_telegram_cannot_create_second_account(self, call):
        self.issue()
        old = get_user_model().objects.create_user(username="old", phone_number=self.phone)
        self.assertEqual(self.register().status_code, 400)
        old.phone_number = "+998999999999"
        old.save()
        TelegramAccount.objects.create(owner=old, chat_id=123)
        self.assertEqual(self.register().status_code, 400)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_private_self_contact_required(self, call):
        row = self.start()
        for chat_type, sender in (("group", 123), ("private", 999)):
            handle_update({"message": {"chat": {"id": 123, "type": chat_type}, "from": {"id": sender}, "text": f"/start reg_{row.verification_id.hex}"}})
        row.refresh_from_db()
        self.assertIsNone(row.chat_id)

    def test_missing_bot_configuration_fails_closed(self, call):
        with patch.dict(os.environ, {"DRIVER_BOT_TOKEN": ""}):
            response = self.client.post("/api/auth/registration-code/", {"phone_number": self.phone}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(RegistrationVerification.objects.exists())

    def test_failed_telegram_delivery_does_not_activate_code(self, call):
        row = self.start()
        self.message(text=f"/start reg_{row.verification_id.hex}")
        call.side_effect = BotError("network")
        with self.assertRaises(BotError):
            self.message(contact={"user_id": 123, "phone_number": self.phone})
        row.refresh_from_db()
        self.assertEqual(row.code_digest, "")

    def test_new_link_cannot_be_claimed_by_other_telegram_chat(self, call):
        row = self.start()
        self.message(text=f"/start reg_{row.verification_id.hex}")
        handle_update({"message": {"chat": {"id": 999, "type": "private"}, "from": {"id": 999}, "text": f"/start reg_{row.verification_id.hex}"}})
        row.refresh_from_db()
        self.assertEqual(row.chat_id, 123)

    def test_issued_code_accepts_only_its_phone_and_role_is_restricted(self, call):
        self.issue()
        self.account["role"] = "admin"
        self.assertEqual(self.register().status_code, 400)
        self.account["role"] = "dispatcher"
        self.assertEqual(self.register().status_code, 201)
        self.message(text="/start")
        text = next(c.kwargs["text"] for c in reversed(call.call_args_list) if c.args[0] == "sendMessage")
        self.assertIn("Yuk joylash", text)

    def test_start_reports_missing_expired_used_and_other_account_separately(self, call):
        def last_text():
            return next(c.kwargs["text"] for c in reversed(call.call_args_list) if c.args[0] == "sendMessage")
        with self.assertLogs("authentication.telegram_verification", level="WARNING") as logs:
            self.message(text=f"/start reg_{uuid.uuid4().hex}")
        self.assertIn("request_not_found", logs.output[0])
        self.assertIn("topilmadi", last_text())
        row = self.start()
        row.expires_at = timezone.now() - timedelta(seconds=1)
        row.save()
        self.message(text=f"/start reg_{row.verification_id.hex}")
        self.assertIn("muddati tugagan", last_text())
        row.consumed_at = timezone.now()
        row.save()
        self.message(text=f"/start reg_{row.verification_id.hex}")
        self.assertIn("allaqachon tasdiqlangan", last_text())
        row.consumed_at = None
        row.expires_at = timezone.now() + timedelta(minutes=5)
        row.chat_id = 999
        row.save()
        self.message(text=f"/start reg_{row.verification_id.hex}")
        self.assertIn("boshqa Telegram", last_text())

    def test_conflict_error_explains_duplicate_polling_without_echoing_api_data(self, call):
        self.assertIn("another bot instance", str(BotError(409)))
        self.assertIn("webhook is active", str(BotError(409, description="Conflict: webhook is active")))


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentRegistrationTests(TransactionTestCase):
    def setUp(self):
        self.row = new_verification("+998901234567")
        self.row.chat_id = 123
        self.row.code_digest = code_digest(self.row, "123456")
        self.row.save()

    def submit_concurrently(self, codes):
        barrier = Barrier(len(codes))

        def submit(item):
            index, code = item
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                register_verified_user({"username": f"parallel_{index}", "password": "AnUnusualPass471!", "phone_number": self.row.phone_number, "role": "driver", "verification_id": self.row.verification_id, "verification_code": code})
                return "created"
            except ValidationError:
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(codes)) as pool:
            return list(pool.map(submit, enumerate(codes)))

    def test_concurrent_code_reuse_creates_exactly_one_account(self):
        results = self.submit_concurrently(["123456", "123456"])
        self.assertCountEqual(results, ["created", "rejected"])
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(TelegramAccount.objects.count(), 1)

    def test_parallel_wrong_guesses_cannot_lose_attempt_counts(self):
        self.assertEqual(self.submit_concurrently(["111111"] * 5), ["rejected"] * 5)
        self.row.refresh_from_db()
        self.assertEqual(self.row.attempts, 5)
        self.assertEqual(self.submit_concurrently(["123456"]), ["rejected"])
        self.assertFalse(get_user_model().objects.exists())
