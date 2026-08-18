#!/usr/bin/env python3
"""Generate api/dashboard.json for the Nerra Network management dashboard.

Read-only aggregator. Walks existing on-disk data (shows/*.yaml,
digests/<show>/metrics_ep*.json, digests/<show>/credit_usage_*.json,
*.rss, data/feed_audit_*.json) and writes a single JSON file consumed
by management.html via fetch().

Landmines covered (per CLAUDE.md "Known Landmines"):
  1  - repo / R2 size, tracked-MP3 count
  2  - RSS integrity, LFS absence, R2 host consistency
  3  - legacy top-level flat files under digests/
  4  - per-show output_dir / audio_subdir begin with digests/<slug>/
  5  - nested digests/digests/ does not exist
  6  - *_formatted.md duplicate files absent
  8  - publishing.x_enabled is a boolean on every show
  9  - TTS voice settings consistency vs shows/_defaults.yaml
  11 - every show resolves tts.provider == grok (network default since May 2026)
  12 - every summaries JSON lives under digests/<slug>/

Items 7 (NEWSAPI dead secret) and 10 (early-episode deletion) are deliberately
excluded per user instruction.

Models & Agents (models_agents) and Models & Agents for Beginners
(models_agents_beginners) are ALWAYS reported as separate entries. They
share no rows, no aggregation keys, and no landmine checks.

Usage::

    python scripts/generate_dashboard.py               # write api/dashboard.json
    python scripts/generate_dashboard.py --offline     # skip HEAD reachability checks
    python scripts/generate_dashboard.py --dry-run     # print JSON to stdout only
    python scripts/generate_dashboard.py --out /tmp/d.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make `engine` importable when this script is run from anywhere.
_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import requests  # only used for --online HEAD checks
except Exception:  # pragma: no cover - requests is in requirements.txt
    requests = None  # type: ignore

try:
    import yaml
except Exception as exc:  # pragma: no cover
    print(f"dashboard: pyyaml required ({exc})", file=sys.stderr)
    raise


HEADERS = {
    "User-Agent": "NerraDashboardBot/1.0 (+https://nerranetwork.com/management.html)"
}
HEAD_TIMEOUT = 5

# Skip these YAML files when discovering shows — they are not shows.
# ``network_meta`` + ``scaffold_pending`` are network-level helper
# files (cross-show metadata + pending scaffold-script state) that
# don't have ``name`` / ``slug`` / ``episode`` / ``publishing``
# blocks of their own — loading them via the ShowConfig dataclass
# pulls in the network defaults and trips the item_4_output_dirs
# landmine check, which was the root cause of the recurring FAIL
# state on the management dashboard workflow.
_NON_SHOW_YAMLS = {
    "_defaults", "_blocked_sources", "pronunciation_map",
    "network_meta", "scaffold_pending", "translation_overrides",
}

# Canonical Russian voice id (the custom "Olya" Grok voice — the May 2026
# full-network Grok migration retired the old ElevenLabs RU voice
# gedzfqL7OGdPbwm0ynTP, but this baseline kept pointing at it, flagging
# FP/PR/age_of_ai as "voice drift" on every dashboard build — a stale-baseline
# false positive that trains the operator to ignore warnings; July 18 2026
# network review). shows/_defaults.yaml ships the English default.
_VOICE_ID_RU = "0b875ae2"

# Per-show sanctioned voice exceptions beyond the EN/RU pair: Age of AI's
# Mira persona deliberately uses the Grok built-in `ara` (NOT the Patrick
# clone — CLAUDE.md AOAI section).
_SANCTIONED_EXTRA_VOICES = {"ara"}

# Stale CLAUDE.md triple we use to detect documentation drift (item 9).
_CLAUDE_MD_OLD_VOICE_TRIPLE = "0.65/0.9/0.85"

# Canonical public show-page filenames (must match generate_html.NETWORK_SHOWS
# + shows/network_meta.yaml). The dashboard used to emit ``{slug}.html``
# which 404s for almost every show (dp_pod → thedppod.html, modern_investing
# → modern-investing.html, RU shows under ru/, etc.).
_SHOW_PAGE_BY_SLUG: Dict[str, str] = {
    "tesla": "tesla.html",
    "omni_view": "omni-view.html",
    "fascinating_frontiers": "fascinating-frontiers.html",
    "planetterrian": "planetterrian.html",
    "env_intel": "env-intel.html",
    "models_agents": "models-agents.html",
    "models_agents_beginners": "models-agents-beginners.html",
    "finansy_prosto": "ru/finansy-prosto.html",
    "privet_russian": "ru/privet-russian.html",
    "modern_investing": "modern-investing.html",
    "unintended_consequences": "unintended-consequences.html",
    "first_principles": "first-principles.html",
    "spacex": "spacex.html",
    "dp_pod": "thedppod.html",
    "age_of_ai": "age-of-ai.html",
}

# Cadence-aware publish-staleness thresholds (warn_hours, stale_hours).
# Daily shows keep the historic 48h/72h. Monday-only shows need ~10 days
# before "stale" is a real miss. Age of AI is interview-driven — never
# flag as stale from pub age alone.
_PUB_AGE_THRESHOLDS_H: Dict[str, Optional[tuple]] = {
    "env_intel": (192, 240),        # Monday
    "finansy_prosto": (192, 240),   # Monday
    "privet_russian": (192, 240),   # Monday
    "offshore_north": (192, 240),   # Monday
    "age_of_ai": None,              # on-demand interviews
}
_PUB_AGE_DEFAULT_H = (48, 72)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class LandmineResult:
    id: str
    title: str
    status: str  # "ok" | "warn" | "fail"
    details: str
    evidence: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Show discovery
# ---------------------------------------------------------------------------


def _absent_preserving_totals(
    per_show: Dict[str, Dict[str, Any]], fields,
) -> Dict[str, Optional[float]]:
    """Sum *fields* across shows, keeping "not measured" distinct from zero.

    This repo's signature bug is rendering absence as ``0``: Apple
    suppresses metrics it will not disclose, and a show with no listening
    has no row at all. The old Apple totals coerced every missing value
    with ``int(v or 0)``, so "Apple told us nothing" and "Apple told us
    zero" collapsed into the same number on the dashboard.

    A field that NO show reported returns ``None`` — the UI renders that
    as an em dash. A field some shows reported sums only those.
    """
    out: Dict[str, Optional[float]] = {}
    for metric in fields:
        values = [
            v.get(metric) for v in per_show.values()
            if isinstance(v.get(metric), (int, float))
        ]
        out[metric] = round(sum(values), 4) if values else None
    return out


def _list_show_yaml_paths(shows_dir: Path) -> List[Path]:
    return sorted(
        p for p in shows_dir.glob("*.yaml")
        if p.stem not in _NON_SHOW_YAMLS
        and not p.stem.endswith("_template")
        and not p.stem.startswith("_")
    )


def load_shows_from_yaml(shows_dir: Path, root: Path) -> List[Dict[str, Any]]:
    """Discover every show YAML and load its merged configuration.

    Returns a list of dicts (one per show). The ``models_agents`` and
    ``models_agents_beginners`` configs are loaded as two distinct entries;
    no downstream code should collapse them.
    """
    from engine.config import load_config  # local import — script boot

    results: List[Dict[str, Any]] = []
    from engine.config import discover_show_slugs
    for slug in discover_show_slugs(shows_dir):
        path = shows_dir / f"{slug}.yaml"
        if not path.exists():
            continue
        try:
            cfg = load_config(str(path))
        except Exception as exc:
            results.append({
                "slug": slug,
                "name": slug,
                "load_error": str(exc)[:200],
                "raw_yaml": {},
                "cfg": None,
            })
            continue

        raw_yaml: Dict[str, Any] = {}
        try:
            raw_yaml = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            raw_yaml = {}

        results.append({
            "slug": cfg.slug or slug,
            "name": cfg.name or slug,
            "yaml_path": str(path.relative_to(root)),
            "cfg": cfg,
            "raw_yaml": raw_yaml,
        })
    return results


# ---------------------------------------------------------------------------
# Landmine checks — CLAUDE.md "Known Landmines"
# ---------------------------------------------------------------------------


def _mk(id_: str, title: str, status: str, details: str, evidence=None) -> Dict[str, Any]:
    return asdict(LandmineResult(
        id=id_, title=title, status=status, details=details,
        evidence=evidence or {},
    ))


def _git_tracked_mp3_count(root: Path) -> Optional[int]:
    """Return the number of MP3 files currently tracked in git, or None."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "ls-files", "*.mp3"],
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
    except Exception:
        return None
    return sum(1 for line in out.decode("utf-8", "replace").splitlines() if line.strip())


def _dir_bytes(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def item_1_repo_size(root: Path) -> Dict[str, Any]:
    """Repo / R2 size + tracked MP3 count."""
    tracked_mp3s = _git_tracked_mp3_count(root)
    digests_bytes = _dir_bytes(root / "digests")
    digests_mb = digests_bytes / (1024 * 1024)

    if tracked_mp3s is None:
        status = "warn"
        details = (
            f"Could not run `git ls-files *.mp3` (not a git checkout?). "
            f"digests/ is {digests_mb:,.0f} MB."
        )
    elif tracked_mp3s > 1000 or digests_mb > 1024:
        status = "fail"
        details = (
            f"{tracked_mp3s} MP3s tracked in git, digests/ is "
            f"{digests_mb:,.0f} MB. R2 migration is urgent."
        )
    elif tracked_mp3s > 100 or digests_mb > 500:
        status = "warn"
        details = (
            f"{tracked_mp3s} MP3s tracked in git, digests/ is "
            f"{digests_mb:,.0f} MB. Above comfort threshold — keep an eye on it."
        )
    else:
        status = "ok"
        details = (
            f"{tracked_mp3s} MP3s tracked in git, digests/ is "
            f"{digests_mb:,.0f} MB."
        )

    return _mk(
        "item_1_repo_size",
        "Repo & R2 size",
        status,
        details,
        {"tracked_mp3_count": tracked_mp3s, "digests_mb": round(digests_mb, 1)},
    )


def item_3_legacy_flatfiles(root: Path, previous: Optional[int] = None) -> Dict[str, Any]:
    """Legacy top-level flat files directly under digests/."""
    digests = root / "digests"
    if not digests.exists():
        return _mk("item_3_legacy_flatfiles", "Legacy flat files in digests/",
                   "ok", "digests/ does not exist.")

    by_ext: Dict[str, int] = {}
    total = 0
    for p in digests.iterdir():
        if not p.is_file():
            continue
        total += 1
        ext = p.suffix.lower() or "<none>"
        by_ext[ext] = by_ext.get(ext, 0) + 1

    if total == 0:
        status = "ok"
        details = "No legacy flat files at digests/ top level."
    elif previous is not None and total > previous:
        status = "fail"
        details = (
            f"{total} legacy flat files — GREW from {previous}. The pipeline "
            f"should only write into per-show subdirectories now."
        )
    else:
        status = "warn"
        details = (
            f"{total} legacy flat files pinned at digests/ top level. They "
            f"cannot be moved (existing RSS URLs anchor to them), but no new "
            f"files should land here."
        )

    return _mk(
        "item_3_legacy_flatfiles",
        "Legacy flat files in digests/",
        status,
        details,
        {"total": total, "by_extension": by_ext, "previous_total": previous},
    )


def item_4_output_dirs(shows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Each show's output_dir + audio_subdir starts with digests/<slug>/."""
    violations = []
    for s in shows:
        cfg = s.get("cfg")
        if not cfg:
            continue
        slug = s["slug"]
        # Tesla is grandfathered: its historic output_dir is
        # "digests/tesla_shorts_time". Accept any path under digests/.
        out = cfg.episode.output_dir or ""
        sub = cfg.publishing.audio_subdir or ""
        if not out.startswith("digests/"):
            violations.append({"slug": slug, "field": "episode.output_dir", "value": out})
        if not sub.startswith("digests/"):
            violations.append({"slug": slug, "field": "publishing.audio_subdir", "value": sub})

    if not violations:
        return _mk(
            "item_4_output_dirs",
            "Per-show output paths under digests/",
            "ok",
            f"All {len(shows)} shows write into digests/…",
        )
    return _mk(
        "item_4_output_dirs",
        "Per-show output paths under digests/",
        "fail",
        f"{len(violations)} path(s) outside digests/",
        {"violations": violations},
    )


def item_5_nested_digests(root: Path) -> Dict[str, Any]:
    nested = root / "digests" / "digests"
    if nested.exists():
        return _mk(
            "item_5_nested_digests",
            "Nested digests/digests/ directory",
            "fail",
            "digests/digests/ exists — legacy path bug has resurfaced.",
            {"path": str(nested.relative_to(root))},
        )
    return _mk(
        "item_5_nested_digests",
        "Nested digests/digests/ directory",
        "ok",
        "No nested digests/digests/ directory.",
    )


def item_6_formatted_md(root: Path) -> Dict[str, Any]:
    hits = list((root / "digests").rglob("*_formatted.md"))
    if hits:
        return _mk(
            "item_6_formatted_md",
            "Duplicate *_formatted.md files",
            "fail",
            f"{len(hits)} *_formatted.md file(s) found — should have been deleted.",
            {"paths": [str(p.relative_to(root)) for p in hits[:10]], "total": len(hits)},
        )
    return _mk(
        "item_6_formatted_md",
        "Duplicate *_formatted.md files",
        "ok",
        "No *_formatted.md duplicates.",
    )


def item_8_feature_flags(shows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Each show YAML exposes publishing.x_enabled as a boolean."""
    per_show = []
    missing = []
    for s in shows:
        raw = s.get("raw_yaml") or {}
        pub = raw.get("publishing") or {}
        if "x_enabled" not in pub:
            missing.append(s["slug"])
            per_show.append({"slug": s["slug"], "x_enabled": None, "explicit": False})
            continue
        val = pub.get("x_enabled")
        if not isinstance(val, bool):
            missing.append(s["slug"])
        per_show.append({
            "slug": s["slug"],
            "x_enabled": val,
            "explicit": True,
        })

    if missing:
        return _mk(
            "item_8_feature_flags",
            "Feature flags (x_enabled) explicit",
            "warn",
            f"{len(missing)} show(s) rely on the publishing.x_enabled default "
            f"(not explicit in YAML): {', '.join(missing)}",
            {"per_show": per_show, "missing": missing},
        )
    return _mk(
        "item_8_feature_flags",
        "Feature flags (x_enabled) explicit",
        "ok",
        f"All {len(shows)} shows declare publishing.x_enabled explicitly.",
        {"per_show": per_show},
    )


def item_11_tts_provider(shows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Network-wide TTS provider invariant.

    All 12 shows run Grok TTS since the May 2026 full-network
    flip (CLAUDE.md landmine #17). ElevenLabs is the rollback path,
    not the live provider — accidental drift back to it would be a
    cost regression (Grok is ~36× cheaper per character) and a voice-
    consistency regression (the entire English network shares one
    custom-trained Grok voice). Pin grok as the expected provider so
    a copy-paste from old YAML lights up the dashboard.
    """
    wrong = []
    for s in shows:
        cfg = s.get("cfg")
        if not cfg:
            continue
        prov = (cfg.tts.provider or "").lower()
        if prov != "grok":
            wrong.append({"slug": s["slug"], "provider": prov or "<unset>"})
    if wrong:
        return _mk(
            "item_11_tts_provider",
            "All shows use Grok TTS",
            "fail",
            f"{len(wrong)} show(s) do not resolve to grok",
            {"wrong": wrong},
        )
    return _mk(
        "item_11_tts_provider",
        "All shows use Grok TTS",
        "ok",
        f"All {len(shows)} shows resolve tts.provider == grok.",
    )


def item_12_summaries_location(shows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Every summaries_json path lives under digests/<slug>/ and no legacy
    summaries_*.json files sit at digests/ top level."""
    violations = []
    for s in shows:
        cfg = s.get("cfg")
        if not cfg:
            continue
        slug = s["slug"]
        sj = cfg.publishing.summaries_json or ""
        if not sj.startswith("digests/"):
            violations.append({"slug": slug, "path": sj})

    digests = _ROOT / "digests"
    legacy: List[str] = []
    if digests.exists():
        for p in digests.iterdir():
            if p.is_file() and p.name.startswith("summaries_") and p.suffix == ".json":
                legacy.append(p.name)

    if violations or legacy:
        return _mk(
            "item_12_summaries_location",
            "summaries_*.json live under digests/<slug>/",
            "fail",
            f"{len(violations)} config(s) not under digests/ and "
            f"{len(legacy)} legacy summaries file(s) at digests/ top level.",
            {"violations": violations, "legacy_top_level": legacy},
        )
    return _mk(
        "item_12_summaries_location",
        "summaries_*.json live under digests/<slug>/",
        "ok",
        "All summaries JSONs live under their per-show subdirectory.",
    )


def item_13_youtube_health(shows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Every YouTube-enabled show has a non-empty podcast_playlist_id.

    Without a playlist ID, episodes upload but never appear in YouTube
    Music's Podcasts section for that show — silent reach loss.
    """
    enabled = []
    missing = []
    for s in shows:
        cfg = s.get("cfg")
        if not cfg:
            continue
        yt = getattr(cfg, "youtube", None)
        if not yt or not getattr(yt, "enabled", False):
            continue
        slug = s["slug"]
        enabled.append(slug)
        playlist = (getattr(yt, "podcast_playlist_id", "") or "").strip()
        if not playlist:
            missing.append(slug)

    if not enabled:
        return _mk(
            "item_13_youtube_health",
            "YouTube-enabled shows have podcast playlists",
            "ok",
            "No shows have youtube.enabled — nothing to validate.",
        )
    if missing:
        return _mk(
            "item_13_youtube_health",
            "YouTube-enabled shows have podcast playlists",
            "fail",
            f"{len(missing)} of {len(enabled)} YouTube-enabled "
            f"show(s) missing podcast_playlist_id: "
            f"{', '.join(missing)}.",
            {"missing": missing, "enabled": enabled},
        )
    return _mk(
        "item_13_youtube_health",
        "YouTube-enabled shows have podcast playlists",
        "ok",
        f"All {len(enabled)} YouTube-enabled show(s) have a podcast "
        f"playlist ID configured.",
    )


def item_22_grok_imagine_health(
    shows: List[Dict[str, Any]],
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Every show opted in to ``image_provider: grok|hybrid`` is
    actually generating images. Operator caught (TST Ep465, May 6
    2026) the Grok Imagine API rejecting the OpenAI-style ``size``
    parameter — both Tesla and MAB were configured for grok but
    silently fell back to the show cover for every long-form / Shorts
    upload. Without this landmine the failure stayed invisible until
    the operator looked at a video on YouTube.

    Fail when an opted-in show's last 30 episodes show <50%
    grok-image generation success. Warn at <90%. OK above.
    """
    opted_in: List[str] = []
    for s in shows:
        cfg = s.get("cfg")
        if not cfg:
            continue
        yt = getattr(cfg, "youtube", None)
        if not yt or not getattr(yt, "enabled", False):
            continue
        provider = (getattr(yt, "image_provider", "pexels") or "pexels").lower()
        if provider in ("grok", "hybrid"):
            opted_in.append(s["slug"])

    if not opted_in:
        return _mk(
            "item_22_grok_imagine_health",
            "Grok Imagine generates images for opted-in shows",
            "ok",
            "No show is on image_provider=grok|hybrid — nothing to validate.",
        )

    # ``aggregate_metrics`` returns the per-show dict directly (keyed by
    # slug). It's NOT wrapped in a ``per_show`` layer.
    per_show = metrics or {}
    failing: List[Dict[str, Any]] = []
    warning: List[Dict[str, Any]] = []
    healthy_count = 0
    for slug in opted_in:
        show_metrics = per_show.get(slug) or {}
        gi = show_metrics.get("grok_imagine") or {}
        attempts = int(gi.get("attempts") or 0)
        rate = float(gi.get("generation_success_rate") or 0.0)
        if attempts == 0:
            # Show is opted in but hasn't run yet (or no metrics history).
            continue
        sample = (gi.get("recent_failures") or [])[:1]
        first_fail = sample[0]["first_failure"] if sample else ""
        if rate < 0.5:
            failing.append({
                "slug": slug,
                "attempts": attempts,
                "success_rate": rate,
                "first_failure": first_fail,
            })
        elif rate < 0.9:
            warning.append({"slug": slug, "success_rate": rate})
        else:
            healthy_count += 1

    if failing:
        return _mk(
            "item_22_grok_imagine_health",
            "Grok Imagine generates images for opted-in shows",
            "fail",
            f"{len(failing)} of {len(opted_in)} opted-in show(s) are "
            f"generating <50% of expected images. First failure for "
            f"{failing[0]['slug']}: {failing[0].get('first_failure', '(no detail)')[:160]}",
            {"failing": failing, "warning": warning, "opted_in": opted_in},
        )
    if warning:
        return _mk(
            "item_22_grok_imagine_health",
            "Grok Imagine generates images for opted-in shows",
            "warn",
            f"{len(warning)} of {len(opted_in)} opted-in show(s) are "
            f"generating between 50% and 90% of expected images. Spot-"
            f"check the recent_failures samples in per_show.<slug>."
            f"grok_imagine.recent_failures.",
            {"warning": warning, "opted_in": opted_in},
        )
    return _mk(
        "item_22_grok_imagine_health",
        "Grok Imagine generates images for opted-in shows",
        "ok",
        f"All {len(opted_in)} opted-in show(s) are generating ≥90% of "
        f"expected images.",
    )


# ---------------------------------------------------------------------------
# Item 2 — RSS integrity + R2 / LFS audit
# ---------------------------------------------------------------------------


def _parse_rfc822(text: str) -> Optional[_dt.datetime]:
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(text)
    except Exception:
        return None


def _head_reachable(url: str, timeout: int = HEAD_TIMEOUT) -> Optional[int]:
    if requests is None:
        return None
    try:
        resp = requests.head(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return resp.status_code
    except Exception:
        return None


def audit_rss_enclosures(
    root: Path,
    *,
    offline: bool = False,
    head_sample: int = 3,
) -> Dict[str, Any]:
    """Walk every top-level *.rss file and report enclosure health.

    Used by both item 1 (R2 adoption) and item 2 (LFS absence, feed integrity).
    """
    feeds = sorted(
        p for p in root.glob("*.rss")
        if p.name != "network.rss" and not p.name.startswith("blog_")
    )
    per_feed: List[Dict[str, Any]] = []
    raw_github_hits: List[str] = []
    non_r2_hosts: List[str] = []

    for feed_path in feeds:
        entry_info: Dict[str, Any] = {
            "file": feed_path.name,
            "entry_count": 0,
            "latest_pub_date": None,
            "latest_enclosures": [],
            "malformed": False,
            "error": None,
        }
        try:
            tree = ET.parse(feed_path)
        except Exception as exc:
            entry_info["malformed"] = True
            entry_info["error"] = str(exc)[:200]
            per_feed.append(entry_info)
            continue

        items = tree.getroot().findall(".//item")
        entry_info["entry_count"] = len(items)

        # Newest first
        dated = []
        for item in items:
            pub = item.findtext("pubDate") or ""
            when = _parse_rfc822(pub) if pub else None
            enc_el = item.find("enclosure")
            enc_url = enc_el.get("url", "") if enc_el is not None else ""
            dated.append((when, enc_url, pub))

        dated_sorted = sorted(
            dated,
            key=lambda t: t[0] or _dt.datetime.min.replace(tzinfo=_dt.timezone.utc),
            reverse=True,
        )
        if dated_sorted and dated_sorted[0][0]:
            entry_info["latest_pub_date"] = dated_sorted[0][0].isoformat()

        for when, enc_url, pub in dated_sorted[:head_sample]:
            if not enc_url:
                continue
            host = re.sub(r"^https?://([^/]+).*$", r"\1", enc_url)
            if "raw.githubusercontent.com" in enc_url:
                raw_github_hits.append(enc_url)
            if host and host != "audio.nerranetwork.com":
                non_r2_hosts.append(host)
            status = None if offline else _head_reachable(enc_url)
            entry_info["latest_enclosures"].append({
                "url": enc_url,
                "host": host,
                "pub_date": when.isoformat() if when else pub,
                "http_status": status,
                "reachable": bool(status and 200 <= status < 400),
            })

        per_feed.append(entry_info)

    return {
        "feeds": per_feed,
        "raw_github_hits": raw_github_hits,
        "non_r2_hosts": sorted(set(non_r2_hosts)),
        "offline": offline,
    }


def item_2_rss_integrity(audit: Dict[str, Any]) -> Dict[str, Any]:
    malformed = [f["file"] for f in audit["feeds"] if f["malformed"]]
    raw_hits = audit.get("raw_github_hits") or []
    non_r2 = audit.get("non_r2_hosts") or []
    unreachable: List[str] = []
    if not audit.get("offline"):
        for f in audit["feeds"]:
            for enc in f.get("latest_enclosures", []):
                if enc.get("http_status") is None or not enc.get("reachable"):
                    unreachable.append(f"{f['file']}: {enc['url']}")

    if malformed or raw_hits:
        status = "fail"
        reason = []
        if malformed:
            reason.append(f"{len(malformed)} malformed feed(s)")
        if raw_hits:
            reason.append(f"{len(raw_hits)} enclosure(s) still pointing at raw.githubusercontent.com")
        details = "; ".join(reason)
    elif non_r2 or unreachable:
        status = "warn"
        reason = []
        if non_r2:
            reason.append(f"non-R2 hosts: {', '.join(non_r2)}")
        if unreachable:
            reason.append(f"{len(unreachable)} recent enclosure(s) unreachable")
        details = "; ".join(reason)
    else:
        status = "ok"
        details = f"All {len(audit['feeds'])} feeds valid, R2-hosted, recent enclosures reachable."

    return _mk(
        "item_2_rss_integrity",
        "RSS integrity, LFS absence, R2 host consistency",
        status,
        details,
        {
            "feeds": len(audit["feeds"]),
            "malformed": malformed,
            "raw_github_hits": raw_hits[:10],
            "non_r2_hosts": non_r2,
            "unreachable": unreachable[:10],
            "offline": audit.get("offline"),
        },
    )


# ---------------------------------------------------------------------------
# Item 9 — voice settings consistency
# ---------------------------------------------------------------------------


def audit_voice_config(shows: List[Dict[str, Any]], root: Path) -> Dict[str, Any]:
    defaults_path = root / "shows" / "_defaults.yaml"
    baseline: Dict[str, Any] = {
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.0,
        "voice_id_en": "dTrBzPvD2GpAqkk1MUzA",
        "voice_id_ru": _VOICE_ID_RU,
    }
    if defaults_path.exists():
        try:
            d = yaml.safe_load(defaults_path.read_text(encoding="utf-8")) or {}
            dtts = (d.get("tts") or {})
            for key in ("stability", "similarity_boost", "style"):
                if key in dtts:
                    baseline[key] = dtts[key]
            if "voice_id" in dtts:
                baseline["voice_id_en"] = dtts["voice_id"]
        except Exception:
            pass

    show_rows = []
    for s in shows:
        cfg = s.get("cfg")
        if not cfg:
            continue
        row = {
            "slug": s["slug"],
            "voice_id": cfg.tts.voice_id,
            "model": cfg.tts.model,
            "stability": cfg.tts.stability,
            "similarity_boost": cfg.tts.similarity_boost,
            "style": cfg.tts.style,
            "drift": [],
        }
        for key in ("stability", "similarity_boost", "style"):
            expected = baseline[key]
            actual = row[key]
            if actual != expected:
                row["drift"].append({
                    "field": key, "expected": expected, "actual": actual,
                })
        # Voice id must be one of the blessed voices (EN/RU pair plus the
        # per-show sanctioned exceptions, e.g. age_of_ai's Mira `ara`).
        if row["voice_id"] not in (
            baseline["voice_id_en"], baseline["voice_id_ru"],
            *_SANCTIONED_EXTRA_VOICES,
        ):
            row["drift"].append({
                "field": "voice_id",
                "expected": f"{baseline['voice_id_en']} or {baseline['voice_id_ru']}",
                "actual": row["voice_id"],
            })
        show_rows.append(row)

    claude_md_drift = False
    claude_md_path = root / "CLAUDE.md"
    if claude_md_path.exists():
        text = claude_md_path.read_text(encoding="utf-8", errors="replace")
        if _CLAUDE_MD_OLD_VOICE_TRIPLE in text:
            current_triple = (
                f"{baseline['stability']}/{baseline['similarity_boost']}/{baseline['style']}"
            )
            if current_triple != _CLAUDE_MD_OLD_VOICE_TRIPLE:
                claude_md_drift = True

    return {
        "baseline": baseline,
        "shows": show_rows,
        "claude_md_drift_detected": claude_md_drift,
    }


def item_9_voice_settings(voice: Dict[str, Any]) -> Dict[str, Any]:
    drifting = [r["slug"] for r in voice["shows"] if r["drift"]]
    status = "ok"
    details_parts = []
    if drifting:
        status = "warn"
        details_parts.append(f"{len(drifting)} show(s) drift from _defaults.yaml: {', '.join(drifting)}")
    if voice.get("claude_md_drift_detected"):
        status = "warn" if status != "fail" else status
        details_parts.append(
            f"CLAUDE.md still references {_CLAUDE_MD_OLD_VOICE_TRIPLE}, "
            f"but _defaults.yaml is "
            f"{voice['baseline']['stability']}/"
            f"{voice['baseline']['similarity_boost']}/"
            f"{voice['baseline']['style']}."
        )
    if not details_parts:
        details_parts.append("All shows match the _defaults.yaml voice baseline.")

    return _mk(
        "item_9_voice_settings",
        "TTS voice settings consistency",
        status,
        " ".join(details_parts),
        {
            "baseline": voice["baseline"],
            "drifting_shows": drifting,
            "claude_md_drift_detected": voice.get("claude_md_drift_detected"),
        },
    )


# ---------------------------------------------------------------------------
# Metrics + cost aggregation
# ---------------------------------------------------------------------------


# Map show slug → on-disk subdirectory name (Tesla uses a historic subdir).
_SHOW_DIR_OVERRIDES = {
    "tesla": "tesla_shorts_time",
}


def _digests_dir_for(slug: str, root: Path) -> Path:
    sub = _SHOW_DIR_OVERRIDES.get(slug, slug)
    return root / "digests" / sub


def _pct(samples: List[float], pct: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    k = max(0, min(len(ordered) - 1, int(round(pct * (len(ordered) - 1)))))
    return round(ordered[k], 2)


def aggregate_metrics(root: Path, shows: List[Dict[str, Any]]) -> Dict[str, Any]:
    per_show: Dict[str, Dict[str, Any]] = {}
    for s in shows:
        slug = s["slug"]
        ddir = _digests_dir_for(slug, root)
        files = sorted(ddir.glob("metrics_ep*.json")) if ddir.exists() else []
        last30 = files[-30:]
        totals: List[float] = []
        successes = 0
        stage_times: Dict[str, List[float]] = {}
        recent_samples = []
        # YouTube publishing health: count how many of the last 30
        # episodes successfully uploaded long-form / shorts. Episodes
        # where the show was YouTube-disabled are excluded from the
        # denominator so we don't dilute the success rate.
        yt_long_attempts = 0
        yt_long_uploaded = 0
        yt_short_attempts = 0
        yt_short_uploaded = 0
        yt_enabled_recent = False
        # Phase 2.6 health cards: track recent metrics that have no
        # dedicated dashboard surface yet.
        recap_attempts = 0  # Sundays where this show's runner ticked
        recap_synthesised = 0  # Sundays where the weekly-summary segment built
        tag_leak_episodes = 0  # episodes with tag_leaks > 0
        # Grok Imagine health (May 2026 rollout). Tracks per-show:
        #   - cost (USD spent generating images this 30-ep window)
        #   - generation success rate (episodes where ≥1 image generated)
        #   - failure samples for recent runs (operator can see WHY 0 imgs)
        # Pexels-only shows have all-zero values here.
        grok_image_cost_total = 0.0
        grok_image_attempts = 0    # episodes whose provider was grok/hybrid
        grok_image_success_eps = 0  # episodes that generated >=1 image
        grok_image_fail_samples: List[Dict[str, Any]] = []
        tag_leak_total = 0  # sum of leak counts across recent episodes
        tag_leak_pattern_counts: Dict[str, int] = {}
        yt_long_errors: List[Dict[str, Any]] = []  # last few error payloads
        youtube_quota_units = 0
        for f in last30:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            total = float(data.get("total_duration_s") or 0.0)
            totals.append(total)
            stages = data.get("stages") or []
            ep_success = all(bool(st.get("success", True)) for st in stages)
            if ep_success:
                successes += 1
            for st in stages:
                name = st.get("name") or "unknown"
                stage_times.setdefault(name, []).append(float(st.get("duration_s") or 0.0))
            counters = data.get("counters") or {}
            if counters.get("youtube_enabled"):
                yt_enabled_recent = True
                yt_long_attempts += 1
                yt_short_attempts += 1
                if counters.get("youtube_long_form_uploaded"):
                    yt_long_uploaded += 1
                if counters.get("youtube_short_uploaded"):
                    yt_short_uploaded += 1
                _err = counters.get("youtube_long_error")
                if isinstance(_err, dict):
                    yt_long_errors.append(_err)

                # Medium item: accumulate real quota units recorded at publish time
                q_units = counters.get("youtube_quota_units_this_episode")
                if isinstance(q_units, (int, float)):
                    youtube_quota_units += int(q_units)
            # Sunday weekly-summary-segment health. July 2026: the full
            # weekly-recap mode became a small in-episode segment; the
            # runner records ``weekly_summary_segment`` (True when the
            # segment built from the content lake, False when skipped).
            # ``weekly_recap_mode`` is the legacy key from the retired mode.
            if "weekly_summary_segment" in counters:
                recap_attempts += 1
                if counters.get("weekly_summary_segment"):
                    recap_synthesised += 1
            elif "weekly_recap_mode" in counters:
                recap_attempts += 1
                if counters.get("weekly_recap_mode"):
                    recap_synthesised += 1
            # Tag-leak rate (Phase 1.6 of the audit added tag_leaks
            # metric — every episode now records 0 or N).
            _tag_leaks = counters.get("tag_leaks")
            if isinstance(_tag_leaks, int) and _tag_leaks > 0:
                tag_leak_episodes += 1
                tag_leak_total += _tag_leaks
                _by_pat = counters.get("tag_leaks_by_pattern") or {}
                if isinstance(_by_pat, dict):
                    for _name, _cnt in _by_pat.items():
                        if isinstance(_cnt, int):
                            tag_leak_pattern_counts[_name] = (
                                tag_leak_pattern_counts.get(_name, 0) + _cnt
                            )

            # Grok Imagine roll-up. Only counts toward attempts/success
            # rate when this episode actually used the grok / hybrid
            # path; pexels-only episodes are excluded from the
            # denominator so the rate doesn't get diluted.
            _ip = (counters.get("image_provider") or "pexels").lower()
            if _ip in ("grok", "hybrid"):
                grok_image_attempts += 1
                _gen = counters.get("grok_images_generated")
                if isinstance(_gen, int) and _gen > 0:
                    grok_image_success_eps += 1
                _cost = counters.get("grok_image_cost_usd")
                if isinstance(_cost, (int, float)):
                    grok_image_cost_total += float(_cost)
                _fails = counters.get("grok_image_failures")
                if isinstance(_fails, list) and _fails and _gen == 0:
                    grok_image_fail_samples.append({
                        "episode_num": data.get("episode_num"),
                        "first_failure": str(_fails[0])[:200],
                    })
            recent_samples.append({
                "episode_num": data.get("episode_num"),
                "total_duration_s": total,
                "success": ep_success,
                "youtube_long_url": bool(counters.get("youtube_long_form_uploaded")),
                "youtube_short_url": bool(counters.get("youtube_short_uploaded")),
            })
        stage_means = {
            name: round(sum(vals) / len(vals), 2) if vals else 0.0
            for name, vals in stage_times.items()
        }
        per_show[slug] = {
            "sample_size": len(totals),
            "p50_duration_s": _pct(totals, 0.50),
            "p95_duration_s": _pct(totals, 0.95),
            "success_rate": round(successes / len(totals), 3) if totals else 0.0,
            "stage_mean_s": stage_means,
            "recent": recent_samples[-10:],
            "youtube": {
                "enabled_in_recent": yt_enabled_recent,
                "long_form_attempts": yt_long_attempts,
                "long_form_uploaded": yt_long_uploaded,
                "long_form_success_rate": (
                    round(yt_long_uploaded / yt_long_attempts, 3)
                    if yt_long_attempts else 0.0
                ),
                "estimated_quota_units_last_30_eps": youtube_quota_units,
                "shorts_attempts": yt_short_attempts,
                "shorts_uploaded": yt_short_uploaded,
                "shorts_success_rate": (
                    round(yt_short_uploaded / yt_short_attempts, 3)
                    if yt_short_attempts else 0.0
                ),
                # Last few HTTP error payloads from failed long-form
                # uploads. Most-likely values for `status` are
                # ``quotaExceeded`` (need quota increase),
                # ``authError`` (refresh token expired), or 5xx
                # (transient — retry next slot).
                "long_form_errors": yt_long_errors[-5:],
            },
            # Sunday weekly-summary-segment health. attempts is the count
            # of Sunday slots in the last 30 episodes for opted-in shows;
            # synthesised is how many actually built the "week in review"
            # segment from the content lake. A gap means the lake had <2
            # episodes in the 7-day window (the episode ships as a plain
            # daily with no segment). Key kept as ``weekly_recap`` for
            # dashboard-consumer backward compatibility.
            "weekly_recap": {
                "attempts": recap_attempts,
                "synthesised": recap_synthesised,
                "success_rate": (
                    round(recap_synthesised / recap_attempts, 3)
                    if recap_attempts else 0.0
                ),
            },
            # Grok Imagine roll-up (May 2026 rollout). Per-show:
            #   - cost_usd_recent: USD spent on image gen in the
            #     last-30-eps window
            #   - generation_success_rate: episodes (of those opted in
            #     to grok/hybrid) that actually got >=1 image. A drop
            #     here usually means an API request-format change or
            #     auth lapse — the recent_failures samples will
            #     pinpoint why.
            #   - recent_failures: first failure message from each of
            #     the last 5 episodes that ran grok and got 0 imgs
            "grok_imagine": {
                "attempts": grok_image_attempts,
                "successful_episodes": grok_image_success_eps,
                "generation_success_rate": (
                    round(grok_image_success_eps / grok_image_attempts, 3)
                    if grok_image_attempts else 0.0
                ),
                "cost_usd_recent": round(grok_image_cost_total, 4),
                "recent_failures": grok_image_fail_samples[-5:],
            },
            # Tag-leak rate (Phase 1.6 of the audit). Aggregates the
            # `tag_leaks` and `tag_leaks_by_pattern` per-episode
            # metrics. Any non-zero count is a regression signal.
            "tag_leaks": {
                "episodes_with_leaks": tag_leak_episodes,
                "total_leaks": tag_leak_total,
                "by_pattern": tag_leak_pattern_counts,
                "rate": (
                    round(tag_leak_episodes / len(totals), 3)
                    if totals else 0.0
                ),
            },
        }
    return per_show


def aggregate_costs(root: Path, shows: List[Dict[str, Any]]) -> Dict[str, Any]:
    today = _dt.date.today()
    d7 = today - _dt.timedelta(days=7)
    d30 = today - _dt.timedelta(days=30)

    per_show: Dict[str, Dict[str, Any]] = {}
    network_7 = {"grok": 0.0, "tts": 0.0, "images": 0.0, "search": 0.0,
                 "total": 0.0, "episodes": 0}
    network_30 = {"grok": 0.0, "tts": 0.0, "images": 0.0, "search": 0.0,
                  "total": 0.0, "episodes": 0}

    for s in shows:
        slug = s["slug"]
        ddir = _digests_dir_for(slug, root)
        files = sorted(ddir.glob("credit_usage_*.json")) if ddir.exists() else []
        show_7 = {"grok": 0.0, "tts": 0.0, "images": 0.0, "search": 0.0,
                  "total": 0.0, "episodes": 0}
        show_30 = {"grok": 0.0, "tts": 0.0, "images": 0.0, "search": 0.0,
                   "total": 0.0, "episodes": 0}
        daily_series: Dict[str, float] = {}

        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            date_str = data.get("date") or ""
            try:
                when = _dt.date.fromisoformat(date_str)
            except Exception:
                continue
            grok = float(
                ((data.get("services") or {}).get("grok_api") or {}).get("total_cost_usd") or 0.0
            )
            tts = float(
                ((data.get("services") or {}).get("tts_api") or {}).get("estimated_cost_usd") or 0.0
            )
            # Images + search were 41% of tracked 30d spend in Aug 2026 yet
            # invisible as categories (absorbed into `total` only) — the
            # 2026-08-18 LLM usage review broke them out.
            images = float(
                ((data.get("services") or {}).get("image_api") or {}).get("estimated_cost_usd") or 0.0
            )
            search = float(
                ((data.get("services") or {}).get("search_api") or {}).get("estimated_cost_usd") or 0.0
            )
            total = float(data.get("total_estimated_cost_usd") or (grok + tts + images + search))
            daily_series[date_str] = round(daily_series.get(date_str, 0.0) + total, 4)

            if when >= d30:
                for bucket in (show_30, network_30):
                    bucket["grok"] += grok
                    bucket["tts"] += tts
                    bucket["images"] += images
                    bucket["search"] += search
                    bucket["total"] += total
                    bucket["episodes"] += 1
            if when >= d7:
                for bucket in (show_7, network_7):
                    bucket["grok"] += grok
                    bucket["tts"] += tts
                    bucket["images"] += images
                    bucket["search"] += search
                    bucket["total"] += total
                    bucket["episodes"] += 1

        for bucket in (show_7, show_30):
            for k in ("grok", "tts", "images", "search", "total"):
                bucket[k] = round(bucket[k], 4)
        # Last 30 daily series, oldest → newest, for sparkline rendering.
        daily_sorted = sorted(daily_series.items())[-30:]
        per_show[slug] = {
            "last_7_days": show_7,
            "last_30_days": show_30,
            "daily_series": daily_sorted,
        }

    for bucket in (network_7, network_30):
        for k in ("grok", "tts", "images", "search", "total"):
            bucket[k] = round(bucket[k], 4)

    # Projection = actual last-7d burn (honest "current weekly rate").
    # Previously multiplied avg × 65, which understated spend when the
    # network ships ~100–150 credit_usage files/week (July 2026).
    episodes_7 = int(network_7.get("episodes", 0) or 0)
    avg_per_episode = (
        round(network_7["total"] / episodes_7, 4) if episodes_7 else 0.0
    )
    projected_weekly = round(network_7["total"], 2)
    projected_monthly = round(network_30["total"], 2)

    return {
        "per_show": per_show,
        "network_last_7_days": network_7,
        "network_last_30_days": network_30,
        # Quick-win enhancements (May 2026 codebase review): the cost
        # rollup also emits forward projections + the YouTube quota
        # surface. Pinned by tests/test_quick_wins.py — keep this marker
        # with the block it names.
        "projections": {
            "avg_cost_per_episode_usd": avg_per_episode,
            "projected_weekly_usd": projected_weekly,
            "projected_monthly_usd": projected_monthly,
            "episodes_7d": episodes_7,
            "note": (
                "Weekly projection = actual last-7d Grok+TTS spend "
                f"({episodes_7} credit_usage files). Monthly = last-30d total. "
                "Not a calendar forecast — a trailing burn rate."
            ),
        },
        "youtube_quota": {
            "enabled_shows_count": sum(
                1 for s in shows
                if s.get("cfg") and getattr(s["cfg"].youtube, "enabled", False)
            ),
            "daily_insert_cost_units": 1600,  # per long-form insert (see engine/youtube_quota.py)
            "note": "Quota raised to 200k units/day per channel (June 26 2026 — landmine #20); "
                    "the binding constraint is now upload CADENCE (~30/day/channel safe ceiling), "
                    "not quota. Preflight + youtube_quota.py have the estimators.",
        },
    }


_ML_LANGS = ("fr", "ru", "es", "zh")


def aggregate_multilingual(
    root: Path, shows: List[Dict[str, Any]], recent_n: int = 10
) -> Dict[str, Any]:
    """Per-show multilingual coverage + 7-day cost (June 2026).

    Coverage comes from each show's ``summaries_<show>.json`` ``translations``
    map (how many of the last *recent_n* episodes have each language / all
    languages). The 7-day cost reads ``services.multilingual.estimated_cost_usd``
    from the recent ``credit_usage_*.json`` files (0 until cost-tracked
    episodes exist — read defensively). Shows with ``multilingual.enabled``
    false (the Russian shows) are excluded.
    """
    from engine.summaries_io import load_summaries  # local import — script boot

    today = _dt.date.today()
    d7 = today - _dt.timedelta(days=7)
    per_show: Dict[str, Any] = {}
    network_cost_7 = 0.0

    for s in shows:
        cfg = s.get("cfg")
        ml = getattr(cfg, "multilingual", None) if cfg else None
        if not (ml and getattr(ml, "enabled", False)):
            continue  # disabled / Russian shows
        slug = s["slug"]

        # Coverage from the summaries translations map.
        per_language = {lang: 0 for lang in _ML_LANGS}
        all_languages = 0
        checked = 0
        summ = cfg.publishing.summaries_json or ""
        summ_path = root / summ if summ else None
        if summ_path and summ_path.exists():
            try:
                _w, records = load_summaries(summ_path)
                recs = sorted(
                    (r for r in records if isinstance(r.get("episode_num"), int)),
                    key=lambda r: r["episode_num"], reverse=True,
                )[:recent_n]
                checked = len(recs)
                for r in recs:
                    tr = r.get("translations") or {}
                    present = [
                        lang for lang in _ML_LANGS
                        if isinstance(tr.get(lang), dict) and tr[lang].get("audio_url")
                    ]
                    for lang in present:
                        per_language[lang] += 1
                    if len(present) == len(_ML_LANGS):
                        all_languages += 1
            except Exception:
                pass
        coverage_pct = round(all_languages / checked * 100, 1) if checked else 0.0

        # 7-day multilingual spend (defensive: section absent on old trackers).
        cost_7 = 0.0
        ddir = _digests_dir_for(slug, root)
        if ddir.exists():
            for f in sorted(ddir.glob("credit_usage_*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    when = _dt.date.fromisoformat(data.get("date") or "")
                except Exception:
                    continue
                if when >= d7:
                    cost_7 += float(
                        ((data.get("services") or {}).get("multilingual") or {})
                        .get("estimated_cost_usd") or 0.0
                    )
        cost_7 = round(cost_7, 4)
        network_cost_7 += cost_7

        per_show[slug] = {
            "languages": list(ml.languages) if getattr(ml, "languages", None) else list(_ML_LANGS),
            "auto": bool(getattr(ml, "auto", False)),
            "episodes_checked": checked,
            "per_language": per_language,
            "all_languages": all_languages,
            "coverage_pct": coverage_pct,
            "cost_7d_usd": cost_7,
        }

    # Audience per language, so the spend above can be judged rather than
    # assumed. Until July 2026 this was measured nowhere — the per-language
    # feeds carry the OP3 prefix but the fetcher never resolved them, so a
    # language with zero listeners looked exactly like one with many.
    op3: Dict[str, Any] = {}
    _op3_path = root / "api" / "op3_stats.json"
    if _op3_path.exists():
        try:
            op3 = json.loads(_op3_path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001 — analytics never break the build
            op3 = {}
    lang_feeds = op3.get("language_feeds") or {}
    per_language_audience: Dict[str, Any] = {}
    for key, entry in lang_feeds.items():
        if not isinstance(entry, dict):
            continue
        slug = entry.get("show_slug") or key.split(":", 1)[0]
        lang = entry.get("language") or (key.split(":", 1)[-1])
        row = {
            "downloads_7d": int(entry.get("downloads_7d") or 0),
            "downloads_30d": int(entry.get("downloads_30d") or 0),
            "stale": bool(entry.get("not_refreshed_this_run")),
        }
        per_language_audience[key] = {"show_slug": slug, "language": lang, **row}
        show_row = per_show.get(slug)
        if show_row is not None:
            show_row.setdefault("audience_by_language", {})[lang] = row

    # Roll up by language so "does ZH earn its keep" is one glance, not a
    # spreadsheet exercise. Cost is apportioned evenly across a show's
    # languages: the per-episode tracker records one multilingual total,
    # not a per-language split, and the tracks are near-identical work.
    by_language: Dict[str, Any] = {}
    for slug, row in per_show.items():
        langs = row.get("languages") or []
        share = (row.get("cost_7d_usd") or 0.0) / len(langs) if langs else 0.0
        for lang in langs:
            agg = by_language.setdefault(
                lang, {"downloads_7d": 0, "downloads_30d": 0,
                       "approx_cost_7d_usd": 0.0, "shows": 0, "measured": False},
            )
            agg["shows"] += 1
            agg["approx_cost_7d_usd"] = round(agg["approx_cost_7d_usd"] + share, 4)
            aud = (row.get("audience_by_language") or {}).get(lang)
            if aud:
                agg["measured"] = True
                agg["downloads_7d"] += aud["downloads_7d"]
                agg["downloads_30d"] += aud["downloads_30d"]

    return {
        "languages": list(_ML_LANGS),
        "recent_n": recent_n,
        "per_show": per_show,
        "network_cost_7d_usd": round(network_cost_7, 4),
        "audience_measured": bool(lang_feeds),
        "per_language_audience": per_language_audience,
        "by_language": by_language,
        "audience_note": (
            "Per-language OP3 downloads for the feeds the multilingual stage "
            "produces. approx_cost_7d_usd splits each show's multilingual "
            "spend evenly across its languages (the tracker records one "
            "total per episode). A language reading 0 downloads across "
            "several weeks is a candidate to switch off in the show YAML."
        ),
    }


def extract_critical_alerts(
    landmines: List[Dict[str, Any]],
    costs: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Produce a list of actionable critical alerts for proactive notifications.

    This is the foundation for the medium-term "proactive alerts webhook" feature.
    Currently focuses on landmine FAILs. Can be extended for cost spikes,
    repeated Grok Imagine failures, etc.
    """
    alerts: List[Dict[str, Any]] = []

    for lm in landmines:
        if lm.get("status") == "fail":
            alerts.append({
                "severity": "critical",
                "type": "landmine",
                "id": lm.get("id"),
                "title": lm.get("title"),
                "details": lm.get("details"),
                "evidence": lm.get("evidence", {}),
            })

    # TODO (future medium item): add cost spike detection using costs["projections"]
    # TODO (future): repeated grok_image or YouTube failures from recent metrics

    return alerts


def build_network_rollup(
    shows: List[Dict[str, Any]],
    landmines: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    costs: Dict[str, Any],
    rss: Dict[str, Any],
) -> Dict[str, Any]:
    counts = {"ok": 0, "warn": 0, "fail": 0}
    for lm in landmines:
        counts[lm["status"]] = counts.get(lm["status"], 0) + 1

    # Per-show latest episode from RSS audit
    latest_by_feed = {f["file"]: f.get("latest_pub_date") for f in rss.get("feeds", [])}

    # Overlay network_meta.yaml show_page overrides (dp_pod, age_of_ai, …).
    show_pages = dict(_SHOW_PAGE_BY_SLUG)
    meta_path = _ROOT / "shows" / "network_meta.yaml"
    if meta_path.exists():
        try:
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
            for mslug, entry in meta.items():
                if isinstance(entry, dict) and entry.get("show_page"):
                    show_pages[mslug] = entry["show_page"]
        except Exception:
            pass

    per_show_summary = []
    for s in shows:
        slug = s["slug"]
        cfg = s.get("cfg")
        if not cfg:
            per_show_summary.append({"slug": slug, "load_error": s.get("load_error")})
            continue
        rss_file = cfg.publishing.rss_file or ""
        latest_pub = latest_by_feed.get(rss_file)
        pub_status = "ok"
        thresholds = _PUB_AGE_THRESHOLDS_H.get(slug, _PUB_AGE_DEFAULT_H)
        if latest_pub and thresholds is not None:
            try:
                when = _dt.datetime.fromisoformat(latest_pub)
                age_hours = (
                    _dt.datetime.now(_dt.timezone.utc) - when
                ).total_seconds() / 3600
                warn_h, stale_h = thresholds
                if age_hours > stale_h:
                    pub_status = "stale"
                elif age_hours > warn_h:
                    pub_status = "warn"
            except Exception:
                pub_status = "unknown"
        elif thresholds is None:
            # On-demand shows (Age of AI): never paint red from silence.
            pub_status = "ok"
        cost_7 = costs["per_show"].get(slug, {}).get("last_7_days", {})
        m = metrics.get(slug, {})
        per_show_summary.append({
            "slug": slug,
            "name": cfg.name,
            "rss_file": rss_file,
            "rss_title": cfg.publishing.rss_title,
            "rss_image": cfg.publishing.rss_image,
            "show_page": show_pages.get(
                slug, slug.replace("_", "-") + ".html"),
            "blog_page": f"blog/{slug}/index.html",
            "newsletter_enabled": cfg.newsletter.enabled,
            "x_enabled": cfg.publishing.x_enabled,
            "latest_pub_date": latest_pub,
            "pub_status": pub_status,
            "cost_last_7_days_usd": cost_7.get("total", 0.0),
            "episodes_last_7_days": cost_7.get("episodes", 0),
            "p50_pipeline_s": m.get("p50_duration_s", 0.0),
            "success_rate": m.get("success_rate", 0.0),
        })

    stale = sum(1 for s in per_show_summary if s.get("pub_status") == "stale")
    return {
        "landmines_counts": counts,
        "shows_count": len(shows),
        "stale_shows": stale,
        "total_cost_last_7_days_usd": costs.get("network_last_7_days", {}).get("total", 0.0),
        "total_cost_last_30_days_usd": costs.get("network_last_30_days", {}).get("total", 0.0),
        "shows": per_show_summary,
    }


# ---------------------------------------------------------------------------
# Modern Investing performance aggregator — powers the website tables
# ---------------------------------------------------------------------------


def _normalize_mit_monthly_snapshots(snapshots: list) -> list:
    """Ensure every monthly snapshot dict has the keys expected by the
    public show page template and management.html, using safe defaults.

    This protects against historical snapshots written by the daily hook
    (which used a different/minimal schema) or any future writer drift.
    The three comparison percentages default to None (rendered as "—").
    """
    if not snapshots:
        return []
    normalized = []
    for s in snapshots:
        if not isinstance(s, dict):
            continue
        normalized.append({
            "month": s.get("month"),
            "trades": s.get("trades") if s.get("trades") is not None else s.get("total_trades", 0),
            "win_rate": s.get("win_rate") if s.get("win_rate") is not None else s.get("win_rate_pct", 0.0),
            "portfolio_pct": s.get("portfolio_pct"),
            "nasdaq_pct": s.get("nasdaq_pct"),
            "alpha_pct": s.get("alpha_pct"),
            "portfolio_pnl": s.get("portfolio_pnl") if s.get("portfolio_pnl") is not None else s.get("cumulative_pnl", 0.0),
            # preserve any extra fields
            **{k: v for k, v in s.items() if k not in {
                "month", "trades", "total_trades", "win_rate", "win_rate_pct",
                "portfolio_pct", "nasdaq_pct", "alpha_pct", "portfolio_pnl", "cumulative_pnl"
            }},
        })
    return normalized


def aggregate_mit_performance(root: Path) -> Dict[str, Any]:
    """Read the Modern Investing trackers and return a dashboard-ready dict.

    Consumed by ``build_dashboard`` under the ``mit_performance`` key.
    Rendered by ``management.html`` (operator) and the public
    ``modern-investing.html`` page via the ``templates/show_page.html.j2``
    template. Returns an empty-but-well-formed dict when the MIT files
    are missing so the caller can render "no data yet" gracefully.
    """
    mit_dir = root / "digests" / "modern_investing"
    tracker_path = mit_dir / "investment_tracker.json"
    taught_path = mit_dir / "taught_lessons.json"
    lessons_path = mit_dir / "lessons_learned.json"

    empty_payload: Dict[str, Any] = {
        "available": False,
        "summary": {},
        "benchmark": {},
        "alpha": {},
        "sectors": {},
        "monthly_snapshots": [],
        "trades": [],
        "lessons_learned": [],
        "taught_lessons_hot": [],
        "sector_concentration_warning": "",
        "last_updated": None,
    }

    if not tracker_path.exists():
        return empty_payload

    try:
        tracker = json.loads(tracker_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return empty_payload

    # Normalise trades — newest first, capped at 100 so a long-running
    # show doesn't bloat the dashboard JSON.
    trades_raw = tracker.get("trades") or []
    trades_normalised: List[Dict[str, Any]] = []
    for t in trades_raw:
        trades_normalised.append({
            "episode_num": t.get("episode_num"),
            "date": t.get("date"),
            "symbol": t.get("symbol"),
            "market": t.get("market"),
            "sector": t.get("sector") or "other",
            "strategy": t.get("strategy"),
            "trade_type": t.get("trade_type"),
            "status": t.get("status"),
            "entry_price": t.get("entry_price"),
            "exit_price": t.get("exit_price"),
            "pnl_pct": t.get("pnl_pct"),
            "pnl_dollars": t.get("pnl_dollars"),
            "nasdaq_entry": t.get("nasdaq_entry"),
            "nasdaq_exit": t.get("nasdaq_exit"),
            "nasdaq_return_pct": t.get("nasdaq_return_pct"),
            "alpha_pct": t.get("alpha_pct"),
            "lesson_tags": t.get("lesson_tags") or [],
            "lesson": t.get("lesson"),
            "confidence": t.get("confidence"),
        })
    trades_normalised.sort(
        key=lambda t: (t.get("date") or "", t.get("episode_num") or 0),
        reverse=True,
    )
    trades_normalised = trades_normalised[:100]

    # Sector concentration warning — mirrors the hook's 30% / 10-trade rule.
    sectors = tracker.get("sectors") or {}
    concentration_warning = ""
    threshold_pct = 30.0
    for sector, data in sectors.items():
        if not isinstance(data, dict):
            continue
        pct = float(data.get("exposure_pct") or 0.0)
        if pct >= threshold_pct:
            concentration_warning = (
                f"{sector}: {pct:.0f}% of recent trades "
                f"(cumulative P&L ${float(data.get('cumulative_pnl') or 0):+.2f})"
            )
            break

    # Lessons learned — active-only, newest-first, cap at 10.
    lessons_active: List[Dict[str, Any]] = []
    if lessons_path.exists():
        try:
            ll = json.loads(lessons_path.read_text(encoding="utf-8"))
            entries = [e for e in (ll.get("entries") or []) if e.get("status") == "active"]
            entries.sort(key=lambda e: e.get("date") or "", reverse=True)
            lessons_active = entries[:10]
        except (json.JSONDecodeError, OSError):
            lessons_active = []

    # Taught-lessons hot list — surfaces which mechanics are currently
    # under cooldown so the operator can spot a repetition trend.
    taught_hot: List[Dict[str, Any]] = []
    if taught_path.exists():
        try:
            taught = json.loads(taught_path.read_text(encoding="utf-8"))
            default_cooldown = int(taught.get("cooldown_days_default") or 21)
            today = _dt.date.today()
            for tag, meta in (taught.get("lessons") or {}).items():
                last = meta.get("last_date")
                if not last:
                    continue
                try:
                    last_d = _dt.date.fromisoformat(last)
                except ValueError:
                    continue
                cooldown = int(meta.get("cooldown_days") or default_cooldown)
                days_since = (today - last_d).days
                if days_since < cooldown:
                    taught_hot.append({
                        "tag": tag,
                        "count": int(meta.get("count") or 0),
                        "last_episode": meta.get("last_episode"),
                        "last_date": last,
                        "days_since": days_since,
                        "cools_in_days": max(cooldown - days_since, 0),
                    })
            taught_hot.sort(key=lambda x: x["days_since"])
        except (json.JSONDecodeError, OSError):
            taught_hot = []

    # Normalise benchmark/alpha sub-keys so the template can use
    # ``performance_data.benchmark.ytd_pct`` without tripping on
    # Jinja's Undefined sentinel on older tracker files. Non-finite
    # floats (yfinance NaN) become None — never 0 (MIT Ep117 / dashboard
    # Portfolio YTD tile was lying as "+0.00%" when both sides were NaN).
    import math as _math

    def _finite_or_none(v: Any) -> Any:
        if isinstance(v, (int, float)) and _math.isfinite(v):
            return v
        return None

    raw_bench = tracker.get("benchmark") or {}
    benchmark = {
        "current_close": _finite_or_none(raw_bench.get("current_close")),
        "inception_to_date_pct": _finite_or_none(
            raw_bench.get("inception_to_date_pct")),
        "ytd_pct": _finite_or_none(raw_bench.get("ytd_pct")),
        "last_updated": raw_bench.get("last_updated"),
    }
    raw_alpha = tracker.get("alpha") or {}
    alpha = {
        "inception_to_date_pct": _finite_or_none(
            raw_alpha.get("inception_to_date_pct")),
        "ytd_pct": _finite_or_none(raw_alpha.get("ytd_pct")),
        "monthly": raw_alpha.get("monthly") or {},
    }

    # Execution-layer health (July 2026 live-trading prep): signal
    # freshness + shadow-ledger vitals so the operator sees at a glance
    # whether the bridge artifacts are flowing. All best-effort.
    execution_health: Dict[str, Any] = {
        "signal": None,
        "shadow": None,
    }
    signal_path = mit_dir / "trade_signal_latest.json"
    if signal_path.exists():
        try:
            sig = json.loads(signal_path.read_text(encoding="utf-8"))
            gen = str(sig.get("generated_at") or "")[:10]
            age_days = None
            try:
                age_days = (_dt.date.today()
                            - _dt.date.fromisoformat(gen)).days
            except ValueError:
                pass
            execution_health["signal"] = {
                "generated_at": sig.get("generated_at"),
                "age_days": age_days,
                "action": sig.get("action"),
                "symbol": (sig.get("trade") or {}).get("snaptrade_symbol"),
                "stale": bool(age_days is not None and age_days > 1),
            }
        except (json.JSONDecodeError, OSError):
            pass
    shadow_path = mit_dir / "shadow_ledger.json"
    if shadow_path.exists():
        try:
            ledger = json.loads(shadow_path.read_text(encoding="utf-8"))
            orders = ledger.get("orders") or []
            decisions: Dict[str, int] = {}
            for o in orders:
                d = str(o.get("decision") or "?")
                decisions[d] = decisions.get(d, 0) + 1
            round_trips = [
                o.get("shadow_return_pct") for o in orders
                if o.get("decision") == "would_sell"
                and isinstance(o.get("shadow_return_pct"), (int, float))
            ]
            execution_health["shadow"] = {
                "orders": len(orders),
                "decisions": decisions,
                "round_trips": len(round_trips),
                "avg_round_trip_pct": (
                    round(sum(round_trips) / len(round_trips), 3)
                    if round_trips else None),
                "last_logged_at": orders[-1].get("logged_at") if orders else None,
            }
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "available": True,
        "summary": tracker.get("summary") or {},
        "benchmark": benchmark,
        "alpha": alpha,
        "sectors": sectors,
        "monthly_snapshots": _normalize_mit_monthly_snapshots(tracker.get("monthly_snapshots") or []),
        "trades": trades_normalised,
        "lessons_learned": lessons_active,
        "taught_lessons_hot": taught_hot,
        "sector_concentration_warning": concentration_warning,
        "execution_health": execution_health,
        "last_updated": (tracker.get("metadata") or {}).get("last_updated"),
    }


# ---------------------------------------------------------------------------
# Public entry point — called by tests AND by __main__
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Growth levers (Aug 2026) — channel trends, experiments in flight, stagger
# health, specials queue, data freshness. Everything here follows the funnel
# report's honesty rules: an unmeasured value is None, never 0, and every
# approximation says so in a note the card renders.
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _parse_iso(ts: str) -> Optional[_dt.datetime]:
    try:
        return _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def _iter_video_index_rows(root: Path):
    """Yield every row from every per-show video index (all channels).

    The indexes are the ONLY complete upload record — the Analytics API
    omits videos with zero activity, which is exactly how 53 of 72 FR
    launch uploads were invisible until Aug 2026. Dashboard math that
    needs "how many did we PUBLISH" must come from here, never from
    analytics rows.
    """
    for idx in sorted(root.glob("digests/*/youtube_videos*.json")):
        data = _load_json(idx)
        if not data:
            continue
        for v in data.get("videos", []):
            if isinstance(v, dict):
                yield v


def build_channel_scorecard(root: Path) -> Dict[str, Any]:
    """Per-channel week-over-week trend card (EN / RU / FR).

    The Aug 2026 review's headline (RU gaining ~9x EN's daily views on
    45% of the uploads; FR at ~zero) lived only in a one-off doc — this
    makes the channel race a permanent, trending surface. WoW deltas are
    the continuous-improvement signal; the zero-view share is the
    early-warning the FR launch lacked.
    """
    section: Dict[str, Any] = {"configured": False}
    stats = _load_json(root / "api" / "youtube_stats.json")
    if not stats or not stats.get("channels"):
        return section
    anchor = _parse_iso(stats.get("generated") or "")
    anchor_d = (anchor.date() if anchor else _dt.date.today())
    hist = _load_json(root / "api" / "youtube_channel_history.json") or {}
    hist_rows = hist.get("rows", [])

    # Complete upload counts (14d window ending at the analytics anchor)
    # from the indexes; analytics rows for the same window from stats.
    win_lo = (anchor_d - _dt.timedelta(days=14)).isoformat()
    win_hi = anchor_d.isoformat()
    uploads: Dict[str, int] = {}
    for v in _iter_video_index_rows(root):
        pub = str(v.get("published") or "")[:10]
        if win_lo <= pub <= win_hi:
            ch = str(v.get("channel") or "en")
            uploads[ch] = uploads.get(ch, 0) + 1
    rows_seen: Dict[str, int] = {}
    vpv: Dict[str, Dict[str, Any]] = {}
    for show in (stats.get("shows") or {}).values():
        for v in show.get("videos", []):
            pub = str(v.get("published") or "")[:10]
            if not (win_lo <= pub <= win_hi):
                continue
            ch = str(v.get("channel") or "en")
            rows_seen[ch] = rows_seen.get(ch, 0) + 1
            kind = "short" if v.get("kind") == "short" else "long"
            b = vpv.setdefault(ch, {}).setdefault(kind, {"n": 0, "views": 0})
            b["n"] += 1
            b["views"] += int(v.get("views") or 0)

    channels_out: Dict[str, Any] = {}
    for ch, c in (stats.get("channels") or {}).items():
        ds = [d for d in (c.get("day_series") or []) if isinstance(d, dict)]
        last7 = ds[-7:]
        prior7 = ds[-14:-7]
        v7 = sum(int(d.get("views") or 0) for d in last7)
        vp7 = sum(int(d.get("views") or 0) for d in prior7)
        subs7 = sum(int(d.get("subscribersGained") or 0)
                    - int(d.get("subscribersLost") or 0) for d in last7)
        subsp7 = sum(int(d.get("subscribersGained") or 0)
                     - int(d.get("subscribersLost") or 0) for d in prior7)
        up = uploads.get(ch, 0)
        seen = rows_seen.get(ch, 0)
        zero_share = (max(0.0, 1.0 - seen / up) if up else None)
        per_kind = {}
        for kind, b in (vpv.get(ch) or {}).items():
            per_kind[kind] = {
                "n": b["n"],
                "views_per_video": round(b["views"] / b["n"], 1) if b["n"] else None,
            }
        channels_out[ch] = {
            "subscribers": c.get("subscribers"),
            "views_7d": v7,
            "views_prior_7d": vp7,
            "views_wow_pct": (round(100.0 * (v7 - vp7) / vp7, 1) if vp7 else None),
            "subs_net_7d": subs7,
            "subs_net_prior_7d": subsp7,
            "uploads_14d": up,
            "analytics_rows_14d": seen,
            "zero_view_share_14d": (round(zero_share, 2)
                                    if zero_share is not None else None),
            "views_per_video_14d": per_kind,
        }
    # Subscriber trajectory from the committed history (per channel).
    subs_series: Dict[str, list] = {}
    for r in hist_rows:
        ch = str(r.get("channel") or "")
        if ch:
            subs_series.setdefault(ch, []).append(
                [r.get("date"), r.get("subscribers")])
    section = {
        "configured": True,
        "as_of": stats.get("generated"),
        "window_note": (
            "WoW = last 7 analytics days vs the 7 before, anchored to the "
            "analytics fetch. zero_view_share compares INDEX uploads (the "
            "complete record) with analytics rows — the API omits zero-"
            "activity videos, so this is the FR-launch early warning."),
        "channels": channels_out,
        "subscriber_series": {ch: s[-30:] for ch, s in subs_series.items()},
    }
    return section


_EXPERIMENT_STATUSES = {"reading", "decide", "done"}


def _experiment_live_metrics(root: Path) -> Dict[str, Any]:
    """Compute the small closed vocabulary of live experiment metrics.

    A metric that cannot be computed is None — the card must say
    "no data yet", never fake a zero (the funnel report's rule).
    """
    out: Dict[str, Any] = {}
    stats = _load_json(root / "api" / "youtube_stats.json") or {}
    anchor = _parse_iso(stats.get("generated") or "")
    anchor_d = (anchor.date() if anchor else _dt.date.today())
    win_lo = (anchor_d - _dt.timedelta(days=14)).isoformat()

    # EN long-form median retention over the last 14 analytics days.
    avps = []
    for show in (stats.get("shows") or {}).values():
        for v in show.get("videos", []):
            if (v.get("kind") == "long" and (v.get("channel") or "en") == "en"
                    and str(v.get("published") or "")[:10] >= win_lo
                    and v.get("average_view_percentage") is not None):
                avps.append(float(v["average_view_percentage"]))
    avps.sort()
    out["long_form_median_avp_en_14d"] = (
        round(avps[len(avps) // 2], 1) if avps else None)

    # Channel views WoW from the day series.
    for ch in ("en", "ru"):
        ds = ((stats.get("channels") or {}).get(ch) or {}).get("day_series") or []
        v7 = sum(int(d.get("views") or 0) for d in ds[-7:])
        vp7 = sum(int(d.get("views") or 0) for d in ds[-14:-7])
        out[f"channel_views_wow_{ch}"] = (
            round(100.0 * (v7 - vp7) / vp7, 1) if vp7 else None)

    # Best short/long vpd per channel from the adaptive policy. The long
    # variants read out the Aug 2026 dub long-form probe (tesla/spacex/FF
    # publish RU+FR longs via dub_force_long_channels).
    policy = _load_json(root / "api" / "youtube_policy.json") or {}
    for ch in ("fr", "ru"):
        for kind in ("short", "long"):
            vals = [v.get(f"{kind}_vpd")
                    for v in ((policy.get("channels") or {}).get(ch) or {}).values()
                    if isinstance(v, dict) and v.get(f"{kind}_vpd") is not None]
            out[f"{ch}_{kind}_vpd_max"] = (round(max(vals), 2) if vals else None)

    # Fragment share of RU/FR window-Short titles (2nd/3rd Shorts) in the
    # last 14 days. Heuristic mirror of the defect: a title whose first
    # letter is lowercase started mid-sentence.
    frag = total = 0
    for v in _iter_video_index_rows(root):
        if v.get("kind") != "short":
            continue
        if (v.get("channel") or "en") not in ("ru", "fr"):
            continue
        if str(v.get("published") or "")[:10] < win_lo:
            continue
        title = str(v.get("title") or "").strip()
        m = re.search(r"[A-Za-zА-Яа-яЁё]", title)
        if not m:
            continue
        total += 1
        if m.group(0).islower():
            frag += 1
    out["dub_fragment_title_share_14d"] = (
        round(frag / total, 2) if total else None)

    # Long-form open hold (Aug 2026, from the retention CURVES): mean
    # audienceWatchRatio at 5% elapsed across the EN longs that carry a
    # curve. The 2026-08-17 baseline read ~0.50 — half the audience gone
    # inside the first ~30-45 s — making the open the dominant remaining
    # retention lever. None until curves exist.
    holds = []
    for show in (stats.get("shows") or {}).values():
        for v in show.get("videos", []):
            curve = v.get("retention_curve")
            if not curve or (v.get("channel") or "en") != "en":
                continue
            try:
                pts = {float(p["t"]): float(p["ratio"]) for p in curve}
                k = min(pts, key=lambda t: abs(t - 0.05))
                holds.append(pts[k])
            except (KeyError, TypeError, ValueError):
                continue
    out["long_open_hold_5pct_en"] = (
        round(sum(holds) / len(holds), 2) if holds else None)
    return out


def build_retention_curves_section(root: Path) -> Dict[str, Any]:
    """Where long-form viewers actually LEAVE, from the per-video
    audience-retention curves the analytics fetch collects for each
    channel's top recent longs (Aug 2026). Renders as a dashboard card;
    the honest-null rules apply — no curves means an unconfigured card,
    never zeros.
    """
    stats = _load_json(root / "api" / "youtube_stats.json") or {}
    rows: List[Dict[str, Any]] = []
    by_channel: Dict[str, List[float]] = {}
    for dir_name, show in (stats.get("shows") or {}).items():
        for v in show.get("videos", []):
            curve = v.get("retention_curve")
            if not curve:
                continue
            try:
                pts = {float(p["t"]): float(p["ratio"]) for p in curve}

                def at(t, _p=pts):
                    return _p[min(_p, key=lambda x: abs(x - t))]

                ch = (v.get("channel") or "en").lower()
                row = {
                    "show": dir_name,
                    "channel": ch,
                    "episode": v.get("episode"),
                    "views": v.get("views"),
                    "hold_5pct": round(at(0.05), 2),
                    "hold_10pct": round(at(0.10), 2),
                    "hold_25pct": round(at(0.25), 2),
                    "hold_50pct": round(at(0.50), 2),
                }
                rows.append(row)
                by_channel.setdefault(ch, []).append(row["hold_5pct"])
            except (KeyError, TypeError, ValueError):
                continue
    if not rows:
        return {"configured": False,
                "note": "No retention curves yet — they accrue from the "
                        "nightly analytics fetch (top 5 recent longs per "
                        "channel)."}
    rows.sort(key=lambda r: -(r.get("views") or 0))
    return {
        "configured": True,
        "as_of": stats.get("generated"),
        "note": ("audienceWatchRatio at 5/10/25/50% elapsed. The 5% mark "
                 "is ~30-45 s in — the open cliff. Baseline 2026-08-17: "
                 "EN mean ~0.50 at 5%."),
        "mean_hold_5pct_by_channel": {
            ch: round(sum(v) / len(v), 2) for ch, v in by_channel.items()},
        "videos": rows[:20],
    }


def build_experiments_section(root: Path) -> Dict[str, Any]:
    """Levers in flight — docs/experiments.yaml + live metric snapshots.

    The registry is the discipline ('one variable at a time; know your
    readout date before you ship'); the dashboard renders it so decision
    dates cannot silently slip past.
    """
    section: Dict[str, Any] = {"configured": False}
    path = root / "docs" / "experiments.yaml"
    if not path.exists():
        return section
    try:
        import yaml as _yaml
        data = _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries = data.get("experiments") or []
        metrics = _experiment_live_metrics(root)
        today = _dt.date.today()
        rows = []
        for e in entries:
            if not isinstance(e, dict) or not e.get("id"):
                continue
            readout = None
            try:
                readout = _dt.date.fromisoformat(str(e.get("readout")))
            except Exception:  # noqa: BLE001
                pass
            status = str(e.get("status") or "reading")
            days = (readout - today).days if readout else None
            rows.append({
                "id": e.get("id"),
                "title": e.get("title"),
                "area": e.get("area"),
                "shipped": e.get("shipped"),
                "readout": e.get("readout"),
                "status": (status if status in _EXPERIMENT_STATUSES
                           else "reading"),
                "days_to_readout": days,
                "overdue": bool(readout and days is not None and days < 0
                                and status != "done"),
                "metric": e.get("metric"),
                "baseline": e.get("baseline"),
                "value": metrics.get(str(e.get("metric") or "")),
                "target": e.get("target"),
                "criteria": e.get("criteria"),
                "notes": e.get("notes"),
            })
        rows.sort(key=lambda r: (r["status"] == "done", r["readout"] or "9999"))
        section = {
            "configured": True,
            "registry": "docs/experiments.yaml",
            "experiments": rows,
            "overdue_count": sum(1 for r in rows if r["overdue"]),
        }
    except Exception as exc:  # noqa: BLE001
        section = {"configured": True, "error": str(exc)}
    return section


def build_stagger_section(root: Path) -> Dict[str, Any]:
    """Staggered-Shorts health: is the feature engaged, and is the
    deferred-comment sweep keeping up?

    A pending comment whose publish time passed > 48h ago means the sweep
    is broken (tokens, workflow, or the whitelist landmine) — that gets a
    warning the alert band picks up, because a silently-dead sweep is a
    silent funnel degradation.
    """
    now = _dt.datetime.now(_dt.timezone.utc)
    shows_out = []
    pending_total = posted_total = 0
    oldest_overdue_h: Optional[float] = None
    for path in sorted(root.glob("digests/*/scheduled_comments.json")):
        data = _load_json(path)
        if data is None:
            continue
        pend = [e for e in data.get("pending", []) if isinstance(e, dict)]
        posted = int(data.get("posted_total", 0) or 0)
        overdue_h = None
        for e in pend:
            due = _parse_iso(e.get("publish_at") or "")
            if due and due < now:
                h = (now - due).total_seconds() / 3600.0
                overdue_h = max(overdue_h or 0.0, h)
        shows_out.append({
            "slug": path.parent.name,
            "pending": len(pend),
            "posted_total": posted,
            "max_overdue_hours": (round(overdue_h, 1)
                                  if overdue_h is not None else None),
        })
        pending_total += len(pend)
        posted_total += posted
        if overdue_h is not None:
            oldest_overdue_h = max(oldest_overdue_h or 0.0, overdue_h)
    stuck = bool(oldest_overdue_h and oldest_overdue_h > 48)
    return {
        "configured": bool(shows_out),
        "shows": shows_out,
        "pending_total": pending_total,
        "posted_total": posted_total,
        "max_overdue_hours": (round(oldest_overdue_h, 1)
                              if oldest_overdue_h is not None else None),
        "sweep_stuck": stuck,
        "note": ("Comments queue while a scheduled Short is private and are "
                 "posted by the multilingual/nightly sweeps once it goes "
                 "public. Entries kept 7 days; overdue > 48h = sweep broken."),
    }


def build_specials_section(root: Path) -> Dict[str, Any]:
    """Deep-dive specials queues — produced history + ready-to-dispatch."""
    produced, pending = [], []
    for path in sorted(root.glob("shows/deep_dives/*.yaml")):
        data = None
        try:
            import yaml as _yaml
            data = _yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        show = path.stem
        for e in (data or {}).get("queue", []):
            if not isinstance(e, dict):
                continue
            row = {"show": show, "id": e.get("id"), "title": e.get("title"),
                   "category": e.get("category")}
            if e.get("produced"):
                row["episode_number"] = e.get("episode_number")
                row["produced_date"] = e.get("produced_date")
                produced.append(row)
            else:
                pending.append(row)
    produced.sort(key=lambda r: str(r.get("produced_date") or ""), reverse=True)
    return {
        "configured": bool(produced or pending),
        "pending": pending,
        "produced": produced[:8],
        "dispatch_hint": ("Actions → Run Podcast Show → show=<show> + "
                          "deep_dive=<id>"),
    }


def build_freshness_section(root: Path) -> Dict[str, Any]:
    """Age of every analytics input, with a warning past 36h.

    The Aug 6 GitHub outage killed a nightly and every downstream number
    silently went a day stale — the operator had no surface saying so.
    Staleness is now a rendered fact, and > 36h raises an alert.
    """
    now = _dt.datetime.now(_dt.timezone.utc)
    sources = {
        "youtube_stats": ("api/youtube_stats.json", "generated"),
        "youtube_policy": ("api/youtube_policy.json", "generated"),
        "op3_stats": ("api/op3_stats.json", "fetched_at"),
        "funnel": ("api/funnel.json", "generated_at"),
    }
    out: Dict[str, Any] = {}
    stale = []
    for name, (rel, key) in sources.items():
        data = _load_json(root / rel)
        ts = _parse_iso((data or {}).get(key) or "")
        if ts is None:
            out[name] = {"age_hours": None, "as_of": None}
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=_dt.timezone.utc)
        age = round((now - ts).total_seconds() / 3600.0, 1)
        out[name] = {"age_hours": age, "as_of": ts.isoformat()}
        if age > 36:
            stale.append(f"{name} is {age:.0f}h old")
    return {"sources": out, "stale": stale, "warn_after_hours": 36}


# ---------------------------------------------------------------------------
# Industry benchmarks + investor view (Aug 2026)
#
# Two sections that put the network's numbers NEXT TO the market's:
#   - "benchmarks": where each show and the network sit against published
#     podcast-industry percentiles, CPM ranges and production costs.
#   - "investor": what has been built (asset inventory with market-comp
#     framing) and honest now / 1-year / 5-year value scenarios.
#
# All external figures come from docs/industry_benchmarks.yaml (one file,
# provenance rendered), all internal figures from the same sections the
# rest of the dashboard uses. House honesty rules apply throughout:
# unmeasured = null (never 0), ranges stay ranges, projections are
# labelled scenarios with their assumptions serialized next to them.
# ---------------------------------------------------------------------------


def _load_industry_benchmarks(root: Path) -> Optional[Dict[str, Any]]:
    path = root / "docs" / "industry_benchmarks.yaml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


_PUBDATE_RE = re.compile(r"<pubDate>([^<]+)</pubDate>")


def _feed_episodes_last_7d(root: Path, network: Dict[str, Any]) -> Dict[str, int]:
    """Count episodes each show actually PUBLISHED in the last 7 days,
    from its RSS feed's pubDates.

    The cost rollup's ``episodes_last_7_days`` counts credit_usage FILES,
    which include multilingual dub tracks and re-runs — using it as the
    per-episode-downloads denominator understated every show's placement
    (145 "episodes"/week vs ~90 real ones). The feed is the publication
    record, so it is the denominator.
    """
    now = _dt.datetime.now(_dt.timezone.utc)
    out: Dict[str, int] = {}
    for s in (network or {}).get("shows", []):
        slug, rss_file = s.get("slug"), s.get("rss_file")
        if not slug or not rss_file:
            continue
        path = root / rss_file
        if not path.exists():
            continue
        count = 0
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            for raw in _PUBDATE_RE.findall(text):
                when = _parse_rfc822(raw.strip())
                if when is None:
                    continue
                if when.tzinfo is None:
                    when = when.replace(tzinfo=_dt.timezone.utc)
                if (now - when).total_seconds() <= 7 * 86400:
                    count += 1
        except Exception:
            continue
        out[slug] = count
    return out


def _percentile_band(dl_7d: float, ladder: Dict[str, Any]) -> str:
    """Map a first-7-days download count onto the industry ladder."""
    try:
        if dl_7d >= float(ladder.get("top_1pct", 4615)):
            return "top 1%"
        if dl_7d >= float(ladder.get("top_5pct", 1029)):
            return "top 5%"
        if dl_7d >= float(ladder.get("top_10pct", 434)):
            return "top 10%"
        if dl_7d >= float(ladder.get("top_25pct", 119)):
            return "top 25%"
        if dl_7d >= float(ladder.get("median", 28)):
            return "top 50%"
        return "below median"
    except (TypeError, ValueError):
        return "unknown"


def build_benchmarks_section(
    root: Path,
    *,
    audience: Dict[str, Any],
    costs: Dict[str, Any],
    network: Dict[str, Any],
) -> Dict[str, Any]:
    bm = _load_industry_benchmarks(root)
    if not bm:
        return {"configured": False}

    ladder = bm.get("podcast_episode_downloads_7d_percentiles") or {}
    op3 = (audience or {}).get("op3") or {}
    section: Dict[str, Any] = {
        "configured": True,
        "as_of": bm.get("as_of"),
        "sources": bm.get("sources") or [],
        "ladder": ladder,
        "method_note": (
            "Per-episode figure = a show's OP3 downloads over the last 7 "
            "days ÷ episodes it published in those 7 days. That is a proxy "
            "for the industry's 'downloads in an episode's first 7 days' "
            "(back-catalog listening inflates it slightly; binge listening "
            "deflates it). Unmeasured shows report null, never 0."
        ),
    }

    # Per-show placement. Episodes counted from each show's RSS feed
    # (the publication record), NOT credit files — see
    # _feed_episodes_last_7d for why.
    episodes_by_slug = _feed_episodes_last_7d(root, network)
    per_show: Dict[str, Any] = {}
    op3_per_show = op3.get("per_show") or {}
    for slug, row in op3_per_show.items():
        eps = episodes_by_slug.get(slug) or 0
        dl7 = row.get("downloads_7d")
        if not eps or dl7 is None:
            per_show[slug] = {
                "dl_per_episode_7d": None,
                "percentile_band": None,
                "episodes_7d": eps,
            }
            continue
        per_ep = round(float(dl7) / max(1, eps), 1)
        per_show[slug] = {
            "dl_per_episode_7d": per_ep,
            "percentile_band": _percentile_band(per_ep, ladder),
            "episodes_7d": eps,
        }
    section["per_show"] = per_show

    # Network-level placement + trailing growth.
    total_eps_7d = sum(episodes_by_slug.values())
    net_dl7 = op3.get("network_downloads_7d")
    net_per_ep = (
        round(float(net_dl7) / total_eps_7d, 1)
        if (op3.get("configured") and net_dl7 is not None and total_eps_7d)
        else None
    )
    weekly = [
        float(r[1] or 0) for r in (op3.get("network_weekly_history") or [])
    ]
    # Median week-over-week growth over the last up-to-8 complete pairs —
    # median rather than mean so one outage week can't fake a trend.
    # Pairs are built from the full series FIRST and then windowed;
    # slicing each side separately misaligns when history is shorter
    # than the window (every week paired with itself → 0% growth).
    wow: List[float] = []
    for a, b in list(zip(weekly[:-1], weekly[1:]))[-8:]:
        if a > 0:
            wow.append(100.0 * (b - a) / a)
    wow_median = round(sorted(wow)[len(wow) // 2], 1) if wow else None

    # Cost per PUBLISHED episode: tracked 7d Grok+TTS spend ÷ episodes
    # the feeds actually gained. The projections' avg is per credit FILE
    # (which include dub tracks), so it reads lower than reality.
    spend_7d = (costs.get("network_last_7_days") or {}).get("total")
    cost_per_episode = (
        round(float(spend_7d) / total_eps_7d, 2)
        if spend_7d and total_eps_7d else None
    )
    prod = bm.get("production_cost_per_episode_usd") or {}
    full_service = prod.get("full_service") or [None, None]
    cost_advantage = None
    if cost_per_episode and full_service[0]:
        cost_advantage = [
            int(float(full_service[0]) / cost_per_episode),
            int(float(full_service[1]) / cost_per_episode),
        ]
    section["network"] = {
        "dl_per_episode_7d": net_per_ep,
        "percentile_band": (
            _percentile_band(net_per_ep, ladder) if net_per_ep is not None
            else None
        ),
        "episodes_7d": total_eps_7d,
        "wow_growth_median_pct": wow_median,
        "cost_per_episode_usd": cost_per_episode,
        "cost_note": (
            "Tracked Grok + TTS spend ÷ episodes published to the feeds "
            "in the same 7 days. Untracked lines (Grok Imagine imagery, "
            "some multilingual) roughly double it — still three orders "
            "of magnitude under market rates."
        ),
        "industry_cost_per_episode_usd": prod,
        "cost_advantage_x": cost_advantage,
        "industry_structure": bm.get("industry_structure") or {},
    }

    # Monetization capacity — illustrative only (the network runs no ads).
    cpm = bm.get("podcast_cpm_usd") or {}
    prog = cpm.get("programmatic") or [None, None]
    host = cpm.get("host_read_midtier") or [None, None]
    dl30 = op3.get("network_downloads_30d")
    podcast_cap = None
    if op3.get("configured") and dl30 and prog[0] and host[1]:
        annual_impressions = float(dl30) * 12.0 / 1000.0
        podcast_cap = [
            int(annual_impressions * float(prog[0]) * 1),   # 1 programmatic slot
            int(annual_impressions * float(host[1]) * 2),   # 2 host-read slots
        ]
    ytb = (audience or {}).get("youtube") or {}
    rpm = (bm.get("youtube") or {}).get("blended_rpm_usd") or [None, None]
    yt_cap = None
    views_window = ytb.get("network_views")
    window_days = ytb.get("window_days") or 90
    if ytb.get("configured") and views_window and rpm[0]:
        annual_views_k = float(views_window) * (365.0 / window_days) / 1000.0
        yt_cap = [int(annual_views_k * float(rpm[0])),
                  int(annual_views_k * float(rpm[1]))]
    section["monetization_capacity"] = {
        "monthly_downloads": dl30 if op3.get("configured") else None,
        "podcast_ads_annual_usd": podcast_cap,
        "youtube_annual_usd": yt_cap,
        "cpm_assumptions": {"programmatic": prog, "host_read": host,
                            "youtube_rpm": rpm},
        "note": (
            "Illustrative capacity if inventory were sold at 2026 industry "
            "rates — the network currently runs ZERO ads by design. Podcast "
            "range = 1 programmatic slot at the low CPM to 2 host-read "
            "slots at the high CPM."
        ),
    }
    return section


def _grow(value: float, monthly_pct: float, months: int) -> float:
    return value * ((1.0 + monthly_pct / 100.0) ** months)


def build_investor_section(
    root: Path,
    *,
    audience: Dict[str, Any],
    costs: Dict[str, Any],
    catalog: Dict[str, Any],
    lake: Dict[str, Any],
    gallery: Dict[str, Any],
    network: Dict[str, Any],
    benchmarks: Dict[str, Any],
) -> Dict[str, Any]:
    bm = _load_industry_benchmarks(root)
    if not bm or not benchmarks.get("configured"):
        return {"configured": False}

    op3 = (audience or {}).get("op3") or {}
    ytb = (audience or {}).get("youtube") or {}
    nl = (audience or {}).get("newsletter") or {}
    episodes_to_date = (catalog or {}).get("network_episodes_to_date") or 0
    shows_count = (catalog or {}).get("shows_count") or 0
    # Real published episodes/week + per-episode cost from the feeds
    # (via benchmarks), not credit-file counts — see _feed_episodes_last_7d.
    eps_per_week = (benchmarks.get("network") or {}).get("episodes_7d") or 0
    avg_cost = (benchmarks.get("network") or {}).get("cost_per_episode_usd")

    prod = bm.get("production_cost_per_episode_usd") or {}
    boutique = prod.get("boutique_agency") or [200, 400]
    library_replacement = (
        [int(episodes_to_date * boutique[0]),
         int(episodes_to_date * boutique[1])]
        if episodes_to_date else None
    )
    # Finished-audio estimate from transcript words at a 150 wpm speaking
    # rate — an estimate, and labelled as one.
    total_words = ((lake or {}).get("stats") or {}).get("total_words") or 0
    audio_hours_est = int(total_words / 150 / 60) if total_words else None

    val = bm.get("valuation") or {}
    nl_per_sub = val.get("newsletter_value_per_free_subscriber_usd") or [1, 8]
    ma_multiple = val.get("podcast_ma_revenue_multiple") or [1, 4]

    yt_subs = sum(
        (c or {}).get("subscribers") or 0
        for c in (ytb.get("channels") or {}).values()
    )
    yt_views_lifetime = sum(
        (c or {}).get("total_views") or 0
        for c in (ytb.get("channels") or {}).values()
    )

    assets = [
        {
            "label": "Content library",
            "value": (f"{episodes_to_date:,} episodes"
                      + (f" · ~{audio_hours_est:,} h finished audio (est.)"
                         if audio_hours_est else "")),
            "framing": (
                "Replacement cost at boutique-agency production rates "
                f"(${boutique[0]}–${boutique[1]}/episode) — what a "
                "traditional studio would charge to produce this catalog."
            ),
            "usd_range": library_replacement,
        },
        {
            "label": "Production engine",
            "value": (f"{shows_count} shows · ~{eps_per_week}/wk · "
                      + (f"${avg_cost:.2f}/episode marginal cost"
                         if avg_cost else "cost not measured")),
            "framing": (
                "Fully autonomous pipeline: fetch → write → voice → mix → "
                "video → publish → analytics → self-review, in 5 languages, "
                "with no per-episode human labor. The engine, not any one "
                "show, is the core asset — a 17th show costs one YAML file."
            ),
            "usd_range": None,
        },
        {
            "label": "Audience & channels",
            "value": (
                f"{(op3.get('network_downloads_30d') or 0):,} podcast "
                f"downloads/30d · {yt_subs:,} YouTube subs · "
                f"{yt_views_lifetime:,} lifetime views · "
                f"{(nl.get('subscriber_count') or 0):,} newsletter subs"
            ),
            "framing": (
                "Early but compounding: distribution live on Apple, "
                "Spotify and 3 YouTube channels; every video ends on a "
                "funnel-tagged site showcase feeding the newsletter."
            ),
            "usd_range": None,
        },
        {
            "label": "Image & data assets",
            "value": (
                f"{((gallery or {}).get('image_count') or 0):,} CC-licensed "
                "images · full-text content lake · per-episode analytics "
                "joined across 6 platforms"
            ),
            "framing": (
                "The feedback loops (retention-ranked imagery, adaptive "
                "publishing policy, experiment registry) compound output "
                "quality without adding headcount."
            ),
            "usd_range": None,
        },
    ]

    # ---- Value scenarios: now / 1 year / 5 years ----
    dl30 = op3.get("network_downloads_30d") if op3.get("configured") else None
    scenarios: Dict[str, Any] = {"configured": dl30 is not None}
    if dl30 is not None:
        cpm = bm.get("podcast_cpm_usd") or {}
        prog_lo = float((cpm.get("programmatic") or [12])[0])
        host_hi = float((cpm.get("host_read_midtier") or [25, 50])[1])

        def capacity(monthly_dl: float) -> List[int]:
            impressions_k = monthly_dl * 12.0 / 1000.0
            return [int(impressions_k * prog_lo * 1),
                    int(impressions_k * host_hi * 2)]

        def ev(cap: List[int]) -> List[int]:
            return [int(cap[0] * ma_multiple[0]), int(cap[1] * ma_multiple[1])]

        # Growth assumptions: deliberately DETACHED from the hot trailing
        # trend (recently ~double-digit weekly), because extrapolating a
        # small base's hot streak for years is how dishonest decks are
        # made. Year 1 runs at the named monthly rate; years 2-5 taper to
        # the long-run rate. All three are scenarios, not forecasts.
        specs = [
            {"name": "hold", "y1_monthly_pct": 0.0, "later_monthly_pct": 0.0,
             "story": "growth stops today; the factory keeps publishing"},
            {"name": "base", "y1_monthly_pct": 5.0, "later_monthly_pct": 2.0,
             "story": "5%/mo year one, tapering to 2%/mo"},
            {"name": "upside", "y1_monthly_pct": 10.0, "later_monthly_pct": 3.0,
             "story": "10%/mo year one, tapering to 3%/mo"},
        ]
        eps_y1 = episodes_to_date + eps_per_week * 52
        eps_y5 = episodes_to_date + eps_per_week * 52 * 5
        rows = []
        for spec in specs:
            dl_y1 = _grow(float(dl30), spec["y1_monthly_pct"], 12)
            dl_y5 = _grow(dl_y1, spec["later_monthly_pct"], 48)
            cap_now = capacity(float(dl30))
            cap_y1 = capacity(dl_y1)
            cap_y5 = capacity(dl_y5)
            rows.append({
                "name": spec["name"],
                "story": spec["story"],
                "downloads_month": {"now": int(dl30), "y1": int(dl_y1),
                                    "y5": int(dl_y5)},
                "revenue_capacity_annual_usd": {
                    "now": cap_now, "y1": cap_y1, "y5": cap_y5},
                "implied_ev_usd": {
                    "now": ev(cap_now), "y1": ev(cap_y1), "y5": ev(cap_y5)},
            })
        scenarios.update({
            "rows": rows,
            "library": {
                "episodes": {"now": episodes_to_date, "y1": eps_y1,
                             "y5": eps_y5},
                "replacement_usd": {
                    "now": library_replacement,
                    "y1": [eps_y1 * boutique[0], eps_y1 * boutique[1]],
                    "y5": [eps_y5 * boutique[0], eps_y5 * boutique[1]],
                },
            },
            "assumptions": [
                "Scenarios, not forecasts — none of this is booked revenue.",
                ("Revenue capacity = monthly downloads × 12 ÷ 1,000 × CPM × "
                 f"slots (low: 1 programmatic slot at ${prog_lo:.0f} CPM; "
                 f"high: 2 host-read slots at ${host_hi:.0f} CPM). The "
                 "network currently sells zero ads."),
                (f"Implied EV applies the {ma_multiple[0]}–{ma_multiple[1]}x "
                 "revenue multiple observed across 2020-24 podcast M&A to "
                 "that capacity IF it were realized."),
                ("Episode counts assume the current cadence "
                 f"(~{eps_per_week}/week) simply continues — the factory's "
                 "marginal cost makes that the default, not a stretch."),
                (f"Library replacement value prices episodes at boutique "
                 f"production rates (${boutique[0]}–${boutique[1]}). It is "
                 "a cost-basis framing, not a resale price."),
                (f"Trailing reality check: median WoW download growth over "
                 "recent weeks is "
                 f"{benchmarks.get('network', {}).get('wow_growth_median_pct')}"
                 "% — the scenarios deliberately assume much less."),
            ],
        })
    section = {
        "configured": True,
        "as_of": bm.get("as_of"),
        "thesis": {
            "shows": shows_count,
            "episodes_per_week": eps_per_week,
            "episodes_to_date": episodes_to_date,
            "languages": None,  # filled by caller (needs multilingual)
            "cost_per_episode_usd": avg_cost,
            "newsletter_per_sub_usd": nl_per_sub,
        },
        "assets": assets,
        "scenarios": scenarios,
    }
    return section


def build_dashboard(root: Path, *, offline: bool = False, previous_flat: Optional[int] = None) -> Dict[str, Any]:
    shows = load_shows_from_yaml(root / "shows", root)
    rss = audit_rss_enclosures(root, offline=offline)
    voice = audit_voice_config(shows, root)

    metrics = aggregate_metrics(root, shows)
    costs = aggregate_costs(root, shows)

    landmines: List[Dict[str, Any]] = [
        item_1_repo_size(root),
        item_2_rss_integrity(rss),
        item_3_legacy_flatfiles(root, previous=previous_flat),
        item_4_output_dirs(shows),
        item_5_nested_digests(root),
        item_6_formatted_md(root),
        item_8_feature_flags(shows),
        item_9_voice_settings(voice),
        item_11_tts_provider(shows),
        item_12_summaries_location(shows),
        item_13_youtube_health(shows),
        # item_22 depends on metrics, so it goes last (and metrics is
        # computed above so the dependency holds).
        item_22_grok_imagine_health(shows, metrics),
    ]

    network = build_network_rollup(shows, landmines, metrics, costs, rss)

    # Strip the ShowConfig object out of per-show entries before serialising.
    serializable_shows: List[Dict[str, Any]] = []
    for s in shows:
        cfg = s.get("cfg")
        serializable_shows.append({
            "slug": s["slug"],
            "name": s["name"],
            "yaml_path": s.get("yaml_path"),
            "load_error": s.get("load_error"),
            "rss_file": (cfg.publishing.rss_file if cfg else None),
            "rss_image": (cfg.publishing.rss_image if cfg else None),
            "newsletter_enabled": (cfg.newsletter.enabled if cfg else False),
            "x_enabled": (cfg.publishing.x_enabled if cfg else None),
        })

    alerts = extract_critical_alerts(landmines, costs)

    # Growth-lever alerts (Aug 2026): a stuck comment sweep and stale
    # analytics are both silent-degradation classes this week surfaced —
    # they belong in the band, not buried in a card.
    stagger = build_stagger_section(root)
    freshness = build_freshness_section(root)
    if stagger.get("sweep_stuck"):
        alerts.append({
            "severity": "warn",
            "message": (f"Scheduled-Short comment sweep looks stuck: oldest "
                        f"queued comment is {stagger.get('max_overdue_hours')}h "
                        "past its Short's publish time (check the multilingual/"
                        "nightly sweep + channel tokens)."),
        })
    for msg in freshness.get("stale", []):
        alerts.append({
            "severity": "warn",
            "message": f"Analytics staleness: {msg} — downstream cards and "
                       "the adaptive policy are reading old data.",
        })
    experiments = build_experiments_section(root)
    if experiments.get("overdue_count"):
        alerts.append({
            "severity": "warn",
            "message": (f"{experiments['overdue_count']} experiment(s) past "
                        "their readout date in docs/experiments.yaml — read "
                        "the result and update status, or the discipline rots."),
        })

    audience = build_audience_section(root)
    efficiency = build_efficiency_section(costs, audience)

    multilingual = aggregate_multilingual(root, shows)
    catalog_section = build_catalog_section(root, shows, rss)
    lake_section = build_content_lake_section(root)
    gallery_section = build_gallery_section(root)

    # Industry benchmarks + investor view (Aug 2026): built from the
    # sections above so every comparison uses the same numbers the rest
    # of the dashboard renders.
    benchmarks = build_benchmarks_section(
        root, audience=audience, costs=costs, network=network)
    investor = build_investor_section(
        root, audience=audience, costs=costs, catalog=catalog_section,
        lake=lake_section, gallery=gallery_section, network=network,
        benchmarks=benchmarks)
    if investor.get("configured"):
        langs = {"en"}
        for entry in (multilingual.get("per_show") or {}).values():
            for lang in entry.get("languages") or []:
                langs.add(str(lang))
        investor["thesis"]["languages"] = len(langs)

    return {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "network": network,
        "shows": serializable_shows,
        "landmines": landmines,
        "alerts": alerts,
        "voice_config": voice,
        "cost_rollup": costs,
        "multilingual": multilingual,
        "pipeline_health": metrics,
        "rss_audit": rss,
        "mit_performance": aggregate_mit_performance(root),
        "audience": audience,
        "efficiency": efficiency,
        "catalog": catalog_section,
        "gallery": gallery_section,
        "content_lake": lake_section,
        "distribution": build_distribution_section(root),
        "youtube_policy": build_youtube_policy_section(root),
        "retention_curves": build_retention_curves_section(root),
        "funnel": build_funnel_section(root),
        "benchmarks": benchmarks,
        "investor": investor,
        # Growth levers (Aug 2026): trends, experiments, stagger, specials.
        "growth": {
            "channel_scorecard": build_channel_scorecard(root),
            "experiments": experiments,
            "shorts_stagger": stagger,
            "specials": build_specials_section(root),
            "freshness": freshness,
        },
    }


def _merge_op3_history(
    root: Path,
    fetched_at: Optional[str],
    per_show: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Accumulate OP3's rolling 4-week series into api/op3_history.json.

    OP3 has no all-time endpoint — it exposes ``weeklyDownloads``
    (w-3 … w0, w0 = the week containing the fetch date). Each dashboard
    build overwrites those four ISO weeks in the history file (they are
    authoritative and w0 is still growing) and leaves older weeks frozen,
    yielding an ever-more-complete weekly ledger. All-time totals are the
    sum over stored weeks, i.e. "since history tracking began".

    NOTE the file must stay in nightly-maintenance.yml's safe-commit-push
    add-paths whitelist — the youtube_channel_history landmine (July 22
    2026 pass) was exactly a history file written but never committed.

    Returns {"network_total", "per_show_totals", "since", "network_series"}.
    Best-effort: any failure returns zeros without breaking the dashboard.
    """
    empty = {"network_total": 0, "per_show_totals": {}, "since": None,
             "network_series": []}
    try:
        # Anchor w0 to the Monday of the week containing the fetch date.
        try:
            fetch_date = _dt.date.fromisoformat(str(fetched_at)[:10])
        except (ValueError, TypeError):
            fetch_date = _dt.date.today()
        monday_w0 = fetch_date - _dt.timedelta(days=fetch_date.weekday())

        hist_path = root / "api" / "op3_history.json"
        weeks: Dict[str, Dict[str, int]] = {}
        if hist_path.exists():
            try:
                stored = json.loads(hist_path.read_text(encoding="utf-8"))
                if isinstance(stored.get("weeks"), dict):
                    weeks = {
                        wk: {s: int(n) for s, n in row.items()
                             if isinstance(n, (int, float))}
                        for wk, row in stored["weeks"].items()
                        if isinstance(row, dict)
                    }
            except Exception:  # noqa: BLE001 — corrupt history: rebuild
                weeks = {}
        stored_weeks = {wk: dict(row) for wk, row in weeks.items()}

        for slug, v in per_show.items():
            series = v.get("weekly_downloads") or []
            for i, n in enumerate(reversed(series)):
                week_start = (monday_w0 - _dt.timedelta(weeks=i)).isoformat()
                weeks.setdefault(week_start, {})[slug] = int(n or 0)

        # Churn suppression: only rewrite when a week actually changed.
        # An unconditional write bumped ``updated_at`` on every build —
        # including read-only/offline builds and every test run — which
        # dirtied the working tree and put a no-content diff into the
        # nightly commit (same reason language/video feeds suppress churn).
        if weeks != stored_weeks:
            hist_path.parent.mkdir(parents=True, exist_ok=True)
            hist_path.write_text(
                json.dumps(
                    {"updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                     "weeks": weeks},
                    indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8")

        per_show_totals: Dict[str, int] = {}
        network_series: List[List[Any]] = []
        for wk in sorted(weeks):
            row = weeks[wk]
            network_series.append([wk, sum(row.values())])
            for slug, n in row.items():
                per_show_totals[slug] = per_show_totals.get(slug, 0) + n
        return {
            "network_total": sum(v for _, v in network_series),
            "per_show_totals": per_show_totals,
            "since": min(weeks) if weeks else None,
            "network_series": network_series,
        }
    except Exception:  # noqa: BLE001 — never break the dashboard
        return empty


def build_audience_section(root: Path) -> Dict[str, Any]:
    """Summarise OP3 download + Buttondown subscriber stats (June 2026).

    Reads ``api/op3_stats.json`` and ``api/buttondown_stats.json`` written
    by the nightly audience-stats step. Both files are optional — when
    absent (secrets not configured yet) the section reports
    ``configured: false`` so the dashboard card can render a setup hint
    instead of zeros.
    """
    section: Dict[str, Any] = {
        "op3": {"configured": False},
        "newsletter": {"configured": False},
    }

    op3_path = root / "api" / "op3_stats.json"
    if op3_path.exists():
        try:
            data = json.loads(op3_path.read_text(encoding="utf-8"))
            shows = data.get("shows") or {}
            per_show = {
                slug: {
                    "downloads_7d": s.get("downloads_7d") or 0,
                    "downloads_30d": s.get("downloads_30d") or 0,
                    "weekly_avg": s.get("weekly_avg") or 0,
                    # 4-element weekly series (w-3 … w0) for trend sparklines.
                    "weekly_downloads": list(s.get("weekly_downloads") or []),
                }
                for slug, s in shows.items()
            }
            # Network weekly trend: right-aligned element-wise sum of the
            # per-show weekly series (shows with shorter histories only
            # contribute to the weeks they have).
            max_weeks = max(
                (len(v["weekly_downloads"]) for v in per_show.values()),
                default=0,
            )
            network_weekly = [0] * max_weeks
            for v in per_show.values():
                wk = v["weekly_downloads"]
                for i, n in enumerate(reversed(wk)):
                    network_weekly[max_weeks - 1 - i] += int(n or 0)

            # All-time downloads: OP3 only exposes rolling windows (the
            # per-episode downloadsAll list is a subset — summing it
            # UNDERCOUNTS badly), so we accumulate the weekly series into
            # api/op3_history.json on every build and sum the accumulated
            # weeks. "All-time" therefore means "since history tracking
            # began" and grows more complete every week.
            history = _merge_op3_history(
                root, data.get("fetched_at"), per_show)
            for slug, v in per_show.items():
                v["downloads_all_time"] = history["per_show_totals"].get(slug, 0)
            top_episodes = sorted(
                (
                    {
                        "show_slug": slug,
                        "title": ep.get("title") or "",
                        "downloads_7d": ep.get("downloads_7d") or 0,
                    }
                    for slug, s in shows.items()
                    for ep in (s.get("episodes") or [])
                ),
                key=lambda e: e["downloads_7d"],
                reverse=True,
            )[:5]
            d30 = sum(v["downloads_30d"] for v in per_show.values())
            d7 = sum(v["downloads_7d"] for v in per_show.values())
            all_time = int(history["network_total"] or 0)
            section["op3"] = {
                "configured": True,
                "fetched_at": data.get("fetched_at"),
                "network_downloads_30d": d30,
                "network_downloads_7d": d7,
                "network_downloads_all_time": all_time,
                "all_time_since": history["since"],
                # History tracking began mid-2026 — all-time can read BELOW
                # the rolling 30d window until enough weeks accumulate.
                "all_time_incomplete": bool(
                    all_time and d30 and all_time < d30),
                "network_weekly_downloads": network_weekly,
                "network_weekly_history": history["network_series"],
                "per_show": per_show,
                "top_episodes_7d": top_episodes,
            }
        except Exception as exc:  # noqa: BLE001 — never break the dashboard
            section["op3"] = {"configured": True, "error": str(exc)}

    bd_path = root / "api" / "buttondown_stats.json"
    if bd_path.exists():
        try:
            data = json.loads(bd_path.read_text(encoding="utf-8"))
            section["newsletter"] = {
                "configured": True,
                "fetched_at": data.get("fetched_at"),
                "subscriber_count": data.get("subscriber_count"),
            }
        except Exception as exc:  # noqa: BLE001
            section["newsletter"] = {"configured": True, "error": str(exc)}

    # July 18 2026 — YouTube channel growth (subscribers were previously
    # tracked NOWHERE). Reads the channels block written by
    # fetch_youtube_analytics (schema v2) + the daily snapshot history for
    # the 7-day delta, plus the top subscriber-driving videos.
    section["youtube"] = {"configured": False}
    yt_path = root / "api" / "youtube_stats.json"
    if yt_path.exists():
        try:
            data = json.loads(yt_path.read_text(encoding="utf-8"))
            channels = data.get("channels") or {}
            hist_rows: List[dict] = []
            hist_path = root / "api" / "youtube_channel_history.json"
            if hist_path.exists():
                try:
                    hist_rows = json.loads(
                        hist_path.read_text(encoding="utf-8")).get("rows", [])
                except Exception:  # noqa: BLE001
                    hist_rows = []

            def _delta_7d(channel: str, current: int) -> Optional[int]:
                cutoff = (_dt.date.today()
                          - _dt.timedelta(days=7)).isoformat()
                older = [r for r in hist_rows
                         if r.get("channel") == channel
                         and str(r.get("date", "")) <= cutoff]
                if older:
                    base = older[-1].get("subscribers")
                    return (current - int(base)
                            if base is not None else None)
                # History too young (< 7 days of snapshots) — fall back to
                # the Analytics day_series net gain over the last 7 rows.
                series = (channels.get(channel) or {}).get("day_series") or []
                if series:
                    tail = series[-7:]
                    return sum(int(d.get("subscribersGained", 0) or 0)
                               - int(d.get("subscribersLost", 0) or 0)
                               for d in tail)
                return None

            per_channel = {}
            for ch, snap in channels.items():
                subs = int(snap.get("subscribers", 0) or 0)
                per_channel[ch] = {
                    "subscribers": subs,
                    "subscribers_delta_7d": _delta_7d(ch, subs),
                    "total_views": snap.get("total_views"),
                    "video_count": snap.get("video_count"),
                }
            top_converters = sorted(
                (
                    {
                        "show": dir_name,
                        "title": v.get("title", ""),
                        "kind": v.get("kind", ""),
                        "channel": v.get("channel", "en"),
                        "subscribers_gained": v.get("subscribers_gained", 0),
                        "views": v.get("views", 0),
                    }
                    for dir_name, s in (data.get("shows") or {}).items()
                    for v in s.get("videos", [])
                    if int(v.get("subscribers_gained", 0) or 0) > 0
                ),
                key=lambda r: r["subscribers_gained"],
                reverse=True,
            )[:5]
            # Per-show rollup (90d Analytics window). Videos already carry
            # show_slug; fall back to digest-dir → YAML slug (tesla_shorts_time
            # → tesla) so Mission Control can show YT next to OP3/Spotify.
            dir_to_slug = {v: k for k, v in _SHOW_DIR_OVERRIDES.items()}
            yt_per_show: Dict[str, Dict[str, Any]] = {}
            for dir_name, s in (data.get("shows") or {}).items():
                for v in s.get("videos") or []:
                    if not isinstance(v, dict):
                        continue
                    slug = str(v.get("show_slug") or "").strip() or str(dir_name)
                    if slug in dir_to_slug:
                        slug = dir_to_slug[slug]
                    if slug == "tesla_shorts_time":
                        slug = "tesla"
                    bucket = yt_per_show.setdefault(slug, {
                        "views": 0,
                        "subscribers_gained": 0,
                        "subscribers_lost": 0,
                        "video_count": 0,
                        "long_views": 0,
                        "short_views": 0,
                        "_ret": [],
                    })
                    views = int(v.get("views") or 0)
                    bucket["views"] += views
                    bucket["subscribers_gained"] += int(
                        v.get("subscribers_gained") or 0)
                    bucket["subscribers_lost"] += int(
                        v.get("subscribers_lost") or 0)
                    bucket["video_count"] += 1
                    kind = str(v.get("kind") or "").lower()
                    if kind == "long":
                        bucket["long_views"] += views
                    elif "short" in kind:
                        bucket["short_views"] += views
                    avp = v.get("average_view_percentage")
                    if isinstance(avp, (int, float)):
                        bucket["_ret"].append(float(avp))
            for slug, bucket in yt_per_show.items():
                rets = bucket.pop("_ret", [])
                bucket["avg_view_percentage"] = (
                    round(sum(rets) / len(rets), 1) if rets else None
                )
            if per_channel or top_converters or yt_per_show:
                section["youtube"] = {
                    "configured": True,
                    "generated": data.get("generated"),
                    "window_days": data.get("window_days") or 90,
                    "channels": per_channel,
                    "top_subscriber_videos": top_converters,
                    "per_show": yt_per_show,
                    "network_views": sum(
                        v["views"] for v in yt_per_show.values()),
                }
        except Exception as exc:  # noqa: BLE001
            section["youtube"] = {"configured": True, "error": str(exc)}

    # July 23 2026 — GA4 site traffic + Spotify listening (fetch_ga4_stats /
    # fetch_spotify_stats). Same optional-file convention as OP3 above; see
    # docs/analytics.md for the full contract.
    section["site"] = {"configured": False}
    ga4_path = root / "api" / "ga4_stats.json"
    if ga4_path.exists():
        try:
            data = json.loads(ga4_path.read_text(encoding="utf-8"))
            section["site"] = {
                "configured": True,
                "fetched_at": data.get("fetched_at"),
                "days": data.get("days"),
                "totals": data.get("totals") or {},
                "day_series": data.get("day_series") or [],
                "top_pages": (data.get("top_pages") or [])[:5],
                "channels": data.get("channels") or [],
                # July 25 2026: countries were fetched but never rendered —
                # the network publishes in 5 languages, so where the audience
                # actually is is a programming signal, not a vanity metric.
                "countries": (data.get("countries") or [])[:8],
            }
        except Exception as exc:  # noqa: BLE001
            section["site"] = {"configured": True, "error": str(exc)}

    # Apple Podcasts Connect (July 25 2026). OP3 already counts Apple
    # DOWNLOADS; what Apple uniquely reports is ENGAGEMENT — followers and
    # whether people finished the episode. No official API exists, so this
    # mirrors the Spotify cookie-connector trade-off.
    # Two Apple sources, deliberately ranked (July 28 2026):
    #
    #   1. api/apple_reporter.json — the OFFICIAL Apple Podcasts Reporter
    #      feed. Token-authenticated, accumulates real daily history.
    #   2. api/apple_stats.json — the cookie-scrape connector. Fragile,
    #      needs a daily re-auth chore, and is the reason two of this
    #      repo's three "absence rendered as 0" bugs existed.
    #
    # Reporter wins when it has data; the scrape stays as a labelled
    # fallback until ~3 weeks of Reporter history accrue and the sources
    # can be compared. Both carry `provenance` and `fetched_at` so the
    # card can say which one it is showing rather than implying a single
    # authoritative Apple number.
    section["apple"] = {"configured": False}
    _apple_sources: dict = {}

    rep_path = root / "api" / "apple_reporter.json"
    if rep_path.exists():
        try:
            rdata = json.loads(rep_path.read_text(encoding="utf-8"))
            rshows = rdata.get("shows") or {}
            # Key by repo slug so the two sources are directly comparable;
            # fall back to the Apple show id when a slug isn't mapped yet.
            reporter_per_show = {}
            for show_id, row in rshows.items():
                slug = row.get("slug") or show_id
                reporter_per_show[slug] = {
                    "plays": row.get("plays"),
                    "listeners": row.get("listeners"),
                    "engaged_listeners": row.get("engaged_listeners"),
                    "listening_hours": row.get("listening_hours"),
                    "days_reported": row.get("days_reported"),
                    "show_name": row.get("show_name") or "",
                }
            _apple_sources["reporter"] = {
                "provenance": "Apple Podcasts Reporter (official)",
                "fetched_at": rdata.get("fetched_at"),
                "first_date": rdata.get("first_date"),
                "last_date": rdata.get("last_date"),
                "days_retained": rdata.get("days_retained"),
                "per_show": reporter_per_show,
                "totals": _absent_preserving_totals(
                    reporter_per_show,
                    ("plays", "listeners", "engaged_listeners", "listening_hours"),
                ),
                "shows_reporting": len(rdata.get("shows_reported") or []),
            }
        except Exception as exc:  # noqa: BLE001
            _apple_sources["reporter"] = {
                "provenance": "Apple Podcasts Reporter (official)",
                "error": str(exc),
            }

    ap_path = root / "api" / "apple_stats.json"
    if ap_path.exists():
        try:
            data = json.loads(ap_path.read_text(encoding="utf-8"))
            shows_raw = data.get("shows") or {}
            per_show = {
                slug: {
                    "plays": s.get("plays"),
                    "listeners": s.get("listeners"),
                    "followers": s.get("followers"),
                    "time_listened": s.get("time_listened"),
                    "errors": sorted((s.get("errors") or {}).keys()) or None,
                }
                for slug, s in shows_raw.items()
            }

            reporting = [s for s, v in per_show.items() if v["plays"] is not None]
            _apple_sources["connect_scrape"] = {
                "provenance": "Apple Podcasts Connect (cookie scrape — fallback)",
                "fetched_at": data.get("fetched_at"),
                "window_days": data.get("window_days"),
                "per_show": per_show,
                "totals": _absent_preserving_totals(
                    per_show, ("plays", "listeners", "followers", "time_listened"),
                ),
                "feeds_registered": len(per_show),
                "feeds_reporting": len(reporting),
            }
        except Exception as exc:  # noqa: BLE001
            _apple_sources["connect_scrape"] = {
                "provenance": "Apple Podcasts Connect (cookie scrape — fallback)",
                "error": str(exc),
            }

    if _apple_sources:
        # Primary = Reporter when it actually reported something. A file
        # that exists but holds no show is not a source of truth, so the
        # scrape keeps the card alive until Reporter history accrues.
        rep = _apple_sources.get("reporter") or {}
        rep_has_data = bool(rep.get("per_show")) and not rep.get("error")
        primary = "reporter" if rep_has_data else (
            "connect_scrape" if _apple_sources.get("connect_scrape") else "reporter"
        )
        chosen = _apple_sources.get(primary, {})
        section["apple"] = {
            "configured": True,
            "primary_source": primary,
            "sources": _apple_sources,
            # Flattened view of the primary source so existing consumers
            # keep working without knowing about the two-source split.
            **{k: v for k, v in chosen.items() if k != "provenance"},
            "provenance": chosen.get("provenance", ""),
        }

    section["spotify"] = {"configured": False}
    sp_path = root / "api" / "spotify_stats.json"
    if sp_path.exists():
        try:
            data = json.loads(sp_path.read_text(encoding="utf-8"))
            shows_raw = data.get("shows") or {}
            per_show = {
                slug: {
                    "followers": s.get("followers"),
                    "streams": s.get("streams"),
                    "listeners": s.get("listeners"),
                    # July 25 2026: starts + episode count were fetched but
                    # discarded. ``starts`` vs ``streams`` is Spotify's own
                    # completion signal (a start that doesn't reach the
                    # stream threshold = an early bail), so surfacing both
                    # turns the card into a retention read.
                    "starts": s.get("starts"),
                    "total_episodes": s.get("totalEpisodes"),
                    "errors": sorted((s.get("errors") or {}).keys()) or None,
                }
                for slug, s in shows_raw.items()
            }

            def _sum(field: str) -> int:
                return sum(int(v[field] or 0) for v in per_show.values()
                           if isinstance(v.get(field), (int, float)))

            # Demographics: Spotify returns age/gender/country facets per
            # show in aggregate_30d — the only demographic data the network
            # gets from any platform. Roll it up network-wide.
            countries: Dict[str, int] = {}
            age_bands: Dict[str, int] = {}
            for s in shows_raw.values():
                agg = s.get("aggregate_30d")
                if not isinstance(agg, dict):
                    continue
                for row in (agg.get("countryFacetedCounts") or {}).items():
                    code, payload = row
                    if isinstance(payload, dict):
                        counts = payload.get("counts")
                        total = (sum(int(x or 0) for x in counts.values())
                                 if isinstance(counts, dict) else 0)
                        if total:
                            countries[code] = countries.get(code, 0) + total
                for band, payload in (agg.get("ageFacetedCounts") or {}).items():
                    if isinstance(payload, dict):
                        counts = payload.get("counts")
                        total = (sum(int(x or 0) for x in counts.values())
                                 if isinstance(counts, dict) else 0)
                        if total:
                            age_bands[band] = age_bands.get(band, 0) + total

            reporting = [s for s, v in per_show.items() if v["streams"] is not None]
            erroring = [s for s, v in per_show.items() if v["errors"]]
            section["spotify"] = {
                "configured": True,
                "fetched_at": data.get("fetched_at"),
                "window_days": data.get("window_days"),
                "per_show": per_show,
                "totals": {
                    "followers": _sum("followers"),
                    "streams": _sum("streams"),
                    "listeners": _sum("listeners"),
                    "starts": _sum("starts"),
                },
                "feeds_registered": len(per_show),
                "feeds_reporting": len(reporting),
                "feeds_erroring": len(erroring),
                "top_countries": sorted(
                    countries.items(), key=lambda kv: -kv[1])[:5],
                "age_bands": sorted(age_bands.items(), key=lambda kv: -kv[1])[:5],
            }
        except Exception as exc:  # noqa: BLE001
            section["spotify"] = {"configured": True, "error": str(exc)}

    # ---- YouTube audience demographics (July 30 2026) ----------------
    # Studio shows these per channel but never split by format, and the
    # split is the interesting cut: Shorts skew young almost everywhere,
    # so a channel whose Shorts DON'T is a different strategic situation
    # from one whose long-form simply drags the average up. Trended here
    # rather than read off a phone screenshot.
    section["youtube_audience"] = {"configured": False}
    yt_path = root / "api" / "youtube_stats.json"
    if yt_path.exists():
        try:
            yt = json.loads(yt_path.read_text(encoding="utf-8"))
            channels = {}
            for ch, block in (yt.get("channels") or {}).items():
                demo = (block or {}).get("demographics") or {}
                geo = (block or {}).get("geography") or []
                if not demo and not geo:
                    continue
                entry: Dict[str, Any] = {
                    "window_days": demo.get("window_days"),
                    "summary": demo.get("summary") or {},
                    "top_countries": [
                        {"country": g.get("country"),
                         "views": g.get("views"),
                         "pct_of_listed": g.get("pct_of_listed")}
                        for g in geo[:10]
                    ],
                }
                # Only present when enough videos of that kind existed to
                # ask for the split — absent means "not measured", which
                # the card must not render as a zero.
                for kind in ("long", "short"):
                    key = f"{kind}_summary"
                    if demo.get(key):
                        entry[key] = demo[key]
                channels[ch] = entry
            if channels:
                section["youtube_audience"] = {
                    "configured": True,
                    "generated": yt.get("generated"),
                    "channels": channels,
                    # The percentages describe SIGNED-IN viewers only, a
                    # subset of views. Carried to the UI so nobody reads
                    # "0.0% under 25" as a headcount.
                    "note": ("viewerPercentage covers signed-in viewers "
                             "only; country shares are of the reported "
                             "top countries, not of all views"),
                }
        except Exception as exc:  # noqa: BLE001
            section["youtube_audience"] = {"configured": False,
                                           "error": str(exc)}

    return section


def build_efficiency_section(
    costs: Dict[str, Any],
    audience: Dict[str, Any],
) -> Dict[str, Any]:
    """Unit economics across OP3 / YouTube / Spotify — never summed as reach.

    Mission Control historically over-weighted YouTube subscriber tiles and
    understated podcast downloads + cost-per-listen. This section puts
    trailing spend next to each platform's own metric so operators can see
    which shows earn their Grok+TTS bill without inventing a fake "total
    reach" number (forbidden by docs/analytics.md).
    """
    op3 = audience.get("op3") or {}
    yt = audience.get("youtube") or {}
    sp = audience.get("spotify") or {}
    ap = audience.get("apple") or {}
    n7 = costs.get("network_last_7_days") or {}
    cost7 = float(n7.get("total") or 0.0)
    eps7 = int(n7.get("episodes") or 0)
    dl7 = int(op3.get("network_downloads_7d") or 0)
    dl30 = int(op3.get("network_downloads_30d") or 0)
    yt_views = int(yt.get("network_views") or 0)
    if not yt_views and isinstance(yt.get("per_show"), dict):
        yt_views = sum(int(v.get("views") or 0) for v in yt["per_show"].values())
    sp_totals = sp.get("totals") or {}
    sp_streams = int(sp_totals.get("streams") or 0)
    sp_listeners = int(sp_totals.get("listeners") or 0)
    ap_totals = ap.get("totals") or {}
    ap_reporting = int(ap.get("feeds_reporting") or 0)

    slugs = set()
    for block in (
        (op3.get("per_show") or {}),
        (costs.get("per_show") or {}),
        (yt.get("per_show") or {}),
        (sp.get("per_show") or {}),
    ):
        slugs.update(block.keys())

    per_show: Dict[str, Dict[str, Any]] = {}
    for slug in sorted(slugs):
        # Skip Spotify language variants in the show-card join (fascinating_frontiers_ru)
        if "_" in slug and slug.rsplit("_", 1)[-1] in ("ru", "fr", "es", "zh"):
            base = slug.rsplit("_", 1)[0]
            if base in slugs or base in (op3.get("per_show") or {}):
                continue
        c7 = ((costs.get("per_show") or {}).get(slug) or {}).get("last_7_days") or {}
        o = (op3.get("per_show") or {}).get(slug) or {}
        y = (yt.get("per_show") or {}).get(slug) or {}
        s = (sp.get("per_show") or {}).get(slug) or {}
        cost_s = float(c7.get("total") or 0.0)
        dl = int(o.get("downloads_7d") or 0)
        views = int(y.get("views") or 0)
        streams = s.get("streams")
        streams_n = int(streams) if isinstance(streams, (int, float)) else 0
        per_show[slug] = {
            "cost_7d_usd": round(cost_s, 4),
            "op3_downloads_7d": dl,
            "op3_downloads_30d": int(o.get("downloads_30d") or 0),
            "usd_per_op3_download": (
                round(cost_s / dl, 4) if dl > 0 else None
            ),
            "youtube_views": views,
            "youtube_avg_view_pct": y.get("avg_view_percentage"),
            "youtube_subs_gained": int(y.get("subscribers_gained") or 0),
            "usd_per_yt_view": (
                round(cost_s / views, 4) if views > 0 else None
            ),
            "spotify_streams_30d": streams_n or None,
        }

    return {
        "cost_7d_usd": round(cost7, 4),
        "episodes_7d": eps7,
        "op3_downloads_7d": dl7,
        "op3_downloads_30d": dl30,
        "usd_per_op3_download_7d": (
            round(cost7 / dl7, 4) if dl7 > 0 else None
        ),
        "youtube_views_window": yt_views,
        "youtube_window_days": yt.get("window_days") or 90,
        "usd_per_yt_view": (
            round(cost7 / yt_views, 4) if yt_views > 0 else None
        ),
        "spotify_streams_30d": sp_streams,
        "spotify_listeners_30d": sp_listeners,
        "apple_feeds_reporting": ap_reporting,
        "apple_plays_30d": int(ap_totals.get("plays") or 0) if ap_reporting else None,
        "note": (
            "Platform metrics are side-by-side and never summed into one "
            "reach number. $/OP3-download uses 7d cost ÷ 7d RSS downloads; "
            "$/YT-view uses 7d cost ÷ Analytics window views (usually 90d) "
            "— directional only across mismatched windows."
        ),
        "per_show": per_show,
    }


def build_funnel_section(root: Path) -> Dict[str, Any]:
    """The four funnel stages + each pilot, condensed for the dashboard.

    Reads ``api/funnel.json`` (built nightly by ``scripts/build_funnel.py``)
    and hands the card exactly what it renders. Stages that were never
    measured stay ``configured: false`` all the way to the UI so the
    operator sees "not measured" rather than a confident zero — the whole
    point of the instrumentation is to stop guessing, and a fabricated
    zero is a guess with a number on it.
    """
    section: Dict[str, Any] = {"configured": False}
    path = root / "api" / "funnel.json"
    if not path.exists():
        return section
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        section["error"] = str(exc)
        return section

    stages = data.get("stages") or {}
    reach = stages.get("reach") or {}
    click = stages.get("click") or {}
    visit = stages.get("visit") or {}
    capture = stages.get("capture") or {}

    def _stage(key, label, configured, value, unit,
               secondary=None, secondary_unit=""):
        # An unmeasured stage reports null, never 0. The card renders
        # "not measured"; a 0 would read as "nobody clicked", and those
        # two facts call for opposite actions.
        return {
            "key": key,
            "label": label,
            "configured": bool(configured),
            "value": value if configured else None,
            "secondary": secondary if configured else None,
            "unit": unit,
            "secondary_unit": secondary_unit,
        }

    section.update({
        "configured": True,
        "generated_at": data.get("generated_at"),
        "window_days": data.get("window_days"),
        "stages": [
            _stage("reach", "Reach", reach.get("configured"),
                   (reach.get("totals") or {}).get("youtube_views"),
                   "YouTube views",
                   (reach.get("totals") or {}).get("podcast_downloads"),
                   "podcast downloads"),
            # attributed_sessions, not the raw total: totals.sessions
            # includes organic/(not set) rows, so labelling it
            # "attributed sessions" showed a number up to 10x the truth
            # while ALSO listing the unattributed count beside it.
            # Fallback subtraction covers a funnel.json built before the
            # field existed.
            _stage("click", "Click", click.get("configured"),
                   ((click.get("totals") or {}).get("attributed_sessions")
                    if (click.get("totals") or {}).get(
                        "attributed_sessions") is not None
                    else (
                        (click.get("totals") or {}).get("sessions", 0)
                        - ((click.get("unattributed") or {})
                           .get("sessions") or 0)
                    ) if (click.get("totals") or {}).get("sessions")
                    is not None else None),
                   "attributed sessions",
                   (click.get("unattributed") or {}).get("sessions"),
                   "unattributed"),
            _stage("visit", "Visit", visit.get("configured"),
                   (visit.get("totals") or {}).get("sessions"),
                   "landings on a funnel page"),
            # The subscriber TOTAL is measured as soon as Buttondown
            # answers; only its per-source breakdown needs the tag fetch.
            _stage("capture", "Capture", capture.get("total_configured"),
                   capture.get("total_subscribers"), "subscribers",
                   capture.get("signup_events_total"),
                   "signup events (window)"),
        ],
        "capture_attribution_configured": bool(capture.get("configured")),
        "rates": data.get("network_rates") or {},
        "pilots": data.get("pilots") or {},
        "by_source": capture.get("by_source") or {},
        "unmeasured": [
            name for name, block in stages.items()
            # Capture's TOTAL is measured as soon as Buttondown answers
            # (the stage row above shows a real number); listing it under
            # "not yet measured" at the same time — because per-source
            # attribution still needs the tag fetch — made the card
            # contradict itself. Only a stage with NO number is unmeasured.
            if not (block or {}).get("configured")
            and not (name == "capture"
                     and (block or {}).get("total_configured"))
        ],
    })

    # The Shorts motion A/B rides on the same card: it is the one
    # experiment currently spending money to answer a funnel question.
    ab_path = root / "api" / "shorts_ab.json"
    if ab_path.exists():
        try:
            ab = json.loads(ab_path.read_text(encoding="utf-8"))
            section["shorts_ab"] = {
                "status": ab.get("status"),
                "min_per_arm": ab.get("min_per_arm"),
                "arms": {
                    name: {
                        "n": (arm or {}).get("n"),
                        "views_mean": ((arm or {}).get("views") or {}).get("mean"),
                        "retention_mean": (
                            (arm or {}).get("average_view_percentage") or {}
                        ).get("mean"),
                        "subs_total": (
                            (arm or {}).get("subscribers_gained") or {}
                        ).get("total"),
                    }
                    for name, arm in (ab.get("arms") or {}).items()
                },
                "comparisons": ab.get("comparisons") or {},
                "spend_usd": ab.get("spend_usd") or {},
            }
        except Exception:  # noqa: BLE001 — the card degrades, never breaks
            pass
    return section


def build_youtube_policy_section(root: Path) -> Dict[str, Any]:
    """Adaptive publishing tiers per show × channel (July 2026 policy).

    ``api/youtube_policy.json`` decides, nightly and from real velocity
    data, whether each show publishes long-form and how many Shorts — the
    single biggest lever on publish volume — but it was never rendered.
    An operator seeing "long-form off" on a show should be able to see WHY
    (its views-per-day) without opening the raw JSON.
    """
    section: Dict[str, Any] = {"configured": False}
    path = root / "api" / "youtube_policy.json"
    if not path.exists():
        return section
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        channels_out: Dict[str, Any] = {}
        for channel, payload in (data.get("channels") or {}).items():
            if not isinstance(payload, dict):
                continue
            # The writer maps slug -> policy directly; tolerate a future
            # {"shows": {...}} wrapper without breaking.
            shows = payload.get("shows") if isinstance(
                payload.get("shows"), dict) else payload
            if not isinstance(shows, dict):
                continue
            rows = []
            tier_counts: Dict[str, int] = {}
            for slug, v in shows.items():
                if not isinstance(v, dict):
                    continue
                tier = str(v.get("tier") or "?")
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
                rows.append({
                    "slug": slug,
                    "tier": tier,
                    "publish_long_form": bool(v.get("publish_long_form")),
                    "shorts_per_episode": v.get("shorts_per_episode"),
                    "long_vpd": v.get("long_vpd"),
                    "short_vpd": v.get("short_vpd"),
                    "pending": v.get("pending"),
                })
            rows.sort(key=lambda r: (r["tier"], r["slug"]))
            channels_out[channel] = {
                "shows": rows,
                "tier_counts": tier_counts,
                "long_form_on": sum(1 for r in rows if r["publish_long_form"]),
                "shorts_planned": sum(int(r["shorts_per_episode"] or 0) for r in rows),
            }
        if channels_out:
            section = {
                "configured": True,
                "generated": data.get("generated"),
                "window_days": data.get("window_days"),
                "channels": channels_out,
            }
    except Exception as exc:  # noqa: BLE001
        section = {"configured": True, "error": str(exc)}
    return section


def build_distribution_section(root: Path) -> Dict[str, Any]:
    """Directory coverage per platform, parsed from the operator's tracker.

    July 25 2026: Apple Podcasts, Amazon Music, Podcast Index, Pocket Casts
    and iHeart have NO analytics API (Apple's downloads already flow through
    OP3), so the only record of where each show is actually *distributed*
    lived in docs/podcast_directories.md — invisible on mission control.
    A directory that silently failed to ingest a feed is lost reach that
    nothing else would surface.

    This parses that markdown status table (the operator's single source of
    truth — kept as markdown deliberately, since it's hand-maintained during
    submission passes) into per-platform coverage counts. Best-effort: a
    missing/renamed table degrades to ``configured: false``.

    Legend in the doc: ``LIVE`` (optionally with a date), ``PENDING``,
    ``--`` (not submitted), ``n/a`` (doesn't apply).
    """
    section: Dict[str, Any] = {"configured": False}
    doc = root / "docs" / "podcast_directories.md"
    if not doc.exists():
        return section
    try:
        text = doc.read_text(encoding="utf-8")
        if "## Submission Status Tracker" not in text:
            return section
        block = text.split("## Submission Status Tracker", 1)[1]
        rows = [ln.strip() for ln in block.splitlines()
                if ln.strip().startswith("|")]
        if len(rows) < 3:
            return section
        header = [c.strip() for c in rows[0].strip("|").split("|")]
        platforms = header[1:]
        per_platform: Dict[str, Dict[str, Any]] = {
            p: {"live": 0, "pending": 0, "missing": 0, "na": 0,
                "missing_shows": []}
            for p in platforms
        }
        show_rows = []
        for line in rows[2:]:  # skip header + separator
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) != len(header):
                continue
            show = cells[0]
            statuses: Dict[str, str] = {}
            for platform, raw in zip(platforms, cells[1:]):
                val = raw.strip()
                low = val.lower()
                bucket = per_platform[platform]
                if low.startswith("live"):
                    bucket["live"] += 1
                    state = "live"
                elif low.startswith("pending"):
                    bucket["pending"] += 1
                    state = "pending"
                elif low.startswith("n/a"):
                    bucket["na"] += 1
                    state = "na"
                else:
                    bucket["missing"] += 1
                    bucket["missing_shows"].append(show)
                    state = "missing"
                statuses[platform] = state
            show_rows.append({"show": show, "statuses": statuses})

        for bucket in per_platform.values():
            applicable = bucket["live"] + bucket["pending"] + bucket["missing"]
            bucket["applicable"] = applicable
            bucket["coverage_pct"] = (
                round(100 * bucket["live"] / applicable, 1) if applicable else 0.0)
            bucket["missing_shows"] = bucket["missing_shows"][:20]

        # Operator follow-ups the doc records in prose (kept short + exact).
        notes = []
        if "Podcast Index: API keys stale" in block or "HTTP 401" in block:
            notes.append("Podcast Index: API keys stale (HTTP 401) — refresh "
                         "PODCAST_INDEX_API_KEY/SECRET, then re-run the "
                         "Submit Podcast Directories workflow.")
        if "never indexed on Spotify" in block:
            notes.append("Spotify: the RU SpaceX feed never indexed — "
                         "resubmit at creators.spotify.com if wanted.")
        if "iHeart: not yet submitted" in block:
            notes.append("iHeart: not yet submitted (manual form).")
        if "Amazon Music" in block and "ownership-confirmation" in block:
            notes.append("Amazon Music: feeds submitted + ownership confirmed "
                         "2026-07-23; shows go LIVE as Amazon ingests them — "
                         "spot-check and mark LIVE in the tracker.")

        section = {
            "configured": True,
            "source_doc": "docs/podcast_directories.md",
            "rows": len(show_rows),
            "platforms": per_platform,
            "shows": show_rows,
            "notes": notes,
        }
    except Exception as exc:  # noqa: BLE001 — never break the dashboard
        section = {"configured": True, "error": str(exc)}
    return section


def _get_content_lake_stats_safe() -> dict:
    try:
        from engine.content_lake import get_lake_stats
        return get_lake_stats()
    except Exception:
        return {"error": "content lake unavailable"}


def build_content_lake_section(root: Path) -> Dict[str, Any]:
    """Content-lake vitals for the dashboard (July 2026).

    The lake (data/content_lake.db) powers cross-episode dedup, the Sunday
    weekly-summary segment, and site search — an empty lake silently
    degrades all three (the exact failure mode scripts/backfill_content_lake.py
    annotates on). Surface its state so the operator sees it on the
    mission-control page, not just in CI logs.
    """
    stats = _get_content_lake_stats_safe()
    db_path = root / "data" / "content_lake.db"
    db_exists = db_path.exists()
    db_size = db_path.stat().st_size if db_exists else 0
    total = int(stats.get("total_episodes") or 0) if isinstance(stats, dict) else 0
    return {
        "stats": stats,
        "db_path": "data/content_lake.db",
        "db_exists": db_exists,
        "db_size_bytes": db_size,
        # <2 episodes means the weekly-summary segment can't build and
        # cross-episode dedup is running blind — the backfill guard's
        # thin-lake threshold.
        "healthy": total >= 2,
        "compaction_note": "Run scripts/compact_lake.py or engine.content_lake.compact_lake() to prune old full text.",
    }


def build_gallery_section(root: Path) -> Dict[str, Any]:
    """Image-library roll-up from the committed gallery manifest (July 2026).

    site/data/gallery-manifest.json is rebuilt nightly from the R2 sidecars
    (build_gallery_manifest.py). This summarises what the network offers on
    /gallery.html: total images, per-show counts, intended-use split, plus
    whether the retention feedback loop (api/gallery_retention.json) has
    data yet. All best-effort — an absent manifest reports configured: false.
    """
    section: Dict[str, Any] = {"configured": False}
    manifest_path = root / "site" / "data" / "gallery-manifest.json"
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            images = data.get("images") or []
            use_counts: Dict[str, int] = {}
            licenses: Dict[str, int] = {}
            latest_generated = ""
            for img in images:
                use = str(img.get("intended_use") or "unknown")
                use_counts[use] = use_counts.get(use, 0) + 1
                lic = str(img.get("license") or "unknown")
                licenses[lic] = licenses.get(lic, 0) + 1
                gen = str(img.get("generated_at") or "")
                if gen > latest_generated:
                    latest_generated = gen
            name_by_slug = {
                s.get("slug"): s.get("name")
                for s in (data.get("shows") or [])
                if isinstance(s, dict)
            }
            section = {
                "configured": True,
                "generated_at": data.get("generated_at"),
                "image_count": int(data.get("image_count") or len(images)),
                "latest_image_at": latest_generated or None,
                "per_show": {
                    slug: {"count": count, "name": name_by_slug.get(slug, slug)}
                    for slug, count in (data.get("show_counts") or {}).items()
                },
                "intended_use": use_counts,
                "licenses": licenses,
            }
        except Exception as exc:  # noqa: BLE001 — never break the dashboard
            section = {"configured": True, "error": str(exc)}

    # Retention feedback loop: how much of the library has audience data.
    retention: Dict[str, Any] = {"available": False}
    ret_path = root / "api" / "gallery_retention.json"
    if ret_path.exists():
        try:
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
            ret_shows = ret.get("shows") or {}
            imgs_with_data = sum(
                len(s.get("images") or {}) for s in ret_shows.values()
                if isinstance(s, dict)
            )
            retention = {
                "available": bool(imgs_with_data),
                "generated": ret.get("generated"),
                "shows_analyzed": len(ret_shows),
                "images_with_retention": imgs_with_data,
            }
        except Exception:  # noqa: BLE001
            pass
    section["retention"] = retention
    return section


def _episode_num_of(record: Dict[str, Any]) -> Optional[int]:
    for key in ("episode_num", "episode"):
        v = record.get(key)
        if isinstance(v, int):
            return v
    return None


def build_catalog_section(
    root: Path, shows: List[Dict[str, Any]], rss: Dict[str, Any],
) -> Dict[str, Any]:
    """Show catalog: episodes to date, feed depth, and news sources (July 2026).

    Answers the cumulative questions the run-rate cards don't: how many
    shows exist, how many episodes each has ever produced, how deep the
    public feed is, and what each show's input pipeline looks like (RSS
    sources + web-search queries for news shows, topic-queue runway for
    narrative shows).
    """
    entry_count_by_feed = {
        f.get("file"): f.get("entry_count")
        for f in (rss.get("feeds") or [])
    }

    per_show: Dict[str, Any] = {}
    total_eps = 0
    total_sources = 0
    total_queries = 0
    for s in shows:
        cfg = s.get("cfg")
        slug = s["slug"]
        if not cfg:
            per_show[slug] = {"name": s.get("name") or slug,
                              "load_error": s.get("load_error")}
            continue

        # Episodes to date: the highest episode number ever recorded in
        # the show's summaries file (the file itself is capped at recent
        # records, but episode numbering is monotonic so max == to-date).
        episodes_to_date = 0
        latest_date = None
        summ = cfg.publishing.summaries_json or ""
        summ_path = root / summ if summ else None
        if summ_path and summ_path.exists():
            try:
                data = json.loads(summ_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("summaries"), list):
                    records = data["summaries"]
                elif isinstance(data, dict) and isinstance(data.get("episodes"), list):
                    records = data["episodes"]
                elif isinstance(data, list):
                    records = data
                else:
                    records = []
                nums = [n for n in (_episode_num_of(r) for r in records
                                    if isinstance(r, dict)) if n is not None]
                episodes_to_date = max(nums) if nums else len(records)
                dates = sorted(str(r.get("date")) for r in records
                               if isinstance(r, dict) and r.get("date"))
                latest_date = dates[-1] if dates else None
            except Exception:  # noqa: BLE001
                pass

        raw = s.get("raw_yaml") or {}
        sources = raw.get("sources") or []
        queries = raw.get("web_search_queries") or []
        n_sources = len(sources) if isinstance(sources, list) else 0
        n_queries = len(queries) if isinstance(queries, list) else 0

        narrative = bool(getattr(cfg, "narrative_mode", False))
        queue_info = None
        if narrative:
            qfile = getattr(cfg, "topic_queue_file", "") or ""
            qpath = root / qfile if qfile else None
            if qpath and qpath.exists():
                try:
                    q = yaml.safe_load(qpath.read_text(encoding="utf-8")) or {}
                    items = q.get("queue") or q.get("topics") or []
                    if not isinstance(items, list):
                        items = []
                    produced = sum(
                        1 for t in items
                        if isinstance(t, dict)
                        and (t.get("produced") or t.get("status") == "produced")
                    )
                    queue_info = {
                        "total": len(items),
                        "produced": produced,
                        "remaining": len(items) - produced,
                    }
                except Exception:  # noqa: BLE001
                    pass

        ml = getattr(cfg, "multilingual", None)
        yt = getattr(cfg, "youtube", None)
        per_show[slug] = {
            "name": cfg.name or slug,
            "episodes_to_date": episodes_to_date,
            "episodes_in_feed": entry_count_by_feed.get(
                cfg.publishing.rss_file or ""),
            "latest_date": latest_date,
            "news_sources": n_sources,
            "web_search_queries": n_queries,
            "narrative_mode": narrative,
            "topic_queue": queue_info,
            "capabilities": {
                "x": bool(cfg.publishing.x_enabled),
                "newsletter": bool(cfg.newsletter.enabled),
                "youtube": bool(yt and getattr(yt, "enabled", False)),
                "multilingual": bool(ml and getattr(ml, "enabled", False)),
                "memory": bool(getattr(cfg, "memory_enabled", False)
                               or slug == "tesla"),  # Tesla: bespoke engine/tesla_memory
            },
        }
        total_eps += episodes_to_date
        total_sources += n_sources
        total_queries += n_queries

    return {
        "shows_count": len(shows),
        "network_episodes_to_date": total_eps,
        "network_news_sources": total_sources,
        "network_web_search_queries": total_queries,
        "per_show": per_show,
    }


def _json_safe(value: Any) -> Any:
    """Recursively replace non-finite floats (NaN/±Infinity) with None.

    JSON.parse in every browser rejects the bare ``NaN``/``Infinity``
    literals Python's json module emits by default, so one poisoned float
    blanks the entire dashboard. ``None`` renders as "—" in every consumer
    (they all use ``x == null`` fallbacks), which is the honest display for
    a value that failed to compute.
    """
    import math as _math
    if isinstance(value, float):
        return value if _math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _read_previous_flat_total(out_path: Path) -> Optional[int]:
    if not out_path.exists():
        return None
    try:
        data = json.loads(out_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    for lm in data.get("landmines") or []:
        if lm.get("id") == "item_3_legacy_flatfiles":
            return (lm.get("evidence") or {}).get("total")
    return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate api/dashboard.json")
    parser.add_argument("--out", default="api/dashboard.json")
    parser.add_argument("--offline", action="store_true",
                        help="Skip HEAD reachability checks on enclosure URLs")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print JSON to stdout, do not write file")
    args = parser.parse_args(argv)

    out_path = (_ROOT / args.out).resolve()
    previous = _read_previous_flat_total(out_path)
    data = build_dashboard(_ROOT, offline=args.offline, previous_flat=previous)

    # NaN/Infinity are valid Python-JSON but INVALID JSON per spec, and
    # browsers' JSON.parse rejects them — a single NaN anywhere in this
    # payload makes management.html fail its fetch and render the error
    # banner instead of the whole dashboard (verified July 25 2026 with a
    # NaN MIT benchmark close: every section went blank). NaN has reached
    # this payload before via yfinance NaN closes (the July 2026 MIT
    # phantom-trade class), so sanitise on the way out.
    blob = json.dumps(_json_safe(data), indent=2, ensure_ascii=False, default=str)
    if args.dry_run:
        print(blob)
        return 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(blob + "\n", encoding="utf-8")

    # Emit a short human-readable summary so CI logs tell the story at a glance.
    counts = data["network"]["landmines_counts"]
    alert_count = len(data.get("alerts", []))
    print(
        f"dashboard: wrote {out_path.relative_to(_ROOT)} — "
        f"{counts.get('ok', 0)} ok, {counts.get('warn', 0)} warn, "
        f"{counts.get('fail', 0)} fail; "
        f"{alert_count} critical alerts; "
        f"{data['network']['shows_count']} shows; "
        f"${data['network']['total_cost_last_7_days_usd']:.2f} 7d spend",
        file=sys.stderr,
    )
    return 1 if counts.get("fail", 0) else 0


if __name__ == "__main__":
    sys.exit(main())
