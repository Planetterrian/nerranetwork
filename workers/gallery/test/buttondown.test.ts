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

  it("includes optional metadata when provided", async () => {
    const fetchSpy = mockFetch(async (_url, init) => {
      const body = JSON.parse(init?.body as string);
      expect(body.metadata).toEqual({ first_name: "Pat" });
      return new Response("", { status: 201 });
    });
    const result = await subscribe(
      "abc", "pat@example.com", ["personal-interest"], { first_name: "Pat" });
    expect(result.ok).toBe(true);
    expect(fetchSpy).toHaveBeenCalledOnce();
  });

  it("omits metadata from the body when none is given", async () => {
    mockFetch(async (_url, init) => {
      const body = JSON.parse(init?.body as string);
      expect(body.metadata).toBeUndefined();
      return new Response("", { status: 201 });
    });
    await subscribe("abc", "alice@example.com", "gallery-subscriber");
  });

  it("treats 400 'already exists' as success", async () => {
    mockFetch(async () => new Response("already subscribed", { status: 400 }));
    const result = await subscribe("abc", "alice@example.com", "gallery-subscriber");
    expect(result.ok).toBe(true);
    expect(result.alreadySubscribed).toBe(true);
  });

  it("merges tags onto a subscriber who already exists", async () => {
    // Before Sep 2026 the duplicate branch returned here, so tags were
    // applied on CREATE only: an address already on the list could never
    // acquire `nerra-member`, a show tag or a `src-*` source however many
    // times they resubmitted the form.
    const calls: { url: string; init?: any }[] = [];
    mockFetch(async (url, init) => {
      const u = String(url);
      calls.push({ url: u, init });
      if (init?.method === "POST") {
        return new Response("subscriber already exists", { status: 400 });
      }
      if (init?.method === "PATCH") return new Response("{}", { status: 200 });
      return new Response(JSON.stringify({
        results: [{ id: "sub_1", tags: ["Tesla Shorts Time"] }],
      }), { status: 200 });
    });

    const result = await subscribe("abc", "alice@example.com",
      ["nerra-member", "src-nerranetwork"]);

    expect(result.ok).toBe(true);
    expect(result.alreadySubscribed).toBe(true);
    expect(result.tagsMerged).toEqual(["nerra-member", "src-nerranetwork"]);

    const patch = calls.find((c) => c.init?.method === "PATCH")!;
    expect(patch.url).toBe("https://api.buttondown.email/v1/subscribers/sub_1");
    // A union, never a replace: PATCH overwrites the array, so dropping the
    // existing show tag here would unsubscribe them from that newsletter.
    expect(JSON.parse(patch.init.body).tags).toEqual([
      "Tesla Shorts Time", "nerra-member", "src-nerranetwork",
    ]);
  });

  it("does not PATCH when the subscriber already carries every tag", async () => {
    const methods: string[] = [];
    mockFetch(async (url, init) => {
      methods.push(init?.method ?? "GET");
      if (init?.method === "POST") {
        return new Response("already present", { status: 400 });
      }
      return new Response(JSON.stringify({
        results: [{ id: "sub_1", tags: ["Nerra-Member"] }],
      }), { status: 200 });
    });
    const result = await subscribe("abc", "alice@example.com", "nerra-member");
    expect(result.tagsMerged).toEqual([]);      // nothing to add
    expect(methods).not.toContain("PATCH");     // case-insensitive match
  });

  it("still reports success when the tag merge fails", async () => {
    // An attribution tag is not worth a 502 on someone's signup.
    mockFetch(async (url, init) => {
      if (init?.method === "POST") {
        return new Response("already exists", { status: 400 });
      }
      return new Response("nope", { status: 500 });
    });
    const result = await subscribe("abc", "alice@example.com", "nerra-member");
    expect(result.ok).toBe(true);
    expect(result.alreadySubscribed).toBe(true);
    expect(result.tagsMerged).toBeNull();
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
