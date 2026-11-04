# Flagship review — SpaceX, Tesla, Models & Agents + shared pipeline (Sep 4, 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

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
