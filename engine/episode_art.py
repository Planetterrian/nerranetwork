"""Per-episode square artwork for Apple's item-level ``<itunes:image>``.

Why this exists
---------------
Apple shows a thumbnail beside every episode in a show's episode list.
When a feed carries no item-level ``<itunes:image>``, every episode
inherits the channel cover — so a 30-episode video show renders as
thirty identical tiles. The network already generates a bespoke visual
per episode (the YouTube thumbnail, built from that day's freshest
Grok scene), it just had no square variant and no public URL, so the
feed had nothing to point at.

Apple's constraint is the awkward part: item artwork must be **square,
1400x1400 to 3000x3000, JPEG or PNG, RGB**. Nothing in the pipeline
produced a square image at any size — Grok is asked only for 16:9 and
9:16, and both thumbnail sizes are rectangular.

Approach
--------
Centre-crop the widest available source to a square and resize once
with Lanczos. A 16:9 Grok still is 1792x1024, so the crop is 1024x1024
and the resize to 1400 is a 1.37x upsample. That is visible at full
size and invisible at the 200-400 px tiles Apple actually renders,
which is the tradeoff worth taking: a distinct, on-topic image per
episode beats a pin-sharp identical one thirty times over.

Centre-crop rather than letterbox-with-blurred-fill deliberately. The
blurred-bar treatment preserves the whole frame but shrinks the actual
subject to about half the tile; at Apple's display size the subject
is what has to read.

Everything here is best-effort. Artwork is a nicety and the feed is
not: every failure path returns ``None`` and the caller falls through
to the channel cover.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

# Apple's minimum for episode artwork. Going larger buys nothing —
# the sources are smaller than this already, so a bigger canvas would
# only upsample further for no visible gain and a fatter file.
APPLE_MIN_EDGE = 1400

# Comfortably under Apple's practical size expectations while staying
# clean at 1400px. Measured around 180-260 KB on Grok stills.
_JPEG_QUALITY = 88


def _first_existing(candidates: Sequence[object]) -> Optional[Path]:
    for cand in candidates:
        if not cand:
            continue
        try:
            path = Path(str(cand))
        except (TypeError, ValueError):
            continue
        if path.is_file():
            return path
    return None


def build_square_art(
    sources: Sequence[object],
    out_path: Path,
    *,
    edge: int = APPLE_MIN_EDGE,
) -> Optional[Path]:
    """Write a square JPEG of *edge* px from the first usable source.

    *sources* is tried in order, so callers pass their preferred image
    first (the freshest 16:9 scene) and fall back through whatever else
    exists (the rendered YouTube thumbnail, the show cover).

    Returns the written path, or ``None`` if nothing usable was found or
    the encode failed. Never raises.
    """
    src = _first_existing(sources)
    if src is None:
        logger.debug("No usable source for episode artwork among %r", sources)
        return None

    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow is a hard dep elsewhere
        logger.warning("Pillow unavailable — skipping episode artwork")
        return None

    try:
        with Image.open(src) as im:
            # Apple rejects CMYK and palette artwork outright, and a
            # stray alpha channel makes the JPEG encoder throw.
            im = im.convert("RGB")
            w, h = im.size
            if w <= 0 or h <= 0:
                return None
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            square = im.crop((left, top, left + side, top + side))
            if side != edge:
                square = square.resize((edge, edge), Image.LANCZOS)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            square.save(out_path, "JPEG", quality=_JPEG_QUALITY, optimize=True)
    except Exception as exc:  # noqa: BLE001 — artwork must never break a run
        logger.warning("Episode artwork build failed from %s: %s", src, exc)
        return None

    logger.info("Episode artwork: %s (%dx%d, %.0f KB) from %s",
                out_path.name, edge, edge,
                out_path.stat().st_size / 1024, src.name)
    return out_path


# Own keyspace, beside ``video/`` rather than inside it, so a storage
# lifecycle rule can expire old MP4s without taking the artwork of every
# still-listed episode with them.
ART_PREFIX = "art"


def art_r2_key(slug: str, base_name: str) -> str:
    """``art/spacex/SpaceX_Daily_Ep046_20260727.jpg``.

    Deliberately deterministic — the gallery bucket keys on a content
    hash, which cannot be reconstructed from an episode number, so a
    lost index would orphan the artwork. This key can always be
    recomputed from the episode's filename stem.

    The ``.jpg`` extension is load-bearing, not cosmetic: Apple requires
    artwork URLs to end in ``.jpg`` or ``.png``, and feedgen enforces the
    same rule by raising on anything else. The gallery uploader writes
    ``.jpeg``, which fails both.
    """
    return f"{ART_PREFIX}/{slug}/{base_name}.jpg"


def publish_square_art(
    sources: Sequence[object],
    *,
    config,
    work_dir: Path,
    base_name: str,
) -> str:
    """Build the square artwork, upload it, and return its public URL.

    Uses the show's own R2 storage config — the same bucket and
    credentials the episode MP4 goes to, already validated by the time
    this runs. Returns ``""`` on any failure or when storage is not
    configured; the feed then emits no item-level image and Apple falls
    back to the channel cover, which is exactly the previous behaviour.
    """
    slug = getattr(config, "slug", "") or "show"
    storage = getattr(config, "storage", None)
    if not storage or getattr(storage, "provider", "") != "r2":
        return ""

    art_path = build_square_art(sources, work_dir / f"{base_name}_square.jpg")
    if art_path is None:
        return ""

    try:
        import os

        from engine.storage import upload_to_r2

        endpoint = os.getenv(storage.endpoint_env, "")
        access_key = os.getenv(storage.access_key_env, "")
        secret_key = os.getenv(storage.secret_key_env, "")
        if not (endpoint and access_key and secret_key):
            logger.info("[%s] R2 credentials unset — no episode artwork URL",
                        slug)
            return ""

        url = upload_to_r2(
            art_path, art_r2_key(slug, base_name),
            bucket=storage.bucket,
            endpoint_url=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            public_base_url=storage.public_base_url,
            content_type="image/jpeg",
        )
    except Exception as exc:  # noqa: BLE001 — never block a publish
        logger.warning("[%s] episode artwork upload failed (non-fatal): %s",
                       slug, exc)
        return ""

    url = url or ""
    if url:
        logger.info("[%s] episode artwork -> %s", slug, url)
    return url
