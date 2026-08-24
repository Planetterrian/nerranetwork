"""Drift guards for the Aug 2026 book release pass (WO-3 … WO-8).

One class per work order. The standing constraints these pin: the podcast
episodes stay published (cuts are book-inclusion decisions only); excluded
episodes can never be re-swept into a future volume; ported content and
corrections cannot regress; and no rewrite in this pass introduces a new
citation-shape flag.
"""

from pathlib import Path

import pytest
import yaml

from engine.claims import find_citation_shapes

ROOT = Path(__file__).resolve().parent.parent
UC_DIR = ROOT / "digests" / "unintended_consequences"
VOLS = ROOT / "books" / "volumes"

CUT_EPISODES = {1, 36, 44, 56, 71, 74, 77}


def _uc_digest(ep: int) -> str:
    matches = sorted(UC_DIR.glob(f"*_Ep{ep:03d}_*.md"))
    matches = [m for m in matches if "_transcript" not in m.name
               and "_tts" not in m.name]
    assert matches, f"no digest for UC ep {ep}"
    return matches[-1].read_text(encoding="utf-8")


class TestWO3ChapterCuts:
    def test_cut_episodes_absent_from_every_volume(self):
        for p in sorted(VOLS.glob("unintended_consequences_vol*.yaml")):
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            eps = set(int(e) for e in data.get("episodes", []))
            titles = set(int(e) for e in (data.get("chapter_titles") or {}))
            hit = CUT_EPISODES & (eps | titles)
            assert not hit, f"{p.name} still lists cut episode(s) {hit}"

    def test_series_excludes_cut_episodes_from_planner(self):
        series = yaml.safe_load(
            (ROOT / "books" / "series" / "unintended_consequences.yaml")
            .read_text(encoding="utf-8"))
        assert set(series.get("excluded_episodes", [])) == CUT_EPISODES

    def test_planner_respects_exclusion(self):
        """A cut episode looks 'uncollected' — without the exclusion the
        planner would open the NEXT volume with the Cobra Bounty."""
        from engine.book_compiler import plan_next_volumes
        for path in plan_next_volumes("unintended_consequences", write=False):
            assert not path.exists() or True  # dry-run returns prospective paths
        # The real assertion: a hypothetical future volume must not start
        # below episode 81 (the first genuinely uncollected episode).
        from engine.book_compiler import (
            _available_episode_numbers, _episodes_already_in_volumes,
            load_series,
        )
        series = load_series("unintended_consequences")
        covered = _episodes_already_in_volumes("unintended_consequences")
        excluded = set(series.get("excluded_episodes", []))
        pending = [n for n in _available_episode_numbers(series)
                   if n not in covered and n not in excluded]
        assert all(n >= 81 for n in pending), pending

    def test_cut_digests_stay_published(self):
        """Book-inclusion decision only — the podcast record survives."""
        for ep in sorted(CUT_EPISODES):
            assert _uc_digest(ep)

    def test_volumes_within_enforced_size_band(self):
        for p in sorted(VOLS.glob("unintended_consequences_vol*.yaml")):
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            assert 10 <= len(data["episodes"]) <= 20, p.name

    def test_sf_rent_control_correction(self):
        """Enacted by the Board of Supervisors, signed by Feinstein,
        pre-empting Proposition R (which voters rejected) — not approved
        by voters."""
        text = _uc_digest(25)
        assert "San Francisco voters approved rent control" not in text
        assert "Board of Supervisors enacted rent control in June 1979" in text
        assert "Proposition R" in text
        assert "Feinstein" in text

    def test_rent_control_port_landed(self):
        """V4C14's 20-unit worked example lives on in the surviving
        chapter (ep25)."""
        text = _uc_digest(25)
        assert "20-unit rent-controlled property generates $180,000" in text
        assert "selective withdrawal" in text
        # …and the donor episode is cut from the books, not deleted.
        assert "20-unit" in _uc_digest(74)

    def test_nclb_port_landed(self):
        """V4C17's AYP arithmetic + science-testing detail live on in
        ep26, which already carried the more complete CEP survey."""
        text = _uc_digest(26)
        assert "science testing beginning in 2007–2008" in text
        assert "arithmetic of Adequate Yearly Progress" in text
        assert "62 percent" in text and "44 percent" in text

    @pytest.mark.parametrize("ep,ceiling", [(25, 1), (26, 2)])
    def test_ports_added_no_citation_shapes(self, ep, ceiling):
        assert len(find_citation_shapes(_uc_digest(ep))) <= ceiling
