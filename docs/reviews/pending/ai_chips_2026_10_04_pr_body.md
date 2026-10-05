Ep4–13 still ship ~9/10 scripts under 1300 words because digests remain the ceiling; consumer handset silicon and Teardown-as-news-rerun still leak, while 'the trade-off flips' calcified into a 7/10 closing tic and Ep9 dropped its Teardown chapter entirely.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1259**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| podcast_script_word_count median Ep4–10 | miss | Ep4–13 median ~1047 words; 9/10 under 1300 (only ep9 at 1333). |
| digest_word_count median Ep4–10 | miss | Scripts still capped well under target with digest_expand already on — substrate did not reach ≥1250 effective. |
| Teardown subject overlap with same-ep news items (manual or lint) | miss | Ep7 MX-1/CXL is both news and Teardown; Ep9 chapters omit Teardown entirely. |
| scripts containing consumer handset/smartphone Silicon items (Vivo/iPhone/OriginOS/Snapdragon flagship phone SKUs) | miss | Ep6 body+Horizon cover Snapdragon 8 Elite Gen 6 flagship phone chips. |
| scripts missing required chapter phrases 'take it apart' OR 'on the horizon' | partial | Horizon present Ep4–8,10–13; Ep9 has no Teardown chapter (anchor likely missing). |
| Teardown first sentence matching shape 'Take it apart and the…' | hit | Opens varied across Ep4–13 (floor plate, aisle, coolant, LIM, 3D V-cache, wafer chain). |
| Data Centres & Power with >=1 site item when fetch had a site-class article | partial | Ep4 Applied Digital 210 MW Brookwood site; improved vs Ep3 zero-site, not proven ≥5/7. |
| dc_items_unlabelled after retry | hit | No recurrence of Ep3-style false-positive unlabelled storms after site-only + two-site floor. |
| x.com Sources per episode | partial | Ep3–9 median window not fully re-counted from digests in this bundle. |
| commas per 100 words in the digest on a grok-4.7 episode | hit | Most Ep4–13 scripts 4.7–6.6 commas/100w; ep7 1.7 is fallback outlier. |
| absence sentences per episode (digest + script, before the filter; metric digest_absence_sentences_removed + script_absence_sentences_removed) | hit | Ep4–13 transcripts ship no not-disclosed/no-figures absence lines. |
| first chapter startTime (s) on episodes 2-8 | hit | chapters_ep004–013 all startTime 3.0. |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/ai_chips_digest.txt`** (prompt) — Selection-layer mirror of new exclude patterns so the LLM does not re-admit handset copy that slips past RSS titles (Ep2, Ep6).
```diff
- Reject consumer graphics cards and gaming GPUs, consumer-hardware deals and reviews, opinion without a new fact, earnings previews, and stock-price stories with no operational substance.
+ Reject consumer graphics cards and gaming GPUs, consumer handsets and flagship smartphone SoCs (iPhone, Vivo, Pixel, Galaxy, Snapdragon 8 Elite mobile SKUs, OriginOS performance write-ups), consumer-hardware deals and reviews, opinion without a new fact, earnings previews, and stock-price stories with no operational substance. Edge/industrial/auto modules and datacenter CPUs stay in.
```

**`shows/prompts/ai_chips_digest.txt`** (prompt) — Third documented same-ep teardown overlap (Ep7). Name failure shape without seeding a specimen topic; pair with lint below.
```diff
- Its subject must NOT be the subject of any news item above, including a forecast or capacity item about the same technology; it is a second story, not a second pass. Carry as many sourced numbers as the articles support, up to four. Open on the mechanism or the number, never on a claim about what most people believe.
+ Its subject must NOT be the subject of any news item above, including a forecast, capacity, or named-part item about the same technology or the same vendor product already headed in Silicon / Data Centres / Supply Chain (Ep1 CoWoS, Ep2 laser vendors, Ep7 MX-1/CXL — failure shape: Teardown re-reads a news heading). It is a second story, not a second pass. Carry as many sourced numbers as the articles support, up to four. Open on the mechanism or the number, never on a claim about what most people believe, and never on a restatement of a news item's first sentence.
```

**`shows/prompts/ai_chips_podcast.txt`** (prompt) — De-seed by shape: prompt's own 'close on when the tradeoff flips' became the 7/10 tic. Verbatim ban + shape description; no new example sentence. Also hard-keeps the chapter anchor after Ep9 dropped Teardown.
```diff
- [The Teardown] A second story, not a second pass: nothing in it restates a fact already spoken. Its first sentence must contain the phrase "take it apart" once, inside a natural sentence (podcast-app chapters key on it); vary everything around it. Build from the mechanism to the numbers; carry at least four numbers; close on when the tradeoff flips.
+ [The Teardown] A second story, not a second pass: nothing in it restates a fact already spoken. Its first sentence must contain the phrase "take it apart" once, inside a natural sentence (podcast-app chapters key on it); vary everything around that phrase — never the skeleton "take it apart and the…". Build from the mechanism to the numbers; carry at least four numbers. Close on one concrete condition that changes the design choice (a limit that moves, a resource that runs out, a threshold a buyer actually hits); vary the predicate every episode. Verbatim ban: do not write "the trade-off flips" / "the tradeoff flips" / "trade-off flips when" — that closer calcified across seven straight episodes.
```

**`shows/prompts/ai_chips_podcast.txt`** (prompt) — Keep hard phrase contract (Ep2 miss fixed in later eps); block Ep6-style phone SKU on Horizon.
```diff
- [On the Horizon] Read LAST before the teaser: its first sentence contains the phrase "on the horizon" once, inside a natural sentence that carries the first item's date (podcast-app chapters key on it). One sentence each for two or three dated items, the date spoken in each. This is the show's fixed close — a listener learns to wait for it.
+ [On the Horizon] Read LAST before the teaser: its first sentence contains the phrase "on the horizon" once, inside a natural sentence that carries the first item's date (podcast-app chapters key on it — if this phrase is missing the Horizon chapter never fires). One sentence each for two or three dated items, the date spoken in each. Never use Horizon to re-date a consumer handset SKU. This is the show's fixed close — a listener learns to wait for it.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/ai_chips.yaml`** (config): Ep6 still admitted Qualcomm flagship phone chips; Ep2 was Vivo/iPhone. Fetch-side drop is highest-yield; prior 09-24 proposal was not applied.
- **`shows/ai_chips.yaml`** (config): Prompt-only teardown uniqueness missed Ep1, Ep2, Ep7. Opt-in lint (entity/title overlap vs Silicon/DC/Supply headings) forces one-shot retry; garble/lint class is highest-yield. Requires matching implementation in engine/digest_lint.py.
- **`engine/digest_lint.py`** (code): Mechanical enforcement after three prompt-only misses; keep show opt-in.
- **`tests/test_ai_chips_quality_pass.py`** (code): Every behavioral fix needs a drift-guard; show still lacks a quality-pass module covering Ep6 handset, Ep9 missing Teardown, and trade-off-flips tic.

## Deferred (carried forward)
- Prune x_accounts handles that log No recent posts once live per-account fetch counts exist.
- Network-wide absence-sentence filter (precision not proven on other shows).
- YouTube / X distribution enable (launch policy — operator date).
- Dedicated audio theme (still assets/music/ModelsAgents.mp3 per plan §5c).
- Re-grade full RSS list with check_feeds.py ai_chips on a runner.
- preferred_domains tightening if x.com Sources median stays >1 after window closes.
- Any podcast-side length lever (min_podcast_words raise, podcast_expand_below_target, write-longer prompt pressure) — do_not_retry.
- Re-proposing dc_items_unlabelled as the fix for zero DC sites — do_not_retry; mix/selection is separate.
- Operator decision on digest format arithmetic if Ep14–20 digest median still <1250 after substance floors — escalate, do not third-file the same mix prompt.
- Data-side Teardown-close / frame memory if 'trade-off flips' successor still converges after one prompt de-seed (second miss → memory, not third prompt filing).

<sub>tokens: 43100 in / 6617 out</sub>