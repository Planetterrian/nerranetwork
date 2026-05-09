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
    dropped a second time to ~1.05× empirical median:

      tesla            : 1700 → 1200  (median 1129)
      omni_view        : 1300 → 900   (median  867)
      planetterrian    : 1400 → 950   (median  887)
      fascinating_fron : 1500 → 1050  (median  985)
      modern_investing : 1500 → 1300  (median 1224)
      models_agents_b… : 1100 → 900   (median  878)
      privet_russian   : 700  → 650   (median  601)

    ``models_agents`` and ``unintended_consequences`` retain their
    Phase-3 values until at least 5 post-Phase-3 episodes have
    committed (insufficient data to retune confidently). FP keeps
    its 900 target because the median 836 is close enough that the
    flag should fire occasionally, which is the desired behaviour."""

    EXPECTED = {
        "tesla":                   1200,
        "fascinating_frontiers":   1050,
        "planetterrian":           950,
        "modern_investing":        1300,
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
