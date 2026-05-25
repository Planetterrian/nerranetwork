#!/usr/bin/env python3
"""Diagnose the gallery R2 wiring end-to-end.

Run when the gallery page is empty after Tesla / MAB runs and you
need to find out *where* the chain broke. Reads the same env vars the
live pipeline reads (``R2_GALLERY_BUCKET``, ``R2_ENDPOINT_URL``,
``R2_ACCESS_KEY_ID``, ``R2_SECRET_ACCESS_KEY``,
``R2_GALLERY_PUBLIC_BASE_URL``) and walks five checks:

  1. Env vars present.
  2. boto3 S3 client constructible.
  3. ``head_bucket`` succeeds (auth + bucket name correct + region OK).
  4. ``list_objects_v2`` returns something (bucket has contents).
  5. The Phase 2 manifest builder produces a non-empty manifest.

Each step prints PASS/FAIL with the underlying error message. The
script exits 0 on all-pass, 1 on any fail — so the operator can wire
it into a smoke-test script if they want.

Run::

    python scripts/diagnose_gallery.py
    python scripts/diagnose_gallery.py --probe-write     # actually
                                                          # upload a
                                                          # 1×1 test
                                                          # image
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.gallery_uploader import (  # noqa: E402
    ImageMetadata,
    gallery_config_from_env,
    upload_image,
)

logger = logging.getLogger("diagnose_gallery")

CHECK_MARK = "✅"  # ✅
CROSS_MARK = "❌"  # ❌
WARN_MARK = "⚠️"  # ⚠️


def _pass(msg: str) -> None:
    print(f"{CHECK_MARK} {msg}")


def _fail(msg: str) -> None:
    print(f"{CROSS_MARK} {msg}")


def _warn(msg: str) -> None:
    print(f"{WARN_MARK} {msg}")


def check_env() -> bool:
    print("\n=== 1. Environment variables ===")
    expected = {
        "R2_GALLERY_BUCKET": os.getenv("R2_GALLERY_BUCKET", ""),
        "R2_GALLERY_PUBLIC_BASE_URL": os.getenv("R2_GALLERY_PUBLIC_BASE_URL", ""),
        "R2_ENDPOINT_URL": os.getenv("R2_ENDPOINT_URL", ""),
        "R2_ACCESS_KEY_ID": os.getenv("R2_ACCESS_KEY_ID", ""),
        "R2_SECRET_ACCESS_KEY": os.getenv("R2_SECRET_ACCESS_KEY", ""),
    }
    ok = True
    for var, val in expected.items():
        if not val:
            if var == "R2_GALLERY_BUCKET":
                _warn(f"{var} not set (will default to 'nerra-gallery')")
            elif var == "R2_GALLERY_PUBLIC_BASE_URL":
                _warn(
                    f"{var} not set (URLs in the manifest will point at "
                    "the raw R2 endpoint — fine for the Worker proxy, but "
                    "the public gallery would 403 without a custom domain)"
                )
            else:
                _fail(f"{var} is empty")
                ok = False
        else:
            display = (
                val[:8] + "…" + val[-4:]
                if var.endswith("KEY") or var.endswith("ID")
                else val
            )
            _pass(f"{var} = {display}")
    return ok


def check_client() -> tuple[bool, object]:
    print("\n=== 2. S3 client constructible ===")
    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except ImportError as e:
        _fail(f"boto3 not installed: {e}")
        return False, None

    config = gallery_config_from_env()
    if not config.is_configured:
        _fail("gallery_config_from_env().is_configured is False")
        return False, None

    try:
        client = boto3.client(
            "s3",
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            config=BotoConfig(
                signature_version="s3v4",
                retries={"max_attempts": 1},
            ),
        )
    except Exception as e:
        _fail(f"client construction failed: {type(e).__name__}: {e}")
        return False, None
    _pass(f"S3 client built (endpoint={config.endpoint_url})")
    return True, client


def check_head_bucket(client) -> bool:
    print("\n=== 3. head_bucket — auth + bucket name + region ===")
    config = gallery_config_from_env()
    try:
        client.head_bucket(Bucket=config.bucket)
    except Exception as e:
        _fail(
            f"head_bucket({config.bucket!r}) failed: "
            f"{type(e).__name__}: {e}"
        )
        _warn(
            "Common causes:\n"
            "  - Bucket name typo (operator created the bucket with a "
            "different name than R2_GALLERY_BUCKET).\n"
            "  - R2 token doesn't have read permission on this bucket.\n"
            "  - The R2 token is scoped to a single bucket (e.g. "
            "'podcast-audio') and can't see the gallery bucket.\n"
            "  - Wrong endpoint URL for the R2 account."
        )
        return False
    _pass(f"head_bucket({config.bucket!r}) OK")
    return True


def check_list(client) -> tuple[bool, int, int]:
    print("\n=== 4. list_objects_v2 — bucket contents ===")
    config = gallery_config_from_env()
    try:
        paginator = client.get_paginator("list_objects_v2")
        total = 0
        sidecars = 0
        for page in paginator.paginate(Bucket=config.bucket, MaxKeys=1000):
            for obj in page.get("Contents", []) or []:
                total += 1
                if obj.get("Key", "").endswith(".json"):
                    sidecars += 1
    except Exception as e:
        _fail(f"list_objects_v2 failed: {type(e).__name__}: {e}")
        return False, 0, 0
    _pass(f"list_objects_v2 OK — {total} object(s), {sidecars} sidecar(s)")
    if total == 0:
        _warn(
            "Bucket is empty. Either:\n"
            "  (a) no Grok-Imagine episode has run yet,\n"
            "  (b) the run-show CI is uploading to a different "
            "bucket / can't reach this one (check metrics_ep*.json for "
            "the latest episode — look for `gallery_attempted` and "
            "`gallery_skipped_reason`),\n"
            "  (c) the bucket was created today and writes are still "
            "propagating (unlikely on R2)."
        )
    return True, total, sidecars


def check_manifest(client, sidecar_count: int) -> bool:
    print("\n=== 5. Manifest builder produces a non-empty manifest ===")
    if sidecar_count == 0:
        _warn(
            "Skipping — bucket has no sidecars to assemble from. Fix "
            "step 4 first."
        )
        return False
    from scripts.build_gallery_manifest import build_manifest, walk_bucket
    config = gallery_config_from_env()
    sidecars = walk_bucket(config)
    manifest = build_manifest(sidecars, config=config)
    if manifest["image_count"] == 0:
        _fail("walk_bucket returned 0 sidecars despite list reporting some")
        return False
    _pass(
        f"manifest builder OK — image_count={manifest['image_count']}, "
        f"shows={len(manifest['shows'])}"
    )
    return True


def probe_write() -> bool:
    """Optional step: actually upload a 1×1 test image to confirm
    write permission. Only runs with --probe-write."""
    print("\n=== 6. Probe write (1×1 test image) ===")
    try:
        from PIL import Image
    except ImportError:
        _fail("Pillow not installed; can't make a test image")
        return False
    img = Image.new("RGB", (1, 1), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    ts = time.strftime("%Y-%m-%d")
    meta = ImageMetadata(
        image_id="",
        show_slug="_diagnostic",
        show_name="Gallery diagnostic probe",
        episode_id=f"ep{int(time.time()) % 1000:03d}",
        episode_title=f"Probe write at {ts}",
        episode_date=ts,
        prompt="(diagnostic probe — safe to delete)",
        model="diagnose_gallery.py",
        intended_use="other",
        tags=["_diagnostic"],
    )
    result = upload_image(buf.getvalue(), meta)
    if result is None:
        _fail(
            "upload_image returned None — look further up the output "
            "for the underlying R2 error logged by engine.gallery_uploader."
        )
        return False
    _pass(
        f"probe write OK — image_id={result.image_id} "
        f"key={result.original_key}\n"
        f"   thumbnail={result.thumbnail_url}\n"
        f"   sidecar={result.sidecar_url}"
    )
    _warn(
        "The probe writes a real object under _diagnostic/. Delete it "
        "from the R2 dashboard when you're done."
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe-write", action="store_true",
        help="Also attempt to upload a 1×1 probe image (writes one "
             "object under _diagnostic/ in the gallery bucket).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )

    env_ok = check_env()
    if not env_ok:
        print("\nEnv var problems above. Fix those before re-running.")
        return 1

    client_ok, client = check_client()
    if not client_ok:
        return 1

    head_ok = check_head_bucket(client)
    if not head_ok:
        return 1

    list_ok, _total, sidecars = check_list(client)
    if not list_ok:
        return 1

    manifest_ok = check_manifest(client, sidecars)

    write_ok = True
    if args.probe_write:
        write_ok = probe_write()

    print()
    if env_ok and client_ok and head_ok and list_ok and (
        manifest_ok or sidecars == 0
    ) and write_ok:
        print(f"{CHECK_MARK} All checks passed.")
        if sidecars == 0:
            print(
                f"{WARN_MARK} Bucket is empty though — see step 4 above for "
                "next steps."
            )
        return 0
    print(f"{CROSS_MARK} One or more checks failed; see output above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
