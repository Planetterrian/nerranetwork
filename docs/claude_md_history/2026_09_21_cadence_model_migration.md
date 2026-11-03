# Cadence + model migration (Sep 21 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Cadence + model migration (Sep 21 2026)

**A show's cadence lives in six places and the public one drifted.**
CRON_MAP, the scheduler Worker's `SLOTS`, `review_episodes.py`'s registry
(the audit's belief), daily-audit's RSS-freshness limit,
`engine.daily_edition`'s `monday_only`, and the `schedule` string every show
page / homepage card / explore filter renders. The first five were correct
and in sync; **the sixth had been wrong since June on three shows.**
env_intel said "Odd weekdays", finansy_prosto and privet_russian said "Even
days", and all three have published Mondays only since the June move — the
July-18 P0 fixed the cron and the audit and never the copy. Unintended
Consequences said "Weekdays" and publishes all seven days. Feed descriptions
carried the same claims, which is the text Apple and Spotify display.
`tests/test_dp_pod_weekly_2026_09_21.py::TestNoSurfaceStillSaysDaily`
derives the check from CRON_MAP, so a cadence change that forgets the copy
now fails. (`modern_investing` is genuinely daily — the "weekdays only" note
elsewhere in this file was the stale one.)

**DP Pod is weekly** (Monday), operator-directed: 60 downloads/30d and 3 in
its last complete week, with three prompt passes that improved the copy and
moved no listeners.

**A missing section is a structural defect, same as an empty one.** The
validator has always emitted `Section 'X' is missing from digest`, and
`_empty_mandatory_section_issues` only matched `0 items` — so an EMPTY
section spent the one-shot corrective regeneration while an ABSENT one
shipped. DP Pod published four episodes with no Lever segment at all (37/37
digests carried it before the 2026-09-04 lever pass, 14/18 after) and the
run logged a formatting mismatch. The gate matches both now, and dp_pod has
a `SHOW_VALIDATION_CONFIGS` entry at last — it had none, which is why
nothing noticed a show had stopped carrying one of its own segments. Fixed
data-side rather than by rewording a prompt that already said "never omit
any": this show's own history (the Network-pick rotation) says an
instruction the model breaks is enforced in code.

**Model changes follow [`docs/model_upgrade_playbook.md`](docs/model_upgrade_playbook.md),
and `scripts/model_trial_report.py` is the instrument.** It reads committed
`metrics_ep*.json` stage durations — dating each episode from the sibling
digest filename, never file mtime, which a fresh checkout rewrites — and
exits non-zero when an LLM stage's p95 passes 50% of the request timeout,
regresses >50% against baseline, or any stage failed. The Aug-18 outage's
registered triggers watched hallucination rate and reviewer flags; nobody
watched latency, and latency is what fired. The grok-4.6 -> 4.7 migration
(experiment `grok-47-staged-migration`) moves two sites on day one — the
episode reviewer and omni_view's script stage — and widens only on a
GATE: PASS. **The reviewer's `reasoning_effort: "low"` branch is a prefix
TUPLE, not one id**: at default effort 4.6 blew the 300s timeout on ~1/3 of
episodes and killed the audit job, and a pin moved to 4.7 would have matched
nothing and silently restored default effort.

**`api/member_metrics.json` filters by Stripe PRODUCT.** The account is
shared ("Lil Learning") and carries the Lil Words products beside Nerra
Personal, so summing every subscription would put another product line's
revenue in a file labelled Nerra's MRR — one number, no error, just wrong.
Today the only active subscription is Nerra Personal, so filtered and
unfiltered agree, which is exactly why the filter went in before it mattered.
