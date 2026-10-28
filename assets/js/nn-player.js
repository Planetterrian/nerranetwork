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
  var queue = [], at = -1, rateAt = 0, lastSave = 0, seeking = false, reported = {};
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
        '<div class="nn-gp-bar"><span class="nn-gp-cur">0:00</span>' +
          '<input type="range" class="nn-gp-seek" min="0" max="1000" value="0" step="1" aria-label="Seek">' +
          '<span class="nn-gp-dur"></span></div>' +
        '<div class="nn-gp-side"><span class="nn-gp-queue"></span>' +
          '<button type="button" class="nn-gp-btn" data-gp="rate" aria-label="Playback speed">1×</button>' +
          '<button type="button" class="nn-gp-btn" data-gp="close" aria-label="Close the player">✕</button></div>' +
      '</div>';
    document.body.appendChild(bar);
    ['cover', 'show', 'title', 'resume', 'cur', 'dur', 'seek', 'queue'].forEach(function (k) { ui[k] = bar.querySelector('.nn-gp-' + k); });
    ui.toggle = bar.querySelector('[data-gp="toggle"]');
    ui.next = bar.querySelector('[data-gp="next"]');
    ui.rate = bar.querySelector('[data-gp="rate"]');
    ui.fill = bar.querySelector('.nn-gp-progress span');
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
    if (!bar) { return; }
    ui.cur.textContent = clock(t);
    ui.dur.textContent = d ? clock(d) : '';
    if (d && !seeking) { ui.seek.value = String(Math.round(t / d * 1000)); }
    ui.fill.style.width = d ? (t / d * 100).toFixed(2) + '%' : '0';
  }

  // --------------------------------------------------------------- engine
  function report(it) {
    if (!it || reported[it.url]) { return; }
    reported[it.url] = 1;
    if (it.sample) {
      track('play_personal_sample', { placement: it.sample, location: location.pathname });
    } else {
      track('episode_play', { src: String(it.url).split('?')[0], location: location.pathname });
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
    rate: function () { rateAt = (rateAt + 1) % RATES.length; audio.playbackRate = RATES[rateAt]; if (ui.rate) { ui.rate.textContent = RATES[rateAt] + '×'; } },
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

  // ------------------------------------------------------------- watching
  var dialog = null;
  function videoId(ref) {
    ref = String(ref || '');
    var m = /(?:youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|embed\/)|youtu\.be\/)([A-Za-z0-9_-]{6,15})/.exec(ref);
    if (m) { return m[1]; }
    return /^[A-Za-z0-9_-]{6,15}$/.test(ref) ? ref : '';
  }
  function closeWatch() {
    if (!dialog) { return; }
    dialog.querySelector('.nn-watch-frame').innerHTML = '';
    if (dialog.open && dialog.close) { dialog.close(); } else { dialog.removeAttribute('open'); }
  }
  function openWatch(ref, info) {
    var id = videoId(ref);
    if (!id) { return false; }
    if (!dialog) {
      dialog = el('dialog', 'nn-watch');
      dialog.setAttribute('aria-label', 'Video');
      dialog.innerHTML = '<div class="nn-watch-shell"><div class="nn-watch-frame"></div>' +
        '<div class="nn-watch-info"><p class="nn-watch-show"></p><h2 class="nn-watch-title"></h2>' +
        '<p class="nn-watch-actions"><a class="nn-watch-post" href="#">Read the episode</a>' +
        '<a class="nn-watch-yt" href="#" target="_blank" rel="noopener">Watch on YouTube ↗</a></p>' +
        '<p class="nn-watch-note">Plays from YouTube in privacy-enhanced mode, only after you open it.</p></div>' +
        '<button type="button" class="nn-watch-close" aria-label="Close the video">✕</button></div>';
      document.body.appendChild(dialog);
      dialog.querySelector('.nn-watch-close').addEventListener('click', closeWatch);
      dialog.addEventListener('click', function (ev) { if (ev.target === dialog) { closeWatch(); } });
      dialog.addEventListener('close', function () { dialog.querySelector('.nn-watch-frame').innerHTML = ''; });
      dialog.querySelector('.nn-watch-yt').addEventListener('click', function () {
        track('watch_on_youtube', { location: location.pathname, placement: 'player' });
      });
    }
    var vertical = info.kind === 'short' || /\/shorts\//.test(String(ref));
    dialog.classList.toggle('is-short', vertical);
    var frame = dialog.querySelector('.nn-watch-frame');
    var ifr = document.createElement('iframe');
    ifr.src = 'https://www.youtube-nocookie.com/embed/' + id + '?autoplay=1&rel=0&playsinline=1&modestbranding=1';
    ifr.title = info.title || 'Video';
    ifr.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    ifr.allowFullscreen = true;
    ifr.referrerPolicy = 'strict-origin-when-cross-origin';
    frame.innerHTML = '';
    frame.appendChild(ifr);
    dialog.querySelector('.nn-watch-show').textContent = info.show || '';
    dialog.querySelector('.nn-watch-title').textContent = info.title || '';
    var post = dialog.querySelector('.nn-watch-post');
    post.hidden = !safeUrl(info.post); post.href = safeUrl(info.post) || '#';
    dialog.querySelector('.nn-watch-yt').href = (vertical ? 'https://www.youtube.com/shorts/' : 'https://www.youtube.com/watch?v=') + id;
    if (!audio.paused) { audio.pause(); }
    if (dialog.showModal) { dialog.showModal(); } else { dialog.setAttribute('open', ''); }
    track('play_video', { kind: vertical ? 'short' : 'long', location: location.pathname });
    return true;
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest ? ev.target.closest('[data-nn-watch]') : null;
    if (!b || ev.metaKey || ev.ctrlKey || ev.shiftKey) { return; }
    var ok = openWatch(b.getAttribute('data-nn-watch') || b.getAttribute('href'), {
      kind: b.getAttribute('data-kind'), title: b.getAttribute('data-title'),
      show: b.getAttribute('data-show'), post: b.getAttribute('data-post') });
    if (ok) { ev.preventDefault(); }
  });

  // ---------------------------------------------------------------- start
  function init() {
    enhance();
    var now = load(NOW_KEY);
    if (now && now.queue && now.queue.length && Date.now() - (now.ts || 0) < RESUME_HOURS * 3600e3 && !current()) {
      queue = normalize(now.queue);
      if (queue.length) { cue(Math.max(0, Math.min(queue.length - 1, now.at || 0)), false); }
    }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();
