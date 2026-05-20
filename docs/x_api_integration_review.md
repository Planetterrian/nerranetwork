# X API Integration Review — Tesla Shorts Time & Network Pipeline

**Date:** 2026-04-22
**Scope:** Assess current X post ingestion, what changed in the X developer
platform, and what to update in the Nerra Networks pipeline to fetch the
last-24-hour posts efficiently and reliably.

---

## 1. TL;DR

Today the pipeline does **not** talk to the X API at all. `engine/fetcher.py`
→ `fetch_x_posts()` delegates to xAI Grok's `x_search` tool and asks Grok to
hand back POST_TITLE/POST_TEXT/POST_URL blocks in free text. That works, but
it's slow, expensive, and prone to hallucinated URLs. X's own developer
platform — now on a pay-per-use model as of Feb 6, 2026 — makes it cheaper
and more reliable to call the native endpoints for this specific job.

Moving the account-timeline fetch to the native X API will cost roughly **$3–6
per month** for Tesla Shorts Time at current volume, eliminate hallucinated
URLs, and give you structured post metadata (engagement, verified author,
media, timestamps) to rank by. The current Grok path should stay as a
fallback for "last 24 hours" broad search on slow-news days.

---

## 2. Current pipeline state

What actually runs today:

- `shows/tesla.yaml` declares three accounts under `x_accounts:` —
  `sawyermerrit` (max 5), `tslaming` (5), `wholemarsblog` (3).
- `run_show.py` (~L446–450) calls `engine.fetcher.fetch_x_posts(config.x_accounts, keywords=config.keywords)`
  in parallel with the RSS fetch.
- `engine/fetcher.py` `fetch_x_posts()` builds a prompt like
  `"from:@sawyermerrit recent posts last 24 hours"`, calls
  `digests.xai_grok.grok_generate_text(prompt=..., enable_x_search=True,
  max_turns=3)`, then regex-parses structured blocks.
- The parsed posts are merged into the RSS article list by `run_show.py`
  (~L495–498) with a 0.65 similarity dedup threshold.
- Diagnostic: `scripts/inspect_x_fetch.py tesla` prints exactly what came
  back.

The `XAccountConfig` dataclass lives in `engine/config.py` (fields: `handle`,
`label`, `max_posts`). No native-API client exists anywhere in the repo;
no `X_API_BEARER_TOKEN` or OAuth 2.0 env var is referenced.

---

## 3. What changed on the X developer platform

Confirmed against `docs.x.com` on 2026-04-22:

- **Pay-per-use is now the only sign-up path.** As of 2026-02-06, new
  developers cannot buy Basic or Pro monthly subscriptions. Legacy
  subscribers can keep them, but switching to pay-per-use is a one-way
  door.
- **Posted prices (pay-per-use):**
  - Post reads: **$0.005** per resource
  - User reads: **$0.010** per resource
  - Owner reads (reading posts from the account the app is registered to):
    **$0.001** per post
- **24-hour deduplication window.** Requesting the same post/user within a
  rolling 24h UTC window is charged once. This matters when multiple shows
  pull the same @sawyermerrit posts on the same day.
- **App-context rate limits (15-min window) that matter for us:**
  - `GET /2/users/:id/tweets` — 10,000/15min
  - `GET /2/tweets/search/recent` — 450/15min (7-day search window)
  - `GET /2/users/by/username/:username` — standard (used once per account,
    then cache the user ID)
- **Free tier** is effectively gone for new apps — restricted to "public
  utility" use cases on a case-by-case basis.

There's a **2M post reads/month** pay-per-use cap — wildly above our needs,
but noting it so you don't hit a surprise ceiling.

---

## 4. Why the current Grok-based path has problems

1. **Hallucinated URLs.** LLMs inventing plausible-looking
   `https://x.com/sawyermerrit/status/…` IDs is a known failure mode. Any
   listener who clicks a fake link in the show notes/blog hits a 404 or,
   worse, lands on an unrelated post.
2. **No structured metadata.** The Grok prompt returns title/text/URL, so
   there's no way to rank by engagement, verify the author is the real
   account (vs. a screenshot quote), filter out replies, or detect quote
   tweets programmatically.
3. **Freshness is advisory, not enforced.** "Last 24 hours" is the LLM's
   interpretation of its own tool output; nothing enforces it. Spot-checking
   older `fetch_x_posts` output in `summaries_tesla.json` will probably turn
   up the occasional day-old or older post.
4. **Inference cost.** Each account fetch is a Grok-4 reasoning call with
   `max_turns=3` — several seconds and real tokens per account. At 10 shows
   × 3 accounts × daily runs, the inference spend adds up.
5. **Silent failure mode.** `fetch_x_posts` already logs an
   `ERROR "X fetch produced 0 posts from N account(s)"` when all accounts
   return empty — but the pipeline still runs because RSS carries it. A
   misconfigured Grok key or a model refusal can cause weeks of empty X
   contribution before anyone notices in `management.html`.

---

## 5. Recommended architecture

Two independent capabilities, both backed by the native X API, with the
Grok path reduced to a fallback:

### 5a. `engine/x_api.py` — new native-API client

Responsibilities:

- Auth with OAuth 2.0 **App-Only Bearer Token** (read-only; no user
  context needed for public posts).
- `get_user_id(username)` — `GET /2/users/by/username/:username`,
  memoized in a JSON cache at `digests/_cache/x_user_ids.json` so we pay
  the $0.010 user read once per handle, not once per run.
- `get_recent_tweets(user_id, since)` — `GET /2/users/:id/tweets` with:
  - `max_results=20` (tune per-show via YAML)
  - `start_time=<24h ago ISO>`
  - `exclude=retweets,replies`
  - `tweet.fields=created_at,public_metrics,entities,referenced_tweets,lang`
- `search_recent(query, since)` — `GET /2/tweets/search/recent` for
  broad-topic, last-24h sweeps (e.g. `(Tesla OR TSLA OR Cybertruck) lang:en
  -is:retweet -is:reply min_faves:50`).
- Returns dicts matching the existing `fetch_rss_articles()` shape so
  downstream dedup/ranking doesn't change, plus two extra keys:
  `engagement` (likes + retweets) and `is_verified_author`.
- Rate-limit aware: respect `x-rate-limit-remaining` / `reset`; sleep on
  429.
- Consumption-aware: log the post-read count per run so the dashboard can
  flag budget drift.

### 5b. Keep Grok `x_search` as the fallback

- If `X_API_BEARER_TOKEN` isn't set **or** the native call raises after
  retries, `fetch_x_posts()` falls through to the current Grok path.
- That keeps the pipeline resilient across tokens expiring or X API
  outages, and avoids blocking shows that haven't been migrated yet.

### 5c. Expand `tesla.yaml` (and the network-wide defaults)

Add a new optional `x_search_queries` section to the schema (next to the
existing `web_search_queries`). For TST:

```yaml
x_search_queries:
  - query: "(Tesla OR TSLA OR Cybertruck OR Robotaxi) lang:en -is:retweet -is:reply min_faves:100"
    label: "Tesla broad"
    max_results: 15
  - query: "(FSD OR \"Full Self Driving\" OR Optimus) from:elonmusk OR from:Tesla OR from:tesla_ai"
    label: "Official Tesla"
    max_results: 10
```

This unlocks the "relevant last-24h posts" use case you asked about —
right now the pipeline only knows about three specific handles.

---

## 6. Config + secret changes

New environment variables (add to `.env.example` and GitHub Actions
secrets):

| Variable | Purpose | Scope |
|---|---|---|
| `X_API_BEARER_TOKEN` | OAuth 2.0 App-Only Bearer for public read endpoints | Global (all shows) |
| `X_API_APP_ID` | App ID, for logging / dashboard attribution | Global |
| `X_API_MONTHLY_BUDGET_USD` | Soft cap used by the dashboard to flag overruns | Global (optional) |

No new OAuth user-context tokens are needed — we already post via
`engine/publisher.post_to_x()` using the per-account `X_*` /
`PLANETTERRIAN_X_*` OAuth 1.0a secrets you already have. The read path
is strictly App-Only.

Update `docs/env_var_inventory.md` and the dashboard's secret-drift table.

---

## 7. Cost estimate

TST-only, current volume, native-API path:

| Line item | Reads/mo | Unit | Subtotal |
|---|---|---|---|
| Account timelines (3 × ~5 posts × 30d) | 450 | $0.005 | $2.25 |
| User-ID lookups (cached) | ~3 | $0.010 | $0.03 |
| Broad Tesla search (~15 hits × 30d) | 450 | $0.005 | $2.25 |
| **TST total** |  |  | **≈ $4.50/mo** |

Network-wide: today **only `tesla.yaml` declares `x_accounts:`** (confirmed
via grep). If you extend X ingestion to OV, FF, PT, EI and add broad-search
to TST/EI, a reasonable upper bound is:

- ~2,500 post reads/mo × $0.005 = **≈ $13/mo**
- 24h dedup further cuts this when shows overlap (e.g., Tesla broad search
  might hit the same post in TST and the EV industry segment of EI).

For reference, a Grok-4 reasoning call runs a few cents per fetch today;
across the same network that's an order of magnitude more, before counting
the extra latency cost.

---

## 8. Migration plan (suggested ordering)

1. **Spike — one show, one endpoint.** Write `engine/x_api.py` with
   `get_user_id` + `get_recent_tweets` only. Wire a feature flag into
   `fetch_x_posts()`: if `X_API_BEARER_TOKEN` is set, try native and fall
   back to Grok on exception. Run manually against `shows/tesla.yaml` via
   `scripts/inspect_x_fetch.py tesla` and compare output side-by-side with
   the Grok path.
2. **Add consumption logging.** Record per-run post-read counts in
   `digests/_cache/x_usage_YYYY-MM.json`. Surface in the existing
   `management.html` as a new card ("X API usage this month").
3. **Add `search_recent`.** Same module, different endpoint. Extend the
   YAML schema (`x_search_queries`). Roll out to TST first.
4. **Network rollout.** Only `tesla.yaml` has `x_accounts:` today. If you
   want X content in OV, FF, PT, EI, etc., add an `x_accounts:` (or
   `x_search_queries:`) block to each show's YAML and roll out one at a
   time.
5. **Sunset the Grok path.** Once native has ≥2 weeks of clean runs,
   demote the Grok path to "emergency only" and drop the per-account
   prompt entirely. Keep `grok_generate_text` for the existing web-search
   use cases.
6. **CLAUDE.md + tests.** Update the architecture section + add a unit
   test with a recorded `responses` or `vcr` fixture for the X API
   client. No live API calls in CI.

---

## 9. Verification checklist before merging

- [ ] `X_API_BEARER_TOKEN` present in GitHub Actions secrets and in
      `.env.example`.
- [ ] `scripts/inspect_x_fetch.py tesla` output shows 100% real URLs
      (spot-check by clicking; ideally assert programmatically against
      `GET /2/tweets/:id`).
- [ ] One full TST run end-to-end with native-API path, X posting
      disabled (`--skip-x`), and diff'd transcript against a Grok-path
      baseline from the same morning.
- [ ] 24h dedup visible — run the fetcher twice in quick succession and
      confirm X-Ratelimit usage only ticks on the first run.
- [ ] Rate-limit / 429 handling smoke-tested (mock a 429 response and
      verify the sleep+retry path).
- [ ] Management dashboard card renders a non-zero post-read count for
      the day.

---

## 10. Open questions for you

1. **Which X dev account?** Are you on a legacy Basic/Pro subscription, or
   already on pay-per-use? If legacy, you have a decision to make — staying
   on $100/mo Basic is almost certainly worse economics than pay-per-use at
   your volume, unless you expect to 10× usage.
2. **Broad-search scope.** Besides the three existing handles, which
   accounts/queries should the "last 24 hours" search cover? I drafted
   defaults above — happy to tune once I can see the console and any
   saved searches.
3. **Show-notes vs. script inclusion.** Should native-API posts be quoted
   directly in the podcast script, or only in the blog/show-notes?
   Quoting in audio raises the bar for URL accuracy even higher (listeners
   can't click, they'll look it up later).

Once access to Chrome or Safari is granted, I can open the developer
console and fill in the concrete answers to (1) and (2) — including
whether your current project has the right access levels set.
