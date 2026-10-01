"""Pure readers over the committed claims record, for the public ledger pages.

The source-integrity gate commits one ``<stem>_claims.json`` beside every
digest (``engine.claims.save_ledger``), and ``engine.corrections`` keeps one
``corrections.yaml`` per show. Until 2026-10-01 the only reader surface was
the collapsed "Verified claims" panel on a single post. This module turns
the whole committed record into per-show and network tables for
``claims.html`` and ``claims/<slug>.html`` (``generate_html.generate_claims_pages``).

Two sidecar generations are read:

* **policy 2** (``gate.policy_version: 2``, Oct 2026, ``on_failure: flag``):
  EVERY ledger entry is committed with a ``status`` — ``verified``,
  ``verified_from_fetched``, ``verified_later`` (a nightly re-check passed;
  ``verified_at`` + ``first_status``), ``unverified_unreachable``,
  ``unverified_not_found``, ``unverified_quote_mismatch``,
  ``unverified_uncovered`` (a citation-shaped sentence with no entry;
  ``claim`` is the sentence, no url) or ``malformed``;
  ``gate.flagged_sentences`` lists what shipped marked.
* **policy 1** (everything before): the sidecar holds only the entries that
  verified, so every entry reads as ``verified``, and
  ``gate.stripped_sentences`` is what strip mode REMOVED before publication.

Everything is read-only and never raises: an unreadable sidecar is logged
and skipped, a show with no sidecar in the window reports ``None`` totals
(null, never 0 — the audience-headline rule), and a show that has no
ledger by construction (the Voices interview shows, the spliced daily
edition) is reported ``applicable: False`` with one sentence saying why.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union
from urllib.parse import urlparse

from engine import corrections as _corrections
from engine.brand import (
    CLAIMS_STATUS_LABELS, CLAIMS_VERIFIED_STATUSES, claims_status_label,
    claims_status_meaning,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
SHOWS_DIR = ROOT / "shows"
DIGESTS_DIR = ROOT / "digests"

#: The default window every ledger page reports over.
DEFAULT_DAYS = 30

#: The statuses a flag-era sidecar may carry. ``engine.claims`` owns the
#: vocabulary; this tuple is what the pages know how to label, and an
#: unknown status is still rendered (raw, amber) rather than dropped.
KNOWN_STATUSES = tuple(s for s in CLAIMS_STATUS_LABELS if s != "correction")

#: The statuses that mean "published and marked".
FLAGGED_STATUSES = (
    "unverified_unreachable", "unverified_not_found",
    "unverified_quote_mismatch", "unverified_uncovered", "malformed",
)

#: Shows that have no claims ledger BY CONSTRUCTION, with the one sentence
#: their row and page say instead of a table. A new show that bypasses
#: ``run_show`` belongs here or it renders as "no episodes in the window",
#: which is a different (and false) statement.
NOT_APPLICABLE = {
    "nerra_daily": (
        "Nerra Daily splices the day's already-published episodes together "
        "and adds Mira's links between them, so it carries no ledger of its "
        "own: every claim in a segment is on the ledger of the show that "
        "made it."
    ),
    "age_of_ai": (
        "The Age of AI is an interview: the guest's words are published "
        "verbatim, a human editor reviews every episode before release and "
        "the guest approves their own transcript, so there is no claims "
        "ledger to check against a source."
    ),
    "nerra_voices": (
        "Nerra Voices is an interview show on the same two human gates as "
        "The Age of AI — editorial review and the guest's own transcript "
        "approval — and carries no claims ledger."
    ),
}

_STEM_RE = re.compile(r"^(?P<prefix>.+)_Ep(?P<ep>\d{1,4})_(?P<date>\d{8})$")


# ---------------------------------------------------------------------------
# Show configuration
# ---------------------------------------------------------------------------

def show_episode_config(slug: str, shows_dir: Union[str, Path, None] = None) -> Optional[dict]:
    """``{"output_dir": Path, "prefix": str}`` from ``shows/<slug>.yaml``, or
    ``None`` when the show has no YAML (a registry-only show) or the YAML
    carries no ``episode`` block."""
    shows_dir = Path(shows_dir) if shows_dir else SHOWS_DIR
    path = shows_dir / f"{slug}.yaml"
    if not path.is_file():
        return None
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 — a ledger page never breaks a build
        logger.warning("claims_ledger: could not read %s: %s", path, exc)
        return None
    ep = data.get("episode") if isinstance(data.get("episode"), dict) else {}
    output_dir = str(ep.get("output_dir") or "").strip()
    prefix = str(ep.get("prefix") or "").strip()
    if not output_dir or not prefix:
        return None
    return {"output_dir": Path(output_dir), "prefix": prefix}


def show_dir_for(slug: str, *, digests_root: Union[str, Path, None] = None,
                 shows_dir: Union[str, Path, None] = None) -> Optional[Path]:
    """The show's digest directory, resolved under *digests_root* (default
    the repo's ``digests/``). A test points this at a scratch tree."""
    cfg = show_episode_config(slug, shows_dir)
    if cfg is None:
        return None
    out = cfg["output_dir"]
    root = Path(digests_root) if digests_root else DIGESTS_DIR
    parts = out.parts
    if parts and parts[0] == "digests":
        return root / Path(*parts[1:]) if len(parts) > 1 else root
    if out.is_absolute():
        return out
    return root.parent / out if digests_root is None else root / out


# ---------------------------------------------------------------------------
# Sidecar reading
# ---------------------------------------------------------------------------

def _domain(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""
    return host[4:] if host.startswith("www.") else host


def _iso(ymd: str) -> str:
    return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"


def parse_stem(stem: str) -> Optional[dict]:
    """``MAG7_Daily_Ep009_20261001`` → ``{"prefix", "episode", "date"}``."""
    m = _STEM_RE.match(stem)
    if not m:
        return None
    return {
        "prefix": m.group("prefix"),
        "episode": int(m.group("ep")),
        "date": _iso(m.group("date")),
    }


def normalise_entry(entry: dict, *, legacy: bool) -> Optional[dict]:
    """One ledger entry as the pages render it, or ``None`` when it carries
    nothing a reader could use.

    *legacy* (policy 1) entries have no ``status`` and are all verified.
    A flag-era entry keeps its status verbatim; an entry with no status in
    a policy-2 sidecar is read as ``malformed`` rather than promoted.
    """
    if not isinstance(entry, dict):
        return None
    claim = " ".join(str(entry.get("claim") or entry.get("episode_span") or "").split())
    if not claim:
        return None
    url = str(entry.get("source_url") or "").strip()
    if not url.startswith(("http://", "https://")):
        url = ""
    raw_status = str(entry.get("status") or "").strip().lower()
    if legacy:
        status = "verified"
    else:
        status = raw_status or "malformed"
    verified_at = str(entry.get("verified_at") or "").strip()[:10]
    first_status = str(entry.get("first_status") or "").strip().lower()
    reason = " ".join(str(entry.get("reason") or "").split())
    return {
        "id": str(entry.get("id") or ""),
        "claim": claim,
        "status": status,
        "label": claims_status_label(status),
        "meaning": claims_status_meaning(status),
        "reason": reason,
        "source_url": url,
        "source_domain": _domain(url) if url else "",
        "source_title": " ".join(str(entry.get("source_title") or "").split()),
        "verified_at": verified_at,
        "first_status": first_status,
        "first_label": claims_status_label(first_status) if first_status else "",
        "is_verified": status in CLAIMS_VERIFIED_STATUSES,
        "is_flagged": status not in CLAIMS_VERIFIED_STATUSES,
    }


def read_sidecar(path: Union[str, Path]) -> Optional[dict]:
    """One sidecar → ``{"policy_version", "claims", "flagged_sentences",
    "stripped_sentences", "gate_passed"}``; ``None`` when unreadable."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("claims_ledger: unreadable sidecar %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    gate = data.get("gate") if isinstance(data.get("gate"), dict) else {}
    try:
        policy = int(gate.get("policy_version") or 1)
    except (TypeError, ValueError):
        policy = 1
    entries = data.get("claims") if isinstance(data.get("claims"), list) else []
    legacy = policy < 2 and not any(
        isinstance(e, dict) and e.get("status") for e in entries)
    claims = [c for c in (normalise_entry(e, legacy=legacy) for e in entries) if c]

    def _sentences(key: str) -> List[str]:
        raw = gate.get(key)
        if not isinstance(raw, list):
            return []
        out = []
        for s in raw:
            if isinstance(s, dict):
                s = s.get("sentence") or s.get("claim") or s.get("text") or ""
            s = " ".join(str(s or "").split())
            if s:
                out.append(s)
        return out

    return {
        "policy_version": 2 if not legacy else 1,
        "claims": claims,
        # Policy 2: what shipped marked (also derivable from the entries;
        # kept so a sidecar whose entries and list disagree still reads).
        "flagged_sentences": _sentences("flagged_sentences"),
        # Policy 1: what strip mode removed before publication.
        "stripped_sentences": _sentences("stripped_sentences"),
        "gate_passed": bool(gate.get("passed", True)),
    }


# ---------------------------------------------------------------------------
# Per-show ledger
# ---------------------------------------------------------------------------

def _window(days: int, today: Optional[date]) -> tuple:
    today = today or date.today()
    start = today - timedelta(days=max(int(days), 0))
    return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


def _pct(num: int, den: int) -> Optional[float]:
    return round(100.0 * num / den, 1) if den else None


def _default_blog_url(slug: str, episode: int) -> str:
    """Same rule as ``generate_html._blog_url_for_episode`` (the file must
    exist and must not be a redirect stub), imported lazily so this module
    stays importable without the generator."""
    try:
        from generate_html import _blog_url_for_episode
        return _blog_url_for_episode(slug, episode_num=episode)
    except Exception:  # noqa: BLE001
        rel = ROOT / "blog" / slug / f"ep{int(episode):03d}.html"
        return f"blog/{slug}/ep{int(episode):03d}.html" if rel.is_file() else ""


def episode_rows(show_dir: Union[str, Path], prefix: str, *, days: int = DEFAULT_DAYS,
                 today: Optional[date] = None, slug: str = "",
                 blog_url_for: Optional[Callable[[str, int], str]] = None) -> List[dict]:
    """Every episode of the show with a sidecar inside the window, newest
    first. Each row carries the episode's claims (with status), its flagged
    / stripped sentences, and the corrections filed against it."""
    show_dir = Path(show_dir)
    if not show_dir.is_dir():
        return []
    start, end = _window(days, today)
    blog_url_for = blog_url_for or _default_blog_url
    all_corrections = _corrections.load_corrections(show_dir)
    rows: Dict[int, dict] = {}
    for path in sorted(show_dir.glob(f"{prefix}_Ep*_*_claims.json")):
        stem = path.name[: -len("_claims.json")]
        meta = parse_stem(stem)
        if not meta or meta["prefix"] != prefix:
            continue
        if not (start <= meta["date"] <= end):
            continue
        side = read_sidecar(path)
        if side is None:
            continue
        ep = meta["episode"]
        # Two files for one episode (a rerun): the later date wins, which is
        # how the blog deduplicates them.
        if ep in rows and rows[ep]["date"] >= meta["date"]:
            continue
        claims = side["claims"]
        by_status = Counter(c["status"] for c in claims)
        verified = sum(1 for c in claims if c["is_verified"])
        flagged = sum(1 for c in claims if c["is_flagged"])
        later = by_status.get("verified_later", 0)
        rows[ep] = {
            "episode": ep,
            "date": meta["date"],
            "stem": stem,
            "sidecar": str(path),
            "blog_url": blog_url_for(slug, ep) if slug else "",
            "policy_version": side["policy_version"],
            "gate_passed": side["gate_passed"],
            "claims": claims,
            "counts": {
                "total": len(claims),
                "verified": verified,
                "verified_later": later,
                "flagged": flagged,
                "by_status": dict(by_status),
            },
            "flagged_sentences": side["flagged_sentences"],
            "stripped_sentences": side["stripped_sentences"],
            "corrections": [c for c in all_corrections if c["episode"] == ep],
        }
    return sorted(rows.values(), key=lambda r: (r["date"], r["episode"]), reverse=True)


def _totals(rows: List[dict], corrections_in_window: int, days: int,
            window: tuple) -> dict:
    """Totals over *rows*; ``None`` (never 0) for the shares and counts of a
    show with no sidecar in the window."""
    if not rows:
        return {
            "episodes": 0,
            "claims": None,
            "verified": None,
            "verified_share_pct": None,
            "verified_later": None,
            "flagged": None,
            "flagged_share_pct": None,
            "flagged_by_reason": {},
            "stripped": None,
            "corrections": corrections_in_window,
            "days": days,
            "window_start": window[0],
            "window_end": window[1],
        }
    claims = sum(r["counts"]["total"] for r in rows)
    verified = sum(r["counts"]["verified"] for r in rows)
    flagged = sum(r["counts"]["flagged"] for r in rows)
    later = sum(r["counts"]["verified_later"] for r in rows)
    stripped = sum(len(r["stripped_sentences"]) for r in rows)
    by_reason: Counter = Counter()
    for r in rows:
        for status, n in r["counts"]["by_status"].items():
            if status not in CLAIMS_VERIFIED_STATUSES:
                by_reason[status] += n
    return {
        "episodes": len(rows),
        "claims": claims,
        "verified": verified,
        "verified_share_pct": _pct(verified, claims),
        "verified_later": later,
        "flagged": flagged,
        "flagged_share_pct": _pct(flagged, claims),
        "flagged_by_reason": {
            s: {"count": n, "label": claims_status_label(s)}
            for s, n in by_reason.most_common()
        },
        "stripped": stripped,
        "corrections": corrections_in_window,
        "days": days,
        "window_start": window[0],
        "window_end": window[1],
    }


def show_ledger(slug: str, *, days: int = DEFAULT_DAYS, today: Optional[date] = None,
                digests_root: Union[str, Path, None] = None,
                shows_dir: Union[str, Path, None] = None,
                blog_url_for: Optional[Callable[[str, int], str]] = None) -> dict:
    """The committed record for one show over the last *days* days.

    Returns ``{"slug", "applicable", "note", "rows", "totals",
    "recent_corrections"}``. ``applicable`` is ``False`` for a show in
    :data:`NOT_APPLICABLE` or one with no ``episode`` block in its YAML (a
    registry-only show); its ``note`` is the one sentence the page prints.
    """
    window = _window(days, today)
    if slug in NOT_APPLICABLE:
        return {
            "slug": slug, "applicable": False, "note": NOT_APPLICABLE[slug],
            "rows": [], "totals": _totals([], 0, days, window),
            "recent_corrections": [],
        }
    cfg = show_episode_config(slug, shows_dir)
    show_dir = show_dir_for(slug, digests_root=digests_root, shows_dir=shows_dir)
    if cfg is None or show_dir is None:
        return {
            "slug": slug, "applicable": False,
            "note": "This show is assembled outside the daily pipeline and "
                    "keeps no claims ledger of its own.",
            "rows": [], "totals": _totals([], 0, days, window),
            "recent_corrections": [],
        }
    rows = episode_rows(show_dir, cfg["prefix"], days=days, today=today,
                        slug=slug, blog_url_for=blog_url_for)
    recent = _corrections.recent_corrections(show_dir, days=days, today=today)
    return {
        "slug": slug,
        "applicable": True,
        "note": "",
        "rows": rows,
        "totals": _totals(rows, len(recent), days, window),
        "recent_corrections": recent,
    }


# ---------------------------------------------------------------------------
# Network ledger
# ---------------------------------------------------------------------------

def network_ledger(slugs: List[str], *, days: int = DEFAULT_DAYS,
                   today: Optional[date] = None,
                   digests_root: Union[str, Path, None] = None,
                   shows_dir: Union[str, Path, None] = None) -> dict:
    """Per-show totals for *slugs* plus network totals.

    Network totals sum only the shows that have sidecars in the window; a
    show with none contributes nothing and is listed with ``None`` totals,
    never as zeros.
    """
    window = _window(days, today)
    shows = []
    for slug in slugs:
        ledger = show_ledger(slug, days=days, today=today, digests_root=digests_root,
                             shows_dir=shows_dir, blog_url_for=lambda s, e: "")
        shows.append({
            "slug": slug,
            "applicable": ledger["applicable"],
            "note": ledger["note"],
            "totals": ledger["totals"],
        })
    measured = [s for s in shows if s["applicable"] and s["totals"]["claims"] is not None]
    claims = sum(s["totals"]["claims"] for s in measured)
    verified = sum(s["totals"]["verified"] for s in measured)
    flagged = sum(s["totals"]["flagged"] for s in measured)
    later = sum(s["totals"]["verified_later"] for s in measured)
    stripped = sum(s["totals"]["stripped"] for s in measured)
    by_reason: Counter = Counter()
    for s in measured:
        for status, item in s["totals"]["flagged_by_reason"].items():
            by_reason[status] += item["count"]
    corrections = sum(s["totals"]["corrections"] for s in shows if s["applicable"])
    totals = {
        "shows_measured": len(measured),
        "shows_applicable": sum(1 for s in shows if s["applicable"]),
        "shows_not_applicable": sum(1 for s in shows if not s["applicable"]),
        "episodes": sum(s["totals"]["episodes"] for s in measured),
        "claims": claims if measured else None,
        "verified": verified if measured else None,
        "verified_share_pct": _pct(verified, claims) if measured else None,
        "verified_later": later if measured else None,
        "flagged": flagged if measured else None,
        "flagged_share_pct": _pct(flagged, claims) if measured else None,
        "flagged_by_reason": {
            s: {"count": n, "label": claims_status_label(s)}
            for s, n in by_reason.most_common()
        },
        "stripped": stripped if measured else None,
        "corrections": corrections,
        "days": days,
        "window_start": window[0],
        "window_end": window[1],
    }
    return {"shows": shows, "totals": totals, "days": days}
