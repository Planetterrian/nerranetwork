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
                  guest_channel: str = "") -> Dict[str, Any]:
    cfg = (run.get("grok_session_log") or {}).get("rehearsal") or {}
    return {
        "arm": arm, "fixture": fixture["id"], "run_id": run.get("id"),
        "measured_at": _iso(_now()), "config": cfg,
        "listen_url": listen_url(run), "metrics": metrics,
        "guest_channel": guest_channel, "transcript": transcript,
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
    return measure_and_write(arm=arm, fixture=fixture, run=run, out_dir=out_dir,
                             index=index)


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


def report_markdown(summary: Dict[str, Dict[str, Any]], result: Dict[str, Any]) -> str:
    lines = [f"## Rehearsal: **{result['result']}**", "", result.get("why", ""), ""]
    lines.append("| metric | proposed | current | rule | ok |")
    lines.append("|---|---|---|---|---|")
    def fmt(v):
        return "—" if v is None else (f"{v:.1f}" if isinstance(v, float) else str(v))

    for ch in result.get("checks", []):
        ok = "—" if ch.get("ok") is None else ("yes" if ch["ok"] else "no")
        lines.append(f"| {ch['metric']} | {fmt(ch.get('proposed'))} | {fmt(ch.get('current'))} "
                     f"| {ch.get('rule', '')} | {ok} |")
    lines.append("")
    for arm, s in summary.items():
        lines.append(f"- **{arm}**: {s['rooms']} room(s), fixtures {', '.join(s['fixtures'])}"
                     + (f", listen: {s['listen_url']}" if s.get("listen_url") else ""))
    lines.append("")
    lines.append("A PASS ships to a real guest only after the operator has listened to one "
                 "run of each arm (see the rehearsal doc under docs/).")
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
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT_DIR / _now().strftime("%Y%m%d")
    for i in range(1, args.repeat + 1):
        run_one(arm=args.arm, fixture=fixture, minutes=args.minutes, prompt=prompt,
                turn_silence_ms=args.turn_silence_ms, reasoning_effort=args.reasoning_effort,
                tools=tools, cough_clip=args.cough_clip or "", out_dir=out_dir, index=i,
                scenario=args.scenario, with_hold=args.with_hold)
    print(f"{args.repeat} {args.arm} room(s) measured into {out_dir}")
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
    result = verdict(summary)
    md = report_markdown(summary, result)
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
    r.add_argument("--minutes", type=int, default=10)
    r.add_argument("--repeat", type=int, default=3)
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
