"""Drift guards for the Sep 5 2026 network delivery review.

The operator's complaint: the flagships read as "narrative driven with
repetition that seems redundant". Four transcript audits traced it to
four mechanisms, each now guarded here:

1. The script stage copied the digest nearly verbatim, so a digest
   duplicate was an audio duplicate — `engine.digest_overlap` drops
   cross-section repeats before the script sees the digest.
2. Nothing measured density; `engine.script_audit` now records
   digest-verbatim share, repeated numeric facts, filler shapes and hook
   restatement per episode.
3. The memory section injected a MANDATORY "1-2 sentences of where this
   fits in the arc" on every story, contradicting the one-callback budget.
4. Prompts supplied worked example sentences that shipped verbatim.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import digest_overlap as do  # noqa: E402
from engine import script_audit as sa  # noqa: E402

TESLA_SHAPED = """# Tesla Shorts Time
**Date:** 2026-09-02
**REAL-TIME TSLA price:** $340.00 +1.2%

**Lexus is building a gigacast EV in China by twenty twenty-seven.**

━━━━━━━━━━━━━━━━━━━━
### Top 12 News Items
1. **Lexus will build an EV in China by 2027 using gigacasting tech: Top Gear Philippines**
   Lexus confirmed plans for a next-generation electric vehicle built in China starting 2027. The model will adopt gigacasting for the rear underbody, following Tesla's Model Y approach. Toyota executives said the Shanghai plant will be the first to use the process. Analysts at Bernstein expect the technique to cut part count by seventy percent.
   Source: https://www.topgear.com.ph/news/lexus-china-ev-gigacasting?utm_source=rss

2. **Tesla Now Uses Grok Think Fast 2.0 With Summer Update: Not A Tesla App**
   The Summer 2026 software update, version 2026.26 and later, introduces Grok Think Fast 2.0 for in-cabin voice interaction. Owners report faster responses to navigation and climate requests. The update also adds a new vehicle icon on the mini-map.
   Source: https://www.notateslaapp.com/news/grok-think-fast-summer-update

3. **Austrian Company Builds Automated NACS Charging Dock for Tesla Robotaxis: Not A Tesla App**
   An Austrian supplier demonstrated an automated dock that plugs a NACS connector into a parked robotaxi without a human. The prototype handles a Model Y in ninety seconds and is being pitched to fleet operators.
   Source: https://www.notateslaapp.com/news/austrian-nacs-dock

━━━━━━━━━━━━━━━━━━━━
## Tesla X Takeover: What's Hot Right Now
1. **Lexus adopts gigacasting for 2027 China-built EV** - Lexus confirmed its first use of large-scale casting on a next-generation electric vehicle built in China from 2027, adopting the Model Y rear underbody approach at its Shanghai plant, with Bernstein analysts expecting a seventy percent cut in part count.
2. **Grok Think Fast 2.0 rolls out in Summer 2026 update** - Vehicles on software version 2026.26 and later get Grok Think Fast 2.0 for in-cabin voice interaction, with owners reporting faster navigation and climate responses.
3. **Cybertruck owners report new wiper firmware** - A firmware note describes a revised wiper cadence for heavy rain on the Cybertruck, spotted by owners on the twenty twenty-six point twenty-six build.

━━━━━━━━━━━━━━━━━━━━
## Short Spot
**Automated NACS dock arrives before Tesla's own robotaxi solution: Not A Tesla App**
A third party shipped robotaxi charging automation before Tesla did, which raises the question of who owns the fleet-charging layer.
Source/Post: https://www.notateslaapp.com/news/austrian-nacs-dock

━━━━━━━━━━━━━━━━━━━━
### Tesla First Principles

Gigacasting is not a single machine but a supply-chain decision. The magic-wand number for a rear underbody is the aluminium alone. Every cast that scraps is a full part lost, not a stamping.

━━━━━━━━━━━━━━━━━━━━
Feedback welcome at @teslashortstime.
"""


class TestDigestCrossSectionDedupe:
    def test_drops_url_headline_and_body_duplicates_and_renumbers(self):
        result = do.dedupe_cross_section_items(TESLA_SHAPED, show_name="tesla")
        reasons = {d.title[:20]: d.reason for d in result.removed}
        assert result.count == 3, reasons
        # Same story re-headlined for X Takeover: caught on body vocabulary.
        assert any("Lexus adopts" in d.title and "body" in d.reason for d in result.removed)
        assert any("Grok Think Fast 2.0 rolls" in d.title for d in result.removed)
        # Short Spot re-using story 3's URL: caught on the source URL.
        assert any(d.section == "Short Spot" and d.reason == "same source URL" for d in result.removed)
        # The fresh Takeover item survives and is renumbered to 1.
        assert "1. **Cybertruck owners report new wiper firmware**" in result.text
        assert "Lexus adopts gigacasting" not in result.text
        # Top 12 untouched, essay untouched, sign-off untouched.
        assert "1. **Lexus will build an EV" in result.text
        assert "3. **Austrian Company" in result.text
        assert "Gigacasting is not a single machine" in result.text
        assert "Feedback welcome" in result.text

    def test_preamble_hook_is_not_an_item(self):
        # The bold hook restates the lead story on purpose; it must never be
        # counted as the "first telling" that gets story 1 dropped.
        result = do.dedupe_cross_section_items(TESLA_SHAPED)
        assert "1. **Lexus will build an EV" in result.text

    def test_no_items_returns_text_unchanged(self):
        essay = "# First Principles Daily\n\nA long narrative paragraph with no items.\n\nAnother paragraph.\n"
        assert do.dedupe_cross_section_items(essay).text == essay
        assert do.dedupe_cross_section_items("").text == ""

    def test_canonical_url_ignores_tracking_and_www(self):
        a = do._canonical_url("https://www.example.com/a/b/?utm_source=x&id=1")
        b = do._canonical_url("https://example.com/a/b?id=1")
        assert a == b

    def test_unrelated_items_are_kept(self):
        text = (
            "### Top News\n"
            "1. **Falcon 9 launches 24 Starlink satellites from Vandenberg**\n"
            "   The booster flew for the fifteenth time and landed on the drone ship. Source: https://a.example/1\n\n"
            "2. **FAA closes Starship Flight 13 mishap investigation**\n"
            "   The agency accepted eleven corrective actions covering the Ship's flap hinge seals. Source: https://a.example/2\n\n"
            "## Community Buzz\n"
            "1. **Observers photograph Booster 19 rolling to the pad**\n"
            "   The move came at dawn with new grid-fin actuators visible. Source: https://a.example/3\n"
        )
        assert do.dedupe_cross_section_items(text).count == 0

    def test_committed_tesla_ep592_five_takeover_repeats(self):
        path = ROOT / "digests/tesla_shorts_time/Tesla_Shorts_Time_Pod_Ep592_20260902.md"
        if not path.exists():
            pytest.skip("committed digest not present")
        result = do.dedupe_cross_section_items(path.read_text(encoding="utf-8"))
        takeover = [d for d in result.removed if "Takeover" in d.section]
        assert len(takeover) == 5, [d.title for d in result.removed]


class TestScriptAudit:
    DIGEST = (
        "### Top News\n1. **xAI pins Grok outage on Memphis data center**\n"
        "   xAI attributed the four-hour Grok outage to a fault at its Memphis data center, "
        "where a cooling loop tripped and idled roughly two hundred thousand GPUs.\n"
    )

    def test_verbatim_copy_scores_high_overlap(self):
        script = (
            "Patrick: xAI attributed the four-hour Grok outage to a fault at its Memphis data center, "
            "where a cooling loop tripped and idled roughly two hundred thousand GPUs.\n"
            "Patrick: The company said service returned by evening.\n"
        )
        a = sa.audit_script(script, digest_text=self.DIGEST)
        assert a.digest_overlap_pct is not None and a.digest_overlap_pct > 50

    def test_rewritten_script_scores_low_overlap(self):
        script = (
            "Patrick: Grok went dark for four hours yesterday, and xAI says the cause was a cooling loop "
            "tripping in Memphis.\nPatrick: That fault idled about two hundred thousand GPUs until evening.\n"
        )
        a = sa.audit_script(script, digest_text=self.DIGEST)
        assert a.digest_overlap_pct is not None and a.digest_overlap_pct < 30

    def test_repeated_numeric_fact_and_hook_restatement(self):
        hook = "Grok went dark for four hours because a cooling loop tripped in Memphis."
        script = "\n".join([
            f"Patrick: {hook}",
            "Patrick: This is SpaceX Daily.",
            "Patrick: Starbase is hiring its first police officers this month.",
            "Patrick: The department will start with twelve officers and one chief.",
            "Patrick: On the AI front, Grok went dark for four hours because a cooling loop tripped in Memphis.",
            "Patrick: xAI said the outage lasted four hours and affected roughly two hundred thousand GPUs.",
            "Patrick: The Memphis site houses roughly two hundred thousand GPUs across two halls.",
        ])
        a = sa.audit_script(script, hook=hook)
        assert a.hook_restated >= 1
        assert a.repeated_facts >= 1
        assert any("two hundred thousand" in e for e in a.repeated_fact_examples)

    def test_filler_shapes_are_counted_by_skeleton(self):
        script = "\n".join([
            "Patrick: Observers are watching for a post-incident report from xAI.",
            "Patrick: The move underscores how quickly the compute race is shifting.",
            "Patrick: No specific dollar figures were provided in the filing.",
            "Patrick: Now, shifting to the launch side of the business.",
            "Patrick: Builders should test the new endpoint before the deprecation date.",
            "Patrick: The report frames the change as a response to customer demand.",
            "Patrick: Falcon 9 flew its four hundredth mission of the year on Tuesday.",
        ])
        a = sa.audit_script(script)
        assert a.filler_sentences == 6
        assert set(a.filler_by_shape) >= {"spectator", "underscores", "nothing-to-say", "announcing", "advisory", "frame"}
        assert a.filler_pct == pytest.approx(600 / 7, rel=1e-3)

    def test_closing_plugs_are_excluded(self):
        script = (
            "Patrick: Falcon 9 flew its four hundredth mission of the year on Tuesday.\n"
            "Patrick: Find every show, free, at nerranetwork.com.\n"
            "Patrick: This episode used AI voice synthesis of my voice.\n"
        )
        a = sa.audit_script(script)
        assert a.sentences == 1

    def test_warnings_fire_above_thresholds(self):
        a = sa.ScriptAudit(
            sentences=50, words=800, digest_overlap_pct=70.0, duplicate_sentences=4,
            repeated_facts=7, filler_sentences=8, filler_pct=16.0, hook_restated=2,
            filler_by_shape={"spectator": 8}, repeated_fact_examples=["four hours x3"],
        )
        text = " ".join(a.warnings())
        for token in ("copies the digest", "carry no fact", "near-duplicate", "spoken more than once", "restated"):
            assert token in text
        clean = sa.ScriptAudit(50, 800, 15.0, 0, 1, 2, 4.0, 0, {}, [])
        assert clean.warnings() == []

    def test_metrics_keys(self):
        a = sa.audit_script("Patrick: Falcon 9 flew its fifteenth mission on Tuesday.", digest_text="x")
        keys = set(a.to_metrics())
        assert {"script_sentences", "script_repeated_facts", "script_filler_pct",
                "script_hook_restated", "script_digest_overlap_pct"} <= keys


class TestRunShowWiring:
    SRC = (ROOT / "run_show.py").read_text(encoding="utf-8")

    def test_dedupe_runs_before_validation_and_after_regen(self):
        first = self.SRC.index("x_thread = _dedupe_digest_sections(x_thread, config, metrics)")
        validate = self.SRC.index("_val_passed, _val_issues, _exact_dups = _validate_digest(")
        assert first < validate
        assert "x_thread = _dedupe_digest_sections(_x_struct, config, metrics)" in self.SRC

    def test_audit_runs_before_disclosure_append(self):
        audit = self.SRC.index("_audit_podcast_script(podcast_script, x_thread, hook, config, metrics)")
        disclosure = self.SRC.index('podcast_script = podcast_script.rstrip() + "\\n\\n" + _disclosure')
        assert audit < disclosure
        assert "_collapse_duplicate_tail_lines(podcast_script)" in self.SRC

    def test_collapse_duplicate_tail_lines(self):
        import importlib.util
        # Load the helper without importing run_show's SystemExit guard.
        src = self.SRC
        start = src.index("def _collapse_duplicate_tail_lines(")
        end = src.index("def _strip_source_scaffold_lines(")
        ns: dict = {}
        exec(src[start:end], ns)  # noqa: S102 — test-only extraction
        fn = ns["_collapse_duplicate_tail_lines"]
        plug = "And on the website: every episode's visuals live in our free image gallery."
        script = "\n".join(["line one", "line two", plug, "This episode used AI voice synthesis.", plug])
        out = fn(script)
        assert out.count(plug) == 1
        assert out.endswith("This episode used AI voice synthesis.")
        assert importlib.util is not None


class TestMemoryInstructionsNotMandatory:
    def test_shared_section_no_longer_demands_arc_sentences(self):
        from engine import show_memory
        text = show_memory._SECTION_INSTRUCTIONS
        assert "MANDATORY" not in text
        assert "1-2 natural sentences" not in text
        assert "ONE audible callback" in text
        assert "delta" in text

    def test_tesla_status_block_has_no_quotable_callback(self):
        from engine import tesla_memory as tm
        tracker = {"programs": {"optimus": {"display_name": "Optimus", "status": "Gen 3 hands in testing.",
                                             "key_open_questions": ["When does volume production start?"]}}}
        block = tm.build_narrative_status_block(tracker)
        assert "Remember, we covered" not in block
        assert "never a generic" in block
        assert "bigger arc" not in block.split("Tracked programs")[0] or "Do NOT add" in block
        assert "CONTINUITY BUDGET" in block

    def test_shared_status_block_matches(self):
        from engine import show_memory
        tracker = {"programs": {"p": {"display_name": "P", "status": "s", "key_open_questions": ["q"]}}}
        block = show_memory.build_narrative_status_block(tracker, "X")
        assert "Do NOT add" in block and "Then answer naturally" not in block


class TestPronunciationFixes:
    def test_vs_code_is_spelled_not_versus(self):
        from assets.pronunciation import replace_versus
        assert replace_versus("the Cursor vs. VS Code cold-start test") == "the Cursor versus V S Code cold-start test"
        assert replace_versus("SpaceX vs Blue Origin") == "SpaceX versus Blue Origin"
        assert replace_versus("a VSCode extension") == "a V S Code extension"

    def test_subreddit_path_is_spoken_as_a_name(self):
        from assets.pronunciation import replace_subreddit_paths
        assert replace_subreddit_paths("according to r/teslamotors, owners say") == \
            "according to the teslamotors subreddit, owners say"
        # A URL fragment is left alone (URLs are stripped elsewhere).
        assert replace_subreddit_paths("https://reddit.com/r/spacex") == "https://reddit.com/r/spacex"

    def test_pipeline_order_subreddit_before_slashes(self):
        src = (ROOT / "assets/pronunciation.py").read_text(encoding="utf-8")
        body = src[src.index("def prepare_text_for_tts("):]
        assert body.index("replace_subreddit_paths(text)") < body.index("replace_slashes(text)")


class TestPromptsCarryNoWorkedTransitionSentences:
    """Every seeded tic in this network came from a prompt supplying the
    literal line it wanted; the Sep 5 audits caught four more shipping
    verbatim (FF Ep182 L2, PT Ep172 L5 / Ep173 L2, OV Ep164 L46, Tesla
    Ep594 'There is a challenge worth discussing')."""

    BANNED = {
        "fascinating_frontiers_podcast.txt": ["Now, on a completely different note..."],
        "planetterrian_podcast.txt": ["Now, shifting to a very different area of research...",
                                      "here's something most people get wrong...\" or"],
        "omni_view_podcast.txt": ["\"Now, to really understand this story, there's something most coverage leaves out...\""],
        "tesla_podcast.txt": ["\"There is a challenge worth discussing...\"",
                              "Remember, we covered", "binge-worthy", "MANDATORY NARRATIVE CONTINUITY"],
        "spacex_podcast.txt": ["Meanwhile, on the Starlink side..."],
        "models_agents_podcast.txt": ["Now, speaking of code generation..."],
        "modern_investing_podcast.txt": ["STORYTELLING over lecturing", "treat it like a sports season"],
    }

    @pytest.mark.parametrize("name,phrases", sorted(BANNED.items()))
    def test_prompt_free_of_seeded_lines(self, name, phrases):
        text = (ROOT / "shows/prompts" / name).read_text(encoding="utf-8")
        for phrase in phrases:
            assert phrase not in text, f"{name} still carries the seeded line {phrase!r}"


class TestContentDisciplineShared:
    SHOWS = ("spacex", "tesla", "models_agents", "omni_view", "fascinating_frontiers",
             "planetterrian", "modern_investing", "env_intel", "mab")

    def test_snippet_exists_and_is_shape_only(self):
        text = (ROOT / "shows/prompts/_shared/content_discipline.txt").read_text(encoding="utf-8")
        for token in ("source material, not a draft", "eight consecutive words", "owner per fact",
                      "as many sentences as it has distinct facts", "ends on its last fact",
                      "ONE audible callback", "named once"):
            assert token in text, token
        # No quotable specimen sentence anywhere in the snippet.
        assert not re.search(r"^(?:Patrick|Host):", text, re.MULTILINE)

    @pytest.mark.parametrize("slug", SHOWS)
    def test_every_english_news_show_includes_it(self, slug):
        text = (ROOT / "shows/prompts" / f"{slug}_podcast.txt").read_text(encoding="utf-8")
        assert "<<include: _shared/content_discipline.txt>>" in text

    def test_rendered_prompts_contain_the_rules(self):
        from engine.generator import load_prompt
        text = load_prompt(ROOT / "shows/prompts/spacex_podcast.txt")
        assert "source material, not a draft" in text
        assert "<<include" not in text


class TestScriptRewriteGate:
    """Sep 5 evening follow-up: Tesla Ep595 (old prompts) copied 63% of its
    8-word phrases from the digest, Ep596 (new prompts) 51% — the prompt
    rule moved the number, not far enough. One bounded rewrite, kept only
    when it copies less and is not a truncation."""

    DIGEST = (
        "### Top News\n1. **Tesla finalizes AI5 and revives Dojo 3 with Intel packaging**\n"
        "   Tesla has finalized development of its Artificial Intelligence 5 automotive processor. "
        "Volume production is now scheduled at both TSMC and Samsung sites. "
        "Intel joins as a key packaging partner using EMIB technology for Dojo modules.\n"
    )
    COPIED = (
        "Patrick: Tesla has finalized development of its Artificial Intelligence 5 automotive processor.\n"
        "Patrick: Volume production is now scheduled at both TSMC and Samsung sites.\n"
        "Patrick: Intel joins as a key packaging partner using EMIB technology for Dojo modules.\n"
        "Patrick: That's your Tesla news for today.\n"
    )
    REWRITTEN = (
        "Patrick: The AI5 car chip is done, and Tesla will build it at two foundries, TSMC and Samsung.\n"
        "Patrick: Dojo 3 is back, with Intel packaging the modules on its EMIB process.\n"
        "Patrick: That means two suppliers for inference silicon and a third for training hardware.\n"
        "Patrick: That's your Tesla news for today.\n"
    )

    class _Cfg:
        class llm:
            script_rewrite_gate_overlap_pct = 40.0

    def test_copied_sentences_names_the_verbatim_ones(self):
        got = sa.copied_sentences(self.COPIED, self.DIGEST)
        assert len(got) == 3
        assert all("nerranetwork" not in s for s in got)
        assert sa.copied_sentences(self.REWRITTEN, self.DIGEST) == []

    def test_gate_rewrites_and_accepts_a_less_copied_script(self, monkeypatch):
        from engine import pipeline
        calls = []
        def fake_gen(tv, config, tracker=None, prompt_appendix=""):
            calls.append(prompt_appendix)
            return self.REWRITTEN
        monkeypatch.setattr("engine.generator.generate_podcast_script", fake_gen)
        out = pipeline._script_rewrite_gate(self.COPIED, self.DIGEST, self._Cfg(), {}, None)
        assert out["fired"] and out["accepted"]
        assert out["script"] == self.REWRITTEN
        assert out["before_pct"] > 40 and out["after_pct"] < out["before_pct"]
        assert "REWRITE REQUIRED" in calls[0] and "TSMC and Samsung" in calls[0]

    def test_gate_keeps_original_when_rewrite_is_truncated_or_no_better(self, monkeypatch):
        from engine import pipeline
        monkeypatch.setattr("engine.generator.generate_podcast_script",
                            lambda tv, config, tracker=None, prompt_appendix="": "Patrick: Short.")
        out = pipeline._script_rewrite_gate(self.COPIED, self.DIGEST, self._Cfg(), {}, None)
        assert out["fired"] and not out["accepted"] and out["script"] == self.COPIED
        monkeypatch.setattr("engine.generator.generate_podcast_script",
                            lambda tv, config, tracker=None, prompt_appendix="": self.COPIED)
        out = pipeline._script_rewrite_gate(self.COPIED, self.DIGEST, self._Cfg(), {}, None)
        assert out["fired"] and not out["accepted"]

    def test_gate_is_off_at_zero_and_below_threshold(self, monkeypatch):
        from engine import pipeline
        class Off:
            class llm:
                script_rewrite_gate_overlap_pct = 0
        assert pipeline._script_rewrite_gate(self.COPIED, self.DIGEST, Off(), {}, None) is None
        monkeypatch.setattr("engine.generator.generate_podcast_script",
                            lambda *a, **k: pytest.fail("must not call the model below threshold"))
        out = pipeline._script_rewrite_gate(self.REWRITTEN, self.DIGEST, self._Cfg(), {}, None)
        assert out["fired"] is False

    def test_gate_never_raises(self, monkeypatch):
        from engine import pipeline
        def boom(*a, **k):
            raise RuntimeError("api down")
        monkeypatch.setattr("engine.generator.generate_podcast_script", boom)
        assert pipeline._script_rewrite_gate(self.COPIED, self.DIGEST, self._Cfg(), {}, None) is None

    @pytest.mark.parametrize("slug", ("spacex", "tesla", "models_agents", "omni_view", "fascinating_frontiers",
                                      "planetterrian", "modern_investing", "env_intel", "models_agents_beginners"))
    def test_english_news_shows_enable_the_gate(self, slug):
        from engine.config import load_config
        cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
        assert float(cfg.llm.script_rewrite_gate_overlap_pct) == 40.0

    def test_narrative_and_russian_shows_leave_it_off(self):
        from engine.config import load_config
        for slug in ("unintended_consequences", "first_principles", "finansy_prosto", "privet_russian", "dp_pod"):
            cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
            assert float(cfg.llm.script_rewrite_gate_overlap_pct) == 0.0, slug

    def test_run_show_records_gate_metrics(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'pop("_script_rewrite_gate"' in src
        assert 'metrics.record("script_rewrite_gate_fired"' in src

    def test_tesla_first_principles_must_not_be_a_covered_story(self):
        text = (ROOT / "shows/prompts/tesla_digest.txt").read_text(encoding="utf-8")
        assert "TOPIC DISTINCTNESS" in text and "Short Spot item today" in text
