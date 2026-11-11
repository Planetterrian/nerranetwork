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


# --- The Flight 15 preview special, and per-entry prompts -------------------

def _queue():
    data = yaml.safe_load((ROOT / "shows/deep_dives/spacex.yaml").read_text(encoding="utf-8"))
    topics = data["queue"] if isinstance(data, dict) else data
    return {t["id"]: t for t in topics}


def test_both_flight_entries_use_the_flight_prompts_and_they_exist():
    q = _queue()
    for tid in ("flight-15-preview", "flight-15-ship-catch"):
        entry = q[tid]
        for key in ("digest_prompt_file", "podcast_prompt_file"):
            assert "spacex_flight_special" in entry[key]
            assert (ROOT / entry[key]).is_file()
        assert entry["research_focus"].strip()


def _unproduced_queue(tmp_path) -> Path:
    """The real queue with the preview not yet produced.

    The picker only offers unproduced entries, and the preview was produced
    the evening these tests were written (Nov 10 2026, Ep158), which turned
    two of them red on main. A real queue is never the fixture for a state
    it will leave: the tests read a copy with the flag cleared.
    """
    data = yaml.safe_load((ROOT / "shows/deep_dives/spacex.yaml").read_text(encoding="utf-8"))
    for entry in data["queue"]:
        if entry.get("id") == "flight-15-preview":
            for key in ("produced", "episode_number", "produced_date"):
                entry.pop(key, None)
    path = tmp_path / "spacex.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def test_the_preview_is_pickable_by_id(tmp_path):
    from engine.topic_queue import pick_deep_dive_topic
    topic = pick_deep_dive_topic(
        _unproduced_queue(tmp_path), "2026-11-11",
        force_id="flight-15-preview")
    assert topic and topic["id"] == "flight-15-preview"


def test_a_produced_special_is_never_picked_again():
    """The other half of the same rule, read from the real queue: a forced
    id that has already aired returns nothing, so a re-run cannot publish
    the special twice."""
    from engine.topic_queue import pick_deep_dive_topic
    produced = [t for t in _queue().values() if t.get("produced") is True]
    for entry in produced:
        assert pick_deep_dive_topic(
            ROOT / "shows/deep_dives/spacex.yaml", "2026-11-11",
            force_id=entry["id"]) is None, entry["id"]


def test_the_flight_prompts_render_and_carry_no_earnings_furniture():
    from engine.generator import load_prompt
    digest = load_prompt(
        str(ROOT / "shows/prompts/spacex_flight_special.txt"),
        dict(today_str="November 11, 2026", topic_title="T", topic_brief="B",
             topic_category="event_special", current_research="R"))
    script = load_prompt(
        str(ROOT / "shows/prompts/spacex_flight_special_podcast.txt"),
        dict(episode_num=158, cold_open_spec="", delivery_spec="", hook="H",
             intro_line="I", closing_block="C", digest="D"))
    for text in (digest, script):
        assert "{" not in text
    for text in (digest, script):
        low = text.lower()
        for word in ("earnings", "capex", "balance sheet", "ebitda"):
            assert word not in low
    assert "## Sources" in digest
    # The chapter markers the show's YAML keys off.
    assert "One thing worth watching" in script
    assert "from an engineering standpoint" in script


def test_run_show_reads_the_entry_prompts_and_the_research_focus():
    src = (ROOT / "run_show.py").read_text(encoding="utf-8")
    assert 'deep_dive_topic.get(_pf)' in src
    assert '"deep_dive_prompt_missing"' in src
    assert 'focus=str(deep_dive_topic.get("research_focus")' in src


def test_research_focus_replaces_the_ipo_lead_line(monkeypatch):
    import digests.xai_grok as xg
    from engine import deep_dive_research as ddr
    seen = {}

    def fake(prompt, **kw):
        seen["prompt"] = prompt
        return "- a fact (https://example.com/a)", {}

    monkeypatch.setattr(xg, "grok_generate_text", fake)
    monkeypatch.setenv("GROK_API_KEY", "x")
    ddr.research_current_context("T", ["q"], focus="the launch window")
    assert "the launch window" in seen["prompt"]
    assert "underwriting" not in seen["prompt"]
    ddr.research_current_context("T", ["q"])
    assert "underwriting" in seen["prompt"]


def test_a_hand_typed_id_matches_whatever_its_case(tmp_path):
    from engine.topic_queue import pick_deep_dive_topic
    queue = _unproduced_queue(tmp_path)
    for typed in ("Flight-15-preview", " FLIGHT-15-PREVIEW ", "flight-15-preview"):
        picked = pick_deep_dive_topic(queue, "2026-11-10", force_id=typed)
        assert picked and picked["id"] == "flight-15-preview", typed
    assert pick_deep_dive_topic(queue, "2026-11-10", force_id="flight-16") is None
