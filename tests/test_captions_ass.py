"""Tests for ``engine.captions.transcript_to_ass_window``.

Covers the per-word ASS generator that powers TikTok-style "current
word" highlighting on YouTube Shorts. Each Whisper segment carries a
``words[]`` array; we emit one Dialogue line per word showing the
chunk text with the active word colour-flipped to cyan.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from engine.captions import (
    _chunk_words,
    _format_ass_timestamp,
    transcript_to_ass_window,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_transcript(
    tmp: Path, segments: list, language: str = "en",
) -> Path:
    """Write a faster-whisper-shaped JSON transcript and return the path."""
    p = tmp / "transcript.json"
    p.write_text(json.dumps({
        "language": language,
        "language_probability": 1.0,
        "duration": segments[-1]["end"] if segments else 0.0,
        "segments": segments,
    }), encoding="utf-8")
    return p


def _seg(start: float, end: float, words: list) -> dict:
    """Build a segment dict from a list of (word, ws, we) tuples."""
    return {
        "start": start,
        "end": end,
        "text": " ".join(w[0] for w in words),
        "words": [
            {"word": w, "start": ws, "end": we, "probability": 0.95}
            for (w, ws, we) in words
        ],
    }


def _parse_dialogue_lines(ass_text: str) -> list:
    """Return [(start, end, text), ...] for every Dialogue line in the file."""
    out = []
    for line in ass_text.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        # Dialogue: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
        parts = line[len("Dialogue:"):].split(",", 9)
        if len(parts) != 10:
            continue
        out.append((parts[1].strip(), parts[2].strip(), parts[9]))
    return out


# ---------------------------------------------------------------------------
# Timestamp formatting
# ---------------------------------------------------------------------------


def test_ass_timestamp_zero():
    assert _format_ass_timestamp(0.0) == "0:00:00.00"


def test_ass_timestamp_subsecond():
    assert _format_ass_timestamp(0.34) == "0:00:00.34"


def test_ass_timestamp_minutes_hours():
    # 1h 2m 3.04s
    assert _format_ass_timestamp(3723.04) == "1:02:03.04"


def test_ass_timestamp_rounds_centiseconds():
    assert _format_ass_timestamp(0.005) == "0:00:00.00" or \
           _format_ass_timestamp(0.005) == "0:00:00.01"  # both valid roundings


def test_ass_timestamp_clamps_negative():
    assert _format_ass_timestamp(-1.5) == "0:00:00.00"


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def test_chunk_words_keeps_short_segment_in_one_chunk():
    words = [
        {"word": "hi", "start": 0.0, "end": 0.2},
        {"word": "world", "start": 0.2, "end": 0.5},
    ]
    chunks = _chunk_words(words, max_chars=24, max_words_per_chunk=8)
    assert len(chunks) == 1
    assert [w["word"] for w in chunks[0]] == ["hi", "world"]


def test_chunk_words_splits_on_char_budget():
    # 6 four-letter words = 6*4 + 5 spaces = 29 chars at one boundary
    # Under max_chars=24 should split.
    words = [
        {"word": f"word{i}", "start": float(i), "end": float(i) + 0.5}
        for i in range(6)
    ]
    chunks = _chunk_words(words, max_chars=24, max_words_per_chunk=8)
    # 6×"wordN" (5 chars) + spaces > 24 → expect at least 2 chunks.
    assert len(chunks) >= 2
    # Every chunk must respect the char budget.
    for c in chunks:
        joined = " ".join(w["word"] for w in c)
        assert len(joined) <= 24


def test_chunk_words_splits_on_word_count_ceiling():
    # 10 single-character words = 19 chars total — under 24 — but the
    # word-count cap kicks in at 8.
    words = [
        {"word": "a", "start": float(i), "end": float(i) + 0.1}
        for i in range(10)
    ]
    chunks = _chunk_words(words, max_chars=24, max_words_per_chunk=8)
    assert len(chunks) == 2
    assert len(chunks[0]) == 8
    assert len(chunks[1]) == 2


def test_chunk_words_drops_blank_tokens():
    words = [
        {"word": "hello", "start": 0.0, "end": 0.2},
        {"word": " ", "start": 0.2, "end": 0.21},  # Whisper artefact
        {"word": "world", "start": 0.21, "end": 0.5},
    ]
    chunks = _chunk_words(words, max_chars=24, max_words_per_chunk=8)
    flat = [w["word"].strip() for c in chunks for w in c]
    assert "" not in flat


# ---------------------------------------------------------------------------
# transcript_to_ass_window — end-to-end
# ---------------------------------------------------------------------------


def test_emits_header_and_one_dialogue_per_word(tmp_path):
    seg = _seg(
        0.0, 1.5, [
            ("Hello", 0.0, 0.3),
            ("world", 0.3, 0.7),
            ("from", 0.7, 0.9),
            ("Tesla", 0.9, 1.5),
        ],
    )
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "short.ass"
    transcript_to_ass_window(
        tp, out,
        window_start_seconds=0.0, window_duration_seconds=10.0,
    )
    body = out.read_text(encoding="utf-8")
    assert body.startswith("[Script Info]")
    assert "[V4+ Styles]" in body
    assert "[Events]" in body
    dialogues = _parse_dialogue_lines(body)
    assert len(dialogues) == 4  # one per word


# The full highlight override tag: colour flip + the July 31 2026 (B2)
# active-word "pop" — a libass animated transform scaling the word to
# 112% over its first 80 ms. Shared by the Shorts window builder and the
# long-form full builder (they render through the same chunk code).
HIGHLIGHT_TAG = "{\\1c&H00FFD400&\\t(0,80,\\fscx112\\fscy112)}"
HIGHLIGHT_RE = re.compile(
    r"\{\\1c&H00FFD400&\\t\(0,80,\\fscx112\\fscy112\)\}([^{]+)\{\\r\}"
)


def test_active_word_is_color_flipped(tmp_path):
    """Each Dialogue line should highlight exactly one word (colour
    flip + B2 pop transform); the rest of the chunk text appears at
    the style default."""
    seg = _seg(
        0.0, 1.2, [
            ("alpha", 0.0, 0.3),
            ("beta", 0.3, 0.6),
            ("gamma", 0.6, 1.2),
        ],
    )
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "short.ass"
    transcript_to_ass_window(
        tp, out,
        window_start_seconds=0.0, window_duration_seconds=10.0,
    )
    dialogues = _parse_dialogue_lines(out.read_text(encoding="utf-8"))
    # Highlight override (colour + pop) appears exactly once per line.
    for start, end, text in dialogues:
        assert text.count(HIGHLIGHT_TAG) == 1, (
            f"line should have one highlight: {text!r}"
        )
        assert text.count("{\\r}") == 1
        # The pop is an animated transform, never a bare colour flip.
        assert "\\t(0,80,\\fscx112\\fscy112)" in text
    # The highlighted words progress: alpha, beta, gamma.
    highlighted = [HIGHLIGHT_RE.search(t).group(1).strip()
                   for _, _, t in dialogues]
    assert highlighted == ["alpha", "beta", "gamma"]


def test_timestamps_rebase_onto_shorts_window(tmp_path):
    """Words at audio t=10s in a window starting at 5s land at t=5s in
    the Shorts ASS."""
    seg = _seg(10.0, 11.0, [("only", 10.0, 11.0)])
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "short.ass"
    transcript_to_ass_window(
        tp, out,
        window_start_seconds=5.0, window_duration_seconds=10.0,
    )
    dialogues = _parse_dialogue_lines(out.read_text(encoding="utf-8"))
    assert len(dialogues) == 1
    start, end, _ = dialogues[0]
    assert start == "0:00:05.00"
    assert end == "0:00:06.00"


def test_audio_offset_applied_before_window_check(tmp_path):
    """``audio_offset_seconds`` shifts whisper timestamps onto the
    final-audio timeline before the window clip — same contract as
    the SRT window function."""
    # Whisper time t=0 ↔ final audio t=4.5 (music intro offset).
    # Shorts window starts at final-audio t=5.0.
    seg = _seg(1.0, 2.0, [("hello", 1.0, 2.0)])
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "short.ass"
    transcript_to_ass_window(
        tp, out,
        window_start_seconds=5.0,
        window_duration_seconds=5.0,
        audio_offset_seconds=4.5,
    )
    dialogues = _parse_dialogue_lines(out.read_text(encoding="utf-8"))
    assert len(dialogues) == 1
    # whisper t=1.0 + offset 4.5 = 5.5 (final); window starts at 5.0
    # → rebased to 0.5
    start, end, _ = dialogues[0]
    assert start == "0:00:00.50"
    assert end == "0:00:01.50"


def test_empty_when_no_overlap(tmp_path):
    """When no words fall inside the window, only the header is
    written (no Dialogue lines) — the caller treats this as 'no
    captions' and falls back to SRT."""
    seg = _seg(20.0, 22.0, [("late", 20.0, 22.0)])
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "short.ass"
    transcript_to_ass_window(
        tp, out,
        window_start_seconds=0.0, window_duration_seconds=5.0,
    )
    body = out.read_text(encoding="utf-8")
    assert "[Script Info]" in body
    assert "Dialogue:" not in body


def test_segment_without_words_is_skipped(tmp_path):
    """Older transcripts (or any segment with no word_timestamps)
    must not crash — the function silently skips them. The fallback
    to SRT in run_show.py then handles the visual outcome."""
    seg = {
        "start": 0.0, "end": 2.0, "text": "no words here",
        # explicitly no "words" key
    }
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "short.ass"
    transcript_to_ass_window(
        tp, out,
        window_start_seconds=0.0, window_duration_seconds=5.0,
    )
    dialogues = _parse_dialogue_lines(out.read_text(encoding="utf-8"))
    assert dialogues == []


def test_chunks_render_independently(tmp_path):
    """A long segment with many words should produce multiple chunks;
    each chunk should run its own per-word highlight cycle without
    bleeding into the next chunk's text."""
    seg = _seg(
        0.0, 5.0, [
            ("one", 0.0, 0.3), ("two", 0.3, 0.6), ("three", 0.6, 0.9),
            ("four", 0.9, 1.2), ("five", 1.2, 1.5), ("six", 1.5, 1.8),
            ("seven", 1.8, 2.1), ("eight", 2.1, 2.4),
            ("nine", 2.4, 2.7), ("ten", 2.7, 3.0),
            ("eleven", 3.0, 3.5), ("twelve", 3.5, 4.0),
        ],
    )
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "short.ass"
    transcript_to_ass_window(
        tp, out,
        window_start_seconds=0.0, window_duration_seconds=10.0,
    )
    dialogues = _parse_dialogue_lines(out.read_text(encoding="utf-8"))
    assert len(dialogues) == 12
    # Each dialogue's plain text (after highlight tags) must contain
    # ONLY the words from its own chunk, never all 12 words.
    for _, _, text in dialogues:
        # Strip override tags to count words.
        plain = re.sub(r"\{[^}]*\}", "", text).strip()
        word_count = len(plain.split())
        assert word_count <= 8, (
            f"chunk leaked too many words ({word_count}): {plain!r}"
        )


def test_invalid_args_raise(tmp_path):
    seg = _seg(0.0, 1.0, [("hi", 0.0, 1.0)])
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "short.ass"
    with pytest.raises(ValueError):
        transcript_to_ass_window(
            tp, out, window_start_seconds=-1.0, window_duration_seconds=5.0,
        )
    with pytest.raises(ValueError):
        transcript_to_ass_window(
            tp, out, window_start_seconds=0.0, window_duration_seconds=0.0,
        )
    with pytest.raises(ValueError):
        transcript_to_ass_window(
            tp, out, window_start_seconds=0.0, window_duration_seconds=5.0,
            audio_offset_seconds=-0.5,
        )


def test_missing_transcript_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        transcript_to_ass_window(
            tmp_path / "nope.json", tmp_path / "out.ass",
            window_start_seconds=0.0, window_duration_seconds=5.0,
        )


def test_ass_escape_strips_braces(tmp_path):
    """Curly braces in a Whisper artefact must be neutered so they
    don't accidentally start an inline tag block."""
    seg = _seg(0.0, 1.0, [("{evil}", 0.0, 0.5), ("hello", 0.5, 1.0)])
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "short.ass"
    transcript_to_ass_window(
        tp, out,
        window_start_seconds=0.0, window_duration_seconds=5.0,
    )
    body = out.read_text(encoding="utf-8")
    # ASS tag delimiter (`{`) must only appear inside our highlight
    # tags, never as part of a token. Strip our known good tags (colour
    # flip + B2 pop transform) and check no `{` remains in any Dialogue
    # text.
    for _, _, text in _parse_dialogue_lines(body):
        without_tags = re.sub(
            r"\{\\1c&H[0-9A-F]+&(?:\\t\([^)]*\))?\}", "", text)
        without_tags = without_tags.replace(r"{\r}", "")
        assert "{" not in without_tags, (
            f"raw brace leaked into dialogue: {text!r}"
        )


# ---------------------------------------------------------------------------
# transcript_to_ass_full — long-form per-word captions (July 31 2026, B1)
# ---------------------------------------------------------------------------


from engine.captions import transcript_to_ass_full  # noqa: E402


def test_full_header_declares_long_form_playres_and_style(tmp_path):
    """The long-form ASS is self-styled in REAL pixels: PlayRes
    1920x1080 and the long-form burn-in look (~98 px white text,
    BorderStyle=1 outline 3 + shadow 1, bottom-centre MarginV=50) —
    the equivalent of _SUBTITLES_FORCE_STYLE's FontSize=26 in libass's
    288-unit SRT space. The render path lets this file self-style."""
    seg = _seg(0.0, 1.0, [("Hello", 0.0, 0.5), ("world", 0.5, 1.0)])
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "long.ass"
    transcript_to_ass_full(tp, out)
    body = out.read_text(encoding="utf-8")
    assert "PlayResX: 1920" in body
    assert "PlayResY: 1080" in body
    style = [ln for ln in body.splitlines()
             if ln.startswith("Style: Default")][0]
    fields = style.split(",")
    assert fields[2] == "98"              # Fontsize (real px)
    assert fields[15] == "1"              # BorderStyle=1 (outline, no card)
    assert fields[16] == "3"              # Outline
    assert fields[17] == "1"              # Shadow
    assert fields[18] == "2"              # Alignment=2 bottom-centre
    assert fields[21] == "50"             # MarginV
    assert "&H80000000" not in style      # no Shorts caption card


def test_full_emits_one_dialogue_per_word_on_absolute_timeline(tmp_path):
    """No window, no rebase: word times land verbatim (plus offset)."""
    seg = _seg(10.0, 11.0, [("only", 10.0, 11.0)])
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "long.ass"
    transcript_to_ass_full(tp, out)
    dialogues = _parse_dialogue_lines(out.read_text(encoding="utf-8"))
    assert len(dialogues) == 1
    start, end, text = dialogues[0]
    assert start == "0:00:10.00"
    assert end == "0:00:11.00"
    # Shared highlight machinery: colour flip + B2 pop.
    assert HIGHLIGHT_TAG in text


def test_full_applies_music_intro_offset(tmp_path):
    seg = _seg(1.0, 2.0, [("hello", 1.0, 2.0)])
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "long.ass"
    transcript_to_ass_full(tp, out, audio_offset_seconds=4.5)
    dialogues = _parse_dialogue_lines(out.read_text(encoding="utf-8"))
    start, end, _ = dialogues[0]
    assert start == "0:00:05.50"
    assert end == "0:00:06.50"


def test_full_uses_wider_long_form_chunk_budget(tmp_path):
    """~42 chars / <=10 words per chunk (the 1920-wide frame fits more
    than the Shorts 24/8 card) — and never more than 10 words."""
    words = [(f"word{i}", i * 0.4, i * 0.4 + 0.35) for i in range(24)]
    seg = _seg(0.0, 10.0, words)
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "long.ass"
    transcript_to_ass_full(tp, out)
    dialogues = _parse_dialogue_lines(out.read_text(encoding="utf-8"))
    assert len(dialogues) == 24  # one per word
    for _, _, text in dialogues:
        plain = re.sub(r"\{[^}]*\}", "", text).strip()
        assert len(plain.split()) <= 10
        assert len(plain) <= 42 + 8  # chunk budget (+ small slack)


def test_full_without_word_data_writes_header_only(tmp_path):
    """Older transcripts: no words[] → no Dialogue lines; run_show
    treats that as 'fall back to the segment-level SRT'."""
    seg = {"start": 0.0, "end": 2.0, "text": "no words here"}
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "long.ass"
    transcript_to_ass_full(tp, out)
    body = out.read_text(encoding="utf-8")
    assert "[Script Info]" in body
    assert "Dialogue:" not in body


def test_full_invalid_offset_raises(tmp_path):
    seg = _seg(0.0, 1.0, [("hi", 0.0, 1.0)])
    tp = _write_transcript(tmp_path, [seg])
    with pytest.raises(ValueError):
        transcript_to_ass_full(tp, tmp_path / "long.ass",
                               audio_offset_seconds=-1.0)


def test_full_missing_transcript_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        transcript_to_ass_full(tmp_path / "nope.json", tmp_path / "out.ass")


# ---------------------------------------------------------------------------
# Aug 2026 — caption card holds through inter-word gaps (no flicker)
# ---------------------------------------------------------------------------

def test_word_cue_holds_until_next_word_starts(tmp_path):
    """A pause between words used to leave the caption card OFF for the
    gap (Whisper leaves 150-600 ms at breaths), so the card vanished and
    re-popped 10-20 times per Short. A cue now extends to the next
    word's start when the gap is short."""
    seg = _seg(0.0, 3.0, [("hello", 0.0, 0.5), ("world", 0.9, 1.4)])
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "short.ass"
    transcript_to_ass_window(
        tp, out, window_start_seconds=0.0, window_duration_seconds=10.0,
    )
    dialogues = _parse_dialogue_lines(out.read_text(encoding="utf-8"))
    assert len(dialogues) == 2
    # First cue holds through the 0.4 s gap to the successor's start.
    assert dialogues[0][1] == "0:00:00.90"
    assert dialogues[1][0] == "0:00:00.90"


def test_word_cue_hold_is_bounded_over_long_silences(tmp_path):
    """A long silence must still clear the card — the hold caps at
    0.6 s rather than bridging an arbitrary gap."""
    seg = _seg(0.0, 6.0, [("before", 0.0, 0.5), ("after", 4.0, 4.5)])
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "short.ass"
    transcript_to_ass_window(
        tp, out, window_start_seconds=0.0, window_duration_seconds=10.0,
    )
    dialogues = _parse_dialogue_lines(out.read_text(encoding="utf-8"))
    assert dialogues[0][1] == "0:00:01.10"  # 0.5 + 0.6 cap


def test_min_duration_floor_never_overlaps_the_next_word(tmp_path):
    """The min_word_duration floor on a sub-80 ms word used to push its
    end past the next word's start — two simultaneous Alignment=2
    events that libass stacks as a one-frame two-line jump."""
    seg = _seg(0.0, 2.0, [("a", 0.00, 0.03), ("tiny", 0.05, 0.6)])
    tp = _write_transcript(tmp_path, [seg])
    out = tmp_path / "short.ass"
    transcript_to_ass_window(
        tp, out, window_start_seconds=0.0, window_duration_seconds=10.0,
    )
    dialogues = _parse_dialogue_lines(out.read_text(encoding="utf-8"))
    assert len(dialogues) == 2
    # First cue may extend only TO the successor's start, never past.
    assert dialogues[0][1] <= dialogues[1][0]
