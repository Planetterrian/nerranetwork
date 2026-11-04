#!/usr/bin/env python3
"""Rebuild one interview's per-speaker tracks, review mix and transcript.

Nov 4 2026 (Blaine Mathieu). Mira's recorder lost twenty seconds at her
30-minute hand-over and twenty-two more at a rescue four minutes later; the
placement step saw one of the two jumps, so for the last seven minutes of the
hour her own track, the review mix Patrick and the guest listen to, the
transcript and the cut made from that transcript all had her twenty-two
seconds off. ``build_tracks`` now places her at the session changes the room
logged. This re-runs that step, and only what depends on it, for a run that
was processed before the fix:

* the per-speaker tracks and the leg file (new R2 keys: the CDN would keep
  serving the old ones under the old keys),
* the review mix and its MP3 preview,
* the room's transcript on the live editorial package, and its cleaned copy.

It sends nothing to anyone, does not make a new package, grade the room,
propose lessons or thank the guest again. A dry run (the default) builds and
checks everything and writes nothing; ``--apply`` uploads and records it, and
keeps the previous ``tracks`` record under ``tracks.before_retrack``. Cut the
episode again afterwards (auto_edit, narrate, assemble_edit).

    python pipelines/voices/retrack_run.py <interview_runs.id> [--apply]
"""
from __future__ import annotations

import datetime as dt
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import post_interview as pi  # noqa: E402
from common import r2_upload, sb_select, sb_update  # noqa: E402

logger = logging.getLogger("nerra.voices.retrack")


def _live_package(run_id: str) -> dict | None:
    rows = sb_select("editorial_packages",
                     f"interview_run_id=eq.{run_id}&status=neq.killed"
                     "&order=created_at.desc&limit=1")
    return rows[0] if rows else None


def retrack(run_id: str, apply: bool) -> dict:
    run = pi._run_row() if not run_id else sb_select("interview_runs", f"id=eq.{run_id}")[0]
    interview, app = pi._interview_and_app(run)
    show = pi.show_for(interview, app)
    log = dict(run.get("grok_session_log") or {})
    old = dict(log.get("tracks") or {})
    with tempfile.TemporaryDirectory(prefix="retrack_") as tmp:
        workdir = Path(tmp)
        raw = pi.fetch_recording(run, workdir)
        host_legs = pi.leg_recordings(run, "host", workdir)
        host_raw = host_legs[0] if host_legs else None
        mira_url = ((old.get("durable") or {}).get("mira")
                    or run.get("recording_mira_url") or "")
        mira_raw = pi.fetch_leg_recording(mira_url, workdir, "mira")
        if mira_raw is None:
            raise SystemExit("no recording of Mira's own to place")
        tracks = pi.build_tracks(run, raw, workdir, host_raw=host_raw,
                                 mira_raw=mira_raw, host_legs=host_legs)
        summary = {"alignment": tracks["alignment"], "unaligned": tracks["unaligned"],
                   "pieces": tracks["pieces"], "sources": tracks["sources"]}
        logger.info("rebuilt: %s", summary)
        if tracks["host"] is not None:
            raise SystemExit("a co-host room: re-run post_interview instead")
        if tracks["unaligned"]:
            raise SystemExit(f"still off the room's clock: {tracks['unaligned']} — "
                             "nothing written")

        words: dict = {}
        label = pi._guest_label(app)
        transcript, confidence = pi.diarized_tracks(
            [(label, tracks["guest"]), ("Mira", tracks["mira"])], workdir,
            offsets={label: 0.0, "Mira": 0.0}, words_out=words)
        transcript, echoed = pi.strip_echo_lines(transcript, "Mira")
        from terms import correct_transcript
        transcript, _changes = correct_transcript(transcript, app, show)
        mixed = pi.mix_two(tracks["guest"], tracks["mira"], workdir / "mixed.wav")
        preview = workdir / "preview.mp3"
        subprocess.run(["ffmpeg", "-y", "-i", str(mixed), "-c:a", "libmp3lame",
                        "-b:a", "96k", "-ac", "1", str(preview)],
                       check=True, capture_output=True)
        summary.update(confidence=round(confidence, 3), echoed_lines=echoed,
                       transcript_lines=transcript.count("\n") + 1)
        logger.info("transcript: %d lines (confidence %.2f)",
                    summary["transcript_lines"], confidence)
        if not apply:
            logger.info("dry run: nothing written. Last lines of the new transcript:\n%s",
                        "\n".join(transcript.strip().splitlines()[-12:]))
            return summary

        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
        key = lambda name: show.r2_key("raw", f"{run['id']}_{name}_rt{stamp}")  # noqa: E731
        processed = {s: r2_upload(tracks[s], key(s) + ".wav") for s in ("guest", "mira")}
        mixed_url = r2_upload(mixed, key("mixed") + ".wav")
        preview_url = r2_upload(preview, key("preview") + ".mp3")
        new = {**old,
               "sources": tracks["sources"], "processed": processed,
               "preview": preview_url, "alignment": tracks["alignment"],
               "unaligned": tracks["unaligned"], "pieces": tracks["pieces"],
               "bleed": tracks["bleed"],
               "retracked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
               "before_retrack": {k: v for k, v in old.items() if k != "before_retrack"}}
        if tracks["sources"].get("guest") == "local":
            try:
                new["leg_local"] = {"url": r2_upload(
                    pi.build_leg_local(tracks["guest"], raw, workdir / "leg_local.flac"),
                    key("leg_local") + ".flac")}
            except Exception:  # noqa: BLE001 — the clean tracks are the point
                logger.exception("leg file not rebuilt; keeping the old one")
        log["tracks"] = new
        sb_update("interview_runs", f"id=eq.{run['id']}",
                  {"recording_mixed_url": mixed_url, "grok_session_log": log})
        pkg = _live_package(run["id"])
        if pkg:
            flags = [f for f in (pkg.get("audio_quality_flag") or "").split(",")
                     if f and not f.startswith("unaligned:")]
            sb_update("editorial_packages", f"id=eq.{pkg['id']}",
                      {"transcript_raw": transcript,
                       "audio_quality_flag": ",".join(flags) or None})
            try:
                from reclean_transcript import reclean
                reclean(pkg["id"])
            except BaseException:  # noqa: BLE001 — the raw transcript is right
                logger.exception("cleaned transcript not redone; the raw one is in")
        summary.update(processed=processed, preview=preview_url,
                       package=(pkg or {}).get("id"))
        logger.info("written: %s", summary)
        return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit(__doc__)
    retrack(args[0], apply="--apply" in sys.argv)
