import logging
import secrets
import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import RegistrationVerification
from .telegram_codes import send_copyable_code
from .verification import CODE_LIFETIME, code_digest, normalize_phone

logger = logging.getLogger(__name__)


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
        if not row:
            logger.warning("Registration Start: request_not_found. Check that this bot and the website use the same database and only one bot instance polls Telegram.")
            call("sendMessage", chat_id=chat_id, text="Bu tasdiqlash havolasi bot bazasida topilmadi. Saytdagi oxirgi “Telegramga o‘tish” tugmasini bosing. Yangi havolada ham takrorlansa, administratorga xabar bering. / Запрос не найден. Откройте последнюю ссылку с сайта. Если ошибка повторяется, обратитесь к администратору.")
            return True
        if row.consumed_at:
            call("sendMessage", chat_id=chat_id, text="Bu raqam allaqachon tasdiqlangan. Saytda akkauntingizga kiring. / Номер уже подтверждён. Войдите в аккаунт на сайте.")
            return True
        if row.expires_at <= timezone.now():
            call("sendMessage", chat_id=chat_id, text="Tasdiqlash havolasining muddati tugagan. Saytdan yangi kod oling. / Срок ссылки истёк. Запросите новый код на сайте.")
            return True
        if row.chat_id not in (None, chat_id):
            call("sendMessage", chat_id=chat_id, text="Bu havola boshqa Telegram akkauntida ochilgan. Saytdan yangi kod oling va o‘z akkauntingizda oching. / Ссылка открыта другим Telegram-аккаунтом. Получите новую ссылку на сайте.")
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
    result = send_copyable_code(call, delete_message, chat_id=chat_id, code=code, remove_keyboard=True,
                               text=f"<b>YukFlow tasdiqlash kodi / Код подтверждения</b>\n\n<code>{code}</code>\n\n📋 Kodni yoki pastdagi tugmani bosib nusxalang. / Нажмите на код или кнопку ниже, чтобы скопировать.\n\nKod 5 daqiqa amal qiladi. Uni YukFlow saytidagi registratsiyaga kiriting. Kodni hech kimga bermang.\n\nДействует 5 минут. Введите код при регистрации на сайте YukFlow. Не сообщайте его другим.")
    previous = row.bot_message_id
    row.bot_message_id = result["message_id"]
    row.save(update_fields=["code_digest", "expires_at", "bot_message_id"])
    delete_message(chat_id, previous)
    delete_message(chat_id, message.get("message_id"))
    return True
