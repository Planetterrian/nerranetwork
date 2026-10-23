#!/usr/bin/env python3
"""Interview firing cron (nerra_voices_fire_interview.yml, every 5 min).

Duties per tick:

1. **T-2h SMS reminder** — interviews ~2h out get one SMS from Mira's
   caller ID (``reminder_sent_at`` guards the once-only).
2. **Fire** — interviews whose ``scheduled_at`` falls inside the next
   5-minute window: compile Mira's system prompt from the brief, create the
   ``interview_runs`` row, and start the Voximplant scenario with the run id
   as customData.
3. **T-5 min** — the guest gets a text and an email: we start in five
   minutes, here is the way in (``start_notice_at``).
4. **T+5 min** — a guest who still hasn't opened the studio: Patrick gets a
   text and an email with their number and a one-click "have Mira call
   them" link (``late_alert_at``). Oct 16 2026, after Meridan Zerner.

GitHub cron is best-effort (spec §5.2 note): the firing window is computed
here as [now - grace, now + 5 min] so a delayed tick still fires anything
it missed, and the ``interview_runs`` uniqueness check keeps a double tick
from double-calling the guest.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re

import requests

from common import (  # noqa: E402
    OPERATOR_EMAIL, ROOT, carry_the_show_block, cohost_name, load_prompt, logger,
    mira_signature_html, guest_notes_block, guest_agenda_block, pacific_time,
    notify_operator, GUEST_AUDIO_HTML, studio_steps_html,
    operator_phone, render_email, sb_insert, sb_select, sb_update, send_email,
    show_for, to_e164, guest_details, interview_subject, missed_email,
)
from learning import lessons_block, variety_block  # noqa: E402
from address import address_rule, first_name, spoken as spoken_address  # noqa: E402
from interview_shape import planned_minutes, shape_block  # noqa: E402

FIRE_WINDOW_AHEAD_MIN = 5          # phone (PSTN) interviews: Mira dials at T-5..T-0
STUDIO_UNLOCK_AHEAD_MIN = 12       # browser studio: run row (= unlock) at T-12, so
                                   # guests and the co-host can sign in, test the
                                   # mic and be in the room 10 minutes early
                                   # (Patrick, Sept 9 2026 rehearsal)
FIRE_GRACE_BEHIND_MIN = 30   # cron drift tolerance — never leave a guest
                             # waiting; GitHub delivers */5 crons roughly
                             # hourly under load, so 10 min missed real slots
                             # (July 17 2026). Also gives failed-call retries
                             # room: a no-answer run resets the interview to
                             # briefed and later ticks in this window re-fire.
REMINDER_AHEAD = (dt.timedelta(minutes=105), dt.timedelta(minutes=135))
# Oct 16 2026 (Patrick, after Meridan Zerner never opened her studio and
# nobody knew until the no-show email forty minutes later). The Worker
# dispatches this job on its five-minute cron while an interview is near, so
# a run lands a minute or so after :x0 and :x5. Starts sit on five-minute
# marks: the tick five minutes before the start finds it 3 to 5 minutes out,
# the one ten minutes before finds it 8 to 10 out, outside this window.
START_NOTICE_AHEAD = (dt.timedelta(minutes=1), dt.timedelta(minutes=7))
# ...and the tick five minutes after the start finds it 4 to 6 minutes late.
# Twenty minutes at the far end covers a GitHub delay; after that the no-show
# sweep (NO_SHOW_AFTER_MIN) has its own email.
LATE_ALERT_AFTER = (dt.timedelta(minutes=4), dt.timedelta(minutes=20))
# Oct 5 2026 (Jon Cheney): a GitHub Actions outage meant no runner picked up
# the five-minute fire job for over an hour, so his studio never unlocked and
# the page told him he was early until he gave up. A browser interview's run
# is now prepared up to a day ahead, as `staged`, and the Worker opens it
# itself the moment the guest arrives: on the day, nothing waits on GitHub.
STAGE_AHEAD = dt.timedelta(hours=24)

# Phase 2 co-host (Sept 2026, docs/cohost_phase2_contract.md): Patrick is in
# the room on every interview unless the interview row says host_mode=false.
# The block is tokenised so {{cohost_name}} follows env COHOST_NAME.
COHOST_BLOCK = (
    "CO-HOST: {{cohost_name}}, the network's founder, is in the room as your "
    "co-host. Introduce him BY NAME in your opening, before your first "
    "question, and give him a beat to greet the guest himself — a guest who "
    "hears a second voice ten minutes in with no idea who it belongs to has "
    "been ambushed. He may interject with a question, a clarification, or to fix a "
    "technical problem. When he speaks, answer him briefly if he asked you "
    "something, otherwise acknowledge in a few words and hand the floor back "
    "to the guest. He is not the interviewee: never interview {{cohost_first}}, "
    "never ask him the lightning round, and keep the guest as the centre of "
    "the conversation. If {{cohost_first}} asks for a pause, stop talking "
    "and wait for him."
)


def _clip_is_there(url: str) -> bool:
    """A clip the room will play must exist: a consent notice that 404s is no
    consent notice at all, and the guest hears nothing."""
    try:
        import time
        import requests
        # Past the CDN: audio.nerranetwork.com caches a 404 for four hours, so
        # anyone who checked a clip before it was uploaded would otherwise keep
        # it out of every room until the cache expired (Sept 23 2026).
        sep = "&" if "?" in url else "?"
        resp = requests.head(f"{url}{sep}exists={int(time.time())}",
                             timeout=10, allow_redirects=True)
        return resp.status_code == 200
    except Exception:  # noqa: BLE001 — unreachable counts as absent
        return False


def room_clips(show) -> dict:
    """The consent notice and drop apology for this show's room.

    Sept 23 2026. Both columns default, in the database, to clips voiced for
    The Age of AI, so every Nerra Voices guest was greeted with "Hi, this is
    Mira, the AI host for the Age of AI" before Mira introduced herself
    properly as the host of Nerra Voices eleven seconds later. Deploying the
    scenario could never fix that: the words are in an MP3. A show that names
    its own clips gets them — but only once they exist, because the shared
    clip with the wrong show name still tells the guest they are being
    recorded, and a missing one tells them nothing.
    """
    out = {}
    for column, url in (("recording_disclosure_url", getattr(show, "disclosure_clip", "")),
                        ("grok_drop_apology_url", getattr(show, "apology_clip", ""))):
        if not url:
            continue
        if _clip_is_there(url):
            out[column] = url
        else:
            logger.warning("%s: %s not found at %s — the room keeps the shared "
                           "clip", show.slug, column, url)
    return out


def host_mode_enabled(interview: dict, run: dict | None = None) -> bool:
    """Whether the co-host is expected in the room.

    Sept 18 2026: this defaulted ON, and every episode was a three-hander
    whether or not Patrick could make it (Sheldon Poon waited for him for
    forty-eight minutes). Mira carries the room on her own; Patrick, who
    created the network, joins when a guest asked for him on the
    application, which the booking writes onto the interview as
    ``host_mode``. An explicit value on the run or the interview wins;
    nothing set means Mira alone."""
    for row in (run, interview):
        if row is not None and row.get("host_mode") is not None:
            return bool(row.get("host_mode"))
    return False


COHOST_INTRO_STEP = (
    "   In that same sentence, introduce {{cohost_name}}, your co-host, by "
    "name: a real person, the founder of the network, who will jump in with "
    "his own questions. If he is already in the room, hand him a beat to say "
    "hello himself before your first question.\n"
)


def cohost_craft(enabled: bool = True, show=None) -> str:
    """What Mira should learn from watching her co-host work.

    Lives in its own prompt file and is loaded only when he is actually in
    the room — an interview with no co-host must not be told to study one.
    """
    if not enabled:
        return ""
    name = cohost_name()
    return (load_prompt("cohost_craft.txt", show=show)
            .replace("{{cohost_name}}", name)
            .replace("{{cohost_first}}", name.split()[0]))


def cohost_intro_step(enabled: bool = True) -> str:
    """Step 3 of the opening, only when there is a co-host to introduce."""
    if not enabled:
        return ""
    return COHOST_INTRO_STEP.replace("{{cohost_name}}", cohost_name())


def cohost_block(enabled: bool = True) -> str:
    if not enabled:
        return ""
    name = cohost_name()
    return (COHOST_BLOCK.replace("{{cohost_name}}", name)
            .replace("{{cohost_first}}", name.split()[0]))


def manage_url(interview: dict) -> str:
    """The guest's own move-or-cancel link, or "" when the row predates it."""
    token = (interview.get("manage_token") or "").strip()
    if not token:
        return ""
    from urllib.parse import quote
    return f"https://api.nerranetwork.com/voices/manage/{quote(token, safe='')}"


def host_link(show, interview_id: str) -> str:
    """Patrick's co-host studio link: the guest studio URL + role=host.

    Room model (Sept 9 2026): no token. Everyone joins the interview room
    the same way; the role only tells Mira who the co-host is and labels
    his recording. The link is the same for the whole session, so it can
    be reused to rejoin after a drop."""
    return f"{show.studio_url(interview_id)}&role=host"


def notify_host(interview: dict, app: dict, show, *, when: str) -> None:
    """Email + SMS Patrick his co-host link (best-effort, never raises).

    ``when`` is the human phrase for the lead time ("in 2 min", "in about
    2 hours"). Email → OPERATOR_EMAIL (templates/email/voices_host_link.j2);
    SMS → OPERATOR_PHONE when set, from Mira's caller ID.
    """
    guest_name = (app.get("name") or "the guest").strip()
    try:
        url = host_link(show, interview["id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Host link not sent for %s: %s", interview["id"], exc)
        notify_operator(show.slack(
            f"co-host link for {guest_name} NOT sent ({exc})"), critical=True)
        return
    try:
        html = render_email(
            "voices_host_link.j2", show=show,
            host_url=url, guest_name=guest_name,
            scheduled_at=pacific_time(interview.get("scheduled_at", "")),
            cohost_name=cohost_name(), when=when,
            interview_id=interview["id"],
        )
        send_email(OPERATOR_EMAIL,
                   f"{show.short_label}: co-host link — {guest_name} {when}",
                   html)
    except Exception:  # noqa: BLE001 — the fire must not fail on this
        logger.exception("Host link email failed (non-fatal)")
    phone = operator_phone()
    if not phone:
        logger.info("OPERATOR_PHONE unset — host link SMS skipped")
        return
    try:
        from voximplant.api_clients.voximplant_client import send_sms
        caller_id = interview.get("caller_id") or os.environ.get(
            "VOXIMPLANT_CALLER_ID", "")
        send_sms(phone, host_sms_text(show, guest_name, url, when),
                 source_number=caller_id or None)
    except Exception:  # noqa: BLE001
        logger.exception("Host link SMS failed (non-fatal)")


def host_sms_text(show, guest_name: str, url: str, when: str) -> str:
    return f"{show.name}: {guest_name} {when}. Your co-host link: {url}"

MIRA_TOOLS = [
    {
        "type": "function",
        "name": "nerra_episode_lookup",
        "description": (
            "Look up the 3 most recent Nerra Network episodes covering a "
            "given topic. Use this when you want to reference what other "
            "Nerra shows have covered on the guest's topic."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "show_filter": {"type": "string",
                                "description": "optional show id"},
            },
            "required": ["topic"],
        },
    },
    {
        "type": "function",
        "name": "guest_brief_lookup",
        "description": (
            "Pull the pre-interview research brief on the current guest. "
            "Use this to refresh your memory mid-interview on a specific "
            "topic they wanted to discuss."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "section": {"type": "string",
                            "enum": ["bio", "topics", "past_work",
                                     "predictions"]},
            },
        },
    },
]

# Oct 21 2026 (review of every interview): the fact-check tool is OFF by
# default. Together with a brief that listed "mismatches", it produced the
# examiner's posture on air — a host telling guests she could not verify
# things that were true. It stays available for a guest who asks for figures
# or dates to be checked (``fact_check: true`` on the interview row), and its
# description never asks for a verdict: it adds to the guest's point or it
# says nothing.
FACT_CHECK_TOOL = {
    "type": "function",
    "name": "fact_check_claim",
    "description": (
        "Quietly look for a figure, date or related case that ADDS to "
        "something the guest just said. Returns at once: "
        "carry on talking and say nothing about it. Anything useful arrives later as a "
        "[RESEARCH NOTE] with its source; if nothing arrives, "
        "nothing happened and the guest's point stands. Never use it to test "
        "whether the guest is right."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "claim": {"type": "string"},
            "context": {"type": "string",
                        "description": "what the guest was discussing"},
        },
        "required": ["claim"],
    },
}


def fact_check_enabled(interview: dict | None, app: dict | None = None) -> bool:
    """Whether this interview's room carries the fact-check tool. Off unless
    the interview row (or, failing that, the application) says so."""
    for row in (interview, app):
        if row is not None and row.get("fact_check") is not None:
            return bool(row.get("fact_check"))
    return False


def mira_tools(interview: dict | None = None, app: dict | None = None) -> list:
    """The tools the room gives Mira for this interview."""
    tools = list(MIRA_TOOLS)
    if fact_check_enabled(interview, app):
        tools.append(FACT_CHECK_TOOL)
    return tools


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse(value) -> "dt.datetime | None":
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _iso(t: dt.datetime) -> str:
    # Z suffix, not +00:00: these strings go raw into PostgREST query
    # strings, where an unencoded "+" is decoded as a space → 400 (this
    # crashed every fire cron tick until July 17 2026).
    return t.isoformat().replace("+00:00", "Z")


def is_hello_session(interview: dict) -> bool:
    """A five-minute pre-call hello (fork E, Oct 21 2026): Mira meets the
    guest two days before the room, checks their sound and asks what they
    most want the hour to reach."""
    return (interview or {}).get("session_kind") == "hello"


def compile_prompt_for(interview: dict, app: dict, brief: dict | None) -> str:
    """The prompt for whichever kind of session this is: closing, hello
    (``hello_sessions.compile_hello_prompt`` when that module is present,
    else the ordinary interview prompt), or the interview."""
    if is_closing_session(interview):
        return compile_closing_prompt(interview, app)
    if is_hello_session(interview):
        try:
            from hello_sessions import compile_hello_prompt  # noqa: E402
        except ImportError:
            logger.warning("hello_sessions is not available; a hello session "
                           "gets the interview prompt")
        else:
            return compile_hello_prompt(interview, app)
    return compile_mira_prompt(interview, app, brief or {})


def compile_closing_prompt(interview: dict, app: dict) -> str:
    """Oct 5 2026 (Piper Martz). A short session that records only the
    closing round of an interview the old time cap cut off; it is spliced
    onto the end of the first recording."""
    show = show_for(interview, app)
    return load_prompt(
        "mira_closing_session.txt", show=show,
        show_name=show.name, guest_name=app["name"],
        guest_address_rule=address_rule(app),
        closing_question=show.closing_question,
        where_we_left_off=where_we_left_off(interview),
        already_answered=already_answered(interview, show.closing_question),
    )


# Oct 14 2026 (Piper Martz). Her first session had reached the lightning
# round, so she had already answered the show's own question ("the one bet
# you're making"), and the closing session asked it again: she made the same
# bet and told the same IKEA story a second time, and the episode had to cut
# it. The closing round is a fixed list, so what the first recording already
# covered is worked out from its transcript and handed to Mira as a list of
# questions she must not ask.
CLOSING_ROUND = (
    ("A book they would recommend, and why",
     re.compile(r"book (you'?d|you would|you) (recommend|suggest)|recommend a book", re.I)),
    ("One person they think you should interview next",
     re.compile(r"interview next|should (i|we) (interview|talk to|speak (to|with)) next", re.I)),
    ("The best piece of advice they were ever given",
     re.compile(r"best (piece of )?advice", re.I)),
    ("The person who has inspired them most",
     re.compile(r"inspired you (the )?most|who inspires you|(person|people) who('?s| has| have) inspired",
                re.I)),
    ("Whether they would like to be interviewed by you again",
     re.compile(r"interviewed by me again|(do|doing) this again", re.I)),
    ("How the experience of being interviewed by an AI was",
     re.compile(r"experience of being interviewed|being interviewed by an ai", re.I)),
    ("One specific suggestion for what could be improved",
     re.compile(r"(thing|suggestion).{0,40}improve|could (we|i|be) improve", re.I)),
)
_ROW = re.compile(r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*([^:]+):\s*(.*)$")
_COMMON = {"what", "what's", "that", "your", "with", "have", "this", "about", "more",
           "from", "they", "their", "there", "which", "would", "could", "you're",
           "when", "were", "been", "into", "than", "then", "them", "these", "those",
           "think", "really", "just"}


def _content_words(text: str) -> set:
    return {w for w in re.findall(r"[a-z']+", (text or "").lower())
            if len(w) >= 4 and w not in _COMMON}


def _asks_show_question(line: str, question: str) -> bool:
    """She rarely reads the show's question word for word ("12 months" for
    "twelve months"), so it counts as asked when most of its words are there."""
    want = _content_words(question)
    if not want:
        return False
    return len(want & _content_words(line)) >= max(2, round(0.6 * len(want)))


def covered_in_transcript(transcript: str, closing_question: str) -> list:
    """The closing-round questions asked AND answered in ``transcript``, in
    the order asked. Answered means the guest spoke after the question and
    Mira spoke again after that: the question the room cut off in the middle
    of is not finished, and stays on her list."""
    rows = []
    for line in (transcript or "").split("\n\n[Closing session]")[0].splitlines():
        m = _ROW.match(line.strip())
        if m:
            rows.append((m.group(4).strip().lower() == "mira", m.group(5)))
    checks = [(f'The show\'s own question: "{closing_question}"',
               lambda text: _asks_show_question(text, closing_question))]
    checks += [(label, rx.search) for label, rx in CLOSING_ROUND]
    covered = []
    for label, asks in checks:
        at = next((i for i, (mira, text) in enumerate(rows) if mira and asks(text)), None)
        if at is None:
            continue
        guest = next((i for i in range(at + 1, len(rows)) if not rows[i][0]), None)
        if guest is not None and any(rows[i][0] for i in range(guest + 1, len(rows))):
            covered.append((at, label))
    return [label for _at, label in sorted(covered)]


def already_answered(interview: dict, closing_question: str) -> str:
    """The ALREADY ANSWERED block of a closing session's prompt."""
    prev = interview.get("continues_interview_id")
    covered = []
    if prev:
        try:
            rows = sb_select("editorial_packages",
                             f"interview_id=eq.{prev}&order=created_at.desc&limit=1"
                             "&select=transcript_raw,transcript_cleaned")
            text = ((rows[0].get("transcript_raw") or rows[0].get("transcript_cleaned") or "")
                    if rows else "")
            covered = covered_in_transcript(text, closing_question)
        except Exception:  # noqa: BLE001 — the session still runs
            logger.exception("could not read what the first recording covered for %s", prev)
    if not covered:
        return "None of the closing round was finished in the first recording."
    return "\n".join(f"- {label}" for label in covered)


def where_we_left_off(interview: dict) -> str:
    """The last few minutes of the interview this session finishes, from its
    transcript, so Mira picks up exactly where the room cut off."""
    if interview.get("episode_thesis"):
        return str(interview["episode_thesis"])
    prev = interview.get("continues_interview_id")
    if prev:
        try:
            rows = sb_select("editorial_packages",
                             f"interview_id=eq.{prev}&order=created_at.desc&limit=1"
                             "&select=transcript_cleaned")
            tail = (rows[0].get("transcript_cleaned") or "")[-1800:] if rows else ""
            if tail:
                return ("The last few minutes of the first recording, where the room "
                        "cut off:\n" + tail)
        except Exception:  # noqa: BLE001 — the session still runs
            logger.exception("could not read the earlier transcript for %s", prev)
    return "The closing round had just begun when the first recording stopped."


def refresh_staged_prompt(run: dict, interview: dict) -> bool:
    """Recompile a staged run's prompt so it carries what was learned since.

    Oct 19 2026 (review of every graded interview). A run is staged up to a
    day ahead, and the grading pass adopts lessons an hour or so after each
    interview, so the next day's interview went in without the last one's
    lessons: Jason Shumard was staged before Cory O'Daniel had been graded.
    Every tick now brings a staged prompt up to date, and only while the run
    is still staged: once the guest has opened the studio it is left alone.
    """
    if (run or {}).get("status") != "staged" or not run.get("id"):
        return False
    try:
        app = sb_select("guest_applications", f"id=eq.{interview['application_id']}")[0]
        if is_closing_session(interview) or is_hello_session(interview):
            prompt = compile_prompt_for(interview, app, None)
        else:
            briefs = sb_select("interview_briefs", f"interview_id=eq.{interview['id']}")
            if not briefs:
                return False
            prompt = compile_prompt_for(interview, app, briefs[0])
    except Exception:  # noqa: BLE001 — the staged prompt still works
        logger.exception("Refreshing the staged prompt for %s failed (non-fatal)",
                         interview.get("id"))
        return False
    patch: dict = {}
    if prompt and prompt != (run.get("mira_system_prompt") or ""):
        patch["mira_system_prompt"] = prompt
    # The end-of-turn silence travels with the run too (Oct 19 2026: Jason
    # Shumard's run was staged at 1.3 s the day before it moved to 1.8 s).
    if run.get("turn_detection") != turn_detection():
        patch["turn_detection"] = turn_detection()
    if not patch:
        return False
    try:
        sb_update("interview_runs", f"id=eq.{run['id']}&status=eq.staged", patch)
    except Exception:  # noqa: BLE001
        logger.exception("Saving the refreshed prompt for run %s failed (non-fatal)", run["id"])
        return False
    logger.info("Run %s: staged prompt refreshed with the latest lessons", run["id"])
    return True


def is_closing_session(interview: dict) -> bool:
    return (interview.get("session_kind") or "interview") == "closing"


#: End-of-turn silence, ms. Oct 19 2026: 1300 → 1800. Scott Pulcini (Oct 6)
#: and Jon Cheney (Oct 19) said the same thing unprompted: "if I pause too
#: long you're gonna move on to the next question", "the questions came at
#: me pretty quickly". A pause to think is where the good answers come from,
#: and 1.3 s is shorter than one. The prompt cannot fix this: it is the
#: voice API deciding the guest has finished, before Mira hears a word.
TURN_SILENCE_MS = 1800


def turn_detection() -> dict:
    """End-of-turn silence Mira waits for, per run (MIRA_TURN_SILENCE_MS)."""
    try:
        ms = int(os.environ.get("MIRA_TURN_SILENCE_MS") or TURN_SILENCE_MS)
    except ValueError:
        ms = TURN_SILENCE_MS
    return {"silence_duration_ms": max(600, min(2500, ms))}


#: Grok Voice 3.0 transcription key terms: at most this many, each this long
#: (xAI: max 100 terms of up to 50 characters, updatable mid-session).
KEYTERMS_MAX = 100
KEYTERM_MAX_CHARS = 50


def keyterms_for(app: dict, show, cohost: str = "") -> list:
    """The proper nouns the live transcription should get right (Oct 15 2026,
    Grok Voice 3.0 ``audio.input.transcription.keyterms``): the guest's name
    and its parts, their organisation and title, the show, the network, the
    host and the co-host. Deduplicated, in that order, trimmed to the API's
    limits. The words Mira hears — and the fact-check tool reads — spell a
    guest's name the way the guest does, instead of the nearest common word."""
    raw = [
        app.get("name") or "",
        *str(app.get("name") or "").split(),
        app.get("organization") or "",
        app.get("title") or "",
        getattr(show, "name", "") or "",
        "Nerra Network", "Mira",
        cohost or "",
        *str(cohost or "").split(),
    ]
    out: list = []
    for term in raw:
        t = " ".join(str(term).split())[:KEYTERM_MAX_CHARS]
        if len(t) >= 2 and t.lower() not in {o.lower() for o in out}:
            out.append(t)
        if len(out) >= KEYTERMS_MAX:
            break
    return out


# Oct 21 2026: the live interview's reasoning effort is a run setting, read
# by the scenario as ``config.reasoning_effort``. "high" is what every room
# has run since Grok Voice 3.0; the rehearsal harness trials "low" before a
# guest hears it. Env MIRA_REASONING_EFFORT overrides for a deploy.
REASONING_EFFORTS = ("none", "low", "medium", "high")
DEFAULT_REASONING_EFFORT = "high"


def reasoning_effort() -> str:
    value = (os.environ.get("MIRA_REASONING_EFFORT") or "").strip().lower()
    return value if value in REASONING_EFFORTS else DEFAULT_REASONING_EFFORT


# Columns a run row may name before their migration is applied, with the
# migration that adds each. PostgREST refuses a row naming a column the table
# lacks, and a refused insert would cost the interview, so the insert retries
# without the column and names the migration to apply.
_OPTIONAL_RUN_COLUMNS = {
    "keyterms": "20261015_interview_runs_keyterms.sql",
    "reasoning_effort": "20261021_mira_hears_and_asks.sql",
}


def insert_interview_run(row: dict) -> dict:
    """``sb_insert("interview_runs", row)`` that survives an optional column
    not being applied yet (``_OPTIONAL_RUN_COLUMNS``)."""
    row = dict(row)
    row.setdefault("reasoning_effort", reasoning_effort())
    for _ in range(len(_OPTIONAL_RUN_COLUMNS) + 1):
        try:
            return sb_insert("interview_runs", row)
        except requests.HTTPError as exc:
            body = (getattr(exc.response, "text", "") or "")[:400]
            status = exc.response.status_code if exc.response is not None else 0
            missing = [c for c in _OPTIONAL_RUN_COLUMNS if c in row and c in body]
            if status not in (400, 404) or not missing:
                raise
            column = missing[0]
            logger.warning(
                "interview_runs has no %s column (apply supabase/migrations/%s); "
                "firing without it: %s", column, _OPTIONAL_RUN_COLUMNS[column], body)
            row = {k: v for k, v in row.items() if k != column}
    return sb_insert("interview_runs", row)


PROMPT_MAX_CHARS = 16000


def compile_mira_prompt(interview: dict, app: dict, brief: dict) -> str:
    """Mira's system prompt for this interview, branded for its show.

    The show (name, premise, opening line, closing question) comes from
    ``show_for(interview, app)`` — the ``show`` column on the interview,
    then the application, then the default show for pre-migration rows.
    """
    show = show_for(interview, app)
    minutes = planned_minutes(interview, app)
    questions = brief.get("likely_questions") or []
    q_text = "\n".join(f"- {q.get('question', q) if isinstance(q, dict) else q}"
                       for q in questions)
    prompt = load_prompt(
        "mira_system_prompt.txt",
        show=show,
        show_name=show.name,
        show_premise=show.premise,
        opening_line=show.opening_line,
        closing_question=show.closing_question,
        guest_name=app["name"],
        guest_address=spoken_address(app),
        guest_address_rule=address_rule(app),
        guest_title=app.get("title") or "",
        guest_details=guest_details(app),
        guest_organization=app.get("organization", ""),
        episode_thesis=interview.get("episode_thesis")
        or brief.get("episode_thesis_draft", ""),
        guest_brief=brief.get("bio_research", ""),
        likely_questions=q_text,
        guest_notes=guest_notes_block(app),
        guest_agenda=guest_agenda_block(app),
        cohost_name=cohost_name(),
        cohost_first=cohost_name().split()[0],
        cohost_block=cohost_block(host_mode_enabled(interview)),
        cohost_intro_step=cohost_intro_step(host_mode_enabled(interview)),
        cohost_craft=cohost_craft(host_mode_enabled(interview), show),
        planned_minutes=minutes,
        # The lightning round needs about a third of a short interview and a
        # fixed quarter-hour of a long one, or a 20-minute conversation is
        # half lightning round.
        lightning_at=max(4, min(15, round(minutes / 3))),
        guest_shape=shape_block(interview, app),
        # What one previous guest said on this guest's subject, as an offer.
        carry_the_show=carry_the_show_block(show, exclude_email=app.get("email", ""), app=app),
        # Sept 17 2026: the standing lessons go near the TOP, right after the
        # guest, not on the end of four thousand words of craft. The prompt
        # was cut to a third so they carry the weight they are meant to.
        lessons=lessons_block(show.slug),
    ) + variety_block(show.slug)
    # Oct 21 2026: the compiled prompt was 43,000 characters for one guest,
    # under 6,000 of them about that guest. A brief is what a host reads in
    # the minute before the room opens; past this it is a rulebook again.
    if len(prompt) > PROMPT_MAX_CHARS:
        logger.warning("Mira's compiled prompt is %d characters (budget %d) for %s",
                       len(prompt), PROMPT_MAX_CHARS, app.get("name"))
    return prompt


def when_text(iso: str, guest_tz: str = "") -> str:
    """Same wording as the prep brief: Pacific Time (the network's zone), with
    the guest's own clock alongside when the booking told us their zone."""
    return pacific_time(iso, guest_tz or None)


def reminder_email(interview: dict, app: dict, show, manage: str,
                   soon: bool = False) -> "tuple[str, str]":
    """Mira's reminder, in her own voice (Sept 28 2026). ``soon`` is the
    short-notice version sent when the studio opens."""
    import html as _h
    studio = show.studio_url(interview["id"]) + "&role=guest"
    phone_mode = (interview.get("call_mode") or "webrtc") != "webrtc"
    when = when_text(interview.get("scheduled_at", ""), interview.get("guest_timezone") or "")
    first = _h.escape(first_name(app))
    closing = is_closing_session(interview)
    if soon:
        subject = (f"I'll call you in a few minutes for {show.name}" if phone_mode
                   else f"Your {show.name} studio is open")
        lead = ("I'm about to call your phone for our interview. Find a quiet spot "
                "and answer when it rings." if phone_mode else
                "The studio is open and I'm ready when you are. We start in about "
                "ten minutes.")
    else:
        # Oct 22 2026: named, so two guests' reminders never share a thread.
        subject = (f"{first_name(app)}, our closing session for {show.name} is in about two hours"
                   if closing else
                   f"{first_name(app)}, our interview on {show.name} is in about two hours")
        lead = (f"We're on for {_h.escape(when)}, about two hours from now."
                if when else "We're on in about two hours.")
    parts = [f"<p>Hi {first},</p>", f"<p>{lead}</p>"]
    # Oct 8 2026 (Patrick): every interview email says what it's about.
    about = "" if soon else interview_subject(interview, app)
    if about:
        label = "The conversation we're finishing" if closing else "What we'll talk about"
        parts.append(f"<p><strong>{label}:</strong> {_h.escape(about)}</p>")
    if phone_mode:
        parts.append("<p>I'll call the number you gave us. If you're able to join from a "
                     "computer with headphones instead, it sounds noticeably better than a "
                     f'phone line: <a href="{studio}">your studio link</a> works right up to '
                     "the start.</p>")
    elif soon:
        # Oct 1 2026: the last email before the interview repeats the way in,
        # step by step. Jonathan had the page open and never got past step 2.
        parts.append("<p>Headphones on, and from your computer for the best sound.</p>")
        parts.append(str(studio_steps_html(studio)))
    else:
        parts.append(GUEST_AUDIO_HTML)
        check = interview.get("setup_check") or {}
        if isinstance(check, dict) and check.get("mic") == "ok":
            parts.append("<p>Your setup test passed, thank you. Use the same computer, "
                         "browser and headphones today and you're all set.</p>")
        else:
            parts.append(
                '<p style="background:#fffbeb;border-left:4px solid #d97706;padding:.7em 1em">'
                f'<strong>Please take 30 seconds now:</strong> <a href="{studio}&test=1">run '
                "the setup test</a> on the computer, browser and headphones you'll use. It "
                "confirms I'll hear you clearly, and anything it finds is easy to fix now and "
                "hard to fix at the start time.</p>")
        parts.append(str(studio_steps_html(studio)))
    if manage and not soon:
        parts.append(f'<p>If today doesn\'t work after all, <a href="{manage}">move or '
                     "cancel it here</a>. One tap, no explanation needed; I would much "
                     "rather know.</p>")
    parts.append(mira_signature_html(show))
    return subject, "".join(parts)


def send_guest_reminder(interview: dict, app: dict, show, manage: str,
                        soon: bool = False) -> None:
    subject, body = reminder_email(interview, app, show, manage, soon=soon)
    # Oct 9 2026: the two-hour reminder is guest correspondence like the
    # rest, so Patrick, Dan and the publicist see it. The studio-open nudge
    # ten minutes out stays between Mira and the guest.
    if soon:
        send_email(app.get("email", ""), subject, body)
    else:
        send_email(app.get("email", ""), subject, body, cc_operator=True,
                   cc=[str(app.get("publicist_email") or "")])


def xai_credit_stop() -> str:
    """The provider's words when the xAI account is out of credit, else "".

    Oct 23 2026: the account ran dry at 09:45 UTC and an interview was booked
    for 20:45 the same day. Mira's live room is a Grok Voice session on that
    account, so a guest would have joined a room nobody could speak in. One
    one-token completion at the T-2h reminder is enough to know; any other
    failure (network, a bad key) answers "" — only a billing stop, read by
    the same matcher the show runs use, raises the alarm."""
    key = os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY") or ""
    if not key:
        return ""
    try:
        r = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "grok-4.3", "max_tokens": 1,
                  "messages": [{"role": "user", "content": "ok"}]},
            timeout=30)
    except Exception:  # noqa: BLE001 — a blip is not a billing stop
        return ""
    if r.status_code < 400:
        return ""
    from engine.provider_quota import is_quota_exhausted
    return r.text[:400] if is_quota_exhausted(r.text) else ""


def credit_alert(interview: dict, app: dict, show, stop: str) -> None:
    """Tell Patrick the room cannot run, while there is time to fix it."""
    when = pacific_time(interview.get("scheduled_at") or "")
    guest = app.get("name") or "the guest"
    text = (f"{show.name}: the xAI account is out of credit and {guest}'s "
            f"interview starts {when}. Mira's room runs on that account — add "
            "credits or raise the spending limit at console.x.ai → Billing "
            "now, or reschedule the guest. Provider said: " + stop)
    notify_operator(text, critical=True)
    try:
        send_email(OPERATOR_EMAIL, f"Mira cannot run {guest}'s interview: xAI out of credit",
                   f"<p>{text}</p>")
    except Exception:  # noqa: BLE001
        logger.exception("credit alert email failed")


def send_reminders() -> None:
    lo, hi = _now() + REMINDER_AHEAD[0], _now() + REMINDER_AHEAD[1]
    due = sb_select(
        "interviews",
        "status=eq.briefed&reminder_sent_at=is.null"
        f"&scheduled_at=gte.{_iso(lo)}&scheduled_at=lte.{_iso(hi)}",
    )
    for interview in due:
        try:
            app_rows = sb_select("guest_applications",
                                 f"id=eq.{interview['application_id']}")
            app = app_rows[0] if app_rows else {}
            show = show_for(interview, app)
            # Claim the reminder FIRST. Sept 10 2026 (Matt Davis): the guest
            # SMS threw on an un-normalised number, so reminder_sent_at was
            # never written and every 5-minute tick re-ran this block —
            # Patrick got five copies of the co-host email. A reminder is
            # best-effort; it must never be retried in a loop.
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"reminder_sent_at": _iso(_now())})
            stop = xai_credit_stop()
            if stop:
                credit_alert(interview, app, show, stop)
            # Phase 2: Patrick's T-2h co-host link goes out first (his own
            # SMS/email, never to the guest) — it does not depend on the
            # guest having a phone on file.
            if host_mode_enabled(interview):
                notify_host(interview, app, show, when="in about 2 hours")
            # Sept 15 2026 (Erica Sell): the only reminder was an SMS with a
            # studio link and no way to say "not today". A guest who cannot
            # make it has to either reply to an email nobody is watching or
            # simply not turn up, and not turning up is what they choose. The
            # reminder now offers the other door, in the message and in the
            # text, two hours out — which is early enough to be useful.
            manage = manage_url(interview)
            try:
                send_guest_reminder(interview, app, show, manage)
            except Exception:  # noqa: BLE001 — the SMS is the primary reminder
                logger.exception("Reminder email failed for %s (non-fatal)",
                                 interview["id"])
            phone = to_e164(app.get("phone"))
            if not phone:
                logger.warning("Interview %s: no usable phone (%r) — guest "
                               "reminder SMS skipped", interview["id"],
                               app.get("phone"))
                notify_operator(show.slack(
                    f"{app.get('name') or 'guest'} has no usable phone number "
                    f"({app.get('phone')!r}) — reminder SMS and the phone "
                    "fallback are unavailable for this interview; the emailed "
                    "studio link still works."))
                continue
            from voximplant.api_clients.voximplant_client import send_sms
            caller_id = interview.get("caller_id") or os.environ.get(
                "VOXIMPLANT_CALLER_ID", "")
            if (interview.get("call_mode") or "webrtc") == "webrtc":
                text = (
                    f"Mira here, from {show.name} (Nerra Network). Your "
                    "interview starts in about two hours. For the best sound, "
                    "join from a computer with headphones and a good mic "
                    "(phone audio is much thinner). Open your link, press "
                    "Check my microphone until it says Sounds good, then "
                    f"Join: {show.studio_url(interview['id'])}"
                    + (f" — can't make it? {manage}" if manage else "")
                    + " — Mira"
                )
            else:
                text = (
                    f"Mira here, from {show.name} (Nerra Network). Your "
                    "interview starts in about two hours — I'll be calling "
                    f"you from this number ({caller_id}). Find a quiet spot "
                    "and we'll make something great."
                    + (f" Can't make it? {manage}" if manage else "")
                    + " — Mira"
                )
            send_sms(phone, text, source_number=caller_id or None)
            logger.info("Reminder SMS sent for interview %s", interview["id"])
        except Exception:  # noqa: BLE001 — a reminder failure must not stop firing
            logger.exception("Reminder failed for %s (non-fatal)",
                             interview["id"])


def fire_due_interviews() -> int:
    lo = _now() - dt.timedelta(minutes=FIRE_GRACE_BEHIND_MIN)
    unlock_hi = _now() + dt.timedelta(minutes=max(FIRE_WINDOW_AHEAD_MIN, STUDIO_UNLOCK_AHEAD_MIN))
    hi = _now() + STAGE_AHEAD
    phone_hi = _now() + dt.timedelta(minutes=FIRE_WINDOW_AHEAD_MIN)
    # status=in.(briefed,scheduled): short-notice bookings (inside the daily
    # prep cron's 12-36h lookahead) arrive still `scheduled` with no brief —
    # they get an inline brief below instead of silently never firing
    # (July 2026: booking opened to 24/7 with 15-min notice).
    due = sb_select(
        "interviews",
        f"status=in.(briefed,scheduled)"
        f"&scheduled_at=gte.{_iso(lo)}&scheduled_at=lte.{_iso(hi)}",
    )
    failures = 0
    for interview in due:
        when = _parse(interview["scheduled_at"])
        # A browser interview without a co-host is staged ahead and opened by
        # the Worker when the guest arrives. Everything else keeps its window.
        studio = ((interview.get("call_mode") or "webrtc") == "webrtc"
                  and not host_mode_enabled(interview))
        in_window = not when or when <= unlock_hi
        if not studio and not in_window:
            continue
        # Phone interviews keep the tight window: dialling a guest's phone
        # ten minutes early is not "unlocking a studio".
        if (interview.get("call_mode") or "webrtc") != "webrtc":
            if when and when > phone_hi:
                continue
        # Idempotency: a delayed/parallel tick must not double-call.
        # A run that was cancelled or failed is history, not an active run:
        # a guest who rebooked onto the same interview row must still be
        # fired (Sept 24 2026: Dr. Brandt sat in the studio because his
        # cancelled Sept 22 run blocked the new slot).
        active = sb_select("interview_runs",
                           f"interview_id=eq.{interview['id']}"
                           f"&status=not.in.(failed,cancelled)") or []
        # Oct 8 2026: a run staged for a slot the guest has since moved
        # (Jason Shumard and Priyanka Sharma were staged on Oct 6 for Oct 7
        # and rebooked to the 13th and 20th) would open a week later with a
        # week-old prompt: none of the lessons adopted in between, no
        # end-of-turn setting. Stage it again for the new time instead.
        stale = [r for r in active if r.get("status") == "staged"
                 and r.get("scheduled_for") and when
                 and _parse(r["scheduled_for"]) != when]
        for r in stale:
            sb_update("interview_runs", f"id=eq.{r['id']}&status=eq.staged",
                      {"status": "cancelled",
                       "disconnect_reason": "re-staged: the interview moved"})
            logger.info("Run %s was staged for %s; the interview moved to %s, "
                        "staging it again", r["id"], r["scheduled_for"],
                        interview["scheduled_at"])
        if [r for r in active if r not in stale]:
            logger.info("Interview %s already has an active run — skipping",
                        interview["id"])
            for r in active:
                if r not in stale:
                    refresh_staged_prompt(r, interview)
            if studio and in_window and not interview.get("reminder_sent_at"):
                start_time_email(interview)
            continue
        show = show_for(interview)
        try:
            app = sb_select("guest_applications",
                            f"id=eq.{interview['application_id']}")[0]
            show = show_for(interview, app)
            brief_rows = sb_select("interview_briefs",
                                   f"interview_id=eq.{interview['id']}")
            if is_closing_session(interview):
                brief = {}
            elif not brief_rows:
                # Short-notice booking: the daily prep cron never saw this
                # interview. Generate the brief inline (same code path as
                # the T-1d workflow) so Mira still calls; the guest gets
                # the prep email immediately instead of a day ahead.
                from generate_briefs import email_brief_to_guest, generate_brief
                logger.warning(
                    "Interview %s due with no brief (short-notice booking) — "
                    "generating inline", interview["id"])
                brief = generate_brief(interview, app)
                try:
                    email_brief_to_guest(interview, app, brief)
                except Exception:  # noqa: BLE001 — email is best-effort here
                    logger.exception("Inline brief email failed (non-fatal)")
                sb_update("interviews", f"id=eq.{interview['id']}",
                          {"status": "briefed",
                           "episode_thesis": brief["episode_thesis_draft"]})
            else:
                brief = brief_rows[0]
            # Sept 15 2026 (Erica Sell): the only reminder was an SMS with a
            # studio link and no way to say "not today". A guest who cannot
            # make it has to either reply to an email nobody is watching or
            # simply not turn up, and not turning up is what they choose. The
            # reminder now offers the other door, in the message and in the
            # text, two hours out — which is early enough to be useful.
            manage = manage_url(interview)
            # Sept 28 2026: this used to send the "in about two hours" email a
            # second time, ten minutes before the start. Only a guest who never
            # got the two-hour reminder (a short-notice booking) hears from Mira
            # here, and what they hear is true: we start in a few minutes.
            if in_window and not interview.get("reminder_sent_at"):
                try:
                    send_guest_reminder(interview, app, show, manage, soon=True)
                    sb_update("interviews", f"id=eq.{interview['id']}",
                              {"reminder_sent_at": _iso(_now())})
                except Exception:  # noqa: BLE001 — never blocks the fire
                    logger.exception("Start-time email failed for %s (non-fatal)",
                                     interview["id"])
            phone = to_e164(app.get("phone"))
            if not phone:
                if (interview.get("call_mode") or "webrtc") != "webrtc":
                    raise RuntimeError(
                        f"guest phone {app.get('phone')!r} is not a usable "
                        "number and this interview is phone-mode")
                # Browser interview: a bad number only costs the SMS and the
                # phone fallback, so let the studio go ahead and say so.
                logger.warning("Interview %s: guest phone %r unusable — studio "
                               "only, no phone fallback", interview["id"],
                               app.get("phone"))
            caller_id = interview.get("caller_id") or os.environ.get(
                "VOXIMPLANT_CALLER_ID", "")
            if not caller_id:
                raise RuntimeError("no caller_id (set VOXIMPLANT_CALLER_ID)")

            call_mode = (interview.get("call_mode") or "webrtc").strip()
            host_mode = host_mode_enabled(interview)
            run = insert_interview_run({
                "interview_id": interview["id"],
                "mira_system_prompt": compile_prompt_for(interview, app, brief),
                "session_kind": interview.get("session_kind") or "interview",
                # The length the guest asked for, in the room as well as in
                # the prompt: the scenario's time checks and hard cap read it.
                "planned_minutes": planned_minutes(interview, app),
                "voice_preset": "ara",
                # Oct 8 2026: the scenario has always read this off the run row
                # and nothing ever wrote it, so every interview ran on its 1.1 s
                # default. About ten interruptions an hour at 1.1 s, and Scott
                # Pulcini felt hurried; 1.3 s waits out a breath between clauses.
                "turn_detection": turn_detection(),
                # Oct 15 2026 (Grok Voice 3.0): the proper nouns the live
                # transcription should spell right. Read by the scenario into
                # audio.input.transcription.keyterms; [] sends nothing.
                "keyterms": keyterms_for(app, show, cohost_name()),
                "tools": mira_tools(interview, app),
                "guest_phone": phone,
                "caller_id": caller_id,
                "scheduled_for": interview["scheduled_at"],
                # Phase 2 co-host: the scenario dials this Voximplant user
                # into the conference (host_user column, migration
                # 20260906_cohost_conference.sql).
                "host_mode": host_mode,
                "host_user": os.environ.get("VOX_HOST_USER", "").strip() or "host",
                **room_clips(show),
                **({"status": "staged"} if studio
                   else {"status": "awaiting_guest"} if call_mode == "webrtc" else {}),
            })
            if host_mode:
                notify_host(interview, app, show,
                            when=("in 10 min" if call_mode == "webrtc" else "in 2 min"))

            if studio:
                logger.info("Interview %s (run %s, %s) staged; the studio opens "
                            "when the guest arrives: %s", interview["id"], run["id"],
                            show.slug, show.studio_url(interview["id"]))
                continue
            if call_mode == "webrtc":
                # WebRTC (default): no outbound dial. The run row is the
                # studio's green light — the guest's browser polls
                # /voices/studio-state, sees ready, and joins; the scenario
                # starts on the inbound call (CallAlerting) and flips the
                # run to in_progress itself.
                logger.info(
                    "Interview %s (run %s, %s) awaiting guest in the studio: "
                    "%s", interview["id"], run["id"], show.slug,
                    show.studio_url(interview["id"]))
                continue

            from voximplant.api_clients.voximplant_client import (
                start_interview_scenario,
            )
            result = start_interview_scenario(run["id"])
            sb_update("interview_runs", f"id=eq.{run['id']}", {
                "status": "fired",
                "fired_at": _iso(_now()),
                "voximplant_session_id": json.dumps(
                    result.get("result", result))[:512],
            })
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"status": "in_progress"})
            logger.info("Fired interview %s (run %s) for %s",
                        interview["id"], run["id"], app["name"])
        except Exception as exc:  # noqa: BLE001
            if not in_window:
                # Staging hours ahead: the next tick tries again. Only a
                # failure at the start time is the operator's problem.
                logger.exception("Staging failed for interview %s (will retry)",
                                 interview["id"])
                continue
            failures += 1
            logger.exception("Firing failed for interview %s", interview["id"])
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"status": "failed"})
            notify_operator(
                show.slack(f"interview {interview['id']} FAILED to fire: {exc}"),
                critical=True,
            )
    return failures


def start_time_email(interview: dict) -> None:
    """The "we start in a few minutes" email for a guest who never had the
    two-hour reminder (a short-notice booking), sent once, at the start."""
    try:
        app = sb_select("guest_applications", f"id=eq.{interview['application_id']}")[0]
        show = show_for(interview, app)
        send_guest_reminder(interview, app, show, manage_url(interview), soon=True)
        sb_update("interviews", f"id=eq.{interview['id']}",
                  {"reminder_sent_at": _iso(_now())})
    except Exception:  # noqa: BLE001 — never blocks anything
        logger.exception("Start-time email failed for %s (non-fatal)", interview["id"])


def _latest_run(interview_id: str) -> "dict | None":
    runs = sb_select("interview_runs",
                     f"interview_id=eq.{interview_id}&order=created_at.desc&limit=1")
    return runs[0] if runs else None


def _claim(interview_id: str, column: str) -> bool:
    """Set ``column`` only if it is still empty: two ticks never both send."""
    rows = sb_update("interviews", f"id=eq.{interview_id}&{column}=is.null",
                     {column: _iso(_now())})
    return bool(rows)


def start_notice_email(interview: dict, app: dict, show) -> "tuple[str, str]":
    """Five minutes before the start (Oct 16 2026, Patrick)."""
    import html as _h
    studio = show.studio_url(interview["id"]) + "&role=guest"
    phone_mode = (interview.get("call_mode") or "webrtc") != "webrtc"
    when = when_text(interview.get("scheduled_at", ""), interview.get("guest_timezone") or "")
    what = "closing session" if is_closing_session(interview) else "interview"
    first = _h.escape(first_name(app))
    if phone_mode:
        subject = f"I'll call you in about 5 minutes for {show.name}"
        body = (f"<p>Hi {first},</p><p>Our {what} starts in about five minutes"
                + (f" ({_h.escape(when)})" if when else "")
                + ". I'll call the number you gave us, so find a quiet spot and answer "
                "when it rings.</p>"
                f'<p>If you can, joining from a computer with headphones sounds much better than '
                f'a phone line: <a href="{studio}">your studio link</a> works right up to the start.</p>')
    else:
        subject = f"We start in 5 minutes: your {show.name} studio is open"
        body = (f"<p>Hi {first},</p><p>Our {what} starts in about five minutes"
                + (f" ({_h.escape(when)})" if when else "")
                + ", and the studio is open. I'm ready when you are.</p>"
                f'<p style="font-size:1.1em"><a href="{studio}"><strong>Join your interview here</strong></a></p>'
                "<p>Headphones on, and from your computer for the best sound.</p>"
                + str(studio_steps_html(studio)))
    body += ("<p>One reminder: it's your hour. Skip anything, take me anywhere, start "
             "any answer again, and anything you'd rather not have in the episode comes "
             "out afterwards.</p>"
             "<p>If anything gets in the way, just reply to this email and I'll see it.</p>"
             + mira_signature_html(show))
    return subject, body


def start_notice_sms(interview: dict, show, caller_id: str = "") -> str:
    studio = show.studio_url(interview["id"])
    what = "closing session" if is_closing_session(interview) else "interview"
    if (interview.get("call_mode") or "webrtc") != "webrtc":
        return (f"Mira here, from {show.name}. Our {what} starts in about 5 minutes. "
                f"I'll call you from {'this number' if not caller_id else caller_id}, "
                "so find a quiet spot. See you soon. Mira")
    return (f"Mira here, from {show.name}. Our {what} starts in about 5 minutes and the "
            f"studio is open: {studio} Headphones on, press Check my microphone, then "
            "Join. See you there. Mira")


def send_start_notices() -> int:
    """T-5: a text and an email to every guest who isn't already in the room."""
    lo, hi = _now() + START_NOTICE_AHEAD[0], _now() + START_NOTICE_AHEAD[1]
    due = sb_select("interviews",
                    "status=in.(briefed,scheduled)&start_notice_at=is.null"
                    f"&scheduled_at=gte.{_iso(lo)}&scheduled_at=lte.{_iso(hi)}")
    sent = 0
    for interview in due:
        try:
            run = _latest_run(interview["id"])
            if run and run.get("guest_joined_at"):
                continue                       # already with Mira
            if not _claim(interview["id"], "start_notice_at"):
                continue
            app_rows = sb_select("guest_applications", f"id=eq.{interview['application_id']}")
            app = app_rows[0] if app_rows else {}
            show = show_for(interview, app)
            if app.get("email"):
                subject, html = start_notice_email(interview, app, show)
                try:
                    # Like the studio-open nudge: between Mira and the guest.
                    send_email(app["email"], subject, html)
                except Exception:  # noqa: BLE001 — the text still goes
                    logger.exception("T-5 email failed for %s", interview["id"])
            phone = to_e164(app.get("phone"))
            if phone:
                from voximplant.api_clients.voximplant_client import send_sms
                caller_id = interview.get("caller_id") or os.environ.get("VOXIMPLANT_CALLER_ID", "")
                send_sms(phone, start_notice_sms(interview, show, caller_id),
                         source_number=caller_id or None)
            logger.info("T-5 notice for %s (%s)", interview["id"],
                        "email and text" if phone else "email only, no usable phone")
            sent += 1
        except Exception:  # noqa: BLE001 — a notice never stops the firing
            logger.exception("T-5 notice failed for %s", interview.get("id"))
    return sent


def call_guest_link(interview_id: str) -> str:
    """Patrick's one-click "have Mira call them". Must match callGuestLink()
    in workers/voices/src/index.ts: hex(HMAC_SHA256(ADMIN_TOKEN,
    "call-guest:" + id))[:40]. "" without ADMIN_TOKEN."""
    import hashlib
    import hmac
    token = os.environ.get("ADMIN_TOKEN", "").strip()
    if not token:
        return ""
    sig = hmac.new(token.encode("utf-8"), f"call-guest:{interview_id}".encode("utf-8"),
                   hashlib.sha256).hexdigest()[:40]
    return f"https://api.nerranetwork.com/voices/admin/call-guest?interview={interview_id}&sig={sig}"


def late_alert(interview: dict, app: dict, show, minutes: int) -> "tuple[str, str, str]":
    """(subject, html, sms) for Patrick: the guest hasn't opened the studio."""
    import html as _h
    who = (app.get("name") or "The guest").strip()
    when = pacific_time(interview.get("scheduled_at", ""))
    phone = to_e164(app.get("phone")) or ""
    studio = show.studio_url(interview["id"]) + "&role=guest"
    call = call_guest_link(interview["id"]) if phone else ""
    notice = "the five-minute text and email" if interview.get("start_notice_at") else "the reminders"
    subject = f"{show.short_label}: {who} hasn't opened the studio, {minutes} minutes in"
    parts = [f"<p>Hi Patrick,</p><p>{_h.escape(who)}'s interview was at {_h.escape(when)}. "
             f"{minutes} minutes in, they still haven't opened their studio link, after "
             f"{notice}.</p><p>What you can do now:</p><ul>"]
    if phone:
        parts.append(f'<li>Call or text them yourself: <a href="tel:{phone}">{_h.escape(phone)}</a></li>')
    if call:
        parts.append(f'<li><a href="{call}">Have Mira call them now</a> and do the interview by phone.</li>')
    if app.get("email"):
        parts.append(f"<li>Email them: {_h.escape(app['email'])}</li>")
    parts.append(f'<li>Their studio link, to send on: <a href="{studio}">{studio}</a></li></ul>'
                 f"<p>If nobody arrives, I'll send them the reschedule email {NO_SHOW_AFTER_MIN} "
                 "minutes after the start.</p><p>Mira</p>")
    sms = (f"{show.short_label}: {who} hasn't opened the studio, {minutes} min after the start."
           + (f" Phone {phone}." if phone else " No phone on file.")
           + (f" Have Mira call them: {call}" if call else ""))
    return subject, "".join(parts), sms


def send_late_alerts() -> int:
    """T+5: Patrick hears at once about a guest who never opened the studio.
    A guest who opened it and is stuck is the studio page's own alert
    (setup_check.stuck_alerted_at), so it is not sent twice."""
    now = _now()
    lo, hi = now - LATE_ALERT_AFTER[1], now - LATE_ALERT_AFTER[0]
    due = sb_select("interviews",
                    "status=in.(briefed,scheduled)&call_mode=eq.webrtc&late_alert_at=is.null"
                    f"&scheduled_at=gte.{_iso(lo)}&scheduled_at=lte.{_iso(hi)}")
    sent = 0
    for interview in due:
        try:
            run = _latest_run(interview["id"])
            if run and (run.get("guest_joined_at")
                        or run.get("status") not in ("staged", "awaiting_guest")):
                continue
            check = interview.get("setup_check") if isinstance(interview.get("setup_check"), dict) else {}
            if check.get("stuck_alerted_at"):
                continue                       # the page already told him
            if run and run.get("status") == "awaiting_guest":
                continue                       # the page is open: its own alert covers it
            if not _claim(interview["id"], "late_alert_at"):
                continue
            app_rows = sb_select("guest_applications", f"id=eq.{interview['application_id']}")
            app = app_rows[0] if app_rows else {}
            show = show_for(interview, app)
            start = _parse(interview.get("scheduled_at"))
            minutes = max(1, round((now - start).total_seconds() / 60)) if start else 5
            subject, html, sms = late_alert(interview, app, show, minutes)
            try:
                send_email(OPERATOR_EMAIL, subject, html, cc_guest_team=False)
            except Exception:  # noqa: BLE001
                logger.exception("late-guest email failed for %s", interview["id"])
            phone = operator_phone()
            if phone:
                from voximplant.api_clients.voximplant_client import send_sms
                send_sms(phone, sms, source_number=interview.get("caller_id")
                         or os.environ.get("VOXIMPLANT_CALLER_ID", "") or None)
            notify_operator(show.slack(f"{app.get('name') or 'guest'} hasn't opened the "
                                       f"studio, {minutes} min after the start"))
            sent += 1
        except Exception:  # noqa: BLE001
            logger.exception("late-guest alert failed for %s", interview.get("id"))
    return sent


NO_SHOW_AFTER_MIN = 40


def sweep_browser_no_shows() -> int:
    """Oct 5 2026, Stan Lewis. A browser interview whose guest never opened
    the studio left its run at awaiting_guest forever: nobody wrote to him,
    nobody told Patrick, and the interview sat at "briefed". The phone path
    has always had a no-show (the call goes unanswered); this is the same
    thing for the studio, forty minutes after the start with no one in."""
    cutoff = _iso(_now() - dt.timedelta(minutes=NO_SHOW_AFTER_MIN))
    oldest = _iso(_now() - dt.timedelta(days=2))
    due = sb_select("interviews",
                    "status=in.(briefed,scheduled)&call_mode=eq.webrtc"
                    f"&scheduled_at=lte.{cutoff}&scheduled_at=gte.{oldest}")
    handled = 0
    for interview in due:
        try:
            runs = sb_select("interview_runs",
                             f"interview_id=eq.{interview['id']}&order=created_at.desc&limit=1")
            run = runs[0] if runs else None
            if not run or run.get("status") not in ("awaiting_guest", "staged"):
                continue
            sb_update("interview_runs", f"id=eq.{run['id']}",
                      {"status": "failed", "disconnect_reason": "no_show"})
            app_rows = sb_select("guest_applications", f"id=eq.{interview['application_id']}")
            app = app_rows[0] if app_rows else {}
            show = show_for(interview, app)
            no_shows = int(interview.get("no_show_count") or 0) + 1
            status = "missed" if no_shows < 2 else "cancelled"
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"status": status, "no_show_count": no_shows})
            if no_shows < 2 and app.get("email"):
                subject, html = missed_email(interview, app, show, first_name(app))
                send_email(app["email"], subject, html, cc_operator=True,
                           cc=[str(app.get("publicist_email") or "")])
                notify_operator(show.slack(
                    f"{app.get('name') or 'guest'} didn't come into the studio "
                    f"(no-show #{no_shows}); Mira sent the reschedule email"))
            else:
                if app.get("id"):
                    sb_update("guest_applications", f"id=eq.{app['id']}", {"status": "lapsed"})
                notify_operator(show.slack(
                    f"{app.get('name') or 'guest'} second no-show; application lapsed"))
            handled += 1
        except Exception:  # noqa: BLE001 — one guest never stops the sweep
            logger.exception("no-show sweep failed for %s", interview.get("id"))
    return handled


def main() -> int:
    send_reminders()
    try:
        sweep_browser_no_shows()
    except Exception:  # noqa: BLE001 — firing matters more
        logger.exception("no-show sweep failed")
    failed = fire_due_interviews()
    # After the fire, so a run that has just been created is the one checked.
    for job in (send_start_notices, send_late_alerts):
        try:
            job()
        except Exception:  # noqa: BLE001 — never fails the fire job
            logger.exception("%s failed", job.__name__)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
