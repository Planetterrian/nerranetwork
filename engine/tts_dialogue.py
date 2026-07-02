"""Two-host dialogue TTS (July 2026, The DP Pod).

Synthesises a speaker-labeled podcast script with a distinct Grok voice per
speaker. The script format is one turn per paragraph, uppercase labels::

    DAN: Welcome to The DP Pod — the Do Positive Podcast. I'm Dan Perra.
    PATRICK: And I'm Patrick Novak. Great to be here.

Pipeline (mirrors ``engine.tts._speak_with_grok``): consecutive same-speaker
turns are merged into groups, each group is chunked and sent to Grok TTS with
that speaker's voice (WAV 48 kHz), each group tail gets a short silence pad so
handoffs breathe, and the whole sequence is crossfaded losslessly and encoded
to MP3 exactly once via ``engine.tts._crossfade_wavs_to_mp3``.

Dialogue mode NEVER applies ``speech_wrap_*``: per-call wraps across every
speaker handoff are exactly the chunk-boundary leak shape that shipped
"Fast." spoken aloud (M&A Ep045, landmine #17) — the wrap parameters are not
even accepted here, so the leak is structurally impossible.

Speaker-label handling is defensive because grok-4.3's label discipline is
imperfect:

* Unlabeled paragraphs continue the previous speaker's turn (this also
  absorbs ``_break_long_paragraphs`` splits in ``run_show.py``).
* Text before the first label is attributed to the first labeled speaker.
* Generic non-speaker prefixes (``HOST:``, ``NARRATOR:``, ``SPEAKER:``) are
  stripped with a warning and the text continues the current turn.
* A script with ZERO recognised labels parses to ``[]`` — the caller falls
  back to single-voice ``engine.tts.synthesize`` so the episode ships.
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

from engine.tts import (
    GROK_MAX_CHARS_PER_REQUEST,
    GROK_TTS_TIMEOUT_SECONDS,
    _crossfade_wavs_to_mp3,
    chunk_text,
    grok_speak_chunk,
    prepare_text_for_tts,
)

logger = logging.getLogger(__name__)

# One word, optionally **bold**, followed by an ASCII or fullwidth colon at
# the start of a paragraph. Whether it *switches speakers* depends on the
# show's dialogue_voices keys — an arbitrary "Note:" line is content, not a
# speaker (see parse_dialogue_turns).
_LABEL_RE = re.compile(
    r"^\s*(?:\*\*)?([A-Za-zА-Яа-яЁё][\w'\-]*)(?:\*\*)?\s*[:：]\s*"
)

# Prefixes the single-host pipeline strips as scaffolding. In dialogue mode
# they are still not real speakers — strip the label, keep the words, warn.
_GENERIC_SPEAKER_LABELS = {"HOST", "NARRATOR", "SPEAKER", "ВЕДУЩАЯ", "ВЕДУЩИЙ"}


def parse_dialogue_turns(
    script: str,
    voices: Dict[str, str],
) -> List[Tuple[str, str]]:
    """Parse *script* into merged ``(speaker, text)`` turn-groups.

    *voices* maps uppercase speaker labels to Grok voice IDs; only those
    labels switch speakers. Returns ``[]`` when no recognised label appears
    anywhere (callers should fall back to single-voice synthesis).
    """
    known = {k.upper() for k in voices}
    turns: List[Tuple[str, str]] = []  # (speaker, paragraph) before merging
    preamble: List[str] = []  # unlabeled paragraphs before the first label
    current_speaker: str | None = None

    for raw_line in script.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _LABEL_RE.match(line)
        label = m.group(1).upper() if m else None
        if label in known:
            current_speaker = label
            body = line[m.end():].strip()
            if body:
                turns.append((current_speaker, body))
            continue
        if label in _GENERIC_SPEAKER_LABELS:
            logger.warning(
                "Dialogue parse: generic label %r is not a configured "
                "speaker (%s) — stripping the label and continuing the "
                "current turn", m.group(0).strip(), sorted(known),
            )
            line = line[m.end():].strip()
            if not line:
                continue
        # Unlabeled (or de-labeled) paragraph: continuation.
        if current_speaker is None:
            preamble.append(line)
        else:
            turns.append((current_speaker, line))

    if not turns:
        return []

    if preamble:
        # Leading unlabeled text belongs to the first labeled speaker.
        first_speaker, first_body = turns[0]
        turns[0] = (first_speaker, "\n\n".join(preamble + [first_body]))

    # Merge consecutive same-speaker turns into one synthesis group.
    groups: List[Tuple[str, str]] = []
    for speaker, text in turns:
        if groups and groups[-1][0] == speaker:
            groups[-1] = (speaker, groups[-1][1] + "\n\n" + text)
        else:
            groups.append((speaker, text))
    return groups


def dialogue_stats(script: str, voices: Dict[str, str]) -> Dict[str, int]:
    """Per-episode label-discipline metrics for the dashboard/review agent."""
    known = {k.upper() for k in voices}
    labeled = 0
    unlabeled = 0
    for raw_line in script.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _LABEL_RE.match(line)
        if m and m.group(1).upper() in known:
            labeled += 1
        else:
            unlabeled += 1
    return {
        "dialogue_labeled_paragraphs": labeled,
        "dialogue_unlabeled_paragraphs": unlabeled,
        "dialogue_turn_count": len(parse_dialogue_turns(script, voices)),
    }


def _pad_wav_tail(wav_path: Path, pause_ms: int) -> Path:
    """Append *pause_ms* of silence to *wav_path* (ffmpeg ``apad``)."""
    padded = wav_path.with_name(wav_path.stem + "_pad.wav")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(wav_path),
            "-af", f"apad=pad_dur={pause_ms / 1000:.3f}",
            str(padded),
        ],
        check=True, capture_output=True, timeout=300,
    )
    return padded


def synthesize_dialogue(
    script: str,
    voices: Dict[str, str],
    output_path: str | Path,
    *,
    api_key: str,
    max_chars: int = GROK_MAX_CHARS_PER_REQUEST,
    language_code: str = "en",
    pause_ms: int = 300,
    timeout: int = GROK_TTS_TIMEOUT_SECONDS,
) -> Path:
    """Synthesise a speaker-labeled *script* into a single MP3 at *output_path*.

    Raises ``ValueError`` when *voices* is unusable or the script has no
    recognised speaker labels — callers decide the fallback (run_show falls
    back to single-voice synthesis with a loud warning + metric).
    """
    if not voices:
        raise ValueError("synthesize_dialogue: dialogue_voices is empty")
    bad = {k: v for k, v in voices.items()
           if not v or not str(v).strip() or "REPLACE" in str(v).upper()}
    if bad:
        raise ValueError(
            f"synthesize_dialogue: unusable voice ID(s) for {sorted(bad)} — "
            "set real Grok voice IDs in tts.dialogue_voices before running",
        )
    voices = {k.upper(): str(v).strip() for k, v in voices.items()}

    script = prepare_text_for_tts(script)
    groups = parse_dialogue_turns(script, voices)
    if not groups:
        raise ValueError(
            "synthesize_dialogue: no recognised speaker labels "
            f"({sorted(voices)}) anywhere in the script — caller should "
            "fall back to single-voice synthesis",
        )

    output_path = Path(output_path)
    effective_max = min(max_chars, GROK_MAX_CHARS_PER_REQUEST)
    tmp_dir = Path(tempfile.mkdtemp(prefix="tts_dialogue_", dir=str(output_path.parent)))

    wav_files: List[Path] = []
    try:
        for g_idx, (speaker, text) in enumerate(groups):
            chunks = chunk_text(text, max_chars=effective_max)
            group_wavs: List[Path] = []
            for c_idx, chunk in enumerate(chunks):
                wav = tmp_dir / f"turn_{g_idx:03d}_{speaker}_{c_idx:02d}.wav"
                grok_speak_chunk(
                    chunk, voices[speaker], wav,
                    api_key=api_key, language_code=language_code,
                    timeout=timeout,
                )
                group_wavs.append(wav)
            # Let the handoff breathe: pad the group's final chunk with
            # silence (skip after the last group — the music outro follows).
            if pause_ms > 0 and g_idx < len(groups) - 1:
                group_wavs[-1] = _pad_wav_tail(group_wavs[-1], pause_ms)
            wav_files.extend(group_wavs)
            logger.info(
                "Dialogue TTS: group %d/%d (%s, %d chars, %d chunk%s)",
                g_idx + 1, len(groups), speaker, len(text),
                len(chunks), "" if len(chunks) == 1 else "s",
            )

        _crossfade_wavs_to_mp3(wav_files, output_path, tmp_dir)
        logger.info(
            "Dialogue TTS: %d speaker groups → %s (single MP3 encode)",
            len(groups), output_path,
        )
    finally:
        for leftover in tmp_dir.glob("*.wav"):
            try:
                leftover.unlink()
            except OSError:
                pass
        try:
            tmp_dir.rmdir()
        except OSError:
            pass
    return output_path
