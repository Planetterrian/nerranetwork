"""Drift guards for scripts/fetch_buttondown_stats.py (June 2026 growth pass)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.fetch_buttondown_stats import (  # noqa: E402
    fetch_subscriber_count,
    main,
)


class TestNoOpWithoutKey:
    def test_exit_zero_and_file_untouched(self, tmp_path, monkeypatch):
        monkeypatch.delenv("BUTTONDOWN_API_KEY", raising=False)
        out = tmp_path / "buttondown_stats.json"
        out.write_text('{"sentinel": true}', encoding="utf-8")

        rc = main(["--out", str(out)])

        assert rc == 0
        assert json.loads(out.read_text()) == {"sentinel": True}

    def test_fetch_failure_leaves_file_untouched(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "key")
        out = tmp_path / "buttondown_stats.json"
        out.write_text('{"subscriber_count": 42}', encoding="utf-8")

        with patch("scripts.fetch_buttondown_stats.fetch_subscriber_count",
                   return_value=None):
            rc = main(["--out", str(out)])

        assert rc == 0
        assert json.loads(out.read_text()) == {"subscriber_count": 42}


class TestCountParsing:
    def _resp(self, status=200, body=None):
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = body if body is not None else {}
        return resp

    def test_reads_count_field(self):
        with patch("scripts.fetch_buttondown_stats.requests.get",
                   return_value=self._resp(body={"count": 257, "results": []})):
            assert fetch_subscriber_count("key") == 257

    def test_missing_count_returns_none(self):
        with patch("scripts.fetch_buttondown_stats.requests.get",
                   return_value=self._resp(body={"results": []})):
            assert fetch_subscriber_count("key") is None

    def test_http_error_returns_none(self):
        with patch("scripts.fetch_buttondown_stats.requests.get",
                   return_value=self._resp(status=401)):
            assert fetch_subscriber_count("key") is None

    def test_network_error_returns_none(self):
        with patch("scripts.fetch_buttondown_stats.requests.get",
                   side_effect=ConnectionError("boom")):
            assert fetch_subscriber_count("key") is None

    def test_writes_stats_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "key")
        out = tmp_path / "b.json"
        with patch("scripts.fetch_buttondown_stats.fetch_subscriber_count",
                   return_value=257):
            rc = main(["--out", str(out)])
        assert rc == 0
        data = json.loads(out.read_text())
        assert data["subscriber_count"] == 257
        assert "fetched_at" in data
