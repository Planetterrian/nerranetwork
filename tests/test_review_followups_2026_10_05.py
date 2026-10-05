"""Oct 5 2026 — follow-ups to the five Grok show reviews merged that day.

* Two merged ledgers (models_agents 2026-10-02, planetterrian 2026-10-03)
  no longer parsed: the review writer always nested a new entry by two
  spaces, and those files keep their lists at column 0. Nothing caught it
  because the schema guard parses only tesla.yaml.
* A section whose spoken anchor is skipped loses its chapter — Models &
  Agents Ep178/185/189/190 (no "pop the hood", all combined-generation),
  AI Chips Ep9/Ep14 ("take the flexible queue apart"). A marker may now
  name its digest heading, and the chapter starts where that section's
  content begins.
* AI Chips: phone-chip launches excluded; the Teardown close de-seeded.
* De-seeds by shape: UC's Lesson, Planetterrian's deep dive / pivots /
  teaser, Tesla's conflicting length opener.
"""

from __future__ import annotations

import datetime
import glob
import importlib.util
import logging
import re
from pathlib import Path

import pytest
import yaml

from engine.chapters import _digest_section_anchor, parse_chapters
from engine.config import SectionMarker, load_config

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "shows" / "prompts"


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Ledgers
# ---------------------------------------------------------------------------

class TestEveryLedgerParses:
    @pytest.mark.parametrize(
        "path", sorted(glob.glob(str(ROOT / "docs" / "reviews" / "ledger" / "*.yaml"))),
        ids=lambda p: Path(p).stem)
    def test_ledger_is_valid_yaml_with_reviews(self, path):
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert isinstance(data, dict) and isinstance(data.get("reviews"), list)
        assert data.get("do_not_retry") is None or isinstance(data["do_not_retry"], list)


class TestLedgerWriterKeepsTheFilesIndentation:
    RESULT = {
        "summary": "Pass.",
        "scored_prior_predictions": [],
        "deferred": ["later: with a colon"],
        "new_predictions": [{"metric": "m", "baseline": "b", "expected": "e"}],
        "proposed_changes": [],
        "do_not_retry_additions": ["never do: this"],
    }

    @pytest.mark.parametrize("style", ["col0", "nested"])
    def test_appended_entry_parses_in_both_styles(self, tmp_path, monkeypatch, style):
        mod = _load_script("run_show_review")
        monkeypatch.setattr(mod, "ROOT", tmp_path)
        ledger = tmp_path / "docs" / "reviews" / "ledger"
        ledger.mkdir(parents=True)
        pad = "" if style == "col0" else "  "
        (ledger / "demo.yaml").write_text(
            "reviews:\n"
            f"{pad}- date: '2026-09-01'\n{pad}  summary: first\n"
            "do_not_retry:\n"
            f"{pad}- idea: old\n{pad}  evidence: x\n",
            encoding="utf-8")
        doc = tmp_path / "docs" / "reviews" / "demo_review.md"
        doc.write_text("doc", encoding="utf-8")
        mod.update_ledger("demo", self.RESULT, doc, 0.1, datetime.date(2026, 10, 5))
        data = yaml.safe_load((ledger / "demo.yaml").read_text(encoding="utf-8"))
        assert [r["date"] for r in data["reviews"]] == ["2026-09-01", "2026-10-05"]
        assert [d["idea"] for d in data["do_not_retry"]] == ["old", "never do: this"]

    def test_empty_do_not_retry_takes_the_reviews_indentation(self, tmp_path, monkeypatch):
        mod = _load_script("run_show_review")
        monkeypatch.setattr(mod, "ROOT", tmp_path)
        ledger = tmp_path / "docs" / "reviews" / "ledger"
        ledger.mkdir(parents=True)
        (ledger / "demo.yaml").write_text(
            "reviews:\n- date: '2026-09-01'\n  summary: first\ndo_not_retry: []\n",
            encoding="utf-8")
        doc = tmp_path / "docs" / "reviews" / "demo_review.md"
        doc.write_text("doc", encoding="utf-8")
        mod.update_ledger("demo", self.RESULT, doc, 0.1, datetime.date(2026, 10, 5))
        data = yaml.safe_load((ledger / "demo.yaml").read_text(encoding="utf-8"))
        assert len(data["reviews"]) == 2 and len(data["do_not_retry"]) == 1


class TestReviewRecordsCorrected:
    def _dnr(self, slug):
        data = yaml.safe_load(
            (ROOT / "docs" / "reviews" / "ledger" / f"{slug}.yaml").read_text(encoding="utf-8"))
        return " ".join(d["idea"] for d in data["do_not_retry"])

    def test_french_number_mismatch_is_recorded_as_whisper(self):
        assert "French transcript" in self._dnr("models_agents")

    @pytest.mark.parametrize("slug", ["tesla", "planetterrian"])
    def test_rewrite_gate_is_not_a_lever(self, slug):
        assert "rewrite/retry gate" in self._dnr(slug)

    def test_the_french_tts_text_really_says_the_right_number(self):
        text = (ROOT / "digests" / "models_agents"
                / "Models_Agents_Ep186_20260927.fr.txt").read_text(encoding="utf-8")
        assert "épisode cent quatre-vingt-six" in text


# ---------------------------------------------------------------------------
# Chapters: a skipped anchor falls back to the digest section
# ---------------------------------------------------------------------------

DIGEST = (
    "# Show\n**HOOK:** Hook.\n\n"
    "### Model Updates\n"
    "**Router ships: Lab**\nA lab shipped a router for retrieval workloads with a new tokenizer.\n"
    "Source: [lab.com](https://lab.com/a)\n\n"
    "### Under the Hood: Speculative Decoding\n"
    "Speculative decoding lets a small drafter propose tokens that a larger target verifies. "
    "Acceptance rates between sixty and eighty percent halve latency. Drafter families must "
    "match vocabularies, and divergence wastes verification passes on mismatched blocks.\n"
)


def _script(with_anchor: bool) -> str:
    news = "\n\n".join(
        f"A lab shipped a router for retrieval workloads, item {i}, with a new tokenizer and numbers."
        for i in range(25))
    opener = ("Pop the hood on speculative decoding today.\n\n" if with_anchor else "")
    dive = "\n\n".join([
        "Speculative decoding lets a small drafter propose tokens the larger target verifies.",
        "Acceptance rates between sixty and eighty percent halve latency for the drafter.",
        "Drafter families must match vocabularies or divergence wastes verification passes.",
        "Mismatched blocks are discarded, so drafter divergence costs whole verification passes.",
    ])
    tail = "\n\n".join(["Closing filler sentence about nothing in particular." for _ in range(40)])
    return (f"This is Show, episode one.\n\n{news}\n\n{opener}{dive}\n\n"
            f"Before we go, tomorrow brings more.\n\n{tail}\n\nThat's Show for today.")


MARKERS = [
    {"pattern": "This is Show", "title": "Introduction", "where": "start"},
    {"pattern": "pop the hood", "title": "Under the Hood", "digest_section": "Under the Hood"},
    {"pattern": "Before we go", "title": "Tomorrow Teaser", "where": "end"},
    {"pattern": "That's Show", "title": "Closing", "where": "end"},
]


class TestDigestSectionFallback:
    def test_skipped_anchor_still_gets_its_chapter(self):
        chapters = parse_chapters(_script(False), MARKERS, min_chapters=1, digest_text=DIGEST)
        titles = [c.title for c in chapters]
        assert "Under the Hood" in titles
        uth = chapters[titles.index("Under the Hood")]
        assert _script(False)[uth.char_start:].lstrip().startswith("Speculative decoding lets")

    def test_without_the_digest_the_behaviour_is_unchanged(self):
        chapters = parse_chapters(_script(False), MARKERS, min_chapters=1)
        assert "Under the Hood" not in [c.title for c in chapters]

    def test_a_spoken_anchor_wins_and_the_digest_changes_nothing(self):
        with_digest = parse_chapters(_script(True), MARKERS, min_chapters=1, digest_text=DIGEST)
        without = parse_chapters(_script(True), MARKERS, min_chapters=1)
        assert ([(c.title, c.word_start) for c in with_digest]
                == [(c.title, c.word_start) for c in without])

    def test_a_marker_without_digest_section_never_anchors(self):
        markers = [dict(m) for m in MARKERS]
        markers[1].pop("digest_section")
        chapters = parse_chapters(_script(False), markers, min_chapters=1, digest_text=DIGEST)
        assert "Under the Hood" not in [c.title for c in chapters]

    def test_an_absent_digest_section_returns_none(self):
        lines = _script(False).splitlines(keepends=True)
        assert _digest_section_anchor(lines, DIGEST, "The Teardown", 0, 10 ** 6) is None

    def test_a_two_word_echo_never_anchors(self):
        lines = ["News about speculative things and drafters.\n"] * 20
        assert _digest_section_anchor(lines, DIGEST, "Under the Hood", 0, 10 ** 6) is None

    def test_the_marker_field_loads_from_yaml(self):
        assert SectionMarker().digest_section == ""
        for slug, title in (("models_agents", "Under the Hood"), ("ai_chips", "The Teardown")):
            cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
            marker = next(m for m in cfg.chapters.section_markers if m.title == title)
            assert marker.digest_section == title

    @pytest.mark.parametrize("path", ["run_show.py", "engine/pipeline.py",
                                      "scripts/resynthesize_episode.py"])
    def test_every_chapter_call_site_passes_the_digest(self, path):
        src = (ROOT / path).read_text(encoding="utf-8")
        call = src[src.index("parse_chapters("):]
        call = call[:call.index(")\n")]
        assert "digest_text=" in call


class TestRealEpisodes:
    """Replay on the committed episodes that lost the chapter."""

    @pytest.fixture(autouse=True)
    def _quiet(self):
        logging.disable(logging.CRITICAL)
        yield
        logging.disable(logging.NOTSET)

    @staticmethod
    def _chapters(slug, stem, with_digest=True):
        from engine.grok_imagine import extract_story_headlines
        cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
        base = ROOT / "digests" / slug / stem
        script = Path(f"{base}_tts.txt").read_text(encoding="utf-8")
        digest = Path(f"{base}.md").read_text(encoding="utf-8")
        return [c.title for c in parse_chapters(
            script, cfg.chapters.section_markers, show_name=cfg.name,
            story_headlines=extract_story_headlines(digest, max_count=12),
            digest_text=digest if with_digest else "")]

    @pytest.mark.parametrize("stem", [
        "Models_Agents_Ep185_20260926", "Models_Agents_Ep189_20260930",
        "Models_Agents_Ep190_20261001"])
    def test_models_agents_deep_dive_recovered(self, stem):
        assert "Under the Hood" not in self._chapters("models_agents", stem, with_digest=False)
        assert "Under the Hood" in self._chapters("models_agents", stem)

    def test_a_healthy_episode_is_unchanged(self):
        stem = "Models_Agents_Ep191_20261002"
        assert (self._chapters("models_agents", stem)
                == self._chapters("models_agents", stem, with_digest=False))

    @pytest.mark.parametrize("stem", ["AI_Chips_Ep009_20260930", "AI_Chips_Ep014_20261005"])
    def test_ai_chips_teardown_recovered(self, stem):
        assert "The Teardown" in self._chapters("ai_chips", stem)


class TestTeardownPattern:
    def _rx(self):
        cfg = yaml.safe_load((ROOT / "shows" / "ai_chips.yaml").read_text(encoding="utf-8"))
        pat = next(m["pattern"] for m in cfg["chapters"]["section_markers"]
                   if m["title"] == "The Teardown")
        return re.compile(pat, re.IGNORECASE)

    @pytest.mark.parametrize("line", [
        "Take the flexible queue apart and the lever is which work is allowed to wait.",
        "Take the six-U G P U server apart and the limit shows up in the power shelf.",
        "Let's take it apart: the mechanism.",
    ])
    def test_matches_any_take_apart_sentence(self, line):
        assert self._rx().search(line)

    def test_does_not_span_sentences(self):
        assert not self._rx().search("We take a look. The parts sit apart.")

    def test_at_most_once_per_committed_episode(self):
        rx = self._rx()
        for path in glob.glob(str(ROOT / "digests" / "ai_chips" / "*_tts.txt")):
            text = Path(path).read_text(encoding="utf-8")
            assert len(rx.findall(text)) <= 1, path


class TestAiChipsHandsetExcludes:
    def _patterns(self):
        cfg = yaml.safe_load((ROOT / "shows" / "ai_chips.yaml").read_text(encoding="utf-8"))
        return [re.compile(p, re.IGNORECASE) for p in cfg["exclude_title_patterns"]]

    @pytest.mark.parametrize("title", [
        "Qualcomm Announces Snapdragon 8 Elite Gen 6: ServeTheHome",
        "Arm Congratulates vivo on New X500 Pro Series with Dimensity 9600 Pro",
        "Samsung smartphone shipments rise in Q3",
    ])
    def test_phone_launches_are_excluded(self, title):
        assert any(p.search(title) for p in self._patterns())

    @pytest.mark.parametrize("title", [
        "Qualcomm sticks with TSMC for both 2nm Snapdragon flagships: Digitimes",
        "Nvidia GB300 racks ship to Microsoft",
        "Power deal signed for 300 MW campus",
    ])
    def test_foundry_and_infrastructure_pass(self, title):
        assert not any(p.search(title) for p in self._patterns())

    def test_the_digest_prompt_rejects_phone_launches(self):
        text = (PROMPTS / "ai_chips_digest.txt").read_text(encoding="utf-8")
        assert "phone and handset chip launches" in text


# ---------------------------------------------------------------------------
# De-seeds (shape, never a quotable line)
# ---------------------------------------------------------------------------

class TestDeSeeds:
    @pytest.mark.parametrize("prompt,banned", [
        ("ai_chips_podcast.txt", "close on when the tradeoff flips"),
        ("unintended_consequences_episode.txt", '"incentive structures always find their loopholes,"'),
        ("unintended_consequences_episode.txt", '"complex systems resist simple interventions,"'),
        ("planetterrian_digest.txt", '"Right now, as you listen to this, your body is..."'),
        ("planetterrian_digest.txt", "Your gut has 38 trillion bacteria"),
        ("planetterrian_digest.txt", "You've probably heard that you lose most body heat"),
        ("planetterrian_podcast.txt", '("Now, shifting to..." or "On a different note..."'),
        ("planetterrian_podcast.txt", '"Next time, we\'ll be watching for..." or "Keep an eye on..."'),
        ("tesla_podcast.txt", "14–16 minute"),
    ])
    def test_specimen_is_gone(self, prompt, banned):
        assert banned not in (PROMPTS / prompt).read_text(encoding="utf-8")

    def test_planetterrian_teaser_keeps_its_chapter_anchor(self):
        text = (PROMPTS / "planetterrian_podcast.txt").read_text(encoding="utf-8")
        assert "Patrick: Before we go —" in text

    def test_ai_chips_teardown_keeps_its_anchor_and_bans_reading_the_title(self):
        text = (PROMPTS / "ai_chips_podcast.txt").read_text(encoding="utf-8")
        assert 'the phrase "take it apart" once' in text
        assert "never read its title out" in text

    def test_tesla_has_one_length_target(self):
        text = (PROMPTS / "tesla_podcast.txt").read_text(encoding="utf-8")
        assert len(re.findall(r"\d+–\d+ minute", text)) == 1
