# Финансы Просто — Quality Review (June 16, 2026)

First **dedicated** FP review (June 10's pass covered FP + Привет, Русский!
together — `docs/russian_shows_review_2026_06_10.md`). Same P0/P1/P2 method
as the Tesla / four-show passes. Transcripts are the ears.

Snapshot baseline (`scripts/review_snapshot.py finansy_prosto`): last 10
episodes (Ep45–54) all **below** the 1,000-word floor (628–842w); 10/10
clean chapters; no cross-episode repeated-phrase tics; avg **$0.096/episode**;
OP3 7-day downloads **7**, 30-day **54**.

---

## Scoring the previous review's prediction

The June 10 Russian-shows pass raised FP's `min_podcast_words` 900 → **1000**
and turned on `podcast_expand_below_target`, predicting longer episodes. **Verdict:
MISS.** Post-fix episodes still ship short:

| Ep | Date | digest words | tts words | actual audio |
|----|------|-------------|-----------|--------------|
| 50 | Jun 10 | 732 | 720 | 5.2 min |
| 51 | Jun 12 | 829 | 842 | 5.8 min |
| 52 | Jun 14 | 707 | 662 | 5.0 min |
| 53 | Jun 15 | 683 | 677 | 4.8 min |
| 54 | Jun 16 | 671 | 782 | 5.3 min |

Root cause (verified): the podcast tracks the **digest** almost 1:1 (`tts ≈
digest`), and the podcast prompt explicitly forbids padding ("если обзор
реально короткий — пусть выпуск будет короче"). So a floor + expand-retry that
operate on the *podcast* cannot exceed a ~700-word digest. The lever has to be
the **digest**, attacked below with a different approach. (The FF June-12 pass
reached the same digest-ceiling conclusion.)

---

## P0 — listener-facing bugs shipping today

### 1. English YouTube call-out spoken on the Russian Olya voice
Every recent FP episode ends (`FP_Ep054…_tts.txt:115`) with:
> *"And if you'd rather watch than listen, find us on YouTube at at Nerra RU — link's in the show notes."*

An English sentence on a Russian-only show — the exact wart class the June-10
pass localized for the AI disclosure, but the YouTube call-out
(`engine/intros.py:_maybe_append_youtube_cta`) was missed. **Fixed:** FP (a
Russian-*spoken* show) now gets a Russian call-out. Привет, Русский! is *taught
in English*, so it keeps the English one.

### 2. "at at Nerra …" — the "@" sigil voiced as the word "at" (network-wide)
The call-out template was `find us on YouTube at {handle}` with
`handle="@NerraRU"`; the TTS voices "@" as "at", shipping "**at at** Nerra RU".
Not FP-specific — **75+ occurrences across six shows** (`fascinating_frontiers`,
`models_agents_beginners`, `modern_investing`, `first_principles`,
`finansy_prosto`, `privet_russian`):
```
49 on YouTube at at Nerra Network — link's in the show notes.
 8 on YouTube at at Nerra RU — link's in the show notes.
 …
```
**Fixed:** the spoken handle is stripped of the "@" in
`_maybe_append_youtube_cta` (network-wide).

### 3. "до завтра" closing on an even-days show
Both FP closings (`engine/intros.py`) ended *"…берегите свои деньги, и **до
завтра**!"* ("see you **tomorrow**"). FP airs **even days only**
(`run-show.yml`: `37 9 2-31/2 * *`; `workers/scheduler`: `even`) — the EI-class
cadence-mismatch bug. **Fixed:** both variants now cadence-neutral ("до встречи
в следующем выпуске" / "до встречи"); the `Завершение` chapter pattern updated
to match.

---

## P1 — quality ceiling

### 4. Structural-integrity gate fires a wasted regen on every FP episode
`metrics_ep045…054.json` all carry `digest_structural_regen: true` — every
episode pays an extra ~32 s / ~$0.03 digest LLM call. Two root causes, both
verified:

- **The Russian hook label isn't recognized.** The FP/PR digest prompts label
  the hook `**ЗАГОЛОВОК:**` (`fp_digest.txt:84`), but `run_show._extract_hook`
  only matched English `HOOK:` or a leading blockquote — so a
  prompt-compliant FP digest reports a missing hook and trips the gate.
  **Fixed:** `_extract_hook` now matches `HOOK|ЗАГОЛОВОК`.
- **The corrective suffix was hardcoded for Tesla.** When the gate fired, the
  retry prompt told the model to *"fill EVERY mandatory section (Top 12 News
  Items, Tesla X Takeover, Short Spot, Tesla First Principles)"* — Tesla's
  sections, applied to **all 12 other shows**. **Fixed:** the suffix is now
  generic ("fill EVERY mandatory section from the formatting template above").

### 5. Chronic under-length — re-attacked at the digest (the June-10 MISS)
Episodes ship ~5 min against a prompt that claims "8-10 минут" in both the
digest (`fp_digest.txt:79`) and podcast (`fp_podcast.txt:19`) — and against the
podcast's own internally-contradictory targets (1,300–1,700w header / "не менее
1300 слов" floor) that a ~700-word digest can never satisfy without the padding
the prompt bans.

FP is **not** content-starved (the snapshot shows 69–129 articles/day) — unlike
FF (RSS snippets) or the narrative shows (single topic). So the ceiling is the
digest's structural spec being too thin, plus a verified digest↔podcast
mismatch: the **podcast** prompt requires "минимум 3" practical tips
(`fp_podcast.txt:30`) but the **digest** only produced "2-3"
(`fp_digest.txt:127`), and the podcast may not invent tips.

**Shipped (digest prompt, A/B):** require **3-4 practical tips** (matching the
podcast's minimum-3), **3 quick-news items** (was 2-3), and **5-7 articles**
(was 4-6) with an explicit "a normal news day has enough material — don't trim
to two topics" steer. This raises the digest's real output where content is
abundant, without inventing anything.

> **Exercise note:** `run_show.py finansy_prosto --test` was run with
> `GROK_API_KEY` set, but today's news pool was already drained by the real
> Ep54 run + content-tracker dedup (most feeds returned "0 passed
> recency/keyword filters"), so a clean before/after word count isn't
> demonstrable today. The prompt **renders** (`test_prompt_fidelity.py`). The
> length effect is the ledger prediction the next review scores on a fresh
> even-day episode (Jun 18/20).

---

## P2 — growth / discoverability

Nothing shipped this pass. Noted for a future pass: OP3 downloads are tiny
(7/week) — length fixes are about honesty-to-the-advertised-format and quality,
not a growth lever. The YouTube `@NerraRU` channel still needs
`YOUTUBE_REFRESH_TOKEN_RU` (operator item; uploads no-op without it).

---

## ⚠️ A/B-listen required (landmine #17)

All four change shipped audio:
1. **Russian YouTube call-out** for FP (was English on the Olya voice).
2. **"@" strip** in the call-out — network-wide (FF, MAB, MIT, FPD, FP, PR).
3. **Cadence-neutral FP closings** ("до встречи" replaces "до завтра").
4. **FP digest depth** (3-4 tips / 3 quick-news / 5-7 articles).

Fixes 4–5's *code* parts (`_extract_hook`, the de-Tesla'd suffix) are metadata
/ prompt-plumbing and don't themselves alter spoken words, but the digest-depth
prompt edit does.

## Deferred

- **Podcast-prompt length-target reconciliation.** The 1,300–1,700w target is
  unreachable from a ~700-word digest; rather than lower the aspiration, this
  pass raised the digest. If the digest-depth change lands episodes at ~7–8
  min, leave the podcast target; if it plateaus, reconcile the numbers next
  pass (and consider a digest-stage expansion retry — the standing network
  lever deferred for FF/UC/FPD).
- **Schedule anomaly:** Ep53 shipped on Jun 15 (odd day) — three consecutive
  days (14/15/16) for an even-days show. Likely manual/dispatch runs, not a
  pipeline bug; flagged for the operator to confirm, not fixed here.

## Test results
`tests/test_finansy_prosto_quality_pass.py` (14, new) + the full suite:
**3153 passed, 3 skipped**. Drift guards pin every fix above.
