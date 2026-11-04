# Audience-growth pass (June 2026; Jul 25 nightly-fetch hardening)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Audience-growth pass (June 2026)

Full network review + growth implementation —
[`docs/network_review_2026_06.md`](docs/network_review_2026_06.md) is the
canonical writeup (market analysis, first real audience numbers, roadmap,
operator checklist). Shipped, all no-ops when secrets unset:

- **Audience read-back.** `scripts/fetch_op3_stats.py` (needs
  `OP3_API_TOKEN`) + `scripts/fetch_buttondown_stats.py` run in nightly
  maintenance before the dashboard build → `api/op3_stats.json`,
  `api/buttondown_stats.json`, public `site/data/popular_episodes.json`.
  Surfaces: dashboard "Audience" card, homepage "Most Played This Week"
  rail, homepage "Join N+ readers" social proof (hidden < 100 subs).
  OP3 response shapes are pinned in `tests/test_op3_stats.py` — verified
  live June 2026 (`monthlyDownloads`/`weeklyDownloads`; episode
  `downloads1/3/7/30/All` keys are OMITTED when the data span is young).
  **July 25 2026 nightly-fetch hardening** (drift guards:
  `tests/test_connector_budget.py`; contract:
  [`docs/analytics.md`](docs/analytics.md)): a live run surfaced two
  issues the JSON outputs had been hiding. (1) The Spotify step ran for
  **over an hour** — `spotifyconnector` retries a failing endpoint 6×
  with unbounded exponential backoff (~124 s each), and a registered
  feed with no plays yet answers `500` on `/metadata` + `/aggregate`
  *every* night (18 of 24 feeds were in that state, ~32 dead endpoints).
  New `engine/connector_budget.py` clamps the connectors' retry
  constants (3 attempts / 1 s base ≈ 6 s per dead endpoint, measured)
  and adds a wall-clock budget (`SPOTIFY_/APPLE_FETCH_BUDGET_SECONDS`,
  default 900 s) as the backstop; unreached shows keep their previous
  entry tagged `not_refreshed_this_run`, so a budget stop never shrinks
  the file. Applied to the Apple fetcher too (its constant is
  `MAX_RETRY_ATTEMPTS`, not `MAX_REQUEST_ATTEMPTS` — a copy-paste would
  clamp nothing). (2) **Age of AI's enclosures carried no OP3 prefix**:
  the prefix is applied by each publish path, never by
  `update_rss_feed`, and the Nerra Voices publisher
  (`pipelines/voices/publish_episode.py`) bypasses run_show — so its
  downloads were invisible. Fixed for new episodes; the published Ep001
  URL is deliberately left unprefixed (rewriting a live enclosure
  re-downloads it for every subscriber). Any future show that bypasses
  run_show must apply the prefix in its own publish step. The `dp_pod` /
  `age_of_ai` OP3 **404s are an indexing lag**, not a bug — OP3's docs
  define 404 as "OP3 doesn't know about the show"; downloads attach
  retroactively once it indexes the feed. A 404 persisting for weeks
  means check the prefix first.
- **Adjacency-map bug fixed.** `newsletter.network_adjacencies` (and the
  other newsletter composition keys) had been mis-indented under
  `cost_circuit_breakers:` in `shows/_defaults.yaml` — newsletter +
  synthesizer read an empty map, so the cross-network email module was
  silently degraded network-wide. Drift guard pins the location. NOTE:
  there are deliberately THREE curated cross-show mappings — web
  (`generate_html.NETWORK_SHOWS[slug]["related_show"]`), email
  (`newsletter.network_adjacencies`), audio/X
  (`engine/network_promo.ENGLISH_SHOWS`). Do not consolidate casually;
  each is tested and serves a different surface.
- **Newsletter growth loop.** Every show now gets a deterministic
  Buttondown slug (`<show>-ep<num>-<hook>`; was Russian-only) so the
  view-in-browser/archive link renders pre-send on dailies AND weeklies;
  reply/share row gained a localized "Forwarded this email? Subscribe
  here" line (UTM `forward_subscribe`).
- **X cross-promo reply.** Flag `publishing.x_cross_promo` (network
  default true in `_defaults.yaml`, dataclass default false) posts a
  second tweet threaded under the teaser: "Follow @{x_handle}" + one
  sibling plug from the `network_promo` rotation. `x_handle` set only for
  tesla/@teslashortstime + the PLANETTERRIAN_X_ shows/@planetterrian;
  OV/M&A/MIT pending operator confirmation. Roughly doubles posts/day per
  X app — flip the flag off if the free-tier cap trips.
- **Podcasting 2.0 channel tags.** `update_rss_feed` now injects
  `podcast:funding` (→ `/#newsletter`) + `podcast:person` (host) on every
  rebuild via `_inject_channel_funding_person_tags` (same pattern as
  `podcast:locked`); empty kwargs = byte-for-byte legacy behavior.
- Sitemap: + `player.html` + `modern-investing-performance.html`,
  − `404.html`. Nightly site-regen step now passes the marketing env vars
  (was silently stripping analytics tags on nightly rebuilds).
- **Known wart (operator decision pending):** Russian shows speak the
  ENGLISH `_AI_DISCLOSURE` line at the end of every episode; a localized
  `_AI_DISCLOSURE_RU` is a one-liner in `run_show.py` but changes shipped
  audio → landmine #17 A/B-listen first.
