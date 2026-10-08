"""Oct 8 2026 — an expired resumable upload session restarts once.

Tesla Ep628, SpaceX Ep124 and Omni View Ep199 lost their long-form video
to ``HttpError 410 "Gone"`` from the resumable upload endpoint, while four
other long-form uploads on the same token succeeded that morning. A 404 or
410 on a resumable upload means YouTube discarded the upload SESSION, and
Google's documented remedy is to begin the upload again. The tenacity retry
around ``_execute_resumable_upload`` reused the dead request (and did not
retry 410 at all), so the video was lost for the day.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import youtube  # noqa: E402

errors = pytest.importorskip("googleapiclient.errors")


class _Resp(dict):
    def __init__(self, status: int):
        super().__init__()
        self.status = status
        self.reason = "Gone"


def _http_error(status: int):
    return errors.HttpError(_Resp(status), b'{"error": {"message": "Gone"}}')


def _install(monkeypatch, outcomes: list):
    """Each insert() pops the next outcome: an exception or a response."""
    inserts = []

    class _Request:
        def __init__(self, outcome):
            self.outcome = outcome

        def next_chunk(self):
            if isinstance(self.outcome, BaseException):
                raise self.outcome
            return None, self.outcome

        def execute(self):
            return {}

    class _Videos:
        def insert(self, **kwargs):
            inserts.append(kwargs)
            return _Request(outcomes.pop(0))

    class _YouTube:
        def videos(self):
            return _Videos()

        def thumbnails(self):
            return type("T", (), {"set": lambda self, **k: _Request({})})()

    fake_discovery = type(sys)("googleapiclient.discovery")
    fake_discovery.build = lambda *a, **kw: _YouTube()
    fake_http = type(sys)("googleapiclient.http")
    fake_http.MediaFileUpload = lambda *a, **kw: object()
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery", fake_discovery)
    monkeypatch.setitem(sys.modules, "googleapiclient.http", fake_http)
    return inserts


def _upload(tmp_path):
    video = tmp_path / "ep.mp4"
    video.write_bytes(b"\x00" * 1024)
    return youtube.upload_video(video, credentials=object(), title="T",
                                description="d", tags=[], category_id=28)


@pytest.mark.parametrize("status", [404, 410])
def test_an_expired_session_restarts_with_a_new_one(monkeypatch, tmp_path, status):
    inserts = _install(monkeypatch, [_http_error(status), {"id": "vid123"}])
    result = _upload(tmp_path)
    assert result.video_id == "vid123"
    assert len(inserts) == 2, "the restart must open a NEW session (a new insert)"
    assert inserts[0]["body"] == inserts[1]["body"]


def test_the_restart_happens_once(monkeypatch, tmp_path):
    inserts = _install(monkeypatch, [_http_error(410), _http_error(410)])
    with pytest.raises(errors.HttpError):
        _upload(tmp_path)
    assert len(inserts) == 2


def test_other_client_errors_are_not_restarted(monkeypatch, tmp_path):
    inserts = _install(monkeypatch, [_http_error(400), {"id": "never"}])
    with pytest.raises(errors.HttpError):
        _upload(tmp_path)
    assert len(inserts) == 1
