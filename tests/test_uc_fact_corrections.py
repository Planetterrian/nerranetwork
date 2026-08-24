"""WO-2 drift guards: verified factual corrections in the UC digests.

These are wrong FACTS, not wrong citations — the softening tool does not
touch them and the exposure regex does not flag them, so each correction
gets its own guard against regression (a regen from a stale copy, a bad
merge, or a well-meaning "restore"). Each test asserts the WRONG text is
gone AND a load-bearing anchor of the CORRECT text is present.

Sources for every correction are in the WO-2 table (Harrington v. Purdue
SCOTUS 23-124; WHO asbestos fact sheet; GiveWell; Petrosino et al.,
Campbell Collaboration 2002; Niinimäki 2020; TIME on Maya Bay; standard
fortification references; IEA/Egyptian electricity statistics; Gig Economy
Data Hub; Peltzman, JPE 83(4) 1975).
"""

import re
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
UC = ROOT / "digests" / "unintended_consequences"


def _digest(ep: int) -> str:
    matches = sorted(UC.glob(f"Unintended_Consequences_Ep{ep:03d}_*.md"))
    matches = [m for m in matches if "_claims" not in m.name]
    assert matches, f"no digest for UC episode {ep}"
    return matches[-1].read_text(encoding="utf-8")


class TestFactualCorrections:
    def test_1_oxycontin_sackler_releases(self):
        """Harrington v. Purdue (2024) struck down nonconsensual releases;
        the confirmed plan's releases are opt-in, ~$7bn over 15 years."""
        t = _digest(34)
        assert "retaining personal immunity from further civil suits" not in t
        assert "Supreme Court" in t and "opt-in" in t and "$7 billion" in t

    def test_2_asbestos_who_toll(self):
        t = _digest(67)
        assert "roughly 40,000 lives" not in t
        assert "more than 200,000 lives" in t

    def test_3_malaria_nets_cost_per_life(self):
        """A NET costs a few dollars; a LIFE SAVED costs thousands."""
        t = _digest(38)
        assert "under fifty dollars per life saved" not in t
        assert "thousand dollars per life saved" in t

    def test_4_scared_straight_review(self):
        """2002 Campbell/Petrosino review; trials 1967-1992; OR 1.68."""
        t = _digest(60)
        assert "A 2000 Campbell" not in t
        assert "between 1978 and 1992" not in t
        assert "approximately 28 percent" not in t
        assert "A 2002 Campbell" in t
        assert "between 1967 and 1992" in t
        assert "1.68" in t and "68 percent more likely" in t

    def test_5_fast_fashion_emissions(self):
        """The 8-10% figure is disputed and of unclear provenance; the
        causal 'stems directly' assertion is removed."""
        t = _digest(63)
        assert "8–10%" not in t and "8-10%" not in t
        assert "stems directly" not in t
        assert "two to six percent" in t

    def test_6_maya_bay_cap(self):
        t = _digest(79)
        assert "daily cap of 375" not in t
        assert "380 per hour" in t and "January 2022" in t

    def test_7_maginot_depth(self):
        t = _digest(9)
        assert "1,500-meter-deep" not in t
        assert "thirty meters deep" in t

    def test_8_aswan_electricity_share(self):
        """55% was true in the mid-1970s; ~7% today. The date is stated."""
        t = _digest(8)
        assert "roughly 55 percent of Egypt" not in t
        assert "mid-1970s" in t and "7 percent" in t

    def test_9_gig_work_sources(self):
        """BLS publishes no such worker estimate (CWS last ran 2017); the
        MIT/CEEPR revision ($3.37 -> $8.55-10) is noted; the
        Uber-commissioned study is 2015 with a $16-30 median range."""
        t = _digest(69)
        assert "Estimates from the Bureau of Labor Statistics" not in t
        assert "contingent-worker survey in 2017" in t
        assert "$3.37" in t and "revised the figure" in t
        assert "a 2014 study commissioned by Uber" not in t
        assert "a 2015 study commissioned by Uber" in t

    def test_10_seatbelts_peltzman_offset(self):
        """Peltzman (1975) argued an essentially COMPLETE offset."""
        t = _digest(72)
        assert "roughly half the expected safety gain" not in t
        assert "essentially complete" in t
        assert "net number of driver fatalities was unaffected" in t


class TestMechanicalFixes:
    def test_ep71_no_dangling_clause(self):
        t = _digest(71)
        assert "restoring ." not in t

    def test_reader_address_is_medium_neutral(self):
        """The books address readers; the digests now use a form that
        reads correctly in both media."""
        assert "Listeners can test" not in _digest(12)
        assert "Listeners facing" not in _digest(68)

    def test_ep66_introduces_daryl_gates(self):
        """V4 Ch6 must introduce Gates by full name before any bare
        'Gates' reference (orphaned-first-reference class)."""
        t = _digest(66)
        full = t.find("Daryl Gates")
        assert full != -1
        first_bare = re.search(r"(?<!Daryl )\bGates\b", t)
        assert first_bare is None or full < first_bare.start()

    def test_ep25_names_the_stanford_researchers(self):
        t = _digest(25)
        assert "a Stanford study examined" not in t
        assert "Diamond" in t and "McQuade" in t and "Qian" in t
        assert "American Economic Review" in t


class TestAmpersandSingleEscape:
    """The reviewed store builds showed literal '&amp;' in chapter text
    (one per FP chapter — the recurring '&' section headings). The current
    digest->EPUB path single-escapes correctly; this pins it so the
    double-escape class cannot return."""

    def test_epub_never_double_escapes(self, tmp_path):
        from engine.book_compiler import BookChapter, BookVolume, build_epub
        vol = BookVolume(
            volume_id="uc-amp-test", show_slug="unintended_consequences",
            show_name="Steel & Speed Weekly", volume_number=99,
            title="Facts & Fixes", subtitle="Errors & Corrections",
            episodes=[1],
        )
        chapter = BookChapter(
            number=1, episode_num=1, title="Records & Rules",
            epigraph="Iron & ore moved the world.",
            sections=[("The Result & The Limits",
                       ["AT&T built the network & kept it."])],
        )
        out = build_epub(vol, [chapter], tmp_path / "amp.epub")
        with zipfile.ZipFile(out) as z:
            for name in z.namelist():
                if not name.endswith((".xhtml", ".opf")):
                    continue
                body = z.read(name).decode("utf-8")
                assert "&amp;amp;" not in body, name
                # every raw & became exactly one entity
                assert not re.search(r"&(?!amp;|lt;|gt;|quot;|apos;|#)",
                                     body), name

    def test_narration_text_carries_raw_ampersand(self):
        from engine.book_compiler import BookChapter, chapter_tts_text
        c = BookChapter(number=1, episode_num=1, title="",
                        sections=[("The Lesson & The Promise",
                                   ["R&D paid for itself."])])
        out = chapter_tts_text(c)
        assert "&amp;" not in out and "R&D" in out


class TestNoNewCitationShapes:
    """WO-2 acceptance: the rewrites introduce no new citation-shape
    flags. Pin the corrected files at (or below) their measured post-fix
    counts so a regen can't quietly re-inflate them."""

    MAX_FLAGS = {34: 1, 67: 2, 38: 1, 60: 1, 63: 1, 79: 1, 9: 0, 8: 0,
                 69: 2, 72: 3, 71: 7, 12: 1, 68: 1, 25: 1}

    @pytest.mark.parametrize("ep", sorted(MAX_FLAGS))
    def test_flag_ceiling(self, ep):
        from engine.claims import find_citation_shapes
        found = len(find_citation_shapes(_digest(ep)))
        assert found <= self.MAX_FLAGS[ep], (
            f"ep{ep}: {found} citation shapes vs ceiling "
            f"{self.MAX_FLAGS[ep]} — a rewrite added provenance-shaped "
            "language without a ledger"
        )
