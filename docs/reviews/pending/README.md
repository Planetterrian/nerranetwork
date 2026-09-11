# Pending review proposals

One file per review: the PR body `scripts/run_show_review.py` committed into
the review branch **before** calling `gh pr create`, because it holds the only
copy of the proposed A/B prompt edits and a failed PR open used to lose them
(five runs' proposals were gone, June–July 2026). Do not stop writing it.

## Retention: newest per show

A later review of the same show **re-scores** every prior prediction and
**re-proposes** whatever is still broken — the Sep 7 Финансы Просто pass
re-filed the Aug 6 proposals verbatim as "never shipped". So the newest file
for a show is the live proposal set and the older ones are superseded by
construction. The precedent is the July 1 2026 triage note: *keep the newest
FF one, review its pending proposals*.

Superseded files are removed here. Nothing is lost: the merged PR body stays
on GitHub, the review doc is in `docs/reviews/`, and the rationale for each
proposal is in the ledger's `proposed_changes_in_pr`
(`docs/reviews/ledger/<slug>.yaml`). Git history has the file itself.

**A file on `main` came from a MERGED review PR.** A review PR closed
unmerged never lands its body here — per the July 18 2026 playbook rule, an
infrastructure close is not a rejection, so recover those proposals from the
PR itself (or its `agent/review-<slug>-*` branch), not from this directory.

Each file is a proposal, never an applied change: prompt/audio edits are
applied and A/B-listened by the operator (landmine #17).
