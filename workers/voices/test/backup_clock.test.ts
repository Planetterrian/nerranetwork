import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker, { CLOCK_BACK_TEXT, CLOCK_STOPPED_TEXT, runTick, tickSlot } from "../src/index";

// Oct 24 2026 — the backup clock. Cloudflare's cron for this Worker went
// dark for 23 hours on Oct 23; a guest's T-2h reminder never went out. The
// tick now runs from whichever clock claims its five-minute slot first:
// Cloudflare's cron, or Supabase's pg_cron posting /voices/cron-tick one
// minute later.

type Call = { method: string; url: string; body: any };

const ADMIN = "admin-token-admin-token";
const SECRET = "cron-tick-secret-0123456789abcdef";
const SLACK = "https://hooks.slack.test/T0/B0/x";

function env(extra: Record<string, unknown> = {}): any {
  return {
    SUPABASE_URL: "https://sb.test", SUPABASE_SERVICE_KEY: "svc",
    GITHUB_DISPATCH_TOKEN: "gh", ADMIN_TOKEN: ADMIN,
    RESEND_API_KEY: "re", VOICES_FROM_EMAIL: "mira@nerranetwork.com",
    CALCOM_BOOKING_URL: "https://cal.test/book",
    CRON_TICK_SECRET: SECRET, SLACK_WEBHOOK: SLACK,
    ...extra,
  };
}

const table = (url: string) => url.replace("https://sb.test/rest/v1/", "").split("?")[0];
const query = (url: string) => new URL(url).searchParams;

/** A Supabase that keeps cron_ticks (primary key: slot) and cron_clock_state
 *  the way the migration does, and answers every other table with []. */
function fakeSupabase(opts: { down?: boolean } = {}) {
  const ticks: { slot: string; source: string }[] = [];
  const state = { name: "cloudflare", outage_since: null as string | null, recovered_at: null as string | null };
  const calls: Call[] = [];
  const fn = vi.fn(async (input: any, init?: any) => {
    const url = typeof input === "string" ? input : input.url;
    const method = (init?.method ?? "GET").toUpperCase();
    let body: any = null;
    if (init?.body && typeof init.body === "string") {
      try { body = JSON.parse(init.body); } catch { body = init.body; }
    }
    calls.push({ method, url, body });
    if (url.startsWith("https://api.github.com/")) return new Response(null, { status: 204 });
    if (url.startsWith("https://api.resend.com/") || url.startsWith(SLACK)) return new Response("{}", { status: 200 });
    if (opts.down) return new Response("unreachable", { status: 503 });
    const t = table(url);
    const q = query(url);
    if (t === "cron_ticks" && method === "POST") {
      if (ticks.some((r) => r.slot === body.slot)) return new Response("[]", { status: 201 });
      ticks.push({ slot: body.slot, source: body.source });
      return new Response(JSON.stringify([{ ...body, claimed_at: new Date().toISOString() }]), { status: 201 });
    }
    if (t === "cron_ticks" && method === "GET") {
      let rows = ticks.slice();
      const src = q.get("source");
      if (src) rows = rows.filter((r) => `eq.${r.source}` === src);
      const gte = q.get("slot");
      if (gte && gte.startsWith("gte.")) rows = rows.filter((r) => r.slot >= gte.slice(4));
      rows.sort((a, b) => (a.slot < b.slot ? 1 : -1));
      return new Response(JSON.stringify(rows), { status: 200 });
    }
    if (t === "cron_clock_state" && method === "PATCH") {
      const cond = q.get("outage_since");
      const match = (cond === "is.null" && state.outage_since === null)
                 || (cond === "not.is.null" && state.outage_since !== null);
      if (!match) return new Response("[]", { status: 200 });
      Object.assign(state, body);
      return new Response(JSON.stringify([{ ...state }]), { status: 200 });
    }
    if (t === "cron_clock_state" && method === "GET") return new Response(JSON.stringify([{ ...state }]), { status: 200 });
    return new Response("[]", { status: 200 });
  });
  const count = (pred: (c: Call) => boolean) => calls.filter(pred).length;
  return {
    fn, calls, ticks, state,
    dispatches: () => count((c) => c.url.endsWith("/dispatches")),
    gate2Runs: () => count((c) => c.method === "GET" && table(c.url) === "editorial_packages"),
    slackTexts: () => calls.filter((c) => c.url.startsWith(SLACK)).map((c) => String(c.body?.text ?? "")),
    emails: () => calls.filter((c) => c.url.startsWith("https://api.resend.com/")),
  };
}

function cronTick(headers: Record<string, string> = {}) {
  return new Request("https://api.nerranetwork.com/voices/cron-tick", {
    method: "POST", headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ source: "supabase-pg-cron" }),
  });
}

beforeEach(() => { vi.restoreAllMocks(); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("the five-minute slot", () => {
  it("floors a firing to its five-minute UTC slot", () => {
    expect(tickSlot(new Date("2026-10-26T17:00:00Z")).toISOString()).toBe("2026-10-26T17:00:00.000Z");
    expect(tickSlot(new Date("2026-10-26T17:01:00Z")).toISOString()).toBe("2026-10-26T17:00:00.000Z");
    expect(tickSlot(new Date("2026-10-26T17:04:59.999Z")).toISOString()).toBe("2026-10-26T17:00:00.000Z");
    expect(tickSlot(new Date("2026-10-26T17:05:00Z")).toISOString()).toBe("2026-10-26T17:05:00.000Z");
    expect(tickSlot(new Date("2026-10-26T23:59:30Z")).toISOString()).toBe("2026-10-26T23:55:00.000Z");
  });
});

describe("one tick, two clocks", () => {
  it("a second claim of the same slot runs nothing", async () => {
    const sb = fakeSupabase();
    vi.stubGlobal("fetch", sb.fn);
    const first = await runTick(env(), new Date("2026-10-26T12:05:00Z"), "cloudflare");
    expect(first).toEqual({ slot: "2026-10-26T12:05:00.000Z", ran: true });
    const callsAfterFirst = sb.calls.length;
    const second = await runTick(env(), new Date("2026-10-26T12:06:00Z"), "supabase");
    expect(second).toEqual({ slot: "2026-10-26T12:05:00.000Z", ran: false });
    // The only call the second clock made was its claim.
    expect(sb.calls.slice(callsAfterFirst).map((c) => `${c.method} ${table(c.url)}`)).toEqual(["POST cron_ticks"]);
    expect(sb.ticks).toEqual([{ slot: "2026-10-26T12:05:00.000Z", source: "cloudflare" }]);
  });

  it("the backup at 17:01 runs the 17:00 gate-2 job", async () => {
    const sb = fakeSupabase();
    vi.stubGlobal("fetch", sb.fn);
    const r = await runTick(env(), new Date("2026-10-26T17:01:00Z"), "supabase");
    expect(r.ran).toBe(true);
    expect(sb.gate2Runs()).toBe(1);
  });

  it("gate-2 runs once when Cloudflare fired at 17:00 and the backup came at 17:01", async () => {
    const sb = fakeSupabase();
    vi.stubGlobal("fetch", sb.fn);
    await worker.scheduled({ scheduledTime: Date.parse("2026-10-26T17:00:00Z") } as any, env());
    await runTick(env(), new Date("2026-10-26T17:01:00Z"), "supabase");
    expect(sb.gate2Runs()).toBe(1);
  });

  it("the half-hour jobs read the slot, not the arrival minute", async () => {
    const sb = fakeSupabase();
    vi.stubGlobal("fetch", sb.fn);
    await runTick(env(), new Date("2026-10-26T12:31:00Z"), "supabase");
    const events = sb.calls.filter((c) => c.url.endsWith("/dispatches")).map((c) => c.body.event_type);
    expect(events).toContain("fire-tick");      // :30 dispatches the fire tick unconditionally
    expect(events).toContain("producer-tick");  // and the inbox (no Gmail gate configured: fail open)
  });

  it("a tick runs anyway when Supabase cannot be reached to claim it", async () => {
    const sb = fakeSupabase({ down: true });
    vi.stubGlobal("fetch", sb.fn);
    const r = await runTick(env(), new Date("2026-10-26T12:30:00Z"), "cloudflare");
    expect(r.ran).toBe(true);
    expect(sb.dispatches()).toBeGreaterThan(0);
  });
});

describe("POST /voices/cron-tick", () => {
  it("refuses a missing secret, a wrong secret and the admin token", async () => {
    const sb = fakeSupabase();
    vi.stubGlobal("fetch", sb.fn);
    for (const headers of [{}, { Authorization: "Bearer wrong" }, { Authorization: `Bearer ${ADMIN}` },
                           { Authorization: SECRET }]) {
      const resp = await worker.fetch(cronTick(headers), env());
      expect(resp.status).toBe(401);
    }
    expect(sb.ticks.length).toBe(0);
    expect(sb.dispatches()).toBe(0);
  });

  it("refuses everything when the Worker has no CRON_TICK_SECRET", async () => {
    const sb = fakeSupabase();
    vi.stubGlobal("fetch", sb.fn);
    const resp = await worker.fetch(cronTick({ Authorization: `Bearer ${SECRET}` }), env({ CRON_TICK_SECRET: "" }));
    expect(resp.status).toBe(401);
  });

  it("refuses the admin token even if it were set as the tick secret", async () => {
    const sb = fakeSupabase();
    vi.stubGlobal("fetch", sb.fn);
    const resp = await worker.fetch(cronTick({ Authorization: `Bearer ${ADMIN}` }), env({ CRON_TICK_SECRET: ADMIN }));
    expect(resp.status).toBe(401);
  });

  it("runs a supabase tick with the secret and says which slot", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-26T18:01:00Z"));
    const sb = fakeSupabase();
    vi.stubGlobal("fetch", sb.fn);
    const resp = await worker.fetch(cronTick({ Authorization: `Bearer ${SECRET}` }), env());
    expect(resp.status).toBe(200);
    expect(await resp.json()).toEqual({ slot: "2026-10-26T18:00:00.000Z", ran: true });
    expect(sb.ticks).toEqual([{ slot: "2026-10-26T18:00:00.000Z", source: "supabase" }]);
  });
});

describe("the watchdog", () => {
  it("alerts once per outage, and once when Cloudflare is back", async () => {
    const sb = fakeSupabase();
    vi.stubGlobal("fetch", sb.fn);
    await runTick(env(), new Date("2026-10-26T10:00:00Z"), "cloudflare");
    // Cloudflare goes quiet; the backup carries the slots.
    for (const t of ["10:06", "10:11", "10:16", "10:21"]) {
      await runTick(env(), new Date(`2026-10-26T${t}:00Z`), "supabase");
    }
    expect(sb.slackTexts().length).toBe(0);           // 20 minutes not yet up
    for (const t of ["10:26", "10:31", "10:36"]) {
      await runTick(env(), new Date(`2026-10-26T${t}:00Z`), "supabase");
    }
    expect(sb.slackTexts().filter((x) => x.includes(CLOCK_STOPPED_TEXT)).length).toBe(1);
    expect(sb.emails().filter((c) => c.body.subject === "Cloudflare's timer has stopped").length).toBe(1);
    expect(sb.state.outage_since).not.toBeNull();
    // Cloudflare fires again: one "back", then nothing.
    await runTick(env(), new Date("2026-10-26T10:40:00Z"), "cloudflare");
    await runTick(env(), new Date("2026-10-26T10:45:00Z"), "cloudflare");
    expect(sb.slackTexts().filter((x) => x.includes(CLOCK_BACK_TEXT)).length).toBe(1);
    expect(sb.state.outage_since).toBeNull();
    // A second outage alerts again.
    for (const t of ["11:06", "11:11", "11:16", "11:21", "11:26"]) {
      await runTick(env(), new Date(`2026-10-26T${t}:00Z`), "supabase");
    }
    expect(sb.slackTexts().filter((x) => x.includes(CLOCK_STOPPED_TEXT)).length).toBe(2);
  });

  it("a backup tick that fills one missed slot is not an outage", async () => {
    const sb = fakeSupabase();
    vi.stubGlobal("fetch", sb.fn);
    await runTick(env(), new Date("2026-10-26T10:00:00Z"), "cloudflare");
    await runTick(env(), new Date("2026-10-26T10:06:00Z"), "supabase");
    await runTick(env(), new Date("2026-10-26T10:10:00Z"), "cloudflare");
    expect(sb.slackTexts().length).toBe(0);
    expect(sb.state.outage_since).toBeNull();
  });
});

describe("/voices/health", () => {
  it("says whether the tick secret is set and the last slot each clock claimed", async () => {
    const sb = fakeSupabase();
    vi.stubGlobal("fetch", sb.fn);
    await runTick(env(), new Date("2026-10-26T10:00:00Z"), "cloudflare");
    await runTick(env(), new Date("2026-10-26T10:06:00Z"), "supabase");
    const resp = await worker.fetch(new Request("https://api.nerranetwork.com/voices/health"), env());
    const body: any = await resp.json();
    expect(body.configured.cron_tick_secret).toBe(true);
    expect(body.clocks.cloudflare.slot).toBe("2026-10-26T10:00:00.000Z");
    expect(body.clocks.supabase.slot).toBe("2026-10-26T10:05:00.000Z");
    expect(JSON.stringify(body)).not.toContain(SECRET);
  });
});
