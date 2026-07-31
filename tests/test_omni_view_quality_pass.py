"""Drift guards for the June 10 2026 Omni View quality pass
(docs/reviews/omni_view_review_2026_06_10.md) — the same review process as
the Tesla flagship pass, the four-show pass, and the env_intel pass, applied
to a show that was missed in every prior chapter / length / expand round.

Pins:
* chapter `where` positional anchors (Introduction=start, Tomorrow
  Teaser/Closing=end) — the Tesla chapter-bug class;
* the Closing chapter pattern matches BOTH closing-pool variants from
  engine.intros (the dominant "That wraps up today's Omni View…" variant
  previously matched NO pattern — 7 of the last 10 episodes shipped with
  no Closing chapter, the MAB orphan-closing bug);
* the "Understanding the Issue" pattern matches the real spoken deep-dive
  opener so the deep dive gets its own chapter AND the auto-segment
  garbage-title fallback stops firing (Ep061 shipped a chapter literally
  titled "Knowing this, when you hear claims that the system worked…");
* parse_chapters on every recent committed script produces a Closing
  chapter and no sentence-fragment chapter titles;
* the steel-man scaffolding tic is attacked at the prompt root — the
  digest no longer seeds the literal "The strongest case for X rests on…"
  lead-in (it shipped 12-20× per episode), the anonymous "one side / the
  other side / advocates on each side" frame is banned in both prompts,
  and the prompt caps "the strongest case" at once;
* one unified podcast length target (the prompt had demanded "8-12
  minutes", "at least 2000 words", and "40+ sentences" at once) plus the
  podcast_expand_below_target opt-in the June network pass missed.
"""

from __future__ import annotations

import re
import sys
import glob
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.intros import _SHOW_PERSONALITIES  # noqa: E402

_YAML = _ROOT / "shows/omni_view.yaml"
_DIGEST_PROMPT = _ROOT / "shows/prompts/omni_view_digest.txt"
_PODCAST_PROMPT = _ROOT / "shows/prompts/omni_view_podcast.txt"


def _cfg():
    return yaml.safe_load(_YAML.read_text(encoding="utf-8"))


def _markers():
    return {m["title"]: m for m in _cfg()["chapters"]["section_markers"]}


# ---------------------------------------------------------------------------
# Chapter positional anchors + pattern coverage
# ---------------------------------------------------------------------------

class TestChapterAnchors:
    def test_introduction_anchored_to_start(self):
        assert _markers()["Introduction"].get("where") == "start"

    def test_teaser_and_closing_anchored_to_end(self):
        by = _markers()
        assert by["Closing"].get("where") == "end"
        assert by["Tomorrow Teaser"].get("where") == "end"

    def test_closing_pattern_matches_both_closing_pool_variants(self):
        regex = re.compile(_markers()["Closing"]["pattern"], re.IGNORECASE)
        closings = _SHOW_PERSONALITIES["omni_view"]["closings"]
        assert closings, "omni_view must have closing-pool variants"
        for closing in closings:
            assert regex.search(closing), (
                f"Closing chapter pattern does not match closing-pool "
                f"variant: {closing[:80]!r}"
            )

    def test_deep_dive_pattern_matches_real_openers(self):
        regex = re.compile(_markers()["Understanding the Issue"]["pattern"],
                           re.IGNORECASE)
        # The actual spoken deep-dive openers seen across Ep069-077.
        for opener in (
            "Now, to really understand this story, there is something most coverage leaves out.",
            "Now, to really understand the tariff proposal, there is an administrative sequence most headlines leave out.",
            "To understand the defence spending announcement more fully, most coverage treats it as simple.",
            "To understand the Hormuz situation more fully, the picture is layered.",
        ):
            assert regex.search(opener), f"deep-dive pattern missed: {opener!r}"


class TestRealScriptChapters:
    """parse_chapters on every recent committed _tts.txt must produce a
    Closing chapter and no sentence-fragment garbage titles."""

    def _scripts(self):
        files = sorted(glob.glob(str(_ROOT / "digests/omni_view/Omni_View_Ep*_tts.txt")))
        # Skip the weekly-recap episodes (different structure, no deep dive).
        return files[-10:]

    def test_every_recent_script_gets_a_closing_chapter(self):
        from engine.config import load_config
        from engine.chapters import parse_chapters
        import logging
        logging.disable(logging.CRITICAL)
        markers = load_config(str(_YAML)).chapters.section_markers
        scripts = self._scripts()
        assert scripts, "expected recent omni_view scripts on disk"
        missing = []
        for f in scripts:
            script = Path(f).read_text(encoding="utf-8")
            titles = [c.title for c in parse_chapters(script, markers, show_name="Omni View")]
            if "Closing" not in titles:
                missing.append(Path(f).name)
        assert not missing, f"episodes missing a Closing chapter: {missing}"

    def test_no_garbage_sentence_fragment_chapter_titles(self):
        """No sentence-fragment chapter titles on the path listeners get.

        2026-07-31: this used to re-parse each script WITHOUT digest
        headlines and assert the bare auto-segment fallback never emits a
        fragment — a property that fallback cannot guarantee by design
        (it truncates the segment's first sentence with an ellipsis), so
        the suite went red on Ep129 purely because that day's first
        sentences ran long. Production never runs that bare path: both
        run_show.py and engine/pipeline.py pass story_headlines from the
        digest, and the fallback only fires per-segment when no headline
        overlaps. So this now checks (a) the production-shaped parse and
        (b) the chapters files that actually shipped.
        """
        from engine.config import load_config
        from engine.chapters import parse_chapters
        from engine.grok_imagine import extract_story_headlines
        import json
        import logging
        logging.disable(logging.CRITICAL)
        markers = load_config(str(_YAML)).chapters.section_markers
        bad = []
        for f in self._scripts():
            script = Path(f).read_text(encoding="utf-8")
            digest_md = Path(f.replace("_tts.txt", ".md"))
            headlines = []
            if digest_md.exists():
                headlines = extract_story_headlines(
                    digest_md.read_text(encoding="utf-8"), max_count=12)
            for c in parse_chapters(script, markers, show_name="Omni View",
                                    story_headlines=headlines):
                if c.title.endswith("…") or len(c.title) > 60:
                    bad.append((Path(f).name, c.title))
        assert not bad, f"garbage sentence-fragment chapter titles: {bad}"

        # The listener-facing artifact: committed chapters files.
        shipped_bad = []
        for f in sorted(glob.glob(
                str(_ROOT / "digests/omni_view/chapters_ep*.json")))[-10:]:
            for c in json.loads(Path(f).read_text(encoding="utf-8")).get(
                    "chapters", []):
                title = c.get("title", "")
                if title.endswith("…") or len(title) > 60:
                    shipped_bad.append((Path(f).name, title))
        assert not shipped_bad, (
            f"fragment titles SHIPPED to listeners: {shipped_bad}")


# ---------------------------------------------------------------------------
# Steel-man scaffolding tic (prompt root cause)
# ---------------------------------------------------------------------------

class TestSteelManTemplate:
    def test_digest_does_not_seed_the_canonical_strongest_case_lead_in(self):
        # The prompt used to PRESCRIBE the literal lead-in
        #   Lead each with its best supporting reason ("The strongest case
        #   for X rests on [specific value / mechanism / evidence]…")
        # which shipped 5-7×/digest → 12-20×/podcast. The phrase may now
        # appear ONLY inside the instruction that bans over-using it, never
        # as the prescribed lead-in template.
        text = _DIGEST_PROMPT.read_text(encoding="utf-8")
        assert 'best supporting reason ("The strongest case' not in text
        assert '[specific value / mechanism / evidence]' not in text

    def test_digest_caps_strongest_case_and_bans_anonymous_sides(self):
        text = _DIGEST_PROMPT.read_text(encoding="utf-8").lower()
        assert "at most once" in text
        assert "one side" in text and "the other side" in text  # named as banned

    def test_podcast_bans_the_one_side_frames_template(self):
        text = _PODCAST_PROMPT.read_text(encoding="utf-8").lower()
        assert "one side frames" in text  # mentioned only to ban it
        assert "advocates on each side" in text
        assert "banned" in text


# ---------------------------------------------------------------------------
# Unified length target + expansion opt-in
# ---------------------------------------------------------------------------

class TestLengthTarget:
    def test_podcast_prompt_has_no_contradictory_length_claims(self):
        text = _PODCAST_PROMPT.read_text(encoding="utf-8")
        assert "8–12 minute" not in text and "8-12 minute" not in text
        assert "at least 2000 words" not in text
        assert "1,700" in text  # the unified target

    def test_yaml_keeps_a_length_lever_and_raised_floor(self):
        # Superseded 2026-07-29 (cost-efficiency pass): the podcast-side
        # expansion retry is OFF wherever a digest-side lever exists. Over
        # 901 committed episodes 81% still shipped below target WITH it
        # running, and it padded by paraphrase-duplication; the July 18
        # playbook had already banned podcast-side length levers. The
        # length lever must now be the digest one — assert that, not the
        # retired flag. Guard: tests/test_cost_efficiency_pass.py.
        llm = _cfg()["llm"]
        assert llm.get("podcast_expand_below_target") is False
        assert llm.get("digest_expand_below_target") is True
        assert llm.get("min_podcast_words", 0) >= 1200


# ---------------------------------------------------------------------------
# July 18 2026 editorial realignment — drift guards
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = _ROOT / "shows/prompts/omni_view_system.txt"
_WEEKLY_PROMPT = _ROOT / "shows/prompts/omni_view_weekly.txt"


class TestEditorialRealignmentJuly18:
    """Pins the July 18 2026 realignment: 7-slot slate (no gossip /
    popular-media), worldwide scope, conditional steel-man, plain
    language, progress segment, de-seeded tics, rebalanced sources."""

    # -- digest prompt --------------------------------------------------

    def test_digest_has_no_gossip_or_popular_media_slots(self):
        text = _DIGEST_PROMPT.read_text(encoding="utf-8").lower()
        assert "top gossip stories" not in text
        assert "top popular media stories" not in text

    def test_digest_has_new_seven_slot_slate(self):
        text = _DIGEST_PROMPT.read_text(encoding="utf-8")
        assert "## Today's lead story (1)" in text
        assert "## Major world stories (3)" in text
        assert "## Economy, science & technology (2)" in text
        assert "## Progress watch (1)" in text

    def test_digest_has_lead_importance_and_breadth_rules(self):
        text = _DIGEST_PROMPT.read_text(encoding="utf-8")
        assert "need to have known" in text  # the year test
        assert "at most 2 stories from any single country" in text.lower()
        assert "NEVER a celebrity death" in text

    def test_digest_no_sides_on_tragedy(self):
        text = _DIGEST_PROMPT.read_text(encoding="utf-8").lower()
        assert "no sides on tragedy" in text
        assert "disasters, accidents, deaths" in text

    def test_digest_plain_language_layer(self):
        text = _DIGEST_PROMPT.read_text(encoding="utf-8").lower()
        assert "fourteen-year-old" in text
        assert "first use" in text

    def test_digest_steel_man_is_conditional_but_survives(self):
        # test_phase4_repositioning pins the literal STEEL-MAN string; the
        # realignment keeps it as the CONDITIONAL header.
        text = _DIGEST_PROMPT.read_text(encoding="utf-8")
        assert "STEEL-MAN THE DISAGREEMENT" in text
        assert "only for genuinely contested stories" in text

    def test_digest_bans_question_worth_considering(self):
        text = _DIGEST_PROMPT.read_text(encoding="utf-8").lower()
        assert '"the question worth considering" is banned' in text

    def test_digest_drama_hook_examples_gone(self):
        text = _DIGEST_PROMPT.read_text(encoding="utf-8")
        assert "openly at war" not in text
        assert "heavy casualties" not in text

    # -- podcast prompt -------------------------------------------------

    def test_podcast_example_no_longer_seeds_the_tics(self):
        text = _PODCAST_PROMPT.read_text(encoding="utf-8")
        # The old EXAMPLE story seeded both dominant shipped tics.
        assert "Host: What is interesting is" not in text
        assert "Host: The question worth considering:" not in text

    def test_podcast_audience_is_teen_to_senior(self):
        text = _PODCAST_PROMPT.read_text(encoding="utf-8").lower()
        assert "fourteen-year-old" in text

    def test_podcast_length_retry_deepens_not_adds(self):
        text = _PODCAST_PROMPT.read_text(encoding="utf-8")
        assert "COVER MORE STORIES" not in text
        assert "DEEPEN the slate" in text

    def test_podcast_seeds_progress_transitions(self):
        text = _PODCAST_PROMPT.read_text(encoding="utf-8").lower()
        assert "progress worth knowing" in text

    # -- system prompt --------------------------------------------------

    def test_system_prompt_no_longer_seeds_banned_tics(self):
        text = _SYSTEM_PROMPT.read_text(encoding="utf-8")
        assert "What's interesting here is" not in text
        assert "The question nobody's asking" not in text

    # -- weekly prompt --------------------------------------------------

    def test_weekly_has_progress_section(self):
        text = _WEEKLY_PROMPT.read_text(encoding="utf-8")
        assert "Progress This Week" in text

    # -- yaml -----------------------------------------------------------

    def test_yaml_daily_mail_removed_and_sources_unique(self):
        cfg = _cfg()
        urls = [s["url"] for s in cfg["sources"]]
        assert not any("dailymail" in u for u in urls)
        assert len(urls) == len(set(urls)), "duplicate feed URLs"

    def test_yaml_has_regional_balance_feeds(self):
        cfg = _cfg()
        labels = {s["label"] for s in cfg["sources"]}
        regional = {
            "BBC Africa", "BBC Asia", "BBC Latin America", "AllAfrica",
            "South China Morning Post", "Nikkei Asia",
            "The Hindu International", "Japan Times", "MercoPress",
        }
        assert len(labels & regional) >= 6, labels & regional

    def test_yaml_has_wire_proxies_and_wsj(self):
        cfg = _cfg()
        labels = {s["label"] for s in cfg["sources"]}
        assert "Reuters (via Google News)" in labels
        assert "AP (via Google News)" in labels
        assert "WSJ World" in labels

    def test_yaml_exclude_title_patterns_present_and_compile(self):
        cfg = _cfg()
        pats = cfg.get("exclude_title_patterns") or []
        assert len(pats) >= 5
        for p in pats:
            re.compile(p)

    def test_yaml_expansion_style_and_digest_floor(self):
        llm = _cfg()["llm"]
        assert llm.get("podcast_expansion_style") == "deepen"
        assert llm.get("digest_expand_below_target") is True
        assert llm.get("min_digest_words", 0) >= 1400

    def test_yaml_has_progress_watch_chapter_marker(self):
        cfg = _cfg()
        titles = [m["title"] for m in cfg["chapters"]["section_markers"]]
        assert "Progress Watch" in titles

    # -- engine ---------------------------------------------------------

    def test_generator_deepen_flavor(self):
        from engine.generator import _build_expansion_retry_prompt
        deepen = _build_expansion_retry_prompt(
            1000, 1700, "digest text", "script text", style="deepen",
        )
        assert "Do NOT add stories" in deepen
        assert "COVERING MORE STORIES" not in deepen
        # Legacy behavior untouched when style is unset.
        legacy = _build_expansion_retry_prompt(
            1000, 1700, "digest text", "script text",
        )
        assert "COVERING" in legacy

    def test_config_dataclass_has_expansion_style_field(self):
        # The silent config-drop class (June 2026 YouTube pass): a YAML key
        # the dataclass doesn't declare is discarded with only a warning.
        from engine.config import LLMConfig
        assert LLMConfig().podcast_expansion_style == ""

    def test_closings_still_match_closing_chapter_pattern(self):
        cfg = _cfg()
        closing_marker = next(
            m for m in cfg["chapters"]["section_markers"]
            if m["title"] == "Closing"
        )
        pat = re.compile(closing_marker["pattern"], re.IGNORECASE)
        for closing in _SHOW_PERSONALITIES["omni_view"]["closings"]:
            assert pat.search(closing), closing[:60]

    # -- shipped-transcript tic ceilings (post-realignment episodes) -----

    def test_post_realignment_transcripts_drop_the_tics(self):
        """Gated on episode number: only episodes shipped AFTER the
        realignment (Ep115+) are held to the new ceilings. Skips cleanly
        until such episodes exist on disk."""
        import pytest as _pytest
        files = sorted(glob.glob(str(
            _ROOT / "digests/omni_view/Omni_View_Ep*_tts.txt")))
        post = []
        for f in files:
            m = re.search(r"Ep(\d+)_", f)
            if m and int(m.group(1)) >= 115:
                post.append(f)
        if not post:
            _pytest.skip("no post-realignment episodes shipped yet")
        for f in post:
            text = Path(f).read_text(encoding="utf-8").lower()
            assert "the question worth considering" not in text, f
            assert "both sides agree" not in text, f
