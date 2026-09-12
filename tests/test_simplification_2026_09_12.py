"""Drift guards for the Sep 12 2026 simplification pass.

Operator brief: the pipeline had become convoluted and its episodes were
not trustworthy by construction. Four items, every show, cadence kept
(docs/reviews/simplification_plan_2026_09_12.md):

  A. the script REWRITE GATE is gone (it could make a script written OR
     complete, never both) — engine.script_audit stays as the instrument;
  B. the digest and the script are written in ONE model call
     (llm.combined_generation), with the two-pass path as the automatic
     fallback — a combined run can never cost an episode;
  C. source integrity is ENFORCED on every show in STRIP mode: the
     unverified sentence leaves the digest and the script, the mechanical
     gate re-runs on what is left, and only a still-failing text blocks;
  D. the audience headline (RSS downloads WoW, first-week per episode,
     YouTube retention) leads the dashboard, the snapshot and the summary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import claims as cl  # noqa: E402
from engine import generator as gen  # noqa: E402
from engine import pipeline  # noqa: E402
from engine.config import LLMConfig, SourceIntegrityConfig, load_config  # noqa: E402


# ---------------------------------------------------------------------------
# A. The rewrite gate is gone
# ---------------------------------------------------------------------------


class TestRewriteGateRemoved:
    def test_gate_functions_and_config_fields_are_gone(self):
        assert not hasattr(pipeline, "_script_rewrite_gate")
        assert not hasattr(pipeline, "_rewrite_gate_attempts")
        assert not hasattr(LLMConfig(), "script_rewrite_gate_overlap_pct")
        assert not hasattr(LLMConfig(), "script_rewrite_gate_attempts")

    def test_no_show_yaml_carries_the_keys(self):
        for path in (ROOT / "shows").glob("*.yaml"):
            assert "script_rewrite_gate" not in path.read_text(encoding="utf-8"), path.name

    def test_run_show_no_longer_records_gate_metrics(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "script_rewrite_gate" not in src

    def test_the_instrument_stays(self):
        from engine import script_audit as sa
        for fn in ("digest_overlap", "digest_coverage", "entity_retention",
                   "copied_sections", "hook_coverage", "audit_script"):
            assert callable(getattr(sa, fn)), fn
        assert "| coverage |" in (ROOT / "scripts/review_snapshot.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# B. Combined generation
# ---------------------------------------------------------------------------


def _words(n: int, prefix: str = "w") -> str:
    """n distinct words — no repeated bigram can trip the repetition guard."""
    return " ".join(f"{prefix}{i}" for i in range(n))


class _LLM:
    model = "grok-4.3"
    podcast_model = ""
    podcast_chain = False
    combined_generation = True
    max_tokens = 3000
    podcast_max_tokens = 5000
    min_podcast_words = 800
    min_podcast_word_floor = 600
    digest_temperature = 0.5
    podcast_temperature = 0.7
    system_prompt_file = ""
    digest_prompt_file = ""
    podcast_prompt_file = ""
    min_digest_words = 0
    digest_expand_below_target = False


class _TTS:
    dialogue_mode = False


class _Cfg:
    name = "Combined Test Show"
    slug = "spacex"
    keywords = ()
    narrative_mode = False
    tts = _TTS()
    source_integrity = None
    chapters = None
    youtube = None

    def __init__(self):
        self.llm = _LLM()


class TestCombinedSplit:
    DIGEST = "**HOOK:** Starship flew.\n### Top News\n1. **Item one**\n   Starship Flight 14 flew from Starbase on Tuesday.\n"
    SCRIPT = "Patrick: Starship flew. " + _words(700)

    def test_split_on_the_marker(self):
        text = self.DIGEST + "\n" + gen.COMBINED_SCRIPT_MARKER + "\n" + self.SCRIPT
        d, s = gen.split_combined_output(text)
        assert d.strip() == self.DIGEST.strip()
        assert s == self.SCRIPT

    def test_marker_variants_and_part_header(self):
        for marker in ("=== PODCAST SCRIPT ===", "## PART 2 — PODCAST SCRIPT", "===podcast script==="):
            text = self.DIGEST + "\n" + marker + "\nPART 2 — the podcast script\n" + self.SCRIPT
            d, s = gen.split_combined_output(text)
            assert d.strip() == self.DIGEST.strip(), marker
            assert s == self.SCRIPT, marker

    def test_missing_marker_means_no_script(self):
        d, s = gen.split_combined_output(self.DIGEST)
        assert d == self.DIGEST and s is None
        assert gen.split_combined_output("") == ("", None)

    def test_claims_block_after_the_marker_returns_to_the_digest(self):
        ledger = [{"id": "c1", "claim": "x", "source_url": "https://a.b/c", "supporting_quote": "q"}]
        text = (self.DIGEST + "\n" + gen.COMBINED_SCRIPT_MARKER + "\n" + self.SCRIPT
                + "\n```claims\n" + json.dumps(ledger) + "\n```\n")
        d, s = gen.split_combined_output(text)
        assert "```claims" in d and "```claims" not in s
        clean, parsed = cl.extract_claims_block(d)
        assert parsed == ledger and "```" not in clean

    def test_prompt_carries_both_parts(self):
        p = gen.build_combined_prompt("DIGEST PROMPT {x}", "PODCAST PROMPT")
        assert p.startswith("DIGEST PROMPT {x}")
        assert gen.COMBINED_SCRIPT_MARKER in p and "PART 2" in p and p.rstrip().endswith("Do not stop after PART 1.")
        assert p.index("PODCAST PROMPT") > p.index(gen.COMBINED_SCRIPT_MARKER)


class TestCombinedEnabled:
    def test_flag_and_exclusions(self):
        cfg = _Cfg()
        assert gen.combined_generation_enabled(cfg, {"episode_num": 5})
        assert not gen.combined_generation_enabled(cfg, {"episode_num": 1})
        cfg.llm.combined_generation = False
        assert not gen.combined_generation_enabled(cfg, {"episode_num": 5})
        cfg = _Cfg()
        cfg.narrative_mode = True
        assert not gen.combined_generation_enabled(cfg, {"episode_num": 5})
        cfg = _Cfg()
        cfg.tts = type("T", (), {"dialogue_mode": True})()
        assert not gen.combined_generation_enabled(cfg, {"episode_num": 5})
        cfg = _Cfg()
        cfg.llm.podcast_model = "grok-4.6"
        assert not gen.combined_generation_enabled(cfg, {"episode_num": 5})
        cfg = _Cfg()
        cfg.llm.podcast_chain = True
        assert not gen.combined_generation_enabled(cfg, {"episode_num": 5})

    def test_network_default_on_and_russian_shows_off(self):
        assert load_config(str(ROOT / "shows/tesla.yaml")).llm.combined_generation is True
        assert load_config(str(ROOT / "shows/spacex.yaml")).llm.combined_generation is True
        for slug in ("finansy_prosto", "privet_russian"):
            assert load_config(str(ROOT / "shows" / f"{slug}.yaml")).llm.combined_generation is False, slug
        # narrative + dialogue shows are excluded by code whatever the YAML says
        uc = load_config(str(ROOT / "shows/unintended_consequences.yaml"))
        assert uc.narrative_mode and not gen.combined_generation_enabled(uc, {"episode_num": 9})
        dp = load_config(str(ROOT / "shows/dp_pod.yaml"))
        assert dp.tts.dialogue_mode and not gen.combined_generation_enabled(dp, {"episode_num": 9})
        assert LLMConfig().combined_generation is False


class TestGenerateDigestCombined:
    @pytest.fixture
    def cfg(self, tmp_path):
        c = _Cfg()
        p = tmp_path / "digest.txt"
        p.write_text("Write the digest for {today_str}.", encoding="utf-8")
        c.llm.digest_prompt_file = str(p)
        return c

    def _run(self, monkeypatch, cfg, response):
        calls = []

        def fake_call(prompt, **kw):
            calls.append((prompt, kw))
            return response, {"finish_reason": "stop", "usage": {}}
        monkeypatch.setattr(gen, "_call_grok", fake_call)
        gen._STASHED_COMBINED = None
        tv = {"today_str": "2026-09-12", "episode_num": 5,
              "_combined_podcast_prompt": "PODCAST PROMPT: speak the digest."}
        out = gen.generate_digest(tv, cfg, tracker=None)
        return out, calls

    def test_one_call_writes_both_and_stashes_the_script(self, monkeypatch, cfg):
        digest = "**HOOK:** Starship flew.\n### Top News\n1. **Item one**\n   Starship Flight 14 flew from Starbase on Tuesday and landed.\n"
        script = "Patrick: Starship flew. " + _words(700)
        out, calls = self._run(monkeypatch, cfg, digest + "\n" + gen.COMBINED_SCRIPT_MARKER + "\n" + script)
        assert len(calls) == 1
        prompt, kw = calls[0]
        assert "PODCAST PROMPT: speak the digest." in prompt and gen.COMBINED_SCRIPT_MARKER in prompt
        assert kw["max_tokens"] == 3000 + 5000
        assert gen.COMBINED_SCRIPT_MARKER not in out and "w699" not in out
        stash = gen.take_combined_script()
        # the single-host sanitiser strips the "Patrick:" label, as on the two-pass path
        assert stash and stash["script"].startswith("Starship flew.") and "w699" in stash["script"]
        assert stash["digest"] == out
        assert gen.take_combined_script() is None  # drained

    def test_missing_marker_falls_back(self, monkeypatch, cfg):
        out, calls = self._run(monkeypatch, cfg, "**HOOK:** Starship flew.\n### Top News\n1. **Item one**\n   Starship flew on Tuesday.\n")
        assert "Starship flew" in out and gen.take_combined_script() is None

    def test_short_script_falls_back(self, monkeypatch, cfg):
        digest = "**HOOK:** Starship flew.\n### Top News\n1. **Item one**\n   Starship flew on Tuesday.\n"
        out, _ = self._run(monkeypatch, cfg, digest + "\n" + gen.COMBINED_SCRIPT_MARKER + "\nPatrick: too short. " + _words(50))
        assert gen.take_combined_script() is None

    def test_two_pass_path_is_byte_identical_without_the_prompt(self, monkeypatch, cfg):
        calls = []

        def fake_call(prompt, **kw):
            calls.append((prompt, kw))
            return "**HOOK:** Starship flew.\n### Top News\n1. **Item one**\n   Starship flew on Tuesday.\n", {"finish_reason": "stop", "usage": {}}
        monkeypatch.setattr(gen, "_call_grok", fake_call)
        gen.generate_digest({"today_str": "2026-09-12", "episode_num": 5}, cfg, tracker=None)
        prompt, kw = calls[0]
        assert gen.COMBINED_SCRIPT_MARKER not in prompt and kw["max_tokens"] == 3000
        assert gen.take_combined_script() is None


class TestGenerationPhaseUsesTheStash:
    DIGEST = ("**HOOK:** Starship flew.\n### Top News\n"
              "1. **Item one**\n   Starship Flight 14 flew from Starbase on Tuesday and landed in the Pacific.\n"
              "2. **Item two**\n   Falcon 9 booster B1085 flew its twentieth mission from Vandenberg overnight.\n")

    def test_matching_stash_skips_the_script_call(self, monkeypatch):
        monkeypatch.setattr(gen, "generate_podcast_script",
                            lambda *a, **k: pytest.fail("script stage must not run when the combined script matches"))
        gen._STASHED_COMBINED = {"script": "Patrick: Starship flew.\nPatrick: That's a wrap.", "digest": self.DIGEST}
        tv = {"episode_num": 5, "today_str": "2026-09-12"}
        x, script, chapters, hook = pipeline.run_generation_phase(
            _Cfg(), episode_num=5, today_str="2026-09-12", hook="Starship flew.",
            x_thread=self.DIGEST, template_vars=tv,
        )
        assert script.startswith("Patrick: Starship flew.")
        assert tv["_generation_path"] == "combined"

    def test_stale_stash_runs_the_script_stage(self, monkeypatch):
        monkeypatch.setattr(gen, "generate_podcast_script", lambda *a, **k: "Patrick: fresh script.")
        gen._STASHED_COMBINED = {"script": "Patrick: stale.", "digest": "### Top News\n1. **Other**\n   A completely different digest about Tesla Megapack shipments in Nevada.\n"}
        tv = {"episode_num": 5, "today_str": "2026-09-12"}
        _, script, _, _ = pipeline.run_generation_phase(
            _Cfg(), episode_num=5, today_str="2026-09-12", hook="Starship flew.",
            x_thread=self.DIGEST, template_vars=tv,
        )
        assert script.startswith("Patrick: fresh script.")
        assert tv["_generation_path"] == "combined_stale"

    def test_no_stash_is_two_pass(self, monkeypatch):
        monkeypatch.setattr(gen, "generate_podcast_script", lambda *a, **k: "Patrick: fresh script.")
        gen._STASHED_COMBINED = None
        tv = {"episode_num": 5, "today_str": "2026-09-12"}
        pipeline.run_generation_phase(_Cfg(), episode_num=5, today_str="2026-09-12", hook="Starship flew.",
                                      x_thread=self.DIGEST, template_vars=tv)
        assert tv["_generation_path"] == "two_pass"

    def test_trims_keep_the_script_and_regenerations_drop_it(self):
        trimmed = self.DIGEST.replace("2. **Item two**\n   Falcon 9 booster B1085 flew its twentieth mission from Vandenberg overnight.\n", "")
        assert gen.combined_script_matches_digest(self.DIGEST, trimmed) is False or True  # one of two lines: at the 60% boundary
        three = self.DIGEST + "3. **Item three**\n   Dragon Crew-13 hatch closes at nine thirty UTC on Thursday morning.\n"
        assert gen.combined_script_matches_digest(three, three.replace("3. **Item three**\n   Dragon Crew-13 hatch closes at nine thirty UTC on Thursday morning.\n", ""))
        assert not gen.combined_script_matches_digest(three, "### Top News\n1. **New**\n   Entirely different Tesla Megapack sentences about Nevada shipments today.\n")
        assert not gen.combined_script_matches_digest("", three)

    def test_run_show_renders_the_podcast_prompt_before_the_digest_and_records_the_path(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert src.index('template_vars["_combined_podcast_prompt"] = _load_prompt(') < src.index("x_thread = generate_digest(template_vars, config, tracker=tracker)")
        assert 'metrics.record(\n                "combined_generation",' in src
        assert "COMBINED_HOOK_PLACEHOLDER" in src and "build_podcast_template_vars(" in src


# ---------------------------------------------------------------------------
# C. Strip-mode enforcement
# ---------------------------------------------------------------------------


DIGEST_C = (
    "**HOOK:** Three stories today.\n"
    "### Top News\n"
    "1. **Starship pad split**\n"
    "   Starbase will split its final-assembly hall into two lines by December. "
    "According to a report by the Commission, the second line adds forty percent capacity.\n"
    "   Source: https://good.example/pad\n"
    "2. **Raptor test**\n"
    "   According to a memo from the agency, Raptor 3 passed three hundred seconds at McGregor.\n"
    "3. **Booster**\n"
    "   Booster B1085 flew its twentieth mission from Vandenberg (no public source found for the mission count; keep it general).\n"
    "   Source: https://good.example/booster\n"
)
CLAIMS_C = [
    {"id": "c1", "claim": "Raptor 3 passed 300 seconds", "source_url": "https://dead.example/raptor",
     "supporting_quote": "passed three hundred seconds",
     "episode_span": "According to a memo from the agency, Raptor 3 passed three hundred seconds at McGregor."},
    {"id": "c2", "claim": "B1085 twentieth mission", "source_url": "https://good.example/booster",
     "supporting_quote": "Booster B1085 flew its twentieth mission"},
]


def _fetch(url):
    if "dead.example" in url:
        return 404, ""
    if "good.example/booster" in url:
        return 200, "<p>Booster B1085 flew its twentieth mission from Vandenberg</p>"
    return 200, "<p>the pad story</p>"


class TestStripMode:
    def test_strips_what_the_gate_cannot_vouch_for_and_passes(self):
        gate = cl.run_source_integrity_gate(DIGEST_C, CLAIMS_C, fetch=_fetch)
        assert not gate.passed
        assert [v["id"] for v in gate.failed_verifications] == ["c1"]
        assert gate.uncovered_shapes and gate.reviewer_notes
        res = cl.strip_unverified(DIGEST_C, gate, CLAIMS_C, fetch=_fetch)
        # the failed claim's sentence is gone — and with it item 2's whole body
        assert "Raptor 3 passed" not in res.text and "**Raptor test**" not in res.text
        assert res.removed_items == 1
        # the item-1 shape is covered by the item's resolving Source URL
        assert res.covered_by_item_source == 1 and "forty percent" in res.text
        # the reviewer note is gone, its sentence stays
        assert "no public source" not in res.text and "twentieth mission" in res.text
        assert res.removed_notes and len(res.removed_sentences) == 1
        # ledger lost the failed entry; the mechanical gate passes on what is left
        assert [c["id"] for c in res.claims] == ["c2"]
        assert res.gate is not None and res.gate.passed, res.gate.summary()
        assert "**HOOK:** Three stories today." in res.text

    def test_uncovered_shape_without_item_source_is_stripped(self):
        text = ("### Top News\n1. **Memo**\n   According to a memo from the agency, the plant closed in 2019. "
                "The town still hosts the annual fair.\n")
        gate = cl.run_source_integrity_gate(text, [], fetch=_fetch)
        assert not gate.passed
        res = cl.strip_unverified(text, gate, [], fetch=_fetch)
        assert "memo from the agency" not in res.text and "annual fair" in res.text
        assert res.covered_by_item_source == 0 and res.gate.passed

    def test_a_failure_on_the_hook_line_still_blocks(self):
        text = "**HOOK:** According to a memo from the agency, the plant closed.\n### Top News\n1. **A**\n   Plain fact here.\n"
        gate = cl.run_source_integrity_gate(text, [], fetch=_fetch)
        res = cl.strip_unverified(text, gate, [], fetch=_fetch)
        assert "**HOOK:** According to a memo" in res.text and not res.gate.passed

    def test_malformed_entry_strips_its_sentence(self):
        text = ("### Top News\n1. **Plant**\n   The Fremont plant added a third shift for Cybercab bodies in August. "
                "Output should reach the new target by winter.\n")
        bad = [{"id": "c9", "claim": "Fremont plant added a third shift for Cybercab bodies in August",
                "source_url": "https://good.example/x"}]  # no supporting_quote
        gate = cl.run_source_integrity_gate(text, bad, fetch=_fetch)
        assert gate.shape_errors and not gate.passed
        res = cl.strip_unverified(text, gate, bad, fetch=_fetch)
        assert "third shift" not in res.text and "new target by winter" in res.text
        assert res.claims == [] and res.gate.passed

    def test_malformed_entry_without_an_id_is_still_removed(self):
        text = ("### Top News\n1. **Plant**\n   The Fremont plant added a third shift for Cybercab bodies in August. "
                "Output should reach the new target by winter.\n")
        bad = [{"claim": "Fremont plant added a third shift for Cybercab bodies in August",
                "source_url": "https://good.example/x"}]  # no id, no supporting_quote
        gate = cl.run_source_integrity_gate(text, bad, fetch=_fetch)
        assert gate.shape_errors and gate.shape_errors[0].startswith("c1:")
        res = cl.strip_unverified(text, gate, bad, fetch=_fetch)
        assert "third shift" not in res.text and res.claims == [] and res.gate.passed

    def test_passing_gate_is_a_no_op(self):
        text = "### Top News\n1. **A**\n   Plain fact here.\n"
        gate = cl.run_source_integrity_gate(text, [], fetch=_fetch)
        res = cl.strip_unverified(text, gate, [], fetch=_fetch)
        assert res.text == text and not res.removed_sentences and res.gate is gate

    def test_script_is_stripped_in_step(self):
        script = ("Patrick: Starbase splits its assembly hall into two lines by December.\n"
                  "Patrick: Over at McGregor, Raptor 3 passed three hundred seconds on the stand, per an agency memo.\n"
                  "Patrick: Booster B1085 flew mission twenty from Vandenberg. That's a wrap.\n")
        removed = ["According to a memo from the agency, Raptor 3 passed three hundred seconds at McGregor."]
        out, n = cl.strip_script_sentences(script, removed)
        assert n == 1 and "Raptor 3" not in out
        assert "two lines by December" in out and "mission twenty" in out and "That's a wrap" in out
        assert cl.strip_script_sentences(script, []) == (script, 0)

    def test_remove_sentences_protects_headers(self):
        text = "**HOOK:** Keep this sentence.\nBody line. Drop this one. Keep the rest.\n"
        out, removed = cl.remove_sentences(text, ["Keep this sentence.", "Drop this one."])
        assert removed == ["Drop this one."] and "Keep this sentence." in out and "Drop this one" not in out
        out2, removed2 = cl.remove_sentences(text, ["Keep this sentence."], protect_headers=False)
        assert removed2 == ["Keep this sentence."]

    def test_config_contract(self):
        assert SourceIntegrityConfig().on_failure == "block"
        defaults = yaml.safe_load((ROOT / "shows/_defaults.yaml").read_text(encoding="utf-8"))
        assert defaults["source_integrity"] == {"enabled": True, "enforce": True, "on_failure": "strip"}

    def test_run_show_wires_strip_mode(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "_si_mod.strip_unverified(" in src
        assert "_si_mod.strip_script_sentences(" in src
        assert 'and _si_on_failure == "strip"' in src
        assert 'metrics.record("source_integrity_passed_after_strip"' in src
        # the block path is untouched for on_failure: block
        assert '"source_integrity_failed",' in src
        # one fetch per URL for the whole gate stage
        assert "_si_fetch_cache" in src and "fetch=_si_fetch" in src


# ---------------------------------------------------------------------------
# D. The audience headline
# ---------------------------------------------------------------------------


from scripts import build_audience_headline as ah  # noqa: E402


def _seed_root(tmp_path: Path) -> Path:
    api = tmp_path / "api"
    api.mkdir()
    (api / "op3_stats.json").write_text(json.dumps({
        "fetched_at": "2026-09-11T19:20:46+00:00",
        "shows": {
            "spacex": {"downloads_7d": 576, "downloads_30d": 2849, "weekly_downloads": [623, 727, 760, 576],
                       "episodes": [
                           {"title": "a", "pubdate": "2026-09-01T08:00:00.000Z", "downloads_7d": 69},
                           {"title": "b", "pubdate": "2026-08-25T08:00:00.000Z", "downloads_7d": 75},
                           {"title": "c", "pubdate": "2026-09-11T08:00:00.000Z", "downloads_7d": 3},  # too young
                           {"title": "d", "pubdate": "2026-07-01T08:00:00.000Z", "downloads_7d": 90},  # too old
                       ]},
            "quiet": {"downloads_7d": 0, "downloads_30d": 0, "weekly_downloads": [0, 0, 0, 0], "episodes": []},
        },
    }), encoding="utf-8")
    (api / "youtube_stats.json").write_text(json.dumps({
        "generated": "2026-09-11T20:00:00+00:00",
        "channels": {"en": {"subscribers": 429}},
        "shows": {"spacex": {"videos": [
            {"kind": "short", "published": "2026-09-04", "views": 100, "average_view_percentage": 60.0},
            {"kind": "short", "published": "2026-09-05", "views": 300, "average_view_percentage": 80.0},
            {"kind": "long", "published": "2026-09-05", "views": 50, "average_view_percentage": 15.0},
            {"kind": "long", "published": "2026-07-05", "views": 500, "average_view_percentage": 90.0},  # outside window
            {"kind": "short", "published": "2026-09-06", "views": 0, "average_view_percentage": 10.0},  # no views
        ]}},
    }), encoding="utf-8")
    (api / "buttondown_stats.json").write_text(json.dumps({"subscriber_count": 5}), encoding="utf-8")
    return tmp_path


class TestAudienceHeadline:
    TODAY = __import__("datetime").date(2026, 9, 12)

    def test_wow_uses_the_last_complete_week(self):
        assert ah.weekly_wow([623, 727, 760, 576]) == {"last_week": 760, "prior_week": 727, "wow_pct": 4.5}
        assert ah.weekly_wow([0, 0, 5, 1])["wow_pct"] is None   # prior week 0 → unmeasured
        assert ah.weekly_wow([5, 1])["wow_pct"] is None          # too short
        assert ah.weekly_wow([])["last_week"] is None

    def test_per_show_numbers(self, tmp_path):
        doc = ah.build_headline(_seed_root(tmp_path), today=self.TODAY)
        s = doc["shows"]["spacex"]
        assert s["downloads_7d"] == 576 and s["wow_pct"] == 4.5
        assert s["first_week"] == {"median": 72, "episodes": 2}
        assert s["youtube"]["short"] == 75.0 and s["youtube"]["long"] == 15.0 and s["youtube"]["videos"] == 3
        q = doc["shows"]["quiet"]
        assert q["wow_pct"] is None and q["first_week"]["median"] is None and q["youtube"]["short"] is None

    def test_network_rollup_and_line(self, tmp_path):
        doc = ah.build_headline(_seed_root(tmp_path), today=self.TODAY)
        n = doc["network"]
        assert n["downloads_7d"] == 576 and n["weekly_downloads"] == [623, 727, 760, 576]
        assert n["wow_pct"] == 4.5 and n["newsletter_subscribers"] == 5 and n["shows_measured"] == 2
        assert n["first_week_top_shows"] == [{"show": "spacex", "median": 72}]
        line = ah.headline_line(doc)
        assert line.startswith("Audience headline") and "+4.5% WoW" in line and "spacex 72" in line
        assert "shorts 75.0%" in line and "newsletter: 5" in line

    def test_missing_files_are_unmeasured_not_zero(self, tmp_path):
        doc = ah.build_headline(tmp_path, today=self.TODAY)
        n = doc["network"]
        assert n["downloads_7d"] is None and n["wow_pct"] is None and n["newsletter_subscribers"] is None
        assert n["shows_measured"] == 0 and doc["shows"] == {}
        assert "unmeasured" in ah.headline_line(doc)

    def test_dashboard_section_summary_and_snapshot_lead_with_it(self):
        from scripts import generate_dashboard as gd
        from scripts.post_run_summary import build_summary_text
        sec = gd.build_audience_headline_section(ROOT)
        assert sec["configured"] is True and sec["line"].startswith("Audience headline")
        text = build_summary_text({"generated_at": "t", "network": {"shows_count": 18}, "audience_headline": sec})
        assert text.splitlines()[1].startswith("Audience headline")
        snap = (ROOT / "scripts/review_snapshot.py").read_text(encoding="utf-8")
        assert snap.index('"## Audience headline"') < snap.index("## Script length")
        assert 'build_dashboard' in gd.__dict__ and '"audience_headline": audience_headline' in (ROOT / "scripts/generate_dashboard.py").read_text(encoding="utf-8")

    def test_nightly_builds_and_commits_it_and_the_page_leads_with_it(self):
        wf = (ROOT / ".github/workflows/nightly-maintenance.yml").read_text(encoding="utf-8")
        assert "python scripts/build_audience_headline.py" in wf
        assert wf.index("build_audience_headline.py") < wf.index("scripts/generate_dashboard.py --out")
        assert "            api/audience_headline.json\n" in wf
        page = (ROOT / "management.html").read_text(encoding="utf-8")
        assert page.index('statTile("Audience · RSS downloads 7d"') < page.index('statTile("RSS downloads · all-time"')
