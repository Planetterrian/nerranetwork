"""Find the places where Mira talked over a guest who was still answering.

Sept 25 2026, Chad Law. Twice in his episode Mira spoke into the middle of an
answer — "That's the moment the jersey stopped feeling like enough" at 3:09,
"Go on" at 37:57 — and he carried straight on underneath her. Patrick's note:
that is an interruption and it should not be in the episode. With one voice
per track it does not have to be: her track can be turned off for those two
seconds while his plays on.

What counts, measured on the processed, room-aligned tracks:

* Mira starts while the guest has spoken in the last 0.7 s,
* the guest is audible for at least 0.3 s WHILE she is talking,
* she stops within three seconds (a real question runs longer), and
* the guest is still talking within a second of her stopping — his turn
  went on, so hers was an interjection rather than the next question.

The last two are what keep a genuine question safe. Mira restarting her own
question over a guest's one-word "Yes" is not an interruption: the guest
stops, and she is asking.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Tuple

import numpy as np

HOP_SEC = 0.02
RECENT_SEC = 0.7
MIN_OVERLAP_SEC = 0.3
MAX_BURST_SEC = 3.0
CONTINUES_SEC = 1.0
PAD_SEC = 0.3   # the switch is instant, so land it in her silence


def _activity(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "8000",
         "-f", "f32le", "-"], capture_output=True, check=True, timeout=1800).stdout
    x = np.frombuffer(raw, dtype=np.float32)
    hop = int(8000 * HOP_SEC)
    n = len(x) // hop
    if n == 0:
        return np.zeros(0, dtype=bool)
    db = 20 * np.log10(np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1)) + 1e-9)
    on = db > np.percentile(db, 97) - 28.0
    # Close sub-300 ms gaps (between words), then drop sub-100 ms blips.
    k = int(0.3 / HOP_SEC)
    on = np.convolve(on.astype(float), np.ones(k), "same") > 0
    on = np.convolve(on.astype(float), np.ones(k), "same") >= k
    return on


def interruptions(guest: Path, mira: Path) -> List[Tuple[float, float]]:
    """``[(from_sec, to_sec)]`` on the tracks' shared clock where Mira's voice
    should be muted because she talked over a guest who kept going."""
    g, m = _activity(guest), _activity(mira)
    n = min(len(g), len(m))
    g, m = g[:n], m[:n]
    out: List[Tuple[float, float]] = []
    onsets = np.where(np.diff(m.astype(int)) == 1)[0] + 1
    for o in onsets:
        k = o
        while k < n and m[k]:
            k += 1
        burst = (k - o) * HOP_SEC
        if burst > MAX_BURST_SEC:
            continue
        if not g[max(0, o - int(RECENT_SEC / HOP_SEC)):o].any():
            continue
        if g[o:k].sum() * HOP_SEC < MIN_OVERLAP_SEC:
            continue
        if not g[k:k + int(CONTINUES_SEC / HOP_SEC)].any():
            continue
        out.append((float(round(max(0.0, o * HOP_SEC - PAD_SEC), 2)),
                    float(round(k * HOP_SEC + PAD_SEC, 2))))
    return out
