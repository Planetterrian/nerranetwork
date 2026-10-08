#!/usr/bin/env python3
"""Interview firing cron (nerra_voices_fire_interview.yml, every 5 min).

Two duties per tick:

1. **T-2h SMS reminder** — interviews ~2h out get one SMS from Mira's
   caller ID (``reminder_sent_at`` guards the once-only).
2. **Fire** — interviews whose ``scheduled_at`` falls inside the next
   5-minute window: compile Mira's system prompt from the brief, create the
   ``interview_runs`` row, and start the Voximplant scenario with the run id
   as customData.

GitHub cron is best-effort (spec §5.2 note): the firing window is computed
here as [now - grace, now + 5 min] so a delayed tick still fires anything
it missed, and the ``interview_runs`` uniqueness check keeps a double tick
from double-calling the guest.
"""

from __future__ import annotations

import datetime as dt
import json
import os

from common import (  # noqa: E402
    OPERATOR_EMAIL, ROOT, carry_the_show_block, cohost_name, load_prompt, logger,
    mira_signature_html, guest_notes_block, guest_agenda_block, pacific_time,
    notify_operator, GUEST_AUDIO_HTML, studio_steps_html,
    operator_phone, render_email, sb_insert, sb_select, sb_update, send_email,
    show_for, to_e164, guest_details,
)
from learning import lessons_block, relapse_recap, variety_block  # noqa: E402
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
    "the conversation. If {{cohost_first}} says 'let's pause' or 'hold on', "
    "stop talking and wait for him."
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
    "   - {{cohost_name}}, your co-host, by name: a real person, the founder "
    "of the network, who will jump in with his own questions. If he is "
    "already in the room, hand him a beat to say hello himself;\n"
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
    {
        "type": "function",
        "name": "fact_check_claim",
        "description": (
            "Quietly research a checkable thing the guest just said (an "
            "event, number, case or person) in the background. Returns at "
            "once: carry on talking and say nothing about it. Anything useful "
            "arrives later as a [RESEARCH NOTE]; if nothing arrives, never "
            "mention the search."
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
    },
]


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
    )


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


def is_closing_session(interview: dict) -> bool:
    return (interview.get("session_kind") or "interview") == "closing"


def turn_detection() -> dict:
    """End-of-turn silence Mira waits for, per run (MIRA_TURN_SILENCE_MS)."""
    try:
        ms = int(os.environ.get("MIRA_TURN_SILENCE_MS") or 1300)
    except ValueError:
        ms = 1300
    return {"silence_duration_ms": max(600, min(2500, ms))}


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
    return load_prompt(
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
        # What previous guests said, so she can put one of them to this one.
        carry_the_show=carry_the_show_block(show, exclude_email=app.get("email", "")),
        # Sept 17 2026: the standing lessons go near the TOP, right after the
        # guest, not on the end of four thousand words of craft. The prompt
        # was cut to a third so they carry the weight they are meant to.
        lessons=lessons_block(show.slug),
    ) + variety_block(show.slug) + relapse_recap(show.slug)


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
    if soon:
        subject = (f"I'll call you in a few minutes for {show.name}" if phone_mode
                   else f"Your {show.name} studio is open")
        lead = ("I'm about to call your phone for our interview. Find a quiet spot "
                "and answer when it rings." if phone_mode else
                "The studio is open and I'm ready when you are. We start in about "
                "ten minutes.")
    else:
        subject = f"Our interview on {show.name} is in about two hours"
        lead = (f"We're on for {_h.escape(when)}, about two hours from now."
                if when else "We're on in about two hours.")
    parts = [f"<p>Hi {first},</p>", f"<p>{lead}</p>"]
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
    send_email(app.get("email", ""), subject, body)


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
        if sb_select("interview_runs",
                     f"interview_id=eq.{interview['id']}"
                     f"&status=not.in.(failed,cancelled)"):
            logger.info("Interview %s already has an active run — skipping",
                        interview["id"])
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
            run = sb_insert("interview_runs", {
                "interview_id": interview["id"],
                "mira_system_prompt": (compile_closing_prompt(interview, app)
                                       if is_closing_session(interview)
                                       else compile_mira_prompt(interview, app, brief)),
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
                "tools": MIRA_TOOLS,
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
                booking = (os.environ.get("CALCOM_BOOKING_URL_NERRA_VOICES", "")
                           if show.slug == "nerra_voices" else "") \
                    or os.environ.get("CALCOM_BOOKING_URL", "")
                html = render_email("voices_interview_reminder.j2", show=show,
                                    guest_name=first_name(app), missed=True,
                                    booking_url=booking)
                send_email(app["email"],
                           f"Sorry we missed each other: pick a new time for {show.name}",
                           html, cc_operator=True,
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
    return 1 if fire_due_interviews() else 0


if __name__ == "__main__":
    raise SystemExit(main())
