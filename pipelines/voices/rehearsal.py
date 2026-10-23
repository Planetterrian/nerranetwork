"""The interview shows' rehearsal harness (Oct 21 2026, review §7.5).

Every other audio-affecting change in this network goes through an A/B
listen before a listener hears it. The interview show had no way to make
one: the only person who could be on the other end of a rehearsal was a
real guest, which is why the Oct 19 prompt rebuild shipped into Jon
Cheney's room the same afternoon. This module gives the show a guest who is
not a guest.

How a rehearsal runs::

    python pipelines/voices/rehearsal.py run --arm proposed --fixture roddy \
        --minutes 10 --repeat 3
    python pipelines/voices/rehearsal.py run --arm current  --fixture roddy ...
    python pipelines/voices/rehearsal.py report outputs/rehearsals/<day>

``run`` creates an ``interview_runs`` row with the configuration under test
(the prompt, the end-of-turn setting, the reasoning effort) on a rehearsal
interview that the fire cron never sees, starts the fixture-guest scenario
(the fixture-guest scenario under ``voximplant/scenarios/``), which calls into the
room exactly like a human leg and plays a past guest from their approved
transcript, waits for the room to end, transcribes both speakers the way
post-production does, measures the hour with ``audio_metrics.measure_audio``
and writes one JSON result per room. ``report`` compares the two arms on the
§7.5 rule: the proposed configuration ships to a real guest only when it
beats the current one on overlap events, self-answered turns and guest
words per answer, and does not lose on Mira's turn length — and the operator
has listened to one run.

Two arms, same fixture, same scheduled behaviours (the fixture pauses
mid-thought at minute two, coughs at 3.5, says "let me think" at five,
pushes back at 6.5, asks who someone is at eight), so the rooms differ in
Mira's configuration and nothing else.

Everything that touches Supabase, Voximplant or audio is behind a function
boundary so the tests run offline; nothing here publishes, emails or edits.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger("rehearsal")

FIXTURES_FILE = HERE / "fixtures" / "rehearsal_guests.yaml"
PERSONA_TEMPLATE = HERE / "prompts" / "fixture_guest.txt"
DEFAULT_OUT_DIR = ROOT / "outputs" / "rehearsals"
ARMS = ("proposed", "current")
#: Which interview scenario a room runs on (Oct 22 2026). ``deployed`` is the
#: live one; ``candidate`` is this checkout's scenario uploaded beside it
#: (voximplant_client.upload_candidate_scenario), reached through its own room
#: prefix, so a change to the room's CODE is rehearsed before it is deployed.
SCENARIOS = {"deployed": "room-", "candidate": "candroom-"}
#: The fixture's scheduled behaviours with a phone call in the middle (Oct 22
#: 2026, hold mode): the same faults as the default list, and at minute four
#: the guest steps away to take a call and comes back at six.
HOLD_BEATS = [
    {"at_min": 2.0, "kind": "pause_mid_thought"},
    {"at_min": 4.0, "kind": "take_call"},
    {"at_min": 6.0, "kind": "end_call"},
    {"at_min": 7.0, "kind": "push_back"},
    {"at_min": 8.0, "kind": "ask_who"},
]
#: The §7.5 rule: proposed must beat current on these (lower is better for
#: the first two, higher for the third) ...
MUST_BEAT = (("overlap_events", "lower"), ("self_answered_turns", "lower"),
             ("guest_words_per_answer_median", "higher"))
#: ... and must not lose on this one (a clipped turn is 7.6 s, a monologue
#: 50 s; the target band is 12-20 s, so "not lose" is "not further from the
#: band than current").
MUST_NOT_LOSE = ("mira_turn_sec_median", (12.0, 20.0))
#: What the fixture's persona may carry into the room (Voximplant's
#: customData has to fit the whole JSON; a persona over this is cut at a
#: line end).
PERSONA_MAX_CHARS = 9000
REGISTER_LINES = 40
#: How long ``run`` waits for a room to end before giving up on it.
ROOM_WAIT_SLACK_MIN = 6
POLL_SECONDS = 20
REHEARSAL_EMAIL_DOMAIN = "rehearsal.nerranetwork.com"
LINE_RE = re.compile(r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*([^:]+):\s*(.*)$")

# Oct 23 2026: lean rehearsals. Thirty-four rooms in two days (about 870
# Voice Agent minutes) found four real faults, and every one was read from
# a room's trace and Mira's words, never from the two-arm medians: the same
# configuration's guest words per answer ran 31 to 84 across rooms, and
# Mira's median turn sat at 4-5 s in every fixture room whatever changed.
# So one room of the proposed arm is the default, it is held to the review
# §7.7 targets the room can be held to, and the report prints the room log.
#: xAI's Voice Agent rate per session minute (an estimate for the report;
#: override with XAI_VOICE_COST_PER_MIN). A room runs two sessions: Mira and
#: the fixture guest.
VOICE_COST_PER_MIN = float(os.environ.get("XAI_VOICE_COST_PER_MIN") or 0.05)
SESSIONS_PER_ROOM = 2
#: The shortest room that reaches the closing round. The room reads a
#: planned length under 15 minutes as its 45-minute default (plannedMin), so
#: the first "12-minute" test room on Oct 23 2026 never opened the round. At
#: 15 the round is required at minute 10 and takes about three.
ROOM_MIN_MINUTES = 15
#: A room shorter than this share of its planned length did not run.
ROOM_RAN_SHARE = 0.75
#: Her words carry a handed question this long after the room handed it, or
#: after the next one was handed, and the round is running behind.
ROUND_LAG_SEC = 45.0
#: §7.7: under one overlap event per ten minutes.
OVERLAP_PER_10_MIN_MAX = 1.0
PREFLIGHT_URL = "https://api.x.ai/v1/chat/completions"
PREFLIGHT_MODEL = os.environ.get("REHEARSAL_PREFLIGHT_MODEL") or "grok-4.3"
_REFUSED_RE = re.compile(r"xAI refused the session", re.I)
_CREDIT_RE = re.compile(r"credit|spending limit", re.I)


class RoomsRefused(RuntimeError):
    """xAI refused every session in a room: the rooms after it would be
    refused too, so none is placed."""


# ---------------------------------------------------------------------------
# Fixtures: a past guest, from their published episode
# ---------------------------------------------------------------------------

def load_fixtures(path: Path = FIXTURES_FILE) -> Dict[str, Dict[str, Any]]:
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = {}
    for fid, row in (data.get("fixtures") or {}).items():
        row = dict(row or {})
        row["id"] = fid
        out[fid] = row
    return out


def _section(md: str, heading: str) -> str:
    """The body of ``### <heading>`` (exact or prefix match) up to the next
    heading or rule."""
    lines = md.splitlines()
    out: List[str] = []
    inside = False
    for line in lines:
        if line.startswith("### "):
            if inside:
                break
            inside = line[4:].strip().lower().startswith(heading.lower())
            continue
        if inside:
            if line.strip() == "---":
                break
            out.append(line)
    return "\n".join(out).strip()


def parse_digest(path: Path) -> Dict[str, Any]:
    """What the persona is made of: the guest's name, the About section, the
    "What we talked about" bullets and the guest's OWN transcript lines (never
    Mira's, never the co-host's)."""
    md = path.read_text(encoding="utf-8")
    about_heading = next((ln[4:].strip() for ln in md.splitlines()
                          if ln.startswith("### About ")), "")
    name = about_heading[len("About "):].strip() if about_heading else ""
    about = _section(md, "About ")
    talked = _section(md, "What we talked about")
    guest_lines: List[str] = []
    labels: Dict[str, int] = {}
    for line in md.splitlines():
        m = LINE_RE.match(line.strip())
        if not m:
            continue
        label = m.group(4).strip()
        labels[label] = labels.get(label, 0) + 1
    # The guest is whoever speaks most who is not Mira or the co-host.
    guest_label = ""
    for label, count in sorted(labels.items(), key=lambda kv: -kv[1]):
        if label.lower() in ("mira", "patrick", "patrick novak", "host"):
            continue
        guest_label = label
        break
    for line in md.splitlines():
        m = LINE_RE.match(line.strip())
        if m and m.group(4).strip() == guest_label:
            text = m.group(5).strip()
            if len(text.split()) >= 6:
                guest_lines.append(text)
    return {"name": name, "about": about, "talked_about": talked,
            "guest_label": guest_label, "guest_lines": guest_lines}


def fixture_persona(fixture: Dict[str, Any], root: Path = ROOT) -> str:
    """Render ``fixture_guest.txt`` for one fixture from its digest. Plain
    replacement, not ``load_prompt``: a transcript may carry braces."""
    digest = parse_digest(root / fixture["digest"])
    sample = "\n".join("- " + ln for ln in digest["guest_lines"][:REGISTER_LINES])
    text = PERSONA_TEMPLATE.read_text(encoding="utf-8")
    subs = {
        "guest_name": fixture.get("name") or digest["name"],
        "about": digest["about"] or "(no biography on file)",
        "talked_about": digest["talked_about"] or "(no notes on file)",
        "register_sample": sample or "(no transcript lines on file)",
    }
    for key, value in subs.items():
        text = text.replace("{" + key + "}", value)
    if fixture.get("register"):
        text += "\nIn one line, how you come across: " + str(fixture["register"]) + ".\n"
    if len(text) > PERSONA_MAX_CHARS:
        cut = text[:PERSONA_MAX_CHARS]
        text = cut[: cut.rfind("\n")] + "\n"
    return text


# ---------------------------------------------------------------------------
# The configuration under test
# ---------------------------------------------------------------------------

def current_prompt() -> str:
    """The prompt the last real interview actually ran on: the honest
    baseline, whatever the repo's prompt file says today."""
    from common import sb_select
    rows = sb_select("interview_runs",
                     "session_kind=eq.interview&status=eq.completed"
                     "&mira_system_prompt=neq.&order=fired_at.desc.nullslast&limit=1")
    if not rows:
        rows = sb_select("interview_runs",
                         "session_kind=eq.interview&order=created_at.desc&limit=1")
    if not rows or not rows[0].get("mira_system_prompt"):
        raise RuntimeError("no completed interview run to take the current prompt from")
    return rows[0]["mira_system_prompt"]


def _original_guest(fixture: Dict[str, Any]) -> Dict[str, Any]:
    """The real application, interview and brief of the guest this fixture
    plays, so the proposed prompt is compiled on real inputs."""
    from common import sb_select
    name = fixture["name"]
    apps = sb_select("guest_applications",
                     f"name=ilike.{requests_quote(name)}&order=created_at.asc&limit=5")
    apps = [a for a in apps if not str(a.get("email") or "").endswith(REHEARSAL_EMAIL_DOMAIN)]
    if not apps:
        raise RuntimeError(f"no guest_applications row for fixture {fixture['id']} ({name})")
    app = apps[0]
    interviews = sb_select("interviews",
                           f"application_id=eq.{app['id']}&session_kind=eq.interview"
                           "&order=scheduled_at.asc&limit=1")
    interview = interviews[0] if interviews else {"application_id": app["id"],
                                                  "duration_min": 45}
    briefs = (sb_select("interview_briefs", f"interview_id=eq.{interview['id']}")
              if interview.get("id") else [])
    return {"app": app, "interview": interview, "brief": briefs[0] if briefs else {}}


def requests_quote(value: str) -> str:
    from urllib.parse import quote
    return quote(value, safe="")


def proposed_prompt(fixture: Dict[str, Any]) -> str:
    """What ``fire_interviews.compile_mira_prompt`` writes TODAY for this
    guest: the repo's prompt, the current lessons, the current blocks."""
    from fire_interviews import compile_mira_prompt
    original = _original_guest(fixture)
    return compile_mira_prompt(original["interview"], original["app"], original["brief"])


def ensure_rehearsal_interview(fixture: Dict[str, Any], minutes: int) -> Dict[str, Any]:
    """A guest_applications + interviews pair for the fixture, status
    ``rehearsal`` on both so no cron, screen, brief or reminder ever touches
    them. Reused across runs."""
    from common import sb_insert, sb_select, sb_update
    email = f"rehearsal+{fixture['id']}@{REHEARSAL_EMAIL_DOMAIN}"
    apps = sb_select("guest_applications", f"email=eq.{requests_quote(email)}&limit=1")
    if apps:
        app = apps[0]
    else:
        app = sb_insert("guest_applications", {
            "name": f"Rehearsal: {fixture['name']}", "email": email,
            "status": "rehearsal", "organization": "Nerra Network rehearsal",
            "title": "fixture guest", "bio": f"A fixture playing {fixture['name']}.",
            "notes": "Rehearsal fixture — never a real guest, never published.",
        })
    rows = sb_select("interviews",
                     f"application_id=eq.{app['id']}&session_kind=eq.rehearsal&limit=1")
    if rows:
        interview = rows[0]
        if interview.get("duration_min") != minutes:
            sb_update("interviews", f"id=eq.{interview['id']}", {"duration_min": minutes})
            interview["duration_min"] = minutes
    else:
        interview = sb_insert("interviews", {
            "application_id": app["id"], "status": "rehearsal",
            "session_kind": "rehearsal", "duration_min": minutes,
            "scheduled_at": _iso(_now()),
        })
    return {"app": app, "interview": interview}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_run_row(*, interview: Dict[str, Any], arm: str, fixture: Dict[str, Any],
                  prompt: str, minutes: int, turn_silence_ms: Optional[int],
                  reasoning_effort: str, tools: Optional[list],
                  scenario: str = "deployed", with_hold: bool = False) -> Dict[str, Any]:
    """The interview_runs row for one rehearsal room. The scenario reads the
    same columns a live run carries; the only marker is session_kind."""
    from fire_interviews import MIRA_TOOLS, keyterms_for, turn_detection
    from common import cohost_name
    from shows import show_for
    show = show_for(interview)
    detection = turn_detection()
    if turn_silence_ms:
        detection = {"silence_duration_ms": max(600, min(2500, int(turn_silence_ms)))}
    row = {
        "interview_id": interview["id"],
        "mira_system_prompt": prompt,
        "session_kind": "rehearsal",
        "planned_minutes": minutes,
        "voice_preset": "ara",
        "turn_detection": detection,
        "keyterms": keyterms_for({"name": fixture["name"]}, show, cohost_name()),
        "tools": MIRA_TOOLS if tools is None else tools,
        "guest_phone": "",
        "caller_id": "rehearsal",
        "scheduled_for": _iso(_now()),
        "host_mode": False,
        "status": "awaiting_guest",
        "grok_session_log": {"rehearsal": {
            "arm": arm, "fixture": fixture["id"], "minutes": minutes,
            "reasoning_effort": reasoning_effort,
            "turn_silence_ms": detection["silence_duration_ms"],
            "prompt_chars": len(prompt), "started": _iso(_now()),
            "scenario": scenario, "with_hold": bool(with_hold),
        }},
    }
    if reasoning_effort:
        row["reasoning_effort"] = reasoning_effort
    return row


def create_run(row: Dict[str, Any]) -> Dict[str, Any]:
    """Insert the run; a column the table does not carry yet (reasoning_effort,
    keyterms) is dropped and the run still happens, the way the fire step
    does it."""
    from fire_interviews import insert_interview_run
    try:
        return insert_interview_run(row)
    except Exception as exc:  # noqa: BLE001
        text = str(getattr(getattr(exc, "response", None), "text", "") or exc)
        if "reasoning_effort" in row and "reasoning_effort" in text:
            logger.warning("interview_runs has no reasoning_effort column; "
                           "the room runs at its default effort")
            return insert_interview_run({k: v for k, v in row.items()
                                         if k != "reasoning_effort"})
        raise


def start_fixture(run_id: str, fixture: Dict[str, Any], persona: str, minutes: int,
                  cough_clip: str = "", scenario: str = "deployed",
                  with_hold: bool = False) -> Dict[str, Any]:
    from voximplant.api_clients.voximplant_client import start_fixture_guest
    return start_fixture_guest(
        run_id, persona=persona, voice=fixture.get("voice") or "sal", minutes=minutes,
        speaks_first=bool(fixture.get("speaks_first")), fixture_id=fixture["id"],
        guest_name=fixture["name"], cough_clip=cough_clip or None,
        beats=HOLD_BEATS if with_hold else None, room_prefix=SCENARIOS[scenario])


def wait_for_room(run_id: str, minutes: int) -> Dict[str, Any]:
    """Poll the run row until the room has ended (status completed/failed, or
    the trace's last line says it is ending)."""
    from common import sb_select
    deadline = time.time() + (minutes + ROOM_WAIT_SLACK_MIN) * 60
    last: Dict[str, Any] = {}
    while time.time() < deadline:
        rows = sb_select("interview_runs", f"id=eq.{run_id}")
        last = rows[0] if rows else {}
        if last.get("status") in ("completed", "failed"):
            return last
        trace = last.get("scenario_trace") or []
        tail = trace[-1] if trace and isinstance(trace[-1], dict) else {}
        if tail.get("e") == "room" and str(tail.get("d") or "").startswith("ending"):
            return last
        time.sleep(POLL_SECONDS)
    logger.warning("room %s did not end within %d min; measuring what there is",
                   run_id, minutes + ROOM_WAIT_SLACK_MIN)
    return last


# ---------------------------------------------------------------------------
# Measuring a room: the same transcription post-production uses
# ---------------------------------------------------------------------------

def _words_from(json_path: Path, shift: float) -> List[Dict[str, Any]]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    out = []
    for seg in data.get("segments", []):
        for w in seg.get("words") or []:
            try:
                out.append({"start": float(w["start"]) + shift,
                            "end": float(w["end"]) + shift,
                            "word": str(w.get("word", "")).strip()})
            except (KeyError, TypeError, ValueError):
                continue
    return out


#: Envelope frames per second for the channel check, and how far either way
#: the two recordings' clocks may disagree.
ENVELOPE_HZ = 10
ECHO_MAX_LAG_SEC = 10.0


def _envelope(path: Path) -> "Any":
    """RMS per 1/ENVELOPE_HZ s of a mono 8 kHz decode of ``path``."""
    import subprocess
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1",
                          "-ar", "8000", "-f", "s16le", "-"],
                         check=True, capture_output=True).stdout
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    win = 8000 // ENVELOPE_HZ
    frames = len(samples) // win
    if frames == 0:
        return np.zeros(0)
    return np.sqrt((samples[:frames * win].reshape(frames, win) ** 2).mean(axis=1))


def echo_score(track: "Any", mira: "Any", max_lag_sec: float = ECHO_MAX_LAG_SEC) -> float:
    """The best envelope correlation of ``track`` with Mira's own recording
    over lags up to ``max_lag_sec`` either way. A channel that carries her
    voice scores high whatever the clock offset; a channel that carries
    someone who speaks only while she is quiet scores near zero or below."""
    import numpy as np
    best = -1.0
    max_lag = int(max_lag_sec * ENVELOPE_HZ)
    for lag in range(-max_lag, max_lag + 1):
        a = mira[max(0, -lag):]
        b = track[max(0, lag):]
        n = min(len(a), len(b))
        if n < ENVELOPE_HZ * 10:
            continue
        a, b = a[:n], b[:n]
        if a.std() == 0 or b.std() == 0:
            continue
        best = max(best, float(np.corrcoef(a, b)[0, 1]))
    return best


def pick_guest_channel(left: Path, right: Path, mira: Optional[Path]) -> tuple:
    """Which side of the guest leg's stereo recording is the guest's mic.

    ``Call.record({stereo:true})`` puts the leg's mic on one channel and what
    the leg hears (Mira) on the other, and post-production reads the left as
    the guest. On the fixture guest's leg the sides are the other way round:
    the Oct 22 rehearsal transcribed Mira's own words, a few seconds late, as
    the guest's answers in both arms (left channel against her recording:
    0.72 envelope correlation; right: 0.11, active only while she was quiet),
    so every number the report compared was Mira against herself. The side
    that sounds least like her recording is the guest.

    Returns ``(guest_wav, heard_wav, side)`` with side "left" or "right";
    without Mira's recording the left stays the guest."""
    if mira is None:
        return left, right, "left"
    m = _envelope(mira)
    left_score = echo_score(_envelope(left), m)
    right_score = echo_score(_envelope(right), m)
    logger.info("guest-leg channels against Mira's recording: left %.2f, right %.2f",
                left_score, right_score)
    if right_score < left_score:
        return right, left, "right"
    return left, right, "left"


def transcribe_run(run: Dict[str, Any], workdir: Path) -> Dict[str, Any]:
    """Per-speaker Whisper words on the room clock for the fixture (guest)
    and Mira. Imports post_interview's fetchers and clock helper by name;
    the module imports cleanly without a run id (its main() is guarded)."""
    from post_interview import (fetch_recording, fetch_leg_recording,
                                room_offsets, _track_durations)
    from audio.mix_tracks import split_channels, duration_seconds
    from engine.transcripts import generate_transcript

    raw = fetch_recording(run, workdir)                      # longest guest leg
    left_wav, right_wav = split_channels(raw, workdir / "channels")
    mira_raw = fetch_leg_recording(run.get("recording_mira_url") or "", workdir, "mira")
    guest_wav, heard_wav, guest_side = pick_guest_channel(left_wav, right_wav, mira_raw)
    # Mira is measured from what the guest heard, never from her own record.
    # Voximplant stops writing her record while she makes no sound for a few
    # minutes: the fifth rehearsal's three-minute hold vanished from it
    # (12:00 against a 14:45 room), every later turn of hers landed minutes
    # before the answer it replied to, and the report counted seven
    # self-answered turns that were not there. The heard side is the guest
    # leg's own clock, so it shares the guest's offset.
    tracks = {"guest": guest_wav, "mira": heard_wav}
    offsets = room_offsets(run, _track_durations({"guest": guest_wav, "mira": mira_raw}))
    offsets["mira"] = offsets.get("guest", 0.0)
    words_by_role: Dict[str, List[Dict[str, Any]]] = {}
    lines: List[tuple] = []
    for role, label in (("guest", "Guest"), ("mira", "Mira")):
        src = tracks.get(role)
        if src is None:
            continue
        result = generate_transcript(src, workdir / "transcripts", f"{role}_track",
                                     model_size="small", language="en")
        if result is None:
            raise RuntimeError(f"transcription failed for the {role} track")
        shift = float(offsets.get(role, 0.0))
        words_by_role[role] = _words_from(result.json_path, shift)
        data = json.loads(result.json_path.read_text(encoding="utf-8"))
        for seg in data.get("segments", []):
            text = (seg.get("text") or "").strip()
            if text:
                lines.append((float(seg.get("start", 0.0)) + shift, label, text))
    lines.sort(key=lambda s: s[0])
    transcript = "\n".join(f"[{int(s // 60):02d}:{int(s % 60):02d}] {label}: {text}"
                           for s, label, text in lines)
    durations = {r: duration_seconds(p) for r, p in tracks.items() if p is not None}
    return {"words_by_role": words_by_role, "transcript": transcript,
            "durations": durations, "guest_channel": guest_side}


def measure_room(run: Dict[str, Any], words_by_role: Dict[str, List[Dict[str, Any]]],
                 transcript: str = "") -> Dict[str, Any]:
    """``audio_metrics.measure_audio`` on the room's words and trace."""
    from audio_metrics import measure_audio
    from fire_interviews import CLOSING_ROUND
    return measure_audio(words_by_role, trace=run.get("scenario_trace") or [],
                         round_questions=[q for q, _ in CLOSING_ROUND],
                         transcript=transcript)


def listen_url(run: Dict[str, Any]) -> str:
    log = run.get("grok_session_log") or {}
    return (log.get("voximplant_mix_record_url") or run.get("recording_mixed_url")
            or run.get("recording_mira_url") or run.get("recording_guest_url") or "")


def result_record(*, arm: str, fixture: Dict[str, Any], run: Dict[str, Any],
                  metrics: Dict[str, Any], transcript: str = "",
                  guest_channel: str = "", refused: bool = False) -> Dict[str, Any]:
    cfg = (run.get("grok_session_log") or {}).get("rehearsal") or {}
    return {
        "arm": arm, "fixture": fixture["id"], "run_id": run.get("id"),
        "measured_at": _iso(_now()), "config": cfg,
        "planned_minutes": run.get("planned_minutes") or cfg.get("minutes"),
        "listen_url": listen_url(run), "metrics": metrics,
        "guest_channel": guest_channel, "transcript": transcript,
        "refused": bool(refused),
        "room_log": room_log(run.get("scenario_trace") or [], transcript),
    }


def measure_and_write(*, arm: str, fixture: Dict[str, Any], run: Dict[str, Any],
                      out_dir: Path, index: int) -> Path:
    """Transcribe a finished room, measure it and write its record."""
    with tempfile.TemporaryDirectory(prefix="rehearsal_") as tmp:
        heard = transcribe_run(run, Path(tmp))
    metrics = measure_room(run, heard["words_by_role"], heard["transcript"])
    record = result_record(arm=arm, fixture=fixture, run=run, metrics=metrics,
                           transcript=heard["transcript"],
                           guest_channel=heard.get("guest_channel", ""))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{arm}_{fixture['id']}_{index}_{str(run['id'])[:8]}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    logger.info("wrote %s", path)
    return path


def run_one(*, arm: str, fixture: Dict[str, Any], minutes: int, prompt: str,
            turn_silence_ms: Optional[int], reasoning_effort: str,
            tools: Optional[list], cough_clip: str, out_dir: Path,
            index: int, scenario: str = "deployed", with_hold: bool = False) -> Path:
    """One room: create the run, send in the fixture, wait, measure, write."""
    pair = ensure_rehearsal_interview(fixture, minutes)
    row = build_run_row(interview=pair["interview"], arm=arm, fixture=fixture,
                        prompt=prompt, minutes=minutes, turn_silence_ms=turn_silence_ms,
                        reasoning_effort=reasoning_effort, tools=tools,
                        scenario=scenario, with_hold=with_hold)
    run = create_run(row)
    logger.info("rehearsal run %s (%s, %s) created", run["id"], arm, fixture["id"])
    persona = fixture_persona(fixture)
    start_fixture(run["id"], fixture, persona, minutes, cough_clip,
                  scenario=scenario, with_hold=with_hold)
    logger.info("fixture %s is calling into room %s", fixture["id"], run["id"])
    run = wait_for_room(run["id"], minutes)
    if room_refused(run.get("scenario_trace") or []):
        # Nothing to transcribe; the record says why, and no further room is
        # placed (Oct 23 2026: four rooms in a row were refused at start
        # while the account was out of credit).
        record = result_record(arm=arm, fixture=fixture, run=run, metrics={},
                               refused=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{arm}_{fixture['id']}_{index}_{str(run['id'])[:8]}.json"
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        raise RoomsRefused(f"xAI refused every session in room {run['id']}")
    return measure_and_write(arm=arm, fixture=fixture, run=run, out_dir=out_dir,
                             index=index)


# ---------------------------------------------------------------------------
# Before a room, and what a room says about itself
# ---------------------------------------------------------------------------

def xai_preflight(api_key: Optional[str] = None, *, post: Any = None) -> Dict[str, Any]:
    """One tiny text request before any room is placed. A 401/403 (or a 429
    that names credit) means every Voice Agent session would be refused too:
    on Oct 23 2026 a rehearsal placed four rooms, and a probe two more, on an
    account that was out of credit. Anything else (a 5xx, a timeout, a 400
    on the request shape) is reported and the rehearsal goes ahead."""
    key = api_key if api_key is not None else (
        os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY") or "")
    if not key:
        return {"ok": True, "checked": False, "why": "no xAI key here; not checked"}
    if post is None:
        import requests
        post = requests.post
    try:
        resp = post(PREFLIGHT_URL, timeout=60,
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json={"model": PREFLIGHT_MODEL, "max_tokens": 16,
                          "messages": [{"role": "user", "content": "Reply with: ok"}]})
    except Exception as exc:  # noqa: BLE001 - a network fault is not a refusal
        return {"ok": True, "checked": False, "why": f"xAI not reached ({exc}); going ahead"}
    status = int(getattr(resp, "status_code", 0) or 0)
    body = str(getattr(resp, "text", "") or "")[:400]
    if status in (401, 403) or (status == 429 and _CREDIT_RE.search(body)):
        why = ("the account is out of credit or at its spending limit"
               if _CREDIT_RE.search(body) else "the key was refused")
        return {"ok": False, "checked": True, "status": status, "why": why, "body": body}
    if status >= 400:
        return {"ok": True, "checked": True, "status": status,
                "why": f"xAI answered {status}; not a refusal, going ahead"}
    return {"ok": True, "checked": True, "status": status, "why": "xAI accepts requests"}


def _grok_lines(trace: List[Dict[str, Any]]) -> List[str]:
    return [str(e.get("d") or "") for e in trace
            if isinstance(e, dict) and e.get("e") == "grok"]


def room_refused(trace: List[Dict[str, Any]]) -> bool:
    """Every session the room opened was refused and Mira never answered."""
    lines = _grok_lines(trace)
    started = sum(1 for d in lines if d.startswith("agent created")
                  or d.startswith("rescued after"))
    refused = sum(1 for d in lines if _REFUSED_RE.search(d))
    answered = any(d == "response done" for d in lines)
    return refused > 0 and refused >= started and not answered


def round_questions(path: Optional[Path] = None) -> List[tuple]:
    """The room's ROUND_QUESTIONS, read from the scenario itself so the
    report and the room can never name different questions. Each pattern is
    widened with the matching fire_interviews.CLOSING_ROUND pattern (the
    same questions in the same order, without the show's own): the room's
    "interviewed again" pattern does not hear "would you do this again",
    which is how she usually asks it."""
    if path is None:
        from voximplant.api_clients.voximplant_client import _SCENARIO_PATH
        path = _SCENARIO_PATH
    src = Path(path).read_text(encoding="utf-8")
    block = src[src.index("const ROUND_QUESTIONS = ["):]
    block = block[:block.index("];")]
    room = []
    for line in block.splitlines()[1:]:
        m = re.match(r'^\s*\[\s*"([^"]+)",\s*/(.+)/(\w*)\s*\],?\s*$', line)
        if m:
            room.append((m.group(1), m.group(2)))
    try:
        from fire_interviews import CLOSING_ROUND
        wider = [rx.pattern for _, rx in CLOSING_ROUND]
    except Exception:  # noqa: BLE001 - the room's own patterns still work
        wider = []
    out = []
    for i, (label, pattern) in enumerate(room):
        extra = wider[i - 1] if 1 <= i <= len(wider) else ""
        out.append((label, re.compile(f"(?:{pattern})" + (f"|(?:{extra})" if extra else ""), re.I)))
    return out


def _clock(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _transcript_lines(transcript: str) -> List[tuple]:
    out = []
    for raw in (transcript or "").splitlines():
        m = LINE_RE.match(raw.strip())
        if not m:
            continue
        a, b, c = int(m.group(1)), int(m.group(2)), m.group(3)
        sec = a * 3600 + b * 60 + int(c) if c else a * 60 + b
        out.append((float(sec), m.group(4).strip(), m.group(5)))
    return out


def room_log(trace: List[Dict[str, Any]], transcript: str = "") -> Dict[str, Any]:
    """What the room's own trace and Mira's words say happened: the
    sessions, the closing round line by line, holds, the turn decisions,
    and, for each closing question, when the room handed it and when her
    words carried it. This is what found every fault the rehearsals have
    found; the medians found none."""
    from audio_metrics import _trace_time, closing_round
    events = [e for e in (trace or []) if isinstance(e, dict)]
    times = [_trace_time(e) for e in events]
    t0 = next((t for t in times if t is not None), None)

    def at(i: int) -> Optional[float]:
        t = times[i]
        return None if (t is None or t0 is None) else (t - t0).total_seconds()

    last = max((x for x in (at(i) for i in range(len(events))) if x is not None), default=None)
    lines = _grok_lines(events)
    kinds = [(str(e.get("e") or ""), str(e.get("d") or "")) for e in events]
    log: Dict[str, Any] = {
        "length_min": None if last is None else round(last / 60.0, 1),
        "sessions": {
            "started": sum(1 for d in lines if d.startswith("agent created")
                           or d.startswith("rescued after")),
            "refused": sum(1 for d in lines if _REFUSED_RE.search(d)),
            "rescued": sum(1 for d in lines if d.startswith("rescued after")),
            "gave_up": any(d.startswith("gave up") for d in lines),
        },
        "ending": next((d[len("ending: "):] for k, d in reversed(kinds)
                        if k == "room" and d.startswith("ending: ")), None),
        "holds": {"entered": sum(1 for k, d in kinds if k == "hold" and d.startswith("entered")),
                  "left": sum(1 for k, d in kinds if k == "hold" and d.startswith("left")),
                  "check_ins": sum(1 for k, d in kinds if k == "hold" and d.startswith("check-in"))},
        "turns": {
            "server_turns_rerouted": sum(1 for k, d in kinds if k == "turn"
                                         and d.startswith("server turn after guest speech")),
            "unfinished_clause_waits": sum(1 for k, d in kinds if k == "turn"
                                           and d.startswith("clause reads unfinished")),
            "dead_air_nudges": sum(1 for k, d in kinds if k == "turn"
                                   and d.startswith("dead air")),
            "unrequested_cancelled": sum(1 for k, d in kinds if k == "turn"
                                         and d.startswith("cancelled a turn nobody")),
        },
        "alerts": [d for k, d in kinds if k == "audio_path" and d.startswith("nothing heard")],
        "round": closing_round(events),
        "round_lines": [{"at": _clock(at(i)), "line": d}
                        for i, (k, d) in enumerate(kinds) if k in ("round", "close")],
        "questions": [],
    }
    handed: Dict[str, float] = {}
    order: List[str] = []
    begin = None
    for i, (k, d) in enumerate(kinds):
        if k != "round":
            continue
        if begin is None:
            begin = at(i)
        m = re.match(r"^asked \d+/\d+:\s*(.*?)(?:\s*\(her own words\))?$", d)
        if m and m.group(1) not in handed and at(i) is not None:
            handed[m.group(1)] = at(i)
            order.append(m.group(1))
    if not (transcript and handed):
        return log
    # Her words from just before the round, joined into one stream: Whisper
    # breaks a sentence across segments ("Who should I interview" / "next?").
    start_from = (begin or 0.0) - 60.0
    stream, starts = "", []
    for sec, who, text in _transcript_lines(transcript):
        if who.lower() == "mira" and sec >= start_from:
            starts.append((len(stream), sec))
            stream += text + " "

    def heard_at(rx) -> Optional[float]:
        m = rx.search(stream)
        if not m:
            return None
        return max((sec for off, sec in starts if off <= m.start()), default=None)

    for label, rx in round_questions():
        heard = heard_at(rx)
        hand = handed.get(label)
        nxt = None
        if label in order and order.index(label) + 1 < len(order):
            nxt = handed[order[order.index(label) + 1]]
        late = bool(heard is not None and hand is not None and (
            heard - hand > ROUND_LAG_SEC or (nxt is not None and heard > nxt)))
        log["questions"].append({"question": label, "handed_at": _clock(hand),
                                 "heard_at": _clock(heard), "late": late,
                                 "never_heard": heard is None})
    return log


def room_checks(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One room against the §7.7 targets a room can be held to. ``ok`` is
    None where the room cannot say (no audio, no closing round reached)."""
    m = record.get("metrics") or {}
    log = record.get("room_log") or {}
    planned = record.get("planned_minutes") or (record.get("config") or {}).get("minutes")
    length = log.get("length_min")
    checks: List[Dict[str, Any]] = []

    def add(name, ok, detail):
        checks.append({"check": name, "ok": ok, "detail": detail})

    if record.get("refused"):
        add("room ran", False, "xAI refused every session; nothing was measured")
        return checks
    ran = None if (length is None or not planned) else length >= ROOM_RAN_SHARE * float(planned)
    add("room ran", ran, f"{length} of {planned} planned minutes")
    sa = m.get("self_answered_turns")
    add("no self-answered turns", None if sa is None else sa == 0, f"{sa}")
    ov = m.get("overlap_events")
    rate = None if (ov is None or not length) else ov / (float(length) / 10.0)
    add("talking over under 1 per 10 min", None if rate is None else rate < OVERLAP_PER_10_MIN_MAX,
        f"{ov} events" + ("" if rate is None else f" ({rate:.1f} per 10 min)"))
    rnd = log.get("round") or {}
    qs = log.get("questions") or []
    if not rnd.get("round_asked"):
        add("closing round", None, "the round did not begin")
    else:
        lost = [q["question"] for q in qs if q.get("never_heard")]
        late = [q["question"] for q in qs if q.get("late")]
        ok = (bool(m.get("closing_round_complete", rnd.get("closing_round_complete")))
              and not lost and not late)
        add("closing round", ok,
            f"{rnd.get('round_answered')}/{rnd.get('round_asked')} answered, "
            f"{rnd.get('round_late', 0)} said late, {rnd.get('round_repeats', 0)} repeated"
            + (f"; never in her words: {', '.join(lost)}" if lost else "")
            + (f"; a turn behind: {', '.join(late)}" if late else ""))
    sess = log.get("sessions") or {}
    add("no dropped session", None if not sess else (sess.get("rescued", 0) == 0
                                                     and not sess.get("gave_up")),
        f"{sess.get('rescued', 0)} rescue(s)" + (", gave up" if sess.get("gave_up") else ""))
    return checks


def single_arm_verdict(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """PASS when every room ran and no room fails a check it can answer.
    A room that could not answer a check (the round never began) is
    INCONCLUSIVE on it, never a pass on it."""
    if not records:
        return {"result": "INCONCLUSIVE", "why": "no room was measured", "rooms": []}
    rooms = [{"run_id": r.get("run_id"), "arm": r.get("arm"), "checks": room_checks(r)}
             for r in records]
    oks = [c["ok"] for room in rooms for c in room["checks"]]
    if any(o is False for o in oks):
        return {"result": "FAIL", "why": "a room failed a check (see the room log)", "rooms": rooms}
    if any(o is None for o in oks):
        return {"result": "INCONCLUSIVE", "why": "a room could not answer every check",
                "rooms": rooms}
    return {"result": "PASS", "why": "every room ran clean on the room's checks", "rooms": rooms}


def voice_minutes(records: List[Dict[str, Any]]) -> float:
    return sum(float((r.get("room_log") or {}).get("length_min") or 0.0)
               for r in records) * SESSIONS_PER_ROOM


def room_markdown(record: Dict[str, Any]) -> str:
    """One room's log for the step summary."""
    log = record.get("room_log") or {}
    sess = log.get("sessions") or {}
    turns = log.get("turns") or {}
    holds = log.get("holds") or {}
    out = [f"### {record.get('arm')} · {record.get('fixture')} · {str(record.get('run_id'))[:8]}", ""]
    if record.get("listen_url"):
        out.append(f"Listen: {record['listen_url']}")
        out.append("")
    out.append(f"- length {log.get('length_min')} min of {record.get('planned_minutes')}; "
               f"ending {log.get('ending')}; sessions {sess.get('started', 0)} started, "
               f"{sess.get('refused', 0)} refused, {sess.get('rescued', 0)} rescued")
    out.append(f"- turns: {turns.get('server_turns_rerouted', 0)} server turns rerouted, "
               f"{turns.get('unfinished_clause_waits', 0)} unfinished-clause waits, "
               f"{turns.get('dead_air_nudges', 0)} dead-air nudges; holds "
               f"{holds.get('entered', 0)} in / {holds.get('left', 0)} out")
    for c in room_checks(record):
        mark = "—" if c["ok"] is None else ("yes" if c["ok"] else "**no**")
        out.append(f"- {c['check']}: {mark} ({c['detail']})")
    qs = log.get("questions") or []
    if qs:
        out += ["", "Each closing question: when the room handed it, and the Whisper segment "
                "where her words first carried it (the room's own patterns; a reworded "
                "question reads as never, so listen before calling it lost).", "",
                "| question | handed | in her words |", "|---|---|---|"]
        for q in qs:
            heard = q.get("heard_at") or "**never**"
            if q.get("late"):
                heard += " (**late**)"
            out.append(f"| {q['question']} | {q.get('handed_at') or '—'} | {heard} |")
    if log.get("round_lines"):
        out += ["", "<details><summary>closing round, as the room traced it</summary>", ""]
        out += [f"    {x['at']}  {x['line']}" for x in log["round_lines"]]
        out += ["", "</details>"]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# The report: PASS only on the §7.5 rule
# ---------------------------------------------------------------------------

def _median(values: List[float]) -> Optional[float]:
    vals = [float(v) for v in values if v is not None]
    return statistics.median(vals) if vals else None


def summarise(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Per arm: the median of every numeric metric across its rooms, the
    room count and one listen link."""
    out: Dict[str, Dict[str, Any]] = {}
    for arm in ARMS:
        rows = [r for r in records if r.get("arm") == arm]
        if not rows:
            continue
        keys = sorted({k for r in rows for k, v in (r.get("metrics") or {}).items()
                       if isinstance(v, (int, float)) and not isinstance(v, bool)})
        medians = {k: _median([(r.get("metrics") or {}).get(k) for r in rows]) for k in keys}
        out[arm] = {"rooms": len(rows), "medians": medians,
                    "listen_url": next((r.get("listen_url") for r in rows
                                        if r.get("listen_url")), ""),
                    "fixtures": sorted({r.get("fixture") for r in rows})}
    return out


def _distance_from_band(value: Optional[float], band: tuple) -> Optional[float]:
    if value is None:
        return None
    lo, hi = band
    if value < lo:
        return lo - value
    if value > hi:
        return value - hi
    return 0.0


def verdict(summary: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """PASS when proposed beats current on every MUST_BEAT metric and is not
    further from the turn-length band than current. A missing arm or metric
    is INCONCLUSIVE, never a pass."""
    checks: List[Dict[str, Any]] = []
    if "proposed" not in summary or "current" not in summary:
        return {"result": "INCONCLUSIVE", "why": "both arms are needed", "checks": checks}
    p, c = summary["proposed"]["medians"], summary["current"]["medians"]
    ok = True
    inconclusive = False
    for key, direction in MUST_BEAT:
        pv, cv = p.get(key), c.get(key)
        if pv is None or cv is None:
            checks.append({"metric": key, "proposed": pv, "current": cv, "ok": None})
            inconclusive = True
            continue
        # Zero is the floor of a "lower" count: when both arms sit on it the
        # proposal cannot beat current there and has not lost (the third
        # rehearsal read FAIL on 0 self-answered turns against 0).
        floor = direction == "lower" and pv == 0 and cv == 0
        passed = floor or (pv < cv if direction == "lower" else pv > cv)
        checks.append({"metric": key, "proposed": pv, "current": cv, "ok": passed,
                       "rule": f"proposed {direction}" + (" (both at zero)" if floor else "")})
        ok = ok and passed
    key, band = MUST_NOT_LOSE
    pv, cv = p.get(key), c.get(key)
    pd, cd = _distance_from_band(pv, band), _distance_from_band(cv, band)
    if pd is None or cd is None:
        checks.append({"metric": key, "proposed": pv, "current": cv, "ok": None})
        inconclusive = True
    else:
        passed = pd <= cd
        checks.append({"metric": key, "proposed": pv, "current": cv, "ok": passed,
                       "rule": f"not further from {band[0]:.0f}-{band[1]:.0f} s than current"})
        ok = ok and passed
    if inconclusive:
        return {"result": "INCONCLUSIVE", "why": "a metric is missing on one arm",
                "checks": checks}
    return {"result": "PASS" if ok else "FAIL",
            "why": ("proposed beats current on overlap, self-answered turns and guest "
                    "words per answer without losing on turn length" if ok
                    else "proposed does not beat current on every required metric"),
            "checks": checks}


def load_records(path: Path) -> List[Dict[str, Any]]:
    files = [path] if path.is_file() else sorted(path.glob("*.json"))
    records = []
    for f in files:
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict) and rec.get("arm") in ARMS:
            records.append(rec)
    return records


def report_markdown(summary: Dict[str, Dict[str, Any]], result: Dict[str, Any],
                    records: Optional[List[Dict[str, Any]]] = None) -> str:
    lines = [f"## Rehearsal: **{result['result']}**", "", result.get("why", ""), ""]
    def fmt(v):
        return "—" if v is None else (f"{v:.1f}" if isinstance(v, float) else str(v))

    if result.get("checks"):
        lines.append("| metric | proposed | current | rule | ok |")
        lines.append("|---|---|---|---|---|")
        for ch in result.get("checks", []):
            ok = "—" if ch.get("ok") is None else ("yes" if ch["ok"] else "no")
            lines.append(f"| {ch['metric']} | {fmt(ch.get('proposed'))} | {fmt(ch.get('current'))} "
                         f"| {ch.get('rule', '')} | {ok} |")
        lines.append("")
    for arm, s in summary.items():
        lines.append(f"- **{arm}**: {s['rooms']} room(s), fixtures {', '.join(s['fixtures'])}"
                     + (f", listen: {s['listen_url']}" if s.get("listen_url") else ""))
    if records:
        minutes = voice_minutes(records)
        lines.append(f"- about {minutes:.0f} Voice Agent minutes "
                     f"(~${minutes * VOICE_COST_PER_MIN:.2f} at ${VOICE_COST_PER_MIN:.2f}/min, "
                     "Mira and the fixture each count)")
        lines.append("")
        for r in records:
            lines.append(room_markdown(r))
            lines.append("")
    lines.append("")
    lines.append("A PASS ships to a real guest only after the operator has listened to the "
                 "room (see the rehearsal doc under docs/).")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_run(args: argparse.Namespace) -> int:
    fixtures = load_fixtures()
    fixture = fixtures.get(args.fixture)
    if not fixture:
        print(f"unknown fixture {args.fixture!r}; known: {', '.join(sorted(fixtures))}",
              file=sys.stderr)
        return 2
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    elif args.arm == "proposed":
        prompt = proposed_prompt(fixture)
    else:
        prompt = current_prompt()
    tools: Optional[list] = [] if args.tools == "none" else None
    if args.minutes < ROOM_MIN_MINUTES:
        print(f"::warning::the room reads {args.minutes} planned minutes as a 45-minute "
              f"interview; under {ROOM_MIN_MINUTES} the closing round never begins")
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT_DIR / _now().strftime("%Y%m%d")
    for i in range(1, args.repeat + 1):
        try:
            run_one(arm=args.arm, fixture=fixture, minutes=args.minutes, prompt=prompt,
                    turn_silence_ms=args.turn_silence_ms, reasoning_effort=args.reasoning_effort,
                    tools=tools, cough_clip=args.cough_clip or "", out_dir=out_dir, index=i,
                    scenario=args.scenario, with_hold=args.with_hold)
        except RoomsRefused as exc:
            print(f"::error::{exc}; no further room was placed")
            return 3
    print(f"{args.repeat} {args.arm} room(s) measured into {out_dir}")
    return 0


def _cmd_preflight(args: argparse.Namespace) -> int:
    result = xai_preflight()
    if not result["ok"]:
        print(f"::error::xAI refuses requests ({result.get('status')}): {result['why']}. "
              "No room was placed.")
        return 3
    print(f"xAI preflight: {result['why']}")
    return 0


def parse_remeasure(spec: str) -> List[tuple]:
    """``"current:<run id>,proposed:<run id>"`` -> [(arm, run id), ...]."""
    pairs = []
    for item in (spec or "").replace(" ", "").split(","):
        if not item:
            continue
        arm, _, run_id = item.partition(":")
        if arm not in ARMS or not re.fullmatch(r"[0-9a-fA-F-]{36}", run_id):
            raise ValueError(f"not an arm:run-id pair: {item!r}")
        pairs.append((arm, run_id))
    return pairs


def _cmd_remeasure(args: argparse.Namespace) -> int:
    """Measure rooms that already ran, without running them again: the
    recordings stay on Voximplant for weeks, a room costs a Voice Agent
    session on both sides, and a measurement fix should not need a rerun."""
    from common import sb_select
    fixtures = load_fixtures()
    fixture = fixtures.get(args.fixture)
    if not fixture:
        print(f"unknown fixture {args.fixture!r}", file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT_DIR / _now().strftime("%Y%m%d")
    for i, (arm, run_id) in enumerate(parse_remeasure(args.runs), start=1):
        rows = sb_select("interview_runs", f"id=eq.{run_id}")
        if not rows or rows[0].get("session_kind") != "rehearsal":
            print(f"{run_id} is not a rehearsal run", file=sys.stderr)
            return 2
        measure_and_write(arm=arm, fixture=fixture, run=rows[0], out_dir=out_dir, index=i)
    print(f"re-measured into {out_dir}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    records = load_records(Path(args.path))
    summary = summarise(records)
    # Both arms: the §7.5 comparison. One arm (the default since Oct 23
    # 2026): every room against the room's own checks.
    result = (verdict(summary) if {"proposed", "current"} <= set(summary)
              else single_arm_verdict(records))
    md = report_markdown(summary, result, records)
    print(md)
    # A run that died before any room (an apt stall installing ffmpeg) has
    # no output directory; the report still writes its INCONCLUSIVE line.
    if args.summary_file:
        Path(args.summary_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary_file).write_text(md, encoding="utf-8")
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(
            {"summary": summary, "verdict": result, "records": len(records)}, indent=2),
            encoding="utf-8")
    return 0 if result["result"] == "PASS" else 1


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="rehearse one arm on one fixture")
    r.add_argument("--arm", choices=ARMS, required=True)
    r.add_argument("--fixture", required=True)
    r.add_argument("--minutes", type=int, default=ROOM_MIN_MINUTES)
    r.add_argument("--repeat", type=int, default=1)
    r.add_argument("--turn-silence-ms", type=int, default=None,
                   help="override the end-of-turn silence for this arm")
    r.add_argument("--reasoning-effort", default="",
                   help="interview_runs.reasoning_effort for this arm (low|none|high)")
    r.add_argument("--tools", choices=("default", "none"), default="default")
    r.add_argument("--prompt-file", default="",
                   help="use this file as the prompt instead of compiling/looking one up")
    r.add_argument("--cough-clip", default=os.environ.get("REHEARSAL_COUGH_CLIP", ""))
    r.add_argument("--out-dir", default="")
    r.add_argument("--scenario", choices=tuple(SCENARIOS), default="deployed",
                   help="candidate = this checkout's room, uploaded beside the live one")
    r.add_argument("--with-hold", action="store_true",
                   help="the fixture steps away to take a call at minute four")
    r.set_defaults(func=_cmd_run)
    f = sub.add_parser("preflight", help="stop before any room if xAI refuses requests")
    f.set_defaults(func=_cmd_preflight)
    m = sub.add_parser("remeasure", help="measure rooms that already ran")
    m.add_argument("--runs", required=True, help="current:<run id>,proposed:<run id>")
    m.add_argument("--fixture", required=True)
    m.add_argument("--out-dir", default="")
    m.set_defaults(func=_cmd_remeasure)
    p = sub.add_parser("report", help="compare the arms in a results directory")
    p.add_argument("path")
    p.add_argument("--summary-file", default="")
    p.add_argument("--json-out", default="")
    p.set_defaults(func=_cmd_report)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
