#!/usr/bin/env python3
"""Cut the episode without being asked (Sept 15 2026).

Every episode so far has been produced because somebody remembered to ask
for it. The interview ends, the transcript lands, and then a human decides
where it starts, where it ends, what to drop, and what Mira should say at
either end. Those are real editorial judgements, but they are judgements
made from the transcript, and the transcript is right here.

So this runs straight after post-interview processing, in the same job, and
writes three things:

* ``narration/<slug>.json`` — Mira's introduction and close, written from
  what the guest actually said.
* ``edl/<slug>.json`` — where the conversation starts, where it ends, and
  which stretches come out, each with a reason.
* an ``episode_records`` row — the content lake. What the guest claimed,
  what they predicted and by when, what we never got to ask. Every guest so
  far has asked to come back in six months; this is what makes that worth
  doing, because the next conversation can open with "last time you said".

The files land on the runner and the next two steps of the same workflow
read them, so nothing needs committing. The decisions are also stored in
``episode_edits``, which is what an explanation or a re-run reads.

    python pipelines/voices/auto_edit.py <interview_run_id>
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from address import spoken as spoken_address  # noqa: E402
from common import (  # noqa: E402
    guest_links, llm, load_prompt, logger, parse_json_lenient, sb_insert,
    sb_select, sb_update, show_for,
)

NARRATION_DIR = Path(__file__).parent / "narration"
EDL_DIR = Path(__file__).parent / "edl"

# How much slack to leave around a cut so a word is never clipped.
EDGE_PAD_SEC = 0.6
# A gap has to be worth the seam. Below this, leave it in — a cut you can
# hear is worse than two seconds of nothing.
MIN_DROP_SEC = 25.0
# ...except in the first two minutes, where the technical check-ins live and
# a four-second "can you hear me / I can hear you" is exactly what to take out.
EARLY_WINDOW_SEC = 120.0
EARLY_DROP_MIN_SEC = 2.0
# A cold-open clip long enough to be a thought, short enough to be a hook.
COLD_OPEN_SEC = (4.0, 20.0)


def recorded_on(run: dict, interview: dict) -> dt.date:
    """The day the conversation happened, in Pacific Time. Oct 27 2026: the
    slug was dated from the run row's creation, which happens the day before
    (Glenn Broder, recorded Oct 27, cut as glenn_broder_2026_10_26)."""
    from zoneinfo import ZoneInfo
    for value in ((run or {}).get("guest_joined_at"), (interview or {}).get("scheduled_at"),
                  (run or {}).get("fired_at"), (run or {}).get("created_at")):
        if not value:
            continue
        # "+00" as Postgres prints it is not ISO on every Python: make it "+00:00".
        text = re.sub(r"([+-]\d{2})$", r"\1:00", str(value).strip().replace("Z", "+00:00"))
        try:
            t = dt.datetime.fromisoformat(text)
        except (TypeError, ValueError):
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        return t.astimezone(ZoneInfo("America/Vancouver")).date()
    return dt.date.today()


def _slug(name: str, when: dt.date) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", (name or "guest").lower()).strip("_")
    return f"{base}_{when:%Y_%m_%d}"


def _ours(slug: str) -> bool:
    """True when the EDL of this name was written by a previous auto cut."""
    try:
        rows = sb_select("episode_edits", f"slug=eq.{slug}&select=generated_by")
        return bool(rows) and rows[0].get("generated_by") == "auto_edit"
    except Exception:  # noqa: BLE001
        return False


def _leg_offset(run: dict, role: str = "guest") -> float:
    """Seconds between the room opening and the guest leg we are cutting.

    The EDL addresses the guest's own recording, whose clock starts when he
    joined; the transcript is on the room's clock. When someone rejoins, the
    two differ by minutes (John Capobianco: 428 seconds), which is the
    difference between an episode and a shuffled one.
    """
    try:
        from post_interview import duration_seconds, room_offsets  # noqa: F401
    except Exception:  # noqa: BLE001
        return 0.0
    log = run.get("grok_session_log") or {}
    # Once every track is placed on the guest leg's clock, the transcript IS
    # on that clock and there is nothing left to convert. Subtracting the
    # guest's join a second time moved every cut in Adrian Wolfberg's
    # episode 268 seconds early: it opened four and a half minutes into the
    # conversation and stopped five minutes before he finished (Sept 16
    # 2026).
    if ((log.get("tracks") or {}).get("alignment")) is not None:
        return 0.0
    tracks = (log.get("tracks") or {}).get("durations") or {}
    seconds = tracks.get(role)
    offsets = room_offsets(run, {role: seconds} if seconds else None)
    return float(offsets.get(role, 0.0))


def _context(run_id: str) -> dict:
    runs = sb_select("interview_runs", f"id=eq.{run_id}")
    if not runs:
        raise SystemExit(f"no interview_runs row {run_id}")
    run = runs[0]
    interview = sb_select("interviews", f"id=eq.{run['interview_id']}")[0]
    app = sb_select("guest_applications", f"id=eq.{interview['application_id']}")[0]
    pkgs = sb_select("editorial_packages",
                     f"interview_run_id=eq.{run_id}&order=created_at.desc")
    if not pkgs:
        raise SystemExit(f"no editorial package for run {run_id} — has "
                         "post_interview.py finished?")
    return {"run": run, "interview": interview, "app": app, "package": pkgs[0]}


def _previous(app: dict) -> str:
    """What this guest said last time, when there was a last time."""
    email = (app.get("email") or "").lower()
    if not email:
        return ""
    rows = sb_select("episode_records",
                     f"guest_email=eq.{email}&order=created_at.desc&limit=3")
    if not rows:
        return ""
    out = []
    for row in rows:
        out.append(f"- {row.get('recorded_on')}: {row.get('summary', '')}")
        for pred in (row.get("predictions") or [])[:4]:
            out.append(f"    predicted: {pred.get('prediction')} "
                       f"(by {pred.get('due_on')})")
    return "THIS GUEST HAS BEEN ON BEFORE:\n" + "\n".join(out)


_LINE = re.compile(r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*([^:]+):\s*(.*)$")
WORD_SEC = 0.45      # a spoken word, roughly
LINE_TAIL_SEC = 1.2  # breath after the last word before the cut


END_SNAP_SEC = 150.0   # how far back a model end is treated as "near the close"


def _last_guest_turn(transcript: str) -> float | None:
    """The room-clock second at which the last non-host line starts."""
    latest = None
    for raw in transcript.splitlines():
        m = _LINE.match(raw.strip())
        if not m:
            continue
        h, mm, ss, who, _text = m.groups()
        if who.strip().lower() == "mira":
            continue
        at = (int(h) * 3600 + int(mm) * 60 + int(ss)) if ss else (int(h) * 60 + int(mm))
        latest = float(at)
    return latest


# ---------------------------------------------------------------------------
# What the guest asked for comes out, whatever its length (Oct 21 2026)
# ---------------------------------------------------------------------------
#
# Mira tells every guest at the open that they can start an answer again,
# skip a question or ask for something to be cut. The edit kept that promise
# only when the model noticed and only when the stretch cleared the
# twenty-five-second floor below, so a two-second "scratch that" survived
# into the episode. The room transcript is read for the request itself,
# the span it implies is built from the lines around it, and such a drop is
# never subject to the floor. The model's own drops are kept; a request the
# model also found is merged with its span.
RESTART_RE = re.compile(
    r"\b(let me (start|try|do) (that |this )?(over|again)|(can|could|may) i (start|do|try|say|take) "
    r"(that |this )?(over|again)|start (that |this )?(over|again)|scratch that|"
    r"let me (rephrase|redo|re-?do)|i'?ll (start|say) (that |this )?(over|again)|"
    r"take two|from the top)\b", re.I)
CUT_RE = re.compile(
    r"\b((can|could) (we|you) (cut|take|leave|edit|keep) (that|this|it)( (out|off))?|"
    r"off the record|don'?t (use|include|keep|publish) (that|this)|"
    r"(cut|strike|remove|delete) (that|this)( (part|bit|out))?|"
    r"(leave|take) (that|this) (out|off)|not for the (show|episode|recording)|"
    r"i'?d rather (that|this) (not|didn'?t|wasn'?t))\b", re.I)
DECLINE_RE = re.compile(
    r"^(i'?d rather not|i'?ll pass|pass on that|let'?s not go there|"
    r"i'?d prefer not|i can'?t (talk|speak|comment) (about|on) that|"
    r"no comment|skip (that|this) one)\b", re.I)
# A request is about what was just said: the span never reaches further back.
REQUEST_SPAN_MAX_SEC = 180.0
# Mira's acknowledgment of a request ("Done, that stays out") is part of the
# exchange and comes out with it, when it is this short.
ACK_MAX_WORDS = 12


def _lines(transcript: str) -> list:
    out = []
    for raw in transcript.splitlines():
        m = _LINE.match(raw.strip())
        if not m:
            continue
        h, mm, ss, who, text = m.groups()
        at = (int(h) * 3600 + int(mm) * 60 + int(ss)) if ss else (int(h) * 60 + int(mm))
        out.append((float(at), who.strip(), text.strip()))
    return out


def _line_end(lines: list, i: int) -> float:
    """Where line ``i`` stops: the next line's start, or the word estimate."""
    at, _who, text = lines[i]
    if i + 1 < len(lines):
        return lines[i + 1][0] - 0.25
    return at + WORD_SEC * max(1, len(text.split())) + LINE_TAIL_SEC


def guest_requests(transcript: str, host: str = "Mira") -> list:
    """``[{from_sec, to_sec, why, kind, guest_request: True}]`` on the room
    clock, one per restart, cut request or declined question in the
    transcript, in time order. Never raises: an unparseable transcript gives
    an empty list, and the model's drops still apply."""
    lines = _lines(transcript)
    found = []
    for i, (at, who, text) in enumerate(lines):
        if who.lower() == host.lower():
            continue
        kind = ("restart" if RESTART_RE.search(text) else
                "cut" if CUT_RE.search(text) else
                "decline" if DECLINE_RE.search(text) else "")
        if not kind:
            continue
        # Back to the start of the guest's turn (their consecutive lines),
        # and for a cut or a decline to the host's question that led into it.
        j = i
        while j > 0 and lines[j - 1][1].lower() == who.lower() \
                and at - lines[j - 1][0] <= REQUEST_SPAN_MAX_SEC:
            j -= 1
        if kind in ("cut", "decline") and j > 0 and lines[j - 1][1].lower() == host.lower() \
                and at - lines[j - 1][0] <= REQUEST_SPAN_MAX_SEC:
            j -= 1
        start = lines[j][0]
        # Forward over the request line, and the host's short acknowledgment.
        k = i
        # ...but never over a question: "Of course. Where did pricing go
        # next?" is an acknowledgment AND the next question, and the
        # question has to survive for its answer to make sense.
        if k + 1 < len(lines) and lines[k + 1][1].lower() == host.lower() \
                and len(lines[k + 1][2].split()) <= ACK_MAX_WORDS \
                and "?" not in lines[k + 1][2]:
            k += 1
        end = _line_end(lines, k)
        if kind == "restart":
            # The retake starts where the next line of theirs begins; the
            # request itself and the aborted attempt go, the retake stays.
            end = lines[k + 1][0] - 0.25 if k + 1 < len(lines) else end
        if end <= start:
            continue
        found.append({"from_sec": round(start, 2), "to_sec": round(end, 2),
                      "kind": kind, "guest_request": True,
                      "why": f"the guest asked ({kind}): \"{text[:120]}\""})
    return found


def merge_drops(model_drops: list, requests: list) -> list:
    """The model's drops plus the guest's requests, overlapping spans merged
    and a merged span inheriting the request's exemption from the floor."""
    rows = [dict(d) for d in (model_drops or []) if d.get("from_sec") is not None
            and d.get("to_sec") is not None]
    for r in requests:
        rows.append(dict(r))
    rows.sort(key=lambda d: float(d["from_sec"]))
    merged: list = []
    for d in rows:
        if merged and float(d["from_sec"]) <= float(merged[-1]["to_sec"]):
            last = merged[-1]
            last["to_sec"] = max(float(last["to_sec"]), float(d["to_sec"]))
            last["guest_request"] = bool(last.get("guest_request") or d.get("guest_request"))
            if d.get("why") and d["why"] not in str(last.get("why", "")):
                last["why"] = (str(last.get("why", "")) + " " + d["why"]).strip()
        else:
            merged.append(d)
    return merged


def _where_it_closes(transcript: str, end_sec: float, room_end: float,
                     why: str) -> tuple[float, str]:
    """The end of the episode's conversation, and a note when it is early.

    Sept 22 2026. Three episodes have now ended mid-sentence — Sheldon Poon
    twice, Meridan Zerner once — because the cutter chose an end a few seconds
    short and nothing questioned it. Patrick's rule: an episode runs to the
    close of the conversation unless he or the guest asks otherwise, or there
    is a reason worth stating. So the guest's final turn is the default. A
    model end within a couple of minutes of it is treated as pointing AT the
    close and snapped there; an end further back than that is a deliberate
    early finish, which is allowed but is written into the edit so it shows up
    at gate 1 rather than being discovered by the guest.
    """
    last_turn = _last_guest_turn(transcript)
    if last_turn is None:
        return _after_the_line(transcript, end_sec, room_end), ""
    to_the_close = _after_the_line(transcript, last_turn, room_end)
    if end_sec >= last_turn - END_SNAP_SEC:
        return to_the_close, ""
    chosen = _after_the_line(transcript, end_sec, room_end)
    note = (f"ENDS EARLY: cut at {chosen / 60:.0f} min, "
            f"{(to_the_close - chosen) / 60:.0f} min before the guest stopped "
            f"talking — {why or 'no reason given'}")
    logger.warning("auto_edit: %s", note)
    return chosen, note

def transcript_of(ctx: dict) -> str:
    return (ctx.get("package") or {}).get("transcript_raw") or ""


def _after_the_line(transcript: str, end_sec: float,
                    until: float | None = None) -> float:
    """Where the episode's conversation ends, given the model's end_sec.

    The transcript stamps where each line STARTS, so end_sec is the start
    of some line and a cut there loses the line: Sheldon Poon's episode
    ended on "...the quality and the amount" with "that we can produce" on
    the floor (Sept 17 2026). And a thought is often several lines — the
    recogniser breaks a long answer at every pause — so the guest is let
    run to the end of their turn: every consecutive line of theirs, up to
    the start of the next speaker's line. If the model pointed at Mira's
    sign-off, the cut is pulled back to the guest's last turn; her live
    "that's the end of the recording" is for the guest, not the listener,
    and the produced outro closes the episode."""
    lines = []
    for raw in transcript.splitlines():
        m = _LINE.match(raw.strip())
        if not m:
            continue
        h, mm, ss, who, text = m.groups()
        at = (int(h) * 3600 + int(mm) * 60 + int(ss)) if ss else (int(h) * 60 + int(mm))
        lines.append((float(at), who.strip(), text))
    if not lines:
        return end_sec
    idx = max((i for i, (at, _w, _t) in enumerate(lines) if at <= end_sec), default=None)
    if idx is None:
        return end_sec
    host = "mira"
    while idx > 0 and lines[idx][1].lower() == host:
        idx -= 1
    # Run forward through the same speaker's consecutive lines.
    who = lines[idx][1].lower()
    last = idx
    while last + 1 < len(lines) and lines[last + 1][1].lower() == who:
        last += 1
    at, _who, text = lines[last]
    spoken = at + WORD_SEC * max(1, len(text.split())) + LINE_TAIL_SEC
    # Sept 22 2026, Meridan Zerner. Her closing line ran from 15:50 to 16:04 —
    # fourteen seconds — and the word-count estimate put it at nine, so the
    # cut landed at 959.3s and took "It is complex" off the end. Sheldon Poon
    # lost eight seconds the same way. The estimate was being used as a CAP,
    # and it is the one number here that is a guess: the transcript's own next
    # timestamp is a measurement. Someone else starting to speak is the only
    # hard evidence that this speaker stopped, so that boundary wins and the
    # estimate can only ever extend the cut, never shorten it.
    if last + 1 < len(lines):
        # Whoever speaks next is the measurement, so it decides — in both
        # directions. Short of it, the estimate was wrong and the guest loses
        # words. Past it, the episode would run into Mira's live "that's the
        # end of the recording", which belongs to the guest and not to the
        # listener; the produced outro closes the episode instead.
        return lines[last + 1][0] - 0.25
    # Nothing follows them on the tape, so the tape's end is where they
    # stopped. Trailing silence is trimmed when the piece is cut.
    return float(until) if until else spoken


def plan(ctx: dict) -> dict:
    run, interview, app, package = (ctx["run"], ctx["interview"],
                                    ctx["app"], ctx["package"])
    show = show_for(interview, app)
    transcript = package.get("transcript_raw") or ""
    if len(transcript) < 2000:
        raise SystemExit("transcript too short to cut from")
    raw = llm(
        load_prompt("auto_edit.txt", show=show,
                    guest_name=app.get("name", ""),
                    guest_address=spoken_address(app),
                    guest_title=app.get("title", ""),
                    guest_organization=app.get("organization", "") or "",
                    guest_bio=app.get("bio", "") or "",
                    guest_links="\n".join(f"- {l['label']}: {l['url']}"
                                          for l in guest_links(app)) or "(none)",
                    cohost_name=(run.get("cohost_name")
                                 or interview.get("cohost_name") or "Patrick Novak"),
                    episode_thesis=interview.get("episode_thesis", "") or "",
                    previous=_previous(app),
                    transcript=transcript),
        temperature=0.4, max_tokens=6000,
    )
    out = parse_json_lenient(raw)
    if not isinstance(out, dict) or "intro" not in out or "outro" not in out:
        raise SystemExit("auto_edit pass did not return intro and outro")
    out["intro"] = _drop_borrowed_open(str(out["intro"]), transcript)
    out = on_the_room_clock(out, transcript)
    for key in ("intro", "outro"):
        out[key] = only_their_domains(str(out.get(key) or ""), app)
    if isinstance(out.get("cold_open"), dict) and out["cold_open"].get("lead"):
        out["cold_open"]["lead"] = only_their_domains(str(out["cold_open"]["lead"]), app)
    return out


# ---------------------------------------------------------------------------
# Numbers on the room's clock, and only the guest's own addresses (Oct 27 2026)
# ---------------------------------------------------------------------------
#
# Glenn Broder's cut opened on "...of school districts. And I have yet to get a
# good answer to that question." The model meant his line at [16:00.9] and
# wrote 1600.9: minutes and seconds read as seconds, a clip from 26:40 instead.
# Its own rationale described the right line, so the clip is now anchored on
# the words: the model gives the clip's words with its times, and the times
# are checked against where those words are in the transcript.
#
# The same cut's close sent listeners to "humanjudgment.ai", which is not his
# and was in none of his links (his only link was LinkedIn). The prompt already
# said not to; this makes it so.

from edit_transcript import parse_lines, stamp_seconds  # noqa: E402

ANCHOR_SLACK_SEC = 20.0


def _norm_words(text: str) -> list:
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def _find_quote(quote: str, transcript: str, who_not: str = "Mira") -> float | None:
    """The room second where the guest's line carrying ``quote`` starts (the
    best match of its first eight words), or None."""
    want = _norm_words(quote)[:8]
    if len(want) < 3:
        return None
    best = None
    lines = [l for l in parse_lines(transcript) if not l[1].lower().startswith(who_not.lower())]
    for i, (at, _who, text) in enumerate(lines):
        # A quote can start at the end of one line and run into the next.
        here = _norm_words(text + " " + (lines[i + 1][2] if i + 1 < len(lines) else ""))
        for j in range(len(here)):
            run = here[j:j + len(want)]
            hits = sum(1 for a, b in zip(run, want) if a == b)
            if hits >= max(3, int(len(want) * 0.75)) and (best is None or hits > best[0]):
                best = (hits, at)
    return best[1] if best else None


def _mmss(x: float) -> float:
    whole = int(x)
    return float(whole // 100 * 60 + whole % 100) + (x - whole)


def _looks_mmss(x: float) -> bool:
    return x >= 100 and int(x) % 100 < 60


def on_the_room_clock(out: dict, transcript: str) -> dict:
    """Every time the model gave, as seconds on the room's clock: "MM:SS"
    strings converted; a number past the end of the room read as minutes and
    seconds; the cold open moved onto the words it quotes."""
    last = max((at for at, _w, _t in parse_lines(transcript)), default=None)

    def sec(v):
        x = stamp_seconds(v)
        if x is None:
            return v
        if last is not None and x > last + 60 and _looks_mmss(x):
            x = _mmss(x)
        return x
    for key in ("start_sec", "end_sec"):
        if key in out:
            out[key] = sec(out[key])
    for d in out.get("drop") or []:
        if isinstance(d, dict):
            for key in ("from_sec", "to_sec"):
                if key in d:
                    d[key] = sec(d[key])
    co = out.get("cold_open")
    if isinstance(co, dict):
        try:
            a, b = float(sec(co.get("from_sec"))), float(sec(co.get("to_sec")))
        except (TypeError, ValueError):
            out["cold_open"] = None
            return out
        anchor = _find_quote(str(co.get("quote") or ""), transcript)
        if anchor is not None and abs(a - anchor) > ANCHOR_SLACK_SEC:
            if _looks_mmss(a) and abs(_mmss(a) - anchor) <= ANCHOR_SLACK_SEC:
                logger.warning("auto_edit: cold open %.1f-%.1f read as minutes and "
                               "seconds (%.1f-%.1f): that is where its words are",
                               a, b, _mmss(a), _mmss(b))
                a, b = _mmss(a), _mmss(b)
            else:
                logger.warning("auto_edit: cold open %.1f-%.1f is not where its words "
                               "are (%.1f) — moved onto them", a, b, anchor)
                a, b = anchor, anchor + max(4.0, min(b - a, COLD_OPEN_SEC[1]))
        elif anchor is None and co.get("quote"):
            logger.warning("auto_edit: the cold open's words are not in the transcript "
                           "— no cold open rather than the wrong one")
            out["cold_open"] = None
            return out
        co["from_sec"], co["to_sec"] = a, b
    return out


_DOMAIN = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:com|ai|io|org|net|co|ca|dev|app|tech|me|"
                     r"xyz|us|uk|info|biz|tv|fm|news|studio|media|so|gg))\b", re.I)
_SPOKEN = re.compile(r"\b([a-z0-9-]+(?:\s+[a-z0-9-]+){0,3})\s+dot\s+(com|ai|io|org|net|co|ca|"
                     r"dev|app|tech|me|xyz|us|uk|info|tv|fm)\b", re.I)
_SOCIAL = {"linkedin.com": "LinkedIn", "x.com": "X", "twitter.com": "X",
           "instagram.com": "Instagram", "youtube.com": "YouTube"}


def _registrable(host: str) -> str:
    host = host.lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def only_their_domains(text: str, app: dict) -> str:
    """``text`` with any sentence that names a website the guest never gave us
    replaced by where they can actually be found (their profile, through the
    episode notes), or dropped when they gave us nothing."""
    if not text:
        return text
    from urllib.parse import urlparse
    links = guest_links(app or {})
    allowed = {"nerranetwork.com"}
    social = None
    for l in links:
        host = _registrable(urlparse(str(l.get("url") or "")).netloc)
        if host:
            allowed.add(host)
            if host in _SOCIAL and social is None:
                social = _SOCIAL[host]
    first = (str((app or {}).get("name") or "").split() or ["them"])[0]
    fallback = (f"You can find {first} on {social}; the link is in the episode notes."
                if social else
                (f"You can find {first} through the links in the episode notes." if links else ""))

    def named(sentence: str) -> list:
        found = [m.group(1) for m in _DOMAIN.finditer(sentence)]
        found += ["".join(m.group(1).split()).lower() + "." + m.group(2).lower()
                  for m in _SPOKEN.finditer(sentence)]
        return [_registrable(d) for d in found]
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        bad = [d for d in named(sentence) if d not in allowed
               and not any(d.endswith("." + a) for a in allowed)]
        if bad:
            logger.warning("auto_edit: narration named %s, which is not one of the "
                           "guest's links — replaced", ", ".join(bad))
            if fallback and fallback not in out:
                out.append(fallback)
            continue
        out.append(sentence)
    return " ".join(x for x in out if x).strip()


def _spoken(transcript: str, until_sec: float = 180.0) -> list[str]:
    """Normalised text of everything said in the room's first few minutes.

    Uses the module's own ``_LINE`` — this had its own copy of that regex for
    about an hour on Sept 22 2026, which shadowed the real one and quietly
    broke ``_after_the_line``, the code that decides where an episode ends.
    """
    said = []
    for line in transcript.splitlines():
        m = _LINE.match(line.strip())
        if not m:
            continue
        h, mm, ss, _who, turn = m.groups()
        # "[06:53]" is minutes and seconds; "[1:02:33]" adds the hour.
        at = (int(h) * 3600 + int(mm) * 60 + int(ss)) if ss else (int(h) * 60 + int(mm))
        if at > until_sec:
            break
        text = _normalise(turn)
        if text:
            said.append(text)
        # One transcript line often holds several sentences ("Thank you. Thank
        # you for having me. I am based in South Florida."), and a narration
        # can borrow from the second one. Each sentence counts as a start too.
        parts = re.split(r"(?<=[.!?])\s+", turn.strip())
        if len(parts) > 1:
            for at in range(1, len(parts)):
                tail = _normalise(" ".join(parts[at:]))
                if tail:
                    said.append(tail)
    return said


def _normalise(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split())


def _drop_borrowed_open(intro: str, transcript: str) -> str:
    """Take the room's own warm-up back off the front of the narration.

    Sept 22 2026, Viktor Popovic. His episode's written introduction began
    "Thank you. Thank you for having me. I am based in South Florida. This is
    Nerra Voices from the Nerra Network. I'm Mira..." — the first three
    sentences are HIS, lifted from [00:38] of the transcript the pass was
    reading, and they would have been performed in Mira's voice as the first
    thing in the episode. The pass is asked to open on the conversation; it
    opened with the conversation.

    A narration is written copy, so nothing at the front of it should be a
    verbatim line from the tape. Walk the opening sentences, and drop the
    longest run of them that matches something somebody actually said.
    """
    text = (intro or "").strip()
    if not text:
        return text
    said = _spoken(transcript)
    if not said:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    drop_upto, joined = 0, ""
    for i, sentence in enumerate(sentences[:-1]):   # never strip it all away
        joined = (joined + " " + sentence).strip()
        probe = _normalise(joined)
        if not probe:
            continue
        # A full spoken line, or the start of one: a borrowed opening is the
        # front of somebody's turn, not a phrase from the middle of it.
        if any(line == probe or line.startswith(probe) for line in said):
            drop_upto = i + 1
    if not drop_upto:
        return text
    dropped = " ".join(sentences[:drop_upto])
    logger.warning("narration intro opened with %d sentence(s) spoken in the "
                   "room, not written for it — dropped: %s",
                   drop_upto, dropped[:200])
    return " ".join(sentences[drop_upto:]).strip()


# How much of a speaker's own voice the bleed gate may swallow before its
# output is no longer the better bed. Measured per track in
# audio/bleed.py as "loud_muted_sec" — seconds muted while the track was
# still too loud to have been anyone's echo.
OVERREACH_MAX_SEC = 3.0


def _clean_bed(run: dict) -> tuple[bool, str]:
    """Should the conversation be cut from the processed tracks?

    Sept 22 2026. The default answer is yes, and it is the better bed for a
    reason that has nothing to do with taste: ``run:guest`` is the guest's
    microphone folded together with what the guest heard, so on any tape
    where the guest had no headphones in, Mira is in the episode twice, a
    few hundred milliseconds apart. The processed tracks have had that taken
    out and are levelled one voice at a time.

    It says no in the three cases where those tracks are not trustworthy:
    they do not exist (an older run, or the two-track fallback path), a
    track could not be placed on the room's clock (folding it would slide a
    speaker away from the conversation), or the bleed gate is measured to
    have muted a real stretch of somebody's own voice.

    Returns ``(use_them, why)``; ``why`` is for the edit's rationale, so a
    human reading the note knows which bed this episode was cut from.
    """
    tracks = ((run.get("grok_session_log") or {}).get("tracks") or {})
    processed = tracks.get("processed") or {}
    if not processed.get("guest") or not processed.get("mira"):
        return False, ("CUT FROM THE STEREO: this run has no processed "
                       "per-speaker tracks.")
    unaligned = [r for r in ("guest", "host", "mira")
                 if r in (tracks.get("unaligned") or []) and processed.get(r)]
    if unaligned:
        return False, ("CUT FROM THE STEREO: " + ", ".join(unaligned) +
                       " could not be placed on the room's clock, and a track "
                       "off the clock folded into the others is worse than an "
                       "echo.")
    over = {}
    unmeasured = []
    for role, stats in (tracks.get("bleed") or {}).items():
        if not isinstance(stats, dict) or not stats.get("bleed"):
            continue
        loud = stats.get("loud_muted_sec")
        if loud is None:
            unmeasured.append(role)
        elif float(loud) > OVERREACH_MAX_SEC:
            over[role] = float(loud)
    if over:
        worst = ", ".join(f"{r} {v:.0f}s" for r, v in sorted(over.items()))
        return False, ("CUT FROM THE STEREO: the bleed gate muted more of a "
                       "speaker's own voice than it should have (" + worst +
                       "), so the stripped tracks are missing words.")
    if unmeasured:
        return True, ("Cut from the processed tracks. The bleed gate on " +
                      ", ".join(unmeasured) + " predates the over-reach "
                      "measurement, so listen for a missing word as well as "
                      "for the echo.")
    return True, "Cut from the processed tracks: one voice each, no echo."


# Oct 5 2026 (Piper Martz). Where a closing session's own recording begins:
# the welcome back and the "how are you" stay out, so a listener hears the
# first conversation run straight on into the round it never finished.
CLOSING_STARTS = re.compile(
    r"(lightning round|closing round|closing questions|quick-?fire"
    r"|book you'?d recommend|book you would recommend"
    r"|where we left off|pick (it|that|things) (up|back up)|picking up where)", re.I)
CLOSING_MARK = "[Closing session]"

# Oct 14 2026 (Piper Martz). Where a closing session's piece of the episode
# ends. Her splice ran to the end of the room, so the episode carried her
# suggestion for what we could improve, which she had prefaced with "I
# wouldn't include this in the formal interview", and then Mira saying "You
# can hang up now" three times. The improvement question is asked for the
# learning loop, which reads the closing session's own transcript, not the
# episode; the sign-off is never content. The piece ends before whichever of
# them comes first.
CLOSING_ENDS = re.compile(
    r"(thing (we|i) could improve|could (we|i) improve|(be|could be) improved"
    r"|suggestion for (what|how)|end of the recording|you can hang up"
    r"|that'?s a wrap)", re.I)
# A reply that only says "go on" is not the guest picking the thread up.
_ACKNOWLEDGEMENT = re.compile(
    r"^(sounds good|sure|great|okay|ok|yes|yeah|yep|perfect|absolutely|of course"
    r"|let'?s do it|happy to|ready)[\s.!,]*(thanks|thank you)?[\s.!,]*$", re.I)


def _closing_span(rows: list) -> tuple:
    """``(begin, end)`` on the transcript's clock for a closing session's
    piece of the episode, from ``[(t, who, text)]``.

    It begins on the Mira turn the guest's first real answer follows, not on
    the first line that mentions the lightning round. Piper's session (Oct 13)
    went: "We left off right in the middle of your book recommendation, so
    let's pick that thread back up...", "Sounds good", "You're back in the
    quick lightning round... go ahead and finish that thought", and then her
    answer. The first of those is Mira explaining the session, and it put a
    break the listener never heard into the middle of the episode.

    It ends before the improvement question or the sign-off, whichever comes
    first (``CLOSING_ENDS``), taking the whole Mira turn that question sits in.
    ``end`` is ``None`` when neither was reached.
    """
    is_mira = [who.strip().lower() == "mira" for _t, who, _x in rows]
    first = next((i for i, (_t, _w, text) in enumerate(rows)
                  if is_mira[i] and CLOSING_STARTS.search(text)), None)
    if first is None:
        # She opened the round in words this does not know: keep everything
        # after her welcome back rather than lose any of it.
        mira_at = [i for i, m in enumerate(is_mira) if m]
        first = mira_at[1] if len(mira_at) > 1 else (mira_at[0] if mira_at else 0)
    begin_i = first
    def _real_answer(text: str) -> bool:
        text = text.strip()
        return not _ACKNOWLEDGEMENT.match(text) and len(text.split()) > 5

    answer = next((i for i in range(first + 1, len(rows))
                   if not is_mira[i] and _real_answer(rows[i][2])), None)
    if answer is not None:
        # The turn of hers that the answer follows, from its first line.
        j = answer - 1
        while j > first and is_mira[j - 1]:
            j -= 1
        if is_mira[j]:
            begin_i = max(first, j)
    begin = rows[begin_i][0] if rows else 0.0
    end = None
    for i in range(begin_i + 1, len(rows)):
        if is_mira[i] and CLOSING_ENDS.search(rows[i][2]):
            k = i
            while k > begin_i + 1 and is_mira[k - 1]:
                k -= 1
            end = rows[k][0]
            break
    return begin, end


def _closing_text_between(text: str, begin: float, end: float | None) -> str:
    """The lines of a closing session's transcript that the episode keeps."""
    kept, keep = [], False
    for line in (text or "").splitlines():
        m = _LINE.match(line.strip())
        if m:
            h_or_m, mm, ss = m.group(1), m.group(2), m.group(3)
            t = (int(h_or_m) * 3600 + int(mm) * 60 + int(ss)) if ss else (int(h_or_m) * 60 + int(mm))
            keep = t >= begin and (end is None or t < end)
        if keep:
            kept.append(line)
    return "\n".join(kept).strip()


def splice_closing(ctx: dict) -> dict:
    """A closing session is not an episode. Its closing round goes onto the
    end of the edit of the interview it finishes, before Mira's produced
    close, and that episode is the one narrated, assembled and sent to
    Patrick. Idempotent: running it twice replaces the earlier splice."""
    run, interview = ctx["run"], ctx["interview"]
    parent_id = interview.get("continues_interview_id")
    if not parent_id:
        raise SystemExit("closing session with no interview to finish "
                         "(interviews.continues_interview_id is empty)")
    edits = sb_select("episode_edits",
                      f"interview_id=eq.{parent_id}&order=created_at.desc&limit=1")
    if not edits:
        raise SystemExit(f"no edit of interview {parent_id} to finish")
    parent = edits[0]
    slug = parent["slug"]
    on_disk = EDL_DIR / f"{slug}.json"
    edl = (json.loads(on_disk.read_text(encoding="utf-8")) if on_disk.exists()
           else dict(parent.get("edl") or {}))
    narration = parent.get("narration") or {}

    offset = _leg_offset(run)
    rows = []
    for line in transcript_of(ctx).splitlines():
        m = _LINE.match(line.strip())
        if not m:
            continue
        h_or_m, mm, ss, who, text = m.groups()
        t = (int(h_or_m) * 3600 + int(mm) * 60 + int(ss)) if ss else (int(h_or_m) * 60 + int(mm))
        rows.append((float(t), who.strip(), text))
    begin, stop = _closing_span(rows)
    try:
        room_end = float(run.get("duration_sec") or 0.0) or None
    except (TypeError, ValueError):
        room_end = None
    last = rows[-1][0] + 8.0 if rows else (room_end or begin + 600.0)
    # Before the improvement question or the sign-off; the end of the room
    # only when the session never reached either.
    last = stop if stop is not None else last
    end = min(last, room_end) if room_end else last
    piece = {"from": "mix:clean", "run_id": run["id"],
             "start": round(max(0.0, begin - offset - 0.4), 1),
             "end": round(max(0.0, end - offset), 1),
             "note": (f"{CLOSING_MARK} recorded {str(run.get('created_at') or '')[:10]}: the "
                      "rest of the closing round, after the room's old time cap cut the "
                      "first session off. It starts on the question the guest's first "
                      "real answer follows" + (
                          ", and ends before Mira asks what could be improved or "
                          "signs off." if stop is not None else
                          "; the session never reached the improvement question or a "
                          "sign-off, so it runs to the end of the room."))}

    # An earlier splice (its piece and its gap) comes out first; then the new
    # one goes in before the produced close, keeping the breath before it.
    cuts = [c for c in (edl.get("cuts") or [])
            if not (isinstance(c, dict) and (c.get("run_id") or c.get("closing")))]
    at = max((i for i, c in enumerate(cuts)
              if isinstance(c, dict) and str(c.get("from", "")).startswith("narration:")),
             default=len(cuts))
    if at > 0 and isinstance(cuts[at - 1], dict) and "gap" in cuts[at - 1]:
        at -= 1
    cuts[at:at] = [{"gap": 0.9, "closing": True}, piece]
    # The first session's last piece no longer ends the episode.
    for c in cuts:
        if isinstance(c, dict) and c.get("from") == "mix:clean" and not c.get("run_id"):
            c.pop("exact_end", None)
    edl["cuts"] = cuts
    edl["note"] = ((edl.get("note") or "").split(" " + CLOSING_MARK)[0] + " " + CLOSING_MARK +
                   " The closing session is spliced on before Mira's close.")

    EDL_DIR.mkdir(parents=True, exist_ok=True)
    on_disk.write_text(json.dumps(edl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if narration:
        NARRATION_DIR.mkdir(parents=True, exist_ok=True)
        (NARRATION_DIR / f"{slug}.json").write_text(
            json.dumps(narration, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sb_update("episode_edits", f"id=eq.{parent['id']}",
              {"edl": edl, "rationale": edl["note"]})

    # The guest approves a transcript as well as the audio: theirs gets the
    # closing session too, once.
    pkgs = sb_select("editorial_packages",
                     f"interview_id=eq.{parent_id}&status=neq.killed"
                     "&select=id,transcript_cleaned&order=created_at.desc&limit=1")
    # Only the lines the episode keeps (Oct 14 2026): the transcript the guest
    # approves is the one that is published, and Piper's carried the feedback
    # she had asked to keep out of the interview.
    closing_text = _closing_text_between(
        ((ctx.get("package") or {}).get("transcript_cleaned")
         or transcript_of(ctx) or ""),
        begin, stop)
    if pkgs and closing_text:
        base = (pkgs[0].get("transcript_cleaned") or "").split("\n\n" + CLOSING_MARK)[0]
        sb_update("editorial_packages", f"id=eq.{pkgs[0]['id']}",
                  {"transcript_cleaned": f"{base}\n\n{CLOSING_MARK}\n{closing_text}"})
    logger.info("closing session spliced into %s at %.0fs-%.0fs of its own tape",
                slug, piece["start"], piece["end"])
    return {"slug": slug, "spliced": True}


def build(run_id: str) -> dict:
    ctx = _context(run_id)
    if (ctx["interview"].get("session_kind") or "interview") == "closing":
        return splice_closing(ctx)
    run, interview, app = ctx["run"], ctx["interview"], ctx["app"]
    decided = plan(ctx)

    when = recorded_on(run, interview)
    slug = _slug(app.get("name", ""), when)
    # A hand-written edit in the repo is somebody's judgement and outranks
    # this one. Never overwrite it — cut alongside it and let a human choose.
    if (EDL_DIR / f"{slug}.json").exists() and not _ours(slug):
        slug = f"{slug}_auto"
        logger.info("a hand-written edit already exists — cutting as %s", slug)
    offset = _leg_offset(run)
    # The room's own length, on the room clock: where the tape stops, and so
    # the last moment the guest could still have been talking.
    try:
        room_end = float(run.get("duration_sec") or 0.0) or None
    except (TypeError, ValueError):
        room_end = None

    # Room clock -> the guest leg's own clock, which is what the EDL addresses.
    def leg(t: float) -> float:
        return max(0.0, float(t) - offset)

    start = leg(float(decided.get("start_sec") or 0.0)) + EDGE_PAD_SEC
    end, ended_early = _where_it_closes(
        transcript_of(ctx), float(decided["end_sec"]), room_end,
        decided.get("end_why") or "")
    end = leg(end)
    requests = guest_requests(transcript_of(ctx))
    if requests:
        logger.info("the guest asked for %d thing(s) to come out: %s", len(requests),
                    "; ".join(r["why"] for r in requests))
    drops = []
    for d in merge_drops(decided.get("drop") or [], requests):
        a, b = leg(float(d["from_sec"])), leg(float(d["to_sec"]))
        # A "can you hear me" right after the welcome is short and worth the
        # seam; anywhere else a short drop is not.
        floor = EARLY_DROP_MIN_SEC if a < start + EARLY_WINDOW_SEC else MIN_DROP_SEC
        # ...and what the guest asked to have out comes out at any length:
        # a two-second "scratch that" is a seam worth making (Oct 21 2026).
        if d.get("guest_request"):
            floor = 0.0
        if b - a >= floor and start < a < b < end:
            drops.append({"from": a, "to": b, "why": d.get("why", ""),
                          **({"guest_request": True} if d.get("guest_request") else {})})
    drops.sort(key=lambda d: d["from"])
    kept_requests = sum(1 for d in drops if d.get("guest_request"))
    rationale_requests = (f"{kept_requests} passage(s) the guest asked to have out "
                          "are out, whatever their length." if kept_requests else "")

    rationale = decided.get("rationale", "")
    if ended_early:
        rationale = (rationale + " " if rationale else "") + ended_early
    if rationale_requests:
        rationale = (rationale + " " if rationale else "") + rationale_requests
    clean, bed_why = _clean_bed(run)
    rationale = (rationale + " " if rationale else "") + bed_why
    logger.info("%s", bed_why)
    # The stereo fold stays as the fallback, with the settings it has always
    # had: level the guest's microphone and the side they heard separately,
    # and give the side carrying Mira her presence EQ.
    # Oct 7 2026: when the guest's own browser take was used, post_interview
    # also writes their leg with that take on the left, and the stereo
    # fallback cuts from it (Scott Pulcini's was cut from the call twice).
    leg_local = str((((run.get("grok_session_log") or {}).get("tracks") or {})
                     .get("leg_local") or {}).get("url") or "")
    bed = ({"from": "mix:clean"} if clean else
           {"from": leg_local, "balance": True, "voice_match": "right",
            "left_source": "local"} if leg_local else
           {"from": "run:guest", "balance": True, "voice_match": "right"})
    if not clean and leg_local:
        rationale += " The guest's side is their own browser recording."
    # The cold open: the guest's own voice first, with one line of context
    # from Mira before it (Sept 25 2026). Needs the guest's own track, which
    # only the clean bed has; without it the introduction stands alone.
    lead, clip = _cold_open(decided, clean, leg, start, end)
    intro = str(decided["intro"]).strip()
    segments = []
    cuts = []
    if clip:
        segments.append({"id": "lead", "text": lead})
        cuts += [{"from": "narration:lead"}, {"gap": 0.35}, clip, {"gap": 0.8}]
    else:
        intro = re.sub(r"^That's\s+", "My guest is ", intro)
    segments += [{"id": "intro", "text": intro},
                 {"id": "outro", "text": decided["outro"]}]
    cuts += [{"from": "narration:intro"}, {"gap": 0.7}]
    over = _interruptions(run, leg) if clean else []
    if over:
        rationale += (" Mira talked over the guest mid-answer " +
                      ", ".join(f"at {a // 60:.0f}:{a % 60:04.1f}" for a, _b in over) +
                      "; her voice is muted there and the guest's carries on.")
    at = start
    for d in drops:
        cuts.append(_with_mutes({**bed,
                     "start": round(at, 1), "end": round(d["from"], 1),
                     "note": f"to {d['from']:.0f}s: {d['why']}"}, over))
        cuts.append({"gap": 0.4})
        at = d["to"]
    cuts.append(_with_mutes({**bed,
                 "start": round(at, 1), "end": round(end, 1),
                 "note": decided.get("end_why", "")}, over))
    # A breath after the guest's last word before the produced close; 0.7 s
    # ran the outro straight into the end of the sentence.
    cuts += [{"gap": 1.4}, {"from": "narration:outro"}]

    narration = {
        "show": show_for(interview, app).slug,
        "voice": run.get("voice_preset") or "ara",
        "note": f"Written by auto_edit from the {app.get('name')} interview.",
        "segments": segments,
    }
    edl = {
        "show": show_for(interview, app).slug,
        "interview_id": interview["id"],
        "run_id": run["id"],
        "narration": slug,
        "note": rationale,
        # The clock the cuts address, relative to the room's: the assembler
        # needs it to place the guest's own cut windows (room clock) on the
        # cuts (leg clock). Zero on every run since the tracks were aligned.
        "room_offset_sec": round(offset, 3),
        "guest_request_drops": kept_requests,
        "cuts": cuts,
    }

    NARRATION_DIR.mkdir(parents=True, exist_ok=True)
    EDL_DIR.mkdir(parents=True, exist_ok=True)
    (NARRATION_DIR / f"{slug}.json").write_text(
        json.dumps(narration, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (EDL_DIR / f"{slug}.json").write_text(
        json.dumps(edl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("cut %s: %.0fs to %.0fs, %d stretch(es) dropped",
                slug, start, end, len(drops))

    existing = sb_select("episode_edits", f"slug=eq.{slug}&select=id")
    row = {"slug": slug, "interview_id": interview["id"],
           "interview_run_id": run["id"], "narration": narration, "edl": edl,
           "rationale": rationale}
    if existing:
        sb_update("episode_edits", f"id=eq.{existing[0]['id']}", row)
    else:
        sb_insert("episode_edits", row)

    _remember(ctx, decided, when)
    return {"slug": slug, "cuts": len(cuts), "drops": len(drops)}


def _cold_open(decided: dict, clean: bool, leg, start: float, end: float):
    """``(lead, cut)`` for the guest's own voice at the top, or ``("", None)``."""
    co = decided.get("cold_open")
    if not clean or not isinstance(co, dict):
        return "", None
    lead = str(co.get("lead") or "").strip()
    try:
        a, b = leg(float(co["from_sec"])), leg(float(co["to_sec"]))
    except (KeyError, TypeError, ValueError):
        return "", None
    lo, hi = COLD_OPEN_SEC
    if not lead or not (lo <= b - a <= hi) or not (start <= a < b <= end):
        logger.warning("auto_edit: cold open %.1f-%.1f unusable — intro stands alone", a, b)
        return "", None
    clip = {"from": "track:guest", "start": round(max(0.0, a - 0.1), 2),
            "end": round(b + 0.3, 2), "gaps": False, "trim_edges": True,
            "note": "Cold open: the guest in their own voice."}
    if str(co.get("quote") or "").strip():
        clip["text"] = " ".join(str(co["quote"]).split())
    return lead, clip


def _interruptions(run: dict, leg) -> list:
    """Where Mira talked over the guest, on the EDL's clock. Best effort: a
    failure here costs a muted interjection, never the episode."""
    processed = (((run.get("grok_session_log") or {}).get("tracks") or {})
                 .get("processed") or {})
    if not processed.get("guest") or not processed.get("mira"):
        return []
    try:
        import tempfile
        import requests
        from audio.overlap import interruptions
        with tempfile.TemporaryDirectory() as tmp:
            paths = {}
            for role in ("guest", "mira"):
                dest = Path(tmp) / f"{role}.wav"
                with requests.get(processed[role], stream=True, timeout=900) as r:
                    r.raise_for_status()
                    with dest.open("wb") as fh:
                        for chunk in r.iter_content(1 << 20):
                            fh.write(chunk)
                paths[role] = dest
            found = interruptions(paths["guest"], paths["mira"])
    except Exception:  # noqa: BLE001
        logger.exception("auto_edit: interruption scan failed (non-fatal)")
        return []
    return [(leg(a), leg(b)) for a, b in found]


def _with_mutes(cut: dict, over: list) -> dict:
    mutes = [{"role": "mira", "from": round(a, 2), "to": round(b, 2)}
             for a, b in over
             if cut.get("start") is not None and cut.get("end") is not None
             and cut["start"] <= a and b <= cut["end"]]
    if mutes and cut.get("from") == "mix:clean":
        cut = {**cut, "mute": mutes}
    return cut


def _remember(ctx: dict, decided: dict, when: dt.date) -> None:
    """The content lake row. Written even if nothing else here works out."""
    run, interview, app = ctx["run"], ctx["interview"], ctx["app"]
    predictions = []
    for p in decided.get("predictions") or []:
        months = p.get("horizon_months")
        due = None
        if isinstance(months, (int, float)) and months > 0:
            due = (when + dt.timedelta(days=int(months) * 30)).isoformat()
        predictions.append({"prediction": p.get("prediction"),
                            "horizon_months": months, "due_on": due,
                            "quote": p.get("quote")})
    row = {
        "show": show_for(interview, app).slug,
        "interview_id": interview["id"],
        "interview_run_id": run["id"],
        "application_id": app.get("id"),
        "guest_name": app.get("name"),
        "guest_email": (app.get("email") or "").lower(),
        "recorded_on": when.isoformat(),
        "summary": decided.get("summary", ""),
        "claims": decided.get("claims") or [],
        "predictions": predictions,
        "unanswered": decided.get("unanswered") or [],
        "follow_ups": decided.get("follow_ups") or [],
        "quotes": decided.get("quotes") or [],
        "topics": app.get("topics") or [],
        "links": app.get("links") or {},
    }
    try:
        # One record per interview, not one per cut. Sept 15 2026: re-cutting
        # Vincent Rylan's episode to see what the machine would do wrote a
        # second record of the same conversation. A guest quoted back to
        # themselves from two slightly different versions of what they said is
        # worse than not being quoted at all.
        existing = sb_select("episode_records",
                             f"interview_run_id=eq.{run['id']}&select=id")
        if existing:
            sb_update("episode_records", f"id=eq.{existing[0]['id']}", row)
            logger.info("content lake: updated this interview's record")
        else:
            sb_insert("episode_records", row)
        logger.info("content lake: %d claims, %d predictions, %d follow-ups",
                    len(decided.get("claims") or []), len(predictions),
                    len(decided.get("follow_ups") or []))
    except Exception:  # noqa: BLE001
        logger.exception("could not write the episode record — continuing")


# common.py sends logging to STDOUT, and this script's stdout is a contract:
# the workflow reads a JSON object from it to learn the slug and hand it to
# the narrate and assemble steps. Every log line landed in that JSON and the
# parse failed, so twice now (Dan Perra, Sept 15 2026) the episode was cut,
# written to the database — and then the job died before Mira recorded a
# word, with the cut stranded on a runner that was about to be destroyed.
# Logs go to stderr here, and the result is written to a file as well, so
# the hand-off does not depend on stdout staying clean.
RESULT_PATH = os.environ.get("AUTO_EDIT_RESULT", "cut.json")


def _logs_to_stderr() -> None:
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout:
            handler.setStream(sys.stderr)


def main() -> int:
    _logs_to_stderr()
    if len(sys.argv) < 2:
        raise SystemExit("usage: auto_edit.py <interview_run_id>")
    result = build(sys.argv[1])
    payload = json.dumps(result)
    try:
        Path(RESULT_PATH).write_text(payload + "\n", encoding="utf-8")
    except Exception:  # noqa: BLE001 — stdout is still there
        logger.exception("could not write %s", RESULT_PATH)
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
