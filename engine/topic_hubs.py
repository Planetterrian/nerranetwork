"""Evergreen topic hubs — one module owns the topic vocabulary.

Why these pages exist. The site has ~1,880 blog posts and every one of them
is a DATED news article: "Tesla's software update fixed the Cybertruck door
rattle" is a fine headline for the day it shipped and a hopeless landing page
three weeks later. Nothing on the site answers the durable question a stranger
actually types — "AI podcast", "space podcast", "Canadian investing podcast" —
so the network earned 20 organic sessions in 28 days against 1,952 sitemap
URLs. A dozen evergreen pages can rank for those; 1,880 dated posts cannot.

Design rules, each of them a scar from somewhere else in this repo:

* **The vocabulary is CURATED, not mined.** The committed search index carries
  auto-mined ``topics`` per episode, and they are useless as hubs: "regulation"
  is on 1,708 of 1,886 episodes (91%) and "finance" on 1,263. A hub named for a
  word that matches nine episodes in ten is not a subject, it is a side effect
  of keyword matching. So a hub names the ``picker_tags.topics`` it absorbs —
  the editorial vocabulary the show registry already declares — and the shows
  follow from that intersection.
* **The intro is written, not generated.** A hub whose prose is assembled from
  its own episode titles is thin content, which is worse for search than no
  page at all. Every hub below carries hand-written copy about the subject, and
  a hub with no intro is not rendered.
* **Episodes come from the COMMITTED index, never the content lake.**
  ``data/content_lake.db`` is gitignored and rebuilt from the repo, so a
  generator that read it would render empty hubs on any checkout that had not
  run the backfill first — exactly how the public search index shipped zero
  episodes ~13x a day until July 2026. ``site/data/search-index.json`` is
  committed, carries date/title/hook/url per episode, and is rebuilt by the
  same nightly step.
* **A hub that cannot be filled is not written.** Below
  ``MIN_EPISODES_FOR_HUB`` the page would be a stub competing with its own
  show page, so the generator skips it and says so.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent

#: The committed episode index the hubs read. Rebuilt nightly and by the
#: run-show finalize job (``scripts/build_search_index.py``), which refuses to
#: overwrite a populated index with an empty one — so a hub built from it
#: inherits that protection.
SEARCH_INDEX_PATH = ROOT / "site" / "data" / "search-index.json"

#: A hub needs this many episodes behind it to be worth a page. Under it the
#: hub would be a thinner copy of the show page it points at.
MIN_EPISODES_FOR_HUB = 12

#: Shows that never appear in a subject hub. Nerra Daily is the whole network
#: spliced into one episode, so its registry topics are honest (it really does
#: carry markets, science and world news) and its presence is still wrong here:
#: a reader who came for Canadian investing does not want a two-hour edition of
#: everything, and listing it in three hubs made all three less useful. Its own
#: page and /mira.html serve it properly.
HUB_EXCLUDED_SHOWS = frozenset({"nerra_daily"})

#: How many episodes a hub lists. Enough to show real depth, bounded so the
#: page stays small and the newest work is what a reader sees first.
HUB_EPISODE_LIMIT = 24

#: Directory the hubs render into, relative to the repo root.
HUB_DIR = "topics"


#: The hubs, in the order they are listed. ``picker_topics`` are matched
#: against each show's ``picker_tags.topics`` in the registry, so adding a
#: show to a hub is a registry edit, not a code edit. ``intro`` is the
#: subject in the network's own words; ``angle`` is the one line that says
#: what this network does with the subject that a generic feed does not.
TOPIC_HUBS: Tuple[Dict[str, Any], ...] = (
    {
        "id": "ai",
        "title": "AI podcasts — models, agents, and the people building them",
        "heading": "Artificial intelligence",
        "picker_topics": ("ai", "research"),
        "intro": (
            "Artificial intelligence moves faster than any daily show can "
            "summarise, so the network covers it three ways instead of one: a "
            "daily brief on what shipped, the same material explained from "
            "scratch for someone who has never used an API, and an interview "
            "show where the host is itself an AI."
        ),
        "angle": (
            "Every episode names its sources, and a claim whose source cannot "
            "be checked is removed before publication rather than softened."
        ),
        "meta_description": (
            "Daily AI podcasts from Nerra Network: model and agent releases, "
            "the same news explained for beginners, and interviews conducted "
            "by an AI host. Free, ad-free, sources named."
        ),
        "keywords": "AI podcast, artificial intelligence podcast, LLM podcast, AI agents, AI news daily",
    },
    {
        "id": "space",
        "title": "Space podcasts — SpaceX, astronomy, and the engineering behind both",
        "heading": "Space",
        "picker_topics": ("space", "astronomy", "spacex", "starship", "starlink"),
        "intro": (
            "Two shows split the sky between them. One follows SpaceX as an "
            "operating company — launch cadence, Starship test articles, "
            "Starlink economics, the filings — and the other covers the wider "
            "frontier: telescopes, missions, and the findings that arrive from "
            "further out."
        ),
        "angle": (
            "The SpaceX show is engineering-first: it would rather explain one "
            "design decision properly than list six headlines."
        ),
        "meta_description": (
            "Space podcasts from Nerra Network: a daily SpaceX engineering "
            "brief and a daily show on astronomy and the wider frontier. Free "
            "and ad-free."
        ),
        "keywords": "space podcast, SpaceX podcast, Starship, Starlink, astronomy podcast, space news daily",
    },
    {
        "id": "markets",
        "title": "Investing and markets podcasts — Canadian and US",
        "heading": "Markets and investing",
        "picker_topics": ("stocks", "investing", "personal-finance", "markets"),
        "intro": (
            "Four shows reach the markets from different directions: a daily "
            "brief built around the Canadian investor as much as the American "
            "one, two companies covered as listed companies rather than as "
            "tickers, and financial literacy in Russian for people whose "
            "money moved countries with them."
        ),
        "angle": (
            "The practice portfolio publishes its whole record — the rules, "
            "every trade, the losers and the abandoned positions — so the "
            "track record can be audited instead of taken on trust."
        ),
        "meta_description": (
            "Investing podcasts from Nerra Network: daily market coverage for "
            "Canadian and US investors, a fully published practice-portfolio "
            "record, and financial literacy in Russian."
        ),
        "keywords": "investing podcast, Canadian investing podcast, TFSA, RRSP, stock market podcast, personal finance podcast",
    },
    {
        "id": "tesla",
        "title": "Tesla podcast — daily, and about the engineering",
        "heading": "Tesla",
        "picker_topics": ("tesla", "ev"),
        "intro": (
            "A daily Tesla show that treats the company as an engineering and "
            "manufacturing story rather than a stock-price story: the software "
            "releases, the factory ramps, the hardware revisions, and what the "
            "filings say."
        ),
        "angle": (
            "It tracks long-running programs across months, so a new filing "
            "arrives as an update to something you already heard rather than "
            "as a fresh headline."
        ),
        "meta_description": (
            "A daily Tesla podcast from Nerra Network: software releases, "
            "factory ramps, hardware revisions and filings, with the ongoing "
            "programs tracked across months. Free and ad-free."
        ),
        "keywords": "Tesla podcast, Tesla daily news, Cybertruck, Optimus, EV podcast, TSLA",
    },
    {
        "id": "science",
        "title": "Science podcasts — research, findings, and what they change",
        "heading": "Science",
        "picker_topics": ("science",),
        "intro": (
            "The science coverage is built from primary research rather than "
            "press releases about research, which is why some days are thinner "
            "than others: a show here would rather skip a day than pad one."
        ),
        "angle": (
            "Findings are reported with what they do and do not establish, "
            "because the gap between those two is where most science coverage "
            "goes wrong."
        ),
        "meta_description": (
            "Science podcasts from Nerra Network: daily coverage of new "
            "research across biology, physics and space, reported from primary "
            "sources with its limits stated."
        ),
        "keywords": "science podcast, research podcast, daily science news, science explained",
    },
    {
        "id": "health-and-longevity",
        "title": "Health and longevity podcast — the research, not the supplements",
        "heading": "Health and longevity",
        "picker_topics": ("longevity", "biotech", "health"),
        "intro": (
            "Longevity has more marketing than evidence, so this coverage "
            "stays on the research: what a study measured, in what population, "
            "and how far the result actually reaches."
        ),
        "angle": (
            "No protocols, no supplement stacks, and no claim that outruns its "
            "source."
        ),
        "meta_description": (
            "A daily health and longevity podcast from Nerra Network: new "
            "research on aging, biotech and human health, reported with its "
            "limits rather than its hype."
        ),
        "keywords": "longevity podcast, health research podcast, biotech podcast, aging research",
    },
    {
        "id": "climate-and-energy",
        "title": "Climate, energy and environmental policy podcasts",
        "heading": "Climate and energy",
        "picker_topics": ("climate", "environment", "regulatory", "energy"),
        "intro": (
            "Two different jobs share this subject. One is regulatory: what "
            "Canadian environmental rules actually require, province by "
            "province, in a form you can forward to a team. The other is "
            "progress: the clean-energy build-out, reported with numbers "
            "instead of adjectives."
        ),
        "angle": (
            "The compliance brief exists because a consultation today is a "
            "gazetted rule next year, and almost nobody covers that gap."
        ),
        "meta_description": (
            "Climate and energy podcasts from Nerra Network: Canadian "
            "environmental regulation explained for teams, plus the "
            "clean-energy build-out with honest numbers."
        ),
        "keywords": "climate podcast, energy podcast, environmental policy Canada, compliance brief, clean energy",
    },
    {
        "id": "world-news",
        "title": "World news podcast — both sides, argued at their strongest",
        "heading": "World news",
        "picker_topics": ("world-news", "politics", "balanced", "news"),
        "intro": (
            "The world-news show has one unusual rule: every competing "
            "position is presented in its strongest form, with its best "
            "supporting reason first. You should not be able to tell from the "
            "episode which side the show favours."
        ),
        "angle": (
            "It is the opposite of a balance disclaimer — the argument itself "
            "has to be steel-manned, not labelled."
        ),
        "meta_description": (
            "A daily world news podcast from Nerra Network that argues every "
            "side at its strongest — you should not be able to tell which one "
            "it favours. Free and ad-free."
        ),
        "keywords": "world news podcast, balanced news podcast, daily news briefing, steel man",
    },
    {
        "id": "interviews",
        "title": "Interview podcasts — an AI host, real guests, guest-approved",
        "heading": "Interviews",
        "picker_topics": ("interviews", "society", "business"),
        "intro": (
            "Two interview shows share a host, and the host is an AI. One "
            "talks to people working on artificial intelligence; the other "
            "talks to people about whatever work they have chosen, with no AI "
            "angle required."
        ),
        "angle": (
            "A human editor reviews every episode with no timer, and every "
            "guest gets their own transcript first — a week to approve it, "
            "cut from it or refuse it, and a takedown afterwards."
        ),
        "meta_description": (
            "Interview podcasts from Nerra Network, hosted by Mira, an AI: "
            "real guests, a human editorial review, and no episode published "
            "until the guest approves their transcript."
        ),
        "keywords": "interview podcast, AI host, AI interviewer, guest podcast, Nerra Voices, The Age of AI",
        # Below the depth bar today (4 published interviews). That is the
        # right outcome rather than a thin page: /mira.html already covers
        # the subject properly, including how an interview runs and the two
        # gates. The hub turns itself on when the archive grows.
        "alternative": {"label": "Meet Mira, the AI host", "href": "mira.html"},
    },
    {
        "id": "history-and-consequences",
        "title": "History and first-principles podcasts — how decisions played out",
        "heading": "History and consequences",
        "picker_topics": ("history", "policy", "narrative"),
        "intro": (
            "Two narrative shows work backwards from outcomes. One takes a "
            "decision that made sense at the time and follows what it actually "
            "caused; the other strips a problem to its physics and its costs "
            "to ask what it should cost instead."
        ),
        "angle": (
            "Neither runs on the news cycle — the episodes are written from a "
            "curated queue, so they are worth hearing a year later."
        ),
        "meta_description": (
            "Narrative podcasts from Nerra Network: the unintended "
            "consequences of reasonable decisions, and first-principles "
            "thinking applied to real industries."
        ),
        "keywords": "history podcast, unintended consequences, first principles podcast, policy podcast",
    },
    {
        "id": "engineering",
        "title": "Engineering podcasts — costs, constraints and how things get built",
        "heading": "Engineering",
        "picker_topics": ("engineering", "innovation", "manufacturing"),
        "intro": (
            "Engineering coverage across the network shares one habit: follow "
            "the constraint. What does the part cost, what does the process "
            "allow, and which of those two is actually the limit?"
        ),
        "angle": (
            "The first-principles show puts a number on it — what the raw "
            "materials cost against what the finished thing sells for."
        ),
        "meta_description": (
            "Engineering podcasts from Nerra Network: manufacturing ramps, "
            "rocket hardware, and first-principles cost analysis of real "
            "industries."
        ),
        "keywords": "engineering podcast, manufacturing podcast, first principles, idiot index, cost engineering",
    },
    {
        "id": "sailing",
        "title": "Offshore sailing podcast — a Canadian Vendée Globe campaign",
        "heading": "Offshore sailing",
        "picker_topics": ("sailing", "sports", "adventure", "canada"),
        "intro": (
            "A weekly show following Canada Ocean Racing and EMIRA IV toward "
            "the Route du Rhum and the Vendée Globe, written for people who "
            "have never touched a rope as much as for the ones who have."
        ),
        "angle": (
            "It carries a public campaign dashboard and a glossary, so the "
            "boat's last known position always has a date and a source next to "
            "it."
        ),
        "meta_description": (
            "A weekly offshore sailing podcast from Nerra Network following "
            "Canada Ocean Racing and EMIRA IV toward the Route du Rhum and the "
            "Vendée Globe."
        ),
        "keywords": "sailing podcast, offshore racing, Vendee Globe, Route du Rhum, IMOCA, Canada Ocean Racing",
        # Weekly show, so the archive grows slowly. The campaign dashboard and
        # the Plain Sailing glossary already serve the subject better than a
        # six-episode hub would.
        "alternative": {"label": "Offshore North campaign dashboard",
                        "href": "offshore-north-dashboard.html"},
    },
    {
        "id": "language-learning",
        "title": "Russian language podcast — vocabulary first, for English speakers",
        "heading": "Language learning",
        "picker_topics": ("language-learning",),
        "intro": (
            "A bilingual Russian course built around vocabulary rather than "
            "news: a theme is chosen first, the words come from that theme, and "
            "nothing is re-taught before you have had a chance to forget it."
        ),
        "angle": (
            "It tracks what it has already taught, so the word of the day is "
            "never a repeat."
        ),
        "meta_description": (
            "A bilingual Russian language podcast from Nerra Network for "
            "English speakers: vocabulary-first lessons on everyday themes, "
            "free and ad-free."
        ),
        "keywords": "Russian podcast, learn Russian, Russian for English speakers, bilingual podcast, vocabulary",
    },
    {
        "id": "good-news",
        "title": "Good news podcast — progress, with honest numbers",
        "heading": "Good news",
        "picker_topics": ("good-news",),
        "intro": (
            "A two-host daily show on things that are going right in science "
            "and technology, plus one action a listener can actually take — "
            "with the arithmetic shown rather than implied."
        ),
        "angle": (
            "If the honest number for an action is small, the episode says so. "
            "That is the point of showing it."
        ),
        "meta_description": (
            "A daily good-news podcast from Nerra Network: progress in science "
            "and technology from two hosts, plus one concrete action with "
            "honest numbers."
        ),
        "keywords": "good news podcast, positive news, progress podcast, climate action, do positive",
    },
)


def hub_by_id(hub_id: str) -> Optional[Dict[str, Any]]:
    for hub in TOPIC_HUBS:
        if hub["id"] == hub_id:
            return hub
    return None


@lru_cache(maxsize=4)
def load_search_index(path: Path = SEARCH_INDEX_PATH) -> Optional[dict]:
    """The committed episode index, or ``None`` when it is missing/unreadable.

    ``None`` is the signal to skip the hubs entirely rather than write empty
    ones — see the module docstring.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("episodes"), list):
        return None
    return data


def hub_shows(hub: Dict[str, Any], all_shows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Shows whose registry ``picker_tags.topics`` intersect this hub.

    Registry-driven on purpose: putting a show in a hub is a one-line YAML
    edit, and a new show joins the hubs it claims without touching this file.
    """
    wanted = {t.lower() for t in hub.get("picker_topics", ())}
    out = []
    for show in all_shows:
        if show.get("slug") in HUB_EXCLUDED_SHOWS:
            continue
        # A show with no feed file yet (pre-launch) joins no hub: a hub
        # page must not advertise a show a visitor cannot listen to (the
        # Sep 19 2026 "no surface advertises something that does not
        # exist" rule). It joins its hubs automatically once its feed exists.
        if show.get("has_feed") is False:
            continue
        topics = {
            str(t).lower()
            for t in ((show.get("picker_tags") or {}).get("topics") or [])
        }
        if topics & wanted:
            out.append(show)
    return out


def hub_episodes(
    records: Iterable[Dict[str, Any]],
    slugs: Iterable[str],
    *,
    limit: int = HUB_EPISODE_LIMIT,
) -> Tuple[List[Dict[str, Any]], int]:
    """(newest *limit* episodes for *slugs*, total episodes available).

    The total is reported separately so the page can say how deep the archive
    goes without listing all of it.
    """
    wanted = {s for s in slugs}
    matched = [
        r for r in records
        if r.get("show_slug") in wanted and (r.get("url") or "").strip()
    ]
    matched.sort(key=lambda r: (str(r.get("date") or ""), r.get("episode_num") or 0),
                 reverse=True)
    return matched[:limit], len(matched)


def build_hub_context(
    hub: Dict[str, Any],
    all_shows: Sequence[Dict[str, Any]],
    index: dict,
    *,
    limit: int = HUB_EPISODE_LIMIT,
) -> Optional[Dict[str, Any]]:
    """Everything the template needs, or ``None`` when the hub is too thin."""
    shows = hub_shows(hub, all_shows)
    if not shows:
        return None
    episodes, total = hub_episodes(
        index.get("episodes") or [], [s["slug"] for s in shows], limit=limit)
    if total < MIN_EPISODES_FOR_HUB:
        return None
    return {
        "hub": hub,
        "shows": shows,
        "episodes": episodes,
        "episode_total": total,
    }


def renderable_hubs(
    all_shows: Sequence[Dict[str, Any]],
    index: dict,
    *,
    limit: int = HUB_EPISODE_LIMIT,
) -> List[Dict[str, Any]]:
    """Hub contexts that clear the depth bar, in declaration order."""
    out = []
    for hub in TOPIC_HUBS:
        ctx = build_hub_context(hub, all_shows, index, limit=limit)
        if ctx:
            out.append(ctx)
    return out


def hubs_for_show(
    show_slug: str,
    all_shows: Sequence[Dict[str, Any]],
    index: Optional[dict] = None,
) -> List[Dict[str, Any]]:
    """The hubs this show belongs to, as ``{"id", "heading"}`` records.

    Used by every blog post to link into its subjects. That link is the whole
    reason the hubs can rank: ~1,880 dated articles each pointing at the
    evergreen page for their subject is the internal-link structure search
    engines read as "this page is the authority here", and without it the hubs
    are orphans reachable only from the nav.

    A hub that the generator SKIPPED for thinness is never linked — an internal
    link to a page that was not written is the broken-link class the Sep 19
    pass removed from ~1,990 pages.
    """
    if index is None:
        index = load_search_index()
    live = _live_hub_ids(all_shows, index)
    out = []
    for hub in TOPIC_HUBS:
        if live and hub["id"] not in live:
            continue
        for show in hub_shows(hub, all_shows):
            if show.get("slug") == show_slug:
                out.append({"id": hub["id"], "heading": hub["heading"]})
                break
    return out


#: Process-local memo for the live-hub set. ``renderable_hubs`` walks 1,886
#: index records per hub, and ``hubs_for_show`` runs once per blog post, so
#: recomputing it per post would be ~20 million comparisons on a full regen.
#:
#: Keyed on the index's CONTENT signature and the show set, never on
#: ``id(index)``: CPython reuses an address once the old object is collected,
#: so an identity key can hand a later, different index the earlier one's
#: answer — a wrong hub list that looks exactly like a right one.
_LIVE_HUB_IDS: Dict[tuple, frozenset] = {}


def _live_hub_ids(all_shows: Sequence[Dict[str, Any]], index: Optional[dict]) -> frozenset:
    if not index:
        return frozenset()
    key = (
        str(index.get("generated_at") or ""),
        len(index.get("episodes") or ()),
        tuple(sorted(str(s.get("slug") or "") for s in all_shows)),
    )
    cached = _LIVE_HUB_IDS.get(key)
    if cached is None:
        cached = frozenset(
            c["hub"]["id"] for c in renderable_hubs(all_shows, index))
        _LIVE_HUB_IDS[key] = cached
    return cached


def alternatives_for_thin_hubs(
    all_shows: Sequence[Dict[str, Any]],
    index: dict,
    *,
    limit: int = HUB_EPISODE_LIMIT,
) -> List[Dict[str, Any]]:
    """Hubs that did not clear the bar but name a page that covers the subject.

    Rendered as one-line pointers on the topics index, so a reader looking for
    "interviews" is sent somewhere real instead of to a stub — and nothing
    silently disappears from the site's own map.
    """
    out = []
    for hub in TOPIC_HUBS:
        if build_hub_context(hub, all_shows, index, limit=limit):
            continue
        alt = hub.get("alternative")
        if alt:
            out.append({"heading": hub["heading"], **alt})
    return out


def hub_page_path(hub_id: str) -> str:
    """Site-relative path for a hub page."""
    return f"{HUB_DIR}/{hub_id}.html"
