# Oct 11 2026, evening — script-stage models (operator-directed)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 11 2026, evening — script-stage models (operator-directed)** (register
`narrative-script-grok47-2026-10-11`, `planetterrian-script-grok46-2026-10-11`;
guards `tests/test_script_models_2026_10_11.py`). Unintended Consequences and
First Principles write their SCRIPT on grok-4.7 at low effort; Planetterrian
on grok-4.6; every digest stays grok-4.3 and every arm streams. **The script
call has its own effort** (`llm.podcast_reasoning_effort`, used only while the
call runs `podcast_model`; a fallback to the digest model runs at that model's
own effort), and every follow-up script call — truncation retry, expansion
retry, publication-floor re-roll, anti-repetition retries — now carries the
same effort and stream as the first (they had sent the arm's model at default
effort, non-streamed: the shape that dropped in September). Measured before:
4.6 script calls take 190-700 s against 20-60 s on 4.3, so a pinned script
arm costs a run 3-12 min; the narrative shows and Planetterrian finish in
5-10 min of the 50-min budget. **Same evening, Tesla and Fascinating
Frontiers moved to the grok-4.6 script stage too, then Modern Investing and
Models & Agents** (operator call, ahead of the 10-23 SpaceX gate; register
`flagship-script-grok46-2026-10-11`, `mit-script-grok46-2026-10-11`,
`models-agents-script-grok46-2026-10-11`; MIT and M&A are CONTROL shows of
the Oct 13 readout, so that readout names them as a confound); Models & Agents for Beginners and The DP Pod, on the 4.6 script stage
since Sep 1 and Aug 18, now stream that call too: Tesla
leaves combined generation (a `podcast_model` override is two-pass), its runs
already reach ~32 min so the long-form render now leans on the budget gate,
and Tesla and FF are ARM shows of the Oct 13 spoken-open readout — read that readout
with this change named as a confound. ⚠️ AUDIO on all seven — A/B-listen Ep1.
**Streaming is the network default** (`llm.stream: true` in `_defaults.yaml`):
Env Intel, Финансы Просто, Привет, Русский! and Offshore North were the last
run_show shows on the non-streaming call. Same model and request; transport
only, and no show may opt back out (`TestConfig::test_every_show_streams`).
The interview shows ignore the flag — the Voices pipeline never calls
`engine.generator`. **Four Grok review PRs triaged the same evening**
(register `review-triage-2026-10-11`; guards
`tests/test_review_triage_2026_10_11.py`): a speaker-labelled line ("DAN:
Ten") is never a chapter title, DP Pod's Cold Open marker matches the spoken
"This is The DP Pod", and its prompts say weekly (⚠️ AUDIO). Checked and not
acted on: SpaceX "Patrick and Vancouver" is Whisper reading a script that says
"in"; on the 4.6 script SpaceX's AI section was empty and the price is spoken
once, at the close.
