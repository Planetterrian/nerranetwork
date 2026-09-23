"""Review gates (Sept 10 2026) — Patrick and the guest both get to listen.

Three defects this pins shut:

* gate 1 was announced on Slack only, with a tokenless URL that 401'd
  until the admin token was pasted by hand, so a quiet Slack meant no
  signal at all that an episode was waiting;
* the guest approved a transcript they had never heard, because the gate 2
  page had no audio on it;
* the two-track path (no co-host in the room) mixed from the raw
  Voximplant stereo and silently threw away the guest's 192 kbps browser
  recording.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))

WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
POST = (ROOT / "pipelines" / "voices" / "post_interview.py").read_text(encoding="utf-8")
MIXER = (ROOT / "pipelines" / "voices" / "audio" / "mix_tracks.py").read_text(encoding="utf-8")
POST_WF = (ROOT / ".github" / "workflows" / "nerra_voices_post_interview.yml").read_text(encoding="utf-8")


def _fn(source: str, signature: str) -> str:
    start = source.index(signature)
    nxt = source.find("\nasync function ", start + 1)
    alt = source.find("\nfunction ", start + 1)
    ends = [e for e in (nxt, alt) if e != -1]
    return source[start:min(ends)] if ends else source[start:]


class TestPackageReviewToken:
    """The emailed gate-1 link opens one package and grants nothing else."""

    def test_python_and_worker_derive_the_same_value(self):
        from common import package_review_token

        pkg_id = "11111111-2222-3333-4444-555555555555"
        expected = hmac.new(b"tok3n", f"nerra-review:{pkg_id}".encode(),
                            hashlib.sha256).hexdigest()[:40]
        assert package_review_token(pkg_id, admin_token="tok3n") == expected
        # The Worker's formula, asserted on its source so the two cannot drift.
        body = _fn(WORKER, "async function packageReviewToken(")
        assert '`nerra-review:${packageId}`' in body
        assert "HMAC" in body and "SHA-256" in body
        assert ".slice(0, 40)" in body

    def test_admin_token_is_required_not_optional(self):
        from common import package_review_token

        with pytest.raises(RuntimeError):
            package_review_token("abc", admin_token="")

    def test_worker_accepts_admin_token_or_the_package_token(self):
        body = _fn(WORKER, "async function requirePackageAccess(")
        assert "supplied === env.ADMIN_TOKEN" in body
        assert "await packageReviewToken(env, packageId)" in body
        assert '"unauthorized" }, 401' in body

    def test_gate_1_page_and_decision_are_both_scoped(self):
        assert "requirePackageAccess(req, env, id)" in _fn(
            WORKER, "async function handleAdminReview(")
        decision = _fn(WORKER, "async function handleEditorialDecision(")
        assert "requirePackageAccess(req, env, String(body.package_id))" in decision
        # A review link must not confer blanket admin on this endpoint.
        assert "requireAdmin(req, env)" not in decision


class TestGateOneNotification:
    """Patrick is emailed, and the link he gets actually opens."""

    def test_slack_and_email_both_carry_a_tokened_link(self):
        assert "package_review_token(pkg['id'])" in POST
        # c6a276178: the token rides in the PATH — a query string's "=" was
        # being eaten between the send and Gmail.
        assert 'f"{REVIEW_BASE}/{pkg[\'id\']}/{package_review_token(pkg[\'id\'])}"' in POST
        assert "send_email(\n            OPERATOR_EMAIL," in POST
        assert "notify_operator(show.slack(" in POST

    def test_neither_notification_can_abort_the_job(self):
        tail = POST[POST.index("flag_note = f\" ⚠️"):]
        assert tail.count("except Exception:") >= 2

    def test_workflow_passes_the_admin_token(self):
        assert "ADMIN_TOKEN: ${{ secrets.ADMIN_TOKEN }}" in POST_WF


class TestGuestHearsTheEpisode:
    def test_gate_2_page_has_an_audio_element(self):
        page = _fn(WORKER, "async function handleGuestReviewPage(")
        assert "<audio controls" in page
        assert "reviewAudioUrl(run)" in page
        # And it still shows the transcript.
        assert "transcript_cleaned" in page

    def test_gate_2_survives_audio_that_is_not_ready(self):
        page = _fn(WORKER, "async function handleGuestReviewPage(")
        assert "still being processed" in page

    def test_reviewers_stream_the_mp3_preview_not_the_raw_wav(self):
        helper = _fn(WORKER, "function reviewAudioUrl(")
        assert "grok_session_log?.tracks?.preview" in helper
        assert "recording_mixed_url" in helper  # fallback kept
        assert 'preload="none"' in WORKER

    def test_post_interview_renders_and_records_the_preview(self):
        assert "libmp3lame" in POST
        assert '"preview": preview_url' in POST


class TestLocalTrackIsNeverDiscarded:
    def test_mix_two_exists(self):
        assert "def mix_two(guest_wav: Path, mira_wav: Path" in MIXER
        assert "amix=inputs=2:duration=longest:normalize=0" in MIXER

    # Sept 22 2026 (46b6a8f38, Viktor Popovic): the two-speaker path is
    # decided by whether MIRA has audio of her own, not by where the guest's
    # track came from. Keyed on the guest being local, a run whose browser
    # upload never arrived fell through to the raw stereo, whose right channel
    # carries the guest's voice back, and his words were attributed to her.
    # A local guest track still takes this path: its Mira source is her leg.
    _CLEAN_TWO = 'elif tracks["sources"].get("mira") != "guest_r":'

    def _branch(self):
        branch = POST[POST.index(self._CLEAN_TWO):]
        # The branch holds a nested (12-space) else; stop at its own.
        return branch[:branch.index("\n        else:\n")]

    def test_no_host_but_a_local_guest_track_still_takes_the_clean_path(self):
        assert self._CLEAN_TWO in POST
        assert 'elif tracks["sources"].get("guest") == "local":' not in POST
        branch = self._branch()
        assert "mix_two(tracks[\"guest\"], tracks[\"mira\"]" in branch
        assert "diarized_tracks(" in branch
        assert "mix_interview(" not in branch

    def test_raw_fallback_survives_for_runs_with_neither(self):
        tail = POST[POST.index(self._CLEAN_TWO):]
        tail = tail[tail.index("\n        else:\n"):]
        assert "mix_interview(raw, workdir / \"mixed.wav\")" in tail
        assert "diarized_transcript(raw, workdir)" in tail
        # The fallback says out loud that its attribution cannot be trusted.
        assert "speaker attribution is unreliable" in tail