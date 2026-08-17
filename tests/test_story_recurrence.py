"""Drift guards for the story-recurrence memory (Aug 2026).

Built after the Fort Bend solar-factory story ran in 5 of 10 Tesla
episodes (and 4 times inside Ep573) past three existing dedup layers:
the 0.72 title-similarity / 2-day content_freshness check, the
ContentTracker's flat DO-NOT-REPEAT list, and the exact-duplicate strip.
The lever is data-side (reads the tracker's dated headline window, no
LLM calls) and delivers inline update-don't-retell notes attached to the
exact articles the model is deciding about — the DP Pod lever-memory
pattern applied to news.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.story_recurrence import (  # noqa: E402
    RecurrenceIndex,
    annotate_articles,
    annotation_for,
    recurrence_in_digest,
    salient_tokens,
)

# The real Fort Bend headline variants that shipped across Tesla
# Ep565-573 — the class the old layers missed because the titles are
# lexically far apart while the story is identical.
_FORT_BEND = [
    "Tesla plans $10B solar cell factory in Fort Bend County",
    "Tesla considers $10 billion solar cell plant in Fort Bend County",
    "Tesla files tax incentive application for $10.1 billion Texas solar cell plant",
    "Tesla seeks Texas tax incentive for USD-10bn solar cell factory",
    "Tesla wants tax breaks to build solar manufacturing plant in Fort Bend County",
]


def _window(headlines_by_date):
    return [{"date": d, "headlines": hs} for d, hs in headlines_by_date]


class TestMatching:
    def _index(self):
        # Realistic window shape: ~8 headlines/day with the recurring
        # story once per day. "tesla" crosses the common-token threshold
        # (as in the real 15-episode window, where it is the ONLY common
        # token); the story's own tokens must NOT — a token carried only
        # by one recurring story is exactly the signal we match on.
        filler = [
            "Tesla recalls 20,000 vehicles over software issue",
            "Tesla Optimus demonstrates new dexterity milestone",
            "Tesla opens 124-stall Supercharger site in Arizona",
            "Tesla FSD v14 expands to more HW3 vehicles",
            "Tesla Semi fleet crosses one million miles",
            "Tesla energy storage deployments hit quarterly record",
            "Tesla Cybertruck production reaches new weekly high",
            "Tesla insurance arm expands to three more states",
            "Tesla megapack order lands with Australian utility",
            "Tesla updates mobile app with charging planner",
            "Tesla hires new head of battery engineering",
            "Tesla robotaxi pilot adds Phoenix service area",
            "Tesla dojo cluster milestone announced by AI team",
            "Tesla model y refresh spotted at fremont factory",
            "Tesla powerwall installations double year over year",
            "Tesla earnings call scheduled for late october",
            "Tesla wins fleet contract with logistics giant",
            "Tesla adds v2h capability in new markets",
            "Tesla shanghai exports rise on strong quarter",
            "Tesla roadside assistance expands coverage hours",
            "Tesla paint shop upgrade begins at giga berlin",
        ]
        return RecurrenceIndex(_window([
            ("2026-08-10", [_FORT_BEND[0]] + filler[:7]),
            ("2026-08-12", [_FORT_BEND[1]] + filler[7:14]),
            ("2026-08-14", [_FORT_BEND[2]] + filler[14:21]),
        ]))

    def test_all_fort_bend_variants_match(self):
        idx = self._index()
        for v in _FORT_BEND:
            m = idx.match(v)
            assert m, f"re-headlined variant missed: {v!r}"

    # A today's-article probe carrying the story's core tokens — the
    # realistic case: a new development on the running story.
    _TODAY_PROBE = "Tesla Fort Bend solar cell plant tax incentive approved"

    def test_times_counts_distinct_days(self):
        idx = self._index()
        m = idx.match(self._TODAY_PROBE)
        assert m and m["times"] == 3  # three window DAYS covered it

    def test_most_recent_match_is_cited(self):
        idx = self._index()
        m = idx.match(self._TODAY_PROBE)
        assert m["date"] == "2026-08-14", (
            "the note says 'most recently on …' — it must cite the "
            "newest matching day, not an older copy")

    def test_unrelated_stories_do_not_match(self):
        idx = self._index()
        for title in (
            "SpaceX launches 28 Starlink satellites from Florida",
            "Tesla Cybertruck wins design award in Germany",
            "Rivian announces new battery chemistry",
        ):
            assert idx.match(title) is None, title

    def test_brand_token_alone_cannot_manufacture_a_match(self):
        # "tesla" is in >30% of window headlines -> common -> excluded.
        idx = self._index()
        assert "tesla" in idx.common

    def test_self_match_excluded_by_date(self):
        idx = RecurrenceIndex(
            _window([("2026-08-16", [_FORT_BEND[0]])]),
            exclude_date="2026-08-16",
        )
        assert len(idx) == 0

    def test_empty_window_is_a_clean_noop(self):
        idx = RecurrenceIndex([])
        assert idx.match(_FORT_BEND[0]) is None
        assert annotate_articles([{"title": _FORT_BEND[0]}], idx) == {}


class TestAnnotation:
    def test_annotation_is_instruction_shaped(self):
        note = annotation_for(
            {"date": "2026-08-14", "headline": _FORT_BEND[2], "times": 3})
        # The load-bearing framing: update, don't ban / don't re-tell.
        assert "NEW development" in note
        assert "UPDATE" in note
        assert "never re-tell" in note
        assert "hook" in note
        # De-seed rule: the note must self-identify as instruction so an
        # echo is detectable, and the sanitizer strips that marker.
        assert note.strip().startswith("[ALREADY-COVERED NOTE")

    def test_sanitizer_strips_an_echoed_note(self):
        from engine.newsletter_sanitizer import scrub_scaffold
        echoed = ("Real digest line.\n"
                  "[ALREADY-COVERED NOTE — instruction, not content: x]\n"
                  "Another real line.")
        out = scrub_scaffold(echoed)
        assert "ALREADY-COVERED" not in out
        assert "Real digest line." in out and "Another real line." in out

    def test_recurrence_in_digest_counts_matches(self):
        idx = TestMatching()._index()
        digest = (
            "### Top News\n"
            f"1. **{_FORT_BEND[4]}**\n   body\n"
            "2. **Rivian announces new battery chemistry**\n   body\n"
        )
        assert recurrence_in_digest(digest, idx) == 1


class TestWiring:
    def test_config_field_exists_and_defaults_off(self):
        from engine.config import load_config
        cfg = load_config(_ROOT / "shows" / "unintended_consequences.yaml")
        assert getattr(cfg, "story_recurrence") is False

    def test_news_shows_opted_in(self):
        for slug in ("tesla", "spacex", "omni_view", "fascinating_frontiers",
                     "planetterrian", "models_agents",
                     "models_agents_beginners", "modern_investing",
                     "env_intel"):
            data = yaml.safe_load(
                (_ROOT / "shows" / f"{slug}.yaml").read_text())
            assert data.get("story_recurrence") is True, slug

    def test_lesson_and_narrative_shows_stay_off(self):
        # Lesson shows revisit topics as CURRICULUM (vocab_tracker owns
        # that); narrative-queue shows have their own no-repeat history.
        for slug in ("finansy_prosto", "privet_russian",
                     "unintended_consequences", "first_principles"):
            data = yaml.safe_load(
                (_ROOT / "shows" / f"{slug}.yaml").read_text())
            assert not data.get("story_recurrence"), slug

    def test_run_show_wires_annotation_and_metric(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "annotate_articles" in src
        assert "story_recurrence_in_digest" in src
        # The outcome metric must be computed against a window that
        # EXCLUDES today (the FF Ep128 self-match class).
        assert "exclude_date=datetime.date.today().isoformat()" in src

    def test_salient_tokens_drop_stopwords(self):
        toks = salient_tokens("Tesla says it will report new record today")
        assert "says" not in toks and "will" not in toks and "new" not in toks
        assert "tesla" in toks and "record" in toks
