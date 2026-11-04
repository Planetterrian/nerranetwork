"""The digest's length floor becomes a FACT floor, on one flagship first
(Nov 3 2026, ``digest-fact-floor-2026-11-03``).

The expansion retry fired on 7/7 episodes of every flagship in the week to
Nov 2 and 0/7 on the cohort: the word floor was what the retry produced,
not what the day gave, and the padding it bought — the digest's own
fact-free share (Planetterrian 62% against 10-17% on the cohort) — was the
best predictor of the daily audit's Repetitive flag (AUC 0.72; the script
inherits it at r 0.69). Pins:

* ``engine.generator.digest_fact_count`` — story-item sentences carrying
  a number, a name, a date or a quote the digest had not given before;
  the hook, What You Need to Know, the deep dive and the Source lines
  never count, and a restatement counts for nothing;
* ``llm.min_digest_facts`` — set, the loop fires on facts (after the Oct 19
  stories floor) instead of words and keeps the retry only when the fact
  count ROSE; 0 is byte-identical to the word test;
* the retry prompt's fact-floor branch asks for fact-bearing sentences,
  never for length, and the deep dive is not its length lever;
* the read-only instrument on ``ScriptAudit`` (digest / script fact-free
  shares, attribution openers, caveat sentences) and its snapshot columns;
* the rollout: Planetterrian alone, calibrated on its last 14 digests;
  every skip floor untouched.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import engine.generator as gen
from engine import script_audit as SA

ROOT = Path(__file__).resolve().parent.parent
DIGESTS = ROOT / "digests"


def _read(rel: str) -> str:
    return (DIGESTS / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The counter
# ---------------------------------------------------------------------------

class TestTheCounter:
    #: Hand-counted on Nov 3 2026 against the committed digests (a lowercase
    #: protein name and an initial after an abbreviation's dot are the ±2).
    COMMITTED = {
        "tesla_shorts_time/Tesla_Shorts_Time_Pod_Ep653_20261102.md": 32,
        "planetterrian/Planetterrian_Daily_Ep230_20261031.md": 25,
        "ai_chips/AI_Chips_Ep042_20261102.md": 22,
    }

    @pytest.mark.parametrize("rel,expected", sorted(COMMITTED.items()))
    def test_three_committed_digests(self, rel, expected):
        assert abs(gen.digest_fact_count(_read(rel)) - expected) <= 2

    def test_ai_chips_is_the_densest_of_the_three(self):
        shares = {}
        free = {}
        for rel in self.COMMITTED:
            facts, total, _ff = SA.digest_fact_profile(_read(rel))
            shares[rel] = facts / total
            free[rel] = SA.digest_fact_free_pct(_read(rel))
        chips = "ai_chips/AI_Chips_Ep042_20261102.md"
        assert shares[chips] == max(shares.values())
        assert free[chips] == min(free.values())
        tesla = "tesla_shorts_time/Tesla_Shorts_Time_Pod_Ep653_20261102.md"
        assert free[tesla] > 40.0  # the flagship shape the review measured

    def test_a_restatement_counts_for_nothing(self):
        one_fact = (
            "**HOOK:** The council met.\n### Top News\n1. **Item one**\n"
            "   The council approved the transit plan on Tuesday. "
            "The plan was approved by the council. "
            "The approval of the plan came from the council.\n"
        )
        assert gen.digest_fact_count(one_fact) == 1
        with_number = one_fact.rstrip("\n") + " The vote was 7 to 2.\n"
        assert gen.digest_fact_count(with_number) == 2
        # the same number again is the second telling, not a fact
        assert gen.digest_fact_count(with_number.rstrip("\n") + " The tally stood at 7 to 2.\n") == 2
        # a quote is always a fact
        assert gen.digest_fact_count(with_number.rstrip("\n") + ' The mayor called it "a start".\n') == 3

    def test_hook_wyntk_source_lines_and_the_deep_dive_never_count(self):
        digest = (
            "# Show\n> **Mayor Ortega won 61 percent on Tuesday.**\n\n"
            "**What You Need to Know:** Ortega won with 61 percent; turnout was 44 percent.\n\n"
            "### Top News\n1. **Item one — Outlet**\n"
            "   The council approved the transit plan. "
            "Source: [outlet.example](https://outlet.example/story-2026-11-03-7-to-2)\n\n"
            "### Science Deep Dive: how a council votes\n"
            "A council of 9 members votes by a simple majority. In 2019 the Charter Review set the quorum at 5.\n"
        )
        assert gen.digest_fact_count(digest) == 0
        assert SA.digest_story_sentences(digest) == ["The council approved the transit plan."]

    def test_also_today_one_liners_count_and_a_name_is_new_once(self):
        digest = (
            "**HOOK:** x\n### Top News\n1. **Item one**\n"
            "   Mayor Ortega opened the line on Tuesday. Ortega spoke for an hour.\n\n"
            "### Also Today\n**Second story: Outlet** Ortega also named Dana Reyes transit chief.\n"
        )
        # Tuesday/Ortega new; "Ortega spoke" restates; Reyes is new
        assert gen.digest_fact_count(digest) == 2

    def test_omni_view_story_headings_are_items(self):
        digest = (
            "## Today's lead story (1)\n### 1) Council approves the plan\n"
            "**What happened (neutral):** The council approved the transit plan on Tuesday by 7 votes to 2.\n\n"
            "**Read more (sources):**\n- [Outlet](https://outlet.example/a) — reports the vote\n"
        )
        assert gen.digest_fact_count(digest) == 1
        assert all("outlet.example" not in s for s in SA.digest_story_sentences(digest))

    def test_an_initial_never_splits_a_sentence(self):
        assert SA.fact_sentences("TSMC chief C.C. Wei said so. The U.S. Army agreed.") == [
            "TSMC chief C.C. Wei said so.", "The U.S. Army agreed.",
        ]


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

ONE_FACT = (
    "**HOOK:** The council met.\n### Top News\n1. **Item one**\n"
    "   The council approved the transit plan on Tuesday. The plan was approved by the council. "
    "The approval of the plan came from the council. The council gave the plan its approval. "
    "Members voted for the plan. The plan now has the council's approval.\n"
)
THREE_FACTS = (
    "**HOOK:** The council met.\n### Top News\n1. **Item one**\n"
    "   The council approved the transit plan on Tuesday by a vote of 7 to 2. "
    "Mayor Ortega called it the largest transit decision since 2019. "
    "The first line opens in March 2028 at a cost of 1.2 billion dollars.\n"
)
ONE_FACT_LONGER = ONE_FACT.rstrip("\n") + (
    " The approval was welcomed by the members. The decision followed a long debate. "
    "The members then adjourned for the evening. The plan will now proceed.\n"
)


class _LLM:
    model = "grok-4.3"
    podcast_model = ""
    podcast_chain = False
    combined_generation = False
    max_tokens = 3000
    podcast_max_tokens = 5000
    digest_temperature = 0.5
    podcast_temperature = 0.7
    system_prompt_file = ""
    podcast_prompt_file = ""
    stream = False
    pinned_model_retries = 1
    digest_expansion_attempts = 1
    digest_expand_below_target = True
    min_digest_words = 10  # every fixture clears the WORD floor
    min_digest_facts = 0

    def __init__(self, prompt_file: str, facts: int):
        self.digest_prompt_file = prompt_file
        self.min_digest_facts = facts


class _Cfg:
    name = "Fact Floor Test Show"
    slug = "fact_floor_test_show"  # no validation config -> no item floor
    keywords = ()
    narrative_mode = False
    source_integrity = None
    chapters = None
    youtube = None

    def __init__(self, tmp_path: Path, facts: int):
        p = tmp_path / "digest.txt"
        p.write_text("Write the digest for {today_str}.", encoding="utf-8")
        self.llm = _LLM(str(p), facts)


def _run(monkeypatch, cfg, answers):
    calls = []
    queue = list(answers)

    def fake_call(prompt, **kw):
        calls.append(prompt)
        return queue.pop(0), {"finish_reason": "stop", "usage": {}}

    monkeypatch.setattr(gen, "_call_grok", fake_call)
    gen._STASHED_COMBINED = None
    gen._LAST_DIGEST_EXPANSION = None
    out = gen.generate_digest({"today_str": "2026-11-03", "episode_num": 233}, cfg, tracker=None)
    return out, calls


class TestTheLoopFiresOnFacts:
    def test_over_the_word_floor_under_the_fact_floor_fires_and_is_judged_on_facts(self, monkeypatch, tmp_path):
        cfg = _Cfg(tmp_path, facts=3)
        assert gen.digest_prose_word_count(ONE_FACT) > cfg.llm.min_digest_words
        out, calls = _run(monkeypatch, cfg, [ONE_FACT, THREE_FACTS])
        assert len(calls) == 2
        assert "vote of 7 to 2" in out
        rec = gen.last_digest_expansion()
        assert rec["fired"] is True and rec["improved"] is True
        assert (rec["facts_before"], rec["facts_after"], rec["floor_facts"]) == (1, 3, 3)
        assert rec["floor"] == 10 and rec["words_after"] == gen.digest_prose_word_count(THREE_FACTS)

    def test_a_retry_whose_facts_did_not_rise_is_discarded(self, monkeypatch, tmp_path):
        cfg = _Cfg(tmp_path, facts=3)
        assert gen.digest_prose_word_count(ONE_FACT_LONGER) > gen.digest_prose_word_count(ONE_FACT)
        out, calls = _run(monkeypatch, cfg, [ONE_FACT, ONE_FACT_LONGER])
        assert len(calls) == 2
        assert "adjourned" not in out  # the longer, no-denser draft was thrown away
        rec = gen.last_digest_expansion()
        assert rec["fired"] is True and rec["improved"] is False
        assert rec["facts_before"] == 1 and rec["facts_after"] == 1 and rec["words_after"] is None

    def test_at_the_fact_floor_nothing_fires(self, monkeypatch, tmp_path):
        cfg = _Cfg(tmp_path, facts=3)
        out, calls = _run(monkeypatch, cfg, [THREE_FACTS])
        assert len(calls) == 1
        rec = gen.last_digest_expansion()
        assert rec["fired"] is False and rec["facts_before"] == 3 and rec["facts_after"] is None

    def test_the_retry_prompt_asks_for_facts_never_length(self, monkeypatch, tmp_path):
        cfg = _Cfg(tmp_path, facts=3)
        _out, calls = _run(monkeypatch, cfg, [ONE_FACT, THREE_FACTS])
        retry = calls[1]
        assert "FACT FLOOR" in retry and "the floor is 3" in retry
        assert "Length is not the measure" in retry
        assert "LENGTHEN THAT SECTION" not in retry
        assert "Rewrite it to at least" not in retry
        assert "never from memory" in retry and "domain knowledge" not in retry

    def test_without_the_flag_the_word_test_is_byte_identical(self, monkeypatch, tmp_path):
        cfg = _Cfg(tmp_path, facts=0)
        out, calls = _run(monkeypatch, cfg, [ONE_FACT])
        assert len(calls) == 1  # over the word floor: no retry, whatever the facts
        rec = gen.last_digest_expansion()
        assert rec["fired"] is False
        assert rec["floor_facts"] is None and rec["facts_before"] is None and rec["facts_after"] is None
        cfg.llm.min_digest_words = 10_000
        out, calls = _run(monkeypatch, cfg, [ONE_FACT, ONE_FACT_LONGER])
        assert len(calls) == 2 and "adjourned" in out  # the word path keeps a longer draft
        assert "Rewrite it to at least 10000 words" in calls[1] and "FACT FLOOR" not in calls[1]


class TestTheRetryPrompt:
    def test_item_floor_ranks_above_the_fact_floor(self):
        p = gen._build_digest_expansion_retry_prompt(
            900, 1400, "draft", item_shortfalls=[("Science Stories", 5, 8)], fact_floor=(12, 18),
        )
        assert p.index("ITEM FLOOR") < p.index("FACT FLOOR")
        assert "The fact floor below ranks second to this floor." in p
        assert "it is not the length lever" in p and "LENGTHEN" not in p

    def test_the_word_branch_is_unchanged(self):
        p = gen._build_digest_expansion_retry_prompt(900, 1400, "draft", item_shortfalls=[("Science Stories", 5, 8)])
        assert "LENGTHEN THAT SECTION first" in p and "FACT FLOOR" not in p
        assert "The depth rule below ranks second to this floor." in p
        assert "Rewrite it to at least 1400 words" in p

    def test_no_quotable_specimen(self):
        p = gen._build_digest_expansion_retry_prompt(900, 1400, "draft", fact_floor=(12, 18))
        # the ask describes the SHAPE of a fact-bearing sentence, never writes one
        assert "for example" not in p.lower() and "e.g." not in p.lower()


# ---------------------------------------------------------------------------
# The instrument
# ---------------------------------------------------------------------------

SCRIPT = (
    "Patrick: This is the show. Three stories today: the vote, the mayor, the line. Let's start.\n"
    "The council approved the transit plan on Tuesday by a vote of 7 to 2.\n"
    "The plan was approved by the council.\n"
    "According to the Gazette, the mayor called it the largest decision since 2019.\n"
    "The Gazette reports that the first line opens in March 2028.\n"
    "That is an observational association, not a randomized test of ridership.\n"
    "The finding does not establish that the line will carry 40,000 riders.\n"
    "Mayor Ortega welcomed the result.\n"
)


class TestTheInstrument:
    def test_to_metrics_carries_the_four_measures(self):
        a = SA.audit_script(SCRIPT, digest_text=ONE_FACT)
        m = a.to_metrics()
        for key in ("digest_fact_free_pct", "script_fact_free_pct",
                    "script_attribution_opener_pct", "script_caveat_sentence_pct"):
            assert key in m, key
        # 6 story sentences, 1 with a fact of its own, 5 restatements with >= 3 salient words
        assert m["digest_fact_free_pct"] == pytest.approx(100 * 5 / 6, abs=0.1)
        # the fact walk: 7 body sentences after the identity line, the map
        # and "Let's start."; "The plan was approved…" and the observational
        # caveat carry nothing of their own
        assert a.script_fact_free_pct == pytest.approx(100 * 2 / 7, abs=0.1)
        # "According to the Gazette, …" and "The Gazette reports that …" open
        # on the outlet, out of the 8 body sentences the tail measure reads
        assert a.attribution_opener_pct == pytest.approx(100 * 2 / 8, abs=0.1)
        # one caveat sentence carries no fact of its own; the other carries a number
        assert a.caveat_sentence_pct == pytest.approx(100 * 1 / 7, abs=0.1)

    def test_a_company_saying_a_thing_is_not_an_attribution_opener(self):
        assert SA.ATTRIBUTION_OPENER_RE.match("Tesla said it will open the plant in March.") is None
        assert SA.ATTRIBUTION_OPENER_RE.match("Electrek reports that the plant opens in March.")
        assert SA.ATTRIBUTION_OPENER_RE.match("According to Reuters, the plant opens in March.")

    def test_no_digest_no_body_is_none_never_zero(self):
        assert SA.digest_fact_free_pct("") is None
        assert SA.script_fact_free_pct("Patrick: This is the show.") is None
        assert SA.caveat_sentence_pct("") is None
        a = SA.audit_script("Patrick: This is the show.")
        assert "digest_fact_free_pct" not in a.to_metrics()

    def test_the_snapshot_prints_the_columns(self):
        src = (ROOT / "scripts" / "review_snapshot.py").read_text(encoding="utf-8")
        assert "| fact-free (digest / script) | opener | caveat |" in src
        for attr in ("digest_fact_free_pct", "script_fact_free_pct",
                     "attribution_opener_pct", "caveat_sentence_pct"):
            assert f"a.{attr}" in src, attr

    def test_committed_longevity_script_reads_caveats(self):
        script = _read("longevity/Longevity_Weekly_Ep006_20261028_tts.txt")
        pct = SA.caveat_sentence_pct(script)
        assert pct is not None and pct > 5.0
        assert SA.caveat_sentence_pct(_read("ai_chips/AI_Chips_Ep042_20261102_tts.txt")) < 2.0


# ---------------------------------------------------------------------------
# The rollout
# ---------------------------------------------------------------------------

class TestTheRollout:
    def test_planetterrian_alone_runs_the_fact_floor(self):
        from engine.config import load_config
        cfg = load_config(ROOT / "shows" / "planetterrian.yaml")
        assert cfg.llm.min_digest_facts == 18
        assert cfg.llm.digest_expand_below_target is True and cfg.llm.min_digest_words == 1400
        assert cfg.llm.min_podcast_publish_words == 850  # the skip floor never moves
        others = []
        for p in sorted((ROOT / "shows").glob("*.yaml")):
            if p.name == "planetterrian.yaml":
                continue
            llm = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("llm") or {}
            if llm.get("min_digest_facts"):
                others.append(p.name)
        assert others == [], f"the fact floor ships on one flagship first: {others}"

    def test_the_floor_clears_an_ordinary_planetterrian_day(self):
        """Calibration: over the 14 committed digests the floor was set on
        (Ep219-232, the last 14 before the Nov 3 slate) the counter reads
        11-25 fact sentences, median 20; 18 fires on at most half of those
        days (two, the thinnest). The set is PINNED — a calibration record,
        never a window that slides with each day's episode."""
        files = []
        for ep in range(219, 233):
            matches = [p for p in (DIGESTS / "planetterrian").glob(f"Planetterrian_Daily_Ep{ep}_*.md")
                       if "_transcript" not in p.name and "_tts" not in p.name]
            assert len(matches) == 1, (ep, matches)
            files.append(matches[0])
        counts = [gen.digest_fact_count(p.read_text(encoding="utf-8")) for p in files]
        assert len(counts) == 14
        fired = sum(1 for c in counts if c < 18)
        assert fired <= 7, (fired, counts)

    def test_the_default_is_off_and_run_show_records_the_fact_keys(self):
        from engine.config import LLMConfig
        assert LLMConfig().min_digest_facts == 0
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        for key in ("digest_expansion_floor_facts", "digest_expansion_facts_before",
                    "digest_expansion_facts_after"):
            assert f'metrics.record("{key}"' in src, key
