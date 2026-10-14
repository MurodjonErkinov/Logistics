import { test, expect } from "@playwright/test";
const user = {
  id: 801,
  username: "driver_test",
  first_name: "Sardor",
  last_name: "",
  email: "",
  phone_number: "+998900000001",
  role: "driver",
  is_staff: false,
};
const load = {
  id: 10,
  origin: "Andijon",
  destination: "Namangan",
  cargo_name: "Karzinka",
  vehicle_type: "Tent",
  weight_tons: "1.5",
  is_price_negotiable: true,
  price_amount: null,
  currency: "UZS",
  contact_phone: "+998900000001",
  alternate_phone: "",
  pickup_date: null,
  notes: "",
  status: "open",
  posted_by: 12,
  posted_by_username: "sender",
  company: null,
  source_url: null,
  created_at: "2026-10-06T05:00:00Z",
  updated_at: "2026-10-06T05:00:00Z",
};

test("driver login, route selection, filters, saved loads, Russian and mobile", async ({
  page,
}) => {
  await page.route("https://yandex.com/**", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: "<html><body>Map provider test</body></html>",
    }),
  );
  await page.route("**/api/auth/me/", (route) => route.fulfill({ json: user }));
  await page.route("**/api/auth/login/", (route) =>
    route.fulfill({ json: {} }),
  );
  await page.route("**/api/cargo/loads/**", (route) =>
    route.fulfill({
      json: [
        load,
        {
          ...load,
          id: 11,
          origin: "Toshkent",
          destination: "Samarqand",
          weight_tons: "20",
        },
      ],
    }),
  );
  await page.goto("/login");
  await page
    .getByLabel("Foydalanuvchi nomi", { exact: true })
    .fill("driver_test");
  await page.getByLabel("Parol", { exact: true }).fill("Testing12345!");
  await page.getByRole("button", { name: "Kirish", exact: true }).click();
  await expect(page).toHaveURL(/\/driver$/);
  await expect(
    page.getByRole("heading", { name: "Salom, Sardor." }),
  ).toBeVisible();
  await expect(page.locator("iframe")).toHaveAttribute(
    "src",
    /rtext=Toshkent%7ESamarqand/,
  );
  await page.getByRole("button", { name: "Andijon → Namangan" }).click();
  await expect(page.locator("iframe")).toHaveAttribute(
    "src",
    /rtext=Andijon%7ENamangan/,
  );
  await expect(
    page.getByRole("link", { name: "Qo‘ng‘iroq qilish" }),
  ).toHaveAttribute("href", "tel:+998900000001");
  await page
    .locator(".workspace-load.selected")
    .getByRole("button", { name: "Yukni saqlash", exact: true })
    .click();
  await page.getByLabel("Faqat saqlanganlar", { exact: true }).check();
  await expect(page.locator(".workspace-load")).toHaveCount(1);
  await page.getByLabel("Qayerdan", { exact: true }).fill("Buxoro");
  await expect(
    page.getByRole("heading", { name: "Yuk topilmadi" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Filtrlarni tozalash" }).click();
  await page.getByLabel("Eng ko‘p og‘irlik (t)").fill("2");
  await expect(page.locator(".workspace-load")).toHaveCount(1);
  await page.getByLabel("Til / Язык").selectOption("ru");
  await expect(
    page.getByRole("heading", { name: "Здравствуйте, Sardor." }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/driver-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "test-results/driver-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
});

test("sender gets own-load dashboard and guests cannot mount authenticated data", async ({
  page,
}) => {
  let authenticated = false;
  const requests: string[] = [];
  await page.route("https://yandex.com/**", (route) =>
    route.fulfill({ contentType: "text/html", body: "Map" }),
  );
  await page.route("**/api/auth/me/", (route) =>
    authenticated
      ? route.fulfill({ json: { ...user, role: "user" } })
      : route.fulfill({ status: 401, json: { detail: "Unauthenticated" } }),
  );
  await page.route("**/api/cargo/loads/**", (route) => {
    requests.push(route.request().url());
    return route.fulfill({ json: [load] });
  });
  await page.goto("/driver");
  await expect(
    page.getByRole("link", { name: "Akkauntga kirish" }),
  ).toBeVisible();
  expect(requests).toHaveLength(0);
  authenticated = true;
  await page.goto("/dashboard");
  await expect(
    page.getByRole("link", { name: "E’lonlarni boshqarish" }),
  ).toBeVisible();
  expect(requests.some((url) => url.endsWith("?mine=1"))).toBe(true);
  await expect(
    page.locator("nav").getByRole("link", { name: "Ish kabineti" }),
  ).toBeVisible();
});
