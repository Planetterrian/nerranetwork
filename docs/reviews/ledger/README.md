# Review ledger

One YAML file per review target (`<slug>.yaml`, plus `network.yaml`). This
is the Show Review Agent's memory — the mechanism that makes the review
loop *recursive* instead of episodic. Every review appends an entry; the
NEXT review of the same target starts by scoring the previous entry's
predictions and honoring its `do_not_retry` list.

## Schema

```yaml
reviews:                      # chronological, newest last
  - date: 2026-06-10
    pr: 576                   # the review PR number (null for pre-agent passes)
    doc: docs/tesla_review_2026_06_10.md
    summary: One-line what-this-pass-was-about.
    shipped:                  # fixes that landed (short labels)
      - chapters positional anchoring
    deferred:                 # recommendations NOT implemented — the next
      - digest-driven chapter titles (medium effort)   # review re-evaluates these
    predictions:              # every shipped fix claiming a measurable effect
      - metric: median _tts.txt words, last 10 eps
        baseline: 1450
        expected: ">= 2000 within 2 weeks"
        verdict: pending      # the NEXT review sets: hit | partial | miss (+ evidence)
        evidence: null
    agent_cost_usd: null      # optional, if known

do_not_retry:                 # operator-rejected / reverted ideas. NEVER
  - idea: phonetic respellings for proper nouns       # re-propose unless the
    evidence: reverted May 11 2026; 100% regression rate on custom voice
    # evidence-no-longer-applies test is explicitly argued in the review doc.
```

## Rules

- A `miss` verdict means the underlying problem is still open: it goes back
  on the new review's findings list, attacked with a *different* approach.
- A reverted prompt/audio commit is a failed A/B listen (landmine #17):
  record it under `do_not_retry` with the revert hash as evidence.
- A closed-unmerged `agent/review-<slug>-*` PR is an operator rejection:
  record the rejected ideas under `do_not_retry`.
- `network.yaml` additionally feeds the meta-review: aggregate verdict rates
  by finding category to decide which kinds of findings the playbook should
  weight up or stop proposing.
