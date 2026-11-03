# Gated shows — members-only and public-weekly (Oct 13 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Gated shows — members-only and public-weekly (Oct 13 2026)

Operator-directed: some shows will publish only for Nerra Personal members
who carry them, some publicly one weekday with the daily episodes for
members. **`engine/access.py` owns the decision; `access:` in the show
YAML is the setting (`public` default — every show is public today and a
guard says so).** Rules that bind: the demand gate runs before any spend
and skips `no_member_demand` at zero, but UNKNOWN demand produces (a paying
member may be waiting); an unknown `access.mode` RAISES, never publishes;
a members episode stops between the rehearsal stop and the publish phase —
audio to the private bucket, text to `digests/<dir>/members/`, the ledger
`members/episodes.json` (also a numbering source) — so no public surface
needs a filter: they all read the show directory's top level. **A new
consumer that globs a show's digests recursively must skip `members/`.**
Nerra Daily reports a members day as skipped (`members_only`); the
Personal builder alone passes `include_members=True`. Text stays in this
public repo by operator choice; only audio is private. **Oct 15 2026 — the five
Omni View regional desks are the first gated shows** (operator-directed;
register `desks-members-only-2026-10-15`; guards
`tests/test_desks_members_only_2026_10_15.py`): `members_only` with
`access.unknown_demand: skip`, so an unreadable demand skips
(`member_demand_unknown`, the audit warns) instead of producing for nobody —
the gallery Worker answered 404 on `/api/admin/show-demand` that day. A
`no_member_demand` day is the gate working and the audit stays quiet. Top
World reads a desk's digest from `members/` too (headlines and publisher URLs
only). A members-only show's page is refreshed by the nightly
(`scripts/list_unowned_show_pages.py` — its run never writes the page), and no
show plugs it on air. Doc:
[`docs/nerra_personal.md`](docs/nerra_personal.md) "Gated shows". Guards:
`tests/test_personal_gating_2026_10_13.py`,
`workers/gallery/test/personal.test.ts` ("show demand").
