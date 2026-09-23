"""Guards from the second review of the four new shows' Episode 1s (Sep 23 2026).

All four published. Each guard names the defect it answers.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
UTC = dt.timezone.utc


def _prompt(name: str) -> str:
    return (ROOT / "shows" / "prompts" / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# MAG 7 Ep1 opened on the lone word "U.S."
# ---------------------------------------------------------------------------

class TestColdOpenFragment:
    HOOK = ("U.S. government files brief urging Supreme Court to reverse Apple "
            "contempt ruling in Epic case.")

    def test_splitter_keeps_abbreviations_whole(self):
        from engine.generator import _split_sentences

        parts = _split_sentences(self.HOOK + " Dr. Smith testified. It rose in the U.S. The company fell.")
        assert parts == [self.HOOK, "Dr. Smith testified.", "It rose in the U.S.", "The company fell."]

    def test_dedup_never_leaves_an_abbreviation_fragment(self):
        from engine.generator import _dedup_expansion_sentences

        script = (f"{self.HOOK}\n\nWelcome to the very first episode of MAG 7 Daily! "
                  f"Today is September twenty-third. {self.HOOK}\n\nNext line.")
        out, removed = _dedup_expansion_sentences(script, min_words=8)
        assert removed == 1
        assert "U.S.\n" not in out and not out.rstrip().endswith("U.S.")
        assert out.startswith(self.HOOK)
        assert "twenty-third. U.S." not in out

    def test_debut_intro_does_not_repeat_the_hook(self):
        src = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'f"Today is {today_str}. {effective_hook}"' not in src
        assert src.count('f"Today is {today_str}.",') == 3


# ---------------------------------------------------------------------------
# MAG 7 tape: stale session, date spoken seven times
# ---------------------------------------------------------------------------

class TestTape:
    @pytest.mark.parametrize("now,want", [
        ("2026-09-23T00:44", "2026-09-22"),  # the Ep1 run: 20:44 New York
        ("2026-09-23T10:46", "2026-09-22"),  # the scheduled 06:46 ET slot
        ("2026-09-22T19:00", "2026-09-21"),  # 15:00 New York, session open
        ("2026-09-26T14:00", "2026-09-25"),  # Saturday
        ("2026-09-28T10:46", "2026-09-25"),  # Monday pre-open
    ])
    def test_expected_last_session(self, now, want):
        from engine.market_quotes import expected_last_session

        assert expected_last_session(dt.datetime.fromisoformat(now).replace(tzinfo=UTC)) == want

    def test_session_date_is_said_once(self):
        from engine.market_quotes import Quote, tape_block

        block = tape_block([Quote("AAPL", 338.98, 336.13, "2026-09-21"),
                            Quote("TSLA", 375.3, 364.4, "2026-09-21")],
                           {"AAPL": "Apple", "TSLA": "Tesla"}, ["AAPL", "TSLA"])
        assert block.count("2026-09-21") == 1
        assert "ONCE" in block

    def test_mixed_dates_stay_per_line(self):
        from engine.market_quotes import Quote, tape_block

        block = tape_block([Quote("AAPL", 1.0 * 300, 299.0, "2026-09-21"),
                            Quote("TSLA", 375.3, 364.4, "2026-09-22")],
                           {}, ["AAPL", "TSLA"])
        assert "on 2026-09-21" in block and "on 2026-09-22" in block

    def test_digest_prompt_says_the_date_once(self):
        assert "First line: the session date the MARKET TAPE block names, once." in _prompt(
            "mag7_digest.txt")


# ---------------------------------------------------------------------------
# MAG 7 Company Desk: empty item, company-name headings, a Thread that retold
# ---------------------------------------------------------------------------

def test_empty_item_heading_is_dropped():
    from engine.absence_sentences import drop_empty_items

    digest = ("### Company Desk\n**Meta tests a concierge: Reuters**\nMeta is testing it. "
              "Source: [r](https://r)\n\n**Microsoft (MSFT):** The Information\n\n"
              "### The Counterpoint\n**x: y**\nBody.")
    out, n = drop_empty_items(digest)
    assert n == 1
    assert "Microsoft (MSFT)" not in out and "Meta tests a concierge" in out


def test_mag7_company_desk_and_thread_rules():
    p = _prompt("mag7_digest.txt")
    assert "never the company's name or ticker" in p
    assert "never a heading with nothing under it" in p
    assert "Build it from an article that itself names two or more of the seven" in p


# ---------------------------------------------------------------------------
# Peptides: an off-subject spotlight, rodent-study news, a spoken domain
# ---------------------------------------------------------------------------

class TestEuropePmcSlices:
    def test_reviews_first_and_medline_only(self):
        from engine.europe_pmc import abstracts_for

        seen = []

        def fake(params):
            seen.append(params)
            return {"resultList": {"result": []}}

        abstracts_for("TITLE:\"insulin\"", get=fake)
        assert 'PUB_TYPE:"review"' in seen[0]["query"]
        assert all("SRC:MED" in p["query"] for p in seen)

    @pytest.mark.parametrize("slug", ("peptides", "longevity"))
    def test_no_curriculum_search_leans_on_a_bare_history_term(self, slug):
        """TITLE:"history" matched "natural history" and "life-history" and
        the insulin spotlight explained rats and wild sheep."""
        queue = yaml.safe_load((ROOT / "shows" / "curricula" / f"{slug}.yaml").read_text())["queue"]
        for entry in queue:
            assert 'TITLE:"history"' not in entry["search"], entry["id"]

    def test_insulin_spotlight_asks_for_the_subject(self):
        queue = yaml.safe_load((ROOT / "shows/curricula/peptides.yaml").read_text())["queue"]
        insulin = next(e for e in queue if e["id"] == "insulin-the-first-peptide")
        assert "discovery of insulin" in insulin["search"]


def test_spoken_domain_attribution_is_removed_but_the_network_address_is_not():
    from engine.absence_sentences import is_absence_sentence

    assert is_absence_sentence("The source for these statements appears in reports linked from x dot com.")
    assert is_absence_sentence("The source is Lifespan dot io.")
    assert not is_absence_sentence("Links to every source are at nerranetwork dot com.")
    assert not is_absence_sentence("Novo Nordisk posted the results on its site.")


@pytest.mark.parametrize("slug", ("peptides", "longevity"))
def test_health_evidence_mix_and_on_subject_spotlight(slug):
    p = _prompt(f"{slug}_digest.txt")
    assert "EVIDENCE MIX" in p and "At most one cell or animal study item a week" in p
    assert "a pointer, not a source" in p
    assert "Use only the abstracts above that are ABOUT this subject" in p


# ---------------------------------------------------------------------------
# Phase 1 launch (B-PR): the four shows go on the schedule
# ---------------------------------------------------------------------------

LAUNCH = {
    "ai_chips": ("31 9 * * *", None),
    "mag7": ("46 10 * * *", None),
    "longevity": ("1 11 * * 3", "wednesday"),
    "peptides": ("7 11 * * 4", "thursday"),
}


class TestPhase1Launch:
    def _wf(self):
        return (ROOT / ".github/workflows/run-show.yml").read_text(encoding="utf-8")

    @pytest.mark.parametrize("slug", sorted(LAUNCH))
    def test_cron_map_and_cron_line(self, slug):
        import re

        cron, day = LAUNCH[slug]
        wf = self._wf()
        assert f"- cron: '{cron}'" in wf
        m = re.search(r'"' + re.escape(cron) + r'":\s*\("(\w+)",\s*(None|"\w+")\)', wf)
        assert m and m.group(1) == slug
        assert m.group(2) == (f'"{day}"' if day else "None")

    @pytest.mark.parametrize("slug", sorted(LAUNCH))
    def test_audited_and_in_all(self, slug):
        import review_episodes as R

        assert slug in R.SHOW_REGISTRY and slug not in R.PRELAUNCH_SLUGS
        want = LAUNCH[slug][1] or "daily"
        assert R.SHOW_REGISTRY[slug]["schedule"] == want
        all_line = next(line for line in self._wf().splitlines()
                        if line.strip().startswith('shows = ["tesla"'))
        assert f'"{slug}"' in all_line
        audit = (ROOT / ".github/workflows/daily-audit.yml").read_text(encoding="utf-8")
        assert f'"{slug}_podcast.rss"' in audit

    def test_first_run_dates_agree_everywhere(self):
        """A weekly whose Ep1 was produced by hand mid-week never runs the
        next day on its first cron (Longevity Ep1 Tue 22, Wednesday slot)."""
        import re

        import review_episodes as R

        reg = {s: i["first_run"] for s, i in R.SHOW_REGISTRY.items() if i.get("first_run")}
        wf = self._wf()
        block = wf[wf.index("FIRST_SCHEDULED_RUN = {"):]
        block = block[:block.index("}")]
        gate = dict(re.findall(r'"(\w+)":\s*"(\d{4}-\d{2}-\d{2})"', block))
        worker = (ROOT / "workers/scheduler/src/index.ts").read_text(encoding="utf-8")
        wblock = worker[worker.index("const FIRST_RUN"):]
        wblock = wblock[:wblock.index("};")]
        wk = dict(re.findall(r'(\w+):\s*"(\d{4}-\d{2}-\d{2})"', wblock))
        assert reg == gate == wk == {"longevity": "2026-09-30", "peptides": "2026-10-01"}

    def test_audit_does_not_expect_a_weekly_before_its_first_run(self):
        import datetime as _dt

        import review_episodes as R

        info = R.SHOW_REGISTRY["longevity"]
        assert not R._scheduled_on(info, _dt.date(2026, 9, 23))   # a Wednesday
        assert R._scheduled_on(info, _dt.date(2026, 9, 30))
