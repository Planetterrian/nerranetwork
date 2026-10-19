import { afterEach, describe, expect, it, vi } from "vitest";
import {
  handleMarkets, MARKET_SYMBOLS, parseChart, requestedSymbols,
} from "../src/markets";

// Unix seconds for 16:00 ET closes (EDT, UTC-4) and a session window.
const close = (iso: string) => Date.parse(`${iso}T20:00:00Z`) / 1000;
const MON = "2026-10-19";
const OPEN = Date.parse(`${MON}T13:30:00Z`) / 1000;   // 09:30 ET
const SHUT = Date.parse(`${MON}T20:00:00Z`) / 1000;   // 16:00 ET

function chart(price: number, t: number, bars: [string, number][], extra: object = {}) {
  return {
    chart: { result: [{
      meta: {
        regularMarketPrice: price, regularMarketTime: t,
        chartPreviousClose: 445.27,          // the close BEFORE the range — never used
        currentTradingPeriod: { regular: { start: OPEN, end: SHUT } },
        ...extra,
      },
      timestamp: bars.map(([d]) => Date.parse(`${d}T13:30:00Z`) / 1000),
      indicators: { quote: [{ close: bars.map(([, c]) => c) }] },
    }] },
  };
}

const WEEK: [string, number][] = [
  ["2026-10-13", 350], ["2026-10-14", 352], ["2026-10-15", 360],
  ["2026-10-16", 354.72],
];

describe("parseChart", () => {
  it("is live inside the session and compares with the last bar before today", () => {
    const now = Date.parse(`${MON}T16:21:00Z`) / 1000;              // 12:21 ET
    const q = parseChart("TSLA", chart(368.18, now - 30, [...WEEK, [MON, 368.18]]), now)!;
    expect(q.state).toBe("live");
    expect(q.prev_close).toBe(354.72);
    expect(q.change_pct).toBeCloseTo(3.8, 1);
    expect(q.as_of).toBe(new Date((now - 30) * 1000).toISOString());
  });

  it("before the open the price is Friday's close, compared with Thursday's", () => {
    const now = Date.parse(`${MON}T12:00:00Z`) / 1000;              // 08:00 ET
    const q = parseChart("TSLA", chart(354.72, close("2026-10-16"), WEEK), now)!;
    expect(q.state).toBe("close");
    expect(q.prev_close).toBe(360);
    expect(q.as_of.slice(0, 10)).toBe("2026-10-16");
  });

  it("never reads chartPreviousClose as the previous close", () => {
    const now = Date.parse(`${MON}T16:21:00Z`) / 1000;
    const q = parseChart("TSLA", chart(368.18, now, [[MON, 368.18]]), now)!;
    expect(q.prev_close).toBeNull();
    expect(q.change_pct).toBeNull();
  });

  it("rejects an empty or zero quote", () => {
    expect(parseChart("TSLA", {}, 0)).toBeNull();
    expect(parseChart("TSLA", chart(0, 1, WEEK), 2)).toBeNull();
  });
});

describe("requestedSymbols", () => {
  it("serves only the closed list", () => {
    expect(requestedSymbols(new URL("https://x/api/markets"))).toEqual([...MARKET_SYMBOLS]);
    expect(requestedSymbols(new URL("https://x/api/markets?symbols=tsla,EVIL,spcx")))
      .toEqual(["TSLA", "SPCX"]);
  });
});

class MemCache {
  store = new Map<string, string>();
  async match(key: string) {
    const v = this.store.get(key);
    return v === undefined ? undefined : new Response(v);
  }
  async put(key: string, resp: Response) { this.store.set(key, await resp.text()); }
}

function ctx() {
  const pending: Promise<unknown>[] = [];
  return { pending, waitUntil: (p: Promise<unknown>) => pending.push(p),
    passThroughOnException() {} } as unknown as ExecutionContext & { pending: Promise<unknown>[] };
}

describe("handleMarkets", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("answers the site with CORS and a short public cache, from one fetch per symbol", async () => {
    const mem = new MemCache();
    vi.stubGlobal("caches", { default: mem });
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(
      chart(100, close("2026-10-16"), WEEK))));
    vi.stubGlobal("fetch", fetchMock);
    const req = new Request("https://api.nerranetwork.com/api/markets?symbols=TSLA,NVDA",
      { headers: { Origin: "https://nerranetwork.com" } });
    const c = ctx();
    const resp = await handleMarkets(req, c);
    await Promise.all(c.pending);
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Access-Control-Allow-Origin")).toBe("https://nerranetwork.com");
    expect(resp.headers.get("Cache-Control")).toMatch(/^public, max-age=\d+$/);
    const body = await resp.json() as { quotes: { symbol: string }[] };
    expect(body.quotes.map((q) => q.symbol)).toEqual(["TSLA", "NVDA"]);
    expect(fetchMock).toHaveBeenCalledTimes(MARKET_SYMBOLS.length);

    // A second request inside the TTL is served from the cache.
    await handleMarkets(req, ctx());
    expect(fetchMock).toHaveBeenCalledTimes(MARKET_SYMBOLS.length);
  });

  it("a refused fetch shows the last good quote as a close, never as live", async () => {
    const mem = new MemCache();
    vi.stubGlobal("caches", { default: mem });
    mem.store.set("https://api.nerranetwork.com/__cache/markets/last-good/v1", JSON.stringify({
      ok: true, fetched_at: "2026-10-19T15:00:00Z", stale: false,
      quotes: [{ symbol: "TSLA", price: 360, prev_close: 354.72, change_pct: 1.49,
        state: "live", as_of: "2026-10-19T14:59:00.000Z" }],
    }));
    vi.stubGlobal("fetch", vi.fn(async () => new Response("Too Many Requests", { status: 429 })));
    const resp = await handleMarkets(new Request("https://api.nerranetwork.com/api/markets"), ctx());
    const body = await resp.json() as { stale: boolean; quotes: { symbol: string; state: string }[] };
    expect(body.stale).toBe(true);
    expect(body.quotes).toEqual([expect.objectContaining({ symbol: "TSLA", state: "close" })]);
  });

  it("answers 503 with no quotes when nothing was ever fetched", async () => {
    vi.stubGlobal("caches", { default: new MemCache() });
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("down"); }));
    const resp = await handleMarkets(new Request("https://api.nerranetwork.com/api/markets"), ctx());
    expect(resp.status).toBe(503);
  });
});
