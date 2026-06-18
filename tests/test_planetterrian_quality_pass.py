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


class TestChapterShapeJune18:
    """June 18 2026 pass — the orphaned-body + stolen-closing chapter class.

    Root causes (verified against Ep085/086/088/090/093 transcripts):
    * the Introduction pattern only matched the "Welcome" greeting, but the
      intro line rotates four greetings — "Good to have you on" and "Thanks
      for tuning in to" carry no "Welcome", so ~50% of episodes shipped with
      NO Introduction chapter and the whole body collapsed under the
      teaser-anchored first chapter;
    * the Tomorrow Teaser opens "Keep an eye on..."/"Watch for..." (not a
      pattern the old marker matched), so the teaser's `Next time` greedily
      matched "See you next time" in the CLOSING line, stealing it and
      leaving Ep086/090 with no Closing chapter;
    * the deep-dive markers required the literal label the prompt forbids
      announcing, so the section always fell to the garbage auto-segment
      fallback.
    """

    def test_introduction_matches_every_greeting_variant(self):
        intro = next(m for m in _markers() if m["title"] == "Introduction")
        regex = re.compile(intro["pattern"], re.IGNORECASE)
        pers = _SHOW_PERSONALITIES["planetterrian"]
        show = pers["show_name"]
        for greeting in pers["greetings"]:
            line = f"{greeting} {show}, episode ninety-three, for June eighteenth."
            assert regex.search(line), f"Introduction missed greeting: {line!r}"

    def test_deep_dive_matches_seeded_spoken_opener(self):
        dd = next(m for m in _markers() if m["title"] == "Science Deep Dive")
        regex = re.compile(dd["pattern"], re.IGNORECASE)
        # The openers the digest/podcast prompt seeds and the model actually
        # speaks (Ep090-093). These do NOT contain the literal label.
        for opener in [
            "Now, here's something most people get wrong about plant responses.",
            "Most people picture soil as a mix of minerals and water.",
            "Most people assume city environments are relatively sterile.",
        ]:
            assert regex.search(opener), f"Deep Dive missed opener: {opener!r}"

    def test_teaser_matches_keep_an_eye_and_watch_for(self):
        teaser = next(m for m in _markers() if m["title"] == "Tomorrow Teaser")
        regex = re.compile(teaser["pattern"], re.IGNORECASE)
        assert regex.search("Keep an eye on early data from gene-editing trials.")
        assert regex.search("Watch for field studies that measure drought effects.")

    def test_closing_marker_precedes_teaser(self):
        # The EI June-11 ordering rule: Closing must be listed BEFORE
        # Tomorrow Teaser so it wins the sign-off line ("See you next time")
        # that both `end` markers can match.
        titles = [m["title"] for m in _markers()]
        assert titles.index("Closing") < titles.index("Tomorrow Teaser")

    def test_end_to_end_orphan_and_steal_fixed(self):
        from engine.chapters import parse_chapters
        # A "Good to have you on" intro (no "Welcome") + a "Keep an eye on"
        # teaser on its own line + a "See you next time" closing — the exact
        # shape that previously produced no Introduction and no Closing.
        body = "\n\n".join(
            f"A study from lab {i} reported a finding with concrete numbers." * 3
            for i in range(20)
        )
        script = (
            "Good to have you on Planetterrian Daily, episode ninety-three, "
            "for June eighteenth, twenty twenty-six.\n\n"
            + body
            + "\n\nKeep an eye on early data from in-vivo gene-editing trials.\n\n"
            "That covers today's science and health news. I'm Patrick in "
            "Vancouver. See you next time."
        )
        chs = parse_chapters(script, _markers(), show_name="planetterrian")
        titles = [c.title for c in chs]
        assert titles[0] == "Introduction", titles
        assert "Closing" in titles, titles
        assert titles[-1] == "Closing", titles
        # The closing must NOT be mislabeled as the teaser.
        assert titles.index("Tomorrow Teaser") < titles.index("Closing")


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
