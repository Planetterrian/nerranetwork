# Tesla Shorts Time — Quality Pass (June 20, 2026)

Second agent-driven review of Tesla Shorts Time, scoring the June 10 pass
(`docs/tesla_review_2026_06_10.md`, PR #576) and attacking the next tier.
Everything below is verified against the working tree and the last 10
committed episodes (Ep507–516). Transcripts are the ears.

## Scoring the June 10 predictions

| Prediction | Verdict | Evidence |
|---|---|---|
| Trailing duplicate "Introduction" chapter: 10/10 → 0/10 | **HIT** | `chapters_ep507–516.json` — no duplicate/trailing Introduction; positional `where` anchors + once-per-title matching held. |
| Median `_tts.txt` words ≥ 2000 | **MISS** | Last 10 scripts run 1254–1676w (median ~1440); **every** episode below the 2000 floor. The expand-retry-with-full-digest fix did not close the gap. Root cause re-diagnosed below — back on the findings list with a different approach. |

The chapter-shape fix held and is healthy. The length fix missed; the
root cause is the **digest ceiling**, not the retry (see P1.1).

---

## P0 — Listener-facing bugs shipping today

### 1. "Tesla-rah-tee" — the #1 source name is voiced as a phonetic garble  → FIXED

The podcast-gen step spells **Teslarati** — the show's most-attributed
source — phonetically as `Tesla-rah-tee` despite the prompt's explicit
phonetic-spelling ban (`shows/prompts/tesla_podcast.txt:13`). It shipped to
TTS in **25+ episodes, including 5 of the last 10** (Ep500/505/512/516),
often several times per episode (Ep393/395/400/405 had 4× each). Whisper of
Ep516 audio confirms it voices as a garble — "Tesla had RadT reported"
(`Ep516_transcript.txt:39`) — the hyphens force an audible break on the
custom voice `kdif6sqjcyiq`.

This is the exact failure class the M&A (An-thropic) and FF (En-sell-uh-dus,
Tianwen) passes fixed: a known finite phonetic respelling that the prompt
ban alone doesn't stop. **Fixed** by adding `tesla-rah-tee` → `Teslarati` to
the blessed `engine.utils.fix_phonetic_garbles` restore layer
(`engine/utils.py`). The layer *removes* a respelling (restores the canonical
word), so per the M&A/FF precedent it sits **outside** the landmine-#17
no-respelling rule — but it changes spoken output, so A/B-listen it anyway.
Drift guard: `TestTeslaratiPhoneticGarble`.

---

## P1 — Quality ceiling

### 1. Chronic under-length is the DIGEST ceiling, not the retry (MISS re-attack)

The June 10 pass set the target to 2,200–2,400w, raised `min_podcast_words`
to 2000, and gave the expansion retry the full digest. The prediction
(≥2000w) **missed**: Ep507–516 scripts run 1254–1676w. Verified root cause —
the digest is the ceiling, and the script tracks it almost 1:1:

| Ep | Digest words | Script words |
|---|---|---|
| 516 | 1234 | 1254 |
| 515 | 1490 | 1676 |
| 512 | 1741 | 1491 |
| 510 | 1747 | 1523 |
| 508 | 1800 | 1358 |

The digest never exceeds ~1800w. Reading Ep516's digest, the cause is plain:
the **Top 12 items ship at 3 sentences each, not the prompt's 4–5**
(`tesla_digest.txt:112`), and several are padded with non-facts — "No
specific timeline for resolution has been reported", "No position size
details were highlighted". Many items are Google-News **snippet-only**
sources, so the model honestly cannot expand them to 5–7 fact-bearing
sentences without inventing facts — exactly the padding both prompts ban
and the listener-value scorer penalizes. This is the same snippet-ceiling
diagnosis that FF (June 12/16), UC (June 12), and PT (June 18) reached, and
each **deferred a length re-attack behind the operator's four-show length
A/B**.

**Recommendation (deferred, consistent with the network stance):** the only
non-padding levers are (a) a **digest-side expansion retry** (the standing
network lever — re-prompt the digest to deepen thin items using full
article text where the source is a full-text feed, not Google-News
snippets), and (b) expanding the **Tesla First Principles essay**, which is
the model's own analysis and is *not* snippet-bound (currently ~3 short
paragraphs / ~180w) — the direct analogue of FF's deferred "Cosmic Deep
Dive" lever. Both change shipped audio and should wait for the four-show
A/B to settle rather than adding a sixth uncoordinated length knob. Not
re-litigating the target itself (it's correct).

### 2. The brand normalizer enshrines "Daily" — the spoken brand contradicts the listing  → FIXED

The June 10 pass aligned the spoken brand to **"Tesla Shorts Time"** (no
"Daily") so the audio matches the Apple/Spotify/website listing for search:
`engine/intros.py:43` dropped "Daily" from `show_name`, and the podcast
prompt bans appending it (`tesla_podcast.txt:21`). `build_intro_line("tesla")`
correctly returns "Tesla Shorts Time".

But the fix missed the deterministic brand normalizer in
`engine/generator.py:_correct_common_llm_text_mistakes` — written pre-June-10
for the "Tela"/"Short's" misspellings — which was still normalizing
**toward** "Tesla Shorts Time **Daily**". The LLM re-adds "Daily" to the
intro every episode (a training habit from hundreds of prior episodes), and
this layer blessed it: **"Tesla Shorts Time Daily" shipped in the spoken
intro of 100% of episodes**, including all 10 post-June-10 (Ep506–516;
verified `Ep516_tts.txt:1`). The whole point of the June 10 brand decision
was defeated.

**Fixed** by flipping the normalizer's targets to drop the stray "Daily"
(`engine/generator.py`) — the deterministic layer now *enforces* the brand
decision instead of fighting it. Misspelling fixes (Tela / Short's) and the
framing-line grammar fix are preserved; clean "Tesla Shorts Time" and the
lowercase X-handle reference "tesla shorts time" are true no-ops. Removes a
spoken word → A/B-listen, but it completes an already-approved decision.
Drift guard: `TestSpokenBrandDropsDaily`.

### 3. Chapter body navigation: fragment titles + the no-body-chapter regression (deferred, documented)

The June 10 positional anchoring killed the duplicate-Introduction bug, but
two body-navigation problems remain across Ep507–516 (metadata-only, no
audio):

- **8/10 episodes ship mid-sentence fragment titles** for the news body —
  "Because L F P cells also support higher cycle counts, the…" (Ep507),
  "Small UX wins like this lead into deeper infrastructure…" (Ep508),
  "Four pipeline stages handle stream selection, link…" (Ep512). This is the
  auto-segmentation fallback titling segments from each segment's first
  sentence — the deferred "digest-driven chapter titles" item from June 10,
  and the same shared class PT (June 18) and M&A deferred.
- **2/10 episodes (Ep515/516) ship NO body chapter at all** — the entire
  ~7-minute news body is swallowed into a single "Introduction" chapter
  (Ep516: Introduction spans 20.0→445.9s of a 585s episode). This is a
  *new* degradation mode and arguably worse than fragments. Root cause:
  `engine/chapters.py:208` triggers auto-segmentation only on
  `len(chapters) < min_chapters`, but the function's own docstring
  (`chapters.py:198-199`) says it should *also* fire "when … the first
  chapter spans most of the script." That second condition was **never
  implemented**. When the editorial markers (Counterpoint / First Principles
  / Teaser / Closing) alone reach `min_chapters` (4), auto-segmentation is
  skipped and the dominant Introduction is left un-split. June 10's reliable
  positional matching of those editorial markers made this path *more*
  likely.

**Recommendation (deferred):** the real fix is digest-driven titles —
fuzzy-match each Top-12 headline against the auto-segment text and title the
segment with the actual story headline. That solves both problems and is the
single biggest in-app navigation upgrade. It is shared `engine/chapters.py`
code touching every show, so it belongs in a coordinated change (ideally the
`network` review) rather than a Tesla-only edit, alongside fixing the
`chapters.py:208` docstring/implementation mismatch. Not shipped this pass to
keep the diff small and low-risk.

### 4. Institutional-filing spam in the digest  → FIXED

MarketBeat/Defense-World-style 13F filing items ("SG Trading Solutions LLC
Purchases New Stake in Tesla", "Tempo Wealth LLC Invests $4.88 Million in
Tesla") keep slipping into the digest — and the X Takeover — despite the
prompt's "reject pure stock/market data" rule (`tesla_digest.txt:30-31`).
Ep516 (the shortest recent episode at 1254w) shipped **three**, each a
zero-value non-story ("No position size details were highlighted beyond the
filing itself"). They follow a rigid title template, so they're now filtered
deterministically at fetch time via `exclude_title_patterns`
(`shows/tesla.yaml`) — the same accepted **no-A/B** class as FF's
stock-market filter. Patterns are anchored on "…in Tesla" / "shares … by
<firm>", verified to drop all live spam while keeping real news ("Tesla
shares jump 5%", "Tesla stock rises on robotaxi news", "EPA filing reveals
Cybercab specs"). Drift guard: `TestInstitutionalFilingSpamFilter`.

---

## P2 — Growth / discoverability

Spot-checked and healthy, no action needed:
- Closing rotates 4 date-keyed variants with the price sentence gated on
  `is_price_publishable` and phrased by market state (`shows/hooks/tesla.py`)
  — the June 10 fix is live and working (Ep516 used variant 4).
- Performance loop is live: `tesla_performance_tracker.json` is auto-derived
  nightly from OP3 (`last_updated` 2026-06-19, real `top_episodes` +
  `strong_topics_last_30d`).
- Narrative + theme trackers are fresh and clean (auto-freshness advancing
  `last_mentioned` per episode; no template-echo themes).
- Hook-led X teaser + episode-blog link confirmed by existing guards.

OP3: 91 downloads/7d, 627/30d — still the network's healthiest property,
though the 7d trend dipped (155→254→100→91 over four weeks). Worth watching
but not actionable from a single-show review.

---

## Summary

| # | Finding | Class | Action |
|---|---------|-------|--------|
| P0.1 | "Tesla-rah-tee" voiced garble (25+ eps) | spoken bug | **Fixed** — garble restore |
| P1.2 | Spoken brand still says "Daily" (100% eps) | brand | **Fixed** — normalizer drops Daily |
| P1.4 | 13F filing spam in digest | content | **Fixed** — fetch filter (no-A/B) |
| P1.1 | Chronic under-length (digest ceiling) | length | Deferred — four-show A/B |
| P1.3 | Chapter body nav (fragments + no-body) | metadata | Deferred — digest-title fix, network-scoped |

### ⚠️ A/B-listen required (landmine #17)
- **P0.1** "Tesla-rah-tee" → "Teslarati": removes a respelling (blessed
  class), but changes spoken output — listen to confirm the custom voice
  says "Teslarati" cleanly.
- **P1.2** dropping "Daily" from the spoken intro: removes one spoken word
  to match the already-approved listing brand.

P1.4 (fetch filter) is deterministic title-matching with no audio/prompt
change — no A/B needed.
