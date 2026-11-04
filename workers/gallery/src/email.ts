/**
 * The Nerra Daily email's preferences (Nov 1 2026).
 *
 * The network sends ONE email, Nerra Daily (engine/nerra_daily_email.py).
 * Buttondown renders it per subscriber from their TAGS: a show's newsletter
 * tag means "carry this show", `nerra-daily-weekly` means "Sundays only",
 * `personal-paid` hides the Personal pitch from a paying member. This module
 * is the only place the Worker changes those tags after signup:
 *
 *   - saving a lineup on My Nerra adds the new shows to the email and drops
 *     the ones the member removed from the lineup (a show followed from a
 *     show page and never in the lineup is left alone);
 *   - `POST /api/account/email` sets the email's shows and frequency
 *     directly (My Nerra's "Your Nerra Daily email" section);
 *   - Stripe activation and cancellation set and clear `personal-paid`.
 *
 * Every Buttondown call is best-effort: a failure is logged and the
 * caller's own result (a saved lineup, an activated membership) stands.
 * Buttondown's PATCH REPLACES the tag array, so every change reads the
 * subscriber first and writes the full new set.
 */

import type { Env } from "./types";

const BUTTONDOWN_BASE = "https://api.buttondown.email/v1";

export const MEMBER_TAG = "nerra-member";
export const PAID_TAG = "personal-paid";
export const WEEKLY_ONLY_TAG = "nerra-daily-weekly";

/** slug -> the show's newsletter tag, for every show a reader can follow in
 * the email: public English shows that are sections of Nerra Daily. MUST
 * mirror engine.nerra_daily_email.email_show_tags() (drift-guarded by
 * tests/test_nerra_daily_email_2026_11_01.py). The members-only desks are
 * not here: the email's archive copy is public. */
export const EMAIL_SHOW_TAGS: Record<string, string> = {
  spacex: "SpaceX Daily",
  tesla: "Tesla Shorts Time",
  planetterrian: "Planetterrian Daily",
  models_agents: "Models & Agents",
  fascinating_frontiers: "Fascinating Frontiers",
  omni_view_world: "Omni View Top World News",
  mag7: "MAG 7 Daily",
  modern_investing: "Modern Investing Techniques",
  longevity: "Longevity Weekly",
  peptides: "Peptides Weekly",
  offshore_north: "Offshore North",
  ai_chips: "AI Chips & Data Centres Daily",
  first_principles: "First Principles Daily",
  unintended_consequences: "Unintended Consequences",
  prediction_markets: "Prediction Markets Daily",
  models_agents_beginners: "Models & Agents for Beginners",
  collingwood: "Collingwood Weekly",
  env_intel: "Environmental Intelligence",
  dp_pod: "DP Pod",
  omni_view: "Omni View",
  vancouver: "Vancouver Daily News",
  age_of_ai: "The Age of AI",
  nerra_voices: "Nerra Voices",
};

const SHOW_TAG_SET = new Set(
  Object.values(EMAIL_SHOW_TAGS).map((t) => t.toLowerCase()),
);

export interface EmailChange {
  /** Shows (slugs) to carry from now on. `undefined` = leave as is. */
  shows?: string[];
  /** Slugs to add (lineup save). */
  addShows?: string[];
  /** Slugs to drop (lineup save: removed from the lineup). */
  dropShows?: string[];
  /** "daily" | "weekly". `undefined` = leave as is. */
  frequency?: "daily" | "weekly";
  /** Set or clear `personal-paid`. `undefined` = leave as is. */
  paid?: boolean;
}

/** The tag array after `change`, from the subscriber's current `existing`
 * tags. Pure (unit-tested): tags this module does not own are never
 * touched, and the result keeps the existing order with additions last. */
export function nextTags(existing: string[], change: EmailChange): string[] {
  const lower = (t: string) => t.toLowerCase();
  let tags = existing.filter((t) => typeof t === "string" && t);
  const tagFor = (slug: string) => EMAIL_SHOW_TAGS[slug];
  const add = (t: string) => {
    if (!tags.some((x) => lower(x) === lower(t))) tags.push(t);
  };
  const drop = (t: string) => {
    tags = tags.filter((x) => lower(x) !== lower(t));
  };
  if (change.shows !== undefined) {
    const want = new Set(
      change.shows.map(tagFor).filter((t): t is string => !!t).map(lower),
    );
    tags = tags.filter((t) => !SHOW_TAG_SET.has(lower(t)) || want.has(lower(t)));
    for (const slug of change.shows) {
      const t = tagFor(slug);
      if (t) add(t);
    }
  }
  for (const slug of change.dropShows ?? []) {
    const t = tagFor(slug);
    if (t) drop(t);
  }
  for (const slug of change.addShows ?? []) {
    const t = tagFor(slug);
    if (t) add(t);
  }
  if (change.frequency === "weekly") add(WEEKLY_ONLY_TAG);
  if (change.frequency === "daily") drop(WEEKLY_ONLY_TAG);
  if (change.paid === true) add(PAID_TAG);
  if (change.paid === false) drop(PAID_TAG);
  return tags;
}

/** What My Nerra shows: the email's shows and frequency, from the tags. */
export function emailStateFromTags(tags: string[], subscribed: boolean) {
  const have = new Set(tags.map((t) => t.toLowerCase()));
  const shows = Object.entries(EMAIL_SHOW_TAGS)
    .filter(([, tag]) => have.has(tag.toLowerCase()))
    .map(([slug]) => slug);
  return {
    subscribed,
    frequency: have.has(WEEKLY_ONLY_TAG) ? "weekly" : "daily",
    shows,
  };
}

interface Subscriber {
  id: string;
  tags: string[];
  type: string;
}

async function findSubscriber(apiKey: string, email: string): Promise<Subscriber | null> {
  const resp = await fetch(
    `${BUTTONDOWN_BASE}/subscribers?email=${encodeURIComponent(email)}`,
    { headers: { Authorization: `Token ${apiKey}`, Accept: "application/json" } },
  );
  if (!resp.ok) throw new Error(`BUTTONDOWN_HTTP_${resp.status}`);
  const body = (await resp.json()) as any;
  const want = email.toLowerCase();
  const row = (body?.results ?? []).find(
    (r: any) => typeof r?.email_address === "string" &&
      r.email_address.toLowerCase() === want,
  );
  if (!row || typeof row.id !== "string") return null;
  return {
    id: row.id,
    tags: Array.isArray(row.tags) ? row.tags.filter((t: unknown) => typeof t === "string") : [],
    type: String(row.type || row.subscriber_type || ""),
  };
}

/** Apply `change` to the subscriber's tags. Returns the new tags, or null
 * when the address is not on the list or Buttondown could not be reached. */
export async function applyEmailChange(
  env: Env,
  email: string,
  change: EmailChange,
): Promise<string[] | null> {
  const apiKey = env.BUTTONDOWN_API_KEY;
  if (!apiKey || !email) return null;
  try {
    const sub = await findSubscriber(apiKey, email);
    if (!sub) return null;
    const next = nextTags(sub.tags, change);
    const same = next.length === sub.tags.length &&
      next.every((t, i) => t === sub.tags[i]);
    if (same) return next;
    const patch = await fetch(`${BUTTONDOWN_BASE}/subscribers/${sub.id}`, {
      method: "PATCH",
      headers: {
        Authorization: `Token ${apiKey}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ tags: next }),
    });
    if (!patch.ok) {
      console.warn("email: tag update refused", patch.status);
      return null;
    }
    return next;
  } catch (e) {
    console.warn("email: tag update skipped:", (e as Error).message);
    return null;
  }
}

/** The email state for My Nerra, or null when Buttondown cannot be read. */
export async function readEmailState(env: Env, email: string) {
  const apiKey = env.BUTTONDOWN_API_KEY;
  if (!apiKey || !email) return null;
  try {
    const sub = await findSubscriber(apiKey, email);
    if (!sub) return emailStateFromTags([], false);
    const subscribed = !sub.type || sub.type === "regular" || sub.type === "premium";
    return emailStateFromTags(sub.tags, subscribed);
  } catch (e) {
    console.warn("email: state read skipped:", (e as Error).message);
    return null;
  }
}
