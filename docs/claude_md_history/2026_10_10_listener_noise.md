# Oct 10 2026 — listener noise, and the slate review behind it

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 10 2026 — listener noise, and the slate review behind it** (review:
[`docs/reviews/slate_review_2026_10_10.md`](docs/reviews/slate_review_2026_10_10.md);
register `listener-noise-2026-10-10`; guards
`tests/test_listener_noise_2026_10_10.py`). Operator listen: too many stock
prices on MAG 7, and how many likes an X post got. **`engine/listener_noise.py`
removes, in code and network-wide, what a prompt already banned**: engagement
counts and the minute a post went up (only right after a posting verb — a
launch time is content), sentences that say only that a post was made on X,
and a closing-price TAPE (two or more consecutive closes for different
subjects; one price in a story and the flagships' quote line are untouched).
It runs on every X post at fetch, on the digest before the source-integrity
gate and on the script; the digest's reader-only `### The Tape` never reaches
the script stage (`strip_reader_only_sections`). Calibrated on 1,092 files —
re-run that sweep before widening a pattern. **Quotas put filler on air**: FF
and Planetterrian are capped at 12 items and include `interesting_first.txt`,
Tesla's Top 12 / Takeover are "up to"; a short, dense episode is the trade.
Shape fixes (⚠️ AUDIO): reference numbers (phone, file, patent, volume, read
time) only when the story turns on them; a story's first sentence names its
subject; desks skip Progress Watch on a none day and Both Sides without a
named disagreement; the Board is not a price tape; SpaceX/FF/MIT/M&A
specimens out; MIT's Action is optional and sourced; UC/FPD carry a named
person and a sourced hook number. "Pope Leo" is not LEO. **Open for the
operator:** the Patrick disclosure line ("editorial selection and analysis
are my own") contradicts the AI-disclosure page — operator decision
2026-10-10: keep it as is for now, do not change it unasked; the closing block (one ask,
topical sibling); widening the 4.6 script stage once SpaceX's streamed arm
has run.
