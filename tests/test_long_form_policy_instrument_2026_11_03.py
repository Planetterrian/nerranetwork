"""Nov 3 2026 — the long-form policy reads the Shorts tier's ruler, as an
INSTRUMENT (youtube-2 steps 1, 2, 4 + the efficiency-9 readout).

What binds:
  - A dub long is a velocity only from its seventh day
    (``LONG_MIN_AGE_DAYS`` is per channel: en 2, ru 7, fr 7).
  - Every policy entry on every channel carries the fixed-age long read
    (``long_d3_median_21d`` / ``long_n_21d`` / ``long_vs_hook_ratio_21d`` /
    ``long_subs_per_1k_age7_pooled_21d`` / ``long_channel_d3_median_21d``)
    and RU/FR entries carry ``hook_short_d3_median_21d`` like EN.
  - The dub long overlay (``DUB_LONG_RELATIVE``) is SHIPPED OFF: with
    ``DUB_LONG_RELATIVE_ENABLED`` False nothing flips ``publish_long_form``;
    enabled in a test, FR tesla at hook 49 / long 13 goes long-off after two
    nights and a show whose long earns 60% of its hook stays on.
  - ``compute_tier`` is still called positionally by older guards.
  - The dub renders record ``long_form_render_duration_s`` on the index row.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "uyp_long_form_instrument", _ROOT / "scripts" / "update_youtube_policy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _vid(slug="tesla", kind="long", channel="en", published="2026-10-26", views=10):
    return {"video_id": "x", "show_slug": slug, "episode": 1, "kind": kind,
            "channel": channel, "title": "t", "hook": "h",
            "published": published, "views": views}


def _stats(videos, generated="2026-11-02T00:00:00+00:00"):
    return {"schema_version": 1, "generated": generated, "window_days": 90,
            "shows": {"somedir": {"videos": videos}}}


AS_OF = datetime.date(2026, 11, 2)


def _long_row(show, ch, published, d3, d7=None, subs7=None):
    views = {"2": max(0, d3 - 1), "3": d3}
    subs = {"2": 0, "3": 0}
    if d7 is not None:
        views["7"] = d7
        if subs7 is not None:
            subs["7"] = subs7
    return {"kind": "long", "channel": ch, "show": show, "published": published,
            "window": "", "views_by_age": views, "subs_by_age": subs}


def _hook_row(show, ch, published, d3):
    return {"kind": "short", "channel": ch, "show": show, "published": published,
            "window": "hook_open", "views_by_age": {"3": d3}, "subs_by_age": {"3": 0}}


def _reach(rows, updated=AS_OF.isoformat()):
    return {"schema_version": 1, "updated": updated,
            "videos": {f"v{i}": r for i, r in enumerate(rows)}}


def _days_ago(n):
    return (AS_OF - datetime.timedelta(days=n)).isoformat()


def _rows(show, ch, *, hook_d3, long_d3, long_n=5, hook_n=8, long_age_from=8,
          long_d7=None, long_subs7=None):
    """A show's 21-day reach: *hook_n* hook Shorts at *hook_d3* and *long_n*
    long-forms at *long_d3*, the longs at least *long_age_from* days old."""
    rows = [_hook_row(show, ch, _days_ago(3 + i), hook_d3) for i in range(hook_n)]
    rows += [_long_row(show, ch, _days_ago(long_age_from + i), long_d3,
                       d7=long_d7, subs7=long_subs7) for i in range(long_n)]
    return rows


# ---------------------------------------------------------------------------
# 1. A dub long is a rate only from its seventh day
# ---------------------------------------------------------------------------


class TestDubLongsAreARateFromDaySeven:
    def test_the_floor_is_per_channel(self):
        mod = _load_script()
        assert mod.LONG_MIN_AGE_DAYS == {"en": 2, "ru": 7, "fr": 7}
        assert mod.long_min_age_days("fr") == 7
        assert mod.long_min_age_days("ru") == 7
        assert mod.long_min_age_days("en") == 2
        assert mod.long_min_age_days("") == 2
        assert mod.long_min_age_days("zz") == 2

    def test_a_dub_long_two_days_old_contributes_no_velocity(self):
        mod = _load_script()
        vel = mod.collect_velocities(_stats([
            _vid(kind="long", channel="fr", published=_days_ago(2), views=40),  # out
            _vid(kind="long", channel="fr", published=_days_ago(6), views=60),  # out
            _vid(kind="long", channel="fr", published=_days_ago(7), views=70),  # in: 10/day
            _vid(kind="long", channel="ru", published=_days_ago(3), views=90),  # out
            _vid(kind="long", channel="ru", published=_days_ago(9), views=90),  # in: 10/day
        ]))
        assert vel[("tesla", "fr", "long")] == [10.0]
        assert vel[("tesla", "ru", "long")] == [10.0]

    def test_the_en_floor_is_unchanged(self):
        mod = _load_script()
        vel = mod.collect_velocities(_stats([
            _vid(kind="long", channel="en", published=_days_ago(1), views=40),  # out
            _vid(kind="long", channel="en", published=_days_ago(2), views=40),  # in: 20/day
        ]))
        assert vel[("tesla", "en", "long")] == [20.0]

    def test_dub_shorts_are_not_held_back(self):
        mod = _load_script()
        vel = mod.collect_velocities(_stats([
            _vid(kind="short", channel="fr", published=_days_ago(1), views=40),
        ]))
        assert vel[("tesla", "fr", "short")] == [40.0]


# ---------------------------------------------------------------------------
# 2. The long-form read, on every entry of every channel
# ---------------------------------------------------------------------------


class TestLongReachInstrument:
    def test_collect_long_reach_rows(self):
        mod = _load_script()
        reach = _reach([
            _long_row("tesla", "fr", _days_ago(13), 13, d7=30, subs7=1),
            _long_row("tesla", "fr", _days_ago(5), 20),            # no age-7 yet
            {"kind": "long", "channel": "fr", "show": "tesla",        # never seen at 3
             "published": _days_ago(2), "views_by_age": {"2": 4}, "subs_by_age": {}},
            _hook_row("tesla", "fr", _days_ago(4), 50),              # a Short
            _long_row("tesla", "fr", _days_ago(22), 99, d7=120, subs7=3),  # past the window
        ])
        rows = mod.collect_long_reach(reach)[("tesla", "fr")]
        assert [r["published"] for r in rows] == [_days_ago(13), _days_ago(5)]
        assert rows[0] == {"published": _days_ago(13), "age": 13, "d3": 13,
                           "d7": 30, "subs7": 1}
        assert rows[1]["d7"] is None and rows[1]["subs7"] is None
        assert mod.collect_long_reach(None) == {}
        assert mod.collect_long_reach({"videos": {}}) == {}

    def test_channel_long_medians(self):
        mod = _load_script()
        reach = _reach(
            _rows("tesla", "fr", hook_d3=40, long_d3=10, long_n=3)
            + _rows("spacex", "fr", hook_d3=40, long_d3=30, long_n=3)
            + _rows("tesla", "en", hook_d3=40, long_d3=50, long_n=2))
        medians = mod.channel_long_medians(mod.collect_long_reach(reach))
        assert medians == {"fr": 20.0, "en": 50.0}

    def test_long_reach_keys(self):
        mod = _load_script()
        longs = [
            {"published": "d", "age": 10, "d3": 10, "d7": 30, "subs7": 1},
            {"published": "d", "age": 9, "d3": 20, "d7": 40, "subs7": 0},
            {"published": "d", "age": 8, "d3": 30, "d7": 50, "subs7": 1},
        ]
        hooks = [("d", 40), ("d", 50)]
        keys = mod.long_reach_keys(longs, hooks)
        assert keys == {
            "long_d3_median_21d": 20.0,
            "long_n_21d": 3,
            "long_vs_hook_ratio_21d": 0.44,            # 20 / 45
            "long_subs_per_1k_age7_pooled_21d": 16.67,  # 2 subs / 120 views
        }
        # Pooled, never a per-show median: the median of [1, 0, 1] subs per
        # video is 1 and of the per-video rates is 20 per 1,000 — neither
        # is the number recorded.
        # Under 30 pooled views a rate is not a rate.
        thin = [{"published": "d", "age": 9, "d3": 5, "d7": 6, "subs7": 1}]
        assert mod.long_reach_keys(thin, hooks)["long_subs_per_1k_age7_pooled_21d"] is None
        # A long not yet seen at age 7 is left out of the pool, not read as 0.
        young = longs + [{"published": "d", "age": 4, "d3": 99, "d7": None, "subs7": None}]
        assert mod.long_reach_keys(young, hooks)["long_subs_per_1k_age7_pooled_21d"] == 16.67
        # No hook Shorts: a ratio is not invented.
        assert mod.long_reach_keys(longs, [])["long_vs_hook_ratio_21d"] is None
        # No longs: unmeasured, never 0.
        assert mod.long_reach_keys([], hooks) == {
            "long_d3_median_21d": None, "long_n_21d": 0,
            "long_vs_hook_ratio_21d": None,
            "long_subs_per_1k_age7_pooled_21d": None}

    def test_every_entry_carries_the_keys(self):
        mod = _load_script()
        reach = _reach(_rows("tesla", "fr", hook_d3=49, long_d3=13, long_d7=20, long_subs7=0)
                       + _rows("tesla", "en", hook_d3=71, long_d3=47, long_d7=80, long_subs7=1))
        stats = _stats([_vid(kind="short", channel="fr", published=_days_ago(3), views=30)
                        for _ in range(5)])
        policy = mod.build_policy(stats, None, now_iso="2026-11-03T00:00:00+00:00",
                                  reach=reach)
        wanted = ("long_d3_median_21d", "long_n_21d", "long_vs_hook_ratio_21d",
                  "long_subs_per_1k_age7_pooled_21d", "long_channel_d3_median_21d",
                  "hook_short_d3_median_21d", "hook_short_n_21d", "dub_long_gated")
        for channel, shows in policy["channels"].items():
            for slug, entry in shows.items():
                for key in wanted:
                    assert key in entry, (channel, slug, key)
                assert entry["dub_long_gated"] is False, (channel, slug)
        fr = policy["channels"]["fr"]["tesla"]
        assert fr["hook_short_d3_median_21d"] == 49 and fr["hook_short_n_21d"] == 8
        assert fr["long_d3_median_21d"] == 13 and fr["long_n_21d"] == 5
        assert fr["long_vs_hook_ratio_21d"] == 0.27
        assert fr["long_subs_per_1k_age7_pooled_21d"] == 0.0
        assert fr["long_channel_d3_median_21d"] == 13
        en = policy["channels"]["en"]["tesla"]
        assert en["long_d3_median_21d"] == 47 and en["long_vs_hook_ratio_21d"] == 0.66
        assert en["long_subs_per_1k_age7_pooled_21d"] == 12.5  # 5 subs / 400 views
        # A show with no reach rows is unmeasured, never 0.
        ru = policy["channels"]["ru"]["tesla"]
        assert ru["long_d3_median_21d"] is None and ru["long_n_21d"] == 0
        assert ru["hook_short_d3_median_21d"] is None
        # No reach file: the keys exist and read unmeasured.
        dark = mod.build_policy(stats, policy, now_iso="2026-11-04T00:00:00+00:00",
                                reach=None)
        fr2 = dark["channels"]["fr"]["tesla"]
        assert fr2["long_d3_median_21d"] is None and fr2["hook_short_d3_median_21d"] is None
        assert fr2["long_channel_d3_median_21d"] is None

    def test_ru_fr_entries_carry_their_hook_short_reach(self):
        mod = _load_script()
        today = datetime.date(2026, 11, 3)
        obs = [(_days_ago(3 + i), 62) for i in range(8)]
        for ch in ("ru", "fr"):
            e = mod.advance_dead_shorts(None, obs, ch, today, have_reach=True,
                                        channel_median=70.0)
            assert e["hook_short_d3_median_21d"] == 62 and e["hook_short_n_21d"] == 8, ch
            # the tier logic stays EN-only
            assert e["shorts_probe_weekly"] is False and e["shorts_dead_pending"] is None
            assert e["shorts_dead_streak"] == 0 and "hook_short_floor" not in e
            # a dead-looking dub show never enters either
            dead = mod.advance_dead_shorts(None, [(_days_ago(3 + i), 1) for i in range(8)],
                                           ch, today, have_reach=True, channel_median=70.0)
            assert dead["hook_short_d3_median_21d"] == 1
            assert dead["shorts_probe_weekly"] is False and dead["shorts_dead_pending"] is None
            # no reach file: unmeasured, and a stale flag is cleared as before
            held = mod.advance_dead_shorts({"shorts_probe_weekly": True}, None, ch, today,
                                           have_reach=False)
            assert held["hook_short_d3_median_21d"] is None and held["hook_short_n_21d"] == 0
            assert held["shorts_probe_weekly"] is False
        # EN is byte-for-byte the Oct 31 behaviour.
        en = mod.advance_dead_shorts(None, [(_days_ago(3 + i), 1) for i in range(8)],
                                     "en", today, have_reach=True, channel_median=11.0)
        assert en["hook_short_d3_median_21d"] == 1 and en["shorts_dead_pending"] is True
        assert en["hook_short_floor"] == 5.5


# ---------------------------------------------------------------------------
# 3. The dub long overlay: shipped off, and what it does when it is on
# ---------------------------------------------------------------------------


def _two_show_fixture():
    """FR tesla: hook 49 / long 13 (five settled longs). FR FF: hook 50 /
    long 30 — 60% of its hook. Both start on tier A."""
    reach = _reach(_rows("tesla", "fr", hook_d3=49, long_d3=13)
                   + _rows("fascinating_frontiers", "fr", hook_d3=50, long_d3=30))
    stats = _stats([_vid(slug, "short", "fr", _days_ago(3), 60)
                    for slug in ("tesla", "fascinating_frontiers") for _ in range(5)])
    prev = {"schema_version": 1, "channels": {"fr": {
        "tesla": {"tier": "A", "publish_long_form": True, "shorts_per_episode": 2},
        "fascinating_frontiers": {"tier": "A", "publish_long_form": True,
                                  "shorts_per_episode": 2},
    }}}
    return reach, stats, prev


class TestDubLongOverlayIsShippedOff:
    def test_shipped_state(self):
        mod = _load_script()
        assert mod.DUB_LONG_RELATIVE_ENABLED is False
        assert mod.DUB_LONG_RELATIVE == 0.5
        assert mod.DUB_LONG_MIN_VIDEOS == 4
        assert mod.DUB_LONG_CHANNELS == frozenset({"ru", "fr"})

    def test_compute_tier_is_still_called_positionally(self):
        mod = _load_script()
        tier, long_vpd, _s, reason = mod.compute_tier([9.0] * 4, [20.0] * 5, "C", "fr")
        assert tier == "A" and long_vpd == 9.0
        # the old guard's exact call shape (tests/test_youtube_policy.py)
        tier, long_vpd, _s, _r = mod.compute_tier([9.0, 9.0], [20.0] * 5, "C", "ru")
        assert long_vpd is None and tier == "C"

    def test_a_dead_read_changes_nothing_while_disabled(self):
        mod = _load_script()
        dead = {"long_d3_median": 13.0, "long_n": 5, "hook_d3_median": 49.0,
                "min_age_days": 7}
        assert mod.dub_long_gate_reason("fr", dead) == ""
        tier, _l, _s, reason = mod.compute_tier([9.0] * 4, [20.0] * 5, "C", "fr",
                                                dub_long_read=dead)
        assert tier == "A" and "long off" not in reason

    def test_nothing_flips_while_disabled(self):
        mod = _load_script()
        reach, stats, prev = _two_show_fixture()
        p1 = mod.build_policy(stats, prev, now_iso="2026-11-03T00:00:00+00:00", reach=reach)
        p2 = mod.build_policy(stats, p1, now_iso="2026-11-04T00:00:00+00:00", reach=reach)
        for p in (p1, p2):
            for slug in ("tesla", "fascinating_frontiers"):
                e = p["channels"]["fr"][slug]
                assert e["tier"] == "A" and e["publish_long_form"] is True, slug
                assert e["computed"] == "A" and e["dub_long_gated"] is False, slug
        # the numbers are still recorded
        assert p2["channels"]["fr"]["tesla"]["long_vs_hook_ratio_21d"] == 0.27

    def test_enabled_overlay_turns_fr_tesla_off_after_two_nights(self, monkeypatch):
        mod = _load_script()
        monkeypatch.setattr(mod, "DUB_LONG_RELATIVE_ENABLED", True)
        reach, stats, prev = _two_show_fixture()
        night1 = mod.build_policy(stats, prev, now_iso="2026-11-03T00:00:00+00:00",
                                  reach=reach)
        t1 = night1["channels"]["fr"]["tesla"]
        assert t1["tier"] == "A" and t1["publish_long_form"] is True   # hysteresis
        assert t1["computed"] == "C" and t1["pending"] == "C" and t1["streak"] == 1
        assert t1["dub_long_gated"] is True
        assert "13" in t1["reason"] and "49" in t1["reason"] and "long off" in t1["reason"]
        night2 = mod.build_policy(stats, night1, now_iso="2026-11-04T00:00:00+00:00",
                                  reach=reach)
        t2 = night2["channels"]["fr"]["tesla"]
        assert t2["tier"] == "C" and t2["publish_long_form"] is False
        assert t2["shorts_per_episode"] >= 1   # Shorts untouched
        # A show whose long earns 60% of its hook stays on.
        for p in (night1, night2):
            ff = p["channels"]["fr"]["fascinating_frontiers"]
            assert ff["tier"] == "A" and ff["publish_long_form"] is True
            assert ff["dub_long_gated"] is False
        # Night 3 with no reach file: the verdict is held, never reset.
        night3 = mod.build_policy(stats, night2, now_iso="2026-11-05T00:00:00+00:00",
                                  reach=None)
        t3 = night3["channels"]["fr"]["tesla"]
        assert t3["tier"] == "C" and t3["publish_long_form"] is False
        assert t3["dub_long_gated"] is True and "held" in t3["reason"]

    def test_enabled_overlay_needs_four_settled_longs_and_never_touches_en(self, monkeypatch):
        mod = _load_script()
        monkeypatch.setattr(mod, "DUB_LONG_RELATIVE_ENABLED", True)
        # three settled longs: not a read
        thin = _reach(_rows("tesla", "fr", hook_d3=49, long_d3=13, long_n=3))
        read = mod.dub_long_read(mod.collect_long_reach(thin)[("tesla", "fr")],
                                 mod.collect_hook_short_reach(thin)[("tesla", "fr")], "fr")
        assert read["long_n"] == 3 and mod.dub_long_gate_reason("fr", read) == ""
        # five longs under seven days old (ages 2-6): not velocities, not a read
        young = _reach(_rows("tesla", "fr", hook_d3=49, long_d3=13, long_age_from=2))
        read = mod.dub_long_read(mod.collect_long_reach(young)[("tesla", "fr")],
                                 mod.collect_hook_short_reach(young)[("tesla", "fr")], "fr")
        assert read["long_n"] == 0 and read["min_age_days"] == 7
        assert mod.dub_long_gate_reason("fr", read) == ""
        # the same dead numbers on EN change nothing (the overlay is a dub rule)
        dead = {"long_d3_median": 13.0, "long_n": 5, "hook_d3_median": 49.0,
                "min_age_days": 2}
        assert mod.dub_long_gate_reason("en", dead) == ""
        tier, *_ = mod.compute_tier([9.0] * 4, [20.0] * 5, "C", "en", dub_long_read=dead)
        assert tier == "A"
        # a hook Short median of 0 or None is never a bar
        assert mod.dub_long_gate_reason("fr", {**dead, "hook_d3_median": None}) == ""
        assert mod.dub_long_gate_reason("fr", {**dead, "hook_d3_median": 0}) == ""


class TestTheRulesThatStay:
    def test_en_two_probe_promotion_and_the_dub_full_read(self):
        mod = _load_script()
        tier, long_vpd, *_ = mod.compute_tier([2.5, 1.5], [5.0] * 4, "C", "en")
        assert long_vpd == 2.0 and tier in ("A", "B")
        for ch in ("ru", "fr"):
            tier, long_vpd, *_ = mod.compute_tier([9.0, 9.0], [20.0] * 5, "C", ch)
            assert long_vpd is None and tier == "C", ch

    def test_weekly_long_form_probe_untouched(self):
        from engine.youtube_policy import _is_probe_day, resolve_publish_plan
        policy = {"channels": {"fr": {"tesla": {
            "tier": "C", "publish_long_form": False, "shorts_per_episode": 2,
            "dub_long_gated": True, "reason": "tier C"}}}}
        base = datetime.date(2026, 11, 2)
        probes = 0
        for d in range(7):
            day = base + datetime.timedelta(days=d)
            plan = resolve_publish_plan(policy, slug="tesla", channel="fr",
                                        yaml_publish_long=True, yaml_shorts=2,
                                        smart_mode=True, adaptive_enabled=True,
                                        probe_today=day)
            assert plan["shorts"] == 2
            if plan["publish_long"]:
                probes += 1
                assert _is_probe_day(day, slug="tesla", channel="fr")
        assert probes == 1


# ---------------------------------------------------------------------------
# 4. The dub renders record their duration on the index row
# ---------------------------------------------------------------------------


def _summaries(tmp_path, lang):
    summaries = tmp_path / "summaries.json"
    summaries.write_text(json.dumps({"podcast": "TST", "summaries": [{
        "episode_num": 5,
        "date": "2026-01-01",  # old → past the no_scenes_yet gate
        "episode_title": "Ep 5",
        "translations": {lang: {"title": "Titre de l'épisode", "description": "d",
                                "audio_url": ""}},
    }]}), encoding="utf-8")
    return summaries


def _arm_common(monkeypatch, tmp_path, dub_mod):
    import engine.publisher as pub_mod
    import engine.transcripts as tr_mod
    import engine.video as video_mod
    import engine.youtube as yt_mod

    monkeypatch.setattr(yt_mod, "get_channel_credentials_from_env",
                        lambda channel="en": object())
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"jpg")
    monkeypatch.setattr(dub_mod, "_cover_path", lambda config: cover)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"images": []}), encoding="utf-8")
    monkeypatch.setattr(dub_mod, "_fresh_manifest_path",
                        lambda dest_dir, **kw: manifest)
    monkeypatch.setattr(dub_mod, "_download_images", lambda urls, d: [])
    monkeypatch.setattr(dub_mod, "_en_optimized_long_title", lambda *a, **k: "")
    calls = {"uploads": []}
    monkeypatch.setattr(yt_mod, "post_video_comment",
                        lambda *, credentials, video_id, text: "cmt1")

    def _fake_upload(video_path, **k):
        calls["uploads"].append(str(video_path))
        n = len(calls["uploads"])
        return SimpleNamespace(watch_url=f"https://yt/v{n}", video_id=f"vid{n}")

    monkeypatch.setattr(video_mod, "build_long_form_video", lambda *a, **k: None)
    monkeypatch.setattr(video_mod, "build_short_video", lambda *a, **k: None)
    monkeypatch.setattr(yt_mod, "upload_video", _fake_upload)
    monkeypatch.setattr(pub_mod, "generate_episode_thumbnail",
                        lambda cover, ep, date, out, **k: out.write_bytes(b"t"))
    monkeypatch.setattr(pub_mod, "generate_shorts_end_card", lambda *a, **k: None)
    monkeypatch.setattr(tr_mod, "generate_transcript", lambda *a, **k: None)
    return calls


class TestDubRendersRecordTheirDuration:
    def test_record_video_writes_the_field_only_when_set(self, tmp_path):
        from engine.youtube_index import record_video
        idx = tmp_path / "youtube_videos.fr.json"
        record_video(video_id="a", show_slug="tesla", episode=5, kind="long",
                     channel="fr", index_path=idx)
        record_video(video_id="b", show_slug="tesla", episode=5, kind="long",
                     channel="fr", render_duration_s=1314.26, index_path=idx)
        rows = {r["video_id"]: r for r in json.loads(idx.read_text())["videos"]}
        assert "long_form_render_duration_s" not in rows["a"]
        assert rows["b"]["long_form_render_duration_s"] == 1314.3

    def test_ru_dub_long_row_records_its_render_time(self, tmp_path, monkeypatch):
        from engine import ru_dub
        summaries = _summaries(tmp_path, "ru")
        cfg = SimpleNamespace(
            slug="tesla", name="Tesla Shorts Time",
            youtube=SimpleNamespace(ru_dub_enabled=True, publish_shorts=True,
                                    privacy_status="public", category_id=28,
                                    ru_podcast_playlist_id=None,
                                    short_duration_seconds=35.0,
                                    shorts_start_offset=0.0),
            multilingual=SimpleNamespace(enabled=True, languages=["ru"]),
            publishing=SimpleNamespace(summaries_json=str(summaries),
                                       base_url="https://nerranetwork.com"),
            episode=SimpleNamespace(output_dir=str(tmp_path / "out")),
            keywords=["Tesla"],
        )
        monkeypatch.setattr(ru_dub, "_policy_plan", lambda config: {
            "publish_long": True, "shorts": 1, "tier": "A",
            "applied": True, "reason": "", "shorts_probe": False})
        audio = tmp_path / "ep5.ru.mp3"
        audio.write_bytes(b"mp3")
        monkeypatch.setattr(ru_dub, "_resolve_ru_audio", lambda *a, **k: audio)
        _arm_common(monkeypatch, tmp_path, ru_dub)
        res = ru_dub.publish_ru_dub(cfg, 5)
        assert res["status"] == "done"
        assert isinstance(res["long_form_render_duration_s"], float)
        assert res["long_form_render_duration_s"] >= 0.0
        idx = json.loads((tmp_path / "out" / "youtube_videos.ru.json").read_text())
        rows = {r["kind"]: r for r in idx["videos"] if r.get("video_id")}
        assert rows["long"]["long_form_render_duration_s"] == res["long_form_render_duration_s"]
        assert "long_form_render_duration_s" not in rows["short"]

    def test_lang_dub_long_row_records_its_render_time(self, tmp_path, monkeypatch):
        from engine import lang_dub
        summaries = _summaries(tmp_path, "fr")
        cfg = SimpleNamespace(
            slug="tesla", name="Tesla Shorts Time",
            youtube=SimpleNamespace(dub_languages=["fr"], dub_playlist_ids={},
                                    publish_shorts=True, adaptive_publishing=True,
                                    category_id=28, privacy_status="public",
                                    short_duration_seconds=35.0,
                                    shorts_start_offset=0.0, auto_comment=True),
            multilingual=SimpleNamespace(enabled=True, languages=["fr"]),
            publishing=SimpleNamespace(summaries_json=str(summaries),
                                       base_url="https://nerranetwork.com"),
            episode=SimpleNamespace(output_dir=str(tmp_path / "out")),
            keywords=["Tesla"],
        )
        monkeypatch.setattr(lang_dub, "_policy_plan", lambda config, lang: {
            "publish_long": True, "shorts": 1, "tier": "A",
            "applied": True, "reason": "", "shorts_probe": False})
        audio = tmp_path / "ep5.fr.mp3"
        audio.write_bytes(b"mp3")
        monkeypatch.setattr(lang_dub, "_resolve_audio", lambda *a, **k: audio)
        idx_path = tmp_path / "out" / "youtube_videos.fr.json"
        monkeypatch.setattr(lang_dub, "index_path", lambda cfg_, lang_: idx_path)
        _arm_common(monkeypatch, tmp_path, lang_dub)
        res = lang_dub.publish_lang_dub(cfg, 5, "fr")
        assert res["status"] == "done", res
        assert isinstance(res["long_form_render_duration_s"], float)
        idx = json.loads(idx_path.read_text())
        rows = {r["kind"]: r for r in idx["videos"] if r.get("video_id")}
        assert rows["long"]["long_form_render_duration_s"] == res["long_form_render_duration_s"]
        assert "long_form_render_duration_s" not in rows["short"]

    def test_both_dub_paths_pass_the_duration_to_the_index(self):
        for name in ("engine/ru_dub.py", "engine/lang_dub.py"):
            src = (_ROOT / name).read_text(encoding="utf-8")
            assert "_long_render_started = time.monotonic()" in src, name
            assert 'render_duration_s=result["long_form_render_duration_s"]' in src, name


class TestTheRuntimeDocumentsTheKeys:
    def test_engine_docstring_names_every_instrument_key(self):
        import engine.youtube_policy as yp
        doc = yp.__doc__ or ""
        for key in ("long_d3_median_21d", "long_n_21d", "long_vs_hook_ratio_21d",
                    "long_subs_per_1k_age7_pooled_21d", "long_channel_d3_median_21d",
                    "hook_short_d3_median_21d", "dub_long_gated",
                    "DUB_LONG_RELATIVE_ENABLED", "LONG_MIN_AGE_DAYS",
                    "long_form_render_duration_s"):
            assert key in doc, key
