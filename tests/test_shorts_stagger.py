"""Drift guards for staggered Shorts publishing (Aug 2026).

Operator directive: Short #1 publishes with the episode; later Shorts
upload private with ``status.publishAt`` at the channel's optimal hours so
one episode's Shorts spread through the day — on every channel (EN/RU/FR)
and on manual runs too. Core logic: engine/shorts_stagger.py; upload
plumbing: engine/youtube.py; wiring: run_show + ru_dub + lang_dub;
deferred funnel comments: sidecar + scripts/post_scheduled_short_comments.py.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from engine.shorts_stagger import (
    DEFAULT_SLOT_HOURS_UTC,
    format_publish_at,
    post_due_comments,
    queue_comment,
    resolve_slot_hours,
    stagger_publish_times,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UTC = dt.timezone.utc


def _at(h, m=0, day=5):
    return dt.datetime(2026, 8, day, h, m, tzinfo=UTC)


class TestStaggerTimes:
    def test_morning_run_uses_same_day_slots(self):
        # EN run at 11:30 UTC → 17:00 and 21:00 today.
        times = stagger_publish_times(_at(11, 30), 2,
                                      slot_hours=[17, 21, 23])
        assert times == [_at(17), _at(21)]

    def test_min_lead_skips_too_close_slot(self):
        # Run at 16:00: the 17:00 slot is only 60 min away (< 90 lead).
        times = stagger_publish_times(_at(16, 0), 1,
                                      slot_hours=[17, 21, 23])
        assert times == [_at(21)]

    def test_late_night_run_rolls_to_tomorrow(self):
        times = stagger_publish_times(_at(23, 30), 2,
                                      slot_hours=[17, 21, 23])
        assert times == [_at(17, day=6), _at(21, day=6)]

    def test_fallback_offsets_when_slots_exhausted(self):
        # Only one slot configured but three Shorts to schedule.
        times = stagger_publish_times(_at(11, 0), 3, slot_hours=[17])
        assert times[0] == _at(17)
        assert times[1] == _at(17, day=6)  # tomorrow's same slot
        assert len(times) == 3
        assert times[2] > times[1]

    def test_zero_count_returns_empty(self):
        assert stagger_publish_times(_at(11), 0, slot_hours=[17]) == []

    def test_strictly_increasing(self):
        times = stagger_publish_times(_at(3, 15), 3,
                                      slot_hours=[15, 18, 20])
        assert times == sorted(times)
        assert len(set(times)) == 3


class TestResolveSlotHours:
    class _Cfg:
        def __init__(self, slots):
            self.shorts_stagger_slots_utc = slots

    def test_yaml_override_wins(self):
        assert resolve_slot_hours(self._Cfg({"ru": [12, 16]}), "ru") == [12, 16]

    def test_defaults_per_channel(self):
        assert resolve_slot_hours(self._Cfg({}), "ru") == \
            sorted(DEFAULT_SLOT_HOURS_UTC["ru"])
        assert resolve_slot_hours(self._Cfg(None), "fr") == \
            sorted(DEFAULT_SLOT_HOURS_UTC["fr"])

    def test_unknown_channel_falls_back_to_en(self):
        assert resolve_slot_hours(self._Cfg({}), "zh") == \
            sorted(DEFAULT_SLOT_HOURS_UTC["en"])

    def test_invalid_entries_dropped(self):
        assert resolve_slot_hours(
            self._Cfg({"en": ["x", -1, 25, 18]}), "en") == [18]


class TestUploadBodyPublishAt:
    def test_publish_at_forces_private_and_sets_timestamp(self):
        from engine.youtube import _build_video_body
        body = _build_video_body(
            title="t", description="d", tags=[], category_id=28,
            default_language="en", privacy_status="public",
            contains_synthetic_media=True, made_for_kids=False,
            publish_at=_at(17),
        )
        assert body["status"]["privacyStatus"] == "private"
        assert body["status"]["publishAt"] == "2026-08-05T17:00:00Z"

    def test_no_publish_at_is_byte_identical_legacy(self):
        from engine.youtube import _build_video_body
        body = _build_video_body(
            title="t", description="d", tags=[], category_id=28,
            default_language="en", privacy_status="public",
            contains_synthetic_media=True, made_for_kids=False,
        )
        assert body["status"]["privacyStatus"] == "public"
        assert "publishAt" not in body["status"]

    def test_format_publish_at_rfc3339(self):
        assert format_publish_at(_at(15, 30)) == "2026-08-05T15:30:00Z"


class TestConfigPlumbing:
    """The silent-config-drop landmine: fields must exist on the dataclass
    AND the network default must be on with all three channels mapped."""

    def test_dataclass_declares_stagger_fields(self):
        from engine.config import YouTubeConfig
        cfg = YouTubeConfig()
        assert cfg.shorts_stagger_enabled is False  # dataclass default
        assert cfg.shorts_stagger_slots_utc == {}

    def test_network_default_enables_stagger_with_all_channels(self):
        from engine.config import load_config
        cfg = load_config(PROJECT_ROOT / "shows" / "spacex.yaml")
        assert cfg.youtube.shorts_stagger_enabled is True
        slots = cfg.youtube.shorts_stagger_slots_utc
        for ch in ("en", "ru", "fr"):
            assert slots.get(ch), f"channel {ch} missing stagger slots"
            assert all(0 <= int(h) <= 23 for h in slots[ch])


class TestDeferredComments:
    def test_queue_and_post_due(self, tmp_path, monkeypatch):
        ddir = tmp_path / "digests" / "spacex"
        ddir.mkdir(parents=True)
        assert queue_comment(ddir, video_id="vid1", channel="ru",
                             text="▶ link", publish_at=_at(15))
        # Re-queue same video → no duplicate.
        assert queue_comment(ddir, video_id="vid1", channel="ru",
                             text="▶ link", publish_at=_at(15))
        assert queue_comment(ddir, video_id="vid2", channel="ru",
                             text="▶ link2", publish_at=_at(20))
        data = json.loads((ddir / "scheduled_comments.json").read_text())
        assert len(data["pending"]) == 2

        posted = []
        import engine.youtube as yt
        monkeypatch.setattr(yt, "get_channel_credentials_from_env",
                            lambda ch: object())
        monkeypatch.setattr(
            yt, "post_video_comment",
            lambda *, credentials, video_id, text: posted.append(video_id)
            or "cid")
        # At 16:00 only vid1 (15:00) is due; vid2 (20:00) stays queued.
        stats = post_due_comments(tmp_path, now=_at(16))
        assert posted == ["vid1"]
        assert stats["posted"] == 1 and stats["kept"] == 1
        data = json.loads((ddir / "scheduled_comments.json").read_text())
        assert [e["video_id"] for e in data["pending"]] == ["vid2"]

    def test_missing_credentials_keep_entry(self, tmp_path, monkeypatch):
        ddir = tmp_path / "digests" / "tesla_shorts_time"
        ddir.mkdir(parents=True)
        queue_comment(ddir, video_id="v", channel="fr", text="t",
                      publish_at=_at(15))
        import engine.youtube as yt
        monkeypatch.setattr(yt, "get_channel_credentials_from_env",
                            lambda ch: None)
        stats = post_due_comments(tmp_path, now=_at(16))
        assert stats == {"posted": 0, "kept": 1, "dropped": 0}
        data = json.loads((ddir / "scheduled_comments.json").read_text())
        assert len(data["pending"]) == 1

    def test_stale_entries_dropped(self, tmp_path, monkeypatch):
        ddir = tmp_path / "digests" / "spacex"
        ddir.mkdir(parents=True)
        queue_comment(ddir, video_id="old", channel="en", text="t",
                      publish_at=_at(15))
        import engine.youtube as yt
        monkeypatch.setattr(yt, "get_channel_credentials_from_env",
                            lambda ch: object())
        monkeypatch.setattr(yt, "post_video_comment",
                            lambda **kw: pytest.fail("must not post stale"))
        stats = post_due_comments(tmp_path, now=_at(15, day=14))
        assert stats["dropped"] == 1
        data = json.loads((ddir / "scheduled_comments.json").read_text())
        assert data["pending"] == []


class TestWiring:
    """Source-scan guards: every publish path passes publish_at, and the
    comment sweep is wired into workflows that hold the channel tokens."""

    def test_run_show_passes_publish_at(self):
        src = (PROJECT_ROOT / "run_show.py").read_text()
        assert "publish_at=_publish_at" in src
        assert "stagger_publish_times" in src
        assert "yt_comments_queued" in src

    def test_ru_dub_passes_publish_at(self):
        src = (PROJECT_ROOT / "engine" / "ru_dub.py").read_text()
        assert "publish_at=_publish_at" in src
        assert "stagger_publish_times" in src
        assert "queue_comment" in src

    def test_lang_dub_passes_publish_at(self):
        src = (PROJECT_ROOT / "engine" / "lang_dub.py").read_text()
        assert "publish_at=_publish_at" in src
        assert "stagger_publish_times" in src
        assert "queue_comment" in src

    def test_comment_sweep_wired_into_workflows(self):
        ml = (PROJECT_ROOT / ".github" / "workflows"
              / "multilingual.yml").read_text()
        nightly = (PROJECT_ROOT / ".github" / "workflows"
                   / "nightly-maintenance.yml").read_text()
        assert "post_scheduled_short_comments.py" in ml
        assert "post_scheduled_short_comments.py" in nightly
        # The nightly add-paths whitelist landmine: the sweep edits the
        # sidecar, and a whitelist gap silently drops that edit for days.
        assert "digests/**/scheduled_comments.json" in nightly
