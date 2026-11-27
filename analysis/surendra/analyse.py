"""Temporary analysis for the Surendra Goel hand re-cut (Nov 27 2026).

Word-timed transcript and voice activity for one track, so EDL boundaries
can be placed on real silences. Not part of the pipeline; deleted with the
branch."""
import json, subprocess, sys
from pathlib import Path
import numpy as np

name, url, out_dir = sys.argv[1], sys.argv[2], Path(sys.argv[3])
src = Path(f"/tmp/{name}.bin")
subprocess.run(["curl", "-sSfL", "-o", str(src), url], check=True)
raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(src), "-f",
                      "s16le", "-ac", "1", "-ar", "16000", "-"],
                     capture_output=True, check=True).stdout
x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
dur = len(x) / 16000
hop = 160
n = len(x) // hop
db = 20 * np.log10(np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1)) + 1e-9)
# voiced runs relative to this track's own speech level
speech = np.percentile(db[db > -70], 90) if np.any(db > -70) else -30
thr = max(-55.0, speech - 22)
loud = db > thr
runs, i = [], 0
while i < n:
    if loud[i]:
        j = i
        while j < n and loud[j]:
            j += 1
        runs.append([i * 0.01, j * 0.01])
        i = j
    else:
        i += 1
merged = []
for a, b in runs:
    if merged and a - merged[-1][1] < 0.25:
        merged[-1][1] = b
    else:
        merged.append([a, b])
merged = [[round(a, 2), round(b, 2)] for a, b in merged if b - a >= 0.08]

from faster_whisper import WhisperModel
model = WhisperModel("small.en", device="cpu", compute_type="int8")
segs, _ = model.transcribe(x, language="en", beam_size=1, word_timestamps=True,
                           vad_filter=False, condition_on_previous_text=False)
words = []
for s in segs:
    for w in s.words or []:
        words.append([round(w.start, 2), round(w.end, 2), w.word.strip(),
                      round(w.probability, 2)])
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / f"{name}.json").write_text(json.dumps(
    {"url": url, "duration": round(dur, 2), "threshold_db": round(float(thr), 1),
     "speech_db": round(float(speech), 1), "voiced": merged, "words": words}))
print(name, dur, len(words), "words", len(merged), "voiced runs")
