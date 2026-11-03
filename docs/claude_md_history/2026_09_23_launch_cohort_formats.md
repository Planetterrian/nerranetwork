# Launch-cohort pass, formats + fixed-clock segments (2026-09-23)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

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
