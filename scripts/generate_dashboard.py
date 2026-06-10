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
    "network_meta", "scaffold_pending",
}

# Canonical Russian voice id (pulled from CLAUDE.md; shows/_defaults.yaml ships
# the English default). Shows may override with either the EN or RU voice id.
_VOICE_ID_RU = "gedzfqL7OGdPbwm0ynTP"

# Stale CLAUDE.md triple we use to detect documentation drift (item 9).
_CLAUDE_MD_OLD_VOICE_TRIPLE = "0.65/0.9/0.85"


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

    All 11 shows migrated to Grok TTS in the May 2026 full-network
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
        # Voice id must be one of the two blessed voices.
        if row["voice_id"] not in (baseline["voice_id_en"], baseline["voice_id_ru"]):
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
        recap_synthesised = 0  # Sundays where the recap actually built
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
            # Sunday weekly-recap health (Phase 1.1 of the May 2026
            # schedule overhaul wired weekly_recap_mode into metrics).
            if "weekly_recap_mode" in counters:
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
            # Sunday weekly-recap synthesis health (Phase 1.1 of
            # the schedule overhaul). recap_attempts is the count
            # of Sunday slots in the last 30 episodes; recap_synthesised
            # is how many actually built a recap from the content lake.
            # A gap means the lake had <2 episodes in the 7-day window
            # (the runner falls back to a normal daily fetch).
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
    network_7 = {"grok": 0.0, "tts": 0.0, "total": 0.0, "episodes": 0}
    network_30 = {"grok": 0.0, "tts": 0.0, "total": 0.0, "episodes": 0}

    for s in shows:
        slug = s["slug"]
        ddir = _digests_dir_for(slug, root)
        files = sorted(ddir.glob("credit_usage_*.json")) if ddir.exists() else []
        show_7 = {"grok": 0.0, "tts": 0.0, "total": 0.0, "episodes": 0}
        show_30 = {"grok": 0.0, "tts": 0.0, "total": 0.0, "episodes": 0}
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
            total = float(data.get("total_estimated_cost_usd") or (grok + tts))
            daily_series[date_str] = round(daily_series.get(date_str, 0.0) + total, 4)

            if when >= d30:
                show_30["grok"] += grok
                show_30["tts"] += tts
                show_30["total"] += total
                show_30["episodes"] += 1
                network_30["grok"] += grok
                network_30["tts"] += tts
                network_30["total"] += total
                network_30["episodes"] += 1
            if when >= d7:
                show_7["grok"] += grok
                show_7["tts"] += tts
                show_7["total"] += total
                show_7["episodes"] += 1
                network_7["grok"] += grok
                network_7["tts"] += tts
                network_7["total"] += total
                network_7["episodes"] += 1

        for bucket in (show_7, show_30):
            for k in ("grok", "tts", "total"):
                bucket[k] = round(bucket[k], 4)
        # Last 30 daily series, oldest → newest, for sparkline rendering.
        daily_sorted = sorted(daily_series.items())[-30:]
        per_show[slug] = {
            "last_7_days": show_7,
            "last_30_days": show_30,
            "daily_series": daily_sorted,
        }

    for bucket in (network_7, network_30):
        for k in ("grok", "tts", "total"):
            bucket[k] = round(bucket[k], 4)

    # Quick-win enhancements (May 2026 codebase review):
    # - Simple projection so operators see "at current burn rate, what does a week cost?"
    # - Surface for future live YT quota remaining (engine.youtube_quota already exists).
    episodes_7 = max(network_7.get("episodes", 0), 1)
    avg_per_episode = round(network_7["total"] / episodes_7, 4)
    # Conservative: network ships ~60-70 episodes/week across 11 shows
    projected_weekly = round(avg_per_episode * 65, 2)

    return {
        "per_show": per_show,
        "network_last_7_days": network_7,
        "network_last_30_days": network_30,
        "projections": {
            "avg_cost_per_episode_usd": avg_per_episode,
            "projected_weekly_usd": projected_weekly,
            "note": "Projection uses last-7d average × 65 (network volume). Tune per operator knowledge.",
        },
        "youtube_quota": {
            "enabled_shows_count": 2,  # TST + MAB only (per landmine #20 quota cap)
            "daily_insert_cost_units": 1600,  # long + short typical (see engine/youtube_quota.py)
            "note": "Hard cap ~10k units/day per channel. Preflight + youtube_quota.py have the estimators. Only 2 shows currently enabled.",
        },
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
        if latest_pub:
            try:
                when = _dt.datetime.fromisoformat(latest_pub)
                age_hours = (
                    _dt.datetime.now(_dt.timezone.utc) - when
                ).total_seconds() / 3600
                if age_hours > 72:
                    pub_status = "stale"
                elif age_hours > 48:
                    pub_status = "warn"
            except Exception:
                pub_status = "unknown"
        cost_7 = costs["per_show"].get(slug, {}).get("last_7_days", {})
        m = metrics.get(slug, {})
        per_show_summary.append({
            "slug": slug,
            "name": cfg.name,
            "rss_file": rss_file,
            "rss_title": cfg.publishing.rss_title,
            "rss_image": cfg.publishing.rss_image,
            "show_page": f"{slug}.html",
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
    # Jinja's Undefined sentinel on older tracker files.
    raw_bench = tracker.get("benchmark") or {}
    benchmark = {
        "current_close": raw_bench.get("current_close"),
        "inception_to_date_pct": raw_bench.get("inception_to_date_pct"),
        "ytd_pct": raw_bench.get("ytd_pct"),
        "last_updated": raw_bench.get("last_updated"),
    }
    raw_alpha = tracker.get("alpha") or {}
    alpha = {
        "inception_to_date_pct": raw_alpha.get("inception_to_date_pct"),
        "ytd_pct": raw_alpha.get("ytd_pct"),
        "monthly": raw_alpha.get("monthly") or {},
    }

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
        "last_updated": (tracker.get("metadata") or {}).get("last_updated"),
    }


# ---------------------------------------------------------------------------
# Public entry point — called by tests AND by __main__
# ---------------------------------------------------------------------------


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

    return {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "network": network,
        "shows": serializable_shows,
        "landmines": landmines,
        "alerts": alerts,
        "voice_config": voice,
        "cost_rollup": costs,
        "pipeline_health": metrics,
        "rss_audit": rss,
        "mit_performance": aggregate_mit_performance(root),
        "audience": build_audience_section(root),
        "content_lake": {
            "stats": _get_content_lake_stats_safe(),
            "compaction_note": "Run scripts/compact_lake.py or engine.content_lake.compact_lake() to prune old full text.",
        },
    }


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
                }
                for slug, s in shows.items()
            }
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
            section["op3"] = {
                "configured": True,
                "fetched_at": data.get("fetched_at"),
                "network_downloads_30d": sum(
                    v["downloads_30d"] for v in per_show.values()),
                "network_downloads_7d": sum(
                    v["downloads_7d"] for v in per_show.values()),
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

    return section


def _get_content_lake_stats_safe() -> dict:
    try:
        from engine.content_lake import get_lake_stats
        return get_lake_stats()
    except Exception:
        return {"error": "content lake unavailable"}


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

    blob = json.dumps(data, indent=2, ensure_ascii=False, default=str)
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
