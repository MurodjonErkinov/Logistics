import re
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.exceptions import Throttled, ValidationError

from .models import RegistrationVerification

CODE_LIFETIME = timedelta(minutes=5)
MAX_ATTEMPTS = 5
INVALID_CODE = "Kod noto‘g‘ri yoki muddati tugagan. Telegramdan yangi kod oling."


def normalize_phone(value):
    value = re.sub(r"[\s()\-]", "", value)
    if not value.startswith("+"):
        value = "+" + value
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", value):
        raise ValidationError("Raqamni xalqaro formatda kiriting: +998901234567.")
    return value


def code_digest(row, code):
    return salted_hmac("registration-code", f"{row.verification_id}:{code}", algorithm="sha256").hexdigest()


@transaction.atomic
def new_verification(phone):
    now = timezone.now()
    row, created = RegistrationVerification.objects.get_or_create(
        phone_number=phone, defaults={"requested_at": now, "expires_at": now + timedelta(minutes=10)},
    )
    row = RegistrationVerification.objects.select_for_update().get(pk=row.pk)
    if not created and (now - row.requested_at).total_seconds() < 60:
        raise Throttled(wait=60 - int((now - row.requested_at).total_seconds()), detail="Yangi kod uchun bir daqiqa kuting.")
    row.verification_id = uuid.uuid4()
    row.requested_at = now
    row.expires_at = now + timedelta(minutes=10)
    row.chat_id = None
    row.code_digest = ""
    row.attempts = 0
    row.consumed_at = None
    row.bot_message_id = None
    row.save()
    return row


def register_verified_user(data):
    verification_id = data.pop("verification_id")
    code = data.pop("verification_code")
    error = None
    user = None
    try:
        with transaction.atomic():
            row = RegistrationVerification.objects.select_for_update().filter(verification_id=verification_id).first()
            if (not row or row.phone_number != data["phone_number"] or row.consumed_at
                    or row.expires_at <= timezone.now() or not row.code_digest or row.attempts >= MAX_ATTEMPTS):
                error = INVALID_CODE
            elif not constant_time_compare(row.code_digest, code_digest(row, code)):
                row.attempts += 1
                row.save(update_fields=["attempts"])
                error = INVALID_CODE
            else:
                from driver_notifications.models import Preference, TelegramAccount
                User = get_user_model()
                if User.objects.filter(phone_number=row.phone_number).exists():
                    error = "Bu telefon raqami allaqachon ro‘yxatdan o‘tgan. Akkauntingizga kiring."
                elif TelegramAccount.objects.filter(chat_id=row.chat_id).exists():
                    error = "Bu Telegram akkaunti allaqachon ulangan. Avvalgi akkauntingizga kiring."
                else:
                    user = User.objects.create_user(**data)
                    TelegramAccount.objects.create(owner=user, chat_id=row.chat_id, ui={"message_id": row.bot_message_id, "actions": {}})
                    Preference.objects.create(owner=user)
                    row.consumed_at = timezone.now()
                    row.code_digest = ""
                    row.save(update_fields=["consumed_at", "code_digest"])
    except IntegrityError:
        raise ValidationError({"detail": "Akkaunt allaqachon mavjud. Ma’lumotlarni tekshiring yoki akkauntingizga kiring."}) from None
    # Raise after committing failed attempts, so guesses cannot roll back the counter.
    if error:
        raise ValidationError({"verification_code": error})
    return user
