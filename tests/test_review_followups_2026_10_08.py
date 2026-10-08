"""Oct 8 2026 — an outside review of the Oct 6-8 slates, checked and acted on.

Verified against the committed files before anything changed (the review
doc lists what was rejected and why):

* Tesla Ep627's hook added "Tesla Megapack deployments" to a story whose
  item, source and claims ledger never mention them (Ep582 did the same).
  ``hook_supported`` is a Tesla digest lint; Ep627 carries a correction.
* AI Chips Ep016's Teardown and SpaceX Ep114's Engineering Deep Dive were
  deleted from their digests as cross-section "duplicates" (each cites a
  news item's report) while the audio kept them. Deep-dive sections are
  exempt from the overlap dedupe on both shows.
* Vancouver Ep013 printed a raw URL chain in a Source line: a linked first
  source followed by bare URLs. Every trailing URL is linked now.
* Nerra Daily, The Age of AI and Nerra Voices bypass run_show, so their feed
  items linked the MP3 (newest) or nothing (older). Both publishers pass the
  episode page, and the committed feeds were backfilled.
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.config import load_config  # noqa: E402
from engine.digest_lint import (  # noqa: E402
    LINTS,
    hook_names,
    hook_unsupported_names,
    run_digest_lints,
)
from engine.newsletter_body import shorten_source_urls  # noqa: E402


def _digest(glob_pat: str) -> str:
    return Path(glob.glob(str(ROOT / "digests" / glob_pat))[0]).read_text(encoding="utf-8")


class TestHookSupported:
    def test_registered_and_on_for_tesla(self):
        assert "hook_supported" in LINTS
        assert "hook_supported" in load_config(ROOT / "shows" / "tesla.yaml").digest_lints

    def test_ep627_fires_on_megapack(self):
        assert hook_unsupported_names(
            _digest("tesla_shorts_time/*Ep627_20261007.md")) == ["Megapack"]
        fired, metrics = run_digest_lints(
            _digest("tesla_shorts_time/*Ep627_20261007.md"), ["hook_supported"])
        assert [f.lint for f in fired] == ["hook_supported"]
        assert metrics["hook_unsupported_names"] == 1

    def test_a_supported_hook_passes(self):
        assert hook_unsupported_names(
            _digest("tesla_shorts_time/*Ep628_20261008.md")) == []

    def test_framing_words_are_not_names(self):
        assert hook_names(
            "Seventeen Korean customers in the South saw the Fed act in March") == []

    def test_precise_on_two_months_of_tesla(self):
        fired = []
        for md in sorted(glob.glob(str(ROOT / "digests/tesla_shorts_time/*_2026[01][089]*.md"))):
            if not re.search(r"_2026(08|09|10)\d\d\.md$", md):
                continue
            if hook_unsupported_names(Path(md).read_text(encoding="utf-8")):
                fired.append(Path(md).name)
        # Ep582 (Aug 24) and Ep627 (Oct 7): both a Megapack angle no item reports.
        assert len(fired) <= 3, fired

    def test_ep627_correction_is_filed(self):
        from engine.corrections import load_corrections
        entries = load_corrections(ROOT / "digests" / "tesla_shorts_time")
        e = next(c for c in entries if c["episode"] == 627)
        assert e["where"] == "both" and e["noted_in"] == 629
        assert "Megapack" in e["text"]


class TestDeepDivesSurviveTheDedupe:
    def test_exemptions(self):
        assert "The Teardown" in load_config(
            ROOT / "shows" / "ai_chips.yaml").digest_overlap_exempt_sections
        assert "Engineering Deep Dive" in load_config(
            ROOT / "shows" / "spacex.yaml").digest_overlap_exempt_sections

    def test_a_deep_dive_citing_a_news_items_source_is_kept(self):
        from engine.digest_overlap import dedupe_cross_section_items
        url = "https://www.datacenterknowledge.com/emea-93gw"
        digest = "\n".join([
            "# AI Chips & Data Centres Daily", "",
            "### Data Centres & Power",
            "**EMEA build shifts past FLAP-D: Data Center Knowledge**",
            f"DC Byte puts EMEA IT capacity at 93 GW across every stage. Source: {url}",
            "",
            "### The Teardown: What Ninety-Three Gigawatts Is Counting",
            "Deployed capacity is what is in service. The 93 GW stack is what has "
            f"been drawn, committed, started or switched on. Source: {url}",
            "",
            "### On the Horizon", "- Nothing dated.",
        ])
        kept = dedupe_cross_section_items(
            digest, exempt_sections=["On the Horizon", "The Teardown"]).text
        assert "Deployed capacity is what is in service" in kept
        dropped = dedupe_cross_section_items(digest, exempt_sections=["On the Horizon"]).text
        assert "Deployed capacity is what is in service" not in dropped, (
            "the fixture no longer reproduces the Ep016 deletion")


class TestSourceLinksNeverChain:
    def test_trailing_bare_urls_are_linked(self):
        line = ("Body. Source: [cbc.ca](https://www.cbc.ca/a) "
                "https://www.timescolonist.com/b, https://surreynowleader.com/c")
        out = shorten_source_urls(line)
        assert out == ("Body. Source: [cbc.ca](https://www.cbc.ca/a) · "
                       "[timescolonist.com](https://www.timescolonist.com/b) · "
                       "[surreynowleader.com](https://surreynowleader.com/c)")
        assert shorten_source_urls(out) == out

    def test_a_single_link_is_untouched(self):
        line = "Body. Source: [cbc.ca](https://www.cbc.ca/a)"
        assert shorten_source_urls(line) == line


class TestBypassFeedsLinkTheEpisodePage:
    def test_both_publishers_pass_the_page(self):
        for rel in ("scripts/build_daily_edition.py", "pipelines/voices/publish_episode.py"):
            src = (ROOT / rel).read_text(encoding="utf-8")
            assert "episode_page_url=" in src, rel
            assert "/blog/{" in src and "ep{episode_num:03d}.html" in src, rel

    def test_committed_feeds_link_every_item_to_a_page(self):
        for feed in ("nerra_daily_podcast.rss", "age_of_ai_podcast.rss",
                     "nerra_voices_podcast.rss"):
            text = (ROOT / feed).read_text(encoding="utf-8")
            for item in re.findall(r"<item>.*?</item>", text, re.S):
                link = re.search(r"<link>(.*?)</link>", item)
                assert link and link.group(1).startswith(
                    "https://nerranetwork.com/blog/"), (feed, item[:120])
