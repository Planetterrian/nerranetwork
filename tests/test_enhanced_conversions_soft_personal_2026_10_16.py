"""Google Ads enhanced conversions for soft_personal_interest_submit.

Oct 16 2026: immediately before the Soft Personal north-star event,
consent-gated gtag('set','user_data',{sha256_email_address}) via
crypto.subtle. Only when email present, honeypot empty, and
ad_user_data/ads consent granted. Never logs the email; never blocks
subscribe.

Scope: assets/js/consent.js, assets/js/footer-subscribe.js,
templates/personal_interest_page.html.j2 (+ committed personal-interest.html).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Source wiring (static)
# ---------------------------------------------------------------------------


class TestEnhancedConversionWiring:
    def test_consent_exports_ad_user_data_gate(self):
        js = _read("assets/js/consent.js")
        assert "function isAdUserDataGranted" in js
        assert "NNConsent.isAdUserDataGranted" in js
        assert "'ad_user_data': grant" in js or '"ad_user_data": grant' in js
        assert "nn_consent_v1" in js

    def test_footer_subscribe_sets_user_data_before_soft_event(self):
        js = _read("assets/js/footer-subscribe.js")
        assert "maybeSetEnhancedConversionUserData" in js
        assert "fireSoftPersonalInterestSubmit" in js
        assert "sha256_email_address" in js
        assert "gtag('set', 'user_data'" in js or 'gtag("set", "user_data"' in js
        assert "crypto.subtle" in js
        assert "normalizeEmailForHash" in js
        # Soft success path calls the gated helper after the ok:true gate.
        # (The function *definition* appears earlier in the file — find the
        # call site that passes email/company from the submit handler.)
        call_token = "fireSoftPersonalInterestSubmit(email, company, {"
        assert call_token in js
        soft_call_idx = js.index(call_token)
        success_gate = js.index("r.data.ok === true") if "r.data.ok === true" in js else js.index("data.ok === true")
        assert soft_call_idx > success_gate
        # Honeypot gate + consent gate present.
        assert "company" in js
        assert "adsUserDataConsentGranted" in js or "isAdUserDataGranted" in js
        # Never log or persist the email around the enhanced-conversion path.
        region = js[js.index("function normalizeEmailForHash"):js.index(
            "window.NNSubscribe.fireSoftPersonalInterestSubmit")]
        assert "console.log" not in region
        assert "localStorage.setItem" not in region

    def test_soft_personal_page_uses_shared_helper(self):
        tmpl = _read("templates/personal_interest_page.html.j2")
        html = _read("personal-interest.html")
        for src in (tmpl, html):
            assert "fireSoftPersonalInterestSubmit" in src
            assert "soft_personal_interest_submit" in src
            # Still fires newsletter_signup on the newsletter-only branch.
            assert "newsletter_signup" in src

    def test_helpers_exported_on_nnsubscribe(self):
        js = _read("assets/js/footer-subscribe.js")
        assert "NNSubscribe.maybeSetEnhancedConversionUserData" in js
        assert "NNSubscribe.fireSoftPersonalInterestSubmit" in js
        assert "NNSubscribe.normalizeEmailForHash" in js
        assert "NNSubscribe.sha256Hex" in js


# ---------------------------------------------------------------------------
# Behaviour (Node + crypto.subtle)
# ---------------------------------------------------------------------------


_NODE_HARNESS = r"""
const fs = require('fs');
const {webcrypto} = require('crypto');

let scenario;
try {
  scenario = JSON.parse(fs.readFileSync(0, 'utf8'));
} catch (e) {
  console.error('stdin parse failed', e);
  process.exit(2);
}

// Minimal browser stubs.
const store = Object.create(null);
const localStorage = {
  getItem(k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
  setItem(k, v) { store[k] = String(v); },
  removeItem(k) { delete store[k]; },
};

const gtagCalls = [];
function gtag() { gtagCalls.push(Array.from(arguments)); }

global.window = global;
global.document = {
  readyState: 'complete',
  getElementById() { return null; },
  querySelectorAll() { return []; },
  createElement() {
    return {
      id: '',
      setAttribute() {},
      querySelector() { return { addEventListener() {} }; },
      style: {},
      classList: { add() {} },
      innerHTML: '',
    };
  },
  body: { appendChild() {} },
  addEventListener() {},
  documentElement: { lang: 'en' },
};
global.localStorage = localStorage;
global.TextEncoder = TextEncoder;
global.crypto = webcrypto;
global.window.crypto = webcrypto;
global.window.gtag = gtag;
global.window.dataLayer = [];
global.window.location = { search: '', pathname: '/personal-interest.html' };

if (scenario.consent === 'accepted') {
  localStorage.setItem('nn_consent_v1', JSON.stringify({
    state: 'accepted', timestamp: Date.now(),
  }));
} else if (scenario.consent === 'rejected') {
  localStorage.setItem('nn_consent_v1', JSON.stringify({
    state: 'rejected', timestamp: Date.now(),
  }));
}
// else: no stored consent → denied

const consentSrc = fs.readFileSync(scenario.consentPath, 'utf8');
const footerSrc = fs.readFileSync(scenario.footerPath, 'utf8');
// consent.js early-returns when not pending — still exports NNConsent first.
eval(consentSrc);
eval(footerSrc);

(async () => {
  const set = await window.NNSubscribe.maybeSetEnhancedConversionUserData(
    scenario.email, scenario.company);
  const userDataCalls = gtagCalls.filter(
    (c) => c[0] === 'set' && c[1] === 'user_data');
  const out = {
    setReturned: set,
    userDataCalls: userDataCalls.map((c) => c[2]),
    consentGranted: window.NNConsent.isAdUserDataGranted(),
  };
  if (scenario.alsoNormalize) {
    out.normalized = window.NNSubscribe.normalizeEmailForHash(scenario.email);
    out.hash = await window.NNSubscribe.sha256Hex(out.normalized);
  }
  process.stdout.write(JSON.stringify(out));
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
"""


def _run_node_scenario(**scenario) -> dict:
    payload = {
        "consentPath": str(ROOT / "assets" / "js" / "consent.js"),
        "footerPath": str(ROOT / "assets" / "js" / "footer-subscribe.js"),
        **scenario,
    }
    res = subprocess.run(
        ["node", "-e", _NODE_HARNESS],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        raise AssertionError(
            f"node harness failed ({res.returncode}): {res.stderr}\n{res.stdout}"
        )
    return json.loads(res.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
class TestEnhancedConversionBehaviour:
    def test_user_data_set_when_consent_granted_and_email_present(self):
        email = "Listener@Example.COM "
        out = _run_node_scenario(
            consent="accepted",
            email=email,
            company="",
            alsoNormalize=True,
        )
        assert out["consentGranted"] is True
        assert out["setReturned"] is True
        assert len(out["userDataCalls"]) == 1
        hashed = out["userDataCalls"][0]["sha256_email_address"]
        expected = hashlib.sha256(b"listener@example.com").hexdigest()
        assert hashed == expected
        assert out["normalized"] == "listener@example.com"
        assert out["hash"] == expected
        # Raw email never appears in the gtag payload.
        blob = json.dumps(out["userDataCalls"])
        assert "Listener@Example.COM" not in blob
        assert "listener@example.com" not in blob or hashed in blob

    def test_user_data_not_set_when_consent_denied(self):
        out = _run_node_scenario(
            consent="rejected",
            email="ok@example.com",
            company="",
        )
        assert out["consentGranted"] is False
        assert out["setReturned"] is False
        assert out["userDataCalls"] == []

    def test_user_data_not_set_when_consent_pending(self):
        out = _run_node_scenario(
            consent="pending",
            email="ok@example.com",
            company="",
        )
        assert out["consentGranted"] is False
        assert out["setReturned"] is False
        assert out["userDataCalls"] == []

    def test_user_data_not_set_when_honeypot_filled(self):
        out = _run_node_scenario(
            consent="accepted",
            email="ok@example.com",
            company="Acme Bot Farm",
        )
        assert out["setReturned"] is False
        assert out["userDataCalls"] == []

    def test_user_data_not_set_when_email_empty(self):
        out = _run_node_scenario(
            consent="accepted",
            email="   ",
            company="",
        )
        assert out["setReturned"] is False
        assert out["userDataCalls"] == []

    def test_hash_uses_trimmed_lowercased_email(self):
        """Same address with different casing/whitespace → same hex."""
        a = _run_node_scenario(
            consent="accepted",
            email="  Pat.Smith@NerraNetwork.COM\t",
            company="",
            alsoNormalize=True,
        )
        b = _run_node_scenario(
            consent="accepted",
            email="pat.smith@nerranetwork.com",
            company="",
            alsoNormalize=True,
        )
        assert a["normalized"] == "pat.smith@nerranetwork.com"
        assert a["hash"] == b["hash"]
        assert a["hash"] == hashlib.sha256(
            b"pat.smith@nerranetwork.com"
        ).hexdigest()
        assert a["userDataCalls"][0]["sha256_email_address"] == a["hash"]
