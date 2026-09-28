/**
 * Footer / homepage / join newsletter subscribe forms.
 *
 * Posts JSON to the gallery Worker (/api/subscribe) with list "member".
 * Bound via data-nn-subscribe on the form — never an inline onsubmit —
 * because Jinja ``| tojson`` inside a double-quoted HTML attribute was
 * truncating the handler (2026-09-27 audit): submit fell through to a
 * GET of the current page and put the email in the URL.
 *
 * Forms must carry method="post" so a no-JS submit cannot leak the
 * address into the query string either.
 */
(function () {
  'use strict';

  var API_URL = 'https://api.nerranetwork.com/api/subscribe';

  function labels(form) {
    return {
      loading: form.getAttribute('data-label-loading') || 'Subscribing…',
      done: form.getAttribute('data-label-done') || 'Check your email ✓',
      idle: form.getAttribute('data-label-idle') || 'Subscribe',
      error: form.getAttribute('data-label-error') || 'Something went wrong — try again',
      needTags: form.getAttribute('data-label-need-tags') || 'Please pick at least one show to subscribe to.',
    };
  }

  function bind(form) {
    if (form.getAttribute('data-nn-subscribe-bound') === '1') return;
    form.setAttribute('data-nn-subscribe-bound', '1');

    form.addEventListener('submit', function (e) {
      e.preventDefault();

      var L = labels(form);
      var boxes = form.querySelectorAll('input[name=tag]:checked');
      if (form.getAttribute('data-require-tags') === '1' && boxes.length === 0) {
        window.alert(L.needTags);
        return;
      }

      var btn = form.querySelector('button[type=submit], button:not([type])');
      if (!btn) return;
      var emailInput = form.querySelector('input[name=email], input[type=email]');
      if (!emailInput || !emailInput.value) return;

      var tags = Array.prototype.map.call(boxes, function (c) { return c.value; });
      var source = form.getAttribute('data-source') || 'src-nerranetwork';
      var redirect = form.getAttribute('data-success-redirect') || '';

      btn.disabled = true;
      btn.textContent = L.loading;

      fetch(API_URL, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: emailInput.value,
          list: 'member',
          tags: tags,
          source: source,
        }),
      }).then(function (r) {
        if (r.ok) {
          if (redirect) {
            window.location = redirect;
            return;
          }
          btn.textContent = L.done;
          var a = form.querySelector('.nn-account-link');
          if (a) a.style.display = 'inline';
        } else {
          btn.textContent = L.error;
          btn.disabled = false;
        }
      }).catch(function () {
        btn.textContent = L.error;
        btn.disabled = false;
      });
    });
  }

  function init() {
    document.querySelectorAll('form[data-nn-subscribe]').forEach(bind);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
