"""Render-time reuse of already-generated gallery images + evergreen b-roll.

The network has paid (Grok Imagine credits) for every scene image it has ever
generated — they all live in the public ``nerra-gallery`` R2 bucket and are
indexed by the committed ``site/data/gallery-manifest.json``. This module
lets render-time consumers (Sunday weekly recaps, RU dubs, any show whose
fresh scenes failed to generate) pull *relevant* historical scenes back down
instead of falling back to a static cover — zero new image-generation cost.

Selection is deterministic: candidates are filtered (show / aspect / episode
window / current-episode exclusion), scored by token overlap between the
caller's context text (episode hook, chapter titles) and the image's
``prompt`` + ``caption`` + ``tags``, and tie-broken by recency then
``image_id``. Winners are downloaded into a local cache keyed on
``image_id`` so repeated renders (and the weekly recap re-using a daily's
scenes) never re-fetch bytes.

Everything network-facing is best-effort by contract: a missing manifest, a
dead URL, or a full R2 outage yields fewer (or zero) results — the public
API never raises, matching the gallery-uploader's soft-fail design
(``engine/gallery_uploader.py``).

The evergreen b-roll pool (``select_broll_clips``) is the companion for
*video* clips: a small committed ``broll.json`` per show (written by
``scripts/build_broll_pool.py``) points at curated clips on R2 — e.g. the
recovered Grok Video clips from ``scripts/recover_grok_video.py``. Only the
JSON is committed; the media stays on R2 (landmine #1).
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = PROJECT_ROOT / "site" / "data" / "gallery-manifest.json"

DOWNLOAD_TIMEOUT_SECONDS = 20

# Aspect → the manifest's ``intended_use`` value (see gallery_uploader):
# ``segment_card`` is the 16:9 long-form scene, ``social`` the 9:16 Short.
_ASPECT_TO_USE = {"16:9": "segment_card", "9:16": "social"}

# Words too common in Grok Imagine prompts / hooks to signal relevance —
# without this every "photo, dramatic lighting" boilerplate token matches.
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that "
    "the this to was were will with photo image style lighting composition "
    "detailed ultra framing depicting no text words rendered".split()
)

# Local-cache path → manifest entry, populated at download time so
# ``scene_context_map`` can resolve paths even without the manifest.
_PATH_REGISTRY: Dict[Path, dict] = {}


# ---------------------------------------------------------------------------
# Manifest loading + selection
# ---------------------------------------------------------------------------


def load_manifest(path: Optional[Path] = None) -> dict:
    """Load the gallery manifest; ``{}`` on any failure (missing/corrupt)."""
    p = Path(path) if path else DEFAULT_MANIFEST
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — missing/corrupt = empty library
        logger.info("gallery_library: manifest unreadable at %s (%s)", p, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _tokenize(text: str) -> frozenset:
    return frozenset(
        t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(t) > 2 and t not in _STOPWORDS
    )


def _entry_tokens(entry: dict) -> frozenset:
    parts = [entry.get("prompt", ""), entry.get("caption", ""),
             entry.get("episode_title", "")]
    parts.extend(entry.get("tags") or [])
    return _tokenize(" ".join(str(p) for p in parts))


def _candidate_entries(
    manifest: dict,
    show_slug: str,
    *,
    intended_use: str,
    exclude_episode_id: Optional[str],
    min_episode_date: Optional[str],
    max_episode_date: Optional[str],
) -> List[dict]:
    out = []
    for entry in manifest.get("images", []) or []:
        if entry.get("show_slug") != show_slug:
            continue
        if entry.get("intended_use") != intended_use:
            continue
        if not entry.get("original_url"):
            continue
        eid = (entry.get("episode_id") or "").lower()
        if exclude_episode_id and eid == exclude_episode_id.lower():
            continue
        # ISO date strings compare correctly lexicographically.
        date = entry.get("episode_date") or ""
        if min_episode_date and date < min_episode_date:
            continue
        if max_episode_date and date > max_episode_date:
            continue
        out.append(entry)
    return out


def _rank(entries: List[dict], context_text: str) -> List[dict]:
    """Deterministic best-first ordering.

    Primary: token overlap with the context. Ties: newer ``episode_date``
    first, then ``image_id`` — so identical inputs always yield identical
    output regardless of manifest document order. Implemented as three
    stable sorts (least- to most-significant key); Python's sort is stable
    even with ``reverse=True``.
    """
    ctx = _tokenize(context_text)
    ranked = sorted(entries, key=lambda e: e.get("image_id") or "")
    ranked.sort(key=lambda e: e.get("episode_date") or "", reverse=True)
    if ctx:
        ranked.sort(key=lambda e: len(ctx & _entry_tokens(e)), reverse=True)
    return ranked


def _default_cache_dir() -> Path:
    return Path(tempfile.gettempdir()) / "gallery_cache"


def _cache_filename(entry: dict) -> str:
    url = entry["original_url"]
    basename = url.rstrip("/").rsplit("/", 1)[-1]
    ext = Path(basename).suffix or ".jpg"
    stem = entry.get("image_id") or Path(basename).stem
    return f"{stem}{ext}"


def _download_entry(entry: dict, cache_dir: Path) -> Optional[Path]:
    """Fetch one image into the cache (or reuse); None on failure."""
    dest = cache_dir / _cache_filename(entry)
    if dest.exists() and dest.stat().st_size > 0:
        _PATH_REGISTRY[dest] = entry
        return dest
    try:
        resp = requests.get(entry["original_url"],
                            timeout=DOWNLOAD_TIMEOUT_SECONDS)
        resp.raise_for_status()
        if not resp.content:
            raise ValueError("empty response body")
        dest.write_bytes(resp.content)
    except Exception as exc:  # noqa: BLE001 — skip the image, keep going
        logger.warning("gallery_library: failed to fetch %s: %s",
                       entry.get("original_url"), exc)
        return None
    _PATH_REGISTRY[dest] = entry
    return dest


def select_library_scenes(
    show_slug: str,
    *,
    aspect: str,
    exclude_episode_id: Optional[str] = None,
    context_text: str = "",
    limit: int = 8,
    manifest: Optional[dict] = None,
    cache_dir: Optional[Path] = None,
    min_episode_date: Optional[str] = None,
    max_episode_date: Optional[str] = None,
) -> List[Path]:
    """Pick + download the show's most relevant already-generated scenes.

    ``aspect`` is ``"16:9"`` (long-form ``segment_card`` images) or
    ``"9:16"`` (Shorts ``social`` images). Candidates from the current
    episode (``exclude_episode_id``) and outside the optional
    ``[min_episode_date, max_episode_date]`` ISO-date window are dropped;
    the rest are ranked by ``context_text`` token overlap against each
    image's prompt/caption/tags with recency as the tiebreak.

    Downloads are cached by ``image_id`` under ``cache_dir`` (default:
    ``gallery_cache/`` in the system temp dir). Failed downloads are
    skipped and the next-best candidate backfills, so the return is
    best-first local Paths, up to ``limit``. Never raises.
    """
    try:
        use = _ASPECT_TO_USE.get(aspect)
        if use is None:
            logger.warning("gallery_library: unknown aspect %r "
                           "(want 16:9 or 9:16)", aspect)
            return []
        data = manifest if manifest is not None else load_manifest()
        entries = _candidate_entries(
            data, show_slug, intended_use=use,
            exclude_episode_id=exclude_episode_id,
            min_episode_date=min_episode_date,
            max_episode_date=max_episode_date)
        if not entries or limit <= 0:
            return []
        cdir = Path(cache_dir) if cache_dir else _default_cache_dir()
        cdir.mkdir(parents=True, exist_ok=True)
        paths: List[Path] = []
        for entry in _rank(entries, context_text):
            if len(paths) >= limit:
                break
            p = _download_entry(entry, cdir)
            if p is not None:
                paths.append(p)
        return paths
    except Exception as exc:  # noqa: BLE001 — library reuse is optional
        logger.warning("gallery_library: scene selection failed for %s: %s",
                       show_slug, exc)
        return []


def collect_week_scenes(
    show_slug: str,
    *,
    aspect: str,
    end_date: str,
    days: int = 7,
    exclude_episode_id: Optional[str] = None,
    manifest: Optional[dict] = None,
    cache_dir: Optional[Path] = None,
    limit: int = 24,
) -> List[Path]:
    """Scenes from the ``days`` ending at ``end_date`` (ISO), newest first.

    The weekly-recap variant of :func:`select_library_scenes`: no context
    scoring — with an empty context the ranking degrades to pure recency,
    which is exactly the "this week's imagery in order" a recap wants.
    """
    try:
        import datetime as _dt
        end = _dt.date.fromisoformat(str(end_date)[:10])
        start = end - _dt.timedelta(days=max(0, days - 1))
    except Exception as exc:  # noqa: BLE001
        logger.warning("gallery_library: bad end_date %r: %s", end_date, exc)
        return []
    return select_library_scenes(
        show_slug,
        aspect=aspect,
        exclude_episode_id=exclude_episode_id,
        context_text="",
        limit=limit,
        manifest=manifest,
        cache_dir=cache_dir,
        min_episode_date=start.isoformat(),
        max_episode_date=end.isoformat(),
    )


def scene_context_map(manifest: dict, paths: Iterable[Path]) -> Dict[Path, str]:
    """Map each local scene Path back to its ``prompt`` + ``caption`` text.

    This is the shape the scene scheduler consumes (``scene_context:
    dict[Path, str]``). Resolution is two-layer: the in-process registry
    written at download time (exact), then a manifest lookup by the
    filename stem (cache files are named by ``image_id``, so a warm cache
    from an earlier process still resolves). Unknown paths map to ``""``.
    """
    by_id: Dict[str, dict] = {}
    try:
        for entry in (manifest or {}).get("images", []) or []:
            iid = entry.get("image_id")
            if iid:
                by_id.setdefault(iid, entry)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gallery_library: bad manifest in scene_context_map: %s",
                       exc)
    out: Dict[Path, str] = {}
    for p in paths:
        p = Path(p)
        entry = _PATH_REGISTRY.get(p) or by_id.get(p.stem) or {}
        parts = [str(entry.get("prompt") or "").strip(),
                 str(entry.get("caption") or "").strip()]
        out[p] = "\n".join(part for part in parts if part)
    return out


# ---------------------------------------------------------------------------
# Evergreen b-roll clips
# ---------------------------------------------------------------------------


def load_broll_entries(digests_dir: Path) -> List[dict]:
    """Entries from ``<digests_dir>/broll.json`` in committed order.

    Accepts both the builder's wrapped form (``{"clips": [...]}``) and a
    bare list. Missing/corrupt file → ``[]``.
    """
    path = Path(digests_dir) / "broll.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("gallery_library: broll.json unreadable at %s: %s",
                       path, exc)
        return []
    clips = data.get("clips") if isinstance(data, dict) else data
    if not isinstance(clips, list):
        return []
    return [c for c in clips if isinstance(c, dict) and c.get("url")]


def select_broll_clips(
    show_slug: str,
    *,
    digests_dir: Path,
    limit: int = 3,
    cache_dir: Optional[Path] = None,
) -> List[Path]:
    """Download up to ``limit`` curated evergreen clips for a show.

    Reads the committed ``broll.json`` pool (see
    ``scripts/build_broll_pool.py``) and returns local Paths in the pool's
    stable committed order — no scoring, the operator curated the order.
    Best-effort: a failed download is skipped (the next entry backfills);
    a missing pool file is a clean ``[]``. Never raises.
    """
    try:
        entries = load_broll_entries(Path(digests_dir))
        if not entries or limit <= 0:
            return []
        cdir = (Path(cache_dir) if cache_dir
                else _default_cache_dir() / "broll" / show_slug)
        cdir.mkdir(parents=True, exist_ok=True)
        paths: List[Path] = []
        for entry in entries:
            if len(paths) >= limit:
                break
            url = str(entry["url"])
            dest = cdir / (url.rstrip("/").rsplit("/", 1)[-1] or "clip.mp4")
            if dest.exists() and dest.stat().st_size > 0:
                paths.append(dest)
                continue
            try:
                resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
                resp.raise_for_status()
                if not resp.content:
                    raise ValueError("empty response body")
                dest.write_bytes(resp.content)
                paths.append(dest)
            except Exception as exc:  # noqa: BLE001 — skip, keep going
                logger.warning("gallery_library: failed to fetch b-roll %s: %s",
                               url, exc)
        return paths
    except Exception as exc:  # noqa: BLE001 — b-roll is optional garnish
        logger.warning("gallery_library: b-roll selection failed for %s: %s",
                       show_slug, exc)
        return []
