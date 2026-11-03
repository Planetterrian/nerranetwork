# Sep 9 2026 — Grok's retention plan, checked against the data

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 9 2026 — Grok's retention plan, checked against the data**
(review: [`docs/reviews/youtube_retention_review_2026_09_09.md`](docs/reviews/youtube_retention_review_2026_09_09.md)).
Three of its items survived the recompute and shipped, all render-only:
**the Shorts end card asks for the SUBSCRIBE** ("WATCH FULL EPISODE"
pointed at a surface the burned card cannot link; the site funnel it
fed measures 8 attributed sessions from 246k views; the headline also
gained shrink-to-fit — 18 characters at 88 px had run off the 1080 px
card since May); **the long-form opening slot draws from the fresh
pool only** (`scene_scheduler`: one token of title overlap outscored
the fresh bonus, so an older library scene could open the video);
**fact cards** (`engine/fact_cards.py` — spoken figures as timed cards
from the Whisper words, which arrive as digits split across tokens;
`youtube.fact_cards_enabled` on tesla/spacex/FF, M&A/MAB/OV control).
Rejected with numbers: replacing the long with a 90–120 s lead cut (no
such knob exists; the long is the Apple video asset and the top EN
subscriber source per video), pausing FPD (34 views/Short — above
Omni View; the dead uploads are env_intel, finansy_prosto and MIT's
dubs — operator's call), "keep fill-to-requested" on EN (median 3
views), and anything spoken (landmine #17). `api/gallery_retention.json`
has never held a tag — do not cite it. Register: `shorts-subscribe-cta`
(metric `short_subs_per_video_14d_en`, baseline 0.11),
`fresh-open-long-form`, `long-form-fact-cards` (readouts 2026-09-30).
Guards: `tests/test_fact_cards.py`, `TestFreshOpen`.
**Same day, operator-directed:** YouTube PAUSED on env_intel and
finansy_prosto (`youtube.enabled: false`, blocks intact for a one-line
re-enable; ~10 and ~6 views per upload). MIT's RU/FR dubs were already
culled 2026-09-02. `YOUTUBE_ENABLED_SHOWS` in `tests/test_schedule.py`
pins the set; register `pause-dead-youtube-uploads`.
