"""Nerra Daily email: one network newsletter, each subscriber's own shows.

Nov 1 2026, operator-directed. The network sent one daily email per show
(about 19 attempts a morning, ten delivered to one to three people each,
five failing every day on a tag no subscriber carried yet) plus a
synthesized weekly per show on Sunday. A reader following five shows got
five emails a day. Meanwhile the free account and every RSS episode
promised "the Nerra newsletter" and nothing was ever sent to that list.

Now there is ONE email, **Nerra Daily**, scheduled for 7:00 AM Eastern
right after the edition publishes. Buttondown renders Django templating per
subscriber (``{% if 'Tesla Shorts Time' in subscriber.tags %}``), so a single
email carries:

* today's Nerra Daily edition (the featured card);
* one card per show the reader follows (the show's newsletter tag is the
  follow, the same tag the show pages, the footer form and My Nerra set);
* a default set for readers who follow nothing yet, with a link to choose;
* one line for every other show that published ("Also on Nerra today");
* on Sunday, the week's most-played episodes and a week list per followed
  show (the Sunday edition replaces the per-show weeklies);
* one line about Nerra Personal, hidden from paying members
  (:data:`PAID_TAG`, which the account Worker sets and removes).

The data is ``api/personal_front.json`` (the homepage build's per-show story
rows: full hook, the deck — one or two sentences of the digest's own prose on
the hook's story, ``engine.landing_test.story_deck`` — headlines, post link)
plus the shows' YouTube indexes. Nothing here calls a model. Every link to
the site is funnel-tagged through :func:`engine.funnel.newsletter_link`.

Nov 3 2026 — the email reads as a briefing: a compact masthead so the first
phone screen carries news (the first show headline sat at y = 788 px on a
390 px phone under the full hero, a featured card repeating the subject and
a paragraph about the layout), a sourced deck under every card, two more
headlines in sentence case, the edition's card after the reader's shows,
"Also on Nerra today" as short headlines grouped by subject, and every
headline whole (the interview and most-played rows had printed clipped feed
titles ending "…").

Russian shows keep their own daily email (``newsletter.delivery: own``) and
are never sections here: a different audience in a different language.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://nerranetwork.com"

#: The email's name, everywhere it is shown.
EMAIL_NAME = "Nerra Daily"
#: The registry slug the email is branded and counted under.
EMAIL_SLUG = "nerra_daily"

# --- Buttondown tags this email reads -----------------------------------
#: Every free account (join page, Soft Personal with the box ticked).
MEMBER_TAG = "nerra-member"
#: The gallery gate's signup ("receive emails from Nerra Network").
GALLERY_TAG = "gallery-subscriber"
#: Set by the account Worker while a Personal subscription is active.
PAID_TAG = "personal-paid"
#: Set from My Nerra: this reader wants the Sunday edition only.
WEEKLY_ONLY_TAG = "nerra-daily-weekly"

#: Shows a reader who follows none of today's shows sees in full: the
#: flagships and the breadth of the network, in this order.
DEFAULT_SHOWS: Tuple[str, ...] = (
    "spacex", "tesla", "omni_view_world", "models_agents",
    "fascinating_frontiers",
)
#: Never a section: the edition itself (the email IS its notes). Nov 3 2026:
#: ``nerra_voices`` left this set — the comment had called it "the interview
#: room with no feed" while the show had four published episodes and the
#: site's third-busiest landing page; an interview published inside the
#: window is news like any other show's episode.
EXCLUDED_SLUGS = frozenset({"nerra_daily"})
#: Headlines under each card's deck (the card's own hook excluded). Three
#: until Nov 3 2026; the deck carries the story now, and the headlines are
#: the "Also in this episode" run.
HEADLINES_PER_CARD = 2
#: Where Gmail clips a message (the whole HTML part, Buttondown's wrapper
#: included) and the margin the warning keeps under it.
GMAIL_CLIP_BYTES = 102_000
SIZE_MARGIN_BYTES = 2_000
#: Bytes Buttondown adds around the body it is given. The send script had
#: warned at 95,000 bytes of OUR copy while saying "including Buttondown's
#: own wrapper", a number nobody had measured. Measured Nov 3 2026 as an
#: UPPER BOUND from the archive page of the Nov 2 send (its chrome before and
#: after our blocks: 17,096 + 8,943 bytes; the archive page carries a site
#: head, a subscribe form and a settings blob the delivered email does not,
#: so the real wrapper is smaller). Re-measure ONCE from a draft sent to a
#: test mailbox (``--mode draft --test-to``; the message's HTML part minus
#: the composed copy) and replace the number and the date. Never read
#: ``/v1/emails/{id}`` for it: its ``body`` is the body as submitted.
BUTTONDOWN_WRAPPER_BYTES = 26_039
BUTTONDOWN_WRAPPER_MEASURED = "2026-11-03, archive page of the Nov 2 send (upper bound)"


def size_warning_bytes() -> int:
    """The largest copy of OUR body that still clears Gmail's clip with the
    wrapper and a margin on top."""
    return GMAIL_CLIP_BYTES - BUTTONDOWN_WRAPPER_BYTES - SIZE_MARGIN_BYTES
#: An episode older than this is never news in today's email.
WINDOW_DAYS = 2
#: Episodes listed per followed show in the Sunday week list.
WEEK_LIST_MAX = 3
#: Most-played episodes in the Sunday block.
MOST_PLAYED_MAX = 5
#: Where a sent email's record lives (committed; the idempotency key).
MARKER_DIR = Path("digests") / "nerra_daily" / "email"

_BODY_FONT = ("font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
              "Roboto,Helvetica,Arial,sans-serif;")
_LINK = "color:#2563eb;"
#: Nov 8 2026 — the email reads like the front page (operator: "more like
#: the landing page and more like a news update"): serif headlines, the
#: landing's navy masthead, "SECTION / SHOW" kickers, a lead story with its
#: picture, and stories separated by rules rather than boxed as cards.
_SERIF = "font-family:Georgia,Times,serif;"
_NAVY = "#0b1220"
_ACCENT = "#6B47FF"
_KICKER = ("font-size:12px;font-weight:700;letter-spacing:.08em;"
           "text-transform:uppercase;line-height:1.4;margin:0 0 6px")
#: Width of a story's picture beside its headline, and of the lead picture.
THUMB_PX = 96
LEAD_IMAGE_PX = 552
#: Reporting links listed under a story ("More in this episode").
READS_PER_CARD = 2
# The lead carries more of its episode's reporting than a card.
LEAD_READS = 3
#: Shows that may lead the email, in rotation by date. The flagships never
#: lead (engine.brand.FLAGSHIP_SHOW_SLUGS: a flagship never also runs as the
#: lead); a reader who follows them has their cards right under it.
LEAD_POOL: Tuple[str, ...] = (
    "omni_view_world", "fascinating_frontiers", "models_agents", "planetterrian",
    "omni_view", "ai_chips", "unintended_consequences", "first_principles",
    "mag7", "modern_investing", "longevity", "prediction_markets",
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _esc(text: Any) -> str:
    """HTML-escape *text* and neutralise template braces.

    Buttondown runs every body through Django templating, so a headline
    carrying ``{{`` or ``{%`` (code on M&A, a JSON sample) would be read as
    template syntax and either vanish or fail the render. Braces become
    entities, which the template engine ignores and every mail client
    shows as braces.
    """
    out = html.escape(str(text or ""), quote=True)
    return out.replace("{", "&#123;").replace("}", "&#125;")


def _tag_literal(tag: str) -> Optional[str]:
    """A Django string literal for *tag*, or ``None`` when it cannot be one."""
    tag = (tag or "").strip()
    if not tag or "\n" in tag:
        return None
    if "'" not in tag:
        return f"'{tag}'"
    if '"' not in tag:
        return f'"{tag}"'
    return None


# Nov 3 2026: every condition also decides the ARCHIVE copy — the "View this
# email in your browser" page, the share links' target, what a search engine
# indexes — where Buttondown renders with NO subscriber in the context. There
# Django's ``in`` / ``not in`` both evaluate to False (the lookup raises and
# the operator swallows it), so the Nov 2 archive carried the hero, an empty
# "Also on Nerra today" heading and the footer: no card, no line, no news.
# A "not followed" condition therefore opens with ``not subscriber or`` (an
# absent reader reads the default copy: five cards and every one-liner) and a
# "followed" condition with ``subscriber and``. Django precedence is
# ``not`` > ``and`` > ``or`` and ``or`` short-circuits, so no parentheses are
# needed; :func:`render_for` evaluates the same subset with ``subscriber``.

def tag_in(tag: str) -> str:
    """``{% if subscriber and '<tag>' in subscriber.tags %}`` (never true for a bad tag)."""
    lit = _tag_literal(tag)
    return "{% if " + (f"subscriber and {lit} in subscriber.tags" if lit else "False") + " %}"


def tag_not_in(tag: str) -> str:
    lit = _tag_literal(tag)
    return "{% if " + (f"not subscriber or {lit} not in subscriber.tags" if lit else "True") + " %}"


def any_of(tags: Iterable[str]) -> str:
    """``{% if not subscriber or 'a' in subscriber.tags or 'b' in subscriber.tags %}``
    — true for a reader who follows any of *tags*, and on the archive."""
    lits = [lit for lit in (_tag_literal(t) for t in tags) if lit]
    if not lits:
        return "{% if False %}"
    return "{% if not subscriber or " + " or ".join(f"{lit} in subscriber.tags" for lit in lits) + " %}"


def followed_any_of(tags: Iterable[str]) -> str:
    """``{% if subscriber and 'a' in subscriber.tags or subscriber and 'b' in … %}``
    — true only for a READER who follows one of *tags*; never on the archive
    copy, which has no reader (the "Your shows today" heading had rendered
    there over nothing, above the default set — Nov 3 2026)."""
    lits = [lit for lit in (_tag_literal(t) for t in tags) if lit]
    if not lits:
        return "{% if False %}"
    return "{% if " + " or ".join(f"subscriber and {lit} in subscriber.tags" for lit in lits) + " %}"


def any_not_in(tags: Iterable[str]) -> str:
    """``{% if not subscriber or 'a' not in subscriber.tags or 'b' not in … %}``
    — true for a reader who does NOT follow at least one of *tags* (the
    "Also on Nerra today" heading has something under it), and on the archive."""
    lits = [lit for lit in (_tag_literal(t) for t in tags) if lit]
    if not lits:
        return "{% if False %}"
    return "{% if not subscriber or " + " or ".join(f"{lit} not in subscriber.tags" for lit in lits) + " %}"


def none_of(tags: Iterable[str]) -> str:
    """``{% if not subscriber or 'a' not in subscriber.tags and 'b' not in subscriber.tags %}``.

    Django's ``{% if %}`` has no parentheses, so every condition in this
    module is a flat ``and`` / ``or`` chain or a nested ``{% if %}``.
    """
    lits = [lit for lit in (_tag_literal(t) for t in tags) if lit]
    if not lits:
        return "{% if True %}"
    return "{% if not subscriber or " + " and ".join(f"{lit} not in subscriber.tags" for lit in lits) + " %}"


ENDIF = "{% endif %}"


def _when(day: dt.date) -> str:
    return f"{day.strftime('%A')}, {day.strftime('%B')} {day.day}"


def _short_day(day: dt.date) -> str:
    return f"{day.strftime('%b')} {day.day}"


def _parse_day(value: Any) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _duration_words(seconds: Optional[int]) -> str:
    if not seconds or seconds <= 0:
        return ""
    minutes = int(round(seconds / 60.0))
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    return f"{hours} h {rest} min" if rest else f"{hours} h"


def _absolute(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return f"{SITE}/{url.lstrip('/')}"


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

@dataclass
class EmailShow:
    """One show this email can carry."""

    slug: str
    name: str
    tag: str
    brand: str
    brand_text: str
    schedule: str = ""
    show_page: str = ""
    stories: List[Dict[str, Any]] = field(default_factory=list)


def _show_yaml(slug: str, root: Path) -> dict:
    path = root / "shows" / f"{slug}.yaml"
    if not path.is_file():
        return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 — a bad YAML is a missing show here
        return {}


def show_delivery(slug: str, root: Path = ROOT) -> str:
    """``"nerra_daily"`` or ``"own"`` for *slug* (``_defaults.yaml`` + YAML)."""
    defaults = _show_yaml("_defaults", root)
    own = _show_yaml(slug, root)
    value = ((own.get("newsletter") or {}).get("delivery")
             or (defaults.get("newsletter") or {}).get("delivery")
             or "own")
    return str(value).strip() or "own"


def newsletter_tag(slug: str, root: Path = ROOT) -> str:
    return str(((_show_yaml(slug, root).get("newsletter") or {}).get("tag") or "")).strip()


def russian_tags(root: Path = ROOT) -> List[str]:
    """Every Buttondown tag that marks a Russian-show subscriber.

    The YAML tag (``Finansy Prosto``) and the show's own Cyrillic name, which
    older signups carry (both exist on the account).
    """
    from engine.show_lang import page_lang

    tags: List[str] = []
    for path in sorted((root / "shows").glob("*.yaml")):
        slug = path.stem
        if slug.startswith("_") or page_lang(slug) != "ru":
            continue
        data = _show_yaml(slug, root)
        for value in ((data.get("newsletter") or {}).get("tag"), data.get("name")):
            value = str(value or "").strip()
            if value and value not in tags:
                tags.append(value)
    return tags


def email_show_tags(root: Path = ROOT) -> Dict[str, str]:
    """slug -> newsletter tag for every show a reader can follow in the email.

    Public English shows that are sections of Nerra Daily, in the registry's
    display order. The account Worker mirrors this map
    (``workers/gallery/src/email.ts`` ``EMAIL_SHOW_TAGS``; drift-guarded) so
    My Nerra and the email agree on what a follow is.
    """
    from engine import access
    from engine.config import load_config
    from engine.show_lang import page_lang

    try:
        from generate_html import NETWORK_SHOWS
        order = list(NETWORK_SHOWS)
    except Exception:  # noqa: BLE001
        order = []
    slugs = order + sorted(p.stem for p in (root / "shows").glob("*.yaml")
                           if p.stem not in order)
    out: Dict[str, str] = {}
    for slug in slugs:
        path = root / "shows" / f"{slug}.yaml"
        if slug.startswith("_") or slug in EXCLUDED_SLUGS or not path.is_file():
            continue
        tag = newsletter_tag(slug, root)
        if not tag or page_lang(slug) != "en" or show_delivery(slug, root) != "nerra_daily":
            continue
        try:
            if access.is_gated(load_config(str(path))):
                continue
        except Exception:  # noqa: BLE001 — a show that will not load is not offered
            continue
        out[slug] = tag
    return out


def load_front(root: Path = ROOT) -> dict:
    path = root / "api" / "personal_front.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def eligible_shows(front: dict, root: Path = ROOT) -> List[EmailShow]:
    """Public English shows with a newsletter tag, in the front's order.

    The order is the homepage's (registry display order), so the email reads
    like the site. Members-only shows are never sections: their digests are
    not public and the email's archive copy is.
    """
    from engine.show_lang import page_lang
    from engine.newsletter_template import _load_show_branding

    out: List[EmailShow] = []
    for slug, entry in (front.get("shows") or {}).items():
        if slug in EXCLUDED_SLUGS or entry.get("members_only"):
            continue
        if page_lang(slug) != "en":
            continue
        if show_delivery(slug, root) != "nerra_daily":
            continue
        tag = newsletter_tag(slug, root)
        if not tag:
            continue
        branding = _load_show_branding(slug)
        out.append(EmailShow(
            slug=slug,
            name=entry.get("name") or branding.get("name") or slug,
            tag=tag,
            brand=entry.get("brand_color") or branding.get("brand_color") or "#6B47FF",
            brand_text=branding.get("brand_color_dark") or "#4338ca",
            schedule=entry.get("schedule") or "",
            show_page=entry.get("show_page") or "",
            stories=list(entry.get("stories") or []),
        ))
    return out


def marker_path(day: dt.date, root: Path = ROOT) -> Path:
    return root / MARKER_DIR / f"{day.isoformat()}.json"


def read_marker(day: dt.date, root: Path = ROOT) -> Optional[dict]:
    try:
        return json.loads(marker_path(day, root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def already_sent(day: dt.date, root: Path = ROOT, *, lookback_days: int = 7) -> Dict[str, set]:
    """``{slug: {episode numbers}}`` carried by the emails before *day*."""
    sent: Dict[str, set] = {}
    for back in range(1, lookback_days + 1):
        record = read_marker(day - dt.timedelta(days=back), root) or {}
        for slug, eps in (record.get("included") or {}).items():
            for ep in eps or []:
                try:
                    sent.setdefault(slug, set()).add(int(ep))
                except (TypeError, ValueError):
                    continue
    return sent


@dataclass
class Pick:
    """The episode a show contributes to today's email."""

    show: EmailShow
    story: Dict[str, Any]
    included: List[int]


def pick_stories(shows: Sequence[EmailShow], day: dt.date,
                 sent: Dict[str, set]) -> List[Pick]:
    """Each show's newest episode not carried by an earlier email.

    An episode is news for :data:`WINDOW_DAYS` days. Vancouver publishes
    after the 7:00 email, so its episode arrives the next morning; a weekly
    show's episode arrives on its day. Every unsent episode inside the window
    is recorded as carried, so a show that published twice is never listed
    twice on later days.
    """
    picks: List[Pick] = []
    oldest = day - dt.timedelta(days=WINDOW_DAYS)
    for show in shows:
        fresh = []
        for story in show.stories:
            when = _parse_day(story.get("date_raw"))
            try:
                ep = int(story.get("episode_num") or 0)
            except (TypeError, ValueError):
                ep = 0
            if not ep or when is None or when > day or when < oldest:
                continue
            if ep in sent.get(show.slug, set()):
                continue
            fresh.append((ep, story))
        if not fresh:
            continue
        fresh.sort(key=lambda pair: pair[0], reverse=True)
        picks.append(Pick(show=show, story=fresh[0][1],
                          included=sorted(ep for ep, _ in fresh)))
    return picks


def video_links(slug: str, root: Path, now: dt.datetime) -> Dict[int, dict]:
    """The show's YouTube links per episode, scheduled ones included.

    A long-form and its hook Short go public in the release slots after
    7:00 ET; the email names the time instead of leaving the link out.
    """
    try:
        from generate_html import NETWORK_SHOWS
        from engine.youtube_index import episode_video_links
        cfg = NETWORK_SHOWS.get(slug) or {}
        if not cfg.get("json_path"):
            return {}
        path = root / Path(cfg["json_path"]).parent / "youtube_videos.json"
        return episode_video_links(path, now=now, include_scheduled=True)
    except Exception:  # noqa: BLE001 — videos are a bonus, never a blocker
        return {}


def week_records(slug: str, day: dt.date, root: Path = ROOT) -> List[Dict[str, Any]]:
    """The show's episodes from the seven days ending *day*, newest first."""
    try:
        from generate_html import NETWORK_SHOWS
        from engine import landing_test as lt
        cfg = NETWORK_SHOWS.get(slug) or {}
        if not cfg.get("json_path"):
            return []
        rows = []
        for rec in lt.recent_records(root / cfg["json_path"], 14):
            when = _parse_day(rec.get("date"))
            if when is None or when > day or when <= day - dt.timedelta(days=7):
                continue
            hook = (rec.get("hook") or "").strip() or lt.hook_from_markdown(
                rec.get("content") or rec.get("summary") or "")
            ep = lt._episode_number(rec)
            if not ep or not hook:
                continue
            rows.append({"episode_num": int(ep), "date": when, "hook": hook})
        return rows[:WEEK_LIST_MAX]
    except Exception:  # noqa: BLE001
        return []


def record_hook(slug: str, episode: int, root: Path = ROOT) -> str:
    """The episode's whole hook from its summaries record, or ``""``."""
    try:
        from generate_html import NETWORK_SHOWS
        from engine import landing_test as lt
        cfg = NETWORK_SHOWS.get(slug) or {}
        if not cfg.get("json_path"):
            return ""
        rec = lt.record_by_number(root / cfg["json_path"], int(episode))
        if not rec:
            return ""
        return ((rec.get("hook") or "").strip()
                or lt.hook_from_markdown(rec.get("content") or rec.get("summary") or ""))
    except Exception:  # noqa: BLE001 — the clipped title is the fallback
        return ""


def most_played(root: Path = ROOT, limit: int = MOST_PLAYED_MAX) -> List[Dict[str, Any]]:
    """The week's most-downloaded episodes (``site/data/popular_episodes.json``).

    The file's ``title`` is the FEED title, clipped to 100 characters with
    its ``Ep N:`` label ("…for a full-duration static…" on the Nov 1 send);
    the whole hook is read from the episode's record and the clipped title
    stands in only when the record is missing (Nov 3 2026).
    """
    from engine import landing_test as lt

    try:
        rows = json.loads((root / "site" / "data" / "popular_episodes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    seen: set = set()
    for row in rows if isinstance(rows, list) else []:
        title = str(row.get("title") or "")
        ep = lt.episode_number_from_title(title)
        slug = row.get("show_slug") or ""
        # One per show: the OP3 ranking is usually led by one show's back
        # catalogue (five SpaceX episodes on Nov 1), which reads as a list
        # of one show, not the network's week.
        if not slug or not ep or slug in EXCLUDED_SLUGS or slug in seen:
            continue
        seen.add(slug)
        out.append({
            "slug": slug,
            "show_name": row.get("show_name") or slug,
            "episode_num": int(ep),
            "title": record_hook(slug, int(ep), root) or lt.strip_episode_label(title),
            "url": row.get("blog_url") or "",
            "downloads_7d": row.get("downloads_7d"),
        })
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# Rendering (every block is ONE line of HTML: the branding wrapper passes a
# line starting with "<" through untouched, and Buttondown keeps a block with
# no blank lines as one raw-HTML block)
# ---------------------------------------------------------------------------

def _heading(text: str) -> str:
    """A section label as the front page sets it: a rule, then small caps."""
    return (f'<h2 style="margin:30px 0 16px;padding:10px 0 0;border-top:3px solid {_ACCENT};'
            'font-size:13px;line-height:1.3;font-weight:800;letter-spacing:.1em;'
            f'text-transform:uppercase;color:#0f172a">{_esc(text)}</h2>')


def _note(inner_html: str) -> str:
    return ('<p style="margin:0 0 14px;font-size:15px;line-height:1.6;'
            f'color:#334155;">{inner_html}</p>')


def _a(href: str, text: str, *, bold: bool = False) -> str:
    weight = "font-weight:600;" if bold else ""
    return f'<a href="{_esc(href)}" style="{_LINK}{weight}">{_esc(text)}</a>'


def _release_note(at: str, now: dt.datetime) -> str:
    from engine.release_schedule import describe_public_at
    when = describe_public_at(at or "", now=now)
    return f" (from {when})" if when else ""


_MUTED_LABEL = ('font-size:12px;font-weight:700;letter-spacing:0.06em;'
                'text-transform:uppercase;color:#475569;')


def _kicker(show: "EmailShow", story: Dict[str, Any], meta: Sequence[str] = ()) -> str:
    """``WORLD NEWS / OMNI VIEW · EP 47 · 9 MIN`` — the front page's kicker."""
    hub = str(story.get("hub_heading") or "").strip()
    bits = ""
    if hub:
        bits += f'<span class="text-muted" style="color:#64748b">{_esc(hub)} &nbsp;/&nbsp; </span>'
    bits += f'<span style="color:{show.brand_text};">{_esc(show.name)}</span>'
    if meta:
        bits += (f'<span class="text-muted" style="color:#64748b;font-weight:600"> · '
                 f'{_esc(" · ".join(meta))}</span>')
    return f'<div style="{_KICKER}">{bits}</div>'


def _image_alt(show: "EmailShow", ep: int) -> str:
    return f"AI-generated scene illustrating {show.name} episode {ep}"


_TRACKING_PARAM_RE = re.compile(r"(?:utm_[a-z]+|traffic_source|ref|cmpid|mc_[a-z]+)=")


def _clean_url(url: str) -> str:
    """A publisher's link without its feed's tracking parameters
    (``?utm_source=rss``, ``traffic_source=rss``): shorter, and the reader
    lands on the article, not a campaign."""
    from urllib.parse import urlsplit, urlunsplit
    parts = urlsplit(url or "")
    if not parts.query:
        return url
    kept = [q for q in parts.query.split("&") if q and not _TRACKING_PARAM_RE.match(q)]
    return urlunsplit(parts._replace(query="&".join(kept)))


def _sources_line(story: Dict[str, Any]) -> str:
    """``Sources: aljazeera.com · thearabweekly.com`` — the hook story's own
    links, named by their address (``engine.landing_test.story_links``)."""
    srcs = [x for x in (story.get("sources") or []) if x.get("url") and x.get("outlet")]
    if not srcs:
        return ""
    links = " · ".join(
        f'<a href="{_esc(_clean_url(x["url"]))}" style="color:#475569">'
        f'{_esc(x["outlet"])}</a>' for x in srcs)
    return ('<p class="text-muted" style="margin:0 0 10px;font-size:13px;line-height:1.5;'
            f'color:#64748b">Sources: {links}</p>')


def _reads_html(story: Dict[str, Any], limit: int = READS_PER_CARD) -> str:
    """"More in this episode": each headline linked to the article it was
    reported from, the outlet beside it; plain headlines when the record
    carries no links (a front built before Nov 8 2026)."""
    reads = [r for r in (story.get("reads") or []) if r.get("url") and r.get("title")][:max(0, limit)]
    if limit <= 0:
        return ""
    label = ('<div class="text-muted" style="font-size:11px;font-weight:700;letter-spacing:.08em;'
             'text-transform:uppercase;color:#64748b;margin:2px 0 6px">More in this episode</div>')
    li = f'<li style="margin:0 0 6px"><b style="color:{_ACCENT}">&#9632;</b>&nbsp; '
    if reads:
        rows = "".join(
            li + f'<a href="{_esc(_clean_url(r["url"]))}" style="color:#0f172a;text-decoration:none">'
            f'{_esc(r["title"])}</a> <i class="text-muted" style="color:#64748b">'
            f'{_esc(r.get("outlet") or "")}</i></li>' for r in reads)
    else:
        heads = [h for h in (story.get("headlines") or []) if str(h).strip()][:min(limit, HEADLINES_PER_CARD)]
        if not heads:
            return ""
        rows = "".join(li + f'{_esc(h)}</li>' for h in heads)
    return (label + '<ul style="list-style:none;margin:0 0 12px;padding:0;line-height:1.45;'
            'color:#334155">' + rows + "</ul>")


def _pill(href: str, text: str) -> str:
    return (f'<a href="{_esc(href)}" class="pill" style="display:inline-block;background:{_NAVY};color:#fff;'
            'padding:7px 14px;border-radius:99px;font-weight:700;text-decoration:none">'
            f'{_esc(text)}</a>')


def _actions_html(pick: "Pick", *, now: dt.datetime, videos: Dict[int, dict]) -> str:
    from engine.funnel import newsletter_link

    show, story = pick.show, pick.story
    ep = int(story.get("episode_num") or 0)
    post = _absolute(story.get("post_url") or "")
    if not post:
        return ""
    listen = newsletter_link(f"{post}#listen", show.slug, ep)
    # No "Read" link: the headline and the picture both open the episode's
    # page, as on the front page, and a card has ~200 bytes to spare.
    links = []
    vids = videos.get(ep) or {}
    if vids.get("long"):
        links.append(_a(vids["long"], "Watch") + _esc(_release_note(vids.get("long_at", ""), now)))
    if vids.get("short"):
        links.append(_a(vids["short"], "Short")
                     + _esc(_release_note(vids.get("short_at", ""), now)))
    return ('<div style="font-size:14px;line-height:2.2;color:#334155">'
            + _pill(listen, "▶ Listen") + (" &nbsp; " if links else "")
            + " &nbsp;·&nbsp; ".join(links) + "</div>")


def _meta(story: Dict[str, Any], day: dt.date) -> List[str]:
    # The episode number stays in the picture's alt text and the link; on a
    # phone "EP 155" pushed the kicker onto a second line.
    meta: List[str] = []
    when = _parse_day(story.get("date_raw"))
    if when and when != day:
        meta.append(_short_day(when))
    dur = _duration_words(story.get("duration_s"))
    if dur:
        meta.append(dur)
    return meta


def _hook_text(story: Dict[str, Any]) -> str:
    hook = _esc(story.get("hook") or "")
    if story.get("guest") and story.get("guest") not in (story.get("hook") or ""):
        hook = f"{_esc(story['guest'])}: {hook}"
    return hook


def card_html(pick: Pick, *, edition_ep: int, now: dt.datetime,
              videos: Dict[int, dict], day: dt.date, reads: int = READS_PER_CARD) -> str:
    """One show's story, set like the front page (Nov 8 2026): the kicker,
    a serif headline with the episode's picture beside it, the deck (the
    digest's own sentences), the hook story's sources, up to three more of
    the episode's stories linked to the articles they came from, and where
    to hear it. Stories are separated by a rule, not boxed. The title keeps
    ``card-title`` so dark mode keeps it a headline."""
    from engine.funnel import newsletter_link

    show, story = pick.show, pick.story
    ep = int(story.get("episode_num") or 0)
    post = _absolute(story.get("post_url") or "")
    read = newsletter_link(post, show.slug, ep) if post else ""
    title = (f'<h3 class="card-title" style="margin:0;{_SERIF}font-size:20px;line-height:1.3;'
             f'font-weight:700;color:#0f172a;"><a href="{_esc(read or post)}" '
             f'style="color:#0f172a;text-decoration:none;">{_hook_text(story)}</a></h3>')
    head = _kicker(show, story, _meta(story, day)) + title
    image = str(story.get("image_url") or "").strip()
    if image.startswith("https://"):
        # Not a link: the headline beside it is, and the ~200 bytes of a
        # second tracked URL per card are what kept a Sunday copy clipped.
        thumb = (f'<img src="{_esc(image)}" width="{THUMB_PX}" '
                 f'alt="{_esc(_image_alt(show, ep))}" style="display:block;width:{THUMB_PX}px;'
                 f'max-width:{THUMB_PX}px;height:auto;border-radius:8px;border:0">')
        head = ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
                f'<tr><td valign="top" style="padding:0 14px 0 0">{head}</td>'
                f'<td valign="top" width="{THUMB_PX}" style="width:{THUMB_PX}px">'
                f'{thumb}</td></tr></table>')
    deck = str(story.get("deck") or "").strip()
    deck_html = ('<p class="deck" style="margin:10px 0 8px;font-size:16px;line-height:1.6;'
                 f'color:#1f2937">{_esc(deck)}</p>') if deck else '<div style="height:10px;"></div>'
    return ('<div class="story" style="border-top:1px solid #e2e8f0;padding:18px 0 6px">'
            f"{head}{deck_html}{_sources_line(story)}{_reads_html(story, reads)}"
            f"{_actions_html(pick, now=now, videos=videos)}</div>")


def lead_html(pick: Pick, *, now: dt.datetime, videos: Dict[int, dict], day: dt.date) -> str:
    """The day's top story, for every reader: the episode's picture across
    the column, the kicker, a large serif headline, the deck, its sources
    and the rest of the episode's reporting — the front page's lead."""
    from engine.funnel import newsletter_link

    show, story = pick.show, pick.story
    ep = int(story.get("episode_num") or 0)
    post = _absolute(story.get("post_url") or "")
    read = newsletter_link(post, show.slug, ep) if post else post
    image = str(story.get("image_url") or "").strip()
    picture = ""
    if image.startswith("https://"):
        picture = (f'<a href="{_esc(read)}"><img src="{_esc(image)}" width="{LEAD_IMAGE_PX}" '
                   f'alt="{_esc(_image_alt(show, ep))}" style="display:block;width:100%;'
                   f'max-width:{LEAD_IMAGE_PX}px;height:auto;border:0;border-radius:10px;'
                   f'border-bottom:4px solid {show.brand};margin:0 0 14px;"></a>')
    title = (f'<h2 class="card-title" style="margin:0 0 10px;padding:0;border:0;{_SERIF}font-size:27px;'
             f'line-height:1.22;font-weight:700;letter-spacing:-0.01em;color:#0f172a;text-transform:none;">'
             f'<a href="{_esc(read)}" style="color:#0f172a;text-decoration:none;">{_hook_text(story)}</a></h2>')
    deck = str(story.get("deck") or "").strip()
    deck_html = ('<p class="deck" style="margin:0 0 8px;font-size:17px;line-height:1.6;'
                 f'color:#1f2937">{_esc(deck)}</p>') if deck else ""
    return ('<div class="lead" style="padding:4px 0 8px;">'
            + picture + _kicker(show, story, _meta(story, day)) + title + deck_html
            + _sources_line(story) + _reads_html(story, LEAD_READS)
            + _actions_html(pick, now=now, videos=videos) + "</div>")


def choose_lead(picks: Sequence[Pick], day: dt.date) -> Optional[Pick]:
    """The show that leads the email: :data:`LEAD_POOL` in rotation by date,
    among today's picks that carry a picture and a deck. Deterministic."""
    by_slug = {p.show.slug: p for p in picks}
    pool = [by_slug[s] for s in LEAD_POOL
            if s in by_slug and str(by_slug[s].story.get("image_url") or "").startswith("https://")
            and str(by_slug[s].story.get("deck") or "").strip()]
    if not pool:
        return None
    return pool[day.toordinal() % len(pool)]


def masthead_html(day: dt.date, *, shows_today: int, listen_url: str = "",
                  duration: str = "") -> str:
    """The landing page's masthead in an email: the date line, "Nerra
    Daily" in serif with the network tagline under it, and the whole
    morning in one listen. Navy in light and dark mode alike."""
    from engine.brand import NETWORK_TAGLINE

    date_line = day.strftime("%A, %B ") + str(day.day) + day.strftime(", %Y")
    count = (f"{shows_today} shows published this morning" if shows_today > 1
             else "Stories from across the network")
    listen = ""
    if listen_url:
        label = "▶ Hear all of it" + (f" · {duration}" if duration else "")
        listen = (f'<div style="margin:16px 0 0;"><a href="{_esc(listen_url)}" style="display:inline-block;'
                  f'background:{_ACCENT};color:#ffffff;padding:9px 16px;border-radius:999px;font-weight:700;'
                  f'font-size:14px;text-decoration:none;{_BODY_FONT}">{_esc(label)}</a></div>')
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'bgcolor="{_NAVY}" style="background:{_NAVY};background-color:{_NAVY};">'
            f'<tr><td style="padding:20px 24px 22px;{_BODY_FONT}">'
            f'<div style="font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;'
            f'color:#e2e8f0;">{_esc(date_line)}</div>'
            f'<div style="font-size:13px;color:#94a3b8;margin:4px 0 14px;padding:0 0 12px;'
            f'border-bottom:1px solid #1e293b;">{_esc(count)}</div>'
            f'<div style="{_SERIF}font-size:36px;line-height:1.1;font-weight:700;color:#ffffff;'
            f'letter-spacing:-0.01em;">Nerra <span style="color:#60a5fa;">Daily</span></div>'
            f'<div style="{_SERIF}font-style:italic;font-size:17px;line-height:1.4;color:#e2e8f0;'
            f'margin:8px 0 0;"><span style="color:#60a5fa;font-style:normal;">&#8212;</span> '
            f'{_esc(NETWORK_TAGLINE)}</div>'
            f'{listen}</td></tr></table>')


def also_headline(story: Dict[str, Any]) -> str:
    """The short headline of an "Also on Nerra today" line, never cut when a
    whole line is available (Nov 6 2026: eleven of eleven lines on the Nov 6
    copy ended in an ellipsis, because the median hook is 102 characters).
    In order: the hook whole when it fits
    :data:`engine.titles.EMAIL_ALSO_LINE_MAX`; the digest's own headline for
    the hook's story (:func:`engine.newsroom.headline_within_hook`) when it
    fits whole; the hook's first clause whole
    (:func:`engine.titles.fit_first_clause`); and only then a clip, which
    gives way to the digest's first headline when it reads as a fragment.
    The full hook is one click away."""
    from engine.newsroom import headline_within_hook
    from engine.titles import EMAIL_ALSO_LINE_MAX, clip_words, fit_first_clause, is_fragment_title

    hook = str(story.get("hook") or "").strip()
    if len(hook) <= EMAIL_ALSO_LINE_MAX:
        return hook
    heads = [str(h).strip() for h in (story.get("headlines") or []) if str(h).strip()]
    for head in heads:
        if len(head) <= EMAIL_ALSO_LINE_MAX and headline_within_hook(head, hook):
            return head
    line = fit_first_clause(hook, EMAIL_ALSO_LINE_MAX)
    if line != hook and is_fragment_title(line):
        if heads:
            line = clip_words(heads[0], EMAIL_ALSO_LINE_MAX)
    return line


def also_line(pick: Pick, *, edition_ep: int) -> str:
    """One line as the front page's "Latest across the network" sets it: the
    show as a coloured kicker, the short headline in serif under it."""
    from engine.funnel import newsletter_link

    show, story = pick.show, pick.story
    ep = int(story.get("episode_num") or 0)
    post = _absolute(story.get("post_url") or "")
    href = newsletter_link(post, show.slug, ep) if post else _absolute(show.show_page)
    return ('<p style="margin:0 0 14px;padding:0 0 12px;border-bottom:1px solid #eef2f6;line-height:1.35;">'
            f'<span style="{_KICKER}color:{show.brand_text};">{_esc(show.name)}</span><br>'
            f'<a href="{_esc(href)}" style="{_SERIF}color:#0f172a;text-decoration:none;font-weight:700;'
            f'font-size:17px;">{_esc(also_headline(story))}</a></p>')


def also_groups(picks: Sequence[Pick]) -> List[Tuple[str, List[Pick]]]:
    """The "Also on Nerra today" lines grouped by subject, in
    ``engine.landing_test.SECTION_ORDER``: ``[(heading, picks), …]``.

    A subject label is worth printing over two or more lines; the
    singletons (and a show with no hub) gather under one "Elsewhere on
    Nerra" label at the end — the Nov 2 distribution would have been twelve
    labels for seventeen lines otherwise. With no subject group at all the
    lines run unlabelled (heading ``""``).
    """
    from engine import landing_test as lt
    from engine import topic_hubs

    order: Dict[str, int] = {}
    for index, hub_id in enumerate(lt.SECTION_ORDER):
        hub = topic_hubs.hub_by_id(hub_id)
        if hub and hub.get("heading"):
            order.setdefault(hub["heading"], index)
    by_heading: Dict[str, List[Pick]] = {}
    for pick in picks:
        heading = str(pick.story.get("hub_heading") or "").strip()
        by_heading.setdefault(heading if heading in order else "", []).append(pick)
    groups: List[Tuple[str, List[Pick]]] = []
    rest: List[Pick] = []
    for heading in sorted((h for h in by_heading if h), key=order.__getitem__):
        members = by_heading[heading]
        if len(members) >= 2:
            groups.append((heading, members))
        else:
            rest.extend(members)
    rest.extend(by_heading.get("", []))
    rest.sort(key=picks.index)
    if rest:
        groups.append(("Elsewhere on Nerra" if groups else "", rest))
    return groups


def also_label(heading: str, members: Sequence[Pick], *, default_slugs: Sequence[str],
               published_tags: Sequence[str]) -> str:
    """A subject label, rendered only when a line will follow it.

    A reader who follows at least one of today's shows (or the archive)
    sees a line for every show of the group they do not follow; a reader
    who follows none of them has the default cards instead, so only the
    group's non-default shows give them a line.
    """
    label = (f'<p class="text-muted" style="margin:14px 0 6px;{_MUTED_LABEL}">'
             f'{_esc(heading)}</p>')
    inner = "<div>" + any_not_in([p.show.tag for p in members]) + label + ENDIF + "</div>"
    if any(p.show.slug not in default_slugs for p in members):
        return "<div>" + any_of(published_tags) + inner + "{% else %}" + label + ENDIF + "</div>"
    return "<div>" + any_of(published_tags) + inner + ENDIF + "</div>"


def week_list_html(show: EmailShow, rows: List[Dict[str, Any]]) -> str:
    """One followed show's week, as a light list (no card: a reader who
    follows every show must stay under Gmail's 102 KB clipping point)."""
    from engine.funnel import PLACEMENT_WEEK, newsletter_link

    items = []
    for row in rows:
        url = _absolute(f"blog/{show.slug}/ep{row['episode_num']:03d}.html")
        href = newsletter_link(url, show.slug, row["episode_num"], placement=PLACEMENT_WEEK)
        items.append(f'<li>{_esc(_short_day(row["date"]))} · '
                     f'<a href="{_esc(href)}" style="{_LINK}">{_esc(row["hook"])}</a></li>')
    return (f'<p style="margin:16px 0 6px;font-size:13px;font-weight:700;letter-spacing:.05em;'
            f'text-transform:uppercase;color:{show.brand_text}">{_esc(show.name)}</p>'
            '<ul style="margin:0 0 8px;padding-left:18px;font-size:15px;line-height:1.55;color:#334155">'
            + "".join(items) + "</ul>")


def personal_block(*, edition_ep: int, trial_days: int) -> str:
    """Members see their own edition; everyone else, one honest line."""
    from engine.funnel import newsletter_link

    join = newsletter_link(f"{SITE}/join.html#plans", EMAIL_SLUG, edition_ep, variant="personal")
    account = newsletter_link(f"{SITE}/account.html", EMAIL_SLUG, edition_ep, variant="account")
    trial = (f" Try it free for {trial_days} days." if trial_days > 0 else "")
    card = ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'border="0" class="card" style="background:#f8fafc;border-radius:10px;'
            'margin:18px 0 14px;"><tr><td class="card" style="padding:16px 18px;'
            'border:1px solid #eef0f3;border-left:4px solid #6B47FF;'
            f'border-radius:10px;{_BODY_FONT}font-size:15px;line-height:1.6;color:#1f2937;">'
            "{content}</td></tr></table>")
    member = card.replace("{content}", (
        '<strong style="color:#0f172a;">Your Personal edition is ready.</strong> '
        "It is in your podcast app, your shows in your order. "
        + _a(account, "Open My Nerra")))
    upsell = card.replace("{content}", (
        '<strong style="color:#0f172a;">Hear this as your own daily episode.</strong> '
        "Nerra Personal turns your shows into one private audio edition in your "
        "podcast app, in your order, introduced by Mira, our AI host, by name."
        + _esc(trial) + " " + _a(join, "See Personal", bold=True)))
    return ("<div>" + tag_in(PAID_TAG) + member + "{% else %}" + upsell + ENDIF + "</div>")


@dataclass
class Composed:
    """A rendered email, ready for Buttondown."""

    subject: str
    body: str
    preheader: str
    included: Dict[str, List[int]]
    sections: List[str]
    edition_ep: int
    sunday: bool
    archive_slug: str
    archive_url: str = ""


def largest_copy_bytes(composed: "Composed", front: dict, root: Path = ROOT) -> int:
    """The size of the biggest copy a subscriber can receive: the reader
    who follows every show and is a member."""
    tags = [s.tag for s in eligible_shows(front, root)] + [PAID_TAG]
    return len(render_for(composed.body, tags).encode())


def compose(day: dt.date, *, root: Path = ROOT, now: Optional[dt.datetime] = None,
            front: Optional[dict] = None, trial_days: int = 0,
            allow_no_edition: bool = False) -> Optional[Composed]:
    """Build the day's Nerra Daily email, or ``None`` when there is nothing to send.

    The cards' "More in this episode" links are the one part that gives way
    to Gmail's clipping point (Nov 8 2026): the email is composed with
    :data:`READS_PER_CARD` of them, and with fewer when the largest copy
    would pass :func:`size_warning_bytes` (a Sunday, a reader who follows
    every show). The lead keeps its links, and every card keeps its
    headline, deck, sources and buttons. A copy still over the budget at
    zero is returned as it is; the send script warns.
    """
    front = front if front is not None else load_front(root)
    budget = size_warning_bytes()
    composed = None
    for reads in range(READS_PER_CARD, -1, -1):
        composed = _compose(day, root=root, now=now, front=front, trial_days=trial_days,
                            allow_no_edition=allow_no_edition, card_reads=reads)
        if composed is None or largest_copy_bytes(composed, front, root) <= budget:
            return composed
    return composed


def _compose(day: dt.date, *, root: Path = ROOT, now: Optional[dt.datetime] = None,
             front: Optional[dict] = None, trial_days: int = 0,
             allow_no_edition: bool = False, card_reads: int = READS_PER_CARD) -> Optional[Composed]:
    from engine.funnel import PLACEMENT_WEEK, newsletter_link
    from engine.newsletter_template import wrap_with_branding
    from engine.titles import NEWSLETTER_SUBJECT_MAX, clip_words

    now = now or dt.datetime.now(dt.timezone.utc)
    # Release notes ("Watch (from 7:00 AM ET)") are judged at the SEND, not
    # at the compose clock: the Nov 2 copy was composed at 6:43 ET for a
    # 7:00 ET send and every "(from 7:00 AM ET)" note was false on arrival.
    try:
        from engine.release_schedule import newsletter_send_time
        send_at = newsletter_send_time(EMAIL_SLUG, now) or now
    except Exception:  # noqa: BLE001 — the compose clock is the fallback
        send_at = now
    front = front if front is not None else load_front(root)
    shows = eligible_shows(front, root)
    sent = already_sent(day, root)
    picks = pick_stories(shows, day, sent)

    edition = None
    for story in ((front.get("shows") or {}).get(EMAIL_SLUG) or {}).get("stories") or []:
        if _parse_day(story.get("date_raw")) == day:
            edition = story
            break
    if edition is None and not allow_no_edition:
        logger.info("Nerra Daily email: no edition for %s yet", day)
        return None
    if not picks and edition is None:
        logger.info("Nerra Daily email: nothing published for %s", day)
        return None

    edition_ep = int((edition or {}).get("episode_num") or 0)
    sunday = day.weekday() == 6
    all_picks = list(picks)
    # Nov 8 2026: one story leads for every reader, with its picture; its
    # show is then left out of the cards and the one-liners below.
    lead = choose_lead(all_picks, day)
    picks = [p for p in all_picks if p is not lead]
    published_tags = [p.show.tag for p in picks]
    by_slug = {p.show.slug: p for p in picks}
    default_slugs = [s for s in DEFAULT_SHOWS if s in by_slug]
    # A reader who follows none of today's shows gets the default set, in
    # full. If none of those published either, the first three picks stand in.
    if not default_slugs:
        default_slugs = [p.show.slug for p in picks[:3]]

    lines: List[str] = []
    # No paragraph about the layout: the masthead says what follows, and the
    # first thing a reader sees under it is the lead story.
    videos_by_slug = {p.show.slug: video_links(p.show.slug, root, now) for p in all_picks}
    if lead is not None:
        lines.append(lead_html(lead, now=send_at, videos=videos_by_slug.get(lead.show.slug, {}), day=day))

    # --- Your shows --------------------------------------------------------
    lines.append("<div>" + followed_any_of(published_tags) + _heading("Your shows today") + ENDIF + "</div>")
    cards = {p.show.slug: card_html(p, edition_ep=edition_ep, now=send_at,
                                    videos=videos_by_slug.get(p.show.slug, {}), day=day,
                                    reads=card_reads)
             for p in picks}
    for pick in picks:
        lines.append("<div>" + tag_in(pick.show.tag) + cards[pick.show.slug] + ENDIF + "</div>")

    # --- Readers who follow none of today's shows ----------------------------
    choose = newsletter_link(f"{SITE}/account.html#customize", EMAIL_SLUG, edition_ep, variant="choose")
    default_html = (_heading("Today on Nerra")
                    + _note("Here are a few of today's stories from across Nerra. "
                            + _a(choose, "Choose your shows", bold=True)
                            + " and this email carries the ones you pick. It takes a minute.")
                    + "".join(cards[s] for s in default_slugs))
    lines.append("<div>" + none_of(published_tags) + default_html + ENDIF + "</div>")

    # --- Also on Nerra today ----------------------------------------------
    also: Dict[str, str] = {}
    for pick in picks:
        line = also_line(pick, edition_ep=edition_ep)
        if pick.show.slug in default_slugs:
            # A default reader already has this show's card; everyone else who
            # does not follow it gets the line.
            also[pick.show.slug] = ("<div>" + tag_not_in(pick.show.tag) + any_of(published_tags)
                                    + line + ENDIF + ENDIF + "</div>")
        else:
            also[pick.show.slug] = "<div>" + tag_not_in(pick.show.tag) + line + ENDIF + "</div>"
    if also:
        # The heading only when at least one published show is not followed
        # (a reader following everything got the heading over nothing).
        # Wrapped in <div> like every conditional block: a line opening on
        # ``{%`` is markdown to the body renderer, and the Nov 1 and Nov 2
        # sends carried this heading as escaped ``&lt;h2 …&gt;`` text.
        lines.append("<div>" + any_not_in(published_tags) + _heading("Also on Nerra today") + ENDIF + "</div>")
        # Short headlines in subject groups (Nov 3 2026); every line keeps
        # its own condition.
        for heading, members in also_groups(picks):
            if heading:
                lines.append(also_label(heading, members, default_slugs=default_slugs,
                                        published_tags=published_tags))
            lines.extend(also[p.show.slug] for p in members)

    # --- Sunday: the week ----------------------------------------------------
    if sunday:
        top = most_played(root)
        if top:
            items = []
            for row in top:
                url = _absolute(row["url"]) or _absolute(f"blog/{row['slug']}/ep{row['episode_num']:03d}.html")
                href = newsletter_link(url, row["slug"], row["episode_num"], placement=PLACEMENT_WEEK)
                items.append(f'<li style="margin:0 0 6px;"><strong>{_esc(row["show_name"])}</strong> · '
                             f'<a href="{_esc(href)}" style="{_LINK}">{_esc(row["title"])}</a></li>')
            lines.append(_heading("Most played this week"))
            lines.append('<ol style="margin:0 0 16px;padding-left:22px;font-size:15px;'
                         'line-height:1.55;color:#1f2937;">' + "".join(items) + "</ol>")
        week_blocks = []
        today_slugs = {p.show.slug for p in all_picks}
        for show in shows:
            rows = week_records(show.slug, day, root)
            if len(rows) < 2:
                continue
            # Today's episode is already a card or a line above (Nov 8 2026).
            rows = [r for r in rows if r["date"] != day or show.slug not in today_slugs]
            if not rows:
                continue
            week_blocks.append("<div>" + tag_in(show.tag)
                               + week_list_html(show, rows)
                               + ENDIF + "</div>")
        if week_blocks:
            all_tags = [s.tag for s in shows]
            lines.append("<div>" + any_of(all_tags) + _heading("Your week") + ENDIF + "</div>")
            lines.extend(week_blocks)

    # --- Personal + managing the email ---------------------------------------
    lines.append(personal_block(edition_ep=edition_ep, trial_days=trial_days))
    manage = newsletter_link(f"{SITE}/account.html#email", EMAIL_SLUG, edition_ep, variant="manage")
    lines.append(_note("Choose your shows, or switch to the Sunday edition only, on "
                       + _a(manage, "My Nerra") + ". Every story is sourced, and you can "
                       "read the article or hear the episode it came from."))

    body = "\n".join(lines)

    lead_hook = (edition or {}).get("hook") or (all_picks[0].story.get("hook") if all_picks else "")
    lead_hook = str(lead_hook or _when(day)).strip().rstrip(" .")
    # The edition's title carries "<Weekday> edition — " for the podcast app
    # (engine.daily_edition.edition_hook); in an inbox showing ~40
    # characters that prefix was the whole subject (Nov 2: "Monday edition —
    # TSMC revival talks, Nor…"). The email's subject is the story.
    lead_hook = re.sub(r"^(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day edition\s*[—–-]\s*", "", lead_hook).strip()
    suffix = f" · {EMAIL_NAME}"
    # The name rides on the subject when the whole headline still fits;
    # otherwise the headline wins (the From line and the hero say Nerra
    # Daily) and is shortened through engine.titles, never sliced.
    if len(lead_hook) + len(suffix) <= NEWSLETTER_SUBJECT_MAX:
        subject = lead_hook + suffix
    else:
        subject = clip_words(lead_hook, NEWSLETTER_SUBJECT_MAX)
    # The preheader is a second and third story, not a list of show names
    # (Nov 3 2026); the show list stays when the day has fewer than two.
    more_hooks = [clip_words(str(p.story.get("hook") or "").strip().rstrip(" ."), 60)
                  for p in all_picks[:3]]
    more_hooks = [h for h in more_hooks if h and h.lower() != lead_hook.lower()][:2]
    if len(more_hooks) >= 2:
        preheader = "Also: " + " · ".join(more_hooks)
    else:
        others = [p.show.name for p in all_picks[:4]]
        preheader = (("Today: " + ", ".join(others)) if others else "Today on Nerra") + \
            (f", and {len(all_picks) - 4} more" if len(all_picks) > 4 else "")
    archive_slug = f"nerra-daily-{day.isoformat()}"

    featured = None
    if edition is not None:
        post = _absolute(edition.get("post_url") or "")
        featured = {
            "show_slug": EMAIL_SLUG,
            "episode_num": edition_ep,
            "hook": edition.get("hook") or "",
            "date": _when(day) + (f" · {_duration_words(edition.get('duration_s'))}"
                                  if edition.get("duration_s") else ""),
            "listen_url": newsletter_link(f"{post}#listen", EMAIL_SLUG, edition_ep) if post else "",
        }

    # The masthead (Nov 8 2026): the landing page's, with the whole morning
    # in one listen. It precedes every heading, so the archive copy (no
    # reader in the context) opens on it too.
    masthead = masthead_html(
        day, shows_today=len(all_picks),
        listen_url=(featured or {}).get("listen_url") or "",
        duration=_duration_words((edition or {}).get("duration_s")) if edition else "")

    from engine.newsletter import BUTTONDOWN_USERNAME
    archive_url = f"https://buttondown.com/{BUTTONDOWN_USERNAME}/archive/{archive_slug}/"
    wrapped = wrap_with_branding(
        EMAIL_SLUG,
        body,
        daily_label=day.strftime("%A"),
        daily_date=day,
        preheader=preheader,
        featured_episode=featured,
        adjacent_shows=None,
        show_reply_share=True,
        archive_url=archive_url,
        issue_number=edition_ep or None,
        # Nov 3 2026: the first screen is the news. The compact masthead
        # replaces the 350 px hero, the edition's card follows the reader's
        # own shows, and its eyebrow says what it is.
        hero="custom",
        masthead_html=masthead,
        featured_position="after_body",
        featured_eyebrow="🎧 Hear all of it",
    )
    # The shared footer (listen / blog / gallery / data / start here) is
    # built for every newsletter and carries no campaign; in this email every
    # site link is measured, so the rest are tagged as the footer's.
    import re as _re

    def _tag_footer(m):
        url = html.unescape(m.group(1))
        if "utm_source=" in url:
            return m.group(0)
        return 'href="' + _esc(newsletter_link(url, EMAIL_SLUG, edition_ep, variant="footer")) + '"'

    wrapped = _re.sub(r'href="(https://nerranetwork\.com/[^"]*)"', _tag_footer, wrapped)

    included = {p.show.slug: p.included for p in all_picks}
    if edition is not None:
        included[EMAIL_SLUG] = [edition_ep]
    return Composed(subject=subject, body=wrapped, preheader=preheader,
                    included=included, sections=[p.show.slug for p in all_picks],
                    edition_ep=edition_ep, sunday=sunday, archive_slug=archive_slug,
                    archive_url=archive_url)


# ---------------------------------------------------------------------------
# Rendering one subscriber's copy (tests, the preview, the size guard)
# ---------------------------------------------------------------------------

def render_for(body: str, tags: Iterable[str], *, subscriber: bool = True) -> str:
    """Render the Django ``{% if %}`` subset this module emits, for *tags*.

    Buttondown does this per subscriber. This is the same evaluation, for
    the operator's preview and for the tests, so a condition that is never
    true (a typo in a tag) is caught before it is sent. Supports exactly
    what :func:`tag_in` / :func:`any_of` / :func:`any_not_in` /
    :func:`none_of` produce, nested ``{% if %}`` and ``{% else %}``.
    ``subscriber=False`` renders the ARCHIVE copy (no reader in the context).
    """
    import re

    have = set(tags)
    token = re.compile(r"\{% (if (.*?)|else|endif) %\}")

    def truth(expr: str) -> bool:
        expr = expr.strip()
        if expr in ("True", "False"):
            return expr == "True"
        if expr == "subscriber":
            return subscriber
        if expr == "not subscriber":
            return not subscriber
        if " or " in expr:
            return any(truth(part) for part in expr.split(" or "))
        if " and " in expr:
            return all(truth(part) for part in expr.split(" and "))
        m = re.fullmatch(r"(['\"])(.*)\1 (not in|in) subscriber\.tags", expr)
        if not m:
            raise ValueError(f"unsupported template condition: {expr!r}")
        inside = m.group(2) in have
        return inside if m.group(3) == "in" else not inside

    out: List[str] = []
    stack: List[Tuple[bool, bool]] = []  # (parent_visible, this_branch_true)
    pos = 0
    visible = True
    for m in token.finditer(body):
        if visible:
            out.append(body[pos:m.start()])
        pos = m.end()
        word = m.group(1)
        if word.startswith("if "):
            cond = truth(m.group(2)) if visible else False
            stack.append((visible, cond))
            visible = visible and cond
        elif word == "else":
            parent, cond = stack[-1]
            visible = parent and not cond
        else:
            parent, _ = stack.pop()
            visible = parent
    if stack:
        raise ValueError("unbalanced {% if %} in the email body")
    if visible:
        out.append(body[pos:])
    return "".join(out)


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def audience_filter(tag_ids: Dict[str, str], *, en_tags: Sequence[str],
                    ru_tags: Sequence[str], sunday: bool) -> Optional[dict]:
    """The Buttondown filter tree for the day's send, or ``None`` = refuse.

    Who gets Nerra Daily: a free account (:data:`MEMBER_TAG`), a gallery
    signup (:data:`GALLERY_TAG`, whose form says "receive emails from Nerra
    Network") or anyone following an English show. Not: a reader whose only
    shows are Russian (they have their own Russian email) and, Monday to
    Saturday, a reader who chose the Sunday edition only. Tags Buttondown
    has never seen are left out of the tree (no subscriber carries them).
    """
    def ids(names: Iterable[str]) -> List[str]:
        return [tag_ids[n] for n in names if n in tag_ids]

    include = ids([MEMBER_TAG, GALLERY_TAG, *en_tags])
    if not include:
        return None
    en_ids = ids(en_tags)
    ru_ids = ids(ru_tags)
    groups = [{"filters": [{"field": "subscriber.tags", "operator": "contains", "value": t}
                           for t in include],
               "groups": [], "predicate": "or"}]
    if ru_ids:
        groups.append({
            "filters": [{"field": "subscriber.tags", "operator": "contains", "value": t}
                        for t in en_ids],
            "groups": [{"filters": [{"field": "subscriber.tags", "operator": "not_contains",
                                     "value": t} for t in ru_ids],
                        "groups": [], "predicate": "and"}],
            "predicate": "or",
        })
    filters = []
    weekly = tag_ids.get(WEEKLY_ONLY_TAG)
    if weekly and not sunday:
        filters.append({"field": "subscriber.tags", "operator": "not_contains", "value": weekly})
    return {"filters": filters, "groups": groups, "predicate": "and"}


def write_marker(day: dt.date, record: dict, root: Path = ROOT) -> Path:
    path = marker_path(day, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
