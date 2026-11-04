import { test, expect, type Page } from "@playwright/test";

const berlin = {
  id: "N:1",
  name: "Berlin",
  description: "Germany",
  country_code: "DE",
  lat: 52.52,
  lon: 13.405,
};
const paris = {
  id: "N:2",
  name: "Paris",
  description: "Île-de-France, France",
  country_code: "FR",
  lat: 48.8566,
  lon: 2.3522,
};

async function mockApi(page: Page, role?: string) {
  const queries: string[] = [];
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/$/, "");
    if (path.endsWith("/auth/me"))
      return role
        ? route.fulfill({
            json: {
              id: 1,
              username: "test_user",
              first_name: "Sardor",
              role,
              is_staff: false,
            },
          })
        : route.fulfill({ status: 401, json: {} });
    if (path.endsWith("/cargo/cities")) {
      const query = url.searchParams.get("q") || "";
      queries.push(query);
      if (query === "Offline")
        return route.fulfill({ status: 503, json: { detail: "Unavailable" } });
      return route.fulfill({
        json: /^Par/i.test(query)
          ? [paris]
          : /^Ber/i.test(query)
            ? [berlin]
            : [],
      });
    }
    if (path.endsWith("/driver/vehicles"))
      return route.fulfill({
        json: [
          {
            id: 10,
            name: "Volvo",
            kind: "tent",
            capacity_tons: "20",
            volume_m3: null,
            plate: "",
          },
        ],
      });
    if (path.endsWith("/driver/preferences"))
      return route.fulfill({
        json: {
          language: "uz",
          telegram_enabled: true,
          partial_interval_minutes: 30,
          timezone: "Asia/Tashkent",
        },
      });
    if (path.endsWith("/unread")) return route.fulfill({ json: { count: 0 } });
    return route.fulfill({ json: [] });
  });
  return queries;
}

test("homepage city suggestions support keyboard, mobile selection and manual entry on outage", async ({
  page,
}) => {
  const queries = await mockApi(page);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const form = page.locator("#send-load");
  const origin = form.getByRole("combobox", { name: "Qayerdan", exact: true });
  await origin.fill("B");
  await origin.fill("Ber");
  const option = page.getByRole("option", { name: /Berlin.*Germany/ });
  await expect(option).toBeVisible();
  expect(queries).toEqual(["Ber"]);
  await page.screenshot({
    path: "test-results/city-search-desktop.png",
    fullPage: false,
  });
  await origin.press("ArrowDown");
  await origin.press("Enter");
  await expect(origin).toHaveValue("Berlin");
  await expect(page.getByRole("listbox")).not.toBeVisible();
  await expect(page).toHaveURL(/\/$/);
  await page.setViewportSize({ width: 390, height: 844 });
  const destination = form.getByRole("combobox", {
    name: "Qayerga",
    exact: true,
  });
  await destination.fill("Par");
  await expect(
    page.getByRole("option", { name: /Paris.*France/ }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/city-search-mobile.png" });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("option", { name: /Paris.*France/ }).click();
  await expect(destination).toHaveValue("Paris");
  await destination.fill("Offline");
  await expect(page.getByRole("status")).toContainText(
    "Manzilni qo‘lda kiriting",
  );
  await destination.press("Escape");
  await expect(destination).toHaveValue("Offline");
  await expect(page.getByRole("listbox")).not.toBeVisible();
});

test("marketplace and workspace filter inputs use the same city search", async ({
  page,
}) => {
  await mockApi(page, "dispatcher");
  for (const path of ["/", "/dashboard"]) {
    await page.goto(path, { waitUntil: "domcontentloaded" });
    const origin = page.getByRole("combobox", {
      name: "Qayerdan",
      exact: true,
    });
    await origin.fill("Ber");
    await page.getByRole("option", { name: /Berlin.*Germany/ }).click();
    await expect(origin).toHaveValue("Berlin");
    const destination = page.getByRole("combobox", {
      name: "Qayerga",
      exact: true,
    });
    await destination.fill("Par");
    await page.getByRole("option", { name: /Paris.*France/ }).click();
    await expect(destination).toHaveValue("Paris");
  }
});

test("a slower old search cannot replace suggestions for the latest input", async ({
  page,
}) => {
  await mockApi(page, "dispatcher");
  let started = false;
  let finished = false;
  let release: () => void = () => {};
  const oldRequest = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/cargo/cities/**", async (route) => {
    const query = new URL(route.request().url()).searchParams.get("q");
    if (query === "Ber") {
      started = true;
      await oldRequest;
      try {
        await route.fulfill({ json: [berlin] });
      } catch {
        /* The browser cancelled the old request. */
      }
      finished = true;
    } else await route.fulfill({ json: [paris] });
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const origin = page.getByRole("combobox", { name: "Qayerdan", exact: true });
  await origin.fill("Ber");
  await expect.poll(() => started).toBeTruthy();
  await origin.fill("Par");
  await expect(
    page.getByRole("option", { name: /Paris.*France/ }),
  ).toBeVisible();
  release();
  await expect.poll(() => finished).toBeTruthy();
  await expect(
    page.getByRole("option", { name: /Berlin.*Germany/ }),
  ).not.toBeVisible();
  await expect(
    page.getByRole("option", { name: /Paris.*France/ }),
  ).toBeVisible();
});

test("load form records selected coordinates and clears them when city text is edited", async ({
  page,
}) => {
  await mockApi(page, "dispatcher");
  await page.goto("/loads/new", { waitUntil: "domcontentloaded" });
  const origin = page.getByRole("combobox", {
    name: "Qayerdan *",
    exact: true,
  });
  await origin.fill("Ber");
  await page.getByRole("option", { name: /Berlin.*Germany/ }).click();
  await page
    .getByText("Yuklash va tushirish koordinatalari", { exact: true })
    .click();
  await expect(
    page.getByLabel("Yuklash kengligi", { exact: true }),
  ).toHaveValue("52.5200000");
  await origin.fill("Berl");
  await expect(
    page.getByLabel("Yuklash kengligi", { exact: true }),
  ).toHaveValue("");
});

test("ticket pickup and destination cities use the shared autocomplete", async ({
  page,
}) => {
  await mockApi(page, "driver");
  await page.goto("/driver/tickets", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Tiket ochish", exact: true }).click();
  await page.getByLabel("Tiket nomi", { exact: true }).fill("Xalqaro tiket");
  await page.getByRole("button", { name: "Davom etish", exact: true }).click();
  await page
    .locator(".simple-ticket-vehicles")
    .getByRole("button", { name: /Volvo/ })
    .click();
  const pickup = page.getByRole("group", {
    name: "Yuklash joylari",
    exact: true,
  });
  await pickup
    .getByRole("combobox", { name: "Shahar", exact: true })
    .fill("Ber");
  await page.getByRole("option", { name: /Berlin.*Germany/ }).click();
  await page.getByRole("button", { name: "Davom etish", exact: true }).click();
  const destinations = page.getByRole("group", {
    name: "Boradigan manzillar",
    exact: true,
  });
  await destinations
    .getByRole("combobox", { name: "Shahar", exact: true })
    .fill("Par");
  await page.getByRole("option", { name: /Paris.*France/ }).click();
  await destinations
    .getByRole("button", { name: "Manzil qo‘shish", exact: true })
    .click();
  await expect(page.locator(".simple-ticket-picked")).toContainText("Paris");
});
