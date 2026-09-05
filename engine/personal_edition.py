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
from dataclasses import dataclass
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

#: The only shows a personal lineup may contain — the EN edition roster.
PERSONAL_SHOW_SLUGS: Tuple[str, ...] = EDITIONS["en"].lineup

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
#: ``tier`` is the minimum tier the add-on runs on. The four location
#: add-ons are researched by Mira for the member's chosen location
#: (weather = measured Open-Meteo data; news/events/traffic = one
#: web-search-grounded Grok call under the field-note honesty rules —
#: an unverifiable section is omitted, an unverifiable day SKIPs).
#: ``markets`` is deterministic — read from the pipeline's committed
#: price caches (api/tsla.json, api/spcx.json), zero LLM cost.
PERSONAL_ADDONS: Dict[str, Dict[str, str]] = {
    "weather":    {"tier": "personal_local", "label": "Local weather"},
    "local_news": {"tier": "personal_local", "label": "Local news"},
    "events":     {"tier": "personal_local", "label": "Local events"},
    "traffic":    {"tier": "personal_local", "label": "Traffic & transit"},
    "markets":    {"tier": "personal",       "label": "Markets minute"},
}

#: What runs when a member has never touched the toggles — matches the
#: pre-add-on behavior exactly (local tier: weather + news + events; no
#: traffic, no markets), so shipping this feature changes nobody's
#: edition until they opt in.
DEFAULT_ADDONS: Tuple[str, ...] = ("weather", "local_news", "events")


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
    city: str = ""
    #: Chosen add-on ids (validated subset of PERSONAL_ADDONS, filtered
    #: to the spec's tier). None = the member never saved a choice →
    #: DEFAULT_ADDONS applies at build time.
    addons: Optional[List[str]] = None
    #: Resolved lazily by the builder (Open-Meteo geocoding, cached).
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    def effective_addons(self) -> List[str]:
        chosen = DEFAULT_ADDONS if self.addons is None else self.addons
        allowed = set(addons_for_tier(self.tier))
        return [a for a in chosen if a in allowed]


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
    city = str(raw.get("city") or "").strip()[:80]
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
                        first_name=first_name, city=city, addons=addons)


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
_ADDON_RESEARCH_LINES = {
    "local_news": (
        "- ONE local news item that a resident would actually care about "
        "(a decision, an opening, a change — not crime-blotter filler)."),
    "events": (
        "- ONE notable local event coming up (a festival, a talk, a game, "
        "a market)."),
    "traffic": (
        "- ONE current traffic or transit disruption that changes how "
        "residents get around this week (a closure, a strike, a major "
        "delay, a new line or detour) — only if a real, current one is "
        "reported; ordinary congestion is not an item."),
}


def build_local_brief_prompt(
    root: Path,
    spec: PersonalSpec,
    target_date: _dt.date,
    weather_line: str,
) -> str:
    template = (root / "shows" / "prompts" / "nerra_personal_local.txt"
                ).read_text(encoding="utf-8")
    addons = spec.effective_addons()
    if "weather" in addons and weather_line:
        weather_block = (
            "Measured weather (from Open-Meteo — read it naturally, never "
            "alter the numbers):\n" + weather_line)
    else:
        weather_block = "(The listener has no weather section today.)"
    research_requests = "\n".join(
        _ADDON_RESEARCH_LINES[a] for a in addons if a in _ADDON_RESEARCH_LINES)
    return template.format(
        date_spoken=target_date.strftime("%A, %B %-d, %Y"),
        city=spec.city,
        listener_name=spec.first_name or "the listener",
        weather_block=weather_block,
        research_requests=research_requests
        or "(No researched sections requested today.)",
    )


def wants_local_brief(spec: PersonalSpec) -> bool:
    """A local brief runs only when a location add-on is actually on."""
    addons = set(spec.effective_addons())
    return bool(spec.city) and bool(
        addons & ({"weather"} | set(_ADDON_RESEARCH_LINES)))


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


def parse_local_brief(text: str) -> Optional[str]:
    """Same honesty contract as Mira's field note: SKIP or an implausible
    length means no local segment today — never filler."""
    cleaned = sanitize_spoken(text or "")
    if not cleaned or "SKIP" in cleaned[:20].upper():
        return None
    words = len(cleaned.split())
    if not 30 <= words <= 220:
        logger.warning("local brief rejected at %d words", words)
        return None
    return cleaned


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


def fetch_weather_line(spec: PersonalSpec, *, timeout: int = 15) -> str:
    """Open-Meteo geocode (once, cached on the spec) + daily forecast.
    Free, keyless, best-effort — "" on any failure."""
    import requests

    try:
        if spec.latitude is None or spec.longitude is None:
            geo = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": spec.city, "count": 1}, timeout=timeout,
            ).json()
            results = geo.get("results") or []
            if not results:
                return ""
            spec.latitude = float(results[0]["latitude"])
            spec.longitude = float(results[0]["longitude"])
        forecast = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": spec.latitude, "longitude": spec.longitude,
                "daily": "temperature_2m_max,temperature_2m_min,weather_code",
                "forecast_days": 1, "timezone": "auto",
            }, timeout=timeout,
        ).json()
        return format_weather_line(spec.city, forecast.get("daily") or {})
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


def build_personal_feed_xml(
    spec: PersonalSpec,
    episodes: List[dict],
) -> str:
    """Personal RSS from the subscriber's episode state (newest first).

    *episodes* rows: {episode_num, date (ISO), title, description,
    filename, duration_seconds, bytes}. GUIDs are deterministic
    (``personal-<token8>-epNNN-date``) so a rebuild never re-notifies a
    podcast app.
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
        "https://nerranetwork.com/assets/covers/nerra-daily.jpg")
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
    return fg.rss_str(pretty=True).decode("utf-8")


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
    if durations.get("local"):
        pieces.append((f"Your {spec.city} brief", durations["local"]))
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


__all__ = [
    "DEFAULT_ADDONS",
    "MIRA_PERSONAL_DISCLOSURE",
    "PERSONAL_ADDONS",
    "PERSONAL_FEED_BASE",
    "PERSONAL_FEED_MAX_EPISODES",
    "PERSONAL_R2_PREFIX",
    "PERSONAL_SHOW_SLUGS",
    "PersonalSpec",
    "addons_for_tier",
    "build_chapters",
    "build_local_brief_prompt",
    "build_markets_line",
    "needs_research_call",
    "wants_local_brief",
    "build_personal_feed_xml",
    "build_personal_links_prompt",
    "enclosure_url_for",
    "fallback_personal_links",
    "feed_url_for",
    "fetch_weather_line",
    "format_weather_line",
    "parse_local_brief",
    "personal_chapter_pieces",
    "personal_episode_title",
    "prune_episode_state",
    "validate_spec",
]
