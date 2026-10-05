"""Guards for the 2026-10-03 show + YouTube review.

Review: docs/reviews/youtube_and_shows_review_2026_10_03.md. Each class pins
one finding to the change that fixed it.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestPromoCadenceWord:
    """Frames 2 and 4 called the FEATURED show a daily briefing whatever its
    cadence (~49 airings since 09-20 for Offshore North, Env Intel, DP Pod,
    Peptides, Collingwood Weekly)."""

    def _all(self):
        from engine.network_promo import ENGLISH_SHOWS, build_network_promo, pick_featured_show
        d0 = dt.date(2026, 9, 1)
        for i in range(70):
            d = d0 + dt.timedelta(days=i)
            for slug in ENGLISH_SHOWS:
                featured = pick_featured_show(slug, d)
                if featured:
                    yield slug, d, featured, build_network_promo(slug, d)

    def test_a_weekly_show_is_never_plugged_as_a_daily_briefing(self):
        from engine.cadence import cadence_adjective, schedule_for_slug
        seen_weekly = 0
        for slug, d, featured, txt in self._all():
            if cadence_adjective(schedule_for_slug(featured)) != "weekly":
                continue
            seen_weekly += 1
            plug = txt.split("nerranetwork.com.")[0]  # the frame, not the surface line
            assert "daily briefing" not in plug, (slug, d, featured, plug)
        assert seen_weekly, "no weekly show was featured in 70 days — the test read nothing"

    def test_a_daily_show_plug_is_unchanged(self):
        from engine.cadence import cadence_adjective, schedule_for_slug
        found = False
        for slug, d, featured, txt in self._all():
            if cadence_adjective(schedule_for_slug(featured)) != "daily":
                continue
            if "our sister show" in txt:
                found = True
                assert "the Nerra Network's daily briefings" in txt, txt
            if "This show comes to you from" in txt:
                found = True
                assert "another sharp daily briefing" in txt, txt
        assert found


class TestBodyOpensOnTheHook:
    def test_the_cold_open_spec_says_so(self):
        from engine.intros import build_cold_open_spec
        spec = build_cold_open_spec("tesla")
        assert "THE BODY KEEPS THE OPEN'S PROMISE FIRST" in spec

    def test_the_spec_supplies_no_quotable_sentence(self):
        from engine.intros import build_cold_open_spec
        spec = build_cold_open_spec("tesla")
        block = spec[spec.index("THE BODY KEEPS"):].split("\n- ")[0]
        assert '"' not in block and "“" not in block

    def test_the_metric_reads_the_first_body_sentences(self):
        from engine.script_audit import hook_leads_body
        hook = "Tesla delivered 486,532 vehicles in the third quarter, beating forecasts by 24,000."
        ident = "This is Tesla Shorts Time, episode six hundred twenty-three."
        on = (f"{hook} {ident} The third quarter total of 486,532 vehicles was a record. "
              "Tesla delivered more vehicles in China than a year earlier. "
              "Wall Street forecasts had been beaten by about 24,000. "
              + "Spain registrations rose sharply in September. " * 6)
        off = (f"{hook} {ident} The Model 3 registered 2,528 units in Spain. "
               "India sales began through a new Mumbai showroom. "
               "Dan Ives raised his price target again. "
               + "Deliveries reached 486,532 vehicles and beat forecasts. " * 6)
        assert hook_leads_body(on) > 0.4
        assert hook_leads_body(off) < 0.25

    def test_the_metric_is_recorded(self):
        from engine.script_audit import audit_script
        hook = "Tesla delivered 486,532 vehicles in the third quarter, beating forecasts."
        script = (f"{hook} This is Tesla Shorts Time, episode one. "
                  + "Deliveries reached 486,532 vehicles in the quarter. " * 10)
        m = audit_script(script, hook=hook).to_metrics()
        assert "script_hook_leads_body_pct" in m


class TestPronunciationFormatting:
    @pytest.mark.parametrize("src,bad", [
        ("Kim Jong-Un met envoys.", "U N"),
        ("He called it un-American.", "U N"),
        ("The deal is NT$600 million.", "NTsix"),
        ("A S$2 billion fund.", "Stwo"),
        ("HK$5 billion raised.", "HKfive"),
        ("Users on the r/longevity subreddit asked.", "subreddit subreddit"),
        ("Part 100-000000652 ships.", "one hundred to six hundred"),
    ])
    def test_reported_garbles_are_gone(self, src, bad):
        from assets.pronunciation import prepare_text_for_tts
        assert bad not in prepare_text_for_tts(src)

    @pytest.mark.parametrize("src,good", [
        ("The UN Security Council met.", "U N"),
        ("The deal is NT$600 million.", "New Taiwan dollars"),
        ("HK$5 billion raised.", "Hong Kong dollars"),
        ("US$95 each.", "U S dollars"),
        ("C$40 fee.", "Canadian dollars"),
        ("Prices of 10-20 dollars.", "ten to twenty"),
        ("Users on r/longevity asked.", "the longevity subreddit"),
    ])
    def test_correct_forms_survive(self, src, good):
        from assets.pronunciation import prepare_text_for_tts
        assert good in prepare_text_for_tts(src)


class TestSelfNarrationContainers:
    @pytest.mark.parametrize("s", [
        "No square footage and no closing date are in the item.",
        "No price for the new contract is in the material.",
        "Nothing in the supplied note names a vote on the motion.",
        "…not in a separate NVIDIA spec sheet in today's pile.",
        "The square footage is not given in the note.",
    ])
    def test_document_as_container_is_removed(self, s):
        from engine.absence_sentences import is_absence_sentence
        assert is_absence_sentence(s)

    @pytest.mark.parametrize("s", [
        "Defects in the material weakened the weld under load.",
        "There is water in the material returned from the asteroid.",
        "There is water in the material.",
        "The council voted on the item last night and it passed.",
        "Graphene is the strongest material ever tested.",
    ])
    def test_news_about_materials_and_agenda_items_stays(self, s):
        from engine.absence_sentences import is_absence_sentence
        assert not is_absence_sentence(s)


class TestPromptDeseeds:
    def test_omni_view_supplies_no_go_deeper_or_teaser_template(self):
        txt = (ROOT / "shows/prompts/omni_view_podcast.txt").read_text(encoding="utf-8")
        assert "If you want to go deeper on" not in txt   # aired 8/8 episodes
        assert "Tomorrow, watch for" not in txt
        assert "Before we go —" not in txt

    def test_spacex_never_fills_an_empty_ai_section(self):
        pod = (ROOT / "shows/prompts/spacex_podcast.txt").read_text(encoding="utf-8")
        dig = (ROOT / "shows/prompts/spacex_digest.txt").read_text(encoding="utf-8")
        assert "one sentence on the live threads to watch" not in pod
        assert "SKIP the segment entirely" in pod
        assert "write ONE sentence noting the quiet" not in dig
        assert "omit the ### AI & Compute heading entirely" in dig


class TestLengthTargetsFitTheFormat:
    def test_top_world_floor_clears_its_own_median(self):
        from engine.config import load_config
        cfg = load_config(ROOT / "shows/omni_view_world.yaml")
        # Ten episodes ran 906-1,321 words; 10-03 was skipped at 821 < 840.
        assert int(cfg.llm.min_podcast_words * 0.6) <= 821

    def test_collingwood_asks_for_what_a_week_carries(self):
        from engine.config import load_config
        cfg = load_config(ROOT / "shows/collingwood.yaml")
        assert cfg.llm.min_podcast_words <= 900
