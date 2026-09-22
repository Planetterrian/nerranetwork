# Video quality pass — 2026-09-22 (second pass of the day)

Operator brief, after the morning's YouTube pipeline review (PR #1263):
*"Is there anything we can do to make the videos, both short and long
videos, more entertaining and visually appealing to the audience and
relevant to the audio?"* — then, on the assessment: *"Please do as
recommended, also yes to the real motion retry and changes to the prompt
as long as it is done carefully and doesn't break other workflows and
processes."*

Method: three exploration passes (the Shorts render path and the motion
options, the long-form scene path and the retention data, the cold open
and the hook path) over the working tree, every claim checked against the
committed files (`api/youtube_stats.json` generated 2026-09-22,
`site/data/gallery-manifest.json`, `api/gallery_retention.json`, the
per-episode metrics and transcripts). Ledger:
`docs/reviews/ledger/network.yaml` 2026-09-22 (second entry). Register:
seven entries dated 2026-09-22 in `docs/experiments.yaml`.

**One item in this pass changes shipped audio** (the spoken-open shape,
§7) and is staged on three shows behind a code gate — A/B-listen per
landmine #17. Everything else is render- or metadata-side.

## 1. What the retention data says

The mean EN long-form audience-watch curve, over the 13 videos that carry
one:

| elapsed | 1% | 2% | 3% | 4% | 5% | 10% | 50% | 100% |
|---|---|---|---|---|---|---|---|---|
| EN mean ratio | 0.95 | 0.85 | 0.74 | 0.56 | 0.48 | 0.31 | 0.10 | 0.03 |

RU holds 0.53 at 5%, FR 0.50. On a ten-minute video that is seconds 6 to
60 — a steady slide, not a cliff at a visual event, and it is over before
the first chapter change (10–20% in). Every render lever since August
(chapter cards, the fresh-open slot, 2K images, caption changes) left the
5% hold at 0.48; the one audio lever, the July cold open, moved
retention about two points. The thumbnail/title promise being delivered
in the first thirty seconds is what the two outliers that held 68–72%
did.

Read: the picture matters less than the first sentence, and a picture
that does not match the sentence matters most.

## 2. What was wrong with the picture

- **Half the images on a flagship long-form were older library shots** —
  13 fresh vs 14 library per episode in the week to 09-22, blended in on
  ONE shared salient token. Only slot 0 was guaranteed fresh.
- **Long-form scene cuts were equal subdivisions of each chapter**,
  landing mid-sentence; the Shorts have snapped to sentence ends since
  June. Nothing on the long-form path read the Whisper words.
- **The gallery-retention flywheel was inert and confounded.** The
  ranking prior matched the report's prompt-mined phrases against the
  manifest's `tags` array (slug, provider, use): 0 non-zero scores across
  1,646 images on three shows. The report pooled Shorts (~55% AVP) with
  long-form (~15%), so every show's top tag was "vertical 9:16 framing"
  and its bottom "wide cinematic 16:9 framing" — a measurement of the
  kind, not of the imagery. Feeding that into prompts would have fed the
  confound.
- **Fact cards, the one render lever with a measured effect** (+3–4 AVP
  points on the treatment shows), existed on long-form only.
- **The thumbnail punch text** (2–4 ALL-CAPS words, generated for every
  episode since July) was used only on the thumbnail.
- **Real motion:** the Shorts motion A/B stalled at n=4 (operator ended
  it 08-14) and the long-form clip pilot was retired for ~1/3 success at
  ~$0.35 an episode and timeouts. The hybrid Short renderer already opens
  on a clip by design but required two.
- **The spoken open is the digest HOOK line, word for word**, and it ran
  14–32 words (median 19 words / 123 characters), no question, no digit
  in 10 of 15, 6 of 15 over the prompts' own "under 120 characters" —
  and nothing in code checked length or shape. Three prompts carried
  quotable WEAK/STRONG specimen hooks; Tesla's labelled its digit-bearing
  example WEAK.

## 3. Shipped — render side (no landmine-#17 item)

**A. Own scenes.** `gallery_blend_max_long` 8 → 3, `gallery_blend_min_
overlap` 1 → 2, `gallery_blend_max_short` 6 → 2; the `visual_reuse`
getattr fallbacks now equal the dataclass (a stub config used to resolve
to the old blend). Register `library-blend-own-scenes-2026-09-22`.

**B. Speech-snapped long-form cuts.** `engine.scene_scheduler._snap_
slots`: each interior equal-split boundary moves to the nearest sentence
end within ±2.5 s; a hold may run past the max by the tolerance to
finish a sentence, never under the min; chapter boundaries and slot
counts are unchanged; `None` words = byte-identical. `long_form_visual_
plan` shifts the Whisper words by the music-intro delay (they are on the
voice-only timeline). Knob `long_form_sentence_cuts` (on). Register
`long-form-speech-cuts-2026-09-22`.

**C. Flywheel repaired per kind.** `build_gallery_retention.py` writes
`summary.by_kind` (long | short) with per-kind medians and tags backed by
≥ 10 videos within the kind; the pooled block stays for the dashboard,
flagged `pooled: true`. The prompt boilerplate is excluded by NAME — the
hint strings are now module constants on `engine.grok_imagine`
(`FRAMING_HINT_*`, `QUALITY_HINT`, `NO_TEXT_HINT`; prompts byte-identical)
— plus the retired-prompt phrases and the "visual subject:" scaffold
label the real manifest still ranked. The ranking prior reads `by_kind`
only and matches phrases against prompt + caption + tags text.
`style_feedback_for()` hands the scene-brief prompt ONE audience-note
sentence (≤ 2 favoured, ≤ 2 avoided phrases; ≥ 10 videos; ≥ 5 points
from the kind's median) or `None`. **On the 09-22 data every flagship
reads `None`** — Tesla's best long-form tags sit at +4.3 — so the prompt
is unchanged until the data says something; that is the design. Register
`gallery-retention-per-kind-2026-09-22`.

**D. Shorts fact cards** (EN, tesla/spacex/FF). `fact_cards_for_window`
gives ≤ 2 clip-relative cards; `_short_form_fact_cards_stage` paints a
96 px cyan figure + 40 px label at ~62% frame height, between the hook
band (gone by 3.05 s) and the caption card. Never under the hook, never
into the end card. The RU/FR dubs render their own Shorts and get none
— the control arm. Register `shorts-fact-cards-2026-09-22`.

**E. Punch frame** (hook Short, EN, tesla/spacex/FF). The punch text
opens the frame for 1.4 s at 96–128 px; the hook's window shifts to
1.2–4.25 s under it; an unfit punch is skipped, never ellipsised.
Register `shorts-punch-frame-2026-09-22`.

**F. Bounded motion retry** (tesla/spacex/FF). `engine/hook_short_
motion.py`: ONE ~4 s Grok video clip (720p, 9:16, $0.28) opens the hook
Short; stills cycle after it (`_build_short_hybrid_sequence(max_still_
hold_s=7)` — one clip used to leave a single 31 s still hold). Gates in
order: disabled → nothing to film → pipeline budget under 300 s → cost
ceiling from the price table BEFORE any request → the request under its
own 150 s budget. Every shortfall ships stills and RECORDS `hook_stills`;
a show whose b-roll pool already opened the Short records `broll_open`
(SpaceX has 25 NASA clips). Never the A/B's `"stills"` label — the A/B
report sweeps that up fail-open. The arm lands on the video index
(`variant`) and rides into `api/youtube_early_reach.json`, so the
age-matched reach can be sliced by arm at readout. ~$25/month at full
success. Register `hook-short-motion-2026-09-22`.

## 4. Shipped — the spoken open (⚠️ A/B-listen)

**G.** `shows/prompts/_shared/hook_shape.txt` — shape only, no quotable
line, no digits: ONE sentence, at most twenty words; the concrete
quantity inside the first ten; the stake in the same sentence; not a
question; no dateline, source name, show name or greeting. Included under
the HOOK spec of the three flagships' digest prompts, whose WEAK/STRONG
specimens are removed. `engine.titles.SPOKEN_HOOK_MAX_CHARS = 150` is the
one owner of the limit; run_show's structural regeneration treats an
over-long hook as a defect on every daily show (SpaceX had no validation
config and was never gated) and takes the retry only when its hook fits
— a gate, never a clip; metric `digest_hook_over_length`.
`build_cold_open_spec` gained one shape bullet with no quoted string.
Scored per arm: `long_open_hold_5pct_arm` (0.49 at ship) against
`long_open_hold_5pct_control` (0.44); `long_open_hold_5pct_en` is never
reopened (long-open-cliff). Register `spoken-open-shape-2026-09-22`.

## 5. Rejected or deferred

- **Splitting the fact card from the punch frame** into a per-show A/B:
  they ship on the same Shorts the same day, so only the pair is
  attributable. Split only if the pair moves.
- **Style feedback on the Shorts' briefs**: long-form only until the
  `short` by_kind block carries a real pair.
- **Pooling the retention prior across kinds** (the quick fix): rejected
  — it would have ranked vertical-looking prompts up on the long-form.
- **A shorter lead cut / replacing the long**: rejected in the morning
  review with numbers (the long is the Apple video asset and the top EN
  subscriber source per video).

## 6. What to read at the readouts (10-13 / 10-20)

`scene_library_count` on the flagships (≤ 3), the scheduler's "interior
cuts snapped" log line, `short_avp_en_14d` on the arm vs the other EN
shows with the dubs flat, `hook_short_motion_share_14d` with the
early-reach file sliced by `variant`, `by_kind` present in
`api/gallery_retention.json` and `scene_brief_style_feedback` in a
flagship's metrics, and `long_open_hold_5pct_arm` vs `_control` with the
first arm episodes listened to. Scoring rule from the morning pass still
holds: a Shorts read that lands on a distribution-side week is
INCONCLUSIVE with the confound named, never a MISS.

## 7. Verification

The venv pytest run over the touched suites and the full suite (the four
`test_it_produces_itself` cases need `ffmpeg`, absent in this container,
as in the morning pass), `ruff check engine/ run_show.py scripts/` clean,
`build_gallery_retention.py` run against the committed manifest and
stats (`by_kind` populated on 14 shows, no framing boilerplate in any
top list), `_experiment_live_metrics` computing every registered key
(arm 0.49 / control 0.44 / short AVP 62.5 / motion share null). No paid
API call, no upload, no publish in the session; the container has no
`GROK_API_KEY`, so the before/after HOOK is not pasted here — the first
arm episodes are the sample.
