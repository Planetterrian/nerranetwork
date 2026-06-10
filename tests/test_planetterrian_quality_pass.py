"""Drift guards for the June 10 2026 Planetterrian quality pass
(docs/planetterrian_review_2026_06_10.md) — same process as the Tesla
flagship pass.

Pins:
* the network-wide missing-closing guard in engine/pipeline.py (PT
  Ep081/Ep084 shipped without the supplied closing block — Ep084 ended
  mid-teaser with no sign-off and no Closing chapter);
* PT chapter markers carry positional anchors and the Closing pattern
  covers "see you next" + every intros-pool closing variant;
* the unified single length target (1,800-2,100 words; floor 1600).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.intros import _SHOW_PERSONALITIES  # noqa: E402


def _markers():
    cfg = yaml.safe_load((_ROOT / "shows/planetterrian.yaml").read_text(encoding="utf-8"))
    return cfg["chapters"]["section_markers"]


class TestChapters:
    def test_every_closing_variant_matched(self):
        closing = next(m for m in _markers() if m["title"] == "Closing")
        regex = re.compile(closing["pattern"], re.IGNORECASE)
        for variant in _SHOW_PERSONALITIES["planetterrian"]["closings"]:
            assert regex.search(variant), variant[:80]
        # The Ep081 failure mode: a model-written "See you next time."
        assert regex.search("See you next time.")

    def test_positional_anchors(self):
        by_title = {m["title"]: m for m in _markers()}
        assert by_title["Introduction"].get("where") == "start"
        assert by_title["Closing"].get("where") == "end"
        assert by_title["Tomorrow Teaser"].get("where") == "end"


class TestUnifiedLength:
    def test_floor_and_single_target(self):
        cfg = yaml.safe_load((_ROOT / "shows/planetterrian.yaml").read_text(encoding="utf-8"))
        assert cfg["llm"]["min_podcast_words"] == 1600
        prompt = (_ROOT / "shows/prompts/planetterrian_podcast.txt").read_text(encoding="utf-8")
        assert "1,800–2,100 words" in prompt
        assert "at least 2400 words" not in prompt
        assert "12-15 minute" not in prompt


class TestMissingClosingGuard:
    """The pipeline appends the supplied closing block verbatim when the
    LLM omitted it, BEFORE chapter parsing (so Closing always parses)."""

    def _run(self, script: str, closing: str, monkeypatch):
        from engine import pipeline as pl
        captured = {}

        def fake_generate(template_vars, config, tracker=None):
            return script

        def fake_parse(podcast_script, markers, show_name=""):
            captured["script"] = podcast_script
            return []

        monkeypatch.setattr("engine.generator.generate_podcast_script", fake_generate)
        monkeypatch.setattr("engine.generator.generate_digest",
                            lambda *a, **k: "digest")
        monkeypatch.setattr("engine.chapters.parse_chapters", fake_parse)
        from types import SimpleNamespace
        config = SimpleNamespace(
            name="Planetterrian Daily", slug="planetterrian",
            llm=SimpleNamespace(min_podcast_words=1600),
            chapters=SimpleNamespace(enabled=True, section_markers=[{"pattern": "x", "title": "y"}]),
            publishing=SimpleNamespace(host_name="Patrick"),
        )
        result = pl.run_generation_phase(
            config, episode_num=85, today_str="June 10, 2026",
            hook="hook", x_thread="# Digest\ncontent",
            extra_context={"closing_block": closing},
            template_vars={"digest": "d", "episode_num": 85},
            args=None, tracker=None,
        )
        return captured.get("script", result[1])

    def test_appends_when_missing(self, monkeypatch):
        closing = ("That's Planetterrian Daily for today. I'm Patrick in "
                   "Vancouver. Thanks for listening.")
        script = "Patrick: Story one.\n\nPatrick: Next time, watch for the koala genome results."
        out = self._run(script, closing, monkeypatch)
        assert "That's Planetterrian Daily for today" in out

    def test_no_double_append_when_present(self, monkeypatch):
        closing = ("That's Planetterrian Daily for today. I'm Patrick in "
                   "Vancouver. Thanks for listening.")
        script = ("Patrick: Story one.\n\nPatrick: That's Planetterrian Daily "
                  "for today. I'm Patrick in Vancouver. Thanks for listening.")
        out = self._run(script, closing, monkeypatch)
        assert out.count("That's Planetterrian Daily for today") == 1
