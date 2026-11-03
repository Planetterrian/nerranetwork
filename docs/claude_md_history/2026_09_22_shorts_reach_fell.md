# Sep 22 2026 — Shorts reach fell on every channel at once

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

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
