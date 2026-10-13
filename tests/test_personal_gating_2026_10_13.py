"""Nerra Personal gating (Oct 13 2026, operator-directed): a show can be
members-only, or public one weekday with its daily episodes for members.

``engine/access.py`` owns the decision. These guards pin: the setting and
its fail-closed validation, the demand gate (skip at zero, produce when the
demand is unknown), where a members episode lives (private bucket +
``members/`` + the ledger), that no public surface ever sees one (Nerra
Daily, the on-air rotation, multilingual, the audit's missed-episode and
feed-freshness checks), that the Personal builder does, and that today
every show is still public.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from engine import access as A

ROOT = Path(__file__).resolve().parent.parent
MONDAY = dt.date(2026, 10, 12)
TUESDAY = dt.date(2026, 10, 13)


def _cfg(mode="public", weekday=0, minimum=1, slug="mag7"):
    return SimpleNamespace(
        slug=slug, name=slug,
        access=SimpleNamespace(mode=mode, public_weekday=weekday, min_members=minimum),
        storage=SimpleNamespace(endpoint_env="R2_ENDPOINT_URL",
                                access_key_env="R2_ACCESS_KEY_ID",
                                secret_key_env="R2_SECRET_ACCESS_KEY"),
    )


class TestTheSetting:
    def test_default_is_public_and_every_show_is_public_today(self):
        from engine.config import discover_show_slugs, load_config

        for slug in discover_show_slugs(ROOT / "shows"):
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
            assert A.access_mode(cfg) == "public", (
                f"{slug} is gated — flipping a show is the operator's call; "
                "update this guard in the same change")

    def test_an_unknown_mode_stops_the_run(self):
        # A typo must never fall back to publishing a gated show publicly.
        with pytest.raises(ValueError):
            A.access_mode(_cfg(mode="members-only"))
        with pytest.raises(ValueError):
            A.public_weekday(_cfg(mode="public_weekly", weekday=7))

    def test_which_days_are_public(self):
        assert A.is_public_on(_cfg("public"), TUESDAY)
        assert not A.is_public_on(_cfg("members_only"), MONDAY)
        weekly = _cfg("public_weekly", weekday=0)
        assert A.is_public_on(weekly, MONDAY)
        assert not A.is_public_on(weekly, TUESDAY)
        assert A.todays_access(weekly, TUESDAY) == A.MEMBERS
        assert A.describe(weekly) == "Free every Monday; daily for members"

    def test_config_loads_the_block(self):
        from engine.config import AccessConfig, ShowConfig

        assert ShowConfig.__dataclass_fields__["access"]
        assert AccessConfig() == AccessConfig(mode="public", public_weekday=0, min_members=1)


class TestDemandGate:
    def test_decisions(self):
        assert A.demand_decision("mag7", {"mag7": 2}, 1) == A.DemandDecision(True, 2, "members_selected")
        assert A.demand_decision("mag7", {"tesla": 4}, 1) == A.DemandDecision(False, 0, "no_member_demand")
        assert A.demand_decision("mag7", {}, 1).run is False
        # Unknown demand produces: a paying member may be waiting.
        assert A.demand_decision("mag7", None, 1) == A.DemandDecision(True, None, "demand_unknown")
        # min_members 0 is the operator's always-produce override.
        assert A.demand_decision("mag7", {}, 0).run is True

    def test_no_token_is_unknown_not_zero(self, monkeypatch):
        for env in A.DEMAND_TOKEN_ENVS:
            monkeypatch.delenv(env, raising=False)
        assert A.fetch_show_demand() is None

    def test_reads_counts_only(self, monkeypatch):
        monkeypatch.setenv("PERSONAL_DEMAND_TOKEN", "t")
        seen = {}

        class _Resp:
            status_code = 200

            def json(self):
                return {"ok": True, "members": 3, "demand": {"mag7": "2", "bad": "x"}}

        def fake_get(url, headers, timeout):
            seen.update(url=url, headers=headers)
            return _Resp()

        with mock.patch("requests.get", fake_get):
            assert A.fetch_show_demand() == {"mag7": 2}
        assert seen["url"].endswith("/api/admin/show-demand")
        assert seen["headers"] == {"Authorization": "Bearer t"}

    def test_an_http_error_is_unknown(self, monkeypatch):
        monkeypatch.setenv("PERSONAL_DEMAND_TOKEN", "t")
        with mock.patch("requests.get", return_value=SimpleNamespace(status_code=503)):
            assert A.fetch_show_demand() is None


class TestWhereAMembersEpisodeLives:
    def test_ledger_round_trip_and_numbering(self, tmp_path):
        assert A.max_members_episode(tmp_path) == 0
        A.record_members_episode(tmp_path, {"episode_num": 21, "date": "2026-10-13",
                                            "audio_url": "r2-private://b/k.mp3"})
        A.record_members_episode(tmp_path, {"episode_num": 22, "date": "2026-10-14",
                                            "audio_url": "r2-private://b/k2.mp3"})
        A.record_members_episode(tmp_path, {"episode_num": 21, "date": "2026-10-13",
                                            "audio_url": "r2-private://b/k3.mp3"})
        assert A.max_members_episode(tmp_path) == 22
        assert len(A.load_ledger(tmp_path)) == 2
        assert A.members_entry_for(tmp_path, TUESDAY)["audio_url"].endswith("k3.mp3")

    def test_artifacts_move_into_members_and_metrics_stay(self, tmp_path):
        names = ["MAG_7_Daily_Ep021_20261013.md", "MAG_7_Daily_Ep021_20261013_tts.txt",
                 "MAG_7_Daily_Ep021_20261013_transcript.json", "MAG_7_Daily_Ep021_20261013.mp3",
                 "chapters_ep021.json", "metrics_ep021.json",
                 "MAG_7_Daily_Ep020_20261012.md"]
        for n in names:
            (tmp_path / n).write_text("x")
        moved = {p.name for p in A.move_episode_artifacts(tmp_path, "MAG_7_Daily", 21, TUESDAY)}
        assert moved == set(names[:5])
        assert (tmp_path / "metrics_ep021.json").exists()
        assert (tmp_path / "MAG_7_Daily_Ep020_20261012.md").exists()
        # The public surfaces glob the top level: nothing of Ep021 is there.
        assert not list(tmp_path.glob("*Ep021*.md"))

    def test_private_reference_round_trip(self):
        ref = A.private_audio_ref("nerra-personal", A.private_audio_key("mag7", "x.mp3"))
        assert ref == "r2-private://nerra-personal/shows/mag7/x.mp3"
        assert A.parse_private_ref(ref) == ("nerra-personal", "shows/mag7/x.mp3")
        assert A.parse_private_ref("https://audio.nerranetwork.com/x.mp3") is None

    def test_private_upload_goes_to_the_private_bucket(self, monkeypatch, tmp_path):
        for env in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            monkeypatch.setenv(env, "x")
        monkeypatch.delenv("PERSONAL_R2_BUCKET", raising=False)
        mp3 = tmp_path / "MAG_7_Daily_Ep021_20261013.mp3"
        mp3.write_bytes(b"x")
        seen = {}

        def fake_upload(local, key, **kw):
            seen.update(key=key, **kw)
            return "unused"

        with mock.patch("engine.storage.upload_to_r2", fake_upload):
            ref = A.upload_private_audio(mp3, _cfg())
        assert seen["bucket"] == "nerra-personal" and seen["public_base_url"] == ""
        assert seen["key"] == "shows/mag7/MAG_7_Daily_Ep021_20261013.mp3"
        assert ref.startswith("r2-private://nerra-personal/")

    def test_no_credentials_is_a_failure_not_a_public_fallback(self, monkeypatch, tmp_path):
        monkeypatch.delenv("R2_ENDPOINT_URL", raising=False)
        assert A.upload_private_audio(tmp_path / "x.mp3", _cfg()) is None


class TestRunShowWiring:
    SRC = (ROOT / "run_show.py").read_text(encoding="utf-8")

    def test_numbering_reads_the_ledger(self):
        assert "_access.max_members_episode(digests_dir)" in self.SRC

    def test_demand_gate_comes_before_any_spend(self):
        gate = self.SRC.index('_skip_episode(\n                    "no_member_demand"')
        assert gate < self.SRC.index("# 3. Tracker")
        assert gate < self.SRC.index("# 3b. Initialize content lake")

    def test_members_stop_sits_between_rehearsal_and_publishing(self):
        rehearse = self.SRC.index("# === Rehearsal stop (--rehearse) ===")
        stop = self.SRC.index("# === Members stop (engine.access")
        publish = self.SRC.index("# === Publish & Distribution Phase ===")
        assert rehearse < stop < publish
        block = self.SRC[stop:publish]
        for needed in ("upload_private_audio", "move_episode_artifacts",
                       "record_members_episode", "write_publish_complete_marker",
                       "return"):
            assert needed in block, needed
        # Nothing public inside the members block.
        for public in ("update_rss_feed", "save_summary_to_github_pages",
                       "_publish_youtube", "post_to_x", "send_show_newsletter",
                       "run_publish_phase"):
            assert public not in block, public


class TestNoPublicSurfaceSeesIt:
    def _root(self, tmp_path, mode):
        from engine.daily_edition import EDITIONS

        (tmp_path / "shows").mkdir()
        d = tmp_path / "digests" / "mag7"
        d.mkdir(parents=True)
        (tmp_path / "shows" / "mag7.yaml").write_text("x: 1")
        A.record_members_episode(d, {
            "episode_num": 21, "date": TUESDAY.isoformat(),
            "episode_title": "Ep 21: chips", "filename": "MAG_7_Daily_Ep021_20261013.mp3",
            "audio_url": "r2-private://nerra-personal/shows/mag7/MAG_7_Daily_Ep021_20261013.mp3"})
        spec = dataclasses.replace(EDITIONS["en"], lineup=("mag7",), monday_only=frozenset(),
                                   weekday_only={})

        def loader(path):
            cfg = _cfg(mode)
            cfg.publishing = SimpleNamespace(summaries_json="digests/mag7/summaries_mag7.json")
            cfg.audio = SimpleNamespace(voice_intro_delay=0.0)
            return cfg

        return spec, loader

    def test_nerra_daily_never_splices_and_never_waits(self, tmp_path):
        from engine.daily_edition import discover_lineup

        spec, loader = self._root(tmp_path, "members_only")
        lineup = discover_lineup(spec, tmp_path, TUESDAY, config_loader=loader)
        assert lineup.segments == [] and lineup.missing == []
        assert lineup.skipped == [{"slug": "mag7", "reason": "members_only"}]

    def test_a_members_day_not_yet_produced_is_not_waited_for(self, tmp_path):
        from engine.daily_edition import discover_lineup

        spec, loader = self._root(tmp_path, "members_only")
        lineup = discover_lineup(spec, tmp_path, dt.date(2026, 10, 14), config_loader=loader)
        assert lineup.missing == [] and lineup.skipped[0]["reason"] == "members_only"

    def test_the_personal_builder_gets_it(self, tmp_path):
        from engine.daily_edition import discover_segments

        spec, loader = self._root(tmp_path, "members_only")
        segments, missing = discover_segments(spec, tmp_path, TUESDAY,
                                              config_loader=loader, include_members=True)
        assert [s.slug for s in segments] == ["mag7"]
        assert segments[0].audio_url.startswith("r2-private://")
        assert segments[0].digest_dir.name == "members"

    def test_builder_downloads_private_audio_from_r2(self):
        src = (ROOT / "scripts" / "build_personal_feeds.py").read_text(encoding="utf-8")
        assert "include_members=True" in src
        assert "parse_private_ref(seg.audio_url)" in src and ".download_file(" in src

    def test_the_rotation_never_plugs_a_members_only_show(self):
        from engine import network_promo as NP

        today = dt.date(2026, 10, 13)
        picks_before = {s: NP.pick_featured_show(s, today) for s in NP.ENGLISH_ORDER}
        gated = NP.ENGLISH_ORDER[1]
        with mock.patch("engine.access.mode_for_slug",
                        lambda slug, root=A.PROJECT_ROOT: "members_only" if slug == gated else "public"):
            for day in range(30):
                for slug in NP.ENGLISH_ORDER:
                    assert NP.pick_featured_show(slug, today + dt.timedelta(days=day)) != gated
        # With nothing gated the rotation is unchanged.
        assert {s: NP.pick_featured_show(s, today) for s in NP.ENGLISH_ORDER} == picks_before

    def test_audit_counts_a_members_episode_as_produced(self, tmp_path, monkeypatch):
        import review_episodes as R

        out = tmp_path / "digests" / "mag7"
        (out / "members").mkdir(parents=True)
        (out / "members" / "MAG_7_Daily_Ep021_20261013.md").write_text("x")
        monkeypatch.setattr(R, "PROJECT_ROOT", tmp_path)
        assert R._members_episode_exists("digests/mag7", TUESDAY)
        assert not R._members_episode_exists("digests/mag7", MONDAY)

    def test_feed_freshness_follows_access(self):
        with mock.patch.object(A, "gated_shows", lambda root=A.PROJECT_ROOT: {
                "mag7": "members_only", "ai_chips": "public_weekly"}):
            limits = A.feed_age_overrides()
        assert limits == {"mag7_podcast.rss": None,
                          "ai_chips_podcast.rss": A.PUBLIC_WEEKLY_FEED_MAX_HOURS}
        audit = (ROOT / ".github" / "workflows" / "daily-audit.yml").read_text(encoding="utf-8")
        assert "feed_age_overrides" in audit

    def test_multilingual_skips_members_days_and_members_only_shows(self):
        wf = (ROOT / ".github" / "workflows" / "multilingual.yml").read_text(encoding="utf-8")
        assert "is_public_on(cfg" in wf
        assert '"members_only"' in wf

    def test_frame_memory_reads_members_scripts(self, tmp_path):
        from engine.frame_memory import script_paths

        (tmp_path / "members").mkdir()
        (tmp_path / "S_Ep001_20261011_tts.txt").write_text("a")
        (tmp_path / "members" / "S_Ep002_20261012_tts.txt").write_text("b")
        assert [p.name for p in script_paths(tmp_path)] == [
            "S_Ep001_20261011_tts.txt", "S_Ep002_20261012_tts.txt"]

    def test_workflow_hands_the_run_its_demand_token(self):
        wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
        assert "PERSONAL_DEMAND_TOKEN: ${{ secrets.PERSONAL_DEMAND_TOKEN }}" in wf


class TestTheWorkerEndpoint:
    TS = (ROOT / "workers" / "gallery" / "src" / "personal.ts").read_text(encoding="utf-8")

    def test_routed(self):
        idx = (ROOT / "workers" / "gallery" / "src" / "index.ts").read_text(encoding="utf-8")
        assert '"GET /api/admin/show-demand"' in idx and "handleShowDemand" in idx

    def test_counts_only(self):
        body = self.TS[self.TS.index("export async function handleShowDemand"):]
        assert "{ ok: true, members, demand }" in body
        for field in ("first_name", "city", "feed_token:", "email"):
            assert f"{field}" not in body.split("return jsonResponse(request, 200")[1][:80]


class TestTheSite:
    def test_card_and_page_say_members(self, tmp_path):
        import generate_html as G

        cfg = A._config_for("mag7", str(A.PROJECT_ROOT))
        before = cfg.access.mode
        try:
            cfg.access.mode = "members_only"
            card = next(c for c in G._build_all_shows_list() if c["slug"] == "mag7")
            assert card["access"] == "members_only" and card["access_label"] == "Members only"
            G.generate_show_page("mag7", output_dir=tmp_path)
            html = (tmp_path / "mag7.html").read_text(encoding="utf-8")
            assert 'id="members-access"' in html and "join.html" in html
        finally:
            cfg.access.mode = before
        macros = (ROOT / "templates" / "_macros.html.j2").read_text(encoding="utf-8")
        assert "show-card-badge--members" in macros

    def test_public_shows_render_no_band(self, tmp_path):
        import generate_html as G

        G.generate_show_page("spacex", output_dir=tmp_path)
        assert 'id="members-access"' not in (tmp_path / "spacex.html").read_text(encoding="utf-8")
