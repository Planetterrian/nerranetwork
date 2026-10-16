import { expect, test } from "@playwright/test";
import { mockApi } from "./helpers";

test.describe("Subscribe and join (mocked API)", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
  });

  test("join page shows pricing and Stripe checkout links", async ({ page }) => {
    await page.goto("/join.html");
    await expect(page.getByRole("heading", { name: /Simple, honest pricing/i })).toBeVisible();
    await expect(page.getByText("$4.99").first()).toBeVisible();
    await expect(page.getByText("$8.99").first()).toBeVisible();

    // Payments: live Payment Links only — we assert they are Stripe host
    // URLs and do NOT complete a real charge (test mode / Payment Link).
    const personal = page.locator('a.cta[href*="buy.stripe.com"]').first();
    await expect(personal).toBeVisible();
    const href = await personal.getAttribute("href");
    expect(href).toMatch(/^https:\/\/buy\.stripe\.com\//);
  });

  test("free-account subscribe form posts to mocked Worker", async ({ page }) => {
    await page.goto("/join.html#join-free");
    const form = page.locator('form[data-nn-subscribe="join"]');
    await expect(form).toBeVisible();

    const email = form.locator('input[name=email], input[type=email]');
    await email.fill("e2e-test@example.com");

    // Pick a show tag if the form requires one.
    const firstTag = form.locator('input[name=tag]').first();
    if (await firstTag.count()) {
      await firstTag.check({ force: true }).catch(() => undefined);
    }

    const [request] = await Promise.all([
      page.waitForRequest(
        (r) =>
          r.url().includes("/api/subscribe") && r.method() === "POST",
      ),
      form.locator('button[type=submit], button:not([type])').first().click(),
    ]);

    const payload = request.postDataJSON() as { email?: string };
    expect(payload.email).toBe("e2e-test@example.com");
  });

  test("account page login requests a magic link via mocked API", async ({ page }) => {
    await page.goto("/account.html");
    // Guest form is revealed after the mocked /api/account 401.
    const guest = page.locator("#nn-guest");
    await expect(guest).toBeVisible({ timeout: 15_000 });
    const email = guest.locator('input[type=email], input[name=email]').first();
    await email.fill("member@example.com");

    const [request] = await Promise.all([
      page.waitForRequest(
        (r) => r.url().includes("/api/login") && r.method() === "GET",
      ),
      guest.locator("form button").first().click(),
    ]);

    expect(request.url()).toContain("email=member%40example.com");
  });
});
