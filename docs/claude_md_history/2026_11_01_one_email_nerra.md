# One email: Nerra Daily (Nov 1 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### One email: Nerra Daily (Nov 1 2026)

Operator-directed (doc [`docs/nerra_daily_email.md`](docs/nerra_daily_email.md);
register `nerra-daily-email-2026-11-01`; guards
`tests/test_nerra_daily_email_2026_11_01.py`, `workers/gallery/test/email.test.ts`).
Measured first: 14 subscribers, about 19 per-show daily sends a morning (five
failing every day on tags no subscriber carried), nine per-show weeklies on
Sunday, 3 email sessions in 28 days, and the free account's promised
newsletter (`nerra-member`) never sent. Rules that bind:

- **The network sends ONE email, Nerra Daily**
  (`engine/nerra_daily_email.py`, `scripts/send_nerra_daily_email.py`).
  - `nerra-daily.yml` sends it right after the edition publishes, scheduled
    for 7:00 AM Eastern.
  - `nerra-daily-email.yml` is the fallback and the operator's draft/preview.
  - The committed `digests/nerra_daily/email/<date>.json` is the
    idempotency key.
- **It is personalized by Buttondown's per-subscriber Django templating on
  TAGS**, never by sending different emails:
  - a show's `newsletter.tag` is the follow;
  - `nerra-daily-weekly` means Sundays only;
  - `personal-paid` hides the Personal pitch.

  Django `{% if %}` has no parentheses, so every condition is a flat
  `and`/`or` chain or a nested `{% if %}`. `render_for` evaluates the same
  subset for tests and the preview. Content braces are entities, so a
  headline cannot become template syntax.
- **`newsletter.delivery`.**
  - `_defaults.yaml` sets `nerra_daily`. With it, `run_show`, the weekly
    runner, `run_weekly_synthesis.py` and the Voices publisher send nothing
    per show.
  - The two Russian shows are `own` and keep their Russian daily email.
  - The dataclass default is `own`, so a caller that bypasses the YAML
    behaves as before.
- **The audience is a filter tree** (`audience_filter`):
  - included: `nerra-member`, `gallery-subscriber`, or an English show tag;
  - excluded: Russian-only readers, and Monday to Saturday the Sundays-only
    tag;
  - a tree with nothing resolved is refused, never sent unfiltered.
- **One show map, two copies:** `email_show_tags()` (public English, not the
  members-only desks) and the Worker's `EMAIL_SHOW_TAGS`.
- **The Worker moves the tags:**
  - a lineup save adds its shows and drops only the shows taken out of the
    lineup (a show followed from a show page stays);
  - `GET`/`POST /api/account/email` is My Nerra's email panel;
  - Stripe sets and clears `personal-paid`;
  - the nightly `scripts/sync_email_tags.py` reconciles paid status and
    never re-adds lineup shows.
- **Every site link is `engine.funnel.newsletter_link`** (`kind="email"`,
  variant `nerra_daily` or the network surface; `PLACEMENT_WEEK` for the
  Sunday lists). The shared footer is tagged as `footer`.
- **Size and contrast.** Every copy must pass contrast and stay under about
  95 KB (Gmail clips at 102 KB). A `display:none` element has no contrast to
  fail (the preheader).
- **Measurement.** `fetch_buttondown_stats.py` reads per-email analytics.
  It counts tags from the subscriber list because `/tags` carries no counts
  on this account. Rates are null under 30 recipients.

Operator:
- `wrangler deploy` in `workers/gallery`, then once
  `PERSONAL_ADMIN_TOKEN=… python scripts/sync_email_tags.py --lineups`.
- Preview with Actions "Nerra Daily email", mode `draft` with `test_to`.
