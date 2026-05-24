"""Cloud storage helpers for podcast audio files.

Supports Cloudflare R2 (S3-compatible) for offloading MP3s from the git
repository.  See ``docs/audio_storage_plan.md`` for context.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def upload_to_r2(
    local_path: Path,
    remote_key: str,
    *,
    bucket: str,
    endpoint_url: str,
    access_key: str,
    secret_key: str,
    public_base_url: str = "",
    content_type: str = "",
) -> str:
    """Upload a file to Cloudflare R2 and return its public URL.

    Parameters
    ----------
    local_path:
        Local file to upload.
    remote_key:
        Object key in the bucket (e.g. ``"tesla/Ep042_20260216.mp3"``).
    bucket:
        R2 bucket name.
    endpoint_url:
        S3-compatible endpoint URL for the R2 account.
    access_key / secret_key:
        R2 API credentials.
    public_base_url:
        Public URL prefix for the bucket (e.g. ``"https://audio.example.com"``).
        If empty, constructs a URL from the endpoint.
    content_type:
        Override for the S3 ``ContentType`` header. When empty, defaults
        to ``audio/mpeg`` for ``.mp3`` paths and ``application/octet-stream``
        otherwise — the existing audio-upload contract.
    """
    import boto3
    from botocore.config import Config as BotoConfig

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=BotoConfig(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "adaptive"},
        ),
    )

    if not content_type:
        content_type = "audio/mpeg" if str(local_path).endswith(".mp3") else "application/octet-stream"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _upload():
        s3.upload_file(
            str(local_path),
            bucket,
            remote_key,
            ExtraArgs={"ContentType": content_type},
        )

    logger.info("Uploading %s → r2://%s/%s", local_path.name, bucket, remote_key)
    _upload()

    if public_base_url:
        url = f"{public_base_url.rstrip('/')}/{remote_key}"
    else:
        url = f"{endpoint_url}/{bucket}/{remote_key}"

    logger.info("Uploaded: %s", url)
    return url


def upload_episode(
    local_path: Path,
    config,
) -> Optional[str]:
    """Upload an episode MP3 to R2 if storage is configured.

    Reads R2 credentials from environment variables named in the config.
    Returns the public URL on success, or ``None`` if storage is not
    configured, credentials are missing, **or the upload failed for any
    reason** (timeouts, bad credentials, network errors, etc.).
    Failures are logged with the boto3 exception class so the operator
    can tell a credential issue from a transient network blip.

    Parameters
    ----------
    local_path:
        Path to the local MP3 file.
    config:
        A ``ShowConfig`` instance (must have ``storage`` attribute).
    """
    storage = getattr(config, "storage", None)
    if not storage or storage.provider != "r2":
        return None

    endpoint = os.getenv(storage.endpoint_env, "").strip()
    access_key = os.getenv(storage.access_key_env, "").strip()
    secret_key = os.getenv(storage.secret_key_env, "").strip()

    if not all([endpoint, access_key, secret_key]):
        logger.info("R2 credentials not set — skipping upload")
        return None

    remote_key = f"{config.slug}/{local_path.name}"

    try:
        return upload_to_r2(
            local_path,
            remote_key,
            bucket=storage.bucket,
            endpoint_url=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            public_base_url=storage.public_base_url,
        )
    except Exception as exc:  # noqa: BLE001 — we want every failure mode
        # boto3 surfaces these via botocore.exceptions; importing them
        # eagerly would force a hard dependency at module-import time
        # even when storage isn't configured. Catching the broad class
        # and logging the type name keeps the behavior contract simple
        # ("returns None on any failure") while preserving diagnostic
        # detail for the operator.
        logger.error(
            "R2 upload failed (%s): %s",
            type(exc).__name__, exc,
        )
        return None
