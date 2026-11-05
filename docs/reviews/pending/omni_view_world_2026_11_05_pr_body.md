Prior Saturday/chapter fixes never shipped (Ep040 still multi-item Saturday; Ep037 still bare 'The Ten'); length ceiling remains an operator format-vs-promise decision; net-worth title filter false-positive’d Prop 40; Progress Watch absence and Both Sides place bugs look clear in Ep035–044.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1255**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| Saturday editions (weekday==5) whose The Ten section is a single story (not ≥5 ranked items) | miss | Ep040 (Sat 2026-11-01) multi-story Ten + week-in-review; Saturday lint from 2026-10-19 never shipped |
| _tts.txt files containing Progress Watch absence sentences (no sign of progress / day had none / nothing that meets a finished result) | hit | Ep035–044 transcripts: 0 absence shapes; PW uses 'a sign of progress' when present (Ep036, 042–044) |
| chapter JSON titles exactly equal to 'The Ten' | partial | Still 1/10: chapters_ep037.json title 'The Ten'; filter proposed 2026-10-19 not shipped |
| Both Sides cold-open place token missing from the digest Both Sides block (Tirana/Toronto class) | hit | Ep035–044 Both Sides openers match dispute geography (UK/Israel/India–US/Mecca/US/Palantir/AGOA/NBA Rwanda/Iran); no Toronto-for-Albania class error |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
None.

## Code/metadata-only proposals (no A/B needed)
- **`engine/digest_lint.py`** (code): Ep040 (and prior Ep019/025) prove Saturday edition_note is ignored; meta-review favors deterministic lint over another prompt. No audio change until a Saturday passes the lint.
- **`shows/omni_view_world.yaml`** (config): Opt Top World into the Saturday structural lint so a multi-item Saturday cannot publish.
- **`engine/chapters.py`** (code): Ep037 still ships bare 'The Ten'; podcast prompt forbids speaking section names; metadata-only, no TTS field changes (landmine #17).
- **`shows/omni_view_world.yaml`** (config): Ep042 leakage: Prop 40 'tax on net worth' is civic news, not paparazzi net-worth churn. Narrow exclude without re-opening celebrity profiles.
- **`tests/test_omni_view_world_quality_pass.py`** (code): Every behavioral fix needs a runway-tolerant drift-guard; avoids red main on same-day shape (Sep 2026 lesson).

## Deferred (carried forward)
- Operator decision: keep 5-developed+5-one-line and lower min_podcast_words + RSS 'twelve minutes' to match median ~1200–1500, OR deepen items 6–10 / cut to 8 stories and only then keep 1750/12 min — do not ship another podcast-side length lever
- 8-story vs 10-story cut after first-week download data (still ~2 median first-week downloads — too thin)
- Re-grade world feeds from a runner (check_feeds.py omni_view_world)
- YouTube enable is a data decision (plan §7; youtube.enabled still false)
- Surface desks_live_at_publish on the management dashboard (members-only desks)
- Tighten progress_watch_thin for bomb-threat reopen / single-bank earnings without public-welfare frame
- Any prompt-only write-longer / podcast_expand_below_target / word-floor pressure (do_not_retry)

<sub>tokens: 49971 in / 4264 out</sub>