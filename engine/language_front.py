"""Front pages in the site's other languages (Oct 19 2026).

``ru/index.html`` and ``fr/index.html`` are news front pages like the English
homepage — a lead, the flagship band, top stories, a latest rail, sections by
subject — laid out by the SAME assembler (``engine.landing_test.assemble``)
over the stories that exist in that language:

* a show made natively in the language (``page_lang``) contributes its
  episodes as the English page would (hook from the digest, its own audio);
* an English show that produces a translated audio track in the language
  contributes each episode that has one: the headline is the TRANSLATED
  title the multilingual stage wrote beside the track, the audio is the
  translated MP3, the picture is the episode's own scene (matched on the
  English hook, which is what the scene prompts were written from), and the
  article link is the English post, which carries the language switcher and
  plays the translated track. "Also in this episode" is left empty — those
  headlines exist only in English.

Dates and the masthead are written in the language here (``MONTHS`` /
``WEEKDAYS``); the subject headings come from the hub copy in
``generate_html._LANGUAGE_HUB_COPY`` so every reader-facing string on the
page is hand-written per language. Nothing here opens a network connection.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from engine import landing_test as _lt
from engine import newsroom as _nr
from engine import show_lang as _show_lang
from engine import titles as _titles

#: How many of a show's newest episodes may run on the page. One per show
#: (the English page's rule) leaves a seven-show French page with seven
#: stories; three gives the assembler a lead, top stories and sections to fill.
STORIES_PER_SHOW = 3

MONTHS: Dict[str, Sequence[str]] = {
    "ru": ("января", "февраля", "марта", "апреля", "мая", "июня", "июля",
           "августа", "сентября", "октября", "ноября", "декабря"),
    "fr": ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"),
}
WEEKDAYS: Dict[str, Sequence[str]] = {
    "ru": ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота",
           "воскресенье"),
    "fr": ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"),
}

_SENTENCE_END_RE = re.compile(r"(?<=[.!?…])\s+")


def date_label(day: dt.date, lang: str) -> str:
    """``18 октября 2026`` / ``18 octobre 2026``; ISO for an unknown language."""
    months = MONTHS.get(lang)
    if not months:
        return day.isoformat()
    return f"{day.day} {months[day.month - 1]} {day.year}"


def long_date(day: dt.date, lang: str) -> str:
    """The masthead dateline: ``воскресенье, 18 октября 2026`` /
    ``dimanche 18 octobre 2026``."""
    days = WEEKDAYS.get(lang)
    if not days:
        return date_label(day, lang)
    weekday = days[day.weekday()]
    if lang == "fr":
        return f"{weekday} {date_label(day, lang)}"
    return f"{weekday}, {date_label(day, lang)}"


def localize_stamp(stamp: Dict[str, Any], lang: str) -> Dict[str, Any]:
    """The newsroom stamp with its label written in *lang*. The Eastern
    clock stays (it is when the network publishes); the page script that
    rewrites English stamps to "2 hours ago" is not loaded on these pages, so
    the absolute label is what a reader sees."""
    out = dict(stamp)
    if not out.get("day"):
        return out
    try:
        day = dt.date.fromisoformat(str(out["day"])[:10])
    except ValueError:
        return out
    label = date_label(day, lang)
    if out.get("has_time") and out.get("iso", "").endswith("Z"):
        try:
            t = dt.datetime.strptime(out["iso"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc).astimezone(_nr.EASTERN)
            label = f"{label} · {t.strftime('%H:%M')} ET"
        except ValueError:
            pass
    out["label"] = label
    out["short"] = date_label(day, lang)
    return out


def masthead(now: dt.datetime, lang: str) -> Dict[str, str]:
    """The dateline and "updated" stamp in *lang* (same clock as the English
    masthead: Eastern, the network's publishing day)."""
    base = _nr.masthead(now)
    aware = now if now.tzinfo else now.replace(tzinfo=dt.timezone.utc)
    t = aware.astimezone(_nr.EASTERN)
    return {
        **base,
        "date": long_date(t.date(), lang),
        "updated": f"{t.strftime('%H:%M')} ET",
    }


def _first_sentence(text: str, limit: int = 220) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    first = _SENTENCE_END_RE.split(text, maxsplit=1)[0].strip()
    return first if 0 < len(first) <= limit else ""


def translated_hook(track: Dict[str, Any]) -> str:
    """The headline a translated episode runs under: the track's translated
    description's first sentence (complete, where the title may be clipped to
    the feed's 100-character budget), else its title without the ``Ep N:``
    label."""
    title = _lt.strip_episode_label(str(track.get("title") or ""))
    desc = _lt.strip_episode_label(str(track.get("description") or ""))
    first = _first_sentence(desc)
    if first and len(first) >= len(title) * 0.8:
        return first
    return title or first


def translated_record(record: Dict[str, Any], lang: str) -> Optional[Dict[str, str]]:
    """``{"hook", "audio_url"}`` for the episode's track in *lang*, or
    ``None`` when the episode has no audio in that language."""
    track = (record.get("translations") or {}).get(lang) or {}
    audio = str(track.get("audio_url") or "").strip()
    if not audio:
        return None
    hook = translated_hook(track)
    if not hook:
        return None
    return {"hook": hook, "audio_url": audio}


def in_language(text: str, lang: str) -> bool:
    """Whether a headline reads in *lang* (so the page marks the others with
    ``lang=``). Russian is detectable by script; French is taken on trust."""
    if lang == "ru":
        return _lt.is_cyrillic(text)
    return True


def build_story(show: Dict[str, Any], record: Dict[str, Any], lang: str, *,
                blog_url_for: Callable[[str, Optional[int]], str],
                audio_url_for: Callable[[str], str],
                gallery: Optional[dict],
                prompts_for: Optional[Callable[[Optional[int], str], Dict[str, str]]] = None,
                ) -> Optional[Dict[str, Any]]:
    """One template-ready story in *lang*, or ``None``.

    A native show's story is the English page's story with the page language
    taken into account; a dubbed show's story is the English story with the
    translated headline and audio in place of the English ones.
    """
    native = show.get("page_lang") == lang
    translated = None if native else translated_record(record, lang)
    if not native and translated is None:
        return None
    story = _lt.build_story(show, record, blog_url_for=blog_url_for,
                            audio_url_for=audio_url_for, gallery=gallery, hub=None,
                            prompts_for=prompts_for)
    if story is None:
        return None
    if translated is not None:
        story["hook"] = translated["hook"]
        story["ticker_text"] = _titles.clip_words(translated["hook"], _titles.LANDING_TICKER_MAX)
        story["audio_url"] = audio_url_for(translated["audio_url"])
        story["more"] = []
        story["translated"] = True
    else:
        story["translated"] = False
    story["lang"] = "" if in_language(story["hook"], lang) else "en"
    return story


def _records_newest_first(json_path: Path) -> List[Dict[str, Any]]:
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = payload.get("summaries") if isinstance(payload, dict) else payload
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    return sorted(rows, key=lambda r: (str(r.get("date") or ""),
                                       _lt._episode_number(r) or 0), reverse=True)


def _prompts_reader(slice_path: Path, slug: str):
    """Build-time only: the scene prompts that say which of the episode's
    scenes depicts a headline. None of the text reaches the page."""
    def read(number: Optional[int], day: str) -> Dict[str, str]:
        return _lt.scene_prompts(slice_path, slug, number, day)
    return read


def collect_stories(lang: str, public: Sequence[Dict[str, Any]], *,
                    network_shows: Dict[str, dict], root: Path, gallery_root: Path,
                    blog_url_for: Callable[[str, Optional[int]], str],
                    audio_url_for: Callable[[str], str], now: dt.datetime,
                    hub_for: Optional[Dict[str, Dict[str, Any]]] = None,
                    per_show: int = STORIES_PER_SHOW) -> List[Dict[str, Any]]:
    """Every story the page can run: the newest ``per_show`` episodes of each
    show made in *lang* or producing a track in it, stamped in *lang*."""
    stories: List[Dict[str, Any]] = []
    for show in public:
        page_lang = show.get("page_lang") or "en"
        if page_lang != lang:
            if page_lang != "en" or lang not in (_show_lang.track_languages(show["slug"]) or ()):
                continue
        cfg = network_shows.get(show["slug"]) or {}
        if not cfg.get("json_path"):
            continue
        gallery = _lt.load_gallery_index(gallery_root, show["slug"])
        slice_path = gallery_root / f"{show['slug']}.json"
        prompts_for = _prompts_reader(slice_path, show["slug"])
        taken = 0
        for record in _records_newest_first(root / cfg["json_path"]):
            story = build_story(show, record, lang, blog_url_for=blog_url_for,
                                audio_url_for=audio_url_for, gallery=gallery,
                                prompts_for=prompts_for)
            if story is None:
                continue
            hub = (hub_for or {}).get(show["slug"])
            if hub:
                story["hub_id"], story["hub_heading"] = hub["id"], hub["heading"]
            story["stamp"] = localize_stamp(
                _nr.stamp(record.get("date"), _nr.published_at(record), now), lang)
            stories.append(story)
            taken += 1
            if taken >= per_show:
                break
    return stories


def assemble(stories: Iterable[Dict[str, Any]], *, lang: str,
             audience_order: Sequence[str] = (), flagships: Sequence[str] = (),
             section_headings: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """The English assembler's layout, with the section headings and the
    edition date written in *lang*. Sections never link the English topic
    hubs (``hub_url`` stays empty)."""
    # Oct 19 2026: a native show's story whose headline is not in the page's
    # language (Привет, Русский! writes its hooks in English) never leads
    # the page or runs as a top story — Ep74's "Today we step into the
    # Russian woods…" led ru/index.html. It stays on the page, in the Latest
    # rail, marked ``lang="en"``.
    stories = list(stories)
    foreign = [s for s in stories if s.get("lang")]
    page = _lt.assemble([s for s in stories if not s.get("lang")],
                        audience_order=audience_order, live_hub_ids=(), flagships=flagships)
    if foreign:
        placed = {id(s) for s in [page.get("lead"), *page.get("top", []), *page.get("latest", []),
                                   *page.get("more", []), *page.get("flagships", []),
                                   *(x for sec in page.get("sections", []) for x in sec["stories"])] if s}
        extra = [s for s in foreign if id(s) not in placed]
        page["latest"] = sorted([*page.get("latest", []), *extra],
                                key=lambda s: s.get("date_obj") or dt.date.min, reverse=True)
    # One card per flagship show, its newest story (the English band's shape;
    # the assembler puts every flagship story in the band, and this page runs
    # up to STORIES_PER_SHOW of each). The older ones stay in the Latest list.
    seen: set = set()
    band = []
    for story in page.get("flagships") or []:
        if story["slug"] in seen:
            continue
        seen.add(story["slug"])
        band.append(story)
    page["flagships"] = band
    headings = section_headings or {}
    for sec in page.get("sections") or []:
        sec["heading"] = headings.get(sec["id"], sec["heading"])
        sec["hub_url"] = ""
    for story in [page.get("lead"), *page.get("top", []), *page.get("latest", []),
                  *page.get("more", []), *page.get("flagships", []),
                  *(s for sec in page.get("sections", []) for s in sec["stories"])]:
        if story and story.get("hub_id"):
            story["hub_heading"] = headings.get(story["hub_id"], story.get("hub_heading", ""))
    newest = page["latest"][0].get("date_obj") if page.get("latest") else None
    if newest:
        page["edition_date"] = long_date(newest, lang)
    return page
