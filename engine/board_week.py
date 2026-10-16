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
# Oct 11 2026: the committed digests write the Board as prose — "Which party
# wins the U.S. Senate: Democrats at a 62 percent implied probability, …;
# Kalshi; …" or "Will one party sweep both chambers…? On Kalshi, a
# Democratic sweep was priced at 61 cents, a 61 percent implied probability"
# — and _LINE_RE (``Question: NN% implied probability``) matched none of it,
# so the Friday Week's Board was empty on 10-02 and 10-09. The question is
# the text up to the first colon or question mark; the reading is the FIRST
# "NN% / NN percent implied probability" on the line (the leading outcome).
_DIGEST_QUESTION_RE = re.compile(r"^(?P<question>[^:?\n]{8,}?)[:?]")
_DIGEST_PROB_RE = re.compile(
    r"(?P<prob>\d{1,3}(?:\.\d+)?)\s*(?:%|percent)\s+implied probability", re.IGNORECASE)
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
        if lm:
            question, prob, rest_text = lm.group("question"), lm.group("prob"), lm.group("rest")
            outcome = ""
        else:
            pm = _DIGEST_PROB_RE.search(line)
            if not pm:
                continue
            question, outcome = _question_and_outcome(line[:pm.start()])
            if len(question) < 8:
                continue
            prob, rest_text = pm.group("prob"), line
        vm = _VENUE_RE.search(rest_text)
        out.append({
            "question": question.strip(),
            "outcome": outcome,
            "prob": float(prob),
            "venue": vm.group(1) if vm else "",
        })
    return out


#: Where a prose Board line's question ends. Oct 16 2026: the question used
#: to run to the first colon, and on a line with none before the price that
#: colon was the reading time ("read at 11:20 UTC"), so the question carried
#: the day's price and the same market was a new question every day — Ep024's
#: Week's Board read one ceasefire market twice as "one reading" and named no
#: outcome on 18 lines running.
_QUESTION_END_RE = re.compile(
    r":|\?|\s[—–]\s|,?\s+(?:is\s+|was\s+)?priced at\b|,\s+(?=(?:Yes|No)\b)")
_OUTCOME_TAIL_RE = re.compile(
    r"[\s,;—–-]*(?:\b(?:is|was)\s+)?(?:\bleading\b.*|\bpriced at\b.*|\bat\s+an?\b.*|\bat\s*$)",
    re.IGNORECASE | re.DOTALL)


def _question_and_outcome(head: str) -> Tuple[str, str]:
    """Split the text before a Board line's first price into the question
    and the outcome the price is for ("Yes", "the Democratic Party", "no
    Hormuz agreement"). The outcome is "" when the line names none."""
    head = (head or "").strip()
    m = _QUESTION_END_RE.search(head)
    if not m:
        return head.rstrip(" ,;:—–-"), ""
    question = head[:m.start()].strip()
    tail = head[m.start():]
    tail = re.sub(r"^\s*(?::|\?|[—–]|,)\s*", "", tail)
    outcome = _OUTCOME_TAIL_RE.sub("", tail).strip(" ,;:—–-")
    return question, " ".join(outcome.split()[:8])


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


_Q_STOP = frozenset("will the a an of in on by to for is be does do which who what when "
                    "wins win won winner continue continues through before after us u s".split())


def _q_tokens(question: str) -> frozenset:
    return frozenset(w for w in _key(question).split() if len(w) >= 3 and w not in _Q_STOP)


#: Two wordings of one market share at least this share of their key words
#: (Jaccard). The script rewrites the question daily: "Does the U.S.-Iran
#: ceasefire continue through October 31" and "US-Iran ceasefire continues
#: through October 31" are one market.
SAME_QUESTION_JACCARD = 0.6


def _same_market(a: Tuple[frozenset, str], b: Tuple[frozenset, str]) -> bool:
    (ta, va), (tb, vb) = a, b
    if va != vb or not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= SAME_QUESTION_JACCARD


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
    outcome: Dict[str, str] = {}
    markets: Dict[str, Tuple[frozenset, str]] = {}
    for d, lines in boards:
        for ln in lines:
            sig = (_q_tokens(str(ln["question"])), str(ln["venue"]))
            k = next((key for key, m in markets.items() if _same_market(m, sig)),
                     _key(str(ln["question"])))
            out_now = str(ln.get("outcome") or "")
            if k not in first:
                markets[k] = sig
                first[k] = (d, float(ln["prob"]), str(ln["venue"]), str(ln["question"]))
                outcome[k] = out_now
            elif not out_now or not outcome[k] or out_now.lower() == outcome[k].lower():
                # Only a reading of the SAME outcome is a price move; a
                # different leader is a different number, not a change.
                latest[k] = (d, float(ln["prob"]))
                outcome[k] = outcome[k] or out_now
    # Today's live board articles carry "NN% implied probability" in their text.
    for art in todays_articles or []:
        text = f"{art.get('title', '')}\n{art.get('content_text') or art.get('description') or ''}"
        for raw in text.splitlines():
            lm = _LINE_RE.match(raw.strip())
            if not lm:
                continue
            vm = _VENUE_RE.search(lm.group("rest") or "")
            sig = (_q_tokens(lm.group("question")), vm.group(1) if vm else "")
            k = next((key for key, m in markets.items() if _same_market(m, sig)), "")
            if k in first:
                latest[k] = (today, float(lm.group("prob")))
    rows: List[str] = []
    once: List[str] = []
    for k, (d0, p0, venue, question) in first.items():
        label = f" — {outcome[k]}" if outcome.get(k) else ""
        if k in latest:
            d1, p1 = latest[k]
            delta = p1 - p0
            sign = "+" if delta > 0 else ""
            rows.append(f"- {question}{label} ({venue}): {p0:g}% on {d0.strftime('%A')} → "
                        f"{p1:g}% on {d1.strftime('%A')} ({sign}{delta:g} points)")
        else:
            once.append(f"{question}{label} ({venue})")
    # Oct 16 2026: Ep024 spoke eighteen "one reading" questions in a row —
    # a percentage tape that scored nothing. A question read once this week
    # is counted, never read out one by one.
    tracked = ("\n".join(rows) if rows else
               "- No question was read on two days this week.")
    single = (f"\nRead once this week (count them in one sentence; do not list or price "
              f"them): {len(once)} — " + "; ".join(once)) if once else ""
    return (
        "### THE WEEK'S BOARD DATA (instruction — do not include in output; Fridays only)\n"
        "Today's digest carries a section headed exactly `### The Week's Board`, placed after "
        "The Board. It is the show's scoring ritual: for each TRACKED question below, one "
        "sentence saying what the price of the named outcome did over the week in points, "
        "with the venue and the outcome named. When no question was read twice, the section "
        "says so in one sentence. Say an outcome occurred ONLY when a news article above "
        "reports it; otherwise the price move is the whole fact. No recommendation, no view "
        "on which reading was right.\nTracked this week:\n"
        + tracked + single
    )
