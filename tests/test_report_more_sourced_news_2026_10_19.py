"""Oct 19 2026 — report the sourced news, never discard it (operator-directed).

Measured Oct 13-19: the prompt listed at most 40 of what a show fetched and
the digest carried 6-15 items of those — 8-25% of the list — while the depth
rules told the model to prefer fewer stories and the desks capped Also Today
at five. Now every news digest carries an Also Today run (one sentence per
remaining qualifying story, no cap), the prompt lists 60 articles, the depth
rules route a thin story to the run instead of cutting it, the run is spoken,
and the share of the list that ships is a metric.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "shows" / "prompts"
INCLUDE = "<<include: _shared/also_today.txt>>"

#: show -> the header that must follow the include (the run sits after the
#: last developed news section and before the show's deep dive / closing
#: sections).
INCLUDED = {
    "tesla": "## Short Spot",
    "spacex": "## Community Buzz",
    "fascinating_frontiers": "### Cosmic Spotlight",
    "planetterrian": "### Planetterrian Spotlight",
    "omni_view": "Then add a deep dive section:",
    "models_agents": "### Under the Hood",
    "env_intel": "### Practitioner Deep Dive",
    "ai_chips": "### The Teardown",
    "mag7": "### The Counterpoint",
    "vancouver": "### Getting Around",
    "collingwood": "### Roads & Weather Ahead",
    "prediction_markets": "### The Board",
    "longevity": "### Mechanism of the Week",
    "peptides": "### Peptide Spotlight",
}
#: The same run under the show's own section name.
OWN_RUN = {"models_agents_beginners": ("mab", "### Quick Bits"),
           "modern_investing": ("modern_investing", "### Quick Hits")}
DESKS = ("omni_view_europe", "omni_view_asia_pacific", "omni_view_africa_mideast",
         "omni_view_latam", "omni_view_north_america")


def _prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


class TestTheSharedRun:
    def test_the_section_is_uncapped_and_omitted_under_two(self):
        text = _prompt("_shared/also_today.txt")
        assert text.startswith("### Also Today\n")
        assert "Every remaining story" in text
        assert "one sentence each" in text
        assert "omitted, header included, when fewer than two qualify" in text
        assert "Source: [EXACT URL]" in text
        # No cap, no quotable specimen sentence (de-seed by shape).
        assert not re.search(r"\b(?:at most|up to|no more than) \d+", text, re.I)
        assert '"' not in text.replace('"huh', "")

    @pytest.mark.parametrize("slug,next_header", sorted(INCLUDED.items()))
    def test_each_news_show_includes_it_before_its_deep_dive(self, slug, next_header):
        text = _prompt(f"{slug}_digest.txt")
        assert text.count(INCLUDE) == 1, slug
        i = text.index(INCLUDE)
        j = text.index(next_header, i)
        between = text[i + len(INCLUDE):j]
        # Only whitespace or the ━━ rule sits between the run and the next header.
        assert not re.sub(r"[\s━]", "", between), (slug, between[:80])

    @pytest.mark.parametrize("slug,spec", sorted(OWN_RUN.items()))
    def test_quick_bits_and_quick_hits_follow_supply(self, slug, spec):
        name, header = spec
        text = _prompt(f"{name}_digest.txt")
        body = text[text.index(header):][:400]
        assert "Every remaining" in body, slug
        assert "never a filler" in body, slug
        assert not re.search(r"\b\d-\d shorter", body), slug

    def test_desks_keep_their_own_uncapped_run(self):
        body = _prompt("_shared/omni_desk_digest_body.txt")
        assert "### Also Today\n**Every remaining qualifying story, one sentence each**" in body
        assert "3 to 5" not in body
        assert "omitted when fewer than two" in body
        for desk in DESKS:
            assert INCLUDE not in _prompt(f"{desk}_digest.txt"), desk


class TestDepthRulesRouteInsteadOfCutting:
    def test_no_digest_prompt_prefers_fewer_stories(self):
        for p in PROMPTS.glob("*_digest.txt"):
            text = p.read_text(encoding="utf-8")
            assert "Prefer fewer stories at FULL depth" not in text, p.name
            assert "Prefer fewer Model Updates" not in text, p.name
            assert "not 12 shallowly" not in text, p.name

    @pytest.mark.parametrize("slug", ["fascinating_frontiers", "planetterrian", "tesla",
                                      "spacex", "models_agents", "omni_view"])
    def test_the_developed_sections_send_their_leftovers_to_the_run(self, slug):
        text = _prompt(f"{slug}_digest.txt")
        assert "Also Today" in text[:text.index(INCLUDE)], slug

    def test_the_expansion_retry_never_drops_a_sourced_story(self):
        from engine.generator import _build_digest_expansion_retry_prompt
        text = _build_digest_expansion_retry_prompt("draft", 100, 900)
        assert "Prefer FEWER items" not in text
        assert "never dropped" in text
        assert "Also Today" in text
        assert "Do NOT invent facts" in text

    def test_the_run_is_spoken(self):
        text = _prompt("_shared/content_discipline.txt")
        assert "The Also Today run is spoken, never skipped" in text
        assert "never introduced with a section name" in text
        # Every show that includes the run also includes the rule.
        for slug in INCLUDED:
            pod = _prompt(f"{slug}_podcast.txt")
            assert "<<include: _shared/content_discipline.txt>>" in pod, slug


class TestThePromptListsMore:
    def test_default_is_sixty_and_the_show_can_override(self):
        from engine.config import DEFAULT_MAX_PROMPT_ARTICLES, ShowConfig
        import dataclasses
        assert DEFAULT_MAX_PROMPT_ARTICLES == 60
        fields = {f.name: f for f in dataclasses.fields(ShowConfig)}
        assert fields["max_prompt_articles"].default == 0

    def test_run_show_reads_the_knob_and_keeps_hook_articles(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "MAX_ARTICLES_FOR_LLM = 40" not in src
        i = src.index("MAX_ARTICLES_FOR_LLM = int(")
        block = src[i:i + 2200]
        assert 'getattr(config, "max_prompt_articles", 0) or DEFAULT_MAX_PROMPT_ARTICLES' in block
        assert '"source_kind") == "hook"' in block
        assert 'metrics.record("articles_in_prompt", len(articles))' in block

    def test_a_yaml_value_reaches_the_config(self, tmp_path):
        from engine.config import load_config
        src = (ROOT / "shows" / "mag7.yaml").read_text(encoding="utf-8")
        (tmp_path / "_defaults.yaml").write_text(
            (ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "mag7.yaml").write_text(src + "\nmax_prompt_articles: 75\n", encoding="utf-8")
        cfg = load_config(tmp_path / "mag7.yaml")
        assert cfg.max_prompt_articles == 75
        assert load_config(ROOT / "shows" / "mag7.yaml").max_prompt_articles == 0


class TestTheRunIsMeasured:
    DIGEST = (
        "# Show\n> **A long enough hook sentence for the test.**\n\n"
        "### Top News\n1. **A developed story headline: Outlet**\n   Facts.\n   Source: https://a.example/1\n\n"
        "### Also Today\n"
        "**Second story headline of the day: Outlet**\nOne sentence with its fact.\nSource: https://a.example/2\n\n"
        "**Third story headline of the day: Outlet**\nOne sentence with its fact.\nSource: https://a.example/3\n\n"
        "### The Teardown: Thing\nProse.\n"
    )

    def test_also_today_items_counts_only_the_run(self):
        from engine.digest_lint import also_today_items, items_without_source
        assert also_today_items(self.DIGEST) == 2
        assert also_today_items(self.DIGEST.replace("### Also Today", "### Elsewhere")) == 0
        assert items_without_source(self.DIGEST) == (3, 0)

    def test_run_show_records_the_share(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        for key in ("items_shipped", "digest_also_today_items", "prompt_articles_reported_pct"):
            assert f'metrics.record("{key}"' in src, key

    def test_dashboard_reads_the_counters(self, tmp_path):
        import sys
        if str(ROOT / "scripts") not in sys.path:
            sys.path.insert(0, str(ROOT / "scripts"))
        import generate_dashboard as gd
        import datetime as dt
        import json
        show = tmp_path / "digests" / "showx"
        show.mkdir(parents=True)
        today = dt.date(2026, 10, 19)
        for ep in range(1, 7):
            d = today - dt.timedelta(days=ep - 1)
            (show / f"Show_Ep{ep:03d}_{d:%Y%m%d}.md").write_text("# x\n", encoding="utf-8")
            (show / f"metrics_ep{ep}.json").write_text(json.dumps({"counters": {
                "prompt_articles_reported_pct": 40.0, "digest_also_today_items": 5}}),
                encoding="utf-8")
        out = gd._episode_counter_shares(tmp_path, today)
        assert out["prompt_articles_reported_pct_7d"] == 40.0
        assert out["also_today_items_7d"] == 5.0
        assert gd._episode_counter_shares(tmp_path, today + dt.timedelta(days=30))[
            "prompt_articles_reported_pct_7d"] is None

    def test_the_register_names_the_metric(self):
        reg = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8"))
        entries = reg if isinstance(reg, list) else reg.get("experiments") or reg
        e = next(x for x in entries if x.get("id") == "report-more-sourced-news-2026-10-19")
        assert e["metric"] == "prompt_articles_reported_pct_7d"


class TestTheRunSitsOutsideEveryFloor:
    """A validator section whose span would otherwise run on into the Also
    Today run (and count its one-liners toward a developed floor) stops at it."""

    @pytest.mark.parametrize("slug,rule", [
        ("fascinating_frontiers", "Space Stories"), ("planetterrian", "Science Stories"),
        ("ai_chips", "Supply Chain & Policy"), ("mag7", "Company Desk"),
        ("vancouver", "The Closer Look"), ("collingwood", "The Closer Look"),
        ("prediction_markets", "The Ecosystem"), ("longevity", "The Week in Longevity"),
        ("peptides", "The Week in Peptides"),
    ])
    def test_the_section_before_the_run_ends_at_it(self, slug, rule):
        from engine.validation import SHOW_VALIDATION_CONFIGS
        cfg = SHOW_VALIDATION_CONFIGS[slug]
        cfg = cfg() if callable(cfg) else cfg
        r = next(s for s in cfg.sections if s.name == rule)
        assert "Also Today" in r.pattern, (slug, rule)
        pat = re.compile(r.pattern, re.S)
        text = ("### " + rule.replace("Space Stories", "Top 12 Space")
                .replace("Science Stories", "Top 12 Science")
                + "\n**A developed story headline: Outlet**\nFacts.\nSource: https://a/1\n\n"
                "### Also Today\n**Leftover story headline: Outlet**\nOne.\nSource: https://a/2\n\n"
                "### Next Section\nx\n")
        m = pat.search(text)
        assert m and "Leftover" not in m.group(1), (slug, rule)


class TestTheRunHasAChapter:
    @pytest.mark.parametrize("slug", sorted(INCLUDED))
    def test_every_show_with_the_run_anchors_its_chapter_on_the_digest(self, slug):
        data = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
        markers = data["chapters"]["section_markers"]
        m = [x for x in markers if x.get("title") == "Also Today"]
        assert len(m) == 1, slug
        assert m[0]["pattern"] == "also today"
        assert m[0]["where"] == "body"
        assert m[0]["digest_section"] == "Also Today"
