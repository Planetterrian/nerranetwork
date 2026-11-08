"""Nov 8 2026 — the long-form follows the audio, and X gets a clean clip.

1. The "Coming up" card: the spoken map's stories on screen while the map is
   spoken (~8-20 s, where the median EN long-form falls from 91% to 57% of
   its viewers). Items are the map's own words from the display script;
   a card is shown whole or not at all.
2. The long-form subscribe pill at 45 s and the midpoint (long-forms bring
   most of the channel's subscribers; the outro card is the only ask and
   almost nobody reaches it).
3. The hook Short posted to X is re-rendered without the YouTube subscribe
   pill and end card.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import long_form_cards as lfc  # noqa: E402
from engine import video as v  # noqa: E402

RUN_SHOW = (ROOT / "run_show.py").read_text(encoding="utf-8")
FIXTURE = json.loads((ROOT / "tests" / "fixtures"
                      / "long_form_rundown_spacex_ep154.json").read_text(encoding="utf-8"))


def _items(text):
    got = lfc.rundown_items(text)
    return [t for t, _ in got] if got else None


# ------------------------------------------------------------- the parser --
class TestRundownItems:
    def test_a_plain_map(self):
        assert _items("Heat-shield data from the latest orbital reentry, jet "
                      "generators in Mississippi, then the Counterpoint and an "
                      "engineering deep dive.") == [
            "Heat-shield data from the latest orbital reentry",
            "Jet generators in Mississippi",
            "The Counterpoint and an engineering deep dive"]

    def test_a_back_pointer_and_its_lead_in_are_not_items(self):
        assert _items("After the polar craters, Rubin’s hidden companions, Lucy "
                      "among the Trojans, and Concordia’s gel propellant, then a "
                      "week in review.") == [
            "Rubin’s hidden companions", "Lucy among the Trojans",
            "Concordia’s gel propellant", "A week in review"]
        assert _items("After that, a diamond wafer, a utility spending plan, and "
                      "a stolen Nvidia shipment, then what's on the horizon.")[0] \
            == "A diamond wafer"

    def test_sequencing_verbs_are_trimmed(self):
        assert _items("Semi production, LFP cells, and Megapacks in Belgium come "
                      "next, plus Counterpoint and First Principles.") == [
            "Semi production", "LFP cells", "Megapacks in Belgium",
            "Counterpoint and First Principles"]
        assert _items("Starship’s first commercial satellites, a Blackwell-series "
                      "cluster, and The Counterpoint follow.")[-1] == "The Counterpoint"

    def test_brand_case_is_kept(self):
        got = _items("Norway's defence contract, orbital compute, and xAI's new "
                     "sites come next, then The Counterpoint and an engineering "
                     "deep dive.")
        assert "xAI's new sites" in got

    def test_a_section_name_may_be_one_word_at_the_end(self):
        assert _items("Childhood measles after immunization gaps, carbon from human "
                      "metabolism, and peanuts and brain insulin follow, then "
                      "Spotlight.")[-1] == "Spotlight"

    @pytest.mark.parametrize("text", [
        # the host narrating her own moves lists verbs, not stories
        "After the close we screen Canadian AI names, walk a simulated hold, "
        "review Aritzia, then options-flow tools.",
        "We'll check the indexes, then how to confirm money is rotating, and a "
        "simulated Bank of Montreal hold.",
        # commas inside an item break it into lowercase single words
        "After that, a Texas foundry booking, Arm's quarter, then heat, coal, and "
        "local votes, and a walk through a die-to-die link.",
        # one-word places in the middle are not sections
        "Intel’s quarter, a lab optical switch, Finland, Ontario, two power "
        "memoranda, then the build.",
        # an item too long for the card is never clipped
        "Malaysia’s opposition loses its registration, families prepare to return "
        "to a Cape Town neighbourhood after apartheid-era removals, and Alberta "
        "decides on Canada.",
        # not a list
        "Starship flies again.",
        "",
    ])
    def test_a_card_is_whole_or_absent(self, text):
        assert lfc.rundown_items(text) is None

    def test_every_item_fits_its_title_limit(self):
        from engine.titles import RUNDOWN_ITEM_MAX
        from PIL import ImageFont
        font = ImageFont.truetype(v._find_font(), v._RUNDOWN_ITEM_FONTSIZE)
        # A full-length item of ordinary headline text fits 1920 px from
        # x=120 with its box.
        sample = ("Canada’s trade pact with the United Arab Emirates and More"
                  )[:RUNDOWN_ITEM_MAX]
        assert len(sample) == RUNDOWN_ITEM_MAX
        assert v._RUNDOWN_X + font.getlength(sample) + 24 < 1920 - 60


# --------------------------------------------------------------- the card --
class TestRundownCard:
    def test_the_card_follows_the_spoken_map(self):
        card = lfc.rundown_card(FIXTURE["tts"], FIXTURE["reader"], FIXTURE["transcript"])
        assert card is not None
        # The map is spoken from 8.7 s to 16.6 s on Ep154.
        assert 8.0 <= card.start <= 9.5
        assert 16.0 <= card.end <= 18.5
        times = [t for t, _ in card.items]
        assert times == sorted(times) and times[0] == card.start
        assert all(card.start <= t < card.end for t in times)
        # Display spelling, never the TTS respelling.
        assert card.label == "COMING UP"
        assert all("Space X" not in t for _, t in card.items)

    def test_the_voice_offset_moves_the_card(self):
        a = lfc.rundown_card(FIXTURE["tts"], FIXTURE["reader"], FIXTURE["transcript"])
        b = lfc.rundown_card(FIXTURE["tts"], FIXTURE["reader"], FIXTURE["transcript"],
                             audio_offset=3.0)
        assert round(b.start - a.start, 2) == 3.0 and round(b.end - a.end, 2) == 3.0

    def test_no_map_no_card(self):
        tts = FIXTURE["tts"].split("\n\n")
        no_map = "\n\n".join(tts[:2] + tts[3:])
        rdr = FIXTURE["reader"].split("\n\n")
        no_map_r = "\n\n".join(rdr[:2] + rdr[3:])
        assert lfc.rundown_card(no_map, no_map_r, FIXTURE["transcript"]) is None

    def test_a_reader_copy_that_does_not_line_up_gives_no_card(self):
        rdr = FIXTURE["reader"].split("\n\n")
        assert lfc.rundown_card(FIXTURE["tts"], "\n\n".join(rdr[1:]),
                                FIXTURE["transcript"]) is None

    def test_garbage_never_raises(self):
        assert lfc.rundown_card(None, None, None) is None
        assert lfc.rundown_card_for_episode("/nope_transcript.json") is None


# ----------------------------------------------------- the subscribe pill --
class TestSubscribeWindows:
    def test_45_seconds_and_the_midpoint(self):
        assert lfc.subscribe_windows(600) == [(45.0, 53.0), (300.0, 308.0)]

    def test_short_episodes_get_one_and_tiny_ones_none(self):
        assert lfc.subscribe_windows(120) == [(45.0, 53.0)]
        assert lfc.subscribe_windows(60) == []
        assert lfc.subscribe_windows(0) == [] and lfc.subscribe_windows(None) == []

    def test_it_moves_past_the_card(self):
        assert lfc.subscribe_windows(600, avoid=[(40.0, 50.0)])[0] == (51.0, 59.0)


# ----------------------------------------------------------- the graph --
def _lf(**kw):
    base = dict(bg_is_video=True, with_url_pill=True,
                hook="A hook line for the test", chapter_cards=[(30.0, "A story")])
    base.update(kw)
    return v._long_form_filter_graph(**base)


OVERLAYS = {
    "rundown": (8.7, 17.6, "COMING UP", [(8.7, "Heat-shield data"),
                                         (11.7, "Jet generators in Mississippi")]),
    "subscribe_text": "Subscribe · daily episodes",
    "subscribe_windows": [(45.0, 53.0), (300.0, 308.0)],
}


class TestTheGraph:
    def test_off_is_byte_identical(self):
        assert _lf() == _lf(overlays=None) == _lf(overlays={})
        sp = dict(scene_count=3, with_url_pill=True, hook="Hook")
        assert (v._single_pass_long_form_filter_graph(**sp)
                == v._single_pass_long_form_filter_graph(**sp, overlays=None))

    def test_on_draws_the_card_and_both_pills(self):
        g = _lf(overlays=OVERLAYS)
        assert "text='COMING UP'" in g
        assert "Jet generators in Mississippi" in g
        assert g.count("Subscribe") == 2
        assert "enable='between(t,45.00,53.05)'" in g
        assert "x=w-text_w-38:y=118" in g
        assert g.endswith("null[v]")

    def test_only_overlays_still_ends_the_graph(self):
        # With no captions, chapters or facts the hook stage must not
        # terminate the graph before the overlays.
        g = v._long_form_filter_graph(bg_is_video=True, hook="Hook", overlays=OVERLAYS)
        assert g.count("[v]") == 1 and g.endswith("null[v]")
        g2 = v._single_pass_long_form_filter_graph(3, hook="Hook", overlays=OVERLAYS)
        assert g2.count("[v]") == 1 and g2.endswith("null[v]")

    def test_too_long_pill_text_draws_no_pill(self):
        g = _lf(overlays={**OVERLAYS, "subscribe_text": "x" * 60})
        assert "x" * 60 not in g

    @pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
    def test_ffmpeg_renders_it(self, tmp_path):
        audio, cover = tmp_path / "a.mp3", tmp_path / "c.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "sine=f=220:d=12", str(audio)], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "color=c=0x223344:s=1920x1080:d=1", "-frames:v", "1",
                        str(cover)], check=True)
        out = tmp_path / "l.mp4"
        v.build_long_form_video(
            audio, cover, out, hook="Hook", show_name="SpaceX Daily",
            overlays={"rundown": (5.0, 10.0, "COMING UP",
                                  [(5.0, "One story"), (7.0, "Another story")]),
                      "subscribe_text": "Subscribe · daily episodes",
                      "subscribe_windows": [(2.0, 10.0)]})
        assert out.exists() and out.stat().st_size > 0


# ------------------------------------------------------------- wiring --
class TestWiring:
    def test_config_default_and_network_default(self):
        from engine.config import YouTubeConfig
        cfg = YouTubeConfig()
        assert cfg.long_form_rundown_card is False
        assert cfg.long_form_subscribe_pill is False
        assert cfg.x_clip_without_youtube_asks is False
        d = yaml.safe_load((ROOT / "shows" / "_defaults.yaml").read_text())["youtube"]
        assert d["long_form_rundown_card"] is True
        assert d["long_form_subscribe_pill"] is True
        assert d["x_clip_without_youtube_asks"] is True

    def test_run_show_passes_the_overlays_to_the_long_form(self):
        assert "overlays=_lf_overlays," in RUN_SHOW
        assert "def _long_form_overlays(" in RUN_SHOW
        assert "rundown_card_for_episode(transcript_path, audio_offset=offset)" in RUN_SHOW

    def test_the_x_copy_drops_only_the_youtube_asks(self):
        i = RUN_SHOW.index("def _render_x_clean_clip(")
        body = RUN_SHOW[i:i + 1500]
        assert "subscribe_pill=None, end_card=False" in body
        assert "_short_render_kwargs" in RUN_SHOW
        assert "**_short_render_kwargs," in RUN_SHOW
        # A failed X render posts the YouTube copy as before.
        assert 'result["x_clip_variant"] = (' in RUN_SHOW

    def test_the_metrics_are_on_the_allowlist(self):
        src = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        for key in ("long_form_rundown_items", "long_form_subscribe_pills",
                    "x_clip_variant"):
            assert f'metrics.record("{key}"' in src

    def test_the_item_limit_lives_in_titles(self):
        src = (ROOT / "engine" / "long_form_cards.py").read_text(encoding="utf-8")
        assert "from engine.titles import RUNDOWN_ITEM_MAX, fits" in src
        assert "[:RUNDOWN" not in src
