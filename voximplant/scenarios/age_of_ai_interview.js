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
 * Secrets: SUPABASE_SERVICE_KEY and XAI_API_KEY are injected as Voximplant
 * application-level custom data / secure storage (Management API
 * SetApplicationInfo) — never hardcode them here.
 *
 * Deploy: voximplant/api_clients/voximplant_client.py upload_scenario().
 */

require(Modules.Recorder);
// Grok Voice Agent connector — native Voximplant module (enable the
// connector once in the Voximplant panel; spec phase 1).
require(Modules.GrokVoiceAgent);

const SUPABASE_URL = "__SUPABASE_URL__";           // substituted at deploy time
const WEBHOOK_URL = "https://api.nerranetwork.com/voices/interview-complete";
const HARD_CAP_MS = 50 * 60 * 1000;                // spec §11.8: 50-min hard cap
const GROK_RECONNECT_GRACE_MS = 10 * 1000;         // spec §7: reconnect window

let runId = null;
let call = null;
let grokAgent = null;
let recorder = null;
let webhookFired = false;
let hardCapTimer = null;

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
      // 3. Recording-consent disclosure — pre-generated Mira clip from R2
      //    (spec §11.2; wording confirmed by Patrick before launch).
      if (config.recording_disclosure_url) {
        call.startPlayback(config.recording_disclosure_url);
        await waitForEvent(call, CallEvents.PlaybackFinished);
      }

      // 4. Dual-track stereo recording (guest one channel, Mira the other).
      recorder = VoxEngine.createRecorder({
        name: "aoa_" + runId,
        stereo: true,
        hd_audio: true,
      });
      call.sendMediaTo(recorder);

      // 5. Grok Voice Agent with Mira's compiled persona.
      grokAgent = VoxEngine.createGrokVoiceAgent({
        apiKey: getSecret("XAI_API_KEY"),
        model: "grok-voice-latest",
        voice: config.voice_preset || "ara",
        instructions: config.mira_system_prompt,
        tools: config.tools || [],
        turn_detection: { type: "server_vad" },
        temperature: 0.7,
      });

      grokAgent.addEventListener(GrokVoiceAgentEvents.Disconnected, onGrokDropped);
      grokAgent.addEventListener(GrokVoiceAgentEvents.Error, onGrokDropped);

      // 6. Bridge guest <-> Mira; record Mira's track too.
      VoxEngine.sendMediaBetween(call, grokAgent);
      grokAgent.sendMediaTo(recorder);

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
      if (recorder) recorder.stop();
      const recordUrl = recorder ? recorder.getUrl() : null;
      await fireWebhook({
        run_id: runId,
        status: "completed",
        voximplant_record_url: recordUrl,
        duration_sec: Math.round(call.getDuration ? call.getDuration() : 0),
        disconnect_reason: call.getDisconnectReason
          ? call.getDisconnectReason()
          : "normal",
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
 * Grok connection dropped mid-call (spec §7 row 3): give the connector a
 * short reconnect window; if the agent is still down, play Mira's
 * pre-recorded apology and hang up. The Disconnected handler then fires
 * the normal webhook with whatever was recorded.
 */
function onGrokDropped() {
  Logger.write("[aoa " + runId + "] Grok connection dropped — grace window");
  setTimeout(async function () {
    const alive = grokAgent && grokAgent.state && grokAgent.state() === "CONNECTED";
    if (alive || !call || call.state() === "DISCONNECTED") return;
    Logger.write("[aoa " + runId + "] Grok did not recover — apologizing and ending");
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
  }, GROK_RECONNECT_GRACE_MS);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getSecret(name) {
  // Application-level secure custom data, set once via the Management API
  // (see voximplant_client.py set_application_secrets).
  const secrets = JSON.parse(Application.customData() || "{}");
  if (!secrets[name]) throw new Error("missing scenario secret: " + name);
  return secrets[name];
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
