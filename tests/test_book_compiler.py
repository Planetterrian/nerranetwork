"""Drift guards for the anthology book pipeline (Aug 2026, product B6).

The compile path is deliberately deterministic — no LLM between the
committed digest and the sellable EPUB — so these tests exercise the real
corpus (Unintended Consequences digests on disk) rather than synthetic
fixtures wherever possible.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.book_compiler import (  # noqa: E402
    AI_NARRATION_DISCLOSURE,
    BookChapter,
    build_epub,
    chapter_tts_text,
    closing_credits_text,
    collect_chapters,
    episode_titles_from_rss,
    find_digest,
    load_volume,
    opening_credits_text,
    parse_digest_to_chapter,
    update_catalog,
)
from engine.titles import BOOK_CHAPTER_TITLE_MAX, fits  # noqa: E402

VOL_PATH = _ROOT / "books" / "volumes" / "uc_vol1.yaml"


def _volume():
    return load_volume(VOL_PATH)


def _chapter(ep: int, number: int = 1) -> BookChapter:
    v = _volume()
    md = find_digest(v, ep).read_text(encoding="utf-8")
    return parse_digest_to_chapter(md, number=number, episode_num=ep)


# ---------------------------------------------------------------------------
# Digest -> chapter parsing (both digest eras, real files)
# ---------------------------------------------------------------------------

class TestDigestParsing:
    def test_early_era_hook_inside_segment_one(self):
        """Ep005 carries its hook inside 'Segment 1 — The Hook'."""
        ch = _chapter(5)
        assert ch.epigraph, "hook segment must become the epigraph"
        assert len(ch.sections) >= 4
        titles = [t for t, _ in ch.sections]
        assert not any("hook" in t.lower() for t in titles), (
            "the hook segment must not survive as a body section"
        )

    def test_late_era_leading_blockquote(self):
        """Ep093-era digests open on a bare `> **hook**` blockquote."""
        v = _volume()
        md = find_digest(v, 50).read_text(encoding="utf-8")
        ch = parse_digest_to_chapter(md, number=1, episode_num=50)
        assert ch.epigraph
        assert ch.sections

    def test_segment_scaffolding_never_reaches_the_book(self):
        for ep in (1, 25, 50):
            ch = _chapter(ep)
            for title, paras in ch.sections:
                assert not re.match(r"(?i)segment\s+\d", title)
                for p in paras:
                    assert "### " not in p
                    assert "**" not in p, f"ep{ep}: markdown bold leaked"

    def test_paragraphs_are_unwrapped_prose(self):
        ch = _chapter(50)
        for _, paras in ch.sections:
            for p in paras:
                assert "\n" not in p, "hard-wrap newlines must be collapsed"

    def test_empty_chapter_is_refused(self):
        try:
            parse_digest_to_chapter("no segments here", number=1,
                                    episode_num=999)
        except ValueError:
            pass
        else:
            raise AssertionError("an empty chapter must raise, not ship")


class TestChapterTitles:
    def test_titles_go_through_the_titles_module(self):
        """The titles rule: books clip via engine.titles, never a slice."""
        v = _volume()
        for ch in collect_chapters(v)[:10]:
            assert fits(ch.title, BOOK_CHAPTER_TITLE_MAX), (
                f"chapter {ch.number} title over limit: {ch.title!r}"
            )

    def test_rss_titles_strip_the_ep_prefix(self):
        titles = episode_titles_from_rss(_volume().resolved_rss())
        if not titles:  # feed window may have rolled past early episodes
            return
        for num, title in titles.items():
            assert not title.lower().startswith(f"ep {num}"), title


# ---------------------------------------------------------------------------
# EPUB structure
# ---------------------------------------------------------------------------

class TestEpubStructure:
    def _built(self, tmp_path: Path):
        v = _volume()
        chapters = [_chapter(1, 1), _chapter(2, 2)]
        out = tmp_path / "test.epub"
        return v, chapters, build_epub(v, chapters, out)

    def test_mimetype_is_first_and_stored(self, tmp_path):
        _, _, epub = self._built(tmp_path)
        with zipfile.ZipFile(epub) as z:
            first = z.infolist()[0]
            assert first.filename == "mimetype"
            assert first.compress_type == zipfile.ZIP_STORED
            assert z.read("mimetype") == b"application/epub+zip"

    def test_every_document_is_well_formed_xml(self, tmp_path):
        _, _, epub = self._built(tmp_path)
        with zipfile.ZipFile(epub) as z:
            for name in z.namelist():
                if name.endswith((".xhtml", ".opf", ".xml")):
                    ET.fromstring(z.read(name))

    def test_spine_and_nav_cover_every_chapter(self, tmp_path):
        _, chapters, epub = self._built(tmp_path)
        with zipfile.ZipFile(epub) as z:
            opf = z.read("OEBPS/package.opf").decode("utf-8")
            nav = z.read("OEBPS/nav.xhtml").decode("utf-8")
            for c in chapters:
                assert f"chap_{c.number:03d}.xhtml" in opf
                assert f"chap_{c.number:03d}.xhtml" in nav

    def test_copyright_page_carries_disclosure_and_funnel_link(self, tmp_path):
        _, _, epub = self._built(tmp_path)
        with zipfile.ZipFile(epub) as z:
            page = z.read("OEBPS/copyright.xhtml").decode("utf-8")
        assert "AI assistance" in page
        assert "utm_source=" in page, "back-matter link must be funnel-tagged"
        assert "utm_campaign=nn-unintended_consequences-en-book-ep001" in page


# ---------------------------------------------------------------------------
# Narration text + credits
# ---------------------------------------------------------------------------

class TestNarrationText:
    def test_tts_text_is_clean_prose(self):
        text = chapter_tts_text(_chapter(5))
        assert text.startswith("Chapter 1.")
        for bad in ("**", "###", "](", "<fast>", "[pause]", "<emphasis>"):
            assert bad not in text

    def test_both_credits_carry_the_disclosure(self):
        v = _volume()
        assert AI_NARRATION_DISCLOSURE in opening_credits_text(v)
        assert AI_NARRATION_DISCLOSURE in closing_credits_text(v)

    def test_closing_does_not_echo_the_show_name(self):
        """Title == show name: the closing names 'the podcast' instead of
        repeating 'Unintended Consequences' twice in one sentence."""
        text = closing_credits_text(_volume())
        assert text.count("Unintended Consequences") == 1


# ---------------------------------------------------------------------------
# Audiobook assembly (offline: metadata + command shape)
# ---------------------------------------------------------------------------

class TestAudiobookAssembly:
    def test_ffmetadata_chapter_offsets_accumulate(self):
        from engine.audiobook import _ffmetadata
        tracks = [("One", Path("a.mp3")), ("Two", Path("b.mp3")),
                  ("Three", Path("c.mp3"))]
        durations = {Path("a.mp3"): 10.0, Path("b.mp3"): 20.5,
                     Path("c.mp3"): 5.25}
        meta = _ffmetadata(tracks, durations)
        assert meta.startswith(";FFMETADATA1")
        assert "START=0\nEND=10000" in meta
        assert "START=10000\nEND=30500" in meta
        assert "START=30500\nEND=35750" in meta
        assert meta.count("[CHAPTER]") == 3

    def test_track_list_opens_and_closes_with_credits(self):
        from engine.audiobook import narration_texts
        v = _volume()
        chapters = [_chapter(1, 1)]
        tracks = narration_texts(v, chapters)
        assert tracks[0][0] == "Opening Credits"
        assert tracks[-1][0] == "Closing Credits"
        assert len(tracks) == len(chapters) + 2

    def test_mp3_and_m4b_settings_are_retail_shaped(self):
        from engine.audiobook import M4B_ARGS, MP3_ARGS
        assert "44100" in MP3_ARGS and "192k" in MP3_ARGS
        assert "aac" in M4B_ARGS

    def test_cost_estimate_uses_tracking_rate(self):
        from engine.audiobook import estimate_tts_cost_usd
        from engine.tracking import TTS_PROVIDER_PRICING
        assert estimate_tts_cost_usd(["x" * 1000]) == (
            TTS_PROVIDER_PRICING["grok"]
        )


# ---------------------------------------------------------------------------
# Funnel vocabulary
# ---------------------------------------------------------------------------

class TestFunnelBookKind:
    def test_book_kind_round_trips(self):
        from engine.funnel import campaign_id, parse_campaign_id
        cid = campaign_id("unintended_consequences", 1, kind="book")
        assert cid == "nn-unintended_consequences-en-book-ep001"
        parsed = parse_campaign_id(cid)
        assert parsed is not None and parsed.kind == "book"
        assert parsed.episode == 1

    def test_book_medium_resolves(self):
        from engine.funnel import MEDIUM_BOOK, episode_link
        link = episode_link("https://nerranetwork.com/x.html",
                            "unintended_consequences", 1, kind="book")
        assert f"utm_medium={MEDIUM_BOOK}" in link


# ---------------------------------------------------------------------------
# Volume config + catalog + workflow wiring
# ---------------------------------------------------------------------------

class TestVolumeConfig:
    def test_uc_vol1_loads_and_every_episode_has_a_digest(self):
        v = _volume()
        assert v.volume_number == 1
        assert len(v.episodes) == 50
        for ep in v.episodes:
            assert find_digest(v, ep).exists()

    def test_missing_required_field_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("volume_id: x\nshow_slug: y\n", encoding="utf-8")
        try:
            load_volume(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("incomplete volume config must raise")


class TestCatalog:
    def test_upsert_is_idempotent_by_volume_id(self, tmp_path):
        path = tmp_path / "catalog.json"
        update_catalog({"volume_id": "v1", "show_slug": "a",
                        "volume_number": 1}, catalog_path=path)
        update_catalog({"volume_id": "v1", "show_slug": "a",
                        "volume_number": 1, "word_count": 5},
                       catalog_path=path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data["volumes"]) == 1
        assert data["volumes"][0]["word_count"] == 5


class TestWiring:
    def test_workflow_exists_and_calls_the_builder(self):
        wf = yaml.safe_load(
            (_ROOT / ".github" / "workflows" / "build-book.yml")
            .read_text(encoding="utf-8"))
        assert wf[True]["workflow_dispatch"]["inputs"]["volume"]
        text = (_ROOT / ".github" / "workflows" / "build-book.yml").read_text(
            encoding="utf-8")
        assert "scripts/build_book.py" in text
        assert "tests/test_book_compiler.py" in text
        assert "--books" in text

    def test_build_products_are_gitignored(self):
        gitignore = (_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert "outputs/books/" in gitignore, (
            "book MP3s/EPUBs must never be committed (landmine #1)"
        )

    def test_books_page_generator_exists(self):
        src = (_ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert "def generate_books_page" in src
        assert 'generate_books_page(dry_run=args.dry_run)' in src
        assert '"books.html"' in src, "books.html must be in the sitemap list"

    def test_r2_keyspace_is_books_prefix(self):
        from engine.book_compiler import R2_BOOKS_PREFIX
        assert R2_BOOKS_PREFIX == "books"
        src = (_ROOT / "scripts" / "build_book.py").read_text(encoding="utf-8")
        assert "R2_BOOKS_PREFIX" in src
