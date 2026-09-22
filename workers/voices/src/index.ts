/**
 * Voices API Worker — The Age of AI + Nerra Voices (the two Mira-hosted
 * live interview shows share this Worker, the Supabase tables and the
 * pipelines; rows carry a `show` slug, see SHOWS below).
 *
 * Routes (all under /voices/ — see wrangler.toml):
 *   POST /voices/apply                public guest application form (both shows)
 *   POST /voices/interview-complete   Voximplant scenario hangup webhook
 *   POST /voices/cal-com-booked       Cal.com booking webhook (show from event type)
 *   GET  /voices/review/:token        guest transcript review page (gate 2)
 *   POST /voices/review/:token        guest approve / redact submit
 *   GET  /voices/admin/triage         Patrick's application triage UI (grouped by show)
 *   POST /voices/triage-decision      approve/decline an application
 *   POST /voices/triage-reassign      move an application to the other show
 *   GET  /voices/admin/review/:id     Patrick's editorial review UI (gate 1)
 *   POST /voices/editorial-decision   approve/kill an editorial package
 *   POST /voices/lesson-decision      promote/drop a proposed Mira lesson
 *   POST /voices/narration-take       scenario reports a finished Mira read
 *   GET  /voices/episode-lookup       Mira tool: nerra_episode_lookup
 *   GET  /voices/guest-brief          Mira tool: guest_brief_lookup
 *   POST /voices/fact-check           Mira tool: fact_check_claim (proxy note)
 *   GET  /voices/studio-state         studio page poll (run readiness, presence)
 *   POST /voices/studio-auth          Voximplant one-time-key login (guest | host)
 *   POST /voices/leg-event            scenario: per-leg joined/left (Phase 2)
 *   POST /voices/upload-chunk         studio: local MediaRecorder chunk → R2 (Phase 2)
 *   POST /voices/upload-done          studio: local recording manifest → R2 + run row
 *   GET  /voices/host-link            admin: Patrick's co-host studio link
 *   GET  /voices/health               deploy verification
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
  // Nerra Voices (Sept 2026): optional second Cal.com event. Falls back to
  // CALCOM_BOOKING_URL when unset so one shared event link keeps working.
  CALCOM_BOOKING_URL_NERRA_VOICES?: string;
  // Optional: the Cal.com event-type slug (or numeric id) per show, used to
  // route the booking webhook. Without them, an event slug containing
  // "voices" → nerra_voices, anything else → age_of_ai.
  CALCOM_EVENT_SLUG_AGE_OF_AI?: string;
  CALCOM_EVENT_SLUG_NERRA_VOICES?: string;
  SLACK_WEBHOOK?: string;
  // WebRTC studio (July 2026): Voximplant app user the browser SDK logs in
  // as, via the one-time-key handshake in /voices/studio-auth.
  VOX_GUEST_USER?: string;      // default "guest"
  VOX_GUEST_PASSWORD?: string;
  OPERATOR_EMAIL?: string;      // default patricknovak1@gmail.com
  // Comma-separated, copied alongside OPERATOR_EMAIL on guest-facing mail.
  OPERATOR_CC?: string;         // default patrick@planetterrian.com
  // Phase 2 co-host (Sept 2026, docs/cohost_phase2_contract.md): Patrick
  // joins every interview from the same studio page as `host`. The
  // scenario dials this Voximplant user; the page auto-answers. Host
  // credentials are only issued to a caller presenting ADMIN_TOKEN.
  VOX_HOST_USER?: string;       // default "host"
  VOX_HOST_PASSWORD?: string;
  OPERATOR_PHONE?: string;      // E.164; the fire step SMSes the host link
  // R2 bucket the Python pipeline also uploads to (VOICES_R2_BUCKET in
  // Actions). Local browser recordings land here as
  // <r2_prefix>/local/<run_id>/<role>/<seq>.webm + manifest.json.
  VOICES_R2: R2Bucket;
}

const REPO = "Planetterrian/nerranetwork";
const SEARCH_INDEX_URL = "https://nerranetwork.com/api/search_index.json";
const SITE = "https://nerranetwork.com";

// ---------------------------------------------------------------------------
// Shows (Sept 2026). Mirrors pipelines/voices/shows.py + shows/<slug>.yaml
// `voices:` blocks — keep the three in sync. Rows written before the
// 20260905 migration have no `show` and resolve to age_of_ai.
// ---------------------------------------------------------------------------

export type ShowSlug = "age_of_ai" | "nerra_voices";

export interface Show {
  slug: ShowSlug;
  name: string;        // "The Age of AI" — sentences, sign-offs
  shortLabel: string;  // "Age of AI" — Slack prefixes, subjects, titles
  brandColor: string;
  page: string;        // public show page on nerranetwork.com
  applyPage: string;
  studioPage: string;  // shared studio; branded via ?show=<slug>
  r2Prefix: string;    // R2 key prefix (mirrors shows/<slug>.yaml r2_prefix)
}

export const SHOWS: Record<ShowSlug, Show> = {
  age_of_ai: {
    slug: "age_of_ai",
    name: "The Age of AI",
    shortLabel: "Age of AI",
    brandColor: "#7C3AED",
    page: "age-of-ai.html",
    applyPage: "age-of-ai-apply.html",
    studioPage: "age-of-ai-studio.html",
    r2Prefix: "age_of_ai",
  },
  nerra_voices: {
    slug: "nerra_voices",
    name: "Nerra Voices",
    shortLabel: "Nerra Voices",
    brandColor: "#0F766E",
    page: "nerra-voices.html",
    applyPage: "nerra-voices-apply.html",
    studioPage: "age-of-ai-studio.html",
    r2Prefix: "nerra_voices",
  },
};

export const DEFAULT_SHOW: ShowSlug = "age_of_ai";

export function isShow(slug: unknown): slug is ShowSlug {
  return typeof slug === "string" && Object.prototype.hasOwnProperty.call(SHOWS, slug);
}

/** Show for a Supabase row (interview, application, run), with fallbacks —
 *  e.g. `showFor(interview, application)`. Missing/unknown → age_of_ai. */
export function showFor(...rows: Array<{ show?: unknown } | null | undefined>): Show {
  for (const row of rows) {
    if (row && isShow(row.show)) return SHOWS[row.show];
  }
  return SHOWS[DEFAULT_SHOW];
}

export type StudioRole = "guest" | "host";

/** Phone number → E.164, or null when it cannot be one. A bare 10-digit
 *  number is assumed North American (+1); 11 digits starting 1 likewise. */
export function toE164(raw: unknown, defaultCountry = "1"): string | null {
  const s = String(raw ?? "").trim();
  if (!s) return null;
  if (s.startsWith("+")) {
    const rest = s.slice(1).replace(/\D/g, "");
    return rest.length >= 8 && rest.length <= 15 ? `+${rest}` : null;
  }
  const d = s.replace(/\D/g, "");
  if (d.length === 10) return `+${defaultCountry}${d}`;
  if (d.length === 11 && d.startsWith("1")) return `+${d}`;
  if (d.startsWith("00") && d.length >= 10 && d.length <= 17) return `+${d.slice(2)}`;
  return d.length >= 8 && d.length <= 15 ? `+${d}` : null;
}

/** Studio page URL. Guests get `&role=guest`; the co-host link is the
 *  same page with `&role=host` — since Sept 9 2026 (rooms) it carries NO
 *  token: everyone joins the interview room the same way, the role only
 *  tells Mira who the co-host is and labels his recording. */
function studioUrl(show: Show, interviewId: string, role: StudioRole = "guest"): string {
  return `${SITE}/${show.studioPage}?interview=${interviewId}&show=${show.slug}&role=${role}`;
}

function hostStudioUrl(_env: Env, show: Show, interviewId: string): string {
  return studioUrl(show, interviewId, "host");
}

function bookingUrl(env: Env, show: Show): string {
  if (show.slug === "nerra_voices" && env.CALCOM_BOOKING_URL_NERRA_VOICES) {
    return env.CALCOM_BOOKING_URL_NERRA_VOICES;
  }
  return env.CALCOM_BOOKING_URL;
}

const signOff = (show: Show) => `— ${show.name}, Nerra Network`;

/** Which show a Cal.com booking belongs to. Explicit env mapping first
 *  (event-type slug or numeric id), then the "voices" heuristic. */
function showFromCalCom(env: Env, eventSlug: string, eventTypeId: string): Show {
  const slug = eventSlug.trim().toLowerCase();
  const id = eventTypeId.trim();
  const mapping: Array<[ShowSlug, string | undefined]> = [
    ["age_of_ai", env.CALCOM_EVENT_SLUG_AGE_OF_AI],
    ["nerra_voices", env.CALCOM_EVENT_SLUG_NERRA_VOICES],
  ];
  for (const [showSlug, configured] of mapping) {
    const want = (configured ?? "").trim().toLowerCase();
    if (want && (want === slug || (id && want === id.toLowerCase()))) return SHOWS[showSlug];
  }
  return slug.includes("voices") ? SHOWS.nerra_voices : SHOWS.age_of_ai;
}

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

/** Secrets pasted into `wrangler secret put` routinely carry a trailing
 *  newline; GitHub answers 401 to `Bearer <token>\n` and the five-minute
 *  fire-tick silently never arrives (Aug 2026 outage debugging). Trim
 *  defensively. */
function githubToken(env: Env): string {
  return (env.GITHUB_DISPATCH_TOKEN || "").trim();
}

async function dispatch(env: Env, eventType: string, payload: Record<string, unknown>) {
  const resp = await fetch(`https://api.github.com/repos/${REPO}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${githubToken(env)}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "nerra-voices-worker",
    },
    body: JSON.stringify({ event_type: eventType, client_payload: payload }),
  });
  if (resp.status !== 204) throw new Error(`repository_dispatch ${eventType}: ${resp.status}`);
}

function operatorEmail(env: Env): string {
  return env.OPERATOR_EMAIL || "patricknovak1@gmail.com";
}

// Sept 21 2026: Mira runs the correspondence end to end and Patrick reads it
// at both addresses — the Gmail he lives in and the Planetterrian one that is
// archived with the rest of the business. Every ccOperator mail goes to both,
// so "copy Patrick" cannot quietly mean one of them. Mirrors OPERATOR_CC in
// pipelines/voices/common.py — change the two together.
function operatorCc(env: Env): string[] {
  const extra = (env.OPERATOR_CC ?? "patrick@planetterrian.com")
    .split(",").map((a) => a.trim()).filter(Boolean);
  const all = [operatorEmail(env), ...extra];
  const seen = new Set<string>();
  return all.filter((a) => {
    const k = a.toLowerCase();
    if (!a.includes("@") || seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

// Something between us and Gmail decodes our HTML as quoted-printable
// without our ever having encoded it, so an "=" inside a link is eaten
// together with the two characters after it ("?interview=89fbb824..."
// arrived as "?interview\uFFFDfbb824..."). A numeric entity survives that
// decode and the browser turns it back into "=", so we spell "=" that way
// inside URLs and nowhere else. Mirrors email_safe_html in
// pipelines/voices/common.py — change the two together.
function emailSafeHtml(html: string): string {
  return (html || "").replace(/https?:\/\/[^\s"'<>]+/g,
    (url) => url.replace(/=/g, "&#61;"));
}

async function email(env: Env, to: string, subject: string, html: string,
                     ccOperator = false, extraCc?: string[]) {
  const body: Record<string, unknown> = {
    from: env.VOICES_FROM_EMAIL, to: [to], subject, html: emailSafeHtml(html),
  };
  // Operator oversight (July 2026): Patrick is CC'ed on guest-facing
  // scheduling/prep mail so Mira can run the show day-to-day while he
  // keeps full visibility.
  const cc: string[] = [];
  if (ccOperator) {
    for (const addr of operatorCc(env)) {
      if (addr.toLowerCase() !== to.toLowerCase()) cc.push(addr);
    }
  }
  for (const addr of extraCc ?? []) {
    if (addr && addr.includes("@") && addr.toLowerCase() !== to.toLowerCase()
        && !cc.some((c) => c.toLowerCase() === addr.toLowerCase())) cc.push(addr);
  }
  if (cc.length) body.cc = cc;
  const resp = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
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

/** The shell every guest-facing page shares. Plain, readable on a phone,
 *  and no branding games — these pages exist to make one decision easy. */
const page = (title: string, body: string, brand = "#2b6cb0") => `<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title>
<style>body{font:16px/1.6 system-ui;max-width:640px;margin:2rem auto;padding:0 1rem;color:#1a202c}
button{background:${brand};color:#fff;border:0;border-radius:8px;padding:.7rem 1.4rem;font-size:1rem;cursor:pointer}
textarea{font:inherit;padding:.5rem;border:1px solid #cbd5e0;border-radius:6px}
a{color:${brand}}label{cursor:pointer}</style>
<h1>${title}</h1>
${body}`;

function requireAdmin(req: Request, env: Env): Response | null {
  const auth = req.headers.get("Authorization") ?? "";
  const url = new URL(req.url);
  const token = auth.replace(/^Bearer\s+/i, "") || url.searchParams.get("token") || "";
  if (!env.ADMIN_TOKEN || token !== env.ADMIN_TOKEN) {
    return json({ error: "unauthorized" }, 401);
  }
  return null;
}

// Gate 1 used to be reachable only with the raw ADMIN_TOKEN, and the
// Slack ping linked to it without one — so the link 401'd until Patrick
// pasted the token by hand, and nothing was emailed at all (Sept 10
// 2026). A per-package token, derived the same way studio passwords are,
// is safe to put in an email: it opens exactly one package and carries no
// admin rights anywhere else.
//   hex(HMAC_SHA256(ADMIN_TOKEN, "nerra-review:" + packageId))[:40]
// The Python side computes the identical value (pipelines/voices/common.py,
// package_review_token) to build the link it emails.
async function packageReviewToken(env: Env, packageId: string): Promise<string> {
  const token = (env.ADMIN_TOKEN || "").trim();
  if (!token) throw new Error("ADMIN_TOKEN required to derive review tokens");
  const enc = new TextEncoder();
  const cryptoKey = await crypto.subtle.importKey(
    "raw", enc.encode(token), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", cryptoKey, enc.encode(`nerra-review:${packageId}`));
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 40);
}

/** Admin rights, or the per-package review token for THIS package. */
async function requirePackageAccess(req: Request, env: Env, packageId: string):
    Promise<Response | null> {
  const url = new URL(req.url);
  const supplied = (req.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "")
    || url.searchParams.get("token") || "";
  if (env.ADMIN_TOKEN && supplied === env.ADMIN_TOKEN) return null;
  if (supplied && packageId) {
    try {
      if (supplied === await packageReviewToken(env, packageId)) return null;
    } catch { /* fall through to 401 */ }
  }
  return json({ error: "unauthorized" }, 401);
}

/** What a reviewer should stream: the small MP3 preview the post-interview
 *  job renders when it can, falling back to the raw mixed WAV (which for a
 *  45-minute call is a ~250 MB download and punishing on a phone). */
function reviewAudioUrl(run: any): string | null {
  const preview = run?.grok_session_log?.tracks?.preview;
  const url = (typeof preview === "string" && preview) || run?.recording_mixed_url;
  return typeof url === "string" && url ? url : null;
}

const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** interview + its application + resolved show (two queries, the pattern
 *  the rest of this file uses). `interview` is null when the id is unknown. */
async function interviewWithApp(env: Env, interviewId: string):
    Promise<{ interview: any | null; app: any | null; show: Show }> {
  const interview = (await sb(env, "GET", `interviews?id=eq.${interviewId}`))?.[0] ?? null;
  const app = interview?.application_id
    ? (await sb(env, "GET", `guest_applications?id=eq.${interview.application_id}`))?.[0] ?? null
    : null;
  return { interview, app, show: showFor(interview, app) };
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

/** Interview length the guest asked for, in minutes, or null. Bounded by what
 *  the room can actually do: the Grok session relay hands over every 30
 *  minutes and the scenario's hard cap is 50, so anything longer than 90 is a
 *  typo rather than a request. */
function clampMinutes(value: unknown): number | null {
  const n = Math.round(Number(value));
  if (!Number.isFinite(n) || n <= 0) return null;
  return Math.min(90, Math.max(15, n));
}

function oneOf(value: unknown, allowed: string[]): string | null {
  const v = String(value ?? "").trim().toLowerCase();
  return allowed.includes(v) ? v : null;
}

async function handleApply(req: Request, env: Env): Promise<Response> {
  const form = await req.json<any>().catch(() => null);
  if (!form?.name || !form?.email) return json({ error: "name and email are required" }, 400);
  // `show` comes from the apply page (age-of-ai-apply.html posts age_of_ai,
  // nerra-voices-apply.html posts nerra_voices); anything else → default.
  const show = showFor({ show: form.show });
  const emailAddr = String(form.email).trim().slice(0, 200);
  const fields: Record<string, unknown> = {
    name: String(form.name).slice(0, 200),
    email: emailAddr,
    // Normalise at the door (Sept 10 2026): a guest typed "7737240695" and
    // Voximplant refused every send with "'destination' parameter is
    // invalid", costing him his reminder SMS and his phone fallback. Bare
    // 10-digit numbers are assumed US/Canada (+1).
    phone: toE164(form.phone),
    organization: form.organization ? String(form.organization).slice(0, 200) : null,
    title: form.title ? String(form.title).slice(0, 200) : null,
    bio: form.bio ? String(form.bio).slice(0, 4000) : null,
    topics: Array.isArray(form.topics) ? form.topics.slice(0, 10) : null,
    links: form.links ?? null,
    // What the guest wants the conversation to be (Sept 13 2026). These three
    // shape Mira's brief, the number of questions she prepares, and the clock
    // she paces to. A guest who asks for twenty minutes and gets forty-five
    // has been mistreated, however good the questions were.
    desired_minutes: clampMinutes(form.desired_minutes),
    depth: oneOf(form.depth, ["accessible", "standard", "deep"]),
    personal_depth: oneOf(form.personal_depth, ["none", "light", "open"]),
    off_limits: form.off_limits ? String(form.off_limits).slice(0, 500) : null,
    // Sept 18 2026: Mira carries the room on her own. Patrick Novak, who
    // created the network, joins as co-host only when the guest asks.
    wants_cohost: form.wants_cohost === true || String(form.wants_cohost ?? "").toLowerCase() === "yes",
    preferred_window: form.preferred_window ?? null,
    referrer: form.referrer ?? null,
    show: show.slug,
  };

  // Nerra Producer (Sept 2026): the inbox job may already have created an
  // `invited` row for this email (publicist pitched, Mira replied with the
  // apply link). The form completes THAT row instead of creating a
  // duplicate — provenance (source='email', pitched_show, email_thread_id,
  // publicist_*) is kept; only the fields the guest actually filled in
  // are merged over the Producer's stub.
  let id: string | undefined;
  let merged = false;
  const invited = await sb(env, "GET",
    `guest_applications?email=ilike.${encodeURIComponent(emailAddr)}&status=eq.invited` +
    `&order=created_at.desc&limit=1&select=id,show`);
  if (invited?.length) {
    const patch: Record<string, unknown> = { status: "pending" };
    for (const [k, v] of Object.entries(fields)) {
      if (v !== null && v !== undefined && v !== "") patch[k] = v;
    }
    const rows = await sb(env, "PATCH", `guest_applications?id=eq.${invited[0].id}`,
      patch, "return=representation");
    id = rows?.[0]?.id ?? invited[0].id;
    merged = true;
    if (invited[0].show && invited[0].show !== show.slug) {
      console.warn(`apply: invited row ${id} was ${invited[0].show}, form says ${show.slug} — using the form's show`);
    }
  } else {
    const row = await sb(env, "POST", "guest_applications", fields, "return=representation");
    id = row?.[0]?.id;
  }

  await slack(env, `${show.shortLabel}: ${merged ? "invited guest completed their application" : "new guest application"} — *${form.name}* (${form.organization ?? "independent"}). Triage: https://api.nerranetwork.com/voices/admin/triage`);
  // Sept 18 2026: the application is read against the open web the moment
  // it arrives, and Patrick's email carries that read (screen_applications.py
  // sends it). Rhett Mikols was approved from a bio and a topic list; the
  // assessment is the paragraph that would have said there was nothing
  // behind them. If the dispatch fails, the plain email below still goes.
  let screening = false;
  if (id) {
    try {
      await dispatch(env, "application-received", { application_id: id });
      screening = true;
    } catch (err: any) {
      console.error("apply: could not dispatch the screen:", err?.message ?? err);
    }
  }
  if (!screening) {
    // Mira notifies the operator directly (July 2026 process): Patrick
    // approves guests from his inbox rather than watching a dashboard.
    try {
      await email(env, operatorEmail(env),
        `New ${show.shortLabel} guest application: ${form.name}`,
        `<p>Hi Patrick,</p>
         <p>A new guest just applied to ${esc(show.name)}${merged ? " (completing the application I invited them to from the inbox)" : ""}:</p>
         <p><strong>${esc(form.name)}</strong>${form.title ? `, ${esc(form.title)}` : ""}
         ${form.organization ? ` — ${esc(form.organization)}` : ""}<br>
         ${esc(String(form.bio ?? "").slice(0, 400))}</p>
         <p><em>Wants to talk about:</em> ${esc((Array.isArray(form.topics) ? form.topics : []).join(", "))}</p>
         <p><a href="https://api.nerranetwork.com/voices/admin/triage?token=${env.ADMIN_TOKEN}">
         Review and approve or decline here</a>. If approved, I'll send them
         my booking link and take it from there — you'll be copied on
         everything I send them.</p>
         <p>— Mira</p>`);
    } catch (err: any) {
      console.error("operator application email failed:", err?.message ?? err);
    }
  }
  return json({ ok: true, id, show: show.slug, merged, screening });
}

const PLATFORM_FAULT_REASONS = new Set(["grok_dropped", "agent_startup_failed", "media_bridge_failed"]);

async function handleInterviewComplete(req: Request, env: Env): Promise<Response> {
  const payload = await req.json<any>().catch(() => null);
  if (!payload?.run_id) return json({ error: "run_id required" }, 400);
  // Room model (Sept 9 2026): the per-person recording URLs arrive from
  // the participant sessions via /voices/leg-event, so the completion
  // payload MERGES into grok_session_log and never nulls a per-leg URL
  // it does not carry.
  const existingRows = await sb(env, "GET",
    `interview_runs?id=eq.${payload.run_id}&select=grok_session_log`);
  const existingLog = existingRows?.[0]?.grok_session_log ?? {};
  const patch: Record<string, unknown> = {
    status: payload.status === "failed" ? "failed" : "completed",
    disconnect_reason: payload.disconnect_reason ?? payload.reason ?? null,
    duration_sec: payload.duration_sec ?? null,
    grok_session_log: {
      ...existingLog,
      ...(payload.grok_session_log ? { log: payload.grok_session_log } : {}),
      ...(payload.voximplant_record_url ? { voximplant_record_url: payload.voximplant_record_url } : {}),
      ...(payload.voximplant_video_url ? { voximplant_video_url: payload.voximplant_video_url } : {}),
      ...(payload.audio_path ? { audio_path: payload.audio_path } : {}),
      ...(payload.voximplant_mix_record_url ? { voximplant_mix_record_url: payload.voximplant_mix_record_url } : {}),
      ...(payload.speech_events !== undefined ? { speech_events: Number(payload.speech_events) || 0 } : {}),
      call_mode: payload.call_mode ?? existingLog.call_mode ?? null,
    },
    // Per-leg Voximplant recordings and the host timeline the room
    // reports. Columns from supabase/migrations/20260906_cohost_conference.sql;
    // the post-interview pipeline reads them to build three clean tracks.
    ...(payload.voximplant_host_record_url ? { recording_host_url: payload.voximplant_host_record_url } : {}),
    ...(payload.voximplant_mira_record_url ? { recording_mira_url: payload.voximplant_mira_record_url } : {}),
    ...(payload.host_joined_at ? { host_joined_at: payload.host_joined_at } : {}),
    ...(payload.host_left_at ? { host_left_at: payload.host_left_at } : {}),
    host_attempts: Number(payload.host_attempts ?? 0) || 0,
  };
  // Aborted studio call (Aug 5 2026, Dan Perra dry run): a WebRTC session
  // shorter than 5 minutes is a failed join (media-path failure, refresh,
  // wrong room), not an interview. Reset the run so the guest can rejoin
  // immediately — do NOT mark it completed or dispatch post-production on
  // 141 seconds of silence.
  const dur = Number(payload.duration_sec ?? 0);
  // Room model (Sept 10 2026): a room that ended on a PLATFORM fault
  // (Grok connector closed, agent never started, media bridge failed) is
  // not a failed join by the guest — reopen the studio so the next join
  // starts a fresh room, count nothing against the browser path, and
  // never flip the interview to a phone call over it.
  const platformFault = PLATFORM_FAULT_REASONS.has(String(payload.disconnect_reason ?? ""));
  if (payload.call_mode === "webrtc" && platformFault) {
    await sb(env, "PATCH", `interview_runs?id=eq.${payload.run_id}`, {
      status: "awaiting_guest", duration_sec: null, disconnect_reason: null,
      grok_session_log: { ...existingLog, last_platform_fault: {
        reason: payload.disconnect_reason, duration_sec: dur, at: new Date().toISOString() } },
    });
    try {
      await email(env, operatorEmail(env),
        `Studio: room ended on a platform fault (${payload.disconnect_reason})`,
        `<p>Hi Patrick,</p><p>The interview room for run ${esc(String(payload.run_id))} ended after
         ${dur} seconds because of <strong>${esc(String(payload.disconnect_reason))}</strong>
         (the AI voice connection, not anyone's browser). The studio is open again: everyone
         can press Join on the same links and a fresh room starts. If it repeats, the xAI
         connector is having a bad moment; wait a minute and try again.</p><p>— Mira</p>`);
    } catch (err: any) {
      console.error("platform-fault email failed:", err?.message ?? err);
    }
    return json({ ok: true, platform_fault: true, reopened: true });
  }
  if (payload.call_mode === "webrtc" && payload.status !== "failed" && dur < 300) {
    const runRows = await sb(env, "GET",
      `interview_runs?id=eq.${payload.run_id}&select=interview_id,grok_session_log`);
    const runRow = runRows?.[0] ?? {};
    const attempts = Number(runRow.grok_session_log?.aborted_attempts ?? 0) + 1;
    const ivRows = runRow.interview_id ? await sb(env, "GET",
      `interviews?id=eq.${runRow.interview_id}&select=application_id,show`) : [];
    const show = showFor(ivRows?.[0]);

    if (attempts >= 2 && runRow.interview_id) {
      // AUTO PHONE FALLBACK (Aug 6 2026, after Dan Perra's four-attempt
      // studio ordeal): two failed browser joins = the browser path is
      // broken for this guest today. Flip the interview to PSTN, fail
      // this run so the fire tick (<=5 min, Worker cron) creates a fresh
      // one and dials the guest's phone. Everyone gets told; nobody has
      // to do anything.
      await sb(env, "PATCH", `interviews?id=eq.${runRow.interview_id}`,
        { status: "briefed", call_mode: "pstn" });
      await sb(env, "PATCH", `interview_runs?id=eq.${payload.run_id}`,
        { status: "failed", disconnect_reason: "studio_join_failed_x2_auto_pstn" });
      const apps = ivRows?.[0]?.application_id ? await sb(env, "GET",
        `guest_applications?id=eq.${ivRows[0].application_id}&select=name,email`) : [];
      if (apps?.[0]?.email) {
        await email(env, apps[0].email,
          "Change of plan — I'll call your phone instead",
          `<p>Hi ${esc(apps[0].name)},</p><p>The browser studio isn't
           cooperating with your setup today — no fault of yours. Let's not
           fight it: <strong>I'll call your phone within the next five
           minutes.</strong> Find a quiet spot, and answer when you see the
           call. Everything else works exactly the same.</p><p>— Mira</p>`,
          true);
      }
      await slack(env, `${show.shortLabel}: 2 failed studio joins — auto-switched to PSTN; Mira dials within 5 minutes.`);
      return json({ ok: true, auto_pstn_fallback: true });
    }

    await sb(env, "PATCH", `interview_runs?id=eq.${payload.run_id}`, {
      status: "awaiting_guest",
      duration_sec: null,
      disconnect_reason: null,
      // Merge, never replace: the log already holds per-leg recording URLs
      // and hand-over history that a short run must not wipe out.
      grok_session_log: { ...existingLog, aborted_attempts: attempts,
        last_aborted: { duration_sec: dur,
          record_url: payload.voximplant_record_url ?? null,
          at: new Date().toISOString() } },
    });
    await slack(env, `${show.shortLabel}: studio call ended after ${dur}s (attempt ${attempts}) — studio reopened for retry; one more failure auto-switches to phone.`);
    try {
      await email(env, operatorEmail(env),
        `${show.shortLabel}: guest's studio call dropped early — retry is open`,
        `<p>Hi Patrick,</p><p>A studio session ended after only ${dur} seconds
         (attempt ${attempts}) — a failed join. The studio is reopened for
         the guest; if the next attempt fails too, I'll automatically switch
         them to a phone call. No action needed.</p><p>— Mira</p>`);
    } catch (err: any) {
      console.error("aborted-join email failed:", err?.message ?? err);
    }
    return json({ ok: true, aborted_join: true, attempt: attempts });
  }

  await sb(env, "PATCH", `interview_runs?id=eq.${payload.run_id}`, patch);

  // Retry ladder for failed dials (spec §7 row 1, implemented July 2026):
  // a no-answer/failed call resets the interview to `briefed`, so the fire
  // cron's grace window re-dials on its next tick. Second strike marks the
  // interview `missed` and emails the guest a reschedule link — no silent
  // dead ends, no infinite redial of someone who isn't answering.
  const reason = String(payload.reason ?? payload.disconnect_reason ?? "");
  const isFailedDial = payload.status === "failed" &&
    (reason.includes("call_failed") || reason.includes("startup"));
  if (isFailedDial) {
    try {
      const runs = await sb(env, "GET",
        `interview_runs?id=eq.${payload.run_id}&select=interview_id`);
      const ivId = runs?.[0]?.interview_id;
      if (ivId) {
        const ivs = await sb(env, "GET",
          `interviews?id=eq.${ivId}&select=no_show_count,application_id,show`);
        const strikes = (ivs?.[0]?.no_show_count ?? 0) + 1;
        const show = showFor(ivs?.[0]);
        if (strikes < 2) {
          await sb(env, "PATCH", `interviews?id=eq.${ivId}`,
            { status: "briefed", no_show_count: strikes });
          await slack(env, `${show.shortLabel}: call attempt ${strikes} failed (${reason.slice(0, 120)}) — will retry within the fire grace window.`);
        } else {
          await sb(env, "PATCH", `interviews?id=eq.${ivId}`,
            { status: "missed", no_show_count: strikes });
          const apps = await sb(env, "GET",
            `guest_applications?id=eq.${ivs[0].application_id}&select=name,email`);
          if (apps?.[0]?.email) {
            const rebook = bookingUrl(env, show);
            await email(env, apps[0].email,
              `We missed you — rebook your ${show.shortLabel} interview`,
              `<p>Hi ${esc(apps[0].name)},</p><p>Mira tried to reach you twice for your` +
              ` ${esc(show.shortLabel)} interview but couldn't get through. No problem — pick a` +
              ` new time that works for you:</p><p><a href="${esc(rebook)}">` +
              `Rebook your interview</a></p><p>${esc(signOff(show))}</p>`, true);
          }
          await slack(env, `${show.shortLabel}: interview ${ivId} marked missed after 2 failed attempts — reschedule email sent.`);
        }
      }
    } catch (err: any) {
      console.error("retry-ladder error:", err?.message ?? err);
    }
    return json({ ok: true });
  }

  await dispatch(env, "interview-complete", { run_id: payload.run_id });
  return json({ ok: true });
}

/** Every address on a Cal.com booking, booker first.
 *
 *  Sept 16 2026: Mo Fakhro booked as mo@mofakhro.com while his application
 *  was under his publicist's pr@mofakhro.com, which was on the booking as a
 *  guest. Only the first attendee was ever looked at, so the booking matched
 *  nothing, no interview row was created, and a confirmed guest would have
 *  sat waiting for a call that was never scheduled. Nobody would have known
 *  until the day.
 */
function bookingEmails(p: any): string[] {
  const out: string[] = [];
  const add = (v: unknown) => {
    const e = String(v ?? "").trim().toLowerCase();
    if (e.includes("@") && !out.includes(e)) out.push(e);
  };
  for (const a of (p.attendees ?? [])) add(a?.email);
  add(p.email);
  add(p.responses?.email?.value ?? p.responses?.email);
  const guests = p.responses?.guests?.value ?? p.responses?.guests ?? p.guests;
  if (Array.isArray(guests)) guests.forEach((g: any) => add(g?.email ?? g));
  return out;
}

/** The booker's name as Cal.com gives it ("Meridan Zerner Nutrition"). */
function bookingName(p: any): string {
  const n = p.attendees?.[0]?.name ?? p.responses?.name?.value ?? p.responses?.name ?? p.name;
  return String(n ?? "").trim();
}

/** Letters and spaces only, lower-cased, for comparing names. */
function nameKey(s: unknown): string {
  return String(s ?? "").toLowerCase().normalize("NFKD")
    .replace(/[^a-z\s]/g, " ").replace(/\s+/g, " ").trim();
}

/** "Meridan Zerner" is on the booking as "Meridan Zerner Nutrition"; a
 *  publicist books as "Rhett Mikols (Think Right PR)". One name containing
 *  the other, with at least two words in common, is the same person. */
function namesOverlap(a: unknown, b: unknown): boolean {
  const ka = nameKey(a), kb = nameKey(b);
  if (ka.length < 5 || kb.length < 5) return false;
  if (ka === kb) return true;
  const wa = new Set(ka.split(" ")), wb = new Set(kb.split(" "));
  const common = [...wa].filter((w) => w.length > 1 && wb.has(w));
  return common.length >= 2 && (` ${kb} `.includes(` ${ka} `) || ` ${ka} `.includes(` ${kb} `));
}

/** Digits of a phone number, or "" when it is not one. */
function phoneDigits(v: unknown): string {
  const d = String(v ?? "").replace(/\D/g, "");
  return d.length >= 10 && d.length <= 15 ? d : "";
}

/** The number typed into the booking, as digits, from wherever Cal.com put
 *  it: the attendee, a phone field, or a custom question. */
function bookingPhone(p: any): string {
  const candidates: unknown[] = [p.attendees?.[0]?.phoneNumber, p.attendees?.[0]?.phone,
                                 p.responses?.phone?.value ?? p.responses?.phone];
  for (const v of Object.values(p.responses ?? {})) {
    const val = (v as any)?.value ?? v;
    if (typeof val === "string" && /\+?\d[\d\s().-]{8,}\d/.test(val)) candidates.push(val);
  }
  for (const c of candidates) {
    const m = String(c ?? "").match(/\+?\d[\d\s().-]{8,}\d/);
    const d = phoneDigits(m?.[0]);
    if (d) return d;
  }
  return "";
}

/** Whatever the booker wrote in the notes/"additional notes" question. */
function bookingNotes(p: any): string {
  const n = p.responses?.notes?.value ?? p.responses?.notes ?? p.additionalNotes ?? p.description;
  return String(n ?? "").trim();
}

async function handleCalComBooked(req: Request, env: Env): Promise<Response> {
  const hook = await req.json<any>().catch(() => null);
  const p = hook?.payload ?? hook ?? {};
  const emails = bookingEmails(p);
  const emailAddr = emails[0] ?? "";
  const startTime = p.startTime ?? p.start_time ?? null;
  if (!emailAddr || !startTime) return json({ error: "email + startTime required" }, 400);

  // Which show was booked: Cal.com sends the event type in a few shapes
  // depending on webhook version. Env mapping wins; else the "voices"
  // heuristic (see showFromCalCom).
  const eventSlug = String(p.eventType?.slug ?? p.eventTypeSlug ?? p.event_type_slug ?? "");
  const eventTypeId = String(p.eventTypeId ?? p.eventType?.id ?? p.event_type_id ?? "");
  const bookedShow = showFromCalCom(env, eventSlug, eventTypeId);

  const base = `guest_applications?email=eq.${encodeURIComponent(emailAddr)}&status=eq.approved`;
  let apps = await sb(env, "GET",
    `${base}&show=eq.${bookedShow.slug}&order=created_at.desc&limit=1`);
  if (!apps?.length) {
    // No approved application for that show — fall back to the newest
    // approved one for the email regardless of show (a guest booked via
    // the other show's event link, or a pre-migration row).
    apps = await sb(env, "GET", `${base}&order=created_at.desc&limit=1`);
    if (apps?.length) {
      console.warn(`cal-com-booked: no approved ${bookedShow.slug} application for ${emailAddr}; ` +
        `falling back to application ${apps[0].id} (show=${apps[0].show ?? "unset"})`);
    }
  }
  if (!apps?.length) {
    // Producer-sourced pitches (Sept 2026): the row's email is usually the
    // publicist's, but the guest books with their own address (or the
    // publicist books with theirs). Match either side before giving up.
    // Try EVERY address on the booking, against both sides of the row. The
    // person who books is often not the address we invited.
    let matchedWith = emailAddr;
    for (const candidate of emails) {
      const alt = `guest_applications?status=eq.approved&or=(publicist_email.eq.${encodeURIComponent(candidate)},email.eq.${encodeURIComponent(candidate)})`;
      apps = await sb(env, "GET", `${alt}&order=created_at.desc&limit=1`);
      if (apps?.length) { matchedWith = candidate; break; }
    }
    if (apps?.length) {
      console.warn(`cal-com-booked: matched ${matchedWith} via publicist_email on application ${apps[0].id}`);
      // Remember the address the guest actually booked with so the
      // confirmation, brief and studio link reach the person on the call.
      if ((apps[0].email ?? "").toLowerCase() !== emailAddr) {
        await sb(env, "PATCH", `guest_applications?id=eq.${apps[0].id}`,
          { email: emailAddr, notes: `${apps[0].notes ?? ""}\nBooked with ${emailAddr} (row email was ${apps[0].email}).`.trim() });
        apps[0].email = emailAddr;
      }
    }
  }
  // Sept 20 2026: Meridan Zerner applied as lyndon@withmeridanzernernutrition.com
  // and booked as meridan@meridanzernernutrition.com. No address matched, the
  // alert above did not exist yet, and the interview was found by hand
  // thirty-eight minutes before it was due. An address is the weakest key we
  // have; the person's name and the phone they typed into the booking are
  // on the row too. Try those before declaring the booking an orphan.
  const bookedName = bookingName(p);
  const bookedPhone = bookingPhone(p);
  let howMatched = "";
  if (!apps?.length && (bookedName || bookedPhone)) {
    const approved: any[] = (await sb(env, "GET",
      "guest_applications?status=eq.approved&order=created_at.desc&limit=300")) ?? [];
    let hits = bookedPhone
      ? approved.filter((a) => phoneDigits(a.phone) && phoneDigits(a.phone) === bookedPhone)
      : [];
    if (hits.length) howMatched = "phone";
    if (!hits.length && bookedName) {
      hits = approved.filter((a) => namesOverlap(a.name, bookedName));
      if (hits.length) howMatched = "name";
    }
    if (hits.length > 1) {
      // Prefer the show that was booked, then the newest; never guess
      // across two people who share a name.
      const sameShow = hits.filter((a) => a.show === bookedShow.slug);
      hits = sameShow.length ? sameShow : hits;
      const distinct = new Set(hits.map((a) => nameKey(a.name)));
      if (distinct.size > 1) hits = [];
    }
    if (hits.length) {
      apps = [hits[0]];
      console.warn(`cal-com-booked: matched ${bookedName || bookedPhone} by ${howMatched} to application ${apps[0].id}`);
      const patch: Record<string, unknown> = {
        notes: `${apps[0].notes ?? ""}\nBooked with ${emailAddr} (row email was ${apps[0].email}); matched by ${howMatched}.`.trim(),
      };
      if ((apps[0].email ?? "").toLowerCase() !== emailAddr) patch.email = emailAddr;
      if (!phoneDigits(apps[0].phone) && bookedPhone) patch.phone = `+${bookedPhone}`;
      await sb(env, "PATCH", `guest_applications?id=eq.${apps[0].id}`, patch);
      Object.assign(apps[0], patch);
      await slack(env, `${bookedShow.shortLabel}: booking from ${emailAddr} matched *${apps[0].name}* by ${howMatched}, not by address — row email updated.`);
    }
  }
  if (!apps?.length) {
    // A booking that matches nothing must never be silent, and it must never
    // be dropped either. Somebody has put a time in Patrick's calendar and is
    // expecting a call, so the call is scheduled from what the booking says
    // and Patrick is told he can kill it. A stranger who found the link costs
    // one wasted call; a confirmed guest nobody rings costs the show a guest.
    const who = `${bookedName || "someone"} (${emails.join(", ") || "no address"})`;
    const stub = await sb(env, "POST", "guest_applications", {
      name: bookedName || emailAddr,
      email: emailAddr,
      phone: bookedPhone ? `+${bookedPhone}` : null,
      bio: bookingNotes(p) || null,
      show: bookedShow.slug,
      status: "approved",
      source: "calcom",
      notes: `Created from a Cal.com booking at ${startTime} that matched no application. ` +
        `Patrick was told; kill the interview from the triage page if this is not a guest we invited.`,
    }, "return=representation");
    apps = stub?.length ? stub : [];
    await slack(env, `:rotating_light: Cal.com booking for ${who} at ${startTime} matched NO application. ` +
      (apps.length
        ? "A placeholder application and the interview were created so Mira still calls; check the triage page."
        : "And the placeholder could not be created — nobody is calling them."));
    try {
      await email(env, operatorEmail(env),
        `A booked ${bookedShow.shortLabel} interview matched no application`,
        `<p>Hi Patrick,</p><p><strong>${esc(who)}</strong> booked a time at
         <strong>${esc(String(startTime))}</strong> and it matched no application
         by address, name or phone.</p>
         ${apps.length
           ? `<p>So that nobody is left waiting for a call, I created an application
              from the booking and scheduled the interview. If this is someone we
              invited under another address, merge it into their real application
              on the <a href="https://api.nerranetwork.com/voices/admin/triage?token=${env.ADMIN_TOKEN}">triage page</a>;
              if it is not a guest we want, kill it there.</p>`
           : `<p>I could not create a placeholder either, so no interview exists and
              nobody will call them. Add it by hand.</p>`}
         ${bookingNotes(p) ? `<p><em>What they wrote on the booking:</em> ${esc(bookingNotes(p).slice(0, 800))}</p>` : ""}
         <p>— Mira</p>`);
    } catch (err: any) {
      console.error("cal-com-booked: could not warn the operator:", err?.message ?? err);
    }
    if (!apps.length) return json({ error: "no application for that booking" }, 404);
  }
  // The application decides the interview's show (that is what Patrick
  // approved and what the pipeline keys prompts/publishing on).
  const show = showFor(apps[0], { show: bookedShow.slug });

  // duration_min existed in the schema from the start and nothing ever wrote
  // it; the length was a constant in the scenario. The guest's answer on the
  // application decides it now, and 45 stays the default for everyone who has
  // no preference.
  const plannedMinutes = clampMinutes(apps[0].desired_minutes) ?? 45;

  const existing = await sb(env, "GET",
    `interviews?application_id=eq.${apps[0].id}&status=in.(scheduled,briefed)&limit=1`);
  let interviewId: string;
  if (existing?.length) {
    interviewId = existing[0].id;
    await sb(env, "PATCH", `interviews?id=eq.${interviewId}`,
      { scheduled_at: startTime, status: "scheduled", reminder_sent_at: null, show: show.slug,
        duration_min: plannedMinutes, host_mode: !!apps[0].wants_cohost });
  } else {
    const created = await sb(env, "POST", "interviews",
      { application_id: apps[0].id, scheduled_at: startTime, status: "scheduled", show: show.slug,
        duration_min: plannedMinutes, host_mode: !!apps[0].wants_cohost },
      "return=representation");
    interviewId = created?.[0]?.id ?? "";
  }
  const studio = studioUrl(show, interviewId, "guest");
  await email(env, emailAddr, `Your ${show.shortLabel} interview is booked`,
    `<p>Hi ${esc(apps[0].name)},</p>
     <p>You're booked. At the scheduled time, join Mira — our AI host — from
     your personal browser studio:</p>
     <p><a href="${studio}"><strong>Join your interview here</strong></a>
     (bookmark it — it unlocks a few minutes before your slot).</p>
     <p>To sound your best: use a computer in a quiet room and
     <strong>wear headphones or earbuds</strong> (a dedicated mic is even
     better, but the headphones matter more). Without them your microphone
     picks up Mira's voice out of your speakers, which puts her half of the
     conversation into your recording and her questions into the transcript as
     though you had said them. The studio plays a tone and listens for it
     before you join, so it will tell you either way. Camera is optional but
     appreciated — we record video for a future YouTube version. If the
     browser route doesn't work for you, reply to this email and Mira can
     call your phone instead.</p>
     <p>We have it down as about ${plannedMinutes} minutes${apps[0].desired_minutes ? ", which is what you asked for" : ""}. Mira paces the
     conversation to that and starts wrapping up near the end rather than
     cutting you off.</p>
     ${apps[0].wants_cohost
       ? "<p>You asked for Patrick Novak, the network's creator, to join as co-host. He will be in the room with Mira.</p>"
       : ""}
     <p>About a day before, you'll receive a short prep brief with the
     themes she plans to explore.</p>
     <p>Two things to know: the conversation is recorded for the podcast,
     and nothing publishes until you've reviewed and approved the
     transcript.</p>
     <p>${esc(signOff(show))}</p>`, true);
  await slack(env, `${show.shortLabel}: ${apps[0].name} booked ${startTime}` +
    (apps[0].wants_cohost ? " — guest asked for Patrick as co-host" : ""));
  return json({ ok: true, show: show.slug, interview_id: interviewId });
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
    const show = showFor(app);
    const link = bookingUrl(env, show);
    await email(env, app.email, `You're invited — book your ${show.name} interview`,
      `<p>Hi ${esc(app.name)},</p>
       <p>We'd love to have you on ${esc(show.name)}. Pick a time that works and
       Mira — our AI host — will call you: </p>
       <p><a href="${esc(link)}">${esc(link)}</a></p>
       <p>The call runs about forty-five minutes. It's recorded, and nothing
       publishes until you've approved the transcript.</p>
       <p>${esc(signOff(show))}</p>`, true);
  }
  if (app && body.decision === "declined" && app.email) {
    // Sept 18 2026: a declined application used to hear nothing at all.
    // Everyone who took the time to apply gets an answer, the same one,
    // and a publicist who pitched them is copied so they are not left
    // chasing.
    const show = showFor(app);
    try {
      await email(env, app.email, `Your ${show.name} application`,
        `<p>Hi ${esc(app.name)},</p>
         <p>Thank you for applying to be a guest on ${esc(show.name)}, and for
         the time you put into telling us about your work.</p>
         <p>We are not going to be able to find a place for it on the show at
         the moment. We record a small number of conversations and choose
         them around what each one lets Mira ask that no other guest could,
         which means turning down more people than we would like to,
         including many with real things to say.</p>
         <p>We keep every application, and if your work takes a turn that
         would give us a specific story to sit down over, you are welcome
         to apply again.</p>
         <p>${esc(signOff(show))}</p>`, true,
        app.publicist_email ? [String(app.publicist_email)] : undefined);
    } catch (err: any) {
      console.error("decline email failed:", err?.message ?? err);
    }
  }
  return json({ ok: true });
}

// POST /voices/triage-reassign {application_id, show} — a pitch that landed
// on the wrong show (the Producer's classifier or the guest's own pick)
// moves before approval, so the booking link, studio branding and the
// pipeline's prompts all follow the corrected show.
async function handleTriageReassign(req: Request, env: Env): Promise<Response> {
  const denied = requireAdmin(req, env);
  if (denied) return denied;
  const body = await req.json<any>().catch(() => null);
  if (!body?.application_id || !isShow(body.show)) {
    return json({ error: `application_id + show(${Object.keys(SHOWS).join("|")}) required` }, 400);
  }
  const rows = await sb(env, "PATCH",
    `guest_applications?id=eq.${body.application_id}`,
    { show: body.show }, "return=representation");
  const app = rows?.[0];
  if (!app) return json({ error: "application not found" }, 404);
  await slack(env, `${SHOWS[body.show as ShowSlug].shortLabel}: application from *${app.name}* reassigned to this show by Patrick.`);
  return json({ ok: true, id: app.id, show: app.show });
}

async function handleEditorialDecision(req: Request, env: Env): Promise<Response> {
  const body = await req.json<any>().catch(() => null);
  if (!body?.package_id || !["approve", "kill"].includes(body.decision)) {
    return json({ error: "package_id + decision(approve|kill) required" }, 400);
  }
  // Scoped to the package being decided: a review link can approve or kill
  // its own episode and nothing else.
  const denied = await requirePackageAccess(req, env, String(body.package_id));
  if (denied) return denied;
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

  const { interview, app, show } = await interviewWithApp(env, pkg.interview_id);
  if (body.decision === "approve") {
    // Gate 1 cleared → open gate 2: email the guest their review link.
    if (!interview || !app) return json({ error: "interview/application not found" }, 404);
    await sb(env, "PATCH", `interviews?id=eq.${interview.id}`, { status: "guest_review" });
    const link = `https://api.nerranetwork.com/voices/review/${pkg.guest_review_token}`;
    // Sept 22 2026. Meridan Zerner's episode ran seventeen minutes because
    // Mira closed it early, and Sameer Ranjan's ended mid-thought. Both
    // needed something said that no template covers, so both were written by
    // hand from Patrick's own mailbox — which is the one thing this process
    // is meant not to do. A note written at gate 1 rides along instead, in
    // Mira's mail, in front of the standard text rather than instead of it.
    const note = String(body.note_to_guest ?? "").trim();
    const noteHtml = note
      ? note.split(/\n{2,}/).map((para: string) =>
          `<p>${esc(para.trim()).replace(/\n/g, "<br>")}</p>`).join("")
      : "";
    await email(env, app.email, `Thank you — your ${show.shortLabel} episode is ready for you`,
      `<p>Hi ${esc(app.name)},</p>
       ${noteHtml}
       <p>Thank you for the time you gave us. Your episode is edited and
       ready, and nothing goes out until you have heard it and said yes.</p>
       <p><a href="${esc(link)}">Listen to the episode and read the transcript</a></p>
       <p>On that page you can approve it as it stands, or quote anything
       you'd rather we cut and it comes out of both the audio and the
       transcript.</p>
       <p>Two other things are on the page, and we mean them. If the
       conversation didn't catch you at your best, you can ask to record it
       again from scratch — we would rather re-record than publish something
       you are lukewarm about. And you can put yourself down to come back in
       six months or a year to tell us what has actually changed in your
       field since we spoke. That follow-up is the part of this show we care
       most about: almost nobody goes back to check.</p>
       <p>One more thing, and it is the part guests tell us they care about
       most: when this publishes we write a full post for the episode.
       There is a box on that page for anything you would like a listener
       to find next — a short biography in your own words, your site or
       book, papers or talks worth reading. Whatever you put there goes in
       the post.</p>
       <p>If we don't hear from you within seven days we'll take that as
       approval, and we'll remind you at day four. You can always ask for
       changes after publication too.</p>
       <p>${esc(signOff(show))}</p>`, true);
    await slack(env, `${show.shortLabel}: Patrick approved package ${pkg.id} — guest review email sent`);
  } else {
    await sb(env, "PATCH", `interviews?id=eq.${pkg.interview_id}`, { status: "failed" });
    await slack(env, `${show.shortLabel}: Patrick KILLED package ${pkg.id}`);
  }
  return json({ ok: true });
}

/** Promote or drop one proposed lesson. Scoped by the package's review token
 *  like every other gate-1 action, so the emailed link can do it. */
async function handleLessonDecision(req: Request, env: Env): Promise<Response> {
  const body = await req.json<any>().catch(() => null);
  const lessonId = String(body?.lesson_id ?? "");
  const status = String(body?.status ?? "");
  if (!UUID_RE.test(lessonId) || !["active", "retired"].includes(status)) {
    return json({ error: "lesson_id + status(active|retired) required" }, 400);
  }
  const denied = await requirePackageAccess(req, env, String(body?.package_id ?? ""));
  if (denied) return denied;
  const rows = await sb(env, "PATCH", `show_lessons?id=eq.${lessonId}`,
    { status, decided_at: new Date().toISOString() }, "return=representation");
  if (!rows?.[0]) return json({ error: "lesson not found" }, 404);
  return json({ ok: true, id: lessonId, status });
}

/** POST /voices/narration-take {take_id, status, record_url?, detail?}
 *  The scenario's narrationSession reports here when Mira has finished
 *  reading one paragraph of a scripted pickup (Sept 11 2026). No auth: the
 *  take_id is an opaque row that must already exist, and the only thing this
 *  can do is attach a Voximplant recording URL to it. */
async function handleNarrationTake(req: Request, env: Env): Promise<Response> {
  const body = await req.json<any>().catch(() => null);
  const takeId = String(body?.take_id ?? "");
  if (!takeId || takeId.length > 128) return json({ error: "take_id required" }, 400);
  const status = ["ok", "failed"].includes(String(body?.status)) ? String(body.status) : "failed";
  const rows = await sb(env, "PATCH",
    `narration_takes?take_id=eq.${encodeURIComponent(takeId)}`, {
      status,
      record_url: typeof body?.record_url === "string" ? body.record_url : null,
      detail: typeof body?.detail === "string" ? body.detail.slice(0, 500) : null,
      reported_at: new Date().toISOString(),
    }, "return=representation");
  if (!rows?.[0]) return json({ error: "take not found" }, 404);
  return json({ ok: true });
}

// -- Gate 2: guest transcript review ----------------------------------------

async function pkgByToken(env: Env, token: string): Promise<any | null> {
  const rows = await sb(env, "GET",
    `editorial_packages?guest_review_token=eq.${encodeURIComponent(token)}&limit=1`);
  return rows?.[0] ?? null;
}

/** A guest's own page for the one thing they may need before the day: not
 *  today. Sept 15 2026 — Erica Sell did not join, and nobody knew whether she
 *  was late, lost or not coming. The room sat open, Mira waited, and the first
 *  anyone learned of it was a failed job. One tap two hours earlier would have
 *  cost nothing, so every reminder now carries this link. No login: the token
 *  is the interview, the way the review link is the episode. */
async function manageInterview(env: Env, token: string): Promise<any | null> {
  const rows = await sb(env, "GET",
    `interviews?manage_token=eq.${encodeURIComponent(token)}&limit=1`);
  return rows?.length ? rows[0] : null;
}

async function handleManagePage(env: Env, token: string): Promise<Response> {
  const interview = await manageInterview(env, token);
  if (!interview) return html(page("Link not found",
    "<p>This link has expired or was mistyped. Reply to any of our emails and we will sort it out.</p>"), 404);
  const apps = await sb(env, "GET",
    `guest_applications?id=eq.${interview.application_id}&limit=1`);
  const app = apps?.[0] ?? {};
  const show = showFor(interview, app);
  const when = interview.scheduled_at
    ? new Date(interview.scheduled_at).toUTCString().replace("GMT", "UTC")
    : "your scheduled time";
  const booking = env.CALCOM_BOOKING_URL || "";
  if (interview.status === "cancelled" || interview.cancelled_at) {
    return html(page("Already cancelled",
      `<p>Thanks — your ${esc(show.shortLabel)} interview is cancelled and nobody is waiting for you.</p>` +
      (booking ? `<p>Whenever you want to pick it up again: <a href="${esc(booking)}">book a new time</a>.</p>` : "")));
  }
  return html(page(`Your ${esc(show.shortLabel)} interview`, `
    <p>Hi ${esc(app.name ?? "there")} — your interview is set for <strong>${esc(when)}</strong>.</p>
    <p>If that still works, you do not need to do anything. If it does not,
       tell us here rather than leaving it. Nobody minds, and it means Mira is
       not sitting in an empty room waiting for you.</p>
    <form method="POST">
      <p><label><input type="radio" name="action" value="reschedule" required>
         I need a different time</label></p>
      <p><label><input type="radio" name="action" value="cancel">
         I cannot do this at all — take me off the schedule</label></p>
      <p><textarea name="note" rows="3" style="width:100%"
         placeholder="Anything you want us to know (optional)"></textarea></p>
      <p><button type="submit">Send</button></p>
    </form>`));
}

async function handleManageSubmit(req: Request, env: Env, token: string): Promise<Response> {
  const interview = await manageInterview(env, token);
  if (!interview) return html(page("Link not found", "<p>This link has expired.</p>"), 404);
  const form = await req.formData().catch(() => null);
  const action = String(form?.get("action") ?? "");
  const note = String(form?.get("note") ?? "").slice(0, 1000);
  const apps = await sb(env, "GET",
    `guest_applications?id=eq.${interview.application_id}&limit=1`);
  const app = apps?.[0] ?? {};
  const show = showFor(interview, app);
  const booking = env.CALCOM_BOOKING_URL || "";
  const now = new Date().toISOString();

  if (action === "cancel") {
    await sb(env, "PATCH", `interviews?id=eq.${interview.id}`,
      { status: "cancelled", cancelled_at: now, cancel_reason: note || null });
    await slack(env, `${app.name ?? "A guest"} cancelled their ${show.shortLabel} interview` +
      (note ? `: ${note}` : ""));
    await email(env, operatorEmail(env),
      `${show.shortLabel}: ${app.name ?? "a guest"} cancelled`,
      `<p>${esc(app.name ?? "A guest")} cancelled their interview` +
      `${interview.scheduled_at ? ` (was ${esc(new Date(interview.scheduled_at).toUTCString())})` : ""}.</p>` +
      (note ? `<p>They said: ${esc(note)}</p>` : "<p>No reason given.</p>"));
    return html(page("Cancelled", `
      <p>Done — nobody is waiting for you, and Mira will not call.</p>
      ${booking ? `<p>If you want to come back to it later: <a href="${esc(booking)}">book a new time</a>.</p>` : ""}
      <p>Thank you for telling us. It genuinely helps.</p>`));
  }

  await sb(env, "PATCH", `interviews?id=eq.${interview.id}`,
    { status: "cancelled", cancelled_at: now,
      cancel_reason: `reschedule requested${note ? `: ${note}` : ""}`,
      reschedule_requested_at: now });
  await slack(env, `${app.name ?? "A guest"} wants to move their ${show.shortLabel} interview` +
    (note ? `: ${note}` : ""));
  return html(page("Let's find another time", `
    <p>No problem at all — the old slot is released.</p>
    ${booking ? `<p><a href="${esc(booking)}">Pick a new time here</a>.</p>`
              : "<p>We will email you some options.</p>"}
    ${note ? "<p>Thanks for the note — we have passed it on.</p>" : ""}`));
}

async function handleGuestReviewPage(env: Env, token: string): Promise<Response> {
  const pkg = await pkgByToken(env, token);
  if (!pkg) return html("<h1>Link not found</h1>", 404);
  if (["approved_by_guest", "published"].includes(pkg.status)) {
    return html("<h1>Already approved — thank you!</h1>");
  }
  const { show } = await interviewWithApp(env, pkg.interview_id);
  // A failed cleaning pass stores "" rather than null, so "??" happily
  // rendered the empty string and John Capobianco's review page went out
  // with no transcript on it at all (Sept 15 2026). Fall back on anything
  // truthy: the raw diarized transcript is readable and it is the same
  // conversation.
  // The guest reviewed a transcript and never heard a word of it until
  // publication (Sept 10 2026). They approve the audio too, so give them
  // the audio: the same mixed recording Patrick listens to at gate 1.
  const run = (await sb(env, "GET",
    `interview_runs?id=eq.${pkg.interview_run_id}&select=recording_mixed_url,grok_session_log`))?.[0] ?? {};
  const listenUrl = reviewAudioUrl(run);
  return html(`<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Review your ${esc(show.shortLabel)} conversation</title>
<style>body{font:16px/1.6 system-ui;max-width:760px;margin:2rem auto;padding:0 1rem;color:#1a202c}
pre{white-space:pre-wrap;background:#f7fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;max-height:60vh;overflow:auto}
textarea{width:100%;min-height:90px}button{background:${show.brandColor};color:#fff;border:0;border-radius:8px;padding:.7rem 1.4rem;font-size:1rem;cursor:pointer;margin-right:.6rem}
.secondary{background:#4a5568}</style>
<h1>Your ${esc(show.shortLabel)} conversation</h1>
<p>Here is the recording and the transcript — this is what would publish.
Have a listen, then approve it as-is, or tell us what to remove: quote the
passage(s) and we'll cut them from both the audio and the transcript before
anything goes out.</p>
${listenUrl
  ? `<audio controls preload="none" src="${esc(listenUrl)}" style="width:100%;margin:1rem 0"></audio>`
  : `<p><em>The audio is still being processed — the transcript below is final. Check back shortly, or approve on the transcript alone.</em></p>`}
<h3>Transcript</h3>
<pre>${esc((pkg.transcript_cleaned || "").trim() || (pkg.transcript_raw || "").trim())}</pre>
<h3>Request removals (optional)</h3>
<textarea id="redactions" placeholder="Quote any passage you'd like removed, one per line, with a word on why if you like."></textarea>
<p>
<span id="actions">
<button id="approveBtn" onclick="submitReview(true)">Approve for publication</button>
<button id="removeBtn" class="secondary" onclick="submitReview(false)">Submit removal requests</button>
</span>
<span id="done" style="display:none;font-weight:600;color:#166534"></span>
</p>
<h3>Your episode's post</h3>
<p>When this publishes we write a full post for it. Anything you'd like a
listener to find next goes in — a short biography in your own words, your
book or site, papers, talks, the project you were describing. Paste it here
and we'll link it.</p>
<textarea id="materials" placeholder="A short bio, links to your work, papers or talks worth reading next — anything you'd like in the post."></textarea>
<h3>Before you go</h3>
<p>Two things we'd rather offer than have you feel stuck with:</p>
<p>
<label><input type="radio" name="followup" value="return_6"> Come back in about six months and tell us what changed</label><br>
<label><input type="radio" name="followup" value="return_12"> Come back in about a year</label><br>
<label><input type="radio" name="followup" value="return_other"> I'd like to come back, but at a different time</label><br>
<label><input type="radio" name="followup" value="redo"> I'd rather record this conversation again from scratch</label><br>
<label><input type="radio" name="followup" value="none" checked> Nothing for now</label>
</p>
<textarea id="followupNote" placeholder="Anything you'd like us to know — a better time, what you'd want to talk about, or what you'd do differently in a re-record."></textarea>
<p id="status"></p>
<script>
// Sept 17 2026, Dr. Wolfberg: he pressed Approve, the request went through,
// and the only acknowledgement was a line at the very bottom of a long page
// he never scrolled to. The answer now appears where the button was.
async function submitReview(approve){
  const picked = document.querySelector('input[name=followup]:checked');
  const approveBtn = document.getElementById('approveBtn');
  const removeBtn = document.getElementById('removeBtn');
  approveBtn.disabled = removeBtn.disabled = true;
  (approve ? approveBtn : removeBtn).textContent = 'Sending\u2026';
  let ok = false;
  try {
    const resp = await fetch(location.pathname, {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({approve, redactions: document.getElementById('redactions').value,
        followup: picked ? picked.value : 'none',
        followup_note: document.getElementById('followupNote').value,
        materials: document.getElementById('materials').value})});
    ok = resp.ok;
  } catch (e) { ok = false; }
  const msg = ok
    ? (approve ? 'Approved \u2014 thank you! Your episode is on its way.' : 'Received \u2014 we will apply the removals and confirm by email.')
    : 'Something went wrong \u2014 please reply to our email instead.';
  document.getElementById('status').textContent = msg;
  const done = document.getElementById('done');
  done.textContent = msg;
  done.style.color = ok ? '#166534' : '#991B1B';
  done.style.display = 'inline';
  if (ok) {
    document.getElementById('actions').style.display = 'none';
  } else {
    approveBtn.disabled = removeBtn.disabled = false;
    approveBtn.textContent = 'Approve for publication';
    removeBtn.textContent = 'Submit removal requests';
  }
  done.scrollIntoView({block: 'center', behavior: 'smooth'});
}
</script>`);
}

async function handleGuestReviewSubmit(req: Request, env: Env, token: string): Promise<Response> {
  const pkg = await pkgByToken(env, token);
  if (!pkg) return json({ error: "not found" }, 404);
  const body = await req.json<any>().catch(() => ({}));
  const now = new Date().toISOString();
  const { interview, app, show } = await interviewWithApp(env, pkg.interview_id);

  // A guest who would come back, or who would rather do it again, is worth
  // more than a guest who merely approved (Sept 13 2026). Recorded here so
  // it becomes a scheduled conversation rather than a good intention.
  // Whatever they want in their episode's post. Kept even when they ask for
  // removals or a re-record: the links are still the links.
  const materials = String(body?.materials ?? "").slice(0, 4000).trim();
  if (materials) {
    await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`,
      { guest_materials: materials });
    await slack(env, `${show.shortLabel}: ${app?.name ?? "guest"} sent materials for the episode post (${materials.length} chars).`);
  }

  const followup = String(body?.followup ?? "none");
  if (followup !== "none") {
    const months = followup === "return_6" ? 6 : followup === "return_12" ? 12 : 0;
    const due = months
      ? new Date(Date.now() + months * 30 * 864e5).toISOString() : null;
    await sb(env, "POST", "guest_return_requests", {
      interview_id: pkg.interview_id,
      application_id: interview?.application_id ?? null,
      show: show.slug,
      kind: followup === "redo" ? "redo" : "return",
      horizon: followup === "return_6" ? "6_months"
        : followup === "return_12" ? "12_months" : "other",
      note: String(body?.followup_note ?? "").slice(0, 1000) || null,
      due_at: due,
    });
    await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`,
      { guest_followup: followup, guest_followup_at: now });
    await slack(env, `${show.shortLabel}: ${app?.name ?? "guest"} chose "${followup}"` +
      (body?.followup_note ? ` — ${String(body.followup_note).slice(0, 300)}` : ""));
  }

  if (body.approve) {
    await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`,
      { status: "approved_by_guest", guest_reviewed_at: now });
    await sb(env, "PATCH", `interviews?id=eq.${pkg.interview_id}`, { status: "approved" });
    await dispatch(env, "interview-approved-by-guest", { interview_id: pkg.interview_id });
    await slack(env, `${show.shortLabel}: guest APPROVED package ${pkg.id} — production dispatched`);
  } else {
    const requests = String(body.redactions ?? "").trim();
    await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`, {
      guest_reviewed_at: now,
      guest_redactions: [{ note: requests, resolved: false }],
      status: "in_review",
    });
    await slack(env, `${show.shortLabel}: guest requested removals on package ${pkg.id} — needs Patrick:\n${requests.slice(0, 500)}`);
  }
  return json({ ok: true });
}

// -- Admin UIs (lean, token-gated) ------------------------------------------

async function handleAdminTriage(req: Request, env: Env): Promise<Response> {
  const denied = requireAdmin(req, env);
  if (denied) return denied;
  const apps = await sb(env, "GET",
    "guest_applications?status=eq.pending&order=created_at.asc&limit=100");
  const all: any[] = apps ?? [];
  const provenance = (a: any) => {
    const bits: string[] = [];
    if (a.source && a.source !== "form") bits.push(`source: ${esc(String(a.source))}`);
    if (a.pitched_show) bits.push(`pitched for: ${esc(String(a.pitched_show))}`);
    if (a.publicist_name || a.publicist_email) {
      bits.push(`publicist: ${esc(String(a.publicist_name ?? ""))}${a.publicist_email ? ` &lt;${esc(String(a.publicist_email))}&gt;` : ""}`);
    }
    if (a.pitch_summary) bits.push(`pitch: ${esc(String(a.pitch_summary)).slice(0, 300)}`);
    return bits.length ? `<br><small class="prov">${bits.join(" · ")}</small>` : "";
  };
  const reassignOptions = (current: ShowSlug) => Object.values(SHOWS)
    .filter((s) => s.slug !== current)
    .map((s) => `<option value="${s.slug}">${esc(s.name)}</option>`).join("");
  // Sept 18 2026: what the screen found, beside the Approve button. Rhett
  // Mikols was approved from a bio and a topic list; this is the paragraph
  // that would have said there was nothing behind them.
  const screenHtml = (a: any) => {
    const sc = a.screen;
    if (!sc?.verdict) return `<br><small class="prov">not yet screened</small>`;
    const colour = sc.verdict === "strong" ? "#166534" : sc.verdict === "thin" ? "#991B1B" : "#92400E";
    const list = (items: any, label: string) => Array.isArray(items) && items.length
      ? `<br><small><b>${label}:</b> ${items.map((x: any) => esc(String(x))).join(" · ")}</small>` : "";
    return `<br><span style="color:${colour};font-weight:600">screen: ${esc(String(sc.verdict))}</span>
      — ${esc(String(sc.summary ?? ""))}${list(sc.specifics, "found")}${list(sc.concerns, "concerns")}`
      + (sc.ask_first ? `<br><small><b>open with:</b> ${esc(String(sc.ask_first))}</small>` : "");
  };
  const rowHtml = (a: any, show: Show) => `
    <li><b>${esc(a.name)}</b> — ${esc(a.title ?? "")} ${esc(a.organization ?? "")}
      ${a.wants_cohost ? '<small class="prov">· asked for Patrick as co-host</small>' : ""}
      <br><small>${esc((a.topics ?? []).join(", "))}</small>${provenance(a)}
      <br>${esc(a.bio ?? "").slice(0, 500)}${screenHtml(a)}
      <br><button onclick="decide('${a.id}','approved')">Approve</button>
      <button onclick="decide('${a.id}','declined')">Decline</button>
      <span class="move">Move to
        <select id="mv-${a.id}">${reassignOptions(show.slug)}</select>
        <button onclick="reassign('${a.id}')">Reassign</button></span></li>`;
  const sections = (Object.values(SHOWS) as Show[]).map((show) => {
    const mine = all.filter((a) => showFor(a).slug === show.slug);
    return `<h2 style="border-left:6px solid ${show.brandColor};padding-left:.6rem">${esc(show.name)}
      <small>(${mine.length})</small></h2>
      <ul>${mine.map((a) => rowHtml(a, show)).join("") || "<i>none</i>"}</ul>`;
  }).join("");
  return html(`<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">
<title>Guest triage — Nerra Network</title>
<style>body{font:15px/1.5 system-ui;max-width:800px;margin:2rem auto;padding:0 1rem}li{margin-bottom:1.4rem}
.prov{color:#4a5568}.move{margin-left:.8rem;font-size:.9rem;color:#4a5568}</style>
<h1>Pending applications (${all.length})</h1>${sections}
<script>
const token = new URL(location).searchParams.get('token');
async function decide(id, decision){
  await fetch('/voices/triage-decision?token='+token, {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({application_id:id, decision})});
  location.reload();
}
async function reassign(id){
  const show = document.getElementById('mv-'+id).value;
  await fetch('/voices/triage-reassign?token='+token, {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({application_id:id, show})});
  location.reload();
}
</script>`);
}

async function handleAdminReview(req: Request, env: Env, id: string): Promise<Response> {
  const denied = await requirePackageAccess(req, env, id);
  if (denied) return denied;
  const rows = await sb(env, "GET", `editorial_packages?id=eq.${id}&limit=1`);
  const pkg = rows?.[0];
  if (!pkg) return html("<h1>Package not found</h1>", 404);
  const run = (await sb(env, "GET", `interview_runs?id=eq.${pkg.interview_run_id}`))[0] ?? {};
  const { app, show } = await interviewWithApp(env, pkg.interview_id);
  // The learning loop's output: what this interview proposes Mira should do
  // differently, and the numbers behind it. Nothing here reaches Mira until
  // it is promoted on this page.
  const proposed = (await sb(env, "GET",
    `show_lessons?interview_id=eq.${pkg.interview_id}&status=eq.proposed&order=created_at.asc`)) ?? [];
  const activeLessons = (await sb(env, "GET",
    `show_lessons?show=eq.${show.slug}&status=eq.active&order=decided_at.desc&limit=12`)) ?? [];
  const metrics = (await sb(env, "GET",
    `episode_metrics?interview_id=eq.${pkg.interview_id}`))?.[0] ?? null;
  const metricLine = metrics
    ? `Guest spoke ${Math.round(Number(metrics.guest_talk_share ?? 0) * 100)}% of the words ·
       Mira took ${metrics.mira_turns ?? "?"} turns${metrics.mira_mean_turn_sec ? ` (avg ${metrics.mira_mean_turn_sec}s apart)` : ""} ·
       ${metrics.repeated_questions ?? 0} repeated question(s) ·
       ${metrics.dead_air_sec ?? 0}s dead air · ${metrics.agent_sessions ?? 1} session(s), ${metrics.drops ?? 0} drop(s)`
    : "not measured";
  const lessonRow = (l: any, kind: "proposed" | "active") => `
    <li style="margin:.5rem 0">
      <b>${esc(String(l.category ?? ""))}</b> — ${esc(String(l.lesson ?? ""))}
      ${l.evidence ? `<br><small style="color:#4a5568">${esc(String(l.evidence))}</small>` : ""}
      ${kind === "proposed"
        ? `<br><button onclick="lesson('${l.id}','active')">Teach Mira this</button>
           <button onclick="lesson('${l.id}','retired')">Discard</button>`
        : `<br><button onclick="lesson('${l.id}','retired')">Stop applying this</button>`}
    </li>`;
  return html(`<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">
<title>${esc(show.shortLabel)} — editorial review</title>
<style>body{font:15px/1.6 system-ui;max-width:860px;margin:2rem auto;padding:0 1rem}
pre{white-space:pre-wrap;background:#f7fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;max-height:50vh;overflow:auto}
textarea{width:100%;min-height:80px}button{padding:.6rem 1.2rem;margin-right:.6rem}
h1{border-left:6px solid ${show.brandColor};padding-left:.6rem}</style>
<h1>${esc(show.name)} — editorial review (gate 1)</h1>
<p>Guest: <b>${esc(app?.name ?? "unknown")}</b> · Status: <b>${esc(pkg.status)}</b>${pkg.audio_quality_flag ? ` · ⚠️ ${esc(pkg.audio_quality_flag)}` : ""}</p>
${reviewAudioUrl(run) ? `<audio controls preload="none" src="${esc(reviewAudioUrl(run)!)}" style="width:100%"></audio>` : ""}
<h3>Episode notes</h3><pre>${esc(pkg.episode_notes ?? "")}</pre>
<h3>Cleaned transcript</h3><pre>${esc(pkg.transcript_cleaned ?? "")}</pre>
<h3>Newsletter draft</h3><pre>${esc(pkg.newsletter_draft ?? "")}</pre>
<h3>How this interview went, by the numbers</h3>
<p>${metricLine}</p>
<h3>What Mira should learn from it</h3>
${proposed.length
  ? `<ul>${proposed.map((l: any) => lessonRow(l, "proposed")).join("")}</ul>`
  : "<p><em>No lessons proposed — the producer's pass found nothing worth changing.</em></p>"}
${activeLessons.length
  ? `<details><summary>Standing instructions Mira is already following (${activeLessons.length})</summary>
     <ul>${activeLessons.map((l: any) => lessonRow(l, "active")).join("")}</ul></details>`
  : ""}
<h3>Decision</h3>
<textarea id="notes" placeholder="Editorial notes (kept on the package, nobody else sees them)"></textarea>
<p>Anything you want said to the guest goes here, and Mira puts it at the top
of the mail she sends them. Leave it empty for the standard note.</p>
<textarea id="to_guest" placeholder="A word to the guest — an apology, a thank-you, what changed since they recorded"></textarea>
<p><button onclick="decide('approve')">Approve → guest review</button>
<button onclick="decide('kill')">Kill episode</button></p>
<p id="status"></p>
<script>
const token = new URL(location).searchParams.get('token');
async function decide(decision){
  const resp = await fetch('/voices/editorial-decision?token='+token, {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({package_id:'${pkg.id}', decision,
      notes: document.getElementById('notes').value,
      note_to_guest: document.getElementById('to_guest').value})});
  document.getElementById('status').textContent = resp.ok ? 'Saved.' : 'Failed — check the token.';
}
async function lesson(id, status){
  const resp = await fetch('/voices/lesson-decision?token='+token, {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({package_id:'${pkg.id}', lesson_id:id, status})});
  document.getElementById('status').textContent = resp.ok
    ? (status === 'active' ? 'Mira will apply that from the next interview.' : 'Dropped.')
    : 'Failed.';
  if (resp.ok) event.target.closest('li').style.opacity = .45;
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
    const { interview, app, show } = await interviewWithApp(env, pkg.interview_id);
    if (!interview || !app) {
      console.error(`gate2: package ${pkg.id} has no interview/application — skipped`);
      continue;
    }
    if (now >= deadline) {
      // Day 7: auto-approve (spec §7) — guest can still request takedown.
      await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`,
        { status: "approved_by_guest", guest_reviewed_at: new Date().toISOString() });
      await sb(env, "PATCH", `interviews?id=eq.${interview.id}`, { status: "approved" });
      await dispatch(env, "interview-approved-by-guest", { interview_id: interview.id });
      await slack(env, `${show.shortLabel}: package ${pkg.id} AUTO-APPROVED (7-day window elapsed)`);
    } else if (deadline - now < 3 * 864e5 && deadline - now > 2 * 864e5) {
      // Day 4 (±cron granularity): one reminder.
      const link = `https://api.nerranetwork.com/voices/review/${pkg.guest_review_token}`;
      await email(env, app.email, `Reminder: your ${show.shortLabel} transcript awaits`,
        `<p>Hi ${esc(app.name)},</p>
         <p>A gentle nudge — your transcript is waiting for review:</p>
         <p><a href="${esc(link)}">${esc(link)}</a></p>
         <p>If we don't hear from you in the next three days we'll take that
         as approval.</p><p>${esc(signOff(show))}</p>`, true);
    }
  }
}

// ---------------------------------------------------------------------------
// WebRTC studio endpoints (July 2026)
// ---------------------------------------------------------------------------

// Compact MD5 (RFC 1321) — WebCrypto has no MD5, and Voximplant's
// one-time-key login hash is MD5(key + "|" + MD5(user + ":voximplant.com:" +
// password)). Verified against Python hashlib before deploy.
function md5(input: string): string {
  const add32 = (a: number, b: number) => (a + b) & 0xffffffff;
  const cmn = (q: number, a: number, b: number, x: number, s: number, t: number) => {
    a = add32(add32(a, q), add32(x, t));
    return add32((a << s) | (a >>> (32 - s)), b);
  };
  const ff = (a: number, b: number, c: number, d: number, x: number, s: number, t: number) => cmn((b & c) | (~b & d), a, b, x, s, t);
  const gg = (a: number, b: number, c: number, d: number, x: number, s: number, t: number) => cmn((b & d) | (c & ~d), a, b, x, s, t);
  const hh = (a: number, b: number, c: number, d: number, x: number, s: number, t: number) => cmn(b ^ c ^ d, a, b, x, s, t);
  const ii = (a: number, b: number, c: number, d: number, x: number, s: number, t: number) => cmn(c ^ (b | ~d), a, b, x, s, t);
  function md5cycle(x: number[], k: number[]) {
    let a = x[0], b = x[1], c = x[2], d = x[3];
    a = ff(a, b, c, d, k[0], 7, -680876936); d = ff(d, a, b, c, k[1], 12, -389564586);
    c = ff(c, d, a, b, k[2], 17, 606105819); b = ff(b, c, d, a, k[3], 22, -1044525330);
    a = ff(a, b, c, d, k[4], 7, -176418897); d = ff(d, a, b, c, k[5], 12, 1200080426);
    c = ff(c, d, a, b, k[6], 17, -1473231341); b = ff(b, c, d, a, k[7], 22, -45705983);
    a = ff(a, b, c, d, k[8], 7, 1770035416); d = ff(d, a, b, c, k[9], 12, -1958414417);
    c = ff(c, d, a, b, k[10], 17, -42063); b = ff(b, c, d, a, k[11], 22, -1990404162);
    a = ff(a, b, c, d, k[12], 7, 1804603682); d = ff(d, a, b, c, k[13], 12, -40341101);
    c = ff(c, d, a, b, k[14], 17, -1502002290); b = ff(b, c, d, a, k[15], 22, 1236535329);
    a = gg(a, b, c, d, k[1], 5, -165796510); d = gg(d, a, b, c, k[6], 9, -1069501632);
    c = gg(c, d, a, b, k[11], 14, 643717713); b = gg(b, c, d, a, k[0], 20, -373897302);
    a = gg(a, b, c, d, k[5], 5, -701558691); d = gg(d, a, b, c, k[10], 9, 38016083);
    c = gg(c, d, a, b, k[15], 14, -660478335); b = gg(b, c, d, a, k[4], 20, -405537848);
    a = gg(a, b, c, d, k[9], 5, 568446438); d = gg(d, a, b, c, k[14], 9, -1019803690);
    c = gg(c, d, a, b, k[3], 14, -187363961); b = gg(b, c, d, a, k[8], 20, 1163531501);
    a = gg(a, b, c, d, k[13], 5, -1444681467); d = gg(d, a, b, c, k[2], 9, -51403784);
    c = gg(c, d, a, b, k[7], 14, 1735328473); b = gg(b, c, d, a, k[12], 20, -1926607734);
    a = hh(a, b, c, d, k[5], 4, -378558); d = hh(d, a, b, c, k[8], 11, -2022574463);
    c = hh(c, d, a, b, k[11], 16, 1839030562); b = hh(b, c, d, a, k[14], 23, -35309556);
    a = hh(a, b, c, d, k[1], 4, -1530992060); d = hh(d, a, b, c, k[4], 11, 1272893353);
    c = hh(c, d, a, b, k[7], 16, -155497632); b = hh(b, c, d, a, k[10], 23, -1094730640);
    a = hh(a, b, c, d, k[13], 4, 681279174); d = hh(d, a, b, c, k[0], 11, -358537222);
    c = hh(c, d, a, b, k[3], 16, -722521979); b = hh(b, c, d, a, k[6], 23, 76029189);
    a = hh(a, b, c, d, k[9], 4, -640364487); d = hh(d, a, b, c, k[12], 11, -421815835);
    c = hh(c, d, a, b, k[15], 16, 530742520); b = hh(b, c, d, a, k[2], 23, -995338651);
    a = ii(a, b, c, d, k[0], 6, -198630844); d = ii(d, a, b, c, k[7], 10, 1126891415);
    c = ii(c, d, a, b, k[14], 15, -1416354905); b = ii(b, c, d, a, k[5], 21, -57434055);
    a = ii(a, b, c, d, k[12], 6, 1700485571); d = ii(d, a, b, c, k[3], 10, -1894986606);
    c = ii(c, d, a, b, k[10], 15, -1051523); b = ii(b, c, d, a, k[1], 21, -2054922799);
    a = ii(a, b, c, d, k[8], 6, 1873313359); d = ii(d, a, b, c, k[15], 10, -30611744);
    c = ii(c, d, a, b, k[6], 15, -1560198380); b = ii(b, c, d, a, k[13], 21, 1309151649);
    a = ii(a, b, c, d, k[4], 6, -145523070); d = ii(d, a, b, c, k[11], 10, -1120210379);
    c = ii(c, d, a, b, k[2], 15, 718787259); b = ii(b, c, d, a, k[9], 21, -343485551);
    x[0] = add32(a, x[0]); x[1] = add32(b, x[1]); x[2] = add32(c, x[2]); x[3] = add32(d, x[3]);
  }
  const bytes = new TextEncoder().encode(input);
  const n = bytes.length;
  const state = [1732584193, -271733879, -1732584194, 271733878];
  let i = 0;
  for (; i + 64 <= n; i += 64) {
    const k = new Array(16).fill(0);
    for (let j = 0; j < 64; j++) k[j >> 2] |= bytes[i + j] << ((j % 4) << 3);
    md5cycle(state, k);
  }
  const tail = new Array(16).fill(0);
  for (let j = 0; i + j < n; j++) tail[j >> 2] |= bytes[i + j] << ((j % 4) << 3);
  tail[(n - i) >> 2] |= 0x80 << (((n - i) % 4) << 3);
  if (n - i > 55) { md5cycle(state, tail); tail.fill(0); }
  tail[14] = n * 8;
  md5cycle(state, tail);
  let out = "";
  for (const word of state)
    for (let j = 0; j < 4; j++)
      out += ((word >> (j * 8 + 4)) & 0xf).toString(16) + ((word >> (j * 8)) & 0xf).toString(16);
  return out;
}

const UUID_RE = /^[0-9a-f-]{36}$/;
const isStudioRole = (r: unknown): r is StudioRole => r === "guest" || r === "host";

/** Admin token from the Authorization header, `?token=` or a JSON body. */
function adminTokenOk(env: Env, req: Request, bodyToken?: unknown): boolean {
  const auth = (req.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "");
  const q = new URL(req.url).searchParams.get("token") ?? "";
  const t = (auth || q || (typeof bodyToken === "string" ? bodyToken : "")).trim();
  // Trim both sides: a secret pasted with a trailing newline (wrangler
  // secret put via a pipe, or GitHub's secret box) must not turn every
  // host link into "unauthorized" (Patrick, Sept 9 2026, 08:28).
  const expected = (env.ADMIN_TOKEN || "").trim();
  return expected.length > 0 && t === expected;
}

// GET /voices/studio-state?interview=<id>&show=&role=[&token=] — the studio
// page polls this until the fire step has created the run row (webrtc mode
// leaves it `awaiting_guest`), then joins with the returned run_id. Phase 2:
// both pages keep polling during the call for presence — `guest_joined` /
// `host_joined` come from the interview_runs columns that /voices/leg-event
// and the interview-complete webhook maintain. `host_user` (the Voximplant
// user the scenario dials) is only revealed to a host presenting ADMIN_TOKEN.
/** The studio's pre-join headphone check, reported for the record.
 *
 *  Sept 21 2026: a guest whose microphone can hear their speakers records
 *  Mira's voice into their own track, and from there into the transcript as
 *  words they never said. Knowing before the interview beats finding out from
 *  the tape, so the verdict is stored and a bad one is said out loud. It is
 *  advisory in every direction: nobody is stopped from joining, and a failure
 *  here never costs the interview.
 */
async function handleStudioEcho(req: Request, env: Env): Promise<Response> {
  const body = await req.json<any>().catch(() => null);
  const verdict = String(body?.verdict ?? "").trim();
  if (!["clean", "borderline", "speakers", "unknown"].includes(verdict)) {
    return json({ error: "verdict must be clean|borderline|speakers|unknown" }, 400);
  }
  const role = String(body?.role ?? "guest").trim() || "guest";
  const runId = String(body?.run_id ?? "").trim();
  const interviewId = String(body?.interview ?? "").trim();
  const record = { verdict, role, at: new Date().toISOString() };
  if (runId) {
    await sb(env, "PATCH", `interview_runs?id=eq.${runId}`, { echo_check: record })
      .catch(() => null);
  }
  if (verdict === "speakers" || verdict === "borderline") {
    let who = role;
    if (interviewId) {
      const rows = await sb(env, "GET",
        `interviews?id=eq.${interviewId}&select=application_id`).catch(() => null);
      const appId = rows?.[0]?.application_id;
      if (appId) {
        const apps = await sb(env, "GET",
          `guest_applications?id=eq.${appId}&select=name,show`).catch(() => null);
        if (apps?.[0]?.name) who = `${apps[0].name} (${role})`;
      }
    }
    await slack(env, `:headphones: studio echo check: ${who} is on speakers` +
      (verdict === "borderline" ? " (faint)" : "") +
      " — their microphone will carry Mira's voice into the recording.");
  }
  return json({ ok: true, verdict });
}

async function handleStudioState(req: Request, env: Env): Promise<Response> {
  const url = new URL(req.url);
  const interviewId = url.searchParams.get("interview") ?? "";
  const role: StudioRole = url.searchParams.get("role") === "host" ? "host" : "guest";
  if (!UUID_RE.test(interviewId)) return json({ error: "interview required" }, 400);
  const ivs = await sb(env, "GET",
    `interviews?id=eq.${interviewId}&select=id,status,scheduled_at,call_mode,show,application_id,host_mode`);
  const iv = ivs?.[0];
  if (!iv) return json({ error: "not found" }, 404);
  // Pre-migration interviews carry no show; fall back to the application's.
  let show = showFor(iv);
  if (!isShow(iv.show) && iv.application_id) {
    const apps = await sb(env, "GET",
      `guest_applications?id=eq.${iv.application_id}&select=show`);
    show = showFor(apps?.[0]);
  }
  // The room model (Sept 9 2026): anyone — guest, co-host, a second guest,
  // someone rejoining after a drop — may join while the newest run is
  // awaiting_guest or in_progress. The run row IS the unlocked studio.
  const latestRows = await sb(env, "GET",
    `interview_runs?interview_id=eq.${interviewId}&order=created_at.desc&limit=1` +
    `&select=id,status,host_mode,guest_joined_at,host_joined_at,host_left_at`);
  const latest = latestRows?.[0] ?? null;
  const run = latest && JOINABLE_RUN_STATUSES.has(String(latest.status)) ? latest : null;
  const hostMode = latest ? latest.host_mode !== false : iv.host_mode !== false;
  return json({
    ready: Boolean(run),
    run_id: run?.id ?? null,
    // The host page must know the run even after the guest has joined
    // (status in_progress) so its local-recording uploads carry the id.
    live_run_id: latest?.id ?? null,
    run_status: latest?.status ?? null,
    interview_status: iv.status,
    scheduled_at: iv.scheduled_at,
    call_mode: iv.call_mode ?? "webrtc",
    show: show.slug,
    show_name: show.name,
    role,
    host_mode: hostMode,
    guest_joined: Boolean(latest?.guest_joined_at),
    host_joined: Boolean(latest?.host_joined_at) && !latest?.host_left_at,
  });
}

const JOINABLE_RUN_STATUSES = new Set(["awaiting_guest", "pending", "in_progress"]);

// POST /voices/studio-auth {key, role?} — Voximplant one-time-key
// handshake: hash = MD5(key + "|" + MD5(user + ":voximplant.com:" + password)).
// Since the room model (Sept 9 2026) EVERY role signs in as the shared
// `guest` studio user — the co-host included, no token. The role travels
// in the call's X-Role header instead; the interview id in the link is
// the only thing that admits anyone, exactly as for guests.
// Studio user passwords are DERIVED, never stored (Sept 9 2026, Dan
// Perra live: a hand-typed VOX_GUEST_PASSWORD did not match the
// Voximplant user and every browser join hung). Both this Worker and the
// deploy workflow (voximplant_client.derive_studio_password) compute
// hex(HMAC_SHA256(ADMIN_TOKEN, "nerra-studio:" + user))[:32] + "Aa1";
// the workflow pushes it onto the users with SetUserInfo. VOX_*_PASSWORD
// secrets are no longer read.
// Studio user NAMES are trimmed and sanitised too (Sept 9 2026, second
// rehearsal): a VOX_HOST_USER secret pasted with a trailing newline made
// the host page ask Voximplant for a key for "host\n@app", which never
// answers, while the same request for "host" answers in 200 ms.
function studioUser(env: Env, role: "guest" | "host"): string {
  const raw = role === "host" ? env.VOX_HOST_USER : env.VOX_GUEST_USER;
  const clean = String(raw || "").trim().replace(/[^A-Za-z0-9_.-]/g, "");
  return clean || role;
}

async function studioPassword(env: Env, user: string): Promise<string> {
  const token = (env.ADMIN_TOKEN || "").trim();
  if (!token) throw new Error("ADMIN_TOKEN required to derive studio passwords");
  const enc = new TextEncoder();
  const cryptoKey = await crypto.subtle.importKey(
    "raw", enc.encode(token), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", cryptoKey, enc.encode(`nerra-studio:${user}`));
  const hex = Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
  return hex.slice(0, 32) + "Aa1";
}

async function handleStudioAuth(req: Request, env: Env): Promise<Response> {
  const body = await req.json<any>().catch(() => null);
  const key = String(body?.key ?? "");
  if (!key) return json({ error: "key required" }, 400);
  const role: StudioRole = body?.role === "host" ? "host" : "guest";
  const user = studioUser(env, "guest");
  if (!env.ADMIN_TOKEN) return json({ error: "studio auth not configured (ADMIN_TOKEN)" }, 503);
  const password = await studioPassword(env, user);
  const token = md5(`${key}|${md5(`${user}:voximplant.com:${password}`)}`);
  return json({ token, user, role });
}

// ---------------------------------------------------------------------------
// Phase 2 co-host endpoints (Sept 2026, docs/cohost_phase2_contract.md)
// ---------------------------------------------------------------------------

// POST /voices/leg-event {run_id, role, event:"joined"|"left"} — the scenario
// reports each leg's Connected/Disconnected (fire-and-forget on its side).
// No auth beyond the run existing: the payload carries nothing sensitive
// and only moves presence timestamps. First join only for *_joined_at; a
// host rejoin after a drop clears host_left_at so `host_joined` is live
// again (the webhook writes the final host_left_at at hangup). Attempts
// are NOT counted here — the scenario reports host_attempts in the webhook.
// Room model (Sept 9 2026): each PARTICIPANT session also posts "left"
// with its own recording URLs (record_url = that person's stereo
// Call.record, video_url = the guest camera recorder); those land on the
// run row here — recording_guest_url / recording_host_url and
// grok_session_log.voximplant_record_url / voximplant_video_url, which
// post_interview.py reads — because the room session that fires the
// completion webhook never sees them.
async function handleLegEvent(req: Request, env: Env): Promise<Response> {
  const body = await req.json<any>().catch(() => null);
  const runId = String(body?.run_id ?? "");
  const role = body?.role, event = body?.event;
  if (!UUID_RE.test(runId) || !(isStudioRole(role) || role === "probe") || !["joined", "left"].includes(event)) {
    return json({ error: "run_id + role(guest|host|probe) + event(joined|left) required" }, 400);
  }
  const runs = await sb(env, "GET",
    `interview_runs?id=eq.${runId}&select=id,guest_joined_at,host_joined_at,host_left_at,` +
    `recording_guest_url,recording_host_url,grok_session_log`);
  const run = runs?.[0];
  if (!run) return json({ error: "run not found" }, 404);
  if (role === "probe") {
    // Diagnostics: the synthetic participant's room-leg recording.
    if (typeof body?.record_url === "string" && body.record_url) {
      await sb(env, "PATCH", `interview_runs?id=eq.${runId}`,
        { grok_session_log: { ...(run.grok_session_log ?? {}), probe_record_url: body.record_url } });
    }
    return json({ ok: true, run_id: runId, role, event });
  }
  const now = new Date().toISOString();
  const patch: Record<string, unknown> = {};
  if (role === "guest" && event === "joined" && !run.guest_joined_at) patch.guest_joined_at = now;
  if (role === "host" && event === "joined") {
    if (!run.host_joined_at) patch.host_joined_at = now;
    if (run.host_left_at) patch.host_left_at = null;
  }
  if (role === "host" && event === "left") patch.host_left_at = now;
  const recordUrl = typeof body?.record_url === "string" && body.record_url ? body.record_url : null;
  const videoUrl = typeof body?.video_url === "string" && body.video_url ? body.video_url : null;
  if (event === "left" && (recordUrl || videoUrl)) {
    if (role === "host" && recordUrl) {
      // Sept 12 2026: this took the LAST host leg, so a ten-second rejoin at
      // the end of the Hogan Shrum episode overwrote the forty-minute leg it
      // was recorded on. Same rule as the guest now: first leg wins the
      // primary track, later ones are kept rather than thrown away.
      const log = { ...(run.grok_session_log ?? {}) };
      if (!run.recording_host_url) {
        patch.recording_host_url = recordUrl;
      } else {
        log.extra_host_record_urls = [...(log.extra_host_record_urls ?? []), recordUrl];
        patch.grok_session_log = log;
      }
    }
    if (role === "guest") {
      // First guest wins the primary track; extra guests are kept in the log.
      const log = { ...(run.grok_session_log ?? {}) };
      if (recordUrl && !run.recording_guest_url && !log.voximplant_record_url) {
        patch.recording_guest_url = recordUrl;
        log.voximplant_record_url = recordUrl;
      } else if (recordUrl) {
        log.extra_guest_record_urls = [...(log.extra_guest_record_urls ?? []), recordUrl];
      }
      if (videoUrl && !log.voximplant_video_url) log.voximplant_video_url = videoUrl;
      patch.grok_session_log = log;
    }
  }
  if (Object.keys(patch).length) await sb(env, "PATCH", `interview_runs?id=eq.${runId}`, patch);
  return json({ ok: true, run_id: runId, role, event, patched: Object.keys(patch) });
}

const LOCAL_CHUNK_MAX_BYTES = 10 * 1024 * 1024;
// Guest uploads are allowed while the run is live — `completed` included,
// because the last chunks (and upload-done) arrive AFTER the hangup webhook.
const GUEST_UPLOAD_STATUSES = new Set(["fired", "in_progress", "awaiting_guest", "completed"]);

/** Run + resolved show for the local-recording endpoints. */
async function runWithShow(env: Env, runId: string):
    Promise<{ run: any | null; show: Show }> {
  const runs = await sb(env, "GET",
    `interview_runs?id=eq.${runId}&select=id,status,interview_id,local_guest_url,local_host_url`);
  const run = runs?.[0] ?? null;
  if (!run) return { run: null, show: SHOWS[DEFAULT_SHOW] };
  const ivs = run.interview_id
    ? await sb(env, "GET", `interviews?id=eq.${run.interview_id}&select=show,application_id`)
    : [];
  let show = showFor(ivs?.[0]);
  if (ivs?.[0] && !isShow(ivs[0].show) && ivs[0].application_id) {
    const apps = await sb(env, "GET",
      `guest_applications?id=eq.${ivs[0].application_id}&select=show`);
    show = showFor(apps?.[0]);
  }
  return { run, show };
}

/** `sid` is the per-join take id the studio page mints each time it starts
 *  recording (Sept 10 2026). Without it a rejoin rewrote 00000.webm onwards
 *  and the earlier take was gone. Old clients send none; those keep the flat
 *  layout so their manifests still resolve. */
function localKey(show: Show, runId: string, role: StudioRole, name: string,
                  sid?: string | null): string {
  const take = sid ? `${sid}/` : "";
  return `${show.r2Prefix}/local/${runId}/${role}/${take}${name}`;
}

const SID_RE = /^[A-Za-z0-9_-]{1,32}$/;
const cleanSid = (raw: unknown): string | null => {
  const s = String(raw ?? "");
  return SID_RE.test(s) ? s : null;
};

/** Shared gate for upload-chunk / upload-done: run must exist and be in a
 *  live-ish status. Since the room model (Sept 9 2026) the host is a
 *  participant like any other — no token; the run id admits the upload. */
async function localUploadGate(req: Request, env: Env, runId: string, role: unknown,
                               bodyToken?: unknown):
    Promise<Response | { run: any; show: Show; role: StudioRole }> {
  if (!env.VOICES_R2) return json({ error: "VOICES_R2 binding not configured" }, 503);
  if (!UUID_RE.test(runId) || !isStudioRole(role)) {
    return json({ error: "run_id + role(guest|host) required" }, 400);
  }
  void bodyToken; // kept for callers; the token is no longer required
  const { run, show } = await runWithShow(env, runId);
  if (!run) return json({ error: "run not found" }, 404);
  if (!GUEST_UPLOAD_STATUSES.has(String(run.status))) {
    return json({ error: `run status ${run.status} does not accept uploads` }, 409);
  }
  return { run, show, role };
}

// POST /voices/upload-chunk?run_id=&role=&seq=[&token=] — body: raw
// audio/webm bytes from the studio page's MediaRecorder (5 s timeslices,
// opus 192 kbps), max 10 MB. Key <prefix>/local/<run>/<role>/<seq:05d>.webm.
async function handleUploadChunk(req: Request, env: Env): Promise<Response> {
  const url = new URL(req.url);
  const runId = url.searchParams.get("run_id") ?? "";
  const role = url.searchParams.get("role");
  const seq = Number(url.searchParams.get("seq"));
  if (!Number.isInteger(seq) || seq < 0 || seq > 99999) return json({ error: "seq required (0..99999)" }, 400);
  const sid = cleanSid(url.searchParams.get("sid"));
  const gate = await localUploadGate(req, env, runId, role);
  if (gate instanceof Response) return gate;
  const declared = Number(req.headers.get("Content-Length") ?? 0);
  if (declared > LOCAL_CHUNK_MAX_BYTES) return json({ error: "chunk too large (10 MB max)" }, 413);
  const body = await req.arrayBuffer();
  if (body.byteLength === 0) return json({ error: "empty chunk" }, 400);
  if (body.byteLength > LOCAL_CHUNK_MAX_BYTES) return json({ error: "chunk too large (10 MB max)" }, 413);
  const contentType = (req.headers.get("Content-Type") || "audio/webm").split(";")[0].trim() || "audio/webm";
  const key = localKey(gate.show, runId, gate.role, `${String(seq).padStart(5, "0")}.webm`, sid);
  await env.VOICES_R2.put(key, body, { httpMetadata: { contentType } });
  return json({ ok: true, key, size: body.byteLength });
}

// POST /voices/upload-done {run_id, role, chunks, mime, started_at,
// duration_ms, token?} — writes the manifest the post-interview pipeline
// reads (pipelines/voices/audio/local_tracks.py) and points
// interview_runs.local_<role>_url at its KEY (not a URL: the Python side
// reads R2 with its own credentials). Every listed chunk is HEADed; gaps
// are reported in `missing` and recorded in the manifest so the pipeline
// can decide to fall back to the Voximplant track.
async function handleUploadDone(req: Request, env: Env): Promise<Response> {
  const body = await req.json<any>().catch(() => null);
  const runId = String(body?.run_id ?? "");
  const gate = await localUploadGate(req, env, runId, body?.role, body?.token);
  if (gate instanceof Response) return gate;
  const chunks = Number(body?.chunks);
  if (!Number.isInteger(chunks) || chunks < 0 || chunks > 100000) return json({ error: "chunks (int) required" }, 400);
  const sid = cleanSid(body?.sid);
  const keys: string[] = [];
  for (let i = 0; i < chunks; i++) keys.push(localKey(gate.show, runId, gate.role, `${String(i).padStart(5, "0")}.webm`, sid));
  const missing: string[] = [];
  let bytes = 0;
  for (const key of keys) {
    const head = await env.VOICES_R2.head(key);
    if (!head) missing.push(key); else bytes += head.size;
  }
  const manifestKey = localKey(gate.show, runId, gate.role, "manifest.json", sid);
  const manifest = {
    run_id: runId,
    role: gate.role,
    show: gate.show.slug,
    sid,
    mime: String(body?.mime ?? "audio/webm;codecs=opus"),
    started_at: body?.started_at ?? null,
    duration_ms: Number(body?.duration_ms ?? 0) || 0,
    completed_at: new Date().toISOString(),
    chunks: keys,
    missing,
    bytes,
  };
  await env.VOICES_R2.put(manifestKey, JSON.stringify(manifest, null, 2),
    { httpMetadata: { contentType: "application/json" } });
  // local_<role>_url keeps pointing at the newest take (what the pipeline
  // reads today); every take is also listed so an interview that survived a
  // reconnect can be reassembled from all of them instead of just the last.
  const existing = (await sb(env, "GET",
    `interview_runs?id=eq.${runId}&select=grok_session_log`))?.[0]?.grok_session_log ?? {};
  const takes = { ...(existing.local_takes ?? {}) };
  const forRole: any[] = Array.isArray(takes[gate.role]) ? takes[gate.role] : [];
  if (!forRole.some((t) => t?.manifest === manifestKey)) {
    forRole.push({ manifest: manifestKey, sid, started_at: manifest.started_at,
                   duration_ms: manifest.duration_ms, chunks: keys.length,
                   missing: missing.length });
  }
  takes[gate.role] = forRole;
  await sb(env, "PATCH", `interview_runs?id=eq.${runId}`,
    { [`local_${gate.role}_url`]: manifestKey,
      grok_session_log: { ...existing, local_takes: takes } });
  return json({ ok: true, key: manifestKey, chunks: keys.length, missing, bytes });
}

// GET /voices/host-link?interview=<id> (admin) — Patrick's co-host studio
// link for one interview: the studio page with role=host (no token since
// the room model; the admin check here only guards this lookup endpoint).
async function handleHostLink(req: Request, env: Env): Promise<Response> {
  const denied = requireAdmin(req, env);
  if (denied) return denied;
  const interviewId = new URL(req.url).searchParams.get("interview") ?? "";
  if (!UUID_RE.test(interviewId)) return json({ error: "interview required" }, 400);
  const { interview, show } = await interviewWithApp(env, interviewId);
  if (!interview) return json({ error: "not found" }, 404);
  return json({ url: hostStudioUrl(env, show, interviewId), show: show.slug, role: "host" });
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

// GET /voices/health — deploy verification without waiting for a cron
// tick. Read-only: reports which secrets are set (never their values), the
// cron schedule, and a live GitHub auth probe (`GET /repos/<repo>` needs
// only metadata:read, which every fine-grained PAT has — so 401 here means
// the STORED token is bad: expired, or pasted with a trailing newline).
// The five-minute fire-tick uses repository_dispatch, which needs Contents: write.
async function handleHealth(env: Env): Promise<Response> {
  const raw = env.GITHUB_DISPATCH_TOKEN || "";
  const tok = githubToken(env);
  const out: Record<string, unknown> = {
    worker: "nerra-voices-api",
    now: new Date().toISOString(),
    cron: { fire_tick: "*/5 * * * * -> repository_dispatch fire-tick",
            producer_tick: "*/30 * * * * -> repository_dispatch producer-tick",
            gate2: "0 17 * * * UTC" },
    configured: {
      supabase: !!(env.SUPABASE_URL && env.SUPABASE_SERVICE_KEY),
      github_token: tok.length > 0,
      github_token_had_whitespace: raw !== tok,
      admin_token: !!env.ADMIN_TOKEN,
      resend: !!(env.RESEND_API_KEY && env.VOICES_FROM_EMAIL),
      calcom: !!env.CALCOM_BOOKING_URL,
      calcom_nerra_voices: !!env.CALCOM_BOOKING_URL_NERRA_VOICES,
      calcom_event_slugs: !!(env.CALCOM_EVENT_SLUG_AGE_OF_AI || env.CALCOM_EVENT_SLUG_NERRA_VOICES),
      slack: !!env.SLACK_WEBHOOK,
      // Studio passwords are derived from ADMIN_TOKEN (Sept 9 2026); the
      // deploy workflow syncs them onto the Voximplant users.
      studio_passwords_derived: !!env.ADMIN_TOKEN,
      vox_guest_password_env_ignored: !!env.VOX_GUEST_PASSWORD,
      vox_host_password_env_ignored: !!env.VOX_HOST_PASSWORD,
      voices_r2: !!env.VOICES_R2,
      operator_phone: !!env.OPERATOR_PHONE,
    },
    shows: Object.keys(SHOWS),
  };
  if (tok) {
    try {
      const resp = await fetch(`https://api.github.com/repos/${REPO}`, {
        headers: {
          Authorization: `Bearer ${tok}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "nerra-voices-worker",
        },
      });
      out.github_status = resp.status;
      out.github_hint =
        resp.status === 200 ? "token authenticates; repository_dispatch additionally needs Contents: Read and write"
        : resp.status === 401 ? "401: stored token rejected — re-run `wrangler secret put GITHUB_DISPATCH_TOKEN` (expired PAT or pasted newline)"
        : `unexpected ${resp.status}`;
    } catch (e: any) {
      out.github_error = e?.message ?? String(e);
    }
  }
  const ok = out.github_status === 200 && (out.configured as any).supabase;
  return json({ ok, ...out }, ok ? 200 : 503);
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
      if (req.method === "POST" && path === "/voices/triage-reassign") return handleTriageReassign(req, env);
      if (req.method === "POST" && path === "/voices/editorial-decision") return handleEditorialDecision(req, env);
      if (req.method === "POST" && path === "/voices/lesson-decision") return handleLessonDecision(req, env);
      if (req.method === "POST" && path === "/voices/narration-take") return handleNarrationTake(req, env);
      const manage = path.match(/^\/voices\/manage\/(.{16,})$/);
      if (manage) {
        const token = decodeURIComponent(manage[1]);
        return req.method === "POST"
          ? handleManageSubmit(req, env, token)
          : handleManagePage(env, token);
      }
      const review = path.match(/^\/voices\/review\/([A-Za-z0-9_-]{16,})$/);
      if (review) {
        return req.method === "POST"
          ? handleGuestReviewSubmit(req, env, review[1])
          : handleGuestReviewPage(env, review[1]);
      }
      if (req.method === "GET" && path === "/voices/admin/triage") return handleAdminTriage(req, env);
      // The token rides in the path as well as the query string: mail
      // transports have twice now mangled the "=" in "?token=..." on the way
      // to Patrick's inbox, and a link that does not survive email is not a
      // link. /voices/admin/review/<id>/<token> is the form we send.
      const adminReview = path.match(
        /^\/voices\/admin\/review\/([0-9a-f-]{36})(?:\/([0-9a-f]{40}))?$/);
      if (adminReview && req.method === "GET") {
        let request = req;
        if (adminReview[2]) {
          const withToken = new URL(req.url);
          withToken.searchParams.set("token", adminReview[2]);
          request = new Request(withToken.toString(), req);
        }
        return handleAdminReview(request, env, adminReview[1]);
      }
      if (req.method === "GET" && path === "/voices/episode-lookup") return handleEpisodeLookup(req, env);
      if (req.method === "GET" && path === "/voices/guest-brief") return handleGuestBrief(req, env);
      if (req.method === "POST" && path === "/voices/fact-check") return handleFactCheck(req, env);
      if (req.method === "GET" && path === "/voices/studio-state") return handleStudioState(req, env);
      if (req.method === "POST" && path === "/voices/studio-echo") return handleStudioEcho(req, env);
      if (req.method === "GET" && path === "/voices/health") return handleHealth(env);
      if (req.method === "POST" && path === "/voices/studio-auth") return handleStudioAuth(req, env);
      // Phase 2 co-host (Sept 2026)
      if (req.method === "POST" && path === "/voices/leg-event") return handleLegEvent(req, env);
      if (req.method === "POST" && path === "/voices/upload-chunk") return handleUploadChunk(req, env);
      if (req.method === "POST" && path === "/voices/upload-done") return handleUploadDone(req, env);
      if (req.method === "GET" && path === "/voices/host-link") return handleHostLink(req, env);
      return json({ error: "not found" }, 404);
    } catch (err: any) {
      console.error("voices worker error:", err?.message ?? err);
      return json({ error: "internal error" }, 500);
    }
  },

  async scheduled(event: ScheduledEvent, env: Env): Promise<void> {
    // */5 tick: punctual fire dispatch (Cloudflare crons fire to the
    // minute; GitHub's own schedule trigger lags up to hours — a real
    // guest sat in a locked studio on Aug 5 2026). Everything downstream
    // is idempotent, so overlapping with the GitHub fallback cron is safe.
    if (event.cron === "*/5 * * * *") {
      try {
        await dispatch(env, "fire-tick", { source: "voices-worker-cron" });
      } catch (err: any) {
        console.error("fire-tick dispatch failed:", err?.message ?? err);
      }
      return;
    }
    // */30 tick: the Nerra Producer inbox job. Same landmine as the fire
    // tick — GitHub delivered the Producer's own */30 schedule roughly
    // every four hours on Sept 5-6 2026, so a publicist's reply waited
    // half a day. Cloudflare fires to the minute; the workflow's
    // concurrency group makes the overlap with GitHub's cron harmless.
    if (event.cron === "*/30 * * * *") {
      try {
        await dispatch(env, "producer-tick", { source: "voices-worker-cron" });
      } catch (err: any) {
        console.error("producer-tick dispatch failed:", err?.message ?? err);
      }
      return;
    }
    await gate2Housekeeping(env);
  },
};
