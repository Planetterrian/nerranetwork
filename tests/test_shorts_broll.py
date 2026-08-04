"""Guards for real-footage Shorts + the rotation-stride regression.

Two findings from the August 2026 video review:

**The rotation was dead in production.** ``select_broll_clips`` passes
``limit=len(entries)`` into ``rotate_for_episode`` (so a failed download
can backfill from the rest of the pool), and the per-episode step was
derived from that limit — ``index * len % len == 0``, cancelling the
episode number. Every episode shipped the SAME clips from the day the
pool landed, while the direct unit tests (which pass the slice width as
the limit) stayed green. The fix is an explicit ``stride`` carrying the
consumer's slice width; the tests here go through the PRODUCTION call
path, not the function in isolation.

**Shorts never used the pool.** The b-roll pool fed only the long-form
hybrid; every Short shipped stills even after real launch footage was
published. Shorts now draw 2 pool clips each through the motion-A/B's
proven ``clip_paths`` path, with a per-short seed so Shorts of one
episode differ from each other and from yesterday's.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402

from engine import gallery_library as gl  # noqa: E402

_ENDPOINT = "https://abc123.r2.cloudflarestorage.com"


@pytest.fixture(autouse=True)
def _reset_cdn_state(monkeypatch):
    monkeypatch.setattr(gl, "_prefer_r2_download", False, raising=False)


def _make_pool(tmp_path, n=25):
    d = tmp_path / "digests"
    d.mkdir(parents=True, exist_ok=True)
    clips = [
        {"url": f"{_ENDPOINT}/nerra-gallery/broll/spacex/c{i:02d}.mp4",
         "key": f"broll/spacex/c{i:02d}.mp4",
         "label": f"src{i % 4}_Isolated___{i:02d}m00s"}
        for i in range(n)
    ]
    (d / "broll.json").write_text(json.dumps({"clips": clips}),
                                  encoding="utf-8")
    return d


def _select(digests_dir, cache_root, seed, limit=3):
    """select_broll_clips with downloads faked — the PRODUCTION path."""
    got = gl.select_broll_clips(
        "spacex", digests_dir=digests_dir, limit=limit,
        cache_dir=cache_root / seed.replace(":", "_"),
        episode_seed=seed,
    )
    return tuple(p.name for p in got)


@pytest.fixture()
def _fake_r2(monkeypatch):
    def _r2(entry, dest):
        dest.write_bytes(b"video")
        return True
    monkeypatch.setattr(gl, "_download_via_r2", _r2)


class TestRotationAliveInProduction:
    """These tests exist because the direct-call tests lied."""

    def test_consecutive_episodes_get_different_clips(self, tmp_path,
                                                      _fake_r2):
        d = _make_pool(tmp_path)
        slices = [
            _select(d, tmp_path, f"spacex:ep{n:03d}") for n in (55, 56, 57, 58)
        ]
        assert len(set(slices)) == len(slices), slices
        # And back-to-back episodes share nothing.
        for a, b in zip(slices, slices[1:]):
            assert not (set(a) & set(b)), (a, b)

    def test_the_dead_rotation_shape_is_pinned(self):
        """Reproduce the bug arithmetic so a revert fails loudly: with
        the step equal to the pool size, every episode collapses to the
        same offset."""
        pool = [{"url": f"u{i}"} for i in range(25)]
        same = {
            tuple(c["url"] for c in gl.rotate_for_episode(
                pool, f"spacex:ep{n:03d}", len(pool)))[:3]
            for n in (55, 56, 57)
        }
        # Without an explicit stride the full-pool call is STILL the
        # degenerate one — the fix is that select_broll_clips passes
        # stride, not that the arithmetic changed underneath everyone.
        assert len(same) == 1
        strided = {
            tuple(c["url"] for c in gl.rotate_for_episode(
                pool, f"spacex:ep{n:03d}", len(pool), stride=3))[:3]
            for n in (55, 56, 57)
        }
        assert len(strided) == 3

    def test_direct_slice_width_callers_are_unchanged(self):
        pool = [{"url": f"u{i}"} for i in range(12)]
        a = gl.rotate_for_episode(pool, "spacex:ep010", 3)
        b = gl.rotate_for_episode(pool, "spacex:ep010", 3, stride=3)
        assert a == b

    def test_download_failure_still_backfills_from_the_pool(self, tmp_path,
                                                            monkeypatch):
        """The reason limit=len(entries) exists at all — keep it working."""
        d = _make_pool(tmp_path, n=6)
        calls = {"n": 0}

        def _flaky(entry, dest):
            calls["n"] += 1
            if calls["n"] == 1:  # first clip of the slice fails
                return False
            dest.write_bytes(b"video")
            return True

        monkeypatch.setattr(gl, "_download_via_r2", _flaky)
        got = gl.select_broll_clips(
            "spacex", digests_dir=d, limit=3,
            cache_dir=tmp_path / "cache", episode_seed="spacex:ep055")
        assert len(got) == 3


class TestShortsDrawFromThePool:
    def test_each_short_gets_a_distinct_clip_pair(self, tmp_path, _fake_r2):
        """The run_show seed shape: episode*4 + short index."""
        d = _make_pool(tmp_path)
        ep = 55
        pairs = [
            _select(d, tmp_path, f"spacex-short:e{ep * 4 + i:05d}", limit=2)
            for i in range(3)
        ]
        assert len(set(pairs)) == 3, pairs

    def test_same_short_differs_across_episodes(self, tmp_path, _fake_r2):
        d = _make_pool(tmp_path)
        short0 = [
            _select(d, tmp_path, f"spacex-short:e{ep * 4:05d}", limit=2)
            for ep in (55, 56, 57)
        ]
        assert len(set(short0)) == 3, short0

    def test_run_show_wiring(self):
        src = (PROJECT_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "episode_num * 4 + short_idx" in src
        assert "clip_paths=(_variant.clip_paths\n" \
               "                                    or _short_broll or None)" \
               in src
        # The A/B guard: no pool clips while an experiment is enrolled.
        assert "not _ab_on" in src
        assert '"shorts_broll", True' in src.replace("'", '"')

    def test_config_default_is_on(self):
        import logging
        logging.disable(logging.CRITICAL)
        try:
            from engine.config import load_config
            cfg = load_config("shows/spacex.yaml")
            assert getattr(cfg.youtube, "shorts_broll", None) is True
        finally:
            logging.disable(logging.NOTSET)

    def test_metrics_record_the_per_short_counts(self):
        src = (PROJECT_ROOT / "engine" / "pipeline.py").read_text(
            encoding="utf-8")
        assert "shorts_broll_counts" in src


class TestPoolBuilderWorkflow:
    def _wf(self):
        import yaml
        path = (PROJECT_ROOT / ".github" / "workflows"
                / "build-broll-pool.yml")
        return path.read_text(encoding="utf-8"), yaml.safe_load(
            path.read_text(encoding="utf-8"))

    def test_dispatch_inputs_cover_both_sources(self):
        text, data = self._wf()
        inputs = data[True]["workflow_dispatch"]["inputs"] \
            if True in data else data["on"]["workflow_dispatch"]["inputs"]
        assert set(inputs) >= {"show", "source", "query", "max_clips"}
        assert "pexels" in text and "nasa" in text

    def test_has_ffmpeg_and_r2_credentials(self):
        text, _ = self._wf()
        assert "system-packages: 'ffmpeg'" in text
        for secret in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID",
                       "R2_SECRET_ACCESS_KEY", "R2_GALLERY_BUCKET",
                       "R2_GALLERY_PUBLIC_BASE_URL", "PEXELS_API_KEY"):
            assert secret in text, f"missing {secret}"

    def test_commits_only_the_pool_index(self):
        """Media in git is landmine #1 — the workflow must add only the
        JSON index, never clip files."""
        text, _ = self._wf()
        assert 'add-paths: "digests/*/broll.json"' in text
        assert ".mp4" not in text.split("safe-commit-push")[1]

    def test_empty_fetch_fails_loudly(self):
        text, _ = self._wf()
        assert "no clips survived" in text
