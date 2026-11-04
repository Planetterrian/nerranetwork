# Provenance — Sep 18 2026: the quote was the problem, not the source

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 18 2026 — the quote was the problem, not the source.** SpaceX
Ep104 lost five TRUE sentences to strip mode (Shotwell telling Boeing
to fly Starliner, Crew-13 entering quarantine, Dragon's 2030 retirement)
with every source RESOLVED: WESH's own headline was the claim. The
model's `supporting_quote`s were paraphrases, so the 0.9 verbatim check
failed, and the repair prompt demanded a DIFFERENT url — a truthful
model omitted every claim ("no usable replacements") and the sidecar
then read "claims=0, passed". Now: for a failed claim whose source
resolved, `attempt_claim_repair` hands the model the page's most
relevant passage (`source_excerpt_for_claim`, from the run's fetch
cache or the fetched copy) and allows the SAME url with a quote copied
verbatim from it; the mechanical 0.9 check is untouched and a verbatim
sentence unrelated to the claim is rejected
(`_quote_consistent_with_claim` — two shared content words or a shared
number). Metric `source_integrity_repair_recovered` (read beside
`_stripped_sentences`); the sidecar's `gate.pre_strip` records the
verdicts and the model's quotes as the gate saw them BEFORE the strip.
A bag-of-words "claim support" fallback was measured and REJECTED as a
gate: random foreign claim/source pairs score ≥ 0.5 four percent of the
time and short true sentences score no higher. Guards:
`tests/test_provenance_pass_2026_09_18.py`.
