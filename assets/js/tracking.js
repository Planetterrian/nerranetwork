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

    // ----- Outbound podcast directory tracking -----
    // Detects clicks on Apple Podcasts, Spotify, and RSS subscribe
    // buttons so we can attribute subscriber acquisition channels.
    function attachOutboundTracking() {
        document.addEventListener('click', function (e) {
            var link = e.target.closest('a[href]');
            if (!link) return;
            var href = link.getAttribute('href') || '';
            var lower = href.toLowerCase();
            // A site visitor sent to the episode's video (Oct 28 2026): the
            // blog's Watch button and every other YouTube link. Its own
            // event — a watch is not a subscribe.
            if (lower.indexOf('youtube.com/watch') !== -1 || lower.indexOf('youtube.com/shorts/') !== -1) {
                track('watch_on_youtube', {
                    transport_type: 'beacon',
                    kind: link.getAttribute('data-nn-watch') || 'link',
                    location: window.location.pathname,
                });
                return;
            }
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

    // ----- Checkout starts (Oct 28 2026) -----
    // A click on a Nerra Personal Payment Link (data-nn-tier on the join
    // and account pages). Until now neither page's Stripe buttons sent
    // anything, so "how many visitors started paying" was unmeasured.
    function attachCheckoutTracking() {
        document.addEventListener('click', function (e) {
            var link = e.target.closest('a[data-nn-tier]');
            if (!link) return;
            track('begin_checkout', {
                transport_type: 'beacon',
                tier: link.getAttribute('data-nn-tier') || 'unknown',
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
                // The Nerra Personal sample edition is the paid product's
                // demo, not an episode: its own event, so the funnel can
                // tell "heard the sample" from "played a show" (Oct 28 2026).
                if (audio.hasAttribute('data-nn-sample')) {
                    track('play_personal_sample', {
                        placement: audio.getAttribute('data-nn-sample') || 'unknown',
                        location: window.location.pathname,
                    });
                    return;
                }
                track('episode_play', {
                    src: (audio.currentSrc || audio.src || '').split('?')[0],
                    location: window.location.pathname,
                });
            });
        });
    }

    // ----- Init on DOM ready -----
    function init() {
        attachOutboundTracking();
        attachCheckoutTracking();
        attachAudioTracking();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
