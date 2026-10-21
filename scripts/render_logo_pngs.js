#!/usr/bin/env node
/*
 * Render the network's wordmark SVGs to PNG with the bundled DM Sans.
 *
 * Oct 21 2026 (the media kit). The logo SVGs set their words as live text in
 * DM Sans. Inside an <img>, or on a publicist's computer without the font,
 * they fall back to Arial and the wordmark spills past its frame. These PNGs
 * are what the press page previews and what the brand zip carries beside the
 * SVGs, so a logo looks right wherever it lands.
 *
 * Run after a logo changes:  node scripts/render_logo_pngs.js
 * Needs Playwright (globally installed in the cloud container and on the
 * operator's machine); the site build never runs it, it reads the PNGs.
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

let playwright;
try { playwright = require("playwright"); }
catch (e) { playwright = require(execSync("npm root -g").toString().trim() + "/playwright"); }

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "assets", "press");
// Every logo the media kit lists (generate_html.MEDIA_KIT_LOGOS), rendered
// at least 1200 px wide (at least 2x), which is print-ready for a publicist.
const LOGOS = [
  "nerra-logo-horizontal.svg", "nerra-logo-horizontal-light.svg",
  "nerra-logo-stacked.svg", "nerra-logo-icon.svg", "nerra-mark-mono.svg",
  "age-of-ai-logo.svg", "nerra-voices-logo.svg",
];
const MIN_WIDTH = 1200;

const font = (file, weight) => `@font-face { font-family: 'DM Sans'; font-weight: ${weight};
  src: url(data:font/ttf;base64,${fs.readFileSync(path.join(ROOT, "assets", "fonts", file)).toString("base64")}); }`;

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await playwright.chromium.launch();
  for (const name of LOGOS) {
    const svg = fs.readFileSync(path.join(ROOT, "assets", name), "utf8");
    const vb = (svg.match(/viewBox="([^"]+)"/) || [])[1];
    if (!vb) { console.warn(`skip ${name}: no viewBox`); continue; }
    const [, , w, h] = vb.split(/\s+/).map(Number);
    const scale = Math.max(2, Math.ceil(MIN_WIDTH / w));
    const page = await browser.newPage({ viewport: { width: Math.ceil(w), height: Math.ceil(h) },
                                         deviceScaleFactor: scale });
    await page.setContent(`<!doctype html><html><head><style>
      ${font("DMSans-Medium.ttf", "400 500")} ${font("DMSans-Bold.ttf", "600 800")}
      html, body { margin: 0; background: transparent; }
      svg { display: block; width: ${w}px; height: ${h}px; }
    </style></head><body>${svg.replace(/<\?xml[^>]*>/, "")}</body></html>`);
    await page.evaluate(() => document.fonts.ready);
    const out = path.join(OUT, name.replace(/\.svg$/, ".png"));
    await page.locator("svg").first().screenshot({ path: out, omitBackground: true });
    console.log(`wrote ${path.relative(ROOT, out)} (${Math.ceil(w) * scale}x${Math.ceil(h) * scale})`);
    await page.close();
  }
  await browser.close();
})();
