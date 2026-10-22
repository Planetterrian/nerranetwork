/**
 * Oct 22 2026 evidence: SSR consent banner + Accept/Reject persistence +
 * gcs G100→G111. Headed Chromium; fresh storage (no suite seed).
 */
import { expect, test, type Request } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

const ARTIFACT_DIR = path.resolve(__dirname, "../../.cursor/artifacts");

function isGoogleCollect(url: string): boolean {
  return (
    /google-analytics\.com\/g\/collect/.test(url) ||
    /analytics\.google\.com\/g\/collect/.test(url) ||
    /pagead2\.googlesyndication\.com\/.*\/ccm\/collect/.test(url) ||
    /googleadservices\.com\/.*\/ccm\/collect/.test(url) ||
    /\/ccm\/collect/.test(url)
  );
}

function gcsFromUrl(url: string): string | null {
  try {
    const u = new URL(url);
    return u.searchParams.get("gcs") || u.searchParams.get("gcd") || null;
  } catch {
    return null;
  }
}

test.describe("SSR consent lighthouse evidence", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("banner SSR on first visit; Accept/Reject persist; G100→G111", async ({
    page,
    context,
  }, testInfo) => {
    const collectHits: { url: string; gcs: string | null }[] = [];
    page.on("request", (req: Request) => {
      const url = req.url();
      if (isGoogleCollect(url)) {
        collectHits.push({ url, gcs: gcsFromUrl(url) });
      }
    });

    // Clear once before first paint — do NOT use addInitScript (it would
    // wipe the choice again on reload and falsely re-show the banner).
    await context.clearCookies();
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await page.evaluate(() => {
      try {
        localStorage.removeItem("nn_consent_v1");
      } catch {
        /* ignore */
      }
    });
    await page.reload({ waitUntil: "domcontentloaded" });

    // SSR node present in HTML; visible on first visit.
    const banner = page.locator("#nn-consent-banner");
    await expect(banner).toBeVisible({ timeout: 15_000 });
    const ssr = await banner.getAttribute("data-nn-consent-ssr");
    expect(ssr).toBe("1");
    await expect(page.locator(".nn-consent-text")).toBeVisible();

    // ---- Reject → G100, hidden on reload ----
    collectHits.length = 0;
    await page.locator('[data-nn-consent="reject-all"]').click();
    await page.waitForTimeout(2500);
    const rejectGcs = collectHits.map((h) => h.gcs).filter(Boolean);
    expect(
      rejectGcs.some((g) => g === "G100" || (g && g.includes("100"))),
      `expected G100 after reject, got ${JSON.stringify(rejectGcs)}`,
    ).toBeTruthy();
    await expect(banner).toBeHidden();

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.locator("#nn-consent-banner")).toBeHidden();
    const storedReject = await page.evaluate(() =>
      localStorage.getItem("nn_consent_v1"),
    );
    expect(storedReject).toBeTruthy();
    expect(storedReject).toMatch(/denied/);

    // ---- Accept → G111, hidden on reload ----
    await context.clearCookies();
    await page.evaluate(() => localStorage.removeItem("nn_consent_v1"));
    collectHits.length = 0;
    await page.goto("/personal-interest.html", { waitUntil: "domcontentloaded" });
    await expect(page.locator("#nn-consent-banner")).toBeVisible({
      timeout: 15_000,
    });
    await page.locator('[data-nn-consent="accept-all"]').click();
    await page.waitForTimeout(3500);
    const acceptGcs = collectHits.map((h) => h.gcs).filter(Boolean);
    expect(
      acceptGcs.some((g) => g === "G111" || (g && g.includes("111"))),
      `expected G111 after accept, got ${JSON.stringify(acceptGcs)}`,
    ).toBeTruthy();
    await expect(page.locator("#nn-consent-banner")).toBeHidden();

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.locator("#nn-consent-banner")).toBeHidden();
    const storedAccept = await page.evaluate(() =>
      localStorage.getItem("nn_consent_v1"),
    );
    expect(storedAccept).toMatch(/granted/);

    const evidence = {
      ssr_attribute: ssr,
      reject: { gcs_samples: rejectGcs.slice(0, 5), hidden_after_reload: true },
      accept: { gcs_samples: acceptGcs.slice(0, 5), hidden_after_reload: true },
    };
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
    const outPath = path.join(ARTIFACT_DIR, "consent-ssr-lighthouse-evidence.json");
    fs.writeFileSync(outPath, JSON.stringify(evidence, null, 2));
    await testInfo.attach("consent-ssr-lighthouse-evidence.json", {
      path: outPath,
      contentType: "application/json",
    });
    // also copy under opt artifacts
    fs.mkdirSync("/opt/cursor/artifacts/lighthouse-oct19", { recursive: true });
    fs.copyFileSync(
      outPath,
      "/opt/cursor/artifacts/lighthouse-oct19/consent-ssr-lighthouse-evidence.json",
    );
  });
});
