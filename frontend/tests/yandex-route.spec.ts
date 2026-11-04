import { test, expect } from "@playwright/test";
import { yandexRoutePoint, yandexRouteUrls } from "../src/lib/yandex-maps";

test("routes use latitude then longitude, handle missing coordinates, and retain exactly two endpoints", () => {
  const from = yandexRoutePoint("Toshkent", "41.31", "69.28");
  const to = yandexRoutePoint("Namangan", 40.99, 71.67);
  const { embed, external } = yandexRouteUrls(from, to, "uz");
  expect(new URL(embed).searchParams.get("rtext")).toBe(
    "41.31,69.28~40.99,71.67",
  );
  expect(new URL(embed).searchParams.get("rtt")).toBe("auto");
  expect(new URL(external).search).toBe(new URL(embed).search);
  expect(yandexRoutePoint("Toshkent", 999, 69)).toBe("Toshkent");
  expect(yandexRoutePoint("Toshkent", "", "")).toBe("Toshkent");
  expect(
    new URL(yandexRouteUrls("A~B", "C", "ru").embed).searchParams.get("rtext"),
  ).toBe("A B~C");
});

test("a load displays both endpoints in one Yandex route without a separate geocoding request", async ({
  page,
}) => {
  let mapRequests = 0;
  const blockedFrames: string[] = [];
  page.on("console", (message) => {
    if (/frame-src/.test(message.text())) blockedFrames.push(message.text());
  });
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.includes("auth/me"))
      return route.fulfill({
        json: {
          id: 1,
          username: "driver",
          first_name: "Sardor",
          role: "driver",
        },
      });
    if (path.includes("map-locations")) {
      mapRequests++;
      return route.fulfill({ json: {} });
    }
    if (path.includes("cargo/loads/42"))
      return route.fulfill({
        json: {
          id: 42,
          origin: "Toshkent",
          destination: "Namangan",
          origin_lat: "41.31",
          origin_lon: "69.28",
          destination_lat: "40.99",
          destination_lon: "71.67",
          cargo_name: "Meva",
          vehicle_type: "Tent",
          weight_tons: "5",
          status: "open",
          posted_by: 2,
          contact_phone: "+998901234567",
          created_at: "2026-11-04",
        },
      });
    return route.fulfill({ json: path.includes("unread") ? { count: 0 } : [] });
  });
  await page.goto("/loads/42", { waitUntil: "domcontentloaded" });
  const map = page.locator(".route-map-panel");
  await expect(map.locator("iframe")).toHaveCount(1);
  const src = await map.locator("iframe").getAttribute("src");
  expect(new URL(src!).searchParams.get("rtext")).toBe(
    "41.31,69.28~40.99,71.67",
  );
  expect(new URL(src!).searchParams.get("mode")).toBe("routes");
  await expect(map.getByRole("heading")).toContainText("Toshkent");
  await expect(map.getByRole("heading")).toContainText("Namangan");
  await map.scrollIntoViewIfNeeded();
  await expect(
    page.frameLocator(".route-map-panel iframe").locator("body"),
  ).toBeVisible({ timeout: 20000 });
  await expect(
    page.frameLocator(".route-map-panel iframe").locator("body"),
  ).toContainText(/\d+\s*(?:h|min|ч|мин)/i, { timeout: 30000 });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".sidebar")).not.toBeInViewport();
  await map.screenshot({
    path: "test-results/yandex-route-mobile.png",
    animations: "disabled",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  expect(mapRequests).toBe(0);
  expect(blockedFrames).toEqual([]);
});
