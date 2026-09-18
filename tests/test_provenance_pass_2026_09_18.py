"""Sep 18 2026 — two things the first combined-generation slate showed.

1. **The combined script was discarded with no regeneration behind it.**
   Tesla Ep609, SpaceX Ep104 and Planetterrian Ep187 all recorded
   ``combined_stale`` at ~50 % line survival, and paid for the script
   twice. The stash test compared raw LINES, and run_show rewrites the
   tail of every item line after generation (``Source: <url>`` becomes
   ``Source: [domain](url)``, the Google-News resolver swaps the url),
   so every item line "changed". The comparison now runs on normalised
   SENTENCES with links, URLs and Source tails removed.

2. **Strip mode removed five TRUE sentences from SpaceX Ep104.** All
   five sources resolved and each page carried the fact (WESH's own
   headline was the Shotwell claim); the model's supporting quotes were
   paraphrases, so the 0.9 verbatim check failed, and the repair pass
   asked for a DIFFERENT url — a truthful model omitted every claim, and
   the committed sidecar then read "claims=0, passed". The repair now
   hands the model the fetched page's relevant passage and lets it
   re-quote VERBATIM from the same source (the mechanical check is
   untouched; an unrelated verbatim sentence is rejected), and the
   sidecar records what the gate saw before the strip.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine import claims as cl
from engine import generator as gen

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# 1. The stash survives what run_show does to a digest
# ---------------------------------------------------------------------------

STASH = """# SpaceX Daily

> **NASA plans to keep Starliner in service longer and shift Dragon's retirement target to 2030.**

### Top News

1. **NASA plans more Starliner flights while Dragon retirement moves to 2030**
 NASA intends to fly additional Starliner missions before retiring the vehicle. The shift follows internal planning documents reviewed this week. Reports indicate the agency wants at least two more Starliner flights to maintain independent crew access. Source: https://news.google.com/rss/articles/CBMiAAAA

2. **Starship Flight 14 slips again as Starbase processing continues**
 The company postponed the next integrated flight test without a new target date. Teams continue work on the Ship and Super Heavy booster stack at Starbase. Regulatory review remains a factor in the schedule. Source: https://www.advanced-television.com/2026/09/18/spacex-delays-starship-14-again/

3. **Gwynne Shotwell tells Boeing to complete Starliner flights**
 The comment came during a public appearance on September 18. SpaceX president Gwynne Shotwell stated that Boeing has received payment and should now fly the vehicle. Shotwell noted the importance of multiple U.S. crew vehicles. Source: https://www.wesh.com/article/gwynne-shotwell-boeing-starliner-comments/73781551

### Community Buzz

4. **Crew-12 astronauts look forward to seeing nature again**
 The four crew members expressed anticipation for seeing nature again after months on the station. NASA confirmed the upcoming undocking and splashdown sequence. Source: https://www.space.com/crew-12-home
"""


def _run_show_view(text: str) -> str:
    """What run_show holds by the time the script stage runs: Source tails
    rewritten to ``[domain](url)`` with the Google-News url resolved, one
    claim-stripped sentence, one cross-section duplicate dropped."""
    text = text.replace(
        "Source: https://news.google.com/rss/articles/CBMiAAAA",
        "Source: [keeptrack.space](https://keeptrack.space/x-report/spacex-brief-2026-09-18)")
    text = text.replace(
        "Source: https://www.advanced-television.com/2026/09/18/spacex-delays-starship-14-again/",
        "Source: [advanced-television.com](https://www.advanced-television.com/2026/09/18/spacex-delays-starship-14-again/)")
    text = text.replace(
        "Source: https://www.wesh.com/article/gwynne-shotwell-boeing-starliner-comments/73781551",
        "Source: [wesh.com](https://www.wesh.com/article/gwynne-shotwell-boeing-starliner-comments/73781551)")
    text = text.replace(
        " SpaceX president Gwynne Shotwell stated that Boeing has received payment and should now fly the vehicle.", "")
    head, _, _ = text.partition("### Community Buzz")
    return head.rstrip() + "\n"


class TestStashSurvivesRunShowTrims:
    def test_link_rewrite_strip_and_dedupe_keep_the_script(self):
        current = _run_show_view(STASH)
        fwd, back = gen.combined_digest_line_shares(STASH, current)
        assert back >= 0.9, (fwd, back)
        assert gen.combined_script_matches_digest(STASH, current)

    def test_the_old_line_test_would_have_discarded_it(self):
        """The failure shape, pinned: on raw lines every item line differs."""
        current = _run_show_view(STASH)
        stash_lines = {ln.strip().lower() for ln in STASH.splitlines() if len(ln.strip()) >= 40}
        cur_lines = [ln.strip().lower() for ln in current.splitlines() if len(ln.strip()) >= 40]
        back_lines = sum(1 for ln in cur_lines if ln in stash_lines) / len(cur_lines)
        assert back_lines < 0.6

    def test_a_regeneration_still_fails(self):
        other = STASH.replace("Starliner", "Falcon Heavy").replace(
            "NASA intends to fly additional", "The FAA published a new set of")
        other = "\n".join(
            ln if not ln.startswith(" ") else " " + ln.strip()[::-1] for ln in other.splitlines())
        assert not gen.combined_script_matches_digest(STASH, other)
        assert not gen.combined_script_matches_digest("", STASH)
        assert not gen.combined_script_matches_digest(STASH, "")

    def test_units_drop_links_urls_and_source_tails(self):
        units = gen._combined_units(
            "1. **Head**\n Body sentence long enough to count as a unit here. "
            "Source: [wesh.com](https://www.wesh.com/a)\n"
            "Body sentence long enough to count as a unit here. Source: https://x.com/b\n")
        assert units == ["body sentence long enough to count as a unit here"] * 2

    def test_pipeline_logs_sentences(self):
        src = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert "stash's sentences" in src and "combined_digest_line_shares" in src


# ---------------------------------------------------------------------------
# 2. Grounded re-quote from the same resolved source
# ---------------------------------------------------------------------------

PAGE = (
    "<html><body><h1>SpaceX president to Boeing: You got paid — now fly the "
    "thing</h1><p>SpaceX's Shotwell says Boeing should fly Starliner; Crew "
    "Dragon isn't retiring now.</p><p>Advertisement</p><p>Speaking on "
    "September 18, Gwynne Shotwell said Boeing has been paid for Starliner "
    "and should now fly the vehicle. She noted the value of two independent "
    "crew systems.</p><p>Unrelated: the weather in Orlando was warm.</p>"
    "</body></html>"
)
URL = "https://www.wesh.com/article/gwynne-shotwell-boeing-starliner-comments/73781551"
EPISODE = (
    "### Top News\n\n"
    "3. **Gwynne Shotwell tells Boeing to complete Starliner flights**\n"
    " The comment came during a public appearance on September 18. SpaceX "
    "president Gwynne Shotwell stated that Boeing has received payment and "
    "should now fly the vehicle.\n"
)
CLAIM = {
    "id": "c3",
    "claim": "Gwynne Shotwell said Boeing has been paid and should fly Starliner",
    "episode_span": ("SpaceX president Gwynne Shotwell stated that Boeing has "
                     "received payment and should now fly the vehicle."),
    "source_url": URL,
    "source_title": "WESH",
    # A paraphrase — not on the page verbatim.
    "supporting_quote": "Shotwell told Boeing it had been paid and ought to fly Starliner",
    "confidence": "high",
}
VERBATIM = ("Gwynne Shotwell said Boeing has been paid for Starliner and "
            "should now fly the vehicle")


def _fetch(url):
    return (200, PAGE) if url == URL else (404, "")


class TestGroundedRequote:
    def test_paraphrased_quote_fails_but_the_source_resolved(self):
        gate = cl.run_source_integrity_gate(EPISODE, [CLAIM], fetch=_fetch)
        assert not gate.passed
        v = gate.failed_verifications[0]
        assert v["resolved"] and not v["unreachable"]
        assert "not found" in v["reason"]

    def test_excerpt_picks_the_passage_that_discusses_the_claim(self):
        text = cl._html_to_text(PAGE)
        ex = cl.source_excerpt_for_claim(f"{CLAIM['claim']} {CLAIM['episode_span']}", text)
        assert "should now fly the vehicle" in ex
        assert "weather in Orlando" not in ex
        assert cl.source_excerpt_for_claim("nothing here matches", text) == ""
        assert len(cl.source_excerpt_for_claim(CLAIM["claim"], text * 50, max_chars=300)) <= 300

    def test_repair_requotes_verbatim_from_the_same_source(self):
        gate = cl.run_source_integrity_gate(EPISODE, [CLAIM], fetch=_fetch)
        seen = {}

        def generate(prompt):
            seen["prompt"] = prompt
            return json.dumps([dict(CLAIM, supporting_quote=VERBATIM)])

        new_gate, repaired = cl.attempt_claim_repair(
            EPISODE, gate, [CLAIM], generate, fetch=_fetch)
        assert "fetched_passage:" in seen["prompt"]
        assert "should now fly the vehicle" in seen["prompt"]
        assert "same source_url is allowed ONLY" in seen["prompt"]
        assert new_gate.passed, new_gate.summary()
        assert new_gate.claims_verified == 1 and new_gate.repair_recovered == 1
        assert repaired[0]["source_url"] == URL
        assert repaired[0]["episode_span"] == CLAIM["episode_span"]

    def test_an_unrelated_verbatim_sentence_is_rejected(self):
        gate = cl.run_source_integrity_gate(EPISODE, [CLAIM], fetch=_fetch)
        new_gate, _ = cl.attempt_claim_repair(
            EPISODE, gate, [CLAIM],
            lambda p: json.dumps([dict(CLAIM, supporting_quote="the weather in Orlando was warm")]),
            fetch=_fetch)
        assert not new_gate.passed and new_gate.repair_recovered == 0

    def test_a_still_paraphrased_requote_still_fails(self):
        gate = cl.run_source_integrity_gate(EPISODE, [CLAIM], fetch=_fetch)
        new_gate, _ = cl.attempt_claim_repair(
            EPISODE, gate, [CLAIM],
            lambda p: json.dumps([dict(CLAIM, supporting_quote="Shotwell said Boeing got paid and must fly Starliner now")]),
            fetch=_fetch)
        assert not new_gate.passed

    def test_unreachable_sources_get_no_passage(self):
        gate = cl.run_source_integrity_gate(EPISODE, [CLAIM], fetch=lambda u: (403, ""))
        seen = {}

        def generate(prompt):
            seen["prompt"] = prompt
            return "[]"

        cl.attempt_claim_repair(EPISODE, gate, [CLAIM], generate, fetch=lambda u: (403, ""))
        assert "could not be fetched" in seen["prompt"]
        assert "fetched_passage" not in seen["prompt"]

    def test_quote_consistency(self):
        assert cl._quote_consistent_with_claim("Boeing has been paid for Starliner", CLAIM["claim"])
        assert cl._quote_consistent_with_claim("the rate rose to 1.25 percent", "BoJ lifted its rate to 1.25")
        assert not cl._quote_consistent_with_claim("the weather in Orlando was warm", CLAIM["claim"])

    def test_run_show_records_recovered_claims(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'metrics.record(\n                        "source_integrity_repair_recovered"' in src


class TestSidecarRecordsWhyItStripped:
    def test_pre_strip_verdicts_and_quotes_reach_the_report(self):
        gate = cl.run_source_integrity_gate(EPISODE, [CLAIM], fetch=_fetch)
        res = cl.strip_unverified(EPISODE, gate, [CLAIM], fetch=_fetch)
        assert res.removed_sentences == [CLAIM["episode_span"]]
        rep = res.gate.to_report()
        pre = rep["pre_strip"]
        assert pre["failed_verifications"][0]["reason"] == "supporting_quote not found in source"
        assert pre["failed_claims"][0]["supporting_quote"] == CLAIM["supporting_quote"]
        assert pre["failed_claims"][0]["source_url"] == URL
        assert rep["stripped_sentences"] == [CLAIM["episode_span"]]
        assert "repair_recovered" in rep

    def test_an_unstripped_gate_has_no_pre_strip_block(self):
        gate = cl.GateResult()
        assert gate.to_report()["pre_strip"] is None
