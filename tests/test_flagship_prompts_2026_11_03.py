"""Nov 3 2026 — write for the ear, by shape (the six-month review's flagship
prompt pass; register ``flagship-prompts-by-shape-2026-11-03``).

Four measured defects shared one surface, the flagship prompts:

* the grok-4.6 script arms grew an attribution TAIL (``script_attribution_tail_pct``
  Tesla median 10.3%, SpaceX 5.0, FF 7.2 against 0 on the grok-4.7 cohort,
  on the SAME ``content_discipline`` include) — the shared sentence paragraph
  read as a count ("a story with five facts gets five sentences") and the
  outlet rule said "first or second sentence" without saying where INSIDE it;
* the "at least two and at most six" item floors, Tesla's thin-day "4-6
  sentences per story instead of 2-4" and the LENGTHEN-the-essay clauses
  manufactured the padding the Repetitive audit class hears (Tesla Ep653
  item 4: one fact, three sentences), while the shared spoken rule says a
  one-fact story is cut, never padded;
* SpaceX's and Tesla's referent-less sentences were born in items summarised
  from X posts (X-only items 16% / 22% against <= 5% elsewhere); Community
  Buzz filled a "4-5 fresh items" quota with an SR-71 museum clip and an
  STS-52 anniversary; Tesla and SpaceX were the two flagship digests without
  ``_shared/interesting_first.txt``; ``engine.fetcher._x_post_entry`` sliced
  ``desc[:100]`` — a title slice outside ``engine/titles.py`` — and kept a
  whole 60-word post as a heading when it came WITH a title (M&A Ep222);
* two prompts REQUIRED the deep dive to re-tell a body item ("Pick ONE item
  from the Top 12 and go DEEPER"), two wrote the explainer "from YOUR OWN
  knowledge" (Omni View told listeners on Nov 2 that governments preload
  alert apps — untrue of Ukraine's Air Alert, with no ledger entry), and
  MAG 7's Thread asked for each company's numbers AGAIN.

Every edit is by SHAPE, with no quotable specimen (three generations of tics
came from supplied sentences). The nine phrases earlier passes pinned stay
verbatim, and this file pins the new shapes the same way.
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROMPTS = ROOT / "shows" / "prompts"


def _prompt(rel: str) -> str:
    return (PROMPTS / rel).read_text(encoding="utf-8")


def _every_prompt_file():
    return sorted(glob.glob(str(PROMPTS / "**" / "*.txt"), recursive=True))


# --------------------------------------------------------------------------
# (1) the shared sentence paragraph, by shape
# --------------------------------------------------------------------------
class TestTheSharedSentenceParagraph:
    PINNED = (
        # tests/test_delivery_pass_2026_09_05.py
        "EVERY fact is spoken", "floor, not a menu",
        # tests/test_transitions_and_length_2026_10_14.py
        "never a sentence that opens on the outlet's name",
        "Consecutive stories never open on the same shape",
        # tests/test_slate_2026_10_12.py
        "never its web address", "never carries a fact held back from a story already told",
        # tests/test_slate_2026_10_21.py
        "named once for the run", "never wedged into a sentence after its subject",
        # tests/test_listener_noise_2026_10_10.py
        "attention is not a fact about the story", "names its subject",
    )

    def test_the_nine_pinned_phrases_survive_verbatim(self):
        cd = _prompt("_shared/content_discipline.txt")
        for phrase in self.PINNED:
            assert phrase in cd, phrase
        assert "Reuters reports" not in cd
        assert "it is spoken only once per intervention" not in cd  # Longevity owns it

    def test_a_sentence_is_a_fact_and_its_relation_never_a_count(self):
        cd = _prompt("_shared/content_discipline.txt")
        # The words that read as a count are gone.
        assert "five facts gets five sentences" not in cd
        assert "one sentence per distinct fact" not in cd
        # The shape: a fact AND its relation; a number with what it measures;
        # length follows weight.
        assert "its relation to the one before" in cd
        assert "cause, contrast, sequence or scale" in cd
        assert "the thing it measures and what it compares to" in cd
        assert "Sentence length varies with the fact's weight" in cd
        # The ceiling and the cut rule stay.
        assert "At most six sentences; a story with fewer than two concrete facts is cut, never padded" in cd

    def test_the_outlet_sits_inside_the_first_fact_sentence_and_never_ends_it(self):
        cd = _prompt("_shared/content_discipline.txt")
        assert "INSIDE the sentence that carries the story's first fact" in cd
        assert "A sentence never ENDS on who reported it" in cd
        assert "in the story's first or second sentence" not in cd
        # Still once per story, still never an opener.
        assert "named once per story" in cd


# --------------------------------------------------------------------------
# (2) the "1 to 2 sentences per line" rule and the quotable attribution
# --------------------------------------------------------------------------
class TestTheLineRuleAndTheSpecimens:
    RETIRED_SPECIMENS = (
        "according to Teslarati",
        "Pick ONE item from the Top 12 and go DEEPER",
        "uses YOUR OWN knowledge",
        "creates natural pauses in the audio",
        "natural TTS pauses",
        # Nov 3 2026: Omni View's script prompt quoted the attribution tag
        # the shared paragraph retires (the twin of "according to Teslarati").
        "Reuters reports",
        "according to the BBC",
    )

    def test_no_podcast_prompt_counts_sentences_per_line(self):
        hits = []
        for path in glob.glob(str(PROMPTS / "*_podcast.txt")) + glob.glob(
                str(PROMPTS / "_shared" / "*podcast*.txt")):
            for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
                if "sentences per" in line:
                    hits.append(f"{Path(path).name}:{n}")
        assert hits == [], hits

    @pytest.mark.parametrize("specimen", RETIRED_SPECIMENS)
    def test_no_prompt_carries_a_retired_specimen(self, specimen):
        hits = [Path(p).name for p in _every_prompt_file()
                if specimen in Path(p).read_text(encoding="utf-8")]
        assert hits == [], (specimen, hits)

    def test_the_new_show_template_teaches_no_retired_rule(self):
        """``engine/show_scaffold.py`` writes every new show's podcast prompt
        from this template, so a rule retired from shows/prompts/ re-enters
        on the next scaffold unless the template drops it too."""
        tpl = (ROOT / "shows" / "templates" / "podcast.txt.template").read_text(encoding="utf-8")
        assert "sentences per" not in tpl
        for specimen in self.RETIRED_SPECIMENS:
            assert specimen not in tpl, specimen
        assert "A line break is not a pause" in tpl

    def test_a_line_is_a_paragraph_not_a_pause(self):
        for name in ("tesla_podcast.txt", "spacex_podcast.txt", "fascinating_frontiers_podcast.txt",
                     "planetterrian_podcast.txt", "omni_view_podcast.txt"):
            p = _prompt(name)
            assert "line is a paragraph" in p, name
            assert "A line break is not a pause" in p, name
        for name in ("ai_chips_podcast.txt", "mag7_podcast.txt", "longevity_podcast.txt",
                     "peptides_podcast.txt", "vancouver_podcast.txt", "collingwood_podcast.txt",
                     "omni_view_world_podcast.txt", "prediction_markets_podcast.txt",
                     "_shared/omni_desk_podcast_body.txt"):
            assert "a line break is not a pause" in _prompt(name), name

    def test_tesla_and_spacex_name_the_source_inside_the_first_fact_sentence(self):
        tesla = _prompt("tesla_podcast.txt")
        spacex = _prompt("spacex_podcast.txt")
        for p in (tesla, spacex):
            assert "inside the sentence that carries the story's first fact" in p
            assert "according to NASASpaceflight" not in p
        # The spoken floors became "as many as the facts".
        assert "at least two, at most six" not in tesla and "at least two, at most six" not in spacex
        assert "(at most six — see CONTENT DISCIPLINE below)" in tesla
        assert "(at most six; see CONTENT DISCIPLINE below)" in spacex
        # Oct 14 pin: never a bare "(up to six sentences)" cap on the essay.
        assert "(up to six sentences)" not in tesla


# --------------------------------------------------------------------------
# (3) the item specs: as many sentences as the facts, the outlet in the heading
# --------------------------------------------------------------------------
class TestTheItemSpecs:
    SPECS = ("tesla_digest.txt", "spacex_digest.txt", "fascinating_frontiers_digest.txt",
             "planetterrian_digest.txt", "models_agents_digest.txt")

    def test_no_prompt_keeps_the_two_sentence_floor(self):
        hits = [Path(p).name for p in _every_prompt_file()
                if "at least two and at most six" in Path(p).read_text(encoding="utf-8")]
        assert hits == []

    @pytest.mark.parametrize("name", SPECS)
    def test_each_spec_says_as_many_as_the_facts_and_where_the_outlet_lives(self, name):
        d = _prompt(name)
        assert "as many sentences as the source gives distinct facts, at most six" in d
        assert "a one-fact story is one sentence, or goes to Also Today" in d
        assert "no body sentence ends on the outlet's name" in d

    def test_models_agents_applies_it_to_all_three_item_sections(self):
        d = _prompt("models_agents_digest.txt")
        assert d.count("a one-fact story is one sentence, or goes to Also Today") == 3

    def test_the_heading_format_is_untouched(self):
        # The **Title: Outlet** heading is structural (engine.digest_lint._ITEM_HEAD_RE).
        from engine.digest_lint import _ITEM_HEAD_RE
        assert _ITEM_HEAD_RE.match("1. **Cybercab pack keeps room for LFP cells: Teslarati**")
        assert "**Title (One Line): Source Name**" in _prompt("tesla_digest.txt")
        assert "**Title (<= 12 words) — Source Name**" in _prompt("fascinating_frontiers_digest.txt")

    def test_thin_days_ship_shorter_never_longer_items(self):
        for name in ("tesla_digest.txt", "fascinating_frontiers_digest.txt", "planetterrian_digest.txt"):
            d = _prompt(name)
            assert "sentences per story instead of" not in d, name
            assert "a thin day ships a shorter digest" in d, name

    def test_the_essay_is_not_a_length_lever(self):
        for name in ("tesla_digest.txt", "fascinating_frontiers_digest.txt", "planetterrian_digest.txt"):
            d = _prompt(name)
            assert "LENGTHEN" not in d, name
            assert "grows only by figures from its fetched article" in d, name
        # Oct 14 pins stay: the deep dives keep their length spec.
        for name in ("fascinating_frontiers_digest.txt", "planetterrian_digest.txt"):
            assert "450-550 words" in _prompt(name)
        ma = _prompt("models_agents_digest.txt")
        assert "LENGTHEN" not in ma and "grows only by figures from its fetched page" in ma


# --------------------------------------------------------------------------
# (4) X-post items get a shape; Tesla and SpaceX select interesting-first
# --------------------------------------------------------------------------
class TestXPostItems:
    X_SHAPE = ("states who posted and what the post itself says, in the post's own figures",
               "a sentence that draws a consequence the post did not state is not written",
               "depends on a picture, a reply thread or a quoted post is one sentence in Also Today")

    def test_tesla_and_spacex_include_interesting_first_above_the_selection_rules(self):
        for name, marker in (("tesla_digest.txt", "### ARTICLE SELECTION"),
                             ("spacex_digest.txt", "Select only stories that are SPECIFIC")):
            d = _prompt(name)
            inc = d.index("<<include: _shared/interesting_first.txt>>")
            assert inc < d.index(marker), name

    def test_the_x_item_shape_on_both_flagships(self):
        for name in ("tesla_digest.txt", "spacex_digest.txt"):
            d = _prompt(name)
            for phrase in self.X_SHAPE:
                assert phrase in d, (name, phrase)

    def test_tesla_takeover_is_up_to_five(self):
        d = _prompt("tesla_digest.txt")
        assert "identify 5" not in d and "identify up to five" in d
        # The Oct 10 / Oct 11 pins: the section header and the checklist say "up to 5".
        assert "up to 5 fresh items" in d
        assert "Tesla X Takeover section included with up to 5" in d
        assert "- Community reactions to major Tesla news" not in d
        assert "2-4 sentences of concrete facts" not in d
        assert "as many sentences as the post gives distinct facts, at most four" in d

    def test_spacex_buzz_is_up_to_four_at_both_sites_with_the_exclusions(self):
        d = _prompt("spacex_digest.txt")
        assert "4–5 fresh items" not in d and "4–5 items" not in d
        # The section list (production notes) and the section body both say it.
        assert d.lower().count("up to four") == 2
        assert "Never an anniversary, a birthday, a profile, or a museum or archive clip" in d

    def test_spacex_market_watch_note_carries_no_tense_of_its_own(self):
        p = _prompt("spacex_podcast.txt")
        assert "never a tense of its own on the quote" in p
        assert "the closing block carries the clock's verb" in p


class TestAWholePostIsNeverAHeading:
    def test_the_limit_lives_in_engine_titles(self):
        from engine import titles
        assert titles.X_ITEM_TITLE_MAX == 110
        assert "X_ITEM_TITLE_MAX" in titles.__all__

    def test_fetcher_has_no_title_slice_of_its_own(self):
        src = (ROOT / "engine" / "fetcher.py").read_text(encoding="utf-8")
        assert "desc[:100]" not in src
        assert src.count("clip_words(") >= 2

    def test_a_400_char_post_yields_a_word_safe_heading_at_both_sites(self):
        from engine.fetcher import _parse_url_extraction, _x_post_entry
        from engine.titles import X_ITEM_TITLE_MAX, clip_words, fits
        post = ("Karpathy says the tokenizer is the part everyone skips and the part that "
                "decides the bill: every sub token is a separate forward pass, so a word "
                "split four ways costs four times what a word split once costs, and the "
                "fix is in the vocabulary, not the model; the demo trains a two-layer "
                "model on a laptop and shows the gap in a single chart with the costs "
                "side by side, then reruns the same text through three public tokenizers "
                "and prints the token count each one produces.")
        assert len(post) >= 400
        e = _x_post_entry(title="", desc=post, url="https://x.com/karpathy/status/1", link="",
                          post_date="", label="Karpathy", handle="karpathy",
                          now_iso="2026-11-03T00:00:00+00:00")
        assert len(e["title"]) <= X_ITEM_TITLE_MAX and fits(e["title"], X_ITEM_TITLE_MAX)
        assert e["title"] == clip_words(post, X_ITEM_TITLE_MAX)
        assert e["title"].endswith("…") and not e["title"][:-1].endswith(" ")
        assert e["description"] == post  # the body keeps the whole post
        # A post that came WITH a long title is clipped the same way.
        e2 = _x_post_entry(title=post, desc="", url="https://x.com/karpathy/status/2", link="",
                           post_date="", label="Karpathy", handle="karpathy",
                           now_iso="2026-11-03T00:00:00+00:00")
        assert len(e2["title"]) <= X_ITEM_TITLE_MAX
        # The fallback URL parser clips through the same rule.
        text = f"- {post}\nhttps://x.com/karpathy/status/3\n"
        out = _parse_url_extraction(text, ["karpathy"], {"karpathy": "Karpathy"},
                                    "2026-11-03T00:00:00+00:00")
        assert out and len(out[0]["title"]) <= X_ITEM_TITLE_MAX
        assert out[0]["title"] == clip_words(out[0]["description"], X_ITEM_TITLE_MAX)

    def test_a_short_post_is_untouched(self):
        from engine.fetcher import _x_post_entry
        e = _x_post_entry(title="", desc="Booster 18 static fire complete.", url="https://x.com/s/status/4",
                          link="", post_date="", label="S", handle="s", now_iso="")
        assert e["title"] == "Booster 18 static fire complete."


# --------------------------------------------------------------------------
# (4b) reaction verbs widen only after the sweep
# --------------------------------------------------------------------------
class TestRepliesOnlyWidening:
    # The sweep's real matches (every committed _tts.txt and digest, Nov 3 2026).
    SWEPT = [
        "Commenters pointed to the Blackbird's maintenance intensity versus the goal of airline-style turnaround for Starship.",
        "Users discussed the implications of the July 16 target date appearing simultaneously in multiple independent reports.",
        "Responses pointed to museum replicas and educational suppliers.",
        "Commenters compared these profiles against current Falcon 9 RTLS constraints and Starship's higher energy requirements.",
        "Commenters noted the lease avoids upfront capital but removes residual value after twelve years.",
        "Users noted the dates remain provisional and subject to slips.",
        "Commenters discussed the trade-offs between reliability and capability in early flight computers.",
        "Replies weighed in on whether the tiles had been replaced.",
        "Commenters contrasted the tower catch with the Shuttle-era crawler.",
    ]
    KEPT = [
        # A named person's words are never a reaction report.
        "Musk noted that the factory would open in May.",
        "Shotwell compared the pad turnaround with Falcon 9's record.",
        "Gerstenmaier pointed to the heat-shield data as the open question.",
        # The noun as an object or inside the sentence, not the subject.
        "The team compared replies from two hundred users before shipping the fix.",
        "Regular users keep getting surprised, because the replies finally feel witty instead of stiff.",
        "The committee will take views from experts and people with a stake.",
    ]

    @pytest.mark.parametrize("sentence", SWEPT)
    def test_the_swept_shapes_are_removed(self, sentence):
        from engine.listener_noise import clean_sentence
        assert clean_sentence(sentence) == ("", True)

    @pytest.mark.parametrize("sentence", KEPT)
    def test_a_named_person_or_an_object_noun_is_kept(self, sentence):
        from engine.listener_noise import clean_sentence
        assert clean_sentence(sentence) == (sentence, False)

    def test_the_subject_list_did_not_widen(self):
        from engine.listener_noise import _REPLIES_ONLY
        assert _REPLIES_ONLY.pattern.startswith(
            r"^(?:replies|commenters|followers|users|other users|responses)\s+")


# --------------------------------------------------------------------------
# (5) deep dives are a second story from a fetched page
# --------------------------------------------------------------------------
class TestDeepDivesAreASecondStory:
    def test_ff_and_pt_spotlights_are_a_story_the_top_12_does_not_carry(self):
        for name in ("fascinating_frontiers_digest.txt", "planetterrian_digest.txt"):
            d = _prompt(name)
            assert "A second story, not a second pass" in d, name
            assert "the Top 12 does NOT carry" in d, name
            assert "article whose full text is printed above" in d, name
            assert "then its Source line" in d, name
            # The validator needs the section every day (min_items=1), so a
            # thin day fills the slot instead of omitting it.
            assert "the slot takes the strongest remaining story" in d, name
            assert "go DEEPER" not in d, name

    def test_ov_and_ma_explainers_are_built_from_one_fetched_page(self):
        for name in ("omni_view_digest.txt", "models_agents_digest.txt"):
            d = _prompt(name)
            assert "built from ONE fetched background page" in d, name
            assert "named in the sentence that first uses it" in d, name
            assert "it is the host's own explanation" in d, name
            assert "ends on that page's Source line" in d, name
            assert "YOUR OWN knowledge" not in d, name

    def test_the_explainer_source_line_is_a_coverage_item(self):
        """Because the section now ends on a Source line, it enters the claims
        coverage floor with no claims code change (``_digest_items_with_source``
        counts every block carrying a Source)."""
        from engine.claims import _digest_items_with_source
        digest = (
            "## Understanding the Issue: How air-raid alerts reach a phone\n"
            "Ukraine's Air Alert app is built by a private developer, Ajax Systems, and the "
            "regional administrations push each alert, the Kyiv Independent explained in "
            "its 2024 guide to the system. The app does not come preloaded on any handset. "
            "Source: https://kyivindependent.com/air-alert-guide\n\n"
            "## Media-literacy note\nCheck two outlets.\n"
        )
        pairs = _digest_items_with_source(digest)
        assert any("Air Alert app" in first for first, _ in pairs), pairs

    def test_ov_context_block_carries_framing_only(self):
        d = _prompt("omni_view_digest.txt")
        assert "framing, disagreement and attribution only" in d
        assert "a fact already stated under What happened is never written again here" in d

    def test_mag7_thread_part_three_never_restates_the_numbers(self):
        d = _prompt("mag7_digest.txt")
        assert "without re-stating a number already given in the first part (one owner per fact)" in d

    def test_mit_explainer_names_its_figures_source(self):
        d = _prompt("modern_investing_digest.txt")
        assert "a number you would supply from memory is left out" in d
        assert "the host's own account of how markets work" in d


# --------------------------------------------------------------------------
# (6) M&A groups preprints; (7) evidence levels once per story
# --------------------------------------------------------------------------
class TestAlsoTodayAndEvidenceLevels:
    def test_models_agents_groups_preprints_by_theme_before_the_run(self):
        d = _prompt("models_agents_digest.txt")
        assert "grouped before it is written" in d
        assert "never one line per paper" in d
        # The shared snippet is unchanged — the grouping is this show's clause.
        assert "grouped" not in _prompt("_shared/also_today.txt")

    def test_evidence_level_once_per_story_on_the_health_shows(self):
        for name in ("longevity_podcast.txt", "peptides_podcast.txt"):
            p = _prompt(name)
            assert "Every finding carries its evidence level" not in p, name
            assert "said once per story" in p, name
            assert "the regulator sentence only where a listener could buy or take the thing" in p, name
            assert "each with its evidence level" not in p, name
        # The pinned line the Oct 21 pass left with Longevity stays.
        assert "Say it once per intervention" in _prompt("longevity_system.txt")


# --------------------------------------------------------------------------
# every prompt still renders
# --------------------------------------------------------------------------
class TestPromptsStillRender:
    class _Forgiving(dict):
        def __missing__(self, key):
            return ""

    @pytest.mark.parametrize("name", [
        "tesla_digest.txt", "tesla_podcast.txt", "spacex_digest.txt", "spacex_podcast.txt",
        "fascinating_frontiers_digest.txt", "fascinating_frontiers_podcast.txt",
        "planetterrian_digest.txt", "planetterrian_podcast.txt", "omni_view_digest.txt",
        "omni_view_podcast.txt", "models_agents_digest.txt", "models_agents_podcast.txt",
        "mag7_digest.txt", "longevity_podcast.txt", "peptides_podcast.txt",
        "modern_investing_digest.txt",
    ])
    def test_renders_with_the_includes_resolved(self, name):
        from engine.generator import load_prompt
        text = load_prompt(str(PROMPTS / name), self._Forgiving())
        assert "<<include:" not in text
        if name in ("tesla_digest.txt", "spacex_digest.txt"):
            assert "INTERESTING FIRST" in text
