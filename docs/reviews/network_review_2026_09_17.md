# Network review — first slate after the simplification pass (Sep 17, 2026)

Operator brief: review the first combined-generation slate and confirm it
shipped cleanly; then a full review of the network — how the changes are
working out and what else is needed.

Scope: every episode from Sep 13 to Sep 17 (62 metrics files, 15 shows),
the 100 `run-show.yml` runs in that window, the claims sidecars, the
daily show-health file, the audience headline, and the two skip markers.

## 1. Did the first slate ship cleanly?

**The pipeline did. The design did not reach the shows it was built for.**

| check | result |
|---|---|
| run-show.yml runs Sep 13–17 | 100 of 100 succeeded |
| episodes lost to the combined path | 0 |
| leaked PART-1/PART-2 placeholder text in any digest or script | 0 files |
| `combined_generation = combined` | 5 episodes: M&A Sep 14/16/17, env_intel Sep 14, Offshore North Sep 14 |
| `combined_generation = two_pass` | 51 episodes |
| combined attempted, PART 2 under the band, fell back | 1 (M&A Sep 13, 852 words on a 990 band) |
| skips | UC Sep 15 (narrative gate block, block mode by design); Planetterrian Sep 17 (`podcast_script_too_thin`, 858 words) |

Why only five: `combined_generation_enabled` excluded any show with
`podcast_chain: true` — and that is Tesla, SpaceX, FF, PT, MIT, FPD and
UC. Combined with the grok-4.6 script-stage shows (OV, MAB, dp_pod) and
the two Russian shows, "one generation" was live on Models & Agents plus
the two Monday shows. The Sep 13 YouTube readout had already flagged this
and left it to the operator; this review makes the call: **the chain no
longer excludes a show.** The chain's outline call exists to give the
script a structure; in a combined call, PART 1 is that structure. The
chain still runs on the fallback script call, so nothing is lost when a
PART 2 comes back short.

What the five combined episodes look like (M&A Ep173/175/176):

| episode | overlap | coverage | names kept | words |
|---|---|---|---|---|
| M&A 173 (combined) | 46.0 | 83.6 | 60.0 | 1,433 |
| M&A 175 (combined) | 59.0 | 74.3 | 49.4 | 1,183 |
| M&A 176 (combined) | 38.4 | 72.2 | 66.4 | 1,132 |
| M&A 172/174 (two-pass, same week) | 30.5 / 25.5 | 79.6 / 70.7 | 78.8 / 63.2 | 1,140 / 1,070 |

Coverage holds at 72–84 % (the two-pass rewrites had fallen to 40–60 %),
but the PART 2 is largely PART 1 with the markdown removed — 38–59 %
of its eight-word phrases are verbatim. The bridge now says so in one
sentence ("PART 2 is not PART 1 with the markdown removed…", A/B-listen)
and asks the script to name each section once as it enters it (see §4).

## 2. The rest of the network, Sep 13–17

**Scripts on the chained flagships copy the digest again.** With the
gate gone and the chain still in place: Tesla 51–66 % verbatim, PT
66–74 %, SpaceX 42–61 %, FF 37–64 %; coverage 39–86 %. Not a regression
against the two-pass copied drafts of Sep 5 — it is the two-pass copied
draft. The fix is §1, not a retry.

**Episodes run short across the network.** The Sep 16 health file flags
eight of eleven shows under target: Tesla 56 %, FF 72 %, SpaceX 75 %, PT
76 %, M&A 80 %, MIT 84 %, UC and FPD a few words under their floors.
Planetterrian Sep 17 was skipped at 858 words after the expansion retry
(810 → 922) and a re-roll (660) both missed the 960 floor. The digest
was normal (12,102 chars, validation passed, 6 claims); the script stage
wrote 810 words from it. This is the digest-ceiling class the July
ledger closed on — and the combined path is the first lever that changes
the shape of the script call rather than pushing on it. Read
`script_words` per show over the next week under combined generation
before anything else is tried.

**Strip mode is doing exactly what it says, on true sentences.**
Stripped episodes: PT 5/5 days (1–2 sentences each), OV 4/5, FF 3/5,
MIT 2/5, M&A 2/5, dp_pod 2/5, Tesla 1/5, SpaceX 1/5. Every stripped
episode passed after the strip; no news show was blocked by the gate.
What left was never a fabrication: PT Sep 17 lost "Japan now has 100,000
people aged 100 or older" (David Sinclair's X post — x.com cannot be
fetched by requests), "Researchers built the first DNA-based computer
capable of performing computations" (publisher 403) and a cellphone-GPS
health-model finding (same). **The fetch stage already held the
evidence for two of the three** — the X post's text and the feed body
are in the article list the digest was written from. Now the gate
verifies a claim against that fetched copy FIRST (`build_local_texts`,
`verify_claim_sources(local_texts=)`, `via: fetched_copy`,
metric `source_integrity_verified_from_fetched`); only a quote the copy
does not carry goes to HTTP, and fails as before. The contract is
unchanged: nothing ships without evidence; the evidence can be the copy
we fetched ourselves.

**The committed sidecar was silent about the strip.** Every PT sidecar
for Sep 14–17 reads `claims=0, passed=true` — it is the post-strip
ledger. The `GateResult` now records `stripped_sentences`,
`stripped_notes`, `removed_items` and `covered_by_item_source`, and
`save_ledger` writes them, so a review can read what left without the
Actions log.

**Chapters.** Planetterrian has parsed exactly four chapters (Intro,
Science Deep Dive, Teaser, Closing) on 12 of its last 15 episodes since
Ep172; MIT four on 13 of 16; the Sep 16 health file flags missing
section markers on Tesla, M&A, MAB and MIT. The scripts stopped speaking
their section names when the Sep 5 content-discipline rule dropped
transitions that "carry no information", and the digest-headline
fallback is not catching PT's paraphrased items. The bridge line above
(name each section once as you enter it) is the combined-path fix;
whether the two-pass shows need the same line in
`content_discipline.txt` is a readout question for Sep 24 — count
chapters per episode.

**Tesla Ep605 (Sep 14) aired 45 seconds of the TTS normalizer's own
reasoning.** Handled the same day by another session (spoken-text gate,
`docs/reviews/tesla_ep605_spoken_text_gate_2026_09_14.md`); nothing to
add here except that the gate is now the thing standing between the
engine and the listener, and it is on.

**Audience headline (as of Sep 16).** Network 1,430 downloads in 7 days;
last complete week 1,352 against 1,588 (−14.9 %). SpaceX −29.6 % (825 →
581 — the week before was its spike), M&A +32.1 %, Tesla −5.2 %, FF
−26.8 %, MAB +84.2 %. First-week downloads per episode: SpaceX 69, Tesla
27, M&A 20. YouTube retention (views-weighted, 28 d): Shorts 75.3 %,
long-form 15.4 %. Newsletter 5. The Sep 12 YouTube review's rule
applies: compare at a fixed age, not against a peak week; the flagship
softening is real but modest, and the September prompt passes cannot be
scored on four days.

## 3. Sep 12 predictions, scored

| prediction | verdict | evidence |
|---|---|---|
| combined on ≥ 80 % of news-show episodes, 0 lost | **miss** (0 lost, 5/56 combined) | chain exclusion; fixed here |
| overlap ≤ 25 % with coverage ≥ 70 % on 8/10 flagship episodes | **miss** | flagships two-pass at 42–74 % overlap; combined M&A 38–59 % |
| 0 news-show claims skips; passed_after_strip ≥ 95 %; median strip ≤ 2 | **hit** | 0 skips; 20/20 stripped episodes passed; median 1 sentence |
| audience headline read in every review | **hit** | this one and the Sep 13 readout open on it |

## 4. Shipped in this pass

- `engine.generator.combined_generation_enabled` no longer excludes
  `podcast_chain` shows (guard `TestChainedShowsAreEligible`).
- PART-2 bridge: "not PART 1 with the markdown removed"; name each
  section once (A/B-listen — the first flagship combined slate).
- `engine.claims.build_local_texts` / `normalize_source_url`;
  `verify_claim_sources(local_texts=)` passes a quote found in the
  fetched copy without HTTP; threaded through the gate, the repair pass
  and the strip re-gate; metric `source_integrity_verified_from_fetched`.
- `GateResult` carries the strip record into the committed sidecar.
- Ledger predictions scored; new predictions filed; register notes.

## 5. Not changed, and why

- The grok-4.6 script-stage shows (OV, MAB, dp_pod) stay two-pass: a
  combined call would move their script to grok-4.3 and end an A/B in
  flight. OV Sep 15/16 coverage 44.8 % and dp_pod Sep 17 29.6 % are that
  trial's readout, not this pass's.
- No length lever. The under-target episodes are the digest-ceiling
  class; the combined path changes the call shape, and its first
  flagship week is the measurement.
- The chapter-marker fallback for two-pass shows is a readout question,
  not a Sep 17 change.

## 6. Same-day follow-up — main was red, and the restock never worked

The PR carrying §4 was merged one minute after its CI failed, and the
failure was not this pass's: the `Run Tests` workflow had been red on
every push to main since Sep 16 (eleven runs), so no merge this week
was checked. Fourteen tests failed on the merged tree:

Two sessions diagnosed the same fourteen failures in parallel on Sep
17; the fixes that reached `main` first (commits `bbad1692`,
`98fc7127`, `735d8400`) are the ones the network runs, and this
section describes those. This PR carries only what they did not: the
three hand-written UC briefs, the ledger predictions, the register
correction, and this write-up.

| failure | class | fix on `main` |
|---|---|---|
| `test_captions … test_real_transcript_cues_fit_the_frame` | data-driven: SpaceX Ep103 closes a sentence in a 0.34 s segment ("comments.") and the 0.4 s flicker filter dropped the word from the burned-in captions | a short segment is HELD on screen to the 0.4 s minimum (short of the next segment) instead of skipped; `artifact_floor_seconds` 0.15 s still drops textless blips |
| `test_daily_edition … test_every_recent_lineup_transcript_hits_a_frame` | data-driven: MIT Ep171 shipped frame 2 without its sibling sentence (text-side); DP Pod Ep069's plug is in the audio but Whisper transcribed nothing for 22 s of it (a local re-run hears it) | the scripted YouTube call-out is a frame-grade anchor when the outro follows it (`anchor: youtube_lead`, 60 s ceiling); "then" for "than"; edition metrics record `cut_anchor` |
| `TestNarrativeQueueRunway[unintended_consequences]` 3.7 wk | the alarm working: the Restock Topic Queues workflow failed nine days running (Sep 8–16) | see below |
| 7 Voices / co-host assertions (`test_producer_autonomy`, `test_review_gates`, `test_the_open_and_the_sound`, `test_transcript_brand`, `test_cohost_scenario`, `test_nerra_voices_pipeline` ×2) | code moved on deliberately in the Sep 15–17 commits (path-token review links, every host leg kept, kwargs-driven transcribe call, room notes that never force a response) without the tests; two were real: Mira's system prompt quoted The Age of AI's closing question verbatim as a war story (a seed, and a leak into Nerra Voices' prompt), and `assemble_edit.py` hard-coded the show | assertions pin the new behaviour; the prompt describes the shape ("the closing question he had already been asked went out three times…") — A/B-listen, it is the live host's prompt; the show comes from the EDL |
| 4 `test_cohost_pipeline::TestTrackSelection` | `align_to_room` shelled out to ffmpeg for real inside a unit test | `align_to_room` is faked in the test |

**The restock automation had never produced a topic on grok-4.6.** The
call was pinned to 4.6 on Aug 19 ("no latency pressure here"). Every
run since that actually needed topics — the first was Sep 8 — failed:
"no JSON array found in model output" on one night, "Server
disconnected without sending a response" (the failure the Aug 18
network-wide 4.6 revert documented) on the rest, on a prompt that
carries the show's entire queue history. The one-minute "successes"
between Aug 19 and Sep 7 were runs that needed nothing. The runway
guard is what caught it, as the July 24 design said it would. On
`main`, `generate_candidates` keeps grok-4.6 as the primary and
retries one failed call on grok-4.3 (`FALLBACK_RESTOCK_MODEL`,
`TestModelFallback`), recording `model` in the run summary. Read that
field: the primary's record on a needed restock is 0 for 9, so if
`model` reads grok-4.3 on every night that restocks, the 4.6 call is a
five-minute failed request paid before each one and the primary should
follow the FPD/UC arms off 4.6 (the register entry is corrected below).
**15:29 UTC dispatch (run 58), read after the merge:** grok-4.6 timed
out at 300 s on both shows (`APITimeoutError`) and grok-4.3 answered
each in under a minute — 0 for 11 for the primary — so the workflow
now sets `NERRA_RESTOCK_MODEL: grok-4.3` through the documented
override. The same run then failed in its own validator AFTER the
model had answered and First Principles had been refilled 4.0 → 8.0
weeks: `resequence_unproduced` interleaved UC's three gate-deferred
head entries while the runway guard measures the pickable sequence
without them, so two pickable policy entries either side of a parked
one read as adjacent ("clustered head: classic, policy, policy") and
nothing was committed. Deferred entries now stay in place and only
pickable entries are interleaved (`TestResequenceSkipsDeferred`; 200
simulated restocks against the live queue clear the guard). Also from
that run: of 30 candidates the model returned for UC, 28 were rejected
as duplicates of the queue's own history that the prompt already lists
— the restock prompt's dedupe instruction is not holding on grok-4.3
either, and that is the next thing to read on the Sep 24 run.
The workflow's commit step pushes to `main` by name, so it cannot be
run against a branch, and this session holds no Grok key; three
hand-written briefs (Mexico City's Hoy No Circula, Jevons' *The Coal
Question*, the European diesel tax break — each a documented case
absent from the 143-entry history, as the June 2026 pass restocked by
hand) take UC to 29 unproduced / 4.1 weeks so the alarm clears now.
The automation refills to eight weeks on its next run (trigger < 5
weeks); if the 13:37 UTC cron has passed when this merges, dispatch
the workflow with `force`.

## 7. Readout — Sep 24

- `combined_generation` on Tesla / SpaceX / FF / PT / MIT: share
  `combined`; fallback reasons in the log.
- `script_digest_overlap_pct` and `script_digest_coverage_pct` on those
  episodes; `script_words` against target.
- Chapters per episode on PT and MIT.
- `source_integrity_verified_from_fetched` and
  `source_integrity_stripped_sentences` on PT, OV, FF; the sidecar's
  `stripped_sentences` list.
- The audience headline, per show, against the Sep 16 line.
- Restock Topic Queues: the first needed run's conclusion; UC ≥ 4.0 wk.
- `Run Tests` on main: green on every push since this merge.

## 8. Sep 18 follow-up — the first flagship slate under combined generation

Eleven of eleven shows published; nothing lost; every spoken-text gate
passed first time; Nerra Daily Ep029 trimmed all eleven segments on frame
anchors. Two defects the counters could see:

**Combined generation shipped on 2 of 5 eligible flagships.** M&A and MIT
kept their combined scripts (M&A 1,540 words on a 1,500 target, 25 %
verbatim, 80 % coverage — the first at-target M&A in weeks; MIT 2,013
words, 100 % coverage, but 63 % verbatim and 7 copied sections, so the
"PART 2 is not PART 1" bridge did not hold there). Tesla, SpaceX and
Planetterrian recorded `combined_stale` and ran the script call anyway.
The run logs show no regeneration behind two of them: Tesla's stash
survived at 50 % of its lines, SpaceX's at 28 % — and the reason is that
run_show rewrites the tail of EVERY item line after generation
(`transform_daily_body` turns `Source: <url>` into `Source: [domain](url)`,
the Google-News resolver swaps the url), so a comparison on raw lines
read a link rewrite as a replacement. The test now compares normalised
sentences: on today's real digests a link-rewritten copy scores 1.00 and
yesterday's digest against today's scores 0.00–0.02.

**Strip mode removed five true sentences from SpaceX Ep104.** All five
sources resolved (HTTP 200) and each page carries the fact — WESH's own
headline is "SpaceX president to Boeing: You got paid — now fly the
thing"; keeptrack's lede is "NASA preparing to order two additional
Starliner missions as SpaceX plans Crew Dragon retirement by 2030". The
model's `supporting_quote`s were paraphrases, the 0.9 verbatim check
failed as designed, and the repair prompt required a DIFFERENT url, so a
truthful model omitted every claim ("no usable replacements") and the
committed sidecar read "claims=0, passed". Omni View lost the Bank of
Japan's move to 1.25 % the same way. Fix: for a failed claim whose
source resolved, the repair carries the page's most relevant passage and
allows the same url with a quote copied verbatim from it; the mechanical
check is untouched, an unrelated verbatim sentence is rejected, the new
metric `source_integrity_repair_recovered` says whether it worked, and
the sidecar's `gate.pre_strip` records what the gate saw before the strip.

A bag-of-words "claim support" check was measured on 28 quote-verified
claims from the last ten days' sidecars against their own and 752 foreign
sources: own-source scores 0.43–1.0, foreign p95 0.57, and 4 % of foreign
pairs reach 0.5 with every number present — not a gate, and rejected.

Guards: `tests/test_provenance_pass_2026_09_18.py`. Read on 09-24:
`combined_stale` share on the five flagships, `source_integrity_repair_recovered`
against `_stripped_sentences` on SpaceX / OV / PT, and `script_repeated_facts`
on combined episodes (a dropped cross-section duplicate is still spoken by
a combined script — `strip_script_sentences` would also remove the first
telling, so that stays open).
