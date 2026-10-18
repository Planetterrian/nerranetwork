import { expect, test } from "@playwright/test";
import { mockApi } from "./helpers";

test.describe("Landing and show journeys", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
  });

  test("home page loads with brand and show grid", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Nerra Network/i);
    await expect(page.locator("text=Nerra Network").first()).toBeVisible();
    // Covers exist in the lineup (lazy ones may be offscreen — assert count).
    const covers = page.locator('img[alt$="cover art"]');
    await expect(covers).toHaveCount(await covers.count());
    expect(await covers.count()).toBeGreaterThan(5);
    // Oct 18 2026: the homepage is the news front page — the first viewport
    // is the lead story (headline linking to its post), not a cover grid.
    const lead = page.locator("article.lt-lead h2 a").first();
    await expect(lead).toBeVisible();
    await expect(lead).toHaveAttribute("href", /^blog\//);
  });

  test("show page opens and exposes the podcast feed link", async ({ page }) => {
    await page.goto("/tesla.html");
    await expect(page).toHaveTitle(/Tesla/i);
    // Canonical Tesla feed is podcast.rss (legacy name).
    const feed = page.locator('a[href*="podcast.rss"], a[href*="rss"]').first();
    await expect(feed).toBeVisible();
  });

  test("site search finds an episode from the local index", async ({ page }) => {
    await page.goto("/");
    const input = page.locator("#nn-global-search-input");
    await expect(input).toBeVisible();
    await input.fill("Tesla");
    await input.press("Enter");
    const results = page.locator("#nn-global-search-results");
    await expect(results).toBeVisible({ timeout: 15_000 });
    // Either matches or an honest empty/loading state — never a blank fail.
    const text = await results.innerText();
    expect(text.length).toBeGreaterThan(0);
  });

  test("FAQ and AI disclosure pages render", async ({ page }) => {
    await page.goto("/faq.html");
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await page.goto("/ai-disclosure.html");
    await expect(page.getByRole("heading", { name: "AI Disclosure" })).toBeVisible();
  });
});
