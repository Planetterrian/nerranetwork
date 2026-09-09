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
_CONT_RE = re.compile(r"^(?:[.,]\d+|,\d{3})%?[.,;:!?]*$")
_SENTENCE_END = (".", "!", "?")
_UNIT_WORDS = {
    "million": "million", "billion": "billion", "trillion": "trillion",
    "thousand": "thousand", "percent": "%", "per cent": "%",
    "dollars": "$",
}
_YEAR_RE = re.compile(r"^(?:19|20)\d\d$")
_EPISODE_WORDS = frozenset({"episode", "ep", "ep.", "number"})


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
    # Whisper splits "$14.08" into "$14" ".8": re-join figures in labels.
    text = re.sub(r"(\d) ([.,]\d)", r"\1\2", text)
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
        prev_word = _clean(words[i - 1].get("word")) if i > 0 else ""
        out.append({
            "start": start, "figure": figure, "unit": unit,
            "idx_from": i, "idx_to": j, "prev_word": prev_word,
            "ended": ended,
        })
        i = j + 1
    return out


def _display_figure(figure: str, unit: str) -> str:
    if unit == "%":
        return figure if figure.endswith("%") else figure + "%"
    if unit == "$":
        return figure if figure.startswith("$") else "$" + figure
    if unit:
        return f"{figure} {unit}"
    return figure


def _label_for(words: Sequence[dict], run: dict) -> str:
    after: List[str] = []
    k = run["idx_to"] + 1
    if not run["ended"]:
        while k < len(words) and len(after) < _LABEL_WORDS:
            tok = _clean(words[k].get("word"))
            core, ended = _strip_trailing_punct(tok)
            after.append(core)
            if ended:
                break
            k += 1
    label = _fit_label(" ".join(after))
    if label:
        return label
    before: List[str] = []
    k = run["idx_from"] - 1
    while k >= 0 and len(before) < _LABEL_WORDS:
        tok = _clean(words[k].get("word"))
        core, ended = _strip_trailing_punct(tok)
        if ended:
            break
        before.insert(0, core)
        k -= 1
    return _fit_label(" ".join(before))


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
        figure = _display_figure(run["figure"], run["unit"])
        if run["prev_word"].lower() in ("v", "version") and run["figure"].count(".") > 1:
            figure = "v" + figure
        label = _label_for(words, run)
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
