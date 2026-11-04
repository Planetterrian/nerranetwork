# Recursive narrative memory generalized (Phase 3, May 2026; Jul 24 + Aug 16 expansions)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

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
