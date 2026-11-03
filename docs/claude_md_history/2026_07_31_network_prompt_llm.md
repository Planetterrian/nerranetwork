# Network prompt + LLM review (July 31, 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Network prompt + LLM review (July 31, 2026)

Operator-directed all-show prompt pass + model strategy — canonical
writeup: [`docs/reviews/network_review_2026_07_31.md`](docs/reviews/network_review_2026_07_31.md);
ledger: `docs/reviews/ledger/network.yaml` (2026-07-31 entry). Highlights:
**P0 fixed** — the July-30 spoken identity line was deleted network-wide
by run_show's junk-title-header regex (no show said its own name since
the cold-open merge; stripper now exempts "this is"/«вы слушаете»
shapes, guarded in `tests/test_intros.py`). Source-scaffold scrub gained
the outlet-name ("Source: Google News.") and Russian em-dash
(«Источник информации — domain») shapes. Eleven confirmed seeded tics
de-seeded by shape across 10 shows (all ⚠️ A/B — PR #927). `clean_digest`
is now WIRED (operator-approved): podcast-only cleanup + Sunday
weekly-summary segment + duplicate-headline strip reach podcast prompts
for the first time. `vocab_tracker` no-reteach list uncapped + themes
window aligned (PR's 7-8-episode re-teach cycle). env_intel switched to
the digest-side length lever (min_digest_words 950; podcast retry off —
finansy_prosto is now the only sanctioned holdout). **Model strategy:**
digests/fetch stay on grok-4.3 (grok-4.5's confident-hallucination rate
rose 25%→54% — wrong trade for a facts-first network); new
`llm.podcast_model` lets one show A/B grok-4.5 on the script stage only
(empty default = byte-identical; guards pin the digest never follows
it); the scheduled reviewer runs grok-4.5 (`REVIEW_MODEL` env rollback).
dp_pod's Network-pick rotation is enforced data-side (recently picked
shows excluded from the candidate list) after the instruction-only fix
was violated six days straight.
