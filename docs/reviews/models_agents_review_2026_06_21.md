# Models & Agents — quality pass, 2026-06-21

Third Models & Agents review (after the June 10 four-show pass and the
June 14 dedicated pass, `docs/reviews/models_agents_review_2026_06_14.md`).
This pass scores the June-14 predictions (all four HIT) and takes the next
tier: one recurring reader-facing text bug shipping today, plus a sharpened
diagnosis of the deferred chapter-shape problem.

Snapshot baseline (`scripts/review_snapshot.py models_agents`): scripts
1067–1582w (9/10 below the 1500 floor; chronic under-length, deferred — see
below); avg cost $0.098/ep; OP3 7-day 112 downloads (30-day 453, weekly trend
[93, 129, 98, 112] — stable/slightly up); chapters reported 10/10 "clean" by
the shape heuristic (but see P1 below — the heuristic counts auto-segmented
fragment titles as a populated chapter).

## Scoring the June-14 predictions — all four HIT

| Prediction | Verdict | Evidence |
|---|---|---|
| `An-thropic` → 0 in post-merge episodes | **hit** | Fix merged ~Jun 17-18 (PR #635). Ep084-088 (post-merge): 0 garbles. Ep081's 2 are pre-merge. |
| `Under the Hood` chapter ≥4/5 | **hit** | Ep084/085/086/087 ✓, Ep088 ✗ (Sunday recap, no deep-dive) = 4/5. |
| raw mid-sentence chapter title ≤1/5 | **hit** | Only Ep085 (3 `…`-ending auto-segment titles) = 1/5. |
| median length no regression (~1290) | **hit** | Median ~1300 (1067-1582). No regression; chronic under-length stays the digest-ceiling lever, deferred. |

The `An-thropic`/`pop the hood` fixes worked. Their drift guards stay in
`tests/test_models_agents_quality_pass.py`.

## P0 — `CUDA` ships to the blog transcript as "koo-dah" (12 episodes)

The published episode blog transcripts (`blog/models_agents/ep*.html`) render
**"koo-dah" verbatim** wherever a digest mentions CUDA:

> "A developer open-sourced a **koo-dah** kernel that keeps Top-K vector
> search entirely on the GPU…" — `blog/models_agents/ep088.html`

This has shipped in **12 episodes since Ep040 (May 5)** — Ep040/042/044/045/
051/057/062/067/071/075/086/088 — up to 5× per episode (Ep067), 23 total
occurrences, and is live in the two most recent CUDA-mentioning episodes
(Ep086, Ep088).

**Root cause — a different class than the June-14 garbles.** The June-14
fixes (`An-thropic` etc.) were LLM-introduced respellings. This one is
emitted by the **shared pronunciation map**: `assets/pronunciation.py:168`
maps `"CUDA": "koo-dah"` in `COMMON_ACRONYMS` — an ElevenLabs-era
word-acronym guide so the TTS says "koo-duh" instead of letter-splitting
"C-U-D-A". The digest correctly says `CUDA` (verified: Ep088.md →
"open-sourced a CUDA kernel"); `_apply_pronunciation` (`run_show.py:2205`)
rewrites it to "koo-dah" *before* the `_tts.txt` is written
(`run_show.py:2299`), and `engine/blog.py:767` builds the inline blog
transcript from that `_tts.txt`. So the respelling leaks into the published
reader-facing text.

This is exactly the class that created `fix_phonetic_garbles` in the first
place — `"nassa"` (the same kind of pronunciation-map guide, still at
`pronunciation.py:180`) shipped in FF Ep096's published transcript, and the
restore layer reverses it. `"nassa"` is in BOTH the pronunciation map AND
the garble-restore dict; `"koo-dah"` was only ever in the pronunciation map.

**Fix (shipped):** added `"koo-dah": "CUDA"` to `engine.utils._PHONETIC_GARBLES`
(`engine/utils.py`). `fix_phonetic_garbles` runs at `run_show.py:2257`, after
`_apply_pronunciation`, so the canonical `CUDA` reaches **both** the published
transcript and the TTS text — identical to how `nassa → NASA` already works.
Verified live that the restored canonical form ships fine on the custom voice:
recent FF `_tts.txt` files carry `NASA` (not `nassa`) and recent M&A carries
`Anthropic` (not `An-thropic`), and those episodes shipped. `"koo-dah"` has no
legitimate English use, so restoration is collision-safe (the regex's `\b`
anchors + the lone-token form). Verified on the real Ep088 text: 2 "koo-dah"
→ 0, 2 "CUDA".

Deliberately **left alone**: the other pronunciation-map word-guides that
collide with ordinary English — `RAG → "rag"`, `LoRA → "Laura"` — cannot use
the lone-token restore approach without mangling real prose. See the deferred
network item below.

## P1 (deferred, diagnosis sharpened) — chapters only clean when the host disobeys the prompt

The June-14 pass added `pop the hood` to the Under-the-Hood marker and
predicted ≤1/5 raw-title episodes (HIT). But the underlying chapter shape is
still unstable, and this pass pinned why:

- Ep084 / Ep086 ship a full 9-chapter shape — because the host literally
  **announces the section labels aloud**: "Now turning to model updates."
  / "Moving to agent and tool developments." / "In practical and community
  updates," / "Here are things to try this week." / "On the horizon,"
  (`Ep084_…_tts.txt:21,63,85,123,133`; `Ep086:31,61,99,153,163`).
- Ep085 / Ep087 / Ep088 ship a sparse or auto-segmented shape — because the
  host *flows naturally* (no spoken labels), so the keyword markers for Top
  Story / Model Updates / Agent & Tool / Things to Try / On the Horizon match
  nothing. Ep085 fell below `min_chapters` and auto-segmented three raw
  mid-sentence fragments as titles ("This moves the open-weight models
  conversation forward…").

The podcast prompt explicitly bans announcing section labels ("Segment
labels … flow into content naturally"; Under the Hood: "Do NOT announce it
as 'Under the Hood' formally"). So **chapter quality is inversely correlated
with prompt compliance** — the best-chaptered episodes are the ones whose
delivery most resembles a press release. This is not fixable by adding more
keyword markers (they require the banned spoken labels). The durable fix is
**digest-driven chapter titles** (deferred network-wide since the Tesla
ledger). Kept deferred; this pass only sharpens the diagnosis so the eventual
fix targets the right lever.

## P1 (chronic, deferred) — under-length is the digest ceiling

9/10 recent scripts below the 1500 floor (carried from June 14 — verified
unchanged: scripts track the digest ~1:1; `podcast_expand_below_target` fires
and plateaus). The non-padding lever is expanding the **Under the Hood**
section (licensed to use the model's own ML-systems knowledge). Deferred on
the same terms as the FF/Tesla ledgers — wait for the operator's four-show
length A/B to settle before expanding a deep-dive so the experiments don't
confound. The grok-4.3 length plateau on news shows is accepted.

## Observed, intentionally NOT changed

- **`x_enabled: true` for M&A vs CLAUDE.md "X disabled".** The YAML enables X
  posting under the `X_` (= @teslashortstime) account. This is **intentional**
  — commit `ea948ad0` ("…enable X on 3 shows") deliberately turned it on for
  models_agents, modern_investing, and one other. CLAUDE.md's table and the
  network-pass note are stale on this point; behavior is correct, not a bug.
  (Noted in the doc only — changing X posting is out of scope and a guardrail.)
  M&A has no `publishing.x_handle`, so the cross-promo "Follow @…" reply is a
  no-op for it — an operator decision, not changed here.
- **"keep an eye on" Tomorrow-Teaser opener (10/10).** The teaser opens
  "keep an eye on" / "Before we go, keep an eye on" / "Tomorrow, keep an eye
  on" every episode (the prompt seeds the phrase). Mild tic, one phrase, one
  segment; changing it is a shipped-audio change with the documented
  100%-regression risk and no evidence it harms. Left as-is (optional A/B
  rotation menu if the operator wants it).
- **"let's pop the hood on" deep-dive opener (9/10).** Carried from June 14 —
  signature segment phrase, varies by topic, leveraged as the chapter signal.
  Not changed.

## What shipped

1. `engine/utils.py` — `"koo-dah": "CUDA"` added to `_PHONETIC_GARBLES`.
2. `tests/test_models_agents_quality_pass.py` — two drift guards (restore +
   collision-safety).

## A/B-listen required (landmine #17)

**Effectively none — but spot-check once.** The fix is the blessed
deterministic-restore layer (removes a respelling; outside landmine #17's
"never add a respelling" rule). It changes what the TTS sees for CUDA from
the respelling "koo-dah" to the canonical "CUDA" — exactly as `nassa → NASA`
already does on every NASA-mentioning episode that ships today. Risk that the
custom voice spells "CUDA" letter-by-letter is low (Grok text normalization
reads NASA/Anthropic/DART as words and those ship), but worth one spot-check
on the next CUDA-mentioning episode since it does touch audio.

## Deferred recommendations (carried backlog)

- **Digest-driven chapter titles** (durable fix for the prompt-compliance/
  chapter tension above). Medium effort, network-wide — deferred since the
  Tesla ledger.
- **Pronunciation-map respellings leaking into published transcripts — a
  network-wide latent class.** `LoRA → "Laura"`, `RAG → "rag"`,
  `JAXA → "jacksa"`, `CRISPR → "crisper"`, `PSYCHE → "Sy-key"`,
  `LOFAR → "low-far"`, `DART → "dart"`, etc. all reach the blog/RSS
  transcript. The collision-safe ones can join the restore dict (as CUDA
  did); the collision-unsafe ones (Laura/rag) cannot. The durable fix is to
  source the blog/RSS transcript from the **pre-pronunciation** script (or the
  Whisper transcript, which already normalizes these — Ep088's Whisper text
  reads "a CUDA kernel"), decoupling TTS pronunciation from published text.
  Bigger architectural change — deferred, flagged for a future network pass.
- **Expand the Under the Hood section for length**, after the four-show length
  A/B settles.
- **"keep an eye on" teaser rotation menu** — optional, A/B.
