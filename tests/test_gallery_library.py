"""Drift guards for engine.gallery_library (render-time gallery reuse).

All network access is stubbed (a fake ``requests`` module injected on the
module) — these tests pin the pure selection contract: filtering, the
deterministic score-then-recency ordering, cache reuse, the best-effort
skip-on-failure download path, the b-roll pool reader, and the
Path → prompt/caption context map the scene scheduler consumes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine import gallery_library as gl  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / stubs
# ---------------------------------------------------------------------------


def _entry(image_id, *, show="tesla", episode="ep520", date="2026-06-24",
           use="segment_card", prompt="", caption="", tags=(), url=None):
    return {
        "image_id": image_id,
        "show_slug": show,
        "episode_id": episode,
        "episode_date": date,
        "intended_use": use,
        "prompt": prompt,
        "caption": caption,
        "tags": list(tags),
        "original_url": (url if url is not None
                         else f"https://gallery.test/{show}/{image_id}.jpeg"),
        "episode_title": "",
    }


def _manifest():
    return {"images": [
        _entry("aaa111", episode="ep520", date="2026-06-24",
               prompt="Cybercab factory robots assembling vehicles",
               caption="Cybercab line"),
        _entry("bbb222", episode="ep521", date="2026-06-25",
               prompt="battery pack assembly closeup"),
        _entry("ccc333", episode="ep522", date="2026-06-26",
               prompt="solar roof installation crew"),
        _entry("ddd444", episode="ep522", date="2026-06-26", use="social",
               prompt="vertical cybercab teaser"),
        _entry("eee555", show="spacex", episode="ep012", date="2026-06-26",
               prompt="rocket on the pad"),
        # No original_url → never a candidate.
        {**_entry("fff000", episode="ep519", date="2026-06-23"),
         "original_url": ""},
        _entry("ggg777", episode="ep400", date="2026-02-01",
               prompt="old winter delivery event"),
    ]}


class _FakeResp:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


def _stub_requests(monkeypatch, fail_urls=()):
    """Inject a fake requests module; returns the list of fetched URLs."""
    calls = []

    def get(url, timeout=None):
        assert timeout, "downloads must carry a timeout"
        calls.append(url)
        if url in fail_urls:
            raise RuntimeError("stub network failure")
        return _FakeResp(b"bytes:" + url.encode())

    monkeypatch.setattr(gl, "requests", SimpleNamespace(get=get))
    return calls


def _stems(paths):
    return [p.stem for p in paths]


# ---------------------------------------------------------------------------
# load_manifest
# ---------------------------------------------------------------------------


class TestLoadManifest:
    def test_missing_file_is_empty(self, tmp_path):
        assert gl.load_manifest(tmp_path / "nope.json") == {}

    def test_corrupt_file_is_empty(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        assert gl.load_manifest(p) == {}

    def test_non_dict_json_is_empty(self, tmp_path):
        p = tmp_path / "list.json"
        p.write_text("[1, 2]", encoding="utf-8")
        assert gl.load_manifest(p) == {}

    def test_default_path_is_committed_manifest(self):
        assert gl.DEFAULT_MANIFEST.name == "gallery-manifest.json"


# ---------------------------------------------------------------------------
# select_library_scenes
# ---------------------------------------------------------------------------


class TestSelection:
    def test_filters_show_and_aspect(self, tmp_path, monkeypatch):
        _stub_requests(monkeypatch)
        got = gl.select_library_scenes(
            "tesla", aspect="16:9", manifest=_manifest(), cache_dir=tmp_path)
        # No social (ddd444), no spacex (eee555), no url-less (fff000).
        assert set(_stems(got)) == {"aaa111", "bbb222", "ccc333", "ggg777"}

        got = gl.select_library_scenes(
            "tesla", aspect="9:16", manifest=_manifest(), cache_dir=tmp_path)
        assert _stems(got) == ["ddd444"]

    def test_unknown_aspect_is_empty(self, tmp_path):
        assert gl.select_library_scenes(
            "tesla", aspect="4:3", manifest=_manifest(),
            cache_dir=tmp_path) == []

    def test_excludes_current_episode(self, tmp_path, monkeypatch):
        _stub_requests(monkeypatch)
        got = gl.select_library_scenes(
            "tesla", aspect="16:9", exclude_episode_id="ep522",
            manifest=_manifest(), cache_dir=tmp_path)
        assert "ccc333" not in _stems(got)

    def test_date_window(self, tmp_path, monkeypatch):
        _stub_requests(monkeypatch)
        got = gl.select_library_scenes(
            "tesla", aspect="16:9", manifest=_manifest(), cache_dir=tmp_path,
            min_episode_date="2026-06-25", max_episode_date="2026-06-26")
        assert set(_stems(got)) == {"bbb222", "ccc333"}

    def test_recency_order_without_context(self, tmp_path, monkeypatch):
        _stub_requests(monkeypatch)
        got = gl.select_library_scenes(
            "tesla", aspect="16:9", context_text="",
            manifest=_manifest(), cache_dir=tmp_path)
        assert _stems(got) == ["ccc333", "bbb222", "aaa111", "ggg777"]

    def test_context_overlap_outranks_recency(self, tmp_path, monkeypatch):
        _stub_requests(monkeypatch)
        got = gl.select_library_scenes(
            "tesla", aspect="16:9",
            context_text="Cybercab robots hit the factory floor",
            manifest=_manifest(), cache_dir=tmp_path)
        # aaa111 is the OLDEST candidate but matches 3 context tokens.
        assert _stems(got)[0] == "aaa111"

    def test_deterministic_across_manifest_order(self, tmp_path, monkeypatch):
        _stub_requests(monkeypatch)
        m1, m2 = _manifest(), _manifest()
        m2["images"] = list(reversed(m2["images"]))
        kw = dict(aspect="16:9", context_text="battery assembly news",
                  cache_dir=tmp_path)
        assert (_stems(gl.select_library_scenes("tesla", manifest=m1, **kw))
                == _stems(gl.select_library_scenes("tesla", manifest=m2, **kw)))

    def test_limit_applies_best_first(self, tmp_path, monkeypatch):
        _stub_requests(monkeypatch)
        got = gl.select_library_scenes(
            "tesla", aspect="16:9", limit=2,
            manifest=_manifest(), cache_dir=tmp_path)
        assert _stems(got) == ["ccc333", "bbb222"]

    def test_cache_reuse_skips_downloads(self, tmp_path, monkeypatch):
        calls = _stub_requests(monkeypatch)
        gl.select_library_scenes(
            "tesla", aspect="16:9", manifest=_manifest(), cache_dir=tmp_path)
        first = len(calls)
        assert first == 4
        got = gl.select_library_scenes(
            "tesla", aspect="16:9", manifest=_manifest(), cache_dir=tmp_path)
        assert len(calls) == first  # warm cache — zero new fetches
        assert all(p.exists() and p.read_bytes() for p in got)

    def test_failed_download_skipped_and_backfilled(self, tmp_path, monkeypatch):
        fail = "https://gallery.test/tesla/ccc333.jpeg"
        _stub_requests(monkeypatch, fail_urls={fail})
        got = gl.select_library_scenes(
            "tesla", aspect="16:9", limit=2,
            manifest=_manifest(), cache_dir=tmp_path)
        # Best candidate failed → next two backfill, still limit results.
        assert _stems(got) == ["bbb222", "aaa111"]

    def test_never_raises_on_garbage_manifest(self, tmp_path):
        assert gl.select_library_scenes(
            "tesla", aspect="16:9", manifest={"images": "not-a-list"},
            cache_dir=tmp_path) == []


# ---------------------------------------------------------------------------
# collect_week_scenes
# ---------------------------------------------------------------------------


class TestWeekScenes:
    def test_window_and_recency_order(self, tmp_path, monkeypatch):
        _stub_requests(monkeypatch)
        got = gl.collect_week_scenes(
            "tesla", aspect="16:9", end_date="2026-06-26", days=3,
            manifest=_manifest(), cache_dir=tmp_path)
        # 06-24..06-26 window: ggg777 (Feb) excluded; newest first.
        assert _stems(got) == ["ccc333", "bbb222", "aaa111"]

    def test_exclude_current_episode(self, tmp_path, monkeypatch):
        _stub_requests(monkeypatch)
        got = gl.collect_week_scenes(
            "tesla", aspect="16:9", end_date="2026-06-26", days=7,
            exclude_episode_id="ep522",
            manifest=_manifest(), cache_dir=tmp_path)
        assert "ccc333" not in _stems(got)

    def test_bad_end_date_is_empty(self, tmp_path):
        assert gl.collect_week_scenes(
            "tesla", aspect="16:9", end_date="soonish",
            manifest=_manifest(), cache_dir=tmp_path) == []


# ---------------------------------------------------------------------------
# scene_context_map
# ---------------------------------------------------------------------------


class TestContextMap:
    def test_maps_paths_to_prompt_and_caption(self, tmp_path, monkeypatch):
        _stub_requests(monkeypatch)
        m = _manifest()
        got = gl.select_library_scenes(
            "tesla", aspect="16:9", limit=1, manifest=m, cache_dir=tmp_path)
        ctx = gl.scene_context_map(m, got)
        assert ctx[got[0]] == "solar roof installation crew"

    def test_caption_joined_after_prompt(self, tmp_path, monkeypatch):
        _stub_requests(monkeypatch)
        m = _manifest()
        got = gl.select_library_scenes(
            "tesla", aspect="16:9", context_text="cybercab robots factory",
            limit=1, manifest=m, cache_dir=tmp_path)
        text = gl.scene_context_map(m, got)[got[0]]
        assert "Cybercab factory robots" in text
        assert text.endswith("Cybercab line")

    def test_manifest_stem_lookup_survives_cold_registry(self, tmp_path,
                                                         monkeypatch):
        # A warm on-disk cache from an EARLIER process: registry empty, but
        # files are named by image_id so the manifest lookup still resolves.
        monkeypatch.setattr(gl, "_PATH_REGISTRY", {})
        p = tmp_path / "bbb222.jpeg"
        p.write_bytes(b"cached")
        ctx = gl.scene_context_map(_manifest(), [p])
        assert ctx[p] == "battery pack assembly closeup"

    def test_unknown_path_maps_to_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gl, "_PATH_REGISTRY", {})
        p = tmp_path / "zzz999.jpeg"
        assert gl.scene_context_map(_manifest(), [p])[p] == ""


# ---------------------------------------------------------------------------
# b-roll pool
# ---------------------------------------------------------------------------


class TestBroll:
    def _pool(self, tmp_path, clips):
        d = tmp_path / "digests_show"
        d.mkdir()
        (d / "broll.json").write_text(
            json.dumps({"show_slug": "tesla", "clips": clips}),
            encoding="utf-8")
        return d

    def _clips(self, n=3):
        return [{"url": f"https://gallery.test/broll/tesla/clip{i}.mp4",
                 "duration_s": 5.0 + i, "label": f"clip {i}"}
                for i in range(n)]

    def test_missing_pool_is_empty(self, tmp_path):
        assert gl.select_broll_clips(
            "tesla", digests_dir=tmp_path, cache_dir=tmp_path) == []

    def test_downloads_in_stable_order_up_to_limit(self, tmp_path, monkeypatch):
        calls = _stub_requests(monkeypatch)
        d = self._pool(tmp_path, self._clips(3))
        cache = tmp_path / "cache"
        got = gl.select_broll_clips("tesla", digests_dir=d, limit=2,
                                    cache_dir=cache)
        assert [p.name for p in got] == ["clip0.mp4", "clip1.mp4"]
        assert len(calls) == 2
        # Cache reuse: second call fetches nothing new.
        again = gl.select_broll_clips("tesla", digests_dir=d, limit=2,
                                      cache_dir=cache)
        assert again == got and len(calls) == 2

    def test_failed_clip_skipped(self, tmp_path, monkeypatch):
        _stub_requests(
            monkeypatch,
            fail_urls={"https://gallery.test/broll/tesla/clip0.mp4"})
        d = self._pool(tmp_path, self._clips(3))
        got = gl.select_broll_clips("tesla", digests_dir=d, limit=2,
                                    cache_dir=tmp_path / "cache")
        assert [p.name for p in got] == ["clip1.mp4", "clip2.mp4"]

    def test_bare_list_form_accepted(self, tmp_path, monkeypatch):
        _stub_requests(monkeypatch)
        d = tmp_path / "digests_show"
        d.mkdir()
        (d / "broll.json").write_text(json.dumps(self._clips(1)),
                                      encoding="utf-8")
        got = gl.select_broll_clips("tesla", digests_dir=d,
                                    cache_dir=tmp_path / "cache")
        assert [p.name for p in got] == ["clip0.mp4"]

    def test_corrupt_pool_is_empty(self, tmp_path):
        d = tmp_path / "digests_show"
        d.mkdir()
        (d / "broll.json").write_text("{oops", encoding="utf-8")
        assert gl.select_broll_clips("tesla", digests_dir=d,
                                     cache_dir=tmp_path / "cache") == []
