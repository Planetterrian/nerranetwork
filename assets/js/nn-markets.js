/* Live quotes for the stocks a reader follows (Oct 29 2026).
 *
 * One small module, used by My Nerra's markets block and the front page's
 * markets strip (assets/js/live-ticker.js). Quotes come from the gallery
 * Worker's markets route (workers/gallery/src/markets.ts): the network's
 * own list by `symbols=`, anything else a reader added by `extra=` (each
 * symbol checked against the same shape the Worker and the edition builder
 * use, engine.personal_edition.TICKER_RE). A quote is "Live" only when the
 * Worker says the regular session is open; otherwise it is a close under
 * its own date. Nothing here writes network text as markup.
 *
 * A signed-in member's stocks live on their account (preferences.tickers);
 * a visitor's stay in this browser (localStorage nnMe.tickers) and become
 * the account's list when they make one.
 */
(function () {
  'use strict';
  if (window.NNMarkets) { return; }

  var API = 'https://api.nerranetwork.com/api/markets';
  var KEY = 'nnMe.tickers';
  var MAX = 8;
  var PER_REQUEST = 10;
  var DEFAULT = ['TSLA', 'SPCX'];
  // The Worker's MARKET_SYMBOLS (served without extra=).
  var NETWORK = ['TSLA', 'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'SPCX'];
  var NAMES = { TSLA: 'Tesla', SPCX: 'SpaceX', NVDA: 'Nvidia', AAPL: 'Apple', MSFT: 'Microsoft',
                GOOGL: 'Alphabet', AMZN: 'Amazon', META: 'Meta' };
  var SHAPE = /^\^?[A-Z0-9][A-Z0-9.\-]{0,9}(=[XF])?$/;
  var ET = 'America/New_York';

  function valid(sym) { return SHAPE.test(String(sym || '')); }
  function clean(list) {
    var out = [];
    (Array.isArray(list) ? list : []).forEach(function (t) {
      var s = String(t || '').trim().toUpperCase();
      if (valid(s) && out.indexOf(s) === -1 && out.length < MAX) { out.push(s); }
    });
    return out;
  }
  function stored() { try { return clean(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch (e) { return []; } }
  function store(list) { try { localStorage.setItem(KEY, JSON.stringify(clean(list))); } catch (e) {} }

  function get(list) {
    var want = [];
    (Array.isArray(list) ? list : []).forEach(function (t) {
      var x = String(t || '').trim().toUpperCase();
      if (valid(x) && want.indexOf(x) === -1) { want.push(x); }
    });
    var closed = want.filter(function (s) { return NETWORK.indexOf(s) !== -1; });
    var extra = want.filter(function (s) { return NETWORK.indexOf(s) === -1; });
    var batches = [];
    for (var i = 0; i < extra.length; i += PER_REQUEST) { batches.push(extra.slice(i, i + PER_REQUEST)); }
    if (!batches.length) { batches.push([]); }
    var out = { quotes: {}, unknown: [], answered: false };
    if (!want.length || !window.fetch) { return Promise.resolve(out); }
    return Promise.all(batches.map(function (b, n) {
      var url = API + '?symbols=' + encodeURIComponent(n === 0 && closed.length ? closed.join(',') : 'none')
        + (b.length ? '&extra=' + encodeURIComponent(b.join(',')) : '');
      return fetch(url, { mode: 'cors', credentials: 'omit' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (body) {
          if (!body) { return; }
          out.answered = true;
          (body.quotes || []).forEach(function (q) {
            if (q && want.indexOf(q.symbol) !== -1 && q.price > 0 && q.as_of) { out.quotes[q.symbol] = q; }
          });
          (body.unknown || []).forEach(function (s) { if (out.unknown.indexOf(s) === -1) { out.unknown.push(s); } });
        })
        .catch(function () {});
    })).then(function () { return out; });
  }

  function price(q) {
    var v = Number(q.price);
    if (String(q.symbol).charAt(0) === '^') { return v.toLocaleString('en-US', { maximumFractionDigits: 2 }); }
    if (/=X$/.test(q.symbol)) { return v.toFixed(4); }
    var cur = q.currency || (NETWORK.indexOf(q.symbol) !== -1 ? 'USD' : '');
    try {
      if (cur) {
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: cur, currencyDisplay: cur === 'USD' ? 'symbol' : 'narrowSymbol',
          minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v) + (cur !== 'USD' ? ' ' + cur : '');
      }
    } catch (e) {}
    return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function change(q) {
    var v = q.change_pct;
    if (v === null || v === undefined || isNaN(v)) { return ''; }
    if (Math.round(v * 10) === 0) { return 'unchanged'; }
    return (v > 0 ? '+' : '−') + Math.abs(v).toFixed(1) + '%';
  }
  function dir(q) {
    var v = q.change_pct;
    if (v === null || v === undefined || isNaN(v) || Math.round(v * 10) === 0) { return 'flat'; }
    return v > 0 ? 'up' : 'down';
  }
  function when(q) {
    var d = new Date(q.as_of);
    if (isNaN(d)) { return ''; }
    try {
      if (q.state === 'live') {
        return 'Live · ' + new Intl.DateTimeFormat('en-US', { timeZone: ET, hour: 'numeric', minute: '2-digit' }).format(d) + ' ET';
      }
      return 'Close · ' + new Intl.DateTimeFormat('en-US', { timeZone: ET, month: 'short', day: 'numeric' }).format(d);
    } catch (e) { return ''; }
  }
  function name(q) { return q.name || NAMES[q.symbol] || ''; }

  window.NNMarkets = {
    API: API, MAX: MAX, DEFAULT: DEFAULT.slice(), valid: valid, clean: clean,
    stored: stored, store: store, get: get, price: price, change: change, dir: dir, when: when, name: name,
  };
})();
