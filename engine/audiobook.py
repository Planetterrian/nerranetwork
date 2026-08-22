"""Narrate a compiled book volume into a retail-ready audiobook.

Reuses the network's existing voice stack end to end: chapter text from
``engine.book_compiler`` -> ``engine.tts.synthesize`` on the Grok provider
with the show's own cloned voice -> per-chapter MP3s (the format the
retail aggregators ingest) -> one M4B with real chapter markers (the
format listeners and direct sales want). ffmpeg does the container work,
exactly as the episode pipeline does.

Cost: Grok TTS is priced per character (``engine.tracking``); a 20-chapter
volume of ~2,000-word essays is ~250k characters, roughly $1 of TTS — the
whole point of product B6 is that the audiobook is a rounding error on
top of content the network already paid to write.

Every volume opens and closes with the AI-narration disclosure
(``book_compiler.AI_NARRATION_DISCLOSURE``): network policy, and a listing
requirement on every retail channel that accepts digital narration.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.audio import get_audio_duration
from engine.book_compiler import (
    BookChapter,
    BookVolume,
    chapter_tts_text,
    closing_credits_text,
    opening_credits_text,
)
from engine.tracking import TTS_PROVIDER_PRICING

logger = logging.getLogger(__name__)

#: Retail-aggregator-friendly per-chapter MP3 settings (192 kbps CBR
#: 44.1 kHz is the common denominator of the ingest specs).
MP3_ARGS = ["-ar", "44100", "-b:a", "192k", "-ac", "1"]

#: M4B (AAC) settings for the combined audiobook file.
M4B_ARGS = ["-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-ac", "1"]


def estimate_tts_cost_usd(texts: List[str]) -> float:
    chars = sum(len(t) for t in texts)
    return (chars / 1000.0) * TTS_PROVIDER_PRICING["grok"]


def narration_texts(volume: BookVolume,
                    chapters: List[BookChapter]) -> List[Tuple[str, str]]:
    """(track_title, narration_text) for every audio track in order."""
    tracks: List[Tuple[str, str]] = [
        ("Opening Credits", opening_credits_text(volume))
    ]
    tracks += [
        (c.heading, chapter_tts_text(c))
        for c in chapters
    ]
    tracks.append(("Closing Credits", closing_credits_text(volume)))
    return tracks


def synthesize_tracks(
    volume: BookVolume,
    chapters: List[BookChapter],
    out_dir: Path,
    *,
    api_key: str,
    voice_id: str,
    language_code: str = "",
) -> List[Tuple[str, Path]]:
    """Narrate every track to ``track_NNN.mp3`` in *out_dir*.

    Idempotent per track — and SAFELY so: each MP3 gets a
    ``track_NNN.txthash`` sidecar holding the hash of the narration text
    it was synthesized from, and a cached MP3 is reused only when the
    hash still matches. That is what lets the caller persist/restore
    this directory through R2 across ephemeral CI runners without ever
    reusing audio whose script has since changed (e.g. the 2026-08-22
    spoken-title change invalidates every chapter open automatically).
    """
    import hashlib

    from engine.tts import prepare_text_for_tts, synthesize

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    produced: List[Tuple[str, Path]] = []
    for i, (title, text) in enumerate(narration_texts(volume, chapters)):
        mp3 = out_dir / f"track_{i:03d}.mp3"
        sidecar = out_dir / f"track_{i:03d}.txthash"
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        cached = (mp3.exists() and mp3.stat().st_size > 0
                  and sidecar.exists()
                  and sidecar.read_text(encoding="utf-8").strip() == text_hash)
        if cached:
            logger.info("audiobook: keeping existing %s (text unchanged)",
                        mp3.name)
        else:
            if mp3.exists():
                logger.info("audiobook: narration text changed — "
                            "re-synthesizing %s", mp3.name)
            logger.info("audiobook: narrating %r (%d chars)", title, len(text))
            synthesize(
                prepare_text_for_tts(text),
                voice_id,
                mp3,
                api_key=api_key,
                provider="grok",
                language_code=language_code or volume.language,
                # No speech wrap: books read at an even register; the
                # <fast> energy wrap is an episode convention.
            )
            sidecar.write_text(text_hash, encoding="utf-8")
        produced.append((title, mp3))
    return produced


def _ffmetadata(tracks: List[Tuple[str, Path]],
                durations: Dict[Path, float]) -> str:
    """FFMETADATA1 chapter list from per-track durations (milliseconds)."""
    lines = [";FFMETADATA1"]
    offset_ms = 0
    for title, path in tracks:
        dur_ms = int(round((durations.get(path) or 0.0) * 1000))
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={offset_ms}",
            f"END={offset_ms + dur_ms}",
            "title=" + title.replace("\n", " "),
        ]
        offset_ms += dur_ms
    return "\n".join(lines) + "\n"


def build_m4b(
    volume: BookVolume,
    tracks: List[Tuple[str, Path]],
    out_m4b: Path,
    *,
    cover_png: Optional[Path] = None,
) -> Path:
    """Concatenate the narrated tracks into one chaptered M4B."""
    out_m4b = Path(out_m4b)
    out_m4b.parent.mkdir(parents=True, exist_ok=True)
    work = out_m4b.parent

    durations = {p: (get_audio_duration(p) or 0.0) for _, p in tracks}
    missing = [p.name for p, d in durations.items() if not d]
    if missing:
        raise RuntimeError(f"audiobook: unreadable track durations: {missing}")

    concat_list = work / "concat.txt"
    concat_list.write_text(
        "".join(f"file '{p.resolve().as_posix()}'\n" for _, p in tracks),
        encoding="utf-8",
    )
    meta = work / "chapters.ffmetadata"
    meta.write_text(_ffmetadata(tracks, durations), encoding="utf-8")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-i", str(meta),
    ]
    have_cover = bool(cover_png and Path(cover_png).exists())
    if have_cover:
        cmd += ["-i", str(cover_png)]
    cmd += ["-map_metadata", "1", "-map", "0:a"]
    if have_cover:
        cmd += ["-map", "2:v", "-c:v", "png", "-disposition:v", "attached_pic"]
    cmd += M4B_ARGS
    cmd += [
        "-metadata", f"title={volume.title}",
        "-metadata", f"artist={volume.author}",
        "-metadata", f"album={volume.title}",
        "-metadata", "genre=Audiobook",
        "-movflags", "+faststart",
        str(out_m4b),
    ]
    logger.info("audiobook: assembling %s (%d tracks, %s)",
                out_m4b.name, len(tracks),
                f"{sum(durations.values()) / 3600:.1f}h")
    subprocess.run(cmd, check=True, capture_output=True)
    return out_m4b


def total_duration_seconds(tracks: List[Tuple[str, Path]]) -> float:
    return sum((get_audio_duration(p) or 0.0) for _, p in tracks)
