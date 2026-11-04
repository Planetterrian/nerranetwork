"""YouTube brand surfaces that cannot age (Nov 3 2026).

The last six seconds of every long-form and the strip on every Short's end
card composited COMMITTED screenshots of the site; the one capture ever
taken (Aug 9 2026) showed "ad-free", "4 languages" and 16 tiles on every
video for 86 days, the sponsor guard sweeps text so a PNG escaped it, and
the monthly capture workflow's Nov 1 run was green with nothing committed.
The live @NerraNetwork banner carried the same retired claims because its
text was typed into a build script nobody re-ran.

What binds now:

* the outro card and the Shorts strip render from the show registry and
  ``engine.brand`` — nothing under ``assets/site_screens`` is opened;
* the burned card is 3 s, so YouTube's own end screen has room;
* the capture script exits non-zero when it captures nothing, and the
  workflow refuses a run that changed no file;
* the three channel banners are written from ``engine.brand`` by
  ``scripts/build_youtube_banners.py`` and the committed SVGs are what it
  writes; the channel copy doc carries the same strings
  (``tests/test_sponsor_ready_2026_10_11.py::TestYouTubeChannelCopy`` sweeps
  both for the retired vocabulary).
"""
from __future__ import annotations

import io
import sys
import types
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


# ---------------------------------------------------------------------------
# 1. The cards open no screenshot
# ---------------------------------------------------------------------------

class TestTheCardsRenderFromData:
    def test_outro_card_opens_no_screenshot(self, tmp_path, monkeypatch):
        from PIL import Image
        from engine import promo_card

        opened = []
        real_open = Image.open

        def spy(fp, *a, **k):
            opened.append(str(fp))
            return real_open(fp, *a, **k)

        monkeypatch.setattr(Image, "open", spy)
        out = promo_card.generate_outro_card(
            tmp_path / "card.png", show_slug="tesla", show_name="Tesla Shorts Time",
            link_url="https://nerranetwork.com/tesla.html?utm_source=youtube")
        assert out is not None
        assert opened, "the card drew no cover at all"
        assert not [p for p in opened if "site_screens" in p], opened
        assert all("assets/covers/" in p for p in opened), opened

    def test_shorts_strip_opens_no_screenshot(self, monkeypatch):
        from PIL import Image
        from engine import promo_card

        promo_card._STRIP_CACHE.clear()
        opened = []
        real_open = Image.open

        def spy(fp, *a, **k):
            opened.append(str(fp))
            return real_open(fp, *a, **k)

        monkeypatch.setattr(Image, "open", spy)
        panel = promo_card.short_site_panel("spacex", "en")
        assert panel is not None
        assert not [p for p in opened if "site_screens" in p], opened
        assert len([p for p in opened if "assets/covers/" in p]) >= 9, opened
        assert Image.open(panel).size == promo_card.SHORT_STRIP_SIZE

    def test_strip_tiles_are_the_other_shows_covers(self):
        """First tile = the first flagship that is not this show."""
        from engine import brand, promo_card
        from engine.share_cards import _cover_fill, _inset, _open
        import numpy as np

        promo_card._STRIP_CACHE.clear()
        wall = promo_card.show_wall(exclude_slug="tesla")
        assert wall[0]["slug"] == [s for s in brand.FLAGSHIP_SHOW_SLUGS if s != "tesla"][0]
        strip = promo_card.render_short_cover_strip([r["cover"] for r in wall])
        strip_px = np.asarray(strip, dtype=float)
        # Geometry as the renderer lays it out: 7 columns, 2 rows, 10 px gaps.
        w, h = promo_card.SHORT_STRIP_SIZE
        tile = min((w - 6 * 10) // 7, (h - 10) // 2)
        x0 = (w - (7 * tile + 60)) // 2
        y0 = (h - (2 * tile + 10)) // 2
        expect = np.asarray(_cover_fill(_inset(_open(wall[0]["cover"])), (tile, tile)), dtype=float)
        inner = (slice(20, tile - 20), slice(20, tile - 20))
        got = strip_px[y0:y0 + tile, x0:x0 + tile][inner]
        assert float(abs(got - expect[inner]).mean()) < 1.0

    def test_publisher_pastes_the_panel_without_the_retired_cropper(self):
        src = (ROOT / "engine" / "publisher.py").read_text(encoding="utf-8")
        assert "render_short_site_strip" not in src
        assert "SHORT_STRIP_SIZE" in src

    def test_nothing_else_reads_the_screenshot_dir(self):
        """The screenshots have no render consumer; a new one must be deliberate."""
        hits = []
        for path in list((ROOT / "engine").glob("*.py")) + [ROOT / "run_show.py"]:
            src = path.read_text(encoding="utf-8")
            if path.name == "promo_card.py":  # its docstring tells the history
                src = src.split('"""', 2)[2]
            if "site_screens" in src:
                hits.append(path.name)
        assert hits == [], hits


# ---------------------------------------------------------------------------
# 2. The burned card is 3 s
# ---------------------------------------------------------------------------

class TestTheOutroIsThreeSeconds:
    def test_network_default(self):
        data = yaml.safe_load((ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert float(data["youtube"]["outro_card_duration_seconds"]) == pytest.approx(3.0)

    def test_every_render_path_reads_the_yaml_value(self):
        for name in ("run_show.py", "engine/ru_dub.py", "engine/lang_dub.py"):
            src = (ROOT / name).read_text(encoding="utf-8")
            assert "outro_card_duration_seconds" in src, name

    def test_the_long_form_end_guard_is_unchanged(self):
        src = (ROOT / "engine" / "video.py").read_text(encoding="utf-8")
        assert "outro_total > outro_card_duration + 10.0" in src


# ---------------------------------------------------------------------------
# 3. The capture fails loudly
# ---------------------------------------------------------------------------

def _fake_playwright(monkeypatch, *, goto_raises: bool):
    """A playwright double whose page either screenshots or fails."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1280, 1500), (20, 20, 40)).save(buf, format="PNG")
    png = buf.getvalue()

    class _Page:
        def goto(self, url, **k):
            if goto_raises:
                raise RuntimeError("net::ERR_TIMED_OUT")

        def evaluate(self, js):
            return None

        def screenshot(self, **k):
            return png

    class _Ctx:
        def add_init_script(self, js):
            return None

        def new_page(self):
            return _Page()

    class _Browser:
        def new_context(self, **k):
            return _Ctx()

        def close(self):
            return None

    class _Chromium:
        def launch(self):
            return _Browser()

    class _PW:
        chromium = _Chromium()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    api = types.ModuleType("playwright.sync_api")
    api.sync_playwright = lambda: _PW()
    pkg = types.ModuleType("playwright")
    pkg.sync_api = api
    monkeypatch.setitem(sys.modules, "playwright", pkg)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", api)


class TestTheCaptureFailsLoudly:
    def _mod(self, monkeypatch):
        import capture_site_screens as mod

        monkeypatch.setattr(mod.time, "sleep", lambda s: None)
        return mod

    def test_zero_pages_captured_is_non_zero(self, tmp_path, monkeypatch, capsys):
        mod = self._mod(monkeypatch)
        _fake_playwright(monkeypatch, goto_raises=True)
        assert mod.capture(out_dir=tmp_path) != 0
        out = capsys.readouterr().out
        assert "::error::" in out and "::warning::" in out
        assert not list(tmp_path.glob("*.png"))

    def test_a_captured_page_is_written_and_exits_zero(self, tmp_path, monkeypatch):
        mod = self._mod(monkeypatch)
        _fake_playwright(monkeypatch, goto_raises=False)
        assert mod.capture(only="network_home", out_dir=tmp_path) == 0
        assert (tmp_path / "network_home.png").exists()

    def test_missing_playwright_is_non_zero(self, tmp_path, monkeypatch, capsys):
        mod = self._mod(monkeypatch)
        monkeypatch.setitem(sys.modules, "playwright", None)
        monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
        assert mod.capture(out_dir=tmp_path) != 0
        assert "::error::" in capsys.readouterr().out

    def test_the_workflow_refuses_a_run_that_changed_nothing(self):
        wf = yaml.safe_load((ROOT / ".github" / "workflows" / "capture-site-screens.yml")
                            .read_text(encoding="utf-8"))
        steps = wf["jobs"]["capture"]["steps"]
        names = [s.get("name", "") for s in steps]
        i_capture = next(i for i, s in enumerate(steps)
                         if "capture_site_screens.py" in str(s.get("run", "")))
        i_refuse = next(i for i, n in enumerate(names) if "changed nothing" in n)
        i_commit = next(i for i, s in enumerate(steps)
                        if "safe-commit-push" in str(s.get("uses", "")))
        assert i_capture < i_refuse < i_commit
        run = steps[i_refuse]["run"]
        assert "git status --porcelain -- assets/site_screens" in run
        assert "::error::" in run and "exit 1" in run
        # The capture step itself carries no continue-on-error: a non-zero
        # exit from the script fails the job.
        assert not steps[i_capture].get("continue-on-error")


# ---------------------------------------------------------------------------
# 4. The banners are engine.brand's lines
# ---------------------------------------------------------------------------

class TestTheBannersAreBrandLines:
    def test_committed_svgs_are_what_the_builder_writes(self):
        import build_youtube_banners as bb

        wordmark = bb.wordmark_from_svg(bb.ASSETS_DIR / bb.SVG_NAMES["en"])
        for channel in bb.CHANNELS:
            committed = (bb.ASSETS_DIR / bb.SVG_NAMES[channel]).read_text(encoding="utf-8")
            assert committed == bb.banner_svg(channel, wordmark), (
                f"{bb.SVG_NAMES[channel]} drifted from engine.brand — run "
                "python scripts/build_youtube_banners.py")

    def test_each_banner_reads_the_brand_tagline_and_strap(self):
        import build_youtube_banners as bb
        from engine import brand

        for channel in bb.CHANNELS:
            lines = bb.banner_text_lines(
                (bb.ASSETS_DIR / bb.SVG_NAMES[channel]).read_text(encoding="utf-8"))
            tagline, strap = brand.youtube_banner_lines(channel)
            assert lines == [tagline, strap], (channel, lines)

    def test_brand_lines_by_channel(self):
        from engine import brand

        assert brand.network_tagline_for("ru") == brand.NETWORK_TAGLINE_RU
        assert brand.network_tagline_for("fr") == brand.NETWORK_TAGLINE_FR
        assert brand.network_tagline_for("xx") == brand.NETWORK_TAGLINE
        en_tag, en_strap = brand.youtube_banner_lines("en")
        assert en_tag == brand.NETWORK_TAGLINE
        assert en_strap.startswith("SPACE · AI · MARKETS · WORLD NEWS · SCIENCE")
        for channel in ("ru", "fr"):
            _t, strap = brand.youtube_banner_lines(channel)
            assert strap.startswith("STARSHIP · TESLA ·"), strap

    def test_the_russian_banner_sets_a_cyrillic_font(self):
        import build_youtube_banners as bb

        ru = (bb.ASSETS_DIR / bb.SVG_NAMES["ru"]).read_text(encoding="utf-8")
        assert "'Golos Text'" in ru
        assert "textLength" not in ru, "a forced width distorts the glyphs per renderer"

    def test_the_pngs_exist_at_banner_size(self):
        import build_youtube_banners as bb
        from PIL import Image

        for channel in bb.CHANNELS:
            png = bb.PNG_DIR / bb.PNG_NAMES[channel]
            assert png.is_file(), png
            assert Image.open(png).size == (bb.WIDTH, bb.HEIGHT)

    def test_build_assets_delegates_the_banners(self):
        """The brand asset builder no longer types the banner's text."""
        src = (ROOT / "brand-refresh-2026" / "build_assets.py").read_text(encoding="utf-8")
        assert 'write("nerra-youtube-banner.svg"' not in src
        section = src.split("# ---------- 3.", 1)[1].split("# ---------- 4.", 1)[0]
        assert "build_youtube_banners" in section
        assert "<text" not in section, "the banner section types its own text again"
