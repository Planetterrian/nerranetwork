"""Nerra Personal — per-subscriber personalized daily editions.

The paid tier of the member system (Aug 2026, operator-directed): each
subscriber picks WHICH shows and in WHAT ORDER, and Mira anchors their
private daily feed — greeting them by name, linking their chosen
segments, and (on the local tier) opening with a short brief for their
city. Built directly on :mod:`engine.daily_edition`: the segments are
the same already-published, promo-trimmed pieces Nerra Daily splices, so
the marginal cost per subscriber is Mira's links (LLM + TTS) plus one
stream-copy concat — measured ~$0.05-0.07/day.

Contracts that bind:

* **Per-day segment cache.** Every subscriber's edition on a given day
  is assembled from the SAME trimmed segment files. The batch builder
  trims each show once into a shared cache dir; per-user work never
  re-downloads or re-trims. Without this, cost scales with users times
  shows instead of shows.
* **PII stays out of logs and out of git.** Specs carry a feed token,
  first name, and city — never an email (the Worker keys accounts by
  email; the builder never sees it). Nothing per-user is ever committed:
  feeds and audio go to the private R2 keyspace ``personal/<token>/``
  and are served ONLY through the Worker's token-checked endpoint, so
  cancelling a subscription revokes the feed immediately.
* **Honest local brief.** Weather comes from Open-Meteo (measured data,
  free); local news/events from one web-search-grounded Grok call under
  the field-note rules — source named aloud, and an unverifiable day
  SKIPS the brief rather than airing filler.
* **Closed show vocabulary.** A spec may only reference shows in
  :data:`PERSONAL_SHOW_SLUGS` (the EN edition lineup); anything else is
  rejected at validation, never guessed at.

Operator setup (Stripe, KV, R2 bucket, cron host):
``docs/nerra_personal.md``. Drift guards: ``tests/test_nerra_personal.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.daily_edition import (
    EDITIONS,
    Segment,
    build_chapters,
    digest_excerpt,
    sanitize_spoken,
)

logger = logging.getLogger(__name__)

#: Shows a member may choose beyond the Nerra Daily roster (Sep 24 2026):
#: the launch cohort — a member in Vancouver or Collingwood, or one who
#: wants a regional desk, prediction markets or the semis tape, picks it
#: here. They stay OUT of the Nerra Daily lineup on purpose (the edition is
#: a fixed two-hour rundown); a personal edition is the member's own order.
#: Segments are discovered by the same per-show machinery, on the same
#: dated episode files, via :func:`personal_edition_spec`.
PERSONAL_EXTRA_SHOW_SLUGS: Tuple[str, ...] = (
    "vancouver", "collingwood", "prediction_markets", "mag7", "ai_chips",
    "peptides", "longevity", "omni_view_world", "omni_view_north_america",
    "omni_view_europe", "omni_view_asia_pacific", "omni_view_africa_mideast",
    "omni_view_latam",
)

#: The only shows a personal lineup may contain — the EN edition roster plus
#: the extra shows above. The Worker mirrors this exact set
#: (workers/gallery/src/personal.ts PERSONAL_SHOWS; drift-guarded).
PERSONAL_SHOW_SLUGS: Tuple[str, ...] = EDITIONS["en"].lineup + PERSONAL_EXTRA_SHOW_SLUGS


def personal_edition_spec():
    """The EN edition spec widened to every show a member may choose — what
    ``build_personal_feeds`` discovers segments with. The Nerra Daily spec
    itself is untouched: its lineup, ready gate and rundown do not change."""
    import dataclasses as _dc
    return _dc.replace(EDITIONS["en"], lineup=PERSONAL_SHOW_SLUGS)

#: Feed serving goes through the Worker (token-checked, revocable) —
#: never a public bucket URL.
PERSONAL_FEED_BASE = "https://api.nerranetwork.com/api/feed"

#: R2 keyspace for everything per-subscriber. Deliberately outside every
#: show's audio prefix AND outside ``nerra_daily/`` so a lifecycle rule
#: can expire personal audio aggressively (subscribers re-download
#: within a day; keep a week).
PERSONAL_R2_PREFIX = "personal"

#: Feed depth per subscriber — a personal daily is a stream, not an
#: archive; the network's public feeds are the archive.
PERSONAL_FEED_MAX_EPISODES = 7

MIRA_PERSONAL_DISCLOSURE = (
    "This personal edition is assembled from the Nerra Network's shows, "
    "which use AI voice synthesis, and my own voice is AI generated too — "
    "the editorial selection and analysis across the network are our own."
)

_TOKEN_RE = re.compile(r"^[a-f0-9]{16,64}$")
_NAME_RE = re.compile(r"^[\w .,'’-]{1,40}$", re.UNICODE)

#: Closed add-on vocabulary (Aug 30 2026, operator-directed): members
#: customize their edition by toggling researched segments on and off.
#: Same discipline as PERSONAL_SHOW_SLUGS — a spec may only reference
#: ids listed here, the Worker mirrors this exact set
#: (workers/gallery/src/personal.ts PERSONAL_ADDONS; drift-guarded in
#: tests/test_nerra_personal.py), and anything else is dropped at
#: validation, never guessed at.
#:
#: ``tier`` is the minimum tier the add-on runs on. Since the Personal
#: News Network launch (Sep 13 2026) every add-on runs on the base tier:
#: the four location add-ons are researched by Mira for the member's
#: chosen location (weather = measured Open-Meteo data; news/events/
#: traffic = one web-search-grounded Grok call under the field-note
#: honesty rules — an unverifiable section is omitted, an unverifiable
#: day SKIPs). What the tiers differ on is DEPTH and BREADTH, not which
#: sections exist: Personal gets the taster (one city, one item per
#: section); Personal News Network gets up to three cities, up to three
#: items per section, and the member's own topics — see
#: :func:`tier_limits`. ``markets`` is deterministic — read from the
#: pipeline's committed price caches (api/tsla.json, api/spcx.json),
#: zero LLM cost.
PERSONAL_ADDONS: Dict[str, Dict[str, str]] = {
    "weather":    {"tier": "personal", "label": "Local weather"},
    "local_news": {"tier": "personal", "label": "Local news"},
    "events":     {"tier": "personal", "label": "Local events"},
    "traffic":    {"tier": "personal", "label": "Traffic & transit"},
    "markets":    {"tier": "personal", "label": "Markets minute"},
}

#: What runs when a member has never touched the toggles: the full
#: taster (one item from each location section) — the operator's call
#: for the Sep 13 2026 launch. It only has an effect once a member has
#: set a location, so nobody's edition changes until they add one.
DEFAULT_ADDONS: Tuple[str, ...] = ("weather", "local_news", "events", "traffic")

#: Per-tier ceilings. ``depth`` is items per researched section in the
#: local brief; ``cities`` how many locations get a brief; ``topics``
#: how many member-named subjects Mira researches. The Worker stores up
#: to the top tier's limits regardless of plan (so a later upgrade
#: applies what the member already typed); the BUILDER enforces the
#: member's actual tier here, the same way effective_addons() does.
TIER_LIMITS: Dict[str, Dict[str, int]] = {
    "personal":       {"depth": 1, "cities": 1, "topics": 0},
    "personal_local": {"depth": 3, "cities": 3, "topics": 5},
}
CITY_MAX_CHARS = 80
TOPIC_MAX_CHARS = 60


def tier_limits(tier: str) -> Dict[str, int]:
    return dict(TIER_LIMITS.get(tier, TIER_LIMITS["personal"]))


def addons_for_tier(tier: str) -> Tuple[str, ...]:
    """The add-on ids a given tier may run."""
    return tuple(a for a, meta in PERSONAL_ADDONS.items()
                 if tier == "personal_local" or meta["tier"] == "personal")


@dataclass
class PersonalSpec:
    """One subscriber's feed definition, as the batch builder sees it."""

    token: str
    shows: List[str]
    tier: str = "personal"          # "personal" | "personal_local"
    first_name: str = ""
    #: Primary location — kept as a plain field for every caller that
    #: predates multiple locations (Sep 13 2026). Always equals
    #: ``cities[0]`` (or "") after validation.
    city: str = ""
    #: Chosen add-on ids (validated subset of PERSONAL_ADDONS, filtered
    #: to the spec's tier). None = the member never saved a choice →
    #: DEFAULT_ADDONS applies at build time.
    addons: Optional[List[str]] = None
    #: All locations, already capped to the tier (1 on Personal, 3 on
    #: PNN). ``city`` is the first of these.
    cities: List[str] = field(default_factory=list)
    #: Member-named subjects Mira researches daily (PNN only; capped to
    #: the tier — always empty on Personal).
    topics: List[str] = field(default_factory=list)
    #: Resolved lazily by the builder (Open-Meteo geocoding, cached per
    #: city name within one run).
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geo_cache: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.city and not self.cities:
            self.cities = [self.city]
        elif self.cities and not self.city:
            self.city = self.cities[0]

    def effective_addons(self) -> List[str]:
        chosen = DEFAULT_ADDONS if self.addons is None else self.addons
        allowed = set(addons_for_tier(self.tier))
        return [a for a in chosen if a in allowed]

    @property
    def depth(self) -> int:
        """Items per researched section in each local brief."""
        return tier_limits(self.tier)["depth"]

    @property
    def is_taster(self) -> bool:
        """True when this member gets the Personal-tier taste of the
        local brief — the thing Mira's weekly nudge is about."""
        return self.tier == "personal"


def validate_spec(raw: dict) -> Optional[PersonalSpec]:
    """Parse one raw spec dict; None (with a warning) on anything off.

    Validation is the trust boundary between the Worker's stored
    preferences and the pipeline: tokens are hex-only (they become R2
    keys and URLs), shows come from the closed vocabulary in their
    user-chosen order, and free-text fields are length/charset capped
    before they reach a prompt.
    """
    if not isinstance(raw, dict):
        return None
    token = str(raw.get("token") or "").strip().lower()
    if not _TOKEN_RE.match(token):
        logger.warning("personal spec rejected: bad token shape")
        return None
    shows_raw = raw.get("shows")
    if not isinstance(shows_raw, list):
        logger.warning("personal spec %s… rejected: shows not a list", token[:8])
        return None
    shows: List[str] = []
    for s in shows_raw:
        slug = str(s).strip()
        if slug in PERSONAL_SHOW_SLUGS and slug not in shows:
            shows.append(slug)
    if len(shows) < 2:
        logger.warning("personal spec %s… rejected: %d valid show(s)",
                       token[:8], len(shows))
        return None
    tier = str(raw.get("tier") or "personal")
    if tier not in ("personal", "personal_local"):
        tier = "personal"
    first_name = str(raw.get("first_name") or "").strip()
    if first_name and not _NAME_RE.match(first_name):
        first_name = ""
    limits = tier_limits(tier)
    # Locations: the new ``cities`` list wins; the legacy single ``city``
    # is honoured for records saved before Sep 13 2026. Capped to the
    # tier HERE (the Worker stores up to the top tier's count).
    cities_raw = raw.get("cities")
    if not isinstance(cities_raw, list):
        cities_raw = [raw.get("city")] if raw.get("city") else []
    cities: List[str] = []
    for c in cities_raw:
        name = _clean_free_text(c, CITY_MAX_CHARS)
        if name and name.lower() not in {x.lower() for x in cities}:
            cities.append(name)
    cities = cities[:limits["cities"]]
    city = cities[0] if cities else ""
    topics_raw = raw.get("topics")
    topics: List[str] = []
    if isinstance(topics_raw, list):
        for t in topics_raw:
            name = _clean_free_text(t, TOPIC_MAX_CHARS)
            if name and name.lower() not in {x.lower() for x in topics}:
                topics.append(name)
    topics = topics[:limits["topics"]]
    addons_raw = raw.get("addons")
    addons: Optional[List[str]] = None
    if isinstance(addons_raw, list):
        # A saved empty list is a real choice ("no add-ons"), distinct
        # from never-saved (None → defaults). Unknown ids are dropped.
        addons = []
        for a in addons_raw:
            aid = str(a).strip()
            if aid in PERSONAL_ADDONS and aid not in addons:
                addons.append(aid)
    return PersonalSpec(token=token, shows=shows, tier=tier,
                        first_name=first_name, city=city, addons=addons,
                        cities=cities, topics=topics)


_FREE_TEXT_RE = re.compile(r"[^\w \-.,'’&/()]", re.UNICODE)


def _clean_free_text(value: object, max_chars: int) -> str:
    """Member-typed text that will land inside a prompt: strip control
    and markup characters, collapse whitespace, cap the length. Same
    discipline as first_name — a prompt never sees raw input."""
    text = re.sub(r"<[^>]*>", " ", str(value or ""))   # tags go first, whole
    text = _FREE_TEXT_RE.sub("", text)
    text = " ".join(text.split())
    return text[:max_chars].strip()


# ---------------------------------------------------------------------------
# Mira's personal links
# ---------------------------------------------------------------------------

def build_personal_links_prompt(
    root: Path,
    spec: PersonalSpec,
    segments: List[Segment],
    target_date: _dt.date,
) -> str:
    template = (root / "shows" / "prompts" / "nerra_personal_links.txt"
                ).read_text(encoding="utf-8")
    lineup_lines = []
    for i, seg in enumerate(segments, 1):
        lineup_lines.append(
            f"{i}. {seg.show_name} — \"{seg.hook or seg.episode_title}\"\n"
            f"   Today's episode covers: {digest_excerpt(seg.content)}"
        )
    listener = spec.first_name or "the listener"
    return template.format(
        date_spoken=target_date.strftime("%A, %B %-d, %Y"),
        listener_name=listener,
        named="yes" if spec.first_name else "no",
        segment_count=len(segments),
        handoff_count=max(0, len(segments) - 1),
        lineup_block="\n".join(lineup_lines),
    )


def fallback_personal_links(
    spec: PersonalSpec, segments: List[Segment], target_date: _dt.date
) -> dict:
    """Deterministic minimal links when the LLM fails — always carries
    the day's real titles, and the greeting still lands personally."""
    who = f", {spec.first_name}" if spec.first_name else ""
    date_spoken = target_date.strftime("%A, %B %-d")
    intro = (
        f"Good morning{who} — this is your Nerra edition for {date_spoken}. "
        f"I'm Mira. Your lineup today: "
        + ", ".join(s.show_name for s in segments) + ". First up, "
        f"{segments[0].show_name}: {segments[0].hook or segments[0].episode_title}"
    )
    handoffs = [
        f"Next in your lineup: {seg.show_name}. Today — "
        f"{seg.hook or seg.episode_title}"
        for seg in segments[1:]
    ]
    signoff = (
        f"And that's your edition for today{who}. Your feed, your order — "
        "adjust it any time at nerranetwork.com. I'm Mira; back tomorrow."
    )
    return {"intro": intro, "handoffs": handoffs, "signoff": signoff}


# ---------------------------------------------------------------------------
# Local brief (personal_local tier)
# ---------------------------------------------------------------------------

#: Per-add-on research instructions for Mira's local brief. Shape-only
#: guidance (de-seed by shape — never a quotable example sentence).
#: ``{n}`` is the tier's depth: "ONE" on the Personal taster, "up to
#: THREE" on Personal News Network.
_ADDON_RESEARCH_LINES = {
    "local_news": (
        "- {n} local news item{s} that a resident would actually care "
        "about (a decision, an opening, a change — not crime-blotter "
        "filler)."),
    "events": (
        "- {n} notable local event{s} coming up (a festival, a talk, a "
        "game, a market)."),
    "traffic": (
        "- {n} current traffic or transit disruption{s} that change{v} how "
        "residents get around this week (a closure, a strike, a major "
        "delay, a new line or detour) — only if a real, current one is "
        "reported; ordinary congestion is not an item."),
}

#: Word budgets per depth: the taster is a paragraph; the full brief
#: may run to a few. parse_local_brief enforces the ceiling.
_BRIEF_WORDS = {1: (60, 160), 3: (120, 320)}


def _depth_words(n: int) -> Tuple[int, int]:
    return _BRIEF_WORDS.get(n, _BRIEF_WORDS[3] if n > 1 else _BRIEF_WORDS[1])


def _research_lines(addons: List[str], depth: int) -> str:
    if depth <= 1:
        fmt = {"n": "ONE", "s": "", "v": "s"}
    else:
        fmt = {"n": f"Up to {['', 'ONE', 'TWO', 'THREE'][min(depth, 3)]}",
               "s": "s", "v": ""}
    return "\n".join(
        _ADDON_RESEARCH_LINES[a].format(**fmt)
        for a in addons if a in _ADDON_RESEARCH_LINES)


def build_local_brief_prompt(
    root: Path,
    spec: PersonalSpec,
    target_date: _dt.date,
    weather_line: str,
    city: Optional[str] = None,
) -> str:
    """The brief prompt for ONE city (``city`` defaults to the primary).
    Depth comes from the tier: one item per section on Personal, up to
    three on Personal News Network."""
    template = (root / "shows" / "prompts" / "nerra_personal_local.txt"
                ).read_text(encoding="utf-8")
    addons = spec.effective_addons()
    depth = spec.depth
    lo, hi = _depth_words(depth)
    if "weather" in addons and weather_line:
        weather_block = (
            "Measured weather (from Open-Meteo — read it naturally, never "
            "alter the numbers):\n" + weather_line)
    else:
        weather_block = "(The listener has no weather section today.)"
    research_requests = _research_lines(addons, depth)
    if depth <= 1:
        depth_rule = ("- At most one item per requested section, told with "
                      "the specific detail that makes it worth knowing — "
                      "never a list.")
    else:
        depth_rule = (f"- Up to {depth} items per requested section, the "
                      "most consequential first, each told with the "
                      "specific detail that makes it worth knowing — "
                      "flowing prose, never a list. Fewer good items beat "
                      "more thin ones.")
    return template.format(
        date_spoken=target_date.strftime("%A, %B %-d, %Y"),
        city=city or spec.city,
        listener_name=spec.first_name or "the listener",
        weather_block=weather_block,
        research_requests=research_requests
        or "(No researched sections requested today.)",
        depth_rule=depth_rule,
        words_lo=lo, words_hi=hi,
    )


def wants_local_brief(spec: PersonalSpec) -> bool:
    """A local brief runs only when a location add-on is actually on."""
    addons = set(spec.effective_addons())
    return bool(spec.cities) and bool(
        addons & ({"weather"} | set(_ADDON_RESEARCH_LINES)))


# ---------------------------------------------------------------------------
# Your topics (Personal News Network)
# ---------------------------------------------------------------------------

#: Generic attributions that are NOT a source. The prompt forbids them;
#: this is the belt to that suspender — logged, never silently accepted.
_GENERIC_SOURCE_RE = re.compile(
    r"\b(local (event )?(guides?|listings?)|event (guides?|listings?)|"
    r"according to (reports|sources)|sources say|reports say|"
    r"it is reported|it's reported|online listings?)\b", re.IGNORECASE)


def generic_attributions(text: str) -> List[str]:
    """The generic-attribution phrases present in a brief, if any."""
    return sorted({m.group(0).lower() for m in _GENERIC_SOURCE_RE.finditer(text or "")})


def build_topics_prompt(
    root: Path,
    spec: PersonalSpec,
    target_date: _dt.date,
) -> str:
    template = (root / "shows" / "prompts" / "nerra_personal_topics.txt"
                ).read_text(encoding="utf-8")
    topic_lines = "\n".join(f"- {t}" for t in spec.topics)
    return template.format(
        date_spoken=target_date.strftime("%A, %B %-d, %Y"),
        listener_name=spec.first_name or "the listener",
        topic_count=len(spec.topics),
        topic_plural="" if len(spec.topics) == 1 else "s",
        topic_lines=topic_lines,
        words_lo=40 * max(1, len(spec.topics)),
        words_hi=90 * max(1, len(spec.topics)),
    )


def wants_topics_brief(spec: PersonalSpec) -> bool:
    return bool(spec.topics)


#: Mira's once-a-week nudge on the Personal tier, spoken right before the
#: sign-off disclosure on a day the taster actually ran. Fixed copy, not
#: LLM: it must be the same honest sentence every time, and it must never
#: fire daily — a daily ad inside a paid product costs more retention
#: than it earns. Monday only.
NUDGE_WEEKDAY = 0  # Monday


def upgrade_nudge_line(spec: PersonalSpec, target_date: _dt.date,
                       taster_ran: bool) -> str:
    if not (spec.is_taster and taster_ran
            and target_date.weekday() == NUDGE_WEEKDAY):
        return ""
    where = spec.city or "your city"
    return (f"One more thing. Today's brief was the taste. Personal News "
            f"Network goes deeper on {where}, adds up to two more places, "
            "and researches the topics you name, every morning. You can "
            "switch plans any time from your account.")


def needs_research_call(spec: PersonalSpec) -> bool:
    """Weather-only briefs are deterministic — skip the Grok call."""
    return bool(set(spec.effective_addons()) & set(_ADDON_RESEARCH_LINES))


def build_markets_line(root: Path) -> str:
    """Deterministic 'markets minute' from the pipeline's committed
    price caches — zero LLM cost, and silent (empty string) when the
    caches are missing or stale rather than ever inventing a number."""
    import json as _json
    parts: List[str] = []
    tsla = root / "api" / "tsla.json"
    spcx = root / "api" / "spcx.json"
    try:
        if tsla.exists():
            d = _json.loads(tsla.read_text(encoding="utf-8"))
            price, prev = d.get("price"), d.get("prev_close")
            if price and prev:
                direction = "up" if price >= prev else "down"
                pct = abs(price - prev) / prev * 100
                parts.append(
                    f"Tesla at ${price:.2f}, {direction} "
                    f"{pct:.1f} percent")
    except Exception:  # noqa: BLE001 — a bad cache never sinks an edition
        pass
    try:
        if spcx.exists():
            d = _json.loads(spcx.read_text(encoding="utf-8"))
            price, prev = d.get("price"), d.get("prev_close")
            if price and prev:
                direction = "up" if price >= prev else "down"
                pct = abs(price - prev) / prev * 100
                # "Ess Pee See Ex", never "S P C X": Grok TTS's server-side
                # text normalization merges the "S P" bigram into "S&P"
                # (the Aug 29 SPCX fix — letter-name words are immune).
                parts.append(
                    f"SpaceX, ticker Ess Pee See Ex, at ${price:.2f}, "
                    f"{direction} {pct:.1f} percent")
    except Exception:  # noqa: BLE001
        pass
    if not parts:
        return ""
    return ("Your markets minute: " + "; ".join(parts)
            + ". As always, prices are from the last market close.")


def parse_local_brief(text: str, *, max_words: int = 220) -> Optional[str]:
    """Same honesty contract as Mira's field note: SKIP or an implausible
    length means no local segment today — never filler. ``max_words``
    scales with depth (the taster's 220, the full brief's 400)."""
    cleaned = sanitize_spoken(text or "")
    if not cleaned or "SKIP" in cleaned[:20].upper():
        return None
    words = len(cleaned.split())
    if not 30 <= words <= max_words:
        logger.warning("local brief rejected at %d words", words)
        return None
    generic = generic_attributions(cleaned)
    if generic:
        # Not fatal — the item may still be real — but it violates the
        # named-source rule and the operator wants to see it happen.
        logger.warning("brief carries generic attribution: %s", ", ".join(generic))
    return cleaned


_NUM_RE = re.compile(r"-?\d+")


def ensure_weather_opener(brief: Optional[str], weather_line: str) -> Optional[str]:
    """The prompt asks Mira to open with the measured weather; on
    2026-09-17 a Vancouver brief came back without it (the model spent
    its words on three researched items). The numbers are the tell: if
    the high and low from the Open-Meteo line are not both in the brief,
    the line is spoken first, verbatim. Measured data is never optional
    when the member asked for it."""
    if not weather_line:
        return brief
    if not brief:
        return weather_line
    nums = _NUM_RE.findall(weather_line)
    head = brief[:400]
    if nums and all(re.search(rf"(?<!\d)(?<!\d\.){re.escape(n)}(?!\d)(?!\.\d)", head)
                    for n in nums):
        return brief
    return f"{weather_line} {brief}"


def brief_max_words(depth: int) -> int:
    return 220 if depth <= 1 else 400


_WEATHER_CODES = {
    0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
    81: "rain showers", 82: "heavy showers", 95: "thunderstorms",
}


def format_weather_line(city: str, daily: dict) -> str:
    """One spoken sentence from an Open-Meteo daily forecast block.

    Measured data only — Mira reads it, never invents it; an empty or
    unusable payload yields "" and the prompt says so.
    """
    try:
        hi = round(float(daily["temperature_2m_max"][0]))
        lo = round(float(daily["temperature_2m_min"][0]))
        code = int(daily.get("weather_code", [None])[0])
    except (KeyError, IndexError, TypeError, ValueError):
        return ""
    sky = _WEATHER_CODES.get(code, "")
    sky_part = f" with {sky}" if sky else ""
    return (f"Today in {city}: a high of {hi} and a low of {lo} degrees"
            f"{sky_part}.")


def fetch_weather_line(spec: PersonalSpec, *, timeout: int = 15,
                       city: Optional[str] = None) -> str:
    """Open-Meteo geocode (once per city, cached on the spec) + daily
    forecast. Free, keyless, best-effort — "" on any failure; the
    forecast call is retried once because it times out now and then
    where the geocoder doesn't (seen 13 Sep 2026)."""
    import requests

    city = city or spec.city
    try:
        coords = spec.geo_cache.get(city)
        if coords is None and city == spec.city and \
                spec.latitude is not None and spec.longitude is not None:
            coords = (spec.latitude, spec.longitude)
        if coords is None:
            geo = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1}, timeout=timeout,
            ).json()
            results = geo.get("results") or []
            if not results:
                return ""
            coords = (float(results[0]["latitude"]),
                      float(results[0]["longitude"]))
            spec.geo_cache[city] = coords
            if city == spec.city:
                spec.latitude, spec.longitude = coords
        daily: dict = {}
        for attempt in (1, 2):
            try:
                forecast = requests.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": coords[0], "longitude": coords[1],
                        "daily": "temperature_2m_max,temperature_2m_min,weather_code",
                        "forecast_days": 1, "timezone": "auto",
                    }, timeout=timeout,
                ).json()
                daily = forecast.get("daily") or {}
                break
            except Exception:  # noqa: BLE001
                if attempt == 2:
                    raise
        return format_weather_line(city, daily)
    except Exception as exc:  # noqa: BLE001 — weather never sinks an edition
        logger.info("weather fetch failed for %s…: %s", spec.token[:8], exc)
        return ""


# ---------------------------------------------------------------------------
# Per-subscriber feed (fresh rebuild from a small R2-side state file —
# the language_feeds pattern: deterministic GUIDs, never an empty feed)
# ---------------------------------------------------------------------------

def feed_url_for(token: str) -> str:
    return f"{PERSONAL_FEED_BASE}/{token}/feed.rss"


def enclosure_url_for(token: str, filename: str) -> str:
    return f"{PERSONAL_FEED_BASE}/{token}/{filename}"


#: The network cover every personal feed showed until Sep 17 2026; still
#: the fallback when a subscriber's own artwork can't be rendered.
NETWORK_COVER_URL = "https://nerranetwork.com/assets/covers/nerra-daily.jpg"
COVER_FILENAME = "cover.jpg"


def build_personal_feed_xml(
    spec: PersonalSpec,
    episodes: List[dict],
    *,
    cover: bool = False,
) -> str:
    """Personal RSS from the subscriber's episode state (newest first).

    *episodes* rows: {episode_num, date (ISO), title, description,
    filename, duration_seconds, bytes} plus, since Sep 17 2026, optional
    ``notes_html`` (rendered as ``content:encoded``) and ``transcripts``
    (filenames beside the MP3, tagged ``<podcast:transcript>``). GUIDs
    are deterministic (``personal-<token8>-epNNN-date``) so a rebuild
    never re-notifies a podcast app. ``cover=True`` points the channel
    art at the subscriber's own ``cover.jpg`` in their keyspace.
    """
    from feedgen.feed import FeedGenerator

    fg = FeedGenerator()
    fg.load_extension("podcast")
    who = f"{spec.first_name}'s" if spec.first_name else "Your"
    fg.title(f"{who} Nerra Daily")
    fg.link(href="https://nerranetwork.com/join.html", rel="alternate")
    fg.description(
        "Your personal edition of the Nerra Network — the shows you chose, "
        "in your order, anchored by Mira. Private feed: don't share this "
        "URL; it is your subscription."
    )
    fg.language("en")
    fg.podcast.itunes_author("Nerra Network")
    fg.podcast.itunes_image(
        enclosure_url_for(spec.token, COVER_FILENAME) if cover
        else NETWORK_COVER_URL)
    fg.podcast.itunes_block("yes")  # private: never index in directories

    rows = sorted(episodes, key=lambda e: int(e.get("episode_num", 0)),
                  reverse=True)[:PERSONAL_FEED_MAX_EPISODES]
    for row in rows:
        fe = fg.add_entry(order="append")
        num = int(row.get("episode_num", 0))
        date = str(row.get("date") or "")
        fe.id(f"personal-{spec.token[:8]}-ep{num:03d}-{date.replace('-', '')}")
        fe.title(str(row.get("title") or f"Your edition — {date}"))
        fe.description(str(row.get("description") or ""))
        if row.get("notes_html"):
            fe.content(str(row["notes_html"]), type="CDATA")
        try:
            pub = _dt.datetime.fromisoformat(date).replace(
                hour=8, tzinfo=_dt.timezone.utc)
        except ValueError:
            pub = _dt.datetime.now(_dt.timezone.utc)
        fe.pubDate(pub)
        fe.podcast.itunes_episode(num)
        fe.podcast.itunes_duration(int(float(row.get("duration_seconds", 0))))
        fe.enclosure(
            enclosure_url_for(spec.token, str(row.get("filename") or "")),
            str(int(row.get("bytes", 0) or 0)),
            "audio/mpeg",
        )
    return _with_chapter_tags(
        fg.rss_str(pretty=True).decode("utf-8"), spec.token, rows)


def chapters_filename_for(date_iso: str) -> str:
    """``chapters_YYYYMMDD.json`` — the name the builder uploads beside
    each edition's MP3 (scripts/build_personal_feeds.py)."""
    return f"chapters_{date_iso.replace('-', '')}.json"


def _with_chapter_tags(xml: str, token: str, rows: List[dict]) -> str:
    """Add ``<podcast:chapters>`` to every item that has a date.

    The builder has always uploaded a Podcasting 2.0 chapters file per
    edition, but until the first paid subscriber's feed was inspected
    (2026-09-06) nothing in the RSS pointed at it — so apps showed one
    24-minute block instead of a chapter per show. feedgen's podcast
    extension has no chapters support; post-process like engine.publisher
    does for the network feeds. Best-effort: on any failure the feed is
    returned unchanged rather than empty.
    """
    import xml.etree.ElementTree as ET

    podcast_ns = "https://podcastindex.org/namespace/1.0"
    try:
        ET.register_namespace("podcast", podcast_ns)
        ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        ET.register_namespace("atom", "http://www.w3.org/2005/Atom")
        ET.register_namespace("content", "http://purl.org/rss/1.0/modules/content/")
        root = ET.fromstring(xml.encode("utf-8"))
        channel = root.find("channel")
        if channel is None:
            return xml
        by_guid = {
            f"personal-{token[:8]}-ep{int(r.get('episode_num', 0)):03d}-"
            f"{str(r.get('date') or '').replace('-', '')}": str(r.get("date") or "")
            for r in rows
        }
        transcripts_by_guid = {
            f"personal-{token[:8]}-ep{int(r.get('episode_num', 0)):03d}-"
            f"{str(r.get('date') or '').replace('-', '')}": [
                str(n) for n in (r.get("transcripts") or []) if n]
            for r in rows
        }
        for item in channel.findall("item"):
            guid_el = item.find("guid")
            date = by_guid.get((guid_el.text or "").strip()) if guid_el is not None else None
            if not date:
                continue
            el = ET.SubElement(item, f"{{{podcast_ns}}}chapters")
            el.set("url", enclosure_url_for(token, chapters_filename_for(date)))
            el.set("type", "application/json+chapters")
            for name in transcripts_by_guid.get((guid_el.text or "").strip(), []):
                mime = TRANSCRIPT_TYPES.get(name.rsplit(".", 1)[-1])
                if not mime:
                    continue
                tr = ET.SubElement(item, f"{{{podcast_ns}}}transcript")
                tr.set("url", enclosure_url_for(token, name))
                tr.set("type", mime)
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
            root, encoding="unicode")
    except Exception as exc:  # noqa: BLE001 — a feed without chapters beats no feed
        logger.warning("personal feed: chapter tags skipped (%s)", exc)
        return xml


def prune_episode_state(episodes: List[dict]) -> Tuple[List[dict], List[str]]:
    """Keep the newest N rows; return (kept, filenames_to_delete)."""
    rows = sorted(episodes, key=lambda e: int(e.get("episode_num", 0)),
                  reverse=True)
    kept = rows[:PERSONAL_FEED_MAX_EPISODES]
    dropped = [str(r.get("filename")) for r in rows[PERSONAL_FEED_MAX_EPISODES:]
               if r.get("filename")]
    return kept, dropped


def personal_episode_title(target_date: _dt.date,
                           segments: List[Segment]) -> str:
    """Personal feeds carry no "Ep N:" label (the number lives in the
    itunes:episode tag) — but the 100-char clip rule from engine.titles
    still binds; podcast apps clamp these too."""
    from engine.titles import clip_words

    lead = segments[0].hook or segments[0].episode_title if segments else ""
    title = clip_words(f"{target_date.strftime('%A')} — {lead}", 100)
    return title or f"Your edition — {target_date.isoformat()}"


def personal_chapter_pieces(
    spec: PersonalSpec,
    segments: List[Segment],
    durations: Dict[str, float],
) -> List[Tuple[str, float]]:
    """(title, duration) chapter rows in splice order for build_chapters."""
    from engine.titles import clip_words

    pieces: List[Tuple[str, float]] = [
        ("Good morning from Mira", durations.get("intro", 0.0))]
    if durations.get("local"):   # pre-Sep-13 single-city builds
        pieces.append((f"Your {spec.city} brief", durations["local"]))
    for i, city in enumerate(spec.cities, 1):
        if durations.get(f"local_{i}"):
            pieces.append((f"Your {city} brief", durations[f"local_{i}"]))
    if durations.get("topics"):
        pieces.append(("Your topics", durations["topics"]))
    if durations.get("markets"):
        pieces.append(("Your markets minute", durations["markets"]))
    for i, seg in enumerate(segments):
        lead = durations.get(f"handoff_{i}", 0.0) if i > 0 else 0.0
        pieces.append((
            clip_words(f"{seg.show_name} — {seg.hook or seg.episode_title}", 100),
            lead + durations.get(f"seg_{seg.slug}", 0.0),
        ))
    pieces.append(("Sign-off", durations.get("signoff", 0.0)))
    return pieces


# ---------------------------------------------------------------------------
# Episode notes, transcripts, artwork, transitions (Sep 17 2026 polish)
# ---------------------------------------------------------------------------

#: ``<podcast:transcript type>`` by file extension. JSON is the
#: Podcasting 2.0 shape (segments with startTime/endTime/body/speaker);
#: VTT is what Apple Podcasts and Pocket Casts read.
TRANSCRIPT_TYPES = {"json": "application/json", "vtt": "text/vtt"}

_SOURCE_VERBS = (r"reports?|reported|says|said|notes?|noted|confirms?|confirmed|"
                 r"announced|announces|writes|wrote|adds|added")
_NAME = (r"((?:The )?[A-Z][\w&'’-]*(?:\.[A-Z][\w&'’-]*)*"
         r"(?:(?: (?:of|for|and|de|du))? [A-Z][\w&'’-]*(?:\.[A-Z][\w&'’-]*)*){0,4})")
_NAMED_SOURCE_RES = (
    # "CBC News reports …", "TransLink says …", "The City of Vancouver notes …"
    re.compile(r"\b" + _NAME + r" (?:" + _SOURCE_VERBS + r")\b"),
    # "according to Global News", "Per Castanet, …"
    re.compile(r"\b(?i:according to|per) (?:the )?" + _NAME),
)
_NOT_A_SOURCE = {"the", "today", "tomorrow", "mira", "it", "this", "that",
                 "there", "monday", "tuesday", "wednesday", "thursday",
                 "friday", "saturday", "sunday"}
#: A credited "source" that starts with one of these is the generic kind
#: ("Local reports say", "Officials confirmed") — not an outlet.
_GENERIC_LEAD = {"local", "sources", "reports", "officials", "residents",
                 "some", "several", "many", "one", "a", "an", "our", "your",
                 "weather", "forecasters", "experts", "analysts", "critics"}
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def named_sources(text: str, limit: int = 6) -> List[str]:
    """Outlets and institutions the brief credits by name ("CBC News
    reports", "according to TransLink"), in order of first mention. The
    generic phrasings the prompt forbids ("local reports say") are
    already screened by :func:`generic_attributions`; this collects the
    real ones so the episode notes can list them as text — the same
    honesty rule Mira follows aloud, made visible."""
    out: List[str] = []
    for sentence in _SENTENCE_SPLIT_RE.split(text or ""):
        for rx in _NAMED_SOURCE_RES:
            for m in rx.finditer(sentence):
                name = m.group(1).strip(" .,")
                key = name.lower()
                lead = key.split(" ", 1)[0]
                if lead == "the" and " " in key:
                    lead = key.split(" ", 2)[1]
                if key in _NOT_A_SOURCE or lead in _GENERIC_LEAD:
                    continue
                if len(name) < 3 or key in {x.lower() for x in out}:
                    continue
                out.append(name)
    return out[:limit]


def _hms(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def episode_notes(
    spec: PersonalSpec,
    chapters: List[dict],
    *,
    sources_by_chapter: Optional[Dict[str, List[str]]] = None,
    segments: Optional[List[Segment]] = None,
) -> Tuple[str, str]:
    """(plain description, HTML notes) for one edition.

    Until now the item description was one line ("Your personal Nerra
    edition: SpaceX Daily, Tesla Shorts Time…"). Podcast apps show the
    notes on the episode screen, so they now carry the running order
    with timestamps, the outlets each brief credits, and where to change
    the lineup. Plain and HTML variants: apps that ignore
    ``content:encoded`` still get the running order as text.
    """
    who = f"{spec.first_name}'s" if spec.first_name else "Your"
    lines: List[str] = []
    html: List[str] = [f"<p><strong>{_esc(who)} edition, in your order.</strong></p>", "<ol>"]
    for ch in chapters:
        t = _hms(float(ch.get("startTime", 0.0)))
        title = str(ch.get("title") or "")
        src = (sources_by_chapter or {}).get(title) or []
        tail = f" (sources: {', '.join(src)})" if src else ""
        lines.append(f"{t} {title}{tail}")
        html.append(
            f"<li><strong>{t}</strong> {_esc(title)}"
            + (f"<br><small>Sources named: {_esc(', '.join(src))}</small>" if src else "")
            + "</li>")
    html.append("</ol>")
    shows = [s.show_name for s in (segments or [])]
    if shows:
        html.append(f"<p>Shows today: {_esc(', '.join(shows))}.</p>")
    html.append(
        '<p>Change your shows, order, cities and topics any time at '
        '<a href="https://nerranetwork.com/account.html">nerranetwork.com/account</a>. '
        "Mira and the shows use AI voice synthesis; the editorial selection is ours.</p>")
    plain = f"{who} edition, in your order. " + " · ".join(lines)
    return plain, "\n".join(html)


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def transcript_filenames_for(date_iso: str) -> Tuple[str, str]:
    """(``transcript_YYYYMMDD.json``, ``transcript_YYYYMMDD.vtt``)."""
    stem = f"transcript_{date_iso.replace('-', '')}"
    return f"{stem}.json", f"{stem}.vtt"


def transcript_entries(
    pieces: List[Tuple[str, float, Optional[str], Optional[dict], Optional[float]]],
) -> List[dict]:
    """Flatten the spliced edition into timed cues.

    *pieces* are ``(speaker, duration, spoken_text, whisper_transcript,
    cut_seconds)`` in splice order. Mira's pieces are TTS text — one cue
    spanning the piece (we know what she said, not when each word
    landed). Show segments carry the committed Whisper transcript; its
    cues are offset to the edition timeline and stop at the promo cut,
    exactly like the audio. Every show pins ``voice_intro_delay`` 0.0,
    so raw-voice time is final-MP3 time (see discover_segments).
    """
    cues: List[dict] = []
    cursor = 0.0
    for speaker, duration, text, transcript, cut in pieces:
        if text:
            cues.append({"startTime": round(cursor, 2),
                         "endTime": round(cursor + duration, 2),
                         "speaker": speaker, "body": text.strip()})
        elif transcript and isinstance(transcript.get("segments"), list):
            for seg in transcript["segments"]:
                try:
                    start, end = float(seg["start"]), float(seg["end"])
                except (KeyError, TypeError, ValueError):
                    continue
                if cut is not None and start >= cut:
                    break
                body = str(seg.get("text") or "").strip()
                if not body:
                    continue
                cues.append({"startTime": round(cursor + start, 2),
                             "endTime": round(cursor + min(end, cut if cut else end), 2),
                             "speaker": speaker, "body": body})
        cursor += max(0.0, float(duration))
    return cues


def transcript_json(cues: List[dict]) -> dict:
    return {"version": "1.0.0", "segments": cues}


def _vtt_time(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def transcript_vtt(cues: List[dict]) -> str:
    out = ["WEBVTT", ""]
    for i, c in enumerate(cues, 1):
        out.append(str(i))
        out.append(f"{_vtt_time(c['startTime'])} --> {_vtt_time(c['endTime'])}")
        out.append(f"<v {c.get('speaker') or 'Speaker'}>{c['body']}")
        out.append("")
    return "\n".join(out)


def cover_signature(spec: PersonalSpec) -> str:
    """What the artwork depends on — re-render only when this changes."""
    return f"v1|{spec.first_name}|{spec.city}"


def render_cover(spec: PersonalSpec, base: Path, out: Path, size: int = 1400) -> bool:
    """The subscriber's own artwork: the network cover with a band naming
    the feed ("Patrick's Nerra Daily · Vancouver, BC"). 1400 px square
    (Apple's minimum) JPEG. Returns False — and the feed keeps the
    network cover — when Pillow or a font is missing; artwork is never a
    reason to fail a build."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.info("cover: Pillow missing — network cover kept")
        return False
    try:
        im = Image.open(base).convert("RGB").resize((size, size), Image.LANCZOS)
        draw = ImageDraw.Draw(im, "RGBA")
        band_h = int(size * 0.22)
        draw.rectangle([0, size - band_h, size, size], fill=(8, 10, 20, 214))
        font_big = _font(int(size * 0.075))
        font_small = _font(int(size * 0.045))
        who = f"{spec.first_name}'s" if spec.first_name else "Your"
        title = f"{who} Nerra Daily"
        sub = spec.city or "Personal edition"
        x = int(size * 0.06)
        y = size - band_h + int(band_h * 0.18)
        draw.text((x, y), title, font=font_big, fill=(255, 255, 255, 255))
        draw.text((x, y + int(size * 0.1)), sub, font=font_small, fill=(200, 208, 224, 255))
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out, "JPEG", quality=88, optimize=True)
        return True
    except Exception as exc:  # noqa: BLE001 — never sink a build over art
        logger.info("cover: render failed (%s) — network cover kept", exc)
        return False


def _font(px: int):
    from PIL import ImageFont

    for cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                 "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        if Path(cand).exists():
            return ImageFont.truetype(cand, px)
    return ImageFont.load_default()


#: Every published show targets -16 LUFS integrated (engine.audio's final
#: mix). A segment further than this from target gets a static gain so
#: the edition doesn't jump between shows — measured on 2026-09-17: nine
#: shows within ±0.4 LU, Unintended Consequences at -25.3 (its voice-only
#: path never had the final loudnorm). Static gain, not a dynamic
#: loudnorm: it preserves the show's own dynamics and costs one encode.
SEGMENT_TARGET_LUFS = -16.0
SEGMENT_LOUDNESS_TOLERANCE_LU = 1.5
SEGMENT_MAX_GAIN_DB = 12.0

_LUFS_RE = re.compile(r"I:\s+(-?[\d.]+) LUFS")


def measure_lufs(path: Path, *, timeout: int = 600) -> Optional[float]:
    """Integrated loudness via ffmpeg's ebur128 (decode-only: seconds per
    ten-minute segment). None when ffmpeg can't say."""
    import subprocess

    try:
        proc = subprocess.run(
            ["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=timeout)
    except Exception:  # noqa: BLE001
        return None
    tail = proc.stderr[proc.stderr.rfind("Integrated loudness"):]
    m = _LUFS_RE.search(tail)
    return float(m.group(1)) if m else None


def segment_gain_db(measured: Optional[float]) -> float:
    """0.0 when the segment is within tolerance (or unmeasured); else the
    static gain that brings it to target, clamped to ±SEGMENT_MAX_GAIN_DB."""
    if measured is None or measured <= -60:
        return 0.0
    delta = SEGMENT_TARGET_LUFS - measured
    if abs(delta) <= SEGMENT_LOUDNESS_TOLERANCE_LU:
        return 0.0
    return max(-SEGMENT_MAX_GAIN_DB, min(SEGMENT_MAX_GAIN_DB, round(delta, 1)))


def segment_gain_cmd(in_path: Path, out_path: Path, gain_db: float) -> List[str]:
    """Apply a static gain with a true-peak limiter so a lifted segment
    can't clip (limit -1 dBTP, matching the network's loudnorm TP)."""
    from engine.daily_edition import SEGMENT_ENCODE_ARGS

    return (["ffmpeg", "-y", "-i", str(in_path), "-af",
             f"volume={gain_db:+.1f}dB,alimiter=limit=0.891:level=false"]
            + SEGMENT_ENCODE_ARGS + [str(out_path)])


def sting_cmd(out_path: Path) -> List[str]:
    """The network's two-tone transition chime (engine.audio's sting),
    rendered straight into the splice format — 44.1 kHz stereo, the
    shared VBR setting — with a breath either side, so it stream-copies
    into the edition ahead of each of Mira's hand-offs and her sign-off.
    Quiet by design (-18 dB): a marker, not a jingle."""
    from engine.daily_edition import SEGMENT_ENCODE_ARGS

    return (["ffmpeg", "-y",
             "-f", "lavfi", "-i", "sine=frequency=880:duration=0.15",
             "-f", "lavfi", "-i", "sine=frequency=1320:duration=0.15",
             "-filter_complex",
             "[0][1]amix=inputs=2,afade=t=in:d=0.05,afade=t=out:st=0.1:d=0.05,"
             "volume=-18dB,adelay=450|450,apad=pad_dur=0.35,"
             "aformat=channel_layouts=stereo[out]",
             "-map", "[out]"]
            + SEGMENT_ENCODE_ARGS + [str(out_path)])


__all__ = [
    "DEFAULT_ADDONS",
    "MIRA_PERSONAL_DISCLOSURE",
    "PERSONAL_ADDONS",
    "PERSONAL_FEED_BASE",
    "PERSONAL_FEED_MAX_EPISODES",
    "PERSONAL_R2_PREFIX",
    "PERSONAL_SHOW_SLUGS",
    "PERSONAL_EXTRA_SHOW_SLUGS",
    "personal_edition_spec",
    "TIER_LIMITS",
    "PersonalSpec",
    "addons_for_tier",
    "build_chapters",
    "build_local_brief_prompt",
    "build_markets_line",
    "needs_research_call",
    "wants_local_brief",
    "build_personal_feed_xml",
    "build_personal_links_prompt",
    "build_topics_prompt",
    "brief_max_words",
    "chapters_filename_for",
    "cover_signature",
    "episode_notes",
    "measure_lufs",
    "named_sources",
    "render_cover",
    "segment_gain_cmd",
    "segment_gain_db",
    "sting_cmd",
    "transcript_entries",
    "transcript_filenames_for",
    "transcript_json",
    "transcript_vtt",
    "generic_attributions",
    "enclosure_url_for",
    "ensure_weather_opener",
    "fallback_personal_links",
    "feed_url_for",
    "fetch_weather_line",
    "format_weather_line",
    "parse_local_brief",
    "personal_chapter_pieces",
    "personal_episode_title",
    "prune_episode_state",
    "tier_limits",
    "upgrade_nudge_line",
    "wants_topics_brief",
    "validate_spec",
]
