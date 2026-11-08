"""Digest lints: structural checks a show opts into by name.

Sep 23 2026, the launch-cohort review. Thirteen new shows shipped Episode 1
and the per-show review found the same class of defect on most of them: a
rule the prompt states and the model breaks — the "What You Need to Know"
paragraph opening on a different story from the hook (MAG 7, AI Chips), a
Lead whose only source is an X post (Africa & Middle East: 6 of 6), a
Progress Watch that was a six-second closing marker (Central & South
America), a Counterpoint about an unrelated company (MAG 7), a data-centre
item with no MW and no build state (AI Chips). This network's standing rule
is that an instruction the model breaks is enforced in code, so each of
those is a lint here.

A lint reads the DIGEST markdown and returns a :class:`LintFinding` or
``None``. run_show feeds the findings into the existing one-shot structural
regeneration (the same path an empty mandatory section takes) with each
finding's ``note`` appended to the corrective suffix, and records each
lint's metric. Nothing here edits text and nothing here blocks an episode:
a digest that still fails after the retry ships, and the metric says so.

Shows opt in with ``digest_lints: [name, ...]`` in their YAML; a show with
no list is byte-identical. ``LINTS`` is the closed vocabulary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from engine.script_audit import _salient
from engine.titles import HEADLINE_CHAPTER_TITLE_MAX, clip_words

# ---------------------------------------------------------------------------
# Parsing helpers (shared by every lint; deliberately forgiving — the
# digests come in two item shapes, ``**Title: Outlet**`` on its own line and
# ``**Title:** Outlet. body`` inline, plus AI Chips' plain ``Title: Outlet``).
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r"^\s*#{2,4}\s+(.+?)\s*$")
# The digest carries the hook as ``**HOOK:** …`` while it is being written
# and as a ``> **…**`` blockquote once run_show has transformed it; a lint
# may see either.
_HOOK_RE = re.compile(r"\*\*HOOK:\*\*\s*(.+)|^>\s*\*\*(.+?)\*\*\s*$", re.MULTILINE)
_WYNTK_RE = re.compile(r"\*\*What You Need to Know:\*\*\s*(.+)")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_URL_RE = re.compile(r"https?://[^\s)\]>]+")
# Oct 13 2026: a Reddit thread is the same defect as an X post when it is a
# lead's ONLY source (Planetterrian Ep212 led its menopause story on
# r/science and never named the paper). Replayed on the last 14 digests of
# every opted-in show: FF 0, Planetterrian 0, MAB 1, M&A 1 firings.
_X_HOST_RE = re.compile(
    r"^https?://(?:www\.|mobile\.|old\.)?(?:x\.com|twitter\.com|reddit\.com)/",
    re.IGNORECASE)
_ITEM_HEAD_RE = re.compile(r"^\s*(?:\d+\.\s*)?\*\*.+\*\*|^\s*(?:\d+\.\s*)?[A-Z][^\n]{8,}?:\s+[^\n]{2,60}$")

#: Section titles whose FIRST item is the episode's lead story.
LEAD_SECTIONS = (
    "Lead", "Top Story", "Top News", "Top Stories", "The Week's Stories",
    "The Ten", "The Week in Peptides", "The Week in Longevity",
    "The Big Story",
)


def is_lead_section(title: str) -> bool:
    """Oct 13 2026: ``x_only_lead`` had been a no-op on five of the shows
    that opted in — Models & Agents for Beginners leads with "The Big
    Story", Fascinating Frontiers and Planetterrian with "Top 12 … Stories"
    — because the lead was matched by exact name. A header that starts
    with "Top " is a lead section wherever it appears."""
    t = (title or "").strip()
    return t in LEAD_SECTIONS or t.startswith("Top ")


def sections(digest: str, *, full_titles: bool = False) -> List[Tuple[str, str]]:
    """``[(title, body), ...]`` for every ``##``/``###`` section, in order.
    The title is taken up to its first colon (``### Both Sides: X`` → ``Both
    Sides``) unless ``full_titles`` — a heading that IS the story (``### 7)
    Tanzania: Dodoma extends…``) needs all of it."""
    out: List[Tuple[str, str]] = []
    title = ""
    buf: List[str] = []
    for line in (digest or "").splitlines():
        m = _HEADER_RE.match(line)
        if m:
            if title or buf:
                out.append((title, "\n".join(buf).strip()))
            raw = m.group(1) if full_titles else m.group(1).split(":")[0]
            title = raw.strip().strip("*")
            buf = []
            continue
        buf.append(line)
    if title or buf:
        out.append((title, "\n".join(buf).strip()))
    return out


def section_body(digest: str, name: str) -> Optional[str]:
    for title, body in sections(digest):
        if title.lower() == name.lower():
            return body
    return None


_NUMBERED_ITEM_RE = re.compile(r"^\s*\d+\.\s*\*\*")
_HEADLINE_ITEM_RE = re.compile(r"^\s*\*\*[^*]{10,}\*\*\s*$")


def items(body: str) -> List[str]:
    """Blank-line-separated blocks that open on an item head."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body or "") if b.strip()]
    out: List[str] = []
    for b in blocks:
        first = b.splitlines()[0]
        # Oct 19 2026: a bold ``**Title: Outlet**`` line followed by a blank
        # line and its body is ONE item. The body's first sentence can read
        # as an item head of its own ("Mark Gurman wrote …: …"), which left
        # the title block without its Source line: MAG 7 Ep026 recorded
        # ``items_without_source_shipped = 3`` on seven sourced items.
        headline_only = bool(out) and "\n" not in out[-1] and _HEADLINE_ITEM_RE.match(out[-1])
        if headline_only and not first.startswith("**") and not _NUMBERED_ITEM_RE.match(first):
            out[-1] = out[-1] + "\n" + b
        elif _ITEM_HEAD_RE.match(first) or first.startswith("**"):
            out.append(b)
        elif out:
            out[-1] = out[-1] + "\n" + b
    return out


_SOURCE_LINE_RE = re.compile(r"Source:\s*\S+.*$", re.MULTILINE)


def _prose(text: str) -> str:
    """Text minus its URLs and ``Source:`` tails, for salience comparisons
    (``https``/``source``/``commission`` were the three tokens MAG 7 Ep1's
    unrelated Counterpoint shared with its lead)."""
    return _URL_RE.sub(" ", _SOURCE_LINE_RE.sub(" ", text or ""))


def urls_in(text: str) -> List[str]:
    return [u.rstrip(".,") for u in _URL_RE.findall(text or "")]


def hook_line(digest: str) -> str:
    m = _HOOK_RE.search(digest or "")
    if not m:
        return ""
    return (m.group(1) or m.group(2) or "").strip()


def wyntk_first_sentence(digest: str) -> str:
    m = _WYNTK_RE.search(digest or "")
    if not m:
        return ""
    return _SENT_SPLIT.split(m.group(1).strip(), 1)[0]


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

@dataclass
class LintFinding:
    lint: str
    #: What the corrective regeneration is told (shape only — never a
    #: quotable specimen sentence).
    note: str
    #: Metric name -> value, recorded whether or not the lint fired.
    metrics: Dict[str, object] = field(default_factory=dict)


# --- wyntk_hook_match -------------------------------------------------------

WYNTK_HOOK_MIN_MATCH = 0.3


def wyntk_hook_match(digest: str) -> Optional[float]:
    """Share of the hook's salient words that WYNTK's first sentence carries.
    ``None`` when there is nothing to judge."""
    hook = hook_line(digest)
    first = wyntk_first_sentence(digest)
    if not hook or not first:
        return None
    hs = _salient(hook)
    if len(hs) < 3:
        return None
    return round(len(hs & _salient(first)) / len(hs), 3)


def lint_wyntk_hook_match(digest: str) -> Optional[LintFinding]:
    score = wyntk_hook_match(digest)
    metrics = {"wyntk_hook_match": score}
    if score is not None and score < WYNTK_HOOK_MIN_MATCH:
        return LintFinding(
            "wyntk_hook_match",
            "the first sentence of What You Need to Know is about a different "
            "story from the HOOK line — the reader's first sentence and the "
            "listener's first sentence must be the same story",
            metrics,
        )
    return LintFinding("wyntk_hook_match", "", metrics) if score is not None else None


# --- x_only_lead ------------------------------------------------------------

def x_only_lead_items(digest: str) -> List[str]:
    """Titles of lead items whose every source URL is a social post (X or
    Reddit)."""
    bad: List[str] = []
    for title, body in sections(digest):
        if not is_lead_section(title):
            continue
        its = items(body)
        if not its:
            continue
        lead = its[0]
        urls = urls_in(lead)
        if urls and all(_X_HOST_RE.match(u) for u in urls):
            bad.append(lead.splitlines()[0].strip("* ")[:80])
    return bad


def lint_x_only_lead(digest: str) -> Optional[LintFinding]:
    bad = x_only_lead_items(digest)
    metrics = {"sources_x_only_lead_items": len(bad)}
    if bad:
        return LintFinding(
            "x_only_lead",
            "the lead item's only source is a social post (X or Reddit) — a "
            "lead item is sourced to a named newsroom's own article or the "
            "paper itself (the post's linked article, or another supplied "
            "article on the same story); a post may be a secondary source, "
            "never the only one",
            metrics,
        )
    return LintFinding("x_only_lead", "", metrics)


# --- progress_watch_thin / region_world_thin (the Omni View desks) --------

PROGRESS_WATCH_MIN_CHARS = 200
_NONE_FORM_RE = re.compile(
    r"\b(?:had none|no (?:measur(?:ed|able)|qualifying|new)[^.]{0,60}|none today|"
    r"nothing (?:measurable|qualified)|day had no)\b", re.IGNORECASE)


def lint_progress_watch_thin(digest: str) -> Optional[LintFinding]:
    body = section_body(digest, "Progress Watch")
    if body is None:
        return LintFinding("progress_watch_thin", "the Progress Watch section is missing",
                           {"progress_watch_chars": 0})
    chars = len(body)
    metrics = {"progress_watch_chars": chars}
    if chars < PROGRESS_WATCH_MIN_CHARS and not _NONE_FORM_RE.search(body):
        return LintFinding(
            "progress_watch_thin",
            "Progress Watch is a fragment — it is either a measured result with "
            "its number and source, or the single explicit sentence that the "
            "day's reporting carried none",
            metrics,
        )
    return LintFinding("progress_watch_thin", "", metrics)


REGION_WORLD_MIN_CHARS = 250


def lint_region_world_thin(digest: str) -> Optional[LintFinding]:
    body = section_body(digest, "The Region and the World")
    if body is None:
        return None  # the section is optional
    chars = len(body)
    metrics = {"region_world_chars": chars}
    if chars < REGION_WORLD_MIN_CHARS:
        return LintFinding(
            "region_world_thin",
            "The Region and the World is present but carries no item — either "
            "one full item with the consequence inside the region stated first, "
            "or leave the section out",
            metrics,
        )
    return LintFinding("region_world_thin", "", metrics)


# --- items_without_source (numbered-item shows) ----------------------------
# Sep 24 2026: Planetterrian Ep193 shipped fifteen numbered items and not one
# Source: line — every prior episode carried 12-15 — and nothing noticed:
# the validator counts items, the claims gate saw "covered by item source:
# 0", the feed's Sources line and the blog's Sources section were empty.
# A show whose format ends every numbered item on its Source: line opts in.

# A story item opens on ``N. **Title**`` (Tesla, FF, PT, SpaceX) or on a
# full-line bold headline ``**Title: Outlet**`` (M&A, MAB, MAG 7, AI Chips,
# the desks, the health weeklies). A bold LABEL followed by prose on the
# same line (``**Current status:** …`` — MIT's shape) is not an item, which
# is why the replay over MIT's last twelve digests fires 7/12 under a
# bold-anything rule and 0/12 under this one. Opt-in per show; the shows
# whose format legitimately carries no per-item URL (MIT, the Russian
# shows, the narrative shows) never opt in.
ITEMS_WITHOUT_SOURCE_MIN_ITEMS = 3
ITEMS_WITHOUT_SOURCE_MIN_SHARE = 0.5


def story_items(digest: str) -> List[str]:
    """Every story-item block in the digest (blank-line separated,
    continuation paragraphs folded in), across all sections."""
    out: List[str] = []
    for _title, body in sections(digest):
        for block in items(body):
            head = block.splitlines()[0]
            if _NUMBERED_ITEM_RE.match(head) or _HEADLINE_ITEM_RE.match(head):
                out.append(block)
    return out


ALSO_TODAY_SECTION = "Also Today"


_BOLD_HEAD_RE = re.compile(r"^\s*(?:\d+\.\s*)?\*\*\S")
# Omni View writes each story as its own heading: ``### 3) Nigeria confirms …``.
_HEADING_ITEM_RE = re.compile(r"^\s*\d+\)\s+\S")


def also_today_items(digest: str) -> int:
    """Oct 19 2026: story items inside the digest's ``Also Today`` run —
    the one-sentence items every news show now carries for the qualifying
    stories its developed sections leave out. 0 when the section is absent.

    Oct 21 2026: every block that opens on a bold head counts, whatever
    follows the head on its line. The Oct 19 counter wanted the bold title
    alone on its line, so ``**Title: Outlet** One sentence.`` (Planetterrian,
    Omni View) and ``**Title — Outlet:** One sentence.`` (Models & Agents)
    read 0 beside a section of four items."""
    n = 0
    for title, body in sections(digest):
        if title.strip().lower() != ALSO_TODAY_SECTION.lower():
            continue
        for block in items(body):
            if _BOLD_HEAD_RE.match(block.splitlines()[0]):
                n += 1
    return n


def story_item_count(digest: str) -> int:
    """Oct 21 2026: sourced story items in the digest, in every shape the
    shows write — a numbered item, a block opening on a bold head that
    carries a URL, or an Omni View ``### N) Title`` heading. A bold field
    line with no URL (``**Ticker:** XYZ``) is not a story. Read by the
    ``items_shipped`` / ``prompt_articles_reported_pct`` metrics, which had
    used the bold-title-alone shape only and so read every inline-headed
    item as missing."""
    n = 0
    for title, body in sections(digest):
        if _HEADING_ITEM_RE.match(title):
            n += 1
            continue
        for block in items(body):
            head = block.splitlines()[0]
            if _NUMBERED_ITEM_RE.match(head) or (
                    _BOLD_HEAD_RE.match(head) and urls_in(block)):
                n += 1
    return n


def items_without_source(digest: str) -> Tuple[int, int]:
    """``(story items, of which carry no URL at all)``."""
    blocks = story_items(digest)
    return len(blocks), sum(1 for b in blocks if not urls_in(b))


def lint_items_without_source(digest: str) -> Optional[LintFinding]:
    total, missing = items_without_source(digest)
    metrics = {"items_without_source": missing, "items_with_headline": total}
    if total >= ITEMS_WITHOUT_SOURCE_MIN_ITEMS and missing / total > ITEMS_WITHOUT_SOURCE_MIN_SHARE:
        return LintFinding(
            "items_without_source",
            f"{missing} of {total} story items carry no Source: line — every "
            "item ends on its own Source: line with the article's exact URL",
            metrics,
        )
    return LintFinding("items_without_source", "", metrics)


# --- counterpoint_keyed_to_lead (MAG 7) ----------------------------------

COUNTERPOINT_MIN_SHARED = 2


def lint_counterpoint_keyed_to_lead(digest: str) -> Optional[LintFinding]:
    lead_body = None
    for title, body in sections(digest):
        if title in ("Top News", "Top Story", "Lead"):
            lead_body = body
            break
    cp = section_body(digest, "The Counterpoint") or section_body(digest, "Counterpoint")
    if lead_body is None or cp is None:
        return None
    lead_items = items(lead_body)
    lead = lead_items[0] if lead_items else lead_body
    shared = len(_salient(_prose(lead)) & _salient(_prose(cp)))
    metrics = {"counterpoint_lead_shared_tokens": shared}
    if shared < COUNTERPOINT_MIN_SHARED:
        return LintFinding(
            "counterpoint_keyed_to_lead",
            "The Counterpoint does not engage the lead story — it is the "
            "strongest argument against the lead item's framing, never an "
            "unrelated item from another company",
            metrics,
        )
    return LintFinding("counterpoint_keyed_to_lead", "", metrics)


# --- dc_items_unlabelled (AI Chips) --------------------------------------

_DC_STATE_RE = re.compile(
    r"\b(?:announced|planned|proposed|under construction|being built|energi[sz]ed|"
    r"operational|online|commissioned)\b", re.IGNORECASE)
_MW_RE = re.compile(r"\d[\d,.]*\s*(?:MW|GW|megawatts?|gigawatts?)\b")
# What makes an item a SITE (a build with a place), as opposed to a power
# architecture, a product, a policy or a grid deal: a capacity figure, or a
# build cue. Sep 24 2026: the lint used to require a state word AND a MW
# figure of EVERY item in the section, but the prompt exempts non-site items
# from the state word and forbids estimating a capacity the source did not
# give — AI Chips Ep3's three power-architecture / product items could never
# pass, fired 3/3, survived the retry, and the ledger blamed the model.
# Descriptive words ("campus", "hyperscale") are NOT cues: Ep3's 800 VDC
# whitepaper item said "not a named campus" and would have counted.
_DC_BUILD_CUE_RE = re.compile(
    r"\b(?:breaks? ground|broke ground|groundbreaking|construction|energi[sz]ation|"
    r"energi[sz]ed|commissioned|hectares?|acres?|square (?:feet|metres|meters)|"
    r"sq\.? ?ft|substation)\b", re.IGNORECASE)


def _is_dc_site_item(item: str) -> bool:
    return bool(_MW_RE.search(item) or _DC_BUILD_CUE_RE.search(item))


def dc_items_unlabelled(digest: str) -> List[str]:
    """SITE items (a capacity figure or a build cue) whose text carries no
    build state. An item that is not a site is never a finding."""
    body = section_body(digest, "Data Centres & Power") or section_body(digest, "Data Centers & Power")
    if body is None:
        return []
    bad = []
    for it in items(body):
        if _is_dc_site_item(it) and not _DC_STATE_RE.search(it):
            bad.append(it.splitlines()[0].strip("* ")[:80])
    return bad


def lint_dc_items_unlabelled(digest: str) -> Optional[LintFinding]:
    """Fires when MORE THAN HALF of the section's items lack the label — a
    single cooling deal or a site with no published capacity is not a
    defect, a section written without the build-state discipline is."""
    body = section_body(digest, "Data Centres & Power") or section_body(digest, "Data Centers & Power")
    all_items = items(body or "") if body else []
    total = len(all_items)
    sites = sum(1 for it in all_items if _is_dc_site_item(it))
    bad = dc_items_unlabelled(digest)
    metrics = {"dc_items_unlabelled": len(bad), "dc_items_total": total,
               "dc_items_sites": sites}
    # Two site items at least: one ambiguous item is not a section written
    # without the build-state discipline.
    if bad and sites >= 2 and len(bad) * 2 > sites:
        return LintFinding(
            "dc_items_unlabelled",
            f"{len(bad)} data-centre SITE item(s) carry no build state — a site "
            "item's first sentence says whether it is announced, under "
            "construction or energized, with the capacity and location the "
            "source gives (a deal, policy or architecture item needs no state "
            "word, and a capacity the source omits is never estimated)",
            metrics,
        )
    return LintFinding("dc_items_unlabelled", "", metrics)


# --- evidence_rung / dose_terms (the health shows) ------------------------

_STUDY_RE = re.compile(
    r"\b(?:study|studies|trial|paper|meta-analysis|cohort|randomi[sz]ed|"
    r"researchers (?:found|showed|reported)|findings? (?:show|suggest))\b",
    re.IGNORECASE)
_RUNG_RE = re.compile(
    r"\b(?:mice|mouse|rats?|rodents?|in vitro|cell(?:s| lines?| cultures?)|worms?|"
    r"flies|zebrafish|primates?|monkeys?|dogs?|pigs?|sheep|lambs?|"
    r"phase\s*(?:[1-4]|I{1,3}|IV)\b|human(?:s)?|people|patients|participants|"
    r"adults|volunteers|women|men|subjects|observational|preclinical|animal|"
    r"placebo|double-blind|approved|n\s*=\s*\d+|\d[\d,]*\s*(?:people|patients|"
    r"participants|adults|volunteers|women|men|subjects))\b",
    re.IGNORECASE)


def evidence_rung_missing(digest: str) -> List[str]:
    """Items that name a study without, anywhere in the item, saying who or
    what it was in. Judged per ITEM, not per sentence: "Neither trial
    showed slowing" is fine when the sentence before it named the two
    trials' 3,800 participants (Peptides Ep1)."""
    out: List[str] = []
    for title, body in sections(digest):
        if title in ("What This Show Covers", "Evidence Ledger"):
            continue
        blocks = items(body) or ([body] if body.strip() else [])
        for block in blocks:
            flat = re.sub(r"\s+", " ", block)
            if _STUDY_RE.search(flat) and not _RUNG_RE.search(flat):
                out.append(flat.strip("* ")[:140])
    return out


def lint_evidence_rung(digest: str) -> Optional[LintFinding]:
    bad = evidence_rung_missing(digest)
    metrics = {"evidence_rung_missing": len(bad)}
    if bad:
        return LintFinding(
            "evidence_rung",
            f"{len(bad)} sentence(s) cite a study without saying what it was in — "
            "every finding names its rung in the same sentence: the organism "
            "or cell model, or the trial phase and the number of people",
            metrics,
        )
    return LintFinding("evidence_rung", "", metrics)


_DOSE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|ug|IU)\b(?:\s*/\s*(?:kg|day|week|dose))?|"
    r"\bmg/kg\b|\bsubq\b|\bsub-?cutaneous(?:ly)? inject|\breconstitut\w*|"
    r"\bdosing (?:protocol|schedule|regimen)|\bcycle (?:of|length)|\bstack(?:ed|ing)? (?:with|it)\b",
    re.IGNORECASE)


def dose_terms(digest: str) -> List[str]:
    return sorted({m.group(0) for m in _DOSE_RE.finditer(digest or "")})


def lint_dose_terms(digest: str) -> Optional[LintFinding]:
    hits = dose_terms(digest)
    metrics = {"dose_terms_found": len(hits)}
    if hits:
        return LintFinding(
            "dose_terms",
            "the digest states a dose, route, preparation or protocol — this "
            "show never does, in any framing; describe what a trial tested "
            "without its dose or regimen",
            metrics,
        )
    return LintFinding("dose_terms", "", metrics)


# --- spotlight_card (Peptides) ------------------------------------------

SPOTLIGHT_CARD_LABELS = (
    "What it is", "Humans given it", "Regulatory status", "Risks", "What it does not show",
)


def spotlight_card_missing(digest: str) -> List[str]:
    body = None
    for title, b in sections(digest):
        if title.lower().startswith("peptide spotlight"):
            body = b
            break
    if body is None:
        return list(SPOTLIGHT_CARD_LABELS)
    # Oct 30 2026: a slot is its label at the start of a line, bold or not.
    # The prompt asks for "each opening with its label and a colon"; the
    # model writes them plain, and the bold-only check fired on complete
    # cards every week (Ep6, Ep7), spending the structural regeneration.
    return [lab for lab in SPOTLIGHT_CARD_LABELS
            if not re.search(rf"(?im)^\s*[-*•]?\s*(?:\*\*)?{re.escape(lab)}\b", body)]


def lint_spotlight_card(digest: str) -> Optional[LintFinding]:
    missing = spotlight_card_missing(digest)
    metrics = {"spotlight_card_missing": len(missing)}
    if missing:
        return LintFinding(
            "spotlight_card",
            "the Peptide Spotlight is missing card slot(s): " + ", ".join(missing)
            + " — the Spotlight carries all five labelled slots every week",
            metrics,
        )
    return LintFinding("spotlight_card", "", metrics)


# --- hook_supported ---------------------------------------------------------
# Oct 8 2026 (Tesla Ep627, flagged by an outside review): the hook read "A
# Dutch battery developer is scaling gigawatt-hour projects into Germany,
# widening the path for Tesla Megapack deployments across Europe." Its item,
# its source and its claims ledger never mention Tesla's Megapack — the hook
# added a show angle the reporting does not carry, and the claims gate does
# not read the hook. Ep582 did the same. A name the hook gives must appear
# in the digest outside the hook and the "What You Need to Know" line that
# restates it. Opt-in: on 956 committed digests the check is precise on
# Tesla (2 of 70, both real) and noisy where a show frames every story for
# its audience (Modern Investing's "TFSA holders").

_HOOK_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9’'\-.]*")
_NOT_A_NAME = frozenset({
    "The", "A", "An", "In", "On", "At", "For", "After", "Before", "As", "With",
    "Its", "It", "This", "That", "These", "Those", "AI", "US", "UK",
    "North", "South", "East", "West", "Southeast", "Northeast", "Southwest",
    "Northwest", "Middle", "Central", "United", "Gulf", "Pacific", "Atlantic",
    "Earth", "Moon", "President", "Prime", "Minister", "Secretary", "Court",
    "Judge", "Senate", "House", "Fed",
})
_DEMONYM_RE = re.compile(r"(?:an|ian|ean|ese|ish|ic|ern|ans)$")
_MONTHS_DAYS = frozenset(
    "January February March April May June July August September October "
    "November December Monday Tuesday Wednesday Thursday Friday Saturday "
    "Sunday".split())


def hook_names(hook: str) -> List[str]:
    """Proper names in the hook (never its first word, never a demonym,
    a direction or a title — those are framing, not reporting)."""
    out: List[str] = []
    for i, raw in enumerate(_HOOK_NAME_RE.findall(hook or "")):
        if i == 0:
            continue
        tok = re.sub(r"(?:’s|'s)$", "", raw).strip(".")
        for part in tok.split("-"):
            if (len(part) < 3 or not part[0].isupper() or part in _NOT_A_NAME
                    or part in _MONTHS_DAYS or _DEMONYM_RE.search(part)):
                continue
            out.append(part)
    return out


def hook_unsupported_names(digest: str) -> Optional[List[str]]:
    hook = hook_line(digest)
    if not hook:
        return None
    rest = _WYNTK_RE.sub(" ", _HOOK_RE.sub(" ", digest or "")).lower()
    return [n for n in hook_names(hook) if n.lower().rstrip("s") not in rest]


# Oct 17 2026 (slate review): two more shapes of the same failure.
#
# * A FIGURE in the hook that no item carries. A spoken hook figure is the
#   episode's first fact; when no item states it, nothing the claims gate
#   reads vouches for it.
# * A figure joined to a consequence its own item never names. Modern
#   Investing Ep203's hook read "September PPI at 6.3% versus 5.3% estimate
#   raises Bank of Canada hike odds before October 28." The 6.3% item is a US
#   Bureau of Labor Statistics print and never mentions the Bank of Canada;
#   the Bank of Canada sentence sits in Market Pulse, a different section,
#   and says nothing about PPI. Every name and figure appears SOMEWHERE, so
#   the name check above passed — the defect is the join. A hook name that
#   is in the digest, but in no section carrying the hook's figure, is that
#   join.
#
# Figures are digit-written only (a spelled-out "forty billion" is not
# compared); a year, a percentage, a count and a price are all figures.

_HOOK_FIGURE_RE = re.compile(r"(?<![\w.,])\$?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?![\w])")
_BODY_FIGURE_RE = _HOOK_FIGURE_RE


def _figure_key(whole: str, frac: Optional[str]) -> str:
    key = whole.replace(",", "").lstrip("0") or "0"
    frac = (frac or "").rstrip("0")
    return f"{key}.{frac}" if frac else key


def figures_in(text: str) -> List[str]:
    """Digit-written figures in *text*, normalised (``16,000`` → ``16000``,
    ``6.30`` → ``6.3``). URLs are ignored."""
    return [_figure_key(m.group(1), m.group(2))
            for m in _BODY_FIGURE_RE.finditer(_URL_RE.sub(" ", text or ""))]


#: A number right after a capitalised word is part of a name ("S&P 500",
#: "Model 3", "Falcon 9") or a calendar date ("October 28") — not a figure
#: the hook reports. A sentence-opening word ("After 16,000-plus…") or a
#: function word is neither.
_NAME_BEFORE_RE = re.compile(r"(?:^|\s)([A-Z][\w&’'.-]*)\s+$")


def _is_name_number(text: str, start: int) -> bool:
    m = _NAME_BEFORE_RE.search(text[:start])
    if not m:
        return False
    word = m.group(1)
    if word in _MONTHS_DAYS:
        return True
    if not text[:m.start(1)].strip():
        return False  # the hook's first word
    return word not in _NOT_A_NAME


def hook_figures(hook: str) -> List[str]:
    out: List[str] = []
    text = _URL_RE.sub(" ", hook or "")
    for m in _HOOK_FIGURE_RE.finditer(text):
        if _is_name_number(text, m.start()):
            continue
        f = _figure_key(m.group(1), m.group(2))
        if f not in out:
            out.append(f)
    return out


def _hook_free_text(digest: str) -> str:
    return _WYNTK_RE.sub(" ", _HOOK_RE.sub(" ", digest or ""))


def figure_matches(hook_fig: str, body_figs: Iterable[str]) -> bool:
    """A hook figure is carried when a body figure equals it at the hook's
    own precision (the hook rounds: "514,158 pesos" for 514,158.45)."""
    try:
        want = float(hook_fig)
    except ValueError:
        return False
    decimals = len(hook_fig.split(".", 1)[1]) if "." in hook_fig else 0
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    for g in body_figs:
        try:
            if abs(float(g) - want) <= tol:
                return True
        except ValueError:
            continue
    return False


def hook_unsupported_figures(digest: str) -> Optional[List[str]]:
    """Hook figures no line of the digest outside the hook/WYNTK carries."""
    hook = hook_line(digest)
    if not hook:
        return None
    rest = set(figures_in(_hook_free_text(digest)))
    return [f for f in hook_figures(hook) if not figure_matches(f, rest)]


def hook_unjoined_names(digest: str) -> Optional[List[str]]:
    """Hook names that appear in the digest but in NO section that carries
    one of the hook's figures. ``None`` when the hook has no figure an item
    carries (nothing to anchor on)."""
    hook = hook_line(digest)
    if not hook:
        return None
    figs = set(hook_figures(hook))
    if not figs:
        return None
    carrying = [
        body.lower() for _t, body in sections(_hook_free_text(digest))
        if any(figure_matches(f, figures_in(body)) for f in figs)
    ]
    if not carrying:
        return None
    rest = _hook_free_text(digest).lower()
    out: List[str] = []
    for name in hook_names(hook):
        key = name.lower().rstrip("s")
        if key not in rest:
            continue  # the plain name check reports it
        if not any(key in body for body in carrying) and name not in out:
            out.append(name)
    return out


def lint_hook_supported(digest: str) -> Optional[LintFinding]:
    missing = hook_unsupported_names(digest)
    if missing is None:
        return None
    figures = hook_unsupported_figures(digest) or []
    unjoined = hook_unjoined_names(digest) or []
    metrics = {"hook_unsupported_names": len(missing),
               "hook_unsupported_figures": len(figures),
               "hook_unjoined_names": len(unjoined)}
    notes: List[str] = []
    if missing:
        notes.append(
            "the HOOK names something no item in the digest reports ("
            + ", ".join(sorted(set(missing))) + ")")
    if figures:
        notes.append(
            "the HOOK states a figure no item in the digest carries ("
            + ", ".join(figures) + ")")
    if unjoined:
        notes.append(
            "the HOOK ties its figure to something the item reporting that "
            "figure never mentions (" + ", ".join(unjoined) + ")")
    if notes:
        return LintFinding(
            "hook_supported",
            "; ".join(notes) + " — the hook states only what the lead item "
            "and its source say; every figure in it is in that item, and it "
            "never adds an angle or a consequence the reporting does not carry",
            metrics,
        )
    return LintFinding("hook_supported", "", metrics)


# --- deep_dive_distinct / deep_dive_distinct_measure ------------------------
# Nov 3 2026 (the six-month review's repetition reader, recomputed by the
# skeptic with this module's own ``_salient``): the flagship deep dive was a
# second PASS on a body item rather than a second STORY — Tesla Ep647's First
# Principles repeats item 9 nearly clause for clause, Planetterrian Ep227's
# Science Deep Dive IS item 10, SpaceX Ep143's Engineering Deep Dive carries
# item 2's exact figures. Tesla's TOPIC DISTINCTNESS rule has been in the
# prompt since Sep 5 and the Tesla ledger's ``do_not_retry`` forbids a third
# prompt-only de-seed "without a data-side or gate change": this is that gate.
#
# The measure is the share of a body item's salient vocabulary the essay
# carries (``|item ∩ essay| / |item|`` over items of eight or more salient
# tokens; the best item wins). Replayed over each show's last eight digests
# at ``DEEP_DIVE_DISTINCT_MAX`` 0.5: Tesla 3/8 (0.60, 0.51, 0.58),
# Planetterrian 4/8 (0.56-0.67), SpaceX 2/8, Fascinating Frontiers 2/8,
# Models & Agents 1/8, MAG 7 0/8, Omni View 0/8, AI Chips 0/8 (the control,
# max 0.35). Two forms, so the regeneration share
# (``digest_structural_regen_share_7d``, ceiling 0.22) is read before a show
# pays for the rule: ``deep_dive_distinct_measure`` records the containment
# and never fires; ``deep_dive_distinct`` fires and rides the one-shot
# structural regeneration like every other lint (never a script retry). The
# metric's consumer is the ``deep-dive-distinct-2026-11-03`` register
# readout: the per-show median of ``deep_dive_contains_body_item`` from
# ``metrics_ep*.json``.

#: The essay sections, in the order the lint looks for them (the first
#: present, non-empty one is judged).
DEEP_DIVE_DISTINCT_SECTIONS = (
    "Tesla First Principles", "Engineering Deep Dive", "Under the Hood",
    "Science Deep Dive", "Cosmic Deep Dive", "Understanding the Issue",
    "Planetterrian Spotlight", "Cosmic Spotlight", "The Thread",
    "Practitioner Deep Dive",
)
#: At or above this share of a body item's salient vocabulary the essay is a
#: second telling of that item.
DEEP_DIVE_DISTINCT_MAX = 0.5
#: An item with fewer salient tokens than this is a one-liner (Also Today),
#: not a story an essay could re-tell.
DEEP_DIVE_DISTINCT_MIN_ITEM_TOKENS = 8


@dataclass
class DeepDiveContainment:
    section: str
    #: Share of the best body item's salient vocabulary the essay carries.
    share: float
    #: 1-based position of that item among the digest's story items.
    item_number: int
    item_title: str


def deep_dive_section(digest: str) -> Optional[Tuple[str, str]]:
    """``(name, body)`` of the first present, non-empty deep-dive section."""
    for name in DEEP_DIVE_DISTINCT_SECTIONS:
        body = section_body(digest, name)
        if body is not None and body.strip():
            return name, body
    return None


_ITEM_TITLE_BOLD_RE = re.compile(r"^\s*(?:\d+[.)]\s*)?\*\*(.+?)\*\*")
_ITEM_TITLE_PREFIX_RE = re.compile(r"^\s*\d+[.)]\s*")


def _item_title(head: str) -> str:
    """The item's title for the finding's note: the bold span of its head
    line (``1. **Title**: Outlet`` → ``Title``; ``**Title:** body`` →
    ``Title``), else the head without its number (an Omni View ``3) Title``
    heading). Never a stray ``*``; clipped through ``engine.titles``."""
    m = _ITEM_TITLE_BOLD_RE.match(head or "")
    text = m.group(1) if m else _ITEM_TITLE_PREFIX_RE.sub("", head or "")
    text = " ".join(text.replace("*", " ").split()).rstrip(":").strip()
    return clip_words(text, HEADLINE_CHAPTER_TITLE_MAX)


def deep_dive_item_containment(digest: str) -> Optional[DeepDiveContainment]:
    """The body item whose salient vocabulary the deep dive carries most of,
    or ``None`` when the digest has no deep-dive section or no item of
    ``DEEP_DIVE_DISTINCT_MIN_ITEM_TOKENS`` to compare. Items are read from
    every section EXCEPT the deep-dive sections, so an essay that opens on
    a bold line never scores against itself."""
    found = deep_dive_section(digest)
    if found is None:
        return None
    name, body = found
    essay = _salient(_prose(body))
    if not essay:
        return None
    skip = {s.lower() for s in DEEP_DIVE_DISTINCT_SECTIONS}
    best: Optional[DeepDiveContainment] = None
    n = 0

    def _consider(head: str, text: str) -> None:
        nonlocal best
        toks = _salient(_prose(text))
        if len(toks) < DEEP_DIVE_DISTINCT_MIN_ITEM_TOKENS:
            return
        share = round(len(toks & essay) / len(toks), 3)
        if best is None or share > best.share:
            best = DeepDiveContainment(name, share, n, _item_title(head))

    # The items are read in every shape the shows write (``story_item_count``,
    # Oct 21 2026 — the two-shape reader "read every inline-headed item as
    # missing"): a numbered item, a bold title alone on its line, a bold head
    # carrying a URL (Models & Agents writes ``**Title:** body … Source:``
    # inline) and an Omni View ``### N) Title`` heading, whose section IS the
    # story — read as ONE item, so its ``**Read more (sources):**`` block
    # never stands in for it.
    for title, sec_body in sections(digest, full_titles=True):
        short = title.split(":")[0].strip().strip("*")
        if short.lower() in skip:
            continue
        if _HEADING_ITEM_RE.match(title):
            n += 1
            _consider(title, title + "\n" + sec_body)
            continue
        for block in items(sec_body):
            head = block.splitlines()[0]
            if not (_NUMBERED_ITEM_RE.match(head) or _HEADLINE_ITEM_RE.match(head)
                    or (_BOLD_HEAD_RE.match(head) and urls_in(block))):
                continue
            n += 1
            _consider(head, block)
    return best


def _deep_dive_distinct(digest: str, fire: bool) -> Optional[LintFinding]:
    lint = "deep_dive_distinct" if fire else "deep_dive_distinct_measure"
    best = deep_dive_item_containment(digest)
    if best is None:
        return None
    metrics = {"deep_dive_contains_body_item": best.share}
    if fire and best.share >= DEEP_DIVE_DISTINCT_MAX:
        return LintFinding(
            lint,
            f"{best.section} re-tells item {best.item_number} ({best.item_title}) "
            "— write it on the mechanism or the second story that item did not "
            "touch, with figures from a fetched article it did not use",
            metrics,
        )
    return LintFinding(lint, "", metrics)


def lint_deep_dive_distinct(digest: str) -> Optional[LintFinding]:
    """The firing form: at ``DEEP_DIVE_DISTINCT_MAX`` the finding rides the
    one-shot structural regeneration."""
    return _deep_dive_distinct(digest, fire=True)


def lint_deep_dive_distinct_measure(digest: str) -> Optional[LintFinding]:
    """The measure form: records ``deep_dive_contains_body_item`` and never
    fires — a show reads a week of it before listing ``deep_dive_distinct``."""
    return _deep_dive_distinct(digest, fire=False)


# ---------------------------------------------------------------------------
# Context lints (Oct 17 2026): checks that need the run's ARTICLE LIST, not
# just the digest. run_show passes ``context={"articles": [...]}``; called
# without one (a replay over committed digests) they measure nothing.
# ---------------------------------------------------------------------------

# --- board_venue_mix --------------------------------------------------------
# Prediction Markets Ep024 and Ep025 put ONE market on The Board (a Polymarket
# ceasefire, then a Manifold play-money question about a chatbot) while the
# hook supplied eight to ten markets from three venues. The root cause was
# upstream (story_recurrence marked nine of ten board markets "already
# covered — pick a different story"; the board articles are now exempt), and
# this is the guard: when two venues supplied markets, the Board carries
# markets from at least two.

def lint_board_venue_mix(digest: str, context: Optional[dict] = None) -> Optional[LintFinding]:
    if not context:
        return None
    from engine.prediction_board import board_venues_in, supplied_board_venues

    supplied = supplied_board_venues(context.get("articles") or [])
    body = section_body(digest, "The Board")
    if body is None:
        return None
    shipped = board_venues_in(body)
    metrics = {"board_venues": sorted(shipped), "board_venues_supplied": sorted(supplied)}
    if len(supplied) >= 2 and len(shipped & supplied) < 2:
        return LintFinding(
            "board_venue_mix",
            "The Board carries markets from "
            + (("only " + ", ".join(sorted(shipped))) if shipped else "no venue")
            + " while the market articles above come from "
            + ", ".join(sorted(supplied)) + " — The Board carries at least one "
            "market from each of two venues whenever two venues supplied markets",
            metrics,
        )
    return LintFinding("board_venue_mix", "", metrics)


# --- deep_dive_fetched_source -----------------------------------------------
# AI Chips Ep026's Teardown (825 words on wafer bow, Zeiss DUNE and Von
# Ardenne's glass-via coating) was written from an EE Times article whose page
# the runner never read: www.eetimes.com timed out on every fetch (Ep019, 021,
# 022, 025, 026), so the prompt held a feed teaser, and both Teardown claims
# the gate checked were "unverified_unreachable". The prompt already says the
# Teardown is built from ONE article whose full text is printed; this is that
# rule in code. A section is read-sourced when a URL it cites, or an outlet it
# names, belongs to an article that carried full text into the prompt.

#: Deep-dive sections whose source status the lint READS
#: (``deep_dive_source_read`` is measured on the first one present). Nov 3
#: 2026: Env Intel's Practitioner Deep Dive joins (shows/env_intel.yaml opts
#: into the lint) — the section is built from one regulation or guidance
#: document the run READ, never a career the host does not have — and so do
#: the flagship essays (``DEEP_DIVE_DISTINCT_SECTIONS``, the digest-lints
#: pass), so the share of essays written from a read page is a number before
#: it is a rule. A show that lists ``deep_dive_fetched_source`` with a section
#: name missing here gets a lint that can never measure;
#: ``tests/test_env_intel_sources_2026_11_03.py`` and
#: ``tests/test_deep_dive_distinct_2026_11_03.py`` pin the names.
DEEP_DIVE_FETCHED_SECTIONS = ("The Teardown",) + DEEP_DIVE_DISTINCT_SECTIONS
#: The sections whose digest prompt STATES the rule (built from ONE article
#: whose full text is printed, the outlet named, the section ending on its
#: Source line): only these fire. The flagship essays are measured until
#: their prompts carry the rule — replayed over each show's last eight
#: digests on Nov 3 2026, Tesla's First Principles cites nothing but the
#: show's own X handle (8/8), the Planetterrian, SpaceX, Omni View, Models &
#: Agents and Fascinating Frontiers essays cite or name no article at all
#: (0/8 each) and MAG 7's Thread ends on a Source line on 6/8, so a firing
#: form would spend the one-shot regeneration on six shows every day against
#: the 0.22 share ceiling (``digest_structural_regen_share_7d``). A section
#: moves here when its prompt states the rule.
DEEP_DIVE_FETCHED_FIRING_SECTIONS = ("The Teardown", "Practitioner Deep Dive")
#: Below this much text an article was a teaser, not a read page.
READ_ARTICLE_MIN_CHARS = 1200


def _norm_url(url: str) -> str:
    from engine.claims import normalize_source_url

    return normalize_source_url(url or "")


def read_articles(articles) -> List[dict]:
    return [a for a in articles or []
            if len(str(a.get("full_text") or "").strip()) >= READ_ARTICLE_MIN_CHARS]


def _outlet_named(outlet: str, text_low: str) -> bool:
    o = " ".join((outlet or "").lower().split())
    if len(o) < 3:
        return False
    return re.search(r"(?<![\w])" + re.escape(o) + r"(?![\w])", text_low) is not None


def deep_dive_source_status(body: str, articles) -> Tuple[Optional[bool], List[str]]:
    """``(read, names)``: ``read`` is True when the section cites or names a
    read article, False when everything it cites or names was unread, None
    when it identifies no article at all. ``names`` are the unread outlets
    or URLs it leaned on."""
    arts = list(articles or [])
    read = read_articles(arts)
    read_urls = {_norm_url(a.get("url") or "") for a in read}
    # A social post is never the article a deep dive was built from, and
    # Tesla's essay ends on the show's own X handle (the feedback line):
    # read as a citation, the essay was "built from an unread page" 8/8.
    cited = [u for u in urls_in(body) if _norm_url(u) and not _X_HOST_RE.match(u)]
    if cited:
        if any(_norm_url(u) in read_urls for u in cited):
            return True, []
        return False, cited[:3]
    low = " ".join((body or "").lower().split())
    named = {str(a.get("source_name") or "").strip() for a in arts
             if _outlet_named(str(a.get("source_name") or ""), low)}
    named.discard("")
    if not named:
        return None, []
    read_named = {str(a.get("source_name") or "").strip() for a in read}
    if named & read_named:
        return True, []
    return False, sorted(named)


def lint_deep_dive_fetched_source(digest: str, context: Optional[dict] = None) -> Optional[LintFinding]:
    if not context:
        return None
    articles = context.get("articles") or []
    for name in DEEP_DIVE_FETCHED_SECTIONS:
        body = section_body(digest, name)
        if body is None or not body.strip():
            continue
        status, leaned_on = deep_dive_source_status(body, articles)
        metrics = {"deep_dive_source_read": status,
                   "deep_dive_read_candidates": len(read_articles(articles))}
        if status is True:
            return LintFinding("deep_dive_fetched_source", "", metrics)
        if not read_articles(articles):
            # Nothing was read today: the prompt's own fallback (leave the
            # section out) is the only honest answer, and a retry cannot do
            # better, so this measures without firing.
            return LintFinding("deep_dive_fetched_source", "", metrics)
        if name not in DEEP_DIVE_FETCHED_FIRING_SECTIONS:
            # Measured, never fired: the prompt behind this essay does not
            # state the rule yet (DEEP_DIVE_FETCHED_FIRING_SECTIONS).
            return LintFinding("deep_dive_fetched_source", "", metrics)
        what = (", ".join(leaned_on) if leaned_on else "no named article")
        return LintFinding(
            "deep_dive_fetched_source",
            f"{name} is built from an article whose full text was never read "
            f"({what}) — build it from ONE article above that carries a FULL "
            f"TEXT block, name its outlet, and end {name} on that article's "
            "Source line",
            metrics,
        )
    return None


# --- hook_figure_sourced (the narrative shows) ------------------------------
# Nov 3 2026: Unintended Consequences Ep161's hook, "Over 500 native species
# vanished…", rests on a ledger entry the gate marked unverified_unreachable
# (the literature says about 200) and Ep160's "25 percent more housing
# starts" on an unverified_quote_mismatch, while the Oct 10 rule says UC and
# FPD lead on a named person and a SOURCED hook number. ``hook_supported``
# checks a hook figure against the digest's own items; a narrative show has
# no items, so its hook figure is checked against what the run READ: every
# digit-written hook figure (``hook_figures``) must appear in the full text
# of a read research article (``read_articles``, ``source_kind ==
# "research"``) OR in the episode's own claims ledger — the skeptic's
# amendment: a figure the page states in words is traced through the ledger
# entry the model wrote for it (which the gate then verifies), never a false
# fire on a spelled figure. The ledger is ``context["claims"]`` when the
# caller supplies it, else a ```claims fence still in the digest text, else
# the stash the generation stage left (``engine.claims.peek_stashed_claims``
# — the ledger of the digest being linted; run_show is untouched). A figure
# found nowhere fires and rides the one-shot structural regeneration; the
# gate runs after the lints, so this is the pre-gate check. The metric's
# consumer is the ``narrative-hooks-sourced-2026-11-03`` register readout.

_LEDGER_TEXT_KEYS = ("claim", "supporting_quote", "episode_span")


def _ledger_for(digest: str, context: dict) -> List[dict]:
    if "claims" in context:
        return [c for c in (context.get("claims") or []) if isinstance(c, dict)]
    from engine.claims import extract_claims_block, peek_stashed_claims

    _clean, fenced = extract_claims_block(digest or "")
    if fenced is not None:
        return fenced
    return [c for c in (peek_stashed_claims() or []) if isinstance(c, dict)]


def _ledger_figures(claims: List[dict]) -> List[str]:
    out: List[str] = []
    for c in claims:
        out.extend(figures_in(" ".join(str(c.get(k) or "") for k in _LEDGER_TEXT_KEYS)))
    return out


def hook_unsourced_figures(digest: str, context: dict) -> Optional[List[str]]:
    """Hook figures that sit in no read research article and no ledger
    entry. ``None`` when the digest has no hook; ``[]`` when the hook
    carries no digit-written figure."""
    hook = hook_line(digest)
    if not hook:
        return None
    figs = hook_figures(hook)
    if not figs:
        return []
    carried: set = set()
    for a in read_articles(context.get("articles") or []):
        if a.get("source_kind") != "research":
            continue
        carried.update(figures_in(str(a.get("full_text") or "")))
    carried.update(_ledger_figures(_ledger_for(digest, context)))
    return [f for f in figs if not figure_matches(f, carried)]


def lint_hook_figure_sourced(digest: str, context: Optional[dict] = None) -> Optional[LintFinding]:
    if not context:
        return None
    missing = hook_unsourced_figures(digest, context)
    if missing is None:
        return None
    metrics = {"hook_figures_unsourced": len(missing)}
    if missing:
        return LintFinding(
            "hook_figure_sourced",
            "the hook's " + ", ".join(missing) + " is in no fetched source — "
            "lead on a figure the sources carry, or on the named person and "
            "the measured thing without the number",
            metrics,
        )
    return LintFinding("hook_figure_sourced", "", metrics)


# ---------------------------------------------------------------------------
# Offshore North Ep012 review (Nov 8 2026)
# ---------------------------------------------------------------------------
#
# A listener review of Offshore North Ep012 (2 Nov) found five defects, each
# one a rule the digest prompt already stated:
#
# * the hook led on Thomas Ruyant withdrawing from the Route du Rhum — Ep006's
#   hook six weeks earlier — because a new franceinfo article retold it
#   (``hook_repeats_past_lead``);
# * "contraint de stopper" (forced to stop) became Anthony Marchand "out of a
#   race", and a skipper heading to port to repair became "removed from
#   contention" (``stop_told_as_retirement``);
# * a team video published 31 October was narrated as coverage of "the
#   conditions the fleet faced after the 1 November start" — a preview told as
#   a result (``preview_told_as_result``);
# * Plain Sailing quoted a campaign budget and an insurance share with no
#   source (``explainer_figures_sourced``);
# * "115 solo boats" sat in no fetched article and against the field guide's
#   sourced 118 (``item_figures_sourced``).
#
# Like every lint here they only feed the one-shot structural regeneration.

#: Sections that carry no sourced news item.
_NON_ITEM_SECTIONS = frozenset({
    "plain sailing", "the countdown", "sources", "countdown", "",
})

_SOURCE_LINE_RE = re.compile(r"\bSource:\s*\[?|\]\([^)]*\)")


def sourced_items(digest: str, skip: Iterable[str] = _NON_ITEM_SECTIONS
                  ) -> List[Tuple[str, str, List[str]]]:
    """``(section, text, urls)`` for every sourced item outside *skip*.

    An item is the run of paragraphs that ends on one carrying a URL — the
    shape of a digest whose items are plain paragraphs closing on a
    ``Source:`` line (Offshore North) as well as the bold-headed ones. A
    trailing run with no URL is not an item."""
    skip_low = {s.lower() for s in skip}
    out: List[Tuple[str, str, List[str]]] = []
    for title, body in sections(digest):
        if title.strip().lower() in skip_low:
            continue
        buf: List[str] = []
        for para in re.split(r"\n\s*\n", body or ""):
            para = para.strip()
            if not para or para.startswith(">") or para.startswith("**HOOK") \
                    or para.startswith("**TITLE") or para.startswith("**Week"):
                continue
            buf.append(para)
            urls = urls_in(para)
            if urls:
                out.append((title, "\n\n".join(buf), urls))
                buf = []
    return out


def _article_index(articles) -> Dict[str, dict]:
    idx: Dict[str, dict] = {}
    for a in articles or []:
        for key in ("url", "aggregator_url"):
            u = _norm_url(str(a.get(key) or ""))
            if u:
                idx.setdefault(u, a)
    return idx


def _article_text(a: dict) -> str:
    return " ".join(str(a.get(k) or "") for k in
                    ("title", "description", "content_text", "full_text"))


def _item_sources(urls: List[str], idx: Dict[str, dict]) -> List[dict]:
    out = []
    for u in urls:
        a = idx.get(_norm_url(u))
        if a is not None:
            out.append(a)
    return out


def _item_subject(text: str) -> str:
    prose = _prose(text)
    first = _SENT_SPLIT.split(prose.strip(), maxsplit=1)[0] if prose.strip() else ""
    return clip_words(first, 70)


# --- hook_repeats_past_lead -------------------------------------------------

#: How many past episodes' hooks the lead is compared with. Ep012 repeated a
#: hook six episodes back; twelve covers a weekly show's quarter.
PAST_HOOKS_WINDOW = 12
#: A token in at least this many of the window's hooks is the beat itself
#: (Route du Rhum, IMOCA, a race start), never evidence of a repeat.
PAST_HOOKS_COMMON_MIN = 2
#: Distinctive tokens (names + event words) a repeat shares with the old hook.
PAST_HOOKS_MIN_SHARED = 3

_HOOK_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ][\w’'À-ÿ-]*")
_HOOK_STOP = frozenset("""
a an the and or but of to in on at for from with by as is are was were be been
has have had his her its their this that these those it they he she not no
could would will can may might after before over into than then this week
because while about against also only still more most new first last
""".split())


def _stem(w: str) -> str:
    w = w.lower().strip("’'").replace("’s", "").replace("'s", "")
    for suf in ("ing", "ed", "es", "s", "n"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def _hook_parts(hook: str) -> Tuple[set, set]:
    """``(name stems, event stems)`` of a hook: capitalised words are names
    (the first word too — a hook often opens on its subject's name), the
    rest are the event's words."""
    names, events = set(), set()
    for i, w in enumerate(_HOOK_WORD_RE.findall(hook or "")):
        low = w.lower()
        if low in _HOOK_STOP or len(low) < 3:
            continue
        if w[0].isupper():
            if w in _MONTHS_DAYS or w in _NOT_A_NAME:
                continue
            names.add(_stem(w))
        elif not w[0].isupper():
            if len(low) >= 4:
                events.add(_stem(w))
    return names, events


def past_hooks(digests_dir, *, before_episode: Optional[int] = None,
               n: int = PAST_HOOKS_WINDOW) -> List[Tuple[str, str]]:
    """``[(YYYY-MM-DD, hook), ...]`` from the show's committed digests,
    newest first, episodes before *before_episode* only. Never raises."""
    from pathlib import Path

    rows = []
    try:
        for path in Path(digests_dir).glob("*_Ep*_*.md"):
            m = re.search(r"_Ep(\d{3,4})_(\d{4})(\d{2})(\d{2})\.md$", path.name)
            if not m:
                continue
            num = int(m.group(1))
            if before_episode is not None and num >= int(before_episode):
                continue
            hook = hook_line(path.read_text(encoding="utf-8"))
            if hook:
                rows.append((num, f"{m.group(2)}-{m.group(3)}-{m.group(4)}", hook))
    except Exception:  # noqa: BLE001 — a lint input can never cost an episode
        return []
    rows.sort(reverse=True)
    return [(d, h) for _n, d, h in rows[:n]]


def _beat_stems(beat_terms) -> set:
    out = set()
    for term in beat_terms or []:
        for w in _HOOK_WORD_RE.findall(str(term)):
            out.add(_stem(w))
    return out


def hook_repeat_match(hook: str, past: List[Tuple[str, str]],
                      beat_terms: Iterable[str] = ()) -> Optional[Tuple[str, str]]:
    """The past ``(date, hook)`` the hook re-leads with, else None.

    A repeat shares a name AND an event word with the past hook, and at
    least ``PAST_HOOKS_MIN_SHARED`` tokens in all, none of them common to the
    window. Replayed on Offshore North Ep001-012: fires
    on Ep012 (Ruyant withdrawing, Ep006) and Ep010 (the boat alongside in
    Gosport, Ep008), never on a race followed from start to finish (Ep003
    start, Ep004 leader). *beat_terms* (the show's own subject — its RSS
    keywords) never count: the skipper's name is the show, not a story."""
    if not hook or not past:
        return None
    parts = [(_hook_parts(h), d, h) for d, h in past]
    counts: Dict[str, int] = {}
    for (names, events), _d, _h in parts:
        for t in names | events:
            counts[t] = counts.get(t, 0) + 1
    common = {t for t, c in counts.items() if c >= PAST_HOOKS_COMMON_MIN}
    common |= _beat_stems(beat_terms)
    names, events = _hook_parts(hook)
    names -= common
    events -= common
    for (p_names, p_events), d, h in parts:
        shared_n, shared_e = names & p_names, events & p_events
        if shared_n and shared_e and len(shared_n | shared_e) >= PAST_HOOKS_MIN_SHARED:
            return d, h
    return None


def lint_hook_repeats_past_lead(digest: str, context: Optional[dict] = None) -> Optional[LintFinding]:
    past = list((context or {}).get("past_hooks") or [])
    hook = hook_line(digest)
    if not past or not hook:
        return None
    m = hook_repeat_match(hook, past, (context or {}).get("beat_terms") or ())
    metrics = {"hook_repeats_past_lead": 0 if m is None else 1}
    if m is None:
        return LintFinding("hook_repeats_past_lead", "", metrics)
    date, old = m
    return LintFinding(
        "hook_repeats_past_lead",
        f"the **HOOK:** leads with a story this show already led with on "
        f"{date} (“{clip_words(old, 60)}”) — lead with a development first "
        f"reported inside this week's window; an earlier event retold by a "
        f"new article is at most one dated clause of context, never the lead "
        f"and never \"this week\"",
        metrics,
    )


# --- stop_told_as_retirement ------------------------------------------------

#: The item says the competitor is out.
_RETIRED_CLAIM_RE = re.compile(
    r"\b(?:out of (?:the|a|this|her|his) (?:race|running)|forced? (?:\w+ )?out\b|"
    r"knock(?:s|ed)? (?:\w+ )?out|retire[sd]?\b|retiring\b|retirement|"
    r"abandon(?:s|ed|ing|ment)?\b|(?:from|out of) contention|"
    r"ends? (?:his|her|their) race|race is over|withdr[ae]w[ns]?\b|withdrawal)",
    re.IGNORECASE)
#: The source says so too (French and English).
_RETIRED_SOURCE_RE = re.compile(
    r"abandon|renonc|retir|forfait|withdr|l[’']éponge|hors course|pulls? out|"
    r"pulled out|out of the race|quit|ne prendra pas le départ|"
    r"ne poursuivra pas|met(?:tre)? fin",
    re.IGNORECASE)
#: Below this much source text nothing is judged.
_SOURCE_TEXT_MIN = 200


def stop_retirement_items(digest: str, articles) -> List[str]:
    idx = _article_index(articles)
    out: List[str] = []
    for _title, text, urls in sourced_items(digest):
        prose = _prose(text)
        claim = next((sent for sent in _SENT_SPLIT.split(prose)
                      if _RETIRED_CLAIM_RE.search(sent)), "")
        if not claim:
            continue
        srcs = _item_sources(urls, idx)
        src_text = " ".join(_article_text(a) for a in srcs)
        if len(src_text.strip()) < _SOURCE_TEXT_MIN:
            continue  # unread: nothing to judge against
        if not _RETIRED_SOURCE_RE.search(src_text):
            out.append(clip_words(claim.strip(), 90))
    return out


def lint_stop_told_as_retirement(digest: str, context: Optional[dict] = None) -> Optional[LintFinding]:
    if not context or not context.get("articles"):
        return None
    bad = stop_retirement_items(digest, context.get("articles"))
    metrics = {"stop_told_as_retirement": len(bad)}
    if not bad:
        return LintFinding("stop_told_as_retirement", "", metrics)
    return LintFinding(
        "stop_told_as_retirement",
        "these items say a competitor is out of the race, but their source "
        "reports a stop, a diversion or a repair, not a retirement: "
        + "; ".join(f"“{b}”" for b in bad)
        + " — say exactly what the source says (stopped, diverting to port, "
        "repairing, assessing the damage) and that the skipper is still in "
        "the race; a retirement is reported only when the source says so",
        metrics,
    )


# --- preview_told_as_result -------------------------------------------------

_MONTHS = ("january february march april may june july august september "
           "october november december").split()
_DATE_DM_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(m.title() for m in _MONTHS)
    + r")(?:,?\s+(\d{4}))?\b")
_DATE_MD_RE = re.compile(
    r"\b(" + "|".join(m.title() for m in _MONTHS)
    + r")\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b")
#: A sentence that looks ahead is a preview already.
_FORWARD_RE = re.compile(
    r"\b(?:will|would|shall|due|scheduled|set to|plans?|planned|planning|"
    r"ahead of|before|preview\w*|upcoming|next|(?:starts?|begins?|opens?) on|expected|"
    r"until|closes|opens|is on|runs from|counting down|days? (?:to|until|before)|"
    r"countdown|leading up|build-up|in the run-up|is set|aims?|intends?)\b",
    re.IGNORECASE)


def _source_date(a: dict):
    import datetime as _dt

    for key in ("page_published_date", "published_date"):
        raw = str(a.get(key) or "")[:10]
        try:
            return _dt.date.fromisoformat(raw)
        except ValueError:
            continue
    return None


def _dates_in(sentence: str, default_year: int):
    import datetime as _dt

    found = []
    for m in _DATE_DM_RE.finditer(sentence):
        day, mon, yr = int(m.group(1)), _MONTHS.index(m.group(2).lower()) + 1, m.group(3)
        found.append((day, mon, int(yr) if yr else default_year))
    for m in _DATE_MD_RE.finditer(sentence):
        mon, day, yr = _MONTHS.index(m.group(1).lower()) + 1, int(m.group(2)), m.group(3)
        found.append((day, mon, int(yr) if yr else default_year))
    out = []
    for day, mon, yr in found:
        try:
            out.append(_dt.date(yr, mon, day))
        except ValueError:
            continue
    return out


def preview_result_items(digest: str, articles) -> List[Tuple[str, str]]:
    """``(item subject, the later date)`` for items narrating, without a
    forward-looking word, an event dated after their source was published."""
    idx = _article_index(articles)
    out: List[Tuple[str, str]] = []
    for _title, text, urls in sourced_items(digest):
        dates = [d for d in (_source_date(a) for a in _item_sources(urls, idx)) if d]
        if not dates:
            continue
        src_date = max(dates)
        for sent in _SENT_SPLIT.split(_prose(text)):
            if _FORWARD_RE.search(sent):
                continue
            later = [d for d in _dates_in(sent, src_date.year) if d > src_date]
            if later:
                out.append((_item_subject(text), later[0].strftime("%-d %B %Y")))
                break
    return out


def lint_preview_told_as_result(digest: str, context: Optional[dict] = None) -> Optional[LintFinding]:
    if not context or not context.get("articles"):
        return None
    bad = preview_result_items(digest, context.get("articles"))
    metrics = {"preview_told_as_result": len(bad)}
    if not bad:
        return LintFinding("preview_told_as_result", "", metrics)
    return LintFinding(
        "preview_told_as_result",
        "these items narrate an event dated after their own source was "
        "published, as if the source had covered it: "
        + "; ".join(f"“{s}” ({d})" for s, d in bad)
        + " — a source published before an event is a PREVIEW: say what it "
        "expected or planned, in the future tense, and never what happened",
        metrics,
    )


# --- explainer_figures_sourced ----------------------------------------------

#: Explainer sections licensed to draw on general knowledge for MECHANISMS —
#: never for money, a share or a count about the current sport.
EXPLAINER_SECTIONS = ("Plain Sailing",)

_NUM_WORD = (r"(?:\d[\d,.]*|one|two|three|four|five|six|seven|eight|nine|ten|"
             r"eleven|twelve|fifteen|twenty|thirty|forty|fifty|sixty|seventy|"
             r"eighty|ninety|hundred|a few|several|dozens?)")
_AMOUNT_RE = re.compile(
    r"(?:[€$£]\s?\d[\d,.]*(?:\s*(?:million|billion|m|bn|k))?|"
    r"\b" + _NUM_WORD + r"(?:[\s-]+(?:to|and|or)[\s-]+" + _NUM_WORD + r")?"
    r"[\s-]+(?:million|billion|thousand|percent|per cent)\b|"
    r"\b\d[\d,.]*\s?%)",
    re.IGNORECASE)


def explainer_unsourced_amounts(digest: str) -> List[str]:
    out: List[str] = []
    for title, body in sections(digest):
        if title.strip().lower() not in {s.lower() for s in EXPLAINER_SECTIONS}:
            continue
        if urls_in(body):
            continue
        for m in _AMOUNT_RE.finditer(body):
            amt = " ".join(m.group(0).split())
            if amt not in out:
                out.append(amt)
    return out


def lint_explainer_figures_sourced(digest: str) -> Optional[LintFinding]:
    bad = explainer_unsourced_amounts(digest)
    metrics = {"explainer_unsourced_amounts": len(bad)}
    if not bad:
        return LintFinding("explainer_figures_sourced", "", metrics)
    return LintFinding(
        "explainer_figures_sourced",
        "the explainer states money, share or percentage figures with no "
        "source (" + ", ".join(bad[:6]) + ") — a budget, a cost, an "
        "insurance share or a count is a current fact, not a mechanism: cite "
        "the fetched article that carries each one with a Source line, or "
        "explain the concept without the figure",
        metrics,
    )


# --- item_figures_sourced ---------------------------------------------------

_YEAR_RE = re.compile(r"^(?:19|20)\d\d$")


def _item_figures(text: str) -> List[str]:
    prose = _URL_RE.sub(" ", _prose(text))
    out: List[str] = []
    for m in _BODY_FIGURE_RE.finditer(prose):
        key = _figure_key(m.group(1), m.group(2))
        if _YEAR_RE.match(key) or _is_name_number(prose, m.start()):
            continue
        after = prose[m.end(): m.end() + 14].lstrip()
        if re.match(r"(?:st|nd|rd|th)?\s*(?:" + "|".join(m2.title() for m2 in _MONTHS) + r")\b", after):
            continue  # a day of the month
        if key not in out:
            out.append(key)
    return out


def item_unsourced_figures(digest: str, context: dict) -> Optional[List[str]]:
    """Digit-written figures in sourced items that no fetched article and no
    briefing text (``reference_text``: the standing facts, the field guide,
    the computed status) carries. None when nothing was read."""
    arts = list(context.get("articles") or [])
    texts = [_article_text(a) for a in arts]
    if not any(len(t.strip()) >= _SOURCE_TEXT_MIN for t in texts):
        return None
    carried = set()
    for t in texts + [str(context.get("reference_text") or "")]:
        carried.update(figures_in(t))
    missing: List[str] = []
    for _title, text, _urls in sourced_items(digest):
        for f in _item_figures(text):
            if not figure_matches(f, carried) and f not in missing:
                missing.append(f)
    return missing


def lint_item_figures_sourced(digest: str, context: Optional[dict] = None) -> Optional[LintFinding]:
    if not context:
        return None
    missing = item_unsourced_figures(digest, context)
    if missing is None:
        return None
    metrics = {"item_figures_unsourced": len(missing)}
    if not missing:
        return LintFinding("item_figures_sourced", "", metrics)
    return LintFinding(
        "item_figures_sourced",
        "these figures are in no fetched article and no briefing fact: "
        + ", ".join(missing[:8])
        + " — state a count, a distance or an amount only as the source "
        "gives it, or leave the number out",
        metrics,
    )


# ---------------------------------------------------------------------------
# Registry + runner
# ---------------------------------------------------------------------------

#: Lints that read the run's article list (``context``) as well as the digest.
# --- pick_stop_loss (Oct 24 2026) --------------------------------------------
# Modern Investing's published method says every pick states a stop-loss and
# the sim exits at it. Through Oct 24 the sim could read a stop on 9 of 41
# era picks: the digest wrote "Maximum acceptable loss 8 percent" (now
# parsed) or dropped the Risk Assessment line altogether (Ep210 shipped an
# AI Analysis block with only a Confidence line). A new pick the sim cannot
# attach a stop to is a structural defect and rides the regeneration.

_PICK_RE = re.compile(r"\*\*Today's Pick:\*\*\s*\[?([A-Z]{1,5}(?:[.-][A-Z]{1,4})?)\]?\s*[-—]")


def pick_without_stop(digest: str) -> Optional[str]:
    """The ticker of a new pick whose section states no parseable stop,
    else None (no pick, a no-trade day, or a stop the sim can read)."""
    m = _PICK_RE.search(digest or "")
    if not m:
        return None
    # The parser is the sim's own, so the lint and the enforcement agree.
    from shows.hooks.modern_investing import _extract_stop_loss
    if _extract_stop_loss(digest):
        return None
    return m.group(1)


def lint_pick_stop_loss(digest: str) -> Optional[LintFinding]:
    sym = pick_without_stop(digest)
    metrics = {"pick_without_stop": 0 if sym is None else 1}
    if sym is None:
        return LintFinding("pick_stop_loss", "", metrics)
    return LintFinding(
        "pick_stop_loss",
        f"the Practice Investment names {sym} and states no stop-loss the "
        f"record can enforce — the pick carries a **Stop-Loss:** line giving "
        f"a price or a percent below entry, derived from the invalidation, "
        f"and the Risk Assessment repeats it",
        metrics,
    )


CONTEXT_LINTS = frozenset({"board_venue_mix", "deep_dive_fetched_source", "hook_figure_sourced",
                           "hook_repeats_past_lead", "stop_told_as_retirement",
                           "preview_told_as_result", "item_figures_sourced"})

LINTS: Dict[str, Callable[..., Optional[LintFinding]]] = {
    "wyntk_hook_match": lint_wyntk_hook_match,
    "x_only_lead": lint_x_only_lead,
    "progress_watch_thin": lint_progress_watch_thin,
    "region_world_thin": lint_region_world_thin,
    "counterpoint_keyed_to_lead": lint_counterpoint_keyed_to_lead,
    "items_without_source": lint_items_without_source,
    "dc_items_unlabelled": lint_dc_items_unlabelled,
    "evidence_rung": lint_evidence_rung,
    "dose_terms": lint_dose_terms,
    "spotlight_card": lint_spotlight_card,
    "hook_supported": lint_hook_supported,
    "pick_stop_loss": lint_pick_stop_loss,
    "board_venue_mix": lint_board_venue_mix,
    "deep_dive_fetched_source": lint_deep_dive_fetched_source,
    "deep_dive_distinct": lint_deep_dive_distinct,
    "deep_dive_distinct_measure": lint_deep_dive_distinct_measure,
    "hook_figure_sourced": lint_hook_figure_sourced,
    "hook_repeats_past_lead": lint_hook_repeats_past_lead,
    "stop_told_as_retirement": lint_stop_told_as_retirement,
    "preview_told_as_result": lint_preview_told_as_result,
    "explainer_figures_sourced": lint_explainer_figures_sourced,
    "item_figures_sourced": lint_item_figures_sourced,
}


def run_digest_lints(digest: str, names: List[str],
                     context: Optional[dict] = None) -> Tuple[List[LintFinding], Dict[str, object]]:
    """Run the named lints. Returns ``(fired_findings, metrics)`` — metrics
    for every lint that had something to measure, findings only for those
    that fired (``note`` non-empty). An unknown name is ignored (the YAML
    validator reports it). ``context`` (``{"articles": [...]}``) reaches
    only the lints in ``CONTEXT_LINTS``."""
    fired: List[LintFinding] = []
    metrics: Dict[str, object] = {}
    for name in names or []:
        fn = LINTS.get(name)
        if fn is None:
            continue
        try:
            f = fn(digest, context) if name in CONTEXT_LINTS else fn(digest)
        except Exception:  # noqa: BLE001 — a lint can never cost an episode
            continue
        if f is None:
            continue
        metrics.update(f.metrics)
        if f.note:
            fired.append(f)
    return fired, metrics


def new_lint_names(before, after) -> List[str]:
    """Lints the retry digest fails that the original digest passed.

    Sep 30 2026 (Tesla Ep617): the one-shot structural regeneration can
    introduce a defect the first digest did not have — the retry wrote
    every item as "**Title** — Outlet" and dropped all 17 Source: lines
    while the post-retry lint was recorded as metrics only. run_show keeps
    the ORIGINAL digest when this list is non-empty.
    """
    before_names = {getattr(f, "lint", f) for f in (before or [])}
    return sorted({getattr(f, "lint", f) for f in (after or [])} - before_names)
