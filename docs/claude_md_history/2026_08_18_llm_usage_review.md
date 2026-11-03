# LLM usage review vs the Aug-2026 xAI product state (Aug 18, 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### LLM usage review vs the Aug-2026 xAI product state (Aug 18, 2026)

Canonical writeup:
[`docs/reviews/llm_usage_review_2026_08_18.md`](docs/reviews/llm_usage_review_2026_08_18.md);
drift guards: `tests/test_llm_usage_pass.py`. The review's verdict was
"no model upgrades", but the **operator overrode it the same day and
directed a NETWORK-WIDE upgrade to grok-4.6** (all LLM stages — digest,
fetch, scripts, synth, titles, reviewer, review agent — off grok-4.3;
refusal fallback repointed to grok-4.3; the dp_pod-4.5 / MIT-4.6
`podcast_model` pins removed as superseded/absorbed; ~+$22-25/mo).
**REVERTED the SAME DAY (2026-08-18, operator-directed)** — the trigger
was operational, not editorial: grok-4.6 digest latency ran **5-10×
grok-4.3** on every show measured (planetterrian 44s → 420s, MAB 36s →
242s, dp_pod 55s → 225s) and the four largest digest prompts (tesla,
spacex, omni_view, modern_investing) blew the 300 s request timeout or
were server-disconnected; nested SDK+tenacity retries amplified each
stall into a 41-45 min burn and **7 of 12 scheduled shows failed on day
one**. Everything is back on grok-4.3 (refusal fallback back on
grok-4.20-reasoning; the translation pin deliberately stays grok-4.6 —
it froze what `grok-latest` already served, and its small chunks never
tripped a timeout). Experiment `network-grok-46-upgrade` is closed
(status `done`, outcome REVERTED); grok-4.6's hallucination profile
remains UNMEASURED. **Any future model upgrade follows
[`docs/model_upgrade_playbook.md`](docs/model_upgrade_playbook.md)** —
staged one-show-first rollout with a digest-latency gate — never a
network-wide day-one flip. **The first staged trial started the same
day** (operator-directed; experiment `staged-grok-46-trial`, readout
2026-09-01): grok-4.6 on dp_pod's SCRIPT stage only, first_principles +
unintended_consequences whole-show (narrative — no news fetch), and the
synth + reviewer stages; `NERRA_LLM_TIMEOUT_SECONDS` raised to 600 in
run-show.yml to cover 4.6 latency. **2026-08-27: the FPD + UC whole-show
arms were WITHDRAWN (operator-directed, playbook latency gate)** — on
the GitHub-cron outage day FPD's 4.6 digest calls stalled ~260 s and
server-disconnected on both of its runs and UC died on both of its
runs, so both shows are back on the grok-4.3 network default; the
narrative-length question is unanswered, not answered negative, and a
re-pin needs a fresh staged trial. dp_pod's script arm and the synth +
reviewer stages continue. Every daily NEWS show's digest/fetch
stays grok-4.3 — scope pinned by
`tests/test_llm_usage_pass.py::TestStagedGrok46Trial`. Reviewer
FACTUAL_ERRORS comparisons from 2026-08-18 on must be cross-show under
the same 4.6 reviewer, never against pre-08-18 history (the instrument
changed with the trial).
The review also shipped three silent-number fixes: (1) **search billed per CALL** ($5/1k, env
`XAI_SEARCH_COST_PER_CALL`) — xAI dropped per-source billing and the usage
object's source count, so 100% of credit files since 07-29 recorded $0
tool fees; (2) **episode reviewer pinned `grok-4.3` + effort `none`** —
its configured slug was retired 05-15 and had been silently served by 4.3
at 4.3 billing while costed 6× cheaper; (3) **translation pinned
`grok-4.6`** (env `NERRA_TRANSLATION_MODEL`) — it rode `grok-latest`, so
vendor releases silently changed shipped dub audio; never put a published
stage on a floating alias. Dashboard `cost_rollup` now breaks out
`images` + `search` (41% of tracked spend, previously invisible). Voice:
the TTS request has NO model param — server-side updates arrive
unpinnable, so spot-listen after major xAI voice announcements;
multilingual-voice A/Bs wait until after the language cull (FR decision
08-25). Imagine stays on `grok-imagine-image` $0.02; the $0.05 quality
tier only if gallery-retention data ever demands it.
