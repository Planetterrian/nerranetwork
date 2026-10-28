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
 *   GET  /voices/survey/:token        guest survey, a day after the room (Oct 21 2026)
 *   POST /voices/survey/:token        the three answers
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
 *   POST /voices/studio-check         studio: pre-join mic check / day-before setup test / guest stuck outside
 *   GET|POST /voices/admin/text-guest admin: signed link → send a stuck guest their link for their phone
 *   GET|POST /voices/admin/call-guest retired Oct 27 2026 (phone interviews are no longer offered)
 *   GET|POST /voices/join             Cal.com event location: email → the guest's own studio
 *   POST /voices/studio-silence       studio or scenario: guest unheard → email Patrick once
 *   POST /voices/studio-phone         retired Oct 27 2026: answers 410, phone interviews are gone
 *   POST /voices/studio-reschedule    studio: "Still not working? Pick another time" → email the guest their move link
 *   POST /voices/studio-text          studio: text + email the studio link to open on a phone
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
  // Oct 2 2026: lets the booking webhook replace Cal.com's own video room
  // with the guest's studio link in the calendar invite.
  CAL_API_KEY?: string;
  // Oct 2 2026: texting a guest their studio link so they can join from
  // their phone's browser (wideband) instead of a phone line (narrowband).
  VOXIMPLANT_ACCOUNT_ID?: string;
  VOXIMPLANT_API_KEY?: string;
  VOXIMPLANT_CALLER_ID?: string;
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
  // Oct 21 2026: the five-minute pre-call hello (pipelines/voices, migration
  // 20261021_pre_call_hello.sql). The Cal.com event-type slug (or numeric id)
  // that books one; without it a slug or title containing "hello" is one.
  CALCOM_EVENT_SLUG_HELLO?: string;
  SLACK_WEBHOOK?: string;
  // Oct 24 2026: the backup clock. Supabase's pg_cron posts to
  // /voices/cron-tick one minute after each Cloudflare slot with this bearer
  // secret (it lives in Supabase Vault as voices_cron_tick_secret and in the
  // Worker's secrets, never in git). It is NOT ADMIN_TOKEN. Unset = the
  // endpoint refuses every call and Cloudflare's cron is the only clock.
  CRON_TICK_SECRET?: string;
  // Oct 21 2026: the room signs what it posts here. The scenario carries the
  // same value (substituted at deploy as __VOICES_WEBHOOK_SECRET__) and sends
  // X-Voices-Signature: sha256=<hex HMAC-SHA256 of the raw body>. Unset =
  // the scenario-only routes accept unsigned requests as before, so a Worker
  // deployed ahead of the scenario cannot drop a live room's hangup. The
  // browser studio never holds the secret: the routes it shares with the
  // scenario (studio-check, studio-silence, the uploads) verify a signature
  // only when one is sent.
  VOICES_WEBHOOK_SECRET?: string;
  // Oct 21 2026: Cal.com's webhook secret (Cal.com signs the raw body with
  // HMAC-SHA256 and sends the hex in X-Cal-Signature-256). Unset = accept.
  CALCOM_WEBHOOK_SECRET?: string;
  // Oct 19 2026: the half-hour producer tick asks Gmail whether anything is
  // unprocessed before it dispatches a runner (producerTickDue). The SAME
  // service account + delegated mailbox the inbox job uses
  // (nerra_producer_inbox.yml's GMAIL_SERVICE_ACCOUNT_JSON /
  // GMAIL_DELEGATED_USER). Both optional: unset = dispatch every half hour
  // as before. GMAIL_MIRA_USER names Mira's own mailbox; unset = the
  // address inside VOICES_FROM_EMAIL, as the pipeline resolves it.
  GMAIL_SERVICE_ACCOUNT_JSON?: string;
  GMAIL_DELEGATED_USER?: string;
  GMAIL_MIRA_USER?: string;
  // WebRTC studio (July 2026): Voximplant app user the browser SDK logs in
  // as, via the one-time-key handshake in /voices/studio-auth.
  VOX_GUEST_USER?: string;      // default "guest"
  VOX_GUEST_PASSWORD?: string;
  OPERATOR_EMAIL?: string;      // default patricknovak1@gmail.com
  // Comma-separated, copied alongside OPERATOR_EMAIL on guest-facing mail.
  OPERATOR_CC?: string;         // default patrick@planetterrian.com
  // Comma-separated, also copied on guest-facing mail (Oct 8 2026: Dan
  // Perra). Default perra.dan@gmail.com; set it empty to copy nobody.
  GUEST_CC?: string;
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

const signOff = (show: Show) => `Mira, host of ${show.name}`;

// Sept 28 2026: every automated email comes from Mira, by name, and ends the
// same way. Mirrors mira_from / mira_signature_html in
// pipelines/voices/common.py — change the two together.
function miraAddress(env: Env): string {
  const raw = (env.VOICES_FROM_EMAIL || "mira@nerranetwork.com").trim();
  const m = raw.match(/<([^>]+)>/);
  return (m ? m[1] : raw).trim();
}
function miraFrom(env: Env): string {
  return `Mira <${miraAddress(env)}>`;
}
// Oct 24 2026 (operator): the press kit and the sponsorship kit go in the
// mail, pleasantly, so people can look at them and pass them on, to suggest a
// sponsor or to market an episode. engine/brand.py owns the addresses and
// the words (MEDIA_KIT_URL, SPONSOR_KIT_URL, KITS_COPY); these are copies,
// and tests/test_kits_in_the_mail_2026_10_24.py keeps them in step.
export const MEDIA_KIT_URL = "https://nerranetwork.com/press.html";
export const SPONSOR_KIT_URL = "https://nerranetwork.com/sponsor.html";
/** KITS_COPY["intro"]: for someone meeting the network (the invitation). */
export const KITS_INTRO_HTML =
  `<p>If you'd like to know more about the network first, the <a href="${MEDIA_KIT_URL}">press kit</a> has a ` +
  `short description, our logos and our audience numbers. And if anyone ` +
  `you know would like to reach the people who listen, the <a href="${SPONSOR_KIT_URL}">sponsorship kit</a> is ` +
  `the thing to pass along; the interview shows themselves never carry a ` +
  `sponsor.</p>`;

function miraSignature(show?: Show): string {
  const title = show ? `Host of ${show.name}, Nerra Network` : "Nerra Network";
  return `<p style="margin-top:1.4em">Sincerely,<br><br>Mira<br>` +
    `<span style="color:#4a5568;font-size:.9em">${esc(title)} · ` +
    `<a href="https://nerranetwork.com" style="color:#4a5568">nerranetwork.com</a><br>` +
    `<a href="${MEDIA_KIT_URL}" style="color:#4a5568">Press kit</a> · ` +
    `<a href="${SPONSOR_KIT_URL}" style="color:#4a5568">Sponsorship kit</a></span></p>`;
}

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

/** Is this booking the five-minute hello? The configured event type wins
 *  (slug or numeric id, the showFromCalCom pattern); else "hello" in the
 *  slug or the event title. A closing session is never a hello. */
export function isHelloBooking(env: Pick<Env, "CALCOM_EVENT_SLUG_HELLO">, eventSlug: string,
                               eventTypeId: string, title: string): boolean {
  const slug = eventSlug.trim().toLowerCase();
  const id = eventTypeId.trim().toLowerCase();
  const want = (env.CALCOM_EVENT_SLUG_HELLO ?? "").trim().toLowerCase();
  if (want && (want === slug || (id && want === id))) return true;
  return /hello/i.test(slug) || /\bhello\b/i.test(title);
}

export const HELLO_MINUTES = 5;

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

// ---------------------------------------------------------------------------
// Webhook signatures (Oct 21 2026). The review found every inbound webhook
// accepting an unsigned body: anyone who knew a run id could end a room,
// attach a recording URL or flip a leg's timeline. The scenario now signs
// what it posts and the Worker checks it when it holds the secret.
// ---------------------------------------------------------------------------

export const SIGNATURE_HEADER = "X-Voices-Signature";
export const CALCOM_SIGNATURE_HEADER = "X-Cal-Signature-256";

export async function hmacHex(secret: string, message: string | ArrayBuffer): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const data = typeof message === "string" ? enc.encode(message) : new Uint8Array(message);
  const sig = await crypto.subtle.sign("HMAC", key, data);
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Does `header` carry a valid HMAC-SHA256 of `raw` under `secret`? Accepts
 *  "sha256=<hex>" or the bare hex, case-insensitively. */
export async function signatureOk(secret: string, header: string | null,
                                  raw: string | ArrayBuffer): Promise<boolean> {
  const given = String(header ?? "").trim().replace(/^sha256=/i, "").toLowerCase();
  if (!given) return false;
  const want = await hmacHex(secret, raw);
  return tokenEquals(given, want);
}

let unsignedWarned = false;

/** Verdict for a scenario-originated request. `required` = the route is
 *  only ever called by the room (interview-complete, leg-event,
 *  narration-take): with the secret set, an unsigned or wrong signature is
 *  a 401. `required: false` = the studio page shares the route and cannot
 *  sign; a request is refused only when it carries a BAD signature. */
export async function webhookVerdict(env: Pick<Env, "VOICES_WEBHOOK_SECRET">,
                                     header: string | null, raw: string | ArrayBuffer,
                                     required: boolean): Promise<"ok" | "unsigned" | "bad"> {
  const secret = (env.VOICES_WEBHOOK_SECRET || "").trim();
  if (!secret) {
    if (!unsignedWarned) {
      unsignedWarned = true;
      console.warn("VOICES_WEBHOOK_SECRET is not set: inbound webhooks are accepted unsigned");
    }
    return "ok";
  }
  if (!header) return required ? "bad" : "unsigned";
  return (await signatureOk(secret, header, raw)) ? "ok" : "bad";
}

/** Read a JSON body the room may have signed. Returns the parsed body (null
 *  when unparseable) and, when the signature fails, the 401 to send. */
async function readSignedJson(req: Request, env: Env, required: boolean):
    Promise<{ body: any; denied: Response | null }> {
  const raw = await req.text().catch(() => "");
  const verdict = await webhookVerdict(env, req.headers.get(SIGNATURE_HEADER), raw, required);
  if (verdict === "bad") return { body: null, denied: json({ error: "bad signature" }, 401) };
  let body: any = null;
  try { body = raw ? JSON.parse(raw) : null; } catch { body = null; }
  return { body, denied: null };
}

/** Cal.com: X-Cal-Signature-256 is the hex HMAC-SHA256 of the raw body under
 *  the webhook's secret. Verified only when CALCOM_WEBHOOK_SECRET is set. */
async function readCalComJson(req: Request, env: Env):
    Promise<{ body: any; denied: Response | null }> {
  const raw = await req.text().catch(() => "");
  const secret = (env.CALCOM_WEBHOOK_SECRET || "").trim();
  if (secret && !(await signatureOk(secret, req.headers.get(CALCOM_SIGNATURE_HEADER), raw))) {
    return { body: null, denied: json({ error: "bad signature" }, 401) };
  }
  let body: any = null;
  try { body = raw ? JSON.parse(raw) : null; } catch { body = null; }
  return { body, denied: null };
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

// Oct 8 2026 (Patrick): Dan Perra is copied on guest correspondence as well
// as Patrick, and so is a guest's publicist on the mail that concerns their
// booking and their episode; Scott Pulcini's publicist booked him and never
// saw his review link. Mirrors GUEST_CC in pipelines/voices/common.py.
function guestTeamCc(env: Env): string[] {
  return (env.GUEST_CC ?? "perra.dan@gmail.com")
    .split(",").map((a) => a.trim()).filter((a) => a.includes("@"));
}

function publicistCc(app: any): string[] | undefined {
  const p = String(app?.publicist_email ?? "").trim();
  return p.includes("@") ? [p] : undefined;
}

/** One line on what the conversation is about. Oct 8 2026, Patrick: every
 *  booking email says it. For the guest their own topics, or the pitch, read
 *  better than our third-person thesis; for Patrick the thesis comes first.
 *  Mirrors interview_subject in pipelines/voices/common.py. */
function interviewSubject(interview: any, app: any, forGuest: boolean): string {
  let topics: unknown = app?.topics;
  if (typeof topics === "string") {
    try { topics = JSON.parse(topics); } catch { topics = [topics]; }
  }
  const list = Array.isArray(topics)
    ? topics.map((t) => String(t ?? "").trim()).filter((t) => t && t !== "[object Object]")
    : [];
  const fromTopics = list.slice(0, 3).join("; ");
  const pitch = String(app?.pitch_summary ?? "").trim();
  const thesis = String(interview?.episode_thesis ?? "").trim();
  const pick = (forGuest ? [fromTopics, pitch, thesis] : [thesis, pitch, fromTopics])
    .find((t) => t) ?? "";
  if (pick.length <= 280) return pick;
  const cut = pick.slice(0, 280);
  return cut.slice(0, cut.lastIndexOf(" ")).replace(/[;,:\s]+$/, "") + "…";
}

function subjectHtml(text: string, label = "What we'll talk about"): string {
  return text ? `<p><strong>${esc(label)}:</strong> ${esc(text)}</p>` : "";
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
    from: miraFrom(env), reply_to: miraAddress(env), to: [to], subject, html: emailSafeHtml(html),
  };
  // Operator oversight (July 2026): Patrick is CC'ed on guest-facing
  // scheduling/prep mail so Mira can run the show day-to-day while he
  // keeps full visibility.
  const cc: string[] = [];
  if (ccOperator) {
    for (const addr of [...operatorCc(env), ...guestTeamCc(env)]) {
      if (addr.toLowerCase() !== to.toLowerCase()
          && !cc.some((c) => c.toLowerCase() === addr.toLowerCase())) cc.push(addr);
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

/** Constant-time string compare for bearer secrets (timingSafeEqual shape). */
function tokenEquals(a: string, b: string): boolean {
  const enc = new TextEncoder();
  const aa = enc.encode(a);
  const bb = enc.encode(b);
  if (aa.length !== bb.length) return false;
  let diff = 0;
  for (let i = 0; i < aa.length; i++) diff |= aa[i] ^ bb[i];
  return diff === 0;
}

function requireAdmin(req: Request, env: Env): Response | null {
  const auth = req.headers.get("Authorization") ?? "";
  const url = new URL(req.url);
  const token = auth.replace(/^Bearer\s+/i, "") || url.searchParams.get("token") || "";
  const expected = (env.ADMIN_TOKEN || "").trim();
  if (!expected || !tokenEquals(token.trim(), expected)) {
    return json({ error: "unauthorized" }, 401);
  }
  return null;
}

/** Admin bearer, or the triage-scoped HMAC (emails + triage POSTs). */
async function requireTriageAccess(req: Request, env: Env): Promise<Response | null> {
  const auth = req.headers.get("Authorization") ?? "";
  const url = new URL(req.url);
  const token = (auth.replace(/^Bearer\s+/i, "") || url.searchParams.get("token") || "").trim();
  const expected = (env.ADMIN_TOKEN || "").trim();
  if (expected && tokenEquals(token, expected)) return null;
  try {
    if (token && tokenEquals(token, await triageToken(env))) return null;
  } catch { /* fall through */ }
  return json({ error: "unauthorized" }, 401);
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
  const expected = (env.ADMIN_TOKEN || "").trim();
  if (expected && tokenEquals(supplied.trim(), expected)) return null;
  if (supplied && packageId) {
    try {
      if (tokenEquals(supplied.trim(), await packageReviewToken(env, packageId))) return null;
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

/** "Hi Viktor," — the guest's first name, the way Patrick writes, and the
 *  way the published-episode note already greeted them. Sept 23 2026: the
 *  guest review invitation opened "Hi Viktor Popovic,". Mirrors first_name in
 *  pipelines/voices/address.py: drop a leading "Dr."/"Doctor", drop anything
 *  after a comma ("Adrian Wolfberg, PhD"), take the first word. */
function firstName(name: unknown): string {
  const bare = String(name ?? "").trim().replace(/^\s*(?:dr\.?|doctor)\s+/i, "");
  const words = bare.split(/\s*,\s*/)[0].split(/\s+/).filter(Boolean);
  return words[0] || "there";
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
 *  is sensible to plan: anything longer than 90 is a typo rather than a
 *  request. It paces Mira; since Oct 5 2026 it never ends the room. */
function clampMinutes(value: unknown): number | null {
  const n = Math.round(Number(value));
  if (!Number.isFinite(n) || n <= 0) return null;
  return Math.min(90, Math.max(15, n));
}

function oneOf(value: unknown, allowed: string[]): string | null {
  const v = String(value ?? "").trim().toLowerCase();
  return allowed.includes(v) ? v : null;
}

// ---------------------------------------------------------------------------
// Public profiles (Oct 25 2026)
//
// Every applicant names at least one public profile: their X account, their
// LinkedIn profile, or their profile page on their company's own website.
// Patrick asked for it so an application can be checked against something
// the applicant did not write for us, and so the episode page can link to
// the guest and carry their public photo (pipelines/voices/profile_photo.py
// finds the photo; the post shows it beside their name). The keys written
// here, links.x / links.linkedin / links.company_profile, are read back by
// public_profiles in pipelines/voices/common.py.
// ---------------------------------------------------------------------------

export type PublicProfiles = { x: string | null; linkedin: string | null; company_profile: string | null };
type Normalised = { url: string | null; error: string | null };

export const PUBLIC_PROFILE_REQUIRED =
  "Please give at least one public profile: your X account, your LinkedIn profile, or your " +
  "profile page on your company's website. We use it to confirm who you are, and your episode " +
  "page links to it.";

const PROFILE_SOCIAL_HOSTS = ["x.com", "twitter.com", "linkedin.com", "facebook.com", "instagram.com",
  "threads.net", "bsky.app", "tiktok.com", "youtube.com"];
// Paths on x.com that are not anybody's account.
const X_NOT_A_HANDLE = new Set(["home", "i", "intent", "share", "search", "explore", "settings",
  "messages", "notifications", "hashtag", "login", "signup", "compose"]);
const X_HANDLE_RE = /^[A-Za-z0-9_]{1,15}$/;

function asUrl(raw: string): URL | null {
  const text = raw.trim();
  if (!text || /\s/.test(text)) return null;
  try {
    const u = new URL(/^https?:\/\//i.test(text) ? text : `https://${text}`);
    if (!/^https?:$/.test(u.protocol) || !u.hostname.includes(".")) return null;
    return u;
  } catch { return null; }
}

const hostIs = (u: URL, domain: string) =>
  u.hostname.toLowerCase() === domain || u.hostname.toLowerCase().endsWith(`.${domain}`);

/** "@piper", "piper", "x.com/piper", "https://twitter.com/piper?s=21" → https://x.com/piper. */
export function normaliseX(raw: unknown): Normalised {
  const text = String(raw ?? "").trim();
  if (!text) return { url: null, error: null };
  const bare = text.replace(/^@/, "");
  let handle = X_HANDLE_RE.test(bare) ? bare : "";
  if (!handle) {
    const u = asUrl(text);
    if (u && (hostIs(u, "x.com") || hostIs(u, "twitter.com"))) {
      const first = u.pathname.split("/").filter(Boolean)[0] ?? "";
      if (X_HANDLE_RE.test(first) && !X_NOT_A_HANDLE.has(first.toLowerCase())) handle = first;
    }
  }
  return handle ? { url: `https://x.com/${handle}`, error: null }
    : { url: null, error: "That X account doesn't look right. Use @yourhandle or the link to your profile." };
}

/** A personal LinkedIn profile (/in/… or the older /pub/…), tracking stripped. */
export function normaliseLinkedIn(raw: unknown): Normalised {
  const text = String(raw ?? "").trim();
  if (!text) return { url: null, error: null };
  const u = asUrl(text);
  const parts = u ? u.pathname.split("/").filter(Boolean) : [];
  if (u && hostIs(u, "linkedin.com") && parts[0] === "in" && parts[1]) {
    return { url: `https://www.linkedin.com/in/${parts[1]}`, error: null };
  }
  if (u && hostIs(u, "linkedin.com") && parts[0] === "pub" && parts[1]) {
    return { url: `https://www.linkedin.com/${parts.join("/")}`, error: null };
  }
  return { url: null, error: "Use the link to your own LinkedIn profile (it has /in/ in it), for example linkedin.com/in/yourname." };
}

/** The page about the guest on their company's own site. */
export function normaliseCompanyProfile(raw: unknown): Normalised {
  const text = String(raw ?? "").trim();
  if (!text) return { url: null, error: null };
  const u = asUrl(text);
  if (!u) {
    return { url: null, error: "The company profile link doesn't look like a web address. Paste the full link to the page about you." };
  }
  if (PROFILE_SOCIAL_HOSTS.some((h) => hostIs(u, h))) {
    return { url: null, error: "For the company profile, use the page about you on your company's own website. Your X and LinkedIn links have their own boxes." };
  }
  u.hash = "";
  return { url: u.toString().replace(/\/$/, ""), error: null };
}

/** The guest's public profiles from the apply form, or the reason to send it back.
 *  Lenient where it can be: a LinkedIn or X link pasted into the company box
 *  or into "other links" is moved to its own key rather than refused, which
 *  also keeps an apply page cached from before Oct 25 (one free-text links
 *  box) working for anyone who put either there. */
export function publicProfiles(form: any): { profiles: PublicProfiles; error: string | null } {
  const links = form?.links && typeof form.links === "object" ? form.links : {};
  const pick = (k: string) => String(links[k] ?? form?.[k] ?? "").trim();
  let xRaw = pick("x"), liRaw = pick("linkedin"), coRaw = pick("company_profile");
  const coUrl = coRaw ? asUrl(coRaw) : null;
  if (coUrl && hostIs(coUrl, "linkedin.com") && !liRaw && normaliseLinkedIn(coRaw).url) { liRaw = coRaw; coRaw = ""; }
  if (coUrl && (hostIs(coUrl, "x.com") || hostIs(coUrl, "twitter.com")) && !xRaw && normaliseX(coRaw).url) { xRaw = coRaw; coRaw = ""; }
  const others = String(typeof form?.links === "string" ? form.links : links.raw ?? "")
    .split(/[\s,]+/).filter(Boolean);
  if (!liRaw) liRaw = others.find((o) => { const u = asUrl(o); return !!u && hostIs(u, "linkedin.com") && !!normaliseLinkedIn(o).url; }) ?? "";
  if (!xRaw) xRaw = others.find((o) => { const u = asUrl(o); return !!u && (hostIs(u, "x.com") || hostIs(u, "twitter.com")) && !!normaliseX(o).url; }) ?? "";
  const x = normaliseX(xRaw), li = normaliseLinkedIn(liRaw), co = normaliseCompanyProfile(coRaw);
  const profiles = { x: x.url, linkedin: li.url, company_profile: co.url };
  const error = x.error || li.error || co.error
    || (profiles.x || profiles.linkedin || profiles.company_profile ? null : PUBLIC_PROFILE_REQUIRED);
  return { profiles, error };
}

/** The links column for a new application: the profiles under their own keys,
 *  anything else the guest listed kept as free text. */
export function applicationLinks(profiles: PublicProfiles, formLinks: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(profiles)) if (v) out[k] = v;
  const raw = typeof formLinks === "string" ? formLinks
    : formLinks && typeof formLinks === "object" ? String((formLinks as any).raw ?? "") : "";
  if (raw.trim()) out.raw = raw.trim().slice(0, 500);
  return out;
}

/** Profile links (and the photo, once found) for the triage page and Patrick's mail. */
export function profilesHtml(app: any): string {
  const l = app?.links && typeof app.links === "object" ? app.links : {};
  const items = ([["X", l.x], ["LinkedIn", l.linkedin], ["Company profile", l.company_profile]] as Array<[string, unknown]>)
    .filter(([, u]) => typeof u === "string" && /^https?:\/\//.test(u as string))
    .map(([label, u]) => `<a href="${esc(String(u))}" target="_blank" rel="noopener">${label}</a>`);
  const photo = typeof app?.profile_photo_url === "string" && app.profile_photo_url
    ? `<img src="${esc(app.profile_photo_url)}" alt="" width="40" height="40" style="border-radius:50%;vertical-align:middle;margin-right:.4rem">` : "";
  return items.length
    ? `<br><small class="prov">${photo}<b>Public profiles:</b> ${items.join(" · ")}</small>`
    : `<br><small style="color:#991B1B"><b>No public profile given</b> (X, LinkedIn or a company page): ask for one before booking.</small>`;
}

async function handleApply(req: Request, env: Env): Promise<Response> {
  const form = await req.json<any>().catch(() => null);
  if (!form?.name || !form?.email) return json({ error: "name and email are required" }, 400);
  // Oct 25 2026: at least one public profile, or the form says what is missing.
  const { profiles, error: profileError } = publicProfiles(form);
  if (profileError) return json({ error: profileError, field: "public_profile" }, 400);
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
    links: applicationLinks(profiles, form.links),
    // What the guest wants the conversation to be (Sept 13 2026). These three
    // shape Mira's brief, the number of questions she prepares, and the clock
    // she paces to. A guest who asks for twenty minutes and gets forty-five
    // has been mistreated, however good the questions were.
    desired_minutes: clampMinutes(form.desired_minutes),
    depth: oneOf(form.depth, ["accessible", "standard", "deep"]),
    personal_depth: oneOf(form.personal_depth, ["none", "light", "open"]),
    off_limits: form.off_limits ? String(form.off_limits).slice(0, 500) : null,
    // Sept 29 2026 (Chad Law): the points the guest wants reached. Mira
    // covers every one, in her own words; they reach her prompt through
    // guest_agenda_block in pipelines/voices/common.py.
    guest_agenda: Array.isArray(form.must_cover) && form.must_cover.some((x: unknown) => String(x ?? "").trim())
      ? { topic: null, points: form.must_cover.map((x: unknown) => String(x ?? "").trim().slice(0, 400))
            .filter(Boolean).slice(0, 5), updated_at: new Date().toISOString(), source: "application" }
      : null,
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
    `&order=created_at.desc&limit=1&select=id,show,links`);
  if (invited?.length) {
    const patch: Record<string, unknown> = { status: "pending" };
    for (const [k, v] of Object.entries(fields)) {
      if (v !== null && v !== undefined && v !== "") patch[k] = v;
    }
    // The Producer's stub may already hold links from the pitch ({urls: [...]});
    // keep them beside what the guest gave on the form.
    const prior = invited[0].links;
    if (prior && typeof prior === "object" && !Array.isArray(prior)) {
      patch.links = { ...prior, ...(fields.links as Record<string, string>) };
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
  // Sept 28 2026: an applicant used to hear nothing until a decision was
  // made, which could be days. Mira says thank you straight away and says
  // what happens next; a decision, either way, follows from her too.
  if (id && emailAddr.includes("@")) {
    try {
      await email(env, emailAddr, `Thank you for applying to ${show.name}`,
        `<p>Hi ${esc(firstName(form.name))},</p>
         ${merged
           ? `<p>Thank you for filling in the details for ${esc(show.name)}. They go straight
              into how I prepare for our conversation. If you haven't picked a time yet, the
              booking link is in my earlier email, or reply here and I'll send it again.</p>
              <p>`
           : `<p>Thank you for applying to be a guest on ${esc(show.name)}. I'm Mira, the AI
              who hosts the show. Patrick Novak, who created the Nerra Network, and I read every
              application, and you will hear back from me either way.</p>
              <p>If it's a fit, my next email will have a link to pick a time. `}In the meantime,
         past conversations are at <a href="${esc(SITE + "/" + show.page)}">${esc(SITE + "/" + show.page)}</a>
         if you'd like a sense of how they go.</p>
         ${miraSignature(show)}`, true);
    } catch (err: any) {
      console.error("apply: acknowledgement email failed:", err?.message ?? err);
    }
  }
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
         <p>${profilesHtml({ links: fields.links }).replace(/^<br>/, "")}</p>
         <p><a href="https://api.nerranetwork.com/voices/admin/triage?token=${await triageToken(env)}">
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

const PLATFORM_FAULT_REASONS = new Set(["grok_dropped", "agent_startup_failed", "media_bridge_failed",
  "room_startup_failed"]);

async function handleInterviewComplete(req: Request, env: Env): Promise<Response> {
  const { body: payload, denied } = await readSignedJson(req, env, true);
  if (denied) return denied;
  if (!payload?.run_id) return json({ error: "run_id required" }, 400);
  // Room model (Sept 9 2026): the per-person recording URLs arrive from
  // the participant sessions via /voices/leg-event, so the completion
  // payload MERGES into grok_session_log and never nulls a per-leg URL
  // it does not carry.
  const existingRows = await sb(env, "GET",
    `interview_runs?id=eq.${payload.run_id}&select=grok_session_log,status,disconnect_reason,session_kind`);
  const existingLog = existingRows?.[0]?.grok_session_log ?? {};
  // Oct 21 2026: the room reports how the turn-taking went on every run.
  // Kept inside grok_session_log (no new column); the rehearsal harness and
  // the audio metrics read them from there.
  const roomCounters = roomCountersOf(payload);
  // A rehearsal (the harness's fixture guest in a real room) is stored and
  // stopped there: no post-interview processing, no email, no Slack.
  if (String(existingRows?.[0]?.session_kind ?? "") === "rehearsal") {
    await sb(env, "PATCH", `interview_runs?id=eq.${payload.run_id}`, {
      status: payload.status === "failed" ? "failed" : "completed",
      disconnect_reason: payload.disconnect_reason ?? payload.reason ?? null,
      duration_sec: payload.duration_sec ?? null,
      ...(payload.voximplant_mira_record_url ? { recording_mira_url: payload.voximplant_mira_record_url } : {}),
      grok_session_log: {
        ...existingLog,
        ...(payload.grok_session_log ? { log: payload.grok_session_log } : {}),
        ...(payload.voximplant_record_url ? { voximplant_record_url: payload.voximplant_record_url } : {}),
        ...(payload.voximplant_mira_record_url ? { voximplant_mira_record_url: payload.voximplant_mira_record_url } : {}),
        ...(payload.voximplant_mix_record_url ? { voximplant_mix_record_url: payload.voximplant_mix_record_url } : {}),
        ...(payload.speech_events !== undefined ? { speech_events: Number(payload.speech_events) || 0 } : {}),
        call_mode: payload.call_mode ?? existingLog.call_mode ?? null,
        rehearsal: true,
        ...roomCounters,
      },
    });
    return json({ ok: true, rehearsal: true });
  }
  // Oct 27 2026: phone interviews are gone, so every room is a browser room.
  // A room that failed to START posts {status: failed, reason: "startup: ..."}
  // with no call_mode (scenarios deployed before today); that is the room's
  // fault, not a guest who didn't answer, and is handled as one below.
  const browserRoom = payload.call_mode !== "pstn";
  const endReason = String(payload.disconnect_reason ?? payload.reason ?? "");
  const roomStartFailed = payload.status === "failed" && /^startup\b/.test(endReason);
  // Only an interview session is held to the five-minute floor. Oct 27 2026:
  // a five-minute hello under about 4:15 was read as a failed join, so the
  // agenda it exists to produce was never made.
  const runKind = String(existingRows?.[0]?.session_kind ?? "interview");
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
      ...roomCounters,
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
  // starts a fresh room, and count nothing against the guest. A room that
  // failed to start at all (Oct 27 2026) is the same kind of fault.
  const platformFault = PLATFORM_FAULT_REASONS.has(String(payload.disconnect_reason ?? "")) || roomStartFailed;
  if (browserRoom && platformFault) {
    await sb(env, "PATCH", `interview_runs?id=eq.${payload.run_id}`, {
      status: "awaiting_guest", duration_sec: null, disconnect_reason: null,
      grok_session_log: { ...existingLog, last_platform_fault: {
        reason: payload.disconnect_reason ?? endReason, duration_sec: dur, at: new Date().toISOString() } },
    });
    try {
      await email(env, operatorEmail(env),
        `Studio: room ended on a platform fault (${payload.disconnect_reason ?? endReason})`,
        `<p>Hi Patrick,</p><p>The interview room for run ${esc(String(payload.run_id))} ended after
         ${dur} seconds because of <strong>${esc(String(payload.disconnect_reason ?? endReason))}</strong>
         (the AI voice connection, not anyone's browser). The studio is open again: everyone
         can press Join on the same links and a fresh room starts. If it repeats, the xAI
         connector is having a bad moment; wait a minute and try again.</p><p>— Mira</p>`);
    } catch (err: any) {
      console.error("platform-fault email failed:", err?.message ?? err);
    }
    return json({ ok: true, platform_fault: true, reopened: true });
  }
  if (browserRoom && runKind === "interview" && payload.status !== "failed" && dur < 300) {
    const runRows = await sb(env, "GET",
      `interview_runs?id=eq.${payload.run_id}&select=interview_id,grok_session_log,guest_joined_at`);
    const runRow = runRows?.[0] ?? {};
    const attempts = Number(runRow.grok_session_log?.aborted_attempts ?? 0) + 1;
    const ivRows = runRow.interview_id ? await sb(env, "GET",
      `interviews?id=eq.${runRow.interview_id}&select=application_id,show`) : [];
    const show = showFor(ivRows?.[0]);

    // Oct 27 2026: two failed joins used to switch the interview to a phone
    // call. Phone interviews are gone, so the studio simply stays open, and
    // on the second failure the guest is told the two ways that work: the
    // same link in their phone's browser, or another time.
    let guestEmailed = false;
    // Only a guest who was actually in the room (Patrick testing on his own
    // as co-host is not "the guest's studio dropping").
    if (attempts === 2 && runRow.interview_id && runRow.guest_joined_at) {
      const ivFull = (await sb(env, "GET",
        `interviews?id=eq.${runRow.interview_id}&select=id,manage_token,application_id,show`))?.[0] ?? {};
      const apps = ivFull.application_id ? await sb(env, "GET",
        `guest_applications?id=eq.${ivFull.application_id}&select=name,email`) : [];
      if (apps?.[0]?.email) {
        const studio = studioUrl(show, runRow.interview_id, "guest");
        const move = ivFull.manage_token
          ? `https://api.nerranetwork.com/voices/manage/${encodeURIComponent(ivFull.manage_token)}`
          : bookingUrl(env, show);
        try {
          await email(env, apps[0].email,
            "Our studio session ended early twice: two ways that work",
            `<p>Hi ${esc(firstName(apps[0].name))},</p><p>Our studio session has ended early twice
             today. If the studio is misbehaving on your computer, that is ours to solve, not
             yours. Two things that work:</p>
             <ol><li><strong>Open <a href="${esc(studio)}">your studio link</a> on your phone</strong>,
             earbuds in. It's the same studio and sounds just as good, and I'm still waiting there.</li>
             <li>If that doesn't work either, <a href="${esc(move)}">pick another time</a>. Nothing is
             lost.</li></ol>${miraSignature(show)}`, true);
          guestEmailed = true;
        } catch (err: any) {
          console.error("second-drop guest email failed:", err?.message ?? err);
        }
      }
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
    await slack(env, `${show.shortLabel}: studio call ended after ${dur}s (attempt ${attempts}) — studio reopened for retry${guestEmailed ? "; guest emailed the phone-browser link and a move link" : ""}.`);
    try {
      await email(env, operatorEmail(env),
        `${show.shortLabel}: guest's studio call dropped early — retry is open`,
        `<p>Hi Patrick,</p><p>A studio session ended after only ${dur} seconds
         (attempt ${attempts}) — a failed join. The studio is reopened for
         the guest.${guestEmailed ? " Because it has happened twice, I've emailed them the link to open on their phone's browser and a link to pick another time." : attempts === 1 ? " If it happens again, I'll email them the link for their phone's browser and a link to pick another time." : ""}
         No action needed unless you'd like to reach out yourself.</p><p>— Mira</p>`);
    } catch (err: any) {
      console.error("aborted-join email failed:", err?.message ?? err);
    }
    return json({ ok: true, aborted_join: true, attempt: attempts });
  }

  await sb(env, "PATCH", `interview_runs?id=eq.${payload.run_id}`, patch);

  // Oct 27 2026: the retry ladder for failed phone dials is gone with the
  // phone path (no call is ever dialled now). Its "startup" match caught room
  // startup failures and, on the second, emailed browser guests "I called
  // twice but couldn't get through"; those are platform faults above.

  await dispatch(env, "interview-complete", { run_id: payload.run_id });
  return json({ ok: true });
}

/** The turn-taking counters the room posts at the end of every run (Oct 21
 *  2026): barge-ins, server-started turns, self-answers the completion check
 *  blocked, whether the closing round completed and which of its questions
 *  were asked. Numbers and booleans only; anything else is dropped. */
export function roomCountersOf(payload: any): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const k of ["barge_ins", "server_turns", "self_answers_blocked",
                   // Oct 22 2026: server turns the room cancelled and decided
                   // itself, and how often the guest stepped away (hold mode).
                   "server_turns_rerouted", "holds", "dead_air_nudges"]) {
    if (payload?.[k] !== undefined && Number.isFinite(Number(payload[k]))) out[k] = Number(payload[k]);
  }
  if (typeof payload?.closing_round_complete === "boolean") out.closing_round_complete = payload.closing_round_complete;
  // Oct 23 2026: the guest's presses on the studio page (good question /
  // move on / ask me about). Bounded and typed; the rest is dropped.
  if (Array.isArray(payload?.guest_feedback)) {
    out.guest_feedback = payload.guest_feedback.slice(0, 60)
      .filter((f: any) => f && ["good", "move_on", "topic"].includes(String(f.kind)))
      .map((f: any) => ({
        kind: String(f.kind),
        by: f.by === "host" ? "host" : "guest",
        at_min: Number.isFinite(Number(f.at_min)) ? Number(f.at_min) : null,
        ...(f.question ? { question: String(f.question).slice(0, 300) } : {}),
        ...(f.text ? { text: String(f.text).slice(0, 240) } : {}),
        ...(typeof f.applied === "boolean" ? { applied: f.applied } : {}),
        ...(typeof f.held === "boolean" ? { held: f.held } : {}),
      }));
  }
  if (payload?.guest_steers_applied !== undefined && Number.isFinite(Number(payload.guest_steers_applied))) {
    out.guest_steers_applied = Number(payload.guest_steers_applied);
  }
  if (Array.isArray(payload?.closing_questions_asked)) {
    out.closing_questions_asked = payload.closing_questions_asked.slice(0, 20).map((q: unknown) => String(q).slice(0, 200));
  } else if (payload?.closing_questions_asked !== undefined && Number.isFinite(Number(payload.closing_questions_asked))) {
    out.closing_questions_asked = Number(payload.closing_questions_asked);
  }
  return out;
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

// Sept 30 2026: every time a person reads is Pacific, the network's zone
// (Vancouver), with the guest's own clock alongside when we know it. Mirrors
// pacific_time in pipelines/voices/common.py.
const PACIFIC_TZ = "America/Vancouver";

function pacificTime(iso: unknown, guestTz?: string | null, dateOnly = false): string {
  const d = new Date(String(iso ?? ""));
  if (!iso || isNaN(d.getTime())) return "";
  const day = (tz: string) => d.toLocaleDateString("en-US",
    { timeZone: tz, weekday: "long", month: "long", day: "numeric" });
  const clock = (tz: string) => d.toLocaleTimeString("en-US",
    { timeZone: tz, hour: "numeric", minute: "2-digit" });
  const pDay = day(PACIFIC_TZ);
  if (dateOnly) return pDay;
  let out = `${pDay} at ${clock(PACIFIC_TZ)} Pacific Time`;
  if (guestTz) {
    try {
      const gClock = clock(guestTz);
      if (gClock !== clock(PACIFIC_TZ) || day(guestTz) !== pDay) {
        const zone = d.toLocaleTimeString("en-US", { timeZone: guestTz, timeZoneName: "short" })
          .split(" ").pop();
        const gDay = day(guestTz) !== pDay ? `${d.toLocaleDateString("en-US", { timeZone: guestTz, weekday: "long" })} ` : "";
        out += ` (${gDay}${gClock} ${zone} where you are)`;
      }
    } catch { /* an unknown zone never breaks a mail */ }
  }
  return out;
}

/** The booked time as the guest reads it: Pacific, and their own clock. */
function attendeeTimeZone(p: any): string | null {
  const tz = p?.attendees?.[0]?.timeZone ?? null;
  return tz ? String(tz) : null;
}
function bookedWhen(startTime: string, p: any): string {
  return pacificTime(startTime, attendeeTimeZone(p));
}

/** Several approved rows share the address a booking came from: a publicist
 *  represents more than one guest. Sept 14 2026: Think Right PR booked Chad
 *  Law, and the newest row under their address was John Colascione's, so
 *  the booking, the interview and a week of reminders went to the wrong
 *  guest. Pick by the name on the booking, or its title and notes; if the
 *  booking names none of them, pick nobody and let the name/phone match and
 *  the orphan alert below deal with it. One row is still just that row. */
function chooseApplication(rows: any[], p: any): any[] {
  if (!rows?.length) return [];
  const byPerson = new Map<string, any>();
  for (const r of rows) if (!byPerson.has(nameKey(r.name))) byPerson.set(nameKey(r.name), r);
  const people = [...byPerson.values()];
  if (people.length === 1) return [people[0]];
  const booked = bookingName(p);
  const hit = people.filter((r) => namesOverlap(r.name, booked));
  if (hit.length === 1) return hit;
  const text = ` ${nameKey([p.title, p.eventTitle, bookingNotes(p), booked].join(" "))} `;
  const named = people.filter((r) => nameKey(r.name).length >= 5 && text.includes(` ${nameKey(r.name)} `));
  return named.length === 1 ? named : [];
}

/** Whatever the booker wrote in the notes/"additional notes" question. */
function bookingNotes(p: any): string {
  // Oct 8 2026: an empty notes field arrives as an object with no value, and
  // String() of that put "[object Object]" in Stan Lewis's and Jason
  // Fishman's bios, which their prep briefs then read. Only text counts.
  for (const n of [p.responses?.notes?.value, p.responses?.notes, p.additionalNotes, p.description]) {
    if (typeof n === "string" && n.trim()) return n.trim();
  }
  return "";
}

/** Oct 5 2026 (Jon Cheney). The webhook only ever heard BOOKING_CREATED, so
 *  a guest who used Cal.com's own Reschedule or Cancel link (the one in their
 *  calendar invite) moved nothing here: Jon rescheduled from Sept 22 and the
 *  room opened for the old slot. A cancellation in Cal.com now cancels the
 *  interview; a reschedule runs through the booking path below, which moves
 *  the guest's existing interview to the new time. */
async function handleCalComCancelled(env: Env, p: any): Promise<Response> {
  if (p.rescheduled === true || p.fromReschedule) return json({ ok: true, ignored: "part of a reschedule" });
  const startTime = p.startTime ?? p.start_time ?? null;
  const emails = bookingEmails(p);
  if (!startTime || !emails.length) return json({ error: "email + startTime required" }, 400);
  const iv = await interviewForBooking(env, String(p.uid ?? ""), String(startTime), emails);
  if (iv) {
    const app = (await sb(env, "GET",
      `guest_applications?id=eq.${iv.application_id}&select=id,name,email,publicist_email,show`))?.[0] ?? {};
    const show = isShow(iv.show) ? showFor(iv) : showFor(app);
    const reason = String(p.cancellationReason ?? p.cancellation_reason ?? "").slice(0, 500);
    await sb(env, "PATCH", `interviews?id=eq.${iv.id}`, {
      status: "cancelled", cancelled_at: new Date().toISOString(),
      cancel_reason: `cancelled in Cal.com${reason ? `: ${reason}` : ""}`,
    });
    await sb(env, "PATCH",
      `interview_runs?interview_id=eq.${iv.id}&status=in.(staged,awaiting_guest,pending)`,
      { status: "cancelled", disconnect_reason: "guest cancelled in Cal.com" });
    const booking = bookingUrl(env, show);
    try {
      await email(env, app.email, `No problem: our interview on ${show.name} is cancelled`,
        `<p>Hi ${esc(firstName(app.name))},</p>
         <p>No problem at all. Your slot is released and nobody is waiting for you.</p>
         ${booking ? `<p>Whenever you'd like to pick it up again, <a href="${esc(booking)}">book a new time here</a>.</p>` : ""}
         ${miraSignature(show)}`, true, publicistCc(app));
    } catch (err: any) { console.error("cancel ack failed:", err?.message ?? err); }
    await email(env, operatorEmail(env), `${show.shortLabel}: ${app.name ?? "a guest"} cancelled in Cal.com`,
      `<p>${esc(app.name ?? "A guest")} cancelled the interview at ${esc(pacificTime(iv.scheduled_at))} from Cal.com.</p>` +
      (reason ? `<p>They said: ${esc(reason)}</p>` : "<p>No reason given.</p>"));
    return json({ ok: true, cancelled: iv.id });
  }
  return json({ ok: true, cancelled: null });
}

/** The interview a Cal.com booking belongs to, found from the booking itself
 *  (its uid, or its start time and the guest's address) rather than by
 *  matching an application, which a guest with two rows of the same name
 *  defeats: the Oct 5 2026 test of a reschedule created a second interview
 *  and a second application instead of moving the first. */
async function interviewForBooking(env: Env, uid: string, startTime: string,
                                   emails: string[]): Promise<any | null> {
  const live = "status=in.(scheduled,briefed)";
  const sel = "select=id,application_id,show,scheduled_at,guest_timezone,manage_token,session_kind,episode_thesis";
  if (uid) {
    const byUid = await sb(env, "GET",
      `interviews?cal_booking_uid=eq.${encodeURIComponent(uid)}&${live}&${sel}&limit=1`);
    if (byUid?.length) return byUid[0];
  }
  const at = new Date(startTime || "");
  if (!startTime || isNaN(at.getTime()) || !emails.length) return null;
  const rows = await sb(env, "GET",
    `interviews?scheduled_at=eq.${encodeURIComponent(at.toISOString())}&${live}&${sel}`) ?? [];
  for (const iv of rows) {
    const app = (await sb(env, "GET",
      `guest_applications?id=eq.${iv.application_id}&select=email,publicist_email`))?.[0];
    const theirs = [app?.email, app?.publicist_email].map((e) => String(e ?? "").toLowerCase());
    if (emails.some((e) => theirs.includes(e))) return iv;
  }
  return null;
}

/** BOOKING_RESCHEDULED: move the guest's interview to the new time and tell
 *  them, in one email, where it now is and how to join. */
async function handleCalComRescheduled(env: Env, p: any): Promise<Response | null> {
  const emails = bookingEmails(p);
  const startTime = p.startTime ?? p.start_time ?? null;
  if (!startTime) return null;
  const iv = await interviewForBooking(env,
    String(p.rescheduleUid ?? p.fromReschedule ?? ""),
    String(p.rescheduleStartTime ?? p.rescheduledFrom ?? ""), emails);
  if (!iv) return null;                       // the booking path will find or make one
  const app = (await sb(env, "GET",
    `guest_applications?id=eq.${iv.application_id}&select=id,name,email,show,topics,pitch_summary,publicist_email`))?.[0] ?? {};
  const show = isShow(iv.show) ? showFor(iv) : showFor(app);
  await sb(env, "PATCH", `interviews?id=eq.${iv.id}`, {
    scheduled_at: startTime, status: "scheduled", reminder_sent_at: null,
    guest_timezone: attendeeTimeZone(p) ?? iv.guest_timezone ?? null,
    cal_booking_uid: String(p.uid ?? "") || null,
    studio_kick_at: null, studio_alert_at: null,
    // Oct 27 2026: a move after the T-5 notice or a late alert used to leave
    // them stamped, so the new slot got neither. (A stuck alert is matched to
    // its slot where it is read.)
    start_notice_at: null, late_alert_at: null, studio_seen_at: null,
    studio_reschedule_sent_at: null,
  });
  const studio = studioUrl(show, iv.id, "guest");
  await setCalendarLocation(env, show, String(p.uid ?? ""), studio, app.name ?? "guest");
  const when = pacificTime(startTime, attendeeTimeZone(p) ?? iv.guest_timezone);
  const manage = iv.manage_token
    ? `https://api.nerranetwork.com/voices/manage/${encodeURIComponent(iv.manage_token)}` : "";
  if (app.email) {
    await email(env, app.email, `Moved: our interview on ${show.name} is now ${pacificTime(startTime, null, true)}`,
      `<p>Hi ${esc(firstName(app.name))},</p>
       <p>No problem at all. We're now on for <strong>${esc(when)}</strong>. Your studio link
       stays the same.</p>
       ${subjectHtml(interviewSubject(iv, app, true))}
       ${studioStepsHtml(studio)}
       ${manage ? `<p>If you need to move it again, <a href="${esc(manage)}">use this link</a>.</p>` : ""}
       ${miraSignature(show)}`, true, publicistCc(app));
  }
  await email(env, operatorEmail(env), `${show.shortLabel}: ${app.name ?? "a guest"} rescheduled in Cal.com`,
    `<p>${esc(app.name ?? "A guest")} moved their interview from ${esc(pacificTime(iv.scheduled_at))}
     to ${esc(pacificTime(startTime))}. The interview row moved with it; nothing to do.</p>
     ${subjectHtml(interviewSubject(iv, app, false), "The interview")}`);
  try { await dispatch(env, "fire-tick", { source: "reschedule", interview_id: iv.id }); }
  catch (err: any) { console.error("reschedule fire-tick failed:", err?.message ?? err); }
  return json({ ok: true, show: show.slug, interview_id: iv.id, moved: true });
}

async function handleCalComBooked(req: Request, env: Env): Promise<Response> {
  const { body: hook, denied } = await readCalComJson(req, env);
  if (denied) return denied;
  const p = hook?.payload ?? hook ?? {};
  const trigger = String(hook?.triggerEvent ?? hook?.trigger_event ?? "").toUpperCase();
  if (trigger === "BOOKING_CANCELLED") return handleCalComCancelled(env, p);
  if (trigger === "BOOKING_RESCHEDULED") {
    const moved = await handleCalComRescheduled(env, p);
    if (moved) return moved;
  }
  // BOOKING_RESCHEDULED carries the new start time and falls through: the
  // guest's scheduled interview is found and moved, exactly as for a rebook.
  const emails = bookingEmails(p);
  const emailAddr = emails[0] ?? "";
  const startTime = p.startTime ?? p.start_time ?? null;
  if (!emailAddr || !startTime) return json({ error: "email + startTime required" }, 400);

  // Which show was booked: Cal.com sends the event type in a few shapes
  // depending on webhook version. Env mapping wins; else the "voices"
  // heuristic (see showFromCalCom).
  // Oct 5 2026 (Piper Martz): this webhook version names the event type in
  // "type", which was never read, so her closing-session booking arrived
  // with no slug and was set up as a new 45-minute interview.
  const eventSlug = String(p.eventType?.slug ?? p.eventTypeSlug ?? p.event_type_slug ?? p.type ?? "");
  const eventTypeId = String(p.eventTypeId ?? p.eventType?.id ?? p.event_type_id ?? "");
  const bookedShow = showFromCalCom(env, eventSlug, eventTypeId);

  const base = `guest_applications?email=eq.${encodeURIComponent(emailAddr)}&status=eq.approved`;
  let apps = chooseApplication(await sb(env, "GET",
    `${base}&show=eq.${bookedShow.slug}&order=created_at.desc&limit=10`), p);
  if (!apps?.length) {
    // No approved application for that show — fall back to the newest
    // approved one for the email regardless of show (a guest booked via
    // the other show's event link, or a pre-migration row).
    apps = chooseApplication(await sb(env, "GET", `${base}&order=created_at.desc&limit=10`), p);
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
      apps = chooseApplication(await sb(env, "GET", `${alt}&order=created_at.desc&limit=10`), p);
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
    await slack(env, `:rotating_light: Cal.com booking for ${who} at ${pacificTime(startTime)} matched NO application. ` +
      (apps.length
        ? "A placeholder application and the interview were created so Mira still calls; check the triage page."
        : "And the placeholder could not be created — nobody is calling them."));
    try {
      await email(env, operatorEmail(env),
        `A booked ${bookedShow.shortLabel} interview matched no application`,
        `<p>Hi Patrick,</p><p><strong>${esc(who)}</strong> booked a time at
         <strong>${esc(pacificTime(startTime) || String(startTime))}</strong> and it matched no application
         by address, name or phone.</p>
         ${apps.length
           ? `<p>So that nobody is left waiting for a call, I created an application
              from the booking and scheduled the interview. If this is someone we
              invited under another address, merge it into their real application
              on the <a href="https://api.nerranetwork.com/voices/admin/triage?token=${await triageToken(env)}">triage page</a>;
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

  // Oct 5 2026 (Piper Martz): the "closing session" event type books a short
  // session that records only the closing round of an interview the old
  // time cap cut off. It is always its own row, pointing at the interview
  // it finishes.
  const eventTitle = String(p.title ?? p.eventTitle ?? p.eventType?.title ?? "");
  const closing = /closing/i.test(eventSlug) ||
    /finishing our conversation/i.test(eventTitle);
  let continues: string | null = null;
  if (closing) {
    const prev = await sb(env, "GET",
      `interviews?application_id=eq.${apps[0].id}&session_kind=eq.interview` +
      `&status=not.in.(scheduled,briefed,cancelled,missed)&order=scheduled_at.desc&limit=1&select=id`);
    continues = prev?.[0]?.id ?? null;
  }
  // Oct 21 2026: the five-minute hello two days before the interview. Its
  // own row (session_kind "hello", five minutes) pointing at the guest's
  // scheduled interview, so the agenda it produces lands on the right one.
  const hello = !closing && isHelloBooking(env, eventSlug, eventTypeId, eventTitle);
  let helloFor: string | null = null;
  if (hello) {
    const main = await sb(env, "GET",
      `interviews?application_id=eq.${apps[0].id}&session_kind=eq.interview` +
      `&status=in.(scheduled,briefed)&order=scheduled_at.asc&limit=1&select=id`);
    helloFor = main?.[0]?.id ?? null;
    if (!helloFor) console.warn(`cal-com-booked: hello for ${emailAddr} has no scheduled interview to precede`);
  }
  const kind = closing ? "closing" : hello ? "hello" : "interview";
  const existing = await sb(env, "GET",
    `interviews?application_id=eq.${apps[0].id}&session_kind=eq.${kind}&status=in.(scheduled,briefed)&limit=1`);
  let interviewId: string;
  if (existing?.length) {
    interviewId = existing[0].id;
    await sb(env, "PATCH", `interviews?id=eq.${interviewId}`,
      { scheduled_at: startTime, status: "scheduled", reminder_sent_at: null, show: show.slug,
        cal_booking_uid: String(p.uid ?? "") || null,
        // Oct 27 2026: a new time starts its alerts afresh.
        start_notice_at: null, late_alert_at: null, studio_seen_at: null,
        studio_reschedule_sent_at: null, studio_kick_at: null, studio_alert_at: null,
        guest_timezone: attendeeTimeZone(p),
        duration_min: closing ? 15 : hello ? HELLO_MINUTES : plannedMinutes, host_mode: false,
        ...(hello ? { hello_for_interview_id: helloFor } : {}) });
  } else {
    const created = await sb(env, "POST", "interviews",
      { application_id: apps[0].id, scheduled_at: startTime, status: "scheduled", show: show.slug,
        cal_booking_uid: String(p.uid ?? "") || null,
        guest_timezone: attendeeTimeZone(p),
        duration_min: closing ? 15 : hello ? HELLO_MINUTES : plannedMinutes, host_mode: false,
        ...(closing ? { session_kind: "closing", continues_interview_id: continues } : {}),
        ...(hello ? { session_kind: "hello", hello_for_interview_id: helloFor } : {}) },
      "return=representation");
    interviewId = created?.[0]?.id ?? "";
  }
  const studio = studioUrl(show, interviewId, "guest");
  const setupTest = `${studio}&test=1`;
  // Oct 1 2026 (Jonathan Bautista, Jason Fishman): the calendar invite's
  // "Where" was a Cal Video room. Both guests clicked it at the start time,
  // sat in an empty room that said "waiting for others to join", and wrote
  // that nobody came; both interviews fell back to the phone. The invite now
  // carries the guest's own studio link.
  await setCalendarLocation(env, show, String(p.uid ?? p.bookingUid ?? ""), studio, apps[0].name);
  let manage = "";
  try {
    const tok = await sb(env, "GET", `interviews?id=eq.${interviewId}&select=manage_token`);
    if (tok?.[0]?.manage_token) manage = `https://api.nerranetwork.com/voices/manage/${encodeURIComponent(tok[0].manage_token)}`;
  } catch { /* the calendar invite carries its own reschedule link */ }
  const when = bookedWhen(startTime, p);
  // Sept 28 2026: written by Mira, in the first person, like everything else
  // a guest receives. It used to speak about "Mira, our AI host".
  // Oct 5 2026: prepare the studio now rather than on a later tick, so a
  // short-notice booking has its room ready long before the start.
  try { await dispatch(env, "fire-tick", { source: "booking", interview_id: interviewId }); }
  catch (err: any) { console.error("booking fire-tick dispatch failed:", err?.message ?? err); }
  if (closing) {
    await email(env, emailAddr, `Thank you for coming back to finish our ${show.name} conversation`,
      `<p>Hi ${esc(firstName(apps[0].name))},</p>
       <p>Thank you so much for making the time. We're on${when ? ` for <strong>${esc(when)}</strong>` : ""}.
       It will only take a few minutes: we'll pick up the quick lightning round where we left off, a couple
       of closing questions, and your last word, and it all goes onto the end of the conversation we already
       recorded. There's no time limit this time.</p>
       ${GUEST_AUDIO_HTML}
       ${studioStepsHtml(studio)}
       <p>${manage ? `If you need to move it, <a href="${esc(manage)}">use this link</a>.` : "If you need to move it, use the reschedule link in your calendar confirmation."}</p>
       ${miraSignature(show)}`, true);
    await slack(env, `${show.shortLabel}: ${apps[0].name} booked a closing session ${pacificTime(startTime)}`);
    return json({ ok: true, show: show.slug, interview_id: interviewId, closing: true });
  }
  if (hello) {
    // The usual confirmation shape — the studio link and the three steps —
    // and no prep brief: the brief belongs to the interview, and the hello
    // is where the guest tells Mira what it should reach.
    await email(env, emailAddr, `Our five-minute hello before ${show.name}`,
      `<p>Hi ${esc(firstName(apps[0].name))},</p>
       <p>Thank you for booking the hello. We're on${when ? ` for <strong>${esc(when)}</strong>` : ""},
       and it is five minutes: I say hello, we check your sound, and you tell me the one or
       two things you most want our conversation to reach. That becomes the shape of the hour.</p>
       <p><a href="${studio}"><strong>This is your personal studio link</strong></a>. Bookmark
       it: the studio opens ${STUDIO_OPENS_BEFORE_TEXT} before we start, and there is nothing to install.</p>
       ${GUEST_AUDIO_HTML}
       ${studioStepsHtml(studio)}
       <p>${manage ? `If you need to move it, <a href="${esc(manage)}">use this link</a>.` : "If you need to move it, use the reschedule link in your calendar confirmation."}</p>
       ${miraSignature(show)}`, true, publicistCc(apps[0]));
    await slack(env, `${show.shortLabel}: ${apps[0].name} booked a five-minute hello ${pacificTime(startTime)}` +
      (helloFor ? "" : " (no scheduled interview found to attach it to)"));
    return json({ ok: true, show: show.slug, interview_id: interviewId, hello: true, hello_for_interview_id: helloFor });
  }
  await email(env, emailAddr, `You're booked on ${show.name}`,
    `<p>Hi ${esc(firstName(apps[0].name))},</p>
     <p>Thank you for booking. We're on${when ? ` for <strong>${esc(when)}</strong>` : ""}.
     I'm Mira, the AI host of ${esc(show.name)}, and it will be just the two of us.</p>
     ${subjectHtml(interviewSubject(null, apps[0], true))}
     <p><a href="${studio}"><strong>This is your personal studio link</strong></a>. Bookmark
     it: the studio opens ${STUDIO_OPENS_BEFORE_TEXT} before we start, and there is nothing to install.</p>
     ${GUEST_AUDIO_HTML}
     <p>You can run the <a href="${setupTest}">30-second setup test</a> any time before
     the day. It confirms I'll hear you clearly. This is an audio conversation: I'm a voice,
     with nothing on screen, and your camera is optional.</p>
     ${studioStepsHtml(studio)}
     <p>We have about ${plannedMinutes} minutes${apps[0].desired_minutes ? ", which is what you asked for" : ""}. I pace the
     conversation to that and start wrapping up near the end rather than cutting you off.</p>
     <p>About a day before, I'll send a short brief with the themes I'd like to explore.
     You can reply to any of my emails with thoughts, corrections, or anything you would
     rather not discuss, and I'll take it into the conversation.</p>
     ${GUEST_YOUR_HOUR_HTML}
     <p>The conversation is recorded. You get the transcript first, with a week to approve it,
     cut anything from it or refuse it; after seven days without a reply the episode goes
     ahead as sent, and you can ask for a takedown at any time.${manage ? ` If you need to move or cancel, <a href="${esc(manage)}">use this link</a>; one tap, no explanation needed.` : " If you need to move the time, use the reschedule link in your calendar confirmation."}</p>
     ${miraSignature(show)}`, true, publicistCc(apps[0]));
  await slack(env, `${show.shortLabel}: ${apps[0].name} booked ${pacificTime(startTime)}`);
  return json({ ok: true, show: show.slug, interview_id: interviewId });
}

async function handleTriageDecision(req: Request, env: Env): Promise<Response> {
  const denied = await requireTriageAccess(req, env);
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
    const mins = clampMinutes(app.desired_minutes) ?? 45;
    await email(env, app.email, `You're invited to ${show.name}`,
      `<p>Hi ${esc(firstName(app.name))},</p>
       <p>Thank you for applying. I'd love to have you on ${esc(show.name)}. Pick a time
       that works for you here, booking with this email address so everything reaches you:</p>
       <p><a href="${esc(link)}">${esc(link)}</a></p>
       <p>Once you book, you'll get a confirmation with your personal studio link. We talk
       from a computer browser with headphones or earbuds on; there is nothing to install.
       The conversation runs about ${mins} minutes and it's recorded. You get the transcript
       first, with a week to approve it, cut anything from it or refuse it before it
       publishes. Past conversations are at
       <a href="${esc(SITE + "/" + show.page)}">${esc(SITE + "/" + show.page)}</a> if you'd
       like a sense of the show first.</p>
       ${KITS_INTRO_HTML}
       ${miraSignature(show)}`, true);
  }
  if (app && body.decision === "declined" && app.email) {
    // Sept 18 2026: a declined application used to hear nothing at all.
    // Everyone who took the time to apply gets an answer, the same one,
    // and a publicist who pitched them is copied so they are not left
    // chasing.
    const show = showFor(app);
    try {
      await email(env, app.email, `Your ${show.name} application`,
        `<p>Hi ${esc(firstName(app.name))},</p>
         <p>Thank you for applying to be a guest on ${esc(show.name)}, and for the time you
         put into telling me about your work.</p>
         <p>I'm not able to find a place for it on the show at the moment. I record a small
         number of conversations and choose them around what each one lets me ask that no
         other guest could, which means turning down more people than I would like to,
         including many with real things to say.</p>
         <p>I keep every application, and if your work takes a turn that would give us a
         specific story to sit down over, you are welcome to apply again.</p>
         ${miraSignature(show)}`, true,
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
  const denied = await requireTriageAccess(req, env);
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
  if (!body?.package_id || !["approve", "kill", "archive", "correction_made"].includes(body.decision)) {
    return json({ error: "package_id + decision(approve|kill|archive|correction_made) required" }, 400);
  }
  // Scoped to the package being decided: a review link can approve or kill
  // its own episode and nothing else.
  const denied = await requirePackageAccess(req, env, String(body.package_id));
  if (denied) return denied;
  if (body.decision === "archive") {
    const resp = await archivePackage(env, String(body.package_id), String(body.notes ?? "").trim() || "archived from the review page");
    if (!resp.ok) return resp;
    return json({ ...(await resp.json<any>()), message: "Archived: kept, never published. Nothing was sent to the guest." });
  }
  // Oct 21 2026: a second Approve used to resend the guest's review email
  // and push their seven-day deadline out again. Approve is idempotent now:
  // a package already past gate 1 keeps its deadline and its email.
  const before = (await sb(env, "GET",
    `editorial_packages?id=eq.${body.package_id}&limit=1`))?.[0];
  if (!before) return json({ error: "package not found" }, 404);
  if (body.decision === "correction_made") return correctionMade(env, before, body);
  if (body.decision === "approve"
      && ["approved_by_patrick", "approved_by_guest", "published"].includes(String(before.status))) {
    return json({ ok: true, already: before.status,
      message: `Already approved${before.patrick_reviewed_at ? ` on ${pacificTime(before.patrick_reviewed_at)}` : ""}. ` +
        "Nothing was sent again and the guest's deadline is unchanged." });
  }
  const now = new Date().toISOString();
  // Oct 24 2026: approving after the guest asked for changes means the
  // changes are made. Their requests are marked resolved, and the email
  // tells them what this version has, instead of the standard text alone.
  const open = body.decision === "approve" ? openRequests(before).filter((r) => r.kind !== "correction") : [];
  const status = body.decision === "approve" ? "approved_by_patrick" : "killed";
  const rows = await sb(env, "PATCH", `editorial_packages?id=eq.${body.package_id}`, {
    status,
    patrick_reviewed_at: now,
    patrick_notes: body.notes ?? null,
    ...(body.decision === "approve"
      ? { guest_review_deadline: new Date(Date.now() + 7 * 864e5).toISOString() }
      : {}),
    ...(open.length
      ? { guest_redactions: (before.guest_redactions ?? []).map((r: any) =>
          r && !r.resolved && r.kind !== "correction" ? { ...r, resolved: true, resolved_at: now, resolved_by: "patrick" } : r) }
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
    const asked = open.map((r) => String(r.note ?? "").trim()).filter((n) => n && !/^\d+ marked line/.test(n));
    const markedLines = open.reduce((n, r) => n + (Number(r.lines ?? 0) || 0), 0);
    const changesHtml = open.length
      ? `<p>This version has the changes you asked for${asked.length ? ":" : "."}</p>` +
        (asked.length ? `<blockquote style="border-left:3px solid #ccc;margin:0 0 1em;padding-left:1em">${asked.map((a) => esc(a)).join("<br>")}</blockquote>` : "") +
        (markedLines ? `<p>The ${markedLines} line${markedLines === 1 ? "" : "s"} you marked ${markedLines === 1 ? "is" : "are"} cut from the audio and the transcript.</p>` : "")
      : "";
    await email(env, app.email, open.length
        ? `Your changes are made: your ${show.shortLabel} episode is ready to hear again`
        : `Thank you — your ${show.shortLabel} episode is ready for you`,
      `<p>Hi ${esc(firstName(app.name))},</p>
       ${noteHtml}
       ${changesHtml}
       <p>${open.length
         ? "Have another listen. Nothing goes out until you have heard it and said yes."
         : "Thank you for the time you gave me. Your episode is edited and ready, and nothing goes out until you have heard it and said yes."}</p>
       <p><a href="${esc(link)}">Listen to the episode and read the transcript</a></p>
       <p>At the bottom of that page you pick one of three things: approve it
       as it stands, approve it with a small correction (like a name said
       wrong or a figure to fix), or ask for changes before anything is
       published. You see your choice once more before it is sent, the page
       shows you what was recorded, and I email you a copy.</p>
       <p>Two other things are on the page, and I mean them. If the
       conversation didn't catch you at your best, you can ask to record it
       again from scratch; I would rather re-record than publish something
       you are lukewarm about. And you can put yourself down to come back in
       six months or a year to tell me what has actually changed in your
       field since we spoke. That follow-up is the part of this show I care
       most about: almost nobody goes back to check.</p>
       <p>One more thing, and it is the part guests tell me they care about
       most: when this publishes I write a full post for the episode.
       There is a box on that page for anything you would like a listener
       to find next: a short biography in your own words, your site or
       book, papers or talks worth reading. Whatever you put there goes in
       the post.</p>
       <p>If I don't hear from you by ${esc(pacificTime(pkg.guest_review_deadline, null, true))}, I'll take
       that as approval, and I'll remind you a few days before. You can always ask
       for changes after publication too.</p>
       ${miraSignature(show)}`, true, publicistCc(app));
    await slack(env, `${show.shortLabel}: Patrick approved package ${pkg.id} — guest review email sent` +
      (open.length ? ` (their ${open.length} request(s) marked done)` : ""));
    return json({ ok: true, status, emailed_to: app.email,
      deadline: pkg.guest_review_deadline, resolved: open.length,
      message: `Approved at ${pacificTime(now)}. Mira emailed ${app.name ?? "the guest"} (${app.email}) ` +
        `${open.length ? "the new cut, with the changes they asked for listed" : "the review link"}. ` +
        `Their deadline: ${pacificTime(pkg.guest_review_deadline, null, true)}.` });
  }
  await sb(env, "PATCH", `interviews?id=eq.${pkg.interview_id}`, { status: "failed" });
  await slack(env, `${show.shortLabel}: Patrick KILLED package ${pkg.id}`);
  return json({ ok: true, status, message: "Killed. Nothing was sent to the guest." });
}

/** Oct 24 2026: the guest approved with one correction (a name said wrong,
 *  a figure). Patrick makes it, re-assembles, listens, and presses
 *  "Correction made": the guest's approval then stands, production is
 *  dispatched, and Mira tells the guest it is done. They review nothing
 *  twice for a pronunciation. */
async function correctionMade(env: Env, pkg: any, body: any): Promise<Response> {
  const corr = openRequests(pkg).find((r) => r.kind === "correction" && r.approves);
  if (!corr) return json({ ok: false, error: "There is no open correction on this episode." }, 409);
  const now = new Date().toISOString();
  // approved_by_patrick first, so a failed dispatch below is retried by
  // gate-2 housekeeping (it re-dispatches packages whose interview is approved).
  await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`, {
    status: "approved_by_patrick",
    patrick_notes: body.notes ?? pkg.patrick_notes ?? null,
    guest_review_deadline: pkg.guest_review_deadline ?? now,
    guest_redactions: (pkg.guest_redactions ?? []).map((r: any) =>
      r && !r.resolved && r.kind === "correction" ? { ...r, resolved: true, resolved_at: now, resolved_by: "patrick" } : r),
  });
  const { app, show } = await interviewWithApp(env, pkg.interview_id);
  let dispatched = true;
  try {
    await approveAndDispatch(env, { ...pkg, guest_reviewed_at: pkg.guest_reviewed_at ?? corr.at ?? now },
      pkg.interview_id, now);
  } catch (err: any) {
    dispatched = false;
    await slack(env, `:warning: ${show.shortLabel}: correction made on ${pkg.id} but the production dispatch failed (${String(err?.message ?? err).slice(0, 120)}); gate-2 housekeeping retries daily.`);
  }
  let emailed = "";
  if (app?.email) {
    const note = String(body.note_to_guest ?? "").trim();
    try {
      await email(env, app.email, `Done: your correction to your ${show.shortLabel} episode`,
        `<p>Hi ${esc(firstName(app.name))},</p>
         ${note ? `<p>${esc(note).replace(/\n/g, "<br>")}</p>` : ""}
         <p>Your correction is made:</p>
         <blockquote style="border-left:3px solid #ccc;margin:0 0 1em;padding-left:1em">${esc(String(corr.note ?? ""))}</blockquote>
         <p>Your approval stands, so there is nothing more for you to do.
         Patrick publishes the episode next, and I will email you when it is live.</p>
         <p>The <a href="https://api.nerranetwork.com/voices/review/${esc(pkg.guest_review_token)}">review page</a> shows where things stand at any time.</p>
         ${miraSignature(show)}`, true, publicistCc(app));
      emailed = app.email;
    } catch (err: any) { console.error("correction-made email failed:", err?.message ?? err); }
  }
  await slack(env, `${show.shortLabel}: correction made on ${pkg.id}; the guest's approval stands` +
    (dispatched ? " — production dispatched" : ""));
  return json({ ok: true, status: dispatched ? "approved_by_guest" : "approved_by_patrick", dispatched, emailed_to: emailed,
    message: `Correction marked made at ${pacificTime(now)}. ${app?.name ?? "The guest"}'s approval stands; ` +
      `${dispatched ? "production is dispatched" : "the production dispatch failed and housekeeping retries it daily"}. ` +
      `${emailed ? `Mira emailed ${emailed} to say it is done.` : "No email address on file, so nobody was emailed."}` });
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
  const packageId = String(body?.package_id ?? "");
  const denied = await requirePackageAccess(req, env, packageId);
  if (denied) return denied;
  // Oct 21 2026: any package's review token could activate or retire ANY
  // lesson, network-wide ones included. The token now decides only the
  // lessons its own interview proposed; a show's standing lesson or a
  // network lesson needs the admin token.
  const lesson = (await sb(env, "GET",
    `show_lessons?id=eq.${lessonId}&select=id,show,interview_id,status&limit=1`))?.[0];
  if (!lesson) return json({ error: "lesson not found" }, 404);
  const viaReviewLink = !!requireAdmin(req, env);
  if (viaReviewLink) {
    const pkg = UUID_RE.test(packageId)
      ? (await sb(env, "GET", `editorial_packages?id=eq.${packageId}&select=id,interview_id&limit=1`))?.[0]
      : null;
    if (!lessonDecisionAllowed(lesson, pkg)) {
      return json({ error: "this review link may only decide lessons from its own interview" }, 403);
    }
  }
  const rows = await sb(env, "PATCH", `show_lessons?id=eq.${lessonId}`,
    { status, decided_at: new Date().toISOString(),
      decided_by: viaReviewLink ? "patrick:review-link" : "patrick" },
    "return=representation");
  if (!rows?.[0]) return json({ error: "lesson not found" }, 404);
  return json({ ok: true, id: lessonId, status });
}

/** May a package's review token decide this lesson? Only when the lesson
 *  was proposed by that package's interview and is not network-scoped. */
export function lessonDecisionAllowed(lesson: { show?: unknown; interview_id?: unknown },
                                      pkg: { interview_id?: unknown } | null | undefined): boolean {
  if (!pkg || !pkg.interview_id || !lesson.interview_id) return false;
  if (String(lesson.show ?? "") === "network") return false;
  return String(lesson.interview_id) === String(pkg.interview_id);
}

/** POST /voices/narration-take {take_id, status, record_url?, detail?}
 *  The scenario's narrationSession reports here when Mira has finished
 *  reading one paragraph of a scripted pickup (Sept 11 2026). No auth: the
 *  take_id is an opaque row that must already exist, and the only thing this
 *  can do is attach a Voximplant recording URL to it. */
async function handleNarrationTake(req: Request, env: Env): Promise<Response> {
  const { body, denied } = await readSignedJson(req, env, true);
  if (denied) return denied;
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
    ? pacificTime(interview.scheduled_at, interview.guest_timezone)
    : "your scheduled time";
  // Oct 5 2026: a Nerra Voices guest was offered the Age of AI booking page.
  const booking = bookingUrl(env, show) || "";
  if (interview.status === "cancelled" || interview.cancelled_at) {
    return html(page("Already cancelled",
      `<p>Thanks — your ${esc(show.shortLabel)} interview is cancelled and nobody is waiting for you.</p>` +
      (booking ? `<p>Whenever you want to pick it up again: <a href="${esc(booking)}">book a new time</a>.</p>` : "")));
  }
  return html(page(`Your ${esc(show.shortLabel)} interview`, `
    <p>Hi ${esc(firstName(app.name))} — your interview is set for <strong>${esc(when)}</strong>.</p>
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
  const booking = bookingUrl(env, show) || "";
  const now = new Date().toISOString();

  if (action === "cancel") {
    await sb(env, "PATCH", `interviews?id=eq.${interview.id}`,
      { status: "cancelled", cancelled_at: now, cancel_reason: note || null });
    await slack(env, `${app.name ?? "A guest"} cancelled their ${show.shortLabel} interview` +
      (note ? `: ${note}` : ""));
    await email(env, operatorEmail(env),
      `${show.shortLabel}: ${app.name ?? "a guest"} cancelled`,
      `<p>${esc(app.name ?? "A guest")} cancelled their interview` +
      `${interview.scheduled_at ? ` (was ${esc(pacificTime(interview.scheduled_at))})` : ""}.</p>` +
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

// -- Where a review stands (Oct 24 2026) ---------------------------------------
// Piper Martz's only note on her episode was a pronunciation. The page's only
// button for it was "Submit removal requests"; it told her "we will apply the
// removals and confirm by email", and then nothing she could see happened for
// four days: no email, no change on the page, and nobody was nudged. Patrick's
// own page answered every click with one word, "Saved." So: every review page
// now opens on where things stand, every choice is shown back before it is
// sent, what was recorded is read back from the database and shown on the
// page and emailed, and Patrick's page says what his click did and to whom.

export type ReviewRequest = {
  kind?: string; note?: string; resolved?: boolean; at?: string;
  approves?: boolean; lines?: number; resolved_at?: string;
};

/** The guest's requests on a package that nobody has resolved yet. */
export function openRequests(pkg: any): ReviewRequest[] {
  const list = Array.isArray(pkg?.guest_redactions) ? pkg.guest_redactions : [];
  return list.filter((r: any) => r && typeof r === "object" && !r.resolved);
}

/** The most recent request that was resolved, if any. */
export function lastResolved(pkg: any): ReviewRequest | null {
  const list = (Array.isArray(pkg?.guest_redactions) ? pkg.guest_redactions : [])
    .filter((r: any) => r && r.resolved && r.resolved_at);
  return list.length ? list[list.length - 1] : null;
}

export type GuestDecision = "approve" | "correction" | "changes";

/** What the guest chose. Lines marked for cutting make it a change request
 *  whatever was pressed (as before); the old {approve: bool} body still works. */
export function guestDecision(body: any, markedLines: number): GuestDecision {
  const asked = String(body?.decision ?? "");
  let d: GuestDecision = asked === "correction" || asked === "changes" || asked === "approve"
    ? asked as GuestDecision : (body?.approve ? "approve" : "changes");
  if (markedLines > 0 && d !== "changes") d = "changes";
  return d;
}

export type ReviewState = { code: string; headline: string; detail: string };

const dayOf = (iso: unknown) => pacificTime(iso, null, true);
const quoteOf = (s: unknown, max = 240) => {
  const t = String(s ?? "").replace(/\s+/g, " ").trim();
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
};

/** Where things stand, in the guest's terms, for the top of their page and
 *  for the copy Mira emails them. Pure, so it is tested on its own. */
export function guestReviewState(pkg: any): ReviewState {
  const status = String(pkg?.status ?? "");
  const open = openRequests(pkg);
  if (status === "archived") return { code: "archived", headline: "This recording has been retired.",
    detail: "It will not be published. If a new recording is planned, you will get a new link for it." };
  if (status === "killed") return { code: "killed", headline: "This episode will not be published.",
    detail: "Questions? Reply to any of Mira's emails." };
  if (status === "published") return { code: "published", headline: "Your episode is published.",
    detail: "Thank you. If you want anything changed now, reply to any of Mira's emails." };
  if (status === "approved_by_guest") return { code: "approved",
    headline: `You approved this episode${pkg?.guest_reviewed_at ? ` on ${dayOf(pkg.guest_reviewed_at)}` : ""}.`,
    detail: "Nothing more is needed from you. Patrick publishes it next, and Mira will email you when it is live. " +
      "You can still ask for a change by replying to any of her emails." };
  const correction = open.find((r) => r.kind === "correction" && r.approves);
  if (correction) return { code: "correction_pending",
    headline: `You approved this on ${dayOf(correction.at || pkg?.guest_reviewed_at)}, with one correction.`,
    detail: `Your correction: “${quoteOf(correction.note)}”. Patrick has it. Once it is made, your approval stands ` +
      "and Mira will email you to say so. You will not need to review the episode again." };
  if (open.length) {
    const r = open[0];
    const lines = Number(r.lines ?? 0) || (Array.isArray(pkg?.guest_redaction_windows) ? pkg.guest_redaction_windows.length : 0);
    const what = [r.note && !/^\d+ marked line/.test(String(r.note)) ? `“${quoteOf(r.note)}”` : "",
      lines ? `${lines} line${lines === 1 ? "" : "s"} marked for cutting` : ""].filter(Boolean).join(" and ");
    return { code: "changes_pending",
      headline: `You asked for changes on ${dayOf(r.at || pkg?.guest_reviewed_at)}.`,
      detail: `${what ? `What you asked for: ${what}. ` : ""}Patrick has them. When the new cut is ready, Mira will ` +
        "email you to listen again. Nothing is published until you have heard it." };
  }
  const done = lastResolved(pkg);
  if (status === "approved_by_patrick" && done) return { code: "changes_made",
    headline: `Your changes are made (${dayOf(done.resolved_at)}).`,
    detail: "Listen again below, then choose. Nothing is published until you do." +
      (pkg?.guest_review_deadline ? ` If we have not heard from you by ${dayOf(pkg.guest_review_deadline)}, we will take that as approval.` : "") };
  if (status === "approved_by_patrick") return { code: "waiting",
    headline: "Waiting for you. Nothing is published until you choose.",
    detail: pkg?.guest_review_deadline
      ? `If we have not heard from you by ${dayOf(pkg.guest_review_deadline)}, we will take that as approval.`
      : "Take your time." };
  return { code: "with_patrick", headline: "This episode is with Patrick for a final check.",
    detail: "Mira will email you when it is ready for you to hear." };
}

/** Where things stand, in Patrick's terms, for the top of the gate-1 page. */
export function operatorReviewState(pkg: any, guestName: string, guestEmail: string): ReviewState {
  const status = String(pkg?.status ?? "");
  const name = guestName || "The guest";
  const open = openRequests(pkg);
  const when = (iso: unknown) => pacificTime(iso);
  const correction = open.find((r) => r.kind === "correction" && r.approves);
  if (correction) return { code: "correction_pending",
    headline: `${name} approved on ${when(correction.at || pkg?.guest_reviewed_at)}, with one correction.`,
    detail: `Their correction: “${quoteOf(correction.note, 500)}”. Make it, re-run the assemble workflow, listen, then press ` +
      "“Correction made”: their approval then stands, production starts, and Mira tells them it is done." };
  if (open.length) {
    const r = open[0];
    const lines = Number(r.lines ?? 0) || (Array.isArray(pkg?.guest_redaction_windows) ? pkg.guest_redaction_windows.length : 0);
    return { code: "changes_pending",
      headline: `${name} asked for changes on ${when(r.at || pkg?.guest_reviewed_at)}.`,
      detail: `${r.note ? `“${quoteOf(r.note, 500)}” ` : ""}${lines ? `${lines} marked line${lines === 1 ? "" : "s"} ` +
        "come out automatically on the next assemble. " : ""}Make any other change, re-run the assemble ` +
        "workflow, listen, then press “Changes made: send the guest the new cut”." };
  }
  if (status === "approved_by_guest") return { code: "approved",
    headline: `${name} approved on ${when(pkg?.guest_reviewed_at)}. Production has been dispatched.`,
    detail: `Publishing is yours: gh workflow run nerra_voices_publish.yml -f interview_id=${pkg?.interview_id ?? ""}` };
  if (status === "approved_by_patrick") return { code: "with_guest",
    headline: `You approved this on ${when(pkg?.patrick_reviewed_at)}. Mira emailed the review link to ${name}` +
      `${guestEmail ? ` (${guestEmail})` : ""}.`,
    detail: pkg?.guest_review_deadline
      ? `Waiting for them. If they do not answer, it counts as approved on ${dayOf(pkg.guest_review_deadline)}.`
      : "Waiting for them." };
  if (status === "published") return { code: "published", headline: "Published.", detail: "" };
  if (status === "killed") return { code: "killed", headline: "Killed. The guest was not emailed.", detail: "" };
  if (status === "archived") return { code: "archived", headline: "Archived: kept, never published.", detail: "" };
  return { code: "waiting", headline: "Waiting for you (gate 1). Nothing has gone to the guest.",
    detail: "Approve sends the guest their review email from Mira. Kill and Archive send them nothing." };
}

const STATE_COLORS: Record<string, [string, string]> = {
  waiting: ["#fffbeb", "#b45309"], with_patrick: ["#f7fafc", "#4a5568"], with_guest: ["#eff6ff", "#1d4ed8"],
  correction_pending: ["#fff7ed", "#c2410c"], changes_pending: ["#fff7ed", "#c2410c"],
  changes_made: ["#eff6ff", "#1d4ed8"], approved: ["#f0fdf4", "#166534"], published: ["#f0fdf4", "#166534"],
  archived: ["#f7fafc", "#4a5568"], killed: ["#fef2f2", "#991b1b"],
};

/** The status box both review pages open on. */
export function stateBoxHtml(s: ReviewState, id = "state"): string {
  const [bg, fg] = STATE_COLORS[s.code] ?? ["#f7fafc", "#1a202c"];
  return `<div id="${id}" data-state="${esc(s.code)}" style="background:${bg};border-left:6px solid ${fg};` +
    `border-radius:8px;padding:.8rem 1rem;margin:1rem 0"><div style="font-weight:700;color:${fg}">${esc(s.headline)}</div>` +
    (s.detail ? `<div style="margin-top:.3rem">${esc(s.detail)}</div>` : "") + `</div>`;
}

const DECISION_LABEL: Record<GuestDecision, string> = {
  approve: "Approve it as it is",
  correction: "Approve, with a small correction",
  changes: "Ask for changes before it is published",
};

const FOLLOWUP_LABEL: Record<string, string> = {
  return_6: "Come back in about six months", return_12: "Come back in about a year",
  return_other: "Come back, at a different time", redo: "Record the conversation again from scratch",
  none: "Nothing for now",
};

/** What the database now holds for a guest's submission, as rows for the
 *  page's receipt and the email copy. Built from the package as re-read
 *  after the writes, not from what the browser sent. */
export function guestReceipt(pkg: any, decision: GuestDecision): Array<[string, string]> {
  const rows: Array<[string, string]> = [["Your choice", DECISION_LABEL[decision]]];
  if (pkg?.guest_reviewed_at) rows.push(["Recorded", pacificTime(pkg.guest_reviewed_at)]);
  const req = (Array.isArray(pkg?.guest_redactions) ? pkg.guest_redactions : []).slice(-1)[0];
  if (decision !== "approve" && req?.note && !/^\d+ marked line/.test(String(req.note))) {
    rows.push([decision === "correction" ? "Your correction" : "What you asked for", quoteOf(req.note, 2000)]);
  }
  const windows = Array.isArray(pkg?.guest_redaction_windows) ? pkg.guest_redaction_windows : [];
  if (decision === "changes" && windows.length) {
    rows.push([`Lines marked for cutting (${windows.length})`,
      windows.map((w: any) => quoteOf(w?.line, 160)).join("\n")]);
  }
  rows.push(["Your answer to Mira's question", pkg?.guest_experience ? "Received, thank you" : "None"]);
  rows.push(["For your episode's post", pkg?.guest_materials ? "Received, thank you" : "Nothing sent"]);
  rows.push(["Coming back", FOLLOWUP_LABEL[String(pkg?.guest_followup ?? "none")] ?? "Nothing for now"]);
  return rows;
}

export function receiptHtml(rows: Array<[string, string]>): string {
  return `<table style="border-collapse:collapse;margin:.5rem 0">${rows.map(([k, v]) =>
    `<tr><td style="padding:.25rem .8rem .25rem 0;vertical-align:top;color:#4a5568;white-space:nowrap">${esc(k)}</td>` +
    `<td style="padding:.25rem 0;white-space:pre-wrap">${esc(v)}</td></tr>`).join("")}</table>`;
}

async function handleGuestReviewPage(env: Env, token: string): Promise<Response> {
  const pkg = await pkgByToken(env, token);
  if (!pkg) return html("<h1>Link not found</h1>", 404);
  if (pkg.status === "archived") {
    return html(page("This recording has been retired",
      "<p>This recording will not be published, so there is nothing to review here. " +
      "If a new recording is planned, you will get a new link for it. Questions? " +
      "Reply to any of Mira's emails.</p>"));
  }
  const { show } = await interviewWithApp(env, pkg.interview_id);
  const state = guestReviewState(pkg);
  // Oct 24 2026: a guest who comes back to the link sees where things stand
  // and what they chose, not a bare "Already approved".
  const closed = ["approved", "published", "archived", "killed"].includes(state.code);
  const pending = ["correction_pending", "changes_pending"].includes(state.code);
  if (closed) {
    const rows = state.code === "approved" || state.code === "published"
      ? guestReceipt(pkg, "approve") : [];
    return html(page(`Your ${esc(show.shortLabel)} episode`,
      stateBoxHtml(state) + (rows.length ? `<h3>What you chose</h3>${receiptHtml(rows)}` : ""),
      show.brandColor));
  }
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
  // Oct 5 2026: the only outside opinion on how Mira interviews was the
  // question she asks at the end of the hour, live, which a guest who was
  // cut off or hung up never heard. Asked again here, after they have heard
  // themselves, with the one question her grading pass wanted to put to
  // this guest; the answer goes into every later grading pass.
  const grade = (await sb(env, "GET",
    `episode_grades?interview_id=eq.${pkg.interview_id}&select=ask_the_guest&limit=1`))?.[0];
  const askGuest = String(grade?.ask_the_guest ?? "").trim() ||
    "How was it, being interviewed by an AI? Is there one thing I could do better next time?";
  // Oct 21 2026: the guest approves the transcript of the EDIT when the
  // pipeline has written one (editorial_packages.edit_transcript), else the
  // room's transcript as before — they used to sign off lines the edit had
  // already removed. Each timed line is clickable; a click marks a cut
  // with its time window, which the edit applies in code.
  const editTranscript = String(pkg.edit_transcript ?? "").trim();
  const transcriptText = editTranscript
    || (pkg.transcript_cleaned || "").trim() || (pkg.transcript_raw || "").trim();
  const transcriptHtml = reviewTranscriptHtml(transcriptText);
  const deadline = pkg.guest_review_deadline ? pacificTime(pkg.guest_review_deadline, null, true) : "";
  return html(`<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Review your ${esc(show.shortLabel)} conversation</title>
<style>body{font:16px/1.6 system-ui;max-width:760px;margin:2rem auto;padding:0 1rem;color:#1a202c}
pre{white-space:pre-wrap;background:#f7fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;max-height:60vh;overflow:auto}
.ln{cursor:pointer;display:block;padding:.1rem .3rem;border-radius:4px}.ln:hover{background:#edf2f7}
.ln.cut{background:#fed7d7;text-decoration:line-through}
textarea{width:100%;min-height:90px}button{background:${show.brandColor};color:#fff;border:0;border-radius:8px;padding:.7rem 1.4rem;font-size:1rem;cursor:pointer;margin:.3rem .6rem .3rem 0}
button:disabled{opacity:.5;cursor:default}.secondary{background:#4a5568}
.choice{display:block;border:2px solid #e2e8f0;border-radius:10px;padding:.8rem 1rem;margin:.6rem 0;cursor:pointer}
.choice:has(input:checked){border-color:${show.brandColor};background:#f7fafc}
.choice b{display:inline-block;margin-left:.3rem}.choice small{display:block;color:#4a5568;margin:.2rem 0 0 1.7rem}
.extra{margin:.5rem 0 0 1.7rem;display:none}.choice:has(input:checked) .extra{display:block}
#confirm,#receipt{border-radius:10px;padding:1rem 1.2rem;margin:1rem 0;display:none}
#confirm{background:#fffbeb;border:2px solid #b45309}#receipt{background:#f0fdf4;border:2px solid #166534}
#problem{color:#991b1b;font-weight:600}</style>
<h1>Your ${esc(show.shortLabel)} conversation</h1>
${stateBoxHtml(state)}
<p>Here is the recording and the transcript: this is what would be published.
Listen, read, and then make your choice at the bottom of the page.
Nothing is published until you have chosen${deadline ? ` (or until ${esc(deadline)}, when silence counts as approval)` : ""}.</p>
${listenUrl
  ? `<audio controls preload="none" src="${esc(listenUrl)}" style="width:100%;margin:1rem 0"></audio>`
  : `<p><em>The audio is still being processed — the transcript below is final. Check back shortly, or choose on the transcript alone.</em></p>`}
<h3>Transcript</h3>
${editTranscript
  ? `<p><em>This is the transcript of the edit a listener will hear, not of the whole recording.</em></p>`
  : ""}
<p style="color:#4a5568;font-size:.95rem">Want something cut? Click its line to mark it; click again to unmark. <span id="marked">Nothing marked.</span></p>
<pre id="transcript">${transcriptHtml}</pre>
${pending ? `<p><em>Your request is with Patrick, so there is nothing to choose here right now. To add to it, reply to any of Mira's emails.</em></p>` : `
<h3>One question from Mira (optional)</h3>
<p>${esc(askGuest)}</p>
<textarea id="experience" placeholder="Anything at all, including what irritated you. I read every answer, and it changes how I interview the next guest."></textarea>
<h3>Your episode's post (optional)</h3>
<p>When this is published we write a full post for it. Anything you'd like a
listener to find next goes in: a short biography in your own words, your
book or site, papers, talks, the project you were describing.</p>
<textarea id="materials" placeholder="A short bio, links to your work, papers or talks worth reading next."></textarea>
<h3>Coming back (optional)</h3>
<p>
<label><input type="radio" name="followup" value="return_6"> Come back in about six months and tell us what changed</label><br>
<label><input type="radio" name="followup" value="return_12"> Come back in about a year</label><br>
<label><input type="radio" name="followup" value="return_other"> I'd like to come back, but at a different time</label><br>
<label><input type="radio" name="followup" value="redo"> I'd rather record this conversation again from scratch</label><br>
<label><input type="radio" name="followup" value="none" checked> Nothing for now</label>
</p>
<textarea id="followupNote" placeholder="Anything you'd like us to know: a better time, what you'd want to talk about, or what you'd do differently in a re-record."></textarea>
<h3 id="decide">Your choice</h3>
<div id="choices">
<label class="choice"><input type="radio" name="decision" value="approve"><b>Approve it as it is</b>
<small>It goes to Patrick to publish. Nothing else is needed from you.</small></label>
<label class="choice"><input type="radio" name="decision" value="correction"><b>Approve, with a small correction</b>
<small>A name said wrong, a figure or a title to fix. Your approval stands once the correction is made, and you won't need to review again.</small>
<div class="extra"><textarea id="correction" placeholder="What should be corrected? For example: my company Aampe is said 'amp', not 'am-pee'."></textarea></div></label>
<label class="choice"><input type="radio" name="decision" value="changes"><b>Ask for changes before it is published</b>
<small>Something should come out, or be redone. Mark lines in the transcript and/or describe it here. You'll hear the new cut before anything is published.</small>
<div class="extra"><textarea id="redactions" placeholder="Anything a marked line cannot say: quote a passage, or describe the change, with a word on why if you like."></textarea></div></label>
</div>
<p id="problem"></p>
<p id="reviewBtnRow"><button id="reviewBtn" onclick="reviewChoice()">Review my choice</button></p>
<div id="confirm"><b>Please check this is right, then send it.</b>
<table id="confirmRows" style="border-collapse:collapse;margin:.5rem 0"></table>
<button id="sendBtn" onclick="sendChoice()">Send my choice</button>
<button class="secondary" id="backBtn" onclick="changeChoice()">Change something</button></div>
<div id="receipt"><b id="receiptHead"></b><p id="receiptDetail"></p>
<table id="receiptRows" style="border-collapse:collapse;margin:.5rem 0"></table>
<p id="receiptMail"></p></div>`}
<script>
// Sept 17 2026, Dr. Wolfberg: he pressed Approve, the request went through,
// and the only acknowledgement was a line at the very bottom of a long page
// he never scrolled to. Oct 24 2026, Piper Martz: a pronunciation note could
// only be sent as "removal requests", and what the page promised never came.
// Now: one explicit choice, shown back before it is sent, and the receipt is
// what the server recorded (read back from the database), where the button was.
const markedEl = document.getElementById('marked');
function markedWindows(){
  return Array.from(document.querySelectorAll('.ln.cut')).map(function(el){
    return {start_sec: Number(el.dataset.start), end_sec: Number(el.dataset.end), line: el.textContent};
  });
}
document.getElementById('transcript').addEventListener('click', function(ev){
  const el = ev.target.closest('.ln');
  if (!el || !document.getElementById('choices')) return;
  el.classList.toggle('cut');
  const n = document.querySelectorAll('.ln.cut').length;
  markedEl.textContent = n ? (n + ' line' + (n === 1 ? '' : 's') + ' marked for cutting. That makes your choice "Ask for changes".') : 'Nothing marked.';
  if (n) document.querySelector('input[name=decision][value=changes]').checked = true;
});
function val(id){ const el = document.getElementById(id); return el ? el.value.trim() : ''; }
function picked(){ const el = document.querySelector('input[name=decision]:checked'); return el ? el.value : ''; }
const LABELS = {approve: 'Approve it as it is', correction: 'Approve, with a small correction', changes: 'Ask for changes before it is published'};
const FOLLOW = {return_6: 'Come back in about six months', return_12: 'Come back in about a year', return_other: 'Come back, at a different time', redo: 'Record the conversation again from scratch', none: 'Nothing for now'};
function fill(table, rows){
  table.innerHTML = '';
  rows.forEach(function(r){
    const tr = document.createElement('tr');
    const k = document.createElement('td'); k.textContent = r[0];
    k.style.cssText = 'padding:.25rem .8rem .25rem 0;vertical-align:top;color:#4a5568;white-space:nowrap';
    const v = document.createElement('td'); v.textContent = r[1]; v.style.cssText = 'padding:.25rem 0;white-space:pre-wrap';
    tr.appendChild(k); tr.appendChild(v); table.appendChild(tr);
  });
}
function problem(msg){ document.getElementById('problem').textContent = msg || ''; }
function reviewChoice(){
  const d = picked(); const lines = markedWindows();
  if (!d) { problem('Please pick one of the three choices above.'); return; }
  if (lines.length && d !== 'changes') { problem('You have ' + lines.length + ' line(s) marked for cutting. Choose "Ask for changes", or click the marked lines again to unmark them.'); return; }
  if (d === 'correction' && !val('correction')) { problem('Please say what should be corrected.'); return; }
  if (d === 'changes' && !lines.length && !val('redactions')) { problem('Please mark the lines to cut, or describe the change.'); return; }
  problem('');
  const fu = document.querySelector('input[name=followup]:checked');
  const rows = [['Your choice', LABELS[d]]];
  if (d === 'correction') rows.push(['Your correction', val('correction')]);
  if (d === 'changes' && val('redactions')) rows.push(['What you are asking for', val('redactions')]);
  if (d === 'changes' && lines.length) rows.push(['Lines marked for cutting (' + lines.length + ')', lines.map(function(l){ return l.line; }).join('\\n')]);
  rows.push(["Your answer to Mira's question", val('experience') ? 'Included' : 'None']);
  rows.push(["For your episode's post", val('materials') ? 'Included' : 'Nothing']);
  rows.push(['Coming back', FOLLOW[fu ? fu.value : 'none']]);
  fill(document.getElementById('confirmRows'), rows);
  document.getElementById('confirm').style.display = 'block';
  document.getElementById('reviewBtnRow').style.display = 'none';
  document.getElementById('confirm').scrollIntoView({block: 'center', behavior: 'smooth'});
}
function changeChoice(){
  document.getElementById('confirm').style.display = 'none';
  document.getElementById('reviewBtnRow').style.display = 'block';
}
async function sendChoice(){
  const d = picked(); const fu = document.querySelector('input[name=followup]:checked');
  const sendBtn = document.getElementById('sendBtn'); const backBtn = document.getElementById('backBtn');
  sendBtn.disabled = backBtn.disabled = true; sendBtn.textContent = 'Sending\\u2026';
  let data = null;
  try {
    const resp = await fetch(location.pathname, {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({decision: d, approve: d !== 'changes', correction: val('correction'),
        redactions: val('redactions'), windows: markedWindows(), followup: fu ? fu.value : 'none',
        followup_note: val('followupNote'), experience: val('experience'), materials: val('materials')})});
    data = await resp.json().catch(function(){ return null; });
  } catch (e) { data = null; }
  if (data && data.already) {
    document.getElementById('confirm').style.display = 'none';
    document.getElementById('choices').style.display = 'none';
    document.getElementById('decide').textContent = 'Your choice was already recorded';
    document.getElementById('receiptHead').textContent = (data.state && data.state.headline) || 'Already recorded.';
    document.getElementById('receiptDetail').textContent = ((data.state && data.state.detail) || '') + ' Nothing new was sent.';
    document.getElementById('receipt').style.display = 'block';
    return;
  }
  if (!data || !data.ok) {
    sendBtn.disabled = backBtn.disabled = false; sendBtn.textContent = 'Send my choice';
    problem(((data && data.error) ? data.error + ' ' : '') + 'Nothing was recorded. Please try again, or reply to any of Mira\\'s emails.');
    return;
  }
  document.getElementById('confirm').style.display = 'none';
  document.getElementById('choices').style.display = 'none';
  document.getElementById('decide').textContent = 'Your choice is recorded';
  document.getElementById('receiptHead').textContent = (data.state && data.state.headline) || 'Recorded.';
  document.getElementById('receiptDetail').textContent = (data.state && data.state.detail) || '';
  fill(document.getElementById('receiptRows'), data.recorded || []);
  document.getElementById('receiptMail').textContent = data.emailed
    ? 'A copy of this is on its way to ' + data.emailed + '.' : '';
  // Nothing below can be sent any more; say so by disabling it.
  Array.from(document.querySelectorAll('textarea, input')).forEach(function(el){ el.disabled = true; });
  const st = document.getElementById('state');
  if (st && data.state) { st.firstChild.textContent = data.state.headline; if (st.children[1]) st.children[1].textContent = data.state.detail; }
  const r = document.getElementById('receipt'); r.style.display = 'block';
  r.scrollIntoView({block: 'center', behavior: 'smooth'});
}
</script>`);
}

/** The transcript as clickable lines: each timed line becomes a span that
 *  carries its window; untimed lines render as text. */
export function reviewTranscriptHtml(text: string): string {
  const timed = transcriptLines(text);
  let i = 0;
  const out: string[] = [];
  for (const raw of String(text ?? "").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) { out.push(""); continue; }
    if (i < timed.length && timed[i].line === line) {
      const w = timed[i++];
      out.push(`<span class="ln" data-start="${w.start}" data-end="${w.end}">${esc(line)}</span>`);
    } else {
      out.push(esc(line));
    }
  }
  return out.join("\n");
}

async function handleGuestReviewSubmit(req: Request, env: Env, token: string): Promise<Response> {
  const pkg = await pkgByToken(env, token);
  if (!pkg) return json({ error: "not found" }, 404);
  if (pkg.status === "archived") return json({ error: "this recording has been retired and will not be published" }, 409);
  const body = await req.json<any>().catch(() => ({}));
  const now = new Date().toISOString();
  // Oct 24 2026: a choice already made is shown back, not made twice, and a
  // choice that cannot be acted on is refused before anything is written.
  const already = guestReviewState(pkg);
  if (["approved", "published", "killed", "correction_pending", "changes_pending"].includes(already.code)) {
    return json({ ok: false, already: true, state: already, error: "Your choice was already recorded." }, 409);
  }
  {
    const w = redactionWindows(body?.windows);
    const d = guestDecision(body, w.length);
    if (d === "correction" && !String(body?.correction ?? "").trim()) {
      return json({ ok: false, error: "Please say what should be corrected." }, 400);
    }
    if (d === "changes" && !String(body?.redactions ?? "").trim() && !w.length) {
      return json({ ok: false, error: "Please mark the lines to cut, or describe the change." }, 400);
    }
  }
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

  const experience = String(body?.experience ?? "").slice(0, 3000).trim();
  if (experience) {
    await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`,
      { guest_experience: experience, guest_experience_at: now });
    try {
      await email(env, operatorEmail(env),
        `${show.shortLabel}: ${app?.name ?? "a guest"} on being interviewed by Mira`,
        `<p>${esc(app?.name ?? "A guest")} answered Mira's question on the review page:</p>
         <blockquote style="border-left:3px solid #ccc;margin:0;padding-left:1em">${esc(experience)}</blockquote>
         <p>It goes into Mira's next grading pass on every show.</p>`);
    } catch (err: any) { console.error("experience email failed:", err?.message ?? err); }
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

  // Oct 21 2026: a cut the guest marks on a transcript line carries its
  // time window, so the edit can apply it in code (guest_redaction_windows);
  // the free-text box stays for anything a line cannot say.
  const windows = redactionWindows(body?.windows);
  if (windows.length) {
    const existing = Array.isArray(pkg.guest_redaction_windows) ? pkg.guest_redaction_windows : [];
    await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`,
      { guest_redaction_windows: mergeWindows(existing, windows) });
  }

  // Oct 24 2026: three explicit choices (approve, approve with one
  // correction, ask for changes); what was recorded is read back and shown
  // on the page, emailed to the guest, and emailed to Patrick.
  const decision = guestDecision(body, windows.length);
  const correction = String(body?.correction ?? "").slice(0, 2000).trim();
  const requests = String(body.redactions ?? "").trim();
  const history = (Array.isArray(pkg.guest_redactions) ? pkg.guest_redactions : []).filter((r: any) => r?.resolved);
  let dispatched: boolean | undefined;
  if (decision === "approve") {
    // The guest's "yes" is recorded first, so a thrown dispatch can never
    // lose it; production is marked approved only once GitHub has the event.
    await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`, { guest_reviewed_at: now });
    try {
      await approveAndDispatch(env, { ...pkg, guest_reviewed_at: now }, pkg.interview_id, now);
      dispatched = true;
      await slack(env, `${show.shortLabel}: guest APPROVED package ${pkg.id} — production dispatched`);
    } catch (err: any) {
      console.error(`guest approval dispatch failed for ${pkg.id}: ${err?.message ?? err}`);
      dispatched = false;
      await slack(env, `:warning: ${show.shortLabel}: guest APPROVED package ${pkg.id} but the production dispatch failed (${String(err?.message ?? err).slice(0, 120)}); gate-2 housekeeping retries daily.`);
    }
  } else if (decision === "correction") {
    await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`, {
      guest_reviewed_at: now,
      guest_redactions: [...history, { kind: "correction", note: correction, approves: true, resolved: false, at: now }],
      status: "in_review",
    });
    await slack(env, `${show.shortLabel}: guest approved package ${pkg.id} with one correction — needs Patrick:\n${correction.slice(0, 500)}`);
  } else {
    const noted = windows.length
      ? `${requests}${requests ? "\n" : ""}${windows.length} marked line(s) carry time windows (guest_redaction_windows).`
      : requests;
    await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`, {
      guest_reviewed_at: now,
      guest_redactions: [...history, { kind: "removal", note: noted, lines: windows.length, resolved: false, at: now }],
      status: "in_review",
    });
    await slack(env, `${show.shortLabel}: guest requested removals on package ${pkg.id} — needs Patrick:\n${noted.slice(0, 500)}`);
  }

  // Read back what the database now holds; that, not what the browser sent,
  // is what the guest is shown and sent.
  const after = (await pkgByToken(env, token)) ?? pkg;
  const state = guestReviewState(decision === "approve" ? { ...after, status: "approved_by_guest", guest_reviewed_at: after.guest_reviewed_at ?? now } : after);
  const recorded = guestReceipt(after, decision);
  const link = `https://api.nerranetwork.com/voices/review/${pkg.guest_review_token}`;
  let emailed = "";
  if (app?.email) {
    try {
      await email(env, app.email, `Got it: your choice on your ${show.shortLabel} episode`,
        `<p>Hi ${esc(firstName(app.name))},</p>
         <p>This is a copy of what you chose on your review page, so you have it in writing.</p>
         ${receiptHtml(recorded)}
         <p><b>${esc(state.headline)}</b> ${esc(state.detail)}</p>
         <p>Your <a href="${esc(link)}">review page</a> always shows where things stand.</p>
         ${miraSignature(show)}`, true, publicistCc(app));
      emailed = app.email;
    } catch (err: any) { console.error("guest receipt email failed:", err?.message ?? err); }
  }
  try {
    const verb = decision === "approve" ? "approved the episode"
      : decision === "correction" ? "approved, with one correction" : "asked for changes";
    const op = operatorReviewState(after, String(app?.name ?? ""), String(app?.email ?? ""));
    const gate1 = `https://api.nerranetwork.com/voices/admin/review/${pkg.id}/${await packageReviewToken(env, pkg.id)}`;
    await email(env, operatorEmail(env), `${show.shortLabel}: ${app?.name ?? "the guest"} ${verb}`,
      `<p>${esc(app?.name ?? "The guest")} ${esc(verb)} on the review page.</p>
       ${receiptHtml(recorded)}
       ${decision === "approve"
         ? `<p>${dispatched ? "Production is dispatched." : "The production dispatch failed; gate-2 housekeeping retries it daily."}
            Publishing is yours: <code>gh workflow run nerra_voices_publish.yml -f interview_id=${esc(String(pkg.interview_id))}</code></p>`
         : `<p><b>${esc(op.headline)}</b> ${esc(op.detail)}</p>`}
       <p><a href="${esc(gate1)}">Open the episode's review page</a></p>`);
  } catch (err: any) { console.error("operator decision email failed:", err?.message ?? err); }
  return json({ ok: true, decision, ...(dispatched === undefined ? {} : { dispatched }), state, recorded, emailed });
}

/** One transcript line as the review page renders it: the [mm:ss] or
 *  [h:mm:ss] prefix is its start; the end is the next line's start, or
 *  start + 15 s on the last line. */
export const TRANSCRIPT_LINE_RE = /^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*(.*)$/;
export const REDACTION_LINE_DEFAULT_SEC = 15;

export function transcriptLines(text: string): Array<{ start: number; end: number; line: string }> {
  const rows: Array<{ start: number; line: string }> = [];
  for (const raw of String(text ?? "").split(/\r?\n/)) {
    const m = raw.match(TRANSCRIPT_LINE_RE);
    if (!m) continue;
    const start = m[3] !== undefined
      ? Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3])
      : Number(m[1]) * 60 + Number(m[2]);
    rows.push({ start, line: raw.trim() });
  }
  return rows.map((r, i) => ({
    start: r.start,
    end: i + 1 < rows.length ? Math.max(r.start + 1, rows[i + 1].start) : r.start + REDACTION_LINE_DEFAULT_SEC,
    line: r.line,
  }));
}

/** The windows a review submit carries, cleaned: numbers only, end after
 *  start, the line text capped, at most 200 of them. */
export function redactionWindows(raw: unknown): Array<{ start_sec: number; end_sec: number; line: string }> {
  if (!Array.isArray(raw)) return [];
  const out: Array<{ start_sec: number; end_sec: number; line: string }> = [];
  for (const w of raw.slice(0, 200)) {
    const start = Number(w?.start_sec ?? w?.start);
    const end = Number(w?.end_sec ?? w?.end);
    if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start) continue;
    out.push({ start_sec: Math.round(start * 100) / 100, end_sec: Math.round(end * 100) / 100,
               line: String(w?.line ?? "").slice(0, 400) });
  }
  return out;
}

export function mergeWindows(existing: any[], added: any[]): any[] {
  const seen = new Set(existing.map((w) => `${w?.start_sec}-${w?.end_sec}`));
  const out = [...existing];
  for (const w of added) {
    const key = `${w.start_sec}-${w.end_sec}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(w);
  }
  return out.sort((a, b) => Number(a.start_sec) - Number(b.start_sec));
}

// -- Guest survey (Oct 21 2026) -----------------------------------------------
// Three questions, emailed by Mira a day after the room (the pipeline mints
// editorial_packages.survey_token and sends the link), asked whether or not
// the guest ever opens the review page. The first number is this show's
// headline figure, the way audience_headline is the network's.

export const SURVEY_RECOMMEND = new Set(["yes", "no", "maybe"]);

async function pkgBySurveyToken(env: Env, token: string): Promise<any | null> {
  const rows = await sb(env, "GET",
    `editorial_packages?survey_token=eq.${encodeURIComponent(token)}&limit=1`);
  return rows?.[0] ?? null;
}

/** The answers a survey submit carries, cleaned; null when nothing usable. */
export function surveyAnswers(body: any): { survey_rating: number | null; survey_change: string | null;
                                             survey_recommend: string | null } | null {
  const rating = Math.round(Number(body?.rating));
  const okRating = Number.isFinite(rating) && rating >= 1 && rating <= 5;
  const change = String(body?.change ?? "").trim().slice(0, 2000);
  const recommend = oneOf(body?.recommend, [...SURVEY_RECOMMEND]);
  if (!okRating && !change && !recommend) return null;
  return {
    survey_rating: okRating ? rating : null,
    survey_change: change || null,
    survey_recommend: recommend,
  };
}

async function handleSurveyPage(env: Env, token: string): Promise<Response> {
  const pkg = await pkgBySurveyToken(env, token);
  if (!pkg) return html(page("Link not found",
    "<p>This link has expired or was mistyped. Reply to any of Mira's emails instead.</p>"), 404);
  const { app, show } = await interviewWithApp(env, pkg.interview_id);
  const answered = !!pkg.survey_answered_at;
  const chosen = (v: string) => String(pkg.survey_recommend ?? "") === v ? " checked" : "";
  const stars = [1, 2, 3, 4, 5].map((n) =>
    `<label style="margin-right:1rem"><input type="radio" name="rating" value="${n}"` +
    `${Number(pkg.survey_rating) === n ? " checked" : ""}> ${n}</label>`).join("");
  return html(page(`How was the hour, ${esc(firstName(app?.name))}?`, `
    <p>Three questions, from Mira. They take a minute, and every answer changes
    how I interview the next guest on ${esc(show.name)}.</p>
    ${answered ? "<p><em>You have answered already; you can change your answers below.</em></p>" : ""}
    <h3>1. On a scale of one to five, how did the hour compare with a human host?</h3>
    <p style="color:#4a5568;font-size:.95rem">1 = much worse · 3 = about the same · 5 = much better</p>
    <p>${stars}</p>
    <h3>2. One thing you would change</h3>
    <textarea id="change" style="width:100%;min-height:90px"
      placeholder="Pace, a question, something I should have asked, something I should not have said.">${esc(String(pkg.survey_change ?? ""))}</textarea>
    <h3>3. Would you recommend it to a peer?</h3>
    <p>
    <label><input type="radio" name="recommend" value="yes"${chosen("yes")}> Yes</label><br>
    <label><input type="radio" name="recommend" value="maybe"${chosen("maybe")}> Maybe</label><br>
    <label><input type="radio" name="recommend" value="no"${chosen("no")}> No</label>
    </p>
    <p><button id="send" onclick="sendSurvey()">Send to Mira</button>
    <span id="done" style="display:none;font-weight:600;color:#166534"></span></p>
    <script>
    async function sendSurvey(){
      const btn = document.getElementById('send');
      btn.disabled = true; btn.textContent = 'Sending\u2026';
      const r = document.querySelector('input[name=rating]:checked');
      const rec = document.querySelector('input[name=recommend]:checked');
      let ok = false;
      try {
        const resp = await fetch(location.pathname, {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({rating: r ? Number(r.value) : null,
            change: document.getElementById('change').value,
            recommend: rec ? rec.value : null})});
        ok = resp.ok;
      } catch (e) { ok = false; }
      const done = document.getElementById('done');
      done.textContent = ok ? 'Thank you. I read every answer.' : 'Something went wrong \u2014 reply to my email instead.';
      done.style.color = ok ? '#166534' : '#991B1B';
      done.style.display = 'inline';
      if (ok) btn.style.display = 'none';
      else { btn.disabled = false; btn.textContent = 'Send to Mira'; }
    }
    </script>`, show.brandColor));
}

async function handleSurveySubmit(req: Request, env: Env, token: string): Promise<Response> {
  const pkg = await pkgBySurveyToken(env, token);
  if (!pkg) return json({ error: "not found" }, 404);
  const body = await req.json<any>().catch(() => ({}));
  const answers = surveyAnswers(body);
  if (!answers) return json({ error: "nothing answered" }, 400);
  const now = new Date().toISOString();
  // A second submit updates the answers; the first time is the one that counts.
  await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`,
    { ...answers, survey_answered_at: pkg.survey_answered_at ?? now });
  const { app, show } = await interviewWithApp(env, pkg.interview_id);
  const who = app?.name ?? "a guest";
  await slack(env, `${show.shortLabel}: ${who} answered Mira's survey — ` +
    `${answers.survey_rating ?? "?"}/5, recommend: ${answers.survey_recommend ?? "?"}` +
    (answers.survey_change ? ` — "${answers.survey_change.slice(0, 200)}"` : ""));
  try {
    await email(env, operatorEmail(env),
      `${show.shortLabel}: ${who} rated the hour ${answers.survey_rating ?? "?"}/5`,
      `<p>${esc(String(who))} answered Mira's three questions:</p>
       <p><b>Compared with a human host:</b> ${esc(String(answers.survey_rating ?? "not answered"))} / 5<br>
       <b>One thing to change:</b> ${esc(answers.survey_change ?? "not answered")}<br>
       <b>Recommend to a peer:</b> ${esc(answers.survey_recommend ?? "not answered")}</p>
       <p>Stored on package ${esc(String(pkg.id))}; the weekly lesson pass reads it.</p>`);
  } catch (err: any) { console.error("survey email failed:", err?.message ?? err); }
  return json({ ok: true, updated: !!pkg.survey_answered_at });
}

// -- Admin UIs (lean, token-gated) ------------------------------------------

async function handleAdminTriage(req: Request, env: Env): Promise<Response> {
  const denied = await requireTriageAccess(req, env);
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
      <br>${esc(a.bio ?? "").slice(0, 500)}${profilesHtml(a)}${screenHtml(a)}
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
const token = new URL(location).searchParams.get('token')
  // Sept 27 2026: the emailed link is /voices/admin/review/<id>/<token>, and the
  // browser keeps that path, so the token has to be read from it too, or every
  // Approve from an email fails with "check the token" (Roddy de la Garza).
  || ((p) => p.length === 40 ? p : '')(location.pathname.split('/').filter(Boolean).pop() || '');
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

// ---------------------------------------------------------------------------
// The archive (Sept 30 2026)
// ---------------------------------------------------------------------------
// Meridan Zerner and Chad Law are both recording again, and the rehearsals
// Patrick ran on Sept 9-10 were never meant for anyone. None of them should
// be published and none of them should be deleted. "archived" is a status
// nothing downstream acts on: the auto-approval looks only at
// approved_by_patrick, the publish step requires approved_by_guest, and the
// guest review page and its submit refuse an archived package. The archive
// page lists them, token-gated, with their audio and transcript.

async function adminSig(env: Env, message: string): Promise<string> {
  const token = (env.ADMIN_TOKEN || "").trim();
  if (!token) throw new Error("ADMIN_TOKEN required");
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(token), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(message));
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 40);
}

async function archiveToken(env: Env): Promise<string> {
  return adminSig(env, "nerra-archive");
}

/** Oct 16 2026: triage emails used to embed the raw ADMIN_TOKEN. Same
 *  HMAC pattern as archive / package-review tokens — opens triage only. */
async function triageToken(env: Env): Promise<string> {
  return adminSig(env, "nerra-triage");
}

/** Oct 27 2026: Patrick's one-click "send them the link for their phone",
 *  in the stuck-guest email. It replaces the "call their phone" link of Oct 1:
 *  phone interviews are gone. GET shows a confirm button (mail scanners
 *  prefetch links, and this one sends a text); POST checks the signature and
 *  sends the same text and email as the guest's own "Text me the link".
 *  pipelines/voices/fire_interviews.py text_guest_link builds the same link. */
async function textGuestSig(env: Env, interviewId: string): Promise<string> {
  return adminSig(env, `text-guest:${interviewId}`);
}

async function textGuestLink(env: Env, interviewId: string): Promise<string> {
  return `https://api.nerranetwork.com/voices/admin/text-guest?interview=${interviewId}&sig=${await textGuestSig(env, interviewId)}`;
}

// Oct 1 2026: the same audio paragraph and steps as pipelines/voices/common.py
// (GUEST_AUDIO_HTML, studio_steps_html); keep the two in step.
// Oct 19 2026 (Patrick, after a review of every interview): the guest is
// told, before the day and again by Mira at the open, that the hour is
// theirs to steer, and that anything can come out afterwards. The same
// words go in the brief (templates/email/voices_prep_brief.j2).
const GUEST_YOUR_HOUR_HTML =
  '<p style="background:#faf5ff;border-left:4px solid #7c3aed;padding:.7em 1em">' +
  "<strong>It's your hour.</strong> I'm there to ask about what you came to talk " +
  "about. If a question doesn't land, say so and I'll move on. If you'd rather go " +
  "somewhere else, say so and we'll go there. If you want to start an answer again, " +
  "just start again. If you want a moment to think, say so and I'll wait. And if " +
  "anything comes out that you'd rather not have in the episode, tell me in the " +
  "moment or mark it on the transcript afterwards, and it comes out of the audio " +
  "too, cleanly. None of that needs an explanation.</p>";

const GUEST_AUDIO_HTML =
  '<p style="background:#f0fdfa;border-left:4px solid #0f766e;padding:.7em 1em">' +
  "<strong>For the best sound:</strong> please join from a computer, wearing " +
  "headphones or earbuds, ideally with a good microphone. A computer with headphones " +
  "and a good microphone sounds clear and full, and listeners tell us those are the " +
  "interviews they enjoy most. AirPods or a headset connected to your computer work well, and a " +
  "USB microphone is even better. Headphones also stop your microphone picking up my " +
  "voice from your speakers; without them my questions end up in your recording as if " +
  "you had said them.</p>";

function studioStepsHtml(studio: string): string {
  return "<p><strong>On the day, three steps and we're on:</strong></p><ol>" +
    `<li>Open <a href="${esc(studio)}">your studio link</a> on your computer, up to ${STUDIO_OPENS_BEFORE_TEXT} before we start.</li>` +
    "<li>Press <strong>Check my microphone</strong> and read the sentence out loud until it says <strong>Sounds good</strong>.</li>" +
    "<li>Press <strong>Join your interview</strong>. You're in when you hear me say hello.</li></ol>" +
    "<p>If your computer gives you trouble, open the same link on your phone, earbuds in: it's " +
    "the same studio and sounds just as good. If neither works, the studio has a button to " +
    "pick another time, so nothing is lost. Interviews happen in the studio only, not by " +
    "phone call, because a phone line sounds too thin for the show.</p>";
}

async function setCalendarLocation(env: Env, show: Show, uid: string, studio: string, who: string) {
  if (!uid) return;
  if (!env.CAL_API_KEY) {
    await slack(env, `:warning: ${show.shortLabel}: ${who}'s calendar invite still points at Cal Video. Set the CAL_API_KEY Worker secret so bookings get the studio link.`);
    return;
  }
  try {
    const res = await fetch(`https://api.cal.com/v2/bookings/${encodeURIComponent(uid)}/location`, {
      method: "PATCH",
      headers: { "Authorization": `Bearer ${env.CAL_API_KEY}`, "cal-api-version": "2024-08-13",
        "Content-Type": "application/json" },
      body: JSON.stringify({ location: { type: "link", link: studio } }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
  } catch (err: any) {
    console.error("cal location update failed:", err?.message ?? err);
    await slack(env, `:warning: ${show.shortLabel}: couldn't put the studio link in ${who}'s calendar invite (${err?.message ?? err}). Their invite shows the default location.`);
  }
}

function minutesToStart(iv: any): number {
  return (Date.parse(iv?.scheduled_at) - Date.now()) / 60000;
}

/** GET/POST /voices/join — the location on the Cal.com event types. A guest
 *  who opens the meeting from a calendar lands here, types the address they
 *  booked with, and goes straight to their studio when the interview is
 *  close; otherwise Mira emails them their personal link. */
async function handleJoin(req: Request, env: Env): Promise<Response> {
  const url = new URL(req.url);
  const page = (title: string, body: string) => new Response(
    `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
     <title>${esc(title)} · Nerra Network</title>
     <body style="font:17px/1.55 system-ui,sans-serif;max-width:520px;margin:3rem auto;padding:0 1rem;color:#1a202c">
     <h1 style="font-size:1.35rem">${esc(title)}</h1>${body}
     <p style="color:#4a5568;font-size:.9rem;margin-top:2rem">Trouble? Email <a href="mailto:mira@nerranetwork.com">mira@nerranetwork.com</a>.</p></body>`,
    { headers: { "content-type": "text/html; charset=utf-8" } });
  // Oct 21 2026: the interview id alone used to open anyone's studio, and a
  // typed email address did the same inside the half hour before the start.
  // The studio now opens from this page only for the guest's own manage
  // token (every reminder carries it); an address gets the link by email.
  const iid = url.searchParams.get("interview") ?? "";
  const token = String(url.searchParams.get("t") ?? url.searchParams.get("token") ?? "").trim();
  if (UUID_RE.test(iid) && token.length >= 16) {
    const { iv, show } = await interviewGuest(env, iid);
    const own = iv ? await manageInterview(env, token) : null;
    if (iv && own && String(own.id) === String(iv.id)) {
      return Response.redirect(studioUrl(show, iid, "guest"), 302);
    }
  }
  const form = (note = "") => page("Join your interview with Mira",
    `${note}<p>Enter the email address you booked with and I'll take you to your studio.</p>
     <form method="post"><input type="email" name="email" required autocomplete="email"
       style="font:inherit;padding:.6rem;border:1px solid #cbd5e0;border-radius:8px;width:100%;box-sizing:border-box">
     <button style="font:inherit;margin-top:.7rem;padding:.6rem 1.2rem;border-radius:8px;border:0;background:#0F766E;color:#fff">
     Go to my studio</button></form>
     <p style="color:#4a5568;font-size:.95rem">For the best sound, use a computer with headphones.</p>`);
  if (req.method !== "POST") return form();
  const fd = await req.formData().catch(() => null);
  const addr = String(fd?.get("email") ?? "").trim().toLowerCase();
  if (!addr.includes("@")) return form("<p style='color:#b45309'>That doesn't look like an email address.</p>");
  const enc = encodeURIComponent(addr);
  const apps: any[] = (await sb(env, "GET",
    `guest_applications?or=(email.ilike.${enc},publicist_email.ilike.${enc})&select=id,name,email,show`)) ?? [];
  const since = new Date(Date.now() - 2 * 3600 * 1000).toISOString();
  let iv: any = null, app: any = null;
  for (const a of apps) {
    const rows = await sb(env, "GET",
      `interviews?application_id=eq.${a.id}&status=in.(scheduled,briefed,in_progress)` +
      `&scheduled_at=gte.${since}&order=scheduled_at.asc&limit=1&select=id,scheduled_at,show`);
    if (rows?.[0] && (!iv || rows[0].scheduled_at < iv.scheduled_at)) { iv = rows[0]; app = a; }
  }
  if (!iv) {
    return form(`<p style='color:#b45309'>I couldn't find an upcoming interview for ${esc(addr)}. ` +
      `Try the address the calendar invite was sent to, or reply to any of my emails.</p>`);
  }
  const show = showFor(app, { show: iv.show });
  const studio = studioUrl(show, iv.id, "guest");
  // The link goes to the guest's own inbox rather than to whoever typed
  // their address, however close to the start it is.
  try {
    await email(env, String(app.email), `Your ${show.name} studio link`,
      `<p>Hi ${esc(firstName(app.name))},</p><p>Here's your personal studio link for our interview on
       <strong>${esc(pacificTime(iv.scheduled_at))}</strong>:
       <a href="${studio}">join your interview here</a>. It opens ${STUDIO_OPENS_BEFORE_TEXT} before we start.</p>
       ${GUEST_AUDIO_HTML}${studioStepsHtml(studio)}${miraSignature(show)}`, true);
  } catch (err: any) { console.error("join link email failed:", err?.message ?? err); }
  return page("Check your email",
    `<p>Your interview is on <strong>${esc(pacificTime(iv.scheduled_at))}</strong>. I've emailed your personal
     studio link to the address on your booking${minutesToStart(iv) <= 30 ? " — it should be there in a moment" : ""}.
     On the day, open it on your computer with headphones on.</p>`);
}

/** Oct 5 2026 (Jon Cheney). The two-hour reminder is sent by the GitHub fire
 *  job, and during the Actions outage that day nothing was sent at all. If
 *  an interview is inside the last hour and a half with no reminder on
 *  record, GitHub has missed it, and the Worker sends it instead: the email,
 *  and the text when Voximplant is configured here. Claimed with a
 *  conditional write, so the two can never both send. A booking made in the
 *  last three hours already has a fresh confirmation and is left alone. */
async function reminderFallback(env: Env): Promise<number> {
  const now = Date.now();
  const lo = new Date(now + 60 * 60000).toISOString();
  const hi = new Date(now + 100 * 60000).toISOString();
  const bookedBefore = new Date(now - 3 * 60 * 60000).toISOString();
  const due = await sb(env, "GET",
    `interviews?status=in.(briefed,scheduled)&reminder_sent_at=is.null` +
    `&scheduled_at=gte.${lo}&scheduled_at=lte.${hi}&created_at=lte.${bookedBefore}` +
    `&select=id,application_id,scheduled_at,show,guest_timezone,manage_token,call_mode,episode_thesis&limit=10`) ?? [];
  let sent = 0;
  for (const iv of due) {
    try {
      const claimed = await sb(env, "PATCH",
        `interviews?id=eq.${iv.id}&reminder_sent_at=is.null`,
        { reminder_sent_at: new Date().toISOString() }, "return=representation");
      if (!claimed?.length) continue;
      const app = (await sb(env, "GET",
        `guest_applications?id=eq.${iv.application_id}&select=name,email,phone,show,topics,pitch_summary,publicist_email`))?.[0];
      if (!app?.email) continue;
      const show = isShow(iv.show) ? showFor(iv) : showFor(app);
      const studio = studioUrl(show, iv.id);
      const when = pacificTime(iv.scheduled_at, iv.guest_timezone);
      const manage = iv.manage_token
        ? `https://api.nerranetwork.com/voices/manage/${encodeURIComponent(iv.manage_token)}` : "";
      await email(env, app.email, `Our interview on ${show.name} is coming up`,
        `<p>Hi ${esc(firstName(app.name))},</p>
         <p>We're on for <strong>${esc(when)}</strong>, a little over an hour from now.</p>
         ${subjectHtml(interviewSubject(iv, app, true))}
         ${GUEST_AUDIO_HTML + studioStepsHtml(studio)}
         ${manage ? `<p>If today doesn't work after all, <a href="${esc(manage)}">move or cancel it here</a>.</p>` : ""}
         ${miraSignature(show)}`, true, publicistCc(app));
      const phone = phoneE164(app.phone);
      if (phone) {
        await sendSms(env, phone,
          `Mira here, from ${show.name}. We're on in about an hour. From a computer with ` +
          `headphones: open ${studio}, press Check my microphone, then Join.` +
          (manage ? ` Can't make it? ${manage}` : "") + " — Mira").catch(() => false);
      }
      await email(env, operatorEmail(env),
        `${show.shortLabel}: the reminder for ${app.name ?? "a guest"} came from the Worker`,
        `<p>GitHub never sent the two-hour reminder for the interview at ${esc(when)}, so the
         Worker sent it (email${phone ? " and text" : ""}). If this keeps happening,
         GitHub Actions is having a bad day.</p>`);
      sent++;
    } catch (err: any) {
      console.error("reminder fallback failed for", iv.id, err?.message ?? err);
    }
  }
  return sent;
}

/** Oct 13 2026: the five-minute fire-tick dispatched a GitHub job 288
 *  times a day (GitHub's own five-minute cron delivered 4), ~75 s of runner each,
 *  and almost every one found nothing to do — fire_interviews.py acts only
 *  on interviews at status briefed/scheduled inside [T-30 min, T+135 min]
 *  (the T-2h reminder is its earliest action) plus the browser no-show
 *  sweep (two days back) and live runs. The Worker reads the same table,
 *  so it asks first. FAIL-OPEN: a Supabase error dispatches, and the
 *  :00/:30 ticks always dispatch, so a row this query cannot see waits at
 *  most thirty minutes — never a guest in a locked studio. */
const FIRE_TICK_LOOKAHEAD_MS = 140 * 60000;   // REMINDER_AHEAD upper bound + drift
// Oct 19 2026: an interview is the fire script's to act on only around its
// slot — the reminder ahead of it, the fire window, the live run (50-minute
// hard cap). The 48-hour lookback on INTERVIEWS held the gate open all day
// for two interviews whose runs had already fired ("already has an active
// run — skipping", 148 dispatches on Oct 19).
const FIRE_TICK_INTERVIEW_LOOKBACK_MS = 3 * 3600000;
// Oct 28 2026: the run-table clause read runs CREATED in the last two days,
// and every run is staged about a day before its slot, so each booking held
// the gate open for two whole days: run d0cdb835 (staged Oct 26 18:02 for
// Oct 27 18:00) and then run 35cdf6f4 (staged Oct 27 17:32 for Oct 28
// 17:30) kept it open all of Oct 27, 232 Worker dispatches that almost all
// logged "already has an active run — skipping". A run is read around its own
// slot (scheduled_for), the same window as the interview; the no-show sweep
// acts 40 minutes after the start, inside it, and a staged prompt is
// refreshed on the half-hour ticks, which always dispatch.

export async function fireTickDue(env: Env): Promise<boolean> {
  try {
    const ilo = new Date(Date.now() - FIRE_TICK_INTERVIEW_LOOKBACK_MS).toISOString();
    const hi = new Date(Date.now() + FIRE_TICK_LOOKAHEAD_MS).toISOString();
    const due = await sb(env, "GET",
      `interviews?status=in.(scheduled,briefed,in_progress)&scheduled_at=gte.${ilo}&scheduled_at=lte.${hi}&select=id&limit=1`);
    if (due?.length) return true;
    // Bounded to the run's own slot: on Oct 13 2026 the table held two
    // awaiting_guest rows from September and a staged row from the day
    // before, none of which the fire script acts on, and an unbounded read
    // would have held the gate open forever.
    const runs = await sb(env, "GET",
      `interview_runs?status=in.(staged,awaiting_guest,fired)&scheduled_for=gte.${ilo}&scheduled_for=lte.${hi}&select=id&limit=1`);
    return !!runs?.length;
  } catch (err: any) {
    console.error("fire-tick gate failed (dispatching anyway):", err?.message ?? err);
    return true;
  }
}

/** Oct 19 2026: the :00/:30 producer tick dispatched nerra_producer_inbox.yml
 *  48 times a day (~70 s of runner each) and the job's first act is one Gmail
 *  query — threads without the Producer/Processed label, newer than 30 days,
 *  in the inbox — which on most ticks returns nothing. The Worker runs that
 *  same query first (gmail_client.list_unprocessed_threads's `q`, the same
 *  service account and delegated user) on both mailboxes and dispatches
 *  only when a thread is waiting. FAIL-OPEN: no credentials configured, a
 *  token error, a Gmail error — all dispatch, as before. The live-interview
 *  five-minute tick is not gated (a guest in the studio is never made to
 *  wait on a query). GitHub's own every-30-minutes cron on the workflow is the catch-all
 *  behind a wrong "nothing waiting". */
const PRODUCER_INBOX_QUERY = "-label:Producer/Processed newer_than:30d in:inbox";
const GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"; // the scope the delegation grants

function b64url(bytes: Uint8Array): string {
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function pemToDer(pem: string): ArrayBuffer {
  const body = pem.replace(/-----[A-Z ]+-----/g, "").replace(/\s+/g, "");
  const bin = atob(body);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out.buffer;
}

async function gmailAccessToken(env: Env, user: string): Promise<string> {
  const sa = JSON.parse(env.GMAIL_SERVICE_ACCOUNT_JSON || "{}");
  if (!sa.client_email || !sa.private_key) throw new Error("service account JSON lacks client_email/private_key");
  const key = await crypto.subtle.importKey(
    "pkcs8", pemToDer(sa.private_key), { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
  const now = Math.floor(Date.now() / 1000);
  const enc = new TextEncoder();
  const header = b64url(enc.encode(JSON.stringify({ alg: "RS256", typ: "JWT" })));
  const claims = b64url(enc.encode(JSON.stringify({
    iss: sa.client_email, sub: user, scope: GMAIL_SCOPE,
    aud: "https://oauth2.googleapis.com/token", iat: now, exp: now + 600,
  })));
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, enc.encode(`${header}.${claims}`));
  const assertion = `${header}.${claims}.${b64url(new Uint8Array(sig))}`;
  const resp = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion }),
  });
  if (!resp.ok) throw new Error(`google token for ${user}: ${resp.status}`);
  const data = await resp.json() as { access_token?: string };
  if (!data.access_token) throw new Error(`google token for ${user}: no access_token`);
  return data.access_token;
}

async function mailboxHasUnprocessed(env: Env, user: string): Promise<boolean> {
  const token = await gmailAccessToken(env, user);
  const url = "https://gmail.googleapis.com/gmail/v1/users/me/threads?maxResults=1&q="
    + encodeURIComponent(PRODUCER_INBOX_QUERY);
  const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!resp.ok) throw new Error(`gmail threads for ${user}: ${resp.status}`);
  const data = await resp.json() as { threads?: unknown[] };
  return Array.isArray(data.threads) && data.threads.length > 0;
}

function miraMailbox(env: Env): string {
  const configured = (env.GMAIL_MIRA_USER || "").trim().toLowerCase();
  if (configured) return configured;
  const m = /<([^>]+)>/.exec(env.VOICES_FROM_EMAIL || "");
  return (m ? m[1] : env.VOICES_FROM_EMAIL || "").trim().toLowerCase();
}

async function producerTickDue(env: Env): Promise<boolean> {
  const user = (env.GMAIL_DELEGATED_USER || "").trim().toLowerCase();
  if (!env.GMAIL_SERVICE_ACCOUNT_JSON || !user) return true;  // not configured: as before
  try {
    const boxes = [user];
    const mira = miraMailbox(env);
    if (mira && mira !== user) boxes.push(mira);
    for (const box of boxes) {
      if (await mailboxHasUnprocessed(env, box)) return true;
    }
    return false;
  } catch (err: any) {
    console.error("producer-tick gate failed (dispatching anyway):", err?.message ?? err);
    return true;
  }
}

async function interviewIsLive(env: Env): Promise<boolean> {
  const lo = new Date(Date.now() - 60 * 60000).toISOString();
  const hi = new Date(Date.now() + 15 * 60000).toISOString();
  const rows = await sb(env, "GET",
    `interviews?status=in.(scheduled,briefed,in_progress)&scheduled_at=gte.${lo}&scheduled_at=lte.${hi}&select=id&limit=1`);
  return !!rows?.length;
}

async function sendSms(env: Env, to: string, text: string): Promise<boolean> {
  if (!env.VOXIMPLANT_ACCOUNT_ID || !env.VOXIMPLANT_API_KEY || !env.VOXIMPLANT_CALLER_ID) return false;
  const form = new URLSearchParams({
    account_id: env.VOXIMPLANT_ACCOUNT_ID, api_key: env.VOXIMPLANT_API_KEY,
    source: env.VOXIMPLANT_CALLER_ID.replace(/^\+/, ""), destination: to.replace(/^\+/, ""),
    sms_body: text.slice(0, 640),
  });
  const res = await fetch("https://api.voximplant.com/platform_api/SendSmsMessage", { method: "POST", body: form });
  const out = await res.json<any>().catch(() => ({}));
  if (!res.ok || out?.error) {
    console.error("SMS failed:", res.status, JSON.stringify(out?.error ?? out).slice(0, 200));
    return false;
  }
  return true;
}

/** POST /voices/studio-text {interview, phone?} — Oct 2 2026. The better
 *  fallback than a phone call: the guest's studio link by text (and email),
 *  to open in their phone's browser. Browser audio is wideband; a phone line
 *  stops at 3.4 kHz, which is why Jason Fishman's episode sounds thin. */
async function handleStudioText(req: Request, env: Env): Promise<Response> {
  const body = await req.json<any>().catch(() => null);
  const interviewId = String(body?.interview ?? "").trim();
  if (!UUID_RE.test(interviewId)) return json({ error: "interview required" }, 400);
  const { iv, app, show } = await interviewGuest(env, interviewId);
  if (!iv || !app) return json({ error: "not found" }, 404);
  const given = phoneE164(body?.phone);
  if (body?.phone && !given) return json({ error: "That number doesn't look right. Include the country code, e.g. +1 604 555 0123.", need_phone: true }, 400);
  const phone = given ?? phoneE164(app.phone);
  if (given && given !== phoneE164(app.phone)) {
    await sb(env, "PATCH", `guest_applications?id=eq.${app.id}`, { phone: given });
  }
  const studio = studioUrl(show, interviewId, "guest");
  let texted = false;
  if (phone) {
    try {
      texted = await sendSms(env, phone,
        `Mira here (${show.name}). Open this on your phone to join our interview, earbuds in if you have them: ${studio}`);
    } catch (err: any) { console.error("studio-text SMS failed:", err?.message ?? err); }
  }
  try {
    await email(env, app.email, `Your ${show.name} studio link, for your phone`,
      `<p>Hi ${esc(firstName(app.name))},</p><p>Open this link on your phone and you'll be in the same
       studio: <a href="${studio}"><strong>join your interview here</strong></a>. Earbuds or headphones
       make it sound best. Then press <strong>Check my microphone</strong>, read the sentence until it says
       <strong>Sounds good</strong>, and press <strong>Join your interview</strong>.</p>${miraSignature(show)}`, true);
  } catch (err: any) { console.error("studio-text email failed:", err?.message ?? err); }
  if (!texted && !phone) return json({ ok: true, texted: false, emailed: true, need_phone: !body?.phone });
  await slack(env, `:iphone: ${show.shortLabel}: ${app.name ?? "guest"} asked for the studio link on their phone (${texted ? "texted" : "emailed; SMS unavailable"}).`);
  return json({ ok: true, texted, emailed: true, phone_last4: phone ? phone.slice(-4) : null });
}

function adminPage(title: string, body: string, status = 200): Response {
  return new Response(
    `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
     <title>${esc(title)}</title><body style="font:16px/1.5 system-ui,sans-serif;max-width:520px;margin:3rem auto;padding:0 1rem">
     <h1 style="font-size:1.3rem">${esc(title)}</h1>${body}</body>`,
    { status, headers: { "content-type": "text/html; charset=utf-8" } });
}

/** The old "call their phone" links in emails sent before Oct 27 2026. */
function handleCallGuestRetired(): Response {
  return adminPage("Phone interviews are no longer offered",
    "<p>This link used to switch a guest to a phone call. Phone interviews are no longer offered: " +
    "the sound is too poor for the show. The guest's studio page offers to carry on from their " +
    "phone's browser, or to pick another time.</p>", 410);
}

async function handleTextGuest(req: Request, env: Env): Promise<Response> {
  const url = new URL(req.url);
  const interviewId = url.searchParams.get("interview") ?? "";
  const sig = url.searchParams.get("sig") ?? "";
  if (!UUID_RE.test(interviewId) || sig !== await textGuestSig(env, interviewId)) {
    return adminPage("Link not valid", "<p>This link is incomplete or has been changed.</p>");
  }
  const { iv, app } = await interviewGuest(env, interviewId);
  if (!iv || !app) return adminPage("Interview not found", "<p>No interview matches this link.</p>");
  const who = esc(String(app.name ?? "the guest"));
  if (req.method !== "POST") {
    return adminPage(`Send ${who} their link for their phone?`,
      `<p>Mira will text ${who} their studio link${app.phone ? ` on ${esc(String(app.phone))}` : ""} and
       email it to ${esc(String(app.email ?? "them"))}, to open in their phone's browser with earbuds in.
       It's the same studio.</p>
       <form method="post"><button style="font:inherit;padding:.6rem 1.2rem;border-radius:8px;border:0;background:#0F766E;color:#fff">
       Send it</button></form>`);
  }
  const res = await handleStudioText(new Request(req.url, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ interview: interviewId }),
  }), env);
  const out = await res.json<any>().catch(() => ({}));
  if (out.ok) {
    return adminPage("Sent", `<p>${out.texted ? `Texted to the number ending in ${esc(String(out.phone_last4))} and emailed.`
      : "Emailed (no usable phone number for a text)."} ${who} can open it on their phone.</p>`);
  }
  return adminPage("Couldn't send it", `<p>${esc(String(out.error ?? "Unknown error"))}</p>`);
}

async function archivePackage(env: Env, packageId: string, reason: string): Promise<Response> {
  const rows = await sb(env, "PATCH", `editorial_packages?id=eq.${packageId}`, {
    status: "archived", patrick_reviewed_at: new Date().toISOString(),
    patrick_notes: `Archived: ${reason}`.slice(0, 2000),
  }, "return=representation");
  const pkg = rows?.[0];
  if (!pkg) return json({ error: "package not found" }, 404);
  await sb(env, "PATCH", `interviews?id=eq.${pkg.interview_id}`, { status: "archived" });
  const { app, show } = await interviewWithApp(env, pkg.interview_id);
  await slack(env, `${show.shortLabel}: ${app?.name ?? "episode"} archived (${reason}) — kept, never published.`);
  return json({ ok: true, archived: pkg.id });
}

async function handleArchivePage(req: Request, env: Env, pathToken?: string): Promise<Response> {
  const url = new URL(req.url);
  const given = (pathToken || url.searchParams.get("token") || "").trim();
  const expected = (env.ADMIN_TOKEN || "").trim();
  const archived = await archiveToken(env);
  if (!given || (!tokenEquals(given, expected) && !tokenEquals(given, archived))) {
    return html("<h1>Link not found</h1>", 404);
  }
  const pkgs = (await sb(env, "GET",
    "editorial_packages?status=eq.archived&order=created_at.desc&limit=200" +
    "&select=id,interview_id,interview_run_id,created_at,patrick_notes,transcript_cleaned,transcript_raw")) ?? [];
  const items: string[] = [];
  for (const pkg of pkgs) {
    const { interview, app, show } = await interviewWithApp(env, pkg.interview_id);
    const runs = pkg.interview_run_id ? await sb(env, "GET",
      `interview_runs?id=eq.${pkg.interview_run_id}&select=grok_session_log,duration_sec`) : [];
    const tracks = runs?.[0]?.grok_session_log?.tracks ?? {};
    const audio = tracks?.edit?.url || tracks?.preview || runs?.[0]?.grok_session_log?.voximplant_mix_record_url || "";
    const when = interview?.scheduled_at ? pacificTime(interview.scheduled_at, null, true) : "";
    const transcript = String(pkg.transcript_cleaned || pkg.transcript_raw || "").trim();
    items.push(`<section style="border-top:1px solid #e2e8f0;padding:1rem 0">
      <h2 style="margin:.2rem 0">${esc(app?.name ?? "Unknown guest")}</h2>
      <p style="color:#4a5568;margin:.2rem 0">${esc(show.name)} · recorded ${esc(when)} ·
        ${esc(String(pkg.patrick_notes ?? "archived").replace(/^Archived:\s*/, ""))}</p>
      ${audio ? `<audio controls preload="none" src="${esc(audio)}" style="width:100%"></audio>
        <p><a href="${esc(audio)}">Download the audio</a></p>` : "<p>No edited audio on file.</p>"}
      ${transcript ? `<details><summary>Transcript</summary><pre style="white-space:pre-wrap;font:14px/1.5 system-ui">${esc(transcript.slice(0, 60000))}</pre></details>` : ""}
    </section>`);
  }
  const body = `<p>Recordings kept but never published: replaced by a new recording,
    retired at the guest's request, or tests. Nothing here appears on the site or in
    any feed. Only this link opens it.</p>` + (items.join("") || "<p>Nothing archived yet.</p>");
  return html(page("Archived episodes", body));
}

async function handleArchiveLink(req: Request, env: Env): Promise<Response> {
  // Oct 16 2026: used to be callable from anywhere — anyone could spam
  // Patrick's inbox and force minting of the archive HMAC. Admin only now.
  const denied = requireAdmin(req, env);
  if (denied) return denied;
  const link = `https://api.nerranetwork.com/voices/admin/archive/${await archiveToken(env)}`;
  await email(env, operatorEmail(env), "The episode archive",
    `<p>Hi Patrick,</p><p>Here is the private archive: recordings that are kept but never
     published (replaced by a new recording, retired at a guest's request, or tests).</p>
     <p><a href="${link}">Open the archive</a></p><p>Keep the link to yourself; it is the
     only key.</p><p>— Mira</p>`);
  return html(page("Sent", "<p>The archive link is on its way to Patrick's inbox.</p>"));
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
    `show_lessons?show=in.(${show.slug},network)&status=eq.active&order=decided_at.desc&limit=30`)) ?? [];
  const metrics = (await sb(env, "GET",
    `episode_metrics?interview_id=eq.${pkg.interview_id}`))?.[0] ?? null;
  const metricLine = metrics
    ? `Guest spoke ${Math.round(Number(metrics.guest_talk_share ?? 0) * 100)}% of the words ·
       Mira took ${metrics.mira_turns ?? "?"} turns${metrics.mira_mean_turn_sec ? ` (avg ${metrics.mira_mean_turn_sec}s apart)` : ""} ·
       ${metrics.repeated_questions ?? 0} repeated question(s) ·
       ${metrics.dead_air_sec ?? 0}s dead air · ${metrics.agent_sessions ?? 1} session(s), ${metrics.drops ?? 0} drop(s)`
    : "not measured";
  // Oct 21 2026: a review link decides its own interview's proposals; the
  // standing list is read-only unless the admin token opened the page.
  const isAdmin = !requireAdmin(req, env);
  // Oct 24 2026: the page opens on where the episode stands and what the
  // last click did; the buttons offered are the ones that make sense now.
  const opState = operatorReviewState(pkg, String(app?.name ?? ""), String(app?.email ?? ""));
  const canApprove = ["waiting", "changes_pending"].includes(opState.code);
  const approveLabel = opState.code === "changes_pending"
    ? "Changes made: send the guest the new cut" : "Approve: email the guest their review link";
  const editTx = String(pkg.edit_transcript ?? "").trim();
  const lessonRow = (l: any, kind: "proposed" | "active") => `
    <li style="margin:.5rem 0">
      <b>${esc(String(l.category ?? ""))}</b> — ${esc(String(l.lesson ?? ""))}
      ${l.evidence ? `<br><small style="color:#4a5568">${esc(String(l.evidence))}</small>` : ""}
      ${kind === "proposed"
        ? `<br><button onclick="lesson('${l.id}','active')">Teach Mira this</button>
           <button onclick="lesson('${l.id}','retired')">Discard</button>`
        : (isAdmin ? `<br><button onclick="lesson('${l.id}','retired')">Stop applying this</button>` : "")}
    </li>`;
  return html(`<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">
<title>${esc(show.shortLabel)} — editorial review</title>
<style>body{font:15px/1.6 system-ui;max-width:860px;margin:2rem auto;padding:0 1rem}
pre{white-space:pre-wrap;background:#f7fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;max-height:50vh;overflow:auto}
textarea{width:100%;min-height:80px}button{padding:.6rem 1.2rem;margin-right:.6rem}
h1{border-left:6px solid ${show.brandColor};padding-left:.6rem}</style>
<h1>${esc(show.name)} — editorial review (gate 1)</h1>
<p>Guest: <b>${esc(app?.name ?? "unknown")}</b>${app?.email ? ` (${esc(app.email)})` : ""} · Status: <b>${esc(pkg.status)}</b>${pkg.audio_quality_flag ? ` · ⚠️ ${esc(pkg.audio_quality_flag)}` : ""}</p>
${stateBoxHtml(opState)}
${reviewAudioUrl(run) ? `<audio controls preload="none" src="${esc(reviewAudioUrl(run)!)}" style="width:100%"></audio>` : ""}
<h3>Episode notes</h3><pre>${esc(pkg.episode_notes ?? "")}</pre>
${editTx
  ? `<h3>Transcript of the edit</h3><p><em>What the guest is shown and what listeners hear.</em></p><pre>${esc(editTx)}</pre>
     <details><summary>The room's transcript (the whole recording)</summary><pre>${esc(pkg.transcript_cleaned ?? "")}</pre></details>`
  : `<h3>Cleaned transcript</h3><pre>${esc(pkg.transcript_cleaned ?? "")}</pre>`}
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
<p id="buttons">
${opState.code === "correction_pending"
  ? `<button id="b_correction_made" onclick="decide('correction_made')">Correction made: their approval stands</button>` : ""}
${canApprove ? `<button id="b_approve" onclick="decide('approve')">${esc(approveLabel)}</button>` : ""}
${["published", "killed", "archived", "approved"].includes(opState.code) ? "" : `<button id="b_kill" onclick="decide('kill')">Kill episode</button>
<button id="b_archive" onclick="decide('archive')">Archive (keep, never publish)</button>`}</p>
<div id="status" style="display:none;border-radius:8px;padding:.8rem 1rem;margin:1rem 0"></div>
<script>
const token = new URL(location).searchParams.get('token')
  // Sept 27 2026: the emailed link is /voices/admin/review/<id>/<token>, and the
  // browser keeps that path, so the token has to be read from it too, or every
  // Approve from an email fails with "check the token" (Roddy de la Garza).
  || ((p) => p.length === 40 ? p : '')(location.pathname.split('/').filter(Boolean).pop() || '');
// Oct 24 2026: every click is answered with what it did ("Mira emailed
// Jason the review link at 12:31; his deadline is Oct 31"), read from the
// server's reply; Kill and Archive ask twice; the page then reloads so the
// status box at the top shows the new state.
const armed = {};
function show(msg, good){
  const el = document.getElementById('status');
  el.textContent = msg; el.style.display = 'block';
  el.style.background = good ? '#f0fdf4' : '#fef2f2';
  el.style.border = '2px solid ' + (good ? '#166534' : '#991b1b');
  el.scrollIntoView({block: 'center', behavior: 'smooth'});
}
async function decide(decision){
  if ((decision === 'kill' || decision === 'archive') && !armed[decision]) {
    armed[decision] = true;
    const b = document.getElementById('b_' + decision);
    if (b) b.textContent = decision === 'kill' ? 'Click again to kill it (the guest gets nothing)' : 'Click again to archive it';
    setTimeout(function(){ armed[decision] = false; if (b) b.textContent = decision === 'kill' ? 'Kill episode' : 'Archive (keep, never publish)'; }, 6000);
    return;
  }
  const buttons = Array.from(document.querySelectorAll('#buttons button'));
  buttons.forEach(function(b){ b.disabled = true; });
  show('Working\u2026', true);
  let data = null, ok = false;
  try {
    const resp = await fetch('/voices/editorial-decision?token='+token, {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({package_id:'${pkg.id}', decision,
        notes: document.getElementById('notes').value,
        note_to_guest: document.getElementById('to_guest').value})});
    data = await resp.json().catch(function(){ return null; });
    ok = resp.ok && data && data.ok;
  } catch (e) { ok = false; }
  if (!ok) {
    buttons.forEach(function(b){ b.disabled = false; });
    show('That did not go through, and nothing changed. ' + ((data && data.error) || 'Check the link (the token may be wrong) and try again.'), false);
    return;
  }
  show((data && data.message) || 'Done.', true);
  setTimeout(function(){ location.reload(); }, 4000);
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
    // Sept 26 2026: no longer called by the scenario, which now researches in
    // the background itself (voximplant/scenarios/age_of_ai_interview.js,
    // researchInBackground). The old instruction here told Mira to "say
    // plainly if it cannot be verified", which is exactly what Patrick does
    // not want said on air.
    instruction:
      "Carry on the conversation. Do not mention checking, searching or "
      + "sources, and never say something cannot be verified.",
  });
}

// -- Scheduled: gate-2 housekeeping ------------------------------------------

/** The guest (or the clock) approved: production is dispatched FIRST and
 *  the package is marked approved only once GitHub has the event. A thrown
 *  dispatch leaves the package at approved_by_patrick with the interview at
 *  "approved", which gate2Housekeeping retries daily (Oct 21 2026 — status
 *  was written before the dispatch, so a failed dispatch left a package
 *  that read as approved and never published). */
async function approveAndDispatch(env: Env, pkg: any, interviewId: string, when: string) {
  await sb(env, "PATCH", `interviews?id=eq.${interviewId}`, { status: "approved" });
  await dispatch(env, "interview-approved-by-guest", { interview_id: interviewId });
  await sb(env, "PATCH", `editorial_packages?id=eq.${pkg.id}`,
    { status: "approved_by_guest", guest_reviewed_at: pkg.guest_reviewed_at ?? when });
}

async function gate2Housekeeping(env: Env) {
  const now = Date.now();
  const pkgs = await sb(env, "GET",
    "editorial_packages?status=eq.approved_by_patrick&guest_review_deadline=not.is.null");
  for (const pkg of pkgs ?? []) {
    // Oct 21 2026: one failed email (a bounced address, Resend down for a
    // minute) used to throw out of the loop and stop every later package
    // that day. Each package is its own try.
    try {
      await gate2Package(env, pkg, now);
    } catch (err: any) {
      console.error(`gate2: package ${pkg.id} failed: ${err?.message ?? err}`);
    }
  }
}

async function gate2Package(env: Env, pkg: any, now: number) {
    const deadline = Date.parse(pkg.guest_review_deadline);
    const { interview, app, show } = await interviewWithApp(env, pkg.interview_id);
    if (!interview || !app) {
      console.error(`gate2: package ${pkg.id} has no interview/application — skipped`);
      return;
    }
    if (String(interview.status) === "approved") {
      // The guest approved and the production dispatch failed at the time
      // (see approveAndDispatch). Try again now rather than at day 7.
      await approveAndDispatch(env, pkg, interview.id, new Date().toISOString());
      await slack(env, `${show.shortLabel}: package ${pkg.id} — production dispatched on retry`);
      return;
    }
    if (now >= deadline) {
      // Day 7: auto-approve (spec §7) — guest can still request takedown.
      await approveAndDispatch(env, pkg, interview.id, new Date().toISOString());
      await slack(env, `${show.shortLabel}: package ${pkg.id} AUTO-APPROVED (7-day window elapsed)`);
    } else if (deadline - now < 3 * 864e5 && deadline - now > 2 * 864e5) {
      // Day 4 (±cron granularity): one reminder.
      const link = `https://api.nerranetwork.com/voices/review/${pkg.guest_review_token}`;
      await email(env, app.email, `Reminder: your ${show.shortLabel} episode is waiting for you`,
        `<p>Hi ${esc(firstName(app.name))},</p>
         <p>A gentle reminder: your episode is edited and waiting for you to listen and
         approve it.</p>
         <p><a href="${esc(link)}">Listen and approve, or ask for changes</a></p>
         <p>If I don't hear from you in the next three days I'll take that as approval,
         and you can still ask for changes after it publishes.</p>${miraSignature(show)}`, true,
        publicistCc(app));
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
  return expected.length > 0 && tokenEquals(t, expected);
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

// ---------------------------------------------------------------------------
// Studio reliability (Sept 28 2026, after Elliot's interview)
// ---------------------------------------------------------------------------
// Elliot joined with a microphone sending almost nothing (-40 to -55 dB for
// the first hundred seconds). The meter barely moved, Mira heard silence and
// kept asking whether he was there, and he left believing his microphone
// worked. Nobody on our side knew until the cancellation arrived. Three
// endpoints close that gap:
//   /studio-check    the pre-join mic check and the day-before setup test
//   /studio-silence  "nothing heard from the guest" — emails Patrick, once
//   /studio-reschedule  the guest's own "Still not working? Pick another time"
//   (/studio-phone, the guest's "Have Mira call my phone", retired Oct 27 2026)

/** The guest behind an interview, for the operator emails. */
async function interviewGuest(env: Env, interviewId: string): Promise<{
  iv: any; app: any; show: Show;
}> {
  const ivs = await sb(env, "GET",
    `interviews?id=eq.${interviewId}&select=id,status,scheduled_at,call_mode,show,application_id,setup_check`);
  const iv = ivs?.[0] ?? null;
  const apps = iv?.application_id ? await sb(env, "GET",
    `guest_applications?id=eq.${iv.application_id}&select=id,name,email,phone,show`) : [];
  const app = apps?.[0] ?? null;
  return { iv, app, show: showFor(iv, app) };
}

/** Loose E.164: keep digits, assume North America for a bare 10-digit
 *  number (every guest so far), refuse anything that cannot be dialled. */
function phoneE164(raw: unknown): string | null {
  const s = String(raw ?? "").trim();
  if (!s) return null;
  const digits = s.replace(/\D/g, "");
  if (s.startsWith("+") && digits.length >= 8 && digits.length <= 15) return "+" + digits;
  if (digits.length === 10) return "+1" + digits;
  if (digits.length === 11 && digits.startsWith("1")) return "+" + digits;
  if (digits.length >= 8 && digits.length <= 15 && s.startsWith("00")) return "+" + digits.slice(2);
  return null;
}

const MIC_VERDICTS = new Set(["ok", "quiet", "silent", "skipped", "unknown"]);
const ECHO_VERDICTS = new Set(["clean", "borderline", "speakers", "unknown", "not_run"]);

/** POST /voices/studio-check {interview, role?, test?, mic, mic_db?, echo?,
 *  signin?, device?, ua?} — the result of the studio's microphone check,
 *  either before a live join or from the day-before setup test (test=true).
 *  Stored on interviews.setup_check. A failed day-before test emails
 *  Patrick, because that is the one moment there is still time to fix it. */
async function alertStuckGuest(env: Env, iv: any, app: any, show: any, record: any, body: any) {
  const who = app?.name ? String(app.name) : "A guest";
  const when = iv.scheduled_at ? pacificTime(iv.scheduled_at) : "an unscheduled slot";
  const late = Math.max(0, Math.round(Number(body?.minutes_late) || 0));
  // Oct 27 2026: say what is actually true. A guest who pressed Join and
  // failed is not one who "hasn't pressed Join"; one who skipped the check is
  // not locked out; and a check that passed and was then reset (Elliot
  // Justin's camera) reads as "not run yet".
  const joinError = String(body?.join_error ?? "").slice(0, 200);
  const where = body?.join_attempted === true && joinError
    ? `They pressed Join and it failed: ${joinError}.`
    : body?.join_attempted === true
      ? "They pressed Join, but they aren't in the room."
      : body?.join_override === true
        ? "They skipped the microphone check, so Join is open, but they haven't pressed it."
        : record.mic === "ok"
          ? "Their microphone check passed, but they haven't pressed Join."
          : record.mic === "quiet" || record.mic === "silent"
            ? `Their microphone check failed (${record.mic}${record.mic_db !== null ? `, ${record.mic_db} dB` : ""}), so Join is still locked.`
            : body?.mic_access === false
              ? "Their browser hasn't given the studio the microphone, so they can't run the check."
              : "Their microphone check hasn't passed on this page yet, so Join is still locked.";
  const signin = record.signin === "failed"
    ? ` The studio sign-in also failed on their network (${esc(record.signin_error || "no detail")}).` : "";
  const phone = app?.phone ? String(app.phone) : "";
  let link = "";
  try { link = await textGuestLink(env, iv.id); } catch { /* no ADMIN_TOKEN: no link */ }
  try {
    await email(env, operatorEmail(env),
      `${show.shortLabel}: ${who} has the studio open but isn't in the interview`,
      `<p>Hi Patrick,</p><p>${esc(who)} has the studio page open for their interview (${esc(when)}),
       but ${late ? `${late} minutes after the start` : "after the start"} they still aren't in the room with me.
       ${esc(where)}${signin}</p>
       <p>The page is showing them the two steps, a button to carry on from their phone's
       browser, and a button to pick another time.</p>
       ${link ? `<p>If you'd like to nudge them: <a href="${link}">send ${esc(who)} their studio link
       for their phone</a> (a text${phone ? ` to ${esc(phone)}` : ""} and an email).</p>` : ""}
       ${phone ? `<p>Their phone, to reach them yourself: ${esc(phone)}.</p>` : "<p>There's no phone number on file for them.</p>"}
       <p>Device: ${esc(record.device || "unknown")}<br>Browser: ${esc(record.ua || "unknown")}<br>
       Guest email: ${esc(app?.email ?? "unknown")}</p>
       <p>— Mira</p>`);
  } catch (err: any) {
    console.error("stuck-guest email failed:", err?.message ?? err);
  }
  await slack(env, `:warning: ${show.shortLabel}: ${who} has the studio open ${late} min after the start but hasn't joined (mic ${record.mic}). Patrick emailed.`);
}

async function handleStudioCheck(req: Request, env: Env): Promise<Response> {
  const body = await req.json<any>().catch(() => null);
  const interviewId = String(body?.interview ?? "").trim();
  if (!UUID_RE.test(interviewId)) return json({ error: "interview required" }, 400);
  const mic = String(body?.mic ?? "unknown");
  const echo = String(body?.echo ?? "not_run");
  if (!MIC_VERDICTS.has(mic) || !ECHO_VERDICTS.has(echo)) {
    return json({ error: "mic must be ok|quiet|silent|skipped|unknown; echo clean|borderline|speakers|unknown|not_run" }, 400);
  }
  const test = body?.test === true;
  const signin = body?.signin === "ok" || body?.signin === "failed" ? body.signin : "unknown";
  const record = {
    mic, echo, signin, test,
    role: String(body?.role ?? "guest").slice(0, 10),
    mic_db: Number.isFinite(Number(body?.mic_db)) ? Math.round(Number(body.mic_db)) : null,
    device: String(body?.device ?? "").slice(0, 120),
    ua: String(body?.ua ?? "").slice(0, 200),
    signin_error: String(body?.signin_error ?? "").slice(0, 200),
    at: new Date().toISOString(),
  };
  const { iv, app, show } = await interviewGuest(env, interviewId);
  if (!iv) return json({ error: "not found" }, 404);
  // Oct 1 2026 (Jonathan Bautista): the studio page was open, the slot had
  // started, and he never got past the microphone check to Join. Nothing
  // reached Mira, so nothing told anyone. The page now reports a guest who
  // is still outside the room a few minutes after the start, and Patrick
  // is emailed once, with what they are stuck on.
  const stuck = body?.stuck === true && !test && record.role === "guest";
  if (stuck) {
    (record as any).join_attempted = body?.join_attempted === true;
    (record as any).join_error = String(body?.join_error ?? "").slice(0, 200);
  }
  // Oct 27 2026: an alert raised for an earlier slot (the interview has
  // since moved) does not silence this one.
  const priorAlert: string | null = iv.setup_check?.stuck_alerted_at ?? null;
  const alertedBefore: string | null = priorAlert && iv.scheduled_at
    && Date.parse(priorAlert) >= Date.parse(iv.scheduled_at) - STUDIO_OPENS_BEFORE_MS ? priorAlert : null;
  const stuckAlertedAt = stuck && !alertedBefore ? record.at : alertedBefore;
  const history = Array.isArray(iv.setup_check?.history) ? iv.setup_check.history.slice(-9) : [];
  await sb(env, "PATCH", `interviews?id=eq.${interviewId}`,
    { setup_check: { ...record, ...(stuckAlertedAt ? { stuck_alerted_at: stuckAlertedAt } : {}),
      history: [...history, { ...record, ...(stuck ? { stuck: true } : {}) }] } }).catch(() => null);
  if (stuck) {
    if (!alertedBefore) await alertStuckGuest(env, iv, app, show, record, body);
    return json({ ok: true, stuck: true, alerted: !alertedBefore });
  }

  const problems: string[] = [];
  if (mic === "silent") problems.push("the microphone sent no sound at all");
  if (mic === "quiet") problems.push(`the microphone is far too quiet (${record.mic_db ?? "?"} dB when speaking; a normal voice is about -30 dB)`);
  if (mic === "skipped") problems.push("they skipped the microphone check");
  if (echo === "speakers") problems.push("the microphone hears the speakers (no headphones)");
  if (echo === "borderline") problems.push("the microphone faintly hears the speakers");
  if (signin === "failed") problems.push(`the studio sign-in failed (${esc(record.signin_error || "no detail")}); a VPN or firewall is the usual cause`);
  const who = app?.name ? String(app.name) : "A guest";
  const when = iv.scheduled_at ? pacificTime(iv.scheduled_at) : "an unscheduled slot";

  if (problems.length && (test || mic === "skipped")) {
    try {
      await email(env, operatorEmail(env),
        `${show.shortLabel}: ${who}'s studio ${test ? "setup test" : "check"} found a problem`,
        `<p>Hi Patrick,</p><p>${esc(who)} ran the ${test ? "setup test" : "microphone check"} for their
         interview (${esc(when)}) and ${problems.map(esc).join("; ")}.</p>
         <p>Device: ${esc(record.device || "unknown")}<br>Browser: ${esc(record.ua || "unknown")}</p>
         <p>They saw plain-language help on the page. If it is not fixed by the next test, the
         safe options are the same link in their phone's browser with earbuds in, or another time.
         Phone interviews are no longer offered.</p>
         <p>Guest email: ${esc(app?.email ?? "unknown")}${app?.phone ? ` · phone ${esc(String(app.phone))}` : " · no phone on file"}</p>
         <p>— Mira</p>`);
    } catch (err: any) {
      console.error("setup-check email failed:", err?.message ?? err);
    }
  }
  await slack(env, `${show.shortLabel}: ${who} ${test ? "setup test" : "pre-join check"}: mic ${mic}` +
    `${record.mic_db !== null ? ` (${record.mic_db} dB)` : ""}, headphones ${echo}, sign-in ${signin}`);
  return json({ ok: true, problems: problems.length });
}

/** POST /voices/studio-silence {run_id, source: scenario|studio, seconds?,
 *  level_db?} — nothing has been heard from the guest since they joined.
 *  Emails Patrick once per run, whichever side notices first. */
async function handleStudioSilence(req: Request, env: Env): Promise<Response> {
  const { body, denied } = await readSignedJson(req, env, false);
  if (denied) return denied;
  // The room signs its posts; a browser post (source=studio) cannot carry
  // the secret and is accepted as before. A scenario post without a valid
  // signature, when the Worker holds the secret, is refused.
  if (body?.source === "scenario" && (env.VOICES_WEBHOOK_SECRET || "").trim()
      && !req.headers.get(SIGNATURE_HEADER)) {
    return json({ error: "signature required" }, 401);
  }
  const runId = String(body?.run_id ?? "").trim();
  if (!UUID_RE.test(runId)) return json({ error: "run_id required" }, 400);
  const source = body?.source === "scenario" ? "scenario" : "studio";
  const runs = await sb(env, "GET",
    `interview_runs?id=eq.${runId}&select=id,interview_id,status,grok_session_log`);
  const run = runs?.[0];
  if (!run) return json({ error: "run not found" }, 404);
  const log = run.grok_session_log ?? {};
  const alerts = Array.isArray(log.silence_alerts) ? log.silence_alerts : [];
  const entry = {
    source, at: new Date().toISOString(),
    seconds: Number(body?.seconds) || null,
    level_db: Number.isFinite(Number(body?.level_db)) ? Math.round(Number(body.level_db)) : null,
  };
  await sb(env, "PATCH", `interview_runs?id=eq.${runId}`,
    { grok_session_log: { ...log, silence_alerts: [...alerts, entry].slice(-10) } }).catch(() => null);
  if (alerts.length) return json({ ok: true, already_alerted: true });

  const { iv, app, show } = await interviewGuest(env, run.interview_id);
  const who = app?.name ? String(app.name) : "The guest";
  const lead = source === "scenario"
    ? `Mira has heard nothing from the room for ${entry.seconds ?? 30} seconds since ${esc(who)} joined.`
    : `${esc(who)}'s own studio page has measured almost no sound from their microphone for ${entry.seconds ?? 30} seconds` +
      (entry.level_db !== null ? ` (loudest ${entry.level_db} dB)` : "") + ".";
  try {
    await email(env, operatorEmail(env),
      `${show.shortLabel}: Mira can't hear ${who} — live now`,
      `<p>Hi Patrick,</p><p>${lead} Their microphone is almost certainly the wrong one or turned
       down.</p><p>What they see: a yellow box telling them Mira can't hear them, a microphone
       switcher, and after thirty seconds a button to carry on from their phone's browser. Mira is
       telling them the same thing out loud.</p><p>If you want to step in: join as co-host
       (<a href="${esc(hostStudioUrl(env, show, iv?.id ?? ""))}">your studio link</a>), or reply to
       them at ${esc(app?.email ?? "their email")}${app?.phone ? `, or call ${esc(String(app.phone))}` : ""}.</p>
       <p>— Mira</p>`);
  } catch (err: any) {
    console.error("silence email failed:", err?.message ?? err);
  }
  await slack(env, `:mute: ${show.shortLabel}: nothing heard from ${who} (${source}) — Patrick emailed.`);
  return json({ ok: true, alerted: true });
}

/** POST /voices/studio-phone — retired Oct 27 2026. Phone interviews are no
 *  longer offered: a phone line stops at 3.4 kHz, and the last one (Elliot
 *  Justin) had a scam call on top of it. A studio page cached from before
 *  today still has the button; it is told what to do instead. */
function handleStudioPhoneRetired(): Response {
  return json({ error: "We don't do interviews by phone call any more. Open the same studio link " +
    "on your phone's browser with earbuds in, or reply to my email and we'll find another time.",
    retired: true }, 410);
}

/** POST /voices/studio-reschedule {interview} — Oct 27 2026. The studio's
 *  "Still not working? Pick another time": emails the guest, at the address
 *  on file and nowhere else, their link to move the interview, and tells
 *  Patrick. Once per ten minutes, so a page left open cannot repeat it. */
async function handleStudioReschedule(req: Request, env: Env): Promise<Response> {
  const body = await req.json<any>().catch(() => null);
  const interviewId = String(body?.interview ?? "").trim();
  if (!UUID_RE.test(interviewId)) return json({ error: "interview required" }, 400);
  const ivs = await sb(env, "GET",
    `interviews?id=eq.${interviewId}&select=id,status,scheduled_at,show,application_id,manage_token,studio_reschedule_sent_at`);
  const iv = ivs?.[0];
  if (!iv) return json({ error: "not found" }, 404);
  if (!LIVE_INTERVIEW_STATUSES.has(String(iv.status))) {
    return json({ error: "This interview isn't on right now. Reply to my last email and I'll find you a time." }, 409);
  }
  const last = iv.studio_reschedule_sent_at ? Date.parse(iv.studio_reschedule_sent_at) : 0;
  if (Date.now() - last < 10 * 60 * 1000) return json({ ok: true, already_sent: true });
  const app = iv.application_id ? (await sb(env, "GET",
    `guest_applications?id=eq.${iv.application_id}&select=name,email,show,publicist_email`))?.[0] : null;
  if (!app?.email) return json({ error: "There's no email on file. Reply to my last email and I'll find you a time." }, 409);
  const show = showFor(iv, app);
  const move = iv.manage_token
    ? `https://api.nerranetwork.com/voices/manage/${encodeURIComponent(iv.manage_token)}`
    : bookingUrl(env, show);
  try {
    await email(env, app.email, `Let's find another time for ${show.name}`,
      `<p>Hi ${esc(firstName(app.name))},</p><p>I'm sorry the studio didn't cooperate today. That is
       ours to solve, not yours. <a href="${esc(move)}"><strong>Pick another time here</strong></a>;
       nothing is lost, and everything you told us is kept for the conversation.</p>
       <p>On the day, a computer with headphones sounds best, and your phone's browser with earbuds
       in works just as well if the computer won't cooperate.</p>${miraSignature(show)}`, true);
  } catch (err: any) {
    console.error("studio-reschedule email failed:", err?.message ?? err);
    return json({ error: "That didn't go through. Reply to my last email and I'll find you another time." }, 502);
  }
  // Stamped once it has gone, so a failed send can be retried at once.
  await sb(env, "PATCH", `interviews?id=eq.${interviewId}`,
    { studio_reschedule_sent_at: new Date().toISOString() }).catch(() => null);
  await slack(env, `:calendar: ${show.shortLabel}: ${app.name ?? "the guest"} couldn't get the studio working and asked for another time (move link emailed).`);
  return json({ ok: true });
}

async function handleStudioState(req: Request, env: Env): Promise<Response> {
  const url = new URL(req.url);
  const interviewId = url.searchParams.get("interview") ?? "";
  const role: StudioRole = url.searchParams.get("role") === "host" ? "host" : "guest";
  if (!UUID_RE.test(interviewId)) return json({ error: "interview required" }, 400);
  const ivs = await sb(env, "GET",
    `interviews?id=eq.${interviewId}&select=id,status,scheduled_at,call_mode,show,application_id,host_mode,studio_kick_at,studio_alert_at,studio_seen_at`);
  const iv = ivs?.[0];
  if (!iv) return json({ error: "not found" }, 404);
  // Oct 27 2026: the late alert used to assume a page that had opened the
  // room once was still open. The guest's page polls every ten seconds; the
  // newest poll is stamped (at most once a minute) so the alert can tell an
  // open page from a tab that was closed at T-10.
  if (role === "guest" && LIVE_INTERVIEW_STATUSES.has(String(iv.status))) {
    const seen = iv.studio_seen_at ? Date.parse(iv.studio_seen_at) : 0;
    if (Date.now() - seen > 60 * 1000) {
      await sb(env, "PATCH", `interviews?id=eq.${interviewId}`,
        { studio_seen_at: new Date().toISOString() }).catch(() => null);
    }
  }
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
  // Oct 5 2026 (Jon Cheney): the studio opens when the guest arrives. The
  // run is prepared ahead as `staged`; the first person to open the page
  // inside the window turns it into the live room, here, with no GitHub job
  // in between. Conditional on status=staged so two tabs cannot race.
  const openNow = studioOpenable(iv);
  if (latest && latest.status === "staged" && openNow) {
    const opened = await sb(env, "PATCH",
      `interview_runs?id=eq.${latest.id}&status=eq.staged`, { status: "awaiting_guest" },
      "return=representation");
    if (opened?.length) latest.status = "awaiting_guest";
    else {
      const again = await sb(env, "GET", `interview_runs?id=eq.${latest.id}&select=status`);
      if (again?.[0]?.status) latest.status = again[0].status;
    }
  }
  // Oct 5 2026: Elliot Justin's cancelled interview still had a run sitting
  // at awaiting_guest, so his old link would have opened a live room.
  const dead = DEAD_INTERVIEW_STATUSES.has(String(iv.status));
  const run = !dead && latest && JOINABLE_RUN_STATUSES.has(String(latest.status)) ? latest : null;
  // Oct 22 2026: the interview has already happened. Cory O'Daniel, Jason
  // Shumard and Stan Lewis each left the studio page open after the room
  // closed; the page kept asking, there was no joinable run (the run was
  // completed), and every one of them sent Patrick "is in the studio and it
  // has not opened" and dispatched a fire tick for nothing. A finished run is
  // not a missing one: the page is told the interview is over, and nobody is
  // alerted.
  const ended = !run && Boolean(latest) && String(latest.status) === "completed";
  // Nothing prepared and the guest is here: ask for the run now, and tell
  // Patrick once, so nobody waits in an empty room without him knowing.
  const waitingForRun = !run && !ended && openNow && !(latest && latest.status === "staged");
  if (waitingForRun) await rescueStudio(env, iv, show, role);
  const hostMode = latest ? latest.host_mode !== false : iv.host_mode !== false;
  // Oct 23 2026: the points the guest asked the hour to reach, for the
  // studio's "Ask me about…" chips. Their own words back to them, only while
  // a room is joinable.
  let agenda: string[] = [];
  if (run && iv.application_id) {
    const apps = await sb(env, "GET",
      `guest_applications?id=eq.${iv.application_id}&select=guest_agenda`).catch(() => null);
    agenda = studioAgenda(apps?.[0]?.guest_agenda);
  }
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
    // The studio would be open by now; it is being prepared. The page says
    // so instead of "you're early".
    opening: waitingForRun,
    // The interview is over (Oct 22 2026); the page says thank you.
    ended,
    agenda,
  });
}

/** Oct 23 2026: guest_agenda.points as short chip labels (at most five). */
export function studioAgenda(agenda: any): string[] {
  const points = Array.isArray(agenda?.points) ? agenda.points : [];
  return points.map((p: unknown) => String(p ?? "").replace(/\s+/g, " ").trim().slice(0, 120))
    .filter(Boolean).slice(0, 5);
}

// The studio may open from 15 minutes before the start until three hours
// after it, while the interview is still on. Oct 21 2026: three emails said
// "ten minutes"; the copy reads this constant now, so it cannot drift again.
const STUDIO_OPENS_BEFORE_MS = 15 * 60 * 1000;
export const STUDIO_OPENS_BEFORE_TEXT = "fifteen minutes";
const STUDIO_OPEN_UNTIL_MS = 3 * 60 * 60 * 1000;
function studioOpenable(iv: any): boolean {
  if (!["briefed", "scheduled", "in_progress"].includes(String(iv?.status))) return false;
  const at = iv?.scheduled_at ? Date.parse(iv.scheduled_at) : NaN;
  if (!Number.isFinite(at)) return false;
  const now = Date.now();
  return now >= at - STUDIO_OPENS_BEFORE_MS && now <= at + STUDIO_OPEN_UNTIL_MS;
}

async function rescueStudio(env: Env, iv: any, show: any, role: string) {
  const now = Date.now();
  const kicked = iv.studio_kick_at ? Date.parse(iv.studio_kick_at) : 0;
  if (now - kicked > 3 * 60 * 1000) {
    await sb(env, "PATCH", `interviews?id=eq.${iv.id}`, { studio_kick_at: new Date(now).toISOString() });
    try { await dispatch(env, "fire-tick", { source: "studio-rescue", interview_id: iv.id }); }
    catch (err: any) { console.error("studio rescue dispatch failed:", err?.message ?? err); }
  }
  if (!iv.studio_alert_at) {
    await sb(env, "PATCH", `interviews?id=eq.${iv.id}`, { studio_alert_at: new Date(now).toISOString() });
    try {
      const apps = iv.application_id
        ? await sb(env, "GET", `guest_applications?id=eq.${iv.application_id}&select=name`) : [];
      const who = apps?.[0]?.name ?? "A guest";
      await email(env, operatorEmail(env), `${show.shortLabel}: ${who} is in the studio and it has not opened`,
        `<p>${esc(who)} opened the studio (${esc(role)}) for the interview at ${esc(pacificTime(iv.scheduled_at))}
         and there is no prepared run to open. I have asked GitHub to prepare it; if it does not open
         within a few minutes, GitHub Actions is probably down.</p>
         <p>Interview ${esc(iv.id)}</p>`);
    } catch (err: any) { console.error("studio rescue alert failed:", err?.message ?? err); }
  }
}

const JOINABLE_RUN_STATUSES = new Set(["awaiting_guest", "pending", "in_progress"]);
// The statuses an interview holds while it can still happen today.
export const LIVE_INTERVIEW_STATUSES = new Set(["scheduled", "briefed", "in_progress"]);
const DEAD_INTERVIEW_STATUSES = new Set(["cancelled", "missed", "no_show", "killed", "archived", "failed"]);

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
  const { body, denied } = await readSignedJson(req, env, true);
  if (denied) return denied;
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
  // Oct 21 2026: the rehearsal harness's fixture guest joins as a guest leg
  // with `fixture: true` on the event. Nothing here reads it; the leg is
  // recorded like any guest's, so the audio metrics see the same tracks.
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

// ---------------------------------------------------------------------------
// One tick, two clocks (Oct 24 2026)
// ---------------------------------------------------------------------------
//
// The Worker's one cron trigger ("*/5 * * * *") stopped firing at about
// 17:15 UTC on Oct 23, during Cloudflare's cron incident, and stayed dead for
// 23 hours: not brought back by the incident's resolution, a redeploy, or the
// schedule deleted and re-added with the same expression (re-registered as
// "0-59/5" on Oct 24, which fired at the next slot). nerra-scheduler's */5 in
// the same account fired throughout. A guest's T-2h reminder never went out,
// Mira's inbox ran every few hours instead of every half hour, and nothing
// said so. It was Cloudflare's fourth cron incident in ten days.
//
// So the tick has two clocks. Cloudflare fires at :00/:05/...; Supabase's
// pg_cron posts /voices/cron-tick one minute later (migration
// 20261024_voices_backup_clock.sql). Whichever arrives first claims the
// five-minute slot in cron_ticks and runs the jobs; the other finds the slot
// taken and does nothing. Every minute-based decision reads the SLOT, never
// the arrival time, so the backup at :01 runs the :00 jobs. The GitHub
// schedule on nerra_voices_fire_interview.yml stays the third clock.

export type TickSource = "cloudflare" | "supabase" | "manual";
export const TICK_SLOT_MS = 5 * 60 * 1000;
/** A supabase tick with no cloudflare claim in this long means Cloudflare's timer has stopped. */
export const CLOUDFLARE_QUIET_MS = 20 * 60 * 1000;
export const CLOCK_STOPPED_TEXT = "Cloudflare's timer has stopped; the backup clock is carrying reminders.";
export const CLOCK_BACK_TEXT = "Cloudflare's timer is back.";

/** The five-minute UTC slot a firing belongs to. */
export function tickSlot(d: Date): Date {
  return new Date(Math.floor(d.getTime() / TICK_SLOT_MS) * TICK_SLOT_MS);
}

/** "claimed": this clock runs the slot; "taken": another clock already did;
 *  "unknown": Supabase did not answer, so the tick runs anyway (fail open). */
async function claimSlot(env: Env, slot: Date, source: TickSource): Promise<"claimed" | "taken" | "unknown"> {
  try {
    const rows = await sb(env, "POST", "cron_ticks", { slot: slot.toISOString(), source },
                          "resolution=ignore-duplicates,return=representation");
    return Array.isArray(rows) && rows.length > 0 ? "claimed" : "taken";
  } catch (err: any) {
    console.error(`cron tick ${slot.toISOString()} (${source}): claim failed, running anyway:`, err?.message ?? err);
    return "unknown";
  }
}

async function clockAlert(env: Env, subject: string, text: string) {
  await slack(env, text);
  try {
    await email(env, operatorEmail(env), subject,
      `<p>${text}</p><p style="color:#555">The Voices Worker runs each five-minute tick from` +
      ` whichever clock arrives first: Cloudflare's cron, or Supabase's pg_cron one minute later.` +
      ` Live state: <a href="https://api.nerranetwork.com/voices/health">/voices/health</a>.</p><p>Mira</p>`);
  } catch (err: any) {
    console.error("clock alert email failed:", err?.message ?? err);
  }
}

/**
 * The watchdog. The outage is a row in Supabase (cron_clock_state), never
 * memory: a supabase tick that claims a slot with no cloudflare claim in the
 * last CLOUDFLARE_QUIET_MS opens the outage, and only the tick whose PATCH
 * finds it closed alerts; a cloudflare claim closes it and says so once.
 */
async function watchCloudflare(env: Env, slot: Date, source: TickSource) {
  try {
    if (source === "cloudflare") {
      const closed = await sb(env, "PATCH", "cron_clock_state?name=eq.cloudflare&outage_since=not.is.null",
                              { outage_since: null, recovered_at: new Date().toISOString() },
                              "return=representation");
      if (Array.isArray(closed) && closed.length) {
        await clockAlert(env, CLOCK_BACK_TEXT, CLOCK_BACK_TEXT);
      }
      return;
    }
    if (source !== "supabase") return;
    const since = new Date(slot.getTime() - CLOUDFLARE_QUIET_MS).toISOString();
    const recent = await sb(env, "GET",
      `cron_ticks?select=slot&source=eq.cloudflare&slot=gte.${encodeURIComponent(since)}&limit=1`);
    if (Array.isArray(recent) && recent.length) return;
    const opened = await sb(env, "PATCH", "cron_clock_state?name=eq.cloudflare&outage_since=is.null",
                            { outage_since: new Date().toISOString() }, "return=representation");
    if (Array.isArray(opened) && opened.length) {
      await clockAlert(env, "Cloudflare's timer has stopped", CLOCK_STOPPED_TEXT);
    }
  } catch (err: any) {
    console.error("cron watchdog failed:", err?.message ?? err);
  }
}

/** One tick: claim the slot, run its jobs, watch the other clock. */
export async function runTick(env: Env, fired: Date, source: TickSource): Promise<{ slot: string; ran: boolean }> {
  const slot = tickSlot(fired);
  const claim = await claimSlot(env, slot, source);
  if (claim === "taken") {
    console.log(`cron tick ${slot.toISOString()} (${source}): another clock already ran this slot`);
    return { slot: slot.toISOString(), ran: false };
  }
  // */5 tick: punctual fire dispatch (Cloudflare crons fire to the
  // minute; GitHub's own schedule trigger lags up to hours — a real
  // guest sat in a locked studio on Aug 5 2026). Everything downstream
  // is idempotent, so overlapping with the GitHub fallback cron is safe.
  // Oct 9 2026: ONE cron trigger carries all three jobs.
  // The account was then on Workers Free (five cron triggers in total) and
  // the show scheduler needed one back (it is on Workers Paid since); the handler reads the firing minute
  // instead of the trigger string. Every job below is idempotent, so a
  // :00/:30 firing running the five-minute block AND the half-hour block
  // is the same as the two triggers it replaces. Oct 24 2026: the minute is
  // the SLOT's, whichever clock is running it.
  const minute = slot.getUTCMinutes();
  const halfHour = minute % 30 === 0;
  const gate2Hour = slot.getUTCHours() === 17 && minute === 0;
  {
    try {
      // Oct 13 2026: gated on the schedule (fireTickDue); the half-hour
      // ticks dispatch unconditionally as the catch-all.
      if (halfHour || await fireTickDue(env)) {
        await dispatch(env, "fire-tick", { source: "voices-worker-cron" });
      }
    } catch (err: any) {
      console.error("fire-tick dispatch failed:", err?.message ?? err);
    }
    try { await reminderFallback(env); }
    catch (err: any) { console.error("reminder fallback failed:", err?.message ?? err); }
    // Oct 2 2026 (Jason Fishman): a guest who writes "I'm in, nobody's
    // here" during their slot waited for the half-hourly inbox run. While
    // an interview is live the inbox runs every five minutes instead, so
    // Mira answers within minutes.
    try {
      if (await interviewIsLive(env)) await dispatch(env, "producer-tick", { source: "live-interview" });
    } catch (err: any) {
      console.error("live producer-tick failed:", err?.message ?? err);
    }
  }
  // :00/:30 tick: the Nerra Producer inbox job. Same landmine as the fire
  // tick — GitHub delivered the Producer's own */30 schedule roughly
  // every four hours on Sept 5-6 2026, so a publicist's reply waited
  // half a day. Cloudflare fires to the minute; the workflow's
  // concurrency group makes the overlap with GitHub's cron harmless.
  if (halfHour) {
    try {
      // Oct 19 2026: gated on Gmail (producerTickDue) — a runner starts
      // only when a thread is waiting in either mailbox; fail-open.
      if (await producerTickDue(env)) {
        await dispatch(env, "producer-tick", { source: "voices-worker-cron" });
      } else {
        console.log("producer-tick: nothing unprocessed in Gmail; no dispatch");
      }
    } catch (err: any) {
      console.error("producer-tick dispatch failed:", err?.message ?? err);
    }
  }
  // 17:00 UTC: gate-2 housekeeping (guest-review reminders / auto-approve).
  // The slot claim is what keeps its day-4 reminder from going out twice.
  if (gate2Hour) await gate2Housekeeping(env);
  if (claim === "claimed") await watchCloudflare(env, slot, source);
  return { slot: slot.toISOString(), ran: true };
}

// POST /voices/cron-tick — the backup clock (Supabase pg_cron). Bearer
// CRON_TICK_SECRET only; ADMIN_TOKEN is refused. The tick runs under
// waitUntil as well as being awaited, so a caller that stops waiting (pg_net
// gives up at 25 s) never cuts a tick off halfway through its jobs.
async function handleCronTick(req: Request, env: Env, ctx?: ExecutionContext): Promise<Response> {
  const secret = (env.CRON_TICK_SECRET || "").trim();
  const auth = req.headers.get("Authorization") ?? "";
  const m = /^Bearer\s+(.+)$/i.exec(auth);
  const given = m ? m[1].trim() : "";
  const admin = (env.ADMIN_TOKEN || "").trim();
  if (!secret || !given || (admin && tokenEquals(given, admin)) || !tokenEquals(given, secret)) {
    return json({ error: "unauthorized" }, 401);
  }
  const tick = runTick(env, new Date(), "supabase");
  if (ctx) ctx.waitUntil(tick.catch(() => {}));
  return json(await tick);
}

/** The last slot each clock claimed, and the watchdog's state, for /voices/health. */
async function clockHealth(env: Env): Promise<Record<string, unknown>> {
  const out: Record<string, unknown> = {};
  try {
    for (const source of ["cloudflare", "supabase", "manual"]) {
      const rows = await sb(env, "GET",
        `cron_ticks?select=slot,claimed_at&source=eq.${source}&order=slot.desc&limit=1`);
      out[source] = Array.isArray(rows) && rows.length ? rows[0] : null;
    }
    const state = await sb(env, "GET", "cron_clock_state?select=outage_since,recovered_at&name=eq.cloudflare");
    out.cloudflare_outage = Array.isArray(state) && state.length ? state[0] : null;
  } catch (err: any) {
    out.error = err?.message ?? String(err);
  }
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
    cron: { trigger: "0-59/5 * * * * (the one trigger; jobs by the five-minute slot)",
            backup: "Supabase pg_cron 1-59/5 -> POST /voices/cron-tick (first claim of a slot runs it)",
            fire_tick: "every 5 min -> repository_dispatch fire-tick",
            producer_tick: ":00/:30 -> repository_dispatch producer-tick",
            gate2: "17:00 UTC" },
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
      // Oct 21 2026: inbound webhooks are signed by the room when this is set.
      webhook_secret: !!(env.VOICES_WEBHOOK_SECRET || "").trim(),
      calcom_webhook_secret: !!(env.CALCOM_WEBHOOK_SECRET || "").trim(),
      cron_tick_secret: !!(env.CRON_TICK_SECRET || "").trim(),
    },
    shows: Object.keys(SHOWS),
  };
  if (env.SUPABASE_URL && env.SUPABASE_SERVICE_KEY) out.clocks = await clockHealth(env);
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
  async fetch(req: Request, env: Env, ctx?: ExecutionContext): Promise<Response> {
    if (req.method === "POST" && new URL(req.url).pathname.replace(/\/+$/, "") === "/voices/cron-tick") {
      try { return await handleCronTick(req, env, ctx); }
      catch (err: any) {
        console.error("cron-tick failed:", err?.message ?? err);
        return json({ error: "internal error" }, 500);
      }
    }
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
      // Oct 21 2026: the three-question survey Mira emails a day after the room.
      const survey = path.match(/^\/voices\/survey\/([A-Za-z0-9_-]{16,})$/);
      if (survey) {
        return req.method === "POST"
          ? handleSurveySubmit(req, env, survey[1])
          : handleSurveyPage(env, survey[1]);
      }
      const review = path.match(/^\/voices\/review\/([A-Za-z0-9_-]{16,})$/);
      if (review) {
        return req.method === "POST"
          ? handleGuestReviewSubmit(req, env, review[1])
          : handleGuestReviewPage(env, review[1]);
      }
      if (req.method === "GET" && path === "/voices/admin/triage") return handleAdminTriage(req, env);
      if (req.method === "GET" && path === "/voices/admin/archive-link") return handleArchiveLink(req, env);
      if ((req.method === "GET" || req.method === "POST") && path === "/voices/admin/call-guest") return handleCallGuestRetired();
      if ((req.method === "GET" || req.method === "POST") && path === "/voices/admin/text-guest") return handleTextGuest(req, env);
      if ((req.method === "GET" || req.method === "POST") && path === "/voices/join") return handleJoin(req, env);
      const archive = path.match(/^\/voices\/admin\/archive(?:\/([0-9a-f]{40}))?$/);
      if (archive && req.method === "GET") return handleArchivePage(req, env, archive[1]);
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
      if (req.method === "POST" && path === "/voices/studio-check") return handleStudioCheck(req, env);
      if (req.method === "POST" && path === "/voices/studio-silence") return handleStudioSilence(req, env);
      if (req.method === "POST" && path === "/voices/studio-phone") return handleStudioPhoneRetired();
      if (req.method === "POST" && path === "/voices/studio-reschedule") return handleStudioReschedule(req, env);
      if (req.method === "POST" && path === "/voices/studio-text") return handleStudioText(req, env);
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
    // Oct 24 2026: the body is runTick, shared with the backup clock
    // (POST /voices/cron-tick); the slot claim decides which clock runs it.
    await runTick(env, new Date(event.scheduledTime), "cloudflare");
  },
};
