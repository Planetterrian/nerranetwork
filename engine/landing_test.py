"""Data for the homepage (``index.html``) — the network's stories as a news front.

Built as an operator-directed TEST (Oct 17 2026, ``landing-test.html``): what
would the site look like if its landing page were a news front — every
public show's newest episode laid out as a lead story, a top-stories grid and
topic sections, with the episode's own scene art — instead of a podcast
catalogue? Promoted to the homepage on Oct 18 2026; ``engine/newsroom.py``
adds the timestamps, developing stories, markets, corrections and schedule.
This module only assembles data.

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
from engine.interviews import INTERVIEW_SHOW_SLUGS
from engine.summaries_ssr import _display_date, _episode_number, _records
from engine.release_schedule import is_still_scheduled

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

#: The lead rotates through the subjects the network promises — world news,
#: AI, science, markets, space, history — one a day by the edition date
#: (Oct 18 2026, operator: the audience ranking alone put SpaceX or Tesla on
#: top every morning). A day whose subject has no pictured story of the newest
#: date takes the next subject in the list.
LEAD_ROTATION = (
    "world-news",
    "ai",
    "science",
    "markets",
    "space",
    "history-and-consequences",
)

#: Hubs that are one beat for the front page's variety rule: SpaceX and Tesla
#: are the same company story to a reader scanning the top.
_SAME_BEAT = {"tesla": "space"}

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


def recent_records(json_path: Path, limit: int = 3) -> List[dict]:
    """The newest *limit* episode records, newest first.

    The ordering rule is :func:`latest_record`'s (episode number when every
    record carries one, otherwise document order reversed), so
    ``recent_records(p, 1)[0]`` is ``latest_record(p)``. A show's summaries
    file is not in date order (SpaceX's last record is Ep115 of 300), so
    neither the file order nor the date alone can be trusted.
    """
    path = Path(json_path)
    if not path.is_file() or limit <= 0:
        return []
    try:
        records = _records(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return []
    if all(_episode_number(r) is not None for r in records):
        ordered = sorted(records, key=_episode_number, reverse=True)
    else:
        ordered = list(reversed(records))
    return ordered[:limit]


#: Headlines kept per story on the member front page (``story_json``): the
#: card prints three, and the topic matcher reads them all.
PERSONAL_HEADLINES = 8

#: The keys of a :func:`build_story` dict that the member page reads. The
#: rest (``date_obj``, the ticker text, the hub id) are the homepage's.
_STORY_JSON_KEYS = ("slug", "show_name", "show_page", "brand_color", "hook",
                    "episode_num", "date_raw", "date", "post_url", "audio_url",
                    "image_url", "image_orientation", "cover_url", "cover_webp",
                    "hub_heading", "guest", "lang")


def story_json(story: Dict[str, Any], *, record: dict,
               duration_s: Optional[int] = None,
               show_dir: Optional[Path] = None) -> Dict[str, Any]:
    """A :func:`build_story` dict as plain JSON for ``api/personal_front.json``.

    ``headlines`` carries up to :data:`PERSONAL_HEADLINES` of the episode's
    own story headlines (the hook's story excluded), read again from the
    record because the homepage keeps only three. ``deck`` is one or two
    sentences of the digest's own prose on the hook's story
    (:func:`story_deck`; ``""`` when the digest has none), with any
    sentence the claims gate flagged left out when *show_dir* (the show's
    digest directory, where the committed sidecar lives) is given.
    ``stamp`` is the homepage's publication stamp without its build-time
    ``is_today``, which the page recomputes against the reader's clock.
    """
    out = {k: story.get(k) for k in _STORY_JSON_KEYS}
    content = record.get("content") or record.get("summary") or ""
    hook = story.get("hook") or ""
    # Nov 3 2026: the headlines are sentence-cased here, where the digest's
    # prose (the evidence for which words are names) is at hand — the email
    # card and My Nerra print them under a sentence-case deck.
    out["headlines"] = [sentence_case_headline(h, content)
                        for h in more_headlines(content, hook, limit=PERSONAL_HEADLINES)]
    flagged = flagged_sentences_for(show_dir, record) if show_dir else frozenset()
    out["deck"] = story_deck(content, hook, flagged=flagged)
    stamp = story.get("stamp") or {}
    out["stamp"] = {k: stamp.get(k) for k in ("iso", "label", "short", "day", "has_time")}
    out["duration_s"] = int(duration_s) if duration_s else None
    return out


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


#: Suffixes folded before a headline word is compared with a scene prompt
#: (Nov 3 2026): "robots" and "Robotic", "models" and "modeling", "protein"
#: and "proteins" are one subject. Longest first.
_STEM_SUFFIXES = ("ically", "ation", "ingly", "ments", "ings", "ment", "ness",
                  "ics", "ies", "ing", "ers", "ic", "al", "ed", "er", "es", "s")


def _stem(word: str) -> str:
    for suf in _STEM_SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)]
    return word


def _stems(text: str) -> set:
    """Stemmed salient tokens of a headline or a scene prompt; three-letter
    nouns count ("lab", "car", "ice")."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {_stem(w) for w in words if (len(w) >= 3 or w.isdigit()) and w not in _STOP}


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


#: A scene must share this many stemmed salient words with the headline to
#: be its picture; ONE shared word is enough when no other scene of the
#: episode shares any (Nov 3 2026 — the Nov 2 front page led with a coral
#: reef under a protein-engineering headline because the three lab scenes
#: scored 1 each on exact words and the chooser fell back to the first scene
#: in slice order). When the episode's prompts are known and no scene
#: matches, the story gets NO scene (the template shows the show's cover):
#: a picture of a different story under a headline is a false claim.
SCENE_MATCH_MIN_WORDS = 2


def episode_scene(index: Optional[dict], slug: str, episode_num: Optional[int],
                  episode_date: str, *, hook: str = "",
                  prompts: Optional[Dict[str, str]] = None,
                  portrait_first: bool = False,
                  avoid_urls: Iterable[str] = ()) -> Optional[Dict[str, Any]]:
    """A scene image of exactly this episode, landscape first.

    Matches show, ``epNNN`` AND date: an episode id alone could be reused
    after a catalogue prune (DP Pod's Aug 2026 purge), and a picture from a
    different episode beside this headline would be a false claim about it.
    An episode has one scene per story, so when *prompts* are given the scene
    whose prompt shares the most words with *hook* wins (SpaceX Ep133's first
    scene was the Optimus story; its Dragon scene is the one that belongs
    beside the Dragon headline). Otherwise the episode's first scene.
    ``portrait_first`` tries the 9:16 set first (a Short's card).
    ``avoid_urls`` skips scenes already printed elsewhere on the page, while
    the episode has another scene to offer (never another episode's).
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
    hook_words = _stems(hook)
    prompts = prompts or {}
    avoid = set(avoid_urls)
    order = ((LANDSCAPE_USE, "landscape"), (PORTRAIT_USE, "portrait"))
    for use, orientation in (order[::-1] if portrait_first else order):
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
                score = len(hook_words & _stems(prompts.get(str(row[i_id]), "")))
                candidates.append((score, position, url))
        if not candidates:
            continue
        fresh = [c for c in candidates if c[2] not in avoid]
        candidates = fresh or candidates
        best = max(candidates, key=lambda c: (c[0], -c[1]))
        runner_up = max((c[0] for c in candidates if c is not best), default=0)
        if best[0] >= SCENE_MATCH_MIN_WORDS or (best[0] == 1 and runner_up == 0):
            return {"url": best[2], "orientation": orientation, "matched": True}
        if prompts and hook_words:
            # The episode's prompts are known and none depicts this headline
            # in this orientation: try the other orientation, then nothing.
            continue
        return {"url": candidates[0][2], "orientation": orientation, "matched": False}
    return None


def more_headlines(content: str, hook: str, limit: int = MORE_HEADLINES) -> List[str]:
    """Up to *limit* of the digest's own story headlines, the hook's story
    excluded — by words, not by spelling: the digest titles the hook's story
    in its own words, and that headline is the hook a second time
    (``engine.newsroom.same_story``)."""
    from engine.grok_imagine import extract_story_headlines
    from engine.newsroom import headline_within_hook

    hook_key = _norm(hook)
    out: List[str] = []
    for headline in extract_story_headlines(content or "", max_count=limit + 4):
        key = _norm(headline)
        if not key or key == hook_key or key in hook_key or hook_key in key:
            continue
        # Nov 3 2026: ``headline_within_hook`` — ``same_story`` widened for a
        # hook that is two stories at once (the Nerra Daily email listed
        # "Sweden Jumps 248%" under the Sweden-and-Norway hook).
        if headline_within_hook(headline, hook):
            continue
        out.append(headline)
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# The deck: the digest's own sentences on the hook's story (Nov 3 2026)
# ---------------------------------------------------------------------------

#: A deck is at most this many sentences and about this many characters;
#: a first sentence may run over by the grace, never cut mid-sentence.
DECK_MAX_SENTENCES = 2
DECK_MAX_CHARS = 240
DECK_FIRST_SENTENCE_GRACE = 80

#: A sentence ends on . ! ? followed by a capital or a digit; a single
#: capital before the period ("U.S.", "D.C.") is an initial, not an end.
_DECK_SENTENCE_RE = re.compile(r"(?<![A-Z]\.)(?<=[.!?])\s+(?=[A-Z0-9“\"‘'(])")
#: ``Source: …`` tails on an item's last line, the parenthesised form too.
_DECK_SOURCE_TAIL_RE = re.compile(r"\(?\bSource:.*$", re.M)
#: A leading field label of a few words ("What happened (neutral):",
#: "Context & perspectives:", "Market Pulse:") — the body's own label, not
#: a sentence a reader wants.
_DECK_LABEL_RE = re.compile(r"^([^.!?:\n]{1,48}?):\s+(?=\S)")
_DECK_LABEL_MAX_WORDS = 4
_DECK_LEAD_NUM_RE = re.compile(r"^\s*\d+[.)]\s*")
_DECK_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
#: An item head's outlet tail: "— TSLAming (X)", ": Reuters".
_DECK_OUTLET_TAIL_MAX_WORDS = 6


def _deck_line_is_furniture(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if s.startswith((">", "#", "- ", "* ", "• ", "|")):
        return True
    if re.fullmatch(r"[-*_]{3,}", s):
        return True
    # A bold-only line is a heading or a label, never prose.
    return bool(re.fullmatch(r"\*\*[^*]+\*\*:?", s))


def _deck_body_lines(item) -> List[str]:
    """The prose lines of an aired item, its head and furniture removed."""
    lines = (item.body or "").splitlines()
    if item.kind == "item" and lines:
        # The first line is the item's head: ``1. **Title** — Outlet`` or
        # ``**Title: Outlet**``. Prose written on the head's own line
        # (``**Title**: the body starts here``) is kept.
        head = _DECK_LEAD_NUM_RE.sub("", lines[0])
        after = _DECK_BOLD_RE.sub("", head, count=1).strip()
        after = after.lstrip("—–-: ").strip()
        if len(after.split()) <= _DECK_OUTLET_TAIL_MAX_WORDS:
            after = ""
        lines = ([after] if after else []) + lines[1:]
    return [ln for ln in lines if not _deck_line_is_furniture(ln)]


def _deck_pick(items: list, hook: str):
    """The aired item that tells the hook's story, or ``None``."""
    from engine.aired_items import _LEAD_SECTIONS
    from engine.newsroom import headline_within_hook

    for item in items:
        if headline_within_hook(item.title, hook):
            return item
    for item in items:
        if (item.section or "").strip().lower() in _LEAD_SECTIONS:
            return item
    if items and len(_salient(items[0].title) & _salient(hook)) >= 2:
        return items[0]
    return None


def _norm_sentence(text: str) -> str:
    """A sentence as the flagged-sentence test compares it: links
    flattened, markdown and punctuation gone, one case."""
    from engine.aired_items import _plain
    return re.sub(r"[^a-z0-9]+", " ", _plain(text or "").lower()).strip()


def _sentence_is_flagged(sentence: str, flagged: Iterable[str]) -> bool:
    key = _norm_sentence(sentence)
    if not key:
        return False
    for flag in flagged:
        if not flag:
            continue
        if key == flag:
            return True
        # The gate records the claim's span, which can be a clause of the
        # sentence ("Jose de Navarro changed that when he installed …" of a
        # longer sentence) or the whole of it.
        if min(len(key), len(flag)) >= 40 and (flag in key or key in flag):
            return True
    return False


def story_deck(content: str, hook: str, *, max_sentences: int = DECK_MAX_SENTENCES,
               max_chars: int = DECK_MAX_CHARS, flagged: Iterable[str] = ()) -> str:
    """One or two sentences of the digest's own prose on the hook's story.

    Nov 3 2026 (the Nerra Daily email): a card was the spoken hook, up to
    three outlet headlines and a link row, so a reader learned no fact
    without clicking. The sentences already exist, verified, in the
    committed digest: this reads the aired item whose title is the hook's
    story (:func:`engine.newsroom.headline_within_hook`), else the lead
    section, else the first item when it shares two salient words with the
    hook, and returns its first sentences — the head line, labels,
    ``Source:`` tails and markdown gone. A record with no matching item gets
    ``""``: the hook stands alone rather than under another story's prose.
    A narrative episode (one ``essay`` item) opens on its cold open, which
    is the point of the show. A sentence the claims gate flagged
    (*flagged*: normalised sentences, see :func:`flagged_sentences_for`) is
    never printed — the Oct 1 2026 rule that a flag is never hidden. No
    sentence is ever cut: the deck stops before the sentence that would pass
    *max_chars*, and only a first sentence may run over, by
    :data:`DECK_FIRST_SENTENCE_GRACE`. Deterministic; no model call.
    """
    from engine.aired_items import _plain, extract_aired_items

    items = [i for i in extract_aired_items(content or "")
             if i.kind in ("item", "heading", "section", "essay")]
    pick = _deck_pick(items, hook)
    if pick is not None:
        lines = _deck_body_lines(pick)
    elif not items and content and not re.search(r"^(?:#|>)", content, re.M):
        # Plain prose with no digest shape at all (an interview record's
        # summary): the first paragraph is the deck.
        lines = [ln for ln in content.splitlines() if not _deck_line_is_furniture(ln)]
        lines = lines[:1]
    else:
        return ""
    text = " ".join(_plain(_DECK_SOURCE_TAIL_RE.sub("", ln)) for ln in lines)
    text = re.sub(r"\s+", " ", text).strip()
    m = _DECK_LABEL_RE.match(text)
    if m and len(m.group(1).split()) <= _DECK_LABEL_MAX_WORDS:
        text = text[m.end():]
    flagged = [f for f in flagged if f]
    out: List[str] = []
    total = 0
    for sentence in _DECK_SENTENCE_RE.split(text):
        sentence = sentence.strip()
        if not sentence or len(sentence.split()) < 3:
            continue
        if flagged and _sentence_is_flagged(sentence, flagged):
            continue
        add = len(sentence) + (1 if out else 0)
        limit = max_chars + (DECK_FIRST_SENTENCE_GRACE if not out else 0)
        if total + add > limit:
            break
        out.append(sentence)
        total += add
        if len(out) >= max_sentences:
            break
    return " ".join(out)


def flagged_sentences_for(show_dir, record: dict) -> frozenset:
    """The sentences the claims gate flagged on this episode, normalised for
    :func:`story_deck` — from the committed ``<stem>_claims.json`` beside
    the digest (``engine.claims_ledger.read_sidecar``), found by episode
    number (``*_EpNNN_*_claims.json``; a rerun's later file wins) or by the
    record's audio stem. An episode with no sidecar has nothing flagged."""
    if not show_dir or not isinstance(record, dict):
        return frozenset()
    show_dir = Path(show_dir)
    if not show_dir.is_dir():
        return frozenset()
    paths: List[Path] = []
    number = _episode_number(record)
    if number:
        paths.extend(sorted(show_dir.glob(f"*_Ep{int(number):03d}_*_claims.json")))
    stem = Path(str(record.get("audio_url") or "").split("?")[0]).stem
    if stem:
        beside = show_dir / f"{stem}_claims.json"
        if beside.is_file() and beside not in paths:
            paths.append(beside)
    if not paths:
        return frozenset()
    try:
        from engine.claims_ledger import read_sidecar
        side = read_sidecar(paths[-1])
    except Exception:  # noqa: BLE001 — a sidecar that will not read flags nothing
        side = None
    if not side:
        return frozenset()
    return frozenset(_norm_sentence(s) for s in side.get("flagged_sentences") or [] if s)


#: A headline reads as Title Case when this share of its words of four or
#: more letters are capitalised, over at least this many such words.
_TITLE_CASE_SHARE = 0.6
_TITLE_CASE_MIN_WORDS = 3
#: Always names, whatever the prose says.
_CALENDAR_WORDS = frozenset(
    "monday tuesday wednesday thursday friday saturday sunday january february "
    "march april may june july august september october november december".split())
_WORD_CORE_RE = re.compile(r"^([^\w]*)(.*?)([^\w]*)$", re.S)
_POSSESSIVE_RE = re.compile(r"(?:'s|’s|')$")
#: Lines that are a heading or a list carry Title Case of their own and are
#: no evidence of a name; a bold head or label is removed from a line before
#: it is read (an Omni View paragraph opens on ``**What happened:**``). The
#: hook's blockquote is prose and is read with its marker removed.
_PROSE_LINE_SKIP_RE = re.compile(r"^\s*(?:#|-\s|\*\s|•|\|)")


def _case_evidence(prose: str) -> tuple:
    """``(capitalised_mid_sentence, lowercase)`` counts per word of the
    digest's prose — the evidence :func:`sentence_case_headline` reads: a
    word the prose capitalises mid-sentence (and does not write lowercase
    more often) is a name; one it never capitalises there is a common word."""
    from collections import Counter

    caps: Counter = Counter()
    lower: Counter = Counter()
    for line in (prose or "").splitlines():
        if _PROSE_LINE_SKIP_RE.match(line):
            continue
        line = re.sub(r"^\s*>\s*", "", line)
        line = re.sub(r"\*\*[^*]+\*\*:?", " ", line)
        line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)
        for sentence in _DECK_SENTENCE_RE.split(line):
            words = sentence.split()
            for index, word in enumerate(words):
                core = _POSSESSIVE_RE.sub("", _WORD_CORE_RE.match(word).group(2))
                if not core.replace("-", "").isalpha():
                    continue
                if core[:1].isupper():
                    if index > 0:
                        caps[core.lower()] += 1
                elif core[:1].islower():
                    lower[core] += 1
    return caps, lower


def _keeps_case(core: str) -> bool:
    """An acronym, a ticker, a product with an internal capital, a figure."""
    if any(ch.isdigit() for ch in core):
        return True
    letters = [ch for ch in core if ch.isalpha()]
    if len(letters) >= 2 and all(ch.isupper() for ch in letters):
        return True
    return any(ch.isupper() for ch in core[1:])


def sentence_case_headline(headline: str, prose: str = "") -> str:
    """A Title Case outlet headline in sentence case; anything else untouched.

    Nov 3 2026 (the Nerra Daily email): the card's headlines are the digest
    items' titles, which outlets write in Title Case, under a hook and a
    deck in sentence case. A word is lowercased only when the headline reads
    as Title Case (:data:`_TITLE_CASE_SHARE` of its longer words capitalised),
    it is not the first word of a sentence, it is not an acronym or ticker
    (EV, TSLA), an internal capital (YoY, SpaceX) or a figure, and the
    digest's own prose does not capitalise it mid-sentence
    (:func:`_case_evidence` — Norway, October and Supercharger are kept;
    "sales", "growth" and a "New" that the prose writes lowercase more
    often than in "New Zealand" are lowercased). A word the prose never
    writes at all is lowercased too: the keep set is what the digest
    capitalised, as an editor would check it. Never clips: limits and
    truncation belong to ``engine.titles``.
    """
    headline = (headline or "").strip()
    words = headline.split()
    cores = [_WORD_CORE_RE.match(w).group(2) for w in words]
    # The shape test reads the PLAIN words: an acronym, a ticker or a
    # SpaceX-style brand is capitalised in any case and says nothing.
    plain = [c for c in cores if c.replace("-", "").isalpha() and len(c) >= 4
             and not _keeps_case(c)]
    capitalised = [c for c in plain if c[:1].isupper()]
    if len(plain) < _TITLE_CASE_MIN_WORDS or len(capitalised) / len(plain) < _TITLE_CASE_SHARE:
        return headline
    caps, lower = _case_evidence(prose)
    out: List[str] = []
    sentence_start = True
    for word in words:
        lead, core, trail = _WORD_CORE_RE.match(word).groups()
        if not core:
            out.append(word)
            continue
        parts = core.split("-")
        new_parts = []
        for i, part in enumerate(parts):
            base = _POSSESSIVE_RE.sub("", part)
            first = sentence_start and i == 0
            key = base.lower()
            name = (caps[key] > 0 and caps[key] >= lower[key]) or key in _CALENDAR_WORDS
            if first or not part[:1].isupper() or _keeps_case(base) or name:
                new_parts.append(part)
            else:
                new_parts.append(part[0].lower() + part[1:])
        out.append(lead + "-".join(new_parts) + trail)
        sentence_start = trail.rstrip("”\"’')").endswith((".", "!", "?"))
    return " ".join(out)


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
    # The interview records carry the whole hook as ``hook``; their title is
    # the feed title, clipped to 100 characters — "Michael Kamins — A CPG
    # hiring veteran builds candidate-owned living portfolios that let AI…"
    # was the Nov 2 email's card (Nov 3 2026). The news records have no
    # ``hook`` key and are unchanged.
    hook = (hook_from_markdown(content) or hook_from_markdown(digest_text)
            or (record.get("hook") or "").strip()
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


def _beat(story: Dict[str, Any]) -> str:
    hub = story.get("hub_id") or ""
    return _SAME_BEAT.get(hub, hub) or story.get("slug", "")


def _rotated_lead(ordered: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The newest day's pictured story from today's subject in
    ``LEAD_ROTATION`` (the audience ranking still picks WITHIN a subject)."""
    newest = ordered[0].get("date_obj") if ordered else None
    if not newest:
        return None
    pictured = [s for s in ordered
                if s.get("date_obj") == newest and s["image_orientation"] == "landscape"]
    start = newest.toordinal() % len(LEAD_ROTATION)
    for i in range(len(LEAD_ROTATION)):
        hub = LEAD_ROTATION[(start + i) % len(LEAD_ROTATION)]
        pick = next((s for s in pictured if s.get("hub_id") == hub), None)
        if pick is not None:
            return pick
    return None


def _varied(stories: Sequence[Dict[str, Any]], limit: int, *, seen: set) -> List[Dict[str, Any]]:
    """Up to ``limit`` stories, one per beat first (in the given order), then
    the rest in order — so the top of the page shows the network's range."""
    seen = set(seen)
    first, later = [], []
    for s in stories:
        (later if _beat(s) in seen else first).append(s)
        seen.add(_beat(s))
    return (first + later)[:limit]


def merge_retellings(ordered: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """*ordered* with a story another show already told folded into it.

    Two shows lead on one story more often than not on a slow day — on Oct
    28 2026 Planetterrian's "top story" and Longevity's Science lead were the
    same inulin-fiber knee trial, two cards apart. The first telling in the
    page's order (newest, then audience rank) keeps its place and gains an
    ``also_by`` list naming the other show's episode; the later telling is
    dropped from the lead, top stories and sections. The Latest list is
    built from the unmerged order: it is the record of what published.
    """
    from engine.newsroom import same_story

    kept: List[Dict[str, Any]] = []
    for story in ordered:
        twin = next((k for k in kept
                     if k["slug"] != story["slug"] and k.get("hook") and story.get("hook")
                     and same_story(k["hook"], story["hook"])), None)
        if twin is None:
            kept.append(story)
            continue
        twin.setdefault("also_by", []).append({
            "show_name": story["show_name"],
            "show_page": story["show_page"],
            "post_url": story.get("post_url") or "",
            "brand_color": story.get("brand_color") or "",
        })
    return kept


def assemble(stories: Iterable[Dict[str, Any]], *,
             audience_order: Sequence[str] = (),
             live_hub_ids: Iterable[str] = (),
             flagships: Sequence[str] = ()) -> Dict[str, Any]:
    """Lay the stories out: lead, flagships, top stories, latest list, sections.

    Deterministic: newest date first, then the audience ranking (30-day
    downloads, the homepage's own order), then slug. The lead is the first
    story with a landscape scene of its own, because a lead without a picture
    is not a front page; when no story has one, the first story leads anyway.

    A ``flagships`` show (``engine.brand.FLAGSHIP_SHOW_SLUGS``) gets its own
    band every day, in the given order, and so never also runs as the lead, a
    top story or a section story; it still appears in the Latest list, which
    is the chronological record.
    """
    rank = {slug: n for n, slug in enumerate(audience_order)}
    ordered = sorted(stories, key=_order_key(rank))
    flagship_order = {slug: n for n, slug in enumerate(flagships)}
    featured: List[Dict[str, Any]] = []
    if ordered and ordered[0].get("date_obj"):
        newest = ordered[0]["date_obj"]
        ordered = [
            s for s in ordered
            if s.get("date_obj") and (newest - s["date_obj"]).days <= MAX_STORY_AGE_DAYS
        ]
    if not ordered:
        return {"lead": None, "flagships": [], "top": [], "latest": [],
                "sections": [], "more": [], "edition_date": "",
                "story_count": 0, "today_count": 0}
    published = ordered
    ordered = merge_retellings(ordered)

    featured = sorted((s for s in ordered if s["slug"] in flagship_order),
                      key=lambda s: flagship_order[s["slug"]])
    pool = [s for s in ordered if s["slug"] not in flagship_order] or ordered
    if pool is ordered:  # nothing but flagships published: they lead as usual
        featured = []
    # Oct 31 2026: before dawn the only story out may have no landscape
    # picture (UC's scenes are portrait), and the page then led for up to 80
    # minutes with YESTERDAY's story under today's dateline. The newest day
    # comes first: its landscape story, then any of its stories with a
    # picture, and only then an older landscape lead.
    newest = pool[0].get("date_obj")
    lead = (_rotated_lead(pool)
            or next((s for s in pool if s.get("date_obj") == newest
                     and s["image_orientation"] == "landscape"), None)
            or next((s for s in pool if s.get("date_obj") == newest and s["image_url"]), None)
            or next((s for s in pool if s["image_orientation"] == "landscape"), pool[0]))
    rest = [s for s in pool if s is not lead]
    with_art = [s for s in rest if s["image_url"]]
    top = _varied((with_art + [s for s in rest if not s["image_url"]]),
                  TOP_STORY_COUNT, seen={_beat(lead)})
    placed = {id(lead), *(id(s) for s in top), *(id(s) for s in featured)}

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

    newest = published[0]["date_obj"]
    return {
        "lead": lead,
        "flagships": featured,
        "top": top,
        "latest": published[:LATEST_LIMIT],
        "sections": sections,
        "more": leftovers,
        "edition_date": (f"{newest.strftime('%A, %B')} {newest.day}, {newest.year}"
                         if newest else ""),
        "story_count": len(published),
        "today_count": sum(1 for s in published if s.get("date_obj") == newest),
    }


# ---------------------------------------------------------------------------
# v2 — the rest of the site on the front page (Oct 17 2026, second pass)
# ---------------------------------------------------------------------------
#
# Everything below is read from committed files by generate_html and passed
# in; nothing here opens a file. Each helper returns an empty value when its
# input is missing, and the template renders a section only when its value
# is non-empty — unknown data renders nothing.

#: The interview shows (``engine.interviews.INTERVIEW_SHOW_SLUGS``) are the
#: site's strongest web draw (GA4, 28 days to Oct 16 2026: an Age of AI
#: article and its show page were the 2nd and 3rd landing pages). They get a
#: "Conversations" section of their own instead of competing as one more
#: news story, so they are left out of the story flow.
CONVERSATION_SLUGS = tuple(INTERVIEW_SHOW_SLUGS)

#: Conversations shown: one feature + the rest as a list.
CONVERSATION_LIMIT = 5

#: Watch: newest EN long-form per show, and newest hook Short per show.
WATCH_LONG_LIMIT = 4
#: The Shorts reel (Oct 18 2026): one card per show, so in practice this is
#: "every show with a recent Short" — the reel is the front page's widest
#: discovery surface, and a visitor scrolls it sideways.
WATCH_SHORT_LIMIT = 16

#: Gallery strip on the front page.
GALLERY_STRIP_LIMIT = 8

#: "Most read" rows from GA4's top pages.
MOST_READ_LIMIT = 5

_HASHTAG_TAIL_RE = re.compile(r"(?:\s+#\w+)+\s*$")


def strip_hashtag_tail(title: str) -> str:
    """``"SpaceX Dragon Runs… #Shorts"`` -> ``"SpaceX Dragon Runs…"``.

    Dropping a trailing platform hashtag is not clipping a title: every word
    of the title is kept, only the tag YouTube needs is removed."""
    return _HASHTAG_TAIL_RE.sub("", (title or "").strip()).strip()


def _video_date(video: dict) -> Optional[date]:
    return _parse_date(str(video.get("published") or ""))


def pick_videos(videos: Iterable[dict], *, kind: str, public_slugs: Iterable[str],
                limit: int, audience_order: Sequence[str] = (),
                channel: str = "en", max_age_days: int = MAX_STORY_AGE_DAYS,
                now=None) -> List[dict]:
    """The newest video of *kind* per show, newest first, at most *limit*.

    Rows are the committed ``digests/<dir>/youtube_videos.json`` entries the
    caller loaded. Only *channel* (English by default — the dub channels get
    a subscribe link, not a card), only public shows, only a
    ``https://www.youtube.com/`` watch URL, and nothing older than
    *max_age_days* before the newest video picked. For Shorts the hook Short
    (``window == "hook_open"``) wins over another window of the same day.
    """
    public = set(public_slugs)
    rank = {slug: n for n, slug in enumerate(audience_order)}
    best: Dict[str, dict] = {}
    for video in videos:
        if not isinstance(video, dict):
            continue
        slug = str(video.get("show_slug") or "")
        url = str(video.get("watch_url") or "")
        when = _video_date(video)
        if (video.get("kind") != kind or slug not in public
                or (video.get("channel") or "en") != channel
                or not url.startswith("https://www.youtube.com/") or not when
                or not strip_hashtag_tail(video.get("title") or "")):
            continue
        # Oct 18 2026: a scheduled video is private until its publish_at —
        # never a card a visitor clicks into "Video unavailable".
        if is_still_scheduled(str(video.get("publish_at") or ""), now=now):
            continue
        ep = video.get("episode") if isinstance(video.get("episode"), int) else 0
        key = (when, 1 if video.get("window") == "hook_open" else 0, ep)
        current = best.get(slug)
        if current is None or key > current[0]:
            best[slug] = (key, video)
    chosen = sorted(best.values(),
                    key=lambda kv: (-kv[0][0].toordinal(),
                                    rank.get(kv[1]["show_slug"], 10_000),
                                    kv[1]["show_slug"]))
    if chosen:
        newest = chosen[0][0][0]
        chosen = [kv for kv in chosen if (newest - kv[0][0]).days <= max_age_days]
    out = []
    for key, video in chosen[:limit]:
        row = dict(video)
        row["display_title"] = strip_hashtag_tail(video.get("title") or "")
        row["date_raw"] = key[0].isoformat()
        row["date"] = _display_date(row["date_raw"])
        out.append(row)
    return out


#: A YouTube video id: 11 URL-safe base64 characters.
_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YT_URL_RES = (
    re.compile(r"^https://(?:www\.|m\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})(?:[/?#]|$)"),
    re.compile(r"^https://(?:www\.|m\.)?youtube\.com/watch\?(?:[^#]*&)?v=([A-Za-z0-9_-]{11})(?:[&#]|$)"),
    re.compile(r"^https://youtu\.be/([A-Za-z0-9_-]{11})(?:[/?#]|$)"),
)


def youtube_video_id(watch_url: str) -> str:
    """The video id in a ``/shorts/<id>`` or ``watch?v=<id>`` URL, else "".

    Read from the URL the index committed, never guessed: a row whose URL
    does not parse gets no in-page player (its card links out instead)."""
    url = str(watch_url or "").strip()
    for pattern in _YT_URL_RES:
        match = pattern.match(url)
        if match:
            return match.group(1)
    return ""


def youtube_embed_url(video_id: str) -> str:
    """The privacy-enhanced (``youtube-nocookie.com``) embed for *video_id*.

    The page never loads it until a visitor presses Play (facade pattern):
    no YouTube frame, script or cookie on the initial page."""
    if not _YT_ID_RE.match(str(video_id or "")):
        return ""
    # enablejsapi: the player script listens for the frame's own onError
    # message (no YouTube script on our page) and offers "Watch on YouTube"
    # when a video cannot play embedded.
    return (f"https://www.youtube-nocookie.com/embed/{video_id}"
            "?autoplay=1&playsinline=1&rel=0&enablejsapi=1")


def preview_url(video: dict) -> str:
    """A Short row's muted preview loop (``engine.short_preview``), when the
    video stage recorded one — an https MP4 only, else ""."""
    url = str((video or {}).get("preview_url") or "").strip()
    return url if url.startswith("https://") and url.split("?")[0].endswith(".mp4") else ""


def order_shorts_for_discovery(shorts: Sequence[dict], *,
                               hub_for: Dict[str, Dict[str, Any]],
                               limit: int = WATCH_SHORT_LIMIT) -> List[dict]:
    """The reel's order: one Short per beat first (the front page's variety
    rule, ``_beat`` — SpaceX and Tesla are one beat), in the order given
    (``pick_videos``: newest, then audience), then the rest in that order.

    ``pick_videos`` already holds one card per show; this decides who a
    visitor meets first. The flagships are not pinned to the front: the reel
    sits directly under their own band, so leading with them again would
    spend the first two cards on the shows the visitor just passed.
    """
    def beat(video: dict) -> str:
        hub = hub_for.get(video.get("show_slug") or "") or {}
        return _beat({"hub_id": hub.get("id") or "", "slug": video.get("show_slug") or ""})

    return _varied_by(shorts, limit, beat)


def _varied_by(items: Sequence[dict], limit: int, beat: Callable[[dict], str]) -> List[dict]:
    seen: set = set()
    first, later = [], []
    for item in items:
        b = beat(item)
        (later if b in seen else first).append(item)
        seen.add(b)
    return (first + later)[:limit]


def gallery_strip(index: Optional[dict], *, public_slugs: Iterable[str],
                  show_names: Optional[Dict[str, str]] = None,
                  exclude_urls: Iterable[str] = (),
                  limit: int = GALLERY_STRIP_LIMIT) -> List[Dict[str, str]]:
    """Recent landscape scene thumbnails for the gallery strip.

    From the network's SLIM gallery index (``_network.index.json`` — never
    the 22 MB manifest): newest episode first, one image per show so the
    strip shows the network rather than one flagship, public shows only,
    story scenes only (``segment_card``; book art is never a scene), and no
    image already printed beside a story on this page.
    """
    if not isinstance(index, dict):
        return []
    ef = index.get("episode_fields") or []
    imf = index.get("image_fields") or []
    try:
        e_slug, e_date, e_id = (ef.index("show_slug"), ef.index("episode_date"),
                                ef.index("episode_id"))
        i_id, i_ep, i_use = (imf.index("image_id"), imf.index("episode"),
                             imf.index("intended_use"))
    except ValueError:
        return []
    base = (index.get("base_url") or "").rstrip("/")
    overrides = index.get("overrides") or {}
    episodes = index.get("episodes") or []
    public = set(public_slugs)
    names = show_names or {}
    skip = set(exclude_urls)
    candidates = []
    for position, row in enumerate(index.get("images") or []):
        if len(row) <= max(i_id, i_ep, i_use) or row[i_use] != LANDSCAPE_USE:
            continue
        n = row[i_ep]
        if not isinstance(n, int) or not 0 <= n < len(episodes):
            continue
        ep = episodes[n]
        if len(ep) <= max(e_slug, e_date, e_id):
            continue
        slug, ep_date, ep_id = ep[e_slug], str(ep[e_date] or ""), str(ep[e_id] or "")
        if slug not in public or not _parse_date(ep_date):
            continue
        url = (overrides.get(str(position)) or {}).get("thumbnail_url") or (
            f"{base}/{slug}/{ep_date}/{ep_id}/{row[i_id]}.thumb.webp" if base else "")
        if not url.startswith("https://") or url in skip:
            continue
        candidates.append((ep_date, position, slug, ep_id, url))
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    seen, out = set(), []
    for ep_date, _pos, slug, ep_id, url in candidates:
        if slug in seen:
            continue
        seen.add(slug)
        digits = re.sub(r"\D", "", ep_id)
        out.append({
            "url": url,
            "show_slug": slug,
            "show_name": names.get(slug, slug),
            "episode_num": str(int(digits)) if digits else "",
            "date": _display_date(ep_date),
        })
        if len(out) >= limit:
            break
    return out


_BLOG_EP_PATH_RE = re.compile(r"^/blog/([a-z0-9_]+)/ep(\d{3,4})\.html$")


def most_read_pages(ga4: Optional[dict], *, public_slugs: Iterable[str],
                    limit: int = MOST_READ_LIMIT) -> List[tuple]:
    """``[(slug, episode_num), …]`` — the most-viewed episode ARTICLES in the
    committed GA4 snapshot (``api/ga4_stats.json`` ``top_pages``), in GA4's
    order. Show pages and the homepage are not articles and are skipped, as
    is any show that is not public. No view count leaves this function: at
    this site's size a number would read as anti-proof; the rank is the
    information."""
    if not isinstance(ga4, dict):
        return []
    public = set(public_slugs)
    out: List[tuple] = []
    for row in ga4.get("top_pages") or []:
        if not isinstance(row, dict):
            continue
        match = _BLOG_EP_PATH_RE.match(str(row.get("pagePath") or ""))
        if not match or match.group(1) not in public:
            continue
        key = (match.group(1), int(match.group(2)))
        if key not in out:
            out.append(key)
        if len(out) >= limit:
            break
    return out


def _int(value) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def glance_numbers(audience: Optional[dict], *, shows_publishing: int,
                   episodes_this_week: Optional[int], languages: int,
                   claims: Optional[dict] = None) -> List[Dict[str, str]]:
    """The "network at a glance" tiles: computed, never typed.

    Each tile is ``{"value", "label"}``. A figure the committed data does not
    carry is left out — never printed as 0. *audience* is
    ``api/audience_headline.json``; *claims* is the network totals block the
    claims page renders (``engine.claims_ledger.network_ledger``).
    """
    tiles: List[Dict[str, str]] = []
    if shows_publishing > 0:
        tiles.append({"value": f"{shows_publishing}", "label": "public shows publishing"})
    if _int(episodes_this_week):
        tiles.append({"value": f"{episodes_this_week:,}",
                      "label": "new episodes in the last 7 days"})
    if languages > 1:
        tiles.append({"value": f"{languages}", "label": "languages to listen in"})
    net = audience.get("network") if isinstance(audience, dict) else None
    net = net if isinstance(net, dict) else {}
    downloads = _int(net.get("downloads_30d"))
    if downloads:
        label = "podcast downloads in 30 days"
        wow = net.get("wow_pct")
        if isinstance(wow, (int, float)) and not isinstance(wow, bool) and wow >= 1:
            label += f", up {round(wow)}% on the week before"
        tiles.append({"value": f"{downloads:,}", "label": label})
    yt = net.get("youtube") if isinstance(net.get("youtube"), dict) else {}
    views = _int(yt.get("views"))
    if views:
        tiles.append({"value": f"{views:,}", "label": "YouTube views in 28 days"})
    totals = claims if isinstance(claims, dict) else {}
    checked = _int(totals.get("claims"))
    if checked:
        tiles.append({"value": f"{checked:,}",
                      "label": f"claims checked against their sources in "
                               f"{totals.get('days') or 30} days"})
    return tiles
