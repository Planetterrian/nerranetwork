"""Guards from the Oct 28-30 slate review (docs/reviews/slate_review_2026_10_30.md)."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# AI Chips Ep037: one read timeout on a fresh enclosure failed a finished run
# ---------------------------------------------------------------------------

_FEED = ('<rss><channel><item><title>e</title>'
         '<pubDate>Wed, 28 Oct 2026 09:00:00 +0000</pubDate>'
         '<enclosure url="https://audio.example.com/ep037.mp3" type="audio/mpeg" length="1"/>'
         '</item></channel></rss>')


def _fake_requests(monkeypatch, answers):
    """`answers` is a list consumed per HEAD call: an int status or an Exception."""
    calls = []

    class _Resp:
        def __init__(self, code):
            self.status_code = code

    def head(url, **kw):
        calls.append(kw.get("timeout"))
        a = answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return _Resp(a)

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(head=head))
    return calls


@pytest.fixture
def feed(tmp_path):
    p = tmp_path / "podcast.rss"
    p.write_text(_FEED, encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    import engine.post_run_validation as prv
    import engine.http_download as hd
    monkeypatch.setattr(prv, "_sleep", lambda s: None)
    monkeypatch.setattr(hd, "_sleep", lambda s: None)


class TestFreshEnclosureIsAskedAgain:
    def test_a_read_timeout_then_200_passes(self, monkeypatch, feed):
        import engine.post_run_validation as prv
        calls = _fake_requests(monkeypatch, [TimeoutError("Read timed out"), 200])
        assert prv.validate_enclosure_reachability(feed, sample_count=1)
        assert calls == [8, 20]  # the second attempt waits longer

    def test_a_5xx_is_asked_again(self, monkeypatch, feed):
        import engine.post_run_validation as prv
        _fake_requests(monkeypatch, [503, 200])
        assert prv.validate_enclosure_reachability(feed, sample_count=1)

    def test_a_404_fails_at_once(self, monkeypatch, feed):
        import engine.post_run_validation as prv
        calls = _fake_requests(monkeypatch, [404])
        assert not prv.validate_enclosure_reachability(feed, sample_count=1)
        assert len(calls) == 1

    def test_still_failing_after_every_attempt_fails(self, monkeypatch, feed):
        import engine.post_run_validation as prv
        n = len(prv.ENCLOSURE_ATTEMPT_TIMEOUTS)
        _fake_requests(monkeypatch, [TimeoutError("x")] * n)
        assert not prv.validate_enclosure_reachability(feed, sample_count=1)


# ---------------------------------------------------------------------------
# Nerra Daily Ep069: 81 silent minutes in a read-timeout-only download
# ---------------------------------------------------------------------------

class _HTTPError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = types.SimpleNamespace(status_code=code)


def _fake_get(monkeypatch, plans):
    """Each plan: ('ok', [chunks]) | ('status', code) | ('raise', exc) | ('slow', n)."""
    import engine.http_download as hd

    def get(url, stream=True, timeout=None):
        assert timeout == (hd.CONNECT_TIMEOUT_S, hd.READ_TIMEOUT_S)
        kind, arg = plans.pop(0)

        class _Ctx:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def raise_for_status(self):
                if kind == "status":
                    raise _HTTPError(arg)

            def iter_content(self, size):
                if kind == "raise":
                    raise arg
                if kind == "slow":
                    for _ in range(arg):
                        yield b"x"
                    return
                yield from arg

        return _Ctx()

    monkeypatch.setitem(sys.modules, "requests",
                        types.SimpleNamespace(get=get, HTTPError=_HTTPError))


class TestEditionDownloadsAreBounded:
    def test_downloads_and_reports_size(self, monkeypatch, tmp_path):
        from engine.http_download import download_to
        _fake_get(monkeypatch, [("ok", [b"ab", b"cd"])])
        dest = tmp_path / "seg.mp3"
        assert download_to("https://x/a.mp3", dest) == 4
        assert dest.read_bytes() == b"abcd"
        assert not (tmp_path / "seg.mp3.part").exists()

    def test_a_trickle_is_abandoned_and_retried(self, monkeypatch, tmp_path):
        import engine.http_download as hd
        ticks = iter(range(0, 100000, 100))  # every clock read = +100 s
        monkeypatch.setattr(hd, "_clock", lambda: next(ticks))
        _fake_get(monkeypatch, [("slow", 50), ("ok", [b"done"])])
        dest = tmp_path / "seg.mp3"
        assert hd.download_to("https://x/a.mp3", dest, deadline_s=250) == 4

    def test_a_404_is_not_retried(self, monkeypatch, tmp_path):
        from engine.http_download import download_to
        _fake_get(monkeypatch, [("status", 404)])
        with pytest.raises(_HTTPError):
            download_to("https://x/a.mp3", tmp_path / "seg.mp3")

    def test_every_attempt_failing_raises(self, monkeypatch, tmp_path):
        import engine.http_download as hd
        _fake_get(monkeypatch, [("raise", ConnectionError("reset"))] * hd.ATTEMPTS)
        with pytest.raises(ConnectionError):
            hd.download_to("https://x/a.mp3", tmp_path / "seg.mp3")

    def test_both_builders_use_it_and_bound_ffmpeg(self):
        for rel in ("scripts/build_daily_edition.py", "scripts/build_personal_feeds.py"):
            src = (ROOT / rel).read_text(encoding="utf-8")
            assert "download_to(" in src, rel
            assert "stream=True, timeout=600" not in src, rel
            run = src[src.index("def _run("):]
            run = run[:run.index("\n\n\n")] if "\n\n\n" in run else run
            assert "timeout=" in run, f"{rel}: _run has no subprocess timeout"


# ---------------------------------------------------------------------------
# Google News links lost their query values (news.amp?news_id, story?id)
# ---------------------------------------------------------------------------

class TestGoogleNewsQueryValues:
    def _body(self, url_escaped):
        import json
        inner = f'["garturlres","{url_escaped}",1]'
        outer = json.dumps([["wrb.fr", "Fbv4je", inner, None, None, None, "generic"]])
        return ")]}'\n\n" + str(len(outer)) + "\n" + outer + '\n25\n[["e",4,null,null,123]]'

    def test_an_escaped_equals_sign_keeps_its_value(self):
        from engine.url_utils import _garturlres_url
        body = self._body("https://news.sbs.co.kr/amp/news.amp?news_id\\u003dN1007912345"
                          "\\u0026plink\\u003dORI")
        assert _garturlres_url(body) == \
            "https://news.sbs.co.kr/amp/news.amp?news_id=N1007912345&plink=ORI"

    def test_a_plain_url_and_a_glued_reply(self):
        from engine.url_utils import _garturlres_url
        body = self._body("https://abcnews.com/Business/story?id\\u003d1234")
        assert _garturlres_url(body).endswith("story?id=1234")
        assert _garturlres_url(body.replace("\n", "")).endswith("story?id=1234")
        assert _garturlres_url(")]}'\n[]") is None

    def test_the_old_backslash_regex_is_gone(self):
        src = (ROOT / "engine" / "url_utils.py").read_text(encoding="utf-8")
        assert '(https?://[^\\\\"]+)' not in src


# ---------------------------------------------------------------------------
# Claims: an unreadable body is unreachable; a duplicate never flags a
# verified claim
# ---------------------------------------------------------------------------

class TestClaimsLabels:
    def test_a_pdf_is_unreachable_not_not_found(self):
        from engine import claims
        claim = {"id": "c1", "claim": "A finding.", "source_url": "https://x.org/r.pdf",
                 "supporting_quote": "a finding in the report"}
        res = claims.verify_claim_sources([claim], fetch=lambda u: (200, ""))
        assert res[0]["unreachable"] is True
        assert claims.status_for_verification(res[0]) == claims.CLAIM_STATUS_UNREACHABLE

    def test_a_404_stays_not_found(self):
        from engine import claims
        claim = {"id": "c1", "claim": "A finding.", "source_url": "https://x.org/r",
                 "supporting_quote": "q"}
        res = claims.verify_claim_sources([claim], fetch=lambda u: (404, ""))
        assert claims.status_for_verification(res[0]) == claims.CLAIM_STATUS_NOT_FOUND

    def test_flag_mode_drops_an_unverified_duplicate_of_a_verified_claim(self):
        src = (ROOT / "engine" / "claims.py").read_text(encoding="utf-8")
        assert "verified_keys" in src and "dropped_ids" in src


# ---------------------------------------------------------------------------
# Lints and filters
# ---------------------------------------------------------------------------

class TestPeptidesCard:
    def test_plain_labels_count(self):
        from engine.digest_lint import spotlight_card_missing
        d = ("### Peptide Spotlight\nWhat it is: x\nHumans given it: y\n"
             "Regulatory status: z\nRisks: r\nWhat it does not show: n\n")
        assert spotlight_card_missing(d) == []
        assert spotlight_card_missing(d.replace("Risks: r\n", "")) == ["Risks"]
        bold = d.replace("What it is:", "**What it is:**")
        assert spotlight_card_missing(bold) == []

    def test_a_label_inside_a_sentence_is_not_a_slot(self):
        from engine.digest_lint import spotlight_card_missing
        d = "### Peptide Spotlight\nThe risks are unclear, and what it is remains open.\n"
        assert "Risks" in spotlight_card_missing(d)


class TestSpokenInstructions:
    @pytest.mark.parametrize("line", [
        "Say implied probability once and leave it there: each of those figures is a price.",
        "The brief record does not give a single lake-by-lake ledger of that shift.",
        "Then the case on both sides, if the day gives one.",
    ])
    def test_aired_lines_are_self_narration(self, line):
        from engine.absence_sentences import is_self_narration_sentence
        assert is_self_narration_sentence(line)

    @pytest.mark.parametrize("line", [
        "Say it once more.", "We'll leave it there for today.",
        "Say today's words out loud even once.", "The brief was filed on Monday.",
    ])
    def test_ordinary_lines_are_not(self, line):
        from engine.absence_sentences import is_self_narration_sentence
        assert not is_self_narration_sentence(line)


# ---------------------------------------------------------------------------
# Prediction Markets: the Friday Week's Board
# ---------------------------------------------------------------------------

def _board_digest(rows):
    return "### The Board\n" + "\n".join(rows) + "\n\n### New and Notable\nx\n"


class TestWeeksBoard:
    def _write(self, tmp_path, days):
        import datetime as dt
        for i, (date, rows) in enumerate(days):
            name = f"Prediction_Markets_Ep{30 + i:03d}_{date:%Y%m%d}.md"
            (tmp_path / name).write_text(_board_digest(rows), encoding="utf-8")
        return dt

    def test_that_date_is_the_yes_outcome(self, tmp_path):
        import datetime as dt
        from engine.board_week import week_board_block
        self._write(tmp_path, [
            (dt.date(2026, 10, 25), ["Does the US-Iran ceasefire continue through October 31 — Yes "
                                     "at an 82.5 percent implied probability, Polymarket."]),
            (dt.date(2026, 10, 29), ["US-Iran ceasefire continues through October 31 — that date "
                                     "at a 96.7 percent implied probability, Polymarket."]),
        ])
        block = week_board_block(tmp_path, dt.date(2026, 10, 30))
        assert "82.5% on Sunday → 96.7% on Thursday" in block

    def test_a_new_leader_is_reported(self, tmp_path):
        import datetime as dt
        from engine.board_week import week_board_block
        self._write(tmp_path, [
            (dt.date(2026, 10, 26), ["Prime minister of Israel after the next election — Gadi "
                                     "Eizenkot at a 56.6 percent implied probability, Polymarket."]),
            (dt.date(2026, 10, 28), ["Prime minister of Israel after the next election — Benjamin "
                                     "Netanyahu at a 44.5 percent implied probability, Polymarket."]),
        ])
        block = week_board_block(tmp_path, dt.date(2026, 10, 30))
        assert "Benjamin Netanyahu" in block and "different outcome" in block

    def test_a_trailing_article_is_not_part_of_the_outcome(self):
        from engine.board_week import _question_and_outcome
        assert _question_and_outcome("2026 midterms — Democrats sweep, a")[1] == "Democrats sweep"


# ---------------------------------------------------------------------------
# Nerra Daily: spelled dates in the opener memory; handoffs that echo the hook
# ---------------------------------------------------------------------------

class TestEditionMemoryAndHandoffs:
    @pytest.mark.parametrize("line,expected", [
        ("October thirtieth, twenty twenty-six finds Nerra Daily", "[date] finds Nerra Daily"),
        ("October twenty-eighth, twenty twenty-six. Nerra Daily opens", "[date]. Nerra Daily opens"),
        ("Friday, October 30, 2026, opens Nerra Daily", "[date] opens Nerra Daily"),
        ("The first segment begins with SpaceX", "The first segment begins with SpaceX"),
    ])
    def test_spelled_dates_collapse(self, line, expected):
        from engine.daily_edition import normalize_date_tokens
        assert normalize_date_tokens(line) == expected

    def _segs(self, hooks):
        from engine.daily_edition import Segment
        out = []
        for name, hook in hooks:
            s = Segment.__new__(Segment)
            s.show_name, s.hook = name, hook
            out.append(s)
        return out

    def test_an_echo_is_sent_back(self):
        from engine.daily_edition import handoff_revision_prompt, handoffs_echoing_hook
        segs = self._segs([("SpaceX Daily", "x"),
                           ("MAG 7 Daily", "Two senators set a November 25 deadline for Meta "
                                           "to account for glasses footage.")])
        links = {"handoffs": ["Letters from two senators set a November 25 deadline for Meta "
                              "to explain footage from its glasses; MAG 7 Daily opens there."]}
        assert handoffs_echoing_hook(links, segs) == [1]
        prompt = handoff_revision_prompt("BASE", links, segs)
        assert prompt and "restate the headline" in prompt and "at the end" not in prompt

    def test_a_different_angle_is_left_alone(self):
        from engine.daily_edition import handoff_revision_prompt
        segs = self._segs([("SpaceX Daily", "x"),
                           ("MAG 7 Daily", "Two senators set a November 25 deadline for Meta "
                                           "to account for glasses footage.")])
        links = {"handoffs": ["Who sees what a camera on your face records? That question "
                              "reaches Congress on MAG 7 Daily."]}
        assert handoff_revision_prompt("BASE", links, segs) is None

    def test_the_links_prompt_no_longer_asks_for_the_name_at_the_end(self):
        src = (ROOT / "shows" / "prompts" / "nerra_daily_links.txt").read_text(encoding="utf-8")
        assert "mid-sentence or at the end" not in src


class TestPromptLengthAndSections:
    def test_uc_script_length_follows_its_brief(self):
        src = (ROOT / "shows" / "prompts" / "unintended_consequences_podcast.txt").read_text(
            encoding="utf-8")
        assert "The brief sets the length" in src

    def test_tesla_names_also_today_in_its_required_sections(self):
        src = (ROOT / "shows" / "prompts" / "tesla_digest.txt").read_text(encoding="utf-8")
        head = src[:src.index("[END PRODUCTION NOTES]")]
        assert "### Also Today" in head
