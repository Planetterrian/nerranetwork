# Grok prompt + voice review (June 10, 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Grok prompt + voice review (June 10, 2026)

All 49 show prompts + in-code prompts (outline/retry, weekly synthesizer,
episode reviewer, X fetch) reviewed against prompt-engineering practice —
canonical writeup: [`docs/prompt_review_2026_06_10.md`](docs/prompt_review_2026_06_10.md);
drift guards: `tests/test_prompt_quality_pass.py`. Voice/TTS config verified
consistent and deliberately untouched (landmine #17). Shipped:
`engine/utils.fix_phonetic_garbles` repair layer on every digest + script
("nassa" had shipped verbatim in a published transcript — bans alone don't
stop a known finite failure set); the X-post fetch prompt now requires
SUBSTANTIVE posts (emoji spam + a slur one-liner had flowed into prompts);
stale "ElevenLabs engine" claims removed from the 9 remaining podcast
prompts; MIT's residual "at least 2500 words" contradiction fixed; Tesla
digest selection rules unified (count-tier table vs judgment rule) and the
template's 🎙️ emoji removed; reviewer QUALITY_SCORE got calibration
buckets; the weekly synthesizer must ground cross-domain threads in actual
coverage; Tesla's system prompt now explicitly forbids filling gaps from
training-data knowledge. Deferred behind A/B (in the doc): few-shot
exemplars for prompts lacking one, converting ban-lists to rotation menus.
