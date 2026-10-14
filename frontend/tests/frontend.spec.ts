import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";

const accounts: string[] = [];
test.afterAll(() => {
  if (!accounts.length) return;
  const names = JSON.stringify(accounts);
  execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "web",
      "python",
      "manage.py",
      "shell",
      "-c",
      `from django.contrib.auth import get_user_model; from partners.models import Company; Company.objects.filter(created_by__username__in=${names}).delete(); get_user_model().objects.filter(username__in=${names}).delete()`,
    ],
    { cwd: "..", stdio: "pipe" },
  );
});

const load = {
  id: 987654,
  origin: "Toshkent",
  destination: "Samarqand",
  cargo_name: "Qurilish materiallari",
  vehicle_type: "Tent fura",
  weight_tons: "20.00",
  is_price_negotiable: true,
  price_amount: null,
  currency: "UZS",
  contact_phone: "",
  alternate_phone: "",
  pickup_date: null,
  notes: "",
  status: "open",
  posted_by: 1,
  posted_by_username: "yuk_egasi",
  company: null,
  source_url: null,
  created_at: "2026-10-06T05:00:00Z",
  updated_at: "2026-10-06T05:00:00Z",
};

test("marketplace filters, saves and fits desktop and mobile", async ({
  page,
}) => {
  await page.route("**/api/auth/me/", (route) =>
    route.fulfill({ status: 401, json: { detail: "Not authenticated" } }),
  );
  await page.route("**/api/cargo/loads/**", (route) =>
    route.fulfill({
      json: [
        load,
        {
          ...load,
          id: 987655,
          origin: "Andijon",
          destination: "Namangan",
          cargo_name: "Pustoy karzinka",
          weight_tons: "1.5",
        },
        {
          ...load,
          id: 987656,
          origin: "Buxoro",
          destination: "Toshkent",
          cargo_name: "Meva va sabzavotlar",
          vehicle_type: "Refrigerator",
          weight_tons: "12",
          price_amount: "3500000",
          is_price_negotiable: false,
        },
      ],
    }),
  );
  await page.setViewportSize({ width: 1440, height: 1080 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Yuk toping. Yo‘lga chiqing." }),
  ).toBeVisible();
  await expect(page.locator(".load-card")).toHaveCount(3);
  await page.screenshot({
    path: "test-results/marketplace-desktop.png",
    fullPage: true,
  });
  await page.getByLabel("Qayerdan", { exact: true }).fill("Andijon");
  await page.getByRole("button", { name: "Yuk qidirish", exact: true }).click();
  await expect(page.locator(".load-card")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Yukni saqlash", exact: true })
    .click();
  await page.goto("/saved");
  await expect(page.locator(".load-card")).toHaveCount(1);
  await page.goto("/");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".load-card")).toHaveCount(3);
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: "test-results/marketplace-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Menyuni ochish" }).click();
  await expect(
    page.getByRole("navigation", { name: "Asosiy menyu" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Mening yuklarim", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Kabinetga xush kelibsiz" }),
  ).toBeVisible();
});

test("live register, company identity, cargo create edit close and delete", async ({
  page,
  context,
}) => {
  const username = `yf_e2e_${Date.now()}`;
  accounts.push(username);
  await page.goto("/register");
  await page.getByLabel("Ism", { exact: true }).fill("Frontend");
  await page.getByLabel("Foydalanuvchi nomi", { exact: true }).fill(username);
  await page.getByLabel("Telefon raqam", { exact: true }).fill("+998901234567");
  await page.getByLabel("Parol", { exact: true }).fill("RoadFlow!Strong2026");
  await page
    .getByRole("button", { name: "Akkaunt yaratish", exact: true })
    .click();
  await expect(page).toHaveURL(/dashboard/);
  await context.clearCookies({ name: "yf_access" });
  const renewed = await Promise.all([
    page.request.get("/api/auth/me/"),
    page.request.get("/api/cargo/loads/?mine=1"),
  ]);
  expect(renewed.map((response) => response.status())).toEqual([200, 200]);
  expect((await page.request.get("/api/auth/users/")).status()).toBe(403);
  expect(
    (await page.request.post("/api/cargo/loads/", { data: {} })).status(),
  ).toBe(403);
  expect((await page.request.get("/api/auth/logout/")).status()).toBe(405);
  await page.goto("/companies");
  await page
    .getByRole("button", { name: "Kompaniya yaratish", exact: true })
    .click();
  await page
    .getByLabel("Kompaniya nomi *", { exact: true })
    .fill(`Frontend QA ${username}`);
  await page
    .getByRole("button", { name: "Kompaniyani yaratish", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Jamoa a’zolari", exact: true }),
  ).toBeVisible();
  await page.goto("/loads/new");
  await page
    .getByLabel("E’lon egasi")
    .selectOption({ label: `Frontend QA ${username}` });
  await page.getByLabel("Qayerdan *", { exact: true }).fill("QA Toshkent");
  await page.getByLabel("Qayerga *", { exact: true }).fill("QA Samarqand");
  await page
    .getByLabel("Yuk nomi *", { exact: true })
    .fill("Frontend avtomatik sinov");
  await page
    .getByLabel("Kerakli transport *", { exact: true })
    .fill("Tent fura");
  await page.getByLabel("Og‘irlik (tonna) *", { exact: true }).fill("1.5");
  await page
    .getByRole("button", { name: "Yukni joylash", exact: true })
    .click();
  await expect(page).toHaveURL(/\/loads\/\d+$/);
  const id = page.url().split("/").pop();
  await expect(
    page.getByRole("link", { name: "+998901234567", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Tahrirlash", exact: true }).click();
  await page.getByLabel("Qayerga *", { exact: true }).fill("QA Buxoro");
  await page.getByRole("button", { name: "O‘zgarishlarni saqlash" }).click();
  await expect(
    page.getByRole("heading", { name: "QA Toshkent → QA Buxoro" }),
  ).toBeVisible();
  await page.goto("/my-loads");
  await page.getByRole("button", { name: "Yopish", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Qayta ochish", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "O‘chirish", exact: true }).click();
  await page
    .getByRole("alertdialog")
    .getByRole("button", { name: "O‘chirish", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Hozircha e’lon yo‘q" }),
  ).toBeVisible();
  const response = await page.request.get(`/api/cargo/loads/${id}/`);
  expect(response.status()).toBe(404);
  await page.goto("/profile");
  await page.getByLabel("Ism", { exact: true }).fill("Sinov yakunlandi");
  await page.getByRole("button", { name: "O‘zgarishlarni saqlash" }).click();
  await expect(page.getByRole("status")).toContainText("Profil saqlandi");
  await page.getByRole("button", { name: "Akkauntdan chiqish" }).click();
  await expect(
    page.getByRole("link", { name: "Kirish", exact: true }),
  ).toBeVisible();
});

test("Russian persists across pages and reloads without translating cargo data", async ({
  page,
}) => {
  await page.route("**/api/auth/me/", (route) =>
    route.fulfill({ status: 401, json: {} }),
  );
  await page.route("**/api/cargo/loads/**", (route) =>
    route.fulfill({ json: [load] }),
  );
  const response = await page.goto("/");
  expect(response?.headers()["x-frame-options"]).toBe("DENY");
  expect(response?.headers()["content-security-policy"]).toContain("'nonce-");
  await page.getByLabel("Til / Язык").selectOption("ru");
  await expect(
    page.getByRole("heading", { name: "Найдите груз. Отправляйтесь в путь." }),
  ).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  await expect(page.locator(".load-card")).toContainText(
    "Qurilish materiallari",
  );
  await expect(page.locator(".load-card")).toContainText("Договорная");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: "test-results/russian-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.goto("/login");
  await expect(
    page.getByRole("heading", { name: "Добро пожаловать", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByLabel("Имя пользователя", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Til / Язык").selectOption("uz");
  await expect(
    page.getByRole("heading", { name: "Xush kelibsiz", exact: true }),
  ).toBeVisible();
});

test("API rejects oversized JSON and cross-scheme origins", async ({
  request,
}) => {
  const oversized = await request.post("/api/auth/login/", {
    headers: { Origin: "http://127.0.0.1:3018" },
    data: { username: "x".repeat(70000), password: "wrong" },
  });
  expect(oversized.status()).toBe(413);
  const crossOrigin = await request.post("/api/auth/login/", {
    headers: { Origin: "https://127.0.0.1:3018" },
    data: {},
  });
  expect(crossOrigin.status()).toBe(403);
  const unknown = await request.get("/api/private/settings/");
  expect(unknown.status()).toBe(404);
});
