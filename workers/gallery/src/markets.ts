/**
 * GET /api/markets — live quotes for the front page's markets strip
 * (Oct 19 2026, operator: "the ticker should have live content").
 *
 * The strip was rendered once per build from committed files, so on a
 * Monday at noon it still printed Friday's closes. A browser cannot ask a
 * quote service directly (no CORS), and the public CORS proxies the show
 * pages lean on are someone else's uptime. This route fetches Yahoo's
 * chart API server-side for a CLOSED list of symbols and answers in one
 * JSON body:
 *
 *   {ok, fetched_at, stale, quotes: [{symbol, price, prev_close,
 *     change_pct, state: "live" | "close", as_of}]}
 *
 * Honesty rules (the same ones engine.newsroom.market_strip prints by):
 *   - ``as_of`` is the quote's own regularMarketTime, never the fetch time.
 *   - ``state`` is "live" only while the regular session is open AND the
 *     quote's own time falls inside it; otherwise the price IS the last
 *     close and the page labels it "Close · <date>" (a pre-market fetch
 *     returns the prior close — the SpaceX/Tesla quote-verb rule).
 *   - ``prev_close`` is the last bar dated BEFORE the quote's own day —
 *     never meta.chartPreviousClose, which is the close before the RANGE
 *     (CLAUDE.md landmine #22: it read $445.27 for a $404.11 day).
 *
 * Load on Yahoo: one aggregated body is cached for 60 s while the session
 * is open (10 min otherwise) in the colo's cache, and a last-good copy is
 * kept for two days; a refused or failed symbol is filled from it, so a
 * 429 shows the last good number with its own time, never a blank.
 *
 * Member tickers (Oct 29 2026): ``?extra=SHOP.TO,BTC-USD`` adds up to
 * MEMBER_SYMBOLS_PER_REQUEST symbols a member chose on My Nerra. Each is
 * checked against MEMBER_SYMBOL_RE (the shapes Yahoo's chart API names:
 * a listing, an exchange suffix, an index ``^``, a pair ``=X``, a future
 * ``=F``), fetched on its own and cached per symbol under the same TTLs,
 * with its own last-good copy. A symbol Yahoo does not know is returned in
 * ``unknown`` so the page can say so; nothing is ever guessed.
 */

import { corsHeaders } from "./cors";

/** Mirrors engine.newsroom.MARKET_TICKERS + SHOW_TICKERS (drift-guarded by
 *  tests/test_live_ticker_2026_10_19.py). Nothing outside it is fetched. */
export const MARKET_SYMBOLS = [
  "TSLA", "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "SPCX",
] as const;

const CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/";
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36";
const CACHE_KEY = "https://api.nerranetwork.com/__cache/markets/v1";
const LAST_GOOD_KEY = "https://api.nerranetwork.com/__cache/markets/last-good/v1";
const SYMBOL_CACHE = "https://api.nerranetwork.com/__cache/markets/sym/v1/";
const SYMBOL_LAST_GOOD = "https://api.nerranetwork.com/__cache/markets/sym-last-good/v1/";

/** A member-chosen symbol (also used by personal.ts cleanTickers). Mirrors
 *  engine.personal_edition.TICKER_RE — drift-guarded. */
export const MEMBER_SYMBOL_RE = /^\^?[A-Z0-9][A-Z0-9.\-]{0,9}(=[XF])?$/;
export const MEMBER_SYMBOLS_PER_REQUEST = 10;
const NAME_MAX = 60;
export const LIVE_TTL_S = 60;
export const CLOSED_TTL_S = 600;
const LAST_GOOD_TTL_S = 2 * 86400;
const FETCH_TIMEOUT_MS = 6000;

export interface LiveQuote {
  symbol: string;
  price: number;
  prev_close: number | null;
  change_pct: number | null;
  state: "live" | "close";
  as_of: string;
  /** Yahoo's own short name for the listing ("Shopify Inc."), when given. */
  name?: string;
  /** ISO currency of the price ("USD", "CAD"), when given. */
  currency?: string;
}

export interface MarketsBody {
  ok: boolean;
  fetched_at: string;
  stale: boolean;
  quotes: LiveQuote[];
  /** Member symbols Yahoo answered with no usable quote. */
  unknown?: string[];
}

function easternDay(epochS: number): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date(epochS * 1000));
}

/** One Yahoo chart response -> a quote, or null when it is unusable. */
export function parseChart(symbol: string, body: unknown, nowS: number): LiveQuote | null {
  const result = (body as any)?.chart?.result?.[0];
  const meta = result?.meta;
  if (!meta) return null;
  const price = Number(meta.regularMarketPrice);
  const t = Number(meta.regularMarketTime);
  if (!Number.isFinite(price) || price <= 0 || !Number.isFinite(t) || t <= 0) return null;

  // Previous close: the last daily bar dated before the quote's own day.
  const stamps: unknown[] = Array.isArray(result.timestamp) ? result.timestamp : [];
  const closes: unknown[] = result?.indicators?.quote?.[0]?.close ?? [];
  const quoteDay = easternDay(t);
  let prev: number | null = null;
  for (let i = stamps.length - 1; i >= 0; i--) {
    const ts = Number(stamps[i]);
    const c = Number(closes[i]);
    if (!Number.isFinite(ts) || !Number.isFinite(c) || c <= 0) continue;
    if (easternDay(ts) < quoteDay) { prev = c; break; }
  }
  if (prev === null) {
    const p = Number(meta.previousClose);
    if (Number.isFinite(p) && p > 0) prev = p;
  }

  const regular = meta.currentTradingPeriod?.regular;
  const start = Number(regular?.start);
  const end = Number(regular?.end);
  const open = Number.isFinite(start) && Number.isFinite(end)
    && nowS >= start && nowS < end && t >= start;

  const change = prev ? ((price - prev) / prev) * 100 : null;
  const q: LiveQuote = {
    symbol,
    price: Math.round(price * 100) / 100,
    prev_close: prev === null ? null : Math.round(prev * 100) / 100,
    change_pct: change === null ? null : Math.round(change * 100) / 100,
    state: open ? "live" : "close",
    as_of: new Date(t * 1000).toISOString(),
  };
  const name = cleanName(meta.shortName || meta.longName);
  if (name) q.name = name;
  const cur = String(meta.currency ?? "").toUpperCase();
  if (/^[A-Z]{3}$/.test(cur)) q.currency = cur;
  return q;
}

/** Yahoo's listing name as plain text: no markup, no control characters,
 *  capped. It reaches a page as textContent and a spoken line as words. */
export function cleanName(raw: unknown): string {
  const text = String(raw ?? "")
    .replace(/<[^>]*>/g, " ")
    .replace(/[^\p{L}\p{N} .,&'()\-]/gu, "")
    .replace(/\s+/g, " ")
    .trim();
  return text.slice(0, NAME_MAX).trim();
}

async function fetchSymbol(symbol: string, nowS: number): Promise<LiveQuote | null> {
  const url = `${CHART_URL}${encodeURIComponent(symbol)}?interval=1d&range=5d`;
  try {
    const resp = await fetch(url, {
      headers: { "User-Agent": UA, Accept: "application/json" },
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    if (!resp.ok) return null;
    return parseChart(symbol, await resp.json(), nowS);
  } catch {
    return null;
  }
}

/** Symbols the request asked for, restricted to the closed list. */
export function requestedSymbols(url: URL): string[] {
  const raw = url.searchParams.get("symbols");
  if (!raw) return [...MARKET_SYMBOLS];
  const wanted = new Set(raw.toUpperCase().split(",").map((s) => s.trim()));
  return MARKET_SYMBOLS.filter((s) => wanted.has(s));
}

/** Member symbols the request added (``?extra=``): valid shapes only, not
 *  already in the closed list, de-duplicated, at most
 *  MEMBER_SYMBOLS_PER_REQUEST. */
export function memberSymbols(url: URL): string[] {
  const raw = url.searchParams.get("extra");
  if (!raw) return [];
  const out: string[] = [];
  for (const part of raw.toUpperCase().split(",")) {
    const s = part.trim();
    if (!s || !MEMBER_SYMBOL_RE.test(s)) continue;
    if ((MARKET_SYMBOLS as readonly string[]).includes(s) || out.includes(s)) continue;
    out.push(s);
    if (out.length >= MEMBER_SYMBOLS_PER_REQUEST) break;
  }
  return out;
}

/** One member symbol, from its own cache, else Yahoo, else its last good
 *  copy (as a close). null when Yahoo has never answered for it. */
async function memberQuote(
  symbol: string, cache: Cache, ctx: ExecutionContext, nowS: number,
): Promise<{ quote: LiveQuote | null; stale: boolean }> {
  const key = SYMBOL_CACHE + encodeURIComponent(symbol);
  const hit = await cache.match(key);
  if (hit) {
    const cached = (await hit.json()) as { quote: LiveQuote | null };
    return { quote: cached.quote, stale: false };
  }
  const fresh = await fetchSymbol(symbol, nowS);
  const lgKey = SYMBOL_LAST_GOOD + encodeURIComponent(symbol);
  const puts: Promise<unknown>[] = [];
  let quote = fresh;
  let stale = false;
  if (fresh) {
    puts.push(cache.put(lgKey, new Response(JSON.stringify(fresh), {
      headers: { "Cache-Control": `public, max-age=${LAST_GOOD_TTL_S}` },
    })));
  } else {
    const lg = await cache.match(lgKey);
    if (lg) {
      quote = { ...((await lg.json()) as LiveQuote), state: "close" };
      stale = true;
    }
  }
  const ttl = quote?.state === "live" ? LIVE_TTL_S : CLOSED_TTL_S;
  puts.push(cache.put(key, new Response(JSON.stringify({ quote }), {
    headers: { "Cache-Control": `public, max-age=${ttl}` },
  })));
  ctx.waitUntil(Promise.all(puts));
  return { quote, stale };
}

function respond(request: Request, body: MarketsBody, maxAge: number): Response {
  const headers = new Headers(corsHeaders(request));
  headers.set("Content-Type", "application/json; charset=utf-8");
  headers.set("Cache-Control", `public, max-age=${maxAge}`);
  // A lookup that named only symbols Yahoo does not know is still an
  // answer (200 with ``unknown``); no quote at all for any reason is 503.
  const answered = body.quotes.length > 0 || (body.unknown?.length ?? 0) > 0;
  return new Response(JSON.stringify(body), { status: answered ? 200 : 503, headers });
}

export async function handleMarkets(request: Request, ctx: ExecutionContext): Promise<Response> {
  const url = new URL(request.url);
  const symbols = requestedSymbols(url);
  const cache = (caches as unknown as { default: Cache }).default;

  let all: MarketsBody | null = null;
  const hit = await cache.match(CACHE_KEY);
  if (hit) all = (await hit.json()) as MarketsBody;

  if (!all) {
    const nowS = Math.floor(Date.now() / 1000);
    const fresh = await Promise.all(MARKET_SYMBOLS.map((s) => fetchSymbol(s, nowS)));
    const lastGoodHit = await cache.match(LAST_GOOD_KEY);
    const lastGood = lastGoodHit ? ((await lastGoodHit.json()) as MarketsBody) : null;
    const byLastGood = new Map((lastGood?.quotes ?? []).map((q) => [q.symbol, q]));
    let stale = false;
    const quotes: LiveQuote[] = [];
    MARKET_SYMBOLS.forEach((s, i) => {
      const q = fresh[i];
      if (q) { quotes.push(q); return; }
      const old = byLastGood.get(s);
      if (old) {
        // An old quote is never "live": it is the price at its own time.
        quotes.push({ ...old, state: "close" });
        stale = true;
      }
    });
    all = { ok: quotes.length > 0, fetched_at: new Date().toISOString(), stale, quotes };
    const ttl = quotes.some((q) => q.state === "live") ? LIVE_TTL_S : CLOSED_TTL_S;
    const store = JSON.stringify(all);
    const put = [cache.put(CACHE_KEY, new Response(store, {
      headers: { "Cache-Control": `public, max-age=${ttl}` },
    }))];
    if (fresh.some(Boolean)) {
      const merged: MarketsBody = { ...all, stale: false,
        quotes: quotes.filter((q) => fresh.some((f) => f && f.symbol === q.symbol)) };
      for (const old of lastGood?.quotes ?? []) {
        if (!merged.quotes.some((q) => q.symbol === old.symbol)) merged.quotes.push(old);
      }
      put.push(cache.put(LAST_GOOD_KEY, new Response(JSON.stringify(merged), {
        headers: { "Cache-Control": `public, max-age=${LAST_GOOD_TTL_S}` },
      })));
    }
    ctx.waitUntil(Promise.all(put));
  }

  const want = new Set(symbols);
  const body: MarketsBody = { ...all, quotes: all.quotes.filter((q) => want.has(q.symbol)) };
  const extras = memberSymbols(url);
  if (extras.length) {
    // An explicit ``symbols=`` filter that names none of the closed list
    // asks for member symbols only.
    const nowS = Math.floor(Date.now() / 1000);
    const got = await Promise.all(extras.map((s) => memberQuote(s, cache, ctx, nowS)));
    const unknown: string[] = [];
    got.forEach((g, i) => {
      if (g.quote) {
        body.quotes.push(g.quote);
        if (g.stale) body.stale = true;
      } else {
        unknown.push(extras[i]);
      }
    });
    if (unknown.length) body.unknown = unknown;
    body.ok = body.quotes.length > 0;
  }
  const live = body.quotes.some((q) => q.state === "live");
  return respond(request, body, live ? LIVE_TTL_S : CLOSED_TTL_S);
}
