import { test, expect, type Page } from "@playwright/test";

const challenge = {
  verification_id: "01234567-89ab-4cde-abcd-0123456789ab",
  bot_url:
    "https://t.me/YukFlowTestBot?start=reset_0123456789ab4cdeabcd0123456789ab",
  retry_after: 60,
};

async function mockRecovery(page: Page) {
  await page.route("**/api/auth/me/", (route) =>
    route.fulfill({ status: 401, json: {} }),
  );
  await page.context().route("https://t.me/YukFlowTestBot**", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: "<title>Telegram test</title>",
    }),
  );
  await page.route("**/api/auth/password-reset-code/", (route) => {
    expect(route.request().postDataJSON()).toEqual({
      phone_number: "+998901234567",
    });
    return route.fulfill({ status: 201, json: challenge });
  });
}

async function enterPasswords(page: Page, confirmation = "ChangedSecret851!") {
  await page.getByLabel("Tasdiqlash kodi", { exact: true }).fill("123456");
  await page
    .getByLabel("Yangi parol", { exact: true })
    .fill("ChangedSecret851!");
  await page
    .getByLabel("Yangi parolni takrorlang", { exact: true })
    .fill(confirmation);
}

test("existing users recover through Telegram and return to login with their destination preserved", async ({
  page,
}) => {
  await mockRecovery(page);
  let resetRequests = 0;
  let registrationRequests = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/auth/register/")) registrationRequests++;
  });
  await page.route("**/api/auth/reset-password/", (route) => {
    resetRequests++;
    expect(route.request().postDataJSON()).toEqual({
      phone_number: "+998901234567",
      verification_id: challenge.verification_id,
      verification_code: "123456",
      password: "ChangedSecret851!",
      password_confirm: "ChangedSecret851!",
    });
    return route.fulfill({ json: { detail: "Parolingiz yangilandi." } });
  });
  await page.goto("/login?next=%2Fdriver%2Ftickets");
  await page
    .getByRole("link", { name: "Parolni unutdingizmi?", exact: true })
    .click();
  await expect(page).toHaveURL(/\/forgot-password\?next=%2Fdriver%2Ftickets$/);
  await expect(page.locator(".auth-root")).toBeVisible();
  await expect(page.locator(".sidebar")).toHaveCount(0);
  await page.getByLabel("Telefon raqam", { exact: true }).fill("+998901234567");
  const [telegram] = await Promise.all([
    page.waitForEvent("popup"),
    page
      .getByRole("button", { name: "Telegramdan kod olish", exact: true })
      .click(),
  ]);
  await expect(telegram).toHaveURL(challenge.bot_url);
  expect(await telegram.evaluate(() => window.opener)).toBeNull();
  await telegram.close();
  await expect(page.locator(".auth-form-wrap")).toContainText(
    "Start bosganingizda kod beriladi",
  );
  await enterPasswords(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: "test-results/password-reset-desktop.png" });
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByLabel("Tasdiqlash kodi", { exact: true })
    .scrollIntoViewIfNeeded();
  await page.screenshot({ path: "test-results/password-reset-mobile.png" });
  await page
    .getByRole("button", { name: "Parolni yangilash", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Parolingiz yangilandi", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText(
    "Avvalgi sessiyalar yakunlandi",
  );
  expect(resetRequests).toBe(1);
  expect(registrationRequests).toBe(0);
  await page.getByRole("link", { name: "Kirish", exact: true }).click();
  await expect(page).toHaveURL(/\/login\?next=%2Fdriver%2Ftickets$/);
  await expect(page.getByLabel("Parol", { exact: true })).toHaveValue("");
});

test("registration has recovery; mismatched and expired codes keep the form editable", async ({
  page,
}) => {
  await mockRecovery(page);
  await page.addInitScript(() => {
    window.open = () => null;
  });
  let resetRequests = 0;
  await page.route("**/api/auth/reset-password/", (route) => {
    resetRequests++;
    return route.fulfill({
      status: 400,
      json: { verification_code: ["Kod noto‘g‘ri yoki muddati tugagan."] },
    });
  });
  await page.goto("/register");
  await page
    .getByRole("link", { name: "Parolni unutdingizmi?", exact: true })
    .click();
  await page.getByLabel("Telefon raqam", { exact: true }).fill("+998901234567");
  await page
    .getByRole("button", { name: "Telegramdan kod olish", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "Telegramga o‘tish" }),
  ).toHaveAttribute("href", challenge.bot_url);
  await enterPasswords(page, "DifferentSecret851!");
  await page
    .getByRole("button", { name: "Parolni yangilash", exact: true })
    .click();
  await expect(page.locator(".error-box")).toContainText(
    "Parollar bir xil bo‘lishi kerak.",
  );
  expect(resetRequests).toBe(0);
  await page
    .getByLabel("Yangi parolni takrorlang", { exact: true })
    .fill("ChangedSecret851!");
  await page
    .getByRole("button", { name: "Parolni yangilash", exact: true })
    .click();
  await expect(page.locator(".error-box")).toContainText("muddati tugagan");
  await expect(page.getByLabel("Yangi parol", { exact: true })).toHaveValue(
    "ChangedSecret851!",
  );
  await page.getByLabel("Telefon raqam", { exact: true }).fill("+998909999999");
  await expect(page.getByLabel("Tasdiqlash kodi", { exact: true })).toHaveCount(
    0,
  );
  await expect(page.locator('input[name="verification_id"]')).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Administratorga yozing" }),
  ).toHaveAttribute("href", "https://t.me/murodjonerkinov");
  await page.getByLabel("Til / Язык").selectOption("ru");
  await expect(
    page.getByRole("heading", { name: "Восстановление пароля", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Новый пароль", { exact: true })).toBeVisible();
});

test("unavailable recovery bot closes its temporary Telegram tab", async ({
  page,
}) => {
  await mockRecovery(page);
  await page.route("**/api/auth/password-reset-code/", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Bot vaqtincha ishlamayapti." },
    }),
  );
  await page.goto("/forgot-password?next=https://example.com");
  await page.getByLabel("Telefon raqam", { exact: true }).fill("+998901234567");
  await page
    .getByRole("button", { name: "Telegramdan kod olish", exact: true })
    .click();
  await expect(page.locator(".error-box")).toContainText(
    "Bot vaqtincha ishlamayapti.",
  );
  await expect.poll(() => page.context().pages().length).toBe(1);
  await expect(
    page.getByRole("link", { name: "Kirish", exact: true }),
  ).toHaveAttribute("href", "/login");
  await expect(
    page.getByRole("button", { name: "Telegramdan kod olish", exact: true }),
  ).toBeEnabled();
});
