"""Caption-track upload: retry the transient, name the reason, RECORD it.

Sep 18 2026, Omni View Ep179: ``captions.insert`` answered HTTP 403 once
while six sibling long-forms on the same channel token uploaded their
tracks within the hour. The old path (a) never retried, (b) blamed every
403 on a missing ``youtube.force-ssl`` scope, and (c) set
``caption_track_uploaded`` on the publish result without it being on
the ``record_youtube_outcomes`` allowlist — so the refusal was findable
only in the Actions log. Since Sep 9 the uploaded track is the ONLY
caption layer on long-form, so a refusal is a captionless video.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_api(monkeypatch, outcomes):
    """Fake googleapiclient whose captions().insert().execute() pops from
    ``outcomes``: an Exception instance is raised, anything else returned."""
    calls = {"n": 0}

    class _FakeHttpError(Exception):
        def __init__(self, status, message):
            super().__init__(message)
            self.resp = SimpleNamespace(status=status)

    class _FakeRequest:
        def execute(self):
            calls["n"] += 1
            out = outcomes.pop(0)
            if isinstance(out, tuple):
                raise _FakeHttpError(*out)
            return out

    class _FakeCaptions:
        def insert(self, **kwargs):
            return _FakeRequest()

    class _FakeYouTube:
        def captions(self):
            return _FakeCaptions()

    fake = type(sys)("googleapiclient")
    disc = type(sys)("googleapiclient.discovery")
    http = type(sys)("googleapiclient.http")
    errs = type(sys)("googleapiclient.errors")
    errs.HttpError = _FakeHttpError
    disc.build = lambda *a, **kw: _FakeYouTube()
    http.MediaFileUpload = lambda *a, **kw: None
    fake.discovery, fake.http, fake.errors = disc, http, errs
    for name, mod in (("googleapiclient", fake),
                      ("googleapiclient.discovery", disc),
                      ("googleapiclient.http", http),
                      ("googleapiclient.errors", errs)):
        monkeypatch.setitem(sys.modules, name, mod)
    return calls


def _srt(tmp_path):
    p = tmp_path / "ep.srt"
    p.write_text("1\n00:00:00,000 --> 00:00:02,000\nHi\n", encoding="utf-8")
    return p


class TestRetryAndReason:
    def test_transient_403_is_retried_once_and_succeeds(self, monkeypatch, tmp_path):
        from engine import youtube as yt
        calls = _install_fake_api(monkeypatch, [(403, "backendError"), {"id": "c1"}])
        slept = []
        ok, reason = yt.upload_caption_track_detailed(
            credentials=object(), video_id="v", srt_path=_srt(tmp_path),
            _sleep=slept.append)
        assert ok is True and reason == ""
        assert calls["n"] == 2
        assert slept == [yt.CAPTION_TRACK_RETRY_DELAY_S]

    def test_scope_403_is_not_retried_and_names_the_scope(self, monkeypatch, tmp_path):
        from engine import youtube as yt
        calls = _install_fake_api(
            monkeypatch,
            [(403, "<HttpError 403 'Insufficient Permission: Request had "
                   "insufficient authentication scopes.'>"), {"id": "never"}])
        slept = []
        ok, reason = yt.upload_caption_track_detailed(
            credentials=object(), video_id="v", srt_path=_srt(tmp_path),
            _sleep=slept.append)
        assert ok is False
        assert reason == yt.CAPTION_REASON_SCOPE
        assert calls["n"] == 1 and slept == []

    def test_5xx_twice_fails_with_transient_reason(self, monkeypatch, tmp_path):
        from engine import youtube as yt
        calls = _install_fake_api(monkeypatch, [(500, "internal"), (503, "unavailable")])
        ok, reason = yt.upload_caption_track_detailed(
            credentials=object(), video_id="v", srt_path=_srt(tmp_path),
            _sleep=lambda s: None)
        assert ok is False
        assert reason == "http_503_transient"
        assert calls["n"] == 2

    def test_400_is_never_retried(self, monkeypatch, tmp_path):
        from engine import youtube as yt
        calls = _install_fake_api(monkeypatch, [(400, "invalidLanguage"), {"id": "never"}])
        ok, reason = yt.upload_caption_track_detailed(
            credentials=object(), video_id="v", srt_path=_srt(tmp_path),
            _sleep=lambda s: None)
        assert ok is False and reason == "http_400"
        assert calls["n"] == 1

    def test_bool_wrapper_keeps_its_contract(self, monkeypatch, tmp_path):
        """ru_dub / lang_dub call the bool form; they inherit the retry."""
        from engine import youtube as yt
        monkeypatch.setattr(yt, "CAPTION_TRACK_RETRY_DELAY_S", 0.0)
        calls = _install_fake_api(monkeypatch, [(429, "rateLimit"), {"id": "c"}])
        assert yt.upload_caption_track(
            credentials=object(), video_id="v", srt_path=_srt(tmp_path)) is True
        assert calls["n"] == 2

    def test_missing_srt_and_video_id_reasons(self, tmp_path):
        from engine import youtube as yt
        assert yt.upload_caption_track_detailed(
            credentials=object(), video_id="v",
            srt_path=tmp_path / "nope.srt") == (False, "no_srt")
        assert yt.upload_caption_track_detailed(
            credentials=object(), video_id="",
            srt_path=_srt(tmp_path)) == (False, "no_video_id")


class TestMetricIsRecorded:
    def _record(self, urls):
        from engine.pipeline import record_youtube_outcomes
        seen = {}

        class _M:
            def record(self, k, v):
                seen[k] = v

        cfg = SimpleNamespace(youtube=SimpleNamespace(enabled=True))
        record_youtube_outcomes(_M(), urls, 1.0, config=cfg)
        return seen

    def test_refusal_reaches_the_metrics_file(self):
        seen = self._record({"long_url": "https://youtu.be/x",
                             "caption_track_uploaded": False,
                             "caption_track_error": "http_403_transient"})
        assert seen["caption_track_uploaded"] is False
        assert seen["caption_track_error"] == "http_403_transient"

    def test_success_is_recorded_without_an_error_key(self):
        seen = self._record({"long_url": "https://youtu.be/x",
                             "caption_track_uploaded": True})
        assert seen["caption_track_uploaded"] is True
        assert "caption_track_error" not in seen

    def test_shorts_only_day_records_nothing(self):
        """No long-form, no track attempted — null, never a fake False."""
        seen = self._record({"short_url": "https://youtu.be/s"})
        assert "caption_track_uploaded" not in seen


class TestRunShowMessage:
    def test_warning_no_longer_presumes_the_scope(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "upload_caption_track_detailed(" in src
        assert "likely missing youtube.force-ssl" not in src
        assert 'result["caption_track_error"] = _cap_reason' in src


class TestPublishResultKeysAreMetricsOrExempt:
    """Plan item 6 (2026-09-18): a key assigned on ``_publish_youtube``'s
    result dict is either RECORDED (a string literal in engine/pipeline.py
    or a ``metrics.record("…")`` call in run_show.py) or named here as
    deliberately not a metric. Three silent keys in six weeks
    (shorts_fill_modes 07-22, grok_image_px_max 09-03,
    caption_track_uploaded 09-18) is a pattern; a NEW key that is
    neither fails CI. Adding a key to the exemption list is a decision,
    and the comment beside it says why."""

    # Carried on the result for other consumers (video index, RSS video
    # feed, funnel comments, the dub sweeps) or dormant pilots — not
    # per-episode metrics. Move a key OUT of this list when it gains a
    # consumer in record_youtube_outcomes.
    NOT_A_METRIC = {
        "short_urls", "short_video_ids", "short_errors",   # video index / errors captured per Short
        "video_podcast_url",                               # summaries_io.upsert_video reads it
        "shorts_scheduled_times", "yt_comments_queued",    # stagger sidecar + scheduled_comments.json
        "outro_card", "visual_fallback", "video_provider",  # render-plan carriers (visual_mode is the metric)
        "shorts_ab_variants",                              # shorts_ab (recorded) carries the same
        "grok_video_cost_usd", "grok_video_failures",      # retired Grok Video pilot (June 2026)
        "video_clips_cost_usd", "video_clips_failures", "video_clips_generated",  # retired clip pilot
    }

    def test_every_result_key_is_recorded_or_exempt(self):
        import re
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        pipe = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        i = src.index("def _publish_youtube")
        j = src.find("\ndef ", i + 10)
        body = src[i:j]
        assigned = sorted(set(re.findall(r'result\["(\w+)"\]\s*=', body)))
        assert len(assigned) > 40, "publish-result key scan found too few keys"
        pipe_literals = set(re.findall(r'"(\w+)"', pipe))
        run_show_recorded = set(re.findall(r'metrics\.record\(\s*"(\w+)"', src))
        silent = [k for k in assigned
                  if k not in pipe_literals and k not in run_show_recorded
                  and k not in self.NOT_A_METRIC]
        assert silent == [], (
            "publish-result keys recorded nowhere — allowlist them in "
            "engine.pipeline.record_youtube_outcomes or add them to "
            f"NOT_A_METRIC with a reason: {silent}")

    def test_exemptions_are_still_assigned(self):
        """A stale exemption hides nothing but should be pruned."""
        import re
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        i = src.index("def _publish_youtube")
        body = src[i:src.find("\ndef ", i + 10)]
        assigned = set(re.findall(r'result\["(\w+)"\]\s*=', body))
        stale = sorted(self.NOT_A_METRIC - assigned)
        assert stale == [], f"exempt keys no longer assigned: {stale}"

    def test_caption_keys_are_not_exempt(self):
        assert "caption_track_uploaded" not in self.NOT_A_METRIC
        assert "caption_track_error" not in self.NOT_A_METRIC
