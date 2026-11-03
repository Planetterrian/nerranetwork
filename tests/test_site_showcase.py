"""Drift guards for the site-showcase video endings (Aug 2026; data-rendered
since Nov 3 2026).

The operator asked for the end of every Short and long-form video to point
viewers at nerranetwork.com — the whole network behind the channel. Pieces
under guard:

* ``engine/promo_card.py`` — outro card + Shorts cover strip rendered from
  the show registry and ``engine.brand`` (never from a screenshot: the one
  capture ever taken shipped "ad-free" and "4 languages" on every video for
  86 days — see ``tests/test_youtube_brand_surfaces_2026_11_03.py``).
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
# The outro card renders from data
# ---------------------------------------------------------------------------

class TestOutroRendersFromData:
    """Nov 3 2026: no screenshot bytes, the brand tagline, the free-show
    count, and a card whenever PIL can draw one."""

    def test_the_module_reads_no_screenshot(self):
        src = (PROJECT_ROOT / "engine" / "promo_card.py").read_text(encoding="utf-8")
        assert "site_screens" not in src.split('"""', 2)[2], (
            "promo_card composites a committed screenshot again")
        assert "SCREENS_DIR" not in src.split('"""', 2)[2]
        assert "render_short_site_strip" not in src

    def test_headline_is_the_brand_tagline_per_channel(self):
        from engine import brand, promo_card

        assert promo_card._texts("en")["headline"] == brand.NETWORK_TAGLINE
        assert promo_card._texts("ru")["headline"] == brand.NETWORK_TAGLINE_RU
        assert promo_card._texts("fr")["headline"] == brand.NETWORK_TAGLINE_FR
        assert promo_card._texts("zz")["headline"] == brand.NETWORK_TAGLINE

    def test_sub_line_carries_the_free_show_count(self):
        from engine import promo_card
        import generate_html

        count = len(generate_html._public_shows())
        assert count > 0
        assert promo_card._texts("en")["sub"].startswith(f"All {count} free shows")

    def test_show_wall_is_free_shows_flagships_first(self):
        from engine import brand, promo_card
        import generate_html

        wall = promo_card.show_wall()
        slugs = [r["slug"] for r in wall]
        assert slugs[:len(brand.FLAGSHIP_SHOW_SLUGS)] == list(brand.FLAGSHIP_SHOW_SLUGS)
        public = {s["slug"] for s in generate_html._public_shows()}
        assert set(slugs) <= public
        assert all(r["cover"].startswith("assets/covers/") for r in wall)
        assert "tesla" not in [r["slug"] for r in promo_card.show_wall(exclude_slug="tesla")]

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

    def test_the_show_tile_is_this_shows_cover(self, tmp_path):
        """The left tile is the show's own cover, pixel for pixel."""
        from engine import promo_card
        from engine.share_cards import _cover_fill, _inset, _open
        from PIL import Image
        import numpy as np

        out = promo_card.generate_outro_card(
            tmp_path / "tesla.png", show_slug="tesla", show_name="Tesla Shorts Time")
        card = np.asarray(Image.open(out).convert("RGB"), dtype=float)
        me = promo_card.show_entry("tesla")
        expect = np.asarray(_cover_fill(_inset(_open(me["cover"])), (548, 548)), dtype=float)
        x0, y0 = 200, 205  # the tile slot (margin 160 + 40, band_y)
        inner = (slice(60, 488), slice(60, 488))  # clear of the rounded corners
        got = card[y0:y0 + 548, x0:x0 + 548][inner]
        assert float(abs(got - expect[inner]).mean()) < 1.0

    def test_a_missing_cover_still_renders_a_card(self, tmp_path, monkeypatch):
        """Never ``None`` while PIL can draw: no cover → the wall and the
        copy; no registry at all → the typographic card."""
        from engine import promo_card

        monkeypatch.setattr(promo_card, "show_entry", lambda slug: {
            "slug": slug, "name": "Ghost", "cover": "assets/covers/does-not-exist.jpg",
            "brand_color": "#123456"})
        out = promo_card.generate_outro_card(tmp_path / "ghost.png", show_slug="ghost")
        assert out is not None and out.exists()

        monkeypatch.setattr(promo_card, "show_wall", lambda exclude_slug="": [])
        monkeypatch.setattr(promo_card, "show_entry", lambda slug: None)
        out = promo_card.generate_outro_card(tmp_path / "bare.png", show_slug="ghost")
        assert out is not None and out.exists()

    def test_outro_card_survives_missing_qrcode(self, tmp_path, monkeypatch):
        """No qrcode package → card still renders, just without a QR."""
        from engine import promo_card

        monkeypatch.setattr(promo_card, "_qr_image", lambda *a, **k: None)
        out = promo_card.generate_outro_card(
            tmp_path / "card.png", show_slug="spacex",
            link_url="https://nerranetwork.com/x")
        assert out is not None and out.exists()

    def test_short_site_panel_is_a_cover_strip(self):
        from engine import promo_card
        from PIL import Image

        panel = promo_card.short_site_panel("tesla", "en")
        assert panel is not None and panel.exists()
        assert Image.open(panel).size == promo_card.SHORT_STRIP_SIZE
        # The same picture serves every channel — and the second call is cached.
        assert promo_card.short_site_panel("tesla", "ru") == panel


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
        from engine.promo_card import short_site_panel
        from PIL import Image
        import numpy as np

        cover = self._cover(tmp_path)
        plain = tmp_path / "plain.png"
        with_site = tmp_path / "site.png"
        generate_shorts_end_card(cover, plain, show_name="Test")
        generate_shorts_end_card(cover, with_site, show_name="Test",
                                 site_image_path=short_site_panel("tesla", "en"))
        a = np.asarray(Image.open(plain).convert("RGB"), dtype=float)
        b = np.asarray(Image.open(with_site).convert("RGB"), dtype=float)
        assert a.shape == b.shape == (1920, 1080, 3)
        # The strip band must actually contain the cover strip.
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
        # Nov 3 2026: 3 s, so YouTube's own end screen (Studio) has its
        # 5-20 s over the closing — END_SCREEN traffic was 1 view in 90 days.
        assert cfg.youtube.outro_card_duration_seconds == pytest.approx(3.0)

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
