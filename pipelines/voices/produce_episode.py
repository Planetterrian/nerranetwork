#!/usr/bin/env python3
"""Final episode production (nerra_voices_produce_episode.yml).

Triggered by ``repository_dispatch: interview-approved-by-guest`` (gate 2
cleared — guest approved or the 7-day auto-approve fired).

Steps: narration LLM pass (Mira's cold open, act intros, sign-off — written
against the APPROVED transcript with redactions already reflected) → Grok
TTS narration → ffmpeg assembly (redaction cuts + music bed + -16 LUFS) →
waveform video → upload episode + video to R2 → mark interview ``approved``
+ ready for the publish workflow → queue cross-show callouts.
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

import requests

from common import (  # noqa: E402
    ROOT, llm, load_prompt, logger, notify_operator, parse_json_lenient,
    r2_upload, sb_insert, sb_select, sb_update,
)

sys.path.insert(0, str(Path(__file__).parent))
from audio.assemble_episode import assemble  # noqa: E402
from audio.generate_narration import synthesize_segments  # noqa: E402
from audio.waveform_video import render as render_waveform  # noqa: E402

MUSIC_BED = ROOT / "assets" / "music" / "age_of_ai.mp3"  # optional; no-op if absent
COVER = ROOT / "assets" / "covers" / "age-of-ai.jpg"
NARRATION_SEGMENT_IDS = ["cold_open", "act_one", "act_two", "act_three", "sign_off"]
CALLOUT_TTL_DAYS = 14


def _load_context() -> tuple[dict, dict, dict, dict]:
    interview_id = os.environ.get("INTERVIEW_ID", "").strip()
    if not interview_id:
        raise RuntimeError("INTERVIEW_ID env var is required")
    interview = sb_select("interviews", f"id=eq.{interview_id}")[0]
    app = sb_select("guest_applications",
                    f"id=eq.{interview['application_id']}")[0]
    pkgs = sb_select(
        "editorial_packages",
        f"interview_id=eq.{interview_id}&status=eq.approved_by_guest",
    )
    if not pkgs:
        raise RuntimeError(
            f"no guest-approved editorial package for interview {interview_id}"
        )
    pkg = pkgs[0]
    run = sb_select("interview_runs", f"id=eq.{pkg['interview_run_id']}")[0]
    return interview, app, pkg, run


def write_narration(interview: dict, app: dict, pkg: dict) -> list[dict]:
    raw = llm(
        load_prompt(
            "mira_narration.txt",
            guest_name=app["name"],
            guest_title=app.get("title", ""),
            guest_organization=app.get("organization", ""),
            episode_thesis=interview.get("episode_thesis", ""),
            episode_notes=pkg.get("episode_notes", ""),
            transcript=pkg.get("transcript_cleaned", ""),
        ),
        temperature=0.6, max_tokens=4000,
    )
    segments = parse_json_lenient(raw)
    if not isinstance(segments, list):
        raise RuntimeError("narration pass did not return a JSON array")
    ids = {s.get("id") for s in segments}
    missing = [i for i in ("cold_open", "sign_off") if i not in ids]
    if missing:
        raise RuntimeError(f"narration pass missing required segments: {missing}")
    return [s for s in segments if s.get("id") in NARRATION_SEGMENT_IDS]


def main() -> int:
    interview, app, pkg, run = _load_context()

    with tempfile.TemporaryDirectory(prefix="aoa_produce_") as tmp:
        workdir = Path(tmp)

        # 1. Interview audio (mixed track from post-processing).
        mixed_url = run.get("recording_mixed_url") or run.get("recording_guest_url")
        if not mixed_url:
            raise RuntimeError("run has no mixed recording URL")
        interview_wav = workdir / "interview.wav"
        with requests.get(mixed_url, stream=True, timeout=900) as resp:
            resp.raise_for_status()
            with interview_wav.open("wb") as fh:
                for chunk in resp.iter_content(1 << 16):
                    fh.write(chunk)

        # 2. Mira narration (LLM → Grok TTS).
        segments = write_narration(interview, app, pkg)
        narration = synthesize_segments(segments, workdir / "narration")

        # 3. Assembly (redaction cuts first, then bed + loudnorm).
        stamp = dt.datetime.now(dt.timezone.utc)
        final_name = f"Age_of_AI_{app['name'].replace(' ', '_')}_{stamp:%Y%m%d}"
        episode_mp3 = assemble(
            narration, interview_wav, workdir / f"{final_name}.mp3",
            music_bed=MUSIC_BED if MUSIC_BED.exists() else None,
            redactions=pkg.get("guest_redactions") or [],
        )

        # 4. Waveform video for YouTube.
        video = render_waveform(
            episode_mp3, workdir / f"{final_name}.mp4",
            cover_image=COVER if COVER.exists() else None,
            title=f"{app['name']} — The Age of AI",
        )

        # 5. Durable copies.
        episode_url = r2_upload(episode_mp3, f"age_of_ai/{episode_mp3.name}")
        video_url = r2_upload(video, f"age_of_ai/video/{video.name}")

    # 6. State + callout queue.
    sb_update("interviews", f"id=eq.{interview['id']}", {"status": "approved"})
    sb_update("editorial_packages", f"id=eq.{pkg['id']}",
              {"status": "approved_by_guest"})
    sb_update("interview_runs", f"id=eq.{run['id']}",
              {"recording_mixed_url": episode_url})

    callouts = pkg.get("cross_show_callouts") or {}
    expires = (dt.datetime.now(dt.timezone.utc)
               + dt.timedelta(days=CALLOUT_TTL_DAYS)).isoformat()
    for target_show, text in callouts.items():
        sb_insert("cross_show_callouts", {
            "source_episode_id": interview["id"],
            "target_show": target_show,
            "callout_text": text,
            "callout_url": "https://nerranetwork.com/age-of-ai.html",
            "expires_at": expires,
        })

    notify_operator(
        f"Age of AI: {app['name']} episode PRODUCED — audio {episode_url} · "
        f"video {video_url}. Publish workflow will pick it up on schedule."
    )
    logger.info("Production complete for interview %s", interview["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
