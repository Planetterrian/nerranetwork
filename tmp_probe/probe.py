"""Temporary: pause measurement on the new Gary cut."""
import subprocess, urllib.request
import numpy as np
url = "https://audio.nerranetwork.com/nerra_voices/raw/88ed9ad7-33cf-4179-b8be-3e14345f154e_edit_20261127154652.mp3"
req = urllib.request.Request(url, headers={"User-Agent": "nerra-probe"})
with urllib.request.urlopen(req) as r, open("/tmp/e.mp3", "wb") as f:
    f.write(r.read())
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", "/tmp/e.mp3", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                     check=True, capture_output=True).stdout
x = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
hop = 320
n = len(x) // hop
db = 20 * np.log10(np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1)) / 32768 + 1e-9)
print("duration", len(x) / 16000)
for thr in (-40, -35, -30):
    q = db < thr
    runs, i = [], 0
    while i < n:
        if q[i]:
            j = i
            while j < n and q[j]:
                j += 1
            runs.append((i * 0.02, (j - i) * 0.02))
            i = j
        else:
            i += 1
    long = [r for r in runs if r[1] > 0.8]
    print(f"thr {thr}: runs>0.6s {sum(r[1]>0.6 for r in runs)}, >0.8s {len(long)}, >1.2s {sum(r[1]>1.2 for r in runs)}")
    print("   ", [(round(a, 1), round(d, 2)) for a, d in long][:80])
print("noise floor pct", np.percentile(db, [5, 10, 20, 30]))
