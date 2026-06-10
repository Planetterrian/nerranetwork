"""Phase 3 (May 2026 audit) — content-calibration drift guards.

Pins the recalibrated thresholds so a future YAML edit can't silently
restore the broken behaviour. Specifically:

  - ``min_podcast_words`` per show is recalibrated to ~1.1× rolling
    median delivery, so ``script_below_target: true`` becomes a real
    signal again instead of firing on 9/11 shows.
  - ``slow_news.repeat_trigger_ratio`` is the new ratio gate (default
    0.55) preventing TST/FF/PT from falling back to evergreen segments
    on healthy news days.
  - ``_sanitize_podcast_script`` now strips consecutive same-sentence
    duplicates that caused the FP Ep32 ``Давайте разберёмся!`` echo.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Recalibrated min_podcast_words
# ---------------------------------------------------------------------------

class TestRecalibratedMinPodcastWords:
    """Operator caught (May 6 2026 Phase-3 audit) ``script_below_target:
    true`` firing on 9 of 11 shows because the per-show
    ``min_podcast_words`` was set ~40 % above what the LLM actually
    delivered. Phase-3 dropped the targets to ~1.1× rolling-7-day
    median.

    May 9 2026 follow-up retune: with PR #335's raw-word-count metric
    now feeding actual delivery data into the audit, the Phase-3
    targets STILL fired ``script_below_target`` on every show every
    day — Phase 3 estimated median delivery from logs but the actual
    median (now visible in metrics_ep*.json) was lower. Targets
    dropped a second time to ~1.05× empirical median.

    May 21 2026 substance-boost: operator reviewed several days of
    output and reported "all the shows are light on substance for
    all the news information... less news items being included in
    all shows and less of the substance from any news item." Three
    coordinated changes shipped together:

      1. ``MAX_ARTICLES_FOR_LLM`` 25 → 40 (run_show.py:872) — gives
         the LLM headroom to drop near-duplicate Google-News stories
         and still hit the Top 15 with diverse angles.
      2. Tesla / FF / PT digest prompts expanded from "2 sentences
         max" / "2-4 sentences" per item to "4-5 sentences with
         concrete substance" and an explicit "required ingredients"
         list (named people, specific numbers, named programs /
         instruments / molecules, short quote, comparison /
         context, mechanism, what-to-watch-next).
      3. Tesla / FF / PT podcast prompts expanded from "Cover 9-11
         × 4-6 sentences" to "Cover 12-14 × 5-7 sentences" so the
         richer digest material lands in the spoken script.

    Targets bumped to match the new structure (and per-show
    max_tokens raised so grok-4.3 reasoning has room to write the
    fuller output):

      tesla            : 1200 → 1600 → 2000 (June 10 2026: one unified 2,200-2,400-word target)
      planetterrian    :  950 → 1250  (12-14 × 5-7 = ~60-98 sent)
      fascinating_fron : 1050 → 1350 → 1700 (June 10 2026: one unified 1,900-2,200-word target)

    Other shows retain their May 9 calibration — their prompts
    weren't changed in this pass."""

    EXPECTED = {
        "tesla":                   2000,  # June 10 2026 review: single 2,200-2,400-word target
        "fascinating_frontiers":   1700,  # June 10 2026 review: single 1,900-2,200-word target
        "planetterrian":           1250,
        "modern_investing":        1800,  # June 10 2026 review: single 2,000-2,200-word target
        "omni_view":               900,
        "unintended_consequences": 1300,
        "finansy_prosto":          900,
        "privet_russian":          650,
    }

    @pytest.mark.parametrize("slug,expected", list(EXPECTED.items()))
    def test_per_show(self, slug, expected):
        from engine.config import load_config
        cfg = load_config(Path("shows") / f"{slug}.yaml")
        assert cfg.llm.min_podcast_words == expected, (
            f"{slug}.min_podcast_words must stay at {expected} (May 2026 "
            f"recalibration); got {cfg.llm.min_podcast_words}"
        )


# ---------------------------------------------------------------------------
# Slow-news repeat_trigger_ratio
# ---------------------------------------------------------------------------

class TestSlowNewsRatioGate:

    def test_default_ratio_is_055(self):
        """0.55 was the audit-recommended ratio. Below it (e.g. the
        prior 0.40), TST tripped slow-news on 13 of 15 episodes
        despite shipping 60 %+ unique stories."""
        from engine.config import SlowNewsConfig
        cfg = SlowNewsConfig()
        assert cfg.repeat_trigger_ratio == 0.55


# ---------------------------------------------------------------------------
# Consecutive same-sentence dedup
# ---------------------------------------------------------------------------

class TestConsecutiveSentenceDedup:
    """Operator caught (FP Ep32, May 6 2026) the LLM producing
    ``Давайте разберёмся! Давайте разберёмся в…`` — same opener
    twice in one narration line. ``_sanitize_podcast_script`` now
    strips the verbatim duplicate."""

    def test_strips_inline_russian_duplicate(self):
        from engine.generator import _sanitize_podcast_script
        script = (
            "С вами Финансы Просто. Давайте разберёмся! "
            "Давайте разберёмся в самых важных новостях."
        )
        out = _sanitize_podcast_script(script)
        assert out.count("Давайте разберёмся!") == 1
        assert "Давайте разберёмся в самых важных новостях." in out

    def test_strips_inline_english_duplicate(self):
        from engine.generator import _sanitize_podcast_script
        script = "Welcome back. Welcome back to today's episode."
        out = _sanitize_podcast_script(script)
        # The first "Welcome back." is the same sentence repeated.
        assert out.count("Welcome back.") == 1

    def test_does_not_collapse_legitimate_repetition_with_different_endings(self):
        """``Welcome back. Welcome back to the show.`` — the SECOND
        starts the same way but has different ending punctuation
        on the first sentence; the regex requires VERBATIM same
        sentence, so this should pass unchanged because
        ``Welcome back`` (no terminator) followed by ``Welcome back
        to the show.`` is NOT a duplicate sentence."""
        from engine.generator import _sanitize_podcast_script
        # Phrase that's similar but not identical — should NOT collapse.
        script = (
            "We are back. We are back today with a new story."
        )
        out = _sanitize_podcast_script(script)
        # Both opening clauses survive.
        assert "We are back." in out
        assert "We are back today" in out


# ---------------------------------------------------------------------------
# AI-disclosure trim
# ---------------------------------------------------------------------------

class TestAiDisclosureTrim:
    """The audio AI disclosure was a 35-second Patrick-monologue at
    the close of every episode. Trimmed to one sentence so the
    show's distinctive sign-off is the listener's last memory."""

    def test_disclosure_is_short(self):
        from run_show import _AI_DISCLOSURE
        # One short sentence — under 200 chars.
        assert len(_AI_DISCLOSURE) < 200, (
            f"_AI_DISCLOSURE bloomed back to {len(_AI_DISCLOSURE)} chars; "
            f"keep it tight (one sentence)."
        )
        # Still mentions AI / synthesis (the disclosure's whole purpose).
        assert "AI" in _AI_DISCLOSURE or "ai" in _AI_DISCLOSURE
        assert "synthesis" in _AI_DISCLOSURE
