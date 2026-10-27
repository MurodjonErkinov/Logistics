from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from cargo.models import Load

from .extraction import LoadExtraction, MessageExtraction
from .filtering import looks_like_load
from .models import TelegramCursor, TelegramPost
from .service import capture_message, close_deleted_messages, delete_expired_loads, ingest_message, rate_limit_delay, retry_failed_messages


def extracted(**changes):
    values = {
        "origin": "Andijon", "destination": "Namangan", "cargo_name": "Pustoy karzinka",
        "vehicle_type": "Tent fura", "weight_tons": 1.5, "is_price_negotiable": True,
        "price_amount": None, "currency": None, "contact_phone": "938086599",
        "alternate_phone": "", "pickup_date": None, "notes": None,
    }
    values.update(changes)
    return LoadExtraction(**values)


@patch.dict("os.environ", {"TELEGRAM_AI_PROVIDER": "openai", "TELEGRAM_LOAD_TTL_HOURS": "168"})
class TelegramImportTests(TestCase):
    def setUp(self):
        self.posted_at = timezone.now()

    def ingest(self, text="Yuk Andijon → Namangan", message_id=91):
        return ingest_message(-1001234, message_id, "@loads", text, self.posted_at)

    @patch("telegram_import.service.extract_loads")
    def test_capture_saves_without_ai_and_replays_once(self, extractor):
        extractor.return_value = MessageExtraction(loads=[extracted()])
        post = capture_message(-1001234, 91, "@loads", "Yuk Andijon → Namangan", self.posted_at)
        extractor.assert_not_called()
        self.assertEqual(post.status, TelegramPost.Status.PROCESSING)
        self.assertEqual(TelegramCursor.objects.get(chat_id=-1001234).last_message_id, 91)
        self.assertEqual(retry_failed_messages(-1001234), 1)
        self.assertEqual(retry_failed_messages(-1001234), 0)
        self.assertEqual(Load.objects.count(), 1)

    @patch("telegram_import.service.extract_loads")
    def test_edit_during_parsing_discards_old_result(self, extractor):
        def edit(text):
            capture_message(-1001234, 91, "@loads", "Yuk Toshkent → Buxoro", self.posted_at)
            return MessageExtraction(loads=[extracted()])
        extractor.side_effect = edit
        post = self.ingest()
        self.assertEqual(post.text, "Yuk Toshkent → Buxoro")
        self.assertEqual(Load.objects.count(), 0)
        self.assertEqual(post.status, TelegramPost.Status.PROCESSING)

    @patch("telegram_import.service.extract_loads")
    def test_delete_during_parsing_discards_result(self, extractor):
        def delete(text):
            close_deleted_messages(-1001234, [91])
            return MessageExtraction(loads=[extracted()])
        extractor.side_effect = delete
        post = self.ingest()
        self.assertEqual(post.status, TelegramPost.Status.SKIPPED)
        self.assertEqual(Load.objects.count(), 0)

    @patch("telegram_import.service.extract_loads")
    def test_import_deduplicate_and_edit(self, extractor):
        extractor.return_value = MessageExtraction(loads=[extracted()])
        post = self.ingest()
        entry = post.entries.get()
        self.assertEqual(post.status, TelegramPost.Status.IMPORTED)
        self.assertEqual(entry.load.origin, "Andijon")
        self.assertEqual(entry.load.contact_phone, "938086599")
        self.assertEqual(post.source_url, "https://t.me/loads/91")
        response = self.client.get(f"/api/cargo/loads/{entry.load_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_url"], post.source_url)
        self.assertEqual(TelegramCursor.objects.get(chat_id=-1001234).last_message_id, 91)
        self.assertEqual(self.ingest().pk, post.pk)
        self.assertEqual(extractor.call_count, 1)
        extractor.return_value = MessageExtraction(loads=[extracted(destination="Farg‘ona")])
        edited = self.ingest("Yuk Andijon → Farg‘ona").entries.get()
        self.assertEqual(edited.load_id, entry.load_id)
        self.assertEqual(edited.load.destination, "Farg‘ona")
        self.assertEqual(Load.objects.count(), 1)

    @patch("telegram_import.service.extract_loads")
    def test_multiple_loads_keep_separate_fields_and_share_source(self, extractor):
        extractor.return_value = MessageExtraction(loads=[
            extracted(),
            extracted(origin="Toshkent", destination="Buxoro", cargo_name="Sement",
                      weight_tons=20, contact_phone="901234567", price_amount=3000000,
                      currency="UZS", is_price_negotiable=False),
        ])
        post = self.ingest("1. Andijon → Namangan, karzinka\n2. Toshkent → Buxoro, sement")
        first, second = post.entries.select_related("load")
        self.assertEqual(Load.objects.count(), 2)
        self.assertEqual(str(first.load.weight_tons), "1.50")
        self.assertEqual(second.load.contact_phone, "901234567")
        self.assertEqual(second.load.cargo_name, "Sement")
        self.assertEqual(second.load.price_amount, 3000000)
        self.assertEqual(first.load.telegram_entry.post_id, second.load.telegram_entry.post_id)
        self.ingest("1. Andijon → Namangan, karzinka\n2. Toshkent → Buxoro, sement")
        self.assertEqual(extractor.call_count, 1)

    @patch("telegram_import.service.extract_loads")
    def test_valid_offer_imports_when_another_needs_review(self, extractor):
        extractor.return_value = MessageExtraction(loads=[extracted(), extracted(contact_phone=None)])
        post = self.ingest()
        self.assertEqual(post.status, TelegramPost.Status.REVIEW)
        valid, incomplete = post.entries.all()
        self.assertIsNotNone(valid.load_id)
        self.assertIsNone(incomplete.load_id)
        self.assertEqual(incomplete.payload["origin"], "Andijon")
        self.assertIn("contact_phone", incomplete.detail)
        self.assertEqual(Load.objects.count(), 1)
        post.entries.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(delete_expired_loads(), 1)

    @patch("telegram_import.service.extract_loads")
    def test_edit_removes_offer_and_closes_invalid_previous_offer(self, extractor):
        extractor.return_value = MessageExtraction(loads=[extracted(), extracted(destination="Buxoro")])
        post = self.ingest()
        first, second = post.entries.all()
        extractor.return_value = MessageExtraction(loads=[extracted(contact_phone=None)])
        post = self.ingest("Yuk: faqat bitta e’lon, telefon olib tashlandi")
        first.load.refresh_from_db()
        second.load.refresh_from_db()
        self.assertEqual(first.load.status, "closed")
        self.assertEqual(second.load.status, "closed")
        self.assertEqual(post.entries.get(position=1).status, TelegramPost.Status.SKIPPED)
        extractor.return_value = MessageExtraction(loads=[extracted()])
        self.ingest("Yuk: telefon qayta qo‘shildi 938086599")
        first.load.refresh_from_db()
        self.assertEqual(first.load.status, "open")
        self.assertEqual(Load.objects.count(), 2)

    @patch("telegram_import.service.extract_loads")
    def test_prefilter_skips_chat_without_calling_ai(self, extractor):
        post = self.ingest("Assalomu alaykum, hammaga yaxshi kun!")
        self.assertEqual(post.status, TelegramPost.Status.SKIPPED)
        self.assertIn("AI not called", post.detail)
        extractor.assert_not_called()
        self.assertEqual(Load.objects.count(), 0)

    @patch.dict("os.environ", {"TELEGRAM_PREFILTER_ENABLED": "false"})
    @patch("telegram_import.service.extract_loads")
    def test_prefilter_can_be_disabled(self, extractor):
        extractor.return_value = MessageExtraction(loads=[])
        self.ingest("Oddiy xabar")
        extractor.assert_called_once()

    @patch("telegram_import.service.extract_loads")
    def test_ai_rejects_vehicle_availability_ad(self, extractor):
        extractor.return_value = MessageExtraction(loads=[])
        post = self.ingest("Bo‘sh fura bor, yuk qidiryapman")
        self.assertEqual(post.status, TelegramPost.Status.SKIPPED)
        extractor.assert_called_once()

    def test_prefilter_accepts_uzbek_russian_and_short_routes(self):
        for text in ("YUK bor", "Юк бор", "ГРУЗ: корзинки", "Андижан — Наманган",
                     "Andijon➡Namangan", "Ташкент Москва 20 т", "Sement 10 tonna"):
            with self.subTest(text=text):
                self.assertTrue(looks_like_load(text))
        self.assertFalse(looks_like_load("Rahmat!"))

    @patch("telegram_import.service.extract_loads")
    def test_expiration_deletes_loads_and_source_deletion_closes_loads(self, extractor):
        extractor.return_value = MessageExtraction(loads=[extracted(), extracted(destination="Buxoro")])
        post = self.ingest(message_id=5)
        post.entries.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(delete_expired_loads(), 2)
        self.assertEqual(Load.objects.count(), 0)
        self.assertFalse(Load.objects.filter(status="open").exists())
        self.ingest(message_id=6)
        close_deleted_messages(-1001234, [6])
        self.assertFalse(Load.objects.filter(status="open").exists())
        self.assertEqual(TelegramPost.objects.get(message_id=6).status, TelegramPost.Status.SKIPPED)

    @patch("telegram_import.service.extract_loads")
    def test_ai_error_closes_all_loads_and_retry_reuses_them(self, extractor):
        extractor.return_value = MessageExtraction(loads=[extracted(), extracted(destination="Buxoro")])
        self.ingest()
        extractor.side_effect = RuntimeError("API unavailable")
        post = self.ingest("Yuk: e’lon tahrirlandi")
        self.assertEqual(post.status, TelegramPost.Status.ERROR)
        self.assertFalse(Load.objects.filter(status="open").exists())
        extractor.side_effect = None
        TelegramPost.objects.filter(pk=post.pk).update(retry_at=timezone.now() - timedelta(seconds=1))
        self.ingest("Yuk: e’lon tahrirlandi")
        self.assertEqual(Load.objects.filter(status="open").count(), 2)
        self.assertEqual(Load.objects.count(), 2)

    @patch("telegram_import.service.extract_loads")
    def test_expired_source_does_not_use_ai(self, extractor):
        old = timezone.now() - timedelta(days=8)
        post = ingest_message(-1001234, 7, "@loads", "Yuk", old)
        self.assertEqual(post.status, TelegramPost.Status.SKIPPED)
        extractor.assert_not_called()

    @patch("telegram_import.service.extract_loads")
    def test_retention_uses_first_import_and_edits_do_not_extend_it(self, extractor):
        extractor.return_value = MessageExtraction(loads=[extracted()])
        self.posted_at = timezone.now() - timedelta(days=2)
        post = self.ingest()
        entry = post.entries.get()
        self.assertEqual(entry.expires_at, entry.load.created_at + timedelta(days=7))
        original_expiry = entry.expires_at
        self.ingest("Yuk Andijon → Namangan yangilandi")
        entry.refresh_from_db()
        self.assertEqual(entry.expires_at, original_expiry)
        self.assertEqual(delete_expired_loads(), 0)

    @patch("telegram_import.service.extract_loads")
    def test_expired_load_is_hidden_before_cleanup_and_not_recreated(self, extractor):
        from rest_framework.test import APIClient
        extractor.return_value = MessageExtraction(loads=[extracted()])
        post = self.ingest()
        entry = post.entries.get()
        load_id = entry.load_id
        entry.expires_at = timezone.now() - timedelta(seconds=1)
        entry.save(update_fields=["expires_at"])
        client = APIClient()
        self.assertEqual(client.get("/api/cargo/loads/").data, [])
        self.assertEqual(client.get(f"/api/cargo/loads/{load_id}/").status_code, 404)
        self.assertEqual(delete_expired_loads(), 1)
        self.assertEqual(delete_expired_loads(), 0)
        self.ingest("Yuk: edited expired source")
        self.assertFalse(Load.objects.exists())

    @patch("telegram_import.service.extract_loads")
    def test_cleanup_preserves_manual_loads(self, extractor):
        extractor.return_value = MessageExtraction(loads=[extracted()])
        post = self.ingest()
        load = post.entries.get().load
        load.pk = None
        load.save()
        post.entries.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(delete_expired_loads(), 1)
        self.assertTrue(Load.objects.filter(pk=load.pk).exists())

    @patch("telegram_import.service.extract_loads")
    def test_rate_limit_saves_new_messages_and_retries_after_reset(self, extractor):
        class RateLimit(Exception):
            status_code = 429

        extractor.side_effect = RateLimit("Please try again in 28m48s.")
        failed = self.ingest()
        self.assertEqual(failed.status, TelegramPost.Status.ERROR)
        self.assertGreater(failed.retry_at, timezone.now() + timedelta(minutes=28))
        pending = self.ingest("Yuk: ikkinchi e’lon", message_id=92)
        self.assertEqual(pending.retry_at, failed.retry_at)
        self.ingest()
        self.assertEqual(extractor.call_count, 1)
        self.assertEqual(retry_failed_messages(-1001234), 0)
        extractor.side_effect = None
        extractor.return_value = MessageExtraction(loads=[extracted()])
        TelegramPost.objects.update(retry_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(retry_failed_messages(-1001234, limit=20), 2)
        self.assertEqual(Load.objects.count(), 2)
        self.assertFalse(TelegramPost.objects.filter(status=TelegramPost.Status.ERROR).exists())

    def test_rate_limit_delay_uses_header_and_message(self):
        self.assertEqual(rate_limit_delay("Please try again in 28m48s."), timedelta(seconds=1729))
        self.assertEqual(rate_limit_delay("limit", {"retry-after": "120"}), timedelta(seconds=121))
        self.assertEqual(rate_limit_delay("insufficient_quota"), timedelta(hours=1))

    @patch("telegram_import.management.commands.telegram_watch.close_old_connections")
    def test_worker_cleans_connections_even_after_failure(self, cleanup):
        from telegram_import.management.commands.telegram_watch import database_call

        def failure():
            raise RuntimeError("Disconnected")

        with self.assertRaises(RuntimeError):
            database_call(failure)
        self.assertEqual(cleanup.call_count, 2)


class TelegramMigrationTests(TransactionTestCase):
    def test_existing_load_link_is_preserved(self):
        executor = MigrationExecutor(connection)
        other_targets = [target for target in executor.loader.graph.leaf_nodes() if target[0] != "telegram_import"]
        old_target = other_targets + [("telegram_import", "0001_initial")]
        new_target = executor.loader.graph.leaf_nodes()
        executor.migrate(old_target)
        try:
            apps = executor.loader.project_state(old_target).apps
            User = apps.get_model("authentication", "User")
            OldLoad = apps.get_model("cargo", "Load")
            Post = apps.get_model("telegram_import", "TelegramPost")
            user = User.objects.create(username="legacy_importer")
            load = OldLoad.objects.create(posted_by_id=user.pk, origin="Andijon", destination="Namangan",
                                          cargo_name="Karzinka", vehicle_type="Tent", weight_tons="1.5",
                                          contact_phone="938086599")
            post = Post.objects.create(chat_id=-1001234, message_id=1, group_name="@loads", text="Yuk",
                                       posted_at=timezone.now(), expires_at=timezone.now(),
                                       status="imported", load_id=load.pk)
            executor = MigrationExecutor(connection)
            executor.migrate(new_target)
            apps = executor.loader.project_state(new_target).apps
            entry = apps.get_model("telegram_import", "TelegramLoad").objects.get(post_id=post.pk)
            self.assertEqual(entry.load_id, load.pk)
            self.assertEqual(entry.position, 0)
            self.assertEqual(entry.status, "imported")
        finally:
            MigrationExecutor(connection).migrate(new_target)
