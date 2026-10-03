"""Dub Shorts are never titled with a transcript fragment (2026-10-03).

The RU and FR channels title each non-hook Short from its window. The
excerpt they handed the headline helper was ONE Whisper segment, often three
words on the Russian track, so the helper refused it (under 15 chars) or had
no story to name, and the raw slice shipped. 81 of 314 RU filled Shorts
published since August carried titles like the ones below, and the SpaceX
Ep119 RU Short published on 2026-10-03 was titled «в 2026 года».

Now the selector carries each window's spoken text, the helper reads that,
and a result that still reads as a fragment is refused in favour of the
whole-episode headline. Title metadata only: no audio changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import ru_dub  # noqa: E402
from engine import translate as tr  # noqa: E402
from engine.shorts_selector import (  # noqa: E402
    WINDOW_TEXT_MAX_CHARS,
    _window_text,
    hook_first_windows,
    pick_top_n_engaging_windows,
)
from engine.titles import is_fragment_title  # noqa: E402

#: Titles that actually shipped on @NerraRU (api/youtube_stats.json).
SHIPPED_FRAGMENTS = [
    "в 2026 года #Shorts",
    "2026 года #Shorts",
    "Как минимум до 2030 года #Shorts",
    "туманности #Shorts",
    "2008 год #Shorts",
]

#: Grammatical but contentless — they name no story. The shape test lets
#: them through on purpose: requiring a proper noun would also reject real
#: headlines like «Черная дыра разрывает звезду…» (797 views, Aug 10). They
#: came from the same one-segment excerpt, and the window text is what fixes
#: them (the helper now reads the window's whole story).
CONTENTLESS_BUT_WHOLE = [
    "Подсказки в 60-70% случаев #Shorts",
    "Полет запланирован на 2029 год #Shorts",
]

#: Titles that shipped on the same Shorts and are real headlines.
SHIPPED_HEADLINES = [
    "Межзвёздная комета 3I/ATLAS прослежена до другой звёздной системы #Shorts",
    "Tesla Powerwalls выдали 500 МВт во время жары в Калифорнии #Shorts",
    "Falcon Heavy выбран для миссии NASA Dragonfly на Титан #Shorts",
    "La NASA découvre des vents de 5400 mph sur une exoplanète lointaine #Shorts",
    "SpaceX Posts First Job for Starbase Louisiana Launch Site",
]


class TestFragmentShape:
    @pytest.mark.parametrize("title", SHIPPED_FRAGMENTS)
    def test_every_shipped_fragment_is_caught(self, title):
        assert is_fragment_title(title)

    @pytest.mark.parametrize("title", CONTENTLESS_BUT_WHOLE)
    def test_contentless_titles_are_left_to_the_context_fix(self, title):
        assert not is_fragment_title(title)

    def test_an_entity_free_headline_is_not_a_fragment(self):
        assert not is_fragment_title(
            "Черная дыра разрывает звезду, раскрывая изменения в галактике")

    @pytest.mark.parametrize("title", SHIPPED_HEADLINES)
    def test_real_headlines_pass(self, title):
        assert not is_fragment_title(title)

    def test_lowercase_start_is_a_fragment(self):
        assert is_fragment_title("полезную нагрузку StarShield с площадки Wandenberg")

    def test_empty_is_a_fragment(self):
        assert is_fragment_title("")
        assert is_fragment_title("#Shorts")


def _segments():
    return [
        {"start": 0.0, "end": 4.0, "text": "Первый полёт Falcon Heavy для NRO."},
        {"start": 4.0, "end": 6.0, "text": "в 2026 года."},
        {"start": 6.0, "end": 14.0,
         "text": "Оба боковых ускорителя приземлились на площадках LZ-1 и LZ-2."},
        {"start": 14.0, "end": 30.0,
         "text": "Это первый запуск тяжёлой ракеты для разведывательного ведомства."},
        {"start": 40.0, "end": 50.0, "text": "Следующая тема — Starlink."},
    ]


class TestWindowText:
    def test_joins_the_speech_inside_the_window(self):
        txt = _window_text(_segments(), 1, window_duration=35.0)
        assert txt.startswith("в 2026 года.")
        assert "LZ-1" in txt and "разведывательного" in txt
        assert "Starlink" not in txt, "a segment past the window leaked in"

    def test_capped_on_a_word_boundary(self):
        segs = [{"start": float(i), "text": "слово " * 30} for i in range(20)]
        txt = _window_text(segs, 0, window_duration=35.0)
        assert len(txt) <= WINDOW_TEXT_MAX_CHARS
        assert not txt.endswith(" ")

    def test_never_raises(self):
        assert _window_text([], 3, window_duration=35.0) == ""
        assert _window_text([{"start": "x"}], 0, window_duration=35.0) == ""

    def test_scored_windows_carry_it(self, tmp_path):
        tr_json = tmp_path / "t.json"
        segs = [{"start": float(t), "end": float(t) + 5,
                 "text": f"Сегмент номер {t} про SpaceX и запуск Falcon 9."}
                for t in range(0, 300, 5)]
        tr_json.write_text(json.dumps({"segments": segs, "duration": 305.0}))
        wins = pick_top_n_engaging_windows(
            tr_json, n=3, audio_offset=0.0, audio_duration=305.0,
            window_duration=35.0, min_score_threshold=0.0, fill_to_n=True)
        assert wins, "selector found no window on a plain transcript"
        for w in wins:
            assert w.opening_text and w.window_text.startswith(
                w.opening_text.rstrip("…")[:10])
            assert len(w.window_text) >= len(w.opening_text.rstrip("…"))

    def test_hook_window_text_is_the_hook(self):
        w = hook_first_windows([], n=1, hook_start=0.0,
                               hook_text="Первый полёт Falcon Heavy")[0]
        assert w.window_text == "Первый полёт Falcon Heavy"


class TestHeadlineNeverAFragment:
    def test_the_helper_reads_the_window_speech(self, monkeypatch):
        seen = {}

        def _fake(excerpt, lang, *, max_chars=70):
            seen["excerpt"] = excerpt
            return "Оба ускорителя Falcon Heavy приземлились после запуска для NRO"
        monkeypatch.setattr(tr, "headline_from_excerpt", _fake)
        out = ru_dub._window_short_headline(
            _window_text(_segments(), 1, window_duration=35.0),
            "в 2026 года.", "ru", 70)
        assert "LZ-1" in seen["excerpt"], "the helper was given one segment"
        assert out.startswith("Оба ускорителя")

    def test_a_fragment_headline_is_refused(self, monkeypatch):
        monkeypatch.setattr(tr, "headline_from_excerpt",
                            lambda *a, **k: "Как минимум до 2030 года")
        assert ru_dub._window_short_headline(
            "текст окна", "в 2026 года.", "ru", 70) == ""

    def test_a_failed_call_never_falls_back_to_the_slice(self, monkeypatch):
        monkeypatch.setattr(tr, "headline_from_excerpt", lambda *a, **k: "")
        assert ru_dub._window_short_headline(
            "", "в 2026 года.", "ru", 70) == ""

    def test_a_complete_raw_opening_still_serves(self, monkeypatch):
        monkeypatch.setattr(tr, "headline_from_excerpt", lambda *a, **k: "")
        out = ru_dub._window_short_headline(
            "", "Оба ускорителя Falcon Heavy приземлились на площадках LZ.",
            "ru", 70)
        assert out and not is_fragment_title(out)

    def test_the_fallback_title_is_a_headline(self):
        ru_title = "Первый полёт Falcon Heavy для NRO: оба ускорителя приземлились"
        fallback = ru_dub._ru_short_title(ru_title, body_limit=58) + " — ещё момент"
        assert not is_fragment_title(fallback)


class TestDashboardWatchSeesTheFragments:
    """The regression watch for this defect read low while it shipped: it
    flagged only a lowercase first letter and counted hook Shorts."""

    def _root(self, tmp_path, titles_by_window):
        import datetime as dt
        today = dt.date.today().isoformat()
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "youtube_stats.json").write_text(json.dumps(
            {"generated": today + "T00:00:00+00:00", "channels": {}, "shows": {}}))
        d = tmp_path / "digests" / "spacex"
        d.mkdir(parents=True)
        rows = [{"video_id": f"v{i}", "kind": "short", "channel": "ru",
                 "published": today, "window": w, "title": t}
                for i, (w, t) in enumerate(titles_by_window)]
        (d / "youtube_videos.ru.json").write_text(json.dumps({"videos": rows}))
        return tmp_path

    def test_digit_and_capital_start_fragments_count(self, tmp_path):
        sys.path.insert(0, str(ROOT / "scripts"))
        import generate_dashboard as G
        root = self._root(tmp_path, [
            ("hook_open", "в нижнем регистре, но это хук #Shorts"),
            ("filled", "2026 года #Shorts"),
            ("filled", "Как минимум до 2030 года #Shorts"),
            ("filled", "Межзвёздная комета 3I/ATLAS прослежена до другой системы #Shorts"),
            ("filled", "Falcon Heavy выбран для миссии NASA Dragonfly на Титан #Shorts"),
        ])
        out = G._experiment_live_metrics(root)
        # 2 of the 4 WINDOW Shorts; the hook Short is not in the denominator.
        assert out["dub_fragment_title_share_14d"] == 0.5
