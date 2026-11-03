"""CLAUDE.md stays the rules, not the history (six-month review, Nov 3 2026).

The file is loaded at the start of every Claude Code session and replayed
across the agentic loop, so its size is a per-session cost on all future
work. The Jul 29 2026 pass trimmed it 185 -> 124 KB by moving dated
narratives verbatim to ``docs/show_review_history.md``; by Nov 3 2026 it
was 540 KB (~135k tokens). This pass moved every dated pass section's body
verbatim to ``docs/claude_md_history/<yyyy_mm_dd>_<slug>.md`` and left the
rules that bind beside a link.

Three guards:

* the file stays under 150,000 bytes (the trim lands around 120 KB; the
  headroom is for a few months of ten-line rule additions, not narrative);
* every relative ``docs/...md`` link in it resolves to a file (a history
  link that 404s is a rule with no record behind it);
* the strings other tests read from CLAUDE.md stay verbatim (the NEEDLES
  list was copied from each test that opens the file on 2026-11-03).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"
HISTORY_DIR = ROOT / "docs" / "claude_md_history"

MAX_BYTES = 150_000

# Strings other tests read from CLAUDE.md. Each entry names the test that
# reads it; change the test and this list together, never the sentence alone.
NEEDLES = (
    # tests/test_grok47_resilience_2026_09_24.py::TestDocs
    "_call_pinned",
    "PinnedModelUnavailable",
    # tests/test_network_sourcing_pass_2026_09_24.py (case-insensitive read)
    "Network sourcing pass",
    # tests/test_story_tags_2026_10_20.py::TestMeasurementBehindTheChange
    "+34 Hz",
    "13 swells",
    "story_tags",
    "Probe TTS tags",
    # tests/test_slate_2026_10_23.py::TestTheAccountIsOnWorkersPaid
    "Workers Paid now",
    # tests/test_first_slate_2026_09_24.py::TestDocs
    "What FIRES is what was last deployed",
    "check_scheduler_deploy.py",
    # tests/test_age_of_ai_pass_2026_09_21.py::TestNotAPhoneCallShow (docstring)
    "Do not describe the show as a phone-call show on any surface.",
    # tests/test_integration.py: the show table's header row; each
    # ``shows/<slug>.yaml`` row's fourth column is the schedule it compares
    # with run-show.yml's CRON_MAP.
    "| Show | Legacy Script | YAML Config | Schedule | X Account | TTS |",
    # The head rule this pass added.
    "A pass adds at most ten lines here",
)

# Strings that must stay ABSENT (tests assert on their absence).
FORBIDDEN = (
    # tests/test_network_sourcing_pass_2026_09_24.py
    "Known hole, not fixed here",
    # tests/test_slate_2026_10_23.py
    "account is on Workers Free",
    "account is on the Workers Free",
)


def _text() -> str:
    return CLAUDE_MD.read_text(encoding="utf-8")


def _flat(s: str) -> str:
    """Line wrapping is not content: compare needles on collapsed whitespace."""
    return re.sub(r"\s+", " ", s)


def test_claude_md_is_under_the_size_cap():
    size = CLAUDE_MD.stat().st_size
    assert size <= MAX_BYTES, (
        f"CLAUDE.md is {size:,} bytes (cap {MAX_BYTES:,}). A pass adds at most "
        "ten lines here; move the narrative to docs/reviews/ or "
        "docs/claude_md_history/ and keep only the rules that bind."
    )


def test_every_relative_docs_link_resolves():
    text = _text()
    missing = []
    for m in re.finditer(r"\]\((docs/[^)\s#]+\.md)(?:#[^)]*)?\)", text):
        rel = m.group(1)
        if not (ROOT / rel).is_file():
            missing.append(rel)
    assert not missing, "CLAUDE.md links to docs that do not exist:\n  " + "\n  ".join(
        sorted(set(missing))
    )


def test_history_directory_is_linked_and_populated():
    files = sorted(HISTORY_DIR.glob("*.md"))
    assert files, "docs/claude_md_history/ holds the moved narratives"
    text = _text()
    unlinked = [p.name for p in files if f"docs/claude_md_history/{p.name}" not in text]
    assert not unlinked, "history files CLAUDE.md no longer links:\n  " + "\n  ".join(unlinked)
    for p in files:
        head = p.read_text(encoding="utf-8").splitlines()[:4]
        assert any("Moved verbatim from CLAUDE.md" in line for line in head), p.name


def test_needles_other_tests_read_stay_verbatim():
    text = _flat(_text())
    lower = text.lower()
    lost = [n for n in NEEDLES if _flat(n) not in text and _flat(n).lower() not in lower]
    assert not lost, "CLAUDE.md lost a sentence another test reads:\n  " + "\n  ".join(lost)
    present = [n for n in FORBIDDEN if n in text]
    assert not present, "CLAUDE.md regrew a sentence a test forbids:\n  " + "\n  ".join(present)
    assert re.search(r"running \d+ shows via a unified", text), (
        "tests/test_show_count_consistency.py reads the show count from this sentence"
    )


def test_show_table_rows_survive():
    """tests/test_integration.py parses every ``| ... | shows/<slug>.yaml | <schedule> |``
    row; tests/test_launch_cohort_schedule_2026_09_23.py forbids a
    pre-launch row."""
    rows = [
        line
        for line in _text().splitlines()
        if line.startswith("|") and ".yaml" in line and "shows/" in line
    ]
    assert len(rows) >= 29, f"the show table lost rows ({len(rows)} left)"
    assert not [r for r in rows if "pre-launch" in r]
