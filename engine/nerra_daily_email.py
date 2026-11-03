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
rows: full hook, headlines, post link) plus the shows' YouTube indexes.
Nothing here calls a model. Every link to the site is funnel-tagged through
:func:`engine.funnel.newsletter_link`.

Russian shows keep their own daily email (``newsletter.delivery: own``) and
are never sections here: a different audience in a different language.
"""

from __future__ import annotations

import datetime as dt
import html
import json
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
#: Headlines under each card's lead (the card's own hook excluded).
HEADLINES_PER_CARD = 3
#: An episode older than this is never news in today's email.
WINDOW_DAYS = 2
#: Episodes listed per followed show in the Sunday week list.
WEEK_LIST_MAX = 5
#: Most-played episodes in the Sunday block.
MOST_PLAYED_MAX = 5
#: Where a sent email's record lives (committed; the idempotency key).
MARKER_DIR = Path("digests") / "nerra_daily" / "email"

_BODY_FONT = ("font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
              "Roboto,Helvetica,Arial,sans-serif;")
_LINK = "color:#2563eb;text-decoration:underline;"


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


def tag_in(tag: str) -> str:
    """``{% if '<tag>' in subscriber.tags %}`` (never true for a bad tag)."""
    lit = _tag_literal(tag)
    return "{% if " + (f"{lit} in subscriber.tags" if lit else "False") + " %}"


def tag_not_in(tag: str) -> str:
    lit = _tag_literal(tag)
    return "{% if " + (f"{lit} not in subscriber.tags" if lit else "True") + " %}"


def any_of(tags: Iterable[str]) -> str:
    """``{% if 'a' in subscriber.tags or 'b' in subscriber.tags %}``."""
    lits = [lit for lit in (_tag_literal(t) for t in tags) if lit]
    if not lits:
        return "{% if False %}"
    return "{% if " + " or ".join(f"{lit} in subscriber.tags" for lit in lits) + " %}"


def none_of(tags: Iterable[str]) -> str:
    """``{% if 'a' not in subscriber.tags and 'b' not in subscriber.tags %}``.

    Django's ``{% if %}`` has no parentheses, so every condition in this
    module is a flat ``and`` / ``or`` chain or a nested ``{% if %}``.
    """
    lits = [lit for lit in (_tag_literal(t) for t in tags) if lit]
    if not lits:
        return "{% if True %}"
    return "{% if " + " and ".join(f"{lit} not in subscriber.tags" for lit in lits) + " %}"


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


def most_played(root: Path = ROOT, limit: int = MOST_PLAYED_MAX) -> List[Dict[str, Any]]:
    """The week's most-downloaded episodes (``site/data/popular_episodes.json``)."""
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
            "title": lt.strip_episode_label(title),
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
    return ('<h2 style="margin:28px 0 12px;padding:2px 0 2px 12px;'
            'border-left:4px solid #6B47FF;font-size:19px;line-height:1.3;'
            f'font-weight:700;color:#0f172a;">{_esc(text)}</h2>')


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


def card_html(pick: Pick, *, edition_ep: int, now: dt.datetime,
              videos: Dict[int, dict], day: dt.date) -> str:
    """One show's card: lead headline, a few more, and where to hear it."""
    from engine.funnel import newsletter_link

    show, story = pick.show, pick.story
    ep = int(story.get("episode_num") or 0)
    post = _absolute(story.get("post_url") or "")
    read = newsletter_link(post, show.slug, ep) if post else ""
    listen = newsletter_link(f"{post}#listen", show.slug, ep) if post else ""
    when = _parse_day(story.get("date_raw"))
    meta = [f"Ep {ep}"]
    if when and when != day:
        meta.append(_short_day(when))
    dur = _duration_words(story.get("duration_s"))
    if dur:
        meta.append(dur)
    eyebrow = (f'<div style="font-size:12px;font-weight:700;letter-spacing:0.06em;'
               f'text-transform:uppercase;color:{show.brand_text};margin:0 0 6px;">'
               f'{_esc(show.name)} · {_esc(" · ".join(meta))}</div>')
    hook = _esc(story.get("hook") or "")
    if story.get("guest") and story.get("guest") not in (story.get("hook") or ""):
        hook = f"{_esc(story['guest'])}: {hook}"
    title = (f'<div style="font-size:17px;font-weight:700;line-height:1.4;margin:0 0 8px;">'
             f'<a href="{_esc(read or post)}" style="color:#0f172a;text-decoration:none;">{hook}</a></div>')
    heads = [h for h in (story.get("headlines") or []) if str(h).strip()][:HEADLINES_PER_CARD]
    items = ""
    if heads:
        items = ('<ul style="margin:0 0 10px;padding-left:18px;font-size:15px;'
                 'line-height:1.55;color:#334155;">'
                 + "".join(f'<li>{_esc(h)}</li>' for h in heads)
                 + "</ul>")
    actions = []
    if listen:
        actions.append(_a(listen, "▶ Listen", bold=True))
    if read:
        actions.append(_a(read, "Read"))
    vids = videos.get(ep) or {}
    if vids.get("long"):
        actions.append(_a(vids["long"], "Watch") + _esc(_release_note(vids.get("long_at", ""), now)))
    if vids.get("short"):
        actions.append(_a(vids["short"], "30-second version")
                       + _esc(_release_note(vids.get("short_at", ""), now)))
    action_row = ('<div style="font-size:14px;line-height:1.6;color:#334155;">'
                  + " &nbsp;·&nbsp; ".join(actions) + "</div>") if actions else ""
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'border="0" class="card" style="background:#f8fafc;border-radius:10px;'
            'margin:0 0 14px;"><tr><td class="card" style="padding:14px 16px;'
            f'border:1px solid #eef0f3;border-left:4px solid {show.brand};'
            f'border-radius:10px;{_BODY_FONT}">'
            f"{eyebrow}{title}{items}{action_row}</td></tr></table>")


def also_line(pick: Pick, *, edition_ep: int) -> str:
    from engine.funnel import newsletter_link

    show, story = pick.show, pick.story
    ep = int(story.get("episode_num") or 0)
    post = _absolute(story.get("post_url") or "")
    href = newsletter_link(post, show.slug, ep) if post else _absolute(show.show_page)
    return ('<p style="margin:0 0 10px;font-size:15px;line-height:1.5;color:#1f2937;">'
            f'<strong style="color:{show.brand_text};">{_esc(show.name)}</strong> · '
            f'<a href="{_esc(href)}" style="{_LINK}">{_esc(story.get("hook") or "")}</a></p>')


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
    return (f'<p style="margin:16px 0 6px;font-size:13px;font-weight:700;letter-spacing:0.05em;'
            f'text-transform:uppercase;color:{show.brand_text};">{_esc(show.name)}</p>'
            '<ul style="margin:0 0 8px;padding-left:18px;font-size:15px;line-height:1.55;color:#334155;">'
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


def compose(day: dt.date, *, root: Path = ROOT, now: Optional[dt.datetime] = None,
            front: Optional[dict] = None, trial_days: int = 0,
            allow_no_edition: bool = False) -> Optional[Composed]:
    """Build the day's Nerra Daily email, or ``None`` when there is nothing to send."""
    from engine.funnel import PLACEMENT_WEEK, newsletter_link
    from engine.newsletter_template import wrap_with_branding
    from engine.titles import NEWSLETTER_SUBJECT_MAX, clip_words

    now = now or dt.datetime.now(dt.timezone.utc)
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
    published_tags = [p.show.tag for p in picks]
    by_slug = {p.show.slug: p for p in picks}
    default_slugs = [s for s in DEFAULT_SHOWS if s in by_slug]
    # A reader who follows none of today's shows gets the default set, in
    # full. If none of those published either, the first three picks stand in.
    if not default_slugs:
        default_slugs = [p.show.slug for p in picks[:3]]

    lines: List[str] = []
    edition_note = ""
    if edition is not None:
        dur = _duration_words(edition.get("duration_s"))
        edition_note = ("Today's edition carries every show of the morning in one "
                        "episode" + (f", {dur}" if dur else "")
                        + ", introduced by Mira, our AI host. ")
    lines.append(_note(_esc(edition_note) + "Below: your shows, one card each, then "
                       "one line on everything else Nerra published."))

    # --- Your shows --------------------------------------------------------
    lines.append("<div>" + any_of(published_tags) + _heading("Your shows today") + ENDIF + "</div>")
    videos_by_slug = {p.show.slug: video_links(p.show.slug, root, now) for p in picks}
    cards = {p.show.slug: card_html(p, edition_ep=edition_ep, now=now,
                                    videos=videos_by_slug.get(p.show.slug, {}), day=day)
             for p in picks}
    for pick in picks:
        lines.append("<div>" + tag_in(pick.show.tag) + cards[pick.show.slug] + ENDIF + "</div>")

    # --- Readers who follow none of today's shows ----------------------------
    choose = newsletter_link(f"{SITE}/account.html#customize", EMAIL_SLUG, edition_ep, variant="choose")
    default_html = (_heading("Today on Nerra")
                    + _note("This email carries the shows you follow. You don't follow any "
                            "that published today, so here are a few of ours. "
                            + _a(choose, "Choose your shows", bold=True)
                            + ": it takes a minute.")
                    + "".join(cards[s] for s in default_slugs))
    lines.append("<div>" + none_of(published_tags) + default_html + ENDIF + "</div>")

    # --- Also on Nerra today ----------------------------------------------
    also = []
    for pick in picks:
        line = also_line(pick, edition_ep=edition_ep)
        if pick.show.slug in default_slugs:
            # A default reader already has this show's card; everyone else who
            # does not follow it gets the line.
            also.append("<div>" + tag_not_in(pick.show.tag) + any_of(published_tags)
                        + line + ENDIF + ENDIF + "</div>")
        else:
            also.append("<div>" + tag_not_in(pick.show.tag) + line + ENDIF + "</div>")
    if also:
        lines.append(_heading("Also on Nerra today"))
        lines.extend(also)

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
        for show in shows:
            rows = week_records(show.slug, day, root)
            if len(rows) < 2:
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

    lead_hook = (edition or {}).get("hook") or (picks[0].story.get("hook") if picks else "")
    lead_hook = str(lead_hook or _when(day)).strip().rstrip(" .")
    suffix = f" · {EMAIL_NAME}"
    # The name rides on the subject when the whole headline still fits;
    # otherwise the headline wins (the From line and the hero say Nerra
    # Daily) and is shortened through engine.titles, never sliced.
    if len(lead_hook) + len(suffix) <= NEWSLETTER_SUBJECT_MAX:
        subject = lead_hook + suffix
    else:
        subject = clip_words(lead_hook, NEWSLETTER_SUBJECT_MAX)
    others = [p.show.name for p in picks[:4]]
    preheader = (("Today: " + ", ".join(others)) if others else "Today on Nerra") + \
        (f", and {len(picks) - 4} more" if len(picks) > 4 else "")
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

    from engine.newsletter import BUTTONDOWN_USERNAME
    wrapped = wrap_with_branding(
        EMAIL_SLUG,
        body,
        daily_label="Sunday" if sunday else "Today",
        daily_date=day,
        preheader=preheader,
        featured_episode=featured,
        adjacent_shows=None,
        show_reply_share=True,
        archive_url=f"https://buttondown.com/{BUTTONDOWN_USERNAME}/archive/{archive_slug}/",
        issue_number=edition_ep or None,
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

    included = {p.show.slug: p.included for p in picks}
    if edition is not None:
        included[EMAIL_SLUG] = [edition_ep]
    return Composed(subject=subject, body=wrapped, preheader=preheader,
                    included=included, sections=[p.show.slug for p in picks],
                    edition_ep=edition_ep, sunday=sunday, archive_slug=archive_slug)


# ---------------------------------------------------------------------------
# Rendering one subscriber's copy (tests, the preview, the size guard)
# ---------------------------------------------------------------------------

def render_for(body: str, tags: Iterable[str]) -> str:
    """Render the Django ``{% if %}`` subset this module emits, for *tags*.

    Buttondown does this per subscriber. This is the same evaluation, for
    the operator's preview and for the tests, so a condition that is never
    true (a typo in a tag) is caught before it is sent. Supports exactly
    what :func:`tag_in` / :func:`any_of` / :func:`none_of` produce, nested
    ``{% if %}`` and ``{% else %}``.
    """
    import re

    have = set(tags)
    token = re.compile(r"\{% (if (.*?)|else|endif) %\}")

    def truth(expr: str) -> bool:
        expr = expr.strip()
        if expr in ("True", "False"):
            return expr == "True"
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
