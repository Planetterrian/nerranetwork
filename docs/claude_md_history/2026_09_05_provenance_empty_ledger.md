# Provenance — Sep 5 2026: the empty ledger was the norm, not the exception

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 5 2026 — the empty ledger was the norm, not the exception.** Every
UC and FPD episode since the counters exist (UC Ep099–106, FPD Ep086–091)
shipped `claims=0`: the appendix calls an empty array normal, so on the
narrative shows the enforce gate was in practice the citation-shape lint
alone, and `attempt_claim_repair` never fired for it (it keyed on failed
verifications). UC 2026-09-05 was blocked twice on one topic with
claims=0 and two uncovered shapes. Repair now also targets UNCOVERED
sentences (anchor pinned to the sentence, full mechanical gate re-runs,
so an unsourced sentence still blocks), and UC's episode prompt no longer
seeds the literal "A 1962 Nature paper warned…" example — the exact
fabricated citation this section opens with. Guards:
`TestClaimRepairUncoveredShapes`.
