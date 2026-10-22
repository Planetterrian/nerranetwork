/**
 * Nerra Network — Cookie Consent Banner (Consent Mode v2)
 *
 * CONSENT_MODE:
 *   'advanced' (default) — gtag loads with all storage denied; cookieless
 *     signals only until the visitor chooses. url_passthrough=false and
 *     ads_data_redaction=true while ad_storage is denied.
 *   'basic' — gtag library is NOT loaded and no hits are sent until
 *     Analytics or Ad measurement is granted.
 *
 * Choices (stored separately; both denied until chosen):
 *   Analytics      → analytics_storage
 *   Ad measurement → ad_storage + ad_user_data
 *   ad_personalization is ALWAYS denied (no cross-site retargeting /
 *   remarketing lists — matches the privacy policy).
 *
 * Banner: Accept all / Reject all / Choose (equal weight). Choose reveals
 * two independent toggles (off by default) + Save. Close ≡ Reject all.
 * "Cookie settings" footer link reopens; withdrawing updates immediately.
 * Cookie settings syncs toggles from the visitor's saved choices.
 *
 * Legacy nn_consent_v1 `{state:'accepted'|'rejected'}` migrates to both
 * granted / both denied.
 *
 * BANNER_COPY / BANNER_COPY_RU hold shared strings; mode-specific body
 * sentences live in BODY_LEAD_BY_MODE / BODY_LEAD_BY_MODE_RU so marketing
 * can swap either without touching logic. RU is chosen when
 * document.documentElement.lang starts with "ru".
 *
 * Place this script BEFORE any gtag.js / gtag('config') so defaults win.
 * In basic mode the template must NOT load gtag.js itself — this file
 * injects it only after a grant (see ensureGtagLoaded).
 */
(function () {
    'use strict';

    // Flip to 'basic' to hold the gtag library until Accept / Save grants.
    var CONSENT_MODE = 'advanced'; // 'basic' | 'advanced'

    var STORAGE_KEY = 'nn_consent_v1';
    var STORAGE_DAYS = 365;

    // ---- Copy (easy to swap) ----------------------------------------
    var BODY_LEAD_BY_MODE = {
        advanced:
            'Before you choose, Google gets only basic, cookie-free signals ' +
            '(for example, that a page loaded), with no cookies or IDs that ' +
            'identify you. ',
        basic:
            'Nothing is sent to Google until you choose. ',
    };

    var BODY_LEAD_BY_MODE_RU = {
        advanced:
            'До вашего выбора Google получает только базовые сигналы без ' +
            'cookie (например, что страница загрузилась), без cookie и ' +
            'идентификаторов, которые вас узнают. ',
        basic:
            'Пока вы не выберете, Google ничего не получает. ',
    };

    var BANNER_COPY = {
        label: 'Cookies on Nerra',
        heading: 'Cookies on Nerra',
        // Lead sentence is mode-specific (see bodyBeforePrivacy()).
        bodyAfterLead:
            'With your OK you can also turn on: Analytics, which uses Google ' +
            'Analytics cookies to show us which pages and episodes are useful, ' +
            'and Ad measurement, which uses Google Ads to measure sign-ups from ' +
            'our ads. When you sign up for Personal tips, Ad measurement also ' +
            'sends Google a coded (hashed) version of your email. Change your ' +
            'mind any time from Cookie settings at the bottom of every page. ',
        privacyLinkText: 'Privacy policy',
        acceptAll: 'Accept all',
        rejectAll: 'Reject all',
        choose: 'Choose',
        analyticsLabel: 'Analytics',
        adsLabel: 'Ad measurement',
        save: 'Save',
        closeAria: 'Close',
        cookieSettings: 'Cookie settings',
        siteWorking: 'Some cookies keep the site working. ',
    };

    var BANNER_COPY_RU = {
        label: 'Cookie на Nerra',
        heading: 'Cookie на Nerra',
        bodyAfterLead:
            'С вашего согласия можно также включить: Аналитику — cookie ' +
            'Google Analytics, чтобы мы видели, какие страницы и выпуски ' +
            'полезны, и Измерение рекламы — Google Ads для подсчёта ' +
            'регистраций с нашей рекламы. Когда вы подписываетесь на ' +
            'Personal tips, Измерение рекламы также отправляет Google ' +
            'закодированную (хешированную) версию вашего email. Изменить ' +
            'выбор можно в любой момент через «Настройки cookie» внизу ' +
            'каждой страницы. ',
        privacyLinkText: 'Политика конфиденциальности',
        acceptAll: 'Принять все',
        rejectAll: 'Отклонить все',
        choose: 'Выбрать',
        analyticsLabel: 'Аналитика',
        adsLabel: 'Измерение рекламы',
        save: 'Сохранить',
        closeAria: 'Закрыть',
        cookieSettings: 'Настройки cookie',
        siteWorking: 'Некоторые cookie нужны для работы сайта. ',
    };

    function isRu() {
        return (document.documentElement.lang || 'en')
            .toLowerCase().indexOf('ru') === 0;
    }

    function bannerCopy() {
        return isRu() ? BANNER_COPY_RU : BANNER_COPY;
    }

    function bodyLeads() {
        return isRu() ? BODY_LEAD_BY_MODE_RU : BODY_LEAD_BY_MODE;
    }

    function bodyBeforePrivacy() {
        var leads = bodyLeads();
        var lead = leads[CONSENT_MODE] || leads.advanced;
        var copy = bannerCopy();
        return copy.siteWorking + lead + copy.bodyAfterLead;
    }

    window.dataLayer = window.dataLayer || [];
    if (typeof window.gtag !== 'function') {
        window.gtag = function () { window.dataLayer.push(arguments); };
    }
    // Always route through window.gtag so a page (or test) stub sees every
    // consent/default/update call — the local name is just a shorthand.
    function gtag() { return window.gtag.apply(window, arguments); }

    function pathPrefix() {
        var script = document.currentScript;
        if (!script) {
            var nodes = document.querySelectorAll('script[src*="consent.js"]');
            script = nodes.length ? nodes[nodes.length - 1] : null;
        }
        if (script) {
            var attr = script.getAttribute('data-nn-path-prefix');
            if (attr !== null && attr !== undefined) return attr;
        }
        return '';
    }

    function href(page) {
        return pathPrefix() + page;
    }

    function scriptEl() {
        var script = document.currentScript;
        if (!script) {
            var nodes = document.querySelectorAll('script[src*="consent.js"]');
            script = nodes.length ? nodes[nodes.length - 1] : null;
        }
        return script;
    }

    function measurementIds() {
        var s = scriptEl();
        return {
            ga4: (s && s.getAttribute('data-nn-ga4-id')) || '',
            ads: (s && s.getAttribute('data-nn-ads-id')) || '',
        };
    }

    /** Normalize / migrate stored consent. Returns null when pending. */
    function normalizeStored(parsed) {
        if (!parsed || typeof parsed !== 'object') return null;
        var ageMs = Date.now() - (parsed.timestamp || 0);
        if (ageMs > STORAGE_DAYS * 24 * 60 * 60 * 1000) return null;

        // Legacy: { state: 'accepted' | 'rejected' }
        if (parsed.state === 'accepted') {
            return { analytics: 'granted', ads: 'granted', timestamp: parsed.timestamp || Date.now() };
        }
        if (parsed.state === 'rejected') {
            return { analytics: 'denied', ads: 'denied', timestamp: parsed.timestamp || Date.now() };
        }

        if (parsed.analytics === 'granted' || parsed.analytics === 'denied' ||
            parsed.ads === 'granted' || parsed.ads === 'denied') {
            return {
                analytics: parsed.analytics === 'granted' ? 'granted' : 'denied',
                ads: parsed.ads === 'granted' ? 'granted' : 'denied',
                timestamp: parsed.timestamp || Date.now(),
            };
        }
        return null;
    }

    function readStored() {
        try {
            var raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return null;
            return normalizeStored(JSON.parse(raw));
        } catch (e) { return null; }
    }

    function writeStored(choices) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                analytics: choices.analytics === 'granted' ? 'granted' : 'denied',
                ads: choices.ads === 'granted' ? 'granted' : 'denied',
                timestamp: Date.now(),
            }));
        } catch (e) { /* localStorage unavailable */ }
    }

    var _gtagLoaded = false;

    function configTags() {
        var ids = measurementIds();
        if (ids.ga4) {
            gtag('config', ids.ga4, { 'anonymize_ip': true });
        }
        // Ads tag config only — no send_to conversion labels. Conversions
        // are imported from GA4 key events (newsletter_signup, etc.).
        // allow_ad_personalization_signals: false keeps remarketing off
        // even when Ad measurement (ad_storage / ad_user_data) is granted.
        if (ids.ads) {
            gtag('config', ids.ads, { allow_ad_personalization_signals: false });
        }
    }

    /**
     * Load gtag.js + config. Advanced: called at boot (denied defaults
     * already set). Basic: called only after Analytics or Ads is granted.
     * Config is queued once in dataLayer (no onload re-config).
     */
    function ensureGtagLoaded() {
        if (_gtagLoaded) return;
        var ids = measurementIds();
        var primary = ids.ga4 || ids.ads;
        if (!primary) {
            // No IDs configured (local / test) — still mark loaded so
            // consent updates are recorded on the stub gtag.
            _gtagLoaded = true;
            gtag('js', new Date());
            return;
        }
        if (document.querySelector('script[src*="googletagmanager.com/gtag/js"]')) {
            _gtagLoaded = true;
            gtag('js', new Date());
            configTags();
            return;
        }
        _gtagLoaded = true;
        gtag('js', new Date());
        var s = document.createElement('script');
        s.async = true;
        s.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(primary);
        // If DOM not ready yet, queue the insert.
        if (document.head) document.head.appendChild(s);
        else {
            document.addEventListener('DOMContentLoaded', function () {
                document.head.appendChild(s);
            });
        }
        // Config queues in dataLayer before the library arrives — do NOT
        // re-config when the script finishes loading (that doubled Ads hits).
        configTags();
    }

    /**
     * Push Consent Mode update. While ad_storage is denied: url_passthrough
     * false + ads_data_redaction true (Advanced cookieless / ID-free pings).
     * ad_personalization stays denied always (no remarketing).
     */
    function applyConsent(choices) {
        var analytics = choices.analytics === 'granted' ? 'granted' : 'denied';
        var ads = choices.ads === 'granted' ? 'granted' : 'denied';
        gtag('consent', 'update', {
            'analytics_storage': analytics,
            'ad_storage': ads,
            'ad_user_data': ads,
            'ad_personalization': 'denied',
        });
        gtag('set', 'url_passthrough', ads === 'granted');
        gtag('set', 'ads_data_redaction', ads !== 'granted');

        if (CONSENT_MODE === 'basic') {
            if (analytics === 'granted' || ads === 'granted') {
                ensureGtagLoaded();
            }
        }
    }

    /** True ONLY when Ad measurement is granted (gates hashed user_data). */
    function isAdUserDataGranted() {
        var s = readStored();
        return !!(s && s.ads === 'granted');
    }

    function isAnalyticsGranted() {
        var s = readStored();
        return !!(s && s.analytics === 'granted');
    }

    function hasChosen() {
        return readStored() !== null;
    }

    // Defaults BEFORE any gtag('config', …).
    gtag('consent', 'default', {
        'ad_storage': 'denied',
        'ad_user_data': 'denied',
        'ad_personalization': 'denied',
        'analytics_storage': 'denied',
        'wait_for_update': 500,
    });
    gtag('set', 'url_passthrough', false);
    gtag('set', 'ads_data_redaction', true);

    var stored = readStored();
    if (stored) {
        writeStored(stored); // rewrite legacy {state:…} once
        applyConsent(stored);
    }

    if (CONSENT_MODE === 'advanced') {
        // Advanced: load the library under denied defaults (cookieless pings).
        ensureGtagLoaded();
    } else if (stored && (stored.analytics === 'granted' || stored.ads === 'granted')) {
        // Basic return visit with a prior grant.
        ensureGtagLoaded();
    }

    function hideBanner(banner) {
        if (!banner) return;
        if (banner.style) banner.style.display = 'none';
        if (typeof banner.setAttribute === 'function') banner.setAttribute('hidden', '');
        try { document.documentElement.classList.remove('nn-consent-needed'); } catch (e) { /* ignore */ }
    }

    function revealBanner(banner) {
        if (!banner) return;
        if (banner.style) banner.style.display = '';
        if (typeof banner.removeAttribute === 'function') banner.removeAttribute('hidden');
        try { document.documentElement.classList.add('nn-consent-needed'); } catch (e) { /* ignore */ }
    }

    function saveChoices(choices, banner) {
        writeStored(choices);
        applyConsent(choices);
        hideBanner(banner || document.getElementById('nn-consent-banner'));
    }

    function rejectAll(banner) {
        saveChoices({ analytics: 'denied', ads: 'denied' }, banner);
    }

    function acceptAll(banner) {
        saveChoices({ analytics: 'granted', ads: 'granted' }, banner);
    }

    /** Reflect saved choices on the Choose-panel toggles. */
    function syncToggles(banner) {
        if (!banner) return;
        var current = readStored() || { analytics: 'denied', ads: 'denied' };
        var aToggle = banner.querySelector('[data-nn-toggle="analytics"]');
        var dToggle = banner.querySelector('[data-nn-toggle="ads"]');
        if (aToggle) aToggle.checked = current.analytics === 'granted';
        if (dToggle) dToggle.checked = current.ads === 'granted';
    }

    /** Bind Accept / Reject / Choose / Save / Close once per banner node. */
    function bindBannerHandlers(banner) {
        if (!banner || banner.getAttribute('data-nn-consent-bound') === '1') return;
        banner.setAttribute('data-nn-consent-bound', '1');
        var accept = banner.querySelector('[data-nn-consent="accept-all"]');
        var reject = banner.querySelector('[data-nn-consent="reject-all"]');
        var choose = banner.querySelector('[data-nn-consent="choose"]');
        var save = banner.querySelector('[data-nn-consent="save"]');
        var close = banner.querySelector('.nn-consent-close');
        if (accept) accept.addEventListener('click', function () { acceptAll(banner); });
        if (reject) reject.addEventListener('click', function () { rejectAll(banner); });
        if (choose) choose.addEventListener('click', function () {
            var panel = banner.querySelector('[data-nn-consent-panel]');
            if (panel) panel.hidden = !panel.hidden;
        });
        if (save) save.addEventListener('click', function () {
            var analyticsOn = banner.querySelector('[data-nn-toggle="analytics"]').checked;
            var adsOn = banner.querySelector('[data-nn-toggle="ads"]').checked;
            saveChoices({
                analytics: analyticsOn ? 'granted' : 'denied',
                ads: adsOn ? 'granted' : 'denied',
            }, banner);
        });
        if (close) close.addEventListener('click', function () { rejectAll(banner); });
    }

    function renderBanner() {
        var existing = document.getElementById('nn-consent-banner');
        if (existing) {
            revealBanner(existing);
            var panel = existing.querySelector('[data-nn-consent-panel]');
            if (panel) panel.hidden = true;
            syncToggles(existing);
            // Refresh body if mode/copy changed between opens (tests).
            var text = existing.querySelector('.nn-consent-text');
            if (text) {
                var tExisting = bannerCopy();
                text.innerHTML = bodyBeforePrivacy() +
                    '<a class="nn-consent-privacy" href="' + href('privacy-policy.html') + '">' +
                    tExisting.privacyLinkText + '</a>.';
            }
            bindBannerHandlers(existing);
            return existing;
        }

        var t = bannerCopy();
        var banner = document.createElement('div');
        banner.id = 'nn-consent-banner';
        banner.setAttribute('role', 'dialog');
        banner.setAttribute('aria-modal', 'true');
        banner.setAttribute('aria-label', t.label);
        banner.innerHTML = '' +
            '<div class="nn-consent-inner">' +
                '<button type="button" class="nn-consent-close" aria-label="' +
                    t.closeAria + '">&times;</button>' +
                '<h2 class="nn-consent-heading" id="nn-consent-heading">' + t.heading + '</h2>' +
                '<div class="nn-consent-text">' +
                    bodyBeforePrivacy() +
                    '<a class="nn-consent-privacy" href="' + href('privacy-policy.html') + '">' +
                        t.privacyLinkText + '</a>.' +
                '</div>' +
                '<div class="nn-consent-actions">' +
                    '<button type="button" class="nn-consent-btn" data-nn-consent="accept-all">' +
                        t.acceptAll + '</button>' +
                    '<button type="button" class="nn-consent-btn" data-nn-consent="reject-all">' +
                        t.rejectAll + '</button>' +
                    '<button type="button" class="nn-consent-btn" data-nn-consent="choose">' +
                        t.choose + '</button>' +
                '</div>' +
                '<div class="nn-consent-panel" data-nn-consent-panel hidden>' +
                    '<label class="nn-consent-toggle">' +
                        '<input type="checkbox" data-nn-toggle="analytics">' +
                        '<span>' + t.analyticsLabel + '</span>' +
                    '</label>' +
                    '<label class="nn-consent-toggle">' +
                        '<input type="checkbox" data-nn-toggle="ads">' +
                        '<span>' + t.adsLabel + '</span>' +
                    '</label>' +
                    '<button type="button" class="nn-consent-btn" data-nn-consent="save">' +
                        t.save + '</button>' +
                '</div>' +
            '</div>';
        document.body.appendChild(banner);
        revealBanner(banner);
        syncToggles(banner);
        bindBannerHandlers(banner);
        return banner;
    }

    function showBanner() {
        if (!document.body) return;
        renderBanner();
    }

    function reopenBanner() {
        showBanner();
    }

    function ensureCookieSettingsLink() {
        var label = bannerCopy().cookieSettings;
        var links = document.querySelectorAll('[data-nn-cookie-settings]');
        if (!links.length) {
            var legal = document.querySelector('.nn-footer-legal > div');
            if (!legal) legal = document.querySelector('.nn-footer-legal');
            if (legal) {
                var a = document.createElement('a');
                a.href = '#';
                a.setAttribute('data-nn-cookie-settings', '1');
                a.textContent = label;
                var sep = document.createElement('span');
                sep.setAttribute('aria-hidden', 'true');
                sep.textContent = ' · ';
                var privacy = legal.querySelector('a[href*="privacy-policy"]');
                if (privacy && privacy.parentNode === legal) {
                    privacy.insertAdjacentElement('afterend', sep);
                    sep.insertAdjacentElement('afterend', a);
                } else {
                    legal.appendChild(sep);
                    legal.appendChild(a);
                }
            } else {
                // Hand-written pages without .nn-footer-legal (ru/index,
                // modern-investing-resources): fall back to footer, then body.
                var host = document.querySelector('footer') || document.body;
                if (host && typeof host.appendChild === 'function') {
                    var p = document.createElement('p');
                    var fa = document.createElement('a');
                    if (p && typeof p.appendChild === 'function' && fa) {
                        p.className = 'nn-cookie-settings-fallback';
                        fa.href = '#';
                        fa.setAttribute('data-nn-cookie-settings', '1');
                        fa.textContent = label;
                        p.appendChild(fa);
                        host.appendChild(p);
                    }
                }
            }
            links = document.querySelectorAll('[data-nn-cookie-settings]');
        }
        Array.prototype.forEach.call(links, function (el) {
            if (el.getAttribute('data-nn-cookie-settings-bound') === '1') return;
            el.setAttribute('data-nn-cookie-settings-bound', '1');
            el.addEventListener('click', function (ev) {
                ev.preventDefault();
                reopenBanner();
            });
        });
    }

    function onReady(fn) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fn);
        } else {
            fn();
        }
    }

    document.addEventListener('keydown', function (ev) {
        if (ev.key !== 'Escape') return;
        var banner = document.getElementById('nn-consent-banner');
        if (!banner || banner.style.display === 'none' || banner.hasAttribute('hidden')) return;
        rejectAll(banner);
    });

    window.NNConsent = window.NNConsent || {};
    window.NNConsent.CONSENT_MODE = CONSENT_MODE;
    window.NNConsent.STORAGE_KEY = STORAGE_KEY;
    window.NNConsent.BANNER_COPY = BANNER_COPY;
    window.NNConsent.BANNER_COPY_RU = BANNER_COPY_RU;
    window.NNConsent.BODY_LEAD_BY_MODE = BODY_LEAD_BY_MODE;
    window.NNConsent.BODY_LEAD_BY_MODE_RU = BODY_LEAD_BY_MODE_RU;
    window.NNConsent.bodyBeforePrivacy = bodyBeforePrivacy;
    window.NNConsent.isRu = isRu;
    window.NNConsent.bannerCopy = bannerCopy;
    window.NNConsent.syncToggles = syncToggles;
    window.NNConsent.isAdUserDataGranted = isAdUserDataGranted;
    window.NNConsent.isAnalyticsGranted = isAnalyticsGranted;
    window.NNConsent.hasChosen = hasChosen;
    window.NNConsent.readStored = readStored;
    window.NNConsent.normalizeStored = normalizeStored;
    window.NNConsent.applyConsent = applyConsent;
    window.NNConsent.saveChoices = saveChoices;
    window.NNConsent.acceptAll = acceptAll;
    window.NNConsent.rejectAll = rejectAll;
    window.NNConsent.reopen = reopenBanner;
    window.NNConsent.showBanner = showBanner;
    window.NNConsent.ensureGtagLoaded = ensureGtagLoaded;
    window.NNConsent.ensureCookieSettingsLink = ensureCookieSettingsLink;

    onReady(function () {
        ensureCookieSettingsLink();
        if (!hasChosen()) {
            // SSR banner is already in the DOM (base.html.j2); bind handlers
            // and keep html.nn-consent-needed so the compact bar stays visible.
            showBanner();
        } else {
            // Returning visitor: ensure the SSR node stays out of the a11y tree.
            hideBanner(document.getElementById('nn-consent-banner'));
        }
    });
})();
