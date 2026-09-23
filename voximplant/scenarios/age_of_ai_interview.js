/**
 * The Age of AI — live interview scenario (Nerra Voices, spec §3).
 *
 * Runs on Voximplant cloud (VoxEngine V8 JS). Since Sept 9 2026 every
 * interview is a ROOM: one Voximplant conference session per interview run
 * that any number of people join the same way — open the studio link,
 * pick a mic, press Join. There is no dialed-out host leg any more and no
 * admin token on the co-host link; the co-host is simply a participant
 * whose link says role=host so Mira knows who he is and his track is
 * labelled.
 *
 * Two kinds of session run this one file (the platform starts a new
 * session per inbound call; VoxEngine.callConference is what merges them):
 *
 *  PARTICIPANT session — one per person (and one for a PSTN guest):
 *    - inbound WebRTC call from age-of-ai-studio.html with X-Run-Id /
 *      X-Role headers (default mode), or
 *    - outbound PSTN call to the guest's phone (StartScenarios with
 *      customData {"run_id"}) — the fallback mode.
 *    It answers, plays the recording-consent disclosure to a guest,
 *    records that person (Call.record stereo: L = their mic, R = what they
 *    hear) plus the guest camera (separate video recorder), then joins the
 *    room with VoxEngine.callConference("room-<run_id>") and bridges the
 *    two calls. When the person leaves it reports its recording URLs to
 *    the Worker (/voices/leg-event "left").
 *
 *  ROOM session — one per interview run, started by the first
 *    callConference("room-<run_id>") and joined by every later one
 *    (AppEvents.CallAlerting per participant). It owns the mixer
 *    (VoxEngine.createConference + sendMediaBetween — the audio
 *    conferencing API, which does NOT need the rule's "video conference"
 *    option; Conference.add endpoints do, and that is why the Sept 9
 *    rehearsals had Mira deaf to the room), the Grok Voice Agent bridged to
 *    the mix (she hears everyone, everyone hears her), the Mira-only
 *    recorder, the real-clock time checks, the 50-minute hard cap, and the
 *    end-of-interview webhook. The room ends REJOIN_GRACE_MS after the last
 *    human leaves, so a dropped connection is "open the link again".
 *
 * All call config (guest phone, caller id, compiled Mira prompt, tools,
 * voice preset, host_mode) is pulled from Supabase so the fire step and
 * the studio page stay thin triggers and the run row is the single source
 * of truth.
 *
 * Secrets: SUPABASE_SERVICE_KEY and XAI_API_KEY are substituted into the
 * deployed copy at deploy time (upload_scenario placeholder substitution,
 * like __SUPABASE_URL__) — never hardcode them here.
 *
 * Deploy: voximplant/api_clients/voximplant_client.py upload_scenario();
 * the deploy workflow also makes sure the "age-of-ai-room" routing rule
 * (pattern ^room-.*) points at this scenario (ensure_room_rule).
 */

// Grok Voice Agent connector — native Voximplant module (enable the
// connector once in the Voximplant panel; spec phase 1). API shape
// verified July 2026 against voximplant/grok-voice-agent-example +
// docs.voximplant.ai: Modules.Grok / Grok.createVoiceAgentAPIClient.
require(Modules.Grok);
// Recorder module: the guest video recorder (participant session) and the
// Mira-only audio recorder (room session).
require(Modules.Recorder);
// Conference module: the room mixer (VoxEngine.createConference).
require(Modules.Conference);

const SUPABASE_URL = "__SUPABASE_URL__";           // substituted at deploy time
const API_BASE = "https://api.nerranetwork.com/voices";
const WEBHOOK_URL = API_BASE + "/interview-complete";
const LEG_EVENT_URL = API_BASE + "/leg-event";     // per-leg joined/left (+ recording URLs)
const NARRATION_TAKE_URL = API_BASE + "/narration-take"; // Mira reading a scripted pickup
const GROK_DROP_GUARD_MS = 1500;                   // spec §7: teardown-race guard
const DEFAULT_PLANNED_MIN = 45;    // when the guest gave no preference
const HARD_CAP_SLACK_MIN = 5;      // how long past the planned end the room may run
const TIME_CHECK_EVERY_MS = 5 * 60 * 1000;
const ROOM_PREFIX = "room-";       // callConference id = ROOM_PREFIX + run id (rule ^room-.*)
// Voximplant ends a session that has had no call for 60 s (session
// limits) — a 90 s grace never fired its webhook and left runs stuck
// in_progress (Sept 10 2026). Stay under the limit.
const REJOIN_GRACE_MS = 45 * 1000; // room stays up this long after the last human leaves
const OPENING_WAIT_MS = 20 * 1000; // Mira opens when a guest is in, or after 20 s with only the host
// Sept 14 2026 (John Capobianco). The trace of that room: guest leg attached
// at 14:55:13.4, Mira opened the show at 14:55:14.5 — 1.1 seconds later,
// before he had his headphones on — and the co-host joined at 14:55:56, 43
// seconds into a show that had already started without him. Both halves of
// the clunky open are timing, not wording.
const GUEST_SETTLE_MS = 7 * 1000;   // let the guest arrive before she speaks
const COHOST_WAIT_MS = 2 * 60 * 1000; // hold the open this long for the co-host
// Sept 14 2026 (Vincent Rylan): he joined at 21:53 for a 22:00 interview and
// the two-minute hold ran out at 21:55, so Mira opened the show four minutes
// before the co-host arrived — the hold was measured from the guest's
// arrival when it should be measured from the time the interview was
// actually called for. An eager guest must not cost the co-host his
// introduction.
const COHOST_WAIT_MAX_MS = 12 * 60 * 1000; // ... but never hold longer than this
// Nobody came (Sept 15 2026, Erica Sell). scheduleTeardown only fires when the
// room EMPTIES, which needs somebody to have joined first, so a room nobody
// joins runs to the hard cap: fifty minutes of session and of an open Grok
// agent for an interview that never happened, and a webhook — and therefore
// the guest's reschedule email — fifty minutes late. This ends it instead.
// Measured from the scheduled start, not from room open, because the room
// opens twelve minutes early and a guest ten minutes late is normal.
const NO_SHOW_GRACE_MS = 12 * 60 * 1000;
const AUDIO_CHECK_AFTER_MS = 12 * 1000; // trace whether the mix has carried speech yet (diagnostic only)
const ROLES = { guest: true, host: true };
// Voice Agent model (Sept 10 2026). The Voximplant connector's built-in
// default is `grok-voice-fast-1.0`, which xAI has DEPRECATED — once xAI
// stopped serving it, every session died 100 ms after the socket opened
// with "WebSocket.Close 1011 Internal server error while operating" and
// Mira never spoke. Always send an explicit model. Substituted at deploy
// time from the GROK_VOICE_MODEL env/var (see upload_scenario); the
// literal below is the fallback if substitution did not run.
const GROK_MODEL = ("__GROK_VOICE_MODEL__".indexOf("__") === 0)
  ? "grok-voice-latest" : "__GROK_VOICE_MODEL__";
// SESSION RELAY (Sept 10 2026). xAI caps ONE Voice Agent session at
// GROK_SESSION_MAX_MIN (30 on Tier 3, and the ceiling is a Voice Agent API
// limit rather than a tier perk). Interviews are booked for 45 minutes, so
// a single session would be killed mid-sentence. Instead the room hands the
// conversation to a FRESH Mira session a few minutes before the ceiling,
// carrying a transcript so she picks up where she left off. Humans never
// leave the room, so the mix and every recording stay continuous.
// Substituted at deploy time; lower it (e.g. 6) to rehearse a hand-off in
// minutes instead of half an hour.
const GROK_SESSION_MAX_MIN = (function () {
  const raw = parseInt("__GROK_SESSION_MAX_MIN__", 10);
  return (raw > 0) ? raw : 30;
})();
// Rotate 4 min before the ceiling, never sooner than 2 min in.
const ROTATE_AFTER_MS_DEFAULT = Math.max(2, GROK_SESSION_MAX_MIN - 4) * 60 * 1000;
// A run row may shorten this for a rehearsal:
//   update interview_runs set grok_session_log =
//     coalesce(grok_session_log,'{}'::jsonb) || '{"rotate_after_sec":90}'
//   where id = '<run>';
function rotateAfterMs() {
  try {
    const override = config && config.grok_session_log &&
                     Number(config.grok_session_log.rotate_after_sec);
    if (override > 0) return override * 1000;
  } catch (err) { /* fall through */ }
  return ROTATE_AFTER_MS_DEFAULT;
}
const HANDOVER_TURNS = 24;   // transcript lines carried into the next session

// Shared state (each session is one of the two kinds; unused fields stay null).
let runId = null;
let callMode = "webrtc";   // "pstn" | "webrtc" — set by whichever entry fires
let sessionKind = null;    // "participant" | "room"
let webhookFired = false;

// ---------------------------------------------------------------------------
// Entry 1: outbound PSTN (fallback mode) — StartScenarios with customData.
// Inbound sessions also fire AppEvents.Started (with no customData); they
// simply return here and are handled by CallAlerting below.
// ---------------------------------------------------------------------------

VoxEngine.addEventListener(AppEvents.Started, async function () {
  const custom = JSON.parse(VoxEngine.customData() || "{}");
  // A narration take has no interview and therefore no run_id, so it must be
  // recognised BEFORE the run_id guard below (Sept 11 2026: it was not, and
  // every take fell through to the inbound-session return and did nothing).
  if (custom.narrate) return narrationSession(custom); // Mira reading a scripted pickup
  if (!custom.run_id) return; // inbound session — CallAlerting takes over.
  if (custom.probe) return probeSession(custom); // synthetic participant (diagnostics)

  sessionKind = "participant";
  callMode = "pstn";
  runId = custom.run_id;
  let config;
  try {
    config = await fetchInterviewConfig(runId);
    if (!config) throw new Error("no interview_runs row for " + runId);
  } catch (e) {
    Logger.write("[aoa] startup failure: " + e.message);
    await fireWebhook({ run_id: runId, status: "failed", reason: "startup: " + e.message });
    return VoxEngine.terminate();
  }

  const call = VoxEngine.callPSTN(config.guest_phone, config.caller_id);
  call.addEventListener(CallEvents.Connected, function () {
    participantConnected(call, "guest", config, /* withVideo = */ false);
  });
  call.addEventListener(CallEvents.Failed, async function (event) {
    // Guest didn't answer / call failed → Worker retry ladder re-dials.
    await fireWebhook({
      run_id: runId, status: "failed", call_mode: callMode,
      reason: "call_failed: " + (event.reason || event.code || "unknown"),
    });
    VoxEngine.terminate();
  });
});

// ---------------------------------------------------------------------------
// Narration takes (Sept 11 2026): Mira reads a written pickup HERSELF.
//
// The show's introductions and closes used to be produced by xAI's
// text-to-speech endpoint while the interview itself is the Speech-to-Speech
// voice agent. Even asking both for the same voice, they are different
// engines and a listener hears two different people — which defeats the
// point of a show hosted by one. So a pickup is now spoken by the same agent
// that hosts the interview: same model, same voice, same person.
//
// One session per paragraph. A Voximplant session with no call is torn down
// after 60 seconds, and a two-minute introduction does not fit inside that;
// a paragraph comfortably does. The caller stitches the takes back together.
// ---------------------------------------------------------------------------

async function narrationSession(custom) {
  sessionKind = "narration";
  const takeId = String(custom.take_id || "");
  const text = String(custom.text || "");
  const preset = String(custom.voice || "ara").trim().toLowerCase();
  let recorder = null;
  let recordUrl = null;
  let finished = false;

  const report = async function (status, detail) {
    if (finished) return;
    finished = true;
    try { if (recorder) recorder.stop(); } catch (err) { /* best-effort */ }
    await sleep(1200);            // let RecorderEvents.Stopped land the URL
    try {
      await Net.httpRequestAsync(NARRATION_TAKE_URL, {
        method: "POST", headers: ["Content-Type: application/json"],
        postData: JSON.stringify({
          take_id: takeId, status: status,
          record_url: recordUrl, detail: detail || null,
        }),
      });
    } catch (err) {
      Logger.write("[aoa narr " + takeId + "] report failed: " + err.message);
    }
    VoxEngine.terminate();
  };

  if (!takeId || !text) return report("failed", "take_id and text are required");

  // How long this paragraph should take to say. ResponseDone fires while she
  // is still speaking (Sept 11 2026: every take came back cut off after the
  // first sentence), so the recorder runs for the length of the script plus a
  // tail, and ResponseDone is only a log line.
  const words = text.split(/\s+/).filter(Boolean).length;
  const expectedMs = Math.min(44000, Math.max(6000, Math.round(words * 430) + 3500));

  // Hard stop well inside the call-less session limit.
  setTimeout(function () { report("failed", "timed out before the read finished"); }, 52 * 1000);

  let agent;
  try {
    agent = await Grok.createVoiceAgentAPIClient({
      xAIApiKey: getSecret("XAI_API_KEY"),
      model: GROK_MODEL,
      onWebSocketClose: function (event) {
        if (finished) return;
        report("failed", "socket closed: " + ((event && (event.code || event.reason)) || "unknown"));
      },
    });
  } catch (err) {
    return report("failed", "agent startup: " + err.message);
  }

  agent.addEventListener(Grok.VoiceAgentAPIEvents.ConversationCreated, function () {
    const narrationSessionCfg = {
      voice: preset,
      turn_detection: null,       // nobody is talking to her; this is a read
      instructions:
          "You are Mira, the host of this show, recording a scripted segment " +
          "in the studio. The user message contains your script. Read it " +
          "aloud word for word, exactly as written. Do not greet anyone, do " +
          "not introduce the script, do not comment on it, do not add or " +
          "remove or reorder anything, and do not answer it as if it were a " +
          "question. Speak it as your own words, warmly and unhurried, the " +
        "way you speak on the show. When the script ends, stop.",
    };
    const narrFormat = audioOutputFormat(custom.audio_rate);
    if (narrFormat) narrationSessionCfg.audio = narrFormat;
    agent.sessionUpdate({ session: narrationSessionCfg });
  });

  agent.addEventListener(Grok.VoiceAgentAPIEvents.SessionUpdated, function () {
    if (recorder) return;         // session.update is echoed back more than once
    try {
      recorder = VoxEngine.createRecorder({ name: "narr_" + takeId, hd_audio: true });
      recorder.addEventListener(RecorderEvents.Started, function (ev) { if (ev && ev.url) recordUrl = ev.url; });
      recorder.addEventListener(RecorderEvents.Stopped, function (ev) { if (ev && ev.url) recordUrl = ev.url; });
      agent.sendMediaTo(recorder);
      agent.conversationItemCreate({
        item: { type: "message", role: "user",
          content: [{ type: "input_text", text: text }] },
      });
      agent.responseCreate({});
      setTimeout(function () { report("ok", "read " + words + " words"); }, expectedMs);
    } catch (err) {
      report("failed", "recorder/read: " + err.message);
    }
  });

  if (Grok.VoiceAgentAPIEvents.ResponseDone) {
    agent.addEventListener(Grok.VoiceAgentAPIEvents.ResponseDone, function () {
      // Not a stop signal — she is usually still talking. Logged only.
      Logger.write("[aoa narr " + takeId + "] ResponseDone (still recording)");
    });
  }
}

// ---------------------------------------------------------------------------
// Entry 2: inbound calls. Two shapes land here:
//   - a studio page calling "mira" with X-Run-Id / X-Role  → participant
//   - VoxEngine.callConference("room-<run>") from a participant → room
// Detected by the dialed destination, whatever routing rule matched.
// ---------------------------------------------------------------------------

VoxEngine.addEventListener(AppEvents.CallAlerting, async function (e) {
  const dest = String(e.destination || (e.toURI || "").replace(/^sip:/, "").split("@")[0] || "");
  if (dest.indexOf(ROOM_PREFIX) === 0) return roomAlerting(e, dest);
  return participantAlerting(e);
});

// ===========================================================================
// PARTICIPANT SESSION
// ===========================================================================

let pCall = null;          // the person's call (WebRTC or PSTN)
let pRole = "guest";
let pRoomCall = null;      // our leg into the room
let pRecordUrl = null;     // Call.record → CallEvents.RecordStarted
let pVideoRecorder = null; // guest camera (WebRTC guests only)
let pVideoUrl = null;
let pConnectedAt = null;
let pDone = false;

function cleanRole(raw) {
  const r = String(raw || "").trim().toLowerCase();
  return ROLES[r] ? r : "guest";
}

async function participantAlerting(e) {
  sessionKind = "participant";
  callMode = "webrtc";
  const headers = e.headers || {};
  runId = headers["X-Run-Id"] || headers["x-run-id"] || null;
  const role = cleanRole(headers["X-Role"] || headers["x-role"]);

  let config;
  try {
    if (!runId) throw new Error("inbound studio call missing X-Run-Id header");
    config = await fetchInterviewConfig(runId);
    if (!config) throw new Error("no interview_runs row for " + runId);
    if (config.status === "completed" || config.status === "failed") {
      throw new Error("run " + runId + " is " + config.status);
    }
  } catch (err) {
    Logger.write("[aoa] inbound startup failure: " + err.message);
    try { e.call.reject(); } catch (ignored) {}
    return VoxEngine.terminate();
  }

  const call = e.call;
  call.addEventListener(CallEvents.Connected, function () {
    participantConnected(call, role, config, /* withVideo = */ role === "guest");
  });
  call.addEventListener(CallEvents.Failed, function (event) {
    Logger.write("[aoa " + runId + "] " + role + " inbound call failed: " + (event.reason || event.code || "unknown"));
    VoxEngine.terminate();
  });
  call.answer();
}

/**
 * One person is connected: record them, play the consent disclosure to a
 * guest, then join the room and bridge the two calls. Both modes converge
 * here (PSTN guest / WebRTC guest / WebRTC host).
 */
async function participantConnected(call, role, config, withVideo) {
  pCall = call;
  pRole = role;
  pConnectedAt = Date.now();
  call.addEventListener(CallEvents.Disconnected, participantLeft);
  try {
    // 1. Recording — call.record({stereo:true}) puts this person's mic on
    //    one channel and what they hear (the room mix: Mira + everyone
    //    else) on the other. Started before the disclosure so consent is
    //    on tape. NOTE: VoxEngine.createRecorder's stereo param records
    //    MIXED streams in both channels and can never separate
    //    participants (verified July 2026) — only Call.record gives the
    //    per-channel split the per-channel Whisper STT depends on.
    call.addEventListener(CallEvents.RecordStarted, function (ev) {
      if (ev && ev.url) pRecordUrl = ev.url;
    });
    call.record({
      name: "aoa_" + runId + (role === "host" ? "_host" : ""),
      stereo: true,
      hd_audio: true,
    });
    // VIDEO (WebRTC guests) on a SEPARATE recorder — guest camera plus the
    // room audio, for the future YouTube version. Dry-run 2 (July 20 2026)
    // proved video:true on call.record collapses the audio to a mono mix.
    if (withVideo) {
      try {
        pVideoRecorder = VoxEngine.createRecorder({ name: "aoa_" + runId + "_video", video: true });
        pVideoRecorder.addEventListener(RecorderEvents.Started, function (ev) { if (ev && ev.url) pVideoUrl = ev.url; });
        pVideoRecorder.addEventListener(RecorderEvents.Stopped, function (ev) { if (ev && ev.url) pVideoUrl = ev.url; });
        call.sendMediaTo(pVideoRecorder);
      } catch (err) {
        Logger.write("[aoa " + runId + "] video recorder unavailable (non-fatal): " + err.message);
        pVideoRecorder = null;
      }
    }

    // 2. Recording-consent disclosure — pre-generated Mira clip from R2
    //    (spec §11.2). Guests only; played on their own leg before they
    //    enter the room so it never interrupts a conversation in progress.
    if (role === "guest" && config.recording_disclosure_url) {
      call.startPlayback(config.recording_disclosure_url);
      await waitForEvent(call, CallEvents.PlaybackFinished);
    }
    if (pDone) return; // hung up during the disclosure

    // 3. Join the room. The first callConference for this id starts the
    //    room session; later ones land in it as CallAlerting.
    joinRoom(call, role);
  } catch (err) {
    Logger.write("[aoa " + runId + "] participant setup failure: " + err.message);
    try { call.hangup(); } catch (ignored) {}
  }
}

function joinRoom(call, role) {
  const headers = { "X-Run-Id": runId, "X-Role": role, "X-Call-Mode": callMode };
  let roomCall;
  try {
    roomCall = VoxEngine.callConference(ROOM_PREFIX + runId, role, role, headers);
  } catch (err) {
    Logger.write("[aoa " + runId + "] callConference threw: " + err.message);
    try { call.hangup(); } catch (ignored) {}
    return;
  }
  pRoomCall = roomCall;
  roomCall.addEventListener(CallEvents.Connected, function () {
    Logger.write("[aoa " + runId + "] " + role + " bridged into the room");
    VoxEngine.sendMediaBetween(call, roomCall);
    if (pVideoRecorder) {
      try { roomCall.sendMediaTo(pVideoRecorder); } catch (err) {
        Logger.write("[aoa " + runId + "] room->video-recorder failed (non-fatal): " + err.message);
      }
    }
  });
  roomCall.addEventListener(CallEvents.Failed, function (ev) {
    Logger.write("[aoa " + runId + "] room leg failed: " + ((ev && (ev.reason || ev.code)) || "unknown"));
    try { call.hangup(); } catch (ignored) {}
  });
  roomCall.addEventListener(CallEvents.Disconnected, function () {
    // The room ended (hard cap, Grok drop, grace expired) — drop the person.
    try { call.hangup(); } catch (ignored) {}
  });
}

async function participantLeft() {
  if (pDone) return;
  pDone = true;
  if (pRoomCall) { try { pRoomCall.hangup(); } catch (ignored) {} }
  if (pVideoRecorder) { try { pVideoRecorder.stop(); } catch (ignored) {} }
  // Recording URLs arrive on RecordStarted (audio) / Stopped (video);
  // give the platform a moment to deliver the video Stopped event.
  await sleep(1500);
  try {
    await Net.httpRequestAsync(LEG_EVENT_URL, {
      method: "POST",
      headers: ["Content-Type: application/json"],
      postData: JSON.stringify({
        run_id: runId, role: pRole, event: "left", call_mode: callMode,
        record_url: pRecordUrl, video_url: pVideoUrl,
        duration_sec: pConnectedAt ? Math.round((Date.now() - pConnectedAt) / 1000) : 0,
      }),
    });
  } catch (err) {
    Logger.write("[aoa " + runId + "] leg-event left failed: " + err.message);
  }
  VoxEngine.terminate();
}

// ---------------------------------------------------------------------------
// PROBE session (Sept 9 2026 diagnostics): a synthetic participant. Fired by
// the "Voximplant room probe" workflow (StartScenarios with customData
// {run_id, probe: true, clip}). It joins the room exactly like a human leg
// (callConference with X-Role guest) and, instead of a microphone, plays a
// speech clip into its room leg twice: once right after joining (while the
// room mix is Mira's input) and once more 12 s later. The room's trace
// then says whether the mix carries speech — no human timing needed. The probe
// records its room leg (R = what the room sent back, i.e. Mira's replies)
// and reports it via /voices/leg-event role=probe.
// ---------------------------------------------------------------------------

async function probeSession(custom) {
  sessionKind = "probe";
  runId = custom.run_id;
  const clip = custom.clip || "";
  const headers = { "X-Run-Id": runId, "X-Role": "guest", "X-Call-Mode": "webrtc", "X-Probe": "1" };
  let probeRecordUrl = null;
  let roomCall;
  try {
    roomCall = VoxEngine.callConference(ROOM_PREFIX + runId, "probe", "probe", headers);
  } catch (err) {
    Logger.write("[aoa " + runId + "] probe callConference threw: " + err.message);
    return VoxEngine.terminate();
  }
  const finish = async function () {
    await sleep(1500);
    try {
      await Net.httpRequestAsync(LEG_EVENT_URL, {
        method: "POST", headers: ["Content-Type: application/json"],
        postData: JSON.stringify({ run_id: runId, role: "probe", event: "left", record_url: probeRecordUrl }),
      });
    } catch (err) { /* best-effort */ }
    VoxEngine.terminate();
  };
  roomCall.addEventListener(CallEvents.Failed, function (ev) {
    Logger.write("[aoa " + runId + "] probe room leg failed: " + ((ev && (ev.reason || ev.code)) || "unknown"));
    finish();
  });
  roomCall.addEventListener(CallEvents.Disconnected, function () { finish(); });
  roomCall.addEventListener(CallEvents.RecordStarted, function (ev) { if (ev && ev.url) probeRecordUrl = ev.url; });
  roomCall.addEventListener(CallEvents.Connected, async function () {
    Logger.write("[aoa " + runId + "] probe in the room");
    try { roomCall.record({ name: "aoa_" + runId + "_probe", stereo: true, hd_audio: true }); } catch (err) {}
    const play = async function (label) {
      if (!clip) return;
      try {
        const player = VoxEngine.createURLPlayer(clip);
        player.sendMediaTo(roomCall);
        Logger.write("[aoa " + runId + "] probe playing clip (" + label + ")");
        await waitForEvent(player, PlayerEvents.PlaybackFinished);
        try { player.stop(); } catch (err) {}
      } catch (err) {
        Logger.write("[aoa " + runId + "] probe clip failed (" + label + "): " + err.message);
      }
    };
    await sleep(4000);      // Mira's session is up and she is opening
    await play("via room mix");
    await sleep(12000);
    await play("second pass");
    await sleep(20000);     // let Mira answer; it is on the recording
    try { roomCall.hangup(); } catch (err) {}
  });
}

// ===========================================================================
// ROOM SESSION
// ===========================================================================

let conf = null;            // the mixer (VoxEngine.createConference)
let config = null;          // interview_runs row

// The interview's length is the guest's answer on their application, carried
// on the run row (planned_minutes), not a constant. Before Sept 13 2026 every
// guest got 45 minutes whatever they had asked for. The room may run a few
// minutes past the planned end so a closing answer is never guillotined.
function plannedMin() {
  const asked = config && Number(config.planned_minutes);
  if (!isFinite(asked) || asked < 15 || asked > 90) return DEFAULT_PLANNED_MIN;
  return Math.round(asked);
}

function hardCapMs() {
  return (plannedMin() + HARD_CAP_SLACK_MIN) * 60 * 1000;
}
let grokAgent = null;
let legs = [];              // [{ id, role, call, joinedAt }]
let legSeq = 0;
let roomReady = null;       // Promise: config loaded + mixer created
let firstJoinAt = null;     // Date.now() of the first human in the room
let hostJoinedAt = null;    // ISO of the FIRST host join
let hostLeftAt = null;      // ISO of the last host drop
let hostJoins = 0;
let guestJoins = 0;
let hardCapTimer = null;
let timeCheckTimer = null;
let micCheckTimer = null;
let teardownTimer = null;
let noShowTimer = null;     // nobody joined at all; end rather than idle
let openingTimer = null;
let miraRecorder = null;
let miraRecordUrl = null;
let mixRecorder = null;     // the whole room mix (conf -> recorder), diagnostics + post-production
let mixRecordUrl = null;
let speechEvents = 0;
let bargeIns = 0;           // turns abandoned because someone else was talking
let miraSpeaking = false;   // a response is in flight (so there is one to cancel)
let agentStartedAt = null;  // when the CURRENT session's client was created
let rotateTimer = null;     // pending hand-off to a fresh session
let rotating = false;       // a hand-off is in flight (ignore the old socket closing)
let agentGeneration = 0;    // 1 = first session, 2 = after the first hand-off...
const transcript = [];      // rolling [who, text] for the hand-over note
let sessionReady = false;   // Grok SessionUpdated received (media bridged)
let openingFired = false;   // Mira opens exactly once
let cohostWaitTimer = null; // holding the open for a co-host who is coming
let cohostWaitExpired = false;
let anyoneHeard = false;    // first InputAudioBufferSpeechStarted
let roomEnded = false;
let endReason = "normal";

async function roomAlerting(e, dest) {
  sessionKind = "room";
  const headers = e.headers || {};
  const role = cleanRole(headers["X-Role"] || headers["x-role"]);
  if (!roomReady) {
    runId = headers["X-Run-Id"] || headers["x-run-id"] || dest.slice(ROOM_PREFIX.length);
    callMode = String(headers["X-Call-Mode"] || headers["x-call-mode"] || "webrtc");
    roomReady = openRoom();
  }
  let ok = false;
  try { ok = await roomReady; } catch (err) { ok = false; }
  if (!ok || roomEnded) {
    try { e.call.reject(); } catch (ignored) {}
    return;
  }
  admitLeg(e.call, role);
}

async function openRoom() {
  try {
    config = await fetchInterviewConfig(runId);
    if (!config) throw new Error("no interview_runs row for " + runId);
  } catch (err) {
    Logger.write("[aoa " + runId + "] room startup failure: " + err.message);
    await fireWebhook({ run_id: runId, status: "failed", reason: "startup: " + err.message });
    setTimeout(function () { VoxEngine.terminate(); }, 500);
    return false;
  }
  // A run can see several room sessions (a room that ended on a platform
  // fault and reopened when someone rejoined): keep the earlier timeline
  // instead of overwriting it, with a marker between sessions.
  try {
    if (Array.isArray(config.scenario_trace) && config.scenario_trace.length) {
      config.scenario_trace.slice(-100).forEach(function (line) { traceLines.push(line); });
      traceLines.push({ t: new Date().toISOString(), e: "room", d: "---- new room session ----" });
    }
  } catch (err) { /* trace is best-effort */ }
  await markRunStatus(runId, "in_progress");
  // The mixer. hd_audio keeps the mix at Opus wideband so Mira's input and
  // the per-person recordings don't get narrowband-downmixed.
  conf = VoxEngine.createConference({ hd_audio: true });
  trace("room", "opened (" + callMode + "); mixer via sendMediaBetween");
  try {
    ["ConferenceError", "Started", "Stopped", "EndpointAdded", "EndpointRemoved"].forEach(function (name) {
      if (ConferenceEvents[name]) {
        conf.addEventListener(ConferenceEvents[name], function (ev) {
          trace("conference", name + (ev && ev.code ? " code " + ev.code : "") + (ev && ev.error ? " " + ev.error : ""));
        });
      }
    });
  } catch (err) { /* event names differ across VoxEngine versions */ }
  startMixRecorder();
  armNoShowTimer();
  hardCapTimer = setTimeout(function () {
    Logger.write("[aoa " + runId + "] hard cap reached, ending room");
    endRoom("hard_cap");
  }, hardCapMs());
  startAgent();   // async; legs are admitted meanwhile
  return true;
}

function admitLeg(call, role) {
  const leg = { id: ++legSeq, role: role, call: call, joinedAt: Date.now() };
  legs.push(leg);
  if (teardownTimer) { clearTimeout(teardownTimer); teardownTimer = null; trace("room", "rejoin — teardown cancelled"); }
  call.addEventListener(CallEvents.Connected, function () {
    VoxEngine.sendMediaBetween(call, conf);
    if (!firstJoinAt) firstJoinAt = Date.now();
    if (role === "host") {
      hostJoins++;
      if (!hostJoinedAt) hostJoinedAt = new Date().toISOString();
    } else if (role === "guest") {
      guestJoins++;
    }
    trace("leg", role + " #" + leg.id + " joined (" + legs.length + " in room)");
    if (role === "guest" && noShowTimer) {
      clearTimeout(noShowTimer); noShowTimer = null;
    }
    if (!openingFired) maybeOpen();
    postLegEvent(role, "joined");
    if (!openingFired) {
      maybeOpen();
    } else if (role === "guest" && guestJoins > 1) {
      // The guest dropped and came back. This is the one arrival worth
      // speaking for: they missed whatever was said while they were gone
      // and they do not know where to pick up.
      resumeForGuest();
    } else {
      // Anyone else coming or going is context, not an event. The co-host
      // reconnecting used to make Mira stop and acknowledge it, over the
      // top of the guest's answer (Adrian Wolfberg, Sept 15 2026, four
      // times in one interview). Patrick must be able to drop and rejoin
      // without the interview noticing.
      noteRoom(role + " joined");
    }
  });
  const gone = function (why) {
    const idx = legs.indexOf(leg);
    if (idx < 0) return;
    legs.splice(idx, 1);
    trace("leg", role + " #" + leg.id + " left: " + why + " (" + legs.length + " in room)");
    if (role === "host" && !legs.some(function (l) { return l.role === "host"; })) {
      hostLeftAt = new Date().toISOString();
    }
    postLegEvent(role, "left");
    if (roomEnded) return;
    if (legs.length === 0) {
      scheduleTeardown();
    } else if (openingFired) {
      noteRoom(role + " left the room");
    }
  };
  call.addEventListener(CallEvents.Disconnected, function () { gone("disconnected"); });
  call.addEventListener(CallEvents.Failed, function (ev) { gone("failed: " + ((ev && (ev.reason || ev.code)) || "unknown")); });
  call.answer();
}

function humansIn(role) {
  return legs.filter(function (l) { return !role || l.role === role; }).length;
}

// The room outlives the last human by REJOIN_GRACE_MS so a dropped
// connection is just "open the link again" — Mira and the mixer stay up.
// End a room nobody joined. Armed at open, cancelled by the first guest.
function armNoShowTimer() {
  if (noShowTimer) clearTimeout(noShowTimer);
  const due = config && config.scheduled_for ? Date.parse(config.scheduled_for) : NaN;
  const from = isFinite(due) ? Math.max(0, due - Date.now()) : 0;
  noShowTimer = setTimeout(function () {
    noShowTimer = null;
    if (roomEnded || humansIn("guest") > 0) return;
    trace("room", "no guest after " + Math.round(NO_SHOW_GRACE_MS / 60000)
          + " minutes past the scheduled start — ending as a no-show");
    endRoom("no_show");
  }, from + NO_SHOW_GRACE_MS);
}

function scheduleTeardown() {
  if (teardownTimer || roomEnded) return;
  trace("room", "empty — ending in " + (REJOIN_GRACE_MS / 1000) + "s unless someone rejoins");
  teardownTimer = setTimeout(function () {
    teardownTimer = null;
    if (legs.length === 0) endRoom("normal");
  }, REJOIN_GRACE_MS);
}

// Remember one line of the conversation for the hand-over note. Text can
// arrive on a few shapes depending on connector version, so dig defensively.
function textOf(event) {
  const e = (event && (event.data || event)) || {};
  const p = e.payload || e;
  const t = p.transcript || p.text || (p.delta && p.delta.transcript) ||
            (p.item && p.item.content && p.item.content[0] &&
             (p.item.content[0].transcript || p.item.content[0].text));
  return typeof t === "string" ? t.trim() : "";
}

function remember(who, text) {
  if (!text) return;
  transcript.push(who + ": " + String(text).slice(0, 400));
  if (transcript.length > 200) transcript.splice(0, transcript.length - 200);
  if (who === "Mira") {
    // Order matters: note the question BEFORE testing for a sign-off, so a
    // turn that asks for a parting thought and then ends the recording in the
    // same breath is caught by the same rule.
    try { noteLastWordAsk(text); }
    catch (err) { Logger.write("[aoa " + runId + "] last-word check failed: " + err.message); }
    try { catchEarlySignOff(text); }
    catch (err) { Logger.write("[aoa " + runId + "] sign-off check failed: " + err.message); }
  } else {
    lastWordAnswered = true;
  }
}

// What the next Mira needs in order to continue rather than restart.
function handoverNote() {
  const said = transcript.slice(-HANDOVER_TURNS).join("\n");
  return "\n\n=== HANDOVER — READ BEFORE SPEAKING ===\n" +
    "This interview is ALREADY IN PROGRESS and you are continuing it. The " +
    "guest has been talking with you for about " +
    Math.round((Date.now() - (firstJoinAt || Date.now())) / 60000) + " minutes. " +
    "Do NOT re-introduce yourself, do NOT greet them again, do NOT restate " +
    "the premise of the show, and do NOT repeat questions already asked. " +
    "There was a brief technical pause; if anything, say something short and " +
    "natural like \"sorry, go on\" and carry straight on.\n" +
    (said ? "Here is the conversation so far:\n" + said + "\n" : "") +
    "=== END HANDOVER ===\n";
}

// Sept 14 2026. Mira's voice is band-limited where the guest's is not: on the
// John Capobianco tape her speech is 50 dB down by 5.5 kHz while his still has
// real energy at 8.3 kHz, and her narration takes measure the same, so it is
// the agent's own output stream and not the call path (the conference, the
// recorders and the mixer are all hd_audio already). xAI documents a PCM
// output rate — 8000, 16000, 22050, 24000 (default), 32000, 44100, 48000 — so
// ask for a specific one and let the measurement decide. Null (the default
// here) sends nothing and keeps whatever the module negotiates today.
function audioOutputFormat(rateOverride) {
  const rate = Number(rateOverride || (config && config.audio_output_rate) || 0);
  if (!rate) return null;
  return { output: { format: { type: "audio/pcm", rate: rate } } };
}

/** End-of-turn detection. Longer silence = she interrupts less. */
function turnDetection() {
  const tuned = (config && config.turn_detection) || {};
  return {
    type: "server_vad",
    // 0.1-0.9; the API's own default is 0.85 and it has been fine.
    threshold: Number(tuned.threshold) || 0.85,
    prefix_padding_ms: Number(tuned.prefix_padding_ms) || 333,
    // The number that matters. 1.1s is longer than a clause-boundary breath
    // and shorter than a "let me think about that" pause, which the prompt
    // tells her to leave alone anyway.
    silence_duration_ms: Number(tuned.silence_duration_ms) || 1100,
  };
}

/**
 * Build a Voice Agent session and wire every listener. `note` is appended to
 * Mira's instructions for a continuation session (null for the first one).
 */
async function createAgent(note) {
  const generation = ++agentGeneration;
  const agent = await Grok.createVoiceAgentAPIClient({
    xAIApiKey: getSecret("XAI_API_KEY"),
    model: GROK_MODEL,
    onWebSocketClose: function (event) { onAgentClosed(generation, event); },
  });

  agent.addEventListener(Grok.VoiceAgentAPIEvents.ConversationCreated, function () {
    // Sept 11 2026: this used to capitalize the preset ("ara" -> "Ara") on
    // the belief that the Voice Agent API wanted title case. xAI's docs are
    // explicit that the Speech-to-Speech and Text-to-Speech APIs share one
    // voice roster and both take the LOWERCASE id, so "Ara" was not a voice
    // and every interview silently fell back to the default voice — which is
    // why Mira on the tape did not match Mira in the narration.
    const preset = String(config.voice_preset || "ara").trim().toLowerCase();
    const sessionCfg = {
        voice: preset,
        // Sept 14 2026 (John Capobianco): "server_vad" with no settings takes
        // the API's default end-of-turn silence, which is a fraction of a
        // second — short enough that a breath mid-sentence reads as the guest
        // finishing, and Mira starts talking over him. A person telling a
        // story pauses for about a second between clauses, so she waits
        // longer than that before taking the turn. Tunable per run without a
        // scenario deploy: interview_runs.turn_detection.
        turn_detection: turnDetection(),
        instructions: config.mira_system_prompt + (note || ""),
        tools: config.tools || [],
    };
    const outFormat = audioOutputFormat();
    if (outFormat) sessionCfg.audio = outFormat;
    agent.sessionUpdate({ session: sessionCfg });
  });

  agent.addEventListener(Grok.VoiceAgentAPIEvents.SessionUpdated, function () {
    if (generation !== agentGeneration) return; // superseded mid-handshake
    try {
      // Bridge Mira <-> the mix: she hears everyone (minus herself),
      // everyone hears her. Audio-conferencing API (sendMediaBetween),
      // not Conference.add endpoints — see the file header.
      VoxEngine.sendMediaBetween(agent, conf);
      if (miraRecorder) { try { agent.sendMediaTo(miraRecorder); } catch (err) { /* best-effort */ } }
      sessionReady = true;
      armRotation();
      if (generation === 1) {
        trace("grok", "session updated; agent<->room mix bridged");
        startMiraRecorder();
        maybeOpen();
      } else {
        trace("grok", "session " + generation + " bridged — resuming the interview");
        rotating = false;
        // Nudge her to speak first so the seam is a beat, not a silence.
        try { miraSpeaking = true; agent.responseCreate({}); } catch (err) { /* best-effort */ }
      }
    } catch (err) {
      Logger.write("[aoa " + runId + "] media-bridge failure: " + err.message);
      endRoom("media_bridge_failed");
    }
  });

  // Barge-in. Flushing the buffer stops her being HEARD; until Sept 15 2026
  // that was all this did, and the server kept generating the rest of the
  // turn. The audio then arrived after the guest finished, which is why she
  // appeared to ask the same question two and three times in a row — it was
  // one question, replayed from a turn nobody had cancelled. Silence her
  // locally AND tell the server to stop, so the turn is actually abandoned.
  agent.addEventListener(Grok.VoiceAgentAPIEvents.InputAudioBufferSpeechStarted, function () {
    speechEvents++;
    if (!anyoneHeard) trace("grok", "first inbound speech heard (via room mix)");
    else if (speechEvents <= 6) trace("grok", "speech heard #" + speechEvents + " (via room mix)");
    anyoneHeard = true;
    if (agent !== grokAgent) return;
    agent.clearMediaBuffer();
    if (!miraSpeaking) return;
    miraSpeaking = false;
    try {
      if (agent.responseCancel) { agent.responseCancel(); bargeIns++; }
      else if (agent.responseCancel === undefined && agent.send) {
        agent.send(JSON.stringify({ type: "response.cancel" })); bargeIns++;
      }
      if (bargeIns <= 6) trace("grok", "yielded mid-turn (" + bargeIns + ")");
    } catch (err) {
      if (bargeIns <= 2) trace("grok", "could not cancel the turn: " + err.message);
    }
    // Sept 23 2026, Viktor Popovic. Cancelling the turn stops her being
    // heard, but nothing told HER that the rest went unsaid, and when he
    // finished she picked the sentence up where it broke: "strategies. What
    // triggers a fallback..." — the first word left over from a question
    // abandoned a minute earlier. Said once, quietly, while he is talking:
    // the unfinished sentence is gone, answer him instead. No responseCreate;
    // this is context for her next turn, not a turn of its own.
    if (bargeIns <= 40) {
      try {
        agent.conversationItemCreate({
          item: { type: "message", role: "system", content: [{ type: "input_text", text:
            "[ROOM — system note, do not read aloud] You were cut off " +
            "mid-sentence and they did not hear the rest. When they finish, " +
            "do NOT pick that sentence up where it stopped and do not repeat " +
            "their last words back to them. Respond to what they just said, " +
            "or ask one fresh, short question." }] },
        });
      } catch (err) {
        if (bargeIns <= 2) trace("grok", "could not note the barge-in: " + err.message);
      }
    }
  });

  // Rolling transcript — the raw material for the hand-over note.
  try {
    if (Grok.VoiceAgentAPIEvents.ResponseOutputAudioTranscriptDone) {
      agent.addEventListener(Grok.VoiceAgentAPIEvents.ResponseOutputAudioTranscriptDone,
        function (ev) { remember("Mira", textOf(ev)); });
    }
    if (Grok.VoiceAgentAPIEvents.Unknown) {
      agent.addEventListener(Grok.VoiceAgentAPIEvents.Unknown, function (ev) {
        const raw = JSON.stringify((ev && (ev.data || ev)) || {});
        if (raw.indexOf("input_audio_transcription.completed") >= 0) remember("Guest", textOf(ev));
      });
    }
    if (Grok.VoiceAgentAPIEvents.ResponseDone) {
      agent.addEventListener(Grok.VoiceAgentAPIEvents.ResponseDone, function () {
        miraSpeaking = false;
        trace("grok", "response done");
      });
    }
  } catch (err) { /* event names differ across connector versions */ }

  // Mira's in-call tools — WITHOUT this handler a tool call stalls her
  // mid-conversation forever (the request is never answered).
  agent.addEventListener(Grok.VoiceAgentAPIEvents.ResponseFunctionCallArgumentsDone, onToolCall);
  agent.addEventListener(Grok.VoiceAgentAPIEvents.WebSocketError, function (event) {
    onAgentClosed(generation, event);
  });
  return agent;
}

async function startAgent() {
  try {
    grokAgent = await createAgent(null);
    agentStartedAt = Date.now();
    trace("grok", "agent created (model " + GROK_MODEL + ")");
  } catch (err) {
    Logger.write("[aoa " + runId + "] agent startup failure: " + err.message);
    trace("grok", "agent startup failed: " + err.message);
    endRoom("agent_startup_failed");
  }
}

// Hand the conversation to a fresh session before xAI kills this one.
function armRotation() {
  if (rotateTimer) clearTimeout(rotateTimer);
  rotateTimer = setTimeout(rotateAgent, rotateAfterMs());
}

async function rotateAgent() {
  rotateTimer = null;
  if (roomEnded || rotating || !grokAgent) return;
  // Nobody is in the room (everyone dropped, or the room is draining). A
  // fresh session would just burn an xAI session on silence; wait for a
  // rejoin instead. If the room really is over, endRoom() clears the timer.
  if (legs.length === 0) { rotateTimer = setTimeout(rotateAgent, 15 * 1000); return; }
  rotating = true;
  const previous = grokAgent;
  const note = handoverNote();
  trace("grok", "handing over to a fresh session after " +
        Math.round((Date.now() - (agentStartedAt || Date.now())) / 1000) + "s (" +
        transcript.length + " lines of transcript, xAI cap " + GROK_SESSION_MAX_MIN + " min)");
  let next;
  try {
    next = await createAgent(note);
  } catch (err) {
    rotating = false;
    trace("grok", "hand-over failed, staying on the current session: " + err.message);
    // Try again shortly; the current session still has a couple of minutes.
    rotateTimer = setTimeout(rotateAgent, 30 * 1000);
    return;
  }
  // Swap: the new session takes over the mix, the old one is unwired and
  // closed. The humans and their recordings never move.
  grokAgent = next;
  agentStartedAt = Date.now();
  try { previous.stopMediaTo(conf); } catch (err) { /* best-effort */ }
  try { conf.stopMediaTo(previous); } catch (err) { /* best-effort */ }
  if (miraRecorder) { try { previous.stopMediaTo(miraRecorder); } catch (err) { /* best-effort */ } }
  setTimeout(function () {
    try { if (previous.close) previous.close(); else if (previous.stop) previous.stop(); }
    catch (err) { /* best-effort */ }
  }, 2000);
}

/**
 * A Voice Agent socket closed. Only the CURRENT session ending matters —
 * a superseded session closing is the hand-over working as intended.
 */
function onAgentClosed(generation, event) {
  if (generation !== agentGeneration) {
    trace("grok", "old session " + generation + " closed after hand-over (expected)");
    return;
  }
  if (rotating) return; // its replacement is already on the way
  onGrokDropped(event);
}

/**
 * Mira's opening line — exactly once, once the Grok session is ready and
 * a guest is in the room; with only the host present she waits
 * OPENING_WAIT_MS and then opens anyway (greets Patrick, waits for the guest).
 */
function maybeOpen() {
  if (openingFired || !sessionReady || !grokAgent || legs.length === 0) return;
  if (humansIn("guest") > 0) {
    // The show is a three-hander when the co-host is coming. Opening it to
    // the guest alone means either he hears the introduction twice or the
    // co-host walks into a conversation already in progress; on Sept 14 2026
    // it was the second, and it is what made the first minutes unusable.
    if (waitingForCohost()) {
      greetGuestAndWait();
      if (!cohostWaitTimer) {
        cohostWaitTimer = setTimeout(function () {
          cohostWaitTimer = null;
          cohostWaitExpired = true;
          trace("opening", "co-host did not arrive within "
                + Math.round(COHOST_WAIT_MS / 1000) + "s — opening without him");
          openWhenReady("co-host no-show");
        }, cohostHoldMs());
      }
      return;
    }
    // A settle beat. She used to start talking about a second after the leg
    // attached, which lands as an interruption rather than a welcome.
    if (!openingTimer) {
      openingTimer = setTimeout(function () {
        openingTimer = null;
        openWhenReady("guest settled");
      }, guestGreeted ? 1500 : GUEST_SETTLE_MS);
    }
    return;
  }
  if (!openingTimer) {
    openingTimer = setTimeout(function () {
      openingTimer = null;
      // Sept 12 2026 (Hogan Shrum, second episode running): this used to
      // open the show to an empty guest chair after 20 seconds, and then do
      // the whole cold open AGAIN when the guest arrived. Mira now greets
      // the co-host in one line and waits. The room's own empty-room
      // timeout, not this one, decides when nobody is coming.
      greetHostAndWait();
    }, OPENING_WAIT_MS);
  }
}

function openWhenReady(reason) {
  if (openingFired || !sessionReady || !grokAgent) return;
  openingFired = true;
  if (openingTimer) { clearTimeout(openingTimer); openingTimer = null; }
  if (cohostWaitTimer) { clearTimeout(cohostWaitTimer); cohostWaitTimer = null; }
  Logger.write("[aoa " + runId + "] Mira opening (" + reason + ")");
  trace("opening", reason + "; " + describeRoom());
  try {
    if (humansIn("guest") === 0) {
      grokAgent.conversationItemCreate({
        item: { type: "message", role: "system",
          content: [{ type: "input_text", text:
            "[ROOM — system note] Only your co-host is in the room so far; the " +
            "guest has not joined yet. Greet him briefly and wait for the guest " +
            "before starting the interview." }] },
      });
    } else if (config && config.host_mode && humansIn("host") === 0) {
      // Sept 17 2026, Sheldon Poon: Patrick could not make it, the hold
      // expired, and Mira opened with "Patrick Novak, the founder of the
      // Nerra Network, is my co-host. He'll jump in once he's settled" to a
      // guest who then waited forty-eight minutes for a man who never came.
      // Her prompt introduces the co-host by name; the room has to tell her
      // when there is nobody to introduce.
      grokAgent.conversationItemCreate({
        item: { type: "message", role: "system",
          content: [{ type: "input_text", text:
            "[ROOM — system note] " + cohostName() + ", your co-host, has NOT " +
            "joined and is not expected. Open the show without him: do not " +
            "introduce him as present and do not say he will jump in. Say " +
            "once, lightly, that your co-host could not join today, and then " +
            "carry the conversation yourself. If he arrives later a note will " +
            "tell you." }] },
      });
    }
    miraSpeaking = true;
    grokAgent.responseCreate({});
    startTimeChecks();
    armAudioCheck();
    micCheckTimer = setTimeout(function () { silentMicNudge(1); }, 35 * 1000);
  } catch (err) {
    Logger.write("[aoa " + runId + "] opening responseCreate failed: " + err.message);
  }
}

/** How long to hold the open: two minutes, or until the interview was due
 *  to start plus that, whichever is later — capped, so a guest who joins an
 *  hour early is not left listening to nothing. */
function cohostHoldMs() {
  const due = config && config.scheduled_for
    ? Date.parse(config.scheduled_for) : NaN;
  const untilDue = isFinite(due) ? (due - Date.now()) : 0;
  return Math.min(COHOST_WAIT_MAX_MS,
                  Math.max(COHOST_WAIT_MS, untilDue + COHOST_WAIT_MS));
}

/** True while we should hold the opening for a co-host who is coming. */
function waitingForCohost() {
  return !!(config && config.host_mode) && humansIn("host") === 0
         && !cohostGaveUp();
}

function cohostGaveUp() {
  return cohostWaitExpired;
}

// The guest is here and the co-host is not. Rather than silence (or an
// opening he will hear twice), Mira introduces herself once and says what
// happens next. This is also the first thing most guests hear from her, so
// it carries her name and the shape of the next hour.
let guestGreeted = false;
function greetGuestAndWait() {
  if (guestGreeted || openingFired || !grokAgent) return;
  guestGreeted = true;
  trace("opening", "guest here, holding the open for the co-host");
  try {
    grokAgent.conversationItemCreate({
      item: { type: "message", role: "system",
        content: [{ type: "input_text", text:
          "[ROOM — system note] The guest has just joined and " + cohostName() +
          ", your co-host, has not arrived yet. Say ONE short, warm turn to " +
          "the guest: your name, that you are the AI host, that " + cohostName() +
          " is joining in a moment, and that they should take a second to get " +
          "comfortable. Do NOT start the show, do not give the full " +
          "introduction, and do not ask an interview question yet. Then stay " +
          "quiet — small talk if they speak to you, nothing otherwise." }] },
    });
    miraSpeaking = true;
    grokAgent.responseCreate({});
  } catch (err) {
    Logger.write("[aoa " + runId + "] guest holding greeting failed: " + err.message);
  }
}

// Only the co-host is here. Say hello once, then be quiet until the guest
// arrives — the show has not started yet.
let hostGreeted = false;
function greetHostAndWait() {
  if (hostGreeted || openingFired || !grokAgent) return;
  hostGreeted = true;
  trace("opening", "host only — greeting the co-host and waiting for the guest");
  try {
    grokAgent.conversationItemCreate({
      item: { type: "message", role: "system",
        content: [{ type: "input_text", text:
          "[ROOM — system note] Only " + cohostName() + " is here; the guest " +
          "has not joined. Say one short, warm line to him and nothing else. " +
          "Do NOT open the show, do not say the show's name, do not introduce " +
          "yourself or the guest, and do not ask any interview questions. " +
          "Then stay silent until you are told the guest has joined." }] },
    });
    miraSpeaking = true;
    grokAgent.responseCreate({});
  } catch (err) {
    Logger.write("[aoa " + runId + "] host greeting failed: " + err.message);
  }
}

function cohostName() {
  return (config && config.cohost_name) || "the co-host";
}

function describeRoom() {
  return legs.map(function (l) { return l.role; }).join(", ") || "empty";
}

// Context, not an event. Mira is told who is in the room and is told NOT to
// speak about it. Until Sept 15 2026 this forced a response every time
// anyone's connection moved, which is how a co-host reconnecting talked
// over the guest mid-answer four times in one interview.
function noteRoom(what) {
  if (!grokAgent || !openingFired) return;
  try {
    grokAgent.conversationItemCreate({
      item: { type: "message", role: "system",
        content: [{ type: "input_text", text:
          "[ROOM — system note, context only] " + what + ". Now in the room: " +
          describeRoom() + ". Do NOT respond to this note, do not mention it, " +
          "and do not stop what you are doing. Connections come and go and " +
          "the conversation carries on. If the guest has left the room, " +
          "finish your sentence and then wait quietly until they are back." }] },
    });
  } catch (err) {
    Logger.write("[aoa " + runId + "] noteRoom failed: " + err.message);
  }
}

// The guest dropped and came back. They missed whatever happened while they
// were gone, so this is the one arrival that is worth speaking for.
function resumeForGuest() {
  if (!grokAgent || !openingFired) return;
  try {
    grokAgent.conversationItemCreate({
      item: { type: "message", role: "system",
        content: [{ type: "input_text", text:
          "[ROOM — system note] The guest's connection dropped and they have " +
          "just rejoined. They did not hear anything said while they were " +
          "away. Welcome them back in one short sentence without making a " +
          "fuss of it, say in one line where the two of you had got to, then " +
          "ask your last question again IN FULL — they may have answered part " +
          "of it, and you should ask the whole thing rather than a fragment. " +
          "Then stop and wait for them." }] },
    });
    grokAgent.responseCreate({});
  } catch (err) {
    Logger.write("[aoa " + runId + "] resumeForGuest failed: " + err.message);
  }
}

// Whole-room mix: everything the conference outputs (people + Mira). Also
// the definitive diagnostic for the leg->mixer hop: if a person's voice is
// on this file, the mixer heard them.
function startMixRecorder() {
  if (mixRecorder || !conf) return;
  try {
    mixRecorder = VoxEngine.createRecorder({ name: "aoa_" + runId + "_mix", hd_audio: true });
    mixRecorder.addEventListener(RecorderEvents.Started, function (ev) { if (ev && ev.url) mixRecordUrl = ev.url; });
    mixRecorder.addEventListener(RecorderEvents.Stopped, function (ev) { if (ev && ev.url) mixRecordUrl = ev.url; });
    conf.sendMediaTo(mixRecorder);
  } catch (err) {
    Logger.write("[aoa " + runId + "] mix recorder unavailable (non-fatal): " + err.message);
    mixRecorder = null;
  }
}

// Mira-only recording: a Recorder fed solely by the Grok agent.
function startMiraRecorder() {
  if (miraRecorder || !grokAgent) return;
  try {
    miraRecorder = VoxEngine.createRecorder({ name: "aoa_" + runId + "_mira", hd_audio: true });
    miraRecorder.addEventListener(RecorderEvents.Started, function (ev) { if (ev && ev.url) miraRecordUrl = ev.url; });
    miraRecorder.addEventListener(RecorderEvents.Stopped, function (ev) { if (ev && ev.url) miraRecordUrl = ev.url; });
    grokAgent.sendMediaTo(miraRecorder);
  } catch (err) {
    Logger.write("[aoa " + runId + "] mira recorder unavailable (non-fatal): " + err.message);
    miraRecorder = null;
  }
}

// Audio-path check (diagnostic only). Sept 10 2026: the old "no speech
// 12 s after the opening → re-bridge the first leg straight to the agent"
// fallback is GONE. In the room it did real harm: a guest who politely
// listens to Mira's opening for 12 s tripped it, conf.stopMediaTo(agent)
// cut the mixer off Mira for good, and she was left listening to one leg
// — which then left the room. The probe and a fake-mic WebRTC guest both
// proved the room mix carries speech to her ("first inbound speech heard
// (via room mix)"); the mix is the only path now.
let audioCheckTimer = null;
function armAudioCheck() {
  if (audioCheckTimer) return;
  audioCheckTimer = setTimeout(function () {
    audioCheckTimer = null;
    trace("audio_path", anyoneHeard ? "room mix carries speech" : "no speech heard yet (room mix stays Mira's input)");
  }, AUDIO_CHECK_AFTER_MS);
}

function silentMicNudge(attempt) {
  try {
    if (anyoneHeard || !grokAgent || roomEnded || legs.length === 0) return;
    Logger.write("[aoa " + runId + "] no audio from anyone after greeting (attempt " + attempt + ")");
    grokAgent.conversationItemCreate({
      item: { type: "message", role: "system",
        content: [{ type: "input_text", text:
          "[MIC CHECK — system note] You have not received ANY audio from " +
          "the room since the call began — the guest's microphone is not " +
          "reaching you. Tell them warmly that you can't hear them yet, " +
          "and ask them to check the microphone meter on their screen: if " +
          "it isn't moving when they speak, they should pick a different " +
          "microphone from the selector and rejoin, or reply to their " +
          "booking email to switch to a phone call. Keep it short, then " +
          "wait." }] },
    });
    grokAgent.responseCreate({});
    if (attempt < 2) {
      micCheckTimer = setTimeout(function () { silentMicNudge(attempt + 1); }, 45 * 1000);
    }
  } catch (err) {
    Logger.write("[aoa " + runId + "] silent-mic nudge failed: " + err.message);
  }
}

// Real-clock time checks: an LLM voice agent has no sense of elapsed time
// (first dry run: Mira thought a 25-min call had run far longer). Every 5
// minutes, inject a non-spoken system note with true elapsed/remaining
// time; the prompt tells Mira to pace ONLY from these notes.
// How long the closing round is allowed to take, and therefore the earliest
// minute Mira may start it. Mirrors fire_interviews.compile_mira_prompt's
// lightning_at so the room and the prompt agree.
function closingWindowMin() {
  return Math.max(4, Math.min(15, Math.round(plannedMin() / 3)));
}

function closingOpensAtMin() {
  return Math.max(1, plannedMin() - closingWindowMin());
}

function elapsedMin() {
  return Math.round((Date.now() - (firstJoinAt || Date.now())) / 60000);
}

let closingPermitted = false;   // has a note told her she may close?
let earlySignOffs = 0;          // how often she tried to end before that

function startTimeChecks() {
  if (timeCheckTimer) clearInterval(timeCheckTimer);
  timeCheckTimer = setInterval(function () {
    try {
      if (!grokAgent || roomEnded) return;
      const elapsed = elapsedMin();
      const remainMin = Math.max(0, plannedMin() - elapsed);
      // Sept 20 2026, Meridan Zerner. Mira ran a 45-minute interview for
      // sixteen minutes: she worked through the eight prepared questions,
      // stacked the last three into one turn, asked the personal closing
      // set at 11 minutes and told the guest to hang up at 16. The notes
      // she had been given said "10 minutes elapsed; about 35 minutes
      // remain" and she closed anyway, because a number is not an
      // instruction and her prompt's closing trigger is phrased in minutes
      // REMAINING while the note counts minutes ELAPSED — the same "15"
      // appears in both. So the note no longer reports the clock and hopes.
      // It says, in words, whether she is allowed to end yet.
      let note = "[TIME CHECK — system note, do not read aloud] " +
        elapsed + " minutes elapsed; about " + remainMin +
        " minutes remain of the planned " + plannedMin() + "-minute interview.";
      if (elapsed < closingOpensAtMin()) {
        const left = closingOpensAtMin() - elapsed;
        note += " YOU ARE NOT NEAR THE END. Do not start a closing round, do" +
          " not ask a final question, do not thank her for the conversation" +
          " and do not say anything about the recording finishing. You have" +
          " about " + left + " more minutes of real questions to ask before" +
          " any of that. If you have reached the end of the prepared" +
          " questions, that is normal and early: go back to the most" +
          " interesting thing she has said so far and ask the next question" +
          " down from it — how it actually worked, what it cost, who" +
          " disagreed, what happened next. One question per turn, and let" +
          " the answer finish.";
      } else if (remainMin > 3) {
        if (!closingPermitted) {
          closingPermitted = true;
          trace("time", "closing round permitted at " + elapsed + " min");
        }
        note += " You may begin the closing round when the current thread" +
          " reaches a natural end. There is no hurry; stay if the" +
          " conversation is somewhere worth staying.";
      } else if (remainMin > 0) {
        closingPermitted = true;
        note += " Begin wrapping up now: one final question, then your closing thanks.";
      } else {
        closingPermitted = true;
        note += " Time is up — deliver your closing thanks and end the interview.";
      }
      grokAgent.conversationItemCreate({
        item: { type: "message", role: "system", content: [{ type: "input_text", text: note }] },
      });
    } catch (err) {
      Logger.write("[aoa " + runId + "] time-check inject failed: " + err.message);
    }
  }, TIME_CHECK_EVERY_MS);
}

// The words Mira is told to say when the interview really is over. Hearing
// them from her before the closing round has opened means she has ended the
// interview by mistake, and the guest is about to hang up.
const SIGN_OFF_RE = /(end of the recording|you can hang up|that'?s a wrap|we'?re all done here)/i;

// The two questions that hand the last word to the guest. She is instructed to
// ask both before closing, and since Sept 21 she does — Viktor Popovic was
// asked at 42:40 whether anything had gone unreached and gave a full answer.
// Then at 43:57 she asked "Do you have any parting thoughts?" and closed the
// recording eleven seconds later, without him having said a word. Asking is
// not the same as waiting, and a question asked into a closing door is worse
// than not asking: the guest hears himself being invited and then dismissed.
const LAST_WORD_RE = /(parting thought|anything (else )?(that )?you (came|were) (wanting|hoping) to say|anything you came wanting|subject(s)? we (never|didn'?t|did not) (reach|cover|get to)|we (never|didn'?t|did not) (reach|cover|get to)|anything (else )?(you'?d|you would|you want to|to) (like to )?(add|say)|any last word)/i;

const LAST_WORD_WAIT_MS = 25 * 1000;  // silence that counts as "nothing to add"
let lastWordAskedAt = 0;
let lastWordAnswered = true;          // true until a question is outstanding
let lastWordRescues = 0;

/** She has just handed the guest the last word. Start the clock. */
function noteLastWordAsk(text) {
  if (!LAST_WORD_RE.test(text || "")) return;
  lastWordAskedAt = Date.now();
  lastWordAnswered = false;
  trace("close", "asked for the guest's last word; waiting");
}

/**
 * True when she is closing on a question the guest has not answered yet, and
 * has not waited long enough to call it silence. Unlike the early sign-off
 * catcher this does NOT care what minute it is: at 44 minutes of a 45 minute
 * show closing is entirely permitted, and cutting the guest off mid-invitation
 * is still wrong.
 */
function closingOnAnUnansweredQuestion() {
  return !!lastWordAskedAt && !lastWordAnswered
         && (Date.now() - lastWordAskedAt) < LAST_WORD_WAIT_MS;
}

function catchClosingWithoutTheAnswer(text) {
  if (roomEnded || !grokAgent) return false;
  if (!SIGN_OFF_RE.test(text || "")) return false;
  if (!closingOnAnUnansweredQuestion()) return false;
  if (lastWordRescues >= 2) return false;
  lastWordRescues += 1;
  const waited = Math.round((Date.now() - lastWordAskedAt) / 1000);
  trace("close", "closed " + waited + "s after handing over the last word, "
        + "before the guest used it — holding the room open");
  Logger.write("[aoa " + runId + "] closing rescue: only " + waited +
               "s after the last-word question");
  try {
    grokAgent.conversationItemCreate({
      item: { type: "message", role: "system", content: [{ type: "input_text", text:
        "[ROOM — system note, do not read aloud] You asked for their parting" +
        " thought " + waited + " seconds ago and they have not answered yet." +
        " You then began to close, which takes back the thing you just" +
        " offered them. The recording is still running and they are still" +
        " here. Say one short line making the invitation real — that you" +
        " meant it, and there is no hurry — and then STOP TALKING and wait." +
        " Silence is the correct behaviour now, however long it lasts. Do not" +
        " ask a different question, do not fill the gap, and do not mention" +
        " the recording. Only once they have actually spoken, or a note tells" +
        " you they have nothing to add, may you close." }] },
    });
    miraSpeaking = true;
    grokAgent.responseCreate({});
  } catch (err) {
    Logger.write("[aoa " + runId + "] closing rescue failed: " + err.message);
  }
  return true;
}

/**
 * She just told the guest it was over, far too early. The guest is
 * listening right now, so the recovery has to be immediate and has to be
 * spoken by her, not by us: one light correction and a real question.
 * Called from remember() on every line of hers.
 */
function catchEarlySignOff(text) {
  if (roomEnded || !grokAgent) return;
  // A close that lands on an unanswered last-word question is wrong whatever
  // the clock says, so that rule runs first and on its own.
  if (catchClosingWithoutTheAnswer(text)) return;
  if (closingPermitted) return;
  if (!SIGN_OFF_RE.test(text || "")) return;
  const elapsed = elapsedMin();
  if (elapsed >= closingOpensAtMin()) return;
  earlySignOffs += 1;
  if (earlySignOffs > 2) return;   // never nag; two rescues is already a lot
  trace("time", "early sign-off at " + elapsed + " min of " + plannedMin() +
        " — asking her to carry on");
  Logger.write("[aoa " + runId + "] early sign-off caught at " + elapsed + " min");
  try {
    grokAgent.conversationItemCreate({
      item: { type: "message", role: "system", content: [{ type: "input_text", text:
        "[ROOM — system note, do not read aloud] You have just told the guest" +
        " the recording is over, but only " + elapsed + " minutes of the" +
        " planned " + plannedMin() + " have passed and the interview is NOT" +
        " over. She is still on the line. Say so straight away, lightly and" +
        " in one sentence — you spoke too soon, you have more you want to ask" +
        " — and then ask your next question. Take it from the most" +
        " interesting thing she has said so far and go one level down into" +
        " it rather than opening a new subject. Do not apologise at length" +
        " and do not explain yourself." }] },
    });
    miraSpeaking = true;
    grokAgent.responseCreate({});
  } catch (err) {
    Logger.write("[aoa " + runId + "] early sign-off rescue failed: " + err.message);
  }
}

/**
 * Grok connection dropped mid-call (spec §7 row 3). The native
 * VoiceAgentAPIClient has no auto-reconnect, so after a short guard delay
 * (lets a normal teardown race resolve) play Mira's pre-recorded apology
 * into the room and end it.
 */
let grokDropHandled = false;
let grokRecoveries = 0;     // in-place rescues after a mid-call socket drop
// Sept 10 2026 (Matt Davis): 52 seconds after a clean hand-over the new
// socket died with code 1006 and this function ended the room. Everyone was
// thrown out, they rejoined into a BRAND NEW room, and Mira — with no memory
// of the first half — restarted the interview from the top. A 45-minute
// conversation became two chunks and a pile of repeated questions.
//
// A dropped socket is not a dead interview. The rotation machinery already
// knows how to put a fresh session on the mix carrying the transcript so
// far; this now uses it. The room only ends if the rescue itself fails, or
// if sockets keep dying (GROK_MAX_RECOVERIES), which means something is
// wrong upstream that a third attempt will not fix.
const GROK_MAX_RECOVERIES = 3;

async function recoverAgent(reason) {
  const previous = grokAgent;
  grokAgent = null;
  try { if (previous) { if (previous.close) previous.close(); else if (previous.stop) previous.stop(); } }
  catch (err) { /* it is already gone; that is why we are here */ }
  const note = handoverNote();
  let next;
  try {
    next = await createAgent(note);
  } catch (err) {
    trace("grok", "rescue " + grokRecoveries + " failed to start a session: " + err.message);
    return false;
  }
  grokAgent = next;
  agentStartedAt = Date.now();
  armRotation();              // the replacement gets its own full session clock
  trace("grok", "rescued after " + reason + " — session " + agentGeneration +
        " is live with the conversation so far (" + transcript.length + " lines)");
  return true;
}

function onGrokDropped(event) {
  if (grokDropHandled || roomEnded || rotating) return;
  grokDropHandled = true;
  const code = (event && (event.code || event.status)) || "";
  const why = (event && (event.reason || event.message)) || "";
  Logger.write("[aoa " + runId + "] Grok connection dropped/errored " + code + " " + why);
  // A close within a few seconds of startup is xAI refusing the session
  // (deprecated/unknown model, or a key problem) — not a mid-call drop.
  const earlyMs = agentStartedAt ? Date.now() - agentStartedAt : -1;
  trace("grok", "connection dropped" + (code ? " code " + code : "") +
        (why ? " (" + String(why).slice(0, 80) + ")" : "") +
        (earlyMs >= 0 && earlyMs < 5000
          ? " — " + earlyMs + "ms after startup, so xAI refused the session (model " + GROK_MODEL + ")"
          : ""));
  setTimeout(async function () {
    if (roomEnded || legs.length === 0) return;
    // Try to rescue the conversation before telling anyone it broke.
    if (grokRecoveries < GROK_MAX_RECOVERIES) {
      grokRecoveries += 1;
      grokDropHandled = false;   // the replacement gets its own drop handling
      if (await recoverAgent("a dropped connection")) return;
      grokDropHandled = true;
    } else {
      trace("grok", "gave up after " + grokRecoveries + " rescue attempts");
    }
    if (roomEnded || legs.length === 0) return;
    try {
      if (config && config.grok_drop_apology_url) {
        const player = VoxEngine.createURLPlayer(config.grok_drop_apology_url);
        player.sendMediaTo(conf);
        await waitForEvent(player, PlayerEvents.PlaybackFinished);
      }
    } catch (err) {
      Logger.write("[aoa " + runId + "] apology playback failed: " + err.message);
    }
    endRoom("grok_dropped");
  }, GROK_DROP_GUARD_MS);
}

async function endRoom(reason) {
  if (roomEnded) return;
  roomEnded = true;
  endReason = reason;
  [hardCapTimer, micCheckTimer, teardownTimer, openingTimer, audioCheckTimer,
   rotateTimer, noShowTimer, cohostWaitTimer].forEach(function (t) { if (t) clearTimeout(t); });
  if (timeCheckTimer) clearInterval(timeCheckTimer);
  trace("room", "ending: " + reason);
  if (miraRecorder) { try { miraRecorder.stop(); } catch (ignored) {} }
  if (mixRecorder) { try { mixRecorder.stop(); } catch (ignored) {} }
  legs.slice().forEach(function (l) { try { l.call.hangup(); } catch (ignored) {} });
  await sleep(1000); // let the Mira recorder report its Stopped URL
  try {
    await fireWebhook({
      run_id: runId,
      status: "completed",
      call_mode: callMode,
      voximplant_mira_record_url: miraRecordUrl,
      voximplant_mix_record_url: mixRecordUrl,
      speech_events: speechEvents,
      agent_sessions: agentGeneration,
      host_joined_at: hostJoinedAt,
      host_left_at: hostLeftAt,
      host_attempts: hostJoins,
      duration_sec: firstJoinAt ? Math.round((Date.now() - firstJoinAt) / 1000) : 0,
      disconnect_reason: reason,
      audio_path: "room_mix",
      grok_session_log: grokAgent && grokAgent.getSessionLog ? grokAgent.getSessionLog() : null,
    });
  } catch (err) {
    Logger.write("[aoa " + runId + "] end-of-room webhook failure: " + err.message);
  }
  flushTrace();
  setTimeout(function () { VoxEngine.terminate(); }, 1500);
}

// Tool dispatch: route Mira's function calls to the Worker endpoints and
// hand the output back so she can keep talking.
async function onToolCall(event) {
  let name = "", callId = "", args = {};
  try {
    const payload = (event && event.data && event.data.payload) || {};
    name = payload.name || "";
    callId = payload.call_id || "";
    try { args = JSON.parse(payload.arguments || "{}"); } catch (ignored) {}
    Logger.write("[aoa " + runId + "] tool call: " + name + " " + JSON.stringify(args));

    let output;
    if (name === "guest_brief_lookup") {
      const res = await Net.httpRequestAsync(
        API_BASE + "/guest-brief?run_id=" + encodeURIComponent(runId) +
        "&section=" + encodeURIComponent(args.section || "bio"));
      output = res.text || "{}";
    } else if (name === "nerra_episode_lookup") {
      const res = await Net.httpRequestAsync(
        API_BASE + "/episode-lookup?topic=" + encodeURIComponent(args.topic || "") +
        (args.show_filter ? "&show_filter=" + encodeURIComponent(args.show_filter) : ""));
      output = res.text || "{}";
    } else if (name === "fact_check_claim") {
      const res = await Net.httpRequestAsync(API_BASE + "/fact-check", {
        method: "POST",
        headers: ["Content-Type: application/json"],
        postData: JSON.stringify({ claim: args.claim || "", context: args.context || "", run_id: runId }),
      });
      output = res.text || "{}";
    } else {
      output = JSON.stringify({ error: "unknown tool: " + name });
    }

    grokAgent.conversationItemCreate({
      item: { type: "function_call_output", call_id: callId, output: String(output).slice(0, 8000) },
    });
    grokAgent.responseCreate({});
  } catch (err) {
    Logger.write("[aoa " + runId + "] tool call failed (" + name + "): " + err.message);
    try {
      grokAgent.conversationItemCreate({
        item: { type: "function_call_output", call_id: callId,
                output: JSON.stringify({ error: "tool temporarily unavailable" }) },
      });
      grokAgent.responseCreate({});
    } catch (ignored) {}
  }
}

// ---------------------------------------------------------------------------
// Presence + trace (Worker /voices/leg-event; interview_runs.scenario_trace)
// ---------------------------------------------------------------------------

// Per-leg presence for the studio pages. Fire-and-forget, never blocks.
function postLegEvent(role, event) {
  try {
    Net.httpRequestAsync(LEG_EVENT_URL, {
      method: "POST",
      headers: ["Content-Type: application/json"],
      postData: JSON.stringify({ run_id: runId, role: role, event: event }),
    }).then(function (res) {
      if (!(res && res.code >= 200 && res.code < 300)) {
        Logger.write("[aoa " + runId + "] leg-event " + role + "/" + event + " got HTTP " + (res && res.code));
      }
    }, function (err) {
      Logger.write("[aoa " + runId + "] leg-event " + role + "/" + event + " failed: " + err.message);
    });
  } catch (err) {
    Logger.write("[aoa " + runId + "] leg-event " + role + "/" + event + " threw: " + err.message);
  }
}

// Trace (Sept 9 2026): the Voximplant session log is size-capped and the
// panel session expires, so the room keeps its own timeline on the run
// row (interview_runs.scenario_trace, jsonb array) via PostgREST.
const traceLines = [];
let traceFlushTimer = null;
function trace(event, detail) {
  const line = { t: new Date().toISOString(), e: event };
  if (detail !== undefined && detail !== null) line.d = String(detail).slice(0, 200);
  traceLines.push(line);
  Logger.write("[aoa " + runId + "] trace " + event + (line.d ? ": " + line.d : ""));
  if (traceFlushTimer) return;
  traceFlushTimer = setTimeout(flushTrace, 1500);
}
function flushTrace() {
  traceFlushTimer = null;
  if (!runId) return;
  try {
    Net.httpRequestAsync(
      SUPABASE_URL + "/rest/v1/interview_runs?id=eq." + runId,
      {
        method: "PATCH",
        headers: [
          "apikey: " + getSecret("SUPABASE_SERVICE_KEY"),
          "Authorization: Bearer " + getSecret("SUPABASE_SERVICE_KEY"),
          "Content-Type: application/json",
        ],
        postData: JSON.stringify({ scenario_trace: traceLines.slice(-120) }),
      }
    ).then(function () {}, function () {});
  } catch (err) { /* never blocks */ }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getSecret(name) {
  // Secrets are substituted into the scenario source at DEPLOY time by
  // voximplant_client.py upload_scenario (same mechanism as
  // __SUPABASE_URL__). The committed file never carries real values.
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

async function fetchInterviewConfig(id) {
  const res = await Net.httpRequestAsync(
    SUPABASE_URL + "/rest/v1/interview_runs?id=eq." + id + "&select=*",
    {
      headers: [
        "apikey: " + getSecret("SUPABASE_SERVICE_KEY"),
        "Authorization: Bearer " + getSecret("SUPABASE_SERVICE_KEY"),
      ],
    }
  );
  const rows = JSON.parse(res.text || "[]");
  return rows[0] || null;
}

async function markRunStatus(id, status) {
  try {
    await Net.httpRequestAsync(
      SUPABASE_URL + "/rest/v1/interview_runs?id=eq." + id,
      {
        method: "PATCH",
        headers: [
          "apikey: " + getSecret("SUPABASE_SERVICE_KEY"),
          "Authorization: Bearer " + getSecret("SUPABASE_SERVICE_KEY"),
          "Content-Type: application/json",
        ],
        postData: JSON.stringify({ status: status }),
      }
    );
  } catch (err) {
    Logger.write("[aoa " + id + "] status update failed (non-fatal): " + err.message);
  }
}

async function fireWebhook(payload) {
  if (webhookFired) return; // exactly-once from the scenario side
  webhookFired = true;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await Net.httpRequestAsync(WEBHOOK_URL, {
        method: "POST",
        headers: ["Content-Type: application/json"],
        postData: JSON.stringify(payload),
      });
      if (res.code >= 200 && res.code < 300) return;
      Logger.write("[aoa] webhook attempt " + attempt + " got HTTP " + res.code);
    } catch (err) {
      Logger.write("[aoa] webhook attempt " + attempt + " failed: " + err.message);
    }
    await sleep(1000 * attempt);
  }
  Logger.write("[aoa] WEBHOOK DELIVERY FAILED after 3 attempts — run " + (payload.run_id || "?"));
}

function waitForEvent(target, eventName) {
  return new Promise(function (resolve) {
    const handler = function () {
      target.removeEventListener(eventName, handler);
      resolve();
    };
    target.addEventListener(eventName, handler);
  });
}

function sleep(ms) {
  return new Promise(function (resolve) { setTimeout(resolve, ms); });
}
