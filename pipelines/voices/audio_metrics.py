"""Craft metrics measured from the audio, not estimated from a transcript
(Oct 21 2026 review, §7.4).

Every number here is computed from the per-speaker Whisper word timestamps
the post-interview step already produces for each track — the same words
``engine/story_breaks.py`` and the spoken-text gate read — plus the room's
own trace. No model call, no transcript line-start arithmetic. The old
``interruptions`` / ``dead_air_sec`` / ``repeated_questions`` estimates stay
beside these for a month of comparison (``metrics_basis`` says which kind a
row carries).

Why: the three faults guests actually name — pace, overlap, no reaction —
are timing phenomena, and the loop measured time from a transcript with
whole-second starts and no ends. Thirteen scorecards did not move while
every room's turn-taking was graded on a guess.

The eight measures and what each answers:

* ``overlap_sec`` / ``overlap_events`` — seconds where Mira's track and the
  guest's track both carry speech; the complaint in every word guests used.
* ``turn_gap_ms_*`` — guest speech end to Mira speech start, per turn.
  400–900 ms is conversation; under 300 is an interruption; over 3,000 is
  dead air she caused.
* ``mira_turn_sec_*`` — her turn length from her own track. 7.6 s is
  clipped; 50 s is a monologue.
* ``guest_words_per_answer_median`` and ``guest_words_trend`` — the honest
  measure of whether a question landed; a host who gets longer answers as
  the hour goes on is doing it right.
* ``self_answered_turns`` — a Mira turn with no guest speech since her
  previous turn.
* ``echo_open_rate`` — the share of her turns whose first four words appear
  in the guest's previous thirty; the tic with no banned-phrase list.
* ``closing_round_complete`` — from the scenario trace: every round
  question asked, one per turn, each followed by the guest.
* ``seams`` — session rotations and drops with guest speech within two
  seconds either side.
"""

from __future__ import annotations

import datetime as dt
import re
import statistics
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

#: A run of words on one track is one turn until a gap longer than this.
TURN_GAP_SEC = 1.0
#: A gap shorter than this between a guest's last word and Mira's first is
#: an interruption, not a reply (§7.4).
INTERRUPTION_MS = 300
#: ... and longer than this is dead air she caused.
DEAD_AIR_MS = 3000
#: Mira's turn opens on an echo when its first N words sit in the guest's
#: previous M words.
ECHO_OPEN_WORDS = 4
ECHO_LOOKBACK_WORDS = 30
#: A rotation or drop counts as a seam when the guest was speaking within
#: this many seconds either side of it.
SEAM_WINDOW_SEC = 2.0
#: Rounds are asked one per turn; the parent scenario traces each ask as
#: ``round: asked <n>/8: ...`` (Oct 21) or ``round: asked: <label>`` (Oct 19).
ROUND_QUESTIONS_DEFAULT = 8

_WORD_RE = re.compile(r"[^\W_]+(?:'[^\W_]+)?", re.UNICODE)


def _norm_words(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "")]


def _clean(words: Iterable[dict]) -> List[Tuple[float, float, str]]:
    """``(start, end, word)`` triples, sorted, with the unusable dropped."""
    out: List[Tuple[float, float, str]] = []
    for w in words or []:
        if not isinstance(w, dict):
            continue
        try:
            start = float(w.get("start"))
            end = float(w.get("end", start))
        except (TypeError, ValueError):
            continue
        if end < start:
            end = start
        text = str(w.get("word") or w.get("text") or "").strip()
        if not text:
            continue
        out.append((start, end, text))
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def turns(words: Iterable[dict], gap_sec: float = TURN_GAP_SEC) -> List[dict]:
    """Group one track's words into turns: ``{"start", "end", "words": [..]}``.

    A turn ends when the next word starts more than ``gap_sec`` after the
    previous word ends. Mid-sentence breaths are under a second; a real
    hand-over of the floor is not.
    """
    out: List[dict] = []
    for start, end, text in _clean(words):
        if out and start - out[-1]["end"] <= gap_sec:
            out[-1]["end"] = max(out[-1]["end"], end)
            out[-1]["words"].append(text)
        else:
            out.append({"start": start, "end": end, "words": [text]})
    return out


def _median(values: Sequence[float]) -> Optional[float]:
    vals = [float(v) for v in values if v is not None]
    return round(statistics.median(vals), 1) if vals else None


def _percentile(values: Sequence[float], pct: float) -> Optional[float]:
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return None
    if len(vals) == 1:
        return round(vals[0], 1)
    pos = (len(vals) - 1) * pct
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    return round(vals[lo] + (vals[hi] - vals[lo]) * (pos - lo), 1)


def _intervals(words: Iterable[dict]) -> List[Tuple[float, float]]:
    return [(t["start"], t["end"]) for t in turns(words)]


def overlap(a: Sequence[Tuple[float, float]],
            b: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Intervals where both speakers carry speech."""
    out: List[Tuple[float, float]] = []
    i = j = 0
    a = sorted(a)
    b = sorted(b)
    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])
        if end > start:
            out.append((round(start, 2), round(end, 2)))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def turn_gaps_ms(guest_turns: Sequence[dict], mira_turns: Sequence[dict]) -> List[int]:
    """For each Mira turn that follows guest speech, the time from the
    guest's last word to her first, in milliseconds (negative = she started
    before they stopped)."""
    gaps: List[int] = []
    for m in mira_turns:
        before = [g for g in guest_turns if g["start"] < m["start"]]
        if not before:
            continue
        last = max(before, key=lambda g: g["end"])
        # Only a reply to THAT guest turn counts: skip when another Mira
        # turn sat between them (she answered twice; see self-answered).
        if any(last["end"] <= o["start"] < m["start"] for o in mira_turns if o is not m):
            continue
        gaps.append(int(round((m["start"] - last["end"]) * 1000)))
    return gaps


def self_answered(guest_turns: Sequence[dict], mira_turns: Sequence[dict]) -> int:
    """Mira turns with no guest speech since her previous turn."""
    count = 0
    for prev, cur in zip(mira_turns, mira_turns[1:]):
        spoke = any(g["end"] > prev["end"] and g["start"] < cur["start"]
                    for g in guest_turns)
        if not spoke:
            count += 1
    return count


def echo_open_rate(guest_turns: Sequence[dict], mira_turns: Sequence[dict]) -> Optional[float]:
    """Share of Mira turns whose opening words were the guest's last."""
    if not mira_turns:
        return None
    echoes = 0
    judged = 0
    for m in mira_turns:
        before = [g for g in guest_turns if g["end"] <= m["start"] + 0.5]
        if not before:
            continue
        recent: List[str] = []
        for g in sorted(before, key=lambda g: g["end"], reverse=True):
            recent = _norm_words(" ".join(g["words"])) + recent
            if len(recent) >= ECHO_LOOKBACK_WORDS:
                break
        recent = recent[-ECHO_LOOKBACK_WORDS:]
        opening = _norm_words(" ".join(m["words"]))[:ECHO_OPEN_WORDS]
        if len(opening) < 2:
            continue
        judged += 1
        # An echo is the opening, in order, inside the guest's last words.
        window = " ".join(recent)
        if " ".join(opening) in window:
            echoes += 1
    return round(echoes / judged, 3) if judged else None


def guest_words_per_answer(guest_turns: Sequence[dict]) -> Tuple[Optional[float], Optional[float]]:
    """Median words per guest turn, and last-third median / first-third."""
    counts = [len(t["words"]) for t in guest_turns]
    if not counts:
        return None, None
    median = _median(counts)
    third = len(counts) // 3
    if third < 2:
        return median, None
    first = statistics.median(counts[:third])
    last = statistics.median(counts[-third:])
    trend = round(last / first, 2) if first else None
    return median, trend


# ---------------------------------------------------------------------------
# The trace: the closing round and the seams
# ---------------------------------------------------------------------------

_ROUND_ASKED = re.compile(r"^asked(?:\s+(\d+)/(\d+))?:?\s*(.*)$", re.I)
_ROUND_ANSWERED = re.compile(r"^answered(?:\s+(\d+)/(\d+))?", re.I)
# Oct 23 2026: the room's other round lines. "asked again" is a repeat (and,
# before the Oct 23 fix, her words carrying a handed question a turn late);
# "said late" is her words carrying a question after the room had handed her
# the next one; "her turn asked nothing" means the question just handed was
# not asked and goes again. Counted as asks they made a lagging round read
# 14 asks and a round that lost three questions read complete.
_ROUND_REPEAT = re.compile(r"^asked again\b", re.I)
_ROUND_OWN = re.compile(r"^asked on her own:\s*(.*)$", re.I)
_ROUND_LATE = re.compile(r"^said late\b", re.I)
_ROUND_REHAND = re.compile(r"^her turn asked (nothing|something else)", re.I)
_ROUND_OWN_WORDS = re.compile(r"\s*\(her own words\)\s*$", re.I)
_SEAM_RE = re.compile(r"(handing over to a fresh session|connection dropped|"
                      r"rescued after a dropped connection|session \d+ bridged)", re.I)


def _trace_time(event: dict) -> Optional[dt.datetime]:
    raw = event.get("t")
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def closing_round(trace: Optional[Sequence[dict]],
                  expected: int = ROUND_QUESTIONS_DEFAULT) -> Dict[str, Any]:
    """Was every round question asked, once, one per turn, and answered?

    Reads the room's ``round`` trace lines. With the Oct 21 scenario each
    ask is followed by ``answered n/8`` when the guest spoke; the Oct 19
    shape only has the asks, and there two asks with nothing between them
    are the one-per-turn relapse the lightning round kept producing.

    Oct 23 2026: a question is counted once however often it is handed
    (a turn that asked nothing hands it again), a question she asked of her
    own accord counts as asked, and the round is complete only with no
    repeat and nothing said late. Rehearsal 0ac88c67 read complete at 8/8
    while her words ran a question behind and three were never put to the
    guest; its only trace of that was three "said late" lines.
    """
    asked: List[str] = []
    answered: List[str] = []
    stacked = 0
    late = 0
    repeats = 0
    rehanded = 0
    saw_answered_lines = False
    awaiting_answer = False     # an ask with no "answered" line yet
    previous_was_ask = False    # the trace line just before this one
    for e in trace or []:
        if not isinstance(e, dict):
            continue
        kind = str(e.get("e") or "")
        detail = str(e.get("d") or "")
        if kind != "round":
            previous_was_ask = False
            continue
        if _ROUND_REPEAT.match(detail):
            repeats += 1
            previous_was_ask = False
            continue
        if _ROUND_LATE.match(detail):
            late += 1
            previous_was_ask = False
            continue
        if _ROUND_REHAND.match(detail):
            # The question just handed was not asked: it is handed again
            # when they finish, and that is not a second question stacked
            # on the first.
            rehanded += 1
            awaiting_answer = False
            previous_was_ask = False
            continue
        own = _ROUND_OWN.match(detail)
        if own:
            label = own.group(1).strip()
            if label and label not in asked:
                asked.append(label)
                answered.append(label)   # asked in conversation; the room skips it
            previous_was_ask = False
            continue
        m = _ROUND_ASKED.match(detail)
        if m:
            label = _ROUND_OWN_WORDS.sub("", (m.group(3) or "").strip()) or f"q{len(asked) + 1}"
            # Two asks with nothing between them, or an ask while the last
            # is still unanswered on a trace that does record answers: the
            # one-per-turn rule was broken.
            if previous_was_ask or (saw_answered_lines and awaiting_answer):
                stacked += 1
            if label not in asked:
                asked.append(label)
            awaiting_answer = True
            previous_was_ask = True
            continue
        previous_was_ask = False
        if _ROUND_ANSWERED.match(detail):
            saw_answered_lines = True
            if asked and awaiting_answer and asked[-1] not in answered:
                answered.append(asked[-1])
            awaiting_answer = False
    if not saw_answered_lines:
        # Oct 19 shape: no answered lines, and the room traces guest speech
        # only six times. Each ask that was not immediately followed by
        # another ask is taken as answered; the stacked ones were not.
        answered = asked[: max(0, len(asked) - stacked)]
    complete = (len(asked) >= expected and stacked == 0 and late == 0
                and repeats == 0 and len(answered) >= len(asked))
    return {"closing_round_complete": bool(asked) and complete,
            "round_asked": len(asked), "round_stacked": stacked,
            "round_answered": len(answered), "round_late": late,
            "round_repeats": repeats, "round_rehanded": rehanded}


def seams(trace: Optional[Sequence[dict]], guest_turns: Sequence[dict],
          room_start: Optional[dt.datetime] = None,
          window_sec: float = SEAM_WINDOW_SEC) -> Dict[str, Any]:
    """Rotations and drops that landed inside the guest's speech.

    The trace is wall-clock; the words are on the room clock, whose zero is
    the first trace line (``room: opened``) unless ``room_start`` is given.
    """
    events: List[Tuple[float, str]] = []
    t0 = room_start
    for e in trace or []:
        if not isinstance(e, dict):
            continue
        when = _trace_time(e)
        if when is None:
            continue
        if t0 is None:
            t0 = when
        detail = str(e.get("d") or "")
        if str(e.get("e")) == "grok" and _SEAM_RE.search(detail):
            events.append(((when - t0).total_seconds(), detail))
    inside = 0
    for at, _detail in events:
        if any(g["start"] - window_sec <= at <= g["end"] + window_sec for g in guest_turns):
            inside += 1
    return {"seams": inside, "seam_candidates": len(events)}


# ---------------------------------------------------------------------------
# Everything at once
# ---------------------------------------------------------------------------

def measure_audio(words_by_role: Dict[str, List[dict]],
                  trace: Optional[List[dict]] = None,
                  round_questions: Optional[List[str]] = None,
                  transcript: str = "",
                  room_start: Optional[dt.datetime] = None) -> Dict[str, Any]:
    """The eight audio measures from per-speaker word timestamps.

    ``words_by_role`` maps ``"mira"`` / ``"guest"`` / ``"host"`` to Whisper
    word dicts (``start``, ``end``, ``word``) on the room clock. A missing
    guest or Mira track gives ``None`` for every measure that needs it, and
    ``metrics_basis`` says so — a number this module cannot vouch for is
    never written as zero.
    """
    mira_words = list((words_by_role or {}).get("mira") or [])
    guest_words = list((words_by_role or {}).get("guest") or [])
    mira_turns = turns(mira_words)
    guest_turns = turns(guest_words)
    expected = len(round_questions) if round_questions else ROUND_QUESTIONS_DEFAULT

    out: Dict[str, Any] = {
        "overlap_sec": None, "overlap_events": None, "overlap_spans": [],
        "turn_gap_ms_median": None, "turn_gap_ms_p10": None, "turn_gap_ms_p90": None,
        "turn_gaps_ms": [],
        "mira_turn_sec_median": None, "mira_turn_sec_p90": None,
        "guest_words_per_answer_median": None, "guest_words_trend": None,
        "self_answered_turns": None, "echo_open_rate": None,
        "closing_round_complete": None, "seams": None,
        "metrics_basis": "audio" if (mira_turns and guest_turns) else "none",
        "mira_turns_audio": len(mira_turns), "guest_turns_audio": len(guest_turns),
    }
    if mira_turns:
        lengths = [t["end"] - t["start"] for t in mira_turns]
        out["mira_turn_sec_median"] = _median(lengths)
        out["mira_turn_sec_p90"] = _percentile(lengths, 0.9)
    if guest_turns:
        median, trend = guest_words_per_answer(guest_turns)
        out["guest_words_per_answer_median"] = median
        out["guest_words_trend"] = trend
    if mira_turns and guest_turns:
        spans = overlap(_intervals(mira_words), _intervals(guest_words))
        out["overlap_spans"] = [list(s) for s in spans]
        out["overlap_events"] = len(spans)
        out["overlap_sec"] = round(sum(e - s for s, e in spans), 1)
        gaps = turn_gaps_ms(guest_turns, mira_turns)
        out["turn_gaps_ms"] = gaps
        out["turn_gap_ms_median"] = _median(gaps)
        out["turn_gap_ms_p10"] = _percentile(gaps, 0.1)
        out["turn_gap_ms_p90"] = _percentile(gaps, 0.9)
        out["self_answered_turns"] = self_answered(guest_turns, mira_turns)
        out["echo_open_rate"] = echo_open_rate(guest_turns, mira_turns)
        out["interruptions_audio"] = sum(1 for g in gaps if g < INTERRUPTION_MS)
        out["dead_air_turns_audio"] = sum(1 for g in gaps if g > DEAD_AIR_MS)
    if trace:
        out.update(closing_round(trace, expected))
        out.update(seams(trace, guest_turns, room_start=room_start))
    return out


#: Columns of ``episode_metrics`` this module fills (the migration of the
#: same date adds them). Everything else above rides in ``notes``.
COLUMNS = (
    "overlap_sec", "overlap_events", "turn_gap_ms_median", "turn_gap_ms_p10",
    "turn_gap_ms_p90", "mira_turn_sec_median", "mira_turn_sec_p90",
    "guest_words_per_answer_median", "guest_words_trend", "self_answered_turns",
    "echo_open_rate", "closing_round_complete", "seams", "metrics_basis",
)


def columns(measured: Dict[str, Any]) -> Dict[str, Any]:
    """The subset of ``measure_audio``'s result that is a table column."""
    return {k: measured.get(k) for k in COLUMNS if k in measured}


def notes(measured: Dict[str, Any]) -> Dict[str, Any]:
    """The rest, for ``episode_metrics.notes``."""
    return {k: v for k, v in measured.items() if k not in COLUMNS}


# ---------------------------------------------------------------------------
# The targets a lesson is retired against (§7.7)
# ---------------------------------------------------------------------------

#: ``metric -> (direction, threshold)``: a room is "green" on a metric when
#: its value is on the right side of the target. ``up`` means higher is
#: better. These are the review's own targets, kept in one place so the
#: weekly adoption and the snapshot agree.
TARGETS: Dict[str, Tuple[str, float]] = {
    "overlap_events_per_10min": ("down", 1.0),
    "self_answered_turns": ("down", 0.0),
    "mira_turn_sec_median_low": ("up", 12.0),
    "mira_turn_sec_median_high": ("down", 20.0),
    "echo_open_rate": ("down", 0.10),
    "guest_words_trend": ("up", 1.0),
    "seams": ("down", 0.0),
}


def is_green(metric: str, row: Dict[str, Any]) -> Optional[bool]:
    """Whether one room meets the target for ``metric``; ``None`` when the
    room did not measure it (an unmeasured room is never green)."""
    value: Any
    if metric == "overlap_events_per_10min":
        events = row.get("overlap_events")
        duration = row.get("duration_sec")
        if events is None or not duration:
            return None
        value = float(events) / (float(duration) / 600.0)
        return value <= TARGETS[metric][1]
    if metric == "mira_turn_sec_median":
        value = row.get("mira_turn_sec_median")
        if value is None:
            return None
        return TARGETS["mira_turn_sec_median_low"][1] <= float(value) <= TARGETS["mira_turn_sec_median_high"][1]
    if metric == "closing_round_complete":
        value = row.get(metric)
        return None if value is None else bool(value)
    if metric not in TARGETS:
        return None
    value = row.get(metric)
    if value is None:
        return None
    direction, threshold = TARGETS[metric]
    return float(value) >= threshold if direction == "up" else float(value) <= threshold
