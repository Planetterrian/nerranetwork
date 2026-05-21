"""Convert faster-whisper transcript JSON into SRT subtitles.

Used by the YouTube long-form pipeline to burn the spoken dialogue
into the video as on-screen captions. We already produce the
transcript JSON post-TTS for Podcasting 2.0 ``<podcast:transcript>``
RSS support, so generating SRT is just a format conversion.

Transcript JSON shape (faster-whisper output)::

    {
      "language": "en",
      "duration": 397.28,
      "segments": [
        {"start": 0.0, "end": 1.46, "text": "...", "words": [...]},
        ...
      ]
    }

We only need ``segments[]`` — the per-word timing is finer-grained
than YouTube viewers can usefully read, and segment-level captions
match how YouTube's own auto-captions are paced (~5–10 s per cue).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def _format_srt_timestamp(seconds: float) -> str:
    """Format seconds as ``HH:MM:SS,mmm`` per the SRT spec."""
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rem_ms = divmod(total_ms, 3_600_000)
    minutes, rem_ms = divmod(rem_ms, 60_000)
    secs, ms = divmod(rem_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _wrap_caption_line(text: str, max_chars: int = 42) -> str:
    """Greedy word-wrap so each caption stays at ≤2 lines.

    SRT renders blank lines as cue terminators, so we use ``\\n``
    between lines within a single cue. 42 chars per line at ~30pt
    sits inside a 1920-wide frame with margins.
    """
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) >= 2:
                # Trailing words go in the second line — let it overflow
                # rather than truncate; the caption renderer can clip
                # gracefully but a missing word reads as a transcription
                # error.
                rest = [current] + [w for w in words[words.index(word) + 1:]]
                lines[-1] = " ".join(rest)
                return "\n".join(lines)
    if current:
        lines.append(current)
    return "\n".join(lines)


def transcript_to_srt(transcript_path: Path, srt_path: Path,
                      *, min_segment_duration: float = 0.4,
                      audio_offset_seconds: float = 0.0) -> Path:
    """Convert a faster-whisper transcript JSON into SRT subtitles.

    Parameters
    ----------
    transcript_path:
        Path to the JSON written by ``engine.transcripts``.
    srt_path:
        Where to write the ``.srt``.
    min_segment_duration:
        Skip cues shorter than this many seconds. Whisper sometimes
        emits sub-100ms artifacts for breath/punctuation that flicker
        on screen.
    audio_offset_seconds:
        Shift every cue right by this many seconds. Required when the
        Whisper transcript was generated against a voice-only "raw"
        MP3 but the video uses the post-mix final MP3 that prepends
        a music intro. The pipeline transcribes the raw voice to get
        clean word boundaries (music confuses Whisper), then offsets
        the SRT by ``config.audio.voice_intro_delay`` so the cues
        align with the speech inside the final mix. Without this
        offset every caption on a show with a 25 s music intro
        (Planetterrian, Unintended Consequences) appeared 25 s
        earlier than the corresponding speech on the YouTube long-
        form — operator reported the result as "terrible". Defaults
        to ``0.0`` for back-compat with any caller that already
        feeds an aligned transcript.

    Returns
    -------
    Path
        ``srt_path`` on success.
    """
    if not transcript_path.exists():
        raise FileNotFoundError(f"transcript not found: {transcript_path}")
    if audio_offset_seconds < 0:
        raise ValueError(
            f"audio_offset_seconds must be >= 0; got {audio_offset_seconds}"
        )

    data = json.loads(transcript_path.read_text(encoding="utf-8"))
    segments = data.get("segments") or []
    if not isinstance(segments, list):
        raise ValueError(
            f"transcript JSON {transcript_path} has no 'segments' list"
        )

    srt_path.parent.mkdir(parents=True, exist_ok=True)
    cues: List[str] = []
    cue_index = 1
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        start = seg.get("start")
        end = seg.get("end")
        text = (seg.get("text") or "").strip()
        if start is None or end is None or not text:
            continue
        try:
            start_f = float(start) + audio_offset_seconds
            end_f = float(end) + audio_offset_seconds
        except (TypeError, ValueError):
            continue
        if end_f - start_f < min_segment_duration:
            continue
        wrapped = _wrap_caption_line(text)
        cues.append(
            f"{cue_index}\n"
            f"{_format_srt_timestamp(start_f)} --> "
            f"{_format_srt_timestamp(end_f)}\n"
            f"{wrapped}\n"
        )
        cue_index += 1

    if not cues:
        logger.warning(
            "Transcript %s produced no usable cues — caption file will be empty",
            transcript_path,
        )

    # SRT files use \n line breaks but cues are separated by a blank line.
    try:
        srt_path.write_text("\n".join(cues), encoding="utf-8")
    except OSError as exc:
        # Disk full / permission denied / read-only mount — caller
        # should know and decide whether to skip burned-in captions.
        logger.error(
            "Failed to write SRT to %s (%s): %s",
            srt_path, type(exc).__name__, exc,
        )
        raise
    logger.info("Wrote %d caption cues → %s", len(cues), srt_path.name)
    return srt_path


def find_transcript_for_episode(digests_dir: Path,
                                episode_prefix: str,
                                episode_num: int,
                                date_str: str) -> Optional[Path]:
    """Locate the transcript JSON written by the TTS stage.

    The pipeline writes
    ``digests/<slug>/<prefix>_Ep{NNN}_{YYYYMMDD}_transcript.json``;
    this helper builds the path and returns it if the file exists,
    or ``None`` if it doesn't (caller decides whether to skip
    captions or fail).
    """
    candidate = digests_dir / (
        f"{episode_prefix}_Ep{episode_num:03d}_{date_str}_transcript.json"
    )
    if candidate.exists():
        return candidate
    logger.info("No transcript JSON at %s — captions will be skipped",
                candidate)
    return None
