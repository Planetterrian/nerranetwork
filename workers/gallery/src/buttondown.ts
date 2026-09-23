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
  /** On an already-subscribed address: the tags this request ADDED, or
   *  `null` when the merge could not be attempted. `[]` means the
   *  subscriber already carried every tag we would have set. */
  tagsMerged?: string[] | null;
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
  metadata?: Record<string, string>,
): Promise<SubscribeResult> {
  if (!apiKey) return { ok: false, alreadySubscribed: false, error: "no api key" };
  // July 2026: accepts multiple tags so one signup can carry both the
  // list it joined AND the surface that sent it (`src-youtube-ru`), which
  // is what makes a capture attributable in api/funnel.json. A bare
  // string keeps every existing caller working unchanged.
  const tags = (Array.isArray(tag) ? tag : [tag]).filter(
    (t) => typeof t === "string" && t.trim().length > 0,
  );
  // Optional subscriber metadata (Sep 2026 Soft Personal first_name).
  // Only string values, capped keys — never pass through client objects.
  const meta: Record<string, string> = {};
  if (metadata && typeof metadata === "object") {
    for (const [k, v] of Object.entries(metadata).slice(0, 8)) {
      if (typeof k === "string" && typeof v === "string" && k && v) {
        meta[k.slice(0, 40)] = v.slice(0, 80);
      }
    }
  }
  const payload: Record<string, unknown> = {
    email_address: email,
    tags,
    type: "regular",
  };
  if (Object.keys(meta).length > 0) {
    payload.metadata = meta;
  }
  let resp: Response;
  try {
    resp = await fetch(`${BUTTONDOWN_BASE}/subscribers`, {
      method: "POST",
      headers: {
        Authorization: `Token ${apiKey}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
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
    // ...but returning here was how tags became unreachable for anyone
    // already on the list (Sep 2026). Tags were applied on CREATE only, so
    // an address already in Buttondown when the tagged path shipped could
    // never acquire `nerra-member`, a show tag, or a `src-*` source however
    // many times they resubmitted the form — which is why all five
    // subscribers read untagged and `capture.by_source` was empty.
    const merged = await mergeTags(apiKey, email, tags);
    return {
      ok: true,
      alreadySubscribed: true,
      status: resp.status,
      tagsMerged: merged,
    };
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

/** Add `wanted` to an existing subscriber's tags, keeping what they have.
 *
 * Buttondown's PATCH REPLACES the tag array, so this reads the current tags
 * and sends the union. Sending `wanted` alone would silently strip a member's
 * show subscriptions the first time they re-used the footer form — a data loss
 * that would look exactly like a working signup.
 *
 * Best-effort by contract: every failure returns `null` and the caller still
 * reports the subscribe as successful, because the visitor IS on the list and
 * an attribution tag is not worth a 502 on their signup.
 */
async function mergeTags(
  apiKey: string,
  email: string,
  wanted: string[],
): Promise<string[] | null> {
  if (!wanted.length) return [];
  try {
    const lookup = await fetch(
      `${BUTTONDOWN_BASE}/subscribers?email=${encodeURIComponent(email)}`,
      {
        headers: {
          Authorization: `Token ${apiKey}`,
          Accept: "application/json",
        },
      },
    );
    if (!lookup.ok) return null;
    const payload = (await lookup.json()) as any;
    const record = (payload?.results ?? [])[0];
    const id = record?.id;
    if (typeof id !== "string" || !id) return null;

    const existing: string[] = Array.isArray(record.tags)
      ? record.tags.filter((t: unknown) => typeof t === "string")
      : [];
    const have = new Set(existing.map((t) => t.toLowerCase()));
    const added = wanted.filter((t) => !have.has(t.toLowerCase()));
    if (!added.length) return [];

    const patch = await fetch(`${BUTTONDOWN_BASE}/subscribers/${id}`, {
      method: "PATCH",
      headers: {
        Authorization: `Token ${apiKey}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ tags: [...existing, ...added] }),
    });
    return patch.ok ? added : null;
  } catch {
    return null;
  }
}

async function safeText(resp: Response): Promise<string> {
  try {
    return await resp.text();
  } catch {
    return "";
  }
}
