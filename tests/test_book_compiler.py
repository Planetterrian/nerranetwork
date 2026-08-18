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

VOL_PATH = (_ROOT / "books" / "volumes" /
            "unintended_consequences_vol1.yaml")


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

    def test_every_chapter_links_back_to_its_episode(self, tmp_path):
        """The book's job includes routing readers to the podcast: each
        chapter ends on a funnel-tagged link to its source episode."""
        _, chapters, epub = self._built(tmp_path)
        with zipfile.ZipFile(epub) as z:
            for c in chapters:
                page = z.read(f"OEBPS/chap_{c.number:03d}.xhtml").decode(
                    "utf-8")
                assert "Hear this story as it first aired" in page
                assert (f"blog/unintended_consequences/"
                        f"ep{c.episode_num:03d}.html") in page
                assert "utm_medium=book" in page

    def test_chapter_images_embed_when_provided(self, tmp_path):
        import io
        from PIL import Image
        v = _volume()
        chapters = [_chapter(1, 1), _chapter(2, 2)]
        buf = io.BytesIO()
        Image.new("RGB", (1000, 570), "#222").save(buf, "JPEG")
        epub = build_epub(v, chapters, tmp_path / "img.epub",
                          chapter_images={1: buf.getvalue()})
        with zipfile.ZipFile(epub) as z:
            assert "OEBPS/art_001.jpg" in z.namelist()
            opf = z.read("OEBPS/package.opf").decode("utf-8")
            assert 'href="art_001.jpg" media-type="image/jpeg"' in opf
            ch1 = z.read("OEBPS/chap_001.xhtml").decode("utf-8")
            assert '<img src="art_001.jpg"' in ch1
            # Chapter 2 got no art: no dangling manifest entry or tag.
            assert "art_002" not in opf
            assert "<img" not in z.read("OEBPS/chap_002.xhtml").decode(
                "utf-8")

    def test_store_title_includes_volume_number(self, tmp_path):
        _, _, epub = self._built(tmp_path)
        with zipfile.ZipFile(epub) as z:
            opf = z.read("OEBPS/package.opf").decode("utf-8")
        assert "Unintended Consequences, Volume 1" in opf


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
    def test_vol1_loads_and_every_episode_has_a_digest(self):
        v = _volume()
        assert v.volume_number == 1
        assert len(v.episodes) == 20
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


class TestSeriesInheritance:
    def test_volume_inherits_author_branding_and_art_config(self):
        v = _volume()
        assert v.author == "Patrick Novak"
        assert v.title == "Unintended Consequences"
        assert v.cover_color == "#B45309"        # show brand amber
        assert v.image_model == "grok-imagine-image-quality"
        assert "no text" in v.chapter_art_style.lower()
        assert "no text" in v.cover_art_style.lower()

    def test_subtitle_counts_the_volume_in_words(self):
        v = _volume()
        assert v.subtitle.startswith("Twenty ")

    def test_full_title_carries_the_volume_number(self):
        assert _volume().full_title == "Unintended Consequences, Volume 1"

    def test_both_series_register_and_stay_in_the_size_band(self):
        from engine.book_compiler import SERIES_DIR, load_series
        slugs = sorted(p.stem for p in SERIES_DIR.glob("*.yaml"))
        assert slugs == ["first_principles", "unintended_consequences"]
        for slug in slugs:
            s = load_series(slug)
            assert s["author"] == "Patrick Novak"
            assert 10 <= int(s["volume_size"]) <= 20

    def test_volume_size_outside_band_raises(self, tmp_path):
        from engine.book_compiler import load_series
        bad = tmp_path / "s.yaml"
        bad.write_text(
            "show_slug: x\nshow_name: X\nseries_title: X\n"
            "author: A\nvolume_size: 50\n", encoding="utf-8")
        try:
            load_series(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("volume_size 50 must be rejected (10-20)")


class TestVolumePlanner:
    def test_planner_is_currently_drained(self):
        """Both series' complete volumes are already cut; the tails
        (UC 81-93, FPD 61-74) are below volume_size and must wait."""
        from engine.book_compiler import plan_next_volumes
        for slug in ("unintended_consequences", "first_principles"):
            assert plan_next_volumes(slug, write=False) == []

    def test_committed_volumes_are_contiguous_and_disjoint(self):
        from engine.book_compiler import VOLUMES_DIR
        by_show = {}
        for p in sorted(VOLUMES_DIR.glob("*.yaml")):
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            by_show.setdefault(data.get("series"), []).extend(
                data["episodes"])
        for slug, eps in by_show.items():
            assert len(eps) == len(set(eps)), f"{slug}: episode in 2 volumes"
            assert eps == sorted(eps)
            assert eps[0] == 1 and eps == list(range(1, len(eps) + 1)), (
                f"{slug}: volumes must cover episodes contiguously from 1"
            )


class TestBookArt:
    def test_prompts_carry_style_and_subject_and_text_ban(self):
        from engine.book_art import chapter_art_prompt, cover_art_prompt
        v = _volume()
        ch = _chapter(1)
        p = chapter_art_prompt(v.chapter_art_style, ch)
        assert "No words" in p or "no text" in p.lower()
        assert (ch.epigraph[:40] in p) or (ch.title[:40] in p)
        cp = cover_art_prompt(v.cover_art_style, v, [ch])
        assert "ONE strong unifying visual metaphor" in cp

    def test_chapter_jpeg_is_resized_and_jpeg(self):
        import io
        from PIL import Image
        from engine.book_art import CHAPTER_IMAGE_WIDTH, to_chapter_jpeg
        buf = io.BytesIO()
        Image.new("RGB", (1792, 1024), "#333").save(buf, "PNG")
        out = Image.open(io.BytesIO(to_chapter_jpeg(buf.getvalue())))
        assert out.format == "JPEG"
        assert out.width == CHAPTER_IMAGE_WIDTH

    def test_cover_composites_art_and_falls_back_without(self, tmp_path):
        import io
        from PIL import Image
        from engine.book_compiler import generate_cover
        v = _volume()
        art = io.BytesIO()
        Image.new("RGB", (1024, 1792), "#654321").save(art, "PNG")
        with_art = generate_cover(v, tmp_path / "a.png",
                                  art_bytes=art.getvalue())
        without = generate_cover(v, tmp_path / "b.png")
        assert Image.open(with_art).size == (1600, 2560)
        assert Image.open(without).size == (1600, 2560)

    def test_gallery_intended_uses_are_invisible_to_scene_selector(self):
        """book_chapter / book_cover must never match the video scene
        selector's intended_use filters (the thumbnail_variant
        precedent) — book art enriches the gallery, not episode
        renders."""
        lib = (_ROOT / "engine" / "gallery_library.py").read_text(
            encoding="utf-8")
        assert "book_chapter" not in lib
        assert "book_cover" not in lib

    def test_quality_model_is_pinned_not_floating(self):
        v = _volume()
        assert not v.image_model.endswith("latest"), (
            "published artifacts never ride floating model aliases"
        )


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
