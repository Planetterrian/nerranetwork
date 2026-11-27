"""Nov 27 2026, Surendra Goel's hand re-cut.

The auto cut read "every time I go to any of the current platform, I start
over" as a guest asking to restart, dropped 62 s of his answer and landed
the episode mid-sentence. A restart is a request, never a description."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines" / "voices"))

import auto_edit  # noqa: E402


class TestARestartIsARequest:
    def test_describing_other_apps_is_not_a_restart(self):
        for text in ("every time I go to any of the current platform, I start over.",
                     "I have to start over and start applying those filters again.",
                     "you start over every time"):
            assert not auto_edit.RESTART_RE.search(text), text

    def test_real_requests_still_are(self):
        for text in ("no wait, let me start over.", "sorry, can I start again",
                     "Let's start over.", "Start again.", "Sorry, start that over",
                     "scratch that", "from the top"):
            assert auto_edit.RESTART_RE.search(text), text

    def test_the_surendra_transcript_finds_no_request(self):
        text = ("[15:24] Mira: Why do existing platforms lose interest once payment clears?\n"
                "[15:29] Surendra: I think the systems were designed.\n"
                "[16:20] Surendra: every time I go to any of the current platform, I start over. "
                "I have to start over and start applying those filters\n"
                "[16:32] Surendra: again. So there's no loyalty there.\n")
        assert auto_edit.guest_requests(text) == []
