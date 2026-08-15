"""Drift guards for the adaptive YouTube publishing policy (July 2026).

Covers the three layers:
  - ``scripts/update_youtube_policy.py`` — velocity math, tier thresholds,
    probe floor, insufficient-data hold, hysteresis, seeds, best-effort
    behavior on missing inputs.
  - ``engine/youtube_policy.py`` — the pure runtime resolution consumers use
    (legacy passthrough contract, smart-mode raise rule).
  - Wiring — run_show / engine.pipeline / engine.ru_dub /
    scripts/publish_ru_dubs consume the policy, and the nightly workflow
    rebuilds + commits it.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.youtube_policy import load_policy, resolve_publish_plan  # noqa: E402


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "update_youtube_policy", _ROOT / "scripts" / "update_youtube_policy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _vid(slug="tesla", kind="long", channel="en",
         published="2026-07-10", views=10):
    return {"video_id": "x", "show_slug": slug, "episode": 1, "kind": kind,
            "channel": channel, "title": "t", "hook": "h",
            "published": published, "views": views}


def _stats(videos, generated="2026-07-13T00:00:00+00:00"):
    return {"schema_version": 1, "generated": generated, "window_days": 90,
            "shows": {"somedir": {"videos": videos}}}


# ---------------------------------------------------------------------------
# scripts/update_youtube_policy.py — computation
# ---------------------------------------------------------------------------


class TestVelocityMath:
    def test_vpd_is_age_normalized(self):
        mod = _load_script()
        vel = mod.collect_velocities(_stats([
            _vid(published="2026-07-08", views=50),   # 5 days old → 10/day
            _vid(published="2026-07-03", views=100),  # 10 days old → 10/day
        ]))
        assert vel[("tesla", "en", "long")] == [10.0, 10.0]

    def test_same_day_video_divides_by_one(self):
        mod = _load_script()
        vel = mod.collect_velocities(_stats([
            _vid(published="2026-07-13", views=7),
        ]))
        assert vel[("tesla", "en", "long")] == [7.0]

    def test_window_excludes_old_and_future_videos(self):
        mod = _load_script()
        vel = mod.collect_velocities(_stats([
            _vid(published="2026-06-20", views=500),  # 23 days old — out
            _vid(published="2026-07-20", views=500),  # future — out
            _vid(published="2026-06-29", views=14),   # exactly 14 days — in
        ]))
        assert vel[("tesla", "en", "long")] == [1.0]

    def test_channels_and_kinds_are_separate_buckets(self):
        mod = _load_script()
        vel = mod.collect_velocities(_stats([
            _vid(kind="long", channel="en", published="2026-07-12", views=4),
            _vid(kind="short", channel="en", published="2026-07-12", views=8),
            _vid(kind="long", channel="ru", published="2026-07-12", views=2),
        ]))
        assert vel[("tesla", "en", "long")] == [4.0]
        assert vel[("tesla", "en", "short")] == [8.0]
        assert vel[("tesla", "ru", "long")] == [2.0]


class TestTierRules:
    def test_thresholds(self):
        mod = _load_script()
        # (long_vpd, short_vpd) → tier
        cases = [
            ([2.0] * 4, [5.0] * 4, "A"),
            ([2.0] * 4, [1.0] * 4, "B"),
            ([0.5] * 4, [1.0] * 4, "C"),
            ([0.5] * 4, [0.1] * 4, "D"),
            ([1.0] * 4, [4.0] * 4, "A"),   # boundaries are inclusive
        ]
        for long_vpds, short_vpds, want in cases:
            tier, _l, _s, reason = mod.compute_tier(long_vpds, short_vpds, "B")
            assert tier == want, reason

    def test_probe_floor_shorts_never_zero(self):
        mod = _load_script()
        for tier, (_long, shorts) in mod.TIER_SETTINGS.items():
            assert shorts >= 1, f"tier {tier} would zero out Shorts"

    def test_insufficient_data_holds_active_dimension(self):
        mod = _load_script()
        # No long-form videos at all (a shorts-only show): the long dimension
        # holds whatever the active tier says.
        tier_a, *_ = mod.compute_tier([], [5.0] * 4, "A")
        assert tier_a == "A"  # active long stays on
        tier_c, *_ = mod.compute_tier([], [5.0] * 4, "C")
        assert tier_c == "C"  # active long stays off
        # 3 videos < MIN_VIDEOS_CONFIDENT is still insufficient.
        tier_held, long_vpd, _s, reason = mod.compute_tier(
            [9.0] * 3, [5.0] * 4, "C")
        assert tier_held == "C" and long_vpd is None
        assert "held" in reason


class TestHysteresis:
    def test_first_run_seed_active_pending_computed(self):
        mod = _load_script()
        active, pending, streak = mod.advance_hysteresis(None, "C", "A")
        assert (active, pending, streak) == ("A", "C", 1)

    def test_first_run_computed_matches_seed(self):
        mod = _load_script()
        assert mod.advance_hysteresis(None, "A", "A") == ("A", None, 0)

    def test_flip_only_after_two_consecutive(self):
        mod = _load_script()
        prev = {"tier": "A", "pending": "C", "streak": 1}
        assert mod.advance_hysteresis(prev, "C", "A") == ("C", None, 0)

    def test_changed_pending_resets_streak(self):
        mod = _load_script()
        prev = {"tier": "A", "pending": "C", "streak": 1}
        assert mod.advance_hysteresis(prev, "D", "A") == ("A", "D", 1)

    def test_computed_back_to_active_clears_pending(self):
        mod = _load_script()
        prev = {"tier": "A", "pending": "C", "streak": 1}
        assert mod.advance_hysteresis(prev, "A", "A") == ("A", None, 0)

    def test_two_run_flip_through_build_policy(self):
        mod = _load_script()
        # tesla is seeded A on EN; feed data that computes C twice.
        stats = _stats(
            [_vid(kind="long", published="2026-07-08", views=1)] * 4
            + [_vid(kind="short", published="2026-07-08", views=10)] * 4
        )
        p1 = mod.build_policy(stats, None)
        e1 = p1["channels"]["en"]["tesla"]
        assert e1["tier"] == "A" and e1["pending"] == "C" and e1["streak"] == 1
        assert e1["publish_long_form"] is True
        p2 = mod.build_policy(stats, p1)
        e2 = p2["channels"]["en"]["tesla"]
        assert e2["tier"] == "C" and e2["pending"] is None and e2["streak"] == 0
        assert e2["publish_long_form"] is False
        assert e2["shorts_per_episode"] == 1


class TestSeedsAndBestEffort:
    def test_cold_start_actives_match_seeds(self):
        mod = _load_script()
        policy = mod.build_policy(None, None)
        for channel, seeds in mod.SEED_TIERS.items():
            for slug, seed in seeds.items():
                entry = policy["channels"][channel][slug]
                assert entry["tier"] == seed
                want_long, want_shorts = mod.TIER_SETTINGS[seed]
                assert entry["publish_long_form"] is want_long
                assert entry["shorts_per_episode"] == want_shorts

    def test_ru_seeds_gate_long_form_off_everywhere(self):
        mod = _load_script()
        assert set(mod.SEED_TIERS["ru"].values()) == {"C"}

    def test_dp_pod_excluded(self):
        mod = _load_script()
        for seeds in mod.SEED_TIERS.values():
            assert "dp_pod" not in seeds

    def test_missing_stats_writes_seed_policy(self, tmp_path, monkeypatch):
        mod = _load_script()
        monkeypatch.setattr(mod, "ROOT", tmp_path)
        monkeypatch.setattr(sys, "argv", ["update_youtube_policy.py"])
        assert mod.main() == 0
        out = json.loads((tmp_path / "api" / "youtube_policy.json").read_text())
        assert out["channels"]["en"]["tesla"]["tier"] == "A"

    def test_missing_stats_keeps_existing_policy_untouched(
            self, tmp_path, monkeypatch):
        mod = _load_script()
        monkeypatch.setattr(mod, "ROOT", tmp_path)
        out_path = tmp_path / "api" / "youtube_policy.json"
        out_path.parent.mkdir(parents=True)
        out_path.write_text('{"sentinel": true}', encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["update_youtube_policy.py"])
        assert mod.main() == 0
        assert json.loads(out_path.read_text()) == {"sentinel": True}

    def test_stale_stats_freeze_a_valid_policy(self, tmp_path, monkeypatch):
        # Aug 2026: a stats file whose fetch silently died keeps its old
        # `generated` stamp; recomputing tiers from the frozen cohort
        # every night could flip a tier on day two of an outage
        # (STREAK_TO_FLIP=2). Stale stats + a valid existing policy =
        # freeze loudly, change nothing.
        mod = _load_script()
        monkeypatch.setattr(mod, "ROOT", tmp_path)
        (tmp_path / "api").mkdir(parents=True)
        (tmp_path / "api" / "youtube_stats.json").write_text(
            json.dumps(_stats([], generated="2026-07-01T00:00:00+00:00")),
            encoding="utf-8")
        out_path = tmp_path / "api" / "youtube_policy.json"
        out_path.write_text('{"sentinel": true}', encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["update_youtube_policy.py"])
        assert mod.main() == 0
        assert json.loads(out_path.read_text()) == {"sentinel": True}

    def test_unreadable_previous_policy_restarts_from_seeds(
            self, tmp_path, monkeypatch):
        mod = _load_script()
        monkeypatch.setattr(mod, "ROOT", tmp_path)
        (tmp_path / "api").mkdir(parents=True)
        (tmp_path / "api" / "youtube_stats.json").write_text(
            json.dumps(_stats([])), encoding="utf-8")
        (tmp_path / "api" / "youtube_policy.json").write_text(
            "not json{", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["update_youtube_policy.py"])
        assert mod.main() == 0
        out = json.loads(
            (tmp_path / "api" / "youtube_policy.json").read_text())
        assert out["channels"]["ru"]["tesla"]["tier"] == "C"


class TestShortsCountFollowsData:
    """July 22 2026: shorts_per_episode follows the computed short_vpd, not
    the tier letter — the C tier had pinned shorts-only shows to 1 Short
    even at short_vpd 18-45 (RU spacex/tesla/FF), discarding the computed
    "-> 2 Short(s)"."""

    def test_shorts_only_show_earns_second_short(self):
        mod = _load_script()
        # RU tesla is seeded C (shorts-only). Warm Shorts: 1 day old, 10
        # vpd — past the 2-Short bar, short of the 3-Short band.
        stats = _stats(
            [_vid(kind="short", channel="ru", published="2026-07-12",
                  views=10)] * 4)
        policy = mod.build_policy(stats, None)
        entry = policy["channels"]["ru"]["tesla"]
        assert entry["tier"] == "C"
        assert entry["publish_long_form"] is False
        assert entry["shorts_per_episode"] == 2

    def test_cold_shorts_drop_to_one_while_tier_letter_holds(self):
        mod = _load_script()
        # EN tesla seeded A; strong long-form, cold Shorts → computed B.
        # Hysteresis holds the ACTIVE letter at A for one run, but the
        # emitted Shorts count follows the data immediately.
        stats = _stats(
            [_vid(kind="long", published="2026-07-08", views=100)] * 4
            + [_vid(kind="short", published="2026-07-08", views=5)] * 4)
        policy = mod.build_policy(stats, None)
        entry = policy["channels"]["en"]["tesla"]
        assert entry["tier"] == "A"          # letter held by hysteresis
        assert entry["publish_long_form"] is True
        assert entry["shorts_per_episode"] == 1   # data says 1

    def test_data_thin_dimension_still_holds_active_count(self):
        mod = _load_script()
        # < MIN_VIDEOS_CONFIDENT shorts → count holds the active tier's.
        stats = _stats(
            [_vid(kind="short", channel="ru", published="2026-07-12",
                  views=50)] * 2)
        policy = mod.build_policy(stats, None)
        entry = policy["channels"]["ru"]["tesla"]
        assert entry["shorts_per_episode"] == 1


class TestCommittedPolicyFile:
    """The generated api/youtube_policy.json stays structurally sound."""

    def test_shape_and_probe_floor(self):
        policy = json.loads(
            (_ROOT / "api" / "youtube_policy.json").read_text(encoding="utf-8"))
        assert policy["schema_version"] == 1
        # en/ru original channels + fr since the @NerraFR launch
        # (July 18 2026, generalized language-dub engine).
        assert set(policy["channels"]) == {"en", "ru", "fr"}
        for shows in policy["channels"].values():
            assert shows  # never an empty channel
            for slug, entry in shows.items():
                assert entry["tier"] in ("A", "B", "C", "D"), slug
                assert entry["shorts_per_episode"] >= 1, slug
                assert isinstance(entry["publish_long_form"], bool), slug
                assert entry["reason"], slug


# ---------------------------------------------------------------------------
# engine/youtube_policy.py — runtime resolution
# ---------------------------------------------------------------------------


def _policy(entry, channel="en", slug="tesla"):
    return {"schema_version": 1, "channels": {channel: {slug: entry}}}


class TestResolvePublishPlan:
    def test_no_policy_is_legacy_passthrough(self):
        plan = resolve_publish_plan(
            None, slug="tesla", channel="en", yaml_publish_long=True,
            yaml_shorts=2, smart_mode=True, adaptive_enabled=True)
        assert plan == {"publish_long": True, "shorts": 2, "tier": "",
                        "applied": False, "reason": ""}

    def test_opt_out_is_legacy_passthrough(self):
        plan = resolve_publish_plan(
            _policy({"publish_long_form": False, "shorts_per_episode": 1}),
            slug="tesla", channel="en", yaml_publish_long=True,
            yaml_shorts=1, smart_mode=True, adaptive_enabled=False)
        assert plan["applied"] is False and plan["publish_long"] is True

    def test_absent_slug_is_legacy_passthrough(self):
        plan = resolve_publish_plan(
            _policy({"publish_long_form": False}, slug="spacex"),
            slug="tesla", channel="en", yaml_publish_long=True,
            yaml_shorts=1, smart_mode=True, adaptive_enabled=True)
        assert plan["applied"] is False

    def test_policy_gates_long_form_off(self):
        plan = resolve_publish_plan(
            _policy({"tier": "C", "publish_long_form": False,
                     "shorts_per_episode": 1, "reason": "cold"}),
            slug="tesla", channel="en", yaml_publish_long=True,
            yaml_shorts=1, smart_mode=False, adaptive_enabled=True,
            # Pin to a non-Monday: the weekly probe (tested separately in
            # TestMondayProbe) legitimately re-enables long-form on
            # Mondays, and an unpinned date made this test fail weekly.
            probe_today=datetime.date(2026, 7, 21))
        assert plan["applied"] is True
        assert plan["publish_long"] is False
        assert plan["tier"] == "C"

    def test_raise_to_two_requires_smart_mode(self):
        entry = {"tier": "A", "publish_long_form": True,
                 "shorts_per_episode": 2}
        blocked = resolve_publish_plan(
            _policy(entry), slug="tesla", channel="en",
            yaml_publish_long=True, yaml_shorts=1,
            smart_mode=False, adaptive_enabled=True)
        assert blocked["shorts"] == 1
        allowed = resolve_publish_plan(
            _policy(entry), slug="tesla", channel="en",
            yaml_publish_long=True, yaml_shorts=1,
            smart_mode=True, adaptive_enabled=True)
        assert allowed["shorts"] == 2

    def test_lowering_always_allowed(self):
        plan = resolve_publish_plan(
            _policy({"publish_long_form": True, "shorts_per_episode": 1}),
            slug="tesla", channel="en", yaml_publish_long=True,
            yaml_shorts=2, smart_mode=False, adaptive_enabled=True)
        assert plan["shorts"] == 1

    def test_probe_floor_at_runtime(self):
        plan = resolve_publish_plan(
            _policy({"publish_long_form": False, "shorts_per_episode": 0}),
            slug="tesla", channel="en", yaml_publish_long=True,
            yaml_shorts=1, smart_mode=True, adaptive_enabled=True)
        assert plan["shorts"] == 1

    def test_ru_channel_lookup(self):
        plan = resolve_publish_plan(
            _policy({"tier": "C", "publish_long_form": False}, channel="ru"),
            slug="tesla", channel="ru", yaml_publish_long=True,
            yaml_shorts=1, smart_mode=False, adaptive_enabled=True,
            probe_today=datetime.date(2026, 7, 21))  # non-Monday (see above)
        assert plan["applied"] is True and plan["publish_long"] is False

    def test_load_policy_missing_and_corrupt(self, tmp_path):
        assert load_policy(tmp_path / "nope.json") is None
        bad = tmp_path / "bad.json"
        bad.write_text("{", encoding="utf-8")
        assert load_policy(bad) is None
        no_channels = tmp_path / "flat.json"
        no_channels.write_text('{"schema_version": 1}', encoding="utf-8")
        assert load_policy(no_channels) is None

    def test_load_policy_reads_committed_file(self):
        policy = load_policy(_ROOT / "api" / "youtube_policy.json")
        assert policy is not None and "channels" in policy


# ---------------------------------------------------------------------------
# Config field
# ---------------------------------------------------------------------------


class TestConfigField:
    def test_dataclass_declares_adaptive_publishing_default_true(self):
        from engine.config import YouTubeConfig
        assert YouTubeConfig().adaptive_publishing is True

    def test_defaults_yaml_documents_flag(self):
        data = yaml.safe_load(
            (_ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert data["youtube"]["adaptive_publishing"] is True


# ---------------------------------------------------------------------------
# run_show + pipeline wiring (source guards — _publish_youtube needs a full
# render environment; the resolution helper itself is unit-tested above)
# ---------------------------------------------------------------------------


class TestRunShowWiring:
    def _src(self):
        return (_ROOT / "run_show.py").read_text(encoding="utf-8")

    def test_publish_stage_resolves_policy(self):
        src = self._src()
        assert "from engine.youtube_policy import load_policy, resolve_publish_plan" in src
        assert '"adaptive_publishing", True' in src

    def test_long_form_gates_on_policy_local_not_yaml(self):
        src = self._src()
        # The YAML field is read exactly once — as the seed of the
        # policy-resolved local. Every publish gate uses the local, so a
        # policy long-skip covers the visual plan, video clips, optimized
        # title, and the long-form render/upload alike.
        assert src.count("config.youtube.publish_long_form") == 1
        assert "if _policy_publish_long:" in src

    def test_shorts_count_comes_from_plan(self):
        assert "shorts_count_yaml = _policy_shorts_count" in self._src()

    def test_metrics_keys_recorded(self):
        src = self._src()
        for key in ("yt_policy_tier", "yt_policy_long_skipped",
                    "yt_policy_shorts"):
            assert key in src
        pipeline = (_ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        for key in ("yt_policy_tier", "yt_policy_long_skipped",
                    "yt_policy_shorts"):
            assert f'"{key}"' in pipeline


# ---------------------------------------------------------------------------
# RU dub gating (engine/ru_dub.py + scripts/publish_ru_dubs.py)
# ---------------------------------------------------------------------------


class TestRuDubPolicyGating:
    """A shorts-only RU policy skips the long render+upload but still ships
    the Short (audio + scenes + thumbnail are shared work)."""

    def _cfg(self, tmp_path):
        summaries = tmp_path / "summaries.json"
        summaries.write_text(json.dumps({"podcast": "TST", "summaries": [{
            "episode_num": 5,
            "date": "2026-01-01",  # old → past the no_scenes_yet gate
            "episode_title": "Ep 5",
            "translations": {"ru": {"title": "Заголовок", "description": "Оп",
                                    "audio_url": ""}},
        }]}), encoding="utf-8")
        return SimpleNamespace(
            slug="tesla", name="Tesla Shorts Time",
            youtube=SimpleNamespace(ru_dub_enabled=True, publish_shorts=True,
                                    privacy_status="public", category_id=28,
                                    ru_podcast_playlist_id=None,
                                    short_duration_seconds=55.0,
                                    shorts_start_offset=0.0),
            multilingual=SimpleNamespace(enabled=True, languages=["ru"]),
            publishing=SimpleNamespace(summaries_json=str(summaries),
                                       base_url="https://nerranetwork.com"),
            episode=SimpleNamespace(output_dir=str(tmp_path / "out")),
            keywords=["Tesla"],
        )

    def _arm(self, monkeypatch, tmp_path, plan):
        from engine import ru_dub
        import engine.youtube as yt_mod
        import engine.video as video_mod
        import engine.publisher as pub_mod
        import engine.transcripts as tr_mod

        monkeypatch.setattr(ru_dub, "_policy_plan", lambda config: plan)
        monkeypatch.setattr(yt_mod, "get_channel_credentials_from_env",
                            lambda channel="en": object())
        cover = tmp_path / "cover.jpg"
        cover.write_bytes(b"jpg")
        monkeypatch.setattr(ru_dub, "_cover_path", lambda config: cover)
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"images": [
            {"show_slug": "tesla", "episode_id": "ep005",
             "intended_use": use, "original_url": f"https://r2/{use}{i}.jpg"}
            for use in ("segment_card", "social") for i in (1, 2)
        ]}), encoding="utf-8")
        monkeypatch.setattr(ru_dub, "_fresh_manifest_path",
                            lambda dest_dir, **kw: manifest)
        audio = tmp_path / "ep5.ru.mp3"
        audio.write_bytes(b"mp3")
        monkeypatch.setattr(ru_dub, "_resolve_ru_audio",
                            lambda *a, **k: audio)
        monkeypatch.setattr(ru_dub, "_download_images", lambda urls, d: [])
        monkeypatch.setattr(ru_dub, "_en_optimized_long_title",
                            lambda *a, **k: "")

        calls = {"long_renders": 0, "short_renders": 0, "uploads": [],
                 "comments": []}

        def _fake_comment(*, credentials, video_id, text):
            calls["comments"].append(text)
            return "cmt1"

        # Stubbed because July 2026 made the RU funnel comment fire on
        # shorts-only days too (it used to be gated on a long-form URL
        # that @NerraRU rarely has, so it posted nothing most days).
        # Without this stub the real client would be constructed here and
        # reach for the YouTube discovery document over the network.
        monkeypatch.setattr(yt_mod, "post_video_comment", _fake_comment)

        def _fake_long(*a, **k):
            calls["long_renders"] += 1

        def _fake_short(*a, **k):
            calls["short_renders"] += 1

        def _fake_upload(video_path, **k):
            calls["uploads"].append(str(video_path))
            n = len(calls["uploads"])
            return SimpleNamespace(watch_url=f"https://yt/v{n}",
                                   video_id=f"vid{n}")

        monkeypatch.setattr(video_mod, "build_long_form_video", _fake_long)
        monkeypatch.setattr(video_mod, "build_short_video", _fake_short)
        monkeypatch.setattr(yt_mod, "upload_video", _fake_upload)
        monkeypatch.setattr(pub_mod, "generate_episode_thumbnail",
                            lambda cover, ep, date, out, **k: out.write_bytes(b"t"))
        monkeypatch.setattr(pub_mod, "generate_shorts_end_card",
                            lambda *a, **k: None)
        monkeypatch.setattr(tr_mod, "generate_transcript",
                            lambda *a, **k: None)
        return calls

    def test_shorts_only_policy_skips_long_but_ships_short(
            self, tmp_path, monkeypatch):
        from engine import ru_dub
        cfg = self._cfg(tmp_path)
        calls = self._arm(monkeypatch, tmp_path, {
            "publish_long": False, "shorts": 1, "tier": "C",
            "applied": True, "reason": "cold longs"})
        res = ru_dub.publish_ru_dub(cfg, 5)
        assert calls["long_renders"] == 0
        assert calls["short_renders"] == 1
        assert len(calls["uploads"]) == 1
        assert res["status"] == "done"
        assert res["policy_long_skipped"] is True
        assert "long_url" not in res
        assert res.get("short_url")
        # The Short's upload is recorded in the RU index (the sweep's
        # done-marker under a shorts-only tier).
        idx = json.loads((tmp_path / "out" / "youtube_videos.ru.json")
                         .read_text(encoding="utf-8"))
        kinds = {v["kind"] for v in idx["videos"] if v.get("video_id")}
        assert kinds == {"short"}
        # July 2026: the funnel comment now fires WITHOUT a RU long-form.
        # @NerraRU is shorts-only for most shows, so gating the comment on
        # a long-form URL meant the network's highest-reach surface posted
        # nothing at all on nearly every run. It must point at a Russian
        # destination — never at an English video.
        assert len(calls["comments"]) == 1
        assert "/ru/" in calls["comments"][0] or "nerranetwork.com" in calls["comments"][0]
        assert "youtube.com" not in calls["comments"][0]
        assert "youtu.be" not in calls["comments"][0]

    def test_legacy_plan_still_uploads_long_and_short(
            self, tmp_path, monkeypatch):
        from engine import ru_dub
        cfg = self._cfg(tmp_path)
        calls = self._arm(monkeypatch, tmp_path, {
            "publish_long": True, "shorts": 1, "tier": "",
            "applied": False, "reason": ""})
        res = ru_dub.publish_ru_dub(cfg, 5)
        assert calls["long_renders"] == 1
        assert calls["short_renders"] == 1
        assert len(calls["uploads"]) == 2
        assert res["status"] == "done"
        assert res.get("long_url") and res.get("short_url")
        assert "policy_long_skipped" not in res

    def test_policy_skip_when_short_also_disabled(self, tmp_path, monkeypatch):
        from engine import ru_dub
        cfg = self._cfg(tmp_path)
        calls = self._arm(monkeypatch, tmp_path, {
            "publish_long": False, "shorts": 1, "tier": "C",
            "applied": True, "reason": ""})
        res = ru_dub.publish_ru_dub(cfg, 5, build_short=False)
        assert res["status"] == "policy_skip"
        assert calls["uploads"] == []

    def test_dry_run_reports_policy_decision(self, tmp_path, monkeypatch):
        from engine import ru_dub
        cfg = self._cfg(tmp_path)
        self._arm(monkeypatch, tmp_path, {
            "publish_long": False, "shorts": 1, "tier": "C",
            "applied": True, "reason": ""})
        res = ru_dub.publish_ru_dub(cfg, 5, dry_run=True)
        assert res["status"] == "dryrun"
        assert res["policy_long"] is False

    def test_policy_plan_resolves_ru_channel(self):
        src = (_ROOT / "engine" / "ru_dub.py").read_text(encoding="utf-8")
        assert 'channel="ru"' in src
        assert "resolve_publish_plan" in src


class TestSweepDoneCheck:
    """publish_ru_dubs._already_done counts an uploaded Short (the
    deliverable under a shorts-only tier) — without it every sweep would
    re-upload a duplicate public Short."""

    def _driver(self):
        spec = importlib.util.spec_from_file_location(
            "publish_ru_dubs", _ROOT / "scripts" / "publish_ru_dubs.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _write_index(self, tmp_path, rows):
        (tmp_path / "youtube_videos.ru.json").write_text(
            json.dumps({"videos": rows}), encoding="utf-8")

    def test_uploaded_short_marks_done(self, tmp_path):
        drv = self._driver()
        cfg = SimpleNamespace(episode=SimpleNamespace(output_dir=str(tmp_path)))
        self._write_index(tmp_path, [
            {"episode": 5, "kind": "short", "video_id": "abc"}])
        assert drv._already_done(cfg, 5) is True

    def test_status_only_rows_still_not_done(self, tmp_path):
        drv = self._driver()
        cfg = SimpleNamespace(episode=SimpleNamespace(output_dir=str(tmp_path)))
        self._write_index(tmp_path, [
            {"episode": 5, "kind": "short", "status": "failed"},
            {"episode": 5, "kind": "long", "status": "deferred"}])
        assert drv._already_done(cfg, 5) is False


# ---------------------------------------------------------------------------
# Nightly workflow wiring
# ---------------------------------------------------------------------------


class TestNightlyWiring:
    def _wf(self):
        return yaml.safe_load(
            (_ROOT / ".github" / "workflows" / "nightly-maintenance.yml")
            .read_text(encoding="utf-8"))

    def test_policy_step_runs_after_performance_update(self):
        wf = self._wf()
        steps = wf["jobs"]["generate-artifacts"]["steps"]
        runs = [str(s.get("run") or "") for s in steps]
        perf_idx = next(i for i, r in enumerate(runs)
                        if "update_youtube_performance.py" in r)
        policy_idx = next(i for i, r in enumerate(runs)
                          if "update_youtube_policy.py" in r)
        assert policy_idx == perf_idx + 1
        # Best-effort: a policy failure must never redden the nightly.
        assert "::warning::" in runs[policy_idx]

    def test_policy_json_in_commit_add_paths(self):
        wf = self._wf()
        steps = wf["jobs"]["generate-artifacts"]["steps"]
        commit = next(s for s in steps
                      if str(s.get("uses", "")).endswith("safe-commit-push"))
        assert "api/youtube_policy.json" in commit["with"]["add-paths"]


class TestMondayLongFormProbe:
    """A Shorts-only show produces no long-form analytics, so without a
    periodic probe it could never re-earn its long-form (one-way door).
    Mondays grant one probe long-form to policy-gated shows."""

    def _policy(self):
        return {"channels": {"en": {"omni_view": {
            "tier": "C", "publish_long_form": False,
            "shorts_per_episode": 1, "reason": "tier C"}}}}

    def test_probe_day_grants_probe_long(self):
        # Probe days are sharded per (channel, slug) since Aug 2026 —
        # every gated show probing on the same UTC Monday was a weekly
        # render/upload spike where each probe competed with every other
        # probe for the same day's browse surface. en/omni_view hashes
        # to weekday 2 (Wednesday); 2026-07-22 is a Wednesday.
        import datetime
        from engine.youtube_policy import resolve_publish_plan, _is_probe_day
        probe_date = datetime.date(2026, 7, 22)
        assert _is_probe_day(probe_date, slug="omni_view", channel="en")
        plan = resolve_publish_plan(
            self._policy(), slug="omni_view", channel="en",
            yaml_publish_long=True, yaml_shorts=1, smart_mode=True,
            adaptive_enabled=True, probe_today=probe_date)
        assert plan["publish_long"] is True
        assert "probe" in plan["reason"].lower()

    def test_probes_are_sharded_across_the_week(self):
        # Not every show probes on the same weekday.
        import datetime
        from engine.youtube_policy import _is_probe_day
        slugs = ["omni_view", "tesla", "spacex", "fascinating_frontiers",
                 "modern_investing", "env_intel", "planetterrian"]
        base = datetime.date(2026, 7, 20)  # a Monday
        days = {s: next(d for d in range(7)
                        if _is_probe_day(base + datetime.timedelta(days=d),
                                         slug=s, channel="en"))
                for s in slugs}
        assert len(set(days.values())) > 1, days

    def test_non_probe_day_keeps_long_gated(self):
        import datetime
        from engine.youtube_policy import resolve_publish_plan
        plan = resolve_publish_plan(
            self._policy(), slug="omni_view", channel="en",
            yaml_publish_long=True, yaml_shorts=1, smart_mode=True,
            adaptive_enabled=True, probe_today=datetime.date(2026, 7, 21))
        assert plan["publish_long"] is False

    def test_probe_never_enables_yaml_disabled_long(self):
        # A show whose YAML never published long-form (e.g. RU dub config
        # off) must not get a probe long out of nowhere.
        import datetime
        from engine.youtube_policy import resolve_publish_plan
        plan = resolve_publish_plan(
            self._policy(), slug="omni_view", channel="en",
            yaml_publish_long=False, yaml_shorts=1, smart_mode=True,
            adaptive_enabled=True, probe_today=datetime.date(2026, 7, 20))
        assert plan["publish_long"] is False


class TestShortsSupplyLadder:
    """July 30 2026: a third Shorts band above 20 views/day.

    Until then the ladder topped out at 2, so RU spacex (62.3 vpd) and RU
    fascinating_frontiers (60.5) were allotted the same supply as RU
    modern_investing (4.9) — a 13x spread in demonstrated demand met by
    identical supply.
    """

    def test_ladder_bands(self):
        mod = _load_script()
        cases = [(0.0, 1), (3.9, 1), (4.0, 2), (19.9, 2), (20.0, 3),
                 (62.3, 3), (1000.0, 3)]
        for vpd, expected in cases:
            assert mod.shorts_for_vpd(vpd) == expected, f"vpd {vpd}"

    def test_ladder_never_returns_zero(self):
        """Shorts are the recovery signal — they never go to 0."""
        mod = _load_script()
        for vpd in (0.0, 0.01, 0.4):
            assert mod.shorts_for_vpd(vpd) >= 1

    def test_hot_shorts_only_show_earns_a_third(self):
        mod = _load_script()
        stats = _stats(
            [_vid(kind="short", channel="ru", published="2026-07-12",
                  views=60)] * 4)
        policy = mod.build_policy(stats, None)
        entry = policy["channels"]["ru"]["tesla"]
        assert entry["shorts_per_episode"] == 3
        assert entry["publish_long_form"] is False   # RU longs stay gated

    def test_written_count_matches_the_logged_computation(self):
        """The writer must not carry its own copy of the threshold rule.

        ``compute_tier`` reports the count in its human-readable reason
        and ``build_policy`` records it in the entry. Those were separate
        expressions until July 30 2026, so the first run after the
        3-Short band landed logged "-> 3 Short(s)" and wrote 2.
        """
        mod = _load_script()
        stats = _stats(
            [_vid(kind="short", channel="ru", published="2026-07-12",
                  views=60)] * 4)
        policy = mod.build_policy(stats, None)
        entry = policy["channels"]["ru"]["tesla"]
        assert f"-> {entry['shorts_per_episode']} Short(s)" in entry["reason"]

    def test_committed_policy_agrees_with_the_ladder(self):
        """api/youtube_policy.json is regenerated, not hand-edited.

        Since the shorts-count hysteresis (commit defdef51), the ACTIVE
        count may lawfully lag the ladder while a change is confirmed
        over consecutive runs — but then the entry must carry the ladder
        value as ``shorts_pending``. An active count that disagrees with
        the ladder with no pending record is a hand-edit or a script bug.
        """
        mod = _load_script()
        policy = json.loads(
            (_ROOT / "api" / "youtube_policy.json").read_text(encoding="utf-8"))
        for channel, entries in (policy.get("channels") or {}).items():
            for slug, entry in entries.items():
                vpd = entry.get("short_vpd")
                if vpd is None:
                    continue    # held — the count follows the active tier
                ladder = mod.shorts_for_vpd(vpd)
                if entry["shorts_per_episode"] == ladder:
                    continue
                assert entry.get("shorts_pending") == ladder, (
                    f"{channel}/{slug}: {vpd} vpd -> ladder {ladder} but "
                    f"active {entry['shorts_per_episode']} Short(s) with "
                    f"pending {entry.get('shorts_pending')!r} — neither "
                    "current nor mid-hysteresis"
                )


class TestMaxShortsCeiling:
    """The ceiling is one shared constant, not a literal per consumer.

    ``engine.ru_dub`` and ``engine.lang_dub`` each carried their own
    ``min(2, ...)``. Because the 3-Short band's members are RU dubs, those
    literals would have made the band a total no-op on exactly the channel
    it was written for.
    """

    def test_no_module_hardcodes_a_local_shorts_cap(self):
        import re
        for name in ("engine/ru_dub.py", "engine/lang_dub.py"):
            src = (_ROOT / name).read_text(encoding="utf-8")
            assert not re.search(r"min\(\s*\d+\s*,\s*int\(plan", src), (
                f"{name} caps the Shorts count with a literal — use "
                "engine.youtube_policy.MAX_SHORTS_PER_EPISODE"
            )
            assert "MAX_SHORTS_PER_EPISODE" in src, f"{name}"

    def test_ceiling_covers_the_top_ladder_band(self):
        mod = _load_script()
        from engine.youtube_policy import MAX_SHORTS_PER_EPISODE
        top = max(count for _, count in mod.SHORT_VPD_BANDS)
        assert MAX_SHORTS_PER_EPISODE >= top, (
            f"the ladder can ask for {top} Shorts but the ceiling is "
            f"{MAX_SHORTS_PER_EPISODE} — the top band would be unreachable"
        )

    def test_resolve_clamps_an_overreaching_policy_file(self):
        from engine.youtube_policy import MAX_SHORTS_PER_EPISODE
        policy = {"channels": {"ru": {"tesla": {
            "tier": "C", "publish_long_form": False,
            "shorts_per_episode": 99, "reason": "corrupt"}}}}
        plan = resolve_publish_plan(
            policy, slug="tesla", channel="ru", yaml_publish_long=False,
            yaml_shorts=1, smart_mode=True, adaptive_enabled=True)
        assert plan["shorts"] == MAX_SHORTS_PER_EPISODE

    def test_clamp_does_not_disturb_a_normal_plan(self):
        policy = {"channels": {"ru": {"tesla": {
            "tier": "C", "publish_long_form": False,
            "shorts_per_episode": 3, "reason": "hot"}}}}
        plan = resolve_publish_plan(
            policy, slug="tesla", channel="ru", yaml_publish_long=False,
            yaml_shorts=1, smart_mode=True, adaptive_enabled=True)
        assert plan["shorts"] == 3

    def test_third_short_still_requires_smart_mode(self):
        """Without the smart selector there is only one window to cut."""
        policy = {"channels": {"ru": {"tesla": {
            "tier": "C", "publish_long_form": False,
            "shorts_per_episode": 3, "reason": "hot"}}}}
        plan = resolve_publish_plan(
            policy, slug="tesla", channel="ru", yaml_publish_long=False,
            yaml_shorts=1, smart_mode=False, adaptive_enabled=True)
        assert plan["shorts"] == 1


class TestShortsCountHysteresis:
    """Aug 2026: raising the Shorts count needs 2 consecutive computed
    runs (band-edge oscillation around 20 vpd toggled 2<->3 nightly);
    lowering applies immediately."""

    def _build(self, mod, prev_entry, short_vpd):
        stats = _stats([])
        # Build a minimal previous policy carrying the entry under test.
        previous = {"channels": {"ru": {"spacex": prev_entry}}}
        vids = []
        import datetime as dt
        gen = dt.date.fromisoformat(stats["generated"][:10])
        for i in range(6):
            pub = (gen - dt.timedelta(days=i + 1)).isoformat()
            vids.append({"show_slug": "spacex", "channel": "ru",
                         "kind": "short", "published": pub,
                         "views": int(short_vpd * (i + 1))})
        stats["shows"]["somedir"]["videos"] = vids
        return mod.build_policy(stats, previous)

    def test_raise_holds_for_one_run_then_applies(self):
        mod = _load_script()
        prev = {"tier": "C", "shorts_per_episode": 2, "pending": "C",
                "streak": 5}
        out1 = self._build(mod, prev, short_vpd=25.0)
        e1 = out1["channels"]["ru"]["spacex"]
        assert e1["shorts_per_episode"] == 2      # held on first sighting
        assert e1["shorts_pending"] == 3
        out2 = self._build(mod, e1, short_vpd=25.0)
        e2 = out2["channels"]["ru"]["spacex"]
        assert e2["shorts_per_episode"] == 3      # confirmed on run 2

    def test_lowering_applies_immediately(self):
        mod = _load_script()
        prev = {"tier": "C", "shorts_per_episode": 3, "pending": "C",
                "streak": 5, "shorts_pending": 3, "shorts_streak": 9}
        out = self._build(mod, prev, short_vpd=5.0)
        e = out["channels"]["ru"]["spacex"]
        assert e["shorts_per_episode"] == 2
