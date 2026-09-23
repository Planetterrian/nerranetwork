#!/usr/bin/env python3
"""Post-interview processing (nerra_voices_post_interview.yml).

Triggered by ``repository_dispatch: interview-complete`` — the Worker
receives the Voximplant hangup webhook, stores the raw payload on the run
row, and dispatches this workflow with the run id.

Steps: pull the recording → durable copies in R2 (/raw/) → leveled mix →
per-channel STT (stereo channels ARE the diarization) → 8 LLM editorial
passes (schema-validated, one retry each) → ``editorial_packages`` row →
Slack ping to Patrick with the review link (gate 1).

Phase 2 co-host (Sept 2026): when Patrick sat in as co-host the run also
carries ``recording_host_url`` / ``recording_mira_url`` (Voximplant
per-leg recordings) and ``local_guest_url`` / ``local_host_url`` (R2
manifest keys of the in-browser recordings). :func:`build_tracks` picks
one clean mono track per speaker — local when its upload is complete,
Voximplant leg otherwise — Whisper runs per track, the transcript is
labelled ``Mira:`` / ``Patrick:`` / ``<Guest>:`` and the mix is
``mix_three``. No host track at all → the original two-track path,
unchanged.

A ``failed`` run (guest never answered) short-circuits: interview marked
missed, reschedule email sent, no-show count incremented (spec §7/§11.7).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

from common import (  # noqa: E402
    OPERATOR_EMAIL, cohost_label, cohost_name, llm, load_prompt, logger,
    new_review_token, notify_operator, package_review_token,
    parse_json_lenient, r2_upload, render_email, sb_insert, sb_select,
    sb_update, send_email, show_for,
    guest_links_markdown,
)

sys.path.insert(0, str(Path(__file__).parent))
from address import written as written_address  # noqa: E402
from audio.local_tracks import (  # noqa: E402
    ROOM_MIN_WINDOWS, align_to_reference, align_to_room, fetch_local_track,
    place_at,
)
from audio.bleed import strip_bleed  # noqa: E402
from audio.mix_tracks import (  # noqa: E402
    duration_seconds, mix_interview, mix_same_clock, mix_three, mix_two,
    split_channels, split_left,
)
from learning import (  # noqa: E402
    adopt_lessons, guest_feedback, host_formulas, lessons_for_prompt, measure,
    parse_transcript, retire_lessons, save_grade, save_host_phrases,
    save_metrics, save_proposed_lessons, session_events_summary,
)
from validators.schema_validators import validate_pass_output  # noqa: E402

SHORT_CALL_THRESHOLD_SEC = 10 * 60
LOW_STT_CONFIDENCE = 0.55
REVIEW_BASE = "https://api.nerranetwork.com/voices/admin/review"

EDITORIAL_PASSES = [
    ("01_clean_transcript.txt", "transcript_cleaned"),
    ("02_chapter_markers.txt", "chapter_markers"),
    ("03_episode_notes.txt", "episode_notes"),
    ("04_classify_show_fits.txt", "topical_show_fits"),
    ("05_suggest_clips.txt", "clip_suggestions"),
    ("06_social_copy.txt", "social_copy"),
    ("07_generate_callouts.txt", "cross_show_callouts"),
    ("08_newsletter_draft.txt", "newsletter_draft"),
]
JSON_PASSES = {"chapter_markers", "topical_show_fits", "clip_suggestions",
               "social_copy", "cross_show_callouts"}


def _run_row() -> dict:
    run_id = os.environ.get("INTERVIEW_RUN_ID", "").strip()
    if not run_id:
        raise RuntimeError("INTERVIEW_RUN_ID env var is required")
    rows = sb_select("interview_runs", f"id=eq.{run_id}")
    if not rows:
        raise RuntimeError(f"interview_runs row {run_id} not found")
    return rows[0]


def _interview_and_app(run: dict) -> tuple[dict, dict]:
    interview = sb_select("interviews", f"id=eq.{run['interview_id']}")[0]
    app = sb_select("guest_applications",
                    f"id=eq.{interview['application_id']}")[0]
    return interview, app


def _anyone_joined(run: dict) -> bool:
    """Did a guest ever connect? The room's own trace is the record.

    A room with no guest leg produced no recording, so everything downstream
    is meaningless. Absent or unreadable trace counts as "yes" — an empty
    trace is not proof of an empty room, and it is better to try to process a
    real interview and fail loudly than to file one as a no-show.
    """
    trace = run.get("scenario_trace")
    if not isinstance(trace, list) or not trace:
        return True
    for event in trace:
        detail = ""
        if isinstance(event, dict):
            detail = str(event.get("d", ""))
        elif isinstance(event, str):
            detail = event
        if "guest" in detail and "joined" in detail:
            return True
    return False


def handle_missed(run: dict, interview: dict, app: dict) -> int:
    """Guest didn't answer (spec §7 row 1 + §11.7 no-show policy)."""
    show = show_for(interview, app)
    no_shows = int(interview.get("no_show_count") or 0) + 1
    status = "missed" if no_shows < 2 else "cancelled"
    sb_update("interviews", f"id=eq.{interview['id']}",
              {"status": status, "no_show_count": no_shows})
    if no_shows < 2:
        html = render_email("voices_interview_reminder.j2", show=show,
                            guest_name=app["name"], missed=True,
                            booking_url=os.environ.get("CALCOM_BOOKING_URL", ""))
        send_email(app["email"],
                   f"We missed you — reschedule your {show.short_label} interview",
                   html)
        notify_operator(show.slack(
            f"{app['name']} no-show #{no_shows} — reschedule email sent"))
    else:
        sb_update("guest_applications", f"id=eq.{app['id']}", {"status": "lapsed"})
        notify_operator(show.slack(
            f"{app['name']} second no-show — application lapsed"))
    return 0


def _ext_of(url: str, default: str = "mp3") -> str:
    # Keep the source container extension: WebRTC recordings are MP4
    # (video + stereo audio), PSTN are MP3. ffmpeg sniffs by content, but
    # a truthful extension keeps R2 keys and tooling honest.
    ext = Path(url.split("?", 1)[0]).suffix.lstrip(".").lower() or default
    return ext if ext in ("mp3", "mp4", "webm", "wav", "m4a") else default


def _download(url: str, dest: Path, timeout: int = 600) -> Path:
    with requests.get(url, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_content(1 << 16):
                fh.write(chunk)
    return dest


def fetch_recording(run: dict, workdir: Path) -> Path:
    """The guest's Voximplant recording — the one that has the interview on it.

    Sept 14 2026 (John Capobianco). He joined, dropped 50 seconds later, and
    rejoined six minutes after that; the interview then ran for forty minutes.
    Voximplant records each leg separately, so the FIRST leg — the 65-second
    false start — is ``voximplant_record_url`` and the forty minutes are in
    ``extra_guest_record_urls``. This function took the first one, and the
    episode came back with a transcript containing almost none of his answers.
    The first leg is not "the recording"; the longest one is.
    """
    log = run.get("grok_session_log") or {}
    candidates = [run.get("recording_guest_url") or "",   # already in R2 (re-run)
                  log.get("voximplant_record_url") or ""]
    candidates += [u for u in (log.get("extra_guest_record_urls") or []) if u]
    candidates = [u for u in candidates if u]
    if not candidates:
        raise RuntimeError("run has no recording URL — scenario upload failed?")

    best: Path | None = None
    best_seconds = 0.0
    for i, url in enumerate(candidates):
        try:
            leg = _download(url, workdir / f"raw_leg_{i}.{_ext_of(url)}")
        except Exception as err:            # a dead leg URL is not fatal
            logger.warning("guest leg %d did not download: %s", i, err)
            continue
        seconds = duration_seconds(leg)
        logger.info("guest leg %d: %.1fs (%d bytes)", i, seconds, leg.stat().st_size)
        if seconds > best_seconds:
            best, best_seconds = leg, seconds
    if best is None:
        raise RuntimeError("no guest leg recording could be downloaded")
    if len(candidates) > 1:
        logger.info("guest recording: using the longest of %d legs (%.1fs)",
                    len(candidates), best_seconds)
    if best.stat().st_size < 50_000:
        raise RuntimeError(f"recording suspiciously small ({best.stat().st_size} bytes)")
    return best


def fetch_leg_recording(url: str, workdir: Path, name: str) -> Path | None:
    """Best-effort download of a Phase 2 per-leg Voximplant recording
    (host leg / Mira recorder). ``None`` when absent, unreachable or too
    small to be a real track (a host who never joined leaves a stub)."""
    url = (url or "").strip()
    if not url:
        return None
    try:
        path = _download(url, workdir / f"raw_{name}.{_ext_of(url)}")
    except Exception as exc:  # noqa: BLE001 — per-leg tracks are optional
        logger.warning("%s leg recording fetch failed (%s) — fallback", name, exc)
        return None
    if path.stat().st_size < 50_000:
        logger.warning("%s leg recording too small (%d bytes) — ignored",
                       name, path.stat().st_size)
        return None
    return path


def leg_recordings(run: dict, role: str, workdir: Path) -> list[Path]:
    """Every recording of this person's legs, in the order they happened.

    Sept 15 2026 (Adrian Wolfberg). Patrick's connection dropped and came
    back four times in one interview: legs of forty minutes, two minutes,
    six minutes and thirty seconds. Taking the longest keeps him in the
    room for the first forty and deletes him from the rest of his own
    interview. Every leg is real audio of a person talking; they belong in
    the episode, each at the point in the room where it happened.
    """
    log = run.get("grok_session_log") or {}
    urls = [run.get(f"recording_{role}_url") or ""]
    urls += [u for u in (log.get(f"extra_{role}_record_urls") or []) if u]
    out = []
    for i, url in enumerate(u for u in urls if u):
        leg = fetch_leg_recording(url, workdir, f"{role}{i or ''}")
        if leg is None:
            continue
        logger.info("%s leg %d: %.1fs", role, i, duration_seconds(leg))
        out.append(leg)
    return out


def longest_leg_recording(run: dict, role: str, workdir: Path) -> Path | None:
    """The co-host's recording, when he joined more than once.

    Sept 14 2026 (Vincent Rylan). Patrick's connection dropped at 22:12:27
    and came back nine seconds later, which is two legs: thirteen minutes and
    thirty. The run row names the first one, so the co-host would have gone
    missing from the last thirty minutes of his own interview. Same rule as
    the guest's: the longest leg is the recording.
    """
    log = run.get("grok_session_log") or {}
    urls = [run.get(f"recording_{role}_url") or ""]
    urls += [u for u in (log.get(f"extra_{role}_record_urls") or []) if u]
    urls = [u for u in urls if u]
    best, best_seconds = None, 0.0
    for i, url in enumerate(urls):
        leg = fetch_leg_recording(url, workdir, f"{role}{i or ''}")
        if leg is None:
            continue
        seconds = duration_seconds(leg)
        logger.info("%s leg %d: %.1fs", role, i, seconds)
        if seconds > best_seconds:
            best, best_seconds = leg, seconds
    if best is not None and len(urls) > 1:
        logger.info("%s recording: using the longest of %d legs (%.1fs)",
                    role, len(urls), best_seconds)
    return best


# A browser recording is better than a conference leg — 192 kbps against a
# codec, and it is the voice as the microphone heard it. But only if it is
# actually there. John Capobianco's browser uploaded 65 seconds of a
# forty-minute interview (he dropped and rejoined, and the second join
# recorded nothing), and the pipeline still preferred it, which is how an
# episode came back with a transcript missing almost every answer.
COVERAGE_MIN = 0.80


def _covers(local: Path, reference: Path | None, who: str) -> bool:
    if reference is None:
        return True
    try:
        local_sec, ref_sec = duration_seconds(local), duration_seconds(reference)
    except Exception as err:
        # Unreadable duration is not evidence against the local take; this
        # check exists to catch a short upload, not to gate on ffprobe.
        logger.warning("%s: could not measure coverage (%s) — keeping the "
                       "local take", who, err)
        return True
    if ref_sec <= 0:
        return True
    ratio = local_sec / ref_sec
    if ratio >= COVERAGE_MIN:
        return True
    logger.warning("%s: local take covers only %.0f%% of the leg (%.0fs of "
                   "%.0fs) — using the Voximplant leg instead",
                   who, ratio * 100, local_sec, ref_sec)
    return False


def join_offsets(run: dict) -> dict:
    """Seconds from the room opening to each leg connecting, in order.

    ``{"guest": [sec, ...], "host": [sec, ...]}``. Mira's agent is created
    with the room, so her offset is 0. These are not when a recorder
    started — Voximplant begins recording a leg seconds after it connects —
    but they say which part of the search space to believe when a leg is
    being placed on the room's clock.
    """
    import datetime as _dt

    def when(stamp):
        try:
            return _dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return None

    opened, out = None, {"guest": [], "host": []}
    for event in run.get("scenario_trace") or []:
        if not isinstance(event, dict):
            continue
        at, kind, what = when(event.get("t")), event.get("e"), str(event.get("d", ""))
        if at is None:
            continue
        if opened is None and kind == "room" and what.startswith("opened"):
            opened = at
            continue
        if opened is None or kind != "leg" or " joined" not in what:
            continue
        role = what.split()[0]
        if role in out:
            out[role].append(max(0.0, (at - opened).total_seconds()))
    return out


def build_tracks(run: dict, raw: Path, workdir: Path,
                 host_raw: Path | None = None,
                 mira_raw: Path | None = None,
                 host_legs: list | None = None) -> dict:
    """One clean 48 kHz mono WAV per speaker (Phase 2 co-host).

    Precedence per speaker:

    * guest — local browser recording (``local_guest_url`` manifest,
      complete) aligned to the Voximplant guest L channel; else that
      channel.
    * host  — local (``local_host_url``) aligned to the Voximplant host
      leg's L channel (or, when the host leg never recorded, to the
      guest's R channel, which carries the host's voice); else the host
      leg L channel; else ``None`` (→ two-track path).
    * mira  — the Voximplant Mira-only recorder (mono, or L of a stereo
      file); else the R channel of the guest recording (Mira + host mix
      in Phase 2, Mira alone before it).

    Returns ``{"guest": Path, "host": Path|None, "mira": Path,
    "sources": {speaker: "local"|"voximplant"|"guest_r"}}``.
    """
    chan_dir = workdir / "channels"
    guest_vox, guest_r = split_channels(raw, chan_dir)
    sources: dict = {}

    # The guest's leg is the clock. Everything else is expected to sit at
    # its own join time minus the guest's — Mira's agent starts with the
    # room, so when a guest joins four minutes late her leg begins four
    # minutes before the reference and has to be trimmed by that much.
    joins = join_offsets(run)
    guest_join = (joins["guest"] or [0.0])[0]

    def expected_delay(role: str, index: int = 0) -> float | None:
        if role == "mira":
            return -guest_join
        legs_at = joins.get(role) or []
        if index >= len(legs_at):
            return None
        return legs_at[index] - guest_join

    guest = None
    local_guest = fetch_local_track(run.get("local_guest_url") or "",
                                    workdir / "local_guest")
    if local_guest is not None and _covers(local_guest, guest_vox, "guest"):
        guest = align_to_reference(local_guest, guest_vox, workdir / "aligned")
        sources["guest"] = "local"
    if guest is None:
        guest, sources["guest"] = guest_vox, "voximplant"

    # A co-host who drops and rejoins has one recording per leg. Each is
    # real audio of a person talking and each belongs at the point in the
    # room where it happened, so they are placed on the room's clock by
    # measurement and laid over one another. Taking the longest (which is
    # what this did until Sept 15 2026) silently deleted Patrick from the
    # last seven minutes of the Wolfberg interview.
    legs = [l for l in (host_legs or ([host_raw] if host_raw else [])) if l]
    host_vox, host_delay, host_windows = None, 0.0, 0
    # A leg whose recorder lost time part-way through is placed in pieces;
    # the pieces are recorded so the review can see it happened.
    pieces: dict = {}
    if legs:
        placed, recorder_lag, unmeasured = [], None, []
        for i, leg in enumerate(legs):
            mono = split_left(leg, chan_dir / f"host_leg{i}.wav")
            expect = expected_delay("host", i)
            leg_pieces: list = []
            shifted, delay, windows = align_to_room(
                mono, guest_r, workdir / "room", expected=expect,
                pieces_out=leg_pieces)
            if len(leg_pieces) > 1:
                pieces.setdefault("host", []).extend(leg_pieces)
            if i == 0:
                host_delay, host_windows = delay, windows
            if windows and expect is not None and recorder_lag is None:
                # How long after this leg connected its recorder started.
                # The same machinery records every leg, so this holds for
                # the ones too short to measure for themselves.
                recorder_lag = delay - expect
                logger.info("host recorder lag measured at %+.2fs", recorder_lag)
            if not windows:
                logger.warning("host leg %d did not correlate with the room",
                               i)
                unmeasured.append((i, mono, expect))
                continue
            logger.info("host leg %d placed at %+.2fs", i, delay)
            placed.append(shifted)
        for i, mono, expect in unmeasured:
            if recorder_lag is None or expect is None:
                logger.warning("host leg %d left out — nothing to place it by", i)
                continue
            at = expect + recorder_lag
            logger.info("host leg %d placed at %+.2fs from the measured "
                        "recorder lag", i, at)
            placed.append(place_at(mono, at, workdir / "room"))
        host_vox = (mix_same_clock(placed, chan_dir / "host.wav")
                    if len(placed) > 1 else (placed[0] if placed else None))
        if host_vox is not None and len(legs) > 1:
            logger.info("host: stitched %d legs of %d", len(placed), len(legs))
    host = None
    local_host = fetch_local_track(run.get("local_host_url") or "",
                                   workdir / "local_host")
    if local_host is not None and _covers(local_host, host_vox or guest_r, "host"):
        host = align_to_reference(local_host, host_vox or guest_r,
                                  workdir / "aligned")
        sources["host"] = "local"
    if host is None and host_vox is not None:
        host, sources["host"] = host_vox, "voximplant"

    if mira_raw is not None:
        mira, sources["mira"] = split_left(mira_raw, chan_dir / "mira_leg.wav"), "voximplant"
    else:
        mira, sources["mira"] = guest_r, "guest_r"

    # Put everyone on one clock before anything is mixed or transcribed.
    # Each leg's recorder starts when Voximplant starts recording it, which
    # is neither the room opening nor the person's join: in the Dan Perra
    # interview the co-host's recording began at 17.2 s and Mira's at 16.4 s,
    # and both were laid into the mix from zero. The guest's right channel
    # is the room as the guest heard it, so it is the clock everything else
    # is measured against. The guest's own track is already on it.
    alignment: dict = {"guest": 0.0}
    unaligned: list = []
    # The host's legs were placed in the room above, so the track that came
    # out of that is already on the clock. Measuring it a second time
    # against an expectation it has already been moved by finds nothing and
    # reports a placed track as unplaced, which is exactly what the Wolfberg
    # re-run did (Sept 16 2026): Mira landed at -233.69s and the co-host,
    # correctly stitched, came back flagged. A local browser take is a
    # different file and does still need placing.
    if host is not None and sources.get("host") == "voximplant":
        alignment["host"] = round(host_delay, 2)
        if host_windows < ROOM_MIN_WINDOWS:
            unaligned.append("host")
        roles = ("mira",)
    else:
        roles = ("host", "mira")
    for role in roles:
        track = host if role == "host" else mira
        if track is None or track == guest_r:
            alignment[role] = 0.0
            continue
        expect = host_delay if role == "host" and host_windows else expected_delay(role)
        role_pieces: list = []
        shifted, delay, windows = align_to_room(track, guest_r, workdir / "room",
                                                expected=expect,
                                                pieces_out=role_pieces)
        if len(role_pieces) > 1:
            pieces[role] = role_pieces
        alignment[role] = delay
        if windows < ROOM_MIN_WINDOWS:
            unaligned.append(role)
        if role == "host":
            host = shifted
        else:
            mira = shifted

    logger.info("tracks: %s; room alignment: %s", sources,
                {k: round(v, 2) for k, v in alignment.items()})

    # Everyone is on one clock now, so each person's own microphone can be
    # relieved of what it picked up of the others. Sheldon Poon's laptop
    # heard Mira through his speakers (Sept 17 2026); left in, that is her
    # question twice in the mix and her lines in his transcript. The
    # guest's R channel carries everything the guest heard, which makes it
    # the reference for the guest's mic; the co-host's own voice is in that
    # channel too, so his mic is measured against Mira and the guest only.
    bleed: dict = {}
    if "guest" not in unaligned:
        guest, bleed["guest"] = strip_bleed(
            guest, [mira, host, guest_r],
            workdir / "bleed", "guest")
    if host is not None and "host" not in unaligned:
        host, bleed["host"] = strip_bleed(host, [mira, guest], workdir / "bleed",
                                          "host")
    return {"guest": guest, "host": host, "mira": mira, "sources": sources,
            "alignment": alignment, "unaligned": unaligned, "pieces": pieces,
            "bleed": bleed}


def has_video_stream(path: Path) -> bool:
    """True when the recording contains a video stream (WebRTC guest camera)."""
    try:
        import subprocess
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "v",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
            check=True, capture_output=True, text=True, timeout=120,
        )
        return "video" in out.stdout
    except Exception:  # noqa: BLE001 — video detection is best-effort
        return False


def room_offsets(run: dict, durations: dict | None = None) -> dict:
    """Seconds between the room opening and each track's recording starting.

    Every per-speaker recording starts when that person's leg connects, not
    when the room opened. Merging them on their own clocks puts a guest who
    joined five minutes late five minutes early in the transcript — which is
    exactly what happened to the Hogan Shrum episode (Sept 12 2026): Mira
    appeared to ask her opening question minutes after he had answered it.

    A speaker can join more than once, and then the FIRST join is the wrong
    answer. John Capobianco (Sept 14 2026) joined, dropped, and rejoined
    seven minutes later; the recording we use is the second leg, so anchoring
    it to his first join put every answer seven minutes ahead of its
    question. Pass ``durations`` — ``{"guest": seconds, ...}`` for the tracks
    actually being merged — and each role is anchored to the join whose
    time in the room best matches the recording in hand.

    Returns {"guest": sec, "host": sec, "mira": sec}; missing roles are 0.
    """
    import datetime as _dt

    def when(stamp):
        try:
            return _dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return None

    trace = run.get("scenario_trace") or []
    opened = None
    out = {"guest": 0.0, "host": 0.0, "mira": 0.0}
    # Every (role, join_offset, leave_offset) the room saw, in order.
    spans: dict[str, list[list]] = {"guest": [], "host": []}
    for event in trace:
        if not isinstance(event, dict):
            continue
        at, kind, what = when(event.get("t")), event.get("e"), str(event.get("d", ""))
        if at is None:
            continue
        if opened is None and kind == "room" and what.startswith("opened"):
            opened = at
            continue
        if opened is None:
            continue
        delta = max(0.0, (at - opened).total_seconds())
        if kind == "leg" and " joined" in what:
            role = what.split()[0]
            if role in spans:
                spans[role].append([delta, None])
        elif kind == "leg" and " left" in what:
            role = what.split()[0]
            for span in reversed(spans.get(role, [])):
                if span[1] is None:
                    span[1] = delta
                    break
        elif kind == "grok" and "bridged" in what and out["mira"] == 0.0:
            out["mira"] = delta

    room_end = max([s[1] for r in spans.values() for s in r if s[1] is not None] or [0.0])
    for role, joins in spans.items():
        if not joins:
            continue
        want = (durations or {}).get(role)
        if want:
            # The join whose time in the room looks like the file we hold.
            def _fit(span):
                left = span[1] if span[1] is not None else room_end
                return abs((left - span[0]) - want)
            best = min(joins, key=_fit)
        else:
            best = joins[0]
        out[role] = best[0]
    return out


# Whisper invents speech in silence. Each speaker's track is mostly silence —
# it is one microphone in a three-way conversation — and the model fills those
# stretches with its most common short utterances. John Capobianco's episode
# transcript carries 47 lines reading only "You" and Vincent Rylan's has "You"
# and "Thank you" every thirty seconds through passages where that person said
# nothing at all. It is cosmetic in the audio and not cosmetic at all in the
# transcript a guest is asked to approve at gate 2.
_GHOSTS = {
    "you", "thank you", "thank you.", "thanks", "bye", "bye.", "okay", "ok",
    "yeah", "mm", "mhm", "hmm", "uh", "um", "so", ".", "...", "，", "。",
    "thank you for watching", "thanks for watching", "you.", "the",
}
# A real short word is spoken; a hallucinated one is inferred from silence, and
# the model is much less sure of it. Below this the segment has to earn its
# place by being longer than a reflex.
_GHOST_LOGPROB = -0.55
_GHOST_MAX_WORDS = 3


def _is_hallucination(seg: dict, text: str) -> bool:
    words = text.split()
    if len(words) > _GHOST_MAX_WORDS:
        return False
    stripped = text.strip().strip(".,!?").lower()
    if stripped not in _GHOSTS:
        return False
    # Whisper's own uncertainty is the tell. A guest really saying "thank you"
    # scores well; the same words conjured out of room tone do not.
    logprob = seg.get("avg_logprob")
    if logprob is not None and float(logprob) > _GHOST_LOGPROB:
        return False
    no_speech = seg.get("no_speech_prob")
    if no_speech is not None and float(no_speech) > 0.5:
        return True
    return logprob is None or float(logprob) <= _GHOST_LOGPROB


# Whisper on a track that is mostly silence does not only invent "you" and
# "thank you" — it also repeats the last real thing that speaker said, at a
# steady cadence, for as long as the silence lasts. Dan Perra's transcript
# (Sept 15 2026) had Patrick saying "Hey, Dan." at 01:20, 01:50 and 02:20
# while he sat quietly listening. A phrase this short, repeated by the same
# speaker with nothing else from them in between, is the echo of the first
# one, not a person saying it again.
_ECHO_MAX_WORDS = 6
_ECHO_MIN_REPEATS = 2


def _drop_echoes(segments: list[tuple[float, str, str]],
                 ) -> list[tuple[float, str, str]]:
    """Remove a short line a speaker appears to repeat into their own
    silence. The first occurrence always survives."""
    counts: dict[tuple[str, str], int] = {}
    last_said: dict[str, str] = {}
    repeated: set[tuple[str, str]] = set()
    for _start, label, text in segments:
        key = (label, text.strip().lower())
        if len(text.split()) > _ECHO_MAX_WORDS:
            last_said[label] = key[1]
            continue
        if last_said.get(label) == key[1]:
            counts[key] = counts.get(key, 0) + 1
            if counts[key] >= _ECHO_MIN_REPEATS:
                repeated.add(key)
        else:
            counts[key] = 0
        last_said[label] = key[1]
    if not repeated:
        return segments
    kept: list[tuple[float, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for start, label, text in segments:
        key = (label, text.strip().lower())
        if key in repeated:
            if key in seen:
                continue
            seen.add(key)
        kept.append((start, label, text))
    logger.info("dropped repeated ghost line(s): %s",
                sorted({t for _l, t in repeated}))
    return kept


def diarized_tracks(tracks: list[tuple[str, Path]], workdir: Path,
                    header: str = "", offsets: dict | None = None) -> tuple[str, float]:
    """Whisper each (label, mono wav) track and merge the segments by
    start time into ``[MM:SS] <label>: text`` lines. The tracks ARE the
    diarization. ``offsets`` maps a label to the seconds between the room
    opening and that track's recording starting, so everyone lands on one
    clock. Returns (transcript, mean segment confidence 0..1)."""
    from engine.transcripts import generate_transcript
    merged: list[tuple[float, str, str]] = []
    confidences: list[float] = []
    offsets = offsets or {}
    for label, wav in tracks:
        shift = float(offsets.get(label, 0.0))
        slug = "".join(c if c.isalnum() else "_" for c in label.lower())
        result = generate_transcript(
            wav, workdir / "transcripts", f"{slug}_track",
            model_size="small", language="en",
        )
        if result is None:
            raise RuntimeError(
                f"transcription failed for the {label} track "
                "(faster-whisper unavailable or audio unreadable)"
            )
        data = json.loads(result.json_path.read_text(encoding="utf-8"))
        for seg in data.get("segments", []):
            text = (seg.get("text") or "").strip()
            if not text or _is_hallucination(seg, text):
                continue
            merged.append((float(seg.get("start", 0.0)) + shift, label, text))
            # faster-whisper avg_logprob ≈ log-confidence; map to 0..1-ish.
            if "avg_logprob" in seg:
                confidences.append(
                    max(0.0, min(1.0, 1.0 + float(seg["avg_logprob"]))))
    merged.sort(key=lambda s: s[0])
    merged = _drop_echoes(merged)
    lines = [f"[{int(s // 60):02d}:{int(s % 60):02d}] {label}: {text}"
             for s, label, text in merged]
    if header:
        lines.insert(0, header)
    mean_conf = sum(confidences) / len(confidences) if confidences else 1.0
    return "\n".join(lines), mean_conf


def diarized_transcript(raw: Path, workdir: Path) -> tuple[str, float]:
    """Per-channel Whisper transcription; the stereo channels ARE the
    diarization (guest left, Mira right — VoxEngine recorder convention).
    Returns (labeled merged transcript, mean segment confidence 0..1).
    The pre-Phase-2 two-track path — labels stay ``GUEST`` / ``MIRA``."""
    guest_wav, mira_wav = split_channels(raw, workdir / "channels")
    return diarized_tracks([("GUEST", guest_wav), ("MIRA", mira_wav)], workdir)


def _guest_label(app: dict) -> str:
    """What the transcript calls the guest: "Dr. Wolfberg" when they hold a
    doctorate, their first name otherwise (pipelines/voices/address.py)."""
    return written_address(app) or "Guest"


def speakers_header(app: dict) -> str:
    return (f"Speakers: Mira (AI host), {cohost_label()} (co-host), "
            f"{_guest_label(app)} (guest)")


def _track_durations(tracks: dict) -> dict:
    """How long each speaker's file is — the evidence room_offsets uses to
    tell which of that person's joins the file came from."""
    out = {}
    for role in ("guest", "host", "mira"):
        path = tracks.get(role)
        if not path:
            continue
        try:
            out[role] = duration_seconds(path)
        except Exception:  # noqa: BLE001
            pass
    return out


def diarized_transcript_three(tracks: dict, app: dict, workdir: Path,
                              run: dict | None = None) -> tuple[str, float]:
    """Phase 2: per-speaker tracks → ``Mira:`` / ``Patrick:`` / ``<Guest>:``
    labelled transcript with the speakers header line on top."""
    labelled = [("Mira", tracks["mira"]), (cohost_label(), tracks["host"]),
                (_guest_label(app), tracks["guest"])]
    # build_tracks has already shifted every track onto the guest leg's
    # clock by measurement, so there is nothing left to offset. Before that
    # (Sept 15 2026) this used join timestamps, which are not when a
    # recorder starts: Dan Perra's transcript had Mira reacting to things
    # he had not said yet.
    if tracks.get("alignment") is None:
        by_role = room_offsets(run or {}, _track_durations(tracks))
        offsets = {"Mira": by_role["mira"], cohost_label(): by_role["host"],
                   _guest_label(app): by_role["guest"]}
    else:
        offsets = {"Mira": 0.0, cohost_label(): 0.0, _guest_label(app): 0.0}
    return diarized_tracks(labelled, workdir, header=speakers_header(app),
                           offsets=offsets)


_ECHO_SAME_RATIO = 0.75      # how alike two lines must be to be one line twice
_ECHO_WINDOW_SEC = 8.0       # how far apart the echo can land from the original


def strip_echo_lines(transcript: str, host_label: str = "Mira") -> tuple[str, int]:
    """Take the host's own words out of everyone else's lines.

    Sept 21 2026, Sameer Ranjan. The studio records the guest's microphone
    with echo cancellation deliberately OFF, because the point of that track
    is fidelity — so a guest without headphones records Mira coming back out
    of their own speakers. The bleed gate mutes most of it, but whatever
    survives is transcribed and attributed to the guest, and his transcript
    opened with him saying "I'm the AI age of 8", "Nothing goes live" and
    "Where are you calling from?" — all of them hers.

    That is not a cosmetic problem. It is the transcript the guest reads and
    approves, the transcript published on the episode page, and the
    transcript the producer's pass reads when deciding what Mira did wrong:
    one of the lessons adopted on Sept 21 cited her own echo as evidence that
    she repeats herself.

    So any non-host line that says what the host says within a few seconds of
    her saying it is dropped as echo. Text is a far better discriminator than
    level here: two people do not independently utter the same sentence
    seconds apart, and a guest agreeing "yes" or "right" is too short to
    match. Returns the cleaned transcript and how many lines went.
    """
    import difflib

    def norm(text: str) -> str:
        return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()

    rows: list[tuple[str, str, float, str]] = []   # (raw line, speaker, sec, text)
    for line in (transcript or "").splitlines():
        m = re.match(r"^\[(\d{1,2}):(\d{2})\]\s*([^:]+):\s*(.*)$", line.strip())
        if m:
            rows.append((line, m.group(3).strip(),
                         int(m.group(1)) * 60 + int(m.group(2)), m.group(4).strip()))
        else:
            rows.append((line, "", -1.0, ""))

    host_said = [(sec, norm(text)) for _, spk, sec, text in rows
                 if spk.lower() == host_label.lower() and sec >= 0 and len(text.split()) >= 3]
    kept: list[str] = []
    dropped = 0
    for line, spk, sec, text in rows:
        if not spk or spk.lower() == host_label.lower() or sec < 0:
            kept.append(line)
            continue
        candidate = norm(text)
        # Three words is the floor: "yes", "right", "exactly" are the guest
        # agreeing, and they belong to him however often she says them too.
        if len(candidate.split()) < 3:
            kept.append(line)
            continue
        echo = False
        for when, said in host_said:
            if abs(when - sec) > _ECHO_WINDOW_SEC:
                continue
            # A whole-string ratio is the wrong measure here. The echo that
            # survives is a GARBLED FRAGMENT of a longer line of hers — "I'm
            # the AI age of 8" out of "I'm the AI who hosts The Age of AI,
            # the first podcast..." — so the question is how much of the
            # guest's line is accounted for by hers, not how alike the two
            # strings are end to end. Sum the matching blocks and divide by
            # the guest's own length.
            matcher = difflib.SequenceMatcher(None, candidate, said)
            covered = sum(b.size for b in matcher.get_matching_blocks())
            if covered / max(len(candidate), 1) >= _ECHO_SAME_RATIO:
                echo = True
                break
        if echo:
            dropped += 1
        else:
            kept.append(line)
    if dropped:
        logger.warning("transcript: dropped %d line(s) attributed to a guest that "
                       "were %s's own voice coming back through their microphone",
                       dropped, host_label)
    return "\n".join(kept), dropped


def run_editorial_passes(transcript: str, interview: dict, app: dict) -> dict:
    show = show_for(interview, app)
    package: dict = {}
    for prompt_file, field in EDITORIAL_PASSES:
        base_prompt = load_prompt(
            f"editorial_passes/{prompt_file}",
            show=show,
            guest_name=app["name"],
            guest_title=app.get("title", ""),
            guest_organization=app.get("organization", ""),
            guest_links=guest_links_markdown(app, "Their links") or "(none given)",
            episode_thesis=interview.get("episode_thesis", ""),
            transcript=transcript,
            cleaned_transcript=package.get("transcript_cleaned", transcript),
            cohost_name=cohost_name(),
        )
        output, error = None, None
        for attempt, strictness in enumerate((
            "", "\n\nSTRICT RETRY: your previous output failed validation "
                "({error}). Output ONLY the requested format, nothing else.",
        )):
            # The cleaned transcript is as long as the transcript. 6,000
            # tokens is twenty-five minutes of conversation, and every
            # episode longer than that came back cut off at the cap with
            # nobody noticing (Sept 17 2026). Budget on the input.
            budget = 6000
            if field == "transcript_cleaned":
                budget = max(6000, min(32000, len(transcript) // 2))
            text = llm(base_prompt + strictness.format(error=error),
                       temperature=0.3, max_tokens=budget)
            try:
                candidate = parse_json_lenient(text) if field in JSON_PASSES else text
                validate_pass_output(field, candidate,
                                     raw=transcript if field == "transcript_cleaned" else None)
                output = candidate
                break
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
                logger.warning("Pass %s attempt %d invalid: %s",
                               field, attempt + 1, exc)
        if output is None:
            # Spec §7: surface to Patrick for a manual editorial draft.
            notify_operator(show.slack(
                f"editorial pass {field!r} failed validation twice "
                f"— manual draft needed. Last error: {error}"), critical=True)
            output = [] if field in JSON_PASSES else ""
        package[field] = output
        logger.info("Editorial pass complete: %s", field)
    return package


def main() -> int:
    run = _run_row()
    interview, app = _interview_and_app(run)
    show = show_for(interview, app)

    if run.get("status") == "failed" or run.get("disconnect_reason", "").startswith("call_failed"):
        return handle_missed(run, interview, app)

    # Nobody came. Sept 15 2026: Erica Sell did not join, the room opened to
    # an empty chair, and this job ran anyway and died on "run has no
    # recording URL" — a red cross on the workflow list and a stack trace for
    # something that is not a fault. A no-show is a normal outcome of running
    # a show and should read like one, or a red cross stops meaning anything.
    if not _anyone_joined(run):
        logger.info("no guest ever joined run %s — recording this as a no-show",
                    run["id"])
        return handle_missed(run, interview, app)

    with tempfile.TemporaryDirectory(prefix=f"{show.slug}_post_") as tmp:
        workdir = Path(tmp)
        raw = fetch_recording(run, workdir)
        duration = duration_seconds(raw)

        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
        # WebRTC-mode recordings arrive as MP4 (guest camera video + the
        # stereo audio tracks); PSTN recordings stay MP3. Preserve the real
        # container extension and, when a video stream is present, store
        # the same artifact as recording_video_url (raw material for the
        # future YouTube version).
        ext = raw.suffix.lstrip(".") or "mp3"
        raw_url = r2_upload(raw, show.r2_key("raw", f"{run['id']}_{stamp}.{ext}"))
        # Video (WebRTC mode) is a SEPARATE recording since dry-run 2
        # showed call.record({video:true}) collapses audio to a mono mix.
        # The scenario ships its URL in the webhook; fall back to probing
        # the raw file for legacy single-recording runs.
        video_url = None
        vox_video = (run.get("grok_session_log") or {}).get("voximplant_video_url")
        if vox_video:
            try:
                vext = Path(vox_video.split("?", 1)[0]).suffix.lstrip(".").lower() or "webm"
                vfile = workdir / f"raw_video.{vext}"
                with requests.get(vox_video, stream=True, timeout=900) as vresp:
                    vresp.raise_for_status()
                    with vfile.open("wb") as fh:
                        for chunk in vresp.iter_content(1 << 16):
                            fh.write(chunk)
                video_url = r2_upload(
                    vfile, show.r2_key("raw", f"{run['id']}_{stamp}_video.{vext}"))
            except Exception:  # noqa: BLE001 — video is best-effort
                logger.exception("Video download/upload failed (non-fatal)")
        if video_url is None and has_video_stream(raw):
            video_url = raw_url

        # Phase 2 co-host: per-leg Voximplant recordings (host, Mira) +
        # local browser recordings → one clean track per speaker.
        host_legs = leg_recordings(run, "host", workdir)
        host_raw = host_legs[0] if host_legs else None
        mira_raw = fetch_leg_recording(run.get("recording_mira_url") or "",
                                       workdir, "mira")
        # Durable R2 copies of the per-leg source files (Voximplant URLs
        # expire); the run row keeps the Voximplant URLs the Worker wrote
        # (recording_host_url / recording_mira_url) — the copies and the
        # processed per-speaker WAVs are recorded in grok_session_log.tracks.
        durable: dict = {}
        for name, src in (("host", host_raw), ("mira", mira_raw)):
            if src is not None:
                durable[name] = r2_upload(src, show.r2_key(
                    "raw", f"{run['id']}_{stamp}_{name}.{src.suffix.lstrip('.')}"))

        tracks = build_tracks(run, raw, workdir, host_raw=host_raw,
                              mira_raw=mira_raw, host_legs=host_legs)
        processed: dict = {}
        if tracks["host"] is not None:
            for speaker in ("guest", "host", "mira"):
                processed[speaker] = r2_upload(
                    tracks[speaker], show.r2_key("raw", f"{run['id']}_{speaker}.wav"))
            mixed = mix_three(tracks["guest"], tracks["host"], tracks["mira"],
                              workdir / "mixed.wav")
            transcript, confidence = diarized_transcript_three(tracks, app, workdir, run)
        elif tracks["sources"].get("mira") != "guest_r":
            # No co-host, but Mira has a recording of her own — either her
            # Voximplant leg or nothing at all, and here it is her leg. That
            # plus the guest's own channel IS two per-speaker tracks, whether
            # or not the guest's browser recording arrived.
            #
            # Sept 22 2026, Viktor Popovic. This branch used to ask whether
            # the GUEST track was the local browser recording. His never
            # uploaded, so a run holding a clean guest channel and a real
            # Mira-only leg fell through to transcribing the raw stereo
            # instead — and the right channel of that stereo is the room as
            # the guest heard it, which carries the guest's own voice back.
            # The recogniser duly attributed his words to her: half her turns
            # in that transcript open with the tail of his sentence, and the
            # grading pass read it as Mira parroting her guest and adopted a
            # standing instruction about a fault that was not hers. Two good
            # tracks were on disk the whole time. What decides this path is
            # whether Mira has her own audio, not where the guest's came from.
            for speaker in ("guest", "mira"):
                processed[speaker] = r2_upload(
                    tracks[speaker], show.r2_key("raw", f"{run['id']}_{speaker}.wav"))
            mixed = mix_two(tracks["guest"], tracks["mira"], workdir / "mixed.wav")
            if tracks.get("alignment") is None:
                by_role = room_offsets(run, _track_durations(tracks))
                offsets = {_guest_label(app): by_role["guest"], "Mira": by_role["mira"]}
            else:
                # build_tracks already placed both on the guest leg's clock.
                offsets = {_guest_label(app): 0.0, "Mira": 0.0}
            transcript, confidence = diarized_tracks(
                [(_guest_label(app), tracks["guest"]), ("Mira", tracks["mira"])],
                workdir, offsets=offsets)
        else:
            # Mira was never recorded separately, so the only thing that
            # carries her is the guest's right channel — which carries the
            # guest too. The original two-track path off the raw stereo, and
            # the reason a transcript from it cannot be trusted about who
            # said what.
            logger.warning("no separate Mira recording on run %s — transcribing "
                           "the raw stereo, so speaker attribution is unreliable",
                           run["id"])
            mixed = mix_interview(raw, workdir / "mixed.wav")
            transcript, confidence = diarized_transcript(raw, workdir)
        # Whatever the bleed gate left of Mira in someone else's microphone
        # stops here, before anyone reads it as something the guest said.
        transcript, echoed_lines = strip_echo_lines(transcript, "Mira")
        mixed_url = r2_upload(mixed, show.r2_key("raw", f"{run['id']}_{stamp}_mixed.wav"))
        # A review copy both humans can actually stream. The mixed WAV is
        # ~250 MB for a 45-minute call, which is a cruel thing to put in
        # front of a guest on a phone (Sept 10 2026).
        preview_url = None
        try:
            preview = workdir / "preview.mp3"
            subprocess.run(["ffmpeg", "-y", "-i", str(mixed), "-c:a", "libmp3lame",
                            "-b:a", "96k", "-ac", "1", str(preview)],
                           check=True, capture_output=True)
            preview_url = r2_upload(preview, show.r2_key(
                "raw", f"{run['id']}_{stamp}_preview.mp3"))
        except Exception:  # noqa: BLE001 — the review pages fall back to the WAV
            logger.exception("Review preview MP3 failed (non-fatal)")
        logger.info("track sources: %s; processed: %s; durable legs: %s",
                    tracks["sources"], processed, durable)

        session_log = dict(run.get("grok_session_log") or {})
        session_log["tracks"] = {"sources": tracks["sources"],
                                 "processed": processed, "durable": durable,
                                 "preview": preview_url,
                                 "alignment": tracks.get("alignment") or {},
                                 "unaligned": tracks.get("unaligned") or [],
                                 "pieces": tracks.get("pieces") or {},
                                 "bleed": tracks.get("bleed") or {}}
        sb_update("interview_runs", f"id=eq.{run['id']}", {
            "status": "completed",
            "recording_guest_url": raw_url,
            "recording_mixed_url": mixed_url,
            "recording_video_url": video_url,
            "duration_sec": int(duration),
            "grok_session_log": session_log,
        })
        sb_update("interviews", f"id=eq.{interview['id']}",
                  {"status": "editorial_review"})

        package = run_editorial_passes(transcript, interview, app)

        flags = []
        if duration < SHORT_CALL_THRESHOLD_SEC:
            flags.append("short_call")
        if confidence < LOW_STT_CONFIDENCE:
            flags.append("low_stt_confidence")
        # A track we could not place on the room's clock means the mix may
        # have people talking over each other in the wrong order. Patrick
        # should be told that before he spends an hour listening, not after.
        if tracks.get("unaligned"):
            flags.append("unaligned:" + "+".join(tracks["unaligned"]))
            notify_operator(show.slack(
                "could not line up " + ", ".join(tracks["unaligned"])
                + f" with the room for {app['name']} — the mix may be out of "
                  "sync and needs an ear before it goes to the guest"),
                critical=True)

        pkg = sb_insert("editorial_packages", {
            "interview_id": interview["id"],
            "interview_run_id": run["id"],
            "transcript_raw": transcript,
            "transcript_cleaned": package["transcript_cleaned"],
            "chapter_markers": package["chapter_markers"],
            "episode_notes": package["episode_notes"],
            "social_copy": package["social_copy"],
            "clip_suggestions": package["clip_suggestions"],
            "cross_show_callouts": package["cross_show_callouts"],
            "newsletter_draft": package["newsletter_draft"],
            "status": "in_review",
            "guest_review_token": new_review_token(),
            "audio_quality_flag": ",".join(flags) or None,
        })

        # Learning loop: measure the craft, grade the hour, and change how she
        # works. Sept 21 2026: the grade is APPLIED rather than proposed —
        # eight proposals had been waiting for a human while the same faults
        # recurred. The grader sees what she already carries and is told not
        # to restate it, and every adoption is reversible from triage.
        try:
            metrics = measure(run, package.get("transcript_cleaned") or transcript,
                              host_label="Mira", guest_label=_guest_label(app))
            save_metrics(interview["id"], metrics)
            logger.info("episode metrics: %s", metrics)
            cleaned = package.get("transcript_cleaned") or transcript
            graded = parse_json_lenient(llm(load_prompt(
                "editorial_passes/09_interview_retro.txt",
                show=show, show_name=show.name,
                guest_name=app["name"],
                session_events=session_events_summary(run),
                active_lessons=lessons_for_prompt(show.slug),
                guest_feedback=guest_feedback(cleaned, _guest_label(app))
                or "(she was not asked, or the answer is not in the tape)",
                metrics=json.dumps({k: v for k, v in metrics.items()
                                    if k != "notes"}, ensure_ascii=False),
                cleaned_transcript=cleaned,
            ), temperature=0.3, max_tokens=2500)) or {}
            if not isinstance(graded, dict):
                graded = {}
            retired = retire_lessons(
                [r.get("id") for r in (graded.get("retire") or [])
                 if isinstance(r, dict)],
                "retired by the grading pass")
            adopted = adopt_lessons(show.slug, interview["id"],
                                    graded.get("lessons") or [])
            save_grade(show.slug, interview["id"], graded, adopted, retired)
            logger.info("graded %s: overall %s — %d lesson(s) adopted, %d retired",
                        app["name"], (graded.get("grades") or {}).get("overall"),
                        len(adopted), retired)
            # Retire the acknowledgment reflexes she leaned on this time.
            tics = host_formulas(
                parse_transcript(package.get("transcript_cleaned") or transcript),
                "Mira")
            logger.info("retiring %d host phrase(s): %s",
                        save_host_phrases(show.slug, interview["id"], tics), tics)
        except Exception:  # noqa: BLE001 — an episode never waits on this
            logger.exception("Retrospective failed (non-fatal)")

        if package.get("topical_show_fits"):
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"topical_show_fits": package["topical_show_fits"]})

    flag_note = f" ⚠️ {', '.join(flags)}" if flags else ""
    # Sept 10 2026: this link used to go out without a token, so it 401'd
    # until Patrick pasted the admin token by hand — and it went to Slack
    # only, so a quiet Slack meant no signal at all that a package was
    # waiting. Now it is a real link, by email as well as Slack.
    try:
        review_url = f"{REVIEW_BASE}/{pkg['id']}/{package_review_token(pkg['id'])}"
    except Exception:  # noqa: BLE001 — never lose the notification over this
        logger.exception("Review token unavailable; sending the bare link")
        review_url = f"{REVIEW_BASE}/{pkg['id']}"
    notify_operator(show.slack(
        f"{app['name']} interview processed "
        f"({int(duration // 60)} min).{flag_note} "
        f"Review (gate 1): {review_url}"
    ))
    try:
        send_email(
            OPERATOR_EMAIL,
            f"{show.short_label}: {app['name']} is ready for your review",
            f"<p>Hi Patrick,</p>"
            f"<p>The interview with <strong>{app['name']}</strong> "
            f"({int(duration // 60)} minutes) is processed and waiting at gate 1."
            f"{' <strong>Flagged: ' + ', '.join(flags) + '.</strong>' if flags else ''}"
            f" The page has the audio, the episode notes, the cleaned transcript "
            f"and the newsletter draft, with Approve and Kill on the bottom:</p>"
            f'<p><a href="{review_url}">Review this episode</a></p>'
            f"<p>Nothing reaches the guest until you approve here.</p>"
            f"<p>— Mira</p>")
    except Exception:  # noqa: BLE001 — Slack already carries the link
        logger.exception("Gate 1 email failed (non-fatal)")
    logger.info("Editorial package %s ready for Patrick", pkg["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
