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


# ---------------------------------------------------------------------------
# ASS — per-word highlight for Shorts (TikTok / Reels look)
# ---------------------------------------------------------------------------

# Highlight colour for the "current word" in the per-word Shorts caption
# card. Cyan (#00D4FF) is one of the two Nerra Network accent colours
# (defined in styles/main.css as --nn-cyan) and lifts cleanly off the
# 50 %-opaque black caption card without bleeding into the white text
# of the surrounding words. ASS colour format is &HAABBGGRR so cyan
# (R=00, G=D4, B=FF) becomes &H00FFD400.
_HIGHLIGHT_PRIMARY_BGR = "&H00FFD400&"

# Inline override that resets the cue's primary colour to whatever
# ``force_style`` set as the default (white in
# ``_SHORTS_SUBTITLES_FORCE_STYLE``). ``\r`` without an argument reverts
# to the style default; we use this rather than hard-coding a white
# colour so per-show style overrides keep working in a future change.
_HIGHLIGHT_RESET = r"{\r}"


def _format_ass_timestamp(seconds: float) -> str:
    """Format ``seconds`` as ASS ``H:MM:SS.cs`` (centiseconds)."""
    if seconds < 0:
        seconds = 0.0
    cs_total = int(round(seconds * 100))
    h = cs_total // (3600 * 100)
    rem = cs_total % (3600 * 100)
    m = rem // (60 * 100)
    rem = rem % (60 * 100)
    s = rem // 100
    cs = rem % 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_escape(text: str) -> str:
    """Escape characters with special meaning in ASS dialogue text.

    ASS uses ``{`` and ``}`` to delimit inline override tags, and
    backslashes inside the braces are tag prefixes. We don't carry
    arbitrary user content through (Whisper output is normal speech)
    so the only realistic risk is curly braces in a quoted lyric or
    a model artefact. Strip them; keep everything else literal.
    """
    if not text:
        return ""
    return text.replace("{", "(").replace("}", ")")


_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,3,3,0,2,40,40,340,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _chunk_words(
    words: List[dict], *, max_chars: int, max_words_per_chunk: int,
) -> List[List[dict]]:
    """Group consecutive words into render-ready chunks.

    A "chunk" is the unit that occupies the caption card for the
    duration of its first→last word range; per-word highlight cycles
    inside a chunk. Splitting on chars (24) + max words (8) keeps
    each chunk to a comfortable 1–2 line render at FontSize=48 on a
    1080-wide frame.
    """
    chunks: List[List[dict]] = []
    current: List[dict] = []
    current_chars = 0
    for w in words:
        token = (w.get("word") or "").strip()
        if not token:
            continue
        prospective = current_chars + len(token) + (1 if current else 0)
        if current and (
            prospective > max_chars or len(current) >= max_words_per_chunk
        ):
            chunks.append(current)
            current = [w]
            current_chars = len(token)
        else:
            current.append(w)
            current_chars = prospective
    if current:
        chunks.append(current)
    return chunks


def _render_chunk_dialogues(
    chunk: List[dict],
    *,
    window_start: float,
    window_end: float,
    audio_offset: float,
    min_word_duration: float = 0.08,
) -> List[str]:
    """Emit one ASS Dialogue line per word in the chunk.

    Each line shows the SAME text (the whole chunk) with one word
    coloured in the highlight cyan and the others left at the style
    default. That produces the TikTok "current word" visual: the
    whole sentence is visible, but the active word pops.

    Word timestamps are first shifted onto the final-audio timeline
    (``audio_offset``), then rebased to the Shorts clip's t=0 origin
    (``window_start``), then clipped to the window.
    """
    if not chunk:
        return []
    tokens = [(w.get("word") or "").strip() for w in chunk]
    tokens = [t for t in tokens if t]
    if not tokens:
        return []

    lines: List[str] = []
    for idx, w in enumerate(chunk):
        token = (w.get("word") or "").strip()
        if not token:
            continue
        try:
            ws = float(w["start"]) + audio_offset
            we = float(w["end"]) + audio_offset
        except (KeyError, TypeError, ValueError):
            continue
        # Clip to the Shorts window, then rebase to t=0.
        ws = max(ws, window_start)
        we = min(we, window_end)
        if we - ws < min_word_duration:
            we = ws + min_word_duration
        rel_start = ws - window_start
        rel_end = we - window_start
        if rel_end <= 0 or rel_start >= (window_end - window_start):
            continue

        # Build the cue text. The current word is wrapped in a
        # primary-colour override; everything else stays default.
        parts: List[str] = []
        for j, t in enumerate(tokens):
            esc = _ass_escape(t)
            if j == idx:
                parts.append(f"{{\\1c{_HIGHLIGHT_PRIMARY_BGR}}}{esc}{_HIGHLIGHT_RESET}")
            else:
                parts.append(esc)
        cue_text = " ".join(parts)
        lines.append(
            f"Dialogue: 0,"
            f"{_format_ass_timestamp(rel_start)},"
            f"{_format_ass_timestamp(rel_end)},"
            f"Default,,0,0,0,,{cue_text}"
        )
    return lines


def transcript_to_ass_window(
    transcript_path: Path,
    ass_path: Path,
    *,
    window_start_seconds: float,
    window_duration_seconds: float,
    audio_offset_seconds: float = 0.0,
    wrap_max_chars: int = 24,
    max_words_per_chunk: int = 8,
) -> Path:
    """Emit an ASS caption file with per-word highlighting for a Shorts
    window.

    Drop-in replacement for ``transcript_to_srt_window`` when the
    Whisper transcript carries per-word timestamps (the network's
    primary transcript invocation in ``engine.transcripts`` has
    ``word_timestamps=True`` so this is the common case). Falls back
    silently to an empty file if no segments / no word data exists
    in the window — the caller treats an empty caption file the same
    as the SRT path (skip burn-in).

    Visual: each chunk of ~24 chars / ≤8 words occupies the bottom-
    third caption card; the active word is rendered in cyan
    (``&H00FFD400``) while the rest of the chunk stays at the style
    default (white from ``_SHORTS_SUBTITLES_FORCE_STYLE``). As speech
    progresses, the highlight steps from one word to the next at
    Whisper's per-word timestamps. The chunk transition is implicit:
    the chunk's last word's end is the start of the next chunk's
    first word.

    The default style block in the file is a sensible Shorts-tuned
    baseline; ffmpeg's ``subtitles`` filter overrides it via
    ``force_style=`` so the values pinned in
    ``engine.video._SHORTS_SUBTITLES_FORCE_STYLE`` remain the source
    of truth at render time.
    """
    if window_start_seconds < 0:
        raise ValueError(
            f"window_start_seconds must be >= 0, got {window_start_seconds}"
        )
    if window_duration_seconds <= 0:
        raise ValueError(
            f"window_duration_seconds must be > 0, got {window_duration_seconds}"
        )
    if audio_offset_seconds < 0:
        raise ValueError(
            f"audio_offset_seconds must be >= 0, got {audio_offset_seconds}"
        )

    try:
        data = json.loads(transcript_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.error("Transcript not found: %s", transcript_path)
        raise
    except json.JSONDecodeError as exc:
        logger.error("Transcript JSON malformed (%s): %s", transcript_path, exc)
        raise

    segments = data.get("segments", []) if isinstance(data, dict) else []
    window_end = window_start_seconds + window_duration_seconds

    dialogue_lines: List[str] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        words = seg.get("words") or []
        if not words:
            continue
        # Filter words to the Shorts window before chunking — avoids
        # chunks that straddle the boundary.
        in_window: List[dict] = []
        for w in words:
            if not isinstance(w, dict):
                continue
            try:
                ws = float(w["start"]) + audio_offset_seconds
                we = float(w["end"]) + audio_offset_seconds
            except (KeyError, TypeError, ValueError):
                continue
            if we <= window_start_seconds or ws >= window_end:
                continue
            in_window.append(w)
        if not in_window:
            continue
        for chunk in _chunk_words(
            in_window,
            max_chars=wrap_max_chars,
            max_words_per_chunk=max_words_per_chunk,
        ):
            dialogue_lines.extend(
                _render_chunk_dialogues(
                    chunk,
                    window_start=window_start_seconds,
                    window_end=window_end,
                    audio_offset=audio_offset_seconds,
                )
            )

    body = _ASS_HEADER + "\n".join(dialogue_lines) + ("\n" if dialogue_lines else "")
    try:
        ass_path.write_text(body, encoding="utf-8")
    except OSError as exc:
        logger.error(
            "Failed to write Shorts ASS to %s (%s): %s",
            ass_path, type(exc).__name__, exc,
        )
        raise
    if not dialogue_lines:
        logger.info(
            "Shorts window [%.2fs, %.2fs] (offset=%.2fs) contained no "
            "word-level transcript data — ASS file written empty",
            window_start_seconds, window_end, audio_offset_seconds,
        )
    else:
        logger.info(
            "Wrote %d per-word Shorts caption events → %s (window=[%.1fs, %.1fs])",
            len(dialogue_lines), ass_path.name,
            window_start_seconds, window_end,
        )
    return ass_path


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
