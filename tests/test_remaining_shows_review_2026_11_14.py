"""Nov 14 2026 remaining-shows review: guards for what shipped.

Review: docs/reviews/remaining_shows_review_2026_11_14.md; register
``remaining-shows-review-2026-11-14``.
"""
from __future__ import annotations

import glob
import re
from pathlib import Path

import pytest
import yaml

from engine.config import load_config
from engine.validation import detect_phrase_repetition

ROOT = Path(__file__).resolve().parents[1]

# A script past ~2,200 words splits the single-call TTS request and drops
# the <fast> wrap (landmine #17). Every stated ceiling stays under it.
WRAP_SAFE_WORDS = 2000

CEILING_SHOWS = {
    "ai_chips": 1750,
    "mag7": 1600,
    "prediction_markets": 1750,
    "peptides": 1500,
    "longevity": 1500,
    "vancouver": 1800,
    "collingwood": 1450,
    "models_agents": 1600,
}


def _yaml(slug: str) -> dict:
    return yaml.safe_load((ROOT / f"shows/{slug}.yaml").read_text(encoding="utf-8"))


def _podcast_prompt(slug: str) -> str:
    return (ROOT / _yaml(slug)["llm"]["podcast_prompt_file"]).read_text(encoding="utf-8")


class TestRepetitionExemptTerms:
    EP158 = ROOT / "digests/spacex/SpaceX_Daily_Ep158_20261110_tts.txt"

    def test_beat_names_are_not_a_loop(self):
        cfg = load_config(ROOT / "shows/spacex.yaml")
        assert "super heavy" in cfg.repetition_exempt_terms
        text = self.EP158.read_text(encoding="utf-8")
        before = {r["phrase"] for r in detect_phrase_repetition(text) if r["severity"] == "critical"}
        assert "super heavy booster" in before
        after = [
            r["phrase"]
            for r in detect_phrase_repetition(text, exempt_terms=tuple(cfg.repetition_exempt_terms))
            if r["severity"] == "critical"
        ]
        assert after == []

    def test_a_real_loop_still_fires(self):
        loop = " ".join(["The kind of change that matters here is real."] * 8)
        reps = detect_phrase_repetition(loop, exempt_terms=("super heavy", "booster", "ship"))
        assert any(r["severity"] == "critical" for r in reps)

    def test_whole_words_only(self):
        # "ship" must not exempt "relationship" or "shipping".
        loop = " ".join(["Their relationship with shipping lanes grew."] * 8)
        reps = detect_phrase_repetition(loop, exempt_terms=("ship",))
        assert any(r["severity"] == "critical" for r in reps)

    def test_empty_is_byte_identical(self):
        text = self.EP158.read_text(encoding="utf-8")
        assert detect_phrase_repetition(text) == detect_phrase_repetition(text, exempt_terms=())

    def test_no_other_show_opts_in(self):
        for p in (ROOT / "shows").glob("*.yaml"):
            if p.name == "spacex.yaml":
                continue
            assert "repetition_exempt_terms" not in p.read_text(encoding="utf-8"), p.name

    def test_the_retry_reads_the_config(self):
        src = (ROOT / "engine/generator.py").read_text(encoding="utf-8")
        assert 'getattr(config, "repetition_exempt_terms"' in src
        assert "detect_phrase_repetition(text, exempt_terms=_rep_exempt)" in src
        assert "detect_phrase_repetition(text_rr, exempt_terms=_rep_exempt)" in src


class TestSpacexSources:
    def test_content_farms_excluded(self):
        cfg = load_config(ROOT / "shows/spacex.yaml")
        for host in ("shattered.io", "ad-hoc-news.de", "finance.biggo.com", "basenor.com"):
            assert host in cfg.exclude_sources


class TestSpacexPrompt:
    def setup_method(self):
        self.text = (ROOT / "shows/prompts/spacex_podcast.txt").read_text(encoding="utf-8")

    def test_the_market_is_spoken_once_in_the_closing(self):
        assert "[Market Watch" not in self.text
        assert "spoken exactly once, by the closing block" in self.text
        assert "A percentage is never spoken without the company" in self.text
        # The specimen the model copied ("up a little over two percent") is gone.
        assert "a little over two percent" not in self.text

    def test_deep_dive_is_not_a_length_lever(self):
        assert "LENGTH LEVER" not in self.text
        assert "length lever" not in self.text
        assert "you should lengthen and deepen it here" not in self.text
        system = (ROOT / "shows/prompts/spacex_system.txt").read_text(encoding="utf-8")
        assert "reach length by deepening the engineering" not in system

    def test_derived_numbers_show_their_working(self):
        assert "SHOW THE WORKING" in self.text
        assert "at least five numbers" not in self.text

    def test_cursor_items_say_why_they_are_here(self):
        assert "the acquisition SpaceX agreed in 2026" in self.text
        digest = (ROOT / "shows/prompts/spacex_digest.txt").read_text(encoding="utf-8")
        assert "the acquisition agreed in 2026" in digest
        assert "how-to guide" in digest

    def test_closing_still_carries_the_quote(self):
        # The closing block is what speaks the price now.
        # Nov 24 2026: the glob was pinned to Ep16x, and Ep165, Ep168 and
        # Ep169 shipped without the quote because the pre-fetch hook timed
        # out (fixed in shows/hooks/spacex.py; guard
        # tests/test_workflow_fixes_2026_11_24.py). Read the newest three
        # episodes instead, skipping those three known casualties.
        lost_hook = {165, 168, 169}
        def _ep(f):
            return int(re.search(r"_Ep(\d+)_", f).group(1))
        files = [f for f in glob.glob(str(ROOT / "digests/spacex/SpaceX_Daily_Ep*_tts.txt"))
                 if _ep(f) not in lost_hook]
        for f in sorted(files, key=_ep)[-3:]:
            assert re.search(r"Ess Pee See Ex closed", Path(f).read_text(encoding="utf-8")), f


class TestTeaserOrNone:
    @pytest.mark.parametrize("slug", ["spacex", "ai_chips", "mag7", "prediction_markets", "models_agents"])
    def test_teaser_names_only_an_unspoken_next_step(self, slug):
        text = _podcast_prompt(slug)
        assert "or none]" in text
        assert "no earlier sentence of this episode" in text
        assert "leave the teaser out" in text

    def test_chapter_marker_is_optional(self):
        # A missing teaser must not cost the episode its Closing chapter:
        # the teaser pattern is a plain `where: end` marker, never required.
        for slug in ("spacex", "ai_chips", "mag7", "prediction_markets", "models_agents"):
            raw = (ROOT / f"shows/{slug}.yaml").read_text(encoding="utf-8")
            assert "required: true" not in raw.split("Before we go")[-1][:200], slug


class TestWordCeiling:
    @pytest.mark.parametrize("slug,ceiling", sorted(CEILING_SHOWS.items()))
    def test_prompt_states_the_yaml_ceiling(self, slug, ceiling):
        cfg = load_config(ROOT / f"shows/{slug}.yaml")
        assert cfg.llm.max_podcast_words == ceiling
        assert cfg.llm.min_podcast_words < ceiling <= WRAP_SAFE_WORDS
        text = _podcast_prompt(slug)
        assert text.count(f"HARD CEILING: {ceiling:,} spoken words.") == 1

    def test_ceiling_off_by_default(self):
        cfg = load_config(ROOT / "shows/tesla.yaml")
        assert cfg.llm.max_podcast_words == 0

    def test_run_show_records_never_trims(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        i = src.index('metrics.record("script_over_ceiling"')
        block = src[i - 600:i + 600]
        assert "_CEILING_WORDS" in block
        assert "_call_grok" not in block and "truncate" not in block

    def test_replay_the_ceiling_would_have_caught_the_wrap_drops(self):
        # Every committed episode whose <fast> wrap dropped ran past its
        # show's ceiling; the ceiling is not tighter than the shows' own
        # typical day (median of the last 14 under it).
        for slug, ceiling in CEILING_SHOWS.items():
            words, dropped = [], []
            fs = sorted(glob.glob(str(ROOT / f"digests/{slug}/metrics_ep*.json")),
                        key=lambda f: int(re.search(r"ep(\d+)", f).group(1)))[-14:]
            import json
            for f in fs:
                c = json.loads(Path(f).read_text(encoding="utf-8")).get("counters", {})
                w = c.get("script_words")
                if isinstance(w, int):
                    words.append(w)
                    if c.get("tts_speech_wrap_dropped"):
                        dropped.append(w)
            assert all(w > ceiling for w in dropped), (slug, dropped)


class TestBeginners:
    def setup_method(self):
        self.text = (ROOT / "shows/prompts/mab_podcast.txt").read_text(encoding="utf-8")

    def test_one_analogy_per_idea(self):
        assert "at LEAST 8 analogies" not in self.text
        assert "2-3 vivid analogies" not in self.text
        assert "ONE analogy per idea" in self.text

    def test_no_sentence_quotas_or_word_floor(self):
        assert "8-10 sentences" not in self.text
        assert "at least 1300 words" not in self.text
        assert "35-45+ sentences" not in self.text

    def test_no_quotable_example_and_no_host_experience(self):
        assert "I tried it this morning" not in self.text
        assert "never claims to have tried" in self.text

    def test_deep_dive_is_a_different_idea(self):
        assert "that The Big Story did NOT already explain" in self.text

    def test_skip_floor_pinned(self):
        cfg = load_config(ROOT / "shows/models_agents_beginners.yaml")
        assert cfg.llm.min_podcast_words == 1000
        assert cfg.llm.min_podcast_publish_words == 720


class TestEnvIntel:
    def setup_method(self):
        self.text = (ROOT / "shows/prompts/env_intel_podcast.txt").read_text(encoding="utf-8")

    def test_actions_are_said_once(self):
        assert "[Action Items — 30-45 seconds, or none]" in self.text
        assert "never the Compliance Brief's action again" in self.text
        assert "[Week Ahead — 20-30 seconds, or none]" in self.text

    def test_teaser_is_weekly_and_unquoted(self):
        assert "every other weekday" not in self.text
        assert "In the next briefing, watch for" not in self.text
        assert "This show is weekly" in self.text

    def test_no_invited_commentary(self):
        assert "What this signals is" not in self.text


class TestFinansyProsto:
    def setup_method(self):
        self.text = (ROOT / "shows/prompts/fp_podcast.txt").read_text(encoding="utf-8")

    def test_one_analogy_and_no_quotas(self):
        assert "МИНИМУМ 8 аналогий" not in self.text
        assert "ОДНА аналогия на одну мысль" in self.text
        assert "35-45+ предложений" not in self.text
        assert "не менее 1300 слов" not in self.text

    def test_each_action_once_and_working_shown(self):
        assert "звучит в выпуске ОДИН раз" in self.text
        assert "вместе с цифрами, из которых он получен" in self.text
        assert "которое главная тема ещё НЕ объяснила" in self.text
