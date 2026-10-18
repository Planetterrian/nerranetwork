"""Consent Mode v2 follow-ups (Oct 18 2026) — PR 1 from the 48h review.

1. Single gtag config per tag (no onload re-config).
2. Cookie settings toggles reflect saved choices (syncToggles).
3. ad_personalization always denied (no remarketing / retargeting).
4. Russian banner + footer Cookie settings label.
5. Cookie settings fallback when .nn-footer-legal is missing.
6. Privacy copy names cookies, says hash on submit, date bumped.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Static source guards
# ---------------------------------------------------------------------------


class TestSingleConfigPerTag:
    def test_no_onload_config_tags(self):
        js = _read("assets/js/consent.js")
        assert "function configTags" in js
        assert "configTags()" in js
        # The duplicate path was: script.onload = function () { configTags(); };
        assert re.search(r"\.onload\s*=\s*function", js) is None
        assert "onload = function" not in js


class TestAdPersonalizationAlwaysDenied:
    def test_apply_consent_keeps_personalization_denied(self):
        js = _read("assets/js/consent.js")
        # Must not mirror ads into ad_personalization.
        assert "'ad_personalization': ads" not in js
        assert '"ad_personalization": ads' not in js
        assert "'ad_personalization': 'denied'" in js
        assert "allow_ad_personalization_signals: false" in js
        # Header documents the decision.
        assert "ad_personalization is ALWAYS denied" in js


class TestRussianBannerCopy:
    def test_banner_copy_ru_strings(self):
        js = _read("assets/js/consent.js")
        assert "BANNER_COPY_RU" in js
        for s in (
            "Cookie на Nerra",
            "Принять все",
            "Отклонить все",
            "Выбрать",
            "Аналитика",
            "Измерение рекламы",
            "Сохранить",
            "Закрыть",
            "Настройки cookie",
            "Политика конфиденциальности",
        ):
            assert s in js
        assert "BODY_LEAD_BY_MODE_RU" in js
        assert "document.documentElement.lang" in js
        assert "indexOf('ru')" in js

    def test_footer_cookie_settings_ru_in_base(self):
        base = _read("templates/base.html.j2")
        assert (
            "'footer_cookie_settings': 'Настройки cookie' if _is_ru "
            "else 'Cookie settings'"
        ) in base


class TestCookieSettingsFallback:
    def test_fallback_host_in_source(self):
        js = _read("assets/js/consent.js")
        assert "nn-cookie-settings-fallback" in js
        assert "querySelector('footer')" in js
        assert "modern-investing-resources" in js or "Hand-written pages" in js


class TestPrivacyCopyMatchesBehaviour:
    def test_cookies_named_and_we_run_ads(self):
        for rel in ("templates/privacy_policy.html.j2", "privacy-policy.html"):
            src = _read(rel)
            assert "We run Google ads" in src
            assert "If we run Google ads" not in src
            assert "submit a Personal tips form" in src
            assert "`_ga`" in src or "<code>_ga</code>" in src
            assert "`_ga_*`" in src or "<code>_ga_*</code>" in src
            assert "`_gcl_au`" in src or "<code>_gcl_au</code>" in src
            assert "`IDE`" in src or "<code>IDE</code>" in src
            assert "doubleclick.net" in src
            assert "ad personalization" in src.lower() or "remarketing" in src.lower()

    def test_date_bumped(self):
        assert 'LEGAL_PAGES_UPDATED_LABEL = "October 18, 2026"' in _read(
            "generate_html.py"
        )
        html = _read("privacy-policy.html")
        assert "Last updated October 18, 2026" in html


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
const attrs = {};

function makeEl(tag) {
  const el = {
    tagName: String(tag).toUpperCase(),
    id: '',
    className: '',
    style: {},
    hidden: false,
    innerHTML: '',
    textContent: '',
    href: '',
    children: [],
    parentNode: null,
    listeners: {},
    attrs: {},
    setAttribute(k, v) {
      this.attrs[k] = String(v);
      if (k === 'id') this.id = String(v);
      if (k === 'class' || k === 'className') this.className = String(v);
    },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; },
    hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); },
    removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    insertAdjacentElement(where, node) {
      if (where === 'afterend' && this.parentNode) {
        const sibs = this.parentNode.children;
        const i = sibs.indexOf(this);
        sibs.splice(i + 1, 0, node);
        node.parentNode = this.parentNode;
      } else {
        this.appendChild(node);
      }
      return node;
    },
    addEventListener(type, fn) {
      this.listeners[type] = this.listeners[type] || [];
      this.listeners[type].push(fn);
    },
    querySelector(sel) {
      const html = this.innerHTML || '';
      if (sel === '[data-nn-consent-panel]') {
        if (!this._panel) this._panel = { hidden: true };
        return this._panel;
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
      if (sel && sel.indexOf('privacy-policy') >= 0) {
        return this.children.find((c) => c.getAttribute && (c.getAttribute('href') || '').indexOf('privacy') >= 0) || null;
      }
      return null;
    },
    querySelectorAll(sel) {
      if (sel === '[data-nn-cookie-settings]') {
        const out = [];
        const walk = (n) => {
          if (n.getAttribute && n.getAttribute('data-nn-cookie-settings')) out.push(n);
          (n.children || []).forEach(walk);
        };
        walk(this);
        return out;
      }
      return [];
    },
    classList: { add() {} },
  };
  created.push(el);
  return el;
}

const footerEl = makeEl('footer');
footerEl.tagName = 'FOOTER';

const bodyEl = {
  appendChild(el) { created.push(el); el.parentNode = bodyEl; this._kids = this._kids || []; this._kids.push(el); },
  children: [],
  querySelector() { return null; },
  querySelectorAll() { return []; },
};

global.window = global;
global.document = {
  readyState: 'complete',
  getElementById(id) {
    return created.find((el) => el.id === id) || null;
  },
  querySelectorAll(sel) {
    if (sel === '[data-nn-cookie-settings]') {
      const out = [];
      const walk = (n) => {
        if (!n) return;
        if (n.getAttribute && n.getAttribute('data-nn-cookie-settings')) out.push(n);
        (n.children || []).forEach(walk);
        (n._kids || []).forEach(walk);
      };
      created.forEach(walk);
      walk(footerEl);
      walk(bodyEl);
      return out;
    }
    if (sel && sel.indexOf('consent.js') >= 0) {
      if (scenario.scriptAttrs) {
        return [{
          getAttribute(k) { return scenario.scriptAttrs[k] || null; },
        }];
      }
      return [];
    }
    if (sel && sel.indexOf('googletagmanager.com/gtag/js') >= 0) return [];
    return [];
  },
  querySelector(sel) {
    if (sel === '.nn-footer-legal > div' || sel === '.nn-footer-legal') {
      return scenario.hasLegal ? (scenario._legal || null) : null;
    }
    if (sel === 'footer') return scenario.useFooter === false ? null : footerEl;
    if (sel && sel.indexOf('googletagmanager') >= 0) return null;
    return null;
  },
  createElement: makeEl,
  body: bodyEl,
  head: { appendChild(s) { created.push(s); } },
  addEventListener() {},
  documentElement: { lang: scenario.lang || 'en' },
  currentScript: scenario.scriptAttrs ? {
    getAttribute(k) { return scenario.scriptAttrs[k] || null; },
  } : null,
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
eval(consentSrc);

function consentUpdates() {
  return gtagCalls.filter((c) => c[0] === 'consent' && c[1] === 'update');
}
function configCalls() {
  return gtagCalls.filter((c) => c[0] === 'config');
}

(async () => {
  const out = { ok: true };

  if (scenario.action === 'acceptPersonalization') {
    window.NNConsent.acceptAll();
    const last = consentUpdates().slice(-1)[0][2];
    out.lastUpdate = last;
    out.configs = configCalls().map((c) => [c[1], c[2] || {}]);
  } else if (scenario.action === 'syncToggles') {
    window.NNConsent.acceptAll();
    window.NNConsent.reopen();
    const banner = document.getElementById('nn-consent-banner');
    // Open Choose so the panel is visible (toggles already synced).
    const choose = banner.querySelector('[data-nn-consent="choose"]');
    choose.click();
    const a = banner.querySelector('[data-nn-toggle="analytics"]');
    const d = banner.querySelector('[data-nn-toggle="ads"]');
    out.analyticsChecked = !!a.checked;
    out.adsChecked = !!d.checked;
  } else if (scenario.action === 'singleConfig') {
    // Boot already called ensureGtagLoaded when IDs present.
    const configs = configCalls();
    out.ga4 = configs.filter((c) => c[1] === 'G-6PWJCVQQ7B').length;
    out.ads = configs.filter((c) => c[1] === 'AW-949617778').length;
    out.adsOpts = configs.filter((c) => c[1] === 'AW-949617778').map((c) => c[2]);
  } else if (scenario.action === 'ruCopy') {
    out.isRu = window.NNConsent.isRu();
    out.copy = window.NNConsent.bannerCopy();
    out.body = window.NNConsent.bodyBeforePrivacy();
  } else if (scenario.action === 'fallbackLink') {
    // Re-run ensure after boot (boot may have already appended).
    window.NNConsent.ensureCookieSettingsLink();
    const links = document.querySelectorAll('[data-nn-cookie-settings]');
    out.linkCount = links.length;
    out.label = links[0] && links[0].textContent;
    out.inFallback = !!(links[0] && links[0].parentNode &&
      links[0].parentNode.className === 'nn-cookie-settings-fallback');
    out.hostTag = links[0] && links[0].parentNode && links[0].parentNode.parentNode
      ? links[0].parentNode.parentNode.tagName
      : (links[0] && links[0].parentNode && links[0].parentNode.tagName);
    // parent of <p.fallback> is footer
    if (links[0] && links[0].parentNode) {
      out.pClass = links[0].parentNode.className;
      out.hostIsFooter = links[0].parentNode.parentNode === footerEl ||
        links[0].parentNode === footerEl;
    }
  }

  process.stdout.write(JSON.stringify(out));
})().catch((err) => { console.error(err); process.exit(1); });
"""


def _run(**scenario) -> dict:
    payload = {
        "consentPath": str(ROOT / "assets" / "js" / "consent.js"),
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
class TestConsentFollowupBehaviour:
    def test_accept_all_keeps_ad_personalization_denied(self):
        out = _run(action="acceptPersonalization")
        assert out["lastUpdate"]["analytics_storage"] == "granted"
        assert out["lastUpdate"]["ad_storage"] == "granted"
        assert out["lastUpdate"]["ad_user_data"] == "granted"
        assert out["lastUpdate"]["ad_personalization"] == "denied"

    def test_single_config_per_tag_after_boot(self):
        out = _run(
            action="singleConfig",
            scriptAttrs={
                "data-nn-ga4-id": "G-6PWJCVQQ7B",
                "data-nn-ads-id": "AW-949617778",
                "data-nn-path-prefix": "",
            },
        )
        assert out["ga4"] == 1
        assert out["ads"] == 1
        assert out["adsOpts"][0].get("allow_ad_personalization_signals") is False

    def test_sync_toggles_after_accept(self):
        out = _run(action="syncToggles")
        assert out["analyticsChecked"] is True
        assert out["adsChecked"] is True

    def test_russian_copy_when_lang_ru(self):
        out = _run(action="ruCopy", lang="ru")
        assert out["isRu"] is True
        assert out["copy"]["acceptAll"] == "Принять все"
        assert out["copy"]["cookieSettings"] == "Настройки cookie"
        assert "До вашего выбора" in out["body"]
        assert "Некоторые cookie нужны для работы сайта" in out["body"]

    def test_cookie_settings_fallback_appends_to_footer(self):
        out = _run(action="fallbackLink", hasLegal=False, useFooter=True)
        assert out["linkCount"] >= 1
        assert out["label"] == "Cookie settings"
        assert out["pClass"] == "nn-cookie-settings-fallback"
        assert out["hostIsFooter"] is True
