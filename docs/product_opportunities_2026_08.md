# Nerra Network — Product Opportunities & Market Analysis

**Date:** 2026-08-18
**Scope:** Full review of the network's built assets (pipeline + content lake + data
+ infra) crossed with market research, producing a comprehensive, prioritized list
of sellable products that can be built and automated on what already exists.
**Supersedes:** the revenue-stream half of `docs/monetization_roadmap.md` (dated
Feb 2026, written when the network had ~60 episodes; its numbers are stale).
**Relation to existing docs:** builds on `docs/industry_benchmarks.yaml` (market
comps, cited), `docs/reviews/network_review_2026_07_18.md` (the "factory is
world-class, funnel is the product gap" verdict), and
`docs/dp_pod_market_assessment_2026_07.md` §5a (the patron model, already chosen).

---

## 1. What we actually have (asset inventory, 2026-08-18)

All numbers from live repo artifacts (`api/*.json`, manifests, code), not estimates
unless labelled.

### 1.1 The factory

- **89 engine modules, ~48,800 lines**, with **201 test files / ~69,200 lines**
  (~1.4 lines of test per engine line) and 31 GitHub Actions workflows + 3
  Cloudflare Workers (exact-minute scheduler, email-gated gallery, Voices API).
- Produces **81 episodes/week across 16 shows in 5 languages** at
  **$0.23/episode marginal cost** ($92.49 / 30 days, all-in tracked spend
  ~$110–125/mo including images + multilingual). 100% run success over the
  measured 30-day window; zero recovery incidents in the July 18 review.
- Config-driven: **a new show costs one YAML file** (`scripts/scaffold_show.py`
  generates YAML + prompts + output dirs + registry in one step).
- End-to-end surface coverage per episode: digest → TTS (single or two-voice
  dialogue) → music mix at broadcast loudness → RSS (Apple/Spotify 17/17 live)
  → blog post with JSON-LD → newsletter → X thread → YouTube long-form + up to
  3 Shorts (per-word captions, thumbnails, end cards, staggered publishing) →
  FR/RU/ES/ZH translation tracks + dubbed YouTube channels → funnel-tagged
  links everywhere → nightly analytics joins from 6 platforms.
- **Nerra Voices** (Age of AI pipeline): AI documentarian persona phones real
  guests (Voximplant → Grok Voice bridge), dual-track records, 8 schema-validated
  editorial passes, two human approval gates, full publish path. **Fully built,
  1 episode shipped** — the July review calls it "arguably the most defensible
  format in the portfolio."

### 1.2 The content lake and archive

- **1,462 episodes / 1,848,463 words** in the SQLite lake (FTS5 full-text search,
  `query_by_entity` / `search_content` / `query_show_range` APIs, 1,324 unique
  entities). 1,946 episodes published to feeds since launch; ~205 h finished
  audio (investor-view estimate); 1,481 blog posts (~13M words rendered HTML);
  82 RSS feeds with 3,005 items; 1,433 plain-text transcripts with word-level
  Whisper timestamps.
- **Narrative/story-arc data no one else has:** 10 narrative trackers, 13
  content trackers (spacex 252 KB, tesla 240 KB…), story-recurrence memory —
  structured "what has this beat done over 6 months" state for Tesla, SpaceX,
  AI models/agents, markets, climate policy.
- **MIT verified trading record:** 59 trade records with entry/exit bars,
  per-trade NASDAQ alpha, published reproducible methodology
  (`docs/mit_trading_method.md`, machine-readable `shows/_trading_policy.yaml`,
  fixed 5-session horizon, no discretionary exits), plus a dormant live/shadow
  execution stack (SnapTrade/Webull clients, 3 workflows). Honest headline:
  blended +9.28% vs NASDAQ across 45 trades, but **verified-window alpha is
  −1.95% and not statistically significant** — the sellable asset today is the
  *transparency machinery*, not the performance.

### 1.3 The image library

- **5,548 Grok-Imagine images**, 100% tagged **CC BY-SA 4.0** with attribution,
  every record carrying its **full generation prompt**, dimensions, R2 URLs,
  episode linkage, YouTube video ID. **3,603 images carry real YouTube retention
  scores** (`api/gallery_retention.json`) — a labelled prompt→retention dataset,
  not just a stock library.
- Delivery rail already built: email-gated Cloudflare Worker (Buttondown
  subscribe, magic-link login, JWT cookie, KV revocation, R2 proxy download).
  Swapping "email" for "Stripe customer" is a small change.

### 1.4 The audience (small but real, measured honestly)

| Surface | Number (30d unless noted) |
|---|---|
| Podcast downloads (OP3) | **5,767** (+88% vs July 18's 3,070) |
| Top shows | spacex 2,033 · tesla 870 · models_agents 778 · MAB 467 |
| YouTube lifetime views | 210,401 (RU 115,955 · EN 89,565 · FR 4,881) |
| YouTube 7d views | 45,528 (RU Shorts avg **361 views/video** vs EN 58) |
| YouTube subscribers | 498 across 3 channels |
| Spotify 30d | 457 streams / 160 listeners |
| Apple (spacex, 21d) | 969 plays / 293 listeners / 50 listening hours |
| Newsletter subscribers | **3** ← the funnel gap |
| Funnel attribution coverage | **0.0%** (instrumented, awaiting volume) |

Differentiation (July 18 review): **topical authority**, not format — Tesla +
Models & Agents + SpaceX = 53% of downloads, and beat-owner shows are the
fastest growers.

### 1.5 Monetization surfaces live today

Funnel instrumentation (closed campaign-ID vocabulary), sponsor + investor
dashboard views (tested), gallery email gate, newsletter engine (4,059 lines),
RU landing pages. **Nothing is currently sold: zero ads, no payment rail.**
`patron_url` in `shows/network_meta.yaml` is an empty field awaiting a link.

---

## 2. Market research summary

Key external numbers used below (full source list in §6):

- **Podcast ads:** US ad revenue $4.2B in 2026 (from $3.2B in 2024). Programmatic
  run-of-network $5–25 CPM (no minimum via Acast/Podcorn); host-read mid-roll
  $25–50; **finance/B2B niches $50–100+ CPM**, and shows with only ~1,000
  downloads/episode in finance/B2B can close direct deals because audience
  quality beats size. ~1,000 downloads/episode is the informal floor for
  approaching brands directly.
- **Paid newsletters:** median price $10/mo; **finance/investing newsletters on
  Beehiiv earn $3K–30K/mo at $20–50/mo** price points; top-decile finance
  free→paid conversion ~20%; B2B/marketing newsletters $2K–20K/mo. Diversified
  creators (subs + sponsorship + products) earn ~3× subscription-only.
- **Premium podcast subscriptions:** 2–5% of engaged listeners convert at
  $5–15/mo; Apple keeps 30%/15%; top 1% of subscription podcasts capture 63% of
  the revenue.
- **AI podcast SaaS:** Wondercraft $21/mo, Jellypod $25/mo, Podcastle $12/mo,
  NotebookLM free. All are *creation* tools — none operates the full
  fetch→script→voice→video→multilingual→distribute→measure loop as a managed
  service.
- **Branded/B2B podcast production:** agencies charge **$400–1,500/episode** or
  $2.8K–5K+/mo retainers; a business-outcome show budgets $30K–80K/yr. Internal
  employee podcasts are a named 2026 B2B trend.
- **AI dubbing/localization:** AI $0.55–2.40/finished-minute vs traditional
  $100–500/min; podcast industry ~$47B with 672M listeners wanting native
  language.
- **AI-moderated voice interviews (research):** ~$8–15/completed interview vs
  $150–300 human-moderated; platforms (Outset, Listen Labs) sell ~$20K/yr
  seats; Voicepanel from $99/mo. Market research industry ≈ $150B, AI-native
  the only double-digit-growth segment.
- **Consumer memory/legacy recording:** StoryWorth $59–199/yr (phone-interview
  features added 2026); Storii $99/yr; Tell Mel $26–229 — validated willingness
  to pay for exactly what Nerra Voices does (AI phone interview → produced
  narrative).
- **AI content licensing:** shifting from one-off training deals to per-use
  retrieval marketplaces; **Microsoft's Publisher Content Marketplace (launched
  Feb 2026)** lets small publishers set terms and get paid by consumption.
- **AI stock images:** Adobe Stock accepts labelled AI images (33% royalty);
  market is crowded (~58M new assets/yr) — raw stock is a weak product, but
  *niche + performance-labelled* datasets are differentiated.
- **Language learning:** language-learning podcast market ≈ $1.1B (2025) growing
  ~25% CAGR; online language learning $27B+ in 2026; app subscriptions $5–25/mo.
- **Stock-picks products (legal):** the Advisers Act "publisher's exclusion"
  covers impersonal, bona fide, regular-circulation publications; no
  personalized advice, clear disclaimers, no promotion of own advisory
  services. MIT's fixed-rules methodology fits the exclusion shape well.
- **Faceless/automation YouTube:** finance/tech RPMs $15–40/1k on long-form, but
  97% of automation channels never break even — channel ad revenue is a weak
  primary product; it's a funnel.

---

## 3. The product catalogue

Each product lists: what it is → asset it builds on → market evidence → price
shape → automation path → effort → honest risk. Ordered by tier, then priority.

**Read this first:** every audience-monetization product below is throttled by
the same constraint the July 18 review named — 5,767 downloads/30d, 3 newsletter
subscribers, 0% attribution. Products in Tier A monetize the *existing* audience
(small $, fast, validating). Tier B monetizes the *assets* (data, images,
record). Tier C sells the *factory* (highest ceiling, real sales work). Tier D
is licensing (low effort, low $). The recommendation in §4 sequences them.

### Tier A — Monetize the existing audience (weeks, near-zero build)

**A1. Programmatic podcast ads on the top feeds.**
- *Build on:* 17 live RSS feeds, OP3 prefix already on every enclosure.
- *Market:* programmatic $5–25 CPM, no download minimum via Acast free tier /
  Podcorn. At 5,767 downloads/30d → **$3–12/mo today**; the point is not the
  money, it's turning on the revenue-per-download metric so growth compounds
  into revenue automatically. At the investor-view base case (26,793
  downloads/mo in y5) this line alone is $1.6K–8K/yr.
- *Automation:* one-time feed enrollment; zero pipeline change (dynamic
  insertion happens host-side). Check R2-hosting compatibility — Acast-style
  monetization may require their hosting or a prefix-based DAI partner; pick a
  partner that works as a *prefix* (like OP3) so R2 enclosures stay canonical.
- *Effort:* days. *Risk:* low; keep host-read slots clean for A2/A4 later.

**A2. Direct sponsorship on the beat-owner shows (SpaceX, Tesla, M&A).**
- *Build on:* 53% of downloads concentrated in three topical-authority shows;
  sponsor dashboard view already built (`?view=sponsor`); YouTube demographic /
  geography / search-term data per channel is genuinely good sponsor collateral.
- *Market:* niche finance/B2B/EV-adjacent sponsors pay $50–100+ CPM and close
  at ~1,000 downloads/episode *in aggregate across a weekly flight*. SpaceX
  Daily at ~68 downloads/episode/30d isn't there per-episode yet, but a
  **network bundle** (all-shows monthly flight ≈ 5,800 impressions + 45K weekly
  YouTube views) is a sellable $200–500/mo test package for space/EV/AI-tool
  brands.
- *Automation:* the ad read is a digest-side prompt insertion (a "sponsor
  block" field in show YAML, injected like the network-promo rotation) — but
  **anything spoken passes landmine #17 (A/B-listen) once, then runs
  automatically**. Sponsor reporting = the existing sponsor view + funnel
  campaign IDs (`utm_content` vocabulary already closed — add a
  `PLACEMENT_SPONSOR`).
- *Effort:* 1–2 weeks build; ongoing sales effort is the real cost.
- *Risk:* medium — sales time; small inventory. Do after A1 proves the metric.

**A3. Membership / patron rail (network-wide, DP Pod model).**
- *Build on:* `docs/dp_pod_market_assessment_2026_07.md` §5a — the model is
  already chosen ($5 Patron / $15 Founding Patron, belonging-not-access,
  nothing paywalled), and `patron_url` exists in the registry awaiting a link.
- *Market:* 1–5% of engaged listeners convert at $5–15/mo. Against ~160–300
  engaged listeners today → **$25–150/mo initially**; scales with downloads.
- *Automation:* Stripe Payment Link or Buttondown paid tier (zero code), Patron
  Wall page generated by the existing site build, on-air thanks via the
  rotation-memory pattern (data-side, like `_recent_levers`).
- *Effort:* days for the link + wall; the on-air element passes landmine #17.
- *Risk:* low. This is also the honest test of whether the audience *wants* to
  pay — informs every Tier B pricing decision.

**A4. Premium feeds (ad-free + bonus) via Apple Subscriptions / private RSS.**
- *Build on:* feed builder already produces per-language/video variants from
  summaries; a "premium variant" feed is the same pattern (`language_feeds` /
  `video_feed` precedent). Deep-dive machinery (SpaceX `--deep-dive`) is a
  ready-made bonus-content format.
- *Market:* $5/mo tier, 2–5% conversion of engaged listeners; top-heavy market
  — don't expect much below tens of thousands of downloads.
- *Effort:* ~1–2 weeks (tokenized private RSS via a Worker, reusing the gallery
  JWT stack; or Apple-native at 30%/15% cut).
- *Risk:* low-medium. Sequence *after* A3 (membership) to avoid splitting the
  small paying audience; or make the private feed a $15-tier perk.

**A5. Claim the free distribution surfaces (revenue-enabling, not a product).**
YouTube Music 0/15, Amazon Music 0/17, Podcast Index 0/17 are unclaimed. Free
downloads → every per-download product above. Operator checklist item; hours.

### Tier B — Productize the data & content assets (1–2 months each)

**B1. "Nerra Gallery Pro" — licensed niche image library + prompt/retention dataset.**
- *Build on:* 5,548 images with full prompts; 3,603 with attached YouTube
  retention scores; working gated-download Worker.
- *Market:* raw AI stock is crowded (58M new assets/yr; Adobe pays 33%) — do
  NOT compete as generic stock. Two differentiated angles: **(a) dual
  licensing** — images are CC BY-SA (free with attribution + share-alike
  forever; that release is irrevocable), so the paid product is a *commercial
  license without the share-alike/attribution obligations* for
  agencies/publishers who can't ship SA content, plus bulk/API access —
  classic dual-licensing, legally clean because we own the works; **(b) the
  prompt→retention dataset** — "which AI-image styles hold viewer attention,
  measured on 3,603 real videos" is a research/data product for creator-tool
  companies, worth more than the images.
- *Price shape:* $19–49/mo creator tier (bulk download + API), one-off dataset
  license $500–5,000 to tool vendors.
- *Automation:* manifest builder + Worker already run nightly; add Stripe to
  the existing JWT gate; dataset export is one script over
  `gallery-manifest.json` × `gallery_retention.json`.
- *Effort:* 2–4 weeks. *Risk:* medium — new-images-under-paid-license needs a
  license field change in `gallery_uploader` (keep existing 5,548 CC BY-SA;
  don't retro-relicense, it's both impossible and reputationally wrong).

**B2. Beat Chronicle API + "Story Tracker Pro" (the content lake as a product).**
- *Build on:* FTS5 lake (1.85M words, 1,324 entities), `query_by_entity`,
  narrative trackers, story-recurrence memory. Nobody else has a clean,
  entity-tagged, 6-month structured chronicle of the Tesla/SpaceX/AI-agents
  beats with per-day headlines and narrative-arc state.
- *Market:* three buyer shapes — (a) **retail researchers/superfans** ($5–10/mo
  web product: entity timeline pages, "what happened with Optimus since
  March"); (b) **AI app builders** wanting grounded niche news context via API
  (usage-priced); (c) **analysts/journalists** (search + export). The
  public search index (1.85 MB) is the free tier that already exists.
- *Price shape:* freemium web → $9/mo pro search/timelines; API $49–199/mo.
- *Automation:* lake is rebuilt from repo nightly already; needs a hosted query
  endpoint (Cloudflare Worker + D1/R2-hosted SQLite, same pattern as gallery)
  and timeline page generation (the narrative-page generator is the template).
- *Effort:* 4–6 weeks. *Risk:* medium — demand unproven; ship the free
  timeline pages first and gate the deep features once traffic shows up.
  Synergy: timeline pages are also SEO surface for the shows.

**B3. MIT "Glass-Box Record" — a radically transparent investing letter.**
- *Build on:* 59-trade tracker, published fixed-rules methodology, era-scoped
  alpha selector, shadow-execution ledger.
- *Market:* finance is the highest-converting paid-newsletter niche (top decile
  ~20% free→paid, $20–50/mo). The differentiator is NOT performance (verified
  alpha is −1.95%, not significant — and the code refuses to lie about it);
  it's **auditability**: every pick timestamped pre-market, entry/exit rules
  fixed in a public YAML, benchmark bought on identical sessions, misses
  published. "The only stock letter whose track record you can recompute
  yourself" is a real position in a market full of survivorship-bias
  marketing.
- *Legal:* fits the publisher's exclusion (impersonal, regular, bona fide);
  keep disclaimers, never personalize, never tie to an advisory service, and
  keep the honesty rules (verified vs blended split) — they are now a
  *marketing asset*, not just hygiene.
- *Price shape:* free daily (existing show) → $15–25/mo premium letter (full
  signal detail pre-open, portfolio dashboard, monthly deep review).
- *Automation:* trade signals + summaries already generated per episode; the
  premium letter is a second newsletter template over existing JSON.
- *Effort:* 2–4 weeks build. *Risk:* medium-high — **do not launch marketing on
  performance until the era-scoped record has ≥30 trades and non-negative
  alpha**; launch as "follow the experiment" positioning instead. Never blend
  the disowned windows (CLAUDE.md live constraint).

**B4. Env Intel "Compliance Brief Pro" — paid B2B regulatory email.**
- *Build on:* the Compliance Brief segment (already required every episode),
  all-province sourcing (24 curated sources + 4 provincial search queries),
  env_intel narrative tracker (regulatory arcs: consultation → gazetted rule).
- *Market:* regulatory-intelligence services (ERM Libryo etc.) are
  enterprise-priced and opaque; there is room under them for a
  **$29–99/mo scannable weekly brief for Canadian EHS managers and
  consultants** — B2B newsletters monetize at $2K–20K/mo at modest list
  sizes. 30 paying readers at $49 ≈ $17K/yr from a show currently doing 42
  downloads/30d.
- *Automation:* the segment already exists; product = extract it into a
  standalone branded email (newsletter engine handles it), add a
  consultation-deadline calendar mined from the tracker.
- *Effort:* 2–3 weeks. *Risk:* medium — needs distribution into a professional
  audience (LinkedIn, industry associations), which is sales work; accuracy
  bar is higher for B2B (the never-invent honesty rule is load-bearing).
  Include a "not legal advice" disclaimer.

**B5. Language-learning products from Привет, Русский! / Финансы Просто.**
- *Build on:* 66 bilingual lesson episodes, vocab tracker (no-reteach state =
  a structured curriculum map), word-level transcripts, Olya voice.
- *Market:* language-learning podcasts ≈ $1.1B growing 25% CAGR; validated
  price points $5–25/mo (apps) and one-off course sales. Podcast-first
  competitors (Coffee Break, News in Slow) monetize via premium
  transcripts/worksheets at $10–15/mo.
- *Product:* compile the archive into a **structured beginner course**
  (episodes resequenced by the vocab tracker's own dependency data) + paid
  companion pack (transcripts, Anki-ready vocab decks auto-exported from
  `vocab_tracker`, exercises generated per episode).
- *Effort:* 3–4 weeks, mostly packaging. *Risk:* medium — the July 18 review
  flagged these shows for reposition/merge/sunset at 17 downloads/30d; a
  packaged course is exactly the reposition, but validate with a $19 one-off
  course before building subscription machinery.

**B6. Narrative-show anthologies (ebooks/audiobooks).**
- *Build on:* Unintended Consequences (92 eps) + First Principles (73 eps) are
  evergreen narrative essays, not news; the lake makes themed compilation a
  query; audio already exists at broadcast quality.
- *Market:* KDP ebooks + Audible/Findaway audiobooks; modest per-unit revenue
  but pure long-tail with zero marginal cost. AI-narration disclosure required
  on audiobook platforms (Audible's policy permits it via their own tools only
  — check current policy; Findaway/Spotify accepts labelled digital voice).
- *Product:* "Unintended Consequences, Vol. 1: 25 stories of backfire" etc.,
  auto-compiled (digest → cleaned prose via one editorial LLM pass → EPUB).
- *Effort:* 2 weeks for the first volume, then a workflow. *Risk:* low cost,
  low expected revenue — do it for catalogue presence and email capture (free
  volume as lead magnet feeds the funnel gap directly).

### Tier C — Sell the factory (the big swings; months + real sales)

**C1. "Nerra Podcast Engine" — managed branded-podcast service (B2B). ⭐ Highest ceiling.**
- *Build on:* the entire run_show stack; scaffold-a-show in one YAML; two-voice
  dialogue mode; newsletter/blog/video/multilingual surfaces; 100% run
  reliability; $0.23/episode marginal cost.
- *Market:* agencies charge **$400–1,500/episode / $2.8K–5K/mo** for far less
  surface (audio + basic distribution, weekly at best). Internal comms /
  employee-briefing podcasts are a named 2026 B2B trend. Nobody offers "your
  company's daily/weekly branded show + newsletter + blog + Shorts + dubbed
  channels, fully operated, from your sources/RSS/docs."
- *Price shape:* $750–2,500/mo per show depending on cadence/surfaces
  (i.e., **~99% gross margin** on compute). 5 clients ≈ $60–150K/yr.
- *Automation:* already 95% automated — the product IS the automation. Needed:
  client isolation (per-client repo-from-template or multi-tenant output
  namespace), a white-label flag (strip Nerra branding in templates/pills),
  client-facing dashboard (the sponsor view is the template), onboarding
  intake → YAML.
- *Effort:* 4–8 weeks to productize; sales is the real work (start with warm
  outreach: EV/space/AI startups whose beats we already demonstrably cover —
  the shows are the demo reel).
- *Risk:* medium — support expectations, editorial liability (contract:
  client approves prompts; the review-agent machinery becomes a client QA
  feature). This is the product the ops record was unknowingly built to sell.

**C2. Podcast localization & dubbed-channel service (B2B, for existing podcasters).**
- *Build on:* `multilingual.py` + `lang_dub.py`/`ru_dub.py` — proven in
  production: @NerraRU outperforms the EN channel (361 vs 58 views/Short);
  per-language feeds, translated metadata, localized captions/end-cards,
  channel ops, staggered publishing. This is not a dubbing *tool*, it's a
  dubbing *operation*.
- *Market:* AI dubbing tools sell at $0.55–2.40/min self-serve; traditional
  $100–500/min. The gap: podcasters don't want minutes of dubbed audio, they
  want *a running foreign-language channel/feed*. Price as managed service:
  **$200–500/mo per language** including feed + YouTube channel operation.
- *Effort:* 4–6 weeks (ingest arbitrary external RSS as source instead of our
  digest; the rest exists). *Risk:* medium — voice cloning of the host needs
  their consent/voice enrollment (xAI voice training, which the operator has
  done twice already); quality bar per language needs a native-speaker spot
  check at onboarding.
- *Proof point to sell with:* the RU pilot funnel doc — real before/after reach
  numbers.

**C3. Nerra Voices as a consumer product — "record a life story by phone."**
- *Build on:* the complete Voices stack (phone → AI interviewer → dual-track
  recording → 8 editorial passes → produced episode with narration + music +
  transcript approval gates).
- *Market:* StoryWorth $59–199/yr (just added phone features — validating the
  exact mechanic), Storii $99/yr, Tell Mel $26–229. Our differentiator: the
  output isn't a transcript or a book — it's a **produced, broadcast-quality
  audio documentary episode** of a parent/grandparent, with a real AI
  interviewer that asks follow-ups.
- *Price shape:* $79–149 per produced episode (one call) or $199–349 for a
  3-call series + keepsake page (private gated player = the gallery Worker
  pattern).
- *Automation:* pipeline exists end-to-end; needed: self-serve intake (the
  apply-form + Cal.com booking already exist), payment, private delivery page,
  and swapping the "Age of AI" editorial framing for a family-memoir prompt
  set (the 8-pass structure is content-agnostic).
- *Effort:* 4–6 weeks. *Risk:* medium — per-unit human QA (the two approval
  gates become a paid-quality feature), telephony costs per interview,
  emotional-stakes support. But it's the most *defensible* consumer product:
  competitors have the phone call OR the book; nobody produces documentary
  audio.

**C4. Nerra Voices as B2B — AI-moderated expert/customer interviews.**
- *Market:* $20K/yr seats (Outset, Listen Labs), $8–15/interview economics.
- *Verdict:* real market but crowded, enterprise sales motion, and the
  research-analysis layer (coding, quant synthesis) is not built. **Park it** —
  C3 exercises the same stack with a consumer motion we can actually run.

**C5. Self-serve "AutoShow" SaaS (topic → running show).**
- *Market:* Jellypod/Wondercraft at $21–25/mo prove demand for AI podcast
  creation; none run the full loop. Differentiators are real (distribution,
  video, multilingual, analytics, memory).
- *Verdict:* the honest read is that self-serve SaaS means multi-tenant infra,
  support, billing, abuse handling, and competing on marketing against funded
  tools — for $25/mo customers. **C1 (managed, high-ticket) extracts the same
  value with 1% of the surface area.** Revisit only if C1 lands >5 clients and
  demand pulls downmarket.

### Tier D — Licensing & passive (days of effort, small but free money)

**D1. AI-retrieval/training licensing of the corpus.** Enroll the 1.8M-word
archive (and future flow: ~90 eps/week) in Microsoft's Publisher Content
Marketplace and equivalent per-use marketplaces. Realistically small for a
niche publisher, but the effort is a registration and the corpus is clean,
dated, entity-tagged, and grows daily. Bonus: our own funnel already sees
`chatgpt.com` referrals — AI answer engines are consuming the site regardless;
better paid than not.

**D2. Audience-research data.** Per-niche YouTube demographics/geo/search-term
snapshots (already fetched nightly) packaged as a quarterly "niche audio
audience report" lead magnet. Not a standalone revenue line; feeds C1 sales
and the newsletter.

**D3. Prompt & ops playbook licensing.** The 72-prompt library +
review-agent playbook + landmine register is genuinely rare operational IP.
Sellable as a $99–299 "operator's kit" info-product to the faceless-automation
crowd — but it arms competitors in our own niches; **hold** unless C1
positioning makes openness a marketing asset.

---

## 4. Recommended sequence

The constraint stack: (1) attribution/funnel first, (2) payment rail second,
(3) products in order of asset-readiness × market pull.

**Phase 0 — this month (enables everything):**
- A5 claim free directories; A1 programmatic enrollment (turn on $/download);
  A3 patron link + wall (turn on willingness-to-pay signal). B6's free lead
  magnet + every product page below feeds email capture — attacking the
  3-subscriber problem with *offers*, not more CTAs.

**Phase 1 — next 60 days (first real revenue lines):**
- B1 Gallery Pro (closest to a same-week product; Stripe on existing gate).
- B3 MIT premium letter in "follow the experiment" positioning (builds the
  finance list while the era record matures).
- B4 Compliance Brief Pro landing page + 20 hand-recruited beta readers.
- C1 pilot: package the managed-show offer, build one white-label demo show,
  pitch 10 warm prospects. One $1K/mo client ≈ 2× current total network cost.

**Phase 2 — quarter two:**
- C3 Voices consumer memoir product (most defensible; needs the payment +
  delivery pages Phase 1 builds).
- C2 localization service (sell with the RU proof point).
- B2 Beat Chronicle free timeline pages → gate later on traffic.
- B5 language course experiment ($19 one-off) to settle the FP/PR
  reposition question with revenue data.

**Explicit non-recommendations:** C5 self-serve SaaS (do C1 instead), C4 B2B
research interviews (park), D3 playbook licensing (hold), YouTube RPM as a
strategy (it's a funnel, not a product — 97% of automation channels never
break even; ours is already paid for by the podcast pipeline).

---

## 5. Cross-cutting constraints (all products)

1. **Landmine #17:** any product element that changes spoken audio (sponsor
   reads, patron thanks, course re-records) is A/B-listen-gated once, then
   automated. Render/metadata/data-side products are exempt.
2. **Funnel honesty rules** extend to product analytics: null-never-zero,
   min-denominator floors, closed campaign vocabularies (`engine/funnel.py`
   owns every new product's UTM/capture tags — add `PLACEMENT_*` /
   destination entries there, never hand-rolled).
3. **MIT:** era-scoped record only on air and in marketing; verified vs
   blended split stays; publisher-exclusion hygiene (impersonal, regular,
   disclaimed, no personalization).
4. **Gallery:** existing 5,548 CC BY-SA images stay CC BY-SA forever;
   dual-licensing applies to *rights relief + convenience + new collections*.
5. **R2 bucket paths and published enclosure URLs never change** for any
   monetization partner integration — prefix-based partners only.
6. **AI disclosure everywhere** (already network policy) — it's a trust asset
   in every B2B/consumer product above, not a liability to hide.

## 6. Sources

Market figures cited in §2 and §3:

- Podcast ads/CPMs: [MillionPodcasts CPM guide](https://www.millionpodcasts.com/blog/podcast-advertising-cost-cpm-rates-by-genre-size/), [Value Add VC podcast monetization 2026](https://valueaddvc.com/blog/podcast-monetization-in-2026-ad-rates-subscription-revenue-and-what-actually-works), [Castos ads guide](https://castos.com/podcast-ads-guide/), [The Podcast Consultant](https://thepodcastconsultant.com/blog/podcast-advertising), [Creators Agency sponsorship rates 2026](https://creatorsagency.co/blog/podcast-sponsorship-rates-2026), [InfluencerFee benchmarks](https://influencerfee.com/blog/podcast-sponsorship-rates-2025/)
- Paid newsletters: [beehiiv State of Paid Newsletters 2026](https://www.beehiiv.com/blog/the-state-of-paid-newsletters-2026), [Press Gazette newsletter pricing 2026](https://pressgazette.co.uk/newsletters/newsletters-2026-prices-retention-churn/), [BizToolkit beehiiv earnings](https://www.biztoolkit.co/post/how-much-do-beehiiv-writers-make-in-2026), [Digital Applied newsletter statistics](https://www.digitalapplied.com/blog/newsletter-statistics-2026-data-points)
- Premium subscriptions: [SQ Magazine Apple Podcasts statistics](https://sqmagazine.co.uk/apple-podcast-statistics/), [Sci-Tech Today monetization statistics](https://www.sci-tech-today.com/news/podcast-monetization-statistics/), [Supercast subscription guide](https://www.supercast.com/resources/subscription-guide)
- AI podcast SaaS: [SaaSworthy Wondercraft](https://www.saasworthy.com/product/wondercraft-ai), [SaaSworthy Jellypod pricing](https://www.saasworthy.com/product/jellypod-ai/pricing), [AutoContent API NotebookLM alternatives](https://autocontentapi.com/notebooklm-alternative)
- Branded podcast production: [Heartcast branded podcast costs 2026](https://www.heartcastmedia.com/what-a-branded-podcast-actually-costs-in-2026/), [AMW pricing guide](https://amworldgroup.com/pricing/podcast-production-cost), [ThePod.fm B2B pricing](https://thepod.fm/resources/blog/podcast-production-cost-for-businesses), [Content Allies B2B podcasting trends](https://contentallies.com/learn/b2b-podcasting-trends)
- AI dubbing: [Perso AI dubbing pricing 2026](https://perso.ai/blog/ai-dubbing-pricing-2026-cost-per-minute-compared), [Vozo AI vs studio dubbing](https://www.vozo.ai/blogs/ai-dubbing/ai-dubbing-vs-traditional-cost)
- AI interview platforms: [Listen Labs platform comparison](https://listenlabs.ai/blog/top-ai-qualitative-research-platforms), [UserIntuition Voicepanel pricing](https://www.userintuition.ai/reference-guides/voicepanel-pricing/), [Koji Listen Labs vs Outset](https://www.koji.so/blog/listen-labs-vs-outset-2026)
- Legacy recording: [StoryWorth pricing](https://welcome.storyworth.com/storyworth-pricing), [StoryWorth voice features](https://welcome.storyworth.com/blog/storyworth-voice-features-explained), [Memoirji StoryWorth alternatives](https://memoirji.com/blog/best-storyworth-alternatives-2026/)
- AI content licensing: [Media Copilot on Microsoft Publisher Content Marketplace](https://mediacopilot.ai/microsoft-publisher-content-marketplace-ai-licensing/), [LLM Pulse licensing deals map](https://llmpulse.ai/blog/ai-content-licensing-deals/), [Newor Media AI licensing for publishers](https://newormedia.com/blog/ai-content-licensing-for-publishers/)
- AI stock images: [StockPhotoScout Adobe Stock AI rules](https://www.stockphotoscout.com/en/guides/sell-ai-generated-images-on-adobe-stock), [PhotoWorkout stock market overview](https://www.photoworkout.com/sell-stock-photos-make-money/)
- Language learning: [FutureDataStats language learning podcast market](https://www.futuredatastats.com/language-learning-podcast-market), [TBRC online language learning report](https://www.thebusinessresearchcompany.com/report/online-language-learning-global-market-report)
- Publisher exclusion: [Interactive Brokers publisher-exclusion spotlight](https://www.interactivebrokers.com/webinars/spotlight-publisher-exclusion.pdf), [RIACC newsletter exemption](https://www.riacc.io/single-post/understanding-the-sec-newsletter-exemption-what-rias-need-to-know), [SEC investor alert](https://sec.gov/fast-answers/answersnewsltrhtm.html)
- Faceless YouTube economics: [Frameloop faceless YouTube statistics 2026](https://frameloop.ai/blog/faceless-youtube-statistics-2026)

Internal: `api/dashboard.json`, `api/op3_stats.json`, `api/youtube_stats.json`,
`api/funnel.json`, `api/buttondown_stats.json`, `api/gallery_retention.json`,
`site/data/gallery-manifest.json`, `docs/industry_benchmarks.yaml`,
`docs/reviews/network_review_2026_07_18.md`,
`docs/dp_pod_market_assessment_2026_07.md`, `docs/mit_trading_method.md`,
`docs/funnel.md`.
