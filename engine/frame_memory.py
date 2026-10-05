"""Rotation memory for sentence FRAMES (Sep 30 2026 network review).

What the operator hears as "repetition" is, on the numbers, not repeated
facts (``script_duplicate_sentences`` reads 0 on every episode of the
09-16..30 window) but repeated FRAMES: fixed openings that recur every
day with a different tail — "Before we go, keep an eye on…" (Fascinating
Frontiers 15/15, Planetterrian 13/15), "Before we wrap, watch for…"
(Modern Investing 11/15), "If you want to go deeper on X, compare how…"
(Omni View 15/15), "The case on both sides…" (every Mira desk 7/8),
"Tesla has not issued a public response on…" (Tesla 6/15).

The ledger record on this class is unambiguous: prompt-only de-seeds of
the same phrase families have missed on three to five consecutive reviews
per show (Fascinating Frontiers "Keep an eye on" ×5), while DATA-SIDE
rotation memory — the DP Pod lever memory, the Nerra Daily opener
memory, the network-promo rotation — hits. This module is that mechanism
applied to sentence openers on every show: it reads the show's own last
scripts, finds the openers that recur with different tails, and hands
the prompt a do-not-open-with list for today. Deterministic, no model
call, no new storage; the committed ``*_tts.txt`` files are the memory.

Rules that keep it honest:

* Furniture is not a frame. A sentence that recurs VERBATIM (the
  identity line, the closing, the network plug, the AI disclosure) is
  fixed text by design and is never listed.
* A chapter anchor is not a frame. The Counterpoint's "one thing worth
  watching" is how ``engine/chapters.py`` finds the chapter; a frame that
  matches any of the show's ``section_markers`` patterns is exempt.
* The list is a BAN, not a menu: it names what was used, never what to
  say instead (de-seed by shape — three generations of this network's
  tics came from prompts supplying the line they wanted).
* Fewer than three prior scripts, or nothing recurring: an empty string,
  so a young show's prompt is byte-identical to before.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

DEFAULT_WINDOW = 6          # scripts read
MIN_SCRIPTS = 3             # fewer than this: no memory
MIN_RECURRENCE = 3          # opener must open a sentence in this many scripts
FRAME_WORDS = 4             # words that make an opener
MAX_FRAMES = 8              # longest list the prompt gets
MIN_SENTENCE_WORDS = 6      # shorter sentences are not judged
FURNITURE_SHARE = 0.5       # verbatim in this share of scripts = fixed text

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9'’-]*")
_SPEAKER_RE = re.compile(r"^\s*[A-ZА-Я][A-Za-zА-Яа-я .'-]{0,30}:\s*")
_TAG_RE = re.compile(r"\[[a-z-]+\]|</?[a-z-]+>")


def _sentences(text: str) -> List[str]:
    out: List[str] = []
    for line in (text or "").splitlines():
        line = _SPEAKER_RE.sub("", line)
        line = _TAG_RE.sub(" ", line)
        for sent in _SENT_SPLIT_RE.split(" ".join(line.split())):
            sent = sent.strip()
            if sent:
                out.append(sent)
    return out


def _norm(text: str) -> str:
    return " ".join(w.lower() for w in _WORD_RE.findall(text or ""))


def _opener(sentence: str, words: int = FRAME_WORDS) -> str:
    """The sentence's first *words* words, lowercased — or ``""`` when the
    opener is CONTENT rather than a frame: a proper noun after the first
    word, a digit, or a spelled-out ticker/acronym ("T S L A closed at",
    "the S P 500 finished", "Nikkei Asia reports") is a fact the show must
    say every day, not a habit to rotate out of."""
    toks = _WORD_RE.findall(sentence)
    if len(toks) < MIN_SENTENCE_WORDS:
        return ""
    head = toks[:words]
    for i, t in enumerate(head):
        if any(ch.isdigit() for ch in t):
            return ""
        if len(t) == 1 and t.isalpha() and t.isupper():
            return ""
        if i > 0 and t[:1].isupper():
            return ""
    return " ".join(t.lower() for t in head)


def script_paths(output_dir: Path, window: int = DEFAULT_WINDOW,
                 exclude_contains: str = "") -> List[Path]:
    """The show's most recent ``*_tts.txt`` scripts, oldest first. A rerun
    of today's episode passes its own ``Ep123_`` tag so it never reads
    itself as history."""
    paths = sorted(Path(output_dir).glob("*_tts.txt"))
    if exclude_contains:
        paths = [p for p in paths if exclude_contains not in p.name]
    return paths[-window:]


def recurring_frames(
    scripts: Sequence[str],
    *,
    min_recurrence: int = MIN_RECURRENCE,
    exempt_patterns: Iterable[str] = (),
    max_frames: int = MAX_FRAMES,
) -> List[Tuple[str, int, str]]:
    """``[(opener, scripts_it_opened_a_sentence_in, example_sentence)]``
    for the openers that recur across *scripts* with DIFFERENT tails,
    most frequent first. Furniture (verbatim-recurring sentences) and
    chapter anchors (*exempt_patterns*) are left out."""
    if len(scripts) < MIN_SCRIPTS:
        return []
    n = len(scripts)
    sentence_scripts: Dict[str, set] = defaultdict(set)
    per_script: List[List[str]] = []
    for idx, text in enumerate(scripts):
        sents = _sentences(text)
        per_script.append(sents)
        for s in sents:
            sentence_scripts[_norm(s)].add(idx)
    furniture = {k for k, v in sentence_scripts.items() if len(v) >= max(2, FURNITURE_SHARE * n)}

    opener_scripts: Dict[str, set] = defaultdict(set)
    opener_tails: Dict[str, set] = defaultdict(set)
    example: Dict[str, str] = {}
    for idx, sents in enumerate(per_script):
        for s in sents:
            if _norm(s) in furniture:
                continue
            op = _opener(s)
            if not op:
                continue
            opener_scripts[op].add(idx)
            opener_tails[op].add(_norm(s))
            example[op] = s  # the most recent script's sentence wins
    exempt = [re.compile(p, re.I) for p in exempt_patterns if p]
    found: List[Tuple[str, int, str]] = []
    for op, idxs in opener_scripts.items():
        if len(idxs) < min_recurrence or len(opener_tails[op]) < 2:
            continue
        if any(rx.search(op) or rx.search(example[op]) for rx in exempt):
            continue
        found.append((op, len(idxs), example[op]))
    found.sort(key=lambda t: (-t[1], t[0]))
    return found[:max_frames]


def _exempt_patterns_for(config: Any) -> List[str]:
    chapters = getattr(config, "chapters", None)
    markers = getattr(chapters, "section_markers", None) or []
    out: List[str] = []
    for m in markers:
        pat = getattr(m, "pattern", None) or (m.get("pattern") if isinstance(m, dict) else None)
        if pat:
            out.append(str(pat))
    return out


def _config_output_dir(config: Any) -> str:
    """The show's episode directory, from a real ``ShowConfig`` (``episode.output_dir``)
    or a flat ``output_dir`` on a test double; ``""`` when neither exists."""
    episode = getattr(config, "episode", None)
    nested = getattr(episode, "output_dir", "") if episode is not None else ""
    return str(nested or getattr(config, "output_dir", "") or "")


def build_recent_frames_block(
    config: Any,
    *,
    output_dir: Optional[Path] = None,
    window: int = DEFAULT_WINDOW,
    exclude_contains: str = "",
) -> str:
    """The prompt block for today, or ``""`` when there is nothing to ban.

    Best-effort: any failure returns ``""`` (the prompt is then what it
    was before this module existed)."""
    try:
        # The real ShowConfig keeps the directory on ``config.episode``;
        # the flat attribute is only what a bare test double has. Sep 30
        # 2026 shipped reading the flat one, so the block rendered "" on
        # every opted-in show for a day (caught by the post-merge readout).
        out_dir = Path(output_dir or _config_output_dir(config) or "")
        if not out_dir or not out_dir.exists():
            return ""
        paths = script_paths(out_dir, window=window, exclude_contains=exclude_contains)
        scripts = [p.read_text(encoding="utf-8", errors="ignore") for p in paths]
        frames = recurring_frames(scripts, exempt_patterns=_exempt_patterns_for(config))
        if not frames:
            return ""
        lines = [
            "ROTATION MEMORY — sentence openers this show has leaned on across "
            f"its last {len(scripts)} episodes. Do not open ANY sentence with "
            "these words today; find a different way into the point (a fact, a "
            "name, a number), never a re-skin of the same opener:",
        ]
        for op, count, _ in frames:
            lines.append(f"- \"{op} …\" (opened a sentence in {count} of the last {len(scripts)} scripts)")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001 — never block a run
        logger.warning("frame memory failed (non-fatal): %s", exc)
        return ""


__all__ = [
    "DEFAULT_WINDOW", "MIN_SCRIPTS", "MIN_RECURRENCE", "FRAME_WORDS", "MAX_FRAMES",
    "script_paths", "recurring_frames", "build_recent_frames_block",
]
