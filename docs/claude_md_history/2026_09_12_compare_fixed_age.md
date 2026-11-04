# Sep 12 2026 — "views and subscribers dropped": compare at a fixed age, never against the peak

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 12 2026 — "views and subscribers dropped": compare at a fixed
age, never against the peak** (review:
[`docs/reviews/youtube_review_2026_09_12.md`](docs/reviews/youtube_review_2026_09_12.md)).
Uploads were complete every day and every channel was +50-60% week
over week on matching weekdays; what read as a drop was three breakout
Shorts on 09-04..06 (883 / 722 / 769 views) fading, plus the Data API
counter re-syncing Shorts views on 09-10 (+21,660 EN in a day). The
honest ruler is views per video at a fixed snapshot age: EN Shorts
published 09-07/08 earned 15-17 at day 3 against 22-32 on pre-peak
weekdays (a real ~35% softening on the non-flagship shows, flat on
Tesla/SpaceX/FF and RU; watch-through unchanged, spoken opens still
match the hooks). `scripts/track_early_reach.py` now folds every
nightly snapshot into `api/youtube_early_reach.json` (whitelisted in
nightly's add-paths) and the dashboard's **Early reach (age-matched)**
card + `short_reach_d3_median_en_7d` read it — use that card before
calling a drop. Same pass: two shows hit the 3,000 s pipeline budget on
09-11 during a chronically slow long-form render (531-1,202 s per
episode, `long_form_render_duration_s`; `long_form_render_median_s_7d`
on the register), and the slideshow graph **fails outright on ffmpeg
7.x** ("inputs need a constant frame rate" at xfade after trim/setpts)
— every zoompan branch now ends on a same-rate `fps` stamp (pass-through
on 6.x; guard `TestFfmpeg7FrameRateStamp`), which is what ubuntu-latest
will ship next. `generate_editorial_page(output_dir=)` exists so the
test renders into tmp instead of the repo root.
