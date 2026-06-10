"""Podcast chapter generation from script section markers.

Parses an LLM-generated podcast script to identify section boundaries,
calculates approximate chapter timestamps using word-count proportions,
and writes Podcasting 2.0-compatible chapter JSON files.

Usage in the pipeline (run_show.py):
    1. After podcast script is generated + cleaned, call ``parse_chapters()``
    2. After final MP3 is produced, call ``calculate_timestamps()``
    3. Call ``write_chapters_json()`` to persist alongside the episode
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Chapter:
    """A single chapter in a podcast episode."""

    title: str
    startTime: float = 0.0
    endTime: float = 0.0
    # Word range within the script (used for proportion calculation)
    word_start: int = 0
    word_end: int = 0
    # Character range within the script (used for text splitting)
    char_start: int = 0
    char_end: int = 0


# Sentence terminators that close a chapter title. ``…`` and Russian
# ``.`` style markers are included so Russian shows benefit too.
_SENTENCE_END_RE = re.compile(r"([.!?…])\s+")


def _first_sentence_as_title(text: str, max_chars: int = 60) -> str:
    """Extract the first sentence of *text* and return a chapter-title
    string (max ``max_chars``).

    Used by the chapter auto-segmentation fallback. Apple Podcasts and
    Pocket Casts surface chapter titles in the player UI, so a title
    derived from actual content (e.g. "Tesla unveils robotaxi service
    in Texas") is dramatically more useful than the previous
    "Segment 2" placeholder. Returns "" if no clean sentence is
    extractable — caller falls back to the numeric placeholder.
    """
    if not text:
        return ""
    # Trim leading whitespace/markdown fragments and pick the first
    # non-blank line so headers/blank gaps don't poison the title.
    cleaned = text.lstrip().lstrip("*_-•> ").lstrip()
    if not cleaned:
        return ""
    # First sentence — anything up to the first . ! ? … plus space.
    match = _SENTENCE_END_RE.split(cleaned, maxsplit=1)
    candidate = match[0].strip() if match else cleaned.strip()
    if not candidate:
        return ""
    # Strip residual inline markdown so the title reads cleanly.
    candidate = re.sub(r"[*_`]+", "", candidate).strip()
    # Truncate to max_chars on a word boundary (no mid-word ellipses).
    if len(candidate) > max_chars:
        truncated = candidate[: max_chars - 1].rsplit(" ", 1)[0]
        candidate = truncated.rstrip(",;:") + "…"
    # Sanity: titles shouldn't be one-word fragments or just a number.
    if len(candidate) < 8 or candidate.replace(".", "").isdigit():
        return ""
    return candidate


def parse_chapters(
    script: str,
    section_markers: list,
    *,
    show_name: str = "",
    min_chapters: int = 4,
    auto_segment_target_seconds: float = 90.0,
    estimated_words_per_minute: float = 165.0,
) -> List[Chapter]:
    """Parse a podcast script to identify section boundaries.

    Parameters
    ----------
    script:
        The cleaned podcast script text (after speaker prefix removal,
        pronunciation fixes, etc.).
    section_markers:
        List of ``SectionMarker`` objects (or dicts with ``pattern`` and
        ``title`` keys) from the show's YAML config.
    show_name:
        Show name for logging context.

    Returns
    -------
    list[Chapter]
        Ordered list of chapters with word boundaries set.  Timestamps
        are set to 0 — call ``calculate_timestamps()`` after the audio
        is produced to map word proportions to real timestamps.
    """
    if not section_markers:
        logger.info("No section markers configured — skipping chapter parsing")
        return []

    # Build compiled patterns
    compiled_markers = []
    for marker in section_markers:
        pattern = marker.pattern if hasattr(marker, "pattern") else marker.get("pattern", "")
        title = marker.title if hasattr(marker, "title") else marker.get("title", "")
        where = marker.where if hasattr(marker, "where") else (
            marker.get("where", "") if isinstance(marker, dict) else ""
        )
        if not pattern or not title:
            continue
        try:
            compiled_markers.append((re.compile(pattern, re.IGNORECASE), title, where or ""))
        except re.error as exc:
            logger.warning("Invalid chapter marker regex %r: %s", pattern, exc)

    if not compiled_markers:
        return []

    # Split script into words with their character positions
    words = script.split()
    total_words = len(words)
    total_chars = len(script)
    if total_words == 0:
        return []

    # Scan line by line, tracking both word index and character offset
    lines = script.splitlines(keepends=True)
    word_idx = 0
    char_offset = 0
    matches: list[tuple[int, int, str]] = []  # (word_index, char_offset, title)
    matched_titles: set[str] = set()

    # Positional windows for ``where``-constrained markers. The opening
    # window is generous (10%, min 60 words) so a long cold-open hook
    # can't push the intro line out of range; the closing window (last
    # 15%) comfortably covers teaser + sign-off on a 1500+-word script.
    start_window_end = max(int(total_words * 0.10), 60)
    end_window_start = min(int(total_words * 0.85), max(total_words - 60, 0))

    for line in lines:
        line_words = line.split()
        line_word_count = len(line_words)
        line_stripped = line.rstrip("\n\r")

        for regex, title, where in compiled_markers:
            # Each semantic section appears once per episode. Without
            # this, brand mentions late in the script re-trigger early
            # markers (the Tesla closing was titled "Introduction" on
            # every episode through Ep505).
            if title in matched_titles:
                continue
            if where == "start" and word_idx > start_window_end:
                continue
            if where == "end" and word_idx < end_window_start:
                continue
            if regex.search(line_stripped):
                matches.append((word_idx, char_offset, title))
                matched_titles.add(title)
                break  # Only match first marker per line

        word_idx += line_word_count
        char_offset += len(line)

    if not matches:
        logger.info("No chapter markers matched in podcast script for %s", show_name)
        return []

    # Build Chapter objects from matches
    chapters: list[Chapter] = []
    for i, (w_start, c_start, title) in enumerate(matches):
        w_end = matches[i + 1][0] if i + 1 < len(matches) else total_words
        c_end = matches[i + 1][1] if i + 1 < len(matches) else total_chars
        chapters.append(Chapter(
            title=title,
            word_start=w_start,
            word_end=w_end,
            char_start=c_start,
            char_end=c_end,
        ))

    # ------------------------------------------------------------------
    # Auto-segmentation fallback. Operator caught (May 2026) that TST
    # episodes ship with only ``Introduction`` + ``Closing`` chapters
    # because the per-show ``section_markers`` regex don't tolerate the
    # variations the LLM and Whisper produce. The result was a 7-minute
    # block called "Introduction" with no nav. When the matched chapter
    # count is below ``min_chapters`` AND the first chapter spans most
    # of the script, we splice extra chapters at paragraph boundaries
    # roughly every ``auto_segment_target_seconds`` of speech so
    # listeners always get useful navigation. May 8 2026: titles now
    # derive from each segment's first sentence (truncated to ~50
    # chars) instead of the previous generic ``Segment N`` placeholder
    # — Apple Podcasts and Pocket Casts surface chapter titles in the
    # player UI, and "Segment 2" tells the listener nothing about
    # whether to skip ahead.
    if len(chapters) < min_chapters and total_words > 0:
        words_per_segment = max(
            int(estimated_words_per_minute * (auto_segment_target_seconds / 60.0)),
            120,
        )
        # Find paragraph break offsets (blank-line-separated chunks).
        para_break_word_idx: list[tuple[int, int]] = []  # (word_index, char_offset)
        idx = 0
        char_idx = 0
        for line in lines:
            line_word_count = len(line.split())
            if line.strip() == "" and idx > 0:
                para_break_word_idx.append((idx, char_idx))
            idx += line_word_count
            char_idx += len(line)

        # Build augmented chapter list — splice auto-segments into the
        # FIRST chapter (the long "Introduction") only. Splitting later
        # chapters tends to cut hand-titled sections.
        if chapters and para_break_word_idx:
            head = chapters[0]
            tail = chapters[1:]
            head_w_end = head.word_end
            head_c_end = head.char_end

            # Accept paragraph breaks inside the head chapter that are at
            # least ``words_per_segment`` words apart.
            insertions: list[tuple[int, int]] = []
            last_w = head.word_start
            for w, c in para_break_word_idx:
                if w <= head.word_start or w >= head_w_end:
                    continue
                if w - last_w >= words_per_segment:
                    insertions.append((w, c))
                    last_w = w

            if insertions:
                rebuilt: list[Chapter] = [Chapter(
                    title=head.title,
                    word_start=head.word_start,
                    word_end=insertions[0][0],
                    char_start=head.char_start,
                    char_end=insertions[0][1],
                )]
                for n, (w, c) in enumerate(insertions, start=2):
                    next_w = insertions[n - 1][0] if n - 1 < len(insertions) else head_w_end
                    next_c = insertions[n - 1][1] if n - 1 < len(insertions) else head_c_end
                    # Title from the first sentence of the segment text.
                    # Falls back to "Segment N" if extraction fails (very
                    # short text, no sentence-ending punctuation, etc).
                    seg_text = script[c:next_c]
                    title = _first_sentence_as_title(seg_text) or f"Segment {n}"
                    rebuilt.append(Chapter(
                        title=title,
                        word_start=w,
                        word_end=next_w,
                        char_start=c,
                        char_end=next_c,
                    ))
                chapters = rebuilt + tail
                logger.info(
                    "Auto-segmented head chapter for %s into %d segments "
                    "(target %.0fs each, ~%d words)",
                    show_name or "show",
                    len(insertions) + 1,
                    auto_segment_target_seconds,
                    words_per_segment,
                )

    # Post-processing robustness (added after reviewing May 28 episodes)
    # Collapse consecutive duplicate titles (very common on quiet days).
    if chapters:
        deduped = [chapters[0]]
        for ch in chapters[1:]:
            if ch.title != deduped[-1].title:
                deduped.append(ch)
        chapters = deduped

    logger.info(
        "Parsed %d chapters for %s: %s",
        len(chapters),
        show_name or "show",
        [c.title for c in chapters],
    )
    return chapters


def split_script_at_chapters(
    script: str,
    chapters: List[Chapter],
) -> List[str]:
    """Split a podcast script into text sections at chapter boundaries.

    Uses the ``char_start``/``char_end`` character offsets stored by
    ``parse_chapters()`` to slice the script into one text segment per
    chapter.  Each segment can then be synthesized separately via TTS.

    Parameters
    ----------
    script:
        The full podcast script text (same text passed to ``parse_chapters()``).
    chapters:
        Chapters with ``char_start``/``char_end`` set.

    Returns
    -------
    list[str]
        Ordered list of text sections, one per chapter.
        Empty sections are preserved to keep alignment with chapters.
    """
    if not chapters:
        return [script] if script.strip() else []

    # If there is text before the first chapter marker, insert a "Preamble"
    # Chapter so that (a) the content is not lost and (b) len(sections) ==
    # len(chapters), keeping alignment for calculate_timestamps().
    first_ch = chapters[0]
    if first_ch.char_start > 0:
        preamble_text = script[:first_ch.char_start].strip()
        if preamble_text:
            chapters.insert(0, Chapter(
                title="Preamble",
                word_start=0,
                word_end=first_ch.word_start,
                char_start=0,
                char_end=first_ch.char_start,
            ))

    sections: list[str] = []
    for ch in chapters:
        section = script[ch.char_start:ch.char_end].strip()
        sections.append(section)

    return sections


def calculate_timestamps(
    chapters: List[Chapter],
    total_duration: float,
    *,
    music_intro_offset: float = 0.0,
) -> List[Chapter]:
    """Map word-count proportions to real timestamps.

    Parameters
    ----------
    chapters:
        Chapters with ``word_start``/``word_end`` set by ``parse_chapters()``.
    total_duration:
        Total duration of the final mixed MP3 in seconds.
    music_intro_offset:
        Seconds of music-only time before the voice content begins.
        Calculated as ``intro_duration + voice_intro_delay`` from audio config.
        The first chapter starts after this offset.

    Returns
    -------
    list[Chapter]
        Same chapters with ``startTime`` and ``endTime`` populated.
    """
    if not chapters or total_duration <= 0:
        return chapters

    # Voice content occupies the time after the music intro
    # We don't subtract outro since voice may overlap with it (crossfade)
    voice_duration = total_duration - music_intro_offset
    if voice_duration <= 0:
        voice_duration = total_duration
        music_intro_offset = 0.0

    # Total words across all chapters
    total_words = chapters[-1].word_end if chapters else 0
    if total_words <= 0:
        return chapters

    for ch in chapters:
        proportion_start = ch.word_start / total_words
        proportion_end = ch.word_end / total_words
        ch.startTime = round(music_intro_offset + proportion_start * voice_duration, 1)
        ch.endTime = round(music_intro_offset + proportion_end * voice_duration, 1)

    # Clamp final chapter end to total duration
    if chapters:
        chapters[-1].endTime = round(total_duration, 1)

    return chapters


def write_chapters_json(
    chapters: List[Chapter],
    output_path: Path,
    *,
    episode_title: str = "",
) -> Optional[Path]:
    """Write chapters in Podcasting 2.0 JSON Chapters format.

    Format spec: https://github.com/Podcastindex-org/podcast-namespace/blob/main/chapters/jsonChapters.md

    Parameters
    ----------
    chapters:
        Chapters with timestamps populated.
    output_path:
        Where to write the JSON file.
    episode_title:
        Optional episode title for the top-level ``title`` field.

    Returns
    -------
    Path or None
        The output path on success, ``None`` if no chapters or on error.
    """
    if not chapters:
        logger.info("No chapters to write")
        return None

    data = {
        "version": "1.2.0",
        "chapters": [],
    }
    if episode_title:
        data["title"] = episode_title

    for ch in chapters:
        entry = {
            "startTime": ch.startTime,
            "title": ch.title,
        }
        if ch.endTime > ch.startTime:
            entry["endTime"] = ch.endTime
        data["chapters"].append(entry)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Chapters JSON written: %s (%d chapters)", output_path, len(chapters))
        return output_path
    except Exception as exc:
        logger.error("Failed to write chapters JSON: %s", exc)
        return None
