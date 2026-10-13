"""Who a show publishes for — public, members-only, or public one weekday.

Oct 13 2026, operator-directed: some shows will publish only for Nerra
Personal members who have them in their lineup, some will publish publicly
once a week with the daily episodes for members, and new shows may launch
members-only. This module is the ONE place that decides, per show and per
day, whether an episode is public, and the one place that knows where a
members-only episode lives. ``shows/<slug>.yaml``'s ``access:`` block
(:class:`engine.config.AccessConfig`) is the setting; ``public`` is the
default and leaves every show exactly as it was.

How a members-only day runs (``run_show.py``):

1. **Demand first, before any spend.** The Worker's
   ``GET /api/admin/show-demand`` counts the paying members whose lineup
   carries each show (no names, emails or feed tokens — counts only). Below
   ``access.min_members`` the run skips with ``no_member_demand`` and costs
   nothing. When demand cannot be read (no token, Worker down) the run
   PROCEEDS: a paying member may be waiting, and an unneeded episode costs
   cents while a missing one costs a subscriber.
2. **Produced like any episode, published to nobody.** Fetch, digest,
   script, TTS, mix and chapters run unchanged. At the rehearsal stop the
   audio goes to the PRIVATE bucket (``PERSONAL_R2_BUCKET``, default
   ``nerra-personal``, key ``shows/<slug>/<file>.mp3``) and the episode's
   text artifacts move into ``digests/<dir>/members/``. Every public
   surface — blog, show page, claims pages, search index, content lake,
   sibling reads, the audit's episode scan — reads the show directory's
   TOP level, so a members episode is off all of them by construction
   rather than by a filter each surface must remember. The RSS feed,
   summaries JSON, YouTube, X, newsletter and directory pings sit after
   the rehearsal stop and are never reached.
3. **Members get it inside their Personal edition.** The episode is
   recorded in ``members/episodes.json`` (the ledger); the Personal
   builder discovers members episodes from it and downloads the audio
   from the private bucket. Nerra Daily never splices one.

Episode numbers continue across public and members episodes (the ledger is
a second numbering source), so a public-weekly show's public feed has
gaps — normal for a podcast feed, never a reused GUID.

The written text of a members episode stays in this (public) repository —
the operator's decision of 2026-10-13: memory, story dedup and the claims
gate keep working unchanged, and only the audio is private.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ACCESS_MODES = ("public", "members_only", "public_weekly")

#: Today's access for one show: an episode either publishes or is for members.
PUBLIC = "public"
MEMBERS = "members"

MEMBERS_SUBDIR = "members"
LEDGER_NAME = "episodes.json"

PRIVATE_BUCKET_ENV = "PERSONAL_R2_BUCKET"
PRIVATE_BUCKET_DEFAULT = "nerra-personal"
PRIVATE_KEY_PREFIX = "shows"
#: A summaries-style ``audio_url`` for audio nobody can fetch without R2
#: credentials. Never an https URL: a members episode has no public address.
PRIVATE_URL_SCHEME = "r2-private://"

API_BASE_ENV = "PERSONAL_API_BASE"
API_BASE_DEFAULT = "https://api.nerranetwork.com"
#: Counts-only token (the Worker accepts it on /api/admin/show-demand and
#: nowhere else); the full admin token also works.
DEMAND_TOKEN_ENVS = ("PERSONAL_DEMAND_TOKEN", "PERSONAL_ADMIN_TOKEN")

#: Daily audit RSS-freshness limit for a public-weekly show's PUBLIC feed:
#: one missed public day plus slack, the band the Monday weeklies use.
PUBLIC_WEEKLY_FEED_MAX_HOURS = 240

WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                 "Saturday", "Sunday")


# ---------------------------------------------------------------------------
# The setting
# ---------------------------------------------------------------------------

def access_mode(config: Any) -> str:
    """The show's validated ``access.mode``.

    An unknown mode RAISES: a typo such as ``members-only`` must stop the
    run, never fall back to publishing a gated show publicly.
    """
    access = getattr(config, "access", None)
    mode = str(getattr(access, "mode", "public") or "public").strip()
    if mode not in ACCESS_MODES:
        raise ValueError(
            f"{getattr(config, 'slug', '?')}: access.mode {mode!r} is not one of "
            f"{', '.join(ACCESS_MODES)} — refusing to guess whether this show "
            "may publish publicly"
        )
    return mode


def public_weekday(config: Any) -> int:
    access = getattr(config, "access", None)
    day = int(getattr(access, "public_weekday", 0) or 0)
    if not 0 <= day <= 6:
        raise ValueError(f"{getattr(config, 'slug', '?')}: access.public_weekday "
                         f"{day} is not 0-6 (0 = Monday)")
    return day


def min_members(config: Any) -> int:
    access = getattr(config, "access", None)
    return max(0, int(getattr(access, "min_members", 1) or 0))


def is_gated(config: Any) -> bool:
    """True when some or all of the show's episodes are for members."""
    return access_mode(config) != "public"


def is_public_on(config: Any, day: dt.date) -> bool:
    """Whether the show's episode for *day* publishes publicly."""
    mode = access_mode(config)
    if mode == "public":
        return True
    if mode == "members_only":
        return False
    return day.weekday() == public_weekday(config)


def todays_access(config: Any, day: dt.date) -> str:
    return PUBLIC if is_public_on(config, day) else MEMBERS


def describe(config: Any) -> str:
    """One plain line for logs and the site ("Members only", …)."""
    mode = access_mode(config)
    if mode == "members_only":
        return "Members only"
    if mode == "public_weekly":
        return (f"Free every {WEEKDAY_NAMES[public_weekday(config)]}; "
                "daily for members")
    return "Public"


# ---------------------------------------------------------------------------
# Demand
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DemandDecision:
    run: bool
    members: Optional[int]
    reason: str


def fetch_show_demand(*, timeout: float = 20.0) -> Optional[Dict[str, int]]:
    """Paying members per show from the Worker, or ``None`` when unknown.

    ``None`` (no token, network error, a non-200, a malformed body) is
    deliberately distinct from ``{}`` (the Worker answered: nobody has
    chosen anything) — the gate proceeds on the first and skips on the
    second.
    """
    token = ""
    for env in DEMAND_TOKEN_ENVS:
        token = (os.environ.get(env) or "").strip()
        if token:
            break
    if not token:
        logger.warning("show demand: no %s set — demand is unknown",
                       " / ".join(DEMAND_TOKEN_ENVS))
        return None
    base = (os.environ.get(API_BASE_ENV) or API_BASE_DEFAULT).rstrip("/")
    try:
        import requests

        resp = requests.get(f"{base}/api/admin/show-demand",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=timeout)
        if resp.status_code != 200:
            logger.warning("show demand: HTTP %s — demand is unknown", resp.status_code)
            return None
        body = resp.json()
    except Exception as exc:  # noqa: BLE001 — unknown, never fatal
        logger.warning("show demand: %s — demand is unknown", type(exc).__name__)
        return None
    demand = body.get("demand") if isinstance(body, dict) else None
    if not isinstance(demand, dict):
        logger.warning("show demand: malformed reply — demand is unknown")
        return None
    out: Dict[str, int] = {}
    for slug, count in demand.items():
        try:
            out[str(slug)] = max(0, int(count))
        except (TypeError, ValueError):
            continue
    return out


def demand_decision(slug: str, demand: Optional[Dict[str, int]],
                    minimum: int) -> DemandDecision:
    """Whether a members-only day should be produced.

    ``minimum <= 0`` always produces (operator override). Unknown demand
    produces (fail open — see the module docstring). Otherwise the show
    runs when at least *minimum* paying members carry it.
    """
    if minimum <= 0:
        count = None if demand is None else demand.get(slug, 0)
        return DemandDecision(True, count, "min_members_0")
    if demand is None:
        return DemandDecision(True, None, "demand_unknown")
    count = demand.get(slug, 0)
    if count >= minimum:
        return DemandDecision(True, count, "members_selected")
    return DemandDecision(False, count, "no_member_demand")


# ---------------------------------------------------------------------------
# Where a members episode lives
# ---------------------------------------------------------------------------

def members_dir(digests_dir: Path) -> Path:
    return Path(digests_dir) / MEMBERS_SUBDIR


def ledger_path(digests_dir: Path) -> Path:
    return members_dir(digests_dir) / LEDGER_NAME


def load_ledger(digests_dir: Path) -> List[dict]:
    path = ledger_path(digests_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("unreadable members ledger: %s", path)
        return []
    episodes = data.get("episodes") if isinstance(data, dict) else None
    return [e for e in (episodes or []) if isinstance(e, dict)]


def max_members_episode(digests_dir: Path) -> int:
    best = 0
    for entry in load_ledger(digests_dir):
        try:
            best = max(best, int(entry.get("episode_num") or 0))
        except (TypeError, ValueError):
            continue
    return best


def members_entry_for(digests_dir: Path, day: dt.date) -> Optional[dict]:
    """The ledger entry for *day* (the newest when a day was re-made)."""
    iso = day.isoformat()
    hits = [e for e in load_ledger(digests_dir) if e.get("date") == iso]
    return hits[-1] if hits else None


def record_members_episode(digests_dir: Path, entry: dict) -> Path:
    """Add or replace (same episode number) one ledger entry."""
    path = ledger_path(digests_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    episodes = [e for e in load_ledger(digests_dir)
                if e.get("episode_num") != entry.get("episode_num")]
    episodes.append(entry)
    episodes.sort(key=lambda e: (str(e.get("date", "")), int(e.get("episode_num") or 0)))
    path.write_text(json.dumps({
        "_readme": ("Members-only episodes of this show (engine/access.py). "
                    "The audio is in the private Nerra Personal bucket; "
                    "members hear these inside their Personal edition."),
        "episodes": episodes,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def episode_artifact_patterns(prefix: str, episode_num: int, day: dt.date) -> List[str]:
    """This episode's text artifacts — the rehearsal stop's set minus the
    metrics file, which is spend and health accounting, not content."""
    return [
        f"{prefix}_Ep{episode_num:03d}_{day:%Y%m%d}*",
        f"chapters_ep{episode_num:03d}.json",
    ]


def move_episode_artifacts(digests_dir: Path, prefix: str, episode_num: int,
                           day: dt.date) -> List[Path]:
    """Move this episode's artifacts into ``members/``; returns the new paths.

    The MP3 moves too (it is never committed, and the public numbering
    glob must not count it twice — the ledger already does).
    """
    dest_dir = members_dir(digests_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    moved: List[Path] = []
    for pattern in episode_artifact_patterns(prefix, episode_num, day):
        for src in sorted(Path(digests_dir).glob(pattern)):
            if not src.is_file():
                continue
            dest = dest_dir / src.name
            try:
                src.replace(dest)
                moved.append(dest)
            except OSError as exc:
                logger.warning("members: could not move %s (%s)", src.name, exc)
    return moved


def private_bucket() -> str:
    return (os.environ.get(PRIVATE_BUCKET_ENV) or PRIVATE_BUCKET_DEFAULT).strip()


def private_audio_key(slug: str, filename: str) -> str:
    return f"{PRIVATE_KEY_PREFIX}/{slug}/{filename}"


def private_audio_ref(bucket: str, key: str) -> str:
    return f"{PRIVATE_URL_SCHEME}{bucket}/{key}"


def parse_private_ref(url: str) -> Optional[Tuple[str, str]]:
    """``(bucket, key)`` for an ``r2-private://`` reference, else ``None``."""
    if not url or not url.startswith(PRIVATE_URL_SCHEME):
        return None
    rest = url[len(PRIVATE_URL_SCHEME):]
    bucket, _, key = rest.partition("/")
    if not bucket or not key:
        return None
    return bucket, key


def upload_private_audio(local_path: Path, config: Any) -> Optional[str]:
    """Upload a members episode's MP3 to the private bucket.

    Returns the ``r2-private://`` reference, or ``None`` when credentials
    are missing or the upload failed (the caller fails the run: a members
    episode with no audio anywhere has reached nobody).
    """
    from engine.storage import upload_to_r2

    storage = getattr(config, "storage", None)
    endpoint = os.environ.get(getattr(storage, "endpoint_env", "R2_ENDPOINT_URL"), "")
    access_key = os.environ.get(getattr(storage, "access_key_env", "R2_ACCESS_KEY_ID"), "")
    secret_key = os.environ.get(getattr(storage, "secret_key_env", "R2_SECRET_ACCESS_KEY"), "")
    if not (endpoint and access_key and secret_key):
        logger.error("members: R2 credentials are not set — the episode's "
                     "audio cannot reach the private bucket")
        return None
    bucket = private_bucket()
    key = private_audio_key(config.slug, Path(local_path).name)
    try:
        upload_to_r2(Path(local_path), key, bucket=bucket, endpoint_url=endpoint,
                     access_key=access_key, secret_key=secret_key,
                     public_base_url="", content_type="audio/mpeg")
    except Exception as exc:  # noqa: BLE001 — reported, the caller decides
        logger.error("members: private upload failed (%s: %s)", type(exc).__name__, exc)
        return None
    return private_audio_ref(bucket, key)


# ---------------------------------------------------------------------------
# Network-wide reads (site, audit, Nerra Daily, promo rotation)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _config_for(slug: str, root: str) -> Any:
    path = Path(root) / "shows" / f"{slug}.yaml"
    if not path.exists():
        return None
    from engine.config import load_config

    try:
        return load_config(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("access: could not load %s (%s)", path, exc)
        return None


def mode_for_slug(slug: str, root: Path = PROJECT_ROOT) -> str:
    """A show's access mode by slug; ``public`` for a registry-only show
    with no YAML (Nerra Daily, Nerra Voices)."""
    config = _config_for(slug, str(root))
    return "public" if config is None else access_mode(config)


def is_slug_public_on(slug: str, day: dt.date, root: Path = PROJECT_ROOT) -> bool:
    config = _config_for(slug, str(root))
    return True if config is None else is_public_on(config, day)


def gated_shows(root: Path = PROJECT_ROOT) -> Dict[str, str]:
    """``{slug: mode}`` for every show that is not plain public."""
    from engine.config import discover_show_slugs

    out: Dict[str, str] = {}
    for slug in discover_show_slugs(Path(root) / "shows"):
        mode = mode_for_slug(slug, root)
        if mode != "public":
            out[slug] = mode
    return out


def feed_age_overrides(root: Path = PROJECT_ROOT) -> Dict[str, Optional[int]]:
    """Daily-audit RSS-freshness overrides keyed by RSS file name.

    A members-only show's public feed never updates (``None`` = do not
    check); a public-weekly show's public feed updates once a week.
    """
    out: Dict[str, Optional[int]] = {}
    for slug, mode in gated_shows(root).items():
        config = _config_for(slug, str(root))
        rss = Path(getattr(getattr(config, "publishing", None), "rss_file", "") or "").name
        if not rss:
            continue
        out[rss] = None if mode == "members_only" else PUBLIC_WEEKLY_FEED_MAX_HOURS
    return out
