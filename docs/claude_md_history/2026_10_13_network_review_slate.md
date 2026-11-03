# Network review — the Oct 12-13 slate (Oct 13 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Network review — the Oct 12-13 slate (Oct 13 2026)

Operator-directed (review:
[`docs/reviews/network_review_2026_10_13.md`](docs/reviews/network_review_2026_10_13.md);
ledger `network` 2026-10-13; register `network-review-2026-10-13`; guards
`tests/test_network_review_2026_10_13.py`). 45 episodes, 100% run success,
spoken-text gate 45/45, every script arm served its own model. What binds:
**sourcing narration is cut in code, at clause level where the sentence
carries a fact** (`engine.absence_sentences.cut_sourcing_clause` — "X is
the source for …, and the current reading is eleven degrees" keeps the
temperature; five more shapes and the Progress Watch echo without a colon;
sweep every committed script before widening a pattern); **a hook that
re-tells a story covered on two or more recent days is a structural
defect** (`HOOK_RECURRENCE_MIN_DAYS` in run_show — Tesla Ep632 led with
Solar Roof a ninth time under the note that said not to); **a fast_info
quote equal to its previous close is the prior close** (SpaceX
`_no_trade_yet` — before the first pre-market print Yahoo returns the
close as the last trade); **a launch designator is two numbers, never a
range** and **a `.TO` ticker is spelled** (`assets/pronunciation.py`);
**Whisper's low-probability echo tokens are dropped before they reach
captions** (`engine.transcripts.drop_echo_words`, calibrated: the echo
reads 0.016-0.022, a real repeat 0.5+); **a lead section is matched by
name OR "Top " prefix, and Reddit joins X in the lead-source rule**
(`is_lead_section` — the lint had been a no-op on five of its own shows);
**a lint a show opts into is a rule its prompt states** (three cohort
prompts lacked the WYNTK clause and Prediction Markets regenerated 5/5
days); **MIT's Market Pulse reads `{nasdaq_benchmark_line}` from the hook**,
never the digest's copy; **MAG 7's Company Desk floor is 1** (the prompt
says never pad); **a prompt never types a sibling's cadence word**
(guarded); **the Voices fire-tick asks Supabase before dispatching**
(`fireTickDue`, fail-open, :00/:30 unconditional — 288 no-op jobs a day;
operator: `wrangler deploy workers/voices`). ⚠️ AUDIO: arXiv on M&A, the
desks' filtered scripts, MIT's Market Pulse, UC's cross-promo, Top World's
first sentences.
