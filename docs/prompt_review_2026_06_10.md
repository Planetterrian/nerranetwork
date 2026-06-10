# Grok Prompt + Voice Review (June 10, 2026)

Review of every LLM prompt surface (49 show prompt files + in-code prompts:
outline/retry/structural-retry, weekly synthesizer, episode reviewer, X-post
fetch, recap framing) and the Grok TTS voice configuration, against current
prompt-engineering practice for a strong always-on-reasoning model
(grok-4.3). Drift guards: `tests/test_prompt_quality_pass.py` (+ a tightened
pin in `test_four_show_quality_pass.py`).

## Voice / TTS: verified consistent, deliberately untouched

The hard-won policy stands (landmine #17: theory-driven TTS modifications
have a 100% regression rate on the custom voice). Verified, not changed:
single-call synthesis + whole-script `<fast>` wrap + 14k `max_chars` as a
coupled set; WAV 48 kHz + server `text_normalization`; letter-spelling-only
pronunciation map; tag-leak detector. One stale comment fixed (tesla.yaml
named a wrong voice id; the network voice is `kdif6sqjcyiq`).

## Implemented

### Reliability (listener/reader-facing)
1. **Phonetic-garble repair layer** (`engine/utils.fix_phonetic_garbles`).
   The prompts ban phonetic spellings, but the model still slips — "nassa"
   shipped verbatim in FF Ep096's published blog transcript; the daily audit
   flags "chwen"/"en-vidia" after publication. Bans alone are the wrong tool
   for a known finite failure set: a deterministic word-boundary repair map
   (nassa→NASA, chwen→Qwen, en-vidia→Nvidia, nay-toe→NATO,
   open-ay-eye→OpenAI, star-mer→Starmer; deliberately no space-separated
   variants — "star merger" collides) now runs on every digest and podcast
   script before TTS/blog/RSS. Detection stays in the audit as the signal
   that the map needs a new entry.
2. **X-post fetch prompt requires substantive posts** — the Ep505 log showed
   "Laughing Emojis", "Video post", and a slur one-liner flowing into digest
   prompts. The fetch now defines substantive (concrete fact, claim,
   announcement, observation) instead of accepting anything recent.
3. **Stale "ElevenLabs engine" claims removed** from all 9 remaining podcast
   prompts (wrong since the May 2026 Grok migration; models follow stated
   context better when it isn't false).

### Contradiction fixes (the failure class behind chronic under-length)
4. **MIT residual length conflict**: line 216 still demanded "at least 2500
   words" against the unified 2,000–2,200 target — exactly the
   smallest-anchor-wins mechanism the June passes fixed. Now one target;
   drift guard tightened to catch the bare "at least 2500" form.
5. **Tesla digest selection rules unified**: the count-driven tier table
   ("10+ → select best 12") and the judgment rule ("EDITORIAL JUDGMENT BEATS
   THE COUNT") were layered contradictions; now one quality-first rule
   (10–12, stop early if the 11th is filler, search only below 7).
6. **Tesla digest emoji contradiction**: the format template's 🎙️ violated
   the prompt's own "no emoji" rule and shipped as boilerplate into every
   blog post. Removed.

### Editorial quality
7. **Reviewer score calibration**: the nightly AI reviewer's "1=terrible,
   10=perfect" rubric produced uncalibrated scores; it now carries explicit
   buckets (1–3 listener-noticeable problems … 10 exemplary), making the
   dashboard's quality trend comparable across shows and days.
8. **Weekly synthesizer grounding**: "Where do AI developments intersect
   with energy?" invited invented connections; the prompt now requires every
   cross-domain thread to be grounded in the listed coverage and to omit
   unsupported pairings.
9. **Tesla system prompt source-gating**: the podcast prompt gates all
   claims on digest+memory, but the system prompt only said "do not add
   information from outside the provided content" — it now explicitly
   forbids filling gaps from training-data knowledge.

## Checked and rejected (with reasons)

- **More variation instructions in the expansion retry** — it already
  forbids verbatim repetition and carries the digest; further meta-
  instruction risks diluting the fact-coverage directive.
- **Reviewer truncation note "over-suppresses INCOMPLETE"** — the note
  already distinguishes review-excerpt truncation from genuine mid-sentence
  cutoffs.
- **Empty-template-var fallbacks** — `cross_show_context` and friends
  already default to explicit "(No recent …)" strings in `run_show.py`.
- **Audience-size weighting in the synthesizer** — audience numbers aren't
  in the prompt's context; asking the model to weight by them invites
  fabrication.
- **Omni View lacking narrative memory** — intentional design (daily
  briefing, not a serialized chronicle).
- **Bulk migration of shared rules into `<<include:>>` snippets** — the
  mechanism's own README forbids bulk rewrites without per-show A/B
  listening; the per-show duplication is the safer state today.
- **New speech tags / prosody hints / phonetic respellings** — landmine #17;
  only the operator's A/B evidence can reopen that door.

## Deferred ideas (output-changing; queue behind A/B results)

- Few-shot "ideal story" exemplars for the podcast prompts that lack one
  (Tesla's example block is the pattern; OV/EI/M&A rely on description
  alone). High potential, but it's a per-show editorial change — add one
  show at a time and A/B-listen.
- Replacing the older shows' negative-instruction lists (M&A carries 9
  "avoid" patterns) with positive rotation menus, as the June passes did for
  openers. Same A/B gate.
- Cross-show entity callouts in weekly newsletters (the synthesizer already
  builds the entity map; the weekly prompts never reference it).

Prompt edits in this pass change generated output — A/B-listen per
landmine #17.
