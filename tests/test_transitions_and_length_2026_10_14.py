"""Natural story transitions and shows that reach their length (Oct 14 2026).

Operator listen: the Oct 13 story break "sounds forced and unnatural", and
many shows run short of their time targets. Measured:

* Every story change in Vancouver Ep021 was 1.6-1.7 s of digital silence
  against a 0.35 s median gap between sentences — a fixed 1.2 s added on
  top of the voice's own pause, with no music under it mid-episode — and
  two beats landed 7 s apart, one before "He asked Albertans…" (the same
  story).
* The cohort ran 66-91% of its word targets; the desks ~6 minutes of a
  10-12 minute promise. The digest length check counted the hidden claims
  ledger (480-1,100 words on a 4.7 run), so the digest-side expansion had
  not fired on the cohort's daily shows since their first week.

Pins: the total-pause planner and its spacing/continuation rules, the
theme cue in the music mix, the prose-only digest count, the desk format
v3 (The Closer Look), the doubled deep dives, the targets sized from the
promised minutes with the skip floors held, and the narration patterns.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

from engine import story_breaks as S

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "shows" / "prompts"
DESKS = ("omni_view_europe", "omni_view_asia_pacific", "omni_view_africa_mideast",
         "omni_view_latam", "omni_view_north_america")


def _cfg(slug):
    from engine.config import load_config
    return load_config(ROOT / "shows" / f"{slug}.yaml")


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------

class TestThePauseIsATotal:
    def test_only_the_difference_is_spliced(self):
        breaks, unplaced = S.plan_breaks([(10.0, 10.5)], [(10.0, 10.45)], gap_seconds=1.0)
        assert unplaced == 0 and len(breaks) == 1
        assert breaks[0].insert == pytest.approx(0.55)
        assert breaks[0].gap_start == 10.0

    def test_a_pause_already_long_enough_gets_nothing_spliced(self):
        breaks, _ = S.plan_breaks([(10.0, 11.2)], [(10.0, 11.2)], gap_seconds=1.0)
        assert breaks[0].insert == 0.0

    def test_beats_closer_than_twenty_seconds_are_dropped(self):
        anchors = [(30.0, 30.4), (37.0, 37.4), (60.0, 60.4)]
        sil = [(29.9, 30.4), (36.9, 37.4), (59.9, 60.4)]
        breaks, _ = S.plan_breaks(anchors, sil, gap_seconds=1.0)
        assert [round(b.cut) for b in breaks] == [30, 60]
        assert S.MIN_STORY_SECONDS == 20.0

    def test_per_cut_splice_and_transcript_shift(self):
        t = {"duration": 100.0, "segments": [{"start": 50.0, "end": 51.0,
                                               "words": [{"start": 50.0, "end": 51.0}]}]}
        out = S.shift_transcript(t, [10.0, 40.0], [0.5, 0.25])
        assert out["segments"][0]["start"] == 50.75
        assert out["duration"] == 100.75
        cmd = S.insert_silences_cmd(Path("a.wav"), Path("b.wav"), [10.0, 40.0], [0.5, 0.0])
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "apad=pad_dur=0.500" in graph and graph.count("apad") == 1

    def test_cue_starts_where_the_last_word_ends_in_the_spliced_track(self):
        breaks = [S.Break(cut=30.2, insert=0.5, gap_start=30.0, gap_end=30.4),
                  S.Break(cut=60.2, insert=0.6, gap_start=60.0, gap_end=60.4)]
        assert S.breather_starts(breaks) == [30.0, 60.5]


class TestWhereABeatGoes:
    MD = ("## News\n\n"
          "1. **Premier on child care**\nDavid Eby child care spot family premier "
          "province budget announced.\nSource: https://a.example/1\n\n"
          "2. **Alberta referendum vote**\nAlberta referendum vote unity Canada "
          "confederation ballot campaign.\nSource: https://a.example/2\n\n"
          "## Weather\n\n"
          "1. **Current conditions**\nCloudy eleven degrees Vancouver airport reading "
          "humidity wind.\nSource: https://w.example/1\n\n"
          "2. **Forecast**\nTuesday mainly cloudy high fourteen index forecast "
          "showers.\nSource: https://w.example/2\n")

    def test_a_line_that_opens_on_a_pronoun_continues_the_story(self):
        assert S.opens_as_continuation("He asked Albertans to vote for unity.")
        assert S.opens_as_continuation("The company said the plant would close.")
        assert not S.opens_as_continuation("Health Canada approved the drug.")
        assert not S.opens_as_continuation("Herald reporters found the files.")
        script = ("Premier David Eby said his family holds a child care spot in the province budget.\n"
                  "Eby announced the child care budget for the province on Monday.\n"
                  "He asked Alberta referendum voters to back unity with Canada on the ballot.\n"
                  "The Alberta referendum vote on confederation is next week, the campaign says.\n")
        assert S.story_boundary_lines(script, self.MD) == []

    def test_short_items_under_one_heading_are_one_block(self):
        units = S.story_units(self.MD)
        assert [u.section for u in units] == ["news", "news", "weather", "weather"]
        script = ("Premier David Eby said his family holds a child care spot in the province budget.\n"
                  "Eby announced the child care budget for the province on Monday.\n"
                  "In Vancouver it is cloudy at eleven degrees at the airport reading, humidity and wind.\n"
                  "Tuesday stays mainly cloudy with a high of fourteen, the forecast index says, showers.\n")
        starts = S.story_boundary_lines(script, self.MD)
        # One beat before the weather block, none inside it.
        assert starts == [2]


class TestTheCue:
    def test_offsets_are_steady_bars_and_differ(self):
        from engine.audio import breather_offsets
        offs = breather_offsets(ROOT / "assets/music/OmniView.mp3", 4)
        assert len(offs) == 4 and len(set(offs)) == 4
        assert all(o >= 8.0 for o in offs)
        assert offs == breather_offsets(ROOT / "assets/music/OmniView.mp3", 4)

    def test_overlay_is_soft_faded_and_never_normalised(self):
        from engine.audio import BREATHER_VOLUME, _breather_overlay_cmd
        cmd = _breather_overlay_cmd("m.wav", "t.mp3", "o.wav", [60.0, 90.0], [12.0, 30.0])
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "normalize=0" in graph and graph.count("afade=t=in") == 2
        assert "adelay=delays=59850:all=1" in graph
        assert 0.1 <= BREATHER_VOLUME <= 0.3

    def test_mix_lays_a_cue_in_the_pause_and_none_in_the_opening_bed(self, tmp_path):
        from engine.audio import mix_with_music

        voice = tmp_path / "voice.wav"
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "sine=f=220:d=60",
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=1.0",
             "-f", "lavfi", "-i", "sine=f=330:d=20",
             "-filter_complex", "[0][1][2]concat=n=3:v=0:a=1,aresample=48000",
             str(voice)], check=True)

        def level(path, start, dur):
            out = subprocess.run(
                ["ffmpeg", "-hide_banner", "-nostats", "-ss", str(start), "-t", str(dur),
                 "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                capture_output=True, text=True).stderr
            return float(re.search(r"mean_volume: (-?[\d.]+|-inf) dB", out).group(1))

        common = dict(intro_duration=3, overlap_duration=15, fade_duration=30,
                      outro_duration=10, voice_intro_delay=0.0, denoise=False)
        plain = tmp_path / "plain.mp3"
        cued = tmp_path / "cued.mp3"
        music = ROOT / "assets/music/OmniView.mp3"
        mix_with_music(voice, music, plain, **common)
        mix_with_music(voice, music, cued, breathers=[60.0, 20.0], **common)
        # The pause at 60-61 s is dead air without the cue and music with it.
        assert level(plain, 60.25, 0.6) < -60
        assert level(cued, 60.25, 0.6) > -45
        # A cue inside the opening bed (20 s) is skipped: same audio there.
        assert abs(level(plain, 19.5, 2.0) - level(cued, 19.5, 2.0)) < 1.0


class TestConfigAndWiring:
    def test_network_values(self):
        from engine.config import AudioConfig
        assert AudioConfig().story_break_seconds == 0.0 and AudioConfig().story_break_cue is False
        a = _cfg("omni_view_world").audio
        assert a.story_break_seconds == 1.0 and a.story_break_cue is True

    def test_run_show_plans_totals_and_passes_the_cues(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        block = src[src.index("# 9a-breaks."):src.index("# 9b. Post-TTS")]
        assert "plan_breaks(" in block and "gap_seconds=_break_s" in block
        assert "breather_starts(_breaks)" in block and "story_break_cue" in block
        assert "breathers=story_cue_starts or None" in src


class TestTheSpokenTurn:
    def test_no_quotable_attribution_specimen(self):
        text = (PROMPTS / "_shared/content_discipline.txt").read_text(encoding="utf-8")
        assert "Reuters reports" not in text
        assert "never a sentence that opens on the outlet's name" in text
        assert "Consecutive stories never open on the same shape" in text

    def test_desk_anchor_phrases_are_never_required(self):
        body = (PROMPTS / "_shared/omni_desk_podcast_body.txt").read_text(encoding="utf-8")
        assert "contains the phrase" not in body and "must contain" not in body
        for slug in ("ai_chips", "mag7", "prediction_markets", "peptides", "longevity"):
            text = (PROMPTS / f"{slug}_podcast.txt").read_text(encoding="utf-8")
            assert "(podcast-app chapters key on it); vary everything around it" not in text, slug


# ---------------------------------------------------------------------------
# Length
# ---------------------------------------------------------------------------

class TestDigestFloorCountsProse:
    def test_the_ledger_is_not_counted(self):
        from engine.generator import digest_prose_word_count
        ledger = "```claims\n" + "[" + ",".join(['{"claim": "a b c d e f g h"}'] * 50) + "]\n```"
        text = "One two three four five.\nSource: https://example.com/x\n\n" + ledger
        assert digest_prose_word_count(text) == 5

    def test_the_expansion_check_uses_it_and_the_retry_is_sourced(self):
        src = (ROOT / "engine/generator.py").read_text(encoding="utf-8")
        assert "word_count = digest_prose_word_count(text)" in src
        assert "it is allowed to use \"\n        f\"your own domain knowledge" not in src
        from engine.generator import _build_digest_expansion_retry_prompt
        p = _build_digest_expansion_retry_prompt(500, 1200, "draft")
        assert "never from memory" in p and "domain knowledge" not in p


class TestDeskFormatV3:
    def test_prompts_carry_the_closer_look(self):
        body = (PROMPTS / "_shared/omni_desk_digest_body.txt").read_text(encoding="utf-8")
        assert "### The Closer Look\n**1 story, 300-420 words**" in body
        assert body.index("### The Closer Look") < body.index("### Also Today")
        assert "nothing from memory" in body
        pod = (PROMPTS / "_shared/omni_desk_podcast_body.txt").read_text(encoding="utf-8")
        assert "[The Closer Look] Only when the briefing has the section." in pod

    def test_validator_and_intake_know_it(self):
        from engine.omni_desks import DESK_ITEM_SECTIONS
        from engine.validation import omni_desk_validation_config
        assert "The Closer Look" in DESK_ITEM_SECTIONS
        rules = {r.name: r for r in omni_desk_validation_config().sections}
        assert rules["The Closer Look"].optional and rules["Lead"].min_chars == 600
        assert "The Closer Look" in rules["Across the Region"].pattern

    @pytest.mark.parametrize("slug", DESKS)
    def test_each_desk(self, slug):
        from engine.generator import publication_floor
        c = _cfg(slug)
        assert c.llm.min_podcast_words == 1650 and c.llm.min_digest_words == 1500
        assert publication_floor(c.llm.min_podcast_words, c.llm.min_podcast_publish_words) == 780
        assert c.fetch_full_text == 20 and c.fetch_full_text_chars == 5000
        raw = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
        assert {"reuters.com", "apnews.com"} <= set(raw["preferred_domains"])
        titles = {m.title: m for m in c.chapters.section_markers}
        assert titles["The Closer Look"].digest_section == "The Closer Look"


# Old skip floor (60% of the old target) — never raised by this pass.
OLD_FLOORS = {"ai_chips": 780, "mag7": 660, "prediction_markets": 660,
              "vancouver": 720, "collingwood": 540, "omni_view_world": 690}


class TestTargetsFromTheMinutes:
    @pytest.mark.parametrize("slug,floor", sorted(OLD_FLOORS.items()))
    def test_target_rose_and_the_skip_floor_did_not(self, slug, floor):
        from engine.generator import publication_floor
        c = _cfg(slug)
        assert publication_floor(c.llm.min_podcast_words, c.llm.min_podcast_publish_words) == floor
        assert c.llm.min_podcast_words > floor / 0.6

    def test_deep_dives_doubled_and_sourced(self):
        chips = (PROMPTS / "ai_chips_digest.txt").read_text(encoding="utf-8")
        assert "(450-600 words)" in chips and "Build it from ONE article above" in chips
        mag7 = (PROMPTS / "mag7_digest.txt").read_text(encoding="utf-8")
        assert "(400-550 words)" in mag7
        pm = (PROMPTS / "prediction_markets_digest.txt").read_text(encoding="utf-8")
        assert "(450-600 words)" in pm and "worked example" in pm
        for slug, sec in (("ai_chips", "The Teardown"), ("mag7", "The Thread")):
            from engine.validation import SHOW_VALIDATION_CONFIGS
            names = [r.name for r in SHOW_VALIDATION_CONFIGS[slug]().sections]
            assert sec in names, slug

    def test_local_shows_and_top_world_grew(self):
        for slug in ("vancouver", "collingwood"):
            assert "### The Closer Look" in (PROMPTS / f"{slug}_digest.txt").read_text(encoding="utf-8")
        world = (PROMPTS / "omni_view_world_digest.txt").read_text(encoding="utf-8")
        assert "Items one to three: sentence count follows fact count, six to nine" in world
        assert "900-1,150 words" in world

    def test_established_short_shows(self):
        ff = (PROMPTS / "fascinating_frontiers_digest.txt").read_text(encoding="utf-8")
        pt = (PROMPTS / "planetterrian_digest.txt").read_text(encoding="utf-8")
        for text in (ff, pt):
            assert "450-550 words" in text and "uses YOUR OWN knowledge" not in text
        tesla = (PROMPTS / "tesla_podcast.txt").read_text(encoding="utf-8")
        assert "(up to six sentences)" not in tesla
        on = (PROMPTS / "offshore_north_digest.txt").read_text(encoding="utf-8")
        assert "LENGTHEN THIS SECTION FIRST" not in on

    def test_full_text_follows_the_likely_stories(self):
        from engine.article_text import enrich_articles_with_full_text
        arts = [{"title": f"t{i}", "url": f"https://x.example/{i}", "description": "short",
                 "source_name": "X"} for i in range(4)]
        arts[3]["story_cluster_size"] = 2
        arts[2]["preferred_source"] = True
        fetched = []

        def fake(url):
            fetched.append(url)
            return 200, "<html><body><p>" + ("word " * 400) + "</p></body></html>"

        enrich_articles_with_full_text(arts, max_articles=2, fetch=fake, workers=1)
        assert sorted(fetched) == ["https://x.example/2", "https://x.example/3"]


class TestNarrationFilter:
    @pytest.mark.parametrize("sentence", [
        "A sign of progress, measured and finished, is not in today's reporting.",
        "The day had none.",
        "Today's text does not carry a named lawmaker's speech or a drafted bill.",
        "None of the markets in today's set opened in the last three days.",
        "No human outcome, and no aging approval for compound nine nine one, is in the report.",
        "None of those accounts says which way the vote will go.",
    ])
    def test_caught(self, sentence):
        from engine.absence_sentences import is_absence_sentence
        assert is_absence_sentence(sentence)

    @pytest.mark.parametrize("sentence", [
        "The storm passed with no injuries reported.",
        "None of the passengers was hurt, police said.",
        "The day had begun with a vote in parliament.",
    ])
    def test_kept(self, sentence):
        from engine.absence_sentences import is_absence_sentence
        assert not is_absence_sentence(sentence)
