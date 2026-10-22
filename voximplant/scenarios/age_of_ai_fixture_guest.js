/**
 * The Age of AI — FIXTURE GUEST (rehearsal harness, Oct 21 2026).
 *
 * A second voice agent that plays a PAST guest so a change to Mira's room
 * (prompt, end-of-turn setting, reasoning effort, rotation policy) can be
 * rehearsed and measured before a real person pays for it. The network
 * insists on an A/B listen for every spoken change; this show had no way to
 * produce one, and the Oct 19 prompt rebuild went straight into Jon
 * Cheney's room (docs/reviews/age_of_ai_review_2026_10_21.md §7.5).
 *
 * This is its OWN scenario, started by the Management API
 * (StartScenarios on the fixture rule) with customData:
 *   {run_id, fixture: true, persona, voice, minutes, speaks_first,
 *    cough_clip, silence_ms, beats}
 * It joins the interview room exactly the way a human leg does —
 * VoxEngine.callConference("room-<run id>") with X-Role guest, the same
 * path the room probe takes — bridges its own Grok Voice agent to that leg
 * (the fixture hears the room, the room hears the fixture), records the
 * leg (L = the fixture's voice, R = what it heard, i.e. Mira), and reports
 * the recording through /voices/leg-event as a guest leg, so the
 * post-interview transcription reads it like any guest.
 *
 * It never edits the interview scenario and needs nothing from it. The
 * room treats the fixture as the guest: it opens to it, pauses for it,
 * interrupts it or not, rotates sessions under it. What the fixture does
 * that a human does: waits for Mira to speak first (unless speaks_first),
 * answers in the persona's register, stops mid-thought for two seconds on
 * cue, coughs once (a clip played into the leg), asks who someone is when a
 * name it does not know is dropped, says "let me think", and pushes back on
 * one question in a run. The cues are scheduled here (BEATS), so every
 * rehearsal exercises the same faults at the same minutes and two arms are
 * comparable.
 *
 * Secrets: the same deploy-time placeholders as the interview scenario
 * (upload_scenario substitutes them); the committed file carries none.
 */

require(Modules.Grok);

const SUPABASE_URL = "__SUPABASE_URL__";
const API_BASE = "https://api.nerranetwork.com/voices";
const LEG_EVENT_URL = API_BASE + "/leg-event";
// Oct 22 2026: a rehearsal of a CANDIDATE room calls "candroom-<run id>"
// (voximplant_client.CANDIDATE_ROOM_PREFIX); nothing else is accepted.
let ROOM_PREFIX = "room-";
const ROOM_PREFIXES = ["room-", "candroom-"];
const GROK_MODEL = ("__GROK_VOICE_MODEL__".indexOf("__") === 0)
  ? "grok-voice-3.0" : "__GROK_VOICE_MODEL__";
const DEFAULT_MINUTES = 10;
const MAX_MINUTES = 30;
// A person replies about a second after the host stops; the fixture's own
// end-of-turn is what Mira's turn detection is measured against, so keep
// it human and fixed across arms.
const DEFAULT_SILENCE_MS = 900;
// Scheduled behaviours, minutes after the fixture joins. Each is a system
// note to the fixture's agent (never spoken) except the cough, which is a
// clip played into the leg. Overridable per run with customData.beats.
const DEFAULT_BEATS = [
  { at_min: 2.0, kind: "pause_mid_thought" },
  { at_min: 3.5, kind: "cough" },
  { at_min: 5.0, kind: "let_me_think" },
  { at_min: 6.5, kind: "push_back" },
  { at_min: 8.0, kind: "ask_who" },
];

let runId = null;
let roomCall = null;
let agent = null;
let recordUrl = null;
let joinedAt = null;
let done = false;
let sessionReady = false;
let bridged = false;
let custom = {};
let beatTimers = [];
let maxTimer = null;

function log(text) { Logger.write("[aoa-fixture " + (runId || "?") + "] " + text); }

function sleep(ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); }

// Request signing: the same helpers as the interview scenario (kept
// byte-identical; tests/test_room_mechanics_2026_10_21.py compares them).
const WEBHOOK_SECRET = "__VOICES_WEBHOOK_SECRET__";

function utf8Bytes(str) {
  const out = [];
  for (let i = 0; i < str.length; i++) {
    let c = str.charCodeAt(i);
    if (c >= 0xd800 && c < 0xdc00 && i + 1 < str.length) {
      const d = str.charCodeAt(i + 1);
      if (d >= 0xdc00 && d < 0xe000) { c = 0x10000 + ((c - 0xd800) << 10) + (d - 0xdc00); i++; }
    }
    if (c < 0x80) out.push(c);
    else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
    else if (c < 0x10000) out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    else out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
  }
  return out;
}

const SHA256_K = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];

function sha256Bytes(bytes) {
  const h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  const len = bytes.length;
  const padded = bytes.slice();
  padded.push(0x80);
  while ((padded.length % 64) !== 56) padded.push(0);
  const bits = len * 8;
  for (let i = 7; i >= 0; i--) padded.push(i >= 4 ? Math.floor(bits / Math.pow(2, 8 * i)) & 0xff : (bits >>> (8 * i)) & 0xff);
  const w = new Array(64);
  for (let off = 0; off < padded.length; off += 64) {
    for (let i = 0; i < 16; i++) {
      w[i] = ((padded[off + 4 * i] << 24) | (padded[off + 4 * i + 1] << 16) |
              (padded[off + 4 * i + 2] << 8) | padded[off + 4 * i + 3]) >>> 0;
    }
    for (let i = 16; i < 64; i++) {
      const s0 = ((w[i - 15] >>> 7) | (w[i - 15] << 25)) ^ ((w[i - 15] >>> 18) | (w[i - 15] << 14)) ^ (w[i - 15] >>> 3);
      const s1 = ((w[i - 2] >>> 17) | (w[i - 2] << 15)) ^ ((w[i - 2] >>> 19) | (w[i - 2] << 13)) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
    }
    let a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
    for (let i = 0; i < 64; i++) {
      const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      const ch = (e & f) ^ (~e & g);
      const t1 = (hh + S1 + ch + SHA256_K[i] + w[i]) >>> 0;
      const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (S0 + maj) >>> 0;
      hh = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    h[0] = (h[0] + a) >>> 0; h[1] = (h[1] + b) >>> 0; h[2] = (h[2] + c) >>> 0; h[3] = (h[3] + d) >>> 0;
    h[4] = (h[4] + e) >>> 0; h[5] = (h[5] + f) >>> 0; h[6] = (h[6] + g) >>> 0; h[7] = (h[7] + hh) >>> 0;
  }
  const out = [];
  h.forEach(function (v) { out.push((v >>> 24) & 0xff, (v >>> 16) & 0xff, (v >>> 8) & 0xff, v & 0xff); });
  return out;
}

function hmacSha256Hex(secret, message) {
  let key = utf8Bytes(secret);
  if (key.length > 64) key = sha256Bytes(key);
  while (key.length < 64) key.push(0);
  const ipad = key.map(function (b) { return b ^ 0x36; });
  const opad = key.map(function (b) { return b ^ 0x5c; });
  const inner = sha256Bytes(ipad.concat(utf8Bytes(message)));
  const outer = sha256Bytes(opad.concat(inner));
  return outer.map(function (b) { return (b < 16 ? "0" : "") + b.toString(16); }).join("");
}

/** Headers for a request to the Worker: JSON, plus the signature when a secret was deployed. */
function signedHeaders(body) {
  const headers = ["Content-Type: application/json"];
  if (WEBHOOK_SECRET && WEBHOOK_SECRET.indexOf("__") !== 0) {
    try { headers.push("X-Voices-Signature: " + hmacSha256Hex(WEBHOOK_SECRET, body)); }
    catch (err) { Logger.write("[aoa " + runId + "] could not sign a request: " + err.message); }
  }
  return headers;
}

function getSecret(name) {
  const secrets = {
    SUPABASE_SERVICE_KEY: "__SUPABASE_SERVICE_KEY__",
    XAI_API_KEY: "__XAI_API_KEY__",
  };
  const value = secrets[name];
  if (!value || value.indexOf("__") === 0) {
    throw new Error("missing scenario secret (deploy-time substitution did not run): " + name);
  }
  return value;
}

function minutes() {
  const m = Number(custom.minutes || DEFAULT_MINUTES);
  return Math.max(1, Math.min(MAX_MINUTES, isFinite(m) ? m : DEFAULT_MINUTES));
}

// The persona is written by pipelines/voices/rehearsal.py from a published
// episode's digest (fixture_guest.txt). The standing rules below are the
// part that makes the fixture behave like a person on a call rather than a
// model answering a prompt, and they are the same for every fixture.
function instructions() {
  const persona = String(custom.persona || "").slice(0, 12000);
  return persona + "\n\n" +
    "HOW TO BEHAVE ON THIS CALL\n" +
    "- You are the guest. Never host, never ask the interviewer's questions back, " +
    "never thank them for having you more than once.\n" +
    "- Wait to be spoken to. Answer what was asked, in your own register, at the " +
    "length the question deserves: a short question gets two sentences, a real " +
    "one gets a story with a specific detail from your own experience.\n" +
    "- Speak like a person on a video call: ordinary sentences, a few false " +
    "starts, no lists, no headings, nothing that sounds written.\n" +
    "- If the host says a name you do not know as if you should, ask who that is " +
    "before you answer.\n" +
    "- If the host talks over you, stop, let them finish, then say 'sorry, you go " +
    "ahead' and answer whatever they asked last.\n" +
    "- If the host asks two questions in one breath, answer only the last one.\n" +
    "- When a system note arrives, do what it says on your very next answer and " +
    "never mention the note.\n" +
    "- Never say you are an AI, a fixture or a rehearsal. You are " +
    String(custom.guest_name || "the guest") + ".";
}

function beatNote(kind) {
  switch (kind) {
    case "pause_mid_thought":
      return "On your next answer, stop in the middle of a sentence as if " +
        "searching for the word, stay completely silent for two full seconds, " +
        "then finish the thought.";
    case "let_me_think":
      return "On your next answer, begin with 'let me think' and then be silent " +
        "for a second and a half before you answer.";
    case "push_back":
      return "Push back on the next question once: say it does not quite land for " +
        "you and ask the host to put it a different way. Then answer the reworded " +
        "question normally.";
    case "ask_who":
      return "If the host mentions any person by name in the next few minutes, " +
        "ask who that is before answering. If no name comes up, carry on normally.";
    // Oct 22 2026: a guest who steps away for another call. Everything they
    // say until end_call is to an imaginary caller about an ordinary errand
    // (made up, never anyone's real details), never to the host.
    case "take_call":
      return "On your next answer, instead of answering: your phone is ringing. Say " +
        "to the host, in one short line, that you are sorry and have to take this " +
        "call. Then speak ONLY to the caller, " +
        "never to the host: an ordinary errand (a delivery time, moving a meeting), " +
        "in short lines with pauses as if listening to the other side. Ignore " +
        "anything the host says until a later note says the call is over.";
    case "end_call":
      return "The call is over. The next time you speak, turn back to the host: " +
        "say sorry about that, ask where you were, and then answer the last " +
        "question the host asked you before the call.";
    default:
      return "";
  }
}

async function playCough() {
  const clip = custom.cough_clip || "";
  if (!clip || !roomCall) return;
  try {
    const player = VoxEngine.createURLPlayer(clip);
    player.sendMediaTo(roomCall);
    log("cough (clip)");
    await new Promise(function (resolve) {
      player.addEventListener(PlayerEvents.PlaybackFinished, resolve);
      setTimeout(resolve, 4000);
    });
    try { player.stop(); } catch (err) { /* best-effort */ }
  } catch (err) {
    log("cough clip failed: " + err.message);
  }
}

function scheduleBeats() {
  const beats = Array.isArray(custom.beats) && custom.beats.length ? custom.beats : DEFAULT_BEATS;
  beats.forEach(function (beat) {
    const at = Number(beat.at_min || 0) * 60 * 1000;
    if (!(at >= 0) || at > minutes() * 60 * 1000) return;
    beatTimers.push(setTimeout(function () {
      if (done || !agent) return;
      if (beat.kind === "cough") { playCough(); return; }
      const note = beatNote(beat.kind);
      if (!note) return;
      try {
        agent.conversationItemCreate({
          item: { type: "message", role: "system",
            content: [{ type: "input_text", text: "[CUE — do not read aloud] " + note }] },
        });
        log("beat " + beat.kind + " at " + beat.at_min + " min");
      } catch (err) {
        log("beat " + beat.kind + " failed: " + err.message);
      }
    }, at));
  });
}

async function createFixtureAgent() {
  const client = await Grok.createVoiceAgentAPIClient({
    xAIApiKey: getSecret("XAI_API_KEY"),
    model: GROK_MODEL,
    onWebSocketClose: function () {
      if (done) return;
      log("fixture agent socket closed");
      reconnectFixture();
    },
  });
  client.addEventListener(Grok.VoiceAgentAPIEvents.ConversationCreated, function () {
    const silence = Number(custom.silence_ms || DEFAULT_SILENCE_MS);
    client.sessionUpdate({ session: {
      // A different voice from Mira's "ara", so the mix and the recordings
      // never confuse the two. Overridable per fixture.
      voice: String(custom.voice || "sal").trim().toLowerCase(),
      turn_detection: { type: "server_vad",
        silence_duration_ms: Math.max(500, Math.min(2500, isFinite(silence) ? silence : DEFAULT_SILENCE_MS)) },
      // The fixture is not the thing under test; keep it quick.
      reasoning: { effort: "low" },
      instructions: instructions(),
      tools: [],
    } });
  });
  client.addEventListener(Grok.VoiceAgentAPIEvents.SessionUpdated, function () {
    sessionReady = true;
    bridge();
  });
  client.addEventListener(Grok.VoiceAgentAPIEvents.WebSocketError, function (ev) {
    log("fixture agent error: " + JSON.stringify((ev && (ev.data || ev)) || {}).slice(0, 200));
  });
  return client;
}

// A dropped fixture socket (Oct 22 2026). One candidate rehearsal lost its
// fixture to a 1006 two minutes in and ran twelve silent minutes measuring
// nothing. The fixture is the instrument, not the thing under test, so it
// comes back: a new agent, bridged to the same leg, told to carry on. The
// beats and the length timer are scheduled once and are not repeated.
const FIXTURE_RECONNECTS_MAX = 3;
let fixtureReconnects = 0;
let beatsScheduled = false;

function reconnectFixture() {
  if (done || !roomCall) return;
  if (fixtureReconnects >= FIXTURE_RECONNECTS_MAX) {
    log("fixture agent lost; no more reconnects");
    return finish("agent_lost");
  }
  fixtureReconnects += 1;
  sessionReady = false;
  bridged = false;
  setTimeout(async function () {
    if (done) return;
    try {
      agent = await createFixtureAgent();
      log("fixture agent reconnected (" + fixtureReconnects + ")");
    } catch (err) {
      log("fixture reconnect failed: " + err.message);
      return reconnectFixture();
    }
  }, 1000);
}

// Bridge once both the leg and the agent are up, whichever comes second.
function bridge() {
  if (bridged || !sessionReady || !roomCall || !agent) return;
  bridged = true;
  try {
    VoxEngine.sendMediaBetween(agent, roomCall);
    log("fixture bridged to the room leg");
  } catch (err) {
    log("bridge failed: " + err.message);
    return finish("bridge_failed");
  }
  if (fixtureReconnects > 0) {
    try {
      agent.conversationItemCreate({
        item: { type: "message", role: "system", content: [{ type: "input_text", text:
          "[CUE — do not read aloud] Your line dropped for a moment and you are back. " +
          "The next time the host speaks, say in one short line that you lost them " +
          "for a second, then answer as yourself." }] },
      });
      // No responseCreate: the fixture never speaks unprompted (a silent room
      // is the room's to break).
    } catch (err) { log("reconnect cue failed: " + err.message); }
  }
  if (beatsScheduled) return;
  beatsScheduled = true;
  scheduleBeats();
  if (custom.speaks_first) {
    // Piper Martz said "Hi Mira, thanks for having me" before the opening;
    // a rehearsal can reproduce that.
    setTimeout(function () {
      if (done) return;
      try {
        agent.conversationItemCreate({
          item: { type: "message", role: "system",
            content: [{ type: "input_text", text:
              "[CUE — do not read aloud] Say hello first, in one short line, as if " +
              "you have just put your headphones on, then wait." }] },
        });
        agent.responseCreate({});
      } catch (err) { log("speaks_first failed: " + err.message); }
    }, 1500);
  }
  maxTimer = setTimeout(function () {
    log("rehearsal length reached (" + minutes() + " min); leaving the room");
    finish("minutes_reached");
  }, minutes() * 60 * 1000);
}

async function postLegEvent(event) {
  try {
    const body = JSON.stringify({
      run_id: runId, role: "guest", event: event, call_mode: "webrtc",
      fixture: true, fixture_id: custom.fixture_id || null,
      record_url: event === "left" ? recordUrl : null,
      duration_sec: joinedAt ? Math.round((Date.now() - joinedAt) / 1000) : 0,
    });
    await Net.httpRequestAsync(LEG_EVENT_URL, {
      method: "POST", headers: signedHeaders(body),
      postData: body,
    });
  } catch (err) { log("leg-event " + event + " failed: " + err.message); }
}

async function finish(reason) {
  if (done) return;
  done = true;
  log("finishing: " + reason);
  beatTimers.forEach(function (t) { clearTimeout(t); });
  if (maxTimer) clearTimeout(maxTimer);
  if (roomCall) { try { roomCall.hangup(); } catch (err) { /* best-effort */ } }
  if (agent) {
    try { if (agent.close) agent.close(); else if (agent.stop) agent.stop(); } catch (err) { /* best-effort */ }
  }
  await sleep(1500);   // let RecordStarted carry the URL before we report it
  await postLegEvent("left");
  VoxEngine.terminate();
}

VoxEngine.addEventListener(AppEvents.Started, async function () {
  try { custom = JSON.parse(VoxEngine.customData() || "{}"); } catch (err) { custom = {}; }
  if (!custom.fixture || !custom.run_id) {
    Logger.write("[aoa-fixture] started without {fixture, run_id}; nothing to do");
    return VoxEngine.terminate();
  }
  runId = custom.run_id;
  const headers = { "X-Run-Id": runId, "X-Role": "guest", "X-Call-Mode": "webrtc", "X-Fixture": "1" };
  try {
    if (ROOM_PREFIXES.indexOf(custom.room_prefix) >= 0) ROOM_PREFIX = custom.room_prefix;
    roomCall = VoxEngine.callConference(ROOM_PREFIX + runId, "guest", "guest", headers);
  } catch (err) {
    log("callConference threw: " + err.message);
    return VoxEngine.terminate();
  }
  roomCall.addEventListener(CallEvents.RecordStarted, function (ev) { if (ev && ev.url) recordUrl = ev.url; });
  roomCall.addEventListener(CallEvents.Failed, function (ev) {
    log("room leg failed: " + ((ev && (ev.reason || ev.code)) || "unknown"));
    finish("room_leg_failed");
  });
  roomCall.addEventListener(CallEvents.Disconnected, function () { finish("room_ended"); });
  roomCall.addEventListener(CallEvents.Connected, async function () {
    joinedAt = Date.now();
    log("in the room as the guest");
    try { roomCall.record({ name: "aoa_" + runId + "_fixture", stereo: true, hd_audio: true }); }
    catch (err) { log("record failed: " + err.message); }
    postLegEvent("joined");
    try {
      agent = await createFixtureAgent();
      log("fixture agent created (model " + GROK_MODEL + ")");
    } catch (err) {
      log("fixture agent failed: " + err.message);
      return finish("agent_failed");
    }
    bridge();
  });
});
