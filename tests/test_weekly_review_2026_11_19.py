"""Weekly network review, Nov 19 2026 (docs/reviews/network_week_review_2026_11_19.md).

Four defects the week's runs and audits proved:

1. Offshore North read two days of a seven-day week (its fetch ladder opened
   at 48h and the campaign feeds' 30-day windows always satisfied
   min_articles, so it never widened); Nov 16 skipped as too thin.
2. No filter ever read X posts: ``fetch_x_posts`` took ``keywords`` and
   ignored it, so Musk's and commentators' Starship / Crisco / Hong Kong
   posts reached Tesla's X Takeover and SpaceX's brief.
3. First Principles and Unintended Consequences close on a lesson that
   re-tells the body (Repetitive on 7/7 and 6/7 audits); FPD's lesson was
   asked for 250-350 words. FPD Ep164-165 also mis-summed a range.
4. A test read a real SpaceX summaries record that rolled off (fixed in
   tests/test_video_job_2026_10_18.py).
"""
from __future__ import annotations

from pathlib import Path

import yaml

from engine.config import load_config

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "shows" / "prompts"


class TestOffshoreNorthReadsTheWeek:
    def test_the_first_rung_is_the_whole_week(self):
        hours = load_config(str(ROOT / "shows" / "offshore_north.yaml")).fetch_expansion_hours
        assert hours and min(hours) >= 168, (
            "the first fetch stage must cover the seven days a Monday episode "
            f"reports on; the campaign feeds always satisfy min_articles, so a "
            f"narrower first rung is the only rung (got {hours})")

    def test_stale_news_is_still_kept_out(self):
        raw = yaml.safe_load((ROOT / "shows" / "offshore_north.yaml").read_text())
        assert 0 < int(raw["stale_article_days"]) <= 10


class TestXPostsOnTopic:
    POSTS = [
        {"title": "Maintenance-free rocket catch mechanism proposed",
         "description": "Honestly I don't think Crisco and hot rocket hardware would be a great combination."},
        {"title": "Cybercab orders open", "description": "Select customers can now order."},
        {"title": "Hong Kong birth rate", "description": "One of the lowest in the world."},
    ]

    def test_only_posts_naming_a_keyword_survive(self):
        from engine.fetcher import filter_x_posts_on_topic
        kept = filter_x_posts_on_topic(self.POSTS, ["tesla", "cybercab", "fsd"])
        assert [p["title"] for p in kept] == ["Cybercab orders open"]

    def test_no_keywords_never_empties_the_intake(self):
        from engine.fetcher import filter_x_posts_on_topic
        assert filter_x_posts_on_topic(self.POSTS, []) == self.POSTS
        assert filter_x_posts_on_topic(self.POSTS, None) == self.POSTS

    def _raw(self, handle):
        return "\n\n".join(
            f"POST_TITLE: {p['title']}\nPOST_TEXT: {p['description']}\n"
            f"POST_URL: https://x.com/{handle}/status/{i}\nPOST_LINK: none\n"
            f"POST_DATE: 2026-11-18"
            for i, p in enumerate(self.POSTS, 1))

    def _run(self, monkeypatch, on_topic_only):
        import digests.xai_grok as xg
        from engine.config import XAccountConfig
        from engine.fetcher import fetch_x_posts
        monkeypatch.setenv("GROK_API_KEY", "x")
        monkeypatch.setattr(xg, "grok_generate_text",
                            lambda **kw: (self._raw(kw["x_handles"][0]), {}))
        acct = XAccountConfig(handle="elonmusk", label="Elon Musk", max_posts=5,
                              on_topic_only=on_topic_only)
        return fetch_x_posts([acct], keywords=["tesla", "cybercab"])

    def test_the_live_fetch_applies_it_for_a_flagged_account(self, monkeypatch):
        posts = self._run(monkeypatch, True)
        assert [p["title"] for p in posts] == ["Cybercab orders open"]

    def test_an_unflagged_account_is_read_whole(self, monkeypatch):
        assert len(self._run(monkeypatch, False)) == 3

    def test_the_yaml_key_reaches_the_dataclass(self):
        tesla = {a.handle: a.on_topic_only
                 for a in load_config(str(ROOT / "shows" / "tesla.yaml")).x_accounts}
        for broad in ("elonmusk", "tslaming", "Teslarati", "sawyermerrit",
                      "RobMaurer", "wholemarsblog"):
            assert tesla[broad] is True, broad
        for own in ("Tesla", "Tesla_AI", "Tesla_Optimus", "teslaenergy", "TeslaCharging"):
            assert tesla[own] is False, own
        spacex = {a.handle: a.on_topic_only
                  for a in load_config(str(ROOT / "shows" / "spacex.yaml")).x_accounts}
        assert spacex["elonmusk"] is True and spacex["SpaceX"] is False


class TestNarrativeLessonsAddNotRetell:
    def test_fpd_lesson_is_short_and_new(self):
        pod = (PROMPTS / "first_principles_podcast.txt").read_text()
        assert "two hundred fifty to three hundred fifty" not in pod
        assert "one hundred to one hundred sixty words" in pod
        assert "never re-tells" in pod
        ep = (PROMPTS / "first_principles_episode.txt").read_text()
        assert "6-8 sentences. Extract two portable principles" not in ep
        assert ep.count("never re-tells an event, a figure") == 2

    def test_fpd_sums_a_range_twice(self):
        ep = (PROMPTS / "first_principles_episode.txt").read_text()
        assert "low ends together and the high ends together" in ep
        pod = (PROMPTS / "first_principles_podcast.txt").read_text()
        assert "the low ends and the high ends" in pod

    def test_uc_lesson_is_short_and_new(self):
        pod = (PROMPTS / "unintended_consequences_podcast.txt").read_text()
        assert "150 to 250 spoken words" not in pod
        assert "100 to 160 spoken words" in pod
        ep = (PROMPTS / "unintended_consequences_episode.txt").read_text()
        assert "never re-tells an event, a figure or a finding" in ep
