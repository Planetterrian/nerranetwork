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
const HARD_CAP_MS = 50 * 60 * 1000;                // spec §11.8: 50-min hard cap
const GROK_DROP_GUARD_MS = 1500;                   // spec §7: teardown-race guard
const PLANNED_MIN = 45;            // soft interview length the prompt paces to
const TIME_CHECK_EVERY_MS = 5 * 60 * 1000;
const ROOM_PREFIX = "room-";       // callConference id = ROOM_PREFIX + run id (rule ^room-.*)
const REJOIN_GRACE_MS = 90 * 1000; // room stays up this long after the last human leaves
const OPENING_WAIT_MS = 20 * 1000; // Mira opens when a guest is in, or after 20 s with only the host
const FALLBACK_AFTER_MS = 12 * 1000; // no speech via the mix → bridge the first guest directly
const ROLES = { guest: true, host: true };

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
  if (!custom.run_id) return; // inbound session — CallAlerting takes over.

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

// ===========================================================================
// ROOM SESSION
// ===========================================================================

let conf = null;            // the mixer (VoxEngine.createConference)
let config = null;          // interview_runs row
let grokAgent = null;
let legs = [];              // [{ id, role, call, joinedAt }]
let legSeq = 0;
let roomReady = null;       // Promise: config loaded + mixer created
let firstJoinAt = null;     // Date.now() of the first human in the room
let hostJoinedAt = null;    // ISO of the FIRST host join
let hostLeftAt = null;      // ISO of the last host drop
let hostJoins = 0;
let hardCapTimer = null;
let timeCheckTimer = null;
let micCheckTimer = null;
let teardownTimer = null;
let openingTimer = null;
let fallbackTimer = null;
let miraRecorder = null;
let miraRecordUrl = null;
let sessionReady = false;   // Grok SessionUpdated received (media bridged)
let openingFired = false;   // Mira opens exactly once
let anyoneHeard = false;    // first InputAudioBufferSpeechStarted
let directBridge = false;   // fallback engaged (first guest -> agent directly)
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
  await markRunStatus(runId, "in_progress");
  // The mixer. hd_audio keeps the mix at Opus wideband so Mira's input and
  // the per-person recordings don't get narrowband-downmixed.
  conf = VoxEngine.createConference({ hd_audio: true });
  trace("room", "opened (" + callMode + "); mixer via sendMediaBetween");
  hardCapTimer = setTimeout(function () {
    Logger.write("[aoa " + runId + "] hard cap reached, ending room");
    endRoom("hard_cap");
  }, HARD_CAP_MS);
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
    }
    trace("leg", role + " #" + leg.id + " joined (" + legs.length + " in room)");
    postLegEvent(role, "joined");
    if (openingFired) {
      announce(role + " joined");
    } else {
      maybeOpen();
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
      announce(role + " left the room");
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
function scheduleTeardown() {
  if (teardownTimer || roomEnded) return;
  trace("room", "empty — ending in " + (REJOIN_GRACE_MS / 1000) + "s unless someone rejoins");
  teardownTimer = setTimeout(function () {
    teardownTimer = null;
    if (legs.length === 0) endRoom("normal");
  }, REJOIN_GRACE_MS);
}

async function startAgent() {
  try {
    // Grok Voice Agent with Mira's compiled persona. No explicit model:
    // xAI's Voice Agent API default is current post May 31 2026.
    grokAgent = await Grok.createVoiceAgentAPIClient({
      xAIApiKey: getSecret("XAI_API_KEY"),
      onWebSocketClose: onGrokDropped,
    });
    trace("grok", "agent created");

    grokAgent.addEventListener(Grok.VoiceAgentAPIEvents.ConversationCreated, function () {
      // Voice presets are capitalized on the Voice Agent API ("Ara");
      // the DB stores lowercase ("ara") for TTS parity.
      const preset = (config.voice_preset || "ara");
      grokAgent.sessionUpdate({
        session: {
          voice: preset.charAt(0).toUpperCase() + preset.slice(1),
          turn_detection: { type: "server_vad" },
          instructions: config.mira_system_prompt,
          tools: config.tools || [],
        },
      });
    });

    grokAgent.addEventListener(Grok.VoiceAgentAPIEvents.SessionUpdated, function () {
      try {
        // Bridge Mira <-> the mix: she hears everyone (minus herself),
        // everyone hears her. Audio-conferencing API (sendMediaBetween),
        // not Conference.add endpoints — see the file header.
        VoxEngine.sendMediaBetween(grokAgent, conf);
        trace("grok", "session updated; agent<->room mix bridged");
        startMiraRecorder();
        sessionReady = true;
        maybeOpen();
      } catch (err) {
        Logger.write("[aoa " + runId + "] media-bridge failure: " + err.message);
        endRoom("media_bridge_failed");
      }
    });

    // Barge-in: flush Mira's buffered audio the moment anyone speaks.
    grokAgent.addEventListener(Grok.VoiceAgentAPIEvents.InputAudioBufferSpeechStarted, function () {
      if (!anyoneHeard) trace("grok", "first inbound speech heard" + (directBridge ? " (direct bridge)" : " (via room mix)"));
      anyoneHeard = true;
      if (grokAgent) grokAgent.clearMediaBuffer();
    });
    try {
      if (Grok.VoiceAgentAPIEvents.ResponseDone) {
        grokAgent.addEventListener(Grok.VoiceAgentAPIEvents.ResponseDone, function () { trace("grok", "response done"); });
      }
    } catch (err) { /* event names differ across connector versions */ }

    // Mira's in-call tools — WITHOUT this handler a tool call stalls her
    // mid-conversation forever (the request is never answered).
    grokAgent.addEventListener(Grok.VoiceAgentAPIEvents.ResponseFunctionCallArgumentsDone, onToolCall);
    grokAgent.addEventListener(Grok.VoiceAgentAPIEvents.WebSocketError, onGrokDropped);
  } catch (err) {
    Logger.write("[aoa " + runId + "] agent startup failure: " + err.message);
    trace("grok", "agent startup failed: " + err.message);
    endRoom("agent_startup_failed");
  }
}

/**
 * Mira's opening line — exactly once, once the Grok session is ready and
 * a guest is in the room; with only the host present she waits
 * OPENING_WAIT_MS and then opens anyway (greets Patrick, waits for the guest).
 */
function maybeOpen() {
  if (openingFired || !sessionReady || !grokAgent || legs.length === 0) return;
  if (humansIn("guest") > 0) return openWhenReady("guest in the room");
  if (!openingTimer) {
    openingTimer = setTimeout(function () {
      openingTimer = null;
      openWhenReady("host only, wait timed out");
    }, OPENING_WAIT_MS);
  }
}

function openWhenReady(reason) {
  if (openingFired || !sessionReady || !grokAgent) return;
  openingFired = true;
  if (openingTimer) { clearTimeout(openingTimer); openingTimer = null; }
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
    }
    grokAgent.responseCreate({});
    startTimeChecks();
    armAudioFallback();
    micCheckTimer = setTimeout(function () { silentMicNudge(1); }, 35 * 1000);
  } catch (err) {
    Logger.write("[aoa " + runId + "] opening responseCreate failed: " + err.message);
  }
}

function describeRoom() {
  return legs.map(function (l) { return l.role; }).join(", ") || "empty";
}

// Non-spoken system note when someone joins or leaves mid-conversation.
function announce(what) {
  if (!grokAgent || !openingFired) return;
  try {
    grokAgent.conversationItemCreate({
      item: { type: "message", role: "system",
        content: [{ type: "input_text", text:
          "[ROOM — system note] " + what + ". Now in the room: " + describeRoom() +
          ". Acknowledge in a few words if it matters, then carry on." }] },
    });
    grokAgent.responseCreate({});
  } catch (err) {
    Logger.write("[aoa " + runId + "] announce failed: " + err.message);
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

// Audio-path fallback: if Grok reports no inbound speech within
// FALLBACK_AFTER_MS of the opening, bridge the first guest straight to the
// agent (the path proven on Sept 9). Everyone still hears each other and
// Mira through the room; only Mira's INPUT becomes that one guest.
function armAudioFallback() {
  if (fallbackTimer) return;
  fallbackTimer = setTimeout(function () {
    fallbackTimer = null;
    if (anyoneHeard || directBridge || !grokAgent || roomEnded) {
      trace("audio_path", anyoneHeard ? "room mix carries speech" : "fallback skipped");
      return;
    }
    const guest = legs.filter(function (l) { return l.role === "guest"; })[0] || legs[0];
    if (!guest) { trace("audio_path", "nobody to bridge"); return; }
    try {
      try { conf.stopMediaTo(grokAgent); } catch (err) { /* may not be wired */ }
      guest.call.sendMediaTo(grokAgent);
      directBridge = true;
      trace("audio_path", "FALLBACK " + guest.role + " #" + guest.id + "->agent direct (no speech heard " + (FALLBACK_AFTER_MS / 1000) + "s after opening)");
      setTimeout(function () {
        try { if (grokAgent && !anyoneHeard) grokAgent.responseCreate({}); } catch (err) { /* best-effort */ }
      }, 2500);
    } catch (err) {
      trace("audio_path", "fallback failed: " + err.message);
    }
  }, FALLBACK_AFTER_MS);
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
function startTimeChecks() {
  if (timeCheckTimer) clearInterval(timeCheckTimer);
  timeCheckTimer = setInterval(function () {
    try {
      if (!grokAgent || roomEnded) return;
      const elapsedMin = Math.round((Date.now() - (firstJoinAt || Date.now())) / 60000);
      const remainMin = Math.max(0, PLANNED_MIN - elapsedMin);
      let note = "[TIME CHECK — system note, do not read aloud] " +
        elapsedMin + " minutes elapsed; about " + remainMin +
        " minutes remain of the planned " + PLANNED_MIN + "-minute interview.";
      if (remainMin <= 5 && remainMin > 0) {
        note += " Begin wrapping up now: one final question, then your closing thanks.";
      } else if (remainMin === 0) {
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

/**
 * Grok connection dropped mid-call (spec §7 row 3). The native
 * VoiceAgentAPIClient has no auto-reconnect, so after a short guard delay
 * (lets a normal teardown race resolve) play Mira's pre-recorded apology
 * into the room and end it.
 */
let grokDropHandled = false;
function onGrokDropped() {
  if (grokDropHandled || roomEnded) return;
  grokDropHandled = true;
  Logger.write("[aoa " + runId + "] Grok connection dropped/errored");
  trace("grok", "connection dropped");
  setTimeout(async function () {
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
  [hardCapTimer, micCheckTimer, teardownTimer, openingTimer, fallbackTimer].forEach(function (t) { if (t) clearTimeout(t); });
  if (timeCheckTimer) clearInterval(timeCheckTimer);
  trace("room", "ending: " + reason);
  if (miraRecorder) { try { miraRecorder.stop(); } catch (ignored) {} }
  legs.slice().forEach(function (l) { try { l.call.hangup(); } catch (ignored) {} });
  await sleep(1000); // let the Mira recorder report its Stopped URL
  try {
    await fireWebhook({
      run_id: runId,
      status: "completed",
      call_mode: callMode,
      voximplant_mira_record_url: miraRecordUrl,
      host_joined_at: hostJoinedAt,
      host_left_at: hostLeftAt,
      host_attempts: hostJoins,
      duration_sec: firstJoinAt ? Math.round((Date.now() - firstJoinAt) / 1000) : 0,
      disconnect_reason: reason,
      audio_path: directBridge ? "direct" : "room_mix",
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
