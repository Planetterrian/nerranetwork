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


def _wrap_caption_line(text: str, max_chars: int = 55,
                       max_lines: int = 3) -> str:
    """Greedy word-wrap so each caption stays within *max_lines*.

    May 2026 operator report: "transcript appears to not be the full
    script shown." Root cause was the previous 2-line cap with
    ``lines[-1] = " ".join(rest)`` — when text overflowed the
    second line, the code OVERWROTE line 2's already-committed
    content with the remainder, losing whatever words had been
    placed in line 2 before the cutoff. The right-side text of
    every long cue was silently clipped.

    Fix: wider per-line budget (55 chars at FontSize=22 still sits
    well inside the 1920-wide long-form frame and the 1080-wide
    Shorts frame; mobile players are the bottleneck) and a true
    multi-line wrap. If a single Whisper segment is so long it
    exceeds ``max_chars * max_lines``, the LAST line is allowed
    to overflow horizontally (libass clips gracefully on the
    right) — better than dropping committed earlier lines.

    SRT renders blank lines as cue terminators, so we use ``\\n``
    between lines within a single cue.
    """
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    words = text.split()
    lines: List[str] = []
    current = ""
    i = 0
    while i < len(words):
        word = words[i]
        candidate = f"{current} {word}".strip()
        # Fits on the current line — accept and continue.
        if len(candidate) <= max_chars or not current:
            current = candidate
            i += 1
            continue
        # Doesn't fit: commit ``current`` and start a new line.
        lines.append(current)
        current = ""
        if len(lines) >= max_lines:
            # Already filled all ``max_lines`` complete lines.
            # Tack the remaining words onto the LAST committed
            # line and let libass clip on the right. The earlier
            # lines stay intact (no overwrite — that was the bug).
            rest = " ".join(words[i:])
            lines[-1] = (lines[-1] + " " + rest).strip()
            return "\n".join(lines)
        # Try this word on the new line in the next iteration.
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


def transcript_to_srt_window(
    transcript_path: Path,
    srt_path: Path,
    *,
    window_start_seconds: float,
    window_duration_seconds: float,
    audio_offset_seconds: float = 0.0,
    min_segment_duration: float = 0.4,
    wrap_max_chars: int = 24,
    wrap_max_lines: int = 2,
) -> Path:
    """Emit a SRT containing only the cues that fall inside a time
    window of the FINAL audio, with their timestamps shifted so the
    SRT starts at t=0 relative to the window.

    Used by the YouTube Shorts pipeline: the Shorts MP4 plays the
    audio slice ``[window_start_seconds, window_start_seconds +
    window_duration_seconds]`` of the final episode MP3, so the
    cues that originally landed within that slice need their
    timestamps rebased to the Shorts clip's own timeline.

    The wrap is tighter (24 chars / 2 lines) than the long-form
    default because vertical Shorts have a 1080-px wide frame
    versus 1920 long-form; wider line lengths spill past the visible
    edge on phones. May 2026 retune dropped these from 32 / 3 lines
    to 24 / 2 to match the FontSize=48 caption card upgrade in
    ``engine.video._SHORTS_SUBTITLES_FORCE_STYLE`` — larger font
    means fewer chars fit per line, and two lines is the comfortable
    reading ceiling on a phone-held-at-arm's-length Short.

    Parameters
    ----------
    transcript_path, srt_path, audio_offset_seconds, min_segment_duration:
        Same as ``transcript_to_srt``.
    window_start_seconds, window_duration_seconds:
        The slice of the FINAL audio (after the music intro offset
        has already been applied via ``audio_offset_seconds``) that
        the Shorts MP4 plays. Both in seconds, ``start`` >= 0.
    wrap_max_chars, wrap_max_lines:
        Per-line and per-cue limits — tighter than the long-form
        defaults to fit the vertical Shorts frame.

    Returns
    -------
    Path
        ``srt_path`` on success. The file may be empty if no cues
        fall inside the window (caller should treat that as
        "skip burn-in captions for this Shorts run").
    """
    if not transcript_path.exists():
        raise FileNotFoundError(f"transcript not found: {transcript_path}")
    if audio_offset_seconds < 0:
        raise ValueError(
            f"audio_offset_seconds must be >= 0; got {audio_offset_seconds}"
        )
    if window_start_seconds < 0:
        raise ValueError(
            f"window_start_seconds must be >= 0; got {window_start_seconds}"
        )
    if window_duration_seconds <= 0:
        raise ValueError(
            f"window_duration_seconds must be > 0; got {window_duration_seconds}"
        )

    data = json.loads(transcript_path.read_text(encoding="utf-8"))
    segments = data.get("segments") or []
    if not isinstance(segments, list):
        raise ValueError(
            f"transcript JSON {transcript_path} has no 'segments' list"
        )

    window_end = window_start_seconds + window_duration_seconds
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
            # Shift to final-audio timeline first, then check window.
            start_f = float(start) + audio_offset_seconds
            end_f = float(end) + audio_offset_seconds
        except (TypeError, ValueError):
            continue
        # Skip cues that don't overlap the Shorts window at all.
        if end_f <= window_start_seconds or start_f >= window_end:
            continue
        # Clip cues that straddle a window boundary so they don't
        # spill into negative-time or past-end territory.
        clipped_start = max(start_f, window_start_seconds)
        clipped_end = min(end_f, window_end)
        if clipped_end - clipped_start < min_segment_duration:
            continue
        # Rebase onto the Shorts clip's t=0 origin.
        rel_start = clipped_start - window_start_seconds
        rel_end = clipped_end - window_start_seconds
        wrapped = _wrap_caption_line(
            text, max_chars=wrap_max_chars, max_lines=wrap_max_lines,
        )
        cues.append(
            f"{cue_index}\n"
            f"{_format_srt_timestamp(rel_start)} --> "
            f"{_format_srt_timestamp(rel_end)}\n"
            f"{wrapped}\n"
        )
        cue_index += 1

    if not cues:
        logger.info(
            "Shorts window [%.2fs, %.2fs] (offset=%.2fs) contained no "
            "transcript cues — caption file will be empty",
            window_start_seconds, window_end, audio_offset_seconds,
        )

    try:
        srt_path.write_text("\n".join(cues), encoding="utf-8")
    except OSError as exc:
        logger.error(
            "Failed to write Shorts SRT to %s (%s): %s",
            srt_path, type(exc).__name__, exc,
        )
        raise
    logger.info(
        "Wrote %d Shorts caption cues → %s (window=[%.1fs, %.1fs])",
        len(cues), srt_path.name,
        window_start_seconds, window_end,
    )
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
