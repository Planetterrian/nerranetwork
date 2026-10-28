import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker, {
  chunkExt, guestHasVideo, roomCountersOf, takeKind, videoTakeFor,
} from "../src/index";

// Oct 28 2026 — the guest's camera, recorded in the browser, and the room's
// own quiet research. A video take lives in its own lane beside the audio
// take and never moves the audio pointer the mix is built from; the review
// page lets a guest who was on camera publish audio only.

const RUN = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
const IV = "11111111-1111-1111-1111-111111111111";

type Call = { method: string; url: string; body: any };

function env(bucket: any): any {
  return {
    SUPABASE_URL: "https://sb.test", SUPABASE_SERVICE_KEY: "svc",
    ADMIN_TOKEN: "admin-token-admin-token", VOICES_R2: bucket,
  };
}

function fakeBucket() {
  const objects = new Map<string, { size: number; type: string }>();
  return {
    objects,
    async put(key: string, body: any, opts?: any) {
      const size = typeof body === "string" ? body.length : (body?.byteLength ?? 0);
      objects.set(key, { size, type: opts?.httpMetadata?.contentType ?? "" });
    },
    async head(key: string) {
      const o = objects.get(key);
      return o ? { size: o.size } : null;
    },
  };
}

function fakeSupabase(log: any = {}) {
  const calls: Call[] = [];
  const fn = vi.fn(async (input: any, init?: any) => {
    const url = typeof input === "string" ? input : input.url;
    const method = (init?.method ?? "GET").toUpperCase();
    let body: any = null;
    if (init?.body && typeof init.body === "string") {
      try { body = JSON.parse(init.body); } catch { body = init.body; }
    }
    calls.push({ method, url, body });
    if (method === "GET" && url.includes("interview_runs?") && url.includes("select=id,status")) {
      return new Response(JSON.stringify([{ id: RUN, status: "in_progress", interview_id: IV }]));
    }
    if (method === "GET" && url.includes("interviews?")) {
      return new Response(JSON.stringify([{ show: "age_of_ai", application_id: null }]));
    }
    if (method === "GET" && url.includes("select=grok_session_log")) {
      return new Response(JSON.stringify([{ grok_session_log: log }]));
    }
    return new Response("[]", { status: 200 });
  });
  return { fn, calls };
}

beforeEach(() => { vi.restoreAllMocks(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe("the video lane", () => {
  it("knows a video take from an audio one", () => {
    expect(takeKind("video")).toBe("video");
    expect(takeKind("audio")).toBe("audio");
    expect(takeKind(undefined)).toBe("audio");
    expect(takeKind("VIDEO")).toBe("audio");
    expect(chunkExt("video", "video/mp4;codecs=avc1")).toBe("mp4");
    expect(chunkExt("video", "video/webm;codecs=vp9,opus")).toBe("webm");
    expect(chunkExt("audio", "video/mp4")).toBe("webm");
  });

  it("records only the guest, and only on a run marked for it", () => {
    expect(videoTakeFor("guest", { local_video: true })).toBe(true);
    expect(videoTakeFor("host", { local_video: true })).toBe(false);
    expect(videoTakeFor("guest", { local_video: false })).toBe(false);
    expect(videoTakeFor("guest", {})).toBe(false);
    expect(videoTakeFor("guest", null)).toBe(false);
  });

  it("offers the audio-only choice only when there is a picture to leave out", () => {
    expect(guestHasVideo({ grok_session_log: { local_video_takes: { guest: [{ chunks: 12 }] } } })).toBe(true);
    expect(guestHasVideo({ grok_session_log: { local_video_takes: { guest: [{ chunks: 0 }] } } })).toBe(false);
    expect(guestHasVideo({ grok_session_log: { tracks: { video: { url: "https://x/y.mkv" } } } })).toBe(true);
    expect(guestHasVideo({ grok_session_log: {} })).toBe(false);
  });

  it("files a video chunk in the guest-video lane and refuses audio sent as video", async () => {
    const bucket = fakeBucket();
    const sb = fakeSupabase();
    vi.stubGlobal("fetch", sb.fn);
    const chunk = (type: string) => new Request(
      `https://api.nerranetwork.com/voices/upload-chunk?run_id=${RUN}&role=guest&seq=3&sid=v1abc&kind=video`,
      { method: "POST", headers: { "Content-Type": type }, body: new Uint8Array([1, 2, 3, 4]) });
    const ok = await worker.fetch(chunk("video/webm;codecs=vp9,opus"), env(bucket), {} as any);
    expect(ok.status).toBe(200);
    const got: any = await ok.json();
    expect(got.key).toBe(`age_of_ai/local/${RUN}/guest-video/v1abc/00003.webm`);
    const refused = await worker.fetch(chunk("audio/webm"), env(bucket), {} as any);
    expect(refused.status).toBe(415);
  });

  it("lists a finished video take and never touches the audio pointer", async () => {
    const bucket = fakeBucket();
    const sb = fakeSupabase({ local_takes: { guest: [{ manifest: "audio-take" }] } });
    vi.stubGlobal("fetch", sb.fn);
    for (let i = 0; i < 2; i++) {
      await bucket.put(`age_of_ai/local/${RUN}/guest-video/v1abc/0000${i}.webm`, new Uint8Array(10));
    }
    const res = await worker.fetch(new Request("https://api.nerranetwork.com/voices/upload-done", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: RUN, role: "guest", kind: "video", sid: "v1abc", chunks: 2,
                             mime: "video/webm;codecs=vp9,opus", started_at: "2026-10-28T17:00:00Z",
                             duration_ms: 10000 }),
    }), env(bucket), {} as any);
    expect(res.status).toBe(200);
    const patch = sb.calls.find((c) => c.method === "PATCH");
    expect(patch).toBeTruthy();
    expect(Object.keys(patch!.body)).toEqual(["grok_session_log"]);
    const takes = patch!.body.grok_session_log.local_video_takes.guest;
    expect(takes).toHaveLength(1);
    expect(takes[0]).toMatchObject({ manifest: `age_of_ai/local/${RUN}/guest-video/v1abc/manifest.json`,
                                     chunks: 2, missing: 0, bytes: 20 });
    expect(patch!.body.grok_session_log.local_takes).toEqual({ guest: [{ manifest: "audio-take" }] });
    expect(bucket.objects.has(`age_of_ai/local/${RUN}/guest-video/v1abc/manifest.json`)).toBe(true);
  });
});

describe("the room's quiet research, as the webhook reports it", () => {
  it("keeps the lookups count and bounded findings", () => {
    const notes = Array.from({ length: 20 }, (_, i) => ({
      kind: i === 0 ? "guest" : "answer", at_sec: 60 * i, took_sec: 9, subject: "s".repeat(400),
      finding: "f".repeat(900), source: "Reuters", delivered: i % 2 === 0,
    }));
    const out: any = roomCountersOf({ research_lookups: 7, research_notes: [...notes, { kind: "other", finding: "x" }] });
    expect(out.research_lookups).toBe(7);
    expect(out.research_notes).toHaveLength(12);
    expect(out.research_notes[0]).toMatchObject({ kind: "guest", at_sec: 0, source: "Reuters", delivered: true });
    expect(out.research_notes[0].subject).toHaveLength(160);
    expect(out.research_notes[0].finding).toHaveLength(300);
    expect(out.research_notes[1].delivered).toBe(false);
  });

  it("drops what is not a finding", () => {
    const out: any = roomCountersOf({ research_notes: [{ kind: "guest" }, { kind: "spam", finding: "x" }, "x"] });
    expect(out.research_notes).toEqual([]);
  });
});
