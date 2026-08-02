"""Drift guards: a b-roll pool must survive a non-public object URL.

SpaceX Ep054 (2026-08-02) rendered with ``broll=0`` despite a healthy
25-clip pool. Every clip failed::

    failed to fetch b-roll ***/nerra-gallery/broll/spacex/….mp4:
        400 Client Error: Bad Request

The URLs were S3 API endpoints
(``https://<acct>.r2.cloudflarestorage.com/<bucket>/<key>``), which
``upload_to_r2`` returns when ``R2_GALLERY_PUBLIC_BASE_URL`` is unset —
they need SigV4 signing, so an unauthenticated GET is answered 400.

The gallery IMAGE path already handled exactly this and recovered on the
same run ("public CDN failed …; R2 fallback OK"). ``select_broll_clips``
had no such ladder: it did one bare GET and treated the failure as "no
clips", which downstream is indistinguishable from "no pool published".
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


def _pool(tmp_path, entries):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "broll.json").write_text(json.dumps({"clips": entries}),
                                         encoding="utf-8")
    return tmp_path


class TestPublicUrlDetection:
    def test_s3_endpoint_is_not_public(self):
        assert not gl.is_public_media_url(
            f"{_ENDPOINT}/nerra-gallery/broll/spacex/a.mp4")

    def test_custom_domain_is_public(self):
        assert gl.is_public_media_url(
            "https://gallery.nerranetwork.com/spacex/a.mp4")

    def test_empty_url_is_treated_as_public(self):
        # Nothing to special-case; the normal path reports the failure.
        assert gl.is_public_media_url("")


class TestObjectKeyResolution:
    def test_prefers_the_pool_entrys_key(self):
        entry = {"url": f"{_ENDPOINT}/nerra-gallery/broll/spacex/a.mp4",
                 "key": "broll/spacex/a.mp4"}
        assert gl._r2_object_key(entry) == "broll/spacex/a.mp4"

    def test_still_prefers_manifest_original_key(self):
        entry = {"original_key": "tesla/2026-07-08/ep535/abc.jpeg",
                 "original_url": "https://gallery.nerranetwork.com/x.jpeg"}
        assert gl._r2_object_key(entry) == "tesla/2026-07-08/ep535/abc.jpeg"

    def test_derives_from_a_public_url_path(self):
        entry = {"original_url":
                 "https://gallery.nerranetwork.com/tesla/ep535/abc.jpeg"}
        assert gl._r2_object_key(entry) == "tesla/ep535/abc.jpeg"

    def test_strips_the_bucket_segment_from_an_endpoint_url(self, monkeypatch):
        """The bucket is passed to the client separately; leaving it in
        the key looks up an object that does not exist."""
        monkeypatch.setattr(
            "engine.gallery_uploader.gallery_config_from_env",
            lambda: type("C", (), {"bucket": "nerra-gallery"})())
        entry = {"url": f"{_ENDPOINT}/nerra-gallery/broll/spacex/a.mp4"}
        assert gl._r2_object_key(entry) == "broll/spacex/a.mp4"

    def test_no_url_and_no_key_is_none(self):
        assert gl._r2_object_key({}) is None


class TestBrollFallback:
    def test_endpoint_urls_skip_the_doomed_public_get(self, tmp_path,
                                                      monkeypatch):
        """25 clips × one guaranteed-400 request is pure waste."""
        d = _pool(tmp_path / "digests", [
            {"url": f"{_ENDPOINT}/nerra-gallery/broll/spacex/a.mp4",
             "key": "broll/spacex/a.mp4"},
        ])
        called = {"get": 0}
        monkeypatch.setattr(gl.requests, "get",
                            lambda *a, **k: called.__setitem__("get", 1))

        def _r2(entry, dest):
            dest.write_bytes(b"video")
            return True

        monkeypatch.setattr(gl, "_download_via_r2", _r2)
        got = gl.select_broll_clips("spacex", digests_dir=d, limit=1,
                                    cache_dir=tmp_path / "cache")
        assert len(got) == 1
        assert called["get"] == 0

    def test_public_failure_falls_back_to_r2(self, tmp_path, monkeypatch):
        d = _pool(tmp_path / "digests", [
            {"url": "https://gallery.nerranetwork.com/broll/a.mp4",
             "key": "broll/spacex/a.mp4"},
        ])

        def _boom(*a, **k):
            raise RuntimeError("403 Forbidden")

        monkeypatch.setattr(gl.requests, "get", _boom)

        def _r2(entry, dest):
            dest.write_bytes(b"video")
            return True

        monkeypatch.setattr(gl, "_download_via_r2", _r2)
        got = gl.select_broll_clips("spacex", digests_dir=d, limit=1,
                                    cache_dir=tmp_path / "cache")
        assert len(got) == 1

    def test_the_ep054_shape_now_yields_clips(self, tmp_path, monkeypatch):
        """The exact regression: a full pool of endpoint URLs."""
        d = _pool(tmp_path / "digests", [
            {"url": f"{_ENDPOINT}/nerra-gallery/broll/spacex/c{i}.mp4",
             "key": f"broll/spacex/c{i}.mp4",
             "label": f"src{i % 4}_Isolated___0{i}m00s"}
            for i in range(25)
        ])
        monkeypatch.setattr(gl.requests, "get", lambda *a, **k: (_ for _ in ()
                                                                ).throw(
            RuntimeError("400 Bad Request")))

        def _r2(entry, dest):
            dest.write_bytes(b"video")
            return True

        monkeypatch.setattr(gl, "_download_via_r2", _r2)
        got = gl.select_broll_clips("spacex", digests_dir=d, limit=3,
                                    cache_dir=tmp_path / "cache",
                                    episode_seed="spacex:ep054")
        assert len(got) == 3

    def test_total_failure_is_announced_not_silent(self, tmp_path,
                                                   monkeypatch, capsys):
        """Empty-because-broken must not look like empty-because-unpublished."""
        d = _pool(tmp_path / "digests", [
            {"url": f"{_ENDPOINT}/x/a.mp4", "key": "broll/spacex/a.mp4"},
        ])
        monkeypatch.setattr(gl.requests, "get", lambda *a, **k: (_ for _ in ()
                                                                ).throw(
            RuntimeError("400")))
        monkeypatch.setattr(gl, "_download_via_r2", lambda e, d_: False)
        got = gl.select_broll_clips("spacex", digests_dir=d, limit=3,
                                    cache_dir=tmp_path / "cache")
        assert got == []
        out = capsys.readouterr().out
        assert "::warning::" in out and "NONE could be fetched" in out

    def test_no_pool_stays_quiet(self, tmp_path, capsys):
        """An unpublished pool is not a failure — no warning."""
        d = _pool(tmp_path / "digests", [])
        assert gl.select_broll_clips("spacex", digests_dir=d, limit=3,
                                     cache_dir=tmp_path / "cache") == []
        assert "::warning::" not in capsys.readouterr().out


class TestCommittedPoolIsRecoverable:
    def test_every_clip_carries_the_key_the_fallback_needs(self):
        pool_path = PROJECT_ROOT / "digests" / "spacex" / "broll.json"
        if not pool_path.exists():
            pytest.skip("spacex pool not published in this checkout")
        clips = json.loads(pool_path.read_text(encoding="utf-8"))["clips"]
        assert clips
        missing = [c.get("url") for c in clips if not c.get("key")]
        assert not missing, f"unrecoverable clips (no key): {missing}"

    def test_pool_builder_warns_on_non_public_urls(self):
        src = (PROJECT_ROOT / "scripts" / "build_broll_pool.py").read_text(
            encoding="utf-8")
        assert "R2_GALLERY_PUBLIC_BASE_URL is unset" in src
