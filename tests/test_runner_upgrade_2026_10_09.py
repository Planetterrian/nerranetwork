"""Oct 9 2026 — the runner upgrade, taken whole, and what it turned up.

Operator-directed: every workflow moved to ubuntu-26.04 (apt ffmpeg 8.0),
Python 3.14 and current action majors in one PR, read on one slate, rather
than let GitHub's ``ubuntu-latest`` label move under the network on Oct 19.

What the render smoke found before the push, and what binds:

* ``-shortest`` alone no longer ends the video where the audio ends on
  ffmpeg 8. A 135 s episode rendered 4,050 frames on 6.1 and 4,101 on 8.1
  — 1.7 s of bare slideshow after the audio, past the outro card's window;
  a 35 s Short came back 36.5 s long. Every final mux now carries an
  explicit output ``-t`` beside ``-shortest`` (``engine.video._output_bound``),
  and the long-form render probes the duration on every path, not only
  when an outro card exists.
* actionlint's built-in label list stops at ubuntu-24.04; the config
  teaches it the image.
* The PyAV ceiling (``<19``) stays; the floor may rise.
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.video import (  # noqa: E402
    _long_form_cmd,
    _output_bound,
    _short_form_cmd,
    _single_pass_long_form_cmd,
)

WORKFLOWS = sorted(glob.glob(str(ROOT / ".github" / "workflows" / "*.yml")))


class TestTheOutputIsBoundToTheAudio:
    def test_the_bound_is_shortest_plus_an_explicit_t(self):
        assert _output_bound(135.0) == ["-shortest", "-t", "135.00"]
        assert _output_bound(0.0) == ["-shortest"]
        assert _output_bound(None) == ["-shortest"]

    def test_every_final_mux_carries_it(self, tmp_path):
        scenes = [tmp_path / f"s{i}.png" for i in range(3)]
        single = _single_pass_long_form_cmd(scenes, "a.mp3", "brand.png", "out.mp4",
                                            total_duration=135.0)
        two_stage = _long_form_cmd("a.mp3", "bg.mp4", "brand.png", "out.mp4",
                                   bg_is_video=True, total_duration=135.0)
        short = _short_form_cmd("a.mp3", "bg.mp4", "brand.png", "short.mp4",
                                bg_is_video=True, start_offset=2.0, duration=35.0)
        for cmd, dur in ((single, "135.00"), (two_stage, "135.00"), (short, "35.00")):
            i = cmd.index("-shortest")
            assert cmd[i + 1:i + 3] == ["-t", dur], cmd[i - 2:i + 4]
            # The bound is on the OUTPUT: it follows the maps and codecs and
            # precedes the output path.
            assert i > cmd.index("-map") and cmd[-1] == "out.mp4" or cmd[-1] == "short.mp4"

    def test_a_render_with_no_known_length_keeps_shortest_alone(self):
        cmd = _long_form_cmd("a.mp3", "bg.mp4", "brand.png", "out.mp4", bg_is_video=True)
        i = cmd.index("-shortest")
        assert cmd[i + 1] != "-t"


class TestTheImageIsPinned:
    def test_every_job_names_ubuntu_26_04(self):
        for wf in WORKFLOWS:
            text = Path(wf).read_text(encoding="utf-8")
            labels = re.findall(r"runs-on:\s*(\S+)", text)
            assert labels, wf
            assert set(labels) == {"ubuntu-26.04"}, (wf, labels)

    def test_python_is_3_14_everywhere(self):
        pins = set()
        for wf in WORKFLOWS + [str(ROOT / ".github/actions/setup-python/action.yml")]:
            pins |= set(re.findall(r"python-version:\s*['\"]([\d.]+)['\"]", Path(wf).read_text(encoding="utf-8")))
        assert pins == {"3.14"}, pins
        action = (ROOT / ".github/actions/setup-python/action.yml").read_text(encoding="utf-8")
        assert 'default: "3.14"' in action

    def test_actions_are_on_current_majors(self):
        found = set()
        for wf in WORKFLOWS + glob.glob(str(ROOT / ".github/actions/*/action.yml")):
            found |= set(re.findall(r"uses: (actions/[a-z-]+)@v(\d+)", Path(wf).read_text(encoding="utf-8")))
        by_action = {}
        for name, major in found:
            by_action.setdefault(name, set()).add(int(major))
        assert by_action["actions/checkout"] == {7}, by_action
        assert by_action["actions/setup-python"] == {7}, by_action
        assert by_action["actions/upload-artifact"] == {7}, by_action

    def test_actionlint_knows_the_label(self):
        cfg = (ROOT / ".github/actionlint.yaml").read_text(encoding="utf-8")
        assert re.search(r"labels:\s*\n\s*- ubuntu-26\.04", cfg), cfg


class TestRequirements:
    def test_floors_moved_and_the_pyav_ceiling_did_not(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        for line in ("openai>=3.26.1", "tenacity>=9.2.1", "websockets>=17.2",
                     "google-auth>=2.61.0", "google-auth-oauthlib>=1.5.0",
                     "google-api-python-client>=2.201.0"):
            assert re.search(rf"^{re.escape(line)}\s*$", req, re.M), line
        assert re.search(r"^av>=18\.1\.0,<19\s*$", req, re.M)
