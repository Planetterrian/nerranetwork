"""Unit tests for ``engine.gallery_uploader``.

Covers the pure helpers (image-id determinism, thumbnail
resize+format+watermark, sidecar JSON schema) and the orchestration
path with R2 mocked at the boto3 boundary.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from engine import gallery_uploader as gu


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_test_jpeg(size=(1600, 900), color=(0, 80, 160)) -> bytes:
    """Synthesize a JPEG byte string at the requested size."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


@pytest.fixture
def sample_jpeg_bytes() -> bytes:
    return _make_test_jpeg()


@pytest.fixture
def configured_gallery(monkeypatch) -> gu.GalleryConfig:
    monkeypatch.setenv("R2_GALLERY_BUCKET", "test-bucket")
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "fake-access")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "fake-secret")
    monkeypatch.setenv("R2_GALLERY_PUBLIC_BASE_URL", "https://gallery.example.com")
    return gu.gallery_config_from_env()


# ---------------------------------------------------------------------------
# compute_image_id
# ---------------------------------------------------------------------------


def test_image_id_is_deterministic_for_same_bytes(sample_jpeg_bytes):
    assert gu.compute_image_id(sample_jpeg_bytes) == gu.compute_image_id(sample_jpeg_bytes)


def test_image_id_changes_when_bytes_change():
    a = _make_test_jpeg(color=(0, 0, 0))
    b = _make_test_jpeg(color=(255, 255, 255))
    assert gu.compute_image_id(a) != gu.compute_image_id(b)


def test_image_id_is_12_hex_chars(sample_jpeg_bytes):
    image_id = gu.compute_image_id(sample_jpeg_bytes)
    assert len(image_id) == 12
    assert all(c in "0123456789abcdef" for c in image_id)


# ---------------------------------------------------------------------------
# make_thumbnail
# ---------------------------------------------------------------------------


def test_thumbnail_downscales_long_edge_to_max(sample_jpeg_bytes):
    thumb_bytes = gu.make_thumbnail(sample_jpeg_bytes, max_edge=800)
    with Image.open(io.BytesIO(thumb_bytes)) as img:
        width, height = img.size
    assert max(width, height) == 800
    # Aspect roughly preserved (16:9 source).
    assert abs(width / height - 1600 / 900) < 0.02


def test_thumbnail_does_not_upscale_small_images():
    small_bytes = _make_test_jpeg(size=(400, 300))
    thumb_bytes = gu.make_thumbnail(small_bytes, max_edge=800)
    with Image.open(io.BytesIO(thumb_bytes)) as img:
        width, height = img.size
    assert width == 400
    assert height == 300


def test_thumbnail_is_webp(sample_jpeg_bytes):
    thumb_bytes = gu.make_thumbnail(sample_jpeg_bytes)
    with Image.open(io.BytesIO(thumb_bytes)) as img:
        assert img.format == "WEBP"


def test_thumbnail_watermark_changes_corner_pixels(sample_jpeg_bytes):
    """The corner that holds the watermark should differ from the
    same-coloured source image's corner after stamping."""
    with_mark = gu.make_thumbnail(sample_jpeg_bytes, watermark=True)
    without_mark = gu.make_thumbnail(sample_jpeg_bytes, watermark=False)

    with Image.open(io.BytesIO(with_mark)) as a, Image.open(io.BytesIO(without_mark)) as b:
        a = a.convert("RGB")
        b = b.convert("RGB")
        # Sample a patch in the bottom-right corner where the watermark
        # is rendered. The mark must alter pixels there.
        w, h = a.size
        patch_a = list(a.crop((w - 120, h - 40, w - 10, h - 5)).getdata())
        patch_b = list(b.crop((w - 120, h - 40, w - 10, h - 5)).getdata())
    assert patch_a != patch_b


def test_thumbnail_no_watermark_matches_clean_render(sample_jpeg_bytes):
    """Sanity check: when watermark=False, the corner stays flat colour."""
    clean = gu.make_thumbnail(sample_jpeg_bytes, watermark=False)
    with Image.open(io.BytesIO(clean)) as img:
        img = img.convert("RGB")
        w, h = img.size
        corner = set(img.crop((w - 50, h - 20, w - 5, h - 5)).getdata())
    # A flat-colour source should produce ~uniform pixels in the
    # corner (WebP introduces a tiny amount of chroma noise, so we
    # tolerate a handful of distinct colours rather than exactly 1).
    assert len(corner) <= 12


# ---------------------------------------------------------------------------
# probe_image
# ---------------------------------------------------------------------------


def test_probe_returns_dimensions_and_format(sample_jpeg_bytes):
    width, height, fmt = gu.probe_image(sample_jpeg_bytes)
    assert (width, height) == (1600, 900)
    assert fmt == "jpeg"


def test_probe_normalises_jpg_to_jpeg():
    img = Image.new("RGB", (100, 100), (10, 10, 10))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    width, height, fmt = gu.probe_image(buf.getvalue())
    assert fmt == "jpeg"


# ---------------------------------------------------------------------------
# ImageMetadata.to_json — schema check
# ---------------------------------------------------------------------------


REQUIRED_SIDECAR_KEYS = {
    "image_id", "show_slug", "show_name", "episode_id", "episode_title",
    "episode_date", "prompt", "model", "generated_at", "intended_use",
    "width", "height", "format", "file_size", "caption", "tags",
    "license", "license_url", "attribution", "youtube_video_id",
}


def test_sidecar_json_includes_every_required_key():
    meta = gu.ImageMetadata(
        image_id="abc123",
        show_slug="tesla",
        show_name="Tesla Shorts Time",
        episode_id="ep042",
        episode_title="Ep 42: Cybertruck",
        episode_date="2026-05-24",
    )
    payload = json.loads(meta.to_json())
    assert set(payload.keys()) == REQUIRED_SIDECAR_KEYS


def test_sidecar_license_default_is_cc_by_sa_4():
    meta = gu.ImageMetadata(
        image_id="x", show_slug="y", show_name="Z", episode_id="ep001",
        episode_title="t", episode_date="2026-01-01",
    )
    payload = json.loads(meta.to_json())
    assert payload["license"] == "CC BY-SA 4.0"
    assert payload["license_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"


def test_sidecar_tags_default_is_empty_list():
    meta = gu.ImageMetadata(
        image_id="x", show_slug="y", show_name="Z", episode_id="ep001",
        episode_title="t", episode_date="2026-01-01",
    )
    assert meta.tags == []
    # Mutating one instance must not leak into another (default_factory check).
    meta.tags.append("alpha")
    meta2 = gu.ImageMetadata(
        image_id="x2", show_slug="y", show_name="Z", episode_id="ep002",
        episode_title="t", episode_date="2026-01-01",
    )
    assert meta2.tags == []


# ---------------------------------------------------------------------------
# GalleryConfig.from_env
# ---------------------------------------------------------------------------


def test_gallery_config_defaults_bucket_to_nerra_gallery(monkeypatch):
    for var in ("R2_GALLERY_BUCKET", "R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID",
                "R2_SECRET_ACCESS_KEY", "R2_GALLERY_PUBLIC_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    config = gu.gallery_config_from_env()
    assert config.bucket == "nerra-gallery"
    assert config.is_configured is False  # no creds


def test_gallery_config_is_configured_when_all_required_set(configured_gallery):
    assert configured_gallery.is_configured is True


# ---------------------------------------------------------------------------
# upload_image — orchestration with mocked R2
# ---------------------------------------------------------------------------


def test_upload_image_returns_none_when_not_configured(sample_jpeg_bytes, monkeypatch):
    for var in ("R2_GALLERY_BUCKET", "R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID",
                "R2_SECRET_ACCESS_KEY", "R2_GALLERY_PUBLIC_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    meta = gu.ImageMetadata(
        image_id="", show_slug="tesla", show_name="Tesla Shorts Time",
        episode_id="ep001", episode_title="Ep 1", episode_date="2026-01-01",
    )
    result = gu.upload_image(sample_jpeg_bytes, meta)
    assert result is None


def test_upload_image_returns_none_on_empty_bytes(configured_gallery):
    meta = gu.ImageMetadata(
        image_id="", show_slug="tesla", show_name="Tesla Shorts Time",
        episode_id="ep001", episode_title="Ep 1", episode_date="2026-01-01",
    )
    result = gu.upload_image(b"", meta, gallery_config=configured_gallery)
    assert result is None


def test_upload_image_writes_three_objects(sample_jpeg_bytes, configured_gallery):
    """upload_image must call upload_to_r2 three times: original,
    thumbnail, sidecar."""
    calls = []

    def _fake_upload_to_r2(local_path, remote_key, **kwargs):
        # Read the bytes so we can assert on content type / size later.
        calls.append({
            "key": remote_key,
            "content_type": kwargs.get("content_type"),
            "size": Path(local_path).stat().st_size,
        })
        # Return what the real helper would.
        base = kwargs["public_base_url"] or kwargs["endpoint_url"]
        return f"{base.rstrip('/')}/{remote_key}"

    meta = gu.ImageMetadata(
        image_id="", show_slug="tesla", show_name="Tesla Shorts Time",
        episode_id="ep042", episode_title="Ep 42",
        episode_date="2026-05-24", prompt="a tesla cybertruck",
    )
    with patch.object(gu, "upload_to_r2", side_effect=_fake_upload_to_r2):
        result = gu.upload_image(
            sample_jpeg_bytes, meta, gallery_config=configured_gallery,
        )

    assert result is not None
    assert len(calls) == 3
    keys = [c["key"] for c in calls]
    # Order: original, thumbnail, sidecar.
    assert keys[0].endswith(".jpeg")
    assert keys[1].endswith(".thumb.webp")
    assert keys[2].endswith(".json")
    # All three share the same prefix.
    prefix = "tesla/2026-05-24/ep042/"
    assert all(k.startswith(prefix) for k in keys)
    # Same image-id stem across all three.
    stems = {k[len(prefix):].split(".", 1)[0] for k in keys}
    assert len(stems) == 1
    assert stems.pop() == result.image_id
    # Content types are right.
    assert calls[0]["content_type"] == "image/jpeg"
    assert calls[1]["content_type"] == "image/webp"
    assert calls[2]["content_type"] == "application/json"


def test_upload_image_fills_metadata_in_place(sample_jpeg_bytes, configured_gallery):
    meta = gu.ImageMetadata(
        image_id="", show_slug="tesla", show_name="Tesla Shorts Time",
        episode_id="ep042", episode_title="Ep 42",
        episode_date="2026-05-24",
    )

    def _ok(local_path, remote_key, **kwargs):
        return f"https://example.com/{remote_key}"

    with patch.object(gu, "upload_to_r2", side_effect=_ok):
        gu.upload_image(sample_jpeg_bytes, meta, gallery_config=configured_gallery)

    assert meta.image_id != ""
    assert meta.width == 1600
    assert meta.height == 900
    assert meta.format == "jpeg"
    assert meta.file_size == len(sample_jpeg_bytes)
    assert meta.generated_at != ""
    assert meta.license == "CC BY-SA 4.0"


def test_upload_image_returns_none_when_r2_raises(sample_jpeg_bytes, configured_gallery):
    def _boom(*args, **kwargs):
        raise RuntimeError("simulated R2 outage")

    meta = gu.ImageMetadata(
        image_id="", show_slug="tesla", show_name="Tesla Shorts Time",
        episode_id="ep001", episode_title="Ep 1", episode_date="2026-05-24",
    )
    with patch.object(gu, "upload_to_r2", side_effect=_boom):
        result = gu.upload_image(
            sample_jpeg_bytes, meta, gallery_config=configured_gallery,
        )
    assert result is None


def test_upload_image_idempotent_image_id_for_same_bytes(sample_jpeg_bytes, configured_gallery):
    """Two uploads of the same bytes must derive the same image_id —
    callers can rely on this for the de-duplication contract."""
    captured_keys = []

    def _capture(local_path, remote_key, **kwargs):
        captured_keys.append(remote_key)
        return f"https://example.com/{remote_key}"

    meta_a = gu.ImageMetadata(
        image_id="", show_slug="tesla", show_name="Tesla Shorts Time",
        episode_id="ep001", episode_title="Ep 1", episode_date="2026-05-24",
    )
    meta_b = gu.ImageMetadata(
        image_id="", show_slug="tesla", show_name="Tesla Shorts Time",
        episode_id="ep001", episode_title="Ep 1", episode_date="2026-05-24",
    )
    with patch.object(gu, "upload_to_r2", side_effect=_capture):
        result_a = gu.upload_image(sample_jpeg_bytes, meta_a, gallery_config=configured_gallery)
        result_b = gu.upload_image(sample_jpeg_bytes, meta_b, gallery_config=configured_gallery)
    assert result_a.image_id == result_b.image_id
    # Same keys = R2 would overwrite the same objects, no duplication.
    assert captured_keys[:3] == captured_keys[3:]


# ---------------------------------------------------------------------------
# R2 layout invariants
# ---------------------------------------------------------------------------


def test_r2_layout_matches_spec(sample_jpeg_bytes, configured_gallery):
    """Object keys must follow the documented
    ``{slug}/{YYYY-MM-DD}/{ep}/{id}.{ext}`` layout."""
    captured = []

    def _capture(local_path, remote_key, **kwargs):
        captured.append(remote_key)
        return f"https://example.com/{remote_key}"

    meta = gu.ImageMetadata(
        image_id="", show_slug="models_agents_beginners",
        show_name="Models & Agents for Beginners",
        episode_id="ep017", episode_title="Ep 17",
        episode_date="2026-05-12",
    )
    with patch.object(gu, "upload_to_r2", side_effect=_capture):
        gu.upload_image(sample_jpeg_bytes, meta, gallery_config=configured_gallery)

    assert captured[0].startswith("models_agents_beginners/2026-05-12/ep017/")
    assert captured[0].endswith(".jpeg")
    assert captured[1].endswith(".thumb.webp")
    assert captured[2].endswith(".json")
