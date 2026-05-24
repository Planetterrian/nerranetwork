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
"""

from __future__ import annotations

import argparse
import json
import logging
import os
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

        original_key, thumb_key, sidecar_key = _build_object_keys(sidecar)
        record = dict(sidecar)
        record["original_url"] = _public_url(config, original_key)
        record["thumbnail_url"] = _public_url(config, thumb_key)
        record["sidecar_url"] = _public_url(config, sidecar_key)
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


def walk_bucket(config: GalleryConfig) -> List[Dict]:
    """Network walk: list every sidecar and fetch it."""
    s3 = _make_s3_client(config)
    sidecars: List[Dict] = []
    keys = list(_iter_sidecar_keys(s3, config.bucket))
    logger.info("Found %d sidecar(s) in bucket %s", len(keys), config.bucket)
    for key in keys:
        body = _fetch_sidecar(s3, config.bucket, key)
        if body is not None:
            sidecars.append(body)
    return sidecars


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
        "-v", "--verbose", action="store_true",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    config = gallery_config_from_env()
    if not config.is_configured:
        logger.warning(
            "Gallery R2 not configured — writing empty manifest. Set "
            "R2_GALLERY_BUCKET + R2_ENDPOINT_URL + R2_ACCESS_KEY_ID + "
            "R2_SECRET_ACCESS_KEY to actually scan the bucket.",
        )
        manifest = empty_manifest(config)
    else:
        try:
            sidecars = walk_bucket(config)
        except Exception as exc:  # noqa: BLE001 — log + write empty rather than crash CI
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
