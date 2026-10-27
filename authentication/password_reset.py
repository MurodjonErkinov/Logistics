import secrets
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.exceptions import Throttled, ValidationError

from driver_notifications.models import TelegramAccount
from .models import PasswordResetVerification
from .telegram_codes import send_copyable_code
from .verification import CODE_LIFETIME, INVALID_CODE, MAX_ATTEMPTS


def reset_code_digest(row, code):
    return salted_hmac("password-reset-code", f"{row.verification_id}:{code}", algorithm="sha256").hexdigest()


def password_fingerprint(user):
    return salted_hmac("password-reset-password", user.password, algorithm="sha256").hexdigest()


@transaction.atomic
def new_password_reset(phone):
    now = timezone.now()
    row, created = PasswordResetVerification.objects.get_or_create(
        phone_number=phone, defaults={"requested_at": now, "expires_at": now + timedelta(minutes=10)},
    )
    row = PasswordResetVerification.objects.select_for_update().get(pk=row.pk)
    if not created and (now - row.requested_at).total_seconds() < 60:
        raise Throttled(wait=60 - int((now - row.requested_at).total_seconds()), detail="Yangi kod uchun bir daqiqa kuting.")
    # Legacy phones are not unique. Never guess which account to reset.
    users = list(get_user_model().objects.filter(phone_number=phone, is_active=True)[:2])
    user = users[0] if len(users) == 1 else None
    account = TelegramAccount.objects.filter(owner=user).first() if user else None
    row.verification_id = uuid.uuid4()
    row.owner = user if account else None
    row.chat_id = account.chat_id if account else None
    row.password_fingerprint = password_fingerprint(user) if account else ""
    row.requested_at = now
    row.expires_at = now + timedelta(minutes=10)
    row.code_digest = ""
    row.attempts = 0
    row.consumed_at = None
    row.bot_message_id = None
    row.save()
    # Unknown/unlinked numbers receive the same public response and cooldown.
    return row


def current_reset_owner(row):
    """Recheck the original identity while holding the challenge lock."""
    user = get_user_model().objects.select_for_update().filter(
        pk=row.owner_id, phone_number=row.phone_number, is_active=True,
    ).first()
    if not user or not constant_time_compare(row.password_fingerprint, password_fingerprint(user)):
        return None
    if not TelegramAccount.objects.select_for_update().filter(owner=user, chat_id=row.chat_id).exists():
        return None
    return user


def reset_password(data):
    error = None
    with transaction.atomic():
        row = PasswordResetVerification.objects.select_for_update().filter(verification_id=data["verification_id"]).first()
        if (not row or row.phone_number != data["phone_number"] or row.consumed_at
                or row.expires_at <= timezone.now() or not row.code_digest or row.attempts >= MAX_ATTEMPTS):
            error = INVALID_CODE
        elif not constant_time_compare(row.code_digest, reset_code_digest(row, data["verification_code"])):
            row.attempts += 1
            row.save(update_fields=["attempts"])
            error = INVALID_CODE
        else:
            user = current_reset_owner(row)
            if not user:
                error = INVALID_CODE
            else:
                try:
                    password_validation.validate_password(data["password"], user)
                except DjangoValidationError as exc:
                    raise ValidationError({"password": exc.messages}) from None
                user.set_password(data["password"])
                user.save(update_fields=["password"])
                # CHECK_REVOKE_TOKEN invalidates existing access and refresh tokens.
                row.consumed_at = timezone.now()
                row.code_digest = ""
                row.save(update_fields=["consumed_at", "code_digest"])
    # Failed guesses must commit even when the API returns a validation error.
    if error:
        raise ValidationError({"verification_code": error})


@transaction.atomic
def handle_password_reset_message(message, call, delete_message):
    text = message.get("text", "").strip()
    if not text.startswith("/start reset_"):
        return False
    chat_id = message["chat"]["id"]
    try:
        token = uuid.UUID(text.split("reset_", 1)[1])
    except ValueError:
        token = None
    row = PasswordResetVerification.objects.select_for_update().filter(verification_id=token).first() if token else None
    if (not row or row.chat_id != chat_id or row.consumed_at or row.attempts >= MAX_ATTEMPTS
            or row.expires_at <= timezone.now() or not current_reset_owner(row)):
        call("sendMessage", chat_id=chat_id, text="Parolni tiklash uchun saytdan yangi havola oling va ro‘yxatdan o‘tishda ulangan Telegram akkauntingizda oching. Telegram ulanmagan bo‘lsa, saytdagi administratorga yozing. / Получите новую ссылку на сайте и откройте её в Telegram, привязанном при регистрации. Если Telegram не привязан, обратитесь к администратору сайта.")
        delete_message(chat_id, message.get("message_id"))
        return True
    if row.code_digest:
        call("sendMessage", chat_id=chat_id, text="Parolni tiklash kodi yuqoridagi xabarda. Yangi kod uchun saytda qayta so‘rang. / Код восстановления уже отправлен. Новый код можно запросить на сайте.")
        delete_message(chat_id, message.get("message_id"))
        return True
    code = f"{secrets.randbelow(1_000_000):06d}"
    result = send_copyable_code(call, delete_message, chat_id=chat_id, code=code,
                               text=f"<b>🔐 YukFlow — parolni tiklash / Восстановление пароля</b>\n\n<code>{code}</code>\n\n📋 Kodni yoki pastdagi tugmani bosib nusxalang. / Нажмите на код или кнопку ниже, чтобы скопировать.\n\nKod 5 daqiqa amal qiladi. Uni saytdagi “Parolni tiklash” bo‘limiga kiriting. Kodni hech kimga bermang. O‘zingiz so‘ramagan bo‘lsangiz, e’tiborsiz qoldiring.\n\nДействует 5 минут. Не сообщайте код другим. Если вы не запрашивали код, проигнорируйте сообщение.")
    row.code_digest = reset_code_digest(row, code)
    row.expires_at = timezone.now() + CODE_LIFETIME
    row.bot_message_id = result["message_id"]
    row.save(update_fields=["code_digest", "expires_at", "bot_message_id"])
    delete_message(chat_id, message.get("message_id"))
    return True
