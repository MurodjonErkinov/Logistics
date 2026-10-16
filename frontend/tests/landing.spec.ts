import { test, expect, type Page } from "@playwright/test";

const user = {
  id: 42,
  username: "landing_user",
  first_name: "Ali",
  last_name: "",
  email: "",
  phone_number: "+998901234567",
  role: "driver",
  is_staff: false,
};

async function mockSession(page: Page) {
  let signedIn = false;
  let account = { ...user };
  await page.route("**/api/auth/me/", (route) =>
    route.fulfill(signedIn ? { json: account } : { status: 401, json: {} }),
  );
  await page.route("**/api/auth/login/", (route) => {
    signedIn = true;
    return route.fulfill({ json: {} });
  });
  await page.route("**/api/auth/register/", (route) => {
    account = { ...account, ...route.request().postDataJSON() };
    return route.fulfill({ status: 201, json: account });
  });
  await page.route("**/api/auth/logout/", (route) => {
    signedIn = false;
    return route.fulfill({ json: {} });
  });
  await page.route("**/api/cargo/loads/**", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route("**/api/driver/notifications/unread/", (route) =>
    route.fulfill({ json: { count: 0 } }),
  );
}

test("guest homepage: sections, role tabs, FAQ, registration and responsive layouts", async ({
  page,
}) => {
  await mockSession(page);
  let cargoRequests = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/cargo/loads/")) cargoRequests++;
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Yukingizga yo‘l.Yo‘lingizga yuk.",
  );
  await expect(page.locator(".sidebar")).toHaveCount(0);
  await expect(page.locator(".load-card")).toHaveCount(0);
  expect(cargoRequests).toBe(0);
  await expect
    .poll(() =>
      page
        .locator('img[src*="convoy-hero"]')
        .evaluate((img) => (img as HTMLImageElement).naturalWidth),
    )
    .toBeGreaterThan(0);
  await page.screenshot({ path: "test-results/landing-hero.png" });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "test-results/landing-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("tab", { name: "Yuk joylovchiman", exact: true })
    .click();
  await expect(page.getByRole("tabpanel")).toContainText(
    "Yuk e’lonini joylang",
  );
  await page.getByRole("tab", { name: "Haydovchiman", exact: true }).click();
  await expect(page.getByRole("tabpanel")).toContainText(
    "Shartlaringiz bilan tiket oching",
  );
  await page
    .locator("summary")
    .filter({ hasText: "Mos yuklar haqida qanday xabar olaman?" })
    .click();
  await expect(page.locator("details[open]")).toContainText([
    "YukFlow",
    "Telegramni ulasangiz",
  ]);
  await page
    .getByRole("link", { name: "Men haydovchiman", exact: true })
    .click();
  await expect(page).toHaveURL(/\/register\?role=driver$/);
  await expect(page.locator('select[name="role"]')).toHaveValue("driver");
  await page.goto("/");
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 844 });
    await expect
      .poll(() =>
        page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      )
      .toBe(true);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "test-results/landing-mobile-hero.png",
    animations: "disabled",
  });
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({
    path: "test-results/landing-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: "Menyuni ochish", exact: true })
    .click();
  await page
    .getByRole("navigation", { name: "Mobil menyu", exact: true })
    .getByRole("link", { name: "Qanday ishlaydi?", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Menyuni ochish", exact: true }),
  ).toHaveAttribute("aria-expanded", "false");
  await page.getByLabel("Til / Язык").selectOption("ru");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Грузу — дорогу.В дорогу — груз.",
  );
  await expect(
    page.getByRole("tab", { name: "Я водитель", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/landing-mobile-ru.png",
    fullPage: true,
  });
});

test("login shows existing workspace and marketplace; logout restores guest homepage", async ({
  page,
}) => {
  await mockSession(page);
  await page.goto("/");
  await page
    .getByRole("banner")
    .getByRole("link", { name: "Kirish", exact: true })
    .click();
  await page
    .getByLabel("Foydalanuvchi nomi", { exact: true })
    .fill("landing_user");
  await page.getByLabel("Parol", { exact: true }).fill("Testing12345!");
  await page.getByRole("button", { name: "Kirish", exact: true }).click();
  await expect(page).toHaveURL(/\/driver$/);
  await expect(
    page.getByRole("heading", { name: "Salom, Ali." }),
  ).toBeVisible();
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Yuk toping. Yo‘lga chiqing." }),
  ).toBeVisible();
  await expect(page.locator(".sidebar")).toHaveCount(1);
  await page.getByRole("button", { name: "Akkauntdan chiqish" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Yukingizga yo‘l.Yo‘lingizga yuk.",
  );
  await expect(page.locator(".sidebar")).toHaveCount(0);
});

test("dispatcher registration selects role and opens existing dashboard", async ({
  page,
}) => {
  await mockSession(page);
  await page.goto("/");
  await page
    .getByRole("link", { name: "Yuk joylamoqchiman", exact: true })
    .click();
  await expect(page.locator('select[name="role"]')).toHaveValue("dispatcher");
  await page.getByLabel("Ism", { exact: true }).fill("Ali");
  await page
    .getByLabel("Foydalanuvchi nomi", { exact: true })
    .fill("new_dispatcher");
  await page.getByLabel("Telefon raqam").fill("+998901234567");
  await page.getByLabel("Parol", { exact: true }).fill("Testing12345!");
  await page
    .getByRole("button", { name: "Akkaunt yaratish", exact: true })
    .click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Salom, Ali." }),
  ).toBeVisible();
});

test("quick shipment preserves route and vehicle through login", async ({
  page,
}) => {
  await mockSession(page);
  await page.route("**/api/partners/companies/**", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.goto("/");
  const form = page.locator("#send-load");
  await form.getByLabel("Qayerdan", { exact: true }).fill("Toshkent");
  await form.getByLabel("Qayerga", { exact: true }).fill("Samarqand");
  await form.locator('input[value="isuzu-5"]').check();
  await form.locator('input[name="price_amount"]').fill("125.50");
  await form.getByLabel("Valyuta", { exact: true }).selectOption("USD");
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    const amount = form.locator('input[name="price_amount"]');
    const currency = form.getByLabel("Valyuta", { exact: true });
    const amountBox = await amount.boundingBox();
    const currencyBox = await currency.boundingBox();
    expect(amountBox!.width).toBeGreaterThan(100);
    expect(currencyBox!.width).toBeLessThan(100);
    expect(currencyBox!.x + currencyBox!.width).toBeLessThanOrEqual(width);
    await expect
      .poll(() =>
        form
          .locator("img")
          .first()
          .evaluate((img) => (img as HTMLImageElement).naturalWidth),
      )
      .toBeGreaterThan(0);
    await amount.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `test-results/shipment-price-${width}.png` });
  }
  await form.getByRole("button", { name: "Yuk yuborishni boshlash" }).click();
  await expect(page).toHaveURL(/register\?role=dispatcher&next=/);
  await page
    .locator(".auth-switch")
    .getByRole("link", { name: "Kirish" })
    .click();
  await expect(page).toHaveURL(/\/login\?next=/);
  await page.locator('input[name="username"]').fill("landing_user");
  await page.locator('input[name="password"]').fill("password123");
  await page.getByRole("button", { name: "Kirish", exact: true }).click();
  await expect(page).toHaveURL(/\/loads\/new\?/);
  await expect(page.locator('input[name="origin"]')).toHaveValue("Toshkent");
  await expect(page.locator('input[name="destination"]')).toHaveValue(
    "Samarqand",
  );
  await expect(page.locator('input[name="vehicle_type"]')).toHaveValue(
    "ISUZU 5",
  );
  await expect(page.locator('input[name="price_amount"]')).toHaveValue(
    "125.50",
  );
  await expect(page.locator('select[name="currency"]')).toHaveValue("USD");
  await expect(
    page.getByLabel("Narx kelishiladi", { exact: true }),
  ).not.toBeChecked();
});
