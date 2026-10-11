# Slate review: October 11, 2026

Operator brief: review the new shows and workflows from the last 24 hours and
find optimizations, improvements and room for differentiation, especially in
show quality and the visual quality of everything produced daily.

Five parallel reviews read the Oct 10–11 output: flagship scripts, the Patrick
cohort and narrative shows, the Mira desks and Nerra Daily, every visual
surface, and the workflow runs. Every finding below was checked against the
committed files before anything was changed. Register:
`slate-2026-10-11`. Guards: `tests/test_slate_2026_10_11.py` (plus
`tests/test_publication_floor_2026_10_11.py`, merged earlier in #1407).

## What was wrong, and what changed

### P0: a narrative episode invented its premise

Unintended Consequences Ep139 said the Argentine government licensed the
Patagonian toothfish fishery off South Georgia, and that the licences cut
orca calf survival there. South Georgia is a British Overseas Territory and
its fishery is licensed by its own government under CCAMLR rules. The
episode's claims ledger is empty, and the research search returned no
sources. The script was written from a queue brief that the restock model
had generated.

- **Correction filed**: `digests/unintended_consequences/corrections.yaml`
  (`where: both`). It reaches the post, its show notes and the next episode's
  notes.
- **Research floor**: `narrative_research_min: 2` on UC and First Principles.
  The topic search must find at least two sources, or the run tries the next
  topic, up to three. If none qualifies, the episode skips with reason
  `narrative_research_thin`. The show no longer writes a case from memory.
  A topic is annotated (two annotations defer it) only when the search worked
  and came back thin. An outage also returns nothing and must never defer
  good topics.
- Open for the operator: audit the next UC briefs written by the restock
  model. The next one (a harp-seal bounty) reads similarly unsourced.

### Sources and provenance

- **SpaceX read @grok as an X source.** The account's posts are chatbot
  replies to users, and one seeded Ep126's deep dive. Removed. A guard fails
  any show that adds it back.
- **SpaceX's deep dive was told it could use its own knowledge, and also
  that it needed five numbers not yet spoken.** Together those invite
  invented figures. Every number must now come from the digest, be a
  physical constant, or be spoken as an estimate. A company's cost, price,
  rate or specification appears only when a fetched source states it.
  ⚠️ AUDIO.
- **Mira's live prompt promised guests they would "hear and approve the
  episode before anyone else does".** That is the stronger gate the site
  stopped claiming on Sep 22: gate 2 auto-approves after seven days. She now
  states the built terms (the transcript, a week to approve, cut or refuse,
  takedown after). ⚠️ AUDIO (live interviews).

### Show structure (all ⚠️ AUDIO)

- **FF and Planetterrian prompts still said "Top 15" and "cover 12–14
  stories"**, one day after the Oct 10 cap of 12 items. The text now reads
  "Top 12" and "cover every story the digest carries". The headers still
  match the validator and content-tracker patterns (`Top \d+`).
- **Tesla's X Takeover asked for exactly 5 items.** It is now "up to 5", in
  line with the Oct 10 ceilings.
- **MIT opened Market Mechanics with "Imagine you…" on 12 of its last 12
  episodes.** The prompt supplied that template. It is now de-seeded by
  shape. This is a body rule; MIT's hook prompt is untouched because MIT is a
  control arm in the Oct 13 spoken-open readout.
- **The desks' Both Sides section was required** by the digest prompt and
  the validator (≥ 400 characters). On days with no named disagreement, it
  made the desks invent a counter-side and "the fact both sides accept". It
  now runs only when the articles name a person or body on each side. The
  validator rule is `optional`, and the sections before it end at Progress
  Watch when it is absent.
- **The Sunday week-in-review instruction quoted its own lead-in.** That
  lead-in opened the segment 12 times over two Sundays. The instruction now
  describes the shape.
- **The AI Chips and MAG 7 teasers named "the nearest item from the
  horizon/calendar just read"**, so the teaser restated the previous
  sentence. They now name a developing story the calendar did not just read.

### Chapters

- **MIT's "Practice Investment of the Day" chapter opened at 0:18 on every
  episode.** The pattern matched the disclaimer ("The Practice Investment of
  the Day uses simulated trades…"), so the chapter swallowed five minutes of
  market news (Ep197: 18.8 s to 343.3 s). The disclaimer's wording is now
  excluded, and on Ep197 the marker moves to the pick, about a third of the
  way in.

### Visuals

These were found by the visual review and fixed earlier on this branch:

- `engine.youtube_titles._clean_title` stripped "7." from "7.7 Quake Hits
  Panama" as if it were a list number. Decimals are now kept.
- A Short with no window hook took the generic fallback title. It now takes
  the episode's optimized title.
- The RU/FR dub thumbnails were cropped covers. They now use the episode's
  first scene.
- **SpaceX Ep127 filled 9 of 15 image prompts with static `image_queries`**
  ("Raptor engine static fire" on a Dragon cargo day). When stories supply
  briefs, the static set only tops the episode up to `MIN_STORY_SET` (4).
- Duplicate briefs for one event (Omni View Ep202's collapsed apartment
  blocks, twice per aspect) are deduplicated (`dedupe_briefs`).
- Essay sections (deep dives, AI & Compute) now contribute scene contexts
  (`essay_section_leads`). Before, briefs came only from numbered items.
- `_extract_hook` promotes a hook to its blockquote before the fallback
  walk, so a digest whose hook is a bare line still yields one.

### Workflows

- **Main had been red since Oct 10 16:00.** An Age of AI transcript guard
  sampled the boilerplate preface. It now samples speaker turns only.
- **Multilingual: a workflow-level concurrency group keeps one pending run
  and cancels the rest.** When four shows finished inside one translate
  window, the middle ones waited for the catch-all crons. Concurrency is now
  per show on the translate job.
- **A show that skipped its episode still ended "success"**, and FF's Oct 11
  skip triggered a sweep that rewrote 188 pages. The resolve step drops a
  show whose run left a skip marker for today and no digest dated today.
- **Nerra Daily Ep051 shipped the deterministic fallback**, reading nine
  feed titles aloud that ended mid-phrase in "…". The log said only "unusable
  shape". Now:
  - the warning names the reason (`links_reply_problem`);
  - a second attempt runs (never after a timeout, which would push the 8am
    release);
  - the fallback speaks the full hook from the digest (`spoken_hook`).
  
  All nine of Oct 11's clipped titles recover their full sentence.
- **The Age of AI has uploaded no video since YouTube was enabled on Sep
  20.** The edit path (`assemble_edit`, every `_edit_` episode) renders no
  MP4, so the derived video URL returned 404 on every publish. The publisher
  now renders the waveform video itself from the episode MP3, using the same
  renderer and cover. The job's cap went from 45 to 90 minutes, so a long
  render cannot cancel the feed commit that follows.
- **AOAI feed titles ran 220–254 characters** (Ep5–Ep11), and every platform
  cut them mid-word. `interview_episode_title` keeps "Ep N: Guest" whole and
  clips the thesis through `engine.titles`. The **summary line printed
  "Episode Summary"** on Ep011, because the notes pass opened on a heading;
  `notes_lede` skips headings, and Ep011's page was repaired. Published feed
  titles were left alone; the fix applies from the next episode.

## Not done, and why

- **Omni View's "What happens next" rule and its EXAMPLE block.** Omni View
  is the control arm of the spoken-open experiment that reads out on Oct 13.
  These changes wait for that readout.
- **Clipped lead-story chapter titles** (`_lead_story_split` / `_clip_title`)
  and **AOAI chapter/timestamp proximity in `supported_chapters`** need a
  calibration sweep over the committed episodes before a threshold moves.
- **Self-narration on the Vancouver and LatAm desks** ("according to the
  briefing"). New absence-filter patterns need the same 1,092-file
  calibration the Oct 10 filter had.
- **Press-release wires** (`/mediaoutreach/` and similar) as desk sources:
  a domain blocklist belongs with `preferred_domains`, which no desk sets
  yet.
- **Visual ideas for a later pass:** per-show image style signatures (every
  show currently shares one look); per-episode `og:image` (every post shares
  the show cover); a scheduled refresh of the outro-card screenshots
  (`scripts/capture_site_screens.py` has never run in CI, so the cards show
  an old site); eleven legacy covers with black corners.
- The `nerra_voices_publish.yml` commit message names only Age of AI. This
  is cosmetic.

## Operator items

1. A/B-listen the first post-merge episode of: UC and FPD (if they publish,
   they now have sources); SpaceX (deep dive); MIT (Market Mechanics and
   chapters); FF and Planetterrian; one desk and Top World (Both Sides);
   Sunday's segment on Oct 18; AI Chips and MAG 7 (teaser); and the next live
   Age of AI interview (Mira's terms).
2. Audit the unproduced UC briefs that the restock model wrote. Any whose
   premise cannot be sourced should be pruned.
3. The Buttondown tag "The Age of AI" does not exist yet, so the show's
   newsletter send refuses. It is created by the first signup carrying it, or
   by hand in Buttondown.
4. Re-run FF for Oct 11 if wanted. The skip happened before #1407 lowered its
   floor.
5. SpaceX Ep126 served grok-4.6 on the script stage at 7% verbatim, so the
   streamed arm is running. Widening it to Tesla still waits for the Oct 23
   GATE.
