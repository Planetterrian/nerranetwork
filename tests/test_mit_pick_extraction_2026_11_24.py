"""Nov 24 2026: a lost pick is annotated; a deliberate no-trade day is not.

Ep239 (2026-11-22) logged "Could not extract Practice Investment pick" for a
digest whose pick line was "None — monitoring ..." (its signal correctly said
explicit_no_trade). Ep205's "TSX:H" pick, announced on air, logged the very
same line and was lost for five days. The two must not look alike."""
import glob
import re
from pathlib import Path

import pytest

from shows.hooks import modern_investing as mi

ROOT = Path(__file__).resolve().parent.parent

EP239 = """### Practice Investment of the Day
**Trade Type:** Weekly Hold
**Structure:** Shares
**Today's Pick:** None — monitoring copper-related names after the Shanghai meeting.
**Market:** NYSE
**Stop-Loss:** 8% below entry
"""

DRIFT = """### Practice Investment of the Day
**Trade Type:** Weekly Hold
**Today's Pick:** Hydro One Limited (ticker H on the Toronto exchange)
**Market:** TSX
"""


class TestMissingPickIsReported:
    def test_a_declared_no_trade_is_not_a_warning(self, capsys, caplog):
        with caplog.at_level("INFO"):
            assert mi._report_missing_pick(EP239, 239) == "explicit_no_trade"
        assert "::warning::" not in capsys.readouterr().out
        assert not [r for r in caplog.records if r.levelname == "WARNING"]

    def test_a_pick_that_cannot_be_read_is_annotated(self, capsys):
        assert mi._extract_trade_from_digest(DRIFT, 1) is None
        assert mi._report_missing_pick(DRIFT, 300) == "no_pick_extracted"
        out = capsys.readouterr().out
        assert "::warning::modern_investing Ep300" in out
        assert "NOT in the" in out

    def test_no_practice_section_is_quiet(self, capsys):
        assert mi._report_missing_pick("### Market Pulse\nNothing.", 1) == "no_practice_section"
        assert "::warning::" not in capsys.readouterr().out

    def test_post_generate_uses_the_reporter(self):
        src = (ROOT / "shows/hooks/modern_investing.py").read_text(encoding="utf-8")
        assert "_report_missing_pick(digest_text, episode_num)" in src


class TestCommittedDigestsAllRead:
    """Every recent committed digest either yields a pick or declares none."""

    def test_recent_digests(self):
        files = sorted(
            f for f in glob.glob(str(ROOT / "digests/modern_investing/Modern_Investing_Ep*_2026*.md"))
            if re.search(r"Ep\d+_\d{8}\.md$", f))[-30:]
        if not files:
            pytest.skip("no committed digests")
        lost = []
        for f in files:
            text = Path(f).read_text(encoding="utf-8")
            if mi._extract_trade_from_digest(text, 1) is None \
                    and mi._no_trade_reason(text) == "no_pick_extracted":
                lost.append(Path(f).name)
        assert not lost, f"picks present but unreadable: {lost}"
