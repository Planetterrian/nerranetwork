import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker from "../src/index";

// Oct 27 2026 — no phone interviews, and the bugs Elliot Justin's interview
// (Oct 26) and the review after it turned up: a room that failed to start
// read as a failed phone dial, two failed joins switched to a phone call, a
// short hello read as a failed join, the stuck alert said things that were
// not true, and the studio had no way to say "pick another time".

const IV = "11111111-1111-1111-1111-111111111111";
const RUN = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
type Call = { method: string; url: string; body: any };

function env(): any {
  return {
    SUPABASE_URL: "https://sb.test", SUPABASE_SERVICE_KEY: "svc",
    GITHUB_DISPATCH_TOKEN: "gh", ADMIN_TOKEN: "admin-token-admin-token",
    RESEND_API_KEY: "re", VOICES_FROM_EMAIL: "mira@nerranetwork.com",
    CALCOM_BOOKING_URL: "https://cal.test/book",
  };
}

function fakeFetch(respond: (c: Call) => any) {
  const calls: Call[] = [];
  const fn = vi.fn(async (input: any, init?: any) => {
    const url = typeof input === "string" ? input : input.url;
    const method = (init?.method ?? "GET").toUpperCase();
    let body: any = null;
    if (init?.body && typeof init.body === "string") {
      try { body = JSON.parse(init.body); } catch { body = init.body; }
    }
    const call = { method, url, body };
    calls.push(call);
    if (url.endsWith("/dispatches")) return new Response(null, { status: 204 });
    if (url.startsWith("https://api.resend.com/")) return new Response("{}", { status: 200 });
    if (url.startsWith("https://hooks.slack.com/")) return new Response("ok", { status: 200 });
    return new Response(JSON.stringify(respond(call) ?? []), { status: 200 });
  });
  return { fn, calls };
}

const post = (path: string, body: unknown) => new Request(`https://api.nerranetwork.com${path}`, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const get = (path: string) => new Request(`https://api.nerranetwork.com${path}`);
const sbTable = (url: string) => url.replace("https://sb.test/rest/v1/", "").split("?")[0];
const emails = (calls: Call[]) => calls.filter((c) => c.url.startsWith("https://api.resend.com/"));
const ivPatches = (calls: Call[]) => calls.filter((c) => c.method === "PATCH" && sbTable(c.url) === "interviews");

beforeEach(() => { vi.restoreAllMocks(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe("no phone calls", () => {
  it("the old 'call their phone' admin link is retired", async () => {
    const { fn, calls } = fakeFetch(() => []);
    vi.stubGlobal("fetch", fn);
    for (const req of [get(`/voices/admin/call-guest?interview=${IV}&sig=x`), post(`/voices/admin/call-guest?interview=${IV}&sig=x`, {})]) {
      const resp = await worker.route(req, env());
      expect(resp.status).toBe(410);
      expect(await resp.text()).toMatch(/Phone interviews are no longer offered/);
    }
    expect(calls.length).toBe(0);
  });

  it("the admin text-guest link refuses a bad signature", async () => {
    const { fn } = fakeFetch(() => []);
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(get(`/voices/admin/text-guest?interview=${IV}&sig=nope`), env());
    expect(await resp.text()).toMatch(/Link not valid/);
  });

  it("two failed joins never switch to a phone call: the studio reopens and the guest gets the phone-browser and move links", async () => {
    const { fn, calls } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.method === "GET" && t === "interview_runs" && c.url.includes("select=grok_session_log,status")) {
        return [{ grok_session_log: { aborted_attempts: 1 }, status: "in_progress", disconnect_reason: null, session_kind: "interview" }];
      }
      if (c.method === "GET" && t === "interview_runs") return [{ interview_id: IV, grok_session_log: { aborted_attempts: 1 }, guest_joined_at: "2026-10-26T20:01:00Z" }];
      if (c.method === "GET" && t === "interviews") return [{ id: IV, application_id: "a1", show: "nerra_voices", manage_token: "mt123" }];
      if (c.method === "GET" && t === "guest_applications") return [{ name: "Elliot Justin", email: "elliot@example.com" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post("/voices/interview-complete",
      { run_id: RUN, status: "completed", call_mode: "webrtc", duration_sec: 40 }), env());
    expect(await resp.json()).toMatchObject({ ok: true, aborted_join: true, attempt: 2 });
    const patrick = emails(calls).find((c) => String(c.body.subject).includes("dropped early"));
    expect(patrick!.body.html).toContain("I've emailed them");
    expect(ivPatches(calls).some((c) => JSON.stringify(c.body).includes("pstn"))).toBe(false);
    const runPatch = calls.find((c) => c.method === "PATCH" && sbTable(c.url) === "interview_runs");
    expect(runPatch?.body.status).toBe("awaiting_guest");
    const guest = emails(calls).find((c) => (c.body.to ?? []).includes?.("elliot@example.com") || JSON.stringify(c.body.to).includes("elliot@example.com"));
    expect(guest).toBeTruthy();
    expect(guest!.body.html).toContain("on your phone");
    expect(guest!.body.html).toContain("/voices/manage/mt123");
    expect(guest!.body.html).not.toMatch(/call your phone|I'll call/i);
  });

  it("a co-host testing on his own is not the guest's studio dropping: no guest email", async () => {
    const { fn, calls } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.method === "GET" && t === "interview_runs" && c.url.includes("select=grok_session_log,status")) {
        return [{ grok_session_log: { aborted_attempts: 1 }, status: "in_progress", disconnect_reason: null, session_kind: "interview" }];
      }
      if (c.method === "GET" && t === "interview_runs") return [{ interview_id: IV, grok_session_log: { aborted_attempts: 1 }, guest_joined_at: null }];
      if (c.method === "GET" && t === "interviews") return [{ id: IV, application_id: "a1", show: "nerra_voices", manage_token: "mt123" }];
      if (c.method === "GET" && t === "guest_applications") return [{ name: "Elliot Justin", email: "elliot@example.com" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    await worker.route(post("/voices/interview-complete",
      { run_id: RUN, status: "completed", call_mode: "webrtc", duration_sec: 40 }), env());
    expect(emails(calls).some((c) => JSON.stringify(c.body.to).includes("elliot@example.com"))).toBe(false);
    const patrick = emails(calls).find((c) => String(c.body.subject).includes("dropped early"));
    expect(patrick!.body.html).not.toContain("I've emailed them");
  });

  it("a room that failed to start is a platform fault: the studio reopens, the guest is not told 'I called twice'", async () => {
    const { fn, calls } = fakeFetch((c) => {
      if (c.method === "GET" && sbTable(c.url) === "interview_runs") {
        return [{ grok_session_log: {}, status: "awaiting_guest", disconnect_reason: null, session_kind: "interview" }];
      }
      return [];
    });
    vi.stubGlobal("fetch", fn);
    // The scenario deployed before Oct 27 posts this, with no call_mode.
    const resp = await worker.route(post("/voices/interview-complete",
      { run_id: RUN, status: "failed", reason: "startup: no interview_runs row for x" }), env());
    expect(await resp.json()).toMatchObject({ ok: true, platform_fault: true, reopened: true });
    expect(ivPatches(calls).length).toBe(0);
    const runPatch = calls.find((c) => c.method === "PATCH" && sbTable(c.url) === "interview_runs");
    expect(runPatch?.body.status).toBe("awaiting_guest");
    expect(calls.some((c) => c.url.endsWith("/dispatches"))).toBe(false);
    for (const e of emails(calls)) expect(JSON.stringify(e.body)).not.toMatch(/called twice/);
  });

  it("the same from the new scenario: room_startup_failed", async () => {
    const { fn } = fakeFetch((c) => (c.method === "GET" && sbTable(c.url) === "interview_runs")
      ? [{ grok_session_log: {}, status: "awaiting_guest", disconnect_reason: null, session_kind: "interview" }] : []);
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post("/voices/interview-complete",
      { run_id: RUN, status: "failed", call_mode: "webrtc", disconnect_reason: "room_startup_failed" }), env());
    expect(await resp.json()).toMatchObject({ platform_fault: true, reopened: true });
  });

  it("a short hello is not a failed join: it goes to post-production for its agenda", async () => {
    const { fn, calls } = fakeFetch((c) => (c.method === "GET" && sbTable(c.url) === "interview_runs")
      ? [{ grok_session_log: {}, status: "in_progress", disconnect_reason: null, session_kind: "hello" }] : []);
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post("/voices/interview-complete",
      { run_id: RUN, status: "completed", call_mode: "webrtc", duration_sec: 230 }), env());
    expect(resp.status).toBe(200);
    expect(calls.some((c) => c.url.endsWith("/dispatches") && c.body.event_type === "interview-complete")).toBe(true);
    const runPatch = calls.find((c) => c.method === "PATCH" && sbTable(c.url) === "interview_runs");
    expect(runPatch?.body.status).toBe("completed");
  });

  it("a short interview session is still a failed join (the studio reopens)", async () => {
    const { fn, calls } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.method === "GET" && t === "interview_runs" && c.url.includes("select=grok_session_log,status")) {
        return [{ grok_session_log: {}, status: "in_progress", disconnect_reason: null, session_kind: "interview" }];
      }
      if (c.method === "GET" && t === "interview_runs") return [{ interview_id: IV, grok_session_log: {} }];
      if (c.method === "GET" && t === "interviews") return [{ application_id: "a1", show: "nerra_voices" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post("/voices/interview-complete",
      { run_id: RUN, status: "completed", call_mode: "webrtc", duration_sec: 73 }), env());
    expect(await resp.json()).toMatchObject({ aborted_join: true, attempt: 1 });
    expect(calls.some((c) => c.url.endsWith("/dispatches"))).toBe(false);
  });
});

describe("/voices/studio-reschedule", () => {
  const live = (extra: Record<string, unknown> = {}) => fakeFetch((c) => {
    const t = sbTable(c.url);
    if (c.method === "GET" && t === "interviews") {
      return [{ id: IV, status: "briefed", scheduled_at: new Date().toISOString(), show: "nerra_voices",
                application_id: "a1", manage_token: "mt123", studio_reschedule_sent_at: null, ...extra }];
    }
    if (c.method === "GET" && t === "guest_applications") return [{ name: "Elliot Justin", email: "elliot@example.com" }];
    return [];
  });

  it("emails the guest their move link at the address on file, once", async () => {
    const { fn, calls } = live();
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post("/voices/studio-reschedule", { interview: IV, email: "attacker@evil.test" }), env());
    expect(await resp.json()).toEqual({ ok: true });
    const sent = emails(calls);
    expect(sent.length).toBeGreaterThan(0);
    expect(JSON.stringify(sent[0].body.to)).toContain("elliot@example.com");
    expect(JSON.stringify(sent.map((e) => e.body))).not.toContain("attacker@evil.test");
    expect(sent[0].body.html).toContain("/voices/manage/mt123");
    expect(ivPatches(calls)[0].body.studio_reschedule_sent_at).toBeTruthy();
  });

  it("a failed send leaves no stamp, so the guest can try again at once", async () => {
    const { fn, calls } = live();
    const failing = vi.fn(async (input: any, init?: any) => {
      const url = typeof input === "string" ? input : input.url;
      if (url.startsWith("https://api.resend.com/")) return new Response("down", { status: 500 });
      return fn(input, init);
    });
    vi.stubGlobal("fetch", failing);
    const resp = await worker.route(post("/voices/studio-reschedule", { interview: IV }), env());
    expect(resp.status).toBe(502);
    expect(ivPatches(calls).some((c) => c.body.studio_reschedule_sent_at)).toBe(false);
  });

  it("does not send it again within ten minutes", async () => {
    const { fn, calls } = live({ studio_reschedule_sent_at: new Date(Date.now() - 60_000).toISOString() });
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post("/voices/studio-reschedule", { interview: IV }), env());
    expect(await resp.json()).toEqual({ ok: true, already_sent: true });
    expect(emails(calls).length).toBe(0);
  });

  it("refuses an interview that isn't on", async () => {
    const { fn, calls } = live({ status: "cancelled" });
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post("/voices/studio-reschedule", { interview: IV }), env());
    expect(resp.status).toBe(409);
    expect(emails(calls).length).toBe(0);
  });
});

describe("studio-state and the stuck alert", () => {
  it("a guest's poll stamps studio_seen_at, at most once a minute", async () => {
    const seen = (at: string | null) => fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.method === "GET" && t === "interviews") {
        return [{ id: IV, status: "briefed", scheduled_at: new Date(Date.now() + 864e5).toISOString(),
                  show: "nerra_voices", application_id: "a1", studio_seen_at: at }];
      }
      return [];
    });
    let f = seen(null); vi.stubGlobal("fetch", f.fn);
    await worker.route(get(`/voices/studio-state?interview=${IV}&role=guest`), env());
    expect(ivPatches(f.calls).some((c) => c.body.studio_seen_at)).toBe(true);
    f = seen(new Date().toISOString()); vi.stubGlobal("fetch", f.fn);
    await worker.route(get(`/voices/studio-state?interview=${IV}&role=guest`), env());
    expect(ivPatches(f.calls).some((c) => c.body.studio_seen_at)).toBe(false);
  });

  it("says Join was pressed and failed when it was, and offers the phone-browser link, not a call", async () => {
    const { fn, calls } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.method === "GET" && t === "interviews") {
        return [{ id: IV, status: "briefed", scheduled_at: new Date().toISOString(), show: "nerra_voices",
                  application_id: "a1", setup_check: null }];
      }
      if (c.method === "GET" && t === "guest_applications") return [{ id: "a1", name: "Elliot Justin", email: "e@x.test", phone: "+16095550100" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    await worker.route(post("/voices/studio-check", { interview: IV, role: "guest", mic: "ok", echo: "clean",
      stuck: true, minutes_late: 3, join_attempted: true, join_error: "Couldn't reach the Voximplant media servers" }), env());
    const alert = emails(calls).find((c) => String(c.body.subject).includes("isn't in the interview"));
    expect(alert).toBeTruthy();
    expect(alert!.body.html).toContain("They pressed Join and it failed");
    expect(alert!.body.html).toContain("/voices/admin/text-guest?interview");
    expect(alert!.body.html).not.toMatch(/phone call|call-guest|Have Mira call/);
  });

  it("a stuck alert raised for an earlier slot does not silence this one", async () => {
    const { fn, calls } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.method === "GET" && t === "interviews") {
        return [{ id: IV, status: "briefed", scheduled_at: new Date().toISOString(), show: "nerra_voices",
                  application_id: "a1", setup_check: { stuck_alerted_at: "2026-10-20T20:03:00Z" } }];
      }
      if (c.method === "GET" && t === "guest_applications") return [{ id: "a1", name: "Elliot Justin", email: "e@x.test" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post("/voices/studio-check", { interview: IV, role: "guest", mic: "ok", echo: "clean", stuck: true }), env());
    expect(await resp.json()).toMatchObject({ stuck: true, alerted: true });
    expect(emails(calls).some((c) => String(c.body.subject).includes("isn't in the interview"))).toBe(true);
  });

  it("a check that passed and was reset is not called 'not run yet'", async () => {
    const { fn, calls } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.method === "GET" && t === "interviews") {
        return [{ id: IV, status: "briefed", scheduled_at: new Date().toISOString(), show: "nerra_voices",
                  application_id: "a1", setup_check: null }];
      }
      if (c.method === "GET" && t === "guest_applications") return [{ id: "a1", name: "Elliot Justin", email: "e@x.test" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    await worker.route(post("/voices/studio-check", { interview: IV, role: "guest", mic: "unknown", echo: "not_run", stuck: true }), env());
    const alert = emails(calls).find((c) => String(c.body.subject).includes("isn't in the interview"));
    expect(alert!.body.html).toContain("hasn't passed on this page yet");
  });
});
