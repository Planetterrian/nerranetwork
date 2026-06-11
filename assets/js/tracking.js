/**
 * Nerra Network — Marketing Event Tracking
 *
 * Wraps gtag() and Plausible event calls so they're safe no-ops when
 * analytics aren't configured. Tracks key conversions:
 *   - Newsletter signup (Buttondown form submit)
 *   - Podcast directory click (Apple, Spotify, RSS)
 *   - Episode play (audio element play event)
 *
 * Cookie consent is managed via Google Consent Mode v2 — gtag is
 * loaded but ad/analytics storage is denied until the user accepts.
 */
(function () {
    'use strict';

    // Safe wrapper — does nothing if gtag isn't loaded
    function track(eventName, params) {
        try {
            if (typeof window.gtag === 'function') {
                window.gtag('event', eventName, params || {});
            }
            // Plausible custom events (alias if loaded)
            if (typeof window.plausible === 'function') {
                window.plausible(eventName, { props: params || {} });
            }
        } catch (e) {
            // Never let tracking break the page
            if (window.console) console.warn('Tracking failed:', e);
        }
    }

    // ----- Newsletter signup tracking -----
    // Buttondown forms post to a target popup window — we tag them
    // before submission so they can be associated with the visitor.
    function attachNewsletterTracking() {
        var forms = document.querySelectorAll('form[action*="buttondown.com/api/emails/embed-subscribe"]');
        forms.forEach(function (form) {
            form.addEventListener('submit', function () {
                var tags = [];
                form.querySelectorAll('input[name="tag"]:checked').forEach(function (cb) {
                    tags.push(cb.value);
                });
                // transport_type beacon: the form navigates to
                // Buttondown immediately after submit, and non-beacon
                // gtag hits fired during unload are frequently lost —
                // fatal for an Ads campaign optimizing on this
                // conversion (June 2026 marketing-readiness review).
                track('newsletter_signup', {
                    tags: tags.join(','),
                    tag_count: tags.length,
                    location: window.location.pathname,
                    transport_type: 'beacon',
                });
                // Fire Google Ads conversion if configured
                if (window._GOOGLE_ADS_SIGNUP_TARGET) {
                    track('conversion', {
                        send_to: window._GOOGLE_ADS_SIGNUP_TARGET,
                        transport_type: 'beacon',
                    });
                }
            });
        });
    }

    // ----- Outbound podcast directory tracking -----
    // Detects clicks on Apple Podcasts, Spotify, and RSS subscribe
    // buttons so we can attribute subscriber acquisition channels.
    function attachOutboundTracking() {
        document.addEventListener('click', function (e) {
            var link = e.target.closest('a[href]');
            if (!link) return;
            var href = link.getAttribute('href') || '';
            var lower = href.toLowerCase();
            var directory = null;
            if (lower.indexOf('podcasts.apple.com') !== -1) directory = 'apple_podcasts';
            else if (lower.indexOf('open.spotify.com') !== -1) directory = 'spotify';
            else if (lower.endsWith('.rss') || lower.indexOf('/podcast.rss') !== -1) directory = 'rss';
            if (!directory) return;
            // Outbound click — beacon survives the navigation.
            track('subscribe_click', {
                transport_type: 'beacon',
                directory: directory,
                show: link.getAttribute('data-show') || 'unknown',
                location: window.location.pathname,
            });
        });
    }

    // ----- Episode play tracking -----
    function attachAudioTracking() {
        document.querySelectorAll('audio').forEach(function (audio) {
            var played = false;
            audio.addEventListener('play', function () {
                if (played) return;  // Only track first play per session
                played = true;
                track('episode_play', {
                    src: (audio.currentSrc || audio.src || '').split('?')[0],
                    location: window.location.pathname,
                });
            });
        });
    }

    // ----- Init on DOM ready -----
    function init() {
        attachNewsletterTracking();
        attachOutboundTracking();
        attachAudioTracking();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
