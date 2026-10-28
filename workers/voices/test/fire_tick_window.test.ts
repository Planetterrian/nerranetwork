import { afterEach, describe, expect, it, vi } from "vitest";
import { fireTickDue } from "../src/index";

// Oct 28 2026 — the fire-tick gate read interview_runs CREATED in the last
// two days, and every run is staged about a day before its slot, so each
// booking held the gate open for two days: the Worker dispatched the fire
// job 232 times on Oct 27, almost all to log "already has an active run".
// These are that day's rows, read from the nerra-voices database.

const INTERVIEWS = [
  { id: "ee929649", status: "briefed", scheduled_at: "2026-10-27T18:00:00Z" },
  { id: "fe4e6a88", status: "briefed", scheduled_at: "2026-10-28T17:30:00Z" },
];
const RUNS = [
  { id: "d0cdb835", status: "staged", created_at: "2026-10-26T18:02:59Z", scheduled_for: "2026-10-27T18:00:00Z" },
  { id: "35cdf6f4", status: "staged", created_at: "2026-10-27T17:32:47Z", scheduled_for: "2026-10-28T17:30:00Z" },
];

function matches(row: Record<string, string>, params: URLSearchParams): boolean {
  for (const [key, cond] of params.entries()) {
    if (key === "select" || key === "limit") continue;
    const value = row[key];
    if (value === undefined) return false;
    const [op, ...rest] = cond.split(".");
    const arg = rest.join(".");
    if (op === "in") {
      if (!arg.replace(/[()]/g, "").split(",").includes(value)) return false;
    } else if (op === "gte") {
      if (Date.parse(value) < Date.parse(arg)) return false;
    } else if (op === "lte") {
      if (Date.parse(value) > Date.parse(arg)) return false;
    } else if (op === "eq") {
      if (value !== arg) return false;
    } else {
      throw new Error(`unhandled filter ${key}=${cond}`);
    }
  }
  return true;
}

function env(): any {
  return { SUPABASE_URL: "https://sb.test", SUPABASE_SERVICE_KEY: "svc" };
}

function fakeSupabase(runs = RUNS) {
  const urls: string[] = [];
  globalThis.fetch = vi.fn(async (input: any) => {
    const url = typeof input === "string" ? input : input.url;
    urls.push(url);
    const u = new URL(url);
    const table = u.pathname.replace("/rest/v1/", "");
    const rows = table === "interviews" ? INTERVIEWS : table === "interview_runs" ? runs : [];
    const hit = (rows as any[]).filter((r) => matches(r, u.searchParams));
    return new Response(JSON.stringify(hit.slice(0, 1)), { status: 200 });
  }) as any;
  return urls;
}

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe("the fire-tick gate opens around a slot, never for a whole day", () => {
  it("replays Oct 27: only the ticks around the 18:00 interview dispatch", async () => {
    fakeSupabase();
    const open: string[] = [];
    for (let m = 0; m < 24 * 60; m += 5) {
      const t = new Date(Date.UTC(2026, 9, 27, 0, m));
      vi.useFakeTimers(); vi.setSystemTime(t);
      if (await fireTickDue(env())) open.push(t.toISOString().slice(11, 16));
    }
    // 18:00 minus the 140-minute lookahead to 18:00 plus the 3-hour lookback.
    expect(open[0]).toBe("15:40");
    expect(open[open.length - 1]).toBe("21:00");
    expect(open.length).toBe(65);
    // Before the fix every one of the 288 ticks was open.
  });

  it("a run staged a day ahead does not open the gate today", async () => {
    fakeSupabase();
    vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-27T23:30:00Z"));
    expect(await fireTickDue(env())).toBe(false);
  });

  it("reads runs by their slot, with Z instants", async () => {
    const urls = fakeSupabase();
    vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-27T12:00:00Z"));
    await fireTickDue(env());
    const run = urls.find((u) => u.includes("/interview_runs?"))!;
    expect(run).toContain("scheduled_for=gte.2026-10-27T09:00:00.000Z");
    expect(run).not.toContain("created_at");
    expect(run).not.toContain("+");
  });

  it("a live run past its interview's window still opens it", async () => {
    fakeSupabase([{ id: "x", status: "fired", created_at: "2026-10-27T17:58:00Z",
                    scheduled_for: "2026-10-27T18:00:00Z" }]);
    vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-27T18:30:00Z"));
    expect(await fireTickDue(env())).toBe(true);
  });

  it("fails open when Supabase is down", async () => {
    globalThis.fetch = vi.fn(async () => new Response("down", { status: 503 })) as any;
    expect(await fireTickDue(env())).toBe(true);
  });
});
