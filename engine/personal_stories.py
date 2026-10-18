"""Nerra Personal — what an edition contains, what this listener already
heard, and where an edition may be trimmed (Oct 18 2026).

Everything here is deterministic and runs on material the builder already
holds: the shows' committed digests, chapter files and Whisper
transcripts, the member's own ``episodes.json`` state in R2, and one
``ffmpeg silencedetect`` pass per show per day over the cached segment.
**No module here makes a model or search call** — the operator's cost
rule for this pass (no new LLM or web-search call per member per day).
What Mira does with the results rides the ONE existing links call.

Five things, in the order the builder uses them:

* **Stories per segment** (:func:`segment_stories`) — the episode's hook,
  its digest headlines, its own chapter list (``chapters_epNNN.json`` beside
  the digest, on the published MP3's timeline) classified as furniture /
  headline / section, the digest's story units, and the Whisper transcript.
* **Edition memory** (:func:`edition_contents`, :func:`memory_notes`,
  :func:`week_threads`) — a compact record of each edition (show, episode,
  hook, up to eight headlines) kept on the member's state row, matched
  against today's stories so Mira can frame a story as an update instead of
  news the listener has not heard.
* **Repeats across the member's own shows** (:func:`cross_repeats`) — a
  later segment retelling a story an earlier one told today.
* **Trims** (:func:`plan_repeat_cuts`, :func:`plan_length_cuts`, both
  through :func:`check_chapter_cut`) — a cut is always a whole show chapter,
  both edges in a pause and between two sentences, never the lead story, the
  cold open, the segment's last chapter or the sign-off, never on a
  members-only episode (its full version is in no public feed). A repeat cut
  additionally needs a strong match and a chapter the transcript shows is
  ONE story. Anything that fails a rule is not cut — Mira just mentions it.
* **Interest highlights** (:func:`interest_highlights`) — the member's topics
  and profile keywords against today's chapter titles and headlines.

Matcher calibration (committed digests, 2026-10-04 → 10-17, every pair of
shows choosable on the same day, see ``docs/nerra_personal.md``): headline
pairs sharing >= 4 salient tokens (after the pool's common tokens and the
spoken-number words are removed) were the same story in every pair read;
3 shared tokens over 60% of the smaller headline were too; 3 over 40-60%
mixed true pairs with different stories that share a phrase ("linked to
higher … risk"), so those need the two digest bodies to agree; 2 were
mostly noise. A CUT needs 4 tokens over 50% plus body agreement >= 0.25.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from engine.story_breaks import _tokens as _unit_tokens
from engine.story_breaks import story_units
from engine.story_recurrence import salient_tokens as _salient
from engine.titles import HEADLINE_CHAPTER_TITLE_MAX, SPOKEN_HOOK_MAX_CHARS, clip_words

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds (calibrated — see the module docstring and docs/nerra_personal.md)
# ---------------------------------------------------------------------------

#: A story the listener should hear named as a repeat / an update: four
#: shared salient tokens over 40% of the smaller headline, or three over
#: 60% (three at 40-60% mixed true pairs with different stories that share
#: a phrase — those count only when the two digest bodies agree too).
MENTION_MIN_OVERLAP = 3
MENTION_MIN_FRACTION = 0.4
MENTION_STRICT_OVERLAP = 4
MENTION_LOOSE_FRACTION = 0.6
MENTION_BODY_SHARE = 0.30
#: A story strong enough to cut a later telling of it.
CUT_MIN_OVERLAP = 4
CUT_MIN_FRACTION = 0.5
#: The two digests' story bodies must agree too (shared salient vocabulary
#: over the smaller body) before a telling is cut.
CUT_MIN_BODY_SHARE = 0.25
#: Share of a chapter's spoken words that must belong to its own story for
#: the chapter to count as ONE story (Tesla's chapters often start late and
#: carry the next, unchaptered item — those chapters are never cut).
CUT_MIN_PURITY = 0.7
#: A cut point must fall inside a pause this close to the chapter boundary
#: (seconds) — never between two words of a sentence. A pause is either a
#: real silence (ffmpeg silencedetect, as engine.story_breaks measures it)
#: or the story-break pause itself: since Oct 14 2026 music shows lay a
#: swell of their theme under every story-break pause (measured at about
#: -21 dB RMS on Models & Agents Ep203 — silencedetect never sees it), so a
#: Whisper word gap of at least STORY_PAUSE_MIN_SECONDS that ends a
#: sentence counts too; ordinary sentence gaps measured 0.5-0.75 s, the
#: story-break pauses 0.8-1.1 s. Every join is rendered with a short fade.
SNAP_TOLERANCE_SECONDS = 1.5
CUT_SILENCE_NOISE_DB = -40.0
CUT_SILENCE_MIN_SECONDS = 0.25
STORY_PAUSE_MIN_SECONDS = 0.8
JOIN_FADE_SECONDS = 0.04
#: A pool token in at least this share of the texts in play carries no
#: signal ("tesla" on a day with four Tesla shows) — and in at least
#: COMMON_MIN_COUNT of them: a member's lineup is a small pool, and the
#: story two of their shows both tell (the very thing being matched) puts
#: its own words in four texts — hook plus headline, twice.
COMMON_DF = 0.05
COMMON_MIN_POOL = 20
COMMON_MIN_COUNT = 5

#: State caps — the memory lives in the member's R2 episodes.json.
MEMORY_EDITIONS = 7
MEMORY_STORIES_PER_SEGMENT = 8
MEMORY_SEGMENTS_MAX = 30
MAX_MEMORY_NOTES = 6
MAX_REPEAT_NOTES = 6
MAX_WEEK_THREADS = 4
MAX_HIGHLIGHTS = 3
#: A thread is worth naming on Sunday when it ran on this many distinct days.
WEEK_THREAD_MIN_DAYS = 3

#: Mira's speaking rate for the length estimate before her pieces exist
#: (words per second, measured on her published handoffs) and the sizes the
#: links prompt asks for.
MIRA_WORDS_PER_SECOND = 2.6
MIRA_PIECE_PAD_SECONDS = 0.8

#: A spoken number word or a generic headline word never makes two
#: headlines the same story (calibration: "seven", "billion", "more than").
_EXTRA_STOP = frozenset("""
one two three four five six seven eight nine ten eleven twelve thirteen
fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty
fifty sixty seventy eighty ninety hundred thousand million billion trillion
percent per cent more than less may first last year years day days week
weeks month now just still before over under amid calls live news could
would should can people also new latest set sets gets get make makes
000 dollars dollar
""".split())

_FURNITURE = frozenset({
    "introduction", "intro", "closing", "sign-off", "sign off", "signoff",
    "cold open", "tomorrow teaser", "teaser", "outro", "welcome",
    "завершение", "прощание", "введение",
})

_NORM_RE = re.compile(r"[^a-z0-9а-яё]+")


def _norm(text: str) -> str:
    return _NORM_RE.sub(" ", (text or "").lower()).strip()


def story_tokens(text: str) -> frozenset:
    """Salient tokens of a headline: the story-recurrence tokenizer minus
    spoken numbers and generic headline words. Short pure digits ("1",
    "36") are dropped too — a count is not a story."""
    return frozenset(
        t for t in _salient(text)
        if t not in _EXTRA_STOP and not (t.isdigit() and len(t) < 4))


# ---------------------------------------------------------------------------
# Stories per segment
# ---------------------------------------------------------------------------

@dataclass
class ShowChapter:
    """One of the show's own chapters, on the segment's timeline."""

    title: str
    start: float
    end: float
    kind: str            # "furniture" | "headline" | "section"
    lead: bool = False   # the first body chapter: never cut


@dataclass
class SegmentStories:
    slug: str
    show_name: str
    episode_num: int
    hook: str
    headlines: List[str]
    chapters: List[ShowChapter]
    units: list = field(default_factory=list)
    transcript: Optional[dict] = None
    private: bool = False
    full_episode_url: str = ""
    #: Segment length after the promo trim (seconds) — the cached file.
    duration: float = 0.0

    def texts(self) -> List[str]:
        """Every story text of the segment: hook, headlines, headline
        chapters (deduped, document order)."""
        out: List[str] = []
        seen = set()
        for t in [self.hook] + list(self.headlines) + [
                c.title for c in self.chapters if c.kind == "headline"]:
            k = _norm(t)
            if t and k and k not in seen:
                seen.add(k)
                out.append(t)
        return out

    def body_chapters(self) -> List[ShowChapter]:
        return [c for c in self.chapters if c.kind != "furniture"]


def chapters_path(digest_dir: Path, episode_num: int) -> Path:
    """``chapters_epNNN.json`` beside the digest (members episodes keep
    theirs in ``members/`` — the digest dir the segment already carries)."""
    return Path(digest_dir) / f"chapters_ep{int(episode_num):03d}.json"


def load_show_chapters(digest_dir: Path, episode_num: int) -> List[dict]:
    path = chapters_path(digest_dir, episode_num)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = data.get("chapters") if isinstance(data, dict) else None
    out = []
    for r in rows or []:
        try:
            out.append({"title": str(r.get("title") or "").strip(),
                        "start": float(r["startTime"]),
                        "end": float(r.get("endTime") or 0.0)})
        except (KeyError, TypeError, ValueError):
            continue
    return [r for r in out if r["title"]]


def _is_headline(title: str, headlines: Sequence[str]) -> bool:
    """A chapter is a single-story headline chapter when its title is one
    of the digest's story headlines (the chapter writer uses the headline
    whole, or clipped at the chapter budget)."""
    nt = _norm(title)
    if len(nt) < 12:
        return False
    for h in headlines:
        nh = _norm(h)
        if nt == nh or (len(nt) >= 24 and (nh.startswith(nt) or nt.startswith(nh))):
            return True
    return False


def classify_chapters(raw: List[dict], headlines: Sequence[str],
                      cut_seconds: Optional[float] = None) -> List[ShowChapter]:
    """The show's chapters, clipped at the promo cut (a chapter starting
    after it is gone with the cut audio), each classified."""
    out: List[ShowChapter] = []
    rows = sorted(raw, key=lambda r: r["start"])
    for i, r in enumerate(rows):
        start = r["start"]
        end = rows[i + 1]["start"] if i + 1 < len(rows) else (r["end"] or start)
        if cut_seconds is not None:
            if start >= cut_seconds:
                break
            end = min(end, cut_seconds)
        if end <= start:
            continue
        title = r["title"]
        if _norm(title) in _FURNITURE:
            kind = "furniture"
        elif _is_headline(title, headlines):
            kind = "headline"
        else:
            kind = "section"
        out.append(ShowChapter(title=title, start=start, end=end, kind=kind))
    for c in out:
        if c.kind != "furniture":
            c.lead = True
            break
    return out


def segment_stories(seg, root: Path, *, cut_seconds: Optional[float] = None,
                    duration: float = 0.0, transcript: Optional[dict] = None,
                    private: bool = False) -> SegmentStories:
    """Everything the personalization layer needs about one segment."""
    from engine.grok_imagine import extract_story_headlines

    headlines = extract_story_headlines(seg.content or "", max_count=24)
    chapters = classify_chapters(
        load_show_chapters(seg.digest_dir, seg.episode_num), headlines,
        cut_seconds)
    try:
        units = story_units(seg.content or "")
    except Exception:  # noqa: BLE001 — a parse failure only disables cuts
        units = []
    url = ""
    if not private:
        blog = Path(root) / "blog" / seg.slug / f"ep{int(seg.episode_num):03d}.html"
        url = (f"https://nerranetwork.com/blog/{seg.slug}/ep{int(seg.episode_num):03d}.html"
               if blog.exists() else str(seg.audio_url or ""))
    return SegmentStories(
        slug=seg.slug, show_name=seg.show_name, episode_num=int(seg.episode_num),
        hook=seg.hook or "", headlines=headlines, chapters=chapters,
        units=units, transcript=transcript, private=private,
        full_episode_url=url, duration=float(duration or 0.0))


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------

class StoryMatcher:
    """Salient-token overlap with a day-pool common-token filter — the
    story-recurrence approach, scoped to the texts in play."""

    def __init__(self, pool: Iterable[str]):
        sets = [story_tokens(t) for t in pool if t]
        df: Dict[str, int] = {}
        for s in sets:
            for t in s:
                df[t] = df.get(t, 0) + 1
        n = len(sets)
        self.common = frozenset(
            t for t, c in df.items()
            if n >= COMMON_MIN_POOL and c / n >= COMMON_DF and c >= COMMON_MIN_COUNT)

    def tokens(self, text: str) -> frozenset:
        return story_tokens(text) - self.common

    def score(self, a: str, b: str) -> Tuple[int, float]:
        ta, tb = self.tokens(a), self.tokens(b)
        if not ta or not tb:
            return 0, 0.0
        ov = len(ta & tb)
        return ov, ov / min(len(ta), len(tb))

    def same(self, a: str, b: str, *, strong: bool = False) -> bool:
        ov, frac = self.score(a, b)
        if strong:
            return ov >= CUT_MIN_OVERLAP and frac >= CUT_MIN_FRACTION
        return mention_level(ov, frac)


def mention_level(overlap: int, fraction: float, body: Optional[float] = None) -> bool:
    """The mention rule (see the thresholds above). *body* — the two digest
    bodies' shared share — rescues a three-token pair under 60%."""
    if fraction < MENTION_MIN_FRACTION or overlap < MENTION_MIN_OVERLAP:
        return False
    if overlap >= MENTION_STRICT_OVERLAP or fraction >= MENTION_LOOSE_FRACTION:
        return True
    return body is not None and body >= MENTION_BODY_SHARE


def _unit_for(text: str, units: Sequence) -> Optional[object]:
    """The digest story unit a headline belongs to (most shared tokens,
    at least two)."""
    toks = _unit_tokens(text)
    best, best_ov = None, 1
    for u in units:
        ov = len(toks & u.tokens)
        if ov > best_ov:
            best, best_ov = u, ov
    return best


def body_share(a_text: str, a_units: Sequence, b_text: str,
               b_units: Sequence) -> float:
    """Shared vocabulary of the two digests' story bodies over the
    smaller one (0 when either headline has no body)."""
    ua, ub = _unit_for(a_text, a_units), _unit_for(b_text, b_units)
    if ua is None or ub is None:
        return 0.0
    small = min(len(ua.tokens), len(ub.tokens))
    return len(ua.tokens & ub.tokens) / small if small else 0.0


# ---------------------------------------------------------------------------
# Edition memory
# ---------------------------------------------------------------------------

def edition_contents(stories: Sequence[SegmentStories]) -> List[dict]:
    """The compact record of one edition kept on the member's state row:
    show, episode, hook and up to eight headlines per segment. Public
    episode text only — nothing about the listener."""
    out = []
    for s in list(stories)[:MEMORY_SEGMENTS_MAX]:
        heads = [clip_words(h, HEADLINE_CHAPTER_TITLE_MAX)
                 for h in s.headlines if _norm(h) != _norm(s.hook)]
        out.append({
            "slug": s.slug, "show": s.show_name, "ep": s.episode_num,
            "hook": clip_words(s.hook, SPOKEN_HOOK_MAX_CHARS),
            "stories": heads[:MEMORY_STORIES_PER_SEGMENT],
        })
    return out


def _row_texts(row: dict) -> List[Tuple[str, str]]:
    """(show name, story text) for every story a past edition carried."""
    out = []
    for c in row.get("contents") or []:
        if not isinstance(c, dict):
            continue
        show = str(c.get("show") or c.get("slug") or "")
        for t in [c.get("hook")] + list(c.get("stories") or []):
            if t:
                out.append((show, str(t)))
    return out


def _past_rows(past_rows: Sequence[dict], target_date: _dt.date) -> List[dict]:
    iso = target_date.isoformat()
    rows = [r for r in past_rows if isinstance(r, dict) and r.get("date")
            and str(r["date"]) < iso and r.get("contents")]
    rows.sort(key=lambda r: str(r["date"]), reverse=True)
    return rows[:MEMORY_EDITIONS]


def _when(date_iso: str, target_date: _dt.date) -> str:
    try:
        d = _dt.date.fromisoformat(date_iso)
    except ValueError:
        return date_iso
    days = (target_date - d).days
    if days == 1:
        return f"yesterday ({d.strftime('%A')})"
    return f"on {d.strftime('%A')} ({days} days ago)"


def memory_notes(today: Sequence[SegmentStories], past_rows: Sequence[dict],
                 target_date: _dt.date) -> List[str]:
    """"This listener heard about <story> on <weekday> in <show>" — one
    note per today's story that one of the member's last seven editions
    carried, newest past telling cited."""
    rows = _past_rows(past_rows, target_date)
    if not rows:
        return []
    pool = [t for s in today for t in s.texts()]
    pool += [t for r in rows for _show, t in _row_texts(r)]
    m = StoryMatcher(pool)
    notes: List[str] = []
    for s in today:
        for text in s.texts():
            hit = None
            for r in rows:   # newest first
                for show, past in _row_texts(r):
                    if m.same(text, past):
                        hit = (str(r["date"]), show, past)
                        break
                if hit:
                    break
            if hit:
                notes.append(
                    f'{s.show_name} today: "{text}" — this listener heard '
                    f'this story {_when(hit[0], target_date)} in {hit[1]} '
                    f'("{hit[2]}").')
                break   # one note per segment keeps the block short
        if len(notes) >= MAX_MEMORY_NOTES:
            break
    return notes


def week_threads(today: Sequence[SegmentStories], past_rows: Sequence[dict],
                 target_date: _dt.date) -> List[str]:
    """Sunday only: stories that ran on WEEK_THREAD_MIN_DAYS or more
    distinct days of the member's week, counted — never invented."""
    if target_date.weekday() != 6:
        return []
    rows = _past_rows(past_rows, target_date)
    entries: List[Tuple[str, str, str]] = []   # (date, show, text)
    iso = target_date.isoformat()
    for s in today:
        entries += [(iso, s.show_name, t) for t in s.texts()]
    for r in rows:
        entries += [(str(r["date"]), show, t) for show, t in _row_texts(r)]
    m = StoryMatcher([e[2] for e in entries])
    threads: List[Tuple[int, str, List[str]]] = []
    used: set = set()
    for i, (d, show, text) in enumerate(entries):
        if i in used:
            continue
        days, shows, members = {d}, [show], [i]
        for j in range(i + 1, len(entries)):
            if j not in used and m.same(text, entries[j][2]):
                days.add(entries[j][0])
                members.append(j)
                if entries[j][1] not in shows:
                    shows.append(entries[j][1])
        if len(days) >= WEEK_THREAD_MIN_DAYS:
            used.update(members)
            threads.append((len(days), text, shows))
    threads.sort(key=lambda x: -x[0])
    return [f'"{text}" — in {n} of this week\'s editions ({", ".join(shows)}).'
            for n, text, shows in threads[:MAX_WEEK_THREADS]]


# ---------------------------------------------------------------------------
# Repeats across the member's own shows
# ---------------------------------------------------------------------------

@dataclass
class Repeat:
    later: str            # slug
    later_show: str
    later_text: str
    earlier: str
    earlier_show: str
    earlier_text: str
    overlap: int
    fraction: float
    body: float = 0.0
    chapter: Optional[ShowChapter] = None

    @property
    def strong(self) -> bool:
        return (self.overlap >= CUT_MIN_OVERLAP and self.fraction >= CUT_MIN_FRACTION
                and self.body >= CUT_MIN_BODY_SHARE)


def cross_repeats(today: Sequence[SegmentStories]) -> List[Repeat]:
    """A later segment's story that an earlier segment told today — the
    best earlier match per later story, in edition order."""
    pool = [t for s in today for t in s.texts()]
    m = StoryMatcher(pool)
    out: List[Repeat] = []
    for j, later in enumerate(today):
        if j == 0:
            continue
        chapter_by_norm = {_norm(c.title): c for c in later.chapters
                           if c.kind == "headline"}
        seen_earlier: set = set()
        for text in later.texts():
            best: Optional[Repeat] = None
            for earlier in today[:j]:
                for etext in earlier.texts():
                    ov, frac = m.score(text, etext)
                    if ov < MENTION_MIN_OVERLAP or frac < MENTION_MIN_FRACTION:
                        continue
                    body = round(body_share(text, later.units, etext,
                                            earlier.units), 2)
                    if not mention_level(ov, frac, body):
                        continue
                    if best is None or (ov, frac) > (best.overlap, best.fraction):
                        best = Repeat(later.slug, later.show_name, text,
                                      earlier.slug, earlier.show_name, etext,
                                      ov, round(frac, 2), body)
            if best is None:
                continue
            key = (best.earlier, _norm(best.earlier_text))
            if key in seen_earlier or any(
                    r.later == later.slug and r.earlier == best.earlier
                    and (m.same(r.later_text, text) or m.same(r.earlier_text, best.earlier_text))
                    for r in out):
                continue   # one note per story per later show (headline + chapter variants)
            seen_earlier.add(key)
            best.chapter = chapter_by_norm.get(_norm(text))
            if best.chapter is None:
                # The hook or a headline may be the lead chapter's story.
                for c in later.chapters:
                    if c.kind == "headline" and m.same(text, c.title, strong=True):
                        best.chapter = c
                        break
            out.append(best)
    return out


# ---------------------------------------------------------------------------
# Cut safety: silences, purity, boundaries
# ---------------------------------------------------------------------------

def detect_cut_silences(audio: Path) -> List[Tuple[float, float]]:
    """Silent stretches of a cached segment — measured once per show per
    day, shared by every member (story_breaks' silencedetect)."""
    from engine.story_breaks import detect_silences

    try:
        return detect_silences(Path(audio), noise_db=CUT_SILENCE_NOISE_DB,
                               min_seconds=CUT_SILENCE_MIN_SECONDS)
    except Exception as exc:  # noqa: BLE001 — no silences = no cuts, never a failure
        logger.info("silencedetect failed (%s) — no trims for this segment", exc)
        return []


def story_pauses(transcript: Optional[dict]) -> List[Tuple[float, float]]:
    """Word gaps of at least STORY_PAUSE_MIN_SECONDS that end a sentence —
    the pauses engine.story_breaks splices in at a story change."""
    words = _words(transcript)
    out = []
    for (s1, e1, w1), (s2, _e2, _w2) in zip(words, words[1:]):
        if s2 - e1 >= STORY_PAUSE_MIN_SECONDS and _TERMINAL_RE.search(w1):
            out.append((round(e1, 3), round(s2, 3)))
    return out


def cut_pauses(silences: Sequence[Tuple[float, float]],
               transcript: Optional[dict]) -> List[Tuple[float, float]]:
    """Every place a cut may sit: measured silences plus story pauses."""
    return sorted(list(silences) + story_pauses(transcript))


def snap_to_silence(t: float, silences: Sequence[Tuple[float, float]],
                    tolerance: float = SNAP_TOLERANCE_SECONDS) -> Optional[float]:
    """The middle of the silence nearest *t*, when that silence lies
    within *tolerance* of it; else None (no cut)."""
    best: Optional[Tuple[float, float]] = None
    for a, b in silences:
        dist = 0.0 if a <= t <= b else min(abs(t - a), abs(t - b))
        if dist <= tolerance and (best is None or dist < best[0]):
            best = (dist, (a + b) / 2.0)
    return None if best is None else round(best[1], 3)


def _sentences(transcript: Optional[dict]) -> List[Tuple[float, float, str]]:
    out = []
    for s in (transcript or {}).get("segments") or []:
        try:
            out.append((float(s["start"]), float(s["end"]), str(s.get("text") or "")))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _belongs(text: str, unit_tokens: frozenset) -> bool:
    toks = _unit_tokens(text)
    need = 1 if len(toks) <= 3 else 2
    return len(toks & unit_tokens) >= need


def chapter_is_one_story(stories: SegmentStories, chapter: ShowChapter,
                         a: float, b: float) -> Tuple[bool, str]:
    """True when the transcript shows the span [a, b] is the chapter's own
    story start to finish: purity >= CUT_MIN_PURITY, the first and last
    sentences belong to it, the sentence before does not (the chapter did
    not start mid-story) and the sentence after does not (it did not end
    mid-story)."""
    unit = _unit_for(chapter.title, stories.units)
    if unit is None:
        return False, "no digest body for the chapter"
    sents = _sentences(stories.transcript)
    inside = [s for s in sents if a - 0.05 <= (s[0] + s[1]) / 2 <= b + 0.05]
    if not inside:
        return False, "no transcript inside the chapter"
    words = sum(len(s[2].split()) for s in inside) or 1
    own = sum(len(s[2].split()) for s in inside if _belongs(s[2], unit.tokens))
    purity = own / words
    if purity < CUT_MIN_PURITY:
        return False, f"chapter is not one story (purity {purity:.2f})"
    if not _belongs(inside[0][2], unit.tokens) or not _belongs(inside[-1][2], unit.tokens):
        return False, "chapter edge does not belong to its story"
    before = [s for s in sents if s[1] <= a + 0.05]
    after = [s for s in sents if s[0] >= b - 0.05]
    if before and _belongs(before[-1][2], unit.tokens):
        return False, "story starts before the chapter"
    if after and _belongs(after[0][2], unit.tokens):
        return False, "story continues after the chapter"
    return True, f"purity {purity:.2f}"


@dataclass
class Cut:
    slug: str
    start: float          # segment timeline (seconds), inside a silence
    end: float
    title: str
    reason: str           # "repeat" | "length"
    earlier_show: str = ""

    @property
    def seconds(self) -> float:
        return max(0.0, self.end - self.start)


def _snapped_span(chapter: ShowChapter,
                  silences: Sequence[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    a = snap_to_silence(chapter.start, silences)
    b = snap_to_silence(chapter.end, silences)
    if a is None or b is None or b - a < 5.0:
        return None
    return a, b


_TERMINAL_RE = re.compile(r"[.!?…][\"”’')\]]*$")


def _words(transcript: Optional[dict]) -> List[Tuple[float, float, str]]:
    out = []
    for seg in (transcript or {}).get("segments") or []:
        for w in seg.get("words") or []:
            try:
                out.append((float(w["start"]), float(w["end"]), str(w.get("word") or "").strip()))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def at_sentence_boundary(t: float, transcript: Optional[dict]) -> bool:
    """True when *t* falls between two sentences: the last word before it
    ends a sentence and no word is spoken across it. Whisper stretches a
    word across a real pause ("and" over 0.7 s on MAG 7 Ep022), so a
    silence alone does not prove a sentence ended. Word times first; a
    transcript without them falls back to segment edges."""
    words = _words(transcript)
    pad = 0.15
    if words:
        if any(ws < t - pad and we > t + pad for ws, we, _ in words):
            return False
        before = [w for w in words if w[0] < t]
        return not before or bool(_TERMINAL_RE.search(before[-1][2]))
    sents = _sentences(transcript)
    if not sents:
        return False
    if any(a < t - pad and b > t + pad for a, b, _ in sents):
        return False
    before = [x for x in sents if x[0] < t]
    return not before or bool(_TERMINAL_RE.search(before[-1][2].strip()))


def check_chapter_cut(stories: SegmentStories, chapter: ShowChapter,
                      silences: Sequence[Tuple[float, float]], *,
                      single_story: bool) -> Tuple[Optional[Tuple[float, float]], str]:
    """``(span, "")`` when the chapter may be cut, else ``(None, reason)``.

    Rules, in order: never a members-only episode (no public full version
    to point at), never furniture (cold open, teaser, sign-off), never the
    lead story, never the segment's LAST chapter (on shows without a Closing
    chapter it carries the sign-off — MAG 7's "On the Calendar"), both
    edges inside a real silence within SNAP_TOLERANCE_SECONDS, both edges
    between two sentences, and — for a repeat, or any headline chapter —
    the transcript must show the span is that one story start to finish."""
    if stories.private:
        return None, "members-only episode"
    if chapter.kind == "furniture":
        return None, "cold open or sign-off"
    if chapter.lead:
        return None, "lead story"
    if stories.chapters and chapter is stories.chapters[-1]:
        return None, "last chapter carries the sign-off"
    span = _snapped_span(chapter, cut_pauses(silences, stories.transcript))
    if span is None:
        return None, "no pause at a chapter edge"
    if not (at_sentence_boundary(span[0], stories.transcript)
            and at_sentence_boundary(span[1], stories.transcript)):
        return None, "chapter edge falls inside a sentence"
    if single_story or chapter.kind == "headline":
        ok, why = chapter_is_one_story(stories, chapter, *span)
        if not ok:
            return None, why
    return span, ""


def plan_repeat_cuts(today: Sequence[SegmentStories], repeats: Sequence[Repeat],
                     silences: Dict[str, List[Tuple[float, float]]]
                     ) -> Tuple[List[Cut], List[Tuple[Repeat, str]]]:
    """(cuts, refused) — a cut for every strong repeat whose chapter passes
    every rule; the reason for each repeat that does not (the builder logs
    counts per reason, never listener data)."""
    by_slug = {s.slug: s for s in today}
    cuts: List[Cut] = []
    refused: List[Tuple[Repeat, str]] = []
    for r in repeats:
        if not r.strong:
            refused.append((r, "match not strong enough to cut"))
            continue
        s = by_slug[r.later]
        ch = r.chapter
        if ch is None or ch.kind != "headline":
            refused.append((r, "no single-story chapter"))
            continue
        span, why = check_chapter_cut(s, ch, silences.get(s.slug) or [],
                                      single_story=True)
        if span is None:
            refused.append((r, why))
            continue
        if any(c.slug == s.slug and c.title == ch.title for c in cuts):
            continue
        cuts.append(Cut(s.slug, span[0], span[1], ch.title, "repeat", r.earlier_show))
    return cuts, refused


def estimate_mira_seconds(words: int, pieces: int) -> float:
    return words / MIRA_WORDS_PER_SECOND + pieces * MIRA_PIECE_PAD_SECONDS


def plan_length_cuts(today: Sequence[SegmentStories], target_seconds: float,
                     overhead_seconds: float,
                     silences: Dict[str, List[Tuple[float, float]]],
                     already: Sequence[Cut] = ()) -> List[Cut]:
    """Trim from the END of segments until the edition fits: the last
    cuttable body chapter of the currently longest segment first, every
    rule of :func:`check_chapter_cut` applying. Never a whole show (the
    lead and the sign-off always stay). If nothing more may be cut, the
    edition ships long — the caller logs the realized length."""
    cuts: List[Cut] = []
    remaining = {s.slug: s.duration - sum(c.seconds for c in already if c.slug == s.slug)
                 for s in today}
    taken = {(c.slug, c.title) for c in already}
    blocked: set = set()

    def total() -> float:
        return overhead_seconds + sum(remaining.values())

    while total() > target_seconds:
        progressed = False
        for s in sorted(today, key=lambda x: -remaining[x.slug]):
            if s.slug in blocked:
                continue
            candidate = None
            for ch in reversed(s.body_chapters()):
                if (s.slug, ch.title) in taken:
                    continue
                span, _why = check_chapter_cut(s, ch, silences.get(s.slug) or [],
                                               single_story=False)
                if span is None:
                    continue
                if any(c.slug == s.slug and not (span[1] <= c.start or span[0] >= c.end)
                       for c in list(already) + cuts):
                    continue
                candidate = (ch, span)
                break
            if candidate is None:
                blocked.add(s.slug)
                continue
            ch, span = candidate
            cut = Cut(s.slug, span[0], span[1], ch.title, "length")
            cuts.append(cut)
            taken.add((s.slug, ch.title))
            remaining[s.slug] -= cut.seconds
            progressed = True
            break
        if not progressed:
            break
    return cuts


# ---------------------------------------------------------------------------
# Applying cuts: keep ranges, time remap
# ---------------------------------------------------------------------------

def removed_spans(cuts: Sequence[Cut], slug: str) -> List[Tuple[float, float]]:
    spans = sorted((c.start, c.end) for c in cuts if c.slug == slug)
    merged: List[Tuple[float, float]] = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def keep_ranges(duration: float, spans: Sequence[Tuple[float, float]]
                ) -> List[Tuple[float, Optional[float]]]:
    """The (start, end) stretches that stay; the last end is None (to the
    end of the file)."""
    out: List[Tuple[float, Optional[float]]] = []
    cursor = 0.0
    for a, b in spans:
        if a > cursor:
            out.append((cursor, a))
        cursor = max(cursor, b)
    out.append((cursor, None))
    return out


def cut_segment_cmd(src: Path, out_path: Path,
                    ranges: Sequence[Tuple[float, Optional[float]]],
                    duration: float) -> List[str]:
    """One ffmpeg command that keeps *ranges* of *src* and joins them with
    JOIN_FADE_SECONDS fades at every internal edge (a story-break pause on
    a music show carries the theme — a bare jump between two bars of it
    clicks). Re-encoded at the splice format, so it concatenates with the
    edition by stream copy like every other piece."""
    from engine.daily_edition import SEGMENT_ENCODE_ARGS

    parts, labels = [], []
    f = JOIN_FADE_SECONDS
    for i, (a, b) in enumerate(ranges):
        end = duration if b is None else b
        chain = f"[0:a]atrim=start={a:.3f}:end={end:.3f},asetpts=PTS-STARTPTS"
        if i > 0:
            chain += f",afade=t=in:d={f}"
        if i < len(ranges) - 1:
            chain += f",afade=t=out:st={max(0.0, end - a - f):.3f}:d={f}"
        parts.append(chain + f"[p{i}]")
        labels.append(f"[p{i}]")
    graph = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(ranges)}:v=0:a=1[out]"
    return (["ffmpeg", "-y", "-i", str(src), "-filter_complex", graph,
             "-map", "[out]"] + SEGMENT_ENCODE_ARGS + [str(out_path)])


def remap_time(t: float, spans: Sequence[Tuple[float, float]]) -> Optional[float]:
    """Segment time → trimmed-segment time; None inside a removed span."""
    shift = 0.0
    for a, b in spans:
        if t >= b:
            shift += b - a
        elif t > a:
            return None
    return t - shift


def remap_transcript(transcript: Optional[dict],
                     spans: Sequence[Tuple[float, float]]) -> Optional[dict]:
    """The Whisper transcript on the trimmed timeline: cues inside a
    removed span are dropped, later ones shifted."""
    if not transcript or not spans:
        return transcript
    segs = []
    for s in transcript.get("segments") or []:
        try:
            start, end = float(s["start"]), float(s["end"])
        except (KeyError, TypeError, ValueError):
            continue
        mid = (start + end) / 2
        if remap_time(mid, spans) is None:
            continue
        ns, ne = remap_time(start, spans), remap_time(end, spans)
        if ns is None or ne is None:
            continue
        row = dict(s)
        row["start"], row["end"] = round(ns, 3), round(ne, 3)
        row.pop("words", None)
        segs.append(row)
    out = dict(transcript)
    out["segments"] = segs
    return out


def remap_cut_point(cut: Optional[float], spans: Sequence[Tuple[float, float]]
                    ) -> Optional[float]:
    if cut is None:
        return None
    return cut - sum(b - a for a, b in spans if b <= cut)


def chapter_trimmed(chapter: ShowChapter, spans: Sequence[Tuple[float, float]]) -> bool:
    """A chapter is gone when at least half of it sits in removed spans (a
    cut's edges snap into the pauses around the chapter's own edges, so a
    trimmed chapter's span and the cut's differ by a second or so)."""
    length = chapter.end - chapter.start
    if length <= 0:
        return False
    inside = sum(max(0.0, min(b, chapter.end) - max(a, chapter.start)) for a, b in spans)
    return inside >= 0.5 * length


def segment_subchapters(stories: SegmentStories, spans: Sequence[Tuple[float, float]]
                        ) -> List[Tuple[str, float]]:
    """(title, start on the trimmed timeline) for the segment's own
    navigable chapters after the lead: section and headline chapters, never
    furniture, never a trimmed one. Titles are the show's own chapter
    titles, whole — never generated, never clipped into a fragment."""
    out: List[Tuple[str, float]] = []
    for c in stories.chapters:
        if c.kind == "furniture" or c.lead:
            continue
        if len(c.title) > HEADLINE_CHAPTER_TITLE_MAX:
            continue
        if chapter_trimmed(c, spans):
            continue
        t = remap_time(c.start, spans)
        if t is None:
            # Starts inside a trimmed stretch but is mostly kept: it begins
            # where that stretch was.
            t = remap_time(max(b for a, b in spans if a <= c.start <= b), spans)
        if t is None or (out and t - out[-1][1] < 5.0):
            continue
        out.append((c.title, round(t, 2)))
    return out


# ---------------------------------------------------------------------------
# Interest highlights
# ---------------------------------------------------------------------------

#: Profile words that say nothing about a subject.
_PROFILE_STOP = frozenset("""
work works working worked job live lives living love loves like likes interested
interest interests follow follows following really very much about into from
want wants mostly especially also always often sometimes morning commute drive
daily listen listening listener podcast podcasts news show shows things stuff
time years kids family wife husband home based small large little good great
best well part full owner own retired student teacher company business
city town area local world industry field team role care keen into
""".split())


def profile_keywords(profile: str) -> List[str]:
    toks = [t for t in re.findall(r"[a-z][a-z0-9\-]{3,}", (profile or "").lower())
            if t not in _PROFILE_STOP and t not in _EXTRA_STOP
            and t in _salient(t)]
    out: List[str] = []
    for t in toks:
        if t not in out:
            out.append(t)
    return out[:12]


def interest_highlights(today: Sequence[SegmentStories], topics: Sequence[str],
                        profile: str = "",
                        spans: Optional[Dict[str, Sequence[Tuple[float, float]]]] = None
                        ) -> List[str]:
    """Where in today's edition the member's own subjects are: a topic
    matches a chapter title / headline when it shares all of its salient
    tokens (or two of them); a profile keyword when the story title carries
    it. Pointers name the show and the story's place in it, from the shows'
    own chapter titles and headlines only — never a story *spans* trimmed
    out, and the place is counted on what remains."""
    out: List[str] = []
    keywords = profile_keywords(profile)
    spans = spans or {}
    for subject, needles, kind in (
            [(t, story_tokens(t), "topic") for t in topics]
            + [(k, frozenset({k}), "profile") for k in keywords]):
        if not needles:
            continue
        for s in today:
            body = [c for c in s.body_chapters()
                    if not chapter_trimmed(c, spans.get(s.slug) or [])]
            items = [(i + 1, c.title) for i, c in enumerate(body)] or \
                [(i + 1, h) for i, h in enumerate(s.headlines)]
            hit = None
            for pos, title in items:
                toks = story_tokens(title)
                need = len(needles) if len(needles) <= 2 else 2
                if len(needles & toks) >= need:
                    hit = (pos, title)
                    break
            if hit:
                where = "the opening story" if hit[0] == 1 else f"story {hit[0]} of the segment"
                label = (f'their topic "{subject}"' if kind == "topic"
                         else f'what they told you ("{subject}")')
                out.append(f'{s.show_name}, {where}: "{hit[1]}" — matches {label}.')
                break
        if len(out) >= MAX_HIGHLIGHTS:
            break
    return out


__all__ = [
    "CUT_MIN_BODY_SHARE",
    "CUT_MIN_FRACTION",
    "CUT_MIN_OVERLAP",
    "CUT_MIN_PURITY",
    "Cut",
    "MENTION_MIN_FRACTION",
    "MENTION_MIN_OVERLAP",
    "Repeat",
    "SegmentStories",
    "ShowChapter",
    "StoryMatcher",
    "chapter_is_one_story",
    "classify_chapters",
    "at_sentence_boundary",
    "check_chapter_cut",
    "cut_pauses",
    "cross_repeats",
    "cut_segment_cmd",
    "detect_cut_silences",
    "edition_contents",
    "estimate_mira_seconds",
    "interest_highlights",
    "keep_ranges",
    "load_show_chapters",
    "memory_notes",
    "mention_level",
    "plan_length_cuts",
    "plan_repeat_cuts",
    "profile_keywords",
    "remap_cut_point",
    "remap_time",
    "remap_transcript",
    "removed_spans",
    "segment_stories",
    "segment_subchapters",
    "snap_to_silence",
    "story_pauses",
    "story_tokens",
    "week_threads",
]
