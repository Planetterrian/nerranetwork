# Nerra Network — Full Network Review & Growth Plan (June 2026)

A full review of the codebase, website, workflows, pipelines, and the market
the network operates in, with a prioritized plan to increase audience value
and position the network for growth. Produced June 10, 2026 alongside an
implementation pass (see "What shipped with this review" below).

---

## 1. Executive summary

The network is **production-mature and remarkably cheap to run** — twelve
shows, ~10 episodes/day, 100% pipeline success over the trailing week,
broadcast-quality audio, ~$0.07–0.21 marginal cost per episode (~$60/month
variable + $150/month Buttondown). Engineering risk is well-managed
(23 documented landmines, drift-guard tests, recovery PRs, multi-source
fallbacks).

The strategic gap is on the **audience side, not the production side**:

1. **The network was audience-blind.** OP3 analytics prefixes have been on
   every RSS enclosure since launch, but the data was never read back. No
   subscriber counts, no web analytics, no download numbers anywhere in the
   repo or dashboards. The Feb 2026 monetization roadmap stalled at exactly
   this step. *Fixed in this pass* — see §6.
2. **The funnel leaked at every stage** — no cross-show discovery loop in
   email (a YAML indentation bug silently emptied the adjacency map), no
   social proof, no view-in-browser/forward path on newsletters, no
   "popular episodes" surface, X teasers with no follow CTA. *Largely fixed
   in this pass.*
3. **Distribution is capped below its potential.** YouTube — the #1 podcast
   discovery surface in 2026 — carries only 2 of 12 shows (API quota).
   IG/TikTok auto-posting is code-complete but waiting on operator app
   registrations. Gallery lead-capture is built but not yet live.

### First real audience numbers (OP3, 30 days to 2026-06-08)

| Show | 30-day downloads | Weekly avg |
|---|---|---|
| Tesla Shorts Time | 616 | 150 |
| Models & Agents | 422 | 100 |
| Models & Agents for Beginners | 235 | 57 |
| Planetterrian Daily | 173 | 41 |
| Fascinating Frontiers | 150 | 35 |
| Modern Investing Techniques | 148 | 36 |
| Omni View | 126 | 30 |
| Привет, Русский! | 77 | 19 |
| Финансы Просто | 64 | 13 |
| Unintended Consequences | 31 | 15 |
| Environmental Intelligence | 24 | 11 |
| **Network total** | **~2,066** | **~507** |

Reading: a real but early-stage audience. Tesla + the two AI shows carry
~62% of listening. The narrative shows (UC, FPD) launched with distribution
off and predictably have near-zero reach. At ~$210/month all-in cost, the
network costs ~$0.10 per download — the economics work at tiny scale, which
is the structural advantage to press.

---

## 2. Market context (June 2026)

- **The AI-podcast flood is the defining market dynamic.** Roughly 35% of
  all new podcast feeds are now AI-generated; one network alone ships 3,000
  episodes/week at <$1/episode. Platforms are responding: Spotify added
  Verified badges and bans voice impersonation; **Apple requires AI
  disclosure in both audio and metadata** when AI generates a material
  portion of audio. Sources: [Eastern Herald](https://easternherald.com/2026/05/04/ai-podcasts-boom-35-percent-machine-generated/),
  [Digital Music News "podslop"](https://www.digitalmusicnews.com/2026/05/04/podslop-ai-podcast-problem/),
  [Variety on Spotify's policy](https://variety.com/2026/digital/news/spotify-bans-ai-generated-podcasts-impersonate-verified-badges-1236752944/),
  [RSS.com AI disclosure guide](https://rss.com/blog/ai-disclosure-in-podcasting-what-it-is-why-it-matters-and-how-to-do-it/).
  **Nerra is already compliant and ahead of the curve**: spoken disclosure
  on every episode, RSS channel+item disclosure, ai-disclosure.html, the
  AI-transparency badge site-wide, and YouTube's syntheticMedia flag. In a
  podslop market, *documented* transparency + longitudinal depth (story
  trackers, narrative memory) is the moat — generic AI news recaps are now
  a commodity.
- **YouTube is the #1 discovery surface**: 1B+ monthly podcast viewers;
  for video-first shows 30–55% of first exposures come from algorithm or
  search; Gen Z discovers via YouTube/TikTok/IG. Sources:
  [The Podcast Host industry stats](https://www.thepodcasthost.com/listening/podcast-industry-stats/),
  [eMarketer](https://www.emarketer.com/content/faq-on-podcasting--video-s-rise--ctv-growth--what-means-advertisers-2026),
  [PodRewind video stats](https://podrewind.com/blog/video-podcast-statistics-2026).
  The 10k units/day quota (landmine #20) limiting video to Tesla+MAB is the
  single biggest distribution constraint.
- **Monetization economics for niche shows** favor engaged audiences over
  scale: direct sponsors $25–40 CPM, memberships $5–10/mo at 2–10%
  conversion, programmatic only $3–15 CPM. Sources:
  [biztoolkit ad rates](https://www.biztoolkit.co/post/podcast-advertising-rates-2026-what-sponsors-actually-pay),
  [RSS.com programmatic](https://rss.com/blog/why-small-podcasts-win-with-programmatic-advertising/).
  At current scale (~500 downloads/week) monetization is premature;
  measurement-first was the right call.
- **Podcasting 2.0 tags have real platform support** (transcript, chapters,
  person, funding). Nerra already shipped transcript+chapters universally;
  funding+person were at zero across all feeds (fixed in this pass).
  Source: [Podcasting 2.0 namespace](https://podcasting2.org/docs/podcast-namespace/1.0).

---

## 3. System review (codebase, workflows, pipelines)

**Strengths worth protecting** (don't churn these):

- Unified runner + YAML config with deep-merge defaults; scaffolded
  new-show creation; per-episode cost tracking with historical pricing.
- Multi-layer quality gates: 14 smoke suites on every run, post-run audit
  with auto-retry, output validation, recovery PRs on push failure.
- Broadcast audio chain (48kHz WAV, sidechain ducking, −16 LUFS) at 36×
  lower TTS cost than the ElevenLabs era.
- Narrative memory / story trackers (Tesla bespoke + generalized engine on
  M&A, FF, PT) — the clearest differentiation vs. commodity AI podcasts.
- Disciplined A/B-listen policy for audio changes (landmine #17) — every
  theory-driven audio "improvement" has regressed; the policy is the guard.

**Top risks** (all previously documented; status confirmed live):

| Risk | Status | Action |
|---|---|---|
| Repo size (#1): 2.2GB+ MP3s in git | Live, ~18–24mo runway | R2 migration for MP3s — already planned in `docs/audio_storage_plan.md`; schedule it |
| YouTube quota (#20): 9,600/10,000 units used by 2 shows | Live | See roadmap §7 — quota increase request + rotation options |
| Grok TTS single-vendor (#17) | Live | Quarterly rollback drill to ElevenLabs (kept configured) |
| Git push transients (#23) | Mitigated (recovery PRs) | None |
| TSLA price chain (#22) | Mitigated (3-source fallback) | None |

**Bug found during this review (fixed):** the cross-network adjacency map
in `shows/_defaults.yaml` was indented under `cost_circuit_breakers:` while
`engine/newsletter.py` and `engine/synthesizer.py` read it under
`newsletter:` — every daily and weekly email's "Across the Nerra Network"
module was silently degraded. Also added the missing
`unintended_consequences` entry, plus drift guards pinning the location.

---

## 4. Audience funnel review (website + distribution)

State at the start of this review, stage by stage:

- **Awareness:** RSS directories ✓, X on 7 shows (single teaser, no follow
  CTA, no cross-promo), YouTube on 2 shows (well-optimized Shorts), no
  IG/TikTok (built, disabled), newsletter (no viral loop).
- **Sampling:** homepage Latest Episodes rail with inline players ✓ (the
  earlier internal review that called it missing was wrong), no
  popularity/social-proof signal anywhere.
- **Conversion:** subscribe buttons ✓, newsletter form ✓ (11-checkbox
  cognitive load, no social proof), gallery email-gate built but secrets
  unset.
- **Retention/deepening:** cross-show recs on web ✓, in email ✗ (the
  adjacency bug), story-tracker pages ✓ but under-promoted, no
  view-in-browser/archive path on emails.
- **Measurement:** none surfaced anywhere (OP3 wired but never read,
  Buttondown count never fetched, GA4/Plausible scaffolded but unset).

Most of the ✗s above are addressed in §6. Remaining structural gaps are in
the roadmap (§7).

---

## 5. Portfolio & editorial review

- **Growth engines (by data, not just intuition now):** Tesla Shorts Time
  (616/mo, YouTube, narrative memory, real-time stock hook), Models &
  Agents (422/mo, AI tailwind, expert positioning), MAB (235/mo, only
  beginner-AI show, YouTube + Education category), Modern Investing
  (148/mo, Canadian niche, investment tracker, monetization-ready
  audience).
- **Solid niches:** Planetterrian, Fascinating Frontiers (narrative memory
  live; YouTube-ready if quota allows).
- **Watch list:** Omni View — the "Steel Man" repositioning (May 2026) is
  the right differentiation but remains unvalidated against output; its
  126/mo is mid-pack despite a broad niche. Env Intel — 24/mo on a B2B
  micro-niche; viable only as a premium/B2B play later. Russian shows —
  small but real (141/mo combined) and structurally underserved niches.
- **New narrative shows (UC, First Principles):** distribution is off/min —
  their evergreen format is exactly what differentiates against podslop,
  but nobody can find them. Cheapest growth lever in the portfolio:
  turn their channels on (UC newsletter+X are now in the cross-promo
  rotation; FPD newsletter/X remain off pending operator call).
- **Format risk:** 7 of 12 shows share the "news + narration" architecture;
  differentiation is topic-only and switching costs are low. The narrative
  memory / story-tracker surfaces are the answer — extend them (MIT's
  investment tracker is already a variant) and promote them.

---

## 6. What shipped with this review (June 10, 2026)

All additive, all clean no-ops when secrets/config are unset, each with
drift-guard tests. Full suite green (2,696 tests).

1. **Adjacency-map bug fix** — newsletter cross-network module restored
   network-wide; `unintended_consequences` added to the rotation; blog
   cross-show recs now deterministically lead with the curated sibling.
2. **OP3 read-back** (`scripts/fetch_op3_stats.py`) — nightly fetch of
   per-show/per-episode downloads → `api/op3_stats.json` (operator
   dashboard "Audience" card) + public `site/data/popular_episodes.json`
   → new homepage **"Most Played This Week"** rail with inline players.
   Initial snapshot committed (the numbers in §1).
3. **Buttondown subscriber count** (`scripts/fetch_buttondown_stats.py`)
   → dashboard + homepage **"Join N+ readers"** social proof (hidden
   below 100 subscribers, rounded down to nearest 10).
4. **Plausible readiness** — nightly site-regen now passes the marketing
   env vars (it previously would have stripped analytics tags nightly);
   enabling analytics is now literally one secret (`PLAUSIBLE_DOMAIN`).
5. **Sitemap hygiene** — player.html + MIT performance page added,
   404.html removed.
6. **Podcasting 2.0 channel tags** — `podcast:funding` (points at the
   newsletter signup; the network's support ask is "subscribe", not
   money) + `podcast:person` (host credit) injected into every feed on
   its next rebuild.
7. **Newsletter growth loop** — deterministic Buttondown slugs for every
   show (was Russian-only) unlock the never-used view-in-browser/archive
   link on every daily + weekly; new localized "Forwarded this email?
   Subscribe here" line with UTM attribution (forwarding is the only
   viral loop email has; Buttondown has no native referral program).
8. **X cross-promo reply** — flag-gated second tweet threaded under each
   daily teaser: "Follow @handle" + one sibling-show plug from the
   deterministic daily rotation, UTM-tagged. Kill switch:
   `publishing.x_cross_promo: false` in `_defaults.yaml`.

---

## 7. Prioritized roadmap (next 1–6 months)

**Near-term, operator-action (see checklist §8):** light up the
measurement (OP3 token, Plausible), confirm X handles, watch the new
funnel surfaces for 2–4 weeks to establish baselines.

**P1 — YouTube expansion (biggest lever, operator decision).**
Options, not mutually exclusive: (a) request a quota increase from
YouTube (audit-based, free; the channel is a legitimate publisher);
(b) drop Tesla/MAB from 2 Shorts to 1 (saves 3,200 units — enough for
two more shows' Shorts-only presence; Shorts are the discovery lever,
long-form converts); (c) day-of-week rotation for the freed slots
(e.g. FF/PT/M&A/MIT each get 1–2 video days/week). Any change requires
updating the `test_only_tst_and_mab_enable_youtube` drift guard
deliberately. The Russian channel (@NerraRU) has its own untouched
quota — FP/PR video is free headroom if those audiences justify it.

**P2 — IG Reels / TikTok enablement.** Code-complete
(`docs/social_distribution.md`); blocked only on Meta/TikTok developer-app
approvals. Start with Tesla. This + P1 is the entire "where Gen Z
discovers podcasts" story.

**P3 — Turn on the narrative shows' distribution.** UC and First
Principles are the most podslop-proof content in the portfolio. FPD:
enable newsletter + add to X rotation after a quality pass on the first
~30 episodes. Consider a `@nerranetwork` umbrella X account if per-show
accounts don't scale.

**P4 — Promote the moat.** Story-tracker pages (tesla-narrative et al.)
are linked from show pages but invisible elsewhere: add them to the
newsletter footer rotation and X cross-promo variants; consider a
"narrative tracker" Shorts format (what changed this month in 60s).

**P5 — Validate Omni View's "Steel Man" claim** — sample 10 episodes
against the May 2026 prompt spec; if balance isn't measurably visible,
either fix sourcing (the Feb audit showed ~40% single-source stories)
or reposition again. A differentiator that isn't real is a liability.

**P6 — Monetization (only after P1–P3 move the numbers).** Thresholds
to act: ~2,000 downloads/week network → Podcorn/affiliate experiments on
MIT (brokers) and M&A (AI tooling); ~5,000/week → direct sponsor
outreach on Tesla/M&A; memberships only with demonstrated superfans
(newsletter reply rate, repeat downloads). The `podcast:funding` tag
currently pointing at the newsletter can be repointed to a support page
in one line when the time comes.

**P7 — Repo size (engineering).** Execute the already-planned R2
migration for committed MP3s before the 10GB wall (~18–24 months out);
it also removes the biggest contributor to push transients (#23).

---

## 8. Operator checklist (things code cannot do)

- [ ] Create an OP3 API token (free, op3.dev/api/keys) → repo secret
      `OP3_API_TOKEN`. Until then the committed snapshot ages.
- [ ] Create a Plausible site → repo secret `PLAUSIBLE_DOMAIN`
      (`nerranetwork.com`). One secret = site-wide analytics.
- [ ] Confirm the live @handle for each X app (`X_*` vs
      `PLANETTERRIAN_X_*`) and fill `publishing.x_handle` for
      omni_view / models_agents / modern_investing (CLAUDE.md's table
      lists @omniviewnews for OV, which contradicts its `X_` prefix).
      Also confirm the X apps' write-tier headroom — the cross-promo
      reply roughly doubles daily posts per app (kill switch in
      `_defaults.yaml` if it trips the free-tier cap).
- [ ] Verify the Buttondown `/v1/subscribers` response on the live
      account (the stats script logs the keys it saw if `count` is
      missing).
- [ ] Gallery Phase 3 go-live: set the four Worker secrets
      (`JWT_SECRET`, `BUTTONDOWN_API_KEY`, `RESEND_API_KEY`,
      `RESEND_FROM_EMAIL`), test the magic-link flow, then link the
      gallery from the newsletter (lead capture).
- [ ] YouTube quota: file the increase request; decide on the
      1-Short/rotation options (P1).
- [ ] Register Meta + TikTok developer apps for social distribution (P2).
- [ ] Spotify "Verified" badge: request via Spotify for Creators for the
      flagship shows (trust signal in the podslop era).
- [ ] Decide on a Russian-localized spoken AI disclosure for Финансы
      Просто / Привет, Русский! — currently the English disclosure
      sentence plays on the Russian Olya voice at the end of every
      episode. One-line fix (`_AI_DISCLOSURE_RU` keyed on
      `config.language` in `run_show.py`) but it changes shipped audio →
      A/B listen first per landmine #17.
- [ ] OP3 caveat: data accrues only from the prefix go-live; no backfill
      exists, so treat early per-episode numbers as directional.

---

## 9. What was deliberately NOT done

- No prompt/editorial changes and no audio-path changes (landmine #17
  A/B-listen policy). The Russian disclosure fix is specced but parked.
- No YouTube quota reallocation (drift-guard-pinned operator decision).
- No monetization surfaces beyond the `podcast:funding` tag (audience
  growth first — the operator's stated priority).
- No show pruning or repositioning (operator chose "grow all 12").
- No consolidation of the three curated cross-show mappings
  (`NETWORK_SHOWS.related_show` for web, `newsletter.network_adjacencies`
  for email, `network_promo.ENGLISH_SHOWS` for audio/X) — three tested
  surfaces, zero audience gain from churning them; documented here
  instead.
