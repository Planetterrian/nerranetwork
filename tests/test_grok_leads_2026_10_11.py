"""Oct 11 2026 — @grok on X as a research desk, never a source.

engine/grok_leads.py: topical @grok explainer replies become deep-dive
ANGLES, each kept only when primary pages were fetched for it; the reply
itself never reaches the article list, a Source line or the claims gate.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from engine.config import load_config
from engine.grok_leads import (
    LEADS_HEADING, fetch_grok_leads, ground_leads, parse_leads, render_leads_block,
)

ROOT = Path(__file__).resolve().parent.parent
SHOWS = ("spacex", "tesla", "models_agents", "ai_chips")

REPLY = """LEAD_QUESTION: Why did Saturn V go from design freeze to first flight faster than SLS?
LEAD_ANSWER: Saturn V's configuration was locked in early 1962 and it first flew in
November 1967 under peak Cold War funding and all-up testing, while SLS began in 2011 with heritage mandates.
LEAD_URL: https://x.com/grok/status/2109212516890943659
LEAD_DATE: 2026-10-10

LEAD_QUESTION: lol
LEAD_ANSWER: haha
LEAD_URL: https://x.com/grok/status/1
LEAD_DATE: 2026-10-10
"""


def _page(url, n=600):
    return {"url": url, "title": f"Page {url[-1]}", "full_text_source": "page",
            "full_text": "word " * n}


class TestParse:
    def test_keeps_a_substantive_explainer_and_joins_wrapped_answers(self):
        leads = parse_leads(REPLY)
        assert len(leads) == 1
        assert leads[0]["answer"].endswith("heritage mandates.")
        assert "1967" in leads[0]["answer"]

    def test_no_leads(self):
        assert parse_leads("NO_LEADS") == []
        assert parse_leads("") == []

    def test_fetch_is_restricted_to_the_grok_handle_and_never_raises(self):
        seen = {}

        def fake(**kw):
            seen.update(kw)
            return REPLY, {}

        assert len(fetch_grok_leads("Starship", generate=fake)) == 1
        assert seen["x_handles"] == ["grok"] and seen["enable_x_search"] is True
        assert "Starship" in seen["prompt"]

        def boom(**kw):
            raise RuntimeError("search down")

        assert fetch_grok_leads("Starship", generate=boom) == []
        assert fetch_grok_leads("", generate=fake) == []


class TestGrounding:
    def _run(self, found_by_question, **kw):
        def research(q, brief, max_results):
            return found_by_question.get(q, [])

        paged = {a["url"] for v in found_by_question.values() for a in v if a.get("_page")}

        def enrich(arts, max_articles):
            for a in arts:
                if a["url"] in paged:
                    a.update(full_text_source="page", full_text="word " * 600)
            return len(arts)

        return ground_leads(parse_leads(REPLY), research=research, enrich=enrich, **kw)

    def test_a_lead_with_two_fetched_pages_is_kept(self):
        q = parse_leads(REPLY)[0]["question"]
        kept, sources = self._run({q: [
            {"url": "https://nasa.gov/a", "title": "A", "_page": True},
            {"url": "https://history.nasa.gov/b", "title": "B", "_page": True},
            {"url": "https://x.com/grok/status/9", "title": "Grok", "_page": True},
        ]})
        assert len(kept) == 1 and len(sources) == 2
        assert all("x.com" not in s["url"] for s in sources)
        assert all(s["source_kind"] == "research" for s in sources)

    def test_a_lead_without_enough_fetched_pages_is_dropped(self):
        q = parse_leads(REPLY)[0]["question"]
        kept, sources = self._run({q: [
            {"url": "https://nasa.gov/a", "title": "A", "_page": True},
            {"url": "https://b.example/b", "title": "B"},  # page not fetched
        ]})
        assert kept == [] and sources == []


class TestBlock:
    def test_block_names_grok_unverified_and_never_links_it(self):
        lead = {**parse_leads(REPLY)[0],
                "sources": [_page("https://nasa.gov/a"), _page("https://nasa.gov/b")]}
        block = render_leads_block([lead])
        assert block.startswith(LEADS_HEADING)
        assert "UNVERIFIED" in block and "never cite, quote or link x.com/grok" in block
        assert "https://x.com/grok/status" not in block
        assert "https://nasa.gov/a" in block

    def test_no_leads_renders_nothing(self):
        assert render_leads_block([]) == ""


class TestWiring:
    def test_four_deep_dive_shows_opt_in(self):
        for slug in SHOWS:
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml").grok_leads
            assert cfg.enabled and cfg.topics and cfg.min_sources >= 2, slug
        assert load_config(ROOT / "shows" / "omni_view.yaml").grok_leads.enabled is False

    def test_grok_is_never_an_x_source(self):
        for path in sorted((ROOT / "shows").glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            handles = {str(a.get("handle", "")).lower()
                       for a in (data.get("x_accounts") or []) if isinstance(a, dict)}
            assert "grok" not in handles, path.name

    def test_prompts_render_the_block(self):
        for slug in SHOWS:
            assert "{deep_dive_leads}" in (ROOT / "shows" / "prompts" / f"{slug}_digest.txt").read_text()

    def test_run_show_wires_leads_and_gate(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'template_vars.setdefault("deep_dive_leads"' in src
        assert "list(_grok_lead_sources" in src  # the claims gate reads the fetched pages
        assert 'metrics.record("grok_leads_kept"' in src
