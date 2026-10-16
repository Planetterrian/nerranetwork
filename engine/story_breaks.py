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
3. :func:`plan_breaks` measures the voice's own pause at each cut and
   :func:`insert_silences_cmd` splices only the difference to
   ``story_break_seconds`` — the TOTAL pause — into a lossless WAV that the
   music mix then reads (no extra lossy encode). Oct 14 2026: the first
   version added a fixed 1.2 s to a ~0.45 s pause, 1.6-1.7 s of dead air
   (the music bed is gone after ~48 s, so nothing came up in the gap) and
   the operator heard it as forced. With ``story_break_cue`` the mix lays a
   soft swell of the show's theme under each pause
   (:func:`breather_starts` -> ``engine.audio.mix_with_music(breathers=)``).
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
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
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
#: A beat closer than this to the previous one is dropped: a story told in
#: under twenty seconds is a brief, and beats every few seconds read as a
#: stutter (Vancouver Ep021 had two 7 s apart).
MIN_STORY_SECONDS = 20.0

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
    section: str = ""
    words: int = 0


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
    section = [""]
    story_section = [False]

    def flush_essay():
        if essay:
            _add(" ".join(essay), "item" if story_section[0] else "essay")
            essay.clear()

    def _add(text: str, label: str):
        toks = _tokens(text)
        if len(toks) >= 6:
            n = len([s for s in _SENT_SPLIT_RE.split(text.strip()) if s.strip()])
            units.append(StoryUnit(label=label, tokens=toks, sentences=max(1, n),
                                   section=section[0], words=len(text.split())))

    # A horizontal rule is a paragraph break too: Fascinating Frontiers
    # writes ``> **hook**\n---\n**first item**`` with no blank line, and
    # the first item used to vanish inside the skipped hook block.
    for para in re.split(r"\n[ \t]*\n|\n(?:-{3,}|━{3,})[ \t]*\n", digest_md or ""):
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
                m = _HEADER_RE.match(block[0])
                section[0] = (m.group(1) if m else "").strip().lower()
                story_section[0] = bool(_NUMBERED_RE.match(section[0]))
                continue
            text = "\n".join(block)
            if text.lstrip().startswith((">", "|")):
                continue
            # Oct 16 2026: a numbered HEADING is a story title, so its whole
            # section is one story. Omni View writes "### 1) <title>" over a
            # "What happened" paragraph, a "Context" paragraph and a
            # "Read more (sources)" list; the list was its own unit and the
            # script's sentence about the second source got a beat in the
            # middle of the lead story.
            if story_section[0]:
                essay.append(text)
                continue
            # Oct 14 2026: a sourced or numbered item under the hook, before
            # any ``##`` header, is a story. Fascinating Frontiers Ep222
            # wrote its six news items straight under the hook rule and
            # the whole block was skipped as front matter — one beat in
            # the episode. The title, date and price lines carry no
            # Source line and no number, so they still never count.
            # Oct 16 2026: FF Ep224 wrote the same block with each item's
            # ``Source: [domain](url)`` at the END of its paragraph, which
            # the line-start Source pattern never sees — one beat for seven
            # stories again. A link in the paragraph counts as its source.
            if not in_sections and not (
                _NUMBERED_RE.match(block[0]) or _SOURCE_RE.search(text)
                or _URL_RE.search(text)
            ):
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


#: Openings that continue the story already being told: a pronoun, a
#: demonstrative or a connective. A new story names its subject first (the
#: shared prompt rule), so a line that opens like this is never a new story.
_CONTINUATION_RE = re.compile(
    r"^\W*(?:he|she|it|its|they|their|them|his|her|this|that|these|those|"
    r"there|here|and|but|so|also|still|both|neither|"
    r"the same|the company|the firm|the agency|the group|the move|the deal|"
    r"the plan|the bill|the court|the report|the study)\b",
    re.IGNORECASE,
)


#: A digest item this short is a list entry (an "Also Today" line, a roads
#: list, a Top World one-liner), told with its neighbours as one block.
SHORT_ITEM_MAX_WORDS = 40


def _is_short_item(unit: "StoryUnit") -> bool:
    return unit.sentences <= 2 and unit.words <= SHORT_ITEM_MAX_WORDS


def opens_as_continuation(line: str) -> bool:
    return bool(_CONTINUATION_RE.match(line or ""))


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
        # A line that opens on a pronoun or a connective is still talking
        # about something already introduced — Vancouver Ep021 put a beat
        # before "He asked Albertans to vote…", splitting the premier from
        # his own quote. The story moves on without a beat.
        if opens_as_continuation(lines[idx]):
            current, run = unit, 1
            continue
        # Short items under the same section heading (a weather reading
        # and its forecast, a roads list, the Top World one-liners) are
        # told as one block: a beat before the block and after it.
        # Oct 14 2026: a short item is short in WORDS too. Fascinating
        # Frontiers Ep222 wrote six two-sentence stories of 40-60 words
        # under one heading and the whole news block got one beat.
        if (units[unit].section and units[unit].section == units[current].section
                and _is_short_item(units[unit]) and _is_short_item(units[current])):
            current, run = unit, 1
            continue
        # Between two one-line items (a market-pulse list, a run of launch
        # notices, a quick-summary block) there is no beat: the list is told
        # together, with a break before it and after it.
        if run >= 2 or nxt == unit:
            breaks.append(idx)
        current, run = unit, 1
    return _settle_adjacent(breaks, lines, units, assigned)


def _unit_score(line: str, units: Sequence[StoryUnit], unit: int) -> float:
    df: Dict[str, int] = {}
    for u in units:
        for w in u.tokens:
            df[w] = df.get(w, 0) + 1
    n = max(1, len(units))
    return round(sum(math.log(1 + n / df[w]) for w in sorted(_tokens(line) & units[unit].tokens)), 6)


def _settle_adjacent(breaks: List[int], lines: Sequence[str], units: Sequence[StoryUnit],
                     assigned: Sequence[Tuple[int, float]]) -> List[int]:
    """Two beats on consecutive lines are one story change: keep one.

    Oct 16 2026: the audio keeps only the first beat of a pair (the second
    falls inside ``MIN_STORY_SECONDS``), so the pause landed wherever the
    first line was — Omni View Ep207 paused before the G7 story's LAST
    sentence (a line the deep dive also covers) instead of before Rubio.
    The line between the two stories goes with whichever it reads like
    more: the story before it (keep the later beat) or the story after it
    (keep the earlier one — Fascinating Frontiers Ep224's green-star line,
    which opens that story).
    """
    out = list(breaks)
    k = 0
    while k + 1 < len(out):
        i, j = out[k], out[k + 1]
        if j != i + 1:
            k += 1
            continue
        prev_unit = next((assigned[x][0] for x in range(i - 1, -1, -1)
                          if assigned[x][0] >= 0 and assigned[x][1] >= MIN_ASSIGN_SCORE), -1)
        next_unit = assigned[j][0]
        opens_i, opens_j = _opens_on_section(lines[i], units), _opens_on_section(lines[j], units)
        if opens_j and not opens_i:
            del out[k]       # the later line names the segment it opens
        elif opens_i and not opens_j:
            del out[k + 1]
        elif prev_unit >= 0 and next_unit >= 0 and (
                _unit_score(lines[i], units, prev_unit) > _unit_score(lines[i], units, next_unit)):
            del out[k]       # the line closes the story before it
        else:
            del out[k + 1]   # the line opens the story after it
        k += 1
    return out


#: Words a section heading shares with almost every show, which name no
#: segment in particular.
_SECTION_GENERIC = frozenset({
    "today", "todays", "news", "top", "stories", "story", "items", "item",
    "major", "world", "daily", "network", "lead", "notes", "note", "more",
    "other", "quick", "segment", "what", "this", "week", "weekly",
})


def _opens_on_section(line: str, units: Sequence[StoryUnit]) -> bool:
    """Whether *line*'s opening words name one of the digest's sections
    (a segment opener such as the what's-on list, the Both Sides case, the
    progress item, the Board or the deep dive), so it, not the line beside
    it, is where the listener hears the segment change."""
    opening = set(re.findall(r"[a-z']+", " ".join((line or "").lower().split()[:10])))
    opening = {w.replace("'", "") for w in opening}
    for name in {u.section for u in units if u.section}:
        words = {w.replace("'", "") for w in re.findall(r"[a-z']+", name)}
        salient = {w for w in words if len(w) >= 4 and w not in _SECTION_GENERIC
                   and w not in _STOP}
        if salient & opening:
            return True
    return False


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

def _norm(word: str) -> str:
    # Accents fold to their letters: "Nación" and Whisper's "Nacion" are
    # the same word, where dropping the "ó" left "nacin" on one side only.
    folded = unicodedata.normalize("NFKD", word or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", folded.lower())


def _two_digits(n: int) -> str:
    from engine.utils import number_to_words

    return number_to_words(n)


def _year_words(year: int) -> str:
    """A year the way the scripts say it: 1977 "nineteen seventy-seven",
    1900 "nineteen hundred", 2001 "two thousand one", 2026 "twenty
    twenty-six"."""
    hi, lo = divmod(year, 100)
    if 2000 <= year <= 2009:
        return "two thousand" + (f" {_two_digits(lo)}" if lo else "")
    head = _two_digits(hi)
    if lo == 0:
        return f"{head} hundred"
    return f"{head} {'oh ' if lo < 10 else ''}{_two_digits(lo)}"


def _decade_words(year: int) -> str:
    """1990s "nineteen nineties", 2000s "two thousands"."""
    if year == 2000:
        return "two thousands"
    hi, lo = divmod(year, 100)
    tens = _two_digits(lo)
    plural = tens[:-1] + "ies" if tens.endswith("y") else tens + "s"
    return f"{_two_digits(hi)} {plural}"


def _spoken(token: str) -> str:
    """Whisper writes numbers as digits; the script spells them out.

    Oct 16 2026: a 4-digit year and a decade are spoken as years ("1977",
    "the 1990s", "the early 2000s"), which the cardinal "one thousand nine
    hundred seventy-seven" never matched — Unintended Consequences opens a
    segment on a date most days, and those beats never reached the audio."""
    m = re.fullmatch(r"(1[1-9]\d\d|20\d\d)(s?)", token or "")
    if m:
        try:
            year = int(m.group(1))
            if m.group(2):
                if year % 10 == 0:
                    return _norm(_decade_words(year))
            else:
                return _norm(_year_words(year))
        except Exception:  # noqa: BLE001
            return token
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
        # Both sides go through the same number speech: a script line that
        # kept "1980s" as digits must still meet Whisper's "1980s".
        toks = [t for t in (_spoken(_norm(x)) for x in lines[idx].split()) if t]
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
        if hit is None:
            hit = _fuzzy_hit(toks, words, owner[pos_char] if pos_char < len(owner) else len(words),
                             _expected_word(lines, idx, len(words)))
        if hit is None or hit == 0:
            unmatched += 1
            continue
        anchors.append((words[hit - 1][2], words[hit][1]))
        pos_char = first_char[hit] + 1
    return anchors, unmatched


#: Oct 16 2026 — the fallback when a line's opening is not in the
#: transcript letter for letter. Whisper writes "the early 2000s" for "the
#: early two thousands", "1,500 kilometres" for "fifteen hundred", and its
#: own spelling of a name ("Columbia's main city", "Helisco", "La
#: Nassion"); on the Oct 15-16 slate that left 4 of 8 story changes on
#: Unintended Consequences and 5 of 8 on the Asia Pacific desk with no
#: pause at all. The fallback compares the opening's letters with every
#: transcript position near where the line should be (its share of the
#: script's words) and takes the closest one, only when it is close.
FUZZY_WORDS = 8
FUZZY_MIN_RATIO = 0.72
FUZZY_WINDOW_WORDS = 150


def _expected_word(lines: Sequence[str], idx: int, n_words: int) -> int:
    before = sum(len(ln.split()) for ln in lines[:idx])
    total = max(1, sum(len(ln.split()) for ln in lines))
    return int(round(before * n_words / total))


def _fuzzy_hit(toks: Sequence[str], words: Sequence[Tuple[str, float, float]],
               start_word: int, expected: int) -> Optional[int]:
    target = "".join(toks[:FUZZY_WORDS])
    if len(target) < CHAR_PROBE:
        return None
    lo = max(1, start_word, expected - FUZZY_WINDOW_WORDS)
    hi = min(len(words) - 1, expected + FUZZY_WINDOW_WORDS)
    best: Optional[Tuple[float, int]] = None
    for h in range(lo, hi + 1):
        cand = "".join(w[0] for w in words[h:h + FUZZY_WORDS + 4])[:len(target)]
        # A story opening is said as written: its first letter survives
        # Whisper even when the rest of a name does not ("Columbia's" for
        # "Colombia's"), and requiring it keeps the match off a
        # neighbouring word.
        if not cand or cand[0] != target[0]:
            continue
        ratio = round(SequenceMatcher(None, target, cand, autojunk=False).ratio(), 4)
        if best is None or (ratio, -abs(h - expected)) > (best[0], -abs(best[1] - expected)):
            best = (ratio, h)
    if best is None or best[0] < FUZZY_MIN_RATIO:
        return None
    return best[1]


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


@dataclass(frozen=True)
class Break:
    """One story change in the raw voice track.

    ``cut`` is where extra silence is spliced (the middle of the voice's
    own pause), ``insert`` how much, and ``gap_start``/``gap_end`` the
    pause the voice already left there.
    """

    cut: float
    insert: float
    gap_start: float
    gap_end: float


def plan_breaks(anchors: Sequence[Tuple[float, float]],
                silences: Sequence[Tuple[float, float]], *,
                gap_seconds: float,
                min_spacing: float = MIN_STORY_SECONDS) -> Tuple[List[Break], int]:
    """``(breaks, unplaced)``: one :class:`Break` per located story change.

    ``gap_seconds`` is the TOTAL pause a listener hears at a story change —
    the voice's own pause is measured and only the difference is spliced,
    so every story change sounds the same length whatever Grok left there.
    Oct 13 2026 added a fixed 1.2 s on top of a pause that was already
    ~0.45 s: 1.6–1.7 s of dead air, almost five times the 0.35 s median
    gap between sentences, and the operator heard it as forced. A beat
    within ``min_spacing`` of the previous one is dropped.
    """
    breaks: List[Break] = []
    unplaced = 0
    for prev_end, start in anchors:
        lo, hi = prev_end - ANCHOR_WINDOW, start + ANCHOR_WINDOW
        mid = (prev_end + start) / 2.0
        best: Optional[Tuple[float, float]] = None
        for s0, s1 in silences:
            if s1 < lo or s0 > hi:
                continue
            if best is None or abs((s0 + s1) / 2 - mid) < abs((best[0] + best[1]) / 2 - mid):
                best = (s0, s1)
        if best is None:
            unplaced += 1
            continue
        s0, s1 = best
        cut = round((s0 + s1) / 2.0, 3)
        if breaks and cut - breaks[-1].cut < min_spacing:
            continue
        insert = round(max(0.0, gap_seconds - (s1 - s0)), 3)
        breaks.append(Break(cut=cut, insert=insert, gap_start=round(s0, 3), gap_end=round(s1, 3)))
    return sorted(breaks, key=lambda b: b.cut), unplaced


def _per_cut(cut_times: Sequence[float], seconds) -> List[Tuple[float, float]]:
    """``[(cut, seconds_spliced), ...]`` sorted; *seconds* is one number for
    every cut or one per cut."""
    if isinstance(seconds, (int, float)):
        pairs = [(float(c), float(seconds)) for c in cut_times]
    else:
        pairs = [(float(c), float(d)) for c, d in zip(cut_times, seconds)]
    return sorted(p for p in pairs if p[0] > 0)


def insert_silences_cmd(src: Path, dst: Path, cut_times: Sequence[float],
                        seconds) -> List[str]:
    """ffmpeg command: *src* with silence spliced at every cut (*seconds*:
    one length for all, or one per cut), written as 48 kHz PCM WAV
    (lossless — the music mix re-encodes once)."""
    pairs = _per_cut(cut_times, seconds)
    cuts = [c for c, _ in pairs]
    parts: List[str] = []
    labels: List[str] = []
    edges = [0.0, *cuts]
    for i, start in enumerate(edges):
        end = cuts[i] if i < len(cuts) else None
        trim = f"atrim=start={start:.3f}" + (f":end={end:.3f}" if end is not None else "")
        pad = (f",apad=pad_dur={pairs[i][1]:.3f}"
               if end is not None and pairs[i][1] > 0 else "")
        parts.append(f"[0:a]{trim},asetpts=PTS-STARTPTS{pad}[s{i}]")
        labels.append(f"[s{i}]")
    graph = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[out]"
    return ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
            "-filter_complex", graph, "-map", "[out]",
            "-ar", "48000", "-c:a", "pcm_s16le", str(dst)]


def shift_time(t: float, cut_times: Sequence[float], seconds) -> float:
    return t + sum(d for c, d in _per_cut(cut_times, seconds) if c <= t)


def shift_transcript(transcript: dict, cut_times: Sequence[float], seconds) -> dict:
    """A copy of a Whisper transcript with every timestamp after each cut
    moved by the silence inserted there (*seconds*: one length or one per
    cut)."""
    pairs = _per_cut(cut_times, seconds)
    cuts = [c for c, _ in pairs]
    lens = [d for _, d in pairs]
    out = json.loads(json.dumps(transcript))
    for seg in out.get("segments") or []:
        for key in ("start", "end"):
            if key in seg:
                seg[key] = round(shift_time(float(seg[key]), cuts, lens), 3)
        for w in seg.get("words") or []:
            for key in ("start", "end"):
                if key in w:
                    w[key] = round(shift_time(float(w[key]), cuts, lens), 3)
    if "duration" in out and out["duration"]:
        out["duration"] = round(float(out["duration"]) + sum(lens), 3)
    return out


def breather_starts(breaks: Sequence[Break]) -> List[float]:
    """Where each story change's pause begins in the SPLICED voice track —
    the moment the last word of a story ends — for the music cue the mix
    lays under it."""
    cuts = [b.cut for b in breaks]
    lens = [b.insert for b in breaks]
    return [round(shift_time(b.gap_start, cuts, lens), 3) for b in breaks]


def rewrite_transcript_files(output_dir: Path, episode_prefix: str,
                             cut_times: Sequence[float], seconds) -> bool:
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
