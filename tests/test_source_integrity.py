"""Drift guards for the source-integrity claim ledger (Aug 2026).

The failure class this system exists for: the pipeline handed the model
real source material, the model wrote citation-shaped prose, three
downstream strippers deleted every attribution, and nothing anywhere
verified that an asserted fact traced to anything — true facts wearing
false provenance (three chapters across two published book volumes each
citing "a 1962 paper in Nature" for findings published elsewhere, or
nowhere). These tests pin:

* the lint vocabulary catches the documented fabrication shapes;
* ledger extraction keeps the fenced block off every published surface;
* the gate's failure policy is BLOCKING (a soft failure reproduces the
  silent-degradation class), and a ledgerless general-form episode passes;
* the rollout shape — network-wide shadow, narrative shows enforced;
* the generation/run_show wiring points, so a refactor can't silently
  disconnect the gate;
* books inherit the ledger as an endnotes page.
"""

import json
import re
import zipfile
from pathlib import Path

import pytest

from engine import claims as claims_mod
from engine.claims import (
    CITATION_SHAPE_PATTERNS,
    claims_prompt_appendix,
    extract_claims_block,
    find_citation_shapes,
    fuzzy_contains,
    lint_uncovered_shapes,
    run_source_integrity_gate,
    save_ledger,
    load_ledger,
    claims_sidecar_path,
    GateResult,
)
from engine.config import load_config

ROOT = Path(__file__).resolve().parent.parent

RUN_SHOW_SRC = (ROOT / "run_show.py").read_text(encoding="utf-8")
GENERATOR_SRC = (ROOT / "engine" / "generator.py").read_text(encoding="utf-8")


def _fetch_with(source_text: str, status: int = 200):
    def _fetch(url):
        return status, f"<html><body>{source_text}</body></html>"
    return _fetch


def _fetch_dead(url):
    return 404, ""


GOOD_CLAIM = {
    "id": "c1",
    "claim": "Wagner linked crocidolite exposure to mesothelioma",
    "episode_span": "a 1960 paper linked crocidolite exposure to mesothelioma",
    "source_url": "https://example.org/wagner-1960",
    "source_title": "Diffuse pleural mesothelioma and asbestos exposure",
    "supporting_quote": "diffuse pleural mesothelioma associated with "
                        "exposure to crocidolite in the North Western Cape",
    "confidence": "high",
}

EPISODE_WITH_CLAIM = (
    "### Segment 2\n\n"
    "A 1960 paper linked crocidolite exposure to mesothelioma in the mines "
    "of the region. The consequences took decades to surface.\n"
)


class TestCitationShapeLint:
    """The lint vocabulary is the fabrication signature — every pattern
    below appeared in the fabricated citations found in the books."""

    @pytest.mark.parametrize("sentence", [
        "A 1962 paper in Nature warned that the perch would spread.",
        "Researchers found the effect reversed within a decade.",
        "Internal documents later released in litigation show the tests.",
        "According to a contemporary survey, most households complied.",
        "Estimates from clean-up organizations put the count far higher.",
        "Studies later showed the filters changed how people smoked.",
        "Trade data show the exports rose every year of the transition.",
        "By most accounts the population exceeded two hundred million.",
        "A 1974 report on the program reached the same conclusion.",
    ])
    def test_fabrication_shapes_are_caught(self, sentence):
        assert find_citation_shapes(sentence), sentence

    @pytest.mark.parametrize("sentence", [
        # The general form — the correct output when a claim can't be
        # sourced — must NOT trip the lint, or enforcement would punish
        # exactly the behavior the prompt asks for.
        "Contemporary observers warned that the lake would change.",
        "It later emerged that the filters changed how people smoked.",
        "The warnings received limited circulation at the time.",
        "Norway built the world's most generous demand-side EV regime.",
    ])
    def test_general_form_passes(self, sentence):
        assert not find_citation_shapes(sentence), sentence

    def test_headings_are_ignored(self):
        assert not find_citation_shapes("### According to a plan\n")

    def test_uncovered_vs_covered(self):
        text = EPISODE_WITH_CLAIM
        assert lint_uncovered_shapes(text, []) != []
        assert lint_uncovered_shapes(text, [GOOD_CLAIM]) == []


class TestClaimsExtraction:
    def _block(self, payload):
        return "Body prose here.\n\n```claims\n" + json.dumps(payload) + "\n```"

    def test_round_trip(self):
        clean, claims = extract_claims_block(self._block([GOOD_CLAIM]))
        assert "```" not in clean
        assert "claims" not in clean.lower() or "claims" in "Body prose here."
        assert claims == [GOOD_CLAIM]

    def test_absent_block_is_none(self):
        clean, claims = extract_claims_block("No ledger anywhere.")
        assert claims is None and clean == "No ledger anywhere."

    def test_empty_block_is_empty_list(self):
        clean, claims = extract_claims_block("Prose.\n\n```claims\n\n```")
        assert claims == [] and "```" not in clean

    def test_malformed_json_is_stripped_and_missing(self):
        clean, claims = extract_claims_block(
            "Prose.\n\n```claims\nnot json at all\n```")
        # Malformed scaffolding must never reach a published surface.
        assert "```" not in clean and claims is None

    def test_entry_cap(self):
        many = [dict(GOOD_CLAIM, id=f"c{i}") for i in range(100)]
        _, claims = extract_claims_block(self._block(many))
        assert len(claims) == claims_mod.MAX_CLAIMS_PER_EPISODE

    def test_validation_strip_helper(self):
        from engine.claims import strip_claims_block_for_validation
        out = strip_claims_block_for_validation(self._block([GOOD_CLAIM]))
        assert "supporting_quote" not in out


class TestFuzzyMatching:
    def test_exact_and_whitespace(self):
        assert fuzzy_contains("hello   world", "say Hello world today")

    def test_near_match_above_threshold(self):
        quote = ("diffuse pleural mesothelioma associated with exposure "
                 "to crocidolite")
        source = ("… a diffuse  pleural mesothelioma associated with the "
                  "exposure to crocidolite in miners …")
        assert fuzzy_contains(quote, source)

    def test_unrelated_text_fails(self):
        assert not fuzzy_contains(
            "the quick brown fox jumped over the lazy dog tonight",
            "quarterly earnings rose four percent on strong deliveries",
        )


class TestGateComposition:
    def test_verified_claim_passes(self):
        gate = run_source_integrity_gate(
            EPISODE_WITH_CLAIM, [GOOD_CLAIM],
            fetch=_fetch_with(GOOD_CLAIM["supporting_quote"]),
        )
        assert gate.passed and gate.claims_verified == 1

    def test_dead_url_blocks(self):
        gate = run_source_integrity_gate(
            EPISODE_WITH_CLAIM, [GOOD_CLAIM], fetch=_fetch_dead)
        assert not gate.passed
        assert gate.failed_verifications
        # The failed claim must not launder the sentence it decorates.
        assert gate.uncovered_shapes

    def test_quote_not_in_source_blocks(self):
        gate = run_source_integrity_gate(
            EPISODE_WITH_CLAIM, [GOOD_CLAIM],
            fetch=_fetch_with("entirely different article text about markets"),
        )
        assert not gate.passed
        assert any("supporting_quote" in v["reason"]
                   for v in gate.failed_verifications)

    def test_ledgerless_general_form_passes(self):
        gate = run_source_integrity_gate(
            "Contemporary observers warned the lake would change.\n",
            None, fetch=_fetch_dead)
        assert gate.passed and not gate.ledger_present

    def test_ledgerless_citation_shape_blocks(self):
        gate = run_source_integrity_gate(
            "Researchers found the effect reversed within a decade.\n",
            None, fetch=_fetch_dead)
        assert not gate.passed and gate.uncovered_shapes

    def test_span_edited_away_drops_claim(self):
        gate = run_source_integrity_gate(
            "Completely different prose about container shipping economics.",
            [GOOD_CLAIM], fetch=_fetch_with(GOOD_CLAIM["supporting_quote"]))
        assert gate.dropped_claims and gate.claims_anchored == 0

    def test_malformed_entry_blocks(self):
        bad = {"id": "c1", "claim": "something specific happened"}
        gate = run_source_integrity_gate(
            "Plain general prose.", [bad], fetch=_fetch_dead)
        assert gate.shape_errors and not gate.passed


class TestLedgerSidecar:
    def test_save_load_round_trip(self, tmp_path):
        digest = tmp_path / "Show_Ep001_20260822.md"
        digest.write_text("x", encoding="utf-8")
        gate = GateResult(passed=True, ledger_present=True,
                          claims_total=1, claims_anchored=1,
                          claims_verified=1, verified_claims=[GOOD_CLAIM])
        path = save_ledger(digest, gate)
        assert path.name == "Show_Ep001_20260822_claims.json"
        assert load_ledger(digest) == [GOOD_CLAIM]

    def test_missing_sidecar_is_empty(self, tmp_path):
        digest = tmp_path / "Show_Ep002_20260822.md"
        assert load_ledger(digest) == []
        assert claims_sidecar_path(digest).name.endswith("_claims.json")


class TestConfigRollout:
    """Network-wide SHADOW, narrative shows ENFORCED — never a
    network-wide day-one enforcement flip (model-upgrade-playbook)."""

    def test_network_default_is_shadow(self):
        for slug in ("tesla", "dp_pod", "omni_view", "spacex"):
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
            si = cfg.source_integrity
            assert si.enabled, f"{slug}: ledger must be on network-wide"
            assert not si.enforce, (
                f"{slug}: enforcement must roll out per show, not by "
                "flipping the network default"
            )

    def test_narrative_shows_are_enforced(self):
        for slug in ("unintended_consequences", "first_principles"):
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
            si = cfg.source_integrity
            assert si.enabled and si.enforce, (
                f"{slug}: the narrative shows are where fabricated "
                "provenance was demonstrated — the gate stays blocking"
            )

    def test_verify_sources_defaults_on(self):
        cfg = load_config(ROOT / "shows" / "unintended_consequences.yaml")
        assert cfg.source_integrity.verify_sources


class TestPromptAppendix:
    def test_de_seeded_by_shape(self):
        """No quotable example sentence — every seeded template tic in
        this network's history came from a prompt supplying the literal
        text it wanted. Placeholders must read as meta-description, not
        plausible content (the SpaceX **Title: Source Name** lesson)."""
        text = claims_prompt_appendix()
        assert "contemporary observers" not in text.lower()
        # Every JSON value in the spec is an angle-bracket meta-placeholder.
        for line in text.splitlines():
            if '":' in line:
                assert "<" in line or line.strip().startswith('"id"'), line

    def test_allows_empty_ledger(self):
        # Blocking on a missing ledger for general-form prose would kill
        # honest episodes; the spec must say an empty array is valid.
        assert "empty array" in claims_prompt_appendix().lower()

    def test_generator_injects_and_extracts(self):
        assert "claims_prompt_appendix" in GENERATOR_SRC
        assert "extract_and_stash" in GENERATOR_SRC
        assert "strip_claims_block_for_validation" in GENERATOR_SRC


class TestRunShowWiring:
    def test_gate_runs_before_digest_save_and_queue_burn(self):
        """A blocked narrative episode must cost a rerun, never a burned
        topic-queue slot: the gate sits before the digest save, which
        sits before mark_topic_produced."""
        gate_pos = RUN_SHOW_SRC.index("run_source_integrity_gate")
        save_pos = RUN_SHOW_SRC.index('digest_md.write_text')
        mark_pos = RUN_SHOW_SRC.index("mark_topic_produced")
        assert gate_pos < save_pos < mark_pos

    def test_enforce_blocks_via_skip(self):
        assert '"source_integrity_failed"' in RUN_SHOW_SRC
        assert '"source_integrity_error"' in RUN_SHOW_SRC  # fail CLOSED

    def test_sidecar_saved_with_episode(self):
        assert "save_ledger(digest_md" in RUN_SHOW_SRC

    def test_script_stage_lint_before_tts(self):
        # The script stage can invent citations the digest never had.
        idx = RUN_SHOW_SRC.index("source_integrity_script_uncovered")
        assert "reader_script" in RUN_SHOW_SRC[idx - 2000:idx]

    def test_shadow_mode_is_loud(self):
        assert "::warning::Source-integrity gate failed in shadow" \
            in RUN_SHOW_SRC


class TestBookEndnotes:
    def _volume(self):
        from engine.book_compiler import BookVolume
        return BookVolume(
            volume_id="uc-vol-99", show_slug="unintended_consequences",
            show_name="Unintended Consequences", volume_number=99,
            title="The Backfire Files", episodes=[1],
        )

    def _chapter(self, with_claims):
        from engine.book_compiler import BookChapter
        return BookChapter(
            number=1, episode_num=1, title="The Test Chapter",
            sections=[("The Lesson", ["One paragraph of prose."])],
            claims=[GOOD_CLAIM] if with_claims else [],
        )

    def test_epub_gets_sources_page_from_ledger(self, tmp_path):
        from engine.book_compiler import build_epub
        out = build_epub(self._volume(), [self._chapter(True)],
                         tmp_path / "book.epub")
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
            assert "OEBPS/sources.xhtml" in names
            sources = z.read("OEBPS/sources.xhtml").decode("utf-8")
            assert GOOD_CLAIM["source_url"] in sources
            assert GOOD_CLAIM["source_title"] in sources
            nav = z.read("OEBPS/nav.xhtml").decode("utf-8")
            assert "sources.xhtml" in nav
            opf = z.read("OEBPS/package.opf").decode("utf-8")
            assert 'idref="sources"' in opf

    def test_no_ledger_no_sources_page(self, tmp_path):
        from engine.book_compiler import build_epub
        out = build_epub(self._volume(), [self._chapter(False)],
                         tmp_path / "book.epub")
        with zipfile.ZipFile(out) as z:
            assert "OEBPS/sources.xhtml" not in z.namelist()

    def test_collect_chapters_loads_sidecars(self):
        src = (ROOT / "engine" / "book_compiler.py").read_text("utf-8")
        assert "load_ledger" in src


class TestOperatorTooling:
    def test_scripts_exist(self):
        for name in ("verify_claims.py", "measure_citation_exposure.py",
                     "soften_citations.py"):
            assert (ROOT / "scripts" / name).exists(), name

    def test_soften_is_dry_run_by_default(self):
        src = (ROOT / "scripts" / "soften_citations.py").read_text("utf-8")
        assert '"--apply"' in src
        assert "if args.apply" in src

    def test_soften_rules_are_grammatical(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "soften_citations", ROOT / "scripts" / "soften_citations.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out, applied, _ = mod.soften_text(
            "A 1962 note in Nature warned that the predator could spread.")
        assert applied and out.startswith("Contemporary accounts warned that")
        # The manual-review classes must NOT be auto-rewritten.
        out2, applied2, flagged2 = mod.soften_text(
            "Internal documents later released in litigation show the tests.")
        assert not applied2 and flagged2

    def test_check_sources_renamed_to_check_feeds(self):
        """The old name implied a guarantee the tool never provided —
        it grades feed health, not whether anything written is true."""
        assert (ROOT / "check_feeds.py").exists()
        assert not (ROOT / "check_sources.py").exists()
        wf = (ROOT / ".github" / "workflows" /
              "source-discovery.yml").read_text("utf-8")
        assert "check_feeds.py" in wf and "check_sources.py" not in wf


class TestDiagnosedFabricationsSoftened:
    """The three '1962 paper in Nature' fabrications the design doc
    diagnosed are softened in the canonical digests and must not return
    via a regen from stale copies."""

    @pytest.mark.parametrize("filename,phrase", [
        ("Unintended_Consequences_Ep075_20260731.md", "1962 note in Nature"),
        ("Unintended_Consequences_Ep008_20260513.md",
         "1962 paper in Nature by biologist Julian Huxley"),
        ("Unintended_Consequences_Ep067_20260723.md", "1962 Nature paper"),
    ])
    def test_fabricated_citation_gone(self, filename, phrase):
        path = ROOT / "digests" / "unintended_consequences" / filename
        assert phrase not in path.read_text(encoding="utf-8")


class TestUnreachableClassification:
    """403/429/5xx/transport failures are 'source could not be READ', not
    the fabrication signature (officialgazette.gov.ph 403'd six of eight
    UC Ep99 claims, 2026-08-24, and took the show down for two days).
    Still a gate FAILURE — the contract stays 'nothing unverified ships' —
    but labelled so repair can ask for a fetchable alternative."""

    def test_403_marks_unreachable_and_still_blocks(self):
        gate = run_source_integrity_gate(
            EPISODE_WITH_CLAIM, [GOOD_CLAIM],
            fetch=_fetch_with("", status=403))
        assert not gate.passed
        assert gate.failed_verifications[0]["unreachable"] is True
        assert "unreachable_sources=1" in gate.summary()

    def test_404_is_not_unreachable(self):
        # A source that says it does not exist IS the fabrication signal.
        gate = run_source_integrity_gate(
            EPISODE_WITH_CLAIM, [GOOD_CLAIM], fetch=_fetch_dead)
        assert not gate.passed
        assert gate.failed_verifications[0]["unreachable"] is False

    def test_transport_error_marks_unreachable(self):
        def _boom(url):
            raise OSError("connection refused")
        gate = run_source_integrity_gate(
            EPISODE_WITH_CLAIM, [GOOD_CLAIM], fetch=_boom)
        assert not gate.passed
        assert gate.failed_verifications[0]["unreachable"] is True

    def test_quote_mismatch_is_not_unreachable(self):
        gate = run_source_integrity_gate(
            EPISODE_WITH_CLAIM, [GOOD_CLAIM],
            fetch=_fetch_with("entirely different text about markets"))
        assert not gate.passed
        assert gate.failed_verifications[0]["unreachable"] is False


class TestClaimRepair:
    """One bounded chance to re-source failed claims — the repaired ledger
    re-runs the FULL mechanical gate, so repair can never launder an
    unverifiable claim into publication."""

    def _repaired_entry(self, url="https://example.edu/alt-source"):
        return {
            "id": "c1",
            "claim": "IGNORED — repair may not rewrite the claim",
            "episode_span": "IGNORED",
            "source_url": url,
            "source_title": "Alternative source",
            "supporting_quote": GOOD_CLAIM["supporting_quote"],
            "confidence": "high",
        }

    def _routed_fetch(self, good_url):
        def _fetch(url):
            if url == good_url:
                return 200, f"<html>{GOOD_CLAIM['supporting_quote']}</html>"
            return 403, ""
        return _fetch

    def test_repair_recovers_unreachable_claim(self):
        from engine.claims import attempt_claim_repair

        fetch = self._routed_fetch("https://example.edu/alt-source")
        gate = run_source_integrity_gate(
            EPISODE_WITH_CLAIM, [GOOD_CLAIM], fetch=fetch)
        assert not gate.passed

        def generate(prompt):
            assert "could not be fetched" in prompt
            return json.dumps([self._repaired_entry()])

        new_gate, new_claims = attempt_claim_repair(
            EPISODE_WITH_CLAIM, gate, [GOOD_CLAIM], generate, fetch=fetch)
        assert new_gate.passed
        assert new_gate.claims_verified == 1
        # Claim text + anchor are the ORIGINAL's — repair only re-sources.
        assert new_claims[0]["claim"] == GOOD_CLAIM["claim"]
        assert new_claims[0]["episode_span"] == GOOD_CLAIM["episode_span"]
        assert new_claims[0]["source_url"] == "https://example.edu/alt-source"

    def test_repair_with_bad_replacement_still_blocks(self):
        from engine.claims import attempt_claim_repair

        fetch = self._routed_fetch("https://example.edu/never-returned")
        gate = run_source_integrity_gate(
            EPISODE_WITH_CLAIM, [GOOD_CLAIM], fetch=fetch)

        def generate(prompt):
            return json.dumps(
                [self._repaired_entry(url="https://example.edu/still-403")])

        new_gate, _ = attempt_claim_repair(
            EPISODE_WITH_CLAIM, gate, [GOOD_CLAIM], generate, fetch=fetch)
        assert not new_gate.passed

    def test_repair_llm_garbage_returns_original(self):
        from engine.claims import attempt_claim_repair

        fetch = self._routed_fetch("https://example.edu/x")
        gate = run_source_integrity_gate(
            EPISODE_WITH_CLAIM, [GOOD_CLAIM], fetch=fetch)
        new_gate, new_claims = attempt_claim_repair(
            EPISODE_WITH_CLAIM, gate, [GOOD_CLAIM],
            lambda p: "no json here", fetch=fetch)
        assert new_gate is gate and new_claims == [GOOD_CLAIM]

    def test_repair_noop_on_passing_gate(self):
        from engine.claims import attempt_claim_repair

        fetch = _fetch_with(GOOD_CLAIM["supporting_quote"])
        gate = run_source_integrity_gate(
            EPISODE_WITH_CLAIM, [GOOD_CLAIM], fetch=fetch)
        assert gate.passed

        def generate(prompt):
            raise AssertionError("repair must not call the LLM when passing")

        new_gate, _ = attempt_claim_repair(
            EPISODE_WITH_CLAIM, gate, [GOOD_CLAIM], generate, fetch=fetch)
        assert new_gate.passed

    def test_run_show_wires_repair_before_block(self):
        # The enforce path must attempt repair before _skip_episode.
        assert "attempt_claim_repair" in RUN_SHOW_SRC
        assert RUN_SHOW_SRC.index("attempt_claim_repair") < RUN_SHOW_SRC.index(
            '"source_integrity_failed"')
