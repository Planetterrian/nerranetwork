"""Source-integrity claim ledger (Aug 2026).

The pipeline used to treat provenance as formatting debris: the model was
handed real source material, wrote citation-shaped prose ("a 1962 paper in
*Nature* warned…"), and three downstream strippers removed every attribution
before publish — while nothing anywhere verified that an asserted fact traced
to anything. The result was true facts wearing false provenance (three
unrelated chapters in two published book volumes each citing "a 1962 paper in
*Nature*" for findings published elsewhere, or nowhere).

This module makes a claim's provenance DATA, not formatting:

* Generation emits two artifacts — the clean prose the pipeline already
  expects, plus a fenced ``claims`` JSON block (the ledger) that is extracted
  here and never reaches TTS / blog / RSS.
* :func:`run_source_integrity_gate` composes the checks that make fabrication
  fail loudly instead of shipping:

  1. every ledger entry's ``episode_span`` must appear in the final digest
     (entries describing text that was edited away are dropped, loudly);
  2. every ``source_url`` must resolve (HTTP 200, non-empty body);
  3. every ``supporting_quote`` must actually appear in the fetched source
     (normalised whitespace, fuzzy match >= 0.9) — the load-bearing check;
  4. every citation-shaped construction in the prose must be covered by a
     ledger entry (the lint — a citation shape with no ledger entry is
     exactly the fabrication signature).

* The ledger is saved as a sidecar next to the digest
  (``<digest_stem>_claims.json``) so show notes and the book compiler can
  render real citations from it.

Rollout: ``source_integrity.enabled`` turns the ledger + shadow telemetry on
(``_defaults.yaml`` network-wide); ``source_integrity.enforce`` makes the
gate BLOCKING (the narrative shows first — they are where fabrication was
demonstrated, and a blocked narrative episode costs a rerun, not a news day).
Per the model-upgrade playbook, enforcement widens per show, never in a
network-wide day-one flip.

The three script strippers in run_show stay: they now remove only genuine
leakage — the ledger carries provenance where nothing needs to strip it.
"""

from __future__ import annotations

import html as _html
import json
import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Citation-shaped constructions (the lint vocabulary)
# ---------------------------------------------------------------------------
# Every pattern below appears in the fabricated citations found in the
# published books. This set is deliberately NARROW: a match means "this
# sentence asserts checkable provenance", and in enforce mode an uncovered
# match blocks the episode — false positives here cost real episodes, so
# widen the vocabulary only with corpus evidence (measure first with
# scripts/measure_citation_exposure.py).

CITATION_SHAPE_PATTERNS: List[str] = [
    # ---- Original template set (Aug 22) — the dated-artifact shape.
    # These carry no capitalization anchors, so they compile
    # case-insensitively via the (?i) prefix. ----
    r"(?i)\ba \d{4} (?:study|paper|report|memo|survey|analysis|bulletin|note)\b",
    r"(?i)\b(?:researchers|scientists|analysts|officials) "
    r"(?:found|noted|estimated|documented)\b",
    r"(?i)\binternal (?:documents|memos|reports)\b",
    r"(?i)\baccording to (?:a|an|the) [a-z]",
    r"(?i)\bestimates (?:from|compiled by)\b",
    r"(?i)\bstudies (?:later )?(?:showed|estimated|found)\b",
    r"(?i)\btrade data show\b",
    r"(?i)\bmost accounts\b",
    # ---- WO-1 widening (Aug 23) — the original set caught 4 of 14
    # hand-verified fabrications. Each pattern below maps to a verified
    # miss category; the fixture in tests/test_citation_shapes.py pins
    # all 14 catches and the general-form guards. The distinction that
    # binds: unnamed PEOPLE ("contemporary observers warned") are the
    # sanctioned general form; non-existent DOCUMENTS, records,
    # institutions and datasets are the fabrication signature.
    #
    # The [A-Z] classes below are LOAD-BEARING named-entity anchors and
    # must stay case-sensitive — the first measurement pass compiled
    # everything IGNORECASE and precision collapsed ("data collected by
    # the rover's instruments", "the record cadence established in
    # 2025" both flagged). Sentence-initial words use [Xx] classes;
    # keyword alternations use scoped (?i:...) groups instead. ----
    # dated institutional action: "In 1962 the WHO issued guidance"
    r"\b(?:[Ii]n|[Bb]y)\s+\d{4},?\s+the\s+[A-Z][\w'&.\- ]{3,50}?\s+"
    r"(?i:issued|published|released|adopted|recommended|established|"
    r"introduced|required|banned|mandated|approved|suspended)\b",
    # invented regulatory history: "The FTC briefly required X in 1957"
    r"\b[Tt]he\s+[A-Z][\w'&.\- ]{3,50}?\s+(?i:briefly\s+|formally\s+|"
    r"first\s+|quietly\s+)?(?i:issued|published|adopted|recommended|"
    r"established|introduced|required|banned|mandated|approved|"
    r"suspended|authorized)\b[^.]{0,60}?\bin\s+\d{4}\b",
    # archival / data custody: "records are preserved by the X Museum"
    r"\b(?i:records|documents|archives|papers|files|data|figures|"
    r"statistics)\s+(?i:(?:are|were|is|now)\s+)?(?i:preserved|held|"
    r"housed|maintained|tracked|compiled|collected|published)\s+"
    r"(?i:by|at|in)\s+(?:the\s+)?[A-Z]",
    # institutional data custody: "waste now tracked by the Ellen
    # MacArthur Foundation" — the custodied noun varies too much to
    # enumerate, so anchor on the custody verb + named institution.
    r"\b(?i:tracked|compiled|catalogued|documented|"
    r"maintained|preserved)\s+by\s+the\s+[A-Z]",
    # named-expert attribution: "pharmacologist Sir Robert Robinson had
    # noted" — a titled, named person lending authority to a claim.
    r"\b(?i:physician|pharmacologist|chemist|biologist|economist|"
    r"engineer|scientist|professor|researcher|historian|epidemiologist|"
    r"statistician)\s+(?:Sir\s+|Dr\.?\s+)?[A-Z][a-z]+\s+[A-Z][a-z]+"
    r"\b[^.]{0,80}?\b(?i:noted|found|warned|observed|argued|reported|"
    r"showed|concluded|estimated)\b",
    # quoted document: "a 1974 internal memo ... observed that '..."
    r"(?i)\b(?:memo|memorandum|report|study|letter|document|paper|bulletin)"
    r"\b[^.]{0,90}?\b(?:observed|noted|stated|concluded|said|wrote|"
    r"argued)\s+that\s+[\"'‘“]",
    # attributed survey / data: "according to surveys by X"
    r"(?i)\baccording to\s+(?:surveys?|data|figures|records|analyses?|"
    r"estimates?|reports?|research)\s+(?:by|from|conducted by)\b",
    # invented empirical finding: "sampling in several cities detected"
    r"(?i)\b(?:sampling|testing|monitoring|surveys?|measurements?|audits?)"
    r"\s+(?:in|across|of|at)\s+[^.]{0,70}?\b(?:detected|found|showed|"
    r"revealed|recorded|documented)\b",
    # dated periodical: "a 1954 British textile journal noted"
    r"(?i)\ba\s+\d{4}\s+[\w\- ]{0,35}?(?:journal|magazine|newspaper|"
    r"publication|periodical|trade press|newsletter)\b",
    # invented archival record: "accounts from the period describe".
    # Deliberately excludes bare "contemporary observers warned" —
    # unnamed people are the sanctioned general form; non-existent
    # documents are not.
    r"(?i)\b(?:accounts?|records?|reports?|sources?)\s+from\s+the\s+"
    r"(?:period|time|era|day)\b",
    r"(?i)\bcontemporary\s+(?:accounts?|records?|reports?|sources?|"
    r"documentation)\s+(?:describe|record|show|indicate|note|suggest|"
    r"confirm)\b",
]

# Case handling lives INSIDE each pattern ((?i) prefix or scoped (?i:...)
# groups) — a global IGNORECASE here would nullify the [A-Z] named-entity
# anchors that keep the widened set precise.
_CITATION_SHAPE_RES = [re.compile(p) for p in CITATION_SHAPE_PATTERNS]

# Fenced ledger block the generation stage appends after the prose.
_CLAIMS_FENCE_RE = re.compile(
    r"```claims[ \t]*\n(?P<body>.*?)\n?```[ \t]*",
    re.DOTALL,
)
# Opening fence with no closing fence, running to the end of the text.
_UNCLOSED_TAIL_FENCE_RE = re.compile(
    r"```claims[ \t]*\n(?P<body>(?:(?!```).)*?)\s*\Z",
    re.DOTALL,
)

REQUIRED_CLAIM_KEYS = ("claim", "source_url", "supporting_quote")

# Fuzzy threshold for "the quote actually appears in the source" (§2.2 of
# the design doc). Normalised-whitespace match, not byte equality.
QUOTE_MATCH_THRESHOLD = 0.9

# Hard cap — a ledger is a list of checkable specifics, not a transcript.
MAX_CLAIMS_PER_EPISODE = 40


# ---------------------------------------------------------------------------
# Prompt constraint (injected by engine.generator when enabled)
# ---------------------------------------------------------------------------

def claims_prompt_appendix() -> str:
    """The generation-side constraint + ledger output spec.

    De-seeded by shape (network rule): no example sentence, no placeholder
    that reads as plausible content — every seeded template tic in this
    network's history came from a prompt supplying the literal text it
    wanted reproduced.
    """
    return (
        "SOURCE-INTEGRITY LEDGER (required):\n"
        "You may only assert a specific, externally checkable fact — a named "
        "or dated study, paper, report, memo or survey; a named person's or "
        "institution's statement; a precise statistic or measurement — if you "
        "can point to a real, reachable source for it: one of the source "
        "articles supplied above, or a stable public URL you are certain "
        "exists and actually supports the fact. Never invent a source, a "
        "venue, a year, or a document. If you cannot point to a real source "
        "for a specific claim, do not state the specific claim: state it in "
        "a general, unattributed form in your own words (no named venue, no "
        "year, no named study), or leave it out.\n"
        "\n"
        "After the complete episode body, append exactly one fenced code "
        "block whose opening fence reads ```claims and whose content is a "
        "JSON array. Add one array element for EACH externally checkable "
        "specific you asserted, as an object with exactly these keys:\n"
        '  "id": a short sequential identifier string\n'
        '  "claim": <the asserted fact, stated plainly in one sentence>\n'
        '  "episode_span": <a short verbatim excerpt of YOUR OWN episode '
        "text where the fact is asserted>\n"
        '  "source_url": <the full URL of the real source>\n'
        '  "source_title": <the title of that source>\n'
        '  "supporting_quote": <a verbatim sentence copied from that source '
        "that supports the claim>\n"
        '  "confidence": <one of high, medium, low>\n'
        "\n"
        "An empty array is a valid and normal ledger when the episode makes "
        "no externally checkable specific assertions. The fenced block is "
        "machine-read and removed before publication — it is never spoken "
        "and never shown to readers, so do not mention it in the episode "
        "body, and do not place any prose after it."
    )


# ---------------------------------------------------------------------------
# Extraction + process-level stash
# ---------------------------------------------------------------------------

def extract_claims_block(text: str) -> Tuple[str, Optional[List[dict]]]:
    """Split generated output into (clean_text, claims).

    Returns ``(text, None)`` when no fenced ``claims`` block is present, and
    ``(clean_text, [])`` for a present-but-empty ledger. A block that fails
    to parse as a JSON array is treated as absent (logged) — malformed
    scaffolding must never reach a published surface, so the block is still
    stripped.
    """
    match = None
    for match in _CLAIMS_FENCE_RE.finditer(text):
        pass  # keep the LAST block — the ledger is defined to be at the tail
    if match is None:
        # An UNCLOSED trailing fence (Tesla Ep585, 2026-08-27: the digest
        # ended "```claims\n[]" with no closing fence) is still the
        # ledger — it reached summaries_tesla.json and rendered on the
        # blog as a <pre>[]</pre> block. Accept it when nothing but
        # whitespace follows the body (Sep 4 2026 flagship pass).
        match = _UNCLOSED_TAIL_FENCE_RE.search(text)
    if match is None:
        return text, None

    cleaned = (text[: match.start()] + text[match.end():]).rstrip() + "\n"
    body = match.group("body").strip()
    if not body:
        return cleaned, []
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Claims block present but not valid JSON (%s) — stripping it "
            "and treating the ledger as missing", exc,
        )
        return cleaned, None
    if not isinstance(parsed, list):
        logger.warning(
            "Claims block parsed to %s, expected a JSON array — treating "
            "the ledger as missing", type(parsed).__name__,
        )
        return cleaned, None
    claims = [c for c in parsed if isinstance(c, dict)]
    if len(claims) > MAX_CLAIMS_PER_EPISODE:
        logger.warning(
            "Claims ledger has %d entries — keeping the first %d",
            len(claims), MAX_CLAIMS_PER_EPISODE,
        )
        claims = claims[:MAX_CLAIMS_PER_EPISODE]
    return cleaned, claims


def strip_claims_block_for_validation(text: str) -> str:
    """Remove the fenced ledger before repetition/refusal validation.

    The ledger is repetitive by construction (the same JSON keys on every
    entry); letting the digest validators see it would trip the
    repeated-phrase guards and burn retry spend on well-formed output.
    """
    cleaned, _ = extract_claims_block(text)
    return cleaned


# One episode runs per process (run_show is invoked per show per day), and
# generate_digest may be called several times per episode (refusal retries,
# slow-news fallback, structural retry). Replace-on-stash keeps the ledger
# belonging to the LAST generated digest — the same accumulate-then-drain
# pattern digests/xai_grok.py uses for search-tool usage.
_STASHED_CLAIMS: Optional[List[dict]] = None


def extract_and_stash(text: str) -> str:
    """Extract the ledger from generated text, stash it, return clean text."""
    global _STASHED_CLAIMS
    cleaned, claims = extract_claims_block(text)
    _STASHED_CLAIMS = claims
    if claims is not None:
        logger.info("Source-integrity ledger extracted: %d claim(s)", len(claims))
    return cleaned


def drain_stashed_claims() -> Optional[List[dict]]:
    """Return and clear the ledger stashed by the last generation call."""
    global _STASHED_CLAIMS
    claims, _STASHED_CLAIMS = _STASHED_CLAIMS, None
    return claims


# ---------------------------------------------------------------------------
# Fuzzy text matching
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase + collapse all whitespace + strip markdown emphasis/quotes."""
    text = re.sub(r"[*_`]+", "", text)
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def fuzzy_contains(needle: str, haystack: str,
                   threshold: float = QUOTE_MATCH_THRESHOLD) -> bool:
    """True when *needle* appears in *haystack* at >= *threshold* similarity.

    Normalised whitespace on both sides; exact substring short-circuits.
    Otherwise a sliding word-window of the needle's length is compared with
    :class:`difflib.SequenceMatcher` — cheap string matching, no model calls.
    """
    needle_n = _normalize(needle)
    haystack_n = _normalize(haystack)
    if not needle_n or not haystack_n:
        return False
    if needle_n in haystack_n:
        return True

    needle_words = needle_n.split()
    hay_words = haystack_n.split()
    win = len(needle_words)
    if win == 0 or len(hay_words) < max(3, int(win * threshold)):
        return False
    step = max(1, win // 2)
    for start in range(0, max(1, len(hay_words) - win + step), step):
        window = " ".join(hay_words[start:start + win + 3])
        # Score = how much of the NEEDLE aligns (in order) inside the
        # window; extra window context is free, so a quote survives the
        # source inserting a word. Matching blocks are ordered, so
        # reshuffled words score poorly.
        sm = SequenceMatcher(None, needle_n, window)
        matched = sum(b.size for b in sm.get_matching_blocks())
        if matched / len(needle_n) >= threshold:
            return True
    return False


_SALIENT_TOKEN_RE = re.compile(r"\b[A-Z][A-Za-z]{4,}\b|\b\d{4}\b")


def _salient_tokens(text: str) -> set:
    """Capitalised words (>=5 chars) + 4-digit years — the checkable anchors."""
    return {t.lower() for t in _SALIENT_TOKEN_RE.findall(text or "")}


# ---------------------------------------------------------------------------
# Ledger shape + anchoring
# ---------------------------------------------------------------------------

def validate_ledger_shape(claims: List[dict]) -> Tuple[List[dict], List[str]]:
    """Keep well-formed entries; report what was dropped and why."""
    valid: List[dict] = []
    errors: List[str] = []
    for i, claim in enumerate(claims):
        cid = str(claim.get("id") or f"c{i + 1}")
        missing = [k for k in REQUIRED_CLAIM_KEYS
                   if not str(claim.get(k) or "").strip()]
        if missing:
            errors.append(f"{cid}: missing {', '.join(missing)}")
            continue
        url = str(claim["source_url"]).strip()
        if not re.match(r"^https?://", url):
            errors.append(f"{cid}: source_url is not an http(s) URL: {url!r}")
            continue
        entry = dict(claim)
        entry["id"] = cid
        # The design doc calls the anchor ``script_span``; the pipeline
        # anchors ledgers to the digest (the canonical artifact books,
        # blog and RSS derive from), so ``episode_span`` is canonical and
        # the doc's name is accepted as an alias.
        if not str(entry.get("episode_span") or "").strip():
            entry["episode_span"] = str(entry.get("script_span") or "").strip()
        valid.append(entry)
    return valid, errors


def anchor_claims(claims: List[dict],
                  episode_text: str) -> Tuple[List[dict], List[dict]]:
    """Split claims into (anchored, dropped) by span presence in the text.

    A claim whose ``episode_span`` no longer appears in the final text
    describes prose that was edited away (dedup passes, retry selection) —
    it must not be published as a citation for text that doesn't exist. An
    entry with no span at all anchors on salient-token overlap between the
    claim text and the episode.
    """
    anchored: List[dict] = []
    dropped: List[dict] = []
    for claim in claims:
        span = str(claim.get("episode_span") or "").strip()
        if span and fuzzy_contains(span, episode_text, threshold=0.8):
            anchored.append(claim)
            continue
        if not span:
            overlap = _salient_tokens(claim.get("claim", "")) & \
                _salient_tokens(episode_text)
            if len(overlap) >= 2:
                anchored.append(claim)
                continue
        dropped.append(claim)
    return anchored, dropped


# ---------------------------------------------------------------------------
# Source verification (URL resolves; quote appears in the source)
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<script\b.*?</script>|<style\b.*?</style>|<[^>]+>",
                     re.DOTALL | re.IGNORECASE)


def _html_to_text(body: str) -> str:
    return _html.unescape(_TAG_RE.sub(" ", body))


def default_fetch(url: str) -> Tuple[int, str]:
    """Fetch *url*, returning ``(status_code, text_body)``.

    Non-text content types return an empty body (a quote cannot be matched
    against bytes, and per the failure policy an unmatchable quote fails).
    Raises on transport errors — callers decide how a dead source counts.
    """
    import requests

    resp = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0 (compatible; NerraSourceCheck/1.0)"},
        allow_redirects=True,
    )
    ctype = (resp.headers.get("content-type") or "").lower()
    if "html" in ctype or ctype.startswith("text/") or "xml" in ctype:
        return resp.status_code, resp.text
    return resp.status_code, ""


#: HTTP statuses that mean "this source could not be READ from our
#: infrastructure", not "this source does not support the claim". A 403
#: from a bot-blocking government site (officialgazette.gov.ph 403'd six
#: of eight claims on UC Ep99, 2026-08-24, and took the show down for two
#: days) says nothing about the citation's truth — unlike a 404 (the
#: source does not exist: the fabrication signature) or a 200 whose body
#: lacks the quote. Unreachable claims still FAIL the gate — the contract
#: stays "nothing unverified ships" — but they are labelled so the repair
#: pass can ask for a *fetchable* alternative source instead of treating
#: the model as a fabricator.
_UNREACHABLE_STATUSES = frozenset({401, 403, 407, 408, 425, 429,
                                   500, 502, 503, 504, 522, 524})


def _is_unreachable(status: Optional[int]) -> bool:
    return status is None or status in _UNREACHABLE_STATUSES


def verify_claim_sources(
    claims: List[dict],
    fetch: Optional[Callable[[str], Tuple[int, str]]] = None,
) -> List[dict]:
    """Run the §2.2 source checks; return one result dict per claim.

    Each result: ``{"id", "url", "resolved", "quote_found", "passed",
    "unreachable", "reason"}``. URLs are fetched once each (deduped) with
    one retry on transport error. No model calls — HTTP + string matching
    only. ``unreachable`` marks fetch-blocked sources (403/429/5xx/
    transport) — still a failure, but distinct from the fabrication
    signature, and repairable with an alternative source.
    """
    if fetch is None:
        fetch = default_fetch

    cache: Dict[str, Tuple[Optional[int], str, str]] = {}

    def _fetch_cached(url: str) -> Tuple[Optional[int], str, str]:
        if url not in cache:
            last_exc = ""
            for _attempt in range(2):
                try:
                    status, body = fetch(url)
                    cache[url] = (status, body, "")
                    break
                except Exception as exc:  # noqa: BLE001 — transport failure
                    last_exc = str(exc)
            else:
                cache[url] = (None, "", last_exc)
        return cache[url]

    results: List[dict] = []
    for claim in claims:
        url = str(claim.get("source_url") or "").strip()
        quote = str(claim.get("supporting_quote") or "").strip()
        status, body, err = _fetch_cached(url)
        resolved = status is not None and 200 <= status < 300 and bool(body.strip())
        quote_found = False
        if resolved and quote:
            source_text = _html_to_text(body)
            quote_found = fuzzy_contains(quote, source_text)
        if status is None:
            reason = f"fetch failed: {err}"
        elif not resolved:
            reason = (f"HTTP {status}" if status and not (200 <= status < 300)
                      else "empty or non-text body")
        elif not quote:
            reason = "no supporting_quote"
        elif not quote_found:
            reason = "supporting_quote not found in source"
        else:
            reason = ""
        results.append({
            "id": claim.get("id", ""),
            "url": url,
            "resolved": resolved,
            "quote_found": quote_found,
            "passed": resolved and quote_found,
            "unreachable": not resolved and _is_unreachable(status),
            "reason": reason,
        })
    return results


# ---------------------------------------------------------------------------
# Lint: citation-shaped prose must be covered by the ledger
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def find_citation_shapes(text: str) -> List[dict]:
    """All citation-shaped constructions in *text*, with their sentences."""
    findings: List[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for sentence in _SENTENCE_SPLIT_RE.split(line):
            for pat in _CITATION_SHAPE_RES:
                m = pat.search(sentence)
                if m:
                    findings.append({
                        "pattern": pat.pattern,
                        "match": m.group(0),
                        "sentence": sentence.strip(),
                    })
    return findings


def _sentence_covered(sentence: str, claim: dict) -> bool:
    span = str(claim.get("episode_span") or "").strip()
    if span and (fuzzy_contains(span, sentence, threshold=0.8)
                 or fuzzy_contains(sentence, span, threshold=0.8)):
        return True
    claim_text = " ".join(
        str(claim.get(k) or "") for k in ("claim", "episode_span")
    )
    overlap = _salient_tokens(sentence) & _salient_tokens(claim_text)
    return len(overlap) >= 2


def lint_uncovered_shapes(text: str, claims: List[dict]) -> List[dict]:
    """Citation-shaped sentences with no covering ledger entry."""
    uncovered: List[dict] = []
    for finding in find_citation_shapes(text):
        if not any(_sentence_covered(finding["sentence"], c) for c in claims):
            uncovered.append(finding)
    return uncovered


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    passed: bool = True
    ledger_present: bool = False
    claims_total: int = 0
    claims_anchored: int = 0
    claims_verified: int = 0
    shape_errors: List[str] = field(default_factory=list)
    dropped_claims: List[dict] = field(default_factory=list)
    failed_verifications: List[dict] = field(default_factory=list)
    uncovered_shapes: List[dict] = field(default_factory=list)
    verified_claims: List[dict] = field(default_factory=list)

    def summary(self) -> str:
        unreachable = sum(
            1 for v in self.failed_verifications if v.get("unreachable"))
        return (
            f"ledger={'yes' if self.ledger_present else 'MISSING'} "
            f"claims={self.claims_total} anchored={self.claims_anchored} "
            f"verified={self.claims_verified} "
            f"failed_verifications={len(self.failed_verifications)} "
            f"(unreachable_sources={unreachable}) "
            f"uncovered_citation_shapes={len(self.uncovered_shapes)}"
        )

    def to_report(self) -> dict:
        return {
            "passed": self.passed,
            "ledger_present": self.ledger_present,
            "claims_total": self.claims_total,
            "claims_anchored": self.claims_anchored,
            "claims_verified": self.claims_verified,
            "shape_errors": self.shape_errors,
            "dropped_claims": self.dropped_claims,
            "failed_verifications": self.failed_verifications,
            "uncovered_shapes": self.uncovered_shapes,
        }


def run_source_integrity_gate(
    episode_text: str,
    claims: Optional[List[dict]],
    fetch: Optional[Callable[[str], Tuple[int, str]]] = None,
    verify_sources: bool = True,
) -> GateResult:
    """Compose every check. ``passed`` is the blocking verdict.

    Failure policy (design doc §2.2): a claim that fails verification, or a
    citation-shaped construction with no covering verified claim, FAILS the
    gate. A soft failure here would reproduce exactly the
    silent-degradation class that produced fabricated provenance, so the
    caller in enforce mode must block the episode, not warn.

    A missing ledger is not by itself a failure: prose written entirely in
    the general form needs no ledger, and the lint decides — any
    citation-shaped sentence in ledgerless prose is uncovered by
    definition and fails.
    """
    result = GateResult()
    result.ledger_present = claims is not None
    raw_claims = claims or []
    result.claims_total = len(raw_claims)

    valid, shape_errors = validate_ledger_shape(raw_claims)
    result.shape_errors = shape_errors

    anchored, dropped = anchor_claims(valid, episode_text)
    result.claims_anchored = len(anchored)
    result.dropped_claims = [
        {"id": c.get("id", ""), "claim": c.get("claim", ""),
         "reason": "episode_span not found in final episode text"}
        for c in dropped
    ]

    if verify_sources and anchored:
        verifications = verify_claim_sources(anchored, fetch=fetch)
        by_id = {v["id"]: v for v in verifications}
        result.verified_claims = [
            c for c in anchored if by_id.get(c.get("id", ""), {}).get("passed")
        ]
        result.failed_verifications = [v for v in verifications if not v["passed"]]
    else:
        result.verified_claims = list(anchored) if not verify_sources else []
        result.failed_verifications = []
    result.claims_verified = len(result.verified_claims)

    # The lint covers shapes with VERIFIED claims only — an entry that
    # failed verification is precisely the fabrication signature and must
    # not launder the sentence it decorates.
    result.uncovered_shapes = lint_uncovered_shapes(
        episode_text, result.verified_claims,
    )

    # Malformed entries also fail: the model asserted it had a source but
    # could not name one — that is a claim, not a formatting problem.
    result.passed = not (
        result.failed_verifications
        or result.uncovered_shapes
        or result.shape_errors
    )
    return result


# ---------------------------------------------------------------------------
# Claim repair — one bounded chance to re-source failed claims
# ---------------------------------------------------------------------------
# Discovered 2026-08-25 (UC Ep99, two lost days): the gate blocked because
# the topic's authoritative sources 403 GitHub's runner IPs and long
# statute pages defeat the fuzzy quote match — the FACTS were never
# disproven, the citations could not be READ. Repair asks the model, once,
# to re-source ONLY the failed claims (same claim text, a different
# fetchable source + verbatim quote), then re-verifies MECHANICALLY. The
# gate's contract is untouched: nothing ships unless every claim traces to
# a fetched, quote-matched source — repair just stops a bot-blocked
# government site from reading as fabrication.
#
# Sep 5 2026: the dominant enforce-mode block was never a failed
# verification. Every UC/FPD ledger since the counters exist was EMPTY
# (the appendix calls an empty array normal), so the gate's real trigger
# on the narrative shows was the citation-shape lint alone — and repair
# keyed on failed_verifications, so it never fired for it (UC 2026-09-05:
# claims=0, two uncovered shapes, blocked twice on one topic). Repair now
# also asks for a source for each UNCOVERED sentence, with the anchor
# pinned to the sentence itself; the full mechanical gate re-runs, so an
# unsourced sentence still blocks exactly as before.

REPAIR_MAX_CLAIMS = 10


def _uncovered_repair_items(uncovered: List[dict]) -> List[dict]:
    """Synthetic repair targets for citation-shaped sentences no VERIFIED
    ledger entry covers (Sep 5 2026). The sentence IS the anchor — the
    model may only supply the sourcing for it, never rewrite it."""
    items: List[dict] = []
    seen: set = set()
    for finding in uncovered:
        sentence = str(finding.get("sentence") or "").strip()
        if not sentence or sentence in seen:
            continue
        seen.add(sentence)
        items.append({
            "id": f"u{len(items) + 1}",
            "sentence": sentence,
            "match": str(finding.get("match") or ""),
        })
        if len(items) >= REPAIR_MAX_CLAIMS:
            break
    return items


def build_repair_prompt(episode_text: str, failed: List[dict],
                        claims: List[dict],
                        uncovered_items: Optional[List[dict]] = None) -> str:
    """Prompt for the one-shot repair call. *failed* are verification
    results; *claims* the original ledger entries (for claim text);
    *uncovered_items* (from ``_uncovered_repair_items``) are
    citation-shaped sentences with no covering verified entry."""
    by_id = {str(c.get("id", "")): c for c in claims}
    lines = []
    for v in failed[:REPAIR_MAX_CLAIMS]:
        cid = str(v.get("id", ""))
        claim = by_id.get(cid, {})
        why = ("the source could not be fetched from our verification "
               "infrastructure (it may block automated readers)"
               if v.get("unreachable")
               else f"verification failed: {v.get('reason', 'unknown')}")
        lines.append(
            f"- id: {cid}\n"
            f"  claim: {claim.get('claim', '')}\n"
            f"  episode_span: {claim.get('episode_span', '')}\n"
            f"  original_source: {v.get('url', '')}\n"
            f"  problem: {why}"
        )
    sections = []
    if lines:
        sections.append(
            "Some claims in an episode's source ledger failed automated "
            "verification. For EACH claim below, provide a replacement ledger "
            "entry with a DIFFERENT source_url that (a) directly supports the "
            "claim, (b) is publicly fetchable without login or bot-blocking "
            "(prefer major encyclopedias, news organizations, .edu pages, "
            "archived copies), and (c) a supporting_quote of 5-25 words copied "
            "VERBATIM from that source's text. Keep the claim and episode_span "
            "EXACTLY as given — only the sourcing changes. If you cannot find "
            "a genuine source for a claim, omit it (an omitted claim blocks "
            "publication — never invent a source).\n\n"
            "Failed claims:\n" + "\n".join(lines)
        )
    unc_lines = []
    for item in uncovered_items or []:
        unc_lines.append(
            f"- id: {item['id']}\n"
            f"  sentence: {item['sentence']}"
        )
    if unc_lines:
        sections.append(
            "The following sentences in the episode assert checkable "
            "provenance (a study, a dated institutional action, a statistic, "
            "an attributed finding) but NO ledger entry covers them. For EACH "
            "sentence, provide a ledger entry: episode_span EXACTLY the "
            "sentence as given, claim = the specific fact it asserts in one "
            "plain sentence, source_url = a real, publicly fetchable page "
            "that directly supports that fact (prefer major encyclopedias, "
            "news organizations, .edu or .gov pages, archived copies), and a "
            "supporting_quote of 5-25 words copied VERBATIM from that page. "
            "If you cannot find a genuine source for a sentence, omit it (an "
            "omitted sentence blocks publication — never invent a source).\n\n"
            "Unsourced sentences:\n" + "\n".join(unc_lines)
        )
    return (
        "\n\n".join(sections) + "\n\n"
        "Episode text (for context):\n---\n" + episode_text[:6000] + "\n---\n\n"
        "Reply with ONLY a JSON array of objects with keys: id, claim, "
        "episode_span, source_url, supporting_quote."
    )


def parse_repair_response(text: str) -> List[dict]:
    """Extract the repair call's JSON array; [] on any shape problem."""
    if not text:
        return []
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [e for e in data if isinstance(e, dict)]


def attempt_claim_repair(
    episode_text: str,
    gate: GateResult,
    claims: List[dict],
    generate: Callable[[str], str],
    fetch: Optional[Callable[[str], Tuple[int, str]]] = None,
) -> Tuple[GateResult, List[dict]]:
    """One bounded repair pass. Returns ``(new_gate_result, new_claims)``.

    *generate* is the injected LLM call (prompt -> text). The repaired
    ledger replaces failed entries with the model's re-sourced versions
    (id-matched; a claim the model omitted stays failed), then the FULL
    gate re-runs — anchoring, mechanical verification, and the lint all
    apply to the repaired ledger exactly as to the original. Any error
    returns the original result unchanged (repair can only help, never
    mask)."""
    # A sentence whose ledger entry FAILED verification is already a repair
    # target through that entry (the lint lists it as uncovered because
    # only verified entries cover) — don't ask for it twice under a
    # synthetic id, or the two answers race for one anchor.
    failed_ids = {str(v.get("id", "")) for v in gate.failed_verifications}
    failed_claims = [c for c in claims if str(c.get("id", "")) in failed_ids]
    uncovered_items = _uncovered_repair_items([
        u for u in gate.uncovered_shapes
        if not any(_sentence_covered(str(u.get("sentence") or ""), c)
                   for c in failed_claims)
    ])
    if gate.passed or not (gate.failed_verifications or uncovered_items):
        return gate, claims
    try:
        prompt = build_repair_prompt(
            episode_text, gate.failed_verifications, claims, uncovered_items)
        replacements = parse_repair_response(generate(prompt))
    except Exception as exc:  # noqa: BLE001 — repair is best-effort
        logger.warning("claim repair call failed: %s", exc)
        return gate, claims
    if not replacements:
        logger.info("claim repair produced no usable replacements")
        return gate, claims

    by_id = {str(r.get("id", "")): r for r in replacements
             if str(r.get("id", "")) in failed_ids}
    # Entries the model supplied for uncovered sentences (Sep 5 2026):
    # the anchor is PINNED to the exact sentence the lint flagged, so the
    # only thing the model contributed is the sourcing — which the full
    # gate below verifies mechanically before the sentence counts as
    # covered. Ids are synthetic (u1..uN) and never shadow a real entry.
    existing_ids = {str(c.get("id", "")) for c in claims}
    uncovered_by_id = {it["id"]: it for it in uncovered_items
                       if it["id"] not in existing_ids}
    new_entries: List[dict] = []
    for r in replacements:
        rid = str(r.get("id", ""))
        item = uncovered_by_id.pop(rid, None)
        if item is None:
            continue
        entry = dict(r)
        entry["id"] = rid
        entry["episode_span"] = item["sentence"]
        if not str(entry.get("claim") or "").strip():
            entry["claim"] = item["sentence"]
        entry.setdefault("confidence", "medium")
        new_entries.append(entry)
    if not by_id and not new_entries:
        return gate, claims
    repaired: List[dict] = []
    for claim in claims:
        cid = str(claim.get("id", ""))
        if cid in by_id:
            replacement = dict(by_id[cid])
            # The claim text and anchor are NOT the model's to rewrite in
            # a repair — only the sourcing. Keep the originals.
            replacement["claim"] = claim.get("claim", "")
            replacement["episode_span"] = claim.get("episode_span", "")
            replacement["id"] = cid
            repaired.append(replacement)
        else:
            repaired.append(claim)
    repaired.extend(new_entries)
    new_gate = run_source_integrity_gate(episode_text, repaired, fetch=fetch)
    logger.info(
        "claim repair: %d replacement(s) tried — gate now %s (%s)",
        len(by_id), "PASSED" if new_gate.passed else "still failing",
        new_gate.summary(),
    )
    return new_gate, repaired


# ---------------------------------------------------------------------------
# Sidecar persistence (the committed, public half of the ledger)
# ---------------------------------------------------------------------------

def claims_sidecar_path(digest_md_path: Path) -> Path:
    """``Show_Ep123_20260822.md`` → ``Show_Ep123_20260822_claims.json``."""
    return digest_md_path.with_name(digest_md_path.stem + "_claims.json")


def save_ledger(digest_md_path: Path, gate: GateResult) -> Path:
    """Persist the verified ledger + gate outcome next to the digest.

    Committed by the same ``git add -A digests/`` the episode output rides,
    so show notes and the book compiler can render real citations from it.
    """
    path = claims_sidecar_path(Path(digest_md_path))
    payload = {
        "version": 1,
        "gate": gate.to_report(),
        "claims": gate.verified_claims,
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_ledger(digest_md_path: Path) -> List[dict]:
    """Verified claims for a digest, or ``[]`` when no sidecar exists."""
    path = claims_sidecar_path(Path(digest_md_path))
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Unreadable claims sidecar %s: %s", path, exc)
        return []
    claims = payload.get("claims")
    return claims if isinstance(claims, list) else []
