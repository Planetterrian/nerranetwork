/**
 * Nerra Network — Cookie Consent Banner
 *
 * Implements Google Consent Mode v2:
 *   - Default: all consent denied (analytics, ads, personalization)
 *   - User clicks Accept All → grant consent for analytics + ads
 *   - User clicks Reject All → deny remains, banner dismisses
 *   - Choice persists in localStorage for 365 days
 *
 * Place this BEFORE the gtag.js script tag so the defaults register
 * before any tracking calls fire.
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'nn_consent_v1';
    var STORAGE_DAYS = 365;

    // Initialize consent defaults BEFORE gtag.js loads
    window.dataLayer = window.dataLayer || [];
    function gtag() { window.dataLayer.push(arguments); }
    window.gtag = window.gtag || gtag;

    // Read stored consent (if any)
    function readStored() {
        try {
            var raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return null;
            var parsed = JSON.parse(raw);
            // Expire after STORAGE_DAYS
            var ageMs = Date.now() - (parsed.timestamp || 0);
            if (ageMs > STORAGE_DAYS * 24 * 60 * 60 * 1000) return null;
            return parsed;
        } catch (e) { return null; }
    }

    function writeStored(state) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                state: state,
                timestamp: Date.now(),
            }));
        } catch (e) { /* localStorage unavailable */ }
    }

    function applyConsent(state) {
        var grant = state === 'accepted' ? 'granted' : 'denied';
        gtag('consent', 'update', {
            'ad_storage': grant,
            'ad_user_data': grant,
            'ad_personalization': grant,
            'analytics_storage': grant,
        });
    }

    // Set defaults: deny everything until user chooses
    var stored = readStored();
    var initialState = (stored && stored.state) || 'pending';
    gtag('consent', 'default', {
        'ad_storage': 'denied',
        'ad_user_data': 'denied',
        'ad_personalization': 'denied',
        'analytics_storage': 'denied',
        'wait_for_update': 500,
    });
    // Consent Mode v2 cookieless measurement (June 2026 marketing-
    // readiness review): with denied defaults, these two flags let
    // Google Ads attribute conversions via URL passthrough + send
    // redacted cookieless pings instead of losing every non-consenting
    // visitor's conversion entirely.
    gtag('set', 'url_passthrough', true);
    gtag('set', 'ads_data_redaction', true);
    if (stored && stored.state === 'accepted') {
        applyConsent('accepted');
    }

    // Don't show banner if user already chose
    if (initialState !== 'pending') return;

    // Show the banner once DOM is ready
    function showBanner() {
        if (document.getElementById('nn-consent-banner')) return;
        var banner = document.createElement('div');
        banner.id = 'nn-consent-banner';
        banner.setAttribute('role', 'dialog');
        banner.setAttribute('aria-label', 'Cookie consent');
        banner.innerHTML = '' +
            '<div class="nn-consent-text">' +
                'We use cookies to understand how listeners find Nerra Network and to measure our marketing. ' +
                '<a href="/privacy-policy.html">Privacy Policy</a>.' +
            '</div>' +
            '<div class="nn-consent-actions">' +
                '<button type="button" class="nn-consent-btn nn-consent-reject">Reject</button>' +
                '<button type="button" class="nn-consent-btn nn-consent-accept">Accept</button>' +
            '</div>';
        document.body.appendChild(banner);

        function dismiss(state) {
            writeStored(state);
            applyConsent(state);
            banner.style.display = 'none';
        }
        banner.querySelector('.nn-consent-accept').addEventListener('click', function () { dismiss('accepted'); });
        banner.querySelector('.nn-consent-reject').addEventListener('click', function () { dismiss('rejected'); });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', showBanner);
    } else {
        showBanner();
    }
})();
