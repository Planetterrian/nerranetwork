"""The hook Short skips the episode's map (Oct 30 2026).

Since Oct 20 every English episode opens: hook, identity line ("This is
<Show>, episode N."), then THE MAP — one sentence listing the stories that
follow ("Intel's new process node, Japan's self-driving filing, ... then
first principles"). The hook Short is a clip of the episode's opening
(``engine.shorts_selector.hook_first_windows``), so from Oct 20 the Short
told its hook, named the show, then read a list of OTHER stories before it
got back to the one it opened on. Measured at age 5 days on every Short
published Oct 5-29 (stored snapshots): average view duration EN 16.0 ->
13.5 s, FR 16 -> 13, RU 19 -> 17; average view percentage EN 46.5 -> 41.7.

This module finds the map in the committed script, locates it in the
Whisper words, and splices it out of the Short's SOURCE (the final mix and
a matching transcript), so captions, fact cards, sentence-snapped cuts and
the clip all read one consistent timeline. The episode itself, its feed
audio and its long-form video are untouched: this is a render of the
Short, not a change to what the episode says.

Nothing here raises into a render: every failure returns ``None`` and the
Short renders from the unspliced source, exactly as before.
"""

from __future__ import annotations

import copy
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

#: The map must start this early in the episode to be the opening's map.
MAP_START_MAX_S = 30.0
#: A cut shorter than this is not worth a splice; longer is not a map.
CUT_MIN_S = 1.0
CUT_MAX_S = 20.0
#: Fade on each side of the splice (the music bed runs under the voice).
SPLICE_FADE_S = 0.03

#: A short follow-on line that finishes the map ("Then first principles.").
_TAIL_RE = re.compile(r"^\W*(?:then|and then|plus|and)\b", re.IGNORECASE)
_TAIL_MAX_WORDS = 8
#: A map is one sentence; a longer line is a story.
MAP_MAX_WORDS = 45
_ATTRIBUTION_RE = re.compile(
    r"\b(?:according to|reports?|reported|said|says|told|announced|wrote)\b",
    re.IGNORECASE)


def is_map_line(line: str) -> bool:
    """A sentence that lists what comes next.

    ``engine.chapters._looks_like_map``'s test (a sequencing word — "then",
    "follow", "come next", "from there" — and a list comma) without its
    no-digit rule, because a map names models ("Telesat books Falcon 9s",
    "new M6 Macs"); and never a line that attributes a fact or opens as a
    continuation. Measured: 136 of the 173 maps in the Oct 20-30 scripts,
    and 0 of the 368 lines in the same place in the Oct 1-19 scripts,
    written before maps existed (one, "... says ...", is excluded by the
    attribution rule).
    """
    from engine import story_breaks as sb
    from engine.chapters import _MAP_CUE_RE

    text = (line or "").strip()
    if not text or len(text.split()) > MAP_MAX_WORDS or text.count(",") < 1:
        return False
    if _ATTRIBUTION_RE.search(text) or sb.opens_as_continuation(text):
        return False
    return bool(_MAP_CUE_RE.search(text))


def map_line_range(script: str) -> Optional[Tuple[int, int]]:
    """``(first, after)`` line indices of the map in ``script_lines``.

    The map is the line right after the identity line when it reads as a
    list of what comes next (:func:`is_map_line`), plus any short "Then ..."
    line that finishes it. ``None`` for a script without
    one (every episode before Oct 20, and any that wrote its lead there).
    """
    from engine import story_breaks as sb

    lines = sb.script_lines(script)
    ident = next((i for i, ln in enumerate(lines[:sb.IDENTITY_SEARCH_LINES])
                  if sb._IDENTITY_RE.search(ln)), None)
    if ident is None or ident + 2 >= len(lines):
        return None
    first = ident + 1
    if not is_map_line(lines[first]):
        return None
    after = first + 1
    while after < len(lines) - 1:
        nxt = lines[after]
        if is_map_line(nxt) or (
                _TAIL_RE.search(nxt) and len(nxt.split()) <= _TAIL_MAX_WORDS
                and not re.search(r"\d", nxt)):
            after += 1
            continue
        break
    return first, after


def map_cut(script: str, transcript: dict) -> Optional[Tuple[float, float]]:
    """``(cut_from, cut_to)`` on the voice timeline, or ``None``.

    Each edge is the midpoint of the pause before a line: the pause before
    the map and the pause before the first story, so the splice keeps one
    natural sentence gap.
    """
    try:
        from engine import story_breaks as sb

        rng = map_line_range(script)
        if rng is None:
            return None
        first, after = rng
        anchors, unmatched = sb.boundary_anchors(script, [first], transcript)
        if unmatched or len(anchors) != 1:
            return None
        prev_a, start_a = anchors[0]
        end = _line_start_after(script, transcript, first, after, start_a)
        if end is None:
            return None
        prev_b, start_b = end
        cut_from = (prev_a + start_a) / 2.0
        cut_to = (prev_b + start_b) / 2.0
        if start_a > MAP_START_MAX_S or not (CUT_MIN_S <= cut_to - cut_from <= CUT_MAX_S):
            return None
        return round(cut_from, 3), round(cut_to, 3)
    except Exception as exc:  # noqa: BLE001 — never block a render
        logger.warning("Short map cut skipped: %s", exc)
        return None


def _line_start_after(script, transcript, first, after, map_start):
    """``(prev_word_end, start)`` of the line after the map.

    Its own opening when the matcher finds it; otherwise the first word
    after the map's last sentence end in the Whisper words (one sentence
    end per map line), because a story can open on a name Whisper spells
    its own way ("CNews") while the map's full stop is still there.
    """
    from engine import story_breaks as sb

    lines = sb.script_lines(script)
    anchors, unmatched = sb.boundary_anchors(script, [first, after], transcript)
    if not unmatched and len(anchors) == 2:
        return anchors[1]
    words = [w for seg in transcript.get("segments") or [] for w in seg.get("words") or []]
    need = after - first
    for i, w in enumerate(words):
        if float(w.get("start", 0.0)) < map_start - 0.01:
            continue
        if str(w.get("word", "")).strip().endswith((".", "!", "?")):
            need -= 1
            if need == 0:
                if i + 1 >= len(words):
                    return None
                return float(w.get("end", 0.0)), float(words[i + 1].get("start", 0.0))
    return None


def splice_transcript(transcript: dict, cut_from: float, cut_to: float) -> dict:
    """The transcript with ``[cut_from, cut_to)`` removed and later times
    moved earlier by the cut, words and segments alike."""
    gap = cut_to - cut_from

    def _t(x: float) -> float:
        return x - gap if x >= cut_to else x

    out = copy.deepcopy(transcript)
    segments: List[dict] = []
    for seg in out.get("segments") or []:
        words = seg.get("words") or []
        kept = [w for w in words
                if not (cut_from <= float(w.get("start", 0.0)) < cut_to)]
        if words and not kept:
            continue
        if not words:
            s, e = float(seg.get("start", 0.0)), float(seg.get("end", 0.0))
            if cut_from <= s < cut_to:
                continue
            seg["start"], seg["end"] = _t(s), _t(e)
            segments.append(seg)
            continue
        for w in kept:
            w["start"] = round(_t(float(w.get("start", 0.0))), 3)
            w["end"] = round(_t(float(w.get("end", 0.0))), 3)
        seg["words"] = kept
        seg["start"] = kept[0]["start"]
        seg["end"] = kept[-1]["end"]
        if len(kept) != len(words):
            seg["text"] = "".join(str(w.get("word", "")) for w in kept)
        segments.append(seg)
    out["segments"] = segments
    return out


def splice_audio_cmd(src: Path, dst: Path, cut_from: float, cut_to: float,
                     *, fade: float = SPLICE_FADE_S) -> List[str]:
    """ffmpeg command: *src* without ``[cut_from, cut_to)``, short fades at
    the join, lossless out (the Short render encodes once)."""
    a_end = max(0.0, cut_from)
    graph = (
        f"[0:a]atrim=0:{a_end:.3f},asetpts=PTS-STARTPTS,"
        f"afade=t=out:st={max(0.0, a_end - fade):.3f}:d={fade:.3f}[a];"
        f"[0:a]atrim=start={cut_to:.3f},asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d={fade:.3f}[b];"
        f"[a][b]concat=n=2:v=0:a=1[out]"
    )
    return ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
            "-filter_complex", graph, "-map", "[out]", "-c:a", "flac", str(dst)]


def script_for_transcript(transcript_path: Path) -> Optional[Path]:
    """The committed spoken script beside a ``*_transcript.json``."""
    name = transcript_path.name
    if not name.endswith("_transcript.json"):
        return None
    path = transcript_path.with_name(name[: -len("_transcript.json")] + "_tts.txt")
    return path if path.exists() else None


def spliced_short_source(final_mp3: Path, transcript_path: Path, work_dir: Path,
                         *, audio_offset: float = 0.0):
    """``(audio, transcript_json, cut_seconds)`` for the hook Short, or
    ``None`` when the episode has no map to remove or anything fails.

    *audio_offset* is where the voice sits in the mix (``voice_intro_delay``):
    the cut is made on the mix at the voice time plus it, and the spliced
    transcript stays on the voice timeline like the original.
    """
    try:
        import json
        import subprocess

        from engine.utils import strip_speech_tags

        script_path = script_for_transcript(Path(transcript_path))
        if script_path is None:
            return None
        transcript = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
        script = strip_speech_tags(script_path.read_text(encoding="utf-8"))
        cut = map_cut(script, transcript)
        if cut is None:
            return None
        cut_from, cut_to = cut
        work_dir.mkdir(parents=True, exist_ok=True)
        audio = work_dir / (final_mp3.stem + "_short_source.flac")
        tx = work_dir / (Path(transcript_path).stem + "_short_source.json")
        subprocess.run(
            splice_audio_cmd(final_mp3, audio, cut_from + audio_offset, cut_to + audio_offset),
            check=True, timeout=300, capture_output=True)
        tx.write_text(json.dumps(splice_transcript(transcript, cut_from, cut_to)),
                      encoding="utf-8")
        return audio, tx, round(cut_to - cut_from, 2)
    except Exception as exc:  # noqa: BLE001 — never block a render
        logger.warning("Short map splice skipped (the Short keeps the map): %s", exc)
        return None
