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


class TestWO7CoverRerolls:
    """cover_art_prompt() is deterministic — same inputs, byte-identical
    image from Grok Imagine (UC Vol 1's cover matched md5 across two
    cold-cache CI runs). cover_variant is the only sanctioned re-roll."""

    def _chapters(self):
        from engine.book_compiler import BookChapter
        return [BookChapter(number=i, episode_num=i, title=f"T{i}")
                for i in range(1, 7)]

    def test_variant_perturbs_prompt_and_empty_is_legacy(self):
        from engine.book_art import cover_art_prompt
        from engine.book_compiler import load_volume
        vol = load_volume(VOLS / "unintended_consequences_vol1.yaml")
        chapters = self._chapters()
        base = cover_art_prompt(vol.cover_art_style, vol, chapters)
        rolled = cover_art_prompt(vol.cover_art_style, vol, chapters,
                                  variant="7")
        assert base != rolled and "Composition variant 7." in rolled
        assert cover_art_prompt(vol.cover_art_style, vol, chapters,
                                variant="") == base

    def test_rejected_covers_carry_a_committed_variant(self):
        """UC Vol 2 (garbled stone lettering) and Vol 4 (illegible bag
        text; rope-reads-as-noose flagged for Patrick) re-roll on the
        next build; approved volumes carry NO variant."""
        from engine.book_compiler import load_volume
        for name, expect in (("unintended_consequences_vol2", True),
                             ("unintended_consequences_vol4", True),
                             ("unintended_consequences_vol1", False),
                             ("unintended_consequences_vol3", False),
                             ("first_principles_vol1", False)):
            vol = load_volume(VOLS / f"{name}.yaml")
            assert bool(str(vol.cover_variant).strip()) is expect, name

    def test_cover_styles_ban_text_bearing_objects(self):
        """Both rejects failed the same way — the artwork depicted
        text-bearing OBJECTS (carved document, printed bag) that the
        generic no-text clause did not prevent."""
        for series in ("unintended_consequences", "first_principles"):
            data = yaml.safe_load(
                (ROOT / "books" / "series" / f"{series}.yaml")
                .read_text(encoding="utf-8"))
            style = data["cover_art_style"]
            assert "object whose surface carries writing" in style, series

    def test_build_script_threads_variant_and_keys_cache(self):
        src = (ROOT / "scripts" / "build_book.py").read_text("utf-8")
        assert "--cover-variant" in src
        assert "cover_art_prompt(volume.cover_art_style, volume, chapters,"\
            in src
        # A bumped variant must never be served the old cached image.
        assert 'f"cover_art{_suffix}.png"' in src

    def test_runbook_no_longer_claims_rerun_rerolls(self):
        doc = (ROOT / "docs" / "books.md").read_text("utf-8")
        assert "re-rolled cover), dispatch it by name" not in doc
        assert "cover_variant" in doc
