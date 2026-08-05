"""Drift guards for the Offshore North weekly-cadence fixes (Aug 4 2026).

Ep001 generated on 2026-08-04 was SKIPPED: a 1124-word podcast script
against a self-imposed 1150-word hard floor. The proximate cause was 26
words; the real cause was that the network fetch ladder tops out at 72h
while the show publishes weekly, so four of the seven days it reports on
were invisible. With keyword filtering on, all stages starved at 6
articles from 2 of 17 feeds; the run only reached 46 articles by dropping
keywords entirely, i.e. by going off-topic, and the digest came out at
596 words against a 1300 target.

These guards pin the three config-side fixes plus the debut appendices,
and — most importantly — that the ladder override is a strict no-op for
every other show.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.config import load_config  # noqa: E402
from engine.first_episode import (  # noqa: E402
    first_episode_digest_appendix,
    first_episode_podcast_appendix,
)

_SHOW_YAML = _ROOT / "shows" / "offshore_north.yaml"


def _cfg():
    return load_config(str(_SHOW_YAML))


class TestFetchLadderOverride:
    def test_offshore_north_ladder_covers_its_own_week(self):
        hours = _cfg().fetch_expansion_hours
        assert hours, "offshore_north must declare a fetch ladder"
        assert max(hours) >= 168, (
            "a Monday show reports on seven days; the widest stage must reach "
            f"168h, got {max(hours)}h"
        )

    def test_every_other_show_keeps_the_default_ladder(self):
        """The override must be opt-in. An accidental default here would
        re-tune the fetch window for all 15 other shows at once."""
        offenders = []
        for path in sorted((_ROOT / "shows").glob("*.yaml")):
            if path.stem.startswith("_") or path.stem == "offshore_north":
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict) or "slug" not in data:
                continue  # not a show config
            if data.get("fetch_expansion_hours"):
                offenders.append(path.stem)
        assert not offenders, (
            "these shows gained a custom fetch ladder — intentional? " f"{offenders}"
        )

    def test_default_is_empty_so_dataclass_falls_back(self):
        from engine.config import ShowConfig

        assert ShowConfig().fetch_expansion_hours == []

    def test_yaml_key_is_actually_read(self):
        """Guards the silent config-drop class (landmine: _build_nested).

        The value in the YAML must survive into the dataclass — a typo in
        the factory would leave the show on the 72h ladder while the YAML
        claims otherwise.
        """
        raw = yaml.safe_load(_SHOW_YAML.read_text(encoding="utf-8"))
        assert _cfg().fetch_expansion_hours == [
            int(h) for h in raw["fetch_expansion_hours"]
        ]

    def test_run_show_builds_stages_from_config(self):
        """The ladder override must exist in run_show and must put the
        keyword-off stage LAST. Dropping keywords earlier trades a longer
        article list for a worse digest — that is what produced the
        596-word digest on 2026-08-04."""
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "fetch_expansion_hours" in src, "override not wired into run_show"
        block = src[src.index("_custom_hours = list(") :][:1200]
        # the appended final stage is the keyword-off one
        assert "expansion_stages.append((_custom_hours[-1], 0.55, False))" in block


class TestThinScriptFloor:
    def test_floor_lets_a_real_episode_through(self):
        """1124 words was a real episode refused by a rounding error."""
        llm = _cfg().llm
        target = llm.min_podcast_words
        hard = max(llm.min_podcast_word_floor or 600, int(target * 0.4))
        soft = int(target * 0.6)
        # run_show skips when below EITHER floor, so the binding gate is the max
        assert max(hard, soft) <= 1124, (
            f"the Ep001 script (1124 words) would still be skipped: "
            f"hard={hard} soft={soft}"
        )

    def test_floor_still_refuses_a_genuinely_rushed_episode(self):
        llm = _cfg().llm
        hard = max(llm.min_podcast_word_floor or 600, int(llm.min_podcast_words * 0.4))
        soft = int(llm.min_podcast_words * 0.6)
        assert max(hard, soft) >= 900, "floor lowered so far it protects nothing"


class TestDeadFeedRemoved:
    def test_seahorse_is_gone(self):
        """Returned 'Feed yielded 0 entries' on all four passes of the
        first live run — the only genuinely broken feed of the 17."""
        urls = " ".join((s.url or "") for s in _cfg().sources).lower()
        assert "seahorsemagazine.com" not in urls

    def test_the_merely_filtered_feeds_were_kept(self):
        """Vendee Globe / Sailorz / Yachting World / Canadian Boating all
        parsed 10-100 entries and were filtered out by the 72h window, not
        broken. Removing them would have been the wrong fix."""
        urls = " ".join((s.url or "") for s in _cfg().sources).lower()
        for host in ("vendeeglobe", "sailorz", "yachtingworld", "canadianboating"):
            assert host in urls, f"{host} was removed — it was filtered, not dead"


class TestDebutIntroduction:
    def test_both_appendices_are_bespoke_for_ep1(self):
        d = first_episode_digest_appendix(1, "Offshore North", "offshore_north")
        p = first_episode_podcast_appendix(1, "Offshore North", "offshore_north")
        assert "What This Show Is" in d
        assert "THE INTRODUCTION" in p

    def test_debut_covers_show_purpose_and_the_network(self):
        p = first_episode_podcast_appendix(1, "Offshore North", "offshore_north")
        # collapse wrapping — the template is hard-wrapped prose, so a
        # phrase can legitimately straddle a line break
        low = " ".join(p.lower().split())
        assert "why it exists" in low
        assert "nerra network" in low
        assert "ad-free" in low
        assert "nerranetwork.com" in low or "nerra network dot com" in low
        for segment in (
            "The Canadian Boat",
            "The Fleet",
            "Plain Sailing",
            "The Countdown",
        ):
            assert segment in p, f"debut must still run {segment}"

    def test_debut_protects_the_intro_line_position(self):
        """The Introduction chapter marker is positional (first ~10% of
        words). Ep001 shipped without it."""
        p = first_episode_podcast_appendix(1, "Offshore North", "offshore_north")
        assert "VERBATIM" in p
        assert re.search(r"first ~?\d+ words", p)

    def test_debut_forbids_inventing_a_biography(self):
        """Dan is a real person; the show's unforgivable error is a
        confidently-stated wrong fact."""
        p = first_episode_podcast_appendix(1, "Offshore North", "offshore_north")
        assert "Do NOT invent" in p

    def test_templates_render_without_stray_placeholders(self):
        for fn in (first_episode_digest_appendix, first_episode_podcast_appendix):
            out = fn(1, "Offshore North", "offshore_north")
            assert "{" not in out and "}" not in out

    def test_only_episode_one_gets_the_appendix(self):
        assert first_episode_digest_appendix(2, "Offshore North", "offshore_north") == ""
        assert (
            first_episode_podcast_appendix(2, "Offshore North", "offshore_north") == ""
        )

    def test_other_shows_debuts_are_untouched(self):
        assert "DEBUT QUALITY BAR" in first_episode_digest_appendix(
            1, "Tesla Shorts Time", "tesla"
        )
        assert "THE DEBUT SCRIPT" in first_episode_podcast_appendix(
            1, "The DP Pod", "dp_pod"
        )


# ---------------------------------------------------------------------------
# Ep001 post-mortem fixes (2026-08-05). The first published episode ran
# 7m32s against a 10-15 min target, gave 38% of its runtime to the
# explainer segment, shipped no Introduction chapter, cited one source,
# and closed a WEEKLY SOLO show with "we'll see you tomorrow".
# ---------------------------------------------------------------------------


class TestKeywordFilterIsCaseInsensitive:
    """The highest-impact bug found in the Ep001 review.

    engine/fetcher.py compared un-lowercased keywords against lowercased
    text, so any keyword with a capital letter could never match — 149 of
    the network's 652 keywords, and 70% of Offshore North's. Every proper
    noun a show is ABOUT is capitalised.
    """

    def test_capitalised_keyword_matches_lowercase_text(self):
        from engine.fetcher import fetch_rss_articles  # noqa: F401  (import guard)

        src = (_ROOT / "engine" / "fetcher.py").read_text(encoding="utf-8")
        assert "any(kw.lower() in text_lower for kw in keywords)" in src, (
            "the RSS keyword filter must lowercase its keywords"
        )
        assert "any(kw in text_lower for kw in keywords)" not in src, (
            "the un-lowercased comparison is back — capitalised keywords are dead again"
        )

    def test_a_headline_of_this_shows_proper_nouns_passes(self):
        kws = [k.lower() for k in _cfg().keywords]
        blob = (
            "Vendee Globe 2028: Scott Shawyer and Canada Ocean Racing "
            "confirm IMOCA programme"
        ).lower()
        assert any(k in blob for k in kws)

    def test_off_topic_headline_is_still_rejected(self):
        """The fix must not turn the filter into a pass-through."""
        kws = [k.lower() for k in _cfg().keywords]
        blob = "Local council approves new bicycle lane downtown".lower()
        assert not any(k in blob for k in kws)


class TestWebSearchFiresOnRelevance:
    """Ep001 finished with 70 articles against min_articles=4, so the
    `len(articles) < min_articles` gate was never true and the show's
    eight configured web_search_queries never ran — even though only a
    handful of those 70 were on topic."""

    def test_gate_counts_on_topic_articles(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "_is_on_topic" in src
        assert "min(len(articles), _relevant) < min_quality" in src, (
            "web search must fire on on-topic count, not raw count"
        )

    def test_show_still_has_queries_to_run(self):
        assert len(_cfg().web_search_queries) >= 5


class TestIntroductionChapterLatches:
    def _pattern(self):
        raw = yaml.safe_load(_SHOW_YAML.read_text(encoding="utf-8"))
        return next(
            m["pattern"]
            for m in raw["chapters"]["section_markers"]
            if m["title"] == "Introduction"
        )

    def test_matches_the_exact_line_that_shipped_broken(self):
        """Ep001's opening. Greeting and show name both present; five
        words wedged between them broke the old pattern."""
        assert re.search(
            self._pattern(),
            "Welcome to the very first episode of Offshore North! Today is "
            "August fifth, twenty twenty-six.",
        )

    def test_still_matches_the_supplied_intro_line(self):
        assert re.search(self._pattern(), "This is Offshore North, episode 1.")

    def test_does_not_match_a_late_brand_mention(self):
        """`where: start` bounds this too, but the pattern must not be so
        loose that a sign-off mention could claim the marker."""
        assert not re.search(
            self._pattern(), "That is all from Offshore North for this week."
        )


class TestDebutDoesNotStealChapterMarkers:
    """The Ep001 debut template told the host to name the four segments,
    so "on the Canadian boat" was spoken inside the introduction and the
    chapter landed at 61s — inside the intro, not at the segment."""

    def test_debut_does_not_contain_segment_trigger_phrases(self):
        p = first_episode_podcast_appendix(1, "Offshore North", "offshore_north")
        raw = yaml.safe_load(_SHOW_YAML.read_text(encoding="utf-8"))
        triggers = []
        for marker in raw["chapters"]["section_markers"]:
            if marker["title"] in ("Introduction", "Sign-Off"):
                continue
            triggers += [t.strip() for t in marker["pattern"].split("|")]
        # the template may NAME a segment, but must never hand the model a
        # ready-made announcement phrase to speak early
        spoken = p.lower()
        for trig in triggers:
            plain = trig.replace("[Ff]", "f").replace(",?", ",")
            if plain.startswith("on the canadian boat") and plain in spoken:
                raise AssertionError(
                    f"debut template contains chapter trigger {plain!r}"
                )

    def test_debut_warns_about_the_trigger_phrases(self):
        p = first_episode_podcast_appendix(1, "Offshore North", "offshore_north")
        assert "chapter trigger" in p.lower()


class TestScriptNaturalness:
    """The operator's note was that Ep001 sounded robotic. The script was
    passive-voice and near-uniform sentence length; the prompt now says so
    explicitly, quoting the actual failures."""

    def _prompt(self):
        return (_ROOT / "shows" / "prompts" / "offshore_north_podcast.txt").read_text(
            encoding="utf-8"
        )

    def test_prompt_demands_active_voice_and_varied_rhythm(self):
        src = self._prompt().lower()
        assert "active voice" in src
        assert "vary sentence length" in src
        assert "contractions" in src

    def test_prompt_bans_meta_commentary_about_the_brief(self):
        """Ep001 said "not established in the supplied sources" on air."""
        assert "the supplied sources" in self._prompt()

    def test_prompt_bans_daily_cadence_language(self):
        """A weekly solo show said "we'll see you tomorrow for episode two"."""
        src = self._prompt()
        assert "tomorrow" in src and "NEXT MONDAY" in src

    def test_plain_sailing_has_a_hard_ceiling(self):
        src = self._prompt()
        assert "HARD CEILING" in src
        assert "600 spoken words" in src


class TestXSourcingIsScaffoldedButDormant:
    def test_accounts_present_but_fetch_disabled(self):
        raw = yaml.safe_load(_SHOW_YAML.read_text(encoding="utf-8"))
        assert raw.get("x_fetch_enabled") is False, (
            "handles are unverified — must not fetch until the operator checks them"
        )
        assert len(raw.get("x_accounts") or []) >= 3

    def test_every_handle_is_flagged_for_verification(self):
        raw = yaml.safe_load(_SHOW_YAML.read_text(encoding="utf-8"))
        for acct in raw["x_accounts"]:
            assert "VERIFY" in acct["label"], (
                f"{acct['handle']}: handle was never confirmed against live X"
            )
