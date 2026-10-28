/*
 * Nerra Network service worker (Oct 28 2026) — what makes the site an app.
 *
 * Deliberately conservative, because a service worker that serves a stale
 * page outlives the deploy that fixes it:
 *   - pages are NETWORK FIRST: a visitor online always gets today's page;
 *     the cached copy is only for a dead connection, then offline.html;
 *   - styles, scripts, fonts, covers and app icons are stale-while-revalidate
 *     (served from cache, refreshed in the background);
 *   - site JSON (api/*.json, site/data/*.json) is network first;
 *   - NOTHING cross-origin is touched: episode audio (audio.nerranetwork.com,
 *     the OP3 prefix), the account Worker (api.nerranetwork.com), YouTube and
 *     analytics all go straight to the network, and no Range request (audio
 *     seeking) is ever answered from a cache.
 * Bump VERSION when this file's behaviour changes; old caches are deleted on
 * activate. A broken worker is replaced by publishing a new sw.js.
 */
var VERSION = 'nn-2026-10-28';
var PAGES = VERSION + '-pages';
var STATIC = VERSION + '-static';
var DATA = VERSION + '-data';
var PAGE_LIMIT = 40;
var PRECACHE = ['/offline.html', '/styles/main.css', '/assets/js/nn-player.js', '/assets/js/nn-app.js',
  '/assets/app/icon-192.png', '/assets/nerra-logo-icon.svg'];

self.addEventListener('install', function (event) {
  event.waitUntil(caches.open(STATIC).then(function (c) { return c.addAll(PRECACHE); }).catch(function () {}));
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf(VERSION) !== 0; })
      .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function trim(cacheName, max) {
  caches.open(cacheName).then(function (c) {
    c.keys().then(function (keys) {
      if (keys.length > max) { c.delete(keys[0]).then(function () { trim(cacheName, max); }); }
    });
  });
}

function networkFirst(request, cacheName, fallbackUrl) {
  return fetch(request).then(function (res) {
    if (res && res.ok && res.type === 'basic') {
      var copy = res.clone();
      caches.open(cacheName).then(function (c) { c.put(request, copy); if (cacheName === PAGES) { trim(PAGES, PAGE_LIMIT); } });
    }
    return res;
  }).catch(function () {
    return caches.match(request, { ignoreSearch: cacheName === PAGES }).then(function (hit) {
      return hit || (fallbackUrl ? caches.match(fallbackUrl) : Response.error());
    });
  });
}

function staleWhileRevalidate(request) {
  return caches.open(STATIC).then(function (c) {
    return c.match(request).then(function (hit) {
      var fresh = fetch(request).then(function (res) {
        if (res && res.ok && res.type === 'basic') { c.put(request, res.clone()); }
        return res;
      }).catch(function () { return hit; });
      return hit || fresh;
    });
  });
}

self.addEventListener('fetch', function (event) {
  var req = event.request;
  if (req.method !== 'GET' || req.headers.has('range')) { return; }
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) { return; }
  if (/\.(mp3|m4a|m4b|mp4|wav|zip|epub)$/i.test(url.pathname)) { return; }
  if (req.mode === 'navigate') {
    event.respondWith(networkFirst(req, PAGES, '/offline.html'));
    return;
  }
  if (/^\/(api|site\/data)\/.*\.json$/.test(url.pathname)) {
    event.respondWith(networkFirst(req, DATA, null));
    return;
  }
  if (/^\/(styles|assets\/js|assets\/fonts|assets\/covers|assets\/app)\//.test(url.pathname)
      || /\.(svg|woff2?)$/i.test(url.pathname)) {
    event.respondWith(staleWhileRevalidate(req));
  }
});
