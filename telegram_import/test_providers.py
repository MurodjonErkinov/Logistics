import io
import json
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
from .providers.ollama import extract_loads as extract_ollama
from .schemas import MessageExtraction
from .service import ingest_message, retry_failed_messages
from .tests import extracted


class ProviderTests(SimpleTestCase):
    @patch.dict("os.environ", {"TELEGRAM_AI_PROVIDER": "ollama", "OPENAI_API_KEY": ""})
    @patch("telegram_import.providers.openai.extract_loads")
    @patch("telegram_import.providers.ollama.extract_loads")
    def test_ollama_never_calls_openai(self, local, paid):
        local.return_value = MessageExtraction(loads=[extracted()])
        self.assertEqual(validate_provider(), "ollama")
        self.assertEqual(len(extract_loads("Yuk").loads), 1)
        local.assert_called_once_with("Yuk")
        paid.assert_not_called()

    @patch.dict("os.environ", {"TELEGRAM_AI_PROVIDER": "openai", "OPENAI_API_KEY": "test"})
    @patch("telegram_import.providers.openai.extract_loads")
    @patch("telegram_import.providers.ollama.extract_loads")
    def test_openai_never_calls_ollama(self, local, paid):
        paid.return_value = MessageExtraction(loads=[])
        self.assertEqual(validate_provider(), "openai")
        extract_loads("Yuk")
        paid.assert_called_once_with("Yuk")
        local.assert_not_called()

    @patch.dict("os.environ", {"TELEGRAM_AI_PROVIDER": "ollama"})
    @patch("telegram_import.providers.openai.extract_loads")
    @patch("telegram_import.providers.ollama.extract_loads", side_effect=RuntimeError("Offline"))
    def test_ollama_failure_does_not_fallback_to_paid_api(self, local, paid):
        with self.assertRaises(RuntimeError):
            extract_loads("Yuk")
        paid.assert_not_called()

    @patch.dict("os.environ", {"TELEGRAM_AI_PROVIDER": "unknown"})
    def test_invalid_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            get_provider()

    @patch.dict("os.environ", {"TELEGRAM_AI_PROVIDER": "openai", "OPENAI_API_KEY": ""})
    def test_openai_requires_its_key(self):
        with self.assertRaises(ValueError):
            validate_provider()

    @patch("telegram_import.providers.ollama.urlopen")
    def test_ollama_uses_json_schema_and_reads_multiple_loads(self, request):
        result = MessageExtraction(loads=[extracted(), extracted(destination="Buxoro")])
        request.return_value = io.BytesIO(json.dumps({"done": True, "message": {"content": result.model_dump_json()}}).encode())
        parsed = extract_ollama("Ikki yuk")
        self.assertEqual(len(parsed.loads), 2)
        body = json.loads(request.call_args.args[0].data)
        self.assertTrue(body["stream"])
        self.assertFalse(body["think"])
        self.assertEqual(body["options"]["num_batch"], 128)
        self.assertEqual(body["format"], MessageExtraction.model_json_schema())
        self.assertEqual(body["messages"][1]["content"], "Ikki yuk")

    @patch("telegram_import.providers.ollama.urlopen")
    def test_stream_accumulates_fragments_until_complete(self, request):
        payload = MessageExtraction(loads=[extracted(), extracted(destination="Buxoro")]).model_dump_json()
        chunks = [{"done": False, "message": {"content": part}} for part in (payload[:100], payload[100:])]
        chunks.append({"done": True, "done_reason": "stop", "message": {"content": ""}})
        request.return_value = io.BytesIO("\n".join(json.dumps(chunk) for chunk in chunks).encode())
        self.assertEqual(len(extract_ollama("Ikki yuk").loads), 2)

    @patch("telegram_import.providers.ollama.urlopen")
    def test_stream_disconnect_does_not_publish_partial_response(self, request):
        payload = MessageExtraction(loads=[extracted()]).model_dump_json()
        request.return_value = io.BytesIO(json.dumps({"done": False, "message": {"content": payload}}).encode())
        with self.assertRaises(RuntimeError):
            extract_ollama("Yuk")

    @patch("telegram_import.providers.ollama.time.monotonic")
    @patch("telegram_import.providers.ollama.urlopen")
    def test_total_deadline_rejects_even_a_complete_response(self, request, clock):
        payload = MessageExtraction(loads=[extracted()]).model_dump_json()
        request.return_value = io.BytesIO(json.dumps({"done": True, "message": {"content": payload}}).encode())
        clock.side_effect = [0, 0, 61]
        with self.assertRaisesRegex(RuntimeError, "time limit"):
            extract_ollama("Yuk")

    @patch("telegram_import.providers.ollama.urlopen")
    def test_ollama_rejects_incomplete_or_invalid_results(self, request):
        for result in ({"done": False}, {"done": True, "done_reason": "length"},
                       {"done": True, "message": {"content": "not json"}}):
            with self.subTest(result=result):
                request.return_value = io.BytesIO(json.dumps(result).encode())
                with self.assertRaises(RuntimeError):
                    extract_ollama("Yuk")


class ProviderSwitchTests(TestCase):
    @patch.dict("os.environ", {"TELEGRAM_AI_PROVIDER": "ollama"})
    @patch("telegram_import.service.extract_loads")
    def test_ollama_timeout_does_not_pause_other_messages(self, extractor):
        now = timezone.now()
        extractor.side_effect = RuntimeError("Ollama timed out")
        failed = ingest_message(-1001234, 10, "@loads", "Yuk: birinchi", now)
        extractor.side_effect = None
        extractor.return_value = MessageExtraction(loads=[extracted()])
        imported = ingest_message(-1001234, 11, "@loads", "Yuk: ikkinchi", now)
        self.assertEqual(imported.status, "imported")
        ingest_message(failed.chat_id, failed.message_id, failed.group_name, failed.text, failed.posted_at)
        self.assertEqual(extractor.call_count, 2)

    @patch.dict("os.environ", {"TELEGRAM_AI_PROVIDER": "ollama"})
    @patch("telegram_import.service.extract_loads")
    def test_retry_batch_handles_one_message_by_default(self, extractor):
        now = timezone.now()
        for message_id in (1, 2):
            TelegramPost.objects.create(chat_id=-1001234, message_id=message_id, group_name="@loads",
                text="Yuk", posted_at=now, expires_at=now + timedelta(hours=24), provider="ollama", status="error")
        extractor.return_value = MessageExtraction(loads=[extracted()])
        self.assertEqual(retry_failed_messages(-1001234), 1)
        extractor.assert_called_once()

    @patch("telegram_import.service.extract_loads")
    def test_switch_bypasses_other_provider_cooldown_without_duplicates(self, extractor):
        now = timezone.now()
        post = TelegramPost.objects.create(
            chat_id=-1001234, message_id=1, group_name="@loads", text="Yuk Andijon → Namangan",
            posted_at=now, expires_at=now + timedelta(hours=24), provider="openai",
            status="error", retry_at=now + timedelta(hours=1), detail="OpenAI limit",
        )
        extractor.return_value = MessageExtraction(loads=[extracted()])
        with patch.dict("os.environ", {"TELEGRAM_AI_PROVIDER": "ollama"}):
            self.assertEqual(retry_failed_messages(-1001234), 1)
        post.refresh_from_db()
        self.assertEqual(post.provider, "ollama")
        self.assertIsNone(post.retry_at)
        self.assertEqual(post.status, "imported")
        with patch.dict("os.environ", {"TELEGRAM_AI_PROVIDER": "openai"}):
            ingest_message(post.chat_id, post.message_id, post.group_name, post.text, post.posted_at)
        self.assertEqual(Load.objects.count(), 1)
        self.assertEqual(extractor.call_count, 1)


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
