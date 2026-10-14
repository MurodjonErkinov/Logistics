from datetime import timedelta
from unittest import skipUnless
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.utils import timezone

from cargo.models import Load
from .extraction import extract_loads, get_provider, validate_provider
from .locking import worker_lock
from .models import TelegramPost
from .schemas import MessageExtraction
from .service import ingest_message, retry_failed_messages
from .tests import extracted


class ProviderTests(SimpleTestCase):
    @patch.dict("os.environ", {"TELEGRAM_AI_PROVIDER": "openai", "OPENAI_API_KEY": "test"})
    @patch("telegram_import.providers.openai.extract_loads")
    def test_openai_parses_multiple_loads(self, parser):
        parser.return_value = MessageExtraction(loads=[extracted(), extracted(destination="Buxoro")])
        self.assertEqual(validate_provider(), "openai")
        self.assertEqual(len(extract_loads("Ikki yuk").loads), 2)
        parser.assert_called_once_with("Ikki yuk")

    @patch.dict("os.environ", {"TELEGRAM_AI_PROVIDER": "unknown"})
    def test_invalid_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            get_provider()

    @patch.dict("os.environ", {"TELEGRAM_AI_PROVIDER": "openai", "OPENAI_API_KEY": ""})
    def test_openai_requires_its_key(self):
        with self.assertRaises(ValueError):
            validate_provider()

    @patch("telegram_import.providers.openai.extract_loads", side_effect=RuntimeError("Offline"))
    def test_provider_failure_is_reported(self, parser):
        with self.assertRaisesRegex(RuntimeError, "Offline"):
            extract_loads("Yuk")


class ProviderRetryTests(TestCase):
    @patch("telegram_import.service.extract_loads")
    def test_retry_batch_handles_one_message_by_default(self, parser):
        now = timezone.now()
        for message_id in (1, 2):
            TelegramPost.objects.create(chat_id=-1001234, message_id=message_id, group_name="@loads", text="Yuk", posted_at=now, expires_at=now + timedelta(hours=24), provider="openai", status="error")
        parser.return_value = MessageExtraction(loads=[extracted()])
        self.assertEqual(retry_failed_messages(-1001234), 1)
        parser.assert_called_once()

    @patch("telegram_import.service.extract_loads")
    def test_legacy_failed_post_can_retry_without_duplicates(self, parser):
        now = timezone.now()
        post = TelegramPost.objects.create(chat_id=-1001234, message_id=1, group_name="@loads", text="Yuk Andijon → Namangan", posted_at=now, expires_at=now+timedelta(hours=24), provider="legacy", status="error", retry_at=now+timedelta(hours=1))
        parser.return_value = MessageExtraction(loads=[extracted()])
        self.assertEqual(retry_failed_messages(-1001234), 1)
        post.refresh_from_db()
        self.assertEqual(post.provider, "openai")
        self.assertEqual(post.status, "imported")
        ingest_message(post.chat_id, post.message_id, post.group_name, post.text, post.posted_at)
        self.assertEqual(Load.objects.count(), 1)
        parser.assert_called_once()


@skipUnless(connection.vendor == "postgresql", "PostgreSQL advisory locks required")
class WorkerLockTests(TransactionTestCase):
    def test_second_worker_is_refused_and_lock_releases(self):
        async def check():
            async with worker_lock(-9991234):
                with self.assertRaises(CommandError):
                    async with worker_lock(-9991234):
                        self.fail("Two workers acquired the same group lock")
            async with worker_lock(-9991234):
                pass

        async_to_sync(check)()
