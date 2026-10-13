# Network review — 2026-10-13

Operator brief: a thorough review of all the recent show runs for content,
quality, information, presentation and enjoyment, and anything else that
positively impacts the network. Window: the Oct 12 and Oct 13 slates (45
episodes on 28 shows, plus Nerra Daily Ep053), every Actions run since
Oct 12 00:00 UTC, the dashboard, the audience headline and the register.
Ears: `_tts.txt` + Whisper transcripts, read by three parallel reviewers
(flagships; the Mira cohort; MIT/UC/FPD/AI Chips/MAG 7/weeklies/Russian),
every claim re-verified against the file before it was acted on.

Ledger: `docs/reviews/ledger/network.yaml` (2026-10-13; the 10-01 and 10-05
predictions are scored there). Register: `network-review-2026-10-13`.
Guards: `tests/test_network_review_2026_10_13.py`.

## 0. Health, in one table

| | |
|---|---|
| Runs | 100% success on every show (n=30 windows); Tesla p95 2,608 s, Omni View 2,456 s, MIT 2,403 s against the 3,000 s budget — the long-form render (600-1,364 s) is the cost |
| Spoken-text gate | 45/45 pass (Привет after one re-synthesis) |
| Script arms | every episode served its configured model; no fallback on Oct 12-13 (Omni View fell back on 10-08 and 10-09) |
| Claims | desks 10-21 verified per episode; the 4.6 flagship scripts 1-11 (SpaceX 1 and 2) |
| Story breaks | first two episodes: Top World Ep021 8 of 9 placed, Prediction Markets Ep021 6 of 8; transcript shifted with the audio |
| Nerra Daily Ep053 | 23 segments, every cut frame-anchored, `missing_expected []`, handoffs 0/22 show-name-led |
| Audience (OP3) | network week 1,772 → 2,889 → 4,032; SpaceX 1,292 of its 4,073 30-day downloads in the last 7 — read with the catalogue-sweep rule (Oct 9) before calling it growth |
| YouTube | EN views +28.7% WoW, RU +30.9%; long 102 views/video, Shorts 61 |
| Cost | $288/30 d network, $88 last 7 d (~$375/mo run rate): the flagships $0.9-1.0/episode; multilingual (~$11/show/mo) and images (~$7.7/show/mo) are the two largest lines |
| Workflow churn | 390 Actions runs on Oct 12, ~340 of them no-ops: 288 Voices fire-ticks (GitHub's own cron delivered 4), 25 fallback show crons each triggering a no-op multilingual + edition run |

## 1. Findings and what shipped

### P0 — listener-facing, shipping today

**grok-4.7 narrates its sourcing discipline, and on Oct 13 the shapes moved
past the Oct 12 filter.** North America Ep020: "The Guardian" eighteen
times, ten sentences of "`<Outlet>` is the source for the order, the court,
the judge…", "not a finding by this show on the underlying case". Africa &
Middle East Ep021: "Progress Watch for the day had none." (the Oct 12
pattern required a colon), "…are the facts The National reports on the
decision", "which is the limit of what Premium Times reports", "What is on
the record, then, is…". MAG 7 Ep021: "not another retelling of the race".
None matched `is_absence_sentence`. The prompt already says "names its
newsroom ONCE" and "never what the reporting did or did not include" —
stated and broken, so code. **Shipped**: five shapes in
`engine/absence_sentences.py`, calibrated against all 2,320 committed
scripts (the prose "The facts on confirmed cases are consistent across
reports" is not matched); the Progress Watch echo without the colon; and a
CLAUSE-level cut for "`<Outlet>` is the source for" — Collingwood Ep3 wrote
"Environment Canada is the source for those figures, and the current
reading given is eleven point zero degrees", and the temperature stays
(`cut_sourcing_clause`; a list inside the clause is never a clause
boundary). Top World's doubled place tag ("In Pakistan, in Asia," on 7 of
10 items of Ep020; 18 across the corpus, all Top World) is stripped to one
tag and the prompt line that seeded it ("names the country and the
region") now describes one place phrase.

**Tesla Ep632 led with a story the show had told on three recent days.**
Hook: "Tesla ended Solar Roof sales after installing roughly 3,000 units…"
— Ep624's hook on Oct 4, and in Ep580/581/582/587/592/606/610; the lead
plus the First Principles essay was a third of the episode, on an August
event, with the ALREADY-COVERED note under the article saying "do not make
it the hook again". The 10-01 prediction on story clusters is scored
*partial* for the same reason (Tesla retells 1-2 clustered pairs a day;
M&A 0 on 12 of 13). **Shipped**: a hook that matches the recurrence window
on two or more prior days is a structural defect and spends the one-shot
regeneration (`HOOK_RECURRENCE_MIN_DAYS`, run_show; metric
`hook_recurrence_days`). Replayed on Tesla's last 16 hooks: fires once
(10-12, times=3); a story covered once before (10-04/05/06) passes as an
update.

**SpaceX said "unchanged on the session" two days running while the stock
moved.** `api/spcx.json`: price 163.42 / prev_close 163.42 from
`yfinance_fast_info` at 09:20 UTC — inside the pre-market window, before
the first print, when `fast_info.last_price` IS the previous close.
**Shipped**: `_no_trade_yet` — a fast_info quote equal to its previous
close takes the move from history's second-last close and is spoken as
"closed at" (`shows/hooks/spacex.py`).

**"Starlink fifteen to twenty-five mission"** (Ep129) — `replace_number_ranges`
read the designator as a range; 38 committed scripts carry "Starlink/Group
n to n". **Shipped**: `replace_mission_designators` (two numbers, no
"to"). Same pass: **"ZLAT.TO" read as one word** opened MIT Ep199 (90
scripts carry a `.TO` ticker) — `spell_exchange_suffix_tickers`.

**Models & Agents spelled arXiv letter by letter 8-9 times an episode**
(Whisper: "RxIV", "RXIV", "RX-IV"; zero in Ep191-200, every episode since
the 4.6 arm writes "on arXiv"). **Shipped** (⚠️ A/B): `arXiv: "archive"` in
`shows/pronunciation_map.yaml` — a real word, not a phonetic respelling.

### P1 — quality ceiling

- **`x_only_lead` was a no-op on five of its own shows.** The lead was
  matched by exact header name; MAB leads with "The Big Story", FF and
  Planetterrian with "Top 12 …". MAB Ep195's Big Story cited only
  `x.com/emollick` and `digest_lints_fired` read `[]`. Shipped:
  `is_lead_section` (name or "Top " prefix) and Reddit beside X in the
  rule (Planetterrian Ep212 led its menopause story on r/science and never
  named the paper). Replay, last 14 digests: FF 0, PT 0, MAB 1, M&A 1.
- **Whisper echo tokens reached captions.** "Texas. Texas." (Tesla Ep633),
  "tomorrow. Tomorrow." (M&A Ep202): the second token has probability
  0.016-0.022, abuts the real word and usually opens the next segment —
  a transcription artifact, not audio (the real word reads 0.5-0.999). 159
  across 2,222 transcripts; 149 adjacent duplicates ABOVE 0.1 are real
  repeats and stay. Shipped: `drop_echo_words` in `engine/transcripts.py`
  (words and text; cross-segment).
- **The WYNTK lint fired on 5 of 5 Prediction Markets episodes** — one
  wasted 4.7 digest call a day — because three cohort prompts
  (prediction_markets, vancouver, collingwood) never carried the clause the
  lint checks ("Its FIRST sentence is the hook's story"), while the desks,
  MAG 7, AI Chips, Peptides and Longevity do. Shipped: the clause, and a
  guard that every `wyntk_hook_match` show states it.
- **MIT aired "today's snapshot does not include a year-to-date figure"
  on both days** with `benchmark.ytd_pct` +17.26% in the tracker: the
  digest's Market Pulse dropped the YTD, the podcast prompt read the
  digest, and its "if unavailable, say so" clause did the rest. Shipped:
  `{nasdaq_benchmark_line}` (the block's first line, never the scoreboard)
  in the Market Pulse spec, set by the hook, defaulted in `pipeline.py`
  (⚠️ A/B).
- **MAG 7's Company Desk floor contradicted its prompt.** "A company with
  no genuine news is omitted — never pad" against `min_items=2`; one item
  on 4 of the last 10 days, logged as a validation failure every time
  (an under-floor section is never regenerated; only empty/absent is).
  Shipped: floor 1.
- **UC typed a sibling's cadence** — "Environmental Intelligence covers
  the regulatory side every Monday" became "daily" on air (Ep140).
  Shipped: the line carries no cadence word; a guard sweeps every prompt
  for a weekly show's name beside "daily"/"every day".
- **The Voices fire-tick dispatches a GitHub job every five minutes** —
  288/day, ~75 s each, GitHub's own cron delivering 4 — and almost every
  one finds nothing: `fire_interviews.py` acts on interviews at
  briefed/scheduled inside [T-30 min, T+135 min], the browser no-show
  sweep (two days back) and live runs. Shipped: `fireTickDue` in the
  Worker reads the same table first; fail-open on any error; the :00/:30
  ticks dispatch unconditionally. **Operator: `wrangler deploy` in
  `workers/voices`.**

### P2 — noted, not shipped

- Omni View Asia Pacific's promo tail runs ~95 words on a 949-word body
  (rating ask + network line + next-listen + Nerra Daily plug).
- Prediction Markets Ep020 Board line: "Who wins the Senate pending a
  Hormuz agreement by October 23 — no Hormuz agreement leading" — the
  Gamma event/market join; read the shapes before changing
  `engine/prediction_board.py`.
- Nerra Daily: handoffs restate the segment's hook seconds before it
  plays; the field note names no outlet.
- FF Ep220: six absence sentences on the Iran item and "Cosmic Deep Dive:"
  spoken as a label — FF and Planetterrian have the absence filter off
  (config flip, A/B).
- DP Pod: "checklist" in 4 of the last 6 weeks; `_recent_banter_phrases`
  mines 2-3 word phrases only.
- Pronunciation asks the reviewers raised (dirhams, lycées, La France
  Insoumise, Macquarie, Andøya): phonetic respellings — landmine #17,
  not done.
- The 25 fallback show crons a day each trigger a no-op multilingual run
  and a no-op edition run (~1 runner-hour/day).

### Checked and already fixed on Oct 12 (verify next run)

FP Ep087's spoken "Source: [kalkine.ca]" (the bracket shape shipped Oct 12
after the episode); MIT Ep198's `<|eos|>` + doubled closing (Ep199 clean);
DP Pod "a family of daily podcasts" and Offshore North's Rhum milestone
(weekly shows; next Monday); Vancouver's Both Sides on one assessment
(the validator rule shipped Oct 12 after Ep020); Привет's English close
(next Monday).

## 2. Predictions scored (10-01, 10-05)

| metric | verdict | evidence |
|---|---|---|
| story_clusters_retold_in_digest 0 on ≥12 of 14 | partial | M&A 12/13, SpaceX 8/13, Tesla 2/12 |
| frame-memory banned openers ≤2/day | partial | no recurring prompt-seeded opener across both days; the counter is read on the 10-27 readout |
| items_without_source_shipped == lint | hit | equal on every episode |
| Apple ratings ≥14 by 11-01 | pending | 6 (from 4) |
| shows_unindexed → 0 | partial | 13 → 6 |
| stripped sentences + gate skips = 0 | hit | 0 and 0 since 10-02 |
| verified_later ≥40% | miss | 2 of 52 (3.8%) — same runners the publishers 403; the second egress is the decision |
| network verified share ≥85% | pending | read on 10-22 |
| UC ≥19 of 21 days | hit | 12 of 13 |
| Omni View overlap ≤20% at coverage ≥75% | hit | median 14.5% / 82% without fallback |
| date-probe share ≥55% | partial | 54.4% |
| FP newsletter_sent two Mondays | partial | 10-12 True (10-05 preceded the fix) |

## 3. Operator items

1. `wrangler deploy` in `workers/voices` (the tick gate) — nothing changes
   until then.
2. ⚠️ A/B-listen: Models & Agents (arXiv), one Omni View desk (the filtered
   script), MIT (Market Pulse), UC (the cross-promo line), Top World
   (first sentences).
3. Carried: the @planetterrian X app's 402; the Age of AI / DP Pod podcast
   playlists (landmine #15); directory submissions for the six unindexed
   feeds; a second egress for the nightly claims re-check.
