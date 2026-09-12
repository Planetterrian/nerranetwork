"""Voice a hand-written narration pickup in Mira's own voice.

Why this is not just text-to-speech (Sept 11 2026): the interview is the
Speech-to-Speech voice agent, and xAI's TTS endpoint is a different engine.
Asking both for the same voice still gives a listener two different people,
which defeats the point of a show hosted by one. So Mira reads her own
introductions and closes, through the same agent that hosts the interview.

    pipelines/voices/narration/<slug>.json
      { "show": "age_of_ai",
        "voice": "ara",                       # optional; lowercase xAI voice id
        "segments": [ {"id": "intro", "text": "..."}, ... ] }

Each segment is split into paragraphs and each paragraph is one Voximplant
session — a session with no call is torn down after 60 seconds, and a
two-minute introduction does not fit inside that. The scenario reports each
recording to the Worker; this stitches the paragraphs back together with a
short breath between them and uploads one MP3 per segment to
<r2_prefix>/narration/<slug>/<id>.mp3.

Set NARRATION_ENGINE=tts to fall back to the text-to-speech path (useful only
when the voice agent is unavailable; it will not match the interview).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import requests  # noqa: E402

from common import logger, r2_upload, sb_insert, sb_select  # noqa: E402
from shows import get_show  # noqa: E402

NARRATION_DIR = Path(__file__).parent / "narration"
TAKE_TIMEOUT_SEC = 180
POLL_SEC = 5
BREATH_SEC = 0.45          # between paragraphs, so it reads as one take
SILENCE_DB = -45           # below this is silence, not speech
KEEP_SILENCE_SEC = 0.35    # a natural pause inside a paragraph
PARAGRAPH_MAX_CHARS = 420  # a paragraph must be SAID inside a 60 s session
SHORT_TAKE_RATIO = 0.6     # a take this far under its script was cut off
MIN_CHECKABLE_WORDS = 14   # below this, pace varies too much to judge
MIN_TAKE_SEC = 0.4         # ... so all a short line must prove is that it exists
WORDS_PER_SEC = 2.4        # Mira's measured pace, for the truncation check


def paragraphs(text: str) -> List[str]:
    """Split on blank lines, then split anything too long on sentences."""
    out: List[str] = []
    for block in [b.strip() for b in (text or "").split("\n\n") if b.strip()]:
        if len(block) <= PARAGRAPH_MAX_CHARS:
            out.append(block)
            continue
        current = ""
        for sentence in block.replace("\n", " ").split(". "):
            piece = sentence if sentence.endswith(".") else sentence + "."
            if current and len(current) + len(piece) + 1 > PARAGRAPH_MAX_CHARS:
                out.append(current.strip())
                current = piece
            else:
                current = f"{current} {piece}".strip()
        if current.strip():
            out.append(current.strip())
    return out


def _record_take(slug: str, segment_id: str, seq: int, text: str, voice: str) -> str:
    from voximplant.api_clients.voximplant_client import start_narration_take

    take_id = f"{slug}-{segment_id}-{seq}-{uuid.uuid4().hex[:8]}"
    sb_insert("narration_takes", {"slug": slug, "segment_id": segment_id,
                                  "seq": seq, "take_id": take_id})
    start_narration_take(take_id, text, voice=voice)
    deadline = time.time() + TAKE_TIMEOUT_SEC
    while time.time() < deadline:
        time.sleep(POLL_SEC)
        rows = sb_select("narration_takes", f"take_id=eq.{take_id}")
        row = rows[0] if rows else {}
        if row.get("status") == "ok" and row.get("record_url"):
            logger.info("take %s/%s#%d recorded", slug, segment_id, seq)
            return row["record_url"]
        if row.get("status") == "failed":
            raise RuntimeError(f"take {take_id} failed: {row.get('detail')}")
    raise RuntimeError(f"take {take_id} never reported within {TAKE_TIMEOUT_SEC}s")


def _trim(part: Path) -> Path:
    """Strip the dead air off a take.

    The scenario records for as long as the paragraph *should* take to say,
    because the agent's ResponseDone fires before it has finished speaking.
    When Mira finishes early the rest of that window is silence, and stitching
    the takes raw left four to ten second holes between paragraphs (Sept 12
    2026). Trim both ends and shorten anything long in the middle, so the
    breath between paragraphs is the one this module adds, not an artefact of
    how long the recorder happened to run.
    """
    out = part.with_name(part.stem + "_trim.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(part), "-af",
         f"silenceremove=start_periods=1:start_threshold={SILENCE_DB}dB:"
         f"start_silence={KEEP_SILENCE_SEC}:detection=rms,"
         f"silenceremove=stop_periods=-1:stop_duration={KEEP_SILENCE_SEC}:"
         f"stop_threshold={SILENCE_DB}dB:detection=rms",
         "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(out)],
        check=True)
    return out


def _duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def _check_not_truncated(part: Path, text: str) -> None:
    """A take that is far shorter than its script was cut off mid-sentence.

    Sept 11 2026: ResponseDone fires while Mira is still speaking, so every
    take came back after roughly its first sentence and the episode shipped a
    mangled introduction. Shipping a silently truncated read is worse than
    failing, so this fails.
    """
    words = len(text.split())
    actual = _duration(part)
    # A short line is said at whatever pace it wants: "That is where we will
    # leave it" is seven words in 1.7 seconds, which tripped this check on its
    # first real outing (Sept 12 2026). Below MIN_CHECKABLE_WORDS the estimate
    # means nothing, so all such a take has to prove is that it is not empty.
    if words < MIN_CHECKABLE_WORDS:
        if actual < MIN_TAKE_SEC:
            raise RuntimeError(
                f"take is empty: {actual:.1f}s of audio for {text[:60]!r}")
        return
    expected = words / WORDS_PER_SEC
    if actual < expected * SHORT_TAKE_RATIO:
        raise RuntimeError(
            f"take was cut off: {actual:.1f}s of audio for {words} words "
            f"(expected about {expected:.0f}s) — {text[:60]!r}")


def _stitch(parts: List[Path], out_mp3: Path) -> Path:
    """Concatenate the paragraph takes with a short breath between them."""
    work = out_mp3.parent
    silence = work / "breath.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", str(BREATH_SEC),
                    "-i", "anullsrc=r=48000:cl=mono", "-c:a", "pcm_s16le", str(silence)],
                   check=True)
    inputs: List[str] = []
    filt: List[str] = []
    idx = 0
    for i, part in enumerate(parts):
        if i:
            inputs += ["-i", str(silence)]
            filt.append(f"[{idx}:a]")
            idx += 1
        inputs += ["-i", str(part)]
        filt.append(f"[{idx}:a]")
        idx += 1
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex",
         "".join(filt) + f"concat=n={idx}:v=0:a=1,"
         "highpass=f=60,dynaudnorm=f=250:g=15,loudnorm=I=-16:TP=-1.5:LRA=11[out]",
         "-map", "[out]", "-ac", "1", "-ar", "48000",
         "-c:a", "libmp3lame", "-b:a", "128k", str(out_mp3)],
        check=True)
    return out_mp3


def narrate(slug: str) -> Dict[str, str]:
    spec_path = NARRATION_DIR / f"{slug}.json"
    if not spec_path.exists():
        raise SystemExit(f"no narration spec at {spec_path}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    show = get_show(spec.get("show"))
    segments = spec.get("segments") or []
    if not segments:
        raise SystemExit("spec has no segments")
    voice = str(spec.get("voice") or os.environ.get("MIRA_VOICE_PRESET")
                or "ara").strip().lower()

    if os.environ.get("NARRATION_ENGINE", "agent").lower() == "tts":
        logger.warning("NARRATION_ENGINE=tts — this will NOT match the "
                       "interview voice; use it only if the agent is down")
        return _narrate_with_tts(spec, show, slug, voice)

    out: Dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for seg in segments:
            seg_id, text = seg["id"], (seg.get("text") or "").strip()
            if not text:
                logger.warning("segment %s is empty — skipped", seg_id)
                continue
            parts: List[Path] = []
            for seq, para in enumerate(paragraphs(text)):
                url = _record_take(slug, seg_id, seq, para, voice)
                part = work / f"{seg_id}_{seq:03d}.mp3"
                part.write_bytes(requests.get(url, timeout=180).content)
                trimmed = _trim(part)
                # Checked AFTER trimming: trailing silence would otherwise
                # make a cut-off read look like a complete one.
                _check_not_truncated(trimmed, para)
                parts.append(trimmed)
            if not parts:
                continue
            mp3 = _stitch(parts, work / f"{seg_id}.mp3")
            out[seg_id] = r2_upload(mp3, show.r2_key("narration", slug, f"{seg_id}.mp3"))
            logger.info("narration %s -> %s (%d takes)", seg_id, out[seg_id], len(parts))
    return out


def _narrate_with_tts(spec: dict, show, slug: str, voice: str) -> Dict[str, str]:
    from audio.generate_narration import synthesize_segments

    os.environ["MIRA_VOICE_PRESET"] = voice
    out: Dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for seg_id, mp3 in synthesize_segments(spec["segments"], Path(tmp)).items():
            out[seg_id] = r2_upload(mp3, show.r2_key("narration", slug, f"{seg_id}.mp3"))
    return out


if __name__ == "__main__":
    slug = os.environ.get("NARRATION_SLUG") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not slug:
        raise SystemExit("NARRATION_SLUG (or argv[1]) required")
    for seg_id, url in narrate(slug).items():
        print(f"{seg_id}\t{url}")
