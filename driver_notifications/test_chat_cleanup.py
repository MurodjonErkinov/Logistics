from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .delivery import deliver
from .models import Notification, TelegramAccount, Ticket, Vehicle
from .telegram import BotError, handle_update, say, ticket_state


class CleanChatTests(TestCase):
    def setUp(self):
        self.driver = get_user_model().objects.create_user(username="clean_driver", role="driver")
        self.account = TelegramAccount.objects.create(owner=self.driver, chat_id=123, ui={"message_id": 99})
        vehicle = Vehicle.objects.create(owner=self.driver, name="Tent", kind="tent", capacity_tons=20)
        self.ticket = Ticket.objects.create(owner=self.driver, vehicle=vehicle, title="Route", origins=[{"name": "Toshkent"}], destinations=[], route_mode="anywhere", ready_at=timezone.now(), expires_at=timezone.now()+timedelta(days=7), available_tons=20)

    def note(self, key, **kwargs):
        return Notification.objects.create(owner=self.driver, ticket=self.ticket, kind="ticket_created", event_key=key, deliver_after=timezone.now()-timedelta(seconds=1), **kwargs)

    def send(self, text, message_id=100):
        handle_update({"message": {"message_id": message_id, "chat": {"id": 123, "type": "private"}, "from": {"id": 123}, "text": text}})
        self.account.refresh_from_db()

    def deleted(self, mock):
        ids = []
        for item in mock.call_args_list:
            if item.args[0] == "deleteMessage":
                ids.append(item.kwargs["message_id"])
            elif item.args[0] == "deleteMessages":
                ids.extend(item.kwargs["message_ids"])
        return ids

    @patch("driver_notifications.telegram.call", return_value={"message_id": 101})
    def test_bottom_button_tap_is_deleted_and_menu_can_be_restored(self, call):
        self.send("/ticket")
        keyboard = next(c.kwargs["reply_markup"] for c in call.call_args_list if c.args[0] == "sendMessage")
        self.assertIn("keyboard", keyboard)
        self.assertIn(100, self.deleted(call))
        self.assertIn(99, self.deleted(call))
        self.send("🏠 Menyu", message_id=102)
        self.assertEqual(self.account.state, {})
        self.assertIn(102, self.deleted(call))

    @patch("driver_notifications.telegram.call", return_value={"message_id": 101})
    def test_known_notifications_are_cleaned_without_removing_site_history(self, call):
        old = self.note("old", sent_at=timezone.now(), message_id=80, message_chat_id=123)
        say(self.account, "Yangi savol")
        self.assertIn(80, self.deleted(call))
        self.assertNotIn(101, self.deleted(call))
        old.refresh_from_db()
        self.assertIsNone(old.message_id)
        self.assertIsNotNone(old.sent_at)
        self.assertTrue(Notification.objects.filter(pk=old.pk).exists())

    @patch("driver_notifications.telegram.call")
    def test_cleanup_failure_is_retried_without_losing_current_message(self, call):
        counter = 100
        fail = True

        def api(method, **kwargs):
            nonlocal counter, fail
            if method == "sendMessage":
                counter += 1
                return {"message_id": counter}
            if method == "deleteMessage" and kwargs["message_id"] == 99 and fail:
                fail = False
                raise BotError(429, 1)
            return True

        call.side_effect = api
        say(self.account, "First")
        self.account.refresh_from_db()
        self.assertEqual(self.account.ui["message_id"], 101)
        self.assertEqual(self.account.ui["cleanup_ids"], [99])
        say(self.account, "Second")
        self.account.refresh_from_db()
        self.assertEqual(self.account.ui["message_id"], 102)
        self.assertEqual(self.account.ui["cleanup_ids"], [])
        self.assertIn(101, self.deleted(call))

    @patch("driver_notifications.delivery.call", return_value={"message_id": 110})
    def test_delivery_waits_for_wizard_then_uses_bottom_keyboard(self, call):
        note = self.note("pending")
        self.account.state = ticket_state()
        self.account.save(update_fields=["state"])
        deliver()
        call.assert_not_called()
        note.refresh_from_db()
        self.assertIsNone(note.sent_at)
        self.account.state = {}
        self.account.save(update_fields=["state"])
        deliver()
        sent = next(c for c in call.call_args_list if c.args[0] == "sendMessage")
        self.assertIn("keyboard", sent.kwargs["reply_markup"])
        self.assertNotIn("inline_keyboard", sent.kwargs["reply_markup"])
        self.assertIn(99, self.deleted(call))
        note.refresh_from_db()
        self.assertIsNotNone(note.sent_at)

    @patch("driver_notifications.delivery.call")
    def test_new_notification_replaces_previous_telegram_notification(self, call):
        def api(method, **kwargs):
            if method == "sendMessage":
                return {"message_id": 110 + sum(c.args[0] == "sendMessage" for c in call.call_args_list)}
            return True

        call.side_effect = api
        first = self.note("first")
        second = self.note("second")
        deliver()
        first.refresh_from_db()
        previous = first.message_id
        deliver()
        self.assertIn(previous, self.deleted(call))
        first.refresh_from_db()
        second.refresh_from_db()
        self.account.refresh_from_db()
        self.assertIsNone(first.message_id)
        self.assertEqual(second.message_id, self.account.ui["message_id"])
        self.assertEqual(Notification.objects.filter(sent_at__isnull=False).count(), 2)

    @patch("driver_notifications.telegram.call", return_value={"message_id": 101})
    def test_notification_url_buttons_work_from_bottom_keyboard(self, call):
        say(self.account, "Yuk", reply_markup={"inline_keyboard": [[{"text": "Yukni ko‘rish", "url": "https://example.com/loads/1"}]]})
        self.send("Yukni ko‘rish")
        sent = [c for c in call.call_args_list if c.args[0] == "sendMessage"]
        self.assertEqual(sent[-1].kwargs["text"], "https://example.com/loads/1")

    @patch("driver_notifications.telegram.call", return_value={"message_id": 101})
    def test_cleanup_stays_within_the_current_owners_chat(self, call):
        other = get_user_model().objects.create_user(username="other_clean_driver", role="driver")
        TelegramAccount.objects.create(owner=other, chat_id=456, ui={"message_id": 888})
        note = self.note("not_in_this_chat", sent_at=timezone.now(), message_id=777, message_chat_id=456)
        say(self.account, "Hello")
        self.assertNotIn(777, self.deleted(call))
        self.assertNotIn(888, self.deleted(call))
        note.refresh_from_db()
        self.assertEqual(note.message_id, 777)
