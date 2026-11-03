# Provenance — Aug 25 2026: unreachable ≠ fabricated, plus two loop-breakers

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Aug 25 2026 — unreachable ≠ fabricated, plus two loop-breakers.** UC
lost two days because its next topic's authoritative sources
(officialgazette.gov.ph) 403 GitHub runners: the gate read "cannot
fetch" as "fabricated", the queue-preserving skip re-picked the same
topic daily, and nothing persisted the failure. Now: (1) verification
labels 403/429/5xx/transport failures `unreachable` — **still a gate
FAILURE** (the enforce contract is untouched), but distinct from the
fabrication signature (404 / quote-not-found); (2) an enforce-mode
block first gets ONE `attempt_claim_repair` pass (the model re-sources
only the failed claims with fetchable alternatives — claim text and
anchor are pinned, the repaired ledger re-runs the FULL mechanical
gate, so repair can never launder an unverifiable claim); (3) a topic
the gate blocks twice is **deferred by the picker**
(`gate_blocks`/`gate_blocked_last` on the queue entry, committed by
run-show.yml's skip-path step — the annotation is the only thing that
survives a skip; threshold in
`engine.topic_queue.GATE_BLOCK_DEFER_THRESHOLD`). Deferred topics stay
in the queue for the operator and are surfaced by
`queue_health()["gate_deferred"]`. Guards:
`TestUnreachableClassification`, `TestClaimRepair`
(`tests/test_source_integrity.py`), `TestGateBlockCooldown`
(`tests/test_unintended_consequences.py`).
