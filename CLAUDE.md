# CLAUDE.md — Tesla Shorts Time Podcast Network

## Titles: one module owns every limit

**Never truncate a title outside `engine/titles.py`.** Import a limit and
`clip_words()` / `episode_title()` from it. A new surface adds its limit
to that module; it does not write its own slice.

This is not style preference. The same bug shipped three times
independently — `engine.blog` sliced `hook[:100]`,
`video_metadata._truncate` sliced `text[:max_len - 3]`, and `run_show`
built `f"Ep {n}: {hook}"` with no cap at all — and the consequence was
that **YouTube silently rewrote episode titles on every show in the
network** for months, cutting mid-word and emailing to say no action was
required. Current limits: YouTube 100, podcast RSS 100 (same on purpose,
YouTube ingests the feed), web `<title>` lead 62, newsletter subject 78.
`tests/test_titles.py` enforces the property against ~4,500 generated
hooks in English and Russian.

Full context, including the Search Console work, the verified state of
each subsystem and the traps found along the way:
[`docs/session_2026-07-28.md`](docs/session_2026-07-28.md).

## Funnel links: one module owns every campaign id

**Never build a `utm_*` link, campaign id, or capture tag for a
published surface outside `engine/funnel.py`.** Import
`episode_link()` / `campaign_id()` / `destination_for()` /
`capture_tags()`. A new surface adds itself to that module's closed
vocabularies; it does not hand-roll a query string.

Same shape as the titles rule, same cause. Three surfaces each invented
their own scheme and the result was that **nothing the network published
could be joined to anything it measured**: `video_metadata` wrote
`utm_campaign=ep45` with no show slug (every show's episode 45 became
one GA4 row), `ru_dub` linked the bare English homepage with no UTM at
all (@NerraRU — the network's HIGHEST-reach surface at ~25,800
views/30d — was invisible), and Buttondown captured one undifferentiated
`gallery-subscriber` tag. Four live analytics systems, no shared key, so
the July 18 2026 audit's central finding (world-class factory, funnel is
the product gap: 3,900 downloads/30d, 3 subscribers) could not be acted
on.

`campaign_id()` and `parse_campaign_id()` must stay exact inverses —
`scripts/build_funnel.py` attributes GA4 rows purely by parsing them, so
drift is SILENT (the report just goes to zero).
`tests/test_funnel.py` round-trips every generated shape and asserts
each real surface emits a parseable campaign.

Full context — the funnel report's honesty rules (null vs 0, the
30-denominator floor, `attribution_coverage_pct`), the RU SpaceX pilot,
and the Shorts motion A/B: [`docs/funnel.md`](docs/funnel.md).

## Provenance: one module owns the claim ledger

**A claim's provenance is DATA, not formatting — `engine/claims.py` owns
it.** Never add a new stripper for source/citation text without checking
the ledger path first. **Since Oct 1 2026 the gate's enforcement is the
STATUS and the public record, not removal**: `on_failure: flag` on every
show publishes the sentence and marks its claim (see "Oct 1 2026 — publish
and mark" below); `strip` and `block` remain selectable per show but are
no longer the network policy. Never turn a flagged claim's status into a
silent pass, and never render a surface that hides the flag.

Same shape as the two rules above, discovered Aug 2026: three functions
in `run_show.py` stripped every attribution the model produced (each for
a good reason — Offshore North Ep001 read its sources block ALOUD) while
nothing anywhere verified that an asserted fact traced to anything, so
**fabricated citations were the expected output** — three unrelated
chapters in two published book volumes each cited "a 1962 paper in
*Nature*" for findings actually published elsewhere (Wagner 1960
*Br J Ind Med*; Fryer 1960 *E Afr Agric J*) or nowhere (the Huxley/Aswan
paper does not exist). True facts wearing false provenance: the model
supplied the citation SHAPE, the pipeline deleted the citation, nothing
checked the difference.

Now: digest generation emits a fenced `claims` JSON ledger (extracted
before any published surface sees it), the gate verifies every entry
(URL resolves + supporting quote fuzzy-appears in the source) and lints
citation-shaped prose against it (`CITATION_SHAPE_PATTERNS` — the
fabrication signature). Verified ledgers commit as
`digests/<slug>/*_claims.json`; books render them as endnotes. Rollout:
network-wide SHADOW (`_defaults.yaml`) from Aug 2026, **enforce: true on
the narrative shows** (UC/FPD — a blocked episode there costs a rerun,
never a burned queue slot: the gate runs before the digest save).
**Since Sep 12 2026 the gate is ENFORCED on every show**, with
`source_integrity.on_failure` deciding what an enforce-mode failure
does after the one repair pass: `block` (UC/FPD — the episode skips) or
`strip` (the network default — `engine.claims.strip_unverified` REMOVES
every sentence the gate cannot vouch for from the digest, the script is
stripped in step by `strip_script_sentences`, the mechanical gate
re-runs on what is left, and only a still-failing text blocks). Shadow
data had shown blocking would lose 2–4 of 7 episodes on five news shows
for malformed ledger entries and 403s, never a proven fabrication.
Strip is not a warning: nothing unverified reaches the blog, the feed or
the newsletter; an uncovered citation shape whose item carries a
resolving `Source:` URL counts as sourced by the item; HOOK/header lines
are never edited. Guards: `tests/test_simplification_2026_09_12.py::TestStripMode`.
The three strippers stay — they
remove leakage; the ledger carries provenance. Audit tools:
`scripts/verify_claims.py` (re-verify committed ledgers),
`scripts/measure_citation_exposure.py` (corpus exposure),
`scripts/soften_citations.py` (backfill, dry-run default). `check_feeds.py`
(ex-`check_sources.py`) grades FEED health only — it has no view on
truth. Drift guards: `tests/test_source_integrity.py`.

**Aug 25 2026 — unreachable ≠ fabricated, plus two loop-breakers.** UC
lost two days because its next topic's authoritative sources
(officialgazette.gov.ph) 403 GitHub runners: the gate read "cannot
fetch" as "fabricated", the queue-preserving skip re-picked the same
topic daily, and nothing persisted the failure. Now: (1) verification
labels 403/429/5xx/transport failures `unreachable` — **still a gate
FAILURE** (the enforce contract is untouched), but distinct from the
fabrication signature (404 / quote-not-found); (2) an enforce-mode
block first gets ONE `attempt_claim_repair` pass (the model re-sources
only the failed claims with fetchable alternatives — claim text and
anchor are pinned, the repaired ledger re-runs the FULL mechanical
gate, so repair can never launder an unverifiable claim); (3) a topic
the gate blocks twice is **deferred by the picker**
(`gate_blocks`/`gate_blocked_last` on the queue entry, committed by
run-show.yml's skip-path step — the annotation is the only thing that
survives a skip; threshold in
`engine.topic_queue.GATE_BLOCK_DEFER_THRESHOLD`). Deferred topics stay
in the queue for the operator and are surfaced by
`queue_health()["gate_deferred"]`. Guards:
`TestUnreachableClassification`, `TestClaimRepair`
(`tests/test_source_integrity.py`), `TestGateBlockCooldown`
(`tests/test_unintended_consequences.py`).

**Sep 8 2026 — reviewer notes are a gate failure, not a formatting
issue (WO-13).** Five fact-checker parentheticals shipped inside chapter
bodies of the Volume 1 builds — "(No public source found tying this
specific manifold redesign to the reusability program; keep the
engineering point …)" — and had to be cut from the store EPUBs by hand.
They came from research-fleet general-form rewrites applied to digests
(Aug 24/26), not from `attempt_claim_repair`, which only ever writes
ledger entries (anchor and claim text pinned; `TestWO13ReviewerNoteGate`
proves a note smuggled into the repair JSON never reaches prose).
`engine.claims.find_reviewer_notes` (`REVIEWER_NOTE_PHRASE_RE` + any
>40-char parenthetical mentioning a source being found/traced/supported;
markdown link targets exempt) now fails `run_source_integrity_gate`
(`reviewer_notes`, logged by run_show) and `build_epub` refuses the
volume (`validate_chapter_prose`, names chapter + match). The EPUB also
carries a legacy `toc.ncx` rendered from the same `_nav_entries` as the
nav (Draft2Digital: "ePub3 missing an NCX file"); epubcheck 0/0.

**Sep 5 2026 — the empty ledger was the norm, not the exception.** Every
UC and FPD episode since the counters exist (UC Ep099–106, FPD Ep086–091)
shipped `claims=0`: the appendix calls an empty array normal, so on the
narrative shows the enforce gate was in practice the citation-shape lint
alone, and `attempt_claim_repair` never fired for it (it keyed on failed
verifications). UC 2026-09-05 was blocked twice on one topic with
claims=0 and two uncovered shapes. Repair now also targets UNCOVERED
sentences (anchor pinned to the sentence, full mechanical gate re-runs,
so an unsourced sentence still blocks), and UC's episode prompt no longer
seeds the literal "A 1962 Nature paper warned…" example — the exact
fabricated citation this section opens with. Guards:
`TestClaimRepairUncoveredShapes`.

**Oct 1 2026 — publish and mark, never strip (operator-directed).** In the
14 days to 10-01 strip mode removed 68 sentences across 261 episodes and
every audited one was TRUE (a 403 journal, an X post the fetch stage held,
a paraphrase, MIT's NASDAQ close); UC skipped 11 of 28 days on its own
gate; four of fifteen flagship episodes had zero claims. The model's
training data lags the 24-hour cycle, so a sourced story newer than the
model must never be dropped for failing memory. Now `on_failure: flag`
(network default, UC and FPD too): after the one repair pass nothing is
removed but reviewer notes; every ledger entry commits with a `status`
(`verified` / `verified_from_fetched` / `verified_later` /
`unverified_unreachable` / `unverified_not_found` /
`unverified_quote_mismatch` / `unverified_uncovered` / `malformed`),
`gate.flagged_sentences` names the sentences, `gate.policy_version` is 2;
metrics `source_integrity_flagged_*`. `scripts/reverify_claims.py` re-checks
unverified claims nightly for seven days (`verified_later`, `verified_at`,
`first_status`; the sidecar glob is in nightly's add-paths). The record is
public — `claims.html` and `claims/<slug>.html` (`engine/claims_ledger.py`,
`generate_claims_pages`, in `--static-pages` and the sitemap), status
badges on every post's claims panel, links from show pages, nav and
footer; `engine.brand.CLAIMS_PROCESS_STEPS` / `CLAIMS_STATUS_LABELS` own
the process copy and the AI-disclosure / editorial / FAQ pages describe
this policy and no stronger one. Register `claims-flag-policy-2026-10-01`;
guards `tests/test_claims_flag_mode_2026_10_01.py`,
`tests/test_claims_pages_2026_10_01.py`.

**Oct 17 2026 — the page the run read vouches, and an unsourced back-test is
a citation shape.** `build_local_texts` now includes an ordinary article's
page `full_text` (`full_text_source: page`): the gate's own HTTP check is a
second, differently-headed request, and France24 refused it on 12 claims in
the week to Oct 17. Two shapes joined `CITATION_SHAPE_PATTERNS` — a back-test
that "shows/found" something, and a historical rate "in N% of cases" —
after Modern Investing Ep203 aired an invented "58% of cases" back-test
inside an item sourced only to a PPI page and the gate passed it 5/5; on all
2,470 committed digests they match four sentences, every one an unsourced
MIT statistic. Guards `tests/test_citation_shapes.py`,
`tests/test_slate_2026_10_17.py`.

**Oct 5 2026 — the coverage floor reads the item's OWN source.** It had
added one verified claim in 24 flagship episodes: it asked the model to
name a fetchable page for each uncovered item from memory, and a truthful
model answered `[]` (Tesla Ep624, SpaceX Ep120) while every item already
cited its Source and the run held the fetched copy. Now
`attempt_item_coverage_repair` pins each item's Source URL and hands over
the passage of it that discusses the sentence (fetched copy first, then
the page); the model only judges support and copies the quote, and the
mechanical check is unchanged. Entries are added only when each verifies
on its own, the result is kept only when the gate verifies more and gets
no worse, and the floor now runs on a FAILING gate in flag mode too (it
never touches the failing entries). One `item coverage floor:` log line
gives the counts. Register `claims-coverage-grounded-2026-10-05`; guards
`tests/test_claims_coverage_grounded_2026_10_05.py`.

**Sep 18 2026 — the quote was the problem, not the source.** SpaceX
Ep104 lost five TRUE sentences to strip mode (Shotwell telling Boeing
to fly Starliner, Crew-13 entering quarantine, Dragon's 2030 retirement)
with every source RESOLVED: WESH's own headline was the claim. The
model's `supporting_quote`s were paraphrases, so the 0.9 verbatim check
failed, and the repair prompt demanded a DIFFERENT url — a truthful
model omitted every claim ("no usable replacements") and the sidecar
then read "claims=0, passed". Now: for a failed claim whose source
resolved, `attempt_claim_repair` hands the model the page's most
relevant passage (`source_excerpt_for_claim`, from the run's fetch
cache or the fetched copy) and allows the SAME url with a quote copied
verbatim from it; the mechanical 0.9 check is untouched and a verbatim
sentence unrelated to the claim is rejected
(`_quote_consistent_with_claim` — two shared content words or a shared
number). Metric `source_integrity_repair_recovered` (read beside
`_stripped_sentences`); the sidecar's `gate.pre_strip` records the
verdicts and the model's quotes as the gate saw them BEFORE the strip.
A bag-of-words "claim support" fallback was measured and REJECTED as a
gate: random foreign claim/source pairs score ≥ 0.5 four percent of the
time and short true sentences score no higher. Guards:
`tests/test_provenance_pass_2026_09_18.py`.


### Cadence + model migration (Sep 21 2026)

**A show's cadence lives in six places and the public one drifted.**
CRON_MAP, the scheduler Worker's `SLOTS`, `review_episodes.py`'s registry
(the audit's belief), daily-audit's RSS-freshness limit,
`engine.daily_edition`'s `monday_only`, and the `schedule` string every show
page / homepage card / explore filter renders. The first five were correct
and in sync; **the sixth had been wrong since June on three shows.**
env_intel said "Odd weekdays", finansy_prosto and privet_russian said "Even
days", and all three have published Mondays only since the June move — the
July-18 P0 fixed the cron and the audit and never the copy. Unintended
Consequences said "Weekdays" and publishes all seven days. Feed descriptions
carried the same claims, which is the text Apple and Spotify display.
`tests/test_dp_pod_weekly_2026_09_21.py::TestNoSurfaceStillSaysDaily`
derives the check from CRON_MAP, so a cadence change that forgets the copy
now fails. (`modern_investing` is genuinely daily — the "weekdays only" note
elsewhere in this file was the stale one.)

**DP Pod is weekly** (Monday), operator-directed: 60 downloads/30d and 3 in
its last complete week, with three prompt passes that improved the copy and
moved no listeners.

**A missing section is a structural defect, same as an empty one.** The
validator has always emitted `Section 'X' is missing from digest`, and
`_empty_mandatory_section_issues` only matched `0 items` — so an EMPTY
section spent the one-shot corrective regeneration while an ABSENT one
shipped. DP Pod published four episodes with no Lever segment at all (37/37
digests carried it before the 2026-09-04 lever pass, 14/18 after) and the
run logged a formatting mismatch. The gate matches both now, and dp_pod has
a `SHOW_VALIDATION_CONFIGS` entry at last — it had none, which is why
nothing noticed a show had stopped carrying one of its own segments. Fixed
data-side rather than by rewording a prompt that already said "never omit
any": this show's own history (the Network-pick rotation) says an
instruction the model breaks is enforced in code.

**Model changes follow [`docs/model_upgrade_playbook.md`](docs/model_upgrade_playbook.md),
and `scripts/model_trial_report.py` is the instrument.** It reads committed
`metrics_ep*.json` stage durations — dating each episode from the sibling
digest filename, never file mtime, which a fresh checkout rewrites — and
exits non-zero when an LLM stage's p95 passes 50% of the request timeout,
regresses >50% against baseline, or any stage failed. The Aug-18 outage's
registered triggers watched hallucination rate and reviewer flags; nobody
watched latency, and latency is what fired. The grok-4.6 -> 4.7 migration
(experiment `grok-47-staged-migration`) moves two sites on day one — the
episode reviewer and omni_view's script stage — and widens only on a
GATE: PASS. **The reviewer's `reasoning_effort: "low"` branch is a prefix
TUPLE, not one id**: at default effort 4.6 blew the 300s timeout on ~1/3 of
episodes and killed the audit job, and a pin moved to 4.7 would have matched
nothing and silently restored default effort.

**`api/member_metrics.json` filters by Stripe PRODUCT.** The account is
shared ("Lil Learning") and carries the Lil Words products beside Nerra
Personal, so summing every subscription would put another product line's
revenue in a file labelled Nerra's MRR — one number, no error, just wrong.
Today the only active subscription is Nerra Personal, so filtered and
unfiltered agree, which is exactly why the filter went in before it mattered.

### Freshness, repetition and reproducibility (Sep 30 2026)

Operator-directed network review (review:
[`docs/reviews/network_review_2026_09_30.md`](docs/reviews/network_review_2026_09_30.md);
ledger `network` 2026-09-30; register `freshness-dating-2026-09-30`,
`frame-memory-2026-09-30`, `whisper-av-pin-2026-09-30`; guards
`tests/test_freshness_pass_2026_09_30.py`,
`tests/test_repetition_pass_2026_09_30.py`). The operator heard
months-old stories and repetition; both confirmed, one cause each.

**An article's date has ONE owner: `engine/article_dates.py`.** Every path
that could not date an article used to stamp it with the RUN CLOCK —
undated feed entries, every web-search result, every X post, every Google
News item (whose feed date is the INDEX date) — so it sorted to the top of
the prompt and printed today's date beside a headline the prompt called
"FRESH". A 2013 Teslarati page aired on Tesla three times (08-17, 09-08,
09-23), a 2021 Mashable story and a January-2025 Starlink deal on SpaceX,
every one behind an UNDATED URL whose page carried its real date; not one
of 691 URL-dated items was stale. Now: `date_source` on every article
(`feed` / `url_path` / `page` trusted; `index` / `model` / `x_post` /
`unknown` not), an unknown date is `""` (sorts LAST, renders no date —
never write `now` into `published_date` again), `probe_page_dates` opens
up to `date_probe_max` pages (default 12, YAML; 0 = off) for the untrusted
ones and the page date replaces the index date or the model's claim, and
`stale_article_days: 3` is on the twelve established news shows. The xAI
search helper raises `SearchUnavailable` instead of falling back to a
tool-less call (an answer from memory parsed as search results — the
route a thin day took to a months-old lead). The tracker's URL-dedup
window is its RETENTION (45 days, `content_tracking.max_days`, now
actually passed to the tracker); X posts and web results pass
`filter_recent_articles` like the RSS ladder. The Sep 23 "credit the
linked article" X fix had shipped into `_parse_x_posts`, which the live
path never calls — `_x_post_entry` is the one builder both parsers use.

**Repetition is frames and second tellings, never exact duplicates**
(`script_duplicate_sentences` 0 everywhere). Combined generation writes
PART 2 from the UN-deduped PART 1, so a dropped cross-section duplicate
was still told twice (SpaceX 2–3× per episode); `strip_second_tellings`
keeps the FIRST telling and `amend_combined_script` rewrites the stash.
Sentence FRAMES ("Before we go, keep an eye on…" FF 15/15, "If you want
to go deeper" OV 15/15, "The case on both sides" every desk 7/8) are
handled the way the ledger says works — data-side rotation memory, never
a prompt-only de-seed (five straight misses on FF): `engine/frame_memory.py`
mines the last six scripts for openers that recur with different tails
(verbatim furniture and chapter anchors exempt; a proper noun, digit or
spelled ticker in the opener is content) and the two shared podcast
snippets render `{recent_frames_block}`; opt-in `frame_memory: true` on 17
shows, MIT off (its ledger lines dominated). ⚠️ A/B-listen: the digest
input on the 12 shows, the 45-day recurrence notes, and the frame block.

**Reproducibility.** PyAV 19.0.0 (PyPI 09-29) removed a keyword
faster-whisper passes; every one of the 23 episodes of 09-30 shipped with
NO transcript and the spoken-text gate ran blind — `av>=11,<19` (floor 18.1 since Oct 9) in
requirements, and `engine/transcripts.py` retries without VAD only on a
VAD-shaped error and prints a `::error::` otherwise. Main had been red
since 09-26 on a FIXTURE (an interview transcript with no 200-char line)
with four data-driven guards behind it: a guard that reads today's
committed data must tolerate today (judge episodes ≥ 1 day old, floors as
runways, fixtures on what they mean — playbook rule). The daily health
check's word floors are the YAML's (`scripts/grok_show_check.py`; it had
flagged Tesla "66% of target" daily against 2,000 words the pipeline
never used). **The model reading that binds the next migration question:**
on the same combined path and snippet, the grok-4.7 cohort writes (4–17%
digest-verbatim, 13–19 verified claims) where the 4.3 flagships copy
(49–78%, 0–3); overlap moved with the model, not with three passes of
prompts and gates, so a script-density threshold is no longer a review
prediction. Operator items: UC skipped 4 of its last 7 days on its own
claims gate; Tesla Ep617's 17 unsourced items passed the lint; a runner
lockfile.

### First post-merge slate, the cohort on every surface, trust surfaces (Oct 1 2026)

Operator-directed follow-up to the Sep 30 pass (review:
[`docs/reviews/network_review_2026_10_01.md`](docs/reviews/network_review_2026_10_01.md);
ledger `network` 2026-10-01; register `frame-memory-wired-2026-10-01`,
`story-clusters-2026-10-01`, `platform-ask-2026-10-01`,
`apple-ratings-instrument-2026-10-01`, `vtt-transcripts-2026-10-01`,
`launch-cohort-newsletters-2026-10-01`). Scored on the 20 episodes of 10-01
(all post-merge): transcripts 20/20 (0/19 the day before), undated articles
in the prompt 0 on 18 of 19 news shows, the stale gate fired six times,
claims 164 → 205. What binds:

**A wiring guard renders through the REAL config object.** The Sep 30
frame-memory block read `config.output_dir`, an attribute only its test
double had; the real `ShowConfig` keeps the directory on
`config.episode.output_dir`, so the block rendered `""` on all 17 opted-in
shows for a day while the guard passed. `engine.frame_memory._config_output_dir`
reads the nested field; the guard loads `shows/omni_view.yaml`.

**A lint measures the text that ships.** Top World Ep009 published 8 of 10
items with no Source while `items_without_source` read 0: the model joined
the reader-only `Ranks:` clause and the `Source:` line, the clause read as
an absence sentence by design ("no figure given"), and the absence filter —
which runs AFTER the lint — dropped the one-sentence line, URL included.
`engine/absence_sentences.py` never drops a line that carries a URL or a
Source tail (the citation stays, the clause goes) and treats `Ranks:` as
structure; run_show re-reads the lint after the filters
(`items_without_source_shipped`). Guards: `tests/test_top_world_sources_2026_10_01.py`.

**A story told once per outlet is not a duplicate the overlap dedupe can
see — cluster upstream, annotate, never drop.** Tesla Ep622 carried the
Model 3 refresh as eight items from eight outlets (each a different angle,
vocabulary overlap 0.10–0.38 against the 0.5 threshold) and the script told
it five times. `engine/story_clusters.py` clusters the fetched list on
salient title+teaser tokens with the show's furniture filtered against the
tracker's 45-day headline window, and later members carry an inline
SAME-STORY note (one item, fold the angle, cite both URLs); opt-in
`story_clusters: true` on the 22 news shows; outcome metric
`story_clusters_retold_in_digest`. A script-level repeated-fact stripper was
prototyped and REJECTED: it also removes the hook-then-body restatement
every cold open relies on. **The TTS emoji strip's "enclosed chars" range
spanned Hangul and every CJK block** — non-Latin outlet names vanished from
the spoken text (Ep622 aired "  reported the patent suit…" for 디지털투데이);
the four real enclosed blocks are listed now, and
`engine.article_text.speakable_source_name` lists a non-Latin outlet by its
domain stem in the prompt.

**The thirteen launch-cohort shows were on every generated surface and off
the three a visitor hits first.** The Worker's `SHOW_NEWSLETTER_TAGS`
(`workers/gallery/src/handlers.ts`) had none of them — every cohort show
page offered a signup whose tag the Worker dropped — plus two established
tags it never had (`DP Pod`, `Nerra Voices`); `tests/test_worker_show_tags_2026_10_01.py`
reads the TypeScript against every show YAML. OP3 wrote NOTHING for an
unindexed feed, so the audience headline read `shows_measured: 16` and
Mission Control showed "—"; `fetch_op3_stats` writes `resolved: false`,
every consumer tolerates it, and the card says "not indexed"
(`shows_unindexed`). None of the thirteen has been submitted to a directory:
`docs/podcast_directories.md` carries their rows and the order — Podcast
Index first, because OP3 resolves feeds through it. The cohort newsletters
are ON (operator: `wrangler deploy`). Hubs `prediction-markets` and
`ai-infrastructure` exist, gated by the 12-episode floor.

**Trust surfaces a listener can see** (all metadata/web except the first):
the spoken closing gains ONE follow-or-rate sentence on alternate days where
it carried no ask (`engine/intros.py`, shapes alternate, Russian on FP;
⚠️ AUDIO — A/B-listen); every feed item carries a WebVTT transcript tag
FIRST (Apple reads VTT; the JSON tag stays for legacy readers) and the
channel carries `itunes:type`, a UUIDv5 `podcast:guid` and a branded
`itunes:author` — 1,972 VTTs and 30 feeds backfilled by
`scripts/backfill_transcript_vtt.py`; show notes carry a network-default
rating ask from each show's NEXT episode (`engine/episode_ask.py`
`DEFAULT_ASK_FROM_EPISODE` — older posts regenerate byte-identically);
every newsletter carries a rating line to the show's own Apple/Spotify
pages (none when the registry has none) and the AI-host branch no longer
raises on `share_text`; YouTube descriptions carry the channel subscribe
link, a Sources line and an AI-host disclosure where the host is Mira
(`engine.video_metadata.video_disclosure_for`); the Shorts funnel comment
and the X follow line take their cadence word from the registry schedule
(`engine/cadence.py`); the promo rotation's Age of AI line no longer says
"on the phone" and `TestPromoRotationTruth` sweeps every surface. Apple
ratings are read nightly from the public show pages
(`scripts/fetch_apple_ratings.py` → `api/apple_ratings.json`, null never 0)
so the asks are measurable; baseline 4 ratings across 15 shows.

**Trust surfaces a reader can see.** Every news-show post renders a
collapsed **Verified claims (N)** panel from its committed `*_claims.json`
(one honest line when the ledger is empty — never hidden), a provenance
line from `engine.brand.episode_provenance` ("Written from N sources · M
claims checked against their sources · K unverified sentences removed
before publication · voiced with Grok TTS"; AI-host shows say so) and a
**Report an error** mailto. **Corrections have a mechanism**
(`engine/corrections.py`, `digests/<show_dir>/corrections.yaml`,
`docs/corrections.md`): a dated box on the corrected post, a line in its
show notes, and the "Correction to episode N" line in the NEXT episode's
show notes that the policy page had promised with nothing behind it
(`engine.show_notes.append_show_notes_extras`, wired in run_show). Audio is
never edited silently (landmine #25). **The verification copy on
`ai_disclosure` / `editorial` tells the truth about the gate** (enforced on
every show, one repair pass, unverified sentences removed, narrative shows
hold the episode) and a guard reads `_defaults.yaml` so it cannot drift;
the Age of AI bullet there had re-grown the stronger gate-2 claim the Sep
22 pass retired — it states the seven-day auto-publish. **One
listener-facing address**: `engine.brand.CONTACT_EMAIL` feeds the
editorial, FAQ and contact pages (Jinja global `contact_email`) and every
post; the RSS owner email in `_defaults.yaml` is a different thing. Guards:
`tests/test_web_trust_2026_10_01.py`.

## Project Overview

Automated daily podcast generation system running 31 shows via a unified
`run_show.py` runner + per-show YAML configs, plus 4 legacy standalone scripts
(deprecated — see note below). Shows use **Grok TTS** (`engine.tts.grok_speak_chunk`)
and (where enabled) post to X/Twitter via `engine/publisher.post_to_x()`.

| Show | Legacy Script | YAML Config | Schedule | X Account | TTS |
|------|--------------|-------------|----------|-----------|-----|
| Tesla Shorts Time | — (deleted) | `shows/tesla.yaml` | Daily | `@teslashortstime` | Grok TTS (custom) |
| Omni View | — (deleted) | `shows/omni_view.yaml` | Daily | `@omniviewnews` | Grok TTS (custom) |
| Fascinating Frontiers | — (deleted) | `shows/fascinating_frontiers.yaml` | Daily | `@planetterrian` | Grok TTS (custom) |
| Planetterrian Daily | — (deleted) | `shows/planetterrian.yaml` | Daily | `@planetterrian` | Grok TTS (custom) |
| Env Intel | — | `shows/env_intel.yaml` | Monday | `@teslashortstime` | Grok TTS (custom) |
| Models & Agents | — | `shows/models_agents.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| Models & Agents for Beginners | — | `shows/models_agents_beginners.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| Финансы Просто | — | `shows/finansy_prosto.yaml` | Monday | — (X disabled) | Grok TTS (Olya) |
| Modern Investing Techniques | — | `shows/modern_investing.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| Привет, Русский! | — | `shows/privet_russian.yaml` | Monday | — (X disabled) | Grok TTS (Olya) |
| Unintended Consequences | — | `shows/unintended_consequences.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| First Principles Daily | — | `shows/first_principles.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| SpaceX Daily | — | `shows/spacex.yaml` | Daily | — (X disabled) | Grok TTS (custom) |
| The DP Pod | — | `shows/dp_pod.yaml` | Monday | — (X disabled) | Grok TTS (two-voice: Patrick + Dan) |
| The Age of AI | — | `shows/age_of_ai.yaml` | When an interview is ready (Nerra Voices pipeline, NOT run_show) | — (X disabled) | Real guest phone audio + Mira narration (Grok voice `ara`) |
| Offshore North | — | `shows/offshore_north.yaml` | Monday | — (X disabled) | Grok TTS (Dan `0vscf8u8yrxc`, single-narrator) |
| AI Chips & Data Centres Daily | — | `shows/ai_chips.yaml` | Daily | — (X source only) | Grok TTS (custom) |
| MAG 7 Daily | — | `shows/mag7.yaml` | Daily | — (X source only) | Grok TTS (custom) |
| Peptides Weekly | — | `shows/peptides.yaml` | Thursday | — (X source only) | Grok TTS (custom) |
| Longevity Weekly | — | `shows/longevity.yaml` | Wednesday | — (X source only) | Grok TTS (custom) |
| Vancouver Daily News | — | `shows/vancouver.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Collingwood Weekly | — | `shows/collingwood.yaml` | Friday | — (X disabled) | Grok TTS (Mira, `ara`) |
| Prediction Markets Daily | — | `shows/prediction_markets.yaml` | Daily | — (X source only) | Grok TTS (custom) |
| Omni View Top World News | — | `shows/omni_view_world.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Omni View North America | — | `shows/omni_view_north_america.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Omni View Europe | — | `shows/omni_view_europe.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Omni View Asia Pacific | — | `shows/omni_view_asia_pacific.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Omni View Africa & Middle East | — | `shows/omni_view_africa_mideast.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Omni View Central & South America | — | `shows/omni_view_latam.yaml` | Daily | — (X source only) | Grok TTS (Mira, `ara`) |
| Nerra Daily | — | registry-only (`shows/network_meta.yaml`; NOT run_show — assembled by `scripts/build_daily_edition.py`) | Daily, 7am Eastern, after the English slate (Vancouver excluded) | — (X disabled) | Splices published show audio + Mira links (Grok voice `ara`) |

> Weekly-summary segment (July 2026): shows on a daily cadence with
> `weekly_summary_segment: true` in their YAML run a NORMAL daily episode on
> Sunday that ALSO includes one short "week in review" segment synthesised
> from the past 7 days via the content lake. (This replaced the retired full
> Sunday weekly-recap mode, which skipped the daily news fetch and turned the
> whole Sunday episode into a look-back.) The segment is appended to the
> podcast-only copy of the digest, so no host-instruction text reaches the
> blog / RSS. See landmine #19.

**Science That Changes Everything** (`digests/science_that_changes.py`, ~83 lines)
is a standalone X-posting script, not a podcast show.

## Architecture

### Pipeline (per show, per run)

1. **Fetch** news sources (RSS, xAI/Grok web search, xAI ``x_search`` for Tesla stock quote)
2. **Dedup** via ContentTracker (cross-episode) + entity dedup
3. **Generate** digest text via xAI/Grok API
4. **Synthesize** podcast audio via Grok TTS (`engine/tts.py`, WAV @ 48 kHz)
5. **Mix** intro/outro music with voice (ffmpeg) — all shows (configurable per YAML)
6. **Post** X thread via `engine/publisher.post_to_x()` + update RSS feed + commit output to git

### Key Directories

```
nerranetwork/
├── run_show.py                    # Unified show runner (~716 lines)
├── shows/                         # Per-show YAML configs
│   ├── tesla.yaml
│   ├── omni_view.yaml
│   ├── fascinating_frontiers.yaml
│   ├── planetterrian.yaml
│   ├── env_intel.yaml
│   ├── models_agents.yaml
│   ├── models_agents_beginners.yaml
│   ├── finansy_prosto.yaml
│   ├── modern_investing.yaml
│   └── privet_russian.yaml
├── digests/                       # Legacy show scripts (deprecated) + ALL generated output
│   ├── tesla_shorts_time.py       # DEPRECATED — use run_show.py tesla
│   ├── omni_view.py               # DEPRECATED — use run_show.py omni_view
│   ├── fascinating_frontiers.py   # DEPRECATED — use run_show.py fascinating_frontiers
│   ├── planetterrian.py           # DEPRECATED — use run_show.py planetterrian
│   ├── science_that_changes.py    # ~83 lines — standalone X posting script
│   ├── xai_grok.py                # Shared xAI/Grok API helper (~111 lines)
│   ├── tesla_shorts_time/         # TST output + summaries_tesla.json
│   ├── omni_view/                 # OV output + summaries_omni.json
│   ├── fascinating_frontiers/     # FF output + summaries_space.json
│   ├── planetterrian/             # PT output + summaries_planet.json
│   ├── env_intel/                 # EI output + summaries_env_intel.json
│   ├── models_agents/             # M&A output + summaries_models_agents.json
│   ├── models_agents_beginners/   # MAB output
│   ├── finansy_prosto/            # FP output (Russian)
│   ├── modern_investing/          # MIT output
│   ├── privet_russian/            # PR output (bilingual Russian)
│   └── *.mp3, *.md, *.txt        # Legacy TST flat output (historical)
├── engine/                        # Shared modules
│   ├── __init__.py
│   ├── utils.py                   # Env helpers, text processing, similarity, dedup
│   ├── tts.py                     # Multi-provider TTS (Grok primary; legacy ElevenLabs path retained) — auth, chunking, synthesis
│   ├── audio.py                   # mix_with_music (3 modes), normalize_voice, duration helpers
│   ├── publisher.py               # RSS feeds, X posting, GitHub Pages summaries, digest formatting
│   ├── content_tracker.py         # Cross-episode dedup (per-show section patterns)
│   ├── fetcher.py                 # RSS article fetching
│   ├── generator.py               # LLM digest/podcast script generation
│   ├── tracking.py                # Credit/usage tracking
│   ├── config.py                  # YAML config loader
│   ├── storage.py                 # Cloudflare R2 storage helpers
│   ├── newsletter.py              # Email newsletter helpers
│   └── validation.py              # Config validation
├── assets/
│   ├── pronunciation.py           # Shared TTS pronunciation fixes
│   └── music/                     # Centralized podcast music (intro/outro)
│       ├── README.md              # Music generation guide + AI prompts
│       ├── tesla_shorts_time.mp3  # TST + EI + M&A theme
│       ├── fascinatingfrontiers.mp3     # FF intro jingle
│       ├── fascinatingfrontiers_bg.mp3  # FF background/outro
│       ├── LubechangeOilers.mp3         # OV theme
│       └── oilers-pride.mp3             # PT theme
├── tests/                         # pytest suite
├── .github/workflows/
│   └── run-show.yml               # Unified daily cron workflow (all shows)
├── *.rss                          # Podcast RSS feeds (consumed by Apple/Spotify)
├── *.html                         # GitHub Pages web players + summaries pages
└── docs/                          # Audit docs, storage plan
```

### Script Relationships


> **Per-show review history lives in**
> [`docs/show_review_history.md`](docs/show_review_history.md) — every
> dated quality-pass narrative (root causes, what was fixed, what was
> deferred), moved out of this file on 2026-07-29 so a session does not
> pay to load ~60 KB of history it rarely needs. The entries below keep
> each show's structural facts. Canonical write-ups:
> [`docs/reviews/`](docs/reviews/); scored predictions +
> `do_not_retry`: [`docs/reviews/ledger/`](docs/reviews/ledger/).

**Live constraints from those passes** (kept here because they bind
today's work, not just explain yesterday's):

- **SpaceX AI section:** the Colossus/Anthropic material is REAL — do not
  "correct" or relitigate it (operator-confirmed, June 13 2026).
- **Length levers are digest-side only.** Podcast-side expansion retries
  are banned network-wide (July 18 playbook `do_not_retry`: ~10 misses vs
  1 hit) and were switched off in the show YAMLs on 2026-07-29 wherever a
  digest-side lever exists. Chronic under-length on FF / PT / UC / Tesla /
  EI is a DIGEST ceiling — do not re-attack it at the script. The
  **publication-floor re-roll** (Aug 2026, `engine/generator.py`) is NOT
  that lever: it fires only inside run_show's 60%-of-target skip band —
  where the alternative is losing the whole day (Tesla Ep564 skipped
  2026-08-06; the identical 2026-07-31 skip was recovered by a manual
  rerun) — and regenerates the full prompt fresh instead of expanding the
  short draft. Guarded by `tests/test_podcast_floor_reroll.py`; do not
  remove it as a "banned retry", and do not widen it above the band.
- **De-seed by shape, never with a quotable example.** Every seeded
  template tic in this network's history came from a prompt supplying the
  literal sentence it wanted; three generations of them are in the
  archive. New prompt guidance describes the shape and bans the verbatim.
  **This applies to FORMAT specs too** (Aug 15 2026): a digest FORMATTING
  line showing the literal `**Title: Source Name**` was reproduced
  verbatim by the model for months (SpaceX Ep34→70 every ~5 episodes;
  on Ep70 every headline shipped as its PUBLISHER name). Never write a
  format template whose placeholder reads as plausible content —
  `engine/newsletter_sanitizer.py` scrubs the known label,
  `engine/chapters.py` strips it from titles, and `review_snapshot.py`'s
  "Digest heading integrity" section audits the canonical .md (the
  chapters JSONs are a downstream copy — four reviews scored the wrong
  surface).
- **The grok-4.3 narrative-length plateau is accepted** (operator
  confirmed; it resists escalation). Not a bug to re-open.
- **MIT is NOT ready for live trading** and its `execution/live.py` layer
  is dormant behind a kill switch. Two operator to-dos remain open:
  `scripts/recompute_mit_benchmarks.py --apply` (needs market-data
  access) and SnapTrade Phase-0 verification.
- **The MIT recompute was, until 2026-08-18, unsafe to run.**
  `_match_bar` scanned a window opening TEN DAYS BEFORE the pick and
  returned the FIRST bar inside the ±2% price tolerance, so the tool
  built to remove hindsight backdating re-created it — a live dry run
  flagged 25 trades, including all ten whose entry bars were already
  correct. Entries are now confined to bars on/after the pick, exits to
  bars on/after the entry, and the CLOSEST price wins over the first;
  the corrected run reports 0 backdated entries and reproduces 8 of the
  10 known-good windows exactly. **Never widen that window back, and
  validate any matcher change against those ten trades** — they are the
  only ones written by the trusted path. Corrected dry run:
  **−3.35% alpha across 42 trades**, beating 1 of 3 indices; 8 trades
  reconcile to no bar at all, and they include the record's best
  (+20.11% DLTR), second-best (+13.36% AMD) and worst (−11.80% MDA).
  `--apply` rewrites published performance numbers — operator's call.
- **MIT's simulated trading has a RULEBOOK and an ERA** (2026-08-18):
  [`shows/_trading_policy.yaml`](shows/_trading_policy.yaml) is the rules
  — entry at the first session open on/after the pick, exit at the stop
  or a FIXED 5-session horizon (flash: 1), $1,000, no discretionary
  exits — and the code reads it (`load_policy` / `horizon_sessions` /
  `era_inception`). Before this, the exit was not a decision: weekly
  holds closed on whichever bar the Friday pre-market run priced, so a
  Wednesday pick got one session and a Monday pick five, and per-trade
  alpha measured pick quality and pick weekday together. Alpha spoken on
  air is now the ERA record only (`era_*` in the summary, trades picked
  on/after the inception date); earlier trades stay published as history
  and are NEVER blended in. `_alpha_scope()` is the ONE selector both
  prompt blocks use — era → verified → blended — so a value and a label
  can never come from different sources again. The sim and
  `execution/shadow.py` both derive the holding period from the same
  policy; if they drift the shadow ledger stops being a check. Public
  methodology: [`docs/mit_trading_method.md`](docs/mit_trading_method.md).
  Drift guards: `TestTradingPolicy`, `TestEraScopedRecord`,
  `TestReproducibleDecisions`.
- **MIT trades options now, and the premium is never modelled**
  (2026-08-19). The show taught options in 32 of 40 episodes and had
  traded one in 0 of 61 positions. Covered calls and cash-secured puts
  are now real: the contract is quoted LIVE at pick time (listed strike,
  listed expiry, bid/ask mid) because a premium cannot be reconstructed
  afterwards from free data, and the position is held to EXPIRY where the
  payoff is arithmetic on the underlying close with no free parameters.
  **If the chain cannot be quoted the pick degrades to shares** and
  records `option_quote_failed` — never an estimated premium. Selection
  is by rule (nearest listed expiry 21-45d, strike closest to 4% OTM,
  ITM/unquoted skipped) so it is reproducible. Returns are on capital
  actually committed, which is what makes them comparable with a $1,000
  share position. Early assignment is NOT modelled and the prompts
  require saying so. Guards: `TestOptionsPositions`.
- **MIT's learned rules ROTATE, or the loop can never score any of them**
  (2026-08-20). Across the first 15 stamped trades only two rule sets
  ever existed, differing by one rule and only because the ledger
  happened to change — four of five rules were common to both, so no rule
  could be told apart from another and the (honest) scoreboard would have
  stayed silent forever while looking like a working feedback loop.
  `learning.rule_rotation` in [`shows/_trading_policy.yaml`](shows/_trading_policy.yaml)
  now shows a rotating subset (4 slots from a ~6-rule pool, cycling on
  the episode number, so it is reproducible from the trade record) which
  gives every rule BOTH a with-rule and a without-rule arm. A rule that
  demonstrates an edge is PINNED and stops rotating (`_proven_rule_ids`,
  >=5 trades on both arms); `always_on: true` pins by hand for
  safety-shaped rules. Do not "simplify" the selector back to
  most-recent-N — that is what made attribution impossible. Guards:
  `TestRuleRotation`.
- **MIT reports alpha by strategy FAMILY, not just by sector**
  (2026-08-20). 61 trades produced 61 unique free-text strategy strings,
  so "are our momentum entries better than our valuation screens" was
  unanswerable. `STRATEGY_FAMILIES` / `strategy_family()` is a closed
  vocabulary REQUIRED on new picks and DERIVED from the free text for
  history (unmatched => `other`, never forced). The block inherits the
  window discipline: verified-window trades when there are enough,
  otherwise labelled indicative-only and explicitly not for air. Guards:
  `TestStrategyFamilies`.
- **MIT accounts on air for the number that DISAPPEARED** (2026-08-20).
  Ep141-143 all announced the new era-scoped record; one of three said
  why, none pointed at the rulebook or ledger, and none mentioned the
  **+9.28% across forty-five trades** the show had been quoting — which
  simply stopped appearing. A strong figure that quietly vanishes is
  indistinguishable from one being buried, and here the truth is the
  opposite (it could not be reproduced, so it was not ours to claim).
  `_build_methodology_disclosure` is a SELF-RETIRING correction —
  `METHODOLOGY_DISCLOSURE_EPISODES = 3` airings, stamped as a list of
  episode numbers so a second `get_prompt_context` call in one episode
  cannot burn two, never consumed by read-only runs — and it is NOT a
  recurring changelog: do not extend it, and keep pipeline internals
  (rule rotation, review coverage, scoreboard mechanics) out of it. Its
  payload is the transferable skill, not the apology: the four questions
  that audit ANY track record (when did it start and was the date chosen
  after the fact; what is the exit rule and was it fixed in advance; are
  losers and abandoned positions included; are individual trades
  published or only the summary). The segment claims the rules and
  ledger are "published for anyone to check" — that claim was FALSE in
  practice until this pass, because `api/mit_trade_ledger.*` was built
  nightly and linked from nowhere; the performance page now carries a
  *Verify this record yourself* panel and a guard asserts the links and
  the files both exist. Prompt change => A/B-listen per landmine #17.
  Guards: `TestMethodologyDisclosure`.
- **The daily audit reviews late episodes on a CATCH-UP pass** — it runs
  at a fixed 16:15 UTC while shows finish anywhere from 09:32 to 19:41,
  and anything later was logged "critical: Missed episode" then
  auto-closed next day by confirming the FILE EXISTS, so its content was
  never reviewed at all (four shows on 2026-08-19; a 32-episode
  network-wide backlog at first run). `review_episodes.py` now reviews
  the previous 3 days' unmarked episodes, tracked in
  `api/review_coverage.json` (14-day prune, committed by daily-audit so
  the pass is idempotent), capped at 10/run oldest-first because the AI
  review calls Grok per episode. Guards: `TestReviewCatchUp`.
- **MIT's rule scoreboard must refuse to claim what it cannot measure.**
  It was emitting FIVE identical `RETIREMENT CANDIDATE` verdicts (same 10
  trades, same -0.17% vs +0.43%) because all five rules were stamped on
  exactly the same trades — perfectly collinear, one undivided sample
  reported as five findings — with the disowned pre-era trades as its
  control group. It is now era-scoped, refuses a verdict when the stamped
  rule set never varies, flags collinear rules as ONE piece of evidence,
  requires >=5 trades on BOTH arms, and says "not measurable yet" instead
  of going silent (silence is how the artifacts rode for weeks). Also:
  `_is_trading_rule` keeps production-hygiene lessons — re-teach
  cooldowns, "state the NASDAQ level", the sim's own data-fetch bugs —
  out of the pick prompt, and `_rule_core` dedups on the rule's
  constraint with its scope clause stripped. Guards:
  `TestRuleScoreboardHonesty`, `TestTradingVsPipelineRules`.
- **MIT's cold streak raises the bar on the pick, never on picking**
  (2026-09-18). The COLD regime text had called an explicit no-trade day
  "acceptable and unremarkable"; from Ep152 (08-28, the first episode
  after the era record turned negative) the show declared no trade on
  19 of 23 episodes, the drought valve fired weekly, its forced pick was
  voided (voided picks reset the valve) or closed into the same
  ten-trade window, and the window never turned over — 9 closed era
  trades in a month, nothing scoreable. Now `_build_regime_block`'s COLD
  text demands named factors, an invalidation level and a graded
  confidence but still expects a pick; `_days_since_last_pick` ignores
  voided picks; and `_no_trade_budget_block` allows ONE no-trade per
  five episodes, read from the committed `trade_signal_ep*.json`, with
  a spent budget making a pick mandatory. Register
  `mit-no-trade-budget-2026-09-18` (metric `mit_new_trade_share_10ep`,
  baseline 0.1). Prompt-context change — A/B-listen the first two
  episodes. Guards: `tests/test_mit_no_trade_budget_2026_09_18.py`.
- **The MIT trade ledger is public** (`scripts/build_mit_ledger.py` ->
  `api/mit_trade_ledger.json` + `.csv`, nightly): every trade with entry/
  exit bar dates, stop, horizon, invalidation, confidence, rules in
  effect and option contract. Voided picks and pre-era trades are
  INCLUDED and flagged — a ledger that drops its failures is marketing.
  Guards: `TestPublicLedger`.
- **Two functions speak MIT's alpha, and they must never disagree:**
  `_build_portfolio_summary` and `_build_benchmark_block`. The Aug 15
  pass fixed only the first, and because both reach the same prompt the
  model fused label and value — Ep138 aired "+9.28% across forty-five
  VERIFIED-window trades", the inflated number wearing the honest label.
  Fixing one of two call sites was worse than fixing neither. Same shape
  in the index sweep: its NASDAQ leg fell back to `nasdaq_return_pct`
  (45 trades) beside 10-trade S&P/TSX legs, and the July-18 `n>=5` gate
  missed it because it checks sample SIZE, not that the legs share the
  same TRADES. Guards: `tests/test_mit_benchmark_integrity.py`
  (`TestSingleAlphaSource`, `TestRecomputeMatcherCannotBackdate`).
- **MIT speaks the VERIFIED-window alpha, never the blended one**
  (Aug 15 2026 review:
  [`docs/reviews/modern_investing_review_2026_08_15.md`](docs/reviews/modern_investing_review_2026_08_15.md)).
  `matched_window_alpha_pct` compounds every trade with a
  `nasdaq_return_pct` — including the 35 whose windows the July-3
  integrity pass itself disowned, because the recompute above has never
  run. That blend put **+9.28% across 45 trades** on air while the 10
  pick-date-aligned trades were at **−1.95%**.
  `verified_window_alpha_pct` / `verified_window_trades` (trades carrying
  `entry_bar_date`) are the on-air numbers; the blended pair stays for
  the performance page and the recompute script. Running
  `recompute_mit_benchmarks.py --apply` collapses the split — do not
  "simplify" the two back into one before then. Same pass fixed three
  more silent-number failures: the digest FORMATTING template never
  listed `### Portfolio Performance` (missing from 13 of 20 episodes, and
  the script then told listeners the feed was down), `_build_trade_review`
  only examined `closed[-1]` so 43 of 50 closed trades were never
  narrated once the pick cadence went daily (now drains oldest-first,
  bounded by `REVIEW_BACKLOG_MAX_DAYS`), and the source-collapse alarm's
  10-episode rolling baseline decayed with the collapse it was watching
  (article median 274 → ~57 for three weeks; now a second long baseline
  catches a slide, and three hard-403 feeds were replaced). Drift guards:
  `tests/test_mit_benchmark_integrity.py`.
- **The lesson from that pass, network-wide:** loops that operate on TEXT
  fail loudly (a tic shows up in a snapshot); loops that operate on
  NUMBERS fail silently, because a wrong number looks exactly like a
  right one. Any watchdog whose baseline is a rolling window of the thing
  it watches can only catch a cliff, never a slide.

- **FF and PT** are "nearly identical twins" — same structure, same functions,
  different news topics and X account
- **TST** shares most patterns with FF/PT but adds: complex pronunciation
  fixes, content tracking, chunked TTS, x_search stock data, TST-specific
  emoji formatting via `engine.publisher.format_tst_digest_for_x()`
- **OV** is structurally different — different TTS approach (no streaming, uses
  env vars for voice settings), simpler functions.
- **EI** runs exclusively via `run_show.py` + `shows/env_intel.yaml`; no legacy script.
- **M&A** (Models & Agents) runs exclusively via `run_show.py` +
  `shows/models_agents.yaml`; no legacy script.
- **MAB** (Models & Agents for Beginners) runs via `run_show.py` +
  `shows/models_agents_beginners.yaml`; beginner/teen-focused version of M&A.
  On the custom Grok voice `kdif6sqjcyiq` (inherits `_defaults.yaml`; the old
  "ElevenLabs" note was stale per landmine #17). X posting disabled.
- **FP** (Финансы Просто) runs via `run_show.py` +
  `shows/finansy_prosto.yaml`; Russian-language financial literacy podcast
  for women in Canada (even days only). Uses **Grok TTS** (Olya voice
  `0b875ae2`, `language_code: ru`). All content generated in Russian. X posting disabled.
- **MIT** (Modern Investing Techniques) runs via `run_show.py` +
  `shows/modern_investing.yaml`; daily investing podcast focused on Canadian
  and US markets. Weekdays only. X posting disabled.
- **PR** (Привет, Русский!) runs via `run_show.py` +
  `shows/privet_russian.yaml`; bilingual Russian language learning podcast
  for English speakers. Even days only. Uses **Grok TTS** (custom Olya voice
  `0b875ae2`, `language_code: ru` — `shows/privet_russian.yaml`). X posting
  disabled.
- **FPD** (First Principles Daily) runs via `run_show.py` +
  `shows/first_principles.yaml`; a **daily narrative** show
  (`narrative_mode: true`, topic-queue-driven like UC — no news fetch).
  Applies the first-principles "magic wand number" + "Idiot Index" lens,
  alternating per episode between a concrete example of the thinking in
  action (`category: concrete_example` — historical and modern: Ford,
  Bessemer, containerization, solar, batteries, mRNA, and *sometimes*
  Musk's teams, deliberately not Musk-only) and an industry ripe for it
  (`category: opportunity_area`); Ep1 is a combined debut. Patrick voice
  (inherits Grok `kdif6sqjcyiq`). Distribution OFF at launch (no newsletter,
  no X, no YouTube). Queue: `shows/topic_queues/first_principles.yaml`.
- **UC** (Unintended Consequences) runs via `run_show.py` +
  `shows/unintended_consequences.yaml`; a weekday **narrative** show
  (`narrative_mode: true`, topic-queue-driven — no news fetch). Patrick
  voice. X posting on via the @planetterrian account.
- **SpaceX** (SpaceX Daily) runs via `run_show.py` + `shows/spacex.yaml`;
  engineering-first daily on SpaceX as a public company (Nasdaq: SPCX),
  `memory_enabled`, X disabled. Has a **manual-force-only deep-dive queue**
  (`shows/deep_dives/spacex.yaml`, `deep_dive.enabled: false` so the daily
  cron never scans it): `python run_show.py spacex --deep-dive <id>` runs a
  standalone special through the spacex_deep_dive prompts (first entry:
  `q2-2026-earnings`, the Q2 2026 earnings special, Aug 2026).
- **DP** (The DP Pod: The Do Positive Podcast) runs via `run_show.py` +
  `shows/dp_pod.yaml`; the network's **two-host dialogue** show (July 2026
  launch) — Dan Perra + Patrick Novak, weekly (Monday) ~10 min of good news in
  science/tech plus one individual action with honest numbers ("The Lever"). Segments:
  Cold Open → The Positive Papers → The Lever → Do Positive Dispatch →
  sign-off "Do something about it." **WEEKLY on Monday since 2026-09-21** (operator-directed; was daily all 7
  days). It is in `ALT_CADENCE_SHOWS` in `tests/test_schedule.py`, never
  `DAILY_SHOWS`, and carries no Sunday recap. The cadence lives in six
  places that must agree — CRON_MAP, the scheduler Worker's SLOTS,
  `review_episodes.py`'s registry, daily-audit's RSS freshness limit,
  `engine.daily_edition`'s `monday_only`, and the public `schedule` string
  — and `tests/test_dp_pod_weekly_2026_09_21.py` pins all six.
  First show on the **two-voice dialogue TTS path**: `tts.dialogue_mode: true`
  + `tts.dialogue_voices` (`PATRICK: kdif6sqjcyiq`, `DAN: 0vscf8u8yrxc`) make
  the pipeline preserve `DAN:`/`PATRICK:` speaker labels (three legacy
  prefix-strippers are gated on the flag — `engine/generator.py`
  `_sanitize_podcast_script`, run_show's `_clean_podcast_script` + final
  defense strip) and synthesize per-speaker via `engine/tts_dialogue.py`
  (turn-group parsing, per-group Grok calls, pause padding, shared WAV
  crossfade → single MP3 encode). Dialogue mode NEVER applies the `<fast>`
  wrap (per-turn wraps are the landmine-#17 leak shape ×30 handoffs) and
  supersedes section-TTS. An unlabeled script falls back to single-voice
  `tts.voice_id` with a loud warning + `dialogue_fallback_single_voice`
  metric. Show page is `thedppod.html` (registered via
  `shows/network_meta.yaml` `show_page` override). RSS + site only at launch
  (X/YouTube/newsletter/multilingual off). Drift guards:
  `tests/test_tts_dialogue.py` (engine; existing shows pinned to
  `dialogue_mode is False`), `tests/test_dp_pod_show.py` (launch shape).
  Prompt edits change shipped audio — A/B-listen per landmine #17; the first
  episodes are the calibration set for `dialogue_pause_ms` handoff pacing.
  **Aug 10 2026 quality pass** (review:
  [`docs/reviews/dp_pod_review_2026_08_10.md`](docs/reviews/dp_pod_review_2026_08_10.md);
  drift guards: `tests/test_dp_pod_show.py::TestLeverRotationMemory`): The
  Lever had converged into week-long identical runs (heat-pump assessment
  ×7 straight, Ep24–30) — the July-9 PREVIOUS LEVER injection was the only
  lever the model saw and both prompts named quotable examples. Fixed with
  data-side rotation memory (`_recent_levers()`, 15-episode window) + full
  de-seed by shape; do NOT reintroduce example actions into the lever/
  dispatch prompt text. Scripts also pasted the brief verbatim (Ep22 65%
  shingle overlap) with zero exclamations in 27/30 episodes, so dp_pod is
  the network's first `llm.podcast_model: grok-4.5` script-stage A/B
  (experiment `dp-pod-script-model-45`, readout 2026-08-24; digest stays
  grok-4.3; revert = delete the line). Digest format spec was raised
  (Papers 6–8 sentences, Lever 6–9) because 2–3×4–6 arithmetically capped
  digests below their own 1100-word floor. **Same-day operator follow-up
  (Aug 10):** `newsletter.enabled: true` (daily briefing now real; email
  replies are the Dispatch submission channel, named on air, on the club
  page, and in the join fine print — "two honest sentences count"), and
  the catalogue was PRUNED 30 → 11 episodes (operator-directed): all
  repeated-lever episodes and high-verbatim-paste episodes removed from
  RSS/summaries/blog/site (kept 1, 2, 3, 8, 9, 11, 15, 19, 21, 24, 30 —
  each with a distinct lever; Ep30 stays partly because RSS `<itunes:
  episode>` max pins `get_next_episode_number` at 31, so the purge can
  never renumber future episodes into published GUIDs). R2 MP3s of
  deleted episodes were NOT removed (no credentials in the session;
  harmless — unreferenced). `metrics_ep*/credit_usage_*` files kept as
  real spend accounting. Still open: `dispatches.json` is empty until a
  real listener/host dispatch is seeded.
  **Sep 4 2026 naturalness pass** (review:
  [`docs/reviews/dp_pod_review_2026_09_04.md`](docs/reviews/dp_pod_review_2026_09_04.md);
  drift guards: `tests/test_dp_pod_show.py::TestSep4NaturalnessPass`):
  the Aug-10 renewal scored 3 hits / 1 miss on 26 shipped episodes
  (verbatim paste ~30% → ~3% median; the grok-4.6 script stage adopted
  Sep 1). Successor tics, all fixed data-side: the Lever converged on
  the "Open your <website> today…" SHAPE (13/26; 21/26 screen lookups) —
  `_recent_levers()` now collapses fuzzy re-skins and computes BANNED
  OPENING VERBS + REAL-WORLD ACTION DUE from the last six levers; the
  prompt's own comedy examples calcified ("checklist" 23/26, "steel-man"
  23/26) — `_recent_banter_phrases()` mines RETIRED BITS from the last
  six scripts (furniture-excluded) and the comedy/dynamic examples were
  removed by shape; the founders' notes went unused (Yukon 0/26) —
  `_founders_detail_nudge()` fires only after five real-material-free
  episodes. Episodes ran 11–14 min against a ten-minute promise → HARD
  CEILING 1,750 words. Two closings double-asked for dispatches (one
  claimed "we read every dispatch" with zero ever received) → mission
  lines instead. **YouTube ON, Shorts-only** (experiment
  `dp-pod-youtube-shorts`; long-form waits on the adaptive policy).
  `review_snapshot.py` crashed on any show without
  `exclude_title_patterns` — fixed. Do NOT re-add example actions,
  example jokes, or example concession phrases to either prompt: three
  generations of this show's tics came from exactly that.
- **AOAI** (The Age of AI) — the network's **AI-hosted LIVE interview show**
  (July 2026): Mira, an AI documentarian persona (Grok voice `ara`,
  deliberately NOT the Patrick clone), interviews REAL guests live through a
  Voximplant scenario bridged to a Grok Voice Agent, dual-track records the
  conversation, and the episode is produced from the real recording.
  **Since 2026-09-09 every interview is a ROOM** — the guest (and an optional
  co-host) joins from `age-of-ai-studio.html`, picks a mic and presses Join,
  and the **outbound PSTN call is the FALLBACK mode**, not the default. An
  earlier version of this paragraph said Mira "phones" guests, and that claim
  had also reached `engine/brand.py` as the BASIS of the network's
  first-of-its-kind claim; corrected 2026-09-20. Do not describe the show as
  a phone-call show on any surface. **Production does NOT go
  through run_show** — `shows/age_of_ai.yaml` exists for registry/publish
  surfaces only, and its narrative mode + permanently-empty topic queue make
  an accidental `run_show.py age_of_ai` a clean `narrative_queue_empty` skip.
  The real pipeline is **Nerra Voices**: `pipelines/voices/` + the five
  `nerra_voices_*.yml` workflows + `workers/voices/` (webhooks, Mira's 3
  in-call tools, triage/review UIs — Cloudflare Worker at
  `api.nerranetwork.com/voices/*`, a documented deviation from the spec's
  Vercel sketch) + `supabase/migrations/20260704_nerra_voices_schema.sql`
  (separate Supabase instance; 6 tables are the state machine) +
  `voximplant/scenarios/age_of_ai_interview.js` (the central glue: outbound
  PSTN → Grok Voice bridge → stereo recorder → hangup webhook; 50-min hard
  cap). Flow: apply form → Patrick triage (~30 s) → Cal.com booking → T-1d
  LLM prep brief emailed to guest → T-2h SMS → fire (5-min cron,
  drift-tolerant window, idempotent) → live call → post-processing (R2, mix,
  per-channel Whisper STT — the stereo tracks ARE the diarization, 8
  schema-validated editorial passes) → **gate 1: Patrick editorial review
  (never times out into publish)** → **gate 2: guest transcript approval
  (day-4 reminder, day-7 auto-approve; redactions cut from audio FIRST at
  assembly)** → Mira narration TTS + ffmpeg assembly + waveform video →
  publish via the standard `engine.publisher` surface. Guest words are
  verbatim; every episode discloses the AI host. Spec-as-implemented +
  operator bootstrap (Voximplant/Supabase/Cal.com/Worker provisioning +
  phase-1 smoke test): [`docs/age_of_ai_plan.md`](docs/age_of_ai_plan.md);
  drift guards: `tests/test_age_of_ai_show.py` (registry no-op shape, spec
  artifacts, dispatch-event coherence, validators, the two human gates).
  **Distribution (2026-09-20, operator-directed): newsletter + YouTube ON,
  X still posted by hand from @nerranetwork, multilingual off** (a dub of a
  guest's own recorded voice is a different consent question, not a config
  flip). Those two flags had been read by NOTHING until this date — the
  interview shows bypass `run_show.py`, where every other show's newsletter
  send and YouTube upload live, so flipping them looked like enabling
  distribution and did nothing, the same class as the OP3-prefix hole.
  `pipelines/voices/publish_episode.py` now reads them:
  `maybe_send_newsletter` reuses `engine.newsletter.send_show_newsletter`
  (so the sanitizer, the contrast check and the 20-hour double-send guard all
  apply) and `maybe_publish_youtube` uploads the waveform MP4 the produce
  step already renders — long-form only, no Shorts/thumbnails/dubs/policy
  tier, recorded in `digests/age_of_ai/youtube_videos.json` so the analytics
  fetcher and the adaptive policy see it. Both run AFTER the rows flip to
  `published` and swallow their own failures: the audio in the feed is the
  product. The video URL is DERIVED from the audio URL
  (`waveform_video_url` — `<prefix>/video/<name>.mp4`) and HEAD-checked,
  because the produce step only ever put it in an email. Any new show that
  bypasses run_show inherits this hole; wire its distribution explicitly.
  **Oct 15 2026 — Grok Voice 3.0 (register `grok-voice-3-2026-10-15`;
  guards `tests/test_grok_voice_3_2026_10_15.py`).** 3.0 is the
  speech-to-speech model behind the Voice Agent API — Mira's live room — and
  NOT the `/v1/tts` endpoint the shows synthesise through, which has no model
  id (the shows are untouched). The `grok-voice-latest` alias moved to 3.0 on
  Oct 14 and 2.0 is deprecated, so Mira was upgraded by the alias before any
  change here; **the model is PINNED now** (`grok-voice-3.0` in
  `voximplant_client.DEFAULT_GROK_VOICE_MODEL` and the scenario fallback;
  `GROK_VOICE_MODEL` overrides) — xAI's production guidance and the network's
  floating-alias rule; the next version is adopted after a rehearsal. From the
  3.0 docs: the scripted narration read runs `reasoning.effort: "none"`, the
  live interview pins `"high"`; the fire step writes `interview_runs.keyterms`
  (guest, organisation, title, show, network, hosts; migration
  `20261015_interview_runs_keyterms.sql`, applied Oct 15) and the scenario
  sends them as `audio.input.transcription.keyterms` — an insert on a database
  without the column retries without it; Mira's prompt is reorganised under
  xAI's recommended H2 order (Role & Persona / Objective / Conversation Flow /
  Guardrails & Escalation / Voice & Communication Style / CRITICAL
  INSTRUCTIONS) with every earlier paragraph kept verbatim (⚠️ AUDIO — the
  first interview is the listen; the guide's trim to a shorter prompt is the
  next A/B, not this one). `idle_timeout_ms` and `resumption` were read and
  NOT adopted: the first conflicts with the hold-the-silence rule, the second
  needs the Voximplant connector to pass `conversation_id`. Operator: run the
  scenario deploy workflow so the pin and the session settings go live.
- **NDaily** (Nerra Daily) — the network's **combined daily edition**
  (Aug 2026): one ~2 h episode/day that SPLICES the day's already-published
  English episode MP3s (pulled back from R2) with short Mira host links
  (Grok voice `ara`) between them — operator-set fixed rundown (SpaceX →
  Tesla → FF → M&A → Planetterrian → Omni View → the rest), DP Pod
  closes; Monday adds EI + Offshore North. Mira also speaks a midpoint
  **field note** — one web-search-grounded item of her own, own chapter,
  honest-SKIP on unverifiable days (`shows/prompts/nerra_daily_find.txt`). **Not a run_show show and it
  must never become one**: registry entry in `shows/network_meta.yaml`
  only (no `shows/nerra_daily.yaml`, deliberately — that keeps it out of
  the review rotation and every shows-glob consumer), assembled by
  `scripts/build_daily_edition.py` + `engine/daily_edition.py`, workflow
  `.github/workflows/nerra-daily.yml` (workflow_run after each Run Podcast
  Show + ready gate: builds minutes after the last expected show lands;
  ≥12:00 UTC sweeps build with whatever published (12:00 force hour +
  the scheduler Worker's 12:07 dispatch land straggler days ~5:40am PT
  — Aug 2026 pass); committed summaries
  entry per date = idempotency key). **Each segment's baked-in outro tail
  (network sibling plug → surface plug → AI disclosure) is trimmed via
  the committed Whisper word timestamps** (`find_promo_cut` — fuzzy on
  Whisper's brand spellings, anchored on the four `network_promo` frames;
  no match = segment ships whole, never a guessed cut) and Mira speaks ONE
  network-level AI disclosure at the end — the standalone feeds keep their
  plugs untouched. Marginal cost ≈ one small Grok call (links, grok-4.3) +
  ~4k TTS chars + one R2 upload (`nerra_daily/` keyspace) — no content
  regenerated. Mira's link LLM output is JSON-validated with a
  deterministic titles-based fallback; her Age of AI self-reference
  rotates by date and a new AOAI episode is plugged, never spliced.
  Editions are language-parameterized (`EditionSpec`) for future RU/FR.
  Surfaces at launch: own RSS (`nerra_daily_podcast.rss`, exact spliced
  chapter markers), show page, daily rundown blog (links into each show's
  post — never duplicates their digests). Docs:
  [`docs/nerra_daily.md`](docs/nerra_daily.md). Drift guards:
  `tests/test_daily_edition.py`.
  **Sep 3 2026 second pass** (review:
  [`docs/reviews/nerra_daily_review_2026_09_03.md`](docs/reviews/nerra_daily_review_2026_09_03.md)):
  the metrics file caught a **P0** — the one non-`promo` cut it ever
  recorded was DP Pod Ep52 losing its Dispatch and sign-off (69 s) in
  Ep10: Whisper writes "sister shows"/"sisters show", the frame regex
  wanted the singular, and the weak brand-mention fallback matched the
  Dispatch's own "show page at nerranetwork.com". Fixed (`sisters?
  shows?` + `WEAK_EVIDENCE_MAX_TAIL_SECONDS` 60 s ceiling on any
  non-frame cut; 210/210 recent transcripts trim on frame evidence and
  `TestPromoCutHardening` sweeps them all in CI — **extend the matcher
  for a new Whisper spelling, never lean on the fallback**). **Sep 17 2026:** the scripted YouTube call-out ("rather watch
  than listen", `engine.intros`) is a frame-grade anchor when the outro
  follows it (`anchor: youtube_lead`, 60 s ceiling) — MIT Ep171's model
  dropped frame 2's sibling sentence and Whisper wrote nothing for 22 s
  of DP Pod Ep069's plug; the edition metrics record `cut_anchor`. Rotation
  memory v2: the date defeated the Aug 25 opener memory (5/9 intros were
  "<date> opens Nerra Daily…"), so openers are date-normalized, and the
  sign-off ("Across these segments" 7/9) and field-note closer
  ("quietly" 10/13 — seeded by BOTH prompts' register lines) got their
  own memory blocks + shape de-seeds (A/B-listen). Every edition had
  been titled with SpaceX's hook (lead show) — the links call now writes
  a validated whole-day `title` (metadata only; experiment
  `nerra-daily-edition-titles`); show notes carry chapter timestamps +
  the field note; `podcast:person` credits Mira. Same-day follow-up: the
  ready gate reads the committed `.skip_<date>.json` marker
  (`discover_lineup` → `skipped`, metrics `skipped_today`) and no
  longer waits for a show that skipped — a UC gate-block had held the
  edition to the 12:00 force hour (12:09 / 12:41 vs ~08:13 on complete
  days). Open operator item: UC's claims-gate retry lands after the
  edition, so a gate-blocked UC never makes that day's edition.
  **Oct 2 2026 — every English show, and a gate that waits.** Ep043
  shipped at 39 min with FOUR segments: the morning flagship wave had been
  diverted into recovery branches (every show run rewrote the new
  `claims.html`; the commit step cannot three-way merge generated HTML —
  P0 fixed the same day: the per-show regen writes only its own
  `claims/<slug>.html`, the network page belongs to `--network` /
  `--static-pages`, and `push_show_artifacts.sh` lists both as
  regenerable). Operator direction: the thirteen launch-cohort shows are
  IN the lineup (26 shows; `weekday_only` for Longevity/Peptides/
  Collingwood; a weekday roster is 21–23; Nerra Personal's vocabulary is
  the roster again). The ready gate is `engine.daily_edition.ready_decision`
  (pure, tested); its 13:00 UTC force hour was replaced on Oct 8 (below).
  The links `max_tokens` scales with the handoff count. ⚠️ AUDIO:
  Mira's handoffs triple — A/B-listen the first edition. Register
  `nerra-daily-full-lineup-2026-10-02`; guards
  `tests/test_nerra_daily_full_lineup_2026_10_02.py`.
  **Oct 8 2026 — the edition goes out at 8:00 AM Pacific, after every
  show (operator-directed).** `ready_decision` reads PACIFIC wall time
  (`RELEASE_PACIFIC` 07:50 — a build takes 6-7 min — and
  `HOLD_UNTIL_PACIFIC` 09:00, `release_window()`): before 07:50 it waits
  whatever has landed; then it builds once every expected show has
  published or skipped; a straggler is held for until 09:00 (it builds the
  edition itself through `workflow_run`), then the edition builds with what
  exists. No 80% floor — the point is a full slate. Never express the
  release as a UTC hour: 07:50 PT is 14:50 UTC under PDT and 15:50 under
  PST. The Worker's `EDITION_DISPATCH` fires at 07:50 and 09:01 Pacific
  from the Worker's ONE cron trigger (`"1,7,16,31,37,46,50 6-17 * * *"`,
  shared with the show slots — Oct 9 2026: the Cloudflare account was then
  on Workers Free, five cron triggers in total, Voices held three, and the
  deploy with a second scheduler trigger was refused with code 10072, so
  the edition dispatch had never gone live; the account is on Workers Paid
  since, see the Oct 9 runner note) and converts to Pacific
  in the handler; GitHub fallbacks 14:55/15:55/16:05/17:05 UTC. Every
  lineup slot lands by ~12:40 UTC, two hours ahead (guarded). Nerra
  Personal follows the edition to ~8am. **A show run's push resolves a
  `blog/<show>/*.html` conflict by keeping its own render**
  (`push_show_artifacts.sh`): on Oct 7 the multilingual sweep re-rendered
  Fascinating Frontiers' posts mid-run, FF / First Principles / SpaceX went
  to recovery PRs #1376-#1378, the late GitHub cron produced FF and FPD a
  second time, and the edition shipped without all three. Operator:
  `wrangler deploy` in `workers/scheduler`. Register
  `nerra-daily-8am-pacific-2026-10-08`; guards
  `tests/test_nerra_daily_8am_pacific_2026_10_08.py`,
  `tests/test_push_show_artifacts.py::TestTheBlogCollision`.
  **Aug 25 2026 first quality pass** (review:
  [`docs/reviews/nerra_daily_review_2026_08_25.md`](docs/reviews/nerra_daily_review_2026_08_25.md);
  ledger `docs/reviews/ledger/nerra_daily.yaml`): audio core verified
  healthy (promo cut 44/44 segments, all `kind=promo`), but the
  periphery wasn't — every blog post titled itself with the italic
  byline (fixed: the rundown now emits the `> **<hook>**` blockquote
  via `edition_hook()`, `engine/blog.py` skips full-italic bylines,
  four rundowns backfilled), and **being a virtual show made it
  invisible to every shows-glob loop**: OP3 never resolved its feed
  (fetcher now reads registry-only shows from `network_meta.yaml` —
  `_virtual_show_targets`), the dashboard cost rollup missed its
  credit files (`_VIRTUAL_COST_SLUGS`), and no per-build record
  existed (now `metrics_ep*.json`: cut kinds, `missing_expected` —
  Offshore North published 17:04 on Monday 2026-08-24, after the
  15:07 force-build, and the miss was uncountable). A new virtual
  show must be added to those two lists or it repeats the hole.
  Mira's handoffs now commit into the rundown .md (tic-detection
  substrate + unique blog prose), and both prompts gained data-side
  rotation memory (`{recent_openers}` / `{recent_field_notes}` — all
  four intros had opened "Good morning."). Launch registered as
  experiment `nerra-daily-launch` (readout 2026-09-22; needs the
  Apple/Spotify submission from the operator checklist).
- **ON** (Offshore North) runs via `run_show.py` + `shows/offshore_north.yaml`;
  the network's **weekly offshore ocean-racing show** (Mondays; Dan on
  `0vscf8u8yrxc`, single-narrator, `memory_enabled`). Spine: Canada Ocean
  Racing / Scott Shawyer / EMIRA IV (CAN 80) toward the Route du Rhum
  (1 Nov 2026, entry confirmed) and the Vendée Globe (12 Nov 2028).
  Prompts carry two included files — `offshore_north_standing_facts.txt`
  (authoritative campaign background, reviewed monthly, with a "standing
  corrections" list of errors already aired) and
  `offshore_north_field_guide.txt` (the sport's map). **Sep 14 2026 review**
  (doc: [`docs/reviews/offshore_north_review_2026_09_14.md`](docs/reviews/offshore_north_review_2026_09_14.md);
  ledger `docs/reviews/ledger/offshore_north.yaml`; guards
  `tests/test_offshore_north_review_2026_09_14.py`): **the digest prompt had
  never seen an article** — headline + feed teaser + URL only — so Ep002–005
  aired the boat's position as "unconfirmed" while the team's 2 Sep post
  said it was heading back to Europe, reported WHEN channels changed rather
  than WHAT they said, spoke the writer-only "standing facts" label, and
  Ep005 aired a race START headline (Google-News re-surfaced) as the RESULT
  of a race that had finished with a different winner. Now:
  `engine/article_text.py` + `fetch_full_text: N` (**opt-in per show; 0 =
  every other show byte-identical**) renders each article's FULL TEXT under
  its headline — WordPress `content:encoded` bodies are stored on every
  article as `content_text` with no HTTP, pages are fetched for the rest,
  campaign feeds first; the freshness block carries a "What it said"
  excerpt + URL; Scott's Notes (the skipper's own writing — a WordPress
  PAGE whose `/feed/` is the COMMENTS feed; the `scotts-blog` category feed
  is the real one) is a flagged campaign source. Editorial rules that now
  bind (all landmine-#17 — A/B-listen the first episode): last-known
  position + the DATE of the fix, never "unconfirmed"; the Canadian Boat is
  FIRST and LONGEST; incidents not leaderboards, one sentence max on a
  leader, no roll-calls; never "standing facts/item" on air and the boat's
  pedigree at most once in four weeks; Plain Sailing EVERGREEN (never a
  same-episode race recap); EXACTLY ONE Dan reference per episode (the
  brief's writer-only "Dan's lens" line names it); a finish inside the
  window outranks a re-surfaced start. Blog footer placeholder is
  cadence-aware (`engine.blog.next_episode_placeholder` — "New episode
  Monday", never "tomorrow" on a weekly show). **Public campaign
  dashboard** `offshore-north-dashboard.html`
  (`generate_offshore_north_dashboard`; curated
  `site/data/offshore_north_dashboard.json` + live
  `api/offshore_north_dashboard.json` from
  `scripts/fetch_offshore_north_dashboard.py`, refreshed nightly and by the
  show hook after each episode; both committing workflows whitelist the
  pair): countdowns, last known position with date + source, the team's
  YB tracker, latest team posts with excerpts, headlines, spec, calendar,
  results, the Route du Rhum IMOCA entry list, qualification ledger,
  lineage, and every source/social the show reads. A new dated position
  fix goes in the curated file's `position_log`; never guess one.
  **Sep 18 2026 round-1 fixes** (operator list on Ep005; guards
  `tests/test_offshore_north_round1_2026_09_18.py`): the campaign's four
  feeds carry `window_hours: 720` (`SourceConfig.window_hours` — a
  per-feed cutoff that may look FURTHER back than the ladder, never less;
  a campaign does not generate news weekly and Ep005 reported the boat
  still in Canada from an empty 7-day window); `stale_article_days: 10`
  drops any article whose PAGE publish date (`engine.article_text.
  extract_published_date`, read during the full-text fetch — OpenGraph
  meta, JSON-LD, `<time>`) or feed date is older than ten days before the
  prompt sees it (`drop_stale_articles`; `window_hours` feeds exempt;
  undated pages kept; metric `articles_dropped_stale`), because Google
  News re-surfaced the 1 Sep race START under a 12 Sep index date and
  Ep005 aired it on the 14th; timestamp sentences ("last updated on…",
  "no new posts inside the window") are banned and the prompt line that
  produced them is gone; the labelled background block is deleted, not
  renamed; a RACE STATE CHECK precedes any race sentence; Plain Sailing
  is a HARD 300-word cap, one point made once, never the lead story's
  subject, and no longer a length lever; class names come from the
  official race site — the 2026 Route du Rhum's six are ULTIM, Ocean
  Fifty, IMOCA, Class40, Vintage Multi, Vintage Mono (formerly Rhum
  Multi / Rhum Mono). Host voice and the incident-driven Fleet rewrite
  are deferred at the operator's direction.
  **Sep 19 2026 resource pass** (§7 of the review doc; guards
  `tests/test_offshore_north_resource_2026_09_19.py`): **the campaign
  record is ONE file** — `site/data/offshore_north_dashboard.json` is
  baked into the dashboard AND rendered by `engine/offshore_north_status.py`
  into a dated CAMPAIGN STATUS block (`{campaign_status}`, hook-supplied,
  defaulted to "" in run_show + `engine.pipeline`) in both prompts: newest
  dated fix + its age, each countdown's NOT STARTED / RUNNING / FINISHED
  state by the clock with EMIRA IV's entry, results on record, the Rhum
  entry count, the countdown as arithmetic. Update the record (dated,
  sourced) and both surfaces follow; never hand-write a date into the
  prompts. A verified ABSENCE (EMIRA IV was not among the 14 at the 48H
  Azimut) is a `position_note`, never a position. The **Plain Sailing
  glossary** (`offshore-north-glossary.html`, `site/data/offshore_north_glossary.json`,
  55 hand-written sourced entries + the aired-explainer archive with
  `#t=` audio deep links, titles via `engine.titles.PLAIN_SAILING_TITLE_MAX`)
  is linked from the show page, the dashboard and every ON blog post
  (`engine.blog.SHOW_RESOURCES`). Dashboard v2 adds an "In the press" rail
  (the show's GN query resolved to publisher URLs), calendar state pills,
  the Défi Azimut result and the Rhum entries' 48H form. (The Sep 19
  probe that found "no JSON endpoint" on the YB tracker read only the
  HTML — see Oct 4 below.)
  **Round 2, same day:** countdowns and results are linked by key
  (`results_key` ↔ `key`) and a FINISHED race with no result entry gets
  "RESULT NOT YET ON RECORD" in the status block and "result pending" on
  the calendar — add the result entry, never a placing from memory. The
  **fleet guide** is parsed nightly from each Rhum entry's imoca.org boat
  page (`imoca_slug` on the entry; `parse_imoca_boat_page`; a failed page
  keeps the last good record, marked `stale`), the **cast** panel is
  twelve one-fact identifiers from the record, the **map** (Leaflet from
  cdnjs + OSM tiles) plots only the dated PLACES a team post named — an
  entry without `lat`/`lon` gets no marker — and the show page carries a
  campaign strip from the same record.
  **Oct 4 2026 — the position is the tracker's, and five operator rules**
  (guards `tests/test_offshore_north_tracker_2026_10_04.py`). The YB
  tracker page is a script app over a public API the page itself calls
  (`app.yb.tl/APIX/Blog/GetEvents` / `GetPositions`, keyword `emira4`);
  `engine/yb_tracker.py` reads it nightly (dashboard fetch) and FRESH in
  the show hook, and the fix is also a hook ARTICLE so the claims gate can
  verify the position sentence. Rules that bind: the base is **Gosport,
  UK (Portsmouth Harbour)**, never Brittany/Lorient (a place is named only
  inside `campaign.tracker.places`, else coordinates); a position always
  carries its date and source; a fix older than **7 days** is "last seen
  <date>", never the present tense (`yb_tracker.STALE_DAYS`); only the
  tracker's dated outings are spoken — never "training solo in Europe";
  the Route du Rhum is **"aiming to start"** until the official entry list
  carries Scott (`rhum_entry` in the record — the Sep 19 "Entry CONFIRMED"
  read the IMOCA class page, not the official list). **Instagram is read,
  never copied** (`engine/instagram_source.py`, Meta Business Discovery):
  captions + permalinks become dated source articles and a dashboard rail;
  pictures reach a reader only as Instagram's own embed, loaded on a click
  (the privacy policy says so); `media_url` is never requested. Secrets
  `INSTAGRAM_GRAPH_TOKEN` / `INSTAGRAM_GRAPH_USER_ID` — deliberately not the
  Shorts publisher's `IG_*` names; unset = a clean no-op.
- **Vancouver Daily News / Collingwood Weekly** (Sep 2026, pre-launch) — the
  first run_show shows with an AI host: `host_kind: ai`, Mira on `ara`, NO
  speech wrap (Nerra Daily's Mira has none). Roads and weather arrive as
  sourced hook ARTICLES from `engine/local_conditions.py` (DriveBC boxed to
  Metro Vancouver, Ontario 511, Environment Canada's `/rss/weather/` feed);
  a data-less day is one sentence. **Every new show runs grok-4.7** on its
  writing stages and includes `_shared/interesting_first.txt` (operator
  brief 2026-09-23; plan §9b; the established shows stay on grok-4.3).
  Guards: `tests/test_new_shows_phase2_2026_09_23.py`. **grok-4.7 had
  never completed a call here** (Vancouver/Collingwood Ep1 died in the
  digest stage, 2026-09-23): a pinned model that fails the pre-flight ping
  or the digest call now switches the run to grok-4.3 and records
  `llm_model_pinned` / `llm_model_fallback` — read those before scoring
  the 4.7 experiment (`engine.generator.switch_to_network_default`).
  **Sep 24 2026 — 9 of the cohort's first 24 episodes fell back, and the
  fallback arm is the thin one** (0–3 claims and ~1 comma per 100 words
  against 8–25 claims on a completed 4.7 run): five dropped connections
  at ~260 s on a NON-STREAMING request, three full 600 s timeouts, one
  pre-flight ping run at default effort. Two of the drops hit the
  STRUCTURAL RETRY of a good 4.7 digest and the sticky switch replaced it
  with a 4.3 one (Top World Ep2: 1,548 → 908 words). Now, per
  `docs/model_upgrade_playbook.md` rule 7: the cohort's calls STREAM
  (`llm.stream`; a stall is silence past `NERRA_LLM_STREAM_IDLE_SECONDS`,
  the request timeout a wall between chunks; false = the exact old request
  on every established show), a pinned model gets ONE budget-gated
  same-model retry before the switch (`engine.generator._call_pinned`,
  `llm.pinned_model_retries`; a 5xx never retries), a retry of an existing
  digest runs with `allow_model_switch=False` and keeps the original
  (`PinnedModelUnavailable`), the ping sends the show's effort with two
  attempts on a pin, and Progress Watch is exempt from the overlap dedup on
  the six Mira desks. Dashboard `llm_pinned_fallback_share_7d` (baseline
  0.38) is the readout; `tests/test_grok47_resilience_2026_09_24.py`.
  **Same evening: Top World Ep2 had shipped eleven items and NO Source line**
  (that 4.3 structural retry cited nothing; the claims gate passed on two
  claims; the blog's Sources list was empty; the cohort guard went red on
  main). Repaired FROM THE RECORD by `scripts/backfill_sources_from_desks.py`
  — each item paired with the same story in the desks' digests of the day or
  the show's own content tracker (the URLs the run fetched), the named outlet
  must fit the URL's publisher, a tie is no match, id-only URLs resolve by
  page title with `--resolve`; never from memory — and `items_without_source`
  is on the eight Mira cohort shows too (`tests/test_top_world_sources_2026_09_24.py`).
- **Prediction Markets Daily** (Sep 2026, pre-launch, Patrick) — the
  ecosystem, never a price tape and never a bet. The Board (≤5 markets) is
  one hook ARTICLE per market from `engine/prediction_board.py` (Polymarket
  Gamma, Kalshi's paced events crawl — it 429s a fast one — and Manifold
  play money; sports, parlays, price ladders and near-certain markets
  excluded; volume in each venue's own unit, never converted); How It Works
  is one subject a day from `shows/curricula/prediction_markets.yaml` with
  Crossref/arXiv abstracts (`engine/research_papers.py`) so the claims gate
  has papers to verify against. Board text is the pipeline's own copy, so it
  carries no specific legal claim. The Board is not content-tracked (a live
  market may lead for weeks). Guards: `tests/test_prediction_markets_2026_09_23.py`.
- **The Omni View desks + Top World** (Sep 2026, pre-launch, Mira) — five
  regional daily briefs (Europe, Asia Pacific, Africa & Middle East, Central &
  South America, North America) and Omni View Top World News, which ranks the
  day's ten. **One definition, every surface:** `engine/omni_desks.py` owns
  the desks (sub-regions, seeded arcs, accents, anti-tabloid filters) and the
  intros / first-episode / validation / tracker / memory / cover registries
  loop over it; the prompts share `shows/prompts/_shared/omni_desk_*.txt` and
  the ONLY per-desk prompt text is `shows/prompts/omni_desks/<region>.txt`.
  No `keywords:` on purpose (regional feeds; a title filter would drop
  on-region stories). Sub-region balance is a data-side preference note from
  the last ten digests, never a quota. **Top World verifies against the
  publisher, never a sibling digest:** its hook turns each desk's Lead and
  first regional item into a hook article carrying only the headline and the
  ORIGINAL publisher URL (no desk prose), text-less hook articles are fetched
  first (`engine.article_text`), and the desks' summaries reach the prompt
  only as a ranking note the claims gate never reads. Guards:
  `tests/test_phase3_desks_2026_09_23.py`. **Ep1 review (2026-09-23):**
  grok-4.7 speaks every prompt rule as a sentence — 37 of 305 script
  sentences narrated the briefing, "the item", the desk's rules or the length
  target, and a per-sentence attribution rule produced "The Times reports…"
  ten lines running. `_shared/omni_listener_rules.txt` (desks + Top World)
  describes the shape, and the opt-in absence filter now removes
  self-narration (`is_self_narration_sentence`). Europe died on a grok-4.7
  503 (the pinned-model fallback now covers 5xx and the script stage) after
  its RSS fetch outlived run_show's 120 s wait and was DISCARDED
  (`_await_fetch` grace period). Guards:
  `tests/test_desk_ep1_review_2026_09_23.py`,
  `tests/test_pinned_model_fallback_2026_09_23.py`.
- **Launch-cohort pass, PR A (2026-09-23; plan
  `/root/.claude/plans/staged-brewing-hanrahan.md`, guards
  `tests/test_launch_cohort_pass_2026_09_23.py`).** The per-show review of
  all 13 new shows found rules the prompts state and the model breaks, so
  they are code now. **`engine/digest_lint.py`** is a closed vocabulary of
  digest checks a show opts into with `digest_lints:` — WYNTK sentence 1
  must be the hook's story (`wyntk_hook_match`; MAG 7 Ep1 scored 0.08), a
  lead item is never sourced only to X, a desk's Progress Watch is a result
  or the explicit one-sentence none, MAG 7's Counterpoint engages the lead,
  AI Chips' data-centre items carry a build state + MW, the health shows'
  study sentences name their rung and never a dose. A finding rides the
  EXISTING one-shot structural regeneration; nothing here blocks or strips.
  **X posts credit the article they link** (`fetch_x_posts` asks for
  `POST_LINK`; the post URL moves to `x_url`), and `x_posts_as_sources`
  (`any` = legacy | `linked_only` | `secondary`) says how a show may use
  posts — Africa & Middle East Ep1 had credited 6 of 6 sources to x.com,
  BBC Africa and Al Jazeera posting their own stories. The committed
  Ep1s were re-sourced the same day with `scripts/resource_x_citations.py`
  (X's public syndication endpoint → the post's outbound link → the
  publisher URL; a tag / topic / mirror page is never a citation; dry-run
  default): 8 of 16 lines resolved, the rest were posts that linked
  nothing. `preferred_domains` (per-show list; `engine/preferred_sources.py`)
  gives a show's primary publishers — regulators, courts, journals, the
  city's own newsroom — a relevance bonus and a `[preferred primary source]`
  tag in the prompt listing (metric `articles_preferred_in_prompt`). **The claims ledger
  has an item coverage floor**: every grok-4.3 episode had recorded 0–1
  claims against 8–13 on 4.7 because the appendix called an empty array
  "valid and normal"; `attempt_item_coverage_repair` spends the existing
  repair pass on sourced items no verified entry covers and can only ADD
  entries. **Local shows carry `region_allowlist`** (word-boundary match on
  title + opening text; hook articles always pass; metric
  `articles_dropped_off_region`). **Top World's desk intake parsed zero
  items on Ep1** — `desk_items` matched only `**Title:** body` and the desks
  write `**Title: Outlet**`; fixed, and an X URL is never a publisher URL
  there. A syndicated wire copy is credited to the wire its dateline names
  (`credit_wire_datelines` — "The Mighty 790 KFGO" carried Reuters).
- **Launch-cohort pass, formats + fixed-clock segments (2026-09-23, same
  PR; guards `tests/test_launch_cohort_formats_2026_09_23.py`; register
  `launch-cohort-pass-2026-09-23`). ⚠️ Every prompt in the cohort changed —
  A/B-listen the first post-merge episode of each show.** Operator direction:
  make every significant change now, while nobody is listening. What binds:
  **the desks are Lead + two developed stories + "Also Today" one-liners**
  (`_shared/omni_desk_digest_body.txt`; story count follows supply, Also
  Today is omitted under two items; validator floor 2 on Across the Region;
  an `also today` body chapter on all five; `DESK_ITEM_SECTIONS` reads it
  for Top World), the hook opens on the consequence INSIDE the region when
  the actor is abroad, and WYNTK sentence 1 is the hook's story on every
  cohort show (prompt + the lint). **Top World** carries a `Ranks:` line per
  story (reader-only), items 6–10 as one sentence, an INTAKE line copied
  from the hook (`intake_line`, metric `desks_live_at_publish` — a hook may
  now return `metrics` and run_show records them) and a **Saturday
  single-story edition** decided by the hook's `edition_note`, never by the
  model reading a calendar (`omni_world_validation_config(saturday=)`
  swaps the items floor for a 1,800-char story). **Prediction Markets**
  scores itself on Fridays: `engine/board_week.py` pairs each question on
  the week's committed Boards with its latest reading and supplies a
  `### The Week's Board` block (a question with one reading is "one
  reading", never resolved); a number is a PRICE, never "the odds"; the
  Board row has four fields; a named critic's counter-argument closes the
  Top Story only when an article carries one; the curriculum gained 19
  subjects (41 unproduced). **MAG 7 and AI Chips close on a dated
  calendar read last** (`### On the Calendar` / `On the Horizon`, both
  chaptered; the teaser names a developing story, never the calendar item just read — Oct 11); MAG 7's Counterpoint
  answers the LEAD and Top News has a chapter (`top of the tape`). **The
  NA desk** has a Canada / US–Mexico floor and `both_sides_rotation_note`
  (data-side; two US-federal questions in a row send today's to Canada, a
  province, a state or the border). Mira's identity line on Vancouver and
  Collingwood says she does not live there. Longevity names the ONE
  hallmark a story touches and never the framework, and excludes the
  disease-trial titles Ep1 led with; Peptides closes its Spotlight on a
  five-slot card the `spotlight_card` lint checks; `evidence_rung` is on
  for both. LatAm reads six Spanish/Portuguese publishers; desks + AI Chips
  fetch 16 full texts; Collingwood's slow-news library
  (`shows/segments/collingwood.json`, 12 evergreen explainers) is on.
  Established shows are untouched; the arm/control hook_shape guard
  excludes the cohort by name.
- **Network sourcing pass (2026-09-24; guards
  `tests/test_network_sourcing_pass_2026_09_24.py`; register
  `network-sourcing-pass-2026-09-24`). ⚠️ The digest INPUT changed on ten
  shows — A/B-listen the first post-merge episode of each.** The launch
  cohort's sourcing floor, ported to every established news show, after the
  audit found the flagships recording 0 claims on 7 of their last 10
  episodes each and `fetch_full_text: 0` on 14 of 15 shows (the digest
  prompt had headline + teaser only — the Offshore North finding, network
  wide). Now: `fetch_full_text` 8–12 on tesla, spacex, models_agents, MAB,
  FF, planetterrian, omni_view, env_intel, modern_investing, finansy_prosto;
  `preferred_domains` (primary publishers: regulators, journals, the labs'
  and companies' own newsrooms, the wires) on each; `x_posts_as_sources:
  secondary` where the show does not own the story (**Tesla and SpaceX stay
  legacy — their own posts are primary**); the `x_only_lead` lint where a
  `LEAD_SECTIONS` header exists (replay: 1 firing in 60 digests).
  `evidence_rung` is deliberately NOT on FF / planetterrian: its rung
  vocabulary is biomedical and it fired on 15–19 items per six digests of
  astronomy and paleontology. The narrative shows, the Russian lesson show
  and the hook_shape arm/control experiment are untouched (guarded).
  **Listeners:** `engine/show_notes.py` appends a linked `Sources:` line
  (publisher domains, publishers before social posts, max 8) to every
  episode's RSS description — the feed copy had every Source line scrubbed
  while the blog listed them (metric `show_notes_sources`). **Readers:**
  `script_commas_per_100w` / `digest_commas_per_100w` in `engine.script_audit`
  and a snapshot column. **Members:** `PERSONAL_EXTRA_SHOW_SLUGS` widens the
  Nerra Personal vocabulary to the 13-show cohort (Worker list mirrored;
  `personal_edition_spec()` is what the builder discovers on; the Nerra
  Daily lineup is unchanged). Feed hygiene from `check_feeds.py` over the
  established shows: CNBC's two feeds (403 on every UA) moved to CNBC's
  search endpoint, Space.com's two dead RSS URLs became one Google News site
  query, two zero-item Google News queries simplified; the reddit 429s, NPR
  403s and news.gov.bc.ca TLS failures are this container's egress and were
  left for a runner read. Operator: `wrangler deploy` in `workers/gallery`
  for the Personal picker.
- **Launch-cohort PR C (2026-09-23; guards
  `tests/test_launch_cohort_schedule_2026_09_23.py`).** The nine hand-launched
  shows are on the clock (plan §6 slots, UTC): Asia Pacific 06:16, Africa &
  Middle East 06:31, Europe 06:46, Collingwood Friday 10:07
  (`FIRST_SCHEDULED_RUN` 2026-10-02 — Ep1 was hand-made on the 23rd from a
  192-hour window), North America 10:16, LatAm 10:31, Prediction Markets
  11:16, Top World 11:31 (after every desk's budget — its intake reads their
  digests), Vancouver 12:16. The six places a cadence lives all moved
  together (CRON_MAP, Worker SLOTS + FIRST_RUN, `review_episodes`
  SHOW_REGISTRY — `PRELAUNCH_SLUGS` is now EMPTY, daily-audit FEEDS,
  `test_schedule` lists; the registry `schedule` strings were already
  right). `CATCH_UP_MAX_PER_RUN` 10 → 16 (sized for 15 shows; 28 run now).
  **All 13 joined `ENGLISH_SHOWS`** (appended; pool 13 → 26, the surface
  pool is unchanged so the stride stays coprime) — until now no established
  show had ever mentioned a new one on air (⚠️ audio — A/B-listen).
  **`/mira.html` gained "Mira also reads the news"** from
  `engine.brand.MIRA_NEWS_SHOW_SLUGS` + `MIRA_NEWS_ROLE`; `MIRA_SHOW_SLUGS`
  (the claim-bearing trio) and the `mira` strand are deliberately untouched
  — the news shows are not the claim's basis. `_mira_shows(slugs=)` is one
  builder for both lists. A show page carries a dated "first scheduled
  episode" line from the registry's `first_run` (Collingwood) while that
  date is ahead — never a typed date. The nine stay OUT of the Nerra Daily
  lineup on purpose (`tests/test_daily_edition.py` EXCLUDED_NEW_SHOWS).
  Operator: `wrangler deploy` the scheduler Worker, then the first
  on-schedule slate is the listen set.
- All shows delegate X posting to `engine.publisher.post_to_x()`
- TST/FF/PT delegate voice normalization to `engine.audio.normalize_voice()`
- All shows use `engine.audio.mix_with_music()` for music mixing (3 modes:
  standard, delayed-intro, dual-music). Music files in `assets/music/`.
  Shows without music files gracefully fall back to voice-only.

## Adding a new show

Use `python scripts/scaffold_show.py` to generate YAML, prompts, output dirs, and
`shows/network_meta.yaml` in one step. Episode 1 gets extra debut guidance via
`engine/first_episode.py`. See [`docs/NEW_SHOW.md`](docs/NEW_SHOW.md).

## Conventions

### Environment Variables

- All secrets come from `.env` (local) or GitHub Actions secrets
- `GROK_API_KEY` — primary xAI key (all shows)
- `ELEVENLABS_API_KEY` — ElevenLabs TTS (legacy/rollback only — no show uses ElevenLabs in production)
- `X_*` / `PLANETTERRIAN_X_*` — two separate X accounts
- Voice IDs: **All 13 shows are on Grok TTS** as of the May 2026 full-network migration. The 10 English shows (including Tesla Shorts Time) share the operator's custom-trained voice `kdif6sqjcyiq`. Russian shows (FP/PR) use the custom Olya voice `0b875ae2`. ElevenLabs is no longer used in production but the API key + legacy settings stay in `_defaults.yaml` for emergency rollback. See landmine #17.
- See `docs/env_var_inventory.md` for the complete inventory

### RSS Feeds

All RSS `<enclosure>` URLs now use `audio.nerranetwork.com` (Cloudflare R2).
MP3 files are uploaded to R2 during the pipeline and excluded from git commits.
**Do NOT change R2 bucket paths — this breaks podcast subscribers.**

### Image gallery (Phases 1 + 2 + 3 — May 2026)

Every Grok-Imagine scene generated for the YouTube long-form / Shorts
slideshow is uploaded to a separate R2 bucket (`nerra-gallery`) with a
JSON sidecar and a watermarked WebP thumbnail.

**Phase 1 — storage.** Module:
[`engine/gallery_uploader.py`](engine/gallery_uploader.py). The hook
into `run_show.py:_publish_youtube` is purely additive — gallery
upload failure cannot block YouTube publish. New env vars:
`R2_GALLERY_BUCKET` (default `nerra-gallery`),
`R2_GALLERY_PUBLIC_BASE_URL` (optional). License default: **CC BY-SA
4.0** with attribution to Nerra Network. Backfill:
[`scripts/backfill_gallery.py`](scripts/backfill_gallery.py) — note
historical scene dirs are in `.gitignore` so there is nothing to
backfill from on-repo state without an external archive.

**Phase 2 — manifest + rendering.** A workflow
([`.github/workflows/build-gallery-manifest.yml`](.github/workflows/build-gallery-manifest.yml))
runs nightly + after every successful `Run Podcast Show` and rebuilds
[`site/data/gallery-manifest.json`](site/data/gallery-manifest.json)
from the R2 sidecars via
[`scripts/build_gallery_manifest.py`](scripts/build_gallery_manifest.py).
The frontend is **vanilla JS** ([`assets/js/gallery.js`](assets/js/gallery.js))
— no build step — hydrating the mount point declared in
[`templates/_gallery_section.html.j2`](templates/_gallery_section.html.j2).
The network-wide page is
[`templates/gallery_page.html.j2`](templates/gallery_page.html.j2)
rendered to `/gallery.html` by `generate_gallery_page()` in
`generate_html.py`. Per-show galleries are embedded on each show page
when `gallery_enabled` is true (any show with `youtube.enabled: true`
AND `image_provider: grok`; as of June 14 2026 that's Tesla, SpaceX,
Fascinating Frontiers, Modern Investing + the two RU shows — MAB's
YouTube is paused so its gallery auto-hides — see landmine #20).
Prompt visibility is a per-image **toggle** (hidden by default in the
lightbox).

**Phase 3 — email-gated downloads.** Cloudflare Worker at
`api.nerranetwork.com` ([`workers/gallery/`](workers/gallery/)) with
four endpoints: `POST /api/subscribe` (Buttondown subscribe + 90-day
JWT cookie), `GET /api/login` (magic-link email via Resend, always
200 so the address can't be enumerated), `GET /api/magic` (consume
the magic JWT, set cookie, 302 to /gallery), `GET /api/download`
(verify cookie, stream the R2 object via the bucket binding with
`Content-Disposition: attachment`). JWT is HS256, hand-rolled in
[`workers/gallery/src/jwt.ts`](workers/gallery/src/jwt.ts) — no
third-party dep on the Worker. The download endpoint **proxies bytes
through the Worker** instead of issuing signed R2 URLs (revocation
works, no shareable URLs, no SigV4 plumbing — documented deviation
from the spec). Frontend [`assets/js/gallery.js`](assets/js/gallery.js)
calls these endpoints with `credentials:'include'`; gate modal
supports both "Subscribe & download" and "Already subscribed? Sign
in instead" paths. New secrets (set via `wrangler secret put` once):
`JWT_SECRET`, `BUTTONDOWN_API_KEY`, `RESEND_API_KEY`,
`RESEND_FROM_EMAIL`. The Worker doesn't need new R2 credentials —
the bucket is wired declaratively as `GALLERY_BUCKET` in
[`workers/gallery/wrangler.toml`](workers/gallery/wrangler.toml).

Layout, schema, env vars, deployment steps, and the operator
checklist live in
[`docs/gallery_storage.md`](docs/gallery_storage.md) and
[`workers/gallery/README.md`](workers/gallery/README.md).
Unconfigured environments (env vars unset) are a clean no-op: the
manifest builder writes an empty manifest, the frontend renders a
friendly empty state, and the gate modal surfaces a network error if
the Worker hostname isn't reachable yet.

### YouTube Shorts production (May 2026 retune)

Two Shorts-quality fixes shipped after the operator caught issues
with the first wave of episodes:

* **Thumbnail title auto-shrink-to-fit.**
  [`engine/publisher.py:generate_episode_thumbnail`](engine/publisher.py)
  iteratively shrinks the hook font (start at the YouTube-spec max,
  step down by 8 px) until the wrapped block fits inside 60 % of the
  frame height AND ≤ max-lines (3 on Shorts 1080×1920, 4 on long-form
  1280×720). Floor at ~32 px. Replaces the legacy fixed-size
  rendering that clipped long Tesla hooks against the safe area.
  Drift guard: `tests/test_thumbnail_autofit.py`.
* **Shorts burn-in caption upgrade.** Bumped from outline-only
  FontSize=34 to FontSize=48 bold on a 50 %-opaque box
  (`BorderStyle=3` + `BackColour=&H80000000`) in
  `engine.video._SHORTS_SUBTITLES_FORCE_STYLE` — TikTok-style
  "subtitle card" that stays readable over Grok-Imagine backgrounds.
  Position shifted to `MarginV=340` to keep the larger card clear of
  the URL pill (y ≈ 1820) and below the hook overlay (y ≈ 1056).
  Caption wrap tightened to 24 chars / 2 lines (was 32 / 3) to match
  the larger font; see
  `engine.captions.transcript_to_srt_window`. Drift guard:
  `tests/test_video_commands.py::test_short_form_filter_graph_burns_subtitles_when_path_provided`.

`shows/models_agents_beginners.yaml` also flipped from
`image_provider: pexels` to `grok` in May 2026 — Pexels A/B was
inconclusive and the gallery pipeline (Phase 1) requires Grok
Imagine. Cost: ~$0.16/episode added.

**Per-word caption highlighting (TikTok / Reels look).** Shorts now
ship with per-word "current word" highlighting instead of static
segment cards.
[`engine.captions.transcript_to_ass_window`](engine/captions.py)
generates an ASS file (the modern subtitle format the ffmpeg
`subtitles` filter accepts identically to SRT — no `video.py` change
needed) with one `Dialogue` line per word; each line shows the full
chunk text with the active word colour-flipped to Nerra cyan
(`#00D4FF` / ASS `&H00FFD400`). Word timestamps come from
`faster-whisper` which already runs with `word_timestamps=True` in
`engine.transcripts` — no new transcription cost. Words are chunked
to ≤24 chars / ≤8 words per chunk to match the FontSize=48 caption
card. `run_show.py` tries the ASS path first; if the transcript has
no word data (older episodes) or no overlap with the Shorts window,
it falls back to the legacy segment-level SRT so the Short always
has captions of some kind. Drift guards in
`tests/test_captions_ass.py`.

**Smart Shorts segment selection.** Tesla + MAB now use
`shorts_start_mode: smart` in their YAML, which calls
[`engine.shorts_selector.pick_engaging_window`](engine/shorts_selector.py)
to scan the Whisper transcript and start the Shorts clip at the
most engaging beat (numeric reveal, hook framing like "the kicker
is…", surprise / question / superlative). Pure heuristic — no LLM
call, no per-episode cost. Falls back to the legacy
`voice_intro_delay` start when no segment scores above the noise
threshold (5.0). The chosen offset + the resolved mode are recorded
as metrics (`shorts_start_offset`, `shorts_start_mode_resolved`) per
episode so the dashboard can show smart-vs-fallback rates. New shows
opt in by setting `youtube.shorts_start_mode: smart` in their YAML.
Drift guards in `tests/test_shorts_selector.py`.

**Multiple Shorts per episode.** Setting `youtube.shorts_per_episode`
to N (default 1; cap at 2-3 for YouTube quota safety on the
@NerraNetwork channel — see landmine #20) makes the runner publish
N Shorts per episode instead of one. Each Short comes from one of
the top-N non-overlapping windows the smart selector
([`pick_top_n_engaging_windows`](engine/shorts_selector.py)) picks
from the transcript; each gets a distinct headline (the window's
opening text), a distinct thumbnail (cycled through the available
Grok-Imagine scene images), and a distinct filename
(`_short_1.mp4`, `_short_2.mp4`, …). Uploads are sequential; one
failure doesn't block the others. Per-Short error captures land in
`result["short_errors"][i]` and the aggregate
`shorts_count_requested` / `shorts_count_uploaded` metrics fire on
every episode so the dashboard can plot the multi-Shorts hit rate.
Requires `shorts_start_mode: smart` (the voice / first_chapter
modes only know about one offset). Default 1 preserves legacy
single-Short behaviour byte-for-byte. Drift guards in
`tests/test_shorts_selector.py` under the
`pick_top_n_engaging_windows` block.

**Staggered Shorts publishing (Aug 2026, operator-directed).** Short #1
publishes with the episode; the 2nd/3rd upload PRIVATE with
`status.publishAt` at the channel's next optimal UTC slots
(`youtube.shorts_stagger_slots_utc` in `_defaults.yaml` — EN 17/21/23,
RU 15/18/20, FR 17/19/21; audience-timezone priors, hand-tuned because
the Analytics API has no hour-of-day dimension), so one episode's Shorts
spread through the day on every channel, manual runs included. YouTube's
own scheduler flips them public — no new infra, dead runners can't
strand a Short. Engine: [`engine/shorts_stagger.py`](engine/shorts_stagger.py);
wired in `run_show._publish_youtube`, `engine/ru_dub.py`,
`engine/lang_dub.py`. The video index records the **publishAt** date so
policy vpd math stays honest. Funnel comments can't be posted on a
private video, so they queue to `digests/<slug>/scheduled_comments.json`
and `scripts/post_scheduled_short_comments.py` (multilingual sweep +
nightly, which hold the channel tokens; sidecar is in nightly's
add-paths whitelist) posts them once public. `shorts_stagger_enabled:
false` per show reverts to publish-all-now. Drift guards:
`tests/test_shorts_stagger.py`.

**Auto-hashtag injection on Shorts descriptions.** Every Shorts
upload now carries entity-derived hashtags in its description
(via [`engine.shorts_hashtags.extract_hashtags`](engine/shorts_hashtags.py)).
YouTube renders the **first 3** hashtags as clickable topic-tag
links above the video title — biggest discovery lever on Shorts
after the title itself. Heuristic-only parser, no LLM call:
multi-word Title-Case entities (`Tesla Cybercab` →
`#TeslaCybercab`) outrank single proper nouns (`Tesla` →
`#Tesla`) which outrank all-caps acronyms (`TSLA` → `#TSLA`),
with the show's YAML `keywords` blended in at the tail to fill
remaining slots. Substring de-dupe across bands prevents
"#Tesla" eating a slot when "#TeslaCybercab" already covers the
entity. Caps at 5 hashtags + the static `#Shorts #podcast`
suffix. Real-hook probes: Tesla wireless-BMS hook →
`#BatteryManagementSystem #Tesla #Cybercab`; Modern Investing
TFSA/RRSP hook → `#ModernInvestingTechniques #TFSA #RRSP`. Drift
guards in `tests/test_shorts_hashtags.py`.

**Hook overlay auto-shrink-to-fit.** The 0–3 s static hook
overlay on the Shorts MP4 used to render at a fixed
fontsize=44 with a conservative char-based wrap (26 chars × 4
lines = 104-char budget) that truncated longer Tesla hooks with
"...". `engine.video.autofit_hook_overlay` now applies the same
shrink-to-fit pattern the thumbnail uses: start at 44 px, drop
in 4-px steps (44 → 40 → 36 → 32) only if the wrapped text
would truncate at the larger size. Pixel-accurate wrap via PIL
`ImageFont.getbbox` uses the actual 1080-px Shorts frame width
instead of the char-budget approximation, so a 110-char hook
(Tesla Ep461 Cybercab wireless-BMS) now fits at 44 px without
truncation, and runaway 170+-char hooks shrink to 32 px and
still fit. Drift guards in `tests/test_video_commands.py` under
the "Shorts hook overlay auto-shrink-to-fit" header.

**End-screen CTA card.** The last
`youtube.shorts_end_card_duration_seconds` (default 3 s) of every
Short overlays a PNG end card composited at run time by
[`engine.publisher.generate_shorts_end_card`](engine/publisher.py).
The card shows the long-form 1280×720 thumbnail in the upper third
(framed with a thin white border so it reads as a tap target),
a big white headline ("WATCH FULL EPISODE"), a cyan sub-line
("Tap Subscribe ↗", matching the per-word caption highlight from
PR #415), and a small `nerranetwork.com` footer. The
`engine.video._short_form_filter_graph` overlays the PNG via a
single `overlay=enable='between(t,END-3,END)'` filter. When PNG
generation fails (or the long-form thumbnail upstream failed),
the chain falls back to the drawtext-only version originally
shipped in PR #417 — soft degradation, never blocks the Shorts
publish. Implemented as a drawbox + 2 drawtext
filters in the existing filter graph — zero filesystem dependency,
no per-episode asset generation. YAML knobs to customise:
`shorts_end_card_enabled` (default true network-wide), plus
`shorts_end_card_main_text` / `shorts_end_card_sub_text` /
`shorts_end_card_duration_seconds` for per-show overrides (useful
for Russian-language shows when they migrate to YouTube). Drift
guards in `tests/test_video_commands.py` under the "Shorts end-
screen CTA card" header.

### YouTube visual reuse + chapter-aligned scenes (June 2026)

Renders now reuse the imagery the network already paid for and time scene
changes editorially — full doc:
[`docs/youtube_visual_reuse.md`](docs/youtube_visual_reuse.md). **Everything
here is render/metadata-only (no audio → outside the landmine-#17 A/B
gate)**, config-gated with defaults **on** (`youtube:` knobs in
`shows/_defaults.yaml`: `gallery_blend_enabled` + per-aspect caps,
`chapter_aligned_scenes`, `long_form_thumbnail_from_scene` /
`thumbnail_variants`, `recap_reuse_scenes`, `gallery_fallback_enabled`,
`shorts_sentence_cuts`, `evergreen_broll`), and best-effort by contract —
any failure logs a warning and ships the exact legacy render.

- **Layers:** [`engine/gallery_library.py`](engine/gallery_library.py)
  (pull relevant historical scenes/b-roll from the `nerra-gallery` R2
  bucket via the committed manifest; cached, never raises) →
  [`engine/scene_scheduler.py`](engine/scene_scheduler.py) (pure planning:
  chapter-aligned scene schedules + sentence-snapped Shorts cuts) →
  `engine/video.py` render hooks (`scene_schedule` / `broll_clips` /
  `scene_change_times`; `None` = legacy byte-identical) →
  [`engine/visual_reuse.py`](engine/visual_reuse.py) (the thin composition
  layer run_show calls: `long_form_visual_plan`, `short_visual_extras`,
  `recap_scene_pool`, `fallback_scene_pool`).
- **Per episode:** long-form blends ≤8 library 16:9 scenes into the 4 fresh
  ones (ranked by hook/chapter-title overlap) and switches scenes on
  chapter boundaries; Shorts blend ≤4 library 9:16 scenes and snap scene
  cuts to sentence ends from the existing Whisper word transcript.
- **Sunday recaps** skip Grok Imagine entirely and reuse the week's gallery
  scenes when both aspects have ≥2 pooled images (below that: generate as
  usual). **Degraded days** (<2 fresh scenes) fall back to gallery-library
  scenes BEFORE the static cover; the degraded `::warning::` says which
  fallback shipped.
- **Thumbnails:** long-form thumbnail composites over the first fresh 16:9
  scene (cover fallback) + up to 2 variant composites from other scenes
  (`engine.publisher.generate_thumbnail_variants`), uploaded to the gallery
  bucket (`intended_use: thumbnail_variant` — invisible to the scene
  selector) for Studio "Test & Compare".
- **Evergreen b-roll:** ≤3 curated clips interleaved into the long-form
  slideshow; a clean no-op until the operator publishes
  `digests/<dir>/broll.json` via `scripts/build_broll_pool.py`.
- **Flywheel:** `scripts/build_gallery_retention.py` (nightly, after the
  analytics fetch + manifest rebuild) joins gallery images with per-video
  `averageViewPercentage` → `api/gallery_retention.json` (top/bottom image
  tags by mean retention, min 3 videos). Clean no-op until analytics data
  accrues.
- **Metrics:** `visual_mode` (chapter_schedule|uniform|cover|
  library_fallback|recap_pool), `scene_fresh_count`, `scene_library_count`,
  `broll_clips_used`, `thumbnail_base`, `thumbnail_variant_urls`. Drift
  guards: `tests/test_visual_reuse.py`.

### Nerra Personal — accounts, personalized feeds, donations (Aug 2026)

The member surface (operator-directed). **One identity**: a "Nerra
account" IS the gallery Worker's existing JWT/Buttondown identity —
every newsletter signup (footer + `/join.html` both POST the Worker's
`/api/subscribe`, `list:"member"`; the Buttondown-direct embed form is
GONE) creates an account that unlocks gallery downloads, per-show
newsletter tags (closed `SHOW_NEWSLETTER_TAGS` set in
`workers/gallery/src/handlers.ts`), and member perks
(`MEMBER_BOOK_CODE` book discount). **Paid tier**: a private daily feed
of the subscriber's chosen shows in THEIR order, Mira anchoring by name
($4.99/mo; +city morning brief $8.99/mo — Open-Meteo weather +
one web-search call under the field-note honesty rules).
`engine/personal_edition.py` (closed vocabulary = the EN edition lineup;
kept in sync with the Worker's copy by a drift test) +
`scripts/build_personal_feeds.py` (segments trimmed ONCE/day into a
shared cache — per-user marginal cost ~$0.05-0.07/day; **PII rules: runs
on a PRIVATE host only, specs carry token/name/city never email, logs
truncate tokens**) + Worker endpoints in
`workers/gallery/src/personal.ts` (KV member records, Stripe webhook
mints/revokes feed tokens — cancel = feed 404s immediately; feeds served
Worker-gated from R2 `nerra-personal`, `itunes:block` on).
**Donations**: `/support.html` (cost-transparency pitch + Stripe links);
every feed's `podcast:funding` tag now points THERE (was `/#newsletter`)
— it renders as the Support button in 2.0 apps. Pages
(`join/account/support.html`) regenerate with `--network`/`--all`;
Stripe URLs flow from env (`STRIPE_LINK_*`), unset = honest
"launching soon" states. Everything Worker-side degrades to 503 until
the operator provisions KV + the `nerra-personal` bucket + secrets
(checklist: [`docs/nerra_personal.md`](docs/nerra_personal.md)). Drift
guards: `tests/test_nerra_personal.py`,
`workers/gallery/test/personal.test.ts`.

### Nerra Personal: Mira knows the listener, at no new model cost (Oct 18 2026)

Operator-directed (guards `tests/test_personal_deep_2026_10_18.py`,
`tests/test_personal_handoffs_2026_10_17.py`; docs `docs/nerra_personal.md`
"Oct 18 2026"; register `personal-deep-2026-10-18`, `personal-trims-2026-10-18`).
**The cost rule binds: no new model or search call per member** — every
personal feature is deterministic code, ffmpeg on the cached segments, or a
few more lines in the ONE existing links call. What it adds: a member note
("Tell Mira about you", ≤ `PROFILE_MAX_CHARS` 240, scrubbed like every
free-text field, fenced in the prompt as information about the listener and
never instructions, at most two observations an edition, never logged);
edition memory (each `episodes.json` row records what the edition contained;
today's stories are matched against the last seven, so Mira says a story is
an update, never fresh news; the first edition explains what she does, Sunday
counts the week's threads); cross-show repeat notes; an opt-in `skip_repeats`
add-on and a length budget (`TARGET_MINUTES` 20/30/45/60) that trim only a
WHOLE show chapter whose edges sit in a pause between sentences, never a lead,
sign-off, last chapter or members-only episode, every trim named on air and in
the notes; and story chapters from the shows' own chapter files. **A music
show's story-break pause carries the theme (~-21 dB), so `silencedetect`
finds nothing there** — a ≥ 0.8 s sentence-ending Whisper gap counts as a
pause. On Oct 4-17 data no repeat trim passed every rule (chapters start late,
see `engine/chapters.py`); the notes are the benefit until they do. The
handoff repair (`realign_handoffs`) runs on every personal edition (Oct 17).
`PROFILE_MAX` / `TARGET_MINUTES` are mirrored in `workers/gallery/src/personal.ts`
(drift-guarded). Operator: `wrangler deploy` in `workers/gallery`; A/B-listen
the first edition with the new prompt blocks. ⚠️ AUDIO (Mira's lines).

### The schedule runs on Eastern time; Nerra Daily out by 7am Eastern (Oct 17 2026)

Operator-directed (register `nerra-daily-7am-eastern-2026-10-17`; guards
`tests/test_seven_am_eastern_2026_10_17.py`). **The scheduler Worker's
`SLOTS` are EASTERN wall time** (`SLOT_TZ = "America/New_York"`; the handler
converts each firing and the day filters read the Eastern date), so the clock
changes move nothing. Shows run as late as they can: 04:00 ET (UC) to 06:10 ET
(Top World, after every desk), five minutes apart; Vancouver keeps its local
05:15 Pacific slot (08:15 ET) and **is not in the edition** (it stays
choosable in Nerra Personal — `PERSONAL_EXTRA_SHOW_SLUGS`). The edition's
gate is `RELEASE_EASTERN` 06:35 / `HOLD_UNTIL_EASTERN` 06:50
(`engine/daily_edition.py`), dispatched by the Worker at those Eastern minutes;
the X queue dispatches :05/:35, 7:05 AM-10:05 PM ET. **The one cron trigger is
`*/5 * * * *`.** The run-show.yml fallback crons are UTC and cannot follow
daylight saving: **each is the slot's EST equivalent (ET + 5 h)** — in summer
it fires an hour after the Worker and the duplicate guard drops it — and
`test_scheduling_punctuality.py` compares Worker and cron map at that offset.
A new show is scaffolded with `--slot-et HH:MM` (multiple-of-five minute).
`GET /` reports slots as `{"at": "05:45", "tz": "America/New_York"}`; a Worker
still answering `"09:16Z"` predates this and the deploy check says so.
Operator: `wrangler deploy` in `workers/scheduler`.

### Audio first, and a release schedule for the day (Oct 17 2026)

Same operator direction as the Eastern schedule above (register
`audio-first-2026-10-17`, `release-schedule-2026-10-17`; guards
`tests/test_audio_first_2026_10_17.py`, `tests/test_release_schedule_2026_10_17.py`).
**A run publishes its audio before it renders video.** Video is two thirds of
a flagship run (25 of 37 minutes on Tesla), so run_show now writes the feed,
summaries, blog post and post-run validation first and pushes them through
`scripts/checkpoint_publish.sh` ("Auto-generated: <show> <date> (audio)" — the
duplicate guard's prefix; `NERRA_AUDIO_FIRST_PUSH=1` from the workflow, never
in `--test`); the workflow's final commit pushes what the video half adds.
`scripts/stage_show_artifacts.sh` is the ONE staging list both use — a new
committed path goes there. A failed checkpoint push un-commits and leaves
everything staged. **The feed item is rewritten after the video on the SAME
GUID** (`update_rss_feed(keep_existing_guid=True)` — the GUID carries a
timestamp, and a new one makes every app download the episode twice).
**`engine/release_schedule.py` owns when each surface goes public**, in
Eastern wall time, from one `RELEASE_ORDER` (news and markets first): hook
Short 7:00 ET + 15 min per rank, long-form from noon and from 18:00, X
preferred slot from 7:30 (7:00 reserved for Nerra Daily), daily newsletters
scheduled for 7:00 through Buttondown (`status: "scheduled"`), Vancouver on
Pacific mornings. A passed slot means now; a refused `publishAt` re-uploads
public; `youtube.release_schedule_enabled` reverts per show. A scheduled
long-form's comment is queued and posted by the half-hourly x-queue run
(`post_scheduled_short_comments.py --stateless`, which checks the video for the
comment first); the feed says when the long-form goes public. Render,
metadata and timing only — outside landmine #17.

### A beat between stories (Oct 13 2026)

Operator listen: stories ran into each other. Measured: the gap at a story
change (~0.55 s) equalled the gap between two sentences, and the shared
content-discipline rule told every script to move on "with the next story's
first fact". Now: **`engine/story_breaks.py` splices
`audio.story_break_seconds` (1.2 in `_defaults.yaml`, 0 = off, never on a
dialogue show) of silence where a new story starts**, before the music mix.
Story starts come from the DIGEST (numbered and sourced items are stories;
an essay section is one unit; a one-line detour or a run of one-liners is
not a break); each cut sits in the voice track's own silence
(`silencedetect`, never between Whisper word times, which abut across real
pauses); the splice is lossless WAV and the committed transcript is shifted
with it, so captions, Shorts and the Nerra Daily cut stay aligned. Grok's
`[pause]` tag was measured and rejected (0.0-2.4 s). Scores sum in sorted
order — set iteration follows the hash seed and flipped near-ties. The prompt
rule became "The listener hears every story change": a new story's first
sentence names its subject before any figure. ⚠️ AUDIO — A/B-listen. Register
`story-breaks-2026-10-13`; guards `tests/test_story_breaks_2026_10_13.py`.

### Natural transitions, and shows that reach their length (Oct 14 2026)

Operator listen: the Oct 13 beat "sounds forced and unnatural", and many
shows ran short (review:
[`docs/reviews/transitions_and_length_2026_10_14.md`](docs/reviews/transitions_and_length_2026_10_14.md);
register `story-transitions-natural-2026-10-14`,
`shows-reach-their-length-2026-10-14`; guards
`tests/test_transitions_and_length_2026_10_14.py`). The Oct 13 value was ADDED
to the voice's ~0.45 s pause and mid-episode there is no music: 1.6-1.7 s of
dead air against a 0.35 s sentence gap. **`audio.story_break_seconds` is now
the TOTAL pause (1.0)** — `plan_breaks` splices only the difference — and
**`audio.story_break_cue` lays a soft swell of the show's own theme under each
pause on the music track** (`engine.audio.breather_offsets`, steady bars, a
different one per break, ~12 dB under the voice, skipped inside the opening
bed and on shows without music). No beat within 20 s of the last; a line
opening on a pronoun or connective never starts a story; short items under one
heading are one block. **The digest length floor counts PROSE**
(`engine.generator.digest_prose_word_count`): it had counted the fenced claims
ledger (480-1,100 words), so the digest expansion never fired on the cohort's
daily shows; the retry takes every figure from the supplied material. Length
is digest-side: desk format v3 (**The Closer Look**, 300-420 sourced words;
Across 2-3; Also Today 3-5; Lead 5-8 sentences; preferred publishers; full
text ranks cluster members first), doubled deep dives (AI Chips Teardown, MAG 7
Thread, PM How It Works, FF/PT deep dives, Tesla's essay — each built from a
fetched article), a Closer Look on Vancouver and Collingwood, a longer Top
World. Targets come from the promised minutes and each host's measured spoken
rate; **every skip floor stays at its old 60% line**
(`min_podcast_publish_words`) — never raise a target without pinning it. Fixed
segment openers ("Across the region,", "At the top of the tape,", "On the
board today,") are optional now, with `digest_section` chapter fallbacks.
⚠️ AUDIO — A/B-listen.

**Oct 14 2026, evening — the first slate, scored** (§5 of the review doc;
register `slate-readout-2026-10-14`; guards
`tests/test_slate_readout_2026_10_14.py`). The desks went to 9.3-12.6
minutes and AI Chips / PM / MAG 7 / Vancouver landed inside their promises;
the breaks sat in the voice's own silence (0.99-1.19 s on Vancouver). Four
corrections: **the cue is `BREATHER_VOLUME` 0.09** — 0.22 played 2-5 dB
under the voice on the shipped mixes because loudnorm lifts an exposed gap;
calibrate a cue level on a REAL voice through `_final_mix_cmd`, never on a
preview by ear (0.22 → 4.7 dB under, 0.12 → 10, 0.08 → 13.4). **The digest
expansion is judged in prose** — it had compared prose to prose-plus-ledger
and accepted Tesla's +80-word pass as +630; the retry prompt names each
section's prose length against the format's own specs, and
`llm.digest_expansion_attempts: 2` (Tesla, FF, MIT, OV) allows a second pass
only under 90% of the floor. **A sourced item under the hook is a story**
(`story_breaks.story_units`; a `---` rule splits paragraphs) and FF's
validator accepts an unnumbered bold list — Ep222 got one beat and burned
its structural retry on a header. **Market-research press releases never
reach a prompt**: `engine.utils.NETWORK_EXCLUDE_TITLE_PATTERNS`
("… Market Forecast to 2035: 11% CAGR") at all three fetch sites, after 19
aired as headlines on eight shows in 40 episodes. Top World's floor is
1,900 with items 1-5 at 7-10 sentences (Mira speaks a developed item in
~80% of its words). **Prediction Markets' Sep 23 curriculum restock had
re-added eleven subjects the show had already taught** (same titles) —
pruned, thirteen new subjects added; a restock checks PRODUCED titles.
**A narrative pick re-interleaves the queue** (`engine.topic_queue.
resequence_unproduced`, now called by `mark_topic_produced`): the Oct 11
thin-research skip takes the topic BEHIND the head and leaves two
same-category briefs adjacent (UC Ep142 — the runway guard went red on
main with nothing wrong in the restock's data).
⚠️ AUDIO — A/B-listen one music show for the cue.

**Oct 14 2026, night — an outside review of the Oct 13 slate, checked**
(register `external-review-2026-10-14`; guards
`tests/test_external_review_2026_10_14.py`). True and fixed: **one budget
for every headline-derived chapter title** — `engine.chapters.HEADLINE_TITLE_MAX`
is `engine.titles.HEADLINE_CHAPTER_TITLE_MAX` (80); the Oct 8 clip ran at 60
and shipped "…halts the number" while most desk lead headlines run 60-80, and
every hook runs over 60, so the lead chapter existed on 9 of 20 episodes; when
the hook is too long for a title and no headline matches, the lead chapter
takes the digest's own section name (`lead_section_name`: "Lead", "Top
Story" — a story heading never is). **A line that is only a URL becomes a
`Source: [domain](url)` line** (`engine.newsletter_body.linkify_bare_url_lines`,
in `transform_daily_body`; 49 such lines in seven days on the desks and the
Board). **The hook's item leads its list** (`engine/hook_item.py`,
`hook_item_first: true` on FF / Planetterrian / Tesla; the item sharing ≥ 3
salient words with the hook and beating item one by 2 moves to the top and the
section renumbers; metric `hook_item_promoted_from`; the replay moved nothing
on SpaceX, M&A, the desks or MAG 7). **The narrative shows list their research
pages** (`engine/research_sources.py` appends a `### Sources` section the blog
card and show notes already read; `READER_ONLY_EXACT_SECTIONS` keeps it out of
the script). **The correction box renders above the headline**, and a
correction may carry `amend_headline: true` (the page title gains "Corrected:";
feed title and audio untouched) — UC Ep139's switch is the operator's. Not
true, not acted on: Top World's Both Sides is a named disagreement, never the
lead's counterpoint; Vancouver's source says 20 per cent; Nerra Daily's rundown
links each show's post.

### Story breaks that reach the audio, and handoffs that match (Oct 16 2026)

Slate review ([`docs/reviews/slate_review_2026_10_16.md`](docs/reviews/slate_review_2026_10_16.md);
register `story-breaks-reach-the-audio-2026-10-16`,
`nerra-daily-handoffs-aligned-2026-10-16`; guards
`tests/test_slate_2026_10_16.py`). Measured in the shipped MP3s, the beat
itself works (1.02–1.06 s on the no-music shows, the cue ~13–16 dB under the
voice); what failed was DETECTION: **13% of October's story changes never
reached the audio** because a line's opening was matched letter for letter
against Whisper ("the early 2000s", "1,500", "Columbia's", "La Nassion").
`engine/story_breaks.py` now folds accents, speaks years and decades the same
way on both sides, and falls back to a fuzzy anchor (first letter must match,
0.72 ratio, ±150 words of the line's expected place) — 362 unplaced → 32 on
replay, every recovered anchor on the line's first word. A link at the end of
a paragraph makes it a story (FF Ep224 had one beat for seven); a numbered
heading is ONE story (Omni View's Read-more list had split its lead); two beats
on adjacent lines settle on the segment opener or the story start. **A Nerra
Daily handoff must introduce the segment after it** (`realign_handoffs`, metric
`handoffs_realigned` — Ep049/055/057 shifted by one, 39 wrong introductions;
replayed on those three, 42 wrong → 1). **Nerra Personal runs the same repair**
(`scripts/build_personal_feeds.py`, Oct 17 — it had only the count check that
let those editions through) and the same links token budget.
Also: ratio shorthands (MoM, YoY, QoQ, ROE, ATH, AR, ML) match only their own
case ("mom-and-pop" aired "month over month"); paid placements are dropped by
URL path (`NETWORK_EXCLUDE_URL_PATTERNS`); Both Sides is overlap-exempt on
Vancouver, Collingwood and Top World; MIT names the record's start date and
teases the next trading session; the Week's Board tracks a market across
rewordings and counts single readings instead of reading them out.
⚠️ AUDIO — A/B-listen one FF and one Omni View episode.

### A beat only where a story changes, and X video (Oct 17 2026)

Slate review ([`docs/reviews/slate_review_2026_10_17.md`](docs/reviews/slate_review_2026_10_17.md);
register `story-breaks-placement-2026-10-17`, `slate-2026-10-17`; guards
`tests/test_slate_2026_10_17.py`). The Oct 16 anchoring held (1 unplaced of
133); what failed was WHICH lines got a beat. **`MIN_STORY_SECONDS` is 12**
(20 dropped 15 real stories in a day — Tesla's run 14-22 s apart). The cold
open (to "This is <Show>, episode") and everything from the sign-off never set
the story; unsourced paragraphs join the sourced paragraph that ends their
section unless it opens on its own bold title; an all-essay digest moves
forward only; the lead runs two lines before the first beat; an anchor backs
off by LETTERS and snaps to a word start. A "retells" overlap suppression was
measured and REJECTED (it ate Planetterrian's deep-dive opener 3/3). Content:
**the expansion dedup never touches a fenced block** (it had deleted ledger
lines — 45 malformed entries in a week); **a date in the URL slug ages an
article** (`engine.article_dates.url_slug_date`, the older date wins, never a
future one, a `/YYYY/MM/` path wins); MIT's pick prompt names the open
positions; Top World says nothing about desks when none fed it; the X teaser
clips through `engine.titles`. **A queued X post is `x_post_queued`, not a
confirmed post** — the x-queue workflow is the delivery record
(`x_queued_share_7d`). Full-episode video on X is possible without Premium up
to 20 min (design in the review doc; needs a Supabase migration — operator).
⚠️ AUDIO — A/B-listen one Tesla and one UC episode.

### The Age of AI: the room, the brief, and a loop that can hear (Oct 21 2026)

Operator-directed, from the full review of the interview show (review
[`docs/reviews/age_of_ai_review_2026_10_21.md`](docs/reviews/age_of_ai_review_2026_10_21.md);
ledger `age_of_ai` 2026-10-21; register `age-of-ai-room-and-loop-2026-10-21`;
guards `tests/test_room_mechanics_2026_10_21.py`,
`tests/test_mira_prompt_is_a_brief_2026_10_21.py`,
`tests/test_audio_metrics_2026_10_21.py`, `tests/test_loop_hears_2026_10_21.py`,
`tests/test_voices_worker_hardening_2026_10_21.py`,
`tests/test_edit_keeps_its_promises_2026_10_21.py`, `tests/test_guest_hour_2026_10_21.py`,
`tests/test_rehearsal_harness_2026_10_21.py`). Thirteen grades ran 2-7 with no
trend, Mira's median turn fell from ~28 s to 7.6 s, the last two rooms
interrupted 14 times each, and the loop reported adopting a lesson after
every tape. The three faults guests named were the ROOM's, and the rules
that bind now:

- **End of turn is a decision, not a timer** (`voximplant/scenarios/age_of_ai_interview.js`).
  The silence timer was raised 1,100 → 1,300 → 1,800 ms and the Oct 20 room
  still interrupted 14 times, so it is never raised again: `turn_detection`
  sends `create_response: false`, the server VAD finds the pause, and the
  room's `decideTurn` gives her the turn only when someone has spoken since
  her last line and the last clause reads finished (one extra wait for a
  late transcription, one for an unfinished clause). A turn the server starts
  with nobody having spoken is cancelled at once (`self_answers_blocked`).
  **`requestTurn` is the one way to a turn** and parks a request while the
  guest is talking — the opening, a tool's return, a rescue, a rejoin, the
  mic nudge and the hand-over all go through it; the only other
  `responseCreate` is the narration take. **She never speaks first on join**
  (the guest's first words or three seconds). **The hand-over happens at a
  pause she is in** (due six minutes before the session ceiling, forced only
  in the last 90 s, the whole kept transcript carried, no unprompted first
  line). **Per-leg `MicStatusChange`** tells the room who is talking: a
  co-host-only voice is neither the guest's barge-in nor the guest's answer.
  **A sign-off before the window is cancelled on the response's transcript
  deltas**, mid-sentence. **The closing round is a state machine in the
  room**: it hands her each of the eight `ROUND_QUESTIONS` one at a time
  after the previous answer ends (trace `round: asked n/8`, `answered n/8`),
  then the last word, then the thanks; a question she asks herself once
  permitted hands the round to the room. `reasoning.effort` comes from
  `interview_runs.reasoning_effort` (default high). Every request the room
  makes to the Worker carries `X-Voices-Signature` (hex HMAC-SHA256 of the
  body; a self-contained SHA-256 checked against the standard vectors) when
  `VOICES_WEBHOOK_SECRET` is deployed to both; unset, nothing changes. The
  end-of-room webhook reports `barge_ins`, `server_turns`,
  `self_answers_blocked`, `closing_round_complete`. A `hello` session (below)
  opens without the show and never runs the round.
- **The prompt is a host's brief, not a rulebook.** `mira_system_prompt.txt`
  is ~1,500 words of positive craft in the order a conversation runs, with
  **no quoted specimen of a bad line and no dated incident narrative** — the
  network's de-seed-by-shape rule applied to Mira (seventy "That's a …" lines
  were listed and the shape moved to a one-word echo opener). The seventeen
  incident stories live in [`docs/mira_craft_notes.md`](docs/mira_craft_notes.md)
  for humans. `lessons_block` renders at most five positive show lessons,
  `relapse_recap` is empty (a rule she breaks three times is a room defect),
  `variety_block` is a shape list with no phrase instances, `fact_check_claim`
  is off the tool list by default, `carry_the_show_block` offers at most one
  previous guest an hour, named with a sentence of who they are, only inside
  this guest's subject and never as "is he right?"; the brief asks what this
  person would be glad to be asked, the question set reads the guest's
  agenda, and the T-1 prep email tells the guest the three things Mira is
  curious about. **Never add a prohibition to the live prompt for a fault the
  room can enforce** (ledger `do_not_retry`).
- **The loop can hear** (`pipelines/voices/audio_metrics.py`). `episode_metrics`
  carries `overlap_sec`/`overlap_events`, the `turn_gap_ms` distribution,
  `mira_turn_sec` median/p90, `guest_words_per_answer_median` and its trend
  across the hour, `self_answered_turns`, `echo_open_rate`,
  `closing_round_complete` and `seams`, measured from the per-speaker Whisper
  words and the room trace (`metrics_basis: audio`; the old transcript
  estimates stay a month for comparison). The retro pass PROPOSES lessons
  with a metric and evidence; **adoption is weekly**
  (`adopt_lessons_weekly.py`, Mondays), at most six show lessons, retirement
  by the motivating metric going green for three rooms, never by age; closing
  sessions are neither graded nor adopted from. **Every guest is asked**: a
  three-question survey email 24 h after the room (`guest_survey.py`,
  `/voices/survey/<token>`), sent whether or not they opened the review page;
  `survey_rating` is this show's headline number. `review_snapshot.py` reads
  the interview shows. Targets in review §7.7.
- **A guest is never the test.** `docs/age_of_ai_rehearsal.md`: a fixture
  guest (`age_of_ai_fixture_guest.js`, a second voice agent playing a past
  guest from their approved transcript, pausing mid-thought, coughing, asking
  who someone is) runs a room through the real scenario. **Since Oct 23 2026
  a rehearsal is ONE fifteen-minute room of the proposed arm** (the room
  reads a planned length under 15 as 45, so a shorter room never opens the
  round; at 15 it is required at minute 10), judged on the room's own checks (ran, no self-answered
  turns, under one overlap per ten minutes, the closing round complete with
  every question in her words and none a turn behind, no dropped session)
  and reported with its ROOM LOG (`rehearsal.room_log`: sessions, turn
  decisions, holds, the round line by line, each question handed vs heard).
  34 rooms in two days (~870 Voice Agent minutes) found four faults, every
  one from the log, none from the medians (guest words per answer ran 31-84
  on one configuration). `arms: both` keeps the two-arm comparison for a
  prompt or setting change. `rehearsal.py preflight` stops the job before
  any room when xAI refuses requests (Oct 23: six rooms placed on an account
  out of credit), and a room xAI refused stops the rest. **A scenario or
  prompt change ships to a real guest only on a PASS plus one operator
  listen.** `closing_round_complete` (live rooms too) is false on a "said
  late" or "asked again" line; it had read complete on a round that lost
  three questions.
- **The edit keeps its promises in code.** A guest's "start that again" or
  "take that out" is found in the transcript and exempt from the 25 s drop
  floor; `edit_transcript` (the transcript of the EDIT, re-stamped on its
  clock) is what the guest approves; redaction windows marked on the review
  page are cut from the SHIPPED file and `publish_episode` refuses to ship a
  file built before the windows were stored; a thank-you from Mira goes
  within the hour of the room ending with three of the guest's own lines; the
  publish-day mail carries the link, a 60-second moment, the share card and a
  return month; a five-minute **hello** two days before (`hello_sessions.py`,
  on the closing-session pattern) writes `guest_agenda` for guests who set
  none. Worker: lesson decisions check ownership, `/studio-phone` never
  redials a finished interview, gate-2 housekeeping survives one failed
  email, status is written after the dispatch, the studio copy says fifteen
  minutes, `/join` needs a token.

Operator: deploy the scenario (Actions "Deploy Voximplant scenario", which
now ships the fixture guest too), `wrangler deploy` in `workers/voices`, apply
the two migrations, set `VOICES_WEBHOOK_SECRET` on both sides, and run the
rehearsal before the next booked room. ⚠️ AUDIO on every interview.

### The Age of AI: a server turn, a guest on another call, and a sign-off too soon (Oct 22 2026)

From the Oct 22 room (run c868dac8; guards `tests/test_room_holds_2026_10_22.py`,
behaviour driven through the real scenario in a node vm by
`tests/fixtures/room_sim.js`). Rules that bind:

- **A turn the server starts after the guest spoke goes through the room's
  decision** (`markTurnStarted`): it is cancelled and `scheduleTurnDecision`
  runs, so `decideTurn` (the only path to `roundAnswered`) sees the answer.
  The closing round had stuck at question 1 for 25 minutes because
  `markTurnStarted` reset the flags `decideTurn` reads. Counter
  `server_turns_rerouted` in the end-of-room webhook (Worker `roomCountersOf`).
- **Hold mode.** When the guest's words say they are stepping away or taking
  another call (`HOLD_ENTER_RE`; "let me think" is not one), or Mira says she
  will wait (`MIRA_HOLD_RE`), the room gives her no turns, holds TIME CHECK
  and round prompts, and counts no speech as an answer, until they address
  her again (`turnsBack`: her name, "sorry about that", "I'm back",
  "where were we", "you were asking", or "Back." as its own sentence —
  the fourth rehearsal's guest came back on "Back. … Anyway, you were
  asking …" and was held silent for two and a half minutes) or three
  minutes pass (`HOLD_CHECK_IN_MS`), when she says
  one short line that she is still there, for as long as they are away. Speech
  is the backstop exit: the guest talking ≥ `HOLD_REPLY_MIN_SPEECH_MS` within
  `HOLD_REPLY_WINDOW_MS` of the end of a check-in (`noteHoldSpeech`, fed by
  `noteSpeechEnded`, the one handler for both VAD paths). **The check-in is
  that one response's `instructions` (`response.create`), never a
  conversation note**: as a note it came out as "welcome back" and the
  question again into a guest still away, and on their return her first line
  was the check-in again (third rehearsal, run e08c026c); `exitHold` drops a
  parked one. On return she
  re-asks the closing question in play and any held time note is delivered.
  The trace carries `hold: entered/left`, never the guest's words.
- **The room hears the guest's words.** Grok Voice 3.0 sends them as the
  NAMED event `ConversationItemInputAudioTranscriptionCompleted`, re-sent
  about every second with the whole item so far; the room listened only for
  an Unknown event, so no guest word ever reached it (the Oct 13 "this room
  does not get one" note was this) and every word rule had never run live.
  `noteGuestTranscript` keeps one line per item, updated in place, and runs
  the hold/stop checks on what is new. Read from the session log of a
  candidate rehearsal (Actions "Voximplant session logs").
- **Dead air is broken.** With unrequested server turns cancelled, a silence
  nobody breaks had no end: 20 s after her line with nobody speaking
  (`DEAD_AIR_MS`) she puts her last question again, more simply; at most
  `DEAD_AIR_MAX_NUDGES` (2) per silence, never in a hold or the closing round;
  counter `dead_air_nudges`. The fixture guest reconnects a dropped socket
  (`FIXTURE_RECONNECTS_MAX` 3) — one rehearsal lost it to a 1006 at minute
  two and measured twelve silent minutes.
- **No sign-off while the round is unfinished**, cut mid-sentence on the
  transcript deltas (`signOffBlockedByRound`), unless the guest asked to stop
  (`GUEST_STOP_RE`), the hard cap fired (it closes the round), or the room
  has already blocked `ROUND_CLOSE_BLOCKS_MAX` (3) — a guest is never trapped.
- **The grader** (`09_interview_retro.txt`): replying to, or acting on, a
  conversation the guest is having with someone else is a turn-taking fault,
  never "patience".
- **A candidate room is rehearsed before it is deployed.** The rehearsal
  workflow's `candidate_scenario` input uploads the branch's scenario as
  `age_of_ai_interview_candidate` with `ROOM_PREFIX` rewritten to
  `candroom-` (its own rule `^candroom-.*`; `candidate_source` refuses
  `room-`), and the fixture guest dials that prefix for the proposed arm; the
  live scenario and rule are never written. Either input also re-uploads this
  ref's rehearsal-only fixture guest (the deployed one predates the prefix and
  would quietly dial the live room). `with_hold` adds a phone-call beat to the
  fixture (`HOLD_BEATS`).
- **The rehearsal finds the guest's channel; it never assumes the left.** On
  the fixture guest's leg the stereo sides are the other way round from a real
  guest's, and the first both-arms rehearsal (run 39852548850) transcribed
  Mira's own words, seconds late, as the guest's answers in BOTH arms, so its
  FAIL compared Mira with herself. `pick_guest_channel` takes the side whose
  loudness tracks her recording least (left 0.83 / right 0.12 on that room)
  and the record says which (`guest_channel`). The workflow's `remeasure`
  input (`current:<run id>,proposed:<run id>`) measures rooms that already ran
  without running new ones. Read a rehearsal's transcript before its verdict.
  **Mira is measured from the side the guest HEARD, never her own record**:
  Voximplant stops writing her record through a long silence (the fifth
  rehearsal's three-minute hold vanished, 12:00 against a 14:45 room) and a
  single offset then put every later turn minutes early, read as seven
  self-answered turns. Post-production is unaffected (`align_to_room` places
  her record piece by piece).
- **She never nudges an empty room** (the same rehearsal: two nudges inside
  the rejoin grace after the fixture's leg dropped).
- **A fresh session runs the dead-air clock** (Oct 23, three-room rehearsal
  run 39879256504): her socket dropped just after a line, the rescue bridged
  a new session, and neither side spoke for eight minutes, because the clock
  was armed only when one of her lines ended. `resumeAfterHandover` is the
  one path after any hand-over or rescue: the owed turn, else `armDeadAir()`;
  the rescue clears her audio with the socket (guards
  `tests/test_room_rescue_2026_10_23.py`).
- **The round counts what she ASKED, not what the room handed her** (Oct 23,
  the first 22-minute room on the deployed scenario, run 4729e7b6: eight of
  eight questions, the last word and the thanks, one turn behind from
  question one). A round turn whose line carries no `?` did not ask the
  question in play: the room hands it again when the guest finishes
  (`noteRoundTurnWithoutQuestion`), or at once if they stay silent. A
  question the room handed her is never a repeat the first time her words
  carry it (`roundSpoken`); the room marks a question asked when it hands it
  over, so before this every on-time question drew a false "you asked it a
  second time" note. **Every turn the room drives in the round (each
  question, the re-ask, the last word, the closing thanks) goes as that one
  response's instructions on top of her session instructions** (`roundTurn`,
  `sessionInstructions`), never as a conversation note: the session log of
  rehearsal 0ac88c67 showed a note followed at once by `response.create`
  taking effect a turn late, every time, so each turn asked the previous
  note's question and the book, AI-interview and improvement questions were
  never put to the guest (the hold check-in's Oct 22 lag, again). Guards
  `tests/test_round_in_step_2026_10_23.py`. **A round turn that asks a
  follow-up instead is handed back too** (rehearsal 0dd50fbe: handed "who
  you should interview next", she asked about the guest's book and the
  question was lost): a turn whose question touches neither the handed
  question's pattern nor its subject (`ROUND_TOPICS`) is handed again, once
  per question, so a rewording never loops (guards
  `tests/test_round_follow_up_2026_10_23.py`).
- **She is handed the question's words, never a description of it** (Oct 23,
  rehearsal 39982637152: handed "whether they would be interviewed again" and
  the like, she asked questions of her own on five of seven turns). Each fixed
  `ROUND_QUESTIONS` entry carries its line as a third element, which its own
  pattern must hear, and the turn ends on it. **A transcript delta's words
  are the string `payload.delta`** (`deltaOf`, `noteMiraDelta`): the room
  read `delta.transcript`, so the mid-sentence sign-off cut had never fired
  and she said "you can hang up now" whole, twice, mid-round. **After a
  sign-off in the round the question in play is handed again as that turn's
  instructions** (`rehandAfterSignOff`, with "you spoke too soon" in front of
  it after the fact), never by a note; a sign-off line is never an
  asked-nothing round turn. Guards `tests/test_round_sign_off_2026_10_23.py`.
  **Her briefs never say "lightning"** (rehearsal 39987282078: handed the
  scripted words, she still ran a quickfire of her own, coffee or tea, ocean
  or mountains, in place of the advice and inspiration questions; "the five
  lightning questions" in her brief named a round and left her to fill it).
  The brief says five short closing questions whose words the room gives,
  and that they are the whole round.
- **Her line ends when it has been HEARD, not when it was generated.**
  `response.done` arrives seconds into a line that plays for half a minute
  (the welcome: 87 words generated by 21:10:41.9, playing until ~21:11:05).
  The room had read it as the end of her turn, so the dead-air clock fired
  while she was still talking, its re-ask repeated the welcome, and the guest
  heard 58 s of Mira with the welcome twice (session log of run 1ca8839a).
  `miraAudibleUntil` is estimated from her line's words
  (`MIRA_MS_PER_WORD` 320, measured ~290 on that room's recording, queued
  lines pushed back) and cleared wherever the room clears her audio
  (`miraSilenced` beside every `clearMediaBuffer`); `requestTurn` parks, and
  `decideTurn` and the dead-air clock wait, until it has passed. A cancelled
  server turn IS silent (`response.done status=cancelled` within ~50 ms, no
  audio) — read from the full session log, which the "Voximplant session
  logs" workflow now attaches whole (it had kept a 60 kB tail, the last two
  minutes). The hold check-in note asks for a few spoken words: under
  "Nothing else" it came out as the one word "Silence."

- **Seven closing questions** (Oct 23 2026, Patrick): the show's own
  question, the book, who to interview next, the best advice, who inspired
  them, how being interviewed by an AI was together with one improvement,
  and last a follow-up interview in six months to a year. Asked separately at
  the end, the two interview questions read to her as the end of the show
  (rehearsal 39991520039: three goodbyes in their place). The scenario,
  `fire_interviews.CLOSING_ROUND` (same order, without the show's question)
  and both briefs change together. **A question whose words never reached the
  guest is not answered by what they say next**: the room hands it again, at
  most `ROUND_UNHEARD_REHANDS_MAX` (2) times; each round turn says how many
  questions are still to come; after her closing thanks she has one goodbye
  and no turn to an empty room (`AFTER_CLOSE_TURNS_MAX`); no time notes once
  the round is over. `audio_metrics.closing_round` reads the round's size
  from the room's own `asked n/N` lines. Guards
  `tests/test_round_end_2026_10_23.py`.

- **Her brief names no closing question** (rehearsal 39998790684): told the
  round held "four short closing questions, one about the interview itself",
  she wrote her own ("what did you learn about yourself doing this
  interview?") and spoke its label ("That's the show's own closing
  question"). The room hands her each question's words; both briefs say only
  that, and that there is no thanks or goodbye until the room says to close.
  A turn that asks ANOTHER round question is never this one reworded, and the
  "interview next" topic check no longer takes any word "interview". Spoken
  turns end on "stop talking", never "in silence" or "nothing else" (she says
  "Silence." and "Nothing.").
- **A person can sit in a draft room**: Actions "Nerra Voices — rehearsal"
  with `invite_email` (and `candidate_scenario`) runs `rehearsal.py invite`:
  a rehearsal-only application and interview (status and session_kind
  `rehearsal`, no co-host), Mira's brief compiled from that person's own
  latest application, and an email with a studio link carrying
  `room=candidate`, which dials `mira-candidate` (routed to the candidate
  scenario by `CANDIDATE_ROOM_RULE_PATTERN`). The job waits up to 90 minutes
  for them to join, then measures the room like any rehearsal. The link and
  the address never go in a log (the repository's Actions logs are public).

Operator: deploy the scenario only after the candidate rehearsal reads PASS and
one listen; `wrangler deploy` in `workers/voices` so the new counters are
stored. ⚠️ AUDIO on every interview.

### The Age of AI: a feedback panel and Mira's picture in the studio (Oct 23 2026)

Operator-directed (guards `tests/test_studio_feedback_2026_10_23.py`). The
studio page (`age-of-ai-studio.html`) lets the guest press **Good question**,
**Move on**, one of their own agenda points ("Ask me about…", from
`guest_applications.guest_agenda` via studio-state's `agenda`,
`studioAgenda`, five at most) or type a subject (240 chars). Nothing is said
on the recording. Rules that bind:

- **The page sends `{nn:1, kind, text}` over the call's message channel**. The
  participant session relays it to the room (`relayPageMessages`) and the room
  answers with an ack (`queued` / `applied` / `noted` / `hold` / `closing` /
  `empty` / `full`). The page shows each ack in words. When no ack arrives in
  6 s, it tells the guest to say it out loud.
- **A move-on or a topic is that ONE response's instructions at her next
  turn** (`takeGuestSteer` inside `requestTurn`, after a room turn). It is
  never a conversation note, which is the round's lesson.
- **Typed text is data, fenced in quotes and stripped of quotes, brackets
  and control characters** (`cleanFeedbackText`). The trace never carries it.
- **Never during a hold or the closing round.** A press is acked
  `hold`/`closing`, and a queued one is dropped when either begins
  (`dropGuestSteer`). "Good question" only records the question.
- Every press goes to the end-of-room webhook as `guest_feedback` /
  `guest_steers_applied`, stored by `roomCountersOf`.
- **Mira's picture** (`assets/mira/mira-studio.mp4` + `.jpg`, a muted
  10 s loop) plays while the room's audio is voiced and rests on the still
  when it is quiet. With no audio access it stays still. The page says it is
  an illustration of an AI that cannot see the guest.

Operator: `wrangler deploy` in `workers/voices` (agenda + stored presses).
Deploy the scenario only on a candidate rehearsal PASS plus a listen. The
page is live on merge.

### Members-only limited series (Oct 18 2026)

Operator-directed (doc [`docs/specials.md`](docs/specials.md); guards
`tests/test_specials_2026_10_18.py`). **A limited series runs outside run_show**
— the deep-dive path is single-episode, skips the lints, gives the claims gate
no local texts and is blocked by the per-date marker — through
`engine/specials.py` + `scripts/produce_special.py` (private) and
`scripts/release_special.py` (public, only after the operator has listened);
workflow **Members-only series**. Series live in `specials/series/<id>.yaml`
(merger: 7 parts ending on the case for and the case against; peptides: an
opener + 16 peptides, each answering the same eight questions). Rules that
bind: **only pages the run READ are sources** (search summaries and social
posts never are) and an episode under `min_sources` does not produce;
**a script is written only from its sourced dossier**, the claims gate runs in
flag mode, a Peptides-hosted series carries the blocking `dose_terms` lint,
and there is no expansion retry (`MIN_SCRIPT_WORDS` fails short); **audio goes
to the private bucket under `specials/`, never a show's keyspace**; **every
paying member gets every released series** as bonus items the builder copies
into `personal/<token>/` (no Worker change); **a trailer GUID never contains
`ep<digits>`** (`trailer_guid`) so the free feed's numbering never moves;
**nothing public reads a series before `status: released`** — specials.html,
the show/homepage cards and the 14-day newsletter P.S. Episodes close on the
network's spoken AI disclosure (`AI_DISCLOSURE`, kept equal to run_show's).
⚠️ AUDIO — listen to every episode before release.

### Actions minutes: the "is there work" decision leaves the runner (Oct 19 2026)

Operator-directed (guards `tests/test_actions_minutes_2026_10_19.py`). Measured
Oct 16-18: ~1,790 runner-minutes a day (the repo is PUBLIC, so standard-runner
minutes are not billed — the cost is queue depth in the morning slate and the
watchdogs), of which ~460 were jobs starting Python to decide there was nothing
to do. Rules that bind: **multilingual.yml and nerra-daily.yml have no
`workflow_run` trigger.** `scripts/followup_dispatch.py` runs at the end of
every show run: it dispatches the multilingual sweep for ONE show only when the
show published a public episode of an auto-translated show whose video is not
still rendering (the video job dispatches `--after-video` once the gallery
manifest is pushed), and it wakes the Nerra Daily gate only for a roster show
landing AFTER `RELEASE_EASTERN` with no edition built (the scheduler Worker
dispatches the gate at the release and at the hold's end; a failed run wakes it
too — the Oct 18 lesson). A single-show multilingual dispatch answers without a
checkout; the cron passes remain every catch-all. **The Voices Worker's
half-hour producer tick asks Gmail first** (`producerTickDue`: the inbox job's
own query on both mailboxes, the same service account, fail-open; secrets
`GMAIL_SERVICE_ACCOUNT_JSON` / `GMAIL_DELEGATED_USER` on the Worker are
optional — unset dispatches as before). **A push to main that changes only
generated output never runs the test suite** (`paths-ignore` on test.yml and
e2e.yml; pull requests are never filtered). Operator: `wrangler deploy` in
`workers/voices` (and the two Gmail secrets to turn the gate on).

### The Oct 19 slate: the Eastern schedule's first day, the video job's first (Oct 19 2026)

Review [`docs/reviews/slate_review_2026_10_19.md`](docs/reviews/slate_review_2026_10_19.md);
guards `tests/test_slate_2026_10_19.py`. 26 runs dispatched to the minute, 21
published, the edition complete at 06:35 ET, 11 of 12 videos published. Rules
that bind: **a bold `**Title: Outlet**` line and its paragraph are ONE item**
(`digest_lint.items` — MAG 7 read 3 unsourced of 7 sourced); **the expansion
retry asks for STORIES when a section is under its `min_items`**
(`generator.digest_item_shortfalls`, ranked above the "fewer items at full
depth" rule — FF Ep227 was generated three times with three stories from 44
articles and padded to the word floor each time); **a bold-wrapped heading is
never the hook** (`promote_hook_to_blockquote` — M&A Ep208 put "# Models &
Agents" on 337 related cards); **the IMOCA boat page is a plain `<th>` table
now** (all 20 fleet pages had failed nightly); **a known platform sender is a
platform notice without a model call** (`classify.PLATFORM_SENDERS`); **the
fire-tick gate reads interviews three hours around their slot**, never two
days. AI Chips Ep027's $2,599 was corrected to Nvidia's $2,399 (`where: both`
— operator: re-synthesize). Open: Nerra Daily Ep059 shipped 8 of 14 segments
behind the Oct 18 re-runs and has no `--replace`; the Sunday segment aired
compressed sentences on three shows (⚠️ AUDIO, second flag); Top World and
Prediction Markets' 4.7 scripts cover half their digests; the forced MAG 7
review was lost to a push failure and needs a re-dispatch.

### The smoke step stopped the slate (Oct 18 2026)

Slate review; guards `tests/test_slate_2026_10_18.py`. **A per-show smoke
step never runs a test that scans another show's committed content**: one UC
sentence ("Lark et al.,") failed the book-release seam guard, which ran in
every show's smoke step, and every show after UC (SpaceX, AI Chips, MAG 7,
Prediction Markets, Top World, Vancouver, two desks) died before generating —
the guard now exempts ordinary abbreviations and runs only in Run Tests. **An
error event inside a stream is a status error**: xAI's "at capacity" arrives
mid-stream as the bare `openai.APIError`, which no retry set named (FF died);
`_stream_completion` raises it as `RateLimitError` (capacity language) or
`InternalServerError`. **Nerra Daily wakes after a failed show run too** —
every trigger had been skipped and nothing built the edition. **A story
cluster is anchored on its lead**: single-link chaining folded six unrelated
Tesla stories into one item (`engine/story_clusters.py`). **The hook gate
matches at 4 shared words with generic words ignored**
(`RecurrenceIndex.hook_match`, `HOOK_GENERIC`; it had fired on 10 of 20 SpaceX
days and on M&A's {agent, coding, models, real}). **MIT's stop parser reads
spelled numbers and "stop N% below entry"** (5 → 21 of the last 45 picks; it
is read at pick time, so no recorded trade changes). **The run budget is 70
min under an 80-min hard kill** — the audio is pushed first, so the time buys
only the video (the render budget had dropped 5 of 15 long-forms on OV, M&A
and MIT). Milestone notes never repeat the episode number (⚠️ AUDIO on round
episodes). The homepage never calls an earlier day's flagship episode or
edition "this morning's" / "today's". **A killed audio-first checkpoint
leaves no rebase behind**: Top World's checkpoint hit the 300 s timeout inside
`git pull --rebase`, the leftover `.git/rebase-merge` failed every later push
attempt as a "conflict", and the recovery branch carried the half-replayed tree
(a workflow change), which GitHub refused — the episode was lost from git.
`_checkpoint_publish` now kills the whole process group, `_restore_after_checkpoint`
aborts the rebase and un-commits the unpushed checkpoint, and
`push_show_artifacts.sh` clears a stale rebase before each attempt. Operator: the scheduler Worker still
fires on the Oct 9 UTC table (runs at :01/:16/:31/:46) — `wrangler deploy` in
`workers/scheduler`.

### The 24-hour review (Oct 18 2026)

Six reviewers over everything Oct 17 14:00 – Oct 18 14:00 UTC (review:
[`docs/reviews/review_2026_10_18_24h.md`](docs/reviews/review_2026_10_18_24h.md);
register `review-24h-2026-10-18`; guards `tests/test_review_2026_10_18.py`,
`tests/test_pinned_comment_2026_10_18.py`). Rules that bind: **a template
renders through `format_map` with every field supplied, never a swallowed
`KeyError` that returns it raw** — every long-form YouTube comment since Jul 18
read "{show_page_url}"; **a hook article's flags survive the merge**
(`engine.hook_articles._FLAG_KEYS` — the PM Board's exemption and venue lint
had read nothing); **the coverage floor reads one-line, unbolded-numbered and
`**Title:** Outlet` items** (`engine.claims._coverage_items`); **a feed
rebuild keeps unnumbered trailer items** (`engine.publisher.
_unnumbered_trailer_items`); **nothing links a scheduled video before its
`publish_at`** (recorded in the video index; `release_schedule.
is_still_scheduled` — homepage, X teaser, blog button); **the checkpoint blog
render gets `_md_path`** (claims panel, chapters, corrections); **the
structural retry has a deadline** (`_structural_retry_deadline`, daemon
thread); **an outcome hook is never a re-telling** (`story_recurrence.
OUTCOME_WORDS`); **empty headings are dropped after validation**
(`drop_empty_sections`); a Wayback citation verifies against its original; a
weekend close says "closed Friday at" (⚠️ AUDIO). Not fixed: Nerra Daily has
no `--replace` for an edition built before late re-runs; FF's expansion
claims drop is unexplained by the committed data. Operator: `wrangler deploy`
in `workers/scheduler` (still the Oct 9 UTC table), delete the placeholder
comments on past long-forms.

### The 48-hour review (Oct 18 2026, evening)

Three reviewers over everything merged Oct 16 19:00 – Oct 18 19:00 UTC, read
against the day's committed episodes and runs (guards
`tests/test_review_48h_2026_10_18.py`). The day itself: 16 of 16 shows
published, audio-first pushed on every one, spoken-text gate 16/16, main
green; the video job has not yet run for real (merged after the slate —
Oct 19 is its first live day). Rules that bind: **every model- or
form-written string on the homepage goes through `| e`** — the "Also in
this episode" headlines and the interview cards' guest, identifier, co-host
and dek rendered raw (a poisoned headline put 16 live `onerror` tags on the
front page in a test render); **a `wrangler.toml` never carries a
placeholder id** — wrangler validates KV ids at upload and the `SUB_COUNTS`
placeholder had blocked every pending gallery-Worker deploy (the block is
commented out until the namespace exists; the Worker no-ops without it);
**the homepage's show-YAML loaders are process-cached**
(`_registry_show_config`, `_listening_languages` — 145 loads were 15 of the
render's 18 s, ~26 renders a day); **`pick_videos` reads the build's `now`**;
**the summaries `datetime` is an aware UTC stamp** (`engine.publisher`,
`build_daily_edition`). **The structural digest retry snapshots the claims
and combined-script stashes and restores them on every path that keeps the
original** (`peek_/restore_stashed_claims`, `snapshot_/restore_combined_script`),
and a generation its caller abandoned (`_call_with_deadline` marks the
thread `nerra_abandoned`) never writes a stash — the retry's ledger had been
pairing with a digest that never shipped. **Both chapter passes use
`voice_intro_delay` alone** (the estimate had added `intro_duration`, 3 s
late on every music show). **The video job's commit step is
`always() && !inputs.rehearse` and the done marker is written BEFORE the X
stage** — a job that died after uploading lost its YouTube index and the
alert invited a duplicate upload; the multilingual cron passes now wait for a
running video job like the `workflow_run` branch does; `x_queue.enqueue`
forgets a copy it hosted when the row already exists; `_schedule_refused`
needs the error to name the publishing time, never a bare 400. **The Show
Review Agent prints git's stderr and retries the push three times** — the
18:46 mag7 run lost its review to a push rejection nobody could read.
Content: two corrections filed and applied (UC Ep146's "corn prices rose
roughly 30 percent 2008–2016" — they fell; FPD Ep134's 630TS "weighed
roughly as much as a small battleship"); the UC restock's duplicate
autopilot topic pruned and the starling brief's Shakespeare-aviary story
marked as the myth its own first source calls it; the Sunday segment names
people as the week's coverage did (Omni View Ep209 said "Lula and
Bolsonaro" for Flávio Bolsonaro — ⚠️ AUDIO on Sundays). Read and not acted
on: the five desks are dark on `no_member_demand` by design; MAG 7 Ep026's
opaque 4.7 prose ("a shattered dot io note") is a ledger item for its next
review, not a code fix. Operator: `wrangler deploy` in `workers/gallery` now
works; the scheduler Worker still fires on the Oct 9 UTC table.

### The video renders in its own job; Shorts on the front page (Oct 18 2026)

Operator-directed (register `video-job-2026-10-18`, `homepage-shorts-reel-2026-10-18`;
guards `tests/test_video_job_2026_10_18.py`, `tests/test_homepage_shorts_reel_2026_10_18.py`).
**Video no longer shares the show run's time limit.** It was 67-82% of a flagship
run and the 70-minute budget cost the long-form on 5 of the last 14 episodes of
Omni View, Models & Agents and Modern Investing. Under the workflow
(`NERRA_VIDEO_JOB=1`) the show run writes `digests/<dir>/.video_pending_<date>.json`
before the audio-first checkpoint (so it rides the audio commit), sends the
newsletter, and stops; `.github/workflows/render-video.yml` ("Render Episode
Video", job `render (<show>)`) checks out main, fetches the MP3 back from R2
(the raw URL, never the OP3 prefix), runs `run_show.py <show> --video-phase
--date <date>` under its own 110-minute watchdog, commits
"Auto-generated: <show> <date> (video)", and refreshes the homepage in its own
concurrency group (never `finalize-shared-pages`: a short job would supersede a
pending full finalize). **The video and X code is the same code**:
`_make_feed_writer`, `_make_blog_writer`, `_run_video_stage` and `_run_x_stage`
were moved verbatim out of `run()` with every variable they read as a keyword
argument; an inline run (a local run, `--test`, a show with no video,
`NERRA_VIDEO_JOB=0`) calls them in the old order. **The X post moves with the
video** (it carries the Short; the full episode replies under it); a show with
no video keeps its X post in the show run. The video job's credentials must
equal the show run's (a test compares the env lists). `scripts/video_job.py
dispatch` starts it after the show run's final push; the scheduled `sweep`
starts a handoff whose dispatch never arrived and **never retries a handoff
that already has a run** (a failed run may have uploaded before it died —
re-run it by hand). A `.video_done_<date>.json` makes a second dispatch a
no-op (`--force-video` overrides). Multilingual runs after the video job too
and waits for a pending video (both write the show's summaries and posts; the
dubs need its scenes). Revert = repo variable `NERRA_VIDEO_JOB=0`.

**The front page carries a Shorts reel** under the flagship band: the newest
English hook Short of each public show, one per beat before repeating, each
card the episode's own portrait scene (never a YouTube thumbnail), a link to
the show, and an in-page player (`<dialog>`, focus-trapped, prev/next, swipe)
that loads the youtube-nocookie embed only on click and falls back to a
"Watch on YouTube / Next Short" panel when YouTube refuses an embed. A Short
row with `preview_url` (the video job cuts a muted ~6 s 360x640 loop with
`engine/short_preview.py` and uploads it to `previews/<slug>/`) plays muted,
only in view, never under reduced motion or Save-Data. `play_short`,
`select_short_show`, `play_short_unavailable` are GA4 engagement events.

### What the flagship rehearsals showed in the video (Oct 18 2026)

Three no-publish rehearsals (SpaceX Ep134, Tesla Ep638, FF Ep226) measured
frame by frame (register `video-pass-2026-10-18`,
`hook-short-motion-ab-2026-10-18`; guards `tests/test_video_pass_2026_10_18.py`).
Rules that bind: **a slot never repeats the previous picture when another image
fits the chapter** (one sharing a word with its title, else a library scene; an
unrelated story's image never fills in — `engine.scene_scheduler._alternatives`),
and **the slot cap never merges same-image neighbours first** — each slot is its
own Ken Burns move, and merged they became one crawl over a still (FF held one
picture 74 s); a merge that would put an image beside itself goes last. **A fact
card shows only a label that reads** (compound units join the figure — "1 GWh",
"230 mph", "37 million light-years"; the label stops at a comma, before a credit
or a joining word; a fragment drops the card unless the figure's unit explains
it). **A Short ends on its last full sentence** inside its final 8 s
(`engine.shorts_selector.end_on_sentence`, metric `short_durations`). **Burned-in
captions rejoin Whisper's split tokens** ("107" ".6" "%" →
`engine.captions.merge_split_words`). **The outro card's show count comes from
`generate_html._public_shows`**; screenshots refresh through Actions "Capture Site
Screenshots" (monthly + on demand — this sandbox's Chromium does not trust the
proxy CA). **The hook motion clip runs on even date ordinals only**
(`youtube.hook_short_motion_alternate`; odd days record `control_stills` /
`control_broll`, never `hook_stills`); readout `hook_motion_vs_control_d3`.
**No show renders an Instagram/TikTok variant while no workflow carries the
posting secrets** (Tesla/SpaceX off). Render and metadata only.

### The follow ask on @nerranetwork, and a render budget sized from the audio (Oct 15 2026)

Operator-directed (register `x-follow-ask-2026-10-15`,
`long-form-render-budget-2026-10-15`; guards
`tests/test_x_follow_ask_2026_10_15.py`). **Every @nerranetwork post had ended
on one identical closer and none asked for a follow.** `engine.x_post.post_closers`
now rotates the closer and, on about one post in four, swaps in a one-sentence
follow ask (`FOLLOW_ASK_CLOSERS`): decided by the calendar and the show's place
in the X POSTING ORDER, so a daily show asks every fourth day and posting
neighbours never ask together. **Oct 17 2026: the order is derived, never
typed** — `FOLLOW_ASK_CADENCE` holds membership and weekday only, and
`FOLLOW_ASK_ROSTER` is sorted by the X slot rank
(`engine.release_schedule.x_posting_order`, Nerra Daily first); a daily show's
phase is its rank among the daily posters, and a weekly show asks once in each
block of four of its weekdays, on a day neither neighbour asks. The
ask is used only when the hook fits whole, and every list ends on the old
closer, so no hook is clipped that was not clipped before. **A show that posts
to the network account must be on the roster** (CI fails otherwise). run_show
records `x_post_follow_ask`; Nerra Daily asks by its edition date. The follower
count is read in X analytics by hand. **Nerra Daily's X post is QUEUED into its
reserved 7:00 ET slot** (`x_queue.enqueue(slot=...)`, the cover hosted on R2
per episode; `x_post_queued` / `x_post_queued_for` in the edition metrics) and
never also posted directly; no queue or a failed enqueue posts at build time as
before. nerra-daily.yml carries the queue's `VOICES_SUPABASE_*` secrets (guards
`tests/test_x_edition_slot_and_follow_phase_2026_10_17.py`). **The long-form render is budgeted at
2.1x the audio** (`engine.video.estimate_long_form_render_seconds`, measured
median 1.91x / p90 2.05x over 60 renders; the 600 s stays as the floor):
Models & Agents Ep204 started a 1,493 s render with 1,189 s left, uploaded the
long-form, died on the alarm before committing, and the fallback cron uploaded
a second long-form five hours later. Metric `long_form_render_need_s`.

### Gated shows — members-only and public-weekly (Oct 13 2026)

Operator-directed: some shows will publish only for Nerra Personal members
who carry them, some publicly one weekday with the daily episodes for
members. **`engine/access.py` owns the decision; `access:` in the show
YAML is the setting (`public` default — every show is public today and a
guard says so).** Rules that bind: the demand gate runs before any spend
and skips `no_member_demand` at zero, but UNKNOWN demand produces (a paying
member may be waiting); an unknown `access.mode` RAISES, never publishes;
a members episode stops between the rehearsal stop and the publish phase —
audio to the private bucket, text to `digests/<dir>/members/`, the ledger
`members/episodes.json` (also a numbering source) — so no public surface
needs a filter: they all read the show directory's top level. **A new
consumer that globs a show's digests recursively must skip `members/`.**
Nerra Daily reports a members day as skipped (`members_only`); the
Personal builder alone passes `include_members=True`. Text stays in this
public repo by operator choice; only audio is private. **Oct 15 2026 — the five
Omni View regional desks are the first gated shows** (operator-directed;
register `desks-members-only-2026-10-15`; guards
`tests/test_desks_members_only_2026_10_15.py`): `members_only` with
`access.unknown_demand: skip`, so an unreadable demand skips
(`member_demand_unknown`, the audit warns) instead of producing for nobody —
the gallery Worker answered 404 on `/api/admin/show-demand` that day. A
`no_member_demand` day is the gate working and the audit stays quiet. Top
World reads a desk's digest from `members/` too (headlines and publisher URLs
only). A members-only show's page is refreshed by the nightly
(`scripts/list_unowned_show_pages.py` — its run never writes the page), and no
show plugs it on air. Doc:
[`docs/nerra_personal.md`](docs/nerra_personal.md) "Gated shows". Guards:
`tests/test_personal_gating_2026_10_13.py`,
`workers/gallery/test/personal.test.ts` ("show demand").

### Network review — the Oct 12-13 slate (Oct 13 2026)

Operator-directed (review:
[`docs/reviews/network_review_2026_10_13.md`](docs/reviews/network_review_2026_10_13.md);
ledger `network` 2026-10-13; register `network-review-2026-10-13`; guards
`tests/test_network_review_2026_10_13.py`). 45 episodes, 100% run success,
spoken-text gate 45/45, every script arm served its own model. What binds:
**sourcing narration is cut in code, at clause level where the sentence
carries a fact** (`engine.absence_sentences.cut_sourcing_clause` — "X is
the source for …, and the current reading is eleven degrees" keeps the
temperature; five more shapes and the Progress Watch echo without a colon;
sweep every committed script before widening a pattern); **a hook that
re-tells a story covered on two or more recent days is a structural
defect** (`HOOK_RECURRENCE_MIN_DAYS` in run_show — Tesla Ep632 led with
Solar Roof a ninth time under the note that said not to); **a fast_info
quote equal to its previous close is the prior close** (SpaceX
`_no_trade_yet` — before the first pre-market print Yahoo returns the
close as the last trade); **a launch designator is two numbers, never a
range** and **a `.TO` ticker is spelled** (`assets/pronunciation.py`);
**Whisper's low-probability echo tokens are dropped before they reach
captions** (`engine.transcripts.drop_echo_words`, calibrated: the echo
reads 0.016-0.022, a real repeat 0.5+); **a lead section is matched by
name OR "Top " prefix, and Reddit joins X in the lead-source rule**
(`is_lead_section` — the lint had been a no-op on five of its own shows);
**a lint a show opts into is a rule its prompt states** (three cohort
prompts lacked the WYNTK clause and Prediction Markets regenerated 5/5
days); **MIT's Market Pulse reads `{nasdaq_benchmark_line}` from the hook**,
never the digest's copy; **MAG 7's Company Desk floor is 1** (the prompt
says never pad); **a prompt never types a sibling's cadence word**
(guarded); **the Voices fire-tick asks Supabase before dispatching**
(`fireTickDue`, fail-open, :00/:30 unconditional — 288 no-op jobs a day;
operator: `wrangler deploy workers/voices`). ⚠️ AUDIO: arXiv on M&A, the
desks' filtered scripts, MIT's Market Pulse, UC's cross-promo, Top World's
first sentences.

### Cost-efficiency pass (July 29 2026)

Six changes that cut spend without touching what a listener gets. The
rule for the whole pass was **measure first** — every item below was
justified from committed data, not from reasoning about where waste
"should" be. Drift guards: `tests/test_cost_efficiency_pass.py`.

Context: the dashboard's tracked figure (~$29/30d) was roughly a third of
real spend. Adding the pieces it did not count — multilingual (~$38/mo)
and Grok Imagine (~$50-60/mo, only counted since July 28) — the true
total is ~$110-125/mo. The two largest lines were the two least measured,
which is why measurement leads this list.

- **Per-language OP3 measurement.** Multilingual is ~1/3 of spend and its
  audience was measured NOWHERE: the per-language enclosures carry the
  OP3 prefix, but `fetch_op3_stats.py` only ever resolved each show's
  English feed, so `api/op3_stats.json` had zero language-track entries
  and a language with no listeners looked exactly like a popular one.
  The fetcher now also resolves the 14 feeds the network actually pays to
  produce (scoped to each show's `multilingual.languages`, not the 44
  feed files on disk) into a separate `language_feeds` section — separate
  because every consumer iterates `shows` keyed by slug. The dashboard
  gains `multilingual.by_language` (downloads vs approximate cost) and
  per-show `audience_by_language`. **This is a decision instrument, not a
  saving:** after 2-4 weeks, a language reading zero across several weeks
  is a candidate to switch off in the show YAML. Today's split is FR
  ~$20/mo (7 shows), RU ~$13/mo (4), ZH ~$8/mo (3); RU feeds @NerraRU and
  earns its keep regardless, ZH has no channel and no directory listing.
- **16:9 scene generation follows the render.** Shorts-only policy days
  still generated 4 fresh 16:9 Grok Imagine scenes, but those feed only
  the long-form slideshow, its thumbnail, and the gallery — Shorts use
  their own 9:16 set. On a shorts-only day for a show with no
  video-podcast feed, three of four paid images were never seen. Now 1
  (thumbnail base + gallery contribution); the 9:16 set is untouched, and
  `video_podcast.enabled` shows still get all four because they render
  long-form regardless of tier. ~$0.06/episode on tier-C shows.
- **xAI search-tool spend is counted.** Server-side `x_search` /
  `web_search` bill per SOURCE consulted; the Responses path returned
  only text, so every search-fetching show under-reported its spend
  (flagged as uncounted by the July 24 pass, still missing after the July
  28 cost fix). `digests/xai_grok.py` accumulates usage per process — the
  fetch layer has no tracker reference — and run_show drains it into the
  episode's credit file via `engine.tracking.record_search_usage`. Rate
  is `SEARCH_COST_PER_SOURCE` ($0.025), env-overridable with
  `XAI_SEARCH_COST_PER_SOURCE`. Also wired `record_render_seconds`, which
  the July 28 pass shipped with no caller.
- **Single-pass long-form render is now the default** (was opt-in behind
  a repo variable). A/B on both production shapes at 1920x1080: uniform
  stills 24.6s -> 16.2s (-34%), chapter-schedule + burned-in captions
  22.3s -> 17.2s (-23%), with outputs equivalent — identical duration,
  frame count, geometry and codecs, mean pixel difference < 0.3/255 at
  every sampled timestamp, identical scene timeline, matching brand pill
  / URL pill / caption rendering. `NERRA_SINGLE_PASS_RENDER=0` forces the
  legacy path, which also remains the automatic fallback on any fused-
  command failure. The escape hatch now covers the RU/FR dub renders too.
  Render-only, no audio — outside landmine #17.
- **The podcast-side expansion retry is off** wherever a digest-side
  lever exists (11 shows). See the superseded note in the June 2026
  network-pass section above for the measurement. **A/B-listen the first
  post-merge episode on a show that used to fire it** — when the retry
  fired, its output was what shipped.
- **`CLAUDE.md` trimmed ~185 KB -> ~124 KB** by moving the dated per-show
  quality-pass narratives verbatim to
  [`docs/show_review_history.md`](docs/show_review_history.md), keeping
  each show's structural facts plus a new "Live constraints" block for
  the rules that still bind (Colossus/Anthropic is real, length is
  digest-side only, de-seed by shape, the grok-4.3 plateau, MIT not
  live-trading ready). This file is loaded in full at the start of every
  Claude Code session and replayed across the agentic loop, so its size
  is a per-session cost on all future work — the June 2026 token review
  found exactly this pattern was the network's largest Anthropic line
  item before the review agent moved to Grok.


### Funnel instrumentation + RU SpaceX pilot + Shorts motion A/B (July 30 2026)

Three connected pieces answering the July 18 audit's central finding
(world-class factory, funnel is the product gap). Full doc:
[`docs/funnel.md`](docs/funnel.md); drift guards:
`tests/test_funnel.py`, `tests/test_shorts_ab.py`,
`tests/test_ru_spacex_pilot.py`.

- **Instrumentation.** [`engine/funnel.py`](engine/funnel.py) is now the
  ONLY builder of funnel URLs / campaign ids / capture tags (see the
  rule at the top of this file). Nightly
  [`scripts/build_funnel.py`](scripts/build_funnel.py) joins
  youtube_stats + op3_stats + ga4_stats + buttondown_stats into
  **`api/funnel.json`** — four stages (reach → click → visit → capture),
  per show / channel / campaign / A-B variant, plus a dashboard card.
  `fetch_ga4_stats.py` gained the `sessionSource/Medium/CampaignName`,
  landing-page and `newsletter_signup` conversion reports (without the
  campaign dimension nothing on the site could be traced to a video);
  `fetch_buttondown_stats.py` gained per-tag counts (the bare total
  cannot attribute anything). **Honesty rules are load-bearing:** an
  unmeasured stage reports `null`, never `0`; rates stay `null` below a
  30 denominator; unparseable GA4 campaigns are summed under
  `unattributed` with an `attribution_coverage_pct`, so the report never
  implies it sees everything.
- **RU SpaceX pilot.** @NerraRU is the network's highest-reach surface
  (~25,800 views/30d vs ~13,800 EN) and every one of its Shorts pointed
  at the bare English homepage. Now: `funnel.destinations.ru` →
  **`ru/spacex.html`** (generated by `generate_ru_landing_page` from
  `templates/ru_landing.html.j2`, path driven off the SAME YAML field the
  descriptions link, so page and link cannot drift), one Russian ask
  («Хроника SpaceX», a Sunday letter), footer show-picker suppressed via
  `hide_footer_subscribe` (default false → every other page unchanged),
  and the letter is actually sent by
  [`scripts/send_ru_spacex_weekly.py`](scripts/send_ru_spacex_weekly.py)
  + `ru-spacex-weekly.yml`. Captures carry `list` + `source` through the
  Worker's **server-side allow-list** (`resolveSubscribeTags`) — the
  client names a list, the server owns the tags. Also fixed: the RU
  funnel comment posted NOTHING on most days because @NerraRU is
  shorts-only and `long_url` was empty; it now falls back to the lander.
- **Shorts motion A/B.** SpaceX Short #1 stays stills (control), Short #2
  renders over Grok Imagine video ([`engine/shorts_ab.py`](engine/shorts_ab.py)
  + `build_short_video(clip_paths=…)`), same episode/audio/channel/day.
  **Not a revival of `video_clips_enabled`** (still false everywhere —
  that was the retired long-form pilot): bounded to ~3 clips on one 35 s
  Short, a hard `shorts_ab_max_cost_usd` checked BEFORE each request, and
  a fallback that ships stills AND RECORDS stills (a treatment arm
  containing disguised control episodes is worse than no experiment).
  ~$1.05/ep ≈ $32/mo — **read it and end it.**
  [`scripts/build_shorts_ab_report.py`](scripts/build_shorts_ab_report.py)
  → `api/shorts_ab.json` refuses to compare below 14/arm and reports a
  95% CI (Welch), not a p-value. Render/metadata-only — outside landmine #17.

### Video enhancement pass — hook-first Shorts + render look v2 (July 31 2026)

Operator-directed ("enhance the videos 200%+; one Short per channel is
the starting hook sequence"). Render/metadata-only — outside landmine
#17. Drift guards: `tests/test_video_commands.py`,
`tests/test_captions_ass.py`, `tests/test_scene_scheduler.py`,
`tests/test_shorts_selector.py::TestHookFirstWindows`,
`tests/test_shorts_ab.py::TestWindowParityDeconfound`,
`tests/test_youtube_feedback_loop.py`.

- **Hook-first Shorts:** Short #1 on every channel (EN/RU/FR) starts at
  the episode opening (= the hook since the cold-open pass); smart
  windows fill the rest (`engine.shorts_selector.hook_first_windows`,
  one implementation, three call sites). Every Short records
  `window="hook_open"|"qualified"|"filled"|"legacy_fallback"` in the
  video index → analytics, so hook-vs-smart is attributable. Config:
  `youtube.shorts_first_is_hook` (default true; **spacex pins false
  until the motion A/B reads out** — flipping mid-experiment would
  confound arm with window position).
- **Render look v2** (`RENDER_LOOK_VERSION = 2`, recorded per episode so
  analytics segment by visual era): network color grade
  (`_GRADE_CHAIN`: eq + vignette + gradfun, no grain) on every [bg];
  Shorts-only `unsharp`; long-form 0-4s fading hook title (autofit,
  h*0.42); long-form per-word ASS captions
  (`transcript_to_ass_full`, SRT fallback, `long_form_captions_path`
  metric); Shorts hook alpha-fade + end-card fade-in; active-word
  `\t` pop; 8-move episode-seeded Ken Burns at 1.06/1.09/1.12
  (CRC32-of-stem seed; `kb_extended=False` keeps byte-identical legacy
  for A/B-enrolled shows); accelerating open (<60s slots cap holds at
  8s); supersampled v2/v3 pills. The four items HELD for the motion-A/B
  verdict all shipped once the A/B was formally ENDED as unreadable
  (operator, 2026-08-14 — enrollment froze at n=4 via the merged spacex
  review PR #973; see `docs/experiments.yaml` `shorts-motion-ab-stalled`):
  progress bar (A3, earlier), Shorts transition split (A2 — vertical
  slideshows join on `_SHORTS_XFADE_S` 0.25 s vs long-form 0.6 s),
  punch-in easing (E1 — alternate Shorts segments front-load their Ken
  Burns travel, `ease="out"`), long-form closing beat (D2 — the final
  scene settles on a gentle centred push-in before the outro card).
  Drift guards: `tests/test_video_commands.py::TestUnheldRenderUpgrades`.
- **Learning loop:** title hints mined per-kind (Shorts retention no
  longer steers long-form titles) with fragment/dateline exemplars
  banned; gallery-retention flywheel CLOSED (bounded ±10 ranking prior
  in `gallery_library._rank` — overlap stays primary, missing report =
  legacy order); motion-A/B window-parity de-confound (top-two windows
  swap by episode parity on enrolled shows).

### Narrative-matched imagery + delivered resolution (Sep 2026)

Operator complaints about video quality traced to two silent defaults:
every Grok Imagine prompt led with a static `image_queries` phrase (so
each Tesla episode shipped the same four pictures) and the library blend
padded the slideshow with older images ranked by weak token overlap.
Now `engine/scene_briefs.py` writes one photographable scene per STORY
(one Grok text call; deterministic fallback) and those briefs LEAD the
prompts (`build_image_prompts(scene_briefs=)`); one fresh 16:9 scene
per story (`scenes_per_episode`) + `short_scenes_per_episode` 9:16;
Shorts open on the scene matching their own window text
(`short_visual_extras(fresh_scene_context=)`). **The image endpoint
ignores `size`** (Sep 3 2026 — every one of 7,500+ committed sidecars
is 1280x720 whatever was requested): the request carries the documented
`aspect_ratio` + `resolution: "2k"` (`engine/grok_imagine.py`, `size`
only as the ladder's fallback) and the delivered width is a per-episode
metric (`grok_image_px_max`) — read THAT, never the request. **Library
overlap is counted on salient tokens** (`gallery_library._common_tokens`:
document frequency > 20% dropped from both sides — "tesla"/"optimus"/
"cinematic" sit in ~100% of the library and matched every image).
**Chapter title cards are a fit gate on `engine.titles.CHAPTER_CARD_MAX`,
never a clip.** Register: `scene-briefs-narrative-imagery`,
`image-source-2k-and-story-matched-shorts`, `video-quality-round-3`
(readouts 2026-09-23). Guards: `tests/test_scene_briefs.py`,
`tests/test_video_commands.py::TestChapterTitleCards`.

**Sep 9 2026 — two numbers that lied, one each way.** (1) The Data
API `channels().list statistics.viewCount` stopped tracking Shorts
views on 2026-09-02 on all three channels (@NerraRU +19/day against
~4,000 Analytics views/day); the `detect_view_cliffs` alarm differenced
that counter and paged CHANNEL VIEW CLIFF for four nights while every
channel was UP (EN +56% WoW). **The Analytics `day_series` is the only
view-flow source for alarms and scorecards; `total_views` in
`api/youtube_channel_history.json` is a lower bound**
(`detect_counter_divergence` says so nightly). (2) A new metric set on
the publish result is NOT a metric until it is on the allowlist in
`engine.pipeline.record_youtube_outcomes` — `grok_image_px_max`
shipped 09-03 and recorded nothing for six days. 2K is confirmed from
the sidecars: 2816x1584 since 09-03.

**Sep 9 2026 — captions: the long-form layer is the uploaded TRACK,
never the pixels.** The Aug 1 network-wide burn-in assumed CC defaults
off; YouTube remembers CC per account, and the operator's screenshot
showed YouTube's caption box drawn over the burned per-word captions
on long-form. `long_form_burn_in_captions: false` in `_defaults.yaml`
(guard `TestLongFormCaptionLayer`); Shorts keep burn-in and upload no
track. **Sep 17 2026:** `transcript_to_srt` never drops a real word —
Whisper closed SpaceX Ep103 on the single word "comments." at 0.34 s and
the under-0.4 s skip lost it from the track; short segments are now HELD
to the minimum (`artifact_floor_seconds` 0.15 s still drops blips). Arabic (or any other language) captions on a Short are
YouTube's auto-generated track auto-translated by the VIEWER's
caption-language preference — nothing in the pipeline carries a
language but `en`/`ru`/`fr`; it is a player setting, not a bug to
chase in code. Same day: EN `filled` Shorts (the second Short that
exists only to reach the requested count) earned a median of 3 views
across 17 uploads while the hook Short earned 48 — `shorts_fill_to_
requested: false` (EN path only; RU/FR dubs pick their own windows and
their filled Shorts earn ~225). Register: `long-form-captions-track-only`,
`en-shorts-no-fill`.

**Sep 9 2026 — Grok's retention plan, checked against the data**
(review: [`docs/reviews/youtube_retention_review_2026_09_09.md`](docs/reviews/youtube_retention_review_2026_09_09.md)).
Three of its items survived the recompute and shipped, all render-only:
**the Shorts end card asks for the SUBSCRIBE** ("WATCH FULL EPISODE"
pointed at a surface the burned card cannot link; the site funnel it
fed measures 8 attributed sessions from 246k views; the headline also
gained shrink-to-fit — 18 characters at 88 px had run off the 1080 px
card since May); **the long-form opening slot draws from the fresh
pool only** (`scene_scheduler`: one token of title overlap outscored
the fresh bonus, so an older library scene could open the video);
**fact cards** (`engine/fact_cards.py` — spoken figures as timed cards
from the Whisper words, which arrive as digits split across tokens;
`youtube.fact_cards_enabled` on tesla/spacex/FF, M&A/MAB/OV control).
Rejected with numbers: replacing the long with a 90–120 s lead cut (no
such knob exists; the long is the Apple video asset and the top EN
subscriber source per video), pausing FPD (34 views/Short — above
Omni View; the dead uploads are env_intel, finansy_prosto and MIT's
dubs — operator's call), "keep fill-to-requested" on EN (median 3
views), and anything spoken (landmine #17). `api/gallery_retention.json`
has never held a tag — do not cite it. Register: `shorts-subscribe-cta`
(metric `short_subs_per_video_14d_en`, baseline 0.11),
`fresh-open-long-form`, `long-form-fact-cards` (readouts 2026-09-30).
Guards: `tests/test_fact_cards.py`, `TestFreshOpen`.
**Same day, operator-directed:** YouTube PAUSED on env_intel and
finansy_prosto (`youtube.enabled: false`, blocks intact for a one-line
re-enable; ~10 and ~6 views per upload). MIT's RU/FR dubs were already
culled 2026-09-02. `YOUTUBE_ENABLED_SHOWS` in `tests/test_schedule.py`
pins the set; register `pause-dead-youtube-uploads`.

**Sep 12 2026 — "views and subscribers dropped": compare at a fixed
age, never against the peak** (review:
[`docs/reviews/youtube_review_2026_09_12.md`](docs/reviews/youtube_review_2026_09_12.md)).
Uploads were complete every day and every channel was +50-60% week
over week on matching weekdays; what read as a drop was three breakout
Shorts on 09-04..06 (883 / 722 / 769 views) fading, plus the Data API
counter re-syncing Shorts views on 09-10 (+21,660 EN in a day). The
honest ruler is views per video at a fixed snapshot age: EN Shorts
published 09-07/08 earned 15-17 at day 3 against 22-32 on pre-peak
weekdays (a real ~35% softening on the non-flagship shows, flat on
Tesla/SpaceX/FF and RU; watch-through unchanged, spoken opens still
match the hooks). `scripts/track_early_reach.py` now folds every
nightly snapshot into `api/youtube_early_reach.json` (whitelisted in
nightly's add-paths) and the dashboard's **Early reach (age-matched)**
card + `short_reach_d3_median_en_7d` read it — use that card before
calling a drop. Same pass: two shows hit the 3,000 s pipeline budget on
09-11 during a chronically slow long-form render (531-1,202 s per
episode, `long_form_render_duration_s`; `long_form_render_median_s_7d`
on the register), and the slideshow graph **fails outright on ffmpeg
7.x** ("inputs need a constant frame rate" at xfade after trim/setpts)
— every zoompan branch now ends on a same-rate `fps` stamp (pass-through
on 6.x; guard `TestFfmpeg7FrameRateStamp`), which is what ubuntu-latest
will ship next. `generate_editorial_page(output_dir=)` exists so the
test renders into tmp instead of the repo root.

**Sep 13 2026 — first slate after both Sep 12 passes** (readout:
[`docs/reviews/youtube_review_2026_09_13.md`](docs/reviews/youtube_review_2026_09_13.md);
guards `tests/test_youtube_pass_2026_09_13.py`). All 12 episodes
published, 34 videos; the render-speed TRIAL is live —
`NERRA_X264_PRESET` defaults to `faster` in run-show.yml (repo variable
overrides; `medium` ends it; dubs stay on medium as the control),
register `x264-preset-faster-2026-09-13`, decision 09-20 on
`long_form_render_median_s_7d` vs 1,024 s. Three things the slate
exposed: (1) **`wall_duration_s` double-counted the render** since
09-11 (`long_form_render_duration_s` is recorded INSIDE
`youtube_publish_duration_s`; MAB read 3,257 s on a 2,225 s step) —
`engine.metrics._NESTED_DURATION_COUNTERS`; add a counter there when it
is nested. (2) **The finalize job spent 38 of 39 minutes re-downloading
10,642 gallery sidecars after EVERY episode** — `build_gallery_manifest`
is now incremental (the committed manifest is the sidecar cache; only
absent keys are fetched, vanished keys drop out) and parallel, the
nightly/standalone runs are `--full`, and a failed walk keeps the
committed manifest instead of writing an empty one. (3) **The price
line opened two SpaceX dub Shorts** — `is_price_line` was English-only
while the dubs pick windows on the RU/FR transcript; it now carries the
RU/FR close verbs and the split "dollars et cents" / bare "рост на n%"
shapes. Also on the record: combined generation engaged on ONE of 12
shows (M&A; PART 2 under-length, fell back) because the chained
flagships, the grok-4.6 script-stage shows and the RU shows are all
excluded by the pass's own rules — with the rewrite gate gone, Tesla /
FF / PT / SpaceX scripts copy 50-61% of the digest again (operator
decision, A/B-listen either way); and strip mode removed only
UNREACHABLE-source sentences (PT lost its lede), never a fabrication —
read `source_integrity_stripped_sentences` weekly.

**Sep 17 2026 — a partial analytics fetch is not a snapshot** (readout:
[`docs/reviews/youtube_review_2026_09_17.md`](docs/reviews/youtube_review_2026_09_17.md);
guards `tests/test_youtube_pass_2026_09_17.py`). The 09-16 nightly got
HTTP 500 from the Analytics API on 13 video batches and the day series
on every channel; each failure was swallowed as an empty result, the
step "succeeded", and a file with 927 of 2,753 videos and NO day series
overwrote the healthy one — the policy read `video_count_14d: 0`
everywhere, the scorecard read zero views, and `channel_views_wow_en`
went null while the dashboard's freshness alert stayed quiet (the file
was fresh). `fetch_youtube_analytics.py` now retries 5xx (never 403),
records failed queries as `payload["degraded"]`, and **refuses to
overwrite a clean file** (`snapshot_regression`: failed queries, under
60% of the committed videos, or a lost day series → `::error::` and the
file stays); `track_early_reach.py` skips a degraded snapshot. Same
pass: the x264 `faster` trial measured **no effect** (30 renders, median
932 s vs 1,024 — the filter graph is the cost) and is closed;
`combined_script_matches_digest` accepts a digest whose lines are all
in the stash (run_show's trims only remove lines — M&A discarded its
combined script every day at 0.3-0.5 forward share) and the discard
warning logs both shares. Reading rule from the early-reach card: the
**second EN Short (`qualified`) earns a median 4 views at age 3 against
31 for the hook Short** — read it at age 7 before cutting it, and never
read a week whose snapshot was refused.

**Sep 18 2026 — a result key is not a metric, third time; and the MIT
loop starves itself** (plan:
[`docs/reviews/youtube_pipeline_plan_2026_09_18.md`](docs/reviews/youtube_pipeline_plan_2026_09_18.md);
guards `tests/test_caption_track_2026_09_18.py`). Omni View Ep179
shipped its long-form with NO captions: `captions.insert` answered one
HTTP 403 while six sibling uploads on the same token succeeded, the
warning blamed a missing `youtube.force-ssl` scope, and
`caption_track_uploaded` had been set on the publish result since July
without ever reaching the `record_youtube_outcomes` allowlist. Now
`engine.youtube.upload_caption_track_detailed` returns `(ok, reason)`,
retries a transient 403/429/5xx ONCE, names a scope refusal only when
the API says `insufficientPermissions`, and both keys are recorded
(`caption_track_refusals_14d` on the register, entry
`caption-track-retry-2026-09-18`). Same pass scored the seven
experiments past readout: the open cliff is a MISS at 0.48 (the render
levers did not move it; the spoken open is what is left), review
catch-up a HIT, the MIT methodology correction retired on schedule but
sent nobody to the performance page, the RU 4th Short holds 55% of the
hook (near miss, n=8, kept), and **MIT declared "no trade today" on 19
of its 23 episodes since Ep152** — the regime block read the young era
record as a COLD STREAK and told the model to raise the bar, so the
rules-based era has 9 closed trades in a month and cannot score a rule.
Fixing that is a prompt-context change (A/B) and is the plan's first
operator item.

**Sep 22 2026, second pass — the picture follows the audio, and the
first sentence has a shape** (review:
[`docs/reviews/video_quality_pass_2026_09_22.md`](docs/reviews/video_quality_pass_2026_09_22.md);
guards `tests/test_scene_scheduler.py::TestLongFormSentenceSnap`,
`tests/test_fact_cards.py::{TestWindow,TestShortRenderStage}`,
`tests/test_video_commands.py::TestShortsPunchFrame`,
`tests/test_hook_short_motion.py`, `tests/test_spoken_open_shape_2026_09_22.py`).
The EN retention curve reads 0.74 at 3% elapsed and 0.48 at 5%: viewers
leave in a steady slide over seconds 6–60, before any chapter change,
and every render lever since August left that number where it was.
Rules that bind: **every long-form image is the episode's own** —
`gallery_blend_max_long` 3 / `min_overlap` 2 / `max_short` 2 (half the
images on a flagship were older library shots matched on one token),
and the `visual_reuse` getattr fallbacks must equal the dataclass. **Long-
form interior cuts snap to sentence ends** (`_snap_slots`, ±2.5 s; a hold
may run past the max by the tolerance, never under the min; chapter
boundaries never move) — the Whisper words are voice-only, shift them by
`voice_intro_delay`. **The gallery-retention prior reads `by_kind` ONLY
and matches prompt text**: pooled over kinds the 9:16 framing hint was
every show's top tag, and the tags-only match had scored 0 on all 1,646
images — the flywheel had never moved a rank; the Grok Imagine hint
strings are module constants so the join excludes exactly them.
`style_feedback_for` writes ONE audience-note sentence into the scene-
brief prompt only when a phrase sits ≥ 5 points from the kind's median on
≥ 10 videos (every flagship reads `None` on 09-22 — that is the design).
**Shorts fact cards + the punch frame** (tesla/spacex/FF, EN only; the
dubs are the control) are `None`-by-default keyword stages on
`_short_form_filter_graph`; a punch shifts the hook window to
1.2–4.25 s. **The hook-Short motion retry** (`engine/hook_short_motion.py`)
is one $0.28 clip with the cost gate before any request; a shortfall
records `hook_stills`, a b-roll-pool open records `broll_open`, and
neither is ever the A/B's `"stills"` label; `variant` rides into
`api/youtube_early_reach.json` for the per-arm read. **The spoken open
has a shape** (⚠️ audio, A/B-listen): `shows/prompts/_shared/hook_shape.txt`
on the three arm digest prompts (their WEAK/STRONG specimen hooks are
gone — Tesla's labelled the digit-bearing one WEAK), `engine.titles.
SPOKEN_HOOK_MAX_CHARS` = 150 as a regeneration GATE in run_show's
structural retry (never a truncation; it now runs on an over-long hook
for every daily show, SpaceX included, which had no validation config),
scored on `long_open_hold_5pct_arm` vs `_control` — `long_open_hold_5pct_en`
stays closed. Seven register entries dated 2026-09-22; readouts 10-13.

**Sep 22 2026 — Shorts reach fell on every channel at once, and "same
episode, different channels" is the test for content vs distribution**
(review: [`docs/reviews/youtube_review_2026_09_22.md`](docs/reviews/youtube_review_2026_09_22.md);
guards `tests/test_youtube_policy.py::{TestEnOneShortCap,TestDeadShortsTier}`,
`tests/test_multilingual.py::TestDubSpokenTextGate`,
`tests/test_youtube_pass_2026_09_17.py::TestTrafficDaySeries`). Between
09-13 and 09-16 the hook Short's age-3 median fell EN 23–41 → 8–10, RU
~220 → 15–92, FR 50–75 → 8–49, and a Short's views freeze after its
first day so those are final numbers. Tesla-EN held (128 / 146) while
Tesla-RU (23 / 15 / 47 / 49) and Tesla-FR (41 / 1 / 41 / 8) — the same
script, translated — fell 5–10×: a content change cannot move a dub and
spare its original, so the 09-17 read ("tracks the script, not the
render") was wrong and the drop is YouTube-side distribution (the
established-audience surface, FF-RU, held; every exploration surface
fell). Nothing measured which traffic source moved: `traffic_sources`
is a 90-day aggregate. Now `fetch_youtube_analytics` stores
`traffic_day_series` per channel (views/day by source; informational —
a failed query never marks a snapshot degraded) and the dashboard's
**Traffic mix** card reads it. Operator decisions the same day: **EN
ships ONE Short per episode, the hook** — the second (`qualified`)
window earned a median 6 views and 0 subscribers over 59 uploads in 28
days against 22 / 30 for the hook, on a channel at ~24 uploads/day
against the 30/day cadence ceiling; `MAX_SHORTS_PER_CHANNEL` in
`engine/youtube_policy.py` is enforced in `resolve_publish_plan` on
both clamps and run_show reads the plan's count on EVERY path (it used
to take it only when a policy entry applied, so a missing policy file
let `tesla.yaml`'s 2 through; revert = delete the dict entry). **A
dead-Shorts weekly-probe tier**: a show whose hook Short's age-3 median
sits under 10 for 21 days (≥ 7 videos) drops to one Short a week on
its sharded probe day after two nights and climbs back when three
probes clear the floor — "Shorts never 0" is now "never 0 for more
than 7 days"; the ruler is `api/youtube_early_reach.json`, never the
rolling channel total, and a missing reach file holds state. On the
09-22 file it enrols omni_view (8.5) and modern_investing (9.0); MAB
(11.0) and dp_pod (14.5, now in `SEED_TIERS`) sit above it. RU/FR keep
the ladder. **The spoken-text gate now runs on the RU/FR/ES/ZH
tracks** (`engine/multilingual.py`, BEFORE the R2 upload that feeds the
per-language feeds and the dubs) in SHADOW — they had never been
compared with their script, on the network's highest-reach surface;
verdicts in `digests/<slug>/spoken_text_gate.<lang>.json`, the dub
engines reuse the sweep's Whisper JSON, `audit_spoken_text.py --dubs`
is the calibration read, enforce after the 10-06 readout. Silent
numbers: `api/audience_headline.json` had Tesla under two keys (the
stats file's keys are digests DIRECTORY names — group by the videos'
`show_slug`); `shorts-subscribe-cta` was scored on subscribers per
Short, which falls with reach (now per 1,000 views, 1.51); fact cards
gave every count under 100 a zero ("9 satellites" now cards, "Falcon 9
booster" never does). Scoring rule from this pass: an experiment
shipped 09-02..09 reading out against the 09-13/16 drop is INCONCLUSIVE
with the confound named, never a MISS. `api/gallery_retention.json`
DOES hold tags now (the Sep 9 note above is stale). Eight entries past
readout closed; four registered (`en-one-short-2026-09-22`,
`dead-shorts-weekly-probe-2026-09-22`, `dub-spoken-text-gate-shadow-2026-09-22`,
`traffic-mix-instrument-2026-09-22`).

**Oct 3 2026 — the August peak was @NerraRU, and what fell was reach per
video** (review: [`docs/reviews/youtube_and_shows_review_2026_10_03.md`](docs/reviews/youtube_and_shows_review_2026_10_03.md);
guards `tests/test_show_review_2026_10_03.py`,
`tests/test_dub_short_titles_2026_10_03.py`). Network views ~44k/week
(08-03, 08-10) → ~20k (09-14, 09-21); RU Shorts were ~75% of them and
their median fell 260–400 → ~50 with uploads, retention and the country mix
unchanged; EN is at its early-August level. Our own volume cuts priced at
~6% of the loss. Rules that bind: **rebuild a daily series from the
snapshot history** (`git log -- api/youtube_stats.json`; a blobless clone
reads it — the CI checkout is depth-1) before calling a trend; **the body
opens on the story the cold open sold** (`build_cold_open_spec` bullet;
`script_hook_leads_body_pct` reads it — Tesla 82% / MAB 92% off since 09-22
while SpaceX, which held its long-form retention, was 25%); **a dub
window-Short title is written from `ScoredWindow.window_text` and never
ships `engine.titles.is_fragment_title`** — the fallback is the episode
headline + tail, tag last; **the sibling plug's cadence word comes from
`engine.cadence`**. Open: the 08-18..21 RU blackout (all Shorts 1–8 views,
no code change, self-recovered) — a Studio read, not a code fix.

**Oct 4 2026 — the Sunday slate after the Oct 3 pass** (guards
`tests/test_sunday_slate_2026_10_04.py`). Every Oct 3 target was clean on
the 21 Oct 4 episodes (no "go deeper" frame on OV, no UN / NT$ garbles, no
doubled "subreddit", no self-narration, no daily plug for a weekly show,
spoken-text gate 21/21 pass). Three defects the slate exposed, all fixed:
(1) **the weekly newsletter run had hit its 45-minute timeout on four
Sundays running** — synthesis is 3-5 min a show on grok-4.6, the walk was
alphabetical, so Planetterrian, SpaceX, Tesla and UC got no weekly after
Sep 6, ten cohort shows spent ~4 min each writing a weekly their missing
Buttondown tag then refused (a tag exists only once someone subscribes
with it), and the cancelled job never committed the sent markers of the
shows that DID go out (a re-run would have sent them twice). Now
`run_weekly_newsletters.send_preflight` refuses before synthesis exactly
what the send would refuse, `PRIORITY_SHOWS` go first, the run step has a
75-minute cap under a 90-minute job and the commit step is `always()`;
the six Oct 4 sends are recorded from the run log, and the default week is the most recent SUNDAY (`default_week_ending`) — with `date.today()` a catch-up dispatch after midnight UTC keyed its markers on Monday and would have re-sent all six. (2) **The Sunday
week-in-review instruction offered "just after the intro"** — the slot the
cold-open rule forbids (13/19 scripts on Sep 27, 3/19 incl. Tesla on Oct
4); it now goes before the close only (⚠️ AUDIO). (3) **Nerra Daily's
handoffs broke the one-in-three show-name rule on every full edition**
(18/18, 18/19): `handoff_revision_prompt` sends a non-compliant draft back
once and `adopt_revised_handoffs` keeps the revision only when it leads
with fewer names (metrics `handoffs_show_name_led_first_draft`,
`handoffs_revised`; ⚠️ AUDIO). Open for the operator: MIT's four disclaimer
sentences sit between the cold open and the first story every day
(`script_hook_leads_body_pct` 0 on 11/11 episodes — compliance placement);
`grok-47-staged-migration` is read again (`model_trial_report --since
2026-09-27 --timeout-seconds 600`): the 4.7 cohort writes better (11-22
claims, 2-17% digest-verbatim against 1-3 and 46-63% on the 4.3 flagships)
and fell back on 2 of 48 episodes (pre-flight pings, last Sep 30), but its
streamed DIGEST stage FAILS the latency gate — p95 433-814 s against the
600 s request timeout, time-to-first-token ~180-280 s. A flagship digest on
4.7 is therefore NOT the next step. **Oct 5 correction: omni_view's 4.7
script arm never ran** — grok-4.3 served all 14 of its scripts from 09-22
(the 4.7 call timed out, 621 s non-streaming, and fell back) while
`llm_script_model` recorded the configured model; it is back on grok-4.6
(8-17% verbatim at 76-85% coverage on 09-10..21), and the metric now
records the SERVED model plus `llm_script_model_fallback`. Read a model
arm from the credit files' per-call `model`, never from config. **The script call had never been timed** — the trial report
listed `generate_podcast_script` as an LLM stage that nothing recorded (the
Sep 30 "script stage p95 67.6 s" was omni_view's 4.3 DIGEST row); it is
recorded from the next run (`PipelineMetrics.record_stage`), so a
script-stage pin can be gated before it widens.

**Oct 5 2026 — the Monday slate** (review:
[`docs/reviews/network_review_2026_10_05.md`](docs/reviews/network_review_2026_10_05.md);
register `slate-review-2026-10-05`; guards
`tests/test_slate_review_2026_10_05.py`). 25/25 published, spoken-text gate
25/25 (FP after one re-synthesis). What binds: **a model arm is read from
the credit file's per-call `model`**, and `llm_script_model` now records
the served model (`llm_script_model_fallback` the reason) — Omni View's 4.7
arm never ran and it is back on grok-4.6; **page dates**: the search reads
1.5M characters, a LABELLED visible date is the fallback, and a numeric
header date is read only for a host listed with proof of its order
(`engine.article_text._NUMERIC_HEADER_DATES`, imoca.org month-first — the
Charal refit aired on Offshore North as 2 October news from a 10 February
page); **no surface says Mira phones guests** (prompts, registry, edition
code, templates swept); a show's `brand_color_dark` must clear 4.5:1 on the
newsletter card (Финансы Просто's had blocked eight sends); MIT maps dotted
share classes to Yahoo's form and voids an open pick with no bars after
`UNPRICED_VOID_DAYS` (14); Env Intel's low-content Deep Dive counts as its
lead and the absence filter is on for Env Intel and Offshore North.
⚠️ AUDIO: Omni View's script model, Env Intel's prompt, both absence
filters, Mira's self-description.

**Same day — the five merged Grok reviews, acted on** (register
`review-followups-2026-10-05`; guards
`tests/test_review_followups_2026_10_05.py`). **A chapter marker may name
its digest heading** (`digest_section`): when the spoken anchor is skipped,
`engine.chapters._digest_section_anchor` starts the chapter where that
section's own words begin. It is opt-in (Models & Agents Under the Hood,
AI Chips Teardown) because a marker chapter can suppress headline
auto-segmentation on shows that forbid spoken labels. **The review writer
copies each ledger's own list indentation**: the merged models_agents and
planetterrian ledgers had stopped parsing, and every ledger is now parsed
in CI. A Grok review's claim is checked against the committed text before
it is acted on: of five, one "P0" was Whisper (M&A's French episode
number) and two leaned on the retired rewrite gate. ⚠️ AUDIO: AI Chips
selection + Teardown close, UC Lesson, Planetterrian deep dive / pivots /
teaser, Tesla's length line.

**Oct 6 2026 — the first slate after those merges** (register
`slate-2026-10-06`; guards `tests/test_slate_2026_10_06.py`). Every Oct 5
target held on its first episode; **Modern Investing published nothing.**
The share-class fix priced HPS.A 40 days late, the benchmark's fixed
one-month fetch could not reach its entry bar, the trade closed with no
alpha, and one `+= None` in the strategy-performance sum dropped the whole
pre-fetch hook — after which the digest prompt died on a missing variable.
Rules that bind: **a benchmark window reaches the entry bar**
(`_period_covering`, never narrower than a month); **a missing alpha is
never a zero** (averages over the trades that carry one); **the MIT hook's
analysis blocks fail one at a time** (`_section`, `::error::` +
`mit_prefetch_failed_sections`) — the record (trade review, portfolio,
indices, benchmark) stays unguarded on purpose. **The claims metrics record
what SHIPS**: `source_integrity_claims` / `_verified` are re-written after
repair and the coverage floor (`_pre_floor` keeps the first reading);
Tesla Ep626 had read 2 beside a committed ledger of 7.

**Oct 8 2026 — no transcripts on the whole slate, again** (review:
[`docs/reviews/slate_review_2026_10_08.md`](docs/reviews/slate_review_2026_10_08.md);
register `slate-2026-10-08`; guards `tests/test_transcripts_pyav_2026_10_08.py`,
`tests/test_youtube_session_restart_2026_10_08.py`). Dependabot #1365
rewrote the Sep 30 PyAV ceiling to `>=19.0.1,<20` and was merged in a
batch while `test_pyav_is_pinned_below_19` was red: 0 of 21 episodes had a
transcript, the spoken-text gate ran blind, Nerra Daily Ep049 shipped every
segment uncut, Shorts lost captions and fact cards. **Whisper never decodes
through PyAV now** (`engine.transcripts.load_whisper_audio` — ffmpeg, samples
identical to faster-whisper's decoder); the ceiling stays and Dependabot
ignores `av>=19`. **Never merge a dependency bump on a red `Run Tests`**,
and read the comment above a pin before moving it. Same day: a 404/410 on a
resumable YouTube upload restarts ONCE with a new session (`upload_video` —
Tesla/SpaceX/Omni View lost their long-forms to "410 Gone"), and apt in
`setup-python` abandons a silent mirror connection after 30 s (five runs
died at exit 124 installing ffmpeg). **Same day, an outside review checked
and acted on** (§7 of the review; guards `tests/test_chapters_lead_2026_10_08.py`,
`tests/test_review_followups_2026_10_08.py`): **the lead story gets its own
chapter** (`engine.chapters._lead_story_split` — it sat inside
"Introduction" on 19 of 21 episodes; never on a known_sections_only show,
never where the body opens on another story) and **a spoken sentence is a
chapter title only when it fits whole** (no clipped fragments, no "Segment
N" — an untitled break is not made); `extract_story_headlines` reads
`**Title:** Outlet`; UC chapters its five digest segments. A missing lead
chapter never blocks an episode — chapters are metadata. **A hook may name
only what an item reports** (`hook_supported` lint, Tesla — Ep627 added
"Tesla Megapack" to a story that never mentions it; correction filed).
**Deep-dive essays are exempt from the overlap dedupe** (AI Chips Teardown,
SpaceX Engineering Deep Dive — each was deleted from a digest for citing a
news item's report). Bypass publishers (Nerra Daily, Voices) pass
`episode_page_url` like run_show. Ten site guards used Nerra Voices as "a
show with no episodes" and failed when it published Ep1 — they render
`conftest.unpublished_show` now; never use a real show as a fixture for a
state it will leave.

**Oct 9 2026 — the runner upgrade, taken whole (operator-directed).**
GitHub moves `ubuntu-latest` to Ubuntu 26 from Oct 19; rather than let the
label move under the network, **every job pins `runs-on: ubuntu-26.04`**
(apt ffmpeg 8.0 — was 6.1), every `setup-python` call and the composite's
default run **Python 3.14**, every action is on its current major, and the
requirements floors are the releases of that date (`av` keeps its `<19`
ceiling; the PyAV guard pins the ceiling and lets the floor move). Read
before trusting: an ffmpeg **9-dev** snapshot aborted inside the Voices
`anlmdn` clean-track chain while the 8.x release line passed the same
tests, so a future bump of the runner's ffmpeg is a render-smoke question,
not a label edit. **The scheduler Worker holds ONE cron trigger** —
`1,7,16,31,37,46,50 6-17 * * *` — because the Cloudflare account was then on
Workers Free (five triggers per account, Voices held three) and the Oct 8
deploy with a second trigger was refused with code 10072 after the script
had uploaded: the show slots kept firing and the 8am edition dispatch never
went live. **The account is on Workers Paid now** (operator, Oct 23 2026),
so a second trigger would deploy; one stays because the handler decides
from the exact firing minute and no job needs another. Since Oct 17 the one
trigger is `*/5 * * * *`. Guards: `tests/test_scheduling_punctuality.py`,
`tests/test_transcripts_pyav_2026_10_08.py`.

**Oct 9 2026, later — four items the operator said yes to** (register
`spacex-script-grok46-2026-10-09`, `ops-bundle-2026-10-09`; guards
`tests/test_ops_bundle_2026_10_09.py`). **SpaceX's script stage runs
grok-4.6** (`llm.podcast_model`; the digest stays 4.3; two-pass by code like
Omni View) — the one measured quality lever: over Oct 2-8 the 4.3 flagship
scripts read the digest aloud (SpaceX 64% verbatim, 3-12 claims) where the
4.6/4.7 script arms write (2-17%, 13-27 claims). Tesla joins only on a
GATE: PASS at the 10-23 readout. ⚠️ AUDIO — A/B-listen Ep1. **The ZH track
is off** on tesla, spacex and fascinating_frontiers (every ZH feed
`measured: false` for eleven weeks at ~$2.70/week; the committed
`*.zh.rss` feeds are frozen, not deleted; a zh track needs BOTH the
language and `zh_approved`). **The Voices Worker holds ONE cron trigger**
(`*/5 * * * *`; fire-tick every firing, producer-tick on :00/:30, gate 2 at
17:00 UTC, decided from the firing minute; it was written when the account's five
Workers Free triggers were all spent, and the account is on Workers Paid
now) — operator: `wrangler deploy` in
`workers/voices`. **Dependabot groups each ecosystem's bumps into one
weekly PR**; the `av>=19` ignore stays.

**Oct 9 2026, later still — the narrative shows get sources** (register
`narrative-research-2026-10-09`; guards
`tests/test_narrative_research_2026_10_09.py`). Unintended Consequences
and First Principles wrote from the topic brief and nothing else — no
article ever reached the episode prompt, every Sources list was empty, UC
verified 0 claims in eight episodes. Now `narrative_research: N` runs ONE
web search for the picked topic (`engine.fetcher.fetch_topic_research_articles`
— ANY date, `exempt_stale`, `source_kind: research`; the news searcher
drops anything older than 72 h and a 1935 cane toad is the point), merges
the results beside the hook articles (so they reach `fetch_full_text`,
`news_section` and the claims gate like a fetched item) and renders them
into both `*_episode.txt` prompts as `{research_sources}` with an honest
fallback line when the search returns nothing — an empty search never
skips an episode. **The claims gate never verifies against the search
model's summary**: `build_local_texts` reads only the title and the fetched
PAGE for a research article (`full_text_source: page`, which
`enrich_articles_with_full_text` now fetches regardless of description
length), else the claim goes to HTTP. ⚠️ AUDIO on both shows (prompt and
input changed) — A/B-listen Ep1.

**Oct 9 2026, network improvement review** (doc:
[`docs/reviews/network_improvement_review_2026_10_09.md`](docs/reviews/network_improvement_review_2026_10_09.md);
guards `tests/test_verify_analytics_snapshot_2026_10_09.py`,
`tests/test_multilingual.py`). Two measurement defects fixed with it:
**`verify-youtube-analytics.yml` runs on any push that touches it and wrote
`api/youtube_stats.json` with no @NerraFR block** (EN/RU tokens only, no
`snapshot_regression`) — it carries every channel token the nightly does
and refuses a regressed snapshot now; and **the multilingual sweep ran on
all seven shows after EVERY successful show run** (92 "Multilingual:"
commits on Oct 7): `workflow_run.head_commit` is the tip the run STARTED
on, never the "Auto-generated: <show>" commit made during it, so the
Sep narrowing had never fired — the resolve step reads the triggering
run's jobs (`run (<show>)`, `actions: read`) instead. Reading rules from
the review: a trailing-7-day OP3 figure that beats every complete week is
a catalogue sweep, not growth (read complete weeks); the 4.7 cohort
writes and the 4.3 flagships copy, on every surface measured; 20 live
feeds are findable only on nerranetwork.com; no first-party signup
surface fires a GA4 event, so "0 signups" means unmeasured.

**Oct 9 2026, afternoon — review items 9–13, and the slate that followed the
morning's merges** (register `structural-regen-2026-10-09`,
`probe-tier-imagery-2026-10-09`, `x-accounts-rotation-2026-10-09`,
`x-on-spacex-daily-aoai-2026-10-09`; guards
`tests/test_review_items_9_13_2026_10_09.py`, `tests/test_sdk_httpx_2026_10_09.py`).
**P0 first: the stream reader imports the SDK's own HTTP module**
(`engine.generator.sdk_httpx` — `openai` 3.26+ is built on `httpx2`, a
different import name, and `httpx` had only ever arrived as a transitive
dependency; when `tokenizers` 0.23.3 landed at 10:00 UTC nothing pulled it
any more and all seven `llm.stream` shows from 10:08 died at their first
digest call). No production module imports `httpx` by name. **A
regeneration the pipeline cannot repair is not a structural defect**: 35%
of episodes (107/304, Sep 25–Oct 8) regenerated their digest — 43 on a hook
over 150 characters, every one on a prompt that supplied its own over-limit
specimen (the shows including `_shared/hook_shape.txt` ran 0–1 in 14). The
two narrative prompts (UC, FPD — 15 of the 43) include it now and their
Example specimens are gone (⚠️ AUDIO, the hook is the spoken open);
**omni_view, models_agents, modern_investing and env_intel are the CONTROL
of the Sep 22 spoken-open experiment and their hook prompts wait, specimens
included, for its Oct 13 readout** — the include goes on them the day it is
scored, never before (`TestStructuralRegen::test_control_shows_wait_for_the_oct_13_readout`);
23 on an empty section —
Tesla's Short Spot is `optional` because the cross-section dedupe empties
it BEFORE the validator and the retry's Short Spot was deduped again (6 of
8 shipped empty anyway), a present optional section with 0 items is not an
issue (MIT's one-sentence Listener Challenge), and FF's Space Stories
pattern accepts the numbered list under the hook rule (the header was the
only thing missing). `digest_structural_regen_reasons` is recorded;
`digest_structural_regen_share_7d` is the readout. **The probe tier draws
two portrait scenes** (`PROBE_PORTRAIT_SCENES`, keyed on the plan's
`shorts_probe`, never a show list; the 16:9 set on tier-B longs is a live
surface and stays). **Review item 11 named the wrong knob**: the cohort's
7–9 search calls were per-account X fetches, not web queries —
`x_accounts_per_run: 4` on vancouver / ai_chips / mag7 / peptides /
longevity reads four accounts a day on a date-seeded rotation
(`engine.fetcher.rotate_x_accounts`); Offshore North is untouched (weekly,
$0.07/week). **X is on for SpaceX** (the `X_` app, @teslashortstime),
**Nerra Daily and The Age of AI post from the network account** through
`engine.x_post` (`NERRANETWORK_X_*` secrets — operator item; unset is a
logged skip recorded as `x_post_skipped: no_credentials`), run_show records
`x_posted` / `x_post_skipped` (`x_posted_share_7d`), and the edition
metrics carry the outcome. **The grok-4.6 script arms on SpaceX and Omni
View never ran** (444 s drop, 660 s timeout, both fell back to 4.3 — read
an arm from the credit file's per-call `model`): both shows now
`llm.stream: true` per playbook rule 7. The multilingual resolve step
treats an EMPTY successful jobs read as "nothing published" (a gate-only
schedule run had swept all seven). Item 12 is an operator step in
`docs/podcast_directories.md`: the three French-only feeds go to Podcast
Index before their $11/mo is decided.

**Oct 10 2026 — listener noise, and the slate review behind it** (review:
[`docs/reviews/slate_review_2026_10_10.md`](docs/reviews/slate_review_2026_10_10.md);
register `listener-noise-2026-10-10`; guards
`tests/test_listener_noise_2026_10_10.py`). Operator listen: too many stock
prices on MAG 7, and how many likes an X post got. **`engine/listener_noise.py`
removes, in code and network-wide, what a prompt already banned**: engagement
counts and the minute a post went up (only right after a posting verb — a
launch time is content), sentences that say only that a post was made on X,
and a closing-price TAPE (two or more consecutive closes for different
subjects; one price in a story and the flagships' quote line are untouched).
It runs on every X post at fetch, on the digest before the source-integrity
gate and on the script; the digest's reader-only `### The Tape` never reaches
the script stage (`strip_reader_only_sections`). Calibrated on 1,092 files —
re-run that sweep before widening a pattern. **Quotas put filler on air**: FF
and Planetterrian are capped at 12 items and include `interesting_first.txt`,
Tesla's Top 12 / Takeover are "up to"; a short, dense episode is the trade.
Shape fixes (⚠️ AUDIO): reference numbers (phone, file, patent, volume, read
time) only when the story turns on them; a story's first sentence names its
subject; desks skip Progress Watch on a none day and Both Sides without a
named disagreement; the Board is not a price tape; SpaceX/FF/MIT/M&A
specimens out; MIT's Action is optional and sourced; UC/FPD carry a named
person and a sourced hook number. "Pope Leo" is not LEO. **Open for the
operator:** the Patrick disclosure line ("editorial selection and analysis
are my own") contradicts the AI-disclosure page — operator decision
2026-10-10: keep it as is for now, do not change it unasked; the closing block (one ask,
topical sibling); widening the 4.6 script stage once SpaceX's streamed arm
has run.

**Oct 11 2026 — a narrative show writes only from sources** (review:
[`docs/reviews/slate_review_2026_10_11.md`](docs/reviews/slate_review_2026_10_11.md);
register `slate-2026-10-11`; guards `tests/test_slate_2026_10_11.py`). UC
Ep139 aired an invented case (Argentina licensing toothfish off South Georgia,
a British territory) from a restock-written brief with 0 research sources;
correction filed. **`narrative_research_min: 2`** on UC and FPD: fewer
sources tries the next topic (up to three, `pick_next_topic(exclude_ids=)`),
then skips `narrative_research_thin` — never a case from memory; a topic is
annotated only when the search WORKED and came back thin (an outage also
returns `[]`). **@grok is a research desk, never a source**
(`engine/grok_leads.py`, `grok_leads:` on SpaceX/Tesla/M&A/AI Chips): its
topical explainer replies become writer-only deep-dive ANGLES
(`{deep_dive_leads}`), each kept only when two primary PAGES were fetched for
it; the reply is never an article, a Source line or claims evidence (an X
post's text verifies by local copy, so a @grok reply "verified" only that
Grok said it — SpaceX Ep127). Metrics `grok_leads_found/kept`,
`grok_lead_sources`. SpaceX deep-dive numbers come from the digest, a
constant, or a labelled estimate. Mira's live prompt states the guest's built terms.
Desk/Top World **Both Sides is optional** (prompt and validator) — it runs
only on a named disagreement. The AI Chips / MAG 7 teaser never restates the
calendar item just read (this reverses the Sep 23 "teaser names the nearest
item"). **Visuals:** story briefs top the image set up to `MIN_STORY_SET` (4),
never pad it to `count` with static `image_queries`; duplicate briefs collapse;
essay sections supply scene contexts; dub thumbnails use a scene; a decimal
title keeps its number. **Workflows:** multilingual concurrency is per SHOW on
the translate job (a workflow-level group cancels pending runs) and a show
that skipped today is not swept; Nerra Daily's links call gets a second
attempt and names why a reply was refused, and its fallback speaks full hooks,
never a "…" title; **The Age of AI renders its own waveform video** when the
edit path left none (0 uploads since Sep 20) and caps feed titles through
`engine.titles`. ⚠️ AUDIO: Mira, FF/PT, Tesla X Takeover, MIT Market
Mechanics, SpaceX deep dive, Both Sides, the Sunday segment, the two teasers.

**Oct 11 2026, later — sponsor-ready, and five operator items** (register
`sponsor-ready-2026-10-11`, `signup-measurement-2026-10-11`,
`narrative-queue-source-audit-2026-10-11`, `fr-dub-gate-enforce-2026-10-11`;
guards `tests/test_sponsor_ready_2026_10_11.py`). **The network no longer
promises "ad-free" anywhere** (operator: sponsorship comes next); the episode
stays free, which is true. **Oct 18 2026: ads are coming to the site and the
shows, and ad-free is reserved for subscribers and paid content** — no free
surface says ad-free (the approved SEO copy in `docs/seo-titles-final.md` had
put "Ad-Free" in the homepage `<title>` and five show metas, the brand-refresh
banner/share art and the September debut articles carried it; all corrected,
and the guard now reads those sources plus show YAMLs and Worker pages).
Transcripts stay the record of what the audio said. Copy that calls the PAID
tier ad-free lives in `engine.brand` and names the product. **`engine.brand` owns the sponsor policy**
(`SPONSOR_POLICY_SUMMARY` / `_RULES`, the `sponsor_policy` Jinja global):
labelled, kept apart from the reporting, no say over coverage, same sourcing
rules, every episode free. It renders on `sponsor.html` (numbers from
`api/audience_headline.json`, dash = unmeasured), `editorial.html#sponsors`,
the FAQ and the press kit; a template that types a rule fails CI. No ad is
placed yet. Also: the footer/join form fires GA4 `newsletter_signup`; the UC
and FPD queues were audited for sources (cut / fixed with a dated SOURCE
AUDIT note / kept) and a restock brief now needs two non-social search
results (`ground_candidates`); the spoken-text gate ENFORCES on French tracks
only (`CALIBRATED_LANGUAGES`; RU stays shadow until its opening match is
calibrated on Cyrillic); `pipelines/voices/backfill_videos.py` (Actions
"Nerra Voices — backfill YouTube videos", dry run by default) gives the Age of
AI's past episodes their video; Prediction Markets' Friday Week's Board parses
the prose Board again (it was empty on 10-02 and 10-09).

**Oct 11 2026, evening — script-stage models (operator-directed)** (register
`narrative-script-grok47-2026-10-11`, `planetterrian-script-grok46-2026-10-11`;
guards `tests/test_script_models_2026_10_11.py`). Unintended Consequences and
First Principles write their SCRIPT on grok-4.7 at low effort; Planetterrian
on grok-4.6; every digest stays grok-4.3 and every arm streams. **The script
call has its own effort** (`llm.podcast_reasoning_effort`, used only while the
call runs `podcast_model`; a fallback to the digest model runs at that model's
own effort), and every follow-up script call — truncation retry, expansion
retry, publication-floor re-roll, anti-repetition retries — now carries the
same effort and stream as the first (they had sent the arm's model at default
effort, non-streamed: the shape that dropped in September). Measured before:
4.6 script calls take 190-700 s against 20-60 s on 4.3, so a pinned script
arm costs a run 3-12 min; the narrative shows and Planetterrian finish in
5-10 min of the 50-min budget. **Same evening, Tesla and Fascinating
Frontiers moved to the grok-4.6 script stage too, then Modern Investing and
Models & Agents** (operator call, ahead of the 10-23 SpaceX gate; register
`flagship-script-grok46-2026-10-11`, `mit-script-grok46-2026-10-11`,
`models-agents-script-grok46-2026-10-11`; MIT and M&A are CONTROL shows of
the Oct 13 readout, so that readout names them as a confound); Models & Agents for Beginners and The DP Pod, on the 4.6 script stage
since Sep 1 and Aug 18, now stream that call too: Tesla
leaves combined generation (a `podcast_model` override is two-pass), its runs
already reach ~32 min so the long-form render now leans on the budget gate,
and Tesla and FF are ARM shows of the Oct 13 spoken-open readout — read that readout
with this change named as a confound. ⚠️ AUDIO on all seven — A/B-listen Ep1.
**Streaming is the network default** (`llm.stream: true` in `_defaults.yaml`):
Env Intel, Финансы Просто, Привет, Русский! and Offshore North were the last
run_show shows on the non-streaming call. Same model and request; transport
only, and no show may opt back out (`TestConfig::test_every_show_streams`).
The interview shows ignore the flag — the Voices pipeline never calls
`engine.generator`. **Four Grok review PRs triaged the same evening**
(register `review-triage-2026-10-11`; guards
`tests/test_review_triage_2026_10_11.py`): a speaker-labelled line ("DAN:
Ten") is never a chapter title, DP Pod's Cold Open marker matches the spoken
"This is The DP Pod", and its prompts say weekly (⚠️ AUDIO). Checked and not
acted on: SpaceX "Patrick and Vancouver" is Whisper reading a script that says
"in"; on the 4.6 script SpaceX's AI section was empty and the price is spoken
once, at the close.

**Oct 12 2026 — the first slate on the pinned script arms** (review:
[`docs/reviews/slate_review_2026_10_12.md`](docs/reviews/slate_review_2026_10_12.md);
register `slate-2026-10-12`; guards `tests/test_slate_2026_10_12.py`). 28/28
published, every arm served its own model; the 4.6 scripts write (MIT 6%
digest-verbatim, Tesla 27%) and bring new defects. Rules that bind: **model
control tokens are stripped wherever model text comes back**
(`engine.utils.strip_model_special_tokens`; `<|eos|>` had aired on MIT
Ep198 and DP Pod), and the missing-closing guard drops a half-written
closing before it appends (`trim_partial_closing`). **The translation call
carries its own 600 s timeout with the SDK's retries off**
(`NERRA_TRANSLATION_TIMEOUT_SECONDS`; a silent call outlived the 120-min
multilingual job and cost SpaceX its FR/RU tracks). **A shared Source URL
is a duplicate only when the items share the story** (a roundup page carried
three stories on Africa & Middle East and two aired with no ledger entry).
**A hook titles a lead chapter only whole**; a bold `Title: Outlet` line may
run to 110 chars. **Network plugs read the SPEAKING show's cadence** — no
"family of daily podcasts" on a weekly show. **Привет, Русский! closes in
Russian** (operator-directed; `_RUSSIAN_CLOSING_SHOWS` — the lesson stays
English-taught). Offshore North's record follows the team's 8 Oct post: Scott
will not start the Route du Rhum, and a race EMIRA IV is not in is never her
next milestone. ⚠️ AUDIO: PR close, MAG 7 calendar anchor, Vancouver/
Collingwood Both Sides, UC/FPD one telling per fact, the shared teaser and
outlet-name lines, Prediction Markets' legal-step rule.

**Same day, later — SpaceX story chapters and @grok leads** (register
`spacex-story-chapters-and-grok-leads-2026-10-12`). **A `known_sections_only`
show gets story chapters, headline used whole**: a digest headline anchored
where its story begins in any body chapter, only when it fits
`engine.titles.HEADLINE_CHAPTER_TITLE_MAX` (80) — never a clipped title, never
the fixed-interval / first-sentence fallback (SpaceX had eight stories inside
"Introduction" on every episode). **@grok leads search subject by subject**
(`engine.grok_leads.lead_subjects`): one search over the whole beat found 0
leads; a probe found 2-4 per show with one search per subject. Request shape
was never the problem — `scripts/probe_x_search.py` (Actions "Probe x_search",
read-only) compares shapes and prompts with the real key; read it before
changing an x_search request. @SpaceX returns 0 posts from x_search with or
without a handle filter (xAI's index). ⚠️ AUDIO: SpaceX segment order.

### Anthology books — ebook + audiobook from the narrative shows (Aug 2026)

Product B6 (operator-directed): a SERIES machine, not one-off books.
`books/series/<show>.yaml` is the branding contract (author **Patrick
Novak**, series title, subtitle template, show brand colors, Grok-art
style guides, `volume_chapters` — a series-level PRODUCT decision,
default 60, band 10–80, never 20: the 20-chapter volumes priced ~5x
market rate per word); `plan_next_volumes()`
(`engine/book_compiler.py`) cuts the next thin
`books/volumes/<id>.yaml` automatically as episodes accrue
(append-only — published volumes never change; **retired** volumes
are ignored for coverage and numbering; it can never emit volume 0 or
an episode already in a live volume — `TestWO12SeriesVolumes`;
`--plan-preview` is the dry run), and
`scripts/build_book.py` (Actions "Build Book": manual per-volume, or
monthly-cron planner mode that plans + builds everything pending)
compiles digests into a store-ready EPUB 3 + Grok-TTS-narrated
chaptered M4B. Text transform is **deterministic — no LLM**; art is
`engine/book_art.py` on **pinned** `grok-imagine-image-quality` (never
a floating -latest alias): one 16:9 illustration per chapter (embedded
in the EPUB, re-encoded ≤~1000px JPEG for KDP delivery fees) + fresh
portrait cover art per volume under FIXED series typography
(`compose_cover` — consistency is the series branding; style guides ban
text inside generated images). Every generated image also uploads to
the show's public gallery with `intended_use` `book_chapter`/
`book_cover` — values the video scene selector must NEVER match (the
thumbnail_variant precedent). Cost/volume ≈ $1 art + $2 TTS, gated by
`--max-image-cost-usd` / `--max-tts-cost-usd`. Rules that bind: chapter
titles are CURATED (`chapter_titles:` map in each volume YAML — never
derived from the episode hook, which is a full sentence and truncated
in every store TOC on the first submission attempt, 2026-08-22) and
clip via `engine.titles.BOOK_CHAPTER_TITLE_MAX`; narration speaks only
"Chapter N." (deliberately decoupled from the printed title so title
edits re-mux, never re-narrate); planner mode builds any committed
volume with no cataloged artifacts (not just same-run plans), a
no-upload build never writes the catalog, narrated tracks persist to
R2 `books/<id>/audio/` keyed by narration-text hash (true CI
resumability + the stores' per-chapter MP3s), and
`scripts/verify_book_catalog.py` asserts claimed artifacts answer 200
after every workflow build; EVERY
reader-facing link goes through `engine.funnel` `kind="book"` (campaign
carries the VOLUME number; each chapter ends on a funnel-tagged link to
its source episode page); artifacts to R2 keyspace `books/<id>/` ONLY
(never a show's audio prefix); `outputs/books/` gitignored (landmine
#1); **the EPUB embeds display-size images only** (Sept 2026 — the
first 73-chapter collected edition shipped at 15.4 MB, 96% images, a
4.8 MB PNG cover: $2.25 of KDP delivery fee per sale and over the 10 MB
upload cap; now chapter art at 720 px under a ~45 KB budget, the cover a
1200×1920 JPEG, documents deflated, `build_epub` refuses anything over
`EPUB_MAX_BYTES` = 5 MB — tune `engine.book_art`'s `EPUB_*` constants,
never the cap; full-res art stays on R2/gallery); **store-level digital-narration DECLARATIONS are non-negotiable
(KDP AI questionnaire stays YES, Spotify's digital-narration box stays
ticked, Google Play stays declared — never remove any of them;
Audible/ACX takes no third-party AI narration at all), but the SPOKEN
in-file disclosure line was removed from the audiobook credits Aug 2026
(WO-8, operator-directed) — no retail channel requires a spoken line,
only the upload declaration; an earlier note here conflated the two.** Committed record: series + volume
YAMLs + `books/catalog.json` → `/books.html` (`generate_html.py
--books`, in `--all` + sitemap + footer). **Store links live in the
volume YAML** (`buy_links`: `direct`, `audiobook_direct`, `books2read`,
retailers) — `/books.html` reads them from the YAML at render time
(`books_page_volumes`, YAML wins per key); the catalog copy refreshes
only on a build, so never hand-edit it for links (WO-15). **Audiobook
masters reach the operator only via Actions "Export audiobook"**
(`scripts/export_audiobook.py`): private-bucket zip (tracks + retail
sample + 3000² cover + manifest), the zip and M4B attached to the run as
3-day **artifacts** with a sha256 table in the step summary — never a
download URL anywhere in CI (WO-15b: GitHub masks the endpoint secret
out of the summary, so a presigned link renders dead; `--print-url` is
local-only). Live (WO-12, Sept 2026): **UC Volume 1** (73 chapters, eps 1–80) and
**First Principles Volume 1** (58 chapters, eps 1–60) — the former
"Collected Editions", renumbered because they are Volume 1 of an
ongoing series (Volume 2 comes from ep 81 / ep 61); their volume ids
keep the historical `_collected` names on purpose (R2 keyspace +
narration cache; `_vol1` is taken). The 20-chapter vol1–4 / vol1–3
books are **retired** (`retired: true` — never on a store, hidden from
books.html and cross-promo, kept for provenance). Spot-listen +
eyeball art on a new volume before store submission (landmine-#17
habit). Store checklist + policies: [`docs/books.md`](docs/books.md).
Drift guards: `tests/test_book_compiler.py`.

### Site-showcase video endings (Aug 2026, operator-directed)

Every long-form video now ends on a 1920×1080 **outro card** built from
real nerranetwork.com screenshots (the show's page + the network home
page, framed side by side), the URL in Nerra cyan, a localized (en/ru/fr)
newsletter line, and a QR to the funnel-tagged show page
(`utm_content=outro` — new `PLACEMENT_OUTRO` in `engine/funnel.py`'s
closed vocabulary). Shorts end cards paste the home page's show-grid
band as a framed strip above a cyan URL footer. Module:
[`engine/promo_card.py`](engine/promo_card.py); overlay threaded through
BOTH long-form command builders in `engine/video.py` (two-pass +
single-pass; no-outro args are byte-identical legacy, pixel-verified on
real renders). Screenshots are **committed** at `assets/site_screens/`
(the render never hits the network) and refreshed by
`scripts/capture_site_screens.py` — a show without its own `show_<slug>`
shot falls back to the network-home card, and a channel lander
(`ru_spacex.png`) wins for that channel's dubs. `qrcode` is in
requirements but optional at runtime (card ships without a QR). Config:
`youtube.outro_card_enabled` / `outro_card_duration_seconds` /
`shorts_end_card_site_panel` (defaults on in `_defaults.yaml`).
Render/metadata only — outside landmine #17; best-effort everywhere
(any failure ships the legacy ending). Registered as the
`site-outro-cards` experiment (readout 2026-08-23). Drift guards:
`tests/test_site_showcase.py`.

### Adaptive YouTube publishing policy (July 2026)

Publish volume/format now adapts to what each channel actually watches
(full doc: [`docs/youtube_feedback_loop.md`](docs/youtube_feedback_loop.md)
"Adaptive publishing policy"). Nightly `scripts/update_youtube_policy.py`
(no secrets; runs right after the title-hint step) turns
`api/youtube_stats.json` into **`api/youtube_policy.json`**: per
show × channel tiers from 14-day views-per-day velocity (A = long + 2
Shorts, B = long + 1, C = shorts-only, D = probe; long on at
`long_vpd ≥ 1.0`, 2 Shorts at `short_vpd ≥ 4.0`, Shorts NEVER 0 — they're
the recovery signal; <4 in-window videos of a kind holds that dimension).
**Hysteresis:** the active tier flips only after the same computed tier on
2 consecutive runs; cold-start actives are `SEED_TIERS` hardcoded from the
2026-07-14 analytics (RU long-form seeded off everywhere). Consumers via
`engine.youtube_policy.resolve_publish_plan`: `run_show._publish_youtube`
(EN + native-RU shows; a shorts-only tier skips the long-form render/upload
while Shorts + the shared thumbnail still ship; Shorts raise to 2 only with
`shorts_start_mode: smart`; metrics `yt_policy_tier` /
`yt_policy_long_skipped` / `yt_policy_shorts`) and
`engine.ru_dub.publish_ru_dub` (@NerraRU dubs; the sweep's done-check now
also counts an uploaded Short). Best-effort by contract: missing policy
file / absent slug / `youtube.adaptive_publishing: false` (new field,
default true) = exact legacy YAML behavior. The policy never edits YAML
files at runtime and never touches audio (outside landmine #17). Drift
guards: `tests/test_youtube_policy.py`.

**July 18 2026 growth pass** (review:
[`docs/reviews/youtube_growth_review_2026_07_18.md`](docs/reviews/youtube_growth_review_2026_07_18.md);
drift guards: `tests/test_youtube_growth_pass.py`,
`tests/test_shorts_selector.py::TestFillToRequested`): post-policy
verification found tier gating exact, RU titles fixed, and RU/EN Shorts
massively outperforming long-form — but tier-A shows chronically
under-shipped Shorts (FF 1-of-2 on EVERY July episode). Shipped:
**fill-to-requested** in the multi-Shorts selector (sub-threshold windows
ship rather than fewer Shorts; `qualified` flag + `shorts_fill_modes`
metric; FF threshold 3.5 parity); **RU multi-Shorts** (policy may raise to
2 — RU Shorts are the network's best surface, spacex-RU short_vpd 30);
**subscriber tracking** (analytics schema v2: per-video subscribersGained,
channel snapshots + `api/youtube_channel_history.json`, dashboard card,
subs-blended title hints — subscribers were previously tracked nowhere);
**title bundle** (one Grok call → long titles + 2-4-word ALL-CAPS
thumbnail punch text + per-window Short titles; empty fields = exact
legacy fallbacks; opt-outs `thumbnail_punch_text` / `optimized_titles`);
**auto-comments** (`engine.youtube.post_video_comment` — long-form posts
the pinned-comment template, Shorts post the full-episode funnel link, RU
only when a RU long exists; API can't pin, operator pins in Studio;
opt-out `auto_comment`); **channel-specific long-form floor**
(`LONG_VPD_FLOOR` en 1.0 / ru 2.0 — RU longs earned ~9% retention);
**gallery-retention style tags** now mined from image prompts (per-show
doc-frequency boilerplate filter). Operator declined publishAt scheduling
(uploads stay immediate). All render/metadata-side — outside landmine #17.

**July 22 2026 scoring pass** (review:
[`docs/reviews/youtube_review_2026_07_22.md`](docs/reviews/youtube_review_2026_07_22.md);
drift guards: `tests/test_youtube_policy.py::TestShortsCountFollowsData`,
`tests/test_youtube_growth_pass.py::TestSmartShortsNetworkWide`): scored the
07-18 rollout list — fill-to-requested HIT (Tesla/FF/SpaceX all 2/2 since
the fix), Monday probe HIT (MIT Ep112, Mon 07-20), FF-RU long demotion HIT;
two MISSes fixed: (1) **`shorts_per_episode` now follows the computed
`short_vpd`, not the tier letter** — `TIER_SETTINGS[active]` had pinned
shorts-only (C) shows to 1 Short, discarding the computed "-> 2 Short(s)"
(RU spacex/tesla/FF sat at short_vpd 18-45, the network's hottest surface,
shipping half the allowed Shorts; policy regenerated, they get the 2nd
Short now); (2) **`api/youtube_channel_history.json` was never committed**
(nightly add-paths whitelist gap — 4 runs silently dropped the snapshot;
path added, file seeded en 207 / ru 61 subs, dashboard `_delta_7d` falls
back to the day_series net gain while history is <7 days old). Also:
**smart Shorts start network-wide** — 7 enabled shows (OV, M&A, EI, PT, UC,
FP, PR) still resolved `voice` (every Short opened on the 10 s intro) and
MAB/FPD's smart mode fell back 6/6 at the 5.0 default threshold; all
enabled shows now pin `smart` + fleet threshold 3.5 (guarded). And
`record_youtube_outcomes` finally persists `shorts_fill_modes` /
`thumbnail_punch_text` / `yt_comments_posted` (the 07-18 layers had shipped
invisibly — verify punch + comments in metrics from 07-23). Subscriber
attribution insight: EN long-form converts subs best (24 vs 15 EN-short /
10 RU-short of 56 tracked) — long-form cuts stay velocity-gated, never
blanket. All policy/metadata-side — outside landmine #17.

**July 30 2026 retention pass** (drift guards:
`tests/test_intros.py`, `tests/test_shorts_selector.py::TestShortsClipLength`,
`tests/test_youtube_policy.py::{TestShortsSupplyLadder,TestMaxShortsCeiling}`,
`tests/test_ru_dub.py::TestClauseTrim`):

- **Every episode now opens on its hook** (AUDIO — A/B-listen per
  landmine #17). Ten seconds of theme music played alone, then
  `build_intro_line` emitted a ~35-word greeting with the date, so the
  first fact arrived around second 28. Long-form median retention was
  10.7% EN / 6.3% RU with average view durations of 18-85 s on 5-13
  minute videos; Shorts, which skip the intro, run ~42% on the same
  audio. `build_intro_line` now emits one short identity line,
  `build_cold_open_spec` injects the shared cold-open rules into all 15
  podcast prompts (no example sentence — de-seed by shape), the prompts
  put `{hook}` before `{intro_line}`, and `voice_intro_delay` is 0 with
  `intro_duration` 3 network-wide. **Music still plays from t=0 and the
  sidechain holds it at the same level under the opening line as
  mid-episode (-31.7 dB either side, verified by render), so this is a
  cold open in structure, not a bare one in sound.** Three shows keep a
  short `identity_tail` / `identity_template` because their line carries
  something load-bearing: DP Pod names both hosts, Age of AI discloses
  its AI host, and the Russian shows would otherwise be handed English.
- **Shorts run 35 s** (was 55 default / 40 on five shows). Median Short
  holds 21 s (n=348, 90-day window), so length mostly decides what
  percentage that is: 38% at 55 s, 60% at 35 s. The dataclass default and
  the four `getattr` fallbacks moved too — `ru_dub` / `lang_dub` /
  `youtube_shorts` each resolve through one, so a stale default would
  ship long Shorts on the dub channels only.
- **Shorts supply ladder gained a 3-Short band** at 20 vpd (`SHORT_VPD_BANDS`
  + `shorts_for_vpd`). RU spacex 62.3 / FF 60.5 had the same supply as
  RU MIT 4.9. Two silent caps had to go first: `build_policy` carried a
  second copy of the threshold rule (logged "-> 3" and wrote 2), and
  `ru_dub`/`lang_dub` each had a local `min(2, ...)` — and the band's
  members are RU dubs, so those literals would have made it a total
  no-op. The ceiling is now `engine.youtube_policy.MAX_SHORTS_PER_EPISODE`,
  enforced in `resolve_publish_plan`.
- **Dub Short titles trim to a clause** (`_clause_trim`). 26% of published
  FR Short titles ended on a dangling preposition (RU 5%, EN 1%) because
  the title is cut from the translated LONG title at 70 chars and French
  runs ~15-20% longer than its English source. Per-language stop-word
  tails, a 55%-of-budget floor, and an unregistered language stays a
  plain word trim.

### Testing

```bash
pytest                             # Run all tests
pytest tests/test_utils.py         # Pure function tests (AST extraction)
pytest tests/test_rss.py           # RSS feed validation
pytest tests/test_audio_commands.py  # ffmpeg command structure tests
pytest tests/test_integration.py   # Pipeline integration tests
```

Tests use AST extraction + `exec()` to load functions from show scripts because
`tesla_shorts_time.py` has a `SystemExit` guard preventing import.

**Phase 1 hardening guards (May 2026):** the network-evolution roadmap's first
phase added safety nets that the `run-show.yml` smoke step now runs on every
episode:

- `tests/test_generator.py` — the LLM-call path (`load_prompt` incl. the new
  shared-snippet include mechanism, `_call_grok` request/response shaping,
  refusal detection, fallback-model resolution). Catches a breaking Grok
  request/response change without spending credits.
- `tests/test_show_memory.py` — pins `engine.tesla_memory`'s load/save/build
  contract (and the first-run copy-isolation fix) *before* Phase 3 generalizes
  it to other shows via `engine/show_memory.py`.
- `tests/test_prompt_fidelity.py` — every show's prompts exist, are non-empty,
  and render without a malformed-brace crash.
- `tests/test_episode_validity.py` — (Run Tests only since Oct 18 2026; never the per-show smoke step) the latest committed digest per show meets
  a conservative word floor and isn't a refusal.
- `tests/test_pipeline_safety.py` — the three safety scripts below.

### Code Style

- No linter configured; scripts are large single-file programs
- Functions are defined inline (not imported), which is why we're extracting
- `logging` for all output; `sys.stdout` handler
- `pathlib.Path` for all file operations
- `tenacity` for retry logic on API calls

### Prompt composition + pipeline safety scripts (Phase 1, May 2026)

- **Shared prompt snippets.** `engine.generator.load_prompt` resolves
  `<<include: relative/path.txt>>` directives (relative to the including
  prompt's dir, recursive, cycle/depth-guarded) **before** `{placeholder}`
  substitution. Canonical snippets live in `shows/prompts/_shared/`. The
  mechanism is **opt-in**: a prompt with no directive renders byte-for-byte as
  before, so existing prompts are unchanged. Do NOT bulk-rewrite prompts to use
  includes without re-running `test_prompt_fidelity.py` + A/B listening (it
  changes generated output). See `shows/prompts/_shared/README.md`.
- **Fail-loud safety nets** (all *loud-but-non-blocking by default*; pass
  `--strict` to hard-fail in a dedicated guard job):
  - `scripts/backfill_content_lake.py` — evaluates the rebuilt lake and emits a
    GitHub `::error::`/`::warning::` annotation when it's empty/thin (was a
    silent failure mode that broke dedup/recaps/search).
    **July 24 2026 orchestration pass** (drift guards:
    `tests/test_memory_lake_expansion.py::TestLakeOrchestration`): the lake
    ENGINE was healthy (1,200+ episodes, 1.5M words, FTS working) but three
    orchestration bugs hid it. (1) The run-show **finalize job** rebuilt the
    public search index on a fresh checkout WITHOUT backfilling the
    gitignored lake — every episode (~13×/day) committed a zero-episode
    `site/data/search-index.json`, so site search served 0 results most of
    every day (nightly repaired it once; the next morning wiped it again).
    Finalize now backfills before `build_search_index.py`, and the index
    builder additionally REFUSES to overwrite a populated index with an
    empty one (loud `::warning::`, non-blocking). (2) **Nightly built the
    dashboard BEFORE the backfill**, so `api/dashboard.json` reported
    "lake: 0 episodes" every night (the mission-control card showed a
    permanent false empty-lake warning) — steps reordered. (3) Shows that
    don't produce run_show digests (**Age of AI**) never entered the lake;
    the backfill gained a summaries-JSON fallback importer so every
    published episode is searchable. The lake remains a rebuild-from-repo
    cache by design: committed `digests/**` are the durable store, the DB
    is derived — safe to delete, cheap to rebuild (~30 s), reliable for
    future content products via `query_show_range` / `search_content` /
    `query_by_entity`.
  - `scripts/youtube_quota_preflight.py` — sums quota for YouTube-enabled shows
    and annotates when projected over the 10k/day budget (landmine #20). Wired
    as a preflight step in `run-show.yml`.
  - `scripts/post_run_summary.py` — positive heartbeat: composes an all-clear /
    cost / quota / RSS-freshness line from `api/dashboard.json` and POSTs to
    `NOTIFICATION_WEBHOOK_URL` (clean no-op when unset). Wired into the finalize
    job.
  - `scripts/retitle_youtube_videos.py` — repairs transcript-fragment titles on
    ALREADY-PUBLISHED videos. Before the July 18 2026 title bundle, a Short's
    title was the raw opening text of its clip: 11% of Shorts published before
    that date carry a fragment title against 1% after. The pipeline was fixed
    forward; the back catalogue never was, and those videos are still live and
    still the first thing a new viewer sees. Rebuilds the title from the
    episode's DIGEST HEADLINES (the Short's own stored `hook` IS the fragment
    for exactly the videos this repairs, so it can never supply the
    replacement; sibling Shorts take different headlines so one episode does
    not produce four identically-titled clips). **Dry run by default** —
    `--apply` is required to write. Run it from Actions ("Retitle YouTube
    Videos"), not a laptop: the YouTube credentials live there, and a local run
    prints its plan then writes nothing. ~51 quota units per video. 31 fixable
    at last count.

### Growth & trust surface (Phase 2, May 2026)

Additive web/distribution enhancements (source-only — generated HTML is
regenerated by the pipeline's finalize `--blogs` step, so these propagate
site-wide within a day without committing hundreds of HTML files):

- **AI-transparency badge.** Reusable `ai_badge(path_prefix, is_ru)` macro in
  [`templates/_macros.html.j2`](templates/_macros.html.j2), wired into blog
  posts and show pages, linking to `ai-disclosure.html`. Turns the AI question
  into a trust signal. Drift guards assert the wiring.
- **PodcastEpisode JSON-LD completed.** The blog-post `PodcastEpisode` block
  previously rendered empty `url`/`datePublished`/`contentUrl`/`transcript`
  (the vars were never supplied). `engine/blog.py` now passes `page_url`,
  `date`, `audio_url`, `transcript_url`, and the template builds the block as a
  dict piped through `tojson` (always-valid JSON; `isPartOf` → PodcastSeries,
  `inLanguage`, optional members only when present; `name` prefers the episode
  hook over the show-name title fallback).
- **Transcript anchored.** The inline transcript `<section>` carries
  `id="transcript"`; the JSON-LD `transcript` points at `…#transcript`.
- **Share + attribution.** Blog share row adds Facebook + Email and tags every
  network link with per-source UTM (`utm_medium=share`) via the existing
  `with_utm` filter, so shared traffic is attributable.
- **Not done (deliberate):** per-episode OG images were deferred — generating
  hundreds of PNGs into git worsens landmine #1 (repo size); revisit via R2
  like the gallery. Live Buttondown subscriber count / referral need a runtime
  API dependency and were left out. Drift guards: `tests/test_phase2_growth.py`.

### Grok prompt + voice review (June 10, 2026)

All 49 show prompts + in-code prompts (outline/retry, weekly synthesizer,
episode reviewer, X fetch) reviewed against prompt-engineering practice —
canonical writeup: [`docs/prompt_review_2026_06_10.md`](docs/prompt_review_2026_06_10.md);
drift guards: `tests/test_prompt_quality_pass.py`. Voice/TTS config verified
consistent and deliberately untouched (landmine #17). Shipped:
`engine/utils.fix_phonetic_garbles` repair layer on every digest + script
("nassa" had shipped verbatim in a published transcript — bans alone don't
stop a known finite failure set); the X-post fetch prompt now requires
SUBSTANTIVE posts (emoji spam + a slur one-liner had flowed into prompts);
stale "ElevenLabs engine" claims removed from the 9 remaining podcast
prompts; MIT's residual "at least 2500 words" contradiction fixed; Tesla
digest selection rules unified (count-tier table vs judgment rule) and the
template's 🎙️ emoji removed; reviewer QUALITY_SCORE got calibration
buckets; the weekly synthesizer must ground cross-domain threads in actual
coverage; Tesla's system prompt now explicitly forbids filling gaps from
training-data knowledge. Deferred behind A/B (in the doc): few-shot
exemplars for prompts lacking one, converting ban-lists to rotation menus.

### Network-wide show quality pass (June 2026)

After the Tesla (#573) and Modern Investing (#574) flagship passes, the
same review ran across the other ten shows. Drift guards:
`tests/test_network_quality_pass.py`.

- **`engine/show_memory.py` inherited both Tesla memory bugs** (it was
  generalized from `tesla_memory` *before* the fixes). Theme mining read
  the narrative TEMPLATE every episode — "open questions" hit count 96 on
  Models & Agents, Fascinating Frontiers, AND Planetterrian — now
  digest-only with the shared `_THEME_STOPWORDS`; the three live histories
  were scrubbed. Narrative trackers were seeded May 29 with no program
  ever updated; `auto_update_narrative_from_digest` (ported from Tesla)
  now advances per-program "last covered on air" freshness each episode
  via `memory_post_generate`, and the status block gained the
  make-continuity-audible callback wording.
- **`podcast_expand_below_target: true`** added to the eight chronically-
  short shows (M&A, FF, PT, MAB, Env Intel, Финансы Просто, Unintended
  Consequences, First Principles — all were ≥50% below target, several
  100%). Models & Agents also got an explicit `min_podcast_words: 1500`
  (was relying on the implicit default).
  **SUPERSEDED 2026-07-29 — this flag is now `false` on the 11 shows that
  have a digest-side lever.** Measured over 901 committed episodes, 81%
  still shipped BELOW target *with* the retry running (Tesla 96.7%, M&A
  95.2%): it fires on nearly every episode and almost never reaches the
  goal, because the ceiling is the DIGEST. It also pads by
  paraphrase-duplication (the July 28 pass had to add
  `_dedup_expansion_sentences` to strip its near-duplicates), so what it
  did ship was the weaker copy — and the July 18 playbook had already
  banned podcast-side length levers network-wide. Only `env_intel` and
  `finansy_prosto` keep it, because they have no digest lever yet;
  give them one before switching theirs off. Drift guard:
  `tests/test_cost_efficiency_pass.py::TestLengthLeverPolicy`.
- **Hook-led X teasers network-wide**: Omni View / FF / Planetterrian's
  hardcoded teasers and the generic fallback (used by Unintended
  Consequences) now lead with the episode hook + link the episode blog
  post, matching Tesla/MIT. Models & Agents/MAB/Env Intel/Russian shows
  don't post to X (unchanged).
- **Boilerplate-tic bans** (prompt edits — A/B-listen per landmine #17):
  M&A "This development sits within the ongoing…"; FF "you know what's
  fascinating / blew my mind" deep-dive openers; PT "this development
  fits the tracked program on X" (ran 6×/episode); Omni View's
  every-story "the strongest case for X / for Y" template (now rotates
  three framings, "strongest case" ≤1×/episode); UC "That wraps today's
  case" closer. Plus: MAB requires ≥2 concrete "try this" experiments;
  Env Intel Compliance Brief required even on thin-news days; Финансы
  Просто requires 3-4 practical tips (was 2 → chronic shortfall).
- **RSS channel descriptions rewritten** as value props for the listing
  pages: M&A, FF, MAB, Omni View (Steel Man), Env Intel (odd-weekday
  cadence + Compliance Brief), Unintended Consequences. PT and the two
  Russian shows already had strong descriptions (kept).
- **Topic-queue restock** (the narrative shows' critical operational
  risk): Unintended Consequences +14 → 38 unproduced (~7.6 wk runway, was
  ~4.8); First Principles +12 → 27 unproduced (~3.9 wk, was ~1.3 and
  about to dry up), preserving the concrete/opportunity alternation.
  **July 24 2026 — restocks are now AUTOMATED** (drift guards:
  `tests/test_queue_restock.py`): `.github/workflows/restock-topic-queues.yml`
  (daily 13:37 UTC + dispatch, `force` input) runs
  `scripts/restock_topic_queues.py` — trigger-gated (FPD <4wk, UC <5wk;
  refills to ~8wk) Grok generation against per-show restock prompts
  (`shows/prompts/*_restock.txt` — full queue history injected for dedupe,
  category balance for FPD's alternation, an explicit never-invent honesty
  rule since briefs become episodes). Validation rejects thin briefs, bad
  categories, id dupes, and fuzzy near-duplicate titles vs the ENTIRE
  history (produced included); existing entries are never modified; the
  workflow re-runs `TestNarrativeQueueRunway` BEFORE committing, so the
  runway floors (3.0/4.0wk) are now the alarm that the AUTOMATION broke,
  not a manual chore. **Sep 17 2026:** it did break — four nights on
  grok-4.6 alone (no JSON array 09-14, `APIConnectionError` 09-16) while
  UC drained to 3.7 wk; `generate_candidates` now retries one failed
  primary call on `FALLBACK_RESTOCK_MODEL` (grok-4.3) and the result
  records `model` (`TestModelFallback`). **Same day, later:** the
  15:29 UTC dispatch made the count 0 for 11 — grok-4.6 timed out at
  300 s on BOTH shows and grok-4.3 answered each in under a minute — so
  `restock-topic-queues.yml` sets `NERRA_RESTOCK_MODEL: grok-4.3` (the
  documented override; delete the line to trial 4.6 again). That run
  also exposed a second blocker: the model answered, FPD was refilled
  4.0 → 8.0 weeks, and the workflow then died in its own validator
  because `resequence_unproduced` interleaved UC's three GATE-DEFERRED
  head entries while `test_uc_unproduced_interleaved_not_clustered`
  measures the pickable sequence without them; nothing was committed.
  Deferred entries now stay in place and only pickable entries are
  interleaved (`TestResequenceSkipsDeferred`). Age of AI's deliberately-empty queue is not
  registered and must never be. Generated topics sit unproduced for weeks
  — prune any weak ones directly in `shows/topic_queues/*.yaml`.
- **Финансы Просто YouTube category** fixed 25 (News) → 27 (Education).
- **Operator items (not code):** localize the Russian shows' spoken AI
  disclosure (still English on the Olya voice — A/B per #17); decide
  First Principles distribution-on after the queue/length fixes settle
  (review recommends waiting to ~Ep15); confirm X handles for the
  X-enabled shows so the follow CTA can be set.

### Network editorial review (July 2026)

Full editorial pass over every transcript in the 2026-06-18 → 07-02 window
(~150 episodes, all 13 shows — fit, interest, content quality, positioning).
Canonical writeup:
[`docs/reviews/network_review_2026_07_02.md`](docs/reviews/network_review_2026_07_02.md);
prediction verdicts + new entries in every per-show ledger
([`docs/reviews/ledger/`](docs/reviews/ledger/) — new ledgers for
privet_russian, modern_investing, network). Four cross-cutting classes:
(1) **number/name garbles in flagship positions** — the comma-blind
currency/ordinal formatter shipped "fifty-nine dollars,990"-class hooks on
Tesla/SpaceX (fixed, `assets/pronunciation.py`); (2) **guard/retry mechanisms
degrading the audio they protect** — the missing-closing guard's literal
signature match double-spoke MAB's closing 5/15 (fixed: fuzzy match in
`engine/pipeline.py`) and the expand-below-target retry pads by
paraphrase-duplication (fixed: near-duplicate sentence stripping);
(3) **third-generation seeded-template convergence** (OV "Both sides
agree…" 12/12, EI "There's a nuance here…" 6/6, MAB/FP/MIT/SpaceX tics) —
ALL prompt de-seeds are PROPOSED-not-applied pending operator A/B (landmine
#17); meta-lesson: de-seed by shape, never with a quotable example;
(4) **same-day sibling overlap** — PT astronomy fetch filter (the pass's
highest-leverage fix), FF lookback 2→7 + ephemeris filter, SpaceX junk-title
filter. Also shipped: EI Closing/Teaser-before-body chapter reorder, MIT
voided phantom trades (honest 37-trade record + review-once), PR vocab
no-reteach 8 + WOTD never-repeat + theme gap, network-wide Source-line scrub
(FP scaffold leak), UC/FPD queue hygiene, Tesla second-brand-normalizer
completion, and `review_snapshot.py` Unicode + missing-final-Closing fixes.
Operator items: three same-day double-publishes + SpaceX's silently missed
June-28 recap (scheduler forensics).

### Network goals & differentiation audit (July 18, 2026)

Operator-requested whole-network review — canonical writeup:
[`docs/reviews/network_review_2026_07_18.md`](docs/reviews/network_review_2026_07_18.md).
Verdict: the factory is world-class (100% run success, ~90 eps/week in 5
languages at ~$35-40/mo) while the funnel is the product gap (3,070
downloads/30d, 3 newsletter subs); differentiation is TOPICAL AUTHORITY
(Tesla+M&A+SpaceX = 53% of downloads), and the two most differentiated bets
(DP Pod, Age of AI) have no market feedback loop. Shipped (all
code/metadata-only): **closing-is-final chapter invariant** in
`engine/chapters.py` (the 07-16 rotating network outro's sibling-show plugs
were stolen by un-anchored body markers AFTER the closing — Tesla Ep544
"First Principles" at 642s, MIT Ep104 "Investor Education"; terminal signal
is the closing TITLE set, not the `where: end` anchor, because EI anchors
only its Teaser); **dp_pod Network-pick rotation memory**
(`_recent_network_picks` — FF was the pick 5/10 with a fixed host+frame); **July 20 2026 Ep016 name-swap fix + banter pass (operator listened:
  hosts signed off as each other; wants human flow + comedic banter):**
  the LLM rotated the supplied closing's speaker labels to dodge a
  same-host boundary (turn before the closing and the closing's first
  line were both DAN's), so Dan's voice said "I'm Patrick Novak" on air.
  Two-layer fix: `_fix_self_introduction_labels` in
  `engine/tts_dialogue.py` relabels any turn whose self-intro names the
  OTHER host (deterministic; joint intros untouched; verified self-healing
  on the real Ep016 script), and the podcast prompt forbids closing-label
  rotation outright. Flow: Ep014-016 shipped ZERO exclamations, ZERO
  voice tags, 12-26% one-liners against the DELIVERY asks — enforcement
  moved INTO the Positive Papers segment spec (per-story 3+ turn volley +
  earned exclamation) and a COMEDY block (2-3 character-driven beats,
  one callback, device rotates daily, no catchphrases). Prompt edits
  change shipped audio — A/B-listen per landmine #17. Drift guards:
  `tests/test_tts_dialogue.py::TestSelfIntroductionRelabel`,
  `tests/test_dp_pod_show.py::TestEp016NameSwapAndBanter`;
**dashboard voice-baseline fix** (stale ElevenLabs RU baseline flagged
FP/PR/Age-of-AI as drift on every build; now Olya `0b875ae2` + sanctioned
`ara`); **snapshot fetch-filter leakage counter** (scored three long-pending
filter predictions immediately: SpaceX/Tesla clean, FF ephemeris still
leaking 3/10 → reopened); **playbook category rules** from the 15-ledger
meta-review (podcast-side length levers formally banned network-wide via
`do_not_retry` — ~10 misses vs 1 hit; de-seed-by-shape + rotation memory
required; conditional predictions banned; two-miss escalation; ledger entry
required for every prediction-bearing pass). Verified with new data: the
07-16 denoise chain IS engaged in shipped audio (re-denoising shipped
episodes removes ~0 dB). P0 operator item: **FP/PR publish off-schedule via
the daily-audit retry path** — CRON_MAP/Worker say Monday-only,
`review_episodes.py` says even days, FP's description says daily; 8
unplanned episodes in one week; pick a cadence and align all three. A/B
proposals (NOT applied): FP double-seeded templates (100% saturation), MIT
seeded transition, PT takeaway tic, PR secret opener, FF ephemeris
digest-scope bullet. Drift guards:
`tests/test_chapters.py::TestClosingIsFinal`,
`tests/test_dp_pod_show.py::TestNetworkPickRotationMemory`,
`tests/test_review_agent.py::{TestSnapshotFetchFilterLeakage,TestDashboardVoiceBaseline}`.

### Flagship review — SpaceX, Tesla, Models & Agents + shared pipeline (Sep 4, 2026)

Operator-directed pass over the three shows carrying >50% of downloads.
Canonical writeup:
[`docs/reviews/flagship_review_2026_09_04.md`](docs/reviews/flagship_review_2026_09_04.md);
ledger entries in `spacex.yaml` / `tesla.yaml` / `models_agents.yaml`
(prior predictions scored; new ones filed). Drift guards:
`tests/test_flagship_pass_2026_09_04.py` + the per-show quality-pass
files. Rules that bind from this pass:

- **A stock quote's VERB comes from the clock, never from which data
  source answered.** SpaceX runs ~07:30 UTC (03:30 New York, before
  pre-market), so `fast_info.last_price` was the prior close on EVERY
  run and 10/10 closings said "is trading at" (Ep084–086 aired Friday's
  move as live three days running); Tesla's history source hard-coded
  REGULAR and an 11:27 ET retry (Ep585) spoke "closed at $351.73" for a
  $345.82 close. `shows/hooks/spacex.py::_market_is_open` and
  `shows/hooks/tesla.py::_regular_session_open` (INTRADAY state) decide
  the wording; a zero move is "unchanged", never "up/down zero percent".
- **The spoken price line is never a Shorts opener**
  (`engine.shorts_selector.is_price_line`) — the numeric-reveal scorer
  loved it (5/68 SpaceX EN Shorts titled "SPCX Trading at $141.50 Up 1%").
- **Google News re-surfaces OLD articles under fresh index dates** (Ep088
  led with a two-year-old "23rd flight reuse record"). `engine/fetcher.py`
  drops an article whose resolved publisher URL path (`/YYYY/MM[/DD]/`)
  is older than the fetch window; undated URLs still pass (open item).
- **Both prompts can seed a tic.** M&A's "Everyone talks about…" deep-dive
  opener (10/10) was supplied verbatim by the DIGEST prompt and the podcast
  prompt; three Grok-generated reviews aimed at the podcast layer only and
  every one shipped nothing. Check every prompt that touches a section
  before de-seeding one. "pop the hood" is now the REQUIRED M&A deep-dive
  anchor (it was one of two example openers, and the model elected the
  other — three episodes shipped with no Under the Hood chapter).
- **Chapter titles never carry links** — `engine/chapters.py` and
  `engine/grok_imagine.py` flatten `[label](url)` and drop `@handle`
  tails (M&A Ep161 shipped "…: [@AnthropicAI](https" as a chapter). M&A's
  literal `**Title: Source Name**` placeholder (the SpaceX Aug-15 root
  cause) is now replaced too; `env_intel_digest.txt` still carries it.
- **A topic word is not a section marker.** M&A's `open.source` alternate
  fired on "open-sourced Pipette" at 7–16% of the script, titled the whole
  news body "Practical & Community" and, by clearing `min_chapters`,
  suppressed the digest-headline navigation. Removed.
- **RSS item `<link>` is the episode blog page** (was the MP3 on the
  newest item only; the re-add path never wrote it) and **feeds serialize
  newest-first** (feedgen prepends by default — every feed was
  oldest-first in document order). Other `update_rss_feed` callers keep
  the legacy MP3 link until they pass `episode_page_url`.
- **Whitelist globs, not literals:** `nightly-maintenance.yml` listed five
  `*_performance_tracker.json` paths while `update_performance_trackers.py`
  writes ten — six memory shows' trackers were discarded every night.
  Same class: `site/data/gallery/*.json` (new per-show manifest slices so a
  show page loads ~1/15th of the 14 MB manifest) is whitelisted in BOTH
  committing workflows.
- **Null stays null on the language card:** OP3 answers 404 for feeds it
  never indexed (every ZH feed + three FR); the dashboard had been showing
  them as `0 downloads, measured: true`. Six of the 14 paid language feeds
  are unmeasurable by construction — submit them to Podcast Index or
  switch them off (operator).
- `wall_duration_s` (stages + timed counters) is the pipeline-health
  duration; `total_duration_s` covers fetch/digest/gate only (spacex p50
  read 99 s for ~29-minute runs). The blog player routes through the OP3
  prefix so blog plays count. `youtube_tmp/*_square.jpg`, `*.social.json`
  and `*.chapters.ffmeta` are ignored (656 tracked files / 54 MB removed).
- Prompt/audio-affecting changes in this pass (A/B-listen per landmine
  #17): M&A digest + podcast de-seeds and the required anchor, two new M&A
  closing variants, the shared `engine/show_memory.py` continuity example
  (de-seeded by shape — M&A had reproduced it verbatim with tracker
  display names 8/10), the SpaceX/Tesla closing-line wording.

### Network delivery review — content density over narration (Sep 5, 2026)

Operator brief: the flagships read as "narrative driven with redundant
repetition"; the ask is content- and information-driven episodes with a
consistent, engaging delivery across podcast, blog and video. Canonical
writeup:
[`docs/reviews/network_delivery_review_2026_09_05.md`](docs/reviews/network_delivery_review_2026_09_05.md);
ledger entries (predictions to score) in eight per-show ledgers + `network`;
experiment `network-content-discipline-2026-09` (readout 2026-09-26). Drift
guards: `tests/test_delivery_pass_2026_09_05.py`. Four audits agreed the
cause was mechanical, not the host's taste, and the rules below bind:

- **The script stage must WRITE, not de-markdown.** On the worst days 62–78%
  of a script's 8-word phrases were verbatim digest text, so every digest
  duplicate shipped as audio. `engine/script_audit.py` measures it per
  episode (`script_digest_overlap_pct`, `script_repeated_facts`,
  `script_filler_pct`, `script_hook_restated`; `::warning::` above
  thresholds; `review_snapshot.py` tabulates it). It is a READ-ONLY
  instrument — a review re-reads the baseline before moving a threshold,
  and a rule that changes the script belongs in the prompt or in a gate,
  never in the audit.
- **The digest's "ZERO STORY OVERLAP" rule is enforced by code, not prose.**
  `engine/digest_overlap.py` drops a later item that repeats an earlier
  one (same Source URL; headline sharing ≥50% of salient words; body
  sharing ≥50% of salient vocabulary — Tesla Ep592's five re-headlined
  X Takeover items carried no Source lines, so URL matching alone was
  blind). Runs before the validator and again after the structural
  regeneration; a section it empties triggers the existing one-shot
  regen, which is the correct outcome. Blocks split at numbered items AND
  header lines — the templates put `### Top News` directly under the hook.
- **Memory is for accuracy, never narration.** `show_memory`'s composed
  section used to inject *MANDATORY CONTINUITY: add 1-2 natural sentences
  of where today's development fits in the ongoing arc* on every story of
  every memory show, contradicting the status block's "at most ONE" — the
  model obeyed the mandatory line. Now: one audible callback, only with a
  delta (what changed since prior coverage); no arc sentences, no
  open-question recaps. Tesla's bespoke `tesla_memory` block still carried
  the quotable "Remember, we covered…" example the shared block lost on
  Sep 4 — gone.
- **`shows/prompts/_shared/content_discipline.txt`** is included in the nine
  English news-show podcast prompts: digest is source material not a
  draft; sentences follow facts (2–6 per story, cut below two, never "no
  details were provided"); one owner per fact; a story ends on its last
  fact; transitions carry information or are dropped; source named once;
  the same voice every day. It is shape-only. **Every worked example
  sentence was removed from seven podcast prompts** (FF Ep182 L2, PT
  Ep172/173, OV Ep164/165 and Tesla Ep594 all shipped a prompt's own
  specimen line) — "described shape, never a quotable line" now applies to
  the EXAMPLE OF IDEAL STORY COVERAGE blocks too, not only to tics.
- **A deep dive is a second story, not a second pass.** M&A's Under the
  Hood re-explained a news item in 5/6 episodes (the exception was the
  densest episode); OV's Understanding the Issue re-narrated the lead;
  SpaceX's Deep Dive carried two numbers, both already spoken. Every
  deep-dive spec now forbids restating a covered body and carries a
  numbers floor (SpaceX 5, M&A 4, Tesla 3). Chapter anchor phrases stay
  as phrases the writer builds a sentence around.
- **Digest items: sentence count follows fact count.** Fixed "4–5 / 5–7
  sentences" produced a fifth sentence restating the first and generic
  consequence prose ("Buyers gain a clearer picture…"). Per-item "what to
  watch next" became a dated next step only when the source names one;
  "why it matters" only when the source explains it. Tesla's X Takeover
  items must carry Source lines; M&A gained ONE STORY = ONE ITEM.
- **One closing per flagship** (SpaceX, Tesla, M&A, MIT) — the rotating
  pool read as register drift. This reverses the Sep 4 M&A pool expansion
  on purpose; the sibling plug and website surface still rotate after it.
  MIT's Market Pulse speaks index levels only; portfolio numbers belong to
  Portfolio Performance alone (Ep160 read the record twice).
- Bugs from the transcripts: "VS Code" is spelled out before the versus
  rule ("versus versus Code"); `r/teslamotors` is spoken as a subreddit
  name; a line repeated inside the closing eight is collapsed (MIT Ep159's
  doubled gallery plug).
- **Same-day readout (Tesla Ep595 old prompts vs Ep596 new):** filler
  3 → 0, digest duplicates 0, one pinned closing — but digest-verbatim
  only 63% → 51% and the essay still re-told a covered story. So:
  `llm.script_rewrite_gate_overlap_pct` (40 on the nine English news
  shows, 0 = off) re-runs the script stage ONCE with the copied sentences
  named when the finished script carries ≥40% verbatim 8-grams; the
  rewrite is kept only when it copies less and is ≥70% of the original
  length (`engine.pipeline._script_rewrite_gate`; metrics
  `script_rewrite_gate_*`). It is a REWRITE gate, never a length lever —
  it does not fire on word count, so it is not the banned podcast-side
  retry class. Tesla's First Principles gained the TOPIC DISTINCTNESS
  rule M&A's Under the Hood has. A mechanical essay-vs-item overlap note
  was prototyped and rejected (no threshold separates re-tells from
  unrelated essays).
- **Sep 6 readout (first full slate with prompts + gate live; the
  "Sep 6 readout" section of the review doc):** OV/FF/MIT clearly
  better, SpaceX/M&A/MAB/Tesla mixed, PT worse. Three defects the
  whole-script number could not see, all fixed in
  `engine/script_audit.py` + `engine/pipeline.py`: (1) **the gate threw
  away a clean rewrite** — Tesla Ep597 went 61 → 2% verbatim and was
  rejected because the floor was pinned to an over-long draft; the floor
  is now 70% of **min(draft, target)** and `script_rewrite_gate_reasons`
  / `_reject_reason` / `_rewrite_words` are recorded — a silent rejection
  is the silent-number class. (2) **Sections were read aloud under the
  threshold** — SpaceX Ep092 sat at 24% overall with its Engineering
  Deep Dive 10/13 digest sentences (word-swap paraphrase, 59% 8-grams);
  the deep-dive block was 78–100% verbatim on 72 of the last 90 episodes
  across nine shows. `copied_sections` scores each digest header block
  (≥100 words; ≥80% 8-grams, or ≥70% sentences near-matched with ≥25%
  verbatim) and the gate fires on it, naming the section. It WILL fire
  on most episodes at first; `script_rewrite_gate_copied_sections_after`
  says whether the retry clears it. (3) **An orphaned hook** — PT Ep175
  opened on a story the body never told; `hook_coverage` (share of the
  opener's salient words the body speaks; PT 0.09, everything healthy
  0.33–1.0) fires the gate below 0.3. Also: the headline-echo tic
  (Tesla ×6, M&A ×9 — a spoken headline then the body restating it) and
  attribution-only sentences are named in the shared snippet; MIT's three
  prompt-supplied lines aired verbatim and are de-seeded; `US$95` had no
  pronunciation handler ("USninety-five dollars" on air) — the `C$` path
  now handles `US$`/`USD$`; MAB keeps every number the briefing gives.
  Guards: `TestSep6*` in `tests/test_delivery_pass_2026_09_05.py`.
- **Sep 7 readout (first slate with the section/hook gate live; "Sep 7
  readout" in the review doc):** the gate fired on all nine gated shows
  and every rewrite was accepted — first drafts still copy 42–66% daily
  and the retry brings them to 0–5%, so **the gate, not the prompt, is
  what keeps scripts written**; budget one extra script call per gated
  episode. Two side effects, both fixed: (1) **rewrites paraphrased the
  NAMES** — "Megapack 3" became "the latest version of the large battery
  packs", "Raptor V3" was never spoken in the body; `script_audit.
  entity_retention` (share of the digest's capitalised mid-sentence
  tokens the script speaks) fell Tesla 73→53%, M&A 81→52%, OV 100→65%.
  The gate now rejects a rewrite more than 15 points under its draft
  (`reject_reason=names_lost`, `REWRITE_GATE_MAX_ENTITY_DROP`) and the
  appendix says names are never paraphrased. (2) **Rewrites shrank to
  the stated floor** (Tesla 985 words on a 1,400 target) — the appendix
  now anchors on the draft's length and records
  `script_rewrite_gate_original_words`. Also: the section test had read
  zero sections everywhere because run_show's podcast digest strips the
  `#` markers — the RAW digest is passed as `section_digest`; a glued
  `Nk` tail is a name ("Nutritionfive thousand" aired), GPU model numbers
  speak as pairs ("RTX fifty ninety"), the subreddit handler no longer
  doubles "the". Guards: `TestSep7*`.
- **Sep 9 readout (Sep 8 slate; "Sep 9 readout" in the review doc): the
  rewrites stopped copying and started DROPPING.** First drafts are now
  under the 40% threshold on 5 of 9 shows before any retry, but a new
  measure — `script_audit.digest_coverage`, the share of the digest's
  sentences the script tells in any wording (`script_digest_coverage_pct`,
  warn < 50, snapshot column) — read 77–95% on copied scripts and 43–65%
  on the rewritten week (Tesla Ep599: two stories skipped, 8 of 17
  numbers, 915 words on 1,400). **Read overlap and coverage together:
  the goal is overlap ≤ 15% AND coverage ≥ 70%; either alone is gamed by
  the other.** The "two to six sentences" rule read as a cap and now
  says every digest fact is spoken ("the floor, not a menu"); the gate
  rejects a rewrite 15 points thinner than its draft (`facts_lost`);
  a rewrite that copies less overall with no new copied section ships
  even if a flagged section persists (M&A Ep167's better rewrite was
  thrown away); `llm.script_rewrite_gate_attempts` (default 1, Tesla 2 —
  its Sep 8 rewrite copied MORE and the draft aired) takes bounded
  attempts each judged against the draft. Also: `_lint_digest_placeholders`
  warns when the digest carries a placeholder-shaped number ("2xxt/s"
  became "half those rates" on air — `digest_placeholder_tokens`), and
  a digit glued to a letter is a model number, not a range ("Xeon Efive
  to two thousand six hundred ninety-six" aired for E5-2696). Two of the
  three short Sep 8 scripts were not thinning: SpaceX's digest had two
  items from 14 articles (a fetch-famine day) and M&A's 1,044 words were
  the headline-echo padding removed with 33 numbers kept — coverage
  tells them apart where word count cannot. Guards: `TestSep9*`.
- Every prompt-side item above is landmine-#17 A/B; the engine modules are
  removal-only or read-only and are not.
- **Sep 12 2026 — the rewrite gate is GONE.** Measured Sep 9–12 across
  the nine gated shows: fired on 30/35 episodes, accepted 11, rejected
  17 (`facts_lost` / `names_lost` / `copies_more`). A two-pass script
  could be written (1–4% verbatim, 40–60% coverage) or complete (55–77%
  verbatim, 85–97% coverage), never both, because the script stage
  re-told a finished document; every patch since Sep 5 moved the tension
  and none resolved it. Do not re-add a script retry of any shape — the
  fix is the generation design (next section). `engine/script_audit.py`
  stays as the read-only instrument.

### Simplification pass — one generation, enforcement everywhere, audience first (Sep 12, 2026)

Operator brief: the pipeline had become convoluted and costly and its
episodes were not trustworthy by construction; keep every show and every
cadence, do 1 (stop adding gates), 2 (claims enforcement on all shows),
4 (collapse digest + script into one generation) and 5 (audience as the
headline number). Plan + evidence:
[`docs/reviews/simplification_plan_2026_09_12.md`](docs/reviews/simplification_plan_2026_09_12.md);
experiments `combined-generation-2026-09-12`,
`source-integrity-strip-network-2026-09-12`,
`audience-headline-2026-09-12`; ledger `network` 2026-09-12. Drift
guards: `tests/test_simplification_2026_09_12.py`. Rules that bind:

- **The digest and the script are written in ONE model call**
  (`llm.combined_generation`, network default in `_defaults.yaml`; the
  Russian shows pin it off; narrative, dialogue, `podcast_model`-override
  and episode-1 runs stay two-pass by code — chained shows became
  eligible on Sep 17, see below).
  run_show renders the podcast prompt BEFORE the digest call through
  `engine.pipeline.build_podcast_template_vars` (extracted from
  `run_generation_phase`, which still calls it) with PART-1 placeholders
  for `{digest}` and `{hook}`; `generate_digest` appends it as PART 2
  after a fixed marker line, splits every response at the marker BEFORE
  any digest validation or post-processing, and stashes the script
  paired with the digest it was written from. `run_generation_phase`
  ships the stashed script only when the current digest still derives
  from that digest (a REPLACEMENT regeneration fails the line test —
  `combined_script_matches_digest`); a missing marker, a refusal-shaped
  or under-band PART 2, or a stale stash runs the script call exactly as
  before. Metric `combined_generation` = `combined` | `two_pass` |
  `combined_stale`. Output budget = `max_tokens + podcast_max_tokens`.
  **Sep 18 2026: the stash test compares normalised SENTENCES, never
  raw lines** — run_show rewrites the tail of every item line after
  generation (`transform_daily_body` turns `Source: <url>` into
  `Source: [domain](url)`, the Google-News resolver swaps the url), so
  on the first flagship slate Tesla Ep609 / SpaceX Ep104 / PT Ep187
  discarded their combined scripts at ~50 % line survival with no
  regeneration behind it and paid for the script twice.
  `engine.generator._combined_units` drops links, URLs, Source tails,
  markdown and punctuation; a trim, strip or link rewrite scores ~1.0
  on today's real digests and yesterday's digest against today's
  scores 0.0–0.02 (`TestStashSurvivesRunShowTrims`).
  **A combined run can never cost an episode; the first live slate is
  the A/B-listen set (landmine #17).** Revert = one line in
  `_defaults.yaml`.
- **Source integrity is enforced on every show** — see the Provenance
  section at the top of this file for the strip contract.
- **The audience headline leads every surface a decision is made from.**
  `scripts/build_audience_headline.py` → `api/audience_headline.json`
  (nightly, committed): per show and network — RSS downloads 7d/30d,
  the LAST COMPLETE week vs the week before (`wow_pct`; the current OP3
  week is partial and never compared), median first-week downloads per
  episode (episodes 7–30 days old; OP3 lists only a show's top episodes,
  so the network view names the carrying shows), views-weighted YouTube
  `averageViewPercentage` over 28 days by kind, newsletter subscribers.
  Null where unmeasured, never 0. It is the dashboard's FIRST tile, the
  review snapshot's FIRST section, and the second line of the daily
  summary. A review scores prompt passes against it first; the 99
  per-episode script metrics are diagnostics.
- **Nothing was pruned from the metrics file**: every unread key is
  recorded inside a retired branch or read by a human; deleting them
  changes nothing a listener gets. A NEW metric names its consumer.
- **Sep 17 2026 — first slate, scored** (review:
  [`docs/reviews/network_review_2026_09_17.md`](docs/reviews/network_review_2026_09_17.md);
  guards `tests/test_network_review_2026_09_17.py`). 100/100 runs, 0
  episodes lost, no placeholder leakage — and combined generation on
  5 of 56 episodes, because `podcast_chain: true` (every flagship) was
  an exclusion. **A chained show is eligible now**; the chain runs only
  on the fallback script call. The five combined episodes kept coverage
  (72–84 %) but read PART 1 aloud (38–59 % verbatim), so the bridge says
  "PART 2 is not PART 1 with the markdown removed" and asks the script to
  name each section once (chapters had collapsed to four on PT 12/15 and
  MIT 13/16). Strip mode removed 1–3 TRUE sentences a day on
  Planetterrian — X posts and 403 journals — while the fetch stage held
  the text: **claims verify against the fetched copy first**
  (`engine.claims.build_local_texts`, `via: fetched_copy`, metric
  `source_integrity_verified_from_fetched`), HTTP only for a quote the
  copy lacks; the committed sidecar now records `stripped_sentences`
  (it had shown the post-strip ledger as "claims=0, passed"). Not a
  length lever: the under-target week (Tesla 56 %, PT skipped at 858 w)
  is the digest-ceiling class, and the combined path's first flagship
  week is its measurement.
- **Sep 17 2026, same day — main had been red for eleven runs.** The
  merge of that review was the first the operator could not trust CI
  on: the test workflow had failed on every push since Sep 16 (seven
  Voices / co-host assertions pinned code other sessions had moved on
  from; the SpaceX caption replay, the promo-cut sweep and the UC
  runway guard are data-driven and all tripped). The fixes are the
  three commits before the review's follow-up merge (captions HOLD a
  short segment, the YouTube call-out anchors a promo cut, the restock
  falls back off grok-4.6 — each noted in its own section above);
  §6 of the review doc is the record. Two things it adds: **the
  grok-4.6 restock arm was never exercised in the window it was read
  out on** (no queue needed topics Aug 19 – Sep 7; every needed run
  since failed, nine in a row — the register entry carries the
  correction, and the run summary's `model` field says whether the
  fallback is doing all the work), and UC was hand-restocked with three
  documented briefs (the June 2026 precedent) so the alarm clears
  while the automation refills. **Check the `Run Tests` conclusion on
  main before reading a merge as checked.**

### Network prompt + LLM review (July 31, 2026)

Operator-directed all-show prompt pass + model strategy — canonical
writeup: [`docs/reviews/network_review_2026_07_31.md`](docs/reviews/network_review_2026_07_31.md);
ledger: `docs/reviews/ledger/network.yaml` (2026-07-31 entry). Highlights:
**P0 fixed** — the July-30 spoken identity line was deleted network-wide
by run_show's junk-title-header regex (no show said its own name since
the cold-open merge; stripper now exempts "this is"/«вы слушаете»
shapes, guarded in `tests/test_intros.py`). Source-scaffold scrub gained
the outlet-name ("Source: Google News.") and Russian em-dash
(«Источник информации — domain») shapes. Eleven confirmed seeded tics
de-seeded by shape across 10 shows (all ⚠️ A/B — PR #927). `clean_digest`
is now WIRED (operator-approved): podcast-only cleanup + Sunday
weekly-summary segment + duplicate-headline strip reach podcast prompts
for the first time. `vocab_tracker` no-reteach list uncapped + themes
window aligned (PR's 7-8-episode re-teach cycle). env_intel switched to
the digest-side length lever (min_digest_words 950; podcast retry off —
finansy_prosto is now the only sanctioned holdout). **Model strategy:**
digests/fetch stay on grok-4.3 (grok-4.5's confident-hallucination rate
rose 25%→54% — wrong trade for a facts-first network); new
`llm.podcast_model` lets one show A/B grok-4.5 on the script stage only
(empty default = byte-identical; guards pin the digest never follows
it); the scheduled reviewer runs grok-4.5 (`REVIEW_MODEL` env rollback).
dp_pod's Network-pick rotation is enforced data-side (recently picked
shows excluded from the candidate list) after the instruction-only fix
was violated six days straight.

### LLM usage review vs the Aug-2026 xAI product state (Aug 18, 2026)

Canonical writeup:
[`docs/reviews/llm_usage_review_2026_08_18.md`](docs/reviews/llm_usage_review_2026_08_18.md);
drift guards: `tests/test_llm_usage_pass.py`. The review's verdict was
"no model upgrades", but the **operator overrode it the same day and
directed a NETWORK-WIDE upgrade to grok-4.6** (all LLM stages — digest,
fetch, scripts, synth, titles, reviewer, review agent — off grok-4.3;
refusal fallback repointed to grok-4.3; the dp_pod-4.5 / MIT-4.6
`podcast_model` pins removed as superseded/absorbed; ~+$22-25/mo).
**REVERTED the SAME DAY (2026-08-18, operator-directed)** — the trigger
was operational, not editorial: grok-4.6 digest latency ran **5-10×
grok-4.3** on every show measured (planetterrian 44s → 420s, MAB 36s →
242s, dp_pod 55s → 225s) and the four largest digest prompts (tesla,
spacex, omni_view, modern_investing) blew the 300 s request timeout or
were server-disconnected; nested SDK+tenacity retries amplified each
stall into a 41-45 min burn and **7 of 12 scheduled shows failed on day
one**. Everything is back on grok-4.3 (refusal fallback back on
grok-4.20-reasoning; the translation pin deliberately stays grok-4.6 —
it froze what `grok-latest` already served, and its small chunks never
tripped a timeout). Experiment `network-grok-46-upgrade` is closed
(status `done`, outcome REVERTED); grok-4.6's hallucination profile
remains UNMEASURED. **Any future model upgrade follows
[`docs/model_upgrade_playbook.md`](docs/model_upgrade_playbook.md)** —
staged one-show-first rollout with a digest-latency gate — never a
network-wide day-one flip. **The first staged trial started the same
day** (operator-directed; experiment `staged-grok-46-trial`, readout
2026-09-01): grok-4.6 on dp_pod's SCRIPT stage only, first_principles +
unintended_consequences whole-show (narrative — no news fetch), and the
synth + reviewer stages; `NERRA_LLM_TIMEOUT_SECONDS` raised to 600 in
run-show.yml to cover 4.6 latency. **2026-08-27: the FPD + UC whole-show
arms were WITHDRAWN (operator-directed, playbook latency gate)** — on
the GitHub-cron outage day FPD's 4.6 digest calls stalled ~260 s and
server-disconnected on both of its runs and UC died on both of its
runs, so both shows are back on the grok-4.3 network default; the
narrative-length question is unanswered, not answered negative, and a
re-pin needs a fresh staged trial. dp_pod's script arm and the synth +
reviewer stages continue. Every daily NEWS show's digest/fetch
stays grok-4.3 — scope pinned by
`tests/test_llm_usage_pass.py::TestStagedGrok46Trial`. Reviewer
FACTUAL_ERRORS comparisons from 2026-08-18 on must be cross-show under
the same 4.6 reviewer, never against pre-08-18 history (the instrument
changed with the trial).
The review also shipped three silent-number fixes: (1) **search billed per CALL** ($5/1k, env
`XAI_SEARCH_COST_PER_CALL`) — xAI dropped per-source billing and the usage
object's source count, so 100% of credit files since 07-29 recorded $0
tool fees; (2) **episode reviewer pinned `grok-4.3` + effort `none`** —
its configured slug was retired 05-15 and had been silently served by 4.3
at 4.3 billing while costed 6× cheaper; (3) **translation pinned
`grok-4.6`** (env `NERRA_TRANSLATION_MODEL`) — it rode `grok-latest`, so
vendor releases silently changed shipped dub audio; never put a published
stage on a floating alias. Dashboard `cost_rollup` now breaks out
`images` + `search` (41% of tracked spend, previously invisible). Voice:
the TTS request has NO model param — server-side updates arrive
unpinnable, so spot-listen after major xAI voice announcements;
multilingual-voice A/Bs wait until after the language cull (FR decision
08-25). Imagine stays on `grok-imagine-image` $0.02; the $0.05 quality
tier only if gallery-retention data ever demands it.

### Website review (June 10, 2026)

Full public-site review — canonical writeup:
[`docs/website_review_2026_06_10.md`](docs/website_review_2026_06_10.md);
drift guards: `tests/test_website_quality_pass.py`. Implemented (source-only,
propagates via nightly regen): absolute `og:image` default in
`templates/base.html.j2` (the relative default broke share previews on every
page without an explicit `og_image`); `noindex` on the 404 template; footer
Gallery link (287 CC-licensed images were reachable from nowhere);
`MIN_SOCIAL_PROOF_SUBSCRIBERS` 100→50. Deferred with rationale in the doc:
blog-index pagination, hero inline-CSS extraction, homepage gallery rail,
Russian brand-page translations, inline-style cleanup, contrast audit.
Rejected after verification: nav-cover empty alts (correct WCAG — visible
text adjacent), search loading state (already exists), blog next-episode nav
(already exists).

### Website review (September 3, 2026)

Second full public-site pass — canonical writeup:
[`docs/website_review_2026_09_03.md`](docs/website_review_2026_09_03.md);
drift guards: `tests/test_website_review_2026_09_03.py`. Rules that now
bind:

- **The legal/trust pages are TEMPLATES** (`templates/ai_disclosure.html.j2`,
  `privacy_policy.html.j2`, `terms_of_service.html.j2` on the shared
  `_legal_page.html.j2` chrome; `generate_legal_page()` / `--legal`).
  Never hand-edit `ai-disclosure.html` / `privacy-policy.html` /
  `terms-of-service.html` at the root again — they were hand-written
  for five months, drifted off-brand (Inter, no nav/footer, hardcoded
  GA4 id) and off-truth (the AI disclosure claimed every episode was
  personally reviewed before publication and cited a Supreme Court
  ruling that does not exist). The disclosure says plainly that no
  human reads every episode before it ships and describes the
  safeguards instead; keep it that way.
- **`--static-pages` is the one flag for every cheap page** (start-here,
  about, FAQ, how-to-listen, press, contact, editorial, legal, gallery,
  books, 404); nightly runs it. A new static page is added to
  `generate_static_pages()`, or it silently stops refreshing between
  `--all` runs (editorial/press/contact/legal had for months).
- **`<title>` comes from `page_title` OR a `block title`** — base now
  renders both. The MIT performance page shipped `<title></title>` for
  the same reason the Tesla tracker did in August; pass `page_title`
  in every generator regardless.
- **The blog hub renders the newest `NETWORK_BLOG_INDEX_MAX_POSTS`
  (240)** plus an archive-by-show rail; per-show indexes stay complete.
  Do not "restore" the full list — it was 1.7 MB and growing daily.
- **Homepage claims are computed, not typed**: show count, ticker,
  About paragraph, cadence wording ("most shows daily"), Most Played
  (`POPULAR_EPISODES_MAX_PER_SHOW = 2`). The homepage newsletter form
  posts to the account Worker like every other form — the Buttondown
  embed endpoint is gone from the site for good.
- **Navigation contract** (`base.html.j2`): "More" dropdown for
  Mira/Topics/Books/Gallery/Data/Editorial/FAQ/Press/Support (Mira and the
  topics map joined it Sep 19–20 2026 — a fourth dropdown would crowd the bar,
  and `topics/index.html` is the crawlable map that carries all twelve hubs);
  no "Home" item (the
  logo is home); dropdowns capped + keyboard-operable; ONE delegated
  mobile-menu close handler (no inline `onclick` on menu links — the
  homepage override forgot `body.menu-open` and scroll-locked phones);
  `scroll-padding-top` under the sticky nav; footer About column
  inside the 6-child grid. `--nn-accent` / `--nn-text-secondary` are
  defined tokens now.
- **Scaffolded shows need a real `display_order`** in
  `shows/network_meta.yaml` (the five were 99–102 and rendered last,
  Nerra Daily dead last; ties fall back to insertion order, guarded).
- **Mission Control never fabricates a zero** (`fmtOrDash` on the show
  cards) and every top-level read is guarded; a data-age pill is
  visible in all three views; the site footer's "Network Status" lands
  on `?view=sponsor`.

Deferred with rationale in the doc: blog `<h1>`==hook duplication
(needs `**TITLE:**` in 13 digest prompts — A/B), boilerplate Story
Trackers on 10 of 11 shows (`last_major_update_episode` never written),
per-show blog pagination, SSR summaries, stale curated Tesla/SpaceX
series under "Live" badges, MIT alpha framing on Mission Control, and
the remaining hand-written pages (`modern-investing-resources.html`,
`age-of-ai-apply.html`; `ru/index.html` is generated since Oct 18 2026).

### Site + funnel + Mira program (Sep 19–20, 2026)

Operator brief: review the site and the last 30 days, then a plan driven by
analytics, with Nerra Personal's visibility and the Mira shows' novelty as the
priorities. The finding was that the factory is healthy and almost nothing it
makes reaches a person: **134,171 YouTube views in 30 days produced 10
attributed sessions and 1 newsletter signup**, the site saw 243 sessions in 28
days with **26% of measured landing sessions hitting a path with no file**, and
the three most differentiated, cheapest, best-trending and most-visited
properties — Nerra Daily, The Age of AI, Nerra Voices — were the three with no
YouTube, no X, no newsletter and no on-air presence. Plan:
`/root/.claude/plans/` (session artifact); guards
`tests/test_site_funnel_pass_2026_09_19.py`,
`tests/test_mira_pass_2026_09_20.py`. Rules that now bind:

- **`engine/brand.py` owns every claim the network makes about itself**, the
  way `engine/titles.py` owns limits and `engine/funnel.py` owns campaign ids.
  Import `mira_claim_paragraphs()`; render it through the `mira_claim` macro in
  `templates/_macros.html.j2` (fed by the `mira` / `mira_shows` Jinja globals).
  A template that hardcodes the sentence fails CI.
- **The Mira claim is NARROW on purpose, and widening it is the failure mode.**
  It rests on the guest holding the publish decision — *an AI asks the
  questions, and the human guest decides whether the conversation is published
  at all* — because the general shape ("an AI host interviews real people") is
  **not ours to claim**: a prior-art search found platforms doing exactly that,
  at least one since 2024, so the broad version is disprovable in one search on
  the page a journalist reads. The basis must also stay true of BOTH call modes:
  the pre-2026-09-09 basis said Mira "places the call", which is now the
  fallback, and it had already shipped inside `llms.txt`. Guards:
  `TestTheClaimHasOneOwner`.
- **The claim never ships without its basis and its correction invitation.**
  A superlative nobody can challenge is a superlative nobody should believe, and
  the AI-disclosure page is the asset the claim trades on.
- **`strand` groups shows in the chrome** (`shows/network_meta.yaml`;
  `_merge_scaffolded_network_registry` passes it through untouched, so a
  registry-only show needs no Python change). It drives the nav Shows dropdown
  group, the mobile menu, and a badge on the homepage grid card. The FOOTER show
  list stays flat — its mobile accordion targets `.nn-footer-col > a` directly,
  so nesting would stop it collapsing on phones.
- **A show that bypasses `run_show.py` gets none of run_show's publish
  surface.** `newsletter.enabled` and `youtube.enabled` on `age_of_ai` were read
  by NOTHING for months; `pipelines/voices/publish_episode.py` reads them now
  (see the AOAI entry above for the mechanics). This is the third instance of
  the class after the OP3 prefix and the per-language OP3 feeds — when a new
  show skips run_show, wire its distribution explicitly and check the secret
  NAMES (`YOUTUBE_REFRESH_TOKEN_EN`, not `YOUTUBE_REFRESH_TOKEN`).
- **No surface advertises something that does not exist.** A show with no feed
  FILE gets no feed link, no `webFeed` JSON-LD, no `alternate`, no JS fetch and
  no Story Tracker link (`has_feed`, Sep 19 — Nerra Voices' dead feed link was
  on ~1,990 pages, the most-repeated broken link on the site), and its page
  leads with a "Not published yet" band and the apply CTA instead of an empty
  episode rail.
- **An internal link never carries a `utm_*` tag.** GA4 starts a new session on
  any page_view carrying `utm_source`, so an internal UTM inflates the session
  count and overwrites the visitor's real acquisition source. Internal CTAs are
  measured with a GA4 EVENT (`select_personal_upsell`). The blog Story Tracker
  link had been doing exactly this.
- **`site/redirects.yaml` + `scripts/audit_dead_urls.py`** own dead URLs: a
  committed stub (meta-refresh + canonical + `noindex`) per retired path, and a
  nightly loud-but-non-blocking audit against the GA4 landing pages. A redirect
  stub is **not** an episode page — `_blog_url_for_episode` skips
  `redirect_stub_paths()`, because "the file exists" stopped being a proxy for
  "the article exists" the moment stubs appeared at `blog/<slug>/epNNN.html`.
- **`age-of-ai-studio.html` stays out of the sitemap** (a private join link for
  a scheduled interview); both `*-apply.html` forms are now IN it, having been
  the unfindable acquisition surface for the network's most differentiated
  shows. Each interview show links its OWN form (registry `apply_page`) —
  the Worker files an application against whichever form posted it.

**Sep 20 2026 — `/topics/` hubs: `engine/topic_hubs.py` owns the subject
vocabulary.** The site had 1,952 sitemap URLs and 20 organic sessions in 28
days because 1,880 of those URLs are DATED news articles — the right shape on
the day, useless as a landing page three weeks later. Twelve evergreen hubs
(`topics/<id>.html` + `topics/index.html`, `generate_topic_hub_pages`) answer
the durable query instead. Rules that bind:

- **The vocabulary is CURATED (`picker_tags.topics` from the registry), never
  the search index's auto-mined `topics`** — those put `regulation` on 1,708 of
  1,886 episodes (91%) and `finance` on 1,263, so a hub named for one is a
  keyword artifact. Adding a show to a hub is a registry edit, not a code edit.
- **Episode lists read the COMMITTED `site/data/search-index.json`, never
  `data/content_lake.db`** (gitignored, rebuilt from the repo). A generator on
  the lake would render empty hubs on any checkout that had not backfilled —
  exactly how the public search index shipped zero episodes ~13×/day until July
  2026. A missing or empty index writes **no pages at all**.
- **Every intro is hand-written.** A hub whose prose is assembled from its own
  episode titles is thin content, which ranks worse than no page.
- **A hub under `MIN_EPISODES_FOR_HUB` (12) is not built**, is not in the
  sitemap, and is never linked from a post. `interviews` and `sailing` sit
  below it today and name the page that already serves the subject
  (`/mira.html`, the Offshore North dashboard); they turn themselves on when the
  archive grows. The sitemap lists hubs from `renderable_hubs`, never a glob,
  so a skipped hub can never be advertised as a page that exists.
- **Every blog post links its subjects** (`topic_hubs` in the post context).
  That link is why the hubs can rank; without it they are orphans reachable
  only from the nav. Committed posts pick it up on their next per-show regen,
  per the Sep 3 source-only convention.
- `topics/*.html` is in nightly's add-paths, and the blog `<title>` lead now
  reads `engine.titles.WEB_TITLE_LEAD_MAX` instead of a literal 62. Per-episode
  blog titles were ALREADY shipped (the Sep 3 deferred item) — 25/25 distinct
  on Tesla; `TestTitleLimitHasOneOwner` pins both.

**Sep 21 2026 — the capture end of the funnel, and why three audits blamed the
wrong function.** Phase 1 made clicks traceable (4 parseable campaigns,
`attribution_coverage_pct` 3.5%) while capture stayed dark: 5 subscribers,
`tag_counts: {}`, `by_source: {}`. `resolveSubscribeTags` was NOT the bug — it
always put tags in the request body. Guards:
`tests/test_capture_measurement_2026_09_21.py`; experiment
`capture-measurement-2026-09-21` (readout 2026-10-21). What binds now:

- **A capture tag is applied on create AND on a duplicate.** The Worker's
  duplicate branch returned `{ok:true, alreadySubscribed:true}` and stopped, so
  tagging was CREATE-only: an address already in Buttondown when the tagged path
  shipped could never acquire `nerra-member`, a show tag or a `src-*` source,
  however many times they resubmitted. `buttondown.ts` now merges via
  `PATCH /v1/subscribers/{id}`. **The merge is a UNION, never a replace** —
  PATCH overwrites the tag array, so sending only the wanted tags would strip a
  member's show subscriptions on their next footer signup, a data loss shaped
  exactly like a working signup. Every merge failure still reports the subscribe
  as successful: an attribution tag is not worth a 502 on someone's signup.
- **A signup form that sends no `source` makes `capture.by_source` structurally
  impossible.** None of the three first-party forms sent one
  (`base.html.j2`, `join_page.html.j2`, `network_page.html.j2`) — only the RU
  lander did — while the Worker accepted the whole allow-list. **The guard is why
  it survived:** it asserted the Worker *accepts* every `engine.funnel` source
  tag and never that a page *emits* one. Guard both ends. The tag renders from
  the `capture_source_site` Jinja global fed by `engine.funnel`, never a literal.
- **"A result key is not a metric" — fourth instance.**
  `select_personal_upsell` had fired from the network's only on-site upsell
  since 2026-09-19 and was read by nothing, because
  `fetch_ga4_stats.py` filtered events to an inline two-name list. Now
  `CONVERSION_EVENTS` / `ENGAGEMENT_EVENTS` are named constants and the
  engagement events are a **SEPARATE report**: `build_funnel._captures()` sums
  every row of the conversions report into `signup_events_total`, so an
  engagement event in that list would report an intention as a subscriber.
  Add the event to the constant when you add the `gtag` call.
- **`api/member_metrics.json` counts paid members, and carries no PII.** The
  admin endpoint returns `first_name` and `city`; at five members that names a
  person, in a file committed to a public repo. `build_member_metrics.py` writes
  integers and show histograms only, never a name, city, email or feed token —
  PII-light by construction, like `build_personal_feeds.py`. `free_accounts`,
  `mrr_usd` and `trialing` are **null**: the endpoint lists only active PAID
  records, and nothing in this repo reads Stripe. A run with no
  `PERSONAL_ADMIN_TOKEN` leaves real counts alone rather than overwriting them
  with nulls.
- **Reading `/tags` cannot tell "no tags" from "tags without counts".**
  `fetch_tag_counts` skipped any row lacking an integer `subscriber_count`
  silently, so both produced an empty dict while the warning asserted the first.
  The repo's other client of that endpoint reads only `name` and `id`, so the
  count field is not a safe assumption. It now says INCOMPLETE when rows were
  skipped, and the warning names the read-only way to settle it: dispatch
  `buttondown-tag-subscriber.yml` in **`list-all`** mode, which prints each
  subscriber's real tags. That script can only write tags drawn from show YAMLs,
  so it cannot backfill `nerra-member` or any `src-*`.
- **Blog cross-show recommendations are seeded per POST**
  (`generate_html.py` `_pick_cross_show_related(seed=…)`, CRC32-of-stem as in
  `engine/video.py`). Unseeded, every regen rewrote all ~200 of a show's posts
  with fresh random picks, so no refactor could be proven output-neutral.
  Seeding by slug would give every episode the identical three. It makes a
  re-run with the same candidate pool byte-identical; it does not freeze the
  picks, since the pool moves as the network publishes.
- The three Python Buttondown clients now agree on `api.buttondown.com/v1`. The
  Worker still writes to `api.buttondown.email/v1`; both hosts are live and that
  write path is deliberately left alone rather than flipped without a key to
  verify against.
- **The Worker's vitest suite is not run by any workflow** — `test.yml` runs
  ruff, actionlint and pytest only. Worker behaviour is guarded from CI by
  reading the TypeScript as text from Python, which is why the guards above
  assert on source strings; run `npx vitest` by hand when you change
  `workers/`.

**Sep 21 2026 — the promo rotation: `mira` + `topics` added, gallery 3 → 2**
(operator-directed; ⚠️ AUDIO — A/B-listen per landmine #17). The two newest
properties were advertised nowhere on air: no `NETWORK_SURFACES` entry existed
for `/mira.html` (the network's sharpest and most contestable claim) or the
`/topics/` hubs (its whole search surface), while the free image gallery held
**3 of 12** slots — a quarter of every spoken outro, X reply and YouTube
description. Pool 12 → 13. Guards:
`tests/test_rotation_pass_2026_09_21.py`; experiment
`promo-rotation-mira-topics-2026-09-21` (readout 2026-10-21). What binds:

- **A surface's `spoken` line is PROMPT TEXT, not deterministic insertion.**
  `build_network_promo` concatenates it into `pod_vars["closing_block"]`
  (`engine/pipeline.py:628-638`), which renders into each show's LLM prompt under
  "Use this exact closing (do not rewrite it)". Nothing verifies it afterwards
  and the model HAS dropped part of it (`engine/daily_edition.py:448-452`, MIT
  Ep171 kept only one sentence of frame 2). So de-seed-by-shape applies here as
  it does to any prompt: a line written loosely is aired loosely, and
  `test_no_surface_supplies_a_quotable_specimen_sentence` bans a quoted specimen
  inside the copy.
- **The on-air Mira line carries the NARROW claim and no superlative.** A
  superlative needs its basis and its correction invitation beside it — the
  `/mira.html` contract — and a spoken outro can carry neither, so it carries
  neither. The line names the term that is actually ours (the guest decides
  whether the conversation is published) and discloses that the host is an AI.
- **Pool length must stay coprime with the offset stride of 3.**
  `pick_featured_surface` offsets each show by `ENGLISH_ORDER.index(slug) * 3`,
  so at pool length 12 the thirteen English shows collapsed into **four** phase
  classes — on 2026-09-22 four of them plugged Nerra Daily, three the gallery,
  three Story Trackers, three Start Here. At 13 they land on thirteen distinct
  slots (12 distinct surfaces; gallery holds two). Nothing about a weight edit
  announces that it has re-collapsed the rotation, so it is pinned
  (`TestSameDayShowsDoNotEchoEachOther`).
- `weight` is a **string** in a `dict[str, str]` list; gallery's reduction keeps
  it above every peer 2:1 and still non-consecutive (slots 6 and 7 apart).
  A new entry needs **no** funnel change — `network_promo.py:349` already routes
  through `engine.funnel.network_link`, which puts the surface `id` in the
  campaign's variant slot.
- **The YouTube description's surface line was the last untagged funnel
  link** — `engine/video_metadata.py` hand-built `https://nerranetwork.com/{url}`
  and picked the surface from the RENDER date. Both fixed 2026-09-21 (it goes
  through `engine.funnel.network_link` with the surface id in the variant slot,
  keyed on the episode date); an earlier version of this note said "not fixed
  here" and was stale by the time it was read on 2026-09-24.

**Sep 21 2026 — the registry grew a second owner for three things, and one
"dead" key was read raw.** Consolidation pass (C1), whose whole acceptance was
a byte-identical `--all`: 1,921 blog posts, 60 root pages, 13 topic hubs, the
four RU pages and `sitemap.xml` all unchanged, with the only 39 differing files
(`api/*.json`, `blog*.rss`) differing solely in their generation timestamps.
Guards: `tests/test_registry_pass_2026_09_21.py`. What binds now:

- **`engine/show_lang.py` owns a show's page language.** The Russian pair was a
  literal tuple repeated SEVEN times — three in `generate_html.py` (summaries
  page, show page, `_count_languages`) and four in `engine/blog.py` (JSON-LD
  `inLanguage`, `_is_ru`, the next-episode placeholder, `page_lang`) — so a
  registry-only show **could not be Russian at all**, and a missed copy renders
  a page in the wrong language with nothing failing. The language is DERIVED
  from `shows/<slug>.yaml`'s `tts.language_code` (the field the operator
  already maintains, the `_newsletter_tag_for_slug` pattern), with an optional
  `page_lang` in `network_meta.yaml` checked first for registry-only shows that
  have no YAML. Verified before it was written: across all 18 shows it returns
  `ru` for exactly `finansy_prosto` and `privet_russian`.
- **`picker_tags` is an ordinary registry key**, not a parallel
  `_SHOW_PICKER_TAGS` dict only the YAML path could write to (a hardcoded show
  could not declare tags, and the tags decide `/topics/` hub membership). The
  twelve blocks were moved programmatically and checked by equality against a
  saved copy, because the failure mode is a transcription slip that empties a
  hub while the page still renders and validates. The hub snapshot guard pins
  hub id → slug SET; a count would pass through exactly that loss.
- **The scaffolded merge is per-key** (`_merge_show_meta`, curated Python value
  wins). It is a **no-op today** — the two sources are disjoint, twelve slugs in
  Python and six in YAML — which is precisely why the footgun went unnoticed:
  `if slug not in NETWORK_SHOWS` silently discarded a YAML entry's thirty-odd
  keys the first time anyone scaffolded over a hardcoded show.
- **`newsletter_tag` in the registry looks dead in one context and is read raw
  in another.** This pass deleted it and nearly shipped that.
  `_newsletter_tag_for_slug` resolves the tag from the show YAML for the
  summaries/show-page context, so `_build_all_shows_list()` shows every show
  correctly tagged with the registry key gone — which reads as proof it is
  unused. The blog path renders from the RAW entry (`generate_blog_posts` does
  `cfg = NETWORK_SHOWS[slug]`; `engine.blog` reads
  `show_config.get("newsletter_tag") or show_config["name"]`), so removing it
  fell back to the Cyrillic display NAME and put a tag Buttondown refuses on
  ~150 Russian blog posts. **Before deleting a registry key, check the raw-entry
  readers as well as the built context** — the full-tree diff is what caught
  this, not the tests.

**Sep 22 2026 — one card to hear it and read it, and a transcript that is not
the page.** Every show has a blog now, including the interviews, and no show
page said so where a visitor looks: the Latest Episode card was a player, a
summary at `display:none`, and no route to the article — which sat four
screens down under "Latest from the Blog". Guards:
`tests/test_episode_card_transcript_2026_09_22.py`; experiment
`episode-card-and-transcript-box-2026-09-22`. What binds:

- **A transcript is collapsed, never withheld, and never the page.** An
  interview digest is 90% transcript (730 of Ep006's 785 lines) and it was
  printed OPEN in the article body, with the chapter list stranded on top of
  it. `engine.interviews.interview_transcript_markdown` pulls it out and
  `interview_body_markdown` stops printing it; **it is the ONLY transcript
  those episodes have** — the Voices pipeline bypasses `run_show`, so there is
  no `*_reader.txt` beside the digest and `transcript` had been empty, which
  is why an interview post carried no transcript box, no `#transcript` anchor
  and no JSON-LD `transcript` at all. The box now previews itself
  (`engine.blog.transcript_preview`, a LITERAL prefix cut at a sentence end —
  the interview module forbids reformatting the guest's approved words, and
  that applies to an excerpt of them) and says its word count. The full text
  stays in the HTML: a box that fetched its contents would cost the in-page
  search a reader uses to find a quote, and every crawler's view of what the
  episode said. **The preview lives inside `<summary>`** because a child of a
  closed `<details>` is hidden by the UA and author CSS cannot reliably bring
  it back; it carries `aria-hidden` since the same words are read again three
  lines below and a 400-character button label is not a button label.
- **The combined card renders from the same JSON the script fetches**
  (`engine.summaries_ssr`), so the script's render is an UPDATE, not a
  different card replacing "Loading...". Both cut the summary at
  `CARD_PREVIEW_CHARS`, interpolated into the script from the module — a
  second literal is how the card flickers into different words a moment after
  paint. **The article link is resolved at build time** through
  `_blog_url_for_episode`, which knows a redirect stub is not an article; when
  the feed has moved past the episode the page was built from, the script
  HIDES the link (`data-episode`) rather than deriving a URL it cannot vouch
  for. A show with no feed renders no card — Nerra Voices had a permanent
  "Loading..." above its own "Not published yet" band.
- **The bespoke DP Pod page needs every generic-template change made twice.**
  `show_page_dp_pod.html.j2` does not use `show_page.html.j2`, which is the
  same gap that left its Story Tracker unlinked for two months; it got the
  card in its own idiom.
- **The summary preview leads with the HOOK.** Four shows' cards opened on
  their own emoji branding line and Tesla's opened on a stock quote, because
  the walk started at line one and the "is this a sentence" test searched for
  a full stop ANYWHERE — and `(3.8%)` contains one. A hook is the episode's
  own headline, so everything above it is preamble by definition; the
  terminal-punctuation test now reads the END of the line. The walk exists
  twice, in `engine.summaries_ssr.plain_preview` and in the page script:
  change both or neither.
- **14 more stale "daily" claims**, on three Monday-only shows. The 09-21
  guard read `schedule` and `rss_description`; it did not reach the DP Pod
  page's own prose (8), its registry `meta_description`/`about_text` and
  Offshore North's `related_reason` (3), or env_intel's and Финансы Просто's
  descriptions (6, including the Russian «ежедневный»). The guard now sweeps
  every public string field for every Monday show, stripping show NAMES first
  so "SpaceX Daily" is not a false positive.

**Sep 22 2026 — The Age of AI: the pages say only what the record supports,
and a publish that renders the page before the post.** Guards:
`tests/test_age_of_ai_truth_2026_09_22.py`; register
`age-of-ai-truth-pass-2026-09-22`. What binds:

- **`generate_html.py --show <slug> --blogs` writes the POSTS first.** Every
  article link on a show page is a file-exists check (`_blog_url_for_episode`),
  and the Nerra Voices publisher writes only the digest `.md` and then calls
  exactly that command — so the page rendered with no link to the episode it
  had just published, every publish (Ep6 and Ep7 both), repaired only by the
  nightly. run_show never hit it because it writes the post HTML itself. The
  guard runs the real `main()` with recorders and asserts the call ORDER.
- **A chapter list is shown only when the transcript vouches for it**
  (`engine.interviews.supported_chapters`, the same shape as the claims
  gate). Ep5–7 shipped chapter lists about a film studio banning AI
  storyboards — for a network-automation builder, a propulsion founder and a
  novelist — because `02_chapter_markers.txt` supplied that exact title as
  its example and the model reproduced it (de-seed by shape applies to the
  Voices editorial passes too; the specimen is gone). Calibrated on all seven
  episodes: the real lists (Ep2–4) pass every title, the fabricated ones pass
  at most one in six; the guest's name and "ai" vouch for nothing on this
  show. The three lists were REMOVED from the committed digests and
  summaries; the Supabase `editorial_packages.chapter_markers` rows still
  hold them, and there is no chapters-only re-run yet (operator item).
- **Run time comes from the feed's `itunes:duration`, never from chapters.**
  `_run_time` used to read the last chapter's `end`, so it was wrong on
  EVERY episode, not only the fabricated ones — Ep2 "23 min" beside a player
  reading 44:52. `feed_durations(rss_path)` is threaded through both the
  show-page cards and the post context.
- **The co-host is read from the transcript, in both directions.** The
  credit said Patrick "is not in the room while Mira is talking to a guest";
  he co-hosted five of the first seven episodes (every one but Ep4 — Ep6
  labels him `PATRICK:` in capitals, which is how a case-sensitive count once
  read it as zero). `cohost_label` reports a label with ≥ 5 lines that is
  neither Mira nor the guest; the show page and the post say "with Patrick
  Novak" on exactly those episodes. The credit now states the arrangement in
  Mira's own prompt: she conducts every interview, he joins as co-host when a
  guest has asked for him, he never answers for the guest afterwards. The
  old guard PINNED the false sentence; the new one checks the copy against
  the committed transcripts. A guard that pins a claim is only as good as
  the claim.
- **Gate 2 is described as built.** `MIRA_FIRST_CLAIM_BASIS`, the interview
  steps, `about.html.j2` and the topic-hub copy all said nothing publishes
  "until the guest has approved it"; `gate2Housekeeping` auto-approves after
  seven days of silence (operator-confirmed to keep the timer, 2026-09-22).
  The copy now says: a week to approve, cut from or refuse the transcript;
  cuts removed from the audio, not bleeped; takedown available afterwards.
  The narrow claim (the guest holds the final say) survives on those terms.
  The guard reads `workers/voices/src/index.ts` for the auto-approve and
  fails any surface that claims the stronger gate while it exists.
- Every blog post on the site printed `\ud83d\udc4d` where a thumbs-up
  belonged — JSON escapes pasted into `blog_post.html.j2`. A guard sweeps
  every template for surrogate escapes.

**Sep 22 2026, later — the finishing pass on the same pages** (guards
`tests/test_age_of_ai_finish_2026_09_22.py`; register
`age-of-ai-finish-pass-2026-09-22`). What binds:

- **`engine/brand.py` owns the interview steps** (`MIRA_INTERVIEW_STEPS`,
  `MIRA_INTERVIEW_STEPS_COMPACT`); `generate_html.MIRA_INTERVIEW_STEPS` is
  the same object re-exported. The `mira_steps_list` macro renders them from
  the `mira_steps` / `mira_steps_compact` globals — all eight on `mira.html`,
  the five a prospective guest asks about on a show page that has an
  `apply_page` (Nerra Daily is `strand: mira` and takes no guests, so it
  shows none). A template that types a step title fails CI. Step 7 states
  the seven-day auto-approve; it is not hidden in the short form.
- **A Spotify id in the show YAML is a Spotify chip** (`_spotify_url_for`,
  the `_apple_links_for` rule: registry string wins, the id fills the gap).
  Six shows had the id and `spotify_url: null` and rendered no chip.
- **Interview posts carry a one-line provenance** from
  `brand.interview_provenance(guest, cohost)`: hosted by an AI, who
  co-hosted (from the transcript), reviewed by Patrick, transcript SENT to
  the guest to approve, cut or refuse — never "approved by", because
  silence also publishes. The scoped `creator_credit` renders on the post
  as it does on the show page; the chapter list left the digest body for
  the page's real `blog-chapters` section (the seek script falls back to
  `.nn-iv-player audio`; the `nn-i18n-audio` literal a guard pins is kept);
  the breadcrumb and both JSON-LD blocks name the guest (`about` Person).
- **Interview index cards lead with the person** (`interview_cards` keyed
  by episode into `generate_blog_index_html`; a news index is byte-identical).
- **`.nn-guest-*`, `.nn-creator-*` and `.mira-steps` live in `styles/main.css`**
  — each is rendered on more than one page now.
- **News surfaces changed in CSS text and whitespace only**, verified by
  rendering Tesla, Omni View and Offshore North before and after. That is
  an intended, reviewed diff, not a byte-identical one: the
  `.nav-next-placeholder` fix applies to every show's latest post.
- Pre-existing, left alone: `generate_blog_index` logs "Unrecognized
  summaries shape" for `age_of_ai` — `engine.summaries_io` does not read the
  Voices `{"episodes": [...]}` wrapper. It was on main before this pass.

**Sep 21 2026 — chrome that scales, and a way to browse (C2).** The footer
repeated the show list three times on every one of ~2,100 pages and `/explore.html`
did not exist. Guards: `tests/test_chrome_pass_2026_09_21.py`; experiment
`explore-and-footer-scale-2026-09-21`. What binds:

- **The accordion hides `.nn-footer-col > a` AND `> ul`** — so a grouped list is
  collapse-safe and the Sep 20 note here ("nesting would stop it collapsing") was
  incomplete. The real trap is a direct child of any OTHER kind: a group label
  written as a heading stays visible on a phone above a column whose links have
  all collapsed away. Labels therefore live INSIDE the `<ul>`. Both guards were
  mutation-tested by hoisting the label out.
- **A source-reading guard must strip Jinja comments first.** The corrected
  footer guard passed under that mutation because `before.rfind("<ul")` matched
  the *comment* explaining the rule. A test that reads source as text can be
  satisfied by prose describing the thing it checks — strip `{# … #}`, or assert
  on rendered output.
- **A chrome guard renders its own page; it never reads a committed one.**
  Generated HTML is refreshed by the pipeline, not committed from a working tree,
  so on any checkout the committed `index.html` still carries the PREVIOUS
  chrome. Two guards failed that way and a third passed vacuously before they
  rendered into `tmp_path` (the `output_dir=` idiom `test_topic_hubs` already
  used).
- **`show_groups` is the one strand grouping**, computed once in `base.html.j2`
  and used by the desktop Shows dropdown, the mobile menu, the footer and the
  Blog dropdown. It carries the translation KEY, not the label, so each surface
  names the ungrouped fallback itself. Four copies of a `selectattr` pair is how
  the footer drifts from the nav.
- **Footer: 53 show-derived links per page → 20.** The 18 per-show blog links
  became the hub plus the topics map; the 17 per-show RSS links became one link to
  `how-to-listen.html#feeds`, which **already listed every feed** including the
  per-language ones, `has_feed`-gated — so this was one `id` attribute, not a new
  page. `modern-investing-resources.html` keeps its old footer: it is one of the
  three hand-written pages and no template reaches it.
- **`/explore.html` filters on the CURATED vocabulary** —
  `engine.topic_hubs.TOPIC_HUBS`, not the union of registry `picker_tags.topics`
  (42 values, 28 singletons, both `tech` and `technology`). A hub below the page
  threshold still filters, because a chip is not a link. Audience is not a facet.
  The grid is server-rendered and the chips only add `.is-dimmed`, so with
  JavaScript off the page is the whole catalogue.
- **The show card is one macro** (`_macros.html.j2` `show_card`), used by the
  homepage and by explore. The homepage's rendered card changed in whitespace
  only (verified by normalised comparison); `.show-card-wrap.is-dimmed` and
  `.show-card-audience` moved from the homepage's inline `<style>` to
  `styles/main.css`, since a rule only one of two pages carries is a rendering
  bug waiting to happen. `.nn-section-header h1` is styled now as well as `h2`.

### Website review (October 7, 2026)

Full render audit (58 pages at 1440 and 390 px) + five reviews + five
implementation passes — write-up
[`docs/website_review_2026_10_07.md`](docs/website_review_2026_10_07.md);
register `website-review-2026-10-07`; guards
`tests/test_site_review_2026_10_07_{chrome,blog,trust,dashboards,gallery_player}.py`.
Rules that bind:

- **`styles/main.css` has a brace-balance guard.** One stray `}` closed the
  phone media query early: the phone layout applied at every width and the
  tablet block (hamburger) was dropped, site-wide, for weeks.
- **A brand colour is never TEXT on the dark surfaces.** Use
  `var(--show-color-text)` / `var(--card-accent-text)` (derived on every
  element in main.css) or `var(--nn-purple-text)`; raw `--show-color`,
  `--card-accent` and `--nn-purple` are for fills, borders and tints. The
  guard fails a raw text use.
- **Prose links are visible** (`main :where(p, li, dd, td) > a` with no class
  or style): style a component's links with a class and it wins.
- **Every blog post with audio has a player** (`engine.blog.episode_audio_url`:
  summaries record, then the feed enclosure, OP3 kept), the headline is
  stated once, the body outline runs h2 → h3, and the provenance line wraps
  (it was a `nowrap` run that made every post wider than a phone).
- **The guest's terms are stated as built, everywhere a guest or reader sees
  them** (site, apply pages, interview posts, the producer's reply facts,
  booking emails, the Voices Worker pages): a week to approve, cut or
  refuse; then it publishes; takedown after. Never "nothing publishes until
  you approve".
- **Gallery and player data are slim indexes**
  (`site/data/gallery/*.index.json`, `--indexes-only` rebuilds them offline;
  the player embeds a compact OP3 index). A per-show gallery never falls
  back to the 22 MB manifest, and a show with no images mounts none.
- **Mission Control's sponsor/investor numbers come from the same honest
  sources as the tiles** (week-over-week from `audience_headline`, episodes
  from RSS pubDates, untracked spend `None`).

### The site's languages: an English front page, one hub per language (Oct 18 2026)

Operator: the English landing page carried the two Russian shows and their
headlines; other-language content belongs behind the header's language
selector or on dedicated pages. Guards `tests/test_site_languages_2026_10_18.py`.
Rules that bind: **`engine/show_lang.py` owns the SITE LANGUAGES**
(`site_languages()` — English plus every language a show renders its pages in
or produces an audio track in, derived from the show YAMLs; `es` and `zh` have
neither today and get no row), `language_hub_path()` (`<lang>/index.html`) and
`track_languages()` (the one reading of `multilingual.languages` with the ZH
approval rule — `generate_html._producing_track_languages` and
`_listening_languages` delegate to it). **The English homepage reads English
shows only** (`_english_shows`; stories, grid, picker, Organization JSON-LD),
while the free-show COUNT stays network-wide (`_public_show_count_cached`, 26).
**The chrome lists the shows of the PAGE's language** (`chrome_shows` in
`base.html.j2`, from each show dict's `page_lang`; a language with no native
show falls back to the English list) and links the other languages' hubs from
the header's one Language menu (Site links + the June 2026 episode-audio
radios, both from `site_languages`), the footer and the mobile menu; the footer
newsletter picker offers the chrome's shows. **`<lang>/index.html` is generated
for every non-English site language** (`generate_language_hub_pages`, template
`language_hub.html.j2`, in `--static-pages` and `--all`, both hubs in nightly's
add-paths): `ru/index.html` is no longer hand-written (the Sep 3 "three
hand-written pages" are two now), `fr/index.html` is new — seven shows produce a
French track and @NerraFR had no page on the site. A hub lists the language's
native shows (latest episode), the English shows with a live `<lang>` feed
(`_collect_language_feeds(..., slug)` — the 45-day freshness gate applies), the
RU landers and the language's YouTube channel; **every reader string is
hand-written in `_LANGUAGE_HUB_COPY`** and a language with no copy gets no
page and a `::warning::`. The homepage and every hub emit the SAME hreflang
group (`_site_hreflang_alternates`, en / fr / ru / x-default on canonical URLs;
the EN↔RU show-pair helper is unchanged) and the sitemap lists hubs from the
same vocabulary. The chrome's translation dict is still EN/RU only: the French
hub's body is French and its chrome English (a `fr` dict is the next step if
the hub earns traffic).

**Oct 19 2026 — the hubs are front pages.** Operator: the Russian and French
pages should be the equivalent of the English landing page, tailored to those
audiences. `ru/index.html` and `fr/index.html` now render the English
homepage's news-front layout — **the same stylesheet** (`_landing_styles.html.j2`,
extracted from `network_page.html.j2`; the English render is byte-identical)
and **the same assembler** (`engine.landing_test.assemble`) — over the
stories that exist in the language (`engine/language_front.py`): a native
show's episodes as the English page would run them, and for each English show
with a translated track, every episode that has one — the headline is the
TRANSLATED title/description the multilingual stage wrote beside the track
(`translated_hook`: the description's first complete sentence, since the feed
title is clipped to 100 characters), the audio is the translated MP3, the
picture is the episode's own scene matched on the English hook, the article
link is the English post (which carries the language switcher), and "Also in
this episode" is empty because those headlines exist only in English. Up to
`STORIES_PER_SHOW` (3) episodes a show so a seven-show page has a lead, top
stories and sections; the flagship band keeps one card per flagship. Dates,
the masthead and the subject headings are written in the language
(`MONTHS` / `WEEKDAYS`; `section_headings` in `_LANGUAGE_HUB_COPY`), the
English topic hubs are never linked, and `engine.brand.NETWORK_TAGLINE_FR`
joins the RU tagline. A guard strips the headlines and asserts the Russian
page's own copy carries no English word. Guards:
`TestLanguageFrontPages` in `tests/test_site_languages_2026_10_18.py`.

### The media kit (Oct 21 2026)

A publicist pitching a Nerra Voices guest asked Mira for a media kit; the press
page had no audience numbers, two hand-typed guest names, a dead language and
one logo. **`press.html` is the media kit** (`media-kit.html` forwards to it)
and is generated by `generate_press_page` from committed data on every
`--static-pages` run: OP3 downloads and YouTube channels from
`api/audience_headline.json` / `api/youtube_stats.json` (a dash, never 0, when
unmeasured; YouTube age bands only, never gender, which small-cell suppression
turns into an artifact), the claims totals from `_claims_network_ledger` (the
numbers `claims.html` prints), the interview shows' guests from their
summaries, where an interview goes from each show YAML's `youtube` /
`newsletter` flags (a flag that is off is never promised), and booking links
from `pipelines.voices.shows` (the ones Mira sends). **`engine.brand` owns the
copy**: `FOUNDERS` (facts from the DP Pod registry line and Patrick's Age of AI
Ep001, nothing else), `network_boilerplate()`, `PRESS_EMAIL` (=
`CONTACT_EMAIL`; `press@` was never confirmed to deliver). **Brand files:**
the wordmark SVGs set words in DM Sans, so `scripts/render_logo_pngs.js` renders
a PNG beside each (re-run it when a logo changes) and the kit previews the PNG;
`build_media_kit_zip` writes `assets/press/nerra-network-brand-assets.zip`
byte-identical while the files are. The horizontal and stacked logos had cut
off their own wordmark (600 / 0..380 frames for artwork reaching 611.8 /
-23..406) since the brand refresh; frames widened in both copies and in
`brand-refresh-2026/build_assets.py`. Guards `tests/test_media_kit_2026_10_21.py`.
**Same day, operator follow-up — growth, the landing message, and a marketing
kit.** The hero, the boilerplate and every copy-ready post lead with the
landing page's words, which `engine.brand.network_promise_visitor()` now owns
(the `network_promise` Jinja global and the homepage share alt call it).
**Growth** (`_media_kit_growth`): podcast downloads per COMPLETE OP3 week from
`api/op3_history.json` (a week is complete when it ended on or before the
file's `updated_at`), YouTube subscribers from the nightly channel snapshots
carried forward per channel, YouTube views from the Analytics `day_series`,
followers wherever a platform reports them (Spotify, Apple ratings, the
newsletter; X and podcast-app subscribers are a dash). A rate needs a
denominator of `MEDIA_KIT_RATE_FLOOR` (30): @NerraFR's 2 → 26 is never
"+1,200%". The two bar charts are inline SVG from `_bar_chart_svg`, one hue,
a hover title per bar and a table view. **What's next** is
`engine.brand.GROWTH_NEXT`, stated as work that exists or is under way, never a
forecast, with its counts filled from the data (`{video_words}` is spelled out
so it never reads as a second show count — the free-count guard). **Share
Nerra** (`_media_kit_marketing`): every public show's 3000² cover and 1200×630
share card, six page cards, links and handles, the Apple badge,
`brand.marketing_posts()` and `brand.BRAND_USAGE`; a file is listed only when
it exists. **`assets/site_screens/` is not offered**: those captures predate
the Oct 18 homepage and still show the retired "ad-free / 0 ads" hero; they
feed the video outro card until Actions "Capture Site Screenshots" refreshes
them.

### The advertising and sponsorship kit (Oct 21 2026)

Operator-directed: a kit beside the media kit, in its voice and from its
numbers, priced to start high and tastefully; then the two kits in the mail
guests and publicists get. Guards `tests/test_sponsor_kit_2026_10_21.py`.
Rules that bind: **`sponsor.html` is the kit** (`advertise.html` and
`sponsorship-kit.html` forward), generated by `generate_sponsor_page` with the
media kit's growth charts and the landing page's tagline and promise; the two
kits share `templates/_kit_styles.html.j2`. **`engine.brand` owns the rate
card** (`SPONSOR_PACKAGES`: flat monthly USD, founding partner $5,000 with a
three-month minimum and the rate held twelve months for the first
`SPONSOR_FOUNDING_PLACES`; SpaceX Daily, Tesla Shorts Time, Nerra Daily, three
subject packages, any other free show from $500), the terms, the booking steps
and the reasons; a template that types a price, a package or a term fails CI.
The rates are the operator's: change them in brand and the page, the
producer's drafts and the guest mail follow. **Each package prints its
MEASURED reach** (30-day downloads and YouTube views of its shows from
`api/audience_headline.json`, "n of m measured" when OP3 has not indexed one,
a dash never 0) and never a forecast. **Only free shows are for sale**: the
interview shows carry no sponsor (a policy rule now, "Never on an
interview"). **Guest mail carries the kits**: Mira's producer facts list
`brand.MEDIA_KIT_URL` and `brand.SPONSOR_KIT_URL` (and the link guard allows
them; the audience question is answered with the media kit, never a number
she types), the publicist follow-up prompt does the same (it used to say the
network publishes no numbers), and the publish-day note ends with one
paragraph offering both. **A would-be advertiser is `sponsor_inquiry`**: held
for Patrick like any commercial mail, with Mira's reply pointing at both kits
(and naming Patrick as the one who handles sponsorship) waiting in the held
drafts (`producer_sponsor_reply.j2`); nothing about rates is ever sent
automatically. The about and contact pages no longer
say the network takes no sponsorships. **When the network began
(operator):** the Nerra Network name was established in February and March
2026 and measurement, marketing and the channels began in June 2026;
`engine.brand.NETWORK_FOUNDING_DATE` / `network_history_note()` own that, both
kits print the note beside the growth figures, and no surface dates the
network to 2024 (guarded). Not changed: Mira's live prompt still
says the network carries information "free of advertising" (a room change
needs a rehearsal PASS and an operator listen).

### The front page and the share cards (Oct 18 2026)

Operator-directed: the landing test becomes the homepage, a news site's front
page; every shared link gets a proper preview. Guards
`tests/test_homepage_landing_2026_10_18.py`, `tests/test_share_cards_2026_10_18.py`;
docs `docs/landing_test.md` ("v3 — the homepage"). Rules that bind:

- **`index.html` is the front page** (`generate_network_page`, template
  `network_page.html.j2` — the old homepage template is gone; `--homepage`
  writes index.html only, and the finalize job and the Nerra Daily build run
  it so the page follows the day). `landing-test.html` is a redirect stub.
  **`engine/newsroom.py` owns the news behaviour**: story times from the
  summary record's `datetime` in Eastern time (the feed pubDate is a fixed
  08:00 UTC), the markets strip (a value older than 3 days or a passed launch
  is not shown), the newest corrections, Today on Nerra from the schedule
  constants, and **developing stories** — two headlines are one thread at ≥ 3
  shared salient words that are ≥ 50% of the shorter (2 words was measured and
  doubled the count with false threads), on ≥ 2 days with an update in the
  last 3. The homepage's one email form is the Soft Personal band (Oct 9 rule).
- **`engine/share_cards.py` owns every link preview**, and `base.html.j2`
  decides through ONE Jinja global, `resolve_og_image`: a square cover becomes
  its show's 1200x630 card, nothing becomes the page's own card (keyed by the
  canonical path) or the network card, anything else (an episode card) passes
  through. **A template never writes its own `og:image`** (guarded) — the
  homepage shares as the network card, never the day's lead scene. The
  committed cards (`assets/share/`: network, every show, the site pages, every
  topic hub; alt text in `manifest.json`) are built by
  `scripts/build_share_cards.py` nightly and rewritten only when their pixels
  change; `assets/og-preview.png` IS the network card (hand-written pages and
  cached links still name it — it had carried the retired no-ads promise).
  Fonts are bundled (`assets/fonts`, OFL: DM Sans, Source Serif 4, Golos Text
  for Cyrillic) so a runner draws the same bytes as a laptop. **Episode cards
  are never committed** (landmine #1): run_show draws one on the show's art
  before the post is written and one on the episode's own scene in the video
  stage, each to a new R2 key `share/<slug>/epNNN-<art|scene>.jpg`, recorded in
  `digests/<dir>/share_cards.json` (metric `share_card`); members-only episodes
  get none. The hook budget is `engine.titles.SHARE_CARD_HOOK_MAX`; an overflow
  shortens through `clip_words`, never a slice. A new site page adds itself to
  `_page_cards` in the build script; a new show needs nothing. Backfill:
  Actions "Share Cards — backfill episodes" (gallery originals via R2).

### The tagline and the promise lead (Oct 18 2026)

Operator-directed: "Feed your curiosity, not your anxiety." and the promise
("News and ideas from N free shows on space, AI, markets, world news, science
and more. Every story is sourced, every claim is checked against its source,
and you can read the article or hear the episode it came from.") lead the
homepage, every share card and the default meta description, instead of
SpaceX and Tesla. Guards `tests/test_brand_messaging_2026_10_18.py`. Rules
that bind: **`engine/brand.py` owns both sentences** (`NETWORK_TAGLINE`,
`NETWORK_TAGLINE_RU`, `network_promise(n)`, `NETWORK_PROMISE_SHORT`; Jinja
globals `network_tagline` / `network_promise`); a template or card that types
them fails CI. **N is the FREE shows** (`generate_html._public_shows` —
public access and a feed), never `len(NETWORK_SHOWS)` (the card had said 31
beside the homepage's 26). **The front-page lead rotates by subject**
(`engine.landing_test.LEAD_ROTATION`: world news, AI, science, markets,
space, history — one a day by the edition date; the audience ranking picks
within the subject) and the top stories show one per beat before repeating
one (Tesla and SpaceX are one beat). The markets strip is alphabetical. Every
card's footer signs with the tagline (Russian on Russian cards); the network
card's art is the breadth of the network, never two of one beat. The Russian
«без рекламы» is in the sponsor guard now (two RU landers still promised it).
**Same day, operator follow-up: the flagships had been reduced too far.**
`engine.brand.FLAGSHIP_SHOW_SLUGS` (`spacex`, `tesla`) is the one list: the
front page gives them a **Flagship shows band every day** directly under the
lead (`landing_test.assemble(flagships=)` — a flagship runs there and in the
Latest list, never also as the lead, a top story or a section story; the lead
rotation picks from the rest), each card with its own market line
(`newsroom.SHOW_TICKERS`), the next launch on SpaceX, and its dashboard and
story tracker; the markets strip leads with TSLA again; the network share card
draws the two flagships as large tiles over a row of six breadth shows; the
start-here / about / join cards lead with them; the homepage meta names SpaceX
and Tesla first. The tagline and the promise wording are unchanged. The
masthead carries three actions (today's Nerra Daily, Find your show, Listen in
any app).

### YouTube pipeline pass (June 10, 2026)

Full video-pipeline review — writeup:
[`docs/youtube_review_2026_06_10.md`](docs/youtube_review_2026_06_10.md);
drift guards: `tests/test_youtube_quality_pass.py`. Headline: the
**silent config-drop class** — `_build_nested` discarded YAML keys the
dataclass didn't declare (now warns loudly + CI guard). Casualties fixed:
`shorts_min_score_threshold` (Tesla's 3.5 never applied anywhere — the
smart Shorts selector fell back to the voice start almost daily; the
single-Short path additionally never passed a threshold at all),
five NewsletterConfig fields (`requires_financial_disclaimer` was
ALWAYS False on the dataclass path), and `_defaults.yaml`'s network-wide
`min_audio_duration: 180` (dead inside the `audio:` block; now
top-level). Viewer-facing: long-form slideshow scenes now CYCLE (≤25 s
per image hold vs 168 s on Ep505) at zero added Grok-Imagine cost;
`channel: ru` without `YOUTUBE_REFRESH_TOKEN_RU` warns loudly;
`shorts_captions_path` metric records ASS vs SRT-fallback. Rejected with
reasons in the doc: bitrate floor, more images, `-preset slow`.

### Scheduled Show Review Agent (June 2026)

The manual quality-pass workflow (Tesla #573/#576, MIT #574, network #575)
is now automated and reproducible. A scheduled Claude Code agent
([`.github/workflows/show-review.yml`](.github/workflows/show-review.yml),
Tue + Fri 07:00 UTC) reviews ONE target per run — the least-recently-
reviewed of the 13 shows + a cross-cutting `network` target, per
[`docs/reviews/review_state.yaml`](docs/reviews/review_state.yaml) /
`scripts/pick_review_target.py` — following the codified playbook in
[`.claude/commands/review-show.md`](.claude/commands/review-show.md)
(same P0/P1/P2 method as the manual passes; transcripts as ears; hard
guardrails baked in). Output is always a **draft PR** on branch
`agent/review-<slug>-<YYYYMMDD>` with prompt/audio changes called out
under "⚠️ A/B-listen required" — the operator's merge is the ship gate,
so landmine #17 is preserved. New review docs go to `docs/reviews/`;
merging a review PR advances the rotation. Run `/review-show <slug>` in
any Claude Code session for a manual pass with identical methodology.
The loop is **recursive, not just scheduled**: every review appends to a
per-target ledger ([`docs/reviews/ledger/`](docs/reviews/ledger/)) with
measurable `predictions:` the NEXT review must score (`hit`/`partial`/
`miss` — a miss reopens the problem) and a `do_not_retry` list built from
operator verdicts (closed-unmerged review PRs = rejections; git reverts
of review commits = failed A/B listens — never re-proposed). Reviews
start from `scripts/review_snapshot.py <slug>` (deterministic
length/tic/chapter/cost/OP3 numbers — the cross-episode repeated-phrase
detector finds boilerplate tics mechanically). When the agent edits a
prompt and `GROK_API_KEY` is present it regenerates a digest via
`run_show.py <slug> --test` and pastes before/after OUTPUT excerpts into
the PR. `network` runs additionally meta-review the ledgers and may
propose edits to the playbook itself (drift guards pin the safety
language). The Daily Audit also dispatches an out-of-rotation review via
`scripts/dispatch_quality_reviews.py` when a show ships editorial-
critical issues (max 1/day, skips shows with an open review PR;
`daily-audit.yml` gained `actions: write` + `pull-requests: read` for
this). A review PR opening pings `NOTIFICATION_WEBHOOK_URL` (no-op when
unset). Setup + tuning: [`docs/REVIEW_AGENT.md`](docs/REVIEW_AGENT.md).
Drift guards: `tests/test_review_agent.py` (rotation covers every show —
scaffolded new shows must be added to the state file; playbook keeps its
safety language; ledger schema; snapshot + dispatcher logic).

**June 2026 — scheduled job migrated to Grok (cost).** A token-usage review
found the scheduled review agent was the network's largest Anthropic line item:
~$6-9/run of Claude Opus 4.8 (~$1,500-2,000/yr), dominated by cache-reads of
this 125 KB `CLAUDE.md` replayed across a long agentic loop and amplified by the
daily-audit out-of-rotation dispatches (the podcast pipeline itself has zero
Anthropic spend — all Grok). `show-review.yml` now runs
[`scripts/run_show_review.py`](scripts/run_show_review.py) on **Grok-4.3** (xAI;
`GROK_API_KEY`, already used everywhere else) instead of the Claude Code GitHub
Action — ~$0.30/run, a >95% cut; the `ANTHROPIC_API_KEY` secret is no longer
needed by the scheduled job. The runner gathers context (snapshot + ledger +
last ~10 transcripts), makes ONE Grok call with the playbook as its system
prompt, writes the review doc + ledger entry + advances rotation, and opens the
draft PR. One deliberate behavior change: it **proposes** prompt/audio edits in
the PR body under "⚠️ A/B-listen required — NOT applied" rather than auto-editing
them — which *strengthens* landmine #17 (nothing audio-affecting is
auto-committed). The fully-autonomous Claude path stays on demand: run
`/review-show <slug>` manually in a Claude Code session for a deep, multi-file
pass. The ledger writer appends by **text-splice** (never reserializes the
existing file) because three committed ledgers contain unquoted `: ` inside list
items and `safe_dump` line-wrapping can corrupt long plain scalars.

### Recursive narrative memory generalized (Phase 3, May 2026)

The content moat: Tesla's narrative-memory pattern generalized so other shows
become longitudinal chronicles, not disposable daily recaps.

- **`engine/show_memory.py`** — generalized engine (narrative tracker +
  performance signals + auto-mined themes), parameterized by a `MemoryConfig`
  (slug, label, file_prefix, seeded `default_programs`, `theme_keywords`).
  `SHOW_MEMORY_CONFIGS` registers **Models & Agents, Fascinating Frontiers,
  Planetterrian** (MIT already has its own `investment_tracker`; Tesla keeps
  its bespoke `engine/tesla_memory.py` — a future cleanup could fold Tesla into
  this engine). **Aug 16 2026 expansion: env_intel (regulatory arcs — a
  consultation today is a gazetted rule next year) and omni_view
  (world-news arcs feeding the Steel Man format) joined the registry** —
  the last two news-driven shows without memory; seeded conservatively,
  injection is A/B-gated per landmine #17.

- **Story-recurrence memory (Aug 16 2026, `engine/story_recurrence.py`;
  drift guards `tests/test_story_recurrence.py`).** The Fort Bend
  solar-factory story ran on 11 distinct days of Tesla's tracker window
  (5 of 10 episodes re-told from scratch, 4× inside Ep573) past THREE
  existing dedup layers — the 0.72 title-similarity/2-day
  `content_freshness` check misses re-headlined multi-day recurrence,
  the ContentTracker's flat DO-NOT-REPEAT block is ignored, and
  banning is editorially wrong anyway (a new filing deserves coverage
  as an UPDATE). The fix is the DP Pod lever-memory pattern applied to
  news: salient-token matching (auto common-token filter, so the brand
  name can't manufacture a match) over the dated headline window the
  ContentTracker already persists, delivered as INLINE
  `[ALREADY-COVERED NOTE …]` annotations under the exact matched
  articles in the digest prompt, framed update-don't-retell. Data-side,
  deterministic, no LLM calls, no new storage. Enabled via
  `story_recurrence: true` on the 9 daily news shows (lesson shows'
  recurrence is curriculum, narrative-queue shows have their own
  history; dp_pod/offshore_north lack tracker section patterns so it
  would no-op). Outcome metric: `story_recurrence_in_digest` per
  episode, scored against the Fort Bend baseline; the sanitizer strips
  any echoed annotation.
- **Flag-gated, single placeholder.** Prompts carry one
  `{narrative_memory_section}` placeholder; the show's thin hook
  (`shows/hooks/<slug>.py` → `show_memory.memory_pre_fetch/`
  `memory_post_generate`) injects the composed section when
  `config.memory_enabled` (new YAML flag, default false) is true, and an empty
  string otherwise — so **disabled is a true byte-for-byte no-op**.
  `run_show.py` `setdefault`s the key so a hook-load failure can never KeyError.
- **Public "story tracker" pages.** `generate_narrative_page(slug)` +
  `templates/narrative_page.html.j2` render `<show>-narrative.html` from the
  committed `digests/<slug>/<slug>_narrative_tracker.json`; show pages link it
  via a "Story Tracker" button. Sunday recaps inject the narrative block too.
- **Seeded conservatively** (factual program status, no speculative claims);
  themes accrue automatically from each digest. Operator can disable any show
  with one YAML flag (`memory_enabled: false`) — per landmine #17, A/B-listen
  before trusting the output change. Drift guards: `tests/test_phase3_memory.py`
  (+ `tests/test_show_memory.py` still pins the untouched Tesla module).
- **July 24 2026 expansion + hygiene pass** (drift guards:
  `tests/test_memory_lake_expansion.py`): **MIT, DP Pod, and Age of AI**
  joined the registry (all 8 non-Tesla content pillars now have memory;
  Tesla stays bespoke). MIT's narrative layer tracks MARKET NARRATIVES
  (rate cycle, AI-infra trade, Canadian wealth mechanics, crypto, the
  practice-portfolio story arc) — the bespoke `investment_tracker`
  trade/lesson ledger is untouched and stays authoritative for results.
  DP Pod tracks progress arcs (clean-energy build-out, health, conservation,
  The Lever track record). **Age of AI never runs through run_show**, so its
  memory feeds the Nerra Voices pipeline instead:
  `pipelines/voices/common.py:episode_memory_block` (reads the committed
  summaries file) injects a `{{show_memory}}` chronicle block into the
  question-generation / episode-thesis / Mira-narration prompts (continuity,
  callbacks, no retreading); the registry entry still gives it the narrative
  page + Story Tracker button + nightly OP3 signals. The podcast stage in
  run_show now `setdefault`s `{narrative_memory_section}` like the digest
  stage (a hook-load failure on a memory show could previously KeyError the
  podcast prompt). Mining hygiene: doubled-word bigrams ("google google"
  ×109 on Tesla — from unstripped `[Google News](url)` labels; the June-13
  label-strip was never ported to the bespoke Tesla module, now is) and
  generic-prose junk bigrams ("need know" ×78 on M&A) are filtered +
  committed histories scrubbed. Memory-section injection changes prompt
  context for MIT/DP Pod → A/B-listen per landmine #17.

### Per-show repositioning + per-episode blog title (Phase 4 partial, May 2026)

Editorial repositioning of four shows (prompt + sourcing changes — they change
generated output; per landmine #17, A/B-listen and revert via git if needed):

- **Omni View → "Steel Man".** Digest + podcast now require presenting each
  competing position in its *strongest* form (best supporting reason first),
  not a caricature — the listener shouldn't be able to tell which side the show
  favours.
- **Финансы Просто → women-in-finance-in-Canada.** New high-priority INCLUDE
  category + "Объясни как подруге" topic steer toward spousal RRSP,
  maternity/parental EI, childcare deduction, FHSA, financial independence;
  two women-finance `web_search_queries` added.
- **Привет, Русский! → vocabulary-first.** Theme is chosen FIRST (rotating
  everyday domains); news is optional backdrop only — it's a language course,
  not a news show.
- **Environmental Intelligence → all-province + B2B brief.** Added a scannable
  "Compliance Brief" section (digest + podcast) for forwarding to a team, plus
  four provincial `web_search_queries` (ON/AB/QC/SK-MB-Atlantic) for true
  national coverage (provincial bodies lack reliable RSS, so search not feeds).

- **Per-episode blog title (Phase 2 carry-over).** `engine/blog.py` now uses
  the unique episode **hook** for the blog `<title>`/`<h1>`/BlogPosting
  headline whenever the extracted title is just the show name (digests lead
  with a `# <Show Name>` heading) — previously every post's title was identical,
  killing per-episode SEO. Falls back to the show name only when there's no
  hook. Drift guards: `tests/test_phase4_repositioning.py`.

- **Operator tooling:** `scripts/update_tesla_narrative.py` now takes `--slug`
  (default tesla) for any memory show.

### Multi-platform Shorts distribution (Instagram Reels / TikTok, May 2026)

Opt-in per show (`youtube.multi_platform_enabled`, default false → no-op). When
on, each published Short also gets: a **safe-zone variant MP4** (drops the
bottom URL pill + end-card and lifts captions via
`build_short_video(drop_url_pill=, caption_margin_v=)` so overlays clear the
IG/TikTok UI bands), a **`.social.json` sidecar** with per-platform
caption/hashtags (`engine/social_metadata.py`), optional **R2 hosting**
(`social_r2_prefix`; needed for IG's URL-based API), and best-effort
**auto-posting** (`engine/social_publisher.py` — IG Graph + TikTok Content
Posting; a clean no-op until `IG_ACCESS_TOKEN`/`IG_USER_ID` /
`TIKTOK_ACCESS_TOKEN` are set, and requires the operator's developer-app
approval). Orchestrated by `engine/social_distribution.py`, called once per
Short from `run_show.py`'s YouTube stage (additive, non-fatal). YouTube uploads
use the original Short, unchanged. Full setup + limitations:
[`docs/social_distribution.md`](docs/social_distribution.md). Drift guards:
`tests/test_social_distribution.py`.

### Audience-growth pass (June 2026)

Full network review + growth implementation —
[`docs/network_review_2026_06.md`](docs/network_review_2026_06.md) is the
canonical writeup (market analysis, first real audience numbers, roadmap,
operator checklist). Shipped, all no-ops when secrets unset:

- **Audience read-back.** `scripts/fetch_op3_stats.py` (needs
  `OP3_API_TOKEN`) + `scripts/fetch_buttondown_stats.py` run in nightly
  maintenance before the dashboard build → `api/op3_stats.json`,
  `api/buttondown_stats.json`, public `site/data/popular_episodes.json`.
  Surfaces: dashboard "Audience" card, homepage "Most Played This Week"
  rail, homepage "Join N+ readers" social proof (hidden < 100 subs).
  OP3 response shapes are pinned in `tests/test_op3_stats.py` — verified
  live June 2026 (`monthlyDownloads`/`weeklyDownloads`; episode
  `downloads1/3/7/30/All` keys are OMITTED when the data span is young).
  **July 25 2026 nightly-fetch hardening** (drift guards:
  `tests/test_connector_budget.py`; contract:
  [`docs/analytics.md`](docs/analytics.md)): a live run surfaced two
  issues the JSON outputs had been hiding. (1) The Spotify step ran for
  **over an hour** — `spotifyconnector` retries a failing endpoint 6×
  with unbounded exponential backoff (~124 s each), and a registered
  feed with no plays yet answers `500` on `/metadata` + `/aggregate`
  *every* night (18 of 24 feeds were in that state, ~32 dead endpoints).
  New `engine/connector_budget.py` clamps the connectors' retry
  constants (3 attempts / 1 s base ≈ 6 s per dead endpoint, measured)
  and adds a wall-clock budget (`SPOTIFY_/APPLE_FETCH_BUDGET_SECONDS`,
  default 900 s) as the backstop; unreached shows keep their previous
  entry tagged `not_refreshed_this_run`, so a budget stop never shrinks
  the file. Applied to the Apple fetcher too (its constant is
  `MAX_RETRY_ATTEMPTS`, not `MAX_REQUEST_ATTEMPTS` — a copy-paste would
  clamp nothing). (2) **Age of AI's enclosures carried no OP3 prefix**:
  the prefix is applied by each publish path, never by
  `update_rss_feed`, and the Nerra Voices publisher
  (`pipelines/voices/publish_episode.py`) bypasses run_show — so its
  downloads were invisible. Fixed for new episodes; the published Ep001
  URL is deliberately left unprefixed (rewriting a live enclosure
  re-downloads it for every subscriber). Any future show that bypasses
  run_show must apply the prefix in its own publish step. The `dp_pod` /
  `age_of_ai` OP3 **404s are an indexing lag**, not a bug — OP3's docs
  define 404 as "OP3 doesn't know about the show"; downloads attach
  retroactively once it indexes the feed. A 404 persisting for weeks
  means check the prefix first.
- **Adjacency-map bug fixed.** `newsletter.network_adjacencies` (and the
  other newsletter composition keys) had been mis-indented under
  `cost_circuit_breakers:` in `shows/_defaults.yaml` — newsletter +
  synthesizer read an empty map, so the cross-network email module was
  silently degraded network-wide. Drift guard pins the location. NOTE:
  there are deliberately THREE curated cross-show mappings — web
  (`generate_html.NETWORK_SHOWS[slug]["related_show"]`), email
  (`newsletter.network_adjacencies`), audio/X
  (`engine/network_promo.ENGLISH_SHOWS`). Do not consolidate casually;
  each is tested and serves a different surface.
- **Newsletter growth loop.** Every show now gets a deterministic
  Buttondown slug (`<show>-ep<num>-<hook>`; was Russian-only) so the
  view-in-browser/archive link renders pre-send on dailies AND weeklies;
  reply/share row gained a localized "Forwarded this email? Subscribe
  here" line (UTM `forward_subscribe`).
- **X cross-promo reply.** Flag `publishing.x_cross_promo` (network
  default true in `_defaults.yaml`, dataclass default false) posts a
  second tweet threaded under the teaser: "Follow @{x_handle}" + one
  sibling plug from the `network_promo` rotation. `x_handle` set only for
  tesla/@teslashortstime + the PLANETTERRIAN_X_ shows/@planetterrian;
  OV/M&A/MIT pending operator confirmation. Roughly doubles posts/day per
  X app — flip the flag off if the free-tier cap trips.
- **Podcasting 2.0 channel tags.** `update_rss_feed` now injects
  `podcast:funding` (→ `/#newsletter`) + `podcast:person` (host) on every
  rebuild via `_inject_channel_funding_person_tags` (same pattern as
  `podcast:locked`); empty kwargs = byte-for-byte legacy behavior.
- Sitemap: + `player.html` + `modern-investing-performance.html`,
  − `404.html`. Nightly site-regen step now passes the marketing env vars
  (was silently stripping analytics tags on nightly rebuilds).
- **Known wart (operator decision pending):** Russian shows speak the
  ENGLISH `_AI_DISCLOSURE` line at the end of every episode; a localized
  `_AI_DISCLOSURE_RU` is a one-liner in `run_show.py` but changes shipped
  audio → landmine #17 A/B-listen first.

### Multilingual + international distribution (late June 2026)

Three additive, off-critical-path systems that turn each English episode into a
multi-language, multi-channel property. English stays the canonical master and
the fallback everywhere; every piece is best-effort and non-blocking.

- **Multilingual translation tracks (FR / RU / ES / ZH).** A post-hoc stage
  (`engine/multilingual.py`, `engine/translate.py`) translates a finalized
  English `_tts.txt` + title/description via Grok, re-voices it with the show's
  **existing** cloned Grok voice (`kdif6sqjcyiq` — one voice across languages;
  `GROK_CLONED_VOICE_ID` optional override), validates the result (rejects
  refusals / English echoes / wrong-script ZH), and uploads to R2 as
  `…/<file>.<lang>.mp3`. Enabled network-wide via `multilingual.auto: true` in
  `_defaults.yaml` (the two RU shows opt out); ~$0.18/ep (~$50-55/mo). The blog
  page renders a language switcher + inline player only when a track exists.
  Each language also gets a real subscribable **per-language podcast feed**
  (`podcast.{fr,ru,es,zh}.rss`) built fresh from `summaries_<slug>.json` by
  `engine/language_feeds.py` (deterministic per-lang GUIDs; channel
  title/description translated once + cached in
  `digests/<slug>/channel_i18n.json` so nightly rebuilds cost no credits).
  Per-language pronunciation lives in `shows/translation_overrides.yaml`
  (language-scoped; never touches the English path). Orchestrated by
  `.github/workflows/multilingual.yml` (its own workflow so RU TTS + a second
  render can never delay/break the English publish). Docs:
  [`docs/multilingual.md`](docs/multilingual.md). Drift guards:
  `tests/test_multilingual.py`, `tests/test_language_feeds.py`.
- **RU YouTube dubs → @NerraRU.** For a show with
  `youtube.ru_dub_enabled: true`, the same multilingual workflow reuses the
  already-generated RU audio track **and** the episode's existing Grok gallery
  scene images (from the R2 manifest — **$0 extra image cost**) to render a
  long-form + 1 Short and upload them to @NerraRU with Russian metadata +
  disclosure (`engine/ru_dub.py`, `scripts/publish_ru_dubs.py`). Enabled for
  `tesla`, `spacex`, `fascinating_frontiers`, `modern_investing`. Idempotent via
  a per-show `digests/<slug>/youtube_videos.ru.json` index (per-show → no
  cross-show push contention). RU Shorts reached EN-channel parity (per-word
  Cyrillic ASS captions, smart-start, end-card CTA) in PR #748. Needs
  `YOUTUBE_REFRESH_TOKEN_RU` (no-ops with a log line until set). Docs:
  [`docs/ru_youtube_dubs.md`](docs/ru_youtube_dubs.md). Drift guards:
  `tests/test_ru_dub.py`.
- **Generalized language dubs → @NerraFR (July 18 2026; future languages).**
  `engine/lang_dub.py` is the language-parameterized sibling of `ru_dub`
  (which stays bespoke + untouched for @NerraRU — the show-memory
  precedent). A `DubLanguage` registry entry + `youtube.dub_languages:
  [fr]` + a `YOUTUBE_REFRESH_TOKEN_<CH>` secret + a `SEED_TIERS` channel
  = a new dubbed channel; language-neutral machinery is IMPORTED from
  ru_dub (no fork). FR registered for tesla/spacex/FF/modern_investing
  (MIT's multilingual `languages` gained `fr` — the track is the dub's
  input), **seeded shorts-only** with the RU 2.0 long_vpd floor (RU
  lesson: dubbed longs earned ~9% retention), full RU parity (optimized-
  title translation with echo rejection, smart multi-Shorts + fill,
  French ASS captions, French end-card + funnel comment, `no_scenes_yet`
  deferral, per-show `youtube_videos.fr.json` auto-picked-up by
  analytics/policy/subscriber tracking). Sweep:
  `scripts/publish_lang_dubs.py --lang fr` in `multilingual.yml`.
  Credentials resolve generically (channel `xx` →
  `YOUTUBE_REFRESH_TOKEN_XX`; en/ru behavior pinned unchanged).
  **@NerraFR went LIVE 2026-07-21** (this section previously said
  DORMANT) — 42 videos across the four shows in its first ten days, 38
  Shorts + 4 long. It was invisible to the feedback loop until
  2026-07-29 because `fetch_youtube_analytics` globbed only
  `youtube_videos.ru.json` beside the base index, so the policy computed
  `video_count_14d = 0` for every FR show and froze them at seed tier —
  a channel that could never earn a promotion. The glob is now a
  pattern, but it landed four minutes before that night's run, so **no
  nightly has definitely included it**; every FR show still reports
  `short_vpd: null`. First clean read is the next nightly, and FR tiers
  should not be touched until a couple of weeks of real velocity exist.
  Docs: [`docs/lang_youtube_dubs.md`](docs/lang_youtube_dubs.md). Drift
  guards: `tests/test_lang_dub.py`.
- **Video podcasts → Apple (July 25 2026 pilot: tesla + spacex).** Doc:
  [`docs/video_podcasts.md`](docs/video_podcasts.md); drift guards:
  `tests/test_video_podcast.py`. Apple's Feb-2026 HLS video experience is
  gated to a short list of hosting partners and it ignores
  `podcast:alternateEnclosure`, so a self-hoster's ONLY route into the
  Apple video player is a plain MP4 `<enclosure>` — and Apple's own
  guidance is to publish video as a **separate show**. So the two pilot
  shows emit `podcast.video.rss` / `spacex_podcast.video.rss` beside their
  audio feeds; **the audio feeds are never touched and no published
  enclosure URL changes**. The asset is the long-form 1920x1080 MP4 the
  YouTube stage already renders and previously deleted right after upload
  (`run_show._publish_youtube`'s cleanup) — so the marginal cost is one R2
  upload and ZERO extra render/Grok spend. Flow: `_publish_youtube` calls
  `engine.video_feed.upload_episode_video` right after the render (BEFORE
  the YouTube upload, so a YouTube failure doesn't also cost the video
  episode, and before the `unlink`) → `engine.summaries_io.upsert_video`
  attaches `record["video"]` → `engine.video_feed.build_video_feed_for_show`
  rebuilds the feed from summaries (the `language_feeds` pattern: fresh
  rebuild, deterministic `<prefix>-video-epNNN-YYYYMMDD` GUIDs, churn
  suppression, never an empty feed). Three things that look redundant and
  are not: `content_type="video/mp4"` is passed EXPLICITLY on both the
  upload and the enclosure (`upload_to_r2` defaults non-`.mp3` to
  `application/octet-stream` and `publisher.py` hardcodes `audio/mpeg` in
  three places — either would make Apple refuse the episode); the R2 key is
  `video/<slug>/…`, outside the audio keyspace every published enclosure
  depends on, so a lifecycle rule can expire video alone; and nightly's
  add-paths needs `*.video.rss` because Tesla's audio feed is the ROOT
  `podcast.rss`, which `*_podcast.*.rss` does not match
  (youtube_channel_history silent-drop class). Enclosures are deliberately
  NOT OP3-prefixed (OP3 is an audio-download redirector, not a video CDN;
  engagement comes from Apple Connect). **Known coupling:** the video
  episode is a by-product of the long-form render, so an adaptive-policy
  shorts-only day yields no video episode — the run logs a `::warning::`
  and records `video_podcast_render_only` (Sep 22 2026 — it renders
  anyway for the feed and skips only the YouTube upload). Per-
  episode `video_podcast_bytes` is recorded so the R2 storage projection
  is measured rather than guessed (unmeasured at merge). Operator work is
  the Apple Podcasts Connect submission of each `.video.rss` as a NEW
  show — see the doc's checklist. Rollback is one YAML flag per show.
- **Recursive YouTube → titles feedback loop.** Mirrors the OP3 audio loop:
  `scripts/fetch_youtube_analytics.py` reads each show's
  `digests/<slug>/youtube_videos.json`, queries the YouTube Analytics API for
  retention (`averageViewPercentage` — the strongest public content-quality
  signal; CTR is Studio-only), and `scripts/update_youtube_performance.py`
  distils a per-show `title_hint` into `youtube_performance.json` that
  `engine/youtube_titles.generate_youtube_titles` injects into the title prompt
  (nightly). It touches ONLY the YouTube title (visual metadata, not the spoken
  hook) so it sits **outside** the landmine #17 A/B gate, and ships **dormant**
  — a clean no-op until the operator re-auths the OAuth token with the
  `yt-analytics.readonly` scope and a few weeks of data accrue. Docs:
  [`docs/youtube_feedback_loop.md`](docs/youtube_feedback_loop.md). Drift
  guards: `tests/test_youtube_feedback_loop.py`.

## Current Refactoring Goal

**Extract duplicated code from the show scripts into `engine/` modules.**

Phase 1 (complete):
- `engine/utils.py` — `number_to_words`, `_env_float/int/bool`,
  `calculate_similarity`, `remove_similar_items`, `deduplicate_by_entity`
- `engine/tts.py` — `validate_elevenlabs_auth`, `speak`, `_speak_chunk`,
  `_chunk_text_for_elevenlabs`
- `engine/audio.py` — `get_audio_duration`, `format_duration`,
  `mix_with_music` (standard / delayed-intro / dual-music modes),
  `normalize_voice`

Phase 2 (complete):
- `engine/publisher.py` — `update_rss_feed`, `get_next_episode_number`,
  `save_summary_to_github_pages`, `post_to_x`, `format_digest_for_x`,
  `format_tst_digest_for_x`, `apply_op3_prefix`
- `engine/content_tracker.py` — `ContentTracker` with per-show section patterns
  (TST, FF, PT, OV, EI, M&A)
- `engine/fetcher.py` — `fetch_rss_articles`
- `engine/generator.py` — `generate_digest`, `generate_podcast_script`
- `engine/tracking.py` — `create_tracker`, `record_llm_usage`,
  `record_tts_usage`, `record_x_post`, `save_usage`

Phase 3 (current):
- All 13 shows now run via `run_show.py` + YAML configs in production (CI/CD).
- Legacy scripts (`digests/{tesla_shorts_time,omni_view,fascinating_frontiers,
  planetterrian}.py`) are **deprecated** — retained for reference only.
- `run_show.py` is the canonical entry point; legacy scripts are not called
  by any workflow or cron job.

## Known Landmines

**Sitemap `lastmod` must not follow file mtime.** Blog post files are
rewritten by every regeneration; the episode date is not. If `lastmod`
tracks mtime, a network-wide regen tells Google all ~1,250 posts changed
at once, which is the exact signal the May 2026 audit removed.
`generate_sitemap()` reads `datePublished` out of each page's JSON-LD.
Do not "simplify" it back to `_file_lastmod`.

**`digests/_newsletter_sending_blocked.json` silently skips the
newsletter for 7 days.** If newsletters stop going out, check for that
file before debugging Buttondown.

**A queued Actions run checks out the SHA fixed at TRIGGER time.** Any
guard that reads committed state (the weekly newsletter's per-week
sent markers, skip markers, cooldown annotations) is blind in a run
that queued behind another in a concurrency group unless the job
first moves its workspace to the live tip (`git fetch --depth=1
origin main && git reset --hard origin/main`). Sep 6 2026: the late
Sunday cron queued behind a manual dispatch, ran twenty minutes later
on a tree from before that dispatch committed its markers, and
re-sent six shows' weeklies. `weekly-newsletter.yml` now syncs first;
guard: `TestWeeklyNewsletterSameWeekGuard`.

**Show slugs use underscores, page filenames use hyphens.**
`fascinating_frontiers` → `fascinating-frontiers.html`. Getting this
wrong in `publishing.rss_link` 404s the "website" button in every
podcast directory, and nothing in the pipeline fetches its own
`rss_link` to notice. `validate_show.py` now checks it.

**Operator's first stop:** the live state of every landmine below is rendered
by [`management.html`](management.html), fed by
[`scripts/generate_dashboard.py`](scripts/generate_dashboard.py) → `api/dashboard.json`.
The dashboard's **Growth levers** section (Aug 2026) renders the per-channel
WoW scorecard, staggered-Shorts/sweep health, the specials queue, analytics
freshness (alerts past 36h — the Aug 6 outage staleness lesson), and the
experiments register: **every change shipped to move a number gets an entry
in [`docs/experiments.yaml`](docs/experiments.yaml)** with its readout date
and (where supported) a live metric key — a typo'd metric name fails CI
(`tests/test_dashboard_growth.py`).

The page carries **three views** (Aug 2026): Operator (everything),
Sponsor (`?view=sponsor` — audience + catalogue, no spend/valuation) and
**Investor** (`?view=investor` — audience, unit economics, industry
benchmarks and now/1yr/5yr value scenarios). Every external market figure
(percentile ladder, CPMs, production costs, M&A multiples) lives ONLY in
[`docs/industry_benchmarks.yaml`](docs/industry_benchmarks.yaml) with
sources + an `as_of` date the page renders; the generator's
`build_benchmarks_section` / `build_investor_section` compute placement
and scenarios from the same audience/cost sections the rest of the page
uses. Honesty rules: episode denominators come from RSS pubDates (credit
files count dub tracks and overstate episodes), unmeasured = null never 0,
projections are labelled scenarios with their assumptions serialized next
to them. Drift guards: `tests/test_investor_dashboard.py`.
Items 7 and 10 are intentionally excluded from the dashboard (per an explicit
decision); everything else has a live status card.

### Active Issues

1. **2.2 GB of MP3s in git HISTORY (HEAD is clean)** — measured June 10
   2026: zero episode MP3s are tracked at HEAD (guards in `.gitignore` +
   the commit step's `git reset -- '*.mp3'`; only the 43 MB of
   `assets/music` themes + two voice-reference WAVs remain, which the
   pipeline needs). All enclosure URLs serve from R2. CI clones are
   shallow since the June 2026 workflow pass (~115 MB packed vs ~2.5 GB
   full), so the day-to-day clone cost is FIXED and growth is now
   text-only (~50 MB/month → years of headroom under GitHub's 10 GB
   limit). The history weight itself can only be removed by a
   `git filter-repo` rewrite + force-push of main — DESTRUCTIVE:
   requires a paused-cron window (12 daily workflows push to main and
   could race the force-push and resurrect old history), invalidates
   every existing clone, and dangles the commit SHAs referenced across
   docs/. Playbook in
   [`docs/workflow_review_2026_06_10.md`](docs/workflow_review_2026_06_10.md);
   operator-scheduled, not urgent. For full local clones meanwhile:
   `git clone --filter=blob:none` skips historical blobs.
2. **Git LFS breaks RSS** — `raw.githubusercontent.com` returns pointer files
   for LFS-tracked content. Do NOT use LFS for MP3s.
3. **Historical TST/OV flat files in `digests/`** — ~220 legacy output files
   (MP3s, markdown, JSON, HTML, TXT) remain at the `digests/` top level from
   before shows were migrated to subdirectories. These cannot be moved without
   breaking existing RSS feed URLs. New episodes now write to subdirectories.
23. **GitHub push transients on large text commits ("fatal error in commit_refs")** —
    Successful episode generation (run_show.py) can produce 8k–10k+ line commits
    (full Whisper transcripts JSON+txt, _tts.txt, metrics, chapters, digests, blog
    HTML, RSS updates). GitHub's ref-update service occasionally returns a server
    error during `git push origin main` even after the pack is accepted. The
    4-attempt rebase/merge loop in `.github/workflows/run-show.yml` handles
    normal concurrency races between matrix jobs. On final exhaustion the step
    now calls `scripts/create_recovery_pr.sh` which creates a `recovery/<show>-<run_id>-<ts>`
    branch, pushes it, and opens a **draft PR** with the complete artifacts plus
    operator instructions. The job exits 0 (data preserved). The PR appears in
    the repo for the operator to merge. This is the hardened path for the
    "Commit and push output" step (the finalize shared-pages push has a 5-attempt
    loop + warning but no recovery PR because those pages are fully regenerable).
    The `safe-commit-push` composite now has an opt-in `recovery-on-failure`
    input wired for the two callers whose commits are expensive to regenerate
    (nightly maintenance, topic-queue restock); the other composite callers
    deliberately stay fail-visible because their artifacts are regenerable
    (stale note corrected 2026-08-15). The multilingual
    sweep's commit step (`.github/workflows/multilingual.yml`) also uses the
    recovery-PR escape hatch now, since it commits large translation-track +
    per-language-feed diffs on the same push-contended `main`. Drift guard:
    the recovery script + the warning annotation in the Actions log.

24. **Schedule punctuality: exact-time dispatcher + duplicate guard (June
    2026)** — GitHub delivers cron `schedule` events 1-6 h late (Tesla's
    11:00 slot observed starting 13:54). Fix: run-show crons moved to
    off-peak :07/:37; `workers/scheduler/` (Cloudflare Cron Trigger,
    fires to the minute) dispatches each show via `workflow_dispatch` at
    its intended slot once the operator deploys it (fine-grained PAT →
    `wrangler secret put GITHUB_DISPATCH_TOKEN`, `wrangler deploy` — see
    its README); the gate's same-day duplicate guard (checks today's
    "Auto-generated: <show> <date>" commit) lets the delayed GitHub cron
    coexist as fallback without double-publishing. The Worker's SLOTS
    table must stay in sync with the gate's CRON_MAP —
    `tests/test_scheduling_punctuality.py` fails CI on drift.
    **What FIRES is what was last deployed, not what is committed** (Sep
    24 2026): a `wrangler deploy` from a checkout that predated the
    launch-cohort PR left nine new shows off the live slot table while the
    cron string already covered their hours, so every old slot fired on
    the minute and no new one did until GitHub's hours-late fallback. The
    Worker's `GET /` lists the live `slots`; `scripts/check_scheduler_deploy.py`
    diffs them against `src/index.ts` nightly once the repo variable
    `SCHEDULER_STATUS_URL` is set. Same day: the dispatcher now honours
    `FIRST_RUN` (Peptides Ep2 fired a week early — only the status page's
    `next_slot` had checked it, and a `workflow_dispatch` skips the
    workflow's own launch-date gate by design).

25. **The TTS engine can speak text we never sent — the spoken-text gate
    is the only thing standing between that and a listener (Sep 14
    2026, Tesla Ep605).** The first 45 s of the published Ep605 are Grok
    TTS reading its own text-normalizer's chain of thought in the host's
    voice ("One thing, the input has line breaks, preserve them … Rules.
    Do not convert at sign in code … So the output should be the entire
    text unchanged") in place of the hook and the identity line. The
    saved `_tts.txt` was clean: the defect was injected SERVER-SIDE by
    the `text_normalization: true` LLM stage (the same component that
    merged "S P C X" into "S&P CX" on SpaceX Ep051), and every check the
    episode passed measured something else — `tag_leak_detector` is a
    registry of tag WORDS (read 0), the opt-in `validate_transcription`
    scores the WHOLE episode (a 50-word leak in 1,083 scores ~0.9), and
    `script_audit` reads the script, never the audio. It shipped to RSS,
    both Shorts (the hook-first Short IS the leak), the Apple video feed
    and Nerra Daily Ep025. Unique across 1,709 committed transcripts.
    Now: `engine/spoken_text_gate.py` compares the Whisper transcript
    (already produced for every episode, BEFORE mix and publish) with the
    in-memory script — the opening must match (`opening_match` ≥ 0.5;
    Ep605 0.17, healthy floor 0.67) and no run of ≥ 40 spoken words may
    be absent from the script (Ep605 61, legit max 22) — with Whisper's
    own artifacts filtered first (a >6 words/s segment is a
    hallucination, M&A Ep140; an n-gram looped >3× is collapsed, MIT
    Ep162). A failure re-runs the IDENTICAL synthesis once
    (`_synthesize_raw_mp3()` closure; the defect does not repeat), a
    second failure SKIPS the episode (`_skip_episode("spoken_text_gate")`).
    `tts.spoken_text_gate: enforce` network-wide; `shadow` on the two
    Russian shows and forced for any non-English transcript (Whisper
    writes Привет's English halves as Cyrillic sound-alikes — the
    instrument is not calibrated there). A missing transcript never
    blocks; it records `no_transcript` and warns that the audio is
    unverified. Metrics `spoken_text_gate*` per episode; calibration
    re-run with `scripts/audit_spoken_text.py` BEFORE moving a
    threshold. Also: `tts.apply_text_normalization` now reaches the Grok
    request (`"off"` → `text_normalization: false`; it was hard-wired
    true) — it stays ON because residual digits (14.3.8, B1081, 845km)
    still reach the TTS text daily and switching it changes shipped
    audio on every show (landmine #17). **Not covered yet:** the FR/RU/ZH
    dub tracks and the RU/FR YouTube dubs use the same request and are
    never compared with their text.
    **Repairing such an episode: never clip, always re-synthesize**
    (Sep 15 2026). The leak REPLACES content — Ep605 never spoke its
    hook, identity line or the two opening sentences of its lead story,
    and the audio resumes mid-sentence — so cutting the defect ships an
    episode that opens on a fragment, for the same downstream cost as a
    re-run. `scripts/resynthesize_episode.py` + Actions
    **"Re-synthesize Episode"** re-run the committed `_tts.txt` through
    the same synthesis: dry-run by default, **uploads to the SAME R2
    key** so no subscriber is re-pointed, and **refuses to upload audio
    the spoken-text gate has not passed** (one retry, then abort — the
    repair tool must never become another way to ship the defect).
    Chapter titles reproduce exactly and only timestamps move; the feed
    item keeps its published title and description and is corrected for
    duration and byte length. It does not touch YouTube (the API cannot
    replace a video's file) — it computes the defect's time span and
    says per video whether to delete or KEEP, because a Short whose clip
    sits past the defect is fine and **the RU/FR dubs are a separate
    synthesis of the translated script and are never affected** (an
    earlier draft listed all eight Ep605 videos for deletion; guard
    `test_dub_videos_are_never_listed_for_deletion`). Guards:
    `tests/test_resynthesize_episode.py`.
    Review: [`docs/reviews/tesla_ep605_spoken_text_gate_2026_09_14.md`](docs/reviews/tesla_ep605_spoken_text_gate_2026_09_14.md).
    Guards: `tests/test_spoken_text_gate.py`.

### Resolved Issues (Feb 2026)

4. **TST/OV output dirs fixed** — `shows/tesla.yaml` and `shows/omni_view.yaml`
   now use `digests/tesla_shorts_time/` and `digests/omni_view/` for
   `output_dir` and `audio_subdir`, matching FF/PT/EI. Legacy scripts already
   pointed to subdirectories. Audio URL construction in both legacy scripts
   also fixed.
5. **Legacy `digests/digests/` path bug cleaned up** — nested directory deleted,
   RSS references removed, SETUP.md corrected. Defensive scanning code remains
   in `tesla_shorts_time.py` in case any legacy files resurface.
6. **58 duplicate `_formatted.md` files deleted** — removed in commit
   `0c10b7f`, code no longer generates them.
7. **`NEWSAPI_KEY` dead secret removed** — not present in active workflow
   (`run-show.yml`), not used in any code. Integration test
   `test_no_newsapi_in_active_workflow()` guards against re-introduction.
8. **Feature flags consistent across shows** — all four legacy scripts
   (TST, FF, PT, OV) support env-overridable `TEST_MODE`, `ENABLE_X_POSTING`,
   `ENABLE_PODCAST`, and `ENABLE_GITHUB_SUMMARIES`. `run_show.py` uses
   CLI flags (`--test`, `--skip-x`, `--skip-podcast`) instead.
9. **ElevenLabs tuning baseline lives in `shows/_defaults.yaml`** — the
   canonical network baseline is now whatever
   [`shows/_defaults.yaml`](shows/_defaults.yaml) declares (today:
   `stability=0.5`, `similarity_boost=0.75`, `style=0.0`, English voice
   `dTrBzPvD2GpAqkk1MUzA`, Russian voice `gedzfqL7OGdPbwm0ynTP`). Per-show
   overrides are allowed; drift is tracked live in the management
   dashboard's *Voice settings consistency* table. Any show row flagged
   with a drift is either intentional (record the reason in the show's
   YAML as a comment) or a regression to investigate. Historical note:
   an earlier baseline had stability `0.65`, similarity boost `0.9`, and
   style `0.85`; that combination is no longer blessed and should not be
   reintroduced without updating `_defaults.yaml`.
10. **Early episodes deleted** — first 20 Tesla, 10 FF, 10 PT, 10 OV episodes
    removed (quality issues). RSS entries removed where applicable.
11. **All 10 shows on Grok TTS (May 2026, full-network migration)** —
    Chatterbox, Kokoro, and Fish Audio were trialled and removed.
    English shows (including Tesla Shorts Time as of the third migration
    wave) all use the operator's custom-trained voice `kdif6sqjcyiq`
    for a single consistent host identity. Russian shows use the
    custom Olya voice (`0b875ae2`). ElevenLabs is no longer used in
    production. Network cost: ~10× cheaper per character on Grok
    ($15/M per the xAI models page, read 2026-10-02 — an earlier version
    of this line said $4.20/M, the promo-era figure; `engine/tracking.py`
    was right all along — vs $150/M for ElevenLabs Flash). Reuses `GROK_API_KEY` /
    `XAI_API_KEY` — no new secret. See landmines #16 and #17.
12. **Summaries JSONs moved** — all summaries live in per-show subdirectories
    (`digests/<show>/summaries_*.json`), not at the `digests/` top level.
13. **LLM default migrated to `grok-4.3` (May 2026)** — released 2026-04-30,
    always-on reasoning, $1.25/$2.50 per 1M tokens (~55% cheaper per
    episode than the previous `grok-4.20-*` defaults). Network default,
    synth model, Tesla / Modern Investing per-show overrides, and the
    tool-use path (`digests/xai_grok.py`, X / web search via the
    Responses API — confirmed grok-4.3 supports `x_search` and
    `web_search` built-in tools) all now run on `grok-4.3`. Refusal
    fallback stays on `grok-4.20-reasoning` so refusals genuinely
    switch model snapshot rather than retrying the same primary.
    Pricing for the historical 4.20 family is retained in
    `engine/tracking.py` so old `credit_usage_*.json` files still cost
    out correctly.
14. **YouTube slideshow imagery is curated, not derived from `keywords:`**
    — early Tesla videos (e.g. Ep456) shipped with topless / fashion-model
    photos because `engine/visual_assets.py:_select_keywords()` was passing
    raw show keywords (`model 3`, `model y`, `model s`) to Pexels with no
    topic context. Pexels treats `model` as a person who poses, not a car.
    Fix landed May 2026: every show's `youtube:` block now declares
    `image_queries:` (curated, disambiguated phrases) and optionally
    `image_query_prefix:` (auto-prepended to any `keywords:` fallback).
    A safety filter (`image_safe_skip_terms`, default list in
    [`engine/config.py`](engine/config.py)) drops Pexels results whose
    URL slug contains people-only / off-topic substrings. The filter
    count is recorded as the `pexels_photos_filtered` metric — a spike
    means a show's queries need tightening. The
    `test_every_show_yaml_has_image_queries` test in
    [`tests/test_visual_assets.py`](tests/test_visual_assets.py) blocks
    any new show from going live without curated phrases.
15. **YouTube Podcasts surface requires manual Studio setup, not API**
    — the pipeline correctly creates per-show playlists and adds each
    upload via `engine/youtube.add_video_to_playlist()`, and every show
    YAML carries a `podcast_playlist_id:` (verified live in CI). But a
    playlist only appears under "YouTube Podcasts" once it's been
    flagged as a podcast in YouTube Studio: open
    `Studio > Content > Podcasts > "Set existing playlist as a podcast"`
    on each channel (`@NerraNetwork` for English shows, `@NerraRU` for
    Финансы Просто / Привет, Русский!) once per playlist. The YouTube
    Data API has no endpoint for this flag. Once flagged once, every
    future video added via the API automatically becomes a podcast
    episode. **One-time setup per playlist — not a code change.**
16. **TTS network default flipped to Grok TTS (May 2026)** — staged in
    two PRs:
    - **First wave (Russian shows):** Финансы Просто and Привет,
      Русский! switched from ElevenLabs voice `gedzfqL7OGdPbwm0ynTP` to
      Grok TTS with the custom "Olya" voice `0b875ae2` (trained on the
      xAI Console). Validated with one live episode (PR Ep017,
      2026-05-02) before broader rollout.
    - **Second wave (English shows):** Network default in
      [`shows/_defaults.yaml`](shows/_defaults.yaml) flipped to
      `provider: grok`, `voice_id: sal` (Grok built-in named voice),
      `language_code: en`. The 7 non-Tesla English shows (Omni View,
      Fascinating Frontiers, Planetterrian, Env Intel, Models &
      Agents, Models & Agents for Beginners, Modern Investing) now
      inherit those defaults — their `tts:` blocks are intentionally
      empty (`{}`) to make inheritance the contract. Tesla Shorts Time
      explicitly overrides back to `provider: elevenlabs`,
      `voice_id: dTrBzPvD2GpAqkk1MUzA` because voice continuity on the
      network's largest show outweighs the cost delta.

    Implementation details: `engine/tts.py:synthesize()` dispatches on
    the `provider` kwarg; the Grok path posts to
    `https://api.x.ai/v1/tts` and reuses `GROK_API_KEY` /
    `XAI_API_KEY` (no new secret). ElevenLabs-only voice settings
    (`stability`, `similarity_boost`, `style`, `use_speaker_boost`,
    `model`, `speed`) live in [`shows/_defaults.yaml`](shows/_defaults.yaml)
    under a `# ---- Legacy ElevenLabs baseline ----` block — harmless
    when `provider=grok` (Grok path silently ignores them) and a tuned
    starting point if any show flips back to ElevenLabs. Pricing is
    per-provider in [`engine/tracking.py`](engine/tracking.py):
    `TTS_PROVIDER_PRICING`. Three drift guards in
    [`tests/test_tts_grok.py`](tests/test_tts_grok.py) block silent
    regressions: `test_russian_shows_use_grok_tts` (Olya voice on
    Russian shows), `test_english_shows_resolve_to_grok_sal` (sal voice
    on the 7 English shows after deep-merge), and
    `test_tesla_stays_on_elevenlabs` (TST voice continuity).
    `ELEVENLABS_API_KEY` is still required because Tesla uses it; if
    Tesla ever migrates, the env-var requirement disappears
    (`run_show.py:_validate_environment` already gates the check on
    `provider == "elevenlabs"`).
17. **Full-network voice migration + broadcast-quality audio pipeline
    (third TTS wave, May 2026)** — Tesla Shorts Time joined the rest of
    the network on Grok TTS. Every English show now inherits the
    operator's custom-trained voice `kdif6sqjcyiq` from
    [`shows/_defaults.yaml`](shows/_defaults.yaml); the previous `sal`
    built-in voice was retired and TST's ElevenLabs override
    (`provider: elevenlabs`, voice `dTrBzPvD2GpAqkk1MUzA`) was removed.

    Same migration shipped a broadcast-quality audio pipeline. Cumulative
    changes to the per-episode signal flow:

    - **Grok TTS request:** now requests **WAV at 48 kHz** with
      `text_normalization: true` (`engine/tts.py:grok_speak_chunk`).
      Previously MP3 at 24 kHz with no normalization. The pipeline
      crossfades chunks in WAV and only encodes to MP3 once at the very
      end (one lossy pass instead of two). Server-side text normalization
      handles dates, currencies, and ordinary numbers — the
      `pronunciation_map.yaml` layer remains for proper-noun / acronym
      overrides.
    - **Voice EQ chain** (`engine/audio.py:_voice_norm_full_cmd`) —
      highpass 80 / lowpass 15k / adeclick+afftdn / loudnorm -18 /
      acompressor 4:1 / alimiter. **This entry used to claim the chain
      "gained a 6.5 kHz dip (`equalizer=f=6500:t=q:w=1.5:g=-3`) for
      gentle de-essing". It never did** — `git log -S "6500"` on
      `engine/audio.py` returns nothing, the string has never existed in
      the file. Corrected 2026-07-30. Do not "restore" it: there is
      nothing to restore.
      **De-essing was then measured and deliberately declined.** With a
      live key, 2:34 of real Tesla Ep557 synthesized on the production
      voice and pushed through the chain shows the midrange flat
      (-0.1 dB) while the sibilance band (5.5-8.5 kHz) gains **+5.1 dB**
      and air (8.5-16 kHz) **+5.0 dB** — the 4:1 broadband compressor
      lifts consonants faster than vowels. Four variants (no de-ess /
      static -3 dB / static -5 dB / ffmpeg `deesser`) were rendered and
      **the operator listened: all four sound the same on this voice.**
      So the +5 dB is a measurement, not a defect, and the network ships
      the chain unchanged — adding a stage that buys no audible benefit
      but alters every episode on 15 shows is the landmine-#17 shape.
      Re-open only with listening evidence, not spectra.
    - **Final mix** (`engine/audio.py:_final_mix_cmd`) replaced the
      simple `amix` with sidechain-ducked music + EBU R128 loudnorm
      to **-16 LUFS** (Apple Podcasts / Spotify spec). Music
      automatically pulls down 8 dB when voice is present and rises
      smoothly when voice pauses. The fixed-curve `mix_with_music`
      music timeline still runs upstream to control intro / overlap /
      fadeout / outro volumes; the sidechain ducking adds the
      moment-to-moment dynamic response that makes voice + music feel
      cinematic instead of mechanical.
    - **Final encode** bumped from CBR 192 kbps to VBR `-q:a 0`
      (~245 kbps) for archival-quality spoken-word + music. ~6.5 MB
      per 30-min episode (was ~5 MB).
    - **Speech tags** are now allowed in podcast prompts (every
      `shows/prompts/*_podcast.txt` carries a `DELIVERY` block).
      Allowed: `[breath]`, `[pause]`, `[long-pause]`,
      `<emphasis>...</emphasis>`. Banned: every other Grok tag
      (`[laugh]` / `<whisper>` / `<slow>` / etc. — they sound
      performative). The TTS path keeps tags; every non-TTS consumer
      runs through `engine.utils.strip_speech_tags()` before publishing
      so blog markdown, RSS show notes, X teaser, and YouTube
      descriptions never see them.
    - **Drift guards:** `tests/test_tts_grok.py` now has
      `test_english_shows_resolve_to_custom_voice` (every English show
      including Tesla resolves to `kdif6sqjcyiq`),
      `test_no_show_uses_elevenlabs_in_production` (catches accidental
      rollback flips), and `test_russian_shows_use_grok_tts` (Olya
      voice unchanged).

    `ELEVENLABS_API_KEY` is **kept** in GitHub Secrets / `.env` for
    emergency rollback even though no show currently needs it. The
    legacy ElevenLabs settings in `_defaults.yaml` (model, stability,
    similarity_boost, style, etc.) are also preserved — harmless under
    `provider=grok` and a one-line YAML flip back to ElevenLabs if
    Grok TTS has an outage.

    **May 4 2026 update — speech-tag wrap simplified.** The chunk-
    send wrap was originally `<fast><build-intensity>...</build-intensity></fast>`
    (PR #293). Whisper transcripts of UC Ep001 ("Build intensity." at
    line 3 + "build intended to dig" at line 127) and Tesla Ep461 (line
    112) showed Grok occasionally **speaking** "build intensity" out
    loud instead of consuming the tag — `<build-intensity>` was never
    in Grok's documented tag list. Wrap simplified to `<fast>...</fast>`.

    **May 11 2026 update — chunk wrap dropped entirely, programmatic
    `<emphasis>` injection added.** M&A Ep045 transcript caught Grok
    voicing the opening `<fast>` aloud as "Fast." at section-TTS
    boundaries (twice — at "in its latest release. Fast. The updates…"
    and "make sense for their workloads. Fast. Okay, let's pop the
    hood…"). Verified against xAI docs: `<fast>` is **not** on Grok's
    documented tag list (only `[breath]`, `[pause]`, `[long-pause]`,
    `<emphasis>`, `<whisper>`, `<slow>`, `<soft>` are). The energy
    lift `<fast>` was supposed to provide was paid for in occasional
    audible tag leakage at every chunk boundary multi-section TTS
    creates. Wrap dropped to empty strings in both `engine.config`
    and `shows/_defaults.yaml`.

    Programmatic `<emphasis>` injection was added in the same PR
    (`engine/prosody.py:inject_prosody_tags()` wrapping currency /
    percentages / cashtags at script-save time) — and **paused the
    same day** (see below).

    The DELIVERY prompt block was also dropped from all 12 podcast
    prompts (`shows/prompts/*_podcast.txt`); 56 recent `_tts.txt`
    files showed the LLM was ignoring it (only 10 had any tags at
    all, never reliably). The block was paying prompt-token cost
    for no measurable audio benefit.

    Defense-in-depth: `engine.utils.strip_speech_tags()` is wired
    into RSS show notes (`engine/publisher.py:_markdown_to_rss_html`),
    newsletter body (`engine/newsletter.py:send_show_newsletter`),
    and YouTube metadata (`engine/video_metadata.py:_strip_markdown`)
    so any speech tag that enters the digest body is scrubbed before
    subscribers / readers / YouTube see it. Drift guard
    `test_default_tts_config_has_no_chunk_wrap` blocks accidental
    re-introduction of the chunk wrap.

    **May 11 2026 update (later same day) — pause all TTS
    modifications, run raw Grok TTS.** Operator A/B-listened to
    Planetterrian Ep060 and Fascinating Frontiers (with the phonetic
    respellings for "Planetterrian", "tissue", "neurodegenerative"
    active) against raw audio and concluded **every phonetic
    respelling sounded worse than the original word** on the custom
    voice `kdif6sqjcyiq`. Same call for the just-shipped programmatic
    `<emphasis>` injector — adding any modification risked regressing
    a voice that already handles these tokens naturally.

    Pause decision:
    - `engine/prosody.py` and its tests **deleted**. The
      `inject_prosody_tags()` call in `run_show.py` reverted.
    - Phonetic respellings (`tissue`/`Tissue`/`tissues`/`Tissues`,
      `neurodegenerative` and 3 case/inflection variants) **removed**
      from `shows/pronunciation_map.yaml`. The Planetterrian
      WORD_PRONUNCIATIONS entry was already removed in PR #355.
    - **Kept**: letter-by-letter acronym expansions in
      `shows/pronunciation_map.yaml` (`TSLA` → `T S L A`, `LLM` → `L
      L M`, `TFSA` / `RRSP` / `FHSA` / `RESP`, `HW4` / `HW5` / `AI5`,
      `MCP`). Those are NOT phonetic guesses — they're literal
      letter-spellings, and the operator-verified failure mode
      without them is Grok saying "lum" / "tezz-luh".
    - **Kept**: `<fast>` chunk-wrap removal + DELIVERY-block removal
      + `strip_speech_tags()` defense (those are removals of broken
      modifications + a no-op safety net, not modifications).

    Re-introduce ANY phonetic respelling or programmatic tag
    injection ONLY with A/B listen-test evidence on the custom voice
    that the modified audio is measurably better than raw on at
    least 3 different show contexts. Theory-driven "this should
    sound better" changes have a 100% regression rate on this voice
    so far (Planetterrian, tissue, neurodegenerative, `<fast>` wrap,
    `<build-intensity>` wrap — every one made it worse).

    **May 13 2026 update — `<fast>` wrap re-enabled via single-call
    synthesis.** Operator listened to the May 13 episodes (post-#365
    editorializing reduction + #366 audio retune + #367 streamline)
    and asked for whole-script `<fast>` energy on every podcast
    ("Option B for all podcasts please"). The historical chunk-wrap
    leak (M&A Ep045 voicing "Fast." at section-TTS boundaries) was
    a *multi-call* problem: section-TTS + chunked synthesis meant
    every chunk got its own `<fast>...</fast>` wrap as an
    independent Grok API call, and Grok occasionally voiced the
    opening tag aloud at the boundary between calls.

    Leak-safe implementation (the only safe path):
    - Network default `shows/_defaults.yaml`: `speech_wrap_open:
      "<fast>"`, `speech_wrap_close: "</fast>"`, `use_section_tts:
      false`, `max_chars: 14000`.
    - The four fields are a *coupled set* — flipping any one
      without the others re-introduces the leak.
    - `run_show.py:1714` gates section-TTS on `config.tts.use_section_tts`
      so the network-wide flip is one YAML field.
    - `engine/tts.py:_speak_with_grok` has a May 13 safety guard:
      if a script overflows `max_chars` and splits into multiple
      chunks, it DROPS the wrap (with a loud warning) rather than
      apply it per-chunk. Episode loses the energy lift but ships
      clean audio.

    Trade-off: section-TTS off means **no transition stings between
    chapter markers**. Chapter markers themselves still work in
    podcast apps (Apple, Spotify, Pocket Casts) because they come
    from `chapters.json` not from section-TTS. The brief musical
    stings between chapters are gone — most listeners won't notice;
    one-line revert (`use_section_tts: true` + drop the wrap) if
    desired.

    Drift guards in `tests/test_tts_grok.py`:
    - `test_default_tts_config_dataclass_has_no_chunk_wrap` —
      dataclass default stays empty (backwards compat for callers
      that bypass YAML).
    - `test_network_default_has_fast_wrap_and_single_call` — pins
      the four coupled fields on the loaded Tesla YAML so a partial
      revert (e.g. re-enabling section-TTS without dropping the
      wrap) fails CI.
    - `test_speak_with_grok_drops_wrap_on_multi_chunk` — verifies
      the safety guard fires when a script overflows.
    - `test_speak_with_grok_keeps_wrap_on_single_chunk` — verifies
      the happy path applies the wrap as expected.

    The policy above (no theory-driven tag changes) still stands
    for any FUTURE additions. The May 13 `<fast>` re-enable was an
    *operator override* with explicit awareness of the historical
    risk; it ships as a single coherent infrastructure change
    (single-call synthesis) rather than as a tag-injection retry.

18a. **Newsletter dark-mode CSS must stay SCOPED (v3, June 2026)** —
    the iPhone dark-mode bug (subject title, "NERRA NETWORK · date"
    byline, forward line, and unsubscribe footer rendering white-on-
    light = invisible; operator screenshots Jun 9 2026, after several
    failed fixes) was caused by GLOBAL selectors in the dark-mode
    `<style>` block (`h1 { color:#fff }`, universal `p/td/div/span`
    text flips, td-style-attribute background matches). Those rules
    leak onto **Buttondown's own wrapper**, whose backgrounds we cannot
    flip. v3 contract in `engine/newsletter_template.py`:
    `wrap_with_branding` stamps every emitted table/div with the `nn`
    marker class (`_scope_nn`), and every color rule inside the
    `@media (prefers-color-scheme: dark)` block is scoped under `.nn`
    (surface classes like `.surface-white` are ours alone and stay
    class-targeted). Buttondown chrome keeps its native always-readable
    colors; our cards adapt. The `:root/body { color-scheme: light
    dark }` opt-in stays — removing it regresses to Apple Mail's
    auto-transform (washed-out headings, the original May 2026 bug).
    Drift guards: `tests/test_newsletter_template.py::TestDarkModeScoping`
    (no unscoped color selectors, no attribute background selectors,
    every block carries `.nn`).

18. **Newsletter pipeline spec v2 (May 2026)** — multi-day refinement
    pass on the Buttondown send pipeline addressing contrast bugs,
    LLM scaffold leaks, and daily-vs-weekly template parity. Files:

    - **`engine/newsletter_sanitizer.py`** (new) — regex blocklist of
      known LLM scaffold patterns (`**HOOK:**`, `**Date:**`,
      `ЗАГОЛОВОК:`, `**The Surprising Truth:**`, box-drawing rules
      `━━━`, etc.) plus a hard tripwire (`assert_clean`) that blocks
      send if any pattern survives scrubbing. Run by
      `send_show_newsletter` before the wrapper sees the body.
    - **`engine/url_utils.py`** (new) — strips C0/C1 control chars
      from RSS-scraped URLs (the `?ito\x14` bleed), and resolves
      Google News redirect URLs (`news.google.com/rss/articles/CBMi…`)
      to their canonical publisher form at fetch time. Both ops are
      best-effort; failures pass through unchanged. Wired into
      `engine/fetcher.py`'s per-article loop.
    - **`engine/newsletter_body.py`** (new) — body-text transforms
      applied between scrub and wrap: box-rules → `<hr>`, Tesla
      `**REAL-TIME TSLA price:**` → styled stock-watch block, Russian
      vocabulary list (Привет) → card stack, Omni View "Read more"
      duplicate-URL dedup.
    - **`engine/contrast_validator.py`** (new) — WCAG 2.1 AA tripwire
      that walks rendered HTML, checks every inline `color:` against
      its nearest-ancestor background. Currently a soft warning in
      `send_show_newsletter` (logs but doesn't block) so we can
      calibrate against real renders before flipping to hard-block.
    - **`engine/newsletter_template.py`** — surgical template fixes:
      hero pill is now a `<table>` with `bgcolor` instead of an
      `rgba()` div (Outlook fix); cover `<img>` carries inline
      `color/font-size/font-weight` so alt-text fallback is readable;
      VML wrapper added for Outlook gradient fallback; dark-mode
      `<style>` block expanded with per-brand-color tokens
      (`.brand-text-tesla` / `.brand-text-mit` / etc.) and surface
      classes (`.surface-white` / `.card` / `.preheader`) to win the
      inline-style override war on Outlook iOS / mobile Gmail; light-
      mode `#94a3b8` / `#64748b` muted greys swapped for `#475569`
      where they appeared as primary text (3.0:1 → 6.4:1 on white);
      P.S. block re-styled with dashed top-border separator + italic
      body; cross-network show names are now full-row clickable
      links; new `_build_view_in_browser_html` partial at top of
      body and `_build_issue_counter_html` per-show counter just
      above Buttondown's auto-footer.
    - **`engine/newsletter.py:send_show_newsletter`** — full daily-
      caller overhaul. Subject line uses
      `build_subject_line(hook_max_chars=50, is_daily=True)` for the
      same `<hook> · <show> <emoji>` shape as weekly (replaces the
      broken `f"{config.name}: {hook}"`). Body is scrubbed → body-
      transformed → wrapped with the same hero / featured-episode /
      P.S. / cross-network / reply-share blocks weeklies use.
      Russian shows render the disclaimer and reply/share copy in
      Russian via the localised `_build_financial_disclaimer_html` /
      `_build_reply_share_html` paths. Buttondown ``slug`` is set
      explicitly for Russian shows using a GOST-7.79 Cyrillic→Latin
      transliteration map so archive URLs read as
      ``privet-russian-ep018-kosmos-9-russkikh-slov`` instead of
      ``u041f-u0440-u0438-…``. Same-day double-send guardrail: each
      show writes a `digests/<slug>/_newsletter_lastsend.txt` after
      a successful send; the next call refuses to re-send within
      20 hours (catches the May 2 Привет Ep 17 + Ep 18 double-send).
    - **`shows/prompts/omni_view_digest.txt`** — the "Read more
      (sources)" instruction now explicitly forbids three identical
      URLs under three different descriptions (the May 2 daily
      shipped with `[Daily Mail](https://...)` × 3). The
      `dedup_read_more_sources` body transform is the
      defense-in-depth layer.

    Operator workflow: nothing changes for the daily cron — it still
    calls `send_show_newsletter`. The added safety gates (sanitizer,
    contrast validator, send guardrail) are defensive — they log
    loudly when they fire so the operator can chase the upstream
    cause (a regressed prompt, a fetcher bug, or a scheduler race).
    The `ELEVENLABS_API_KEY` and legacy ElevenLabs settings in
    `_defaults.yaml` remain untouched — separate concern.

19. **Schedule overhaul + weekly-summary segment (May 2026; restructured
    July 2026)** — 7 shows moved to daily cadence (Omni View,
    Planetterrian, Fascinating Frontiers, Models & Agents, MAB, Modern
    Investing, Tesla; SpaceX joined later). Cron times shifted +1h across
    the board to widen the per-slot window; last show now finishes ~12 UTC
    (~8 AM ET). **July 2026 restructure:** the full Sunday weekly-recap
    mode was RETIRED. Sunday is no longer a special episode — every daily
    show runs a NORMAL daily episode every day, and shows with
    `weekly_summary_segment: true` (was `weekly_recap_on_sunday`) simply
    include ONE short "week in review" *segment* on Sunday. Mechanically:
    `_resolve_weekly_summary` in `run_show.py` gates on Sunday + the flag
    + not-a-deep-dive; when true, the daily digest generates as usual and
    `engine.weekly_recap.build_weekly_summary_segment` synthesises a
    compact host-instruction block from the past 7 days in the content
    lake. That block is appended to the **podcast-only** copy of the digest
    (`clean_digest`, after cleanup) — NOT to the published `x_thread` — so
    the host weaves a brief recap into the episode while zero instruction
    text reaches the blog / RSS / newsletter. A thin content lake (<2
    episodes in window) returns `None` → a plain daily episode with no
    segment. The retired full-recap machinery (digest short-circuit,
    daily-validator skip, and the recap "republish from clean narrative"
    step) is gone; the video recap-scene-reuse path in `_publish_youtube`
    remains as a dormant default-off capability. Prompt/audio-affecting on
    Sunday → A/B-listen per landmine #17. Modern Investing additionally has
    a Saturday "weekend mode" instruction in its podcast prompt covering
    international markets, crypto, lessons learned, and what to prepare for
    in the coming weeks. Drift guards in `tests/test_schedule.py` +
    `tests/test_weekly_summary_segment.py` pin: cron consistency, the daily
    shows carrying the weekly-summary flag, alt-cadence/narrative shows NOT
    carrying it, the segment shape/append point, and that the retired
    full-recap machinery does not return. The legacy `weekly_recap_on_sunday`
    YAML key is still read as a back-compat fallback in `engine/config.py`.

20. **YouTube quota cap (May 2026; four-show expansion June 2026)** —
    the YouTube Data API quota is 10,000 units/day **per channel**;
    each `videos.insert` costs 1,600 units (plus thumbnail 50 /
    playlist 50 / caption 400 on the paper model in
    `engine/youtube_quota.py`). The May 2026 schedule overhaul had
    disabled YouTube on every English show except Tesla and MAB
    (long-form + 2 Shorts each). **June 2026 expansion (operator
    decision, quota-increase request submitted and pending):**
    - Tesla + MAB dropped from 2 Shorts to 1 each.
    - Fascinating Frontiers + Modern Investing enabled **Shorts-only**
      (`publish_long_form: false`) on `@NerraNetwork`. Flip
      `publish_long_form: true` per show once the increase is granted.
    - Финансы Просто + Привет, Русский! enabled **full format** on
      `@NerraRU` (`channel: ru`, its own 10k/day quota; both run even
      days only ≈ 7,600 paper-units). Requires the
      `YOUTUBE_REFRESH_TOKEN_RU` secret — uploads no-op with a logged
      warning until it's set.
    EN channel paper-math now projects 11,000/day — the SAME paper
    level as the previous Tesla+MAB 2-Shorts config, which ran in
    production without quota failures (the documented-cost model is
    conservative vs. actual charging), so the daily preflight
    `::error::` annotation is expected until the increase lands.
    `estimate_network_daily_units` groups per channel since June 2026
    (a RU show never counts against the EN budget). Drift guards:
    `test_only_tst_and_mab_enable_youtube` pins the exact enabled set,
    `test_youtube_expansion_quota_shape` pins the 1-Short /
    Shorts-only / ru-channel shape so a partial revert fails CI.
    - **June 14 2026 — SpaceX Daily swapped in for MAB.** SpaceX Daily
      took MAB's EN-channel **full-format** slot (long-form + 1 Short);
      MAB's `youtube.enabled` flipped to `false` (rest of its block
      retained for a one-line re-enable). Same per-episode EN footprint,
      so the 11,000/day paper-math and the expected preflight `::error::`
      are unchanged. The EN full-format pair is now **Tesla + SpaceX**;
      FF + MIT stay Shorts-only; RU shows unchanged. `YOUTUBE_ENABLED_SHOWS`
      in `tests/test_schedule.py` updated accordingly. **All YouTube-enabled
      shows now generate imagery with Grok Imagine** (FF/MIT/RU previously
      inherited the `pexels` default → stock Shorts; now `image_provider:
      grok` is pinned, guarded by `test_all_youtube_shows_use_grok_imagine`).
      Operator one-time setup pending: create the SpaceX podcast playlist in
      Studio + flag it (landmine #15); uploads publish without it (warned).
    - **June 26 2026 — quota raised 10k → 200k; full-network rollout.** The
      @NerraNetwork quota increase landed, so the constrained shape above is
      undone (full rollout doc:
      [`docs/youtube_rollout_2026_06_25.md`](docs/youtube_rollout_2026_06_25.md)).
      `DEFAULT_DAILY_QUOTA` is now **200k**, env-overridable per channel
      (`YOUTUBE_DAILY_QUOTA[_EN|_RU]`, `resolve_daily_quota()`). **All 13 shows**
      publish to YouTube: FF + MIT flipped back to long-form, FPD added Shorts,
      MAB un-paused, and the 6 disabled shows (env_intel, planetterrian,
      omni_view, models_agents, models_agents_beginners, unintended_consequences)
      enabled with `image_provider: grok`. Tesla + SpaceX back to **2
      Shorts/episode**. EN steady state ≈ **24 uploads/day, ~45k units** (vs
      200k). Quota is no longer the constraint — **cadence is**: the preflight
      now warns (never blocks) above `SAFE_DAILY_UPLOADS_PER_CHANNEL` (default
      30, env `YOUTUBE_SAFE_DAILY_UPLOADS`), since YouTube's inauthentic-content
      policy penalises mass posting. Mitigations shipped same-day: LLM-optimized
      long-form titles separate from the spoken hook
      (`engine/youtube_titles.py`, `youtube.optimized_titles`) and the
      slideshow still-hold cap lowered 25 → 15 s for more motion network-wide
      (commit `6559b3a9`). None of these touch audio (outside landmine #17).
      **The hybrid Grok video-clip pilot on Tesla + SpaceX has since been
      REMOVED network-wide (commit `72d81cce`, June 29 2026): the Ep526 pilot
      showed ~1/3 clip success at ~$0.35/ep for the weakest payoff and pushed
      the render toward the 40-min pipeline timeout — the most expensive
      component for the least value (full Grok Video was already disabled
      June 23, commit `08021ebe`, as ~$40-50/ep). `video_clips_enabled` is
      `false` everywhere; motion now comes entirely from slideshow crossfades
      + varied Ken Burns over Grok Imagine stills. Recovery scripts
      (`scripts/recover_grok_video.py` et al.) still exist for any
      already-generated clips.** Enabled-set + 200k + 15 s cap pinned by
      `tests/test_schedule.py`, `tests/test_youtube_quota.py`,
      `tests/test_youtube_quality_pass.py`, `tests/test_config.py`. Operator
      one-time tasks: create/flag the 6 new shows' podcast playlists (landmine
      #15), confirm quota scope + set the env budget if EN-only, and enable
      Studio Title/Thumbnail "Test & Compare" (the runner stashes 3 title
      candidates).

21. **`min_articles_skip` is tuned per-show, not per-network (May 2026)**
    — `engine/config.py` defaults `min_articles_skip` to `3` (a show
    skips that day's run if fewer than 3 fresh articles survive
    fetch + dedup). The default is a deliberately weak floor; every
    show that needs a different threshold pins it explicitly in its
    YAML. Current pinned values:

    | Show | `min_articles_skip` | Rationale |
    |---|---|---|
    | `tesla` | 6 | Largest property; six-segment digest needs density. |
    | `omni_view` | 4 | World-news scan; below 4 the digest reads thin. |
    | `fascinating_frontiers` | 4 | Space/science; needs multiple beats. |
    | `models_agents` | 4 | AI news firehose; sub-4 means a quiet day → skip. |
    | `finansy_prosto` | 4 | Russian financial news scarcity → wait for a real day. |
    | `modern_investing` | (default 3) | Markets always produce 3+ stories on a weekday. |
    | `env_intel` | 2 | Alt-cadence (odd weekdays); 2 substantive stories enough. |
    | `models_agents_beginners` | 2 | Re-uses M&A pool; lower bar OK because tone is explanatory. |
    | `planetterrian` | 2 | Science/longevity/health show (NOT local news — that description was stale); primary-research days can be thin, so 2 is the realistic floor. |
    | `privet_russian` | 1 | Bilingual lesson show; one solid theme is sufficient. |
    | `unintended_consequences` | 0 | Narrative show — articles aren't the input, topic queue is. |
    | `first_principles` | 0 | Narrative show — topic queue is the input (alternates concrete example / opportunity area). |

    **Landmine:** changing the default from `3` would silently
    re-tune four shows (the ones currently pinned at `4` would still
    pass; the ones below `3` rely on the explicit override winning).
    Always change the per-show YAML, not the default. The
    `unintended_consequences` value of `0` is load-bearing — that
    show pulls from `shows/topic_queues/unintended_consequences.yaml`
    and never fetches news; raising it would block every episode.

22. **TSLA price source: multi-source fallback chain (May 2026)** —
    `shows/hooks/tesla.py:_fetch_tsla_price()` tries three sources
    in priority order until one returns a quote that passes
    validation:

    1. **`yfinance.Ticker.history(period="5d")`** — primary.  Same
       library + endpoint Modern Investing uses successfully every
       weekday.  yfinance manages a cookie + crumb-token session
       against Yahoo internally, which Yahoo's anti-bot trusts.
    2. **`yfinance.Ticker.fast_info`** — secondary.  Adds the live
       pre / post-market price when `history()` alone gives only
       end-of-day closes.  Treats `0.0` as falsy (the historical
       degraded-response failure mode) so it falls through cleanly.
    3. **Direct HTTP to Yahoo v8 chart API** — last resort.  Works
       locally and from some egress IPs but the bare `requests.get`
       call (no session cookies / no crumb token) is observed to
       return non-200s from GitHub Actions runner IPs at times.

    Each source returns `(price, prev_close, market_state)` or
    `None`; the same validation (`$200–$1500` sanity band, 25%
    deviation guard) gates every source, so a single bad source
    can't ship a wrong number.

    The `api/tsla.json` cache the hook writes is the single source
    the website's primary path reads.  Cache file records
    `"source": "yfinance_history"` / `"yfinance_fast_info"` /
    `"yahoo_v8_chart"` so the management dashboard can tell at a
    glance which path is winning — and notice if the primary has
    been silently failing for days.

    **Three prior fetchers failed and were superseded:**

    - **yfinance `fast_info` only (early 2026):** operator caught
      it repeatedly returning `$0.00 (price unavailable)`.  The
      `or` chain treated `0.0` as falsy and fell through every
      fallback to no data.  See git blame on commit `3247317`.
    - **Grok `x_search` (May 1–18 2026):** queried X for the latest
      `$TSLA` cashtag post.  Failed twice within 48 h.  TST Ep473
      (May 15) returned $250 vs a real ~$444 (Grok pulled from a
      stale post — caught by the deviation guard).  TST Ep474 (May
      16) returned `price == prev_close == $415.50` because the X
      post Grok latched onto only quoted a single number (caught
      by the operator).  X posts are not an authoritative quote
      source.
    - **Direct Yahoo HTTP only (PR #385, May 18 2026):** worked
      locally but Ep477 (May 19) + Ep478 (May 20) both shipped
      `(price unavailable)` on GitHub Actions.  Bare `requests.get`
      doesn't carry the cookie + crumb session yfinance manages,
      and Yahoo's anti-bot apparently treats GHA egress IPs
      differently for unauthenticated v8 calls than for
      session-managed yfinance calls to the same endpoint.

    **Subtle previous-close bug fixed at the same time:** the
    direct HTTP source originally read `meta.chartPreviousClose`
    as previous close.  That field is the close BEFORE the chart's
    range window (so for `range=5d` it's the close from 6 trading
    days ago — `$445.27` on 2026-05-20 vs the correct
    `$404.11` for yesterday).  The HTTP source now reads
    `indicators.quote[0].close[-2]` (the bar immediately before
    the latest), which mirrors what `yfinance.Ticker.history()`
    returns.  Meta fields are only fallbacks for null bar data.

    **Sanity band:** prices outside `$200 – $1500` are rejected.

    **Dynamic deviation guard:** new prices that swing more than
    25% from the last cached close are rejected.  Load-bearing
    under the Grok fetcher; kept on the multi-source chain as
    defence-in-depth (any single source's bad day still gets the
    chain to fall through to the next).

    **`yfinance` is now also the primary** — it remains required
    for Modern Investing's trade-execution pricing across many
    tickers, and now powers Tesla too.

    **Drift guards:** 31 unit tests in `tests/test_tesla_hook.py`
    pin per-source happy paths, chain fall-through semantics
    (source 1 fails → source 2 tries; source 1 + 2 fail → source
    3 tries), validation rejection forcing fall-through to the
    next source, `marketState: null` rendering as REGULAR (not
    After-hours), and persistence (success writes, failure does
    NOT overwrite the previous-good cache).  Plus the
    `test_bar_close_array_is_authoritative` guard explicitly
    pins the HTTP source on `indicators.quote[0].close[-2]` over
    `meta.chartPreviousClose`.

### Report the sourced news, never discard it (Oct 19 2026)

Operator-directed (register `report-more-sourced-news-2026-10-19`; guards
`tests/test_report_more_sourced_news_2026_10_19.py`). Measured Oct 13-19: a
show fetched 50-480 articles, the prompt listed at most 40 of them, the digest
carried 6-15 items (8-25% of the list), and the prompts said why — "prefer
fewer stories at full depth", "7 stories properly, not 12 shallowly", the
desks' "3 to 5" Also Today cap — so the rest of a sourced day was cut before
anyone heard it. Rules that bind: **every news digest carries an Also Today
run** (`shows/prompts/_shared/also_today.txt` on 14 digest prompts; the desks'
own section is uncapped now; MAB's Quick Bits and MIT's Quick Hits are the same
run under their names; Top World's items 6-10 already are) — one sentence per
remaining qualifying story, the count follows the day, omitted under two, and
a story that earns only a sentence goes THERE rather than being dropped (the
depth lines and the expansion retry say so; the selection tests still apply,
so a birthday or a price move does not qualify). The run is spoken as a brisk
run after the last developed story (`content_discipline.txt`; ⚠️ AUDIO —
A/B-listen one flagship and one desk) and chaptered on its digest section.
**The prompt lists `DEFAULT_MAX_PROMPT_ARTICLES` (60) articles**
(`ShowConfig.max_prompt_articles`; the literal 40 is gone). The run sits
outside every developed section's validator span, so item floors still
measure developed items. Readout: `articles_in_prompt`, `items_shipped`,
`digest_also_today_items`, `prompt_articles_reported_pct` per episode;
`prompt_articles_reported_pct_7d` / `also_today_items_7d` on the dashboard.

### The front page's ticker is live (Oct 19 2026)

Operator: the ticker should carry live content, stocks and headlines (on a
Monday at noon the strip still printed Friday's closes). Guards
`tests/test_live_ticker_2026_10_19.py`, `workers/gallery/test/markets.test.ts`;
register `live-ticker-2026-10-19`. Rules that bind: **`GET /api/markets` on the
gallery Worker** (`workers/gallery/src/markets.ts`) fetches Yahoo's chart API
server-side for a CLOSED list (`MARKET_SYMBOLS` = `engine.newsroom.MARKET_TICKERS`
+ SPCX, drift-guarded), caches one body a minute while the session is open (ten
minutes otherwise) and keeps a two-day last-good copy that fills a refused
symbol — **an old quote is never "live"**; `as_of` is the quote's own time;
the previous close is the last bar dated before the quote's day, never
`chartPreviousClose` (landmine #22). **`assets/js/live-ticker.js`** updates the
strip and the flagship quote lines from it (`data-live-markets`,
`data-symbol`; "Live · 12:21 PM ET" only when the Worker says the regular
session is open, else "Close · <date>"), re-reads the page's own newest build
for the Latest headlines (`data-live-headlines`, every
`LIVE_HEADLINES_REFRESH_S`; the RU/FR hubs too), and moves an overflowing row
by advancing its own scroll (still swipeable) — paused on hover, focus, touch,
its Pause button and a hidden tab, never moving under reduced motion, copies
`aria-hidden` and out of the tab order. Network data is written with
`textContent` only. The printed build-time values stay whenever the Worker does
not answer. Operator: `wrangler deploy` in `workers/gallery`.

### The voice marks a story change; the music swell is gone (Oct 20 2026)

Operator listen: the Oct 14 music interludes between stories are not wanted
(register `story-tags-and-map-2026-10-20`; guards
`tests/test_story_tags_2026_10_20.py`). Measured first, on Tesla Ep639 and
Vancouver Ep027 against NPR's hourly newscast and Up First with the same
pitch-and-pause analysis: **a human newsreader does not pause longer between
stories than between sentences** (0.5-0.7 s either way on NPR; one pause over
0.7 s in the whole cast) and marks the change with the VOICE — a +2..+8 Hz
lift opening an ordinary sentence against **+34 Hz** opening a new segment,
and a firmer landing on a segment's last words (−30 vs −18 Hz). Grok TTS on
the custom voice lifts ~+20 Hz at every sentence and the same at a story
change, and lands identically at both — so nothing in the audio told a
listener a story had changed, and the Oct 13 pause and the Oct 14 swell
(**13 swells** in nine minutes on Tesla, 5-10 dB under the voice after
loudnorm, 11 of 13 between items inside one section) were treating the
symptom. Post-processed pitch shaping (rubberband on the first second of
each story) was rendered and REJECTED by the operator: it robotises the
onset. A separate TTS request per story was measured on UC Ep143 and gives
no fresh start (+23 Hz onset, −11 landing — a sentence's numbers). Rules
that bind: **`audio.story_break_cue` is false network-wide** (the code
stays for a per-show opt-in; the 1.0 s beat is unchanged); **the voice
marks the boundary with Grok's own tags, inserted in code before synthesis
at the SAME boundaries `story_breaks` finds** (`engine/story_tags.py`,
`tts.story_tags` / `story_tag_open` `[breath]` / `story_tag_close`) so the
committed `*_tts.txt` is what was spoken; **the landing tag ships EMPTY until
Actions "Probe TTS tags" (`scripts/probe_tts_tags.py`, read-only, attaches
the WAVs) shows which pitch tag this voice consumes without speaking it** —
xAI's own tag tables did not render, the code's May list says `<low>`,
Telnyx says `<lower-pitch>`, and an unknown tag is spoken aloud; **every
Whisper match reads the tag-stripped script** (story_breaks anchors, chapter
alignment, the spoken-text gate — a `[breath]` at a line's opening is not in
the audio); **THE MAP**: `build_cold_open_spec` asks for ONE sentence after
the identity line giving the shape of the episode (the two or three stories
after the lead in order, then recurring segments by name; no count, no
number, no promise language, never the lead again, never yesterday's
shape) — a map, not a tease, de-seeded by shape. `script_hook_leads_body_pct`
reads lower by design on map shows (the map sits in its three-sentence
window). ⚠️ AUDIO on every English show — A/B-listen the first slate; read
`story_tags_inserted` beside `story_breaks_inserted` and
`tag_leaks_by_pattern` for `breath` / `pitch-tag`.

**Oct 20 2026, the first slate — the breath is OUT.** The operator heard the
`[breath]` at every story start as "way too prominent" on the custom voice
(the probe had measured it as the cleanest tag; a measurement is not a
listen). Now `tts.story_tags: false` with an empty opener, **no
breath-family tag reaches synthesis whoever wrote it**
(`engine.utils.strip_breath_tags` — `[breath]` / `[inhale]` / `[exhale]` /
`[sigh]` — in run_show before the `*_tts.txt` save, in
`scripts/resynthesize_episode.py` on the committed script, and on the
multilingual stage's translation input), and `[breath]` left the delivery
spec's sanctioned set. The 14 episodes that aired with it are repaired by
re-synthesis from their committed scripts through Actions "Re-synthesize
Episode" (same R2 key, feed item kept; the tool strips the tags from the
script first); their long-form videos and the Nerra Daily edition of the
day keep the old audio. The map sentence and the no-music beat stay.
**A chapter marker never fires on the identity line or the map sentence
after it** unless it is a `start` marker (`engine/chapters.py` — the map
speaks the segments' anchor phrases, and SpaceX Ep136's "later the
engineering angle" titled The Engineering Angle at 11 s while the real
deep dive fell back to its digest heading). `engine/story_tags.py` and the
probe remain for the next candidate, and a candidate is LISTENED to on a
shipped episode before it ships to a slate. **The repair tool never moves a
feed item** (same day, found on the first fourteen repairs): it had rebuilt
the enclosure from `publishing.base_url` — the SITE, a 404 on every repaired
feed — put the MP3 in `<link>` where the blog page belongs, and minted a new
GUID, which every app reads as a new episode to download again. Now
`read_published_item` carries the enclosure URL, link and GUID and
`refresh_rss_item` writes them back verbatim (`keep_existing_guid`); the
workflow commits the stripped `*_tts.txt` and the shifted `.vtt` too. The
audio at the R2 key was right the whole time (the edge cache serves the old
object for a while — read `cf-cache-status` before calling an upload
missing); guard `TestRepairNeverMovesTheFeedItem`.

### The Oct 21 slate: what a listener heard wrong (Oct 21 2026)

Review [`docs/reviews/slate_review_2026_10_21.md`](docs/reviews/slate_review_2026_10_21.md);
register `slate-2026-10-21`; guards `tests/test_slate_2026_10_21.py`. Rules
that bind: **a bare clock time never gains a half of the day the text did not
give** (`replace_times` — "4:53 in the afternoon" had aired as "four
fifty-three A M in the afternoon"); **the first chapter starts at 0 and no
later chapter starts on the identity line or the map sentence** (the map names
the stories, so headline anchoring took it on six episodes); **a structural
retry that folds a retold story into nothing is rejected**
(`story_clusters.dropped_clusters` — Tesla Ep641 lost the Tesla–SpaceX merger
story); **a shared link is not a shared story** — the shared-URL dedupe reads
the items' words without their links, and two titled items with unrelated
headlines are never one story by link alone (MAG 7 Ep029 aired an item its
digest had dropped); MIT's index line says "since the practice portfolio
opened", never "since the record began"; the Also Today readout records on
every show. Prompt changes (⚠️ AUDIO): the map is at most three stories on a
news show and its own shape on a narrative show; an outlet shared by
consecutive stories is named once for the run; UC's cold open comes from the
sources; Longevity states an evidence level once per intervention; Omni View's
teaser never repeats a told fact; Tesla has no Counterpoint without a Short
Spot. Six corrections filed (UC 149, FPD 137, SpaceX 137, MIT 207, AI Chips
30, FF 229). Operator: the closing still carries three to six asks.

### The Oct 22 slate: the catalog writes, lead stories stay in the record (Oct 22 2026)

Review [`docs/reviews/slate_review_2026_10_22.md`](docs/reviews/slate_review_2026_10_22.md);
register `slate-2026-10-22`; guards `tests/test_slate_2026_10_22.py`. Rules
that bind:

- **A catalog write that sets only some columns is a PATCH, never an upsert.**
  PostgREST runs an upsert as an INSERT first, so NOT NULL is checked before
  the merge, and every runtime write failed (HTTP 400, 23502). Each write in
  `record_run` stands alone; the articles never ride on another write's
  success.
- **A section told as one prose story is an aired item** (`kind: section`):
  `### Top Story`, `### The Big Story` and every deep dive. The lead section
  is titled by the hook. `_STRUCTURAL_SECTIONS` lists the sections that
  schedule, list or argue about another story, and those are never stories.
  `AIRED_SCHEMA` 3 re-migrates every tracker.
- **MIT's era record is the AVERAGE trade** (parallel $1,000 positions, never
  compounded). It is spoken with its dollar total. A reviewed trade is called
  "earlier" when a newer one has closed.
- **A model name is not a range** (`Llama-3.1-8B`).
- **Outside 09:30-16:00 ET, SpaceX's `fast_info` price equal to history's last
  close is that close.**
- **13F holdings notices never reach a prompt.**
- **An Elsevier PII dates its article; URL parentheses are percent-encoded.**
- **A numbered bold headline loses its number** before it becomes a chapter
  or a scene.
- **`setup-python`'s apt install retries inside 900 s.**

Operator: re-dispatch SpaceX multilingual, then "Story Catalog" `full: true`.
⚠️ AUDIO: MIT's record line.

### The Oct 23 slate: a billing stop, a dead mirror, and the catalog's aired flag (Oct 23 2026)

Review [`docs/reviews/slate_review_2026_10_23.md`](docs/reviews/slate_review_2026_10_23.md);
register `slate-2026-10-23`; guards `tests/test_slate_2026_10_23.py`. 4 of 21
shows published: the xAI account ran out of credit at ~09:45 UTC (11 runs,
every producer-inbox run) and the Ubuntu mirror served nothing for 15 minutes
to six setups. Rules that bind:

- **The mirror is the last resort** (`.github/actions/setup-python`). The
  .debs a run downloads are cached per runner image and every later run
  installs them `--no-download`. When apt still cannot finish, ffmpeg comes
  from the pinned BtbN 8.1.3 build `test.yml` runs on (the guard keeps the
  tags equal). `setup-ffmpeg` has the same fallback.
- **A lake re-store keeps the story ids it did not change**, and run_show
  re-assigns after its second write. A catalog article is aired when an
  aired item carries its URL, story id or not (essays included). It had
  read 0 on every run.
- **A query string that names the page stays in the dedup key** (`id`, `v`,
  `p`, `prid`, `doi`, …). Every PLOS One paper had shared one key.
- **Mira's T-2h reminder checks the xAI account**
  (`fire_interviews.xai_credit_stop`, the `engine.provider_quota` matcher). A
  billing stop alerts Patrick by Slack and email with the guest and the time.
- **The video sweep restarts a handoff whose one run died before "Render and
  publish the video" started** (`scripts/video_job.retryable_titles`). Any
  other failed run is still re-run by a person.
- **Past the hold, the Nerra Daily gate waits for a re-run.** Ep064 shipped
  6 of 15 segments: the first re-run to land woke the gate while nine were
  still generating. A missing roster show whose run started after the hold
  and has not reached its own `if: always()` wake step is waited for
  (`engine.daily_edition.rerunning_shows`); the last re-run builds the
  edition. A morning straggler is not, so 7:00 ET is unchanged; an
  unreadable Actions API decides as before.
- The Cloudflare account is on Workers Paid (operator, Oct 23).

### Covered means aired, and a story catalog (Oct 21 2026)

Operator-directed (review
[`docs/reviews/content_lake_and_story_catalog_2026_10_21.md`](docs/reviews/content_lake_and_story_catalog_2026_10_21.md);
design [`docs/story_catalog.md`](docs/story_catalog.md); register
`story-catalog-2026-10-21`; guards `tests/test_story_catalog_2026_10_21.py`).
Measured first: the tracker recorded the whole PROMPT list (up to 60
articles) as covered — 63-75% of ALREADY-COVERED notes cited stories that
never aired, about one tracker URL in five had aired, and an unused article
was blocked for 45 days; the lake CI rebuilds held no headlines, so the
cross-show block read "none" on all 23 prompts every day. Rules that bind:
**`engine/aired_items.py` is the one reader of "the stories a digest told"**
(the shapes `story_item_count` counts; a narrative episode is one `essay`) —
the tracker, the lake and the catalog all use it. **The tracker records what
aired**: `record_episode(record_aired=False)` on the first draft records its
sections and the listed articles (`listed_urls`, blocked
`LISTED_URL_BLOCK_DAYS` = 2); the aired stories are recorded once the final
digest is on disk; a pre-Oct-21 tracker migrates itself once from the
committed digests (`migrate_to_aired`, `aired_schema: 2`). **Story ids come
from `engine/story_catalog.py`**, deterministic (date, show, episode, item),
strict across shows (three shared words; network- and show-common words
ignored; a core check stops drift; an essay is its own story); the lake
stores them in an `items` table (`rebuild_story_ids`, `query_items`,
`story_timeline`, `search_items`). **The cross-show block names only today's
articles a sibling told in two days and asks for this show's angle, never
silence** (`engine/cross_show.py`, metric `cross_show_matches`). **The story
catalog is `catalog_*` in the nerra-voices Supabase** (`engine/catalog.py`,
migration applied Oct 21): a show run writes its episode and every article it
fetched after the audio-first publish (`story_catalog` metric; never blocks);
Actions "Story Catalog" (05:23 UTC; `full` for the first fill) re-copies three
days from the lake, prunes unaired articles past 90 days and writes
`api/story_catalog.json` (multi-show and developing stories, retelling by
show, corrections with the other episodes that told the story, and
`missed_stories` — null when unreadable, never 0). **Books never print a
corrected error** (`validate_chapter_corrections` in `build_epub`); themed
material comes from `scripts/catalog_dossier.py`; specials get a
`prior_coverage.md` (never a source). Word matching misses synonyms — embeddings
are the next step and a new model call (operator). ⚠️ AUDIO — the digest input
changes on every news show: A/B-listen Tesla, SpaceX and one desk. Operator:
dispatch "Story Catalog" with `full: true` after merge.
