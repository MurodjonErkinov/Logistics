# YukFlow frontend

Next.js App Router, React, TypeScript, Tailwind CSS, Manrope va Lucide. Interfeys o‘zbekcha va ruscha; barcha e’lonlar mavjud Django API’dan olinadi. Test namunalari faqat Playwright sinovida ishlatiladi.

## Local ishga tushirish

Backend `http://127.0.0.1:8018` da ishlayotgan bo‘lishi kerak.

```bash
cd frontend
npm ci
npm run dev
```

Sayt: http://localhost:3018

Root papkadan: `make frontend-dev`.

Backend boshqa manzilda bo‘lsa `.env.example` dan `.env.local` yarating va `BACKEND_URL` ni o‘zgartiring. Bu server sozlamasi, brauzerga chiqarilmaydi.

## Docker

```bash
make frontend-up
make frontend-logs
make frontend-stop
```

`frontend-up` frontendni build qiladi, Django va PostgreSQL bilan ishga tushiradi. Telegram importer providerini o‘zgartirmaydi. Frontend porti `.env` dagi `FRONTEND_PORT` (default 3018), backend 8018, PostgreSQL 5438.

Bir vaqtda local frontend va Docker frontendni bir xil portda ishlatmang. `make down` barcha konteynerlarni to‘xtatadi; keyin frontendni `make frontend-up` bilan ishga tushiring.

## Sahifalar

- `/`: aktual yuklar, yo‘nalish/transport/og‘irlik/qidiruv filtrlari, saralash va sahifalash.
- `/loads/:id`: yuk tafsilotlari; login’dan keyin aloqa raqamlari.
- `/saved`: shu brauzerda, akkaunt bo‘yicha alohida saqlangan e’lonlar.
- `/login`, `/register`: JWT asosidagi kirish va ro‘yxatdan o‘tish.
- `/loads/new`, `/loads/:id/edit`: shaxsiy yoki ruxsat berilgan kompaniya nomidan yuk yaratish/tahrirlash.
- `/my-loads`: o‘z e’lonlari va egasi bo‘lgan kompaniya e’lonlari; yopish, qayta ochish, o‘chirish.
- `/companies`: kompaniya yaratish, ma’lumotlarini tahrirlash, a’zolarni qo‘shish/chiqarish va yuk joylash ruxsati.
- `/profile`: profil va parolni yangilash.
- `/admin`: `is_staff` huquqli administrator uchun foydalanuvchilar va rollarni o‘zgartirish.

`user`, `driver`, `dispatcher` yuk qidirishi va shaxsiy yuk joylashi mumkin. Kompaniya nomidan joylash membership ruxsati bilan tekshiriladi. Rol nomi `admin` bo‘lishi o‘zi administrator huquqini bermaydi: backend `is_staff` ni tekshiradi.

## Auth va API

Brauzer `/api/...` Next.js serveriga murojaat qiladi. Server Django’ga so‘rov yuboradi. Access va refresh tokenlar HttpOnly, SameSite=Lax cookie’da, HTTPS’da Secure bilan saqlanadi. Tokenlar localStorage’da yoki login javobida yo‘q. Access eskirganda refresh avtomatik ishlaydi. O‘zgartiruvchi so‘rovlar uchun bir xil hostdan Origin talab qilinadi. Public cargo API javobida telefon maydonlari va display_text bo‘sh; login’dan keyin to‘liq.

Boshlang‘ich versiyada yuk filtrlari va sahifalash brauzerda bajariladi, API ro‘yxatni to‘liq qaytaradi. Katta hajm uchun server pagination keyingi bosqich. Saqlangan e’lonlar qurilmalar orasida sinxronlanmaydi. UZ/RU tanlovi cookie’da saqlanadi; yuklarning asl matni tarjima qilinmaydi.

## Tekshirish

```bash
npm run typecheck
npm run build
npm run test:e2e
```

E2E uchun local frontend, Docker backend va Google Chrome o‘rnatilgan bo‘lsin. Birinchi test API’ni mock qilib desktop/mobile, filtr va saqlashni tekshiradi. Ikkinchisi backend bilan vaqtinchalik akkaunt va kompaniya yaratib, auth refresh va yuk CRUD’ini tekshiradi. Test oxirida faqat o‘zi yaratgan akkauntlar, kompaniyalar va ularga tegishli sinov ma’lumotlarini Docker orqali tozalaydi.

Security: qarang ../SECURITY_REVIEW.md. Parol almashtirish current_password ni talab qiladi; muvaffaqiyatdan so‘ng qayta login kerak. CSP nonce sababli sahifalar request vaqtida render qilinadi.


## Role workspaces

`/driver` provides the driver workspace; `/dashboard` provides a sender/dispatcher workspace. Login redirects according to the server-returned role (staff go to `/admin`), while an explicit safe `next` is preserved. Both pages require a session and choose their data by the current role. Driver navigation highlights the workspace, marketplace and saved loads; other roles retain load and company management.

The workspace uses the existing cargo API, route/vehicle/maximum-weight filters, local saved loads, selectable route cards, phone links and a visible-tab 60-second refresh. Own-load dashboards use `mine=1`, enforced by Django. Saved loads do not reserve a shipment; there is no application/assignment API yet.

Routes are rendered in a Yandex Maps iframe using announcement place names. Only `https://yandex.com` is allowed by `frame-src`; tokens are not passed to the provider. Place names are shared with the map provider. The external map link remains available if the widget cannot load. Routing may resolve ambiguous names incorrectly and is not truck-specific; loading addresses and road suitability must be confirmed with the sender. See [Yandex widget documentation](https://yandex.com/support/maps/en/concept/get-map-reference).


Driver ticket and notification flows: `/driver/tickets`, `/notifications`. See `../DRIVER_NOTIFICATIONS.md` for bot configuration, matching semantics, coordinate limitations, quiet hours and delivery behavior. New APIs and Postman bodies are listed in `../api.txt`.
