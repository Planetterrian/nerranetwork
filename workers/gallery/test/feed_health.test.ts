/**
 * Private feed freshness (Nov 6 2026). Every batch run from Nov 2 to Nov 6
 * failed on a 401 and no member's feed moved for five days while every
 * public check stayed green. The daily audit now reads these counts.
 */

import { describe, expect, it } from "vitest";
import { summariseFeedFreshness, todayIso } from "../src/build";
import { handleFeedHealth } from "../src/personal";
import type { Env } from "../src/types";

class FakeKV {
  store = new Map<string, string>();
  async get(key: string) { return this.store.get(key) ?? null; }
  async put(key: string, value: string) { this.store.set(key, value); }
  async delete(key: string) { this.store.delete(key); }
  async list(opts: { prefix: string; cursor?: string }) {
    const keys = [...this.store.keys()]
      .filter((k) => k.startsWith(opts.prefix))
      .map((name) => ({ name }));
    return { keys, list_complete: true, cursor: undefined };
  }
}

class FakeBucket {
  objects = new Map<string, string>();
  async get(key: string) {
    const body = this.objects.get(key);
    if (body === undefined) return null;
    return { body, text: async () => body };
  }
}

const NOW = new Date("2026-11-06T18:00:00Z");  // 13:00 Eastern

function seeded() {
  const kv = new FakeKV();
  const bucket = new FakeBucket();
  const member = (email: string, token: string, status = "active") =>
    kv.store.set(`member:${email}`, JSON.stringify({
      shows: ["tesla", "spacex"], first_name: "Ann", city: "Vancouver",
      tier: "personal", status, feed_token: token, updated_at: "",
    }));
  member("a@example.com", "a".repeat(32));
  member("b@example.com", "b".repeat(32));
  member("c@example.com", "c".repeat(32));
  member("d@example.com", "d".repeat(32), "canceled");
  bucket.objects.set(`personal/${"a".repeat(32)}/episodes.json`, JSON.stringify({
    episodes: [{ date: "2026-11-05" }, { date: "2026-11-06" }],
  }));
  bucket.objects.set(`personal/${"b".repeat(32)}/episodes.json`, JSON.stringify({
    episodes: [{ date: "2026-10-31" }, { date: "2026-11-01" }],
  }));
  // c: never built.
  const env = {
    RATE_LIMIT_KV: kv, PERSONAL_BUCKET: bucket,
    PERSONAL_ADMIN_TOKEN: "admin-token", PERSONAL_DEMAND_TOKEN: "demand-token",
  } as unknown as Env;
  return env;
}

const req = (auth?: string) => new Request(
  "https://api.example.com/api/admin/personal-feed-health",
  auth ? { headers: { Authorization: auth } } : {});

describe("summariseFeedFreshness", () => {
  it("counts fresh, behind and never-built feeds and the worst lag", () => {
    const s = summariseFeedFreshness(["2026-11-06", "2026-11-01", null], "2026-11-06");
    expect(s).toEqual({
      today: "2026-11-06", members: 3, built_today: 1, behind: 1,
      never_built: 1, newest_edition: "2026-11-06",
      oldest_latest_edition: "2026-11-01", max_days_behind: 5,
    });
  });

  it("no members is not a failure and not a zero lag", () => {
    const s = summariseFeedFreshness([], "2026-11-06");
    expect(s.members).toBe(0);
    expect(s.max_days_behind).toBeNull();
    expect(s.newest_edition).toBeNull();
  });
});

describe("GET /api/admin/personal-feed-health", () => {
  it("reads every active member's private feed, as counts", async () => {
    const res = await handleFeedHealth(req("Bearer demand-token"), seeded(), NOW);
    expect(res.status).toBe(200);
    const body = await res.json() as Record<string, unknown>;
    expect(body.today).toBe(todayIso(NOW));
    expect(body.members).toBe(3);  // the cancelled member is not counted
    expect(body.built_today).toBe(1);
    expect(body.behind).toBe(1);
    expect(body.never_built).toBe(1);
    expect(body.max_days_behind).toBe(5);
  });

  it("is bearer-gated and never carries a name, city, email or token", async () => {
    const env = seeded();
    expect((await handleFeedHealth(req(), env, NOW)).status).toBe(401);
    expect((await handleFeedHealth(req("Bearer wrong"), env, NOW)).status).toBe(401);
    const res = await handleFeedHealth(req("Bearer admin-token"), env, NOW);
    expect(res.status).toBe(200);
    const text = await res.text();
    for (const leak of ["Ann", "Vancouver", "example.com", "a".repeat(32), "aaaaaaaa"]) {
      expect(text).not.toContain(leak);
    }
  });
});
