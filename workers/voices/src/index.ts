/**
 * Nerra Voices (The Age of AI) API Worker.
 *
 * Routes (all under /voices/ — see wrangler.toml):
 *   POST /voices/apply                public guest application form
 *   POST /voices/interview-complete   Voximplant scenario hangup webhook
 *   POST /voices/cal-com-booked       Cal.com booking webhook
 *   GET  /voices/review/:token        guest transcript review page (gate 2)
 *   POST /voices/review/:token        guest approve / redact submit
 *   GET  /voices/admin/triage         Patrick's application triage UI
 *   POST /voices/triage-decision      approve/decline an application
 *   GET  /voices/admin/review/:id     Patrick's editorial review UI (gate 1)
 *   POST /voices/editorial-decision   approve/kill an editorial package
 *   GET  /voices/episode-lookup       Mira tool: nerra_episode_lookup
 *   GET  /voices/guest-brief          Mira tool: guest_brief_lookup
 *   POST /voices/fact-check           Mira tool: fact_check_claim (proxy note)
 *   scheduled (daily)                 gate-2 day-4 reminder + day-7 auto-approve
 *
 * Design: thin handlers — update Supabase (service key), send the odd
 * email, and fire repository_dispatch events that GitHub Actions pipelines
 * consume. No business logic lives here that the pipelines also implement.
 */

export interface Env {
  SUPABASE_URL: string;
  SUPABASE_SERVICE_KEY: string;
  GITHUB_DISPATCH_TOKEN: string;
  ADMIN_TOKEN: string;
  RESEND_API_KEY: string;
  VOICES_FROM_EMAIL: string;
  CALCOM_BOOKING_URL: string;
  SLACK_WEBHOOK?: string;
}

const REPO = "Planetterrian/nerranetwork";
const SEARCH_INDEX_URL = "https://nerranetwork.com/api/search_index.json";

// ---------------------------------------------------------------------------
// Small clients
// ---------------------------------------------------------------------------

async function sb(env: Env, method: string, path: string, body?: unknown,
                  prefer = ""): Promise<any> {
  const headers: Record<string, string> = {
    apikey: env.SUPABASE_SERVICE_KEY,
    Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
    "Content-Type": "application/json",
  };
  if (prefer) headers.Prefer = prefer;
  const resp = await fetch(`${env.SUPABASE_URL}/rest/v1/${path}`, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`supabase ${method} ${path}: ${resp.status} ${await resp.text()}`);
  const text = await resp.text();
  return text ? JSON.parse(text) : null;
}

async function dispatch(env: Env, eventType: string, payload: Record<string, unknown>) {
  const resp = await fetch(`https://api.github.com/repos/${REPO}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "nerra-voices-worker",
    },
    body: JSON.stringify({ event_type: eventType, client_payload: payload }),
  });
  if (resp.status !== 204) throw new Error(`repository_dispatch ${eventType}: ${resp.status}`);
}

async function email(env: Env, to: string, subject: string, html: string) {
  const resp = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from: env.VOICES_FROM_EMAIL, to: [to], subject, html }),
  });
  if (!resp.ok) throw new Error(`resend: ${resp.status} ${await resp.text()}`);
}

async function slack(env: Env, text: string) {
  if (!env.SLACK_WEBHOOK) return;
  try {
    await fetch(env.SLACK_WEBHOOK, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: `:studio_microphone: ${text}` }),
    });
  } catch { /* notifications are best-effort */ }
}

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
const html = (body: string, status = 200) =>
  new Response(body, { status, headers: { "Content-Type": "text/html;charset=utf-8" } });

function requireAdmin(req: Request, env: Env): Response | null {
  const auth = req.headers.get("Authorization") ?? "";
  const url = new URL(req.url);
  const token = auth.replace(/^Bearer\s+/i, "") || url.searchParams.get("token") || "";
  if (!env.ADMIN_TOKEN || token !== env.ADMIN_TOKEN) {
    return json({ error: "unauthorized" }, 401);
  }
  return null;
}

const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

async function handleApply(req: Request, env: Env): Promise<Response> {
  const form = await req.json<any>().catch(() => null);
  if (!form?.name || !form?.email) return json({ error: "name and email are required" }, 400);
  const row = await sb(env, "POST", "guest_applications", {
    name: String(form.name).slice(0, 200),
    email: String(form.email).slice(0, 200),
    phone: form.phone ? String(form.phone).slice(0, 40) : null,
    organization: form.organization ? String(form.organization).slice(0, 200) : null,
    title: form.title ? String(form.title).slice(0, 200) : null,
    bio: form.bio ? String(form.bio).slice(0, 4000) : null,
    topics: Array.isArray(form.topics) ? form.topics.slice(0, 10) : null,
    links: form.links ?? null,
    preferred_window: form.preferred_window ?? null,
    referrer: form.referrer ?? null,
  }, "return=representation");
  await slack(env, `Age of AI: new guest application — *${form.name}* (${form.organization ?? "independent"}). Triage: https://api.nerranetwork.com/voices/admin/triage`);
  return json({ ok: true, id: row[0]?.id });
}

async function handleInterviewComplete(req: Request, env: Env): Promise<Response> {
  const payload = await req.json<any>().catch(() => null);
  if (!payload?.run_id) return json({ error: "run_id required" }, 400);
  const patch: Record<string, unknown> = {
    status: payload.status === "failed" ? "failed" : "completed",
    disconnect_reason: payload.disconnect_reason ?? payload.reason ?? null,
    duration_sec: payload.duration_sec ?? null,
    grok_session_log: {
      ...(payload.grok_session_log ? { log: payload.grok_session_log } : {}),
      voximplant_record_url: payload.voximplant_record_url ?? null,
    },
  };
  await sb(env, "PATCH", `interview_runs?id=eq.${payload.run_id}`, patch);
  await dispatch(env, "interview-complete", { run_id: payload.run_id });
  return json({ ok: true });
}

async function handleCalComBooked(req: Request, env: Env): Promise<Response> {
  const hook = await req.json<any>().catch(() => null);
  const p = hook?.payload ?? hook ?? {};
  const attendee = (p.attendees ?? [])[0] ?? {};
  const emailAddr = (attendee.email ?? p.email ?? "").toLowerCase();
  const startTime = p.startTime ?? p.start_time ?? null;
  if (!emailAddr || !startTime) return json({ error: "email + startTime required" }, 400);

  const apps = await sb(env, "GET",
    `guest_applications?email=eq.${encodeURIComponent(emailAddr)}&status=eq.approved&order=created_at.desc&limit=1`);
  if (!apps?.length) return json({ error: "no approved application for that email" }, 404);

  const existing = await sb(env, "GET",
    `interviews?application_id=eq.${apps[0].id}&status=in.(scheduled,briefed)&limit=1`);
  if (existing?.length) {
    await sb(env, "PATCH", `interviews?id=eq.${existing[0].id}`,
      { scheduled_at: startTime, status: "scheduled", reminder_sent_at: null });
  } else {
    await sb(env, "POST", "interviews",
      { application_id: apps[0].id, scheduled_at: startTime, status: "scheduled" });
  }
  await email(env, emailAddr, "Your Age of AI interview is booked",
    `<p>Hi ${esc(apps[0].name)},</p>
     <p>You're booked. Mira — our AI host — will call you at the number you
     provided at the scheduled time. About a day before, you'll receive a
     short prep brief with the themes she plans to explore.</p>
     <p>Two things to know: the call is recorded for the podcast, and nothing
     publishes until you've reviewed and approved the transcript.</p>
     <p>— The Age of AI, Nerra Network</p>`);
  await slack(env, `Age of AI: ${apps[0].name} booked ${startTime}`);
  return json({ ok: true });
}

async function handleTriageDecision(req: Request, env: Env): Promise<Response> {
  const denied = requireAdmin(req, env);
  if (denied) return denied;
  const body = await req.json<any>().catch(() => null);
  if (!body?.application_id || !["approved", "declined"].includes(body.decision)) {
    return json({ error: "application_id + decision(approved|declined) required" }, 400);
  }
  const rows = await sb(env, "PATCH",
    `guest_applications?id=eq.${body.application_id}`,
    { status: body.decision, notes: body.notes ?? null }, "return=representation");
  const app = rows?.[0];
  if (app && body.decision === "approved") {
    await email(env, app.email, "You're invited — book your Age of AI interview",
      `<p>Hi ${esc(app.name)},</p>
       <p>We'd love to have you on The Age of AI. Pick a time that works and
       Mira — our AI host — will call you: </p>
       <p><a href="${esc(env.CALCOM_BOOKING_URL)}">${esc(env.CALCOM_BOOKING_URL)}</a></p>
       <p>The call runs about forty-five minutes. It's recorded, and nothing
       publishes until you've approved the transcript.</p>
       <p>— The Age of AI, Nerra Network</p>`);
  }
  return json({ ok: true });
}

async function handleEditorialDecision(req: Request, env: Env): Promise<Response> {
  const denied = requireAdmin(req, env);
  if (denied) return denied;
  const body = await req.json<any>().catch(() => null);
  if (!body?.package_id || !["approve", "kill"].includes(body.decision)) {
    return json({ error: "package_id + decision(approve|kill) required" }, 400);
  }
  const status = body.decision === "approve" ? "approved_by_patrick" : "killed";
  const rows = await sb(env, "PATCH", `editorial_packages?id=eq.${body.package_id}`, {
    status,
    patrick_reviewed_at: new Date().toISOString(),
    patrick_notes: body.notes ?? null,
    ...(body.decision === "approve"
      ? { guest_review_deadline: new Date(Date.now() + 7 * 864e5).toISOString() }
      : {}),
  }, "return=representation");
  const pkg = rows?.[0];
  if (!pkg) return json({ error: "package not found" }, 404);

  if (body.decision === "approve") {
    // Gate 1 cleared → open gate 2: email the guest their review link.
    const interview = (await sb(env, "GET", `interviews?id=eq.${pkg.interview_id}`))[0];
    const app = (await sb(env, "GET", `guest_applications?id=eq.${interview.application_id}`))[0];
    await sb(env, "PATCH", `interviews?id=eq.${interview.id}`, { status: "guest_review" });
    const link = `https://api.nerranetwork.com/voices/review/${pkg.guest_review_token}`;
    await email(env, app.email, "Your Age of AI transcript is ready for review",
      `<p>Hi ${esc(app.name)},</p>
       <p>Your conversation with Mira is edited and ready. Please review the
       transcript — approve it as-is, or mark anything you'd like removed:</p>
       <p><a href="${esc(link)}">${esc(link)}</a></p>
       <p>If we don't hear from you within seven days we'll take that as
       approval (we'll remind you at day four). You can always request
       changes post-publish as well.</p>
       <p>— The Age of AI, Nerra Network</p>`);
    await slack(env, `Age of AI: Patrick approved package ${pkg.id} — guest review email sent`);
  } else {
    await sb(env, "PATCH", `interviews?id=eq.${pkg.interview_id}`, { status: "failed" });
    await slack(env, `Age of AI: Patrick KILLED package ${pkg.id}`);
  }
  return json({ ok: true });
}

// -- Gate 2: guest transcript review ----------------------------------------

async function pkgByToken(env: Env, token: string): Promise<any | null> {
  const rows = await sb(env, "GET",
    `editorial_packages?guest_review_token=eq.${encodeURIComponent(token)}&limit=1`);
  return rows?.[0] ?? null;
}

async function handleGuestReviewPage(env: Env, token: string): Promise<Response> {
  const pkg = await pkgByToken(env, token);
  if (!pkg) return html("<h1>Link not found</h1>", 404);
  if (["approved_by_guest", "published"].includes(pkg.status)) {
    return html("<h1>Already approved — thank you!</h1>");
  }
  return html(`<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Review your Age of AI transcript</title>
<style>body{font:16px/1.6 system-ui;max-width:760px;margin:2rem auto;padding:0 1rem;color:#1a202c}
pre{white-space:pre-wrap;background:#f7fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;max-height:60vh;overflow:auto}
textarea{width:100%;min-height:90px}button{background:#7C3AED;color:#fff;border:0;border-radius:8px;padding:.7rem 1.4rem;font-size:1rem;cursor:pointer;margin-right:.6rem}
.secondary{background:#4a5568}</style>
<h1>Your Age of AI transcript</h1>
<p>Everything below is what would publish. Approve it as-is, or tell us what
to remove — quote the passage(s) and we'll cut them from both the audio and
the transcript before anything goes out.</p>
<pre>${esc(pkg.transcript_cleaned ?? pkg.transcript_raw ?? "")}</pre>
<h3>Request removals (optional)</h3>
<textarea id="redactions" placeholder="Quote any passage you'd like removed, one per line, with a word on why if you like."></textarea>
<p>
<button onclick="submitReview(true)">Approve for publication</button>
<button class="secondary" onclick="submitReview(false)">Submit removal requests</button>
</p>
<p id="status"></p>
<script>
async function submitReview(approve){
  const resp = await fetch(location.pathname, {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({approve, redactions: document.getElementById('redactions').value})});
  document.getElementById('status').textContent = resp.ok
    ? (approve ? 'Approved — thank you! Your episode is on its way.' : 'Received — we will apply the removals and confirm by email.')
    : 'Something went wrong — please reply to our email instead.';
}
</script>`);
}

async function handleGuestReviewSubmit(req: Request, env: Env, token: string): Promise<Response> {
  const pkg = await pkgByToken(env, token);
  if (!pkg) return json({ error: "not found" }, 404);
  const body = await req.json<any>().catch(() => ({}));
  const now = new Date().toISOString();
  if (body.approve) {
    await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`,
      { status: "approved_by_guest", guest_reviewed_at: now });
    await sb(env, "PATCH", `interviews?id=eq.${pkg.interview_id}`, { status: "approved" });
    await dispatch(env, "interview-approved-by-guest", { interview_id: pkg.interview_id });
    await slack(env, `Age of AI: guest APPROVED package ${pkg.id} — production dispatched`);
  } else {
    const requests = String(body.redactions ?? "").trim();
    await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`, {
      guest_reviewed_at: now,
      guest_redactions: [{ note: requests, resolved: false }],
      status: "in_review",
    });
    await slack(env, `Age of AI: guest requested removals on package ${pkg.id} — needs Patrick:\n${requests.slice(0, 500)}`);
  }
  return json({ ok: true });
}

// -- Admin UIs (lean, token-gated) ------------------------------------------

async function handleAdminTriage(req: Request, env: Env): Promise<Response> {
  const denied = requireAdmin(req, env);
  if (denied) return denied;
  const apps = await sb(env, "GET",
    "guest_applications?status=eq.pending&order=created_at.asc&limit=50");
  const rows = (apps ?? []).map((a: any) => `
    <li><b>${esc(a.name)}</b> — ${esc(a.title ?? "")} ${esc(a.organization ?? "")}
      <br><small>${esc((a.topics ?? []).join(", "))}</small>
      <br>${esc(a.bio ?? "").slice(0, 500)}
      <br><button onclick="decide('${a.id}','approved')">Approve</button>
      <button onclick="decide('${a.id}','declined')">Decline</button></li>`).join("");
  return html(`<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">
<title>Age of AI — triage</title>
<style>body{font:15px/1.5 system-ui;max-width:800px;margin:2rem auto;padding:0 1rem}li{margin-bottom:1.4rem}</style>
<h1>Pending applications (${(apps ?? []).length})</h1><ul>${rows || "<i>none</i>"}</ul>
<script>
const token = new URL(location).searchParams.get('token');
async function decide(id, decision){
  await fetch('/voices/triage-decision?token='+token, {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({application_id:id, decision})});
  location.reload();
}
</script>`);
}

async function handleAdminReview(req: Request, env: Env, id: string): Promise<Response> {
  const denied = requireAdmin(req, env);
  if (denied) return denied;
  const rows = await sb(env, "GET", `editorial_packages?id=eq.${id}&limit=1`);
  const pkg = rows?.[0];
  if (!pkg) return html("<h1>Package not found</h1>", 404);
  const run = (await sb(env, "GET", `interview_runs?id=eq.${pkg.interview_run_id}`))[0] ?? {};
  return html(`<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">
<title>Age of AI — editorial review</title>
<style>body{font:15px/1.6 system-ui;max-width:860px;margin:2rem auto;padding:0 1rem}
pre{white-space:pre-wrap;background:#f7fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;max-height:50vh;overflow:auto}
textarea{width:100%;min-height:80px}button{padding:.6rem 1.2rem;margin-right:.6rem}</style>
<h1>Editorial review — gate 1</h1>
<p>Status: <b>${esc(pkg.status)}</b>${pkg.audio_quality_flag ? ` · ⚠️ ${esc(pkg.audio_quality_flag)}` : ""}</p>
${run.recording_mixed_url ? `<audio controls src="${esc(run.recording_mixed_url)}" style="width:100%"></audio>` : ""}
<h3>Episode notes</h3><pre>${esc(pkg.episode_notes ?? "")}</pre>
<h3>Cleaned transcript</h3><pre>${esc(pkg.transcript_cleaned ?? "")}</pre>
<h3>Newsletter draft</h3><pre>${esc(pkg.newsletter_draft ?? "")}</pre>
<h3>Decision</h3>
<textarea id="notes" placeholder="Editorial notes (kept on the package)"></textarea>
<p><button onclick="decide('approve')">Approve → guest review</button>
<button onclick="decide('kill')">Kill episode</button></p>
<p id="status"></p>
<script>
const token = new URL(location).searchParams.get('token');
async function decide(decision){
  const resp = await fetch('/voices/editorial-decision?token='+token, {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({package_id:'${pkg.id}', decision, notes: document.getElementById('notes').value})});
  document.getElementById('status').textContent = resp.ok ? 'Saved.' : 'Failed — check the token.';
}
</script>`);
}

// -- Mira tool endpoints -----------------------------------------------------

async function handleEpisodeLookup(req: Request, env: Env): Promise<Response> {
  const topic = (new URL(req.url).searchParams.get("topic") ?? "").toLowerCase();
  if (!topic) return json({ episodes: [] });
  try {
    const idx: any = await (await fetch(SEARCH_INDEX_URL, { cf: { cacheTtl: 3600 } } as any)).json();
    const entries: any[] = Array.isArray(idx) ? idx : idx.entries ?? idx.episodes ?? [];
    const words = topic.split(/\s+/).filter(Boolean);
    const hits = entries
      .map((e: any) => {
        const hay = `${e.title ?? ""} ${e.summary ?? e.description ?? ""}`.toLowerCase();
        return { e, score: words.filter((w) => hay.includes(w)).length };
      })
      .filter((h) => h.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 3)
      .map((h) => ({
        show: h.e.show ?? h.e.show_name ?? "",
        title: h.e.title ?? "",
        date: h.e.date ?? "",
        summary: String(h.e.summary ?? h.e.description ?? "").slice(0, 300),
      }));
    return json({ episodes: hits });
  } catch {
    return json({ episodes: [], note: "search index unavailable" });
  }
}

async function handleGuestBrief(req: Request, env: Env): Promise<Response> {
  const url = new URL(req.url);
  const runId = url.searchParams.get("run_id") ?? "";
  const section = url.searchParams.get("section") ?? "bio";
  if (!runId) return json({ error: "run_id required" }, 400);
  const run = (await sb(env, "GET", `interview_runs?id=eq.${runId}`))?.[0];
  if (!run) return json({ error: "run not found" }, 404);
  const brief = (await sb(env, "GET", `interview_briefs?interview_id=eq.${run.interview_id}`))?.[0];
  if (!brief) return json({ error: "no brief" }, 404);
  const map: Record<string, unknown> = {
    bio: brief.bio_research,
    topics: brief.likely_questions,
    past_work: brief.past_work_summary,
    predictions: brief.episode_thesis_draft,
  };
  return json({ section, content: map[section] ?? brief.bio_research });
}

async function handleFactCheck(req: Request, env: Env): Promise<Response> {
  // The Grok Voice agent has native web search; this named endpoint exists
  // so fact checks are deliberate and auditable in the session log (spec
  // §3.2). We simply echo an instruction telling the agent to use its own
  // search grounding for the claim — keeping the audit trail without
  // adding a second search stack in the Worker.
  const body = await req.json<any>().catch(() => ({}));
  return json({
    claim: body.claim ?? "",
    instruction:
      "Verify this claim with your web search grounding now, state what you "
      + "found in one sentence with the source name, and say plainly if it "
      + "cannot be verified.",
  });
}

// -- Scheduled: gate-2 housekeeping ------------------------------------------

async function gate2Housekeeping(env: Env) {
  const now = Date.now();
  const pkgs = await sb(env, "GET",
    "editorial_packages?status=eq.approved_by_patrick&guest_review_deadline=not.is.null");
  for (const pkg of pkgs ?? []) {
    const deadline = Date.parse(pkg.guest_review_deadline);
    const interview = (await sb(env, "GET", `interviews?id=eq.${pkg.interview_id}`))[0];
    const app = (await sb(env, "GET", `guest_applications?id=eq.${interview.application_id}`))[0];
    if (now >= deadline) {
      // Day 7: auto-approve (spec §7) — guest can still request takedown.
      await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`,
        { status: "approved_by_guest", guest_reviewed_at: new Date().toISOString() });
      await sb(env, "PATCH", `interviews?id=eq.${interview.id}`, { status: "approved" });
      await dispatch(env, "interview-approved-by-guest", { interview_id: interview.id });
      await slack(env, `Age of AI: package ${pkg.id} AUTO-APPROVED (7-day window elapsed)`);
    } else if (deadline - now < 3 * 864e5 && deadline - now > 2 * 864e5) {
      // Day 4 (±cron granularity): one reminder.
      const link = `https://api.nerranetwork.com/voices/review/${pkg.guest_review_token}`;
      await email(env, app.email, "Reminder: your Age of AI transcript awaits",
        `<p>Hi ${esc(app.name)},</p>
         <p>A gentle nudge — your transcript is waiting for review:</p>
         <p><a href="${esc(link)}">${esc(link)}</a></p>
         <p>If we don't hear from you in the next three days we'll take that
         as approval.</p><p>— The Age of AI, Nerra Network</p>`);
    }
  }
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

// CORS: the apply form on nerranetwork.com posts cross-origin to
// api.nerranetwork.com — browsers preflight JSON POSTs, and without these
// headers every form submission fails in the browser (curl worked, which
// is how this shipped; caught on the first real form submit, July 2026).
const ALLOWED_ORIGINS = new Set([
  "https://nerranetwork.com",
  "https://www.nerranetwork.com",
]);

function corsHeaders(origin: string): Record<string, string> {
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function withCors(req: Request, res: Response): Response {
  const origin = req.headers.get("Origin");
  if (!origin || !ALLOWED_ORIGINS.has(origin)) return res;
  const out = new Response(res.body, res);
  for (const [k, v] of Object.entries(corsHeaders(origin))) out.headers.set(k, v);
  return out;
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    if (req.method === "OPTIONS") {
      const origin = req.headers.get("Origin");
      return new Response(null, {
        status: 204,
        headers: origin && ALLOWED_ORIGINS.has(origin) ? corsHeaders(origin) : {},
      });
    }
    return withCors(req, await this.route(req, env));
  },

  async route(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    const path = url.pathname.replace(/\/+$/, "");
    try {
      if (req.method === "POST" && path === "/voices/apply") return handleApply(req, env);
      if (req.method === "POST" && path === "/voices/interview-complete") return handleInterviewComplete(req, env);
      if (req.method === "POST" && path === "/voices/cal-com-booked") return handleCalComBooked(req, env);
      if (req.method === "POST" && path === "/voices/triage-decision") return handleTriageDecision(req, env);
      if (req.method === "POST" && path === "/voices/editorial-decision") return handleEditorialDecision(req, env);
      const review = path.match(/^\/voices\/review\/([A-Za-z0-9_-]{16,})$/);
      if (review) {
        return req.method === "POST"
          ? handleGuestReviewSubmit(req, env, review[1])
          : handleGuestReviewPage(env, review[1]);
      }
      if (req.method === "GET" && path === "/voices/admin/triage") return handleAdminTriage(req, env);
      const adminReview = path.match(/^\/voices\/admin\/review\/([0-9a-f-]{36})$/);
      if (adminReview && req.method === "GET") return handleAdminReview(req, env, adminReview[1]);
      if (req.method === "GET" && path === "/voices/episode-lookup") return handleEpisodeLookup(req, env);
      if (req.method === "GET" && path === "/voices/guest-brief") return handleGuestBrief(req, env);
      if (req.method === "POST" && path === "/voices/fact-check") return handleFactCheck(req, env);
      return json({ error: "not found" }, 404);
    } catch (err: any) {
      console.error("voices worker error:", err?.message ?? err);
      return json({ error: "internal error" }, 500);
    }
  },

  async scheduled(_event: ScheduledEvent, env: Env): Promise<void> {
    await gate2Housekeeping(env);
  },
};
