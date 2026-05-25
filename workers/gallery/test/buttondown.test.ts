/**
 * Buttondown client tests — mocks `fetch` globally so we don't hit
 * the real API.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { isSubscribed, subscribe } from "../src/buttondown";


function mockFetch(impl: (input: any, init?: any) => Promise<Response> | Response) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(impl as any);
}

afterEach(() => {
  vi.restoreAllMocks();
});


describe("subscribe()", () => {
  it("sends a JSON POST with the Token auth header and tag", async () => {
    const fetchSpy = mockFetch(async (url, init) => {
      expect(String(url)).toBe("https://api.buttondown.email/v1/subscribers");
      expect(init?.method).toBe("POST");
      expect(init?.headers.Authorization).toBe("Token abc");
      const body = JSON.parse(init?.body as string);
      expect(body.email_address).toBe("alice@example.com");
      expect(body.tags).toEqual(["gallery-subscriber"]);
      return new Response("", { status: 201 });
    });
    const result = await subscribe("abc", "alice@example.com", "gallery-subscriber");
    expect(result.ok).toBe(true);
    expect(result.alreadySubscribed).toBe(false);
    expect(fetchSpy).toHaveBeenCalledOnce();
  });

  it("treats 400 'already exists' as success", async () => {
    mockFetch(async () => new Response("already subscribed", { status: 400 }));
    const result = await subscribe("abc", "alice@example.com", "gallery-subscriber");
    expect(result.ok).toBe(true);
    expect(result.alreadySubscribed).toBe(true);
  });

  it("surfaces HTTP error codes as BUTTONDOWN_HTTP_<code>", async () => {
    mockFetch(async () => new Response("server angry", { status: 500 }));
    const result = await subscribe("abc", "alice@example.com", "gallery-subscriber");
    expect(result.ok).toBe(false);
    expect(result.error).toBe("BUTTONDOWN_HTTP_500");
  });

  it("returns a BUTTONDOWN_DOWN error when fetch throws", async () => {
    mockFetch(async () => {
      throw new Error("network is unreachable");
    });
    const result = await subscribe("abc", "alice@example.com", "gallery-subscriber");
    expect(result.ok).toBe(false);
    expect(result.error).toContain("BUTTONDOWN_DOWN");
  });

  it("refuses to call without an api key", async () => {
    const spy = mockFetch(async () => new Response("", { status: 201 }));
    const result = await subscribe("", "x@y.z", "gallery-subscriber");
    expect(result.ok).toBe(false);
    expect(spy).not.toHaveBeenCalled();
  });
});


describe("isSubscribed()", () => {
  it("returns exists:true when results include the email case-insensitively", async () => {
    mockFetch(async () =>
      new Response(JSON.stringify({
        count: 1,
        results: [{ email_address: "Alice@Example.com" }],
      }), { status: 200 }),
    );
    const result = await isSubscribed("abc", "alice@example.com");
    expect(result.ok).toBe(true);
    expect(result.exists).toBe(true);
  });

  it("returns exists:false when results don't include the email", async () => {
    mockFetch(async () =>
      new Response(JSON.stringify({ count: 0, results: [] }), { status: 200 }),
    );
    const result = await isSubscribed("abc", "alice@example.com");
    expect(result.ok).toBe(true);
    expect(result.exists).toBe(false);
  });

  it("surfaces HTTP errors", async () => {
    mockFetch(async () => new Response("rate limited", { status: 429 }));
    const result = await isSubscribed("abc", "alice@example.com");
    expect(result.ok).toBe(false);
    expect(result.error).toBe("BUTTONDOWN_HTTP_429");
  });

  it("returns a BUTTONDOWN_DOWN error when fetch throws", async () => {
    mockFetch(async () => {
      throw new Error("network is unreachable");
    });
    const result = await isSubscribed("abc", "alice@example.com");
    expect(result.ok).toBe(false);
    expect(result.error).toContain("BUTTONDOWN_DOWN");
  });
});
