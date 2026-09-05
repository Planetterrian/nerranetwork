"""Deterministic density audit of a finished podcast script.

Sep 5 2026 network delivery review. Four transcript audits (SpaceX,
Tesla, Models & Agents, and a four-show sample) agreed on the shape of
the "narrative-driven, redundant" complaint, and none of it was visible
to the existing tooling because `review_snapshot`'s repeated-phrase
detector only sees STRINGS that recur across episodes:

* the script stage was writing the digest out almost verbatim — 62-78%
  of a script's 8-grams appeared word for word in the digest on the
  worst days — so every duplicate in the digest became a duplicate in
  the audio;
* the same number was spoken 3-6 times in one episode (Memphis outage
  ×6 in SpaceX Ep090, HARNESSEVO ×4 in M&A Ep163, 1M miles ×3 in Tesla
  Ep594);
* 7-15% of sentences carried no fact at all — "Observers are watching",
  "Builders should", "The move underscores", "No specific figures were
  provided", analogy bridges between unrelated stories.

This module measures those per episode. It is a READ-ONLY instrument:
nothing here edits the script. `run_show` records the numbers as
metrics and prints a `::warning::` above thresholds; `review_snapshot`
tabulates them for the last N committed episodes so the next review
scores the prompt changes against a number instead of an impression.

Loops that operate on text fail loudly; loops that operate on numbers
fail silently — so the thresholds below are documented against the
baseline they were read from, and a review must re-read them, never
trust them.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from engine.utils import calculate_similarity

# ---------------------------------------------------------------------------
# Sentence handling
# ---------------------------------------------------------------------------

_SPEAKER_PREFIX_RE = re.compile(r"^\s*[A-Z][A-Za-z]{1,20}:\s*", re.MULTILINE)
_SPEECH_TAG_RE = re.compile(r"\[(?:breath|pause|long-pause)\]|</?(?:emphasis|fast|slow|whisper|soft)>")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'“‘(\[])")
_NGRAM = 8


def split_sentences(text: str) -> List[str]:
    """Spoken sentences of a script, speaker labels and speech tags removed."""
    if not text:
        return []
    cleaned = _SPEECH_TAG_RE.sub(" ", _SPEAKER_PREFIX_RE.sub("", text))
    out: List[str] = []
    for para in cleaned.split("\n"):
        para = " ".join(para.split())
        if not para:
            continue
        for sent in _SENTENCE_SPLIT_RE.split(para):
            sent = sent.strip()
            if len(sent.split()) >= 3:
                out.append(sent)
    return out


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9][a-z0-9'’-]*", text.lower())


def _ngrams(words: List[str], n: int = _NGRAM) -> Set[Tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(max(0, len(words) - n + 1))}


# ---------------------------------------------------------------------------
# Repeated facts: numeric phrases (scripts spell numbers as words)
# ---------------------------------------------------------------------------

_NUMBER_WORDS = (
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty "
    "thirty forty fifty sixty seventy eighty ninety hundred thousand million "
    "billion trillion half quarter point percent per cent dollars dollar cents "
    "kilometres kilometers miles kilowatt megawatt gigawatt tonnes tons hours "
    "minutes seconds days weeks months years"
).split()
_NUMBER_WORD_RE = re.compile(
    r"(?:\b(?:" + "|".join(_NUMBER_WORDS) + r")\b[\s,-]*){2,}|\b\d[\d,.]*(?:\s*(?:%|percent|million|billion))?",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"^(?:twenty twenty(?: |-)?(?:one|two|three|four|five|six|seven|eight|nine)?|two thousand[a-z ]*|(?:19|20)\d\d)$")


def numeric_phrases(sentence: str) -> List[str]:
    """Normalized numeric phrases ('two point four seconds', '1.48 million')."""
    out = []
    for m in _NUMBER_WORD_RE.finditer(sentence):
        phrase = " ".join(m.group(0).lower().replace("-", " ").replace(",", " ").split())
        # Single generic number words ("one thing", "two of them") are not facts.
        toks = phrase.split()
        if len(toks) < 2 and not re.search(r"\d", phrase):
            continue
        if _YEAR_RE.match(phrase):
            continue
        if all(t in ("one", "two", "three", "point", "half", "per", "cent") for t in toks):
            continue
        out.append(phrase)
    return out


# ---------------------------------------------------------------------------
# Filler shapes — sentences that announce, frame, or apologise for the
# absence of a fact instead of stating one. Shapes, not strings: each
# pattern is a skeleton the audits found under different words.
# ---------------------------------------------------------------------------

FILLER_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("advisory", r"^(?:builders|teams|developers|listeners|investors|readers|owners) (?:should|can|may want to|would do well to|will want to)\b"),
    ("spectator", r"^(?:observers|analysts|builders|teams|developers|researchers|investors|listeners|watchers|markets)\b[^.]{0,40}\b(?:are|will|should|can|continue|need|remain)\b"),
    ("underscores", r"\b(?:underscores|underlines|highlights|illustrates|reflects|demonstrates|signals|marks|reinforces)\s+(?:how|why|that|the|a|an|its|tesla|spacex)\b"),
    ("meaning", r"\bwhat (?:this|that|it) (?:all )?means\b|\bthis matters because\b|\bwhy (?:this|it) matters\b"),
    ("big-picture", r"\bthe bigger picture\b|\bstepping back\b|\btaking a step back\b|\bzoom(?:ing)? out\b"),
    ("takeaway", r"\bthe (?:practical |key |real |big )?takeaway\b|\bthe bottom line\b"),
    ("watch-for", r"\bworth (?:watching|noting|keeping an eye on)\b|\bwatch for\b|\bwhat happens next\b|\bwhat to watch\b|\bkeep an eye on\b"),
    ("nothing-to-say", r"\bno (?:specific|exact|further|additional|detailed|official|precise)\b[^.]{0,60}\b(?:were|was|are|is|has been|have been)\s+(?:provided|released|stated|included|announced|shared|disclosed|given|reported|confirmed)\b|\b(?:details|timelines?|figures?|specifics)\s+(?:were|was|remain|are|have)\s+(?:not|un)(?:released|available|disclosed|announced|confirmed|specified)\b|\bhas not (?:yet )?(?:been )?(?:announced|disclosed|confirmed|released)\b"),
    ("announcing", r"^(?:now|next|meanwhile|turning|shifting|moving|switching)\b[^.]{0,30}\b(?:to|on|over|our attention|gears)\b|\blet'?s (?:turn|shift|move) (?:now )?to\b|\bfrom [^.]{3,60}\bwe (?:turn|move|shift) to\b|\bleads naturally to\b|\bpairs well with\b|\bon a completely different note\b"),
    ("frame", r"\bthe (?:report|piece|post|analysis|article|story|thread) (?:frames|positions|highlights|argues|notes|suggests|points out)\b"),
)
_FILLER_COMPILED = [(name, re.compile(pat, re.IGNORECASE)) for name, pat in FILLER_PATTERNS]

DUPLICATE_SENTENCE_THRESHOLD = 0.8
HOOK_RESTATE_THRESHOLD = 0.7

# Warning thresholds: read from the Sep 2026 baseline (flagship scripts
# 21-78% digest overlap, 7-15% filler, 2-11 repeated facts/episode). The
# aim of the prompt pass shipped with this module is to sit well under
# them; a review re-reads the baseline before moving them.
WARN_DIGEST_OVERLAP_PCT = 50.0
WARN_FILLER_PCT = 12.0
WARN_DUPLICATE_SENTENCES = 3
WARN_REPEATED_FACTS = 6


@dataclass
class ScriptAudit:
    sentences: int
    words: int
    digest_overlap_pct: Optional[float]
    duplicate_sentences: int
    repeated_facts: int
    filler_sentences: int
    filler_pct: float
    hook_restated: int
    filler_by_shape: Dict[str, int]
    repeated_fact_examples: List[str]

    def to_metrics(self) -> Dict[str, object]:
        m: Dict[str, object] = {
            "script_sentences": self.sentences,
            "script_words": self.words,
            "script_duplicate_sentences": self.duplicate_sentences,
            "script_repeated_facts": self.repeated_facts,
            "script_filler_sentences": self.filler_sentences,
            "script_filler_pct": round(self.filler_pct, 1),
            "script_hook_restated": self.hook_restated,
        }
        if self.digest_overlap_pct is not None:
            m["script_digest_overlap_pct"] = round(self.digest_overlap_pct, 1)
        return m

    def warnings(self) -> List[str]:
        out = []
        if self.digest_overlap_pct is not None and self.digest_overlap_pct >= WARN_DIGEST_OVERLAP_PCT:
            out.append(
                f"script copies the digest: {self.digest_overlap_pct:.0f}% of its "
                f"8-word phrases appear verbatim in the digest (warn >= {WARN_DIGEST_OVERLAP_PCT:.0f}%)"
            )
        if self.filler_pct >= WARN_FILLER_PCT:
            shapes = ", ".join(f"{k} x{v}" for k, v in sorted(self.filler_by_shape.items(), key=lambda kv: -kv[1])[:4])
            out.append(
                f"{self.filler_sentences} of {self.sentences} sentences ({self.filler_pct:.0f}%) "
                f"carry no fact — {shapes} (warn >= {WARN_FILLER_PCT:.0f}%)"
            )
        if self.duplicate_sentences >= WARN_DUPLICATE_SENTENCES:
            out.append(f"{self.duplicate_sentences} near-duplicate sentence pairs (warn >= {WARN_DUPLICATE_SENTENCES})")
        if self.repeated_facts >= WARN_REPEATED_FACTS:
            ex = "; ".join(self.repeated_fact_examples[:3])
            out.append(f"{self.repeated_facts} numeric facts spoken more than once ({ex}) (warn >= {WARN_REPEATED_FACTS})")
        if self.hook_restated:
            out.append(f"the cold-open fact is restated {self.hook_restated}x later in the episode")
        return out

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


def digest_overlap(script_text: str, digest_text: str) -> Optional[float]:
    """Share (0-100) of the script's 8-grams that appear verbatim in the digest."""
    if not script_text or not digest_text:
        return None
    grams = _ngrams(_words(_SPEAKER_PREFIX_RE.sub("", script_text)))
    if not grams:
        return None
    dgrams = _ngrams(_words(digest_text))
    return 100.0 * len(grams & dgrams) / len(grams)


def _closing_cut(sentences: List[str]) -> List[str]:
    """Drop the disclosure/CTA tail so 'nerranetwork.com' plugs never count."""
    keep = []
    for s in sentences:
        low = s.lower()
        if "ai voice synthesis" in low or "nerranetwork.com" in low:
            continue
        keep.append(s)
    return keep


def audit_script(
    script_text: str,
    *,
    digest_text: str = "",
    hook: str = "",
) -> ScriptAudit:
    sentences = _closing_cut(split_sentences(script_text))
    n = len(sentences)
    words = sum(len(s.split()) for s in sentences)

    # Near-duplicate sentence pairs (non-adjacent, so a deliberate
    # two-beat restatement inside one thought is not counted).
    dup_pairs = 0
    lowered = [s.lower() for s in sentences]
    for i in range(n):
        if len(lowered[i].split()) < 6:
            continue
        for j in range(i + 2, n):
            if len(lowered[j].split()) < 6:
                continue
            if abs(len(lowered[i]) - len(lowered[j])) > max(len(lowered[i]), len(lowered[j])) * 0.5:
                continue
            if calculate_similarity(lowered[i], lowered[j]) >= DUPLICATE_SENTENCE_THRESHOLD:
                dup_pairs += 1
                break

    # Numeric facts spoken more than once.
    seen: Dict[str, int] = {}
    for s in sentences:
        for phrase in set(numeric_phrases(s)):
            seen[phrase] = seen.get(phrase, 0) + 1
    repeated = {p: c for p, c in seen.items() if c >= 2}
    examples = [f"{p} x{c}" for p, c in sorted(repeated.items(), key=lambda kv: -kv[1])]

    # Filler shapes.
    by_shape: Dict[str, int] = {}
    filler = 0
    for s in sentences:
        for name, rx in _FILLER_COMPILED:
            if rx.search(s):
                by_shape[name] = by_shape.get(name, 0) + 1
                filler += 1
                break

    # Hook restated later in the body (the cold open itself is sentence 0/1).
    hook_hits = 0
    hook_low = " ".join((hook or "").lower().split())
    if hook_low and len(hook_low.split()) >= 5:
        for s in sentences[3:]:
            if calculate_similarity(hook_low, s.lower()) >= HOOK_RESTATE_THRESHOLD:
                hook_hits += 1

    return ScriptAudit(
        sentences=n,
        words=words,
        digest_overlap_pct=digest_overlap(script_text, digest_text) if digest_text else None,
        duplicate_sentences=dup_pairs,
        repeated_facts=len(repeated),
        filler_sentences=filler,
        filler_pct=(100.0 * filler / n) if n else 0.0,
        hook_restated=hook_hits,
        filler_by_shape=by_shape,
        repeated_fact_examples=examples,
    )


def audit_rows(pairs: Iterable[Tuple[str, str, str, str]]) -> List[Dict[str, object]]:
    """Batch helper for review_snapshot: (label, script, digest, hook) -> rows."""
    rows = []
    for label, script, digest, hook in pairs:
        a = audit_script(script, digest_text=digest, hook=hook)
        row: Dict[str, object] = {"label": label}
        row.update(a.to_metrics())
        rows.append(row)
    return rows
