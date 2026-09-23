"""The Week's Board — Prediction Markets Daily's Friday scoring segment.

Sep 23 2026 (launch-cohort review, market read). Every credible forecasting
programme scores itself on a fixed clock — Risky Business's January
predictions and December scoring, the forecasting tournaments' resolution
tables — and the show that reads prices as forecasts should too. On
Fridays the hook reads the week's COMMITTED Board sections (Monday to
Thursday, plus whatever today's venues returned), pairs each question with
its later price where the same market recurs, and supplies the digest a
data-side block for a ``### The Week's Board`` section. Nothing is looked up
by the model: a question with no later reading is reported as "no later
reading", never as resolved.

Data-side and deterministic. A week with no committed Boards produces no
block and no section (the validator treats the section as optional).
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

BOARD_HEADER_RE = re.compile(r"^###\s+The Board\s*$", re.MULTILINE)
NEXT_HEADER_RE = re.compile(r"^###\s+", re.MULTILINE)
_LINE_RE = re.compile(
    r"^(?P<question>[^:\n]{8,}?):\s*(?P<prob>\d{1,3}(?:\.\d+)?)%\s*implied probability"
    r"(?P<rest>.*)$", re.IGNORECASE)
_VENUE_RE = re.compile(r"\b(Polymarket|Kalshi|Manifold)\b")
_DATE_IN_NAME_RE = re.compile(r"_(\d{8})\.md$")

#: How many committed days feed the Friday block (Mon–Thu of the same week
#: on a normal week; the window is by date so a holiday week still works).
WEEK_DAYS = 6


def board_lines(digest_md: str) -> List[Dict[str, object]]:
    """Parse one committed digest's Board into ``[{question, prob, venue}]``."""
    m = BOARD_HEADER_RE.search(digest_md or "")
    if not m:
        return []
    rest = digest_md[m.end():]
    nxt = NEXT_HEADER_RE.search(rest)
    body = rest[:nxt.start()] if nxt else rest
    out: List[Dict[str, object]] = []
    for raw in body.splitlines():
        line = raw.strip().lstrip("-*• ").strip()
        lm = _LINE_RE.match(line)
        if not lm:
            continue
        vm = _VENUE_RE.search(lm.group("rest"))
        out.append({
            "question": lm.group("question").strip(),
            "prob": float(lm.group("prob")),
            "venue": vm.group(1) if vm else "",
        })
    return out


def committed_boards(digests_dir: Path, today: _dt.date,
                     days: int = WEEK_DAYS) -> List[Tuple[_dt.date, List[Dict[str, object]]]]:
    """``[(date, lines)]`` for the show's digests dated inside the window,
    oldest first, today excluded (today's board comes from the live venues)."""
    out: List[Tuple[_dt.date, List[Dict[str, object]]]] = []
    if not digests_dir.exists():
        return out
    for path in sorted(digests_dir.glob("*_Ep*_*.md")):
        dm = _DATE_IN_NAME_RE.search(path.name)
        if not dm:
            continue
        try:
            d = _dt.datetime.strptime(dm.group(1), "%Y%m%d").date()
        except ValueError:
            continue
        if d >= today or (today - d).days > days:
            continue
        try:
            lines = board_lines(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if lines:
            out.append((d, lines))
    return out


def _key(question: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", question.lower()).strip()


def week_board_block(digests_dir: Path, today: _dt.date,
                     todays_articles: Optional[Sequence[Dict[str, object]]] = None) -> str:
    """The Friday instruction block, or "" when the week has no boards.

    Each question that appeared on a committed board this week is listed
    with its FIRST reading and, where the same question recurs on a later
    board or in today's venue articles, its LATEST reading — so the digest
    can say what the price did, in points, over the week. A question with
    one reading gets "no later reading" and is described as such."""
    boards = committed_boards(digests_dir, today)
    if not boards:
        return ""
    first: Dict[str, Tuple[_dt.date, float, str, str]] = {}
    latest: Dict[str, Tuple[_dt.date, float]] = {}
    for d, lines in boards:
        for ln in lines:
            k = _key(str(ln["question"]))
            if k not in first:
                first[k] = (d, float(ln["prob"]), str(ln["venue"]), str(ln["question"]))
            else:
                latest[k] = (d, float(ln["prob"]))
    # Today's live board articles carry "NN% implied probability" in their text.
    for art in todays_articles or []:
        text = f"{art.get('title', '')}\n{art.get('content_text') or art.get('description') or ''}"
        for raw in text.splitlines():
            lm = _LINE_RE.match(raw.strip())
            if not lm:
                continue
            k = _key(lm.group("question"))
            if k in first:
                latest[k] = (today, float(lm.group("prob")))
    rows: List[str] = []
    for k, (d0, p0, venue, question) in first.items():
        if k in latest:
            d1, p1 = latest[k]
            delta = p1 - p0
            sign = "+" if delta > 0 else ""
            rows.append(f"- {question} ({venue}): {p0:g}% on {d0.strftime('%A')} → "
                        f"{p1:g}% on {d1.strftime('%A')} ({sign}{delta:g} points)")
        else:
            rows.append(f"- {question} ({venue}): {p0:g}% on {d0.strftime('%A')}; no later reading")
    return (
        "### THE WEEK'S BOARD DATA (instruction — do not include in output; Fridays only)\n"
        "Today's digest carries a section headed exactly `### The Week's Board`, placed after "
        "The Board. It is the show's scoring ritual: for each question below, one sentence "
        "saying what the price did over the week in points, with the venue. A question marked "
        "'no later reading' is described as having one reading this week — never as resolved. "
        "Say an outcome occurred ONLY when a news article above reports it; otherwise the "
        "price move is the whole fact. No recommendation, no view on which reading was right.\n"
        + "\n".join(rows)
    )
