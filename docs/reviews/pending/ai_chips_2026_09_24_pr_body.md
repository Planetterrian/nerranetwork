After three on-schedule episodes, ai_chips still ships ~950-word scripts against a 1,300 target because digests top out near 1,000 words; Ep2 re-tore-down the same laser news it just read and admitted consumer phone silicon, while chapter starts are fixed and grok-4.7 comma density is a clear hit.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0974**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes (first 7) where a news item's main subject is a model/software release rather than hardware, facilities, power, supply chain or policy | partial | No pure model-release leads in Ep1–3; Ep3 AMD/SuperMicro framed around agentic AI CPU needs but stayed on silicon/systems. |
| same-day stories shared with Models & Agents told without a new hardware or cost fact (read against the sibling block) | partial | Sibling block wired in hooks/ai_chips.py; Ep1–3 scripts show hardware/cost facts on chip stories — full M&A cross-read not in this bundle. |
| The Teardown re-explains a news item from the same episode | miss | Ep1 CoWoS news+teardown; Ep2 LitLit/Raven/Menhir lasers are both Supply Chain news and Teardown body. |
| absence sentences per episode (digest + script, before the filter; metric digest_absence_sentences_removed + script_absence_sentences_removed) | hit | Ep2/Ep3 transcripts ship no 'not disclosed/no figures' lines; Ep1 8+8 was baseline before filter. |
| first chapter startTime (s) on episodes 2-8 | hit | chapters_ep002.json and chapters_ep003.json both startTime 3.0 (≤25). |
| Teardown numbers not traceable to that day's articles (spot check, 3 episodes) | partial | Ep3 figures tied to named sources; Ep2 '$2.4 billion in 2025' ultrafast-laser market line still unanchored in transcript. |
| podcast_script_word_count median, first 7 episodes | miss | Ep1–3 scripts 953/1011/938 — median 953 vs expected ≥1100; Ep3 digest ~1034 ceiling. |
| commas per 100 words in the digest on a grok-4.7 episode | hit | Ep3 digest 5.2 commas/100w (script 7.0) on pinned grok-4.7 — already logged hit 2026-09-24. |
| x.com Sources per episode | partial | Ep3 still 3/14 x.com Sources; Ep3–9 median window incomplete. |
| dc_items_unlabelled after retry | partial | Lint corrected to site-only + two-site floor; no Ep4–8 yet to score the new behavior (old Ep3 '3' was a false positive). |
| Data Centres & Power sections with >= 1 site item | miss | Ep3 Data Centres carried zero site items (800 VDC paper, UnifiedBus, wasted-power claim); Ep4–10 window not open but Ep3 already fails the mix rule the prediction named. |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/ai_chips_digest.txt`** (prompt) — Selection-layer mirror of the new exclude patterns so the LLM does not re-admit handset copy that slips past RSS titles (Ep2 A20/Vivo).
```diff
- Prioritize, in order: (1) chips and systems that shipped or were formally launched with specifications; (2) engineering research published or presented inside the window — a paper, a conference result, a lab demonstration in chips, packaging, photonics, cooling or power — with what was measured; (3) data-centre sites announced, started, energized or cancelled, with capacity and location; (4) power, cooling and grid interconnection developments that constrain where compute can go; (5) memory, packaging and foundry capacity; (6) export controls, tariffs and industrial policy with a concrete rule or date; (7) capex disclosures with numbers. Reject consumer graphics cards and gaming GPUs, consumer-hardware deals and reviews, opinion without a new fact, earnings previews, and stock-price stories with no operational substance.
+ Prioritize, in order: (1) chips and systems that shipped or were formally launched with specifications; (2) engineering research published or presented inside the window — a paper, a conference result, a lab demonstration in chips, packaging, photonics, cooling or power — with what was measured; (3) data-centre sites announced, started, energized or cancelled, with capacity and location; (4) power, cooling and grid interconnection developments that constrain where compute can go; (5) memory, packaging and foundry capacity; (6) export controls, tariffs and industrial policy with a concrete rule or date; (7) capex disclosures with numbers. Reject consumer graphics cards and gaming GPUs, smartphones and consumer handsets (phone SoCs, OriginOS/Android flagship SKUs, iPhone/Galaxy package teardowns), consumer-hardware deals and reviews, opinion without a new fact, earnings previews, and stock-price stories with no operational substance. A mobile/edge module counts only when the source frames it as industrial, robotics, automotive, or data-centre infrastructure — never a retail phone launch.
```

**`shows/prompts/ai_chips_digest.txt`** (prompt) — Ep3 Data Centres had no site despite the section's job; dc_items_unlabelled correctly ignores non-sites — selection/mix is the lever (ledger 2026-09-24 correction). Digest-side only; supports length via real MW items.
```diff
- ### Data Centres & Power
- **3-5 items**: sites, capacity in megawatts, location, owner and tenant, energization dates, cooling approach, grid and generation deals. Same heading and sentence rules. Every SITE item's first sentence carries its state in one of exactly three words — announced, under construction, or energized — with the megawatts and the location the source gives; a source that gives no capacity figure leaves the item without one, never an estimate. A deal or policy item that is not a site needs no state word.
- Source: [EXACT URL]
+ ### Data Centres & Power
+ **3-5 items**: sites, capacity in megawatts, location, owner and tenant, energization dates, cooling approach, grid and generation deals. Same heading and sentence rules. Every SITE item's first sentence carries its state in one of exactly three words — announced, under construction, or energized — with the megawatts and the location the source gives; a source that gives no capacity figure leaves the item without one, never an estimate. A deal or policy item that is not a site needs no state word. Item-mix: when the fetched set includes any site-class article (a named place plus MW/IT load, or a groundbreaking / under-construction / energisation / substation / land-area cue), at least one item in this section MUST be that site with its state word — architecture whitepapers, fabric product notes, and generic efficiency claims fill remaining slots only, never the whole section (Ep3 shipped three non-sites and zero builds).
+ Source: [EXACT URL]
```

**`shows/prompts/ai_chips_digest.txt`** (prompt) — Second miss on teardown uniqueness in three episodes; name the Ep2 failure shape (vendor re-read) without seeding a new specimen topic the model can elect next.
```diff
- ### The Teardown: [Topic Title]
- One engineering explanation (220-320 words) of a mechanism behind today's layer of the stack — why a packaging step bottlenecks supply, what actually limits rack power density, how a cooling method trades water for energy, why an interconnect choice matters. It uses your engineering knowledge for the MECHANISM, in words, and today's articles for any FACT. Every number in it — a wafer count, a capacity, a wattage, a percentage, a price — comes from an article above and its source is named in the sentence; a figure you would supply from memory is left out and the mechanism is explained without it (Ep1's teardown gave wafer-per-month and reticle-per-wafer ranges that no article contained). Its subject must NOT be the subject of any news item above, including a forecast or capacity item about the same technology; it is a second story, not a second pass. Carry as many sourced numbers as the articles support, up to four. Open on the mechanism or the number, never on a claim about what most people believe.
+ ### The Teardown: [Topic Title]
+ One engineering explanation (220-320 words) of a mechanism behind today's layer of the stack — why a packaging step bottlenecks supply, what actually limits rack power density, how a cooling method trades water for energy, why an interconnect choice matters. It uses your engineering knowledge for the MECHANISM, in words, and today's articles for any FACT. Every number in it — a wafer count, a capacity, a wattage, a percentage, a price — comes from an article above and its source is named in the sentence; a figure you would supply from memory is left out and the mechanism is explained without it (Ep1's teardown gave wafer-per-month and reticle-per-wafer ranges that no article contained). Its subject must NOT be the subject of any news item above, including a forecast, capacity, vendor, or product item about the same technology or the same named companies — Ep2's Supply Chain laser items (LitLit, Raven, Menhir) were illegally re-read as the Teardown. Pick a mechanism those items depend on but do not narrate the same vendors' shipment/factory facts again. It is a second story, not a second pass. Carry as many sourced numbers as the articles support, up to four. Open on the mechanism or the number, never on a claim about what most people believe.
```

**`shows/prompts/ai_chips_podcast.txt`** (prompt) — De-seed by shape (2/3 'take it apart and the') with a verbatim ban and no new example sentence; hard-require Horizon phrase after Ep2 dropped it and shipped sentence-debris chapter titles.
```diff
- [The Teardown] A second story, not a second pass: nothing in it restates a fact already spoken. Its first sentence must contain the phrase "take it apart" once, inside a natural sentence (podcast-app chapters key on it); vary everything around it. Build from the mechanism to the numbers; carry at least four numbers; close on when the tradeoff flips.
- 
- [On the Horizon] Read LAST before the teaser: its first sentence contains the phrase "on the horizon" once, inside a natural sentence that carries the first item's date (podcast-app chapters key on it). One sentence each for two or three dated items, the date spoken in each. This is the show's fixed close — a listener learns to wait for it.
+ [The Teardown] A second story, not a second pass: nothing in it restates a fact already spoken. Its first sentence must contain the phrase "take it apart" once, inside a natural sentence (podcast-app chapters key on it). Ban the frozen opener shape "Take it apart and the…" — the phrase may not be the first three words, and the three words after the phrase must not be "and the" + a noun. Vary the syntactic frame every episode (clause-medial phrase is fine). Build from the mechanism to the numbers; carry at least four numbers; close on when the tradeoff flips.
+ 
+ [On the Horizon] Read LAST before the teaser: its first sentence contains the phrase "on the horizon" once, inside a natural sentence that carries the first item's date (podcast-app chapters key on it). Never skip this phrase — without it the podcast-app Horizon chapter does not fire (Ep2). One sentence each for two or three dated items, the date spoken in each. This is the show's fixed close — a listener learns to wait for it.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/ai_chips.yaml`** (config): Ep2 transcript admitted Vivo X500 Pro/Dimensity 9600 Pro and iPhone 18 Pro Max A20 as Silicon items; existing patterns only block gaming gear, shopping deals, and how-tos. Fetch-side drop is higher-yield than prompt prose alone.
- **`tests/test_ai_chips_quality_pass.py`** (code): Every behavioral fix needs a drift-guard; show has launch tests but no quality-pass module yet for Ep2 handset leak, Horizon phrase, or teardown shape ban.
- **`engine/digest_lint.py`** (code): Prompt-only teardown uniqueness missed twice (Ep1 CoWoS, Ep2 lasers). Garble/lint class is highest-yield per meta-review; keep show opt-in like absence_sentence_filter.

## Deferred (carried forward)
- Prune x_accounts handles that log No recent posts once live per-account fetch counts exist (carried from 2026-09-22 Ep1 review).
- Network-wide absence-sentence filter (precision not proven on other shows).
- Enable newsletter / YouTube / X distribution (launch policy — First Principles pattern; operator date, not review).
- Dedicated audio theme (still assets/music/ModelsAgents.mp3 per plan §5c).
- Re-grade full RSS list with check_feeds.py ai_chips on a runner (carried from scaffold).
- Escalate Data Centres site-mix to an explicit operator decision if Ep4–6 still ship zero sites after the prompt mix rule — do not file the same mix proposal a third time.
- preferred_domains tightening if x.com Sources median stays >1 after Ep9 window closes.
- Any podcast-side length lever (min_podcast_words raise, podcast_expand_below_target, 'write longer' prompt pressure) — meta-review miss class; digest ceiling only.

<sub>tokens: 24621 in / 8034 out</sub>