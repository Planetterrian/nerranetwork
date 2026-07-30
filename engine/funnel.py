"""One module owns every funnel link, campaign id, and capture tag.

Why this exists
---------------
The July 18 2026 network audit found the factory world-class and the
*funnel* the product gap: ~3,900 downloads/30d and 3 newsletter
subscribers, with no way to tell which surface produced either. The
reason was not missing analytics accounts — OP3, YouTube Analytics,
GA4 and Buttondown were all live. The reason was that nothing they
measured shared a key, so the four datasets could never be joined:

* ``engine.video_metadata`` hand-rolled ``utm_campaign=ep45`` — no show
  slug, so every show's episode 45 collided into one GA4 campaign row.
* ``engine.ru_dub`` linked the bare homepage with no UTM at all, so the
  network's highest-reach surface (@NerraRU Shorts) was invisible.
* Buttondown captured one undifferentiated ``gallery-subscriber`` tag,
  so a signup could never be traced back to the video that earned it.

This module is the single source of truth that closes that gap, in the
same spirit as :mod:`engine.titles`: **never build a funnel URL, a
campaign string, or a capture tag anywhere else.** Import from here.

The contract
------------
Two halves that must stay exact inverses of each other:

    build:  campaign_id(...)          -> "nn-spacex-ru-short-ep045"
    parse:  parse_campaign_id(...)    -> Campaign(show="spacex", ...)

``scripts/build_funnel.py`` reads campaign strings back out of GA4 and
attributes them to a show / episode / channel / placement / experiment
variant purely by parsing them. If the two halves drift, the funnel
silently reports zeros for the surfaces that changed — the exact
failure class this module was written to end — so
``tests/test_funnel.py`` round-trips every generated shape.

Format::

    nn-<show>-<channel>-<kind>-ep<NNN>[-<variant>]

``-`` is the separator and can never appear inside a component: show
slugs use underscores, channels are ISO-ish language tokens, kinds come
from a closed set, the episode is numeric, and variants are normalised
to ``[a-z0-9_]``. So ``split("-")`` is unambiguous and needs no
escaping.

Placement (description / comment / end card / show page) rides in
``utm_content`` instead of the campaign, so one campaign aggregates a
video's whole surface area while still breaking down by placement.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, Iterable, Optional
from urllib.parse import quote, urlparse, urlunparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Taxonomy — closed vocabularies. Adding a value here is the ONLY way a new
# surface enters the funnel; the parser rejects anything else so a typo shows
# up as an unattributed row in api/funnel.json rather than as silence.
# ---------------------------------------------------------------------------

CAMPAIGN_PREFIX = "nn"

# utm_source — WHERE the click came from. YouTube is channel-qualified
# because @NerraNetwork / @NerraRU / @NerraFR are separate audiences with
# separate economics.
SOURCE_YOUTUBE = "youtube"
SOURCE_YOUTUBE_RU = "youtube_ru"
SOURCE_YOUTUBE_FR = "youtube_fr"
SOURCE_PODCAST = "podcast"
SOURCE_NEWSLETTER = "newsletter"
SOURCE_X = "x"
SOURCE_SITE = "nerranetwork"

SOURCES = frozenset({
    SOURCE_YOUTUBE, SOURCE_YOUTUBE_RU, SOURCE_YOUTUBE_FR,
    SOURCE_PODCAST, SOURCE_NEWSLETTER, SOURCE_X, SOURCE_SITE,
})

# utm_medium — WHAT KIND of thing the click came from.
MEDIUM_SHORT = "short"
MEDIUM_LONG = "long"
MEDIUM_EPISODE = "episode"      # podcast show notes / RSS
MEDIUM_EMAIL = "email"
MEDIUM_SOCIAL = "social"
MEDIUM_WEB = "web"

MEDIUMS = frozenset({
    MEDIUM_SHORT, MEDIUM_LONG, MEDIUM_EPISODE,
    MEDIUM_EMAIL, MEDIUM_SOCIAL, MEDIUM_WEB,
})

# utm_content — WHICH PLACEMENT inside that thing.
PLACEMENT_DESCRIPTION = "description"
PLACEMENT_COMMENT = "comment"
PLACEMENT_ENDCARD = "endcard"
PLACEMENT_SHOWNOTES = "shownotes"
PLACEMENT_BODY = "body"

PLACEMENTS = frozenset({
    PLACEMENT_DESCRIPTION, PLACEMENT_COMMENT, PLACEMENT_ENDCARD,
    PLACEMENT_SHOWNOTES, PLACEMENT_BODY,
})

# The ``kind`` component of a campaign id — the asset that carried the link.
KINDS = frozenset({"short", "long", "episode", "email", "post"})

# YouTube channel token -> utm_source. Unknown channels fall back to a
# generic ``youtube_<token>`` so a new dub channel is attributable the day
# it launches, without a code change.
_CHANNEL_SOURCES: Dict[str, str] = {
    "en": SOURCE_YOUTUBE,
    "ru": SOURCE_YOUTUBE_RU,
    "fr": SOURCE_YOUTUBE_FR,
}

_SLUG_RE = re.compile(r"[^a-z0-9_]+")
_CAMPAIGN_RE = re.compile(
    r"^" + CAMPAIGN_PREFIX + r"-"
    r"(?P<show>[a-z0-9_]+)-"
    r"(?P<channel>[a-z0-9_]+)-"
    r"(?P<kind>[a-z0-9_]+)-"
    r"ep(?P<episode>\d+)"
    r"(?:-(?P<variant>[a-z0-9_]+))?$"
)


# ---------------------------------------------------------------------------
# Campaign ids
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Campaign:
    """A parsed campaign id. ``variant`` is ``""`` when the asset was not
    part of an experiment."""

    show: str
    channel: str
    kind: str
    episode: int
    variant: str = ""

    @property
    def source(self) -> str:
        """The ``utm_source`` this campaign's asset would have used."""
        return channel_source(self.channel)

    def as_dict(self) -> Dict[str, object]:
        return {
            "show": self.show,
            "channel": self.channel,
            "kind": self.kind,
            "episode": self.episode,
            "variant": self.variant,
        }


def _norm(token: str) -> str:
    """Lowercase a token and squash everything the separator would eat.

    Hyphens become underscores (not dropped) so ``models-agents`` and
    ``modelsagents`` can never collide into one campaign row.
    """
    token = (token or "").strip().lower().replace("-", "_")
    token = _SLUG_RE.sub("_", token)
    return token.strip("_")


def channel_source(channel: str) -> str:
    """``"ru"`` -> ``"youtube_ru"``. Unknown tokens stay attributable."""
    token = _norm(channel) or "en"
    known = _CHANNEL_SOURCES.get(token)
    if known:
        return known
    return f"{SOURCE_YOUTUBE}_{token}"


def campaign_id(
    show_slug: str,
    episode: int,
    *,
    channel: str = "en",
    kind: str = "short",
    variant: str = "",
) -> str:
    """Build the canonical campaign id for one published asset.

    >>> campaign_id("spacex", 45, channel="ru", kind="short")
    'nn-spacex-ru-short-ep045'
    >>> campaign_id("spacex", 45, variant="grok_video")
    'nn-spacex-en-short-ep045-grok_video'
    """
    show = _norm(show_slug)
    if not show:
        # Still parseable, so the row is not lost — but loud, because
        # every campaign from this caller will pile into one
        # "nn-unknown-…" bucket and be attributable to no show at all.
        logger.warning(
            "funnel: campaign built with no show slug — attribution for "
            "this asset will land under 'unknown' (episode %s, channel %s)",
            episode, channel,
        )
        show = "unknown"
    chan = _norm(channel) or "en"
    knd = _norm(kind) or "short"
    try:
        ep = max(0, int(episode))
    except (TypeError, ValueError):
        ep = 0
    parts = [CAMPAIGN_PREFIX, show, chan, knd, f"ep{ep:03d}"]
    var = _norm(variant)
    if var:
        parts.append(var)
    return "-".join(parts)


def parse_campaign_id(campaign: str) -> Optional[Campaign]:
    """Inverse of :func:`campaign_id`. ``None`` when the string is not ours.

    Returning ``None`` (rather than guessing) is deliberate: GA4 campaign
    rows include organic and third-party values, and the funnel builder
    buckets everything unparseable under ``other`` instead of inventing
    an attribution.
    """
    m = _CAMPAIGN_RE.match((campaign or "").strip().lower())
    if not m:
        return None
    kind = m.group("kind")
    if kind not in KINDS:
        return None
    return Campaign(
        show=m.group("show"),
        channel=m.group("channel"),
        kind=kind,
        episode=int(m.group("episode")),
        variant=m.group("variant") or "",
    )


# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------

def funnel_link(
    destination: str,
    *,
    source: str,
    medium: str,
    campaign: str = "",
    placement: str = "",
) -> str:
    """Tag *destination* with the funnel's UTM parameters.

    Idempotent by contract: a URL that already carries ``utm_source`` is
    returned untouched, so a link that passes through two surfaces keeps
    the attribution of the first one rather than acquiring a second,
    conflicting set (the ``_with_utm`` filter in ``generate_html.py``
    established this rule for the website; the funnel uses the same one).

    An empty *destination* returns ``""`` — callers append the result to
    a description only when truthy, so a show with no destination
    configured simply ships one fewer line rather than a bare "?utm_…".
    """
    dest = (destination or "").strip()
    if not dest:
        return ""
    if "utm_source=" in dest:
        return dest

    parts = [
        f"utm_source={quote(source or SOURCE_SITE, safe='')}",
        f"utm_medium={quote(medium or MEDIUM_WEB, safe='')}",
    ]
    if campaign:
        parts.append(f"utm_campaign={quote(campaign, safe='')}")
    if placement:
        parts.append(f"utm_content={quote(placement, safe='')}")

    scheme, netloc, path, params, query, fragment = urlparse(dest)
    query = "&".join([q for q in (query, "&".join(parts)) if q])
    return urlunparse((scheme, netloc, path, params, query, fragment))


def episode_link(
    destination: str,
    show_slug: str,
    episode: int,
    *,
    channel: str = "en",
    kind: str = "short",
    placement: str = PLACEMENT_DESCRIPTION,
    variant: str = "",
    source: str = "",
    medium: str = "",
) -> str:
    """The common case: tag *destination* for one episode's asset.

    Derives ``utm_source`` from the channel and ``utm_medium`` from the
    asset kind, so a caller only has to know what it just published.
    """
    kind_norm = _norm(kind) or "short"
    resolved_medium = medium or {
        "short": MEDIUM_SHORT,
        "long": MEDIUM_LONG,
        "episode": MEDIUM_EPISODE,
        "email": MEDIUM_EMAIL,
        "post": MEDIUM_SOCIAL,
    }.get(kind_norm, MEDIUM_WEB)
    return funnel_link(
        destination,
        source=source or channel_source(channel),
        medium=resolved_medium,
        campaign=campaign_id(
            show_slug, episode, channel=channel, kind=kind_norm,
            variant=variant,
        ),
        placement=placement,
    )


# ---------------------------------------------------------------------------
# Destinations — where a surface's viewers are actually sent
# ---------------------------------------------------------------------------

def destination_for(config, *, channel: str = "en") -> str:
    """Resolve one show's funnel destination for a publishing *channel*.

    Priority: ``funnel.destinations[<channel>]`` -> ``funnel.destinations
    ["default"]`` -> the show page (``publishing.rss_link``) ->
    ``publishing.base_url``.

    The per-channel override is the whole point of the RU SpaceX pilot:
    @NerraRU Shorts get a Russian landing page with one call to action,
    while @NerraNetwork keeps sending viewers to the English show page.
    """
    funnel_cfg = getattr(config, "funnel", None)
    if funnel_cfg is not None and getattr(funnel_cfg, "enabled", True):
        dests = getattr(funnel_cfg, "destinations", None) or {}
        if isinstance(dests, dict):
            token = _norm(channel) or "en"
            for key in (token, "default"):
                value = (dests.get(key) or "").strip()
                if value:
                    return value

    publishing = getattr(config, "publishing", None)
    for attr in ("rss_link", "base_url"):
        value = (getattr(publishing, attr, "") or "").strip()
        if value:
            return value
    return ""


def capture_tags(
    config,
    *,
    channel: str = "en",
    extra: Optional[Iterable[str]] = None,
) -> list:
    """Buttondown tags a capture from this surface should carry.

    Always includes the show's newsletter tag (so the subscriber gets the
    show they asked for) plus a ``src-<source>`` tag (so
    ``scripts/build_funnel.py`` can count captures per surface), plus any
    pilot tag configured under ``funnel.capture_tag``.
    """
    tags: list = []

    def _add(tag: str) -> None:
        tag = (tag or "").strip()
        if tag and tag not in tags:
            tags.append(tag)

    _add(getattr(getattr(config, "newsletter", None), "tag", ""))
    funnel_cfg = getattr(config, "funnel", None)
    if funnel_cfg is not None:
        _add(getattr(funnel_cfg, "capture_tag", ""))
    _add(source_tag(channel_source(channel)))
    for tag in extra or ():
        _add(tag)
    return tags


SOURCE_TAG_PREFIX = "src-"


def source_tag(source: str) -> str:
    """``"youtube_ru"`` -> ``"src-youtube-ru"`` (Buttondown-safe)."""
    token = _norm(source).replace("_", "-")
    return f"{SOURCE_TAG_PREFIX}{token}" if token else ""


def source_from_tag(tag: str) -> str:
    """Inverse of :func:`source_tag`; ``""`` for a non-source tag."""
    tag = (tag or "").strip().lower()
    if not tag.startswith(SOURCE_TAG_PREFIX):
        return ""
    return tag[len(SOURCE_TAG_PREFIX):].replace("-", "_")
