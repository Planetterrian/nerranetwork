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
from env): **Personal $4.99/mo**, **Personal + Local $8.99/mo**. Tier is
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

**The local brief** (personal_local tier): Open-Meteo geocoding +
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
   `tier=personal`), Personal+Local $8.99/mo (`tier=personal_local`),
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
