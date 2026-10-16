import secrets
import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import RegistrationVerification
from .verification import CODE_LIFETIME, code_digest, normalize_phone


@transaction.atomic
def handle_registration_message(message, call, delete_message):
    """Runs inside the bot's update transaction. Never accepts a typed phone."""
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    row = None
    if text.startswith("/start reg_"):
        try:
            token = uuid.UUID(text.split("reg_", 1)[1])
        except ValueError:
            token = None
        row = RegistrationVerification.objects.select_for_update().filter(verification_id=token).first() if token else None
        if not row or row.consumed_at or row.expires_at <= timezone.now() or row.chat_id not in (None, chat_id):
            call("sendMessage", chat_id=chat_id, text="Tasdiqlash havolasi eskirgan. Saytdan yangi kod so‘rang. / Получите новую ссылку на сайте.")
            return True
        if row.code_digest:
            call("sendMessage", chat_id=chat_id, text="Kod yuqoridagi xabarda. Yangi kod kerak bo‘lsa, saytdan qayta so‘rang. / Код уже отправлен, новый можно запросить на сайте.")
            return True
        # Only the most recent started request in this chat accepts its next contact.
        RegistrationVerification.objects.filter(chat_id=chat_id, code_digest="", consumed_at__isnull=True).exclude(pk=row.pk).update(chat_id=None)
        row.chat_id = chat_id
        row.save(update_fields=["chat_id"])
        result = call("sendMessage", chat_id=chat_id,
                      text=f"YukFlow’da {row.phone_number} raqamini tasdiqlash uchun pastdagi tugmani bosing. / Подтвердите свой номер кнопкой ниже.",
                      reply_markup={"keyboard": [[{"text": "📱 Telefon raqamimni yuborish / Отправить номер", "request_contact": True}]], "resize_keyboard": True, "one_time_keyboard": True})
        previous = row.bot_message_id
        row.bot_message_id = result["message_id"]
        row.save(update_fields=["bot_message_id"])
        delete_message(chat_id, previous)
        delete_message(chat_id, message.get("message_id"))
        return True
    if "contact" not in message:
        return False
    row = RegistrationVerification.objects.select_for_update().filter(chat_id=chat_id, consumed_at__isnull=True, expires_at__gt=timezone.now()).order_by("-requested_at").first()
    if not row:
        return False
    contact = message["contact"]
    phone = None
    if contact.get("user_id") == message.get("from", {}).get("id"):
        try:
            phone = normalize_phone(contact.get("phone_number", ""))
        except ValidationError:
            pass
    if phone != row.phone_number:
        call("sendMessage", chat_id=chat_id, text="Faqat o‘zingizning Telegram raqamingizni tugma orqali yuboring. Saytdagi raqam ham shu raqam bo‘lishi kerak. / Отправьте свой номер кнопкой. Он должен совпадать с номером на сайте.")
        delete_message(chat_id, message.get("message_id"))
        return True
    if row.code_digest:
        # Repeated contacts/updates must not rotate or repeatedly disclose an OTP.
        delete_message(chat_id, message.get("message_id"))
        return True
    code = f"{secrets.randbelow(1_000_000):06d}"
    row.code_digest = code_digest(row, code)
    row.expires_at = timezone.now() + CODE_LIFETIME
    result = call("sendMessage", chat_id=chat_id,
                  text=f"YukFlow tasdiqlash kodi: {code}\n\nKod 5 daqiqa amal qiladi. Uni YukFlow saytidagi registratsiyaga kiriting. Kodni hech kimga bermang.\n\nКод подтверждения: {code}. Действует 5 минут. Не сообщайте его другим.",
                  reply_markup={"remove_keyboard": True}, protect_content=True)
    previous = row.bot_message_id
    row.bot_message_id = result["message_id"]
    row.save(update_fields=["code_digest", "expires_at", "bot_message_id"])
    delete_message(chat_id, previous)
    delete_message(chat_id, message.get("message_id"))
    return True
