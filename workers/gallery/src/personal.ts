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
 *   POST /api/stripe/webhook             - checkout + cancel lifecycle
 *   GET  /api/feed/<token>/<file>        - token-gated private feed/audio
 *   GET  /api/admin/personal-specs       - batch-builder input (bearer auth;
 *                                          tokens + prefs, NEVER emails)
 */

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

const COOKIE_NAME = "nn_gallery";
const FEED_FILE_RE = /^[A-Za-z0-9_.-]+$/;
const TOKEN_RE = /^[a-f0-9]{16,64}$/;
const NAME_MAX = 40;
const CITY_MAX = 80;

interface MemberRecord {
  shows: string[];
  first_name: string;
  city: string;
  tier: string;          // "personal" | "personal_local"
  status: string;        // "none" | "active" | "cancelled"
  feed_token?: string;
  sub_id?: string;
  updated_at: string;
}

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
    member: {
      preferences: member
        ? {
            shows: member.shows || [],
            first_name: member.first_name || "",
            city: member.city || "",
          }
        : null,
      tier: member?.tier || "none",
      status: member?.status || "none",
      feed_url: active
        ? `https://api.nerranetwork.com/api/feed/${member!.feed_token}/feed.rss`
        : null,
    },
    perks: {
      // Set via `wrangler secret put MEMBER_BOOK_CODE` (or a plain var) —
      // the store-side discount code members redeem on /books.html titles.
      book_discount_code: env.MEMBER_BOOK_CODE || null,
    },
  });
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
  const city = String(body?.city ?? "").trim().slice(0, CITY_MAX);

  const existing = (await loadMember(env, email)) || {
    shows: [], first_name: "", city: "", tier: "none", status: "none",
    updated_at: "",
  };
  const rec: MemberRecord = {
    ...existing,
    shows,
    first_name: firstName,
    city,
    updated_at: new Date().toISOString(),
  };
  await saveMember(env, email, rec);
  return jsonResponse(request, 200, { ok: true, saved: {
    shows, first_name: firstName, city,
  } });
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
    const email = String(
      session.customer_details?.email || session.customer_email || "",
    ).toLowerCase();
    if (!email) {
      console.warn("stripe: membership checkout with no email");
      return jsonResponse(request, 200, { ok: true });
    }
    const existing = (await loadMember(env, email)) || {
      shows: [], first_name: "", city: "", tier: "none", status: "none",
      updated_at: "",
    };
    const token = existing.feed_token || randomToken();
    const rec: MemberRecord = {
      ...existing,
      tier,
      status: "active",
      feed_token: token,
      sub_id: String(session.subscription || existing.sub_id || ""),
      updated_at: new Date().toISOString(),
    };
    await saveMember(env, email, rec);
    await env.RATE_LIMIT_KV.put(`feedtok:${token}`, email);
    if (rec.sub_id) {
      await env.RATE_LIMIT_KV.put(`sub:${rec.sub_id}`, email);
    }
    console.log("stripe: activated", tier, "token", token.slice(0, 8));
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
          default_lineup: (rec.shows?.length ?? 0) < 2,
        });
      }
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return jsonResponse(request, 200, { ok: true, specs });
}
