# Sep 21 2026 — the capture end of the funnel

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 21 2026 — the capture end of the funnel, and why three audits blamed the
wrong function.** Phase 1 made clicks traceable (4 parseable campaigns,
`attribution_coverage_pct` 3.5%) while capture stayed dark: 5 subscribers,
`tag_counts: {}`, `by_source: {}`. `resolveSubscribeTags` was NOT the bug — it
always put tags in the request body. Guards:
`tests/test_capture_measurement_2026_09_21.py`; experiment
`capture-measurement-2026-09-21` (readout 2026-10-21). What binds now:

- **A capture tag is applied on create AND on a duplicate.** The Worker's
  duplicate branch returned `{ok:true, alreadySubscribed:true}` and stopped, so
  tagging was CREATE-only: an address already in Buttondown when the tagged path
  shipped could never acquire `nerra-member`, a show tag or a `src-*` source,
  however many times they resubmitted. `buttondown.ts` now merges via
  `PATCH /v1/subscribers/{id}`. **The merge is a UNION, never a replace** —
  PATCH overwrites the tag array, so sending only the wanted tags would strip a
  member's show subscriptions on their next footer signup, a data loss shaped
  exactly like a working signup. Every merge failure still reports the subscribe
  as successful: an attribution tag is not worth a 502 on someone's signup.
- **A signup form that sends no `source` makes `capture.by_source` structurally
  impossible.** None of the three first-party forms sent one
  (`base.html.j2`, `join_page.html.j2`, `network_page.html.j2`) — only the RU
  lander did — while the Worker accepted the whole allow-list. **The guard is why
  it survived:** it asserted the Worker *accepts* every `engine.funnel` source
  tag and never that a page *emits* one. Guard both ends. The tag renders from
  the `capture_source_site` Jinja global fed by `engine.funnel`, never a literal.
- **"A result key is not a metric" — fourth instance.**
  `select_personal_upsell` had fired from the network's only on-site upsell
  since 2026-09-19 and was read by nothing, because
  `fetch_ga4_stats.py` filtered events to an inline two-name list. Now
  `CONVERSION_EVENTS` / `ENGAGEMENT_EVENTS` are named constants and the
  engagement events are a **SEPARATE report**: `build_funnel._captures()` sums
  every row of the conversions report into `signup_events_total`, so an
  engagement event in that list would report an intention as a subscriber.
  Add the event to the constant when you add the `gtag` call.
- **`api/member_metrics.json` counts paid members, and carries no PII.** The
  admin endpoint returns `first_name` and `city`; at five members that names a
  person, in a file committed to a public repo. `build_member_metrics.py` writes
  integers and show histograms only, never a name, city, email or feed token —
  PII-light by construction, like `build_personal_feeds.py`. `free_accounts`,
  `mrr_usd` and `trialing` are **null**: the endpoint lists only active PAID
  records, and nothing in this repo reads Stripe. A run with no
  `PERSONAL_ADMIN_TOKEN` leaves real counts alone rather than overwriting them
  with nulls.
- **Reading `/tags` cannot tell "no tags" from "tags without counts".**
  `fetch_tag_counts` skipped any row lacking an integer `subscriber_count`
  silently, so both produced an empty dict while the warning asserted the first.
  The repo's other client of that endpoint reads only `name` and `id`, so the
  count field is not a safe assumption. It now says INCOMPLETE when rows were
  skipped, and the warning names the read-only way to settle it: dispatch
  `buttondown-tag-subscriber.yml` in **`list-all`** mode, which prints each
  subscriber's real tags. That script can only write tags drawn from show YAMLs,
  so it cannot backfill `nerra-member` or any `src-*`.
- **Blog cross-show recommendations are seeded per POST**
  (`generate_html.py` `_pick_cross_show_related(seed=…)`, CRC32-of-stem as in
  `engine/video.py`). Unseeded, every regen rewrote all ~200 of a show's posts
  with fresh random picks, so no refactor could be proven output-neutral.
  Seeding by slug would give every episode the identical three. It makes a
  re-run with the same candidate pool byte-identical; it does not freeze the
  picks, since the pool moves as the network publishes.
- The three Python Buttondown clients now agree on `api.buttondown.com/v1`. The
  Worker still writes to `api.buttondown.email/v1`; both hosts are live and that
  write path is deliberately left alone rather than flipped without a key to
  verify against.
- **The Worker's vitest suite is not run by any workflow** — `test.yml` runs
  ruff, actionlint and pytest only. Worker behaviour is guarded from CI by
  reading the TypeScript as text from Python, which is why the guards above
  assert on source strings; run `npx vitest` by hand when you change
  `workers/`.
