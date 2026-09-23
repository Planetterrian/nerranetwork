# New shows — build plan (22 Sep 2026; fifteenth show added 23 Sep)

**Status:** plan, nothing shipped. Operator-requested. This document is the
spec for every PR in the rollout; each PR links back to the section it
implements and the per-show registration checklist in Appendix A.

**Scope requested:** AI Chips & Data Centres Daily · Vancouver Daily News ·
Collingwood Weekly · Nerra Weekly · Nerra Network Developments · MAG 7
Daily · Peptides Weekly · Longevity Weekly · Omni View North America ·
Omni View Europe · Omni View Asia Pacific · Omni View Central & South
America · Omni View Africa & Middle East · Omni View Top World News.
**Added 2026-09-23 (operator):** Prediction Markets Daily (§4.11).

Everything below was checked against the tree on 2026-09-22 (file:line
references are to that tree) and against a live probe of ~260 candidate
feeds (Appendix B). Where the plan makes a decision the brief left open,
§10 lists it as an operator call with the assumption the plan proceeds on.

---

## 0. Summary

**23 Sep 2026 operator brief — read first.** Three decisions that bind every
remaining phase and change what the Phase 1 shows already do (§9b):
(1) every new show runs **grok-4.7** on its writing stages — the new shows are
the proving ground for the latest model, and what works is carried to the
established shows afterwards under the playbook; (2) every new show leads with
**useful, interesting, timely** developments — never share prices, earnings
calendars or announcements of announcements (MAG 7 Ep1 spent its opening on
seven closing prices and dates a month out); (3) the health shows **teach**
rather than report a drug pipeline. A fifteenth show, **Prediction Markets
Daily**, joins the plan (§4.11).

- **Nine daily and five weekly shows, 12 through `run_show.py` and 2
  assembled.** Nerra Weekly is a registry-only edition on the Nerra Daily
  machinery (no YAML, deliberately, like Nerra Daily). The other thirteen
  are YAML shows; Nerra Network Developments is a YAML show whose
  "articles" are the week's merged PRs, supplied by a hook.
- **Two engine enablers unlock five of the shows and must land first**
  (§2): (a) a hook may supply articles, which today it cannot — the
  `pre_fetch` dict never reaches the fetched list, so the PR-review show,
  the Top World desk, Vancouver traffic and the two health shows' journal
  APIs have no honest path in; (b) an AI host for a `run_show` show — the
  spoken disclosure says "synthesis of *my* voice … analysis *my own*" and
  the RSS line says "curated by Patrick" with no per-show override, the
  speaker-label stripper is case-sensitive, and the newsletter footer is
  hardcoded Patrick. Mira cannot host a news show until those are
  host-aware.
- **A third enabler is strongly recommended:** named-weekday cadence. The
  whole cadence machinery (gate filter, Worker, `review_episodes`, audit
  thresholds, edition roster, the cron-shape test) models only "daily" and
  "Monday". Five new weeklies all on Monday would put twenty shows on one
  morning and make Nerra Weekly a Monday look-back instead of a Sunday one.
- **Distribution is OFF at launch for all fourteen** (RSS + site + blog
  only), the First Principles launch pattern. The EN YouTube channel sits
  at ~24 uploads/day against the 30/day cadence ceiling; nine dailies at
  one Short each would breach it on day one. The Mira desks get their own
  channel later (the dub-channel credential resolver already supports a
  new channel key), decided on data, not at launch.
- **Cost:** ~+$75/month at the launch tier (LLM + TTS + a little search),
  rising to ~+$200/month if every show later gets images, video and a
  French track. Today's tracked burn is ~$160/month plus ~$60 multilingual.
- **Rollout in five phases over ~5 weeks**, Patrick's shows first (no new
  host machinery), then Mira's two local shows as the calibration set for
  the AI-host path, then the six desks, then the two assembled/derived
  shows. Every show launches by manual dispatch, its Episode 1 is
  A/B-listened, and only then does its cron entry land.
- **Design is a strand system, not fourteen new hues.** The palette has 18
  shows in it already and every candidate hue sits within 10° of an
  existing one. New shows get a strand colour family, a per-show accent, a
  cover from one deterministic PIL template (the Nerra Daily "dial"
  approach), and strand badges in the chrome.

---

## 1. What binds this plan (lessons already paid for)

Each item names the mechanism, not the story; the stories are in
`CLAUDE.md` and `docs/show_review_history.md`.

| Lesson | What every new show does about it |
|---|---|
| Titles, funnel ids, provenance each have ONE owner | No new limit, no hand-rolled `utm_*`, no new citation stripper. Claims gate stays `enforce` + `strip` (network default); narrative-shaped shows use `block`. |
| The Ep1 that shipped was retired three times (DP Pod) | Every show gets a designed debut in `engine/first_episode.py` (`_SHOW_DIGEST_EP1` / `_SHOW_PODCAST_EP1`), shape-only, and Ep1 is listened to before Ep2 can run (cron lands after the listen). |
| De-seed by shape; format specs must not read as plausible content | No prompt supplies a quotable sentence, example joke, example action or `**Title: Source Name**` placeholder. Section names are nouns, never sentences. |
| A missing section is a defect (DP Pod Lever) | Every show gets a `SHOW_VALIDATION_CONFIGS` entry AND a `SHOW_SECTION_PATTERNS` entry on day one (DP Pod / Offshore North / FPD lack them). |
| The digest prompt never saw an article (Offshore North) | Weekly shows carry `window_hours: 168–192` per feed and `stale_article_days`; local and campaign-style shows carry `fetch_full_text`. Google News re-surfaces old stories under fresh index dates — every GN query is paired with real publisher feeds. |
| Cadence lives in six places and the public copy drifted | The scaffold prints the cron line only; §6 lists all six places per show and the guard is derived from CRON_MAP. No public string for a weekly show says "daily". |
| A show that bypasses run_show gets none of its publish surface | Nerra Weekly wires OP3 prefix, `_VIRTUAL_COST_SLUGS`, content-lake import and any distribution explicitly. |
| Per-show `min_articles_skip`, never the default | Pinned per show below; the `or 3` bug that turns 0 into 3 is fixed in Phase 0. |
| Same-day sibling overlap (PT/FF; SpaceX/Tesla) | Boundaries are written into the prompts AND enforced data-side where a mechanism exists: MAG 7 vs Tesla Shorts Time, AI Chips vs Models & Agents, Longevity vs Planetterrian, Top World vs the regional desks vs Omni View. |
| Loops on NUMBERS fail silently | Every new per-show data file (`api/mag7_quotes.json`, `api/vancouver_roads.json`, …; never `api/<slug>.json`, which is the per-show public episode API) is whitelisted in BOTH committing workflows and read by a dashboard card or a metric with a named consumer. |
| Model changes follow the playbook | **Superseded 2026-09-23 (operator):** every new show pins `llm.model: grok-4.7` on its writing stages (digest + script, combined generation still on); fetch stays on grok-4.3. It is a named, registered arm (`new-shows-grok-47-2026-09-23`; the guard forbids it growing onto an established show) with latency-first revert triggers — the playbook's staging, applied to shows with no audience history to lose. |
| Feeds from a laptop are not feeds from a runner | Appendix B was probed through this session's proxy; five publishers returned 403 that likely differ on a GitHub runner. Every candidate list is re-graded with `check_feeds.py <slug>` from Actions before Ep1. |
| YouTube cadence, not quota, is the constraint | Off at launch; a second channel for the Mira desks is a data decision (§7). |
| Landmine #17 | Every prompt is A/B-listened on Ep1. Mira on `ara` inherits the `<fast>` wrap tuned on Patrick's voice; the Vancouver Ep1 test renders are made with and without it and the operator picks. |

---

## 2. Phase 0 — shared engineering before any show ships

One PR, ~all tests green, no show enabled. Everything here is used by more
than one new show.

### 2a. Hook-supplied articles

**Today:** `pre_fetch` output goes into `template_vars` / `pod_vars` only
(`run_show.py:1608`, `engine/pipeline.py:451`). It cannot add to
`articles`, so the no-articles skip, dedup, full text, the stale gate, the
`news_section` renderer and `build_local_texts` for the claims gate never
see hook data (`run_show.py:1230-1319, 1476-1494, 2355-2360`).

**Change:** a `pre_fetch` return key `articles: list[dict]` (same shape the
fetcher emits: `title, link, published, source, description, content_text`)
is merged into the fetched list AFTER the RSS ladder and BEFORE dedup, with
`source_kind: "hook"`. Hook articles are exempt from the keyword filter and
from `drop_stale_articles` only when the hook says so per article
(`exempt_stale: true`); they go through everything else, including
`build_local_texts`, so a claim citing a hook article verifies from the
fetched copy without HTTP. Metric: `articles_from_hook`. Guard: a test that
a hook article reaches `news_section` and `local_texts`, and that an
exception in the hook still yields `{}` (existing contract).

Consumers: Nerra Network Developments (PRs), Omni View Top World News
(the five desk digests), Vancouver Daily (DriveBC Open511 road events,
weather), Peptides/Longevity (Europe PMC search JSON).

### 2b. AI host support (Mira on a run_show show)

- **Disclosure lines are host-aware.** `run_show.py:88-123` gains an
  AI-host variant selected by a new `publishing.host_kind: human|ai`
  (default `human`). Spoken: names the host as an AI, says the voice is
  synthesized and the selection automated from named sources, and does
  NOT claim human review — `tests/test_age_of_ai_pass_2026_09_21.py`
  exists precisely to keep the review claim on the two shows that bypass
  run_show. Under 200 chars and containing "synthesis" (both pinned by
  `tests/test_phase3_calibration.py:167-175`). RSS variant likewise;
  `youtube.synthetic_disclosure` is already overridable per show.
- **Speaker-label stripping goes case-insensitive**
  (`run_show.py:5114-5143`): the Age of AI personality uses `MIRA:` and
  `host_name` is `Mira`; today that mismatch is latent only because AoAI
  never runs through run_show.
- **`_SHOW_PERSONALITIES` entries** for every Mira show with
  `host: "Mira"` and the identity tail that discloses the AI on every
  episode (the AoAI pattern). Ep1 falls back to a generic "see you
  tomorrow" closing for a show without an entry (`engine/intros.py:1371`),
  so this is a launch item, not polish.
- **`podcast:person` URL** follows the host: `run_show.py:4306-4307`
  hardcodes `/about.html`; Mira shows point at `/mira.html`.
- **Newsletter chrome** parameterizes "Editorial by Patrick" /
  "Patrick reads every one" (`engine/newsletter_template.py:36-38,
  1396-1399, 1643-1644`) on the show's `host_name` and `host_kind`.
- **Registry `host` key** (`network_meta.yaml`, merged untouched like
  `strand`): `patrick | dan | mira | patrick_dan`. It drives the card
  badge ("Hosted by Mira", `_macros.html.j2:114`, currently keyed on
  `strand == 'mira'`), the "Hosted by …" line in `about_host` defaults,
  and the computed Mira copy below. `strand: mira` stays reserved for the
  three claim-bearing shows: it renders the interview claim band and a
  "Be a guest" button on the show page (`show_page.html.j2:686-699`),
  which a news desk must never carry.
- **Mira copy becomes computed.** `MIRA_SHORT_DESCRIPTION`,
  `MIRA_NETWORK_ROLE` ("three jobs"), `mira_page.html.j2` ("Three jobs, one
  host"), `ai_disclosure.html.j2:41` ("Three shows … are hosted by Mira")
  and the `mira` promo copy all name three shows. They render from
  `host == mira` in the registry after this change. **The claim sentence,
  its basis and `MIRA_SHOW_SLUGS` do not change** — the claim is about the
  guest holding the publish decision, and adding news desks does not
  widen it. `tests/test_mira_pass_2026_09_20.py:227-236` keeps pinning the
  `strand: mira` set to the three.
- **Voice wrap:** Mira shows set the speech wrap explicitly (empty or
  `<fast>`) after the Vancouver Ep1 render comparison; the network default
  is the Patrick-tuned `<fast>` (`_defaults.yaml:114`).
- **Dashboard voice baseline** already sanctions `ara`
  (`scripts/generate_dashboard.py:93-96`); nothing to add unless Mira ever
  gets a custom-trained voice.

### 2c. Named-weekday cadence

Add `monday | tuesday | … | sunday` as filter values everywhere the
existing `monday` filter is understood:

| Place | Today | Change |
|---|---|---|
| `run-show.yml` gate filter (lines 188-215) | even/odd/odd_weekday/weekday/monday | any weekday name |
| `workers/scheduler/src/index.ts` `dayFilterPasses` (47-65) | same | same; SLOTS rows carry the name |
| `review_episodes.py` `SHOW_REGISTRY[*].schedule` + `_should_run_on` (326-343) | "daily"/"monday" | any weekday name |
| `daily-audit.yml` `FEEDS` limits (167-202) + `test_scheduling_punctuality.py:127` | Monday ⇒ ≥192h | any weekly ⇒ ≥192h |
| `scripts/generate_dashboard.py` `_PUB_AGE_THRESHOLDS_H` (128) | per-slug, dp_pod missing | derived from CRON_MAP (fixes the dp_pod gap) |
| `tests/test_mit_benchmark_integrity.py:2725` cron-shape model | daily or `1`+monday only | any single weekday |
| `engine/daily_edition.py` `expected_slugs` | Monday-aware | unchanged: no new show joins the lineup at launch |

If the operator declines this, every weekly below moves to Monday and the
slot table in §6 has an alternate column.

### 2d. Scaffold repairs (the tool would ship four defects today)

- `shows/templates/weekly.txt.template` carries `{today_str}` and
  `{slow_news_context}` — a scaffolded weekly prompt fails
  `tests/test_prompt_fidelity.py:114` on `.format()`.
- Template sets `slow_news.enabled: true` with no `library_file` —
  fails `tests/test_slow_news.py:219`.
- `merge_network_meta` rewrites `shows/network_meta.yaml` with
  `safe_dump(sort_keys=True)` (`engine/show_scaffold.py:221-233`) — strips
  the comments and reorders every entry. Append a block instead.
- The registration patch prints a 48h audit limit for a weekly show
  because `weekly_summary_segment` defaults true; and the Buttondown tag it
  prints (`slug-with-dashes`) disagrees with the YAML `newsletter.tag`
  (the show name) — the Worker's `SHOW_NEWSLETTER_TAGS` must match the
  YAML or the tag is silently dropped.
- New CLI flags: `--display-order`, `--strand`, `--host`, `--voice`,
  `--cadence <weekday|daily>`, `--related-reason`, `--page-lang`.
- `publishing.rss_link` must point at an HTML file that exists
  (`tests/test_config.py:892`): the scaffold renders the show page stub
  (`generate_html.py --show <slug>`) as part of scaffolding.

### 2e. Small fixes that bite new shows

- `skip_threshold = getattr(config, "min_articles_skip", 3) or 3`
  (`run_show.py:1235`) turns an explicit 0 into 3. Use `is None`.
- `cost_circuit_breakers:` is only honoured at the TOP level of a show
  YAML (`engine/config.py:1390-1394`); the nested block in `_defaults` is
  dead. Every new show sets `max_weekly_cost_usd` at top level (values in
  §4) so a runaway search or TTS loop on an unproven show is bounded.
- The "18 shows" literals (`CLAUDE.md:238`, `engine/newsletter.py:100`,
  pinned by `tests/test_show_count_consistency.py`) become a computed count
  from the registry — the site rule is "claims computed, not typed", and
  this number changes five times in this rollout.
- `_SLUG_TO_BRAND_CLASS` in `engine/newsletter_template.py:444` lacks
  every show since DP Pod; add the new slugs when their newsletters turn on.

### 2f. Chrome: strands, badges, explore, hubs

- New `strand` values: `world` (the six Omni View desks + the existing
  Omni View), `local` (Vancouver, Collingwood), `network` (Nerra Daily,
  Nerra Weekly, Nerra Network Developments), `markets` (MAG 7, Modern
  Investing, Tesla Shorts Time), `health` (Planetterrian, Peptides,
  Longevity). `base.html.j2:214-216` special-cases only `mira`; it becomes a
  generic grouping with a translation key per strand, so the Shows dropdown,
  mobile menu, footer and Blog dropdown all group the same way
  (`show_groups` is already the one grouping — extend it, do not fork it).
  Nerra Daily keeps `strand: mira` for the claim band AND is listed under
  the network group in navigation via `host`/`strand` both being read; if
  that proves confusing in the render, Nerra Daily stays where it is.
- Explore filters on `TOPIC_HUBS`; new `picker_tags.topics` use the hub
  vocabulary only: desks → `world-news, politics, balanced`; local →
  `news, canada` plus a new hub `local-news` (built only when
  ≥12 episodes exist — `MIN_EPISODES_FOR_HUB`); chips → `ai, engineering`;
  MAG 7 → `stocks, markets, ai`; Peptides/Longevity → `longevity, health,
  biotech, science`; Nerra Weekly → excluded like Nerra Daily
  (`HUB_EXCLUDED_SHOWS`); Nerra Dev → `engineering`. Hub snapshot guard
  (`tests/test_registry_pass_2026_09_21.py:30`) is updated per phase.
- `start_here.html.j2:134-314` and `templates/show_page.html.j2:192-212`
  have hardcoded slug lists — reviewed per phase.
- Homepage/explore card macro is shared; strand badge text comes from the
  strand key, host badge from `host`.

### 2g. Registration surfaces that tests do NOT guard

These drift silently and are on every show's checklist (Appendix A):
`engine/network_promo.py` `ENGLISH_SHOWS`/`ENGLISH_ORDER` (spoken name +
tagline; note with 27 English shows against a 13-slot surface pool,
same-day echoes become unavoidable — the echo guard
`TestSameDayShowsDoNotEchoEachOther` needs re-reading, not just re-running),
`_producer_policy.yaml` `pitched_show_names` (pinned at 13),
`workers/gallery/src/handlers.ts` `SHOW_NEWSLETTER_TAGS`,
`weekly-newsletter.yml` options, `generate_network_rss.py` `FEEDS`
(already missing spacex and first_principles), `scripts/submit_to_directories.py`,
`pipelines/voices/validators/schema_validators.py` `KNOWN_SHOWS`,
`engine/intros.py` `_SHOW_PERSONALITIES`, `SEED_TIERS`
(`scripts/update_youtube_policy.py:164`) when YouTube turns on.

---

## 3. The roster

| # | Show | Slug | Host / voice | Cadence (UTC slot, §6) | Modelled on | Strand | Brand |
|---|---|---|---|---|---|---|---|
| 1 | AI Chips & Data Centres Daily | `ai_chips` | Patrick `kdif6sqjcyiq` | daily 09:31 | Models & Agents | ai | `#4338CA` |
| 2 | MAG 7 Daily | `mag7` | Patrick | daily 10:46 | SpaceX Daily | markets | `#334155` + gold accent `#F59E0B` |
| 3 | Peptides Weekly | `peptides` | Patrick | Thu 11:01 | Planetterrian | health | `#9D174D` |
| 4 | Longevity Weekly | `longevity` | Patrick | Wed 11:01 | Planetterrian | health | `#3F6212` |
| 5 | Vancouver Daily News | `vancouver` | Mira `ara` | daily 12:16 (05:16 PT) | Omni View | local | `#0D6E8C` |
| 6 | Collingwood Weekly | `collingwood` | Mira | Fri 10:07 (06:07 ET) | Omni View | local | `#7C2D12` |
| 7 | Omni View North America | `omni_view_north_america` | Mira | daily 10:16 (06:16 ET) | Omni View | world | family `#0B6FD6`, accent amber |
| 8 | Omni View Europe | `omni_view_europe` | Mira | daily 06:46 (08:46 CEST) | Omni View | world | family, accent indigo |
| 9 | Omni View Asia Pacific | `omni_view_asia_pacific` | Mira | daily 06:16 (16:16 AEST) | Omni View | world | family, accent teal |
| 10 | Omni View Central & South America | `omni_view_latam` | Mira | daily 10:31 (07:31 BRT) | Omni View | world | family, accent green |
| 11 | Omni View Africa & Middle East | `omni_view_africa_mideast` | Mira | daily 06:31 (09:31 EAT) | Omni View | world | family, accent sand |
| 12 | Omni View Top World News | `omni_view_world` | Mira | daily 11:31 (after all desks) | Omni View + desks | world | family, accent white |
| 13 | Nerra Weekly | `nerra_weekly` (registry-only) | Mira | Sun 13:23 (own workflow) | Nerra Daily | network | `#005F78` |
| 14 | Nerra Network Developments | `nerra_dev` | **Patrick (assumption, §10)** | Sun 11:01 | new shape (hook articles) | network | `#475569` |
| 15 | Prediction Markets Daily *(added 23 Sep)* | `prediction_markets` | **Patrick (assumption, §10)** | daily 11:16 (07:16 ET) | MAG 7 (desk + hook data) | markets | `#86198F` |

Naming: the network brand is "Omni View" (two words, registry name). The
desks are named "Omni View Europe" etc.; the brief's "Omniview" spelling is
not used on any surface. Slug hyphen rule: page files are
`omni-view-europe.html`, `ai-chips.html`, `mag7.html`, `vancouver.html`.

Voices: the ten English Patrick shows share `kdif6sqjcyiq`; all Mira shows
use the built-in `ara` with `publishing.host_name: Mira`,
`host_kind: ai`, `rss_author: Nerra Network` (the AoAI shape,
`shows/age_of_ai.yaml:59-97`).

---

## 4. Per-show specifications

Common to all YAML shows unless stated: `_defaults.yaml` inheritance
(grok-4.3, combined generation on, source_integrity enforce+strip, spoken
text gate enforce, `<fast>` wrap for Patrick shows), `weekly_summary_segment:
true` on dailies only, `story_recurrence: true` on news shows,
`youtube.enabled: false` with a complete block and ≥3 curated
`image_queries` (guard), `newsletter.enabled: false` at launch,
`multilingual.enabled: false`, `x_enabled: false`, top-level
`max_weekly_cost_usd`, an Ep1 override in `engine/first_episode.py`, a
`_SHOW_PERSONALITIES` entry (host, identity tail, three closing variants,
shape-described), a `SHOW_SECTION_PATTERNS` entry, a
`SHOW_VALIDATION_CONFIGS` entry, a ledger file `docs/reviews/ledger/<slug>.yaml`,
a `review_state.yaml` target dated to launch, an `experiments.yaml` entry
`<slug>-launch-<date>` (area `reach`, metric: median first-week downloads
from `api/audience_headline.json`, target set after four weeks, not
before), and a `shows/segments/<slug>.json` slow-news library or
`slow_news.enabled: false`.

### 4.1 AI Chips & Data Centres Daily (`ai_chips`)

- **Promise:** the silicon, the buildings and the power behind AI — what
  shipped, what broke ground, what it costs. Engineering-and-capex first.
- **Boundary with Models & Agents:** M&A owns models, agents, software and
  research; AI Chips owns silicon, systems, data-centre construction,
  power/cooling, supply chain and export policy. A chip launch may appear
  on both with different lenses; the prompt says which lens is this
  show's, and `cross_show_already_covered` (a hook block built from the
  last 24h of `digests/models_agents/*.md`, the DP Pod sibling-digest
  pattern) marks the overlap so the writer treats it as covered. M&A's
  `ai_compute` memory program stays where it is.
- **Digest sections** (`### `, in order): Top Story · Silicon (4–6) ·
  Data Centres & Power (4–5) · Supply Chain & Policy (3–4) · The Teardown:
  [topic] (a second story, never a re-pass; numbers floor 4) · On the
  Horizon. Item sentence count follows fact count (the Sep 5 rule); every
  item carries a `Source:` line.
- **Podcast:** cold open on the hook → identity line → sections in order
  → Teardown → Tomorrow Teaser → `{closing_block}`; includes
  `_shared/content_discipline.txt`. 1,500–2,000 words. Chapter markers
  = the six headers.
- **Sources (probed OK):** SemiAnalysis, Tom's Hardware, ServeTheHome,
  The Next Platform, HPCwire, EE Times, Semiconductor Engineering,
  Semiconductor Digest, TechPowerUp, Data Center Dynamics, Data Center
  Knowledge, Utility Dive (power), NVIDIA blog + `nvidianews.nvidia.com/releases.xml`,
  IEEE Spectrum semiconductors (slow), plus GN queries: "TSMC", "HBM
  memory", "data center power grid", "Nvidia Blackwell Rubin", "export
  controls chips". Dead: AnandTech, Data Center Frontier `/rss`, The
  Register data-centre atom (retest the Register's other atom paths from a
  runner). `exclude_title_patterns` for consumer GPU deals / "best
  laptop" listicles (TechPowerUp and Tom's are consumer-heavy).
- **Memory (`memory_enabled: true`, seeded programs):** nvidia_roadmap,
  tsmc_nodes_and_packaging, hbm_supply, hyperscaler_capex, stargate_and
  _gigasites, xai_colossus, grid_interconnection_and_power, export_controls,
  intel_foundry, custom_silicon (TPU/Trainium/MTIA/Maia). Seeded with
  status only, no forecasts.
- **Thresholds:** `min_articles_skip: 4`, `min_digest_words: 1300`,
  `min_podcast_words: 1500`, `max_weekly_cost_usd: 8`.
- **Ep1:** a "What this desk covers" section after the hook (200–300
  words: the three layers — chips, systems, sites — and the one number
  the show will keep returning to, gigawatts under construction), then a
  normal day. No catalogue read, no "last week".
- **Risks:** consumer-hardware noise (filter), and the same-day overlap
  with M&A on NVIDIA days (the hook block above; read
  `story_recurrence_in_digest` weekly).

### 4.2 MAG 7 Daily (`mag7`)

> **Revised 2026-09-23 (§9b):** the show is about what the seven build, ship,
> discover and are allowed to do. The tape below survives only as one
> reader-only line at the foot of the digest that the script never reads;
> the earnings calendar is gone.

- **Promise:** the seven largest US companies as one daily desk — the tape,
  the news, one cross-company thread, the calendar. Not a trading show.
- **Boundaries:** Tesla Shorts Time owns Tesla's products, FSD, energy and
  community; MAG 7 speaks Tesla only at company level (results, guidance,
  capital, regulation, the share) and plugs TST for the rest. Modern
  Investing owns picks and the practice portfolio; MAG 7 never picks. Both
  boundaries are prompt rules plus a TST-sibling `cross_show_already_covered`
  block. The SpaceX AI section rule (Colossus/Anthropic material is REAL)
  carries over wherever xAI appears.
- **Hook `shows/hooks/mag7.py`:** seven quotes via the Tesla chain
  (yfinance history → fast_info → Yahoo v8), the SpaceX clock rule for the
  verb (`_market_is_open` — weekday 04:00–20:00 New York; "closed at" on
  weekends and pre-open; "unchanged", never "up zero percent"), a sanity
  band per ticker and the 25% deviation guard, cached to `api/mag7_quotes.json`
  (whitelisted in the run-show commit step and nightly `add-paths`;
  `_STOCK_WIDGETS["mag7"]`). Recommended: lift the chain into
  `engine/market_quotes.py` used by mag7 first; Tesla and SpaceX migrate
  later under their own review, not in this PR. The hook also supplies the
  next earnings date per company (yfinance calendar; "unknown" when the
  API has none — never a guessed date), `tone_hint`, and the
  `closing_block` with the spoken not-financial-advice line.
- **Digest sections:** The Tape (the seven quotes verbatim from the hook
  block, or one sentence saying the feed was unavailable) · Top News (3–4
  across companies) · Company Desk (one item per company WITH news; a
  company without news is omitted, never padded) · The Counterpoint · The
  Thread (one cross-company story with a numbers floor of 5) · Calendar
  (earnings, events, regulatory dates from the hook) · sign-off. Saturday:
  the Tape becomes the week's moves; Sunday: the weekly-summary segment
  plus the week-ahead calendar (SpaceX precedent).
- **Sources (probed OK):** company newsrooms — Google blog, About Amazon,
  Apple Newsroom, Meta Newsroom, Microsoft blog, NVIDIA releases; Yahoo
  Finance multi-ticker headline feed; The Information, FT technology RSS,
  Bloomberg technology RSS, MacRumors, 9to5Google/9to5Mac, Android
  Authority, GeekWire (Amazon/Microsoft), Stratechery, Ars, The Verge,
  TechCrunch; GN queries per ticker + "antitrust" + "earnings". Blocked
  by policy: `finance.yahoo.com` and `seekingalpha.com` are in
  `_blocked_sources.yaml` (quality) — the Yahoo HEADLINE feed is a
  different host (`feeds.finance.yahoo.com`); confirm with `--check-blocked`
  before relying on it, or drop it. CNBC/Reuters/WSJ answer 403/401.
- **Disclaimer:** `newsletter.requires_financial_disclaimer: true`; the
  podcast prompt requires one spoken not-advice line in the closing (the
  SpaceX shape, MIT wording precedent).
- **Thresholds:** `min_articles_skip: 5`, `min_articles: 8` (web search
  fires below it), `min_digest_words: 1200`, `min_podcast_words: 1300`,
  `podcast_chain: true` (SpaceX), `max_weekly_cost_usd: 10`.
- **Ep1:** debut section explains the seven, the one-desk idea and the
  boundaries (TST, MIT) as a listener promise; the Tape runs as normal.
- **Risks:** market-data flakiness (the chain has three sources and a
  cached fallback, and the digest must SAY when it has no price); the
  Tesla double-coverage complaint is the one to watch in the first ledger.

### 4.3 Peptides Weekly (`peptides`) and 4.4 Longevity Weekly (`longevity`)

> **Revised 2026-09-23 (§9b):** education first — human findings a listener
> can use, how the biology works, consumer protection; commercial pipeline
> news at most one item a week; a Worth Knowing section; BioPharma Dive
> replaced by research sources; curricula lead with practical subjects.

Both are Patrick, weekly, Planetterrian-structured, and carry the same
health posture, so they share one spec with per-show differences.

- **Posture (both):** education and awareness, never dosing, sourcing or
  "protocols". Every episode speaks a standing line in the identity tail
  and in the closing (shape: what the show is not, whom to ask) — supplied
  by the hook's `closing_block` so the model cannot drop it, the same
  mechanism as the SpaceX closing. New `newsletter.requires_health_disclaimer`
  (sibling of `requires_financial_disclaimer`, `engine/config.py:511`,
  rendered by a new `_build_health_disclaimer_html`). The digest prompt
  requires regulatory status per substance where stated by the source
  (approved / investigational / unapproved) and the claims gate's
  `enforce` + `strip` does the rest: an unverifiable efficacy sentence
  does not ship. **YouTube stays off until a review pass** — platform
  medical-content policy is a channel-level risk, not a per-video one.
- **Structure (both):** `### The Week in <field>` (5–8 items; weekly
  feeds need `window_hours: 192` on every source and `stale_article_days: 9`)
  · `### <Spotlight>` (Peptides: "Peptide Spotlight: [name]"; Longevity:
  "Mechanism of the Week: [name]") ~400 words from a CURRICULUM queue ·
  `### Evidence Ledger` (the studies behind the spotlight, each a claim
  the ledger verifies) · `### Trial Tracker` (Longevity only; from memory
  programs) · sign-off. Podcast ~1,600 words, content_discipline included.
- **Curriculum queue:** `shows/topic_queues/<slug>.yaml` in the existing
  queue format (`id, title, brief, category, produced`), consumed by the
  hook (`pre_fetch` → `{spotlight_title}`, `{spotlight_brief}`; `post_generate`
  → `mark_topic_produced`), NOT `narrative_mode` — the news fetch still
  runs. Seeded ~26 entries each (six months). Peptides: GLP-1 class
  (semaglutide, tirzepatide, retatrutide, cagrilintide), insulin as the
  first therapeutic peptide, oxytocin, teriparatide, thymosin alpha-1,
  BPC-157, TB-500, GHK-Cu, CJC-1295/ipamorelin/sermorelin/tesamorelin,
  PT-141, melanotan, epitalon, MOTS-c and humanin, SS-31, semax/selank,
  kisspeptin, DSIP, AOD-9604, peptide manufacturing and the grey market as
  a topic in itself. Longevity: the hallmarks of aging, senolytics,
  rapamycin/mTOR, NAD+, epigenetic clocks, caloric restriction and
  fasting, GLP-1s and aging, VO2max and strength, sleep, partial
  reprogramming, plasma factors, autophagy, telomeres, mitochondria,
  inflammaging, the microbiome, Klotho, thymic involution, biomarkers, the
  named trials (TAME, PEARL, TRIIM-X), regulation of aging as an
  indication. Not auto-restocked at launch (the restock registry is FP/UC
  only); a `TestNarrativeQueueRunway`-style guard at 6 weeks.
- **Sibling rule (Longevity vs Planetterrian):** Planetterrian is daily
  and already "science, longevity, health". Longevity Weekly is the
  synthesis + mechanism show and must not re-tell Planetterrian's week:
  the hook builds `cross_show_already_covered` from the last seven
  `digests/planetterrian/*.md` (headline + date), injected as
  update-don't-retell notes. Peptides has no daily sibling.
- **Sources (probed OK):** Fight Aging!, Lifespan.io, Nature Aging, Aging
  Cell (Wiley), Cell Metabolism, ScienceDaily healthy-aging and hormone
  feeds, STAT, Endpoints, Fierce Biotech, BioPharma Dive, Peptides journal
  (ScienceDirect RSS), Journal of Peptide Science (Wiley; thin), Europe PMC
  search JSON via hook articles (`query=peptide therapeutic` /
  `aging intervention`, last 14 days). Operator: create two PubMed saved
  searches and paste their RSS URLs (the RSS key is UI-generated). Retest
  from a runner: FDA press RSS (401/403 here), NIH/NIA (403 / stale Feb
  2026), bioRxiv collection feeds (429). Longevity.Technology returned 202
  (bot challenge) — drop. Peter Attia and Buck Institute are opinion /
  stale — not sources.
- **Memory:** Longevity `memory_enabled: true` with programs
  tame_metformin, rapamycin_trials, partial_reprogramming, senolytics,
  glp1_and_aging, epigenetic_clocks, longevity_biotech_funding,
  aging_as_indication. Peptides: glp1_class, regulatory_actions,
  peptide_manufacturing, grey_market_enforcement.
- **Thresholds:** `min_articles_skip: 3` (weekly window is wide),
  `min_digest_words: 1200`, `min_podcast_words: 1400`, `on_failure: strip`
  (not block: a blocked weekly costs a week), `max_weekly_cost_usd: 4`.
- **Ep1:** the posture IS the debut section — what the show will and will
  not do, how it reads evidence, and the first spotlight (Peptides:
  insulin, the peptide everyone already trusts; Longevity: the hallmarks
  framework), so the series starts from ground truth rather than a
  controversial compound.

### 4.5 Vancouver Daily News (`vancouver`) — Mira

- **Promise:** the morning brief for people who live in Metro Vancouver:
  the day's civic and provincial stories, getting around, sports, what's
  on, and one contested local issue argued fairly both ways. Ready by
  05:30 Pacific.
- **Host:** Mira (`ara`), first Mira news show and therefore **the
  calibration set for the whole AI-host path (§2b)**: identity tail
  discloses the AI every day; Ep1 test renders are made with and without
  the `<fast>` wrap and the operator picks; the spoken-text gate is
  `enforce` (English).
- **Digest sections:** Top Stories (3–4) · City & Province (3–4: council,
  housing, transit policy, BC government) · Getting Around (from hook data
  ONLY: DriveBC Open511 road events for the Lower Mainland, TransLink
  alerts when a machine-readable source is confirmed, Environment Canada
  forecast; a data-less day says so in one sentence) · Sports (Canucks,
  Whitecaps, Lions, Canadians; via GN queries and CanucksArmy) · What's On
  (events; Thu/Fri lean to the weekend) · Both Sides (one contested local
  issue, strongest case each way — the Omni View DNA, one per episode).
- **Hook `shows/hooks/vancouver.py`:** hook-supplied articles from the
  DriveBC Open511 JSON (answered 200 in the probe; area filter for the
  Lower Mainland, severity ≥ moderate, `exempt_stale`), plus a weather
  article from the Environment Canada city RSS (the URL returned 404 via
  proxy — confirm the current path). Metric: `articles_from_hook`.
- **Sources (probed OK):** CBC British Columbia, Vancouver Sun, The
  Province, Global BC, CityNews Vancouver, Daily Hive Vancouver (feed at
  `/feed/vancouver`), Vancouver Is Awesome, Georgia Straight, The Tyee,
  Business in Vancouver, North Shore News, Richmond News, Delta Optimist,
  Squamish Chief, VPD news, UBC News, CanucksArmy; GN queries: "Vancouver
  city council", "TransLink", "Metro Vancouver", "Canucks", "Whitecaps",
  "BC Lions", "Vancouver events". Retest from a runner: BC Gov News
  (timeout), Burnaby Now / Tri-City News (`/rss` served HTML — Glacier
  sites use `/rss` on some titles and a feed path on others), Metro
  Vancouver, TransLink. `fetch_full_text: 8` (local wire copy is short;
  the digest needs bodies), `stale_article_days: 3`.
- **Region purity:** `keywords` include the municipalities; the prompt's
  first rule is "a story qualifies if it happens in, or is decided for,
  Metro Vancouver or British Columbia".
- **Thresholds:** `min_articles_skip: 4`, `min_digest_words: 1200`,
  `min_podcast_words: 1300` (a 9–11 minute commute brief, deliberately
  shorter than the network's 1,500 default), `max_weekly_cost_usd: 8`.
- **Timezone:** 12:16 UTC = 05:16 PDT. This is the latest slot the
  scheduler Worker's cron window (hours 6–12) allows; the window and its
  test (`test_schedule.py:106`) stay as they are.
- **Ep1:** Mira introduces herself as an AI in the first thirty seconds,
  says what the brief is for and the one thing it will not do (speculate
  about people), then a normal day.

### 4.6 Collingwood Weekly (`collingwood`) — Mira

- **Promise:** the week in Collingwood and the south Georgian Bay towns —
  council and county, Blue Mountain, the roads and the weekend ahead,
  local sport — in twelve minutes on Friday morning.
- **Cadence:** Friday 10:07 UTC (06:07 ET) so "the weekend ahead" is
  true; Monday if §2c is declined.
- **Sources (probed OK):** CollingwoodToday (Village Media; the anchor
  feed), Bayshore Broadcasting, Simcoe.com search RSS (Metroland; rate
  limited on `/feed/` — use the search feed), County of Simcoe news
  (`simcoe.ca/rss`), Midland Today / Barrie Today / Orillia Matters for
  regional context (BarrieToday timed out via proxy), GN queries: "Town of
  Collingwood", "Collingwood council", "Blue Mountain resort", "Wasaga
  Beach", "Clearview Township", "Grey County", "Collingwood Blues", "OPP
  Collingwood". No feed: Town of Collingwood, The Blue Mountains, OPP,
  Wasaga Sun, Enterprise-Bulletin (closed) — GN covers them.
  `window_hours: 192` on every feed, `stale_article_days: 9`,
  `fetch_full_text: 10`.
- **Sections:** The Week's Stories (4–6) · Council & County · Roads &
  Weather Ahead (hook: Ontario 511 has an Open511-style API — confirm;
  otherwise this section is source-only and says so) · Sport ·
  The Weekend (events) · Both Sides (one local issue). `min_articles_skip:
  3` — a small town in a quiet week is a real case; slow-news library
  seeded with evergreen Collingwood/Georgian Bay explainers rather than
  skipping.
- **Thresholds:** `min_digest_words: 1000`, `min_podcast_words: 1200`,
  `max_weekly_cost_usd: 3`.
- **Risk:** thinness. This is the show most likely to hit
  `insufficient_articles`; the ledger's first prediction is the skip rate.

### 4.7 The Omni View desks (five regional shows) — Mira

One shared spec; each desk is a YAML plus a region file included into
shared prompts.

- **Relationship to the existing Omni View:** Omni View (Patrick) is the
  analytical world show — Steel Man, Understanding the Issue,
  media-literacy note. The desks are Mira's regional briefs: faster, one
  region deep, the Steel Man DNA kept as exactly one "Both Sides" block per
  episode. No desk carries Understanding the Issue or the media-literacy
  note (those stay Omni View's). Omni View's own sources already span the
  regions; that overlap is accepted — the desks exist for the listener
  who wants one region every day.
- **Prompt architecture:** `shows/prompts/_shared/omni_desk_digest.txt` and
  `omni_desk_podcast.txt` carry the format; each desk's prompt is a short
  file that includes them (`<<include:>>`, opt-in, resolved before
  placeholders) and supplies the region definition, its sub-regions, the
  languages/outlets the desk reads, and its "region rule": a story
  qualifies if its primary actor or location is in the region; a global
  story qualifies only through its regional consequence. The five region
  files are the ONLY per-desk prompt text, so a format fix lands once.
- **Digest sections:** Lead (1) · Across the Region (4, each from a
  different sub-region where the day allows) · The Region and the World
  (1) · Both Sides (1 contested story, strongest case each way) · Progress
  Watch (1) · Read More (sources). ~1,300 words; podcast ~1,400 words
  (10–12 minutes). Validation: Lead + Across the Region `min_items=4`;
  section patterns registered for all five.
- **Sub-region balance is data-side:** the hook records which sub-regions
  appeared in the last ten digests and injects an "under-covered" note
  (the DP Pod lever-rotation pattern) — no roll-call, no quota.
- **Sources per desk** (all probed OK unless noted; full list Appendix B):
  - *Europe* (06:46 UTC): BBC Europe, Guardian Europe, France 24 Europe,
    DW Europe, Euronews, Irish Times, Balkan Insight, Moscow Times; retest
    Politico Europe (403 here), Kyiv Independent (404 at `/feed`; try
    `/rss/`); The Local's feed is stale (Jan 2025) — drop. GN: EU
    Commission, UK politics, Germany, France, Ukraine war, Nordics, Iberia.
  - *Asia Pacific* (06:16 UTC): BBC Asia, Guardian Asia, France 24 APAC, DW
    Asia, SCMP, Nikkei Asia, Japan Times, ABC Australia, CNA, Straits Times
    Asia, Korea Herald, Yonhap, The Hindu international, Times of India
    world, Hindustan Times world, SMH world, RNZ (thin). GN: China, Japan,
    India, ASEAN, Australia, Pacific islands, Taiwan.
  - *Africa & Middle East* (06:31 UTC): BBC Africa, BBC Middle East,
    Guardian Africa, Guardian Middle East, France 24 Africa, France 24
    Middle East, DW Africa, Al Jazeera, Arab News, Middle East Eye,
    Haaretz, Daily Maverick, Premium Times, Punch, Nation (Kenya), Daily
    News Egypt; retest The East African, Times of Israel, AllAfrica (403 /
    timeout here); Mail & Guardian 404. GN: Gulf, Levant, Iran, Nigeria,
    Kenya, South Africa, Sahel, Maghreb, Ethiopia/Horn.
  - *Central & South America* (10:31 UTC): BBC Latin America, Guardian
    Americas, France 24 Americas, MercoPress, Buenos Aires Times, Mexico
    News Daily, Rio Times, Colombia Reports, Jamaica Observer, Al Jazeera;
    Brasil Wire served HTML; EFE 500; teleSUR 404. GN: Brazil, Mexico,
    Argentina, Colombia, Chile, Peru, Venezuela, Central America,
    Caribbean. This is the thinnest English-language desk; `min_articles:
    8` so web search fires more often, and a Spanish/Portuguese-source
    question is an operator decision (the translation layer exists; the
    fetch layer is English-only today).
  - *North America* (10:16 UTC): BBC US & Canada, Guardian Americas, CBC
    Top Stories, Global News (Canada feed path to confirm), PBS NewsHour,
    LA Times world-nation, Mexico News Daily (Mexico belongs to this desk
    AND the LatAm desk; the region files say which stories go where:
    US–Mexico affairs here, domestic Mexico there), Globe and Mail (Canada
    category feed to confirm); retest NPR and Politico (403 here). GN: US
    Congress, White House, Supreme Court, Canadian politics, provinces,
    US states.
- **Thresholds (each desk):** `min_articles_skip: 4`, `min_digest_words:
  1100`, `min_podcast_words: 1300`, `exclude_title_patterns` = Omni
  View's nine anti-tabloid regexes, `max_weekly_cost_usd: 7`.
- **Memory:** `memory_enabled: true` with three or four seeded regional
  arcs per desk (Europe: ukraine_war, eu_institutions, uk_politics,
  migration; APAC: taiwan_strait, china_economy, india_politics,
  korea_peninsula; AME: gaza_and_israel, iran, sudan_and_sahel,
  gulf_economies; LatAm: venezuela, argentina_economy, mexico_security,
  amazon_and_climate; NA: us_executive_and_courts, canada_federal,
  us_mexico_border, trade).
- **Ep1 (each):** Mira's AI disclosure in the first thirty seconds, the
  region rule spoken once as a listener promise, no tour of the other
  desks (one sentence that the desks exist), then a normal day.
- **Risks:** the APAC desk publishes at 16:16 AEST / 15:16 JST — an
  evening brief for its own region, a morning one for Europe. A true APAC
  morning is ~21:00 UTC and outside the Worker window; accepted at launch
  and noted on the show page ("ready by the end of the Asia-Pacific
  business day"). Read the OP3 geography once it exists before moving it.

### 4.8 Omni View Top World News (`omni_view_world`) — Mira

- **Promise:** the ten stories that matter most anywhere in the world
  today, one Both Sides, done in twelve minutes. The desk that reads the
  other five.
- **Mechanism:** runs LAST (11:31 UTC). Its hook supplies the day's five
  regional desk digests as hook articles (title = each item's headline,
  `content_text` = the item body, `link` = the item's `Source:` URL — so
  the claims gate verifies against the ORIGINAL publisher URL and the
  fetched copy, never against a sibling digest), plus its own top-line
  feeds (BBC World, Guardian World, Al Jazeera, DW World, NYT World, Globe
  and Mail World, CBC World). A desk that skipped that day is simply
  absent (the skip marker is read, the Nerra Daily pattern). Without the
  hook data it is still a valid show on its own feeds.
- **Why this is not the existing Omni View:** Omni View picks ~7 stories
  and argues them; Top World ranks ten across regions with one Both Sides
  and no essay. §10 flags the operator question of whether the existing
  show should be renamed to signal the difference.
- **Sections:** The Ten (ranked; one paragraph each; region tag in the
  headline line) · Both Sides (1) · Progress Watch (1) · Read More.
  `min_articles_skip: 4`, `min_digest_words: 1200`, `min_podcast_words:
  1400`, memory off (the desks carry the arcs), `max_weekly_cost_usd: 6`.

### 4.9 Nerra Weekly (`nerra_weekly`) — Mira, assembled

- **Promise:** the week on the Nerra Network in about an hour: the best
  segment from each show, the week's interview, and what the network
  learned. Sunday.
- **Shape:** an EDITION on `engine/daily_edition.py`, registry-only (no
  YAML, like Nerra Daily — `docs/nerra_daily.md:17-23` says why), built by
  a new `scripts/build_weekly_edition.py` + `.github/workflows/nerra-weekly.yml`
  (Sunday 13:23 UTC, after the last Sunday show; `workflow_dispatch` with a
  week-ending date). `EditionSpec` is already language-parameterized; the
  weekly needs the day assumptions generalized, not a new engine:
  - selection over a DATE RANGE per show (today: exact-date match,
    `discover_lineup` :346-349);
  - per show, the week's top episode by `downloads_3d` from
    `api/op3_stats.json` `episodes[]` where present, else the midweek
    episode; `selection_basis` recorded per segment (null vs 0 rules);
  - a CLIP, not the whole episode: the chapter whose title best overlaps
    the hook, bounded on the Whisper word timestamps (chapter JSON times
    are proportional estimates — `engine/chapters.py:1-5` — and must not
    be used as cut points), snapped to sentence ends, 3–6 minutes, promo
    tail never included (`find_promo_cut` anchors);
  - Age of AI: a 90–120 s excerpt of the week's interview chapter as
    produced (the guest's approved words, unedited inside the excerpt)
    plus the plug — the "never splice the 40-minute interview" rule
    (`tests/test_daily_edition.py:77-80`) is about whole episodes; an
    excerpt is a new, narrower rule the test file states explicitly;
  - Mira's links from a `nerra_weekly_links.txt` prompt with the same JSON
    validation, rotation memory and fallback as the daily; her network
    AI-disclosure once at the end (`MIRA_AI_DISCLOSURE`); no field note in
    v1;
  - wording generalized where the daily hardcodes it: `"<Weekday>
    edition —"`, "published today", "back tomorrow", the `nerra daily`
    title validator, the AoAI same-date check.
- **Outputs:** `nerra_weekly_podcast.rss` (exact spliced chapters),
  `nerra-weekly.html`, a rundown `.md` per week → blog post linking into
  each show's episode page, `metrics_epNNN.json`, `credit_usage_*`.
- **Registration:** `network_meta.yaml` entry (`host: mira`, `strand:
  network`, `page_lang` not needed), `_VIRTUAL_COST_SLUGS += ("nerra_weekly",)`,
  `_virtual_show_targets` picks it up once the feed file exists,
  `import_virtual_shows` imports the rundowns, `HUB_EXCLUDED_SHOWS`,
  `nerra-weekly.yml` `add-paths`, cover via the brand script. Not in
  `review_state.yaml` (registry-only shows are operator-reviewed) — a
  ledger file exists from day one.
- **Cost:** one small links call + ~3k TTS chars + one R2 upload per week
  (<$0.50). Marginal, like the daily.
- **Ep1:** the first edition explains itself in Mira's intro (what "best"
  means here — the listeners' numbers, when they exist) and never claims
  a number the metrics file does not carry.

### 4.10 Nerra Network Developments (`nerra_dev`) — Patrick (assumption)

- **Promise:** what changed on the network this week and why — the PRs
  that merged, the bugs that were found, the numbers that moved — told as
  a builder's changelog, failures included. Sunday.
- **Input (hook-supplied articles, §2a):** `shows/hooks/nerra_dev.py`
  lists PRs merged into `main` since the previous episode's date via the
  GitHub REST API (`/repos/{repo}/pulls?state=closed&base=main`, filter
  `merged_at`), one article per PR: title, body (sanitized), labels,
  author, `merged_at`, files/additions/deletions counts, URL. Direct
  "Auto-generated:" episode commits are excluded by prefix. Also one
  article per closed-unmerged review PR (the network's rejection record)
  and the week's `docs/experiments.yaml` readouts. The repo is public, so
  unauthenticated reads work; the run step gets `GITHUB_TOKEN` anyway for
  the rate limit (it does not have it today — `run-show.yml` gives it only
  to the gate and the recovery step).
- **Claims:** `source_url` = the PR URL; the supporting quote is found in
  the hook article's `content_text`, so verification is `fetched_copy`
  and never hits github.com (which would answer 429 as "unreachable" and
  strip true sentences).
- **Sanitizer:** PR bodies pass a redaction pass before the prompt (token
  shapes, emails, hostnames, anything matching the secret-name patterns in
  `docs/env_var_inventory.md`); the repo is public, but the SPOKEN
  surface is a different audience than a diff.
- **Sections:** Headline Change (the one thing a listener notices) ·
  Shipped (grouped: shows & editorial, pipeline & provenance, site &
  funnel, video, infrastructure) · Fixed (each with the before/after) · By
  the Numbers (PR count, tests added, cost and audience deltas from
  `api/audience_headline.json` — null stays unspoken) · What It Means for
  Listeners · Next Week (open draft PRs; never a promise).
  `narrative_mode: false`, `sources: []` is rejected by the workflow's
  validation step (`run-show.yml:385-391`), so the YAML carries one real
  feed (the repo's own commits Atom feed on github.com — probe from a
  runner; otherwise the GitHub blog changelog) and `min_articles_skip: 1`.
- **Thresholds:** `min_digest_words: 1000`, `min_podcast_words: 1300`,
  `source_integrity.on_failure: block` (a claims failure here means the
  hook broke, and a broken changelog should not ship), `max_weekly_cost_usd: 3`.
- **Ep1:** the debut looks back over the last ninety days at the level of
  themes (the provenance ledger, the funnel, the simplification pass) with
  the PR list as receipts, then sets the weekly promise.
- **Host:** the brief names no host. The plan assumes Patrick because the
  changelog is the operator's own work; Mira is the alternative if the
  operator wants the whole `network` strand in one voice (§10).

---

### 4.11 Prediction Markets Daily (`prediction_markets`) — added 2026-09-23

- **Promise (operator's brief):** a daily show on the developing prediction-
  market ecosystem in Canada, the United States and the world — the
  interesting new markets, the most popular ones, the strategies and the
  people helping to build and legitimize the field, and the economics behind
  it (why a price can be a forecast, and when it is not).
- **Host:** Patrick on `kdif6sqjcyiq`, markets strand (operator-confirmed
  2026-09-23, §10 item 12).
- **The MAG 7 lesson, written in on day one (§9b):** the show is about the
  ecosystem, not a price tape. The board of popular markets is ONE short
  segment of at most five markets; the rest of the episode is developments.
- **Digest sections:** Top Story · The Ecosystem (3–5: regulation and
  courts — the CFTC, state gaming regulators and the suits between them,
  Canadian securities regulators; new venues and products; partnerships with
  leagues, brokers and media; money raised only when it changes what a venue
  can do) · The Board (hook data only, ≤5 markets: the question, the implied
  probability, the venue, the 24-hour volume and the time it was read; one
  sentence of why each is moving only when an article says so) · New and
  Notable (1–3 markets that opened in the window and why they are
  interesting) · How It Works (a rotating explainer, 220–320 words, from a
  curriculum like the health shows': information aggregation and the
  efficient-markets case, calibration and accuracy research, arbitrage and
  market making as mechanisms, manipulation and thin-market failure modes,
  resolution disputes, futarchy and decision markets, the law in Canada vs
  the US) · the closing.
- **Posture:** education and journalism, never a bet. Never a
  recommendation to buy, sell or trade a contract, never "the smart money",
  never a pick. Every probability carries its venue, its time and its
  volume; a thin market is called thin. Legality varies by jurisdiction and
  the show says so whenever a venue is named (most Canadian provinces
  restrict or prohibit these products; US access varies by state and
  product). A gambling-harm line sits in the verbatim closing, the way the
  health shows carry their posture.
- **Hook `shows/hooks/prediction_markets.py`:** the board as hook ARTICLES
  (the `engine/local_conditions.py` pattern): public, keyless endpoints
  probed 2026-09-23 — Polymarket's Gamma API (`gamma-api.polymarket.com/
  markets?order=volume24hr`), Kalshi's public market API
  (`api.elections.kalshi.com/trade-api/v2/markets`) and Manifold's
  (`api.manifold.markets/v0/search-markets?sort=24-hour-vol`), each a
  sourced article with the numbers in `content_text` so the claims gate
  verifies them. Venue filters drop sports-parlay and sub-$10k-volume
  markets from the board (a board of same-game parlays is noise).
- **Sources (probed 23 Sep):** Polymarket's newsletter (`news.polymarket.com/
  feed`), Manifold's (`news.manifold.markets/feed`), Astral Codex Ten (its
  "Mantic Monday" forecasting round-ups), CoinDesk and The Block (with a
  keyword filter — both are crypto-wide), the CFTC general press feed
  (`cftc.gov/RSS/RSSGP/rssgp.xml`), and Google News queries: "prediction
  markets", "Kalshi", "Polymarket", "CFTC event contracts", "prediction
  market Canada OR Ontario Securities Commission", "Metaculus OR forecasting
  tournament". Retest from a runner: the Kalshi blog (429 via proxy),
  Metaculus news (403), the Ontario Securities Commission (403).
- **X accounts (verify handles before Ep1):** the venues and the regulator
  (Kalshi, Polymarket, Manifold, Metaculus, CFTC) plus two or three
  journalists who cover the beat daily; read the first run's per-handle
  counts and prune (§9a).
- **Thresholds:** `min_articles_skip: 4`, `min_digest_words: 1200`,
  `min_podcast_words: 1100`, `max_weekly_cost_usd: 8`, grok-4.7 (§9b).
- **Boundaries:** MAG 7 and Modern Investing own stocks; Omni View owns the
  news a market is about. This show owns the markets as markets — a market
  on an election is covered for what the market is doing, never as election
  coverage.
- **Ep1:** what a prediction market is and why a price can be read as a
  probability, the one thing the show will not do (tell anyone what to
  bet), and the legal patchwork in one sentence each for Canada and the US;
  then a normal day.
- **Phase:** 2b — build after the Phase 2 Episode 1s are heard, before the
  desks. It needs no new host machinery (Patrick) and reuses the
  hook-articles and curriculum machinery that already exist.
- **Risks:** (1) promotion — venues court coverage; the posture and the
  board's five-market cap are the defence; (2) sports-parlay noise on the
  board (filter); (3) regulatory whiplash — a ruling can change what is
  legal in a week, so every legal claim is dated and sourced.

## 5. Design: making fourteen shows read as one network

### 5a. Strand colour system

The palette is full: 18 brand colours already, and every candidate hue
for a new show lands within 10° of an existing one (checked; e.g. any
"local" teal sits next to Planetterrian, any "world" blue next to SpaceX
or Omni View). Fourteen more unique hues would be indistinguishable on a
card grid. So:

- A **strand family** colour carries the group; a **per-show accent**
  (used on the cover glyph, the card badge and the show page's `theme_color`)
  distinguishes shows inside the group.
- Registry: `brand_color` (family), `brand_color_dark`, `theme_color`
  (accent). All values ≥ 4.5:1 on white (newsletter brand-text classes
  render on white) — checked for every value below.

| Strand | Family | Show accents |
|---|---|---|
| world (Omni View + 6 desks) | Omni View blue `#0B6FD6` / dark `#0B1B3B` | World `#1E3A8A` navy · Europe `#1D4ED8` · North America `#0369A1` · Asia Pacific `#0E7490` · C&S America `#15803D` · Africa & Middle East `#A16207` |
| local | `#0D6E8C` (Pacific) | Vancouver `#0D6E8C` · Collingwood `#7C2D12` (Georgian Bay brick) |
| ai (M&A, MAB, AI Chips) | M&A violet `#7C3AED` | AI Chips `#4338CA` |
| markets (MIT, Tesla, MAG 7) | MIT green `#047857` | MAG 7 `#334155` slate with gold `#F59E0B` on the cover |
| health (Planetterrian, Peptides, Longevity) | Planetterrian `#017A99` | Peptides `#9D174D` · Longevity `#3F6212` |
| network (Nerra Daily, Nerra Weekly, Nerra Dev) | Nerra Daily `#007A99` | Nerra Weekly `#005F78` · Nerra Dev `#475569` |

Existing shows keep their colours; strands are additive.

### 5b. Covers: one deterministic template, fourteen outputs

`scripts/generate_nerra_daily_brand.py` is the model: PIL-only, $0,
idempotent, network field `#070E1A` → `#0D1E33`, Nerra cyan arc, DejaVu
typography, WebP variants. Generalize it into
`scripts/generate_show_brand.py --slug <slug>` reading the registry's
colours and a per-strand glyph:

- **world:** the dial with one highlighted SECTOR per desk (six sectors,
  the World cover lights all six) — a family that reads as one product on
  the grid.
- **local:** a horizon line with a single place mark; the city name set
  large; Vancouver's arc in Pacific teal, Collingwood's in brick.
- **ai / markets / health / network:** the arc plus a simple geometric
  glyph (die outline; seven ticks; a helix-free molecule ring, a leaf
  ring; the network's own tick ring from Nerra Daily reduced to seven for
  Weekly and a commit-graph dot line for Dev).
- Title typography and the "NERRA NETWORK" eyebrow identical across all
  fourteen; the host is credited on Mira covers as the daily cover does.
- Grok-Imagine art can replace any cover later; the template guarantees
  every show has a correct 3000×3000 JPEG + `-800/-400.webp` on launch
  day (the YouTube cover lookup and the API both derive from
  `assets/covers/<slug-hyphen>.jpg`).

### 5c. Music

No generator exists in-repo; themes are Suno tracks the operator makes
from the briefs in `assets/music/README.md`. Shows without a file ship
voice-only, so music is not a launch blocker. Plan:

- Launch reuse (precedent: M&A/MAB share one theme; EI used the Tesla
  theme for months): desks → `OmniView.mp3`; AI Chips → `ModelsAgents.mp3`;
  MAG 7 → `ModernInvesting.mp3`; Peptides/Longevity → `oilers-pride.mp3`;
  Nerra Dev → `tesla_shorts_time.mp3`; Vancouver/Collingwood → voice-only
  until a "local" theme exists; Nerra Weekly → the Nerra Daily bed
  behaviour.
- Briefs to commission (one each): a **desk** variant of the Omni View
  theme (same motif, lighter, 30 s), a **local** theme (warm, acoustic,
  civic), a **Mira** sonic identity used under her links across Nerra
  Daily/Weekly (not a per-show theme). Add each to the README table.

### 5d. Chrome and pages

- Strand groups in nav/footer/explore via `show_groups` (§2f); the
  homepage grid keeps `display_order` (new values interleave: desks 3.1–3.6
  after Omni View at 3; Vancouver/Collingwood 3.7/3.8; AI Chips 1.5; MAG 7
  6.5; Peptides/Longevity 2.1/2.2; Nerra Weekly 0.6; Nerra Dev 14.5).
- Show pages come from `show_page.html.j2` unchanged (the DP Pod bespoke
  page is the one exception on the network and stays so); the Latest
  Episode card, transcript box and topic links come for free.
- `/mira.html`: role list computed from `host == mira`; the claim block
  untouched; a "Mira also reads the news" section listing the desks and
  the local shows with the plain statement that those are automated
  briefs without a human gate — the honest version of the distinction the
  claim already draws.
- Feed descriptions (Apple/Spotify text): written per show in §4 voice;
  weekly shows never contain "daily"; the guard sweeps every public
  string field.

---

## 6. Schedule

Allowed minutes {1,7,16,31,37,46}, hours 06–12 UTC
(`tests/test_scheduling_punctuality.py:53`, `test_schedule.py:106`);
12:07 is the edition dispatch. Free slots today: 26 of 42.

| UTC | Show | Filter | Note |
|---|---|---|---|
| 06:07 | privet_russian (existing) | monday | |
| 06:16 | omni_view_asia_pacific | daily | 16:16 AEST |
| 06:31 | omni_view_africa_mideast | daily | 09:31 EAT / 08:31 SAST |
| 06:46 | omni_view_europe | daily | 08:46 CEST |
| 07:01–09:16 | ten existing dailies | | unchanged |
| 08:07 / 09:37 / 09:46 / 10:01 | env_intel / finansy_prosto / dp_pod / offshore_north | monday | unchanged |
| 09:31 | ai_chips | daily | |
| 10:07 | collingwood | friday (monday fallback) | 06:07 ET |
| 10:16 | omni_view_north_america | daily | 06:16 ET |
| 10:31 | omni_view_latam | daily | 07:31 BRT/ART |
| 10:46 | mag7 | daily | 06:46 ET, pre-market |
| 11:01 | longevity | wednesday | |
| 11:07 | peptides | thursday | Checked in Phase 0: the scheduler Worker takes the FIRST `SLOTS` row matching h:m, so every weekly needs its own minute |
| 11:16 | prediction_markets | daily | 07:16 ET; added 23 Sep (§4.11) |
| 11:37 | nerra_dev | sunday | |
| 11:31 | omni_view_world | daily | after every desk's 50-min budget |
| 12:16 | vancouver | daily | 05:16 PDT |
| 13:23 | nerra_weekly | sunday | own workflow, not CRON_MAP |

Consequences:

- `CRON_MAP` grows 15 → 27 (`test_scheduling_punctuality.py:59` pins
  the count; update per phase). Worker `SLOTS` mirrors it; the wrangler
  cron string is unchanged.
- **Nerra Daily lineup:** none of the new shows joins at launch; each is
  listed in `tests/test_daily_edition.py:52-62` as explicitly excluded
  with the reason (a 2-hour edition would become 3.5 hours; the desks are
  a candidate SECOND edition, `EDITIONS["world"]`, which the spec supports
  as a new spec + prompt — an operator decision after the desks have
  audience data).
- **Daily audit:** `FEEDS` entries per show (48h dailies except Vancouver
  at 60h given its late slot; ≥192h weeklies); the review catch-up cap of
  10 per run (`review_episodes.py`) is raised to 16 — the backlog rule was
  written for 15 shows.
- **Review rotation:** 14 new targets with `last_reviewed` = launch date
  so Tue/Fri rotation reaches them in order without starving the existing
  shows; the Daily Audit's out-of-rotation dispatch (max 1/day) covers
  editorial-critical issues on a new show earlier.
- **Runner load:** three shows every fifteen minutes 06:16–07:01, then
  the existing slate; peak concurrency ~5 jobs. Push contention on `main`
  (landmine #23) rises with 24 daily commits — the 4-attempt loop and the
  recovery-PR path already handle it; watch `recovery/` branches in week 1.

---

## 7. Cost, capacity and distribution

**Per-episode reference (last 7 episodes, committed credit files):**
Omni View $0.56, Models & Agents $0.52 (+$0.19 FR), SpaceX $0.43 (+$0.34
dubs), Planetterrian $0.42. Of that, images are ~$0.14–0.26 and the
X-account fetch ~$0.09; LLM ~$0.06, TTS ~$0.13.

**Launch tier (no images, no video, no dubs, no X fetch, some web
search):** ~$0.22–0.28 per episode.

| | Episodes / month | $ / month |
|---|---|---|
| 9 dailies | ~270 | ~$68 |
| 4 YAML weeklies | ~17 | ~$5 |
| Nerra Weekly | ~4 | ~$2 |
| **Total at launch** | | **≈ +$75** (today's tracked burn ~$160 + ~$60 multilingual) |
| Full tier later (13 Grok images + FR track + video render) at ~$0.70 | | ≈ +$200 |

Top-level `max_weekly_cost_usd` on every new show bounds a bad week to
roughly double its expected cost. Actions minutes are free (public repo).

**YouTube:** EN channel ~24 uploads/day vs the 30/day cadence ceiling
(`SAFE_DAILY_UPLOADS_PER_CHANNEL`). Decision path: (1) off at launch for
all fourteen; (2) after four weeks of RSS data, AI Chips and MAG 7 may join
the EN channel at one Short each (+4/day incl. long-form → 28); (3) the
six desks plus the two local shows go to a NEW channel only — the
credential resolver is generic (`channel: xx` → `YOUTUBE_REFRESH_TOKEN_XX`),
so a `@NerraWorld` channel is a secret, a `SEED_TIERS` entry and
`YOUTUBE_ENABLED_SHOWS`; (4) Peptides/Longevity stay off until a
policy review. `youtube_quota_preflight.py` counts every enabled show as
daily — fine, it is conservative.

**Newsletter:** off at launch; each show's Buttondown tag is added to the
Worker allow-list when it turns on. **Multilingual:** off; the RU/FR
economics are read per language on the dashboard card first.
**X:** off (no handles).

---

## 8. Rollout phases and PR sequence

**Implementation status (updated as work lands):**

- **Phase 0 — shipped** on `claude/funny-lovelace-2nskcy`: hook articles,
  AI-host disclosure, named-weekday cadence, scaffold repairs, strand
  grouping, cover generator (`tests/test_new_shows_2026_09.py`).
- **Phase 1 A-parts — shipped** on the same branch: AI Chips, MAG 7,
  Peptides, Longevity are scaffolded and on the site as "Not published yet"
  pages, dispatchable by hand, and NOT on a cron. Found during the build and
  handled: (1) a registered show with no episodes would be reported "missed"
  by the daily audit and auto-retried, publishing Episode 1 unheard — new
  `review_episodes.PRELAUNCH_SLUGS` keeps them out until each show's B-PR;
  (2) curricula live in `shows/curricula/`, not `shows/topic_queues/`, so the
  restock automation and runway guards never touch them; (3) the health
  spotlights fetch real Europe PMC abstracts as hook articles, because the
  claims gate would otherwise strip an unsourced spotlight to nothing;
  (4) hub pages skip a show with no feed file; (5) the pre-launch band on a
  show page no longer assumes the show takes guests.
- **Phase 1 B-PR — shipped 2026-09-23** (this branch, after all four
  Episode 1s published and two review rounds, §9a): AI Chips daily 09:31,
  MAG 7 daily 10:46, Longevity Wednesday 11:01 (first scheduled run
  2026-09-30), Peptides Thursday 11:07 (first scheduled run 2026-10-01).
  The first-run date exists because a weekly's hand-made Episode 1 lands
  mid-week and its first cron would otherwise fire the next day on the
  same week of news; it lives in three places that a guard keeps equal
  (run-show gate `FIRST_SCHEDULED_RUN`, Worker `FIRST_RUN`, registry
  `first_run`). The Worker change goes live only on `wrangler deploy`.
  Deliberately NOT in this B-PR: `engine/network_promo.py` rotation (adding
  four shows changes every existing show's spoken outro rotation — an
  audio change on thirteen shows, landmine #17, and the stride-3/pool-13
  echo guard needs re-deriving); the Phase 2 A-PR does it for all new
  shows at once, with an A/B listen.
- **23 Sep 2026 operator brief — shipped** (§9b): grok-4.7 on the four
  Phase 1 shows' writing stages, MAG 7 and AI Chips moved off prices and
  earnings calendars onto developments and research, Longevity and Peptides
  moved from the drug pipeline to education (Worth Knowing section, new
  sources, curricula reordered). A/B-listen the next episode of each.
- **Phase 2 A-parts — shipped 2026-09-23** (Vancouver Daily News, Collingwood
  Weekly; guards `tests/test_new_shows_phase2_2026_09_23.py`). What the build
  settled: (1) roads and weather arrive as sourced hook ARTICLES from
  keyless public data (`engine/local_conditions.py`: DriveBC Open511 filtered
  to a Metro Vancouver box — the "Lower Mainland District" runs to Hope;
  Ontario 511 filtered to the south Georgian Bay; Environment Canada's
  location Atom feed, because the `/rss/city/` path the plan named is 404);
  a data-less day is one honest sentence; (2) Mira's voice ships with **no
  speech wrap**, the voice Nerra Daily listeners already know — the plan's
  with-and-without render needs a key this build did not have, so Episode 1
  is that listen and the wrap is a two-line flip; (3) voice-only audio sets
  `intro_duration: 0` so chapter times carry no phantom music offset;
  (4) Village Media titles use `/rss/local-news` — the bare `/rss` is a
  network aggregate that led every title with the same wire story;
  (5) a `local-news` topic hub exists and stays unbuilt until 12 episodes;
  (6) Collingwood's X fetch is off until its handles are verified;
  (7) `/mira.html` still lists Mira's three original shows — the desks join
  its copy in their B-PR, once they have episodes, never as "launching soon";
  (8) hook articles that carry their own text are now rendered whole, outside
  the full-text cap (`engine.article_text.enrich_articles_with_full_text`):
  merged last, they had fallen outside the first-N slots on any busy day —
  the road list would have reached the prompt as one line, and the health
  shows' Europe PMC abstracts had been reaching it as 600 characters.
  Still deferred, deliberately: `engine/network_promo.py` rotation for all
  the new shows at once (an audio change on thirteen shows — its own PR with
  an A/B listen, after the Phase 2 Episode 1s).
- **Phase 2 Episode 1s — FAILED 2026-09-23, not heard yet.** Both runs died in
  the digest stage on grok-4.7: the 10-token pre-flight ping timed out at
  30 s, then three digest attempts each hung ~260 s until xAI dropped the
  connection. No committed credit file anywhere records a grok-4.7
  completion — Omni View's script-stage pin had fallen back to grok-4.3 on
  its first run because the script stage has a fallback and the digest stage
  did not. Fix (separate PR): a pinned model that fails the ping or the
  digest call switches the run to grok-4.3, sticky for the process, and
  records `llm_model_pinned` / `llm_model_fallback`. The pins stay (the
  operator wants 4.7); an episode that fell back is not a 4.7 data point.
  AI Chips and MAG 7 were on the same path from their first grok-4.7 cron.
- **Phase 2b A-parts — shipped 2026-09-23** (Prediction Markets Daily,
  Patrick; guards `tests/test_prediction_markets_2026_09_23.py`). What the
  build settled: (1) The Board is one hook article PER MARKET
  (`engine/prediction_board.py`), so every board line cites its own market
  URL; Polymarket's events endpoint is sorted server-side by 24-hour volume
  and carries tags; Kalshi's is NOT sorted, returns thousands of events and
  answers HTTP 429 to a fast crawl, so it is paged slowly (≤20 pages, one
  retry) and ranked from what was read; Manifold is play money and its top
  volume is perpetual contracts, so only binary markets with ≥100 traders;
  (2) filters by rule — sports and esports tags / categories, recurring
  price ladders, tweet counts, Kalshi numeric strike ladders and parlays,
  and near-certain markets (the first live read put "will the US confirm
  aliens exist" on the board at 3.1%); mutually exclusive outcomes are
  ranked by price, a "by…?" date ladder keeps its own order; volume is
  reported in each venue's own unit (Kalshi's is contracts), never
  converted; (3) board text is the pipeline's own copy, which the claims
  gate treats as sourced, so it carries a neutral access line and NO
  specific legal claim — legal facts come from dated news articles only;
  (4) How It Works is a 23-subject curriculum
  (`shows/curricula/prediction_markets.yaml`, about three weeks of dailies;
  the hook warns under seven) with real abstracts from Crossref and arXiv
  (`engine/research_papers.py`) — Crossref's citation sort returns AlphaFold
  for "prediction markets", so results are filtered on TITLE first and then
  ranked by citations; every subject's query was run and returned ≥2
  on-subject papers; OpenAlex and Semantic Scholar answered 429;
  (5) Google News for Kalshi / Polymarket is saturated with sportsbook
  promo-code pages — title filters match the affiliate shapes and a guard
  checks real regulatory headlines still pass; (6) the Board is NOT
  content-tracked (a live market can lead for weeks); (7) the not-advice
  and gambling-help lines live in the verbatim closing. Cover glyph
  "gauge"; accent `#A21CAF` inside the markets family (AI Chips owns
  `#4338CA`). Episode 1 waits for the pinned-model fallback to merge.
- **Phase 2 / 2b Episode 1s — published 2026-09-23.** Vancouver (on grok-4.3:
  the 4.7 digest call still timed out at default effort), then Collingwood
  and Prediction Markets on grok-4.7 end to end at `reasoning_effort: low`
  (147 s and 445 s pipelines; scripts 3.5-6% verbatim against the digest,
  the lowest on the network). Defects found and fixed: the pre-dedup cap
  sliced off the two hook articles (Vancouver shipped no forecast); the
  debut explainer tripped the Getting Around chapter anchor at 16 s (new
  `where: body`); the entity dedup read the TOWN as every headline's entity
  (`entity_dedup_ignore`); the digest expansion retry emptied the claims
  ledger on ~78% of the network's expanded episodes (draft ledger carried
  over); the generic debut line dropped Mira's identity, so neither Mira
  debut named her until the closing; Prediction Markets used 5,384 of a
  5,500-token digest budget on 4.7 and its ledger never arrived (every 4.7
  show now 8,000); a "two sentences minimum" rule padded headline-only
  items with "the report is about…" (now one fact, one sentence); board
  volumes were read to the dollar (now rounded). Open: Vancouver's items
  lost their commas on 4.3 (a sporadic 4.3 habit, also on FF/MIT/SpaceX);
  Collingwood ran 4.5 minutes on a thin Wednesday — its Friday slot is the
  real test.
- **Phase 3 A-parts — shipped 2026-09-23** (the five Omni View desks and Top
  World; guards `tests/test_phase3_desks_2026_09_23.py`). What the build
  settled: (1) ONE definition — `engine/omni_desks.py` holds each desk's
  sub-regions, seeded arcs, accent and the anti-tabloid filters (Omni View's
  nine plus live blogs, galleries, quizzes, obituaries), and every registry
  (intros, first-episode, validation, tracker, memory, covers) loops over
  it; (2) ONE format — `shows/prompts/_shared/omni_desk_*.txt`, with the
  region file (`shows/prompts/omni_desks/`) the only per-desk prompt text;
  system prompts are read raw (no includes), so they are written from one
  template; (3) no `keywords:` on any desk — the feeds are regional and a
  title filter would drop stories whose titles name no country; (4) the
  sub-region balance note names only the sub-regions the last ten digests
  never reached, as a preference, never a quota; (5) **Top World verifies
  against the publisher, never a sibling digest**: each desk's Lead and
  first regional item become hook articles carrying only the headline and
  the ORIGINAL publisher URL, text-less hook articles take the first
  page-fetch slots, and the desks' summaries reach the prompt only as a
  ranking note the claims gate never reads; ≤ 10 desk articles, under the
  12-article hook cap; (6) segment anchors (`across the region`, `the wider
  world`, `the case on both sides`, `a sign of progress`) are `where: body`;
  (7) a globe cover glyph lights each desk's region. Feeds probed from the
  session egress on 23 Sep (LatAm thinnest, as planned; Kyiv Independent,
  Euractiv, Times of Israel, Americas Quarterly, Focus Taiwan and Colombia
  Reports did not answer). Episode 1s wait on the operator's dispatch.
- **Each B-PR** (after Episode 1 is heard): CRON_MAP + `- cron:` line +
  Worker SLOTS row (unique minute) + move the slug from `PRELAUNCH_SLUGS`
  into `SHOW_REGISTRY` + daily-audit FEEDS limit + `ALT_CADENCE_SHOWS` /
  `DAILY_SHOWS` + `network_promo` + adjacency siblings + hub snapshot.

Each show's launch is two PRs: **A** (scaffold + prompts + hook + registry +
tests + `--test` digest pasted in the PR body) merged → Ep1 by
`workflow_dispatch` → operator listens → **B** (CRON_MAP + Worker row +
audit entry + review registry + cadence copy) merged. Nothing is on a cron
before its Ep1 has been heard. Two `--test` digests on consecutive days
precede every Ep1 (read for tics, section shape, region purity).

| Phase | Week | Ships | Gate to next |
|---|---|---|---|
| 0 | 1 | §2 enablers + scaffold repairs + strand chrome + brand-cover generator; `tests/test_new_shows_2026_09.py` guards (hook articles, host-aware disclosure, weekday filters, count derivation) | CI green; `--all` render byte-identical for existing pages except the nav grouping |
| 1 | 1–2 | AI Chips, MAG 7 (daily, Patrick); Peptides, Longevity (weekly, Patrick) | four Ep1s heard; MAG 7 price line verified on a weekend and a Monday pre-open; no Tesla double-coverage flag on day 3 |
| 2 | 2–3 | Vancouver Daily (Mira calibration set), Collingwood Weekly | Mira Ep1 with/without `<fast>` chosen; disclosure heard; spoken-text gate `opening_match` healthy on `ara`; `check_feeds.py` from a runner ≥ B on the anchor feeds |
| 2b | 3 | Prediction Markets Daily (Patrick; §4.11) | Ep1 heard; the board is ≤5 markets and the episode is developments-led; no pick language in the transcript |
| 3 | 3–4 | five regional desks (A-PRs together, Ep1s over two days), then Top World | region purity read on 3 episodes each; Top World's hook articles present in `articles_from_hook`; Omni View's own audience unchanged after two weeks (ledger prediction) |
| 4 | 4–5 | Nerra Weekly (edition generalization + workflow), Nerra Network Developments | first Weekly heard end-to-end; clip boundaries land on sentence ends on 10/10 segments; Dev Ep1's every claim `fetched_copy` |
| 5 | 6+ | readouts: `<slug>-launch` experiments at four weeks; YouTube decisions (§7); Nerra World edition decision; music commissions land as they arrive | |

Every prompt in phases 1–4 is landmine-#17 A/B; the engine changes in
phase 0 are removal-only or additive and are not.

---

## 9. First-episode playbook (all fourteen)

1. Ep1 forces two-pass generation (`generator.py:1715-1718`) and gets
   the `_SHOW_DIGEST_EP1` / `_SHOW_PODCAST_EP1` override: a ~250-word
   "what this show is" section directly after the hook, then a NORMAL
   episode. The override describes shape (what leads, what is promised,
   what is out of scope); it never supplies a sentence to say.
2. Mira shows disclose the AI host inside the first thirty seconds and at
   the close. Patrick shows use the standard identity line.
3. No cross-network tour, no catalogue read, no "last week", no
   editorial-standards boilerplate (the DP Pod Ep1 lesson, three renders
   deep).
4. The debut section is where each show's BOUNDARY is spoken once as a
   promise: MAG 7 vs Tesla Shorts Time, AI Chips vs Models & Agents, the
   desks' region rule, the health shows' posture, Top World's "ten across
   regions".
5. The operator listens to Ep1 in full before PR B. A retired Ep1 is
   retired the DP Pod way: artifacts deleted, RSS item removed, numbering
   back to 1, regenerated by dispatch (the duplicate guard does not apply
   to dispatch).
6. `scripts/review_snapshot.py <slug>` runs on Ep3 and Ep7 (length,
   tics, chapters, cost) and the ledger's first predictions are scored at
   the four-week review.

### 9a. What the Phase 1 Episode 1s taught — apply to every later show

Four shows, seven production attempts, two review rounds (22–23 Sep; guards
`tests/test_new_shows_ep1_review_2026_09_22.py`,
`tests/test_new_shows_ep1_round2_2026_09_23.py`; ledgers carry the
predictions). Each line is now either engine behaviour every show gets, or
a default the Phase 2+ A-PRs copy.

**Engine (every show gets it; nothing to copy)**
- Chapters cover the opening even when the start marker misses (AI Chips
  and Longevity Ep1 began at 343 s / 326 s).
- The debut intro no longer re-reads the hook, and the dedup splitter no
  longer cuts after "U.S." (MAG 7 Ep1 opened on that one word).
- Europe PMC research slices take the most-cited REVIEWS first, MEDLINE
  only (Peptides Ep1's insulin spotlight explained rats and sheep).
- A hook never caches to `api/<slug>.json` — that path is the public
  episode API; the collision sent MAG 7 Ep1 to a recovery PR.

**Defaults every new news show's A-PR sets (copy from `shows/mag7.yaml`)**
- `absence_sentence_filter: true` — drops "No X was disclosed" sentences,
  empty item headings, and spoken-domain attribution lines (8 of AI Chips'
  10 items; MAG 7's empty Microsoft item; Peptides' "x dot com" line).
- `fetch_full_text: 12` — items written from teasers came out two
  sentences long and padded with absence sentences.
- `x_fetch_enabled: true` + `x_accounts` that POST DAILY — newsrooms,
  beat reporters, aggregators. MAG 7's first run: four chief executives
  and a brand account returned nothing in 24 hours; Mark Gurman and the
  NVIDIA newsroom carried the news. Weeklies set `x_lookback_hours`. Read
  the first run's per-handle counts and prune.
- `llm.min_podcast_words` set to what the format's digest supports, not an
  aspiration: the skip floor is 60 % of it, and three of seven Ep1 attempts
  skipped against targets 15–25 % too high (MAG 7 now 1,100; AI Chips
  1,300; weeklies 1,200).
- Every podcast prompt carries the COVERAGE rule ("every item in the
  briefing is told … the floor, not a menu") and a shape-only
  story-coverage ratio. Without it the script told a 1,100-word digest in
  660–700 words.
- The start marker's pattern includes `first episode of` so the debut is
  chaptered like every later episode.

**Editorial rules the Phase 1 prompts had to learn (write them in on day one)**
- Scope is a rule, not a keyword: Longevity's bare `trial` keyword let in
  three unrelated Phase 3 wins; its prompt now states what is in scope.
- An X post is a pointer, not a source, unless it names the drug, trial or
  number; a hook names the subject, never "an investigational medicine".
- A deep section (Thread / Teardown / Spotlight) uses only the day's
  articles for numbers and never re-tells an item — both MAG 7's Thread
  and AI Chips' Teardown did, the latter with figures from memory.
- Curriculum searches are run LIVE before launch (all 52 were, after the
  insulin miss); ambiguous title terms ("history") are banned.
- Price tapes say the session date once, and a run after the close must
  carry that day's close.

**Process**
- `--test` stops at the digest: the SCRIPT stage — where three of seven
  attempts failed — is only exercised by a real run. Budget two Episode 1
  attempts per show, and read the skip marker, not the run's colour.
- A run that exits through the recovery-PR hatch is GREEN; check main for
  the `Auto-generated: <slug>` commit before calling an episode published.
- A weekly's B-PR names its first scheduled run date (above).

---

### 9b. The 23 Sep 2026 operator brief — useful, interesting, timely

The Phase 1 Episode 1s were well sourced and still spent their best minutes
on the wrong things: MAG 7 opened on seven closing prices and earnings dates
a month away, and the health shows' weeks were drug-company news. The
operator's direction binds every show from here:

- **Every new show runs grok-4.7** on its writing stages (`llm.model` — digest
  and script in one combined call). The new shows are the proving ground;
  lessons carry to the established shows only through the playbook's
  one-show-first rule. Fetch stays on grok-4.3. Revert per show = delete the
  line. Read `python scripts/model_trial_report.py --since 2026-09-24
  --shows <new shows>` before any widening.
- **Interesting first.** Every new show's digest includes
  `shows/prompts/_shared/interesting_first.txt`: rank by NEW, USEFUL,
  CONSEQUENTIAL; market noise (price moves, market-value milestones, analyst
  targets, earnings previews, dates weeks away) is not news; an announcement
  about a future announcement earns one sentence inside a real item at most;
  research counts when it is published inside the window. Shape-only — it
  quotes no sentence to copy.
- **Market shows are about what companies and markets DO.** Prices survive
  only as reader-only data at the foot of a digest (MAG 7's Tape) or a
  capped board (Prediction Markets' five markets). Earnings calendars are
  gone. Research blogs are sources.
- **Health shows teach.** Human findings a listener can understand and use,
  how the biology works, consumer protection; commercial pipeline news is at
  most one item a week and only with a human result or a regulator's
  decision. A "Worth Knowing" section gives the plain-language meaning of the
  week's human evidence — never an instruction, dose or product.
- **Local shows are useful the same morning:** the roads and the forecast
  from public data, the decisions that change something here, and one issue
  argued fairly both ways.

## 10. Operator decisions (the plan proceeds on the first option)

1. **Nerra Network Developments host:** Patrick (assumed) or Mira.
2. **Named-weekday cadence (§2c):** build it (assumed) or run all five
   weeklies on Monday.
3. **Top World vs Omni View:** ship Top World as specified (assumed), or
   also rename the existing show ("Omni View: The Steel Man") to signal
   the split, or fold Top World's job into Omni View and drop it.
4. **Desk spelling:** "Omni View Europe" (assumed) vs "Omniview Europe".
5. **Mexico:** on the North America desk for US–Mexico affairs and on the
   C&S America desk for domestic stories (assumed), or one desk only.
6. **Spanish/Portuguese sources for the LatAm desk:** English-only at
   launch (assumed); a fetch-side translation step is new work.
7. **PubMed saved-search RSS URLs** for Peptides and Longevity (operator
   creates; the key is UI-generated).
8. **Second YouTube channel** for the Mira desks — name and timing
   (data decision after week 4, assumed).
9. **Music commissions** (§5c) — three Suno briefs.
10. **Nerra World edition** (the six desks spliced, Mira anchoring) —
    after the desks have four weeks of audience data.
11. **Apple/Spotify/Podcast Index submissions** per show once Ep3 exists
    (the OP3 404-until-indexed lag applies to every new feed; six of the
    existing paid language feeds are still unmeasurable for this reason).
12. ~~**Prediction Markets Daily host:** Patrick (assumed, markets strand) or
    Mira.~~ **Decided 2026-09-23: Patrick.**
13. **A "local" music theme** for Vancouver and Collingwood (voice-only at
    launch) — a Suno brief like §5c's.

---

## Appendix A — per-show registration checklist

Tick every row for every YAML show (registry-only shows: rows marked ★).

**Files**
- `shows/<slug>.yaml` (sources with `window_hours` on weeklies; `min_articles_skip`; top-level `max_weekly_cost_usd`; `tts` voice + wrap; `publishing.host_name/host_kind/rss_author/rss_link` (hyphen page); complete `youtube` block with ≥3 `image_queries` + `image_provider: grok` + `shorts_start_mode: smart` + threshold 3.5 even while disabled; `newsletter` block with tag; `slow_news` library or disabled; `content_tracking.section_patterns` or registry entry)
- `shows/prompts/<slug>_{system,digest,podcast,weekly}.txt` (weekly template repaired; `content_discipline` include; no quotable specimen)
- `shows/hooks/<slug>.py` where §4 names one
- `shows/topic_queues/<slug>.yaml` (Peptides, Longevity)
- `shows/segments/<slug>.json` slow-news library
- `digests/<slug>/.gitkeep`, `blog/<slug>/.gitkeep`
- `assets/covers/<slug-hyphen>.jpg` + `.webp` + `-800/-400.webp` ★
- `<slug-hyphen>.html` rendered before merge (rss_link guard) ★
- `docs/reviews/ledger/<slug>.yaml` ★; `docs/experiments.yaml` entry ★

**Registry & copy** ★
- `shows/network_meta.yaml`: full entry with `strand`, `host`,
  `display_order`, `picker_tags` in hub vocabulary, `about_host`,
  `related_show` + matching `related_reason`, `schedule` string that agrees
  with CRON_MAP, `meta_description`, `source_highlights`
- `docs/reviews/review_state.yaml` target (YAML shows only)
- `shows/_defaults.yaml` `newsletter.network_adjacencies[<slug>]`
- `shows/_producer_policy.yaml` `pitched_show_names` (if the show accepts pitches; the count is pinned)
- `engine/network_promo.py` `ENGLISH_SHOWS` + `ENGLISH_ORDER`
- `engine/intros.py` `_SHOW_PERSONALITIES`
- `engine/first_episode.py` overrides
- `engine/content_tracker.py` `SHOW_SECTION_PATTERNS`; `engine/validation.py` `SHOW_VALIDATION_CONFIGS`; `engine/show_memory.py` `SHOW_MEMORY_CONFIGS` where memory is on
- `engine/newsletter_template.py` `_SLUG_TO_BRAND_CLASS` (when newsletter on)
- `workers/gallery/src/handlers.ts` `SHOW_NEWSLETTER_TAGS` (when newsletter on)
- `.github/workflows/weekly-newsletter.yml` options; `generate_network_rss.py` `FEEDS`; `scripts/submit_to_directories.py`; `pipelines/voices/validators/schema_validators.py` `KNOWN_SHOWS`
- `templates/start_here.html.j2` section lists (review)
- `scripts/generate_dashboard.py` `_VIRTUAL_COST_SLUGS` (registry-only only)
- `engine/daily_edition.py` + `tests/test_daily_edition.py`: explicit exclusion with reason

**Cadence (six places + tests)**
- `run-show.yml` CRON_MAP + `- cron:` line + `workflow_dispatch` options + `all` list
- `workers/scheduler/src/index.ts` SLOTS
- `review_episodes.py` SHOW_REGISTRY (schedule, sections, floors)
- `daily-audit.yml` FEEDS limit
- `scripts/generate_dashboard.py` `_PUB_AGE_THRESHOLDS_H` (until derived)
- registry `schedule` + `rss_description` never say "daily" on a weekly
- `tests/test_schedule.py` DAILY_SHOWS / ALT_CADENCE_SHOWS; `test_scheduling_punctuality.py` count; `test_mit_benchmark_integrity.py:2698` coverage; `test_show_count_consistency.py`; `test_registry_pass_2026_09_21.py` count + hub snapshot; `test_mira_pass_2026_09_20.py` (strand set unchanged)

**Whitelists**
- new `api/<slug>_<name>.json` (NEVER `api/<slug>.json` — that is the public episode API) in the run-show commit step AND `nightly-maintenance.yml` `add-paths`
- new per-show pages in nightly `add-paths` where the glob does not cover them

**Pre-launch checks**
- `python scripts/validate_show.py <slug>`; `python check_feeds.py <slug>` FROM A RUNNER (Actions), anchors ≥ B; `--check-blocked` clean
- `python run_show.py <slug> --test` on two consecutive days, digests read
- §9a defaults present: `absence_sentence_filter`, `fetch_full_text`, daily-posting `x_accounts`, a realistic `min_podcast_words`, COVERAGE + shape block, `first episode of` in the start marker
- §9b present: `llm.model: grok-4.7` (and the slug added to `NEW_SHOWS_47_ARM` in `tests/test_grok_47_migration_2026_09_21.py`), `<<include: _shared/interesting_first.txt>>` in the digest prompt, no price tape or calendar spoken
- curriculum/research queries run live and read
- Ep1 by `workflow_dispatch` (budget two attempts); the `Auto-generated` commit is on main; listened; then PR B (weeklies: `first_run` date in the three places)

## Appendix B — feed probe (22 Sep 2026, via this session's proxy)

Status codes from a non-runner egress; 403/401 from AP, NPR, Politico,
CNBC, Reuters, WSJ, FDA, NIH, Times of Israel, The East African, News24
and Euractiv should be re-tested from Actions before being called dead.

**Working (feed parsed, fresh within 48h unless noted):**

- *Vancouver:* CBC BC · Vancouver Sun · The Province · Global BC ·
  CityNews Vancouver · Daily Hive (`/feed/vancouver`) · Vancouver Is
  Awesome · Georgia Straight · The Tyee · BIV · North Shore News ·
  Richmond News · Delta Optimist · Squamish Chief · VPD · UBC News ·
  CanucksArmy · DriveBC Open511 JSON (200; hook) · Sportsnet NHL feed
  (stale Jul 2025 — drop)
- *Collingwood:* CollingwoodToday · Bayshore Broadcasting · Simcoe.com
  search RSS · County of Simcoe · Midland Today · Bradford Today · Orillia
  Matters (BarrieToday timed out)
- *Chips & DC:* SemiAnalysis · Tom's Hardware · ServeTheHome · Next
  Platform · HPCwire · EE Times · Semiconductor Engineering · Semiconductor
  Digest · TechPowerUp · DCD · Data Center Knowledge · Utility Dive · NVIDIA
  blog · NVIDIA releases.xml · IEEE Spectrum semiconductors (weekly-ish) ·
  Semafor (general) · The Register on-prem atom (stale May 2026 — drop)
- *MAG 7:* Google blog · About Amazon · Apple Newsroom · Meta Newsroom ·
  Microsoft blog · NVIDIA releases · Yahoo Finance multi-ticker headlines ·
  Yahoo top stories · The Information · FT technology · Bloomberg technology
  · MacRumors · 9to5Google · 9to5Mac · Android Authority · GeekWire ·
  Stratechery · Ars · The Verge · TechCrunch · MarketWatch top ·
  Investing.com (news_25) · WSJ markets RSS (stale Jan 2025 — drop)
- *Peptides / Longevity:* Fight Aging! · Lifespan.io · Nature Aging ·
  Aging Cell (Wiley 14749726) · Cell Metabolism · ScienceDaily healthy
  aging / hormone / health-medicine · STAT · Endpoints · Fierce Biotech ·
  BioPharma Dive · Peptides (ScienceDirect) · J Peptide Science (Wiley
  10991387, thin) · Europe PMC search JSON (hook) · NIA news RSS (stale Feb
  2026) · Buck Institute (stale Aug) · Peter Attia (opinion)
- *World desks:* BBC World/Europe/Asia/Africa/Middle East/Latin
  America/US&Canada · Guardian World/Europe/Asia/Africa/Americas/Middle
  East · Al Jazeera · France 24 Europe/Africa/APAC/Americas/Middle East · DW
  World/EU/Asia/Africa · Euronews · SCMP · Nikkei Asia · Japan Times · ABC
  Australia · CNA · Straits Times Asia · The Hindu international · Korea
  Herald · Yonhap · SMH world · RNZ world (thin) · Times of India world ·
  Hindustan Times world · Irish Times · Balkan Insight · Moscow Times ·
  MercoPress · Buenos Aires Times · Mexico News Daily · Rio Times · Colombia
  Reports · Jamaica Observer · Arab News · Middle East Eye · Haaretz · Daily
  Maverick · Premium Times · Punch · Nation (Kenya) · Daily News Egypt · CBC
  top/world · PBS NewsHour · NYT World · LA Times world-nation · Globe and
  Mail world · Global News world

**Not usable as probed:** AnandTech (HTML) · Data Center Frontier `/rss`
(404) · Register data-centre atom (404) · CNBC (403) · Reuters (401) · WSJ
tech (401) · Bloomberg `/feeds/technology.rss` (404) · Tesla blog/IR (403/404)
· Alphabet IR (403) · NVIDIA IR (403) · FDA press (401/403/404) · NIH (403)
· bioRxiv collections (404/429) · EurekAlert (404) · Medical News Today
(404) · New Scientist (406) · Longevity.Technology (202 challenge) ·
Aging-US (404) · A4M (403) · TransLink (404) · BC Gov News (timeout) ·
Environment Canada city RSS at the tried path (404) · CTV BC/Barrie (404) ·
BC Lions / Whitecaps (404/timeout) · Burnaby Now / Tri-City News `/rss`
(HTML) · New West Record (403) · Town of Collingwood / Blue Mountains /
Grey / OPP / Blue Mountain resort (404 or HTML) · Wasaga Sun (timeout) ·
AP (403) · NPR (403) · Politico / Politico EU (403) · Euractiv (403) · Kyiv
Independent `/feed` (404) · The Local (stale) · Mail & Guardian (404) · The
East African (403) · Times of Israel (403) · News24 (403) · Al Arabiya
(403) · The National (404) · teleSUR (404) · EFE (500) · Brasil Wire (HTML)
· Washington Post (timeout) · AllAfrica (timeout).
