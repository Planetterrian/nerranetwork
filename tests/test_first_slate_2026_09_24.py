"""The first on-schedule slate (2026-09-24): what it exposed, pinned.

1. The scheduler Worker fires whatever was last deployed — a stale redeploy
   left nine new slots off the live table. `scripts/check_scheduler_deploy.py`
   diffs the live `GET /` slot table against the source, nightly.
2. The Worker dispatched Peptides a week before its launch date — the
   dispatcher now honours FIRST_RUN (guard in test_scheduling_punctuality).
3. MAG 7 Ep2 lost The Counterpoint and On the Calendar to the overlap dedup
   (guards in test_delivery_pass) and nothing regenerated — the validator
   now requires the Counterpoint.
4. Peptides Ep2 shipped a dose past two dose_terms findings — a blocking
   lint list skips such an episode.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

EXEMPTIONS = {
    "mag7": {"The Counterpoint", "On the Calendar"},
    "ai_chips": {"On the Horizon"},
    "models_agents": {"On the Horizon"},
    "prediction_markets": {"The Week's Board"},
    "spacex": {"The Counterpoint"},
}


def _yaml(slug):
    return yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))


class TestDeployDriftCheck:
    COMMITTED = {"omni_view": (7, 1, None), "omni_view_asia_pacific": (6, 16, None),
                 "collingwood": (10, 7, "friday")}

    def test_status_payload_parses(self):
        from engine.scheduler_slots import slots_from_status
        live = slots_from_status({"slots": [
            {"at": "07:01Z", "show": "omni_view", "filter": None},
            {"at": "10:07Z", "show": "collingwood", "filter": "friday"},
            {"at": "bad", "show": "x"}, "junk",
        ]})
        assert live == {"omni_view": (7, 1, None), "collingwood": (10, 7, "friday")}
        assert slots_from_status({}) == {} and slots_from_status({"slots": None}) == {}

    def test_stale_table_is_named(self):
        from scripts.check_scheduler_deploy import check
        ok, lines = check({"slots": [
            {"at": "07:01Z", "show": "omni_view", "filter": None},
            {"at": "10:07Z", "show": "collingwood", "filter": "friday"},
        ]}, self.COMMITTED)
        assert ok is False
        assert any("missing on the live Worker: omni_view_asia_pacific @ 06:16Z" in ln for ln in lines)

    def test_matching_table_is_quiet(self):
        from scripts.check_scheduler_deploy import check
        ok, lines = check({"slots": [
            {"at": "07:01Z", "show": "omni_view", "filter": None},
            {"at": "06:16Z", "show": "omni_view_asia_pacific", "filter": None},
            {"at": "10:07Z", "show": "collingwood", "filter": "friday"},
        ]}, self.COMMITTED)
        assert ok is True and len(lines) == 1

    def test_changed_slot_and_no_table(self):
        from scripts.check_scheduler_deploy import check
        ok, lines = check({"slots": [
            {"at": "07:31Z", "show": "omni_view", "filter": None},
            {"at": "06:16Z", "show": "omni_view_asia_pacific"},
            {"at": "10:07Z", "show": "collingwood", "filter": "friday"},
        ]}, self.COMMITTED)
        assert ok is False and any(ln.startswith("changed: omni_view ") for ln in lines)
        ok, lines = check({"worker": "nerra-scheduler"}, self.COMMITTED)
        assert ok is False and "no slot table" in lines[0]

    def test_unset_variable_is_a_no_op(self, monkeypatch, capsys):
        from scripts.check_scheduler_deploy import main
        monkeypatch.delenv("SCHEDULER_STATUS_URL", raising=False)
        assert main([]) == 0
        assert "skipped" in capsys.readouterr().out

    def test_committed_parser_reads_the_real_table(self):
        from engine.scheduler_slots import worker_slots
        slots = worker_slots()
        assert slots["omni_view_asia_pacific"] == (6, 16, None)
        assert slots["collingwood"] == (10, 7, "friday")
        assert len(slots) >= 28

    def test_daily_audit_runs_it(self):
        wf = (ROOT / ".github" / "workflows" / "daily-audit.yml").read_text(encoding="utf-8")
        assert "python scripts/check_scheduler_deploy.py" in wf
        assert "SCHEDULER_STATUS_URL: ${{ vars.SCHEDULER_STATUS_URL }}" in wf
        readme = (ROOT / "workers" / "scheduler" / "README.md").read_text(encoding="utf-8")
        assert "SCHEDULER_STATUS_URL" in readme


class TestOverlapExemptionsAreConfigured:
    def test_yaml_and_dataclass(self):
        from engine.config import load_config
        for slug, expected in EXEMPTIONS.items():
            assert set(_yaml(slug).get("digest_overlap_exempt_sections") or []) == expected, slug
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
            assert set(cfg.digest_overlap_exempt_sections) == expected, slug

    def test_every_exempt_section_is_a_real_section_of_that_prompt(self):
        for slug, expected in EXEMPTIONS.items():
            prompt = (ROOT / "shows" / "prompts" / f"{slug}_digest.txt").read_text(encoding="utf-8")
            for name in expected:
                assert name in prompt, (slug, name)

    def test_default_is_empty(self):
        from engine.config import load_config
        assert load_config(ROOT / "shows" / "tesla.yaml").digest_overlap_exempt_sections == []


class TestMag7CounterpointRequired:
    def test_committed_ep2_fails_and_ep1_passes(self):
        from engine.validation import mag7_validation_config, validate_digest
        ep1 = ROOT / "digests/mag7/MAG7_Daily_Ep001_20260923.md"
        ep2 = ROOT / "digests/mag7/MAG7_Daily_Ep002_20260924.md"
        if not (ep1.exists() and ep2.exists()):
            pytest.skip("committed digests not present")
        cfg = mag7_validation_config()
        _, issues2, _ = validate_digest(ep2.read_text(encoding="utf-8"), cfg)
        assert any("The Counterpoint" in i and "missing" in i for i in issues2), issues2
        _, issues1, _ = validate_digest(ep1.read_text(encoding="utf-8"), cfg)
        assert not any("The Counterpoint" in i for i in issues1), issues1


class TestBlockingLints:
    def test_peptides_blocks_on_dose_terms(self):
        from engine.config import load_config
        assert _yaml("peptides").get("digest_lints_blocking") == ["dose_terms"]
        cfg = load_config(ROOT / "shows" / "peptides.yaml")
        assert cfg.digest_lints_blocking == ["dose_terms"]
        assert "dose_terms" in cfg.digest_lints  # a blocking lint must also be a running lint

    def test_no_other_show_blocks_yet(self):
        for p in (ROOT / "shows").glob("*.yaml"):
            if p.name.startswith("_") or p.stem == "peptides":
                continue
            assert not (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("digest_lints_blocking"), p.name

    def test_run_show_skips_never_strips(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        i = src.index("digest_lints_blocking")
        block = src[i:i + 2500]
        assert '"digest_lint_blocking"' in block and "_skip_episode(" in block
        assert 'metrics.record("digest_lints_blocked"' in block
        assert "strip_unverified" not in block and "strip_script_sentences" not in block

    def test_committed_peptides_ep2_would_have_been_blocked(self):
        from engine.digest_lint import run_digest_lints
        p = ROOT / "digests/peptides/Peptides_Weekly_Ep002_20260924.md"
        if not p.exists():
            pytest.skip("committed digest not present")
        fired, _ = run_digest_lints(p.read_text(encoding="utf-8"), ["dose_terms"])
        assert [f.lint for f in fired] == ["dose_terms"]


class TestItemsWithoutSourceLint:
    """Sep 24 2026: PT Ep193 shipped fifteen numbered items and no Source:
    line; the replay found PT Ep185/186, FF Ep192-195 and Tesla Ep614 had
    done the same, unnoticed by every gate."""

    OPT_IN = ("planetterrian", "fascinating_frontiers", "tesla", "spacex", "models_agents",
              "models_agents_beginners", "mag7", "ai_chips", "peptides", "longevity",
              "prediction_markets", "omni_view", "env_intel")
    NEVER = ("modern_investing", "finansy_prosto", "privet_russian", "unintended_consequences",
             "first_principles", "dp_pod", "offshore_north", "age_of_ai")

    def test_registered_and_opted_in(self):
        from engine.digest_lint import LINTS
        assert "items_without_source" in LINTS
        for slug in self.OPT_IN:
            assert "items_without_source" in (_yaml(slug).get("digest_lints") or []), slug
        for slug in self.NEVER:
            assert "items_without_source" not in (_yaml(slug).get("digest_lints") or []), slug

    def test_fires_on_the_committed_pt_ep193_and_not_on_ep192(self):
        from engine.digest_lint import run_digest_lints
        for ep, expect in (("193_20260924", True), ("192_20260923", False)):
            hits = list((ROOT / "digests/planetterrian").glob(f"*_Ep{ep}.md"))
            if not hits:
                pytest.skip("committed digest not present")
            fired, m = run_digest_lints(hits[0].read_text(encoding="utf-8"), ["items_without_source"])
            assert bool(fired) is expect, (ep, m)

    def test_bold_labels_are_not_items(self):
        from engine.digest_lint import items_without_source
        mit = ("### Portfolio\n**Current status:** the book holds three names. Source: none needed\n\n"
               "**Next review:** Friday.\n\n**Risk note:** the stop sits at 4%.\n")
        assert items_without_source(mit) == (0, 0)
        desk = ("### Across the Region\n**A dam closes: Reuters**\nBody. Source: https://r.example/a\n\n"
                "**A vote passes: BBC**\nBody.\n\n**A strike ends: AFP**\nBody.\n\n"
                "**A port opens: DW**\nBody.\n")
        assert items_without_source(desk) == (4, 3)

    def test_replay_is_quiet_on_the_opted_in_shows_recent_digests(self):
        # Every opted-in show's last 8 committed digests, minus the known
        # lapses this lint exists to catch.
        from engine.digest_lint import run_digest_lints
        known = {"Planetterrian_Daily_Ep185_20260916.md", "Planetterrian_Daily_Ep186_20260917.md",
                 "Planetterrian_Daily_Ep193_20260924.md", "Tesla_Shorts_Time_Pod_Ep614_20260923.md",
                 "MAB_Ep176_20260924.md"}
        import yaml as _y
        for slug in self.OPT_IN:
            cfg = _y.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            d = ROOT / ((cfg.get("episode") or {}).get("output_dir") or f"digests/{slug}")
            for p in sorted(x for x in d.glob("*_Ep*.md") if "_reader" not in x.name)[-8:]:
                if p.name in known or re.search(r"_Ep19[2-5]_202609", p.name) and slug == "fascinating_frontiers":
                    continue
                fired, m = run_digest_lints(p.read_text(encoding="utf-8"), ["items_without_source"])
                assert not fired, (slug, p.name, m)


class TestDocs:
    def test_claude_md_names_the_deploy_trap(self):
        md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        assert "What FIRES is what was last deployed" in md
        assert "check_scheduler_deploy.py" in md
