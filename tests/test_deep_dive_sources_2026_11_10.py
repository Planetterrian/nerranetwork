"""Nov 10 2026: a deep-dive special's Sources come from its own research.

The Flight 15 special (run Nov 10) skipped at the publish guard because a
deep dive fetches no articles and its prompts never ask for Source lines.
"""
from pathlib import Path

import yaml

from engine.deep_dive_research import append_research_sources, research_source_urls
from engine.publish_guards import digest_has_rendered_sources

ROOT = Path(__file__).resolve().parents[1]

RESEARCH = (
    "- Flight 15 has not launched.[[1]](https://www.spacex.com/launches/starship-flight-15)"
    "[[2]](https://en.wikipedia.org/wiki/Starship_flight_15)\n"
    "- NET November 13 per https://www.spacex.com/launches/starship-flight-15.\n"
)


def test_urls_are_read_from_the_briefing_in_order_and_deduped():
    assert research_source_urls(RESEARCH) == [
        "https://www.spacex.com/launches/starship-flight-15",
        "https://en.wikipedia.org/wiki/Starship_flight_15",
    ]


def test_a_digest_with_no_sources_gets_the_research_links():
    digest = "**HOOK:** Flight 15 special.\n\n## The moment\n\nSome prose.\n"
    assert not digest_has_rendered_sources(digest)
    out, n = append_research_sources(digest, RESEARCH)
    assert n == 2
    assert digest_has_rendered_sources(out)


def test_a_digest_that_cites_a_url_is_unchanged():
    digest = "Prose.\nSource: https://example.com/story\n"
    out, n = append_research_sources(digest, RESEARCH)
    assert (out, n) == (digest, 0)


def test_no_research_adds_nothing_so_the_guard_still_skips():
    digest = "Prose with no links.\n"
    out, n = append_research_sources(digest, "")
    assert (out, n) == (digest, 0)
    assert not digest_has_rendered_sources(out)


def test_run_show_appends_before_the_digest_is_saved():
    src = (ROOT / "run_show.py").read_text(encoding="utf-8")
    i_add = src.index("append_research_sources(")
    i_save = src.index('logger.info("Digest saved: %s", digest_md)')
    i_guard = src.index("check_publish_guards(\n")
    assert i_add < i_save < i_guard


def test_spacex_specials_get_a_special_sized_digest_budget():
    cfg = yaml.safe_load((ROOT / "shows/spacex.yaml").read_text(encoding="utf-8"))
    assert cfg["deep_dive"]["max_tokens"] >= 8000
    from engine.config import load_config
    assert load_config(ROOT / "shows/spacex.yaml").deep_dive.max_tokens == cfg["deep_dive"]["max_tokens"]
