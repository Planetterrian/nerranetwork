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
const ROOM_PREFIX = "room-";
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
    onWebSocketClose: function () { if (!done) log("fixture agent socket closed"); },
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
    await Net.httpRequestAsync(LEG_EVENT_URL, {
      method: "POST", headers: ["Content-Type: application/json"],
      postData: JSON.stringify({
        run_id: runId, role: "guest", event: event, call_mode: "webrtc",
        fixture: true, fixture_id: custom.fixture_id || null,
        record_url: event === "left" ? recordUrl : null,
        duration_sec: joinedAt ? Math.round((Date.now() - joinedAt) / 1000) : 0,
      }),
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
