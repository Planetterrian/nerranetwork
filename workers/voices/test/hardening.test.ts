import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker, {
  guestDecision, guestReceipt, guestReviewState, openRequests, operatorReviewState,
  CALCOM_SIGNATURE_HEADER, HELLO_MINUTES, LIVE_INTERVIEW_STATUSES, SIGNATURE_HEADER,
  isHelloBooking,
  STUDIO_OPENS_BEFORE_TEXT, hmacHex, lessonDecisionAllowed, mergeWindows,
  redactionWindows, reviewTranscriptHtml, roomCountersOf, signatureOk, surveyAnswers,
  transcriptLines, webhookVerdict,
} from "../src/index";

// Oct 21 2026 — the hardening pass from the Age of AI review: signed
// webhooks, lesson ownership, a studio-phone that cannot dial a finished
// interview, gate-2 housekeeping that survives one failure, approval that is
// recorded before the dispatch and marked only after it, a /join that needs
// a token, the fifteen-minute copy, the survey page and redaction windows.

const IV = "11111111-1111-1111-1111-111111111111";
const IV2 = "22222222-2222-2222-2222-222222222222";
const PKG = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const RUN = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
const LESSON = "cccccccc-cccc-cccc-cccc-cccccccccccc";

type Call = { method: string; url: string; body: any };

function env(extra: Record<string, unknown> = {}): any {
  return {
    SUPABASE_URL: "https://sb.test", SUPABASE_SERVICE_KEY: "svc",
    GITHUB_DISPATCH_TOKEN: "gh", ADMIN_TOKEN: "admin-token-admin-token",
    RESEND_API_KEY: "re", VOICES_FROM_EMAIL: "mira@nerranetwork.com",
    CALCOM_BOOKING_URL: "https://cal.test/book",
    ...extra,
  };
}

/** A fetch that answers Supabase, GitHub and Resend from a table of
 *  responders and records every call. */
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
    if (url.startsWith("https://api.github.com/repos/") && url.endsWith("/dispatches")) {
      const r = respond(call);
      return new Response(null, { status: r === "fail" ? 500 : 204 });
    }
    if (url.startsWith("https://api.resend.com/")) {
      const r = respond(call);
      if (r === "fail") return new Response("boom", { status: 500 });
      return new Response("{}", { status: 200 });
    }
    const r = respond(call);
    if (r === "fail") return new Response("db down", { status: 500 });
    return new Response(JSON.stringify(r ?? []), { status: 200 });
  });
  return { fn, calls };
}

function post(path: string, body: unknown, headers: Record<string, string> = {}) {
  return new Request(`https://api.nerranetwork.com${path}`, {
    method: "POST", headers: { "Content-Type": "application/json", ...headers },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

const sbTable = (url: string) => url.replace("https://sb.test/rest/v1/", "").split("?")[0];

beforeEach(() => { vi.restoreAllMocks(); });
afterEach(() => { vi.unstubAllGlobals(); });

// ---------------------------------------------------------------------------
// 2. Webhook signatures
// ---------------------------------------------------------------------------

describe("webhook signatures", () => {
  const secret = "s3cret";
  const body = JSON.stringify({ run_id: RUN, status: "completed", duration_sec: 2000 });

  it("accepts the hex HMAC-SHA256 of the raw body, bare or sha256= prefixed", async () => {
    const hex = await hmacHex(secret, body);
    expect(hex).toMatch(/^[0-9a-f]{64}$/);
    expect(await signatureOk(secret, hex, body)).toBe(true);
    expect(await signatureOk(secret, `sha256=${hex.toUpperCase()}`, body)).toBe(true);
    expect(await signatureOk(secret, hex.replace(/^./, (c) => (c === "0" ? "1" : "0")), body)).toBe(false);
    expect(await signatureOk(secret, null, body)).toBe(false);
  });

  it("accepts anything unsigned while the Worker has no secret", async () => {
    expect(await webhookVerdict({}, null, body, true)).toBe("ok");
    expect(await webhookVerdict({ VOICES_WEBHOOK_SECRET: "  " }, "junk", body, true)).toBe("ok");
  });

  it("with the secret set: a scenario route refuses a missing or wrong header", async () => {
    const e = { VOICES_WEBHOOK_SECRET: secret };
    expect(await webhookVerdict(e, null, body, true)).toBe("bad");
    expect(await webhookVerdict(e, "deadbeef", body, true)).toBe("bad");
    expect(await webhookVerdict(e, await hmacHex(secret, body), body, true)).toBe("ok");
    // a shared route: unsigned passes, a bad signature does not
    expect(await webhookVerdict(e, null, body, false)).toBe("unsigned");
    expect(await webhookVerdict(e, "deadbeef", body, false)).toBe("bad");
  });

  it("/voices/interview-complete is 401 without the signature and runs with it", async () => {
    const { fn, calls } = fakeFetch((c) => {
      if (c.method === "GET" && sbTable(c.url) === "interview_runs") {
        return [{ grok_session_log: {}, status: "in_progress", disconnect_reason: null }];
      }
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const e = env({ VOICES_WEBHOOK_SECRET: secret });
    const unsigned = await worker.route(post("/voices/interview-complete", body), e);
    expect(unsigned.status).toBe(401);
    expect(calls.length).toBe(0);
    const wrong = await worker.route(
      post("/voices/interview-complete", body, { [SIGNATURE_HEADER]: "00" }), e);
    expect(wrong.status).toBe(401);
    const signed = await worker.route(
      post("/voices/interview-complete", body, { [SIGNATURE_HEADER]: await hmacHex(secret, body) }), e);
    expect(signed.status).toBe(200);
    expect(calls.some((c) => c.url.endsWith("/dispatches") && c.body.event_type === "interview-complete")).toBe(true);
  });

  it("/voices/leg-event and /voices/narration-take take the same gate", async () => {
    const { fn } = fakeFetch(() => []);
    vi.stubGlobal("fetch", fn);
    const e = env({ VOICES_WEBHOOK_SECRET: secret });
    const leg = await worker.route(post("/voices/leg-event", { run_id: RUN, role: "guest", event: "joined" }), e);
    expect(leg.status).toBe(401);
    const take = await worker.route(post("/voices/narration-take", { take_id: "t1", status: "ok" }), e);
    expect(take.status).toBe(401);
  });

  it("/voices/studio-silence: the room's post must be signed, the browser's need not be", async () => {
    const { fn } = fakeFetch((c) => {
      if (c.method === "GET" && sbTable(c.url) === "interview_runs") {
        return [{ id: RUN, interview_id: IV, status: "in_progress", grok_session_log: { silence_alerts: [{}] } }];
      }
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const e = env({ VOICES_WEBHOOK_SECRET: secret });
    const scenario = JSON.stringify({ run_id: RUN, source: "scenario", seconds: 30 });
    expect((await worker.route(post("/voices/studio-silence", scenario), e)).status).toBe(401);
    const signed = post("/voices/studio-silence", scenario, { [SIGNATURE_HEADER]: await hmacHex(secret, scenario) });
    expect((await worker.route(signed, e)).status).toBe(200);
    const browser = post("/voices/studio-silence", { run_id: RUN, source: "studio", seconds: 30 });
    expect((await worker.route(browser, e)).status).toBe(200);
  });

  it("Cal.com: the body is verified against X-Cal-Signature-256 when the secret is set", async () => {
    const { fn } = fakeFetch(() => []);
    vi.stubGlobal("fetch", fn);
    const e = env({ CALCOM_WEBHOOK_SECRET: "cal" });
    const hook = JSON.stringify({ triggerEvent: "BOOKING_CREATED", payload: {} });
    expect((await worker.route(post("/voices/cal-com-booked", hook), e)).status).toBe(401);
    const ok = post("/voices/cal-com-booked", hook, { [CALCOM_SIGNATURE_HEADER]: await hmacHex("cal", hook) });
    // Signature passes; the payload has no email, so the handler's own 400.
    expect((await worker.route(ok, e)).status).toBe(400);
  });
});

// ---------------------------------------------------------------------------
// 1. Lesson ownership
// ---------------------------------------------------------------------------

describe("lesson decisions", () => {
  it("a review link may decide only its own interview's show lessons", () => {
    expect(lessonDecisionAllowed({ show: "age_of_ai", interview_id: IV }, { interview_id: IV })).toBe(true);
    expect(lessonDecisionAllowed({ show: "age_of_ai", interview_id: IV2 }, { interview_id: IV })).toBe(false);
    expect(lessonDecisionAllowed({ show: "network", interview_id: IV }, { interview_id: IV })).toBe(false);
    expect(lessonDecisionAllowed({ show: "age_of_ai", interview_id: null }, { interview_id: IV })).toBe(false);
    expect(lessonDecisionAllowed({ show: "age_of_ai", interview_id: IV }, null)).toBe(false);
  });

  it("/voices/lesson-decision: 403 for another interview's lesson, 200 with the admin token", async () => {
    const { fn, calls } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.method === "GET" && t === "show_lessons") return [{ id: LESSON, show: "age_of_ai", interview_id: IV2, status: "active" }];
      if (c.method === "GET" && t === "editorial_packages") return [{ id: PKG, interview_id: IV }];
      if (c.method === "PATCH" && t === "show_lessons") return [{ id: LESSON, status: "retired" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const e = env();
    // the package's review token: hex(HMAC(ADMIN_TOKEN, "nerra-review:" + id))[:40]
    const reviewToken = (await hmacHex(e.ADMIN_TOKEN, `nerra-review:${PKG}`)).slice(0, 40);
    const viaLink = await worker.route(
      post(`/voices/lesson-decision?token=${reviewToken}`, { package_id: PKG, lesson_id: LESSON, status: "retired" }), e);
    expect(viaLink.status).toBe(403);
    expect(calls.filter((c) => c.method === "PATCH").length).toBe(0);
    const asAdmin = await worker.route(
      post(`/voices/lesson-decision?token=${e.ADMIN_TOKEN}`, { package_id: PKG, lesson_id: LESSON, status: "retired" }), e);
    expect(asAdmin.status).toBe(200);
    const patch = calls.find((c) => c.method === "PATCH" && sbTable(c.url) === "show_lessons");
    expect(patch?.body.decided_by).toBe("patrick");
  });
});

// ---------------------------------------------------------------------------
// 3. Studio phone cannot dial a finished interview
// ---------------------------------------------------------------------------

describe("/voices/studio-phone", () => {
  // Oct 27 2026: phone interviews are gone. The endpoint a cached studio page
  // still calls answers 410 for every interview, live or not, and touches
  // nothing.
  it("is retired: 410 for every status, and nothing is written or dispatched", async () => {
    expect([...LIVE_INTERVIEW_STATUSES].sort()).toEqual(["briefed", "in_progress", "scheduled"]);
    for (const status of ["briefed", "in_progress", "completed", "published"]) {
      const { fn, calls } = fakeFetch((c) => {
        const t = sbTable(c.url);
        if (t === "interviews") return [{ id: IV, status, scheduled_at: new Date().toISOString(), application_id: "x", show: "age_of_ai" }];
        if (t === "guest_applications") return [{ id: "x", name: "A Guest", email: "a@b.c", phone: "+16045550123" }];
        return [];
      });
      vi.stubGlobal("fetch", fn);
      const resp = await worker.route(post("/voices/studio-phone", { interview: IV }), env());
      expect(resp.status, status).toBe(410);
      const out: any = await resp.json();
      expect(out.error).toMatch(/phone's browser/);
      expect(calls.length, status).toBe(0);
    }
  });
});

// ---------------------------------------------------------------------------
// 4 + 5. Gate-2 housekeeping and dispatch ordering
// ---------------------------------------------------------------------------

function housekeepingFetch(opts: { failFirstEmail?: boolean; failDispatch?: boolean }) {
  const past = new Date(Date.now() - 864e5).toISOString();      // day 7 passed
  const day4 = new Date(Date.now() + 2.5 * 864e5).toISOString(); // reminder window
  let emails = 0;
  return fakeFetch((c) => {
    const t = sbTable(c.url);
    if (c.url.startsWith("https://api.resend.com/")) {
      emails += 1;
      return opts.failFirstEmail && emails === 1 ? "fail" : null;
    }
    if (c.url.endsWith("/dispatches")) return opts.failDispatch ? "fail" : null;
    // Oct 24 2026: the tick claims its five-minute slot first.
    if (c.method === "POST" && t === "cron_ticks") return [{ slot: c.body.slot, source: c.body.source }];
    if (c.method === "GET" && t === "editorial_packages") {
      return [
        { id: "p-reminder", interview_id: IV, guest_review_deadline: day4, guest_review_token: "tok1tok1tok1tok1tok1" },
        { id: "p-auto", interview_id: IV2, guest_review_deadline: past, guest_review_token: "tok2tok2tok2tok2tok2" },
      ];
    }
    if (c.method === "GET" && t === "interviews") {
      const id = c.url.includes(IV2) ? IV2 : IV;
      return [{ id, application_id: "app", status: "guest_review", show: "age_of_ai" }];
    }
    if (c.method === "GET" && t === "guest_applications") return [{ id: "app", name: "Guest", email: "g@x.y" }];
    return [];
  });
}

describe("gate2Housekeeping", () => {
  it("one failed reminder email does not stop the later packages", async () => {
    const { fn, calls } = housekeepingFetch({ failFirstEmail: true });
    vi.stubGlobal("fetch", fn);
    const fired = new Date("2026-10-21T17:00:00Z");
    await worker.scheduled({ scheduledTime: fired.getTime() } as any, env());
    const dispatched = calls.filter((c) => c.url.endsWith("/dispatches") && c.body.event_type === "interview-approved-by-guest");
    expect(dispatched.length).toBe(1);
    const approved = calls.find((c) => c.method === "PATCH" && sbTable(c.url) === "editorial_packages"
      && c.url.includes("p-auto") && c.body.status === "approved_by_guest");
    expect(approved).toBeTruthy();
  });

  it("marks a package approved only after the dispatch succeeded", async () => {
    const { fn, calls } = housekeepingFetch({ failDispatch: true });
    vi.stubGlobal("fetch", fn);
    await worker.scheduled({ scheduledTime: Date.parse("2026-10-21T17:00:00Z") } as any, env());
    const approved = calls.filter((c) => c.method === "PATCH" && sbTable(c.url) === "editorial_packages"
      && c.body.status === "approved_by_guest");
    expect(approved.length).toBe(0);
    // the interview is marked, so the next day's run retries the dispatch
    const ivPatch = calls.find((c) => c.method === "PATCH" && sbTable(c.url) === "interviews" && c.body.status === "approved");
    expect(ivPatch).toBeTruthy();
  });
});

describe("guest approval on the review page", () => {
  function reviewFetch(failDispatch: boolean) {
    return fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.url.endsWith("/dispatches")) return failDispatch ? "fail" : null;
      if (c.method === "GET" && t === "editorial_packages") {
        return [{ id: PKG, interview_id: IV, status: "approved_by_patrick", guest_review_token: "tok", guest_redaction_windows: [] }];
      }
      if (c.method === "GET" && t === "interviews") return [{ id: IV, application_id: "app", show: "age_of_ai" }];
      if (c.method === "GET" && t === "guest_applications") return [{ id: "app", name: "Guest", email: "g@x.y" }];
      return [];
    });
  }

  it("records the yes first, dispatches, then marks the package approved", async () => {
    const { fn, calls } = reviewFetch(false);
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post("/voices/review/tokentokentokentoken", { approve: true }), env());
    expect(resp.status).toBe(200);
    const order = calls.filter((c) => c.method === "PATCH" || c.url.endsWith("/dispatches"))
      .map((c) => c.url.endsWith("/dispatches") ? "dispatch" : `${sbTable(c.url)}:${c.body.status ?? "-"}`);
    expect(order.indexOf("dispatch")).toBeGreaterThan(order.indexOf("interviews:approved"));
    expect(order.indexOf("editorial_packages:approved_by_guest")).toBeGreaterThan(order.indexOf("dispatch"));
  });

  it("a thrown dispatch leaves the package for housekeeping to retry", async () => {
    const { fn, calls } = reviewFetch(true);
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post("/voices/review/tokentokentokentoken", { approve: true }), env());
    expect(resp.status).toBe(200);
    expect(await resp.json()).toMatchObject({ ok: true, dispatched: false });
    expect(calls.some((c) => c.method === "PATCH" && c.body.status === "approved_by_guest")).toBe(false);
    expect(calls.some((c) => c.method === "PATCH" && sbTable(c.url) === "editorial_packages" && c.body.guest_reviewed_at)).toBe(true);
  });

  it("marked lines are stored as time windows and make the submit a removal request", async () => {
    const { fn, calls } = reviewFetch(false);
    vi.stubGlobal("fetch", fn);
    const windows = [{ start_sec: 61, end_sec: 70, line: "[01:01] Guest: cut this" }];
    const resp = await worker.route(post("/voices/review/tokentokentokentoken",
      { approve: false, redactions: "", windows }), env());
    expect(resp.status).toBe(200);
    const stored = calls.find((c) => c.method === "PATCH" && c.body.guest_redaction_windows);
    expect(stored?.body.guest_redaction_windows).toEqual(windows);
    const inReview = calls.find((c) => c.method === "PATCH" && c.body.status === "in_review");
    expect(inReview?.body.guest_redactions[0].note).toContain("1 marked line");
  });

  it("gate 1's second Approve is a no-op: no second email, no new deadline", async () => {
    const { fn, calls } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.method === "GET" && t === "editorial_packages") return [{ id: PKG, status: "approved_by_patrick" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const e = env();
    const resp = await worker.route(
      post(`/voices/editorial-decision?token=${e.ADMIN_TOKEN}`, { package_id: PKG, decision: "approve" }), e);
    expect(resp.status).toBe(200);
    expect(await resp.json()).toMatchObject({ ok: true, already: "approved_by_patrick" });
    expect(calls.filter((c) => c.method === "PATCH").length).toBe(0);
    expect(calls.filter((c) => c.url.startsWith("https://api.resend.com/")).length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 6. /join needs a token
// ---------------------------------------------------------------------------

describe("/voices/join", () => {
  it("an interview id alone shows the form; the guest's manage token opens the studio", async () => {
    const { fn } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (t === "interviews") {
        if (c.url.includes("manage_token=eq.")) {
          return c.url.includes("manage_token=eq.goodtokengoodtokengood") ? [{ id: IV }] : [];
        }
        return [{ id: IV, status: "briefed", scheduled_at: new Date().toISOString(), application_id: "app", show: "age_of_ai" }];
      }
      if (t === "guest_applications") return [{ id: "app", name: "Guest", email: "g@x.y" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const bare = await worker.route(new Request(`https://api.nerranetwork.com/voices/join?interview=${IV}`), env());
    expect(bare.status).toBe(200);
    expect(await bare.text()).toContain("Enter the email address");
    const wrong = await worker.route(new Request(`https://api.nerranetwork.com/voices/join?interview=${IV}&t=wrongtokenwrongtoken`), env());
    expect(wrong.status).toBe(200);
    const good = await worker.route(new Request(`https://api.nerranetwork.com/voices/join?interview=${IV}&t=goodtokengoodtokengood`), env());
    expect(good.status).toBe(302);
    expect(good.headers.get("Location")).toContain(`interview=${IV}`);
  });

  it("a typed address inside the half hour gets the link by email, never a redirect", async () => {
    const { fn, calls } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (t === "guest_applications") return [{ id: "app", name: "Guest", email: "g@x.y", show: "age_of_ai" }];
      if (t === "interviews") return [{ id: IV, scheduled_at: new Date(Date.now() + 5 * 60000).toISOString(), show: "age_of_ai" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const fd = new FormData(); fd.set("email", "g@x.y");
    const resp = await worker.route(new Request("https://api.nerranetwork.com/voices/join", { method: "POST", body: fd }), env());
    expect(resp.status).toBe(200);
    expect(await resp.text()).toContain("emailed your personal");
    const mail = calls.find((c) => c.url.startsWith("https://api.resend.com/"));
    expect(mail?.body.to).toEqual(["g@x.y"]);
    expect(mail?.body.html).toContain(STUDIO_OPENS_BEFORE_TEXT);
  });
});

// ---------------------------------------------------------------------------
// 7. The copy says fifteen minutes
// ---------------------------------------------------------------------------

describe("the studio-opens copy", () => {
  it("reads the constant the studio actually opens on", () => {
    expect(STUDIO_OPENS_BEFORE_TEXT).toBe("fifteen minutes");
  });
});

// ---------------------------------------------------------------------------
// 8. Survey
// ---------------------------------------------------------------------------

describe("/voices/survey/:token", () => {
  it("cleans the answers", () => {
    expect(surveyAnswers({ rating: "4", change: " slower ", recommend: "YES" }))
      .toEqual({ survey_rating: 4, survey_change: "slower", survey_recommend: "yes" });
    expect(surveyAnswers({ rating: 9 })).toBeNull();
    expect(surveyAnswers({ recommend: "maybe" })).toMatchObject({ survey_recommend: "maybe", survey_rating: null });
  });

  it("an unknown token is a 404 page; answers are stored and a second submit updates", async () => {
    let answeredAt: string | null = null;
    const { fn, calls } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.method === "GET" && t === "editorial_packages") {
        return c.url.includes("survey_token=eq.known") ? [{ id: PKG, interview_id: IV, survey_answered_at: answeredAt }] : [];
      }
      if (c.method === "GET" && t === "interviews") return [{ id: IV, application_id: "app", show: "age_of_ai" }];
      if (c.method === "GET" && t === "guest_applications") return [{ id: "app", name: "Piper Martz", email: "p@x.y" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const unknown = await worker.route(new Request("https://api.nerranetwork.com/voices/survey/unknownunknownunknown"), env());
    expect(unknown.status).toBe(404);
    const page = await worker.route(new Request("https://api.nerranetwork.com/voices/survey/knownknownknownknown"), env());
    expect(page.status).toBe(200);
    const text = await page.text();
    expect(text).toContain("compare with a human host");
    expect(text).toContain("One thing you would change");
    expect(text).toContain("recommend it to a peer");
    expect(text).toContain("Piper");
    const first = await worker.route(post("/voices/survey/knownknownknownknown", { rating: 5, change: "nothing", recommend: "yes" }), env());
    expect(first.status).toBe(200);
    expect(await first.json()).toEqual({ ok: true, updated: false });
    const patch = calls.find((c) => c.method === "PATCH" && sbTable(c.url) === "editorial_packages");
    expect(patch?.body).toMatchObject({ survey_rating: 5, survey_change: "nothing", survey_recommend: "yes" });
    expect(patch?.body.survey_answered_at).toBeTruthy();
    answeredAt = "2026-10-21T00:00:00Z";
    const second = await worker.route(post("/voices/survey/knownknownknownknown", { rating: 4 }), env());
    expect(await second.json()).toEqual({ ok: true, updated: true });
    const again = calls.filter((c) => c.method === "PATCH" && sbTable(c.url) === "editorial_packages").pop();
    expect(again?.body.survey_answered_at).toBe(answeredAt);
    const empty = await worker.route(post("/voices/survey/knownknownknownknown", {}), env());
    expect(empty.status).toBe(400);
  });
});

// ---------------------------------------------------------------------------
// 9. Redaction windows + the edit's transcript
// ---------------------------------------------------------------------------

describe("redaction windows", () => {
  const text = "Speakers: Mira, Guest\n[00:05] Mira: Hello.\n[00:09] Guest: Hi there.\n\n[01:02:03] Mira: Late line.";

  it("parses [mm:ss] and [h:mm:ss] lines; the end is the next line's start or +15 s", () => {
    expect(transcriptLines(text)).toEqual([
      { start: 5, end: 9, line: "[00:05] Mira: Hello." },
      { start: 9, end: 3723, line: "[00:09] Guest: Hi there." },
      { start: 3723, end: 3738, line: "[01:02:03] Mira: Late line." },
    ]);
  });

  it("renders timed lines as clickable spans and untimed lines as text", () => {
    const out = reviewTranscriptHtml(text);
    expect(out).toContain('<span class="ln" data-start="5" data-end="9">[00:05] Mira: Hello.</span>');
    expect(out.split("\n")[0]).toBe("Speakers: Mira, Guest");
    expect(out).not.toContain("<script");
  });

  it("cleans and merges submitted windows", () => {
    expect(redactionWindows([{ start_sec: 10, end_sec: 5 }, { start: "a" }, { start_sec: 1, end_sec: 2, line: "x" }]))
      .toEqual([{ start_sec: 1, end_sec: 2, line: "x" }]);
    expect(redactionWindows("nope")).toEqual([]);
    const merged = mergeWindows([{ start_sec: 30, end_sec: 40, line: "b" }],
      [{ start_sec: 1, end_sec: 2, line: "a" }, { start_sec: 30, end_sec: 40, line: "b again" }]);
    expect(merged.map((w) => w.start_sec)).toEqual([1, 30]);
    expect(merged.length).toBe(2);
  });

  it("the review page shows the edit's transcript when the pipeline wrote one", async () => {
    const { fn } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.method === "GET" && t === "editorial_packages") {
        return [{ id: PKG, interview_id: IV, status: "approved_by_patrick", interview_run_id: RUN,
                  transcript_cleaned: "[00:01] Mira: room line", edit_transcript: "[00:01] Mira: edit line" }];
      }
      if (t === "interview_runs") return [{ recording_mixed_url: null, grok_session_log: {} }];
      if (t === "interviews") return [{ id: IV, application_id: "app", show: "age_of_ai" }];
      if (t === "guest_applications") return [{ id: "app", name: "Guest", email: "g@x.y" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const page = await worker.route(new Request("https://api.nerranetwork.com/voices/review/tokentokentokentoken"), env());
    const text = await page.text();
    expect(text).toContain("edit line");
    expect(text).not.toContain("room line");
    expect(text).toContain("transcript of the edit a listener will hear");
    expect(text).toContain("markedWindows()");
  });
});

// ---------------------------------------------------------------------------
// Rehearsal runs and the room's turn-taking counters (Oct 21 2026)
// ---------------------------------------------------------------------------

describe("rehearsal runs", () => {
  const counters = { barge_ins: 2, server_turns: 31, self_answers_blocked: 1,
                     closing_round_complete: true, closing_questions_asked: ["one bet", "a book"] };

  it("a rehearsal run stores the webhook and the counters, dispatches nothing, emails nobody", async () => {
    const { fn, calls } = fakeFetch((c) => {
      if (c.method === "GET" && sbTable(c.url) === "interview_runs") {
        return [{ grok_session_log: { call_mode: "webrtc" }, status: "in_progress", disconnect_reason: null, session_kind: "rehearsal" }];
      }
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post("/voices/interview-complete", {
      run_id: RUN, status: "completed", duration_sec: 600, voximplant_mira_record_url: "https://r/mira.mp3",
      voximplant_mix_record_url: "https://r/mix.mp3", grok_session_log: { x: 1 }, ...counters }), env());
    expect(resp.status).toBe(200);
    expect(await resp.json()).toEqual({ ok: true, rehearsal: true });
    const patch = calls.find((c) => c.method === "PATCH" && sbTable(c.url) === "interview_runs");
    expect(patch?.body.status).toBe("completed");
    expect(patch?.body.duration_sec).toBe(600);
    expect(patch?.body.recording_mira_url).toBe("https://r/mira.mp3");
    expect(patch?.body.grok_session_log).toMatchObject({ rehearsal: true, voximplant_mix_record_url: "https://r/mix.mp3", log: { x: 1 }, ...counters });
    expect(calls.some((c) => c.url.endsWith("/dispatches"))).toBe(false);
    expect(calls.some((c) => c.url.startsWith("https://api.resend.com/"))).toBe(false);
  });

  it("a real run keeps the counters in grok_session_log and still dispatches", async () => {
    const { fn, calls } = fakeFetch((c) => {
      if (c.method === "GET" && sbTable(c.url) === "interview_runs") {
        return [{ grok_session_log: {}, status: "in_progress", disconnect_reason: null, session_kind: "interview" }];
      }
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post("/voices/interview-complete",
      { run_id: RUN, status: "completed", duration_sec: 2400, ...counters, unexpected_field: "ignored" }), env());
    expect(resp.status).toBe(200);
    const patch = calls.find((c) => c.method === "PATCH" && sbTable(c.url) === "interview_runs");
    expect(patch?.body.grok_session_log).toMatchObject(counters);
    expect(calls.some((c) => c.url.endsWith("/dispatches") && c.body.event_type === "interview-complete")).toBe(true);
  });

  it("drops counters that are not numbers or booleans", () => {
    expect(roomCountersOf({ barge_ins: "3", server_turns: "many", closing_round_complete: "yes", closing_questions_asked: 4 }))
      .toEqual({ barge_ins: 3, closing_questions_asked: 4 });
    expect(roomCountersOf({})).toEqual({});
  });

  it("a fixture guest's leg event is an ordinary guest leg", async () => {
    const { fn, calls } = fakeFetch((c) => {
      if (c.method === "GET" && sbTable(c.url) === "interview_runs") {
        return [{ id: RUN, guest_joined_at: null, host_joined_at: null, host_left_at: null, grok_session_log: {} }];
      }
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post("/voices/leg-event", { run_id: RUN, role: "guest", event: "joined", fixture: true }), env());
    expect(resp.status).toBe(200);
    expect(((await resp.json()) as any).patched).toEqual(["guest_joined_at"]);
    expect(calls.some((c) => c.method === "PATCH" && c.body.guest_joined_at)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// The five-minute hello booking (Oct 21 2026, fork E's pre-call hello)
// ---------------------------------------------------------------------------

describe("hello bookings", () => {
  it("recognises the configured event type, else a slug or title with hello; never a closing", () => {
    expect(isHelloBooking({ CALCOM_EVENT_SLUG_HELLO: "pre-call" }, "pre-call", "", "Anything")).toBe(true);
    expect(isHelloBooking({ CALCOM_EVENT_SLUG_HELLO: "4242" }, "other", "4242", "")).toBe(true);
    expect(isHelloBooking({}, "hello-with-mira", "", "")).toBe(true);
    expect(isHelloBooking({}, "age-of-ai", "", "A five-minute hello before the show")).toBe(true);
    expect(isHelloBooking({}, "age-of-ai", "", "The Age of AI interview")).toBe(false);
    expect(HELLO_MINUTES).toBe(5);
  });

  it("books a hello as its own five-minute row pointing at the scheduled interview, no prep brief", async () => {
    const start = "2026-10-25T17:00:00Z";
    const { fn, calls } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.method === "GET" && t === "guest_applications") {
        return [{ id: "app1", name: "Stan Lewis", email: "stan@x.y", show: "age_of_ai", status: "approved" }];
      }
      if (c.method === "GET" && t === "interviews") {
        if (c.url.includes("session_kind=eq.interview")) return [{ id: IV }];
        if (c.url.includes("session_kind=eq.hello")) return [];
        return [{ manage_token: "managetokenmanagetoken" }];
      }
      if (c.method === "POST" && t === "interviews") return [{ id: IV2 }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const hook = { triggerEvent: "BOOKING_CREATED", payload: {
      uid: "cal-uid", startTime: start, title: "Hello with Mira",
      eventType: { slug: "hello-with-mira", title: "Hello with Mira" },
      attendees: [{ email: "stan@x.y", name: "Stan Lewis", timeZone: "America/Vancouver" }],
    } };
    const resp = await worker.route(post("/voices/cal-com-booked", hook), env());
    expect(resp.status).toBe(200);
    expect(await resp.json()).toMatchObject({ ok: true, hello: true, hello_for_interview_id: IV, interview_id: IV2 });
    const created = calls.find((c) => c.method === "POST" && sbTable(c.url) === "interviews");
    expect(created?.body).toMatchObject({ session_kind: "hello", duration_min: 5, hello_for_interview_id: IV,
                                          application_id: "app1", scheduled_at: start });
    const mail = calls.find((c) => c.url.startsWith("https://api.resend.com/"));
    expect(mail?.body.to).toEqual(["stan@x.y"]);
    expect(mail?.body.subject).toContain("five-minute hello");
    expect(mail?.body.html).toContain("studio link");
    expect(mail?.body.html).not.toContain("short brief");
    expect(calls.some((c) => c.url.endsWith("/dispatches") && c.body.event_type === "fire-tick")).toBe(true);
  });

  it("an ordinary booking is unchanged by the hello branch", async () => {
    const { fn, calls } = fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.method === "GET" && t === "guest_applications") {
        return [{ id: "app1", name: "Stan Lewis", email: "stan@x.y", show: "age_of_ai", status: "approved" }];
      }
      if (c.method === "GET" && t === "interviews") {
        return c.url.includes("manage_token") ? [{ manage_token: "managetokenmanagetoken" }] : [];
      }
      if (c.method === "POST" && t === "interviews") return [{ id: IV }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const hook = { triggerEvent: "BOOKING_CREATED", payload: {
      uid: "cal-uid", startTime: "2026-10-27T17:00:00Z", title: "The Age of AI interview",
      eventType: { slug: "age-of-ai" }, attendees: [{ email: "stan@x.y", name: "Stan Lewis" }],
    } };
    const resp = await worker.route(post("/voices/cal-com-booked", hook), env());
    expect(await resp.json()).toEqual({ ok: true, show: "age_of_ai", interview_id: IV });
    const created = calls.find((c) => c.method === "POST" && sbTable(c.url) === "interviews");
    expect(created?.body.session_kind).toBeUndefined();
    expect(created?.body.duration_min).toBe(45);
    const mail = calls.find((c) => c.url.startsWith("https://api.resend.com/"));
    expect(mail?.body.html).toContain("short brief");
  });
});

// ---------------------------------------------------------------------------
// Oct 24 2026 — the review process says what was chosen and what happened.
// Piper Martz's pronunciation note could only go as "removal requests", the
// page promised an email that never came, and Patrick's page said "Saved."
// ---------------------------------------------------------------------------

describe("review choices are explicit, shown back, recorded and confirmed", () => {
  const GTOK = "tokentokentokentoken";
  function pkgFetch(pkg: Record<string, unknown>, failDispatch = false) {
    let current: any = { id: PKG, interview_id: IV, guest_review_token: "tok", guest_redaction_windows: [], ...pkg };
    return fakeFetch((c) => {
      const t = sbTable(c.url);
      if (c.url.endsWith("/dispatches")) return failDispatch ? "fail" : null;
      if (c.method === "PATCH" && t === "editorial_packages") { current = { ...current, ...c.body }; return [current]; }
      if (c.method === "GET" && t === "editorial_packages") return [current];
      if (c.method === "GET" && t === "interviews") return [{ id: IV, application_id: "app", show: "nerra_voices" }];
      if (c.method === "GET" && t === "guest_applications") return [{ id: "app", name: "Piper Martz", email: "g@x.y" }];
      return [];
    });
  }
  const resendTo = (calls: Call[]) => calls.filter((c) => c.url.startsWith("https://api.resend.com/")).map((c) => ({ to: c.body.to[0], subject: c.body.subject, html: c.body.html }));

  it("marked lines always make it a change request; the old approve flag still works", () => {
    expect(guestDecision({ decision: "approve" }, 2)).toBe("changes");
    expect(guestDecision({ decision: "correction" }, 0)).toBe("correction");
    expect(guestDecision({ approve: true }, 0)).toBe("approve");
    expect(guestDecision({ approve: false }, 0)).toBe("changes");
  });

  it("the guest's page opens on where things stand", () => {
    const deadline = "2026-10-31T19:31:42Z";
    expect(guestReviewState({ status: "approved_by_patrick", guest_review_deadline: deadline }).code).toBe("waiting");
    expect(guestReviewState({ status: "approved_by_patrick", guest_review_deadline: deadline }).detail).toContain("October 31");
    const corr = guestReviewState({ status: "in_review", guest_reviewed_at: deadline,
      guest_redactions: [{ kind: "correction", approves: true, note: "Aampe is said amp", resolved: false, at: deadline }] });
    expect(corr.code).toBe("correction_pending");
    expect(corr.detail).toContain("Aampe is said amp");
    expect(corr.detail).toContain("will not need to review");
    const ch = guestReviewState({ status: "in_review", guest_redaction_windows: [{}, {}],
      guest_redactions: [{ kind: "removal", note: "2 marked line(s) carry time windows", lines: 2, resolved: false, at: deadline }] });
    expect(ch.code).toBe("changes_pending");
    expect(ch.detail).toContain("2 lines marked for cutting");
    expect(ch.detail).not.toContain("time windows");
    const made = guestReviewState({ status: "approved_by_patrick", guest_review_deadline: deadline,
      guest_redactions: [{ kind: "removal", note: "x", resolved: true, resolved_at: deadline }] });
    expect(made.code).toBe("changes_made");
    expect(guestReviewState({ status: "approved_by_guest", guest_reviewed_at: deadline }).code).toBe("approved");
    expect(openRequests({ guest_redactions: [{ resolved: true }, { resolved: false, note: "a" }] }).length).toBe(1);
  });

  it("a correction records the approval, waits for Patrick, and is confirmed to the guest and to Patrick", async () => {
    const { fn, calls } = pkgFetch({ status: "approved_by_patrick" });
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post(`/voices/review/${GTOK}`,
      { decision: "correction", correction: "Aampe is said amp, not am-pee" }), env());
    expect(resp.status).toBe(200);
    const data: any = await resp.json();
    expect(data).toMatchObject({ ok: true, decision: "correction", emailed: "g@x.y" });
    expect(data.state.code).toBe("correction_pending");
    expect(data.recorded).toContainEqual(["Your correction", "Aampe is said amp, not am-pee"]);
    const patch = calls.find((c) => c.method === "PATCH" && c.body.guest_redactions);
    expect(patch?.body.status).toBe("in_review");
    expect(patch?.body.guest_redactions.at(-1)).toMatchObject({ kind: "correction", approves: true, resolved: false });
    expect(calls.some((c) => c.url.endsWith("/dispatches"))).toBe(false);
    const mails = resendTo(calls);
    expect(mails.find((m) => m.to === "g@x.y")?.subject).toContain("Got it");
    expect(mails.find((m) => m.to === "g@x.y")?.html).toContain("Aampe is said amp");
    // Oct 24 2026: every Mira email signs off with the two kits.
    expect(mails.find((m) => m.to === "g@x.y")?.html).toContain("https://nerranetwork.com/press.html");
    expect(mails.find((m) => m.to === "g@x.y")?.html).toContain("https://nerranetwork.com/sponsor.html");
    expect(mails.some((m) => m.to !== "g@x.y" && /approved, with one correction/.test(m.subject))).toBe(true);
  });

  it("an approval is answered with what was recorded and a copy by email", async () => {
    const { fn, calls } = pkgFetch({ status: "approved_by_patrick" });
    vi.stubGlobal("fetch", fn);
    const data: any = await (await worker.route(post(`/voices/review/${GTOK}`,
      { decision: "approve", followup: "return_6", materials: "my site" }), env())).json();
    expect(data).toMatchObject({ ok: true, decision: "approve", dispatched: true, emailed: "g@x.y" });
    expect(data.state.code).toBe("approved");
    expect(data.recorded[0]).toEqual(["Your choice", "Approve it as it is"]);
    expect(resendTo(calls).some((m) => /approved the episode/.test(m.subject))).toBe(true);
  });

  it("a choice that cannot be acted on is refused before anything is written", async () => {
    const { fn, calls } = pkgFetch({ status: "approved_by_patrick" });
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post(`/voices/review/${GTOK}`,
      { decision: "correction", correction: "  ", materials: "bio" }), env());
    expect(resp.status).toBe(400);
    expect(calls.filter((c) => c.method === "PATCH" || c.method === "POST").length).toBe(0);
  });

  it("a second submit is shown the choice already recorded, and writes nothing", async () => {
    const { fn, calls } = pkgFetch({ status: "approved_by_guest", guest_reviewed_at: "2026-10-24T19:00:00Z" });
    vi.stubGlobal("fetch", fn);
    const resp = await worker.route(post(`/voices/review/${GTOK}`, { decision: "approve" }), env());
    expect(resp.status).toBe(409);
    expect(await resp.json()).toMatchObject({ already: true, state: { code: "approved" } });
    expect(calls.filter((c) => c.method === "PATCH").length).toBe(0);
  });

  it("a returning guest's page shows what they chose, not a bare thank-you", async () => {
    const { fn } = pkgFetch({ status: "approved_by_guest", guest_reviewed_at: "2026-10-24T19:00:00Z", guest_followup: "return_12" });
    vi.stubGlobal("fetch", fn);
    const page = await (await worker.route(new Request(`https://api.nerranetwork.com/voices/review/${GTOK}`), env())).text();
    expect(page).toContain("You approved this episode");
    expect(page).toContain("Come back in about a year");
  });

  it("gate 1's approve after a change request marks it done, says so to the guest, and tells Patrick who was emailed", async () => {
    const { fn, calls } = pkgFetch({ status: "in_review", patrick_reviewed_at: "2026-10-17T00:00:00Z",
      guest_redactions: [{ kind: "removal", note: "Cut the bit about my brother", lines: 0, resolved: false, at: "2026-10-20T00:00:00Z" }] });
    vi.stubGlobal("fetch", fn);
    const e = env();
    const data: any = await (await worker.route(post(`/voices/editorial-decision?token=${e.ADMIN_TOKEN}`,
      { package_id: PKG, decision: "approve" }), e)).json();
    expect(data).toMatchObject({ ok: true, status: "approved_by_patrick", emailed_to: "g@x.y", resolved: 1 });
    expect(data.message).toContain("g@x.y");
    const patch = calls.find((c) => c.method === "PATCH" && sbTable(c.url) === "editorial_packages");
    expect(patch?.body.guest_redactions[0]).toMatchObject({ resolved: true, resolved_by: "patrick" });
    const mail = resendTo(calls).find((m) => m.to === "g@x.y");
    expect(mail?.subject).toContain("Your changes are made");
    expect(mail?.html).toContain("Cut the bit about my brother");
  });

  it("'Correction made' lets the guest's approval stand, dispatches production and tells the guest", async () => {
    const { fn, calls } = pkgFetch({ status: "in_review", guest_review_deadline: "2026-10-31T00:00:00Z",
      guest_redactions: [{ kind: "correction", approves: true, note: "Aampe is said amp", resolved: false, at: "2026-10-20T01:04:28Z" }] });
    vi.stubGlobal("fetch", fn);
    const e = env();
    const data: any = await (await worker.route(post(`/voices/editorial-decision?token=${e.ADMIN_TOKEN}`,
      { package_id: PKG, decision: "correction_made" }), e)).json();
    expect(data).toMatchObject({ ok: true, status: "approved_by_guest", dispatched: true, emailed_to: "g@x.y" });
    expect(calls.some((c) => c.url.endsWith("/dispatches"))).toBe(true);
    expect(calls.some((c) => c.method === "PATCH" && c.body.status === "approved_by_guest")).toBe(true);
    expect(resendTo(calls).find((m) => m.to === "g@x.y")?.subject).toContain("Done: your correction");
  });

  it("'Correction made' with no correction open changes nothing", async () => {
    const { fn, calls } = pkgFetch({ status: "approved_by_patrick" });
    vi.stubGlobal("fetch", fn);
    const e = env();
    const resp = await worker.route(post(`/voices/editorial-decision?token=${e.ADMIN_TOKEN}`,
      { package_id: PKG, decision: "correction_made" }), e);
    expect(resp.status).toBe(409);
    expect(calls.filter((c) => c.method === "PATCH").length).toBe(0);
  });

  it("Patrick's page shows the state box and the buttons for it", async () => {
    const e = env();
    let r = pkgFetch({ status: "in_review", guest_redactions: [{ kind: "correction", approves: true, note: "Aampe is said amp", resolved: false, at: "2026-10-20T01:04:28Z" }] });
    vi.stubGlobal("fetch", r.fn);
    let html = await (await worker.route(new Request(`https://api.nerranetwork.com/voices/admin/review/${PKG}?token=${e.ADMIN_TOKEN}`), e)).text();
    expect(html).toContain("Correction made: their approval stands");
    expect(html).not.toContain("Approve: email the guest");
    expect(html).toContain('data-state="correction_pending"');
    r = pkgFetch({ status: "approved_by_patrick", patrick_reviewed_at: "2026-10-24T19:31:42Z", guest_review_deadline: "2026-10-31T19:31:42Z" });
    vi.stubGlobal("fetch", r.fn);
    html = await (await worker.route(new Request(`https://api.nerranetwork.com/voices/admin/review/${PKG}?token=${e.ADMIN_TOKEN}`), e)).text();
    expect(html).not.toContain("b_approve");
    expect(html).toContain("Mira emailed the review link to Piper Martz (g@x.y)");
    expect(html).not.toContain("'Saved.'");
  });

  it("Patrick's page opens on the state and offers only the buttons that make sense", () => {
    const corr = operatorReviewState({ status: "in_review", guest_redactions: [{ kind: "correction", approves: true, note: "n", resolved: false, at: "2026-10-20T01:04:28Z" }] }, "Piper", "p@x.y");
    expect(corr.code).toBe("correction_pending");
    const sent = operatorReviewState({ status: "approved_by_patrick", patrick_reviewed_at: "2026-10-24T19:31:42Z", guest_review_deadline: "2026-10-31T19:31:42Z" }, "Jason", "j@x.y");
    expect(sent.code).toBe("with_guest");
    expect(sent.headline).toContain("j@x.y");
    expect(sent.detail).toContain("October 31");
    expect(guestReceipt({ guest_reviewed_at: "2026-10-24T19:00:00Z", guest_redactions: [{ note: "fix", kind: "correction" }] }, "correction"))
      .toContainEqual(["Your correction", "fix"]);
  });
});
