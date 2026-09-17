/**
 * On-demand personal builds (Sep 17 2026).
 *
 * Until now a subscriber's first edition arrived with the next batch
 * run — the morning after they paid, or the morning after they changed
 * their lineup. That is the wrong first impression for a product whose
 * whole point is "it's yours". This module lets the Worker wake the
 * private batch repo's workflow for ONE subscriber:
 *
 *   - activation (Stripe checkout completed) → build today's edition now
 *     (the starter lineup if they haven't picked shows yet);
 *   - POST /api/account/rebuild → rebuild today's edition after a
 *     preference change, REBUILDS_PER_DAY times a day at most.
 *
 * The builder is the source of truth: `--only <token>` restricts a run
 * to that subscriber, `--replace` lets it re-make a date it already
 * built. This module only dispatches and reports state; it never
 * touches R2 except to READ episodes.json for "built today at …".
 *
 * Needs GITHUB_DISPATCH_TOKEN (wrangler secret): a fine-grained PAT
 * scoped to the batch repo with Actions: Read and write — the same
 * token the public repo's nerra-daily.yml uses to chain the daily
 * build. Absent → every dispatch answers "not configured" and the
 * account page hides the button; the scheduled sweeps still run.
 */

import type { Env } from "./types";

export const BATCH_REPO = "Planetterrian/nerra-personal-batch";
export const BATCH_WORKFLOW = "personal-feeds.yml";
/** Rebuilds of an already-built date per subscriber per UTC day. The
 *  first build of a day (activation, or a day the sweep missed) is free. */
export const REBUILDS_PER_DAY = 2;
/** How long "building…" is believed without a new episodes.json row. A
 *  real build takes 3-6 minutes; a failed one leaves nothing behind. */
export const BUILDING_TTL_SECONDS = 20 * 60;
/** Minutes the page quotes as the wait. */
export const BUILD_ETA_MINUTES = 6;

export interface BuildState {
  since: string;   // ISO timestamp of the dispatch
  reason: string;  // "activation" | "rebuild"
  date: string;    // edition date requested
}

export interface TodayStatus {
  date: string;
  built_at: string | null;    // ISO timestamp from the builder, or null
  building: boolean;
  rebuilds_left: number;
  /** False when the Worker cannot dispatch (no token) — the page then
   *  shows when the scheduled build runs instead of a button. */
  available: boolean;
}

export function todayIso(now = new Date()): string {
  return now.toISOString().slice(0, 10);
}

function buildKey(token: string): string {
  return `build:${token}`;
}

function rebuildsKey(token: string, date: string): string {
  return `rebuilds:${token}:${date}`;
}

/** Trim defensively: a `wrangler secret put` paste routinely carries a
 *  trailing newline, and GitHub then answers 401 to `Bearer <tok>\n`
 *  (the Aug 2026 scheduler outage). */
function dispatchToken(env: Env): string {
  return (env.GITHUB_DISPATCH_TOKEN || "").trim();
}

export function dispatchAvailable(env: Env): boolean {
  return dispatchToken(env).length > 0;
}

/** The builder's row for `date`, read from the subscriber's episodes.json. */
export async function readEditionRow(
  env: Env,
  token: string,
  date: string,
): Promise<Record<string, unknown> | null> {
  if (!env.PERSONAL_BUCKET) return null;
  try {
    const obj = await env.PERSONAL_BUCKET.get(`personal/${token}/episodes.json`);
    if (!obj) return null;
    const text = typeof (obj as any).text === "function"
      ? await (obj as any).text()
      : String((obj as any).body ?? "");
    const state = JSON.parse(text) as { episodes?: Record<string, unknown>[] };
    for (const row of state.episodes ?? []) {
      if (row && row.date === date) return row;
    }
  } catch (e) {
    console.warn("build: episodes.json unreadable", token.slice(0, 8),
      (e as Error).message);
  }
  return null;
}

export async function readBuildState(
  env: Env,
  token: string,
): Promise<BuildState | null> {
  if (!env.RATE_LIMIT_KV) return null;
  const raw = await env.RATE_LIMIT_KV.get(buildKey(token));
  if (!raw) return null;
  try {
    return JSON.parse(raw) as BuildState;
  } catch {
    return null;
  }
}

/** What the account page shows for today: built when, building now,
 *  rebuilds left. "Building" clears itself the moment the builder writes
 *  a row newer than the dispatch (or the TTL lapses). */
export async function todayStatus(
  env: Env,
  token: string,
  now = new Date(),
): Promise<TodayStatus> {
  const date = todayIso(now);
  const row = await readEditionRow(env, token, date);
  const builtAt = row && typeof row.built_at === "string" ? row.built_at : null;
  const pending = await readBuildState(env, token);
  let building = false;
  if (pending && pending.date === date) {
    building = !builtAt || builtAt < pending.since;
    if (!building && env.RATE_LIMIT_KV) {
      // The build landed; forget the dispatch so the next status is clean.
      await env.RATE_LIMIT_KV.delete(buildKey(token));
    }
  }
  const used = env.RATE_LIMIT_KV
    ? parseInt((await env.RATE_LIMIT_KV.get(rebuildsKey(token, date))) || "0", 10) || 0
    : 0;
  return {
    date,
    built_at: builtAt,
    building,
    rebuilds_left: Math.max(0, REBUILDS_PER_DAY - used),
    available: dispatchAvailable(env),
  };
}

export type DispatchResult =
  | { ok: true }
  | { ok: false; status: number; error: string };

/** Fire the batch workflow for one subscriber. One retry on GitHub 5xx /
 *  429 / network; 4xx is configuration and is reported, not retried. */
export async function dispatchPersonalBuild(
  env: Env,
  token: string,
  opts: { date: string; replace: boolean; reason: string },
): Promise<DispatchResult> {
  const pat = dispatchToken(env);
  if (!pat) return { ok: false, status: 503, error: "on-demand builds not configured" };
  const url = `https://api.github.com/repos/${BATCH_REPO}/actions/workflows/${BATCH_WORKFLOW}/dispatches`;
  const body = JSON.stringify({
    ref: "main",
    inputs: { date: opts.date, only: token, replace: opts.replace ? "true" : "false" },
  });
  let last = "";
  for (let attempt = 1; attempt <= 2; attempt++) {
    let res: Response;
    try {
      res = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${pat}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "nerra-gallery-api",
          "Content-Type": "application/json",
        },
        body,
      });
    } catch (e) {
      last = `network: ${(e as Error).message}`;
      continue;
    }
    if (res.status === 204) {
      if (env.RATE_LIMIT_KV) {
        const state: BuildState = {
          since: new Date().toISOString(), reason: opts.reason, date: opts.date,
        };
        await env.RATE_LIMIT_KV.put(buildKey(token), JSON.stringify(state),
          { expirationTtl: BUILDING_TTL_SECONDS });
      }
      console.log("build: dispatched", opts.reason, token.slice(0, 8), opts.date,
        opts.replace ? "(replace)" : "");
      return { ok: true };
    }
    const text = await res.text().catch(() => "");
    last = `${res.status} ${text.slice(0, 200)}`;
    if (res.status < 500 && res.status !== 429) break;
  }
  console.error("build: dispatch failed", token.slice(0, 8), last);
  return { ok: false, status: 502, error: "build could not be started" };
}

/** Record one rebuild of an already-built date (36 h TTL so the counter
 *  dies with the day). */
export async function noteRebuild(env: Env, token: string, date: string): Promise<void> {
  if (!env.RATE_LIMIT_KV) return;
  const key = rebuildsKey(token, date);
  const used = parseInt((await env.RATE_LIMIT_KV.get(key)) || "0", 10) || 0;
  await env.RATE_LIMIT_KV.put(key, String(used + 1), { expirationTtl: 36 * 3600 });
}
