/* Live ticker for the front pages (Oct 19 2026).
 *
 * 1. Quotes. The markets strip is printed at build time from committed files
 *    (engine.newsroom.market_strip). This updates it from the Worker route
 *    named in data-live-markets (workers/gallery/src/markets.ts) every
 *    data-every seconds while the page is visible. A quote is "Live" only
 *    when the Worker says the regular session is open; otherwise it is a
 *    close under its own date. Until the Worker answers, and whenever it
 *    fails, the printed values stay. Every value is written with
 *    textContent: nothing from the network becomes markup.
 * 2. Headlines. The Latest row re-reads this page's own newest build (the
 *    site regenerates it after every show) and swaps in its headlines.
 * 3. Motion. A row wider than its box moves as a tape (its own scroll
 *    position advances, so it can still be swiped). It pauses on hover, on
 *    keyboard focus, on touch, with its Pause button and in a hidden tab,
 *    and never moves under prefers-reduced-motion.
 */
(function () {
  'use strict';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var ET = 'America/New_York';

  function fmtTime(d) {
    try { return new Intl.DateTimeFormat('en-US', {timeZone: ET, hour: 'numeric', minute: '2-digit'}).format(d) + ' ET'; }
    catch (e) { return ''; }
  }
  function fmtDay(d) {
    try { return new Intl.DateTimeFormat('en-US', {timeZone: ET, month: 'short', day: 'numeric'}).format(d); }
    catch (e) { return ''; }
  }
  function money(v) {
    return '$' + Number(v).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  }
  function pct(v) {
    if (v === null || v === undefined || isNaN(v)) return '';
    if (Math.round(v * 10) === 0) return 'unchanged';
    return (v > 0 ? '+' : '−') + Math.abs(v).toFixed(1) + '%';
  }
  function direction(v) {
    if (v === null || v === undefined || isNaN(v) || Math.round(v * 10) === 0) return 'flat';
    return v > 0 ? 'up' : 'down';
  }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function visible() { return document.visibilityState !== 'hidden'; }

  /* ---------------- Tape motion ---------------- */
  // The row keeps its own horizontal scroll (a reader can still swipe it);
  // the tape advances that scroll position and loops over a copy of the
  // items, so nothing jumps when it wraps.
  var SPEED = 40; // px per second
  function Tape(row) {
    this.row = row;
    this.ul = row.querySelector('ul');
    this.btn = row.querySelector('.lt-tape-pause');
    this.paused = false;
    this.loop = 0;
    this.pos = 0;
    this.last = 0;
    this.raf = 0;
    var self = this;
    if (this.btn) {
      this.btn.addEventListener('click', function () {
        self.paused = !self.paused;
        self.btn.setAttribute('aria-pressed', self.paused ? 'true' : 'false');
        self.btn.textContent = self.paused
          ? (self.btn.getAttribute('data-play') || 'Play')
          : (self.btn.getAttribute('data-pause') || 'Pause');
        row.classList.toggle('is-paused', self.paused);
      });
    }
    var hold = function () { row.classList.add('is-held'); };
    var release = function () {
      row.classList.remove('is-held');
      if (self.ul) self.pos = self.ul.scrollLeft;  // pick up where a swipe left it
    };
    row.addEventListener('mouseenter', hold);
    row.addEventListener('mouseleave', release);
    row.addEventListener('focusin', hold);
    row.addEventListener('focusout', release);
    row.addEventListener('touchstart', hold, {passive: true});
    row.addEventListener('touchend', function () { setTimeout(release, 1500); }, {passive: true});
    this.refresh();
    if (window.ResizeObserver) {
      var t;
      new ResizeObserver(function () { clearTimeout(t); t = setTimeout(function () { self.refresh(); }, 250); }).observe(row);
    }
  }
  Tape.prototype.held = function () {
    return this.paused || this.row.classList.contains('is-held') || !visible();
  };
  Tape.prototype.step = function (now) {
    var self = this;
    var dt = this.last ? Math.min(0.1, (now - this.last) / 1000) : 0;
    this.last = now;
    if (!this.held() && this.loop > 0) {
      this.pos += SPEED * dt;
      if (this.pos >= this.loop) this.pos -= this.loop;
      this.ul.scrollLeft = this.pos;
    }
    this.raf = window.requestAnimationFrame(function (t) { self.step(t); });
  };
  Tape.prototype.refresh = function () {
    var ul = this.ul;
    if (!ul) return;
    if (this.raf) { window.cancelAnimationFrame(this.raf); this.raf = 0; }
    Array.prototype.slice.call(ul.querySelectorAll('[data-tape-copy]')).forEach(function (n) { n.remove(); });
    this.row.classList.remove('is-moving');
    this.loop = 0;
    var originals = Array.prototype.slice.call(ul.children);
    var overflow = ul.scrollWidth > ul.clientWidth + 8;
    if (reduce || !overflow || !originals.length) {
      if (this.btn) this.btn.hidden = true;
      return;
    }
    originals.forEach(function (li) {
      var copy = li.cloneNode(true);
      copy.setAttribute('data-tape-copy', '');
      copy.setAttribute('aria-hidden', 'true');
      Array.prototype.slice.call(copy.querySelectorAll('a, button')).forEach(function (a) { a.setAttribute('tabindex', '-1'); });
      ul.appendChild(copy);
    });
    var firstCopy = ul.querySelector('[data-tape-copy]');
    this.loop = firstCopy.offsetLeft - originals[0].offsetLeft;
    if (this.loop <= 0) { this.loop = 0; return; }
    this.pos = Math.min(ul.scrollLeft, this.loop - 1);
    this.last = 0;
    this.row.classList.add('is-moving');
    if (this.btn) this.btn.hidden = false;
    var self = this;
    this.raf = window.requestAnimationFrame(function (t) { self.step(t); });
  };

  /* ---------------- Live quotes ---------------- */
  function liveQuotes(aside, tape) {
    var api = aside.getAttribute('data-live-markets');
    var every = Math.max(30, parseInt(aside.getAttribute('data-every'), 10) || 60) * 1000;
    var ul = aside.querySelector('ul');
    if (!api || !ul || !window.fetch) return;
    var symbols = [];
    Array.prototype.slice.call(aside.querySelectorAll('[data-quotes]:not([data-tape-copy]) [data-symbol]')).forEach(function (n) {
      var s = n.getAttribute('data-symbol');
      if (s && symbols.indexOf(s) < 0) symbols.push(s);
    });
    if (!symbols.length) return;
    var timer = null;

    function render(quotes) {
      // Group by what the value is: live now, or a close on its own day.
      var groups = [];
      quotes.forEach(function (q) {
        var at = new Date(q.as_of);
        if (isNaN(at)) return;
        var label = q.state === 'live' ? 'Live' : 'Close';
        var when = q.state === 'live' ? fmtTime(at) : fmtDay(at);
        var g = groups.length && groups[groups.length - 1];
        if (!g || g.label.replace(/s$/, '') !== label || g.when !== when) {
          g = {label: label, when: when, iso: q.as_of, quotes: []};
          groups.push(g);
        } else if (label === 'Close') {
          g.label = 'Closes';
        }
        g.quotes.push(q);
      });
      if (!groups.length) return false;
      var frag = document.createDocumentFragment();
      groups.forEach(function (g) {
        var li = el('li', 'lt-mk-group');
        li.setAttribute('data-quotes', '');
        if (g.label === 'Live') li.classList.add('is-live');
        var lab = el('span', 'lt-mk-label', g.label + ' · ');
        var t = el('time', '', g.when);
        t.setAttribute('datetime', g.iso);
        lab.appendChild(t);
        li.appendChild(lab);
        g.quotes.forEach(function (q) {
          var d = direction(q.change_pct);
          var s = el('span', 'lt-quote is-' + d);
          s.setAttribute('data-symbol', q.symbol);
          s.appendChild(el('b', 'lt-quote-sym', q.symbol));
          s.appendChild(document.createTextNode(' '));
          s.appendChild(el('span', 'lt-quote-px', money(q.price)));
          var c = pct(q.change_pct);
          if (c) { s.appendChild(document.createTextNode(' ')); s.appendChild(el('span', 'lt-quote-chg', c)); }
          li.appendChild(s);
        });
        frag.appendChild(li);
      });
      Array.prototype.slice.call(ul.querySelectorAll('[data-quotes], [data-tape-copy]')).forEach(function (n) { n.remove(); });
      ul.insertBefore(frag, ul.firstChild);
      return true;
    }

    function flagships(quotes) {
      quotes.forEach(function (q) {
        Array.prototype.slice.call(document.querySelectorAll('.lt-flag-quote[data-symbol="' + q.symbol + '"]')).forEach(function (p) {
          var at = new Date(q.as_of);
          if (isNaN(at)) return;
          p.className = 'lt-flag-quote lt-quote is-' + direction(q.change_pct);
          var px = p.querySelector('.lt-quote-px');
          if (px) px.textContent = money(q.price);
          var chg = p.querySelector('.lt-quote-chg');
          var c = pct(q.change_pct);
          if (chg) chg.textContent = c;
          var small = p.querySelector('small');
          if (small) {
            small.textContent = '';
            small.appendChild(document.createTextNode((q.state === 'live' ? 'Live' : 'Close') + ' · '));
            var t = el('time', '', q.state === 'live' ? fmtTime(at) : fmtDay(at));
            t.setAttribute('datetime', q.as_of);
            small.appendChild(t);
          }
        });
      });
    }

    function tick() {
      clearTimeout(timer);
      timer = null;
      if (!visible()) return;
      var url = api + (api.indexOf('?') < 0 ? '?' : '&') + 'symbols=' + encodeURIComponent(symbols.join(','));
      fetch(url, {mode: 'cors', credentials: 'omit'})
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (body) {
          var quotes = body && Array.isArray(body.quotes) ? body.quotes.filter(function (q) {
            return q && symbols.indexOf(q.symbol) >= 0 && q.price > 0 && q.as_of;
          }) : [];
          if (!quotes.length) return;
          quotes.sort(function (a, b) { return symbols.indexOf(a.symbol) - symbols.indexOf(b.symbol); });
          if (render(quotes)) {
            aside.classList.add('is-live-data');
            flagships(quotes);
            if (tape) tape.refresh();
          }
          // A closed market changes slowly: look again in ten minutes.
          var live = quotes.some(function (q) { return q.state === 'live'; });
          timer = setTimeout(tick, live ? every : Math.max(every, 600000));
        })
        .catch(function () { timer = setTimeout(tick, every * 2); })
        .then(function () { if (!timer && visible()) timer = setTimeout(tick, every); });
    }
    document.addEventListener('visibilitychange', function () { if (visible()) tick(); else clearTimeout(timer); });
    tick();
  }

  /* ---------------- Live headlines ---------------- */
  function liveHeadlines(row, tape) {
    var every = Math.max(60, parseInt(row.getAttribute('data-every'), 10) || 300) * 1000;
    var ul = row.querySelector('ul');
    if (!ul || !window.fetch || !window.DOMParser) return;
    var timer = null;
    function keyOf(list) {
      return Array.prototype.slice.call(list.querySelectorAll('li:not([data-tape-copy]) a')).map(function (a) {
        return a.getAttribute('href') + '|' + a.textContent;
      }).join('\n');
    }
    function tick() {
      clearTimeout(timer);
      if (!visible()) return;
      fetch(window.location.pathname, {cache: 'no-cache', credentials: 'same-origin'})
        .then(function (r) { return r.ok ? r.text() : null; })
        .then(function (html) {
          if (!html) return;
          var doc = new DOMParser().parseFromString(html, 'text/html');
          var fresh = doc.querySelector('[data-live-headlines] ul');
          if (!fresh || !fresh.children.length || keyOf(fresh) === keyOf(ul)) return;
          // The parsed page is this site's own build; adopt its items as-is.
          var items = Array.prototype.slice.call(fresh.children).map(function (li) { return document.importNode(li, true); });
          ul.textContent = '';
          items.forEach(function (li) { ul.appendChild(li); });
          if (tape) tape.refresh();
        })
        .catch(function () { /* keep what is shown */ })
        .then(function () { timer = setTimeout(tick, every); });
    }
    document.addEventListener('visibilitychange', function () { if (visible()) tick(); else clearTimeout(timer); });
    timer = setTimeout(tick, every);
  }

  function init() {
    var aside = document.querySelector('[data-live-markets]');
    if (aside) liveQuotes(aside, new Tape(aside));
    var row = document.querySelector('[data-live-headlines]');
    if (row) liveHeadlines(row, new Tape(row));
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
