/**
 * Exact-time dispatcher for the Run Podcast Show workflow.
 *
 * Oct 17 2026 (operator-directed): the schedule is anchored to EASTERN wall
 * time so Nerra Daily is live by 7:00 AM New York and the 1 November clock
 * change does not move a single slot. SLOTS rows are [etHour, etMinute,
 * show, dayFilter] on SLOT_TZ; the handler converts each firing to that
 * clock and matches on it, and the day filters read the Eastern date and
 * weekday. Every slot sits between 04:00 and 08:15 ET (08:00-13:15 UTC), so
 * the Eastern and UTC calendar days always agree.
 *
 * Mirrors the CRON_MAP in .github/workflows/run-show.yml, whose GitHub
 * fallback crons are UTC and cannot follow daylight saving: each is the
 * slot's EST equivalent (ET + 5 h), so in summer the fallback fires an hour
 * after the Worker and the gate's duplicate guard drops it. Drift guard:
 * tests/test_scheduling_punctuality.py compares the two at the EST offset.
 * dayFilter semantics match the gate: "even"/"odd" = day-of-month parity,
 * "weekday" = Mon-Fri, "odd_weekday" = both, a weekday name = that day.
 */

interface Env {
  GITHUB_DISPATCH_TOKEN: string;
}

const REPO = "Planetterrian/nerranetwork";
const WORKFLOW = "run-show.yml";

/** The one wall clock every SLOTS row, the edition and the X queue read. */
const SLOT_TZ = "America/New_York";

// Nerra Daily edition dispatch, on EASTERN wall time (Oct 17 2026,
// operator-directed: the edition is out by 7:00 AM New York). 06:35 opens
// the release — the last edition show (Top World) starts at 06:10 and a
// build takes 6-7 minutes — and 06:50 is the end of the straggler hold,
// past which the gate builds with whatever landed
// (engine/daily_edition.py RELEASE_EASTERN / HOLD_UNTIL_EASTERN). A
// straggler that lands inside the hold triggers the build itself
// (nerra-daily.yml's workflow_run). Deliberately an OBJECT, not a SLOTS row
// — tests/test_scheduling_punctuality.py parses SLOTS rows as shows.
const EDITION_DISPATCH = {
  tz: "America/New_York",
  times: [[6, 35], [6, 50]] as Array<[number, number]>,
  workflow: "nerra-daily.yml",
};

// Daytime X posting for @nerranetwork (Oct 11 2026; Eastern since Oct 17).
// Shows queue their post into a half-hour slot between 7:00 AM and
// 10:00 PM Eastern (engine/x_queue.py); x-queue.yml posts whatever is due.
// Dispatched at :05 and :35 Eastern from 7:05 AM to 10:05 PM, five minutes
// after each slot. Deliberately an OBJECT, not a SLOTS row (those parse as
// shows).
const X_QUEUE_DISPATCH = {
  workflow: "x-queue.yml",
  tz: "America/New_York",
  first: [7, 5] as [number, number],
  last: [22, 5] as [number, number],
  minutes: [5, 35],
};

function xQueueDue(eh: number, em: number): boolean {
  if (!X_QUEUE_DISPATCH.minutes.includes(em)) return false;
  const at = eh * 60 + em;
  const [fh, fm] = X_QUEUE_DISPATCH.first;
  const [lh, lm] = X_QUEUE_DISPATCH.last;
  return at >= fh * 60 + fm && at <= lh * 60 + lm;
}

interface WallClock {
  date: string; // YYYY-MM-DD on the zone's calendar
  day: number; // day of month
  weekday: number; // 0=Sun .. 6=Sat
  hour: number;
  minute: number;
}

const WEEKDAY_INDEX: Record<string, number> = {
  Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6,
};
const FORMATTERS: Record<string, Intl.DateTimeFormat> = {};

/** *d* on *tz*'s wall clock (date, weekday, hour, minute). The same
 *  Intl.DateTimeFormat approach the Pacific edition clock used. */
function wallClock(d: Date, tz: string = SLOT_TZ): WallClock {
  const fmt = FORMATTERS[tz] ??= new Intl.DateTimeFormat("en-US", {
    timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit",
    weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
  const parts = fmt.formatToParts(d);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return {
    date: `${get("year")}-${get("month")}-${get("day")}`,
    day: Number(get("day")),
    weekday: WEEKDAY_INDEX[get("weekday")] ?? -1,
    hour: Number(get("hour")),
    minute: Number(get("minute")),
  };
}

// [etHour, etMinute, show, dayFilter] — Eastern wall time (SLOT_TZ).
// Oct 17 2026 timetable: the shows run as late as possible for freshness and
// every Nerra Daily show starts by 06:10 ET (its audio lands ~15-20 minutes
// later, before the 06:35 release). Minutes are unique: the handler takes
// the FIRST row matching h:m.
const SLOTS: Array<[number, number, string, string | null]> = [
  [4, 0,  "unintended_consequences",  null],
  [4, 5,  "first_principles",         null],
  [4, 10, "privet_russian",          "monday"],
  [4, 15, "env_intel",               "monday"],
  [4, 20, "finansy_prosto",          "monday"],
  [4, 25, "dp_pod",                  "monday"],
  [4, 30, "omni_view_asia_pacific",   null],
  [4, 35, "offshore_north",          "monday"],
  [4, 40, "omni_view_africa_mideast", null],
  [4, 45, "longevity",               "wednesday"],
  [4, 50, "omni_view_europe",         null],
  [4, 55, "peptides",                "thursday"],
  [5, 0,  "planetterrian",            null],
  [5, 5,  "omni_view_latam",          null],
  [5, 10, "fascinating_frontiers",    null],
  [5, 15, "omni_view_north_america",  null],
  [5, 20, "ai_chips",                 null],
  [5, 25, "models_agents",            null],
  [5, 30, "models_agents_beginners",  null],
  [5, 35, "collingwood",             "friday"],
  [5, 40, "omni_view",                null],
  [5, 45, "spacex",                   null],
  [5, 50, "tesla",                    null],
  [5, 55, "mag7",                     null],
  [6, 0,  "modern_investing",         null],
  [6, 5,  "prediction_markets",       null],
  // After every desk's 50-minute budget: its intake reads their digests.
  [6, 10, "omni_view_world",          null],
  // Local Pacific morning slot (05:15 PT — ET minus PT is three hours all
  // year); NOT in the 7 AM edition.
  [8, 15, "vancouver",                null],
];

// First scheduled run per show (Sep 2026 launch) — mirrors run-show.yml's
// FIRST_SCHEDULED_RUN and review_episodes' "first_run". A weekly whose
// Episode 1 was produced by hand mid-week must not run the next day.
const FIRST_RUN: Record<string, string> = {
  longevity: "2026-09-30",
  peptides: "2026-10-01",
  collingwood: "2026-10-02",
};

function launched(show: string, clock: WallClock): boolean {
  const first = FIRST_RUN[show];
  return !first || clock.date >= first;
}

function dayFilterPasses(filter: string | null, clock: WallClock): boolean {
  const day = clock.day;
  const weekday = clock.weekday; // 0=Sun .. 6=Sat, Eastern calendar
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
    // Named weekdays for weekly shows (Sep 2026). 0=Sun .. 6=Sat.
    case "tuesday":
      return weekday === 2;
    case "wednesday":
      return weekday === 3;
    case "thursday":
      return weekday === 4;
    case "friday":
      return weekday === 5;
    case "saturday":
      return weekday === 6;
    case "sunday":
      return weekday === 0;
    default:
      return true;
  }
}

function hhmm(h: number, m: number): string {
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
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

function nextSlot(now: Date): { show: string; at: string; et: string; filter: string | null } | null {
  // Walk forward minute-by-minute (bounded to 7 days) to the next SLOT
  // whose day filter passes — what the operator should expect to see fire.
  const t = new Date(now.getTime());
  t.setUTCSeconds(0, 0);
  for (let i = 0; i < 7 * 24 * 60; i++) {
    t.setUTCMinutes(t.getUTCMinutes() + 1);
    const clock = wallClock(t);
    const slot = SLOTS.find(([h, m]) => h === clock.hour && m === clock.minute);
    if (slot && dayFilterPasses(slot[3], clock) && launched(slot[2], clock)) {
      return {
        show: slot[2], at: t.toISOString(),
        et: `${clock.date} ${hhmm(clock.hour, clock.minute)}`, filter: slot[3],
      };
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
      cron: "*/5 * * * * (UTC)",
      slot_tz: SLOT_TZ,
      next_slot: nextSlot(now),
      edition_dispatch: EDITION_DISPATCH,
      x_queue_dispatch: X_QUEUE_DISPATCH,
      // Eastern wall time, e.g. {"at": "05:45", "tz": "America/New_York"} —
      // engine/scheduler_slots.slots_from_status parses exactly this.
      slots: SLOTS.map(([h, m, show, f]) => ({
        at: hhmm(h, m), tz: SLOT_TZ, show, filter: f,
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
    const clock = wallClock(now);
    // The X queue, the edition and the show slots are independent: one
    // failing (or sharing a minute) never skips another.
    if (xQueueDue(clock.hour, clock.minute)) {
      try {
        await dispatchWorkflow(env, X_QUEUE_DISPATCH.workflow, {}, "x-queue");
      } catch (e) {
        console.log(`x-queue dispatch failed: ${(e as Error).message}`);
      }
    }
    if (EDITION_DISPATCH.times.some(([h, m]) => h === clock.hour && m === clock.minute)) {
      // The edition workflow's own gate decides whether there is anything
      // to build (already-published days no-op on the fast gate).
      try {
        await dispatchWorkflow(env, EDITION_DISPATCH.workflow, {}, "nerra-daily");
      } catch (e) {
        console.log(`nerra-daily dispatch failed: ${(e as Error).message}`);
      }
    }
    const slot = SLOTS.find(([h, m]) => h === clock.hour && m === clock.minute);
    if (!slot) {
      console.log(`No slot for ${clock.date} ${hhmm(clock.hour, clock.minute)} ET — nothing to dispatch.`);
      return;
    }
    const [, , show, filter] = slot;
    if (!dayFilterPasses(filter, clock)) {
      console.log(`${show}: day filter '${filter}' not satisfied today — no-op.`);
      return;
    }
    // Sep 24 2026: the status page's nextSlot() honoured FIRST_RUN and the
    // dispatcher did not — Peptides Ep2 fired 09-24, a week before its
    // 10-01 launch date, and a workflow_dispatch bypasses the workflow's
    // own FIRST_SCHEDULED_RUN gate by design (manual reruns stay possible).
    // The Worker owns "when"; the launch date is part of when.
    if (!launched(show, clock)) {
      console.log(`${show}: first scheduled run is ${FIRST_RUN[show]} — not launched yet, no-op.`);
      return;
    }
    await dispatch(env, show);
  },
};
