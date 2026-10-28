"""Network review, Oct 13 2026 — drift guards.

Review: docs/reviews/network_review_2026_10_13.md. Each class pins one
shipped fix against the evidence that produced it: the Oct 12-13 slate
read through its scripts, transcripts and metrics.
"""
from __future__ import annotations

import glob
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "shows" / "prompts"


# ---------------------------------------------------------------------------
# 1. Sourcing narration is cut in code (engine/absence_sentences.py)
# ---------------------------------------------------------------------------

class TestSourcingNarration:
    NARRATION = [
        "Progress Watch for the day had none.",
        "That approval, the increase, the dirham total, the dollar equivalent and "
        "the three-year window are the facts The National reports on the decision.",
        "The gap Nigeria acknowledged is in tracking those infections, which is the "
        "limit of what Premium Times reports on the point.",
        "What is on the record, then, is a Houthi claim and a denial.",
        "That is not a finding by this show on the underlying case.",
        "Collins, Murkowski, Curtis and Tillis are the four names The Hill attaches "
        "to that opposition.",
        "Since yesterday's spending talk, the new piece is that ceiling, not another "
        "retelling of the race.",
    ]
    PROSE = [
        "The facts on confirmed cases are consistent across reports.",
        "Belgal is twenty-eight, The Guardian reports.",
        "The night shift was not a moral failure. It was arithmetic.",
        "Progress Watch this week is the Lagos metro's first full month of service.",
    ]

    @pytest.mark.parametrize("sentence", NARRATION)
    def test_the_oct_13_shapes_are_narration(self, sentence):
        from engine.absence_sentences import is_absence_sentence
        assert is_absence_sentence(sentence)

    @pytest.mark.parametrize("sentence", PROSE)
    def test_prose_is_untouched(self, sentence):
        from engine.absence_sentences import cut_sourcing_clause, is_absence_sentence
        assert not is_absence_sentence(sentence)
        assert cut_sourcing_clause(sentence) == sentence

    def test_a_sourcing_clause_is_cut_and_the_fact_stays(self):
        from engine.absence_sentences import cut_sourcing_clause
        assert cut_sourcing_clause(
            "Environment Canada is the source for those figures, and the current "
            "reading given is eleven point zero degrees."
        ) == "The current reading given is eleven point zero degrees."
        assert cut_sourcing_clause(
            "What was decided is a temporary halt, not a final ruling on the ads, and "
            "The Guardian is the source for the order, the court and the judge."
        ) == "What was decided is a temporary halt, not a final ruling on the ads."
        # A list inside the clause is not a clause boundary.
        assert cut_sourcing_clause(
            "The New York Times is the source for the pledge, the size claim, and "
            "the Miami campus plan.") == ""
        assert cut_sourcing_clause("NPR is the source for the early start.") == ""

    def test_the_filter_counts_a_cut_and_keeps_the_line(self):
        from engine.absence_sentences import strip_absence_sentences
        text = ("Environment Canada is the source for those figures, and the current "
                "reading given is eleven point zero degrees.\n"
                "Progress Watch for the day had none.\n")
        out, removed = strip_absence_sentences(text)
        assert "The current reading given is eleven point zero degrees." in out
        assert "Progress Watch" not in out
        assert removed == 2

    def test_the_cut_never_leaves_a_fragment_on_any_committed_script(self):
        """Swept the corpus: a remainder is a sentence of five or more
        words that opens on a capital, never a list tail."""
        from engine.absence_sentences import _SENT_SPLIT, cut_sourcing_clause
        files = glob.glob(str(ROOT / "digests" / "*" / "*_tts.txt"))
        if not files:
            pytest.skip("no committed scripts")
        for f in files:
            for line in Path(f).read_text(encoding="utf-8", errors="ignore").split("\n"):
                for s in _SENT_SPLIT.split(line):
                    q = cut_sourcing_clause(s)
                    if q and q != s.strip():
                        assert len(q.split()) >= 5 and q[0].isupper(), (f, s, q)


class TestDoubledPlaceTags:
    def test_the_second_tag_goes(self):
        from engine.absence_sentences import strip_doubled_place_tags, strip_absence_sentences
        text = ("In Pakistan, in Asia, President Zardari put the province under "
                "emergency rule.\nIn Haiti, in the Americas, the electoral body is "
                "preparing a revised calendar.\n")
        out, n = strip_doubled_place_tags(text)
        assert n == 2
        assert out.startswith("In Pakistan, President Zardari")
        assert "In Haiti, the electoral body" in out
        # It rides the opt-in filter on both the digest and the script.
        assert "in Asia," not in strip_absence_sentences(text)[0]

    def test_a_single_place_phrase_is_untouched(self):
        from engine.absence_sentences import strip_doubled_place_tags
        text = "In Pakistan, President Zardari acted. In Asia, markets fell.\n"
        assert strip_doubled_place_tags(text) == (text, 0)

    def test_top_world_prompt_describes_one_place_phrase(self):
        text = (PROMPTS / "omni_view_world_digest.txt").read_text(encoding="utf-8")
        assert "The first sentence names the country and the region." not in text
        assert "one place phrase" in text


# ---------------------------------------------------------------------------
# 2. A hook that re-tells a story covered on 2+ recent days regenerates
# ---------------------------------------------------------------------------

class TestHookRecurrence:
    SRC = (ROOT / "run_show.py").read_text(encoding="utf-8")

    def test_the_gate_is_wired_as_a_structural_defect(self):
        assert "HOOK_RECURRENCE_MIN_DAYS = 2" in self.SRC
        assert '_LintFinding(\n                "hook_recurrence",' in self.SRC
        assert 'metrics.record("hook_recurrence_days"' in self.SRC
        assert "lead with today's NEW development" in self.SRC

    @pytest.mark.skipif(
        not (ROOT / "digests" / "tesla_shorts_time" /
             "Tesla_Shorts_Time_Pod_Ep632_20261012.md").exists(),
        reason="fixture episode pruned")
    def test_tesla_ep632_fires_and_ep633_does_not(self):
        """Replayed on the tracker as it stood before each episode."""
        from engine.digest_lint import hook_line
        from engine.story_recurrence import RecurrenceIndex
        tracker = json.loads((ROOT / "digests" / "tesla_shorts_time" /
                              "tesla_content_tracker.json").read_text(encoding="utf-8"))
        episodes = tracker.get("episodes", [])
        if not any(str(e.get("date", "")) < "2026-10-12" for e in episodes):
            pytest.skip("tracker window has rolled past the fixture")
        def times(stem: str, iso: str) -> int:
            idx = RecurrenceIndex([e for e in episodes if str(e.get("date", "")) < iso],
                                  exclude_date=iso)
            md = (ROOT / "digests" / "tesla_shorts_time" / f"{stem}.md").read_text(encoding="utf-8")
            m = idx.match(hook_line(md) or "")
            return int(m["times"]) if m else 0
        assert times("Tesla_Shorts_Time_Pod_Ep632_20261012", "2026-10-12") >= 2
        assert times("Tesla_Shorts_Time_Pod_Ep633_20261013", "2026-10-13") < 2


# ---------------------------------------------------------------------------
# 3. SpaceX: a fast_info quote equal to its previous close is a bar
# ---------------------------------------------------------------------------

class TestSpaceXPreMarketQuote:
    def test_no_trade_yet(self):
        from shows.hooks.spacex import _no_trade_yet
        assert _no_trade_yet(163.42, 163.42)
        assert not _no_trade_yet(163.42, 162.57)
        assert not _no_trade_yet(163.42, None)

    def test_the_prior_close_comes_from_history_and_says_closed(self, monkeypatch):
        import shows.hooks.spacex as sx
        monkeypatch.setattr(sx, "_quote_from_fast_info", lambda: (163.42, 163.42))
        monkeypatch.setattr(sx, "_quote_from_history", lambda: (163.42, 162.57))
        monkeypatch.setattr(sx, "_validate", lambda p: True)
        monkeypatch.setattr(sx, "_persist", lambda *a, **k: None)
        price, change, source = sx._fetch_spcx_quote()
        assert price == 163.42 and change == "+0.5%" and source == "yfinance_history"
        # A fixed weekday: on a weekend the close is spoken "closed Friday at"
        # (Oct 18 2026), and a wall-clock test would fail every Saturday.
        wed = __import__("datetime").datetime(2026, 10, 14, 7, 30, tzinfo=__import__("datetime").timezone.utc)
        assert "closed at" in sx._price_sentence(price, change, source, now=wed)
        assert "unchanged" not in sx._price_sentence(price, change, source, now=wed)

    def test_a_real_trade_at_the_prior_close_keeps_fast_info(self, monkeypatch):
        import shows.hooks.spacex as sx
        monkeypatch.setattr(sx, "_quote_from_fast_info", lambda: (163.42, 163.42))
        monkeypatch.setattr(sx, "_quote_from_history", lambda: (161.00, 160.00))
        monkeypatch.setattr(sx, "_validate", lambda p: True)
        monkeypatch.setattr(sx, "_persist", lambda *a, **k: None)
        _, change, source = sx._fetch_spcx_quote()
        assert source == "yfinance_fast_info" and change == "+0.0%"


# ---------------------------------------------------------------------------
# 4. Pronunciation: launch designators and exchange-suffix tickers
# ---------------------------------------------------------------------------

class TestPronunciation:
    def test_designators_and_tickers(self):
        from assets.pronunciation import prepare_text_for_tts
        assert "Starlink fifteen twenty-five" in prepare_text_for_tts("the Starlink 15-25 mission")
        assert "Group six eighty-seven" in prepare_text_for_tts("Starlink Group 6-87 lifted off")
        assert "ten to twenty" in prepare_text_for_tts("a 10-20 dollar range")
        assert "Z L A T" in prepare_text_for_tts("ETF ZLAT.TO gives TFSA investors")
        assert ".TO" not in prepare_text_for_tts("IAG.TO and AGGX.TO rose")
        assert "E5-2696" in prepare_text_for_tts("the Xeon E5-2696 chip")

    def test_arxiv_is_a_word(self):
        import yaml
        data = yaml.safe_load((ROOT / "shows" / "pronunciation_map.yaml").read_text(encoding="utf-8"))
        flat = json.dumps(data)
        assert '"arXiv": "archive"' in flat


# ---------------------------------------------------------------------------
# 5. The lead-source lint reaches every opted-in show
# ---------------------------------------------------------------------------

class TestLeadLintCoverage:
    def test_lead_headers_by_prefix_and_name(self):
        from engine.digest_lint import is_lead_section
        assert is_lead_section("The Big Story")
        assert is_lead_section("Top 12 Space & Astronomy Stories")
        assert is_lead_section("Lead")
        assert not is_lead_section("Quick Bits")

    def test_a_reddit_only_lead_fires(self):
        from engine.digest_lint import lint_x_only_lead
        digest = ("### Top 12 Science & Health Discoveries\n"
                  "1. **A study on sleep** — r/science\n"
                  "The analysis tracks sleep. Source: https://www.reddit.com/r/science/comments/abc/\n")
        f = lint_x_only_lead(digest)
        assert f is not None and f.note
        digest2 = digest.replace("https://www.reddit.com/r/science/comments/abc/",
                                 "https://www.nature.com/articles/s41586-026-1")
        assert not lint_x_only_lead(digest2).note

    @pytest.mark.parametrize("slug,header", [
        ("models_agents_beginners", "The Big Story"),
        ("fascinating_frontiers", "Top 12"),
        ("planetterrian", "Top 12"),
    ])
    def test_the_opted_in_shows_lead_sections_are_seen(self, slug, header):
        import yaml
        from engine.digest_lint import is_lead_section
        cfg = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
        assert "x_only_lead" in (cfg.get("digest_lints") or [])
        assert is_lead_section(header if header != "Top 12" else "Top 12 Stories")


# ---------------------------------------------------------------------------
# 6. Whisper echo tokens never reach captions
# ---------------------------------------------------------------------------

class TestEchoWords:
    def test_a_cross_segment_echo_is_dropped(self):
        from engine.transcripts import drop_echo_words
        segs = [
            {"start": 50.0, "end": 52.2, "text": "The plant is in Texas.",
             "words": [{"word": "in", "start": 51.5, "end": 51.8, "probability": 0.99},
                       {"word": "Texas.", "start": 51.82, "end": 52.2, "probability": 0.999}]},
            {"start": 52.2, "end": 55.0, "text": "Texas. By the end of September",
             "words": [{"word": "Texas.", "start": 52.2, "end": 52.6, "probability": 0.021},
                       {"word": "By", "start": 52.7, "end": 52.9, "probability": 0.99}]},
        ]
        out, n = drop_echo_words(segs)
        assert n == 1
        assert out[1]["text"] == "By the end of September"
        assert [w["word"] for w in out[1]["words"]] == ["By"]
        assert out[0]["words"][-1]["end"] == 52.6
        assert segs[1]["text"].startswith("Texas.")  # input untouched

    def test_a_real_repeat_is_kept(self):
        from engine.transcripts import drop_echo_words
        segs = [{"start": 0, "end": 2, "text": "that that is fine",
                 "words": [{"word": "that", "start": 0.0, "end": 0.3, "probability": 0.9},
                           {"word": "that", "start": 0.3, "end": 0.6, "probability": 0.87},
                           {"word": "is", "start": 0.6, "end": 0.8, "probability": 0.99}]}]
        assert drop_echo_words(segs) == (segs, 0)

    @pytest.mark.skipif(
        not (ROOT / "digests" / "tesla_shorts_time" /
             "Tesla_Shorts_Time_Pod_Ep633_20261013_transcript.json").exists(),
        reason="fixture episode pruned")
    def test_tesla_ep633_drops_exactly_its_texas_echo(self):
        from engine.transcripts import drop_echo_words
        t = json.loads((ROOT / "digests" / "tesla_shorts_time" /
                        "Tesla_Shorts_Time_Pod_Ep633_20261013_transcript.json").read_text(encoding="utf-8"))
        out, n = drop_echo_words(t["segments"])
        assert n == 1
        assert not any(s["text"].startswith("Texas. By the end") for s in out)

    def test_wired_into_transcription(self):
        src = (ROOT / "engine" / "transcripts.py").read_text(encoding="utf-8")
        assert "transcript_segments, _echoes = drop_echo_words(transcript_segments)" in src


# ---------------------------------------------------------------------------
# 7. A lint a show opts into is a rule its prompt states
# ---------------------------------------------------------------------------

class TestWyntkPromptMatchesLint:
    def test_every_wyntk_lint_show_states_the_rule(self):
        import yaml
        missing = []
        for y in sorted(glob.glob(str(ROOT / "shows" / "*.yaml"))):
            cfg = yaml.safe_load(Path(y).read_text(encoding="utf-8")) or {}
            if "wyntk_hook_match" not in (cfg.get("digest_lints") or []):
                continue
            slug = Path(y).stem
            prompt = PROMPTS / f"{slug}_digest.txt"
            text = prompt.read_text(encoding="utf-8") if prompt.exists() else ""
            # The desks share one body snippet.
            for inc in re.findall(r"<<include:\s*([^>]+)>>", text):
                p = (PROMPTS / inc.strip()).resolve()
                if p.exists():
                    text += p.read_text(encoding="utf-8")
            if "FIRST sentence is the hook" not in text:
                missing.append(slug)
        assert not missing, missing


# ---------------------------------------------------------------------------
# 8. Small guards: MAG 7 floor, MIT's YTD line, sibling cadence words,
#    the Voices tick gate
# ---------------------------------------------------------------------------

class TestSmallGuards:
    def test_mag7_company_desk_floor_is_one(self):
        from engine.validation import mag7_validation_config
        rule = [r for r in mag7_validation_config().sections if r.name == "Company Desk"][0]
        assert rule.min_items == 1

    def test_mit_market_pulse_reads_the_benchmark_line(self):
        text = (PROMPTS / "modern_investing_podcast.txt").read_text(encoding="utf-8")
        assert "{nasdaq_benchmark_line}" in text
        assert "If the benchmark data is unavailable, say so" not in text
        pipeline = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'pod_vars.setdefault("nasdaq_benchmark_line", "")' in pipeline
        hook = (ROOT / "shows" / "hooks" / "modern_investing.py").read_text(encoding="utf-8")
        assert 'context["nasdaq_benchmark_line"]' in hook

    WEEKLY = {
        "Environmental Intelligence": "env_intel", "Env Intel": "env_intel",
        "The DP Pod": "dp_pod", "DP Pod": "dp_pod",
        "Offshore North": "offshore_north", "Peptides Weekly": "peptides",
        "Longevity Weekly": "longevity", "Collingwood Weekly": "collingwood",
        "Финансы Просто": "finansy_prosto", "Привет, Русский!": "privet_russian",
    }

    def test_no_prompt_calls_a_weekly_sibling_daily(self):
        """UC Ep140 aired "Environmental Intelligence covers the regulatory
        side daily" from a prompt line that typed the cadence. A sibling's
        cadence word never sits beside its name in any prompt."""
        bad = []
        for p in PROMPTS.rglob("*.txt"):
            text = p.read_text(encoding="utf-8")
            for name in self.WEEKLY:
                for m in re.finditer(re.escape(name), text):
                    window = text[m.end(): m.end() + 80]
                    if re.search(r"\b(?:daily|every day|each day|weekdays)\b", window):
                        bad.append((p.name, name, window[:60]))
        assert not bad, bad

    def test_voices_tick_is_gated_and_fails_open(self):
        src = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
        assert "async function fireTickDue" in src
        assert "if (halfHour || await fireTickDue(env))" in src
        gate = src[src.index("async function fireTickDue"):src.index("async function interviewIsLive")]
        assert "catch" in gate and "return true;" in gate.split("catch")[-1]
        assert "status=in.(scheduled,briefed,in_progress)" in gate
        # The runs read is bounded: stale awaiting_guest / staged rows (Sep 9,
        # Sep 28, Oct 12 2026) would otherwise hold the gate open forever.
        # Since Oct 28 it is bounded by the run's own slot, not its creation
        # (tests/test_slate_2026_10_28.py).
        assert "interview_runs?status=in.(staged,awaiting_guest,fired)&scheduled_for=gte.${ilo}&scheduled_for=lte.${hi}" in gate
