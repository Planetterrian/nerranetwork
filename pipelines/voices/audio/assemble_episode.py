"""Final episode assembly for The Age of AI (Nerra Voices).

Episode shape (spec §5.4):

    cold open → Act I narration → interview audio (redactions cut) →
    Act II narration → Act III narration → sign-off

with the show's music bed under the narration bookends, crossfades between
blocks, and one EBU R128 loudnorm pass to the network's -16 LUFS target.
Guest redactions ([{start, end, reason}] seconds into the interview audio)
are cut FIRST so no redacted audio survives into any later artifact.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CROSSFADE_SEC = 0.6
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"


def _run(cmd: list) -> None:
    logger.info("ffmpeg: %s …", " ".join(str(c) for c in cmd[:10]))
    subprocess.run([str(c) for c in cmd], check=True, capture_output=True,
                   timeout=3600)


def apply_redactions(interview_wav: Path, redactions: List[dict],
                     out_path: Path) -> Path:
    """Cut [start, end] second ranges out of the interview audio.

    Guest review submits free-text requests ([{note, resolved}]); the
    operator resolves them into {start, end} windows before approval.
    Entries without numeric start/end are SKIPPED LOUDLY rather than
    crashing assembly (July 2026 dry run: a raw note KeyError'd here).
    """
    cuttable = [r for r in redactions
                if isinstance(r.get("start"), (int, float))
                and isinstance(r.get("end"), (int, float))]
    skipped = len(redactions) - len(cuttable)
    if skipped:
        logger.error(
            "%d redaction request(s) have no start/end time window and were "
            "NOT cut — resolve them into {start, end} seconds before "
            "publishing: %s", skipped,
            [r.get("note", "")[:80] for r in redactions
             if r not in cuttable])
    redactions = cuttable
    if not redactions:
        return interview_wav
    # Build a keep-filter: select everything outside the redacted ranges.
    conditions = "+".join(
        f"between(t,{float(r['start'])},{float(r['end'])})" for r in redactions
    )
    _run(["ffmpeg", "-y", "-i", interview_wav,
          "-af", f"aselect='not({conditions})',asetpts=N/SR/TB",
          out_path])
    logger.info("Applied %d redaction cut(s)", len(redactions))
    return out_path


def _concat_with_crossfades(blocks: List[Path], out_path: Path) -> Path:
    if len(blocks) == 1:
        _run(["ffmpeg", "-y", "-i", blocks[0], out_path])
        return out_path
    inputs: list = []
    for b in blocks:
        inputs += ["-i", b]
    graph, prev = [], "0:a"
    for i in range(1, len(blocks)):
        label = f"x{i}"
        graph.append(
            f"[{prev}][{i}:a]acrossfade=d={CROSSFADE_SEC}:c1=tri:c2=tri[{label}]"
        )
        prev = label
    _run(["ffmpeg", "-y", *inputs,
          "-filter_complex", ";".join(graph),
          "-map", f"[{prev}]", out_path])
    return out_path


def assemble(narration: Dict[str, Path], interview_wav: Path,
             out_mp3: Path, *, music_bed: Optional[Path] = None,
             redactions: Optional[List[dict]] = None) -> Path:
    """Assemble the final episode MP3. ``narration`` keys: cold_open,
    act_one, act_two, act_three, sign_off (missing keys are skipped)."""
    with tempfile.TemporaryDirectory(prefix="aoa_assemble_") as tmp:
        tmpdir = Path(tmp)

        interview_clean = apply_redactions(
            interview_wav, redactions or [], tmpdir / "interview_redacted.wav")

        order = ["cold_open", "act_one", "interview", "act_two",
                 "act_three", "sign_off"]
        blocks: List[Path] = []
        for seg_id in order:
            if seg_id == "interview":
                blocks.append(interview_clean)
            elif seg_id in narration:
                blocks.append(narration[seg_id])
        if not blocks:
            raise RuntimeError("nothing to assemble — no narration, no interview")

        voice_track = _concat_with_crossfades(blocks, tmpdir / "voice.wav")

        if music_bed and Path(music_bed).exists():
            # Sidechain-ducked bed under the whole episode (same approach as
            # engine.audio._final_mix_cmd — music pulls down when voice is
            # present), then loudnorm + VBR encode.
            _run(["ffmpeg", "-y", "-i", voice_track,
                  "-stream_loop", "-1", "-i", music_bed,
                  "-filter_complex",
                  "[1:a]volume=0.35[m];"
                  "[m][0:a]sidechaincompress=threshold=0.05:ratio=8:"
                  "attack=50:release=500[duck];"
                  f"[0:a][duck]amix=inputs=2:duration=first,{LOUDNORM}",
                  "-c:a", "libmp3lame", "-q:a", "0", out_mp3])
        else:
            _run(["ffmpeg", "-y", "-i", voice_track,
                  "-af", LOUDNORM,
                  "-c:a", "libmp3lame", "-q:a", "0", out_mp3])
        logger.info("Episode assembled: %s", out_mp3)
        return out_mp3
