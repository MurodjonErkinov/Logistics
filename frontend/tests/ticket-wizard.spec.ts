import { test, expect, type Page } from "@playwright/test";
import type { Place, Ticket, Vehicle } from "../src/lib/driver-types";

type Draft = {
  title: string;
  vehicle: number;
  origins: Place[];
  destinations: Place[];
  route_mode: string;
};
const berlin = {
  id: "N:1",
  name: "Berlin",
  description: "Germany",
  lat: 52.52,
  lon: 13.405,
};
const paris = {
  id: "N:2",
  name: "Paris",
  description: "France",
  lat: 48.85,
  lon: 2.35,
};
const volvo = {
  id: 10,
  name: "Volvo",
  kind: "tent",
  capacity_tons: "20",
  volume_m3: null,
  plate: "",
};

async function setup(page: Page, hasVehicle = true) {
  const state = {
    vehicles: hasVehicle ? ([volvo] as Vehicle[]) : [],
    tickets: [] as Ticket[],
    saves: [] as Draft[],
    failNext: false,
  };
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/$/, "");
    const method = route.request().method();
    if (path.endsWith("/auth/me"))
      return route.fulfill({
        json: {
          id: 1,
          username: "driver",
          first_name: "Sardor",
          role: "driver",
          is_staff: false,
        },
      });
    if (path.endsWith("/cargo/cities"))
      return route.fulfill({
        json: [url.searchParams.get("q")?.startsWith("Par") ? paris : berlin],
      });
    if (path.endsWith("/driver/vehicles")) {
      if (method === "POST") {
        const created = { ...volvo, ...route.request().postDataJSON(), id: 11 };
        state.vehicles.push(created);
        return route.fulfill({ status: 201, json: created });
      }
      return route.fulfill({ json: state.vehicles });
    }
    if (path.endsWith("/driver/preferences"))
      return route.fulfill({
        json: {
          language: "uz",
          timezone: "Asia/Tashkent",
          partial_interval_minutes: 30,
          telegram_enabled: true,
        },
      });
    if (path.endsWith("/driver/tickets"))
      return route.fulfill({ json: state.tickets });
    if (/\/driver\/tickets\/(\d+\/)?simple$/.test(path)) {
      if (state.failNext) {
        state.failNext = false;
        return route.fulfill({
          status: 500,
          json: { detail: "Qayta urinib ko‘ring." },
        });
      }
      const draft = route.request().postDataJSON() as Draft;
      state.saves.push(draft);
      const id =
        method === "PATCH"
          ? Number(path.match(/tickets\/(\d+)/)?.[1])
          : state.tickets.length + 1;
      const ticket: Ticket = {
        ...draft,
        id,
        vehicle_name:
          state.vehicles.find((v) => v.id === draft.vehicle)?.name || "",
        status: "active",
        current_location: draft.origins[0],
        waypoints: [],
        ready_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
        available_tons: "20",
        partial_load: false,
        min_price: "0",
        currency: "UZS",
        price_basis: "trip",
        match_mode: "route",
        notes: "",
      };
      state.tickets = [...state.tickets.filter((t) => t.id !== id), ticket];
      return route.fulfill({
        status: method === "POST" ? 201 : 200,
        json: ticket,
      });
    }
    return route.fulfill({ json: { count: 0 } });
  });
  await page.goto("/driver/tickets", { waitUntil: "domcontentloaded" });
  return state;
}

async function start(page: Page, title: string) {
  await page.getByRole("button", { name: "Tiket ochish", exact: true }).click();
  await page.getByLabel("Tiket nomi", { exact: true }).fill(title);
  await page.getByRole("button", { name: "Davom etish", exact: true }).click();
}
async function city(page: Page, query: string, name: string) {
  await page.getByRole("combobox", { name: "Shahar", exact: true }).fill(query);
  await page.getByRole("option", { name: new RegExp(name) }).click();
}

test("four short steps save multiple cities, preserve back navigation and refresh bot-created tickets", async ({
  page,
}) => {
  const state = await setup(page);
  await start(page, "Yevropa yo‘nalishim");
  await page
    .locator(".simple-ticket-vehicles")
    .getByRole("button", { name: /Volvo/ })
    .click();
  await city(page, "Ber", "Berlin");
  await page
    .getByRole("button", { name: "Manzil qo‘shish", exact: true })
    .click();
  await city(page, "Par", "Paris");
  await page.getByRole("button", { name: "Davom etish", exact: true }).click();
  await city(page, "Par", "Paris");
  await page.getByRole("button", { name: "Orqaga", exact: true }).click();
  await expect(page.locator(".simple-ticket-picked")).toContainText("Berlin");
  await expect(page.locator(".simple-ticket-picked")).toContainText("Paris");
  await page.getByRole("button", { name: "Davom etish", exact: true }).click();
  await expect(page.locator(".simple-ticket-picked")).toContainText("Paris");
  await expect(page.locator(".simple-ticket-steps li")).toHaveCount(4);
  await expect(page.getByLabel("Tayyor vaqt", { exact: true })).toHaveCount(0);
  await page.screenshot({
    path: "test-results/ticket-wizard-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".sidebar")).not.toBeInViewport();
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/ticket-wizard-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: "Tiketni ochish", exact: true })
    .click();
  await expect(
    page
      .locator(".ticket-card")
      .getByRole("heading", { name: "Yevropa yo‘nalishim", exact: true }),
  ).toBeVisible();
  expect(state.saves).toHaveLength(1);
  expect(state.saves[0].origins.map((p) => p.name)).toEqual([
    "Berlin",
    "Paris",
  ]);
  expect(state.saves[0].destinations.map((p) => p.name)).toEqual(["Paris"]);
  expect(Object.keys(state.saves[0]).sort()).toEqual([
    "destinations",
    "origins",
    "route_mode",
    "title",
    "vehicle",
  ]);
  state.tickets.push({
    ...state.tickets[0],
    id: 2,
    title: "Telegram botdan tiket",
  });
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(
    page
      .locator(".ticket-card")
      .getByRole("heading", { name: "Telegram botdan tiket", exact: true }),
  ).toBeVisible();
  await page
    .locator(".ticket-card")
    .filter({
      has: page.getByRole("heading", {
        name: "Yevropa yo‘nalishim",
        exact: true,
      }),
    })
    .getByRole("button", { name: "Tahrirlash", exact: true })
    .click();
  await expect(page.getByLabel("Tiket nomi", { exact: true })).toHaveValue(
    "Yevropa yo‘nalishim",
  );
});

test("any destination completes immediately and a failed save can be retried", async ({
  page,
}) => {
  const state = await setup(page);
  await start(page, "Istalgan yo‘nalish");
  await page
    .locator(".simple-ticket-vehicles")
    .getByRole("button", { name: /Volvo/ })
    .click();
  await page.getByRole("button", { name: "Davom etish", exact: true }).click();
  await expect(
    page.locator(".simple-ticket-wizard").getByRole("alert"),
  ).toContainText("Kamida bitta");
  await city(page, "Ber", "Berlin");
  await page.getByRole("button", { name: "Davom etish", exact: true }).click();
  state.failNext = true;
  await page.getByRole("button", { name: /Istalgan manzil/ }).click();
  await expect(
    page.locator(".simple-ticket-wizard").getByRole("alert"),
  ).toContainText("Qayta urinib");
  await page.getByRole("button", { name: /Istalgan manzil/ }).click();
  await expect(
    page
      .locator(".ticket-card")
      .getByRole("heading", { name: "Istalgan yo‘nalish", exact: true }),
  ).toBeVisible();
  expect(state.saves).toHaveLength(1);
  expect(state.saves[0].route_mode).toBe("anywhere");
  expect(state.saves[0].destinations).toEqual([]);
});

test("adding a first vehicle resumes the existing ticket at the city step", async ({
  page,
}) => {
  const state = await setup(page, false);
  await start(page, "Birinchi tiketim");
  await page
    .locator(".simple-ticket-wizard")
    .getByRole("button", { name: "Mashina qo‘shish", exact: true })
    .click();
  await page.getByLabel("Mashina nomi", { exact: true }).fill("Isuzu");
  await page.getByLabel("Sig‘im (tonna)", { exact: true }).fill("4");
  await page.getByRole("button", { name: "Saqlash", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Qayerdan yuk olasiz?", exact: true }),
  ).toBeVisible();
  await city(page, "Ber", "Berlin");
  await page.getByRole("button", { name: "Davom etish", exact: true }).click();
  await page.getByRole("button", { name: /Istalgan manzil/ }).click();
  await expect(
    page
      .locator(".ticket-card")
      .getByRole("heading", { name: "Birinchi tiketim", exact: true }),
  ).toBeVisible();
  expect(state.saves[0].vehicle).toBe(11);
});
