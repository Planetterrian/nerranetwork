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

    def test_committed_manifest_is_valid_json_without_conflict_markers(self):
        """The committed manifest must always parse.

        Jul 16 2026: a `git pull --rebase --autostash` conflict in the
        nightly job committed `<<<<<<<` markers into the manifest on main —
        every consumer (library blend, RU dubs, gallery page) silently
        no-opped. This guard makes that failure loud in CI.
        """
        if not gl.DEFAULT_MANIFEST.exists():
            return  # unconfigured checkout — nothing to validate
        text = gl.DEFAULT_MANIFEST.read_text(encoding="utf-8")
        assert "<<<<<<< " not in text, (
            "gallery-manifest.json contains unresolved git conflict markers")
        data = json.loads(text)  # raises on corrupt JSON
        assert isinstance(data, dict) and "images" in data

    def test_corrupt_existing_manifest_warns_loudly(self, tmp_path, caplog):
        """An EXISTING-but-unparseable manifest is a WARNING, not info —
        it silently zeroes scene_library_count on every episode."""
        import logging
        p = tmp_path / "broken.json"
        p.write_text('{\n<<<<<<< Updated upstream\n "a": 1\n}', encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="engine.gallery_library"):
            assert gl.load_manifest(p) == {}
        assert any("UNREADABLE" in r.message for r in caplog.records)

    def test_missing_manifest_stays_quiet(self, tmp_path, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger="engine.gallery_library"):
            assert gl.load_manifest(tmp_path / "absent.json") == {}
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


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
        # Kill R2 fallback so a public failure stays a soft skip.
        monkeypatch.setattr(gl, "_download_via_r2", lambda *a, **k: False)
        got = gl.select_library_scenes(
            "tesla", aspect="16:9", limit=2,
            manifest=_manifest(), cache_dir=tmp_path)
        # Best candidate failed → next two backfill, still limit results.
        assert _stems(got) == ["bbb222", "aaa111"]

    def test_circuit_breaker_stops_after_consecutive_failures(
            self, tmp_path, monkeypatch):
        """Ep537 class: gallery CDN 403s every URL. Without a breaker we
        walked 150+ candidates; with it we abort after N consecutive
        misses and return whatever we have (usually empty)."""
        big = {"images": [
            _entry(f"img{i:03d}", episode=f"ep{i}",
                   date=f"2026-06-{(i % 28) + 1:02d}",
                   prompt=f"scene {i}")
            for i in range(40)
        ]}
        calls = _stub_requests(monkeypatch, fail_urls={
            e["original_url"] for e in big["images"]
        })
        monkeypatch.setattr(gl, "_download_via_r2", lambda *a, **k: False)
        got = gl.select_library_scenes(
            "tesla", aspect="16:9", limit=8,
            manifest=big, cache_dir=tmp_path)
        assert got == []
        assert len(calls) == gl._MAX_CONSECUTIVE_DOWNLOAD_FAILURES

    def test_r2_fallback_used_when_public_cdn_fails(
            self, tmp_path, monkeypatch):
        m = _manifest()
        for e in m["images"]:
            e["original_key"] = f"tesla/{e['image_id']}.jpeg"
        fail_all = {e["original_url"] for e in m["images"] if e.get("original_url")}
        _stub_requests(monkeypatch, fail_urls=fail_all)

        def _fake_r2(entry, dest):
            dest.write_bytes(b"r2:" + entry["image_id"].encode())
            return True

        monkeypatch.setattr(gl, "_download_via_r2", _fake_r2)
        got = gl.select_library_scenes(
            "tesla", aspect="16:9", limit=2,
            manifest=m, cache_dir=tmp_path)
        assert len(got) == 2
        assert got[0].read_bytes().startswith(b"r2:")

    def test_prefer_r2_after_first_cdn_403(self, tmp_path, monkeypatch):
        """After one public 403, later downloads skip the CDN entirely."""
        monkeypatch.setattr(gl, "_prefer_r2_download", False)
        m = {"images": [
            _entry("aaa111", episode="ep1", date="2026-07-01",
                   prompt="cybercab"),
            _entry("bbb222", episode="ep2", date="2026-07-02",
                   prompt="battery"),
        ]}
        for e in m["images"]:
            e["original_key"] = f"tesla/{e['image_id']}.jpeg"

        class _Forbidden(Exception):
            def __init__(self):
                self.response = SimpleNamespace(status_code=403)

        calls = {"public": 0, "r2": 0}

        def get(url, timeout=None):
            calls["public"] += 1
            raise _Forbidden()

        def _fake_r2(entry, dest):
            calls["r2"] += 1
            dest.write_bytes(b"r2:" + entry["image_id"].encode())
            return True

        monkeypatch.setattr(gl, "requests", SimpleNamespace(get=get))
        monkeypatch.setattr(gl, "_download_via_r2", _fake_r2)
        got = gl.select_library_scenes(
            "tesla", aspect="16:9", limit=2,
            manifest=m, cache_dir=tmp_path)
        assert len(got) == 2
        # First image: 1 public attempt (403) + R2. Second: R2 only.
        assert calls["public"] == 1
        assert calls["r2"] == 2

    def test_never_raises_on_garbage_manifest(self, tmp_path):
        assert gl.select_library_scenes(
            "tesla", aspect="16:9", manifest={"images": "not-a-list"},
            cache_dir=tmp_path) == []

    def test_zero_download_blend_warns_loudly_with_first_reason(
            self, tmp_path, monkeypatch, caplog):
        """Selected N candidates, downloaded 0 → ONE loud warning naming the
        first concrete failure — the silent-no-op shape that hid the
        CDN-403 defect for a week (scene_library_count: 0, Jul 2026)."""
        import logging
        m = _manifest()  # 4 tesla 16:9 candidates — below the breaker of 5
        fail_all = {e["original_url"] for e in m["images"]
                    if e.get("original_url")}
        _stub_requests(monkeypatch, fail_urls=fail_all)
        monkeypatch.setattr(gl, "_prefer_r2_download", False)
        monkeypatch.setattr(gl, "_download_via_r2", lambda *a, **k: False)
        monkeypatch.setattr(gl, "_r2_configured", lambda: False)
        with caplog.at_level(logging.WARNING, logger="engine.gallery_library"):
            got = gl.select_library_scenes(
                "tesla", aspect="16:9", limit=8,
                manifest=m, cache_dir=tmp_path)
        assert got == []
        degraded = [r for r in caplog.records if "BLEND DEGRADED" in r.message]
        assert len(degraded) == 1
        msg = degraded[0].message
        assert "downloaded 0" in msg
        assert "stub network failure" in msg          # the first reason
        assert "credentials unset" in msg             # R2 state named

    def test_partial_download_does_not_warn_degraded(
            self, tmp_path, monkeypatch, caplog):
        import logging
        m = _manifest()
        first_fail = next(e["original_url"] for e in m["images"]
                          if e.get("original_url"))
        _stub_requests(monkeypatch, fail_urls={first_fail})
        monkeypatch.setattr(gl, "_prefer_r2_download", False)
        monkeypatch.setattr(gl, "_download_via_r2", lambda *a, **k: False)
        monkeypatch.setattr(gl, "_r2_configured", lambda: False)
        with caplog.at_level(logging.WARNING, logger="engine.gallery_library"):
            got = gl.select_library_scenes(
                "tesla", aspect="16:9", limit=8,
                manifest=m, cache_dir=tmp_path)
        assert got  # at least one scene shipped
        assert not [r for r in caplog.records
                    if "BLEND DEGRADED" in r.message]


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
