import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from driver_notifications.models import TelegramAccount
from driver_notifications.telegram import BotError, handle_update
from .models import PasswordResetVerification
from .password_reset import new_password_reset, reset_code_digest, reset_password
from .verification import code_digest, new_verification


@patch.dict(os.environ, {"DRIVER_BOT_TOKEN": "test-token", "DRIVER_BOT_USERNAME": "YukFlowTestBot"})
@patch("driver_notifications.telegram.call", return_value={"message_id": 55})
class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.phone = "+998901234567"
        self.old_password = "OriginalSecret739!"
        self.new_password = "ChangedSecret851!"
        self.user = get_user_model().objects.create_user(
            username="existing_driver", phone_number=self.phone, password=self.old_password, role="driver",
        )
        self.account = TelegramAccount.objects.create(owner=self.user, chat_id=123)

    def start(self, phone=None):
        response = self.client.post("/api/auth/password-reset-code/", {"phone_number": phone or self.phone}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(set(response.data), {"verification_id", "bot_url", "retry_after"})
        self.assertIn("?start=reset_", response.data["bot_url"])
        return PasswordResetVerification.objects.get(verification_id=response.data["verification_id"])

    def message(self, row, chat=123, chat_type="private", sender=None):
        handle_update({"message": {"chat": {"id": chat, "type": chat_type}, "from": {"id": sender or chat},
                                  "message_id": 10, "text": f"/start reset_{row.verification_id.hex}"}})

    def issue(self):
        row = self.start()
        with patch("authentication.password_reset.secrets.randbelow", return_value=123456):
            self.message(row)
        row.refresh_from_db()
        return row

    def data(self, row, **changes):
        return {"phone_number": self.phone, "verification_id": str(row.verification_id), "verification_code": "123456",
                "password": self.new_password, "password_confirm": self.new_password, **changes}

    def submit(self, row, **changes):
        return self.client.post("/api/auth/reset-password/", self.data(row, **changes), format="json")

    def test_linked_account_gets_code_on_start_and_resets_once(self, call):
        TelegramAccount.objects.filter(owner=self.user).update(blocked=True)
        row = self.issue()
        self.assertFalse(TelegramAccount.objects.get(owner=self.user).blocked)
        sent = [c for c in call.call_args_list if c.args[0] == "sendMessage"]
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].kwargs["chat_id"], 123)
        self.assertIn("123456", sent[0].kwargs["text"])
        self.assertFalse(sent[0].kwargs.get("protect_content", False))
        self.assertEqual(sent[0].kwargs["parse_mode"], "HTML")
        self.assertIn("<code>123456</code>", sent[0].kwargs["text"])
        self.assertEqual(sent[0].kwargs["reply_markup"]["inline_keyboard"][0][0]["copy_text"], {"text": "123456"})
        self.assertNotIn("request_contact", str(sent[0].kwargs))
        self.assertNotIn("123456", row.code_digest)
        result = self.submit(row)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertNotIn(self.new_password, str(result.data))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertFalse(self.user.check_password(self.old_password))
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(TelegramAccount.objects.get(owner=self.user).chat_id, 123)
        row.refresh_from_db()
        self.assertIsNotNone(row.consumed_at)
        self.assertEqual(row.code_digest, "")
        self.assertEqual(self.submit(row).status_code, 400)
        self.assertEqual(self.client.post("/api/auth/login/", {"username": self.user.username, "password": self.old_password}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login/", {"username": self.user.username, "password": self.new_password}).status_code, 200)

    def test_old_access_and_refresh_tokens_are_revoked(self, call):
        refresh = RefreshToken.for_user(self.user)
        access = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        row = self.issue()
        self.assertEqual(self.submit(row).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.client.credentials()
        response = self.client.post("/api/auth/refresh/", {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_unknown_unlinked_duplicate_and_inactive_phones_do_not_issue_codes(self, call):
        for kind in ("unknown", "unlinked", "duplicate", "inactive"):
            with self.subTest(kind=kind):
                PasswordResetVerification.objects.all().delete()
                cache.clear()
                phone = self.phone
                duplicate = None
                if kind == "unknown":
                    phone = "+998999999999"
                elif kind == "unlinked":
                    self.account.delete()
                elif kind == "duplicate":
                    duplicate = get_user_model().objects.create_user(username="duplicate", phone_number=phone)
                elif kind == "inactive":
                    self.user.is_active = False
                    self.user.save()
                row = self.start(phone)
                self.assertIsNone(row.owner_id)
                self.message(row)
                row.refresh_from_db()
                self.assertEqual(row.code_digest, "")
                self.assertEqual(self.submit(row, phone_number=phone).status_code, 400)
                response = self.client.post("/api/auth/password-reset-code/", {"phone_number": phone}, format="json")
                self.assertEqual(response.status_code, 429)
                if duplicate:
                    duplicate.delete()
                if kind == "unlinked":
                    self.account = TelegramAccount.objects.create(owner=self.user, chat_id=123)

    def test_another_telegram_group_or_forged_sender_cannot_get_code(self, call):
        row = self.start()
        for kwargs in ({"chat": 999}, {"chat_type": "group"}, {"sender": 999}):
            call.reset_mock()
            self.message(row, **kwargs)
            row.refresh_from_db()
            self.assertEqual(row.code_digest, "")
            self.assertFalse(any("123456" in c.kwargs.get("text", "") for c in call.call_args_list))
        with patch("authentication.password_reset.secrets.randbelow", return_value=123456):
            self.message(row)
        self.assertEqual(self.submit(row).status_code, 200)

    def test_wrong_phone_forged_id_and_expired_code_cannot_reset(self, call):
        row = self.issue()
        for changes in ({"phone_number": "+998999999999"}, {"verification_id": str(uuid.uuid4())}):
            self.assertEqual(self.submit(row, **changes).status_code, 400)
        row.expires_at = timezone.now() - timedelta(seconds=1)
        row.save()
        self.assertEqual(self.submit(row).status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))

    def test_five_guesses_lock_code_and_start_cannot_restore_it(self, call):
        row = self.issue()
        for _ in range(5):
            self.assertEqual(self.submit(row, verification_code="111111").status_code, 400)
        row.refresh_from_db()
        self.assertEqual(row.attempts, 5)
        self.message(row)
        self.assertEqual(self.submit(row).status_code, 400)

    def test_password_confirmation_and_strength_are_checked_before_consumption(self, call):
        row = self.issue()
        self.assertEqual(self.submit(row, password_confirm="DifferentSecret").status_code, 400)
        for password in ("12345678", "short", "existing_driver"):
            result = self.submit(row, password=password, password_confirm=password)
            self.assertEqual(result.status_code, 400)
            self.assertIn("password", result.data)
        row.refresh_from_db()
        self.assertIsNone(row.consumed_at)
        self.assertEqual(row.attempts, 0)
        self.assertEqual(self.submit(row).status_code, 200)

    def test_resend_revokes_old_link_and_code_and_start_is_not_a_resend(self, call):
        row = self.issue()
        original = self.data(row)
        original_digest = row.code_digest
        with patch("authentication.password_reset.secrets.randbelow", return_value=999999):
            self.message(row)
        row.refresh_from_db()
        self.assertEqual(row.code_digest, original_digest)
        response = self.client.post("/api/auth/password-reset-code/", {"phone_number": self.phone}, format="json")
        self.assertEqual(response.status_code, 429)
        row.requested_at -= timedelta(minutes=2)
        row.save()
        new = self.start()
        self.assertNotEqual(row.verification_id, new.verification_id)
        self.assertEqual(new.code_digest, "")
        response = self.client.post("/api/auth/reset-password/", original, format="json")
        self.assertEqual(response.status_code, 400)

    def test_account_identity_or_password_change_revokes_pending_code(self, call):
        row = self.issue()
        self.account.chat_id = 999
        self.account.save()
        self.assertEqual(self.submit(row).status_code, 400)
        self.account.chat_id = 123
        self.account.save()
        self.user.phone_number = "+998999999999"
        self.user.save()
        self.assertEqual(self.submit(row).status_code, 400)
        self.user.phone_number = self.phone
        self.user.set_password("AnotherSecret731!")
        self.user.save()
        self.assertEqual(self.submit(row).status_code, 400)

    def test_registration_and_password_reset_codes_are_not_interchangeable(self, call):
        registration = new_verification(self.phone)
        registration.chat_id = 123
        registration.code_digest = code_digest(registration, "123456")
        registration.save()
        reset = self.issue()
        self.assertEqual(self.submit(reset, verification_id=str(registration.verification_id)).status_code, 400)
        response = self.client.post("/api/auth/register/", {
            "username": "new_account", "password": self.new_password, "phone_number": self.phone,
            "verification_id": str(reset.verification_id), "verification_code": "123456",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertNotEqual(code_digest(reset, "123456"), reset.code_digest)
        self.assertEqual(self.submit(reset).status_code, 200)

    def test_bot_failure_and_missing_configuration_fail_closed(self, call):
        row = self.start()
        call.side_effect = BotError("network")
        with self.assertRaises(BotError):
            self.message(row)
        row.refresh_from_db()
        self.assertEqual(row.code_digest, "")
        with patch.dict(os.environ, {"DRIVER_BOT_TOKEN": ""}):
            response = self.client.post("/api/auth/password-reset-code/", {"phone_number": "+998999999999"}, format="json")
        self.assertEqual(response.status_code, 503)


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentPasswordResetTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="parallel_reset", phone_number="+998901234567", password="OriginalSecret739!")
        TelegramAccount.objects.create(owner=self.user, chat_id=123)
        self.row = new_password_reset(self.user.phone_number)
        self.row.code_digest = reset_code_digest(self.row, "123456")
        self.row.save()

    def submit_concurrently(self, codes):
        barrier = Barrier(len(codes))

        def submit(code):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                reset_password({"phone_number": self.user.phone_number, "verification_id": self.row.verification_id,
                                "verification_code": code, "password": "ChangedSecret851!"})
                return "reset"
            except ValidationError:
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(codes)) as pool:
            return list(pool.map(submit, codes))

    def test_simultaneous_code_reuse_changes_password_once(self):
        self.assertCountEqual(self.submit_concurrently(["123456"] * 2), ["reset", "rejected"])
        self.row.refresh_from_db()
        self.assertIsNotNone(self.row.consumed_at)

    def test_parallel_failed_guesses_cannot_lose_attempts(self):
        self.assertEqual(self.submit_concurrently(["111111"] * 5), ["rejected"] * 5)
        self.row.refresh_from_db()
        self.assertEqual(self.row.attempts, 5)
        self.assertEqual(self.submit_concurrently(["123456"]), ["rejected"])
