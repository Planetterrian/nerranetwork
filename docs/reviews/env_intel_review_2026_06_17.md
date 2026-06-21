# Environmental Intelligence — quality pass, 2026-06-17

Fourth dedicated env_intel review. Scores the June 15 (#641) predictions
against Ep046 — the first true post-merge episode (env_intel runs odd
weekdays; Ep045 on June 15 was generated before #641 merged) — and attacks
the next tier: a latent **orphan-Introduction chapter bug** that the
June 10 `where`-anchor pass left half-fixed.

## Scoring the prior predictions

| Prediction (from 2026-06-15) | Verdict | Evidence |
|---|---|---|
| Deep-dive openers using "You arrive at a…" drop to ≤3/10 | **hit** | Ep046 (only post-merge episode) opens the Practitioner Deep Dive with "There's a nuance here worth understanding when benzene detections appear inconsistent across nested wells." No "You arrive at a…". (`Env_Intel_Ep046_20260617_tts.txt:65`) |
| Transcripts using "here's something I wish someone had told me early in my career" → 0/10 | **hit** | Absent from Ep046. (Present in pre-merge Ep045 line 51 — `Env_Intel_Ep045_20260615_tts.txt:51`.) |
| Median `_tts.txt` words ≥ 900 (carried from June 10) | **miss** | Last-10 median 814.5w; post-fix-only (Ep044/045/046 = 835/958/867) median 867w, still under the 900 floor. Chronic under-length persists — digest ceiling, deferred (see below). |

Both June-15 tic fixes held on the single post-merge episode available;
re-score after 2–3 more episodes since one episode is not a rotation proof.

## P0 — Introduction chapter missing on every "Welcome to" episode

`engine/intros.py` rotates **three** env_intel greetings
(`engine/intros.py:292-296`):

- `"Good morning. This is"` → "…This is Environmental Intelligence, episode N…"
- `"Good to have you back. This is"` → "…This is Environmental Intelligence…"
- `"Welcome to"` → **"Welcome to Environmental Intelligence, episode N…"**

The June 10 pass added `where: start` to the Introduction marker but kept
the pattern `"This is Environmental Intelligence"`
(`shows/env_intel.yaml:268`). That pattern never matches the "Welcome to"
form, so every "Welcome to" episode ships with **no Introduction chapter** —
the opening welcome + Compliance Brief gets absorbed into the first content
chapter ("Regulatory & Policy Watch").

Verified across the last ten episodes — 4 of 10 open with "Welcome to"
(Ep037, 038, 042, 046) and the post-fix examples confirm the mechanism:

```
ep45 (greeting "Good to have you back. This is") → Introduction | … | Closing   ✓
ep46 (greeting "Welcome to")                     → Regulatory & Policy Watch | …  ✗ no Introduction
```

(`chapters_ep045.json`, `chapters_ep046.json`). The episode has 5 chapters
so the auto-segment fallback (min 4) doesn't fire — it just silently ships
without the Introduction.

This is the same orphan-chapter class the June 10/11 passes fixed for the
Closing variant, missed for the Introduction.

**Fix (shipped, metadata-only — no audio/prompt change):** broaden the
Introduction pattern to `"(?:This is|Welcome to) Environmental Intelligence"`
(`shows/env_intel.yaml`). `where: start` (first 10%) still prevents the
closing's "Environmental Intelligence" mention from re-triggering it.
Drift guards:
`tests/test_env_intel_quality_pass.py::TestChapterPositionalAnchors::test_introduction_pattern_matches_every_greeting_variant`
(pins the pattern against every greeting in `_SHOW_PERSONALITIES`) and
`::test_welcome_to_opener_yields_introduction_chapter` (end-to-end Ep046
shape through `parse_chapters`).

## Deferred (carried forward — re-evaluated each pass)

- **Chronic under-length / digest ceiling.** Median 814w vs 900 floor;
  8/10 below floor. Same root cause as FF/UC: the digest is the ceiling and
  the podcast (told to use only the brief) can't exceed it without the
  padding both prompts ban. The non-padding lever is expanding the
  Practitioner Deep Dive (licensed to use the model's own domain knowledge),
  deferred behind the operator's four-show length A/B. Not re-litigated.
- **Mid-section chapter markers rely on literal keywords the prompt doesn't
  enforce.** Ep046 has no "Week Ahead" chapter — the week-ahead content
  ("…remains open through existing liaison channels", "…for the next thirty
  days", "Watch for potential IESO updates") uses none of the
  `week ahead|mark your calendar` keywords and merged into Action Items.
  This is the long-deferred "digest-driven / position-aware mid-section
  chapter titles" item (medium effort, shared across shows). The new
  Introduction fix + the existing Closing/Teaser anchors keep the
  episode's head and tail correct; the middle is best fixed network-wide.
- **Numbers/dates spell-out drift** ("BC CSR Protocol 4", "Q three") —
  landmine #17, needs A/B before any repair layer.
- **Thin-news blog title reads as intelligence** — no post-fix thin-news
  day yet to observe; carried.

## Watch items (no fix this pass)

- New deep-dive opener "There's a nuance here worth understanding…" — could
  itself become a template echo. Only 1 post-merge episode; re-check next
  pass that openers genuinely rotate rather than swapping one fixed
  lead-in for another.

## ⚠️ A/B-listen required (landmine #17)

**None.** The only shipped change is a chapter-marker regex — it runs on the
already-generated script and affects `chapters_ep*.json` metadata only, not
the spoken audio or any prompt.

## Test results

- `tests/test_env_intel_quality_pass.py` — 17 passed
- `tests/test_chapters.py`, `tests/test_prompt_fidelity.py`,
  `tests/test_episode_validity.py`, `tests/test_generator.py` — 160 passed
