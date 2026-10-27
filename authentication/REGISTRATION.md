# Telegram registration verification

All new public registrations (driver and dispatcher) require a phone number and a
one-time Telegram code. Existing accounts can still log in normally. Admin user
creation is unchanged.

Use the existing bot with `DRIVER_BOT_TOKEN` and `DRIVER_BOT_USERNAME` set in the
backend and bot environment. `DRIVER_BOT_USERNAME` is the bot's username, without
`t.me/`. Both processes must use the same database and `DJANGO_SECRET_KEY`.
`make restart` runs migration `authentication.0004_registrationverification`,
rebuilds the frontend/backend and starts the `driver_bot` service.

1. Enter the Telegram phone number on `/register` and request a code. The click
   opens Telegram automatically in a new tab, preserving the registration form.
2. Press Start and share your own number with the contact button. Typed numbers and contacts belonging to other users are rejected.
3. Enter the six-digit code and complete registration. The Telegram account is
   automatically linked and Telegram notifications are enabled. Drivers receive
   ticket notifications in that same verified Telegram chat without a separate
   link or opt-in. Quiet hours, partial-match intervals and language remain configurable.

`POST /api/auth/registration-code/` accepts `phone_number` and returns
`verification_id`, `bot_url` and `retry_after`. A pending link lasts ten minutes.
The issued code lasts five minutes, has five allowed guesses and can be used once.
A new request is allowed after 60 seconds and invalidates the previous link/code.
Phone and address throttles apply. Only a keyed digest is stored in the database;
the API never returns the code. Completion is locked and committed together with
user creation, so concurrent submissions cannot reuse a code. Registration fails
closed if the bot is not configured.

`POST /api/auth/register/` now also requires `verification_id` and
`verification_code`, and the phone must match the verified contact. Duplicate
registered phone numbers and Telegram accounts are rejected after code verification.

Backend regression tests: `python manage.py test authentication.test_registration
 driver_notifications.test_inline` (on one line). Browser tests:
`cd frontend && npm run test:e2e -- tests/landing.spec.ts`.
These tests mock Telegram delivery; a final live check needs a real person pressing
Start and sharing their contact in the configured bot.

## Start link reported as invalid or expired

Run only one polling instance per bot token. A local bot and a server bot with the
same token compete for updates (`Telegram error 409`), and a Start update may reach
the database that did not create its registration request. Use a separate test bot
for local development, or stop the local `driver_bot` when testing the live site.
Pausing Docker is temporary; starting the whole local stack again starts that bot.

A missing request is now reported separately from an expired, consumed, or
other-account link. `request_not_found` in the bot logs means the request is absent
from that bot's database (for example, a superseded link or a different environment).
After resolving duplicate polling, request a new code on the live site and use
that latest Telegram link. If it still fails, compare web/bot database configuration
and inspect `driver_bot` logs. Do not post bot tokens, database passwords or full
verification URLs in diagnostic output.


## Automatic notification destinations

The ticket page has no manual Telegram link, unlink or enable control. The old
`driver/telegram-link/` API and its bot link tokens are disabled. The registration
chat is the notification destination; phone numbers are never used to guess a chat.
Opening the bot after unblocking it clears the saved blocked status automatically.

Migration `driver_notifications.0004_automatic_registration_notifications` enables
notifications for existing preferences and restores missing or changed links only
from completed registration proofs with an unambiguous matching phone. It never
takes a chat already owned by another account. Existing quiet hours and partial-match
intervals are preserved. Legacy accounts without a confirmed Telegram identity
cannot be linked automatically and need administrator assistance.

## Forgotten passwords

Login and registration link to `/forgot-password`. Enter the registered phone,
open Telegram and press Start; the bot immediately issues a six-digit reset code
to the **previously linked private Telegram chat**. No new contact-sharing step is
needed. Enter the code and the new password twice on the website, then sign in.
This creates no new user and preserves tickets, cargo and the notification chat.

`POST /api/auth/password-reset-code/` accepts `phone_number`. Every valid phone
gets the same response shape (`verification_id`, `bot_url`, `retry_after`), even
if no matching account can recover. The `reset_` deep link works only in the
existing linked Telegram account. Unknown, inactive, unlinked and ambiguous
legacy phone numbers cannot issue a reset code; the page links to the administrator.
Never bind a new chat or reset a legacy account using an unverified phone alone.

`POST /api/auth/reset-password/` accepts `phone_number`, `verification_id`,
`verification_code`, `password` and `password_confirm`. Reset codes are stored
as purpose-specific HMACs in a separate model and cannot serve as registration
codes. Codes last five minutes, allow five guesses and are consumed atomically.
A new request rotates the ID after a 60-second cooldown; phone and address limits
also apply. Changes to the account phone, linked chat or password invalidate the
pending challenge. Django password validators run against the existing user.
Existing access and refresh tokens fail after reset through `CHECK_REVOKE_TOKEN`.
The frontend clears its cookies and returns the user to login.

Deploy the web and bot together, applying migration
`authentication.0005_passwordresetverification` before the new endpoints are used
(`make restart` applies migrations on web startup). Run
`python manage.py test authentication.test_password_reset authentication.test_registration`
and `cd frontend && npm run test:e2e -- tests/password-reset.spec.ts tests/landing.spec.ts`.
Telegram delivery is mocked in these tests.

Registration and password-reset codes use HTML `<code>` formatting and a native
Telegram `copy_text` button that copies only the six digits. OTP messages are
copyable (no `protect_content` restriction). Registration removes the contact
keyboard with a silent temporary message, deletes it, then sends the code with
the inline copy button.
