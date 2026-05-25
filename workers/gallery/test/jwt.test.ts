import { describe, expect, it } from "vitest";
import { base64UrlDecode, base64UrlEncode, signJwt, verifyJwt } from "../src/jwt";

const SECRET = "test-secret-not-for-production-use";

describe("base64url", () => {
  it("round-trips arbitrary bytes", () => {
    const bytes = new Uint8Array([0, 1, 2, 250, 251, 252, 253, 254, 255, 13, 10, 9, 32]);
    const encoded = base64UrlEncode(bytes);
    expect(encoded).not.toContain("+");
    expect(encoded).not.toContain("/");
    expect(encoded).not.toContain("=");
    expect(Array.from(base64UrlDecode(encoded))).toEqual(Array.from(bytes));
  });

  it("handles empty input", () => {
    expect(base64UrlEncode(new Uint8Array())).toBe("");
    expect(base64UrlDecode("").length).toBe(0);
  });

  it("decodes without padding", () => {
    // "M" → "TQ" (no padding) and "TQ==" (padded) decode to the same byte.
    expect(Array.from(base64UrlDecode("TQ"))).toEqual([0x4d]);
  });
});

describe("signJwt + verifyJwt", () => {
  it("produces a three-part token", async () => {
    const token = await signJwt(
      { sub: "alice@example.com", scope: "gallery-subscriber", ttlSeconds: 60 },
      SECRET,
    );
    expect(token.split(".").length).toBe(3);
  });

  it("round-trips claims via verifyJwt", async () => {
    const now = 1_700_000_000;
    const token = await signJwt(
      { sub: "alice@example.com", scope: "gallery-subscriber", ttlSeconds: 3600 },
      SECRET,
      now,
    );
    const verify = await verifyJwt(token, SECRET, { now: now + 10 });
    expect(verify.ok).toBe(true);
    expect(verify.claims?.sub).toBe("alice@example.com");
    expect(verify.claims?.scope).toBe("gallery-subscriber");
    expect(verify.claims?.iat).toBe(now);
    expect(verify.claims?.exp).toBe(now + 3600);
  });

  it("rejects expired tokens", async () => {
    const now = 1_700_000_000;
    const token = await signJwt(
      { sub: "x@y.z", scope: "magic-login", ttlSeconds: 60 },
      SECRET,
      now,
    );
    const verify = await verifyJwt(token, SECRET, { now: now + 61 });
    expect(verify.ok).toBe(false);
    expect(verify.reason).toBe("expired");
  });

  it("rejects tampered payload", async () => {
    const token = await signJwt(
      { sub: "alice@example.com", scope: "gallery-subscriber", ttlSeconds: 60 },
      SECRET,
    );
    const parts = token.split(".");
    // Re-encode a malicious payload but keep the original signature.
    const evilPayload = base64UrlEncode(
      new TextEncoder().encode(
        JSON.stringify({
          sub: "evil@attacker.com",
          scope: "gallery-subscriber",
          iat: 0,
          exp: 9_999_999_999,
        }),
      ),
    );
    const tampered = `${parts[0]}.${evilPayload}.${parts[2]}`;
    const verify = await verifyJwt(tampered, SECRET);
    expect(verify.ok).toBe(false);
    expect(verify.reason).toBe("signature mismatch");
  });

  it("rejects tokens signed with a different secret", async () => {
    const token = await signJwt(
      { sub: "alice@example.com", scope: "gallery-subscriber", ttlSeconds: 60 },
      "other-secret",
    );
    const verify = await verifyJwt(token, SECRET);
    expect(verify.ok).toBe(false);
    expect(verify.reason).toBe("signature mismatch");
  });

  it("rejects malformed tokens", async () => {
    const verify = await verifyJwt("not.a.real.jwt", SECRET);
    expect(verify.ok).toBe(false);
  });

  it("rejects empty token", async () => {
    expect((await verifyJwt("", SECRET)).ok).toBe(false);
  });

  it("rejects wrong scope when expectedScope is set", async () => {
    const now = 1_700_000_000;
    const token = await signJwt(
      { sub: "x@y.z", scope: "magic-login", ttlSeconds: 60 },
      SECRET,
      now,
    );
    const verify = await verifyJwt(token, SECRET, {
      expectedScope: "gallery-subscriber",
      now: now + 10,
    });
    expect(verify.ok).toBe(false);
    expect(verify.reason).toBe("wrong scope");
  });

  it("accepts matching scope", async () => {
    const now = 1_700_000_000;
    const token = await signJwt(
      { sub: "x@y.z", scope: "magic-login", ttlSeconds: 60 },
      SECRET,
      now,
    );
    const verify = await verifyJwt(token, SECRET, {
      expectedScope: "magic-login",
      now: now + 10,
    });
    expect(verify.ok).toBe(true);
  });

  it("rejects tokens issued in the future (beyond clock skew)", async () => {
    const now = 1_700_000_000;
    const token = await signJwt(
      { sub: "x@y.z", scope: "magic-login", ttlSeconds: 600 },
      SECRET,
      now + 120, // 2 min in the future
    );
    const verify = await verifyJwt(token, SECRET, { now });
    expect(verify.ok).toBe(false);
    expect(verify.reason).toBe("issued in future");
  });

  it("refuses to sign with empty secret", async () => {
    await expect(
      signJwt({ sub: "x@y.z", scope: "magic-login", ttlSeconds: 60 }, ""),
    ).rejects.toThrow();
  });
});
