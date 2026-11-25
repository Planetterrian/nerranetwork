"""Flagship quality pass, Nov 24 2026 (SpaceX Daily + Tesla Shorts Time).

Review: docs/reviews/flagship_quality_review_2026_11_24.md.

What these pin:

1. ``engine/market_calendar.py`` — "closed <day> at" follows the NYSE
   calendar: a Monday pre-open episode says Friday, the day after
   Thanksgiving says Wednesday.
2. ``engine/market_move.py`` — a move of 4% or more gets ONE search for dated
   reporting; a reason is never written by the pipeline, and an undated page
   is never evidence for this session.
3. Both digest prompts carry ``{market_move_section}`` and its rule, and
   every run renders it (empty by default).
4. Chapters: a one-sentence second telling yields its chapter to the story
   after it (SpaceX Ep172); the bare "takeover" marker is gone (Tesla Ep674).
5. Tesla's Short Spot keeps its story when it repeats a Top 12 item.
6. ``item_names_sourced_measure`` reads Ep172's "Britain" and never fires.
7. The SpaceX deep dive is written for the ear.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "fixtures" / "flagship_2026_11_24"

from engine import digest_lint as dl  # noqa: E402
from engine import market_calendar as mc  # noqa: E402
from engine import market_move as mm  # noqa: E402
from engine.digest_overlap import dedupe_cross_section_items  # noqa: E402


def _utc(y, m, d, h=11, mi=0):
    return dt.datetime(y, m, d, h, mi, tzinfo=dt.timezone.utc)


class TestMarketCalendar:
    def test_weekend_and_monday_pre_open_say_friday(self):
        assert mc.close_day_word(_utc(2026, 11, 21)) == " Friday"   # Saturday
        assert mc.close_day_word(_utc(2026, 11, 22)) == " Friday"   # Sunday
        assert mc.close_day_word(_utc(2026, 11, 23)) == " Friday"   # Monday 6am ET

    def test_ordinary_weekday_morning_has_no_day_word(self):
        assert mc.close_day_word(_utc(2026, 11, 24)) == ""          # Tuesday

    def test_after_the_open_there_is_no_day_word(self):
        assert mc.close_day_word(_utc(2026, 11, 23, 16)) == ""      # Monday 11am ET

    def test_thanksgiving_and_the_day_after_say_wednesday(self):
        assert not mc.is_trading_day(dt.date(2026, 11, 26))
        assert mc.close_day_word(_utc(2026, 11, 26)) == " Wednesday"
        assert mc.close_day_word(_utc(2026, 11, 27)) == " Wednesday"

    def test_new_year_weekend(self):
        assert not mc.is_trading_day(dt.date(2027, 1, 1))
        assert mc.close_day_word(_utc(2027, 1, 4)) == " Thursday"

    def test_after_the_close_the_session_is_today(self):
        # The Nov 24 rehearsals ran at 22:58 UTC (5:58pm Eastern).
        assert mc.close_session_date(_utc(2026, 11, 24, 22, 58)) == dt.date(2026, 11, 24)
        assert mc.close_session_date(_utc(2026, 11, 24, 11)) == dt.date(2026, 11, 23)
        assert mc.close_session_date(_utc(2026, 11, 28, 23)) == dt.date(2026, 11, 27)  # Saturday

    def test_holidays_by_rule(self):
        h = mc.holidays(2026)
        for day in ((1, 1), (1, 19), (2, 16), (4, 3), (5, 25), (6, 19),
                    (7, 3), (9, 7), (11, 26), (12, 25)):
            assert dt.date(2026, *day) in h, day

    def test_both_hooks_use_the_one_calendar(self):
        for hook in ("tesla", "spacex"):
            src = (ROOT / "shows" / "hooks" / f"{hook}.py").read_text(encoding="utf-8")
            assert "market_calendar" in src, hook

    def test_tesla_monday_closing_says_friday(self):
        from shows.hooks import tesla as hook
        text = hook._pick_closing(
            {"price": "385.46", "change_str": "▲ $39.64 (11.5%)"},
            date=dt.date(2026, 11, 23))
        assert "closed Friday at" in text


class TestMarketMove:
    def test_parse_both_hook_shapes(self):
        assert mm.parse_pct("▲ $39.64 (11.5%)") == 11.5
        assert mm.parse_pct("▼ $28.59 (7.6%)") == -7.6
        assert mm.parse_pct("+4.4%") == 4.4
        assert mm.parse_pct("-7.7%") == -7.7
        assert mm.parse_pct("") is None

    def test_below_the_bar_is_not_a_move(self):
        assert mm.describe("TSLA", "Tesla", "▲ $3.10 (0.9%)", now=_utc(2026, 11, 24)) is None
        assert mm.describe("TSLA", "Tesla", "▼ $12.00 (3.9%)", now=_utc(2026, 11, 24)) is None

    def test_a_move_in_progress_is_not_described(self):
        assert mm.describe("TSLA", "Tesla", "▲ $20.00 (6.0%) Pre-market",
                           now=_utc(2026, 11, 24)) is None

    def test_describe_names_the_session(self):
        move = mm.describe("TSLA", "Tesla", "▲ $39.64 (11.5%)", price=385.46,
                           now=_utc(2026, 11, 24))
        assert move["direction"] == "up" and move["pct"] == 11.5
        assert move["session_date"] == "2026-11-23"
        assert "Monday, November 23, 2026" == move["session_label"]

    def _move(self):
        return mm.describe("SPCX", "SpaceX", "-7.7%", now=_utc(2026, 11, 20))

    def test_only_dated_reports_inside_the_window_are_kept(self):
        found = [
            {"title": "Old explainer", "url": "https://a.example/1", "published_date": "2026-10-02"},
            {"title": "No date", "url": "https://a.example/2", "published_date": ""},
            {"title": "A post", "url": "https://x.com/u/status/1", "published_date": "2026-11-19"},
            {"title": "The report", "url": "https://a.example/3", "published_date": "2026-11-19T21:10:00Z"},
            {"title": "Next morning", "url": "https://a.example/4", "published_date": "2026-11-20"},
        ]
        kept = mm.fetch_move_articles(self._move(), research=lambda *a, **k: found,
                                      today=dt.date(2026, 11, 20))
        assert [a["title"] for a in kept] == ["The report", "Next morning"]
        assert all(a["source_kind"] == mm.SOURCE_KIND_MARKET_MOVE for a in kept)

    def test_a_failed_search_costs_nothing(self):
        def boom(*a, **k):
            raise RuntimeError("search down")
        assert mm.fetch_move_articles(self._move(), research=boom,
                                      today=dt.date(2026, 11, 20)) == []

    def test_the_block_states_facts_and_never_a_reason(self):
        none = mm.render_block(self._move(), [])
        assert "SPCX closed down 7.7%" in none
        assert "No dated report" in none
        some = mm.render_block(self._move(), [{"title": "The report", "url": "https://a.example/3"}])
        assert "The report" in some and "No dated report" not in some
        assert mm.render_block(None) == ""
        for text in (none, some):
            assert "because" not in text.lower()

    def test_prompts_carry_the_block_and_its_rule(self):
        for name in ("tesla_digest.txt", "spacex_digest.txt"):
            text = (ROOT / "shows" / "prompts" / name).read_text(encoding="utf-8")
            assert "{market_move_section}" in text, name
            assert "MARKET MOVE RULE" in text, name

    def test_every_run_renders_the_placeholder(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'template_vars.setdefault("market_move_section", "")' in src
        assert "fetch_move_articles" in src
        for hook in ("tesla", "spacex"):
            hsrc = (ROOT / "shows" / "hooks" / f"{hook}.py").read_text(encoding="utf-8")
            assert 'context["market_move_section"] = ""' in hsrc, hook

    def test_no_other_show_prompt_needs_the_placeholder(self):
        # A show whose prompt carries the placeholder must have a hook that
        # can fill it; today that is the two flagships only.
        carriers = sorted(p.name for p in (ROOT / "shows" / "prompts").glob("*.txt")
                          if "{market_move_section}" in p.read_text(encoding="utf-8"))
        assert carriers == ["spacex_digest.txt", "tesla_digest.txt"]


def _chapters(slug, stem):
    from engine.chapters import parse_chapters
    from engine.config import load_config
    from engine.grok_imagine import extract_story_headlines
    cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
    digest = (FIX / f"{stem}.md").read_text(encoding="utf-8")
    script = (FIX / f"{stem}_tts.txt").read_text(encoding="utf-8")
    chapters = parse_chapters(
        script, cfg.chapters.section_markers, show_name=cfg.name,
        story_headlines=extract_story_headlines(digest, max_count=12),
        digest_text=digest,
        known_sections_only=getattr(cfg.chapters, "known_sections_only", False))
    words = script.split()
    return [(c.title, " ".join(words[c.word_start:c.word_start + 8])) for c in chapters]


class TestChapters:
    def test_spacex_ep172_debris_story_has_its_own_chapter(self):
        chapters = _chapters("spacex", "SpaceX_Daily_Ep172_20261124")
        titles = [t for t, _w in chapters]
        assert any(t.startswith("Profepa Reports") for t in titles), titles
        # The chapter that sat over the debris story before the fix.
        for title, opening in chapters:
            if "Profepa" in opening:
                assert title.startswith("Profepa"), (title, opening)

    def test_tesla_ep674_opens_on_introduction(self):
        chapters = _chapters("tesla", "Tesla_Shorts_Time_Pod_Ep674_20261123")
        assert chapters[0][0] == "Introduction"
        assert "Tesla X Takeover" not in [t for t, _w in chapters[:2]]

    def test_the_bare_takeover_marker_is_gone(self):
        cfg = yaml.safe_load((ROOT / "shows" / "tesla.yaml").read_text(encoding="utf-8"))
        patterns = [m.get("pattern", "") for m in cfg["chapters"]["section_markers"]]
        assert "Tesla X Takeover" in patterns
        assert not any("|takeover" in p for p in patterns)


_DIGEST = """# Tesla Shorts Time
**Date:** x

### Top 12 News Items

1. **Cybercab opens rides in Dallas: Teslarati**
   Tesla opened public Cybercab rides in Dallas on Monday with forty vehicles. Source: https://a.example/dallas

2. **Tesla sales in China fall 20 percent in October: Reuters**
   China Passenger Car Association data showed Tesla retail sales fell twenty percent year over year in October. Source: https://b.example/china

3. **Megapack plant ships unit 1,000: Electrek**
   The Houston Megapack plant shipped its thousandth unit this week. Source: https://c.example/mega

## Short Spot

**{title}**
{body} Source/Post: {url}

### Tesla First Principles
Essay text here about batteries and the cost of cells over time in plain words.
"""


class TestShortSpotKeepsItsStory:
    CHINA = dict(title="China sales slide deepens for Tesla: Reuters",
                 body="Tesla retail sales in China fell twenty percent in October, the CPCA said, as BYD gained share.",
                 url="https://b.example/china")
    LEAD = dict(title="Cybercab Dallas rides open with forty vehicles: Teslarati",
                body="Tesla opened public Cybercab rides in Dallas with forty vehicles on Monday.",
                url="https://a.example/dallas")

    def test_default_is_unchanged(self):
        out = dedupe_cross_section_items(_DIGEST.format(**self.CHINA))
        assert "China sales slide" not in out.text
        assert "fall 20 percent" in out.text

    def test_claiming_section_keeps_the_story_once(self):
        out = dedupe_cross_section_items(_DIGEST.format(**self.CHINA),
                                         claiming_sections=["Short Spot"])
        assert "China sales slide" in out.text
        assert "fall 20 percent" not in out.text
        assert "2. **Megapack" in out.text           # renumbered
        assert out.count == 1 and out.removed[0].section == "Top 12 News Items"

    def test_the_lead_is_never_given_up(self):
        out = dedupe_cross_section_items(_DIGEST.format(**self.LEAD),
                                         claiming_sections=["Short Spot"])
        assert "1. **Cybercab opens rides in Dallas" in out.text
        assert "forty vehicles on Monday" not in out.text

    def test_tesla_and_only_tesla_sets_it(self):
        setters = []
        for path in sorted((ROOT / "shows").glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if data.get("digest_overlap_claiming_sections"):
                setters.append((path.stem, data["digest_overlap_claiming_sections"]))
        assert setters == [("tesla", ["Short Spot"])]

    def test_the_config_reads_it(self):
        from engine.config import load_config
        cfg = load_config(str(ROOT / "shows" / "tesla.yaml"))
        assert cfg.digest_overlap_claiming_sections == ["Short Spot"]
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "digest_overlap_claiming_sections" in src


class TestItemNamesMeasure:
    URL = "https://www.neoteo.com/en/himes-ties-his-support-for-spacex-funding-to-starshield-answers"
    PAGE = ("Representative James Himes of Connecticut ties support for SpaceX funding to "
            "Starshield answers. Himes sent separate requests to National Intelligence "
            "Director Jay Clayton and Elon Musk. CNN reported two rounds of speed "
            "restrictions over occupied territories in Ukraine in October. U.S. "
            "government officials. ") * 12

    def _digest(self):
        return (FIX / "SpaceX_Daily_Ep172_20261124.md").read_text(encoding="utf-8")

    def test_ep172_britain_is_in_no_source(self):
        ctx = {"articles": [{"url": self.URL, "title": "Himes ties his support", "full_text": self.PAGE}]}
        judged, missing = dl.item_unsourced_names(self._digest(), ctx)
        assert judged == 1
        assert "British" in missing or "Britain" in missing
        assert "Himes" not in missing and "Clayton" not in missing

    def test_it_measures_and_never_fires(self):
        ctx = {"articles": [{"url": self.URL, "title": "t", "full_text": self.PAGE}]}
        fired, metrics = dl.run_digest_lints(self._digest(), ["item_names_sourced_measure"], ctx)
        assert fired == []
        assert metrics["item_names_judged_items"] == 1
        assert metrics["item_names_unsourced"] >= 1

    def test_an_unread_source_is_not_judged(self):
        ctx = {"articles": [{"url": self.URL, "title": "t", "full_text": "short"}]}
        assert dl.item_unsourced_names(self._digest(), ctx) is None

    def test_listed_on_both_flagships(self):
        for slug in ("tesla", "spacex"):
            data = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            assert "item_names_sourced_measure" in data["digest_lints"], slug
        assert "item_names_sourced_measure" in dl.CONTEXT_LINTS


class TestPrompts:
    def _read(self, name):
        return (ROOT / "shows" / "prompts" / name).read_text(encoding="utf-8")

    def test_spacex_deep_dive_is_for_the_ear(self):
        text = self._read("spacex_podcast.txt")
        assert "NUMBERS FOR THE EAR" in text
        assert "SHOW THE WORKING" not in text

    def test_spacex_length_matches_what_the_show_runs(self):
        text = self._read("spacex_podcast.txt")
        assert "9–12 minute" in text and "11–14 minute" not in text

    def test_spacex_digest_rules(self):
        text = self._read("spacex_digest.txt")
        assert "NAMED HARDWARE AND CAUSES" in text

    def test_tesla_first_principles_is_the_whole_essay(self):
        text = self._read("tesla_podcast.txt")
        assert "60–90 seconds" not in text

    def test_prompts_still_render(self):
        for name in ("tesla_digest.txt", "spacex_digest.txt"):
            raw = self._read(name)
            assert raw.count("{market_move_section}") == 1, name
