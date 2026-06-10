# Environmental Intelligence — quality review (2026-06-10)

First dedicated quality pass on **env_intel**. The show was scaffolded after
the May/June flagship rounds and was *missed* by the Tesla chapter-bug fix
and the June 10 four-show pass, so it still carried two bug classes those
passes eliminated elsewhere (mis-positioned chapters + orphan closing
variant) plus a cadence-accuracy bug unique to its odd-weekday schedule.

Snapshot baseline (`scripts/review_snapshot.py env_intel`): 8/10 recent
episodes below the 900-word target (493–925 words, avg ~750); 5/10 episodes
with duplicate/misordered chapter titles; cost ~$0.074/ep; OP3 11 dl/7d,
24 dl/30d. No prior review, no ledger.

## P0 — listener-facing bugs shipping today

### 1. Chapters: mis-positioned + duplicated + orphan closing variant
`shows/env_intel.yaml` chapter `section_markers` had **no `where`
positional anchors** (every other anchored show got them in the Tesla / PT /
four-show passes). Verified against committed `chapters_ep0*.json`:

- **Ep040**: `[Introduction, Reg, Action Items, Reg, Science, Tomorrow
  Teaser, Closing, Industry & Practice, Tomorrow Teaser, Science]` — the
  **"Closing" chapter landed at position 7 of 10** with real content after
  it; `Reg`, `Science`, `Tomorrow Teaser` each appeared twice.
- **Ep038**: `Regulatory & Policy Watch` and `Science & Technical` both
  duplicated.
- The Closing chapter pattern was `"That's Environmental Intelligence"`,
  which matches closing-pool variant 1 but **not** variant 2 (`"That covers
  today's environmental intelligence"`) — episodes using variant 2 ship with
  no Closing chapter (the MAB orphan-closing bug class). Verified:
  `closings matched: [True, False]` before the fix.
- The `Industry & Practice` marker `"industry|practice"` matched the bare
  word **"practice" in the closing** (`"useful to your practice"`). In 3 of
  4 recent episodes "industry" never appears at all and "practice" *only*
  appears in the closing — so the chapter was almost always a false match
  that stole the final segment's title.

**Shipped:** added `where: start` to Introduction, `where: end` to Tomorrow
Teaser and Closing; widened the Closing pattern to cover both closing-pool
variants; excluded the closing phrase from the Industry pattern with a
negative lookbehind `industry|(?<!your )practice`. Re-parsing the last four
committed scripts with the new markers: **zero duplicate titles**, Closing
anchored to the end window, both closings matched. (The once-per-title
dedup landed engine-side in the four-show pass; these YAML anchors are what
keep the *positions* correct.)

## P1 — quality ceiling

### 2. Cadence-inaccurate spoken copy ("daily" / "back tomorrow")
env_intel runs **odd weekdays** (`run-show.yml`: `odd_weekday` — odd days
AND weekdays, so a ≥2-day gap between episodes). The RSS description was
corrected to "published every other weekday" in the June network pass, but
the **spoken** intro/closing in `engine/intros.py` still claimed a daily
cadence on every episode:

- opener: *"Your daily environmental intelligence briefing."*
- framing: *"Your daily briefing on…"*
- closings (both pool variants): *"We're back tomorrow. Have a productive
  day."* / *"We're back tomorrow morning."* — the snapshot found *"back
  tomorrow have a productive day"* in 7/10 transcripts.

Saying "back tomorrow" on a show whose next episode is two-plus days out is
simply wrong. **Shipped:** dropped "daily" from the opener/framings and
replaced the "back tomorrow" sign-offs with the cadence-neutral *"We'll be
back with the next briefing."* (This also removes "tomorrow" from the
closing text, which was the source of the Tomorrow-Teaser chapter
false-matching the closing on old episodes.)

### 3. Self-contradictory length target
`env_intel_podcast.txt` demanded *"6–9 minute (1500–2200 words)"* and *"Your
script must be at least 1500 words (45+ sentences)"* — while the YAML pins
`min_podcast_words: 900` (deliberately tuned down, with a detailed comment
noting episodes realistically run ~700–930 words) and the prompt's own
closing instruction says *"if the briefing is genuinely thin, let the
episode be shorter."* The 1500-word floor was unreachable on this narrow
news surface and contradicted both the gate and itself, firing the
expand-retry on essentially every episode. **Shipped (prompt edit — A/B):**
unified to one realistic target — *"6–8 minute (900–1300 words)"*, *"30-45
sentences"*, *"should target 900–1300 words (30+ sentences)"* — matching the
prior passes' "one length target per prompt" principle and the tuned YAML
floor.

## P2 — growth / discoverability

OP3 is low (11 dl/7d) but the RSS channel description + Compliance Brief
positioning were already rewritten in the June network pass, and X/YouTube
are intentionally disabled for this show. No new growth changes this pass —
the chapter/cadence fixes are the higher-leverage work. Revisit
discoverability once the above settle (see deferred).

## Deferred (recommendations, not shipped)

- **Digest-driven / position-aware mid-section chapters.** The mid-episode
  markers (`science|technical`, `industry|practice`, `regulatory|policy
  watch`) match incidental keywords because the prompt deliberately tells
  the host *not* to announce sections. Even after the structural anchors,
  a mid-section chapter can attach to the first incidental keyword rather
  than the real section boundary (Ep042 opened on `Industry & Practice`).
  A robust fix means deriving chapter boundaries from the digest's section
  structure rather than transcript keyword-matching — medium effort, shared
  across shows, defer.
- **Thin-news-day handling.** Ep043 (June 9) shipped with the digest stating
  *"No Canadian regulatory changes … appear in today's feed"* and ~594
  spoken words about the absence of news. `min_articles_skip: 2` let it
  through; the `slow_news` library (`shows/segments/env_intel.json`) is
  configured but didn't fill. Worth a follow-up: either raise the skip
  threshold or ensure the evergreen segment library backfills a thin day.
  Not changed this pass (touching skip thresholds is landmine #21 territory
  and needs the operator's editorial call).

## Tests

New drift guard `tests/test_env_intel_quality_pass.py` (7 tests): chapter
positional anchors, both closing variants matched, Industry pattern excludes
the closing phrase, no "daily"/"tomorrow" in spoken copy, unified length
target + contradictory targets removed. All pass. Smoke suites green:
`test_prompt_fidelity`, `test_intros`, `test_chapters`,
`test_episode_validity`, `test_generator`, `test_four_show_quality_pass`,
`test_schedule`, `test_config` (314 tests total across the run).

## ⚠️ A/B-listen required (landmine #17)

Two changes alter shipped audio — listen before trusting:

1. **`engine/intros.py`** — env_intel intro/framing/closing copy (dropped
   "daily", replaced "back tomorrow" with "We'll be back with the next
   briefing"). Deterministic, not LLM, but it changes spoken words.
2. **`shows/prompts/env_intel_podcast.txt`** — length target 1500-2200 →
   900-1300 words. Live regen against the Ep042 digest produced an 893-word
   script with correct structure (new intro/closing rendered, sat right at
   the floor as expected for this show). Could marginally shorten episodes;
   confirm coverage still feels complete on a normal-news day.
