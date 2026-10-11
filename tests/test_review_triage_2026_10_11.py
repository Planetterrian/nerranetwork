"""Oct 11 2026 — triage of the four open Grok review PRs (#1381 dp_pod,
#1391 spacex, #1402 collingwood, #1406 omni_view_europe).

Two DP Pod findings were verified against the committed files and are fixed
here:

* a host's spoken line was a chapter title, speaker label included
  ("DAN: Ten", "PATRICK: I'll take the hit on that" — Ep070–077, six of ten
  episodes), because the spoken-sentence title helper never recognised a
  dialogue turn;
* no episode carried a Cold Open chapter: the identity line is "This is The
  DP Pod, episode N" and the marker only knew the Welcome forms.

The weekly show's writer prompts also still described it as daily.
"""
from __future__ import annotations

import glob
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class TestDialogueLinesAreNeverChapterTitles:
    @pytest.mark.parametrize("line", [
        "DAN: Ten.",
        "PATRICK: I'll take the hit on that.",
        "DAN: Strongest version of that: a one-and-done metabolic fix.",
    ])
    def test_a_speaker_labelled_line_gives_no_title(self, line):
        from engine.chapters import _first_sentence_as_title
        assert _first_sentence_as_title(line) == ""

    def test_an_ordinary_sentence_still_titles(self):
        from engine.chapters import _first_sentence_as_title
        assert _first_sentence_as_title(
            "Underwater solar cells capture energy ten metres down.") != ""

    def test_committed_dp_pod_episodes_replay_clean(self):
        from engine.chapters import parse_chapters
        from engine.config import load_config
        ch = load_config(ROOT / "shows" / "dp_pod.yaml").chapters
        replayed = 0
        for ep in range(70, 78):
            tts = glob.glob(str(ROOT / "digests" / "dp_pod" / f"*Ep{ep:03d}_*_tts.txt"))
            if not tts:
                continue
            script = Path(tts[0]).read_text(encoding="utf-8")
            chapters = parse_chapters(
                script, list(ch.section_markers), show_name="dp_pod",
                known_sections_only=getattr(ch, "known_sections_only", False))
            titles = [c.title for c in chapters]
            assert not any(re.match(r"^[A-Z]{2,15}:\s", t) for t in titles), (ep, titles)
            assert titles and titles[0] == "Cold Open", (ep, titles)
            replayed += 1
        assert replayed >= 5

    def test_only_dialogue_scripts_carry_speaker_labels(self):
        # The rule is safe network-wide because no other show's script opens
        # a line on a speaker label.
        shows = {Path(p).parent.name for p in glob.glob(str(ROOT / "digests" / "*" / "*_tts.txt"))
                 if re.search(r"(?m)^[A-Z]{2,15}: ", Path(p).read_text(encoding="utf-8"))}
        assert shows <= {"dp_pod"}, shows


class TestDpPodPromptsSayWeekly:
    @pytest.mark.parametrize("name,stale", [
        ("dp_pod_system.txt", "a daily conversation"),
        ("dp_pod_system.txt", "ten minutes a day"),
        ("dp_pod_system.txt", "one mindset principle a day"),
        ("dp_pod_digest.txt", "producing the daily briefing"),
        ("dp_pod_digest.txt", "club's daily email"),
        ("dp_pod_podcast.txt", "ten minutes a day"),
        ("dp_pod_podcast.txt", "reply to the daily email"),
    ])
    def test_no_daily_cadence(self, name, stale):
        text = (ROOT / "shows" / "prompts" / name).read_text(encoding="utf-8")
        assert stale not in text, (name, stale)
