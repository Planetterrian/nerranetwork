"""Drift guards: complete headlines for window-titled dub Shorts (Aug 2026)
plus the pre-staged spacex specials.

Once the RU 3-Short band shipped, ~2/3 of @NerraRU's Short titles were
mid-sentence transcript fragments («атмосферу. Успех станет…») — the
2nd/3rd Short is titled from its window's opening speech, a mid-sentence
slice by construction. ``engine.translate.headline_from_excerpt`` now asks
Grok for ONE complete same-language headline grounded in the excerpt
(never-invent), and both dub paths fall back to the legacy clause-trim on
any failure. Title-only metadata — no audio touched.
"""

from __future__ import annotations

from pathlib import Path

import yaml

import engine.translate as tr

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RU_EXCERPT = (
    "атмосферу. Успех станет первым возвращением верхней ступени с "
    "орбитальной скорости с неповреждённым теплозащитным экраном, что "
    "подтвердит текущий плиточный подход."
)


class TestHeadlineFromExcerpt:
    def test_happy_path_returns_validated_headline(self, monkeypatch):
        monkeypatch.setattr(
            tr, "_generate",
            lambda prompt, model, max_tokens:
                "«Успех подтвердит плиточный теплозащитный экран Starship»")
        out = tr.headline_from_excerpt(RU_EXCERPT, "ru", max_chars=70)
        assert out == "Успех подтвердит плиточный теплозащитный экран Starship"

    def test_wrong_script_result_rejected(self, monkeypatch):
        # An English headline must never ship on @NerraRU — the same
        # script guard the audio-translation path uses.
        monkeypatch.setattr(
            tr, "_generate",
            lambda *a: "Starship heat shield survives first orbital return")
        assert tr.headline_from_excerpt(RU_EXCERPT, "ru") == ""

    def test_wildly_over_budget_rejected(self, monkeypatch):
        monkeypatch.setattr(tr, "_generate", lambda *a: "х" * 300)
        assert tr.headline_from_excerpt(RU_EXCERPT, "ru", max_chars=70) == ""

    def test_short_excerpt_skips_llm_call(self, monkeypatch):
        def _boom(*a):  # pragma: no cover
            raise AssertionError("must not call the LLM for a stub excerpt")
        monkeypatch.setattr(tr, "_generate", _boom)
        assert tr.headline_from_excerpt("короткое", "ru") == ""
        assert tr.headline_from_excerpt(RU_EXCERPT, "xx") == ""

    def test_generate_failure_returns_empty(self, monkeypatch):
        def _boom(*a):
            raise RuntimeError("network down")
        monkeypatch.setattr(tr, "_generate", _boom)
        assert tr.headline_from_excerpt(RU_EXCERPT, "ru") == ""


class TestDubWiring:
    """Both dub paths try the headline first and KEEP the clause-trim
    fallback — a Short must never ship untitled because Grok hiccuped."""

    def test_ru_dub_uses_headline_with_fallback(self):
        src = (PROJECT_ROOT / "engine" / "ru_dub.py").read_text()
        assert "headline_from_excerpt" in src
        # The legacy fallback trim of the raw excerpt must survive.
        assert 'opening_text.rstrip("…").rstrip()' in src

    def test_lang_dub_uses_headline_with_fallback(self):
        src = (PROJECT_ROOT / "engine" / "lang_dub.py").read_text()
        assert "headline_from_excerpt" in src
        assert 'opening_text.rstrip("…").rstrip()' in src


class TestPreStagedSpecials:
    def test_queue_carries_both_specials_unproduced(self):
        data = yaml.safe_load(
            (PROJECT_ROOT / "shows" / "deep_dives" / "spacex.yaml").read_text())
        by_id = {e["id"]: e for e in data["queue"]}
        assert by_id["q2-2026-earnings"]["produced"] is True  # history intact
        for eid in ("flight-14-catch-reaction", "q3-2026-earnings"):
            e = by_id[eid]
            assert e["produced"] is False
            assert e["title"] and e["brief"]
            assert e["web_search_queries"] and e["x_handles"]
            # Manual-force only: no scheduling keys, so even if
            # deep_dive.enabled ever flips true these cannot hijack a
            # daily episode on their own.
            assert "date" not in e and "when" not in e

    def test_future_event_briefs_enforce_honesty(self):
        """Both events post-date the brief's authorship — each brief must
        pin its facts to the live research, never presume the outcome."""
        data = yaml.safe_load(
            (PROJECT_ROOT / "shows" / "deep_dives" / "spacex.yaml").read_text())
        by_id = {e["id"]: e for e in data["queue"]}
        f14 = by_id["flight-14-catch-reaction"]["brief"]
        assert "{current_research}" in f14
        assert "UNKNOWN" in f14
        assert "Do not presume success" in f14
        q3 = by_id["q3-2026-earnings"]["brief"]
        assert "{current_research}" in q3
        assert "never reuse a Q2 figure" in q3

    def test_forced_pick_finds_both_and_unforced_finds_none(self):
        from engine.topic_queue import pick_deep_dive_topic
        q = PROJECT_ROOT / "shows" / "deep_dives" / "spacex.yaml"
        assert pick_deep_dive_topic(q, "2026-08-07") is None
        for eid in ("flight-14-catch-reaction", "q3-2026-earnings"):
            t = pick_deep_dive_topic(q, "2026-08-07", force_id=eid)
            assert t and t["id"] == eid
