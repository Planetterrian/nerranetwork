/**
 * Sitewide Worker subscribe forms (footer / homepage / join / show /
 * Soft Personal / blog).
 *
 * Posts JSON to the gallery Worker (/api/subscribe). Bound via
 * data-nn-subscribe on the form — never an inline onsubmit — because
 * Jinja ``| tojson`` inside a double-quoted HTML attribute was truncating
 * the handler (2026-09-27 audit): submit fell through to a GET of the
 * current page and put the email in the URL.
 *
 * Forms must carry method="post" so a no-JS submit cannot leak the
 * address into the query string either.
 *
 * Source attribution (Sep 2026 Soft Personal capture pass): when the
 * landing URL carries utm_source (youtube / youtube_ru / youtube_fr /
 * …), map it to the Worker's SOURCE_TAGS allow-list (src-youtube, …)
 * instead of always sending the page default (src-nerranetwork). Mirror
 * of engine.funnel.source_tag() + workers/gallery SOURCE_TAGS.
 */
(function () {
  'use strict';

  var API_URL = 'https://api.nerranetwork.com/api/subscribe';

  // Closed map: utm_source value → Worker source tag. Anything not listed
  // falls through to the form's data-source (server default). Keep in sync
  // with workers/gallery/src/handlers.ts SOURCE_TAGS.
  var UTM_SOURCE_TAGS = {
    youtube: 'src-youtube',
    youtube_ru: 'src-youtube-ru',
    youtube_fr: 'src-youtube-fr',
    podcast: 'src-podcast',
    newsletter: 'src-newsletter',
    x: 'src-x',
    nerranetwork: 'src-nerranetwork',
    facebook: 'src-facebook',
    linkedin: 'src-linkedin',
    whatsapp: 'src-whatsapp',
    telegram: 'src-telegram',
    email_share: 'src-email-share',
  };

  function queryParams() {
    try {
      return new URLSearchParams(window.location.search);
    } catch (e) {
      return new URLSearchParams('');
    }
  }

  /**
   * Resolve the capture source tag for a form.
   * Prefer utm_source from the URL when it maps to a Worker-allowed tag;
   * otherwise use data-source (usually capture_source_site = src-nerranetwork).
   */
  function resolveSource(form) {
    var qs = queryParams();
    var utm = (qs.get('utm_source') || '').trim().toLowerCase();
    if (utm && UTM_SOURCE_TAGS[utm]) {
      return UTM_SOURCE_TAGS[utm];
    }
    // Already-tagged value (?utm_source=src-youtube) — accept only if it is
    // on the allow-list shape.
    if (utm.indexOf('src-') === 0) {
      var bare = utm.slice(4).replace(/-/g, '_');
      if (UTM_SOURCE_TAGS[bare]) return UTM_SOURCE_TAGS[bare];
    }
    var fallback = (form && form.getAttribute('data-source')) || '';
    return fallback || 'src-nerranetwork';
  }

  function labels(form) {
    return {
      loading: form.getAttribute('data-label-loading') || 'Subscribing…',
      done: form.getAttribute('data-label-done') || 'Check your email ✓',
      idle: form.getAttribute('data-label-idle') || 'Subscribe',
      error: form.getAttribute('data-label-error') || 'Something went wrong — try again',
      needTags: form.getAttribute('data-label-need-tags') || 'Please pick at least one show to subscribe to.',
      invalidEmail: form.getAttribute('data-label-invalid-email') ||
        'That email doesn’t look right. Try again, or start Personal now at nerranetwork.com/join.',
      softDone: form.getAttribute('data-label-soft-done') ||
        'You’re on the list. Shows stay free either way.',
    };
  }

  function statusEl(form) {
    return form.querySelector('[data-nn-subscribe-status], .nn-subscribe-status, .spi-status');
  }

  function say(form, text, state) {
    var el = statusEl(form);
    if (!el) return;
    el.textContent = text || '';
    if (state) el.setAttribute('data-state', state);
    else el.removeAttribute('data-state');
  }

  function isSoftPersonal(form) {
    var list = (form.getAttribute('data-list') || '').trim();
    var kind = (form.getAttribute('data-nn-subscribe') || '').trim();
    return list === 'personal-interest' || kind === 'soft-personal';
  }

  function fireGa(eventName, payload) {
    if (typeof window.gtag !== 'function') return;
    window.gtag('event', eventName, payload || {});
  }

  /** Trim + lowercase — Google Ads enhanced-conversions email normalize. */
  function normalizeEmailForHash(email) {
    return String(email || '').trim().toLowerCase();
  }

  /**
   * SHA-256 hex via crypto.subtle. Resolves null when SubtleCrypto is
   * unavailable. Never logs the input.
   */
  function sha256Hex(value) {
    if (!window.crypto || !window.crypto.subtle || typeof TextEncoder === 'undefined') {
      return Promise.resolve(null);
    }
    try {
      var bytes = new TextEncoder().encode(value);
      return window.crypto.subtle.digest('SHA-256', bytes).then(function (buf) {
        var arr = new Uint8Array(buf);
        var hex = '';
        for (var i = 0; i < arr.length; i++) {
          var h = arr[i].toString(16);
          hex += h.length === 1 ? '0' + h : h;
        }
        return hex;
      }).catch(function () { return null; });
    } catch (e) {
      return Promise.resolve(null);
    }
  }

  function adsUserDataConsentGranted() {
    if (window.NNConsent && typeof window.NNConsent.isAdUserDataGranted === 'function') {
      return !!window.NNConsent.isAdUserDataGranted();
    }
    // Fallback if consent.js has not attached yet: same localStorage key.
    try {
      var raw = localStorage.getItem('nn_consent_v1');
      if (!raw) return false;
      var parsed = JSON.parse(raw);
      return !!(parsed && parsed.state === 'accepted');
    } catch (e) {
      return false;
    }
  }

  /**
   * Google Ads enhanced conversions (via the Google tag): set hashed
   * email on gtag user_data immediately before soft_personal_interest_submit.
   *
   * Only when: typed email present, honeypot (company) empty, and
   * ad_user_data / ads consent granted. Skip silently otherwise. Never
   * blocks the subscribe POST — callers chain this only around the GA
   * event after a successful save. Never logs or stores the email.
   *
   * @returns {Promise<boolean>} true when user_data was set
   */
  function maybeSetEnhancedConversionUserData(email, company) {
    var normalized = normalizeEmailForHash(email);
    if (!normalized) return Promise.resolve(false);
    if ((company || '').trim()) return Promise.resolve(false);
    if (!adsUserDataConsentGranted()) return Promise.resolve(false);
    if (typeof window.gtag !== 'function') return Promise.resolve(false);

    return sha256Hex(normalized).then(function (hash) {
      if (!hash) return false;
      window.gtag('set', 'user_data', { sha256_email_address: hash });
      return true;
    }).catch(function () {
      return false;
    });
  }

  /**
   * Fire soft_personal_interest_submit, setting enhanced-conversion
   * user_data first when allowed. Always fires the event (hash/consent
   * failures are silent). Does not touch the subscribe request.
   */
  function fireSoftPersonalInterestSubmit(email, company, payload) {
    var eventPayload = payload || {};
    function emit() {
      fireGa('soft_personal_interest_submit', eventPayload);
    }
    maybeSetEnhancedConversionUserData(email, company).then(emit, emit);
  }

  function bind(form) {
    if (form.getAttribute('data-nn-subscribe-bound') === '1') return;
    form.setAttribute('data-nn-subscribe-bound', '1');

    form.addEventListener('submit', function (e) {
      e.preventDefault();

      var L = labels(form);
      var soft = isSoftPersonal(form);
      var boxes = form.querySelectorAll('input[name=tag]:checked');
      if (form.getAttribute('data-require-tags') === '1' && boxes.length === 0) {
        window.alert(L.needTags);
        return;
      }

      var btn = form.querySelector('button[type=submit], button:not([type])');
      if (!btn) return;
      var emailInput = form.querySelector('input[name=email], input[type=email]');
      if (!emailInput) return;
      var email = (emailInput.value || '').trim();
      if (!email || email.indexOf('@') < 1 || email.indexOf('.') < 0) {
        if (soft) {
          say(form, L.invalidEmail, 'error');
          emailInput.focus();
        }
        return;
      }

      var tags = Array.prototype.map.call(boxes, function (c) { return c.value; });
      // Hidden show-tag inputs (newsletter forms that pin one show).
      form.querySelectorAll('input[type=hidden][name=tag]').forEach(function (h) {
        if (h.value && tags.indexOf(h.value) < 0) tags.push(h.value);
      });

      var source = resolveSource(form);
      var redirect = form.getAttribute('data-success-redirect') || '';
      var list = (form.getAttribute('data-list') || (soft ? 'personal-interest' : 'member')).trim();
      var companyInput = form.querySelector('input[name=company]');
      var company = companyInput ? (companyInput.value || '').trim() : '';
      var firstNameInput = form.querySelector('input[name=first_name]');
      var firstName = firstNameInput ? (firstNameInput.value || '').trim() : '';

      btn.disabled = true;
      btn.textContent = L.loading;
      say(form, soft ? 'Saving…' : '', '');

      var body = {
        email: email,
        list: list,
        tags: tags,
        source: source,
      };
      if (soft) {
        body.company = company;
        if (firstName) body.first_name = firstName;
      }

      fetch(API_URL, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (data) {
          return { ok: r.ok, status: r.status, data: data };
        });
      }).then(function (r) {
        // Soft Personal (and honest newsletter UX): require HTTP 200 +
        // {ok:true}. Never celebrate on a 4xx/5xx or a non-ok body.
        var success = r.ok && r.data && r.data.ok === true;
        if (!success) {
          throw new Error('fail');
        }
        // Oct 11 2026: a real signup is a GA4 conversion. Until now no
        // first-party form fired one, so the funnel's "0 signups" meant
        // unmeasured. Sent as a beacon so the join page's redirect cannot
        // drop it. Read by scripts/fetch_ga4_stats.py CONVERSION_EVENTS.
        if (!soft) {
          fireGa('newsletter_signup', {
            list: list,
            source: source || 'direct',
            show_tags: tags.join(','),
            page_path: window.location.pathname || '',
            already_subscribed: !!(r.data && r.data.alreadySubscribed),
            transport_type: 'beacon',
          });
        }
        if (redirect) {
          window.location = redirect;
          return;
        }
        if (soft) {
          btn.textContent = form.getAttribute('data-label-done') || 'Saved ✓';
          say(form, L.softDone, 'ok');
          var confirmSel = form.getAttribute('data-confirm-selector');
          if (confirmSel) {
            var confirmEl = document.querySelector(confirmSel);
            if (confirmEl) confirmEl.classList.add('is-visible');
          }
          // Hide the form fields when a confirm panel is present (Soft
          // Personal page). One-field hero forms keep the button label.
          if (form.getAttribute('data-hide-on-success') === '1') {
            form.hidden = true;
          }
          // Enhanced conversions: consent-gated SHA-256 email on gtag
          // user_data immediately before the north-star event. Skip
          // silently when consent denied / honeypot filled / no email.
          fireSoftPersonalInterestSubmit(email, company, {
            form_id: form.getAttribute('data-form-id') || 'personal-interest',
            page_path: window.location.pathname || '',
            list: list,
            source: source || 'direct',
            show: form.getAttribute('data-show') || undefined,
          });
        } else {
          btn.textContent = L.done;
          var a = form.querySelector('.nn-account-link');
          if (a) a.style.display = 'inline';
        }
      }).catch(function () {
        btn.textContent = L.error;
        btn.disabled = false;
        if (soft) {
          say(
            form,
            form.getAttribute('data-label-error') ||
              'Couldn’t save that just now. Try again in a moment — or start Personal whenever you’re ready at nerranetwork.com/join.',
            'error'
          );
        }
      });
    });
  }

  function init() {
    document.querySelectorAll('form[data-nn-subscribe]').forEach(bind);
  }

  // Public: Soft Personal page (and any inline handler) reuses the same map
  // + enhanced-conversion helpers (hashed email only; never the raw address).
  window.NNSubscribe = window.NNSubscribe || {};
  window.NNSubscribe.resolveSource = resolveSource;
  window.NNSubscribe.UTM_SOURCE_TAGS = UTM_SOURCE_TAGS;
  window.NNSubscribe.normalizeEmailForHash = normalizeEmailForHash;
  window.NNSubscribe.sha256Hex = sha256Hex;
  window.NNSubscribe.maybeSetEnhancedConversionUserData =
    maybeSetEnhancedConversionUserData;
  window.NNSubscribe.fireSoftPersonalInterestSubmit =
    fireSoftPersonalInterestSubmit;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
