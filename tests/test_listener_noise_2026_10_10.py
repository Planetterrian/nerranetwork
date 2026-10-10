"""Oct 10 2026 — listener noise: engagement counts, post metadata, a read tape.

Operator listen: "I didn't like so many stock prices read in MAG 7 and
hearing how many likes a recent X post received." In the month to Oct 10
Tesla aired a post's view count eight times (Ep629: "The post came at eight
eighteen AM on October nine with eighteen views."), Models & Agents once,
and MAG 7 read all seven closing prices on 3 of 18 episodes — the
reader-only "The Tape" voiced despite the prompt. ``engine.listener_noise``
removes all three in code; this file pins the real cases, the false
positives found while calibrating on 1,092 scripts and digests, and the
wiring.
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.listener_noise import (  # noqa: E402
    clean_sentence, strip_engagement_noise, strip_price_tape,
    strip_reader_only_sections,
)

REMOVED = [
    # Tesla Ep629, digest and script.
    "The post came at 8:18 AM on October 9 with 18 views.",
    "The post appeared at 7:45 AM on October 9 with 47 views.",
    "The analysis was shared on X at 5:19 AM on October 9 with 56 views.",
    "The post came at eight eighteen AM on October nine with eighteen views.",
    "That post appeared at seven forty five AM on October nine with forty seven views.",
    "The analysis was shared on X at five nineteen AM on October nine with fifty six views.",
    "The post was made on X.",
    "The comment was posted on X.",
    "The message was shared on the platform this morning.",
    # Tesla earlier, M&A Oct 4, SpaceX.
    "The post received eighteen point nine thousand views according to Teslarati.",
    "The post received four point one million views.",
    "The post received twenty-eight thousand six hundred views within hours.",
    "The discussion thread collected over two hundred replies within the first hour of posting.",
]

KEPT = [
    # Content that only looks like the shape.
    "A recent Reddit post described turning to ChatGPT at 2 a.m. when therapy and friends were unavailable.",
    "The Q3 company update will stream on X on October 21 at 4:30 pm CT.",
    "Another thread highlights the October 1 Florida doubleheader featuring Crew-13 at 11:10 a.m.",
    "A de-orbit burn at two thirty-seven A M local time over Delhi.",
    "Regular users keep getting surprised, because the replies finally feel witty instead of stiff.",
    "The committee will take views from experts and people with a stake.",
    "The chart that he posted shows deliveries up nine percent.",
]


class TestEngagementNoise:
    @pytest.mark.parametrize("sentence", REMOVED)
    def test_metadata_sentences_are_removed(self, sentence):
        assert clean_sentence(sentence) == ("", True)

    @pytest.mark.parametrize("sentence", KEPT)
    def test_content_is_untouched(self, sentence):
        assert clean_sentence(sentence) == (sentence, False)

    def test_a_count_clause_leaves_the_rest_of_the_sentence(self):
        out, n = strip_engagement_noise(
            "Sawyer Merritt posted the delivery chart, which drew 12K likes and "
            "900 reposts, showing Q3 up 9 percent.")
        assert out == "Sawyer Merritt posted the delivery chart, showing Q3 up 9 percent."
        assert n == 1

    def test_the_post_time_goes_but_the_claim_stays(self):
        assert clean_sentence(
            "Kalshi posted at 11:00 a.m. on October 4 that its traders forecast "
            "only 0.1 emergency rate cuts this year.")[0] == (
            "Kalshi posted that its traders forecast only 0.1 emergency rate cuts this year.")

    def test_digest_item_keeps_its_source_and_its_facts(self):
        line = ("   Ming posted that no technical aspects appear changed under the new "
                "name. The post came at 8:18 AM on October 9 with 18 views. The post "
                "was made on X. Source: [x.com](https://x.com/tslaming/status/2108472099727933483)")
        out, n = strip_engagement_noise(line)
        assert n == 2
        assert "views" not in out and "made on X" not in out
        assert out.startswith("   Ming posted that no technical aspects appear changed")
        assert out.endswith("Source: [x.com](https://x.com/tslaming/status/2108472099727933483)")

    def test_a_source_url_containing_the_word_is_never_touched(self):
        line = "Source: [phys.org](https://phys.org/news/2026-10-sentinel-3c-views-earth.html)"
        assert strip_engagement_noise(line) == (line, 0)

    def test_the_x_fetch_strips_counts_before_any_prompt(self):
        from engine.fetcher import _x_post_entry
        e = _x_post_entry(
            title="Tesla teases the Q3 update (3M views)",
            desc="Tesla posted a teaser for the Q3 update. The post received three million views.",
            url="https://x.com/Tesla/status/1", link="", post_date="2026-10-09",
            label="Tesla", handle="Tesla", now_iso="2026-10-09T00:00:00Z")
        assert "views" not in e["title"] and "views" not in e["description"]
        assert e["description"] == "Tesla posted a teaser for the Q3 update."


TAPE = """That's the day's top story.
Alphabet's GOOGL closed at three hundred forty-seven dollars and sixty-eight cents, up 0.3 percent.
Amazon's AMZN closed at two hundred fifty-six dollars and twenty-nine cents, up 1.9 percent.
Apple's AAPL closed at three hundred thirty-three dollars and sixty-three cents, up 0.2 percent.
Now to the Company Desk."""


class TestPriceTape:
    def test_a_read_tape_is_removed_whole(self):
        out, n = strip_price_tape(TAPE)
        assert n == 3
        assert out == "That's the day's top story.\nNow to the Company Desk."

    def test_one_price_inside_a_story_stays(self):
        s = ("Shares closed at three hundred eighty dollars after the recall notice. "
             "The recall covers twelve thousand cars.")
        assert strip_price_tape(s) == (s, 0)

    def test_the_same_price_repeated_is_not_a_tape(self):
        # SpaceX Ep120 said its one quote twice — a repetition, not a tape.
        s = ("Ess Pee See Ex closed at one hundred fifty-eight dollars and ninety-six cents. "
             "Ess Pee See Ex closed at one hundred fifty-eight dollars and ninety-six cents, up six percent.")
        assert strip_price_tape(s)[1] == 0

    def test_a_price_and_a_fair_value_are_not_a_tape(self):
        # Modern Investing Ep190: the stock's price and its fair value.
        s = ("The company issued bonds while the stock traded at one hundred twenty two dollars. "
             "Narrative fair value sits at one hundred thirty nine dollars.")
        assert strip_price_tape(s) == (s, 0)

    def test_every_committed_tape_read_is_caught_and_nothing_else(self):
        caught = []
        for f in sorted(glob.glob(str(ROOT / "digests" / "*" / "*_2026*_tts.txt"))):
            text = Path(f).read_text(encoding="utf-8")
            if strip_price_tape(text)[1]:
                caught.append(Path(f).name)
        assert caught, "the committed MAG 7 tape reads are the calibration set"
        assert all(name.startswith("MAG7_Daily_") for name in caught), caught


class TestReaderOnlySections:
    def test_the_tape_never_reaches_the_script_stage(self):
        digest = ("### On the Calendar\nApple event Tuesday.\n\n### The Tape\n"
                  "2026-10-06 · GOOGL 347.68 +0.3% · AMZN 256.29 +1.9%\n\n"
                  "━━━━━━━━━━━━\nClosing line.")
        out = strip_reader_only_sections(digest)
        assert "GOOGL" not in out and "The Tape" not in out
        assert "Apple event Tuesday." in out and "Closing line." in out

    def test_the_podcast_digest_cleaner_drops_it(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("run_show_mod", ROOT / "run_show.py")
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        body = src[src.index("def _clean_digest_for_podcast("):]
        body = body[: body.index("\ndef ", 10)]
        assert "strip_reader_only_sections(digest)" in body
        assert spec is not None


class TestWiring:
    def test_runner_filters_digest_and_script_network_wide(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'metrics.record("digest_listener_noise_removed", _noise_n)' in src
        assert 'metrics.record("script_listener_noise_removed", _noise_s)' in src
        assert 'metrics.record("script_price_tape_removed", _tape_s)' in src
        # Before the source-integrity gate, like the absence filter.
        assert src.index("digest_listener_noise_removed") < src.index(
            "digest_absence_sentences_removed")

    def test_the_x_fetch_prompt_asks_for_the_words_only(self):
        src = (ROOT / "engine" / "fetcher.py").read_text(encoding="utf-8")
        assert "POST_TEXT is the post's own words only" in src


# ------------------------------------------------- the rest of the slate --
P = ROOT / "shows" / "prompts"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class TestTheSlateReview:
    """The Oct 10 transcript review's verified findings, fixed by shape."""

    def test_the_shared_rules_name_attention_and_reference_numbers(self):
        cd = _read("shows/prompts/_shared/content_discipline.txt")
        assert "attention is not a fact about the story" in cd
        assert "Never read a run of closing prices for several companies" in cd
        assert "A reference number is not a fact a listener can use" in cd
        assert "names its subject" in cd
        assert "attention it drew" in _read("shows/prompts/_shared/interesting_first.txt")

    @pytest.mark.parametrize("slug", ["fascinating_frontiers", "planetterrian"])
    def test_ff_and_pt_quota_is_a_ceiling(self, slug):
        d = (P / f"{slug}_digest.txt").read_text(encoding="utf-8")
        assert "ALWAYS pick 15" not in d and "At most 12 items" in d
        assert "<<include: _shared/interesting_first.txt>>" in d
        assert "COVER MORE STORIES" not in (P / f"{slug}_podcast.txt").read_text(encoding="utf-8")

    def test_tesla_quotas_are_ceilings(self):
        d = (P / "tesla_digest.txt").read_text(encoding="utf-8")
        assert "exactly 12 items" not in d and "exactly 5 fresh items" not in d
        assert "17 distinct stories" not in d

    def test_ff_tease_has_no_specimen(self):
        assert '"Keep an eye on..."' not in (P / "fascinating_frontiers_podcast.txt").read_text(encoding="utf-8")

    @pytest.mark.parametrize("rel", ["_shared/omni_desk_podcast_body.txt", "omni_view_world_podcast.txt"])
    def test_desks_never_speak_an_absence_or_a_both_accept_tail(self, rel):
        t = (P / rel).read_text(encoding="utf-8")
        assert "one sentence says so" not in t
        assert "the fact both accept" not in t
        assert "skip the segment" in t.lower()

    def test_the_board_is_not_a_price_tape(self):
        t = (P / "prediction_markets_podcast.txt").read_text(encoding="utf-8")
        assert "all four fields every time" not in t
        assert "never spoken" in t

    def test_spacex_hedge_has_no_specimen(self):
        assert "an observer at Starbase posted" not in (P / "spacex_podcast.txt").read_text(encoding="utf-8")

    def test_mit_action_is_optional_and_the_tone_is_not_spin(self):
        d = (P / "modern_investing_digest.txt").read_text(encoding="utf-8")
        assert "[REQUIRED — exactly ONE concrete portfolio decision" not in d
        assert "What most retail investors don't realize is" not in d
        assert "remind listeners this is learning" not in _read("shows/hooks/modern_investing.py")

    def test_ma_benchmarks_have_no_specimen_decimals(self):
        assert "MMLU 88.4" not in (P / "models_agents_digest.txt").read_text(encoding="utf-8")

    @pytest.mark.parametrize("slug", ["unintended_consequences", "first_principles"])
    def test_narrative_essays_have_a_person_and_a_sourced_hook(self, slug):
        t = (P / f"{slug}_episode.txt").read_text(encoding="utf-8")
        assert "STORY SPINE" in t and "named person" in t

    def test_cold_open_stakes_land_in_the_same_sentence(self):
        assert "or the very next one" not in _read("engine/intros.py")

    def test_collingwood_does_not_pad_its_digest(self):
        from engine.config import load_config
        assert load_config(ROOT / "shows" / "collingwood.yaml").llm.digest_expand_below_target is False

    def test_pope_leo_is_not_low_earth_orbit(self):
        from assets.pronunciation import apply_pronunciation_fixes
        out = apply_pronunciation_fixes("Pope Leo XIV spoke. Starlink sits in LEO.")
        assert "Pope Leo XIV" in out and "L E O" in out
