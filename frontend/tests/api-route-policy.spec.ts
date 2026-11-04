import { test, expect } from "@playwright/test";
import { isAllowedApiRoute } from "../src/lib/api-route-policy";

test("the frontend proxy allows the implemented city, ticket and load actions", () => {
  for (const route of [
    "cargo/cities",
    "cargo/loads",
    "cargo/loads/1",
    "cargo/loads/1/claim",
    "cargo/loads/1/map-locations",
    "driver/tickets",
    "driver/tickets/simple",
    "driver/tickets/1/simple",
    "driver/tickets/1/return-trip",
    "driver/notifications/1/dismiss",
    "auth/me",
    "partners/companies/1/members/2",
  ])
    expect(isAllowedApiRoute(route), route).toBe(true);
});

test("the frontend proxy rejects unrecognized actions and arbitrary backend paths", () => {
  for (const route of [
    "admin",
    "cargo/cities/delete",
    "cargo/loads/claim",
    "cargo/loads/1/delete-all",
    "driver/tickets/simple/1",
    "driver/tickets/1/simple/extra",
    "driver/tickets/../users",
    "auth/refresh",
    "partners/companies/1/members/2/other",
    "https://example.com",
    "cargo//loads",
    "",
  ])
    expect(isAllowedApiRoute(route), route).toBe(false);
});
