"""Compile narrative-show episodes into a sellable ebook (EPUB 3) + the
clean chapter text an audiobook is narrated from.

Product B6 from ``docs/product_opportunities_2026_08.md``: the narrative
shows (Unintended Consequences, First Principles Daily) publish evergreen
essays, not news — a volume of them is a book that already exists, one
transform away. The transform here is **deterministic**: the digests were
verified free of podcast-isms ("this episode", "welcome back": 0 hits
across all 93 UC digests at build time), so no LLM pass runs and the
ebook's marginal cost is zero. The audiobook (see ``engine/audiobook.py``)
re-narrates the compiled text with the network's existing Grok voice.

Layout of a volume:

    books/volumes/<volume_id>.yaml   — config (show, episodes, title, links)
    books/catalog.json               — committed catalog the site page renders
    output/books/<volume_id>/        — build products (gitignored; R2 is the
                                       durable store, key prefix books/<id>/)

Chapter source is the committed digest markdown (the same canonical text
the blog renders), NOT the ``_tts.txt`` (which carries spoken-delivery
artifacts). Chapter titles come from the show's RSS feed ("Ep N: <hook>")
clipped through ``engine.titles`` — never sliced here (titles rule).
"""

from __future__ import annotations

import html
import json
import logging
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape as xml_escape

import yaml

from engine.titles import BOOK_CHAPTER_TITLE_MAX, clip_words
from engine.utils import strip_speech_tags

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent

#: Where a finished volume's files live in the R2 bucket. Deliberately its
#: own keyspace — NEVER under an audio show prefix (published podcast
#: enclosures depend on those paths; landmine: R2 bucket paths are frozen).
R2_BOOKS_PREFIX = "books"

_SEGMENT_RE = re.compile(
    r"^#{2,4}\s*Segment\s+(\d+)\s*[—–\-:]\s*(.+?)\s*$", re.MULTILINE
)

#: Segment titles whose body is (only) the episode hook. They become the
#: chapter epigraph rather than a section.
_HOOK_SECTION_TITLES = {"the hook", "the cold open", "cold open", "hook"}

_RSS_TITLE_RE = re.compile(r"<title>\s*Ep\s+(\d+):\s*(.*?)\s*</title>", re.DOTALL)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class BookChapter:
    number: int                      # 1-based position in the volume
    episode_num: int                 # source episode
    title: str                       # clipped, TOC-safe
    epigraph: str = ""               # the full episode hook, if present
    sections: List[Tuple[str, List[str]]] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        words = len(self.epigraph.split())
        for _, paras in self.sections:
            words += sum(len(p.split()) for p in paras)
        return words


@dataclass
class BookVolume:
    volume_id: str
    show_slug: str
    show_name: str
    volume_number: int
    title: str
    subtitle: str = ""
    author: str = "Nerra Network"
    description: str = ""
    language: str = "en"
    episodes: List[int] = field(default_factory=list)
    digest_dir: str = ""             # default: digests/<show_slug>
    rss_file: str = ""               # default: <show_slug>_podcast.rss
    buy_links: Dict[str, str] = field(default_factory=dict)
    price_usd: Optional[float] = None
    keywords: List[str] = field(default_factory=list)
    cover_color: str = "#0f1b2d"     # deep navy default
    cover_accent: str = "#00D4FF"    # Nerra cyan

    def resolved_digest_dir(self) -> Path:
        return ROOT / (self.digest_dir or f"digests/{self.show_slug}")

    def resolved_rss(self) -> Path:
        return ROOT / (self.rss_file or f"{self.show_slug}_podcast.rss")


# ---------------------------------------------------------------------------
# Volume config
# ---------------------------------------------------------------------------

def load_volume(path: str | Path) -> BookVolume:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    required = ("volume_id", "show_slug", "show_name", "volume_number",
                "title", "episodes")
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise ValueError(f"volume config {path} missing fields: {missing}")
    known = {f for f in BookVolume.__dataclass_fields__}
    unknown = sorted(set(data) - known)
    if unknown:
        # The silent-config-drop class (landmine: _build_nested) — warn
        # loudly rather than discard.
        logger.warning("volume config %s has unknown keys (ignored): %s",
                       path, unknown)
    return BookVolume(**{k: v for k, v in data.items() if k in known})


# ---------------------------------------------------------------------------
# Digest -> chapter
# ---------------------------------------------------------------------------

def find_digest(volume: BookVolume, episode_num: int) -> Path:
    pattern = f"*_Ep{episode_num:03d}_*.md"
    matches = sorted(volume.resolved_digest_dir().glob(pattern))
    if not matches:
        raise FileNotFoundError(
            f"no digest for {volume.show_slug} episode {episode_num} "
            f"({volume.resolved_digest_dir()}/{pattern})"
        )
    # A retired-and-regenerated episode can leave two dated files; the
    # newest date is the published one.
    return matches[-1]


def episode_titles_from_rss(rss_path: Path) -> Dict[int, str]:
    """Map episode number -> hook sentence from the feed's item titles.

    The feed's titles were built by ``engine.titles.episode_title`` so
    they are already clean ("Ep N: <hook>"); we strip the numeric prefix
    back off. Episodes that have left the feed window simply aren't in
    the map — callers fall back to the digest's own hook line.
    """
    titles: Dict[int, str] = {}
    if not rss_path.exists():
        return titles
    text = rss_path.read_text(encoding="utf-8")
    for num, title in _RSS_TITLE_RE.findall(text):
        cleaned = html.unescape(title).strip()
        if cleaned:
            titles.setdefault(int(num), cleaned)
    return titles


def _clean_inline(text: str) -> str:
    """Markdown inline debris -> plain prose (bold/italic markers kept
    OUT of the book body; emphasis in flowing prose reads fine without
    them and the audiobook must not see them either)."""
    text = strip_speech_tags(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links -> anchor text
    return text.strip()


def _split_paragraphs(block: str) -> List[str]:
    paras: List[str] = []
    for raw in re.split(r"\n\s*\n", block):
        p = raw.strip()
        if not p or set(p) <= {"-", "—", "–", " "}:
            continue  # horizontal rules / empty
        # Un-hard-wrap: single newlines inside a paragraph are wrapping.
        p = re.sub(r"\s*\n\s*", " ", p)
        p = _clean_inline(p)
        if p:
            paras.append(p)
    return paras


def _extract_blockquote(block: str) -> str:
    """Collapse a leading ``> …`` blockquote into one clean line."""
    lines = [ln.lstrip("> ").strip() for ln in block.splitlines()
             if ln.strip().startswith(">")]
    return _clean_inline(" ".join(ln for ln in lines if ln))


def parse_digest_to_chapter(
    md_text: str,
    *,
    number: int,
    episode_num: int,
    rss_title: str = "",
) -> BookChapter:
    """Deterministic digest-markdown -> chapter transform.

    Handles both digest eras: the leading bare ``> **hook**`` blockquote
    (later episodes) and the hook living inside a "Segment 1 — The Hook"
    section (early episodes). Segment scaffolding ("Segment N —") never
    reaches the book; the editorial section titles do.
    """
    md_text = md_text.replace("\r\n", "\n")

    epigraph = ""
    sections: List[Tuple[str, List[str]]] = []

    matches = list(_SEGMENT_RE.finditer(md_text))
    preamble = md_text[: matches[0].start()] if matches else md_text
    quote = _extract_blockquote(preamble)
    if quote:
        epigraph = quote

    for i, m in enumerate(matches):
        sec_title = _clean_inline(m.group(2))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        body = md_text[m.end():end]
        if sec_title.lower() in _HOOK_SECTION_TITLES:
            hook = _extract_blockquote(body) or " ".join(_split_paragraphs(body))
            if hook and not epigraph:
                epigraph = hook
            continue
        paras = _split_paragraphs(body)
        if paras:
            sections.append((sec_title, paras))

    if not sections:
        raise ValueError(
            f"episode {episode_num}: no segment sections parsed — digest "
            "format changed? Refusing to ship an empty chapter."
        )

    title_source = rss_title or epigraph or sections[0][0]
    title = clip_words(title_source, BOOK_CHAPTER_TITLE_MAX)

    return BookChapter(
        number=number,
        episode_num=episode_num,
        title=title,
        epigraph=epigraph,
        sections=sections,
    )


def collect_chapters(volume: BookVolume) -> List[BookChapter]:
    rss_titles = episode_titles_from_rss(volume.resolved_rss())
    chapters: List[BookChapter] = []
    for idx, ep in enumerate(volume.episodes, start=1):
        digest = find_digest(volume, ep)
        chapters.append(parse_digest_to_chapter(
            digest.read_text(encoding="utf-8"),
            number=idx,
            episode_num=ep,
            rss_title=rss_titles.get(ep, ""),
        ))
    return chapters


# ---------------------------------------------------------------------------
# Audiobook narration text
# ---------------------------------------------------------------------------

#: Spoken on every audiobook, non-negotiable: the network disclosure
#: policy applies to paid products exactly as it does to free episodes,
#: and every retail channel that accepts digital narration requires it.
AI_NARRATION_DISCLOSURE = (
    "This audiobook is narrated by a digital voice."
)


def chapter_tts_text(chapter: BookChapter) -> str:
    """Plain narration text for one chapter — no markdown, no tags."""
    parts = [f"Chapter {chapter.number}. {chapter.title.rstrip('.…')}."]
    if chapter.epigraph:
        parts.append(chapter.epigraph)
    for sec_title, paras in chapter.sections:
        parts.append(f"{sec_title.rstrip('.')}.")
        parts.extend(paras)
    return "\n\n".join(strip_speech_tags(p) for p in parts)


def opening_credits_text(volume: BookVolume) -> str:
    bits = [volume.title.rstrip(".") + "."]
    if volume.subtitle:
        bits.append(volume.subtitle.rstrip(".") + ".")
    bits.append(f"Written and produced by {volume.author}.")
    bits.append(AI_NARRATION_DISCLOSURE)
    return " ".join(bits)


def closing_credits_text(volume: BookVolume) -> str:
    # When the book carries the show's own name, "began as an episode of
    # <same name>" reads as an echo — name the source generically instead.
    source = ("the podcast"
              if volume.show_name.lower() in volume.title.lower()
              else volume.show_name)
    return (
        f"This has been {volume.title.rstrip('.')}, from {volume.author}. "
        f"Every story in this collection began as an episode of "
        f"{source}, free wherever you get podcasts. "
        f"{AI_NARRATION_DISCLOSURE} "
        "Find the whole network at nerra network dot com."
    )


# ---------------------------------------------------------------------------
# EPUB 3
# ---------------------------------------------------------------------------

_EPUB_CSS = """\
body { font-family: Georgia, 'Times New Roman', serif; line-height: 1.55;
       margin: 0 5%; }
h1 { font-size: 1.5em; margin: 2em 0 0.2em; line-height: 1.25; }
h2 { font-size: 1.05em; margin: 1.6em 0 0.4em; letter-spacing: 0.04em;
     text-transform: uppercase; }
p { margin: 0 0 0.9em; text-align: justify; }
.epigraph { font-style: italic; margin: 1em 0 2em; color: #444; }
.chapnum { font-size: 0.85em; letter-spacing: 0.15em; color: #666;
           text-transform: uppercase; margin-top: 3em; }
.frontmatter p { text-align: left; }
.titlepage { text-align: center; margin-top: 20%; }
.titlepage h1 { font-size: 2em; }
.titlepage .subtitle { font-style: italic; margin-top: 1em; }
.titlepage .author { margin-top: 3em; letter-spacing: 0.1em;
                     text-transform: uppercase; }
"""


def _xhtml(title: str, body: str, lang: str = "en") -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml" '
        f'xmlns:epub="http://www.idpf.org/2007/ops" '
        f'xml:lang="{lang}" lang="{lang}">\n'
        f"<head><title>{xml_escape(title)}</title>"
        '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
        f"<body>{body}</body>\n</html>\n"
    )


def _chapter_xhtml(chapter: BookChapter, lang: str) -> str:
    parts = [
        f'<p class="chapnum">Chapter {chapter.number}</p>',
        f"<h1>{xml_escape(chapter.title)}</h1>",
    ]
    if chapter.epigraph:
        parts.append(f'<p class="epigraph">{xml_escape(chapter.epigraph)}</p>')
    for sec_title, paras in chapter.sections:
        parts.append(f"<h2>{xml_escape(sec_title)}</h2>")
        parts.extend(f"<p>{xml_escape(p)}</p>" for p in paras)
    return _xhtml(chapter.title, "\n".join(parts), lang)


def _title_page_xhtml(volume: BookVolume) -> str:
    body = [
        '<div class="titlepage">',
        f"<h1>{xml_escape(volume.title)}</h1>",
    ]
    if volume.subtitle:
        body.append(f'<p class="subtitle">{xml_escape(volume.subtitle)}</p>')
    body.append(f'<p class="author">{xml_escape(volume.author)}</p>')
    body.append("</div>")
    return _xhtml(volume.title, "\n".join(body), volume.language)


def _about_link(volume: BookVolume) -> str:
    """The back-matter link to the show page — funnel-tagged through
    engine.funnel (the only module allowed to build campaign links)."""
    from engine.funnel import PLACEMENT_BODY, episode_link
    page = volume.show_slug.replace("_", "-")
    return episode_link(
        f"https://nerranetwork.com/{page}.html",
        volume.show_slug,
        volume.volume_number,
        kind="book",
        placement=PLACEMENT_BODY,
    )


def _copyright_xhtml(volume: BookVolume) -> str:
    year = date.today().year
    link = _about_link(volume)
    body = (
        '<div class="frontmatter">'
        f"<p>Copyright © {year} {xml_escape(volume.author)}. "
        "All rights reserved.</p>"
        "<p>The stories in this collection were first published as "
        f"episodes of <i>{xml_escape(volume.show_name)}</i>, a Nerra "
        "Network podcast, where they remain free to listen to. This "
        "collection was produced with AI assistance and reviewed for "
        "publication.</p>"
        f'<p>Hear every story, and the ones that came after, at '
        f'<a href="{xml_escape(link)}">nerranetwork.com</a>.</p>'
        "</div>"
    )
    return _xhtml("Copyright", body, volume.language)


def _nav_xhtml(volume: BookVolume, chapters: List[BookChapter]) -> str:
    items = [
        '<li><a href="titlepage.xhtml">Title Page</a></li>',
        '<li><a href="copyright.xhtml">Copyright</a></li>',
    ]
    items += [
        f'<li><a href="chap_{c.number:03d}.xhtml">'
        f"{xml_escape(c.title)}</a></li>"
        for c in chapters
    ]
    body = (
        '<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>'
        + "".join(items) + "</ol></nav>"
    )
    return _xhtml("Contents", body, volume.language)


def _package_opf(volume: BookVolume, chapters: List[BookChapter],
                 *, has_cover: bool) -> str:
    uid = f"urn:nerranetwork:book:{volume.volume_id}"
    modified = date.today().isoformat() + "T00:00:00Z"
    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
        'properties="nav"/>',
        '<item id="css" href="style.css" media-type="text/css"/>',
        '<item id="titlepage" href="titlepage.xhtml" '
        'media-type="application/xhtml+xml"/>',
        '<item id="copyright" href="copyright.xhtml" '
        'media-type="application/xhtml+xml"/>',
    ]
    spine = ['<itemref idref="titlepage"/>', '<itemref idref="copyright"/>']
    if has_cover:
        manifest.append(
            '<item id="cover-image" href="cover.png" media-type="image/png" '
            'properties="cover-image"/>'
        )
    for c in chapters:
        cid = f"chap{c.number:03d}"
        manifest.append(
            f'<item id="{cid}" href="chap_{c.number:03d}.xhtml" '
            'media-type="application/xhtml+xml"/>'
        )
        spine.append(f'<itemref idref="{cid}"/>')
    meta_title = xml_escape(volume.title)
    if volume.subtitle:
        meta_title += f": {xml_escape(volume.subtitle)}"
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        'unique-identifier="uid">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'<dc:identifier id="uid">{uid}</dc:identifier>\n'
        f"<dc:title>{meta_title}</dc:title>\n"
        f"<dc:language>{volume.language}</dc:language>\n"
        f"<dc:creator>{xml_escape(volume.author)}</dc:creator>\n"
        f"<dc:description>{xml_escape(volume.description)}</dc:description>\n"
        f'<meta property="dcterms:modified">{modified}</meta>\n'
        "</metadata>\n"
        "<manifest>\n" + "\n".join(manifest) + "\n</manifest>\n"
        '<spine>\n' + "\n".join(spine) + "\n</spine>\n"
        "</package>\n"
    )


def build_epub(
    volume: BookVolume,
    chapters: List[BookChapter],
    out_path: Path,
    *,
    cover_png: Optional[Path] = None,
) -> Path:
    """Assemble a store-ready EPUB 3. Hand-rolled (zip + XHTML) so the
    pipeline gains no new dependency; the structure follows the EPUB 3.3
    packaging spec (mimetype first + stored, container.xml, package.opf
    with a nav document)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    has_cover = bool(cover_png and Path(cover_png).exists())
    with zipfile.ZipFile(out_path, "w") as z:
        # Spec: first entry, uncompressed, exact bytes.
        z.writestr(
            zipfile.ZipInfo("mimetype"), "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        z.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/package.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles>'
            "</container>",
        )
        z.writestr("OEBPS/package.opf",
                   _package_opf(volume, chapters, has_cover=has_cover))
        z.writestr("OEBPS/nav.xhtml", _nav_xhtml(volume, chapters))
        z.writestr("OEBPS/style.css", _EPUB_CSS)
        z.writestr("OEBPS/titlepage.xhtml", _title_page_xhtml(volume))
        z.writestr("OEBPS/copyright.xhtml", _copyright_xhtml(volume))
        if has_cover:
            z.write(cover_png, "OEBPS/cover.png")
        for c in chapters:
            z.writestr(f"OEBPS/chap_{c.number:03d}.xhtml",
                       _chapter_xhtml(c, volume.language))
    logger.info("EPUB written: %s (%d chapters, %d words)",
                out_path, len(chapters), sum(c.word_count for c in chapters))
    return out_path


# ---------------------------------------------------------------------------
# Cover
# ---------------------------------------------------------------------------

def generate_cover(volume: BookVolume, out_png: Path,
                   *, size: Tuple[int, int] = (1600, 2560)) -> Path:
    """Typographic cover at KDP's recommended 1600x2560. Deliberately
    text-only (no Grok Imagine spend); the operator can replace the PNG
    before store submission if a designed cover is worth it."""
    from PIL import Image, ImageDraw, ImageFont

    w, h = size
    img = Image.new("RGB", size, volume.cover_color)
    draw = ImageDraw.Draw(img)

    def _font(px: int):
        for name in ("DejaVuSerif-Bold.ttf", "DejaVuSerif.ttf",
                     "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, px)
            except OSError:
                continue
        return ImageFont.load_default()

    def _wrap(text: str, font, max_w: int) -> List[str]:
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if draw.textlength(trial, font=font) <= max_w or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    margin = int(w * 0.1)
    max_text_w = w - 2 * margin

    # Title block — shrink-to-fit (same pattern as the thumbnail autofit).
    title_px = 160
    while title_px > 72:
        font = _font(title_px)
        lines = _wrap(volume.title, font, max_text_w)
        if len(lines) <= 5:
            break
        title_px -= 12
    font = _font(title_px)
    lines = _wrap(volume.title, font, max_text_w)
    y = int(h * 0.16)
    for ln in lines:
        draw.text((w // 2, y), ln, font=font, fill="#f5f2ea", anchor="ma")
        y += int(title_px * 1.18)

    # Accent rule.
    y += int(h * 0.02)
    draw.rectangle([margin, y, w - margin, y + 8], fill=volume.cover_accent)
    y += int(h * 0.035)

    if volume.subtitle:
        sub_font = _font(64)
        for ln in _wrap(volume.subtitle, sub_font, max_text_w):
            draw.text((w // 2, y), ln, font=sub_font, fill="#c9d4e0",
                      anchor="ma")
            y += 80

    author_font = _font(72)
    draw.text((w // 2, int(h * 0.86)), volume.author.upper(),
              font=author_font, fill="#f5f2ea", anchor="ma")
    series_font = _font(44)
    draw.text((w // 2, int(h * 0.92)),
              f"Volume {volume.volume_number} · {volume.show_name}",
              font=series_font, fill="#8fa3b8", anchor="ma")

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png, "PNG")
    return out_png


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

CATALOG_PATH = ROOT / "books" / "catalog.json"


def update_catalog(entry: Dict, *, catalog_path: Path = None) -> Dict:
    """Idempotent upsert by ``volume_id`` into books/catalog.json.

    The catalog is the committed source the website's Books page and any
    future dashboard card render from; R2 holds the artifacts, the repo
    holds the metadata (same split as the gallery)."""
    path = Path(catalog_path) if catalog_path else CATALOG_PATH
    catalog = {"volumes": []}
    if path.exists():
        catalog = json.loads(path.read_text(encoding="utf-8"))
    volumes = [v for v in catalog.get("volumes", [])
               if v.get("volume_id") != entry.get("volume_id")]
    volumes.append(entry)
    volumes.sort(key=lambda v: (v.get("show_slug", ""),
                                v.get("volume_number", 0)))
    catalog["volumes"] = volumes
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return catalog
