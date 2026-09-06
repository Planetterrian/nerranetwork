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
    episode_date: str = ""           # YYYY-MM-DD from the digest filename
    image_name: str = ""             # EPUB-internal filename when art exists
    #: Verified claim-ledger entries from the episode's committed
    #: ``*_claims.json`` sidecar (engine.claims, Aug 2026). Episodes
    #: published before the ledger existed have none — the sources page
    #: renders only what was actually verified, never a reconstruction.
    claims: List[Dict] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        words = len(self.epigraph.split())
        for _, paras in self.sections:
            words += sum(len(p.split()) for p in paras)
        return words

    @property
    def heading(self) -> str:
        """Printed heading / TOC entry / audiobook chapter-marker name.
        Deliberately NEVER spoken — narration says only "Chapter N." so a
        title edit can re-mux metadata without re-narrating audio."""
        if self.title:
            return f"Chapter {self.number} · {self.title}"
        return f"Chapter {self.number}"


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
    #: Curated short chapter titles keyed by EPISODE number. Written by a
    #: person (or reviewed in a PR); never derived from the hook — see
    #: parse_digest_to_chapter. Missing entries print as bare "Chapter N".
    chapter_titles: Dict[int, str] = field(default_factory=dict)
    digest_dir: str = ""             # default: digests/<show_slug>
    rss_file: str = ""               # default: <show_slug>_podcast.rss
    buy_links: Dict[str, str] = field(default_factory=dict)
    price_usd: Optional[float] = None
    keywords: List[str] = field(default_factory=list)
    cover_color: str = "#0f1b2d"     # deep navy default
    cover_accent: str = "#00D4FF"    # Nerra cyan
    # Series-inherited art config (empty = art generation disabled).
    image_model: str = ""
    chapter_art_style: str = ""
    cover_art_style: str = ""
    # ---- Combined-volume / front-matter machinery (WO-6, Aug 2026) ----
    #: Optional part groupings: a list of {title: str, episodes: [int]}
    #: mappings. When set, the episodes across parts must exactly
    #: partition the volume's episode list (validated at load); the EPUB
    #: gains part-title pages and the TOC nests chapters under parts.
    #: Empty = single-volume behavior unchanged.
    parts: List[Dict] = field(default_factory=list)
    #: Authored prose files (paths relative to repo root), NOT generated:
    #: an introduction and conclusion per volume, and a series-inherited
    #: author bio. Empty = page omitted.
    introduction_file: str = ""
    conclusion_file: str = ""
    author_bio_file: str = ""
    #: Hidden from the public Books page (still built, still in the
    #: catalog — bundle/direct extras). The bigger-books shift unlisted
    #: the pamphlet-thin numbered volumes; the collected editions are
    #: the store products.
    unlisted: bool = False
    #: True for a combined/best-of volume that REUSES episodes already
    #: published in the numbered volumes. Anthologies are exempt from the
    #: contiguous/disjoint coverage invariant and from the planner's
    #: covered-set arithmetic concerns; full_title drops the
    #: ", Volume N" suffix.
    anthology: bool = False
    #: Cover re-roll knob (WO-7). cover_art_prompt() is deterministic —
    #: same style + volume + chapter titles returns the byte-identical
    #: image from Grok Imagine (UC Vol 1's cover matched md5 across two
    #: cold-cache CI runs), so "re-run the workflow" NEVER re-rolls a
    #: cover; it re-bills for the same image. Set/bump this in the
    #: volume YAML to get a genuinely fresh cover; the committed value
    #: keeps the shipped cover reproducible. Empty = legacy prompt.
    cover_variant: str = ""

    def resolved_digest_dir(self) -> Path:
        return ROOT / (self.digest_dir or f"digests/{self.show_slug}")

    def resolved_rss(self) -> Path:
        return ROOT / (self.rss_file or f"{self.show_slug}_podcast.rss")

    @property
    def full_title(self) -> str:
        """Store-listing title: series title + volume number (bare title
        for anthologies — a combined edition is not Volume N)."""
        if self.anthology:
            return self.title
        return f"{self.title}, Volume {self.volume_number}"

    @property
    def built_date_hint(self) -> str:
        return date.today().isoformat()


# ---------------------------------------------------------------------------
# Series + volume config
# ---------------------------------------------------------------------------

SERIES_DIR = ROOT / "books" / "series"
VOLUMES_DIR = ROOT / "books" / "volumes"

#: Series-level keys a volume inherits. ``subtitle`` is derived from
#: ``subtitle_template`` at load time so per-volume story counts read
#: naturally ("Twenty true stories…", "Fourteen…").
_SERIES_INHERITED = (
    "show_slug", "show_name", "author", "language", "description",
    "price_usd", "keywords", "cover_color", "cover_accent",
    "image_model", "chapter_art_style", "cover_art_style",
    "author_bio_file",
)


def load_series(slug_or_path: str | Path) -> Dict:
    path = Path(slug_or_path)
    if not path.suffix:
        path = SERIES_DIR / f"{slug_or_path}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    required = ("show_slug", "show_name", "series_title", "author",
                "volume_size")
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise ValueError(f"series config {path} missing fields: {missing}")
    size = int(data["volume_size"])
    # Band widened 10-20 -> 10-60 (Aug 2026, operator-directed): the
    # 20-chapter volumes the planner cut came out at 12-24k words —
    # pamphlet-length at store prices. Future auto-planned volumes are
    # book-length annual collections (volume_size ~50 => ~40-55k words
    # at current chapter lengths).
    if not 10 <= size <= 60:
        raise ValueError(
            f"series {data['show_slug']}: volume_size {size} outside the "
            "10-60 stories-per-volume band"
        )
    return data


def _subtitle_for(series: Dict, count: int) -> str:
    template = series.get("subtitle_template", "")
    if not template:
        return ""
    from engine.utils import number_to_words
    words = number_to_words(count)
    return template.format(
        count_words=words[:1].upper() + words[1:], count=count)


def load_volume(path: str | Path) -> BookVolume:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    series_slug = data.pop("series", "")
    if series_slug:
        series = load_series(series_slug)
        merged: Dict = {k: series[k] for k in _SERIES_INHERITED
                        if k in series}
        merged["title"] = series["series_title"]
        merged["subtitle"] = _subtitle_for(
            series, len(data.get("episodes", [])))
        # Volume file wins on any key it sets explicitly.
        merged.update(data)
        data = merged

    required = ("volume_id", "show_slug", "show_name", "volume_number",
                "title", "episodes")
    # volume_number 0 is legal (anthology) — absent/empty is missing,
    # falsy-but-present is not.
    missing = [k for k in required
               if data.get(k) is None or data.get(k) in ("", [])]
    if missing:
        raise ValueError(f"volume config {path} missing fields: {missing}")
    known = {f for f in BookVolume.__dataclass_fields__}
    unknown = sorted(set(data) - known)
    if unknown:
        # The silent-config-drop class (landmine: _build_nested) — warn
        # loudly rather than discard.
        logger.warning("volume config %s has unknown keys (ignored): %s",
                       path, unknown)
    vol = BookVolume(**{k: v for k, v in data.items() if k in known})
    # YAML may deliver chapter_titles keys as ints or strings; normalize
    # to int so lookups by episode number always hit.
    vol.chapter_titles = {int(k): str(v).strip()
                          for k, v in (vol.chapter_titles or {}).items()
                          if str(v).strip()}
    if vol.parts:
        vol.parts = [
            {"title": str(p.get("title", "")).strip(),
             "episodes": [int(e) for e in (p.get("episodes") or [])]}
            for p in vol.parts
        ]
        part_eps = [e for p in vol.parts for e in p["episodes"]]
        if sorted(part_eps) != sorted(int(e) for e in vol.episodes) or \
                len(part_eps) != len(set(part_eps)):
            raise ValueError(
                f"volume config {path}: parts must exactly partition the "
                "episode list (every episode in exactly one part)")
        if any(not p["title"] for p in vol.parts):
            raise ValueError(f"volume config {path}: every part needs a title")
    return vol


def resolve_parts(volume: BookVolume,
                  chapters: List[BookChapter]) -> Optional[List[Tuple[str, List[BookChapter]]]]:
    """(part_title, chapters) in reading order, or None when no parts.

    Chapter numbering (1..N) already follows the volume's episode order;
    parts just group them, so the volume's ``episodes:`` list must be in
    reading order and the parts must follow it — validated here.
    """
    if not volume.parts:
        return None
    by_ep = {c.episode_num: c for c in chapters}
    layout: List[Tuple[str, List[BookChapter]]] = []
    for part in volume.parts:
        # Tolerate a chapter SUBSET: the free-sample EPUB builds from
        # chapters[:1], so a part may reference episodes not present.
        # (The full partition is validated at load_volume; the KeyError
        # here killed the first collected-edition CI build.)
        chs = [by_ep[e] for e in part["episodes"] if e in by_ep]
        if chs:
            layout.append((part["title"], chs))
    if not layout:
        return None
    flat = [c.number for _, chs in layout for c in chs]
    if flat != sorted(flat):
        raise ValueError(
            f"volume {volume.volume_id}: parts out of reading order — the "
            "episodes: list defines chapter numbering and the parts must "
            "follow it")
    return layout


def _load_prose_file(path_str: str) -> str:
    """Authored front/back-matter prose (repo-relative path), '' if unset."""
    if not str(path_str or "").strip():
        return ""
    path = ROOT / path_str
    if not path.exists():
        raise FileNotFoundError(
            f"authored prose file missing: {path_str} — front matter is "
            "written by a person, never generated; fix the path or drop "
            "the field")
    return path.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# Volume planner — the automated pipeline of volumes
# ---------------------------------------------------------------------------

def _available_episode_numbers(series: Dict) -> List[int]:
    digest_dir = ROOT / f"digests/{series['show_slug']}"
    nums = set()
    for p in digest_dir.glob("*_Ep[0-9][0-9][0-9]_*.md"):
        m = re.search(r"_Ep(\d{3})_", p.name)
        if m:
            nums.add(int(m.group(1)))
    return sorted(nums)


def _episodes_already_in_volumes(show_slug: str) -> set:
    covered: set = set()
    for p in sorted(VOLUMES_DIR.glob("*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        slug = data.get("show_slug") or data.get("series", "")
        if slug == show_slug:
            covered.update(int(e) for e in data.get("episodes", []))
    return covered


def _max_volume_number(show_slug: str) -> int:
    highest = 0
    for p in sorted(VOLUMES_DIR.glob("*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        slug = data.get("show_slug") or data.get("series", "")
        if slug == show_slug:
            highest = max(highest, int(data.get("volume_number", 0)))
    return highest


def plan_next_volumes(series_slug: str, *, write: bool = True) -> List[Path]:
    """Cut the next volume config(s) from episodes not yet in any volume.

    Only FULL volumes are cut (a partial tail waits for the show to
    publish more episodes), episodes are consumed in broadcast order,
    and existing volume files are never modified — the planner is
    append-only, so a published volume's contents can never drift.
    Returns the volume YAML paths it wrote (or would write).
    """
    series = load_series(series_slug)
    size = int(series["volume_size"])
    covered = _episodes_already_in_volumes(series["show_slug"])
    # Episodes editorially excluded from BOOKS (the podcast episodes stay
    # published). Without this, an episode removed from a volume config
    # (the WO-3 chapter cuts) would look uncollected and the planner
    # would sweep it into the FRONT of the next volume.
    excluded = {int(e) for e in series.get("excluded_episodes", []) or []}
    pending = [n for n in _available_episode_numbers(series)
               if n not in covered and n not in excluded]

    written: List[Path] = []
    next_num = _max_volume_number(series["show_slug"]) + 1
    while len(pending) >= size:
        block, pending = pending[:size], pending[size:]
        vol_id = f"{series_slug}_vol{next_num}"
        out = VOLUMES_DIR / f"{vol_id}.yaml"
        if out.exists():
            raise RuntimeError(f"planner refuses to overwrite {out}")
        doc = {
            "volume_id": vol_id,
            "series": series_slug,
            "volume_number": next_num,
            "episodes": block,
            # Curated short titles (2-5 words) per episode — REQUIRED
            # before store submission; empty prints as bare "Chapter N".
            # Never paste the episode hook here: hooks are full sentences
            # and truncate in store TOCs (the 2026-08-22 launch blocker).
            "chapter_titles": {ep: "" for ep in block},
            "buy_links": {k: "" for k in
                          ("direct", "amazon", "apple_books",
                           "google_play", "kobo", "spotify")},
        }
        if write:
            header = (
                f"# {series['series_title']}, Volume {next_num} — "
                f"episodes {block[0]}-{block[-1]}.\n"
                "# Generated by plan_next_volumes(); branding/title/author "
                "inherit from\n"
                f"# books/series/{series_slug}.yaml. Paste store URLs into "
                "buy_links as\n# listings go live.\n"
            )
            out.write_text(
                header + yaml.safe_dump(doc, sort_keys=False,
                                        allow_unicode=True),
                encoding="utf-8")
        written.append(out)
        logger.info("planned %s: episodes %d-%d", vol_id, block[0],
                    block[-1])
        next_num += 1
    if not written:
        logger.info("series %s: %d uncollected episode(s), below the "
                    "volume size %d — nothing to plan",
                    series_slug, len(pending), size)
    return written


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
    title: str = "",
) -> BookChapter:
    """Deterministic digest-markdown -> chapter transform.

    Handles both digest eras: the leading bare ``> **hook**`` blockquote
    (later episodes) and the hook living inside a "Segment 1 — The Hook"
    section (early episodes). Segment scaffolding ("Segment N —") never
    reaches the book; the editorial section titles do.

    *title* is the CURATED short chapter title from the volume YAML's
    ``chapter_titles`` map — never derived from the episode hook. The
    hook is a full podcast sentence; clipping it produced truncated
    "Delhi's British government paid for dead cobras to cut snake…"
    TOC entries on the first store submission attempt (2026-08-22).
    With no curated title the chapter prints as bare "Chapter N" (a
    normal essay-collection convention) and the hook survives as the
    epigraph either way.
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

    return BookChapter(
        number=number,
        episode_num=episode_num,
        title=clip_words(title, BOOK_CHAPTER_TITLE_MAX) if title else "",
        epigraph=epigraph,
        sections=sections,
    )


def collect_chapters(volume: BookVolume) -> List[BookChapter]:
    chapters: List[BookChapter] = []
    curated = volume.chapter_titles or {}
    missing = [ep for ep in volume.episodes if not curated.get(ep)]
    if missing:
        # Loud, not fatal: bare "Chapter N" is an acceptable convention,
        # but a planner-fresh volume should get its titles written before
        # store submission.
        logger.warning(
            "volume %s: no curated chapter_titles for episode(s) %s — "
            "those chapters print as bare 'Chapter N'",
            volume.volume_id, missing,
        )
    for idx, ep in enumerate(volume.episodes, start=1):
        digest = find_digest(volume, ep)
        chapter = parse_digest_to_chapter(
            digest.read_text(encoding="utf-8"),
            number=idx,
            episode_num=ep,
            title=str(curated.get(ep) or "").strip(),
        )
        m = re.search(r"_(\d{4})(\d{2})(\d{2})", digest.name)
        if m:
            chapter.episode_date = "-".join(m.groups())
        # Inherit the episode's verified claim ledger (engine.claims
        # sidecar) so the volume gets a real sources page for free.
        try:
            from engine.claims import load_ledger
            chapter.claims = load_ledger(digest)
        except Exception as exc:  # noqa: BLE001 — never block a build on this
            logger.warning("claims sidecar unreadable for ep %s: %s", ep, exc)
        chapters.append(chapter)
    return chapters


# ---------------------------------------------------------------------------
# Audiobook narration text
# ---------------------------------------------------------------------------

#: Store-level digital-narration DECLARATIONS are non-negotiable and
#: live at upload time (KDP questionnaire, Spotify's ticked box, Google
#: Play's declaration — never remove those). No retail channel requires
#: a SPOKEN in-file disclosure line, though — an earlier comment here
#: claimed "every retail channel that accepts digital narration
#: requires it", which conflated the upload declaration with a line in
#: the audio. The spoken credits dropped the line in Aug 2026 (WO-8,
#: operator-directed); the constant remains for any surface that wants
#: the canonical wording (e.g. store listing copy).
AI_NARRATION_DISCLOSURE = (
    "This audiobook is narrated by a digital voice."
)


def chapter_tts_text(chapter: BookChapter) -> str:
    """Plain narration text for one chapter — no markdown, no tags."""
    # Spoken form is JUST the number — deliberately decoupled from the
    # printed title so title edits never invalidate narrated audio.
    parts = [f"Chapter {chapter.number}."]
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
        f"{source}, available wherever you get podcasts. "
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
.chapart { margin: 1.2em 0; text-align: center; }
.chapart img { max-width: 100%; border-radius: 4px; }
.listen { margin-top: 2.2em; padding-top: 0.9em; border-top: 1px dashed
          #999; font-size: 0.92em; color: #444; text-align: left; }
.chapnum { font-size: 0.85em; letter-spacing: 0.15em; color: #666;
           text-transform: uppercase; margin-top: 3em; }
.frontmatter p { text-align: left; }
.titlepage { text-align: center; margin-top: 20%; }
.titlepage h1 { font-size: 2em; }
.titlepage .subtitle { font-style: italic; margin-top: 1em; }
.titlepage .author { margin-top: 3em; letter-spacing: 0.1em;
                     text-transform: uppercase; }
.partpage { text-align: center; margin-top: 30%; }
.partpage .partnum { font-size: 0.9em; letter-spacing: 0.2em; color: #666;
                     text-transform: uppercase; }
.partpage h1 { font-size: 1.8em; margin-top: 0.4em; }
.tocpage h2 { margin-top: 1.4em; }
.tocentry { text-align: left; margin: 0 0 0.7em; }
.tocdesc { font-style: italic; color: #444; }
.frontmatter-page p { text-align: justify; }
.alsoby-entry { text-align: left; margin: 0 0 0.9em; }
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


def _episode_page_link(volume: BookVolume, chapter: BookChapter) -> str:
    """Funnel-tagged link to the chapter's source episode page — every
    chapter routes readers back to the podcast (engine.funnel owns the
    tagging; campaign carries the VOLUME number)."""
    from engine.funnel import PLACEMENT_BODY, episode_link
    url = (f"https://nerranetwork.com/blog/{volume.show_slug}/"
           f"ep{chapter.episode_num:03d}.html")
    return episode_link(url, volume.show_slug, volume.volume_number,
                        kind="book", placement=PLACEMENT_BODY)


def _chapter_xhtml(chapter: BookChapter, lang: str,
                   volume: Optional[BookVolume] = None) -> str:
    parts = [f'<p class="chapnum">Chapter {chapter.number}</p>']
    if chapter.title:
        parts.append(f"<h1>{xml_escape(chapter.title)}</h1>")
    if chapter.image_name:
        parts.append(
            f'<p class="chapart"><img src="{xml_escape(chapter.image_name)}" '
            f'alt="{xml_escape(chapter.title)}"/></p>'
        )
    if chapter.epigraph:
        parts.append(f'<p class="epigraph">{xml_escape(chapter.epigraph)}</p>')
    for sec_title, paras in chapter.sections:
        parts.append(f"<h2>{xml_escape(sec_title)}</h2>")
        parts.extend(f"<p>{xml_escape(p)}</p>" for p in paras)
    if volume is not None:
        link = _episode_page_link(volume, chapter)
        parts.append(
            f'<p class="listen">♪ Hear this story as it first aired: '
            f'<a href="{xml_escape(link)}">episode '
            f"{chapter.episode_num} of {xml_escape(volume.show_name)}</a>, "
            "wherever you get podcasts.</p>"
        )
    return _xhtml(chapter.heading, "\n".join(parts), lang)


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
        "Network podcast. Researched and directed by the author, with "
        "AI assistance in drafting, and reviewed before publication.</p>"
        f'<p>Hear every story, and the ones that came after, at '
        f'<a href="{xml_escape(link)}">nerranetwork.com</a>.</p>'
        "</div>"
    )
    return _xhtml("Copyright", body, volume.language)


def _has_sources(chapters: List[BookChapter]) -> bool:
    return any(c.claims for c in chapters)


def _sources_xhtml(volume: BookVolume, chapters: List[BookChapter]) -> str:
    """Endnotes rendered from the episodes' verified claim ledgers.

    Every entry here passed the source-integrity gate at publish time
    (URL resolved, supporting quote found in the source) — this page is
    the ledger made reader-visible, not an authoring step. URLs are
    deduped across the volume; a source cited by several chapters is
    listed where it first appears.
    """
    seen_urls: set = set()
    parts = [
        "<h1>Sources</h1>",
        "<p>The specific studies, reports and statistics cited in these "
        "chapters were verified against the sources below when each story "
        "was first published. Where a chapter speaks in general terms, it "
        "is because a claim could not be traced to a source we could "
        "check.</p>",
    ]
    for c in chapters:
        entries = []
        for claim in c.claims:
            url = str(claim.get("source_url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            title = str(claim.get("source_title") or "").strip() or url
            entries.append(
                f"<li>{xml_escape(title)} — "
                f'<a href="{xml_escape(url)}">{xml_escape(url)}</a></li>'
            )
        if entries:
            parts.append(f"<h2>{xml_escape(c.heading)}</h2>")
            parts.append("<ol>" + "".join(entries) + "</ol>")
    return _xhtml("Sources", "\n".join(parts), volume.language)


def _prose_xhtml(title: str, prose: str, lang: str,
                 css_class: str = "frontmatter-page") -> str:
    """Render authored markdown-lite prose (paragraphs on blank lines,
    ``#``/``##`` headings) as a simple page. Emphasis markers are kept
    out of the rendered text the same way chapter prose handles them."""
    parts = [f'<div class="{css_class}">', f"<h1>{xml_escape(title)}</h1>"]
    for block in re.split(r"\n\s*\n", prose):
        block = block.strip()
        if not block:
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", block)
        if m:
            parts.append(f"<h2>{xml_escape(_clean_inline(m.group(2)))}</h2>")
            continue
        text = re.sub(r"\s*\n\s*", " ", block)
        parts.append(f"<p>{xml_escape(_clean_inline(text))}</p>")
    parts.append("</div>")
    return _xhtml(title, "\n".join(parts), lang)


def _part_xhtml(number: int, title: str, lang: str) -> str:
    words = ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight"]
    label = words[number - 1] if 1 <= number <= len(words) else str(number)
    body = (
        '<div class="partpage">'
        f'<p class="partnum">Part {xml_escape(label)}</p>'
        f"<h1>{xml_escape(title)}</h1>"
        "</div>"
    )
    return _xhtml(f"Part {label} · {title}", body, lang)


def _toc_page_xhtml(volume: BookVolume,
                    chapters: List[BookChapter]) -> str:
    """Browsable contents page — one line per chapter (the episode hook
    serves as the descriptor), grouped under parts when they exist.
    Distinct from the machine nav document."""
    layout = resolve_parts(volume, chapters)
    groups = layout if layout is not None else [("", chapters)]
    parts = ['<div class="tocpage">', "<h1>Contents</h1>"]
    for title, chs in groups:
        if title:
            parts.append(f"<h2>{xml_escape(title)}</h2>")
        for c in chs:
            desc = c.epigraph or ""
            parts.append(
                '<p class="tocentry">'
                f'<a href="chap_{c.number:03d}.xhtml">{xml_escape(c.heading)}'
                "</a>"
                + (f' — <span class="tocdesc">{xml_escape(desc)}</span>'
                   if desc else "")
                + "</p>"
            )
    parts.append("</div>")
    return _xhtml("Contents", "\n".join(parts), volume.language)


def _other_books(volume: BookVolume) -> List[Dict]:
    """Other live volumes across both series, from the committed catalog
    — the cross-promotion page's data. Never raises; empty = no page."""
    out: List[Dict] = []
    try:
        catalog = json.loads(
            (CATALOG_PATH).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — no catalog, no page
        return out
    volumes = catalog.get("volumes", catalog if isinstance(catalog, list)
                          else [])
    for entry in volumes:
        vid = entry.get("volume_id", "")
        if not vid or vid == volume.volume_id:
            continue
        out.append(entry)
    return out


def _crosspromo_xhtml(volume: BookVolume) -> str:
    """'Also from the Nerra Network' — the other volumes in this series
    and the sibling series. Every reader-facing link goes through
    engine.funnel (the only module allowed to build campaign links)."""
    from engine.funnel import PLACEMENT_BODY, episode_link

    entries = _other_books(volume)
    if not entries:
        return ""
    parts = ['<div class="alsoby">', "<h1>Also from the Nerra Network</h1>"]
    for e in entries:
        title = str(e.get("full_title") or e.get("title")
                    or e.get("volume_id"))
        slug = str(e.get("show_slug") or volume.show_slug)
        link = episode_link(
            "https://nerranetwork.com/books.html", slug,
            int(e.get("volume_number") or 0), kind="book",
            placement=PLACEMENT_BODY,
        )
        desc = str(e.get("subtitle") or e.get("description") or "").strip()
        parts.append(
            f'<p class="alsoby-entry"><a href="{xml_escape(link)}">'
            f"{xml_escape(title)}</a>"
            + (f" — {xml_escape(desc)}" if desc else "") + "</p>"
        )
    parts.append(
        '<p class="alsoby-entry">Every story began as a Nerra Network '
        "podcast episode. Find all the shows and books at "
        "nerranetwork.com.</p>")
    parts.append("</div>")
    return _xhtml("Also from the Nerra Network", "\n".join(parts),
                  volume.language)


def _nav_xhtml(volume: BookVolume, chapters: List[BookChapter],
               *, extras: Optional[Dict[str, bool]] = None) -> str:
    extras = extras or {}
    items = [
        '<li><a href="titlepage.xhtml">Title Page</a></li>',
        '<li><a href="copyright.xhtml">Copyright</a></li>',
    ]
    if extras.get("toc_page"):
        items.append('<li><a href="contents.xhtml">Contents</a></li>')
    if extras.get("introduction"):
        items.append(
            '<li><a href="introduction.xhtml">Introduction</a></li>')
    layout = resolve_parts(volume, chapters)
    if layout is None:
        items += [
            f'<li><a href="chap_{c.number:03d}.xhtml">'
            f"{xml_escape(c.heading)}</a></li>"
            for c in chapters
        ]
    else:
        for i, (title, chs) in enumerate(layout, start=1):
            sub = "".join(
                f'<li><a href="chap_{c.number:03d}.xhtml">'
                f"{xml_escape(c.heading)}</a></li>"
                for c in chs
            )
            items.append(
                f'<li><a href="part_{i:02d}.xhtml">'
                f"{xml_escape(title)}</a><ol>{sub}</ol></li>"
            )
    if extras.get("conclusion"):
        items.append('<li><a href="conclusion.xhtml">Conclusion</a></li>')
    if _has_sources(chapters):
        items.append('<li><a href="sources.xhtml">Sources</a></li>')
    if extras.get("author_bio"):
        items.append(
            '<li><a href="author.xhtml">About the Author</a></li>')
    if extras.get("crosspromo"):
        items.append(
            '<li><a href="alsoby.xhtml">Also from the Nerra Network</a>'
            "</li>")
    body = (
        '<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>'
        + "".join(items) + "</ol></nav>"
    )
    return _xhtml("Contents", body, volume.language)


def _package_opf(volume: BookVolume, chapters: List[BookChapter],
                 *, has_cover: bool,
                 extras: Optional[Dict[str, bool]] = None) -> str:
    extras = extras or {}
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
            '<item id="cover-image" href="cover.jpg" media-type="image/jpeg" '
            'properties="cover-image"/>'
        )

    def _extra(flag: str, item_id: str, href: str) -> None:
        if extras.get(flag):
            manifest.append(
                f'<item id="{item_id}" href="{href}" '
                'media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="{item_id}"/>')

    _extra("toc_page", "contents", "contents.xhtml")
    _extra("introduction", "introduction", "introduction.xhtml")

    layout = resolve_parts(volume, chapters)
    part_of = {}
    if layout is not None:
        for i, (_title, chs) in enumerate(layout, start=1):
            part_of[chs[0].number] = i
    for c in chapters:
        if c.number in part_of:
            i = part_of[c.number]
            manifest.append(
                f'<item id="part{i:02d}" href="part_{i:02d}.xhtml" '
                'media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="part{i:02d}"/>')
        cid = f"chap{c.number:03d}"
        manifest.append(
            f'<item id="{cid}" href="chap_{c.number:03d}.xhtml" '
            'media-type="application/xhtml+xml"/>'
        )
        if c.image_name:
            manifest.append(
                f'<item id="art{c.number:03d}" href="{c.image_name}" '
                'media-type="image/jpeg"/>'
            )
        spine.append(f'<itemref idref="{cid}"/>')
    _extra("conclusion", "conclusion", "conclusion.xhtml")
    if _has_sources(chapters):
        manifest.append(
            '<item id="sources" href="sources.xhtml" '
            'media-type="application/xhtml+xml"/>'
        )
        spine.append('<itemref idref="sources"/>')
    _extra("author_bio", "authorbio", "author.xhtml")
    _extra("crosspromo", "alsoby", "alsoby.xhtml")
    meta_title = xml_escape(volume.full_title)
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
    chapter_images: Optional[Dict[int, bytes]] = None,
) -> Path:
    """Assemble a store-ready EPUB 3. Hand-rolled (zip + XHTML) so the
    pipeline gains no new dependency; the structure follows the EPUB 3.3
    packaging spec (mimetype first + stored, container.xml, package.opf
    with a nav document).

    *chapter_images* maps chapter number -> JPEG bytes; chapters present
    in the map get their illustration embedded above the epigraph. Every
    image is re-encoded to its EPUB display size on the way in and the
    cover PNG is embedded as a reader-size JPEG (``engine.book_art``
    ``EPUB_*`` constants) — the payload budget ``validate_epub_size``
    enforces at the end is a delivery-fee contract, not a style choice.
    """
    from engine.book_art import to_epub_chapter_jpeg, to_epub_cover_jpeg

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    has_cover = bool(cover_png and Path(cover_png).exists())
    chapter_images = {n: to_epub_chapter_jpeg(b)
                      for n, b in (chapter_images or {}).items()}
    cover_jpeg = to_epub_cover_jpeg(Path(cover_png)) if has_cover else b""
    for c in chapters:
        c.image_name = (f"art_{c.number:03d}.jpg"
                        if c.number in chapter_images else "")

    # WO-6 front/back matter — all optional; a volume configured with
    # none of it builds the exact pre-WO-6 structure.
    intro_prose = _load_prose_file(volume.introduction_file)
    conclusion_prose = _load_prose_file(volume.conclusion_file)
    bio_prose = _load_prose_file(volume.author_bio_file)
    crosspromo_page = _crosspromo_xhtml(volume)
    layout = resolve_parts(volume, chapters)
    extras = {
        "toc_page": layout is not None,
        "introduction": bool(intro_prose),
        "conclusion": bool(conclusion_prose),
        "author_bio": bool(bio_prose),
        "crosspromo": bool(crosspromo_page),
    }
    # Deflate the documents (zipfile's default is STORED — the first
    # collected editions shipped every XHTML uncompressed); images are
    # already JPEG and stay stored.
    with zipfile.ZipFile(out_path, "w",
                         compression=zipfile.ZIP_DEFLATED) as z:
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
                   _package_opf(volume, chapters, has_cover=has_cover,
                                extras=extras))
        z.writestr("OEBPS/nav.xhtml",
                   _nav_xhtml(volume, chapters, extras=extras))
        z.writestr("OEBPS/style.css", _EPUB_CSS)
        z.writestr("OEBPS/titlepage.xhtml", _title_page_xhtml(volume))
        z.writestr("OEBPS/copyright.xhtml", _copyright_xhtml(volume))
        if extras["toc_page"]:
            z.writestr("OEBPS/contents.xhtml",
                       _toc_page_xhtml(volume, chapters))
        if intro_prose:
            z.writestr("OEBPS/introduction.xhtml",
                       _prose_xhtml("Introduction", intro_prose,
                                    volume.language))
        if has_cover:
            z.writestr("OEBPS/cover.jpg", cover_jpeg,
                       compress_type=zipfile.ZIP_STORED)
        if layout is not None:
            for i, (title, _chs) in enumerate(layout, start=1):
                z.writestr(f"OEBPS/part_{i:02d}.xhtml",
                           _part_xhtml(i, title, volume.language))
        for c in chapters:
            z.writestr(f"OEBPS/chap_{c.number:03d}.xhtml",
                       _chapter_xhtml(c, volume.language, volume))
            if c.image_name:
                z.writestr(f"OEBPS/{c.image_name}",
                           chapter_images[c.number],
                           compress_type=zipfile.ZIP_STORED)
        if conclusion_prose:
            z.writestr("OEBPS/conclusion.xhtml",
                       _prose_xhtml("Conclusion", conclusion_prose,
                                    volume.language))
        if _has_sources(chapters):
            z.writestr("OEBPS/sources.xhtml",
                       _sources_xhtml(volume, chapters))
        if bio_prose:
            z.writestr("OEBPS/author.xhtml",
                       _prose_xhtml("About the Author", bio_prose,
                                    volume.language))
        if crosspromo_page:
            z.writestr("OEBPS/alsoby.xhtml", crosspromo_page)
    validate_epub_escaping(out_path)
    validate_epub_size(out_path)
    payload = epub_payload_breakdown(out_path)
    logger.info("EPUB written: %s (%d chapters, %d words, %.2f MB: "
                "%.2f MB images in %d files, %.2f MB documents)",
                out_path, len(chapters), sum(c.word_count for c in chapters),
                payload["total"] / _MB, payload["images"] / _MB,
                payload["image_count"], payload["documents"] / _MB)
    return out_path


_MB = 1024 * 1024

#: Hard cap on a built EPUB — the alarm, not the target. The embed
#: constants in engine.book_art aim a fully illustrated 73-chapter
#: collected edition under 4 MB; a build crossing 5 MB means art is
#: reaching the file at a size the reader never displays (or the cover
#: came back as a PNG), and it costs $0.15/MB per sale on KDP's 70%
#: royalty plan — the 15.4 MB first build lost $1.26 of royalty on every
#: copy. Shrink the payload, never raise the cap.
EPUB_MAX_BYTES = 5 * _MB

_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")


def epub_payload_breakdown(epub_path: Path) -> Dict[str, int]:
    """Bytes on disk split into images vs documents (as packed)."""
    epub_path = Path(epub_path)
    total = epub_path.stat().st_size
    images = image_count = 0
    with zipfile.ZipFile(epub_path) as z:
        for info in z.infolist():
            if info.filename.lower().endswith(_IMAGE_SUFFIXES):
                images += info.compress_size
                image_count += 1
    return {"total": total, "images": images, "image_count": image_count,
            "documents": total - images}


def validate_epub_size(epub_path: Path, *,
                       max_bytes: int = EPUB_MAX_BYTES) -> None:
    """Fail the build when the packaged EPUB exceeds *max_bytes*, naming
    the measured size and where it went."""
    payload = epub_payload_breakdown(epub_path)
    if payload["total"] > max_bytes:
        raise ValueError(
            f"{Path(epub_path).name} is {payload['total'] / _MB:.2f} MB "
            f"({payload['images'] / _MB:.2f} MB of images across "
            f"{payload['image_count']} files, "
            f"{payload['documents'] / _MB:.2f} MB of documents) — exceeds "
            f"the {max_bytes / _MB:.0f} MB EPUB payload cap. KDP charges "
            "$0.15/MB delivery per sale on the 70% royalty plan and its "
            "browser upload caps at 10 MB; shrink the embedded art "
            "(engine.book_art EPUB_* constants), do not raise the cap.")


_DOUBLE_ESCAPE_RE = re.compile(r"&amp;(?:amp|lt|gt|quot|apos|#\d+);")


def validate_epub_escaping(epub_path: Path) -> None:
    """Fail the build if any packaged XML document is mis-escaped.

    Locks the WO-11 acceptance criterion at build time: every
    .xhtml/.opf/.ncx must (1) contain no double-escape (``&amp;amp;`` and
    friends — the sequence that renders a literal "&amp;" to readers),
    (2) parse as well-formed XML (a bare ``&`` would fail here), and
    (3) yield extracted text with no literal "&amp;" — i.e. what the
    reader displays is "&", never the entity spelling.
    """
    import xml.etree.ElementTree as ET
    import zipfile

    with zipfile.ZipFile(epub_path) as z:
        for name in z.namelist():
            if not name.endswith((".xhtml", ".opf", ".ncx")):
                continue
            raw = z.read(name).decode("utf-8")
            if _DOUBLE_ESCAPE_RE.search(raw):
                raise ValueError(
                    f"{epub_path.name}:{name} contains a double-escaped "
                    f"entity ({_DOUBLE_ESCAPE_RE.search(raw).group(0)}) — "
                    "it would render literally to readers")
            try:
                root = ET.fromstring(raw.encode("utf-8"))
            except ET.ParseError as exc:
                raise ValueError(
                    f"{epub_path.name}:{name} is not well-formed XML: "
                    f"{exc}") from exc
            if "&amp;" in "".join(root.itertext()):
                raise ValueError(
                    f"{epub_path.name}:{name} renders a literal '&amp;' "
                    "in its text")


# ---------------------------------------------------------------------------
# Cover
# ---------------------------------------------------------------------------

def generate_cover(volume: BookVolume, out_png: Path,
                   *, art_bytes: bytes = None,
                   size: Tuple[int, int] = (1600, 2560)) -> Path:
    """Series-branded cover at KDP's 1600x2560. With *art_bytes* (fresh
    Grok-Imagine art from ``engine.book_art``) the fixed series
    typography is composited over it; without, the same layout renders
    over the series color — so unbranded fallbacks still look like the
    series. Composition lives in ``engine.book_art.compose_cover``."""
    from engine.book_art import compose_cover

    return compose_cover(volume, out_png, art_bytes=art_bytes, size=size)


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
