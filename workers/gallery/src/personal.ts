/**
 * Nerra Personal — member accounts + personalized-feed endpoints.
 *
 * Extends the gallery Worker (same host, same JWT cookie: a "Nerra
 * account" IS the existing gallery-subscriber identity, which is what
 * unifies gallery downloads + newsletter + member perks + the paid
 * personal feed under one sign-in). Everything here degrades to 503
 * "not configured" until the operator provisions the KV namespace,
 * the personal R2 bucket, and the Stripe secrets — the pre-existing
 * gallery routes are untouched either way.
 *
 * Storage (all in the one KV namespace, prefix-separated like rl:/revoke:):
 *   member:<email>   {shows, first_name, city, tier, status,
 *                     feed_token, sub_id, updated_at}
 *   feedtok:<token>  <email>        (deleted on cancel = instant revoke)
 *   sub:<subId>      <email>        (Stripe subscription -> member)
 *
 * Endpoints:
 *   GET  /api/account                    - member record for the cookie's email
 *   POST /api/account/preferences        - save shows/order/name/city
 *   POST /api/account/rebuild            - build/rebuild today's edition now
 *   POST /api/stripe/webhook             - checkout + cancel lifecycle
 *   GET  /api/feed/<token>/<file>        - token-gated private feed/audio
 *   GET  /api/admin/personal-specs       - batch-builder input (bearer auth;
 *                                          tokens + prefs, NEVER emails)
 */

import {
  BUILD_ETA_MINUTES,
  dispatchAvailable,
  dispatchPersonalBuild,
  noteRebuild,
  todayIso,
  todayStatus,
} from "./build";
import { corsHeaders, jsonResponse } from "./cors";
import { verifyJwt } from "./jwt";
import type { Env } from "./types";

// Closed show vocabulary — mirrors engine.personal_edition.PERSONAL_SHOW_SLUGS
// (the EN edition lineup). Keep the two in sync; an unknown slug is dropped
// server-side, never stored.
export const PERSONAL_SHOWS = [
  "spacex",
  "tesla",
  "fascinating_frontiers",
  "models_agents",
  "planetterrian",
  "omni_view",
  "modern_investing",
  "unintended_consequences",
  "first_principles",
  "models_agents_beginners",
  "env_intel",
  "offshore_north",
  "dp_pod",
] as const;

// Starter lineup for a paying subscriber who hasn't picked 2+ shows yet
// (Aug 27 2026): the builder needs at least two segments to make an
// edition, and the old spec filter silently EXCLUDED such members — they
// paid, their feed URL 404'd forever, and nothing anywhere said why. A
// subscription must always produce a feed; the starter is the network's
// flagship mix, replaced the moment they save their own lineup.
export const DEFAULT_LINEUP = [
  "spacex",
  "tesla",
  "models_agents",
  "planetterrian",
  "dp_pod",
] as const;

// Closed add-on vocabulary — MUST mirror PERSONAL_ADDONS in
// engine/personal_edition.py (drift-guarded in tests/test_nerra_personal.py).
// The Worker validates ids only; tier gating and build behavior live in
// the Python builder, which re-validates everything anyway.
export const PERSONAL_ADDONS = [
  "weather",
  "local_news",
  "events",
  "traffic",
  "markets",
] as const;
const ADDONS_MAX = 8;

const COOKIE_NAME = "nn_gallery";
const FEED_FILE_RE = /^[A-Za-z0-9_.-]+$/;
const TOKEN_RE = /^[a-f0-9]{16,64}$/;
const NAME_MAX = 40;
const CITY_MAX = 80;
// Personal News Network (Sep 13 2026): multiple locations + member
// topics. The Worker stores up to the TOP tier's counts whatever the
// member's plan (so an upgrade applies what they already typed); the
// builder's validate_spec caps to the actual tier. Mirrors
// engine.personal_edition.TIER_LIMITS — drift-guarded.
const CITIES_MAX = 3;
const TOPICS_MAX = 5;
const TOPIC_MAX = 60;

interface MemberRecord {
  shows: string[];
  addons?: string[];   // validated subset of PERSONAL_ADDONS; absent = defaults
  first_name: string;
  city: string;        // primary location — always cities[0] (legacy readers)
  cities?: string[];   // all locations, member's order, ≤ CITIES_MAX
  topics?: string[];   // member-named subjects, ≤ TOPICS_MAX
  tier: string;          // "personal" | "personal_local"
  status: string;        // "none" | "active" | "cancelled"
  feed_token?: string;
  sub_id?: string;
  customer_id?: string;  // Stripe customer — needed to open the billing portal
  ends_at?: string;      // ISO date when a cancel-at-period-end takes effect
  trial_ends_at?: string; // ISO date the free trial converts (Sep 17 2026)
  updated_at: string;
}

/** Subscription statuses that mean "stop serving now" when seen on
 *  customer.subscription.updated — a trial that ended without a working
 *  card lands here (unpaid / canceled) before, or instead of, the
 *  .deleted event, depending on the dunning settings. */
const DEAD_STATUSES = new Set(["canceled", "unpaid", "incomplete_expired"]);

function isoDate(unixSeconds: unknown): string | undefined {
  const n = Number(unixSeconds);
  return n > 0 ? new Date(n * 1000).toISOString().slice(0, 10) : undefined;
}

// Checkout references: an opaque, short-lived id the signed-in account
// page appends to the Payment Links as ?client_reference_id=… so the
// webhook can attach the purchase to THIS account even when the wallet
// (Apple Pay / Link) reports a different email than the one signed in.
// Seen for real on 2026-09-06: checkout prefilled with one address, the
// membership landed on another. Never the email itself in a URL.
const CREF_TTL_SECONDS = 60 * 60;
const CREF_RE = /^[a-f0-9]{32}$/;

function notConfigured(request: Request): Response {
  return jsonResponse(request, 503, {
    ok: false,
    error: "personal tier not configured",
  });
}

async function emailFromCookie(
  request: Request,
  env: Env,
): Promise<string | null> {
  const header = request.headers.get("Cookie");
  if (!header) return null;
  let token: string | null = null;
  for (const part of header.split(/;\s*/)) {
    const eq = part.indexOf("=");
    if (eq !== -1 && part.slice(0, eq) === COOKIE_NAME) {
      token = decodeURIComponent(part.slice(eq + 1));
    }
  }
  if (!token) return null;
  const verify = await verifyJwt(token, env.JWT_SECRET, {
    expectedScope: "gallery-subscriber",
  });
  if (!verify.ok || !verify.claims?.sub) return null;
  return (verify.claims.sub as string).toLowerCase();
}

async function loadMember(env: Env, email: string): Promise<MemberRecord | null> {
  if (!env.RATE_LIMIT_KV) return null;
  const raw = await env.RATE_LIMIT_KV.get(`member:${email}`);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as MemberRecord;
  } catch {
    return null;
  }
}

async function saveMember(env: Env, email: string, rec: MemberRecord) {
  await env.RATE_LIMIT_KV!.put(`member:${email}`, JSON.stringify(rec));
}

// ---------------------------------------------------------------------------
// GET /api/account
// ---------------------------------------------------------------------------

export async function handleAccount(request: Request, env: Env): Promise<Response> {
  const email = await emailFromCookie(request, env);
  if (!email) {
    return jsonResponse(request, 401, { ok: false, error: "auth required" });
  }
  const member = env.RATE_LIMIT_KV ? await loadMember(env, email) : null;
  const active = member?.status === "active" && member.feed_token;
  return jsonResponse(request, 200, {
    ok: true,
    shows: PERSONAL_SHOWS,
    // The member's own address, for "signed in as" on their own page.
    // (The admin export stays email-free; this is the account holder.)
    email,
    member: {
      preferences: member
        ? {
            shows: member.shows || [],
            first_name: member.first_name || "",
            city: member.city || "",
            cities: member.cities ?? (member.city ? [member.city] : []),
            topics: member.topics ?? [],
            addons: member.addons ?? null,
          }
        : null,
      tier: member?.tier || "none",
      status: member?.status || "none",
      ends_at: member?.ends_at || null,
      trial_ends_at: member?.trial_ends_at || null,
      feed_url: active
        ? `https://api.nerranetwork.com/api/feed/${member!.feed_token}/feed.rss`
        : null,
      // True when the page may offer "Manage plan & billing" (portal) —
      // a member with a Stripe subscription and a Worker that has the key.
      billing_portal: Boolean(
        env.STRIPE_SECRET_KEY && member && (member.customer_id || member.sub_id)),
      // Today's edition (Sep 17 2026): built when, building now, rebuilds
      // left — so the page can offer "Build my edition now" after a
      // change instead of "check back tomorrow".
      today: active ? await todayStatus(env, member!.feed_token!) : null,
    },
    perks: {
      // Set via `wrangler secret put MEMBER_BOOK_CODE` (or a plain var) —
      // the store-side discount code members redeem on /books.html titles.
      book_discount_code: env.MEMBER_BOOK_CODE || null,
      // Books for members (Sep 14 2026): every Nerra EPUB is included
      // with Personal News Network, served by /api/books/<vol>/<file>.
      // The page carries the catalog (public metadata); this flag says
      // whether the download links will answer for this member.
      library: libraryUnlocked(env, member),
    },
  });
}

function libraryUnlocked(env: Env, member: MemberRecord | null): boolean {
  return Boolean(env.BOOKS_BUCKET && member &&
    member.status === "active" && member.tier === "personal_local");
}

// ---------------------------------------------------------------------------
// GET /api/books/<volume_id>/<file>
//
// Session-checked (cookie), tier-checked (PNN only), streamed from the
// private masters bucket. A top-level navigation from nerranetwork.com
// carries the SameSite=Lax cookie, so a plain <a href> on the account
// page works — no token in the URL, nothing to leak or share.
// ---------------------------------------------------------------------------

const BOOK_VOLUME_RE = /^[a-z0-9_]{3,60}$/;
const BOOK_FILE_RE = /^[a-z0-9_]{3,80}\.epub$/;

export async function handleBookDownload(
  request: Request,
  env: Env,
  volume: string,
  file: string,
): Promise<Response> {
  if (!env.RATE_LIMIT_KV || !env.BOOKS_BUCKET) return notConfigured(request);
  if (!BOOK_VOLUME_RE.test(volume) || !BOOK_FILE_RE.test(file) ||
      !file.startsWith(volume)) {
    return jsonResponse(request, 400, { ok: false, error: "bad request" });
  }
  const email = await emailFromCookie(request, env);
  if (!email) {
    return jsonResponse(request, 401, { ok: false, error: "auth required" });
  }
  const member = await loadMember(env, email);
  if (!libraryUnlocked(env, member)) {
    return jsonResponse(request, 403, {
      ok: false, error: "books are included with Personal News Network",
    });
  }
  const object = await env.BOOKS_BUCKET.get(`books/${volume}/${file}`);
  if (!object) {
    return jsonResponse(request, 404, { ok: false, error: "not found" });
  }
  const headers = new Headers(corsHeaders(request));
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  headers.set("Content-Type", "application/epub+zip");
  headers.set("Content-Disposition", `attachment; filename="${file}"`);
  headers.set("Cache-Control", "private, no-store");
  console.log("books: download", volume, "member", email.slice(0, 3) + "…");
  return new Response(object.body, { status: 200, headers });
}

// ---------------------------------------------------------------------------
// POST /api/account/checkout-ref
//
// Mints a one-hour opaque reference the signed-in page appends to the
// Payment Links (?client_reference_id=…). The webhook resolves it back
// to this account. See CREF_* above.
// ---------------------------------------------------------------------------

export async function handleCheckoutRef(
  request: Request,
  env: Env,
): Promise<Response> {
  if (!env.RATE_LIMIT_KV) return notConfigured(request);
  const email = await emailFromCookie(request, env);
  if (!email) {
    return jsonResponse(request, 401, { ok: false, error: "auth required" });
  }
  const ref = randomToken();
  await env.RATE_LIMIT_KV.put(`cref:${ref}`, email,
    { expirationTtl: CREF_TTL_SECONDS });
  return jsonResponse(request, 200, { ok: true, ref });
}

// ---------------------------------------------------------------------------
// POST /api/account/portal
//
// Opens Stripe's customer portal for the signed-in member — the one
// place to switch Personal ↔ Personal News Network (prorated), update
// the card, or cancel. Replaces the account page's old "upgrade" link,
// which opened a FRESH checkout and would have created a second
// subscription for an existing member (found 2026-09-13).
// ---------------------------------------------------------------------------

const STRIPE_API = "https://api.stripe.com/v1";

async function stripePost(
  env: Env,
  path: string,
  form: Record<string, string>,
): Promise<any> {
  const res = await fetch(`${STRIPE_API}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.STRIPE_SECRET_KEY}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams(form).toString(),
  });
  const body: any = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(`stripe ${path} ${res.status}: ${body?.error?.message || "?"}`);
  }
  return body;
}

async function stripeGet(env: Env, path: string): Promise<any> {
  const res = await fetch(`${STRIPE_API}${path}`, {
    headers: { Authorization: `Bearer ${env.STRIPE_SECRET_KEY}` },
  });
  const body: any = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(`stripe ${path} ${res.status}: ${body?.error?.message || "?"}`);
  }
  return body;
}

export async function handlePortal(
  request: Request,
  env: Env,
): Promise<Response> {
  if (!env.RATE_LIMIT_KV || !env.STRIPE_SECRET_KEY) return notConfigured(request);
  const email = await emailFromCookie(request, env);
  if (!email) {
    return jsonResponse(request, 401, { ok: false, error: "auth required" });
  }
  const member = await loadMember(env, email);
  if (!member || (!member.customer_id && !member.sub_id)) {
    return jsonResponse(request, 404, { ok: false, error: "no subscription" });
  }
  try {
    let customer = member.customer_id || "";
    if (!customer) {
      // Members activated before customer_id was recorded (Sep 2026):
      // look the customer up once from the subscription and remember it.
      const sub = await stripeGet(env, `/subscriptions/${member.sub_id}`);
      customer = String(sub.customer || "");
      if (!customer) throw new Error("subscription has no customer");
      await saveMember(env, email, { ...member, customer_id: customer,
        updated_at: new Date().toISOString() });
    }
    const session = await stripePost(env, "/billing_portal/sessions", {
      customer,
      return_url: "https://nerranetwork.com/account.html",
    });
    return jsonResponse(request, 200, { ok: true, url: String(session.url) });
  } catch (e) {
    console.error("portal: failed", (e as Error).message);
    return jsonResponse(request, 502, { ok: false, error: "portal unavailable" });
  }
}

/** Map a Stripe price id to a tier id, via the two configured vars. */
function tierForPrice(env: Env, priceId: string): string | null {
  if (!priceId) return null;
  if (env.STRIPE_PRICE_PERSONAL && priceId === env.STRIPE_PRICE_PERSONAL) {
    return "personal";
  }
  if (env.STRIPE_PRICE_PNN && priceId === env.STRIPE_PRICE_PNN) {
    return "personal_local";
  }
  return null;
}

// ---------------------------------------------------------------------------
// POST /api/account/preferences
// ---------------------------------------------------------------------------

export async function handlePreferences(
  request: Request,
  env: Env,
): Promise<Response> {
  if (!env.RATE_LIMIT_KV) return notConfigured(request);
  const email = await emailFromCookie(request, env);
  if (!email) {
    return jsonResponse(request, 401, { ok: false, error: "auth required" });
  }
  let body: any;
  try {
    body = await request.json();
  } catch {
    return jsonResponse(request, 400, { ok: false, error: "invalid json" });
  }
  const shows: string[] = [];
  if (Array.isArray(body?.shows)) {
    for (const s of body.shows) {
      const slug = String(s);
      if ((PERSONAL_SHOWS as readonly string[]).includes(slug) &&
          !shows.includes(slug)) {
        shows.push(slug);
      }
    }
  }
  const firstName = String(body?.first_name ?? "").trim().slice(0, NAME_MAX);
  // Locations: `cities` (array) is the Sep 2026 shape; a bare `city`
  // string from an older page becomes a one-element list. Primary `city`
  // is always cities[0] so nothing that reads it needs to change.
  let citiesIn: unknown[] = Array.isArray(body?.cities)
    ? body.cities
    : (body?.city !== undefined ? [body.city] : []);
  const cities = cleanList(citiesIn, CITIES_MAX, CITY_MAX);
  const city = cities[0] ?? "";
  const topics = cleanList(
    Array.isArray(body?.topics) ? body.topics : [], TOPICS_MAX, TOPIC_MAX);
  // addons: absent = leave the stored choice untouched; an array (even
  // empty — a real "no add-ons" choice) replaces it, unknown ids dropped.
  let addons: string[] | undefined;
  if (Array.isArray(body?.addons)) {
    addons = [];
    for (const a of body.addons.slice(0, ADDONS_MAX)) {
      const id = String(a);
      if ((PERSONAL_ADDONS as readonly string[]).includes(id) &&
          !addons.includes(id)) {
        addons.push(id);
      }
    }
  }

  const existing = (await loadMember(env, email)) || {
    shows: [], first_name: "", city: "", tier: "none", status: "none",
    updated_at: "",
  };
  const rec: MemberRecord = {
    ...existing,
    shows,
    first_name: firstName,
    city,
    cities,
    topics,
    ...(addons !== undefined ? { addons } : {}),
    updated_at: new Date().toISOString(),
  };
  await saveMember(env, email, rec);
  return jsonResponse(request, 200, { ok: true, saved: {
    shows, first_name: firstName, city, cities, topics,
    addons: addons !== undefined ? addons : (existing as MemberRecord).addons ?? null,
  } });
}

// ---------------------------------------------------------------------------
// POST /api/account/rebuild
//
// "Build my edition now." Wakes the batch workflow for this one member:
// a first build of today is free (activation should already have done
// it); re-making a date that exists costs one of REBUILDS_PER_DAY. 409
// while a build is in flight, 503 when the Worker has no dispatch token.
// ---------------------------------------------------------------------------

export async function handleRebuild(
  request: Request,
  env: Env,
): Promise<Response> {
  if (!env.RATE_LIMIT_KV || !env.PERSONAL_BUCKET) return notConfigured(request);
  const email = await emailFromCookie(request, env);
  if (!email) {
    return jsonResponse(request, 401, { ok: false, error: "auth required" });
  }
  const member = await loadMember(env, email);
  if (!member || member.status !== "active" || !member.feed_token) {
    return jsonResponse(request, 404, { ok: false, error: "no active subscription" });
  }
  if (!dispatchAvailable(env)) {
    return jsonResponse(request, 503, {
      ok: false, error: "on-demand builds not configured",
    });
  }
  const token = member.feed_token;
  const status = await todayStatus(env, token);
  if (status.building) {
    return jsonResponse(request, 409, {
      ok: false, error: "already building", today: status,
    });
  }
  const replace = Boolean(status.built_at);
  if (replace && status.rebuilds_left <= 0) {
    return jsonResponse(request, 429, {
      ok: false, error: "rebuild limit reached for today", today: status,
    });
  }
  const result = await dispatchPersonalBuild(env, token, {
    date: status.date, replace, reason: "rebuild",
  });
  if (!result.ok) {
    return jsonResponse(request, result.status, { ok: false, error: result.error });
  }
  if (replace) await noteRebuild(env, token, status.date);
  return jsonResponse(request, 202, {
    ok: true,
    eta_minutes: BUILD_ETA_MINUTES,
    today: await todayStatus(env, token),
  });
}

/** Member-typed free text bound for a prompt: tags out whole, control
 *  and markup characters out, whitespace collapsed, length capped,
 *  case-insensitive dedupe, list capped. Same rules as the builder's
 *  _clean_free_text so what the page shows is what Mira gets. */
function cleanList(values: unknown[], maxItems: number, maxChars: number): string[] {
  const out: string[] = [];
  for (const v of values) {
    let t = String(v ?? "").replace(/<[^>]*>/g, " ");
    t = t.replace(/[^\p{L}\p{N}_ \-.,'’&/()]/gu, "");
    t = t.replace(/\s+/g, " ").trim().slice(0, maxChars).trim();
    if (!t) continue;
    if (out.some((x) => x.toLowerCase() === t.toLowerCase())) continue;
    out.push(t);
    if (out.length >= maxItems) break;
  }
  return out;
}

// ---------------------------------------------------------------------------
// POST /api/stripe/webhook
// ---------------------------------------------------------------------------

/** Verify Stripe's `t=...,v1=...` signature header (HMAC-SHA256 of
 * `${t}.${payload}`, 5-minute tolerance). */
export async function verifyStripeSignature(
  payload: string,
  header: string | null,
  secret: string,
  nowSeconds = Math.floor(Date.now() / 1000),
): Promise<boolean> {
  if (!header) return false;
  let t = "";
  const v1s: string[] = [];
  for (const part of header.split(",")) {
    const [k, v] = part.split("=", 2);
    if (k === "t") t = v;
    if (k === "v1") v1s.push(v);
  }
  if (!t || v1s.length === 0) return false;
  if (Math.abs(nowSeconds - parseInt(t, 10)) > 300) return false;
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const mac = await crypto.subtle.sign(
    "HMAC", key, new TextEncoder().encode(`${t}.${payload}`),
  );
  const expected = [...new Uint8Array(mac)]
    .map((b) => b.toString(16).padStart(2, "0")).join("");
  // Constant-time-ish compare (lengths are fixed for SHA-256 hex).
  return v1s.some((sig) => {
    if (sig.length !== expected.length) return false;
    let diff = 0;
    for (let i = 0; i < sig.length; i++) {
      diff |= sig.charCodeAt(i) ^ expected.charCodeAt(i);
    }
    return diff === 0;
  });
}

function randomToken(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function handleStripeWebhook(
  request: Request,
  env: Env,
): Promise<Response> {
  if (!env.RATE_LIMIT_KV || !env.STRIPE_WEBHOOK_SECRET) {
    return notConfigured(request);
  }
  const payload = await request.text();
  const ok = await verifyStripeSignature(
    payload, request.headers.get("Stripe-Signature"),
    env.STRIPE_WEBHOOK_SECRET,
  );
  if (!ok) {
    return jsonResponse(request, 400, { ok: false, error: "bad signature" });
  }
  let event: any;
  try {
    event = JSON.parse(payload);
  } catch {
    return jsonResponse(request, 400, { ok: false, error: "invalid json" });
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data?.object ?? {};
    // Tier comes from the Payment Link's metadata, which Stripe copies
    // onto every Checkout Session the link creates (operator sets
    // {"tier": "personal"|"personal_local"} on each membership link).
    //
    // The marker is REQUIRED, not a hint. This endpoint receives EVERY
    // completed checkout in the account, and since 2026-08-23 that
    // includes the /support.html donation links. The earlier
    // `amount_total >= 799` fallback was written when memberships were
    // the only thing that could complete a checkout here; with donations
    // live it would hand a paid feed to anyone who gave $10 once. An
    // untagged session is not a membership purchase, so it is ignored.
    const tier = session.metadata?.tier;
    if (tier !== "personal" && tier !== "personal_local") {
      console.log(
        "stripe: ignoring non-membership checkout",
        session.metadata?.kind || "untagged",
      );
      return jsonResponse(request, 200, { ok: true });
    }
    // Prefer the signed-in account the page attached (client_reference_id
    // → cref:… → email) over whatever email the wallet reported.
    let email = "";
    const cref = String(session.client_reference_id || "");
    if (CREF_RE.test(cref)) {
      email = (await env.RATE_LIMIT_KV.get(`cref:${cref}`)) || "";
      if (email) await env.RATE_LIMIT_KV.delete(`cref:${cref}`);
    }
    if (!email) {
      email = String(
        session.customer_details?.email || session.customer_email || "",
      ).toLowerCase();
    }
    if (!email) {
      console.warn("stripe: membership checkout with no email");
      return jsonResponse(request, 200, { ok: true });
    }
    const existing = (await loadMember(env, email)) || {
      shows: [], first_name: "", city: "", tier: "none", status: "none",
      updated_at: "",
    };
    const token = existing.feed_token || randomToken();
    // Free trial (Sep 17 2026): the session doesn't say when a trial
    // converts; the subscription does. One read, best-effort — without
    // the key (or on any error) the member is simply "active".
    let trialEndsAt: string | undefined;
    const subId = String(session.subscription || "");
    if (subId && env.STRIPE_SECRET_KEY) {
      try {
        const sub = await stripeGet(env, `/subscriptions/${subId}`);
        if (sub.status === "trialing") trialEndsAt = isoDate(sub.trial_end);
      } catch (e) {
        console.log("stripe: trial lookup skipped:", (e as Error).message);
      }
    }
    const rec: MemberRecord = {
      ...existing,
      tier,
      status: "active",
      feed_token: token,
      sub_id: subId || existing.sub_id || "",
      customer_id: String(session.customer || existing.customer_id || ""),
      ends_at: undefined,
      trial_ends_at: trialEndsAt,
      updated_at: new Date().toISOString(),
    };
    await saveMember(env, email, rec);
    await env.RATE_LIMIT_KV.put(`feedtok:${token}`, email);
    if (rec.sub_id) {
      await env.RATE_LIMIT_KV.put(`sub:${rec.sub_id}`, email);
    }
    console.log("stripe: activated", tier, "token", token.slice(0, 8));
    if (existing.status !== "active") {
      // First edition within minutes of paying (Sep 17 2026) — the
      // starter lineup until they pick shows. Best-effort: a failed or
      // unconfigured dispatch just means the morning batch does it.
      const r = await dispatchPersonalBuild(env, token, {
        date: todayIso(), replace: false, reason: "activation",
      });
      if (!r.ok) console.log("stripe: first-edition dispatch skipped:", r.error);
    }
  } else if (event.type === "customer.subscription.deleted") {
    const subId = String(event.data?.object?.id || "");
    const email = subId
      ? await env.RATE_LIMIT_KV.get(`sub:${subId}`)
      : null;
    if (email) {
      const member = await loadMember(env, email);
      if (member) {
        if (member.feed_token) {
          // Deleting the token mapping revokes the feed IMMEDIATELY —
          // the R2 objects can linger for the lifecycle rule to clean.
          await env.RATE_LIMIT_KV.delete(`feedtok:${member.feed_token}`);
        }
        await saveMember(env, email, {
          ...member,
          status: "cancelled",
          updated_at: new Date().toISOString(),
        });
        console.log("stripe: cancelled sub", subId.slice(0, 12));
      }
    }
  } else if (event.type === "customer.subscription.updated") {
    // A portal plan switch (Personal ↔ PNN) or a cancel-at-period-end.
    // The feed token never changes here — a member's URL survives an
    // upgrade; only the tier (and the add-ons the builder lets it run)
    // moves. Price ids not configured → log and leave the record alone.
    const sub = event.data?.object ?? {};
    const subId = String(sub.id || "");
    const email = subId ? await env.RATE_LIMIT_KV.get(`sub:${subId}`) : null;
    const member = email ? await loadMember(env, email) : null;
    if (!member) {
      console.log("stripe: subscription.updated for unknown sub", subId.slice(0, 12));
      return jsonResponse(request, 200, { ok: true });
    }
    if (DEAD_STATUSES.has(String(sub.status || ""))) {
      // Trial ended with no working card, or Stripe gave up on dunning:
      // revoke exactly as .deleted does, without waiting for it.
      if (member.status === "active") {
        if (member.feed_token) {
          await env.RATE_LIMIT_KV.delete(`feedtok:${member.feed_token}`);
        }
        await saveMember(env, email!, {
          ...member, status: "cancelled", trial_ends_at: undefined,
          updated_at: new Date().toISOString(),
        });
        console.log("stripe: subscription", sub.status, "→ cancelled", subId.slice(0, 12));
      }
      return jsonResponse(request, 200, { ok: true });
    }
    const priceId = String(sub.items?.data?.[0]?.price?.id || "");
    const tier = tierForPrice(env, priceId);
    if (!tier && priceId) {
      console.warn("stripe: unmapped price on subscription.updated", priceId);
    }
    // API 2025-03-31.basil moved current_period_end from the subscription
    // to its items; this endpoint runs on the account default (newer), so
    // read the item first and fall back to the legacy top-level field.
    const periodEnd = sub.items?.data?.[0]?.current_period_end
      ?? sub.current_period_end;
    const endsAt = sub.cancel_at_period_end && periodEnd
      ? new Date(Number(periodEnd) * 1000).toISOString().slice(0, 10)
      : undefined;
    const trialEndsAt = sub.status === "trialing" ? isoDate(sub.trial_end) : undefined;
    const next: MemberRecord = {
      ...member,
      tier: tier || member.tier,
      customer_id: String(sub.customer || member.customer_id || ""),
      ends_at: endsAt,
      trial_ends_at: trialEndsAt,
      updated_at: new Date().toISOString(),
    };
    if (next.tier !== member.tier || next.ends_at !== member.ends_at ||
        next.customer_id !== member.customer_id ||
        next.trial_ends_at !== member.trial_ends_at) {
      await saveMember(env, email!, next);
      console.log("stripe: subscription.updated", member.tier, "→", next.tier,
        endsAt ? `ends ${endsAt}` : "");
    }
  }
  return jsonResponse(request, 200, { ok: true });
}

// ---------------------------------------------------------------------------
// GET /api/feed/<token>/<file>
// ---------------------------------------------------------------------------

export async function handlePersonalFeed(
  request: Request,
  env: Env,
  token: string,
  file: string,
): Promise<Response> {
  if (!env.RATE_LIMIT_KV || !env.PERSONAL_BUCKET) return notConfigured(request);
  if (!TOKEN_RE.test(token) || !FEED_FILE_RE.test(file) ||
      file.includes("..")) {
    return jsonResponse(request, 400, { ok: false, error: "bad request" });
  }
  const email = await env.RATE_LIMIT_KV.get(`feedtok:${token}`);
  if (!email) {
    return jsonResponse(request, 404, { ok: false, error: "not found" });
  }
  const member = await loadMember(env, email);
  if (!member || member.status !== "active") {
    return jsonResponse(request, 404, { ok: false, error: "not found" });
  }
  const object = await env.PERSONAL_BUCKET.get(`personal/${token}/${file}`);
  if (!object) {
    return jsonResponse(request, 404, { ok: false, error: "not found" });
  }
  const headers = new Headers(corsHeaders(request));
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  if (file.endsWith(".rss")) {
    headers.set("Content-Type", "application/rss+xml; charset=utf-8");
  } else if (file.endsWith(".mp3")) {
    headers.set("Content-Type", "audio/mpeg");
  }
  headers.set("Cache-Control", "private, max-age=300");
  return new Response(object.body, { status: 200, headers });
}

// ---------------------------------------------------------------------------
// GET /api/admin/personal-specs
// ---------------------------------------------------------------------------

export async function handleAdminSpecs(
  request: Request,
  env: Env,
): Promise<Response> {
  if (!env.RATE_LIMIT_KV || !env.PERSONAL_ADMIN_TOKEN) {
    return notConfigured(request);
  }
  const auth = request.headers.get("Authorization") || "";
  if (auth !== `Bearer ${env.PERSONAL_ADMIN_TOKEN}`) {
    return jsonResponse(request, 401, { ok: false, error: "auth required" });
  }
  const specs: object[] = [];
  let cursor: string | undefined;
  do {
    const page = await env.RATE_LIMIT_KV.list({
      prefix: "member:",
      cursor,
    });
    for (const key of page.keys) {
      const raw = await env.RATE_LIMIT_KV.get(key.name);
      if (!raw) continue;
      let rec: MemberRecord;
      try {
        rec = JSON.parse(raw);
      } catch {
        continue;
      }
      if (rec.status === "active" && rec.feed_token) {
        // A paying member ALWAYS gets a feed: fewer than 2 chosen shows
        // falls back to the starter lineup instead of silently dropping
        // the member from the build (their feed URL used to 404 forever).
        const chosen = (rec.shows?.length ?? 0) >= 2
          ? rec.shows
          : [...DEFAULT_LINEUP];
        // Deliberately NO email: the batch builder is PII-light.
        specs.push({
          token: rec.feed_token,
          shows: chosen,
          tier: rec.tier,
          first_name: rec.first_name || "",
          city: rec.city || "",
          cities: rec.cities ?? (rec.city ? [rec.city] : []),
          topics: rec.topics ?? [],
          ...(rec.addons !== undefined ? { addons: rec.addons } : {}),
          default_lineup: (rec.shows?.length ?? 0) < 2,
        });
      }
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return jsonResponse(request, 200, { ok: true, specs });
}
