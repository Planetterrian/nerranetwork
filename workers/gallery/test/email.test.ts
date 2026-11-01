/**
 * The Nerra Daily email's preferences (Nov 1 2026): the tags that decide
 * what the one network email carries for each subscriber.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  EMAIL_SHOW_TAGS,
  PAID_TAG,
  WEEKLY_ONLY_TAG,
  emailStateFromTags,
  nextTags,
} from "../src/email";
import { handleEmailPrefs, handlePreferences } from "../src/personal";
import { signJwt } from "../src/jwt";
import type { Env } from "../src/types";

class FakeKV {
  store = new Map<string, string>();
  async get(key: string) { return this.store.get(key) ?? null; }
  async put(key: string, value: string) { this.store.set(key, value); }
  async delete(key: string) { this.store.delete(key); }
}

function envWith(overrides: Record<string, unknown> = {}): Env {
  return {
    JWT_SECRET: "test-secret-test-secret-test-secret!",
    BUTTONDOWN_API_KEY: "bd-key",
    RATE_LIMIT_KV: new FakeKV() as unknown as KVNamespace,
    ...overrides,
  } as unknown as Env;
}

async function cookie(env: Env, email: string, verified = true) {
  const token = await signJwt(
    { sub: email, scope: "gallery-subscriber", ...(verified ? { v: 1 } : {}), ttlSeconds: 3600 },
    env.JWT_SECRET,
  );
  return `nn_gallery=${encodeURIComponent(token)}`;
}

/** A fake Buttondown holding one subscriber; records every PATCH. */
function fakeButtondown(tags: string[], type = "regular") {
  const state = { tags: [...tags], patches: [] as string[][] };
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (!init || !init.method || init.method === "GET") {
      return new Response(JSON.stringify({ results: [
        { id: "sub_1", email_address: "fan@example.com", tags: state.tags, type },
      ] }), { status: 200 });
    }
    if (init.method === "PATCH") {
      const body = JSON.parse(String(init.body));
      state.tags = body.tags;
      state.patches.push(body.tags);
      return new Response("{}", { status: 200 });
    }
    return new Response("{}", { status: 404 });
  }));
  return state;
}

afterEach(() => vi.unstubAllGlobals());

describe("nextTags", () => {
  it("sets the email's shows exactly and never touches other tags", () => {
    const out = nextTags(
      ["nerra-member", "Tesla Shorts Time", "src-youtube", "Privet Russian"],
      { shows: ["spacex", "omni_view_europe", "nope"] },
    );
    expect(out).toEqual(["nerra-member", "src-youtube", "Privet Russian", "SpaceX Daily"]);
  });

  it("a lineup save adds its shows and drops only what left the lineup", () => {
    const out = nextTags(
      ["gallery-subscriber", "Models & Agents", "Tesla Shorts Time"],
      { addShows: ["spacex", "tesla"], dropShows: ["models_agents"] },
    );
    expect(out).toEqual(["gallery-subscriber", "Tesla Shorts Time", "SpaceX Daily"]);
  });

  it("frequency and paid status are single tags", () => {
    let tags = nextTags(["nerra-member"], { frequency: "weekly", paid: true });
    expect(tags).toEqual(["nerra-member", WEEKLY_ONLY_TAG, PAID_TAG]);
    tags = nextTags(tags, { frequency: "daily", paid: false });
    expect(tags).toEqual(["nerra-member"]);
  });

  it("the members-only desks and the Russian shows are not email shows", () => {
    expect(EMAIL_SHOW_TAGS.omni_view_europe).toBeUndefined();
    expect(EMAIL_SHOW_TAGS.finansy_prosto).toBeUndefined();
    expect(EMAIL_SHOW_TAGS.privet_russian).toBeUndefined();
  });

  it("reads the state back from tags", () => {
    expect(emailStateFromTags(["SpaceX Daily", WEEKLY_ONLY_TAG], true))
      .toEqual({ subscribed: true, frequency: "weekly", shows: ["spacex"] });
  });
});

describe("GET/POST /api/account/email", () => {
  it("needs a verified session", async () => {
    const env = envWith();
    const res = await handleEmailPrefs(new Request("https://api.example.com/api/account/email", {
      headers: { Cookie: await cookie(env, "fan@example.com", false) },
    }), env);
    expect(res.status).toBe(403);
  });

  it("reads and writes the email's shows and frequency", async () => {
    const env = envWith();
    const bd = fakeButtondown(["nerra-member", "Tesla Shorts Time"]);
    const got = await (await handleEmailPrefs(new Request("https://api.example.com/api/account/email", {
      headers: { Cookie: await cookie(env, "fan@example.com") },
    }), env)).json() as any;
    expect(got.email).toEqual({ subscribed: true, frequency: "daily", shows: ["tesla"] });

    const res = await handleEmailPrefs(new Request("https://api.example.com/api/account/email", {
      method: "POST",
      headers: { Cookie: await cookie(env, "fan@example.com"), "Content-Type": "application/json" },
      body: JSON.stringify({ shows: ["spacex", "mag7"], frequency: "weekly" }),
    }), env);
    expect(res.status).toBe(200);
    expect(bd.tags).toEqual(["nerra-member", "SpaceX Daily", "MAG 7 Daily", WEEKLY_ONLY_TAG]);
  });
});

describe("a lineup save moves the email with it", () => {
  it("adds the lineup's shows and drops the one taken out", async () => {
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    kv.store.set("member:fan@example.com", JSON.stringify({
      shows: ["tesla", "models_agents"], first_name: "", city: "", tier: "none",
      status: "none", updated_at: "",
    }));
    const bd = fakeButtondown(["nerra-member", "Tesla Shorts Time", "Models & Agents", "Omni View"]);
    const res = await handlePreferences(new Request("https://api.example.com/api/account/preferences", {
      method: "POST",
      headers: { Cookie: await cookie(env, "fan@example.com"), "Content-Type": "application/json" },
      body: JSON.stringify({ shows: ["tesla", "spacex"] }),
    }), env);
    expect(res.status).toBe(200);
    // Omni View was followed from a show page, never in the lineup: kept.
    expect(bd.tags).toEqual(["nerra-member", "Tesla Shorts Time", "Omni View", "SpaceX Daily"]);
  });
});
