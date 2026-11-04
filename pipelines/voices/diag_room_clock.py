"""TEMPORARY diagnostic: how Mira's own recording sits against the room,
window by window, for one interview run. Prints a delay curve and the
session events from the trace in track seconds. Read-only."""
import sys
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audio.local_tracks import _whole_envelope, _window_offset, ROOM_ENVELOPE_SR  # noqa: E402
from common import sb_select  # noqa: E402
import subprocess  # noqa: E402


def dl(url, dest):
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for c in r.iter_content(1 << 16):
                fh.write(c)
    return dest


def chan(src, idx, out):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af",
                    f"pan=mono|c0=c{idx}", "-ar", "48000", str(out)], check=True)
    return out


def curve(name, track, room, base, win_s=40, step_s=10, span=60):
    print(f"\n=== {name}: windows of {win_s}s every {step_s}s, around {base:+.2f}s")
    e_t = _whole_envelope(track, W)
    e_r = _whole_envelope(room, W)
    cut = int(round(-base * ROOM_ENVELOPE_SR))
    e_t = e_t[cut:] if cut > 0 else np.concatenate([np.zeros(-cut, np.float32), e_t])
    win, step = int(win_s * ROOM_ENVELOPE_SR), int(step_s * ROOM_ENVELOPE_SR)
    n = min(len(e_t), len(e_r))
    for st in range(0, n - win, step):
        lag, s = _window_offset(e_t[st:st + win], e_r[st:st + win], -span, span)
        if lag is None:
            continue
        mark = "*" if s >= 0.45 else " "
        print(f"room {st / ROOM_ENVELOPE_SR:7.0f}s  track {st / ROOM_ENVELOPE_SR - base:7.0f}s"
              f"  delay {base - lag:+7.2f}  corr {s:.2f} {mark}")


run_id = sys.argv[1]
W = Path("diag")
W.mkdir(exist_ok=True)
run = sb_select("interview_runs", f"id=eq.{run_id}&select=*")[0]
log = run.get("grok_session_log") or {}
tracks = log.get("tracks") or {}
raw = dl(run["recording_guest_url"], W / "raw.mp3")
mira_url = (tracks.get("durable") or {}).get("mira") or run.get("recording_mira_url")
mira = dl(mira_url, W / "mira_raw.mp3")
for p in (raw, mira):
    print(p, subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration:stream=channels,sample_rate", "-of", "compact",
                             str(p)], capture_output=True, text=True).stdout)
gl = chan(raw, 0, W / "guest_L.wav")
gr = chan(raw, 1, W / "guest_R.wav")
ml = chan(mira, 0, W / "mira_L.wav")
base = float((tracks.get("alignment") or {}).get("mira") or 0.0)
print("trace (room-open seconds):")
import datetime as dt  # noqa: E402
t0 = None
for ev in run.get("scenario_trace") or []:
    t = dt.datetime.fromisoformat(ev["t"].replace("Z", "+00:00"))
    t0 = t0 or t
    if ev["e"] in ("grok", "leg", "room") and any(k in ev["d"] for k in (
            "hand", "bridged", "dropped", "rescued", "joined", "left", "closed", "opened")):
        print(f"  {(t - t0).total_seconds():7.1f}s  {ev['e']}: {ev['d'][:90]}")
u = (tracks.get("processed") or {}).get("mira")
if u:
    dl(u, W / "proc_mira.wav")

# --- the fix, on the real tapes ---
import logging  # noqa: E402
logging.basicConfig(level=logging.INFO, format="%(message)s")
for name in ("audio.local_tracks",):
    logging.getLogger(name).setLevel(logging.INFO)
logging.getLogger("audio.local_tracks").addFilter(lambda r: "ffmpeg:" not in r.getMessage())
import post_interview as pi  # noqa: E402
from audio.local_tracks import align_by_sessions, clock_residuals  # noqa: E402
joins = pi.join_offsets(run)
gj = (joins["guest"] or [0.0])[0]
changes = [c - gj for c in pi.mira_session_changes(run)]
print("\n=== FIX: session changes (guest clock):", changes)
pieces: list = []
res = align_by_sessions(ml, gr, W / "fix", changes, expected=-gj, fill_gaps=True, pieces_out=pieces)
print("FIX pieces:", pieces)
print("FIX result:", res)
if res:
    curve("FIX placed mira vs guest R", res[0], gr, 0.0, win_s=30, step_s=15, span=90)
old = (tracks.get("processed") or {}).get("mira")
if old:
    print("OLD processed mira short-window residuals:",
          clock_residuals(W / "proc_mira.wav", gr, W / "oldcheck")[:20])
