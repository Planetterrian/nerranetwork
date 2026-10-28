"""Podcast chapter generation from script section markers.

Parses an LLM-generated podcast script to identify section boundaries,
calculates approximate chapter timestamps using word-count proportions,
and writes Podcasting 2.0-compatible chapter JSON files.

Usage in the pipeline (run_show.py):
    1. After podcast script is generated + cleaned, call ``parse_chapters()``
    2. After final MP3 is produced, call ``calculate_timestamps()``
    3. Call ``write_chapters_json()`` to persist alongside the episode
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from engine.titles import HEADLINE_CHAPTER_TITLE_MAX

# Oct 20 2026: the identity line and THE MAP after it (engine.intros
# build_cold_open_spec) — the same shape engine.story_breaks reads, kept
# here as a copy so chapters never imports the audio module.
_MAP_IDENTITY_RE = re.compile(r"^\W*this is .{2,60}episode", re.IGNORECASE)
_MAP_IDENTITY_SEARCH_LINES = 4
# What a map sentence sounds like (Oct 21 2026). A script written before the
# Oct 20 map has its LEAD on the line after the identity line, so only a line
# that reads as a list of what comes next is treated as the map: it carries no
# digit (the spec bans numbers), a sequencing word ("then", "follows", "after
# that", "at the end") and a list comma. Measured on the 16 Oct 21 maps (all
# read as maps) and the 187 pre-map scripts of Oct 10-19 (see the guard).
_MAP_CUE_RE = re.compile(
    r"(?:^after\b|\b(?:then|follows?|up after|after the lead|and later|later we)\b"
    r"|\bat the end\b(?! of)"
    # Oct 22 2026: "From there it's…", "From that horizon, …", "… are the
    # run from here" and "… come next" are maps too (MAB, FF, SpaceX).
    r"|^from (?:that|there|here)\b|\bfrom here\b|\bcomes? next\b)",
    re.IGNORECASE)


def _looks_like_map(line: str) -> bool:
    text = (line or "").strip()
    if not text or re.search(r"\d", text):
        return False
    return bool(_MAP_CUE_RE.search(text)) and text.count(",") >= 1



logger = logging.getLogger(__name__)

#: One budget for every headline-derived chapter title (Oct 14 2026). The
#: Oct 8 clip ran at 60 and shipped "...halts the number" fragments on the
#: Oct 13 slate while most desk lead headlines run 60-80; a headline that
#: fits ``engine.titles.HEADLINE_CHAPTER_TITLE_MAX`` ships whole now and a
#: longer one is clipped at a clause boundary inside it.
HEADLINE_TITLE_MAX = HEADLINE_CHAPTER_TITLE_MAX


@dataclass
class Chapter:
    """A single chapter in a podcast episode."""

    title: str
    startTime: float = 0.0
    endTime: float = 0.0
    # Word range within the script (used for proportion calculation)
    word_start: int = 0
    word_end: int = 0
    # Character range within the script (used for text splitting)
    char_start: int = 0
    char_end: int = 0
    # The opening words of the line the chapter starts on (Oct 17 2026), so
    # the start can be found again in the spoken audio after later passes
    # have edited the script around it (align_timestamps_to_transcript).
    opening: str = ""


# Sentence terminators that close a chapter title. ``…`` and Russian
# ``.`` style markers are included so Russian shows benefit too.
_SENTENCE_END_RE = re.compile(r"([.!?…])\s+")


# Digest FORMATTING templates show the heading shape as a literal
# ``**Title: Source Name**`` and the model periodically reproduces the
# label instead of substituting (SpaceX Ep58/60/66/68/70, DP Pod Ep35 —
# Aug 2026 review). Chapter titles were one of the two surfaces with no
# defense (the other, the digest itself, is repaired at generation time).
# Same fix engine/youtube_titles.py has carried since July.
_TITLE_LABEL_RE = re.compile(r"^(?:title|headline)\s*\d*\s*[:\-—]\s*", re.IGNORECASE)

# ``[label](url)`` inside a candidate title. Models & Agents Ep161
# (2026-09-02) shipped the chapter "Training a Misaligned Reward Seeker:
# [@AnthropicAI](https" — the digest headline carried an X-profile link
# as its source tail and the clipper cut through the URL. Links are
# flattened to their label (and a lone ``@handle`` tail dropped) in every
# title-producing helper, so no chapter surface can show a URL fragment.
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\((?:[^)\s]*)\)")
_HANDLE_TAIL_RE = re.compile(r"\s*[:\-—]\s*@\w+\s*$")


# Words that carry no signal when locating a digest section's content in
# the script (``_digest_section_anchor``). Four letters or more only.
_ANCHOR_STOPWORDS = frozenset(
    "that this with from have will been were their they which about into "
    "than then also more most when what where while there these those over "
    "under such only just very each other some your because being would "
    "could should after before between through against during without "
    "within across among".split()
)
# A script line belongs to the section when it carries this many of the
# section's DISCRIMINATIVE words (in the section, in no other section).
_ANCHOR_LINE_MIN = 4
# ...and the run it opens must reach this many on at least one line, so a
# stray two-word echo of the section in a news item never anchors it.
_ANCHOR_RUN_PEAK_MIN = 8


def _anchor_tokens(text: str) -> set:
    return {
        w for w in re.findall(r"[a-z][a-z0-9\-]{3,}", (text or "").lower())
        if w not in _ANCHOR_STOPWORDS
    }


def _digest_sections(digest_text: str) -> dict:
    """``{heading: body}`` for every ``##``-``####`` heading, Source lines dropped."""
    out: dict = {}
    current = None
    buf: list = []
    for line in (digest_text or "").splitlines():
        m = re.match(r"^#{2,4}\s+(.*\S)", line)
        if m:
            if current is not None:
                out[current] = "\n".join(buf)
            current, buf = m.group(1).strip(), []
        elif current is not None:
            if re.match(r"^\s*sources?\s*:", line, re.IGNORECASE):
                continue
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf)
    return out


def _digest_section_anchor(
    lines: List[str], digest_text: str, heading_prefix: str,
    lo_word: int, hi_word: int,
) -> Optional[tuple]:
    """Where the digest section headed *heading_prefix* starts in the script.

    Oct 5 2026. A section's chapter keys on a spoken phrase; when the model
    writes the section but skips the phrase, the chapter vanished and its
    content was filed under the previous chapter (Models & Agents
    Ep178/185/189/190 shipped no Under the Hood chapter — every miss on the
    combined-generation path; AI Chips Ep9 said "take the flexible queue
    apart" and lost The Teardown). The section's content is still in the
    script, so the chapter starts at the first line of the first run of
    lines carrying the section's own words — words that appear in that
    digest section and in no other one, so a news item that shares the
    deep dive's subject cannot anchor it. Returns ``(word_idx, char_offset)``
    or ``None``; nothing is ever guessed below the thresholds.
    """
    if not digest_text or not heading_prefix:
        return None
    sections = _digest_sections(digest_text)
    prefix = heading_prefix.strip().lower()
    target = next((h for h in sections if h.lower().startswith(prefix)), None)
    if target is None:
        return None
    own = _anchor_tokens(sections[target] + " " + target.split(":", 1)[-1])
    others: set = set()
    for heading, body in sections.items():
        if heading != target:
            others |= _anchor_tokens(heading + " " + body)
    disc = own - others
    if len(disc) < _ANCHOR_RUN_PEAK_MIN:
        return None

    scored: list = []  # (word_idx, char_offset, score) for content lines
    word_idx = 0
    char_offset = 0
    for line in lines:
        n = len(line.split())
        if n and lo_word <= word_idx < hi_word:
            scored.append((word_idx, char_offset,
                           len(_anchor_tokens(line) & disc)))
        word_idx += n
        char_offset += len(line)

    for i, (w, c, score) in enumerate(scored):
        if score < _ANCHOR_LINE_MIN:
            continue
        run = scored[i:i + 4]
        if sum(1 for r in run[1:] if r[2] >= _ANCHOR_LINE_MIN) < 2:
            continue
        if max(r[2] for r in run) < _ANCHOR_RUN_PEAK_MIN:
            continue
        return (w, c)
    return None


def _strip_title_label(title: str) -> str:
    title = _MD_LINK_RE.sub(lambda m: m.group(1), title or "")
    title = _HANDLE_TAIL_RE.sub("", title)
    return _TITLE_LABEL_RE.sub("", title).strip()


def _whole_title(raw: str) -> str:
    """A headline as it would ship as a chapter title, never shortened.

    Oct 17 2026: a headline is a chapter title WHOLE or not at all. Tesla
    Ep637 shipped "Luxury estate in South Africa has off-grid home fitted"
    and "History Says Tesla Stock Swings Hard on Earnings. It Has Moved 8%"
    — word-clipped headlines from the lead split and the headline anchors,
    the two paths that still called ``_clip_title``. Callers compare the
    length of this against ``HEADLINE_TITLE_MAX`` and drop what does not fit.
    """
    title = _strip_title_label(re.sub(r"[*_`]+", "", raw or "").strip())
    # An outlet's SEO tail is not part of the headline: a ticker in
    # parentheses ("… Bottleneck (TSLA)") or a bracketed year ("… [2026]").
    return _SEO_TAIL_RE.sub("", title).strip()


_SEO_TAIL_RE = re.compile(r"\s*(?:\((?:NASDAQ|NYSE|TSX)?:?\s*[A-Z]{1,5}(?:\.[A-Z]{1,3})?\)|\[(?:19|20)\d\d\])$")


#: A line spoken by a named host in a dialogue script ("DAN: Ten",
#: "PATRICK: I'll take the hit on that"). Oct 11 2026: The DP Pod shipped
#: these as chapter titles on six of ten episodes (Ep070–077) — a host's
#: reaction is a turn in a conversation, never the name of a segment.
_SPEAKER_LABEL_RE = re.compile(r"^[A-Z]{2,15}:\s")

#: A sentence that opens on one of these continues the one before it — it is
#: never a chapter title on its own.
_CONTINUATION_OPENER_RE = re.compile(
    r"^(?:and|but|or|so|yet|still|also|then|because|which|while|that|this|"
    r"these|those|it|its|they|their|he|she|his|her|we|there|here|instead|"
    r"meanwhile|however|now|plus|even|after that|by then|in turn|as a result)\b",
    re.IGNORECASE,
)


def _first_sentence_as_title(text: str, max_chars: int = 60) -> str:
    """Extract the first sentence of *text* and return a chapter-title
    string (max ``max_chars``).

    Used by the chapter auto-segmentation fallback. Apple Podcasts and
    Pocket Casts surface chapter titles in the player UI, so a title
    derived from actual content (e.g. "Tesla unveils robotaxi service
    in Texas") is dramatically more useful than the previous
    "Segment 2" placeholder. Returns "" if no clean sentence is
    extractable — caller falls back to the numeric placeholder.
    """
    if not text:
        return ""
    # Trim leading whitespace/markdown fragments and pick the first
    # non-blank line so headers/blank gaps don't poison the title.
    cleaned = text.lstrip().lstrip("*_-•> ").lstrip()
    if not cleaned or _SPEAKER_LABEL_RE.match(cleaned):
        return ""
    # First sentence — anything up to the first . ! ? … plus space.
    match = _SENTENCE_END_RE.split(cleaned, maxsplit=1)
    candidate = match[0].strip() if match else cleaned.strip()
    if not candidate:
        return ""
    # Strip residual inline markdown so the title reads cleanly.
    candidate = _strip_title_label(re.sub(r"[*_`]+", "", candidate).strip())
    # Oct 8 2026: a spoken sentence is a title only when it is WHOLE.
    # Clipping one ("Giorgos Mazonakis, fifty-four, died on September
    # ninth…", "A two thousand nine meta-analysis in JAMA turned that…" on
    # Longevity Ep003) or taking one that leans on the sentence before it
    # ("Yet these observations received little weight in the final…" on
    # UC Ep136) ships a fragment to every podcast app's chapter list. The
    # caller makes no chapter break where no title exists.
    if len(candidate) > max_chars:
        return ""
    if _CONTINUATION_OPENER_RE.match(candidate):
        return ""
    # Sanity: titles shouldn't be one-word fragments or just a number.
    if len(candidate) < 8 or candidate.replace(".", "").isdigit():
        return ""
    return candidate


# Words that carry no topical signal when matching a script segment to a
# clean digest headline (auto-segment titling). Kept small + lowercase.
_TITLE_MATCH_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "at", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "it", "its", "this", "that", "these", "those", "into", "over",
    "after", "before", "about", "than", "then", "so", "we", "you", "they",
    "their", "our", "his", "her", "new", "now", "up", "out", "has", "have",
})


def _tokenize_for_match(text: str) -> set:
    """Lowercase content-word token set for overlap scoring."""
    toks = re.findall(r"[a-z0-9]{3,}", (text or "").lower())
    return {t for t in toks if t not in _TITLE_MATCH_STOPWORDS}


def _best_headline_for_segment(
    seg_text: str, headlines: List[str], used: set,
    max_chars: int = HEADLINE_TITLE_MAX,
    whole_only: bool = False,
) -> str:
    """Pick the unused digest *headline* that best overlaps *seg_text*.

    Auto-segment titles drawn from the segment's raw first sentence are
    often mid-thought fragments ("Knowing this, when you hear claims…").
    The episode digest already carries clean, capitalised per-story
    headlines (``extract_story_headlines``); matching each spoken segment
    to its originating headline by content-word overlap yields a proper
    title ("Tesla unveils robotaxi service in Texas"). Returns "" when no
    headline overlaps the segment meaningfully (caller falls back to the
    first-sentence title, then ``Segment N``).
    """
    if not headlines:
        return ""
    seg_tokens = _tokenize_for_match(seg_text)
    if not seg_tokens:
        return ""
    best_title = ""
    best_score = 0
    for idx, h in enumerate(headlines):
        if h in used:
            continue
        if _is_hook_candidate(h, idx, max_chars):
            # Not a title: extract_story_headlines leads with the digest's
            # blockquote HOOK — a full sentence (needed as image context,
            # useless here). Raw token-overlap favors the longest
            # candidate (Omni View Ep160, 2026-08-30: the 130-char hook
            # beat the real summit headline). The 08-30 fix skipped
            # EVERYTHING over max_chars, which on 2026-09-02 (Ep163)
            # threw away 7 of 8 real headlines (62-91 chars) and shipped
            # first-sentence fragments instead. Only hook-length
            # candidates are skipped now; a long real headline competes
            # and is shortened cleanly by ``_clip_title``.
            continue
        if whole_only and len(_whole_title(h)) > max_chars:
            # Oct 17 2026: a headline is a chapter title whole or not at all.
            continue
        h_tokens = _tokenize_for_match(h)
        if not h_tokens:
            continue
        overlap = len(seg_tokens & h_tokens)
        # Require ≥2 shared content words (or ≥half a short headline) so an
        # incidental single-word match doesn't mis-title a segment.
        if overlap > best_score and (
            overlap >= 2 or overlap >= max(1, len(h_tokens) // 2)
        ):
            best_score = overlap
            best_title = h
    if not best_title:
        return ""
    used.add(best_title)  # claim the headline so the next segment can't reuse it
    if whole_only:
        return _whole_title(best_title)
    return _clip_title(best_title, max_chars)


# A candidate longer than ``max_chars * _HOOK_LENGTH_FACTOR`` is the
# digest's lead HOOK (a full sentence), never a headline.
_HOOK_LENGTH_FACTOR = 2


def _is_hook_candidate(h: str, idx: int, max_chars: int) -> bool:
    """True when *h* is the digest's lead hook rather than a headline.

    ``extract_story_headlines`` puts the blockquote hook FIRST, so an
    over-budget first candidate is the hook (Tesla Ep592: the 104-char
    hook "Installers face six-figure losses after Tesla stopped…" would
    otherwise out-score every real headline for the lead segment).
    Anything longer than twice the budget is a sentence, not a title,
    wherever it sits.
    """
    n = len(h)
    return n > max_chars * _HOOK_LENGTH_FACTOR or (idx == 0 and n > max_chars)

# Function words a shortened headline must not end on — "…criticizes
# Chinese actions at" reads as a cut; "…criticizes Chinese actions" reads
# as a title.
_DANGLING_TAIL = frozenset(
    "a an the and or but nor of at in on for to with by as from after over "
    "into amid while than that its their his her our this these those "
    "under before between against about via per not no is are was were be "
    "has have had will would could should can may might who which when "
    "where how what why if so yet up more".split()
)


#: Where a shortened headline may end cleanly: before a clause or a
#: prepositional phrase, never inside one.
_CLAUSE_BREAKS = (", ", "; ", " — ", " – ", " - ", " on ", " in ", " at ",
                  " for ", " to ", " after ", " as ", " with ", " from ",
                  " amid ", " while ", " over ", " by ", " of ")


#: Digest lead headings that name the lead story's SLOT, not the story —
#: the chapter is still titled with them when the hook is too long to be a
#: title and no headline matches, because a listener can jump to "Lead"
#: and cannot jump to nothing. Longer, sentence-shaped headings never are.
_LEAD_HEADING_MAX_CHARS = 40
_LEAD_HEADING_RE = re.compile(r"^\s*#{2,6}\s+(.+?)\s*$", re.MULTILINE)
_LEAD_HEADING_COUNT_RE = re.compile(r"\s*\(\d+\)\s*$")


def lead_block_tokens(digest_text: str) -> set:
    """Content words of the digest's LEAD TEXT: the first paragraph (or first
    numbered item) under its first section heading. Mira's desks tell the
    lead in short paragraphs that name the actor once and then say "he" —
    Asia Pacific Ep021's first body paragraphs shared one word with the hook
    and none with the matched headline, so the lead had no chapter even
    though the digest's Lead section carried every word of them (Yonhap,
    Tuesday, Cabinet, Seoul). Empty when the digest has no section heading."""
    text = digest_text or ""
    m = _LEAD_HEADING_RE.search(text)
    if not m:
        return set()
    rest = text[m.end():]
    nxt = _LEAD_HEADING_RE.search(rest)
    section = rest[: nxt.start()] if nxt else rest
    for block in re.split(r"\n[ \t]*\n", section):
        block = re.sub(r"^\s*\d+[.)]\s*", "", block.strip())
        block = re.sub(r"(?im)^\s*Source(?:/Post)?\s*:.*$", "", block)
        block = re.sub(r"https?://\S+", " ", block)
        toks = _tokenize_for_match(re.sub(r"[*_`#>]+", " ", block))
        if len(toks) >= 4:
            return toks
    return set()


def lead_section_name(digest_text: str) -> str:
    """The digest's own name for its first section ("Lead", "Top Story",
    "Top News", "Today's lead story"), or ``""`` when the first heading is a
    story title rather than a label (Omni View's ``### 1) <headline>``, a
    heading with sentence punctuation, or one over the label length)."""
    for line in (digest_text or "").split("\n"):
        m = _LEAD_HEADING_RE.match(line)
        if not m:
            continue
        name = _LEAD_HEADING_COUNT_RE.sub("", re.sub(r"[*_`]+", "", m.group(1))).strip()
        if (not name or len(name) > _LEAD_HEADING_MAX_CHARS
                or re.match(r"^\d+[.)]", name) or re.search(r"[.!?:—]", name)):
            return ""
        return name
    return ""


def _clip_title(raw: str, max_chars: int = HEADLINE_TITLE_MAX) -> str:
    """Fit a real digest headline into *max_chars* WITHOUT an ellipsis.

    A headline is a title, so a trailing "…" is wrong on every surface
    (seek bar, description, on-screen card): it reads as a broken
    sentence and the on-screen card stage rightly refuses such titles.
    The cut goes through ``engine.titles.clip_words`` (the one sanctioned
    clipper) and then drops any dangling function word. Only when the
    clean cut would lose more than half the headline does the legacy
    ellipsis clip remain, so a title can never collapse to two words.
    """
    title = _strip_title_label(re.sub(r"[*_`]+", "", raw or "").strip())
    if len(title) <= max_chars:
        return title
    from engine.titles import clip_words
    words = clip_words(title, max_chars, ellipsis="").split()
    while words and words[-1].lower().strip(",;:'\"") in _DANGLING_TAIL:
        words.pop()
    clean = " ".join(words).rstrip(",;:—–-")
    # Oct 8 2026: a clip that lands mid-phrase ("…Supercharger stalls on
    # former", "…reasoning at one") reads as a broken sentence. Back off to
    # the last clause boundary when enough of the headline survives.
    boundary = max((clean.rfind(m) for m in _CLAUSE_BREAKS), default=-1)
    if boundary >= int(max_chars * 0.6):
        clean = clean[:boundary].rstrip(",;:—–- ")
    if len(clean) >= max_chars // 2:
        return clean
    return title[: max_chars - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _paragraphs(lines: List[str]) -> list:
    """``[(start_word, start_char, content_tokens), ...]`` per paragraph.

    Mirrors parse_chapters' offset accounting (``splitlines(keepends)``).
    """
    paras: list[tuple[int, int, set]] = []
    word_idx = 0
    char_idx = 0
    cur_start: Optional[tuple[int, int]] = None
    cur_text: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            if cur_start is None:
                cur_start = (word_idx, char_idx)
            cur_text.append(stripped)
        elif cur_start is not None:
            paras.append(
                (cur_start[0], cur_start[1], _tokenize_for_match(" ".join(cur_text)))
            )
            cur_start, cur_text = None, []
        word_idx += len(line.split())
        char_idx += len(line)
    if cur_start is not None:
        paras.append(
            (cur_start[0], cur_start[1], _tokenize_for_match(" ".join(cur_text)))
        )
    return paras


def _opens_as_continuation(text: str) -> bool:
    """A paragraph opening on a pronoun, a demonstrative or a connective
    continues the story before it (``engine.story_breaks`` owns the shape —
    the same lines never get a story beat). "This is <show>…" is the
    identity line, never a continuation."""
    if re.match(r"^\W*this is\b", text or "", re.IGNORECASE):
        return False
    from engine.story_breaks import opens_as_continuation
    return opens_as_continuation(text)


#: The lead story must begin within this many paragraphs of the opening
#: chapter's start, or it is not where the episode put its lead.
LEAD_SEARCH_PARAGRAPHS = 4
#: Content words a script paragraph must share with the digest's lead text
#: (``lead_block_tokens``) to be the lead paragraph.
LEAD_TEXT_MIN_SHARED = 3


def _lead_story_split(
    lines: List[str],
    head: "Chapter",
    story_headlines: List[str],
    max_chars: int = HEADLINE_TITLE_MAX,
    whole_only: bool = False,
    fallback_title: str = "",
    lead_text_tokens: Optional[set] = None,
    exclude_titles: Optional[set] = None,
    lead_story_words: Optional[set] = None,
) -> Optional[tuple]:
    """Where the lead story starts inside the opening chapter.

    Oct 8 2026: the lead had its own chapter on 2 of 21 episodes. Since
    the July cold-open pass every script opens on the hook, then the
    identity line, then the lead story, all inside "Introduction";
    headline anchoring skipped the lead because it starts fewer than 60
    words in, and marker-driven shows never split the opening at all. So
    the story every title and thumbnail sells was the one story a
    listener could not jump to.

    The lead paragraph is the first paragraph after the opening chapter's
    own first paragraph (within ``LEAD_SEARCH_PARAGRAPHS``) that shares
    content words with the hook — or, on a digest with no hook, with its
    first headline. Its title is the headline that best matches the hook;
    when the lead has no headline of its own (desks, M&A and Prediction
    Markets write the lead under a bare section heading), the hook itself
    cut cleanly at a word boundary. A body that does not open on the
    hook's story gets no lead chapter — never a guess. Returns
    ``(word_idx, char_offset, title)`` or None.

    Oct 14 2026: the budget is ``HEADLINE_TITLE_MAX`` (80) on every show —
    at 60 the lead chapter on the Oct 13 slate read "...halts the number"
    on 9 of 20 episodes and was missing on the rest, because a hook over
    60 characters (every one of them) and a headline over 60 (most desk
    leads) left nothing to title it with. When the hook is longer than the
    budget and no headline matches it, *fallback_title* — the digest's own
    name for its lead section ("Lead", "Top Story") — titles the chapter,
    so a listener can jump to the lead on a desk whose lead is written
    under a bare heading, as every desk's is.

    Oct 17 2026: (1) with ``whole_only`` a headline that does not fit the
    budget is never clipped — the lead then takes *fallback_title* or gets
    no chapter (Tesla Ep637 shipped "Luxury estate in South Africa has
    off-grid home fitted"). (2) *exclude_titles* are headlines known to
    tell a DIFFERENT story than the hook: AI Chips Ep026's hook was TSMC's
    "Second Arizona fab", and the two words it shared with "Samsung's second
    Taylor fab…" titled the TSMC lead with the Samsung story. (3) The lead
    starts on the first paragraph of its run: a paragraph that opens on a
    pronoun or a demonstrative ("Those packs hold…") continues the story the
    hook began, so the chapter backs up over it.
    """
    if not story_headlines:
        return None
    exclude = exclude_titles or set()
    hook = ""
    candidates = []
    for idx, h in enumerate(story_headlines):
        if _is_hook_candidate(h, idx, max_chars):
            if idx == 0:
                hook = h
            continue
        if h in exclude:
            continue
        tokens = _tokenize_for_match(h)
        if tokens:
            candidates.append((h, tokens))

    def _fits(t: str) -> bool:
        return not whole_only or len(_whole_title(t)) <= max_chars

    hook_tokens = _tokenize_for_match(hook)
    title = ""
    if hook_tokens:
        best = max(candidates, key=lambda c: len(c[1] & hook_tokens), default=None)
        if best and len(best[1] & hook_tokens) >= 2:
            lead_tokens = best[1] | hook_tokens
            if _fits(best[0]):
                title = best[0]
        else:
            lead_tokens = hook_tokens
        if not title:
            # Oct 12 2026: the hook is a spoken sentence, and a spoken
            # sentence is a title only when it fits whole (the Oct 8 rule).
            # A word-clipped hook ("Sixteen people drowned in Bihar while
            # collecting festival") shipped as the lead chapter on five
            # desks; no title means no lead chapter, never a fragment.
            if len(_whole_title(hook)) <= max_chars:
                title = _clip_title(hook, max_chars)
            elif fallback_title:
                title = fallback_title
    elif candidates:
        title, lead_tokens = candidates[0]
        if not _fits(title):
            title = fallback_title
    else:
        return None
    if not title:
        return None
    body = [p for p in _paragraphs(lines)
            if head.word_start < p[0] < head.word_end]
    text = "".join(lines)
    text_tokens = lead_text_tokens or set()
    # Oct 21 2026: the identity line and the map sentence after it are never
    # the lead. The map names the stories, so it shares the hook's words and
    # took the lead chapter on six of the Oct 21 episodes (FF at 10.7 s, MAB
    # at 7.3 s, Top World at 12.2 s — the lead itself began seconds later).
    _skip: set = set()
    for j, (_w, _c, _t) in enumerate(body[:LEAD_SEARCH_PARAGRAPHS]):
        if _MAP_IDENTITY_RE.match(text[_c:_c + 120].strip()):
            _skip.update({j, j + 1})
            break
    _floor = max(_skip) + 1 if _skip else 0
    for i, (w, c, tokens) in enumerate(body[:LEAD_SEARCH_PARAGRAPHS]):
        if i in _skip:
            continue
        # The paragraph tells the hook's story: it shares the hook's or the
        # headline's words, or (Oct 14 2026) three of the digest's own lead
        # text — the desks' short, pronoun-led paragraphs match that way.
        if (len(tokens & lead_tokens) >= 2 or len(tokens & text_tokens) >= LEAD_TEXT_MIN_SHARED
                or w in (lead_story_words or ())):
            while i > _floor and _opens_as_continuation(text[body[i - 1][1]:body[i - 1][1] + 80]):
                i -= 1
            w, c = body[i][0], body[i][1]
            return w, c, (_whole_title(title) if whole_only else _clip_title(title, max_chars))
    return None


def _headline_anchored_insertions(
    lines: List[str],
    head_word_start: int,
    head_word_end: int,
    story_headlines: List[str],
    min_segment_words: int = 60,
    max_chars: int = HEADLINE_TITLE_MAX,
    whole_titles_max: Optional[int] = None,
    min_results: int = 2,
) -> list:
    """Anchor auto-segment boundaries where each digest story BEGINS.

    The legacy auto-segment slices the head chapter every ~90s of speech
    at arbitrary paragraph breaks, then fits a headline to whatever text
    lands in each window — so a chapter can carry one story's title while
    starting mid-way through another (Tesla Ep548, July 21 2026). Shows
    whose prompts ban spoken section labels hit this on most episodes
    because their keyword markers never match.

    This variant inverts the mapping: for each digest headline, find the
    paragraph inside the head span whose content words best overlap it,
    and start a chapter (bearing that headline) at that paragraph. Titles
    and boundaries then agree by construction. Returns
    ``[(word_idx, char_offset, title), ...]`` sorted by position, or
    ``[]`` when fewer than ``min_results`` headlines anchor confidently —
    callers fall back to the legacy fixed-interval segmentation.

    ``whole_titles_max`` (Oct 12 2026, known_sections_only shows): a
    headline longer than this is not a candidate at all, and the ones that
    fit are used whole — never clipped.
    """
    if not story_headlines or len(story_headlines) < 2:
        return []

    paras = _paragraphs(lines)
    in_head = [p for p in paras if head_word_start < p[0] < head_word_end]
    if not in_head:
        return []

    # Best-matching paragraph per headline; a paragraph keeps only its
    # strongest headline so two stories can't anchor the same spot.
    anchors: dict[int, tuple[int, str]] = {}  # para index -> (score, headline)
    for idx, h in enumerate(story_headlines):
        if _is_hook_candidate(h, idx, max_chars):
            # Not a title: extract_story_headlines leads with the digest's
            # blockquote HOOK — a full lead sentence, wanted as image
            # context but never as a chapter. It out-scores real headlines
            # on raw token overlap (Omni View Ep160, 2026-08-30: "Leaders
            # from Russia, China, India and Iran meet in Central…" reached
            # listeners). Real headlines between max_chars and twice that
            # stay eligible and are shortened cleanly (see _clip_title).
            continue
        if whole_titles_max is not None and len(
                _strip_title_label(re.sub(r"[*_`]+", "", h).strip())) > whole_titles_max:
            continue
        h_tokens = _tokenize_for_match(h)
        if not h_tokens:
            continue
        best_i = None
        best_score = 0
        for i, (_w, _c, p_tokens) in enumerate(in_head):
            overlap = len(p_tokens & h_tokens)
            if overlap > best_score and (
                overlap >= 2 or overlap >= max(1, len(h_tokens) // 2)
            ):
                best_i, best_score = i, overlap
        if best_i is not None:
            prev = anchors.get(best_i)
            if prev is None or best_score > prev[0]:
                anchors[best_i] = (best_score, h)

    result: list = []
    last_w = head_word_start
    for i in sorted(anchors):
        w, c, _tokens = in_head[i]
        if w - last_w < min_segment_words:
            continue  # too close to the previous boundary — merge forward
        title = (_strip_title_label(re.sub(r"[*_`]+", "", anchors[i][1]).strip())
                 if whole_titles_max is not None
                 else _clip_title(anchors[i][1], max_chars))
        result.append((w, c, title))
        last_w = w
    return result if len(result) >= min_results else []


# ---------------------------------------------------------------------------
# Story chapters from the story-change detector (Oct 17 2026)
# ---------------------------------------------------------------------------

#: A bold item heading at the start of a digest line: ``1. **Title** —
#: Outlet``, ``**Title — Phys.org**``, ``**Title:** Outlet``,
#: ``**[Title]: source**``. Group 1 is the number, 2 the bold span, 3 the rest.
_ITEM_BOLD_RE = re.compile(r"^\s*(\d+[.)]\s+)?\*\*(.+?)\*\*(.*)$")
_ITEM_H3_RE = re.compile(r"^\s*#{2,6}\s+\d+[.)]\s+(.+?)\s*$")
_HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")
#: An outlet tail after a bold title: short, no sentence inside it.
_OUTLET_TAIL_RE = re.compile(r"^\s*[—–:\-|]\s*[^.!?]{1,60}$")


def _digest_item_titles(digest_text: str) -> List[str]:
    """Every story title the digest's own item headings carry, in order.

    ``engine.grok_imagine.extract_story_headlines`` stops at twelve (the hook
    included) and drops a bold line over 70 characters that carries its
    outlet as ``— Phys.org`` rather than ``: Phys.org`` — so Fascinating
    Frontiers Ep225 offered ONE title for nine stories. Chapters need every
    item's title; this reads them straight from the item headings.
    """
    out: List[str] = []
    seen: set = set()
    for line in (digest_text or "").splitlines():
        if line.lstrip().startswith(">"):
            continue  # the hook: a sentence, never an item title
        m = _ITEM_H3_RE.match(line)
        if m:
            raw = m.group(1)
        else:
            m = _ITEM_BOLD_RE.match(line)
            if not m:
                continue
            numbered, bold, rest = m.group(1), m.group(2).strip(), m.group(3)
            # Oct 28 2026: the number may sit INSIDE the bold
            # ("**1. Satellites close to … — r/space**"); every Fascinating
            # Frontiers Ep235 chapter title opened "1.", "3.", "11.". The
            # number is the item's place in the list, never its title.
            inner = re.match(r"^\d{1,2}[.)]\s+(?=\S)", bold)
            if inner:
                numbered, bold = numbered or inner.group(0), bold[inner.end():]
            if bold.endswith(":"):
                # ``**Title:** Outlet`` — a title only when the rest is an
                # outlet name, never a label introducing a sentence.
                tail = rest.strip()
                if (not tail or len(tail.split()) > 6 or tail.endswith(".")
                        or re.search(r"[$%€£¥▲▼]", tail)):
                    continue
                bold = bold[:-1]
            elif rest.strip() and not numbered and not _OUTLET_TAIL_RE.match(rest):
                continue  # a bold lead-in to a sentence, not a heading
            raw = bold.strip("[]").replace("]:", ":").replace("] ", " ")
        if raw.lstrip().startswith("#"):
            # Oct 21 2026: ``**# Models & Agents**`` is the digest's title,
            # bold-wrapped — Ep210 shipped a chapter named "# Models & Agents".
            continue
        title = _clean_item_title(raw)
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        out.append(title)
    return out


#: A digest heading that numbers a slot ("Segment 2 — Why It Costs…",
#: First Principles) is a placeholder, never a chapter title.
_PLACEHOLDER_TITLE_RE = re.compile(r"^(?:segment|part|section|item|story)\s+\d+\b", re.IGNORECASE)


def _clean_item_title(raw: str) -> str:
    """An item heading as a chapter title: links flattened, the outlet tail
    dropped, never shortened otherwise. ``""`` when it is not a title (under
    three words, cut inside its own parenthesis — "iShares A.I. Innovation
    and Tech ETF (TSX" on Modern Investing Ep201 — or a numbered slot)."""
    try:
        from engine.grok_imagine import (
            _strip_bold_line_source_tail, _strip_source_suffix,
        )
    except Exception:  # noqa: BLE001 — chapters never raise
        return ""
    raw = _MD_LINK_RE.sub(lambda mm: mm.group(1), raw or "")
    raw = raw.strip()
    # A quoted tail after the colon is the headline's own subtitle ("…
    # Cybertruck: 'People Prefer Car'"), never an outlet.
    if not re.search(r":\s*['\"‘’“”]", raw):
        raw = _strip_bold_line_source_tail(raw)
    raw = _strip_source_suffix(raw)
    # A longer outlet tail inside the bold ("…34 children: The Globe and
    # Mail", Top World): at most five capitalised words after the LAST
    # colon, no digit, no quote — a subtitle reads otherwise.
    head, sep, tail = raw.rpartition(": ")
    if (sep and len(head) >= 20 and 1 <= len(tail.split()) <= 5 and len(tail) <= 40
            and re.match(r"^[A-Z]", tail) and not re.search(r"[\d'\"‘’“”?!]", tail)
            and all(w[:1].isupper() or w.lower() in ("and", "of", "the", "de", "la", "le")
                    for w in tail.split())):
        raw = head
    title = _whole_title(raw).rstrip(":.,;").strip()
    if (len(title.split()) < 3
            or title.count("(") != title.count(")")
            or title.count("[") != title.count("]")
            or _PLACEHOLDER_TITLE_RE.match(title)):
        return ""
    return title


def _marker_field(marker, name: str) -> str:
    if hasattr(marker, name):
        return getattr(marker, name) or ""
    if isinstance(marker, dict):
        return marker.get(name, "") or ""
    return ""


def _norm_heading(text: str) -> str:
    t = re.sub(r"[*_`#]+", "", text or "").strip().lower()
    t = re.sub(r"\s*\(\d+\)\s*$", "", t)
    return " ".join(t.replace("&", "and").split())


def _section_marker_title(section: str, section_markers: list) -> str:
    """The marker title that names the digest section *section*: a marker
    whose ``digest_section`` or title the heading starts with ("Cosmic Deep
    Dive: Self-Interacting Dark Matter" -> "Cosmic Deep Dive"). Opening and
    closing markers never name a body section."""
    head = _norm_heading(section)
    if not head:
        return ""
    for marker in section_markers or []:
        if _marker_field(marker, "where") in ("start", "end"):
            continue
        title = _marker_field(marker, "title")
        for name in (_marker_field(marker, "digest_section"), title):
            n = _norm_heading(name)
            if n and (head == n or head.startswith(n + " ") or head.startswith(n + ":")):
                return title
    # Oct 28 2026: a heading the marker's own SPOKEN pattern names is that
    # marker's section when the pattern matches the whole heading. SpaceX's "### Engineering Deep Dive" is chaptered by
    # the "engineering deep dive|engineering angle…" marker titled "The
    # Engineering Angle"; with neither name matching, the heading itself
    # became a second chapter title, and Ep143 carried "Engineering Deep
    # Dive" at 0:42 — inside the lead, whose Raptor 4 story the deep dive
    # explains — beside the real "The Engineering Angle" at 6:58.
    for marker in section_markers or []:
        if _marker_field(marker, "where") in ("start", "end"):
            continue
        pattern = _marker_field(marker, "pattern")
        if not pattern:
            continue
        try:
            # The WHOLE heading, never a word inside it: the spoken patterns
            # are loose ("regulatory", "news") and a search mapped Env
            # Intel's "Regulatory Calendar" onto another marker's title.
            if re.fullmatch(pattern, head, re.IGNORECASE):
                return _marker_field(marker, "title")
        except re.error:
            continue
    return ""


def _story_units_context(lines: List[str], digest_text: str):
    """``(units, assigned, boundaries, positions, kept)`` or None.

    *kept* are the script's non-empty lines (the story-change detector's
    line index) and *positions* their ``(word_idx, char_offset)`` in
    parse_chapters' accounting.
    """
    from engine import story_breaks as sb
    units = sb.story_units(digest_text)
    if len(units) < 2:
        return None
    kept: List[str] = []
    positions: List[tuple] = []
    w = c = 0
    for line in lines:
        if line.strip():
            kept.append(line.strip())
            positions.append((w, c))
        w += len(line.split())
        c += len(line)
    if not kept:
        return None
    assigned = sb._assign(kept, units)
    boundaries = sb.story_boundary_lines("\n".join(kept), digest_text)
    return units, assigned, boundaries, positions, kept


def _confident(assigned_entry, line: str, unit) -> bool:
    from engine import story_breaks as sb
    u, score = assigned_entry
    return (u >= 0 and score >= sb.MIN_ASSIGN_SCORE
            and len(sb._tokens(line) & unit.tokens) >= sb.MIN_ASSIGN_TOKENS)


def _unit_titles(units, candidates: List[str], max_chars: int) -> dict:
    """``{unit_index: whole title or ""}`` for every item unit a title names.

    A title belongs to the item unit that carries most of its words (the
    item's own heading is part of the unit's text). A title over the budget
    is still matched — so its unit is known to have one — and then left
    empty: a headline is a chapter title whole or not at all.
    """
    from engine import story_breaks as sb
    best_for_unit: dict = {}
    for idx, title in enumerate(candidates):
        if _is_hook_candidate(title, idx, max_chars):
            continue
        if title.count("(") != title.count(")") or title.count("[") != title.count("]"):
            continue  # cut inside its own parenthesis ("… ETF (TSX"): not a title
        toks = sb._tokens(title)
        if len(toks) < 2:
            continue
        # Every unit competes: an unsourced item reads as an "essay" to the
        # story detector (Modern Investing's Quick Hits), and a title that
        # could only land on a sourced item went to the wrong one.
        # A numbered story HEADING ("### 3) Aid groups warn…", Omni View) is
        # the story's title and is not in its unit's text: it counts too.
        scored = [(len(toks & (u.tokens | (sb._tokens(u.section)
                                           if re.match(r"^\d+[.)]\s", u.section or "")
                                           else frozenset()))), i)
                  for i, u in enumerate(units)]
        if not scored:
            continue
        # Ties go to the SMALLER story: a headline's words all sit in its own
        # item and, now and then, in a long essay that mentions it (Modern
        # Investing Ep198's Strategy Spotlight carried every word of the
        # "US Treasury Sanctions ICC…" quick hit).
        hit, _density, i = max(
            ((h, h / max(1, len(units[j].tokens)), j) for h, j in scored),
            key=lambda x: (x[0], x[1], -x[2]))
        if hit < max(2, -(-len(toks) * 6 // 10)):
            continue
        cov = hit / len(toks)
        if i not in best_for_unit or cov > best_for_unit[i][0]:
            best_for_unit[i] = (cov, title)
    out = {}
    for i, (_cov, title) in best_for_unit.items():
        whole = _whole_title(title)
        out[i] = whole if len(whole) <= max_chars else ""
    # A title on its own paragraph (Top World writes "**Title: Outlet**", a
    # blank line, then the story) is a unit of its own to the story map; it
    # names the story told in the unit right after it.
    for i in sorted(out):
        unit = units[i]
        if (i + 1 < len(units) and i + 1 not in out
                and unit.words <= len(_whole_title(best_for_unit[i][1]).split()) + 6
                and units[i + 1].section == unit.section):
            out[i + 1] = out[i]
    return out


def _title_candidates(story_headlines: List[str], digest_text: str) -> List[str]:
    """``story_headlines`` (the hook first, untouched) cleaned like the
    digest's own item headings, then every item heading they miss."""
    heads = list(story_headlines or [])[:1]
    for h in list(story_headlines or [])[1:]:
        t = _clean_item_title(h)
        if t and t.lower() not in {x.lower() for x in heads}:
            heads.append(t)
    have = {h.lower() for h in heads}
    return heads + [t for t in _digest_item_titles(digest_text) if t.lower() not in have]


def _story_break_insertions(
    ctx, digest_text: str, section_markers: list, story_headlines: List[str],
    lo_word: int, hi_word: int, max_chars: int = HEADLINE_TITLE_MAX,
) -> list:
    """Chapters where the episode's stories begin, titled by the story.

    Oct 17 2026. Headline anchoring matched a headline to the paragraph that
    shared the most words with it — often a story's second or third
    sentence (Tesla Ep637's Q3 preview chapter opened on "The constraint is
    laid out…"), merged any story told in under sixty words into the one
    before it, and only ever split the OPENING chapter — so a show whose
    markers matched (Planetterrian's deep dive, AI Chips' Teardown) shipped
    eight news stories inside one deep-dive chapter. The network already
    knows where every story starts: the story-change detector that places
    the audio beat (``engine.story_breaks.story_boundary_lines``). Each beat
    inside the body becomes a chapter when its story has a title — the
    item's headline, whole, or for an essay section the marker that names the
    section (else its heading, whole). No title, no chapter: the text stays
    in the chapter before it. Returns ``[(word_idx, char_offset, title)]``.
    """
    if ctx is None:
        return []
    units, assigned, boundaries, positions, _kept = ctx
    item_titles = _unit_titles(units, _title_candidates(story_headlines, digest_text),
                               max_chars)
    headings: dict = {}
    first_heading = ""
    for line in (digest_text or "").splitlines():
        m = _HEADING_RE.match(line)
        if m:
            key = re.sub(r"[*_`]+", "", m.group(2)).strip().lower()
            headings.setdefault(key, (len(m.group(1)), _whole_title(m.group(2))))
            if not first_heading and len(m.group(1)) >= 2:
                first_heading = key
    # A story told twice (a one-line callback inside another segment, then
    # its own telling) gets its chapter where it is TOLD: per story, the
    # first beat that opens two or more of its lines (Modern Investing
    # Ep203's Investor Education was named in one line of the trade review
    # long before its own segment); a story only ever mentioned in single
    # lines takes its first beat.
    kept = ctx[4]
    starts = set(boundaries) | set(_short_item_starts(ctx, section_markers))
    usable = [k for k in sorted(starts) if k < len(positions)
              and lo_word < positions[k][0] < hi_word and assigned[k][0] >= 0]
    best: dict = {}
    for n, k in enumerate(usable):
        u = assigned[k][0]
        stop = usable[n + 1] if n + 1 < len(usable) else len(kept)
        run = sum(1 for j in range(k, stop)
                  if assigned[j][0] == u and _confident(assigned[j], kept[j], units[u]))
        if u not in best or (best[u][1] < 2 <= run):
            best[u] = (k, run)
    first_item_of_section: dict = {}
    for i, unit in enumerate(units):
        if unit.label == "item" and unit.section:
            first_item_of_section.setdefault(unit.section, i)
    out: list = []
    used: set = set()
    for k in usable:
        u = assigned[k][0]
        if best[u][0] != k:
            continue
        w, c = positions[k]
        unit = units[u]
        if u in item_titles:
            title = item_titles[u]  # the story's own headline, whole, or none
        elif unit.label == "item":
            title = ""
            if first_item_of_section.get(unit.section) == u:
                # An untitled story that opens a section a marker names
                # (Modern Investing's Strategy Spotlight is one sourced
                # paragraph) is where that section starts.
                title = _section_marker_title(unit.section, section_markers)
        else:
            title = _section_marker_title(unit.section, section_markers)
            if not title:
                level, heading = headings.get(unit.section, (0, ""))
                if (level >= 2 and unit.section != first_heading
                        and 4 <= len(heading) <= max_chars
                        and not re.match(r"^\d+[.)]", heading)
                        and not _PLACEHOLDER_TITLE_RE.match(heading)):
                    title = heading
        if not title or title in used:
            continue
        used.add(title)
        out.append((w, c, title, None if u in item_titles else unit.section))
    return [(w, c, t) for w, c, t, _s in _in_section_order(out, units)]


def _short_item_starts(ctx, section_markers: list) -> List[int]:
    """Lines that open a one- or two-sentence story the beat detector folds
    into its neighbours.

    The audio beat skips a run of short items under one heading (a pause
    between one-liners reads as a stutter), so on Omni View Top World the
    one-sentence items six to ten — five stories — sat in one chapter titled
    with the first of them. A chapter is navigation, not a pause: each short
    item opens its own, unless a marker already names the block they sit in
    (the desks' "Also Today") — then the block's chapter is the navigation.
    """
    from engine import story_breaks as sb
    units, assigned, _b, _p, kept = ctx
    confident = [(k, assigned[k][0]) for k in range(len(kept))
                 if assigned[k][0] >= 0
                 and _confident(assigned[k], kept[k], units[assigned[k][0]])]
    out: List[int] = []
    for n in range(1, len(confident)):
        k, u = confident[n]
        prev = confident[n - 1][1]
        if u == prev:
            continue
        nxt = confident[n + 1][1] if n + 1 < len(confident) else None
        unit = units[u]
        if (nxt == prev
                or _section_marker_title(unit.section, section_markers)
                or sb.opens_as_continuation(kept[k])):
            continue
        # A short item, or a one-line telling the map is sure of (Top World
        # Ep024's one-liners carry 15-46 points of evidence; a stray market
        # line on Modern Investing scores 4.5).
        strong = (assigned[k][1] >= SHORT_STORY_MIN_SCORE
                  and len(sb._tokens(kept[k]) & unit.tokens) >= 4)
        if sb._is_short_item(unit) or strong:
            out.append(k)
    return out


#: Evidence (the story map's weighted score) a single line needs to open a
#: chapter the audio beat did not mark.
SHORT_STORY_MIN_SCORE = 12.0


def _in_section_order(entries: list, units) -> list:
    """Drop section chapters that run against the digest's section order.

    A narrative script tells its segments in the digest's order, but its
    vocabulary crosses them: Unintended Consequences Ep143's story map put
    "The Good Intention" (segment 2) at 750 s, after "The Aftermath"
    (segment 5). Section-titled entries keep the longest run that follows
    the digest order; story-titled entries (news items, told in any order)
    are untouched.
    """
    # Only a digest that NUMBERS its segments ("Segment 2 — The Good
    # Intention", the narrative shows) declares an order; Modern Investing
    # airs its sections in a different order than it writes them.
    order: dict = {}
    for u in units:
        if (u.section and u.section not in order
                and _PLACEHOLDER_TITLE_RE.match(u.section)):
            order[u.section] = len(order)
    idx = [i for i, e in enumerate(entries) if e[3] is not None and e[3] in order]
    if len(idx) < 2:
        return entries
    seq = [order[entries[i][3]] for i in idx]
    # Longest strictly increasing subsequence (n is tiny).
    best = [1] * len(seq)
    prev = [-1] * len(seq)
    for j in range(len(seq)):
        for i in range(j):
            if seq[i] < seq[j] and best[i] + 1 > best[j]:
                best[j], prev[j] = best[i] + 1, i
    j = max(range(len(seq)), key=lambda x: (best[x], -x))
    keep = set()
    while j >= 0:
        keep.add(idx[j])
        j = prev[j]
    return [e for i, e in enumerate(entries) if e[3] is None or i in keep
            or e[3] not in order]


def _marker_section_misfires(ctx, matches: list, section_markers: list) -> set:
    """Marker matches that fired inside ANOTHER section's content.

    Oct 17 2026: Modern Investing Ep203 opened "Trade Review & Lessons" on
    "Enbridge… is today's simulated weekly hold" (the pick) and "Practice
    Investment of the Day" on the pick's closing disclaimer, where the trade
    review began — the two labels swapped. A body marker whose line the
    story detector confidently places in a digest section that a DIFFERENT
    marker names is not where its own section starts; it is dropped, and the
    section's own story chapter takes its place. Returns ``{(word, title)}``.
    """
    if ctx is None:
        return set()
    units, assigned, _boundaries, positions, kept = ctx
    at_word = {}
    for i, (w, _c) in enumerate(positions):
        at_word.setdefault(w, i)
    where = {_marker_field(m, "title"): _marker_field(m, "where")
             for m in section_markers or []}
    bad = set()
    for w, _c, title in matches:
        if where.get(title) in ("start", "end"):
            continue
        k = at_word.get(w)
        if k is None:
            continue
        u = assigned[k][0]
        if u < 0 or not _confident(assigned[k], kept[k], units[u]):
            continue
        other = _section_marker_title(units[u].section, section_markers)
        if other and other != title:
            bad.add((w, title))
    return bad


#: A story chapter this close to a chapter that already starts there is the
#: same change (a section opener spoken on the line before the story).
STORY_CHAPTER_MIN_GAP_WORDS = 25
_TAIL_TITLES = ("closing", "sign-off", "tomorrow teaser", "teaser",
                "завершение", "прощание")


def _apply_story_chapters(
    chapters: List["Chapter"], ctx, digest_text: str, section_markers: list,
    story_headlines: List[str], total_words: int, total_chars: int,
) -> tuple:
    """``(chapters, placed)``: *chapters* with a chapter at every titled
    story change in the body (``_story_break_insertions``). *placed* is True
    when the detector found any titled story change, in which case its
    chapters are the episode's segmentation.

    A story chapter titled like a section marker that also matched LATER in
    the same run moves the marker's chapter back to where the section's
    content begins (nothing else may start between them); a marker that
    matched earlier keeps its place — the spoken opener leads the content.
    """
    body_end = next((c.word_start for c in chapters
                     if c.title.strip().lower() in _TAIL_TITLES), total_words)
    inserts = _story_break_insertions(
        ctx, digest_text, section_markers, story_headlines,
        chapters[0].word_start, body_end)
    if not inserts:
        return chapters, False
    bounds = [[c.word_start, c.char_start, c.title] for c in chapters]
    all_starts = sorted({b[0] for b in bounds} | {w for w, _c, _t in inserts})
    added: list = []
    for w, c, t in inserts:
        same = next((b for b in bounds if b[2] == t), None)
        if same is not None:
            if w < same[0] and not any(w < x < same[0] for x in all_starts):
                same[0], same[1] = w, c
            continue
        if any(abs(w - b[0]) < STORY_CHAPTER_MIN_GAP_WORDS for b in bounds + added):
            continue
        added.append([w, c, t])
    merged = sorted(bounds + added, key=lambda b: b[0])
    out: List[Chapter] = []
    for i, (w, c, t) in enumerate(merged):
        nw = merged[i + 1][0] if i + 1 < len(merged) else total_words
        nc = merged[i + 1][1] if i + 1 < len(merged) else total_chars
        out.append(Chapter(title=t, word_start=w, word_end=nw, char_start=c, char_end=nc))
    return out, True


def _opening_paragraph(text: str, max_words: int = 80) -> str:
    """The first paragraph of *text* (at most *max_words* words): what a
    segment opens on. Oct 17 2026: a fixed-interval segment was titled with
    whichever headline its whole text echoed most, so Fascinating Frontiers
    Ep225's "NASA's Hubble spies spiral's edge" opened at 108 s inside the
    deep dive while the Hubble story began at 183 s. A segment takes a
    headline only when it OPENS on that story."""
    for para in re.split(r"\n[ \t]*\n", text or ""):
        if para.strip():
            return " ".join(para.split()[:max_words])
    return ""


def _lead_section_for_hook(digest_text: str, story_headlines: List[str]) -> tuple:
    """``(lead section name, lead text tokens)`` — both empty unless the
    digest's first section holds the hook's story.

    ``lead_section_name`` reads the digest's FIRST heading. On the desks
    that heading is the lead's slot ("Lead", "Top Story"); on Fascinating
    Frontiers the news items sit above any heading and the first heading is
    the Cosmic Spotlight, a different story — so Ep224/225 titled the El
    Gordo lead "Cosmic Spotlight" (Oct 17 2026). The section is the lead's
    only when its first paragraph shares two words with the hook (or, with
    no hook, with the first headline).
    """
    name = lead_section_name(digest_text)
    toks = lead_block_tokens(digest_text)
    if not story_headlines:
        return name, toks
    ref = _tokenize_for_match(story_headlines[0])
    if len(ref & toks) >= 2:
        return name, toks
    return "", set()


def _hook_unit(ctx, story_headlines: List[str]) -> int:
    """The story-map unit the hook (the first, sentence-length headline)
    tells, or -1 when there is no map, no hook, or no clear match."""
    if ctx is None or not story_headlines:
        return -1
    if not _is_hook_candidate(story_headlines[0], 0, HEADLINE_TITLE_MAX):
        return -1
    from engine import story_breaks as sb
    (hu, score), = sb._assign([story_headlines[0]], ctx[0])
    if hu < 0 or score < sb.MIN_ASSIGN_SCORE:
        return -1
    return hu


def _hook_story_words(ctx, story_headlines: List[str]) -> set:
    """Word positions of the script lines the story map confidently places in
    the hook's story. Fascinating Frontiers Ep225's lead resumed after the
    identity line with "El Gordo, as the cluster is nicknamed, contains two
    colliding regions…" — no word of the hook, every word of its item — and
    the lead chapter opened two sentences late."""
    hu = _hook_unit(ctx, story_headlines)
    if hu < 0:
        return set()
    units, assigned, _b, positions, kept = ctx
    return {positions[k][0] for k in range(len(kept))
            if assigned[k][0] == hu and _confident(assigned[k], kept[k], units[hu])}


def _headlines_off_hook(ctx, story_headlines: List[str], digest_text: str) -> set:
    """Headlines the story map places in a different story than the hook.

    AI Chips Ep026's hook ("Second Arizona fab volume production begins…")
    shared "second" and "fab" with "Samsung's second Taylor fab is lined up
    for an early-November start", which titled the TSMC lead with the
    Samsung story (Oct 17 2026). The hook is matched to its digest story by
    the story detector's weighted vocabulary, each headline to the item that
    carries it; a headline whose item is not the hook's story is excluded.
    Empty when there is no story map or the hook matches no story clearly.
    """
    hu = _hook_unit(ctx, story_headlines)
    if hu < 0:
        return set()
    units = ctx[0]
    titles = _unit_titles(units, story_headlines[1:], 10 ** 6)
    by_title: dict = {}
    for u, t in titles.items():
        by_title[t] = u
    from engine import story_breaks as sb
    hook_best = sb._unit_score(story_headlines[0], units, hu)
    # The hook lands in the digest's lead slot (its first section): every
    # headline of another item is another story — Prediction Markets Ep025's
    # CFTC lead had been titled with the SpaceX-IPO market. Elsewhere (a deep
    # dive on the lead's subject can outscore the lead's own item, SpaceX
    # Ep126) a headline is excluded only when the hook reads less than half
    # as much like its item.
    first_section = next((u.section for u in units if u.section), "")
    in_lead_slot = bool(first_section) and units[hu].section == first_section
    out = set()
    for h in story_headlines[1:]:
        u = by_title.get(_whole_title(h))
        if u is None or u == hu:
            continue
        if in_lead_slot or (sb._unit_score(story_headlines[0], units, u)
                            < OFF_HOOK_SCORE_SHARE * hook_best):
            out.add(h)
    return out


#: See ``_headlines_off_hook``.
OFF_HOOK_SCORE_SHARE = 0.5


def parse_chapters(
    script: str,
    section_markers: list,
    *,
    show_name: str = "",
    min_chapters: int = 4,
    auto_segment_target_seconds: float = 90.0,
    estimated_words_per_minute: float = 165.0,
    story_headlines: Optional[List[str]] = None,
    known_sections_only: bool = False,
    digest_text: str = "",
) -> List[Chapter]:
    """Parse a podcast script to identify section boundaries.

    Parameters
    ----------
    script:
        The cleaned podcast script text (after speaker prefix removal,
        pronunciation fixes, etc.).
    section_markers:
        List of ``SectionMarker`` objects (or dicts with ``pattern`` and
        ``title`` keys) from the show's YAML config.
    show_name:
        Show name for logging context.
    digest_text:
        The episode digest. Used only by markers that set
        ``digest_section``: when such a marker's phrase is not spoken, the
        chapter starts where that digest section's content begins.

    Returns
    -------
    list[Chapter]
        Ordered list of chapters with word boundaries set.  Timestamps
        are set to 0 — call ``calculate_timestamps()`` after the audio
        is produced to map word proportions to real timestamps.
    """
    if not section_markers:
        logger.info("No section markers configured — skipping chapter parsing")
        return []
    # A headline cut inside its own parenthesis ("iShares A.I. Innovation and
    # Tech ETF (TSX", Modern Investing Ep201) is not a title anywhere below.
    # The first entry stays: it is the hook slot, whatever its shape.
    story_headlines = [
        h for i, h in enumerate(story_headlines or [])
        if i == 0 or (h.count("(") == h.count(")") and h.count("[") == h.count("]"))
    ]

    # Build compiled patterns
    compiled_markers = []
    for marker in section_markers:
        pattern = marker.pattern if hasattr(marker, "pattern") else marker.get("pattern", "")
        title = marker.title if hasattr(marker, "title") else marker.get("title", "")
        where = marker.where if hasattr(marker, "where") else (
            marker.get("where", "") if isinstance(marker, dict) else ""
        )
        if not pattern or not title:
            continue
        try:
            compiled_markers.append((re.compile(pattern, re.IGNORECASE), title, where or ""))
        except re.error as exc:
            logger.warning("Invalid chapter marker regex %r: %s", pattern, exc)

    if not compiled_markers:
        return []

    # Split script into words with their character positions
    words = script.split()
    total_words = len(words)
    total_chars = len(script)
    if total_words == 0:
        return []

    # Scan line by line, tracking both word index and character offset
    lines = script.splitlines(keepends=True)
    word_idx = 0
    char_offset = 0
    matches: list[tuple[int, int, str]] = []  # (word_index, char_offset, title)
    matched_titles: set[str] = set()

    # Positional windows for ``where``-constrained markers. The opening
    # window is generous (10%, min 60 words) so a long cold-open hook
    # can't push the intro line out of range; the closing window (last
    # 15%) comfortably covers teaser + sign-off on a 1500+-word script.
    #
    # July 16 2026: the end window is additionally floored at the last
    # 250 words. The code-appended tail AFTER the spoken sign-off
    # (network cross-promo + site CTA + AI disclosure) is a FIXED
    # ~120-180 words, so on short scripts it eats more than 15% and
    # pushes the real closing line out of the percentage window — MAB
    # shipped 5 of 14 July episodes with NO Closing chapter because
    # "that's a wrap" landed at ~84% of words. On 1500+-word scripts
    # min() keeps the original 85% behavior.
    start_window_end = max(int(total_words * 0.10), 60)
    end_window_start = min(int(total_words * 0.85), max(total_words - 250, 0))

    # Oct 20 2026: the MAP — one sentence right after the identity line
    # naming the stories and segments still to come (engine.intros
    # build_cold_open_spec) — speaks the segments' own anchor phrases.
    # SpaceX Ep136's "…and later the engineering angle on first-stage
    # reuse" fired "The Engineering Angle" at 11 s and the real deep dive
    # at 301 s fell back to its digest heading. A marker other than a
    # ``start`` one never matches on the identity line or the line after it.
    map_lines: set = set()
    seen_text = 0
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        seen_text += 1
        if _MAP_IDENTITY_RE.match(line.strip()):
            map_lines.add(i)
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    map_lines.add(j)
                    break
            break
        if seen_text >= _MAP_IDENTITY_SEARCH_LINES:
            break

    for line_i, line in enumerate(lines):
        line_words = line.split()
        line_word_count = len(line_words)
        line_stripped = line.rstrip("\n\r")

        for regex, title, where in compiled_markers:
            # Each semantic section appears once per episode. Without
            # this, brand mentions late in the script re-trigger early
            # markers (the Tesla closing was titled "Introduction" on
            # every episode through Ep505).
            if title in matched_titles:
                continue
            if line_i in map_lines and where != "start":
                continue
            if where == "start" and word_idx > start_window_end:
                continue
            if where == "end" and word_idx < end_window_start:
                continue
            # ``body`` (Sep 23 2026): never inside the opening window.
            # Vancouver Ep1's debut explainer said "…what those decisions
            # mean for getting around" at 16 s, the segment anchor matched
            # there, and five minutes of provincial politics shipped under
            # a "Getting Around" chapter.
            if where == "body" and word_idx <= start_window_end:
                continue
            if regex.search(line_stripped):
                matches.append((word_idx, char_offset, title))
                matched_titles.add(title)
                break  # Only match first marker per line

        word_idx += line_word_count
        char_offset += len(line)

    # Where every story starts (Oct 17 2026): the story-change detector's
    # map of the script onto the digest's stories. Used to drop a marker
    # that fired inside another section's content, to put a chapter at
    # every titled story change, and to keep the lead's title on the lead's
    # own story. ``None`` (no digest, fewer than two stories, any error)
    # leaves every path below exactly as it was.
    story_ctx = None
    if digest_text:
        try:
            story_ctx = _story_units_context(lines, digest_text)
        except Exception as exc:  # noqa: BLE001 — chapters are metadata
            logger.warning("Story map unavailable for chapters (%s): %s",
                           show_name or "show", exc)
            story_ctx = None
    if story_ctx is not None and matches:
        misfires = _marker_section_misfires(story_ctx, matches, section_markers)
        if misfires:
            logger.info(
                "Dropping %d marker chapter(s) that fired inside another "
                "section's content for %s: %s", len(misfires),
                show_name or "show", sorted(t for _w, t in misfires))
            matches = [m for m in matches if (m[0], m[2]) not in misfires]
            matched_titles = {t for _w, _c, t in matches}

    # Digest-section fallback (Oct 5 2026): a marker that names its digest
    # heading still gets its chapter when the phrase was skipped. Body only
    # — never inside the opening window, never in the closing window.
    if digest_text:
        for marker in section_markers:
            heading = (marker.digest_section if hasattr(marker, "digest_section")
                       else (marker.get("digest_section", "")
                             if isinstance(marker, dict) else ""))
            title = (marker.title if hasattr(marker, "title")
                     else marker.get("title", "") if isinstance(marker, dict)
                     else "")
            if not heading or not title or title in matched_titles:
                continue
            found = _digest_section_anchor(
                lines, digest_text, heading,
                start_window_end + 1, end_window_start)
            if found is None or any(w == found[0] for w, _c, _t in matches):
                continue
            matches.append((found[0], found[1], title))
            matched_titles.add(title)
            logger.info(
                "Chapter '%s' anchored on its digest section (spoken "
                "marker absent) at word %d for %s",
                title, found[0], show_name or "show")
        matches.sort(key=lambda m: m[0])

    if not matches:
        logger.info("No chapter markers matched in podcast script for %s", show_name)
        return []

    # A `where: end` chapter (the Closing/Sign-Off) is FINAL: nothing may
    # start after it. The rotating network cross-promo outro (July 16 2026)
    # names sibling shows AFTER the closing, and un-anchored body markers
    # were stealing those mentions as spurious final chapters — Tesla Ep544
    # shipped a "First Principles" chapter at 642s (after Closing at 616s)
    # from the promo line "try First Principles Daily next", and MIT Ep104
    # an "Investor Education" chapter from the promo's "daily deep dive"
    # (July 18 2026 network review). Same theft class FF fixed June 24 by
    # dropping bare markers — this closes it engine-wide.
    # The terminal signal is the closing TITLE (network convention — same
    # set the snapshot checker accepts), NOT the `where: end` anchor: EI
    # deliberately anchors only its Tomorrow Teaser while its Closing
    # marker is position-free, and a teaser may legitimately precede the
    # closing. Cut at the LAST closing-titled match.
    _terminal = ("closing", "sign-off", "завершение", "прощание")
    closing_positions = [
        w for w, _c, t in matches if t.strip().lower() in _terminal
    ]
    if closing_positions:
        closing_at = max(closing_positions)
        stolen = [t for w, _c, t in matches if w > closing_at]
        if stolen:
            logger.warning(
                "Dropping %d chapter(s) starting after the closing "
                "(promo-tail marker theft): %s", len(stolen), stolen,
            )
            matches = [m for m in matches if m[0] <= closing_at]

    # The opening must belong to a chapter (Sep 22 2026, new-show Ep1s).
    # When no ``where: start`` marker matches inside the opening window,
    # the first matched marker is a mid-episode section, and everything
    # before it — the hook, the identity line and every news story —
    # belonged to no chapter at all: AI Chips Ep1's chapters began at
    # 343 s ("The Teardown"), Longevity Ep1's at 326 s. Auto-segmentation
    # only ever splits the FIRST chapter, so it could not recover them.
    # A synthetic opening chapter (titled like the show's own start
    # marker) now covers that span, and the fallback below splits it on
    # the digest headlines like any long Introduction. Only for shows that
    # configure a start marker: a show without one keeps the legacy shape
    # (split_script_at_chapters' "Preamble" section for section-TTS).
    _start_titles = [t for _r, t, w in compiled_markers if w == "start"]
    if _start_titles and matches[0][0] > start_window_end:
        _open_title = _start_titles[0]
        if _open_title in {t for _w, _c, t in matches}:
            _open_title = "Opening"
        matches.insert(0, (0, 0, _open_title))
        logger.info(
            "No start marker matched for %s — opening covered by a "
            "synthetic '%s' chapter up to word %d",
            show_name or "show", _open_title, matches[1][0],
        )

    # Build Chapter objects from matches
    chapters: list[Chapter] = []
    for i, (w_start, c_start, title) in enumerate(matches):
        w_end = matches[i + 1][0] if i + 1 < len(matches) else total_words
        c_end = matches[i + 1][1] if i + 1 < len(matches) else total_chars
        chapters.append(Chapter(
            title=title,
            word_start=w_start,
            word_end=w_end,
            char_start=c_start,
            char_end=c_end,
        ))

    # Story chapters (Oct 17 2026): a chapter at every titled story change
    # inside the body, from the same detector that places the audio beat.
    # When it places any, it IS the segmentation — the headline anchoring
    # and fixed-interval fallbacks below run only where it cannot.
    story_done = False
    if story_ctx is not None and chapters:
        try:
            chapters, story_done = _apply_story_chapters(
                chapters, story_ctx, digest_text, section_markers,
                story_headlines or [], total_words, total_chars)
        except Exception as exc:  # noqa: BLE001 — chapters are metadata
            logger.warning("Story chapters skipped for %s: %s",
                           show_name or "show", exc)
            story_done = False
        if story_done:
            logger.info("Story chapters for %s: %s", show_name or "show",
                        [c.title for c in chapters])

    # ------------------------------------------------------------------
    # Auto-segmentation fallback. Operator caught (May 2026) that TST
    # episodes ship with only ``Introduction`` + ``Closing`` chapters
    # because the per-show ``section_markers`` regex don't tolerate the
    # variations the LLM and Whisper produce. The result was a 7-minute
    # block called "Introduction" with no nav. When the matched chapter
    # count is below ``min_chapters`` OR the first chapter spans most
    # of the script (≥50% of words — Ep537 had 4 markers so cleared
    # min_chapters but Introduction still covered 9 of 13 minutes), we
    # splice extra chapters at paragraph boundaries roughly every
    # ``auto_segment_target_seconds`` of speech so listeners always get
    # useful navigation. May 8 2026: titles now derive from each
    # segment's first sentence (truncated to ~50 chars) instead of the
    # previous generic ``Segment N`` placeholder — Apple Podcasts and
    # Pocket Casts surface chapter titles in the player UI, and
    # "Segment 2" tells the listener nothing about whether to skip ahead.
    head_spans_most = bool(
        chapters
        and total_words > 0
        and (chapters[0].word_end - chapters[0].word_start)
        >= int(total_words * 0.50)
    )
    # Aug 27 2026 (spacex Ep077): shows whose prompts speak a full, fixed
    # section set opt out of auto-segmentation entirely — every inserted
    # chapter would carry a digest headline / first-sentence title outside
    # the known section set, which ships as listener-facing spam in the
    # chapter UI ("SpaceX is hiring for natural gas trading to support
    # energy…" between Introduction and Counterpoint). For those shows the
    # matched markers ARE the navigation.
    #
    # Oct 12 2026: that left SpaceX with eight news stories inside one
    # "Introduction" chapter on every episode. Such a show now gets ONE kind
    # of inserted chapter: a digest headline, anchored where that story
    # begins, used whole and only when it fits HEADLINE_CHAPTER_TITLE_MAX —
    # never the fixed-interval fallback, never a first-sentence title, never
    # a clipped headline (the three shapes the Aug 27 decision was about).
    if story_done:
        pass  # the story chapters above are this episode's segmentation
    elif known_sections_only:
        from engine.titles import HEADLINE_CHAPTER_TITLE_MAX
        anchored = []
        if chapters and story_headlines:
            # The body runs to the teaser / closing. A 4.6-written script may
            # air the Counterpoint and the deep dive straight after the lead
            # and the rest of the news after them (SpaceX Ep126), so a story
            # can sit inside ANY body chapter, not only the opening one.
            _tail_titles = ("closing", "sign-off", "tomorrow teaser", "teaser")
            body_end = next((c.word_start for c in chapters
                             if c.title.strip().lower() in _tail_titles),
                            chapters[-1].word_end)
            starts = [c.word_start for c in chapters]
            have = {c.title for c in chapters}
            anchored = [
                (w, c, t) for w, c, t in _headline_anchored_insertions(
                    lines, chapters[0].word_start, body_end, story_headlines,
                    whole_titles_max=HEADLINE_CHAPTER_TITLE_MAX, min_results=1,
                )
                # never on top of (or just after) a section's own start
                if t not in have and not any(0 <= w - s0 < 60 for s0 in starts)
            ]
        if anchored:
            last_end_w = chapters[-1].word_end
            last_end_c = chapters[-1].char_end
            bounds = sorted(
                [(c.word_start, c.char_start, c.title) for c in chapters] + anchored
            )
            chapters = [
                Chapter(title=t, word_start=w, char_start=c,
                        word_end=(bounds[i + 1][0] if i + 1 < len(bounds) else last_end_w),
                        char_end=(bounds[i + 1][1] if i + 1 < len(bounds) else last_end_c))
                for i, (w, c, t) in enumerate(bounds)
            ]
        logger.info(
            "known_sections_only: %d whole-headline story chapter(s) for %s "
            "(no other auto-segmentation)",
            len(anchored), show_name or "show",
        )
    elif (len(chapters) < min_chapters or head_spans_most) and total_words > 0:
        words_per_segment = max(
            int(estimated_words_per_minute * (auto_segment_target_seconds / 60.0)),
            120,
        )
        # Find paragraph break offsets (blank-line-separated chunks).
        para_break_word_idx: list[tuple[int, int]] = []  # (word_index, char_offset)
        idx = 0
        char_idx = 0
        for line in lines:
            line_word_count = len(line.split())
            if line.strip() == "" and idx > 0:
                para_break_word_idx.append((idx, char_idx))
            idx += line_word_count
            char_idx += len(line)

        # Build augmented chapter list — splice auto-segments into the
        # FIRST chapter (the long "Introduction") only. Splitting later
        # chapters tends to cut hand-titled sections.
        if chapters and para_break_word_idx:
            head = chapters[0]
            tail = chapters[1:]
            head_w_end = head.word_end
            head_c_end = head.char_end

            # Preferred (July 21 2026): anchor boundaries where each digest
            # story begins, so titles and positions agree by construction.
            # Falls back to fixed ~90s intervals when the script doesn't
            # echo enough headline content to anchor confidently.
            anchored = _headline_anchored_insertions(
                lines, head.word_start, head_w_end, story_headlines or [],
                whole_titles_max=HEADLINE_TITLE_MAX,
            )
            _seg_mode = "headline_anchored" if anchored else "fixed_interval"

            # (word_idx, char_offset, pre-assigned title or "")
            insertions: list[tuple[int, int, str]] = list(anchored)
            if not insertions:
                # Legacy: accept paragraph breaks inside the head chapter
                # that are at least ``words_per_segment`` words apart.
                last_w = head.word_start
                for w, c in para_break_word_idx:
                    if w <= head.word_start or w >= head_w_end:
                        continue
                    if w - last_w >= words_per_segment:
                        insertions.append((w, c, ""))
                        last_w = w

            if insertions:
                # Title preference: (1) the anchored headline, (2) a
                # matching clean digest headline (avoids mid-sentence
                # spoken fragments), (3) the segment's first sentence when
                # it is a whole sentence that stands alone. Oct 8 2026: no
                # title = no chapter break there — the text stays in the
                # chapter before it. The old "Segment N" placeholder and
                # clipped fragments told a listener nothing.
                _used_headlines: set[str] = set()
                titled: list[tuple[int, int, str]] = []
                for n, (w, c, _pre) in enumerate(insertions):
                    next_c = insertions[n + 1][1] if n + 1 < len(insertions) else head_c_end
                    seg_text = script[c:next_c]
                    title = (
                        _pre
                        or _best_headline_for_segment(
                            _opening_paragraph(seg_text), story_headlines or [],
                            _used_headlines, whole_only=True)
                        or _first_sentence_as_title(seg_text)
                    )
                    if title:
                        titled.append((w, c, title))
                if titled:
                    bounds = titled + [(head_w_end, head_c_end, "")]
                    rebuilt: list[Chapter] = [Chapter(
                        title=head.title,
                        word_start=head.word_start,
                        word_end=titled[0][0],
                        char_start=head.char_start,
                        char_end=titled[0][1],
                    )]
                    for (w, c, title), (nw, nc, _t) in zip(bounds, bounds[1:]):
                        rebuilt.append(Chapter(
                            title=title, word_start=w, word_end=nw,
                            char_start=c, char_end=nc,
                        ))
                    chapters = rebuilt + tail
                logger.info(
                    "Auto-segmented head chapter for %s into %d segments "
                    "(mode=%s, target %.0fs each, ~%d words)",
                    show_name or "show",
                    len(insertions) + 1,
                    _seg_mode,
                    auto_segment_target_seconds,
                    words_per_segment,
                )

    # The lead story gets its own chapter (Oct 8 2026). It sat inside the
    # opening chapter on 19 of 21 episodes. Skipped when a chapter already
    # carries the lead's title. On a known_sections_only show (spacex) the
    # lead's title must fit HEADLINE_CHAPTER_TITLE_MAX whole (Oct 12 2026 —
    # the Aug 27 decision was against clipped titles, not story chapters).
    #
    # Oct 17 2026: the lead's title is used whole on EVERY show (Tesla Ep637
    # shipped a clipped one); the digest's lead-section name is a fallback
    # only when that section holds the hook's story (Fascinating Frontiers'
    # first heading is its Cosmic Spotlight, a different story — Ep224/225
    # titled the El Gordo lead "Cosmic Spotlight"); and a headline the story
    # map places in another story never titles the lead (AI Chips Ep026).
    if chapters:
        head = chapters[0]
        _lead_heads = _title_candidates(story_headlines or [], digest_text)
        _lead_name, _lead_toks = _lead_section_for_hook(digest_text, _lead_heads)
        _off_hook = _headlines_off_hook(story_ctx, _lead_heads, digest_text)
        found = _lead_story_split(lines, head, _lead_heads,
                                  max_chars=HEADLINE_TITLE_MAX,
                                  whole_only=True, fallback_title=_lead_name,
                                  lead_text_tokens=_lead_toks,
                                  exclude_titles=_off_hook,
                                  lead_story_words=_hook_story_words(story_ctx, _lead_heads))
        if found and story_done:
            # A story chapter may already carry the lead's title where the
            # script came back to the lead story; the lead's own chapter is
            # the first telling (Modern Investing's lead IS its Strategy
            # Spotlight on most days: the section's chapter is the lead's).
            for k in range(len(chapters) - 1, 0, -1):
                if chapters[k].title == found[2] and chapters[k].word_start > found[0]:
                    chapters[k - 1].word_end = chapters[k].word_end
                    chapters[k - 1].char_end = chapters[k].char_end
                    del chapters[k]
            head = chapters[0]
        if found and found[2] not in {c.title for c in chapters} \
                and head.word_start < found[0] < head.word_end:
            w, c, title = found
            chapters = [
                Chapter(title=head.title, word_start=head.word_start,
                        word_end=w, char_start=head.char_start, char_end=c),
                Chapter(title=title, word_start=w, word_end=head.word_end,
                        char_start=c, char_end=head.char_end),
            ] + chapters[1:]
            logger.info("Lead story chapter for %s: %r at word %d",
                        show_name or "show", title, w)

    # Post-processing robustness (added after reviewing May 28 episodes)
    # Collapse consecutive duplicate titles (very common on quiet days).
    if chapters:
        deduped = [chapters[0]]
        for ch in chapters[1:]:
            if ch.title != deduped[-1].title:
                deduped.append(ch)
        chapters = deduped

    # Oct 21 2026: no chapter after the first starts on the identity line or
    # the map sentence, whatever path placed it. The map names the stories
    # to come, so headline anchoring matched it too: the lead chapter opened
    # on the map on six of the Oct 21 episodes (Fascinating Frontiers 10.7 s,
    # MAB 7.3 s, Top World 12.2 s) while the lead began seconds later.
    _map_line = max(map_lines) if len(map_lines) > 1 else None
    if (_map_line is not None and len(chapters) > 1
            and _looks_like_map(lines[_map_line])):
        starts = []
        pos = 0
        for ln in lines:
            starts.append(pos)
            pos += len(ln)
        lo = starts[_map_line]
        hi_line = _map_line + 1
        while hi_line < len(lines) and not lines[hi_line].strip():
            hi_line += 1
        if hi_line < len(lines):
            hi = starts[hi_line] + (len(lines[hi_line]) - len(lines[hi_line].lstrip()))
            hi_w = len(script[:hi].split())
            k = 1
            while k < len(chapters):
                ch = chapters[k]
                if lo <= ch.char_start < hi:
                    nxt = chapters[k + 1].char_start if k + 1 < len(chapters) else len(script)
                    if hi < nxt:
                        ch.char_start, ch.word_start = hi, hi_w
                        chapters[k - 1].char_end, chapters[k - 1].word_end = hi, hi_w
                    else:
                        chapters[k - 1].char_end = ch.char_end
                        chapters[k - 1].word_end = ch.word_end
                        del chapters[k]
                        continue
                k += 1

    for ch in chapters:
        ch.opening = script[ch.char_start:ch.char_start + 120].strip().split("\n")[0]

    logger.info(
        "Parsed %d chapters for %s: %s",
        len(chapters),
        show_name or "show",
        [c.title for c in chapters],
    )
    return chapters


def split_script_at_chapters(
    script: str,
    chapters: List[Chapter],
) -> List[str]:
    """Split a podcast script into text sections at chapter boundaries.

    Uses the ``char_start``/``char_end`` character offsets stored by
    ``parse_chapters()`` to slice the script into one text segment per
    chapter.  Each segment can then be synthesized separately via TTS.

    Parameters
    ----------
    script:
        The full podcast script text (same text passed to ``parse_chapters()``).
    chapters:
        Chapters with ``char_start``/``char_end`` set.

    Returns
    -------
    list[str]
        Ordered list of text sections, one per chapter.
        Empty sections are preserved to keep alignment with chapters.
    """
    if not chapters:
        return [script] if script.strip() else []

    # If there is text before the first chapter marker, insert a "Preamble"
    # Chapter so that (a) the content is not lost and (b) len(sections) ==
    # len(chapters), keeping alignment for calculate_timestamps().
    first_ch = chapters[0]
    if first_ch.char_start > 0:
        preamble_text = script[:first_ch.char_start].strip()
        if preamble_text:
            chapters.insert(0, Chapter(
                title="Preamble",
                word_start=0,
                word_end=first_ch.word_start,
                char_start=0,
                char_end=first_ch.char_start,
            ))

    sections: list[str] = []
    for ch in chapters:
        section = script[ch.char_start:ch.char_end].strip()
        sections.append(section)

    return sections


def calculate_timestamps(
    chapters: List[Chapter],
    total_duration: float,
    *,
    music_intro_offset: float = 0.0,
) -> List[Chapter]:
    """Map word-count proportions to real timestamps.

    Parameters
    ----------
    chapters:
        Chapters with ``word_start``/``word_end`` set by ``parse_chapters()``.
    total_duration:
        Total duration of the final mixed MP3 in seconds.
    music_intro_offset:
        Seconds of music-only time before the voice content begins.
        Calculated as ``intro_duration + voice_intro_delay`` from audio config.
        The first chapter starts after this offset.

    Returns
    -------
    list[Chapter]
        Same chapters with ``startTime`` and ``endTime`` populated.
    """
    if not chapters or total_duration <= 0:
        return chapters

    # Voice content occupies the time after the music intro
    # We don't subtract outro since voice may overlap with it (crossfade)
    voice_duration = total_duration - music_intro_offset
    if voice_duration <= 0:
        voice_duration = total_duration
        music_intro_offset = 0.0

    # Total words across all chapters
    total_words = chapters[-1].word_end if chapters else 0
    if total_words <= 0:
        return chapters

    for ch in chapters:
        proportion_start = ch.word_start / total_words
        proportion_end = ch.word_end / total_words
        ch.startTime = round(music_intro_offset + proportion_start * voice_duration, 1)
        ch.endTime = round(music_intro_offset + proportion_end * voice_duration, 1)

    # Clamp final chapter end to total duration
    if chapters:
        chapters[-1].endTime = round(total_duration, 1)

    return chapters


#: An aligned start further than this share of the episode from its
#: word-count estimate is a wrong match, never a correction.
ALIGN_MAX_SHIFT_SHARE = 0.15


def align_timestamps_to_transcript(
    chapters: List[Chapter],
    script: str,
    transcript: dict,
    *,
    music_intro_offset: float = 0.0,
    total_duration: float = 0.0,
) -> List[Chapter]:
    """Move each chapter start onto the Whisper time its first line is spoken.

    Oct 17 2026. ``calculate_timestamps`` spreads the voice evenly over the
    script's words, so a chapter lands wherever the words before it would
    end at an average pace — but a run of numbers is slower than a run of
    names, and every story beat adds a pause the word count never sees.
    Modern Investing Ep203's Portfolio Performance chapter opened 20 s
    after the segment did. The committed transcript is the voice track's own
    clock (shifted for the story-break pauses), so the start of the line a
    chapter opens on is located there — with the same opening matcher the
    story beats use (``engine.story_breaks.boundary_anchors``) — and placed
    *music_intro_offset* later, where the voice sits in the mix.

    Run AFTER ``calculate_timestamps``. A line that cannot be found, an
    alignment that would reorder chapters, or one that moves a start by more
    than ``ALIGN_MAX_SHIFT_SHARE`` of the episode keeps its word-count time.
    Never raises: chapters are metadata.
    """
    try:
        return _align_timestamps(chapters, script, transcript,
                                 music_intro_offset, total_duration)
    except Exception as exc:  # noqa: BLE001 — chapters are metadata
        logger.warning("Chapter alignment to the transcript skipped: %s", exc)
        return chapters


def _opening_key(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", (text or "").lower()).split()[:8])


def _align_timestamps(chapters, script, transcript, offset, total_duration):
    from engine import story_breaks as sb
    if not chapters or not transcript or not script:
        return chapters
    # Non-empty lines with their character offsets, in script_lines order.
    line_starts: List[int] = []
    pos = 0
    for raw in script.split("\n"):
        if raw.strip():
            line_starts.append(pos + (len(raw) - len(raw.lstrip())))
        pos += len(raw) + 1
    if not line_starts:
        return chapters
    lines = sb.script_lines(script)
    targets: List[Optional[int]] = []
    cursor = 0
    for ch in chapters:
        k = None
        key = _opening_key(ch.opening)
        if key:
            k = next((i for i in range(cursor, len(lines))
                      if _opening_key(lines[i]).startswith(key)), None)
        if k is None and not ch.opening:
            k = next((i for i, s in enumerate(line_starts) if s >= ch.char_start), None)
        if k is not None:
            cursor = k + 1
        targets.append(k)
    found: dict = {}
    wanted: List[int] = []
    for i, k in enumerate(targets):
        if i == 0 or k is None or k == 0:
            continue
        anchors, _unmatched = sb.boundary_anchors(script, wanted + [k], transcript)
        if len(anchors) > len(found):
            found[i] = anchors[-1][1]
            wanted.append(k)
    if not found:
        return chapters
    duration = total_duration or (chapters[-1].endTime if chapters else 0.0)
    limit = max(10.0, ALIGN_MAX_SHIFT_SHARE * duration) if duration else float("inf")
    moved = 0
    for i, t in found.items():
        new = round(offset + t, 1)
        prev_start = chapters[i - 1].startTime
        nxt = chapters[i + 1].startTime if i + 1 < len(chapters) else (duration or float("inf"))
        if i + 1 in found:
            nxt = min(nxt, round(offset + found[i + 1], 1))
        if abs(new - chapters[i].startTime) > limit or not (prev_start < new < nxt):
            continue
        chapters[i].startTime = new
        moved += 1
    for i in range(len(chapters) - 1):
        chapters[i].endTime = chapters[i + 1].startTime
    if duration:
        chapters[-1].endTime = round(duration, 1)
    logger.info("Chapters aligned to the transcript: %d of %d starts moved",
                moved, len(chapters) - 1)
    return chapters


def write_chapters_json(
    chapters: List[Chapter],
    output_path: Path,
    *,
    episode_title: str = "",
) -> Optional[Path]:
    """Write chapters in Podcasting 2.0 JSON Chapters format.

    Format spec: https://github.com/Podcastindex-org/podcast-namespace/blob/main/chapters/jsonChapters.md

    Parameters
    ----------
    chapters:
        Chapters with timestamps populated.
    output_path:
        Where to write the JSON file.
    episode_title:
        Optional episode title for the top-level ``title`` field.

    Returns
    -------
    Path or None
        The output path on success, ``None`` if no chapters or on error.
    """
    if not chapters:
        logger.info("No chapters to write")
        return None

    data = {
        "version": "1.2.0",
        "chapters": [],
    }
    if episode_title:
        data["title"] = episode_title

    for i, ch in enumerate(chapters):
        entry = {
            # Oct 21 2026: the first chapter covers the episode from 0. It
            # had started on the identity line (~5 s on most shows, 17.6 s
            # on Models & Agents Ep210), so the hook played under no
            # chapter at all.
            "startTime": 0.0 if i == 0 else ch.startTime,
            "title": ch.title,
        }
        if ch.endTime > ch.startTime:
            entry["endTime"] = ch.endTime
        data["chapters"].append(entry)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Chapters JSON written: %s (%d chapters)", output_path, len(chapters))
        return output_path
    except Exception as exc:
        logger.error("Failed to write chapters JSON: %s", exc)
        return None
