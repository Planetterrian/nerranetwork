#!/usr/bin/env python3
"""Rebuild the gallery manifest from the R2 ``nerra-gallery`` bucket.

Phase 2 of the gallery feature. Walks every ``*.json`` sidecar in the
gallery bucket, downloads + parses each, and writes one aggregated
manifest to ``site/data/gallery-manifest.json``. The gallery page (and
each show's embedded gallery) consume the manifest client-side to
render thumbnails, run filters / sort, and link to the gated download.

Schema (versioned via ``schema_version``)::

    {
      "schema_version": 1,
      "generated_at": "2026-05-24T15:30:00+00:00",
      "image_count": 124,
      "show_counts": {"tesla": 84, "models_agents_beginners": 40},
      "shows": [
        {"slug": "tesla", "name": "Tesla Shorts Time", "image_count": 84},
        ...
      ],
      "images": [
         {  ... sidecar fields ... ,
           "original_url": "https://gallery.../.../<id>.jpeg",
           "thumbnail_url": "https://gallery.../.../<id>.thumb.webp",
           "sidecar_url": "https://gallery.../.../<id>.json"
         },
         ...
      ]
    }

Images are sorted newest-first by ``generated_at`` (falling back to
``episode_date``) so the gallery page's default "Newest" sort matches
the manifest's natural ordering and the JS doesn't have to re-sort on
load.

The script is **idempotent** and **safe to run anywhere**:

* When R2 isn't configured (env vars missing), it logs a warning and
  writes an empty manifest. The HTML gallery handles the empty case.
* When a sidecar fails to parse, the script logs and skips that
  image — never crashes the whole build.
* When the only change to the manifest is the ``generated_at``
  timestamp, the script does **not** rewrite the file (so the CI
  workflow's ``git diff --cached --quiet`` check stays clean and
  avoids no-op commits).

Run::

    python scripts/build_gallery_manifest.py
    python scripts/build_gallery_manifest.py --out site/data/gallery-manifest.json
    python scripts/build_gallery_manifest.py --dry-run     # don't write
    python scripts/build_gallery_manifest.py --indexes-only  # no R2: slices +
                                                             # slim indexes from --out

Every write also produces the slim indexes the pages load
(``site/data/gallery/_network.index.json`` and ``<slug>.index.json`` —
``build_gallery_index``), derived from the manifest of the same run.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.gallery_uploader import (  # noqa: E402
    GalleryConfig,
    gallery_config_from_env,
)

logger = logging.getLogger("build_gallery_manifest")

SCHEMA_VERSION = 1
DEFAULT_OUTPUT = PROJECT_ROOT / "site" / "data" / "gallery-manifest.json"


# ---------------------------------------------------------------------------
# R2 walk
# ---------------------------------------------------------------------------


def _make_s3_client(config: GalleryConfig):
    """Build a boto3 S3 client pointing at the gallery bucket.

    Imported lazily so this module can still be imported (and
    unit-tested) on machines without boto3 installed.
    """
    import boto3
    from botocore.config import Config as BotoConfig

    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        config=BotoConfig(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "adaptive"},
        ),
    )


def _iter_sidecar_keys(s3, bucket: str) -> Iterable[str]:
    """Yield every ``*.json`` key in the bucket, paginated."""
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []) or []:
            key = obj.get("Key", "")
            if key.endswith(".json"):
                yield key


def _fetch_sidecar(s3, bucket: str, key: str) -> Optional[Dict]:
    """Download + parse one sidecar. Returns ``None`` on any failure."""
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
        body = resp["Body"].read()
        return json.loads(body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read sidecar %s: %s", key, exc)
        return None


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------


REQUIRED_SIDECAR_FIELDS = (
    "image_id", "show_slug", "show_name", "episode_id", "episode_title",
    "episode_date", "format",
)

# Text-burned YouTube thumbnail composites are stored in R2 for Studio
# "Test & Compare" A/B, but they are NOT useful in the public gallery
# (dark image + white hook text). Filter them out of the public
# manifest so visitors only see clean Grok Imagine scenes.
PUBLIC_GALLERY_EXCLUDED_USES = frozenset({
    "thumbnail_variant",
    "thumbnail",
    "youtube_thumbnail",
})


def _public_url(config: GalleryConfig, key: str) -> str:
    if config.public_base_url:
        base = config.public_base_url.rstrip("/")
    else:
        base = f"{config.endpoint_url.rstrip('/')}/{config.bucket}"
    return f"{base}/{key}"


def _build_object_keys(sidecar: Dict) -> Tuple[str, str, str]:
    """Reconstruct the three R2 keys from sidecar fields.

    Mirrors ``engine.gallery_uploader._build_keys`` — kept in sync so
    that the manifest builder never has to round-trip through the
    uploader module to learn the layout.
    """
    prefix = (
        f"{sidecar['show_slug']}/{sidecar['episode_date']}/{sidecar['episode_id']}"
    )
    stem = sidecar["image_id"]
    ext = (sidecar.get("format") or "jpeg").lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    return (
        f"{prefix}/{stem}.{ext}",
        f"{prefix}/{stem}.thumb.webp",
        f"{prefix}/{stem}.json",
    )


def _validate_sidecar(sidecar: Dict, source_key: str) -> bool:
    missing = [f for f in REQUIRED_SIDECAR_FIELDS if not sidecar.get(f)]
    if missing:
        logger.warning(
            "Sidecar %s missing required field(s) %s — skipping",
            source_key, missing,
        )
        return False
    return True


def _sort_key(image: Dict) -> str:
    return (
        str(image.get("generated_at") or "")
        + "|"
        + str(image.get("episode_date") or "")
        + "|"
        + str(image.get("image_id") or "")
    )


def build_manifest(
    sidecars: Iterable[Dict],
    *,
    config: GalleryConfig,
    generated_at: Optional[str] = None,
) -> Dict:
    """Build the manifest dict from an iterable of sidecar payloads.

    Pure function — the network walk (``_iter_sidecar_keys`` +
    ``_fetch_sidecar``) is the only side-effectful part of this module.
    Splitting them lets the unit tests pass in a hand-rolled list of
    sidecars instead of mocking the entire S3 layer.
    """
    images: List[Dict] = []
    show_counts: Dict[str, int] = {}
    show_names: Dict[str, str] = {}

    for sidecar in sidecars:
        if not isinstance(sidecar, dict):
            continue
        # _validate_sidecar already logs; just check the return.
        if not _validate_sidecar(sidecar, sidecar.get("image_id", "?")):
            continue

        # Skip text-burned thumbnail composites from the public gallery.
        use = str(sidecar.get("intended_use") or "").strip().lower()
        if use in PUBLIC_GALLERY_EXCLUDED_USES:
            continue
        tags = sidecar.get("tags") or []
        if isinstance(tags, list) and any(
            str(t).strip().lower() in PUBLIC_GALLERY_EXCLUDED_USES for t in tags
        ):
            continue

        original_key, thumb_key, sidecar_key = _build_object_keys(sidecar)
        record = dict(sidecar)
        record["original_url"] = _public_url(config, original_key)
        record["thumbnail_url"] = _public_url(config, thumb_key)
        record["sidecar_url"] = _public_url(config, sidecar_key)
        # Phase 3: the frontend passes this key to the Worker's
        # /api/download endpoint. The Worker validates the JWT cookie
        # then streams the R2 object from the bound bucket.
        record["original_key"] = original_key
        images.append(record)

        slug = sidecar["show_slug"]
        show_counts[slug] = show_counts.get(slug, 0) + 1
        if slug not in show_names:
            show_names[slug] = sidecar.get("show_name") or slug

    # Newest first. Stable enough — ``generated_at`` is RFC 3339, sorts
    # lexicographically; ``image_id`` tiebreaks for deterministic order.
    images.sort(key=_sort_key, reverse=True)

    shows = sorted(
        (
            {
                "slug": slug,
                "name": show_names[slug],
                "image_count": show_counts[slug],
            }
            for slug in show_counts
        ),
        key=lambda s: s["name"].lower(),
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": (
            generated_at
            or datetime.now(timezone.utc).isoformat(timespec="seconds")
        ),
        "image_count": len(images),
        "show_counts": show_counts,
        "shows": shows,
        "images": images,
    }


# ---------------------------------------------------------------------------
# Write / compare
# ---------------------------------------------------------------------------


def _without_timestamp(manifest: Dict) -> Dict:
    """Return a copy with ``generated_at`` stripped, for diffing."""
    return {k: v for k, v in manifest.items() if k != "generated_at"}


def write_manifest_if_changed(manifest: Dict, out_path: Path) -> bool:
    """Write ``manifest`` to ``out_path`` only if the content (excluding
    ``generated_at``) differs from what's already on disk.

    Returns ``True`` when the file was (re)written. This keeps the CI
    workflow's commit step a no-op when only the timestamp would
    change, avoiding a daily empty commit.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    new_payload = _without_timestamp(manifest)
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            if _without_timestamp(existing) == new_payload:
                logger.info(
                    "Manifest content unchanged (image_count=%d) — "
                    "skipping write.", manifest["image_count"],
                )
                return False
        except Exception:  # noqa: BLE001 — bad file → overwrite
            logger.warning("Existing manifest unreadable — overwriting")

    out_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    logger.info(
        "Wrote %s (image_count=%d, shows=%d)",
        out_path, manifest["image_count"], len(manifest["shows"]),
    )
    return True


def write_show_slices(manifest: Dict, out_path: Path) -> List[Path]:
    """Write one per-show manifest slice next to the full manifest.

    Sep 4 2026 flagship pass: every gallery-enabled show page loaded the
    whole 14.2 MB manifest (7,680 images) and filtered it client-side to
    the ~500 images of one show — the heaviest thing a show page did, on
    every visit, on every phone. ``assets/js/gallery.js`` fetches
    ``site/data/gallery/<slug>.json`` when the embed is pinned to a show
    and falls back to the full manifest if the slice is missing.

    Slices are written to ``<out_dir>/gallery/<slug>.json`` and carry the
    same top-level shape (``schema_version``, ``generated_at``,
    ``image_count``, ``shows``, ``images``) so the frontend needs no
    second code path. Stale slices for shows no longer in the manifest
    are removed. Returns the paths written.
    """
    slice_dir = out_path.parent / "gallery"
    slice_dir.mkdir(parents=True, exist_ok=True)
    by_show: Dict[str, List[Dict]] = {}
    for img in manifest.get("images", []):
        by_show.setdefault(str(img.get("show_slug") or ""), []).append(img)
    written: List[Path] = []
    keep = set()
    for slug, images in by_show.items():
        if not slug:
            continue
        keep.add(f"{slug}.json")
        payload = {
            "schema_version": manifest.get("schema_version", SCHEMA_VERSION),
            "generated_at": manifest.get("generated_at"),
            "show_slug": slug,
            "image_count": len(images),
            "shows": [s for s in manifest.get("shows", []) if s.get("slug") == slug],
            "images": images,
        }
        target = slice_dir / f"{slug}.json"
        try:
            existing = json.loads(target.read_text(encoding="utf-8")) if target.exists() else None
        except Exception:  # noqa: BLE001 — bad file → overwrite
            existing = None
        if existing is not None and _without_timestamp(existing) == _without_timestamp(payload):
            continue
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        written.append(target)
    for stale in slice_dir.glob("*.json"):
        # The slim indexes share the directory and own their own cleanup.
        if stale.name.endswith(INDEX_SUFFIX):
            continue
        if stale.name not in keep:
            stale.unlink()
    if written:
        logger.info("Wrote %d per-show gallery slice(s) under %s", len(written), slice_dir)
    return written


# ---------------------------------------------------------------------------
# Slim indexes (Oct 7 2026)
# ---------------------------------------------------------------------------

#: Every slim index ends in this, so ``site/data/gallery/*.json`` (already
#: whitelisted by both committing workflows) carries them and the slice
#: cleanup above can tell them apart from a show slice.
INDEX_SUFFIX = ".index.json"
#: The network-wide index. A leading underscore cannot collide with a slug.
NETWORK_INDEX_NAME = "_network" + INDEX_SUFFIX

#: Positional fields of one ``images`` row and one ``episodes`` row. The
#: client reads the positions from these lists, never from literals.
INDEX_IMAGE_FIELDS = ["image_id", "episode", "format", "caption", "intended_use"]
INDEX_EPISODE_FIELDS = ["show_slug", "episode_date", "episode_id", "episode_title"]
_INDEX_LICENSE_FIELDS = ("license", "license_url", "attribution")


def _key_stem(record: Dict) -> str:
    return (
        f"{record.get('show_slug')}/{record.get('episode_date')}/"
        f"{record.get('episode_id')}/{record.get('image_id')}"
    )


def build_gallery_index(manifest: Dict, show_slug: Optional[str] = None) -> Dict:
    """The grid's view of ``manifest``: no prompt, no derivable URL.

    Oct 7 2026: ``gallery.html`` parsed the whole 22 MB manifest before the
    first card — 6.7 MB of it prompts the lightbox hides by default and
    ~3 MB of URLs that are the R2 key under one base. The grid needs the
    id, the episode (show, date, title) and the thumbnail; the lightbox
    needs the licence (one value network-wide) and, when the visitor asks,
    the prompt — which ``assets/js/gallery.js`` reads lazily from the
    show's full slice. Episodes are a table (one title per episode, not
    per image) and images are positional rows.

    URLs are rebuilt client-side as ``base_url/<key>``; a record whose
    stored URL or key does not match that rule, or whose licence differs
    from the default, is carried verbatim in ``overrides`` (keyed by row
    position) so the index can never point at a different file than the
    manifest does.
    """
    images = [
        img for img in manifest.get("images") or []
        if isinstance(img, dict)
        and (show_slug is None or img.get("show_slug") == show_slug)
    ]

    bases: Dict[str, int] = {}
    licences: Dict[Tuple[str, str, str], int] = {}
    for img in images:
        thumb = str(img.get("thumbnail_url") or "")
        tail = "/" + _key_stem(img) + ".thumb.webp"
        if thumb.endswith(tail):
            base = thumb[: -len(tail)]
            bases[base] = bases.get(base, 0) + 1
        lic = tuple(str(img.get(f) or "") for f in _INDEX_LICENSE_FIELDS)
        licences[lic] = licences.get(lic, 0) + 1
    base_url = max(bases, key=bases.get) if bases else ""
    default_licence = (
        max(licences, key=licences.get) if licences
        else ("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/",
              "Nerra Network")
    )

    episodes: List[List[str]] = []
    episode_rows: Dict[Tuple[str, str, str], int] = {}
    rows: List[List] = []
    overrides: Dict[str, Dict] = {}
    for img in images:
        ep_key = (str(img.get("show_slug") or ""), str(img.get("episode_date") or ""),
                  str(img.get("episode_id") or ""))
        if ep_key not in episode_rows:
            episode_rows[ep_key] = len(episodes)
            episodes.append([*ep_key, str(img.get("episode_title") or "")])
        original_key = str(img.get("original_key") or "")
        stem = _key_stem(img)
        fmt = original_key[len(stem) + 1:] if original_key.startswith(stem + ".") else ""
        position = len(rows)
        rows.append([
            str(img.get("image_id") or ""), episode_rows[ep_key], fmt,
            str(img.get("caption") or ""), str(img.get("intended_use") or ""),
        ])
        override: Dict[str, str] = {}
        if not fmt:
            override["original_key"] = original_key
        if str(img.get("thumbnail_url") or "") != f"{base_url}/{stem}.thumb.webp":
            override["thumbnail_url"] = str(img.get("thumbnail_url") or "")
        if str(img.get("episode_title") or "") != episodes[episode_rows[ep_key]][3]:
            override["episode_title"] = str(img.get("episode_title") or "")
        for field, default in zip(_INDEX_LICENSE_FIELDS, default_licence):
            if str(img.get(field) or "") != default:
                override[field] = str(img.get(field) or "")
        if override:
            overrides[str(position)] = override

    shows = manifest.get("shows") or []
    if show_slug is not None:
        shows = [s for s in shows if s.get("slug") == show_slug]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": manifest.get("generated_at"),
        "image_count": len(rows),
        "show_slug": show_slug or "",
        "base_url": base_url,
        "license": default_licence[0],
        "license_url": default_licence[1],
        "attribution": default_licence[2],
        "shows": shows,
        "episode_fields": INDEX_EPISODE_FIELDS,
        "episodes": episodes,
        "image_fields": INDEX_IMAGE_FIELDS,
        "images": rows,
        "overrides": overrides,
    }


def write_gallery_indexes(manifest: Dict, out_path: Path) -> List[Path]:
    """Write the network index and one index per show beside the slices.

    Derived from the manifest of the SAME run, after it was written, so
    every path that keeps the committed manifest (a failed R2 walk returns
    before this) keeps the committed indexes too. Compact JSON with no
    indentation: these are read by browsers, not diffed by people. Stale
    per-show indexes are removed; unchanged ones are not rewritten.
    """
    slice_dir = out_path.parent / "gallery"
    slice_dir.mkdir(parents=True, exist_ok=True)
    slugs = sorted({
        str(img.get("show_slug") or "") for img in manifest.get("images") or []
        if isinstance(img, dict) and img.get("show_slug")
    })
    targets = {NETWORK_INDEX_NAME: build_gallery_index(manifest)}
    for slug in slugs:
        targets[slug + INDEX_SUFFIX] = build_gallery_index(manifest, slug)
    written: List[Path] = []
    for name, payload in targets.items():
        target = slice_dir / name
        try:
            existing = json.loads(target.read_text(encoding="utf-8")) if target.exists() else None
        except Exception:  # noqa: BLE001 — bad file → overwrite
            existing = None
        if existing is not None and _without_timestamp(existing) == _without_timestamp(payload):
            continue
        target.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        written.append(target)
    for stale in slice_dir.glob("*" + INDEX_SUFFIX):
        if stale.name not in targets:
            stale.unlink()
    if written:
        logger.info("Wrote %d gallery index file(s) under %s", len(written), slice_dir)
    return written


def empty_manifest(config: GalleryConfig) -> Dict:
    """Build the manifest representing zero images.

    Returned both when R2 isn't configured and when the bucket is
    actually empty. The HTML gallery handles the empty case ("No
    images yet — check back after the first episode publish.").
    """
    return build_manifest([], config=config)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


# Sidecar downloads run in parallel: one GET is ~0.2 s from a GitHub
# runner, and the bucket holds 10,000+ sidecars, so a serial walk took
# 38 minutes on 2026-09-13 — inside run-show's finalize job, after EVERY
# episode (~13x/day). boto3 clients are thread-safe.
FETCH_WORKERS = 8


def cached_sidecars(existing: Optional[Dict]) -> Dict[str, Dict]:
    """Map sidecar R2 key -> record for every image in an existing manifest.

    The manifest records ARE the sidecars (``build_manifest`` copies the
    sidecar and adds the URL fields), so a committed manifest is a
    complete cache of every sidecar it lists. Records that cannot
    reconstruct their key (a hand-edited or truncated file) are simply
    not cached and get fetched again.
    """
    out: Dict[str, Dict] = {}
    if not isinstance(existing, dict):
        return out
    for record in existing.get("images") or []:
        if not isinstance(record, dict):
            continue
        try:
            out[_build_object_keys(record)[2]] = record
        except (KeyError, TypeError):
            continue
    return out


def walk_bucket(
    config: GalleryConfig,
    *,
    existing: Optional[Dict] = None,
    full: bool = False,
    workers: int = FETCH_WORKERS,
) -> List[Dict]:
    """Network walk: list every sidecar key, fetch the ones we do not have.

    Sep 13 2026 — INCREMENTAL by default. The key listing is cheap (a
    dozen paginated calls); the per-sidecar GETs are what cost 38
    minutes per finalize. With ``existing`` (the committed manifest)
    only keys absent from it are downloaded; keys that vanished from the
    bucket drop out because the listing is the source of truth. A
    sidecar EDITED in place is not noticed on an incremental pass — the
    nightly runs ``--full`` for exactly that. Sidecars the manifest
    excludes (thumbnail composites) are never in the cache and are
    re-read every pass; that is ~1,400 objects, seconds across
    ``workers`` threads, and keeps the cache honest without a second
    committed file.
    """
    from concurrent.futures import ThreadPoolExecutor

    s3 = _make_s3_client(config)
    keys = list(_iter_sidecar_keys(s3, config.bucket))
    logger.info("Found %d sidecar(s) in bucket %s", len(keys), config.bucket)

    cache = {} if full else cached_sidecars(existing)
    sidecars: List[Dict] = []
    to_fetch: List[str] = []
    for key in keys:
        hit = cache.get(key)
        if hit is not None:
            sidecars.append(hit)
        else:
            to_fetch.append(key)
    logger.info(
        "Reusing %d cached sidecar(s), fetching %d%s",
        len(sidecars), len(to_fetch), " (full rebuild)" if full else "",
    )

    fetched = 0
    if to_fetch:
        with ThreadPoolExecutor(max_workers=max(1, int(workers or 1))) as pool:
            for body in pool.map(
                lambda k: _fetch_sidecar(s3, config.bucket, k), to_fetch
            ):
                if body is not None:
                    sidecars.append(body)
                    fetched += 1
    logger.info("Fetched %d sidecar(s)", fetched)
    return sidecars


def load_existing_manifest(path: Path) -> Optional[Dict]:
    """The committed manifest, or ``None`` when absent/unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUTPUT,
        help=f"Output manifest path (default: {DEFAULT_OUTPUT.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Compute the manifest but don't write or commit.",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Re-download every sidecar instead of reusing the records "
             "already in --out (the nightly safety rebuild; catches "
             "sidecars edited in place).",
    )
    parser.add_argument(
        "--workers", type=int, default=FETCH_WORKERS,
        help=f"Parallel sidecar downloads (default {FETCH_WORKERS}).",
    )
    parser.add_argument(
        "--indexes-only", action="store_true",
        help="Do not touch R2: rebuild the per-show slices and the slim "
             "indexes from the manifest already at --out.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if args.indexes_only:
        existing = load_existing_manifest(args.out)
        if not existing or not (existing.get("images") or []):
            # Never derive an empty index from a missing manifest: that is
            # how the site would show "no images" with the data still in R2.
            logger.error("No populated manifest at %s — nothing written", args.out)
            return 1
        write_show_slices(existing, args.out)
        write_gallery_indexes(existing, args.out)
        return 0

    config = gallery_config_from_env()
    if not config.is_configured:
        logger.warning(
            "Gallery R2 not configured — writing empty manifest. Set "
            "R2_GALLERY_BUCKET + R2_ENDPOINT_URL + R2_ACCESS_KEY_ID + "
            "R2_SECRET_ACCESS_KEY to actually scan the bucket.",
        )
        manifest = empty_manifest(config)
    else:
        existing = load_existing_manifest(args.out)
        try:
            sidecars = walk_bucket(
                config, existing=existing, full=args.full, workers=args.workers,
            )
        except Exception as exc:  # noqa: BLE001 — never crash CI
            # Sep 13 2026: a failed walk used to write an EMPTY manifest,
            # which would have wiped 9,000+ images from every gallery
            # (and deleted the per-show slices) on one R2 hiccup — the
            # search-index lesson of July 24. Keep what is committed.
            if existing and (existing.get("images") or []):
                logger.error(
                    "R2 bucket walk failed (%s): %s — keeping the existing "
                    "manifest (%d image(s)) untouched",
                    type(exc).__name__, exc, len(existing.get("images") or []),
                )
                return 0
            logger.error(
                "R2 bucket walk failed (%s): %s — writing empty manifest",
                type(exc).__name__, exc,
            )
            sidecars = []
        manifest = build_manifest(sidecars, config=config)

    if args.dry_run:
        logger.info(
            "[dry-run] would write %d image(s) to %s", manifest["image_count"],
            args.out,
        )
        # Print the head for inspection (no need to dump 10k images).
        preview = dict(manifest)
        preview["images"] = manifest["images"][:3]
        print(json.dumps(preview, indent=2, ensure_ascii=False))
        return 0

    write_manifest_if_changed(manifest, args.out)
    write_show_slices(manifest, args.out)
    write_gallery_indexes(manifest, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
