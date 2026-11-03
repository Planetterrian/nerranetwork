# Oct 9 2026, later — four items the operator said yes to

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 9 2026, later — four items the operator said yes to** (register
`spacex-script-grok46-2026-10-09`, `ops-bundle-2026-10-09`; guards
`tests/test_ops_bundle_2026_10_09.py`). **SpaceX's script stage runs
grok-4.6** (`llm.podcast_model`; the digest stays 4.3; two-pass by code like
Omni View) — the one measured quality lever: over Oct 2-8 the 4.3 flagship
scripts read the digest aloud (SpaceX 64% verbatim, 3-12 claims) where the
4.6/4.7 script arms write (2-17%, 13-27 claims). Tesla joins only on a
GATE: PASS at the 10-23 readout. ⚠️ AUDIO — A/B-listen Ep1. **The ZH track
is off** on tesla, spacex and fascinating_frontiers (every ZH feed
`measured: false` for eleven weeks at ~$2.70/week; the committed
`*.zh.rss` feeds are frozen, not deleted; a zh track needs BOTH the
language and `zh_approved`). **The Voices Worker holds ONE cron trigger**
(`*/5 * * * *`; fire-tick every firing, producer-tick on :00/:30, gate 2 at
17:00 UTC, decided from the firing minute; it was written when the account's five
Workers Free triggers were all spent, and the account is on Workers Paid
now) — operator: `wrangler deploy` in
`workers/voices`. **Dependabot groups each ecosystem's bumps into one
weekly PR**; the `av>=19` ignore stays.
