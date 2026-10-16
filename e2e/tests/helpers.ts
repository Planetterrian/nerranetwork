import type { Page, Route } from "@playwright/test";

/** Intercept gallery / personal Worker calls so CI never touches prod. */
export async function mockApi(page: Page): Promise<void> {
  await page.route("https://api.nerranetwork.com/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();

    if (path === "/api/subscribe" && method === "POST") {
      const body = route.request().postDataJSON() as { email?: string } | null;
      if (!body?.email || !String(body.email).includes("@")) {
        return route.fulfill({
          status: 400,
          contentType: "application/json",
          body: JSON.stringify({ ok: false, error: "email required" }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, alreadySubscribed: false }),
      });
    }

    if (path === "/api/login" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      });
    }

    if (path === "/api/account" && method === "GET") {
      // Signed-out by default — account page shows the login form.
      return route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ ok: false, error: "auth required" }),
      });
    }

    if (path === "/api/account/checkout-ref" && method === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, ref: "e2e-test-ref" }),
      });
    }

    if (path === "/api/logout" && method === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      });
    }

    // Default: empty ok so stray beacons (Plausible/gtag) do not fail the run.
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, mocked: true }),
    });
  });

  // Block third-party analytics so the suite stays offline-friendly.
  await page.route(/googletagmanager|google-analytics|plausible\.io/, (route) =>
    route.fulfill({ status: 204, body: "" }),
  );
}
