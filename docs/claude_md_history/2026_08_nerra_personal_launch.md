# Nerra Personal — accounts, personalized feeds, donations (Aug 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Nerra Personal — accounts, personalized feeds, donations (Aug 2026)

The member surface (operator-directed). **One identity**: a "Nerra
account" IS the gallery Worker's existing JWT/Buttondown identity —
every newsletter signup (footer + `/join.html` both POST the Worker's
`/api/subscribe`, `list:"member"`; the Buttondown-direct embed form is
GONE) creates an account that unlocks gallery downloads, per-show
newsletter tags (closed `SHOW_NEWSLETTER_TAGS` set in
`workers/gallery/src/handlers.ts`), and member perks
(`MEMBER_BOOK_CODE` book discount). **Paid tier**: a private daily feed
of the subscriber's chosen shows in THEIR order, Mira anchoring by name
($4.99/mo; +city morning brief $8.99/mo — Open-Meteo weather +
one web-search call under the field-note honesty rules).
`engine/personal_edition.py` (closed vocabulary = the EN edition lineup;
kept in sync with the Worker's copy by a drift test) +
`scripts/build_personal_feeds.py` (segments trimmed ONCE/day into a
shared cache — per-user marginal cost ~$0.05-0.07/day; **PII rules: runs
on a PRIVATE host only, specs carry token/name/city never email, logs
truncate tokens**) + Worker endpoints in
`workers/gallery/src/personal.ts` (KV member records, Stripe webhook
mints/revokes feed tokens — cancel = feed 404s immediately; feeds served
Worker-gated from R2 `nerra-personal`, `itunes:block` on).
**Donations**: `/support.html` (cost-transparency pitch + Stripe links);
every feed's `podcast:funding` tag now points THERE (was `/#newsletter`)
— it renders as the Support button in 2.0 apps. Pages
(`join/account/support.html`) regenerate with `--network`/`--all`;
Stripe URLs flow from env (`STRIPE_LINK_*`), unset = honest
"launching soon" states. Everything Worker-side degrades to 503 until
the operator provisions KV + the `nerra-personal` bucket + secrets
(checklist: [`docs/nerra_personal.md`](docs/nerra_personal.md)). Drift
guards: `tests/test_nerra_personal.py`,
`workers/gallery/test/personal.test.ts`.
