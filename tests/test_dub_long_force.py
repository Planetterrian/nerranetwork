"""Drift guards: operator-directed dub long-form probe + Shorts progress
bar (Aug 2026).

The operator wants long-form on @NerraRU and @NerraFR for the three most
popular shows (tesla, spacex, fascinating_frontiers) ALONGSIDE the
existing Shorts system. Mechanism: ``youtube.dub_force_long_channels``
pins ``publish_long`` True after policy resolution while the Shorts
supply ladder stays exactly what the policy computes. This deliberately
overrides the July RU long-form demotion (~9% retention) — registered as
``dub-long-form-probe`` in docs/experiments.yaml with a 2026-08-21
readout, so it gets read, not forgotten.
"""

from __future__ import annotations

from pathlib import Path

from engine.config import load_config
from engine.youtube_policy import resolve_publish_plan

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_POLICY = {
    "channels": {
        "ru": {
            "spacex": {"tier": "C", "publish_long_form": False,
                       "shorts_per_episode": 3, "short_vpd": 52.5,
                       "reason": "computed C"},
        },
    },
}


class TestForceLongResolution:
    def test_force_long_overrides_tier_but_not_shorts(self):
        plan = resolve_publish_plan(
            _POLICY, slug="spacex", channel="ru",
            yaml_publish_long=True, yaml_shorts=1, smart_mode=True,
            adaptive_enabled=True, force_long=True,
            probe_today=__import__("datetime").date(2026, 8, 7),  # a Friday
        )
        assert plan["publish_long"] is True
        assert plan["shorts"] == 3  # the supply ladder is untouched
        assert "override" in plan["reason"]

    def test_without_force_tier_c_stays_shorts_only(self):
        plan = resolve_publish_plan(
            _POLICY, slug="spacex", channel="ru",
            yaml_publish_long=True, yaml_shorts=1, smart_mode=True,
            adaptive_enabled=True,
            probe_today=__import__("datetime").date(2026, 8, 7),
        )
        assert plan["publish_long"] is False

    def test_force_long_noop_when_policy_already_long(self):
        policy = {"channels": {"ru": {"spacex": {
            "tier": "A", "publish_long_form": True,
            "shorts_per_episode": 2}}}}
        plan = resolve_publish_plan(
            policy, slug="spacex", channel="ru",
            yaml_publish_long=True, yaml_shorts=1, smart_mode=True,
            adaptive_enabled=True, force_long=True,
        )
        assert plan["publish_long"] is True
        assert "override" not in plan["reason"]


class TestBigThreeYamlFlags:
    def test_big_three_no_longer_force_dub_longs(self):
        """Probe ENDED 2026-08-15 per its own exit rule: ru_long_vpd 1.52
        vs the 2.0 floor, 52 forced longs at ~9 views/video, net -2 subs
        (the July demotion numbers repeated). The flags are gone and the
        adaptive policy decides again — re-adding one re-opens a negative
        experiment (see docs/experiments.yaml dub-long-form-probe)."""
        for slug in ("tesla", "spacex", "fascinating_frontiers"):
            cfg = load_config(PROJECT_ROOT / "shows" / f"{slug}.yaml")
            chans = list(getattr(cfg.youtube, "dub_force_long_channels", []))
            assert chans == [], (slug, chans)

    def test_other_dub_show_not_forced(self):
        cfg = load_config(PROJECT_ROOT / "shows" / "modern_investing.yaml")
        assert list(getattr(cfg.youtube, "dub_force_long_channels", [])) == []

    def test_dataclass_default_empty(self):
        from engine.config import YouTubeConfig
        assert YouTubeConfig().dub_force_long_channels == []


class TestDubEngineWiring:
    def test_ru_dub_passes_force_long(self):
        src = (PROJECT_ROOT / "engine" / "ru_dub.py").read_text()
        assert "force_long=" in src
        assert "dub_force_long_channels" in src

    def test_lang_dub_passes_force_long(self):
        src = (PROJECT_ROOT / "engine" / "lang_dub.py").read_text()
        assert "force_long=" in src
        assert "dub_force_long_channels" in src


class TestExperimentRegistered:
    def test_probe_in_registry_with_readout(self):
        import yaml
        data = yaml.safe_load(
            (PROJECT_ROOT / "docs" / "experiments.yaml").read_text())
        by_id = {e["id"]: e for e in data["experiments"]}
        e = by_id["dub-long-form-probe"]
        assert e["status"] == "done" and "NEGATIVE" in e.get("criteria", "")
        # Registered with a readout; its status moves as it is read
        # (closed 'done' 2026-09-02 once the readout date passed).
        assert by_id["shorts-progress-bar"]["status"] in ("reading", "done")
        assert by_id["shorts-progress-bar"].get("readout")


class TestShortsProgressBar:
    def test_graph_contains_slide_in_overlay_when_enabled(self):
        """The animation MUST be the overlay slide-in, not drawbox — the
        production ffmpeg builds evaluate drawbox's width once (verified:
        a t-expression painted a static full-width bar), while overlay's
        x is per-frame (eval=frame default)."""
        from engine.video import _short_form_filter_graph
        g = _short_form_filter_graph(total_duration=35.0, progress_bar=True)
        assert "color=c=0x00D4FF" in g and "[pbsrc]" in g
        assert "overlay=x='-w+w*min(t/35.00,1)'" in g
        assert "shortest=1[pbar]" in g
        assert "drawbox" not in g.split("[pbar]")[0].split("[pbsrc]")[-1]

    def test_graph_unchanged_when_disabled(self):
        from engine.video import _short_form_filter_graph
        g = _short_form_filter_graph(total_duration=35.0, progress_bar=False)
        assert "[pbar]" not in g

    def test_bar_renders_under_hook_and_captions(self):
        """The bar must be drawn BEFORE hook/captions so later overlays
        stack above it (and the end card covers it in the last seconds)."""
        from engine.video import _short_form_filter_graph
        g = _short_form_filter_graph(
            total_duration=35.0, progress_bar=True, hook="Big news today",
            subtitles_path="/tmp/x.ass")
        assert g.index("[pbar]") < g.index("subtitles")

    def test_run_show_honors_optout_knob(self):
        src = (PROJECT_ROOT / "run_show.py").read_text()
        assert "shorts_progress_bar" in src

    def test_config_default_on(self):
        from engine.config import YouTubeConfig
        assert YouTubeConfig().shorts_progress_bar is True
