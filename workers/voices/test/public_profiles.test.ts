import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker, {
  PUBLIC_PROFILE_REQUIRED, applicationLinks, normaliseCompanyProfile, normaliseLinkedIn,
  normaliseX, profilesHtml, publicProfiles,
} from "../src/index";

// Oct 25 2026 — every guest application names at least one public profile
// (an X account, a LinkedIn profile, or the guest's page on their company's
// site), so the applicant can be checked against something they did not
// write for us and the episode page can link to them with their photo.

type Call = { method: string; url: string; body: any };

function env(): any {
  return {
    SUPABASE_URL: "https://sb.test", SUPABASE_SERVICE_KEY: "svc",
    GITHUB_DISPATCH_TOKEN: "gh", ADMIN_TOKEN: "admin-token-admin-token",
    RESEND_API_KEY: "re", VOICES_FROM_EMAIL: "mira@nerranetwork.com",
  };
}

function fakeFetch(respond: (c: Call) => any) {
  const calls: Call[] = [];
  const fn = vi.fn(async (input: any, init?: any) => {
    const url = typeof input === "string" ? input : input.url;
    const method = (init?.method ?? "GET").toUpperCase();
    let body: any = null;
    if (init?.body && typeof init.body === "string") {
      try { body = JSON.parse(init.body); } catch { body = init.body; }
    }
    const call = { method, url, body };
    calls.push(call);
    if (url.endsWith("/dispatches")) return new Response(null, { status: 204 });
    if (url.startsWith("https://api.resend.com/")) return new Response("{}", { status: 200 });
    return new Response(JSON.stringify(respond(call) ?? []), { status: 200 });
  });
  return { fn, calls };
}

const apply = (body: unknown) => new Request("https://api.nerranetwork.com/voices/apply", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});
const base = { name: "Piper Martz", email: "piper@example.com", bio: "I run Aampe.", topics: ["agents"],
  show: "nerra_voices" };
const sbTable = (url: string) => url.replace("https://sb.test/rest/v1/", "").split("?")[0];

beforeEach(() => { vi.restoreAllMocks(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe("reading the three profiles", () => {
  it("X: a handle, with or without @, or a profile link, becomes https://x.com/<handle>", () => {
    for (const raw of ["@pipermartz", "pipermartz", "x.com/pipermartz", "https://twitter.com/pipermartz?s=21",
                       "https://mobile.x.com/pipermartz/"]) {
      expect(normaliseX(raw)).toEqual({ url: "https://x.com/pipermartz", error: null });
    }
    expect(normaliseX("").url).toBeNull();
    expect(normaliseX("").error).toBeNull();
    expect(normaliseX("https://x.com/home").error).toMatch(/X account/);
    expect(normaliseX("piper martz").error).toMatch(/X account/);
    expect(normaliseX("https://example.com/piper").error).toMatch(/X account/);
  });

  it("LinkedIn: only a personal profile, tracking stripped", () => {
    expect(normaliseLinkedIn("linkedin.com/in/piper-martz").url).toBe("https://www.linkedin.com/in/piper-martz");
    expect(normaliseLinkedIn("https://ca.linkedin.com/in/piper-martz/?originalSubdomain=ca").url)
      .toBe("https://www.linkedin.com/in/piper-martz");
    expect(normaliseLinkedIn("https://www.linkedin.com/company/aampe").error).toMatch(/\/in\//);
    expect(normaliseLinkedIn("https://example.com/in/piper").error).toMatch(/\/in\//);
  });

  it("company profile: any page on their own site, not a social network", () => {
    expect(normaliseCompanyProfile("aampe.com/team/piper#top").url).toBe("https://aampe.com/team/piper");
    expect(normaliseCompanyProfile("https://www.facebook.com/aampe").error).toMatch(/company's own website/);
    expect(normaliseCompanyProfile("not a link").error).toMatch(/web address/);
  });
});

describe("at least one is required", () => {
  it("none at all is refused with the sentence the form shows", () => {
    expect(publicProfiles({ links: { raw: "aampe.com" } }).error).toBe(PUBLIC_PROFILE_REQUIRED);
    expect(publicProfiles({}).error).toBe(PUBLIC_PROFILE_REQUIRED);
  });

  it("one good one is enough; a bad one is named even beside a good one", () => {
    expect(publicProfiles({ links: { linkedin: "linkedin.com/in/piper" } }).error).toBeNull();
    const r = publicProfiles({ links: { linkedin: "linkedin.com/in/piper", x: "https://x.com/home" } });
    expect(r.error).toMatch(/X account/);
  });

  it("a LinkedIn or X link in the wrong box, or in the old free-text box, is moved, not refused", () => {
    expect(publicProfiles({ links: { company_profile: "https://www.linkedin.com/in/piper" } }))
      .toEqual({ profiles: { x: null, linkedin: "https://www.linkedin.com/in/piper", company_profile: null }, error: null });
    // an apply page cached from before Oct 25 posts one free-text box
    const old = publicProfiles({ links: { raw: "aampe.com, https://x.com/pipermartz" } });
    expect(old.error).toBeNull();
    expect(old.profiles.x).toBe("https://x.com/pipermartz");
  });

  it("the links column keeps the profiles under their own keys and the rest as text", () => {
    const { profiles } = publicProfiles({ links: { x: "@pipermartz", company_profile: "aampe.com/team/piper",
      raw: "aampe.com" } });
    expect(applicationLinks(profiles, { raw: "aampe.com" })).toEqual({
      x: "https://x.com/pipermartz", company_profile: "https://aampe.com/team/piper", raw: "aampe.com" });
  });
});

describe("POST /voices/apply", () => {
  it("is a 400 naming what is missing, and stores nothing", async () => {
    const { fn, calls } = fakeFetch(() => []);
    vi.stubGlobal("fetch", fn);
    const res = await worker.route(apply({ ...base, links: { raw: "aampe.com" } }), env());
    expect(res.status).toBe(400);
    const body: any = await res.json();
    expect(body.field).toBe("public_profile");
    expect(body.error).toBe(PUBLIC_PROFILE_REQUIRED);
    expect(calls.length).toBe(0);
  });

  it("stores the profiles under links.x / links.linkedin / links.company_profile", async () => {
    const { fn, calls } = fakeFetch((c) => {
      if (c.method === "POST" && sbTable(c.url) === "guest_applications") return [{ id: "app-1" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const res = await worker.route(apply({ ...base, links: {
      x: "@pipermartz", linkedin: "https://www.linkedin.com/in/piper-martz/", company_profile: "", raw: "aampe.com" } }), env());
    expect(res.status).toBe(200);
    const insert = calls.find((c) => c.method === "POST" && sbTable(c.url) === "guest_applications");
    expect(insert?.body.links).toEqual({
      x: "https://x.com/pipermartz", linkedin: "https://www.linkedin.com/in/piper-martz", raw: "aampe.com" });
  });

  it("completing an invited row keeps the pitch's links beside the form's", async () => {
    const { fn, calls } = fakeFetch((c) => {
      if (c.method === "GET" && sbTable(c.url) === "guest_applications") {
        return [{ id: "inv-1", show: "nerra_voices", links: { urls: ["https://aampe.com"] } }];
      }
      if (c.method === "PATCH") return [{ id: "inv-1" }];
      return [];
    });
    vi.stubGlobal("fetch", fn);
    const res = await worker.route(apply({ ...base, links: { linkedin: "linkedin.com/in/piper-martz" } }), env());
    expect(res.status).toBe(200);
    const patch = calls.find((c) => c.method === "PATCH" && sbTable(c.url) === "guest_applications");
    expect(patch?.body.links).toEqual({ urls: ["https://aampe.com"], linkedin: "https://www.linkedin.com/in/piper-martz" });
  });
});

describe("what Patrick sees", () => {
  it("the triage row shows the profiles and the photo, or says none was given", () => {
    const html = profilesHtml({ links: { x: "https://x.com/pipermartz" },
      profile_photo_url: "https://audio.nerranetwork.com/voices/guests/a/photo-1.jpg" });
    expect(html).toContain('href="https://x.com/pipermartz"');
    expect(html).toContain("photo-1.jpg");
    expect(profilesHtml({ links: { urls: ["https://aampe.com"] } })).toMatch(/No public profile given/);
  });
});
