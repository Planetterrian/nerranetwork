/**
 * The Age of AI — live interview scenario (Nerra Voices, spec §3).
 *
 * Runs on Voximplant cloud (VoxEngine V8 JS). One scenario run = one
 * interview: outbound PSTN call to the guest, bridge to a Grok Voice Agent
 * running Mira's persona, dual-track stereo recording, webhook on hangup.
 *
 * Fired by pipelines/voices/fire_interviews.py via the Voximplant
 * Management API (StartScenarios) with customData = JSON:
 *   { "run_id": "<interview_runs.id>" }
 * All call config (guest phone, caller id, compiled Mira prompt, tools,
 * voice preset) is pulled from Supabase at start so the fire step stays a
 * thin trigger and the run row is the single source of truth.
 *
 * Secrets: SUPABASE_SERVICE_KEY and XAI_API_KEY are substituted into the
 * deployed copy at deploy time (upload_scenario placeholder substitution,
 * like __SUPABASE_URL__) — never hardcode them here.
 *
 * Deploy: voximplant/api_clients/voximplant_client.py upload_scenario().
 */

// call.record() needs no module require (Recorder module only needed
// for VoxEngine.createRecorder).
// Grok Voice Agent connector — native Voximplant module (enable the
// connector once in the Voximplant panel; spec phase 1). API shape
// verified July 2026 against voximplant/grok-voice-agent-example +
// docs.voximplant.ai: Modules.Grok / Grok.createVoiceAgentAPIClient.
require(Modules.Grok);

const SUPABASE_URL = "__SUPABASE_URL__";           // substituted at deploy time
const WEBHOOK_URL = "https://api.nerranetwork.com/voices/interview-complete";
const HARD_CAP_MS = 50 * 60 * 1000;                // spec §11.8: 50-min hard cap
const GROK_DROP_GUARD_MS = 1500;                   // spec §7: teardown-race guard

let runId = null;
let call = null;
let grokAgent = null;
let webhookFired = false;
let hardCapTimer = null;
let recordUrl = null;      // delivered via CallEvents.RecordStarted (no getter API)
let connectedAt = null;    // Call has no getDuration(); compute from timestamps

VoxEngine.addEventListener(AppEvents.Started, async function () {
  let config;
  try {
    const custom = JSON.parse(VoxEngine.customData() || "{}");
    runId = custom.run_id;
    if (!runId) throw new Error("customData missing run_id");
    config = await fetchInterviewConfig(runId);
    if (!config) throw new Error("no interview_runs row for " + runId);
  } catch (e) {
    Logger.write("[aoa] startup failure: " + e.message);
    await fireWebhook({ run_id: runId, status: "failed", reason: "startup: " + e.message });
    return VoxEngine.terminate();
  }

  await markRunStatus(runId, "in_progress");

  // 2. Outbound PSTN call to the guest.
  call = VoxEngine.callPSTN(config.guest_phone, config.caller_id);

  call.addEventListener(CallEvents.Connected, async function () {
    try {
      // 3. Dual-track stereo recording — call.record({stereo:true})
      //    puts guest→cloud audio on one channel and cloud→guest (Mira +
      //    played clips) on the other. NOTE: VoxEngine.createRecorder's
      //    stereo param records MIXED streams in both channels and can
      //    never separate participants (verified July 2026) — only
      //    Call.record gives the per-channel split the editorial
      //    pipeline's per-channel Whisper STT depends on. Started before
      //    the disclosure so the consent exchange is on tape.
      connectedAt = Date.now();
      call.addEventListener(CallEvents.RecordStarted, function (e) {
        if (e && e.url) recordUrl = e.url;
      });
      call.record({
        name: "aoa_" + runId,
        stereo: true,
        hd_audio: true,
      });

      // 4. Recording-consent disclosure — pre-generated Mira clip from R2
      //    (spec §11.2; wording confirmed by Patrick before launch).
      if (config.recording_disclosure_url) {
        call.startPlayback(config.recording_disclosure_url);
        await waitForEvent(call, CallEvents.PlaybackFinished);
      }

      // 5. Grok Voice Agent with Mira's compiled persona. No explicit
      //    model: xAI's Voice Agent API default is current post
      //    May 31 2026 (per voximplant/grok-voice-agent-example).
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
          // 6. Bridge guest <-> Mira; record Mira's track too. Mira
          //    opens the conversation (responseCreate).
          VoxEngine.sendMediaBetween(call, grokAgent);
          grokAgent.responseCreate({});
        } catch (e) {
          Logger.write("[aoa " + runId + "] media-bridge failure: " + e.message);
          call.hangup();
        }
      });

      // Telephony-natural barge-in: flush Mira's buffered audio the
      // moment the guest starts speaking.
      grokAgent.addEventListener(Grok.VoiceAgentAPIEvents.InputAudioBufferSpeechStarted, function () {
        if (grokAgent) grokAgent.clearMediaBuffer();
      });

      grokAgent.addEventListener(Grok.VoiceAgentAPIEvents.WebSocketError, onGrokDropped);

      // 7. Safety hard cap (Mira's prompt soft-wraps at 45; spec §11.8).
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
  });

  call.addEventListener(CallEvents.Disconnected, async function () {
    if (hardCapTimer) clearTimeout(hardCapTimer);
    try {
      // 8. Stop recording, collect the Voximplant record URL, notify the
      //    pipeline. The post-interview workflow moves the recording into
      //    R2 (/raw/) — Net.httpRequest can't stream multi-MB audio
      //    reliably from a scenario, so the durable copy happens in
      //    GitHub Actions where retries are cheap (spec §7 handles the
      //    upload-failure case there).
      // call.record stops automatically when the call disconnects.
      await fireWebhook({
        run_id: runId,
        status: "completed",
        voximplant_record_url: recordUrl,
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
    // 9. Guest didn't answer / call failed → pipeline marks the interview
    //    missed and emails a reschedule link (spec §7 row 1).
    if (hardCapTimer) clearTimeout(hardCapTimer);
    await fireWebhook({
      run_id: runId,
      status: "failed",
      reason: "call_failed: " + (event.reason || event.code || "unknown"),
    });
    VoxEngine.terminate();
  });
});

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
