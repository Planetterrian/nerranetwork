# Nerra Personal — accounts, personalized feeds, donations

The member surface (Aug 2026, operator-directed): ONE identity unifies
the newsletter, the gallery gate, member perks (book discounts), and the
paid product — a private daily feed of the subscriber's chosen shows, in
their order, anchored by Mira. Donations live beside it on
`/support.html`. Engine design rules: `engine/personal_edition.py`
docstring. Drift guards: `tests/test_nerra_personal.py`,
`workers/gallery/test/personal.test.ts`.

## The one-identity model

A "Nerra account" IS the existing gallery-subscriber identity (the
Worker's 90-day JWT cookie + Buttondown record). Nothing was forked:

- **Signing up anywhere creates the account.** The footer newsletter
  form and `/join.html` both POST `/api/subscribe` with `list:"member"`
  (tags `nerra-member` + `gallery-subscriber`, plus any per-show
  newsletter tags from the closed `SHOW_NEWSLETTER_TAGS` set). The
  Buttondown-direct embed form is gone — every newsletter signup is now
  an account.
- **Sign-in** is the existing magic-link flow (`/api/login` →
  `/api/magic`). No passwords anywhere.
- **Gallery downloads** already honor this cookie — members get them by
  construction.
- **Perks** render on `/account.html` from `GET /api/account` — today:
  the book discount code (`MEMBER_BOOK_CODE` Worker secret; create the
  matching code in the book store — Gumroad supports codes; KDP does
  not, use its price promotions instead).

## The paid tier (personalized feeds)

| Piece | Where |
|---|---|
| Preferences (shows/order/name/city) | `POST /api/account/preferences` → KV `member:<email>` |
| Billing | Stripe Payment Links (operator-created) + `POST /api/stripe/webhook` |
| Feed token | Minted on `checkout.session.completed`; KV `feedtok:<token>` → email |
| Assembly | `scripts/build_personal_feeds.py` (daily, on a PRIVATE host) |
| Audio + feed storage | R2 bucket `nerra-personal`, keys `personal/<token>/…` |
| Serving | `GET /api/feed/<token>/<file>` — Worker-gated, streams from R2 |
| Revocation | Subscription cancelled → `feedtok:` mapping deleted → feed 404s immediately |

Pricing (operator sets the amounts in Stripe; the pages read the links
from env): **Personal $4.99/mo**, **Personal News Network $8.99/mo** (the
public name since 13 Sep 2026 — see that section below; the internal tier
id stays `personal_local`). Tier is
carried on the Payment Link's `metadata.tier`
(`personal` / `personal_local`), which Stripe copies onto every Checkout
Session the link creates.

That marker is **required**, not a hint. The webhook endpoint receives
every completed checkout in the Stripe account — including the
`/support.html` donations, which live in the same account. An earlier
`amount_total >= $7.99` fallback would have handed a paid feed to anyone
who donated $10 once, so it was removed on 2026-08-23: a session without
a known `tier` is ignored and logged, never activated. Donation links
carry `metadata.kind = "donation"` so the log line says which.

The builder's cost discipline: each show's episode is downloaded and
promo-trimmed ONCE per day into a shared cache (the same
`find_promo_cut` machinery Nerra Daily uses); per-subscriber work is
Mira's links (grok-4.3 + TTS, deterministic fallback), the optional
local brief, and a stream-copy concat. Measured marginal cost
~$0.05–0.07/subscriber/day. Feeds keep the newest 7 episodes
(`PERSONAL_FEED_MAX_EPISODES`); older audio is deleted on prune.

**The local brief** (`personal_local` tier — publicly Personal News Network): Open-Meteo geocoding +
forecast (free, keyless, measured data only) plus ONE
web-search-grounded Grok call for a local story/event — the field-note
honesty contract: source named aloud, `SKIP` when nothing verifiable,
never filler.

**PII rules.** Specs flow Worker → builder as
`{token, shows, tier, first_name, city}` — never an email
(`/api/admin/personal-specs` strips it by construction, bearer-gated by
`PERSONAL_ADMIN_TOKEN`). The builder logs tokens truncated to 8 chars
and never logs names/cities. It must run on a **private host** (VPS
cron or a private repo's Actions) — never in this public repo's
workflows, whose logs are world-readable. Recommended cron:
`30 12 * * *` UTC (after the English slate + Nerra Daily).

## Add-ons (Aug 30 2026)

Members customize what Mira researches for their edition from the
dashboard (`/account.html`). Closed vocabulary — `PERSONAL_ADDONS` in
`engine/personal_edition.py`, mirrored verbatim in
`workers/gallery/src/personal.ts` (drift guard:
`tests/test_nerra_personal.py::TestAddons`):

| Add-on | Tier | Source | Marginal cost |
|---|---|---|---|
| `weather` | Personal News Network | Open-Meteo (measured, keyless, free) | ~0 |
| `local_news` | Personal News Network | Mira web search, source named aloud | shared* |
| `events` | Personal News Network | Mira web search | shared* |
| `traffic` | Personal News Network | Mira web search (real disruptions only — regional 511 APIs all need keys, so research beats integration) | shared* |
| `markets` | Personal | `api/tsla.json` + `api/spcx.json` (deterministic, zero LLM) | ~0 |

*One Grok web-search call covers ALL selected researched sections for a
member — cost does not scale with add-on count. Weather-only briefs skip
the LLM entirely (measured data spoken verbatim).

Rules that bind:

- **Defaults preserve pre-add-on behavior**: a member who never touched
  the toggles gets weather + local news + events on the local tier and
  nothing extra on the base tier. A saved empty list is a real "no
  add-ons" choice, distinct from never-saved (Worker keeps them apart:
  absent field vs `[]`).
- **Tier gating is server-side twice**: the Worker only stores ids from
  the closed set, and `PersonalSpec.effective_addons()` re-filters by
  tier at build time — a base-tier record can never buy a local brief by
  writing addons into KV.
- **Honesty per section**: an unverifiable requested section is silently
  omitted; a day with nothing verifiable and no weather SKIPs the brief.
  Never filler. The markets line reads the committed price caches and
  emits nothing when they're missing — never an invented number.
- **SPCX is spoken "Ess Pee See Ex"** in the markets line — the spaced
  "S P" bigram regresses to "S&P" under Grok TTS text normalization
  (Aug 29 landmine).
- The dashboard's location field is free-text — "wherever you choose",
  not billing address; Open-Meteo geocodes it. Multiple locations per
  feed is roadmap, not yet schema.

## Soft Personal interest (`/personal-interest.html`)

Sep 2026 (SpaceX Daily hero funnel): optional email capture for Personal
tips or a reminder — **not a waitlist, not paid checkout**. Copy SoT is
the Wed Clip 3 Soft Personal section (curiosity, not scarcity; all 18
shows stay free; no episode totals).

- Page: `templates/personal_interest_page.html.j2` →
  `/personal-interest.html` (also linked from `/join.html`).
- Submissions: `POST https://api.nerranetwork.com/api/subscribe` with
  `list: "personal-interest"` (Worker tags
  `personal-interest` + `nerra-member` + `gallery-subscriber`, plus
  `src-nerranetwork`). Optional newsletter checkbox adds the closed
  show tag `SpaceX Daily`. Optional first name is stored as Buttondown
  subscriber metadata. Honeypot field `company` is silently discarded.
- Founder filter: Buttondown tag `personal-interest`.
- Paid path stays on `/join.html` ("Or start Personal now →").

Deploy note: the HTML ships with the site; the new Worker list needs a
`wrangler deploy` of `workers/gallery` before submissions land on the
new tag (unknown lists fall back to `gallery`).

## Donations (`/support.html`)

Cost-transparency page (the honest-ledger pitch: ~$120/month runs the
whole network) + Stripe Payment Links for monthly/one-time donations.
It is also the target of every feed's `podcast:funding` tag — Apple and
every Podcasting-2.0 app render that as the show's **Support** button,
the highest-intent surface the network has. Donations are ordinary
income, not charitable — the page's fine print says so.

## Operator checklist (one-time)

Cloudflare (from repo root, per the wrangler.toml comments — do NOT
uncomment bindings before the resources exist):
1. `workers/gallery/node_modules/.bin/wrangler kv namespace create gallery_rate_limits`
   → paste the id into wrangler.toml's KV block and uncomment.
2. `wrangler r2 bucket create nerra-personal` → uncomment the
   `PERSONAL_BUCKET` block.
3. Secrets: `wrangler secret put STRIPE_WEBHOOK_SECRET`,
   `wrangler secret put PERSONAL_ADMIN_TOKEN` (any long random string),
   `wrangler secret put MEMBER_BOOK_CODE`.
4. `wrangler deploy` from `workers/gallery/`.

Stripe (dashboard, ~15 min):
5. Products + **Payment Links**: Personal $4.99/mo (link metadata
   `tier=personal`), Personal News Network $8.99/mo
   (`tier=personal_local`),
   Donate monthly (open amount), Donate one-time (open amount). Enable
   the customer portal for self-serve cancellation.
6. Webhook endpoint `https://api.nerranetwork.com/api/stripe/webhook`
   with events `checkout.session.completed`,
   `customer.subscription.deleted` → its signing secret is step 3's
   `STRIPE_WEBHOOK_SECRET`.
7. Put the four link URLs in the site-generation environment
   (`STRIPE_LINK_PERSONAL`, `STRIPE_LINK_PERSONAL_LOCAL`,
   `STRIPE_LINK_DONATE_MONTHLY`, `STRIPE_LINK_DONATE_ONCE` — GitHub
   Actions vars used by nightly/finalize `generate_html`); until set,
   the pages render honest "launching soon" states.

Batch host:
8. A small VPS (or private-repo Actions) with this repo, ffmpeg, and
   env `GROK_API_KEY`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`,
   `R2_SECRET_ACCESS_KEY`, `PERSONAL_R2_BUCKET=nerra-personal`,
   `PERSONAL_ADMIN_TOKEN`; cron
   `python scripts/build_personal_feeds.py --fetch`.
   Live host: the private repo `Planetterrian/nerra-personal-batch`
   (`.github/workflows/personal-feeds.yml`), which checks out this repo.
8b. **Punctuality (Sep 14 2026).** GitHub delivers `schedule` events
   hours late (the batch repo's 12:30 UTC cron ran 16:30-18:09 UTC every
   day of Sep 7-14, so a subscriber's edition landed at lunchtime while
   Nerra Daily, driven by the exact-time scheduler Worker, was out by
   ~5:40am Pacific). The edition workflow (`nerra-daily.yml`, step "Wake
   the Nerra Personal build") now dispatches the batch build the moment
   the edition publishes, gated on the edition having been published by
   that very run. It needs one secret in THIS repo:
   `PERSONAL_BATCH_DISPATCH_TOKEN` = a fine-grained PAT (Settings →
   Developer settings → Personal access tokens → Fine-grained), repository
   access **only `nerra-personal-batch`**, permission **Actions: Read and
   write**, 1-year expiry. Without it the step warns and no-ops and the
   batch repo's own off-peak sweep crons (13:41 / 16:41 UTC) still ship
   the edition, just late. The builder skips subscribers already built
   for the date, so dispatch + sweep never double-publish.

Store:
9. Create the member discount code in the book store matching
   `MEMBER_BOOK_CODE`.

## Launch marketing (already wired)

- Footer on every page: join link + account link after signup.
- `podcast:funding` on every feed → `/support.html` → cross-sells
  membership.
- `/join.html` and `/support.html` in the sitemap; `account.html`
  deliberately not (console, not content).
- Natural next steps (not in this pass): a Mira spoken mention in the
  network outro rotation (audio — landmine #17, operator A/B), a
  newsletter launch announcement, Nerra Daily blog cross-links.

## First edition in minutes, and the polish pass (17 Sep 2026)

**On-demand builds.** A new subscriber used to wait for the next batch
run to hear anything. Now `checkout.session.completed` dispatches the
batch workflow for that one member (`inputs.only=<feed token>`, starter
lineup until they choose shows), and the account page's "Build my
edition now" (`POST /api/account/rebuild`) re-makes today's edition
after a lineup / city / topic change — `REBUILDS_PER_DAY` (2) times a
day; the first build of a day is free. The builder's `--only` and
`--replace` flags are the contract: a replaced day keeps its episode
number and GUID (no duplicate in the app), gets an `_rN` filename so
cached audio is re-fetched, and the superseded MP3 is deleted.
`GET /api/account` now carries `member.today` (`built_at`, `building`,
`rebuilds_left`, `available`).

Secret: `GITHUB_DISPATCH_TOKEN` on the Worker (`wrangler secret put`),
the same fine-grained PAT as step 8b (repo `nerra-personal-batch`,
Actions: Read and write). Without it the route answers 503, the page
hides the button, and activation falls back to the morning sweep.

**Polish.** Every cached segment is measured (`ffmpeg ebur128`) and
statically levelled to the network's -16 LUFS when a show drifts more
than 1.5 LU — on 2026-09-17 nine shows sat within ±0.4 LU and
Unintended Consequences at -25.3 (its voice-only path skips the final
loudnorm; fix upstream too). A -18 dB two-tone chime precedes each of
Mira's hand-offs and her sign-off. The feed carries the subscriber's
own artwork (`cover.jpg`, network cover + name band, re-rendered when
name or city changes), timestamped episode notes as `content:encoded`
naming the outlets each brief credits, and `<podcast:transcript>` in
JSON and VTT built from Mira's text plus the shows' committed Whisper
transcripts (offset to the edition timeline, cut where the audio is).

## Personal News Network (13 Sep 2026)

Two paid tiers, same add-ons, different depth. Internal tier ids are
unchanged (`personal`, `personal_local`); only the names people see moved.

| | Personal $4.99 | Personal News Network $8.99 |
|---|---|---|
| Location add-ons (weather, news, events, transit) | the taster: **one** city, **one** item per section | up to **three** cities, up to **three** items per section |
| Your topics (member-named subjects, one item each, sourced) | — | up to five |
| Mira's upgrade nudge | Mondays only, only on a day the taster ran, fixed copy (`upgrade_nudge_line`) | — |

The Worker stores up to the top tier's counts whatever the plan (an
upgrade applies what the member already typed); `validate_spec` enforces
the member's real tier — the builder is the trust boundary, as for add-ons.
Limits live in `engine.personal_edition.TIER_LIMITS` and are mirrored as
`CITIES_MAX` / `TOPICS_MAX` / `TOPIC_MAX` in the Worker (drift-guarded).

Both prompts (`nerra_personal_local.txt`, `nerra_personal_topics.txt`)
require every item to name its source aloud; a generic attribution
("local event guides", "reports say") is forbidden, and
`generic_attributions()` logs any that slip through. Plan switching goes
through Stripe's customer portal from the account page (never a second
checkout); `customer.subscription.updated` moves the tier and keeps the
feed token.
