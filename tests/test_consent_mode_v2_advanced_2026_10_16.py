"""Consent Mode v2 Advanced (default) + Soft Personal user_data gate.

Default CONSENT_MODE is 'advanced'. Independent Analytics / Ad measurement
toggles; hashed user_data only when Ad measurement is granted; close ≡
Reject all; Cookie settings reopen + withdrawal; legacy migration.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# Exact advanced-mode body lead (marketing).
_ADVANCED_LEAD = (
    "Before you choose, Google gets only basic, cookie-free signals "
    "(for example, that a page loaded), with no cookies or IDs that "
    "identify you."
)
_BASIC_LEAD = "Nothing is sent to Google until you choose."

_YOUR_CHOICES_ADVANCED = (
    "Before you choose, and if you reject, Google's tag sends only limited "
    "cookie-free signals, such as that a page loaded, so we can estimate "
    "overall traffic. These don't set cookies or include identifiers, "
    "though like any web request your browser shares its IP address."
)

_PRIVACY_CONTACT = (
    "The person in charge of protecting personal information at Nerra "
    "Network is Patrick Novak. Contact:"
)


class TestConsentModeConstant:
    def test_default_is_advanced(self):
        js = _read("assets/js/consent.js")
        assert re.search(r"var CONSENT_MODE\s*=\s*'advanced'", js)
        assert "BODY_LEAD_BY_MODE" in js
        # Lead is split across JS string concatenations — assert the pieces.
        assert "Before you choose, Google gets only basic, cookie-free signals" in js
        assert "no cookies or IDs that" in js
        assert "identify you." in js
        assert _BASIC_LEAD in js

    def test_template_does_not_hard_load_gtag(self):
        """Basic mode must be able to hold the library; consent.js owns load."""
        base = _read("templates/base.html.j2")
        assert "assets/js/consent.js" in base
        assert "data-nn-ga4-id" in base
        # No second googletagmanager script tag in the template.
        assert "googletagmanager.com/gtag/js" not in base


class TestBannerCopyAndEqualWeight:
    def test_three_equal_weight_buttons_same_class(self):
        js = _read("assets/js/consent.js")
        assert 'data-nn-consent="accept-all"' in js
        assert 'data-nn-consent="reject-all"' in js
        assert 'data-nn-consent="choose"' in js
        assert "Accept all" in js and "Reject all" in js and "Choose" in js
        # Every primary action uses nn-consent-btn only (no accept/reject skin).
        assert "nn-consent-accept" not in js
        assert "nn-consent-reject" not in js
        css = _read("styles/main.css")
        assert "#nn-consent-banner .nn-consent-btn" in css
        assert ".nn-consent-accept" not in css
        assert ".nn-consent-reject" not in css

    def test_advanced_banner_body_is_default_rendered(self):
        js = _read("assets/js/consent.js")
        # bodyBeforePrivacy uses CONSENT_MODE to pick the lead.
        assert "function bodyBeforePrivacy" in js
        assert "leads[CONSENT_MODE]" in js or "BODY_LEAD_BY_MODE[CONSENT_MODE]" in js
        assert "Some cookies keep the site working." in js
        assert "Cookie settings at the bottom of every page" in js
        assert "Privacy policy" in js

    def test_independent_toggles_off_by_default(self):
        js = _read("assets/js/consent.js")
        assert 'data-nn-toggle="analytics"' in js
        assert 'data-nn-toggle="ads"' in js
        assert "Analytics" in js and "Ad measurement" in js
        # Markup for the two checkboxes must not ship a checked attribute.
        assert '<input type="checkbox" data-nn-toggle="analytics">' in js
        assert '<input type="checkbox" data-nn-toggle="ads">' in js
        assert '<input type="checkbox" data-nn-toggle="analytics" checked' not in js
        assert '<input type="checkbox" data-nn-toggle="ads" checked' not in js

    def test_cookie_settings_footer_wiring(self):
        base = _read("templates/base.html.j2")
        assert 'data-nn-cookie-settings="1"' in base
        assert "Cookie settings" in base
        js = _read("assets/js/consent.js")
        assert "ensureCookieSettingsLink" in js
        assert "reopenBanner" in js or "NNConsent.reopen" in js


class TestPrivacyPolicyAdvancedCopy:
    def test_your_choices_and_privacy_contact(self):
        for rel in ("templates/privacy_policy.html.j2", "privacy-policy.html"):
            src = _read(rel)
            assert _YOUR_CHOICES_ADVANCED in src
            assert _PRIVACY_CONTACT in src
            assert 'href="mailto:privacy@nerranetwork.com"' in src
            assert "email" in src and "privacy@nerranetwork.com" in src
            assert "contact page" in src
            assert "If you don't allow Ad measurement, your email hash is never sent." in src
            assert "If you decline cookies, nothing is sent." not in src
            assert "We run Google ads" in src
            assert "If we run Google ads" not in src
            assert "when you submit a Personal tips form" in src

    def test_enhanced_conversions_sentence_kept(self):
        src = _read("templates/privacy_policy.html.j2")
        assert "SHA-256 hash of your email address" in src
        assert "Google calls this enhanced conversions" in src


# ---------------------------------------------------------------------------
# Behaviour (Node)
# ---------------------------------------------------------------------------


_NODE_HARNESS = r"""
const fs = require('fs');
const {webcrypto} = require('crypto');

let scenario;
try { scenario = JSON.parse(fs.readFileSync(0, 'utf8')); }
catch (e) { console.error(e); process.exit(2); }

const store = Object.create(null);
const localStorage = {
  getItem(k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
  setItem(k, v) { store[k] = String(v); },
  removeItem(k) { delete store[k]; },
};

const gtagCalls = [];
function gtag() { gtagCalls.push(Array.from(arguments)); }

const created = [];
global.window = global;
global.document = {
  readyState: 'complete',
  getElementById(id) {
    return created.find((el) => el.id === id) || null;
  },
  querySelectorAll(sel) {
    if (sel === '[data-nn-cookie-settings]') {
      return created.filter((el) => el.getAttribute && el.getAttribute('data-nn-cookie-settings'));
    }
    if (sel && sel.indexOf('consent.js') >= 0) return [];
    return [];
  },
  querySelector() { return null; },
  createElement(tag) {
    const el = {
      tagName: String(tag).toUpperCase(),
      id: '',
      style: {},
      hidden: false,
      innerHTML: '',
      children: [],
      listeners: {},
      setAttribute(k, v) { this.attrs = this.attrs || {}; this.attrs[k] = String(v); if (k === 'id') this.id = String(v); },
      getAttribute(k) { return (this.attrs && this.attrs[k]) || null; },
      hasAttribute(k) { return !!(this.attrs && Object.prototype.hasOwnProperty.call(this.attrs, k)); },
      removeAttribute(k) { if (this.attrs) delete this.attrs[k]; },
      appendChild(c) { this.children.push(c); return c; },
      addEventListener(type, fn) {
        this.listeners[type] = this.listeners[type] || [];
        this.listeners[type].push(fn);
      },
      querySelector(sel) {
        // Very small CSS subset for the banner harness.
        const html = this.innerHTML || '';
        if (sel === '[data-nn-consent-panel]') {
          return this._panel || null;
        }
        if (sel && sel.indexOf('data-nn-consent=') >= 0) {
          const m = sel.match(/data-nn-consent="([^"]+)"/);
          const key = m && m[1];
          const btn = {
            addEventListener(type, fn) {
              this._fns = this._fns || {};
              this._fns[type] = this._fns[type] || [];
              this._fns[type].push(fn);
            },
            click() {
              (this._fns && this._fns.click || []).forEach((f) => f({ preventDefault() {} }));
            },
          };
          this._btns = this._btns || {};
          this._btns[key] = btn;
          return btn;
        }
        if (sel && sel.indexOf('data-nn-toggle=') >= 0) {
          const m = sel.match(/data-nn-toggle="([^"]+)"/);
          const key = m && m[1];
          this._toggles = this._toggles || {};
          if (!this._toggles[key]) this._toggles[key] = { checked: false };
          return this._toggles[key];
        }
        if (sel === '.nn-consent-close') {
          if (!this._close) {
            this._close = {
              addEventListener(type, fn) {
                this._fns = this._fns || {};
                this._fns[type] = this._fns[type] || [];
                this._fns[type].push(fn);
              },
              click() {
                (this._fns && this._fns.click || []).forEach((f) => f({ preventDefault() {} }));
              },
            };
          }
          return this._close;
        }
        if (sel === '.nn-consent-text') {
          if (!this._text) this._text = { innerHTML: '' };
          return this._text;
        }
        return null;
      },
      querySelectorAll() { return []; },
      classList: { add() {} },
    };
    created.push(el);
    return el;
  },
  body: {
    appendChild(el) { created.push(el); },
  },
  head: { appendChild() {} },
  addEventListener() {},
  documentElement: { lang: 'en' },
};
global.localStorage = localStorage;
global.TextEncoder = TextEncoder;
global.crypto = webcrypto;
global.window.crypto = webcrypto;
global.window.gtag = gtag;
global.window.dataLayer = [];
global.window.location = { search: '', pathname: '/', href: 'https://nerranetwork.com/' };

if (scenario.seed) {
  localStorage.setItem('nn_consent_v1', JSON.stringify(scenario.seed));
}

let consentSrc = fs.readFileSync(scenario.consentPath, 'utf8');
if (scenario.forceMode) {
  consentSrc = consentSrc.replace(
    /var CONSENT_MODE = 'advanced'/,
    "var CONSENT_MODE = '" + scenario.forceMode + "'"
  );
}
eval(consentSrc);

if (scenario.footerPath) {
  eval(fs.readFileSync(scenario.footerPath, 'utf8'));
}

function consentDefaults() {
  return gtagCalls.filter((c) => c[0] === 'consent' && c[1] === 'default');
}
function consentUpdates() {
  return gtagCalls.filter((c) => c[0] === 'consent' && c[1] === 'update');
}
function setCalls(key) {
  return gtagCalls.filter((c) => c[0] === 'set' && c[1] === key);
}

(async () => {
  const out = {
    mode: window.NNConsent.CONSENT_MODE,
    body: window.NNConsent.bodyBeforePrivacy(),
    defaults: consentDefaults().map((c) => c[2]),
    urlPassthroughInit: setCalls('url_passthrough').map((c) => c[2]),
    adsRedactionInit: setCalls('ads_data_redaction').map((c) => c[2]),
    isAd: window.NNConsent.isAdUserDataGranted(),
    isAnalytics: window.NNConsent.isAnalyticsGranted(),
    stored: window.NNConsent.readStored(),
  };

  if (scenario.action === 'acceptAll') {
    window.NNConsent.acceptAll();
    out.after = {
      isAd: window.NNConsent.isAdUserDataGranted(),
      isAnalytics: window.NNConsent.isAnalyticsGranted(),
      stored: window.NNConsent.readStored(),
      updates: consentUpdates().map((c) => c[2]),
    };
  } else if (scenario.action === 'rejectAll') {
    window.NNConsent.rejectAll();
    out.after = {
      isAd: window.NNConsent.isAdUserDataGranted(),
      isAnalytics: window.NNConsent.isAnalyticsGranted(),
      stored: window.NNConsent.readStored(),
      updates: consentUpdates().map((c) => c[2]),
    };
  } else if (scenario.action === 'savePartial') {
    window.NNConsent.saveChoices({
      analytics: scenario.analytics || 'denied',
      ads: scenario.ads || 'denied',
    });
    out.after = {
      isAd: window.NNConsent.isAdUserDataGranted(),
      isAnalytics: window.NNConsent.isAnalyticsGranted(),
      stored: window.NNConsent.readStored(),
      updates: consentUpdates().map((c) => c[2]),
    };
  } else if (scenario.action === 'migrate') {
    out.stored = window.NNConsent.readStored();
    out.isAd = window.NNConsent.isAdUserDataGranted();
    out.isAnalytics = window.NNConsent.isAnalyticsGranted();
  } else if (scenario.action === 'userData') {
    const set = await window.NNSubscribe.maybeSetEnhancedConversionUserData(
      scenario.email, scenario.company || '');
    const userDataCalls = gtagCalls.filter(
      (c) => c[0] === 'set' && c[1] === 'user_data');
    out.userData = {
      setReturned: set,
      calls: userDataCalls.map((c) => c[2]),
      isAd: window.NNConsent.isAdUserDataGranted(),
    };
  } else if (scenario.action === 'bannerClose') {
    window.NNConsent.showBanner();
    const banner = document.getElementById('nn-consent-banner');
    // Wire happens in renderBanner; click the close control.
    const close = banner.querySelector('.nn-consent-close');
    close.click();
    out.after = {
      isAd: window.NNConsent.isAdUserDataGranted(),
      isAnalytics: window.NNConsent.isAnalyticsGranted(),
      stored: window.NNConsent.readStored(),
    };
  } else if (scenario.action === 'withdraw') {
    window.NNConsent.acceptAll();
    const before = {
      isAd: window.NNConsent.isAdUserDataGranted(),
      updates: consentUpdates().length,
    };
    window.NNConsent.rejectAll();
    out.after = {
      before,
      isAd: window.NNConsent.isAdUserDataGranted(),
      isAnalytics: window.NNConsent.isAnalyticsGranted(),
      stored: window.NNConsent.readStored(),
      lastUpdate: consentUpdates().slice(-1)[0][2],
    };
  }

  process.stdout.write(JSON.stringify(out));
})().catch((err) => { console.error(err); process.exit(1); });
"""


def _run(**scenario) -> dict:
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
        raise AssertionError(f"node failed: {res.stderr}\n{res.stdout}")
    return json.loads(res.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
class TestConsentBehaviourAdvancedDefault:
    def test_defaults_all_denied_and_advanced_flags(self):
        out = _run()
        assert out["mode"] == "advanced"
        assert _ADVANCED_LEAD in out["body"]
        assert _BASIC_LEAD not in out["body"]
        assert out["defaults"]
        d = out["defaults"][0]
        assert d["ad_storage"] == "denied"
        assert d["ad_user_data"] == "denied"
        assert d["ad_personalization"] == "denied"
        assert d["analytics_storage"] == "denied"
        assert False in out["urlPassthroughInit"]
        assert True in out["adsRedactionInit"]
        assert out["isAd"] is False
        assert out["isAnalytics"] is False

    def test_accept_all_grants_both(self):
        out = _run(action="acceptAll")
        assert out["after"]["isAd"] is True
        assert out["after"]["isAnalytics"] is True
        assert out["after"]["stored"]["ads"] == "granted"
        assert out["after"]["stored"]["analytics"] == "granted"

    def test_reject_all_denies_both(self):
        out = _run(action="rejectAll")
        assert out["after"]["isAd"] is False
        assert out["after"]["isAnalytics"] is False
        assert out["after"]["stored"]["ads"] == "denied"

    def test_independent_toggles_analytics_only(self):
        out = _run(action="savePartial", analytics="granted", ads="denied")
        assert out["after"]["isAnalytics"] is True
        assert out["after"]["isAd"] is False

    def test_independent_toggles_ads_only(self):
        out = _run(action="savePartial", analytics="denied", ads="granted")
        assert out["after"]["isAnalytics"] is False
        assert out["after"]["isAd"] is True

    def test_user_data_only_when_ads_granted(self):
        now = int(__import__("time").time() * 1000)
        # Analytics-only → no hash
        a = _run(
            action="userData",
            email="a@example.com",
            seed={"analytics": "granted", "ads": "denied", "timestamp": now},
        )
        assert a["userData"]["isAd"] is False
        assert a["userData"]["setReturned"] is False
        assert a["userData"]["calls"] == []

        # Ads granted → hash set
        b = _run(
            action="userData",
            email="  Pat@Example.COM ",
            seed={"analytics": "denied", "ads": "granted", "timestamp": now},
        )
        assert b["userData"]["isAd"] is True
        assert b["userData"]["setReturned"] is True
        expected = hashlib.sha256(b"pat@example.com").hexdigest()
        assert b["userData"]["calls"][0]["sha256_email_address"] == expected

    def test_close_counts_as_reject(self):
        out = _run(action="bannerClose")
        assert out["after"]["stored"]["ads"] == "denied"
        assert out["after"]["stored"]["analytics"] == "denied"
        assert out["after"]["isAd"] is False

    def test_withdrawal_updates_immediately(self):
        out = _run(action="withdraw")
        assert out["after"]["before"]["isAd"] is True
        assert out["after"]["isAd"] is False
        assert out["after"]["lastUpdate"]["ad_user_data"] == "denied"
        assert out["after"]["lastUpdate"]["analytics_storage"] == "denied"

    def test_legacy_migration(self):
        now = int(__import__("time").time() * 1000)
        a = _run(action="migrate", seed={"state": "accepted", "timestamp": now})
        assert a["stored"]["analytics"] == "granted"
        assert a["stored"]["ads"] == "granted"
        assert a["isAd"] is True
        r = _run(action="migrate", seed={"state": "rejected", "timestamp": now})
        assert r["stored"]["analytics"] == "denied"
        assert r["stored"]["ads"] == "denied"
        assert r["isAd"] is False

    def test_basic_mode_body_variant(self):
        out = _run(forceMode="basic")
        assert out["mode"] == "basic"
        assert _BASIC_LEAD in out["body"]
        assert _ADVANCED_LEAD not in out["body"]
