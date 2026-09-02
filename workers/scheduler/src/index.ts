/**
 * Exact-time dispatcher for the Run Podcast Show workflow.
 *
 * Mirrors the CRON_MAP in .github/workflows/run-show.yml — keep the two
 * in sync (drift guard: tests/test_scheduling_punctuality.py parses both).
 * dayFilter semantics match the gate: "even"/"odd" = UTC day of month
 * parity, "weekday" = Mon-Fri, "odd_weekday" = both.
 */

interface Env {
  GITHUB_DISPATCH_TOKEN: string;
}

const REPO = "Planetterrian/nerranetwork";
const WORKFLOW = "run-show.yml";

// Nerra Daily edition force-dispatch (Aug 2026, "land by 6am Pacific"):
// the edition's when-ready gate stops waiting for stragglers at
// FORCE_BUILD_UTC_HOUR (12:00 UTC, scripts/build_daily_edition.py), but
// its GitHub sweep crons are as late as any other — on 2026-08-24/25 the
// 14:23 sweep ran 15:07/15:13 and the edition landed ~8am PT. This slot
// fires nerra-daily.yml at 12:07 UTC sharp (a minute the wrangler cron
// already covers), so a straggler day still assembles by ~12:40 UTC =
// 5:40am PDT / 4:40am PST. Deliberately an OBJECT, not a SLOTS row —
// tests/test_scheduling_punctuality.py parses SLOTS rows as shows.
const EDITION_DISPATCH = { hour: 12, minute: 7, workflow: "nerra-daily.yml" };

// [utcHour, utcMinute, show, dayFilter]
const SLOTS: Array<[number, number, string, string | null]> = [
  [6, 7,  "privet_russian",          "monday"],
  [7, 1,  "omni_view",                null],
  [7, 16, "planetterrian",            null],
  [7, 31, "fascinating_frontiers",    null],
  [7, 46, "models_agents",            null],
  [8, 7,  "env_intel",               "monday"],
  [8, 1,  "models_agents_beginners",  null],
  [8, 16, "modern_investing",         null],
  [8, 31, "first_principles",         null],
  [8, 46, "tesla",                    null],
  [9, 1,  "unintended_consequences",  null],
  [9, 16, "spacex",                   null],
  [9, 37, "finansy_prosto",          "monday"],
  [9, 46, "dp_pod",                   null],
  [10, 1, "offshore_north",          "monday"],
];

function dayFilterPasses(filter: string | null, now: Date): boolean {
  const day = now.getUTCDate();
  const weekday = now.getUTCDay(); // 0=Sun .. 6=Sat
  const isWeekday = weekday >= 1 && weekday <= 5;
  switch (filter) {
    case "even":
      return day % 2 === 0;
    case "odd":
      return day % 2 === 1;
    case "weekday":
      return isWeekday;
    case "odd_weekday":
      return day % 2 === 1 && isWeekday;
    case "monday":
      return weekday === 1;
    default:
      return true;
  }
}

/** Secrets pasted into `wrangler secret put` routinely carry a trailing
 *  newline; GitHub then answers 401 to `Bearer <token>\n` and the Worker
 *  looks deployed-but-dead (Aug 2026 outage debugging). Trim defensively. */
function token(env: Env): string {
  return (env.GITHUB_DISPATCH_TOKEN || "").trim();
}

function ghHeaders(env: Env): Record<string, string> {
  return {
    Authorization: `Bearer ${token(env)}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "nerra-scheduler",
  };
}

async function dispatchWorkflow(
  env: Env,
  workflow: string,
  inputs: Record<string, string>,
  label: string,
): Promise<void> {
  // One retry on transient GitHub trouble (5xx / 429 / network). A 4xx is
  // configuration (token scope, workflow name) and retrying cannot help.
  let lastErr = "";
  for (let attempt = 1; attempt <= 2; attempt++) {
    let res: Response;
    try {
      res = await fetch(
        `https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`,
        {
          method: "POST",
          headers: { ...ghHeaders(env), "Content-Type": "application/json" },
          body: JSON.stringify({ ref: "main", inputs }),
        },
      );
    } catch (e) {
      lastErr = `network: ${(e as Error).message}`;
      await new Promise((r) => setTimeout(r, 15_000));
      continue;
    }
    if (res.status === 204) {
      console.log(`Dispatched ${label} (attempt ${attempt})`);
      return;
    }
    const body = await res.text();
    lastErr = `${res.status} ${body.slice(0, 300)}`;
    if (res.status < 500 && res.status !== 429) break;
    await new Promise((r) => setTimeout(r, 15_000));
  }
  throw new Error(`workflow_dispatch for ${label} failed: ${lastErr}`);
}

async function dispatch(env: Env, show: string): Promise<void> {
  await dispatchWorkflow(env, WORKFLOW, { show }, show);
}

function nextSlot(now: Date): { show: string; at: string; filter: string | null } | null {
  // Walk forward minute-by-minute (bounded to 7 days) to the next SLOT
  // whose day filter passes — what the operator should expect to see fire.
  const t = new Date(now.getTime());
  t.setUTCSeconds(0, 0);
  for (let i = 0; i < 7 * 24 * 60; i++) {
    t.setUTCMinutes(t.getUTCMinutes() + 1);
    const slot = SLOTS.find(([h, m]) => h === t.getUTCHours() && m === t.getUTCMinutes());
    if (slot && dayFilterPasses(slot[3], t)) {
      return { show: slot[2], at: t.toISOString(), filter: slot[3] };
    }
  }
  return null;
}

/** Read-only self-test: does the stored token authenticate, and does it
 *  carry the ONE permission workflow_dispatch needs (Actions: write)?
 *  GET on the workflow needs actions:read, which a write grant includes;
 *  401 = bad/whitespace token, 403/404 = token lacks the Actions
 *  permission on this repo (a Contents-only PAT — the voices Worker's
 *  scope — lands here). Nothing is dispatched. */
async function githubSelfTest(env: Env): Promise<Record<string, unknown>> {
  const tok = token(env);
  const raw = env.GITHUB_DISPATCH_TOKEN || "";
  const out: Record<string, unknown> = {
    token_present: tok.length > 0,
    token_had_whitespace: raw !== tok,
    token_prefix_ok: tok.startsWith("github_pat_") || tok.startsWith("ghp_"),
  };
  if (!tok) return { ...out, github: "no token" };
  try {
    const res = await fetch(
      `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}`,
      { headers: ghHeaders(env) },
    );
    out.github_status = res.status;
    out.github_ok = res.status === 200;
    out.github_hint =
      res.status === 200 ? "token authenticates and can see the workflow (Actions permission present)"
      : res.status === 401 ? "401: token rejected — re-run `wrangler secret put GITHUB_DISPATCH_TOKEN` (check for a pasted newline / expired PAT)"
      : res.status === 403 || res.status === 404 ? `${res.status}: token lacks Actions (read/write) on ${REPO} — workflow_dispatch needs Actions: Read and write`
      : `unexpected ${res.status}`;
    out.rate_limit_remaining = res.headers.get("x-ratelimit-remaining");
  } catch (e) {
    out.github_error = (e as Error).message;
  }
  return out;
}

export default {
  /** GET /  → config + next slot.  GET /health → the above plus a live
   *  read-only GitHub auth probe. Both unauthenticated on purpose: they
   *  reveal nothing secret and exist so a deploy can be verified from a
   *  browser instead of by waiting for a slot and checking Actions. */
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    const now = new Date();
    const base = {
      worker: "nerra-scheduler",
      now: now.toISOString(),
      cron: "1,7,16,31,37,46 6-12 * * * (UTC)",
      next_slot: nextSlot(now),
      edition_dispatch: EDITION_DISPATCH,
      slots: SLOTS.map(([h, m, show, f]) => ({
        at: `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}Z`, show, filter: f,
      })),
    };
    if (url.pathname === "/health") {
      const self = await githubSelfTest(env);
      return Response.json({ ...base, ...self, ok: self.github_ok === true }, {
        status: self.github_ok === true ? 200 : 503,
        headers: { "Cache-Control": "no-store" },
      });
    }
    return Response.json(base, { headers: { "Cache-Control": "no-store" } });
  },

  async scheduled(controller: ScheduledController, env: Env): Promise<void> {
    const now = new Date(controller.scheduledTime);
    if (
      now.getUTCHours() === EDITION_DISPATCH.hour &&
      now.getUTCMinutes() === EDITION_DISPATCH.minute
    ) {
      // The edition workflow's own gate decides whether there is anything
      // to build (already-published days no-op on the fast gate).
      await dispatchWorkflow(env, EDITION_DISPATCH.workflow, {}, "nerra-daily");
      return;
    }
    const slot = SLOTS.find(
      ([h, m]) => h === now.getUTCHours() && m === now.getUTCMinutes(),
    );
    if (!slot) {
      console.log(`No slot for ${now.toISOString()} — nothing to dispatch.`);
      return;
    }
    const [, , show, filter] = slot;
    if (!dayFilterPasses(filter, now)) {
      console.log(`${show}: day filter '${filter}' not satisfied today — no-op.`);
      return;
    }
    await dispatch(env, show);
  },
};
