# Network review — 2026-10-01: the first post-merge slate, the cohort on every surface, and the trust surfaces

Operator brief (2026-10-01): review the quality improvements of Sep 30 and
decide whether more is needed for the shows to be the most compelling,
accurate and trustworthy delivery they can be — so that people keep
listening, subscribe, and review on the platforms they use; align the website
to every change and carry the new shows through every surface (Mission
Control, Nerra Personal, all of it); keep building a high-trust,
high-interest network for a diverse audience.

Ledger: `docs/reviews/ledger/network.yaml` (2026-10-01). Register:
`frame-memory-wired-2026-10-01`, `story-clusters-2026-10-01`,
`platform-ask-2026-10-01`, `apple-ratings-instrument-2026-10-01`,
`vtt-transcripts-2026-10-01`, `launch-cohort-newsletters-2026-10-01`.
Guards: `tests/test_story_clusters_2026_10_01.py`,
`tests/test_top_world_sources_2026_10_01.py`,
`tests/test_trust_retention_2026_10_01.py`,
`tests/test_transcript_vtt_2026_10_01.py`,
`tests/test_apple_ratings_2026_10_01.py`,
`tests/test_op3_unindexed_2026_10_01.py`,
`tests/test_worker_show_tags_2026_10_01.py`,
`tests/test_web_trust_2026_10_01.py`, plus the real-config case added to
`tests/test_repetition_pass_2026_09_30.py`.

## 0. Verdict in one paragraph

The Sep 30 pass did what it claimed on the half the operator could hear
first: transcripts are back on every episode, no undated article reached a
prompt on 18 of 19 news shows, the stale gate fired six times on real stale
items, and the combined scripts lost five second tellings in a day. It did
not do one thing it claimed: the frame-memory block rendered empty on all
seventeen opted-in shows because the builder read an attribute only its
test double had. The day also exposed two defects the Sep 30 pass could not
have seen — Top World losing eight Source lines to the absence filter, and
Tesla telling one Model 3 story five times because eight outlets each got
their own digest item — and both are code now. On the site, the generated
surfaces already carried the thirteen new shows; the three places they were
missing were the ones a visitor and a member hit first (the newsletter tag
the Worker dropped, the audience cards that could not say "not indexed",
and the directories none of them had been submitted to). On trust, the
network had the strongest verification pipeline in its class and said so
nowhere a listener looks: seventeen closings asked for nothing, the feed
transcript tag pointed at a file no app reads, no email asked for a rating,
and the YouTube descriptions cited no source.

## 1. Readout — 2026-10-01 against 09-30

Every 10-01 episode post-dates both merges; every 09-30 episode pre-dates
them (last 09-30 commit 15:48 UTC; merges 16:55 and 17:26). Twenty shows
published; UC skipped on its own claims gate (section 4).

| Measure | 09-30 (before) | 10-01 (after) |
|---|---|---|
| Episodes with a Whisper transcript | 0 / 19 | 20 / 20 |
| `spoken_text_gate` | `no_transcript` on every row | `pass` on every row (M&A `retry_pass`) |
| `articles_undated_in_prompt` | not recorded | 0 on 18 / 19 news shows (Peptides 2) |
| Page-date probe | — | hit the 12-page cap on 11 shows; 93 of 200 probed pages yielded a date |
| `articles_dropped_stale` firings | 2 (Asia Pacific) | 6 (MAB 2, AI Chips 3, Europe 1) |
| Combined generation engaged | 10 / 19 | 14 / 20 |
| Second tellings stripped | — | 5 sentences across 5 combined episodes (Tesla 1, SpaceX 3, MAG 7 1) |
| `script_repeated_facts`, 19 paired shows | 46 | 38 |
| Claims in ledgers, network sum | 164 | 205 |
| Pre-strip gate failures / sentences stripped | 5 / 5 | 4 / 3 |
| Frame-memory block rendered | n/a | "" on 17 / 17 (defect, section 2) |
| Structural-retry lint guard fired | n/a | 0 (never needed) |

Flagship script overlap moved the right way where combined generation
engaged (SpaceX 47 → 20 %, FF 63 → 13 %, M&A 73 → 34 %) and the wrong way on
Tesla (42 → 59 %) — the Model 3 story, section 2. Listener read of seven
10-01 scripts: no datable old story anywhere (every dated Source path is
2026-09/10); second tellings on Tesla (×5), SpaceX (Needham run rate ×2,
orbital-compute specs in the news block and again in the deep dive), FF
(Crew-13 ×2) and M&A (DEdit speedup ×2); one self-narration ("in the item
CBC published", Vancouver); Planetterrian bridged seven stories with the
same "From X to Y." shape inside one episode.

## 2. Three defects the slate exposed, and what is code now

**Frame memory was a no-op.** `build_recent_frames_block` read
`config.output_dir`; the real `ShowConfig` keeps it on
`config.episode.output_dir`, so the block was `""` on every opted-in show
and the Sep 30 guard passed on a fake config. Re-running the builder with
the right directory, the block each 10-01 episode WOULD have received names
the frames the review found (FF "On a different note" 5/6, OV "If you want
to" 6/6, MAB four openers at 3/6, PM two at 3/6), and six banned-frame
sentences shipped that day. Fixed; the guard now loads `shows/omni_view.yaml`
and points its episode directory at a fixture. Playbook rule added: a
wiring guard renders through the real config object, never a stand-in.

**Top World shipped 8 of 10 items without a Source while the lint said 0.**
The Actions log for the run settles it: "Removed 8 absence sentence(s) from
the digest." The model joined each item's reader-only `Ranks:` clause and
its `Source:` line on ONE line; the prompt asks the ranking clause to say
"two words" where the item cannot support it ("no figure given"), so the
clause reads as an absence sentence, the line had one sentence, and the
absence filter dropped it — URL included. The lint ran before the filter,
so the published metric was true of a text that never shipped. Now: a line
carrying a URL or a Source tail is never dropped whole (the citation stays,
the clause goes), `Ranks:` lines are structure, and run_show re-reads the
lint on the shipped text (`items_without_source_shipped`, with a warning
when it disagrees with the pre-filter read).

**Tesla told the Model 3 refresh five times.** Ep622's digest carried the
story as eight of seventeen items — InsideEVs on the China screen and V2L,
Electrek on the same, drive.com.au and The Driven on the Australian price
cut, driveteslacanada on the headliner, a Reddit NZ post — and the script
followed the digest. The cross-section dedupe is blind to this: each outlet
is a different angle, so headline and body vocabulary overlap stayed at
0.10–0.38 against a 0.5 threshold. "One story = one item" is a prompt line
the model breaks. The lever is the Fort Bend shape, upstream of generation:
`engine/story_clusters.py` clusters the fetched list on salient title and
teaser tokens, with the show's furniture filtered against the tracker's
45-day headline window so "tesla", "starship" or "language models" can never
join two stories, and every later member carries an inline SAME-STORY note
(one item, fold the angle in, cite both URLs). Nothing is dropped. Calibrated
on four shows' last four days of tracker headlines: every proposed cluster
was a real same-story pair once the window filter was in (the one false
join, two arXiv titles on "language models", is exactly what the window
removes). Outcome metric `story_clusters_retold_in_digest`; opt-in on the
22 shows that already run story recurrence.

A script-level stripper for repeated numeric facts was prototyped on the
10-01 scripts and REJECTED: it found the real re-tells (SpaceX 49/52/56,
Tesla 96/99) and also the hook-then-body restatement every cold open relies
on (Tesla [6]←[0], FF [4],[5]←[0]). The digest-side cluster is the lever;
read it before adding a stripper.

Two spoken-text defects from the same read, both fixed in the TTS text
path: the emoji strip's "enclosed chars" range (U+24C2–U+1F251) spanned
Hangul and every CJK block, so 디지털투데이 vanished and Ep622 aired
"  reported the patent suit exposure…"; the prompt now lists a non-Latin
outlet by its domain stem too ("Digitaltoday"). "Another r/teslamotors
thread" aired as "Another the teslamotors subreddit thread"; any determiner
suppresses the article.

## 3. The thirteen new shows on every surface

The surface audit found the generated site, nav, explore, footer, feeds
list, sitemap, llms.txt, hubs, blog hub, Personal pickers (Python + Worker +
pages), promo rotation, daily audit, review rotation, trackers and memory
all carry the cohort — every one of them derives from the registry or the
shows glob, so a fourteenth show inherits them. The gaps were the three
hand-maintained or data-derived ones:

- **The Worker's `SHOW_NEWSLETTER_TAGS` had none of the thirteen** — every
  cohort show page offered a per-show signup whose tag the Worker silently
  dropped (and two established tags, DP Pod's short YAML tag and Nerra
  Voices, were missing all along). Fifteen tags added; a guard reads the
  TypeScript against every show YAML. The cohort newsletters are ON (the
  forms were already live); operator: `wrangler deploy` in
  `workers/gallery`.
- **OP3 omitted an unindexed feed with no marker**, so the audience
  headline read `shows_measured: 16` and Mission Control showed "—" with
  nothing to distinguish "not indexed" from "no listeners". The fetcher now
  writes `resolved: false` (the language-feed loop's contract), every
  consumer tolerates it, the headline lists `shows_unindexed`, and the show
  card says "not indexed".
- **None of the thirteen has been submitted to any directory.** The tracker
  had 17 rows and Mission Control read Apple and Spotify at 100 %. Rows
  added (all `--`), feed URLs listed, and the submission order written down:
  Podcast Index first, because OP3 resolves feeds through it and that is
  what turns measurement on. (Shipped in #1323.)

Also: two topic hubs the cohort had no home in (`prediction-markets`,
`ai-infrastructure`), gated by the 12-episode floor and self-enabling within
days; `local-news` turns on at 12 by itself.

## 4. Trust and retention — what listeners and readers now get

| Surface | Before | Now |
|---|---|---|
| Spoken closing | 7 shows asked for a rating or subscribe; 11 English shows + 6 desks asked for nothing; no closing said "follow" | one sentence on alternate days, follow and rate alternating, only where the closing carried no ask; Russian on Финансы Просто (A/B-listen) |
| Feed item | `podcast:transcript` → raw Whisper JSON (no app reads it) | WebVTT first, JSON kept; 1,972 VTTs and 30 feeds backfilled; Apple can show the transcript |
| Feed channel | no `itunes:type`, no `podcast:guid`, author "Patrick" on 16 feeds | episodic, UUIDv5 guid, "<author> · Nerra Network" |
| Show notes | an ask on SpaceX only | network-default rating ask from each show's next episode (Russian on FP) |
| Newsletter | no rating ask; the AI-host branch would have crashed on first send | rating line to the show's own Apple/Spotify pages; branch fixed |
| YouTube description | "Subscribe" linked the website; no sources; "curated by Patrick" on Mira shows | channel subscribe link, Sources line, AI-host disclosure |
| Shorts comment / X follow | "daily episodes" on weekly shows | the registry's cadence word |
| Promo rotation | "puts real builders on the phone" | the narrow basis (guest decides publication) |
| Blog post | Sources, chapters, transcript; no claims ledger, no corrections mechanism, two contact addresses | verified-claims panel from the committed ledger, provenance line, report-an-error link, dated corrections box, one address (section 5) |
| Measurement | Apple ratings read nowhere | nightly `api/apple_ratings.json` + a Mission Control tile; 10-01 baseline: 4 ratings across 15 shows |

The platform ask is the one audio change; it lands after the sign-off in
the slot the YouTube call-out already uses. A/B-listen the first two
episodes of one Omni desk and AI Chips.

## 5. Web trust surfaces

What a reader of any news-show post now sees, rendered from committed data
and never typed: a collapsed **Verified claims (N)** panel under Sources,
each row the claim sentence linked to its source domain, from the
episode's `*_claims.json`; when the ledger is empty, one honest line says
so instead of hiding the state. A **provenance line** under the AI badge
(`engine.brand.episode_provenance` — "Written from 14 sources · 6 claims
checked against their sources · 1 unverified sentence removed before
publication · voiced with Grok TTS"; AI-host shows say so), and a
**Report an error** mailto beside it with the show and episode prefilled.

**Corrections have a mechanism now**, not only a policy sentence:
`digests/<show_dir>/corrections.yaml` (`engine/corrections.py`) renders a
dated box at the top of the corrected post, a line in that episode's show
notes, and — the promise the policy page had been making for months with
nothing behind it — a "Correction to episode N" line in the NEXT episode's
show notes (`engine.show_notes.append_show_notes_extras`, wired into
run_show). Audio is never edited silently; re-synthesis is the repair tool
(landmine #25). `docs/corrections.md` is the operator's how-to. No show has
a corrections file yet.

**The verification copy tells the truth about the gate.** The AI
disclosure and editorial pages said a failed claim blocks the episode "on
our narrative shows"; since 2026-09-12 the gate is enforced on every show,
re-sources failed claims once with the claim text pinned, REMOVES
still-unverified sentences before publication, counts an unreachable source
as a failure, enforces an item-coverage floor and fails on reviewer notes —
the narrative shows hold the episode back instead. Both pages say exactly
that and no more; a guard reads `_defaults.yaml`'s `enforce` / `on_failure`
and fails the templates if the wording drifts. The same page's Age of AI
bullet had re-grown the stronger gate-2 claim the Sep 22 pass retired ("each
guest approves their transcript before the episode publishes"); it states
the seven-day auto-publish now. One listener-facing address,
`engine.brand.CONTACT_EMAIL`, feeds the editorial, FAQ and contact pages and
every blog post (the editorial page had carried a different one).

## 6. What the operator decides

1. **Submit the thirteen feeds** — Podcast Index (public form), then Apple
   and Spotify; record `apple_url` / `spotify_show_id`. Until then they are
   findable only on nerranetwork.com and unmeasured by OP3.
2. **`wrangler deploy workers/gallery`** — the newsletter tag allow-list.
3. **UC skipped again on 10-01** (eleven skips since 09-03, two gate-blocked
   topics now deferred). A narrative show that publishes four days in seven
   on its own gate is the retention problem this brief is about; the Sep 30
   options stand (`on_failure: strip` for UC, or a claims appendix for
   historical sources).
4. **SpaceX Ep117 recorded 0 claims** with six sourced items and the
   coverage repair attempted — the repair returned nothing. Read the next
   three sidecars before touching the pass.
5. **Cover art**: Offshore North 1200×1200 is below Apple's 1400 minimum.
6. **The 09-30 transcripts** are still absent (a feed item without a
   transcript on 19 shows for that day); a re-run of `generate_transcript`
   over the committed MP3s is the fix.

## 7. Playbook additions

- A wiring guard renders through the real config object; a fake config with
  the attribute the code reads proves nothing.
- A lint that measures the digest must run on the text that ships, or
  record a second read after the last filter — two numbers that can
  disagree are better than one that cannot be wrong.
- A story told once per outlet is not a duplicate the overlap dedupe can
  see; cluster upstream and annotate, never drop.

## 8. Same-day policy change — publish and mark, never strip (operator-directed)

The operator's second brief of the day: a transparent claims-and-corrections
process for every show, so resources stop going into removing possible
problems from episodes as they are made — and so the shows stop missing
important, timely news because the gate could not vouch for it. The model's
training data lags the 24-hour cycle; a story newer than the model is
verified against its fetched source, never against memory, and "cannot
verify" has to be a status, not a reason to drop the story.

**What the old policy cost, measured.** In the 14 days to 10-01 the strip
mode removed 68 sentences across 261 episodes — Omni View 12, Planetterrian
10, Europe 7, SpaceX 5 — and every one audited in the Sep 17, Sep 18 and
Oct 1 passes was TRUE (a 403 journal, an X post the fetch stage held, a
paraphrased quote, MIT's NASDAQ close). Unintended Consequences skipped 11
of 28 days on its own gate; First Principles one. Four of fifteen flagship
episodes recorded zero claims, so on those days the gate protected nothing
and cost nothing — the silent half of the same problem.

**The policy now.** `on_failure: flag` on every show, UC and FPD included.
After the one repair pass, nothing is removed from the digest or the
script except the model's own reviewer notes; every ledger entry commits
with a status — verified (direct, from the fetched copy, or later),
unverified with its reason (source unreachable, not found, quote mismatch,
uncovered citation shape) — and `gate.flagged_sentences` names the
sentences a reader should weigh. A nightly job re-checks every unverified
claim for seven days and upgrades it to `verified_later` with the date.
The record is public: `claims.html` for the network and `claims/<slug>.html`
per show render every episode's claims with status badges, the flagged
sentences in plain words, later verifications with their dates, and every
correction filed; the blog's claims panel shows the same badges; the show
pages, nav and footer link it; the AI-disclosure, editorial and FAQ pages
describe this policy and no stronger one, and `engine.brand` owns the
process copy. Corrections (`engine/corrections.py`) reach the post, its
notes and the next episode's notes. What is still not claimed anywhere: a
human reading every episode before it ships.

**What this is not.** Not a return to shadow mode: enforcement is the
status and the public record, and a false flagged claim is corrected in the
open rather than pre-emptively deleted along with the true ones. Register
`claims-flag-policy-2026-10-01` scores it: zero strips and zero gate skips
for 21 days, at least 40% of unreachable claims verified within a week, a
network verified share of 85% or better, UC publishing 19 of 21 days.

