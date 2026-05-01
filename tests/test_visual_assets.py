"""Tests for the Pexels-backed scene-image fetcher.

The HTTP layer is mocked end-to-end so the suite never hits the
network. We verify keyword selection, fallback behaviour, cache
hits, and the attribution metadata that ends up in the YouTube
description.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from engine import visual_assets


# ---------------------------------------------------------------------------
# Keyword selection
# ---------------------------------------------------------------------------

def test_select_keywords_dedupes_and_lowercases():
    # No prefix — bare keyword behaviour preserved for shows that don't
    # set ``image_query_prefix``.
    out = visual_assets._select_keywords(
        ["Tesla", "TESLA", "Model 3", "model 3", "FSD"],
        limit=5,
    )
    # FSD (3-letter all-caps) is filtered as a SKU/acronym.
    assert "tesla" in out
    assert "model 3" in out
    assert "fsd" not in out  # in skip_too_short list
    assert len(out) == set(out).__len__()  # no duplicates


def test_select_keywords_respects_limit():
    out = visual_assets._select_keywords(
        ["a-1-very-long-keyword", "b-1", "c-1", "d-1", "e-1", "f-1"],
        limit=3,
    )
    assert len(out) == 3


def test_select_keywords_skips_pure_digits():
    out = visual_assets._select_keywords(["4680", "tesla", "100"])
    assert "4680" not in out
    assert "100" not in out
    assert "tesla" in out


# ---------------------------------------------------------------------------
# Fallback paths
# ---------------------------------------------------------------------------

def test_fetch_falls_back_to_cover_when_no_api_key(tmp_path: Path):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")  # JPEG magic bytes
    work = tmp_path / "youtube_tmp"

    result = visual_assets.fetch_scene_images(
        work_dir=work,
        episode_num=42,
        keywords=["tesla", "ev"],
        fallback_cover=cover,
        api_key="",
    )

    assert result.is_fallback is True
    assert len(result) == 1
    assert result.scenes[0].path == cover
    assert result.attribution_lines() == []


def test_fetch_returns_cached_set_on_second_call(tmp_path: Path):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    work = tmp_path / "youtube_tmp"

    first = visual_assets.fetch_scene_images(
        work_dir=work, episode_num=1,
        keywords=["tesla"], fallback_cover=cover, api_key="",
    )
    # Manifest written.
    manifest = work / "scenes_ep001" / "manifest.json"
    assert manifest.exists()

    # Second call must NOT call the API (api_key stays empty so an API
    # call would do nothing useful anyway, but we want to see cache hit).
    second = visual_assets.fetch_scene_images(
        work_dir=work, episode_num=1,
        keywords=["tesla"], fallback_cover=cover, api_key="some-key",
    )
    assert second.is_fallback == first.is_fallback
    assert second.paths() == first.paths()


# ---------------------------------------------------------------------------
# Pexels API plumbing (mocked)
# ---------------------------------------------------------------------------

def _fake_pexels_response(photo_ids):
    """Build a Pexels-shaped JSON response for a search."""
    photos = []
    for pid in photo_ids:
        photos.append({
            "id": pid,
            "url": f"https://pexels.com/photo/{pid}",
            "photographer": f"Photographer {pid}",
            "photographer_url": f"https://pexels.com/@{pid}",
            "src": {
                "large2x": f"https://images.pexels.com/photo{pid}_large2x.jpg",
                "large": f"https://images.pexels.com/photo{pid}_large.jpg",
            },
        })
    return {"photos": photos}


def test_fetch_with_api_key_downloads_photos(tmp_path: Path, monkeypatch):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    work = tmp_path / "youtube_tmp"

    queries_seen = []

    def fake_search(query, *, api_key, per_page=3):
        queries_seen.append(query)
        # Return 2 unique photo IDs per query so we can exercise dedupe.
        return _fake_pexels_response([
            f"{query}_1", f"{query}_2",
        ])

    downloads_seen = []

    def fake_download(url, dest):
        downloads_seen.append((url, dest))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\xFF\xD8")
        return dest

    monkeypatch.setattr(visual_assets, "_pexels_search", fake_search)
    monkeypatch.setattr(visual_assets, "_download_image", fake_download)

    result = visual_assets.fetch_scene_images(
        work_dir=work,
        episode_num=7,
        keywords=["tesla", "cybertruck", "model 3", "robotaxi", "supercharger"],
        fallback_cover=cover,
        api_key="fake-key",
        target_count=6,
    )

    assert result.is_fallback is False
    assert len(result) == 6
    # Each scene has the photographer credit.
    attributions = result.attribution_lines()
    assert all("Photographer" in line for line in attributions)
    assert len(attributions) == 6
    # We stopped querying once we hit target_count.
    assert len(queries_seen) <= 5


def test_fetch_dedupes_repeated_photo_ids(tmp_path: Path, monkeypatch):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    work = tmp_path / "youtube_tmp"

    def fake_search(query, *, api_key, per_page=3):
        # Every query returns the same photo id 99 — should dedupe.
        return _fake_pexels_response([99])

    monkeypatch.setattr(visual_assets, "_pexels_search", fake_search)
    monkeypatch.setattr(
        visual_assets, "_download_image",
        lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                           dest.write_bytes(b"\xFF\xD8"), dest)[2],
    )

    result = visual_assets.fetch_scene_images(
        work_dir=work, episode_num=8,
        keywords=["tesla", "cybertruck", "model 3"],
        fallback_cover=cover,
        api_key="fake-key",
        target_count=5,
    )

    # Only one unique photo, even though three queries returned it.
    assert len(result) == 1
    # Falls into the "got at least one photo, not fallback" branch.
    assert result.is_fallback is False


def test_fetch_falls_back_when_search_returns_nothing(tmp_path: Path, monkeypatch):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    work = tmp_path / "youtube_tmp"

    monkeypatch.setattr(
        visual_assets, "_pexels_search",
        lambda query, *, api_key, per_page=3: {"photos": []},
    )

    result = visual_assets.fetch_scene_images(
        work_dir=work, episode_num=9,
        keywords=["nonsense-no-results"],
        fallback_cover=cover, api_key="fake-key",
    )

    assert result.is_fallback is True
    assert len(result) == 1
    assert result.scenes[0].path == cover


def test_fetch_falls_back_when_search_raises(tmp_path: Path, monkeypatch):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    work = tmp_path / "youtube_tmp"

    def boom(*args, **kwargs):
        raise RuntimeError("Pexels is down")

    monkeypatch.setattr(visual_assets, "_pexels_search", boom)

    result = visual_assets.fetch_scene_images(
        work_dir=work, episode_num=10,
        keywords=["tesla"], fallback_cover=cover, api_key="fake-key",
    )

    # Should still cache + return a fallback set, not raise.
    assert result.is_fallback is True
    assert len(result) == 1


def test_fallback_cover_must_exist(tmp_path: Path):
    work = tmp_path / "youtube_tmp"
    with pytest.raises(FileNotFoundError, match="fallback_cover"):
        visual_assets.fetch_scene_images(
            work_dir=work, episode_num=1,
            keywords=["tesla"],
            fallback_cover=tmp_path / "missing.jpg",
            api_key="fake-key",
        )


# ---------------------------------------------------------------------------
# Manifest / cache
# ---------------------------------------------------------------------------

def test_manifest_contains_attribution(tmp_path: Path, monkeypatch):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    work = tmp_path / "youtube_tmp"

    monkeypatch.setattr(
        visual_assets, "_pexels_search",
        lambda q, *, api_key, per_page=3: _fake_pexels_response([42]),
    )
    monkeypatch.setattr(
        visual_assets, "_download_image",
        lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                           dest.write_bytes(b"\xFF\xD8"), dest)[2],
    )

    visual_assets.fetch_scene_images(
        work_dir=work, episode_num=11,
        keywords=["tesla"], fallback_cover=cover, api_key="fake-key",
    )

    manifest = work / "scenes_ep011" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["is_fallback"] is False
    assert len(data["scenes"]) == 1
    assert data["scenes"][0]["photographer"] == "Photographer 42"
    assert "https://pexels.com/photo/42" == data["scenes"][0]["pexels_url"]


def test_manifest_invalidates_on_missing_image(tmp_path: Path, monkeypatch):
    """If a cached image file is deleted, manifest is treated as invalid
    and we refetch."""
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    work = tmp_path / "youtube_tmp"

    monkeypatch.setattr(
        visual_assets, "_pexels_search",
        lambda q, *, api_key, per_page=3: _fake_pexels_response([55]),
    )
    monkeypatch.setattr(
        visual_assets, "_download_image",
        lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                           dest.write_bytes(b"\xFF\xD8"), dest)[2],
    )

    first = visual_assets.fetch_scene_images(
        work_dir=work, episode_num=12,
        keywords=["tesla"], fallback_cover=cover, api_key="fake-key",
    )
    # Delete the cached image — cache should now be invalid.
    first.scenes[0].path.unlink()

    fetch_calls = []

    def tracking_download(url, dest):
        fetch_calls.append(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\xFF\xD8")
        return dest

    monkeypatch.setattr(visual_assets, "_download_image", tracking_download)
    visual_assets.fetch_scene_images(
        work_dir=work, episode_num=12,
        keywords=["tesla"], fallback_cover=cover, api_key="fake-key",
    )
    # We re-downloaded.
    assert len(fetch_calls) == 1


# ---------------------------------------------------------------------------
# Curated image_queries override
# ---------------------------------------------------------------------------

def test_image_queries_override_keywords(tmp_path: Path, monkeypatch):
    """When ``image_queries`` is set, ``keywords`` is ignored verbatim."""
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    work = tmp_path / "youtube_tmp"

    queries_seen = []

    def fake_search(query, *, api_key, per_page=3):
        queries_seen.append(query)
        return _fake_pexels_response([f"id_{len(queries_seen)}"])

    monkeypatch.setattr(visual_assets, "_pexels_search", fake_search)
    monkeypatch.setattr(
        visual_assets, "_download_image",
        lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                           dest.write_bytes(b"\xFF\xD8"), dest)[2],
    )

    visual_assets.fetch_scene_images(
        work_dir=work, episode_num=20,
        keywords=["tesla", "model 3", "model y"],  # would leak fashion models
        image_queries=["tesla supercharger", "electric vehicle charging"],
        fallback_cover=cover, api_key="fake-key",
        target_count=2,
    )

    assert queries_seen == ["tesla supercharger", "electric vehicle charging"]


def test_image_queries_dedupes_and_skips_blanks(tmp_path: Path, monkeypatch):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    work = tmp_path / "youtube_tmp"

    queries_seen = []

    def fake_search(query, *, api_key, per_page=3):
        queries_seen.append(query)
        return _fake_pexels_response([f"id_{len(queries_seen)}"])

    monkeypatch.setattr(visual_assets, "_pexels_search", fake_search)
    monkeypatch.setattr(
        visual_assets, "_download_image",
        lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                           dest.write_bytes(b"\xFF\xD8"), dest)[2],
    )

    visual_assets.fetch_scene_images(
        work_dir=work, episode_num=21,
        keywords=[],
        image_queries=["tesla car", "", "  ", "Tesla Car", "tesla supercharger"],
        fallback_cover=cover, api_key="fake-key",
        target_count=10,
    )

    # "Tesla Car" is a case-insensitive dupe of "tesla car"; blanks dropped.
    assert queries_seen == ["tesla car", "tesla supercharger"]


# ---------------------------------------------------------------------------
# image_query_prefix
# ---------------------------------------------------------------------------

def test_select_keywords_applies_prefix():
    """Prefix is prepended to keywords that don't already contain its head word."""
    out = visual_assets._select_keywords(
        ["model 3", "tesla supercharger", "robotaxi", "cybertruck"],
        prefix="tesla ",
    )
    # "tesla supercharger" already contains "tesla" — prefix not duplicated.
    assert "tesla model 3" in out
    assert "tesla supercharger" in out
    assert "tesla robotaxi" in out
    assert "tesla cybertruck" in out
    # No bare "model 3" leaks through (would hit fashion models on Pexels).
    assert "model 3" not in out


def test_select_keywords_no_prefix_keeps_originals():
    out = visual_assets._select_keywords(
        ["space telescope", "rocket launch"],
        prefix="",
    )
    assert out == ["space telescope", "rocket launch"]


def test_select_keywords_prefix_dedupes_after_application():
    """If prefix application would create duplicates, dedupe correctly."""
    out = visual_assets._select_keywords(
        ["car", "tesla car"],
        prefix="tesla ",
    )
    # Both expand to "tesla car" — only one survives.
    assert out.count("tesla car") == 1


# ---------------------------------------------------------------------------
# Pexels safety filter
# ---------------------------------------------------------------------------

def test_photo_is_safe_drops_url_slug_match():
    photo = {
        "id": 8784176,
        "url": "https://www.pexels.com/photo/topless-model-in-panties-8784176/",
        "alt": "",
    }
    assert visual_assets._photo_is_safe(photo, ["topless"]) is False
    assert visual_assets._photo_is_safe(photo, ["model-in"]) is False


def test_photo_is_safe_passes_clean_photos():
    photo = {
        "id": 35736766,
        "url": "https://www.pexels.com/photo/tesla-model-3-charging-at-electric-station-35736766/",
        "alt": "Tesla Model 3 charging",
    }
    skip = ["topless", "model-in", "lingerie"]
    assert visual_assets._photo_is_safe(photo, skip) is True


def test_photo_is_safe_empty_skip_terms_is_permissive():
    photo = {"id": 1, "url": "anything", "alt": ""}
    assert visual_assets._photo_is_safe(photo, []) is True


def test_photo_is_safe_case_insensitive():
    photo = {"id": 1, "url": "https://www.pexels.com/photo/Topless-Model/", "alt": ""}
    assert visual_assets._photo_is_safe(photo, ["topless"]) is False


def test_safety_filter_drops_photos_during_fetch(tmp_path: Path, monkeypatch):
    """End-to-end: bad photos are filtered out, photos_filtered is recorded."""
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    work = tmp_path / "youtube_tmp"

    def fake_search(query, *, api_key, per_page=3):
        # First photo is bad (matches "topless"), second is fine.
        return {
            "photos": [
                {
                    "id": 1,
                    "url": "https://pexels.com/photo/topless-model-1",
                    "alt": "topless model",
                    "photographer": "Bad Photographer",
                    "photographer_url": "https://pexels.com/@bad",
                    "src": {"large2x": "https://example.com/1.jpg"},
                },
                {
                    "id": 2,
                    "url": "https://pexels.com/photo/tesla-model-3-charging-2",
                    "alt": "tesla charging",
                    "photographer": "Good Photographer",
                    "photographer_url": "https://pexels.com/@good",
                    "src": {"large2x": "https://example.com/2.jpg"},
                },
            ],
        }

    monkeypatch.setattr(visual_assets, "_pexels_search", fake_search)
    monkeypatch.setattr(
        visual_assets, "_download_image",
        lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                           dest.write_bytes(b"\xFF\xD8"), dest)[2],
    )

    result = visual_assets.fetch_scene_images(
        work_dir=work, episode_num=30,
        keywords=[],
        image_queries=["tesla car"],
        fallback_cover=cover, api_key="fake-key",
        safe_skip_terms=["topless", "lingerie"],
        target_count=5,
    )

    # Only the clean photo made it through.
    assert len(result) == 1
    assert result.is_fallback is False
    assert result.photos_filtered == 1
    # Manifest persists the count.
    manifest = json.loads(
        (work / "scenes_ep030" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["photos_filtered"] == 1


def test_safety_filter_off_when_skip_terms_empty(tmp_path: Path, monkeypatch):
    """With empty skip_terms, the bad photo passes through unchanged."""
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    work = tmp_path / "youtube_tmp"

    def fake_search(query, *, api_key, per_page=3):
        return {
            "photos": [
                {
                    "id": 1,
                    "url": "https://pexels.com/photo/topless-model-1",
                    "alt": "",
                    "photographer": "X",
                    "photographer_url": "",
                    "src": {"large2x": "https://example.com/1.jpg"},
                },
            ],
        }

    monkeypatch.setattr(visual_assets, "_pexels_search", fake_search)
    monkeypatch.setattr(
        visual_assets, "_download_image",
        lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                           dest.write_bytes(b"\xFF\xD8"), dest)[2],
    )

    result = visual_assets.fetch_scene_images(
        work_dir=work, episode_num=31,
        keywords=[],
        image_queries=["tesla car"],
        fallback_cover=cover, api_key="fake-key",
        safe_skip_terms=[],
        target_count=5,
    )

    assert len(result) == 1
    assert result.photos_filtered == 0


# ---------------------------------------------------------------------------
# Show YAML coverage — every show with youtube.enabled has curated queries
# ---------------------------------------------------------------------------

def test_every_show_yaml_has_image_queries():
    """Every show YAML defines image_queries so the keyword fallback never
    fires in production. Drift from this is the leading regression mode for
    the off-topic-imagery class of bug.
    """
    import yaml as _yaml
    shows_dir = Path(__file__).resolve().parent.parent / "shows"
    # Underscore-prefixed YAMLs (`_defaults.yaml`, `_blocked_sources.yaml`)
    # and shared maps (`pronunciation_map.yaml`) are network-wide
    # configuration, not shows.
    show_files = sorted(
        f for f in shows_dir.glob("*.yaml")
        if not f.name.startswith("_")
        and f.name != "pronunciation_map.yaml"
    )
    assert show_files, f"No show YAMLs found under {shows_dir}"
    for show_file in show_files:
        data = _yaml.safe_load(show_file.read_text(encoding="utf-8")) or {}
        yt = data.get("youtube") or {}
        queries = yt.get("image_queries") or []
        assert isinstance(queries, list) and len(queries) >= 3, (
            f"{show_file.name}: youtube.image_queries must list >=3 curated "
            f"phrases (got {queries!r}). The keyword fallback returned "
            f"off-topic imagery in production — see Tesla Ep456 manifest."
        )
