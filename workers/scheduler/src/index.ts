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

// [utcHour, utcMinute, show, dayFilter]
const SLOTS: Array<[number, number, string, string | null]> = [
  [6, 7,  "privet_russian",          "monday"],
  [6, 37, "omni_view",                null],
  [7, 7,  "planetterrian",            null],
  [7, 37, "fascinating_frontiers",    null],
  [8, 7,  "env_intel",               "monday"],
  [8, 37, "models_agents",            null],
  [9, 7,  "models_agents_beginners",  null],
  [9, 37, "finansy_prosto",          "monday"],
  [10, 7, "modern_investing",         null],
  [10, 37, "first_principles",        null],
  [11, 7, "tesla",                    null],
  [11, 37, "unintended_consequences", null],
  [12, 7, "spacex",                   null],
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

async function dispatch(env: Env, show: string): Promise<void> {
  const res = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "nerra-scheduler",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main", inputs: { show } }),
    },
  );
  if (res.status !== 204) {
    const body = await res.text();
    throw new Error(`workflow_dispatch for ${show} failed: ${res.status} ${body}`);
  }
  console.log(`Dispatched ${show}`);
}

export default {
  async scheduled(controller: ScheduledController, env: Env): Promise<void> {
    const now = new Date(controller.scheduledTime);
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
