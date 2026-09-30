# Network review — freshness, repetition and reproducibility (Sep 30, 2026)

Operator brief: a comprehensive assessment of show quality and content
since the last changes, coupled with improvements to the workflow,
pipeline and codebase that make everything more efficient and
reproducible — shows that are more interesting, informative, timely and
not repetitive. Two things the operator heard: repetition, and stories
in the daily show that were news from months ago. The standard is a
news network people can trust and come back to daily.

Scope: every episode from Sep 16 to Sep 30 (254 scripts, 223 news
digests / 2,053 items across 28 shows), the metrics and claims sidecars
for the same window, the audience headline, every ledger in
`docs/reviews/ledger/` (638 predictions), the experiments register, the
CI history on main since Sep 26, and today's Actions logs. Four sweeps
ran mechanically (stale stories, repetition, the freshness code path,
the ledger meta-review); every example below was read raw before it was
cited.

## 0. The short version

**The operator is right on both counts, and both have one cause each.**

*Months-old stories.* Every path that could not date an article stamped
it with the run clock. Undated feed entries, every xAI web-search
result, every X post and every Google News item (whose feed date is the
INDEX date) arrived carrying today's date, sorted to the top of the
digest prompt, and printed `(2026-09-30)` beside a headline the prompt
then told the model was "FRESH (within last 48 hours)". The sweep found
seven such stories on the flagships in fourteen days — a 2013 Teslarati
page aired on Tesla three times (Aug 17, Sep 8, Sep 23), a May-2021
Mashable story and a January-2025 Starlink deal on SpaceX, a June
article read as September on Tesla — **every one behind an undated URL
whose page carried its real date**, and not one of the 691 URL-dated
items was stale, because the URL-path guard from the Sep 4 pass works.
The stale-article gate that reads page dates was on for the Sep-2026
cohort and off on every flagship. The tracker that should have stopped
the third airing of the 2013 page held its exact URL — under a 7-day
query window inside a 14-day file. And when the xAI search API failed,
the code re-sent the "search the web for the last 24 hours" prompt to
a model with NO tools and parsed its answer from memory as results.

*Repetition.* Exact repetition inside a script is absent network-wide
(`script_duplicate_sentences` is 0 on every episode). What the operator
hears is (a) SpaceX telling a story two or three times inside one
episode — combined generation writes PART 2 in the same call as PART 1,
so when the cross-section dedupe drops the digest's second copy of a
story, the script has already told it twice (`script_repeated_facts`
7–12 on Ep112–116 against 1–5 before; dupes removed a median 3 a day on
the show); and (b) sentence FRAMES that recur every day with a
different tail — "Before we go, keep an eye on…" (FF 15/15, PT 13/15),
"If you want to go deeper on X, compare how…" (Omni View 15/15), "The
case on both sides…" (every Mira desk 7/8). The ledger record on frames
is unambiguous: prompt-only de-seeds have missed three to five reviews
running per show; data-side rotation memory hits.

*Reproducibility.* Main has been red on every push since Sep 26 over a
test fixture (an interview transcript with no line over 200
characters), with four more data-driven guards red behind it; today
every one of 23 episodes shipped with **no transcript**, the spoken-text
gate blind on all of them, because PyAV 19.0.0 (PyPI, yesterday
evening) removed a keyword faster-whisper still passes and nothing
pinned it; and the daily health check has flagged Tesla "66% of target"
every day against a floor of 2,000 words the pipeline never used
(tesla.yaml enforces 1,400).

What shipped is in §5; the A/B-listen list in §6; what is deliberately
left for the operator in §7.

## 1. The state of the network, Sep 16–30

| measure | reading |
|---|---|
| RSS downloads, last complete week vs the week before | 1,621 vs 1,360 (+19.2%); 6,565 / 30 d |
| carrying shows (median first-week downloads) | SpaceX 88, Tesla 27, M&A 22; everything else ≤ 8 |
| newsletter subscribers | 11 |
| YouTube 28-d views-weighted AVP | Shorts 66.5, long 14.9 (105,918 views, 982 videos) |
| runs | every scheduled run completed; UC skipped by its own claims gate on 4 of the last 7 days |
| combined generation | `combined` on 120 of 244 news episodes (49%); the flagships 9–11 of 14 |
| scripts vs target (median) | FF 0.70, PT 0.70, SpaceX 0.80, Tesla 0.90, M&A 0.80, MIT 0.80, cohort 0.7–0.9 |
| digest-verbatim share, combined episodes | grok-4.3 shows 49–78% (FF 62, PT 69, Tesla 54, SpaceX 49); grok-4.7 cohort 4–17% |
| story recurrence annotations | Tesla 3, SpaceX 3.5 already-covered stories per digest; SpaceX Ep116: 28 of 43 fetched articles already covered |
| claims verified | flagships 0–3 per episode; grok-4.7 cohort 13–19; 83 of 244 episodes record 0 claims |
| strip mode | 75/75 stripped episodes passed; median 1 sentence; 0 news-show blocks |

Two readings that decide the next model question: **the grok-4.7 cohort
writes and the grok-4.3 flagships copy.** On the same combined path,
the same shared prompt snippet and the same instruction, the 4.7 shows
carry 4–17% of the digest's eight-word phrases verbatim with 13–19
verified claims; the 4.3 shows carry 49–78% with 0–3. The Sep 5–12
passes moved the tension between "written" and "complete" through three
gates and a redesign and never closed it; the model does. That is a
playbook-governed migration question (latency gate first — the cohort's
4.7 digest stages FAIL the gate today, p95 747 s on AI Chips, 870 s on
Prediction Markets, on prompts the flagships' digests would exceed),
not a prompt question, and it is the first item in §7.

## 2. Findings

### P0 — listener-facing, shipping this week

**P0-1. Old stories aired as today's news.** Verified rows from the
sweep (every URL undated; page date read from the page's own meta /
JSON-LD):

| days old | show | file | story | page date |
|---|---|---|---|---|
| 4,767 | Tesla | `Tesla_Shorts_Time_Pod_Ep614_20260923.md:57` (also Ep599 L15, Ep575 L45 — same URL, three airings) | Portable Solar Powered EV Charging Stations (Teslarati) | 2013-09-04 |
| 1,968 | SpaceX | `SpaceX_Daily_Ep114_20260928.md:31` | "Falcon 9 reused for 10th time… during a recent Starlink mission" (Mashable) | 2021-05-09 |
| 626 | SpaceX | `SpaceX_Daily_Ep110_20260924.md:9` (Top News #2) | $1.6B Starlink deal with the Italian government (Teslarati) | 2025-01-06 |
| ~665 | Tesla | `Tesla_Shorts_Time_Pod_Ep613_20260922.md:51` | Morgan Stanley reiterates optimism on Tesla solar (Stocktwits) | 2024-11-27 |
| 182 / 123 | Prediction Markets | `Prediction_Markets_Ep006_20260928.md:19` / `:16` | Kalshi margin clearance; Polymarket KYC | 2026-03-30 / 2026-05-28 |
| 95 | Tesla | `Tesla_Shorts_Time_Pod_Ep620_20260929.md:37` (also Ep595 L48, same URL) | "NIO Stock Eyes June Delivery Test" — aired Sep 29 | 2026-06-26 |
| 53 | Planetterrian | `Planetterrian_Daily_Ep195_20260926.md:7` (lead) | Polygenic breast-cancer score (Nature) | 2026-08-04 |

The mechanism, with the lines (audit doc in the session scratchpad,
all read):

- `engine/fetcher.py` stamped an undated feed entry with the run clock
  (`published_time … else now`), and `tests/test_fetcher.py::
  test_no_date_uses_current_time` pinned it as intended. The prompt
  listing sorts newest-first (`run_show.py` `articles.sort(
  key=published_date)`), so the stamped items led.
- Google News feed dates are index dates; after resolution only the
  URL-path regex checked the publisher URL; an undated permalink
  (Teslarati, Mashable, Stocktwits, CoinMarketCap) passed.
- `fetch_web_search_articles` had no date field in its format and
  stamped every result `now`; `digests/xai_grok.py` fell back to Chat
  Completions with NO tools when the Responses API failed — the same
  "last 24 hours" prompt answered from training data, parsed as
  results. It fired whenever the on-topic count fell under
  `min_articles` (Tesla 10, SpaceX 8): thin days, exactly when a stale
  story has room to lead.
- X posts were stamped `now`; the `POST_LINK` article inherited it.
- `stale_article_days` (the only page-date gate) was 0 on every
  flagship; even where on, it had a page date only for the ≤ N
  full-text-fetched articles.
- The content tracker's URL-dedup window was a fixed 7 days inside a
  14-day file (`content_tracker.py` `url_window = max(day_window, 7)`);
  X posts and web-search results never met the tracker at all.

**P0-2. A story told twice or three times in one SpaceX episode.**
`SpaceX_Daily_Ep116_20260930_tts.txt:15` "Space X told NASA it has no
current interest in developing Starship for crewed low Earth orbit
launches" → `:99` "One thing worth watching is that Space X has told
NASA it has no current interest…" (also Ep107 L29↔L49, Ep109 L67↔L105,
Ep114 L27↔L53). Ep112 tells the GB300 three-waves story at L33 (Top
News), L67 (Deep Dive) and L87 (teaser). Cause: combined generation
writes the script from the UN-deduped PART 1; `_dedupe_digest_sections`
then drops the digest's later copy and the stashed script keeps both
tellings. The Sep 18 review deferred exactly this ("strip_script_sentences
would also remove the FIRST telling").

**P0-3. Every episode today shipped with no transcript.** 23 of 23
metrics files for 2026-09-30 record `spoken_text_gate: no_transcript`;
0 `*_transcript.json` files exist for the day against 19–25 on each
prior day. Root cause from the Actions logs: `av-19.0.0` in every
"Successfully installed" line today against `av-18.1.0` yesterday;
faster-whisper 1.2.1 calls `av.open(…, metadata_errors="ignore")` and
PyAV 19 removed the keyword. `engine/transcripts.py` read the
`TypeError` as "VAD unavailable", retried without VAD, failed
identically and returned `None`. Consequences: the spoken-text gate
(landmine #25's only defence) ran blind on the whole slate; Shorts went
out without captions; the caption track was not uploaded; Nerra Daily's
promo cut had no word timestamps. Published audio is unaffected. Not an
HF hiccup — the model cache hit on every run.

**P0-4. UC skipped by its own claims gate on 4 of the last 7 days**
(10 skips in September, all `verified=0`). A daily narrative show that
publishes three days in seven is not daily; the block-mode gate plus a
ledger the model leaves empty is the shape the Sep 5 note described.
Not fixed here (it needs a prompt-side look at UC's claims appendix and
the repair pass on empty ledgers); operator item §7.

### P1 — quality ceiling

**P1-1. Frames.** Sentence openers recurring with different tails,
measured on the `_tts.txt` scripts (transcripts agree): "(Before we
go,) keep an eye on…" FF 15/15, PT 13/15; "Before we wrap, watch for…"
MIT 11/15; "Before we go" opens the teaser on 15/15 Tesla / SpaceX /
M&A, 8/8 mag7 and Prediction Markets, 9/9 AI Chips; "If you want to go
deeper on X, compare how A and B are covering…" Omni View 15/15; "To
really understand how…" 13/15; "The case on both sides…" 7/8 on each of
the five desks, 6/8 Top World, 8/8 Vancouver; "A sign of progress…" 7/8
Europe (including "There is not a sign of progress to enter today", Ep3
L73); "You know that feeling when…" MAB 7/15; "Tesla has not issued a
public response on…" 6/15. The content repeats in only 1/15 Tesla and
1/8 mag7 cases; the frame repeats. `review_snapshot.py` reported "no
repeated phrases" on the flagships because it runs on Whisper
transcripts, whose punctuation splits the frames.

**P1-2. The X-post "credit the linked article" fix never ran in
production.** `fetch_x_posts` → `_parse_x_posts_multi` →
`_parse_structured_blocks`, which ignores `POST_LINK`; the Sep 23 logic
lives in `_parse_x_posts`, called only by a test. So no post was ever
`x_linked`: every `linked_only` desk dropped 100% of its posts
(`x_posts_dropped_unlinked` 4–8 = all of them) and the six-outlets-
credited-to-x.com defect the fix was written for stayed.

**P1-3. Scripts run 20–30% under target on the grok-4.3 flagships**
(table in §1); the 09-17 prediction of ≥ 85% of target is a MISS (FF
0.70, PT 0.70, SpaceX 0.80, M&A 0.80). Digest-ceiling class, and the §1
model reading says which lever is left.

**P1-4. Tesla Ep617 shipped 17 of 17 items with no Source line** while
the run recorded `digest_lints_fired: []` and the replay test on main
has been red on it since Sep 26. The lint ran on the raw digest; the
committed file has none. Not resolved in this pass — it needs the run's
own text, which the metrics do not keep; §7.

**P1-5. The Tesla price line repeats verbatim on Fri/Sat/Sun** ("T S L A
closed at three hundred seventy-two dollars and eleven cents" Ep617–619,
same shape on two earlier weekends): correct, and heard three times.
Prompt-side wording ("unchanged since Friday's close"); §7.

### P2 — instruments and process

**P2-1. Main red since Sep 26 on a fixture, not a defect.**
`tests/test_episode_card_transcript_2026_09_22.py` demanded a > 200-
character line in the newest interview transcript; Ep009 (Sep 26) had
none. Behind it on the same tree: `test_first_slate` (Ep617, P1-4),
`test_video_feed_metadata` (today's episodes have no transcript yet on a
fresh checkout — and none at all today, P0-3), `test_transcript_brand`
("NaraDaily" / "NARA" Whisper tokens in two Sep 27 word arrays),
`test_launch_cohort_formats::test_curriculum_restocked` (pinned the
stock the restock LEFT, 41, on a show that drains one a day — 34 now),
`test_show_page_episode_links::test_the_rss_fallback_cards_get_it_too`.
A guard that reads today's committed data will be red on any day the
data moves; the rule is in §8.

**P2-2. `scripts/grok_show_check.py` hard-coded word floors** (Tesla
2,000 vs the YAML's 1,400; the six desks 900 vs 1,300) — the daily
health file has flagged Tesla "significantly short, 66% of target"
every day; `review_episodes.py` fixed the same class in June by reading
the YAML first.

**P2-3. Eleven experiments past readout; scored in §4.** `overdue_count`
on the dashboard excludes same-day readouts (says 7).

**P2-4. `docs/reviews/ledger/vancouver.yaml` was not valid YAML** (an
unquoted `: ` inside a verdict scalar) — the next append would have
corrupted it.

## 3. Scoring the previous network entries

| entry | metric | verdict | evidence |
|---|---|---|---|
| 09-17 | combined on ≥ 70% of the five flagships' episodes, 0 lost | partial (already scored 09-22) | 49% network-wide over 09-17..30; flagships 9–11 of 14; 0 lost |
| 09-17 | script words ≥ 85% of target on the five flagships, 0 thin skips | **miss** | medians FF 0.70, PT 0.70, SpaceX 0.80, M&A 0.80, MIT 0.80, Tesla 0.90; PT skipped 09-17 |
| 09-17 | PT stripped ≤ 2/5 days; ≥ 1 claim/day verified from the fetched copy | partial | PT stripped 7/14 days (1–2 sentences), `verified_from_fetched` median 1 on PT, 0 on SpaceX/Tesla |
| 09-17 | chapters ≥ 6 on 4/5 combined episodes, PT and MIT | partial | PT 9–13 on 11/14 (three 4-chapter days remain); MIT 4–5 on 14/14 — its section set is the digest's, not the bridge's |
| 09-17 | restock workflow succeeds; UC ≥ 4.0 wk, FPD ≥ 3.0 wk | hit | 14 consecutive successes 09-17..29; both queues above floor |
| 09-17 | main-branch tests green on the merge and 7 days after | **miss** | green 09-18..25, red every push 09-26..28 (fixture) |
| 09-18 | combined_stale only on regeneration days, ≤ 1 of 5 per day | hit | 5 `combined_stale` in 70 flagship episodes, each on a logged retry |
| 09-18 | stripped sentences where the source resolved: repair recovers | partial | resolved-source strips: Tesla 2/2 recovered, FF 2/3, PT 1/6, desks 0/14 |
| 09-22 | EN hook-Short age-3 median ≥ 15 by 10-06 | pending (due 10-06) | — |
| 09-22 | EN Shorts uploads ≤ 12/day | pending (due 10-06) | — |

## 4. Experiments past readout (register updated)

| id | reading | status |
|---|---|---|
| nerra-daily-edition-titles | `edition_title_source=llm` 14/14; OP3 per edition 3–4 downloads_7d, inside the 2–5 baseline | done — mechanism HIT, reach flat (distribution gate, as the criteria said) |
| grok-47-staged-migration | omni_view script stage GATE PASS (p95 67.6 s, 9/9 on 4.7, LV 7.4–8.9); the COHORT's 4.7 DIGEST stages fail the gate (AI Chips p95 747 s, Prediction Markets 870 s) | reading — widen only on script stages; digest stages wait on latency |
| dp-pod-youtube-shorts | short_vpd 1.81; dead-Shorts weekly probe since 09-26 (d3 median 6.5); OP3 8–12/wk vs ~27, confounded by the weekly move; 0 funnel sessions | done — MISS; keep/pause is the operator's call |
| grok-46-wave2-scripts | OV left the arm 09-22 (4.7); MAB 0.38 flags/ep at or below same-window 4.3 peers; 0 missed slots | done — keep the MAB pin |
| network-content-discipline-2026-09 | overlap medians SpaceX 47 / Tesla 51 / M&A 38 (target ≤ 25: MISS); filler 1.5–3.4 (HIT); dupes still firing (SpaceX) | done — PARTIAL; superseded by the model reading in §1 |
| combined-generation-2026-09-12 | combined 49% (target 80%: MISS); overlap ≤ 25 AND coverage ≥ 70 on the same episode: Tesla 2/19, SpaceX 0/19, M&A 3/19 (MISS); entity retention 73/80/67 (PARTIAL); 0 lost (HIT) | reading — the second-telling strip ships today; re-read 10-14 |
| source-integrity-strip-network-2026-09-12 | passed_after_strip 75/75; 0 skips; median strip 1 | done — HIT on criteria; 83/244 episodes with an empty ledger is the open item |
| shorts-subscribe-cta | 1.99 per 1,000 views vs target 2.0 (baseline 1.51) | done — HIT within noise |
| fresh-open-long-form | 0.48 = baseline (target 0.52) | done — MISS |
| long-form-fact-cards | treatment 16.6 vs control 12.5 post-09-10 against a pre-period gap of +5.4 → diff-in-diff −1.3 | done — NO EFFECT |
| pause-dead-youtube-uploads | 0 uploads from the paused shows; EN weekly views 19.4k→8.8k→10.0k across the 09-13/16 distribution drop | done — INCONCLUSIVE, confound named |

## 5. What shipped (code-only unless marked ⚠️)

**Freshness — one owner for an article's date.**
- `engine/article_dates.py` (new): `date_source` on every article
  (`feed` / `index` / `url_path` / `page` trusted-or-not), `""` for an
  unknown date (sorts LAST under every existing newest-first sort and
  renders no date), `probe_page_dates` (opens up to `date_probe_max`
  pages — default 12, YAML-tunable, 0 = off — for the articles nothing
  trustworthy dated and reads the publisher's own date; the page date
  then replaces the index date / the model's claim, so the stale gate and
  the prompt's order both tell the truth).
- `engine/fetcher.py`: undated feed entries are undated, not `now`;
  Google News items are marked `index`; web-search results carry an
  `ARTICLE_DATE` the model reports (`model`) or none, and a result the
  model itself dates outside the window is dropped; X posts carry
  `POST_DATE` or none; `_x_post_entry` is the ONE builder both X parsers
  use, so the live path credits a linked article (P1-2) and a linked
  article whose URL path dates it outside the window is not promoted.
- `digests/xai_grok.py`: a search request that fails raises
  `SearchUnavailable` — never an answer from memory. Every search caller
  already catches it.
- `run_show.py`: the page-date probe runs before the stale gate, after
  the full-text fetch (metrics `articles_date_probe_candidates` /
  `_probed` / `_probe_dated`, `articles_undated_in_prompt`,
  `articles_date_source_untrusted`); X posts and web-search results now
  pass `content_tracker.filter_recent_articles` like the RSS ladder;
  `content_tracking.max_days` is passed to the tracker (it never was).
- `engine/content_tracker.py`: the URL-dedup window is the retention;
  `_defaults.yaml` retention 14 → 45 days (story-recurrence annotations
  read the same window — ⚠️ prompt input).
- ⚠️ `stale_article_days: 3` on the twelve established news shows
  (tesla, spacex, models_agents, MAB, FF, planetterrian, omni_view,
  env_intel, modern_investing, finansy_prosto, mag7, ai_chips) — the
  digest INPUT changes; A/B-listen the first post-merge episode.

**Repetition.**
- `engine/digest_overlap.py`: `DuplicateItem.body` + `strip_second_tellings`
  (keeps the first script telling of a dropped duplicate, removes the
  later ones; sentences under eight words never judged);
  `engine/generator.py` `peek_combined_script` / `amend_combined_script`;
  `run_show._dedupe_digest_sections` amends the stash (metric
  `combined_script_second_tellings_removed`).
- ⚠️ `engine/frame_memory.py` (new): data-side rotation memory for
  sentence frames — the show's last six scripts are mined for openers
  that recur with different tails (furniture that recurs verbatim and
  chapter-anchor phrases are exempt; an opener carrying a proper noun,
  a digit or a spelled ticker is content, never a frame) and the podcast
  prompt gets a do-not-open-with list through `{recent_frames_block}` in
  `_shared/content_discipline.txt` and `_shared/omni_desk_podcast_body.txt`.
  Opt-in `frame_memory: true` on 17 shows (the news flagships, the six
  desks, Vancouver, mag7, AI Chips, Prediction Markets); MIT stays off
  (its list was its ledger-supplied lines). It names what was used and
  never supplies the replacement. A/B-listen the first episode.

**Reproducibility.**
- `requirements.txt`: `av>=11,<19`. `engine/transcripts.py`: only a
  VAD-shaped error earns the VAD-less retry; a transcription failure is
  a `::error::` annotation naming the episode.
- `scripts/grok_show_check.py`: the word floor is the YAML's
  `min_podcast_words` (table as fallback).
- Guards re-pinned to what they mean: the interview-transcript fixture
  takes the longest line (≥ 60 chars); the video-feed metadata test
  judges episodes at least a day old; the curriculum floor is a
  three-week runway alarm (21), not the stock the restock left.
- `docs/reviews/ledger/vancouver.yaml` quoted; 11 experiments scored;
  three new register entries.

Drift guards: `tests/test_freshness_pass_2026_09_30.py` (48),
`tests/test_repetition_pass_2026_09_30.py`; `tests/test_fetcher.py`,
`tests/test_content_tracker.py`, `tests/test_offshore_north_round1_2026_09_18.py`
re-pinned to the new contract.

## 6. ⚠️ A/B-listen required (landmine #17)

Nothing here changes a prompt's wording, but three changes alter the
context the model writes from, and that is the same gate:

1. `stale_article_days: 3` + the page-date probe on the twelve
   established news shows — the article list the digest is written from
   loses re-surfaced old stories and gains nothing; a thin day may be
   thinner and more honest.
2. Tracker retention 45 days — more `[ALREADY-COVERED NOTE]` annotations
   in the digest prompt on the story-recurrence shows.
3. Frame memory on 17 shows — a ROTATION MEMORY block in the podcast
   prompt naming the openers to avoid today.

`GROK_API_KEY` is not set in this session, so no digest was regenerated
to show before/after output; the first post-merge episode of each show
is the listen set.

## 7. Operator decisions and deferred items

1. **The model question, by the playbook.** The grok-4.7 cohort writes
   (4–17% verbatim, 13–19 claims) where the 4.3 flagships copy (49–78%,
   0–3). Three passes of prompt and gate work did not move that; the
   model did. Run `model_trial_report` on a script-stage-only pin for one
   flagship (SpaceX, the largest, which is already chained) with the
   latency gate — the cohort's 4.7 DIGEST stages fail it today, so the
   digest stays on 4.3.
2. **UC skips 4 of 7 days on its own gate** (P0-4): decide between
   `on_failure: strip` for UC (the network default) and a claims-appendix
   pass that makes its empty ledger fire the repair; the deferral logic
   is working as designed, the show is not.
3. **Tesla Ep617's lint blindness** (P1-4) and the `test_first_slate`
   replay — a follow-up session with a run trace.
4. **The Tesla weekend price line** (P1-5) — prompt/hook wording, A/B.
5. **Frame memory on Modern Investing** once the memory can see the
   prompt context (its ledger lines dominated the list).
6. **`test_transcript_brand` / `test_show_page_episode_links`** — two
   remaining data-driven reds on main, both outside this pass's scope
   (a Whisper spelling the normalizer does not know; a page with one
   article card).
7. **A dependency lockfile for the runner.** PyAV was the second
   transitive bump to take a stage down in a fortnight (grok-4.7's
   streaming was the first class); `pip-compile` constraints on the
   run-show job would make a runner day reproducible.
8. **Nerra Daily Ep041 and today's 23 episodes** have no transcript, no
   captions and no caption track; the Re-synthesize workflow does not
   apply (the audio is fine). A transcript backfill for 09-30 is a
   one-line script over the R2 audio if the operator wants the feeds'
   `<podcast:transcript>` entries.

## 8. Meta-review — what the ledgers say the playbook should change

Across 638 predictions (291 scored): hit 47%, miss 35%. By category:
MIT record integrity 73% hit, chapters/metadata 61%, garble 50%,
tic/de-seed 49% (but 90 of them, and the misses are the same phrase
families three to five reviews running), sourcing/claims 42%,
fetch-filter 36%, length 36% hit / 44% miss, **script density and
coverage thresholds 0% hit / 86% miss** (12 of 14). Podcast-side length
levers still re-enter under new metric names (22 misses). Thirteen
ledgers (the launch cohort and Age of AI) have no scored row.

Three rules added to the playbook:

- **A script-density threshold is not a prediction.** Overlap and
  coverage moved with the MODEL, not with any prompt or gate; a review
  predicts the data-side change it ships (a dropped duplicate, a banned
  opener), never a percentage the script stage will reach.
- **A prompt-only de-seed of a family already missed twice is an
  operator-decision item**, never a third filing; the data-side rotation
  memory is the fix class that ships.
- **A guard that reads today's committed data must tolerate today.** A
  test that asserts on the newest episode's shape, the current stock of a
  queue, or a file the day's runs have not committed yet is red on the
  days nothing is wrong; judge episodes at least a day old, floors as
  runways, fixtures on what they mean.
