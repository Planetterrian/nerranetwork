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

Nov 1 2026: the dubbed hook Shorts (@NerraRU ``engine.ru_dub``, @NerraFR
``engine.lang_dub``) skip the translated map the same way (see "Dub hook
Shorts" below): the translation keeps the English script's lines one for
one, so the dub's map is the dub line at the English map's position, found
in the dub's own Whisper words by its letters.
"""

from __future__ import annotations

import copy
import logging
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

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


# ---------------------------------------------------------------------------
# Dub hook Shorts (Nov 1 2026)
# ---------------------------------------------------------------------------
#
# The @NerraRU and @NerraFR hook Shorts are clips of the dub track's opening,
# which carries the translated map. The English tests cannot find it there:
# ``is_map_line``'s cues are English words, and ``story_breaks._norm`` folds
# accents to ASCII and so drops every Cyrillic letter. Two facts make the dub
# map findable without a language model:
#
# - the translation keeps the English script's lines one for one (every
#   committed RU/FR script of Oct 20-Nov 1 has its English script's line
#   count), so the dub's map is the dub line at the English map's index:
#   ``map_line_range`` on the English ``_tts.txt`` says where;
# - the dub's own Whisper words carry the timing. Each edge line is found by
#   its letters (Cyrillic transliterated, accents folded, digits dropped
#   because Whisper writes "144" where the script spells the number), then
#   the whole span between the two edges must read as the map's text.
#
# Every test is a refusal, never a guess: no English map, a line count that
# differs, an edge Whisper did not hear, or a span that does not read as the
# map returns ``None`` and the Short renders from the dub track as before.

#: Cyrillic to Latin, close enough for letter matching (both sides use it).
_CYR_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "і": "i", "ї": "i", "є": "e", "ґ": "g",
}
#: Words of a line's opening compared with the dub transcript.
DUB_PROBE_WORDS = 8
#: An edge counts as found at this similarity of letters (Whisper misspells
#: names: "Сванденберга", "Valèse-Marineris"). Measured on the 99 mapped
#: RU/FR openings of Oct 20-Nov 1: every found edge 0.64-1.00; the two
#: openings where Whisper wrote no words over the map (a 17-18 s hole while
#: the audio speaks) best 0.45 (M&A Ep220 FR) and 0.31 (SpaceX Ep148 RU).
DUB_EDGE_MIN_RATIO = 0.6
#: The words between the two edges must read as the map's own text at this
#: similarity (every found span measured 0.88-1.00).
DUB_SPAN_MIN_RATIO = 0.75
#: A probe shorter than this many letters matches anywhere.
DUB_PROBE_MIN_CHARS = 12
#: The edge snaps to a sentence start within this many words of the best
#: letter match (Whisper splits "650 -1." and runs "au programme" on).
_DUB_SNAP_WORDS = 2
_SENTENCE_END_RE = re.compile(r"[.!?…][\"'»”)\]]*$")
#: How far past the map's start the next line may begin (the longest dub map
#: measured ran 18.5 s).
_DUB_NEXT_LINE_MAX_S = CUT_MAX_S + 5.0


def dub_norm(word: str) -> str:
    """Letters of *word* for matching a dub script against its Whisper words.

    Accents fold, Cyrillic transliterates, digits and punctuation drop: the
    scripts spell numbers out and Whisper writes digits, in both languages.
    """
    s = unicodedata.normalize("NFKD", str(word or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = "".join(_CYR_LATIN.get(c, c) for c in s)
    return re.sub(r"[^a-z]", "", s)


def dub_map_line_range(english_script: str, dub_script: str) -> Optional[Tuple[int, int]]:
    """``(first, after)`` of the map in the dub's ``script_lines``, or ``None``.

    The English map's position (:func:`map_line_range`), carried over only
    when the dub keeps the English script's lines one for one.
    """
    from engine import story_breaks as sb

    rng = map_line_range(english_script)
    if rng is None:
        return None
    en = sb.script_lines(english_script)
    dub = sb.script_lines(dub_script)
    if len(en) != len(dub) or rng[1] >= len(dub):
        return None
    return rng


def _dub_words(transcript: dict) -> List[Tuple[str, float, float, str]]:
    out: List[Tuple[str, float, float, str]] = []
    for seg in (transcript or {}).get("segments") or []:
        for w in seg.get("words") or []:
            raw = str(w.get("word", ""))
            out.append((dub_norm(raw), float(w.get("start", 0.0)),
                        float(w.get("end", 0.0)), raw))
    return out


def _dub_locate(line: str, words: Sequence[Tuple[str, float, float, str]],
                lo: int, max_start: float) -> Optional[int]:
    """Index of the transcript word where *line* starts, searched from *lo*
    among words starting no later than *max_start*; ``None`` when no
    position's letters are close enough."""
    toks = [t for t in (dub_norm(x) for x in (line or "").split()) if t]
    target = "".join(toks[:DUB_PROBE_WORDS])
    if len(target) < DUB_PROBE_MIN_CHARS:
        return None
    scored: List[Tuple[float, int]] = []
    for h in range(max(1, lo), len(words)):
        if words[h][1] > max_start:
            break
        if not words[h][0]:
            continue
        stream = ""
        k = h
        while len(stream) < len(target) and k < len(words):
            stream += words[k][0]
            k += 1
        ratio = SequenceMatcher(None, target, stream[:len(target)], autojunk=False).ratio()
        scored.append((round(ratio, 4), h))
    if not scored:
        return None
    # Equal letters, first letter decides: with the digits dropped, "эпизод
    # [140,] полет …" scores the same from "эпизод" as from "полет" (SpaceX
    # Ep140 RU), and a line is said as written from its first letter.
    best_ratio, _fl, neg_h = max(
        (round(r, 2), words[h][0][:1] == target[:1], -h) for r, h in scored)
    best_h = -neg_h
    if best_ratio < DUB_EDGE_MIN_RATIO:
        return None
    # A line starts a sentence: prefer the nearest position after a sentence
    # end whose letters score almost as well. A position may be a number
    # Whisper wrote as digits ("15 -й полёт" for "Пятнадцатый полёт", "5
    # -летняя" for "Пятилетнее"): it has no letters, so it scores as the
    # first word with letters after it. Without this SpaceX Ep137 RU cut at
    # the map's last word and kept "разбор" in the Short.
    ratio_at = {h: r for r, h in scored}
    near: List[Tuple[int, int]] = []
    for j in range(max(1, lo, best_h - _DUB_SNAP_WORDS),
                   min(len(words), best_h + _DUB_SNAP_WORDS + 1)):
        if not _SENTENCE_END_RE.search(words[j - 1][3].strip()):
            continue
        k = j
        while k < len(words) and k - j < _DUB_SNAP_WORDS and not words[k][0]:
            k += 1          # a number in digits: no letters, score what follows
        r = ratio_at.get(k)
        if r is not None and r >= best_ratio - 0.1:
            near.append((abs(j - best_h), j))
    if near:
        return min(near)[1]
    return best_h


def dub_map_cut(english_script: str, dub_script: str,
                transcript: dict) -> Optional[Tuple[float, float]]:
    """``(cut_from, cut_to)`` of the map on the dub track, or ``None``.

    Same edges as :func:`map_cut`: the midpoint of the pause before the map
    and of the pause before the first story.
    """
    try:
        from engine import story_breaks as sb

        rng = dub_map_line_range(english_script, dub_script)
        if rng is None:
            return None
        first, after = rng
        lines = sb.script_lines(dub_script)
        words = _dub_words(transcript)
        if len(words) < 3:
            return None
        ha = _dub_locate(lines[first], words, 1, MAP_START_MAX_S)
        if ha is None:
            return None
        hb = _dub_locate(lines[after], words, ha + 1, words[ha][1] + _DUB_NEXT_LINE_MAX_S)
        if hb is None or hb <= ha:
            return None
        target = "".join(dub_norm(x) for x in " ".join(lines[first:after]).split())
        heard = "".join(w[0] for w in words[ha:hb])
        if SequenceMatcher(None, target, heard, autojunk=False).ratio() < DUB_SPAN_MIN_RATIO:
            return None
        cut_from = (words[ha - 1][2] + words[ha][1]) / 2.0
        cut_to = (words[hb - 1][2] + words[hb][1]) / 2.0
        if words[ha][1] > MAP_START_MAX_S or not (CUT_MIN_S <= cut_to - cut_from <= CUT_MAX_S):
            return None
        return round(cut_from, 3), round(cut_to, 3)
    except Exception as exc:  # noqa: BLE001 — never block a render
        logger.warning("Dub Short map cut skipped: %s", exc)
        return None


#: An edge moves into the track's own silence when one sits this close
#: (``story_breaks.ANCHOR_WINDOW``: Whisper's word times abut across real
#: pauses — SpaceX Ep143 RU's map ends on "разбор" at 29.98 s by Whisper and
#: at 30.11 s in the audio).
DUB_SILENCE_WINDOW_S = 0.6


def snap_cut_to_silence(cut: Tuple[float, float],
                        silences: Sequence[Tuple[float, float]],
                        *, window: float = DUB_SILENCE_WINDOW_S) -> Tuple[float, float]:
    """Each edge of *cut* moved to the middle of the silence it sits in, or
    of the nearest silence within *window* seconds; an edge with no silence
    near it stays where it is."""
    def _snap(t: float) -> float:
        best = None
        for s0, s1 in silences:
            dist = 0.0 if s0 <= t <= s1 else min(abs(t - s0), abs(t - s1))
            if dist > window:
                continue
            if best is None or dist < best[0]:
                best = (dist, (s0 + s1) / 2.0)
        return t if best is None else best[1]

    a, b = _snap(float(cut[0])), _snap(float(cut[1]))
    if not (CUT_MIN_S <= b - a <= CUT_MAX_S):
        return cut
    return round(a, 3), round(b, 3)


def _opening_silences(audio: Path, until_s: float) -> List[Tuple[float, float]]:
    """Silences in the first *until_s* seconds of *audio* (ffmpeg
    silencedetect, the story-break thresholds)."""
    import subprocess

    from engine import story_breaks as sb

    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-t", f"{until_s:.1f}", "-i", str(audio),
         "-af", f"silencedetect=noise={sb.SILENCE_NOISE_DB}dB:d={sb.SILENCE_MIN_SECONDS}",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=120)
    return sb.parse_silencedetect(proc.stderr)


def dub_scripts_for(output_dir: Path, episode_num: int,
                    lang: str) -> Optional[Tuple[Path, Path]]:
    """``(english_tts, dub_script)`` the multilingual sweep committed for an
    episode (``<stem>_tts.txt`` and ``<stem>.<lang>.txt``), or ``None``."""
    try:
        for dub in sorted(Path(output_dir).glob(f"*_Ep{int(episode_num):03d}_*.{lang}.txt")):
            stem = dub.name[: -len(f".{lang}.txt")]
            tts = dub.with_name(stem + "_tts.txt")
            if tts.exists():
                return tts, dub
    except Exception:  # noqa: BLE001
        return None
    return None


def spliced_dub_short_source(dub_audio: Path, transcript_path: Path,
                             output_dir: Path, episode_num: int, lang: str,
                             work_dir: Path):
    """``(audio, transcript_json, cut_seconds)`` for a dub hook Short, or
    ``None`` when the episode has no map to remove or anything fails.

    The dub track is voice only (no music bed), so the cut is made on the
    track at the transcript's own times. *output_dir* is the show's digest
    directory, which holds the English and translated scripts.
    """
    try:
        import json
        import subprocess

        from engine.utils import strip_speech_tags

        scripts = dub_scripts_for(Path(output_dir), episode_num, lang)
        if scripts is None:
            return None
        tts_path, dub_path = scripts
        transcript = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
        cut = dub_map_cut(strip_speech_tags(tts_path.read_text(encoding="utf-8")),
                          strip_speech_tags(dub_path.read_text(encoding="utf-8")),
                          transcript)
        if cut is None:
            return None
        try:
            cut = snap_cut_to_silence(
                cut, _opening_silences(Path(dub_audio), cut[1] + DUB_SILENCE_WINDOW_S + 2.0))
        except Exception as exc:  # noqa: BLE001 — the Whisper edges stand
            logger.info("Dub Short map cut: no silence read (%s); Whisper edges kept", exc)
        cut_from, cut_to = cut
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        audio = work_dir / f"{lang}_ep{int(episode_num):03d}_short_source.flac"
        tx = work_dir / f"{lang}_ep{int(episode_num):03d}_short_source.json"
        subprocess.run(splice_audio_cmd(Path(dub_audio), audio, cut_from, cut_to),
                       check=True, timeout=300, capture_output=True)
        tx.write_text(json.dumps(splice_transcript(transcript, cut_from, cut_to),
                                 ensure_ascii=False), encoding="utf-8")
        return audio, tx, round(cut_to - cut_from, 2)
    except Exception as exc:  # noqa: BLE001 — never block a render
        logger.warning("Dub Short map splice skipped (the Short keeps the map): %s", exc)
        return None


def dub_short_source(yt, short_idx: int, window_label: str, audio: Path,
                     tr_json: Optional[Path], dub_words: list, output_dir: Path,
                     episode_num: int, lang: str, work_dir: Path, result: dict):
    """``(audio, transcript, words)`` a dub Short is cut from.

    The dub sibling of ``run_show._short_source``: the hook Short (Short #1,
    ``hook_open``) renders from the dub track with the translated map spliced
    out when ``youtube.shorts_skip_map`` is on; every other Short, and any
    failure, renders from the dub track itself. Records ``shorts_map_cut_s``
    on *result*. Never raises.
    """
    source = (audio, tr_json, dub_words)
    try:
        if not (short_idx == 0 and window_label == "hook_open"
                and tr_json is not None
                and bool(getattr(yt, "shorts_skip_map", False))):
            return source
        spliced = spliced_dub_short_source(audio, Path(tr_json), output_dir,
                                           episode_num, lang, work_dir)
        if spliced is None:
            return source
        s_audio, s_tx, cut_s = spliced
        words: list = []
        try:
            from engine.visual_reuse import load_transcript_words
            words = load_transcript_words(s_tx)
        except Exception:  # noqa: BLE001 — the Short ends on the grid
            words = []
        result["shorts_map_cut_s"] = cut_s
        logger.info("%s hook Short: the map (%.1f s) is cut from the clip", lang, cut_s)
        return s_audio, s_tx, words
    except Exception as exc:  # noqa: BLE001 — never block a render
        logger.warning("Dub Short map splice skipped (the Short keeps the map): %s", exc)
        return source
