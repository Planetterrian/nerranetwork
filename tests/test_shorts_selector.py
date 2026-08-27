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


def test_trim_opening_text_cuts_on_word_boundary():
    """July 2026: Shorts titles must not truncate mid-word."""
    from engine.shorts_selector import _trim_opening_text
    long = (
        "Tesla is hiring engineers to build a wireless Battery "
        "Management System for Cybercab that removes heavy wiring"
    )
    out = _trim_opening_text(long, max_chars=80)
    assert len(out) <= 80
    assert out.endswith("…")
    assert " " not in out[-2:]  # ellipsis, not a mid-word cut
    # Last visible char before ellipsis is not mid-word garbage.
    assert not out.rstrip("…").endswith("wirele")
    assert "wireless" in out or out.rstrip("…").endswith("a")


def test_trim_opening_text_leaves_short_alone():
    from engine.shorts_selector import _trim_opening_text
    assert _trim_opening_text("Short hook", max_chars=80) == "Short hook"


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


# ---------------------------------------------------------------------------
# pick_top_n_engaging_windows — multi-Shorts selection
# ---------------------------------------------------------------------------


def test_pick_top_n_returns_empty_when_n_le_0(tmp_path):
    """Defensive — n=0 (or negative) is a caller bug; return empty
    rather than picking anything."""
    from engine.shorts_selector import pick_top_n_engaging_windows
    segs = [_seg(0.0, 5.0, "And the kicker is they hit $15 billion in revenue.")]
    tp = _write_transcript(tmp_path, segs)
    out = pick_top_n_engaging_windows(
        tp, n=0, audio_offset=0.0, audio_duration=300.0,
    )
    assert out == []


def test_pick_top_n_returns_one_for_n_equals_1(tmp_path):
    """n=1 must behave identically to pick_engaging_window — caller
    that's already on the single-Short path can swap if desired."""
    from engine.shorts_selector import (
        pick_engaging_window,
        pick_top_n_engaging_windows,
    )
    segs = [
        _seg(0.0, 5.0, "Welcome to today's episode."),
        _seg(5.0, 12.0, "And the kicker is they hit $15 billion in revenue."),
    ]
    tp = _write_transcript(tmp_path, segs)
    single = pick_engaging_window(
        tp, audio_offset=0.0, audio_duration=300.0,
    )
    multi = pick_top_n_engaging_windows(
        tp, n=1, audio_offset=0.0, audio_duration=300.0,
    )
    assert single is not None
    assert len(multi) == 1
    assert multi[0].start_seconds == single.start_seconds


def test_pick_top_n_picks_non_overlapping_windows(tmp_path):
    """N=2 must produce two windows whose [start, end] don't
    overlap with each other (or share less than min_gap_seconds
    between end and next start)."""
    from engine.shorts_selector import pick_top_n_engaging_windows
    # Two clearly distinct engaging beats far apart in the episode.
    high_signal_a = "Here's the kicker: $15 billion this quarter."
    high_signal_b = "And the wild part is they hit 38% revenue."
    filler = "The quarterly report covers regular data."
    segs = [
        _seg(0.0, 5.0, filler),
        _seg(5.0, 12.0, high_signal_a),       # window candidate A
        _seg(12.0, 60.0, filler),
        _seg(70.0, 80.0, high_signal_b),      # window candidate B (way later)
        _seg(80.0, 100.0, filler),
    ]
    tp = _write_transcript(tmp_path, segs)
    out = pick_top_n_engaging_windows(
        tp, n=2, audio_offset=0.0, audio_duration=300.0,
        window_duration=55.0, min_gap_seconds=10.0,
    )
    assert len(out) == 2
    # Sorted chronologically.
    assert out[0].start_seconds < out[1].start_seconds
    # Non-overlapping with the configured gap.
    assert out[0].end_seconds + 10.0 <= out[1].start_seconds


def test_pick_top_n_rejects_overlapping_candidates(tmp_path):
    """When two engaging beats are inside the same 55s window, only
    one of them survives — the other would overlap."""
    from engine.shorts_selector import pick_top_n_engaging_windows
    # Both beats fall inside [0, 55] so picking both as starts would
    # produce overlapping windows.
    segs = [
        _seg(0.0, 5.0, "Welcome to today's episode."),
        _seg(5.0, 12.0, "Here's the kicker: $15 billion this quarter."),
        _seg(12.0, 20.0, "And the wild part is they hit 38% growth."),
        _seg(20.0, 80.0, "More content."),
    ]
    tp = _write_transcript(tmp_path, segs)
    out = pick_top_n_engaging_windows(
        tp, n=2, audio_offset=0.0, audio_duration=200.0,
        window_duration=55.0, min_gap_seconds=10.0,
    )
    # Only one of the two close-by signals survives — the other
    # falls inside the picked window.
    assert len(out) == 1


def test_pick_top_n_returns_fewer_than_n_when_supply_short(tmp_path):
    """If the episode only has 1 strong beat, n=3 returns 1 window
    rather than padding with garbage."""
    from engine.shorts_selector import pick_top_n_engaging_windows
    segs = [
        _seg(0.0, 5.0, "Welcome to today's episode."),
        _seg(5.0, 12.0, "Here's the kicker: $15 billion this quarter."),
        _seg(12.0, 200.0, "Some boring filler content."),
    ]
    tp = _write_transcript(tmp_path, segs)
    out = pick_top_n_engaging_windows(
        tp, n=3, audio_offset=0.0, audio_duration=300.0,
    )
    assert len(out) == 1


def test_pick_top_n_returns_empty_when_no_threshold_breakers(tmp_path):
    """All-boilerplate episode produces no Shorts plan; caller falls
    back to the legacy voice-start single Short."""
    from engine.shorts_selector import pick_top_n_engaging_windows
    segs = [
        _seg(0.0, 5.0, "Welcome to today's episode."),
        _seg(5.0, 12.0, "The company released a report."),
        _seg(12.0, 20.0, "Operations continue as expected."),
    ]
    tp = _write_transcript(tmp_path, segs)
    out = pick_top_n_engaging_windows(
        tp, n=3, audio_offset=0.0, audio_duration=300.0,
        min_score_threshold=5.0,
    )
    assert out == []


def test_pick_top_n_sorted_chronologically(tmp_path):
    """The returned list is sorted by start_seconds ascending so the
    Shorts publish flow uploads them in episode order (Short 1 from
    earlier in the episode, Short 2 later) — small but real signal
    for viewers who watch multiple Shorts in a row."""
    from engine.shorts_selector import pick_top_n_engaging_windows
    # Two engaging beats; the later one has a HIGHER raw score so
    # we'd take it first if sort were by score. After re-sort, it
    # comes second.
    segs = [
        _seg(0.0, 5.0, "Filler before any signal."),
        _seg(5.0, 12.0, "The kicker is they hit $15 billion."),  # mid score
        _seg(12.0, 60.0, "More filler."),
        _seg(70.0, 80.0, "Here's the kicker: incredibly the wild part is 80%."),  # higher score
        _seg(80.0, 200.0, "More filler."),
    ]
    tp = _write_transcript(tmp_path, segs)
    out = pick_top_n_engaging_windows(
        tp, n=2, audio_offset=0.0, audio_duration=300.0,
        window_duration=55.0, min_gap_seconds=10.0,
    )
    assert len(out) == 2
    # Returned chronologically even though the latter has a higher
    # raw score.
    assert out[0].start_seconds < out[1].start_seconds


def test_pick_top_n_respects_min_start_final(tmp_path):
    """An engaging beat that lands during the music intro (final-
    audio time < min_start_final) must be rejected even if its
    Whisper timestamp is t=0."""
    from engine.shorts_selector import pick_top_n_engaging_windows
    segs = [
        _seg(0.0, 5.0, "Here's the kicker: $15 billion this quarter."),
    ]
    tp = _write_transcript(tmp_path, segs)
    # Whisper t=0..5; final audio adds 4.5s offset; window starts at
    # final t=4.5. With min_start_final=10.0, the window is rejected.
    out = pick_top_n_engaging_windows(
        tp, n=3, audio_offset=4.5, audio_duration=300.0,
        min_start_final=10.0, window_duration=55.0,
    )
    assert out == []


class TestFillToRequested:
    """July 18 2026: fill-to-requested — the multi-Shorts selector ships
    the best available sub-threshold windows instead of fewer Shorts."""

    @staticmethod
    def _write_transcript(tmp_path, segments):
        import json
        p = tmp_path / "tr.json"
        p.write_text(json.dumps({"segments": segments}), encoding="utf-8")
        return p

    def _segments(self):
        # One strong beat early, mediocre prose later — mimics the FF
        # failure shape (only one window beats a high threshold).
        segs = [{
            "start": 0.0, "end": 8.0,
            "text": ("Here's the kicker: profits jumped fifty percent to "
                     "ten million dollars in one day."),
        }]
        t = 8.0
        filler = [
            "The mission continued with routine operations throughout.",
            "Engineers reviewed the data and confirmed the results.",
            "The team documented findings for the next review cycle.",
            "Observations continued as the spacecraft passed overhead.",
            "Analysts noted steady progress on the program milestones.",
        ] * 7
        for txt in filler:
            segs.append({"start": t, "end": t + 8.0, "text": txt})
            t += 8.0
        return segs

    def test_fill_returns_requested_count(self, tmp_path):
        from engine.shorts_selector import pick_top_n_engaging_windows
        tr = self._write_transcript(tmp_path, self._segments())
        wins = pick_top_n_engaging_windows(
            tr, n=2, audio_offset=0.0, audio_duration=300.0,
            window_duration=40.0, min_score_threshold=5.0, fill_to_n=True,
        )
        assert len(wins) == 2
        modes = sorted(w.qualified for w in wins)
        assert modes == [False, True], (
            "expected one qualified + one filled window")

    def test_no_fill_preserves_legacy_behavior(self, tmp_path):
        from engine.shorts_selector import pick_top_n_engaging_windows
        tr = self._write_transcript(tmp_path, self._segments())
        wins = pick_top_n_engaging_windows(
            tr, n=2, audio_offset=0.0, audio_duration=300.0,
            window_duration=40.0, min_score_threshold=5.0, fill_to_n=False,
        )
        assert len(wins) == 1  # only the strong beat qualifies
        assert all(w.qualified for w in wins)

    def test_negative_scores_never_fill(self, tmp_path):
        from engine.shorts_selector import pick_top_n_engaging_windows
        segs = [
            {"start": 0.0, "end": 8.0,
             "text": "Here's the kicker: profits doubled to ten million."},
            # A boring-opener window (negative score) far from the first.
            {"start": 120.0, "end": 128.0,
             "text": "Welcome to the show, today on the show we talk."},
        ]
        tr = self._write_transcript(tmp_path, segs)
        wins = pick_top_n_engaging_windows(
            tr, n=2, audio_offset=0.0, audio_duration=200.0,
            window_duration=40.0, min_score_threshold=5.0, fill_to_n=True,
        )
        assert all(w.score >= 0 for w in wins)

    def test_scored_window_defaults_qualified(self):
        from engine.shorts_selector import ScoredWindow
        w = ScoredWindow(0.0, 40.0, 5.0)
        assert w.qualified is True

    def test_config_flag_exists(self):
        from engine.config import YouTubeConfig
        assert YouTubeConfig().shorts_fill_to_requested is True

    def test_ff_threshold_parity(self):
        import yaml as _yaml
        from pathlib import Path
        cfg = _yaml.safe_load(
            (Path(__file__).resolve().parent.parent
             / "shows/fascinating_frontiers.yaml").read_text(encoding="utf-8"))
        assert cfg["youtube"]["shorts_min_score_threshold"] == 3.5


class TestShortsClipLength:
    """Shorts run 35s network-wide (July 30 2026).

    Measured over 348 Shorts with >=5 views in the 90-day analytics
    window: the median Short holds a viewer 21 seconds (EN 23, RU 18;
    p75 29s, p90 40s). Absolute watch time barely moves with clip
    length, so length mostly decides what percentage those seconds
    represent — and completion is the dominant Shorts ranking signal.
    21s of 55s is 38%; of 35s it is 60%.

    Eight shows had been sitting on the 55s network default. The floor
    below is what keeps a new show from inheriting that again.
    """

    _MAX = 35.0

    @staticmethod
    def _shows():
        import pathlib
        import yaml as _yaml
        root = pathlib.Path(__file__).resolve().parent.parent
        for path in sorted((root / "shows").glob("*.yaml")):
            if path.stem.startswith("_"):
                continue
            raw = _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            yield path.stem, (raw.get("youtube") or {})

    def test_no_show_pins_a_longer_clip(self):
        for stem, yt in self._shows():
            if "short_duration_seconds" not in yt:
                continue
            assert yt["short_duration_seconds"] <= self._MAX, (
                f"{stem}.yaml pins {yt['short_duration_seconds']}s Shorts — "
                f"above the measured {self._MAX}s completion optimum"
            )

    def test_network_default_is_35(self):
        import pathlib
        import yaml as _yaml
        root = pathlib.Path(__file__).resolve().parent.parent
        raw = _yaml.safe_load(
            (root / "shows/_defaults.yaml").read_text(encoding="utf-8"))
        assert raw["youtube"]["short_duration_seconds"] == 35

    def test_dataclass_default_matches_yaml(self):
        """Callers that build a YouTubeConfig directly must not get 55.

        engine.ru_dub / engine.lang_dub / engine.youtube_shorts each
        resolve the length through a getattr fallback, so a stale
        dataclass default would ship long Shorts on the dub channels
        only — the hardest place to notice it.
        """
        from engine.config import YouTubeConfig
        assert YouTubeConfig().short_duration_seconds == 35.0

    def test_selector_window_default_matches(self):
        import inspect
        from engine.shorts_selector import (
            pick_engaging_window, pick_top_n_engaging_windows,
        )
        for fn in (pick_engaging_window, pick_top_n_engaging_windows):
            default = inspect.signature(fn).parameters["window_duration"].default
            assert default == 35.0, f"{fn.__name__} defaults to {default}s"


class TestHookFirstWindows:
    """July 31 2026 operator directive: Short #1 on every channel is the
    episode's opening hook sequence (since the cold-open pass, t~=0 IS
    the hook); smart windows fill the remaining slots, overlaps dropped.
    The hook window records window="hook_open" so the analytics loop can
    score the directive against smart windows."""

    def _w(self, start, end, score=6.0, text="w", qualified=True):
        from engine.shorts_selector import ScoredWindow
        return ScoredWindow(start_seconds=start, end_seconds=end,
                            score=score, opening_text=text,
                            qualified=qualified)

    def test_hook_window_is_always_first(self):
        from engine.shorts_selector import hook_first_windows
        smart = [self._w(120, 155), self._w(300, 335)]
        out = hook_first_windows(smart, n=3, hook_start=0.0,
                                 window_duration=35.0, hook_text="The hook")
        assert out[0].start_seconds == 0.0
        assert out[0].opening_text == "The hook"
        assert out[0].score == float("inf")
        assert [w.start_seconds for w in out[1:]] == [120, 300]

    def test_overlapping_smart_windows_are_dropped(self):
        from engine.shorts_selector import hook_first_windows
        smart = [self._w(20, 55), self._w(200, 235)]  # 20s overlaps hook
        out = hook_first_windows(smart, n=3, hook_start=0.0,
                                 window_duration=35.0)
        assert [w.start_seconds for w in out] == [0.0, 200]

    def test_count_is_respected(self):
        from engine.shorts_selector import hook_first_windows
        smart = [self._w(120, 155), self._w(300, 335), self._w(500, 535)]
        out = hook_first_windows(smart, n=2, hook_start=0.0,
                                 window_duration=35.0)
        assert len(out) == 2
        assert out[0].score == float("inf")

    def test_zero_count_returns_empty(self):
        from engine.shorts_selector import hook_first_windows
        assert hook_first_windows([], n=0, hook_start=0.0) == []

    def test_hook_first_is_on_network_wide_including_spacex(self):
        """Default true (the directive applies network-wide). spacex was
        pinned false only to protect the motion A/B from a window-
        position confound; the experiment ended 2026-08-01 (operator
        verdict: real footage over generated motion), so the pin lifted
        with it."""
        from engine.config import load_config
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        for slug in ("tesla", "spacex"):
            assert load_config(root / "shows" / f"{slug}.yaml").youtube \
                .shorts_first_is_hook is True, slug

    def test_run_show_and_both_dub_paths_are_wired(self):
        """All three publish paths must apply the directive — a channel
        that silently keeps smart-only Shorts would look like the
        directive failing when it was never wired."""
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        for f in ("run_show.py", "engine/ru_dub.py", "engine/lang_dub.py"):
            src = (root / f).read_text(encoding="utf-8")
            assert "hook_first_windows" in src, f
            assert "shorts_first_is_hook" in src, f
        # And the index records the window label for the learning loop.
        idx = (root / "engine" / "youtube_index.py").read_text(
            encoding="utf-8")
        assert 'row["window"] = window' in idx


class TestRequestedCountDefaultsToZero:
    """Aug 27 2026: YouTube-disabled shows (dp_pod, offshore_north) return
    an empty publish result, and the metrics recorder's old default wrote a
    phantom "1 Short requested / 0 uploaded" per episode — 13 fake misses a
    fortnight in the dashboard's multi-Shorts hit rate. No key = 0."""

    def test_pipeline_records_zero_when_publish_result_empty(self):
        src = open("engine/pipeline.py", encoding="utf-8").read()
        assert 'youtube_urls.get("shorts_count_requested", 0)' in src, (
            "shorts_count_requested default regressed to a phantom 1"
        )
