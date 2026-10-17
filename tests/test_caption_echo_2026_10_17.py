"""Whisper's suffix echo never reaches captions (Oct 17 2026).

Oct 13 dropped the exact echo ("Texas. Texas."). Whisper also writes the
TAIL of a word again ("Friday. day.", "timeline line", "reports. ports.").
engine.transcripts.drop_echo_words now drops that too, below
SUFFIX_ECHO_MAX_PROBABILITY, calibrated against each episode's script.
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.transcripts import SUFFIX_ECHO_MAX_PROBABILITY, drop_echo_words  # noqa: E402


def _seg(*words):
    out, t = [], 0.0
    for w, p in words:
        out.append({"word": w, "start": t, "end": t + 0.3, "probability": p})
        t += 0.3
    return [{"text": " ".join(w for w, _ in words), "words": out}]


def test_suffix_echo_is_dropped():
    segs, n = drop_echo_words(_seg(("on", 0.9), ("Friday.", 0.95), ("day.", 0.007), ("The", 0.9)))
    assert n == 1
    assert [w["word"] for w in segs[0]["words"]] == ["on", "Friday.", "The"]
    assert "day." not in segs[0]["text"].split()


def test_a_confident_suffix_word_is_kept():
    # "this is" — a real bigram whose second word ends the first.
    segs, n = drop_echo_words(_seg(("this", 0.95), ("is", 0.94)))
    assert n == 0


def test_a_single_letter_tail_is_never_an_echo():
    segs, n = drop_echo_words(_seg(("data", 0.9), ("a", 0.01)))
    assert n == 0


def test_threshold():
    assert SUFFIX_ECHO_MAX_PROBABILITY == 0.25


def test_replay_drops_only_words_the_script_never_said():
    """Every suffix echo dropped from the committed October transcripts is
    checked against the episode script: almost none may be a real bigram."""
    def norm(t):
        return re.findall(r"[a-z0-9']+", t.lower())
    dropped = real = 0
    for f in sorted(glob.glob(str(ROOT / "digests" / "*" / "*_202610*_transcript.json")))[:400]:
        tts = Path(f.replace("_transcript.json", "_tts.txt"))
        if not tts.exists():
            continue
        data = json.loads(Path(f).read_text(encoding="utf-8"))
        segs = data.get("segments") if isinstance(data, dict) else data
        if not segs:
            continue
        script = " " + " ".join(norm(tts.read_text(encoding="utf-8"))) + " "
        before = [w for s in segs for w in (s.get("words") or [])]
        after, _ = drop_echo_words(segs)
        kept_ids = {(w.get("start"), w.get("word")) for s in after for w in (s.get("words") or [])}
        for i, w in enumerate(before):
            if i and (w.get("start"), w.get("word")) not in kept_ids:
                prev = re.sub(r"[^\w']", "", str(before[i - 1].get("word", ""))).lower()
                cur = re.sub(r"[^\w']", "", str(w.get("word", ""))).lower()
                if prev != cur:
                    dropped += 1
                    real += f" {prev} {cur} " in script
    if dropped:
        assert real <= max(1, dropped // 20), (real, dropped)
