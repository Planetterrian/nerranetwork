# Models & Agents — quality pass, 2026-06-14

First dedicated Models & Agents review (prior coverage was the June 10
four-show pass, `docs/four_show_review_2026_06_10.md`, which fixed the
Closing/`where`-anchor chapter class and added `podcast_expand_below_target`).
This pass takes the next tier: two listener-facing metadata bugs the four-show
pass did not touch, both shippable with no audio-prompt change.

Snapshot baseline (`scripts/review_snapshot.py models_agents`): scripts
1085–1476w (10/10 below the 1500 floor); avg cost $0.114/ep; OP3 7-day 98
downloads (30-day 429); chapter-shape problems on 4/10 recent episodes.

## P0 — phonetic garbles shipping to TTS *and* chapter titles

The podcast-generation step spelled core AI proper nouns phonetically despite
the prompt's explicit pronunciation-guide ban, and those spellings reached the
text sent to TTS (`*_tts.txt`):

| Garble | Correct | Occurrences (last 10 eps `_tts.txt`) |
|---|---|---|
| `An-thropic` | Anthropic | 94 — present since Ep004 (March); 6× in Ep080 |
| `Lah-mah[-…]` | Llama | ~12 (`Lah-mah-three/-swap/-server/-cpp/-style`) |
| `Hah-sah-biss` | Hassabis | 5 |

Verified the garbles are in the **podcast script**, not the digest (digests
Ep075–080 are clean) — so the leak is the script-gen stage. On the custom
voice the hyphen forces an audible break ("An… thropic"), and `parse_chapters`
runs *after* the script is built, so the garble also poisoned chapter titles
(Ep080 chapter: `"An-thropic called the order a misunderstanding and stated…"`,
`run_show.py:2249` repair → `:2271` parse).

**Fix (shipped, no A/B):** extended the blessed deterministic-restore layer
`engine.utils.fix_phonetic_garbles` (`engine/utils.py:648`) with
`an-thropic → Anthropic`, `lah-mah → Llama`, `hah-sah-biss → Hassabis`. This
is the same mechanism the FF June 12 review used for `En-sell-uh-dus`/
`Tee-en-wen`; it **removes** the model's bad respelling rather than adding one,
so it is explicitly outside landmine #17's "never add phonetic respellings"
rule (the operator's own finding is that the raw word beats any respelling on
this voice). The trailing `\b` preserves possessives and compounds:
`An-thropic's → Anthropic's`, `Lah-mah-swap → Llama-swap`. Verified against the
real shipped Ep080 lines. Global dict → also fixes any leak on Tesla/MIT/MAB.

## P1 — "Under the Hood" chapter missing on 4/5 episodes → raw-sentence titles

The engineering deep-dive opens with **"let's pop the hood on …"** in 9–10/10
episodes (the podcast prompt seeds that exact phrase, `models_agents_podcast.txt`),
but the chapter marker only matched the literal `under the hood` —
so only **1 of the last 5** episodes got an `Under the Hood` chapter despite
all 5 containing the deep-dive. That missing marker dropped several episodes
below `min_chapters` (4), firing the auto-segmentation fallback that titles
chapters from raw mid-sentence text:

- Ep080 (before): `Introduction` → `"Agents completed twenty-six minutes of
  independent work…"` → `"An-thropic called the order a misunderstanding…"` →
  `Practical & Community` → `Closing`.
- Ep080 (after `+pop the hood`): `Introduction` → `Practical & Community` →
  `Under the Hood` → `Closing`. Both raw-sentence titles gone.

**Fix (shipped, metadata-only):** added `|pop the hood` to the Under the Hood
marker (`shows/models_agents.yaml`). Simulated on the real Ep076–080 scripts:
adds a proper `Under the Hood` chapter to Ep076/077/079, and on Ep080 raises
the match count enough to suppress auto-segmentation entirely. No regression on
already-clean episodes. `pop the hood` appears exactly once per script (the
deep-dive), so no false mid-script match.

Residual: Ep078 still auto-segments (it already matched `Under the Hood`; its
*middle* sections — Top Story/Model Updates/Agent/Practical — matched no marker
because the prompt deliberately bans spoken section labels). That is the
general "keyword markers vs. label-free prose" limitation; the durable fix is
**digest-driven chapter titles** (deferred network-wide since the Tesla ledger,
medium effort) — kept deferred here for consistency.

## P1 (chronic, deferred) — under-length: the digest is the ceiling

All 10 recent scripts are below the 1500 floor (1085–1476w). Verified this is
the **FF root cause, not the target**: digests run 969–1432w and the scripts
track or barely exceed them (Ep080 script 1432w ≈ digest 1432w). The podcast
prompt bans padding/invention and tells the host to use only the briefing, so
the script cannot exceed a thin digest. The `podcast_expand_below_target` retry
(added June 10) fires every episode and plateaus.

M&A has the same non-padding lever FF identified: the **Under the Hood** section
is explicitly licensed to use the model's own ML-systems knowledge
(`models_agents_digest.txt`: "uses YOUR OWN knowledge … not just today's
articles"), analogous to FF's Cosmic Deep Dive. Deferred on the same terms as
the FF review — wait for the operator's four-show length A/B to settle before
expanding a deep-dive, so the two experiments don't confound. The grok-4.3
length plateau on news shows is accepted.

## Observed, intentionally NOT changed

- **"let's pop the hood on" as an opener tic (9–10/10).** Unlike Tesla's
  "Taking a step back" filler, this reads as a deliberate segment signature and
  the topic after it varies every episode (distillation, hybrid attention,
  tokenization…). Changing it is a shipped-audio change with the documented
  100%-regression risk and no evidence it harms. Left as-is; instead *leveraged*
  as the Under the Hood chapter signal (above). Operator may revisit with a
  rotation menu if A/B-listening suggests it.
- **Length target numbers.** The prompt's "1,600–2,200 words" target with a
  1500 floor is internally consistent by design (hard floor under the soft
  target), pinned by `test_four_show_quality_pass.py`. Not re-litigated.

## What shipped

1. `engine/utils.py` — 3 garble entries (Anthropic/Llama/Hassabis).
2. `shows/models_agents.yaml` — `|pop the hood` on the Under the Hood marker.
3. `tests/test_models_agents_quality_pass.py` — drift guards for both.

## A/B-listen required (landmine #17)

**None.** Both fixes are deterministic and metadata-only (text-repair +
chapter regex). No prompt or audio-generation change.

## Deferred recommendations

- Digest-driven chapter titles (durable fix for the label-free-prose miss; the
  Ep078 residual). Medium effort, network-wide — deferred since the Tesla ledger.
- Expand the Under the Hood section for length, after the four-show length A/B.
- Re-score the garble + chapter predictions next pass (below).
