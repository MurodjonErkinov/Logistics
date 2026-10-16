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
   automatically linked; drivers can receive their existing ticket notifications.

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
