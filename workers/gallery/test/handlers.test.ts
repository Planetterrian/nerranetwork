/**
 * Endpoint-level tests with fake Buttondown + Resend clients and a
 * tiny in-memory R2 bucket. Exercises the full request/response
 * surface without hitting the network.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  handleDownload,
  handleLogin,
  handleMagic,
  handleSubscribe,
  isSafeKey,
  normaliseEmail,
} from "../src/handlers";
import { signJwt } from "../src/jwt";
import type { ButtondownClient, Env, HandlerDeps, ResendClient } from "../src/types";

const SECRET = "test-secret-not-for-production-use";

function makeEnv(overrides: Partial<Env> = {}): Env {
  return {
    GALLERY_BUCKET: makeBucket(),
    JWT_SECRET: SECRET,
    BUTTONDOWN_API_KEY: "fake-bd",
    RESEND_API_KEY: "fake-rs",
    RESEND_FROM_EMAIL: "gallery@nerranetwork.com",
    ...overrides,
  };
}

function makeBucket(contents: Record<string, Uint8Array | null> = {}): R2Bucket {
  return {
    async get(key: string) {
      const data = contents[key];
      if (data === undefined || data === null) return null;
      return {
        body: new Response(data).body,
        httpEtag: '"fake"',
        writeHttpMetadata(headers: Headers) {
          headers.set("Content-Type", "image/jpeg");
        },
      } as unknown as R2ObjectBody;
    },
  } as unknown as R2Bucket;
}

function makeDeps(overrides: Partial<HandlerDeps> = {}): HandlerDeps {
  const buttondown: ButtondownClient = {
    subscribe: vi.fn(async () => ({ ok: true, alreadySubscribed: false, status: 201 })),
    isSubscribed: vi.fn(async () => ({ ok: true, exists: true, status: 200 })),
  };
  const resend: ResendClient = {
    sendEmail: vi.fn(async () => ({ ok: true, id: "msg_1", status: 200 })),
  };
  return { buttondown, resend, ...overrides };
}

function makeRequest(method: string, url: string, init: RequestInit = {}): Request {
  const headers = new Headers(init.headers);
  headers.set("Origin", "https://nerranetwork.com");
  return new Request(url, { method, ...init, headers });
}


beforeEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

describe("normaliseEmail", () => {
  it("lowercases and trims", () => {
    expect(normaliseEmail("  Alice@Example.COM ")).toBe("alice@example.com");
  });
  it("rejects garbage", () => {
    expect(normaliseEmail("")).toBeNull();
    expect(normaliseEmail("not-an-email")).toBeNull();
    expect(normaliseEmail("a@b")).toBeNull();
    expect(normaliseEmail(null)).toBeNull();
    expect(normaliseEmail(undefined)).toBeNull();
    expect(normaliseEmail(42)).toBeNull();
  });
});

describe("isSafeKey", () => {
  it("accepts the bucket layout", () => {
    expect(isSafeKey("tesla/2026-05-24/ep042/abc123def456.jpeg")).toBe(true);
    expect(isSafeKey("models_agents_beginners/2026-05-24/ep017/img.thumb.webp")).toBe(true);
  });
  it("rejects traversal + absolute paths + empties", () => {
    expect(isSafeKey("")).toBe(false);
    expect(isSafeKey("/etc/passwd")).toBe(false);
    expect(isSafeKey("../escape")).toBe(false);
    expect(isSafeKey("a//b")).toBe(false);
    expect(isSafeKey("a/../b")).toBe(false);
    expect(isSafeKey("a b")).toBe(false);
    expect(isSafeKey("a?b")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// /api/subscribe
// ---------------------------------------------------------------------------

describe("POST /api/subscribe", () => {
  it("subscribes and sets the cookie on success", async () => {
    const deps = makeDeps();
    const env = makeEnv();
    const req = makeRequest("POST", "https://api.nerranetwork.com/api/subscribe", {
      body: JSON.stringify({ email: "Alice@Example.com" }),
      headers: { "Content-Type": "application/json" },
    });
    const resp = await handleSubscribe(req, env, deps);
    expect(resp.status).toBe(200);
    expect(deps.buttondown.subscribe).toHaveBeenCalledWith(
      "fake-bd", "alice@example.com", "gallery-subscriber",
    );
    const setCookie = resp.headers.get("Set-Cookie");
    expect(setCookie).toMatch(/^nn_gallery=/);
    expect(setCookie).toContain("HttpOnly");
    expect(setCookie).toContain("Secure");
    expect(setCookie).toContain("SameSite=Lax");
    expect(setCookie).toContain("Path=/");
    expect(resp.headers.get("Access-Control-Allow-Origin"))
      .toBe("https://nerranetwork.com");
    expect(resp.headers.get("Access-Control-Allow-Credentials")).toBe("true");
  });

  it("400s on invalid JSON", async () => {
    const req = makeRequest("POST", "https://api.nerranetwork.com/api/subscribe", {
      body: "not json",
      headers: { "Content-Type": "application/json" },
    });
    const resp = await handleSubscribe(req, makeEnv(), makeDeps());
    expect(resp.status).toBe(400);
  });

  it("400s on bad email", async () => {
    const req = makeRequest("POST", "https://api.nerranetwork.com/api/subscribe", {
      body: JSON.stringify({ email: "garbage" }),
      headers: { "Content-Type": "application/json" },
    });
    const resp = await handleSubscribe(req, makeEnv(), makeDeps());
    expect(resp.status).toBe(400);
  });

  it("502s when Buttondown fails — without leaking detail", async () => {
    const deps = makeDeps({
      buttondown: {
        subscribe: vi.fn(async () => ({ ok: false, alreadySubscribed: false, error: "BUTTONDOWN_HTTP_500" })),
        isSubscribed: vi.fn(),
      },
    });
    const req = makeRequest("POST", "https://api.nerranetwork.com/api/subscribe", {
      body: JSON.stringify({ email: "alice@example.com" }),
      headers: { "Content-Type": "application/json" },
    });
    const resp = await handleSubscribe(req, makeEnv(), deps);
    expect(resp.status).toBe(502);
    const body = await resp.json();
    expect(body).toEqual({ ok: false, error: "subscribe failed" });
    // Must not leak upstream error code to the client.
    expect(JSON.stringify(body)).not.toContain("BUTTONDOWN");
  });

  it("treats already-subscribed as success", async () => {
    const deps = makeDeps({
      buttondown: {
        subscribe: vi.fn(async () => ({ ok: true, alreadySubscribed: true, status: 400 })),
        isSubscribed: vi.fn(),
      },
    });
    const req = makeRequest("POST", "https://api.nerranetwork.com/api/subscribe", {
      body: JSON.stringify({ email: "alice@example.com" }),
      headers: { "Content-Type": "application/json" },
    });
    const resp = await handleSubscribe(req, makeEnv(), deps);
    expect(resp.status).toBe(200);
    const body = await resp.json() as { alreadySubscribed: boolean };
    expect(body.alreadySubscribed).toBe(true);
    expect(resp.headers.get("Set-Cookie")).toMatch(/^nn_gallery=/);
  });
});

// ---------------------------------------------------------------------------
// /api/login
// ---------------------------------------------------------------------------

describe("GET /api/login", () => {
  it("emails a magic link when the address is subscribed", async () => {
    const deps = makeDeps();
    const req = makeRequest(
      "GET",
      "https://api.nerranetwork.com/api/login?email=alice%40example.com",
    );
    const resp = await handleLogin(req, makeEnv(), deps);
    expect(resp.status).toBe(200);
    expect(deps.resend.sendEmail).toHaveBeenCalledOnce();
    const args = (deps.resend.sendEmail as any).mock.calls[0];
    expect(args[2].to).toBe("alice@example.com");
    expect(args[2].subject).toMatch(/sign in/i);
    expect(args[2].html).toContain("https://api.nerranetwork.com/api/magic?token=");
  });

  it("returns the same 200 when the address is NOT subscribed (enumeration-safe)", async () => {
    const deps = makeDeps({
      buttondown: {
        subscribe: vi.fn(),
        isSubscribed: vi.fn(async () => ({ ok: true, exists: false, status: 200 })),
      },
    });
    const req = makeRequest(
      "GET",
      "https://api.nerranetwork.com/api/login?email=ghost%40example.com",
    );
    const resp = await handleLogin(req, makeEnv(), deps);
    expect(resp.status).toBe(200);
    expect(deps.resend.sendEmail).not.toHaveBeenCalled();
    const body = await resp.json();
    expect(body).toEqual({ ok: true });
  });

  it("400s on invalid email", async () => {
    const req = makeRequest("GET", "https://api.nerranetwork.com/api/login?email=garbage");
    const resp = await handleLogin(req, makeEnv(), makeDeps());
    expect(resp.status).toBe(400);
  });

  it("still returns 200 when the upstream lookup errors (no enumeration via timing)", async () => {
    const deps = makeDeps({
      buttondown: {
        subscribe: vi.fn(),
        isSubscribed: vi.fn(async () => ({ ok: false, exists: false, error: "BUTTONDOWN_DOWN" })),
      },
    });
    const req = makeRequest(
      "GET",
      "https://api.nerranetwork.com/api/login?email=alice%40example.com",
    );
    const resp = await handleLogin(req, makeEnv(), deps);
    expect(resp.status).toBe(200);
    expect(deps.resend.sendEmail).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// /api/magic
// ---------------------------------------------------------------------------

describe("GET /api/magic", () => {
  it("302s to /gallery.html and sets the subscriber cookie", async () => {
    const env = makeEnv();
    const token = await signJwt(
      { sub: "alice@example.com", scope: "magic-login", ttlSeconds: 600 },
      SECRET,
    );
    const req = makeRequest(
      "GET",
      `https://api.nerranetwork.com/api/magic?token=${encodeURIComponent(token)}`,
    );
    const resp = await handleMagic(req, env, makeDeps());
    expect(resp.status).toBe(302);
    expect(resp.headers.get("Location")).toBe("https://nerranetwork.com/gallery.html");
    const setCookie = resp.headers.get("Set-Cookie");
    expect(setCookie).toMatch(/^nn_gallery=/);
    expect(setCookie).toContain("HttpOnly");
    expect(setCookie).toContain("Secure");
    expect(setCookie).toContain("Max-Age=7776000"); // 90 d
  });

  it("400s on missing token", async () => {
    const req = makeRequest("GET", "https://api.nerranetwork.com/api/magic");
    const resp = await handleMagic(req, makeEnv(), makeDeps());
    expect(resp.status).toBe(400);
  });

  it("400s on expired token", async () => {
    const env = makeEnv();
    const now = Math.floor(Date.now() / 1000);
    const token = await signJwt(
      { sub: "alice@example.com", scope: "magic-login", ttlSeconds: 60 },
      SECRET,
      now - 3600,
    );
    const req = makeRequest(
      "GET",
      `https://api.nerranetwork.com/api/magic?token=${encodeURIComponent(token)}`,
    );
    const resp = await handleMagic(req, env, makeDeps());
    expect(resp.status).toBe(400);
  });

  it("400s when the token has the wrong scope (cookie token replayed as magic)", async () => {
    const env = makeEnv();
    const cookieToken = await signJwt(
      { sub: "alice@example.com", scope: "gallery-subscriber", ttlSeconds: 600 },
      SECRET,
    );
    const req = makeRequest(
      "GET",
      `https://api.nerranetwork.com/api/magic?token=${encodeURIComponent(cookieToken)}`,
    );
    const resp = await handleMagic(req, env, makeDeps());
    expect(resp.status).toBe(400);
  });
});

// ---------------------------------------------------------------------------
// /api/download
// ---------------------------------------------------------------------------

describe("GET /api/download", () => {
  it("streams the R2 object when the JWT cookie is valid", async () => {
    const bytes = new Uint8Array([0xde, 0xad, 0xbe, 0xef]);
    const env = makeEnv({
      GALLERY_BUCKET: makeBucket({
        "tesla/2026-05-24/ep042/abc.jpeg": bytes,
      }),
    });
    const cookie = await signJwt(
      { sub: "alice@example.com", scope: "gallery-subscriber", ttlSeconds: 600 },
      SECRET,
    );
    const req = makeRequest(
      "GET",
      "https://api.nerranetwork.com/api/download?key=tesla/2026-05-24/ep042/abc.jpeg",
      { headers: { Cookie: `nn_gallery=${cookie}` } },
    );
    const resp = await handleDownload(req, env, makeDeps());
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Content-Disposition")).toContain("attachment");
    expect(resp.headers.get("Content-Disposition")).toContain("abc.jpeg");
    const body = new Uint8Array(await resp.arrayBuffer());
    expect(Array.from(body)).toEqual(Array.from(bytes));
  });

  it("401s when no cookie present", async () => {
    const req = makeRequest(
      "GET",
      "https://api.nerranetwork.com/api/download?key=tesla/2026-05-24/ep042/abc.jpeg",
    );
    const resp = await handleDownload(req, makeEnv(), makeDeps());
    expect(resp.status).toBe(401);
  });

  it("401s when cookie token has the wrong scope", async () => {
    const env = makeEnv();
    const magicToken = await signJwt(
      { sub: "alice@example.com", scope: "magic-login", ttlSeconds: 600 },
      SECRET,
    );
    const req = makeRequest(
      "GET",
      "https://api.nerranetwork.com/api/download?key=tesla/2026-05-24/ep042/abc.jpeg",
      { headers: { Cookie: `nn_gallery=${magicToken}` } },
    );
    const resp = await handleDownload(req, env, makeDeps());
    expect(resp.status).toBe(401);
  });

  it("400s on traversal attempt", async () => {
    const cookie = await signJwt(
      { sub: "x@y.z", scope: "gallery-subscriber", ttlSeconds: 600 },
      SECRET,
    );
    const req = makeRequest(
      "GET",
      "https://api.nerranetwork.com/api/download?key=../etc/passwd",
      { headers: { Cookie: `nn_gallery=${cookie}` } },
    );
    const resp = await handleDownload(req, makeEnv(), makeDeps());
    expect(resp.status).toBe(400);
  });

  it("404s when the object is missing from R2", async () => {
    const cookie = await signJwt(
      { sub: "x@y.z", scope: "gallery-subscriber", ttlSeconds: 600 },
      SECRET,
    );
    const req = makeRequest(
      "GET",
      "https://api.nerranetwork.com/api/download?key=tesla/2026-05-24/ep042/missing.jpeg",
      { headers: { Cookie: `nn_gallery=${cookie}` } },
    );
    const resp = await handleDownload(req, makeEnv(), makeDeps());
    expect(resp.status).toBe(404);
  });
});
