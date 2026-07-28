"""Drift guards for P1-3 (feeds/CDN that fail every run) and P1-4 (false-green).

Three degradations that had become background noise:

  * Reddit feeds 429 from cloud egress. The descriptive-UA fix (July 21)
    helped, but the retry predicate never covered 429 — a throttled feed
    was dropped on the first refusal. A live probe on 2026-07-28 returned
    200 / 200 / 429 for r/LocalLLaMA / r/SpaceXLounge / r/space in the
    same second, so these are throttles to back off from, not blocks.
  * The gallery CDN 403s and every render silently pays the authenticated
    R2 fallback — visible only as INFO lines, so a bucket that stopped
    being public looked like a healthy pipeline.
  * The newsletter preflight printed "validated successfully" and the
    send then failed at the end of every single run, because a valid API
    key is not the same as an account that is allowed to send.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine.fetcher as fetcher  # noqa: E402
import engine.gallery_library as gallery_library  # noqa: E402
import engine.newsletter as newsletter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestThrottleRetry:
    def _response(self, status):
        resp = Mock()
        resp.status_code = status
        resp.content = b"<rss/>"
        resp.raise_for_status = Mock()
        return resp

    def test_429_is_retried_and_can_succeed(self):
        calls = []

        def _get(url, **kwargs):
            calls.append(url)
            return self._response(429 if len(calls) < 3 else 200)

        with patch.object(fetcher.requests, "get", side_effect=_get):
            resp = fetcher._fetch_url_with_retry("https://www.reddit.com/r/space/.rss")

        assert resp.status_code == 200
        assert len(calls) == 3, "throttled feed must be retried, not dropped"

    def test_503_is_retried(self):
        calls = []

        def _get(url, **kwargs):
            calls.append(url)
            return self._response(503 if len(calls) < 2 else 200)

        with patch.object(fetcher.requests, "get", side_effect=_get):
            resp = fetcher._fetch_url_with_retry("https://example.com/feed.rss")
        assert resp.status_code == 200
        assert len(calls) == 2

    def test_persistent_throttle_finally_raises(self):
        with patch.object(fetcher.requests, "get",
                          side_effect=lambda url, **kw: self._response(429)):
            with pytest.raises(fetcher.ThrottledError):
                fetcher._fetch_url_with_retry("https://www.reddit.com/r/space/.rss")

    def test_404_is_not_retried(self):
        """Retrying a dead feed is the waste this is meant to remove."""
        calls = []

        def _get(url, **kwargs):
            calls.append(url)
            resp = Mock()
            resp.status_code = 404
            resp.raise_for_status = Mock(
                side_effect=fetcher.requests.exceptions.HTTPError("404")
            )
            return resp

        with patch.object(fetcher.requests, "get", side_effect=_get):
            with pytest.raises(fetcher.requests.exceptions.HTTPError):
                fetcher._fetch_url_with_retry("https://example.com/gone.rss")
        assert len(calls) == 1

    def test_success_is_a_single_call(self):
        calls = []

        def _get(url, **kwargs):
            calls.append(url)
            return self._response(200)

        with patch.object(fetcher.requests, "get", side_effect=_get):
            fetcher._fetch_url_with_retry("https://example.com/feed.rss")
        assert len(calls) == 1

    def test_reddit_keeps_its_descriptive_user_agent(self):
        """Reddit's guidelines require it; a browser UA draws the 429s."""
        headers = fetcher._headers_for_url("https://www.reddit.com/r/space/.rss")
        assert "nerranetwork-rss" in headers["User-Agent"]
        other = fetcher._headers_for_url("https://www.nasaspaceflight.com/feed/")
        assert "nerranetwork-rss" not in other["User-Agent"]


class TestGalleryCdnVisibility:
    @pytest.fixture(autouse=True)
    def _reset_breaker(self):
        gallery_library._prefer_r2_download = False
        yield
        gallery_library._prefer_r2_download = False

    def _forbidden(self, *args, **kwargs):
        err = gallery_library.requests.exceptions.HTTPError("403 Forbidden")
        err.response = Mock(status_code=403)
        raise err

    def _entry(self, name="b"):
        return {
            "original_url": f"https://gallery.nerranetwork.com/a/{name}.jpeg",
            "image_id": name,
            "original_key": f"a/{name}.jpeg",
        }

    def test_first_403_emits_a_loud_annotation(self, tmp_path, capsys):
        with patch.object(gallery_library.requests, "get", side_effect=self._forbidden), \
             patch.object(gallery_library, "_download_via_r2", return_value=False):
            result = gallery_library._download_entry(self._entry(), tmp_path)

        assert result is None
        out = capsys.readouterr().out
        assert "::warning::gallery CDN rejected a public read" in out
        assert "403" in out
        # And the breaker flipped, so the rest of the run skips the CDN.
        assert gallery_library._prefer_r2_download is True

    def test_annotation_fires_once_not_per_image(self, tmp_path, capsys):
        """Up to 16 library fetches per render — one warning, not sixteen."""
        with patch.object(gallery_library.requests, "get", side_effect=self._forbidden), \
             patch.object(gallery_library, "_download_via_r2", return_value=False):
            for i in range(5):
                gallery_library._download_entry(self._entry(f"img{i}"), tmp_path)

        out = capsys.readouterr().out
        assert out.count("::warning::gallery CDN rejected a public read") == 1

    def test_healthy_cdn_stays_silent(self, tmp_path, capsys):
        ok = Mock(content=b"jpegbytes", raise_for_status=Mock())
        with patch.object(gallery_library.requests, "get", return_value=ok):
            result = gallery_library._download_entry(self._entry(), tmp_path)

        assert result is not None
        assert "::warning::" not in capsys.readouterr().out
        assert gallery_library._prefer_r2_download is False


class TestNewsletterSendingBlock:
    @pytest.fixture(autouse=True)
    def _isolate_marker(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            newsletter, "_SENDING_BLOCKED_MARKER", tmp_path / "blocked.json"
        )

    @pytest.mark.parametrize(
        "detail",
        [
            '{"code":"email_invalid","detail":"configure a custom sending domain"}',
            "EMAIL_INVALID: you must configure a custom sending domain first",
        ],
    )
    def test_sending_domain_error_is_recognised(self, detail):
        assert newsletter._is_sending_domain_error(detail) is True

    @pytest.mark.parametrize(
        "detail",
        [
            '{"code":"tag_invalid","detail":"unknown tag"}',
            "500 Internal Server Error",
            "",
        ],
    )
    def test_other_errors_are_not_swallowed(self, detail):
        assert newsletter._is_sending_domain_error(detail) is False

    def test_block_is_remembered_then_reported(self):
        assert newsletter.sending_block_reason() is None
        newsletter._remember_sending_block("email_invalid: sending domain")
        reason = newsletter.sending_block_reason()
        assert reason and "sending domain" in reason

    def test_block_expires_so_a_fix_is_picked_up_automatically(self):
        import datetime
        newsletter._remember_sending_block("email_invalid: sending domain")
        stale = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=newsletter._SENDING_BLOCK_TTL_DAYS + 1
        )
        newsletter._SENDING_BLOCKED_MARKER.write_text(
            json.dumps({"blocked_at": stale.isoformat(), "detail": "x"}),
            encoding="utf-8",
        )
        assert newsletter.sending_block_reason() is None

    def test_successful_send_clears_the_block(self):
        newsletter._remember_sending_block("email_invalid: sending domain")
        assert newsletter.sending_block_reason() is not None
        newsletter.clear_sending_block()
        assert newsletter.sending_block_reason() is None

    def test_corrupt_marker_is_not_fatal(self):
        newsletter._SENDING_BLOCKED_MARKER.write_text("{not json", encoding="utf-8")
        assert newsletter.sending_block_reason() is None

    def test_send_skips_early_when_blocked(self):
        """Skip before composing, not after — the point is to stop the waste."""
        source = (REPO_ROOT / "engine" / "newsletter.py").read_text(encoding="utf-8")
        body = source.split("def send_show_newsletter(")[1]
        assert "sending_block_reason()" in body.split("_can_send_now(")[0], \
            "the block check must run before the send guards and composition"

    def test_preflight_consults_the_block(self):
        source = (REPO_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "sending_block_reason" in source
