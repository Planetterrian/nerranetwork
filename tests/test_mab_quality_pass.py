"""Drift guards for the Models & Agents for Beginners (MAB) quality pass.

June 25 2026 review (docs/reviews/models_agents_beginners_review_2026_06_25.md).

The MAB prompts seeded the exact lead-in / closer sentences for the Big Story
opener and the Deep Dive payoff, and the model echoed them verbatim into nearly
every shipped episode (the same "prompt example becomes a template tic" class as
Omni-View "strongest case", EI deep-dive opener, and First Principles
lesson-template). These guards pin the de-seed so the literal templates can't
re-enter the prompts.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PODCAST = _ROOT / "shows/prompts/mab_podcast.txt"
_DIGEST = _ROOT / "shows/prompts/mab_digest.txt"


class TestDeepDiveCloserDeSeed:
    """The Deep Dive connector + payoff must not seed a verbatim template."""

    def test_podcast_does_not_seed_verbatim_connector(self):
        text = _PODCAST.read_text(encoding="utf-8")
        # The old seeded connector that echoed into ~every episode.
        assert "and that's basically what the AI is doing when it..." not in text

    def test_podcast_does_not_seed_not_so_scary_as_closer_example(self):
        text = _PODCAST.read_text(encoding="utf-8")
        # The old seeded closer example line. The de-seed must still NAME the
        # banned phrase so the model knows to avoid it, but must not present it
        # as the model's instruction to "End with: ...".
        assert 'End with: "and that\'s basically how [concept] works' not in text
        # The de-seed explicitly bans the verbatim closer.
        assert "not so scary, right?" in text  # named as banned
        assert "phrase it FRESH" in text

    def test_digest_does_not_seed_verbatim_analogy_template(self):
        text = _DIGEST.read_text(encoding="utf-8")
        # Old step 3/4 seeds.
        assert (
            'And that\'s basically what [technology] is doing when it '
            '[does the thing].' not in text
        )
        assert (
            'So next time someone says [intimidating term], you can tell '
            'them' not in text
        )
        # De-seed keeps the structure but requires fresh phrasing.
        assert "phrased FRESH every episode" in text


class TestBigStoryOpenerDeSeed:
    """The Big Story opener guidance must ban the over-used template shapes."""

    def test_opener_variation_still_required(self):
        text = _PODCAST.read_text(encoding="utf-8")
        assert "VARY THE OPENER EVERY EPISODE" in text

    def test_something_just_happened_is_banned(self):
        text = _PODCAST.read_text(encoding="utf-8")
        # The new emergent tic (5/10 episodes) — must be called out as banned,
        # not offered as an example shape.
        assert '"Something wild just happened:"' not in text  # no longer an example
        assert "just happened" in text  # named in the ban
        assert "BANNED" in text
