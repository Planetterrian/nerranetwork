/**
 * Nerra Personal endpoint tests — Stripe signature verification, the
 * closed show vocabulary, feed-token gating, and the PII-light admin
 * spec export.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_LINEUP,
  PERSONAL_ADDONS,
  PERSONAL_SHOWS,
  handleAccount,
  handleAdminSpecs,
  handleBookDownload,
  handleCheckoutRef,
  handlePersonalFeed,
  handlePortal,
  handlePreferences,
  handleRebuild,
  handleStripeWebhook,
  verifyStripeSignature,
} from "../src/personal";
import { REBUILDS_PER_DAY, todayIso } from "../src/build";
import { resolveSubscribeTags } from "../src/handlers";
import { signJwt } from "../src/jwt";
import type { Env } from "../src/types";

// ---------------------------------------------------------------------------
// Fakes
// ---------------------------------------------------------------------------

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
    return {
      body,
      httpEtag: "etag",
      writeHttpMetadata: (_h: Headers) => {},
    };
  }
}

function envWith(overrides: Partial<Record<string, unknown>> = {}): Env {
  return {
    GALLERY_BUCKET: new FakeBucket() as unknown as R2Bucket,
    JWT_SECRET: "test-secret-test-secret-test-secret!",
    BUTTONDOWN_API_KEY: "x",
    RESEND_API_KEY: "x",
    RESEND_FROM_EMAIL: "x@example.com",
    RATE_LIMIT_KV: new FakeKV() as unknown as KVNamespace,
    PERSONAL_BUCKET: new FakeBucket() as unknown as R2Bucket,
    STRIPE_WEBHOOK_SECRET: "whsec_test",
    PERSONAL_ADMIN_TOKEN: "admin-token",
    ...overrides,
  } as unknown as Env;
}

async function stripeSig(payload: string, secret: string, t: number) {
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const mac = await crypto.subtle.sign(
    "HMAC", key, new TextEncoder().encode(`${t}.${payload}`),
  );
  const hex = [...new Uint8Array(mac)]
    .map((b) => b.toString(16).padStart(2, "0")).join("");
  return `t=${t},v1=${hex}`;
}

// ---------------------------------------------------------------------------

describe("verifyStripeSignature", () => {
  it("accepts a valid signature inside tolerance", async () => {
    const now = 1_700_000_000;
    const sig = await stripeSig("payload", "whsec_test", now);
    expect(await verifyStripeSignature("payload", sig, "whsec_test", now))
      .toBe(true);
  });

  it("rejects a stale timestamp", async () => {
    const now = 1_700_000_000;
    const sig = await stripeSig("payload", "whsec_test", now - 3600);
    expect(await verifyStripeSignature("payload", sig, "whsec_test", now))
      .toBe(false);
  });

  it("rejects a wrong secret", async () => {
    const now = 1_700_000_000;
    const sig = await stripeSig("payload", "other", now);
    expect(await verifyStripeSignature("payload", sig, "whsec_test", now))
      .toBe(false);
  });
});

describe("stripe webhook lifecycle", () => {
  async function post(env: Env, event: object) {
    const payload = JSON.stringify(event);
    const sig = await stripeSig(
      payload, "whsec_test", Math.floor(Date.now() / 1000));
    return handleStripeWebhook(
      new Request("https://api.example.com/api/stripe/webhook", {
        method: "POST",
        body: payload,
        headers: { "Stripe-Signature": sig },
      }),
      env,
    );
  }

  it("activates a member and mints a feed token on checkout", async () => {
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    const res = await post(env, {
      type: "checkout.session.completed",
      data: { object: {
        customer_details: { email: "Fan@Example.com" },
        metadata: { tier: "personal_local" },
        subscription: "sub_123",
        amount_total: 899,
      } },
    });
    expect(res.status).toBe(200);
    const rec = JSON.parse(kv.store.get("member:fan@example.com")!);
    expect(rec.status).toBe("active");
    expect(rec.tier).toBe("personal_local");
    expect(rec.feed_token).toMatch(/^[a-f0-9]{32}$/);
    expect(kv.store.get(`feedtok:${rec.feed_token}`)).toBe("fan@example.com");
    expect(kv.store.get("sub:sub_123")).toBe("fan@example.com");
  });

  it("cancellation revokes the feed token immediately", async () => {
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    await post(env, {
      type: "checkout.session.completed",
      data: { object: {
        customer_email: "fan@example.com",
        metadata: { tier: "personal" },
        subscription: "sub_9",
        amount_total: 499,
      } },
    });
    const rec = JSON.parse(kv.store.get("member:fan@example.com")!);
    await post(env, {
      type: "customer.subscription.deleted",
      data: { object: { id: "sub_9" } },
    });
    expect(kv.store.has(`feedtok:${rec.feed_token}`)).toBe(false);
    const after = JSON.parse(kv.store.get("member:fan@example.com")!);
    expect(after.status).toBe("cancelled");
  });

  it("ignores a donation checkout instead of minting a feed", async () => {
    // /support.html donations hit the SAME endpoint as memberships. A $10
    // gift used to clear the old amount>=799 fallback and hand the donor a
    // paid feed. The tier marker is what separates the two.
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    const res = await post(env, {
      type: "checkout.session.completed",
      data: { object: {
        customer_details: { email: "donor@example.com" },
        metadata: { kind: "donation", interval: "once" },
        amount_total: 1000,
      } },
    });
    expect(res.status).toBe(200);
    expect(kv.store.has("member:donor@example.com")).toBe(false);
    expect([...kv.store.keys()].some((k) => k.startsWith("feedtok:")))
      .toBe(false);
  });

  it("ignores an untagged checkout however large the amount", async () => {
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    const res = await post(env, {
      type: "checkout.session.completed",
      data: { object: {
        customer_details: { email: "stranger@example.com" },
        amount_total: 99999,
      } },
    });
    expect(res.status).toBe(200);
    expect(kv.store.has("member:stranger@example.com")).toBe(false);
  });

  it("rejects a bad signature outright", async () => {
    const env = envWith();
    const res = await handleStripeWebhook(
      new Request("https://api.example.com/api/stripe/webhook", {
        method: "POST", body: "{}",
        headers: { "Stripe-Signature": "t=1,v1=deadbeef" },
      }),
      env,
    );
    expect(res.status).toBe(400);
  });
});

describe("personal feed gating", () => {
  const token = "a".repeat(32);

  function activeEnv(status = "active") {
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    kv.store.set(`feedtok:${token}`, "fan@example.com");
    kv.store.set("member:fan@example.com", JSON.stringify({
      shows: ["tesla", "spacex"], first_name: "", city: "",
      tier: "personal", status, feed_token: token, updated_at: "",
    }));
    const bucket = env.PERSONAL_BUCKET as unknown as FakeBucket;
    bucket.objects.set(`personal/${token}/feed.rss`, "<rss/>");
    return env;
  }

  async function get(env: Env, tok: string, file: string) {
    return handlePersonalFeed(
      new Request(`https://api.example.com/api/feed/${tok}/${file}`),
      env, tok, file,
    );
  }

  it("serves an active member's feed", async () => {
    const res = await get(activeEnv(), token, "feed.rss");
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toContain("rss");
  });

  it("404s an unknown token (no enumeration signal)", async () => {
    const res = await get(activeEnv(), "b".repeat(32), "feed.rss");
    expect(res.status).toBe(404);
  });

  it("404s a cancelled member even with a lingering mapping", async () => {
    const res = await get(activeEnv("cancelled"), token, "feed.rss");
    expect(res.status).toBe(404);
  });

  it("rejects traversal-shaped file names", async () => {
    const res = await get(activeEnv(), token, "..secrets");
    expect(res.status).toBe(400);
  });
});

describe("admin specs export", () => {
  it("is bearer-gated and never includes emails", async () => {
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    kv.store.set("member:fan@example.com", JSON.stringify({
      shows: ["tesla", "spacex"], first_name: "Sam", city: "Vancouver",
      tier: "personal_local", status: "active",
      feed_token: "c".repeat(32), updated_at: "",
    }));
    const denied = await handleAdminSpecs(
      new Request("https://api.example.com/api/admin/personal-specs"), env);
    expect(denied.status).toBe(401);

    const res = await handleAdminSpecs(
      new Request("https://api.example.com/api/admin/personal-specs", {
        headers: { Authorization: "Bearer admin-token" },
      }), env);
    expect(res.status).toBe(200);
    const body = await res.json() as { specs: Record<string, unknown>[] };
    expect(body.specs).toHaveLength(1);
    expect(body.specs[0].token).toBe("c".repeat(32));
    expect(body.specs[0].default_lineup).toBe(false);
    expect(JSON.stringify(body)).not.toContain("fan@example.com");
  });

  it("a paying member with no lineup gets the starter lineup, not silence", async () => {
    // Aug 27 2026: <2 chosen shows used to silently EXCLUDE the member
    // from the build — they paid and their feed URL 404'd forever.
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    kv.store.set("member:new@example.com", JSON.stringify({
      shows: [], first_name: "", city: "",
      tier: "personal", status: "active",
      feed_token: "d".repeat(32), updated_at: "",
    }));
    const res = await handleAdminSpecs(
      new Request("https://api.example.com/api/admin/personal-specs", {
        headers: { Authorization: "Bearer admin-token" },
      }), env);
    const body = await res.json() as { specs: Record<string, unknown>[] };
    expect(body.specs).toHaveLength(1);
    expect(body.specs[0].shows).toEqual([...DEFAULT_LINEUP]);
    expect(body.specs[0].default_lineup).toBe(true);
  });

  it("every starter-lineup slug is in the closed show vocabulary", () => {
    for (const slug of DEFAULT_LINEUP) {
      expect(PERSONAL_SHOWS).toContain(slug);
    }
    expect(DEFAULT_LINEUP.length).toBeGreaterThanOrEqual(2);
  });
});


describe("add-ons (Aug 30 2026)", () => {
  it("admin specs carry a member's saved addons, absent when never saved", async () => {
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    kv.store.set("member:a@example.com", JSON.stringify({
      shows: ["tesla", "spacex"], first_name: "", city: "Lyon",
      tier: "personal_local", status: "active",
      addons: ["weather", "traffic"],
      feed_token: "e".repeat(32), updated_at: "",
    }));
    kv.store.set("member:b@example.com", JSON.stringify({
      shows: ["tesla", "spacex"], first_name: "", city: "",
      tier: "personal", status: "active",
      feed_token: "f".repeat(32), updated_at: "",
    }));
    const res = await handleAdminSpecs(
      new Request("https://api.example.com/api/admin/personal-specs", {
        headers: { Authorization: "Bearer admin-token" },
      }), env);
    const body = await res.json() as { specs: Record<string, unknown>[] };
    const withAddons = body.specs.find((sp) => sp.token === "e".repeat(32))!;
    const withoutAddons = body.specs.find((sp) => sp.token === "f".repeat(32))!;
    expect(withAddons.addons).toEqual(["weather", "traffic"]);
    // Never-saved must stay ABSENT (the builder treats absent as
    // "defaults apply"), never an empty list ("no add-ons" choice).
    expect("addons" in withoutAddons).toBe(false);
  });

  it("addon vocabulary stays closed and non-trivial", () => {
    expect(PERSONAL_ADDONS.length).toBeGreaterThanOrEqual(4);
    for (const id of PERSONAL_ADDONS) {
      expect(id).toMatch(/^[a-z_]+$/);
    }
  });
});

describe("membership plumbing", () => {
  it("member list carries the gallery tag (one identity)", () => {
    const { tags } = resolveSubscribeTags("member", undefined);
    expect(tags).toContain("nerra-member");
    expect(tags).toContain("gallery-subscriber");
  });

  it("Soft Personal interest list is filterable without forcing newsletter", () => {
    const { tags, list } = resolveSubscribeTags(
      "personal-interest", "src-nerranetwork");
    expect(list).toBe("personal-interest");
    expect(tags).toEqual(["personal-interest", "src-nerranetwork"]);
    expect(tags).not.toContain("gallery-subscriber");
    expect(tags).not.toContain("nerra-member");
  });

  it("Soft Personal newsletter checkbox adds nerra-member (Ask C segment)", () => {
    const { tags } = resolveSubscribeTags(
      "personal-interest", "src-nerranetwork", ["SpaceX Daily"],
      { networkNewsletter: true });
    expect(tags).toContain("nerra-member");
    expect(tags).toContain("SpaceX Daily");
    expect(tags).not.toContain("gallery-subscriber");
  });

  it("show newsletter tags pass only from the closed set", () => {
    const { tags } = resolveSubscribeTags("member", undefined, [
      "Tesla Shorts Time", "Not A Real Tag", "SpaceX Daily",
    ]);
    expect(tags).toContain("Tesla Shorts Time");
    expect(tags).toContain("SpaceX Daily");
    expect(tags).not.toContain("Not A Real Tag");
  });

  it("show vocabulary matches the EN edition lineup size", () => {
    expect(PERSONAL_SHOWS).toHaveLength(13);
  });
});

// ---------------------------------------------------------------------------
// Plan switching (Sep 13 2026): checkout refs, subscription.updated,
// and the customer-portal route.
// ---------------------------------------------------------------------------

async function memberCookie(env: Env, email: string) {
  const token = await signJwt(
    { sub: email, scope: "gallery-subscriber", ttlSeconds: 3600 },
    env.JWT_SECRET,
  );
  return `nn_gallery=${encodeURIComponent(token)}`;
}

describe("plan switching (Sep 13 2026)", () => {
  async function post(env: Env, event: object) {
    const payload = JSON.stringify(event);
    const sig = await stripeSig(
      payload, "whsec_test", Math.floor(Date.now() / 1000));
    return handleStripeWebhook(
      new Request("https://api.example.com/api/stripe/webhook", {
        method: "POST", body: payload,
        headers: { "Stripe-Signature": sig },
      }), env);
  }

  afterEach(() => { vi.unstubAllGlobals(); });

  it("a checkout ref attaches the purchase to the signed-in account, not the wallet email", async () => {
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    // Signed in as the +tag address, mint a ref…
    const refRes = await handleCheckoutRef(
      new Request("https://api.example.com/api/account/checkout-ref", {
        method: "POST",
        headers: { Cookie: await memberCookie(env, "me+nerra@example.com") },
      }), env);
    const { ref } = await refRes.json() as { ref: string };
    expect(ref).toMatch(/^[a-f0-9]{32}$/);
    // …then Apple Pay reports the bare address (the 2026-09-06 case).
    await post(env, {
      type: "checkout.session.completed",
      data: { object: {
        client_reference_id: ref,
        customer_details: { email: "me@example.com" },
        customer: "cus_42",
        metadata: { tier: "personal" },
        subscription: "sub_42", amount_total: 499,
      } },
    });
    expect(kv.store.has("member:me@example.com")).toBe(false);
    const rec = JSON.parse(kv.store.get("member:me+nerra@example.com")!);
    expect(rec.status).toBe("active");
    expect(rec.customer_id).toBe("cus_42");
    // One-shot: the ref is consumed.
    expect(kv.store.has(`cref:${ref}`)).toBe(false);
  });

  it("a bogus or expired ref falls back to the wallet email", async () => {
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    await post(env, {
      type: "checkout.session.completed",
      data: { object: {
        client_reference_id: "0".repeat(32),
        customer_details: { email: "fan@example.com" },
        metadata: { tier: "personal" }, subscription: "sub_1", amount_total: 499,
      } },
    });
    expect(kv.store.has("member:fan@example.com")).toBe(true);
  });

  it("checkout-ref requires a session", async () => {
    const res = await handleCheckoutRef(
      new Request("https://api.example.com/api/account/checkout-ref",
        { method: "POST" }), envWith());
    expect(res.status).toBe(401);
  });

  it("subscription.updated switches the tier and keeps the feed token", async () => {
    const env = envWith({
      STRIPE_PRICE_PERSONAL: "price_p", STRIPE_PRICE_PNN: "price_pnn",
    });
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    await post(env, {
      type: "checkout.session.completed",
      data: { object: {
        customer_email: "fan@example.com", customer: "cus_1",
        metadata: { tier: "personal" }, subscription: "sub_1", amount_total: 499,
      } },
    });
    const before = JSON.parse(kv.store.get("member:fan@example.com")!);
    await post(env, {
      type: "customer.subscription.updated",
      data: { object: {
        id: "sub_1", customer: "cus_1",
        items: { data: [{ price: { id: "price_pnn" } }] },
        cancel_at_period_end: false,
      } },
    });
    const after = JSON.parse(kv.store.get("member:fan@example.com")!);
    expect(after.tier).toBe("personal_local");
    expect(after.feed_token).toBe(before.feed_token);
    expect(after.status).toBe("active");
    expect(kv.store.get(`feedtok:${after.feed_token}`)).toBe("fan@example.com");
  });

  it("subscription.updated records a cancel-at-period-end date and clears it again", async () => {
    const env = envWith({ STRIPE_PRICE_PERSONAL: "price_p" });
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    await post(env, {
      type: "checkout.session.completed",
      data: { object: {
        customer_email: "fan@example.com",
        metadata: { tier: "personal" }, subscription: "sub_1", amount_total: 499,
      } },
    });
    await post(env, {
      type: "customer.subscription.updated",
      data: { object: {
        id: "sub_1", items: { data: [{ price: { id: "price_p" } }] },
        cancel_at_period_end: true, current_period_end: 1790000000,
      } },
    });
    let rec = JSON.parse(kv.store.get("member:fan@example.com")!);
    expect(rec.ends_at).toBe("2026-09-21");
    expect(rec.status).toBe("active");        // still served until then
    await post(env, {
      type: "customer.subscription.updated",
      data: { object: {
        id: "sub_1", items: { data: [{ price: { id: "price_p" } }] },
        cancel_at_period_end: false, current_period_end: 1790000000,
      } },
    });
    rec = JSON.parse(kv.store.get("member:fan@example.com")!);
    expect(rec.ends_at).toBeUndefined();
  });

  it("reads current_period_end from the subscription item (2025-03-31.basil shape)", async () => {
    const env = envWith({ STRIPE_PRICE_PERSONAL: "price_p" });
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    await post(env, {
      type: "checkout.session.completed",
      data: { object: {
        customer_email: "fan@example.com",
        metadata: { tier: "personal" }, subscription: "sub_1", amount_total: 499,
      } },
    });
    await post(env, {
      type: "customer.subscription.updated",
      data: { object: {
        id: "sub_1", cancel_at_period_end: true,
        items: { data: [{ price: { id: "price_p" }, current_period_end: 1790000000 }] },
      } },
    });
    expect(JSON.parse(kv.store.get("member:fan@example.com")!).ends_at)
      .toBe("2026-09-21");
  });

  it("an unmapped price leaves the tier alone", async () => {
    const env = envWith({ STRIPE_PRICE_PERSONAL: "price_p" });
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    await post(env, {
      type: "checkout.session.completed",
      data: { object: {
        customer_email: "fan@example.com",
        metadata: { tier: "personal_local" }, subscription: "sub_1", amount_total: 899,
      } },
    });
    await post(env, {
      type: "customer.subscription.updated",
      data: { object: { id: "sub_1", items: { data: [{ price: { id: "price_mystery" } }] } } },
    });
    expect(JSON.parse(kv.store.get("member:fan@example.com")!).tier)
      .toBe("personal_local");
  });

  it("portal: 503 without the key, 404 without a subscription, url with both", async () => {
    const noKey = envWith();
    const cookie = await memberCookie(noKey, "fan@example.com");
    const req = () => new Request("https://api.example.com/api/account/portal",
      { method: "POST", headers: { Cookie: cookie } });
    expect((await handlePortal(req(), noKey)).status).toBe(503);

    const env = envWith({ STRIPE_SECRET_KEY: "rk_test" });
    expect((await handlePortal(req(), env)).status).toBe(404);

    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    kv.store.set("member:fan@example.com", JSON.stringify({
      shows: [], first_name: "", city: "", tier: "personal", status: "active",
      feed_token: "a".repeat(32), sub_id: "sub_1", updated_at: "",
    }));
    const calls: string[] = [];
    vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method || "GET"} ${url}`);
      if (url.endsWith("/subscriptions/sub_1")) {
        return new Response(JSON.stringify({ id: "sub_1", customer: "cus_7" }));
      }
      if (url.endsWith("/billing_portal/sessions")) {
        expect(String(init?.body)).toContain("customer=cus_7");
        expect(String(init?.body)).toContain("return_url=");
        return new Response(JSON.stringify({ url: "https://billing.stripe.com/p/session/x" }));
      }
      return new Response("{}", { status: 500 });
    });
    const res = await handlePortal(req(), env);
    expect(res.status).toBe(200);
    expect((await res.json() as { url: string }).url)
      .toBe("https://billing.stripe.com/p/session/x");
    // Legacy member (no customer_id) → looked up once, then remembered.
    expect(JSON.parse(kv.store.get("member:fan@example.com")!).customer_id).toBe("cus_7");
    expect(calls[0]).toContain("/subscriptions/sub_1");
  });

  it("account exposes billing_portal only when it can be opened", async () => {
    const env = envWith({ STRIPE_SECRET_KEY: "rk_test" });
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    const cookie = await memberCookie(env, "fan@example.com");
    const get = async (e: Env) => (await (await handleAccount(
      new Request("https://api.example.com/api/account", { headers: { Cookie: cookie } }),
      e)).json()) as { member: { billing_portal: boolean; ends_at: string | null } };
    expect((await get(env)).member.billing_portal).toBe(false);   // no member yet
    kv.store.set("member:fan@example.com", JSON.stringify({
      shows: [], first_name: "", city: "", tier: "personal", status: "active",
      feed_token: "a".repeat(32), sub_id: "sub_1", ends_at: "2026-10-01", updated_at: "",
    }));
    const body = await get(env);
    expect(body.member.billing_portal).toBe(true);
    expect(body.member.ends_at).toBe("2026-10-01");
    expect((body as any).email).toBe("fan@example.com");
    expect((await get(envWith())).member.billing_portal).toBe(false); // no key
  });
});

// ---------------------------------------------------------------------------
// Personal News Network (Sep 13 2026): locations + topics on the record.
// ---------------------------------------------------------------------------

describe("locations + topics (Sep 13 2026)", () => {
  async function save(env: Env, email: string, body: object) {
    return handlePreferences(new Request("https://api.example.com/api/account/preferences", {
      method: "POST",
      headers: { Cookie: await memberCookie(env, email), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }), env);
  }
  async function account(env: Env, email: string) {
    return (await (await handleAccount(
      new Request("https://api.example.com/api/account",
        { headers: { Cookie: await memberCookie(env, email) } }), env)).json()) as any;
  }

  it("stores up to three cities and five topics, scrubbed and deduped, city = cities[0]", async () => {
    const env = envWith();
    const res = await save(env, "fan@example.com", {
      shows: ["spacex", "tesla"],
      cities: ["Vancouver, BC", " kelowna ", "Kelowna", "Victoria", "Calgary"],
      topics: ["<b>Starship</b>", "BC  housing", "x".repeat(200), "", "{date_spoken}", "six", "seven"],
    });
    expect(res.status).toBe(200);
    const saved = (await res.json() as any).saved;
    expect(saved.cities).toEqual(["Vancouver, BC", "kelowna", "Victoria"]);
    expect(saved.city).toBe("Vancouver, BC");
    expect(saved.topics).toHaveLength(5);
    expect(saved.topics[0]).toBe("Starship");
    expect(saved.topics[1]).toBe("BC housing");
    expect(saved.topics[2]).toHaveLength(60);
    expect(saved.topics[3]).toBe("date_spoken");   // braces never reach a prompt
    const acct = await account(env, "fan@example.com");
    expect(acct.member.preferences.cities).toEqual(["Vancouver, BC", "kelowna", "Victoria"]);
    expect(acct.member.preferences.topics[0]).toBe("Starship");
  });

  it("a legacy page sending a bare city still works, and old records read back as one city", async () => {
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    await save(env, "fan@example.com", { shows: ["spacex", "tesla"], city: "Kelowna" });
    let rec = JSON.parse(kv.store.get("member:fan@example.com")!);
    expect(rec.cities).toEqual(["Kelowna"]);
    expect(rec.city).toBe("Kelowna");
    // A pre-Sep-13 record with only `city`:
    kv.store.set("member:old@example.com", JSON.stringify({
      shows: ["spacex", "tesla"], first_name: "", city: "Victoria",
      tier: "personal_local", status: "active", feed_token: "c".repeat(32), updated_at: "",
    }));
    const acct = await account(env, "old@example.com");
    expect(acct.member.preferences.cities).toEqual(["Victoria"]);
    expect(acct.member.preferences.topics).toEqual([]);
  });

  it("admin specs carry cities and topics (still no email)", async () => {
    const env = envWith();
    await save(env, "fan@example.com", {
      shows: ["spacex", "tesla"], cities: ["Vancouver, BC", "Kelowna"], topics: ["Starship"],
    });
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    const rec = JSON.parse(kv.store.get("member:fan@example.com")!);
    kv.store.set("member:fan@example.com", JSON.stringify({
      ...rec, tier: "personal_local", status: "active", feed_token: "d".repeat(32),
    }));
    const res = await handleAdminSpecs(new Request("https://api.example.com/api/admin/personal-specs",
      { headers: { Authorization: "Bearer admin-token" } }), env);
    const body = await res.json() as { specs: any[] };
    const sp = body.specs.find((x) => x.token === "d".repeat(32))!;
    expect(sp.cities).toEqual(["Vancouver, BC", "Kelowna"]);
    expect(sp.topics).toEqual(["Starship"]);
    expect(sp.city).toBe("Vancouver, BC");
    expect(JSON.stringify(body)).not.toContain("example.com");
  });
});

// ---------------------------------------------------------------------------
// Books for members (Sep 14 2026): the EPUB library behind /api/books.
// ---------------------------------------------------------------------------

describe("books library (Sep 14 2026)", () => {
  function envWithBooks() {
    const env = envWith({ BOOKS_BUCKET: new FakeBucket() as unknown as R2Bucket });
    const books = env.BOOKS_BUCKET as unknown as FakeBucket;
    books.objects.set("books/first_principles_vol1/first_principles_vol1.epub", "PK-epub-bytes");
    return env;
  }
  async function member(env: Env, email: string, tier: string, status = "active") {
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    kv.store.set(`member:${email}`, JSON.stringify({
      shows: ["spacex", "tesla"], first_name: "", city: "", tier, status,
      feed_token: "a".repeat(32), sub_id: "sub_1", updated_at: "",
    }));
    return memberCookie(env, email);
  }
  const get = (env: Env, path: string, cookie?: string) => handleBookDownload(
    new Request(`https://api.example.com${path}`, { headers: cookie ? { Cookie: cookie } : {} }),
    env, path.split("/")[3], path.split("/")[4]);

  it("streams an EPUB to an active Personal News Network member", async () => {
    const env = envWithBooks();
    const cookie = await member(env, "fan@example.com", "personal_local");
    const res = await get(env, "/api/books/first_principles_vol1/first_principles_vol1.epub", cookie);
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("application/epub+zip");
    expect(res.headers.get("Content-Disposition")).toContain("first_principles_vol1.epub");
    expect(res.headers.get("Cache-Control")).toContain("no-store");
  });

  it("is 401 without a session, 403 on Personal, 403 once cancelled or downgraded", async () => {
    const env = envWithBooks();
    const path = "/api/books/first_principles_vol1/first_principles_vol1.epub";
    expect((await get(env, path)).status).toBe(401);
    expect((await get(env, path, await member(env, "p@example.com", "personal"))).status).toBe(403);
    expect((await get(env, path, await member(env, "c@example.com", "personal_local", "cancelled"))).status).toBe(403);
  });

  it("rejects anything that is not an EPUB of that volume, and unknown volumes", async () => {
    const env = envWithBooks();
    const cookie = await member(env, "fan@example.com", "personal_local");
    expect((await get(env, "/api/books/first_principles_vol1/first_principles_vol1.m4b", cookie)).status).toBe(400);
    expect((await get(env, "/api/books/first_principles_vol1/other.epub", cookie)).status).toBe(400);
    expect((await get(env, "/api/books/nope_vol9/nope_vol9.epub", cookie)).status).toBe(404);
  });

  it("503 without the bucket; account reports library only for active PNN", async () => {
    const noBucket = envWith();
    const cookie = await member(noBucket, "fan@example.com", "personal_local");
    expect((await get(noBucket, "/api/books/first_principles_vol1/first_principles_vol1.epub", cookie)).status).toBe(503);
    const env = envWithBooks();
    const c2 = await member(env, "fan@example.com", "personal_local");
    const acct = await (await handleAccount(new Request("https://api.example.com/api/account",
      { headers: { Cookie: c2 } }), env)).json() as any;
    expect(acct.perks.library).toBe(true);
    const c3 = await member(env, "p@example.com", "personal");
    const acct2 = await (await handleAccount(new Request("https://api.example.com/api/account",
      { headers: { Cookie: c3 } }), env)).json() as any;
    expect(acct2.perks.library).toBe(false);
  });
});


// ---------------------------------------------------------------------------
// On-demand builds (Sep 17 2026): activation dispatch, /api/account/rebuild,
// and the account page's "today" status.
// ---------------------------------------------------------------------------

describe("on-demand builds (Sep 17 2026)", () => {
  const TOKEN = "b".repeat(32);
  const today = todayIso();

  function activeEnv(overrides: Record<string, unknown> = {}) {
    const env = envWith({ GITHUB_DISPATCH_TOKEN: "github_pat_x\n", ...overrides });
    (env.RATE_LIMIT_KV as unknown as FakeKV).store.set(
      "member:fan@example.com", JSON.stringify({
        shows: ["spacex", "tesla"], first_name: "Pat", city: "", tier: "personal",
        status: "active", feed_token: TOKEN, sub_id: "sub_1", updated_at: "",
      }));
    return env;
  }

  function stubGitHub(calls: { url: string; body: any; auth: string }[], status = 204) {
    vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
      const headers = init?.headers as Record<string, string>;
      calls.push({ url, body: JSON.parse(String(init?.body)), auth: headers.Authorization });
      return new Response(status === 204 ? null : "{}", { status });
    });
  }

  async function rebuild(env: Env) {
    const cookie = await memberCookie(env, "fan@example.com");
    return handleRebuild(new Request("https://api.example.com/api/account/rebuild",
      { method: "POST", headers: { Cookie: cookie } }), env);
  }

  async function account(env: Env) {
    const cookie = await memberCookie(env, "fan@example.com");
    return (await (await handleAccount(
      new Request("https://api.example.com/api/account", { headers: { Cookie: cookie } }),
      env)).json()) as any;
  }

  afterEach(() => { vi.unstubAllGlobals(); });

  it("first build of the day is free, dispatches only this member, trims the token", async () => {
    const env = activeEnv();
    const calls: any[] = [];
    stubGitHub(calls);
    const res = await rebuild(env);
    expect(res.status).toBe(202);
    const body = await res.json() as any;
    expect(body.eta_minutes).toBeGreaterThan(0);
    expect(body.today.building).toBe(true);
    expect(body.today.rebuilds_left).toBe(REBUILDS_PER_DAY);   // not a rebuild
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toContain("/repos/Planetterrian/nerra-personal-batch/actions/workflows/personal-feeds.yml/dispatches");
    expect(calls[0].body).toEqual({ ref: "main", inputs: { date: today, only: TOKEN, replace: "false" } });
    expect(calls[0].auth).toBe("Bearer github_pat_x");   // newline trimmed
    // While building: 409, and the account reports it.
    expect((await rebuild(env)).status).toBe(409);
    expect((await account(env)).member.today.building).toBe(true);
  });

  it("re-making a built day costs a rebuild and stops at the daily limit", async () => {
    const env = activeEnv();
    (env.PERSONAL_BUCKET as unknown as FakeBucket).objects.set(
      `personal/${TOKEN}/episodes.json`, JSON.stringify({ episodes: [
        { date: today, built_at: "2026-01-01T00:00:00Z", filename: "x.mp3" },
      ] }));
    const calls: any[] = [];
    stubGitHub(calls);
    for (let i = 0; i < REBUILDS_PER_DAY; i++) {
      const res = await rebuild(env);
      expect(res.status).toBe(202);
      expect(calls[i].body.inputs.replace).toBe("true");
      // Simulate the builder landing a newer row so "building" clears.
      (env.PERSONAL_BUCKET as unknown as FakeBucket).objects.set(
        `personal/${TOKEN}/episodes.json`, JSON.stringify({ episodes: [
          { date: today, built_at: new Date(Date.now() + 1000).toISOString(), filename: "x.mp3" },
        ] }));
    }
    const status = (await account(env)).member.today;
    expect(status.building).toBe(false);
    expect(status.rebuilds_left).toBe(0);
    expect(status.built_at).toBeTruthy();
    expect((await rebuild(env)).status).toBe(429);
    expect(calls).toHaveLength(REBUILDS_PER_DAY);
  });

  it("503 without the dispatch token; 404 for a non-member; 502 when GitHub refuses", async () => {
    const none = activeEnv({ GITHUB_DISPATCH_TOKEN: undefined });
    expect((await rebuild(none)).status).toBe(503);
    expect((await account(none)).member.today.available).toBe(false);
    const env = activeEnv();
    (env.RATE_LIMIT_KV as unknown as FakeKV).store.delete("member:fan@example.com");
    expect((await rebuild(env)).status).toBe(404);
    const refused = activeEnv();
    const calls: any[] = [];
    stubGitHub(calls, 403);
    expect((await rebuild(refused)).status).toBe(502);
    expect(calls).toHaveLength(1);   // 4xx is not retried
    expect((await account(refused)).member.today.building).toBe(false);
  });

  it("activation dispatches the first edition; a re-activation does not", async () => {
    const env = envWith({ GITHUB_DISPATCH_TOKEN: "github_pat_x" });
    const calls: any[] = [];
    stubGitHub(calls);
    const post = async (event: object) => {
      const payload = JSON.stringify(event);
      const sig = await stripeSig(payload, "whsec_test", Math.floor(Date.now() / 1000));
      return handleStripeWebhook(new Request("https://api.example.com/api/stripe/webhook", {
        method: "POST", body: payload, headers: { "Stripe-Signature": sig },
      }), env);
    };
    const session = { metadata: { tier: "personal" }, subscription: "sub_9",
      customer: "cus_9", customer_details: { email: "new@example.com" } };
    expect((await post({ type: "checkout.session.completed", data: { object: session } })).status).toBe(200);
    expect(calls).toHaveLength(1);
    const rec = JSON.parse((env.RATE_LIMIT_KV as unknown as FakeKV).store.get("member:new@example.com")!);
    expect(calls[0].body.inputs).toEqual({ date: today, only: rec.feed_token, replace: "false" });
    // Same member checks out again (already active) → no second dispatch.
    expect((await post({ type: "checkout.session.completed", data: { object: session } })).status).toBe(200);
    expect(calls).toHaveLength(1);
  });

  it("activation without a token still activates (dispatch is best-effort)", async () => {
    const env = envWith();
    const payload = JSON.stringify({ type: "checkout.session.completed", data: { object: {
      metadata: { tier: "personal" }, subscription: "sub_9",
      customer_details: { email: "new@example.com" } } } });
    const sig = await stripeSig(payload, "whsec_test", Math.floor(Date.now() / 1000));
    const res = await handleStripeWebhook(new Request("https://api.example.com/api/stripe/webhook", {
      method: "POST", body: payload, headers: { "Stripe-Signature": sig } }), env);
    expect(res.status).toBe(200);
    expect(JSON.parse((env.RATE_LIMIT_KV as unknown as FakeKV).store.get("member:new@example.com")!).status).toBe("active");
  });
});


// ---------------------------------------------------------------------------
// Free trial (Sep 17 2026): trial end recorded at checkout, cleared on
// conversion, and a dead subscription status revokes without .deleted.
// ---------------------------------------------------------------------------

describe("free trial (Sep 17 2026)", () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  async function post(env: Env, event: object) {
    const payload = JSON.stringify(event);
    const sig = await stripeSig(payload, "whsec_test", Math.floor(Date.now() / 1000));
    return handleStripeWebhook(new Request("https://api.example.com/api/stripe/webhook", {
      method: "POST", body: payload, headers: { "Stripe-Signature": sig } }), env);
  }
  const member = (env: Env) => JSON.parse(
    (env.RATE_LIMIT_KV as unknown as FakeKV).store.get("member:t@example.com")!);

  it("records trial_ends_at from the subscription at checkout, clears it on conversion", async () => {
    const env = envWith({ STRIPE_SECRET_KEY: "rk_test", STRIPE_PRICE_PERSONAL: "price_p" });
    vi.stubGlobal("fetch", async (url: string) => {
      if (url.endsWith("/subscriptions/sub_t")) {
        return new Response(JSON.stringify({ id: "sub_t", status: "trialing", trial_end: 1790208000 }));
      }
      return new Response("{}", { status: 500 });
    });
    await post(env, { type: "checkout.session.completed", data: { object: {
      metadata: { tier: "personal" }, subscription: "sub_t", customer: "cus_t",
      customer_details: { email: "t@example.com" } } } });
    expect(member(env).status).toBe("active");
    expect(member(env).trial_ends_at).toBe("2026-09-24");
    const cookie = await memberCookie(env, "t@example.com");
    const acct = await (await handleAccount(new Request("https://api.example.com/api/account",
      { headers: { Cookie: cookie } }), env)).json() as any;
    expect(acct.member.trial_ends_at).toBe("2026-09-24");
    // Trial converts: status active, no trial_end → cleared, still served.
    await post(env, { type: "customer.subscription.updated", data: { object: {
      id: "sub_t", status: "active", customer: "cus_t",
      items: { data: [{ price: { id: "price_p" }, current_period_end: 1792800000 }] } } } });
    expect(member(env).trial_ends_at).toBeUndefined();
    expect(member(env).status).toBe("active");
  });

  it("a subscription that goes unpaid or canceled revokes the feed at once", async () => {
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    kv.store.set("member:t@example.com", JSON.stringify({
      shows: [], first_name: "", city: "", tier: "personal", status: "active",
      feed_token: "c".repeat(32), sub_id: "sub_t", trial_ends_at: "2026-09-24", updated_at: "" }));
    kv.store.set("feedtok:" + "c".repeat(32), "t@example.com");
    kv.store.set("sub:sub_t", "t@example.com");
    await post(env, { type: "customer.subscription.updated", data: { object: {
      id: "sub_t", status: "unpaid", customer: "cus_t", items: { data: [] } } } });
    expect(member(env).status).toBe("cancelled");
    expect(member(env).trial_ends_at).toBeUndefined();
    expect(kv.store.has("feedtok:" + "c".repeat(32))).toBe(false);
    const res = await handlePersonalFeed(new Request("https://api.example.com/x"), env,
      "c".repeat(32), "feed.rss");
    expect(res.status).toBe(404);
  });

  it("checkout without the key still activates (no trial lookup)", async () => {
    const env = envWith();
    await post(env, { type: "checkout.session.completed", data: { object: {
      metadata: { tier: "personal" }, subscription: "sub_t",
      customer_details: { email: "t@example.com" } } } });
    expect(member(env).status).toBe("active");
    expect(member(env).trial_ends_at).toBeUndefined();
  });
});
