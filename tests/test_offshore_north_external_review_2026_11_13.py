"""Offshore North — the external review's five suggestions (Nov 13 2026).

Review: docs/reviews/offshore_north_external_review_2026_11_13.md.
Register: offshore-north-external-review-2026-11-13.

1. The week's biggest story leads, ranked across all of offshore racing,
   never a story an earlier episode already covered.
2. Every race fact is dated; a clock time carries its place and date.
3. Each story carries its own why-it-matters; the Canadian boat only on a
   real connection.
4. The Canadian Boat runs every week, short and dated; a quiet week is one
   dated line, never a claim that nothing happened.
5. Each story told once; Plain Sailing never re-tells the episode or a past
   explainer (``explainer_distinct``); the countdown ends on one dated event
   to watch.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

import engine.digest_lint as dl

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "shows" / "prompts"
DIGESTS = ROOT / "digests" / "offshore_north"


def _digest() -> str:
    return (PROMPTS / "offshore_north_digest.txt").read_text(encoding="utf-8")


def _podcast() -> str:
    return (PROMPTS / "offshore_north_podcast.txt").read_text(encoding="utf-8")


def _system() -> str:
    return (PROMPTS / "offshore_north_system.txt").read_text(encoding="utf-8")


def _ep(n: int) -> Path:
    return next(DIGESTS.glob(f"Offshore_North_Ep{n:03d}_*.md"))


class TestRunningOrder:
    def test_fleet_comes_first_in_the_digest_template(self):
        d = _digest()
        fmt = d[d.index("### FORMATTING (EXACT)"):]
        assert fmt.index("### The Fleet") < fmt.index("## The Canadian Boat") < fmt.index("## Plain Sailing")

    def test_fleet_comes_first_in_the_script_structure(self):
        p = _podcast()
        assert p.index("[The Fleet]") < p.index("[The Canadian Boat]") < p.index("[Plain Sailing]")

    def test_the_campaign_leads_only_with_the_weeks_biggest_story(self):
        d, p = _digest(), _podcast()
        assert "runs BEFORE ### The Fleet" in d
        assert "BEFORE The Fleet (the campaign has the week's biggest story)" in p
        assert "running order follows the news" in _system()

    def test_rank_the_week_across_all_offshore_racing(self):
        d = _digest()
        assert "RANK THE WEEK FIRST" in d
        rank = d[d.index("RANK THE WEEK FIRST"):d.index("THE WINDOW:")]
        for cls in ("IMOCA", "Ultim", "Ocean Fifty", "Class40"):
            assert cls in rank
        assert "never the lead and never retold" in rank

    def test_hook_repeat_gate_is_still_on(self):
        lints = yaml.safe_load((ROOT / "shows" / "offshore_north.yaml").read_text())["digest_lints"]
        assert "hook_repeats_past_lead" in lints


class TestCanadianBoat:
    def test_short_dated_every_week(self):
        d = _digest()
        start = d.index("## The Canadian Boat\nSHORT AND DATED")
        sec = d[start:d.index("## Plain Sailing\n", start)]
        m = re.search(r"(\d+)–(\d+) words in the brief", sec)
        assert m and int(m.group(2)) <= 250
        assert "A QUIET WEEK IS ONE LINE" in sec

    def test_quiet_week_is_never_an_absence_claim(self):
        d, p = _digest(), _podcast()
        assert "never a claim that nothing happened" in d
        assert "never say that nothing happened" in p
        # the Sep 18 absence ban is untouched
        assert "NEVER CLAIM AN ABSENCE OF NEWS" in d and "NEVER CLAIM AN ABSENCE OF NEWS" in p

    def test_qualification_is_one_sentence_here(self):
        d, p = _digest(), _podcast()
        assert "say so in ONE sentence using ONLY the field guide's qualification section" in d
        assert "Qualification gets one sentence at most here" in p


class TestDatedFactsAndWhyItMatters:
    def test_every_race_fact_is_dated(self):
        d = _digest()
        assert "EVERY RACE FACT IS DATED" in d
        assert '"local time" with no place' in d
        assert "Every race fact is dated" in _system()

    def test_own_consequence_and_real_canadian_connection(self):
        d, p = _digest(), _podcast()
        assert "its OWN explicit consequence line" in d
        assert "Two items never share one consequence line" in d and "Two items never share one consequence line" in p
        assert "only on a real connection" in d

    def test_no_quotable_specimen_was_added(self):
        """De-seed by shape: the new rules describe the shape and carry no
        sentence the model could copy."""
        both = _digest() + _podcast()
        for specimen in ("Guadeloupe time", "half past two", "23 October, announced",
                         "due into Guadeloupe"):
            assert specimen not in both


class TestOneToWatch:
    def test_countdown_ends_on_one_dated_event(self):
        d, p = _digest(), _podcast()
        start = d.index("## The Countdown\n")
        cd = d[start:d.index("## Sources\n", start)]
        assert "Three facts, no more" in cd and "ONE TO WATCH" in cd
        assert "never a promise of what the show will cover" in cd
        assert "left out" in cd
        pc = p[p.index("[The Countdown]"):p.index("[Closing]")]
        assert "one to watch" in pc and "never as a promise" in pc


class TestExplainerDistinct:
    def test_registered_context_aware_and_wired(self):
        assert "explainer_distinct" in dl.LINTS
        assert "explainer_distinct" in dl.CONTEXT_LINTS
        lints = yaml.safe_load((ROOT / "shows" / "offshore_north.yaml").read_text())["digest_lints"]
        assert "explainer_distinct" in lints
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'ctx["past_explainers"] = past_explainer_openings(' in src

    def test_replay_fires_on_ep013_retell(self):
        r = dl.lint_explainer_distinct(_ep(13).read_text(encoding="utf-8"),
                                       {"past_explainers": dl.past_explainer_openings(DIGESTS, before_episode=13)})
        assert r and "The Canadian Boat" in r.note
        assert r.metrics["explainer_retells_section"] >= dl.EXPLAINER_RETELL_MAX

    def test_replay_fires_on_ep012_copied_opening(self):
        r = dl.lint_explainer_distinct(_ep(12).read_text(encoding="utf-8"),
                                       {"past_explainers": dl.past_explainer_openings(DIGESTS, before_episode=12)})
        assert r and "2026-09-21" in r.note
        assert r.metrics["explainer_repeats_past"] == 1

    def test_replay_quiet_on_ep006_to_ep011(self):
        for n in range(6, 12):
            r = dl.lint_explainer_distinct(_ep(n).read_text(encoding="utf-8"),
                                           {"past_explainers": dl.past_explainer_openings(DIGESTS, before_episode=n)})
            assert r is not None and r.note == "", (n, r.note)

    def test_no_explainer_measures_nothing(self):
        assert dl.lint_explainer_distinct("# X\n\n## The Fleet\nA thing happened.\n") is None

    def test_runner_routes_context(self):
        digest = _ep(12).read_text(encoding="utf-8")
        fired, metrics = dl.run_digest_lints(
            digest, ["explainer_distinct"],
            {"past_explainers": dl.past_explainer_openings(DIGESTS, before_episode=12)})
        assert [f.lint for f in fired] == ["explainer_distinct"]
        assert metrics["explainer_repeats_past"] == 1

    def test_past_openings_never_raise(self, tmp_path):
        assert dl.past_explainer_openings(tmp_path / "missing") == []
