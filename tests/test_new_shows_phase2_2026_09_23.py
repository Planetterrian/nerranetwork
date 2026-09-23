"""Guards for new-shows Phase 2 and the Sep 23 2026 operator brief.

Phase 2 is Mira's two local shows (docs/new_shows_plan_2026_09_22.md §4.5-4.6):
Vancouver Daily News and Collingwood Weekly, the first run_show shows with an
AI host. The same day the operator asked for (1) grok-4.7 on every new show,
(2) MAG 7 and every new show about developments rather than prices and
earnings calendars, and (3) Longevity and Peptides about education rather
than the commercial drug pipeline. Each guard names what it protects.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PHASE2 = ("vancouver", "collingwood")
NEW_SHOWS = ("ai_chips", "mag7", "peptides", "longevity") + PHASE2


def _cfg(slug):
    from engine.config import load_config
    return load_config(ROOT / "shows" / f"{slug}.yaml")


def _prompt(name: str) -> str:
    return (ROOT / "shows" / "prompts" / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# engine/local_conditions.py — roads and weather as sourced hook articles
# ---------------------------------------------------------------------------

def _drivebc_event(**kw):
    ev = {
        "event_type": "CONSTRUCTION", "severity": "MINOR",
        "updated": "2026-09-22T10:00:00-07:00",
        "description": "Work at Main St. Last update: September 22nd, 2026 at 10:00am PDT.",
        "geography": {"type": "Point", "coordinates": [-123.1, 49.25]},
        "roads": [{"name": "Highway 1"}],
    }
    ev.update(kw)
    return ev


class TestDriveBC:
    NOW = dt.datetime(2026, 9, 23, 12, 0, tzinfo=dt.timezone.utc)

    def _run(self, events):
        from engine.local_conditions import drivebc_article
        return drivebc_article(fetch=lambda url: {"events": events}, now=self.NOW)

    def test_keeps_majors_and_fresh_incidents_only(self):
        art = self._run([
            _drivebc_event(severity="MAJOR", description="Bridge closed overnight."),
            _drivebc_event(description="Line painting."),                     # minor work
            _drivebc_event(event_type="INCIDENT", description="Crash, right lane blocked.",
                           updated="2026-09-23T04:00:00-07:00"),
            _drivebc_event(event_type="INCIDENT", description="Washout.",       # months old
                           updated="2026-03-01T10:00:00-08:00"),
        ])
        body = art["content_text"]
        assert "Bridge closed overnight" in body and "Crash, right lane blocked" in body
        assert "Line painting" not in body and "Washout" not in body
        # Incidents lead.
        assert body.index("Crash") < body.index("Bridge closed")
        assert "Last update" not in body
        assert art["exempt_stale"] is True and art["url"].startswith("https://")

    def test_stays_inside_metro_vancouver(self):
        """The first probe's top 'Lower Mainland' event was a washout near
        Hope — the DriveBC district runs to the Fraser Canyon."""
        art = self._run([_drivebc_event(severity="MAJOR", description="Hope closure.",
                                        geography={"type": "Point", "coordinates": [-121.41, 49.37]})])
        assert art is None

    def test_network_failure_degrades_to_none(self):
        from engine.local_conditions import drivebc_article

        def boom(url):
            raise OSError("down")
        assert drivebc_article(fetch=boom) is None


class TestOntario511:
    def test_box_filter_and_day_night_dedup(self):
        from engine.local_conditions import ontario511_article
        events = [
            {"RoadwayName": "HWY 26", "Description": "Nightly Construction on HWY 26 between A and B.",
             "Latitude": 44.5, "Longitude": -80.2, "IsFullClosure": True, "EventType": "roadwork"},
            {"RoadwayName": "HWY 26", "Description": "Daily Construction on HWY 26 between A and B.",
             "Latitude": 44.5, "Longitude": -80.2, "IsFullClosure": True, "EventType": "roadwork"},
            {"RoadwayName": "HWY 401", "Description": "London closure.",
             "Latitude": 42.85, "Longitude": -81.27, "EventType": "roadwork"},
        ]
        art = ontario511_article((44.35, -80.65, 44.62, -79.95), "Collingwood",
                                 fetch=lambda url: events)
        assert art["content_text"].count("HWY 26:") == 1
        assert "London" not in art["content_text"]


class TestWeather:
    FEED = """<feed><entry><title>No watches or warnings in effect, Vancouver</title>
<updated>x</updated><summary type="html">No watches or warnings in effect.</summary></entry>
<entry><title>Current Conditions: Mostly Cloudy, 16.9°C</title><updated>x</updated>
<summary type="html"><![CDATA[<b>Observed at:</b> YVR]]></summary></entry>
<entry><title>Wednesday: Showers. High 17.</title><updated>x</updated>
<summary type="html">A few showers ending early. High 17. Forecast issued 4:00 PM PDT Tuesday 22 September 2026</summary></entry>
</feed>"""

    def test_parses_periods_without_the_issue_stamp(self):
        from engine.local_conditions import weather_article
        art = weather_article(49.245, -123.115, "Vancouver", fetch=lambda url: self.FEED)
        body = art["content_text"]
        assert "No watches or warnings in effect." in body
        assert "- Wednesday: A few showers ending early. High 17." in body
        assert "Forecast issued" not in body
        assert art["url"] == "https://weather.gc.ca/rss/weather/49.245_-123.115_e.xml"

    def test_the_old_city_path_is_not_used(self):
        """weather.gc.ca/rss/city/<code>_e.xml answered 404 on 2026-09-23."""
        src = (ROOT / "engine" / "local_conditions.py").read_text(encoding="utf-8")
        assert "/rss/weather/" in src and "/rss/city/{" not in src


class TestConditionsBlock:
    def test_no_data_means_one_honest_sentence(self):
        from engine.local_conditions import conditions_block
        block = conditions_block([], "Getting Around")
        assert "ONE sentence" in block and "never a forecast or a closure from memory" in block

    def test_with_data_the_section_is_built_from_the_articles_only(self):
        from engine.local_conditions import conditions_block
        block = conditions_block([{"source_name": "DriveBC"}], "Getting Around")
        assert "ONLY from these articles" in block and "DriveBC" in block


@pytest.mark.parametrize("slug", PHASE2)
def test_hook_returns_articles_and_the_section_instruction(slug, monkeypatch):
    import importlib

    import engine.local_conditions as LC
    mod = importlib.import_module(f"shows.hooks.{slug}")
    monkeypatch.setattr(mod, "gather", lambda builders: [
        {"title": "t", "url": "https://x", "source_name": "Environment Canada"}])
    monkeypatch.setattr(mod.show_memory, "memory_pre_fetch", lambda cfg, s: {})
    ctx = mod.pre_fetch(_cfg(slug))
    assert ctx["articles"][0]["url"] == "https://x"
    assert "ONLY from these articles" in ctx["hook_context"]
    assert LC  # module import is the contract the hook relies on


# ---------------------------------------------------------------------------
# The two shows' wiring
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slug", PHASE2)
class TestPhase2Wiring:
    def test_ai_host_config(self, slug):
        c = _cfg(slug)
        assert c.publishing.host_kind == "ai" and c.publishing.host_name == "Mira"
        assert c.tts.voice_id == "ara"
        # Nerra Daily's Mira is synthesized without a wrap; the <fast> default
        # was tuned on Patrick's voice.
        assert c.tts.speech_wrap_open == "" and c.tts.speech_wrap_close == ""
        assert "Patrick" not in c.publishing.rss_author

    def test_launch_shape(self, slug):
        c = _cfg(slug)
        assert c.max_weekly_cost_usd > 0
        assert c.youtube.enabled is False and c.newsletter.enabled is False
        assert c.publishing.x_enabled is False
        assert c.llm.model == "grok-4.7"

    def test_phase1_lessons_are_defaults(self, slug):
        """docs/new_shows_plan_2026_09_22.md §9a."""
        c = _cfg(slug)
        assert c.absence_sentence_filter is True
        assert c.fetch_full_text >= 10
        assert 900 <= c.llm.min_podcast_words <= 1300
        assert c.llm.podcast_expand_below_target is False
        starts = [m for m in c.chapters.section_markers if m.where == "start"]
        assert starts and "first episode of" in starts[0].pattern

    def test_voice_only_audio_has_no_intro_offset(self, slug):
        c = _cfg(slug)
        assert not c.audio.music_file
        assert c.audio.intro_duration == 0 and c.audio.voice_intro_delay == 0

    def test_prompts(self, slug):
        dig = _prompt(f"{slug}_digest.txt")
        pod = _prompt(f"{slug}_podcast.txt")
        system = _prompt(f"{slug}_system.txt")
        assert "REGION FIRST" in dig and "{hook_context}" in dig
        assert "NO ABSENCE SENTENCES" in dig
        assert "<<include: _shared/interesting_first.txt>>" in dig
        assert "**Title:" not in dig and "Source Name**" not in dig
        assert "<<include: _shared/content_discipline.txt>>" in pod
        assert "COVERAGE: every item in the briefing is told" in pod
        # Mira never claims a body or a place.
        assert "Mira is an AI" in system and "Mira is an AI" in pod
        assert "strongest form" in system

    def test_every_chapter_anchor_is_required_by_the_script(self, slug):
        from engine.intros import build_closing_block, build_intro_line
        pod = _prompt(f"{slug}_podcast.txt").lower()
        intro = build_intro_line(slug, episode_num=1, today_str="x")
        closing = build_closing_block(slug, episode_num=2, today_str="x")
        for m in _cfg(slug).chapters.section_markers:
            if m.title == "Introduction":
                assert re.search(m.pattern, intro, re.I)
            elif m.title == "Closing":
                assert re.search(m.pattern, closing, re.I)
            else:
                assert re.search(m.pattern, pod, re.I), (m.title, m.pattern)

    def test_identity_discloses_the_ai_and_nobody_is_in_a_place(self, slug):
        from engine.intros import build_closing_block, build_intro_line
        intro = build_intro_line(slug, episode_num=5, today_str="x")
        closing = build_closing_block(slug, episode_num=5, today_str="x")
        assert "AI host" in intro
        assert " in Vancouver" not in closing and " in Collingwood" not in closing

    def test_spoken_and_rss_disclosure_are_the_ai_host_variants(self, slug):
        from run_show import _rss_disclosure_for, _spoken_disclosure
        c = _cfg(slug)
        for text in (_spoken_disclosure(c, slug), _rss_disclosure_for(c, slug)):
            assert "Mira" in text and "AI" in text
            assert "my voice" not in text and "Patrick" not in text

    def test_registries(self, slug):
        from engine.content_tracker import SHOW_SECTION_PATTERNS
        from engine.first_episode import _SHOW_DIGEST_EP1, _SHOW_PODCAST_EP1
        from engine.intros import _SHOW_PERSONALITIES
        from engine.show_memory import SHOW_MEMORY_CONFIGS
        from engine.validation import SHOW_VALIDATION_CONFIGS
        for reg in (SHOW_SECTION_PATTERNS, SHOW_VALIDATION_CONFIGS, SHOW_MEMORY_CONFIGS,
                    _SHOW_PERSONALITIES, _SHOW_DIGEST_EP1, _SHOW_PODCAST_EP1):
            assert slug in reg

    def test_registry_page_and_cover(self, slug):
        import generate_html as G
        e = G.NETWORK_SHOWS[slug]
        assert e["host"] == "mira" and e["strand"] == "local"
        assert (ROOT / e["podcast_image"]).exists()
        for px in ("400", "800"):
            assert (ROOT / e["podcast_image"].replace(".jpg", f"-{px}.webp")).exists()
        assert (ROOT / e["show_page"]).exists()

    def test_prelaunch(self, slug):
        import review_episodes as R
        assert slug in R.PRELAUNCH_SLUGS and slug not in R.SHOW_REGISTRY


def test_collingwood_is_a_weekly_everywhere_it_says_so():
    import generate_html as G
    c = _cfg("collingwood")
    assert "daily" not in c.publishing.rss_description.lower()
    assert "Friday" in G.NETWORK_SHOWS["collingwood"]["schedule"]
    assert all(s.window_hours >= 168 for s in c.sources)


def test_mira_claim_is_not_widened_by_the_news_desks():
    """strand: mira carries the interview claim band and a 'Be a guest'
    button; a news desk must never carry either (plan §2b)."""
    from engine.brand import MIRA_SHOW_SLUGS
    assert set(MIRA_SHOW_SLUGS) == {"nerra_daily", "age_of_ai", "nerra_voices"}
    page = (ROOT / "vancouver.html").read_text(encoding="utf-8")
    assert "Be a guest" not in page


def test_local_news_hub_waits_for_its_archive():
    from engine.topic_hubs import MIN_EPISODES_FOR_HUB, TOPIC_HUBS
    hub = next(h for h in TOPIC_HUBS if h["id"] == "local-news")
    assert hub["alternative"]["href"] == "vancouver.html"
    assert MIN_EPISODES_FOR_HUB >= 12


# ---------------------------------------------------------------------------
# Operator brief, 2026-09-23
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slug", NEW_SHOWS)
def test_every_new_show_writes_on_grok_47_and_selects_interesting_first(slug):
    c = _cfg(slug)
    assert c.llm.model == "grok-4.7"
    assert not c.llm.podcast_model, "combined generation needs one model"
    assert "<<include: _shared/interesting_first.txt>>" in _prompt(f"{slug}_digest.txt")


def test_interesting_first_bans_market_noise_by_shape():
    snippet = _prompt("_shared/interesting_first.txt")
    assert "Market noise is not news" in snippet
    assert "announcement about a future announcement" in snippet
    assert '"' not in snippet.replace('"why the stock fell"', "").replace('"coming soon"', ""), (
        "a quoted specimen sentence would be reproduced verbatim")


class TestMag7IsAboutDevelopments:
    def test_no_calendar_and_no_spoken_tape(self):
        dig = _prompt("mag7_digest.txt")
        pod = _prompt("mag7_podcast.txt")
        assert "### Calendar" not in dig and "EARNINGS CALENDAR" not in dig
        assert dig.index("### The Tape") > dig.index("### The Thread")
        assert "[The Tape]" not in pod and "[Calendar]" not in pod
        assert "never an earnings date" in pod

    def test_hook_no_longer_fetches_earnings_dates(self):
        src = (ROOT / "shows/hooks/mag7.py").read_text(encoding="utf-8")
        assert "_earnings_block" not in src and ".calendar" not in src

    def test_research_sources_and_noise_filters(self):
        import yaml
        raw = yaml.safe_load((ROOT / "shows/mag7.yaml").read_text())
        urls = " ".join(s["url"] for s in raw["sources"])
        for host in ("research.google", "deepmind.google", "microsoft.com/en-us/research",
                     "machinelearning.apple.com", "amazon.science", "engineering.fb.com"):
            assert host in urls
        assert "earnings" not in " ".join(u for u in urls.split() if "news.google" in u).lower()
        pats = raw["exclude_title_patterns"]
        for title in ("Nvidia earnings preview: what to expect",
                      "Here's why Apple stock fell today",
                      "Microsoft market cap hits $5 trillion"):
            assert any(re.search(p, title, re.I) for p in pats), title
        for title in ("Apple unveils M6 chip with 40% faster GPU",
                      "Google DeepMind publishes new weather model"):
            assert not any(re.search(p, title, re.I) for p in pats), title


@pytest.mark.parametrize("slug", ("peptides", "longevity"))
class TestHealthShowsTeach:
    def test_education_first_and_pipeline_capped(self, slug):
        dig = _prompt(f"{slug}_digest.txt")
        assert "EDUCATION FIRST" in dig
        assert "at most ONE item a week" in dig

    def test_worth_knowing_section_and_chapter(self, slug):
        dig = _prompt(f"{slug}_digest.txt")
        pod = _prompt(f"{slug}_podcast.txt")
        assert "### Worth Knowing" in dig and "never as an instruction" in dig
        assert '"worth knowing"' in pod
        titles = {m.title for m in _cfg(slug).chapters.section_markers}
        assert "Worth Knowing" in titles

    def test_biotech_trade_press_is_gone(self, slug):
        urls = [s.url for s in _cfg(slug).sources]
        assert not any("biopharmadive" in u for u in urls)
        assert any("sciencedaily" in u for u in urls)

    def test_curriculum_leads_with_practical_subjects(self, slug):
        import yaml
        q = yaml.safe_load((ROOT / f"shows/curricula/{slug}.yaml").read_text())["queue"]
        ids = [e["id"] for e in q]
        industry = {"longevity-biotech", "retatrutide-triple-agonists", "peptide-manufacturing"}
        assert all(ids.index(i) >= len(ids) - 3 for i in industry if i in ids)


def test_hook_articles_are_rendered_whole_even_on_a_busy_day():
    """Hook articles are merged LAST, so the full-text cap (the first N
    articles) left them out whenever the feeds were busy: the prompt saw one
    line of the DriveBC list, and 600 characters of each Europe PMC abstract
    on the health shows. They carry their own text, so no fetch is spent."""
    from engine.article_text import enrich_articles_with_full_text

    feed = [{"title": f"a{i}", "url": f"https://x/{i}", "description": "d",
             "content_text": "body text"} for i in range(20)]
    hook = {"title": "DriveBC", "url": "https://www.drivebc.ca/", "description": "first line",
            "content_text": "event one\nevent two\nevent three", "source_kind": "hook"}
    calls = []
    enrich_articles_with_full_text(feed + [hook], max_articles=12,
                                   fetch=lambda url: calls.append(url) or (200, ""))
    assert "event three" in hook["full_text"] and hook["full_text_source"] == "hook"
    assert sum(1 for a in feed if a.get("full_text")) == 12
    assert "https://www.drivebc.ca/" not in calls
