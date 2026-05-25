/**
 * CORS helpers tailored to the gallery Worker.
 *
 * The Worker lives at api.nerranetwork.com and is called from
 * nerranetwork.com (the static site). Every endpoint must:
 *
 *   - Echo the request Origin header *only* when it matches the
 *     allow-list (so we don't accidentally grant credentials access
 *     to arbitrary origins).
 *   - Set `Access-Control-Allow-Credentials: true` because the
 *     subscribe + download flow rely on cookies the browser only
 *     sends when CORS credentials are explicitly allowed.
 *   - Vary on Origin so a CDN can cache per-origin if it ever sits
 *     in front of the Worker.
 */

const ALLOWED_ORIGINS = new Set<string>([
  "https://nerranetwork.com",
  "https://www.nerranetwork.com",
  // Local dev. Adding 127.0.0.1 here so the gallery JS can be tested
  // against the live Worker by serving the static site with
  // `python -m http.server 8080`.
  "http://localhost:8080",
  "http://127.0.0.1:8080",
]);

export function pickOrigin(request: Request): string | null {
  const origin = request.headers.get("Origin");
  if (origin && ALLOWED_ORIGINS.has(origin)) return origin;
  return null;
}

export function corsHeaders(request: Request): HeadersInit {
  const origin = pickOrigin(request);
  const headers: Record<string, string> = {
    Vary: "Origin",
  };
  if (origin) {
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Access-Control-Allow-Credentials"] = "true";
  }
  return headers;
}

export function handlePreflight(request: Request): Response {
  const origin = pickOrigin(request);
  if (!origin) {
    return new Response(null, { status: 403, headers: corsHeaders(request) });
  }
  const headers = new Headers({
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  });
  return new Response(null, { status: 204, headers });
}

export function jsonResponse(
  request: Request,
  status: number,
  body: unknown,
  extraHeaders: HeadersInit = {},
): Response {
  const headers = new Headers(corsHeaders(request));
  headers.set("Content-Type", "application/json; charset=utf-8");
  headers.set("Cache-Control", "no-store");
  for (const [k, v] of Object.entries(extraHeaders)) {
    headers.set(k, v as string);
  }
  return new Response(JSON.stringify(body), { status, headers });
}
