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
  paraphrased (``memorable_moments``). They are chosen deterministically — the
  guest's longest turns that carry a number or a proper noun — so a re-run
  sends the same note and nothing is invented.
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
MOMENT_MIN_WORDS = 12
MOMENT_MAX_CHARS = 320

_LINE = re.compile(r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*([^:]+):\s*(.*)$")
_NUMBER = re.compile(r"\d")
_PROPER = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}")
_HOUSEKEEPING = re.compile(
    r"\b(can you hear me|i can hear you|headphones?|microphone|mic\b|"
    r"start (that |this )?(over|again)|scratch that|off the record|"
    r"can we cut|hang up|the recording|is this working)\b", re.I)


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


def _score(text: str) -> int:
    words = len(text.split())
    if words < MOMENT_MIN_WORDS or _HOUSEKEEPING.search(text):
        return 0
    # A line that carries a figure or a name is a line worth remembering;
    # length breaks ties, and nothing else is judged.
    bonus = 1000 if (_NUMBER.search(text) or _PROPER.search(text)) else 0
    return bonus + min(words, 80)


def _trim(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= MOMENT_MAX_CHARS:
        return text
    cut = text[:MOMENT_MAX_CHARS]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return (cut[:end + 1] if end > 80 else cut.rsplit(" ", 1)[0] + "…").strip()


def memorable_moments(transcript: str, guest_label: str = "",
                      n: int = MOMENTS) -> List[Tuple[float, str]]:
    """The guest's own lines Mira will say she remembers, in time order."""
    rows = []
    for at, who, text in guest_lines(transcript):
        if guest_label and who.lower() != guest_label.lower():
            # A co-host's lines are not the guest's moments.
            if who.lower() in ("patrick", "patrick novak", "host", "co-host"):
                continue
        score = _score(text)
        if score:
            rows.append((score, at, text))
    rows.sort(key=lambda r: (-r[0], r[1]))
    chosen = sorted(rows[:n], key=lambda r: r[1])
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
        parts.append("<p>Three things you said that I will remember:</p><ul>"
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
    subject = f"Thank you for today, {first} — and what happens next"
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
