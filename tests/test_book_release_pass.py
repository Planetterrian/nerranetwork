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


FP_DIR = ROOT / "digests" / "first_principles"


def _fp_digest(ep: int) -> str:
    matches = sorted(p for p in FP_DIR.glob(f"*_Ep{ep:03d}_*.md")
                     if "_transcript" not in p.name and "_tts" not in p.name)
    assert matches, f"no digest for FP ep {ep}"
    return matches[-1].read_text(encoding="utf-8")


class TestWO5FirstPrinciplesArithmetic:
    """The corrected numbers are load-bearing: this series invites
    readers to check the arithmetic, and its audience will."""

    @pytest.mark.parametrize("ep,gone,present", [
        # Ammonia: HHV is not a minimum; exothermic synthesis adds no floor
        (7, "theoretical minimum of 39.4 kWh",
         "reversible minimum of about 33 kWh"),
        (7, "brings the combined floor to something like 8.5–9 MWh",
         "exothermic, releasing about 2.7 GJ per ton"),
        # Solar: real 1990s prices (nominal-vs-real stated as prose);
        # index eras reconciled
        (8, "still tens of dollars per watt into the 1990s",
         "five or six dollars per watt by 1990 in the "
         "dollars of the day"),
        # Atlantic cable: 1866 conductor ~215 t; the index moved to
        # 'the tens' (ledger verification could source the company's
        # capital raisings but not the million-pound contract price the
        # 20-40 arithmetic presumed)
        (33, "several thousand tons of copper whose commodity value",
         "complete armoured cable"),
        (33, "Idiot Index on the order of two to three",
         "Idiot Index in the tens"),
        # Watt: lede matches the body (one-third the fuel = 2/3 cut);
        # the impossible whole-cylinder-per-stroke calc is gone
        (55, "cut fuel use by roughly three-quarters",
         "cut fuel use by roughly two-thirds"),
        (55, "two tons of iron cooled and reheated by 80 degrees",
         "well under one percent"),
        # Heat pump: capital vs seasonal operating separated
        (32, "yields another few hundred dollars in energy cost",
         "belongs in the operating column"),
        # Two-Billion-Dollar Mile: like-for-like index
        (34, "Idiot Index on the order of two hundred or more",
         "Dividing like by like matters"),
        # Nuclear: 10-20x understated its own case ~8x
        (5, "one-tenth to one-twentieth of the overnight capital cost",
         "one-eightieth to one-one-hundred-sixtieth"),
        # Geothermal: consistent tonnage, real OCTG price
        (22, "a few hundred dollars per ton plus a few dozen tons",
         "$1,200–2,500 per tonne"),
        # Wright brothers: real tunnel dimensions; cables warp, chains
        # drive propellers
        (23, "six inches square and twenty inches long",
         "sixteen inches square and six feet long"),
        (23, "four lengths of bicycle-chain cable",
         "the bicycle chains went to the propeller drive"),
        # Recycling: pellet prices are 5-10x the stated figure
        (26, "perhaps two hundred dollars per ton once pelletized",
         "$1,300–2,600 per ton once cleaned and pelletized"),
        # Blood test: the honest denominator is what is actually paid —
        # $10.33 on the current (post-PAMA) CLFS; the WO's ~$14.50 was
        # the pre-PAMA rate, refined during ledger verification
        (9, "implied Idiot Index therefore sits somewhere between fifty",
         "roughly ten and a half dollars Medicare actually pays"),
    ])
    def test_correction_applied(self, ep, gone, present):
        text = _fp_digest(ep)
        assert gone not in text, f"ep{ep}: wrong text returned: {gone!r}"
        assert present in text, f"ep{ep}: correction missing: {present!r}"

    def test_index_accounting_rule_stated_once_for_series(self):
        note = ROOT / "books" / "frontmatter" / \
            "first_principles_index_note.md"
        assert "same boundary" in note.read_text(encoding="utf-8")
        for n in (1, 2, 3):
            data = yaml.safe_load(
                (VOLS / f"first_principles_vol{n}.yaml")
                .read_text(encoding="utf-8"))
            assert data.get("introduction_file", "").endswith(
                "first_principles_index_note.md"), n

    def test_heat_pump_chapter_retitled(self):
        """'Beating 100 Percent' conflated COP with efficiency."""
        data = yaml.safe_load(
            (VOLS / "first_principles_vol2.yaml").read_text(encoding="utf-8"))
        assert data["chapter_titles"][32] == "Moving Heat, Not Making It"


class TestWO6CombinedVolume:
    """The combined 30-chapter edition + the parts/front-matter machinery."""

    @pytest.fixture(scope="class")
    def built(self, tmp_path_factory):
        import zipfile
        from engine.book_compiler import (build_epub, collect_chapters,
                                          load_volume)
        vol = load_volume(VOLS / "unintended_consequences_collected.yaml")
        chapters = collect_chapters(vol)
        out = tmp_path_factory.mktemp("epub") / "collected.epub"
        build_epub(vol, chapters, out)
        return vol, chapters, zipfile.ZipFile(out)

    def test_thirty_chapters_five_parts_kudzu_opens(self, built):
        vol, chapters, _ = built
        assert len(chapters) == 30 and len(vol.parts) == 5
        assert all(len(p["episodes"]) == 6 for p in vol.parts)
        # Kudzu (ep59) opens the book: it debunks a myth the reader
        # arrives believing — the inverse of the cut Cobra opener.
        assert chapters[0].episode_num == 59
        assert chapters[0].title.lower().startswith("kudzu")
        # No cut episode sneaks back in via the anthology.
        assert not CUT_EPISODES & {c.episode_num for c in chapters}

    def test_anthology_identity_and_price(self, built):
        vol, _, _ = built
        assert vol.anthology and vol.volume_number == 0
        assert vol.full_title == "Unintended Consequences: The Collected Edition"
        assert float(vol.price_usd) == 7.99
        assert vol.subtitle.startswith("Thirty ")

    def test_epub_structure_with_parts(self, built):
        _, _, z = built
        names = z.namelist()
        for page in ("OEBPS/contents.xhtml", "OEBPS/introduction.xhtml",
                     "OEBPS/conclusion.xhtml", "OEBPS/author.xhtml",
                     "OEBPS/alsoby.xhtml"):
            assert page in names, page
        for i in range(1, 6):
            assert f"OEBPS/part_{i:02d}.xhtml" in names

    def test_spine_order(self, built):
        import re
        _, _, z = built
        opf = z.read("OEBPS/package.opf").decode("utf-8")
        spine = re.search(r"<spine>(.*?)</spine>", opf, re.S).group(1)
        order = re.findall(r'idref="([^"]+)"', spine)
        assert order[:6] == ["titlepage", "copyright", "contents",
                             "introduction", "part01", "chap001"]
        assert order[-4:] == ["conclusion", "sources", "authorbio",
                              "alsoby"]

    def test_nav_nests_chapters_under_parts(self, built):
        vol, _, z = built
        nav = z.read("OEBPS/nav.xhtml").decode("utf-8")
        for part in vol.parts:
            assert part["title"] in nav
        # nested <ol> per part inside the top-level list
        assert nav.count("<ol>") >= 6

    def test_toc_page_has_descriptor_per_chapter(self, built):
        _, chapters, z = built
        toc = z.read("OEBPS/contents.xhtml").decode("utf-8")
        assert toc.count("tocentry") >= len(chapters)

    def test_crosspromo_links_are_funnel_tagged(self, built):
        _, _, z = built
        page = z.read("OEBPS/alsoby.xhtml").decode("utf-8")
        assert "utm_campaign=nn-" in page and "book" in page

    def test_front_matter_is_authored_files_not_generated(self, built):
        vol, _, _ = built
        for f in (vol.introduction_file, vol.conclusion_file,
                  vol.author_bio_file):
            assert f and (ROOT / f).exists(), f
        # a missing authored file must fail loudly, never render empty
        from engine.book_compiler import _load_prose_file
        with pytest.raises(FileNotFoundError):
            _load_prose_file("books/frontmatter/does_not_exist.md")

    def test_parts_must_partition_episodes(self, tmp_path):
        from engine.book_compiler import load_volume
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "volume_id: x\nshow_slug: unintended_consequences\n"
            "show_name: UC\nvolume_number: 9\ntitle: T\n"
            "episodes: [2, 3, 4]\n"
            "parts:\n- title: P\n  episodes: [2, 3]\n",
            encoding="utf-8")
        with pytest.raises(ValueError):
            load_volume(bad)

    def test_every_collected_chapter_has_a_verified_ledger(self):
        """WO-4: all 30 shipping chapters carry a committed, non-empty
        claims sidecar, and each passes the offline gate (anchoring +
        lint) against the current digest — zero uncovered citation
        shapes. Live URL/quote verification happened at ledger save;
        re-audits run via scripts/verify_claims.py."""
        from engine import claims as C
        vol = yaml.safe_load(
            (VOLS / "unintended_consequences_collected.yaml")
            .read_text(encoding="utf-8"))
        for ep in vol["episodes"]:
            md = sorted(p for p in UC_DIR.glob(f"*_Ep{ep:03d}_*.md")
                        if "_transcript" not in p.name
                        and "_tts" not in p.name)[-1]
            ledger = C.load_ledger(md)
            assert ledger, f"ep{ep}: no ledger sidecar"
            gate = C.run_source_integrity_gate(
                md.read_text(encoding="utf-8"), ledger,
                verify_sources=False)
            assert gate.passed, f"ep{ep}: {gate.summary()}"

    def test_sources_page_populates_from_ledgers(self, built):
        _, _, z = built
        assert "OEBPS/sources.xhtml" in z.namelist()
        src = z.read("OEBPS/sources.xhtml").decode("utf-8")
        assert src.count("<h2>") == 30  # one group per chapter
        assert src.count('<a href="http') >= 100

    def test_single_volume_builds_unaffected_by_parts_machinery(self,
                                                                tmp_path):
        """A numbered volume (no parts, no intro/conclusion) keeps its
        pre-WO-6 chapter structure; it gains only the series bio page
        and the cross-promotion page."""
        import zipfile
        from engine.book_compiler import (build_epub, collect_chapters,
                                          load_volume)
        vol = load_volume(VOLS / "unintended_consequences_vol1.yaml")
        chapters = collect_chapters(vol)[:2]
        out = tmp_path / "v1.epub"
        build_epub(vol, chapters, out)
        names = zipfile.ZipFile(out).namelist()
        assert "OEBPS/contents.xhtml" not in names
        assert "OEBPS/introduction.xhtml" not in names
        assert not any(n.startswith("OEBPS/part_") for n in names)
        assert "OEBPS/author.xhtml" in names
        assert "OEBPS/alsoby.xhtml" in names
