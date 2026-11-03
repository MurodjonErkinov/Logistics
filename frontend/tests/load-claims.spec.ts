import { test, expect } from "@playwright/test";

test("driver confirms contact, takes a load and opens its map and updated driver count", async ({
  page,
}) => {
  let taken = false;
  let count = 2;
  let claims = 0;
  const blockedFrames: string[] = [];
  page.on("console", (message) => {
    if (/frame-src/.test(message.text())) blockedFrames.push(message.text());
  });
  const user = {
    id: 10,
    username: "driver",
    first_name: "Sardor",
    last_name: "",
    email: "",
    phone_number: "",
    role: "driver",
    is_staff: false,
  };
  const load = () => ({
    id: 42,
    origin: "Toshkent",
    destination: "Namangan",
    cargo_name: "Meva va sabzavotlar",
    vehicle_type: "Tent",
    weight_tons: "5.00",
    is_price_negotiable: false,
    price_amount: "2500000",
    currency: "UZS",
    contact_phone: "+998901234567",
    alternate_phone: "",
    pickup_date: null,
    notes: "Yuk ombordan olinadi.",
    status: "open",
    posted_by: 20,
    posted_by_username: "dispatch",
    company: null,
    source_url: "https://t.me/loads/123",
    created_at: "2026-11-04T08:00:00Z",
    updated_at: "2026-11-04T08:00:00Z",
    claim_count: count,
    is_claimed: taken,
    claimed_at: taken ? "2026-11-04T09:00:00Z" : null,
  });
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/$/, "");
    if (path.endsWith("/auth/me")) return route.fulfill({ json: user });
    if (path.endsWith("/cargo/loads/42/claim")) {
      expect(route.request().postDataJSON()).toEqual({
        confirmed_contact: true,
      });
      claims++;
      taken = true;
      count++;
      return route.fulfill({ status: 201, json: load() });
    }
    if (path.endsWith("/cargo/loads/42"))
      return route.fulfill({ json: load() });
    if (path.endsWith("/map-locations"))
      return route.fulfill({
        json: {
          origin: {
            lat: 41.31,
            lon: 69.28,
            approximate: true,
            label: "Toshkent, Uzbekistan",
          },
          destination: {
            lat: 40.99,
            lon: 71.67,
            approximate: true,
            label: "Namangan, Uzbekistan",
          },
        },
      });
    if (path.endsWith("/cargo/loads"))
      return route.fulfill({ json: taken ? [load()] : [] });
    if (path.endsWith("/unread")) return route.fulfill({ json: { count: 0 } });
    return route.fulfill({ json: [] });
  });
  await page.goto("/loads/42", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Yukni olish", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Yuk egasi bilan gaplashdingizmi?" }),
  ).toBeVisible();
  await dialog.screenshot({ path: "test-results/take-load-confirmation.png" });
  await dialog.getByRole("button", { name: "Hali gaplashmadim" }).click();
  expect(claims).toBe(0);
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "Yukni olish", exact: true }).click();
  await dialog
    .getByRole("button", { name: "Ha, yukni olish", exact: true })
    .click();
  await expect(page).toHaveURL(/\/driver\/?$/);
  await expect(
    page.getByRole("heading", { name: "Mening yuklarim", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".haul-card")).toHaveCount(1);
  await expect(page.locator(".haul-card-footer")).toContainText("2");
  await page.screenshot({
    path: "test-results/my-loads-desktop.png",
    fullPage: true,
  });
  await page.locator(".haul-card").click();
  await expect(
    page.getByRole("heading", { name: "Yuk sizning ro‘yxatingizda" }),
  ).toBeVisible();
  await expect(page.locator(".claim-activity strong")).toHaveText(
    "2 boshqa haydovchi",
  );
  count = 5;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.locator(".claim-activity strong")).toHaveText(
    "4 boshqa haydovchi",
  );
  await page.getByRole("tab", { name: /Tushirish.*Namangan/ }).click();
  await expect(
    page.getByRole("tab", { name: /Tushirish.*Namangan/ }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".load-map iframe")).toHaveAttribute(
    "src",
    /marker=40.99,71.67/,
  );
  await expect(
    page.getByRole("link", { name: "Yo‘lni ochish" }),
  ).toHaveAttribute("href", /origin=Toshkent&destination=Namangan/);
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .locator(".claim-panel")
    .screenshot({ path: "test-results/taken-load-mobile.png" });
  await page.locator(".load-map").scrollIntoViewIfNeeded();
  await expect(
    page
      .frameLocator(".load-map iframe")
      .getByRole("region", { name: "Map", exact: true }),
  ).toBeVisible({ timeout: 20000 });
  await page
    .frameLocator(".load-map iframe")
    .getByRole("button", { name: "Zoom In", exact: true })
    .click();
  await page
    .locator(".route-map-panel")
    .screenshot({ path: "test-results/load-map-mobile.png" });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.goto("/driver");
  await page
    .getByRole("textbox", { name: "Yuklarimdan qidirish" })
    .fill("Buxoro");
  await expect(page.locator(".haul-card")).toHaveCount(0);
  await page
    .getByRole("textbox", { name: "Yuklarimdan qidirish" })
    .fill("Namangan");
  await expect(page.locator(".haul-card")).toHaveCount(1);
  await page.screenshot({
    path: "test-results/my-loads-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  expect(claims).toBe(1);
  expect(blockedFrames).toEqual([]);
});

test("a rejected claim stays in the confirmation dialog and does not navigate", async ({
  page,
}) => {
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.includes("auth/me"))
      return route.fulfill({
        json: { id: 10, username: "driver", role: "driver" },
      });
    if (path.includes("/claim/"))
      return route.fulfill({
        status: 400,
        json: { detail: "Bu yuk e’loni endi aktual emas." },
      });
    if (path.includes("cargo/loads/42"))
      return route.fulfill({
        json: {
          id: 42,
          origin: "Toshkent",
          destination: "Namangan",
          cargo_name: "Meva",
          vehicle_type: "Tent",
          weight_tons: "5",
          status: "open",
          posted_by: 20,
          created_at: "2026-11-04",
          claim_count: 0,
        },
      });
    if (path.includes("/unread")) return route.fulfill({ json: { count: 0 } });
    return route.fulfill({ json: [] });
  });
  await page.goto("/loads/42", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Yukni olish", exact: true }).click();
  await page
    .getByRole("button", { name: "Ha, yukni olish", exact: true })
    .click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "endi aktual emas",
  );
  await expect(page).toHaveURL(/\/loads\/42/);
});
