# Models & Agents for Beginners (MAB) — Quality Review, June 25 2026

First dedicated MAB review. MAB was previously touched only by the June 10
four-show pass (`docs/four_show_review_2026_06_10.md`: Closing-chapter pattern
coverage, length floor 900→1200, `podcast_expand_below_target`, and the "So
imagine" opener de-seed). This pass scores those and attacks the next tier.

Snapshot: `python scripts/review_snapshot.py models_agents_beginners`.
Transcripts (Whisper) are the ears. Cost ~$0.082/episode; OP3 7-day downloads
53, 30-day 292.

## Scoring the June 10 four-show predictions (MAB)

- **"So imagine" opener de-seed → HIT.** 0/10 recent episodes open with "So
  imagine" (Ep073–082 openers verified varied: "Something wild just happened",
  "Picture this", "Here's something…", "A company known for…", etc.).
- **Length floor 900→1200 + expand-retry → MISS (digest ceiling).** 9 of the
  last 10 `_tts.txt` are still under the 1200-word floor (1050, 1099, 1076,
  1085, 1085, 820, 1156, 1083, 883; only Ep079, the Sunday recap, hit 1470).
  Same root cause as FF/PT/UC: the digest aims 800–1200 words and the podcast
  is told to use only the briefing, so it cannot exceed the digest without the
  padding both prompts ban. Stays deferred behind the network four-show length
  A/B — not re-litigated here.

## P0 — listener-facing bugs shipping today

None new. Chapters parse without orphan/mis-title crashes on 8/9 recent
episodes (the one exception, Ep081, is a P1 below). No spoken garbles found in
the last 10 transcripts.

## P1 — quality ceiling

### 1. Deep Dive closing template echoed verbatim every episode (FIXED — A/B)

The single clearest tic. Every episode's "Deep Dive" / "Explain Like I'm 14"
segment closes with the **same three-sentence formula, near word-for-word**:

> Ep080: "And that's basically what record replay is doing when it turns your
> one-time demonstration… So next time someone says AI agents learning from
> demonstration, you can tell them it is basically… Not so scary, right?"
> Ep081: "…and that is basically what a neural network is doing when it… So
> next time someone says neural network, you can tell them it is basically…
> Not so scary, right?"
> Ep082: "…and that is basically how the ultrasound system helps the robot
> hand… So next time someone mentions sensing under the skin… Not so scary,
> right?"

Snapshot confirms: "not so scary right" 9/10, "and that is basically" 9/10,
"so next time someone" 6/10, "you can tell them it is" 6/10.

**Root cause (same class as Omni-View "strongest case", EI deep-dive opener,
First Principles lesson-template):** both prompts SEED the exact sentences.
- `shows/prompts/mab_podcast.txt:138-139` — `Connect it back: "and that's
  basically what the AI is doing when it…"` / `End with: "and that's basically
  how [concept] works — not so scary, right?"`
- `shows/prompts/mab_digest.txt:121-122` — `Connect it back to the tech: "And
  that's basically what [technology] is doing when it [does the thing]."` /
  `End with the 'aha!' payoff: "So next time someone says [intimidating term],
  you can tell them — it's basically [simple analogy]. Not so scary, right?"`
  (the digest feeds the podcast Deep Dive, so the echo is double-seeded.)

**Fix:** de-seed both prompts — keep the analogy METHOD (connect-back +
reassuring payoff structure is the show's intentional signature) but remove
the verbatim sentences, require fresh per-episode phrasing, and explicitly
name the "not so scary, right?" / "so next time someone says X, you can tell
them" formulas as banned-as-verbatim. Drift guard:
`tests/test_mab_quality_pass.py::TestDeepDiveCloserDeSeed`.

**Before/after (rendered via `run_show.py models_agents_beginners --test`,
GROK live):**
- BEFORE (committed Ep082 digest): "And that's basically what the ultrasound
  system is doing when it… So next time someone says 'sensing under the skin,'
  you can tell them—it's basically… Not so scary, right?"
- AFTER (Ep083 test render): "…The result feels less like talking to a robot
  that only hears the words and more like chatting with someone who actually
  gets the point." (no template formula; the reassuring beat is reached
  organically.)

### 2. New "Something [adj] just happened" opener template (FIXED — A/B)

The June-10 "So imagine" de-seed worked, but the model converged on a *new*
shape from the same prompt's example list. 5 of the last 10 Big Story openers
are "Something [wild/big/surprising] just happened…" (Ep073, 074, 075, 078,
080); "Something wild just happened" specifically is 3/10. Root cause is
identical: `mab_podcast.txt:125` offered "Something wild just happened:" as one
of the example opener shapes, and the model picked the memorable example —
exactly how "So imagine" became a tic.

**Fix:** removed that example from the rotation menu and added it to the BANNED
list alongside "So imagine…", with the "roughly half of recent episodes"
context so the model treats it as a known-overused template, not a suggestion.
Drift guard: `tests/test_mab_quality_pass.py::TestBigStoryOpenerDeSeed`.

### 3. "The Big Story" chapter is missing on every episode (DEFERRED)

The heart segment (~3 min, the single biggest chunk) is **never chaptered**.
On all 9 recent episodes the chapter shape is `Welcome → Deep Dive → …`, with
no "The Big Story" chapter — the entire Big Story is absorbed into the
`where: start` "Welcome" chapter (Ep082: "Welcome" spans 20s–120.5s, ~100s,
of which only ~15s is the actual welcome). Cause: the `big story|biggest news`
marker (`shows/models_agents_beginners.yaml:184`) never matches because the
host's Big Story opener is deliberately varied (no "big story" keyword) — a
dead marker, same class as M&A's pre-fix "under the hood" and OV's
"Understanding the Issue".

Unlike M&A's "pop the hood" fix, there is **no reliable phrase** to anchor on
(the opener variety is intentional and now enforced harder by fix #2). The
durable lever is the network-deferred **digest-driven / position-aware chapter
titles** (M&A June-21 confirmed this as the real fix). Documented, deferred —
no speculative marker shipped. Related: Ep081 fell below `min_chapters` (4) and
fired the auto-segment fallback, titling a chapter from a raw mid-sentence
("Another angle is writing your own quick summary of what…"); same deferred
class. Ep075 shipped with no Welcome chapter because the LLM rewrote the
"do not rewrite" intro line (2 of 76 episodes — low frequency, deferred).

### 4. MAB pronunciation hook is stale and injects landmine-#17 respellings (DEFERRED)

`shows/hooks/models_agents_beginners.py` is a **Fish-Audio / Chatterbox-era**
hook (per its docstring) still injecting phonetic respellings —
`CUDA→"kooda"`, `LoRA→"laura"`, `Qwen→"Chwen"`, `Hassabis→"Ha-sah-bis"`,
`SOTA→"so-tah"`, `ONNX→"onyx"`, `multimodal→"multi-modal"`, etc. — via
`pronunciation_overrides()` (wired through `run_show.py:_apply_pronunciation`).
MAB now runs on the custom Grok voice `kdif6sqjcyiq`, where landmine #17
documents a 100% regression rate for phonetic respellings, and its sister show
**Models & Agents uses NO pronunciation hook at all** (it relies on the shared
baseline + the blessed `engine.utils.fix_phonetic_garbles` restore layer).

Worse, `CUDA→"kooda"` actively **defeats** the network-wide restore: the shared
map emits `CUDA→"koo-dah"` which `fix_phonetic_garbles` restores to "CUDA"
(M&A June-21 fix), but MAB's hook overrides it to "kooda", which the restore
layer does NOT catch — so if "CUDA" ever appeared, M&A would ship "CUDA" and
MAB would ship "kooda".

**However:** none of these terms have appeared in **any of the 76 MAB
transcripts** — a beginner show structurally rejects CUDA/LoRA/ONNX/Qwen
jargon (the digest prompt's REJECT list excludes it). Zero listener impact
today. Per the "evidence first / small verified fixes" rule, the broad hook
cleanup (align MAB with M&A by removing the respellings, keeping only the
letter-by-letter acronym expansions like `AI-powered→"A I powered"`) is
**recommended but deferred** rather than shipped speculatively. Recommendation
for a future pass: strip the `extra_words` respellings + the non-letter
`extra_acronyms` (keep acronym letter-spellings + identity cancellations +
`i.e./e.g./vs.` expansions), matching the proven-good sibling. Low risk (0/76
impact) but it touches TTS — A/B-listen.

## P2 — growth / discoverability

Nothing new shipped. RSS channel description is already a strong value prop
(rewritten in the June network pass). X posting disabled. YouTube paused
(landmine #20). The chapter-coverage gap (#3) is the main discoverability
residual but is gated on the deferred digest-driven-titles lever.

## What shipped this pass

1. Deep Dive closer de-seed — `mab_podcast.txt`, `mab_digest.txt` (A/B).
2. Big Story "Something … just happened" opener de-seed — `mab_podcast.txt`
   (A/B).
3. Drift guards — `tests/test_mab_quality_pass.py` (5 tests).

## ⚠️ A/B-listen required (landmine #17)

Both shipped fixes are prompt edits that change generated audio. Listen to the
next 2–3 episodes:
- Deep Dive should still land the "you get this now" reassurance but in fresh
  words each episode (NOT "…not so scary, right?" verbatim every time). The
  rendered Ep083 test digest reads naturally — verify the spoken episode keeps
  the warmth without the template.
- Big Story openers should not be "Something [wild/big] just happened…".

If either regresses (loses the show's signature warmth), revert via git.

## Deferred (carried to the ledger)

- Chronic under-length (digest ceiling; four-show length A/B lever).
- "The Big Story" chapter never present + Ep081 auto-segment garbage title
  (digest-driven / position-aware chapter titles — durable network lever).
- MAB pronunciation-hook respelling cleanup (0/76 impact; align with M&A).
- Ep075-class intro-rewrite → no Welcome chapter (2/76; UC-style generic
  opening-word fallback if it grows).
