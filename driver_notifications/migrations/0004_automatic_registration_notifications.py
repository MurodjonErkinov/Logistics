from django.db import migrations


def automatic_registration_notifications(apps, schema_editor):
    alias = schema_editor.connection.alias
    User = apps.get_model("authentication", "User")
    Verification = apps.get_model("authentication", "RegistrationVerification")
    Account = apps.get_model("driver_notifications", "TelegramAccount")
    Preference = apps.get_model("driver_notifications", "Preference")
    LinkToken = apps.get_model("driver_notifications", "LinkToken")

    # A completed phone verification is the only safe source for a missing link.
    for proof in Verification.objects.using(alias).filter(consumed_at__isnull=False, chat_id__isnull=False).iterator():
        users = list(User.objects.using(alias).filter(phone_number=proof.phone_number, is_active=True)[:2])
        if len(users) != 1:
            continue
        user = users[0]
        if Account.objects.using(alias).filter(chat_id=proof.chat_id).exclude(owner_id=user.pk).exists():
            continue
        account = Account.objects.using(alias).filter(owner_id=user.pk).first()
        if account is None:
            Account.objects.using(alias).create(owner_id=user.pk, chat_id=proof.chat_id)
        elif account.chat_id != proof.chat_id:
            account.chat_id = proof.chat_id
            account.blocked = False
            account.state = {}
            account.ui = {}
            account.save(using=alias, update_fields=["chat_id", "blocked", "state", "ui"])

    Preference.objects.using(alias).update(telegram_enabled=True)
    # Remove saved wizard indices that included the obsolete Telegram opt-in step.
    Account.objects.using(alias).filter(state__flow="preferences").update(state={})
    LinkToken.objects.using(alias).all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("driver_notifications", "0003_telegramaccount_ui"),
        ("authentication", "0004_registrationverification"),
    ]
    operations = [migrations.RunPython(automatic_registration_notifications, migrations.RunPython.noop)]
