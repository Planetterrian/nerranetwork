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


# Digest FORMATTING templates show the heading shape as a literal
# ``**Title: Source Name**`` and the model periodically reproduces the
# label instead of substituting (SpaceX Ep58/60/66/68/70, DP Pod Ep35 —
# Aug 2026 review). Chapter titles were one of the two surfaces with no
# defense (the other, the digest itself, is repaired at generation time).
# Same fix engine/youtube_titles.py has carried since July.
_TITLE_LABEL_RE = re.compile(r"^(?:title|headline)\s*\d*\s*[:\-—]\s*", re.IGNORECASE)


def _strip_title_label(title: str) -> str:
    return _TITLE_LABEL_RE.sub("", title or "").strip()


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
    candidate = _strip_title_label(re.sub(r"[*_`]+", "", candidate).strip())
    # Truncate to max_chars on a word boundary (no mid-word ellipses).
    if len(candidate) > max_chars:
        truncated = candidate[: max_chars - 1].rsplit(" ", 1)[0]
        candidate = truncated.rstrip(",;:") + "…"
    # Sanity: titles shouldn't be one-word fragments or just a number.
    if len(candidate) < 8 or candidate.replace(".", "").isdigit():
        return ""
    return candidate


# Words that carry no topical signal when matching a script segment to a
# clean digest headline (auto-segment titling). Kept small + lowercase.
_TITLE_MATCH_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "at", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "it", "its", "this", "that", "these", "those", "into", "over",
    "after", "before", "about", "than", "then", "so", "we", "you", "they",
    "their", "our", "his", "her", "new", "now", "up", "out", "has", "have",
})


def _tokenize_for_match(text: str) -> set:
    """Lowercase content-word token set for overlap scoring."""
    toks = re.findall(r"[a-z0-9]{3,}", (text or "").lower())
    return {t for t in toks if t not in _TITLE_MATCH_STOPWORDS}


def _best_headline_for_segment(
    seg_text: str, headlines: List[str], used: set,
    max_chars: int = 60,
) -> str:
    """Pick the unused digest *headline* that best overlaps *seg_text*.

    Auto-segment titles drawn from the segment's raw first sentence are
    often mid-thought fragments ("Knowing this, when you hear claims…").
    The episode digest already carries clean, capitalised per-story
    headlines (``extract_story_headlines``); matching each spoken segment
    to its originating headline by content-word overlap yields a proper
    title ("Tesla unveils robotaxi service in Texas"). Returns "" when no
    headline overlaps the segment meaningfully (caller falls back to the
    first-sentence title, then ``Segment N``).
    """
    if not headlines:
        return ""
    seg_tokens = _tokenize_for_match(seg_text)
    if not seg_tokens:
        return ""
    best_title = ""
    best_score = 0
    for idx, h in enumerate(headlines):
        if h in used:
            continue
        if _is_hook_candidate(h, idx, max_chars):
            # Not a title: extract_story_headlines leads with the digest's
            # blockquote HOOK — a full sentence (needed as image context,
            # useless here). Raw token-overlap favors the longest
            # candidate (Omni View Ep160, 2026-08-30: the 130-char hook
            # beat the real summit headline). The 08-30 fix skipped
            # EVERYTHING over max_chars, which on 2026-09-02 (Ep163)
            # threw away 7 of 8 real headlines (62-91 chars) and shipped
            # first-sentence fragments instead. Only hook-length
            # candidates are skipped now; a long real headline competes
            # and is shortened cleanly by ``_clip_title``.
            continue
        h_tokens = _tokenize_for_match(h)
        if not h_tokens:
            continue
        overlap = len(seg_tokens & h_tokens)
        # Require ≥2 shared content words (or ≥half a short headline) so an
        # incidental single-word match doesn't mis-title a segment.
        if overlap > best_score and (
            overlap >= 2 or overlap >= max(1, len(h_tokens) // 2)
        ):
            best_score = overlap
            best_title = h
    if not best_title:
        return ""
    used.add(best_title)  # claim the headline so the next segment can't reuse it
    return _clip_title(best_title, max_chars)


# A candidate longer than ``max_chars * _HOOK_LENGTH_FACTOR`` is the
# digest's lead HOOK (a full sentence), never a headline.
_HOOK_LENGTH_FACTOR = 2


def _is_hook_candidate(h: str, idx: int, max_chars: int) -> bool:
    """True when *h* is the digest's lead hook rather than a headline.

    ``extract_story_headlines`` puts the blockquote hook FIRST, so an
    over-budget first candidate is the hook (Tesla Ep592: the 104-char
    hook "Installers face six-figure losses after Tesla stopped…" would
    otherwise out-score every real headline for the lead segment).
    Anything longer than twice the budget is a sentence, not a title,
    wherever it sits.
    """
    n = len(h)
    return n > max_chars * _HOOK_LENGTH_FACTOR or (idx == 0 and n > max_chars)

# Function words a shortened headline must not end on — "…criticizes
# Chinese actions at" reads as a cut; "…criticizes Chinese actions" reads
# as a title.
_DANGLING_TAIL = frozenset(
    "a an the and or but nor of at in on for to with by as from after over "
    "into amid while than that its their his her our this these those "
    "under before between against about via per not no is are was were be "
    "has have had will would could should can may might who which when "
    "where how what why if so yet up more".split()
)


def _clip_title(raw: str, max_chars: int = 60) -> str:
    """Fit a real digest headline into *max_chars* WITHOUT an ellipsis.

    A headline is a title, so a trailing "…" is wrong on every surface
    (seek bar, description, on-screen card): it reads as a broken
    sentence and the on-screen card stage rightly refuses such titles.
    The cut goes through ``engine.titles.clip_words`` (the one sanctioned
    clipper) and then drops any dangling function word. Only when the
    clean cut would lose more than half the headline does the legacy
    ellipsis clip remain, so a title can never collapse to two words.
    """
    title = _strip_title_label(re.sub(r"[*_`]+", "", raw or "").strip())
    if len(title) <= max_chars:
        return title
    from engine.titles import clip_words
    words = clip_words(title, max_chars, ellipsis="").split()
    while words and words[-1].lower().strip(",;:'\"") in _DANGLING_TAIL:
        words.pop()
    clean = " ".join(words).rstrip(",;:—–-")
    if len(clean) >= max_chars // 2:
        return clean
    return title[: max_chars - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _headline_anchored_insertions(
    lines: List[str],
    head_word_start: int,
    head_word_end: int,
    story_headlines: List[str],
    min_segment_words: int = 60,
    max_chars: int = 60,
) -> list:
    """Anchor auto-segment boundaries where each digest story BEGINS.

    The legacy auto-segment slices the head chapter every ~90s of speech
    at arbitrary paragraph breaks, then fits a headline to whatever text
    lands in each window — so a chapter can carry one story's title while
    starting mid-way through another (Tesla Ep548, July 21 2026). Shows
    whose prompts ban spoken section labels hit this on most episodes
    because their keyword markers never match.

    This variant inverts the mapping: for each digest headline, find the
    paragraph inside the head span whose content words best overlap it,
    and start a chapter (bearing that headline) at that paragraph. Titles
    and boundaries then agree by construction. Returns
    ``[(word_idx, char_offset, title), ...]`` sorted by position, or
    ``[]`` when fewer than two headlines anchor confidently — callers
    fall back to the legacy fixed-interval segmentation.
    """
    if not story_headlines or len(story_headlines) < 2:
        return []

    # Walk lines once, building paragraphs with word/char start offsets
    # (mirrors parse_chapters' offset accounting: splitlines(keepends)).
    paras: list[tuple[int, int, set]] = []  # (start_word, start_char, tokens)
    word_idx = 0
    char_idx = 0
    cur_start: Optional[tuple[int, int]] = None
    cur_text: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            if cur_start is None:
                cur_start = (word_idx, char_idx)
            cur_text.append(stripped)
        elif cur_start is not None:
            paras.append(
                (cur_start[0], cur_start[1], _tokenize_for_match(" ".join(cur_text)))
            )
            cur_start, cur_text = None, []
        word_idx += len(line.split())
        char_idx += len(line)
    if cur_start is not None:
        paras.append(
            (cur_start[0], cur_start[1], _tokenize_for_match(" ".join(cur_text)))
        )

    in_head = [p for p in paras if head_word_start < p[0] < head_word_end]
    if not in_head:
        return []

    # Best-matching paragraph per headline; a paragraph keeps only its
    # strongest headline so two stories can't anchor the same spot.
    anchors: dict[int, tuple[int, str]] = {}  # para index -> (score, headline)
    for idx, h in enumerate(story_headlines):
        if _is_hook_candidate(h, idx, max_chars):
            # Not a title: extract_story_headlines leads with the digest's
            # blockquote HOOK — a full lead sentence, wanted as image
            # context but never as a chapter. It out-scores real headlines
            # on raw token overlap (Omni View Ep160, 2026-08-30: "Leaders
            # from Russia, China, India and Iran meet in Central…" reached
            # listeners). Real headlines between max_chars and twice that
            # stay eligible and are shortened cleanly (see _clip_title).
            continue
        h_tokens = _tokenize_for_match(h)
        if not h_tokens:
            continue
        best_i = None
        best_score = 0
        for i, (_w, _c, p_tokens) in enumerate(in_head):
            overlap = len(p_tokens & h_tokens)
            if overlap > best_score and (
                overlap >= 2 or overlap >= max(1, len(h_tokens) // 2)
            ):
                best_i, best_score = i, overlap
        if best_i is not None:
            prev = anchors.get(best_i)
            if prev is None or best_score > prev[0]:
                anchors[best_i] = (best_score, h)

    result: list = []
    last_w = head_word_start
    for i in sorted(anchors):
        w, c, _tokens = in_head[i]
        if w - last_w < min_segment_words:
            continue  # too close to the previous boundary — merge forward
        result.append((w, c, _clip_title(anchors[i][1], max_chars)))
        last_w = w
    return result if len(result) >= 2 else []


def parse_chapters(
    script: str,
    section_markers: list,
    *,
    show_name: str = "",
    min_chapters: int = 4,
    auto_segment_target_seconds: float = 90.0,
    estimated_words_per_minute: float = 165.0,
    story_headlines: Optional[List[str]] = None,
    known_sections_only: bool = False,
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
    #
    # July 16 2026: the end window is additionally floored at the last
    # 250 words. The code-appended tail AFTER the spoken sign-off
    # (network cross-promo + site CTA + AI disclosure) is a FIXED
    # ~120-180 words, so on short scripts it eats more than 15% and
    # pushes the real closing line out of the percentage window — MAB
    # shipped 5 of 14 July episodes with NO Closing chapter because
    # "that's a wrap" landed at ~84% of words. On 1500+-word scripts
    # min() keeps the original 85% behavior.
    start_window_end = max(int(total_words * 0.10), 60)
    end_window_start = min(int(total_words * 0.85), max(total_words - 250, 0))

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

    # A `where: end` chapter (the Closing/Sign-Off) is FINAL: nothing may
    # start after it. The rotating network cross-promo outro (July 16 2026)
    # names sibling shows AFTER the closing, and un-anchored body markers
    # were stealing those mentions as spurious final chapters — Tesla Ep544
    # shipped a "First Principles" chapter at 642s (after Closing at 616s)
    # from the promo line "try First Principles Daily next", and MIT Ep104
    # an "Investor Education" chapter from the promo's "daily deep dive"
    # (July 18 2026 network review). Same theft class FF fixed June 24 by
    # dropping bare markers — this closes it engine-wide.
    # The terminal signal is the closing TITLE (network convention — same
    # set the snapshot checker accepts), NOT the `where: end` anchor: EI
    # deliberately anchors only its Tomorrow Teaser while its Closing
    # marker is position-free, and a teaser may legitimately precede the
    # closing. Cut at the LAST closing-titled match.
    _terminal = ("closing", "sign-off", "завершение", "прощание")
    closing_positions = [
        w for w, _c, t in matches if t.strip().lower() in _terminal
    ]
    if closing_positions:
        closing_at = max(closing_positions)
        stolen = [t for w, _c, t in matches if w > closing_at]
        if stolen:
            logger.warning(
                "Dropping %d chapter(s) starting after the closing "
                "(promo-tail marker theft): %s", len(stolen), stolen,
            )
            matches = [m for m in matches if m[0] <= closing_at]

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
    # count is below ``min_chapters`` OR the first chapter spans most
    # of the script (≥50% of words — Ep537 had 4 markers so cleared
    # min_chapters but Introduction still covered 9 of 13 minutes), we
    # splice extra chapters at paragraph boundaries roughly every
    # ``auto_segment_target_seconds`` of speech so listeners always get
    # useful navigation. May 8 2026: titles now derive from each
    # segment's first sentence (truncated to ~50 chars) instead of the
    # previous generic ``Segment N`` placeholder — Apple Podcasts and
    # Pocket Casts surface chapter titles in the player UI, and
    # "Segment 2" tells the listener nothing about whether to skip ahead.
    head_spans_most = bool(
        chapters
        and total_words > 0
        and (chapters[0].word_end - chapters[0].word_start)
        >= int(total_words * 0.50)
    )
    # Aug 27 2026 (spacex Ep077): shows whose prompts speak a full, fixed
    # section set opt out of auto-segmentation entirely — every inserted
    # chapter would carry a digest headline / first-sentence title outside
    # the known section set, which ships as listener-facing spam in the
    # chapter UI ("SpaceX is hiring for natural gas trading to support
    # energy…" between Introduction and Counterpoint). For those shows the
    # matched markers ARE the navigation.
    if known_sections_only and (len(chapters) < min_chapters or head_spans_most):
        logger.info(
            "known_sections_only: skipping auto-segmentation for %s "
            "(%d marker chapters stand as-is)",
            show_name or "show", len(chapters),
        )
    elif (len(chapters) < min_chapters or head_spans_most) and total_words > 0:
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

            # Preferred (July 21 2026): anchor boundaries where each digest
            # story begins, so titles and positions agree by construction.
            # Falls back to fixed ~90s intervals when the script doesn't
            # echo enough headline content to anchor confidently.
            anchored = _headline_anchored_insertions(
                lines, head.word_start, head_w_end, story_headlines or [],
            )
            _seg_mode = "headline_anchored" if anchored else "fixed_interval"

            # (word_idx, char_offset, pre-assigned title or "")
            insertions: list[tuple[int, int, str]] = list(anchored)
            if not insertions:
                # Legacy: accept paragraph breaks inside the head chapter
                # that are at least ``words_per_segment`` words apart.
                last_w = head.word_start
                for w, c in para_break_word_idx:
                    if w <= head.word_start or w >= head_w_end:
                        continue
                    if w - last_w >= words_per_segment:
                        insertions.append((w, c, ""))
                        last_w = w

            if insertions:
                _used_headlines: set[str] = set()
                rebuilt: list[Chapter] = [Chapter(
                    title=head.title,
                    word_start=head.word_start,
                    word_end=insertions[0][0],
                    char_start=head.char_start,
                    char_end=insertions[0][1],
                )]
                for n, (w, c, pre_title) in enumerate(insertions, start=2):
                    next_w = insertions[n - 1][0] if n - 1 < len(insertions) else head_w_end
                    next_c = insertions[n - 1][1] if n - 1 < len(insertions) else head_c_end
                    # Title preference: (1) the anchored headline, (2) a
                    # matching clean digest headline (avoids mid-sentence
                    # spoken fragments), (3) the segment's first sentence,
                    # (4) "Segment N" placeholder.
                    seg_text = script[c:next_c]
                    title = (
                        pre_title
                        or _best_headline_for_segment(
                            seg_text, story_headlines or [], _used_headlines)
                        or _first_sentence_as_title(seg_text)
                        or f"Segment {n}"
                    )
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
                    "(mode=%s, target %.0fs each, ~%d words)",
                    show_name or "show",
                    len(insertions) + 1,
                    _seg_mode,
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
