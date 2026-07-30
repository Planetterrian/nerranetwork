"""Tests for the dynamic daily intro system (engine.intros)."""

import datetime

import pytest

from engine.intros import (
    build_closing_block,
    build_intro_line,
    get_show_host,
    _pick,
    _milestone_note,
)


# ---------------------------------------------------------------------------
# Deterministic selection
# ---------------------------------------------------------------------------

class TestPick:
    def test_same_day_same_result(self):
        pool = ["a", "b", "c", "d"]
        d = datetime.date(2026, 3, 15)
        r1 = _pick(pool, "tesla", d, salt="greeting")
        r2 = _pick(pool, "tesla", d, salt="greeting")
        assert r1 == r2

    def test_different_days_can_differ(self):
        pool = list("abcdefghijklmnop")  # large pool to reduce collision chance
        results = set()
        for day in range(1, 30):
            d = datetime.date(2026, 3, day)
            results.add(_pick(pool, "tesla", d, salt="greeting"))
        # With 29 days and 16 options, we should see at least 3 different values
        assert len(results) >= 3

    def test_different_shows_can_differ(self):
        pool = list("abcdefghijklmnop")
        d = datetime.date(2026, 3, 15)
        results = set()
        for show in ["tesla", "omni_view", "env_intel", "models_agents", "planetterrian"]:
            results.add(_pick(pool, show, d, salt="greeting"))
        assert len(results) >= 2

    def test_empty_pool(self):
        assert _pick([], "tesla", datetime.date(2026, 1, 1)) == ""

    def test_single_item(self):
        assert _pick(["only"], "tesla", datetime.date(2026, 1, 1)) == "only"


# ---------------------------------------------------------------------------
# Milestone detection
# ---------------------------------------------------------------------------

class TestMilestones:
    def test_episode_100(self):
        note = _milestone_note(100)
        assert note is not None
        assert "one hundred" in note or "100" in note

    def test_episode_200(self):
        assert _milestone_note(200) is not None

    def test_episode_500(self):
        assert _milestone_note(500) is not None

    def test_episode_300(self):
        # Generic round number
        note = _milestone_note(300)
        assert note is not None

    def test_no_milestone(self):
        assert _milestone_note(42) is None
        assert _milestone_note(1) is None
        assert _milestone_note(99) is None


# ---------------------------------------------------------------------------
# build_intro_line
# ---------------------------------------------------------------------------

class TestBuildIntroLine:
    def test_tesla_contains_show_name(self):
        intro = build_intro_line(
            "tesla",
            episode_num=403,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        # June 2026: "Daily" dropped from the spoken name so the audio
        # brand matches the Apple/Spotify listing ("Tesla Shorts Time").
        assert "Tesla Shorts Time" in intro
        assert "Tesla Shorts Time Daily" not in intro
        assert "Patrick:" in intro

    def test_env_intel_contains_show_name(self):
        intro = build_intro_line(
            "env_intel",
            episode_num=10,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "Environmental Intelligence" in intro
        assert "Host:" in intro

    def test_models_agents_contains_show_name(self):
        intro = build_intro_line(
            "models_agents",
            episode_num=50,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "Models and Agents" in intro

    def test_finansy_prosto_russian(self):
        intro = build_intro_line(
            "finansy_prosto",
            episode_num=5,
            today_str="15 марта 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "Финансы Просто" in intro
        assert "Ведущая:" in intro

    def test_unknown_show_returns_generic(self):
        intro = build_intro_line(
            "nonexistent_show",
            episode_num=1,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "episode 1" in intro

    def test_monday_uses_day_specific_greetings(self):
        """Monday (weekday=0) should use day_colors greetings if available."""
        monday = datetime.date(2026, 3, 16)  # March 16, 2026 is a Monday
        intro = build_intro_line(
            "tesla",
            episode_num=10,
            today_str="March 16, 2026",
            date=monday,
        )
        # Should still contain show name regardless of day
        assert "Tesla Shorts Time" in intro

    def test_intro_does_not_vary_by_day(self):
        """The identity line is fixed for a given episode number.

        Before July 30 2026 this line was the whole opening and rotated
        greeting / opener / framing pools per day, which is why it was
        long enough to matter. It is now one short sentence, so the same
        episode must render identically whatever day it is built on —
        day rotation returning here would mean the long opener came
        back with it.
        """
        rendered = {
            build_intro_line(
                "tesla",
                episode_num=403,
                today_str=f"March {day}, 2026",
                date=datetime.date(2026, 3, day),
            )
            for day in range(1, 28)
        }
        assert len(rendered) == 1

    def test_milestone_in_intro(self):
        intro = build_intro_line(
            "tesla",
            episode_num=100,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "one hundred" in intro or "milestone" in intro


# ---------------------------------------------------------------------------
# build_closing_block
# ---------------------------------------------------------------------------

class TestBuildClosingBlock:
    def test_tesla_closing(self):
        closing = build_closing_block(
            "tesla",
            episode_num=100,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "Patrick:" in closing
        assert "Tesla" in closing or "tomorrow" in closing or "listening" in closing

    def test_env_intel_closing(self):
        closing = build_closing_block(
            "env_intel",
            episode_num=10,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "Host:" in closing

    def test_unknown_show_generic(self):
        closing = build_closing_block(
            "nonexistent",
            episode_num=1,
            today_str="March 15, 2026",
        )
        assert "tomorrow" in closing


# ---------------------------------------------------------------------------
# get_show_host
# ---------------------------------------------------------------------------

class TestGetShowHost:
    def test_tesla(self):
        assert get_show_host("tesla") == "Patrick"

    def test_env_intel(self):
        assert get_show_host("env_intel") == "Host"

    def test_finansy_prosto(self):
        assert get_show_host("finansy_prosto") == "Ведущая"

    def test_unknown(self):
        assert get_show_host("nonexistent") == "Patrick"


# ---------------------------------------------------------------------------
# All registered shows produce valid intros
# ---------------------------------------------------------------------------

_ALL_SHOWS = [
    "tesla", "omni_view", "fascinating_frontiers", "planetterrian",
    "env_intel", "models_agents", "models_agents_beginners",
    "finansy_prosto", "privet_russian", "modern_investing",
    "unintended_consequences", "dp_pod",
]

@pytest.mark.parametrize("show_slug", _ALL_SHOWS)
def test_all_shows_produce_intros(show_slug):
    intro = build_intro_line(
        show_slug,
        episode_num=42,
        today_str="March 15, 2026",
        date=datetime.date(2026, 3, 15),
    )
    assert len(intro) > 20
    assert ":" in intro  # should have host prefix


@pytest.mark.parametrize("show_slug", _ALL_SHOWS)
def test_all_shows_produce_closings(show_slug):
    closing = build_closing_block(
        show_slug,
        episode_num=42,
        today_str="March 15, 2026",
        date=datetime.date(2026, 3, 15),
    )
    assert len(closing) > 20
    assert ":" in closing


# ---------------------------------------------------------------------------
# YouTube channel CTA in closing block
# ---------------------------------------------------------------------------

def test_closing_block_appends_youtube_cta_when_handle_set():
    closing = build_closing_block(
        "tesla",
        episode_num=42,
        today_str="April 30, 2026",
        youtube_channel_handle="@NerraNetwork",
    )
    # The "@" is stripped from the SPOKEN handle: the TTS voices it as the
    # word "at", which collided with the call-out's own "at" and shipped as
    # "...find us on YouTube at at Nerra Network" in 49+ episodes.
    # The EN CamelCase handle is also split to the spaced brand "Nerra Network"
    # so the TTS pronounces it identically to the promo's "Nerra Network" and
    # the "nerranetwork.com" URL (the compound "NerraNetwork" drifted).
    assert "Nerra Network" in closing
    assert "NerraNetwork" not in closing  # compound split into the spaced brand
    assert "@NerraNetwork" not in closing
    assert "at at" not in closing.lower()
    assert "YouTube" in closing
    assert "show notes" in closing


def test_closing_block_omits_youtube_cta_without_handle():
    closing = build_closing_block(
        "tesla",
        episode_num=42,
        today_str="April 30, 2026",
    )
    assert "@NerraNetwork" not in closing
    assert "YouTube" not in closing


def test_closing_block_youtube_cta_idempotent():
    """If the closing already mentions YouTube (e.g. handcrafted in
    show personality), the helper should not duplicate the line."""
    from engine.intros import _maybe_append_youtube_cta
    closing = "Patrick: That's it. Watch us on YouTube tomorrow."
    out = _maybe_append_youtube_cta(closing, "@NerraNetwork")
    # No duplicate "YouTube" sentence appended.
    assert out == closing


def test_closing_block_supports_russian_handle():
    closing = build_closing_block(
        "finansy_prosto",
        episode_num=5,
        today_str="30 апреля 2026",
        youtube_channel_handle="@NerraRU",
    )
    # Spoken handle without the "@" sigil (voiced as "at"), and the call-out
    # itself is in Russian — Финансы Просто's host speaks Russian, so the
    # English "find us on YouTube" line was the same wart as the English AI
    # disclosure localized in June 2026.
    assert "NerraRU" in closing
    assert "@NerraRU" not in closing
    assert "YouTube" in closing
    assert "show notes" not in closing  # English call-out replaced
    assert "Ссылка" in closing          # Russian call-out present


# ---------------------------------------------------------------------------
# Cold-open contract (July 30 2026)
#
# The change: every episode's first spoken words are the hook. Before it,
# 10 s of theme music played, then the host spent ~18 more seconds on
# "Welcome back to <show>, episode N, it's <date>, I'm Patrick in
# Vancouver, let's dive into today's news" — the first fact arrived around
# second 28. Measured cost on YouTube long-form: median retention 10.7%
# (EN) / 6.3% (RU), average view durations of 18-85 s on 5-13 minute
# videos. Shorts, which skip the intro entirely, run ~42%.
#
# These guards pin the three pieces that a later edit could quietly undo:
# the identity line stays short and dateless, the prompts keep the hook
# ahead of the identity line, and the YAMLs keep the voice starting at 0.
# ---------------------------------------------------------------------------

import re
from pathlib import Path

import yaml

from engine.intros import _COLD_OPEN_BANNED, _SHOW_PERSONALITIES, build_cold_open_spec

_REPO = Path(__file__).resolve().parent.parent
_SHOWS = _REPO / "shows"
_PROMPTS = _SHOWS / "prompts"

_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December",
           "января", "февраля", "марта", "апреля", "мая", "июня", "июля",
           "августа", "сентября", "октября", "ноября", "декабря")

# Every show that renders {intro_line} through run_show, mapped to its
# podcast prompt. age_of_ai is deliberately absent from the prompt-order
# check below (its production path is pipelines/voices/, not run_show) but
# still has to satisfy the identity-line rules.
_PROMPT_FOR_SLUG = {
    "tesla": "tesla_podcast.txt",
    "spacex": "spacex_podcast.txt",
    "omni_view": "omni_view_podcast.txt",
    "fascinating_frontiers": "fascinating_frontiers_podcast.txt",
    "planetterrian": "planetterrian_podcast.txt",
    "env_intel": "env_intel_podcast.txt",
    "models_agents": "models_agents_podcast.txt",
    "models_agents_beginners": "mab_podcast.txt",
    "modern_investing": "modern_investing_podcast.txt",
    "unintended_consequences": "unintended_consequences_podcast.txt",
    "first_principles": "first_principles_podcast.txt",
    "finansy_prosto": "fp_podcast.txt",
    "privet_russian": "privet_russian_podcast.txt",
}


class TestIdentityLineIsShortAndDateless:
    def test_no_show_speaks_the_date(self):
        """The date is in the metadata and stamps the episode stale.

        It was the single worst offender in the old opener: someone
        arriving from search three weeks later heard "it's July 30" as
        the second thing in the episode.
        """
        for slug in _SHOW_PERSONALITIES:
            intro = build_intro_line(
                slug, episode_num=42, today_str="July 30, 2026",
                date=datetime.date(2026, 7, 30),
            )
            for month in _MONTHS:
                assert month not in intro, f"{slug} speaks a date: {intro}"
            assert "2026" not in intro, f"{slug} speaks a year: {intro}"

    def test_identity_line_stays_short(self):
        """One sentence of identity, plus an optional short tail.

        The old line ran ~35 words. A regression here means the opener
        crept back in, whatever the wording.
        """
        for slug in _SHOW_PERSONALITIES:
            intro = build_intro_line(
                slug, episode_num=42, today_str="July 30, 2026",
                date=datetime.date(2026, 7, 30),
            )
            words = len(intro.split())
            assert words <= 20, f"{slug} identity line is {words} words: {intro}"

    def test_no_cliche_openers_in_identity_line(self):
        for slug in _SHOW_PERSONALITIES:
            intro = build_intro_line(
                slug, episode_num=42, today_str="July 30, 2026",
                date=datetime.date(2026, 7, 30),
            ).lower()
            for banned in _COLD_OPEN_BANNED:
                assert banned not in intro, f"{slug}: banned {banned!r} in {intro!r}"

    def test_russian_show_identity_line_is_russian(self):
        """Финансы Просто is hosted entirely in Russian.

        The default identity template is English, so without a per-show
        ``identity_template`` the trim would have handed an English
        sentence to a Russian-language show.
        """
        intro = build_intro_line(
            "finansy_prosto", episode_num=30, today_str="30 июля 2026",
            date=datetime.date(2026, 7, 30),
        )
        assert "Финансы Просто" in intro
        assert "This is" not in intro
        assert "episode" not in intro
        assert "выпуск" in intro

    def test_dp_pod_still_names_both_hosts(self):
        """Two-voice show — the listener has to learn which voice is which.

        Dan says his OWN name (the Ep016 name-swap rule).
        """
        intro = build_intro_line(
            "dp_pod", episode_num=16, today_str="July 30, 2026",
            date=datetime.date(2026, 7, 30),
        )
        assert intro.startswith("DAN:")
        assert "Dan Perra" in intro and "Patrick Novak" in intro

    def test_age_of_ai_still_discloses_the_ai_host(self):
        """Every Age of AI episode must disclose that its host is an AI.

        The legacy rotating openers carried that disclosure, so the trim
        keeps a short version rather than dropping it.
        """
        intro = build_intro_line(
            "age_of_ai", episode_num=2, today_str="July 30, 2026",
            date=datetime.date(2026, 7, 30),
        )
        assert "Mira" in intro
        assert "AI" in intro


class TestColdOpenSpec:
    def test_spec_carries_no_example_sentence(self):
        """De-seed by shape, never with a quotable example.

        Every seeded template tic in this network's history came from a
        prompt supplying the literal sentence it wanted. The only quoted
        strings in this spec are the BANNED phrases.
        """
        spec = build_cold_open_spec("tesla")
        quoted = re.findall(r'"([^"]+)"', spec)
        for q in quoted:
            assert q.lower() in _COLD_OPEN_BANNED, (
                f"cold-open spec quotes {q!r}, which is not a banned phrase — "
                "a quotable specimen is how a tic gets seeded network-wide"
            )

    def test_spec_bans_the_cliches(self):
        spec = build_cold_open_spec("tesla").lower()
        for banned in ("welcome to", "let's dive in", "buckle up", "today is"):
            assert banned in spec

    def test_spec_forbids_date_and_greeting(self):
        spec = build_cold_open_spec("tesla").lower()
        assert "no greeting" in spec
        assert "no date" in spec

    def test_russian_spec_is_russian(self):
        spec = build_cold_open_spec("finansy_prosto", is_ru=True)
        assert "ХОЛОДНОЕ ОТКРЫТИЕ" in spec
        assert "COLD OPEN" not in spec


class TestPromptsPutTheHookFirst:
    """The structural guarantee: {hook} precedes {intro_line}.

    This is the whole change. A prompt edit that reorders these two
    placeholders puts the housekeeping back in front of the value
    without changing a single line of Python, so it is pinned here.
    """

    @staticmethod
    def _placement_offset(text, placeholder):
        """Offset of the line that IS the placeholder, not one that mentions it.

        Every prompt also names ``{intro_line}`` in prose — the brand
        rules say to copy it verbatim — and that mention sits near the
        top of the file. The placement is the line whose entire content
        is the placeholder.
        """
        offset = 0
        for line in text.splitlines(keepends=True):
            if line.strip() == placeholder:
                return offset
            offset += len(line)
        return None

    def test_hook_precedes_intro_line_in_every_prompt(self):
        for slug, filename in _PROMPT_FOR_SLUG.items():
            text = (_PROMPTS / filename).read_text(encoding="utf-8")
            assert "{hook}" in text, f"{filename} lost its {{hook}}"
            intro_at = self._placement_offset(text, "{intro_line}")
            assert intro_at is not None, (
                f"{filename} has no standalone {{intro_line}} line — the "
                "identity line is no longer placed, only described"
            )
            assert text.index("{hook}") < intro_at, (
                f"{filename}: {{intro_line}} is placed before {{hook}} — the "
                "episode would open on housekeeping again"
            )

    def test_hook_appears_exactly_once(self):
        """Two {hook} sites would speak the hook twice."""
        for slug, filename in _PROMPT_FOR_SLUG.items():
            text = (_PROMPTS / filename).read_text(encoding="utf-8")
            assert text.count("{hook}") == 1, f"{filename} has multiple {{hook}}"

    def test_russian_cold_open_labels_match_each_shows_own_rule(self):
        """The two Russian prompts disagree about speaker labels.

        Финансы Просто requires every line to start with «Ведущая:» —
        feminine, because Olya hosts it; the masculine «Ведущий:» is
        both the wrong label and the wrong gender. Привет, Русский!
        forbids speaker labels outright ("This is a SOLO host show — do
        NOT prefix lines"). The first draft of this change got both
        wrong, so both are pinned.
        """
        fp = (_PROMPTS / "fp_podcast.txt").read_text(encoding="utf-8")
        fp_hook = next(l for l in fp.splitlines() if "{hook}" in l)
        assert fp_hook.startswith("Ведущая:"), fp_hook

        pr = (_PROMPTS / "privet_russian_podcast.txt").read_text(encoding="utf-8")
        pr_hook = next(l for l in pr.splitlines() if "{hook}" in l)
        assert pr_hook.strip() == "{hook}", (
            f"privet_russian labels its cold open ({pr_hook!r}) but the same "
            "prompt forbids speaker labels"
        )

    def test_every_prompt_injects_the_cold_open_spec(self):
        for slug, filename in _PROMPT_FOR_SLUG.items():
            text = (_PROMPTS / filename).read_text(encoding="utf-8")
            assert "{cold_open_spec}" in text, (
                f"{filename} does not inject {{cold_open_spec}} — it would "
                "cold-open with no rules about what the first words must do"
            )


class TestVoiceStartsImmediately:
    """No show may reintroduce a music-alone wait before the first words.

    All 13 run_show shows override the network defaults, so a partial
    revert is a per-file edit that this catches.
    """

    @staticmethod
    def _audio(slug):
        from engine.config import load_config
        return load_config(_SHOWS / f"{slug}.yaml").audio

    def test_no_show_delays_the_voice(self):
        for slug in _PROMPT_FOR_SLUG:
            audio = self._audio(slug)
            assert audio.voice_intro_delay == 0.0, (
                f"{slug} delays the voice by {audio.voice_intro_delay}s — "
                "the hook no longer lands in the first second"
            )

    def test_music_alone_period_is_a_breath_not_a_wait(self):
        for slug in _PROMPT_FOR_SLUG:
            audio = self._audio(slug)
            assert audio.intro_duration <= 5.0, (
                f"{slug} has intro_duration {audio.intro_duration}s"
            )

    def test_network_default_matches(self):
        raw = yaml.safe_load((_SHOWS / "_defaults.yaml").read_text(encoding="utf-8"))
        assert raw["audio"]["voice_intro_delay"] == 0.0
        assert raw["audio"]["intro_duration"] == 3.0

    def test_music_still_plays_over_the_open(self):
        """The open is a cold open in structure, not a bare one in sound.

        Rendered A/B at merge time: with the theme playing from t=0 and
        the voice entering at t=0, the sidechain compressor holds the
        music at the same level under the opening line as under the rest
        of the episode (-31.7 dB at t=0..3 and at t=240 alike, measured
        above 2 kHz against a 1 kHz tone voice), and integrated loudness
        stays on target (-16.2 LUFS). So intro_volume must stay > 0 —
        dropping the music would make the change a bare cold open, which
        is not what was verified.
        """
        for slug in _PROMPT_FOR_SLUG:
            audio = self._audio(slug)
            assert audio.intro_volume > 0.0, f"{slug} has no intro music"


class TestDeliverySpec:
    """Performance direction, injected globally (July 30 2026).

    A DELIVERY block used to live in the prompts and was dropped in May
    2026: of 56 sampled scripts only 10 carried any tag. A first attempt
    at reviving it here asked for a 3-6 tag budget and produced ZERO tags
    in a live Grok generation — the same failure, twice measured.

    So the spec leads with prose craft, which a live A/B showed the model
    DOES follow (physical verbs, sentence-length contrast, translating a
    big number into something picturable), and demotes tags to an
    optional cap of 3. Rhythm from sentence construction is the mechanism;
    tags are the garnish.
    """

    def test_only_sanctioned_tags_are_offered(self):
        from engine.intros import _SANCTIONED_TAGS, build_delivery_spec
        spec = build_delivery_spec("tesla")
        for tag in _SANCTIONED_TAGS:
            assert tag in spec, tag
        # Tags known to be VOICED aloud by Grok must never be suggested.
        for leak in ("<fast>", "<slow>", "<whisper>", "[laugh]",
                     "<build-intensity>", "<soft>", "<loud>"):
            assert leak not in spec, f"{leak} has shipped as spoken audio"

    def test_carries_no_example_sentence(self):
        """De-seed by shape — the same rule the cold-open spec follows."""
        import re
        from engine.intros import build_delivery_spec
        spec = build_delivery_spec("tesla")
        assert not re.search(r'"[A-Z][^"]{25,}"', spec), (
            "a quotable specimen is how a tic gets seeded network-wide")

    def test_tag_budget_is_stated_and_small(self):
        spec = __import__("engine.intros", fromlist=["x"]).build_delivery_spec("tesla")
        assert "at most 3" in spec
        assert "OPTIONAL" in spec

    def test_russian_variant_is_russian(self):
        from engine.intros import build_delivery_spec
        spec = build_delivery_spec("finansy_prosto", is_ru=True)
        assert "ПОДАЧА" in spec and "DELIVERY" not in spec

    def test_every_podcast_prompt_injects_it(self):
        """Global by construction — no future propagation pass."""
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        prompts = sorted((root / "shows" / "prompts").glob("*_podcast.txt"))
        assert len(prompts) >= 15
        for p in prompts:
            assert "{delivery_spec}" in p.read_text(encoding="utf-8"), p.name

    def test_runner_always_supplies_it(self):
        """Asserted against engine/pipeline.py — the path that RUNS.

        This test used to check run_show.py, which built a `pod_vars`
        dict that was never passed to run_generation_phase. It passed
        while nothing supplied the key, and every show died with
        `KeyError: 'cold_open_spec'` on 2026-07-30. The dead block is
        gone; the assertion now points at the live builder.

        tests/test_podcast_prompt_placeholders.py covers this
        behaviourally by rendering every prompt through the real path.
        """
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent
               / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'pod_vars.setdefault(' in src
        assert '"delivery_spec"' in src


class TestColdOpenIsCompelling:
    """The July 30 2026 revision, after a live A/B on real Grok output."""

    def test_no_longer_asks_for_wire_report_prose(self):
        """That instruction measurably flattened the writing.

        With it, Grok produced press-release register; without any spec it
        produced livelier prose but a cliche greeting. The spec now keeps
        the wire report's ACCURACY bar while explicitly rejecting its
        voice.
        """
        from engine.intros import build_cold_open_spec
        spec = build_cold_open_spec("tesla")
        assert "NOT written like one" in spec
        assert "announcer cadence" in spec

    def test_asks_for_the_least_expected_fact(self):
        from engine.intros import build_cold_open_spec
        spec = build_cold_open_spec("tesla")
        assert "least expect" in spec
        assert "even when it is not the biggest story" in spec

    def test_requires_stakes_in_the_same_breath(self):
        from engine.intros import build_cold_open_spec
        assert "STAKES" in build_cold_open_spec("tesla")

    def test_bans_opening_on_a_question(self):
        from engine.intros import build_cold_open_spec
        assert "Never open on a question" in build_cold_open_spec("tesla")
