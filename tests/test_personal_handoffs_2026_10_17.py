"""Nerra Personal handoffs introduce the show that follows them (Oct 17 2026).

Nerra Daily Ep049/055/057 aired with every later handoff one show early: the
model skipped a show mid-edition and padded the end, and the count check
passed. Nerra Daily runs ``realign_handoffs`` since Oct 16; the personal
builder makes the same call and now runs the same repair.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.daily_edition import Segment  # noqa: E402
from engine.personal_edition import PersonalSpec  # noqa: E402


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_personal_feeds_t", ROOT / "scripts" / "build_personal_feeds.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _segments():
    def seg(name, hook):
        return Segment(slug=name.lower(), show_name=name, episode_num=1, episode_title="",
                       hook=hook, date="2026-10-17", audio_url="", content="",
                       digest_dir=ROOT, transcript_path=None, music_intro_offset=0.0)
    return [
        seg("SpaceX Daily", "SpaceX thrusters give the Roadster aerial flight"),
        seg("Planetterrian Daily", "Researchers mapped PFAS across Finger Lakes water bodies"),
        seg("Models & Agents", "Pause-token compression shrinks the inference cache"),
        seg("Fascinating Frontiers", "Young lunar faults measure how much the moon contracted"),
        seg("Omni View", "G7 nations will run joint drills against cyber attacks"),
    ]


def _reply(handoffs):
    return json.dumps({"intro": "Good morning, this is your edition.",
                       "handoffs": handoffs,
                       "signoff": "That is your edition for today."})


def test_a_shifted_personal_draft_is_realigned(monkeypatch):
    mod = _builder()
    seen = {}

    def fake(**kw):
        seen.update(kw)
        return _reply([
            "Next, PFAS samples from the Finger Lakes water bodies.",
            "After the water data, lunar faults show how far the moon contracted.",
            "Your edition closes with the G7 drills against cyber attacks.",
            "There is no new interview in your lineup today.",
        ]), {}

    import digests.xai_grok as xg
    monkeypatch.setattr(xg, "grok_generate_text", fake)
    links = mod.generate_personal_links(
        PersonalSpec(token="t" * 32, shows=["spacex"]), _segments(),
        __import__("datetime").date(2026, 10, 17))
    hand = links["handoffs"]
    assert links["_handoffs_realigned"] >= 2
    assert "PFAS" in hand[0]
    assert "Models & Agents" in hand[1]
    assert "lunar" in hand[2]
    assert "G7" in hand[3]
    # The token budget grows with the lineup, as Nerra Daily's does.
    assert seen["max_tokens"] == max(2500, 900 + 140 * 4)


def test_the_budget_scales_with_a_long_lineup():
    src = (ROOT / "scripts" / "build_personal_feeds.py").read_text(encoding="utf-8")
    assert "max_tokens=max(2500, 900 + 140 * handoff_count)" in src
    assert "links = realign_handoffs(links, segments)" in src
