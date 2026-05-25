/**
 * Minimal JSON Web Token implementation for the gallery Worker.
 *
 * HS256 only (HMAC-SHA256) — symmetric signing with a shared secret
 * the Worker holds in `env.JWT_SECRET`. We don't need RS256 / ES256
 * because both ends of every token are the Worker itself.
 *
 * Why hand-rolled rather than a library: the standard libraries
 * (`jose`, `jsonwebtoken`) carry kilobytes of optional features we
 * don't use (RSA / EdDSA / JWE / JWKS resolution) and pull in
 * dependencies that have caused supply-chain incidents in the past.
 * Three small primitives (base64url encode/decode + HMAC-SHA256) are
 * directly available on the Workers runtime via `crypto.subtle`, so
 * the dependency adds nothing.
 *
 * Two token scopes live in the same secret + verifier:
 *   - `gallery-subscriber` — long-lived (90 d) cookie issued after
 *     successful Buttondown subscription OR magic-link login.
 *   - `magic-login`        — short-lived (15 m) URL-bound token
 *     emailed to existing subscribers. Single-use is enforced by
 *     the cookie issued on consumption (a second visit to the same
 *     magic URL will still issue a fresh cookie — that's a low-risk
 *     replay window inside the 15 m exp).
 */

export type JwtScope = "gallery-subscriber" | "magic-login";

export interface JwtClaims {
  sub: string;        // subject — the visitor's email address
  scope: JwtScope;
  iat: number;        // issued-at, unix seconds
  exp: number;        // expires-at, unix seconds
}

const HEADER_B64 = base64UrlEncode(
  new TextEncoder().encode(JSON.stringify({ alg: "HS256", typ: "JWT" })),
);


// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function signJwt(
  payload: Omit<JwtClaims, "iat" | "exp"> & { ttlSeconds: number },
  secret: string,
  now: number = Math.floor(Date.now() / 1000),
): Promise<string> {
  if (!secret) throw new Error("jwt: empty secret");
  if (payload.ttlSeconds <= 0) throw new Error("jwt: ttlSeconds must be positive");
  const claims: JwtClaims = {
    sub: payload.sub,
    scope: payload.scope,
    iat: now,
    exp: now + payload.ttlSeconds,
  };
  const payloadB64 = base64UrlEncode(
    new TextEncoder().encode(JSON.stringify(claims)),
  );
  const signingInput = `${HEADER_B64}.${payloadB64}`;
  const signature = await hmacSha256(secret, signingInput);
  return `${signingInput}.${base64UrlEncode(signature)}`;
}


export interface VerifyOptions {
  expectedScope?: JwtScope;
  now?: number;
}

export interface VerifyResult {
  ok: boolean;
  claims?: JwtClaims;
  reason?: string;
}

export async function verifyJwt(
  token: string,
  secret: string,
  opts: VerifyOptions = {},
): Promise<VerifyResult> {
  if (!secret) return { ok: false, reason: "empty secret" };
  if (typeof token !== "string" || token.length === 0) {
    return { ok: false, reason: "missing token" };
  }
  const parts = token.split(".");
  if (parts.length !== 3) return { ok: false, reason: "malformed" };

  const [headerB64, payloadB64, sigB64] = parts;

  // Verify signature *before* we trust the header / payload bytes.
  let expectedSig: Uint8Array;
  try {
    expectedSig = await hmacSha256(secret, `${headerB64}.${payloadB64}`);
  } catch (e) {
    return { ok: false, reason: "hmac failed" };
  }
  let providedSig: Uint8Array;
  try {
    providedSig = base64UrlDecode(sigB64);
  } catch {
    return { ok: false, reason: "bad signature encoding" };
  }
  if (!constantTimeEquals(expectedSig, providedSig)) {
    return { ok: false, reason: "signature mismatch" };
  }

  // Parse claims only after signature has been validated.
  let claims: JwtClaims;
  try {
    const json = new TextDecoder().decode(base64UrlDecode(payloadB64));
    claims = JSON.parse(json);
  } catch {
    return { ok: false, reason: "bad payload encoding" };
  }
  if (
    typeof claims.sub !== "string" ||
    typeof claims.scope !== "string" ||
    typeof claims.iat !== "number" ||
    typeof claims.exp !== "number"
  ) {
    return { ok: false, reason: "claims shape" };
  }

  const now = opts.now ?? Math.floor(Date.now() / 1000);
  if (claims.exp <= now) return { ok: false, reason: "expired" };
  if (claims.iat > now + 60) return { ok: false, reason: "issued in future" };
  if (opts.expectedScope && claims.scope !== opts.expectedScope) {
    return { ok: false, reason: "wrong scope" };
  }
  return { ok: true, claims };
}


// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

async function hmacSha256(secret: string, message: string): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(message),
  );
  return new Uint8Array(sig);
}

export function base64UrlEncode(bytes: Uint8Array): string {
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function base64UrlDecode(b64url: string): Uint8Array {
  const pad = b64url.length % 4 === 0 ? "" : "=".repeat(4 - (b64url.length % 4));
  const b64 = b64url.replace(/-/g, "+").replace(/_/g, "/") + pad;
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

function constantTimeEquals(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}
