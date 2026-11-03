# What the flagship rehearsals showed in the video (Oct 18 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### What the flagship rehearsals showed in the video (Oct 18 2026)

Three no-publish rehearsals (SpaceX Ep134, Tesla Ep638, FF Ep226) measured
frame by frame (register `video-pass-2026-10-18`,
`hook-short-motion-ab-2026-10-18`; guards `tests/test_video_pass_2026_10_18.py`).
Rules that bind: **a slot never repeats the previous picture when another image
fits the chapter** (one sharing a word with its title, else a library scene; an
unrelated story's image never fills in — `engine.scene_scheduler._alternatives`),
and **the slot cap never merges same-image neighbours first** — each slot is its
own Ken Burns move, and merged they became one crawl over a still (FF held one
picture 74 s); a merge that would put an image beside itself goes last. **A fact
card shows only a label that reads** (compound units join the figure — "1 GWh",
"230 mph", "37 million light-years"; the label stops at a comma, before a credit
or a joining word; a fragment drops the card unless the figure's unit explains
it). **A Short ends on its last full sentence** inside its final 8 s
(`engine.shorts_selector.end_on_sentence`, metric `short_durations`). **Burned-in
captions rejoin Whisper's split tokens** ("107" ".6" "%" →
`engine.captions.merge_split_words`). **The outro card's show count comes from
`generate_html._public_shows`**; screenshots refresh through Actions "Capture Site
Screenshots" (monthly + on demand — this sandbox's Chromium does not trust the
proxy CA). **The hook motion clip runs on even date ordinals only**
(`youtube.hook_short_motion_alternate`; odd days record `control_stills` /
`control_broll`, never `hook_stills`); readout `hook_motion_vs_control_d3`.
**No show renders an Instagram/TikTok variant while no workflow carries the
posting secrets** (Tesla/SpaceX off). Render and metadata only.
