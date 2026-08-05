/**
 * The Age of AI — live interview scenario (Nerra Voices, spec §3).
 *
 * Runs on Voximplant cloud (VoxEngine V8 JS). One scenario run = one
 * interview, in either call mode:
 *
 *  - WEBRTC (default, July 2026): the guest joins from the browser studio
 *    page (age-of-ai-studio.html) via the Voximplant Web SDK. The inbound
 *    call arrives with an X-Run-Id header; we answer, record WITH VIDEO
 *    (guest camera → MP4, H.264) plus the dual-track stereo audio, and
 *    bridge to the Grok Voice Agent. Full-bandwidth Opus audio — the fix
 *    for dry-run 1's rough PSTN guest sound.
 *  - PSTN (fallback): fired by pipelines/voices/fire_interviews.py via the
 *    Management API (StartScenarios) with customData {"run_id": ...};
 *    outbound call to the guest's phone, audio-only recording.
 *
 * All call config (guest phone, caller id, compiled Mira prompt, tools,
 * voice preset) is pulled from Supabase so the fire step / studio page stay
 * thin triggers and the run row is the single source of truth.
 *
 * Secrets: SUPABASE_SERVICE_KEY and XAI_API_KEY are substituted into the
 * deployed copy at deploy time (upload_scenario placeholder substitution,
 * like __SUPABASE_URL__) — never hardcode them here.
 *
 * Deploy: voximplant/api_clients/voximplant_client.py upload_scenario().
 */

// Grok Voice Agent connector — native Voximplant module (enable the
// connector once in the Voximplant panel; spec phase 1). API shape
// verified July 2026 against voximplant/grok-voice-agent-example +
// docs.voximplant.ai: Modules.Grok / Grok.createVoiceAgentAPIClient.
require(Modules.Grok);
// Recorder module: used ONLY for the separate video recorder in WebRTC
// mode (the primary audio recording stays call.record — see below).
require(Modules.Recorder);

const SUPABASE_URL = "__SUPABASE_URL__";           // substituted at deploy time
const API_BASE = "https://api.nerranetwork.com/voices";
const WEBHOOK_URL = API_BASE + "/interview-complete";
const HARD_CAP_MS = 50 * 60 * 1000;                // spec §11.8: 50-min hard cap
const GROK_DROP_GUARD_MS = 1500;                   // spec §7: teardown-race guard
const PLANNED_MIN = 45;            // soft interview length the prompt paces to
const TIME_CHECK_EVERY_MS = 5 * 60 * 1000;

let runId = null;
let call = null;
let grokAgent = null;
let webhookFired = false;
let hardCapTimer = null;
let recordUrl = null;      // delivered via CallEvents.RecordStarted (no getter API)
let connectedAt = null;    // Call has no getDuration(); compute from timestamps
let timeCheckTimer = null; // periodic real-clock injections (Mira has no clock)
let callMode = "pstn";     // "pstn" | "webrtc" — set by whichever entry fires
let videoRecorder = null;  // separate WebRTC-mode video recorder
let guestHeard = false;    // set on first InputAudioBufferSpeechStarted
let micCheckTimer = null;  // silent-mic detection
let videoRecordUrl = null;

// ---------------------------------------------------------------------------
// Entry 1: outbound PSTN (fallback mode) — StartScenarios with customData.
// Inbound WebRTC sessions also fire AppEvents.Started (with no customData);
// they simply return here and are handled by CallAlerting below.
// ---------------------------------------------------------------------------

VoxEngine.addEventListener(AppEvents.Started, async function () {
  const custom = JSON.parse(VoxEngine.customData() || "{}");
  if (!custom.run_id) return; // WebRTC guest joining — CallAlerting takes over.

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

  await markRunStatus(runId, "in_progress");
  call = VoxEngine.callPSTN(config.guest_phone, config.caller_id);
  call.addEventListener(CallEvents.Connected, function () {
    beginInterview(config, /* withVideo = */ false);
  });
  attachEndHandlers();
});

// ---------------------------------------------------------------------------
// Entry 2: inbound WebRTC from the studio page (default mode, July 2026).
// The Web SDK call carries X-Run-Id in its extra headers.
// ---------------------------------------------------------------------------

VoxEngine.addEventListener(AppEvents.CallAlerting, async function (e) {
  callMode = "webrtc";
  call = e.call;
  const headers = e.headers || {};
  runId = headers["X-Run-Id"] || headers["x-run-id"] || null;

  let config;
  try {
    if (!runId) throw new Error("inbound studio call missing X-Run-Id header");
    config = await fetchInterviewConfig(runId);
    if (!config) throw new Error("no interview_runs row for " + runId);
  } catch (err) {
    Logger.write("[aoa] inbound startup failure: " + err.message);
    await fireWebhook({ run_id: runId, status: "failed", reason: "startup: " + err.message });
    try { e.call.reject(); } catch (ignored) {}
    return VoxEngine.terminate();
  }

  await markRunStatus(runId, "in_progress");
  call.addEventListener(CallEvents.Connected, function () {
    beginInterview(config, /* withVideo = */ true);
  });
  attachEndHandlers();
  call.answer();
});

// ---------------------------------------------------------------------------
// Shared interview flow (both call modes converge here on Connected)
// ---------------------------------------------------------------------------

async function beginInterview(config, withVideo) {
  try {
    // 1. Recording — call.record({stereo:true}) puts guest→cloud audio on
    //    one channel and cloud→guest (Mira + played clips) on the other.
    //    NOTE: VoxEngine.createRecorder's stereo param records MIXED
    //    streams in both channels and can never separate participants
    //    (verified July 2026) — only Call.record gives the per-channel
    //    split the editorial pipeline's per-channel Whisper STT depends
    //    on. video:true (WebRTC mode) additionally captures the guest's
    //    camera into the same recording (H.264 → MP4); post-processing
    //    extracts the audio and stores the video URL for future YouTube
    //    use. Started before the disclosure so consent is on tape.
    connectedAt = Date.now();
    call.addEventListener(CallEvents.RecordStarted, function (e) {
      if (e && e.url) recordUrl = e.url;
    });
    // AUDIO stays a dedicated audio-only recording in BOTH modes: dry-run
    // 2 (July 20 2026) proved that video:true on call.record collapses
    // the audio to a single mono mix (WebM/Opus, channels=1), destroying
    // the per-participant stereo split the diarization depends on.
    call.record({
      name: "aoa_" + runId,
      stereo: true,
      hd_audio: true,
    });
    // VIDEO (WebRTC mode) records on a SEPARATE recorder — guest camera
    // plus the mixed conversation audio, for the future YouTube version.
    // Best-effort: a video-recorder failure never blocks the interview.
    if (withVideo) {
      try {
        videoRecorder = VoxEngine.createRecorder({
          name: "aoa_" + runId + "_video",
          video: true,
        });
        videoRecorder.addEventListener(RecorderEvents.Started, function (e) {
          if (e && e.url) videoRecordUrl = e.url;
        });
        videoRecorder.addEventListener(RecorderEvents.Stopped, function (e) {
          if (e && e.url) videoRecordUrl = e.url;
        });
        call.sendMediaTo(videoRecorder);
      } catch (e) {
        Logger.write("[aoa " + runId + "] video recorder unavailable (non-fatal): " + e.message);
        videoRecorder = null;
      }
    }

    // 2. Recording-consent disclosure — pre-generated Mira clip from R2
    //    (spec §11.2; wording confirmed by Patrick before launch).
    if (config.recording_disclosure_url) {
      call.startPlayback(config.recording_disclosure_url);
      await waitForEvent(call, CallEvents.PlaybackFinished);
    }

    // 3. Grok Voice Agent with Mira's compiled persona. No explicit
    //    model: xAI's Voice Agent API default is current post May 31 2026
    //    (per voximplant/grok-voice-agent-example).
    grokAgent = await Grok.createVoiceAgentAPIClient({
      xAIApiKey: getSecret("XAI_API_KEY"),
      onWebSocketClose: onGrokDropped,
    });

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
        // 4. Bridge guest <-> Mira; Mira opens the conversation.
        VoxEngine.sendMediaBetween(call, grokAgent);
        if (videoRecorder) {
          try { grokAgent.sendMediaTo(videoRecorder); } catch (e) {
            Logger.write("[aoa " + runId + "] mira->video-recorder failed (non-fatal): " + e.message);
          }
        }
        grokAgent.responseCreate({});
        startTimeChecks();
      } catch (e) {
        Logger.write("[aoa " + runId + "] media-bridge failure: " + e.message);
        call.hangup();
      }
    });

    // Telephony-natural barge-in: flush Mira's buffered audio the moment
    // the guest starts speaking. Also feeds the silent-mic detector.
    grokAgent.addEventListener(Grok.VoiceAgentAPIEvents.InputAudioBufferSpeechStarted, function () {
      guestHeard = true;
      if (grokAgent) grokAgent.clearMediaBuffer();
    });

    // Silent-mic detection (Aug 5 2026, Dan Perra dry run: guest heard
    // Mira fine, his mic never reached us, and the call limped on in
    // one-way silence). If Grok hears NOTHING from the guest shortly
    // after the greeting, Mira says so and points at the on-screen mic
    // meter — twice, then keeps waiting rather than hanging up.
    micCheckTimer = setTimeout(function () { silentMicNudge(1); }, 35 * 1000);

    // 5. Mira's in-call tools — WITHOUT this handler a tool call stalls
    //    her mid-conversation forever (the request is never answered).
    grokAgent.addEventListener(Grok.VoiceAgentAPIEvents.ResponseFunctionCallArgumentsDone, onToolCall);

    grokAgent.addEventListener(Grok.VoiceAgentAPIEvents.WebSocketError, onGrokDropped);

    // 6. Safety hard cap (Mira's prompt soft-wraps at 45; spec §11.8).
    hardCapTimer = setTimeout(function () {
      if (call && call.state() !== "DISCONNECTED") {
        Logger.write("[aoa " + runId + "] hard cap reached, ending call");
        call.hangup();
      }
    }, HARD_CAP_MS);
  } catch (e) {
    Logger.write("[aoa " + runId + "] connected-handler failure: " + e.message);
    call.hangup();
  }
}

function silentMicNudge(attempt) {
  try {
    if (guestHeard || !grokAgent || !call || call.state() === "DISCONNECTED") return;
    Logger.write("[aoa " + runId + "] no guest audio after greeting (attempt " + attempt + ")");
    grokAgent.conversationItemCreate({
      item: { type: "message", role: "system",
        content: [{ type: "input_text", text:
          "[MIC CHECK — system note] You have not received ANY audio from " +
          "the guest since the call began — their microphone is not " +
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
  } catch (e) {
    Logger.write("[aoa " + runId + "] silent-mic nudge failed: " + e.message);
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
      if (!grokAgent || !call || call.state() === "DISCONNECTED") return;
      const elapsedMin = Math.round((Date.now() - connectedAt) / 60000);
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
        item: {
          type: "message",
          role: "system",
          content: [{ type: "input_text", text: note }],
        },
      });
    } catch (e) {
      Logger.write("[aoa " + runId + "] time-check inject failed: " + e.message);
    }
  }, TIME_CHECK_EVERY_MS);
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
        postData: JSON.stringify({
          claim: args.claim || "", context: args.context || "", run_id: runId,
        }),
      });
      output = res.text || "{}";
    } else {
      output = JSON.stringify({ error: "unknown tool: " + name });
    }

    grokAgent.conversationItemCreate({
      item: { type: "function_call_output", call_id: callId, output: String(output).slice(0, 8000) },
    });
    grokAgent.responseCreate({});
  } catch (e) {
    Logger.write("[aoa " + runId + "] tool call failed (" + name + "): " + e.message);
    try {
      grokAgent.conversationItemCreate({
        item: { type: "function_call_output", call_id: callId,
                output: JSON.stringify({ error: "tool temporarily unavailable" }) },
      });
      grokAgent.responseCreate({});
    } catch (ignored) {}
  }
}

// End-of-call handlers, shared by both entries.
function attachEndHandlers() {
  call.addEventListener(CallEvents.Disconnected, async function () {
    if (hardCapTimer) clearTimeout(hardCapTimer);
    if (timeCheckTimer) clearInterval(timeCheckTimer);
    if (micCheckTimer) clearTimeout(micCheckTimer);
    try {
      // The recording stops automatically on disconnect; the durable copy
      // happens in GitHub Actions (Net.httpRequest can't stream multi-MB
      // audio reliably from a scenario).
      if (videoRecorder) { try { videoRecorder.stop(); } catch (ignored) {} }
      await fireWebhook({
        run_id: runId,
        status: "completed",
        call_mode: callMode,
        voximplant_record_url: recordUrl,
        voximplant_video_url: videoRecordUrl,
        duration_sec: connectedAt
          ? Math.round((Date.now() - connectedAt) / 1000)
          : 0,
        disconnect_reason: "normal",
        grok_session_log: grokAgent && grokAgent.getSessionLog
          ? grokAgent.getSessionLog()
          : null,
      });
    } catch (e) {
      Logger.write("[aoa " + runId + "] disconnect-handler failure: " + e.message);
      await fireWebhook({ run_id: runId, status: "failed", reason: "post-call: " + e.message });
    }
    VoxEngine.terminate();
  });

  call.addEventListener(CallEvents.Failed, async function (event) {
    // Guest didn't answer / call failed → Worker retry ladder re-dials
    // (PSTN) or the guest can rejoin from the studio page (WebRTC).
    if (hardCapTimer) clearTimeout(hardCapTimer);
    await fireWebhook({
      run_id: runId,
      status: "failed",
      call_mode: callMode,
      reason: "call_failed: " + (event.reason || event.code || "unknown"),
    });
    VoxEngine.terminate();
  });
}

/**
 * Grok connection dropped mid-call (spec §7 row 3). The native
 * VoiceAgentAPIClient has no auto-reconnect, so a long grace window is
 * just dead air for the guest: after a short guard delay (lets a normal
 * teardown race resolve — the socket also closes when WE hang up), play
 * Mira's pre-recorded apology and end. The Disconnected handler then
 * fires the normal webhook with whatever was recorded.
 */
let grokDropHandled = false;
function onGrokDropped() {
  if (grokDropHandled) return;
  grokDropHandled = true;
  Logger.write("[aoa " + runId + "] Grok connection dropped/errored");
  setTimeout(async function () {
    if (!call || call.state() === "DISCONNECTED") return;
    Logger.write("[aoa " + runId + "] guest still on line — apologizing and ending");
    try {
      const cfg = await fetchInterviewConfig(runId);
      if (cfg && cfg.grok_drop_apology_url) {
        call.startPlayback(cfg.grok_drop_apology_url);
        await waitForEvent(call, CallEvents.PlaybackFinished);
      }
    } catch (e) {
      Logger.write("[aoa " + runId + "] apology playback failed: " + e.message);
    }
    call.hangup();
  }, GROK_DROP_GUARD_MS);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getSecret(name) {
  // Secrets are substituted into the scenario source at DEPLOY time by
  // voximplant_client.py upload_scenario (same mechanism as
  // __SUPABASE_URL__). The committed file never carries real values.
  // NOTE: VoxEngine has no Application.customData() — the original
  // application-custom-data design was written from spec and does not
  // exist in the live API (verified July 2026).
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
  } catch (e) {
    Logger.write("[aoa " + id + "] status update failed (non-fatal): " + e.message);
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
    } catch (e) {
      Logger.write("[aoa] webhook attempt " + attempt + " failed: " + e.message);
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
