import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";

const origin = process.env.SUBPATH_TEST_URL;
const accounts: string[] = [];
test.afterAll(() => {
  if (!accounts.length) return;
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
      `from django.contrib.auth import get_user_model; get_user_model().objects.filter(username__in=${JSON.stringify(accounts)}).delete()`,
    ],
    { cwd: "..", stdio: "pipe" },
  );
});

test("production subpath login, assets, language cookies and logout stay in logistics", async ({
  page,
  context,
}) => {
  test.skip(
    !origin,
    "Set SUBPATH_TEST_URL for a frontend built with /logistics",
  );
  const username = `yf_subpath_${Date.now()}`;
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
      `from django.contrib.auth import get_user_model; get_user_model().objects.create_user(username=${JSON.stringify(username)}, password="Subpath!StrongPass2026", role="driver")`,
    ],
    { cwd: "..", stdio: "pipe" },
  );
  accounts.push(username);
  const wrongRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (
      url.origin === origin &&
      (url.pathname.startsWith("/api/") ||
        url.pathname.startsWith("/_next/") ||
        url.pathname.startsWith("/images/"))
    )
      wrongRequests.push(url.pathname);
  });
  await page.goto(`${origin}/logistics/login/?next=/driver/tickets`);
  await page.getByLabel("Foydalanuvchi nomi", { exact: true }).fill(username);
  await page
    .getByLabel("Parol", { exact: true })
    .fill("Subpath!StrongPass2026");
  await page.getByRole("button", { name: "Kirish", exact: true }).click();
  await expect(page).toHaveURL(/\/logistics\/driver\/tickets\/$/);
  const auth = (await context.cookies()).filter((c) =>
    c.name.startsWith("yf_"),
  );
  expect(auth.find((c) => c.name === "yf_access")?.path).toBe("/logistics");
  expect(auth.find((c) => c.name === "yf_access")?.secure).toBe(true);
  await context.clearCookies({ name: "yf_access" });
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Avtomobillarim", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Avtomobillarim", exact: true })
    .click();
  await page.getByRole("button", { name: "S 0.3 t", exact: true }).click();
  await expect
    .poll(() =>
      page
        .locator(".vehicle-reference-image")
        .evaluate(
          (img) =>
            (img as HTMLImageElement).complete &&
            (img as HTMLImageElement).naturalWidth > 0,
        ),
    )
    .toBe(true);
  await page.getByLabel("Til / Язык").selectOption("ru");
  expect(
    (await context.cookies()).find((c) => c.name === "yf_locale")?.path,
  ).toBe("/logistics");
  await page.getByLabel("Til / Язык").selectOption("uz");
  expect(wrongRequests).toEqual([]);
  await page.getByRole("button", { name: /chiqish/i }).click();
  await expect(page).toHaveURL(`${origin}/logistics/`);
  expect(
    (await context.cookies()).some(
      (c) => c.name === "yf_access" || c.name === "yf_refresh",
    ),
  ).toBe(false);
});
