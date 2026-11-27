"""Temporary: word-timed Whisper over windows of audio files (Gary recut)."""
import numpy as np
import json, subprocess, sys, urllib.request
from pathlib import Path
from faster_whisper import WhisperModel

cfg = json.loads(Path("tmp_probe/probe.json").read_text())
model = WhisperModel(cfg.get("model", "small.en"), device="cpu", compute_type="int8")
for item in cfg["files"]:
    src = Path("/tmp") / item["name"]
    if not src.exists():
        req = urllib.request.Request(item["url"], headers={"User-Agent": "nerra-probe"})
        with urllib.request.urlopen(req) as r, open(src, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
    for a, b in item["windows"]:
        clip = Path(f"/tmp/clip_{item['name']}_{a}.wav")
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-to", str(b), "-i", str(src),
                              "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], check=True,
                             capture_output=True).stdout
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        segs, _ = model.transcribe(audio, word_timestamps=True, vad_filter=False,
                                   condition_on_previous_text=False)
        print(f"\n=== {item['name']} {a}-{b}")
        for s in segs:
            print("  " + " ".join(f"{w.word.strip()}@{a + w.start:.2f}-{a + w.end:.2f}" for w in s.words))
        sys.stdout.flush()
