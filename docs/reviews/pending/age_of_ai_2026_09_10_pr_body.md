First Age of AI pass: registry/no-op shell and contingency prompts look intentional and safe, but the review harness is blind (0 local scripts/chapters/costs/OP3) to the real Nerra Voices path, and the contingency podcast prompt contradicts the network cold-open order.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0453**._

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/age_of_ai_podcast.txt`** (prompt) — Contingency path currently contradicts {delivery_spec} and the network cold-open contract (hook before intro_line). Low runtime probability while the topic queue stays empty, but harmless to align; any exercise of this path needs A/B-listen.
```diff
- 1. Begin with this exact line, copied verbatim:
- {intro_line}
- Then the premise in Mira's own words (the host is an AI; the people in this story are real), and the hook: {hook}
+ 1. Cold open on the hook — first spoken words are substance, not a greeting: {hook}
+ Then this exact identity line, copied verbatim:
+ {intro_line}
+ Then the premise in Mira's own words (the host is an AI; the people in this story are real).
```

## Code/metadata-only proposals (no A/B needed)
- **`scripts/review_snapshot.py`** (code): P1 blocker: without Voices-aware substrate every AOAI review can only restate the registry shell and will mis-score empty _tts as quality.

## Deferred (carried forward)
- Full Nerra Voices pipeline + shipped-episode transcript/editorial quality audit (no pipeline files in this bundle)
- Phase-8 enable of X, YouTube, newsletter, multilingual when operator launches publicly
- Operator verify Apple/Spotify catalog episode counts vs age_of_ai_podcast.rss and OP3 feed resolution
- Voices episode_memory_block coherence with memory_enabled narrative/Story Tracker surfaces
- Guest-funnel and diversity metrics from Supabase Voices tables
- Any podcast-side min_podcast_words / expand-retry length lever (network length meta-rule; interview length is edit/guest-driven)
- TTS voice_id, speech tags, phonetic respellings, coupled speech_wrap/use_section_tts/max_chars changes (landmine #17)

<sub>tokens: 13089 in / 3187 out</sub>