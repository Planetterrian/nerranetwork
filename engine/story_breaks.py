"""A beat of silence between stories (Oct 13 2026, operator-directed).

Listening note: on the news shows one story ran straight into the next.
SpaceX Ep128 went from Indian pricing to a Crew Dragon splashdown to Grok in
Cybercab with the same ~0.55 s gap Grok TTS leaves after every sentence —
measured over four episodes each of eleven news shows, the gap at a story
change (median 0.51–0.58 s) was indistinguishable from the gap between two
sentences of the same story (0.44–0.54 s). Nothing in the audio told a
listener a new story had begun, and nothing gave them a moment to file the
last one.

The fix is deterministic and lives in the audio, not in a tag the voice may
read aloud:

1. :func:`story_boundary_lines` finds the script lines where a new story
   starts by mapping each spoken sentence to the digest item it tells —
   numbered items and sourced paragraphs are stories; an essay section (a
   deep dive, prose with no source) is ONE unit, so its paragraphs never
   split. No model cooperation, nothing new in any prompt.
2. :func:`boundary_anchors` finds those lines in the Whisper words of the
   raw voice track, and :func:`choose_cuts` puts each cut in the middle of
   the audio's own silence at that hand-over (:func:`detect_silences`) —
   never inside a word; no silence there means no cut.
3. :func:`insert_silences_cmd` splices ``story_break_seconds`` of silence at
   each cut into a lossless WAV that the music mix then reads — no extra
   lossy encode. In the mix the sidechain lets the bed come up a little in
   the gap, which is the radio cue for "next story".
4. :func:`shift_transcript` moves every later Whisper timestamp by the
   silence already inserted, so captions, Shorts windows, the Nerra Daily
   promo cut and chapters stay aligned with the audio they describe.

Grok's documented ``[pause]`` tag was measured first and rejected for this:
across the 24 committed uses it rendered anywhere from 0.0 to 2.4 s.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

#: A sentence needs at least this much evidence (sum of log-IDF weights of
#: the digest-unit tokens it shares) to be assigned to a story.
MIN_ASSIGN_SCORE = 4.0
#: ...and share at least this many distinct words with it (the identity
#: line "This is <Show>, episode N" shares only the show's own name).
MIN_ASSIGN_TOKENS = 3
#: Characters of a line's opening matched against the transcript stream.
CHAR_PROBE = 24
CHAR_PROBE_MIN = 12
#: Silence detection on the raw voice track (Grok TTS has a clean floor).
SILENCE_NOISE_DB = -45.0
SILENCE_MIN_SECONDS = 0.15
#: How far either side of the Whisper hand-over a silence may sit.
ANCHOR_WINDOW = 0.6

_STOP = frozenset(
    "the a an and or of to in on for with at by from is are was were be been "
    "it its this that these those as has have had not but if than then so into "
    "over under about after before also more most new said says will would can "
    "could may might their they them he she his her we our you your one two "
    "three four five six seven eight nine ten eleven twelve twenty thirty forty "
    "fifty sixty seventy eighty ninety hundred thousand million billion "
    "percent point there here what which who when where while just still now "
    "today yesterday week year years day days".split())

_HEADER_RE = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$")
_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+")
_URL_RE = re.compile(r"https?://\S+")
_SOURCE_RE = re.compile(r"(?im)^\s*(?:\*\*)?source", re.M)
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _tokens(text: str) -> frozenset:
    t = (text or "").lower().replace("space x", "spacex")
    t = _URL_RE.sub(" ", t)
    return frozenset(w for w in re.findall(r"[a-z][a-z0-9\-]{2,}|\d+", t)
                     if w not in _STOP)


@dataclass(frozen=True)
class StoryUnit:
    """One story (or one essay) of the digest."""

    label: str
    tokens: frozenset
    sentences: int


def story_units(digest_md: str) -> List[StoryUnit]:
    """The digest's stories, in order.

    Each numbered item is a story; each prose paragraph that carries a URL
    or a Source line is a story (Community Buzz); consecutive prose
    paragraphs WITHOUT one in the same section are ONE unit (an essay —
    the Engineering Deep Dive, AI & Compute). Text before the first
    section header (title, hook, price line) is not a story.
    """
    units: List[StoryUnit] = []
    in_sections = False
    essay: List[str] = []

    def flush_essay():
        if essay:
            _add(" ".join(essay), "essay")
            essay.clear()

    def _add(text: str, label: str):
        toks = _tokens(text)
        if len(toks) >= 6:
            n = len([s for s in _SENT_SPLIT_RE.split(text.strip()) if s.strip()])
            units.append(StoryUnit(label=label, tokens=toks, sentences=max(1, n)))

    for para in re.split(r"\n[ \t]*\n", digest_md or ""):
        lines = [ln for ln in para.split("\n") if ln.strip()]
        if not lines:
            continue
        # A header starts a section (and may carry the first item under it).
        current: List[str] = []
        blocks: List[Tuple[str, List[str]]] = []
        for ln in lines:
            if _HEADER_RE.match(ln):
                if current:
                    blocks.append(("body", current))
                blocks.append(("header", [ln]))
                current = []
                continue
            if _NUMBERED_RE.match(ln) and current:
                blocks.append(("body", current))
                current = []
            current.append(ln)
        if current:
            blocks.append(("body", current))
        for kind, block in blocks:
            if kind == "header":
                in_sections = in_sections or block[0].lstrip().startswith("##")
                flush_essay()
                continue
            if not in_sections:
                continue
            text = "\n".join(block)
            if text.lstrip().startswith((">", "|")):
                continue
            if _NUMBERED_RE.match(block[0]) or _URL_RE.search(text) or _SOURCE_RE.search(text):
                flush_essay()
                _add(text, "item")
            else:
                essay.append(text)
    flush_essay()
    return units


def _assign(lines: Sequence[str], units: Sequence[StoryUnit]) -> List[Tuple[int, float]]:
    df: Dict[str, int] = {}
    for u in units:
        for w in u.tokens:
            df[w] = df.get(w, 0) + 1
    n = max(1, len(units))
    out: List[Tuple[int, float]] = []
    for line in lines:
        toks = _tokens(line)
        best, best_score = -1, 0.0
        for i, u in enumerate(units):
            # Summed in sorted order and rounded: set iteration follows the
            # per-process hash seed, and two near-tied stories must resolve
            # the same way on every run (the earlier one wins a tie).
            score = round(sum(math.log(1 + n / df[w]) for w in sorted(toks & u.tokens)), 6)
            if score > best_score:
                best, best_score = i, score
        out.append((best, best_score))
    return out


def script_lines(script: str) -> List[str]:
    return [ln.strip() for ln in (script or "").split("\n") if ln.strip()]


def story_boundary_lines(script: str, digest_md: str) -> List[int]:
    """Indices (into :func:`script_lines`) of lines that open a new story.

    A confident line whose story differs from the current one opens a new
    story when the next confident line stays on it, or when its story is
    short (one or two sentences in the digest). The first story never gets
    a break (the hook and the identity line lead into it), and lines that
    match nothing (the identity line, the closing) never move the cursor.
    """
    units = story_units(digest_md)
    lines = script_lines(script)
    if len(units) < 2 or not lines:
        return []
    assigned = _assign(lines, units)
    confident = [(i, u) for i, (u, s) in enumerate(assigned)
                 if u >= 0 and s >= MIN_ASSIGN_SCORE
                 and len(_tokens(lines[i]) & units[u].tokens) >= MIN_ASSIGN_TOKENS]
    breaks: List[int] = []
    current: Optional[int] = None
    run = 0  # confident lines told so far in the current story
    for k, (idx, unit) in enumerate(confident):
        if unit == current:
            run += 1
            continue
        if current is None:
            current, run = unit, 1
            continue
        nxt = confident[k + 1][1] if k + 1 < len(confident) else None
        # A one-line detour that returns to the story being told (A B A) is
        # a passing reference, not a new story.
        if nxt == current:
            continue
        # Between two one-line items (a market-pulse list, a run of launch
        # notices, a quick-summary block) there is no beat: the list is told
        # together, with a break before it and after it.
        if run >= 2 or nxt == unit:
            breaks.append(idx)
        current, run = unit, 1
    return breaks


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def _spoken(token: str) -> str:
    """Whisper writes numbers as digits; the script spells them out."""
    if token.isdigit() and len(token) <= 9:
        try:
            from engine.utils import number_to_words

            return _norm(number_to_words(int(token)))
        except Exception:  # noqa: BLE001
            return token
    return token


def transcript_words(transcript: dict) -> List[Tuple[str, float, float]]:
    out = []
    for seg in (transcript or {}).get("segments") or []:
        for w in seg.get("words") or []:
            n = _spoken(_norm(w.get("word", "")))
            if n:
                out.append((n, float(w.get("start", 0.0)), float(w.get("end", 0.0))))
    return out


def boundary_anchors(script: str, boundary_idx: Sequence[int],
                     transcript: dict) -> Tuple[List[Tuple[float, float]], int]:
    """``([(prev_word_end, line_start), ...], unmatched)`` for each boundary
    line, located in the Whisper words of the voice track.

    Lines are found in order (each search starts after the last hit) by the
    letters-and-digits of their opening; a line that cannot be found gets no
    anchor — never a guessed one.
    """
    lines = script_lines(script)
    words = transcript_words(transcript)
    # Letters-and-digits stream of the transcript, with the word each
    # character came from: "Keeptrack.space" / "keeptrack space" and
    # "A I" / "AI" are the same characters either way.
    stream = "".join(w[0] for w in words)
    owner: List[int] = []
    first_char: Dict[int, int] = {}
    for i, w in enumerate(words):
        first_char[i] = len(owner)
        owner.extend([i] * len(w[0]))
    anchors: List[Tuple[float, float]] = []
    unmatched = 0
    pos_char = len(words[0][0]) if words else 0
    for idx in boundary_idx:
        toks = [t for t in (_norm(x) for x in lines[idx].split()) if t]
        hit = None
        # From the first word; then from the second or third when the line
        # opens on something Whisper spells differently (a station's call
        # letters, a model number).
        for skip in (0, 1, 2):
            probe = "".join(toks[skip:])[:CHAR_PROBE]
            if len(probe) < CHAR_PROBE_MIN:
                break
            at = stream.find(probe, pos_char)
            if at >= 0:
                hit = max(0, owner[at] - skip)
                break
        if hit is None or hit == 0:
            unmatched += 1
            continue
        anchors.append((words[hit - 1][2], words[hit][1]))
        pos_char = first_char[hit] + 1
    return anchors, unmatched


def detect_silences(audio: Path, *, noise_db: float = SILENCE_NOISE_DB,
                    min_seconds: float = SILENCE_MIN_SECONDS) -> List[Tuple[float, float]]:
    """``[(start, end), ...]`` silent stretches of *audio* (ffmpeg
    silencedetect). Whisper's word times often abut across a real pause, so
    the cut is placed in the audio's own silence, not between word times."""
    import subprocess

    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(audio), "-af",
         f"silencedetect=noise={noise_db}dB:d={min_seconds}", "-f", "null", "-"],
        capture_output=True, text=True, timeout=600,
    )
    return parse_silencedetect(proc.stderr)


def parse_silencedetect(log: str) -> List[Tuple[float, float]]:
    out: List[Tuple[float, float]] = []
    start: Optional[float] = None
    for line in (log or "").splitlines():
        m = re.search(r"silence_start:\s*(-?[\d.]+)", line)
        if m:
            start = max(0.0, float(m.group(1)))
            continue
        m = re.search(r"silence_end:\s*([\d.]+)", line)
        if m and start is not None:
            out.append((start, float(m.group(1))))
            start = None
    return out


def choose_cuts(anchors: Sequence[Tuple[float, float]],
                silences: Sequence[Tuple[float, float]]) -> Tuple[List[float], int]:
    """``(cut_times, unplaced)``: for each anchor, the middle of the audio
    silence nearest the hand-over between the two words (within
    ``ANCHOR_WINDOW`` seconds). No silence there = no cut: splicing inside
    speech would chop a word."""
    cuts: List[float] = []
    unplaced = 0
    for prev_end, start in anchors:
        lo, hi = prev_end - ANCHOR_WINDOW, start + ANCHOR_WINDOW
        mid = (prev_end + start) / 2.0
        best = None
        for s0, s1 in silences:
            if s1 < lo or s0 > hi:
                continue
            c = (s0 + s1) / 2.0
            if best is None or abs(c - mid) < abs(best - mid):
                best = c
        if best is None:
            unplaced += 1
            continue
        cuts.append(round(best, 3))
    return sorted(set(cuts)), unplaced


def insert_silences_cmd(src: Path, dst: Path, cut_times: Sequence[float],
                        seconds: float) -> List[str]:
    """ffmpeg command: *src* with *seconds* of silence spliced at every cut,
    written as 48 kHz PCM WAV (lossless — the music mix re-encodes once)."""
    cuts = sorted(t for t in cut_times if t > 0)
    parts: List[str] = []
    labels: List[str] = []
    edges = [0.0, *cuts]
    for i, start in enumerate(edges):
        end = cuts[i] if i < len(cuts) else None
        trim = f"atrim=start={start:.3f}" + (f":end={end:.3f}" if end is not None else "")
        pad = f",apad=pad_dur={seconds:.3f}" if end is not None else ""
        parts.append(f"[0:a]{trim},asetpts=PTS-STARTPTS{pad}[s{i}]")
        labels.append(f"[s{i}]")
    graph = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[out]"
    return ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
            "-filter_complex", graph, "-map", "[out]",
            "-ar", "48000", "-c:a", "pcm_s16le", str(dst)]


def shift_time(t: float, cut_times: Sequence[float], seconds: float) -> float:
    return t + seconds * sum(1 for c in cut_times if c <= t)


def shift_transcript(transcript: dict, cut_times: Sequence[float], seconds: float) -> dict:
    """A copy of a Whisper transcript with every timestamp after each cut
    moved by the silence inserted there."""
    cuts = sorted(cut_times)
    out = json.loads(json.dumps(transcript))
    for seg in out.get("segments") or []:
        for key in ("start", "end"):
            if key in seg:
                seg[key] = round(shift_time(float(seg[key]), cuts, seconds), 3)
        for w in seg.get("words") or []:
            for key in ("start", "end"):
                if key in w:
                    w[key] = round(shift_time(float(w[key]), cuts, seconds), 3)
    if "duration" in out and out["duration"]:
        out["duration"] = round(float(out["duration"]) + seconds * len(cuts), 3)
    return out


def rewrite_transcript_files(output_dir: Path, episode_prefix: str,
                             cut_times: Sequence[float], seconds: float) -> bool:
    """Shift the committed ``<prefix>_transcript.json`` and re-render its
    ``.vtt`` from the shifted segments. The ``.txt`` carries no times."""
    from engine.transcripts import segments_to_vtt

    json_path = Path(output_dir) / f"{episode_prefix}_transcript.json"
    if not json_path.exists() or not cut_times:
        return False
    data = json.loads(json_path.read_text(encoding="utf-8"))
    shifted = shift_transcript(data, cut_times, seconds)
    json_path.write_text(json.dumps(shifted, indent=2, ensure_ascii=False), encoding="utf-8")
    vtt_path = Path(output_dir) / f"{episode_prefix}_transcript.vtt"
    if vtt_path.exists():
        vtt_path.write_text(segments_to_vtt(shifted.get("segments") or []), encoding="utf-8")
    return True
