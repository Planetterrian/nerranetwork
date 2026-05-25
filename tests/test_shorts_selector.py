"""Tests for ``engine.shorts_selector`` and the ``smart`` mode in
``engine.youtube_shorts.resolve_shorts_start_offset``.

Heuristic scoring is pure-function — every signal has an
independent test below so a regression in one (e.g. dropping the
numeric pattern by mistake) lights up a single targeted failure.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from engine.shorts_selector import (
    ScoredWindow,
    pick_engaging_window,
    score_candidates,
    score_text,
)
from engine.youtube_shorts import resolve_shorts_start_offset


# ---------------------------------------------------------------------------
# score_text — individual signal tests
# ---------------------------------------------------------------------------


def test_empty_text_scores_zero():
    assert score_text("") == 0.0
    assert score_text(None) == 0.0  # type: ignore[arg-type]


def test_neutral_text_scores_zero():
    assert score_text("The company released its quarterly report.") == 0.0


def test_hook_phrase_adds_five():
    assert score_text("And here's the kicker — they doubled revenue.") == 5.0


def test_multiple_hook_phrases_stack():
    text = "Here's the kicker: imagine if they actually pulled it off."
    # "here's the kicker" + "imagine if"
    assert score_text(text) == 10.0


def test_question_hook_at_start_adds_three():
    assert score_text("Why does Tesla keep doing this?") == 3.0


def test_boring_opener_penalizes_eight():
    assert score_text("Welcome to today's episode.") == -16.0
    # "welcome to" and "today's episode" both match.


def test_superlative_adds_one():
    # "biggest" matches; one numeric (the 5000) adds +2.
    assert score_text("This was the biggest week in company history.") == 1.0


def test_numeric_dollar_adds_two():
    assert score_text("Revenue hit $15 billion this quarter.") == 4.0
    # $1 → numeric_pattern_1 (+2), "15 billion" → numeric_pattern_3 (+2)


def test_numeric_percent_adds_two():
    assert score_text("Sales fell 38% year-over-year.") == 2.0


def test_numeric_multiplier_adds_two():
    assert score_text("The model is 10x faster.") == 2.0


def test_four_digit_year_adds_two():
    assert score_text("The 2026 plan looks ambitious.") == 2.0


def test_score_text_combines_signals():
    """A hook + a number + a superlative should sum cleanly."""
    text = (
        "Here's the kicker: it was the biggest "
        "delivery quarter in the company's history at 500,000 units."
    )
    # "here's the kicker" = +5
    # "biggest" = +1
    # "history" doesn't match anything
    # "500,000" — no digit pattern matches comma-separated 6-digit;
    # \b\d{4}\b matches the leading "500,"? No — \d{4} only matches
    # 4-digit runs and "500" is 3 digits. Add nothing.
    assert score_text(text) == 6.0


# ---------------------------------------------------------------------------
# score_candidates — window construction
# ---------------------------------------------------------------------------


def _write_transcript(tmp: Path, segments: list) -> Path:
    p = tmp / "transcript.json"
    p.write_text(json.dumps({
        "language": "en",
        "language_probability": 1.0,
        "duration": segments[-1]["end"] if segments else 0.0,
        "segments": segments,
    }), encoding="utf-8")
    return p


def _seg(start: float, end: float, text: str) -> dict:
    return {"start": start, "end": end, "text": text, "words": []}


def test_empty_transcript_returns_empty(tmp_path):
    tp = _write_transcript(tmp_path, [])
    out = score_candidates(tp, audio_offset=4.5, audio_duration=300.0)
    assert out == []


def test_missing_transcript_returns_empty(tmp_path, caplog):
    out = score_candidates(
        tmp_path / "nope.json", audio_offset=4.5, audio_duration=300.0,
    )
    assert out == []


def test_candidates_sorted_descending(tmp_path):
    segs = [
        _seg(0.0, 5.0, "Welcome to today's episode of Tesla Shorts Time."),
        _seg(5.0, 12.0, "And the kicker is they hit $15 billion in revenue."),
        _seg(12.0, 20.0, "Some boilerplate filler text without signals."),
    ]
    tp = _write_transcript(tmp_path, segs)
    out = score_candidates(
        tp, audio_offset=4.5, audio_duration=300.0, window_duration=55.0,
    )
    # Highest-scoring window must come first.
    assert len(out) >= 2
    assert out[0].score >= out[1].score
    # The high-signal segment ("kicker" + "$15 billion") wins.
    assert "kicker" in out[0].opening_text.lower()


def test_window_too_late_in_episode_is_rejected(tmp_path):
    # Segment at 250s in a 300s episode — start + 55s = 305s > 300s.
    segs = [_seg(250.0, 260.0, "Here's the kicker!")]
    tp = _write_transcript(tmp_path, segs)
    out = score_candidates(
        tp, audio_offset=0.0, audio_duration=300.0, window_duration=55.0,
    )
    assert out == []


def test_window_during_music_intro_is_rejected(tmp_path):
    # Segment at whisper t=0 with audio_offset=4.5 means final-audio
    # start is 4.5. If min_start_final=10.0, this should be rejected.
    segs = [_seg(0.0, 8.0, "And the kicker is they hit $15 billion.")]
    tp = _write_transcript(tmp_path, segs)
    out = score_candidates(
        tp, audio_offset=4.5, audio_duration=300.0,
        window_duration=55.0, min_start_final=10.0,
    )
    assert out == []


def test_position_weighting_prefers_hook_at_start(tmp_path):
    """A window with the high-signal segment as the OPENING should
    outscore a window where the same signal is buried 30 s in."""
    high_signal = "And the kicker is they hit $15 billion in revenue."
    filler = "The quarterly report covers regular operating data."
    # Window A starts on high-signal.
    # Window B starts on filler, with high-signal 30 s later.
    segs = [
        _seg(0.0, 5.0, filler),
        _seg(5.0, 10.0, filler),
        _seg(10.0, 15.0, high_signal),
        _seg(15.0, 20.0, filler),
        _seg(20.0, 25.0, filler),
        _seg(25.0, 30.0, filler),
        _seg(30.0, 35.0, filler),
        _seg(35.0, 40.0, filler),
        _seg(40.0, 45.0, filler),
        _seg(45.0, 50.0, filler),
        _seg(50.0, 55.0, filler),
        _seg(55.0, 60.0, filler),
        _seg(60.0, 65.0, high_signal),  # appears late in window B
        _seg(65.0, 70.0, filler),
    ]
    tp = _write_transcript(tmp_path, segs)
    out = score_candidates(
        tp, audio_offset=0.0, audio_duration=200.0, window_duration=55.0,
    )
    # The window opening on the high-signal segment (start=10.0
    # whisper) should outscore the window where it lands 30 s in.
    by_start = {round(w.start_seconds, 1): w for w in out}
    assert 10.0 in by_start
    assert by_start[10.0].score > by_start.get(0.0, ScoredWindow(0, 0, -99, "")).score


# ---------------------------------------------------------------------------
# pick_engaging_window — threshold + fallback
# ---------------------------------------------------------------------------


def test_pick_returns_none_when_below_threshold(tmp_path):
    """A boring transcript with no signal segments must return None
    so the caller falls back to legacy voice-start."""
    segs = [
        _seg(0.0, 5.0, "The company released its report."),
        _seg(5.0, 12.0, "Operations continued as planned."),
    ]
    tp = _write_transcript(tmp_path, segs)
    out = pick_engaging_window(
        tp, audio_offset=0.0, audio_duration=300.0,
        min_score_threshold=5.0,
    )
    assert out is None


def test_pick_returns_best_when_above_threshold(tmp_path):
    segs = [
        _seg(0.0, 5.0, "The company released its report."),
        _seg(5.0, 12.0, "And here's the kicker: $15 billion in revenue."),
    ]
    tp = _write_transcript(tmp_path, segs)
    out = pick_engaging_window(
        tp, audio_offset=4.5, audio_duration=300.0,
        min_score_threshold=5.0,
    )
    assert out is not None
    # final-audio start = whisper 5.0 + offset 4.5 = 9.5
    assert out.start_seconds == pytest.approx(9.5)
    assert out.score >= 5.0


def test_pick_returns_none_on_missing_transcript(tmp_path):
    out = pick_engaging_window(
        tmp_path / "nope.json", audio_offset=0.0, audio_duration=300.0,
    )
    assert out is None


# ---------------------------------------------------------------------------
# resolve_shorts_start_offset — smart mode integration
# ---------------------------------------------------------------------------


def _config(*, audio_kw=None, yt_kw=None):
    audio = SimpleNamespace(**(audio_kw or {}))
    yt = SimpleNamespace(
        shorts_start_mode=(yt_kw or {}).pop("shorts_start_mode", "voice"),
        shorts_start_offset=(yt_kw or {}).pop("shorts_start_offset", None),
        short_duration_seconds=(yt_kw or {}).pop("short_duration_seconds", 55.0),
        **(yt_kw or {}),
    )
    return SimpleNamespace(audio=audio, youtube=yt)


def test_smart_mode_falls_back_when_no_transcript(tmp_path):
    cfg = _config(audio_kw={"voice_intro_delay": 4.5},
                  yt_kw={"shorts_start_mode": "smart"})
    # No transcript_path passed — must fall back to voice_intro_delay.
    assert resolve_shorts_start_offset(cfg, None, audio_duration=300.0) == 4.5


def test_smart_mode_falls_back_when_transcript_unreadable(tmp_path):
    cfg = _config(audio_kw={"voice_intro_delay": 4.5},
                  yt_kw={"shorts_start_mode": "smart"})
    # Path doesn't exist on disk — falls through to voice.
    nope = tmp_path / "nope.json"
    assert resolve_shorts_start_offset(
        cfg, None, audio_duration=300.0, transcript_path=nope,
    ) == 4.5


def test_smart_mode_picks_high_signal_segment(tmp_path):
    cfg = _config(audio_kw={"voice_intro_delay": 4.5},
                  yt_kw={"shorts_start_mode": "smart"})
    segs = [
        _seg(0.0, 5.0, "Welcome to today's episode of the show."),
        _seg(5.0, 12.0, "And the kicker is they hit $15 billion in revenue."),
        _seg(12.0, 20.0, "Some boilerplate filler text."),
    ]
    tp = _write_transcript(tmp_path, segs)
    offset = resolve_shorts_start_offset(
        cfg, None, audio_duration=300.0, transcript_path=tp,
    )
    # whisper 5.0 + voice_intro_delay 4.5 = 9.5
    assert offset == pytest.approx(9.5)


def test_smart_mode_falls_back_when_all_segments_boring(tmp_path):
    cfg = _config(audio_kw={"voice_intro_delay": 4.5},
                  yt_kw={"shorts_start_mode": "smart"})
    segs = [
        _seg(0.0, 5.0, "The company released a quarterly report."),
        _seg(5.0, 12.0, "Operations continued as expected."),
    ]
    tp = _write_transcript(tmp_path, segs)
    offset = resolve_shorts_start_offset(
        cfg, None, audio_duration=300.0, transcript_path=tp,
    )
    # No segment scored above threshold → falls back to voice.
    assert offset == 4.5


def test_voice_mode_unchanged_by_smart_addition(tmp_path):
    """Regression guard: smart-mode wiring must not alter ``voice``
    or ``first_chapter`` modes."""
    cfg = _config(audio_kw={"voice_intro_delay": 10.0},
                  yt_kw={"shorts_start_mode": "voice"})
    segs = [_seg(0.0, 5.0, "Here's the kicker $15 billion revenue.")]
    tp = _write_transcript(tmp_path, segs)
    # Even with a transcript that would pick a different smart offset,
    # voice mode must ignore it.
    assert resolve_shorts_start_offset(
        cfg, None, audio_duration=300.0, transcript_path=tp,
    ) == 10.0


def test_explicit_offset_overrides_smart(tmp_path):
    """``shorts_start_offset`` is a hard operator override and must
    win over every mode including ``smart``."""
    cfg = _config(audio_kw={"voice_intro_delay": 4.5},
                  yt_kw={"shorts_start_mode": "smart",
                         "shorts_start_offset": 42.0})
    segs = [_seg(0.0, 5.0, "Here's the kicker $15 billion.")]
    tp = _write_transcript(tmp_path, segs)
    assert resolve_shorts_start_offset(
        cfg, None, audio_duration=300.0, transcript_path=tp,
    ) == 42.0
