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
subscriber with Django templating on their tags. Since Nov 3 2026 it reads as
a briefing — the first phone screen is the first card, not the hero:

1. **The masthead:** one row (cover, "Nerra Daily", the date) and one line:
   "Your shows below, then the rest of Nerra · ▶ 2 h 36 min, the whole
   morning in one listen". No paragraph about the layout.
2. **Your shows today:** one card per followed show.
   - The lead headline (the episode's whole hook).
   - **The deck:** one or two sentences of the digest's own prose on that
     story (`engine.landing_test.story_deck`, written into
     `api/personal_front.json` by the homepage build; no model call). A
     sentence the claims gate flagged is never printed; a digest with no
     matching item gets no deck rather than another story's prose.
   - **Also in this episode:** two more headlines in sentence case
     (`sentence_case_headline`, names kept as the digest capitalises them);
     the hook's own story is never listed again
     (`engine.newsroom.headline_within_hook`).
   - Listen, Read, Watch and the 30-second Short.
   - A video still scheduled says when it goes public.
3. **For a reader who follows none of today's shows:** five shows in full
   (SpaceX, Tesla, Top World, Models & Agents, Fascinating Frontiers), with
   "Choose your shows" linking to My Nerra.
4. **Also on Nerra today:** one short headline per other show that
   published (`engine.titles.EMAIL_ALSO_LINE_MAX`; a clip that reads as a
   fragment gives way to the digest's own headline), the show as a muted
   label, grouped by subject in the front page's section order. A subject
   label appears only over two or more lines; the rest gather under
   "Elsewhere on Nerra".
5. **🎧 Hear all of it:** today's Nerra Daily edition, after the reader's
   own shows.
6. **Sundays only:**
   - "Most played this week", one episode per show, each named by its
     whole hook (the OP3 file carries the clipped feed title).
   - "Your week": each followed show's last seven days.
7. **The Personal line:** "Hear this as your own daily episode… Try it free
   for N days." A paying member sees their own edition instead.
8. **The manage line:** choose your shows, or Sundays only, on My Nerra.

The archive copy ("View this email in your browser", no reader in the
context) opens on the masthead line and carries the default set; the
"Your shows today" heading is a reader's and never renders there.

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
  - It warns when the largest copy passes the size budget
    (`engine.nerra_daily_email.size_warning_bytes()`): Gmail's 102 KB clip
    minus Buttondown's wrapper minus a 2 KB margin. The wrapper
    (`BUTTONDOWN_WRAPPER_BYTES`, with its measured date) is an UPPER BOUND
    read from the archive page of the Nov 2 send (26,039 bytes of chrome
    around our blocks; the archive page carries a site head, a subscribe
    form and a settings blob the email does not). Measured on Nov 3 2026
    against that budget: the Monday follow-everything copy is 63 KB, the
    Sunday one 80 KB (a warning until the real wrapper is measured). The
    one-time operator measurement: send a draft to a test mailbox
    (`--mode draft --test-to`), take the message's HTML part size minus
    the composed copy, and replace the number and date. Never read
    `/v1/emails/{id}` for it — its `body` is the body as submitted. Each
    send's marker records `largest_copy_bytes`, `size_budget_bytes` and the
    `archive_url` of the sent copy.
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

## Nov 6 2026 review

Review doc (Claude Doc "Buttondown review: Nerra Daily"). In the code:

- A deck never opens on an item head's list of outlets and never ends a
  sentence on an abbreviation ("Oct.").
- An "Also on Nerra today" line prints whole up to
  `engine.titles.EMAIL_ALSO_LINE_MAX` (110), else the digest's headline for
  that story, else the hook's first clause.
- **The welcome email** is composed by `engine/nerra_welcome_email.py`
  (`python -m engine.nerra_welcome_email out.html`). It is not wired to any
  sender: a Buttondown automation (Standard plan) or the account Worker is
  the operator's choice.
- Buttondown starts accounts with open and click tracking OFF; until it is
  turned on, `opens` and `clicks` read 0 and mean "not measured".

Guards: `tests/test_nerra_daily_email_2026_11_06.py`,
`tests/test_nerra_daily_email_2026_11_01.py`,
`workers/gallery/test/email.test.ts`.
