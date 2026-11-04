"""One owner for the word a surface uses for a show's cadence — and, since
Nov 3 2026, for the length a surface promises.

Oct 1 2026: the Shorts funnel comment said "Subscribe for daily episodes"
on every show and the X follow line said "for daily episodes" — on The DP
Pod (Monday), Peptides (Thursday), Longevity (Wednesday), Collingwood
(Friday) and Offshore North (Monday) that is a promise the show does not
keep. The registry ``schedule`` string (``shows/network_meta.yaml``) is the
public cadence (CLAUDE.md: it is one of the six places a cadence lives);
``engine.blog.next_episode_placeholder`` already reads it for the blog.
"""
from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def cadence_adjective(schedule: str) -> str:
    """"daily" / "weekly" / "new" from a registry schedule string, never a
    cadence the string does not support."""
    sched = (schedule or "").strip().lower()
    if not sched:
        return "new"
    if sched.startswith("daily") or sched.startswith("every day"):
        return "daily"
    if "weekly" in sched or any(d in sched for d in _DAYS):
        return "weekly"
    if "weekday" in sched:
        return "weekday"
    return "new"


def schedule_for_slug(slug: str) -> str:
    """The registry schedule string for a show, "" when unknown."""
    try:
        from generate_html import NETWORK_SHOWS  # type: ignore
        return str((NETWORK_SHOWS.get(slug) or {}).get("schedule") or "")
    except Exception:  # noqa: BLE001 — the registry is a site-layer import
        return ""


def episodes_phrase(slug: str) -> str:
    """"daily episodes" / "weekly episodes" / "new episodes"."""
    return f"{cadence_adjective(schedule_for_slug(slug))} episodes"


# ---------------------------------------------------------------------------
# Promised length (Nov 3 2026)
# ---------------------------------------------------------------------------
#
# Seven shows promised minutes they did not deliver — median audio over the
# last 14 episodes: Unintended Consequences 10.8 vs "~15-18 min", Finansy
# Prosto 6.3 vs ~12, Privet Russian 4.8 vs ~10, Env Intel 7.0 vs ~10,
# Models & Agents for Beginners 8.3 vs ~10, Top World 9.3 vs "about twelve
# minutes", Tesla 9.2 vs ~15 — and nothing read the drift. The length a
# surface promises is COMPUTED from the show's own committed episodes, never
# typed. Until the operator says yes for a show it stays the registry
# string, and the daily audit warns (never fails) when a public string
# drifts from what the show delivers (scripts/check_promised_lengths.py).

#: How many of a show's newest episodes the median reads.
LENGTH_WINDOW_EPISODES = 14
#: Under this many dated episodes the registry string stands.
LENGTH_MIN_EPISODES = 5
#: A stated length further than this from the median is drift.
LENGTH_DRIFT_TOLERANCE = 0.25
#: Shows whose published ``episode_length`` is the computed string. Ships
#: EMPTY on purpose: Tesla's "~15 min" is a standing ledger decision and the
#: Russian shows wait on the operator's Russian decision — a show joins this
#: set on the operator's yes, and its pages then state what it delivers.
COMPUTED_LENGTH_SHOWS: frozenset = frozenset()
#: The public strings the drift check reads (plus ``episode_length`` for a
#: show still on its typed string).
LENGTH_STRING_FIELDS = ("rss_description", "description_long", "about_text")

_ROOT = Path(__file__).resolve().parent.parent
_DIGEST_DATE_RE = re.compile(r"_Ep0*(\d+)_(\d{8})\.md$")
_METRICS_RE = re.compile(r"^metrics_ep0*(\d+)\.json$")


def _show_yaml(slug: str, root: Path) -> dict:
    try:
        import yaml
        data = yaml.safe_load((root / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — no YAML (a registry-only show)
        return {}
    return data if isinstance(data, dict) else {}


def _show_output_dir(slug: str, root: Path) -> Optional[Path]:
    """``episode.output_dir`` from the show YAML; None for a registry-only
    show (Nerra Daily) or an unreadable file."""
    out = (_show_yaml(slug, root).get("episode") or {}).get("output_dir")
    return (root / str(out)) if out else None


def recent_audio_minutes(slug: str, root: Optional[Path] = None,
                         window: int = LENGTH_WINDOW_EPISODES) -> List[float]:
    """Audio minutes of the show's newest *window* episodes.

    Each ``metrics_ep*.json`` is dated by its sibling digest's filename
    (``…_EpNNN_YYYYMMDD.md``, top level or ``members/``) — never by mtime,
    which is the checkout time on every CI runner. A metrics file with no
    dated digest, or no ``audio_duration_s``, is not counted."""
    root = Path(root) if root else _ROOT
    out_dir = _show_output_dir(slug, root)
    if out_dir is None or not out_dir.is_dir():
        return []
    dates: Dict[int, str] = {}
    for md in list(out_dir.glob("*.md")) + list((out_dir / "members").glob("*.md")):
        m = _DIGEST_DATE_RE.search(md.name)
        if m:
            dates.setdefault(int(m.group(1)), m.group(2))
    rows: List[Tuple[str, int, float]] = []
    for mf in out_dir.glob("metrics_ep*.json"):
        m = _METRICS_RE.match(mf.name)
        if not m or int(m.group(1)) not in dates:
            continue
        try:
            counters = (json.loads(mf.read_text(encoding="utf-8")) or {}).get("counters") or {}
            seconds = float(counters.get("audio_duration_s") or 0)
        except (OSError, ValueError, TypeError, AttributeError):
            continue
        if seconds > 0:
            ep = int(m.group(1))
            rows.append((dates[ep], ep, seconds / 60.0))
    rows.sort()
    return [minutes for _, _, minutes in rows[-window:]]


def median_episode_minutes(slug: str, root: Optional[Path] = None) -> Optional[float]:
    """Median audio minutes over the newest episodes; None under
    ``LENGTH_MIN_EPISODES`` (unmeasured, never 0)."""
    minutes = recent_audio_minutes(slug, root)
    if len(minutes) < LENGTH_MIN_EPISODES:
        return None
    return float(statistics.median(minutes))


def registry_episode_length(slug: str) -> str:
    """The registry's typed ``episode_length``, "" when unknown."""
    try:
        from generate_html import NETWORK_SHOWS  # type: ignore
        return str((NETWORK_SHOWS.get(slug) or {}).get("episode_length") or "")
    except Exception:  # noqa: BLE001 — the registry is a site-layer import
        return ""


def episode_length_for_slug(slug: str, registry: Optional[str] = None,
                            root: Optional[Path] = None) -> str:
    """``"~N min"`` from the median audio of the show's last 14 committed
    episodes; the registry string under ``LENGTH_MIN_EPISODES``."""
    median = median_episode_minutes(slug, root)
    if median is None:
        return registry if registry is not None else registry_episode_length(slug)
    return f"~{max(1, int(median + 0.5))} min"


def published_episode_length(slug: str, registry: str, root: Optional[Path] = None,
                             computed: Optional[Iterable[str]] = None) -> str:
    """The length a page prints: computed for a show in
    ``COMPUTED_LENGTH_SHOWS`` (or *computed*), else the registry string
    unchanged — nothing is read from disk for a show that has not opted in."""
    opted = COMPUTED_LENGTH_SHOWS if computed is None else frozenset(computed)
    if slug not in opted:
        return registry
    return episode_length_for_slug(slug, registry=registry, root=root)


_UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
          "seven": 7, "eight": 8, "nine": 9}
_TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
          "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
          "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60}
_NUM = (r"(?:\d+(?:\.\d+)?|(?:" + "|".join(_TENS) + r")(?:[- ](?:" + "|".join(_UNITS)
        + r"))?|" + "|".join(sorted(_TEENS, key=len, reverse=True)) + "|"
        + "|".join(_UNITS) + ")")
_LENGTH_NOUNS = (r"episodes?|briefings?|brief|shows?|podcasts?|digests?|editions?|"
                 r"reads?|listens?|round-?ups?|daily")
#: Only shapes that state an episode's length: "~10-12 min", "about twelve
#: minutes", "a 10-minute briefing". "sleep in 20-minute fragments" states
#: no episode length and does not match.
_STATED_LENGTH_RES = (
    re.compile(rf"~\s*(?P<lo>{_NUM})(?:\s*[-–]\s*(?P<hi>{_NUM}))?\s*min", re.I),
    re.compile(rf"\b(?:about|around|roughly|approximately|nearly|under|over|just)\s+"
               rf"(?P<lo>{_NUM})(?:\s*(?:to|[-–])\s*(?P<hi>{_NUM}))?\s+minutes?\b", re.I),
    re.compile(rf"\b(?P<lo>{_NUM})(?:\s*[-–]\s*(?P<hi>{_NUM}))?[- ]minute\s+"
               rf"(?:{_LENGTH_NOUNS})\b", re.I),
)


def _number(token: str) -> Optional[float]:
    token = (token or "").strip().lower()
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        pass
    total = 0
    for part in re.split(r"[- ]", token):
        value = _UNITS.get(part) or _TEENS.get(part) or _TENS.get(part)
        if value is None:
            return None
        total += value
    return float(total)


def stated_minutes(text: str) -> List[Tuple[float, float, str]]:
    """Every episode length *text* states, as ``(low, high, phrase)``."""
    found: List[Tuple[float, float, str]] = []
    for pattern in _STATED_LENGTH_RES:
        for m in pattern.finditer(text or ""):
            lo = _number(m.group("lo"))
            hi = _number(m.group("hi")) if m.group("hi") else lo
            if lo is None or hi is None:
                continue
            found.append((min(lo, hi), max(lo, hi), m.group(0).strip()))
    return found


def length_drift(fields: Dict[str, str], median: float,
                 tolerance: float = LENGTH_DRIFT_TOLERANCE) -> List[dict]:
    """The lengths *fields* state that sit further than *tolerance* from
    *median* (a range is judged by its nearest end)."""
    out: List[dict] = []
    if not median or median <= 0:
        return out
    for field_name, text in fields.items():
        for lo, hi, phrase in stated_minutes(str(text or "")):
            nearest = min(max(median, lo), hi)
            off = abs(nearest - median) / median
            if off > tolerance:
                out.append({"field": field_name, "phrase": phrase,
                            "stated": [lo, hi], "median_min": round(median, 1),
                            "off_pct": round(100 * off)})
    return out


def length_drift_report(root: Optional[Path] = None,
                        registry: Optional[Dict[str, dict]] = None) -> List[dict]:
    """Every public string that promises a length the show does not
    deliver: ``rss_description`` (show YAML), ``description_long`` /
    ``about_text`` and — for a show still on its typed string —
    ``episode_length`` (the registry)."""
    root = Path(root) if root else _ROOT
    if registry is None:
        try:
            from generate_html import NETWORK_SHOWS  # type: ignore
            registry = NETWORK_SHOWS
        except Exception:  # noqa: BLE001 — the YAML half still runs
            registry = {}
    slugs = sorted({p.stem for p in (root / "shows").glob("*.yaml")
                    if not p.stem.startswith("_")} | set(registry))
    report: List[dict] = []
    for slug in slugs:
        median = median_episode_minutes(slug, root)
        if median is None:
            continue
        entry = registry.get(slug) or {}
        fields: Dict[str, str] = {
            "rss_description": str((_show_yaml(slug, root).get("publishing") or {})
                                   .get("rss_description") or ""),
        }
        for name in LENGTH_STRING_FIELDS[1:]:
            fields[name] = str(entry.get(name) or "")
        if slug not in COMPUTED_LENGTH_SHOWS:
            fields["episode_length"] = str(entry.get("episode_length") or "")
        for row in length_drift(fields, median):
            report.append({"show": slug, **row})
    return report


__all__ = [
    "cadence_adjective", "schedule_for_slug", "episodes_phrase",
    "COMPUTED_LENGTH_SHOWS", "LENGTH_DRIFT_TOLERANCE", "LENGTH_MIN_EPISODES",
    "LENGTH_STRING_FIELDS", "LENGTH_WINDOW_EPISODES", "episode_length_for_slug",
    "length_drift", "length_drift_report", "median_episode_minutes",
    "published_episode_length", "recent_audio_minutes", "registry_episode_length",
    "stated_minutes",
]
