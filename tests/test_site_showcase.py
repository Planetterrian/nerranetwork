"""Drift guards for the site-showcase video endings (Aug 2026).

The operator asked for the end of every Short and long-form video to
show nerranetwork.com — the show page and the whole-network page — so
viewers see the site (all shows, transcripts, newsletters) behind the
channel. Pieces under guard:

* ``engine/promo_card.py`` — outro card + Shorts site strip composited
  from COMMITTED screenshots (``assets/site_screens/``).
* ``engine/funnel.py`` — ``PLACEMENT_OUTRO`` in the closed placement
  vocabulary (QR scans separable from Shorts end-card taps in GA4).
* ``engine/video.py`` — outro overlay threaded through BOTH long-form
  command builders; absent args keep the legacy command byte-for-byte.
* ``engine/publisher.generate_shorts_end_card`` — optional site strip.
* Config knobs + wiring in run_show / ru_dub / lang_dub.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Funnel placement
# ---------------------------------------------------------------------------

class TestOutroPlacement:
    def test_outro_in_closed_vocabulary(self):
        from engine import funnel

        assert funnel.PLACEMENT_OUTRO == "outro"
        assert funnel.PLACEMENT_OUTRO in funnel.PLACEMENTS

    def test_episode_link_carries_outro_content(self):
        from engine import funnel

        url = funnel.episode_link(
            "https://nerranetwork.com/spacex.html", "spacex", 59,
            channel="ru", kind="long", placement=funnel.PLACEMENT_OUTRO)
        assert "utm_content=outro" in url
        # The campaign must still round-trip exactly.
        campaign = re.search(r"utm_campaign=([^&]+)", url).group(1)
        parsed = funnel.parse_campaign_id(campaign)
        assert parsed is not None
        assert (parsed.show, parsed.channel, parsed.kind, parsed.episode) == (
            "spacex", "ru", "long", 59)


# ---------------------------------------------------------------------------
# Committed screenshots + promo card
# ---------------------------------------------------------------------------

class TestScreenshotAssets:
    def test_committed_screenshots_exist(self):
        screens = PROJECT_ROOT / "assets" / "site_screens"
        for name in ("network_home", "show_spacex", "show_tesla",
                     "show_fascinating_frontiers", "ru_spacex"):
            assert (screens / f"{name}.png").exists(), (
                f"assets/site_screens/{name}.png missing — the outro/"
                "end-card showcase composites from committed screenshots; "
                "run scripts/capture_site_screens.py")

    def test_capture_script_exists(self):
        assert (PROJECT_ROOT / "scripts" / "capture_site_screens.py").exists()


class TestPromoCard:
    def test_screenshot_resolution_priority(self):
        from engine import promo_card

        # RU channel prefers the RU lander for spacex…
        assert promo_card.site_screenshot_for("spacex", "ru").name == \
            "ru_spacex.png"
        # …EN gets the show page; a show without a page gets None.
        assert promo_card.site_screenshot_for("spacex", "en").name == \
            "show_spacex.png"
        assert promo_card.site_screenshot_for("dp_pod", "en") is None

    def test_outro_card_renders_all_channels(self, tmp_path):
        from engine.promo_card import generate_outro_card
        from PIL import Image

        for channel in ("en", "ru", "fr"):
            out = generate_outro_card(
                tmp_path / f"card_{channel}.png",
                show_slug="spacex", show_name="SpaceX Daily",
                channel=channel,
                link_url="https://nerranetwork.com/spacex.html?utm_source=x")
            assert out is not None and out.exists()
            assert Image.open(out).size == (1920, 1080)

    def test_outro_card_none_without_screenshots(self, tmp_path, monkeypatch):
        from engine import promo_card

        monkeypatch.setattr(promo_card, "SCREENS_DIR", tmp_path / "nope")
        out = promo_card.generate_outro_card(
            tmp_path / "card.png", show_slug="spacex")
        assert out is None

    def test_outro_card_survives_missing_qrcode(self, tmp_path, monkeypatch):
        """No qrcode package → card still renders, just without a QR."""
        from engine import promo_card

        monkeypatch.setattr(promo_card, "_qr_image", lambda *a, **k: None)
        out = promo_card.generate_outro_card(
            tmp_path / "card.png", show_slug="spacex",
            link_url="https://nerranetwork.com/x")
        assert out is not None and out.exists()

    def test_short_site_panel_defaults_to_network_home(self):
        from engine.promo_card import short_site_panel

        assert short_site_panel("tesla", "en").name == "network_home.png"
        # RU lander wins for the show that has one.
        assert short_site_panel("spacex", "ru").name == "ru_spacex.png"


# ---------------------------------------------------------------------------
# Long-form render wiring
# ---------------------------------------------------------------------------

class TestLongFormOutroOverlay:
    def _graph(self, cmd):
        return cmd[cmd.index("-filter_complex") + 1]

    def test_two_pass_cmd_overlays_outro(self):
        from engine.video import _long_form_cmd

        cmd = _long_form_cmd(
            "a.mp3", "bg.png", "brand.png", "out.mp4",
            outro_card_in="outro.png", total_duration=300.0,
            outro_duration=6.0)
        graph = self._graph(cmd)
        assert "[outrocard]" in graph
        assert "enable='between(t,294.00,300.00)'" in graph
        assert "fade=t=in:st=294.00" in graph
        assert cmd[cmd.index("-map") + 1] == "[vout]"
        assert "outro.png" in cmd

    def test_two_pass_cmd_legacy_without_outro(self):
        from engine.video import _long_form_cmd

        cmd = _long_form_cmd("a.mp3", "bg.png", "brand.png", "out.mp4")
        graph = self._graph(cmd)
        assert "outrocard" not in graph
        assert cmd[cmd.index("-map") + 1] == "[v]"

    def test_two_pass_outro_needs_duration(self):
        """No total duration → no window to place → legacy graph."""
        from engine.video import _long_form_cmd

        cmd = _long_form_cmd(
            "a.mp3", "bg.png", "brand.png", "out.mp4",
            outro_card_in="outro.png", total_duration=0.0)
        assert "outrocard" not in self._graph(cmd)

    def test_two_pass_chapter_metadata_index_shifts(self):
        """The ffmetadata input must stay LAST; its -map_metadata index
        follows the extra outro input."""
        from engine.video import _long_form_cmd

        cmd = _long_form_cmd(
            "a.mp3", "bg.png", "brand.png", "out.mp4",
            url_pill_in="pill.png", chapter_metadata_in="ch.ffmeta",
            outro_card_in="outro.png", total_duration=300.0)
        # bg(0) audio(1) brand(2) pill(3) outro(4) → metadata is input 5.
        assert cmd[cmd.index("-map_metadata") + 1] == "5"

    def test_single_pass_cmd_overlays_outro(self):
        from engine.video import _single_pass_long_form_cmd

        scenes = [Path("s1.png"), Path("s2.png")]
        cmd = _single_pass_long_form_cmd(
            scenes, "a.mp3", "brand.png", "out.mp4",
            scene_durations=[10.0, 10.0],
            outro_card_in="outro.png", total_duration=300.0,
            outro_duration=6.0)
        graph = self._graph(cmd)
        assert "[outrocard]" in graph
        assert cmd[cmd.index("-map") + 1] == "[vout]"
        # scenes(0..1) audio(2) brand(3) → outro is input 4.
        assert "[4:v]format=rgba" in graph

    def test_single_pass_cmd_legacy_without_outro(self):
        from engine.video import _single_pass_long_form_cmd

        scenes = [Path("s1.png"), Path("s2.png")]
        cmd = _single_pass_long_form_cmd(
            scenes, "a.mp3", "brand.png", "out.mp4",
            scene_durations=[10.0, 10.0])
        assert "outrocard" not in self._graph(cmd)
        assert cmd[cmd.index("-map") + 1] == "[v]"

    def test_build_long_form_video_accepts_outro_kwargs(self):
        import inspect
        from engine.video import build_long_form_video

        params = inspect.signature(build_long_form_video).parameters
        assert "outro_card_path" in params
        assert "outro_card_duration" in params


# ---------------------------------------------------------------------------
# Shorts end-card site strip
# ---------------------------------------------------------------------------

class TestShortsEndCardSitePanel:
    def _cover(self, tmp_path):
        from PIL import Image

        cover = tmp_path / "thumb.png"
        Image.new("RGB", (1280, 720), (40, 40, 60)).save(cover)
        return cover

    def test_site_panel_changes_card(self, tmp_path):
        from engine.publisher import generate_shorts_end_card
        from engine.promo_card import network_screenshot
        from PIL import Image
        import numpy as np

        cover = self._cover(tmp_path)
        plain = tmp_path / "plain.png"
        with_site = tmp_path / "site.png"
        generate_shorts_end_card(cover, plain, show_name="Test")
        generate_shorts_end_card(cover, with_site, show_name="Test",
                                 site_image_path=network_screenshot())
        a = np.asarray(Image.open(plain).convert("RGB"), dtype=float)
        b = np.asarray(Image.open(with_site).convert("RGB"), dtype=float)
        assert a.shape == b.shape == (1920, 1080, 3)
        # The strip band must actually contain the screenshot.
        band = slice(int(1920 * 0.785), int(1920 * 0.785) + 260)
        assert float(abs(a[band] - b[band]).mean()) > 1.0

    def test_bad_site_image_keeps_legacy_card(self, tmp_path):
        from engine.publisher import generate_shorts_end_card
        from PIL import Image
        import numpy as np

        cover = self._cover(tmp_path)
        plain = tmp_path / "plain.png"
        broken = tmp_path / "broken.png"
        generate_shorts_end_card(cover, plain, show_name="Test")
        generate_shorts_end_card(cover, broken, show_name="Test",
                                 site_image_path=tmp_path / "missing.png")
        a = np.asarray(Image.open(plain).convert("RGB"))
        b = np.asarray(Image.open(broken).convert("RGB"))
        assert (a == b).all(), "failed site strip must ship the legacy card"


# ---------------------------------------------------------------------------
# Config + wiring
# ---------------------------------------------------------------------------

class TestConfigAndWiring:
    def test_youtube_config_declares_knobs(self):
        from engine.config import YouTubeConfig

        cfg = YouTubeConfig()
        assert cfg.outro_card_enabled is True
        assert cfg.outro_card_duration_seconds == pytest.approx(6.0)
        assert cfg.shorts_end_card_site_panel is True

    def test_defaults_yaml_carries_knobs(self):
        from engine.config import load_config

        cfg = load_config(PROJECT_ROOT / "shows" / "tesla.yaml")
        assert cfg.youtube.outro_card_enabled is True
        assert cfg.youtube.shorts_end_card_site_panel is True

    def test_run_show_wires_outro_and_panel(self):
        src = (PROJECT_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "generate_outro_card" in src
        assert "outro_card_path=_outro_card_path" in src
        assert "PLACEMENT_OUTRO" in src
        assert "short_site_panel" in src
        assert "site_image_path=_site_panel" in src

    def test_dub_modules_wire_outro_and_panel(self):
        for name in ("ru_dub", "lang_dub"):
            src = (PROJECT_ROOT / "engine" / f"{name}.py").read_text(
                encoding="utf-8")
            assert "generate_outro_card" in src, name
            assert "PLACEMENT_OUTRO" in src, name
            assert "short_site_panel" in src, name
            assert "outro_card_path=outro_card" in src, name

    def test_qrcode_in_requirements(self):
        req = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
        assert "qrcode" in req
