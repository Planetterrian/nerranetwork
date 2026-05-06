"""Tests for engine.publisher.notify_directories — the directory
ping fan-out that runs after every RSS feed update.

Lives in its own file (separate from test_publisher.py) because the
test_publisher.py module-level ``importorskip("feedgen")`` skips the
whole file in environments without ``feedgen`` installed —
``notify_directories`` itself doesn't depend on feedgen and is
worth covering everywhere.
"""

from __future__ import annotations

import pytest


class TestNotifyDirectoriesPodcastIndexRetired:
    """Operator caught (TST Ep465 production log, May 6 2026) the
    ``api.podcastindex.org/api/1.0/hub/pubnotify`` endpoint returning
    HTTP 403 on every TST run. Podcast Index had retired direct
    pubnotify in favour of subscribing to the WebSub hub. The
    PubSubHubbub step still runs, so Podcast Index keeps picking up
    the feed via WebSub. The direct call was removed to silence the
    warning. This test pins that the function no longer hits that
    URL — re-introducing the call would resurrect the noise.
    """

    def test_does_not_call_deprecated_podcast_index_endpoint(
        self, monkeypatch,
    ):
        from engine import publisher

        urls_called: list = []

        def _fake_post(url, *args, **kwargs):
            urls_called.append(url)

            class _R:
                status_code = 204  # WebSub success
            return _R()

        def _fake_get(url, *args, **kwargs):
            urls_called.append(url)

            class _R:
                status_code = 200
            return _R()

        import requests as _requests
        monkeypatch.setattr(_requests, "post", _fake_post)
        monkeypatch.setattr(_requests, "get", _fake_get)

        # Ping-O-Matic is xmlrpc — make it a noop so the test stays
        # fully offline.
        class _RpcServer:
            class weblogUpdates:
                @staticmethod
                def ping(*_a, **_kw):
                    return {"flerror": False}

        import xmlrpc.client as _xmlrpc
        monkeypatch.setattr(
            _xmlrpc, "ServerProxy", lambda *_a, **_kw: _RpcServer(),
        )

        result = publisher.notify_directories(
            "https://nerranetwork.com/podcast.rss", show_name="Test",
        )

        # No HTTP call to the retired endpoint.
        assert not any(
            "podcastindex.org/api/1.0/hub/pubnotify" in u
            for u in urls_called
        ), (
            f"notify_directories should not hit the retired Podcast "
            f"Index endpoint anymore. Saw: {urls_called}"
        )
        # And the result still records that Podcast Index is being
        # served (via the WebSub path).
        assert result.get("podcast_index") == "via_websub"

    def test_pubsubhubbub_still_called(self, monkeypatch):
        """Sanity: the PubSubHubbub WebSub call is what actually
        notifies Podcast Index now, so it must still happen."""
        from engine import publisher

        post_calls: list = []

        def _fake_post(url, *args, **kwargs):
            post_calls.append(url)

            class _R:
                status_code = 204
            return _R()

        import requests as _requests
        monkeypatch.setattr(_requests, "post", _fake_post)
        monkeypatch.setattr(
            _requests, "get",
            lambda *_a, **_kw: type("R", (), {"status_code": 200})(),
        )

        class _RpcServer:
            class weblogUpdates:
                @staticmethod
                def ping(*_a, **_kw):
                    return {"flerror": False}

        import xmlrpc.client as _xmlrpc
        monkeypatch.setattr(
            _xmlrpc, "ServerProxy", lambda *_a, **_kw: _RpcServer(),
        )

        publisher.notify_directories(
            "https://nerranetwork.com/podcast.rss", show_name="Test",
        )

        assert any("pubsubhubbub" in u for u in post_calls), (
            f"PubSubHubbub WebSub call missing — Podcast Index will "
            f"no longer pick up the feed. POST calls: {post_calls}"
        )
