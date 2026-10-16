import { defineConfig, devices } from "@playwright/test";

/**
 * Serves the committed static site from the repo root and mocks
 * api.nerranetwork.com so CI never hits production Stripe, Buttondown,
 * or the gallery Worker.
 */
const PORT = 4173;
const BASE = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: BASE,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    // Same consent seed as scripts/capture_site_screens.py — no banner,
    // no analytics consent recorded by the robot.
    storageState: {
      cookies: [],
      origins: [
        {
          origin: BASE,
          localStorage: [
            {
              name: "nn_consent_v1",
              value: JSON.stringify({ state: "rejected", timestamp: Date.now() }),
            },
          ],
        },
      ],
    },
  },
  webServer: {
    command: `python3 -m http.server ${PORT} --bind 127.0.0.1`,
    cwd: "..",
    url: BASE,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
