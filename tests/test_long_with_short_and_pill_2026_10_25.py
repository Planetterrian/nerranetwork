"""Oct 25 2026 — the two operator decisions from the YouTube/X review.

1. The long-form goes public in the hook Short's slot, not in the Oct 17
   noon / 18:00 ET waves. 97% of a Short's views arrive by day 3 and the
   waves kept the long private through that window, so the Short could
   only point at the website.
2. Every EN Short carries a persistent "Subscribe · <cadence> episodes"
   pill from ~3 s to the end card. Half of a Short's viewers leave before
   the end card, which was the only place the Short asked.
"""
from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import release_schedule as rs  # noqa: E402
from engine import video as v  # noqa: E402

RUN_SHOW = (ROOT / "run_show.py").read_text(encoding="utf-8")
PILL = "Subscribe · daily episodes"


# ------------------------------------------------------- 1. long with Short --
class TestLongGoesWithTheShort:
    def test_run_show_hands_the_long_slot_to_the_hook_short(self):
        i = RUN_SHOW.index("_short1_at = None\n            if _release_on")
        block = RUN_SHOW[i:i + 900]
        assert "_long_publish_at is not None" in block
        assert "_short1_at = _long_publish_at" in block

    def test_the_short_links_the_long_when_they_share_the_instant(self):
        # _long_hidden_from is "t is None or t < _long_publish_at": the same
        # instant is NOT hidden, so the Short's description links the long.
        assert "return t is None or t < _long_publish_at" in RUN_SHOW

    def test_every_show_gets_the_same_slot_for_both(self):
        run = dt.datetime(2026, 10, 26, 5, 0, tzinfo=rs.EASTERN)
        for slug in rs.RELEASE_ORDER:
            assert rs.youtube_long_time(slug, run) == rs.youtube_short_time(slug, run)

    def test_the_today_schedule_has_no_long_form_wave(self):
        from engine.newsroom import schedule_is_clean, todays_schedule
        rows = todays_schedule(dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.timezone.utc))
        labels = [r["label"] for r in rows]
        assert "Evening wave" not in labels
        yt = [r for r in rows if r["label"] == "YouTube"]
        assert yt and "full episode" in yt[0]["detail"]
        assert schedule_is_clean(rows)


# ------------------------------------------------------- 2. subscribe pill --
def _graph(**kw):
    base = dict(hook="A hook line for the test", end_card=True,
                end_card_duration=3.0, total_duration=32.0,
                subtitles_path="/tmp/x.ass", with_url_pill=True)
    base.update(kw)
    return v._short_form_filter_graph(1080, 1920, 30, **base)


class TestSubscribePill:
    def test_off_is_byte_identical(self):
        assert _graph() == _graph(subscribe_pill=None) == _graph(subscribe_pill="")

    def test_on_runs_from_three_seconds_to_the_end_card(self):
        g = _graph(subscribe_pill=PILL)
        assert "Subscribe" in g and "daily episodes" in g
        assert "enable='between(t,3.00,29.00)'" in g
        assert "[subpill]" in g

    def test_without_an_end_card_it_runs_to_the_end(self):
        g = _graph(subscribe_pill=PILL, end_card=False)
        assert "enable='between(t,3.00,32.00)'" in g

    def test_it_sits_top_left_on_the_brand_pill_row(self):
        g = _graph(subscribe_pill=PILL)
        stage = g[g.index("Subscribe"):g.index("[subpill]")]
        assert "x=38:y=54-text_h/2" in stage
        # Drawn before the hook, captions and end card, so it never
        # paints over them.
        assert g.index("[subpill]") < g.index("A hook line")
        assert g.index("[subpill]") < g.index("subtitles=")

    def test_too_long_or_no_room_draws_nothing(self):
        assert _graph(subscribe_pill="x" * 60) == _graph()
        assert _graph(subscribe_pill=PILL, total_duration=6.0) == \
            _graph(total_duration=6.0)

    def test_the_longest_text_clears_the_brand_pill(self):
        # Brand pill: 320 px wide, 24 px from the right edge.
        from PIL import ImageFont
        font = ImageFont.truetype(v._find_font(), v._SUBSCRIBE_PILL_FONTSIZE)
        widest = max(font.getlength(f"Subscribe · {w} episodes")
                     for w in ("daily", "weekly", "weekday", "new"))
        assert 38 + widest + 14 < 1080 - 24 - 320

    def test_config_default_and_network_default(self):
        from engine.config import YouTubeConfig
        assert YouTubeConfig().shorts_subscribe_pill is False
        defaults = yaml.safe_load((ROOT / "shows" / "_defaults.yaml").read_text())
        assert defaults["youtube"]["shorts_subscribe_pill"] is True

    def test_run_show_wires_the_en_short_with_the_cadence_word(self):
        i = RUN_SHOW.index("# ---- Persistent subscribe pill (Oct 25 2026) ----")
        block = RUN_SHOW[i:i + 1500]
        assert '_yt_channel == "en"' in block
        assert "episodes_phrase" in block
        assert "subscribe_pill=_short_pill," in RUN_SHOW

    def test_the_cadence_word_follows_the_schedule(self):
        from engine.cadence import episodes_phrase
        assert episodes_phrase("tesla") == "daily episodes"
        assert episodes_phrase("dp_pod") == "weekly episodes"

    def test_the_metric_is_on_the_allowlist(self):
        src = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'metrics.record("shorts_subscribe_pill_rendered"' in src

    @pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
    def test_ffmpeg_renders_it(self, tmp_path):
        audio, cover = tmp_path / "a.mp3", tmp_path / "c.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "sine=f=220:d=7", str(audio)], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "color=c=0x223344:s=1080x1920:d=1", "-frames:v", "1",
                        str(cover)], check=True)
        out = tmp_path / "s.mp4"
        v.build_short_video(audio, cover, out, duration=6.0, hook="Hook",
                            show_name="Tesla Shorts Time", end_card=True,
                            subscribe_pill=PILL)
        assert out.exists() and out.stat().st_size > 0
