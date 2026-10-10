"""Listener noise: numbers and sentences that sound like information and are not.

Oct 10 2026, operator listen: "I didn't like so many stock prices read in
MAG 7 and hearing how many likes a recent X post received." Both are real
and both got past a prompt that already banned them, so they are removed in
code — an instruction the model breaks is enforced data-side (CLAUDE.md,
DP Pod's Network-pick rotation; the absence filter is the same shape).

Three classes, all deterministic and narrow:

1. **Engagement counts.** How many people viewed, liked or reposted a post is
   not news, and it is a number the model can only copy from the search
   tool's metadata. Tesla read eight of them in the month to Oct 10 (Ep629:
   "The post came at eight eighteen AM on October nine with eighteen
   views."), Models & Agents one ("The post received four point one million
   views."). The CLAUSE is removed from a sentence that carries anything
   else; a sentence left saying only that a post appeared, was made on X or
   received views goes. The minute a post went up is removed with it, but
   only inside a sentence about a post — a launch at 2:37 AM local is
   content.

2. **Post-metadata sentences.** "The post was made on X." "The comment was
   posted on X." Filler the model writes to give a thin post a second
   sentence. Removed whole.

3. **A read price tape** (script only). Two or more consecutive sentences
   that each give a different company's closing price are a ticker tape
   read aloud — MAG 7 read all seven closes on 3 of its 18 episodes, the
   reader-only "The Tape" section voiced despite the prompt. The whole run
   goes. One price inside a story, or the flagships' single closing price
   line, is untouched: a run needs two DIFFERENT subjects.

The digest's reader-only ``### The Tape`` section never reaches the script
stage at all (``strip_reader_only_sections``, called by run_show's podcast
digest cleaner). English-only patterns: the Russian shows are unaffected.
"""

from __future__ import annotations

import re
from typing import List, Tuple

# A count as written in a digest ("18", "4.1M", "18.9K", "1,204") or as the
# TTS text spells it ("eighteen point nine thousand", "four point one
# million", "eight hundred eighty-one").
_NUM_WORDS = (
    r"zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|"
    r"million|billion|point|and|a|dozen|several|hundreds|thousands|millions"
)
_NUM_TOKEN = r"(?:\d[\d,.]*\s?[kKmMbB]?|(?:" + _NUM_WORDS + r"))"
_COUNT = _NUM_TOKEN + r"(?:[\s-]+" + _NUM_TOKEN + r")*"
_ENG_NOUN = (
    r"views|likes|reposts|retweets|replies|bookmarks|impressions|quote posts|"
    r"quote tweets|hearts"
)
_HEDGE = r"(?:about|roughly|around|over|more than|nearly|almost|just over|some|close to)\s+"

# ", with 47 views" / " and 300 reposts" — a trailing clause.
_ENG_TAIL = re.compile(
    r"(?:,\s*|\s+)(?:with|and|after|drawing|garnering|racking up|earning)\s+(?:" + _HEDGE + r")?"
    + _COUNT + r"\s+(?:" + _ENG_NOUN + r")\b"
    r"(?:\s*(?:,|and)\s*(?:" + _HEDGE + r")?" + _COUNT + r"\s+(?:" + _ENG_NOUN + r")\b)*"
    r"(?:\s+according to [^.,;!?]+)?",
    re.IGNORECASE,
)
# "The post received 4.1 million views." — the verb carries the count.
_ENG_VERB = re.compile(
    r"\b(?:received|recorded|drew|got|garnered|racked up|earned|topped|passed|"
    r"reached|has|had|hit|amassed|attracted|collected|pulled|logged|clocked)\s+(?:" + _HEDGE + r")?"
    + _COUNT + r"\s+(?:" + _ENG_NOUN + r")\b"
    r"(?:\s*(?:,|and)\s*(?:" + _HEDGE + r")?" + _COUNT + r"\s+(?:" + _ENG_NOUN + r")\b)*"
    r"(?:\s+according to [^.,;!?]+)?",
    re.IGNORECASE,
)
# "(18 views)" / "(1.2K likes, 300 reposts)"
_ENG_PAREN = re.compile(
    r"\s*\((?![^()]*(?:https?://|www\.|/))(?:[^()]*?\b(?:" + _ENG_NOUN
    + r")\b[^()]*?)\)", re.IGNORECASE)

_POST_WORD = re.compile(
    r"\b(?:post|posts|posted|tweet|tweeted|on X\b|x\.com|thread|reply|replied)\b",
    re.IGNORECASE)
# "at 8:18 AM on October 9" / "at eight eighteen AM on October nine"
_POST_TIME = re.compile(
    r"\b((?:posted|shared|tweeted|published|came|appeared|landed)"
    r"(?:\s+(?:on|to)\s+X)?)"
    r"\s+at\s+(?:\d{1,2}(?::\d{2})?|(?:" + _NUM_WORDS + r")(?:[\s-]+(?:" + _NUM_WORDS
    + r"|oh))*)\s*(?:a\.?\s?m\.?|p\.?\s?m\.?)"
    r"(?:\s+(?:ET|PT|UTC|GMT|Eastern|Pacific|local(?: time)?))?"
    r"(?:\s+on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
    r"January|February|March|April|May|June|July|August|September|October|"
    r"November|December)(?:\s+(?:\d{1,2}|[a-z-]+))?)?",
    re.IGNORECASE,
)

# A sentence that says only that a post exists.
_META_SUBJECT = (
    r"(?:the|that|this|his|her|their|its|a|an|one)\s+(?:[a-z-]+\s+)?"
    r"(?:post|tweet|comment|remark|analysis|thread|reply|update|message|note|"
    r"observation|clip|video)"
)
_META_ONLY = re.compile(
    r"^(?:but\s+|and\s+)?" + _META_SUBJECT + r"\s+"
    r"(?:was|came|appeared|went up|landed|received|recorded|drew|got)"
    r"(?:\s+(?:made|posted|shared|published|written|put up|up|out))?"
    r"(?:\s+(?:on|to|via)\s+(?:X|x\.com|Twitter|X/Twitter|the platform)(?:\s+formerly Twitter)?)?"
    r"(?:\s+(?:earlier|today|this morning|overnight|yesterday))?\s*[.!?]?$",
    re.IGNORECASE,
)

_SENT_SPLIT = re.compile(r"(?:(?<=[.!?])|(?<=[.!?][\"'”]))\s+(?=[\"'“A-Z0-9])")
_SKIP_LINE = re.compile(r"^\s*(?:#|```|Source:|Ranks:|\|)")
_URL_RE = re.compile(r"https?://\S+")


def is_post_metadata_sentence(sentence: str) -> bool:
    """True when the sentence says only that a post appeared / was made on X."""
    s = (sentence or "").strip()
    return bool(s) and bool(_META_ONLY.match(s))


def clean_sentence(sentence: str) -> Tuple[str, bool]:
    """Remove engagement counts (and a post's time of day) from one sentence.

    Returns ``(sentence, changed)``. The result is ``""`` when nothing but
    post metadata is left.
    """
    s = sentence
    orig = s
    s = _ENG_PAREN.sub("", s)
    s = _ENG_TAIL.sub("", s)
    s = _ENG_VERB.sub("", s)
    if _POST_WORD.search(orig):
        s = _POST_TIME.sub(r"\1", s)
    if s != orig:
        # "…chart, which drew 12K likes, showing…" leaves a bare "which".
        s = re.sub(r",?\s*\b(?:which|that)\b\s*(?=[,.;!?]|$)", "", s)
        s = re.sub(r"\s+([,.;!?])", r"\1", s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        s = re.sub(r",\s*([.!?])$", r"\1", s)
        if s and s[-1] not in ".!?\"'”" and orig.rstrip()[-1:] in ".!?":
            s += orig.rstrip()[-1]
        bare = re.sub(r"[\s.!?,;:]+", " ", s).strip()
        # "The post came." / "The post received." — a subject with nothing left.
        if not bare or re.fullmatch(
                _META_SUBJECT + r"(?:\s+(?:was|came|appeared|went up|landed|received|"
                r"recorded|drew|got|has|had|reached|hit))?"
                r"(?:\s+(?:made|posted|shared|published|up|out))?"
                r"(?:\s+(?:on|to|via)\s+(?:X|Twitter))?"
                r"(?:\s+(?:within|in|over|inside|during|after)\s+[^.!?]{0,40}"
                r"|\s+(?:today|overnight|this morning|yesterday|earlier))?",
                bare, re.IGNORECASE):
            return "", True
    if is_post_metadata_sentence(s):
        return "", True
    return s, s != orig


def strip_engagement_noise(text: str) -> Tuple[str, int]:
    """Remove engagement counts and post-metadata sentences. Returns (text, n).

    ``n`` counts sentences changed or removed. Headings, Source lines, tables
    and fenced blocks are left alone. A line whose every sentence was noise is
    dropped only when it had no Source tail or URL (the citation stays).
    """
    if not text:
        return text, 0
    out: List[str] = []
    n = 0
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence or not line.strip() or _SKIP_LINE.match(line):
            out.append(line)
            continue
        lead = line[: len(line) - len(line.lstrip())]
        body = line.strip()
        # A numbered/bulleted item keeps its marker and bold headline.
        marker = ""
        m = re.match(r"^((?:\d+[.)]|[-*])\s+(?:\*\*[^*]+\*\*\s*(?:[—–-]\s*[^.!?\n]{0,80}?\s*)?)?)", body)
        if m and m.group(1).strip():
            marker, body = m.group(1), body[m.end(1):]
        tail = ""
        m_tail = re.search(r"\s*((?:Source|Post|Источник)\s*:\s*\S.*)$", body)
        if m_tail and m_tail.start() > 0:
            body, tail = body[: m_tail.start()].rstrip(), m_tail.group(1)
        parts = _SENT_SPLIT.split(body) if body else []
        kept: List[str] = []
        for p in parts:
            if _URL_RE.search(p):
                kept.append(p)
                continue
            c, changed = clean_sentence(p)
            if changed:
                n += 1
            if c:
                kept.append(c)
        if parts and not kept and not tail and not marker:
            continue
        rebuilt = " ".join(kept + ([tail] if tail else []))
        out.append(lead + marker + rebuilt if (marker or rebuilt) else "")
    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result, n


# --------------------------------------------------------------- price tape --
_PRICE_SENT = re.compile(
    r"\b(?:closed|finished|ended|settled)\s+"
    r"(?:the\s+(?:session|day)\s+)?(?:at|near|around|up at|down at)\s+"
    r"[^.!?]{0,90}?\b(?:dollars?|\$\s?\d)",
    re.IGNORECASE,
)
_SUBJECT_STOP = re.compile(
    r"\b(?:closed|finished|ended|settled|traded|trading|opened|sits?|sat)\b",
    re.IGNORECASE)


def _price_subject(sentence: str) -> str:
    head = _SUBJECT_STOP.split(sentence, maxsplit=1)[0]
    head = re.sub(r"^(?:on the [^,]*,\s*|and\s+|while\s+|meanwhile,?\s+)", "", head.strip(),
                  flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9 ]", "", head.lower()).strip()


def strip_price_tape(script: str) -> Tuple[str, int]:
    """Drop runs of two or more consecutive closing-price sentences about
    DIFFERENT subjects (a ticker tape read aloud). Returns (script, removed).

    A single price sentence — a story's own move, the flagships' one quote
    line — is never touched, and neither is the same price repeated.
    """
    if not script:
        return script, 0
    lines = script.split("\n")
    # Flatten to (line_idx, sentence) so a run may span one-sentence lines.
    flat: List[Tuple[int, str]] = []
    for i, line in enumerate(lines):
        if not line.strip():
            flat.append((i, ""))
            continue
        for s in _SENT_SPLIT.split(line.strip()):
            flat.append((i, s))
    drop = set()
    k = 0
    while k < len(flat):
        if flat[k][1] and _PRICE_SENT.search(flat[k][1]):
            j = k
            subjects = set()
            while j < len(flat) and (not flat[j][1] or _PRICE_SENT.search(flat[j][1])):
                if flat[j][1]:
                    subjects.add(_price_subject(flat[j][1]))
                j += 1
            run = [x for x in range(k, j) if flat[x][1]]
            if len(run) >= 2 and len(subjects) >= 2:
                drop.update(run)
            k = j
        else:
            k += 1
    if not drop:
        return script, 0
    rebuilt: dict = {}
    for idx, (i, s) in enumerate(flat):
        if not s:
            rebuilt.setdefault(i, [])
            continue
        if idx in drop:
            rebuilt.setdefault(i, [])
            continue
        rebuilt.setdefault(i, []).append(s)
    out: List[str] = []
    for i, line in enumerate(lines):
        if not line.strip():
            out.append(line)
            continue
        kept = rebuilt.get(i, [])
        if kept:
            out.append(" ".join(kept))
    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result, len(drop)


# --------------------------------------------------- reader-only sections --
#: Digest sections written for readers that the script stage must never see.
READER_ONLY_SECTIONS = ("The Tape",)
_READER_ONLY_RE = re.compile(
    r"^#{1,6}\s*(?:" + "|".join(re.escape(t) for t in READER_ONLY_SECTIONS) + r")\b.*$",
    re.IGNORECASE)
_ANY_HEADER = re.compile(r"^\s*#{1,6}\s")
_RULE = re.compile(r"^[\s━─═\-=]{4,}$")


def strip_reader_only_sections(digest: str) -> str:
    """Remove reader-only sections (heading through the next heading or rule)."""
    if not digest:
        return digest
    out: List[str] = []
    skipping = False
    for line in digest.split("\n"):
        if _READER_ONLY_RE.match(line.strip()):
            skipping = True
            continue
        if skipping and (_ANY_HEADER.match(line) or _RULE.match(line)):
            skipping = False
        if not skipping:
            out.append(line)
    return "\n".join(out)
