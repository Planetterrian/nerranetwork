"""The show gets better on purpose (Sept 10 2026).

Every interview leaves two things behind besides an episode:

* ``episode_metrics`` — a handful of numbers about the craft, so "Mira is
  improving" is a claim that can be checked rather than a feeling;
* ``show_lessons`` — standing instructions proposed by a producer's pass over
  the tape, which Patrick promotes or discards at gate 1. Active lessons are
  appended to Mira's system prompt for every later interview on that show.

Deliberately a human-in-the-loop design. A host that rewrites its own
instructions unsupervised drifts, and the drift is invisible until an episode
is bad. Proposing costs nothing; promoting is one click.
"""

from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List, Optional, Tuple

from common import cohost_label, logger, sb_insert, sb_select, sb_update

LESSON_CATEGORIES = {"pacing", "questions", "interruption", "listening", "tone"}
MAX_ACTIVE_LESSONS = 12          # Mira's prompt is not a filing cabinet
MAX_RETIRED_PHRASES = 20         # the same, for her verbal tics
PHRASE_MAX_WORDS = 12            # an acknowledgment, not a sentence of substance
DEAD_AIR_SEC = 4.0
REPEAT_RATIO = 0.82              # difflib ratio at which two questions are "the same"

LINE_RE = re.compile(r"^\[(\d{1,2}):(\d{2})\]\s*([^:]+):\s*(.*)$")


def parse_transcript(transcript: str) -> List[Tuple[float, str, str]]:
    """``[MM:SS] Speaker: text`` lines → (seconds, speaker, text)."""
    out: List[Tuple[float, str, str]] = []
    for line in (transcript or "").splitlines():
        m = LINE_RE.match(line.strip())
        if m:
            out.append((int(m.group(1)) * 60 + int(m.group(2)),
                        m.group(3).strip(), m.group(4).strip()))
    return out


def _questions(texts: List[str]) -> List[str]:
    qs: List[str] = []
    for t in texts:
        for sentence in re.split(r"(?<=[.?!])\s+", t):
            s = sentence.strip()
            if s.endswith("?") and len(s.split()) >= 4:
                qs.append(s.lower())
    return qs


def count_repeated_questions(host_texts: List[str]) -> int:
    qs = _questions(host_texts)
    repeats = 0
    for i, q in enumerate(qs):
        for earlier in qs[:i]:
            if difflib.SequenceMatcher(None, q, earlier).ratio() >= REPEAT_RATIO:
                repeats += 1
                break
    return repeats


def count_interruptions(rows: List[Tuple[float, str, str]], host_label: str,
                        guest_label: str) -> Optional[int]:
    """Times the host started talking while the guest was still going.

    The transcript carries a start time per line but not an end, so a line's
    span is estimated from its own word count at the host's measured pace. A
    host line that starts well inside a guest line's estimated span, and is
    not the guest trailing off, is an interruption. Approximate by
    construction — it is a trend line, not a verdict on any one moment.
    """
    if not guest_label:
        return None
    pace = 2.4          # words per second
    guest = [(t, len(txt.split()) / pace) for t, spk, txt in rows
             if spk.lower() == guest_label.lower()]
    if not guest:
        return None
    host_starts = [t for t, spk, _ in rows if spk.lower() == host_label.lower()]
    hits = 0
    for start in host_starts:
        for g_start, g_len in guest:
            if g_len < 20 and g_start + 2.0 < start < g_start + g_len - 1.0:
                hits += 1
                break
    return hits


def host_formulas(rows: List[Tuple[float, str, str]], host_label: str) -> List[str]:
    """The host's short acknowledgment lines — the reflexes, not the questions.

    Mira reaches for one shape over and over ("That's a crisp way to put it",
    "That's a bold direction", "That's a meaningful backstop"). Three in an
    episode and she sounds like a form. These are collected so later
    interviews can be told not to use them again.
    """
    out: List[str] = []
    for _, speaker, text in rows:
        if speaker.lower() != host_label.lower():
            continue
        for sentence in re.split(r"(?<=[.?!])\s+", text):
            line = sentence.strip()
            if not line or line.endswith("?"):
                continue                       # a question is not a reflex
            words = line.split()
            if 2 <= len(words) <= PHRASE_MAX_WORDS:
                out.append(line.rstrip(".!").strip())
    # Keep the ones that read as formulas rather than as content.
    formulaic = [p for p in out
                 if re.match(r"(?i)^(that'?s|what a|i love|good|nice|fair|"
                             r"understood|got it|makes sense|interesting)\b", p)]
    seen: dict = {}
    for phrase in formulaic:
        seen[phrase.lower()] = phrase
    return list(seen.values())


def save_host_phrases(show_slug: str, interview_id: str, phrases: List[str]) -> int:
    saved = 0
    for phrase in phrases[:MAX_RETIRED_PHRASES]:
        try:
            sb_insert("host_phrases", {"show": show_slug, "interview_id": interview_id,
                                       "phrase": phrase[:200]})
            saved += 1
        except Exception:  # noqa: BLE001 — never block an episode on a tic
            logger.exception("host_phrases insert failed (non-fatal)")
    return saved


def variety_block(show_slug: str) -> str:
    """The phrases Mira has already used on this show, so she stops reusing
    them. Empty for a show with no history, so a first episode reads exactly
    as it did before."""
    try:
        rows = sb_select("host_phrases",
                         f"show=eq.{show_slug}&order=created_at.desc"
                         f"&limit={MAX_RETIRED_PHRASES}")
    except Exception:  # noqa: BLE001
        logger.exception("host phrases unavailable (non-fatal)")
        return ""
    phrases = []
    for row in rows or []:
        phrase = (row.get("phrase") or "").strip()
        if phrase and phrase.lower() not in {p.lower() for p in phrases}:
            phrases.append(phrase)
    if not phrases:
        return ""
    return ("\n\nALREADY USED ON THIS SHOW\n"
            "You have said each of these on a previous episode. They are "
            "retired. Do not say them again, and do not say a near-variant "
            "of them:\n" + "\n".join(f'- "{p}"' for p in phrases) + "\n")


def session_events_summary(run: dict, limit: int = 60) -> str:
    """The scenario trace as plain lines, for the retro prompt."""
    trace = run.get("scenario_trace") or []
    lines = [f"{(e.get('t') or '')[11:19]}  {e.get('e')}: {e.get('d')}"
             for e in trace if isinstance(e, dict)]
    if len(lines) > limit:
        head, tail = lines[: limit // 2], lines[-(limit // 2):]
        lines = head + [f"... {len(lines) - limit} more events ..."] + tail
    return "\n".join(lines) or "(no session events recorded)"


def measure(run: dict, transcript: str, host_label: str = "Mira",
            guest_label: Optional[str] = None) -> Dict[str, Any]:
    """Craft metrics from the labelled transcript plus the session trace.

    Talk share is measured in WORDS, not seconds: the transcript carries a
    start time per line but not an end, so seconds would be a guess dressed
    up as a measurement.
    """
    rows = parse_transcript(transcript)
    speakers = {s for _, s, _ in rows}
    known = {host_label.lower(), "patrick", "mira/patrick", cohost_label().lower()}
    # Sept 12 2026: talk share came back as 0.0 for the Hogan Shrum episode
    # because the caller passed the guest's first name while the transcript
    # labelled him GUEST. Take the name if it is there, else whatever speaker
    # is left, else the literal GUEST label older transcripts use.
    wanted = (guest_label or "").lower()
    match = next((s for s in speakers if s.lower() == wanted), None)
    if match is None:
        others = [s for s in speakers if s.lower() not in known]
        match = others[0] if others else ""
    guest_label = match

    host_rows = [r for r in rows if r[1].lower() == host_label.lower()]
    words: Dict[str, int] = {}
    for _, spk, text in rows:
        words[spk] = words.get(spk, 0) + len(text.split())
    total_words = sum(words.values()) or 1

    gaps = [b[0] - a[0] for a, b in zip(rows, rows[1:])]
    host_turn_lengths = [b[0] - a[0] for a, b in zip(host_rows, host_rows[1:])
                         if 0 < (b[0] - a[0]) < 300]

    trace = run.get("scenario_trace") or []
    descr = [str(e.get("d", "")) for e in trace if isinstance(e, dict)]
    sessions = sum(1 for d in descr if "bridged" in d) + 1
    drops = sum(1 for d in descr if "connection dropped" in d)

    return {
        "interview_run_id": run.get("id"),
        "duration_sec": run.get("duration_sec"),
        "guest_talk_share": round(words.get(guest_label, 0) / total_words, 3),
        "mira_turns": len(host_rows),
        "mira_mean_turn_sec": (round(sum(host_turn_lengths) / len(host_turn_lengths), 1)
                               if host_turn_lengths else None),
        "interruptions": count_interruptions(rows, host_label, guest_label),
        "repeated_questions": count_repeated_questions([t for _, _, t in host_rows]),
        "dead_air_sec": round(sum(g - DEAD_AIR_SEC for g in gaps if g > DEAD_AIR_SEC), 1),
        "agent_sessions": sessions,
        "drops": drops,
        "notes": {"talk_share_basis": "words", "word_counts": words,
                  "interruption_basis": "estimated line spans",
                  "host_label": host_label, "guest_label": guest_label},
    }


def save_metrics(interview_id: str, metrics: Dict[str, Any]) -> None:
    row = dict(metrics)
    row["interview_id"] = interview_id
    try:
        # interview_id is the primary key; a re-run replaces the measurement.
        sb_update("episode_metrics", f"interview_id=eq.{interview_id}", row) \
            or sb_insert("episode_metrics", row)
    except Exception:          # noqa: BLE001 — metrics never block an episode
        logger.exception("episode_metrics insert failed (non-fatal)")


def save_proposed_lessons(show_slug: str, interview_id: str,
                          lessons: List[dict]) -> int:
    """Store a retro pass's output as PROPOSED lessons. Nothing reaches Mira
    until a human promotes it."""
    saved = 0
    for item in lessons or []:
        if not isinstance(item, dict):
            continue
        lesson = str(item.get("lesson") or "").strip()
        category = str(item.get("category") or "other").strip().lower()
        if not lesson:
            continue
        if category not in LESSON_CATEGORIES:
            category = "other"
        try:
            sb_insert("show_lessons", {
                "show": show_slug,
                "interview_id": interview_id,
                "category": category,
                "lesson": lesson[:400],
                "evidence": str(item.get("evidence") or "")[:400] or None,
                "status": "proposed",
            })
            saved += 1
        except Exception:  # noqa: BLE001
            logger.exception("show_lessons insert failed (non-fatal)")
    return saved


def active_lessons(show_slug: str) -> List[dict]:
    try:
        rows = sb_select("show_lessons",
                         f"show=eq.{show_slug}&status=eq.active"
                         f"&order=decided_at.desc&limit={MAX_ACTIVE_LESSONS}")
        return rows or []
    except Exception:  # noqa: BLE001 — never block an interview on this
        logger.exception("active lessons unavailable (non-fatal)")
        return []


def lessons_block(show_slug: str) -> str:
    """The block appended to Mira's system prompt. Empty when nothing has
    been promoted, so a fresh show reads exactly as it did before."""
    rows = active_lessons(show_slug)
    if not rows:
        return ""
    lines = "\n".join(f"- {r['lesson']}" for r in rows if r.get("lesson"))
    if not lines:
        return ""
    return (
        "\n\nWHAT EARLIER INTERVIEWS TAUGHT YOU\n"
        "These are standing corrections from tape of your own past episodes, "
        "reviewed and approved by your producer. They outrank your habits and "
        "apply to this interview:\n" + lines + "\n"
    )
