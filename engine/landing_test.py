"""Data for ``landing-test.html`` — the network's stories as a news front page.

Operator-directed TEST (Oct 17 2026): what would the site look like if its
landing page were a news front — every public show's newest episode laid out
as a lead story, a top-stories grid and topic sections, with the episode's
own scene art — instead of a podcast catalogue? The page is ``noindex``, kept
out of the sitemap and linked from nowhere; this module only assembles data.

Everything here comes from committed files and nothing is written for the
page:

* **The headline is the episode's hook** — the digest's own headline, from
  the summaries JSON the show page's Latest Episode card already reads
  (``engine.summaries_ssr``), with its ``Ep N:`` label removed. Never
  rewritten.
* **"More from this episode"** lines are the digest's own story headlines
  (``engine.grok_imagine.extract_story_headlines``), copied, never edited.
* **The picture is that episode's own scene**, matched in the slim gallery
  index (``site/data/gallery/<slug>.index.json``) by show, episode id AND
  date. An episode with no scene of its own gets the show's cover art, never
  an older episode's picture: an image beside a headline is a claim about
  that story.
* **Members-only shows never appear** (``engine.access``), and nothing here
  reads ``digests/*/members/``: the summaries file it reads is the show
  directory's top level, which is public by construction.

Subjects are the curated ``engine.topic_hubs.TOPIC_HUBS`` vocabulary, never
the registry's free-text tags (the keyword-artifact problem that module was
written to avoid).
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from engine import titles as _titles
from engine import topic_hubs as _hubs
from engine.summaries_ssr import _display_date, _episode_number, _records

#: Access modes whose top-level episodes are public. ``members_only`` shows
#: are left out entirely (their public surfaces never carry an episode).
PUBLIC_ACCESS_MODES = frozenset({"public", "public_weekly"})

#: A story older than this many days before the newest one is not news on a
#: front page; its show still appears in the Listen rail.
MAX_STORY_AGE_DAYS = 14

#: How many stories sit in the top-stories grid under the lead.
TOP_STORY_COUNT = 4

#: "More from this episode" headlines per card.
MORE_HEADLINES = 3

#: A topic section shows at most this many stories; one with fewer than
#: ``MIN_SECTION_STORIES`` folds into "More from the network" instead of
#: rendering as a lonely one-card section.
SECTION_STORY_LIMIT = 4
MIN_SECTION_STORIES = 2

#: Entries in the "Latest" list beside the lead.
LATEST_LIMIT = 10

#: Front-page section order. Each story lands in the FIRST section here whose
#: hub lists its show, so no story is printed twice. Ids are
#: ``engine.topic_hubs`` hub ids; an id missing from that module is skipped.
SECTION_ORDER = (
    "world-news",
    "ai",
    "space",
    "tesla",
    "markets",
    "science",
    "health-and-longevity",
    "climate-and-energy",
    "local-news",
    "history-and-consequences",
    "interviews",
    "engineering",
    "good-news",
    "language-learning",
    "sailing",
    "prediction-markets",
    "ai-infrastructure",
)

#: Shows that are not news stories: the daily edition is the network itself
#: in one episode and gets its own strip.
EDITION_SLUG = "nerra_daily"

#: The scene kind cut 16:9 for the long-form video; ``social`` is 9:16.
LANDSCAPE_USE = "segment_card"
PORTRAIT_USE = "social"

_EP_LABEL_RE = re.compile(r"^\s*(?:Ep(?:isode)?|Выпуск)\s*\.?\s*\d+\s*[:—–-]\s*", re.I)


def strip_episode_label(title: str) -> str:
    """``"Ep 133: SpaceX Dragon…"`` -> ``"SpaceX Dragon…"``; anything else
    passes through unchanged."""
    return _EP_LABEL_RE.sub("", (title or "").strip()).strip()


_HOOK_LINE_RE = re.compile(r"^>\s*(.+?)\s*$")


def hook_from_markdown(text: str) -> str:
    """The digest's own headline: its first blockquote line, bold removed.

    The summaries record's ``episode_title`` is the FEED title, which
    ``engine.titles.episode_title`` clips to 100 characters with an ``Ep N:``
    label, so it is the wrong source for a headline printed whole.
    """
    for raw in (text or "").splitlines()[:40]:
        match = _HOOK_LINE_RE.match(raw.strip())
        if not match:
            continue
        hook = re.sub(r"[*_]{1,2}", "", match.group(1)).strip()
        if len(hook) >= 20:
            return hook
    return ""


def is_cyrillic(text: str) -> bool:
    """True when most of *text*'s letters are Cyrillic."""
    letters = [c for c in text or "" if c.isalpha()]
    if not letters:
        return False
    cyr = sum(1 for c in letters if "\u0400" <= c <= "\u04ff")
    return cyr * 2 > len(letters)


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").lower()).strip()


def _parse_date(value: str) -> Optional[date]:
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Committed inputs
# ---------------------------------------------------------------------------


def latest_record(json_path: Path) -> Optional[dict]:
    """The newest episode record in a show's summaries JSON, or ``None``.

    Same ordering rule as ``engine.summaries_ssr.summary_cards`` (episode
    number where every record has one, otherwise document order reversed),
    so this page and the show page's Latest Episode card agree on which
    episode is newest.
    """
    path = Path(json_path)
    if not path.is_file():
        return None
    try:
        records = _records(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None
    if not records:
        return None
    if all(_episode_number(r) is not None for r in records):
        return max(records, key=_episode_number)
    return records[-1]


def record_by_number(json_path: Path, number: int) -> Optional[dict]:
    """The summaries record for episode *number*, or ``None``."""
    path = Path(json_path)
    if not path.is_file():
        return None
    try:
        records = _records(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None
    for record in records:
        if _episode_number(record) == number:
            return record
    return None


_EP_NUM_RE = re.compile(r"(?i)\bep(?:isode)?\s*(\d+)\b")


def episode_number_from_title(title: str) -> Optional[int]:
    """``"Ep 124: …"`` / ``"… - Episode 125 - …"`` -> the number."""
    match = _EP_NUM_RE.search(title or "")
    return int(match.group(1)) if match else None


def load_gallery_index(gallery_dir: Path, slug: str) -> Optional[dict]:
    """A show's slim gallery index, or ``None``. Never the 22 MB manifest."""
    path = Path(gallery_dir) / f"{slug}.index.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


_STOP = frozenset(
    "the and for with that this from into over under after before while their "
    "there about than then they them have has had will would could should "
    "were been being which what when where cinematic photo photograph light "
    "lighting high energy style scene inside outside image wide shot".split())


def _salient(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if (len(w) >= 4 or w.isdigit()) and w not in _STOP}


def scene_prompts(slice_path: Path, slug: str, episode_num: Optional[int],
                  episode_date: str) -> Dict[str, str]:
    """``image_id -> prompt`` for one episode, from the show's full gallery
    slice (``site/data/gallery/<slug>.json``). Read at BUILD time only, to
    pick the episode scene that depicts the headline; nothing from it reaches
    the page. ``{}`` when the slice is missing or unreadable."""
    path = Path(slice_path)
    if not isinstance(episode_num, int) or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    wanted = f"ep{episode_num:03d}"
    out: Dict[str, str] = {}
    for img in (data.get("images") or []) if isinstance(data, dict) else []:
        if (isinstance(img, dict) and img.get("show_slug") == slug
                and img.get("episode_id") == wanted
                and str(img.get("episode_date") or "") == episode_date[:10]):
            out[str(img.get("image_id") or "")] = str(img.get("prompt") or "")
    return out


#: A scene must share this many salient words with the headline to be
#: preferred over the episode's first scene.
SCENE_MATCH_MIN_WORDS = 2


def episode_scene(index: Optional[dict], slug: str, episode_num: Optional[int],
                  episode_date: str, *, hook: str = "",
                  prompts: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """A scene image of exactly this episode, landscape first.

    Matches show, ``epNNN`` AND date: an episode id alone could be reused
    after a catalogue prune (DP Pod's Aug 2026 purge), and a picture from a
    different episode beside this headline would be a false claim about it.
    An episode has one scene per story, so when *prompts* are given the scene
    whose prompt shares the most words with *hook* wins (SpaceX Ep133's first
    scene was the Optimus story; its Dragon scene is the one that belongs
    beside the Dragon headline). Otherwise the episode's first scene.
    Returns ``{"url", "orientation", "matched"}`` or ``None``.
    """
    if not index or not isinstance(episode_num, int) or not episode_date:
        return None
    ef = index.get("episode_fields") or []
    imf = index.get("image_fields") or []
    try:
        e_slug, e_date, e_id = (ef.index("show_slug"), ef.index("episode_date"),
                                ef.index("episode_id"))
        i_id, i_ep, i_use = (imf.index("image_id"), imf.index("episode"),
                             imf.index("intended_use"))
    except ValueError:
        return None
    wanted_id = f"ep{episode_num:03d}"
    episodes = index.get("episodes") or []
    rows = {
        n for n, ep in enumerate(episodes)
        if len(ep) > max(e_slug, e_date, e_id)
        and ep[e_slug] == slug and ep[e_id] == wanted_id
        and ep[e_date] == episode_date[:10]
    }
    if not rows:
        return None
    base = (index.get("base_url") or "").rstrip("/")
    overrides = index.get("overrides") or {}
    hook_words = _salient(hook)
    prompts = prompts or {}
    for use, orientation in ((LANDSCAPE_USE, "landscape"), (PORTRAIT_USE, "portrait")):
        candidates = []
        for position, row in enumerate(index.get("images") or []):
            if len(row) <= max(i_id, i_ep, i_use):
                continue
            if row[i_ep] not in rows or row[i_use] != use:
                continue
            ep = episodes[row[i_ep]]
            url = (overrides.get(str(position)) or {}).get("thumbnail_url") or (
                f"{base}/{ep[e_slug]}/{ep[e_date]}/{ep[e_id]}/{row[i_id]}.thumb.webp"
                if base else "")
            if url.startswith("https://"):
                score = len(hook_words & _salient(prompts.get(str(row[i_id]), "")))
                candidates.append((score, position, url))
        if not candidates:
            continue
        best = max(candidates, key=lambda c: (c[0], -c[1]))
        if best[0] >= SCENE_MATCH_MIN_WORDS:
            return {"url": best[2], "orientation": orientation, "matched": True}
        return {"url": candidates[0][2], "orientation": orientation, "matched": False}
    return None


def more_headlines(content: str, hook: str, limit: int = MORE_HEADLINES) -> List[str]:
    """Up to *limit* of the digest's own story headlines, the hook excluded."""
    from engine.grok_imagine import extract_story_headlines

    hook_key = _norm(hook)
    out: List[str] = []
    for headline in extract_story_headlines(content or "", max_count=limit + 4):
        key = _norm(headline)
        if not key or key == hook_key or key in hook_key or hook_key in key:
            continue
        out.append(headline)
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def hub_by_slug(all_shows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Show slug -> the first hub in ``SECTION_ORDER`` that lists it."""
    out: Dict[str, Dict[str, Any]] = {}
    for hub_id in SECTION_ORDER:
        hub = _hubs.hub_by_id(hub_id)
        if not hub:
            continue
        for show in _hubs.hub_shows(hub, all_shows):
            out.setdefault(show["slug"], hub)
    return out


def build_story(show: Dict[str, Any], record: dict, *,
                blog_url_for: Callable[[str, Optional[int]], str],
                audio_url_for: Callable[[str], str],
                gallery: Optional[dict],
                hub: Optional[Dict[str, Any]],
                digest_text: str = "",
                prompts_for: Optional[Callable[[Optional[int], str], Dict[str, str]]] = None,
                ) -> Optional[Dict[str, Any]]:
    """One template-ready story, or ``None`` when the record has no headline.

    The headline is the digest's hook (from the record's content, else from
    *digest_text* — the episode's committed digest, which the interview
    shows' records do not carry); the feed title is the last resort.
    """
    content = record.get("content") or record.get("summary") or ""
    raw_title = (record.get("episode_title") or record.get("title") or "").strip()
    hook = (hook_from_markdown(content) or hook_from_markdown(digest_text)
            or strip_episode_label(raw_title))
    if not hook:
        return None
    number = _episode_number(record)
    date_raw = str(record.get("date") or "")[:10]
    scene = episode_scene(
        gallery, show["slug"], number, date_raw, hook=hook,
        prompts=prompts_for(number, date_raw) if (prompts_for and gallery) else None)
    cover = show.get("podcast_image") or ""
    cover_base = cover[:-4] if cover.endswith(".jpg") else ""
    return {
        "slug": show["slug"],
        "show_name": show["name"],
        "show_page": show["show_page"],
        "blog_page": show.get("blog_page", ""),
        "brand_color": show.get("brand_color") or "#6B47FF",
        "hook": hook,
        "ticker_text": _titles.clip_words(hook, _titles.LANDING_TICKER_MAX),
        "episode_num": number,
        "date_raw": date_raw,
        "date": _display_date(date_raw),
        "date_obj": _parse_date(date_raw),
        "post_url": blog_url_for(show["slug"], number),
        "audio_url": audio_url_for((record.get("audio_url") or "").strip()),
        "image_url": scene["url"] if scene else "",
        "image_orientation": scene["orientation"] if scene else "",
        "cover_url": cover,
        "cover_webp": f"{cover_base}-400.webp" if cover_base else "",
        "more": more_headlines(content, hook),
        "hub_id": hub["id"] if hub else "",
        "hub_heading": hub["heading"] if hub else "",
        "guest": (record.get("guest") or "").strip(),
        # Read from the TEXT, not the show: Привет, Русский! renders its
        # pages in Russian but writes its hooks in English.
        "lang": "ru" if is_cyrillic(hook) else "",
    }


def _order_key(rank: Dict[str, int]) -> Callable[[Dict[str, Any]], tuple]:
    def key(story: Dict[str, Any]) -> tuple:
        d = story.get("date_obj") or date.min
        return (-d.toordinal(), rank.get(story["slug"], 10_000), story["slug"])
    return key


def assemble(stories: Iterable[Dict[str, Any]], *,
             audience_order: Sequence[str] = (),
             live_hub_ids: Iterable[str] = ()) -> Dict[str, Any]:
    """Lay the stories out: lead, top stories, latest list, sections.

    Deterministic: newest date first, then the audience ranking (30-day
    downloads, the homepage's own order), then slug. The lead is the first
    story with a landscape scene of its own, because a lead without a picture
    is not a front page; when no story has one, the first story leads anyway.
    """
    rank = {slug: n for n, slug in enumerate(audience_order)}
    ordered = sorted(stories, key=_order_key(rank))
    if ordered and ordered[0].get("date_obj"):
        newest = ordered[0]["date_obj"]
        ordered = [
            s for s in ordered
            if s.get("date_obj") and (newest - s["date_obj"]).days <= MAX_STORY_AGE_DAYS
        ]
    if not ordered:
        return {"lead": None, "top": [], "latest": [], "sections": [],
                "more": [], "edition_date": "", "story_count": 0,
                "today_count": 0}

    lead = next((s for s in ordered if s["image_orientation"] == "landscape"),
                ordered[0])
    rest = [s for s in ordered if s is not lead]
    with_art = [s for s in rest if s["image_url"]]
    top = (with_art + [s for s in rest if not s["image_url"]])[:TOP_STORY_COUNT]
    placed = {id(lead), *(id(s) for s in top)}

    live = set(live_hub_ids)
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    leftovers: List[Dict[str, Any]] = []
    for story in ordered:
        if id(story) in placed:
            continue
        if story["hub_id"]:
            buckets.setdefault(story["hub_id"], []).append(story)
        else:
            leftovers.append(story)

    sections = []
    for hub_id in SECTION_ORDER:
        items = buckets.get(hub_id) or []
        if len(items) < MIN_SECTION_STORIES:
            leftovers.extend(items)
            continue
        hub = _hubs.hub_by_id(hub_id) or {}
        # Pictured stories lead a section; order is otherwise kept.
        items = sorted(items, key=lambda s: 0 if s["image_url"] else 1)
        shown, overflow = items[:SECTION_STORY_LIMIT], items[SECTION_STORY_LIMIT:]
        leftovers.extend(overflow)
        sections.append({
            "id": hub_id,
            "heading": hub.get("heading", hub_id),
            "hub_url": _hubs.hub_page_path(hub_id) if hub_id in live else "",
            "stories": shown,
        })
    leftovers.sort(key=_order_key(rank))

    newest = ordered[0]["date_obj"]
    return {
        "lead": lead,
        "top": top,
        "latest": ordered[:LATEST_LIMIT],
        "sections": sections,
        "more": leftovers,
        "edition_date": (f"{newest.strftime('%A, %B')} {newest.day}, {newest.year}"
                         if newest else ""),
        "story_count": len(ordered),
        "today_count": sum(1 for s in ordered if s.get("date_obj") == newest),
    }
