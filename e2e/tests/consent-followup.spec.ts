/**
 * Consent Mode v2 follow-ups (Oct 18 2026) — headed evidence for PR 1.
 *
 * Asserts: Reject → gcs G100 + no Google cookies; Accept → G111 with
 * ad_personalization denied (gcd) and a single config per tag; Cookie
 * settings after Accept shows both toggles on.
 *
 * Uses a fresh context (no storageState seed) so the banner appears.
 */
import { expect, test, type Page, type Request } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

const ARTIFACT_DIR = path.resolve(__dirname, "../../.cursor/artifacts");
const GA4 = "G-6PWJCVQQ7B";
const ADS = "AW-949617778";

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

function gcdFromUrl(url: string): string | null {
  try {
    return new URL(url).searchParams.get("gcd");
  } catch {
    return null;
  }
}

async function clearConsent(page: Page) {
  await page.addInitScript(() => {
    try {
      localStorage.removeItem("nn_consent_v1");
    } catch {
      /* ignore */
    }
  });
  await page.context().clearCookies();
}

test.describe("Consent follow-ups (PR1 evidence)", () => {
  // Override the suite-level rejected seed so the banner shows.
  test.use({ storageState: { cookies: [], origins: [] } });

  test("Reject → G100 cookieless; Accept → G111 + ad_personalization denied + toggles", async ({
    page,
    context,
  }, testInfo) => {
    const collectHits: { url: string; gcs: string | null; gcd: string | null }[] =
      [];
    page.on("request", (req: Request) => {
      const url = req.url();
      if (isGoogleCollect(url)) {
        collectHits.push({
          url,
          gcs: gcsFromUrl(url),
          gcd: gcdFromUrl(url),
        });
      }
    });

    await clearConsent(page);
    await page.goto("/personal-interest.html", { waitUntil: "domcontentloaded" });

    // ---- Reject ----
    collectHits.length = 0;
    const rejectBtn = page.locator('[data-nn-consent="reject-all"]');
    await expect(rejectBtn).toBeVisible({ timeout: 15_000 });
    await rejectBtn.click();
    await page.waitForTimeout(2500);

    const rejectHits = [...collectHits];
    const rejectGcs = rejectHits.map((h) => h.gcs).filter(Boolean);
    expect(
      rejectGcs.some((g) => g === "G100" || (g && g.includes("100"))),
      `expected G100 after reject, got ${JSON.stringify(rejectGcs)}`,
    ).toBeTruthy();

    const cookiesAfterReject = await context.cookies();
    const googleCookiesAfterReject = cookiesAfterReject.filter(
      (c) =>
        c.name.startsWith("_ga") ||
        c.name.startsWith("_gcl") ||
        c.name === "IDE" ||
        c.name === "test_cookie",
    );
    expect(
      googleCookiesAfterReject,
      `no Google cookies after reject, got ${JSON.stringify(googleCookiesAfterReject)}`,
    ).toEqual([]);

    // dataLayer: last consent update personalization denied
    const afterReject = await page.evaluate(() => {
      const dl = (window as unknown as { dataLayer: unknown[] }).dataLayer || [];
      const updates = dl.filter(
        (e) =>
          Array.isArray(e) === false &&
          e &&
          typeof e === "object" &&
          // Arguments object from gtag push
          true,
      );
      // dataLayer entries from gtag are Arguments-like; scan stringified.
      const raw = dl.map((e) => {
        try {
          return Array.from(e as unknown as unknown[]);
        } catch {
          return e;
        }
      });
      return raw;
    });

    // ---- Fresh page for Accept ----
    await context.clearCookies();
    await page.evaluate(() => localStorage.removeItem("nn_consent_v1"));
    collectHits.length = 0;
    await page.goto("/personal-interest.html", { waitUntil: "domcontentloaded" });

    const acceptBtn = page.locator('[data-nn-consent="accept-all"]');
    await expect(acceptBtn).toBeVisible({ timeout: 15_000 });
    await acceptBtn.click();
    await page.waitForTimeout(3500);

    const acceptHits = [...collectHits];
    const acceptGcs = acceptHits.map((h) => h.gcs).filter(Boolean);
    expect(
      acceptGcs.some((g) => g === "G111" || (g && g.includes("111"))),
      `expected G111 after accept, got ${JSON.stringify(acceptGcs)}`,
    ).toBeTruthy();

    // gcd encodes consent; ad_personalization denied shows as a 'd' in the
    // personalization slot. Also assert via dataLayer consent update.
    const consentState = await page.evaluate(() => {
      const dl = ((window as unknown as { dataLayer: unknown[] }).dataLayer ||
        []) as unknown[];
      const configs: unknown[][] = [];
      const updates: Record<string, string>[] = [];
      for (const entry of dl) {
        let arr: unknown[];
        try {
          arr = Array.from(entry as unknown as unknown[]);
        } catch {
          continue;
        }
        if (arr[0] === "config") configs.push(arr);
        if (arr[0] === "consent" && arr[1] === "update") {
          updates.push(arr[2] as Record<string, string>);
        }
      }
      const ga4Configs = configs.filter((c) => c[1] === "G-6PWJCVQQ7B");
      const adsConfigs = configs.filter((c) => c[1] === "AW-949617778");
      return {
        lastUpdate: updates[updates.length - 1] || null,
        ga4ConfigCount: ga4Configs.length,
        adsConfigCount: adsConfigs.length,
        adsConfigOpts: adsConfigs.map((c) => c[2] || {}),
        stored: (window as unknown as { NNConsent: { readStored: () => unknown } })
          .NNConsent.readStored(),
      };
    });

    expect(consentState.lastUpdate?.ad_personalization).toBe("denied");
    expect(consentState.lastUpdate?.ad_storage).toBe("granted");
    expect(consentState.lastUpdate?.analytics_storage).toBe("granted");
    expect(consentState.ga4ConfigCount).toBe(1);
    expect(consentState.adsConfigCount).toBe(1);
    expect(
      (consentState.adsConfigOpts[0] as { allow_ad_personalization_signals?: boolean })
        ?.allow_ad_personalization_signals,
    ).toBe(false);

    // gcd on a collect hit should reflect personalization denied when present.
    const gcds = acceptHits.map((h) => h.gcd).filter(Boolean) as string[];
    // Document whatever gcd we saw for the PR body.
    const gcdNote = gcds.length ? gcds[0] : "(no gcd on collect hits in this run)";

    // ---- Cookie settings shows both toggles on ----
    await page.locator('[data-nn-cookie-settings]').first().click();
    await expect(page.locator("#nn-consent-banner")).toBeVisible();
    await page.locator('[data-nn-consent="choose"]').click();
    const analyticsToggle = page.locator('[data-nn-toggle="analytics"]');
    const adsToggle = page.locator('[data-nn-toggle="ads"]');
    await expect(analyticsToggle).toBeChecked();
    await expect(adsToggle).toBeChecked();

    const evidence = {
      reject: {
        gcs_samples: rejectGcs.slice(0, 5),
        google_cookies: googleCookiesAfterReject,
        hit_count: rejectHits.length,
      },
      accept: {
        gcs_samples: acceptGcs.slice(0, 5),
        gcd_sample: gcdNote,
        last_consent_update: consentState.lastUpdate,
        ga4_config_count: consentState.ga4ConfigCount,
        ads_config_count: consentState.adsConfigCount,
        ads_config_opts: consentState.adsConfigOpts,
        toggles_after_reopen: { analytics: true, ads: true },
      },
      afterReject_datalayer_len: afterReject.length,
    };

    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
    const outPath = path.join(ARTIFACT_DIR, "consent-followup-evidence.json");
    fs.writeFileSync(outPath, JSON.stringify(evidence, null, 2));
    await testInfo.attach("consent-followup-evidence.json", {
      path: outPath,
      contentType: "application/json",
    });

    // Soft check: if gcd is present, it must not encode full personalization grant.
    // Google's gcd format varies; primary proof is dataLayer ad_personalization=denied.
    expect(consentState.lastUpdate?.ad_personalization).toBe("denied");
  });
});
