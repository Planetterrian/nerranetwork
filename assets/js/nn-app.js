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
 *   - Oct 29 2026: offers the app once in a while as a small sheet at the
 *     bottom of the page (a returning visitor, a member, or someone who
 *     just pressed play), never inside the app, never twice in a session,
 *     and not again for SHEET_SNOOZE_DAYS after "Not now"; and sets the app
 *     badge while a member's edition for today is built and unplayed.
 * Events: app_install_prompt (outcome), app_installed, app_open (standalone),
 *   app_sheet (shown | install | how | dismiss).
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
  // Since iOS 16.4 every iPhone browser can add a page to the Home Screen
  // from its Share menu; an in-app browser (Instagram, Facebook) cannot.
  var isInApp = /FBAN|FBAV|Instagram|Line\/|Twitter|LinkedInApp/i.test(ua);
  var isMacSafari = /macintosh/i.test(ua) && isSafari && !(navigator.maxTouchPoints > 1);
  function iosCanAdd() { return isIos && !isInApp; }
  function paintInstall() {
    var dismissed = load('nnApp.dismissed') === '1';
    document.querySelectorAll('[data-nn-install]').forEach(function (n) {
      var optional = n.hasAttribute('data-nn-dismissable');
      n.hidden = standalone || !deferred || (optional && dismissed);
    });
    document.querySelectorAll('[data-nn-install-ios]').forEach(function (n) {
      var optional = n.hasAttribute('data-nn-dismissable');
      n.hidden = standalone || !iosCanAdd() || (optional && dismissed);
    });
    // Oct 29 2026: Safari on a Mac adds a site to the Dock (File > Add to
    // Dock); an in-app browser has to hand the page to Safari or Chrome.
    document.querySelectorAll('[data-nn-install-mac]').forEach(function (n) { n.hidden = standalone || !isMacSafari; });
    document.querySelectorAll('[data-nn-install-inapp]').forEach(function (n) { n.hidden = standalone || !isInApp; });
    document.querySelectorAll('[data-nn-installed]').forEach(function (n) { n.hidden = !standalone; });
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
  // ------------------------------------------------------------ the sheet
  var SHEET_SNOOZE_DAYS = 14;
  var DAY = 86400000;
  function today() { return new Date().toISOString().slice(0, 10); }
  function visitDays() {
    // Distinct days this browser opened the site (a returning reader is the
    // one worth asking).
    var v = {};
    try { v = JSON.parse(load('nnApp.visits') || '{}') || {}; } catch (e) { v = {}; }
    var d = today();
    if (v.last !== d) { v.days = (v.days || 0) + 1; v.last = d; save('nnApp.visits', JSON.stringify(v)); }
    return v.days || 1;
  }
  var sheetShown = false;
  function sheetAllowed() {
    if (standalone || sheetShown) { return false; }
    if (!(deferred || iosCanAdd())) { return false; }
    if (/\/(app|add|offline)\.html$/.test(location.pathname)) { return false; }
    var snoozed = Number(load('nnApp.sheetSnoozed') || 0);
    if (snoozed && Date.now() - snoozed < SHEET_SNOOZE_DAYS * DAY) { return false; }
    try { if (sessionStorage.getItem('nnApp.sheet')) { return false; } } catch (e) {}
    // Never over the cookie choice.
    if (root.classList.contains('nn-consent-needed')) {
      var banner = document.getElementById('nn-consent-banner');
      if (banner && banner.offsetParent !== null) { return false; }
    }
    return true;
  }
  function showSheet(reason, member) {
    if (!sheetAllowed()) { return; }
    sheetShown = true;
    try { sessionStorage.setItem('nnApp.sheet', '1'); } catch (e) {}
    var el = document.createElement('div');
    el.className = 'nn-app-sheet';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-labelledby', 'nn-app-sheet-h');
    var title = member ? 'Put My Nerra on your Home Screen' : 'Get the Nerra app';
    var lede = member
      ? 'Your shows, your edition and the player, one tap from your Home Screen. It opens full screen and keeps playing on the lock screen.'
      : "Free, nothing to download from a store. Today's stories in one tap, and the player keeps going on your lock screen.";
    el.innerHTML =
      '<img src="/assets/app/icon-192.png" alt="" width="48" height="48">' +
      '<div class="nn-app-sheet-body"><p class="nn-app-sheet-h" id="nn-app-sheet-h"></p><p class="nn-app-sheet-p"></p>' +
      '<ol class="nn-app-sheet-steps" hidden><li>Tap <b>Share</b> <span aria-hidden="true">⬆︎</span> in the browser bar</li><li>Choose <b>Add to Home Screen</b></li><li>Tap <b>Add</b></li></ol></div>' +
      '<div class="nn-app-sheet-actions">' +
        (deferred ? '<button type="button" class="nn-app-btn" data-sheet="install">Install</button>'
                  : '<button type="button" class="nn-app-btn" data-sheet="how">Show me how</button>') +
        '<a class="nn-app-sheet-more" href="/app.html">How it works</a>' +
        '<button type="button" class="nn-app-x" data-sheet="later" aria-label="Not now">✕</button>' +
      '</div>';
    el.querySelector('.nn-app-sheet-h').textContent = title;
    el.querySelector('.nn-app-sheet-p').textContent = lede;
    el.addEventListener('click', function (ev) {
      var b = ev.target.closest('[data-sheet]');
      if (!b) { return; }
      var a = b.getAttribute('data-sheet');
      if (a === 'install' && deferred) {
        track('app_sheet', { action: 'install', reason: reason });
        var d = deferred; deferred = null; d.prompt();
        (d.userChoice || Promise.resolve({ outcome: 'unknown' })).then(function (c) {
          track('app_install_prompt', { outcome: c && c.outcome, location: location.pathname, placement: 'sheet' });
          close();
        });
      } else if (a === 'how') {
        track('app_sheet', { action: 'how', reason: reason });
        el.querySelector('.nn-app-sheet-steps').hidden = false;
        b.remove();
      } else if (a === 'later') {
        track('app_sheet', { action: 'dismiss', reason: reason });
        save('nnApp.sheetSnoozed', String(Date.now()));
        close();
      }
    });
    function close() { el.classList.remove('is-open'); setTimeout(function () { el.remove(); }, 300); }
    document.body.appendChild(el);
    requestAnimationFrame(function () { el.classList.add('is-open'); });
    track('app_sheet', { action: 'shown', reason: reason });
  }
  function offerLater() {
    var days = visitDays();
    var acct = window.nnAccount || Promise.resolve(null);
    acct.then(function (a) {
      var member = !!(a && a.member && !a.verify_required);
      if (member || days >= 2) {
        setTimeout(function () { showSheet(member ? 'member' : 'returning', member); }, 6000);
      }
      badge(a);
    }).catch(function () {});
    // Someone who just pressed play is the likeliest to want it back.
    if (window.NNPlayer && NNPlayer.onChange) {
      NNPlayer.onChange(function (st) { if (st.playing) { setTimeout(function () { showSheet('played', false); }, 20000); } });
    }
  }

  // ------------------------------------------------------------ the badge
  // A member's edition for today is built and not yet played on this device
  // (the player stamps nnMe.editionDone with the edition's date).
  function badge(acct) {
    if (!('setAppBadge' in navigator)) { return; }
    try {
      var t = acct && acct.member && acct.member.today;
      var done = String(load('nnMe.editionDone') || '').replace(/"/g, '');
      if (t && t.built_at && t.date && done !== t.date) { navigator.setAppBadge(1).catch(function () {}); }
      else { navigator.clearAppBadge().catch(function () {}); }
    } catch (e) {}
  }

  function init() {
    paintInstall();
    offerLater();
    if (standalone) {
      tabBar();
      var first = true;
      try { first = !sessionStorage.getItem('nnApp.opened'); sessionStorage.setItem('nnApp.opened', '1'); } catch (e) {}
      if (first) { track('app_open', { location: location.pathname }); }
    }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();
