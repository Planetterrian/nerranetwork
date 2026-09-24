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
from typing import Callable, Dict, List, Optional, Tuple

from engine.script_audit import _salient

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
_X_HOST_RE = re.compile(r"^https?://(?:www\.|mobile\.)?(?:x\.com|twitter\.com)/", re.IGNORECASE)
_ITEM_HEAD_RE = re.compile(r"^\s*(?:\d+\.\s*)?\*\*.+\*\*|^\s*(?:\d+\.\s*)?[A-Z][^\n]{8,}?:\s+[^\n]{2,60}$")

#: Section titles whose FIRST item is the episode's lead story.
LEAD_SECTIONS = (
    "Lead", "Top Story", "Top News", "Top Stories", "The Week's Stories",
    "The Ten", "The Week in Peptides", "The Week in Longevity",
)


def sections(digest: str) -> List[Tuple[str, str]]:
    """``[(title, body), ...]`` for every ``##``/``###`` section, in order.
    The title is taken up to its first colon (``### Both Sides: X`` → ``Both
    Sides``)."""
    out: List[Tuple[str, str]] = []
    title = ""
    buf: List[str] = []
    for line in (digest or "").splitlines():
        m = _HEADER_RE.match(line)
        if m:
            if title or buf:
                out.append((title, "\n".join(buf).strip()))
            title = m.group(1).split(":")[0].strip().strip("*")
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


def items(body: str) -> List[str]:
    """Blank-line-separated blocks that open on an item head."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body or "") if b.strip()]
    out: List[str] = []
    for b in blocks:
        first = b.splitlines()[0]
        if _ITEM_HEAD_RE.match(first) or first.startswith("**"):
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
    """Titles of lead items whose every source URL is an X post."""
    bad: List[str] = []
    for title, body in sections(digest):
        if title not in LEAD_SECTIONS:
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
            "the lead item's only source is a post on X — a lead item is "
            "sourced to a named newsroom's own article (the post's linked "
            "article, or another supplied article on the same story); an X "
            "post may be a secondary source, never the only one",
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
_NUMBERED_ITEM_RE = re.compile(r"^\s*\d+\.\s*\*\*")
_HEADLINE_ITEM_RE = re.compile(r"^\s*\*\*[^*]{10,}\*\*\s*$")
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
    low = body.lower()
    return [lab for lab in SPOTLIGHT_CARD_LABELS if f"**{lab.lower()}" not in low]


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


# ---------------------------------------------------------------------------
# Registry + runner
# ---------------------------------------------------------------------------

LINTS: Dict[str, Callable[[str], Optional[LintFinding]]] = {
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
}


def run_digest_lints(digest: str, names: List[str]) -> Tuple[List[LintFinding], Dict[str, object]]:
    """Run the named lints. Returns ``(fired_findings, metrics)`` — metrics
    for every lint that had something to measure, findings only for those
    that fired (``note`` non-empty). An unknown name is ignored (the YAML
    validator reports it)."""
    fired: List[LintFinding] = []
    metrics: Dict[str, object] = {}
    for name in names or []:
        fn = LINTS.get(name)
        if fn is None:
            continue
        try:
            f = fn(digest)
        except Exception:  # noqa: BLE001 — a lint can never cost an episode
            continue
        if f is None:
            continue
        metrics.update(f.metrics)
        if f.note:
            fired.append(f)
    return fired, metrics
