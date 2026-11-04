# Provenance — Oct 1 2026: publish and mark, never strip (operator-directed)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 1 2026 — publish and mark, never strip (operator-directed).** In the
14 days to 10-01 strip mode removed 68 sentences across 261 episodes and
every audited one was TRUE (a 403 journal, an X post the fetch stage held,
a paraphrase, MIT's NASDAQ close); UC skipped 11 of 28 days on its own
gate; four of fifteen flagship episodes had zero claims. The model's
training data lags the 24-hour cycle, so a sourced story newer than the
model must never be dropped for failing memory. Now `on_failure: flag`
(network default, UC and FPD too): after the one repair pass nothing is
removed but reviewer notes; every ledger entry commits with a `status`
(`verified` / `verified_from_fetched` / `verified_later` /
`unverified_unreachable` / `unverified_not_found` /
`unverified_quote_mismatch` / `unverified_uncovered` / `malformed`),
`gate.flagged_sentences` names the sentences, `gate.policy_version` is 2;
metrics `source_integrity_flagged_*`. `scripts/reverify_claims.py` re-checks
unverified claims nightly for seven days (`verified_later`, `verified_at`,
`first_status`; the sidecar glob is in nightly's add-paths). The record is
public — `claims.html` and `claims/<slug>.html` (`engine/claims_ledger.py`,
`generate_claims_pages`, in `--static-pages` and the sitemap), status
badges on every post's claims panel, links from show pages, nav and
footer; `engine.brand.CLAIMS_PROCESS_STEPS` / `CLAIMS_STATUS_LABELS` own
the process copy and the AI-disclosure / editorial / FAQ pages describe
this policy and no stronger one. Register `claims-flag-policy-2026-10-01`;
guards `tests/test_claims_flag_mode_2026_10_01.py`,
`tests/test_claims_pages_2026_10_01.py`.
