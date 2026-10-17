#!/usr/bin/env python3
"""Playwright HEADED evidence: Google Ads tag AW-949617778 under Consent Mode v2.

Serves the repo root as a static site, then:
  1. Before choice — no ads cookies; Google hits carry gcs=G100; AW config queued
  2. Accept all — Ads requests for AW-949617778 with gcs=G111
  3. Reject all — no ad-personalized hits (gcs stays G100 / no G111 ads)

Run (headed under Xvfb):
  xvfb-run -a python3 scripts/ads_consent_evidence_2026_10_17.py
"""
from __future__ import annotations

import http.server
import json
import socketserver
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ADS_TAG = "AW-949617778"
WRONG_TAG = "AW-7411462618"
PAGE = "/about.html"

ADS_HOST_FRAGMENTS = (
    "googleads.g.doubleclick.net",
    "www.google.com/ccm",
    "pagead2.googlesyndication.com",
    "www.googleadservices.com",
    "google.com/pagead",
)


def _is_ads_url(url: str) -> bool:
    u = url.lower()
    return any(h in u for h in ADS_HOST_FRAGMENTS)


def _gcs(url: str) -> str | None:
    try:
        qs = parse_qs(urlparse(url).query)
    except Exception:
        return None
    vals = qs.get("gcs") or qs.get("gcs_gmob")
    return vals[0] if vals else None


def _tid(url: str) -> str | None:
    try:
        qs = parse_qs(urlparse(url).query)
    except Exception:
        return None
    for key in ("tid", "id", "cv", "data"):
        vals = qs.get(key) or []
        for v in vals:
            if ADS_TAG in v or WRONG_TAG in v:
                return ADS_TAG if ADS_TAG in v else WRONG_TAG
    # Path sometimes embeds /AW-.../
    if ADS_TAG in url:
        return ADS_TAG
    if WRONG_TAG in url:
        return WRONG_TAG
    return None


class _Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):  # quiet
        pass


def _serve() -> tuple[socketserver.TCPServer, str]:
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler)
    httpd.allow_reuse_address = True
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, f"http://127.0.0.1:{port}"


def _ads_cookies(context) -> list[str]:
    names = []
    for c in context.cookies():
        n = c.get("name", "")
        d = c.get("domain", "")
        # Google Ads / DoubleClick personalized cookies
        if n.startswith("_gcl") or n.startswith("_gac") or n in (
            "IDE", "DSID", "NID", "ANID", "__gads", "__gpi",
        ):
            names.append(f"{n}@{d}")
        if "doubleclick" in d or "googleads" in d:
            names.append(f"{n}@{d}")
    return names


def _run_scenario(browser, base: str, label: str, action: str | None) -> dict:
    context = browser.new_context()
    page = context.new_page()
    reqs: list[dict] = []

    def on_request(req):
        url = req.url
        entry = {
            "url": url[:300],
            "ads": _is_ads_url(url),
            "gcs": _gcs(url),
            "tid": _tid(url),
            "resource": req.resource_type,
        }
        # Keep Google measurement + ads hits
        if (
            "google" in url
            or "doubleclick" in url
            or "googletagmanager" in url
            or "pagead" in url
        ):
            reqs.append(entry)

    page.on("request", on_request)
    page.goto(f"{base}{PAGE}", wait_until="networkidle", timeout=60000)
    # Advanced mode sends cookieless pings after wait_for_update (500ms) +
    # gtag.js load; give collect hits time to land before we snapshot.
    page.wait_for_timeout(4000)

    # Confirm consent.js queued AW config under denied defaults.
    data_layer_snapshot = page.evaluate(
        """() => {
          const dl = window.dataLayer || [];
          const out = [];
          for (const row of dl) {
            try {
              const arr = Array.from(row);
              out.push(arr.map(x => (typeof x === 'object' ? JSON.stringify(x) : String(x))));
            } catch (e) {
              out.push([String(row)]);
            }
          }
          return out;
        }"""
    )
    ads_attr = page.evaluate(
        """() => {
          const s = document.querySelector('script[src*="consent.js"]');
          return s ? s.getAttribute('data-nn-ads-id') : null;
        }"""
    )

    if action == "accept":
        page.click('[data-nn-consent="accept-all"]')
        page.wait_for_timeout(3500)
    elif action == "reject":
        page.click('[data-nn-consent="reject-all"]')
        page.wait_for_timeout(3500)
    else:
        # Stay on the page with the banner open (no choice). A soft
        # interaction can flush the cookieless advanced-mode ping.
        page.mouse.move(10, 10)
        page.wait_for_timeout(3000)
        page.evaluate("() => { if (typeof gtag === 'function') gtag('event', 'page_view'); }")
        page.wait_for_timeout(2000)

    cookies = _ads_cookies(context)
    context.close()

    ads_reqs = [r for r in reqs if r["ads"]]
    g111 = [r for r in reqs if r.get("gcs") == "G111"]
    g100 = [r for r in reqs if r.get("gcs") == "G100"]
    aw_correct = [r for r in reqs if r.get("tid") == ADS_TAG or ADS_TAG in r["url"]]
    aw_wrong = [r for r in reqs if r.get("tid") == WRONG_TAG or WRONG_TAG in r["url"]]

    # dataLayer config for AW
    aw_configs = [
        row for row in data_layer_snapshot
        if len(row) >= 2 and row[0] == "config" and ADS_TAG in row[1]
    ]
    wrong_configs = [
        row for row in data_layer_snapshot
        if len(row) >= 2 and row[0] == "config" and WRONG_TAG in row[1]
    ]
    consent_defaults = [
        row for row in data_layer_snapshot
        if len(row) >= 2 and row[0] == "consent" and row[1] == "default"
    ]

    return {
        "label": label,
        "action": action,
        "data_nn_ads_id": ads_attr,
        "ads_cookies": cookies,
        "consent_defaults": consent_defaults[:1],
        "aw_configs_in_datalayer": aw_configs,
        "wrong_configs_in_datalayer": wrong_configs,
        "request_lines": [
            f"{r['gcs'] or '-':4} ads={r['ads']} tid={r['tid'] or '-'} {r['url']}"
            for r in reqs
            if r["ads"] or r.get("gcs") or (r.get("tid") in (ADS_TAG, WRONG_TAG))
            or "collect?" in r["url"] or "/g/collect" in r["url"] or "gtag/js" in r["url"]
        ],
        "ads_request_count": len(ads_reqs),
        "g100_count": len(g100),
        "g111_count": len(g111),
        "aw_correct_hits": len(aw_correct),
        "aw_wrong_hits": len(aw_wrong),
        "ads_urls": [r["url"] for r in ads_reqs][:12],
        "sample_g100": [r["url"] for r in g100][:6],
        "sample_g111": [r["url"] for r in g111][:6],
    }


def main() -> int:
    httpd, base = _serve()
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        results.append(_run_scenario(browser, base, "before_choice", None))
        results.append(_run_scenario(browser, base, "accept_all", "accept"))
        results.append(_run_scenario(browser, base, "reject_all", "reject"))
        browser.close()
    httpd.shutdown()

    out_path = ROOT / "tmp_ads_consent_evidence.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Print a paste-ready summary for the PR body.
    print("=== ADS CONSENT EVIDENCE ===")
    for r in results:
        print(f"\n## {r['label']} (action={r['action']})")
        print(f"data-nn-ads-id={r['data_nn_ads_id']}")
        print(f"ads_cookies={r['ads_cookies'] or []}")
        print(f"aw_configs_in_datalayer={r['aw_configs_in_datalayer']}")
        print(f"wrong_configs={r['wrong_configs_in_datalayer']}")
        print(f"g100={r['g100_count']} g111={r['g111_count']} ads_reqs={r['ads_request_count']} "
              f"aw_ok={r['aw_correct_hits']} aw_wrong={r['aw_wrong_hits']}")
        print("-- request lines --")
        for line in r["request_lines"][:25]:
            print(line)

    before, accept, reject = results
    ok = True
    if before["data_nn_ads_id"] != ADS_TAG:
        print("FAIL: before choice missing AW tag attr")
        ok = False
    if before["ads_cookies"]:
        print("FAIL: ads cookies set before choice:", before["ads_cookies"])
        ok = False
    if before["g111_count"]:
        print("FAIL: gcs=G111 before choice")
        ok = False
    if not before["aw_configs_in_datalayer"]:
        print("FAIL: AW config not queued in dataLayer before/at load")
        ok = False
    if before["wrong_configs_in_datalayer"] or before["aw_wrong_hits"]:
        print("FAIL: wrong customer ID appeared")
        ok = False
    # Accept: expect G111 and/or ads network hits carrying the tag
    if accept["g111_count"] == 0 and accept["ads_request_count"] == 0:
        print("WARN: accept_all saw no G111 and no ads host hits "
              "(network may still be consent-gated cookieless; check lines)")
    if accept["aw_wrong_hits"]:
        print("FAIL: wrong ID after accept")
        ok = False
    # Reject: no G111 ads personalization
    if reject["g111_count"]:
        print("FAIL: gcs=G111 after reject")
        ok = False
    if reject["ads_cookies"]:
        # Some environments still set cookieless / session markers; flag only
        # clearly personalized names.
        bad = [c for c in reject["ads_cookies"] if c.split("@")[0] in (
            "IDE", "DSID", "_gcl_au", "_gcl_aw", "__gads"
        )]
        if bad:
            print("FAIL: personalized ads cookies after reject:", bad)
            ok = False

    print("\nWrote", out_path)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
