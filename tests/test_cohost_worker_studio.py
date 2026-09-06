"""Phase 2 co-host (Sept 2026) — Worker + studio-page contracts.

String-level drift guards on workers/voices/src/index.ts, wrangler.toml and
age-of-ai-studio.html (the pattern tests/test_voices_worker_routing.py
uses), pinned to docs/cohost_phase2_contract.md: the host role is gated by
ADMIN_TOKEN, the scenario's per-leg events and the new webhook fields land
on interview_runs, local browser recordings stream to the VOICES_R2 bucket
under <r2_prefix>/local/<run>/<role>/, and the host studio page answers
Mira's callUser leg instead of dialling.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
WRANGLER = (ROOT / "workers" / "voices" / "wrangler.toml").read_text(encoding="utf-8")
README = (ROOT / "workers" / "voices" / "README.md").read_text(encoding="utf-8")
STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    """Body of one top-level function in index.ts (up to the next one)."""
    assert name in WORKER, f"{name} missing from index.ts"
    return WORKER.split(name)[1].split("\nasync function")[0].split("\nfunction ")[0]


# ---------------------------------------------------------------------------
# Worker: env, SHOWS, routes
# ---------------------------------------------------------------------------

def test_env_has_host_creds_r2_and_operator_phone():
    env = WORKER.split("export interface Env {")[1].split("\n}")[0]
    assert "VOX_HOST_USER?: string" in env
    assert "VOX_HOST_PASSWORD?: string" in env
    assert "OPERATOR_PHONE?: string" in env
    assert "VOICES_R2: R2Bucket" in env


def test_shows_map_carries_r2_prefix():
    block = re.search(r"export const SHOWS: Record<ShowSlug, Show> = \{(.*?)\n\};", WORKER, re.S)
    assert block, "SHOWS map missing"
    assert 'r2Prefix: "age_of_ai"' in block.group(1)
    assert 'r2Prefix: "nerra_voices"' in block.group(1)
    assert "r2Prefix: string" in WORKER.split("export interface Show {")[1].split("\n}")[0]


@pytest.mark.parametrize("method,path,handler", [
    ("POST", "/voices/leg-event", "handleLegEvent"),
    ("POST", "/voices/upload-chunk", "handleUploadChunk"),
    ("POST", "/voices/upload-done", "handleUploadDone"),
    ("GET", "/voices/host-link", "handleHostLink"),
    ("POST", "/voices/studio-auth", "handleStudioAuth"),
    ("GET", "/voices/studio-state", "handleStudioState"),
])
def test_routes_present(method, path, handler):
    assert f'req.method === "{method}" && path === "{path}"' in WORKER, f"route {method} {path}"
    assert f"return {handler}(req, env)" in WORKER


def test_scenario_and_worker_agree_on_leg_event_url():
    assert 'API_BASE + "/leg-event"' in SCENARIO
    assert 'JSON.stringify({ run_id: runId, role: role, event: event })' in SCENARIO


# ---------------------------------------------------------------------------
# Worker: studio-auth / studio-state
# ---------------------------------------------------------------------------

def test_studio_auth_gates_host_on_admin_token():
    body = _fn("async function handleStudioAuth")
    assert 'body?.role === "host"' in body
    assert "adminTokenOk(env, req, body?.token)" in body, "host role must check ADMIN_TOKEN"
    assert 'json({ error: "unauthorized" }, 401)' in body
    assert 'env.VOX_HOST_USER || "host"' in body
    assert "env.VOX_HOST_PASSWORD" in body
    assert '"host studio auth not configured" }, 503' in body
    # Guest path is unchanged: VOX_GUEST_* with the same 503 when unset.
    assert 'env.VOX_GUEST_USER || "guest"' in body and "env.VOX_GUEST_PASSWORD" in body
    assert "return json({ token, user, role })" in body
    ok = _fn("function adminTokenOk")
    assert "t === env.ADMIN_TOKEN" in ok and "Boolean(env.ADMIN_TOKEN)" in ok


def test_studio_state_reports_presence_and_host_user_only_with_token():
    body = _fn("async function handleStudioState")
    for field in ("host_mode: hostMode", "guest_joined: Boolean(latest?.guest_joined_at)",
                  "host_joined: Boolean(latest?.host_joined_at) && !latest?.host_left_at",
                  "live_run_id:", "run_status:"):
        assert field in body, field
    assert 'role === "host" && adminTokenOk(env, req)' in body
    assert 'hostAllowed ? { host_user: env.VOX_HOST_USER || "host" } : {}' in body
    # Existing fields survive.
    for field in ("ready: Boolean(run)", "run_id: run?.id ?? null", "show: show.slug",
                  "show_name: show.name", "interview_status: iv.status"):
        assert field in body, field


# ---------------------------------------------------------------------------
# Worker: leg-event, upload-chunk, upload-done, host-link, interview-complete
# ---------------------------------------------------------------------------

def test_leg_event_sets_first_join_and_host_left():
    body = _fn("async function handleLegEvent")
    assert "requireAdmin" not in body, "the scenario posts without a token"
    assert '["joined", "left"].includes(event)' in body
    assert 'if (!run) return json({ error: "run not found" }, 404)' in body
    assert "!run.guest_joined_at) patch.guest_joined_at = now" in body
    assert "if (!run.host_joined_at) patch.host_joined_at = now" in body
    assert 'event === "left") patch.host_left_at = now' in body
    assert "host_attempts" not in body, "attempts come from the webhook, not leg-event"


def test_upload_chunk_contract():
    body = _fn("async function handleUploadChunk")
    assert "LOCAL_CHUNK_MAX_BYTES" in body and "10 * 1024 * 1024" in WORKER
    assert "req.arrayBuffer()" in body
    assert "env.VOICES_R2.put(key, body, { httpMetadata: { contentType } })" in body
    assert "return json({ ok: true, key, size: body.byteLength })" in body
    assert '`${String(seq).padStart(5, "0")}.webm`' in body
    key = _fn("function localKey")
    assert "`${show.r2Prefix}/local/${runId}/${role}/${name}`" in key
    gate = _fn("async function localUploadGate")
    assert 'role === "host" && !adminTokenOk(env, req, bodyToken)' in gate
    assert 'role === "guest" && !GUEST_UPLOAD_STATUSES.has' in gate
    statuses = WORKER.split("const GUEST_UPLOAD_STATUSES = new Set([")[1].split("])")[0]
    for st in ("fired", "in_progress", "awaiting_guest", "completed"):
        assert f'"{st}"' in statuses, f"guest uploads must be allowed while {st}"


def test_upload_done_writes_manifest_key_and_reports_missing():
    body = _fn("async function handleUploadDone")
    assert "env.VOICES_R2.head(key)" in body
    assert "missing.push(key)" in body
    assert 'localKey(gate.show, runId, gate.role, "manifest.json")' in body
    for field in ("mime:", "started_at:", "duration_ms:", "completed_at:", "chunks: keys", "missing,"):
        assert field in body, field
    assert "[`local_${gate.role}_url`]: manifestKey" in body, "store the KEY, not a URL"
    assert "return json({ ok: true, key: manifestKey, chunks: keys.length, missing" in body


def test_interview_complete_persists_phase2_fields():
    body = _fn("async function handleInterviewComplete")
    assert "recording_host_url: payload.voximplant_host_record_url ?? null" in body
    assert "recording_mira_url: payload.voximplant_mira_record_url ?? null" in body
    assert "host_joined_at: payload.host_joined_at ?? null" in body
    assert "host_left_at: payload.host_left_at ?? null" in body
    assert "host_attempts: Number(payload.host_attempts ?? 0) || 0" in body
    # Existing behaviour untouched.
    assert "voximplant_record_url: payload.voximplant_record_url ?? null" in body
    assert 'dispatch(env, "interview-complete", { run_id: payload.run_id })' in body
    # The scenario actually sends those keys.
    for key in ("voximplant_host_record_url", "voximplant_mira_record_url",
                "host_joined_at", "host_left_at", "host_attempts"):
        assert f"{key}:" in SCENARIO, f"scenario webhook payload lacks {key}"


def test_host_link_and_guest_studio_url_roles():
    assert '&role=${role}' in WORKER
    assert 'studioUrl(show, interviewId, "guest")' in _fn("async function handleCalComBooked")
    link = _fn("function hostStudioUrl")
    assert 'studioUrl(show, interviewId, "host")' in link
    assert "&token=${encodeURIComponent(env.ADMIN_TOKEN)}" in link
    body = _fn("async function handleHostLink")
    assert "requireAdmin(req, env)" in body
    assert "url: hostStudioUrl(env, show, interviewId)" in body


def test_health_reports_host_password_and_r2():
    body = _fn("async function handleHealth")
    assert "vox_host_password: !!env.VOX_HOST_PASSWORD" in body
    assert "voices_r2: !!env.VOICES_R2" in body


# ---------------------------------------------------------------------------
# wrangler.toml + README
# ---------------------------------------------------------------------------

def test_wrangler_has_r2_binding_and_documents_vars():
    assert "[[r2_buckets]]" in WRANGLER
    assert 'binding = "VOICES_R2"' in WRANGLER
    assert 'bucket_name = "podcast-audio"' in WRANGLER
    for var in ("VOX_HOST_USER", "VOX_HOST_PASSWORD", "OPERATOR_PHONE"):
        assert var in WRANGLER, f"wrangler.toml must document {var}"
    for text in ("/voices/leg-event", "/voices/upload-chunk", "/voices/upload-done",
                 "/voices/host-link", "VOX_HOST_PASSWORD"):
        assert text in README


# ---------------------------------------------------------------------------
# Studio page
# ---------------------------------------------------------------------------

def test_studio_reads_role_and_token():
    assert 'params.get("role") === "host" ? "host" : "guest"' in STUDIO
    assert 'params.get("token")' in STUDIO
    assert "Co-host studio" in STUDIO
    assert "hold on" in STUDIO
    assert 'role: role' in STUDIO and "authBody.token = adminToken" in STUDIO
    assert '"&role=" + role' in STUDIO, "studio-state poll must carry the role"


def test_studio_host_auto_answers_incoming_call():
    assert "sdk.on(VoxImplant.Events.IncomingCall, onIncomingCall)" in STUDIO
    assert 'call.answer("", {}, { sendVideo: false, receiveVideo: false })' in STUDIO
    assert 'headers["X-Run-Id"]' in STUDIO
    assert "incomingRun !== runId" in STUDIO, "must ignore calls for another run"
    # Re-arm after a drop; only a deliberate Leave stops auto-answer.
    assert "if (!leaving) armHost()" in STUDIO or "if (!leaving) {\n        armHost();" in STUDIO
    assert "call.on(VoxImplant.CallEvents.Connected, onCallConnected)" in STUDIO
    assert "call.on(VoxImplant.CallEvents.Disconnected, onCallEnded)" in STUDIO
    # Guest flow keeps dialling Mira with the run id header.
    assert 'number: "mira"' in STUDIO and '"X-Run-Id": runId' in STUDIO


def test_studio_local_recording_contract():
    assert 'var LOCAL_MIME = "audio/webm;codecs=opus"' in STUDIO
    assert "MediaRecorder.isTypeSupported(LOCAL_MIME)" in STUDIO
    assert "new MediaRecorder(stream, { mimeType: LOCAL_MIME, audioBitsPerSecond: 192000 })" in STUDIO
    assert "recorder.start(5000)" in STUDIO
    assert "echoCancellation: false, noiseSuppression: false, autoGainControl: false" in STUDIO
    assert "channelCount: 1, sampleRate: 48000" in STUDIO
    assert '"/upload-chunk?run_id="' in STUDIO and '"&seq=" + seq' in STUDIO
    assert 'API + "/upload-done"' in STUDIO
    assert "attempt < 3" in STUDIO, "three retries per chunk"
    assert "navigator.sendBeacon(" in STUDIO
    assert '"local recording: "' in STUDIO
    # Chunks are queued sequentially and the final chunk is awaited before upload-done.
    assert "rec.queue = rec.queue.then(" in STUDIO
    assert "return rec.queue;" in STUDIO
