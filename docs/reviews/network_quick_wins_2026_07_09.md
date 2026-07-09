# Nerra Network Quick Wins Review — July 9, 2026

Full site + pipeline + workflow + website review focused on **sizeable,
noticeable impact for current and prospective users** (listeners, newsletter
subscribers, web visitors). Editorial/prompt A/B items (landmine #17) are
listed under Operator items — **not applied**.

Drift guards: `tests/test_network_quick_wins_2026_07_09.py`.

## Verdict

The production stack is mature (15 shows, Podcasting 2.0 RSS, AI disclosure,
gallery, multilingual tracks, YouTube rollout). The biggest user-facing gaps
were **discovery and conversion surfaces that drifted when new shows launched**
— footer newsletter stuck at 11 shows, search URLs 404ing, Start Here / FAQ /
player / how-to-listen missing DP Pod / SpaceX / First Principles / Age of AI,
Age of AI blog 404s sitewide, and homepage episode cards that couldn't deep-link
into articles. All of those are **site/workflow-only** and ship in this pass.

## What's already strong (verified)

- Unified `run_show.py` + YAML configs; recovery PRs on push failure; daily
  audit with auto-retry; shallow clones.
- RSS: OP3 enclosures, hook titles, chapters/transcript reinjection,
  `podcast:funding` / `person` / `locked`, AI disclosure.
- Trust: AI badge, ai-disclosure.html, Consent Mode v2.
- Discovery assets exist: gallery (2,396 images), story trackers, data hub,
  global search UI, popular-episodes rail (when OP3 is fresh).
- Multilingual FR/RU/ES/ZH feeds + how-to-listen language links.

## Bugs found (with evidence)

| Bug | Evidence | Impact |
|-----|----------|--------|
| Footer newsletter hardcoded 11 shows | `templates/base.html.j2` checkboxes; missing SpaceX, FPD, DP Pod, Age of AI | Every non-homepage page blocked signup for 4/15 shows |
| Search index hyphenated blog slugs | `scripts/build_search_index.py` `replace('_','-')` vs real `blog/omni_view/` | Search results 404 for most shows |
| Search legacy fallback incomplete | `assets/js/search.js` LEGACY_ENDPOINTS | Fallback missed 5 shows |
| Player + How to Listen stale | Not in nightly `--network`; player said "13 shows", no `dp_pod` | New flagship show invisible on primary listen surfaces |
| Start Here omitted 4 shows | `start_here.html.j2` slug filters | Onboarding never guided visitors to SpaceX / FPD / DP Pod / AOAI |
| FAQ claimed even/odd cadence | `faq.html.j2` JSON-LD + body | Wrong expectations → subscribe-then-churn |
| About promised a removed quiz | `about.html.j2` | Trust friction on primary CTA |
| Age of AI "Read Blog" → 404 | `blog/age_of_ai/` empty (`.gitkeep` only); nav/sitemap linked index | Sitewide broken links + guest apply orphaned |
| Homepage cards not clickable | `network_page.html.j2` latest/popular | Discovery dead-end after sampling audio |
| Hardcoded "900+" episode count | Template ignored `total_episodes` | Under-sold the catalog |
| Daily audit missed SpaceX + DP Pod RSS | `daily-audit.yml` FEEDS dict | Stale feeds wouldn't page |
| Stale "Most Played" rail | `op3_stats.json` `fetched_at` 2026-06-30; no freshness gate | Misleading favorites when token unset |

## Shipped in this pass ✅ (all site/workflow — no audio)

1. **Footer newsletter** loops `{% for s in all_shows %}` with `newsletter_tag`.
2. **Search index URLs** keep underscores + zero-pad `epNNN.html`.
3. **Search legacy fallback** adds spacex / first_principles / dp_pod /
   age_of_ai / models_agents_beginners.
4. **Start Here** adds SpaceX, First Principles, DP Pod, Age of AI + guest
   apply card.
5. **FAQ schedule** rewritten to daily / weekdays / odd / even / interview-ready.
6. **About CTA** copy fixed (no quiz).
7. **Homepage**: dynamic episode count, ticker + about copy for new shows,
   clickable latest/popular cards with "Read article →".
8. **Age of AI**: show hero promotes Apply; empty blog index CTA to apply;
   generated `blog/age_of_ai/index.html`.
9. **Data hub**: Story Trackers card + links to all narrative pages.
10. **Nightly maintenance** regenerates `--player`, `--how-to-listen`,
    `--start-here`, `--faq`, `--about` and commits those HTML files.
11. **CLI flags** `--how-to-listen` / `--start-here` / `--faq` / `--about`.
12. **Daily audit** FEEDS includes `spacex_podcast.rss` + `dp_pod_podcast.rss`.
13. **Popular rail freshness**: hide when OP3 `fetched_at` > 8 days;
    `blog_url` on popular episodes.
14. **Regenerated** index / player / how-to-listen / start-here / faq / about /
    age-of-ai / data.html / age_of_ai blog index so the fix is live on merge
    (not waiting for nightly).

## Recommended next (not implemented)

| Priority | Item | Why deferred |
|----------|------|--------------|
| P1 | Blog index pagination (Tesla ~280 cards) | Template + URL design; still open from June website review |
| P1 | Homepage gallery rail (3–4 images → /gallery) | Design taste; footer link exists |
| P1 | Apple/Spotify listing URLs for SpaceX + DP Pod | Needs directory submissions (operator) |
| P2 | Russian hub rebuild on `base.html.j2` | Translation quality = operator |
| P2 | Hero inline CSS → `styles/main.css` | Perf refactor; verify on devices |
| P2 | Published-feed audit in `feed-audit.yml` | Today audits input news sources only |
| P2 | Recovery-PR webhook: "RSS subscribers won't see this until merge" | Operator notification copy |

## Operator items (human decision / credentials)

1. **Deploy Cloudflare exact-time scheduler** (`workers/scheduler/`) — GitHub
   crons still 1–6h late until deployed (landmine #24).
2. **Set / refresh `OP3_API_TOKEN`** — popular rail is currently hidden by the
   new freshness gate (stats from 2026-06-30).
3. **Merge open `recovery/*` PRs** — stranded commits = RSS subscribers miss
   episodes even when R2/YouTube already have audio.
4. **Apple/Spotify URLs** for SpaceX Daily + The DP Pod in `network_meta.yaml`.
5. **YouTube Studio**: flag podcast playlists for shows added in the June
   rollout (landmine #15).
6. **Gallery Worker secrets** (JWT / Buttondown / Resend) for email-gated
   downloads.
7. **Prompt de-seeds** from `docs/reviews/network_review_2026_07_02.md`
   (OV/EI/MAB/FP/MIT/SpaceX tics) — A/B-listen required; not applied here.
8. **Age of AI pre-launch**: keep apply-forward UX (shipped) vs hide from
   network grid until first episode.

## Method

Read-only audits of templates, `generate_html.py`, workflows, RSS/newsletter/
YouTube/multilingual surfaces, plus prior reviews
(`docs/website_review_2026_06_10.md`, `docs/network_review_2026_06.md`,
`docs/reviews/network_review_2026_07_02.md`, `docs/workflow_review_2026_06_10.md`).
Implemented only high IMPACT × EASE items that are site/workflow-only.
