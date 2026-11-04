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
    CLAUSE_BREAK_WORDS,
    CLAUSE_STUB_TAIL_WORDS,
    EMAIL_ALSO_LINE_MAX,
    FIRST_CLAUSE_MIN_WORDS,
    NEWSLETTER_SUBJECT_MAX,
    PODCAST_EPISODE_TITLE_MAX,
    WEB_TITLE_LEAD_MAX,
    WEB_TITLE_SEPARATOR,
    X_ITEM_TITLE_MAX,
    YOUTUBE_TITLE_MAX,
    clip_words,
    episode_title,
    fit_first_clause,
    fits,
    web_page_title,
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

CAPS = [20, 40, WEB_TITLE_LEAD_MAX, EMAIL_ALSO_LINE_MAX, NEWSLETTER_SUBJECT_MAX,
        YOUTUBE_TITLE_MAX, X_ITEM_TITLE_MAX]


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


# The interview theses whose feed titles ended in "…" on Nov 4 2026 (Ep12-15
# of The Age of AI, Ep3-4 of Nerra Voices), with the label each sits behind.
INTERVIEW_THESES = [
    ("Ep12: Thor Hesselberg",
     "A recruitment founder counters AI deepfakes flooding hiring pipelines by"
     " building portable verified credentials that replace self-reported CVs"
     " with employer-confirmed trust scores."),
    ("Ep13: Jon Cheney",
     "A founder racing to embed agentic systems and fractional CAIO leadership"
     " across enterprises now tests whether those same tools can scale human"
     " judgment without eroding the critical thinking his own doctrine requires."),
    ("Ep14: Piper Martz",
     "How a DTC lifecycle operator moving from static CRM automations to agentic"
     " engagement stacks experiences the loss of junior execution practice and"
     " the limits of community dinners in closing the documented gender gap in"
     " AI adoption."),
    ("Ep15: Michael Kamins",
     "A CPG hiring veteran builds candidate-owned living portfolios that let AI"
     " surface matches without rejections so humans can restore authenticity"
     " and cut early turnover where static resumes failed."),
    ("Ep3: Scott Pulcini",
     "A scalper who once handled a tenth of E-mini volume rebuilt a durable edge"
     " by reading iceberg orders and stop runs after algorithms erased his"
     " original speed advantage, then teaches the resulting rule set to retail"
     " traders."),
    ("Ep4: Stuart Berkowitz",
     "Translating scattered trial data into a public Bayesian atlas that models"
     " upper-bound life-year gains from overlapping interventions while exposing"
     " every assumption for inspection."),
]


class TestFitFirstClause:
    """Nov 4 2026: a sentence that does not fit gives its FIRST CLAUSE, whole,
    before anything is clipped — and when a clause is returned it is a
    prefix of the sentence that ends on a word, with no ellipsis."""

    @pytest.mark.parametrize("hook", HOOKS)
    @pytest.mark.parametrize("cap", CAPS)
    def test_never_exceeds_the_cap(self, hook, cap):
        assert len(fit_first_clause(hook, cap)) <= cap

    @pytest.mark.parametrize("hook", HOOKS)
    @pytest.mark.parametrize("cap", CAPS)
    def test_a_clause_is_a_whole_prefix_and_a_clip_is_an_honest_one(self, hook, cap):
        out = fit_first_clause(hook, cap)
        if out.endswith(ELLIPSIS):
            assert out == clip_words(hook, cap)
            assert not _splits_a_word(hook, out)
        elif out != hook.strip():
            assert hook.strip().startswith(out)
            nxt = hook.strip()[len(out):]
            assert not nxt[:1].isalnum(), f"{out!r} stops inside a word of {hook!r}"
            assert len(out.split()) >= FIRST_CLAUSE_MIN_WORDS
            assert out.split()[-1].lower() not in CLAUSE_BREAK_WORDS
            assert out.split()[-1].lower() not in CLAUSE_STUB_TAIL_WORDS

    def test_the_interview_theses_fit_whole_behind_their_labels(self):
        for label, thesis in INTERVIEW_THESES:
            room = PODCAST_EPISODE_TITLE_MAX - len(label) - len(" — ")
            out = fit_first_clause(thesis, room)
            title = f"{label} — {out}"
            assert len(title) <= PODCAST_EPISODE_TITLE_MAX, title
            assert ELLIPSIS not in title, title
            assert thesis.startswith(out) and len(out.split()) >= FIRST_CLAUSE_MIN_WORDS, title
            assert not title.endswith(("—", "-", ",", " ")), title

    def test_strong_separators_are_tried_first_in_order(self):
        text = "In 1935, Australia brought cane toads from Hawaii — but the toads bred out of control"
        assert fit_first_clause(text, 70) == "In 1935, Australia brought cane toads from Hawaii"
        text = "A first clause that fits here: the second clause is the long one that does not"
        assert fit_first_clause(text, 40) == "A first clause that fits here"
        text = ("The first clause has five words; the second clause is much longer"
                " than that and runs on")
        assert fit_first_clause(text, 45) == "The first clause has five words"

    def test_a_list_comma_is_not_a_clause_break(self):
        text = ("A broker weighs what judgment, intuition, and human connection he"
                " refuses to delegate while seeking balance through daily work")
        # Wide enough for the clause before "while": the list commas and the
        # "and" that closes the list are never where it cuts.
        assert fit_first_clause(text, 90) == (
            "A broker weighs what judgment, intuition, and human connection he refuses to delegate")
        # Too narrow for any clause: the honest clip, never a list fragment.
        out = fit_first_clause(text, 70)
        assert out == clip_words(text, 70) and out.endswith(ELLIPSIS)
        assert not out.rstrip(ELLIPSIS).endswith(("judgment", "intuition")), out
        text = "A CEO weighs whether tools for copy, targeting and optimization erode demand for oversight"
        assert fit_first_clause(text, 60) == "A CEO weighs whether tools"

    def test_a_stub_falls_through_to_clip_words(self):
        text = "In 1935, Australia brought cane toads from Hawaii to battle beetles"
        out = fit_first_clause(text, 14)
        assert out == clip_words(text, 14) and out.endswith(ELLIPSIS)

    def test_a_hyphenated_compound_is_never_cut_and_a_clause_never_ends_on_a_determiner(self):
        """Nov 4 2026 review: "so" / "on" / "co" are break words, but not when
        they open "so-called" / "on-site" / "co-founder" — the cut in front of
        the compound shipped "…fights the" and "…builds the first"."""
        text = "A founder builds the first on-site clinic for a factory town that never had one"
        assert fit_first_clause(text, 50) == "A founder builds the first on-site clinic"
        text = "A founder sells the business to his co-founder before the market turns"
        assert fit_first_clause(text, 36) == "A founder sells the business"
        text = ("A recruitment founder fights the so-called talent crunch with verified"
                " credentials and trust")
        out = fit_first_clause(text, 45)
        assert out == clip_words(text, 45) and out.endswith(ELLIPSIS)
        # A clause may not end on an article or a possessive even when the
        # next word is a break word used as a noun ("the before and after").
        text = "A recruitment founder measures the before and after of every product launch"
        out = fit_first_clause(text, 40)
        assert out == clip_words(text, 40) and out.endswith(ELLIPSIS)
        for tail in ("the", "a", "an", "its", "their", "his", "her", "our", "this", "those"):
            assert tail in CLAUSE_STUB_TAIL_WORDS

    def test_short_text_and_edge_caps(self):
        assert fit_first_clause("Short one", 50) == "Short one"
        assert fit_first_clause("", 50) == ""
        assert fit_first_clause(None, 50) == ""
        assert fit_first_clause("anything", 0) == ""

    def test_random_sentences_always_fit_and_never_split(self):
        rng = random.Random(2026_11_04)
        words = ["founder", "builds", "verified", "credentials", "that", "replace",
                 "CVs", "by", "reading", "orders", "and", "stop", "runs", "while",
                 "teaching", "retail", "traders,", "quietly", "—", "so", "humans",
                 "restore", "authenticity", "in", "hiring", "atlas:", "models"]
        for _ in range(400):
            text = " ".join(rng.choice(words) for _ in range(rng.randint(3, 40)))
            cap = rng.randint(1, 120)
            out = fit_first_clause(text, cap)
            assert len(out) <= cap
            if not out.endswith(ELLIPSIS) and out != text.strip():
                assert text.strip().startswith(out)
                assert not text.strip()[len(out):][:1].isalnum()


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

    @pytest.mark.parametrize("hook", HOOKS)
    def test_x_post_item_heading(self, hook):
        """Nov 3 2026: an X post's heading in a digest item is clipped here,
        never sliced in ``engine.fetcher`` (``desc[:100]``), and a post that
        arrives WITH a title is clipped the same way — M&A Ep222 made an
        entire 60-word post the item heading."""
        from engine.fetcher import _x_post_entry
        post = (hook + " ") * 4
        for title in ("", post):
            entry = _x_post_entry(title=title, desc=post, url="https://x.com/a/status/1",
                                  link="", post_date="", label="A", handle="a",
                                  now_iso="2026-11-03T00:00:00+00:00")
            assert len(entry["title"]) <= X_ITEM_TITLE_MAX
            assert entry["title"] == clip_words(title or post.strip(), X_ITEM_TITLE_MAX)
            assert not _splits_a_word(post.strip(), entry["title"])


SHOW_NAMES = ["Tesla Shorts Time", "Привет, Русский!", "The Age of AI", "Omni View"]


class TestWebPageTitle:
    """Nov 3 2026: a page ``<title>`` is ``"<lead> · <Show>"`` — the lead
    clipped to WEB_TITLE_LEAD_MAX on a word, the show whole, no episode
    number — so the show name begins inside the ~60 characters a search
    result displays."""

    @pytest.mark.parametrize("show", SHOW_NAMES)
    @pytest.mark.parametrize("hook", HOOKS)
    def test_shape_and_budget(self, hook, show):
        out = web_page_title(hook, show)
        assert out.endswith(show)
        lead = out[: -len(show)] if out != show else ""
        if lead:
            assert lead.endswith(WEB_TITLE_SEPARATOR), out
            lead = lead[: -len(WEB_TITLE_SEPARATOR)]
            assert len(lead) <= WEB_TITLE_LEAD_MAX, (lead, len(lead))
            assert lead == clip_words(hook, WEB_TITLE_LEAD_MAX)
            assert not _splits_a_word(hook, lead), (hook, lead)
        assert " — Ep" not in out and "| " not in out

    def test_lead_budget_leaves_the_show_inside_the_displayed_window(self):
        # Google renders ~60 characters; with a 58-character lead the
        # separator and the show's first letter are still inside it.
        assert WEB_TITLE_LEAD_MAX + len(WEB_TITLE_SEPARATOR) <= 62
        assert WEB_TITLE_LEAD_MAX == 58

    def test_no_lead_is_the_show_alone_and_the_show_is_never_doubled(self):
        assert web_page_title("", "Tesla Shorts Time") == "Tesla Shorts Time"
        assert web_page_title(None, "Tesla Shorts Time") == "Tesla Shorts Time"
        assert web_page_title("Models & Agents", "Models & Agents") == "Models & Agents"
        assert web_page_title("models & agents", "Models & Agents") == "Models & Agents"

    def test_short_lead_is_untouched(self):
        assert web_page_title("Short one", "Omni View") == "Short one · Omni View"


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

    def test_web_page_titles_keep_the_show_and_the_budget_for_any_hook(self):
        rng = random.Random(20261103)
        words = ["Tesla", "registrations", "rose", "248", "percent", "жилья",
                 "T-cell", "$2B", "1.6-trillion", "Musk's", "extraordinarily"]
        for _ in range(1500):
            hook = " ".join(rng.choice(words) for _ in range(rng.randint(1, 30)))
            show = rng.choice(SHOW_NAMES)
            out = web_page_title(hook, show)
            assert out.endswith(show), (hook, out)
            lead = out[: -len(show) - len(WEB_TITLE_SEPARATOR)]
            assert len(lead) <= WEB_TITLE_LEAD_MAX, (hook, out)
            if len(hook.split()[0]) <= WEB_TITLE_LEAD_MAX:
                assert not _splits_a_word(hook, lead), (hook, out)
