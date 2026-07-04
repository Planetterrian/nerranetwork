#!/usr/bin/env python3
"""Post-interview processing (nerra_voices_post_interview.yml).

Triggered by ``repository_dispatch: interview-complete`` — the Worker
receives the Voximplant hangup webhook, stores the raw payload on the run
row, and dispatches this workflow with the run id.

Steps: pull the recording → durable copies in R2 (/raw/) → leveled mix →
per-channel STT (stereo channels ARE the diarization) → 8 LLM editorial
passes (schema-validated, one retry each) → ``editorial_packages`` row →
Slack ping to Patrick with the review link (gate 1).

A ``failed`` run (guest never answered) short-circuits: interview marked
missed, reschedule email sent, no-show count incremented (spec §7/§11.7).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path

import requests

from common import (  # noqa: E402
    llm, load_prompt, logger, new_review_token, notify_operator,
    parse_json_lenient, r2_upload, render_email, sb_insert, sb_select,
    sb_update, send_email,
)

sys.path.insert(0, str(Path(__file__).parent))
from audio.mix_tracks import (  # noqa: E402
    duration_seconds, mix_interview, split_channels,
)
from validators.schema_validators import validate_pass_output  # noqa: E402

SHORT_CALL_THRESHOLD_SEC = 10 * 60
LOW_STT_CONFIDENCE = 0.55
REVIEW_BASE = "https://api.nerranetwork.com/voices/admin/review"

EDITORIAL_PASSES = [
    ("01_clean_transcript.txt", "transcript_cleaned"),
    ("02_chapter_markers.txt", "chapter_markers"),
    ("03_episode_notes.txt", "episode_notes"),
    ("04_classify_show_fits.txt", "topical_show_fits"),
    ("05_suggest_clips.txt", "clip_suggestions"),
    ("06_social_copy.txt", "social_copy"),
    ("07_generate_callouts.txt", "cross_show_callouts"),
    ("08_newsletter_draft.txt", "newsletter_draft"),
]
JSON_PASSES = {"chapter_markers", "topical_show_fits", "clip_suggestions",
               "social_copy", "cross_show_callouts"}


def _run_row() -> dict:
    run_id = os.environ.get("INTERVIEW_RUN_ID", "").strip()
    if not run_id:
        raise RuntimeError("INTERVIEW_RUN_ID env var is required")
    rows = sb_select("interview_runs", f"id=eq.{run_id}")
    if not rows:
        raise RuntimeError(f"interview_runs row {run_id} not found")
    return rows[0]


def _interview_and_app(run: dict) -> tuple[dict, dict]:
    interview = sb_select("interviews", f"id=eq.{run['interview_id']}")[0]
    app = sb_select("guest_applications",
                    f"id=eq.{interview['application_id']}")[0]
    return interview, app


def handle_missed(run: dict, interview: dict, app: dict) -> int:
    """Guest didn't answer (spec §7 row 1 + §11.7 no-show policy)."""
    no_shows = int(interview.get("no_show_count") or 0) + 1
    status = "missed" if no_shows < 2 else "cancelled"
    sb_update("interviews", f"id=eq.{interview['id']}",
              {"status": status, "no_show_count": no_shows})
    if no_shows < 2:
        html = render_email("voices_interview_reminder.j2",
                            guest_name=app["name"], missed=True,
                            booking_url=os.environ.get("CALCOM_BOOKING_URL", ""))
        send_email(app["email"], "We missed you — reschedule your Age of AI interview", html)
        notify_operator(f"Age of AI: {app['name']} no-show #{no_shows} — reschedule email sent")
    else:
        sb_update("guest_applications", f"id=eq.{app['id']}", {"status": "lapsed"})
        notify_operator(f"Age of AI: {app['name']} second no-show — application lapsed")
    return 0


def fetch_recording(run: dict, workdir: Path) -> Path:
    url = (run.get("recording_guest_url")  # already in R2 (re-run case)
           or (run.get("grok_session_log") or {}).get("voximplant_record_url")
           or "")
    if not url:
        raise RuntimeError("run has no recording URL — scenario upload failed?")
    raw = workdir / "raw_interview.mp3"
    with requests.get(url, stream=True, timeout=600) as resp:
        resp.raise_for_status()
        with raw.open("wb") as fh:
            for chunk in resp.iter_content(1 << 16):
                fh.write(chunk)
    if raw.stat().st_size < 50_000:
        raise RuntimeError(f"recording suspiciously small ({raw.stat().st_size} bytes)")
    return raw


def diarized_transcript(raw: Path, workdir: Path) -> tuple[str, float]:
    """Per-channel Whisper transcription; the stereo channels ARE the
    diarization (guest left, Mira right — VoxEngine recorder convention).
    Returns (labeled merged transcript, mean segment confidence 0..1)."""
    from engine.transcripts import generate_transcript
    guest_wav, mira_wav = split_channels(raw, workdir / "channels")
    merged: list[tuple[float, str, str]] = []
    confidences: list[float] = []
    for label, wav in (("GUEST", guest_wav), ("MIRA", mira_wav)):
        result = generate_transcript(
            wav, workdir / "transcripts", f"{label.lower()}_track",
            model_size="small", language="en",
        )
        if result is None:
            raise RuntimeError(
                f"transcription failed for the {label} channel "
                "(faster-whisper unavailable or audio unreadable)"
            )
        data = json.loads(result.json_path.read_text(encoding="utf-8"))
        for seg in data.get("segments", []):
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            merged.append((float(seg.get("start", 0.0)), label, text))
            # faster-whisper avg_logprob ≈ log-confidence; map to 0..1-ish.
            if "avg_logprob" in seg:
                confidences.append(
                    max(0.0, min(1.0, 1.0 + float(seg["avg_logprob"]))))
    merged.sort(key=lambda s: s[0])
    lines = [f"[{int(s // 60):02d}:{int(s % 60):02d}] {label}: {text}"
             for s, label, text in merged]
    mean_conf = sum(confidences) / len(confidences) if confidences else 1.0
    return "\n".join(lines), mean_conf


def run_editorial_passes(transcript: str, interview: dict, app: dict) -> dict:
    package: dict = {}
    for prompt_file, field in EDITORIAL_PASSES:
        base_prompt = load_prompt(
            f"editorial_passes/{prompt_file}",
            guest_name=app["name"],
            guest_title=app.get("title", ""),
            guest_organization=app.get("organization", ""),
            episode_thesis=interview.get("episode_thesis", ""),
            transcript=transcript,
            cleaned_transcript=package.get("transcript_cleaned", transcript),
        )
        output, error = None, None
        for attempt, strictness in enumerate((
            "", "\n\nSTRICT RETRY: your previous output failed validation "
                "({error}). Output ONLY the requested format, nothing else.",
        )):
            text = llm(base_prompt + strictness.format(error=error),
                       temperature=0.3, max_tokens=6000)
            try:
                candidate = parse_json_lenient(text) if field in JSON_PASSES else text
                validate_pass_output(field, candidate)
                output = candidate
                break
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
                logger.warning("Pass %s attempt %d invalid: %s",
                               field, attempt + 1, exc)
        if output is None:
            # Spec §7: surface to Patrick for a manual editorial draft.
            notify_operator(
                f"Age of AI: editorial pass {field!r} failed validation twice "
                f"— manual draft needed. Last error: {error}", critical=True)
            output = [] if field in JSON_PASSES else ""
        package[field] = output
        logger.info("Editorial pass complete: %s", field)
    return package


def main() -> int:
    run = _run_row()
    interview, app = _interview_and_app(run)

    if run.get("status") == "failed" or run.get("disconnect_reason", "").startswith("call_failed"):
        return handle_missed(run, interview, app)

    with tempfile.TemporaryDirectory(prefix="aoa_post_") as tmp:
        workdir = Path(tmp)
        raw = fetch_recording(run, workdir)
        duration = duration_seconds(raw)

        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
        raw_url = r2_upload(raw, f"age_of_ai/raw/{run['id']}_{stamp}.mp3")
        mixed = mix_interview(raw, workdir / "mixed.wav")
        mixed_url = r2_upload(mixed, f"age_of_ai/raw/{run['id']}_{stamp}_mixed.wav")

        transcript, confidence = diarized_transcript(raw, workdir)

        sb_update("interview_runs", f"id=eq.{run['id']}", {
            "status": "completed",
            "recording_guest_url": raw_url,
            "recording_mixed_url": mixed_url,
            "duration_sec": int(duration),
        })
        sb_update("interviews", f"id=eq.{interview['id']}",
                  {"status": "editorial_review"})

        package = run_editorial_passes(transcript, interview, app)

        flags = []
        if duration < SHORT_CALL_THRESHOLD_SEC:
            flags.append("short_call")
        if confidence < LOW_STT_CONFIDENCE:
            flags.append("low_stt_confidence")

        pkg = sb_insert("editorial_packages", {
            "interview_id": interview["id"],
            "interview_run_id": run["id"],
            "transcript_raw": transcript,
            "transcript_cleaned": package["transcript_cleaned"],
            "chapter_markers": package["chapter_markers"],
            "episode_notes": package["episode_notes"],
            "social_copy": package["social_copy"],
            "clip_suggestions": package["clip_suggestions"],
            "cross_show_callouts": package["cross_show_callouts"],
            "newsletter_draft": package["newsletter_draft"],
            "status": "in_review",
            "guest_review_token": new_review_token(),
            "audio_quality_flag": ",".join(flags) or None,
        })

        if package.get("topical_show_fits"):
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"topical_show_fits": package["topical_show_fits"]})

    flag_note = f" ⚠️ {', '.join(flags)}" if flags else ""
    notify_operator(
        f"Age of AI: {app['name']} interview processed "
        f"({int(duration // 60)} min).{flag_note} "
        f"Review (gate 1): {REVIEW_BASE}/{pkg['id']}"
    )
    logger.info("Editorial package %s ready for Patrick", pkg["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
