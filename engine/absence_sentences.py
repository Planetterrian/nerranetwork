"""Absence sentences: sentences whose only content is that a fact is missing.

"No energization date was stated." "Current reporting supplies no release
date." "Alphabet has not yet released additional information." Every one of
the Sep 2026 new shows' first episodes carried them — AI Chips Ep1 closed 8
of its 10 digest items on one, MAG 7 Ep1's script spent 9 of 66 sentences
on them — although all four digest prompts banned the shape outright after
the dry runs. An instruction the model breaks is enforced in code (CLAUDE.md,
DP Pod's Network-pick rotation), so this module removes them.

Deliberately narrow. It matches only the DISCLOSURE shape — a detail that was
not given, stated, released, disclosed. It never matches the health shows'
required caveats ("No regulatory body has approved…", "…has not been tested
in people", "…remains unknown"): what science has not established is
content; what a press release left out is not. Opt-in per show
(``absence_sentence_filter: true``); every other show is untouched.
"""

from __future__ import annotations

import re
from typing import Tuple

_VERBS = (
    r"disclosed|provided|released|specified|detailed|given|listed|stated|"
    r"announced|mentioned|named|shared|supplied|outlined|included|made public|"
    r"offered|published|revealed|itemi[sz]ed|quantified|broken down"
)

_PATTERNS = [
    # "No energization date was stated." / "No further details … were provided"
    re.compile(
        r"^(?:but\s+|however,?\s+|yet\s+)?(?:no|neither)\b[^.!?]{0,120}?\b"
        r"(?:was|were|has been|have been|is|are|had been)\s+(?:yet\s+)?"
        r"(?:" + _VERBS + r")\b",
        re.IGNORECASE,
    ),
    # "Alphabet has not yet released additional information." /
    # "The company did not disclose the price."
    re.compile(
        r"\b(?:did|does|do|has|have|had)\s+not\s+(?:yet\s+)?"
        r"(?:disclose|provide|specify|detail|give|list|state|announce|mention|"
        r"name|release|share|supply|outline|reveal|quantify|put a number on)\b",
        re.IGNORECASE,
    ),
    # "Regulatory review status has not been detailed in the report."
    re.compile(
        r"\b(?:has|have|had|was|were|is|are)\s+not\s+(?:yet\s+)?(?:been\s+)?"
        r"(?:" + _VERBS + r")\b",
        re.IGNORECASE,
    ),
    # "Current reporting supplies no release date."
    re.compile(
        r"\b(?:supplies|supplied|provides|provided|gives|gave|includes|included|"
        r"carries|carried|offers|offered|contains|contained|lists|listed)\s+no\b",
        re.IGNORECASE,
    ),
    # "No energization date appears in the release." / "No new capabilities
    # received mention alongside the update."
    re.compile(
        r"^(?:no|neither)\b[^.!?]{0,120}?\b(?:appears?|appeared|received\s+mention|"
        r"were\s+mentioned|accompanied)\b",
        re.IGNORECASE,
    ),
    # "No release date or specific design elements have been confirmed in
    # the current reporting." — "confirmed" only when the sentence names the
    # document that failed to confirm it.
    re.compile(
        r"^(?:no|neither)\b[^.!?]{0,120}?\b(?:has|have|had)\s+been\s+confirmed\b"
        r"[^.!?]{0,60}\b(?:report|reporting|announcement|release|statement|"
        r"filing|article|coverage)\b",
        re.IGNORECASE,
    ),
    # "Terms remain undisclosed." (never "unknown"/"unclear": science's open
    # questions are content on the health shows)
    re.compile(r"\bremains?\s+(?:undisclosed|unspecified|unannounced)\b", re.IGNORECASE),
]

# Lines that are structure, not prose.
_SKIP_LINE = re.compile(r"^\s*(?:#|>|\*\*[^*]+\*\*\s*$|[-*]\s|\d+[.)]\s|```|Source:|Ranks:)")

# Oct 1 2026, Top World Ep009: the model joined each item's reader-only
# ``Ranks:`` line and its ``Source:`` line into ONE line ("Ranks: … · no
# figure given · now Source: https://…"). The ranking clause reads as an
# absence sentence by design (the prompt asks for "two words" where the item
# cannot support a clause), the line had one "sentence", so the whole line
# went — URL included. Eight of ten items shipped with no Source, the
# published lint metric still read 0 missing (it ran before this filter),
# and the claims gate saw two sourced items. A line that carries a URL or
# a Source label is never dropped whole: the Source tail is kept verbatim.
_SOURCE_TAIL_RE = re.compile(r"(\bSource:\s*\S.*)$")
_URL_RE = re.compile(r"https?://\S+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“‘'(\[])")


# A sentence whose only content is WHERE something was read, naming a
# spoken domain (Peptides Ep1: "The source for these statements appears in
# reports linked from x dot com."). The run's spoken-URL tripwire only
# counts these on every show; on the opt-in shows they are removed. The
# filter runs on the script BEFORE the TTS transform speaks the dot, so the
# written form counts too (Omni View Asia Pacific Ep1 read "The source named
# for the lead is AP News, at apnews dot com." past it).
_SPOKEN_DOMAIN_RE = re.compile(
    r"\b[a-z0-9-]+(?: dot |\.)(?:com|org|net|io|gov|ca|co|uk|ai)\b", re.IGNORECASE)
_ATTRIBUTION_RE = re.compile(
    r"\b(?:source|sources|sourced|link|links|linked|appears?|posted|according to|"
    r"reported (?:on|by|at)|read (?:on|at))\b", re.IGNORECASE)


def is_attribution_only_sentence(sentence: str) -> bool:
    """Never the network's own address: the closings and promos point
    listeners at nerranetwork dot com on purpose."""
    s = sentence.strip()
    domains = [m.group(0).lower() for m in _SPOKEN_DOMAIN_RE.finditer(s)]
    if not domains or all(d.startswith("nerranetwork") for d in domains):
        return False
    return bool(_ATTRIBUTION_RE.search(s))


# Self-narration: a sentence about how the script was made rather than about
# the news — the briefing it was written from, "the item", this brief's or
# this desk's rules, the length target. grok-4.7 turns every prompt rule into
# a sentence: the four Omni View desk Ep1s (2026-09-23) spoke 37 of them in
# 305 ("The item does not, in the reporting provided here, give a count of
# the dead…", "That is all the digest states on it, so that is all I will
# say.", "Stretching this to 1, would mean inventing details or padding items
# already covered, which this brief does not allow."). Every shape below
# names the production apparatus, which is never news. A show's debut copy
# about itself ("This brief is for listeners who…") is left alone.
_SELF_NARRATION = [
    # The digest is never the show's own name; "briefing" often is ("That
    # wraps today's briefing", "this briefing finds you every day"), so it
    # counts only as a document that says, carries or lacks something.
    re.compile(r"\b(?:the|this|today's) digest\b", re.IGNORECASE),
    re.compile(r"\bthe briefing (?:says|states|gives|carries|has|does|lists|names)\b"
               r"|\b(?:in|from) (?:the|today's) briefing\b", re.IGNORECASE),
    re.compile(r"\bas provided\b|\bprovided (?:here|for this)\b|\breporting provided\b"
               r"|\b(?:text|material) (?:given|filed|provided) for\b|\bsource text\b"
               r"|\bmaterial this (?:desk|brief) has\b", re.IGNORECASE),
    # "The facts the item does carry are…" — the item as a DOCUMENT with a
    # verb of saying. Never bare "the item(s)": the required debut disclosure
    # ("Software picks and writes the items from named newsrooms…") uses it.
    re.compile(r"\b(?:the|this) item (?:does|did|carries|says|states)\b", re.IGNORECASE),
    re.compile(r"\bheadline on the\b", re.IGNORECASE),
    re.compile(r"\b(?:this|the) (?:brief|desk)(?:'s|’s)? (?:does not|doesn't|doesn’t|did not|"
               r"will not treat|adds|has (?:independently|adjusted)|makes on its own|"
               r"(?:does not |doesn't )?allow)\b", re.IGNORECASE),
    re.compile(r"\b(?:by|of|for) this (?:brief|desk)\b|\bthis (?:brief|desk) (?:makes|has)\b",
               re.IGNORECASE),
    # Oct 3 2026 review of the launch cohort (~21 such sentences in 52
    # episodes): the item / note / material / pile as a DOCUMENT that holds
    # or lacks a fact — "…are in the item.", "No price … is in the
    # material.", "Nothing in the supplied note names a vote", "…in today's
    # pile." A copula or "nothing" must govern the phrase, so physics prose
    # ("defects in the material") never matches.
    re.compile(r"^(?=.*\b(?:no|not|nothing|none|neither)\b)"
               r".*\b(?:is|are|was|were|appears?)\s+(?:\w+\s+){0,3}?"
               r"(?:in|from) (?:the|today's|this) (?:item|note|material|pile)"
               r"(?=\s*[.,;:!?]|\s*$)", re.IGNORECASE),
    re.compile(r"\bsupplied (?:note|notes|material|item|items|text)\b"
               r"|\btoday's pile\b", re.IGNORECASE),
    re.compile(r"\ball I (?:will|can) say\b|\binventing details\b|\bpadding\b"
               r"|\bword (?:count|target)\b", re.IGNORECASE),
    # Oct 12 2026 slate: the source as a DOCUMENT the script stage reads
    # from — LatAm Ep020 narrated its sources eleven times ("The published
    # note gives the job figure…", "that is the paper's characterization",
    # "What the report establishes on the page…", "On the progress file…"),
    # Prediction Markets read its own checklist ("…in the material here.").
    # Swept against every committed script: "on the page", "in that text"
    # and "the written note" are prose elsewhere and are NOT matched.
    re.compile(r"\bthe published (?:account|note|report|piece|text|item)\b"
               r"|\bwhat the (?:report|article|piece|note|account) establishes\b"
               r"|\bthe paper(?:'|’)?s characteri[sz]ation\b"
               r"|\bthe progress file\b|\bheads the item\b", re.IGNORECASE),
    re.compile(r"\bin the (?:material|text) here\b"
               r"|\b(?:text|material) given for this\b", re.IGNORECASE),
    # A segment label spoken as a lead-in ("Progress Watch: the day had
    # none.") — the Oct 10 rule skips the section; this is its echo.
    re.compile(r"^(?:Progress Watch|Both Sides|Also Today|The Board|"
               r"How It Works|Counterpoint)\s*:", re.IGNORECASE),
    # Oct 13 2026: the same echo without the colon — Africa & Middle East
    # Ep021 spoke "Progress Watch for the day had none." past the line above.
    re.compile(r"^Progress Watch\b[^.!?]{0,40}\b(?:had none|none today|was empty)\b",
               re.IGNORECASE),
    # Oct 13 2026 slate (North America Ep020, Africa & Middle East Ep021,
    # MAG 7 Ep021): grok-4.7 narrated its sourcing discipline in shapes the
    # Oct 12 sweep had not seen — "…are the facts The National reports on
    # the decision", "which is the limit of what Premium Times reports on
    # the point", "What is on the record, then, is…", "not a finding by
    # this show", "the four names The Hill attaches to that opposition",
    # "not another retelling of the race". Swept against all 2,320
    # committed scripts: every match is narration; "The facts on confirmed
    # cases are consistent across reports" (prose, Omni View) is not
    # matched because the outlet must follow "the facts".
    re.compile(r"\bnot a finding by this show\b"
               r"|\bthis show(?:'s|’s) own (?:finding|reading|judgement|judgment)\b"
               r"|\bare the facts [A-Z][^.!?]{0,50}? reports (?:on|about|for)\b"
               r"|\bthe limit of what [^.!?]{0,40}? (?:reports|carried|carries|says)\b"
               r"|\bon the record, then\b|\bnot another retelling\b"
               r"|\b(?:names?|figures?) [^.!?]{0,40}? attaches to\b", re.IGNORECASE),
    # Oct 14 2026 (review of the cohort's Oct 7-13 scripts): absences and
    # rule-narration the shapes above did not reach — "A sign of progress
    # … is not in today's reporting.", "The day had none.", "Today's text
    # does not carry a named lawmaker's speech…", "None of the markets in
    # today's set opened…", "No human outcome … is in the report.", "None
    # of those accounts says which way the vote will go." Swept against
    # all 2,321 committed scripts: 20 matches, every one narration.
    re.compile(r"\b(?:is|are|was|were) not in today(?:'s|’s) (?:reporting|reports|articles|"
               r"text|coverage|briefing)\b"
               r"|\bno sign of progress\b|^The day had none\b"
               r"|\btoday(?:'s|’s) (?:text|reporting|articles|coverage|set) (?:does not|doesn't|"
               r"doesn’t|did not|do not|don't) (?:carry|include|name|say|give|show)\b"
               r"|\bin today(?:'s|’s) set\b"
               r"|\bnone of (?:those|these|the) (?:accounts|reports|articles|sources|outlets|"
               r"stories) (?:says?|names?|gives?|reports?|states?)\b", re.IGNORECASE),
    re.compile(r"^(?:No|None of)\b[^.!?]{0,120}\b(?:is|are|was|were) (?:in|given in|named in) "
               r"(?:the|today(?:'s|’s)) (?:report|reporting|text|post|article|account)s?\b",
               re.IGNORECASE),
    # Oct 18 2026 slate: grok-4.7 wrote its own instructions into essay
    # sections — Top World Ep025 "Set the week in order, using only what
    # these reports name." / "What it changes, and for whom, follows from
    # those named claims.", MAG 7 Ep026 "What changes follows from which
    # figure touches which company.", AI Chips Ep027 "Walk only the figures
    # iTWire prints." Swept against every committed digest and script: these
    # four shapes match exactly those four sentences.
    re.compile(r"\busing only what (?:these|the) (?:reports|sources) name\b"
               r"|\bfollows from (?:those|these) named claims\b"
               r"|\bfollows from which (?:figure|fact|number|claim)\b"
               r"|^Walk only the (?:figures|facts|numbers)\b", re.IGNORECASE),
]

# "<Outlet> is the source for <list>" — North America Ep020 (2026-10-13)
# carried ten of them and the shape names an outlet on every story, so
# it is not an absence sentence but a sourcing clause. It is cut as a
# CLAUSE, never a sentence: Collingwood Ep3 wrote "Environment Canada is
# the source for those figures, and the current reading given is eleven
# point zero degrees." — the temperature stays. A sentence that is only
# the clause goes.
_SOURCE_FOR_HEAD_RE = re.compile(
    r"^(?:The |the )?[A-Z][\w&'’.-]*(?:\s+[A-Z][\w&'’.-]*){0,5}\s+"
    r"(?:is|are|was|were) the sources? for\b")
_SOURCE_FOR_TAIL_RE = re.compile(
    r",?\s*(?:and|but|while)\s+(?:The |the )?[A-Z][\w&'’.-]*(?:\s+[A-Z][\w&'’.-]*){0,5}\s+"
    r"(?:is|are|was|were) the sources? for\b[^.;!?]*")
# The clause ends where a second CLAUSE begins — ", and the current reading
# given is eleven…" — never at a comma inside the list it introduces ("the
# pledge, the size claim, and the Miami campus plan").
_NEXT_CLAUSE_RE = re.compile(
    r",\s*(?:and|but|while)\s+(?=(?:[\w'’-]+\s+){0,4}(?:is|are|was|were|has|have|had|"
    r"said|says|will|did|does|do)\b)")


def cut_sourcing_clause(sentence: str) -> str:
    """Remove an "<Outlet> is the source for …" clause; '' when nothing
    else was in the sentence. Any other sentence is returned unchanged."""
    s = sentence.strip()
    m = _SOURCE_FOR_HEAD_RE.match(s)
    if m:
        n = _NEXT_CLAUSE_RE.search(s, m.end())
        rest = s[n.end():].strip() if n else ""
        if len(rest.split()) < 5:
            return ""
        return rest[0].upper() + rest[1:]
    m = _SOURCE_FOR_TAIL_RE.search(s)
    if m:
        head = s[:m.start()].rstrip(" ,;")
        if len(head.split()) < 5:
            return ""
        return head + ("." if s.endswith(".") else "")
    return s


# Top World Ep020 (2026-10-12) opened 7 of 10 items on a doubled place
# tag — "In Pakistan, in Asia, President Zardari…", "In Haiti, in the
# Americas, the electoral body…" (18 across the committed scripts, all
# Top World). The prompt asks for the country and the region; the country
# carries the region. Only the second tag goes.
_PLACE_TAG_RE = re.compile(
    r"^(In [^,\n]{2,40}), in (?:Europe|Asia|Africa|the Americas|North America|"
    r"South America|Latin America|the Middle East|the Pacific|Oceania|"
    r"Central America|the Caribbean|the Gulf),", re.MULTILINE)


def strip_doubled_place_tags(text: str) -> Tuple[str, int]:
    """``In X, in <continent>,`` -> ``In X,``. Returns (text, count)."""
    if not text:
        return text, 0
    return _PLACE_TAG_RE.subn(r"\1,", text)


def is_self_narration_sentence(sentence: str) -> bool:
    s = sentence.strip()
    return bool(s) and any(p.search(s) for p in _SELF_NARRATION)


def is_absence_sentence(sentence: str) -> bool:
    s = sentence.strip()
    if not s or s.lower().startswith("source:"):
        return False
    return (any(p.search(s) for p in _PATTERNS) or is_attribution_only_sentence(s)
            or is_self_narration_sentence(s))


def strip_absence_sentences(text: str) -> Tuple[str, int]:
    """Remove absence sentences from prose lines. Returns (text, removed).

    Headings, list items, blockquotes, fenced blocks and ``Source:`` lines
    are left alone. A line whose every prose sentence matches keeps its
    first sentence, so no paragraph is ever emptied.
    """
    if not text:
        return text, 0
    text, _tags = strip_doubled_place_tags(text)
    out = []
    removed = 0
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
        tail = ""
        m_tail = _SOURCE_TAIL_RE.search(body)
        if m_tail and m_tail.start() > 0:
            # A Source tail glued onto prose: judge the prose, keep the tail.
            body, tail = body[: m_tail.start()].rstrip(), m_tail.group(1)
        elif _URL_RE.search(body):
            # A URL inside prose is a citation; the sentence that carries it
            # is never an absence sentence to remove.
            out.append(line)
            continue
        parts = _SENT_SPLIT.split(body)
        keep = [p for p in parts if not is_absence_sentence(p)]
        # Sourcing clauses are cut inside the sentence (a cut counts as
        # one removal); a sentence the cut empties is dropped and counted
        # with the absence sentences below.
        cut = []
        for p in keep:
            q = cut_sourcing_clause(p)
            if q:
                if q != p:
                    removed += 1
                cut.append(q)
        keep = cut
        prose_kept = [p for p in keep if not p.lower().startswith("source:")]
        if not prose_kept:
            # Every sentence was an absence sentence. A one-sentence line
            # (a script line) goes; a multi-sentence item keeps its first.
            if len(parts) == 1 and not tail:
                removed += 1
                continue
            if len(parts) == 1:
                # The only prose was an absence clause but a Source rides
                # on the line: the citation stays, the clause goes.
                removed += 1
                out.append(lead + tail)
                continue
            keep = [parts[0]] + [p for p in keep if p.lower().startswith("source:")]
        removed += len(parts) - len(keep)
        out.append(lead + " ".join(keep + ([tail] if tail else [])))
    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result, removed


# An item heading with nothing under it (MAG 7 Ep1: "**Microsoft (MSFT):**
# The Information" and then the next section). Same opt-in flag: it is the
# same failure — the model filling a slot it had nothing for.
_ITEM_HEADING_RE = re.compile(r"^\s*\*\*[^*\n]{2,160}\*\*[^.!?\n]{0,80}$")
_SECTION_RE = re.compile(r"^\s*#{1,6}\s")


def drop_empty_items(text: str) -> Tuple[str, int]:
    """Remove bold item headings that carry no body before the next heading."""
    if not text:
        return text, 0
    lines = text.split("\n")
    keep = [True] * len(lines)
    removed = 0
    for i, line in enumerate(lines):
        if not _ITEM_HEADING_RE.match(line):
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if (j >= len(lines) or _SECTION_RE.match(lines[j])
                or _ITEM_HEADING_RE.match(lines[j])):
            keep[i] = False
            removed += 1
    out = "\n".join(line for line, k in zip(lines, keep) if k)
    return re.sub(r"\n{3,}", "\n\n", out), removed


_MD_HEADING_RE = re.compile(r"^(#{2,4})\s+\S")


def drop_empty_sections(text: str) -> Tuple[str, int]:
    """Remove ``##``-``####`` headings with nothing under them.

    Oct 18 2026: published digests carried bare headings — Tesla "## Short
    Spot" (emptied by the cross-section dedupe), SpaceX "### AI & Compute"
    on 5 of 8 episodes, Prediction Markets "### New and Notable" after the
    absence filter took its one sentence — and the blog rendered each as a
    linked table-of-contents entry over nothing. A heading followed by a
    DEEPER heading is a parent and stays; one followed by a heading of the
    same or a higher level, or by the end of the text, goes. Runs after
    validation, so it can never turn an optional empty section into a
    "missing section" regeneration. Fenced blocks are left alone.
    """
    if not text:
        return text, 0
    lines = text.split("\n")
    keep = [True] * len(lines)
    in_fence = False
    fenced = [False] * len(lines)
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            fenced[i] = True
            continue
        fenced[i] = in_fence
    removed = 0
    for i, line in enumerate(lines):
        m = _MD_HEADING_RE.match(line)
        if not m or fenced[i]:
            continue
        j = i + 1
        ruled = False
        while j < len(lines) and (not lines[j].strip() or lines[j].strip() == "---"):
            ruled = ruled or lines[j].strip() == "---"
            j += 1
        if j >= len(lines):
            empty = True
        else:
            n = _MD_HEADING_RE.match(lines[j])
            # A ``---`` rule closes the section (Tesla's "## Short Spot" /
            # "---" / "### Tesla First Principles"), so the deeper heading
            # after it is not this one's child.
            empty = bool(n) and (ruled or len(n.group(1)) <= len(m.group(1)))
        if empty:
            keep[i] = False
            removed += 1
    out = "\n".join(line for line, k in zip(lines, keep) if k)
    return re.sub(r"\n{3,}", "\n\n", out), removed
