"""Long-form video cards that follow the audio (Nov 8 2026).

Two render-only additions to the 16:9 long-form, both read from what the
episode already says. Nothing here changes a word of the audio.

1. **The "Coming up" card.** Every English episode since Oct 20 opens: hook,
   identity line, then THE MAP, one sentence listing the stories that follow
   ("Heat-shield data from the latest orbital reentry, jet generators in
   Mississippi, then the Counterpoint and an engineering deep dive."). It
   sits at about 8-20 s, and that is where the long-forms lose their viewers:
   across the 74 EN long-forms with a retention curve on Nov 7, the median
   holds 91% at 6 s, 57% at 20 s and 42% at 30 s. On screen during the map
   there was only the scene picture (the hook title is gone at 4 s). The card
   puts the map's own stories on screen as a list, each line appearing as it
   is spoken, so a viewer deciding whether to stay can SEE what is coming.

   The items are the map sentence's own words, from the display copy of the
   script (``*_reader.txt``, before pronunciation respellings: "SpaceX", not
   "Space X"), split at its list commas and "then". The card is shown only
   when every item reads as an item: 2-5 of them, each of two or more words
   (one word only if it is a capitalised section name such as "Spotlight"),
   none opening on a pronoun, each fitting ``engine.titles.RUNDOWN_ITEM_MAX``
   whole. Anything else, and any failure, renders the video as before: an
   item is never clipped and a card is never guessed.

   Timing comes from :func:`engine.short_furniture.map_cut` (the Whisper
   words of the committed ``_tts.txt``), the same locator the hook Short uses
   to cut the map out, so the card and the spoken map share one clock.

2. **The long-form subscribe pill.** The long-forms are where the channel's
   subscribers come from (Oct 7 - Nov 5: 27 subscribers from long-forms
   against 5 from Shorts) and the only ask in the picture was the outro card
   in the last seconds, which ~95% of viewers never reach (median retention
   8% at 5 min). The Shorts carry a persistent pill since Oct 25; the long
   form now shows the same "Subscribe · <cadence> episodes" pill twice, for
   :data:`SUBSCRIBE_PILL_SECONDS`, at :data:`SUBSCRIBE_FIRST_AT_S` and at the
   episode's midpoint, never inside the map or the outro.

Both are YAML switches (``youtube.long_form_rundown_card`` and
``youtube.long_form_subscribe_pill``, off in the dataclass, on in
``_defaults.yaml``); off is byte-identical. The dubbed long-forms do not pass
either and are the control.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

#: Fewest / most map items a card shows.
RUNDOWN_MIN_ITEMS = 2
RUNDOWN_MAX_ITEMS = 6
#: Words per item: a map item is a phrase, not a sentence.
RUNDOWN_ITEM_MAX_WORDS = 11
#: The card stays this long after the map's last word (into the pause
#: before the first story), then fades.
RUNDOWN_HOLD_S = 1.0
#: Fade in / out of each line and of the card.
RUNDOWN_FADE_S = 0.25
#: The card never starts before the hook title has gone (it ends at 4 s).
RUNDOWN_MIN_START_S = 4.5
#: The label above the items. The map lists what comes AFTER the lead.
RUNDOWN_LABEL = "COMING UP"

#: The long-form subscribe pill.
SUBSCRIBE_PILL_SECONDS = 8.0
SUBSCRIBE_FIRST_AT_S = 45.0
#: Neither window may come closer than this to the end of the episode
#: (the outro card asks there).
SUBSCRIBE_TAIL_CLEAR_S = 30.0
#: Episodes shorter than this get only the first window.
SUBSCRIBE_SECOND_MIN_EPISODE_S = 180.0

_LEAD_IN_RE = re.compile(
    r"^(?:after (?:that|this)|from (?:there|here)|next)\b[,:]?\s*"
    r"(?:(?:comes?|come next|we look at|the hour moves to|the hour turns to)\s+)?",
    re.IGNORECASE)
#: A first comma segment that only points back at the lead ("After the
#: polar craters", "After that foundry calendar").
_BACK_POINTER_RE = re.compile(r"^after\s+(?:the|that|this|we)\b[^,]*$", re.IGNORECASE)
#: Splits inside a comma segment.
_SEQUENCE_SPLIT_RE = re.compile(
    r"\s+(?:and then|then|and later|later|plus|along with)\s+", re.IGNORECASE)
_ITEM_PREFIX_RE = re.compile(
    r"^(?:(?:and then|and later|then|and|plus|later|with|along with|also|first)\s+)+",
    re.IGNORECASE)
_ITEM_SUFFIX_RE = re.compile(
    r"\s+(?:(?:comes?|follows?)(?: next| later| after [\w'’ ]+| from there)?|"
    r"(?:are|is) up(?: after the lead)?|"
    r"later|first|after (?:that|this)|at the end|from there)$",
    re.IGNORECASE)
#: A map that narrates the host's own moves ("we screen ..., walk ...")
#: lists verbs, not stories.
_FIRST_PERSON_RE = re.compile(r"\b(?:we|we'll|we’ll|we're|we’re|I'll|I’ll)\b", re.IGNORECASE)
_PRONOUN_START_RE = re.compile(
    r"^(?:we|we'll|we’ll|i|you|it|they|she|he|this|that|there|"
    r"after|before|through|into|the path)\b", re.IGNORECASE)
_TRAILING_PUNCT = " \t.,;:!?—–-"


def rundown_items(map_text: str) -> Optional[List[Tuple[str, int]]]:
    """``[(item, char_offset), ...]`` for a map sentence, or ``None``.

    *char_offset* is where the item starts in *map_text* (for timing each
    line to the moment it is spoken). ``None`` whenever any item fails the
    gates in the module docstring: a card is shown whole or not at all.
    """
    from engine.titles import RUNDOWN_ITEM_MAX, fits

    text = (map_text or "").strip()
    if not text:
        return None
    # Segment by commas (and an em dash used as a list break), keeping
    # each segment's offset into the original sentence.
    segments: List[Tuple[str, int]] = []
    for m in re.finditer(r"[^,—;]+", text):
        seg = m.group(0)
        if seg.strip():
            segments.append((seg, m.start()))
    if not segments:
        return None
    if _FIRST_PERSON_RE.search(segments[0][0]):
        return None
    # A first segment that only points back at the lead is not an item.
    first, first_off = segments[0]
    if _BACK_POINTER_RE.match(first.strip()):
        segments = segments[1:]
    else:
        stripped = _LEAD_IN_RE.sub("", first.lstrip())
        if stripped != first.lstrip():
            lead = len(first) - len(first.lstrip()) + (len(first.lstrip()) - len(stripped))
            segments[0] = (stripped, first_off + lead)
    pieces: List[Tuple[str, int]] = []
    for seg, off in segments:
        pos = 0
        for part in _SEQUENCE_SPLIT_RE.split(seg):
            idx = seg.find(part, pos)
            pos = idx + len(part) if idx >= 0 else pos
            pieces.append((part, off + max(idx, 0)))
    items: List[Tuple[str, int]] = []
    for raw, off in pieces:
        lead_ws = len(raw) - len(raw.lstrip())
        item = raw.strip()
        before = len(item)
        item = _ITEM_PREFIX_RE.sub("", item)
        off += lead_ws + (before - len(item))
        prev = None
        while prev != item:
            prev = item
            item = _ITEM_SUFFIX_RE.sub("", item.strip(_TRAILING_PUNCT)).strip(_TRAILING_PUNCT)
        item = _ITEM_PREFIX_RE.sub("", item).strip(_TRAILING_PUNCT)
        if not item:
            continue
        words = item.split()
        if len(words) > RUNDOWN_ITEM_MAX_WORDS:
            return None
        if len(words) == 1 and not item[:1].isupper():
            return None
        if _PRONOUN_START_RE.match(item):
            return None
        if not item[:1].isalnum():
            return None
        first_word = words[0]
        # "xAI", "iPhone", "eVTOL" keep their own case.
        if first_word[:1].islower() and first_word[1:] == first_word[1:].lower():
            item = item[:1].upper() + item[1:]
        if not fits(item, RUNDOWN_ITEM_MAX):
            return None
        items.append((item, off))
    if not (RUNDOWN_MIN_ITEMS <= len(items) <= RUNDOWN_MAX_ITEMS):
        return None
    # A one-word item is a section name ("Spotlight", "Sports"), and those
    # close a map; one-word items in the middle are a list of places or
    # subjects the commas broke apart ("Finland, Ontario, two power ...").
    for i, (item, _off) in enumerate(items[:-2]):
        if len(item.split()) == 1:
            return None
    return items


@dataclass(frozen=True)
class RundownCard:
    """Render-ready card on the VIDEO timeline (voice offset applied)."""

    start: float
    end: float
    label: str
    #: ``[(appear_at, text), ...]``, in spoken order.
    items: Tuple[Tuple[float, str], ...]

    def as_tuple(self):
        return (self.start, self.end, self.label, list(self.items))


def _map_text(script_text: str, rng: Tuple[int, int]) -> str:
    from engine import story_breaks as sb

    lines = sb.script_lines(script_text)
    first, after = rng
    return " ".join(ln.strip() for ln in lines[first:after]).strip()


def rundown_card(tts_script: str, reader_script: str, transcript: dict, *,
                 audio_offset: float = 0.0) -> Optional[RundownCard]:
    """The "Coming up" card for an episode, or ``None``.

    *tts_script* is the committed ``_tts.txt`` (what Whisper heard),
    *reader_script* its display copy (``_reader.txt``), *transcript* the
    Whisper JSON on the voice timeline, *audio_offset* where the voice sits
    in the mix (``voice_intro_delay``). Never raises.
    """
    try:
        from engine import short_furniture as sf

        rng = sf.map_line_range(tts_script or "")
        if rng is None or sf.map_line_range(reader_script or "") != rng:
            return None
        cut = sf.map_cut(tts_script, transcript)
        if cut is None:
            return None
        spoken = _map_text(reader_script, rng)
        items = rundown_items(spoken)
        if not items:
            return None
        cut_from, cut_to = (float(cut[0]) + audio_offset,
                            float(cut[1]) + audio_offset)
        start = max(cut_from, RUNDOWN_MIN_START_S + audio_offset)
        span = max(cut_to - start, 0.5)
        total = max(len(spoken), 1)
        timed = []
        for text, off in items:
            at = start + span * (off / total)
            timed.append((round(max(at, start), 2), text))
        end = round(cut_to + RUNDOWN_HOLD_S, 2)
        if end - start < 2.0:
            return None
        return RundownCard(start=round(start, 2), end=end, label=RUNDOWN_LABEL,
                           items=tuple(timed))
    except Exception as exc:  # noqa: BLE001 — never block a render
        logger.warning("Rundown card skipped: %s", exc)
        return None


def rundown_card_for_episode(transcript_path, *, audio_offset: float = 0.0
                             ) -> Optional[RundownCard]:
    """Load the three committed files beside *transcript_path*; ``None`` if
    any is missing."""
    try:
        import json

        tp = Path(transcript_path)
        if not tp.name.endswith("_transcript.json") or not tp.exists():
            return None
        stem = tp.name[: -len("_transcript.json")]
        tts = tp.with_name(stem + "_tts.txt")
        reader = tp.with_name(stem + "_reader.txt")
        if not (tts.exists() and reader.exists()):
            return None
        return rundown_card(tts.read_text(encoding="utf-8"),
                            reader.read_text(encoding="utf-8"),
                            json.loads(tp.read_text(encoding="utf-8")),
                            audio_offset=audio_offset)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rundown card skipped: %s", exc)
        return None


def subscribe_windows(episode_s: float, *,
                      avoid: Sequence[Tuple[float, float]] = ()
                      ) -> List[Tuple[float, float]]:
    """``[(start, end), ...]`` for the long-form subscribe pill.

    The first at :data:`SUBSCRIBE_FIRST_AT_S`, the second at the midpoint of
    episodes over :data:`SUBSCRIBE_SECOND_MIN_EPISODE_S`. A window that would
    overlap one in *avoid* (the rundown card) moves to just after it; one
    that would reach the last :data:`SUBSCRIBE_TAIL_CLEAR_S` is dropped.
    """
    try:
        total = float(episode_s or 0.0)
    except (TypeError, ValueError):
        return []
    if total <= 0:
        return []
    starts = [SUBSCRIBE_FIRST_AT_S]
    if total >= SUBSCRIBE_SECOND_MIN_EPISODE_S:
        starts.append(round(total / 2.0, 2))
    out: List[Tuple[float, float]] = []
    for s in starts:
        for a, b in avoid:
            if s < b and s + SUBSCRIBE_PILL_SECONDS > a:
                s = b + 1.0
        e = s + SUBSCRIBE_PILL_SECONDS
        if e > total - SUBSCRIBE_TAIL_CLEAR_S:
            continue
        if out and s < out[-1][1] + SUBSCRIBE_PILL_SECONDS:
            continue
        out.append((round(s, 2), round(e, 2)))
    return out
