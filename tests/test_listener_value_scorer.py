"""Guards for the Listener Value Scorer recalibration (August 2026).

The scorer warned "below threshold" on EVERY episode of EVERY show —
60 sampled runs across five shows scored 3.1-6.3 against a 6.5 bar, so
the gate carried no information.

Worse, it scored the presence of stock phrases: ``narrative`` counted
"since we last" / "update on" / "open question", and ``listener_value``
counted "why this matters" / "what this means for" / "watch for". Those
are documented tics — ``engine.generator`` calls 'watch for' 12x "a
heavier real tic" a regeneration introduced, and "this matters for" sits
in the repetition detector's template-artefact allowlist. The
suggestions then told the operator to add exactly that phrasing, which
is how seeded tics start (see the network rule: de-seed by shape, never
with a quotable example).

v2 measures what the shows are actually asked for — coverage of the
programs the memory system tracks, and density of figures and named
entities — and the threshold is calibrated to fire on the bottom ~10%.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine import listener_value_scorer as lvs  # noqa: E402


_SCRIPT = (
    "Starship completed its thirteenth flight on August 2, lifting 47 "
    "Starlink satellites to a 340 kilometre orbit. Raptor engines ran "
    "for 162 seconds before staging. The Falcon 9 booster returned to "
    "Landing Zone 1 nine minutes later. Analysts at Morgan Stanley put "
    "the cadence at 92 launches year to date, ahead of the 80 forecast "
    "in January. Starbase crews began stacking the next vehicle within "
    "18 hours of the landing."
)


class TestNoLongerRewardsTicPhrases:
    def test_catchphrases_do_not_raise_the_value_score(self):
        """A script stuffed with the old reward phrases but empty of
        substance must not outscore a specific one."""
        stuffed = (
            "Why this matters is simple. What this means for owners is "
            "clear. Watch for the next update on the ongoing story. "
            "Since we last spoke there is an open question worth asking. "
        ) * 6
        stuffed_score = lvs.score_script(stuffed, target_words=200)
        real_score = lvs.score_script(_SCRIPT, target_words=200)
        assert real_score["listener_value"] > stuffed_score["listener_value"]

    def test_reward_phrase_lists_are_gone_from_the_source(self):
        src = (PROJECT_ROOT / "engine" / "listener_value_scorer.py").read_text(
            encoding="utf-8")
        # They may appear in explanatory comments, but not as scored data.
        assert 'value_indicators = [' not in src
        assert 'memory_keywords = [' not in src

    def test_suggestions_never_quote_a_phrase_to_insert(self):
        thin = "It happened. It was reported. People responded. " * 20
        out = lvs.score_script(thin, target_words=400)
        text = out["suggestions"].lower()
        for banned in ("why this matters", "watch for", "since we last",
                       "what this means for"):
            assert banned not in text, f"suggestion seeds {banned!r}"


class TestSpecificityDrivesValue:
    def test_figures_and_entities_score_higher_than_vague_prose(self):
        vague = ("The company made progress on its programme and things "
                 "moved forward for everyone involved. ") * 8
        assert (lvs.score_script(_SCRIPT, target_words=200)["listener_value"]
                > lvs.score_script(vague, target_words=200)["listener_value"])

    def test_sentence_initial_capitals_are_not_counted_as_entities(self):
        """Otherwise every sentence start inflates specificity."""
        plain = ("Today the team shipped. Then the team rested. "
                 "Later the team returned. ") * 8
        assert lvs.score_script(plain, target_words=200)["listener_value"] < 4


class TestProgramCoverage:
    def test_covering_tracked_programs_scores_high(self):
        memory = {"narrative_memory_section": (
            "Tracked programs: Starship Development, Starlink Expansion, "
            "Falcon Reuse, Dragon Crew Rotation. Status notes follow for "
            "each programme with dates and current state of play."
        )}
        out = lvs.score_script(
            "Starship Development advanced this week while Starlink "
            "Expansion added capacity and Falcon Reuse hit a new mark. "
            + _SCRIPT, memory_blocks=memory, target_words=200)
        assert out["narrative_continuity"] >= 7.5

    def test_ignoring_tracked_programs_scores_low(self):
        memory = {"narrative_memory_section": (
            "Tracked programs: Starship Development, Starlink Expansion, "
            "Falcon Reuse, Dragon Crew Rotation. Status notes follow for "
            "each programme with dates and current state of play."
        )}
        out = lvs.score_script(
            "An unrelated discussion of weather patterns and shipping "
            "lanes filled the episode today. " * 6,
            memory_blocks=memory, target_words=200)
        assert out["narrative_continuity"] <= 2.5

    def test_no_memory_context_is_neutral_not_zero(self):
        """A show without a memory system must not be permanently
        penalised on a dimension it cannot express."""
        assert lvs.score_script(_SCRIPT, memory_blocks={},
                                target_words=200)["narrative_continuity"] == 5.0


class TestThresholdIsCalibrated:
    def test_threshold_constant_exists_and_is_used(self):
        assert hasattr(lvs, "REVIEW_THRESHOLD")
        run_show = (PROJECT_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "listener_value_scorer.REVIEW_THRESHOLD" in run_show
        assert "< 6.5" not in run_show.split("Listener Value Score")[0][-400:]

    def test_real_scripts_mostly_clear_the_bar(self):
        """The calibration itself: a gate that always fires is noise."""
        import glob
        scores = []
        for slug in ("spacex", "tesla_shorts_time", "fascinating_frontiers"):
            for path in sorted(glob.glob(f"digests/{slug}/*_tts.txt"))[-10:]:
                scores.append(lvs.score_script(
                    Path(path).read_text(encoding="utf-8"),
                    show_slug=slug, memory_blocks={},
                    target_words=1300)["overall"])
        if len(scores) < 10:
            import pytest
            pytest.skip("not enough committed scripts in this checkout")
        fired = sum(1 for s in scores if s < lvs.REVIEW_THRESHOLD)
        assert fired / len(scores) < 0.35, (
            f"gate fires on {fired}/{len(scores)} shipped scripts")

    def test_version_marks_the_break_in_comparability(self):
        assert lvs.score_script(_SCRIPT, target_words=200)["version"].startswith(
            "2.")
