from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .delivery import deliver
from .models import Notification, Preference, TelegramAccount, Ticket, Vehicle
from .telegram import BotError, handle_update, say, ticket_state


class TicketNotificationLifecycleTests(TestCase):
    def setUp(self):
        self.driver = get_user_model().objects.create_user(username="lifecycle_driver", role="driver")
        self.account = TelegramAccount.objects.create(owner=self.driver, chat_id=123, ui={"message_id": 99})
        self.vehicle = Vehicle.objects.create(owner=self.driver, name="Tent", kind="tent", capacity_tons=20)
        self.first = self.ticket("First")
        self.second = self.ticket("Second")
        self.client = APIClient()
        self.client.force_authenticate(self.driver)

    def ticket(self, title):
        return Ticket.objects.create(owner=self.driver, vehicle=self.vehicle, title=title, origins=[{"name": "Toshkent"}], destinations=[], route_mode="anywhere", ready_at=timezone.now(), expires_at=timezone.now()+timedelta(days=7), available_tons=20)

    def note(self, ticket, key, message_id=None, **kwargs):
        return Notification.objects.create(owner=self.driver, ticket=ticket, kind="match", event_key=key,
            snapshot={"origin": "Toshkent" if ticket.pk == self.first.pk else "Chirchiq", "destination": "Samarqand"},
            deliver_after=timezone.now()-timedelta(seconds=1), sent_at=timezone.now() if message_id else None,
            message_id=message_id, message_chat_id=123 if message_id else None, **kwargs)

    def deleted(self, call):
        result = []
        for item in call.call_args_list:
            if item.args[0] == "deleteMessage":
                result.append(item.kwargs["message_id"])
            elif item.args[0] == "deleteMessages":
                result.extend(item.kwargs["message_ids"])
        return result

    @patch("driver_notifications.delivery.call", return_value={"message_id": 200})
    def test_api_delete_removes_only_that_tickets_messages(self, call):
        self.note(self.first, "first", 80)
        keep = self.note(self.second, "second", 81)
        ticket_id = self.first.pk
        response = self.client.delete(f"/api/driver/tickets/{ticket_id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Notification.objects.filter(ticket_id=ticket_id).exists())
        self.account.refresh_from_db()
        self.assertEqual(self.account.ui["notification_cleanup"], {"80": [ticket_id]})
        deliver()
        self.assertIn(80, self.deleted(call))
        self.assertNotIn(81, self.deleted(call))
        keep.refresh_from_db()
        self.assertEqual(keep.message_id, 81)
        self.account.refresh_from_db()
        self.assertEqual(self.account.ui["notification_cleanup"], {})

    @patch("driver_notifications.delivery.call", return_value={"message_id": 200})
    def test_close_stops_all_queued_messages_and_cleans_sent_messages(self, call):
        old = self.note(self.first, "old", 80)
        pending = self.note(self.first, "pending")
        created = Notification.objects.create(owner=self.driver, ticket=self.first, kind="ticket_created", event_key="created", deliver_after=timezone.now())
        keep = self.note(self.second, "keep", 81)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(f"/api/driver/tickets/{self.first.pk}/", {"status": "closed"}, format="json")
        self.assertEqual(response.status_code, 200)
        deliver()
        self.assertIn(80, self.deleted(call))
        self.assertNotIn(81, self.deleted(call))
        self.assertFalse(any(c.args[0] == "sendMessage" for c in call.call_args_list))
        old.refresh_from_db()
        keep.refresh_from_db()
        pending.refresh_from_db()
        created.refresh_from_db()
        self.assertIsNone(old.message_id)
        self.assertEqual(keep.message_id, 81)
        self.assertIsNone(pending.sent_at)
        self.assertIsNone(created.sent_at)
        self.assertTrue(pending.obsolete)

    @patch("driver_notifications.delivery.call", return_value={"message_id": 201})
    @patch("driver_notifications.telegram.call", return_value={"message_id": 200})
    def test_bot_close_uses_the_same_ticket_scoped_cleanup(self, bot, worker):
        self.note(self.first, "old", 80)
        self.note(self.second, "keep", 81)
        with self.captureOnCommitCallbacks(execute=True):
            handle_update({"callback_query": {"id": "q", "from": {"id": 123}, "data": f"close:{self.first.pk}", "message": {"message_id": 80, "chat": {"id": 123, "type": "private"}}}})
        self.assertNotIn(80, self.deleted(bot))
        deliver()
        self.assertIn(80, self.deleted(worker))
        self.assertNotIn(81, self.deleted(worker))

    @patch("driver_notifications.delivery.call", return_value={"message_id": 200})
    def test_cleanup_retry_survives_notification_cascade(self, call):
        self.note(self.first, "old", 80)
        ticket_id = self.first.pk
        self.first.delete()
        call.side_effect = BotError(429, 60)
        deliver()
        self.account.refresh_from_db()
        self.assertEqual(self.account.ui["notification_cleanup"], {"80": [ticket_id]})
        self.assertFalse(Notification.objects.filter(ticket_id=ticket_id).exists())
        call.side_effect = None
        deliver()
        self.account.refresh_from_db()
        self.assertEqual(self.account.ui["notification_cleanup"], {})

    @patch("driver_notifications.delivery.call", return_value={"message_id": 200})
    def test_legacy_shared_digest_is_edited_to_keep_the_other_ticket(self, call):
        self.note(self.first, "removed", 80)
        keep = self.note(self.second, "survivor", 80)
        self.first.delete()
        deliver()
        edits = [c for c in call.call_args_list if c.args[0] == "editMessageText"]
        self.assertEqual(len(edits), 1)
        self.assertEqual(edits[0].kwargs["message_id"], 80)
        self.assertIn("Chirchiq", edits[0].kwargs["text"])
        self.assertNotIn("Toshkent", edits[0].kwargs["text"])
        self.assertNotIn(80, self.deleted(call))
        keep.refresh_from_db()
        self.assertEqual(keep.message_id, 80)

    @patch("driver_notifications.delivery.call", return_value={"message_id": 200})
    def test_pause_keeps_delivered_notifications(self, call):
        self.note(self.first, "paused", 80)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.patch(f"/api/driver/tickets/{self.first.pk}/", {"status": "paused"}, format="json")
        deliver()
        self.assertNotIn(80, self.deleted(call))
        self.account.refresh_from_db()
        self.assertFalse(self.account.ui.get("notification_cleanup"))

    @patch("driver_notifications.telegram.call", return_value={"message_id": 200})
    def test_old_ui_markers_and_queued_regular_cleanup_cannot_delete_notifications(self, call):
        self.note(self.first, "old_version", 80)
        self.account.ui = {"message_id": 80, "cleanup_ids": [80]}
        self.account.save(update_fields=["ui"])
        say(self.account, "Menyu")
        self.assertNotIn(80, self.deleted(call))
        self.account.refresh_from_db()
        self.assertEqual(self.account.ui["cleanup_ids"], [])

    @patch("driver_notifications.delivery.call", return_value={"message_id": 200})
    def test_deleting_one_ticket_does_not_interrupt_another_draft(self, call):
        self.note(self.first, "removed", 80)
        self.account.state = ticket_state()
        self.account.save(update_fields=["state"])
        self.first.delete()
        deliver()
        self.assertIn(80, self.deleted(call))
        self.assertNotIn(99, self.deleted(call))
        self.assertFalse(any(c.args[0] == "sendMessage" for c in call.call_args_list))
        self.account.refresh_from_db()
        self.assertEqual(self.account.state, ticket_state())

    @patch("driver_notifications.delivery.call", return_value={"message_id": 200})
    def test_digests_for_different_tickets_are_kept_in_separate_messages(self, call):
        Preference.objects.create(owner=self.driver, partial_interval_minutes=30)
        first = self.note(self.first, "first", level="partial")
        second = self.note(self.second, "second", level="partial")
        deliver()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertIsNotNone(first.sent_at)
        self.assertIsNone(second.sent_at)

    @patch("driver_notifications.delivery.call", return_value={"message_id": 200})
    def test_other_driver_cannot_delete_or_queue_cleanup_for_my_ticket(self, call):
        self.note(self.first, "mine", 80)
        stranger = get_user_model().objects.create_user(username="stranger", role="driver")
        self.client.force_authenticate(stranger)
        self.assertEqual(self.client.delete(f"/api/driver/tickets/{self.first.pk}/").status_code, 404)
        deliver()
        call.assert_not_called()
        self.account.refresh_from_db()
        self.assertFalse(self.account.ui.get("notification_cleanup"))

    @patch("driver_notifications.delivery.call", return_value={"message_id": 200})
    def test_worker_recovers_closed_ticket_cleanup_from_persisted_status(self, call):
        old = self.note(self.first, "closed_outside_api", 80)
        self.note(self.second, "keep", 81)
        Ticket.objects.filter(pk=self.first.pk).update(status="closed")
        deliver()
        self.assertIn(80, self.deleted(call))
        self.assertNotIn(81, self.deleted(call))
        old.refresh_from_db()
        self.assertTrue(old.obsolete)
        self.assertIsNone(old.message_id)

    @patch("driver_notifications.delivery.call", return_value={"message_id": 200})
    def test_deleting_latest_notification_restores_main_bottom_keyboard(self, call):
        self.note(self.first, "latest", 80)
        self.account.ui = {"message_id": None, "notification_message_id": 80}
        self.account.save(update_fields=["ui"])
        self.first.delete()
        deliver()
        sent = next(c for c in call.call_args_list if c.args[0] == "sendMessage")
        buttons = [b["text"] for row in sent.kwargs["reply_markup"]["keyboard"] for b in row]
        self.assertIn("🎫 Tiket ochish", buttons)
        self.account.refresh_from_db()
        self.assertEqual(self.account.ui["message_id"], 200)
        self.assertNotIn("notification_message_id", self.account.ui)
