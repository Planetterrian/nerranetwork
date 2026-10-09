"""Oct 9 2026 — the operator's yes to four of the post-upgrade items.

* SpaceX's SCRIPT stage runs grok-4.6 (experiment
  ``spacex-script-grok46-2026-10-09``); its digest stays on the 4.3 network
  default, the shape every script-stage arm has had since dp_pod's.
* The ZH translation track is off on the three shows that carried it:
  eleven weeks after the per-language OP3 instrument went in, every ZH
  feed still read ``measured: false`` at ~$2.70/week (pinned in
  tests/test_multilingual.py).
* The Voices Worker holds ONE cron trigger; its three jobs run by firing
  minute (pinned in tests/test_producer_autonomy.py). Workers Free allows
  five per account and the show scheduler needed one back.
* Dependabot groups each ecosystem's weekly bumps into one PR — five
  separate PRs a week is how #1365 (PyAV 19) was merged with its pin
  comment unread.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.config import load_config  # noqa: E402


class TestSpaceXScriptArm:
    def test_script_on_46_digest_on_43(self):
        cfg = load_config(ROOT / "shows" / "spacex.yaml")
        assert cfg.llm.podcast_model == "grok-4.6"
        assert cfg.llm.model == "grok-4.3", "the digest never follows the script arm"

    def test_tesla_waits_for_the_gate(self):
        """Tesla joins only on a GATE: PASS from the SpaceX arm
        (docs/model_upgrade_playbook.md) — never by accident."""
        cfg = load_config(ROOT / "shows" / "tesla.yaml")
        assert not getattr(cfg.llm, "podcast_model", "")

    def test_registered(self):
        reg = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8"))
        ids = {e["id"] for e in reg["experiments"]}
        assert "spacex-script-grok46-2026-10-09" in ids


class TestDependabotGroups:
    def test_each_ecosystem_opens_one_pr_a_week(self):
        cfg = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
        by_eco = {u["package-ecosystem"]: u for u in cfg["updates"]}
        for eco in ("pip", "github-actions"):
            groups = by_eco[eco].get("groups") or {}
            assert groups, eco
            assert any(g.get("patterns") == ["*"] for g in groups.values()), eco
        # The PyAV ceiling is still ignored, grouped or not.
        ignored = by_eco["pip"].get("ignore") or []
        assert any(i.get("dependency-name") == "av" and i.get("versions") == [">=19"]
                   for i in ignored)
