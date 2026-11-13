"""Fascinating Frontiers review, Nov 13 2026.

Review: docs/reviews/fascinating_frontiers_review_2026_11_13.md. The daily
audit flagged FACTUAL_ERRORS on 12 of the 22 episodes Ep230-251 and
REPETITIVE on 12 of the last 14; downloads slid 202, 142, 157, 129 over the
four OP3 weeks to Nov 11. What this pins:

* who the show may cite (no Reddit, no dead feeds, the primary science desks);
* picture-of-the-day captions never reach the briefing;
* a hook that re-leads the previous episode's story is regenerated;
* the digest retry counts FACTS, so it never pads the deep dive;
* the deep dive's comparisons are arithmetic on stated figures, never guesses;
* the script's length is the digest's facts, never a word count;
* the hook fits the episode title whole.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from engine.utils import drop_excluded_titles, is_excluded_source

ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "shows" / "fascinating_frontiers.yaml"
DIGEST_PROMPT = ROOT / "shows" / "prompts" / "fascinating_frontiers_digest.txt"
PODCAST_PROMPT = ROOT / "shows" / "prompts" / "fascinating_frontiers_podcast.txt"
DIGESTS = ROOT / "digests" / "fascinating_frontiers"


def _cfg() -> dict:
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))


def _urls() -> list:
    return [s["url"] for s in _cfg()["sources"]]


class TestWhoTheShowCites:
    def test_no_reddit_feed(self):
        assert not [u for u in _urls() if "reddit.com" in u]

    def test_no_feed_the_audit_found_dead(self):
        # data/feed_audit_2026-11-08.json: ESA 404, Sky & Telescope 403,
        # science.nasa.gov/feed 200 with zero entries.
        dead = ("esa.int/rssfeed", "skyandtelescope.com", "science.nasa.gov/feed")
        assert not [u for u in _urls() if any(d in u for d in dead)]

    def test_no_feed_listed_twice(self):
        urls = _urls()
        assert len(urls) == len(set(urls))
        # The two NASA image-of-the-day URLs and the two Space.com URLs
        # served the same entries.
        assert sum("image_of_the_day" in u or "iotd" in u for u in urls) <= 1
        assert sum("space.com/" in u for u in urls) == 1

    def test_the_primary_science_desks_are_read(self):
        urls = " ".join(_urls())
        for host in ("jpl.nasa.gov", "eso.org", "esawebb.org", "esahubble.org",
                     "aasnova.org", "planetary.org", "nasaspaceflight.com",
                     "arstechnica.com/space"):
            assert host in urls, host

    def test_excluded_publishers_are_dropped(self):
        srcs = _cfg()["exclude_sources"]
        assert is_excluded_source({"url": "https://www.reddit.com/r/Astronomy/comments/x"}, srcs)
        assert is_excluded_source({"url": "https://news.google.com/rss/articles/abc",
                                   "source_name": "Global Times"}, srcs)
        assert is_excluded_source({"url": "https://www.youtube.com/watch?v=x"}, srcs)
        assert not is_excluded_source({"url": "https://phys.org/news/2026-11-x.html"}, srcs)
        assert not is_excluded_source({"url": "https://www.jpl.nasa.gov/news/x"}, srcs)


class TestPictureOfTheDay:
    def _kept(self, title, url="https://example.org/news/x"):
        kept, _ = drop_excluded_titles([{"title": title, "url": url}],
                                       _cfg()["exclude_title_patterns"])
        return bool(kept)

    def test_the_ep251_captions_are_dropped(self):
        assert not self._kept("APOD: 2026 November 12 – Moon, Venus and Spica Meet",
                              "https://science.nasa.gov/image-article/apod-2026-november-12/")
        assert not self._kept("Taula eclipse",
                              "https://www.astronomy.com/picture-of-the-day/photo/taula-eclipse/")
        assert not self._kept("November Night Sky Highlights: Meteor Showers and Supermoons")

    def test_real_image_releases_survive(self):
        for title in ("Webb captures commotion from nebula's stellar jets",
                      "Hubble image reveals a ghostly nebula",
                      "NASA's Perseverance images a new rock outcrop"):
            assert self._kept(title), title


class TestHookNeverReleads:
    def test_listed(self):
        assert "hook_repeats_past_lead" in _cfg()["digest_lints"]

    def test_ep251_reled_ep250_and_ep250_did_not_relead(self):
        from engine.digest_lint import hook_line, hook_repeat_match, past_hooks
        beat = [t.strip() for t in _cfg()["publishing"]["rss_keywords"].split(",")]
        ep251 = hook_line((DIGESTS / "Fascinating_Frontiers_Ep251_20261112.md").read_text(encoding="utf-8"))
        ep250 = hook_line((DIGESTS / "Fascinating_Frontiers_Ep250_20261111.md").read_text(encoding="utf-8"))
        assert hook_repeat_match(ep251, past_hooks(DIGESTS, before_episode=251), beat)
        assert hook_repeat_match(ep250, past_hooks(DIGESTS, before_episode=250), beat) is None


class TestTheRetryCountsFacts:
    def test_floors(self):
        llm = _cfg()["llm"]
        assert llm["min_digest_facts"] == 18
        assert llm["min_podcast_publish_words"] == 850  # the skip floor never moves
        assert llm["min_podcast_words"] == 1400
        assert llm["podcast_expand_below_target"] is False


class TestTheDeepDiveNeverGuesses:
    def test_comparisons_are_arithmetic_on_stated_figures(self):
        p = DIGEST_PROMPT.read_text(encoding="utf-8")
        assert "plain arithmetic on two figures you state" in p
        assert "never an order-of-magnitude guess" in p
        assert "units exactly as the article gives them" in p

    def test_the_old_seeds_and_memory_lever_are_gone(self):
        p = DIGEST_PROMPT.read_text(encoding="utf-8")
        for gone in ("licensed-knowledge length lever", "riding alongside a photon",
                     "jaw-dropping scale comparison", "Coming soon to Apple Podcasts",
                     "Include at least one specific, surprising number"):
            assert gone not in p, gone

    def test_one_telling_per_story(self):
        p = DIGEST_PROMPT.read_text(encoding="utf-8")
        assert "ONE TELLING PER STORY, CHOSEN FIRST" in p
        assert "no item, Also Today line or Spotlight above uses" in p

    def test_hook_fits_the_title_whole(self):
        from engine.titles import PODCAST_EPISODE_TITLE_MAX, episode_title
        p = DIGEST_PROMPT.read_text(encoding="utf-8")
        m = re.search(r"\*\*HOOK:\*\* \[One sentence of at most \d+ words and under (\d+) characters", p)
        assert m
        # "Ep 999: " plus the hook must fit the feed title.
        assert int(m.group(1)) + len("Ep 999: ") <= PODCAST_EPISODE_TITLE_MAX
        hook = "x" * (int(m.group(1)) - 1)
        assert episode_title(hook, 999).endswith(hook)


class TestTheScriptIsTheDigestsFacts:
    def test_no_word_target(self):
        p = PODCAST_PROMPT.read_text(encoding="utf-8")
        assert "1,900" not in p and "2,200" not in p
        assert "There is no word target" in p

    def test_no_quotable_example_story(self):
        p = PODCAST_PROMPT.read_text(encoding="utf-8")
        assert "rolled out to the launch pad" not in p
        assert "EXAMPLE OF IDEAL STORY COVERAGE" not in p

    def test_accuracy_on_air(self):
        p = PODCAST_PROMPT.read_text(encoding="utf-8")
        assert "Never convert a unit, never work out a multiple or a ratio" in p
        assert "Never merge two dated events into one sentence" in p


# --- Follow-up after the first live episode (Ep252, Nov 13) ---------------
# Ep252 ran 6.8 minutes: twelve items of two or three sentences each (an
# Ohio astronaut profile, a Korean workshop, SpaceX's Brownsville water
# money read from its X post), the deep dive built from item 12's article,
# and a 94-character hook clipped in the feed title.


class TestFewerStoriesEachExplained:
    def test_a_listed_item_is_built_from_a_read_article(self):
        p = DIGEST_PROMPT.read_text(encoding="utf-8")
        assert "FEWER STORIES, EACH EXPLAINED" in p
        assert "carries at least three distinct facts" in p
        assert "At most 10 items" in p

    def test_wonder_ranks_the_list(self):
        p = DIGEST_PROMPT.read_text(encoding="utf-8")
        assert "WONDER RANKS THE LIST" in p
        assert "spending or site work on Earth" in p

    def test_enough_articles_are_read(self):
        # 10 items plus a Spotlight plus a deep dive, each from its own page.
        assert _cfg()["fetch_full_text"] >= 24

    def test_a_sister_show_never_steers_the_show_away(self):
        p = DIGEST_PROMPT.read_text(encoding="utf-8")
        assert "change course" not in p
        assert "never a reason to skip it" in p

    def test_the_hook_is_counted_in_words(self):
        p = DIGEST_PROMPT.read_text(encoding="utf-8")
        assert "at most 13 words and under 90 characters" in p
        ep252 = ("Euclid has released images of 900 million galaxies spanning "
                 "an area equal to 9500 full moons.")
        assert len(ep252.split()) > 13  # the hook that was clipped


class TestTheScriptExplains:
    def test_each_story_is_explained_not_listed(self):
        p = PODCAST_PROMPT.read_text(encoding="utf-8")
        assert "Each story is EXPLAINED, not listed" in p
        assert "Zero commentary sentences" not in p
        # The plain-words sentence carries no number: the accuracy rules hold.
        assert "with no number in it" in p
        assert "Never convert a unit, never work out a multiple or a ratio" in p

    def test_no_handle_or_web_address_is_spoken(self):
        p = PODCAST_PROMPT.read_text(encoding="utf-8")
        assert "Never a social-media handle" in p
        assert '"X dot com"' in p
