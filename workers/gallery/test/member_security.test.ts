/**
 * Oct 28 2026 — member accounts need a session that read the inbox, the
 * paying member can always sign in, cancelling one plan never cancels the
 * other, and the private feed streams the way podcast apps ask for it.
 *
 * The defect these pin: POST /api/subscribe signed a 90-day cookie for any
 * address typed into a form, and every account endpoint accepted that
 * cookie, so knowing a member's email was enough to read their private feed
 * URL, name, cities, topics and profile note, and to change their lineup.
 */

import { describe, expect, it, vi } from "vitest";
import {
  handleAccount,
  handlePersonalFeed,
  handlePortal,
  handlePreferences,
  handleStripeWebhook,
  mayUseRecord,
  parseByteRange,
  resolveRange,
  welcomeFeedXml,
} from "../src/personal";
import { handleLogin, handleMagic, handleSubscribe } from "../src/handlers";
import { buildWelcomeEmail } from "../src/magic-email";
import { signJwt, verifyJwt } from "../src/jwt";
import type { ButtondownClient, Env, HandlerDeps, ResendClient } from "../src/types";

const SECRET = "test-secret-test-secret-test-secret!";
const TOKEN = "b".repeat(32);

class FakeKV {
  store = new Map<string, string>();
  async get(key: string) { return this.store.get(key) ?? null; }
  async put(key: string, value: string) { this.store.set(key, value); }
  async delete(key: string) { this.store.delete(key); }
  async list(opts: { prefix: string }) {
    return {
      keys: [...this.store.keys()].filter((k) => k.startsWith(opts.prefix))
        .map((name) => ({ name })),
      list_complete: true, cursor: undefined,
    };
  }
}

/** An R2 bucket with sizes, HEAD, ranged GET and PUT. */
class SizedBucket {
  objects = new Map<string, Uint8Array>();
  puts: string[] = [];
  private meta(key: string) {
    const data = this.objects.get(key);
    if (!data) return null;
    return {
      size: data.length,
      httpEtag: '"e"',
      writeHttpMetadata: (_h: Headers) => {},
    };
  }
  async head(key: string) { return this.meta(key); }
  async get(key: string, opts?: { range?: { offset: number; length: number } }) {
    const data = this.objects.get(key);
    if (!data) return null;
    const slice = opts?.range
      ? data.slice(opts.range.offset, opts.range.offset + opts.range.length)
      : data;
    return { ...this.meta(key)!, body: new Response(slice).body };
  }
  async put(key: string, value: string) {
    this.objects.set(key, new TextEncoder().encode(value));
    this.puts.push(key);
  }
}

function envWith(overrides: Record<string, unknown> = {}): Env {
  return {
    GALLERY_BUCKET: new SizedBucket() as unknown as R2Bucket,
    JWT_SECRET: SECRET,
    BUTTONDOWN_API_KEY: "x",
    RESEND_API_KEY: "x",
    RESEND_FROM_EMAIL: "x@example.com",
    RATE_LIMIT_KV: new FakeKV() as unknown as KVNamespace,
    PERSONAL_BUCKET: new SizedBucket() as unknown as R2Bucket,
    STRIPE_WEBHOOK_SECRET: "whsec_test",
    ...overrides,
  } as unknown as Env;
}

function makeDeps(exists = false): HandlerDeps {
  const buttondown: ButtondownClient = {
    subscribe: vi.fn(async () => ({ ok: true, alreadySubscribed: false, status: 201 })),
    isSubscribed: vi.fn(async () => ({ ok: true, exists, status: 200 })),
  };
  const resend: ResendClient = {
    sendEmail: vi.fn(async () => ({ ok: true, id: "m", status: 200 })),
  };
  return { buttondown, resend };
}

async function cookie(email: string, opts: { verified?: boolean; now?: number } = {}) {
  const token = await signJwt(
    { sub: email, scope: "gallery-subscriber", ttlSeconds: 3600,
      ...(opts.verified ? { v: 1 as const } : {}) },
    SECRET, opts.now);
  return `nn_gallery=${encodeURIComponent(token)}`;
}

function paidMember(env: Env, email: string, extra: Record<string, unknown> = {}) {
  const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
  kv.store.set(`member:${email}`, JSON.stringify({
    shows: ["spacex", "tesla"], first_name: "Dana", city: "Halifax",
    cities: ["Halifax"], topics: ["fusion"], profile: "I fly drones.",
    tier: "personal", status: "active", feed_token: TOKEN, sub_id: "sub_new",
    customer_id: "cus_1", updated_at: "", ...extra,
  }));
  kv.store.set(`feedtok:${TOKEN}`, email);
}

const req = (path: string, init: RequestInit = {}) =>
  new Request(`https://api.example.com${path}`, init);

async function stripeSig(payload: string, t: number) {
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode("whsec_test"),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(`${t}.${payload}`));
  return `t=${t},v1=${[...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("")}`;
}

async function webhook(env: Env, event: object, deps?: HandlerDeps) {
  const payload = JSON.stringify(event);
  const sig = await stripeSig(payload, Math.floor(Date.now() / 1000));
  return handleStripeWebhook(req("/api/stripe/webhook", {
    method: "POST", body: payload, headers: { "Stripe-Signature": sig },
  }), env, deps);
}

// ---------------------------------------------------------------------------

describe("a form-signed cookie never opens a paid record", () => {
  it("subscribe signs an UNVERIFIED cookie; the emailed link signs a verified one", async () => {
    const env = envWith();
    const sub = await handleSubscribe(req("/api/subscribe", {
      method: "POST", body: JSON.stringify({ email: "victim@example.com" }),
      headers: { "Content-Type": "application/json", Origin: "https://nerranetwork.com" },
    }), env, makeDeps());
    const subTok = decodeURIComponent(
      /nn_gallery=([^;]+)/.exec(sub.headers.get("Set-Cookie") || "")![1]);
    expect((await verifyJwt(subTok, SECRET)).claims?.v).toBeUndefined();

    const link = await signJwt(
      { sub: "victim@example.com", scope: "magic-login", ttlSeconds: 600 }, SECRET);
    const magic = await handleMagic(req(`/api/magic?token=${encodeURIComponent(link)}`),
      env, makeDeps());
    const magicTok = decodeURIComponent(
      /nn_gallery=([^;]+)/.exec(magic.headers.get("Set-Cookie") || "")![1]);
    expect((await verifyJwt(magicTok, SECRET)).claims?.v).toBe(1);
  });

  it("GET /api/account with a form cookie shows nothing of a paying member's record", async () => {
    const env = envWith();
    paidMember(env, "victim@example.com");
    const res = await handleAccount(req("/api/account", {
      headers: { Cookie: await cookie("victim@example.com") } }), env);
    expect(res.status).toBe(200);
    const body = await res.json() as any;
    expect(body.verify_required).toBe(true);
    expect(body.member).toBeNull();
    const text = JSON.stringify(body);
    for (const secret of [TOKEN, "Dana", "Halifax", "fusion", "drones", "active", "personal\""]) {
      expect(text).not.toContain(secret);
    }
  });

  it("a verified session sees the same record in full", async () => {
    const env = envWith();
    paidMember(env, "victim@example.com");
    const res = await handleAccount(req("/api/account", {
      headers: { Cookie: await cookie("victim@example.com", { verified: true }) } }), env);
    const body = await res.json() as any;
    expect(body.verify_required).toBeUndefined();
    expect(body.member.feed_url).toContain(TOKEN);
    expect(body.member.preferences.profile).toBe("I fly drones.");
  });

  it("a form cookie cannot change a paying member's lineup", async () => {
    const env = envWith();
    paidMember(env, "victim@example.com");
    const before = (env.RATE_LIMIT_KV as unknown as FakeKV).store.get("member:victim@example.com");
    const res = await handlePreferences(req("/api/account/preferences", {
      method: "POST", body: JSON.stringify({ shows: ["dp_pod", "mag7"] }),
      headers: { Cookie: await cookie("victim@example.com") },
    }), env);
    expect(res.status).toBe(403);
    expect(((await res.json()) as any).error).toBe("verify_required");
    expect((env.RATE_LIMIT_KV as unknown as FakeKV).store.get("member:victim@example.com"))
      .toBe(before);
  });

  it("billing is never opened to a form cookie", async () => {
    const env = envWith({ STRIPE_SECRET_KEY: "sk_test" });
    paidMember(env, "victim@example.com");
    const res = await handlePortal(req("/api/account/portal", {
      method: "POST", headers: { Cookie: await cookie("victim@example.com") } }), env);
    expect(res.status).toBe(403);
  });

  it("a new account can pick shows straight after signing up, and only that session can", async () => {
    const env = envWith();
    const t0 = Math.floor(Date.now() / 1000) - 600;
    const mine = await cookie("new@example.com", { now: t0 });
    const first = await handlePreferences(req("/api/account/preferences", {
      method: "POST", body: JSON.stringify({ shows: ["spacex", "tesla"] }),
      headers: { Cookie: mine } }), env);
    expect(first.status).toBe(200);
    const again = await handlePreferences(req("/api/account/preferences", {
      method: "POST", body: JSON.stringify({ shows: ["spacex", "mag7"] }),
      headers: { Cookie: mine } }), env);
    expect(again.status).toBe(200);
    // Another form cookie for the same address (another visitor) is refused.
    const other = await cookie("new@example.com", { now: t0 + 300 });
    const theirs = await handlePreferences(req("/api/account/preferences", {
      method: "POST", body: JSON.stringify({ shows: ["dp_pod", "mag7"] }),
      headers: { Cookie: other } }), env);
    expect(theirs.status).toBe(403);
  });

  it("mayUseRecord: verified always; nothing private yet; paid needs verified", () => {
    const sess = { email: "a@b.co", verified: false, iat: 10 };
    expect(mayUseRecord({ ...sess, verified: true }, { status: "active" } as any)).toBe(true);
    expect(mayUseRecord(sess, null)).toBe(true);
    expect(mayUseRecord(sess, { status: "active", feed_token: TOKEN } as any)).toBe(false);
    expect(mayUseRecord(sess, { status: "cancelled", feed_token: TOKEN } as any)).toBe(false);
    expect(mayUseRecord(sess, { status: "none", created_iat: 10 } as any)).toBe(true);
    expect(mayUseRecord(sess, { status: "none", created_iat: 11 } as any)).toBe(false);
    expect(mayUseRecord(sess, { status: "none" } as any)).toBe(false);
  });
});

describe("a paying member can always sign in", () => {
  it("sends the link to an address with a member record even when the newsletter list lacks it", async () => {
    const env = envWith();
    paidMember(env, "buyer@example.com");
    const deps = makeDeps(false);
    const res = await handleLogin(req("/api/login?email=buyer%40example.com"), env, deps);
    expect(res.status).toBe(200);
    expect(deps.resend.sendEmail).toHaveBeenCalledTimes(1);
  });

  it("still sends nothing to an address that is neither listed nor a member", async () => {
    const env = envWith();
    const deps = makeDeps(false);
    await handleLogin(req("/api/login?email=ghost%40example.com"), env, deps);
    expect(deps.resend.sendEmail).not.toHaveBeenCalled();
  });
});

describe("activation welcomes the member", () => {
  const checkout = (email: string) => ({
    type: "checkout.session.completed",
    data: { object: {
      metadata: { tier: "personal" }, customer_details: { email },
      subscription: "sub_new", customer: "cus_1",
    } },
  });

  it("writes a valid one-item feed and sends the welcome email with the feed URL", async () => {
    const env = envWith();
    const deps = makeDeps();
    const res = await webhook(env, checkout("buyer@example.com"), deps);
    expect(res.status).toBe(200);
    const rec = JSON.parse((env.RATE_LIMIT_KV as unknown as FakeKV)
      .store.get("member:buyer@example.com")!);
    const bucket = env.PERSONAL_BUCKET as unknown as SizedBucket;
    const xml = new TextDecoder().decode(
      bucket.objects.get(`personal/${rec.feed_token}/feed.rss`)!);
    expect(xml).toContain("<itunes:block>yes</itunes:block>");
    expect(xml).toContain('type="audio/mpeg"');
    expect(deps.resend.sendEmail).toHaveBeenCalledTimes(1);
    const mail = (deps.resend.sendEmail as any).mock.calls[0][2];
    expect(mail.to).toBe("buyer@example.com");
    expect(mail.text).toContain(`/api/feed/${rec.feed_token}/feed.rss`);
    expect(mail.text).toContain("/api/magic?token=");
  });

  it("never overwrites a feed the builder already wrote", async () => {
    const env = envWith();
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    kv.store.set("member:back@example.com", JSON.stringify({
      shows: [], first_name: "", city: "", tier: "personal", status: "cancelled",
      feed_token: TOKEN, updated_at: "" }));
    const bucket = env.PERSONAL_BUCKET as unknown as SizedBucket;
    bucket.objects.set(`personal/${TOKEN}/feed.rss`, new TextEncoder().encode("<rss>real</rss>"));
    await webhook(env, checkout("back@example.com"), makeDeps());
    expect(new TextDecoder().decode(bucket.objects.get(`personal/${TOKEN}/feed.rss`)!))
      .toBe("<rss>real</rss>");
  });

  it("the welcome feed escapes the name and keeps the private markers", () => {
    const xml = welcomeFeedXml(TOKEN, "A&B <x>");
    expect(xml).toContain("A&amp;B &lt;x&gt;'s Nerra Daily");
    expect(xml).toContain(`personal-${TOKEN.slice(0, 8)}-welcome`);
  });

  it("the welcome email escapes what it is given", () => {
    const mail = buildWelcomeEmail({
      firstName: "<b>Eve</b>", feedUrl: "https://x/feed.rss",
      signInUrl: "https://x/api/magic?token=a&b", signInHours: 24, firstEditionNow: false,
    });
    expect(mail.html).not.toContain("<b>Eve</b>");
    expect(mail.html).toContain("token=a&amp;b");
    expect(mail.text).toContain("next morning");
  });
});

describe("cancelling one plan never cancels the other", () => {
  it("a deleted, superseded subscription leaves the membership and the feed alone", async () => {
    const env = envWith();
    paidMember(env, "up@example.com", { sub_id: "sub_new" });
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    kv.store.set("sub:sub_old", "up@example.com");
    await webhook(env, { type: "customer.subscription.deleted",
      data: { object: { id: "sub_old" } } });
    expect(JSON.parse(kv.store.get("member:up@example.com")!).status).toBe("active");
    expect(kv.store.get(`feedtok:${TOKEN}`)).toBe("up@example.com");
  });

  it("deleting the CURRENT subscription still cancels", async () => {
    const env = envWith();
    paidMember(env, "up@example.com", { sub_id: "sub_new" });
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    kv.store.set("sub:sub_new", "up@example.com");
    await webhook(env, { type: "customer.subscription.deleted",
      data: { object: { id: "sub_new" } } });
    expect(JSON.parse(kv.store.get("member:up@example.com")!).status).toBe("cancelled");
    expect(kv.store.get(`feedtok:${TOKEN}`)).toBeUndefined();
  });

  it("a superseded subscription going unpaid does not revoke the feed", async () => {
    const env = envWith();
    paidMember(env, "up@example.com", { sub_id: "sub_new" });
    const kv = env.RATE_LIMIT_KV as unknown as FakeKV;
    kv.store.set("sub:sub_old", "up@example.com");
    await webhook(env, { type: "customer.subscription.updated",
      data: { object: { id: "sub_old", status: "unpaid" } } });
    expect(JSON.parse(kv.store.get("member:up@example.com")!).status).toBe("active");
  });
});

describe("the private feed streams like a podcast host", () => {
  function withAudio(env: Env) {
    paidMember(env, "m@example.com");
    const bucket = env.PERSONAL_BUCKET as unknown as SizedBucket;
    bucket.objects.set(`personal/${TOKEN}/ep.mp3`,
      new Uint8Array(Array.from({ length: 1000 }, (_, i) => i % 256)));
  }

  it("HEAD answers with the length and no body", async () => {
    const env = envWith();
    withAudio(env);
    const res = await handlePersonalFeed(req(`/api/feed/${TOKEN}/ep.mp3`, { method: "HEAD" }),
      env, TOKEN, "ep.mp3");
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Length")).toBe("1000");
    expect(res.headers.get("Accept-Ranges")).toBe("bytes");
    expect(res.body).toBeNull();
  });

  it("a byte range is a 206 with Content-Range and only those bytes", async () => {
    const env = envWith();
    withAudio(env);
    const res = await handlePersonalFeed(req(`/api/feed/${TOKEN}/ep.mp3`, {
      headers: { Range: "bytes=10-19" } }), env, TOKEN, "ep.mp3");
    expect(res.status).toBe(206);
    expect(res.headers.get("Content-Range")).toBe("bytes 10-19/1000");
    const bytes = new Uint8Array(await res.arrayBuffer());
    expect(bytes.length).toBe(10);
    expect(bytes[0]).toBe(10);
  });

  it("an open-ended and a suffix range resolve against the size; past the end is 416", async () => {
    const env = envWith();
    withAudio(env);
    const tail = await handlePersonalFeed(req(`/api/feed/${TOKEN}/ep.mp3`, {
      headers: { Range: "bytes=-100" } }), env, TOKEN, "ep.mp3");
    expect(tail.headers.get("Content-Range")).toBe("bytes 900-999/1000");
    const open = await handlePersonalFeed(req(`/api/feed/${TOKEN}/ep.mp3`, {
      headers: { Range: "bytes=990-" } }), env, TOKEN, "ep.mp3");
    expect(open.headers.get("Content-Range")).toBe("bytes 990-999/1000");
    const past = await handlePersonalFeed(req(`/api/feed/${TOKEN}/ep.mp3`, {
      headers: { Range: "bytes=5000-6000" } }), env, TOKEN, "ep.mp3");
    expect(past.status).toBe(416);
    expect(past.headers.get("Content-Range")).toBe("bytes */1000");
  });

  it("a full GET still returns the whole file with its length", async () => {
    const env = envWith();
    withAudio(env);
    const res = await handlePersonalFeed(req(`/api/feed/${TOKEN}/ep.mp3`), env, TOKEN, "ep.mp3");
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Length")).toBe("1000");
    expect((await res.arrayBuffer()).byteLength).toBe(1000);
  });

  it("parseByteRange / resolveRange", () => {
    expect(parseByteRange(null)).toBeNull();
    expect(parseByteRange("bytes=0-0,5-6")).toBeNull();
    expect(parseByteRange("bytes=5-1")).toBeNull();
    expect(parseByteRange("bytes=2-4")).toEqual({ offset: 2, length: 3 });
    expect(resolveRange({ offset: 2, length: 3 }, 10)).toEqual({ start: 2, end: 4 });
    expect(resolveRange({ suffix: 0 }, 10)).toBeNull();
    expect(resolveRange({ offset: 0, length: 50 }, 10)).toEqual({ start: 0, end: 9 });
  });
});

describe("today is the Eastern date", () => {
  it("an evening in Eastern time is still that day, though UTC has moved on", async () => {
    const { todayIso } = await import("../src/build");
    // 23:30 UTC on Oct 28 = 7:30 pm EDT, Oct 28.
    expect(todayIso(new Date("2026-10-28T23:30:00Z"))).toBe("2026-10-28");
    // 01:30 UTC on Oct 29 = 9:30 pm EDT, Oct 28 — the UTC date said the 29th.
    expect(todayIso(new Date("2026-10-29T01:30:00Z"))).toBe("2026-10-28");
    // After 4 am Eastern the dates agree again.
    expect(todayIso(new Date("2026-10-29T09:00:00Z"))).toBe("2026-10-29");
    // Winter (EST, UTC-5).
    expect(todayIso(new Date("2026-12-02T04:30:00Z"))).toBe("2026-12-01");
  });
});
