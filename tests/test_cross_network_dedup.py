"""Tests for the cross-network dedup signal wired in May 2026.

The runner builds a ``{cross_show_context}`` template variable from the
last 7 days of cross-show episodes (``run_show.py:844-868``) and stuffs
it into every digest prompt's ``template_vars``. This module guards two
invariants:

1. Every news-show digest prompt actually references the variable —
   otherwise the runner builds a dedup signal that the LLM never sees,
   which is exactly the bug Phase 1.1 fixed.

2. The runner always provides SOME value for the variable (even when
   the content lake has nothing or fails) so prompt rendering never
   raises ``KeyError`` mid-run.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "shows" / "prompts"

# News-show digest prompts. Narrative-mode shows (currently just UC,
# whose digest prompt is ``unintended_consequences_episode.txt``) are
# excluded — narrative-mode bypasses the news-fetch + cross-show
# context construction entirely, so wiring the variable into a
# narrative prompt would be cargo-culting.
NEWS_SHOW_DIGEST_PROMPTS = [
    "tesla_digest.txt",
    "omni_view_digest.txt",
    "planetterrian_digest.txt",
    "fascinating_frontiers_digest.txt",
    "env_intel_digest.txt",
    "models_agents_digest.txt",
    "mab_digest.txt",
    "modern_investing_digest.txt",
    "fp_digest.txt",
    "privet_russian_digest.txt",
]

# Podcast prompts (one per show including UC's narrative path) that
# should encourage cross-show promos when the topic genuinely overlaps.
ALL_PODCAST_PROMPTS = [
    "tesla_podcast.txt",
    "omni_view_podcast.txt",
    "planetterrian_podcast.txt",
    "fascinating_frontiers_podcast.txt",
    "env_intel_podcast.txt",
    "models_agents_podcast.txt",
    "mab_podcast.txt",
    "modern_investing_podcast.txt",
    "fp_podcast.txt",
    "privet_russian_podcast.txt",
    "unintended_consequences_podcast.txt",
]


@pytest.mark.parametrize("prompt_name", NEWS_SHOW_DIGEST_PROMPTS)
def test_news_show_digest_uses_cross_show_context(prompt_name):
    """Drift guard: every news-show digest prompt must reference the
    ``{cross_show_context}`` template variable.

    If a prompt is missing this, the runner happily computes the
    dedup signal in ``run_show.py:844-868`` and the LLM never sees
    it — listeners get repeated topics across shows within 24 hours.
    """
    text = (PROMPTS_DIR / prompt_name).read_text(encoding="utf-8")
    assert "{cross_show_context}" in text, (
        f"{prompt_name} doesn't reference {{cross_show_context}}. "
        f"The runner builds this signal but the LLM will never see it. "
        f"Add a CROSS-NETWORK CONTEXT block — see Phase 1.1 in the audit "
        f"plan or any sister show's digest prompt for the standard wording."
    )


@pytest.mark.parametrize("prompt_name", ALL_PODCAST_PROMPTS)
def test_podcast_prompt_has_cross_promo_block(prompt_name):
    """Every podcast prompt (across all 11 shows) must include a
    CROSS-PROMO block telling the LLM when to mention sister shows.

    Phase 1.3 of the May 2026 audit added this — without it, only UC
    encouraged cross-promos and the network felt like 11 silos. The
    rule is: ONLY mention sister shows when the topic genuinely
    overlaps, ONLY in the closing/lesson segment, single sentence
    max. Each show's prompt has its own list of relevant pairings.
    """
    text = (PROMPTS_DIR / prompt_name).read_text(encoding="utf-8")
    assert "CROSS-PROMO" in text, (
        f"{prompt_name} doesn't have a CROSS-PROMO block. Without "
        f"it, the show won't mention sister shows even when the topic "
        f"genuinely overlaps. See Phase 1.3 of the audit plan or any "
        f"other show's podcast prompt for the standard wording."
    )
    # Must explicitly forbid forced cross-promos to keep them rare.
    assert "NEVER force a connection" in text, (
        f"{prompt_name}'s CROSS-PROMO block is missing the 'NEVER force "
        f"a connection' guard. Without it, the LLM will over-cross-promo."
    )


def test_runner_always_supplies_cross_show_context():
    """The runner must always populate ``cross_show_context`` (even on
    content-lake failure or empty 7-day window) — otherwise prompt
    rendering raises ``KeyError`` mid-run."""
    runner = (REPO_ROOT / "run_show.py").read_text(encoding="utf-8")
    # The runner sets the variable in three places:
    # 1. With cross-show topics when the lake returns episodes
    # 2. With "(No recent cross-network coverage...)" when lake is empty
    # 3. With "(Cross-network context unavailable...)" when lake errors
    assert 'template_vars["cross_show_context"]' in runner, (
        "run_show.py no longer sets template_vars['cross_show_context'] — "
        "every digest prompt that uses {cross_show_context} will KeyError."
    )
    # Both fallback strings must be present so the variable is always
    # set, never missing.
    assert "No recent cross-network coverage" in runner, (
        "Empty-lake fallback for cross_show_context missing in run_show.py"
    )
    assert "Cross-network context unavailable" in runner, (
        "Error fallback for cross_show_context missing in run_show.py"
    )
