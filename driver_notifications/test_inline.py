from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Preference, TelegramAccount, Vehicle
from .telegram import TICKET_STEPS, VEHICLE_STEPS, handle_update, prompt


@patch("driver_notifications.telegram.call", return_value={"message_id": 1})
class InlineBotTests(TestCase):
    def setUp(self):
        self.driver = get_user_model().objects.create_user(username="inline_driver", role="driver")
        self.account = TelegramAccount.objects.create(owner=self.driver, chat_id=123)

    def message(self, text):
        handle_update({"message": {"chat": {"id": 123, "type": "private"}, "from": {"id": 123}, "text": text}})
        self.account.refresh_from_db()

    def tap(self, payload):
        handle_update({"callback_query": {"id": "query1", "from": {"id": 123}, "data": payload, "message": {"chat": {"id": 123, "type": "private"}, "message_id": 1}}})
        self.account.refresh_from_db()

    def sent(self, call):
        return next(item for item in reversed(call.call_args_list) if item.args[0] == "sendMessage")

    def payload(self, call, suffix):
        self.account.refresh_from_db()
        for payload in self.account.ui.get("actions", {}).values():
            if payload.endswith(suffix):
                return payload
        self.fail(f"Button {suffix} missing")

    def test_menu_opens_forms_without_commands(self, call):
        self.message("/start")
        self.message("🚛 Mashinalarim")
        self.assertIn("Hali mashina", self.sent(call).kwargs["text"])
        self.message("➕ Mashina qo‘shish")
        self.assertEqual(self.account.state["flow"], "vehicle")
        self.message("/start")
        self.assertEqual(self.sent(call).args[0], "sendMessage")
        self.assertIn("keyboard", self.sent(call).kwargs["reply_markup"])
        self.tap("nav:vehicle")
        self.assertEqual(self.account.state["flow"], "vehicle")
        self.assertIn("keyboard", self.sent(call).kwargs["reply_markup"])
        self.tap(self.payload(call, ":/cancel"))
        self.assertEqual(self.account.state, {})
        self.tap("nav:settings")
        self.assertEqual(self.account.state["flow"], "preferences")

    def test_inline_vehicle_wizard_and_stale_button(self, call):
        self.tap("nav:vehicle")
        self.message("Isuzu")
        payload = self.payload(call, ":refrigerator")
        self.tap(payload)
        self.assertEqual(self.account.state["data"]["kind"], "refrigerator")
        index = self.account.state["index"]
        self.tap(payload)
        self.assertEqual(self.account.state["index"], index)
        self.assertIn("eski", self.sent(call).kwargs["text"])
        self.message("8")
        self.tap(self.payload(call, ":-"))
        self.tap(self.payload(call, ":-"))
        self.tap(self.payload(call, ":ha"))
        self.assertEqual(self.account.state, {})
        self.assertEqual(Vehicle.objects.get().kind, "refrigerator")

    def test_vehicle_choice_and_invalid_callback_do_not_cross_steps(self, call):
        vehicle = Vehicle.objects.create(owner=self.driver, name="Volvo", kind="tent", capacity_tons=20)
        self.account.state = {"flow": "ticket", "index": TICKET_STEPS.index("vehicle"), "data": {}}
        self.account.save()
        prompt(self.account)
        self.account.refresh_from_db()
        self.tap(f"u:{self.account.state['ui_nonce']}:ha")
        self.assertNotIn("vehicle", self.account.state["data"])
        self.tap(self.payload(call, f":{vehicle.pk}"))
        self.assertEqual(self.account.state["data"]["vehicle"], vehicle.pk)

    def test_location_help_keeps_step_and_back_cancel_available(self, call):
        self.account.state = {"flow": "ticket", "index": TICKET_STEPS.index("current_location"), "data": {}}
        self.account.save()
        prompt(self.account)
        self.account.refresh_from_db()
        self.tap(self.payload(call, ":location"))
        self.assertIn("Skrepka", self.sent(call).kwargs["text"])
        self.assertEqual(self.account.state["index"], TICKET_STEPS.index("current_location"))
        self.assertIn("keyboard", self.sent(call).kwargs["reply_markup"])
        self.tap(self.payload(call, ":/back"))
        self.assertEqual(self.account.state["index"], TICKET_STEPS.index("vehicle"))
        self.tap(self.payload(call, ":/cancel"))
        self.assertEqual(self.account.state, {})

    def test_all_steps_and_pending_place_have_inline_controls(self, call):
        Vehicle.objects.create(owner=self.driver, name="Tent", kind="tent", capacity_tons=20)
        for flow, steps in (("ticket", TICKET_STEPS), ("vehicle", VEHICLE_STEPS)):
            for i, key in enumerate(steps):
                with self.subTest(flow=flow, step=key):
                    self.account.state = {"flow": flow, "index": i, "data": {"origins": [{"name": "Toshkent"}], "destinations": [{"name": "Samarqand"}]}}
                    self.account.save()
                    prompt(self.account)
                    markup = self.sent(call).kwargs["reply_markup"]
                    self.assertIn("keyboard", markup)
                    self.assertNotIn("inline_keyboard", markup)
                    buttons = [b for row in markup["keyboard"] for b in row]
                    self.assertTrue(any(b["text"] == "🏠 Menyu" for b in buttons))
                    self.assertTrue(markup["resize_keyboard"])
                    self.assertTrue(markup["is_persistent"])

    def test_russian_choices_are_inline(self, call):
        Preference.objects.create(owner=self.driver, language="ru")
        self.tap("nav:settings")
        self.tap(self.payload(call, ":ru"))
        self.assertIn("keyboard", self.sent(call).kwargs["reply_markup"])
        buttons = [b["text"] for row in self.sent(call).kwargs["reply_markup"]["keyboard"] for b in row]
        self.assertIn("30", buttons)
        self.assertIn("🏠 Меню", buttons)

    def test_start_restores_delivery_without_reconnecting(self, call):
        self.account.blocked = True
        self.account.save(update_fields=["blocked"])
        self.message("/start")
        self.assertFalse(self.account.blocked)
        self.assertEqual(self.account.chat_id, 123)

    def test_old_bot_and_user_messages_are_deleted(self, call):
        self.account.ui = {"message_id": 99}
        self.account.save(update_fields=["ui"])
        handle_update({"message": {"message_id": 100, "chat": {"id": 123, "type": "private"},
                                   "from": {"id": 123}, "text": "/start"}})
        deleted = [item.kwargs["message_id"] for item in call.call_args_list if item.args[0] == "deleteMessage"]
        self.assertIn(99, deleted)
        self.assertIn(100, deleted)
