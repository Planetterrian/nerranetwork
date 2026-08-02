"""Guards for two Ep054 failures: a wasted regen and a blocked send.

**Repetition.** The digest bigram bar was 4, and measured across the
last 30 committed digests on six shows it fired on 17 of 180 (20% on
SpaceX) with EVERY flagged phrase a false positive — domain nouns
("upper stage", "static fire", "flight 13") or bare function phrases
("the first", "the same", "whether the"). Ep054 burned a full
lower-temperature regeneration and then logged "did not improve —
keeping original". The detector must still catch a genuine loop.

**Buttondown tag.** ``Could not resolve Buttondown tag id(s) for
['SpaceX Daily']`` blocked the send (correctly refusing to blast the
whole list unfiltered), but told the operator only to "verify the name
matches" — without showing what names exist.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402

from engine.generator import _validate_llm_output  # noqa: E402


# Varied filler to clear the 50-word floor the scanners require WITHOUT
# introducing repetition of its own (an earlier version of this helper
# repeated one sentence and tripped the detector it was meant to test).
_FILLER = (
    "Starbase crews rolled a booster to the pad before dawn. Weather "
    "officers gave a favourable forecast for Tuesday. Range control "
    "cleared a corridor over the Gulf. Investors watched premarket "
    "quotes drift sideways. A supplier confirmed new tooling arrived "
    "in Florida. Regulators published an updated environmental review. "
)


def _digest(body: str) -> str:
    return _FILLER + body


_SUBJECTS = ["Analysts", "Engineers", "Regulators", "Investors", "Crews",
             "Suppliers", "Controllers", "Auditors", "Planners", "Managers",
             "Inspectors", "Technicians"]
_VERBS = ["described", "flagged", "measured", "questioned", "welcomed",
          "audited", "compared", "documented", "revisited", "praised",
          "disputed", "modelled"]
_NOUNS = ["telemetry", "margins", "cadence", "tooling", "propellant",
          "avionics", "schedule", "throughput", "hardware", "staffing",
          "insulation", "guidance"]
_TAILS = ["ahead of the review", "in the quarterly filing",
          "during a campaign", "at the Cape", "before a window",
          "under a new contract", "across two pads", "for the manifest",
          "in a briefing", "on a call", "after a delay",
          "with fresh capacity"]


def _phrase_in_varied_sentences(phrase: str, times: int) -> str:
    """Repeat *phrase* with EVERY neighbouring word varying.

    This is how a phrase recurs in a real digest: the phrase returns,
    the sentences around it do not. Holding any neighbour fixed would
    manufacture a second repeated n-gram and test the harness rather
    than the detector — and repeating a whole sentence would build an
    actual hallucination loop, which the detector is supposed to catch.
    """
    return _digest(" ".join(
        f"{_SUBJECTS[i % len(_SUBJECTS)]} {_VERBS[i % len(_VERBS)]} "
        f"{phrase} {_NOUNS[i % len(_NOUNS)]} {_TAILS[i % len(_TAILS)]}."
        for i in range(times)
    ))


class TestFunctionPhrasesNoLongerFire:
    """A determiner plus one word carries no information."""

    @pytest.mark.parametrize("phrase", [
        "the first", "the same", "the work", "the open", "whether the",
        "the upper", "the ship",
    ])
    def test_bare_function_bigrams_are_ignored(self, phrase):
        text = _phrase_in_varied_sentences(phrase, 12)
        assert _validate_llm_output(text, "digest", "spacex", 0, ()) == 0


class TestDomainVocabularyIsNotHallucination:
    # The bar that matters is the RETRY trigger (_rep_count >= 3), not
    # whether a phrase is noted at all. One domain noun recurring is
    # allowed to be logged; what must not happen is burning a
    # regeneration over it, which is what Ep054 did.
    RETRY_AT = 3

    def test_technical_noun_phrase_does_not_trigger_a_regen(self):
        """'upper stage' ×5 in a digest about the upper stage is the
        subject matter — this is the exact Ep054 flag."""
        text = _phrase_in_varied_sentences("upper stage", 5)
        assert _validate_llm_output(
            text, "digest", "spacex", 0, ()) < self.RETRY_AT

    def test_static_fire_and_flight_number(self):
        for phrase in ("static fire", "flight 13"):
            assert _validate_llm_output(
                _phrase_in_varied_sentences(phrase, 5),
                "digest", "spacex", 0, ()) < self.RETRY_AT

    def test_memory_block_framing_is_exempt(self):
        """"open questions" is a heading engine.show_memory hands the
        prompt per tracked program — SpaceX Ep029/Ep035 regenerated on
        it alone."""
        for phrase in ("open question", "open questions",
                       "whose open questions"):
            assert _validate_llm_output(
                _phrase_in_varied_sentences(phrase, 6),
                "digest", "spacex", 0, ()) < self.RETRY_AT


class TestRealLoopsStillCaught:
    def test_repeated_clause_is_flagged(self):
        loop = (
            "The rocket achieved orbital velocity today. " * 3
            + "Engineers confirmed the anomaly was contained within the "
              "vehicle. " * 9
            + "More detail followed from the flight director. "
        ) * 3
        assert _validate_llm_output(loop, "digest", "spacex", 0, ()) >= 3

    def test_content_bigram_above_the_new_bar_still_fires(self):
        """Two content words recurring far past the bar, in otherwise
        varied prose — the shape a real fixation takes."""
        text = _phrase_in_varied_sentences("quantum entanglement", 9)
        assert _validate_llm_output(text, "digest", "spacex", 0, ()) >= 1

    def test_sensitivity_was_not_bought_by_raising_the_threshold(self):
        """The count threshold is deliberately UNCHANGED — a blunt raise
        also blunts real tics (it broke
        test_known_entities_do_not_mask_unrelated_repetition, which
        catches a clause tic at 5 repeats). The fix is the content-word
        floor, which discriminates instead."""
        src = (PROJECT_ROOT / "engine" / "generator.py").read_text(
            encoding="utf-8")
        assert '_rep_threshold = 5 if stage == "podcast_script" else 4' in src
        assert "if sum(1 for t in tokens if t not in _STOPWORDS) < 2:" in src

    def test_clause_level_tic_at_five_repeats_still_fires(self):
        """Pins the behaviour the threshold raise would have lost."""
        filler = " ".join(f"unique{i} token{i} filler{i}" for i in range(30))
        text = filler + " " + (
            "The kicker is nobody expected the kicker is real. " * 5)
        assert _validate_llm_output(text, "digest", "tesla", 0,
                                    ("tesla", "model y")) >= 1


class TestNoNetworkRegressionOnCommittedDigests:
    def test_recent_digests_do_not_trigger_regeneration(self):
        """The measurement that justified the change, pinned."""
        import glob
        from engine.config import load_config
        fired = 0
        checked = 0
        for slug, pat in (
            ("spacex", "digests/spacex/*.md"),
            ("tesla", "digests/tesla_shorts_time/*.md"),
            ("fascinating_frontiers", "digests/fascinating_frontiers/*.md"),
        ):
            try:
                cfg = load_config(f"shows/{slug}.yaml")
            except Exception:
                continue
            kw = tuple(getattr(cfg, "keywords", []) or ())
            for path in sorted(glob.glob(pat))[-20:]:
                text = Path(path).read_text(encoding="utf-8")
                try:
                    n = _validate_llm_output(text, "digest", slug, 0, kw)
                except Exception:
                    continue
                checked += 1
                if n >= 3:
                    fired += 1
        if checked < 10:
            pytest.skip("not enough committed digests in this checkout")
        # Was 13/90 on these three shows before the fix.
        assert fired == 0, f"{fired}/{checked} digests would still regenerate"


class TestButtondownTagDiagnostics:
    def test_fold_normalises_case_and_whitespace(self):
        from engine.newsletter import _fold_tag
        assert _fold_tag("  SpaceX   Daily ") == _fold_tag("spacex daily")

    def test_tolerant_match_recovers_a_case_typo(self, monkeypatch):
        import engine.newsletter as nl
        monkeypatch.setattr(nl, "_TAG_ID_CACHE", {"SpaceX Daily": "tag_1"})
        monkeypatch.setattr(nl, "_ALL_TAG_NAMES", ["SpaceX Daily"])
        got = nl._resolve_tag_ids(["Spacex daily "], api_key="k")
        assert got == {"Spacex daily ": "tag_1"}

    def test_exact_match_is_unchanged(self, monkeypatch):
        import engine.newsletter as nl
        monkeypatch.setattr(nl, "_TAG_ID_CACHE", {"SpaceX Daily": "tag_1"})
        monkeypatch.setattr(nl, "_ALL_TAG_NAMES", ["SpaceX Daily"])
        assert nl._resolve_tag_ids(["SpaceX Daily"], api_key="k") == {
            "SpaceX Daily": "tag_1"}

    def test_genuinely_absent_tag_still_misses(self, monkeypatch):
        """Tolerance must not invent a match — refusing to send is right
        when the tag does not exist."""
        import engine.newsletter as nl
        monkeypatch.setattr(nl, "_TAG_ID_CACHE", {"Tesla Shorts Time": "t1"})
        monkeypatch.setattr(nl, "_ALL_TAG_NAMES", ["Tesla Shorts Time"])
        assert nl._resolve_tag_ids(["SpaceX Daily"], api_key="k") == {}

    def test_error_names_the_available_tags(self):
        src = (PROJECT_ROOT / "engine" / "newsletter.py").read_text(
            encoding="utf-8")
        assert "The account has %d tag(s)" in src
        assert "_ALL_TAG_NAMES" in src


class TestTagIdPassthrough:
    """A show may pin the immutable id instead of the display name.

    Buttondown's Tags page is hand-edited: SpaceX Daily and First
    Principles Daily both failed every send until their tags were
    created (2026-08-02), and a later rename would fail the same silent
    way. Both are pinned to ids now.
    """

    def test_recognises_both_observed_id_shapes(self):
        from engine.newsletter import looks_like_tag_id
        assert looks_like_tag_id("sub_tag_75a48w4wsm9fhr6n2eckfysexs")
        assert looks_like_tag_id("tag_abc123")

    def test_display_names_are_not_mistaken_for_ids(self):
        from engine.newsletter import looks_like_tag_id
        for name in ("SpaceX Daily", "Tesla Shorts Time", "DP Pod", ""):
            assert not looks_like_tag_id(name)

    def test_pinned_id_resolves_without_any_api_lookup(self, monkeypatch):
        """An id must not depend on the Tags endpoint being reachable."""
        import engine.newsletter as nl
        monkeypatch.setattr(nl, "_TAG_ID_CACHE", {})
        monkeypatch.setattr(nl, "_ALL_TAG_NAMES", [])

        def _no_calls(*a, **k):
            raise AssertionError("Tags endpoint must not be called")

        monkeypatch.setattr(nl.requests, "get", _no_calls)
        got = nl._resolve_tag_ids(["sub_tag_75a48w4wsm9fhr6n2eckfysexs"],
                                  api_key="k")
        assert got == {"sub_tag_75a48w4wsm9fhr6n2eckfysexs":
                       "sub_tag_75a48w4wsm9fhr6n2eckfysexs"}

    def test_ids_and_names_resolve_together(self, monkeypatch):
        import engine.newsletter as nl
        monkeypatch.setattr(nl, "_TAG_ID_CACHE", {"Tesla Shorts Time": "t1"})
        monkeypatch.setattr(nl, "_ALL_TAG_NAMES", ["Tesla Shorts Time"])
        got = nl._resolve_tag_ids(
            ["Tesla Shorts Time", "sub_tag_abc"], api_key="k")
        assert got == {"Tesla Shorts Time": "t1", "sub_tag_abc": "sub_tag_abc"}

    def test_the_two_repaired_shows_pin_an_id_in_tag_id(self):
        """The id lives in ``tag_id``, NOT ``tag`` — see
        TestTagIdIsSeparateFromDisplayName for why that distinction is
        load-bearing."""
        import logging
        logging.disable(logging.CRITICAL)
        try:
            from engine.config import load_config
            from engine.newsletter import looks_like_tag_id
            for slug in ("spacex", "first_principles"):
                cfg = load_config(f"shows/{slug}.yaml")
                tag_id = (getattr(cfg.newsletter, "tag_id", "") or "").strip()
                assert looks_like_tag_id(tag_id), (
                    f"{slug} tag_id is not an id: {tag_id!r}")
        finally:
            logging.disable(logging.NOTSET)

    def test_other_shows_still_use_readable_names(self):
        """Names stay where they work — ids are for the surfaces that
        actually broke, not a blanket rewrite."""
        import logging
        logging.disable(logging.CRITICAL)
        try:
            from engine.config import load_config
            from engine.newsletter import looks_like_tag_id
            cfg = load_config("shows/tesla.yaml")
            assert not looks_like_tag_id(cfg.newsletter.tag)
        finally:
            logging.disable(logging.NOTSET)


class TestTagIdIsSeparateFromDisplayName:
    """``tag`` is ALSO the subscribe-form checkbox value.

    Pinning identifiers into ``newsletter.tag`` (one commit on
    2026-08-02) meant the next site regeneration would have written
    ``value="sub_tag_75a4…"`` into every show page, blog post and the
    network page's signup form. Subscribers carry tag NAMES, so those
    signups would have been tagged with a literal identifier string
    matching nothing — and would silently never receive the newsletter.
    Caught by a dirty working tree before the nightly regen shipped it.
    """

    def _cfg(self, slug):
        import logging
        logging.disable(logging.CRITICAL)
        try:
            from engine.config import load_config
            return load_config(f"shows/{slug}.yaml")
        finally:
            logging.disable(logging.NOTSET)

    def test_pinned_shows_keep_a_readable_display_name(self):
        from engine.newsletter import looks_like_tag_id
        for slug, name in (("spacex", "SpaceX Daily"),
                           ("first_principles", "First Principles Daily")):
            tag = self._cfg(slug).newsletter.tag
            assert tag == name
            assert not looks_like_tag_id(tag), (
                f"{slug}: an id in `tag` reaches the subscribe form")

    def test_pinned_shows_carry_the_id_in_tag_id(self):
        from engine.newsletter import looks_like_tag_id
        for slug in ("spacex", "first_principles"):
            assert looks_like_tag_id(self._cfg(slug).newsletter.tag_id)

    def test_tag_id_is_declared_on_the_dataclass(self):
        """Landmine: _build_nested drops YAML keys the dataclass does
        not declare, so an undeclared tag_id would silently be lost."""
        from engine.config import NewsletterConfig
        assert hasattr(NewsletterConfig(), "tag_id")
        assert self._cfg("spacex").newsletter.tag_id

    def test_send_prefers_the_id_over_the_name(self):
        src = (PROJECT_ROOT / "engine" / "newsletter.py").read_text(
            encoding="utf-8")
        assert 'getattr(newsletter, "tag_id", "")' in src

    def test_page_generation_reads_the_display_name(self):
        """The site helper reads newsletter.tag — with the id split out,
        the form value is a name again."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_gh", PROJECT_ROOT / "generate_html.py")
        src = (PROJECT_ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert '(data.get("newsletter") or {}).get("tag")' in src
        assert "tag_id" not in src.split("_newsletter_tag_for_slug")[1][:900]


class TestCaptureTagAbsenceIsNotAnError:
    """``ru-spacex`` does not exist because the RU lander has not
    converted anyone yet — Buttondown creates a capture tag with the
    first signup (that is how ``gallery-subscriber`` appeared). Failing
    the weekly workflow red every week for that is noise."""

    @staticmethod
    def _account(monkeypatch, names, fail=False):
        """Stub the Tags endpoint with a real account shape."""
        import engine.newsletter as nl
        monkeypatch.setattr(nl, "_TAG_ID_CACHE", {})
        monkeypatch.setattr(nl, "_ALL_TAG_NAMES", [])

        class _Resp:
            def raise_for_status(self):
                if fail:
                    raise RuntimeError("401 Unauthorized")

            def json(self):
                return {"results": [{"name": n, "id": f"sub_tag_{i}"}
                                    for i, n in enumerate(names)],
                        "next": None}

        monkeypatch.setattr(nl.requests, "get", lambda *a, **k: _Resp())
        return nl

    def test_absent_tag_reports_false_when_the_account_was_read(
            self, monkeypatch):
        nl = self._account(monkeypatch, ["SpaceX Daily", "gallery-subscriber"])
        assert nl.tag_exists("ru-spacex", "k") is False

    def test_unreachable_account_reports_none_not_false(self, monkeypatch):
        """An API outage must not be read as 'no subscribers yet'."""
        nl = self._account(monkeypatch, [], fail=True)
        assert nl.tag_exists("ru-spacex", "k") is None

    def test_present_tag_reports_true(self, monkeypatch):
        nl = self._account(monkeypatch, ["ru-spacex", "SpaceX Daily"])
        assert nl.tag_exists("ru-spacex", "k") is True

    def test_weekly_script_exits_zero_on_absence(self):
        src = (PROJECT_ROOT / "scripts" / "send_ru_spacex_weekly.py").read_text(
            encoding="utf-8")
        assert "present = tag_exists(CAPTURE_TAG, api_key)" in src
        assert "if present is False:" in src
