"""Every published title fits its platform cap and never splits a word.

This exists because the same bug shipped three times independently:
``engine.blog`` sliced ``hook[:100]``, ``engine.video_metadata._truncate``
sliced ``text[:max_len - 3]``, and ``run_show`` built the podcast RSS
title with no cap at all. YouTube found the third one for us — it
rewrote titles on every show between June and July 2026, cutting
mid-word, and emailed to say no action was required.

The point of these tests is the *property*, not the examples: whatever a
future hook looks like, in whatever language, the result fits and ends on
a word. Add a surface to ``engine.titles`` and add it here.
"""

import random
import re

import pytest

from engine.titles import (
    NEWSLETTER_SUBJECT_MAX,
    PODCAST_EPISODE_TITLE_MAX,
    WEB_TITLE_LEAD_MAX,
    YOUTUBE_TITLE_MAX,
    clip_words,
    episode_title,
    fits,
)

ELLIPSIS = "…"

# Real hooks that YouTube actually rewrote, plus the shapes that break
# naive truncation: Cyrillic, an em dash, a possessive, a decimal.
HOOKS = [
    "Virtual reality experiments show how artificial light at night changes"
    " how coral reef fish behave after dark",
    "US researchers mapped how a rare longevity gene shields the brain from"
    " Alzheimer's pathology in later life",
    "Genomic variants shape engineered T-cell safety and a mouse study shows"
    " lifelong valine restriction extends healthspan",
    "In 1935, Australia brought 102 cane toads from Hawaii to battle sugarcane"
    " beetles — but the toads bred out of control",
    "Tesla gains a stake in SpaceX by converting its $2B xAI investment,"
    " deepening ties between Musk's companies",
    "Продажи жилья"
    " в США упали до"
    " минимума за"
    " десятилетие",
    "A 1.6-trillion-parameter model matched human experts on 750 tasks",
    "Short one",
    "",
]

CAPS = [20, 40, WEB_TITLE_LEAD_MAX, NEWSLETTER_SUBJECT_MAX, YOUTUBE_TITLE_MAX]


def _splits_a_word(original: str, clipped: str) -> bool:
    """True when *clipped* stops inside a word that *original* continues.

    A single word longer than the whole cap has no boundary to cut at, so
    it is excluded — that is a genuine impossibility, not a bug.
    """
    if not clipped.endswith(ELLIPSIS):
        return False
    stem = clipped[: -len(ELLIPSIS)]
    if not original.startswith(stem):
        return False  # trailing punctuation was stripped; nothing was split
    nxt = original[len(stem):]
    return bool(nxt) and nxt[0].isalnum()


class TestClipWords:
    @pytest.mark.parametrize("cap", CAPS)
    @pytest.mark.parametrize("hook", HOOKS)
    def test_never_exceeds_the_cap(self, hook, cap):
        assert len(clip_words(hook, cap)) <= cap

    @pytest.mark.parametrize("cap", CAPS)
    @pytest.mark.parametrize("hook", HOOKS)
    def test_never_splits_a_word(self, hook, cap):
        clipped = clip_words(hook, cap)
        first_word = hook.split()[0] if hook.split() else ""
        if len(first_word) > cap:
            return  # no boundary exists inside a single over-long word
        assert not _splits_a_word(hook, clipped), (
            f"{clipped!r} cuts into a word of {hook!r}"
        )

    def test_short_text_is_returned_untouched(self):
        assert clip_words("Short one", 60) == "Short one"
        assert ELLIPSIS not in clip_words("Short one", 60)

    def test_ellipsis_only_when_something_was_removed(self):
        exact = "x" * 40
        assert clip_words(exact, 40) == exact

    def test_no_dangling_punctuation_before_the_ellipsis(self):
        out = clip_words("Beetles, moths, and toads overran the state", 12)
        assert not re.search(r"[ ,;:.—-]" + ELLIPSIS + "$", out)

    def test_single_word_longer_than_cap_still_fits(self):
        out = clip_words("Supercalifragilisticexpialidocious", 12)
        assert len(out) <= 12

    def test_handles_empty_and_none(self):
        assert clip_words("", 50) == ""
        assert clip_words(None, 50) == ""

    def test_zero_and_negative_caps(self):
        assert clip_words("anything", 0) == ""
        assert clip_words("anything", -5) == ""

    def test_fits_helper(self):
        assert fits("short", 10)
        assert not fits("a much longer string than ten", 10)


class TestEpisodeTitle:
    @pytest.mark.parametrize("hook", HOOKS)
    @pytest.mark.parametrize("num", [1, 47, 133, 555, 1234])
    def test_always_within_the_podcast_cap(self, hook, num):
        """YouTube ingests the podcast feed and rewrites anything over 100."""
        assert len(episode_title(hook, num)) <= PODCAST_EPISODE_TITLE_MAX

    @pytest.mark.parametrize("num", [7, 133, 999])
    def test_episode_label_is_never_sacrificed(self, num):
        out = episode_title(HOOKS[0], num)
        assert out.startswith(f"Ep {num}:")

    def test_russian_prefix_length_is_accounted_for(self):
        out = episode_title(HOOKS[5], 65, prefix="Выпуск")
        assert out.startswith("Выпуск 65:")
        assert len(out) <= PODCAST_EPISODE_TITLE_MAX

    def test_falls_back_when_there_is_no_hook(self):
        out = episode_title("", 12, fallback="Env Intel - Episode 12 - July 28, 2026")
        assert "Episode 12" in out
        assert len(out) <= PODCAST_EPISODE_TITLE_MAX

    def test_fallback_is_itself_clipped(self):
        out = episode_title("", 12, fallback="x " * 200)
        assert len(out) <= PODCAST_EPISODE_TITLE_MAX


class TestSurfacesStayWithinTheirCaps:
    @pytest.mark.parametrize("hook", HOOKS)
    def test_youtube_video_title(self, hook):
        from engine.video_metadata import _build_seo_title
        assert len(_build_seo_title(hook, "Planetterrian Daily")) <= YOUTUBE_TITLE_MAX

    @pytest.mark.parametrize("hook", HOOKS)
    def test_youtube_shorts_keeps_its_classifier_hint(self, hook):
        """#Shorts must survive a long hook — it drives Shorts placement."""
        from engine.video_metadata import _build_seo_title
        out = _build_seo_title(hook, "Planetterrian Daily", suffix="#Shorts")
        assert len(out) <= YOUTUBE_TITLE_MAX
        assert out.endswith("#Shorts")

    @pytest.mark.parametrize("hook", HOOKS)
    def test_blog_helper_delegates_to_the_shared_rule(self, hook):
        from engine.blog import _clip_words
        assert _clip_words(hook, WEB_TITLE_LEAD_MAX) == clip_words(
            hook, WEB_TITLE_LEAD_MAX)


class TestProperties:
    def test_random_hooks_always_fit_and_never_split(self):
        """The guarantee has to hold for hooks nobody has written yet."""
        words = [
            "alpha", "bravo", "charlie", "delta", "echo", "foxtrot",
            "extraordinarily", "hippocampal", "жилья",
            "T-cell", "$2B", "1.6-trillion", "Musk's",
        ]
        rng = random.Random(20260728)
        for _ in range(3000):
            hook = " ".join(rng.choice(words) for _ in range(rng.randint(1, 40)))
            for cap in CAPS:
                out = clip_words(hook, cap)
                assert len(out) <= cap, (hook, cap, out)
                if len(hook.split()[0]) <= cap:
                    assert not _splits_a_word(hook, out), (hook, cap, out)

    def test_episode_titles_fit_for_any_hook_and_number(self):
        rng = random.Random(1)
        words = ["reef", "fish", "longevity", "restriction", "healthspan"]
        for _ in range(1500):
            hook = " ".join(rng.choice(words) for _ in range(rng.randint(1, 40)))
            num = rng.randint(1, 9999)
            assert len(episode_title(hook, num)) <= PODCAST_EPISODE_TITLE_MAX
