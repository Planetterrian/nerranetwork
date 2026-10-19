"""Guards for the homepage Shorts reel (Oct 18 2026).

Operator direction: "Build the video Shorts into the new landing page such
that it looks beautiful and improves the quality of the landing page and
discovery of shows for visitors." What these pin:

* the reel renders one 9:16 card per show from the committed
  ``youtube_videos.json`` rows (``engine.landing_test.pick_videos``), never a
  still-scheduled video, ordered one per beat first
  (``order_shorts_for_discovery``), each card linking its show page;
* nothing from YouTube loads with the page: no iframe, no YouTube script —
  the player is a facade and its frame is the youtube-nocookie.com embed,
  built only from an id parsed out of the committed watch_url; a row with no
  parseable id links out instead of getting a Play button;
* a row with a ``preview_url`` renders a muted, looping, inline, preload-none
  ``<video>`` with the scene as its poster, and reduced motion stops it;
* brand colours are never text (the Oct 7 rule) in the reel's CSS;
* every GA4 event the reel fires is one the fetcher reads;
* ``engine.short_preview`` cuts a silent 360x640 H.264 loop under the size
  cap with ffmpeg and uploads it to ``previews/<slug>/…`` as video/mp4.

Every render goes to ``tmp_path`` through the real generator: never read a
committed generated page.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate_html as G  # noqa: E402
from engine import landing_test as LT  # noqa: E402
from engine import short_preview as SP  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 17, 13, 30, tzinfo=UTC)
TEMPLATE = ROOT / "templates" / "network_page.html.j2"
SCRIPT = ROOT / "assets" / "js" / "shorts-reel.js"

SCENE = "https://gallery.nerranetwork.com/test/scene-portrait.webp"
PREVIEW = "https://audio.nerranetwork.com/previews/spacex/ep120-short1.mp4"


def _short(slug, vid, **kw):
    return {"show_slug": slug, "kind": "short", "published": kw.pop("published", "2026-10-17"),
            "episode": kw.pop("episode", 120), "channel": "en", "window": "hook_open",
            "title": kw.pop("title", f"{slug} hook headline #Shorts"),
            "watch_url": kw.pop("watch_url", f"https://www.youtube.com/watch?v={vid}"), **kw}


FIXTURE = {
    "spacex": [_short("spacex", "AAAAAAAAAA1", preview_url=PREVIEW)],
    "tesla": [_short("tesla", "BBBBBBBBBB2", watch_url="https://www.youtube.com/shorts/BBBBBBBBBB2")],
    "models_agents": [_short("models_agents", "CCCCCCCCCC3")],
    "omni_view": [_short("omni_view", "DDDDDDDDDD4")],
    # No parseable id: the card links out, no Play button.
    "planetterrian": [_short("planetterrian", "", watch_url="https://www.youtube.com/@NerraNetwork/shorts")],
    "modern_investing": [_short("modern_investing", "EEEEEEEEEE5")],
    # Private until its publish_at: never a card.
    "fascinating_frontiers": [_short("fascinating_frontiers", "FFFFFFFFFF6",
                                     publish_at="2099-01-01T00:00:00Z")],
}
EXPECTED = {"spacex", "tesla", "models_agents", "omni_view", "planetterrian", "modern_investing"}


def _section(html: str, section_id: str) -> str:
    match = re.search(rf'<section[^>]*\bid="{section_id}"', html)
    assert match, f"#{section_id} not rendered"
    return html[match.start():html.index("</section>", match.end())]


@pytest.fixture(scope="module")
def home(tmp_path_factory) -> str:
    mp = pytest.MonkeyPatch()
    by_dir = {}
    for slug, rows in FIXTURE.items():
        cfg = G.NETWORK_SHOWS.get(slug) or {}
        assert cfg.get("json_path"), slug
        by_dir[(ROOT / cfg["json_path"]).parent.resolve()] = rows
    real_load = G._load_json_quiet

    def fake_load(path):
        p = Path(path)
        if p.name == "youtube_videos.json":
            return {"videos": by_dir.get(p.parent.resolve(), [])}
        return real_load(path)

    real_scene = LT.episode_scene

    def fake_scene(index, slug, number, ep_date, **kw):
        if kw.get("portrait_first") and slug in FIXTURE and slug != "omni_view":
            return {"url": SCENE + f"?{slug}", "orientation": "portrait"}
        return real_scene(index, slug, number, ep_date, **kw)

    mp.setattr(G, "_load_json_quiet", fake_load)
    mp.setattr(LT, "episode_scene", fake_scene)
    try:
        out = tmp_path_factory.mktemp("reel")
        return G.generate_network_page(output_dir=out, now=NOW).read_text(encoding="utf-8")
    finally:
        mp.undo()


def _cards(html: str):
    sec = _section(html, "shorts")
    return re.findall(r'<li class="lt-reel-card".*?</li>', sec, re.S)


# --------------------------------------------------------------------------
# The reel
# --------------------------------------------------------------------------

class TestReel:
    def test_one_card_per_show_and_scheduled_rows_excluded(self, home):
        cards = _cards(home)
        assert len(cards) == len(EXPECTED)
        names = {G.NETWORK_SHOWS[s]["name"] for s in EXPECTED}
        for name in names:
            assert any(name.replace("&", "&amp;") in c or name in c for c in cards), name
        assert "FFFFFFFFFF6" not in home

    def test_every_card_links_its_show_page(self, home):
        for card in _cards(home):
            assert re.search(r'<a class="lt-reel-show" href="[\w-]+\.html">Listen to <b>', card), card[:200]

    def test_reel_sits_under_the_flagship_band_and_is_in_the_section_nav(self, home):
        if 'id="flagships"' in home:
            assert home.index('id="flagships"') < home.index('id="shorts"')
        assert '<a href="#shorts">Shorts</a>' in home

    def test_no_youtube_frame_or_script_loads_with_the_page(self, home):
        assert "<iframe" not in home
        for src in re.findall(r'<script[^>]+src="([^"]+)"', home):
            assert "youtube" not in src, src
        assert "iframe_api" not in home and "ytimg.com" not in home
        assert 'src="assets/js/shorts-reel.js" defer' in home

    def test_play_buttons_only_for_parseable_ids(self, home):
        cards = _cards(home)
        data = json.loads(re.search(r'<script type="application/json" id="lt-reel-data">(.*?)</script>',
                                    home, re.S).group(1))
        assert len(data) == len(cards)
        for i, (card, row) in enumerate(zip(cards, data)):
            if row["id"]:
                # Play is a real link to the Short: it works with no script.
                assert re.search(rf'<a class="lt-reel-hit" href="{re.escape(row["watch"])}"[^>]*'
                                 rf'data-reel-play="{i}"', card)
                assert row["embed"].startswith(f"https://www.youtube-nocookie.com/embed/{row['id']}?")
                assert "autoplay=1" in row["embed"] and "playsinline=1" in row["embed"] and "rel=0" in row["embed"]
            else:
                assert "data-reel-play" not in card
                assert 'target="_blank" rel="noopener"' in card and row["embed"] == ""
        ids = {r["id"] for r in data}
        assert {"AAAAAAAAAA1", "BBBBBBBBBB2"} <= ids  # watch?v= and /shorts/ both parse

    def test_preview_row_renders_a_muted_inline_loop_with_its_poster(self, home):
        card = next(c for c in _cards(home) if PREVIEW in c)
        video = re.search(r"<video[^>]*>", card).group(0)
        for attr in ("muted", "loop", "playsinline", 'preload="none"', f'src="{PREVIEW}"',
                     f'poster="{SCENE}?spacex"', 'aria-hidden="true"'):
            assert attr in video, attr
        assert "autoplay" not in video
        others = [c for c in _cards(home) if PREVIEW not in c]
        assert all("<video" not in c for c in others)

    def test_a_card_without_a_scene_uses_the_show_cover_never_a_youtube_thumbnail(self, home):
        card = next(c for c in _cards(home) if "Omni View" in c)
        assert 'class="lt-reel-cover"' in card and "lt-reel-frame is-card" in card

    def test_the_player_is_an_accessible_dialog(self, home):
        sec = _section(home, "shorts")
        dialog = re.search(r"<dialog[^>]*>", sec).group(0)
        assert 'aria-modal="true"' in dialog and 'aria-labelledby="lt-player-title"' in dialog
        assert 'id="lt-player-title"' in sec
        assert 'aria-label="Close the player"' in sec
        assert "privacy-enhanced" in sec

    def test_empty_state_renders_no_reel(self, tmp_path):
        html = G.generate_network_page(output_dir=tmp_path, all_shows=[]).read_text(encoding="utf-8")
        assert 'id="shorts"' not in html and "shorts-reel.js" not in html and "<dialog class" not in html


class TestOrderAndIds:
    def test_one_per_beat_first(self):
        hub = {"spacex": {"id": "space"}, "tesla": {"id": "tesla"}, "fascinating_frontiers": {"id": "space"},
               "models_agents": {"id": "ai"}, "ai_chips": {"id": "ai"}, "omni_view": {"id": "world-news"}}
        rows = [{"show_slug": s} for s in ("spacex", "tesla", "models_agents", "fascinating_frontiers",
                                          "ai_chips", "omni_view")]
        out = [r["show_slug"] for r in LT.order_shorts_for_discovery(rows, hub_for=hub, limit=16)]
        # SpaceX and Tesla are one beat (the front page's variety rule).
        assert out == ["spacex", "models_agents", "omni_view", "tesla", "fascinating_frontiers", "ai_chips"]
        assert len(LT.order_shorts_for_discovery(rows, hub_for=hub, limit=2)) == 2

    def test_the_reel_shows_many_shows(self):
        assert LT.WATCH_SHORT_LIMIT >= 12

    @pytest.mark.parametrize("url,vid", [
        ("https://www.youtube.com/watch?v=XuInqVlb4_8", "XuInqVlb4_8"),
        ("https://www.youtube.com/shorts/6Ku9UDncjO0", "6Ku9UDncjO0"),
        ("https://www.youtube.com/shorts/6Ku9UDncjO0?feature=share", "6Ku9UDncjO0"),
        ("https://www.youtube.com/watch?feature=x&v=XuInqVlb4_8", "XuInqVlb4_8"),
        ("https://youtu.be/XuInqVlb4_8", "XuInqVlb4_8"),
        ("https://www.youtube.com/@NerraNetwork/shorts", ""),
        ("https://www.youtube.com/watch?v=short", ""),
        ("https://www.youtube.com/watch?v=XuInqVlb4_8x", ""),
        ("http://www.youtube.com/watch?v=XuInqVlb4_8", ""),
        ("https://evil.example/watch?v=XuInqVlb4_8", ""),
        ("", ""),
    ])
    def test_video_id_extraction(self, url, vid):
        assert LT.youtube_video_id(url) == vid

    def test_embed_is_nocookie_and_refuses_a_bad_id(self):
        assert LT.youtube_embed_url("XuInqVlb4_8").startswith(
            "https://www.youtube-nocookie.com/embed/XuInqVlb4_8?autoplay=1&playsinline=1&rel=0")
        assert LT.youtube_embed_url("bad id") == "" and LT.youtube_embed_url("") == ""

    def test_preview_url_must_be_an_https_mp4(self):
        assert LT.preview_url({"preview_url": PREVIEW}) == PREVIEW
        assert LT.preview_url({"preview_url": "http://x/y.mp4"}) == ""
        assert LT.preview_url({"preview_url": "https://x/y.gif"}) == ""
        assert LT.preview_url({}) == ""


class TestStyleAndScript:
    def _css(self):
        # Oct 19 2026: the stylesheet is the shared _landing_styles include.
        text = (ROOT / "templates" / "_landing_styles.html.j2").read_text(encoding="utf-8")
        css = text[text.index("<style>"):text.index("</style>")]
        return re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def test_no_raw_brand_colour_as_text(self):
        css = self._css()
        assert re.findall(r"(?<![-\w])color:\s*var\(--show-color(?:,[^)]*\))?\)", css) == []
        assert not re.search(r"(?<![-\w])color:\s*var\(--card-accent\)", css)
        assert ".lt-reel-badge" in css and "--show-color-text" in css

    def test_reduced_motion_stops_the_previews(self):
        css = self._css()
        block = css[css.index("@media (prefers-reduced-motion: reduce)"):]
        assert ".lt-reel-preview { display: none !important; }" in block
        js = SCRIPT.read_text(encoding="utf-8")
        assert "matchMedia('(prefers-reduced-motion: reduce)')" in js
        assert "IntersectionObserver" in js and "saveData" in js

    def test_the_script_builds_the_frame_only_on_play_and_removes_it_on_close(self):
        js = SCRIPT.read_text(encoding="utf-8")
        assert "createElement('iframe')" in js
        assert "frame.textContent = ''" in js
        assert "showModal" in js and "'Escape'" in js and "touchstart" in js
        assert "ArrowRight" in js and "ArrowLeft" in js

    def test_every_event_the_reel_fires_is_read_by_the_fetcher(self):
        from scripts.fetch_ga4_stats import CONVERSION_EVENTS, ENGAGEMENT_EVENTS

        fired = set(re.findall(r"track_event\('([a-z_]+)'", SCRIPT.read_text(encoding="utf-8")))
        assert {"play_short", "select_short_show"} <= fired
        for name in fired:
            assert name in ENGAGEMENT_EVENTS and name not in CONVERSION_EVENTS, name


# --------------------------------------------------------------------------
# engine.short_preview
# --------------------------------------------------------------------------

needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                                  reason="ffmpeg not installed")


def _probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json",
                          str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.fixture(scope="module")
def source_clip(tmp_path_factory) -> Path:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    path = tmp_path_factory.mktemp("clip") / "short.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=540x960:rate=30:duration=9",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=9", "-shortest",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True)
    return path


@needs_ffmpeg
class TestShortPreview:
    def test_cuts_a_silent_9x16_h264_loop_under_the_cap(self, source_clip, tmp_path):
        out = tmp_path / "prev.mp4"
        assert SP.make_short_preview(source_clip, out, start_s=1.0) is True
        info = _probe(out)
        kinds = [s["codec_type"] for s in info["streams"]]
        assert kinds == ["video"]  # no audio
        v = info["streams"][0]
        assert (v["codec_name"], v["width"], v["height"], v["pix_fmt"]) == ("h264", 360, 640, "yuv420p")
        assert v["r_frame_rate"] == "24/1"
        assert 5.5 <= float(info["format"]["duration"]) <= 6.5
        assert 0 < out.stat().st_size <= SP.PREVIEW_MAX_BYTES
        # +faststart: the moov atom precedes the media data.
        head = out.read_bytes()[:4096]
        assert head.find(b"moov") != -1 and (head.find(b"mdat") == -1 or head.find(b"moov") < head.find(b"mdat"))

    def test_landscape_source_is_cropped_to_portrait(self, tmp_path):
        src = tmp_path / "wide.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                        "-i", "testsrc2=size=1280x720:rate=30:duration=3", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", str(src)], check=True)
        out = tmp_path / "p.mp4"
        assert SP.make_short_preview(src, out, seconds=2)
        v = _probe(out)["streams"][0]
        assert (v["width"], v["height"]) == (360, 640)

    def test_failure_returns_false_and_never_raises(self, tmp_path):
        assert SP.make_short_preview(tmp_path / "missing.mp4", tmp_path / "o.mp4") is False
        junk = tmp_path / "junk.mp4"
        junk.write_bytes(b"not a video")
        assert SP.make_short_preview(junk, tmp_path / "o2.mp4") is False
        assert not (tmp_path / "o2.mp4").exists()


class TestShortPreviewUpload:
    def test_key_bucket_and_content_type(self, tmp_path, monkeypatch):
        clip = tmp_path / "p.mp4"
        clip.write_bytes(b"\x00" * 10)
        for k, v in (("R2_ENDPOINT_URL", "https://r2.example"), ("R2_ACCESS_KEY_ID", "a"),
                     ("R2_SECRET_ACCESS_KEY", "s")):
            monkeypatch.setenv(k, v)
        calls = {}

        def fake_upload(local_path, remote_key, **kw):
            calls.update(kw, key=remote_key, path=local_path)
            return f"{kw['public_base_url']}/{remote_key}"

        import engine.storage as storage
        monkeypatch.setattr(storage, "upload_to_r2", fake_upload)
        url = SP.upload_short_preview(clip, "tesla", 638, index=2)
        assert calls["key"] == "previews/tesla/ep638-short2.mp4"
        assert calls["content_type"] == "video/mp4"
        assert url == "https://audio.nerranetwork.com/previews/tesla/ep638-short2.mp4"
        # Never the audio keyspace (<slug>/...).
        assert not calls["key"].startswith("tesla/")

    def test_no_credentials_or_failure_returns_empty(self, tmp_path, monkeypatch):
        clip = tmp_path / "p.mp4"
        clip.write_bytes(b"\x00")
        for k in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            monkeypatch.delenv(k, raising=False)
        assert SP.upload_short_preview(clip, "tesla", 1) == ""
        for k in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            monkeypatch.setenv(k, "x")
        import engine.storage as storage

        def boom(*a, **kw):
            raise RuntimeError("network down")

        monkeypatch.setattr(storage, "upload_to_r2", boom)
        assert SP.upload_short_preview(clip, "tesla", 1) == ""
        assert SP.upload_short_preview(tmp_path / "missing.mp4", "tesla", 1) == ""
