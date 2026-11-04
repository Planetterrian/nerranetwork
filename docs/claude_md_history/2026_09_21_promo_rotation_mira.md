# Sep 21 2026 — the promo rotation: mira + topics added, gallery 3 → 2

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

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
