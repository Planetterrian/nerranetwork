"""The voice marks a story change; the music under the beat is retired (Oct 20 2026).

Operator listen: the Oct 14 music swells at every story change read as
interludes. Measured on Tesla Ep639: 13 swells in nine minutes, 5-10 dB under
the voice, 11 of them between items inside one section. Measured against a
human newscast (NPR hourly, Up First): a reader pauses no longer between
stories than between sentences and marks the change with the voice — a big
pitch lift opening a story, a firm landing closing one — where Grok TTS lifts
the same ~20 Hz at every sentence.

Pins: the cue off on every show; engine/story_tags.py placing a sanctioned
opener tag at exactly the boundaries story_breaks finds (on the tag-stripped
script, idempotent, never on a line already opening on a tag); the optional
landing tag wrapping only the previous story's last sentence; run_show
inserting before the *_tts.txt write and stripping tags before every
Whisper match; the new tag words known to the stripper and the leak
detector; and the map rule in the shared cold-open spec with no specimen.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from engine import story_breaks as S
from engine import story_tags as T
from engine.config import load_config
from engine.utils import strip_speech_tags

ROOT = Path(__file__).resolve().parent.parent
EP = ROOT / "digests" / "spacex" / "SpaceX_Daily_Ep128_20261012"
HAVE_FIXTURE = Path(f"{EP}_tts.txt").exists()


def _real():
    return (Path(f"{EP}.md").read_text(encoding="utf-8"),
            Path(f"{EP}_tts.txt").read_text(encoding="utf-8"))


def _show_yamls():
    for p in sorted((ROOT / "shows").glob("*.yaml")):
        if p.name.startswith("_") or p.name in ("network_meta.yaml",):
            continue
        yield p


@pytest.mark.skipif(not HAVE_FIXTURE, reason="fixture episode pruned")
class TestTagPlacementOnARealEpisode:
    def test_a_breath_opens_every_story_start_and_nothing_else(self):
        md, script = _real()
        expected = S.story_boundary_lines(script, md)
        assert len(expected) >= 5
        res = T.tag_story_boundaries(script, md)
        assert res.boundaries == len(expected) and res.opened == len(expected) and res.closed == 0
        tagged_lines = S.script_lines(res.script)
        for k, line in enumerate(tagged_lines):
            assert line.startswith("[breath] ") == (k in expected), (k, line[:60])

    def test_the_spoken_words_are_unchanged(self):
        md, script = _real()
        res = T.tag_story_boundaries(script, md)
        assert strip_speech_tags(res.script).split() == strip_speech_tags(script).split()

    def test_tagging_is_idempotent_and_boundaries_survive_the_tags(self):
        md, script = _real()
        once = T.tag_story_boundaries(script, md)
        twice = T.tag_story_boundaries(once.script, md)
        assert twice.script == once.script and twice.opened == 0
        # The audio beat reads the stripped script and finds the same starts.
        assert S.story_boundary_lines(strip_speech_tags(once.script), md) == S.story_boundary_lines(script, md)

    def test_a_landing_tag_wraps_only_the_previous_last_sentence(self):
        md, script = _real()
        res = T.tag_story_boundaries(script, md, close_tag="low")
        assert 0 < res.closed <= res.boundaries
        lines = S.script_lines(res.script)
        for k, line in enumerate(lines):
            if "<low>" in line:
                assert line.count("<low>") == 1 and line.rstrip().endswith("</low>")
                assert lines[k + 1].startswith("[breath] ")
                inner = re.search(r"<low>(.*?)</low>", line).group(1)
                assert len(inner.split()) <= T.MAX_CLOSE_SENTENCE_WORDS
        assert strip_speech_tags(res.script).split() == strip_speech_tags(script).split()

    def test_a_bare_tag_name_is_required(self):
        md, script = _real()
        with pytest.raises(ValueError):
            T.tag_story_boundaries(script, md, close_tag="<low>x")


class TestLastSentence:
    def test_span(self):
        line = "First fact here. Second one follows, and it ends. Last sentence lands."
        s, e = T.last_sentence_span(line)
        assert line[s:e] == "Last sentence lands."
        assert T.last_sentence_span("Only one.")[0] == 0

    def test_long_or_tagged_closers_are_left_alone(self):
        long = " ".join(["word"] * (T.MAX_CLOSE_SENTENCE_WORDS + 1)) + "."
        assert T._wrap_last_sentence(long, "low") == (long, False)
        assert T._wrap_last_sentence("Done. <emphasis>Big</emphasis> close.", "low")[1] is False


class TestNetworkSetting:
    def test_defaults(self):
        d = yaml.safe_load((ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert d["audio"]["story_break_cue"] is False
        assert d["audio"]["story_break_seconds"] == 1.0
        # Oct 20 2026, the first slate: the breath was heard as far too
        # prominent on the custom voice. Off, and no breath tag reaches TTS.
        assert d["tts"]["story_tags"] is False
        assert d["tts"]["story_tag_open"] == ""
        assert d["tts"]["story_tag_close"] == ""

    def test_no_show_keeps_the_music_cue_or_turns_story_tags_on(self):
        for p in _show_yamls():
            cfg = load_config(p)
            assert cfg.audio.story_break_cue is False, p.name
            assert cfg.tts.story_tags is False, p.name

    def test_breath_is_no_longer_a_sanctioned_tag(self):
        from engine import intros
        assert not any("breath" in t for t in intros._SANCTIONED_TAGS)
        assert "[breath]" not in intros.build_delivery_spec("tesla")


class TestNoBreathReachesSynthesis:
    def test_strip_breath_tags(self):
        from engine.utils import strip_breath_tags
        s = "Last fact here.\n[breath] South Korea's exports fell.\nIt [inhale] went [pause] on. [exhale]\n"
        assert strip_breath_tags(s) == "Last fact here.\nSouth Korea's exports fell.\nIt went [pause] on.\n"
        assert strip_breath_tags(strip_breath_tags(s)) == strip_breath_tags(s)
        assert strip_breath_tags("") == ""

    @pytest.mark.skipif(not HAVE_FIXTURE, reason="fixture episode pruned")
    def test_a_tagged_script_strips_back_to_its_words(self):
        from engine.utils import strip_breath_tags
        md, script = _real()
        tagged = T.tag_story_boundaries(script, md, open_tag="[breath]").script
        assert strip_breath_tags(tagged).split() == script.split()

    def test_run_show_resynth_and_the_dubs_strip_before_synthesis(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        strip_at = src.index("podcast_script = _strip_breaths(podcast_script)")
        assert src.index("from engine.story_tags import tag_story_boundaries") < strip_at < src.index("# Save TTS-ready script")
        resynth = (ROOT / "scripts" / "resynthesize_episode.py").read_text(encoding="utf-8")
        assert "strip_breath_tags(" in resynth
        multi = (ROOT / "engine" / "multilingual.py").read_text(encoding="utf-8")
        assert "strip_breath_tags(" in multi


class TestRunShowWiring:
    def test_tags_go_in_before_the_tts_text_is_saved_and_never_cost_an_episode(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        tag_at = src.index("from engine.story_tags import tag_story_boundaries")
        save_at = src.index("# Save TTS-ready script")
        assert tag_at < save_at
        block = src[tag_at - 600:save_at]
        assert "not config.tts.dialogue_mode" in block
        assert "story_break_seconds" in block
        assert 'metrics.record("story_tags_inserted"' in block
        assert "except Exception" in block

    def test_every_whisper_match_reads_the_stripped_script(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        block = src[src.index("# 9a-breaks."):src.index("# 9b. Post-TTS")]
        assert "story_boundary_lines(_spoken_script" in block
        assert "boundary_anchors(\n                                _spoken_script" in block
        assert "align_timestamps_to_transcript(\n                                episode_chapters, _ch_strip(podcast_script)" in src

    def test_the_music_cue_code_remains_an_opt_in(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "breather_starts(_breaks)" in src and '"story_break_cue"' in src


class TestTagVocabulary:
    def test_the_stripper_and_detector_know_the_candidate_tags(self):
        from engine.tag_leak_detector import LEAK_PATTERNS
        s = strip_speech_tags("<low>It lands.</low> [breath] <lower-pitch>Lower.</lower-pitch> [inhale] Next.")
        assert s == "It lands. Lower. Next."
        names = {n for _, n in LEAK_PATTERNS}
        assert "pitch-tag" in names
        rx = dict((n, r) for r, n in LEAK_PATTERNS)["pitch-tag"]
        assert rx.search("The extension runs. Lower pitch. A regional airline")
        assert not rx.search("The pitch of the roof is lower than the code allows")

    def test_the_probe_covers_the_candidates_through_the_production_request(self):
        src = (ROOT / "scripts" / "probe_tts_tags.py").read_text(encoding="utf-8")
        for tag in ('_variant("low"', '_variant("lower-pitch"', '_variant("soft"',
                    '"[breath]"', '"[long-pause]"'):
            assert tag in src, tag
        assert "grok_speak_chunk(" in src and '"<fast>"' in src and "text_normalization=True" in src
        wf = (ROOT / ".github" / "workflows" / "probe-tts-tags.yml").read_text(encoding="utf-8")
        assert "contents: read" in wf and "upload-artifact" in wf and "scripts/probe_tts_tags.py" in wf


class TestTheMap:
    def test_the_cold_open_spec_asks_for_a_map_after_the_identity_line(self):
        from engine.intros import build_cold_open_spec
        spec = build_cold_open_spec("tesla")
        assert "THE MAP" in spec
        i_map = spec.index("THE MAP")
        assert spec.index("identity line", i_map - 400) < i_map
        # A map, not a tease: the rule forbids counts and promise language.
        tail = spec[i_map:]
        assert "no count of items" in tail and "no promise language" in tail
        assert "never the lead story again" in tail
        # The body rule knows the map sits between the identity line and the lead.
        assert "identity line (and the map, below)" in spec

    def test_the_map_rule_supplies_no_specimen_sentence(self):
        from engine.intros import build_cold_open_spec
        spec = build_cold_open_spec("tesla")
        tail = spec[spec.index("THE MAP"):]
        # No quoted phrase the model could copy (the banned list sits earlier).
        assert '"' not in tail
        assert not re.search(r"\b(?:three|two) things today\b", tail, re.I)
        assert "coming up" not in tail.lower() and "stay tuned" not in tail.lower()

    def test_russian_spec_is_unchanged_in_shape(self):
        from engine.intros import build_cold_open_spec
        assert "THE MAP" not in build_cold_open_spec("finansy_prosto", is_ru=True)


class TestMeasurementBehindTheChange:
    """The numbers the decision rests on, pinned so the next pass reads them."""

    def test_oct_19_benchmark_numbers_are_recorded(self):
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        for needle in ("+34 Hz", "13 swells", "story_tags", "Probe TTS tags"):
            assert needle in text, needle
        reg = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8"))
        ids = {e["id"] for e in reg["experiments"]}
        assert "story-tags-and-map-2026-10-20" in ids

    @pytest.mark.skipif(not HAVE_FIXTURE, reason="fixture episode pruned")
    def test_fixture_transcript_still_anchors_after_tagging(self):
        md, script = _real()
        tx = json.loads(Path(f"{EP}_transcript.json").read_text(encoding="utf-8"))
        tagged = T.tag_story_boundaries(script, md).script
        clean = strip_speech_tags(tagged)
        lines = S.story_boundary_lines(clean, md)
        anchors, unmatched = S.boundary_anchors(clean, lines, tx)
        base_anchors, base_unmatched = S.boundary_anchors(script, S.story_boundary_lines(script, md), tx)
        assert anchors == base_anchors and unmatched == base_unmatched


class TestTheMapNeverTitlesAChapter:
    """The map speaks the segments' own anchor phrases (SpaceX Ep136: "…and
    later the engineering angle on first-stage reuse" fired The Engineering
    Angle at 11 s and the real deep dive fell back to its digest heading)."""

    SCRIPT = (
        "Falcon 9 booster B1063 reaches its 36th flight today.\n\n"
        "This is SpaceX Daily, episode 136.\n\n"
        "Senators on Starshield in Ukraine, Grok on X, and later the engineering angle on first-stage reuse.\n\n"
        + "\n\n".join(f"Story sentence number {k} carries a fact of its own for the record." for k in range(40))
        + "\n\nReuse physics is the engineering angle today, because a first stage only flies again if the energy budget closes.\n\n"
        + "\n\n".join(f"Deep dive sentence {k} adds a number to the physics." for k in range(12))
        + "\n\nAnd that's a wrap on today's SpaceX developments.\n"
    )
    MARKERS = [
        {"pattern": r"this is spacex daily", "title": "Introduction", "where": "start"},
        {"pattern": r"engineering deep dive|engineering angle", "title": "The Engineering Angle"},
        {"pattern": r"that's a wrap", "title": "Closing", "where": "end"},
    ]

    def test_a_marker_fires_on_the_real_segment_not_the_map(self):
        from engine.chapters import parse_chapters
        chapters = parse_chapters(self.SCRIPT, self.MARKERS, min_chapters=1)
        angle = next(c for c in chapters if c.title == "The Engineering Angle")
        assert angle.opening.startswith("Reuse physics is the engineering angle today")
        assert [c.title for c in chapters].count("The Engineering Angle") == 1

    def test_a_start_marker_on_the_identity_line_still_fires(self):
        from engine.chapters import parse_chapters
        chapters = parse_chapters(self.SCRIPT, self.MARKERS, min_chapters=1)
        intro = next(c for c in chapters if c.title == "Introduction")
        assert intro.opening.startswith("This is SpaceX Daily")

    def test_the_real_ep136_script_titles_the_deep_dive_once(self):
        import yaml
        from engine.chapters import parse_chapters
        ep = ROOT / "digests" / "spacex" / "SpaceX_Daily_Ep136_20261020"
        if not Path(f"{ep}_tts.txt").exists():
            pytest.skip("fixture episode pruned")
        ch = yaml.safe_load((ROOT / "shows" / "spacex.yaml").read_text(encoding="utf-8"))["chapters"]
        chapters = parse_chapters(Path(f"{ep}_tts.txt").read_text(encoding="utf-8"), ch["section_markers"],
                                  known_sections_only=ch.get("known_sections_only", False),
                                  digest_text=Path(f"{ep}.md").read_text(encoding="utf-8"))
        angles = [c for c in chapters if c.title == "The Engineering Angle"]
        assert len(angles) == 1 and angles[0].word_start > 500
        assert not any(c.title == "Engineering Deep Dive" for c in chapters)
