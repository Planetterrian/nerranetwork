# Actions minutes: the "is there work" decision leaves the runner (Oct 19 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Actions minutes: the "is there work" decision leaves the runner (Oct 19 2026)

Operator-directed (guards `tests/test_actions_minutes_2026_10_19.py`). Measured
Oct 16-18: ~1,790 runner-minutes a day (the repo is PUBLIC, so standard-runner
minutes are not billed — the cost is queue depth in the morning slate and the
watchdogs), of which ~460 were jobs starting Python to decide there was nothing
to do. Rules that bind: **multilingual.yml and nerra-daily.yml have no
`workflow_run` trigger.** `scripts/followup_dispatch.py` runs at the end of
every show run: it dispatches the multilingual sweep for ONE show only when the
show published a public episode of an auto-translated show whose video is not
still rendering (the video job dispatches `--after-video` once the gallery
manifest is pushed), and it wakes the Nerra Daily gate only for a roster show
landing AFTER `RELEASE_EASTERN` with no edition built (the scheduler Worker
dispatches the gate at the release and at the hold's end; a failed run wakes it
too — the Oct 18 lesson). A single-show multilingual dispatch answers without a
checkout; the cron passes remain every catch-all. **The Voices Worker's
half-hour producer tick asks Gmail first** (`producerTickDue`: the inbox job's
own query on both mailboxes, the same service account, fail-open; secrets
`GMAIL_SERVICE_ACCOUNT_JSON` / `GMAIL_DELEGATED_USER` on the Worker are
optional — unset dispatches as before). **A push to main that changes only
generated output never runs the test suite** (`paths-ignore` on test.yml and
e2e.yml; pull requests are never filtered). Operator: `wrangler deploy` in
`workers/voices` (and the two Gmail secrets to turn the gate on).
