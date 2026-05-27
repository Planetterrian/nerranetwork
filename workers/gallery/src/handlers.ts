/**
 * Endpoint handlers for the gallery Worker.
 *
 * Pure functions of `(request, env, deps)` — the `deps` argument
 * gives tests a seam to inject fake Buttondown / Resend clients
 * without touching the network. In production, `index.ts` wires the
 * real `buttondown.ts` / `resend.ts` modules in.
 *
 * Endpoint behaviour:
 *
 *   POST /api/subscribe
 *     Body: { email }
 *     - Validate email.
 *     - Subscribe via Buttondown with tag `gallery-subscriber`.
 *     - Issue a 90-day HttpOnly Secure SameSite=Lax JWT cookie.
 *     - 200 { ok: true }.
 *
 *   GET /api/login?email=...
 *     - Validate email.
 *     - Look up the address in Buttondown.
 *     - If subscribed, sign a 15-minute magic-login JWT and email
 *       a link to /api/magic?token=... via Resend.
 *     - Always 200 { ok: true } regardless of whether the email
 *       exists, to avoid enumeration.
 *
 *   GET /api/magic?token=...
 *     - Verify the magic-login JWT.
 *     - On success: issue the 90-day cookie and 302 to /gallery.html.
 *     - On failure: 400.
 *
 *   GET /api/download?key=<r2_object_key>
 *     - Verify the gallery-subscriber cookie.
 *     - Check per-email revocation KV blacklist (Item 3).
 *     - Validate the key is well-formed (no traversal / absolute paths).
 *     - Fetch the R2 object via the bound bucket.
 *     - Stream it back with Content-Disposition: attachment.
 *
 * Revocation (Item 3, May 2026): operator sets a KV key under the
 * RATE_LIMIT_KV binding ("revoke:email@ex.com" = timestamp). All
 * download + magic flows check it after JWT validation and refuse
 * access (403/401). Stateless JWTs remain lightweight; revocation is
 * immediate without rotating secrets.
 *
 * Spec deviation note: the project spec calls for "generates
 * short-lived signed R2 URL, 302 redirects" on /api/download. We
 * proxy the bytes through the Worker instead because:
 *   - it re-validates the JWT on every request (revocation works);
 *   - signed URLs would be cacheable in browser history & shareable;
 *   - no SigV4 plumbing or third-party deps are required.
 * For the low-traffic gallery this costs negligible Worker bandwidth
 * (under the free tier). Documented in docs/gallery_storage.md.
 */

import { corsHeaders, jsonResponse } from "./cors";
import { signJwt, verifyJwt } from "./jwt";
import { buildMagicLinkEmail } from "./magic-email";
import type {
  ButtondownClient,
  Env,
  HandlerDeps,
  ResendClient,
} from "./types";


// ---------------------------------------------------------------------------
// Tunables
// ---------------------------------------------------------------------------

const SUBSCRIBER_TAG = "gallery-subscriber";
const COOKIE_NAME = "nn_gallery";
const SUBSCRIBER_TTL_SECONDS = 90 * 24 * 60 * 60;   // 90 days
const MAGIC_TTL_SECONDS = 15 * 60;                  // 15 minutes
const MAGIC_TTL_MINUTES = 15;

// Email shape — loose RFC compliance is fine here; the upstream
// (Buttondown) and the SMTP path will reject obvious garbage.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// R2 key safety — every gallery key looks like
// "<slug>/<YYYY-MM-DD>/<episode>/<imageid>.<ext>" so we only allow
// alphanumerics, dashes, underscores, dots, and slashes, and we
// explicitly reject anything that contains a path traversal segment
// or starts with a slash (which would be an absolute path).
const KEY_SAFE_RE = /^[A-Za-z0-9_./-]+$/;

const REDIRECT_AFTER_MAGIC = "https://nerranetwork.com/gallery.html";

// Simple KV-based rate limiting (medium item).
// 5 attempts per 10 minutes per IP on subscribe + login routes.
// This protects Buttondown/Resend quotas and Worker resources.
const RATE_LIMIT_ATTEMPTS = 5;
const RATE_LIMIT_WINDOW_SECONDS = 10 * 60;

// Per-email revocation (Item 3 of May 2026 review).
// Operator revokes via wrangler KV CLI (or dashboard) using the same
// RATE_LIMIT_KV binding:  wrangler kv key put --binding RATE_LIMIT_KV "revoke:email@ex.com" "2026-05-24"
// The value is the revocation timestamp (human readable). Download/login
// paths check this after JWT validation and hard-fail with 403/401.
const REVOCATION_PREFIX = "revoke:";

async function checkRateLimit(
  env: Env,
  route: "subscribe" | "login",
  ip: string,
): Promise<{ allowed: boolean; retryAfter?: number }> {
  if (!env.RATE_LIMIT_KV) {
    // No KV binding configured yet — fail open (don't block legitimate traffic).
    return { allowed: true };
  }

  const key = `rl:${route}:${ip}`;
  const now = Math.floor(Date.now() / 1000);
  const windowStart = now - (now % RATE_LIMIT_WINDOW_SECONDS);

  const current = await env.RATE_LIMIT_KV.get(key);
  const count = current ? parseInt(current, 10) : 0;

  if (count >= RATE_LIMIT_ATTEMPTS) {
    const retryAfter = RATE_LIMIT_WINDOW_SECONDS - (now % RATE_LIMIT_WINDOW_SECONDS);
    return { allowed: false, retryAfter };
  }

  // Increment (best-effort, fire-and-forget)
  await env.RATE_LIMIT_KV.put(key, String(count + 1), {
    expirationTtl: RATE_LIMIT_WINDOW_SECONDS + 60,
  });

  return { allowed: true };
}


async function isEmailRevoked(env: Env, email: string): Promise<boolean> {
  if (!env.RATE_LIMIT_KV) {
    return false; // fail-open for revocation (no lockout on misconfig)
  }
  const key = REVOCATION_PREFIX + email;
  const val = await env.RATE_LIMIT_KV.get(key);
  return !!val; // presence = revoked (value is the timestamp for audit)
}


// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

export async function handleSubscribe(
  request: Request,
  env: Env,
  deps: HandlerDeps,
): Promise<Response> {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";

  const rate = await checkRateLimit(env, "subscribe", ip);
  if (!rate.allowed) {
    return jsonResponse(
      request,
      429,
      { ok: false, error: "rate limited", retryAfter: rate.retryAfter },
      { "Retry-After": String(rate.retryAfter || 600) }
    );
  }

  let body: any;
  try {
    body = await request.json();
  } catch {
    return jsonResponse(request, 400, { ok: false, error: "invalid json" });
  }
  const email = normaliseEmail(body?.email);
  if (!email) {
    return jsonResponse(request, 400, { ok: false, error: "invalid email" });
  }

  const result = await deps.buttondown.subscribe(
    env.BUTTONDOWN_API_KEY,
    email,
    SUBSCRIBER_TAG,
  );

  if (!result.ok) {
    // Don't leak upstream detail to the client; logged in the Worker tail.
    console.warn("subscribe: buttondown failure", result.error, result.status);
    return jsonResponse(request, 502, { ok: false, error: "subscribe failed" });
  }

  const token = await signJwt(
    {
      sub: email,
      scope: "gallery-subscriber",
      ttlSeconds: SUBSCRIBER_TTL_SECONDS,
    },
    env.JWT_SECRET,
  );

  return jsonResponse(
    request,
    200,
    { ok: true, alreadySubscribed: result.alreadySubscribed },
    { "Set-Cookie": cookieFor(token, SUBSCRIBER_TTL_SECONDS) },
  );
}


export async function handleLogin(
  request: Request,
  env: Env,
  deps: HandlerDeps,
): Promise<Response> {
  const url = new URL(request.url);
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";

  const rate = await checkRateLimit(env, "login", ip);
  if (!rate.allowed) {
    return jsonResponse(
      request,
      429,
      { ok: false, error: "rate limited", retryAfter: rate.retryAfter },
      { "Retry-After": String(rate.retryAfter || 600) }
    );
  }

  const email = normaliseEmail(url.searchParams.get("email"));
  if (!email) {
    return jsonResponse(request, 400, { ok: false, error: "invalid email" });
  }

  // Always-200 contract: don't disclose whether the address is in
  // the list. Internal failures still 200 — the operator can spot
  // them in Worker logs / Resend dashboard.
  try {
    const check = await deps.buttondown.isSubscribed(
      env.BUTTONDOWN_API_KEY,
      email,
    );
    if (check.ok && check.exists) {
      const token = await signJwt(
        { sub: email, scope: "magic-login", ttlSeconds: MAGIC_TTL_SECONDS },
        env.JWT_SECRET,
      );
      const magicUrl = `https://${url.host}/api/magic?token=${encodeURIComponent(token)}`;
      const mail = buildMagicLinkEmail({
        magicUrl,
        ttlMinutes: MAGIC_TTL_MINUTES,
      });
      const send = await deps.resend.sendEmail(
        env.RESEND_API_KEY,
        env.RESEND_FROM_EMAIL,
        { to: email, subject: mail.subject, html: mail.html, text: mail.text },
      );
      if (!send.ok) {
        console.warn("login: resend failure", send.error, send.status);
      }
    } else if (!check.ok) {
      console.warn("login: buttondown lookup failure", check.error, check.status);
    }
  } catch (e) {
    console.warn("login: unexpected error", (e as Error).message);
  }

  return jsonResponse(request, 200, { ok: true });
}


export async function handleMagic(
  request: Request,
  env: Env,
  _deps: HandlerDeps,
): Promise<Response> {
  const url = new URL(request.url);
  const token = url.searchParams.get("token") ?? "";
  const verify = await verifyJwt(token, env.JWT_SECRET, {
    expectedScope: "magic-login",
  });
  if (!verify.ok || !verify.claims) {
    return new Response(
      "This sign-in link has expired or is invalid. Request a fresh one from the gallery.",
      {
        status: 400,
        headers: { "Content-Type": "text/plain; charset=utf-8" },
      },
    );
  }

  // Item 3: block magic login for revoked emails (prevents fresh long-lived cookie)
  const magicEmail = (verify.claims.sub || "").toLowerCase();
  if (magicEmail && await isEmailRevoked(env, magicEmail)) {
    return new Response(
      "This subscription has been revoked. Please contact support if you believe this is an error.",
      { status: 403, headers: { "Content-Type": "text/plain; charset=utf-8" } },
    );
  }

  const cookieToken = await signJwt(
    {
      sub: verify.claims.sub,
      scope: "gallery-subscriber",
      ttlSeconds: SUBSCRIBER_TTL_SECONDS,
    },
    env.JWT_SECRET,
  );
  return new Response(null, {
    status: 302,
    headers: {
      Location: REDIRECT_AFTER_MAGIC,
      "Set-Cookie": cookieFor(cookieToken, SUBSCRIBER_TTL_SECONDS),
      "Cache-Control": "no-store",
    },
  });
}


export async function handleDownload(
  request: Request,
  env: Env,
  _deps: HandlerDeps,
): Promise<Response> {
  const url = new URL(request.url);
  const key = url.searchParams.get("key") ?? "";
  if (!isSafeKey(key)) {
    return jsonResponse(request, 400, { ok: false, error: "invalid key" });
  }
  const cookieToken = readCookie(request.headers.get("Cookie"), COOKIE_NAME);
  if (!cookieToken) {
    return jsonResponse(request, 401, { ok: false, error: "auth required" });
  }
  const verify = await verifyJwt(cookieToken, env.JWT_SECRET, {
    expectedScope: "gallery-subscriber",
  });
  if (!verify.ok) {
    return jsonResponse(request, 401, { ok: false, error: "auth required" });
  }

  // Item 3: per-email revocation check (after JWT, before streaming bytes)
  const claimsEmail = (verify.claims?.sub || "").toLowerCase();
  if (claimsEmail && await isEmailRevoked(env, claimsEmail)) {
    return jsonResponse(request, 403, { ok: false, error: "subscription revoked" });
  }

  const object = await env.GALLERY_BUCKET.get(key);
  if (!object) {
    return jsonResponse(request, 404, { ok: false, error: "not found" });
  }
  const headers = new Headers(corsHeaders(request));
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  // Force a download dialog rather than inline display; the
  // filename strips the bucket path prefix so the browser saves
  // the image as "<image_id>.jpeg" not the full key.
  const filename = key.split("/").pop() ?? "image";
  headers.set(
    "Content-Disposition",
    `attachment; filename="${filename}"`,
  );
  headers.set("Cache-Control", "private, max-age=60");
  return new Response(object.body, { status: 200, headers });
}


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function normaliseEmail(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const s = raw.trim().toLowerCase();
  if (!EMAIL_RE.test(s)) return null;
  if (s.length > 254) return null;
  return s;
}

export function isSafeKey(key: string): boolean {
  if (!key || key.length > 256) return false;
  if (key.startsWith("/")) return false;
  if (key.includes("..")) return false;
  if (key.includes("//")) return false;
  return KEY_SAFE_RE.test(key);
}

function cookieFor(token: string, ttlSeconds: number): string {
  // Domain not set — defaults to the Worker's host. The frontend
  // calls the Worker cross-origin with credentials:'include', so the
  // browser sends the cookie back as long as SameSite=None... but
  // SameSite=None requires Secure (which we have) AND allows the
  // cookie cross-site, which we don't want. Keep SameSite=Lax and
  // route the frontend through fetch(credentials:'include'); the
  // CORS Allow-Credentials header on the response is what lets the
  // browser persist the cookie set by a cross-origin response.
  return [
    `${COOKIE_NAME}=${token}`,
    "Path=/",
    "HttpOnly",
    "Secure",
    "SameSite=Lax",
    `Max-Age=${ttlSeconds}`,
  ].join("; ");
}

function readCookie(header: string | null, name: string): string | null {
  if (!header) return null;
  const parts = header.split(/;\s*/);
  for (const part of parts) {
    const eq = part.indexOf("=");
    if (eq === -1) continue;
    if (part.slice(0, eq) === name) {
      return decodeURIComponent(part.slice(eq + 1));
    }
  }
  return null;
}
