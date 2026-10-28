/**
 * Nerra Network — the web app layer (Oct 28 2026).
 *
 * The site is installable (manifest.webmanifest + sw.js). This script:
 *   - registers the service worker (https only, never inside a frame);
 *   - marks the page ``html.nn-standalone`` when it runs as the installed
 *     app and gives it a bottom tab bar (Today, Watch, Shows, My Nerra),
 *     which the browser's own chrome otherwise provides;
 *   - turns every ``[data-nn-install]`` element into an Install button when
 *     the browser offers an install (Chrome, Edge, Android), and every
 *     ``[data-nn-install-ios]`` element into the Share > Add to Home Screen
 *     hint on iPhone/iPad Safari, where no install prompt exists. Both stay
 *     hidden when the app is already installed or nothing can install it.
 * Events: app_install_prompt (outcome), app_installed, app_open (standalone).
 */
(function () {
  'use strict';
  function track(name, params) {
    try {
      if (typeof window.gtag === 'function') { window.gtag('event', name, params || {}); }
      if (typeof window.plausible === 'function') { window.plausible(name, { props: params || {} }); }
    } catch (e) {}
  }
  function load(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function save(key, val) { try { localStorage.setItem(key, val); } catch (e) {} }

  var root = document.documentElement;
  var standalone = false;
  try { standalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true; } catch (e) {}
  if (standalone) { root.classList.add('nn-standalone'); }

  // Service worker: never in a frame, never over http (localhost excepted).
  if ('serviceWorker' in navigator && window.top === window
      && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
    });
  }

  // ------------------------------------------------------------ install
  var deferred = null;
  var ua = navigator.userAgent || '';
  var isIos = /iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1);
  var isSafari = /safari/i.test(ua) && !/crios|fxios|edgios|android/i.test(ua);
  function paintInstall() {
    var dismissed = load('nnApp.dismissed') === '1';
    document.querySelectorAll('[data-nn-install]').forEach(function (n) {
      var optional = n.hasAttribute('data-nn-dismissable');
      n.hidden = standalone || !deferred || (optional && dismissed);
    });
    document.querySelectorAll('[data-nn-install-ios]').forEach(function (n) {
      var optional = n.hasAttribute('data-nn-dismissable');
      n.hidden = standalone || !(isIos && isSafari) || (optional && dismissed);
    });
  }
  window.addEventListener('beforeinstallprompt', function (ev) {
    ev.preventDefault();
    deferred = ev;
    paintInstall();
  });
  window.addEventListener('appinstalled', function () {
    deferred = null;
    track('app_installed', { location: location.pathname });
    paintInstall();
  });
  document.addEventListener('click', function (ev) {
    var go = ev.target.closest ? ev.target.closest('[data-nn-install-go]') : null;
    if (go && deferred) {
      ev.preventDefault();
      var d = deferred;
      deferred = null;
      d.prompt();
      (d.userChoice || Promise.resolve({ outcome: 'unknown' })).then(function (c) {
        track('app_install_prompt', { outcome: c && c.outcome, location: location.pathname });
        paintInstall();
      });
      return;
    }
    var x = ev.target.closest ? ev.target.closest('[data-nn-install-dismiss]') : null;
    if (x) { ev.preventDefault(); save('nnApp.dismissed', '1'); paintInstall(); }
  });

  // ------------------------------------------------------------ tab bar
  var TABS = [
    { href: '/', label: 'Today', match: /^\/(index\.html)?$/,
      icon: '<path d="M4 5h16v14H4z M8 9h8 M8 13h8 M8 16h5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' },
    { href: '/watch.html', label: 'Watch', match: /^\/watch\.html$/,
      icon: '<rect x="3" y="5" width="18" height="14" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M10 9.5v5l4.5-2.5z" fill="currentColor"/>' },
    { href: '/explore.html', label: 'Shows', match: /^\/explore\.html$/,
      icon: '<rect x="4" y="4" width="7" height="7" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="13" y="4" width="7" height="7" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="4" y="13" width="7" height="7" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="13" y="13" width="7" height="7" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.8"/>' },
    { href: '/account.html', label: 'My Nerra', match: /^\/(account|join)\.html$/,
      icon: '<circle cx="12" cy="9" r="3.6" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M5 19.5c1.4-3.2 4-4.8 7-4.8s5.6 1.6 7 4.8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>' },
  ];
  function tabBar() {
    var nav = document.createElement('nav');
    nav.className = 'nn-tabbar';
    nav.setAttribute('aria-label', 'App');
    var path = location.pathname;
    var active = -1;
    TABS.forEach(function (t, i) { if (active === -1 && t.match.test(path)) { active = i; } });
    nav.innerHTML = TABS.map(function (t, i) {
      return '<a href="' + t.href + '"' + (i === active ? ' aria-current="page" class="is-on"' : '') + '>'
        + '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false">' + t.icon + '</svg><span>' + t.label + '</span></a>';
    }).join('');
    document.body.appendChild(nav);
    var set = function () { root.style.setProperty('--nn-tabbar-h', nav.offsetHeight + 'px'); };
    set();
    window.addEventListener('resize', set);
  }
  function init() {
    paintInstall();
    if (standalone) {
      tabBar();
      var first = true;
      try { first = !sessionStorage.getItem('nnApp.opened'); sessionStorage.setItem('nnApp.opened', '1'); } catch (e) {}
      if (first) { track('app_open', { location: location.pathname }); }
    }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();
