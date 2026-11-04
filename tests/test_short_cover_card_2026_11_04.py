"""Nov 4 2026 — a Short never crops the show's title off its own cover.

AI Chips & Data Centres Daily Ep044's X clip shipped "AI CHIPS",
"DATA CENTRES", "THE NERRA NETWORK" and the tagline row cut off at both
edges: every show cover is square, and the Shorts cover fallback (the X-only
clip always, and any Short with no scene images) scaled it to FILL 1080x1920
and centre-cropped 44% of its width away. The opening hook then sat on the
cover's tagline row. These guards pin the fix for every show:

* the cover becomes a vertical card that holds ALL of it, inside the
  margin the cover push-in (zoom <= 1.08) never reaches;
* the opening hook moves below the cover on a card;
* the Shorts show pill grows to hold a long show name and never reaches the
  subscribe pill on the same row.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engine import video as V

ROOT = Path(__file__).resolve().parents[1]
SHOWS = ROOT / "shows"


def _show_configs():
    out = []
    for y in sorted(SHOWS.glob("*.yaml")):
        if y.stem.startswith("_") or y.stem == "network_meta":
            continue
        data = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict) or not data.get("name"):
            continue
        out.append((y.stem, data))
    return out


def _cover_for(stem: str, data: dict):
    covers = ROOT / "assets" / "covers"
    slug = str(data.get("slug") or stem)
    cands = [covers / f"{slug.replace('_', '-')}.jpg", covers / f"{slug}.jpg"]
    rss = str(((data.get("publishing") or {}).get("rss_image")) or "")
    if rss:
        cands.append(covers / rss.rstrip("/").rsplit("/", 1)[-1])
    return next((c for c in cands if c.exists()), None)


SHOW_COVERS = [
    (stem, c) for stem, d in _show_configs()
    if (c := _cover_for(stem, d)) is not None
]


def test_every_show_has_a_cover_under_test():
    assert len(SHOW_COVERS) >= 20


class TestCoverCard:

    def test_card_geometry_survives_the_push_in(self):
        # The cover fallback zooms to 1.08 at most: the visible width is
        # 1080/1.08 = 1000 px, so the cover must be narrower than that.
        assert V._COVER_CARD_SIDE_FRAC * 1080 <= 1080 / 1.08
        top = V._COVER_CARD_TOP_FRAC * 1920
        bottom = top + V._COVER_CARD_SIDE_FRAC * 1080
        visible_top = (1920 - 1920 / 1.08) / 2
        assert top > max(84, visible_top)  # below the corner pills
        # Above the opening hook block (4 lines ~ +/-108 px at 54 px/line).
        assert bottom < V._COVER_CARD_HOOK_Y_FRAC * 1920 - 4 * 54 / 2 + 1

    @pytest.mark.parametrize("stem,cover", SHOW_COVERS,
                             ids=[s for s, _ in SHOW_COVERS])
    def test_every_cover_becomes_a_whole_cover_card(self, stem, cover, tmp_path):
        from PIL import Image
        out = V._vertical_cover_card(cover, tmp_path / "card.png")
        assert out is not None, f"{stem}: square cover got no card"
        with Image.open(out) as card:
            assert card.size == (1080 * V._COVER_CARD_SCALE,
                                 1920 * V._COVER_CARD_SCALE)

    def test_portrait_still_keeps_fill_and_crop(self, tmp_path):
        from PIL import Image
        src = tmp_path / "tall.png"
        Image.new("RGB", (900, 1600), (10, 20, 30)).save(src)
        assert V._vertical_cover_card(src, tmp_path / "card.png") is None

    def test_unreadable_cover_never_raises(self, tmp_path):
        src = tmp_path / "cover.jpg"
        src.write_bytes(b"\xFF\xD8")
        assert V._vertical_cover_card(src, tmp_path / "card.png") is None

    def test_builder_uses_the_card_and_moves_the_hook(self, tmp_path, monkeypatch):
        from PIL import Image
        cover = tmp_path / "cover.jpg"
        Image.new("RGB", (600, 600), (40, 60, 90)).save(cover)
        audio = tmp_path / "voice.mp3"
        audio.write_bytes(b"\x00")
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            return type("R", (), {"returncode": 0})()

        monkeypatch.setattr("engine.video.subprocess.run", fake_run)
        V.build_short_video(audio, cover, tmp_path / "short.mp4",
                            duration=30.0, hook="A hook that opens the Short",
                            show_name="AI Chips & Data Centres Daily")
        cmd = seen["cmd"]
        bg = cmd[cmd.index("-i") + 1]
        assert Path(bg).name.startswith("_cover_card_v1_")
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "y=h*0.62" in graph and "y=h*0.55" not in graph

    def test_cover_in_a_scene_list_is_swapped_for_the_card(self, tmp_path, monkeypatch):
        from PIL import Image
        cover = tmp_path / "cover.jpg"
        Image.new("RGB", (600, 600), (40, 60, 90)).save(cover)
        audio = tmp_path / "voice.mp3"
        audio.write_bytes(b"\x00")
        seen = {}

        def fake_slides(scenes, out, **kw):
            seen["scenes"] = list(scenes)
            Path(out).write_bytes(b"\x00")

        monkeypatch.setattr(V, "_render_slideshow", fake_slides)
        monkeypatch.setattr("engine.video.subprocess.run",
                            lambda cmd, **kw: type("R", (), {"returncode": 0})())
        other = tmp_path / "scene.png"
        Image.new("RGB", (900, 1600)).save(other)
        V.build_short_video(audio, cover, tmp_path / "short.mp4",
                            duration=30.0, scene_paths=[cover, other])
        assert Path(cover) not in [Path(p) for p in seen["scenes"]]

    def test_graph_is_byte_identical_without_a_card(self):
        assert (V._short_form_filter_graph(hook="A hook")
                == V._short_form_filter_graph(hook="A hook", cover_card=False))
        assert "h*0.55" in V._short_form_filter_graph(hook="A hook")


class TestShowPillFits:

    @pytest.mark.parametrize("stem,data", _show_configs(),
                             ids=[s for s, _ in _show_configs()])
    def test_show_pill_clears_the_subscribe_pill(self, stem, data, tmp_path):
        from PIL import Image, ImageFont
        from engine.cadence import episodes_phrase
        out = tmp_path / "pill.png"
        V._make_show_pill(data["name"], out, max_width=V._SHORT_SHOW_PILL_MAX_W)
        with Image.open(out) as pill:
            pill_w = pill.size[0]
        assert 320 <= pill_w <= V._SHORT_SHOW_PILL_MAX_W
        text = "Subscribe · " + episodes_phrase(str(data.get("slug") or stem))
        font = ImageFont.truetype(V._find_font(), V._SUBSCRIBE_PILL_FONTSIZE)
        bb = font.getbbox(text)
        sub_right = 38 + (bb[2] - bb[0]) + 2 * 14
        assert sub_right + 12 <= 1080 - 24 - pill_w, (stem, pill_w, sub_right)

    def test_long_name_grows_the_pill(self, tmp_path):
        from PIL import Image
        out = tmp_path / "pill.png"
        V._make_show_pill("AI Chips & Data Centres Daily", out,
                          max_width=V._SHORT_SHOW_PILL_MAX_W)
        with Image.open(out) as pill:
            assert pill.size[0] > 320

    def test_long_form_pill_unchanged(self, tmp_path):
        from PIL import Image
        out = tmp_path / "pill.png"
        V._make_show_pill("AI Chips & Data Centres Daily", out)
        with Image.open(out) as pill:
            assert pill.size == (320, 60)
