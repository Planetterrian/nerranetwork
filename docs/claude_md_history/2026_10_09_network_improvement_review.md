# Oct 9 2026, network improvement review

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 9 2026, network improvement review** (doc:
[`docs/reviews/network_improvement_review_2026_10_09.md`](docs/reviews/network_improvement_review_2026_10_09.md);
guards `tests/test_verify_analytics_snapshot_2026_10_09.py`,
`tests/test_multilingual.py`). Two measurement defects fixed with it:
**`verify-youtube-analytics.yml` runs on any push that touches it and wrote
`api/youtube_stats.json` with no @NerraFR block** (EN/RU tokens only, no
`snapshot_regression`) — it carries every channel token the nightly does
and refuses a regressed snapshot now; and **the multilingual sweep ran on
all seven shows after EVERY successful show run** (92 "Multilingual:"
commits on Oct 7): `workflow_run.head_commit` is the tip the run STARTED
on, never the "Auto-generated: <show>" commit made during it, so the
Sep narrowing had never fired — the resolve step reads the triggering
run's jobs (`run (<show>)`, `actions: read`) instead. Reading rules from
the review: a trailing-7-day OP3 figure that beats every complete week is
a catalogue sweep, not growth (read complete weeks); the 4.7 cohort
writes and the 4.3 flagships copy, on every surface measured; 20 live
feeds are findable only on nerranetwork.com; no first-party signup
surface fires a GA4 event, so "0 signups" means unmeasured.
