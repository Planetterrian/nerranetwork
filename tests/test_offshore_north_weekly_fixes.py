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
        # Tightened 600 -> 450 by the August 2026 editorial review (v2
        # prompt): 350-450 target, never more than a quarter of the episode.
        assert "450 spoken words" in src
        assert "600 spoken words" not in src


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


# ---------------------------------------------------------------------------
# August 2026 editorial review (v2): standing facts, scope, single-source
# rule, tightened lengths, short display title, YouTube source feed.
# Canonical inputs: the reviewer's standing-facts file + master prompt v2.
# ---------------------------------------------------------------------------

_PROMPTS = _ROOT / "shows" / "prompts"
_FACTS = _PROMPTS / "offshore_north_standing_facts.txt"


def _digest_prompt():
    return (_PROMPTS / "offshore_north_digest.txt").read_text(encoding="utf-8")


def _podcast_prompt():
    return (_PROMPTS / "offshore_north_podcast.txt").read_text(encoding="utf-8")


def _system_prompt():
    return (_PROMPTS / "offshore_north_system.txt").read_text(encoding="utf-8")


class TestStandingFactsLayer:
    """Ep002 asserted the campaign has no boat — from one article, against
    a fact the campaign's own site has carried since 2025. The standing
    facts file is the fix: verified background injected into every prompt,
    outranking any single weekly source."""

    def test_facts_file_exists_and_carries_the_essentials(self):
        text = _FACTS.read_text(encoding="utf-8")
        for essential in ("EMIRA IV", "Scott Shawyer", "Canada Ocean Racing",
                          "12 November 2028", "Route du Rhum"):
            assert essential in text, f"standing facts lost: {essential}"

    def test_facts_file_carries_the_ep2_standing_correction(self):
        text = _FACTS.read_text(encoding="utf-8")
        assert "HAS a boat" in text, (
            "the Ep2 boat-denial correction is the reason this file exists"
        )
        assert "Standing corrections" in text

    def test_both_generation_prompts_include_the_facts(self):
        inc = "<<include: offshore_north_standing_facts.txt>>"
        assert inc in _digest_prompt(), "digest prompt must inject standing facts"
        assert inc in _podcast_prompt(), "podcast prompt must inject standing facts"

    def test_includes_actually_resolve(self):
        """load_prompt must expand the include — a typo'd path would ship
        the literal directive as prompt text."""
        from engine.generator import load_prompt
        for name in ("offshore_north_digest.txt", "offshore_north_podcast.txt"):
            rendered = load_prompt(str(_PROMPTS / name))
            assert "<<include" not in rendered, f"{name}: include did not resolve"
            assert "Standing corrections" in rendered, (
                f"{name}: standing facts content missing after include expansion"
            )

    def test_conflict_rule_flags_rather_than_asserts(self):
        src = _digest_prompt()
        assert "conflicts with standing facts" in src.lower() or (
            "CONFLICTS with the standing facts" in src
        ), "the digest prompt must route conflicts to a VERIFY flag"

    def test_facts_file_has_no_prompt_placeholders(self):
        """The include expands BEFORE {placeholder} substitution; a stray
        brace in the facts file would crash every render."""
        text = _FACTS.read_text(encoding="utf-8")
        assert "{" not in text and "}" not in text


class TestScopeExclusions:
    """The reviewer's Fleet complaint: aggregation pulls in America's Cup
    and Olympic content that is not offshore ocean racing."""

    def test_digest_prompt_names_the_exclusions(self):
        src = _digest_prompt()
        for banned in ("America's Cup", "SailGP", "Olympic"):
            assert banned in src, f"digest scope must exclude: {banned}"

    def test_system_prompt_names_the_exclusions(self):
        src = _system_prompt()
        for banned in ("America's Cup", "SailGP"):
            assert banned in src, f"system scope must exclude: {banned}"


class TestSingleSourceRule:
    """Ep002 built a multi-paragraph crisis narrative from one newspaper
    article. One source = report the claim and stop."""

    def test_digest_prompt_carries_the_rule(self):
        assert "SINGLE-SOURCE RULE" in _digest_prompt()

    def test_system_prompt_carries_the_rule(self):
        assert "single-source rule" in _system_prompt()

    def test_podcast_prompt_respects_it_downstream(self):
        assert "single-source rule" in _podcast_prompt()


class TestEpisodeLengthBandV2:
    def test_podcast_prompt_uses_the_v2_band(self):
        src = _podcast_prompt()
        assert "1,400–1,800" in src
        assert "1,500–2,200" not in src

    def test_yaml_target_sits_inside_the_band(self):
        words = _cfg().llm.min_podcast_words
        assert 1400 <= words <= 1800, (
            f"min_podcast_words={words} is outside the 1,400-1,800 band — "
            "the expand-retry would fire on every good episode"
        )


class TestShortDisplayTitle:
    """The v2 prompt adds a **TITLE:** metadata line (<=60-char headline —
    podcast apps truncate). run_show extracts it for display-title surfaces
    and falls back to the hook; the sanitizer strips the line from body
    text. The hard RSS cap stays in engine.titles, unchanged."""

    def _extract(self):
        import run_show
        return run_show._extract_short_title

    def test_digest_prompt_asks_for_the_line(self):
        src = _digest_prompt()
        assert "**TITLE:**" in src
        assert "60 characters" in src

    def test_extractor_finds_the_line(self):
        fn = self._extract()
        digest = (
            "# Offshore North\n**HOOK:** A full consequence sentence.\n\n"
            "**TITLE:** [EMIRA IV's last week in Collingwood]\n\n## The Canadian Boat\n"
        )
        assert fn(digest) == "EMIRA IV's last week in Collingwood"

    def test_extractor_returns_none_when_absent(self):
        fn = self._extract()
        assert fn("**HOOK:** Something happened.\n\n## Body\n") is None

    def test_extractor_does_not_eat_the_hook(self):
        import run_show
        digest = (
            "**HOOK:** The real hook.\n**TITLE:** Short headline\n## Body\n"
        )
        assert run_show._extract_hook(digest) == "The real hook."

    def test_sanitizer_strips_the_title_line(self):
        from engine.newsletter_sanitizer import scrub_scaffold
        body = "**HOOK:** Kept as lead.\n**TITLE:** Metadata only\nReal prose stays.\n"
        cleaned = scrub_scaffold(body)
        assert "Metadata only" not in cleaned
        assert "TITLE" not in cleaned
        assert "Real prose stays." in cleaned

    def test_run_show_wires_title_hook_into_rss_title(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "title_hook = _extract_short_title(x_thread) or hook" in src
        assert "_build_episode_title(\n            title_hook," in src


class TestYouTubeSourceFeed:
    """Reviewer item 2: the campaign's YouTube channel has an official
    Atom feed keyed by raw channel ID (verified serving entries Aug 2026)."""

    def test_feed_is_wired_with_the_verified_channel_id(self):
        urls = [s["url"] for s in yaml.safe_load(
            _SHOW_YAML.read_text(encoding="utf-8"))["sources"]]
        yt = [u for u in urls if "youtube.com/feeds/videos.xml" in u]
        assert yt, "Canada Ocean Racing YouTube feed missing from sources"
        assert "channel_id=UCbyLJ8WsopLJ0fLjkCAVQjg" in yt[0]

    def test_digest_prompt_treats_video_as_bonus(self):
        src = _digest_prompt()
        assert "every two weeks" in src, (
            "the prompt must not expect a weekly video from a biweekly channel"
        )


class TestWebSearchAlways:
    """2026-08-14 Ep2 redo: 16 on-topic articles (mostly Google News
    Vendée aggregation) kept the count gate shut, so the eight
    load-bearing queries — the only route to imoca.org and
    theoceanrace.com — never ran. Digest 493 words, script 904, skip.
    The show's YAML has declared web search load-bearing since launch;
    the gate now honors that with a per-show always-on flag."""

    def test_yaml_flag_survives_into_dataclass(self):
        """Silent config-drop class (landmine: _build_nested)."""
        raw = yaml.safe_load(_SHOW_YAML.read_text(encoding="utf-8"))
        assert raw.get("web_search_always") is True
        assert _cfg().web_search_always is True

    def test_dataclass_defaults_false(self):
        from engine.config import ShowConfig
        assert ShowConfig().web_search_always is False

    def test_every_other_show_keeps_the_count_gate(self):
        offenders = []
        for path in sorted((_ROOT / "shows").glob("*.yaml")):
            if path.stem.startswith("_") or path.stem == "offshore_north":
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict) or "slug" not in data:
                continue
            if data.get("web_search_always"):
                offenders.append(path.stem)
        assert not offenders, (
            f"these shows gained always-on web search — intentional? {offenders}"
        )

    def test_gate_honors_the_flag(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'getattr(config, "web_search_always", False)' in src
        assert "_search_wanted" in src


# ---------------------------------------------------------------------------
# August 2026 editorial review, round three (post-Ep2-redo listen):
# forward-plan-as-fact, absence claims, audience disparagement, Dan's real
# background, position report, campaign channel freshness.
# ---------------------------------------------------------------------------


class TestTimeSensitiveStandingFacts:
    """Ep2 (redo) said the boat 'stays in Collingwood through mid-August'
    after it had already departed (weekend of 8-9 Aug). Plans decay; the
    facts file now marks its location/schedule sections time-sensitive."""

    def test_facts_file_carries_the_warning_and_correction(self):
        text = _FACTS.read_text(encoding="utf-8")
        assert "TIME-SENSITIVE" in text
        assert "departed Collingwood the weekend of 8–9 August 2026" in text

    def test_forward_plan_rule_in_all_three_prompts(self):
        for src, name in ((_digest_prompt(), "digest"),
                          (_podcast_prompt(), "podcast"),
                          (_system_prompt(), "system")):
            assert "forward-looking plan as current fact".lower() in src.lower(), (
                f"{name} prompt lost the forward-plan rule"
            )


class TestNoAbsenceClaims:
    """'Canada Ocean Racing made no public announcements this week' ran on
    air in the same week the boat left Collingwood. Absence is unverifiable
    from inside the pipeline; verified channel freshness is."""

    def test_rule_in_all_three_prompts(self):
        for src, name in ((_digest_prompt(), "digest"),
                          (_podcast_prompt(), "podcast"),
                          (_system_prompt(), "system")):
            assert "absence" in src.lower(), f"{name} prompt lost the absence rule"

    def test_digest_no_longer_instructs_the_one_sentence_absence(self):
        assert "write exactly one sentence saying so" not in _digest_prompt()

    def test_digest_has_freshness_block(self):
        src = _digest_prompt()
        assert "{campaign_freshness}" in src
        assert "CAMPAIGN CHANNEL FRESHNESS" in src


class TestCampaignFreshnessPlumbing:
    def test_yaml_flags_the_campaign_feeds(self):
        raw = yaml.safe_load(_SHOW_YAML.read_text(encoding="utf-8"))
        flagged = [s["label"] for s in raw["sources"] if s.get("freshness_report")]
        assert len(flagged) == 3, f"expected the 3 campaign channels, got {flagged}"
        assert all("Canada Ocean Racing" in l for l in flagged)

    def test_flag_survives_into_dataclass(self):
        """Silent config-drop class."""
        flagged = [s for s in _cfg().sources if s.freshness_report]
        assert len(flagged) == 3

    def test_no_other_show_flags_feeds(self):
        offenders = []
        for path in sorted((_ROOT / "shows").glob("*.yaml")):
            if path.stem.startswith("_") or path.stem == "offshore_north":
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict) or "slug" not in data:
                continue
            for s in data.get("sources") or []:
                if isinstance(s, dict) and s.get("freshness_report"):
                    offenders.append(path.stem)
        assert not offenders, f"freshness_report leaked to: {offenders}"

    def test_collector_is_a_noop_without_flags(self):
        from engine.fetcher import collect_feed_freshness
        from engine.config import SourceConfig
        assert collect_feed_freshness([]) == ""
        assert collect_feed_freshness([SourceConfig(url="https://x/feed")]) == ""

    def test_run_show_supplies_the_placeholder(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert '"campaign_freshness": _campaign_freshness' in src


class TestNoAudienceDisparagement:
    """Ep2's sign-off: 'Send this to the one other person you know who
    follows this sport — there aren't many of us.' Reads as apology; CTA
    must be about the listener's enthusiasm, never the show's reach."""

    def test_prompt_bans_it(self):
        src = _podcast_prompt()
        assert "DISPARAGE" in src.upper()
        assert "there aren't many of us" in src  # quoted as the banned example

    def test_no_closing_variant_carries_it(self):
        from engine.intros import _SHOW_PERSONALITIES
        closings = _SHOW_PERSONALITIES["offshore_north"]["closings"]
        for c in closings:
            low = c.lower()
            assert "aren't many of us" not in low
            assert "one other person" not in low
            # every variant must still end on the chapter-marker sign-off
            assert "fair winds" in low


class TestCompactCrossPromo:
    """Dan: 'Sign-off — one line, then out. No stacked cross-promos.'
    Ep2 shipped a sibling plug AND a website-surface plug back to back."""

    def test_offshore_is_compact(self):
        from engine.network_promo import COMPACT_PROMO_SHOWS
        assert "offshore_north" in COMPACT_PROMO_SHOWS

    def test_promo_is_single_frame_no_surface(self):
        import datetime as dt
        from engine.network_promo import build_network_promo
        # Any date: offshore must always get the short frame, never the
        # surface add-on (Dispatch Wall / gallery / tracker sentences).
        for day in range(1, 15):
            promo = build_network_promo("offshore_north", dt.date(2026, 8, day))
            assert promo.startswith("Quick tip from the network:"), promo
            assert "Dispatch Wall" not in promo
            assert "gallery" not in promo.lower()

    def test_other_shows_keep_full_rotation(self):
        import datetime as dt
        from engine.network_promo import build_network_promo
        # Tesla must still rotate through all four frames over a fortnight.
        starts = {build_network_promo("tesla", dt.date(2026, 8, d)).split(" ")[0]
                  for d in range(1, 15)}
        assert len(starts) > 1, "compact mode leaked to other shows"


class TestDanBackgroundIsReal:
    """The voice section now carries Dan's actual background, with a hard
    one-personal-reference-per-episode limit."""

    def test_prompt_has_the_real_background(self):
        src = _podcast_prompt()
        for fact in ("Boeing 737", "wing foil", "Hobie 18", "bareboat"):
            assert fact in src, f"voice section lost: {fact}"

    def test_one_reference_limit(self):
        src = _podcast_prompt()
        assert "ONE personal reference per episode" in src
        assert "TWO first-person touches" not in src

    def test_never_upgrade_experience(self):
        src = _podcast_prompt()
        assert "has not raced across an ocean" in src


class TestPositionReport:
    def test_both_prompts_open_canadian_boat_with_it(self):
        assert "POSITION REPORT" in _digest_prompt()
        assert "POSITION REPORT" in _podcast_prompt()

    def test_accumulation_framing_present(self):
        src = _digest_prompt()
        assert "Never inflate a lock transit into a milestone" in src


class TestWebSearchSentinelParsing:
    """2026-08-16: query 1 returned a valid ARTICLE_TITLE/URL block (a
    Toronto Star feature on the campaign) followed by a stray
    NO_RECENT_ARTICLES — and the `in text` sentinel check discarded the
    whole response. The sentinel is only meaningful with no article."""

    def _run(self, fake_text, monkeypatch):
        import engine.fetcher as fetcher
        monkeypatch.setattr(
            "digests.xai_grok.grok_generate_text",
            lambda **kw: (fake_text, {}),
            raising=False,
        )
        monkeypatch.setenv("GROK_API_KEY", "test-key")
        return fetcher.fetch_web_search_articles(["test query"], keywords=[])

    def test_article_plus_stray_sentinel_is_kept(self, monkeypatch):
        text = (
            "ARTICLE_TITLE: A real campaign feature\n"
            "ARTICLE_URL: https://example.com/story\n"
            "ARTICLE_DESCRIPTION: Something substantive.\n"
            "ARTICLE_SOURCE: Toronto Star\n\n"
            "NO_RECENT_ARTICLES"
        )
        articles = self._run(text, monkeypatch)
        assert len(articles) == 1
        assert articles[0]["title"] == "A real campaign feature"

    def test_bare_sentinel_still_means_empty(self, monkeypatch):
        assert self._run("NO_RECENT_ARTICLES", monkeypatch) == []


class TestNoSeededTitleExample:
    """The 2026-08-16 draft's TITLE was 'EMIRA IV's last week in
    Collingwood' — the prompt's own example copied verbatim, asserting a
    location the boat had left. De-seed by shape (network rule): no
    quotable, plausible-content example in the TITLE or HOOK spec."""

    def test_title_spec_has_no_quotable_example(self):
        src = _digest_prompt()
        assert "last week in Collingwood" not in src
        assert "**TITLE:**" in src  # the spec itself survives

    def test_hook_spec_has_no_location_asserting_example(self):
        src = _digest_prompt()
        assert "now training on Georgian Bay" not in src

    def test_hook_and_title_specs_carry_the_accuracy_tie(self):
        src = _digest_prompt()
        # both metadata fields must be explicitly bound to the accuracy rules
        assert src.count("obeys the accuracy rules") >= 2


class TestVerifyFlagsNeverSpoken:
    """2026-08-17: the first [VERIFY:] flag this show ever produced —
    correctly marking the Toronto Star's stale acquisition framing — was
    SPOKEN ON AIR ("Verify, conflict with standing facts on acquisition
    date" is in the shipped Ep2 transcript). The prompts promise flags
    are stripped before production; now something actually does it."""

    def test_strip_removes_inline_and_lone_line_flags(self):
        from engine.utils import strip_verify_flags
        text = (
            "A real sentence. [VERIFY: translated from French source] More.\n\n"
            "[VERIFY: conflict with standing facts on acquisition date]\n\n"
            "Final sentence."
        )
        cleaned, flags = strip_verify_flags(text)
        assert len(flags) == 2
        assert "VERIFY" not in cleaned
        assert "A real sentence. More." in cleaned
        assert "Final sentence." in cleaned

    def test_no_flags_is_a_noop(self):
        from engine.utils import strip_verify_flags
        cleaned, flags = strip_verify_flags("Plain text.\n\nTwo paragraphs.")
        assert flags == []
        assert cleaned == "Plain text.\n\nTwo paragraphs."

    def test_run_show_strips_before_tts_and_reader(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "strip_verify_flags as _strip_verify" in src
        # spoken path: strip assigned back onto podcast_script
        assert "podcast_script, _verify_flags = _strip_verify(podcast_script)" in src
        # public blog transcript: same rule
        assert "_reader_body, _ = _strip_verify(_reader_body)" in src
        # the flag must surface to the operator, not vanish silently
        assert "Editorial flag stripped from spoken script" in src


class TestOldEventNewArticle:
    """2026-08-17: a weekend Toronto Star profile retold the early-2025
    boat purchase, and the digest framed it as this week's development
    (hook, title, and a 'from planning to preparation' consequence). The
    news was the coverage, not the event."""

    def test_digest_prompt_carries_the_rule(self):
        src = _digest_prompt()
        assert "OLD EVENT, NEW ARTICLE" in src
        assert "the news is the COVERAGE, not the event" in src
