# Fascinating Frontiers — Quality Review (June 16, 2026)

Second scheduled-agent review of Fascinating Frontiers (FF). Scores the June
12 pass ([`fascinating_frontiers_review_2026_06_12.md`](fascinating_frontiers_review_2026_06_12.md))
against the four episodes shipped since (Ep100–103) and attacks the next
tier. Snapshot: `scripts/review_snapshot.py fascinating_frontiers`.

/ TLDR /
- **Both June-12 predictions HIT.** Phonetic garbles (`En-sell-uh-dus` /
  `Tee-en-wen`) are gone from Ep100–103 `_tts.txt`; `fascinating frontiers`
  no longer appears in any new `top_themes` list (Ep100+ lead with "dark
  matter"). Deterministic fixes held.
- **New P0/P1 (this pass's headline): SPCX stock-market intrusion.** Since the
  SpaceX/SPCX IPO (June 12) the Google-News "SpaceX" queries flood FF — a
  *space-and-astronomy science* show — with pure stock-market items. **Ep103
  shipped FOUR of fifteen stories as market action** (an $85.7B funding round
  told twice, a "$60B all-stock merger with Cursor", NASDAQ index inclusion, a
  20% share move), duplicative and off-brand, crowding out astronomy and
  overlapping directly with SpaceX Daily + Modern Investing. Fixed at fetch
  time (deterministic title filter, same class as the accepted almanac filter)
  + a digest-prompt scope backstop. Verified against today's live feeds: 7
  SPCX market-action items dropped, the Falcon 9 *launch* story kept.
- **Already resolved upstream:** the `@`→"at at" YouTube-CTA bug ("YouTube at
  at Nerra Network" in Ep103) was fixed network-wide by the June-16 Финансы
  Просто pass (`engine/intros.py:925`, `lstrip("@")`); Ep103 just predates it.
  No action — verify clean on Ep104+.

---

## Scoring the June-12 pass (predictions)

| Prediction | Verdict | Evidence |
|---|---|---|
| `En-sell-uh-dus`/`Tee-en-wen` → 0 in new episodes | **hit** | grep of Ep100–103 `_tts.txt`: zero phonetic-garble hits. |
| `fascinating frontiers` never in new `top_themes` | **hit** | `theme_history.json` Ep100/101/102/103 top_themes all lead with `dark matter`; show-name bigram absent. |

The `science nasa` residual (count noted June 12) **persists** (still in the
top-6 every episode) — carried forward, deferred (lower harm, filtering risks
real content).

---

## P0 / P1 — SPCX stock-market intrusion *(shipped)*

FF's sourcing (`shows/fascinating_frontiers.yaml:35-44`: Google News
"space+exploration", "NASA+SpaceX+rocket+launch", r/spacex) pulls general
"SpaceX" news. Before June 12 that was almost all missions/science. After the
SPCX IPO it includes a daily stream of ticker news. The digest prompt had **no
scope-exclusion** for stock items, and the `{cross_show_context}` overlap
nudge (digest line 64-67) did not deflect them.

**Evidence — Ep103 (June 16) digest Top-15** (`Fascinating_Frontiers_Ep103_20260616.md`):

| # | Title | Class |
|---|---|---|
| 3 | SpaceX Raises Record $85.7 Billion in Funding Round (`$2.5T market cap`) | market action |
| 13 | Space Exploration Files for $60 Billion Merger (with **Cursor**) | market action |
| 14 | SPCX Added to NASDAQ Telecom Index | market action |
| 15 | SPCX Shares Rise 20 Percent After Funding News (`$2.5T`, greenshoe) | market action |

Stories #3 and #15 are the **same funding event** told twice (both cite the
$2.5T cap + greenshoe) — the podcast (`..._Ep103_..._tts.txt`) faithfully
covered both, plus the nonsensical "$60B merger with Cursor" and the index-
rebalancing item. A space-science listener does not want greenshoe options and
NASDAQ rebalancing; this is SpaceX Daily / Modern Investing territory.

Recurrence: Ep097/099/102 had **0** stock hits; Ep098/100 had **1** (the
legitimate "SpaceX goes public" space-policy milestone); **Ep103 had 7**. This
is an emerging, recurring spike that will continue as long as SPCX is a hot
ticker.

### Fix 1 — deterministic fetch-time title filter *(no A/B)*

Added a stock/market block to FF's `exclude_title_patterns`
(`shows/fascinating_frontiers.yaml`), reusing
`engine.utils.drop_excluded_titles` (the same mechanism already accepted for
the almanac filter). Patterns target market-action titles — `SPCX`, `IPO`,
`market cap`, `greenshoe`, `funding round`, `shares <move>`, `<$/billion>
merger`, `index inclusion/rebalancing` — while **keeping** SpaceX
mission/engineering/science news.

A bare `\b(nasdaq|nyse)\b` pattern was tried and **removed after the live test
caught a false positive**: it dropped *"SpaceX launches its first Falcon 9
rocket since Nasdaq debut"* — a launch story, core FF content. Every real
stock item already trips a more specific pattern, so the exchange name on its
own is unnecessary and unsafe (regression guard added).

**Live verification (today's FF feeds, 125 unique titles):**
```
DROPPED (7 market-action + 1 pre-existing almanac):
  x SPCX Stock Rockets After Historic Tech-Sector IPO Debut
  x SpaceX IPO brings Starship to NYC | Space photo of the day...
  x SpaceX makes first acquisition post-IPO
  x Space Exploration (NASDAQ: SPCX) plans $60B all-stock merger with Cursor
  x Space Exploration Technologies (SPCX) Continues Strong Post-IPO Rally with 9% Gain
  x Space Exploration Technologies Corp.(NasdaqGS:SPCX) added to NASDAQ Telecom Index
  x SpaceX shares skyrocket as money raised hits $85.7 billion
  x 2026 Full Moon calendar... (existing almanac filter)
KEPT: "SpaceX launches its first Falcon 9 rocket since Nasdaq debut" ✓
      "SpaceX Cargo Dragon Departs Space Station With Science Research" ✓
```

### Fix 2 — digest-prompt scope backstop *(⚠️ A/B-listen, landmine #17)*

Added a `NO STOCK / MARKET ITEMS` bullet to the digest prompt's SELECTION
section (`shows/prompts/fascinating_frontiers_digest.txt`) — defense-in-depth
for any market item whose *title* doesn't trip Fix 1 (body-financial). It
explicitly keeps a space company's missions/launches/hardware/science/NASA
contracts and bans restating one funding event as a second "shares rose" item.
Renders clean (`test_prompt_fidelity.py`); since Fix 1 removes the stock items
at fetch, the LLM rarely sees them, so this is a backstop, not the primary lever.

**Guards:** `tests/test_fascinating_frontiers_quality_pass.py::TestStockMarketTitleFilter`
(drops the four Ep103 titles; keeps nine mission/science/contract/launch
titles incl. the Falcon-9-since-Nasdaq regression; asserts the prompt bullet).

---

## P1 — chronic under-length *(carried forward, still deferred)*

Snapshot: Ep94–103 median ~1500w, 9 of 10 below the 1700 floor (Ep100 1753w
the lone pass). This is the same digest-ceiling problem the June-12 pass
verified and deferred (RSS snippets cap the digest; the podcast can't exceed
it without banned padding — `do_not_retry`: "harder prompt pressure"). The
only legitimate lever — expanding the **Cosmic Deep Dive** (the one section
licensed to use the model's own astrophysics knowledge) — remains deferred
until the operator's four-show length A/B settles (no revert of the June-10
floor observed; status unknown). Shipping a second length-oriented audio
change in the same PR as the stock-scope fix would confound that A/B. Carried
forward unchanged.

---

## P2 — growth / discoverability

No new action. Hook-led X teaser, per-episode blog title, value-prop RSS
description, chapter shape (10/10 clean) all verified holding from prior passes.

---

## Findings checked and dismissed (for the record)

- **"I'm Patrick and Vancouver"** (snapshot repeated-phrase, 6/10) — Whisper
  mishearing of "in"; the `_tts.txt` correctly says "I'm Patrick in Vancouver".
  Not a bug.
- **"YouTube at at Nerra Network"** (Ep103 `_tts.txt`) — real `@`→"at" bug, but
  **already fixed in main** by the June-16 FP pass (`engine/intros.py:925`
  `lstrip("@")`). Ep103 predates the merge. Verify on Ep104+.
- **"Keep an eye on…"** (7/10) — the prompt's intended Tomorrow-Teaser opener
  (podcast prompt line 122). Not a tic.

## Shipped this pass

| Change | File | A/B needed? |
|---|---|---|
| Stock/market `exclude_title_patterns` | `shows/fascinating_frontiers.yaml` | No (deterministic fetch filter) |
| `NO STOCK / MARKET ITEMS` scope bullet | `shows/prompts/fascinating_frontiers_digest.txt` | **Yes** (digest-prompt edit) |
| Drift guards | `tests/test_fascinating_frontiers_quality_pass.py` | — |

## ⚠️ A/B-listen required (landmine #17)

- **Digest-prompt scope bullet** (`fascinating_frontiers_digest.txt`). Low
  regression risk (editorial-scope clarification, not a creative/length
  change), but it changes generated digest text. Listen to the next episode to
  confirm SpaceX *mission* coverage is unaffected. The deterministic title
  filter (Fix 1) is **not** audio-affecting in the creative sense — it only
  removes off-topic articles before the LLM, same class as the accepted
  almanac filter.

## Tests

`pytest tests/test_fascinating_frontiers_quality_pass.py
tests/test_prompt_fidelity.py tests/test_prompt_quality_pass.py
tests/test_episode_validity.py tests/test_four_show_quality_pass.py
tests/test_utils.py tests/test_network_quality_pass.py` — **205 passed**.
Live filter demonstration run against today's FF feeds (above).
