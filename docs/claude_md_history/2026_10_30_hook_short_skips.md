# The hook Short skips the map (Oct 30 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The hook Short skips the map (Oct 30 2026)

Review [`docs/reviews/youtube_review_2026_10_30.md`](docs/reviews/youtube_review_2026_10_30.md);
register `shorts-skip-map-2026-10-30`; guards
`tests/test_short_skips_map_2026_10_30.py`. EN took a second Shorts step on
Oct 19-20 (Shorts-feed views ~220 → ~90 a day, day-3 median per Short 15-16 →
8.5; long-form unchanged), and since Oct 20 the hook Short — a clip of the
episode's opening — carried the map sentence: ~9 s of a ~32 s Short listing
other stories. Shorts on all three channels held viewers ~2.5-3 s less at age
5. Rules that bind: **the hook Short renders from a spliced source**
(`engine/short_furniture.py`: the map line located in the committed script —
a sequencing word and a list comma, never an attribution or continuation —
and in the Whisper words, cut from a FLAC copy of the mix and from the
transcript, so captions, fact cards and cuts share one timeline; any failure
renders as before; `youtube.shorts_skip_map`, metric `shorts_map_cut_s`).
**The episode, its feed audio and its long-form keep the map.** Replay: 128 of
176 cut since Oct 20, 0 of 379 before. Open (operator): the dead-Shorts
tier's absolute floor of 10 now demotes six EN shows on a channel-wide slump
(the Oct 31 review made it relative).
