# Weekly network review — Nov 12 to 18, 2026

Operator-directed (Nov 19): review every show and workflow from the last week,
judge how each performed, and make the improvements. Builds on the Nov 10-14
per-show passes; this pass checks whether those moved their numbers and fixes
what is new. Register `weekly-review-2026-11-19`; guards
`tests/test_weekly_review_2026_11_19.py`.

## How the shows did (daily audit, `api/editorial_score_history.json`)

Mean score, the two weeks before Nov 12 against Nov 12-18.

| Show | Before | Week | Read |
|---|---|---|---|
| AI Chips | 6.8 | **7.6** | Up after the Nov 14 word ceiling (#1714) |
| MAG 7 | 6.4 | **7.4** | Up, same pass |
| Prediction Markets | 6.9 | 7.3 | Up |
| Fascinating Frontiers | 6.2 | **6.9** | Up after #1698/#1703/#1717; Repetitive 4/7 |
| Omni View | 5.8 | **6.7** | Up after grok-4.7 and the prompt rebuild (#1697/#1704/#1713) |
| Models & Agents | 6.6 | 7.0 | Up; Factual Errors 4/7 |
| Unintended Consequences | 7.2 | 7.0 | Flat; Repetitive 6/7, every quote the close |
| Vancouver | 6.8 | 6.9 | Flat |
| Planetterrian | 6.3 | 6.6 | Flat; see the fact-floor readout below |
| Top World | 6.5 | 6.6 | Flat |
| SpaceX | 6.2 | 6.4 | Flat; Off Topic 3/7, Incoherent 3/7 |
| Beginners | 6.3 | 6.4 | Flat; Repetitive 5/7 (the Nov 14 target is at most 5 of 14) |
| Modern Investing | 6.5 | 6.4 | Flat; Repetitive 5/7, expansion fired 7/7 |
| Tesla | 5.9 | 6.1 | Lowest daily; Repetitive 6/7; off-topic X posts |
| **First Principles** | 6.5 | **6.0** | Down; Repetitive 7/7; two arithmetic errors |
| Env Intel (weekly) | 5.5 | 5.0 | Repetitive; Nov 10 review open |
| **Offshore North (weekly)** | 6.0 | — | **Skipped Nov 16** |
| Weeklies (DP Pod 8, Longevity 8, Peptides 8, Privet 7, Collingwood 7, Finansy 6) | | | Steady |

Loudness: every episode this week measured −15.6 to −16.6 LUFS. The Nov 3
mastering fix holds. The back-catalogue re-master is still the operator's open
item.

## Workflows

- **Run Tests on main has been red since Nov 16 22:56 UTC** (1 of 17,794):
  `test_it_rebuilds_the_handoff_from_a_published_episode` read SpaceX Ep134's
  real summaries record, which rolled off the file. Fixed: the test builds its
  own digest and record.
- **Offshore North**: both Nov 16 runs skipped as `podcast_script_too_thin`.
  Cause and fix below.
- **Post queued X posts** failed every half hour through Nov 16 15:35 UTC (the
  @nerranetwork lock) and has been green since.
- **Restock Topic Queues** failed Nov 14: UC's restock produced 0 valid topics
  (every candidate's research returned no sources) with 4.7 weeks of runway.
  The Nov 15 and 16 restocks committed; nothing to fix this week.
- **Nerra Producer inbox**: 2 failures in ~170 runs (Google `unauthorized_client`
  token refresh), transient.
- Two `Run Podcast Show` finalize jobs cancelled on Nov 19: the concurrency
  group superseding an older finalize, as designed.
- The four members-only Omni View desks skip daily (`no_member_demand`) as
  designed; each writes a commit.
- Nine draft PRs are open: seven bot-opened show reviews (no CI: their runs sit
  at `action_required`) and two Dependabot bumps.

## What this pass fixed

1. **Offshore North read two days of a seven-day week.** Its fetch ladder
   opened at 48h and widens only when fewer than `min_articles` come back, but
   the campaign feeds carry their own 30-day windows and always supply that
   many. The Nov 2, 9 and 16 logs all stop at `cutoff=48h`: Vendée Globe (50
   entries), Google News IMOCA (51) and Scuttlebutt (40) passed none. Digests
   came out at 530 to 691 words every week and the expansion retry fired every
   week. On a quiet weekend the script reached 881, then 693 words against the
   950 floor, and the episode skipped. `fetch_expansion_hours` is now `[168]`;
   `stale_article_days: 10` still keeps old news out.
2. **No filter ever read X posts.** `engine.fetcher.fetch_x_posts` took
   `keywords` and never used it, although Tesla's YAML said "the keyword filter
   keeps his non-Tesla posts out". Tesla Ep666-669 put Starship catches,
   "Starship the Game" and a Crisco joke about catch-arm lubrication in the X
   Takeover (Ep669's 5/10 cites it four times); SpaceX Ep164 aired Musk on Hong
   Kong's birth rate. New per-account `on_topic_only: true` keeps only posts
   whose headline or text names a show keyword (the RSS filter's test). It is
   on for Tesla's commentators and Musk and SpaceX's Musk; the companies' own
   accounts are read whole.
3. **The narrative shows' lessons re-told the episode.** Every Repetitive
   quote on First Principles (7/7) and most on UC (6/7) is the close restating
   the body. FPD's script prompt asked for a 250-350-word lesson with two
   principles, about a quarter of a 1,200-word script. Now: FPD one principle
   in about 100-160 words, UC 100-160 (was 150-250), and on both shows the
   lesson adds what the episode has not said and never re-tells an event, a
   figure or a finding. FPD's arithmetic: a range is two sums (low ends, high
   ends) with both totals said, and any "N-fold" is the division of two numbers
   the brief states (Ep165 summed a 660 high end as "under 450"; Ep164 called
   an 8.6x gap "more than tenfold"). ⚠️ AUDIO: rehearsed before merge.
4. **Main is green again** (item above).

## Readouts of last week's work

- **Planetterrian fact floor** (`digest-fact-floor-2026-11-03`): the retry
  fires on 3 of the last 7 episodes against 7 of 7 before, but Repetitive went
  from 8 of 14 audits to 13 of 15 and the mean is flat. Padding was not the
  main cause; this week's quotes are within-item paraphrase. Recommendation:
  keep it on Planetterrian and do not extend it to Tesla yet.
- **Expansion retry still fires on nearly every episode** of Tesla (7/7),
  Modern Investing (7/7), Beginners (7/7), UC (7/7), FPD (6/7) and SpaceX
  (6/7), adding 30-100% to the digest. Given the readout above, lowering these
  word floors is the next lever to test, one show at a time.
- **Remaining-shows pass** (`remaining-shows-review-2026-11-14`, readout Nov
  28): SpaceX Incoherent 3 of 7 is on pace for its target; Beginners
  Repetitive 5 of 7 is not.
- **Fascinating Frontiers** and **Omni View** improved most; their readouts
  are Nov 27.

## Predictions (scored at the next weekly review)

- Offshore North publishes on Nov 23 with a pre-expansion digest over 900 words.
- No Tesla or SpaceX OFF_TOPIC flag quotes an X post in the next 14 audits.
- FPD Repetitive on at most 8 of the next 14 audits; mean at or above 6.5.

## For the operator

- Merge the dependency PRs only on a green Run Tests (#1723, #1724).
- The seven bot-opened show-review drafts need a merge, a close or a label.
- `docs/outstanding.md`: the back-catalogue re-master, Offshore North on Apple
  Podcasts, and the six unindexed feeds on Podcast Index are still open, and
  the latter two decide whether Offshore North has listeners at all.
