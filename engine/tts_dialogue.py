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
import statistics
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

    # Name-voice congruence guard (July 20 2026, Ep016): the LLM rotated
    # the supplied closing's speaker labels to dodge a same-host boundary
    # (the turn before the closing and the closing's first line were both
    # DAN's), so Dan's VOICE said "I'm Patrick Novak" and Patrick's said
    # "I'm Dan Perra" on air. A self-introduction is unambiguous: a turn
    # saying "I'm <OtherHost>" belongs to that host — relabel it.
    turns = _fix_self_introduction_labels(turns, known)

    # Merge consecutive same-speaker turns into one synthesis group.
    groups: List[Tuple[str, str]] = []
    for speaker, text in turns:
        if groups and groups[-1][0] == speaker:
            groups[-1] = (speaker, groups[-1][1] + "\n\n" + text)
        else:
            groups.append((speaker, text))
    return groups


def _fix_self_introduction_labels(
    turns: List[Tuple[str, str]],
    known: set,
) -> List[Tuple[str, str]]:
    """Relabel turns whose self-introduction names the OTHER configured host.

    Speaker labels double as first names on the network's dialogue shows
    (DAN → "Dan", PATRICK → "Patrick"), so "I'm Dan…" spoken under a
    PATRICK: label is a wrong-voice defect, never intent. Only unambiguous
    single-host self-intros are touched; a turn matching several hosts'
    names (a joint intro) is left alone with a warning.
    """
    intro_res = {
        label: re.compile(rf"\bI(?:'|’)?m {label.capitalize()}\b")
        for label in known
    }
    fixed: List[Tuple[str, str]] = []
    for speaker, text in turns:
        claimed = [lbl for lbl, rx in intro_res.items() if rx.search(text)]
        if len(claimed) == 1 and claimed[0] != speaker:
            logger.warning(
                "Dialogue label fix: %r self-introduces as %s — relabeling "
                "the turn so the right voice says its own name "
                "(text: %.60r)", speaker, claimed[0], text,
            )
            speaker = claimed[0]
        elif len(claimed) > 1:
            logger.warning(
                "Dialogue label check: turn names multiple hosts (%s) — "
                "leaving label %r unchanged", claimed, speaker,
            )
        fixed.append((speaker, text))
    return fixed


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


# --- Inter-turn loudness matching (July 2026, Ep001 v5 operator listen) ---
# Dialogue mode makes one Grok TTS call per speaker group (30-40 per episode)
# and per-call output loudness varies — the shipped episode drifted between a
# good level and audibly quiet turns. The downstream normalize_voice() chain
# can't fix this: its loudnorm runs with linear=true (ONE gain for the whole
# file) and the 4:1 compressor only acts above threshold, so quiet turns stay
# quiet. Single-voice shows never hit this because the whole script is one
# TTS call. Fix: measure each turn WAV's mean level and gain-match everything
# to the MEDIAN before the crossfade — median (not a fixed absolute) so a
# uniformly loud/quiet session is untouched and only outlier turns move.
# mean_volume via volumedetect is stable on short clips where loudnorm's
# integrated measurement is not (many turns are one sentence, ~2-4 s).

_MAX_TURN_GAIN_DB = 12.0   # never boost/cut a turn more than this
_MIN_TURN_GAIN_DB = 1.0    # leave sub-1 dB drift alone (inaudible)


def _measure_mean_volume_db(wav_path: Path) -> Optional[float]:
    """Return ffmpeg volumedetect ``mean_volume`` in dB, or None on failure."""
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", str(wav_path), "-af", "volumedetect",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=120,
        )
        m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", proc.stderr)
        return float(m.group(1)) if m else None
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def _match_turn_levels(wav_files: List[Path]) -> Tuple[List[Path], int]:
    """Gain-match *wav_files* to their median mean level, in place per file.

    Returns ``(paths, n_adjusted)`` — paths in the same order, with adjusted
    turns replaced by ``*_lvl.wav`` siblings. Any measurement/ffmpeg failure
    leaves that file untouched (never blocks synthesis).
    """
    if len(wav_files) < 2:
        return wav_files, 0
    levels = {p: _measure_mean_volume_db(p) for p in wav_files}
    valid = [v for v in levels.values() if v is not None]
    if len(valid) < 2:
        logger.warning(
            "Dialogue level match: could not measure enough turns "
            "(%d/%d) — skipping", len(valid), len(wav_files),
        )
        return wav_files, 0
    target = statistics.median(valid)
    out: List[Path] = []
    n_adjusted = 0
    max_move = 0.0
    for p in wav_files:
        v = levels[p]
        gain = 0.0 if v is None else max(
            -_MAX_TURN_GAIN_DB, min(_MAX_TURN_GAIN_DB, target - v),
        )
        if abs(gain) < _MIN_TURN_GAIN_DB:
            out.append(p)
            continue
        leveled = p.with_name(p.stem + "_lvl.wav")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(p),
                 "-af", f"volume={gain:.2f}dB", str(leveled)],
                check=True, capture_output=True, timeout=300,
            )
        except (subprocess.SubprocessError, OSError):
            logger.warning(
                "Dialogue level match: gain failed on %s — using raw", p.name,
            )
            out.append(p)
            continue
        out.append(leveled)
        n_adjusted += 1
        max_move = max(max_move, abs(gain))
    logger.info(
        "Dialogue level match: median %.1f dB, adjusted %d/%d turn file(s)"
        "%s", target, n_adjusted, len(wav_files),
        f" (largest move {max_move:.1f} dB)" if n_adjusted else "",
    )
    return out, n_adjusted


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
    speed: float = 1.0,
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

    try:
        # Pass 1: synthesise every group (per-group WAV lists, no padding yet).
        group_wav_lists: List[List[Path]] = []
        for g_idx, (speaker, text) in enumerate(groups):
            chunks = chunk_text(text, max_chars=effective_max)
            group_wavs: List[Path] = []
            for c_idx, chunk in enumerate(chunks):
                wav = tmp_dir / f"turn_{g_idx:03d}_{speaker}_{c_idx:02d}.wav"
                grok_speak_chunk(
                    chunk, voices[speaker], wav,
                    api_key=api_key, language_code=language_code,
                    timeout=timeout, speed=speed,
                )
                group_wavs.append(wav)
            group_wav_lists.append(group_wavs)
            logger.info(
                "Dialogue TTS: group %d/%d (%s, %d chars, %d chunk%s)",
                g_idx + 1, len(groups), speaker, len(text),
                len(chunks), "" if len(chunks) == 1 else "s",
            )

        # Pass 2: gain-match every turn file to the median level BEFORE the
        # silence padding (padding would skew the mean-level measurement).
        flat = [w for gw in group_wav_lists for w in gw]
        leveled, _n_adjusted = _match_turn_levels(flat)
        it = iter(leveled)
        group_wav_lists = [[next(it) for _ in gw] for gw in group_wav_lists]

        # Pass 3: let each handoff breathe — pad the group's final chunk
        # with silence (skip after the last group; the music outro follows).
        wav_files: List[Path] = []
        for g_idx, group_wavs in enumerate(group_wav_lists):
            if pause_ms > 0 and g_idx < len(group_wav_lists) - 1:
                group_wavs[-1] = _pad_wav_tail(group_wavs[-1], pause_ms)
            wav_files.extend(group_wavs)

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
