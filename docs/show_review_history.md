# Show review history (archive)

Every dated quality-pass narrative that used to live inline in
`CLAUDE.md`'s *Script Relationships* section, moved here verbatim on
2026-07-29. Nothing was rewritten or dropped — only relocated.

**Why:** `CLAUDE.md` is loaded in full at the start of every Claude
Code session and replayed across the whole agentic loop, so its size
is a per-session cost on every future piece of work. It had grown to
~185 KB, the majority of it this history: valuable as a record, but
not something an agent needs resident to make today's change. The
structural facts each show needs (how it runs, its voice, its
cadence, its live constraints) stayed in `CLAUDE.md`; the story of
how each show got there lives here.

The canonical per-pass write-ups remain in
[`docs/reviews/`](reviews/), with scored predictions in
[`docs/reviews/ledger/`](reviews/ledger/). This file is the
chronological digest that used to be inline.

> Landmine #17 still governs everything here: any change touching a
> prompt, a closing pool, or shipped audio needs an operator
> A/B-listen. Reading a past pass is not approval to redo it — check
> the ledger's `do_not_retry` list first.

## Environmental Intelligence

- **June 10 2026 quality pass** (review:
[`docs/reviews/env_intel_review_2026_06_10.md`](docs/reviews/env_intel_review_2026_06_10.md);
drift guards: `tests/test_env_intel_quality_pass.py`): EI was missed by
the Tesla/PT/four-show chapter fixes — it had no positional `where`
anchors, so the "Closing" chapter could land mid-script (Ep040, position
7 of 10) and the "That covers today's environmental intelligence"
closing-pool variant matched no Closing pattern (MAB orphan-closing bug).
Added `where: start` (Introduction) / `where: end` (Tomorrow Teaser,
Closing), widened the Closing pattern to both variants, and excluded the
closing's "your practice" from the `industry|practice` marker via
lookbehind. Cadence fix: EI runs odd weekdays but the spoken intro/closing
claimed "daily" and "back tomorrow" (7/10 transcripts) — now cadence-
neutral ("We'll be back with the next briefing"). The podcast prompt's
contradictory length target (demanded 1500–2200w while the YAML pins 900
and episodes ship ~750) unified to 900–1300w. Intro/closing + length
prompt edits change shipped audio — A/B-listen per landmine #17.
**June 11 2026 follow-up pass** (review:
[`docs/reviews/env_intel_review_2026_06_11.md`](docs/reviews/env_intel_review_2026_06_11.md)):
scoring the June 10 predictions against Ep044 (first post-fix episode)
caught the orphan-Closing prediction MISSING — Ep044 shipped with no
Closing chapter because the LLM merged the Tomorrow Teaser sentence and
the `{closing_block}` into one paragraph and the parser's first-marker-
per-line rule titled it "Tomorrow Teaser". Fixed by reordering the two
`where: end` markers so **Closing precedes Tomorrow Teaser** (Closing wins
a merged final line; separate lines still yield both) — config-only, no
audio change. Also took the deferred thin-news issue at a new lever (not
the `min_articles_skip` floor): Ep044's HOOK was literally "No major
Canadian regulatory announcements … appeared in today's feed", which
became the blog title/h1, the chapter title, and the spoken opener; the
digest prompt now forbids an absence-of-news hook and steers thin days to
lead with a forward-looking item (A/B render: "CCME soil vapour … comment
period closes in 19 days …" replaced the absence hook). Digest-prompt edit
changes output — A/B-listen per landmine #17.
**June 15 2026 third pass** (review:
[`docs/reviews/env_intel_review_2026_06_15.md`](docs/reviews/env_intel_review_2026_06_15.md);
drift guards: `tests/test_env_intel_quality_pass.py::TestDeepDiveOpenerNotTic`):
scored the prior predictions against Ep045 (first true post-merge,
normal-news episode — Closing chapter present, real hook, cadence-neutral
closing, 958w; orphan-Closing + absence-hook predictions both HIT). Next
tier: the Practitioner Deep Dive opened with the verbatim "You arrive at
a…" scenario in 9/10 episodes — root cause was the DIGEST prompt seeding
that exact example (`env_intel_digest.txt:173`), which the podcast
faithfully echoed (an Omni-View "strongest case" tic class). Dropped the
seeded example, required a rotated deep-dive entry point in both prompts,
and banned the verbatim "here's something I wish someone had told me…"
lead-in (5/10). A/B render: "A Phase I ESA flags a B.C. site within 5 km
of a glacial lake…" replaced "You arrive at a…". The structural format
(scenario → science → most-common-mistake + fix) is the show's intentional
B2B signature and is unchanged. Prompt edits change output — A/B-listen
per landmine #17.
**June 17 2026 fourth pass** (review:
[`docs/reviews/env_intel_review_2026_06_17.md`](docs/reviews/env_intel_review_2026_06_17.md);
drift guards: `tests/test_env_intel_quality_pass.py::TestChapterPositionalAnchors`):
both June-15 deep-dive tic fixes HIT on Ep046 (first true post-merge
episode — odd-weekday show; the "You arrive at a…" and "wish someone had
told me…" openers are both gone). New finding — a latent orphan-
Introduction bug the June-10 `where`-anchor pass left half-fixed: the
Introduction marker only matched the "This is Environmental Intelligence"
greeting, but `engine/intros.py` rotates a "Welcome to Environmental
Intelligence" greeting too, so every "Welcome to" episode
(Ep037/038/042/046 of the last ten) shipped with NO Introduction chapter
(the welcome + Compliance Brief got absorbed into the first content
chapter). Broadened the pattern to `(?:This is|Welcome to) Environmental
Intelligence` (metadata-only, no audio/prompt change — same orphan-
chapter class the June 10/11 passes fixed for the Closing variant).
Chronic under-length stays deferred (median 814w vs 900 floor; digest
ceiling, behind the four-show length A/B), as does the mid-section
chapter-marker keyword reliance (Ep046 had no Week Ahead chapter).

## Fascinating Frontiers

- **FF June 12 2026 quality pass** (review:
[`docs/reviews/fascinating_frontiers_review_2026_06_12.md`](docs/reviews/fascinating_frontiers_review_2026_06_12.md);
drift guards: `tests/test_fascinating_frontiers_quality_pass.py`): the
June-10 four-show length fix MISSED — Ep097/098/099 (post-pass) shipped
1634/1390/1637w, all under the 1700 floor. Verified root cause is the
**digest ceiling**, not the target: FF's RSS feeds return snippets
(not full text) → digests run 1027-1597w → the podcast can't exceed
them without the padding/invention both prompts ban (Ep099 script 1664w
> its digest 1572w). The expand-retry fires every episode and plateaus;
on the thinnest day it padded 6 stories with title-case headline
restatements. Deferred the only non-padding lever (expand the Cosmic
Deep Dive, which is licensed to use the model's own astrophysics
knowledge) until the operator's four-show length A/B settles. Shipped
two deterministic, no-A/B fixes: (1) `fix_phonetic_garbles` extended for
the space names the model spelled phonetically despite the ban —
"En-sell-uh-dus"→Enceladus (Ep048/088/094), "Tee-en-wen"→Tianwen
(Ep090); (2) a theme-mining self-reference filter — the show's own name
("fascinating frontiers") had been mined as a top "recurring theme"
every episode (Ep97/98/99 led their top_themes with it); only the full
show-name bigram is filtered, never component tokens.

- **FF June 16 2026 quality pass** (review:
[`docs/reviews/fascinating_frontiers_review_2026_06_16.md`](docs/reviews/fascinating_frontiers_review_2026_06_16.md);
drift guards: `tests/test_fascinating_frontiers_quality_pass.py::TestStockMarketTitleFilter`):
both June-12 predictions HIT (garbles gone, show-name no longer a top
theme). New finding: since the SpaceX/SPCX IPO (June 12) the Google-News
"SpaceX" queries flood FF — a *science* show — with pure stock-market
items; Ep103 shipped FOUR of fifteen stories as market action (an $85.7B
funding round told twice, a "$60B merger with Cursor", NASDAQ index
inclusion, a 20% share move), off-brand and overlapping SpaceX Daily /
Modern Investing. Fixed at fetch time via stock/market
`exclude_title_patterns` (same accepted class as the almanac filter —
deterministic, no A/B) + a digest-prompt `NO STOCK / MARKET ITEMS` scope
bullet (A/B-listen). Live-verified on today's feeds: 7 SPCX items dropped,
Falcon 9 *launch* kept (a bare `nasdaq/nyse` pattern was tried and removed
after it dropped that launch story). The chronic under-length / Cosmic Deep
Dive lever stays deferred pending the four-show length A/B. The `@`→"at at"
YouTube-CTA wart in Ep103 was already fixed upstream by the June-16 FP pass.
Prompt edit changes output — A/B-listen per landmine #17.
**June 24 2026 third pass** (review:
[`docs/reviews/fascinating_frontiers_review_2026_06_24.md`](docs/reviews/fascinating_frontiers_review_2026_06_24.md);
drift guards: `tests/test_fascinating_frontiers_quality_pass.py::TestChapterClosingOrdering`):
scored June-16 — launch-false-drop prediction HIT; the stock-filter
prediction PARTIAL (dailies clean, but the Sunday recap Ep108 re-surfaced
pre-filter Ep103 SPCX content via the content lake — `engine/weekly_recap.py`
bypasses the fetch filter; self-healing next cycle, deferred). Headline: the
orphan-Closing chapter class the snapshot's loose `chapter_issues` check
missed — Ep110/Ep111 shipped with NO Closing chapter (ended on Tomorrow
Teaser) and Ep109 shipped a spurious out-of-order Cosmic Deep Dive chapter.
Root cause: the sign-off "…see you next time" matches the teaser's `Next
time` and Teaser was listed before Closing; the real "Keep an eye on…"/
"Watch for…" teaser openers (6/8) matched no pattern; and bare `deep dive`
only ever matched the cross-promo "daily deep dive into everything Tesla".
Fixed (metadata-only, no audio): Closing before Tomorrow Teaser, teaser
broadened to line-anchored `^Keep an eye on`/`^Watch for`, bare `deep
dive`/`under the hood` dropped (EI June-11 / SpaceX June-18 / FP June-23
ordering-rule class) — verified by re-parsing real Ep108-111 (all now end
Tomorrow Teaser -> Closing). Chronic under-length + the digest-driven
mid-section chapter titles stay deferred.

## First Principles Daily

- **June 10 2026 quality pass** (review:
[`docs/reviews/first_principles_review_2026_06_10.md`](docs/reviews/first_principles_review_2026_06_10.md);
drift guards: `tests/test_first_principles_quality_pass.py`): FP was
missed by the Tesla/four-show chapter hardening — no positional `where`
anchors, so the brand-heavy closing ("That's *First Principles Daily*…")
re-opened an `Introduction` chapter on the sign-off and Ep001-004 shipped
with no `Closing` chapter; added `where: start` (Introduction) /
`where: end` (Closing). The bigger fix: `podcast_expand_below_target` was
a DEAD path for narrative shows — the expansion retry was news-framed
("cover more stories"), useless for a one-topic show, so every thin FP
episode (Ep002 953w, Ep004 935w) fired the retry and kept its length. The
retry is now narrative-aware (`_build_expansion_retry_prompt(...,
narrative=)` in `engine/generator.py`): narrative shows (FP + UC) expand
by DEEPENING the single topic from the brief. Deferred: the digest stage
is itself under-length (briefs 870-1498w vs the 1600 prompt floor; no
digest expansion retry) — the next lever. The ~10-12 min length ceiling
is accepted (operator confirmed grok-4.3 plateaus, resists escalation),
not re-litigated. Retry edit changes shipped audio when it fires —
A/B-listen per landmine #17.
**June 23 2026 second pass** (review:
[`docs/reviews/first_principles_review_2026_06_23.md`](docs/reviews/first_principles_review_2026_06_23.md);
drift guards: `tests/test_first_principles_quality_pass.py::TestClosingNotStolenByBodyMarkers`,
`TestLessonTemplateDeSeed`, `TestDigestExpansionRetry`): scored the June-10
predictions — the narrative retry was PARTIAL (scripts now exceed their
briefs but the thin brief still caps a few) and the chapter prediction
MISSED on its Closing half. P0: **7 of the first 18 episodes
(Ep001/004/007/009/011/015/017) shipped with NO Closing chapter** — the
June-10 `where` anchors fixed the duplicate-Introduction class but not
this one: the sign-off tagline "one example or one **opportunity**, every
day" (and the brand "**First Principles** Daily") let the body markers
*The Opportunity* / *The First Principle* steal the closing line whenever
they had not matched earlier in the body. Fixed by listing **Closing
before the body markers** (EI June-11 / SpaceX June-18 ordering rule);
`where: end` keeps it out of the body → 18/18 episodes get a Closing
chapter (metadata-only, no audio). P1: the June-10-deferred **lesson-
template echo** grew to 12 of ~16 episodes opening the lesson with the
verbatim seeded formula "a [part] whose price greatly exceeds its
[materials] is announcing a design problem" (Omni-View "strongest case"
class) — de-seeded both digest-prompt tracks, require fresh per-topic
phrasing (`--test`: formula gone). P1: shipped the June-10-deferred
**digest-stage expansion retry** (new opt-in `llm.digest_expand_below_target`
/ `llm.min_digest_words`, default no-op; narrative-aware deepen-the-brief,
mirrors the podcast stage; FP opts in at 1400 — `--test`: a 1146w brief
lifted to 1400w). Prompt + digest-retry edits change shipped output —
A/B-listen per landmine #17; the chapter reorder does not.

## Four-show pass (MIT, M&A, MAB, FF)

- **June 10 2026 four-show pass** (MIT, M&A, MAB, FF; full review:
[`docs/four_show_review_2026_06_10.md`](docs/four_show_review_2026_06_10.md);
drift guards: `tests/test_four_show_quality_pass.py`): every show's
Closing chapter pattern now matches every closing-pool variant (MAB had
shipped 50% of episodes with NO Closing chapter; M&A's bare `agent`
pattern opened a spurious chapter ~30s into every episode) with
`where: start|end` positional anchors; ONE unified length target per
prompt (MIT 2,000-2,200w/floor 1800; M&A 1,600-2,200w; FF
1,900-2,200w/floor 1700; MAB floor 1200) replacing contradictory
anchors; `engine/show_memory.py` gained all four Tesla memory fixes
(narrative-prose echo filter, per-episode idempotency, URL stripping,
word-boundary program detection) + `update_performance_from_op3`; the
nightly performance step generalized to
`scripts/update_performance_trackers.py` (Tesla + M&A + FF + PT); the
three memory shows' theme histories were re-scrubbed; MAB's "So
imagine" opener tic (49 of 60 episodes — the prompt's own example was
the template) now requires rotating opener shapes. Length/opener
prompt edits change output — A/B-listen per landmine #17.

## Models & Agents

- **June 14 2026 quality pass** (review:
[`docs/reviews/models_agents_review_2026_06_14.md`](docs/reviews/models_agents_review_2026_06_14.md);
drift guards: `tests/test_models_agents_quality_pass.py`): two
listener-facing metadata bugs, both no-A/B. (1) The script-gen step
spelled core AI proper nouns phonetically despite the prompt ban and
they reached TTS *and* chapter titles (`parse_chapters` runs after the
repair): `An-thropic` shipped in nearly every episode (6× in Ep080, present
since Ep004), plus `Lah-mah` (Llama) and `Hah-sah-biss` (Hassabis) —
added to the blessed `engine.utils.fix_phonetic_garbles` restore layer
(global; removes a respelling, so outside landmine #17). (2) The Under
the Hood chapter marker only matched literal "under the hood" but the
deep-dive opens with "let's pop the hood on …" in 9-10/10 episodes, so
only 1/5 recent episodes got the chapter — the miss dropped several below
`min_chapters` (4) and fired the auto-segment fallback that titled
chapters from raw mid-sentence text (Ep080); added `|pop the hood` to the
marker (`shows/models_agents.yaml`). Deferred: digest-driven chapter
titles (Ep078-class residual, Tesla-deferred) and Under-the-Hood length
expansion (after the four-show length A/B). The "pop the hood" opener tic
was left unchanged (signature phrase; shipped-audio risk).
**June 21 2026 third pass** (review:
[`docs/reviews/models_agents_review_2026_06_21.md`](docs/reviews/models_agents_review_2026_06_21.md);
drift guards: `tests/test_models_agents_quality_pass.py::TestPhoneticGarbleRepair`):
all four June-14 predictions scored HIT. One recurring reader-facing text
bug: the SHARED pronunciation map respells `CUDA → "koo-dah"`
(`assets/pronunciation.py:168`, an ElevenLabs-era word-acronym guide), and
that respelling is written into the `_tts.txt` → the published blog/RSS
transcript (`engine/blog.py:767`), shipping verbatim in 12 episodes since
Ep040 (e.g. Ep088 "open-sourced a koo-dah kernel"). Same class as the
original "nassa" leak that created `fix_phonetic_garbles`; restored the same
way — `koo-dah → CUDA` added to `engine.utils._PHONETIC_GARBLES` (global;
the canonical acronym reaches both transcript and TTS, exactly as
`nassa → NASA` already ships). Collision-safe ("koo-dah" has no English
use); the collision-unsafe map guides (`LoRA → "Laura"`, `RAG → "rag"`) are
left alone. Sharpened the deferred chapter diagnosis: chapter quality is
inversely correlated with prompt compliance — Ep084/086 ship a full
9-chapter shape only because the host announces the banned section labels
aloud ("Now turning to model updates"), while prompt-compliant episodes
(Ep085/087/088) collapse to auto-segment fragments or sparse shapes;
confirms digest-driven titles as the durable lever (deferred). New deferred
network-wide item: pronunciation-map word-guides leaking into published
transcripts (durable fix = source the transcript from pre-pronunciation or
Whisper text). Restore-layer edit touches TTS — spot-check per landmine #17
(low risk; matches the NASA/Anthropic precedent that ships today).

## Models & Agents for Beginners

- **June 25 2026 quality pass** (first dedicated MAB review:
[`docs/reviews/models_agents_beginners_review_2026_06_25.md`](docs/reviews/models_agents_beginners_review_2026_06_25.md);
drift guards: `tests/test_mab_quality_pass.py`): scored the June-10
four-show predictions — the "So imagine" opener de-seed HIT (0/10), the
length floor raise MISSED (9/10 still under 1200, digest ceiling, deferred).
Two prompt de-seeds (A/B). (1) The Deep Dive closer echoed a verbatim
three-sentence template every episode — "and that's basically what X is
doing when it Y / so next time someone says Z, you can tell them it is
basically W / not so scary, right?" (9/10 "not so scary right", Ep080/081/082
word-for-word); root cause was BOTH prompts seeding the literal sentences
(`mab_podcast.txt:138-139`, `mab_digest.txt:121-122`, the Omni-View
"strongest case" / EI deep-dive / FP lesson-template class). De-seeded both,
keeping the analogy method but requiring fresh per-episode phrasing and
naming the formulas as banned-as-verbatim (A/B render: digest now ends "…more
like chatting with someone who actually gets the point" instead of the
formula). (2) After the "So imagine" fix the model converged on a new
"Something [adj] just happened" opener (5/10) — straight from the prompt's
own example list (`mab_podcast.txt:125`); moved it from the example menu to
the BANNED list. Deferred: chronic under-length (digest ceiling, four-show
length A/B); "The Big Story" chapter missing on every episode (dead
`big story|biggest news` marker — host's opener is intentionally varied, no
anchor; digest-driven/position-aware titles is the durable lever, M&A
June-21 class); Ep081 auto-segment garbage title (same lever); the stale
Fish/Chatterbox pronunciation hook still injecting landmine-#17 respellings
(`CUDA→"kooda"` etc., 0/76 transcript impact — recommend aligning with
sister M&A which uses no hook). Prompt edits change output — A/B-listen per
landmine #17.

## Modern Investing Techniques

- **June 2026 quality pass** (drift guards: `tests/test_mit_quality_pass.py`):
the recursive-learning loop had been DEAD on every episode —
`_analyze_strategy_patterns` was called but never defined, the NameError
was swallowed by pre_fetch's try/except, and all three learning blocks
shipped as "temporarily unavailable" (now implemented: FAVOR/AVOID sector
guidance). Two trades closed with NaN exit prices (yfinance returns NaN
floats that pass `is None`) had poisoned `cumulative_pnl` into NaN —
"Running Total: $nan" on air; all aggregations now route through
`_finite()` and `_close_trade` rejects non-finite prices. The summary
gained `cumulative_alpha_vs_nasdaq` (the headline metric previously read
from a key that never existed — actual record: +20.6% across 26
benchmarked trades, finally stated on air via the portfolio block).
Lesson cooldowns now ESCALATE with teach-count (flat 21d let
bid_ask_spread reteach 13×; every 3 repeats adds a full period, cap
180d). Trade extraction logs loudly on formatting drift vs quiet on
deliberate no-trade days. MIT opts into `podcast_expand_below_target`,
gets a hook-led X teaser linking the episode blog + performance page,
and the deep-dive queue carries a 6-entry evergreen Canadian bench
(operator schedules via `when: next`). Prompt edits (no-trade platitude
ban, Market Pulse macro frame) change output — A/B-listen per landmine
#17.
**July 3 2026 benchmark-integrity pass** (review:
[`docs/reviews/modern_investing_review_2026_07_03.md`](docs/reviews/modern_investing_review_2026_07_03.md);
drift guards: `tests/test_mit_benchmark_integrity.py`): audit driven by
the operator's live-trading intent — the measurement layer was not
measuring what it claims. Every FLASH trade had `nasdaq_return_pct: 0.0`
(the annotator compared the same close to itself → "alpha" was the raw
return); mid-week weekly picks were BACKDATED to Monday's open
(hindsight gain — Ep35 AMD picked Wed, +13.36% from Mon open); Ep50
"CNR (TSX)" was priced as US Core Natural Resources, not Canadian
National Railway; DELL/HIMS NaN closes were still spoken as breakevens
(the July-2 migration caught nulls, not NaN); `--test` runs appended
REAL trades (post_generate runs before the test-mode exit); and the
lessons_learned "learning loop" was an echo chamber (65 actives, ~47
copies of two rules — the 9/10-episode "closing-price confirmation"
tic). Fixed: matched-bar-window benchmark (index open→close over the
trade's own bars), pick-date entry integrity (no bars before the pick;
cron-delay wrong-day pricing killed; stale picks void after 10d), TSX
`.TO`/`.V` resolution + pick-time probe + price-discontinuity tripwire,
self-healing void of non-finite closes (tracker now 40 closed/6 voided,
win rate 57.5%), `NERRA_HOOKS_READONLY` set by run_show for
`--test`/`--rehearse` (only the MIT hook honors it so far — extending to
the memory shows is a deferred network item), lessons dedup-on-append +
ledger collapse 65→11 distinct rules, matched-window compounded alpha +
labeled scoreboard blocks (A/B-listen: scoreboard/lessons/bar-day-label
changes alter spoken output), per-bucket confidence calibration (46/46
picks had said "Medium"). Operator to-dos: run
`scripts/recompute_mit_benchmarks.py --apply` (needs market-data access;
realigns historical windows + reports wrong-instrument trades) for the
first trustworthy alpha baseline, and see the review doc's live-trading
readiness verdict (NOT READY — honest record +$304 over 40 sequential
$1k trades vs NASDAQ +15.46% ITD; accumulate 2-3 months of clean
post-fix record first).
**July 3 2026 SnapTrade execution plan** (doc:
[`docs/mit_snaptrade_live_trading_plan.md`](docs/mit_snaptrade_live_trading_plan.md);
drift guards: `tests/test_mit_benchmark_integrity.py::TestTradeSignal`):
design for live trading via SnapTrade (the only sanctioned Wealthsimple
API route; Webull US/CA trading added Dec 2025). Shipped the execution
bridge: `post_generate` now writes a schema-versioned
`trade_signal_latest.json` + per-episode copy (explicit
new_trade/no_trade with drift-distinguishing reason, SnapTrade-format
symbol — Yahoo `.TO` convention matches the tracker's resolved symbols
1:1 — CAD→Wealthsimple / USD→Webull routing, deterministic uuid5
`client_order_id` for idempotent placement; read-only runs write
nothing). The future `execution/` package consumes ONLY this artifact
— the LLM never touches the order path. Phased rollout in the doc
(read-only mirror → shadow mode → $150-250 micro-live on Webull →
scale), fail-closed risk caps, and an operator checklist (SnapTrade's
per-broker matrix must be verified in the dashboard: trade enablement
for Wealthsimple, Limit+Day support, fractional/notional). NOTE:
SnapTrade's sandbox is READ-ONLY (no simulated fills) — shadow mode is
the paper-trading layer. Podcast stays a simulation on air; live
execution is a private layer decoupled from the 08:16 UTC episode run
(executor runs its own ~13:50 UTC slot).
**July 4 2026 optimize-the-loop pass** (drift guards:
`tests/test_mit_benchmark_integrity.py::{TestMultiIndexBenchmark,TestRuleEffectiveness}`,
`tests/test_snaptrade_execution.py::{TestRiskGates,TestShadowExecutor}`):
three workstreams toward "beat all major indices". (1) **Multi-index
matched-window benchmarking** — every closed trade now carries
`benchmark_returns` for ^IXIC + ^GSPC + ^GSPTSE over the SAME bar
window; summary gains per-index compounded `benchmark_scores` +
`indices_beaten`; the scoreboard block adds a once-per-episode
"beating N of 3 major indices" sweep (NASDAQ stays the headline;
legacy trades fall back to the nasdaq field; recompute script rebuilds
history for all three). (2) **Rule-effectiveness scoring** — trades are
stamped with `rules_in_effect` (the exact rule IDs shown on pick day);
`_build_rule_scoreboard` compares stamped-trade alpha vs trades
without each rule and flags ≥8-trade no-edge rules as RETIREMENT
CANDIDATES (operator decision — never auto-retired). The learning loop
now measures whether its own rules work. (3) **Shadow mode (Phase 2)
LIVE** — `execution/risk.py` (pure, env-tunable hard gates; kill
switch defaults off) + `execution/shadow.py` (signal → gates →
decision-time quote → would-be marketable-limit order → committed
`shadow_ledger.json`, idempotent) + `mit-shadow-executor.yml`
(weekdays 13:50 UTC, yfinance only, no secrets); the read-only/no
order-placement contract still pinned. `scripts/mit_shadow_report.py`
= sim-vs-shadow slippage table. Scoreboard/lessons-block additions
change prompt context → A/B-listen per landmine #17. Same-PR second
batch: shadow EXITS (paired idempotent `would_sell` on the sim's exit
calendar → round-trip shadow P&L + sim-vs-shadow gap in the report),
regime block (rolling last-10 alpha + drawdown → cold streak makes
no-trade the default / hot streak holds the bar), FAVOR/AVOID now
requires n≥5 samples (was 2-3 — coin flips steered picks), performance
page gained the matched-window headline tile + "not capital-matched"
relabel + major-index sweep.
**July 4 2026 fidelity batch** (drift guards:
`tests/test_mit_benchmark_integrity.py::{TestStopLossExtraction,TestStopBreach,TestAlphaTStat}`,
`tests/test_dashboard_mit_section.py::TestExecutionHealth`): stop-loss
ENFORCEMENT — the digest narrates a stop on every pick but the sim
never enforced it; the stop is now parsed at pick time (never guessed),
carried on the trade + trade signal (future bracket orders), and
enforced at evaluation against intraday lows (bars carry a 4th
low element; gap-aware fills; entry-bar breaches never claimed; the
benchmark window follows the shortened hold; the review narrates
"stopped out" as stop discipline working). Per-trade alpha **t-stat**
(`alpha_t_stat` / `alpha_statistically_significant`) in the summary +
an on-air honesty rule in the scoreboard block (hedge "not yet
statistically significant" until t≥2). Dashboard `execution_health`
block (trade-signal freshness/staleness + shadow-ledger vitals).
Stop enforcement changes sim outcomes going forward; the honesty line
+ stop narration are new prompt context → A/B-listen per landmine #17.
**July 4 2026 Phase-3 live executor (DORMANT)** (drift guards:
`tests/test_snaptrade_execution.py::{TestLiveEntry,TestLiveExits,TestLiveStatePrivacy}`):
operator-directed "build the next layer" — real order placement now
EXISTS but cannot run until armed. `execution/live.py` +
`scripts/mit_live_executor.py` + `mit-live-executor.yml` (13:52 UTC
entries / 19:45 UTC exits). Gate order, all fail-closed: kill switch
(repo var `LIVE_TRADING_ENABLED=1`; unset → logged no-op that never
loads credentials) → SnapTrade config → self-halt (2 consecutive
rejects halt the layer via committed `live_execution_state.json`;
exits still run so positions are never unmanaged) → shared risk gates
→ daily/open-position caps → account resolution (institution match on
the signal's routing hint) → live quote (none = never place blind).
Integer-share marketable limits under `MIT_MAX_POSITION_USD` (default
$250); idempotent `client_order_id`; the narrated stop rides on the
signal for future bracket orders. Privacy split: committed state =
ids/status only; full `live_ledger.json` (account ids/amounts) is
gitignored + 90-day CI artifact. The Phase-1/2 "no placement code"
contract is superseded by a narrower pinned one: the SDK trading call
exists ONLY in `snaptrade_client.py`, invoked ONLY by `live.py`, whose
FIRST gate is the kill switch (a poisoned-client test proves disabled
runs touch nothing). No prompt/audio changes (outside landmine #17).
**July 18 2026 two-week scoring review** (review:
[`docs/reviews/modern_investing_review_2026_07_18.md`](docs/reviews/modern_investing_review_2026_07_18.md);
drift guards: `tests/test_mit_benchmark_integrity.py::{TestRegimeDeadlockFix,TestWeeklyMinHold,TestSweepGating,TestNoTradeReasonTaxonomy}`):
scored the July 3-4 predictions — 8 HIT (tic 9/10→0/10, entry
integrity, stops 2/2, rule stamps, 3-index closes, shadow ledger
complete with paired exits, dormant live layer untouched), 1 MISS,
1 pending. Two production design flaws fixed: (1) the regime
cold-streak brake DEADLOCKED the Practice Investment (2 picks in 14
episodes; mean poisoned by the -11.8 MDA outlier, $100 drawdown
threshold permanently tripped at $164 standing, and cold suppressed
the closes that refresh the window) — regime v2 uses the MEDIAN, a
full-position $250 drawdown threshold, a >7-day pick-drought escape
valve (SELECTIVE RESET expects the next Monday pick), and tells the
show to narrate capital-preservation mode on air; (2) Ep101 COST was
picked Thursday and closed as a one-bar "weekly hold" (entry==exit
bar, -2.35% while the shadow layer holding Thu→Fri made +0.26%) —
weekly closes now require ≥2 days since pick, shadow calendar matched.
The MISSed prediction: the t-stat honesty hedge was spoken in ZERO
episodes while the alpha was quoted in most — the caveat now lives
INLINE in the alpha sentence (models echo data lines, drop separate
instructions — a reusable lesson). Index sweep gated on n≥5 per index
(was comparing 37-trade NASDAQ vs 2-trade S&P/TSX). No-trade signal
reasons: explicit forms broadened ("Today's Pick: None" was mislabeled
as extraction drift), `no_practice_section` for recaps. Regime/caveat
text changes prompt context → A/B-listen per landmine #17. Operator
items still open: recompute --apply (matched alpha retains old-window
inflation until backfill), SnapTrade Phase-0 verification, LL-054
family retirement.
**July 24 2026 operator-directed pass** (review:
[`docs/reviews/modern_investing_review_2026_07_24.md`](docs/reviews/modern_investing_review_2026_07_24.md);
drift guards: `tests/test_mit_benchmark_integrity.py::{TestSuffixedSymbolExtraction,TestCryptoSymbolCandidates,TestInstrumentScaleMismatch,TestVoidDisclosure,TestAlphaCaveatDataShaped,TestArticleCollapseAlarm}`):
the trade EXTRACTOR could not parse the exchange-native symbols the
July-3 pass taught the digest to emit — Ep111's spoken CNR.TO weekly
pick was silently LOST (`no_pick_extracted`) and Ep113's "BTC-USD —
Bitcoin" was truncated to "BTC", validated against an unrelated $28.80
equity (narrated stop $64,500), routed to Webull in the trade signal,
and would_place'd by the SHADOW executor — the wrong instrument reached
the execution layer. Fixed: suffixed/hyphenated symbol extraction +
CRYPTO market (+ latent TSX-V alternation bug), crypto candidates force
the `-USD` pair with no bare fallback, a wrong-instrument tripwire
(stop outside [ref/3, ref×3] voids at record time + self-healing
migration; committed tracker migrated — Ep113 BTC voided), and an
announced-then-voided pick is now disclosed on air exactly once. Ep115
fetched 9 articles (vs 222-337 median) and shipped 6/6 x.com sources —
new network-wide source-collapse `::warning::` + `article_count_degraded`
metric in run_show; digest prompt gains x.com-as-one-publication /
publisher-first sourcing, the Tools-header scaffold typo fix ("…Tool:
Source" shipped verbatim), and Today's-Pick template instructions moved
out of the value slot (Ep111 echoed the parenthetical on air). Length
attacked at the sanctioned substrate (`digest_expand_below_target` +
`min_digest_words: 1500`; 10/10 scripts were under the 1800 floor). The
significance caveat missed a SECOND time (1/6 alpha mentions) — now
fused into the alpha value as a data-shaped parenthetical; a third miss
goes to the operator as accept-or-abandon. Prompt/caveat/digest-lever
edits change output — A/B-listen per landmine #17.

**Tesla Shorts Time Recursive Memory System (May 2026+)**  
TST received a full recursive improvement architecture (analogous to MIT):
- `engine/tesla_memory.py` + three persistent trackers in `digests/tesla_shorts_time/`:
`tesla_narrative_tracker.json` (major programs with status, claims, confidence),
`tesla_performance_tracker.json` (YouTube/Shorts signals for emphasis),
`tesla_theme_history.json` (mined from transcripts/digests).
- Injected on every episode via `shows/hooks/tesla.py` pre_fetch → rich context blocks
(`tesla_narrative_status_block`, performance signals, theme context).
- Prompt updates in both digest and podcast prompts.
- Public page `tesla-narrative.html` (generated nightly + on demand).
- Post-episode hook + Sunday recap integration.
- Operator tooling: `scripts/update_tesla_narrative.py` for easy updates without hand-editing JSON.
- Goal: TST becomes the best long-term public chronicle of Tesla's major programs while
continuously optimizing for real audience engagement.

## Omni View

- **June 10 2026 quality pass** (review:
[`docs/reviews/omni_view_review_2026_06_10.md`](docs/reviews/omni_view_review_2026_06_10.md);
drift guards: `tests/test_omni_view_quality_pass.py`): OV was missed by
every chapter/length hardening round. Two shipped chapter bugs fixed
(metadata-only): 7 of the last 10 episodes had NO Closing chapter (the
dominant "That wraps up today's Omni View…" closing-pool variant matched
no pattern — MAB orphan-closing class), and the dead "Understanding the
Issue" pattern let the auto-segment fallback title chapters from raw
deep-dive sentences (Ep061 "Knowing this, when you hear claims…", Ep068
"How are casualty figures verified…"); added `where` anchors + a Closing
pattern covering both variants + a deep-dive pattern matching the real
spoken opener. The June "strongest case ≤1×/episode" steel-man fix had
FAILED (12-20×/episode in Ep070/071/075, or mutated to the anonymous
"One side frames / The other side frames / Advocates on each side" frame
in Ep077 — which also violates the prompt's own attribution rule); root
cause was the DIGEST prompt seeding the literal "The strongest case for X
rests on…" lead-in, so the fix dropped that seed, requires NAMED
advocates, and bans the anonymous frame in both prompts (verified via
`--test`: 0 uses, advocates now named). Unified three contradictory
length targets (8-12 min / 2000 words / "40+ sentences") to one
(1,700-2,000w ≈ 11-13 min) + added `podcast_expand_below_target` and
raised `min_podcast_words` 900→1400 (the expand opt-in the June network
pass missed). Prompt/length edits change shipped audio — A/B-listen per
landmine #17; the chapter fix does not.
**July 18 2026 editorial realignment** (operator-directed; review:
[`docs/reviews/omni_view_review_2026_07_18.md`](docs/reviews/omni_view_review_2026_07_18.md);
drift guards: `tests/test_omni_view_quality_pass.py::TestEditorialRealignmentJuly18`):
repositioned to "top world stories, balanced, teen-to-senior,
informative AND encouraging, anti-clickbait". The 12-slot taxonomy
(whose mandatory daily gossip + popular-media slots forced tabloid
filler and twice LED episodes with tabloid items) became a 7-slot
slate: lead (1) + world (3) + economy/science/tech (2) + **Progress
watch** (1, rigor bar: named actors + a number + the complication) +
the retained Understanding the Issue deep dive. Steel-man is now
CONDITIONAL (2-3 genuinely contested stories, named advocates; the
"Both sides agree" family had shipped ~38×/10 eps incl. on a
waterslide accident) — disasters/deaths/science/culture get context +
what-happens-next, never manufactured sides. Plain-language layer
(define every institution in one clause; teen-to-senior audience in
every prompt). Sources: Daily Mail REMOVED (was the most-cited outlet;
Reuters/AP were 0×), dup-BBC + r/news removed; Reuters/AP Google-News
proxies, WSJ World + 9 regional feeds (Africa/Asia/LatAm) added with a
geographic-breadth rule (≥3 regions, ≤2/country, UK ≤1); conservative
tabloid `exclude_title_patterns`. Engine: `podcast_expansion_style:
deepen` (new LLMConfig field — the "cover more stories" retry would
fight the fixed slate), `min_digest_words: 1500` + digest retry (the
under-length root fix), `ov_validation_config` + `OV_SECTION_PATTERNS`
updated to the new headers (Ep068 regenerate-class). New closings pair
perspective coaching with one encouraging line; a per-episode
"go deeper: compare two outlets" pointer. Public copy updated (tagline
kept). All prompt/closing/source changes alter shipped audio —
A/B-listen the first post-merge episode per landmine #17; watch the
Progress Watch chapter marker for the dead-marker class.

## Planetterrian Daily

- **June 10 2026 Planetterrian pass** (review:
[`docs/planetterrian_review_2026_06_10.md`](docs/planetterrian_review_2026_06_10.md);
drift guards: `tests/test_planetterrian_quality_pass.py`): NEW
network-wide missing-closing guard in `engine/pipeline.py` (PT Ep081/084
shipped without the supplied closing block — Ep084 ended mid-teaser; the
pipeline now appends the resolved `closing_block` verbatim when absent,
before chapter parsing); ONE unified length target (1,800–2,100 words ≈
12–13 min, floor 1250→1600 — the prompt had demanded three conflicting
lengths and all 15 recent episodes ran under target, avg ~970); chapter
`where` anchors + "see you next" closing coverage. Watch the first week
for `podcast_script_too_thin` skip markers; fall back to floor 1400 if
PT skips more than once. A/B-listen per landmine #17.
**June 18 2026 second pass** (review:
[`docs/reviews/planetterrian_review_2026_06_18.md`](docs/reviews/planetterrian_review_2026_06_18.md);
drift guards: `tests/test_planetterrian_quality_pass.py::TestChapterShapeJune18`):
the June-10 `where` anchors exposed two deeper chapter P0s (all
metadata-only, no A/B). (1) The Introduction marker matched only the
"Welcome" greeting, but the intro rotates four greetings — "Good to have
you on" / "Thanks for tuning in to" carry no "Welcome", so ~50% of
episodes (Ep085/086/088/093) shipped with NO Introduction chapter and the
whole body collapsed under the teaser-anchored first chapter
(orphaned-body class); now anchored on "Planetterrian … episode" (matches
all four greetings). (2) The spoken teaser opens "Keep an eye on…" / "Watch
for…" (the pattern missed it), so the teaser's `Next time` stole "See you
next time" from the closing line and Ep086/090 shipped with no Closing
chapter — fixed via the EI June-11 ordering rule (Closing precedes Tomorrow
Teaser) + a broadened teaser pattern. (3) The Science Deep Dive marker was
dead (prompt forbids announcing the section); now matches the seeded spoken
opener ("most people get wrong / picture / assume"). The June-10 length fix
scored a MISS — episodes still 1178–1378w (digest ceiling, FF/UC root
cause); re-attack deferred behind the four-show length A/B. Garbage
mid-body auto-segment chapter titles also deferred (shared LLM-title class).

## Russian shows (Финансы Просто + Привет, Русский!)

- **June 10 2026 Russian-shows pass** (FP + PR; review:
[`docs/russian_shows_review_2026_06_10.md`](docs/russian_shows_review_2026_06_10.md);
drift guards: `tests/test_russian_shows_quality_pass.py`): the spoken +
RSS AI disclosures are now LOCALIZED (`_AI_DISCLOSURE_RU` /
`_AI_DISCLOSURE_RSS_RU` in `run_show.py`, gated on `_RUSSIAN_SHOWS`) —
closing the "English disclosure on the Olya voice" wart from two prior
reviews; Russian feeds title episodes "Выпуск N: …"; closing-pool
coverage + `where` anchors fixed (FP's "Вот и всё" variant matched no
pattern; PR had ONE closing ever — now 3 rotating); floors FP 900→1000,
PR 650→800 (PR keeps `min_podcast_word_floor: 550`); NEW
`engine/vocab_tracker.py` + `shows/hooks/privet_russian.py` give PR
vocabulary memory — spaced-repetition review callbacks + a
no-reteach/theme-rotation list via `{vocab_review_section}` (Animals had
run 3 consecutive episodes; words never reappeared). Audio-affecting
changes → A/B-listen per landmine #17.

## SpaceX Daily

- **June 13 2026 quality pass** (review:
[`docs/reviews/spacex_review_2026_06_13.md`](docs/reviews/spacex_review_2026_06_13.md);
drift guards: `tests/test_spacex_show.py`,
`tests/test_network_quality_pass.py`): two days post-launch, after the
operator's same-day fixes for the Ep2 AI-chapter `A I` spacing and the
AI-section accuracy guardrail (Colossus/Anthropic is real — do not
relitigate). The theme miner mined source-attribution LABELS — the
bare-URL strip in `engine/show_memory.py` missed the markdown
`[Google News](url)` label, so `"google spacex"` shipped as the #1
recurring theme (latent network-wide: FF `science nasa`, M&A `reddit
localllama`); now strips the whole `[label](url)` construct first, and
the polluted `spacex_theme_history.json` was rebuilt clean. The rocket
thrust unit `tf` (tonne-force) was spoken letter-by-letter ("280 T F",
twice in Ep2) — a per-show `pronunciation_overrides()` in
`shows/hooks/spacex.py` expands `tf → tons-force` (a unit expansion, not
a respelling — outside landmine #17; A/B-listen the audio change anyway).
Deferred with levers: the SPCX price is spoken twice/episode (Market
Watch segment + closing block) — the clean fix needs the Closing chapter
marker reordered ahead of Market Watch to avoid an orphan-closing
regression; and "AI & Compute" chapter lumping (swallows trailing Top
News when the LLM emits news after the editorial markers) — observe Ep3+
before a prompt change.

- **June 18 2026 second pass** (review:
[`docs/reviews/spacex_review_2026_06_18.md`](docs/reviews/spacex_review_2026_06_18.md);
drift guard: `tests/test_spacex_show.py::TestClosingBeforeMarketWatch`):
both June-13 predictions HIT (themes clean, no `tf`/`T F`). Found + fixed a
P0 the snapshot's "clean chapters" check missed — **weekly-recap episodes
shipped with NO Closing chapter** (`chapters_ep003.json` ended at a
mis-titled "Market Watch"). The code-supplied closing block appends the
SPCX price into the sign-off, the Market Watch marker matches that price
phrase, and Market Watch was listed before Closing; dailies escaped via
the real Market Watch segment consuming the marker first (once-per-title),
but recaps have no such segment. Fixed by ordering the **Closing marker
ahead of Market Watch** (`where: end` keeps it pinned to the sign-off) —
metadata-only, no audio, zero regression on all 7 scripts. This also
clears the chapter blocker on the deferred price-twice fix. Deferred
(evidence strengthened): chronic under-length is the **Engineering Deep
Dive under-delivering its own spec** (140-181w vs the digest prompt's "3
paragraphs of 4-6 sentences" ~250-360w) — the expand-the-deep-dive lever
stays deferred pending the network four-show length A/B. The AI-lumping
and hook-jargon June-13 deferrals did NOT recur.
**June 19 2026 third pass** (review:
[`docs/reviews/spacex_review_2026_06_19.md`](docs/reviews/spacex_review_2026_06_19.md);
drift guards: `tests/test_pronunciation.py::TestReplaceTimes`,
`tests/test_spacex_show.py::TestLaunchTimePronunciation`): both June-18
predictions scored (deep-dive-still-short HIT — Ep8 139w; daily-Closing HIT,
recap pending). New P0 spoken garble: launch times **with seconds** shipped
mangled — the digest's `1:50:45 a.m.` was voiced "one fifty A M:45 a.m." and
`0850:45 UTC` as raw digits (Whisper-confirmed in Ep8 audio). The shared
`assets/pronunciation.py:replace_times` matcher was seconds-blind
(`(\d{1,2}):(\d{2})…` matched only `1:50`, stranding `:45`). Fix: drop
seconds (`(?::\d{2})?`), add a compact `0850:45 UTC` → "oh eight fifty U T C"
handler that runs before the HH:MM matcher, and tighten the trailing
whitespace so an absent AM/PM no longer glues the next word ("P MUTC"). A
latent network-wide bug surfacing on SpaceX because spaceflight reporting
gives T-0 to the second — the same spoken-garble class as the June-13
`tf`→`T F` fix. Deterministic number-normalization correctness change (not a
respelling) but changes spoken output — A/B-listen per landmine #17. The
deep-dive length lever + price-spoken-twice (8/8) stay deferred (reasons
hold); tomorrow-teaser "watch for the [next] <test>" frame now 6/8 (P2 monitor).

## Tesla Shorts Time

- **June 2026 quality pass** (drift guards: `tests/test_tesla_quality_pass.py`):
theme mining now reads the DIGEST only (the old code mined the narrative
TEMPLATE text every episode — "open questions" hit count 112 and drowned
real topics; `_THEME_STOPWORDS` + a one-time scrub fixed existing
histories). `auto_update_narrative_from_digest` auto-advances per-program
`last_mentioned_episode/date` on every episode (the tracker had sat 13
days stale on a daily show) — operator-curated `status` text still only
changes via `scripts/update_tesla_narrative.py`. The listener-value score
gained a 15%-weight length component (`target_words` kwarg). Tesla opts
into `llm.podcast_expand_below_target: true` — the one-shot expansion
retry fires on ANY below-target script, not only near the 60% skip floor
(9 of 10 episodes had shipped 15-35% under the 1600-word target). The X
teaser leads with the episode hook + links the episode blog post. The
prompts ban the "Taking a step back from today's headlines" opener,
rotate three First Principles frameworks, cap the vertical-integration
conclusion, enforce the Takeover/Top-12 zero-overlap check, and add
3-tier attribution discipline. Prompt changes alter generated output —
A/B-listen per landmine #17 and revert via git if quality dips.

- **June 10 2026 follow-up pass** (full review:
[`docs/tesla_review_2026_06_10.md`](docs/tesla_review_2026_06_10.md);
drift guards in `tests/test_tesla_quality_pass.py`,
`tests/test_chapters.py::TestPositionalConstraints`,
`tests/test_tesla_hook.py::TestClosingBlock`):
chapter markers gained positional `where: start|end` constraints +
once-per-title matching (the closing's "tesla shorts time" mention had
titled the closing "Introduction" on every episode); the spoken closing
now rotates 4 variants, phrases by market state, and OMITS the price
sentence when the quote failed validation (previously spoke "closed at
zero dollars, price unavailable"); the expansion retry now carries the
full digest (it previously saw only its own short script — it could not
add facts, the root cause of chronic under-length); ONE unified length
target (2,200–2,400 words ≈ 14–16 min, `min_podcast_words: 2000` — the
prompt had demanded four contradictory lengths); the performance loop is
LIVE (`scripts/update_tesla_performance.py` nightly derives
`strong_topics_last_30d` from OP3 download data — `record_performance_signal`
previously had zero callers); theme mining filters narrative-prose echo +
URLs and is idempotent per episode; program detection uses word-boundary
regexes (bare "unsupervised" no longer advances FSD); the spoken show
name dropped "Daily" to match the listing brand "Tesla Shorts Time";
content-tracker headlines filter junk/slur titles
(`_is_dedupe_worthy_title`); blog posts link the Story Tracker page.
Length/brand prompt changes alter shipped audio — A/B-listen per
landmine #17.

- **June 20 2026 second agent pass** (review:
[`docs/reviews/tesla_review_2026_06_20.md`](docs/reviews/tesla_review_2026_06_20.md);
drift guards: `tests/test_tesla_quality_pass.py`): scored June 10 — the
chapter-anchoring HIT (0/10 trailing-Introduction) but the length
prediction MISSED (Ep507-516 1254-1676w, all under the 2000 floor).
Three deterministic fixes. (1) The podcast-gen step spelled Teslarati —
the show's #1 source — phonetically as `Tesla-rah-tee` in 25+ episodes
(5 of the last 10), voiced as an audible garble (Whisper of Ep516:
"Tesla had RadT"); added to the blessed `engine.utils.fix_phonetic_garbles`
restore layer (removes a respelling → outside landmine #17, A/B anyway).
(2) The June-10 "drop Daily from the spoken brand" decision had MISSED
the pre-existing brand normalizer in `engine/generator.py`, which kept
normalizing TOWARD "Tesla Shorts Time Daily" — so the LLM-appended
"Daily" shipped in the spoken intro of 100% of episodes (Ep506-516);
the normalizer now drops the stray "Daily" (completes the approved
decision; A/B-listen). (3) 13F institutional-filing spam ("LLC Purchases
New Stake in Tesla", 3× in Ep516) now filtered at fetch via
`exclude_title_patterns` in `shows/tesla.yaml` (deterministic, no-A/B,
FF stock-filter class). Deferred with re-diagnosis: chronic under-length
is the DIGEST ceiling (Top-12 items ship 3 thin sentences from
Google-News snippets; script tracks the digest ~1:1) — same root cause
as FF/UC/PT, held behind the four-show length A/B (levers: digest-
expansion retry / First-Principles essay expansion). Also deferred:
chapter body navigation — fragment auto-segment titles (8/10) AND a new
no-body-chapter regression (2/10; `engine/chapters.py:208` never
implemented its docstring's "head spans most of script" auto-segment
trigger) — fix is network-scoped digest-driven titles.

## The DP Pod

- **July 2 2026 Ep1 rework (operator listened: "terrible and robotic"):**
theme song `assets/music/dp_pod.mp3` ("Do Positive", 4.5 min Suno track)
is the intro/outro bed; NEW `audio.debut_song_file`/`debut_song_episode`
(AudioConfig, generic no-op default) appends the FULL song after the
closing on Episode 1 only via `engine.audio.append_full_song` (after
chapter timestamps — the song must not stretch the proportional chapter
math); the debut is a DESIGNED episode via per-show overrides in
`engine/first_episode.py` (`_SHOW_DIGEST_EP1`/`_SHOW_PODCAST_EP1`:
founding statement → anchor discussion from the network's own First
Principles material → network tour → starter lever → on-air song intro);
`shows/hooks/dp_pod.py` supplies `{nerra_network_context}` (sibling-show
catalog + latest FP brief; setdefault-ed in pipeline/run_show so a hook
failure can't KeyError); the podcast prompt gained a DELIVERY — WRITE THE
ENERGY IN block (spoken-English volleys, ≥⅓ one-sentence turns, no
news-anchor phrasing — the anti-robotic levers) + a one-mention-max
cross-promo rule; `dialogue_pause_ms` 300→220. The shipped Ep001 was
retired (artifacts deleted, RSS items stripped, numbering back to 1) —
regenerate via workflow_dispatch; the schedule-event duplicate guard
doesn't apply to manual dispatch.
**July 2 2026 second rework (operator listened again: still robotic,
Dan especially; intro too short; too much show-info recap):** the LIVE
Ep1 intro/closing path is `engine/pipeline.py:run_generation_phase`
(run_show builds pod_vars but never passes them — BOTH Ep001 renders
aired pipeline's truncated `"please subscribe... "` literal); pipeline's
Ep1 block is now dialogue-aware + the generic literal completed. Grok
TTS docs pass (docs.x.ai): punctuation IS prosody (exclamation points
now encouraged where genuine), sanctioned inline tags with a hard
budget (≤10 of `[laugh]/[sigh]/[breath]/[pause]`, ≤4 `<emphasis>`; all
other wraps stay banned), documented `speed` param wired through
`grok_speak_chunk`→`synthesize_dialogue` (sent only when ≠1.0; dp_pod
pins 1.05), `dialogue_pause_ms` 220→180. Editorial repositioning
(All-In-inspired friends-reviewing-consequential-events): system prompt
celebrates builders/creators/contributors; "THE ANALYSIS IS THE SHOW"
(~⅓ facts / ⅔ hosts' unique-lens takes); digest widened from pure
good-news to consequential-with-agency + names the builders. Debut
override v2: 500+ word founding conversation introducing show AND
network, anchor material as SPRINGBOARD (≤3 recap sentences), network
tour capped at 3 shows/1 sentence each with editorial-boilerplate
phrases BANNED (the v1 render walled 5 near-verbatim "measured result…"
paragraphs). Second Ep001 retired the same way. Dan's voice ceiling is
the CLONE — docs: custom-voice quality tracks the reference clips;
re-record Dan's samples with expressive conversational takes (operator).
**July 4 2026 v4 review + community layer:** the v4 Ep001 render (much
improved — real disagreement, Frankl Think Positive debut, proper
personality closing, song appended) surfaced three fixable defects, all
fixed + retired the render (drift guards:
`tests/test_dp_pod_show.py::TestEp001V4Fixes`): the DIGEST expansion
retry pads by paraphrase-duplication exactly like the podcast retry did
(the founding brief re-told every beat; `_dedup_expansion_sentences` now
runs on the digest-retry output too — `engine/generator.py`, global but
a correctness strip); the pipeline's `effective_hook` fallback spoke a
raw markdown header on air when the digest lacked a HOOK line (fallback
now skips `#`/rule lines + strips bold; the dp_pod debut-digest override
also REQUIRES the HOOK line); and the cold open's passing "The Lever"
mention stole the Lever chapter at 74s (marker is now announce-anchored
— "brings us to/time for/now for The Lever" — with a SEGMENT-NAME
DISCIPLINE prompt block requiring short forms before announcements).
Website community layer ("a place to learn and encourage each other"):
the club page gained a **Mindset Shelf** (`_collect_dp_mindsets` in
`generate_html.py` extracts each digest's `### Think Positive` principle)
and a **Dispatch Wall** (`_collect_dp_dispatches` reads the
OPERATOR-CURATED `digests/dp_pod/dispatches.json` — real listener
dispatches only, per the club charter; empty file = honest empty state;
operator CLI: `scripts/add_dp_dispatch.py`).
Drift guards: `tests/test_dp_pod_show.py::TestCommunityLayer`.
**July 4 2026 level-drift fix + anthem canon (operator listened to v5:
"inconsistent and drifting between good sound level then quiet"):** root
cause is structural to dialogue mode — 30-40 independent Grok TTS calls
per episode, each at its own loudness, and `normalize_voice`'s
`loudnorm … linear=true` applies ONE gain to the whole file so inter-turn
variance survives to air (single-voice shows synthesize in one call and
never hit this). Fix: `_match_turn_levels` in `engine/tts_dialogue.py`
gain-matches every turn WAV to the MEDIAN mean level (volumedetect —
stable on 2-4s clips where loudnorm's integrated measure is not; ±12 dB
cap, <1 dB left alone, runs BEFORE pause padding so silence can't skew
the measure; verified 28 dB synthetic spread → 0). Second leak in the
same report: `append_full_song` concatenated the debut song at its native
master level — the song branch now runs `loudnorm I=-16`
(`_append_song_cmd`, episode branch untouched). Both change shipped audio
— A/B-listen per landmine #17. **Anthem:** the operator-supplied "Do
Positive" lyrics are canon at `assets/music/dp_pod_lyrics.md`; the
podcast prompt's THE SHOW ANTHEM block allows at most ONE verbatim lyric
phrase per episode (default ZERO — anti seeded-template), the Ep1 debut
override lets the song intro quote one chorus line exactly, and the club
page gained an Anthem section (chorus + collapsible full lyrics). Drift
guards: `tests/test_tts_dialogue.py::{TestTurnLevelMatching,
TestDebutSongLoudness}`, `tests/test_dp_pod_show.py::TestShowAnthem`
(including a prompt-quote-matches-canon check).
**July 4 2026 follow-up-episodes pass (operator approved Ep1 v6 — level
drift measured fixed at 0.52 dB stdev across 41 windows — and asked for
great regular episodes that regularly point to network shows/episodes):**
`shows/hooks/dp_pod.py` now builds a **FRESH ON THE NETWORK** block (each
sibling's actual latest episode within 3 days, read from the committed
`summaries_*.json` — entries are newest-FIRST, picked by max date) and a
**Think Positive rotation memory** (thinkers mined from recent dp_pod
digests → do-not-reuse list; roster in `_THINKERS`). The occasional
CROSS-PROMO became the regular **FROM THE NETWORK** beat: exactly ONE
grounded pointer per episode naming a REAL fresh episode, spoken as a
friend's recommendation, position/speaker rotating (never a fixed slot —
anti-tic); the digest gained a required-when-fresh **Network pick:** line
and the thinker-rotation rule. Depth lever: `min_digest_words` 700→1100
(Ep1 scripts capped ~1,200w vs the 1,550 target — the brief was the
ceiling). The shipped debut anchor `shows/dp_pod_debut_anchor.md` was
deleted (pin mechanism kept). Prompt/digest edits change output —
A/B-listen per landmine #17. Drift guards:
`tests/test_dp_pod_show.py::TestFollowUpEpisodes`.

## Unintended Consequences

- **June 12 2026 quality pass** (review:
[`docs/reviews/unintended_consequences_review_2026_06_12.md`](docs/reviews/unintended_consequences_review_2026_06_12.md);
drift guards: `tests/test_unintended_consequences_quality_pass.py`): UC
was missed by the Tesla/four-show/FP chapter hardening — no `where`
anchors, and seven keyword markers that assume the spoken prose contains
literal section words the podcast prompt forbids; the brand name
*Unintended Consequences* (contains "consequence") collided with the
body marker on both the intro and the sign-off, so 0/10 recent episodes
had a correct chapter shape (ep024 opened on "The Lesson"; ep028 ended
on "The Unintended Consequences"). Fixed by anchoring Introduction
(`where: start`) + Closing (`where: end`), dropping the unreliable middle
markers, and letting auto-segmentation fill the middle with in-order
content titles (the Introduction pattern includes a generic opening-word
fallback because the LLM rewrites the supplied intro on ~30% of episodes,
dropping the brand + "episode N") — verified 10/10, metadata-only.
The closing pool grew 2→4 and dropped "That wraps today's case" (the
prompt's WHAT TO AVOID block had banned that phrase while `intros.py`
supplied it verbatim on 5/10 episodes; the 2-entry pool repeated 3× in a
row, Ep026-028). Chronic under-length (857-1211w vs 1300 floor / 2200-
2800 target) is DEFERRED with the same root cause + lever as First
Principles: the digest is thin (700-960w), so the podcast — told to use
only the brief — is capped; the digest-expansion retry is the deferred
network lever, and the grok-4.3 narrative plateau is accepted. Closing-
pool + prompt edits change shipped audio — A/B-listen per landmine #17.

## Финансы Просто

- **June 16 2026 quality pass** (first dedicated FP review; combined June 10
pass was `docs/russian_shows_review_2026_06_10.md`; review:
[`docs/reviews/finansy_prosto_review_2026_06_16.md`](docs/reviews/finansy_prosto_review_2026_06_16.md);
drift guards: `tests/test_finansy_prosto_quality_pass.py`): scored the
June-10 floor-raise as a MISS (episodes still ~5 min / ~700w — the podcast
tracks a ~700w digest 1:1 and may not pad, so a podcast-side floor +
expand-retry can't help; re-attacked at the digest). Two listener-facing
P0s on the Olya voice: the YouTube call-out was an ENGLISH sentence (the
AI-disclosure wart class the June-10 pass localized, but the call-out in
`engine/intros._maybe_append_youtube_cta` was missed) — now Russian for
FP via `_RUSSIAN_SPOKEN_SHOWS` (PR stays English, it's taught in English);
and the "@" handle was voiced as the word "at" ("...YouTube **at at** Nerra
Network", 75+ times across six shows) — now stripped network-wide. The
closings said "до завтра" on an even-days show (EI-class cadence bug) — now
cadence-neutral ("до встречи"). P1s: `_extract_hook` now recognizes the
Russian `ЗАГОЛОВОК:` hook label (the FP/PR digest format), stopping a wasted
structural regen that fired on every FP episode (`digest_structural_regen:
true`, Ep45-54); the structural-retry corrective suffix was hardcoded with
Tesla section names ("Top 12 News Items, Tesla X Takeover…") and applied to
all shows — now generic. The digest prompt asks for 3-4 tips / 3 quick-news
/ 5-7 articles (matching the podcast's already-required minimum of 3 tips;
content is abundant at 69-129 articles/day). Call-out/closing/digest edits
change shipped audio — A/B-listen per landmine #17.
