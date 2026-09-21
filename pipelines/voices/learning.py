"""The show gets better on purpose (Sept 10 2026).

Every interview leaves two things behind besides an episode:

* ``episode_metrics`` — a handful of numbers about the craft, so "Mira is
  improving" is a claim that can be checked rather than a feeling;
* ``show_lessons`` — standing instructions proposed by a producer's pass over
  the tape, which Patrick promotes or discards at gate 1. Active lessons are
  appended to Mira's system prompt for every later interview on that show.

Sept 21 2026: the loop closes itself. Lessons used to land as proposals for
Patrick to promote at gate 1, and eight of them were still sitting there
unread while the same faults recurred — a queue is not a learning loop. The
grading pass now ADOPTS what it decides, retires what it has outgrown, and
tells Patrick what it did. Two things keep the old safety without the queue:
the grader is shown the instructions Mira already carries and told not to
restate them, so a relapse cannot multiply into three copies of one lesson;
and every adoption is reversible from the same triage page that used to
approve it, because a bad instruction should cost one click to remove rather
than a deploy.
"""

from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List, Optional, Tuple

import datetime as dt

from common import cohost_label, logger, sb_insert, sb_select, sb_update


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

LESSON_CATEGORIES = {"pacing", "questions", "interruption", "listening", "tone"}
MAX_ACTIVE_LESSONS = 12          # Mira's prompt is not a filing cabinet
MAX_RETIRED_PHRASES = 20         # the same, for her verbal tics
PHRASE_MAX_WORDS = 12            # an acknowledgment, not a sentence of substance
DEAD_AIR_SEC = 4.0
REPEAT_RATIO = 0.82              # difflib ratio at which two questions are "the same"
# Two lessons are the same instruction in different words. Measured against
# the eight real proposals sitting in the queue on Sept 21 2026: the one true
# duplicate pair scored 0.80 / 0.89 and the closest genuinely-different pair
# scored 0.43 / 0.30, so both thresholds sit in open space.
SAME_LESSON_RATIO = 0.72         # difflib ratio on the whole sentence
SAME_LESSON_WORDS = 0.75         # shared share of the shorter sentence's words

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
    # Sept 18 2026. Retiring the instances did nothing: seventy "That's a
    # [adjective] [noun]" lines across six episodes, a fresh adjective each
    # time, every one of them technically new. The SHAPE is what repeats,
    # so the shape is what gets named, once, with the count that earned it.
    shapes: dict = {}
    singles = []
    for phrase in phrases:
        shape = phrase_shape(phrase)
        if shape:
            shapes[shape] = shapes.get(shape, 0) + 1
        else:
            singles.append(phrase)
    out = ["\n\nALREADY USED ON THIS SHOW"]
    for shape, n in sorted(shapes.items(), key=lambda kv: -kv[1]):
        out.append(f'The shape "{shape}" is retired outright: you have opened '
                   f'{n} replies with it on this show, changing only the '
                   f'adjective, which is not variety. Never open a reply that way '
                   f'again, whatever the adjective.')
    if singles:
        out.append("You have said each of these on a previous episode. They are "
                   "retired. Do not say them again, and do not say a near-variant "
                   "of them:\n" + "\n".join(f'- "{p}"' for p in singles))
    return "\n".join(out) + "\n"


_SHAPES = (
    (re.compile(r"(?i)^that'?s (a|an) "), "That's a ..."),
    (re.compile(r"(?i)^what (a|an) "), "What a ..."),
    (re.compile(r"(?i)^i love (that|how|the) "), "I love that ..."),
)


def phrase_shape(phrase: str) -> str:
    """The reflex a phrase is an instance of, or "" when it is just itself."""
    for pattern, label in _SHAPES:
        if pattern.match(phrase.strip()):
            return label
    return ""


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


def _already_says_it(lesson: str, existing: List[str]) -> bool:
    """Is this lesson the same instruction as one she already carries?

    A relapse reads to the grader as a fresh fault, so the same sentence
    arrives again in slightly different words. Adopting it twice spends two
    of a dozen slots saying one thing.
    """
    a = re.sub(r"[^a-z ]", "", (lesson or "").lower()).strip()
    if not a:
        return False
    a_words = set(a.split())
    for other in existing:
        b = re.sub(r"[^a-z ]", "", (other or "").lower()).strip()
        if not b:
            continue
        if difflib.SequenceMatcher(None, a, b).ratio() >= SAME_LESSON_RATIO:
            return True
        b_words = set(b.split())
        shared = len(a_words & b_words) / max(1, min(len(a_words), len(b_words)))
        if shared >= SAME_LESSON_WORDS:
            return True
    return False


# The closing round asks every guest what they would change about how Mira
# did this. That answer is the only outside opinion in the whole loop, so it
# is pulled out of the tape by hand rather than left for the grader to find.
_FEEDBACK_CUE = re.compile(
    r"(change one thing about how I|what would you change|being interviewed by an AI"
    r"|irritating|would not have said to a person|wouldn't have said to a person)",
    re.I)


def guest_feedback(transcript: str, guest_label: str) -> str:
    """What the guest said when asked how the interview itself went.

    Returns the guest's answers that follow Mira's feedback questions, or ""
    when she never asked — which is itself worth knowing, and the grader is
    told so.
    """
    rows = parse_transcript(transcript)
    if not rows or not guest_label:
        return ""
    out: List[str] = []
    for i, (_, speaker, text) in enumerate(rows):
        if speaker.lower() == guest_label.lower() or not _FEEDBACK_CUE.search(text):
            continue
        # Take the guest's next few lines; an answer to this question is
        # usually two or three sentences and often starts hesitantly.
        said: List[str] = []
        for _, spk, later in rows[i + 1:]:
            if spk.lower() != guest_label.lower():
                if said:
                    break
                continue
            said.append(later)
            if len(" ".join(said).split()) > 90:
                break
        if said:
            out.append(f"Asked: {text.strip()}\nThey said: {' '.join(said).strip()}")
    return "\n\n".join(out[:3])


def retire_lessons(ids: List[str], why: str = "superseded") -> int:
    """Move standing instructions out of Mira's prompt, keeping the record."""
    done = 0
    for lesson_id in ids or []:
        lesson_id = str(lesson_id or "").strip()
        if not lesson_id:
            continue
        try:
            sb_update("show_lessons", f"id=eq.{lesson_id}",
                      {"status": "retired", "decided_at": _now(),
                       "decided_by": "mira", "decision_note": why[:200]})
            done += 1
        except Exception:  # noqa: BLE001 — never block an episode on this
            logger.exception("retiring lesson %s failed (non-fatal)", lesson_id)
    return done


def adopt_lessons(show_slug: str, interview_id: str,
                  lessons: List[dict]) -> List[dict]:
    """Put a grading pass's lessons straight into Mira's standing
    instructions, and return the ones that took.

    Skips anything she already carries in other words, and once the show is
    at :data:`MAX_ACTIVE_LESSONS` retires its oldest decision to make room,
    so the newest instruction is never the one silently left out of the
    prompt.
    """
    current = active_lessons(show_slug)
    existing = [str(r.get("lesson") or "") for r in current]
    adopted: List[dict] = []
    for item in lessons or []:
        if not isinstance(item, dict):
            continue
        lesson = str(item.get("lesson") or "").strip()
        if not lesson:
            continue
        if _already_says_it(lesson, existing):
            logger.info("lesson already carried, not adopted again: %s", lesson)
            continue
        category = str(item.get("category") or "other").strip().lower()
        if category not in LESSON_CATEGORIES:
            category = "other"
        room = MAX_ACTIVE_LESSONS - (len(current) + len(adopted))
        if room <= 0:
            oldest = sorted(current + adopted,
                            key=lambda r: str(r.get("decided_at") or ""))[:1]
            if oldest:
                retire_lessons([str(oldest[0].get("id"))],
                               "made room for a newer lesson")
                current = [r for r in current
                           if str(r.get("id")) != str(oldest[0].get("id"))]
        try:
            row = sb_insert("show_lessons", {
                "show": show_slug,
                "interview_id": interview_id,
                "category": category,
                "lesson": lesson[:400],
                "evidence": str(item.get("evidence") or "")[:400] or None,
                "status": "active",
                "decided_at": _now(),
                "decided_by": "mira",
                "decision_note": f"adopted automatically ({item.get('confidence') or 'medium'} confidence)",
            })
            adopted.append(row)
            existing.append(lesson)
        except Exception:  # noqa: BLE001
            logger.exception("adopting lesson failed (non-fatal): %s", lesson)
    return adopted


def save_grade(show_slug: str, interview_id: str, graded: Dict[str, Any],
               adopted: List[dict], retired: int) -> Optional[dict]:
    """Record the scorecard so "Mira is getting better" is checkable."""
    grades = graded.get("grades") if isinstance(graded, dict) else {}
    grades = grades if isinstance(grades, dict) else {}

    def score(key: str) -> Optional[float]:
        try:
            value = float(grades.get(key))
        except (TypeError, ValueError):
            return None
        return round(min(10.0, max(0.0, value)), 1)

    row = {
        "interview_id": interview_id,
        "show": show_slug,
        "overall": score("overall"),
        "listening": score("listening"),
        "questions": score("questions"),
        "pacing": score("pacing"),
        "turn_taking": score("turn_taking"),
        "warmth": score("warmth"),
        "why": str(graded.get("grade_why") or "")[:1200] or None,
        "worked": [str(w)[:300] for w in (graded.get("worked") or [])][:3],
        "lessons_adopted": len(adopted),
        "lessons_retired": retired,
        "ask_the_guest": str(graded.get("ask_the_guest") or "")[:400] or None,
    }
    try:
        return (sb_update("episode_grades", f"interview_id=eq.{interview_id}", row)
                or [sb_insert("episode_grades", row)])[0]
    except Exception:  # noqa: BLE001 — a grade never blocks an episode
        logger.exception("episode_grades write failed (non-fatal)")
        return None


def grade_trend(show_slug: str, limit: int = 6) -> List[dict]:
    """The last few overall scores for this show, newest first."""
    try:
        return sb_select("episode_grades",
                         f"show=eq.{show_slug}&order=created_at.desc"
                         f"&limit={limit}&select=overall,created_at,interview_id") or []
    except Exception:  # noqa: BLE001
        logger.exception("grade trend unavailable (non-fatal)")
        return []


def lessons_for_prompt(show_slug: str) -> str:
    """The active instructions with their ids, for the grading prompt."""
    rows = active_lessons(show_slug)
    if not rows:
        return "(none yet — this is the first graded interview on this show)"
    return "\n".join(
        f"- [{r.get('id')}] ({r.get('category') or 'other'}) {r.get('lesson')}"
        for r in rows)


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
        "\nWHAT EARLIER INTERVIEWS TAUGHT YOU. These are standing corrections "
        "from tape of your own past episodes, reviewed and approved by your "
        "producer. They outrank everything below and apply to this interview:\n"
        + lines + "\n"
    )


def improvement_summary(show_slug: str, interview_id: str) -> str:
    """The scorecard and what Mira changed about herself, for Patrick's email.

    Sept 15 2026: the retro had been running since Matt Davis and its output
    was only ever visible to someone who went looking in the database, so it
    moved next to the episode. Sept 21 2026: it no longer asks for anything.
    The lessons here are already in force; this is the record of a decision,
    and the triage page is where Patrick undoes one he disagrees with.
    """
    try:
        adopted = sb_select(
            "show_lessons",
            f"show=eq.{show_slug}&interview_id=eq.{interview_id}"
            f"&status=eq.active&order=created_at.desc&limit=8") or []
        proposed = sb_select(
            "show_lessons",
            f"show=eq.{show_slug}&interview_id=eq.{interview_id}"
            f"&status=eq.proposed&order=created_at.desc&limit=8") or []
        metrics = sb_select("episode_metrics",
                            f"interview_id=eq.{interview_id}&limit=1") or []
        grades = sb_select("episode_grades",
                           f"interview_id=eq.{interview_id}&limit=1") or []
    except Exception:  # noqa: BLE001
        logger.exception("improvement summary unavailable (non-fatal)")
        return ""
    proposed = adopted + proposed
    if not proposed and not metrics and not grades:
        return ""

    parts = ["<h3 style='margin:18px 0 6px'>What Mira took from this one</h3>"]
    if grades:
        g = grades[0]
        scores = " &middot; ".join(
            f"{label} {g[key]}" for label, key in (
                ("listening", "listening"), ("questions", "questions"),
                ("pacing", "pacing"), ("turn-taking", "turn_taking"),
                ("warmth", "warmth"))
            if g.get(key) is not None)
        overall = g.get("overall")
        parts.append(
            "<p style='margin:0 0 4px'><b>She graded this one "
            + (f"{overall} out of ten" if overall is not None else "ungraded")
            + ".</b>" + (f" {g['why']}" if g.get("why") else "") + "</p>")
        if scores:
            parts.append(f"<p style='color:#555;margin:0 0 8px'>{scores}</p>")
        worked = [str(w) for w in (g.get("worked") or []) if str(w).strip()]
        if worked:
            parts.append("<p style='color:#555;margin:0 0 8px'>Worked: "
                         + "; ".join(worked) + "</p>")
    if metrics:
        m = metrics[0]
        bits = []
        for label, key, suffix in (
                ("interruptions", "interruptions", ""),
                ("repeated questions", "repeated_questions", ""),
                ("her share of the talking", "host_talk_share", "%"),
                ("questions asked", "questions", "")):
            value = m.get(key)
            if value is None:
                continue
            if suffix == "%":
                value = f"{round(float(value) * 100)}"
            bits.append(f"{label}: {value}{suffix}")
        if bits:
            parts.append("<p style='color:#555'>" + " &middot; ".join(bits) + "</p>")
    if proposed:
        live = [r for r in proposed if r.get("status") == "active"]
        parts.append(
            "<p>These are now standing instructions for every later interview "
            "on this show. They are already in force — nothing is waiting on "
            "you. If one of them is wrong, remove it on the triage page and "
            "she stops carrying it:</p><ul>"
            if live else
            "<p>Left for you to decide on:</p><ul>")
        for row in proposed:
            lesson = (row.get("lesson") or "").strip()
            why = (row.get("evidence") or "").strip()
            mark = "" if row.get("status") == "active" else " <i>(awaiting you)</i>"
            parts.append(f"<li>{lesson}{mark}"
                         + (f"<br><span style='color:#777;font-size:90%'>{why}</span>"
                            if why else "")
                         + "</li>")
        parts.append("</ul>")
    else:
        parts.append("<p>Nothing to change from this one, which is the right "
                     "answer for a clean interview.</p>")
    return "".join(parts)
