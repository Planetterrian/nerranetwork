/**
 * The front page's For you band (Oct 28 2026). See network_page.html.j2.
 *
 * Visitor: the show picker keeps its picks in this browser
 * (localStorage nnMe.draft = {shows, ts}); My Nerra saves them as the
 * lineup of an account that has none. Member: the newest episode of each
 * of their shows, in their order, from api/personal_front.json, played by
 * the site player (assets/js/nn-player.js) as one queue.
 * Story text reaches the page through textContent only.
 */
(function () {
  'use strict';
  var band = document.querySelector('[data-nn-you]');
  if (!band) { return; }
  var prefix = band.getAttribute('data-prefix') || '';
  var DRAFT = 'nnMe.draft';
  function load(k) { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } }
  function save(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  function track(name, params) {
    try { if (typeof window.gtag === 'function') { window.gtag('event', name, params || {}); } } catch (e) {}
  }
  function safeUrl(u) { u = String(u || ''); return /^https:\/\//.test(u) || /^[a-z0-9_-]+[/.]/i.test(u) ? u : ''; }
  function easternDay() {
    try { return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' }).format(new Date()); } catch (e) { return ''; }
  }

  // ------------------------------------------------------------ visitor
  var picks = ((load(DRAFT) || {}).shows || []).filter(function (s) { return typeof s === 'string'; });
  var buttons = Array.prototype.slice.call(band.querySelectorAll('.nn-you-pick'));
  var count = band.querySelector('[data-nn-you-count]');
  var go = band.querySelector('[data-nn-you-go]');
  function paintPicks() {
    buttons.forEach(function (b) { b.setAttribute('aria-pressed', picks.indexOf(b.getAttribute('data-slug')) !== -1 ? 'true' : 'false'); });
    var n = picks.length;
    if (count) { count.textContent = n === 0 ? 'Pick two or more' : n === 1 ? '1 show · pick one more' : n + ' shows, in the order you tapped them'; }
  }
  buttons.forEach(function (b) {
    b.addEventListener('click', function () {
      var slug = b.getAttribute('data-slug');
      var i = picks.indexOf(slug);
      if (i === -1) { picks.push(slug); } else { picks.splice(i, 1); }
      save(DRAFT, { shows: picks, ts: Date.now() });
      paintPicks();
    });
  });
  if (go) {
    go.addEventListener('click', function () {
      save(DRAFT, { shows: picks, ts: Date.now() });
      track('build_lineup_start', { count: picks.length, placement: 'homepage', location: location.pathname });
    });
  }
  paintPicks();

  // ------------------------------------------------------------- member
  function card(slug, entry, s, n) {
    var li = document.createElement('li');
    li.style.setProperty('--show-color', entry.brand_color || '#6B47FF');
    var cover = safeUrl(s.image_url) || safeUrl(entry.cover_webp) || safeUrl(entry.cover_url);
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'nn-you-card';
    btn.setAttribute('data-nn-play', '');
    btn.setAttribute('data-nn-queue', 'for-you');
    var post = safeUrl(s.post_url);
    var attrs = { key: slug + '|' + s.episode_num, src: safeUrl(s.audio_url), title: s.hook || '', show: entry.name || '',
                  cover: cover ? (/^https:/.test(cover) ? cover : prefix + cover) : '', post: post ? prefix + post : '', color: entry.brand_color || '' };
    Object.keys(attrs).forEach(function (k) { if (attrs[k]) { btn.setAttribute('data-' + k, attrs[k]); } });
    btn.setAttribute('aria-label', 'Play ' + (entry.name || '') + ': ' + (s.hook || ''));
    var img = document.createElement('img');
    if (attrs.cover) { img.src = attrs.cover; }
    img.alt = ''; img.loading = 'lazy'; img.width = 64; img.height = 64;
    var txt = document.createElement('span'); txt.className = 'nn-you-card-txt';
    var b = document.createElement('b'); b.textContent = n + '. ' + (entry.name || '');
    var h = document.createElement('span'); h.className = 'nn-you-card-hl'; h.textContent = s.hook || '';
    var meta = document.createElement('small');
    var mins = s.duration_s ? Math.max(1, Math.round(s.duration_s / 60)) + ' min' : '';
    meta.textContent = [(s.stamp && s.stamp.day === easternDay()) ? 'Today' : ((s.stamp && s.stamp.short) || ''), mins].filter(Boolean).join(' · ');
    txt.appendChild(b); txt.appendChild(h); txt.appendChild(meta);
    var ic = document.createElement('span'); ic.className = 'nn-you-card-play'; ic.setAttribute('aria-hidden', 'true');
    btn.appendChild(img); btn.appendChild(txt); btn.appendChild(ic);
    li.appendChild(btn);
    return li;
  }
  function member(acct) {
    var m = acct && acct.member;
    var prefs = (m && m.preferences) || {};
    var shows = (prefs.shows || []).slice(0, 8);
    if (!shows.length) {
      // Signed in with no lineup yet: the picker, saving into My Nerra.
      if (go) { go.textContent = 'Save these to My Nerra'; go.href = prefix + 'account.html#customize'; }
      return;
    }
    fetch(prefix + 'api/personal_front.json').then(function (r) { return r.ok ? r.json() : null; }).then(function (front) {
      if (!front || !front.shows) { return; }
      var row = band.querySelector('[data-nn-you-row]');
      var n = 0, today = 0, secs = 0;
      shows.forEach(function (slug) {
        var entry = front.shows[slug];
        var s = entry && entry.stories && entry.stories[0];
        if (!s || !safeUrl(s.audio_url)) { return; }
        n += 1;
        if (s.stamp && s.stamp.day === easternDay()) { today += 1; secs += s.duration_s || 0; }
        row.appendChild(card(slug, entry, s, n));
      });
      if (!n) { return; }
      band.querySelector('[data-nn-you-visitor]').hidden = true;
      // A member's own shows come straight after the lead story.
      var top = document.querySelector('.lt-top');
      if (top && top.parentNode && top.nextSibling !== band) { top.parentNode.insertBefore(band, top.nextSibling); }
      band.querySelector('[data-nn-you-member]').hidden = false;
      var hour = new Date().getHours();
      var part = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
      var greet = band.querySelector('[data-nn-you-greet]');
      greet.textContent = '';
      greet.appendChild(document.createTextNode(part + (prefs.first_name ? ', ' : '.')));
      if (prefs.first_name) { var em = document.createElement('em'); em.textContent = prefs.first_name; greet.appendChild(em); greet.appendChild(document.createTextNode('.')); }
      band.querySelector('[data-nn-you-sub]').textContent = today
        ? today + ' new from your shows today' + (secs ? ', ' + Math.max(1, Math.round(secs / 60)) + ' minutes in all.' : '.')
        : 'The newest episode from each of your shows.';
      var all = band.querySelector('[data-nn-you-playall]');
      all.hidden = false;
      all.addEventListener('click', function () {
        var first = row.querySelector('[data-nn-play]');
        if (first) { first.click(); }
      });
      var paid = m && m.status === 'active';
      band.querySelector('[data-nn-you-upsell]').hidden = !!paid;
      // Oct 29 2026: a paying member's own edition, from their private feed
      // (the newest item), played by the site player.
      if (paid && m.feed_url && window.DOMParser) { edition(m.feed_url); }
    }).catch(function () {});
  }
  function edition(feedUrl) {
    var btn = band.querySelector('[data-nn-you-edition]');
    if (!btn || !/^https:\/\/api\.nerranetwork\.com\/api\/feed\//.test(feedUrl)) { return; }
    fetch(feedUrl, { credentials: 'omit' }).then(function (r) { return r.ok ? r.text() : null; }).then(function (xml) {
      if (!xml) { return; }
      var doc = new DOMParser().parseFromString(xml, 'text/xml');
      var item = doc.querySelector('item');
      var enc = item && item.querySelector('enclosure');
      var url = enc && safeUrl(enc.getAttribute('url'));
      if (!url) { return; }
      var title = (item.querySelector('title') || {}).textContent || 'Your edition';
      btn.hidden = false;
      btn.addEventListener('click', function () {
        if (!window.NNPlayer) { return; }
        NNPlayer.start([{ key: url, url: url, title: title, show: 'Your Nerra edition',
          cover: prefix + 'assets/covers/nerra-daily.jpg', post: prefix + 'account.html#nn-edition', color: '#6B47FF' }], 0);
      });
    }).catch(function () {});
  }
  function start() {
    var p = window.nnAccount;
    if (p && p.then) { p.then(function (a) { if (a && a.member !== undefined) { member(a); } }); }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', start); } else { start(); }
})();
