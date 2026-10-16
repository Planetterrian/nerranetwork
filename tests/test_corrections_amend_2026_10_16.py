"""Oct 16 2026 — real corrections amend text surfaces, not only the note box.

When a correction carries ``replacements`` / ``headline``,
``apply_episode_amendments`` rewrites digest, transcripts and RSS so the
false claim is gone. The dated Correction box still renders.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import corrections as C  # noqa: E402


class TestAmendmentsRoundTrip:
    def test_replacements_and_headline_are_read(self, tmp_path):
        C.corrections_path(tmp_path).write_text(
            "- episode: 1\n  date: 2026-10-16\n  text: Wrong figure.\n"
            "  where: both\n  amend_headline: true\n"
            "  headline: Sales dropped 9.35 percent.\n"
            "  replacements:\n"
            "    - find: \"12 percent\"\n"
            "      replace: \"9.35 percent\"\n",
            encoding="utf-8",
        )
        rows = C.corrections_for(tmp_path, 1)
        assert rows[0]["headline"].startswith("Sales dropped")
        assert rows[0]["replacements"] == [
            {"find": "12 percent", "replace": "9.35 percent"}
        ]
        assert C.has_text_amendments(rows[0])

    def test_apply_rewrites_digest_hook_and_body(self, tmp_path):
        md = tmp_path / "Show_Ep001_20261016.md"
        md.write_text(
            "> **Sales dropped 12 percent year over year.**\n\n"
            "Tesla's China sales dropped 12 percent year over year.\n",
            encoding="utf-8",
        )
        (tmp_path / "Show_Ep001_20261016_tts.txt").write_text(
            "Sales dropped 12 percent year over year.\n\nBody.\n",
            encoding="utf-8",
        )
        C.corrections_path(tmp_path).write_text(
            "- episode: 1\n  date: 2026-10-16\n  text: CPCA was 9.35%.\n"
            "  where: digest\n"
            "  headline: Sales dropped 9.35 percent year over year.\n"
            "  replacements:\n"
            "    - find: \"12 percent\"\n"
            "      replace: \"9.35 percent\"\n",
            encoding="utf-8",
        )
        report = C.apply_episode_amendments(tmp_path, 1, dry_run=False)
        assert report["hits"] >= 2
        body = md.read_text(encoding="utf-8")
        assert "9.35 percent" in body
        assert "12 percent" not in body
        assert "Sales dropped 9.35 percent year over year." in body
        tts = (tmp_path / "Show_Ep001_20261016_tts.txt").read_text(encoding="utf-8")
        assert "12 percent" not in tts
        assert "9.35 percent" in tts

    def test_apply_rewrites_rss_item(self, tmp_path):
        rss = tmp_path / "show.rss"
        rss.write_text(
            '<?xml version="1.0"?><rss><channel>'
            "<item><title>Ep 2: Later episode</title>"
            "<link>https://nerranetwork.com/blog/show/ep2.html</link>"
            "<description>Correction to episode 1: Sales dropped 12 percent was wrong."
            "</description>"
            "<itunes:episode>2</itunes:episode>"
            "<guid>show-ep2-x</guid></item>"
            "<item><title>Ep 1: Sales dropped 12 percent…</title>"
            "<link>https://nerranetwork.com/blog/show/ep1.html</link>"
            "<description>&lt;b&gt;Sales dropped 12 percent year over year.&lt;/b&gt;"
            " More text with 12 percent.</description>"
            "<itunes:episode>1</itunes:episode>"
            "<guid>show-ep1-x</guid></item>"
            "</channel></rss>",
            encoding="utf-8",
        )
        (tmp_path / "Show_Ep001_20261016.md").write_text(
            "> **Sales dropped 12 percent year over year.**\n",
            encoding="utf-8",
        )
        C.corrections_path(tmp_path).write_text(
            "- episode: 1\n  date: 2026-10-16\n  text: Fix.\n  where: digest\n"
            "  headline: Sales dropped 9.35 percent year over year.\n"
            "  replacements:\n"
            "    - find: \"12 percent\"\n"
            "      replace: \"9.35 percent\"\n",
            encoding="utf-8",
        )
        n = C.amend_rss_feed(rss, 1, C.corrections_for(tmp_path, 1)[0], dry_run=False)
        assert n >= 1
        out = rss.read_text(encoding="utf-8")
        # Ep 1 amended; Ep 2's carried-correction mention of "12 percent" stays
        # (it is quoting the error) — identity match must not select Ep 2.
        assert "<title>Ep 2: Later episode</title>" in out
        assert "Ep 1: Sales dropped 9.35 percent" in out
        assert "Ep 1: Sales dropped 12 percent" not in out

    def test_dry_run_does_not_write(self, tmp_path):
        md = tmp_path / "Show_Ep001_20261016.md"
        original = "> **Hook with 12 percent.**\n\nBody 12 percent.\n"
        md.write_text(original, encoding="utf-8")
        C.corrections_path(tmp_path).write_text(
            "- episode: 1\n  date: 2026-10-16\n  text: x\n"
            "  replacements:\n    - find: \"12 percent\"\n      replace: \"9.35 percent\"\n",
            encoding="utf-8",
        )
        C.apply_episode_amendments(tmp_path, 1, dry_run=True)
        assert md.read_text(encoding="utf-8") == original


class TestLiveEpisodesCorrected:
    """The two episodes the Oct 15 review flagged must be amended on disk."""

    def test_uc_139_yaml_carries_amendments(self):
        rows = C.corrections_for(ROOT / "digests/unintended_consequences", 139)
        assert rows
        assert rows[0]["amend_headline"] is True
        assert C.has_text_amendments(rows[0])
        assert "Argentine" in rows[0]["text"]
        assert any("Argentine government" in r["find"] for r in rows[0]["replacements"])

    def test_tesla_634_yaml_carries_amendments(self):
        rows = C.corrections_for(ROOT / "digests/tesla_shorts_time", 634)
        assert rows
        assert C.has_text_amendments(rows[0])
        assert "9.35" in rows[0]["headline"]
        assert any("12 percent" in r["find"] for r in rows[0]["replacements"])

    def test_uc_139_digest_no_longer_asserts_argentina(self):
        matches = sorted(
            (ROOT / "digests/unintended_consequences").glob(
                "Unintended_Consequences_Ep139_*.md"
            )
        )
        matches = [m for m in matches if "_claims" not in m.name]
        assert matches
        text = matches[-1].read_text(encoding="utf-8")
        assert "The Argentine government had issued" not in text
        assert "Argentine-flagged" not in text
        assert "Government of South Georgia" in text
        assert "unsupported" in text.lower() or "Corrected" in text or "Britain" in text

    def test_tesla_634_digest_uses_cpca_figure(self):
        matches = sorted(
            (ROOT / "digests/tesla_shorts_time").glob(
                "Tesla_Shorts_Time_Pod_Ep634_*.md"
            )
        )
        matches = [m for m in matches if "_claims" not in m.name]
        assert matches
        text = matches[-1].read_text(encoding="utf-8")
        assert "12 percent" not in text
        assert "9.35 percent" in text
