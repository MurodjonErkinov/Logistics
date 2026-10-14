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
      `from django.contrib.auth import get_user_model; from driver_notifications.models import Ticket, Vehicle; Ticket.objects.filter(owner__username__in=${names}).delete(); Vehicle.objects.filter(owner__username__in=${names}).delete(); get_user_model().objects.filter(username__in=${names}).delete()`,
    ],
    { cwd: "..", stdio: "pipe" },
  );
});

test("driver creates vehicle and multi-destination ticket, sees bell and manages settings", async ({
  page,
}) => {
  const username = `yf_notify_${Date.now()}`;
  accounts.push(username);
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
      `from django.contrib.auth import get_user_model; get_user_model().objects.create_user(username=${JSON.stringify(username)}, password="DriverE2E12345!", role="driver")`,
    ],
    { cwd: "..", stdio: "pipe" },
  );
  await page.goto("/login?next=/driver/tickets");
  await page.getByLabel("Foydalanuvchi nomi", { exact: true }).fill(username);
  await page.getByLabel("Parol", { exact: true }).fill("DriverE2E12345!");
  await page.getByRole("button", { name: "Kirish", exact: true }).click();
  await expect(page).toHaveURL(/\/driver\/tickets$/, { timeout: 15000 });
  await page
    .getByRole("button", { name: "Avtomobillarim", exact: true })
    .click();
  await page.getByLabel("Mashina nomi", { exact: true }).fill("Volvo test");
  await page.getByRole("button", { name: "FURA 20 t", exact: true }).click();
  await expect(page.getByLabel("Sig‘im (tonna)", { exact: true })).toHaveValue(
    "20",
  );
  await page.getByRole("button", { name: /Izotermik/ }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".vehicle-picker")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page
    .locator(".vehicle-picker")
    .screenshot({ path: "/tmp/vehicle-picker-mobile.png" });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole("button", { name: "Saqlash", exact: true }).click();
  await expect(
    page.locator(".ticket-card").getByRole("heading", { name: "Volvo test" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Tiket ochish", exact: true }).click();
  await page.getByLabel("Tiket nomi", { exact: true }).fill("Ikki yo‘nalish");
  const origins = page.getByRole("group", {
    name: "Yuklash joylari",
    exact: true,
  });
  await origins.getByLabel("Shahar 1", { exact: true }).fill("Toshkent");
  const destinations = page.getByRole("group", {
    name: "Boradigan manzillar",
    exact: true,
  });
  await destinations.getByLabel("Shahar 1", { exact: true }).fill("Samarqand");
  await destinations.getByRole("button", { name: "Manzil qo‘shish" }).click();
  await destinations.getByLabel("Shahar 2", { exact: true }).fill("Buxoro");
  await expect(page.getByLabel("Qachon xabar berilsin?")).toHaveValue(
    "any_two",
  );
  await page.getByRole("button", { name: "Tiketni saqlash" }).click();
  await expect(
    page
      .locator(".ticket-card")
      .getByRole("heading", { name: "Ikki yo‘nalish" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Pauza", exact: true }).click();
  await expect(page.locator(".ticket-card .status-chip")).toHaveText("Pauzada");
  await page
    .getByRole("button", { name: "Qaytish tiketi", exact: true })
    .click();
  await expect(page.locator(".ticket-card")).toHaveCount(2);
  await page
    .getByRole("button", { name: "Xabar sozlamalari", exact: true })
    .click();
  await page.getByLabel("Qisman mos yuklarni jamlash").selectOption("15");
  await page.getByLabel("Tinch vaqt boshlanishi").fill("22:00");
  await page.getByLabel("Tinch vaqt tugashi").fill("07:00");
  await page.getByRole("button", { name: "Saqlash", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Saqlandi");
  await page.reload();
  await page
    .getByRole("button", { name: "Xabar sozlamalari", exact: true })
    .click();
  await expect(page.getByLabel("Tinch vaqt boshlanishi")).toHaveValue("22:00");
  await page.getByLabel("Til / Язык").selectOption("ru");
  await expect(
    page.getByRole("heading", { name: "Пусть груз найдёт вас" }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/driver-notifications-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.goto("/notifications");
  await expect(
    page.getByRole("heading", { name: "Уведомления", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".notification-bell")).toBeVisible();
});

test("notification explains all checks, read and dismiss update bell", async ({
  page,
}) => {
  const user = {
    id: 123,
    username: "driver",
    first_name: "Sardor",
    role: "driver",
    is_staff: false,
  };
  let dismissed = false;
  let read = false;
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: user }));
  await page.route("**/api/auth/me/", (route) => route.fulfill({ json: user }));
  await page.route("**/api/driver/notifications/**", (route) => {
    const url = route.request().url();
    if (url.includes("unread"))
      return route.fulfill({ json: { count: read ? 0 : 1 } });
    if (route.request().method() === "POST") {
      read = true;
      if (url.includes("dismiss")) dismissed = true;
      return route.fulfill({ json: { ok: true } });
    }
    return route.fulfill({
      json: {
        count: 1,
        results: [
          {
            id: 1,
            ticket: 1,
            ticket_title: "Toshkent",
            load: 12,
            kind: "match",
            level: "partial",
            snapshot: {
              load_id: 12,
              origin: "Toshkent",
              destination: "Buxoro",
              cargo_name: "Sement",
              weight_tons: "25",
              phone: "+998900000001",
              price: "3000000",
              currency: "UZS",
            },
            reasons: {
              checks: {
                route: true,
                vehicle: true,
                capacity: false,
                time: null,
                price: false,
              },
            },
            read_at: read ? new Date().toISOString() : null,
            created_at: new Date().toISOString(),
            obsolete: dismissed,
            sent_at: null,
            delivery_error: "",
          },
        ],
      },
    });
  });
  await page.goto("/notifications");
  await expect(page.getByText("✕ Sig‘im", { exact: true })).toBeVisible();
  await expect(page.getByText("? Vaqt", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Mos emas", exact: true }).click();
  await expect(
    page.getByText("Yuk yoki moslik eskirgan", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".notification-bell")).toHaveAttribute(
    "aria-label",
    "Bildirishnomalar: 0",
  );
});
