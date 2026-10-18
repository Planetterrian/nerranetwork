"""Numeric fact cards for long-form video (Sep 2026).

EN long-form retention sits at ~13% average view percentage with a
median view duration around 70 s, while the same audio cut into Shorts
holds ~48%. The Shorts selector already knows that the strongest beats
in a news episode are the NUMBERS (``engine.shorts_selector`` scores
numeric reveals first). Long-form gave those numbers no visual
presence: a figure was spoken and gone.

This module turns the spoken figures into on-screen cards — the figure
large in Nerra cyan, a short label from the sentence around it — timed
from the Whisper word transcript the pipeline already has, so the card
lands exactly when the host says the number. Deterministic, no LLM, no
new storage. Render-only (outside landmine #17): the audio is untouched.

Rules that bind:

* **Whisper writes spoken figures as digits, split across tokens**
  (``$368`` ``.16,`` / ``4`` ``,000`` / ``14`` ``.3`` ``.9``). Runs are
  merged before anything is judged; a token with letters (``V3``,
  ``B1081``, ``1990s``, ``35th``) is never a figure.
* **Money, percentages and multiplier units outrank bare numbers**;
  a bare year, the episode number ("episode 600") and anything inside
  the opening hook window are never a card.
* **Labels are never sliced here** — ``engine.titles.clip_words`` on
  ``FACT_CARD_LABEL_MAX``, then the dangling-tail rule from
  ``engine.chapters`` (never end on "for"/"of"/"the").
* Cards keep ``MIN_GAP_S`` apart and clear of chapter title cards, so
  the frame never shows two cards popping at once.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from engine.titles import FACT_CARD_LABEL_MAX, clip_words

logger = logging.getLogger(__name__)

#: Seconds a card stays on screen.
FACT_CARD_SECONDS = 4.0
#: Most cards per episode — a card every ~40 s on a 10-minute episode
#: is a rhythm; more is wallpaper.
MAX_CARDS = 8
#: Minimum spacing between two cards.
MIN_GAP_S = 40.0
#: The opening hook title owns the first seconds of the frame.
OPEN_SKIP_S = 6.0
#: Clearance after a chapter title card starts (the card is ~4 s).
CHAPTER_CLEAR_S = 5.0
#: Words of context read after (or before) the figure for the label.
_LABEL_WORDS = 8

_START_RE = re.compile(r"^[\$€£]?\d[\d,]*(?:\.\d+)?%?[.,;:!?]*$")
# Oct 18 2026: a lone "%" is a continuation too — Whisper writes "100"
# "%" as two tokens, and the card read "100 / % means claims are already".
_CONT_RE = re.compile(r"^(?:(?:[.,]\d+|,\d{3})%?|%)[.,;:!?]*$")
_SENTENCE_END = (".", "!", "?")
_UNIT_WORDS = {
    "million": "million", "billion": "billion", "trillion": "trillion",
    "thousand": "thousand", "percent": "%", "per cent": "%",
    "dollars": "$",
}
# A bare four-digit 1500-2099 is a year ("1856", "1181" on FF Ep223); a
# count of that size is written "1,856".
_YEAR_RE = re.compile(r"^(?:1[5-9]|20)\d\d$")
_EPISODE_WORDS = frozenset({"episode", "ep", "ep.", "number"})
# Sep 22 2026: a small count with a unit noun IS a fact ("9 satellites",
# "1 gigawatt", "5 orbital launches"), but ``_score`` gave every bare
# value under 100 a zero, so the treatment shows rendered 1-3 cards an
# episode against the >= 3 the fact-card experiment asked for while their
# transcripts carried 12-25 digit figures. The noun is consumed into the
# run (so the label never repeats it) and scored 2 — below money and
# percentages, above bare thousands. Digits only: a spelled-out number
# stays out of scope (``_START_RE`` is untouched).
_COUNT_NOUNS = frozenset({
    "gigawatt", "gigawatts", "megawatt", "megawatts", "kilowatt", "kilowatts",
    "satellite", "satellites", "launch", "launches", "flight", "flights",
    "mission", "missions", "engine", "engines", "booster", "boosters",
    "year", "years", "month", "months", "day", "days", "hour", "hours",
    "mile", "miles", "km", "kilometer", "kilometers", "kilometre", "kilometres",
    "tonne", "tonnes", "ton", "tons", "kg", "kilogram", "kilograms",
    "employee", "employees", "vehicle", "vehicles", "unit", "units",
    "country", "countries", "patient", "patients", "sample", "samples",
    "light-year", "light-years", "orbit", "orbits", "starlink", "starlinks",
    "pound", "pounds", "foot", "feet", "meter", "meters", "metre", "metres",
    "euro", "euros", "yuan", "yen",
})
#: Oct 18 2026: the second word of a compound unit. Whisper writes
#: "light" "-years" and "gigawatt" "hour"; the card read "1 gigawatt /
#: Hour" and "37 million / Light -years away in Columbus". Each entry is
#: (unit already read, next words) -> the unit as displayed.
_COMPOUND_UNITS = {
    ("gigawatt", "hour"): "GWh", ("gigawatt", "hours"): "GWh",
    ("gigawatts", "hour"): "GWh", ("gigawatts", "hours"): "GWh",
    ("megawatt", "hour"): "MWh", ("megawatt", "hours"): "MWh",
    ("megawatts", "hour"): "MWh", ("megawatts", "hours"): "MWh",
    ("kilowatt", "hour"): "kWh", ("kilowatt", "hours"): "kWh",
    ("kilowatts", "hour"): "kWh", ("kilowatts", "hours"): "kWh",
    ("miles", "per hour"): "mph", ("mile", "per hour"): "mph",
    ("km", "per hour"): "km/h", ("kilometers", "per hour"): "km/h",
    ("kilometres", "per hour"): "km/h",
    ("square", "feet"): "sq ft", ("square", "foot"): "sq ft",
    ("square", "meters"): "m²", ("square", "metres"): "m²",
}
#: After a scale word ("million", "billion") one more unit word may follow:
#: "1.7 million square feet", "6.08 million euros", "160 million won".
_SCALE_UNITS = frozenset({"million", "billion", "trillion", "thousand"})
_AFTER_SCALE = frozenset({
    "euros", "pounds", "won", "yuan", "yen", "rupees", "square", "light",
    "tons", "tonnes", "kilometers", "kilometres", "miles", "people", "users",
    "vehicles", "units", "subscribers", "customers", "years", "light-years",
})
#: "in 2021 launches resumed" — a year before a count noun is still a year.
_YEAR_PREPS = frozenset({"in", "since", "by", "from", "until", "of", "through"})


@dataclass(frozen=True)
class FactCard:
    start: float
    figure: str
    label: str
    score: int

    def as_tuple(self) -> Tuple[float, str, str]:
        return (self.start, self.figure, self.label)


def _clean(tok: str) -> str:
    return str(tok or "").strip()


def _strip_trailing_punct(tok: str) -> Tuple[str, bool]:
    """Return ``(token, ended_sentence)`` with trailing punctuation removed."""
    ended = tok.endswith(_SENTENCE_END)
    return tok.rstrip(".,;:!?"), ended


def _dangling_tail() -> frozenset:
    try:
        from engine.chapters import _DANGLING_TAIL
        return _DANGLING_TAIL
    except Exception:  # noqa: BLE001 — label rule is garnish
        return frozenset()


def _fit_label(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip(" ,;:-–—")
    # Whisper splits "$14.08" into "$14" ".8", "3.7%" into "3.7" "%" and
    # "end-to-end" into "end" "-to" "-end": re-join them in labels.
    from engine.captions import join_split_text
    text = join_split_text(text)
    if not text:
        return ""
    clean = clip_words(text, FACT_CARD_LABEL_MAX, ellipsis="")
    words = clean.split()
    tail = _dangling_tail()
    while words and words[-1].lower().strip(".,;:!?") in tail:
        words.pop()
    if not words:
        return ""
    out = " ".join(words).rstrip(".,;:!?")
    return out[:1].upper() + out[1:]


def _score(figure: str, unit: str, prev_word: str) -> int:
    if prev_word.lower().strip(".,;:!?") in _EPISODE_WORDS:
        return 0
    core = figure.lstrip("$€£").rstrip("%")
    if figure.startswith(("$", "€", "£")) or figure.endswith("%"):
        return 3
    if unit in ("million", "billion", "trillion", "thousand", "%", "$"):
        return 3
    if unit in _COUNT_NOUNS:
        if _YEAR_RE.match(core) and prev_word.lower().strip(".,;:!?") in _YEAR_PREPS:
            return 0
        # "Falcon 9 booster", "Raptor 3 engines", "Model 3 units": a number
        # right after a capitalised word is a designation, not a count. A
        # count follows a verb, article or preposition (lowercase).
        if prev_word[:1].isupper():
            return 0
        return 2
    if _YEAR_RE.match(core):
        return 0
    if core.count(".") > 1:
        # 14.3.9 — a version number; worth a card only with a "v".
        return 1 if prev_word.lower() in ("v", "version") else 0
    try:
        value = float(core.replace(",", ""))
    except ValueError:
        return 0
    if value >= 1000:
        return 2
    if value >= 100:
        return 1
    return 0


def _word_at(words: Sequence[dict], k: int) -> Tuple[str, bool]:
    if k >= len(words):
        return "", True
    core, ended = _strip_trailing_punct(_clean(words[k].get("word")))
    return core.lower(), ended


def _extend_unit(words: Sequence[dict], j: int, unit: str) -> Tuple[str, int, bool]:
    """Read the rest of a compound unit after *unit* (the word at *j*).

    Returns ``(display, last_index, ended)``. "1 gigawatt hour" shows as
    "1 GWh", "230 miles per hour" as "230 mph", "1.7 million square feet"
    as "1.7 million sq ft", "37 million light -years" as "37 million
    light-years". Anything else returns the unit unchanged.
    """
    display, ended = unit, False
    w1, e1 = _word_at(words, j + 1)
    w2, e2 = _word_at(words, j + 2)
    if unit in _SCALE_UNITS and w1 == "dollars":
        return f"{unit} dollars", j + 1, e1
    if unit in _SCALE_UNITS and w1 in _AFTER_SCALE:
        if w1 in ("square", "light") and w2:
            joined = "light-years" if (w1 == "light" and w2.lstrip("-") in ("years", "year")) else None
            if joined:
                return f"{unit} {joined}", j + 2, e2
            compound = _COMPOUND_UNITS.get((w1, w2))
            if compound:
                return f"{unit} {compound}", j + 2, e2
            return display, j, ended
        return f"{unit} {w1}", j + 1, e1
    if (unit, w1) in _COMPOUND_UNITS:
        return _COMPOUND_UNITS[(unit, w1)], j + 1, e1
    if w1 == "per" and (unit, f"per {w2}") in _COMPOUND_UNITS:
        return _COMPOUND_UNITS[(unit, f"per {w2}")], j + 2, e2
    if w1.startswith("-") and unit in ("light",):
        return "light-years", j + 1, e1
    return display, j, ended


def _merge_runs(words: Sequence[dict]) -> List[dict]:
    """Merge Whisper's split numeric tokens into figure candidates.

    Each candidate: ``{"start", "figure", "unit", "idx_from", "idx_to",
    "prev_word", "ended"}`` where the indexes bound the run inside
    *words* (inclusive) and ``ended`` says the run closed a sentence.
    """
    out: List[dict] = []
    i = 0
    n = len(words)
    while i < n:
        tok = _clean(words[i].get("word"))
        if not _START_RE.match(tok):
            i += 1
            continue
        figure, ended = _strip_trailing_punct(tok)
        try:
            start = float(words[i].get("start"))
        except (TypeError, ValueError):
            i += 1
            continue
        j = i
        while not ended and j + 1 < n:
            nxt = _clean(words[j + 1].get("word"))
            if not _CONT_RE.match(nxt):
                break
            piece, ended = _strip_trailing_punct(nxt)
            figure += piece
            j += 1
        unit = ""
        if not ended and j + 1 < n:
            nxt_raw = _clean(words[j + 1].get("word"))
            nxt, nxt_ended = _strip_trailing_punct(nxt_raw)
            key = nxt.lower()
            if key in _UNIT_WORDS:
                unit = _UNIT_WORDS[key]
                j += 1
                ended = nxt_ended
            elif key in _COUNT_NOUNS and not figure.endswith("%"):
                unit = key
                j += 1
                ended = nxt_ended
        display = unit
        if unit and not ended:
            display, j, ended = _extend_unit(words, j, unit)
        prev_word = _clean(words[i - 1].get("word")) if i > 0 else ""
        out.append({
            "start": start, "figure": figure, "unit": unit,
            "unit_display": display,
            "idx_from": i, "idx_to": j, "prev_word": prev_word,
            "ended": ended,
        })
        i = j + 1
    return out


def _display_figure(figure: str, unit: str) -> str:
    if unit in ("GWh", "MWh", "kWh", "mph", "km/h", "sq ft", "m²"):
        return f"{figure} {unit}"
    if unit.endswith(" dollars"):
        scale = unit.split()[0]
        return f"{figure if figure.startswith('$') else '$' + figure} {scale}"
    if unit == "%":
        return figure if figure.endswith("%") else figure + "%"
    if unit == "$":
        return figure if figure.startswith("$") else "$" + figure
    if unit:
        return f"{figure} {unit}"
    return figure


#: Oct 18 2026 label rules. A label is read from the words after the
#: figure, and it stops where the clause stops: at a comma, before a
#: credit ("according to", "reports"), before a joining word once it has
#: two words. A label that still does not read as a description of the
#: figure is dropped — the card then shows the figure alone when its unit
#: explains it, or not at all. Measured on the last week of the three
#: flagships: "Of U .S", "% means claims are already", "Up 0.3% I'm
#: Patrick in Vancouver", "In the evening Central Time".
_LABEL_STOP_BEFORE = frozenset({
    "according", "reports", "reported", "report", "says", "said", "noted",
    "notes", "told", "writes", "wrote", "i'm", "via",
})
_LABEL_JOINERS = frozenset({
    "and", "but", "yet", "while", "which", "who", "whose", "that", "so",
    "because", "although", "though", "or", "as", "if", "when", "where",
})
_LABEL_BAD_START = frozenset({
    "of", "and", "or", "but", "yet", "so", "nor", "than", "to", "is", "are",
    "was", "were", "means", "mean", "had", "has", "have", "be", "been",
    "it", "its", "they", "this", "that", "which", "who", "a", "an",
    "according", "said", "says", "reports", "i'm", "won",
})
_TIME_WORDS = frozenset({
    "am", "pm", "a.m", "p.m", "a.m.", "p.m.", "evening", "morning",
    "afternoon", "tonight", "eastern", "pacific", "central",
})
_LABEL_MIN_WORDS = 2


def _label_words(words: Sequence[dict], run: dict) -> Tuple[List[str], bool]:
    """The words after the figure, cut where its clause ends, and whether
    the cut was a credit ("… Universe Today reports")."""
    after: List[str] = []
    if run["ended"]:
        return after, False
    k = run["idx_to"] + 1
    while k < len(words) and len(after) < _LABEL_WORDS:
        tok = _clean(words[k].get("word"))
        core = tok.rstrip(".,;:!?")
        low = core.lower()
        if low in _LABEL_STOP_BEFORE:
            return after, True
        if low in _LABEL_JOINERS and after:
            break
        after.append(core)
        if tok.endswith(_SENTENCE_END) or tok.endswith((",", ";", ":")):
            break
        k += 1
    return after, False


def _label_reads(label_words: Sequence[str]) -> bool:
    if not label_words:
        return False
    first = label_words[0].lower()
    if first in _LABEL_BAD_START or first in _LABEL_JOINERS:
        return False
    if first[:1].isdigit() or first[:1] in "%.,-":
        return False
    if any(w.lower().strip(".") in _TIME_WORDS for w in label_words[:3]):
        return False
    return True


def _before_words(words: Sequence[dict], run: dict) -> List[str]:
    """The words of the figure's own clause before it, for a figure that
    ends its sentence ("a record altitude of 150.")."""
    before: List[str] = []
    k = run["idx_from"] - 1
    while k >= 0 and len(before) < _LABEL_WORDS:
        tok = _clean(words[k].get("word"))
        core, ended = _strip_trailing_punct(tok)
        if ended or tok.endswith((",", ";", ":")):
            break
        before.insert(0, core)
        k -= 1
    return before


def _plural_noun(word: str) -> bool:
    low = word.lower()
    return (word.isalpha() and word[:1].islower() and len(word) > 3
            and low.endswith("s") and not low.endswith("ss")
            and low not in _LABEL_BAD_START and low not in _LABEL_JOINERS)


def _label_for(words: Sequence[dict], run: dict) -> Tuple[Optional[str], str]:
    """``(label, noun)`` for the run.

    *label* is the text under the figure, ``""`` for a figure that stands
    alone, or ``None`` when the card should not be shown at all. *noun* is
    a plural noun that joins the figure instead ("700 cars").
    """
    tail = _dangling_tail()
    if run["ended"]:
        before = _before_words(words, run)
        while before and before[-1].lower() in tail | _LABEL_JOINERS:
            before.pop()
        if len(before) >= _LABEL_MIN_WORDS and _label_reads(before):
            label = _fit_label(" ".join(before))
            if label:
                return label, ""
        after, credited = [], False
    else:
        after, credited = _label_words(words, run)
    while after and after[-1].lower() in tail | _LABEL_JOINERS:
        after.pop()
    # Words that run straight into a credit are the outlet's name.
    if credited and len(after) <= 3:
        after = []
    if len(after) >= _LABEL_MIN_WORDS and _label_reads(after):
        label = _fit_label(" ".join(after))
        if label:
            return label, ""
    # No label that reads: the figure may still stand alone when its unit
    # says what it counts ("$4.2 billion", "85%", "230 mph"), or when the
    # word after it is the thing counted ("700 cars").
    unit = run.get("unit_display") or run["unit"]
    figure = run["figure"]
    if unit or figure.startswith(("$", "€", "£")) or figure.endswith("%"):
        return "", ""
    nxt = _clean(words[run["idx_to"] + 1].get("word")) if run["idx_to"] + 1 < len(words) else ""
    noun, _ = _strip_trailing_punct(nxt)
    if _plural_noun(noun):
        return "", noun
    return None, ""


def extract_fact_cards(
    words: Sequence[dict],
    *,
    chapter_starts: Iterable[float] = (),
    max_cards: int = MAX_CARDS,
    min_gap_s: float = MIN_GAP_S,
    open_skip_s: float = OPEN_SKIP_S,
) -> List[FactCard]:
    """Pick up to *max_cards* spoken figures worth a card, sorted by time."""
    if not words:
        return []
    chapters = sorted(float(c) for c in chapter_starts or [] if c is not None)
    candidates: List[FactCard] = []
    for run in _merge_runs(words):
        if run["start"] < open_skip_s:
            continue
        if any(0.0 <= run["start"] - c < CHAPTER_CLEAR_S for c in chapters):
            continue
        score = _score(run["figure"], run["unit"], run["prev_word"])
        if score <= 0:
            continue
        figure = _display_figure(run["figure"], run.get("unit_display") or run["unit"])
        if run["prev_word"].lower() in ("v", "version") and run["figure"].count(".") > 1:
            figure = "v" + figure
        label, noun = _label_for(words, run)
        if label is None:
            continue
        if noun:
            figure = f"{figure} {noun}"
        candidates.append(FactCard(round(run["start"], 2), figure, label, score))
    candidates.sort(key=lambda c: (-c.score, c.start))
    picked: List[FactCard] = []
    for cand in candidates:
        if len(picked) >= max_cards:
            break
        if any(abs(cand.start - p.start) < min_gap_s for p in picked):
            continue
        picked.append(cand)
    picked.sort(key=lambda c: c.start)
    return picked


def _chapter_starts(chapters_path) -> List[float]:
    try:
        import json
        raw = json.loads(Path(chapters_path).read_text(encoding="utf-8"))
        chs = raw.get("chapters") if isinstance(raw, dict) else raw
        out = []
        for c in chs or []:
            if not isinstance(c, dict):
                continue
            s = c.get("startTime", c.get("start_time", c.get("start")))
            if s is not None:
                out.append(float(s))
        return out
    except Exception:  # noqa: BLE001
        return []


def fact_cards_for_episode(
    transcript_path, chapters_path=None, *, max_cards: int = MAX_CARDS,
) -> Optional[List[Tuple[float, str, str]]]:
    """Build the render-ready ``[(start, figure, label), …]`` for an episode.

    Returns ``None`` when there is no usable transcript (no words, no
    file) so the caller ships the legacy render; never raises.
    """
    try:
        if not transcript_path or not Path(transcript_path).exists():
            return None
        from engine.visual_reuse import load_transcript_words
        words = load_transcript_words(transcript_path)
        if not words:
            return None
        starts = _chapter_starts(chapters_path) if chapters_path else []
        cards = extract_fact_cards(words, chapter_starts=starts, max_cards=max_cards)
        return [c.as_tuple() for c in cards]
    except Exception as exc:  # noqa: BLE001 — cards are best-effort
        logger.warning("fact_cards: skipped (%s)", exc)
        return None


#: Shorts cards (Sep 22 2026): the 0-3 s hook overlay owns the open, so
#: a card may not start before this; the end card takes the tail.
SHORT_OPEN_SKIP_S = 3.5
SHORT_TAIL_CLEAR_S = 3.0
SHORT_MIN_GAP_S = 8.0
SHORT_MAX_CARDS = 2


def fact_cards_for_window(
    transcript_path,
    window_start: float,
    duration: float,
    *,
    max_cards: int = SHORT_MAX_CARDS,
    open_skip_s: float = SHORT_OPEN_SKIP_S,
    tail_clear_s: float = SHORT_TAIL_CLEAR_S,
    min_gap_s: float = SHORT_MIN_GAP_S,
) -> Optional[List[Tuple[float, str, str]]]:
    """Fact cards for ONE Shorts clip, on the clip's own t=0 timeline.

    *window_start* is the clip's start on the transcript's (voice-only)
    timeline — the caller has already removed the music-intro offset,
    exactly as it does for the Shorts captions. Cards start no earlier
    than *open_skip_s* into the clip and finish before the last
    *tail_clear_s* (the end card). Returns ``None`` on no usable
    transcript so the caller ships the legacy render; never raises.
    """
    try:
        if not transcript_path or not Path(transcript_path).exists():
            return None
        if not duration or float(duration) <= 0:
            return None
        from engine.visual_reuse import load_transcript_words
        words = load_transcript_words(transcript_path)
        if not words:
            return None
        start = float(window_start)
        end = start + float(duration)
        clip_words = []
        for w in words:
            try:
                ws = float(w["start"])
                we = float(w["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if ws < start or we > end:
                continue
            clip_words.append({**w, "start": ws - start, "end": we - start})
        if not clip_words:
            return None
        latest = float(duration) - tail_clear_s - FACT_CARD_SECONDS
        cards = extract_fact_cards(
            clip_words, max_cards=max_cards, min_gap_s=min_gap_s,
            open_skip_s=open_skip_s,
        )
        return [c.as_tuple() for c in cards if c.start <= latest]
    except Exception as exc:  # noqa: BLE001 — cards are best-effort
        logger.warning("fact_cards: Shorts window skipped (%s)", exc)
        return None
