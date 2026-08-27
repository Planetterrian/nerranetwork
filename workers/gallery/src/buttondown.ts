/**
 * Buttondown API client (the subset the gallery Worker needs).
 *
 * Buttondown's API base is https://api.buttondown.email/v1/. Auth is
 * a bearer token in the `Authorization` header (the same key used by
 * the Python newsletter pipeline lives in the `BUTTONDOWN_API_KEY`
 * Worker secret — no new key needs to be provisioned).
 *
 * Two operations:
 *
 *   subscribe({email, tag})  - POST /subscribers
 *                              Idempotent on the API side: a duplicate
 *                              email returns a 4xx with a recognisable
 *                              body ("already subscribed"). We treat
 *                              that as success.
 *
 *   isSubscribed(email)      - GET /subscribers?email=...
 *                              Used by the magic-link login endpoint
 *                              to confirm the visitor exists before
 *                              we mail them anything.
 *
 * Failures are surfaced as `BUTTONDOWN_DOWN` / `BUTTONDOWN_HTTP_<code>`
 * error codes so the handler can map them to user-facing 502s without
 * leaking the upstream error body.
 */

const BUTTONDOWN_BASE = "https://api.buttondown.email/v1";


export interface SubscribeResult {
  ok: boolean;
  alreadySubscribed: boolean;
  error?: string;
  status?: number;
  /** Redacted upstream body, for the Worker log only — never returned
   *  to the client. Without it a Buttondown 400 is unreadable: the code
   *  alone cannot tell "duplicate" from "tag rejected" from "plan
   *  limit", which cost an afternoon on 2026-08-26 when signup broke
   *  and the log said only BUTTONDOWN_HTTP_400. */
  detail?: string;
}


/** Strip anything email-shaped before an upstream body reaches a log. */
export function redact(body: string): string {
  return body
    .replace(/[\w.+-]+@[\w-]+\.[\w.-]+/g, "<email>")
    .slice(0, 300);
}

export async function subscribe(
  apiKey: string,
  email: string,
  tag: string | string[],
): Promise<SubscribeResult> {
  if (!apiKey) return { ok: false, alreadySubscribed: false, error: "no api key" };
  // July 2026: accepts multiple tags so one signup can carry both the
  // list it joined AND the surface that sent it (`src-youtube-ru`), which
  // is what makes a capture attributable in api/funnel.json. A bare
  // string keeps every existing caller working unchanged.
  const tags = (Array.isArray(tag) ? tag : [tag]).filter(
    (t) => typeof t === "string" && t.trim().length > 0,
  );
  let resp: Response;
  try {
    resp = await fetch(`${BUTTONDOWN_BASE}/subscribers`, {
      method: "POST",
      headers: {
        Authorization: `Token ${apiKey}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        email_address: email,
        tags,
        type: "regular",
      }),
    });
  } catch (e) {
    return {
      ok: false,
      alreadySubscribed: false,
      error: `BUTTONDOWN_DOWN: ${(e as Error).message ?? "fetch failed"}`,
    };
  }

  if (resp.status === 201 || resp.status === 200) {
    return { ok: true, alreadySubscribed: false, status: resp.status };
  }

  // Buttondown returns 400 with a "subscriber already exists" body
  // for duplicates. We don't want the visitor's repeat sub to look
  // like a failure — treat as success but flag so the caller can log
  // it as an idempotent re-subscribe.
  const body = await safeText(resp);
  if (resp.status === 400 && /already|exists|present/i.test(body)) {
    return { ok: true, alreadySubscribed: true, status: resp.status };
  }

  return {
    ok: false,
    alreadySubscribed: false,
    status: resp.status,
    error: `BUTTONDOWN_HTTP_${resp.status}`,
    detail: redact(body),
  };
}


export interface IsSubscribedResult {
  ok: boolean;
  exists: boolean;
  error?: string;
  status?: number;
}

export async function isSubscribed(
  apiKey: string,
  email: string,
): Promise<IsSubscribedResult> {
  if (!apiKey) return { ok: false, exists: false, error: "no api key" };
  let resp: Response;
  try {
    resp = await fetch(
      `${BUTTONDOWN_BASE}/subscribers?email=${encodeURIComponent(email)}`,
      {
        method: "GET",
        headers: {
          Authorization: `Token ${apiKey}`,
          Accept: "application/json",
        },
      },
    );
  } catch (e) {
    return {
      ok: false,
      exists: false,
      error: `BUTTONDOWN_DOWN: ${(e as Error).message ?? "fetch failed"}`,
    };
  }
  if (resp.status !== 200) {
    return {
      ok: false,
      exists: false,
      status: resp.status,
      error: `BUTTONDOWN_HTTP_${resp.status}`,
    };
  }
  let body: any;
  try {
    body = await resp.json();
  } catch {
    return { ok: false, exists: false, status: 200, error: "BUTTONDOWN_BAD_JSON" };
  }
  // Buttondown's list endpoint returns { count, results: [...] }.
  // An exact email match is a single result. We don't trust the API
  // to filter perfectly server-side — match on the returned address
  // case-insensitively just to be safe.
  const want = email.toLowerCase();
  const results = Array.isArray(body?.results) ? body.results : [];
  const exists = results.some(
    (r: any) =>
      typeof r?.email_address === "string" &&
      r.email_address.toLowerCase() === want,
  );
  return { ok: true, exists, status: 200 };
}

async function safeText(resp: Response): Promise<string> {
  try {
    return await resp.text();
  } catch {
    return "";
  }
}
