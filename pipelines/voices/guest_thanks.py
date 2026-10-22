"""What a guest hears from Mira in the hour after the room ends (Oct 21 2026).

Between the recording ending and gate 1 there were two to ten days of
silence. The guest had just given an hour, often their first conversation
with an AI host, and the next thing they received was a transcript to
approve. This closes that gap: as soon as the transcript is final, Mira
writes to say thank you, names three moments from the hour in the guest's
own words, says when the edit will reach them and what they will be asked to
do with it.

Rules:

* **The moments are the guest's own lines, verbatim**, never Mira's and never
  paraphrased (``memorable_moments``). They are chosen deterministically so a
  re-run sends the same note and nothing is invented.
* **Only answers, only safe ones** (Oct 22 2026, Stan Lewis). The first
  version took the guest's longest lines that carried a number or a name,
  which is exactly what a phone number, a date of birth and a medical
  history look like. Stan took a call from the VA in the middle of the hour,
  and two of the three "things you said that I will remember", sent to him
  with Patrick and Dan copied, were his side of that call: a scheduling
  argument and his hyperglycemia. A moment is now a complete sentence or two
  from his answer to one of Mira's questions; nothing with a health, legal,
  money or personal-identifier word or a long number in it is ever quoted;
  and with fewer than two safe moments the note simply thanks him.
* **Once.** ``editorial_packages.thanks_sent_at`` is stamped and read first.
* **Never into the pipeline.** ``after_room`` swallows every failure; the
  package is the product and a lost email is a lost email.
* Closing sessions get no note (the guest already had one); a pre-call hello
  writes the agenda instead (``hello_sessions`` when present).

``EDIT_REACHES_YOU_DAYS`` is the promise: gate 1 is a person and does not
time out, so the note says "within about a week" and gives the date.
"""

from __future__ import annotations

import datetime as dt
import html as _html
import re
from typing import Any, Dict, List, Optional, Tuple

from common import (  # noqa: E402
    logger, mira_signature_html, sb_update, send_email, show_for,
)

EDIT_REACHES_YOU_DAYS = 7
MOMENTS = 3
MOMENTS_MIN = 2                  # fewer safe ones than this: quote nothing
MOMENT_MIN_WORDS = 12
MOMENT_MAX_WORDS = 40
MOMENT_MAX_CHARS = 320
ANSWER_WINDOW_SEC = 120          # a line this long after her question is its answer

_LINE = re.compile(r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*([^:]+):\s*(.*)$")
_NUMBER = re.compile(r"\d")
_PROPER = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}")
_HOUSEKEEPING = re.compile(
    r"\b(can you hear me|i can hear you|headphones?|microphone|mic\b|"
    r"start (that |this )?(over|again)|scratch that|off the record|"
    r"can we cut|hang up|the recording|is this working)\b", re.I)
# Never quoted back to a guest, whoever is copied: health, legal, money and
# identity, and anything that sounds like another conversation (a call taken
# mid-interview is scheduling talk). Conservative on purpose: a lovely line
# lost costs nothing, a private one quoted costs the guest's trust.
_SENSITIVE = re.compile(
    r"\b(social security|ssn|date of birth|birthday|born on|"
    r"diagnos\w*|prescri\w*|medicat\w*|medical|disease|illness|symptom\w*|"
    r"diabet\w*|glyc\w*|cancer|tumou?r|surgery|hospital\w*|doctor\w*|clinic\w*|"
    r"therap\w*|psychiatr\w*|depress\w*|anxiety|addict\w*|rehab|pregnan\w*|"
    r"disabilit\w*|veterans? affairs|the va\b|cfr\b|claim\w*|lawsuit|attorney|"
    r"lawyer|court|divorce|custody|arrest\w*|bankrupt\w*|debt|salary|"
    r"password|account number|credit card|my address|my number|phone number|"
    r"appointment|schedul\w*|what day|what time|call (you|me) back|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I)
_IDENTIFIER = re.compile(
    r"\d{3}[\s.-]?\d{3}[\s.-]?\d{4}|\d{4,}|@|\b(january|february|march|april|"
    r"may|june|july|august|september|october|november|december)\s+\d", re.I)
_SENTENCE = re.compile(r"[^.!?]+[.!?]")


def guest_lines(transcript: str, host: str = "Mira") -> List[Tuple[float, str, str]]:
    """``[(room_sec, who, text)]`` for every line not spoken by the host (or a
    narration label), on the transcript's own clock."""
    out = []
    for raw in (transcript or "").splitlines():
        m = _LINE.match(raw.strip())
        if not m:
            continue
        h, mm, ss, who, text = m.groups()
        who = who.strip()
        if who.lower().startswith(host.lower()):
            continue
        at = (int(h) * 3600 + int(mm) * 60 + int(ss)) if ss else (int(h) * 60 + int(mm))
        out.append((float(at), who, text.strip()))
    return out


def safe_to_quote(text: str) -> bool:
    """May this sentence be read back to the guest, with others copied?"""
    return not (_HOUSEKEEPING.search(text) or _SENSITIVE.search(text)
                or _IDENTIFIER.search(text))


def _score(text: str) -> int:
    words = len(text.split())
    if words < MOMENT_MIN_WORDS or words > MOMENT_MAX_WORDS or not safe_to_quote(text):
        return 0
    # A line that names something (a place, a company, a person) is a line
    # worth remembering; length breaks ties. Numbers earn nothing: they are
    # how phone numbers and dates get in.
    bonus = 100 if _PROPER.search(text) else 0
    return bonus + min(words, 50)


def _answers(transcript: str, host: str = "Mira") -> List[Tuple[float, str]]:
    """``[(room_sec, text)]``: the guest's words that answer one of Mira's
    questions, each answer joined from its consecutive lines. A question is
    pending from the Mira line that carries the question mark until the guest
    starts answering it, within ``ANSWER_WINDOW_SEC``; her other lines in
    between ("take your time") do not cancel it."""
    out: List[Tuple[float, str]] = []
    asked_at: Optional[float] = None
    current: Optional[list] = None
    for raw in (transcript or "").splitlines():
        m = _LINE.match(raw.strip())
        if not m:
            continue
        h, mm, ss, who, text = m.groups()
        at = float((int(h) * 3600 + int(mm) * 60 + int(ss)) if ss else (int(h) * 60 + int(mm)))
        who = who.strip().lower()
        if who.startswith(host.lower()):
            if current is not None:
                out.append((current[0], " ".join(current[1])))
                current = None
            if "?" in text:
                asked_at = at
            continue
        if who in ("patrick", "patrick novak", "host", "co-host"):
            continue
        if current is not None:
            current[1].append(text.strip())
        elif asked_at is not None and at - asked_at <= ANSWER_WINDOW_SEC:
            current = [at, [text.strip()]]
            asked_at = None
    if current is not None:
        out.append((current[0], " ".join(current[1])))
    return out


def _sentences(text: str) -> List[str]:
    """Whole sentences only, starting with a capital: a fragment that starts
    mid-thought ("as a peacemaker. And that's...") is never a quote."""
    found = [x.strip() for x in _SENTENCE.findall(" ".join(text.split()))]
    return [x for x in found if x[:1].isupper()]


def _trim(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= MOMENT_MAX_CHARS:
        return text
    cut = text[:MOMENT_MAX_CHARS]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return (cut[:end + 1] if end > 80 else cut.rsplit(" ", 1)[0] + "…").strip()


def memorable_moments(transcript: str, guest_label: str = "",
                      n: int = MOMENTS) -> List[Tuple[float, str]]:
    """The guest's own words Mira will say she remembers, in time order:
    one or two whole, safe sentences from each of their best answers, at most
    one per answer. Empty when fewer than ``MOMENTS_MIN`` qualify."""
    rows = []
    for at, answer in _answers(transcript):
        if not safe_to_quote(answer):
            # One unsafe sentence anywhere in the answer rules the whole
            # answer out: it is about something that should not be quoted.
            continue
        sentences = _sentences(answer)
        best = None
        for i in range(len(sentences)):
            for j in (i + 1, i + 2):
                span = " ".join(sentences[i:j])
                if j > len(sentences):
                    continue
                score = _score(span)
                if score and (best is None or score > best[0]):
                    best = (score, span)
        if best:
            rows.append((best[0], at, best[1]))
    rows.sort(key=lambda r: (-r[0], r[1]))
    chosen = sorted(rows[:n], key=lambda r: r[1])
    if len(chosen) < MOMENTS_MIN:
        return []
    return [(at, _trim(text)) for _s, at, text in chosen]


def thank_you_email(show, app: Dict[str, Any], transcript: str,
                    now: Optional[dt.datetime] = None) -> Tuple[str, str]:
    """``(subject, html)``."""
    e = _html.escape
    now = now or dt.datetime.now(dt.timezone.utc)
    name = str(app.get("name") or "").strip()
    first = name.split()[0] if name else "there"
    reaches = (now + dt.timedelta(days=EDIT_REACHES_YOU_DAYS)).strftime("%A %B %-d")
    moments = memorable_moments(transcript, str(app.get("name") or ""))
    parts = [f"<p>Hi {e(first)},</p>",
             "<p>Thank you for the hour. I am still turning it over.</p>"]
    if moments:
        lead = "Three things" if len(moments) == 3 else "Two things"
        parts.append(f"<p>{lead} you said that I will remember:</p><ul>"
                     + "".join(f"<li>“{e(t)}”</li>" for _at, t in moments) + "</ul>")
    parts += [
        f"<p>Here is what happens next. The edit is being cut now, and Patrick listens "
        f"to it before anyone else does. You will have the episode and its transcript "
        f"by about {e(reaches)}, with a link to approve it, cut anything from it, or "
        f"refuse it; nothing publishes before you have had a week with it. Anything "
        f"you asked to have out in the room is already out of the edit.</p>",
        "<p>If something from today is on your mind before then, reply to this and "
        "it reaches me.</p>",
        mira_signature_html(show),
    ]
    subject = f"Thank you for today, {first}, and what happens next"
    return subject, "".join(parts)


def send_thank_you(run: Dict[str, Any], interview: Dict[str, Any], app: Dict[str, Any],
                   transcript: str, package: Dict[str, Any]) -> bool:
    """Send the note once. Returns True when it went out now."""
    if (interview.get("session_kind") or "interview") != "interview":
        return False
    if package.get("thanks_sent_at"):
        logger.info("thank-you already sent %s", package["thanks_sent_at"])
        return False
    to = str(app.get("email") or "").strip()
    if "@" not in to:
        logger.warning("no guest address — thank-you not sent")
        return False
    show = show_for(interview, app)
    subject, body = thank_you_email(show, app, transcript)
    send_email(to, subject, body, cc_operator=True,
               cc=[str(app.get("publicist_email") or "").strip()])
    try:
        sb_update("editorial_packages", f"id=eq.{package['id']}",
                  {"thanks_sent_at": dt.datetime.now(dt.timezone.utc).isoformat()})
    except Exception:  # noqa: BLE001
        logger.exception("thanks_sent_at not stamped (non-fatal)")
    logger.info("thank-you sent to %s", to)
    return True


def after_room(run: Dict[str, Any], interview: Dict[str, Any], app: Dict[str, Any],
               transcript: str, package: Dict[str, Any]) -> None:
    """The one call post_interview makes. Never raises."""
    try:
        kind = interview.get("session_kind") or "interview"
        if kind == "hello":
            from hello_sessions import after_hello
            after_hello(interview, app, transcript, package)
            return
        send_thank_you(run, interview, app, transcript, package)
    except Exception:  # noqa: BLE001 — the package is the product
        logger.exception("after-room note failed (non-fatal)")
