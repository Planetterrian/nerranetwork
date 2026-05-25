"""Unit tests for ``scripts/build_gallery_manifest``.

Covers the pure manifest assembly (URL construction, sort order, show
counts) and the write-if-changed path (no-op when only timestamp
differs). The network walk is tiny glue around boto3 paginators and is
not unit-tested here — it'd require mocking three boto3 surfaces for
little signal.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.gallery_uploader import GalleryConfig  # noqa: E402
from scripts import build_gallery_manifest as bgm  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> GalleryConfig:
    return GalleryConfig(
        bucket="nerra-gallery",
        endpoint_url="https://acct.r2.cloudflarestorage.com",
        access_key="fake",
        secret_key="fake",
        public_base_url="https://gallery.example.com",
    )


def _sidecar(
    *, image_id, slug="tesla", name="Tesla Shorts Time",
    episode_id="ep001", episode_title="Ep 1", episode_date="2026-05-24",
    generated_at="2026-05-24T15:00:00+00:00", fmt="jpeg",
    prompt="a tesla cybertruck",
):
    return {
        "image_id": image_id,
        "show_slug": slug,
        "show_name": name,
        "episode_id": episode_id,
        "episode_title": episode_title,
        "episode_date": episode_date,
        "generated_at": generated_at,
        "format": fmt,
        "prompt": prompt,
        "model": "grok-imagine-image",
        "intended_use": "segment_card",
        "width": 1792,
        "height": 1024,
        "file_size": 215000,
        "caption": "",
        "tags": [slug, "segment_card"],
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "attribution": "Nerra Network",
        "youtube_video_id": "",
    }


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------


def test_public_url_uses_public_base_when_set(config):
    url = bgm._public_url(config, "tesla/2026-05-24/ep001/abc.jpeg")
    assert url == "https://gallery.example.com/tesla/2026-05-24/ep001/abc.jpeg"


def test_public_url_falls_back_to_endpoint(config):
    config.public_base_url = ""
    url = bgm._public_url(config, "tesla/2026-05-24/ep001/abc.jpeg")
    assert url == (
        "https://acct.r2.cloudflarestorage.com/nerra-gallery/"
        "tesla/2026-05-24/ep001/abc.jpeg"
    )


def test_build_object_keys_matches_uploader_layout(config):
    sidecar = _sidecar(image_id="abc123def456", fmt="jpeg")
    original, thumb, sidecar_key = bgm._build_object_keys(sidecar)
    assert original == "tesla/2026-05-24/ep001/abc123def456.jpeg"
    assert thumb == "tesla/2026-05-24/ep001/abc123def456.thumb.webp"
    assert sidecar_key == "tesla/2026-05-24/ep001/abc123def456.json"


def test_build_object_keys_normalises_jpg_to_jpeg():
    sidecar = _sidecar(image_id="x", fmt="jpg")
    original, _, _ = bgm._build_object_keys(sidecar)
    assert original.endswith(".jpeg")


def test_build_object_keys_passes_png_through():
    sidecar = _sidecar(image_id="x", fmt="png")
    original, _, _ = bgm._build_object_keys(sidecar)
    assert original.endswith(".png")


# ---------------------------------------------------------------------------
# build_manifest
# ---------------------------------------------------------------------------


def test_build_manifest_empty_input(config):
    manifest = bgm.build_manifest([], config=config)
    assert manifest["image_count"] == 0
    assert manifest["images"] == []
    assert manifest["show_counts"] == {}
    assert manifest["shows"] == []
    assert manifest["schema_version"] == bgm.SCHEMA_VERSION
    assert "generated_at" in manifest


def test_build_manifest_sorts_newest_first(config):
    older = _sidecar(image_id="older", generated_at="2026-05-22T10:00:00+00:00")
    newer = _sidecar(image_id="newer", generated_at="2026-05-24T10:00:00+00:00")
    middle = _sidecar(image_id="middle", generated_at="2026-05-23T10:00:00+00:00")
    manifest = bgm.build_manifest([older, newer, middle], config=config)
    assert [img["image_id"] for img in manifest["images"]] == [
        "newer", "middle", "older",
    ]


def test_build_manifest_aggregates_show_counts(config):
    sidecars = [
        _sidecar(image_id="t1", slug="tesla", name="Tesla Shorts Time"),
        _sidecar(image_id="t2", slug="tesla", name="Tesla Shorts Time"),
        _sidecar(
            image_id="m1", slug="models_agents_beginners",
            name="Models & Agents for Beginners",
        ),
    ]
    manifest = bgm.build_manifest(sidecars, config=config)
    assert manifest["show_counts"] == {"tesla": 2, "models_agents_beginners": 1}
    show_slugs = {s["slug"]: s for s in manifest["shows"]}
    assert show_slugs["tesla"]["name"] == "Tesla Shorts Time"
    assert show_slugs["models_agents_beginners"]["image_count"] == 1


def test_build_manifest_skips_invalid_sidecars(config, caplog):
    bad = {"image_id": "missing_show_slug"}  # missing required fields
    good = _sidecar(image_id="ok")
    manifest = bgm.build_manifest([bad, good], config=config)
    assert manifest["image_count"] == 1
    assert manifest["images"][0]["image_id"] == "ok"


def test_build_manifest_attaches_urls_to_every_image(config):
    sidecar = _sidecar(image_id="abc")
    manifest = bgm.build_manifest([sidecar], config=config)
    img = manifest["images"][0]
    assert img["thumbnail_url"].endswith("/abc.thumb.webp")
    assert img["original_url"].endswith("/abc.jpeg")
    assert img["sidecar_url"].endswith("/abc.json")
    # Phase 3: frontend passes this key to /api/download.
    assert img["original_key"] == "tesla/2026-05-24/ep001/abc.jpeg"
    # Original sidecar fields are preserved.
    assert img["prompt"] == "a tesla cybertruck"
    assert img["license"] == "CC BY-SA 4.0"


def test_build_manifest_ignores_non_dict_entries(config):
    sidecar = _sidecar(image_id="ok")
    manifest = bgm.build_manifest(
        [sidecar, None, "not a dict", 42], config=config,
    )
    assert manifest["image_count"] == 1


# ---------------------------------------------------------------------------
# write_manifest_if_changed
# ---------------------------------------------------------------------------


def test_write_creates_file_when_missing(tmp_path, config):
    out = tmp_path / "site" / "data" / "gallery-manifest.json"
    manifest = bgm.build_manifest([_sidecar(image_id="a")], config=config)
    written = bgm.write_manifest_if_changed(manifest, out)
    assert written is True
    assert out.exists()
    on_disk = json.loads(out.read_text())
    assert on_disk["image_count"] == 1


def test_write_is_noop_when_only_timestamp_differs(tmp_path, config):
    out = tmp_path / "manifest.json"
    first = bgm.build_manifest(
        [_sidecar(image_id="a")], config=config,
        generated_at="2026-05-24T10:00:00+00:00",
    )
    bgm.write_manifest_if_changed(first, out)
    first_mtime = out.stat().st_mtime

    second = bgm.build_manifest(
        [_sidecar(image_id="a")], config=config,
        generated_at="2026-05-25T10:00:00+00:00",
    )
    written = bgm.write_manifest_if_changed(second, out)
    assert written is False
    assert out.stat().st_mtime == first_mtime
    # File still holds the first timestamp.
    on_disk = json.loads(out.read_text())
    assert on_disk["generated_at"] == "2026-05-24T10:00:00+00:00"


def test_write_rewrites_when_content_changes(tmp_path, config):
    out = tmp_path / "manifest.json"
    first = bgm.build_manifest(
        [_sidecar(image_id="a")], config=config,
        generated_at="2026-05-24T10:00:00+00:00",
    )
    bgm.write_manifest_if_changed(first, out)

    second = bgm.build_manifest(
        [_sidecar(image_id="a"), _sidecar(image_id="b", episode_id="ep002")],
        config=config,
        generated_at="2026-05-25T10:00:00+00:00",
    )
    written = bgm.write_manifest_if_changed(second, out)
    assert written is True
    on_disk = json.loads(out.read_text())
    assert on_disk["image_count"] == 2


def test_write_recovers_from_corrupt_existing_file(tmp_path, config):
    out = tmp_path / "manifest.json"
    out.write_text("{ not valid json ::")
    manifest = bgm.build_manifest([_sidecar(image_id="a")], config=config)
    written = bgm.write_manifest_if_changed(manifest, out)
    assert written is True
    assert json.loads(out.read_text())["image_count"] == 1


# ---------------------------------------------------------------------------
# empty_manifest
# ---------------------------------------------------------------------------


def test_empty_manifest_has_zero_images(config):
    manifest = bgm.empty_manifest(config)
    assert manifest["image_count"] == 0
    assert manifest["images"] == []
    assert manifest["schema_version"] == bgm.SCHEMA_VERSION


# ---------------------------------------------------------------------------
# main() — orchestration with R2 unconfigured
# ---------------------------------------------------------------------------


def test_main_writes_empty_manifest_when_r2_unconfigured(tmp_path, monkeypatch):
    for var in ("R2_GALLERY_BUCKET", "R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID",
                "R2_SECRET_ACCESS_KEY", "R2_GALLERY_PUBLIC_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    out = tmp_path / "manifest.json"
    rc = bgm.main(["--out", str(out)])
    assert rc == 0
    assert out.exists()
    payload = json.loads(out.read_text())
    assert payload["image_count"] == 0
    assert payload["schema_version"] == bgm.SCHEMA_VERSION


def test_main_dry_run_does_not_write(tmp_path, monkeypatch, capsys):
    for var in ("R2_GALLERY_BUCKET", "R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID",
                "R2_SECRET_ACCESS_KEY", "R2_GALLERY_PUBLIC_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    out = tmp_path / "manifest.json"
    rc = bgm.main(["--dry-run", "--out", str(out)])
    assert rc == 0
    assert not out.exists()
    captured = capsys.readouterr().out
    assert '"image_count": 0' in captured
