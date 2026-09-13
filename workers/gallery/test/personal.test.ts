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
  handleCheckoutRef,
  handlePersonalFeed,
  handlePortal,
  handleStripeWebhook,
  verifyStripeSignature,
} from "../src/personal";
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
    expect((await get(envWith())).member.billing_portal).toBe(false); // no key
  });
});
