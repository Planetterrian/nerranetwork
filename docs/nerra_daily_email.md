# Nerra Daily email (Nov 1 2026)

The network sends one email, **Nerra Daily**. Each subscriber's copy carries
the shows they follow. It replaces the per-show daily emails and the per-show
Sunday weeklies for every English show.

## Why

Measured on Nov 1 2026, before the change:

- **Who it reached.** 14 subscribers in total (2 paid Personal members).
  Email sent 3 sessions to the site in 28 days.
- **Daily sends.** About 19 per-show sends were attempted each morning.
  - Ten went out, each to one to three people.
  - Five failed every day (Vancouver, Top World, MAG 7, AI Chips,
    Prediction Markets), because nobody had followed those shows, so
    Buttondown had no tag for them.
  - A reader following five shows got five emails a day, plus five more
    on Sunday.
- **The weekly.** It spent about 36 minutes of Grok synthesis every Sunday
  on nine emails with a handful of readers each.
- **A promise with nothing behind it.** The join page ("Joining subscribes
  you to the Nerra newsletter") and every RSS episode ("Get the sources and
  notes by email, free") promised a newsletter. Those signups were tagged
  `nerra-member`, and nothing was ever sent to that tag.
- **Unmeasured.** No email link carried a campaign, so a click from Gmail
  read as Direct.
- **Nothing to upgrade from.** No email mentioned Nerra Personal.

## What a reader gets

One email at 7:00 AM Eastern, Monday to Sunday. Buttondown renders it per
subscriber with Django templating on their tags:

1. **Today's Nerra Daily edition** (the featured card).
2. **Your shows today:** one card per followed show.
   - The lead headline, then three more.
   - Listen, Read, Watch and the 30-second Short.
   - A video still scheduled says when it goes public.
3. **For a reader who follows none of today's shows:** five shows in full
   (SpaceX, Tesla, Top World, Models & Agents, Fascinating Frontiers), with
   "Choose your shows" linking to My Nerra.
4. **Also on Nerra today:** one line for every other show that published.
5. **Sundays only:**
   - "Most played this week", one episode per show.
   - "Your week": each followed show's last seven days.
6. **The Personal line:** "Hear this as your own daily episode… Try it free
   for N days." A paying member sees their own edition instead.
7. **The manage line:** choose your shows, or Sundays only, on My Nerra.

An episode counts as news for two days. An episode published after the
7:00 AM email (Vancouver, a weekly show's late run) arrives the next morning.
Every episode an email carried is recorded in that day's marker, so it is
never repeated.

## Tags (the state)

| Tag | Meaning | Set by |
|---|---|---|
| a show's `newsletter.tag` | carry this show | show page, footer and blog forms; My Nerra (lineup and the email panel) |
| `nerra-member` | free account | join page, Soft Personal box |
| `gallery-subscriber` | gallery signup ("receive emails from Nerra Network") | gallery gate, footer form |
| `nerra-daily-weekly` | Sunday edition only | My Nerra |
| `personal-paid` | an active Personal member: no pitch | Stripe webhook; nightly reconcile |

**Audience** (`engine.nerra_daily_email.audience_filter`) is everyone with:
- `nerra-member`, `gallery-subscriber` or an English show tag;
- minus a reader whose only shows are Russian (they have their own Russian
  email);
- minus, Monday to Saturday, `nerra-daily-weekly`.

Tags Buttondown has never seen are left out of the filter. An empty filter
is never sent, because it would reach the whole list.

**Show map.** `engine.nerra_daily_email.email_show_tags()` (public English
shows, `newsletter.delivery: nerra_daily`, members-only desks excluded) is
mirrored in `workers/gallery/src/email.ts` `EMAIL_SHOW_TAGS`. The two are
drift-guarded.

## Moving parts

- **Composition:** `engine/nerra_daily_email.py`. It reads
  `api/personal_front.json` and the shows' YouTube indexes, and makes no
  model call. Every site link goes through `engine.funnel.newsletter_link`:
  - `utm_source=newsletter`, `utm_medium=email`;
  - campaign `nn-<show>-en-email-epNNN-nerra_daily`;
  - network pages use show `nerra_daily` with the variant `personal`,
    `choose`, `manage` or `footer`.
- **Sending:** `scripts/send_nerra_daily_email.py`.
  - Before anything goes to Buttondown, it renders three copies (a new
    reader, a two-show follower, everything) and refuses on a contrast
    failure or an unbalanced template.
  - It warns when the largest copy passes 95 KB. Gmail clips at about
    102 KB.
- **When it runs:**
  - `nerra-daily.yml` runs it right after the edition publishes.
  - `nerra-daily-email.yml` is the fallback (12:25 and 13:25 UTC) and the
    operator's preview.
- **Idempotency:** the committed marker
  `digests/nerra_daily/email/<date>.json`. Buttondown also refuses a second
  email with the same archive slug.
- **Delivery switch:** `newsletter.delivery`.
  - `_defaults.yaml` sets it to `nerra_daily` for every show.
  - `finansy_prosto` and `privet_russian` are `own`.
  - With `nerra_daily`, `run_show`, `scripts/run_weekly_newsletters.py`,
    `run_weekly_synthesis.py` and the Voices publisher send nothing per
    show.
- **Account Worker:** `workers/gallery/src/email.ts`.
  - A lineup save adds its shows to the email and drops the shows removed
    from the lineup. A show followed from a show page and never in the
    lineup is left alone.
  - `GET` / `POST /api/account/email` power the email panel on My Nerra.
  - Stripe activation and cancellation set and clear `personal-paid`.
  - `POST /api/admin/sync-email-tags` reconciles paid status nightly;
    `?lineups=1` is a one-time backfill of lineups.
- **Measurement:** `scripts/fetch_buttondown_stats.py`.
  - Per-email analytics for the last 30 days, and the last seven Nerra
    Daily sends in `nerra_daily`.
  - Tag counts from the subscriber list when `/tags` carries none (it has
    carried none on this account).
  - Rates stay null under 30 recipients; the counts are the honest number.
  - Mission Control has a "Nerra Daily email" tile.

## Operator

- **Preview:** Actions → **Nerra Daily email** → mode `draft` with your
  address in `test_to`, or mode `preview` for the HTML as an artifact.
- **After `wrangler deploy` in `workers/gallery`:**
  `PERSONAL_ADMIN_TOKEN=… python scripts/sync_email_tags.py --lineups` once.
- **Revert to per-show emails:** set `newsletter.delivery: own` in
  `shows/_defaults.yaml`.

Guards: `tests/test_nerra_daily_email_2026_11_01.py`,
`workers/gallery/test/email.test.ts`.
