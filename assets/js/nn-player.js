/**
 * Nerra Network — the site's one player (Oct 28 2026).
 *
 * Every page shares this player: a bar at the bottom of the screen that
 * plays a queue of episodes, remembers where each one stopped, and comes
 * back (paused, one tap to resume) on the next page a visitor opens. The
 * site is a set of static pages, so a page change stops the audio; the
 * resume bar is the honest way to keep listening across pages.
 *
 * Three ways in, all declarative:
 *   - any element with ``data-nn-play`` plays the episode its data-* fields
 *     name (src, title, show, cover, post, color, key; data-nn-queue groups
 *     buttons into one queue in page order; data-nn-sample marks the
 *     Personal sample, which reports its own event);
 *   - ``audio`` elements inside ``.lt-lead-audio`` (the front page's cards)
 *     are taken over: the native control stays in the HTML for a visitor
 *     without JavaScript and is hidden behind a Listen button;
 *   - any element with ``data-nn-watch`` (a YouTube URL or id) opens the
 *     video in a privacy-enhanced embed inside the page.
 *
 * window.NNPlayer is the API other scripts use (My Nerra's lineup player).
 * Positions live in localStorage under the keys My Nerra has used since Oct
 * 28 (nnMe.pos, nnMe.played), so a story heard on one page reads as heard on
 * every other. Storage is a convenience: every read and write is guarded.
 */
(function () {
  'use strict';
  if (window.NNPlayer) { return; }

  var NOW_KEY = 'nnPlay.now';
  var RESUME_HOURS = 24;
  var RATES = [1, 1.25, 1.5, 1.75, 2, 0.8];

  function load(key) { try { var v = localStorage.getItem(key); return v ? JSON.parse(v) : null; } catch (e) { return null; } }
  function save(key, val) { try { if (val === null) { localStorage.removeItem(key); } else { localStorage.setItem(key, JSON.stringify(val)); } } catch (e) {} }
  function track(name, params) {
    try {
      if (typeof window.gtag === 'function') { window.gtag('event', name, params || {}); }
      if (typeof window.plausible === 'function') { window.plausible(name, { props: params || {} }); }
    } catch (e) {}
  }
  function safeUrl(u) {
    u = String(u || '');
    if (/^https:\/\//.test(u)) { return u; }
    if (/^(\.\.?\/|[a-z0-9_-]+[/.])/i.test(u) && !/^[a-z]+:/i.test(u)) { return u; }
    return '';
  }
  function clock(s) {
    s = Math.max(0, Math.floor(s || 0));
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    return (h ? h + ':' + (m < 10 ? '0' : '') : '') + m + ':' + (x < 10 ? '0' : '') + x;
  }
  function el(tag, cls, html) { var n = document.createElement(tag); if (cls) { n.className = cls; } if (html != null) { n.innerHTML = html; } return n; }

  var audio = new Audio();
  audio.preload = 'none';
  var RATE_KEY = 'nnPlay.rate';
  var queue = [], at = -1, rateAt = Math.max(0, RATES.indexOf(Number(load(RATE_KEY)) || 1)), lastSave = 0, seeking = false, reported = {};
  var positions = load('nnMe.pos') || {};
  var listeners = [];
  var bar = null, ui = {};

  function current() { return queue[at] || null; }
  function isPlayed(url) { var p = load('nnMe.played') || {}; return !!(url && p[url]); }
  function markPlayed(url) {
    var p = load('nnMe.played') || {};
    if (!url || p[url]) { return; }
    p[url] = 1;
    var keys = Object.keys(p); if (keys.length > 400) { delete p[keys[0]]; }
    save('nnMe.played', p);
  }
  function remember() {
    var it = current();
    if (!it) { return; }
    positions[it.url] = audio.currentTime || positions[it.url] || 0;
    var keys = Object.keys(positions); if (keys.length > 200) { delete positions[keys[0]]; }
    save('nnMe.pos', positions);
    save(NOW_KEY, { queue: queue.slice(0, 40), at: at, ts: Date.now() });
  }
  function emit() {
    if (inline.length) { paintInline(); }
    var it = current();
    var st = { key: it ? it.key : '', playing: !!(it && !audio.paused) };
    listeners.forEach(function (fn) { try { fn(st); } catch (e) {} });
    document.querySelectorAll('[data-nn-play]').forEach(function (b) {
      b.classList.toggle('is-playing', st.playing && b.getAttribute('data-key') === st.key);
    });
  }

  // ------------------------------------------------------------------ bar
  function build() {
    if (bar) { return; }
    bar = el('div', 'nn-gp');
    bar.id = 'nn-gp';
    bar.hidden = true;
    bar.setAttribute('role', 'region');
    bar.setAttribute('aria-label', 'Now playing');
    bar.innerHTML =
      '<div class="nn-gp-progress" aria-hidden="true"><span></span></div>' +
      '<div class="nn-gp-inner">' +
        '<img class="nn-gp-cover" alt="" width="48" height="48">' +
        '<div class="nn-gp-who"><b class="nn-gp-show"></b><a class="nn-gp-title" href="#"></a>' +
          '<span class="nn-gp-resume" hidden>Pick up where you left off</span></div>' +
        '<div class="nn-gp-ctl">' +
          '<button type="button" class="nn-gp-btn nn-gp-skip" data-gp="back" aria-label="Back 15 seconds">−15</button>' +
          '<button type="button" class="nn-gp-big" data-gp="toggle" aria-label="Play"><span class="ic" aria-hidden="true"></span></button>' +
          '<button type="button" class="nn-gp-btn nn-gp-skip" data-gp="fwd" aria-label="Forward 30 seconds">+30</button>' +
          '<button type="button" class="nn-gp-btn" data-gp="next" aria-label="Next episode">⏭</button>' +
        '</div>' +
        '<div class="nn-gp-bar">' +
          '<button type="button" class="nn-gp-btn nn-gp-skip-sm" data-gp="back" aria-label="Back 15 seconds">−15</button>' +
          '<span class="nn-gp-cur">0:00</span>' +
          '<input type="range" class="nn-gp-seek" min="0" max="1000" value="0" step="1" aria-label="Seek">' +
          '<span class="nn-gp-dur"></span>' +
          '<button type="button" class="nn-gp-btn nn-gp-skip-sm" data-gp="fwd" aria-label="Forward 30 seconds">+30</button></div>' +
        '<div class="nn-gp-side"><span class="nn-gp-queue"></span>' +
          '<a class="nn-read nn-gp-read" href="#" hidden><span class="ic" aria-hidden="true"></span><span class="t">Read</span></a>' +
          '<button type="button" class="nn-gp-btn" data-gp="rate" aria-label="Playback speed">' + RATES[rateAt] + '×</button>' +
          '<button type="button" class="nn-gp-btn" data-gp="close" aria-label="Close the player">✕</button></div>' +
      '</div>';
    document.body.appendChild(bar);
    ['cover', 'show', 'title', 'resume', 'cur', 'dur', 'seek', 'queue'].forEach(function (k) { ui[k] = bar.querySelector('.nn-gp-' + k); });
    ui.toggle = bar.querySelector('[data-gp="toggle"]');
    ui.next = bar.querySelector('[data-gp="next"]');
    ui.rate = bar.querySelector('[data-gp="rate"]');
    ui.fill = bar.querySelector('.nn-gp-progress span');
    ui.read = bar.querySelector('.nn-gp-read');
    bar.addEventListener('click', function (ev) {
      var b = ev.target.closest('[data-gp]');
      if (!b) { return; }
      var a = b.getAttribute('data-gp');
      if (a === 'toggle') { api.toggle(); }
      else if (a === 'back') { api.seekBy(-15); }
      else if (a === 'fwd') { api.seekBy(30); }
      else if (a === 'next') { api.next(); }
      else if (a === 'rate') { api.rate(); }
      else if (a === 'close') { api.close(); }
    });
    ui.seek.addEventListener('input', function () { seeking = true; });
    ui.seek.addEventListener('change', function () {
      seeking = false;
      if (audio.duration) { audio.currentTime = Number(ui.seek.value) / 1000 * audio.duration; }
    });
    window.addEventListener('resize', function () { if (!bar.hidden) { setOffset(true); } });
  }
  function setOffset(on) {
    var h = on && bar ? bar.offsetHeight : 0;
    document.documentElement.style.setProperty('--nn-player-h', h + 'px');
    document.documentElement.classList.toggle('nn-has-player', !!on);
  }
  function show(on) { build(); bar.hidden = !on; setOffset(on); }
  function paint(resuming) {
    var it = current();
    if (!it || !bar) { return; }
    bar.style.setProperty('--show-color', it.color || '#6B47FF');
    ui.cover.src = safeUrl(it.cover) || '';
    ui.cover.hidden = !ui.cover.src;
    ui.show.textContent = it.show || '';
    ui.title.textContent = it.title || '';
    ui.title.href = safeUrl(it.post) || '#';
    // Read (Oct 29 2026): the article of what is playing, one tap away.
    if (ui.read) {
      ui.read.hidden = !safeUrl(it.post);
      ui.read.href = safeUrl(it.post) || '#';
      ui.read.setAttribute('aria-label', 'Read the story' + (it.title ? ': ' + it.title : ''));
    }
    ui.resume.hidden = !resuming;
    if (resuming) { ui.cur.textContent = clock(positions[it.url] || 0); ui.dur.textContent = ''; }
    ui.queue.textContent = queue.length > 1 ? (at + 1) + ' of ' + queue.length : '';
    ui.next.disabled = at >= queue.length - 1;
    var playing = !audio.paused;
    ui.toggle.classList.toggle('is-playing', playing);
    ui.toggle.setAttribute('aria-label', playing ? 'Pause' : (resuming ? 'Resume' : 'Play'));
    if ('mediaSession' in navigator) {
      try {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: it.title || '', artist: it.show || 'Nerra Network', album: 'Nerra Network',
          artwork: ui.cover.src ? [{ src: new URL(ui.cover.src, location.href).href, sizes: '400x400' }] : [] });
      } catch (e) {}
    }
    emit();
  }
  function progress() {
    var d = audio.duration || 0, t = audio.currentTime || 0;
    if (inline.length) { paintInline(); }
    if (!bar) { return; }
    ui.cur.textContent = clock(t);
    ui.dur.textContent = d ? clock(d) : '';
    if (d && !seeking) { ui.seek.value = String(Math.round(t / d * 1000)); }
    ui.fill.style.width = d ? (t / d * 100).toFixed(2) + '%' : '0';
    ui.seek.setAttribute('aria-valuetext', clock(t) + (d ? ' of ' + clock(d) : ''));
    if (d && 'mediaSession' in navigator && navigator.mediaSession.setPositionState) {
      try { navigator.mediaSession.setPositionState({ duration: d, position: Math.min(t, d), playbackRate: audio.playbackRate || 1 }); } catch (e) {}
    }
  }

  // --------------------------------------------------------------- engine
  // Oct 29 2026: a member's edition URL carries their private feed token
  // (/api/feed/<token>/<file>.mp3); analytics never sees it. The edition is
  // reported as itself, by file name.
  function analyticsSrc(url) {
    var u = String(url || '').split('?')[0];
    var m = /\/api\/feed\/[^/]+\/([^/]+)$/.exec(u);
    return m ? 'personal_edition/' + m[1] : u;
  }
  function report(it) {
    if (!it || reported[it.url]) { return; }
    reported[it.url] = 1;
    // A member's edition played: the app badge for that day clears.
    var ed = /\/api\/feed\/[^/]+\/Nerra_Personal_(\d{4})(\d{2})(\d{2})/.exec(String(it.url));
    if (ed) {
      save('nnMe.editionDone', ed[1] + '-' + ed[2] + '-' + ed[3]);
      try { if (navigator.clearAppBadge) { navigator.clearAppBadge().catch(function () {}); } } catch (e) {}
    }
    if (it.sample) {
      track('play_personal_sample', { placement: it.sample, location: location.pathname });
    } else {
      track('episode_play', { src: analyticsSrc(it.url), location: location.pathname });
    }
  }
  function cue(i, autoplay) {
    if (i < 0 || i >= queue.length) { return; }
    at = i;
    var it = current();
    audio.src = it.url;
    audio.playbackRate = RATES[rateAt];
    var pos = positions[it.url];
    audio.addEventListener('loadedmetadata', function () {
      if (pos && pos > 5 && (!audio.duration || pos < audio.duration - 5)) { try { audio.currentTime = pos; } catch (e) {} }
      progress();
    }, { once: true });
    show(true);
    if (autoplay) {
      var p = audio.play();
      if (p && p.catch) { p.catch(function () { paint(true); }); }
      report(it);
    }
    paint(!autoplay);
    save(NOW_KEY, { queue: queue.slice(0, 40), at: at, ts: Date.now() });
  }
  audio.addEventListener('play', function () { paint(false); });
  audio.addEventListener('pause', function () { paint(false); remember(); });
  audio.addEventListener('timeupdate', function () {
    progress();
    if (Date.now() - lastSave > 5000) {
      lastSave = Date.now();
      remember();
      var d = audio.duration || 0;
      if (d && audio.currentTime / d > 0.9) { markPlayed((current() || {}).url); }
    }
  });
  audio.addEventListener('ended', function () {
    var it = current();
    if (it) { markPlayed(it.url); delete positions[it.url]; save('nnMe.pos', positions); }
    if (at < queue.length - 1) { cue(at + 1, true); } else { paint(false); save(NOW_KEY, null); }
  });
  window.addEventListener('pagehide', remember);
  if ('mediaSession' in navigator) {
    try {
      navigator.mediaSession.setActionHandler('nexttrack', function () { api.next(); });
      navigator.mediaSession.setActionHandler('seekbackward', function () { api.seekBy(-15); });
      navigator.mediaSession.setActionHandler('seekforward', function () { api.seekBy(30); });
      navigator.mediaSession.setActionHandler('previoustrack', function () {
        if (audio.currentTime > 5 || at <= 0) { audio.currentTime = 0; } else { cue(at - 1, true); }
      });
      navigator.mediaSession.setActionHandler('seekto', function (d) {
        if (d && typeof d.seekTime === 'number' && audio.duration) { audio.currentTime = Math.max(0, Math.min(audio.duration, d.seekTime)); progress(); }
      });
      navigator.mediaSession.setActionHandler('play', function () { api.toggle(); });
      navigator.mediaSession.setActionHandler('pause', function () { if (!audio.paused) { audio.pause(); } });
    } catch (e) {}
  }

  function normalize(items) {
    return (items || []).map(function (x) {
      return {
        key: String(x.key || x.url || ''), url: safeUrl(x.url), title: String(x.title || ''),
        show: String(x.show || ''), cover: safeUrl(x.cover), post: safeUrl(x.post),
        color: /^#[0-9a-f]{3,8}$/i.test(x.color || '') ? x.color : '', sample: x.sample ? String(x.sample) : '',
      };
    }).filter(function (x) { return x.url; });
  }

  var api = {
    // Plays a page's own <audio> through this player, from *seconds* when
    // given; false when the element has no player card (the caller then
    // plays it natively). A chapter link uses it, so the hidden native
    // element never fetches the file a second time.
    playElement: function (el, seconds) {
      for (var k = 0; k < inline.length; k++) {
        if (inline[k].native === el) { inlinePlay(inline[k], typeof seconds === 'number' ? seconds : undefined); return true; }
      }
      return false;
    },
    start: function (items, i) {
      var list = normalize(items);
      if (!list.length) { return; }
      queue = list; cue(Math.max(0, Math.min(list.length - 1, i || 0)), true);
    },
    toggle: function () {
      if (!current()) { return; }
      if (audio.paused) {
        var p = audio.play(); if (p && p.catch) { p.catch(function () {}); }
        report(current());
      } else { audio.pause(); }
    },
    seekBy: function (s) { if (audio.duration) { audio.currentTime = Math.max(0, Math.min(audio.duration - 1, audio.currentTime + s)); } },
    next: function () { if (at < queue.length - 1) { cue(at + 1, true); } },
    rate: function () {
      rateAt = (rateAt + 1) % RATES.length; audio.playbackRate = RATES[rateAt];
      if (ui.rate) { ui.rate.textContent = RATES[rateAt] + '×'; ui.rate.setAttribute('aria-label', 'Playback speed, ' + RATES[rateAt] + ' times'); }
      save(RATE_KEY, RATES[rateAt]); progress();
    },
    // Oct 29 2026: signing out forgets anything private this browser kept —
    // a member's edition carries their feed token in its URL.
    forgetPrivate: function () {
      var it = current();
      if (it && /\/api\/feed\//.test(it.url)) { api.close(); }
      var now = load(NOW_KEY);
      if (now && (now.queue || []).some(function (x) { return /\/api\/feed\//.test(x.url || ''); })) { save(NOW_KEY, null); }
      ['nnMe.pos', 'nnMe.played'].forEach(function (k) {
        var m = load(k) || {}, changed = false;
        Object.keys(m).forEach(function (u) { if (/\/api\/feed\//.test(u)) { delete m[u]; changed = true; } });
        if (changed) { save(k, m); }
      });
      positions = load('nnMe.pos') || {};
    },
    close: function () { remember(); audio.pause(); show(false); queue = []; at = -1; save(NOW_KEY, null); emit(); },
    isKey: function (key) { var it = current(); return !!(it && it.key === key); },
    isPlaying: function () { return !!current() && !audio.paused; },
    isPlayed: isPlayed,
    position: function (url) { return positions[url] || 0; },
    onChange: function (fn) { if (typeof fn === 'function') { listeners.push(fn); } },
    watch: function (ref, info) { openWatch(ref, info || {}); },
  };
  window.NNPlayer = api;

  // ----------------------------------------------------------- the inputs
  function itemFrom(node) {
    return {
      key: node.getAttribute('data-key') || node.getAttribute('data-src'),
      url: node.getAttribute('data-src'), title: node.getAttribute('data-title'),
      show: node.getAttribute('data-show'), cover: node.getAttribute('data-cover'),
      post: node.getAttribute('data-post'), color: node.getAttribute('data-color'),
      sample: node.getAttribute('data-nn-sample'),
    };
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest ? ev.target.closest('[data-nn-play]') : null;
    if (!b) { return; }
    ev.preventDefault();
    var key = b.getAttribute('data-key') || b.getAttribute('data-src');
    if (api.isKey(key)) { api.toggle(); return; }
    var group = b.getAttribute('data-nn-queue');
    var nodes = group ? Array.prototype.slice.call(document.querySelectorAll('[data-nn-play][data-nn-queue="' + group.replace(/"/g, '') + '"]')) : [b];
    var seen = {}, items = [], start = 0;
    nodes.forEach(function (n) {
      var it = itemFrom(n);
      if (!it.url || seen[it.url]) { return; }
      seen[it.url] = 1;
      if (n === b) { start = items.length; }
      items.push(it);
    });
    api.start(items, start);
  });

  // The front page's cards: take over each native control.
  function cardInfo(a) {
    var card = a.closest('article, .lt-edition, .lt-flag, .lt-convo-feature, .lt-card') || a.parentNode;
    var link = card.querySelector('.lt-hl a');
    var img = card.querySelector('img');
    var label = a.getAttribute('aria-label') || '';
    var m = /^Play (.+?) episode/.exec(label);
    var color = '';
    try { color = getComputedStyle(card).getPropertyValue('--show-color').trim(); } catch (e) {}
    return {
      key: a.getAttribute('src'), url: a.getAttribute('src'),
      title: a.getAttribute('data-title') || (link ? link.textContent.trim() : label.replace(/^Play (an? )?/i, '')),
      show: a.getAttribute('data-show') || (m ? m[1] : (a.hasAttribute('data-nn-sample') ? 'Nerra Personal' : '')),
      cover: img ? (img.currentSrc || img.getAttribute('src')) : '',
      post: link ? link.getAttribute('href') : '', color: color,
      sample: a.getAttribute('data-nn-sample') || '',
    };
  }
  function enhance() {
    var controls = Array.prototype.slice.call(document.querySelectorAll('.lt-lead-audio audio[src], audio[data-nn-player][src]'));
    controls.forEach(function (a) {
      if (a._nn) { return; }
      a._nn = true;
      var info = cardInfo(a);
      var btn = el('button', 'nn-listen');
      btn.type = 'button';
      btn.setAttribute('data-nn-play', '');
      btn.setAttribute('data-nn-queue', 'page');
      ['key', 'src', 'title', 'show', 'cover', 'post', 'color'].forEach(function (k) {
        var v = k === 'src' ? info.url : info[k];
        if (v) { btn.setAttribute('data-' + k, v); }
      });
      if (info.sample) { btn.setAttribute('data-nn-sample', info.sample); }
      btn.setAttribute('aria-label', a.getAttribute('aria-label') || 'Play');
      var heard = isPlayed(info.url), pos = positions[info.url];
      btn.innerHTML = '<span class="ic" aria-hidden="true"></span><span class="nn-listen-txt">'
        + (heard ? 'Listen again' : pos > 30 ? 'Resume · ' + clock(pos) : 'Listen') + '</span>';
      a.parentNode.insertBefore(btn, a);
      a.classList.add('nn-native-audio');
      a.setAttribute('aria-hidden', 'true');
      a.tabIndex = -1;
    });
  }

  // -------------------------------------------------------- inline players
  // Oct 30 2026: every other native <audio controls> on the site (a blog
  // post's "Listen to this episode", a show page's latest episode and its
  // archive, the language hubs, the specials) becomes a player of our own
  // that drives this one engine. On an iPhone the native control drew a
  // white box on the dark pages, and a press started a second, separate
  // player the bar knew nothing about. The native element stays in the HTML,
  // hidden, for a visitor without JavaScript, and it stays the source of the
  // episode's URL: a language switch or a chapter seek that sets its src or
  // currentTime and calls play() is routed here (``proxy``). A card shows
  // cover, show, title, play, −15/+30, a scrubber with times and the speed;
  // a row (an archive list) shows the controls only.
  var inline = [];
  // The page's one episode player, by id, and where its title is written
  // (pages built before Oct 30 carry no data-nn-title-from).
  var CARD_IDS = { 'nn-i18n-audio': '.blog-hero h1 .nn-i18n-title', 'latest-audio': '#latest-title' };
  function pageShow() {
    var b = document.querySelector('.blog-show-badge');
    if (b) { return b.textContent.replace(/\s+Blog\s*$/i, '').trim(); }
    var h = document.querySelector('.show-hero h1');
    return h ? h.textContent.trim() : '';
  }
  function pageCover() {
    var i = document.querySelector('.blog-show-badge img, .show-hero-art');
    return i ? (i.currentSrc || i.getAttribute('src') || '') : '';
  }
  function absUrl(u) { try { return u ? new URL(u, location.href).href : ''; } catch (e) { return ''; } }
  function inlineItem(p) {
    var a = p.native, card = a.closest('article, .episode-card, .glass-card, .nn-guest, .lt-card, section') || a.parentNode;
    var titleFrom = a.getAttribute('data-nn-title-from') || (typeof CARD_IDS[a.id] === 'string' ? CARD_IDS[a.id] : '');
    var titleNode = titleFrom ? document.querySelector(titleFrom) : null;
    if (!titleNode && card) { titleNode = card.querySelector('[data-role="title"], .episode-card-title, .nn-guest-name, h3, .lt-hl'); }
    if (!titleNode && p.card) { titleNode = document.querySelector('.blog-hero h1, .nn-iv-name, h1'); }
    var label = (a.getAttribute('aria-label') || '').replace(/^Play (an? |the )?/i, '');
    var img = card && !p.card ? card.querySelector('img') : null;
    var color = '';
    try { color = getComputedStyle(a.parentNode).getPropertyValue('--show-color').trim(); } catch (e) {}
    return {
      key: a.getAttribute('src') || '', url: absUrl(a.getAttribute('src')),
      title: a.getAttribute('data-title') || (titleNode ? titleNode.textContent.trim() : '') || label || document.title,
      show: a.getAttribute('data-show') || pageShow(),
      cover: absUrl(a.getAttribute('data-cover') || (img ? (img.currentSrc || img.getAttribute('src')) : '') || pageCover()),
      post: absUrl(a.getAttribute('data-post') || ''), color: color,
    };
  }
  function inlineSync(p) {
    var it = inlineItem(p);
    // Written only when changed: a write is a DOM mutation, and the page's
    // mutation observer calls back here.
    if (p.ui.title && p.ui.title.textContent !== it.title) { p.ui.title.textContent = it.title; }
    if (p.ui.show && p.ui.show.textContent !== it.show) { p.ui.show.textContent = it.show; p.ui.show.hidden = !it.show; }
    if (p.ui.cover) {
      if (it.cover) { if (p.ui.cover.getAttribute('src') !== it.cover) { p.ui.cover.setAttribute('src', it.cover); } p.ui.cover.hidden = false; } else { p.ui.cover.hidden = true; }
    }
    p.root.hidden = !it.url;
  }
  function inlineIsCur(p) { var c = current(); return !!(c && p.native.getAttribute('src') && c.url === absUrl(p.native.getAttribute('src'))); }
  function inlineDur(p) { var d = p.native.duration; return isFinite(d) && d > 0 ? d : (p.knownDur || 0); }
  function paintInline() {
    inline.forEach(function (p) {
      var cur = inlineIsCur(p), playing = cur && !audio.paused;
      var url = absUrl(p.native.getAttribute('src'));
      var t = cur ? (audio.currentTime || 0) : (positions[url] || 0);
      var d = cur ? (audio.duration || inlineDur(p)) : inlineDur(p);
      if (cur && audio.duration) { p.knownDur = audio.duration; }
      p.root.classList.toggle('is-current', cur);
      p.root.classList.toggle('is-playing', playing);
      p.ui.play.setAttribute('aria-label', playing ? 'Pause' : (t > 30 && !cur ? 'Resume from ' + clock(t) : 'Play'));
      p.ui.cur.textContent = clock(t);
      p.ui.dur.textContent = d ? clock(d) : '';
      if (!p.seeking) { p.ui.seek.value = d ? String(Math.round(Math.min(t, d) / d * 1000)) : '0'; }
      p.ui.seek.style.setProperty('--nn-ip-fill', d ? (Math.min(t, d) / d * 100).toFixed(2) + '%' : '0%');
      p.ui.seek.setAttribute('aria-valuetext', clock(t) + (d ? ' of ' + clock(d) : ''));
      p.ui.seek.disabled = !d;
      p.ui.rate.textContent = RATES[rateAt] + '×';
      p.ui.back.disabled = !cur; p.ui.fwd.disabled = !cur;
      if (p.ui.state) { p.ui.state.textContent = playing ? 'Playing' : cur ? 'Paused' : isPlayed(url) ? 'Played' : t > 30 ? 'Resume at ' + clock(t) : ''; }
    });
  }
  function inlinePlay(p, at) {
    var it = inlineItem(p);
    if (!it.url) { return; }
    if (inlineIsCur(p)) {
      if (typeof at === 'number' && audio.duration) { audio.currentTime = Math.max(0, Math.min(audio.duration - 1, at)); if (audio.paused) { api.toggle(); } return; }
      api.toggle(); return;
    }
    if (typeof at === 'number' && at > 0) { positions[it.url] = at; }
    // The page's rows play as one queue in page order; a card plays alone.
    if (p.card) { api.start([it], 0); return; }
    var rows = inline.filter(function (x) { return !x.card && !x.root.hidden; });
    api.start(rows.map(inlineItem), Math.max(0, rows.indexOf(p)));
  }
  function proxy(p) {
    // A script that plays the hidden native element (a chapter link, the
    // language switcher) plays through the engine instead, from where it
    // put the playhead.
    p.native.addEventListener('play', function () {
      var t = p.native.currentTime || 0;
      try { p.native.pause(); } catch (e) {}
      inlinePlay(p, t > 0 ? t : undefined);
    });
    p.native.addEventListener('loadedmetadata', function () { paintInline(); });
    if (window.MutationObserver) {
      var last = absUrl(p.native.getAttribute('src'));
      new MutationObserver(function () {
        var now = absUrl(p.native.getAttribute('src'));
        if (now === last) { return; }
        var wasCur = current() && current().url === last && !audio.paused;
        last = now; p.knownDur = 0;
        inlineSync(p);
        if (wasCur) { inlinePlay(p); } else { paintInline(); }
      }).observe(p.native, { attributes: true, attributeFilter: ['src'] });
    }
  }
  function buildInline(a) {
    var isCard = a.hasAttribute('data-nn-card') || !!CARD_IDS[a.id] || !!a.closest('.nn-iv-player');
    var root = el('div', 'nn-ip' + (isCard ? ' nn-ip--card' : ' nn-ip--row'));
    root.setAttribute('role', 'group');
    root.setAttribute('aria-label', 'Episode player');
    root.innerHTML =
      (isCard ? '<img class="nn-ip-cover" alt="" width="64" height="64" loading="lazy">' +
        '<div class="nn-ip-head"><b class="nn-ip-show"></b><span class="nn-ip-title"></span>' +
        '<span class="nn-ip-state" aria-live="polite"></span></div>' : '') +
      '<div class="nn-ip-ctl">' +
        '<button type="button" class="nn-ip-play" aria-label="Play"><span class="ic" aria-hidden="true"></span></button>' +
        '<button type="button" class="nn-ip-skip" data-ip="back" aria-label="Back 15 seconds">−15</button>' +
        '<div class="nn-ip-track"><input type="range" class="nn-ip-seek" min="0" max="1000" value="0" step="1" aria-label="Seek">' +
          '<span class="nn-ip-times"><span class="nn-ip-cur">0:00</span><span class="nn-ip-dur"></span></span></div>' +
        '<button type="button" class="nn-ip-skip" data-ip="fwd" aria-label="Forward 30 seconds">+30</button>' +
        '<button type="button" class="nn-ip-rate" data-ip="rate" aria-label="Playback speed">1×</button>' +
      '</div>';
    var p = { native: a, root: root, card: isCard, ui: {}, knownDur: 0, seeking: false };
    ['cover', 'show', 'title', 'state', 'play', 'seek', 'cur', 'dur'].forEach(function (k) { p.ui[k] = root.querySelector('.nn-ip-' + k); });
    p.ui.back = root.querySelector('[data-ip="back"]');
    p.ui.fwd = root.querySelector('[data-ip="fwd"]');
    p.ui.rate = root.querySelector('[data-ip="rate"]');
    p.ui.play.addEventListener('click', function () { inlinePlay(p); });
    p.ui.back.addEventListener('click', function () { if (inlineIsCur(p)) { api.seekBy(-15); } });
    p.ui.fwd.addEventListener('click', function () { if (inlineIsCur(p)) { api.seekBy(30); } });
    p.ui.rate.addEventListener('click', function () { api.rate(); paintInline(); });
    p.ui.seek.addEventListener('input', function () {
      p.seeking = true;
      var d = inlineIsCur(p) ? audio.duration : inlineDur(p);
      if (d) { p.ui.cur.textContent = clock(Number(p.ui.seek.value) / 1000 * d); }
    });
    p.ui.seek.addEventListener('change', function () {
      p.seeking = false;
      var d = inlineIsCur(p) ? audio.duration : inlineDur(p);
      if (d) { inlinePlay(p, Number(p.ui.seek.value) / 1000 * d); }
    });
    a.parentNode.insertBefore(root, a);
    a.classList.add('nn-native-audio');
    a.setAttribute('aria-hidden', 'true');
    a.tabIndex = -1;
    a._nn = true;
    inline.push(p);
    proxy(p);
    inlineSync(p);
  }
  function enhanceInline() {
    // A card a page script re-rendered away is forgotten.
    inline = inline.filter(function (p) { return document.contains(p.root); });
    inline.forEach(inlineSync);
    var found = Array.prototype.slice.call(document.querySelectorAll('audio[controls]'));
    var added = false;
    found.forEach(function (a) {
      if (a._nn || a.hasAttribute('data-nn-native') || a.closest('noscript, .lt-lead-audio, .nn-gp')) { return; }
      if (a.classList.contains('nn-sticky-audio')) { return; }
      buildInline(a); added = true;
    });
    if (added) { paintInline(); }
  }

  // ------------------------------------------------------------- watching
  // One dialog for a single video and for a playlist (My Nerra's "Watch my
  // lineup"). A playlist item is a YouTube video, or Mira's card: her studio
  // loop with a written greeting, no voice (a spoken one would be a model
  // call per member). A playlist advances when a video ends, through the
  // YouTube IFrame API on the privacy-enhanced host, loaded only on a press;
  // if that script cannot load, the video still plays and Next advances.
  var dialog = null, list = [], listAt = 0, ytPlayer = null, ytReady = null, miraTimer = null;
  var MIRA_SECONDS = 8;
  function videoId(ref) {
    ref = String(ref || '');
    var m = /(?:youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|embed\/)|youtu\.be\/)([A-Za-z0-9_-]{6,15})/.exec(ref);
    if (m) { return m[1]; }
    return /^[A-Za-z0-9_-]{6,15}$/.test(ref) ? ref : '';
  }
  function loadYT() {
    if (ytReady) { return ytReady; }
    ytReady = new Promise(function (resolve) {
      if (window.YT && window.YT.Player) { resolve(window.YT); return; }
      var prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = function () { if (prev) { try { prev(); } catch (e) {} } resolve(window.YT); };
      var s = document.createElement('script');
      s.src = 'https://www.youtube.com/iframe_api';
      s.onerror = function () { resolve(null); };
      document.head.appendChild(s);
      setTimeout(function () { resolve(window.YT && window.YT.Player ? window.YT : null); }, 6000);
    });
    return ytReady;
  }
  function stopFrame() {
    clearInterval(miraTimer); miraTimer = null;
    if (ytPlayer && ytPlayer.destroy) { try { ytPlayer.destroy(); } catch (e) {} }
    ytPlayer = null;
    if (dialog) { var f = dialog.querySelector('.nn-watch-frame'); f.innerHTML = ''; f.classList.remove('is-mira'); }
  }
  function closeWatch() {
    if (!dialog) { return; }
    stopFrame();
    list = []; listAt = 0;
    if (dialog.open && dialog.close) { dialog.close(); } else { dialog.removeAttribute('open'); }
  }
  function buildDialog() {
    if (dialog) { return; }
    dialog = el('dialog', 'nn-watch');
    dialog.setAttribute('aria-label', 'Video');
    dialog.innerHTML = '<div class="nn-watch-shell"><div class="nn-watch-frame"></div>' +
      '<div class="nn-watch-info"><p class="nn-watch-show"></p><h2 class="nn-watch-title"></h2>' +
      '<div class="nn-watch-list" hidden><button type="button" class="nn-gp-btn" data-wl="prev" aria-label="Previous video">‹ Prev</button>' +
      '<span class="nn-watch-count"></span><button type="button" class="nn-gp-btn" data-wl="next" aria-label="Next video">Next ›</button>' +
      '<span class="nn-watch-next"></span></div>' +
      '<p class="nn-watch-actions"><a class="nn-watch-post" href="#">Read the episode</a>' +
      '<a class="nn-watch-yt" href="#" target="_blank" rel="noopener">Watch on YouTube ↗</a></p>' +
      '<p class="nn-watch-note">Plays from YouTube in privacy-enhanced mode, only after you open it.</p></div>' +
      '<button type="button" class="nn-watch-close" aria-label="Close the video">✕</button></div>';
    document.body.appendChild(dialog);
    dialog.querySelector('.nn-watch-close').addEventListener('click', closeWatch);
    dialog.addEventListener('click', function (ev) {
      if (ev.target === dialog) { closeWatch(); return; }
      var b = ev.target.closest('[data-wl]');
      if (b) { showItem(listAt + (b.getAttribute('data-wl') === 'next' ? 1 : -1)); }
    });
    dialog.addEventListener('close', function () { stopFrame(); list = []; listAt = 0; });
    dialog.querySelector('.nn-watch-yt').addEventListener('click', function () {
      track('watch_on_youtube', { location: location.pathname, placement: 'player' });
    });
  }
  function paintInfo(info, vertical, id) {
    dialog.classList.toggle('is-short', vertical);
    dialog.querySelector('.nn-watch-show').textContent = info.show || '';
    dialog.querySelector('.nn-watch-title').textContent = info.title || '';
    var post = dialog.querySelector('.nn-watch-post');
    post.hidden = !safeUrl(info.post); post.href = safeUrl(info.post) || '#';
    var yt = dialog.querySelector('.nn-watch-yt');
    yt.hidden = !id;
    if (id) { yt.href = (vertical ? 'https://www.youtube.com/shorts/' : 'https://www.youtube.com/watch?v=') + id; }
    var bar = dialog.querySelector('.nn-watch-list');
    bar.hidden = list.length < 2;
    if (list.length > 1) {
      dialog.querySelector('.nn-watch-count').textContent = (listAt + 1) + ' of ' + list.length;
      bar.querySelector('[data-wl="prev"]').disabled = listAt === 0;
      bar.querySelector('[data-wl="next"]').disabled = listAt >= list.length - 1;
      var nx = list[listAt + 1];
      dialog.querySelector('.nn-watch-next').textContent = nx ? 'Up next: ' + (nx.show || nx.title || '') : '';
    }
  }
  function playVideo(id, info, vertical) {
    var frame = dialog.querySelector('.nn-watch-frame');
    frame.innerHTML = '';
    var advance = list.length > 1 && listAt < list.length - 1;
    var plain = function () {
      var ifr = document.createElement('iframe');
      ifr.src = 'https://www.youtube-nocookie.com/embed/' + id + '?autoplay=1&rel=0&playsinline=1&modestbranding=1';
      ifr.title = info.title || 'Video';
      ifr.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      ifr.allowFullscreen = true;
      ifr.referrerPolicy = 'strict-origin-when-cross-origin';
      frame.appendChild(ifr);
    };
    if (!advance) { plain(); return; }
    var mount = document.createElement('div');
    frame.appendChild(mount);
    var at = listAt;
    loadYT().then(function (YT) {
      if (at !== listAt || !dialog.open) { return; }
      if (!YT) { frame.innerHTML = ''; plain(); return; }
      ytPlayer = new YT.Player(mount, {
        host: 'https://www.youtube-nocookie.com', videoId: id,
        playerVars: { autoplay: 1, rel: 0, playsinline: 1, modestbranding: 1 },
        events: { onStateChange: function (e) { if (e.data === 0 && at === listAt) { showItem(listAt + 1); } } },
      });
      var ifr = frame.querySelector('iframe');
      if (ifr) { ifr.title = info.title || 'Video'; }
    });
  }
  function playMira(item) {
    var frame = dialog.querySelector('.nn-watch-frame');
    frame.innerHTML = '';
    frame.classList.add('is-mira');
    var card = el('div', 'nn-watch-mira');
    var v = document.createElement('video');
    v.muted = true; v.loop = true; v.playsInline = true; v.autoplay = true;
    v.setAttribute('playsinline', ''); v.setAttribute('aria-hidden', 'true');
    v.poster = item.poster || ''; v.src = item.video || '';
    card.appendChild(v);
    var txt = el('div', 'nn-watch-mira-txt');
    txt.appendChild(el('p', 'nn-watch-mira-k', 'Mira · your lineup'));
    var h = el('p', 'nn-watch-mira-h'); h.textContent = item.greeting || ''; txt.appendChild(h);
    (item.lines || []).forEach(function (line) { var p = el('p', 'nn-watch-mira-l'); p.textContent = line; txt.appendChild(p); });
    var go = el('button', 'nn-gp-btn nn-watch-mira-go'); go.type = 'button';
    txt.appendChild(go);
    card.appendChild(txt);
    frame.appendChild(card);
    var left = MIRA_SECONDS, at = listAt, held = false;
    // Oct 29 2026 (WCAG 2.2.1): the countdown waits while a reader is on
    // the card (pointer over it, or keyboard focus in it).
    var paint = function () { go.textContent = held ? 'Start' : 'Start · ' + left + 's'; };
    paint();
    go.addEventListener('click', function () { showItem(at + 1); });
    card.addEventListener('mouseenter', function () { held = true; paint(); });
    card.addEventListener('mouseleave', function () { held = false; paint(); });
    card.addEventListener('focusin', function () { held = true; paint(); });
    card.addEventListener('focusout', function () { held = false; paint(); });
    miraTimer = setInterval(function () {
      if (held) { return; }
      left -= 1;
      if (left <= 0 || at !== listAt) { clearInterval(miraTimer); if (at === listAt) { showItem(at + 1); } return; }
      paint();
    }, 1000);
  }
  function showItem(i) {
    if (i < 0 || i >= list.length) { return; }
    stopFrame();
    listAt = i;
    var item = list[i];
    if (item.kind === 'mira') {
      paintInfo({ show: 'Mira', title: item.title || 'Your lineup' }, false, '');
      playMira(item);
      return;
    }
    var id = videoId(item.url), vertical = item.kind === 'short' || /\/shorts\//.test(String(item.url));
    paintInfo(item, vertical, id);
    playVideo(id, item, vertical);
    track('play_video', { kind: vertical ? 'short' : 'long', placement: list.length > 1 ? 'lineup' : 'single', location: location.pathname });
  }
  function openList(items, start) {
    var clean = (items || []).filter(function (x) { return x && (x.kind === 'mira' || videoId(x.url)); });
    if (!clean.length) { return false; }
    buildDialog();
    list = clean;
    if (!audio.paused) { audio.pause(); }
    if (!dialog.open) { if (dialog.showModal) { dialog.showModal(); } else { dialog.setAttribute('open', ''); } }
    showItem(Math.max(0, Math.min(clean.length - 1, start || 0)));
    return true;
  }
  function openWatch(ref, info) {
    if (!videoId(ref)) { return false; }
    return openList([{ url: ref, kind: info.kind, title: info.title, show: info.show, post: info.post }], 0);
  }
  api.watchList = function (items, start) { return openList(items, start); };
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest ? ev.target.closest('[data-nn-watch]') : null;
    if (!b || ev.metaKey || ev.ctrlKey || ev.shiftKey) { return; }
    var ok = openWatch(b.getAttribute('data-nn-watch') || b.getAttribute('href'), {
      kind: b.getAttribute('data-kind'), title: b.getAttribute('data-title'),
      show: b.getAttribute('data-show'), post: b.getAttribute('data-post') });
    if (ok) { ev.preventDefault(); }
  });

  // ---------------------------------------------------------------- start
  // The episode button at the top of a post ("Listen to podcast") starts the
  // episode in the page's player instead of only scrolling to it.
  function listenLinks() {
    document.addEventListener('click', function (e) {
      var a = e.target && e.target.closest ? e.target.closest('a[href="#listen"]') : null;
      if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey) { return; }
      var box = document.getElementById('listen');
      var card = null;
      for (var k = 0; k < inline.length; k++) {
        if (inline[k].card && !inline[k].root.hidden && box && box.contains(inline[k].root)) { card = inline[k]; break; }
      }
      if (!card) { return; }
      e.preventDefault();
      try { card.root.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (err) { card.root.scrollIntoView(); }
      if (!inlineIsCur(card) || audio.paused) { inlinePlay(card); }
    });
  }

  function init() {
    enhance();
    enhanceInline();
    document.documentElement.classList.add('nn-ip-ready');
    listenLinks();
    // A show page draws its archive after a fetch; those players are taken
    // over as they arrive.
    if (window.MutationObserver && document.body) {
      var pending = 0;
      new MutationObserver(function (muts) {
        if (pending) { return; }
        for (var i = 0; i < muts.length; i++) {
          var tg = muts[i].target;
          // The players' own clocks and labels are not new content.
          if (tg && tg.closest && tg.closest('.nn-ip, .nn-gp')) { continue; }
          if (muts[i].addedNodes && muts[i].addedNodes.length) {
            pending = setTimeout(function () { pending = 0; enhance(); enhanceInline(); }, 60);
            return;
          }
        }
      }).observe(document.body, { childList: true, subtree: true });
    }
    var now = load(NOW_KEY);
    if (now && now.queue && now.queue.length && Date.now() - (now.ts || 0) < RESUME_HOURS * 3600e3 && !current()) {
      queue = normalize(now.queue);
      if (queue.length) { cue(Math.max(0, Math.min(queue.length - 1, now.at || 0)), false); }
    }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();
