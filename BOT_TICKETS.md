# Driver bot ticket flow

The Telegram account verified during website registration is used directly.
The bot and website use the same Ticket and Notification records.

1. Tap **🎫 Tiket ochish** and enter a title (up to 120 characters).
2. Choose an owned vehicle. Adding a new vehicle returns to the ticket automatically.
3. Send a Telegram location/venue or a Google Maps/Yandex Maps pin link.
   The city and address are resolved automatically, without asking for the city again.
   Tap **➕ Manzil qo‘shish** to add another pickup (up to 10), then **✅ Davom etish**.
4. Send one or more destination locations/links (up to 10) and tap **✅ Tiketni ochish**.
   Alternatively, **🌍 Istalgan manzil** creates the ticket immediately without a destination.

These controls are actual inline buttons beneath the current message. The main menu
uses Telegram's persistent bottom keyboard. Previous bot prompts and driver messages
are removed by the existing chat cleanup behavior.

The bot automatically sets readiness to now, expiry to 7 days, capacity to the selected
vehicle's full capacity, no minimum price, and route-based matching. It asks no questions
about price, currency, dates, radius, waypoints, notes, or matching modes. A route-based
match requires the pickup/destination and capacity; a known incompatible vehicle type
is rejected. Unknown price or pickup date does not prevent a match. These matches are
queued immediately for Telegram, respecting existing quiet hours and delivery retries.
The worker keeps scanning for newly published loads and creates site notifications.

## Location lookup

Map links are validated against the existing Google/Yandex host allowlist. Coordinates
are taken from the selected pin rather than inventing a point from a place name.
Only the coordinates are submitted to the reverse geocoder; the returned city becomes
the matching name, while the detailed address, original coordinates and map link are retained.

`GEOCODER_REVERSE_URL` selects a Photon-compatible `/reverse` endpoint. The default
is `https://photon.komoot.io/reverse`; no API key is required. Requests have a 6 second
timeout, are spaced by at least 1.1 seconds in the single polling process, and successful
lookups are cached for 30 days (Redis in production). OpenStreetMap attribution appears
on location summaries. If lookup fails or no settlement is identified, the bot keeps the
same step and asks to resend a location/link; it does not save a placeholder GPS city.

Photon documentation: https://github.com/komoot/photon/blob/master/docs/api-v1.md
The public demo permits moderate usage with no availability guarantee:
https://github.com/komoot/photon#demo-server
For higher traffic, configure your own Photon instance using `GEOCODER_REVERSE_URL`.

## Update production

```sh
cd /var/www/logistics
git pull --ff-only origin main
make prod-restart
```

No model migration is needed: locations remain in existing JSON fields. In-progress
tickets from the old wizard restart at the title step after deployment. Saved tickets
stay available. Editing a ticket through the bot applies the simple defaults and starts
a fresh 7-day search; the site's detailed editor can still change advanced options.
