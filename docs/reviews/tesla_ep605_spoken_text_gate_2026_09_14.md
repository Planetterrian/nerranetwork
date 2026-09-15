# Tesla Shorts Time Ep605 — the TTS engine spoke its own reasoning (2026-09-14)

**Class:** P0, listener-facing, shipped to every surface.
**Scope of the defect:** one episode (Tesla Ep605). Unique across 1,709
committed episode transcripts.
**Scope of the hole:** every show on every run — nothing in the pipeline
compared what the audio SAYS with what the script SAID, and the one
opt-in check that comes close scores the whole episode, which cannot see
a 45-second defect.

## What the listener heard

The first 45 seconds of the published MP3 (RSS, Apple video feed, the
hook-first YouTube Short in its entirety, and Nerra Daily Ep025's Tesla
segment) are Grok TTS reading, in the host's voice:

> One thing, the input has line breaks, preserve them. The text ends
> abruptly, matter more. Since no conversions needed, output the same.
> But the human message is, followed by the text, I think, is part of
> the input, perhaps a tag for fast speech or something. But rules say
> leave as is. Rules. Do not convert at sign in code. But here, probably
> leave. So the output should be the entire text unchanged inside. But
> looking at previous, for hello, it's hello, then headline density for
> throughput and cost. …

The hook, the identity line ("This is Tesla Shorts Time, episode six
hundred five") and the first two sentences of the lead story were
replaced. The episode then resumes mid-sentence and is clean to the end.

## How it happened

1. The text we sent was clean. `Tesla_Shorts_Time_Pod_Ep605_20260914_tts.txt`
   opens exactly as designed: hook, identity line, first story. The
   script was 7,266 characters, one Grok TTS request, `<fast>` wrap
   applied (the leak's "perhaps a tag for fast speech" is the normalizer
   describing our wrap).
2. The Grok TTS request carries `text_normalization: true` (since the
   May 2026 audio pipeline; server-side expansion of numbers, dates,
   currency). That normalizer is an LLM stage. The leaked passage is its
   chain of thought about *our* text — "the input has line breaks",
   "the text ends abruptly, matter more" (its first chunk ended on
   "…gains matter more"), "for hello, it's hello" (its own few-shot
   example) — emitted as the normalized output instead of the text. The
   TTS voice then read it faithfully.
3. The same component has misbehaved before, less loudly: SpaceX Ep051
   (Aug 2026) aired "S&P CX closed at $112.20" because the normalizer
   merged the spelled ticker "S P C X" into the S&P index. That was fixed
   by changing the spelling; the component was never gated.
4. Every check the episode passed was measuring something else:
   * `tag_leak_detector` — a fixed registry of tag WORDS ("build
     intensity", "long pause", stray `<tag>`). It read 0.
   * `validate_transcription` (opt-in, off on every show) — a
     whole-episode `SequenceMatcher` ratio with a 0.7 floor. The leak
     replaced ~50 of 1,083 words; it would have scored ~0.9 and passed.
   * `script_audit` (hook coverage, overlap, entity retention) — reads
     the SCRIPT, never the audio.
   * `min_audio_duration` — 490 s, fine.
   The Whisper transcript, which contains the leak verbatim, is produced
   for every episode BEFORE mixing and publishing and was not consulted
   for this purpose.

## Are other shows affected?

`scripts/audit_spoken_text.py` runs the new checker over every committed
`_tts.txt` + `_transcript.json` pair. Since 2026-06-01 (1,214 pairs, 15
shows):

| finding | verdict |
|---|---|
| Tesla Ep605 (2026-09-14): opening 0.17, 61-word foreign passage at 2% | **the defect** |
| MAB Ep075 (2026-06-18): 79-word passage at 85% | the closing spoken twice — the missing-closing guard bug fixed 2026-07-02; would have been caught by this gate |
| FF Ep112 (2026-06-25): 112-word passage at 91% | `_tts.txt` at that time was saved BEFORE the outro was appended; a text-artifact, audio was right (today's `_tts.txt` matches the audio to the last word) |
| MIT Ep162 (2026-09-06): "S&P-S&P-S&P-…" ×40 | Whisper repetition hallucination at a segment boundary; the audio says "the S&P 500 closed at" |
| M&A Ep140 (2026-08-13): 70 words of gibberish at 6% | Whisper hallucination — 70 words inside a 2.3 s segment is not speech |
| Привет, Русский! ×6, Финансы Просто ×1 | Whisper: English halves transcribed as Cyrillic sound-alikes; one Russian episode translated into English |

So the exact failure is unique, the class (audio ≠ script) has one other
real instance in the window (a since-fixed script bug), and the two
Russian shows cannot be measured by this instrument yet.

The multilingual dub tracks (FR/RU/ZH) and the RU/FR YouTube dubs go
through the same TTS request. The RU/FR dub renders transcribe their
audio for captions but do not compare it with the translated text; the
FR/ZH audio tracks are never transcribed. **Open item:** the gate does
not yet cover the dubs (see Follow-ups).

## What shipped

**`engine/spoken_text_gate.py` — deterministic, no model, no network.**
Reads the Whisper transcript the pipeline already makes and compares it
with the in-memory script that was sent to TTS:

* `opening_match` — share of the first 30 spoken words found, in order,
  in the script's opening. Ep605: 0.17. Every healthy English episode
  since June: ≥ 0.67. Threshold **0.5**.
* `longest_unmatched_run` — after aligning the whole transcript against
  the whole script, the longest run of spoken words the script does not
  contain (one matched word does not break a run). Ep605: 61. Legit
  maximum since June: 22 (benchmark numbers Whisper writes as digits).
  Threshold **40**.
* Whisper artifacts filtered first: segments faster than 6 words/s are
  dropped (M&A Ep140); n-gram loops repeated more than 3× are collapsed
  (MIT Ep162). Both committed artifacts are test fixtures.

**`run_show.py` — gate between transcript and mix.** The synthesis
branches are wrapped in `_synthesize_raw_mp3()` (body unchanged, only
indented) so the gate can re-run the identical synthesis. Flow: transcribe
→ check → on failure re-synthesise once and re-transcribe (the defect is
injected server-side and does not repeat; ~$0.11 and ~2 min) → on a second
failure **skip the episode** (`_skip_episode("spoken_text_gate", …)` —
the same marker the daily review and Nerra Daily's ready gate read).
Metrics per episode: `spoken_text_gate` (pass | retry_pass | blocked |
fail_shadow | no_transcript | off), `spoken_text_gate_mode`,
`spoken_text_opening_match`, `spoken_text_unmatched_run`,
`spoken_text_gate_reasons`, `spoken_text_gate_attempts`,
`spoken_text_gate_retry_duration_s`, `spoken_text_gate_first_attempt`
(the failing numbers when a retry rescued the episode),
`spoken_text_whisper_segments_dropped`, `spoken_text_whisper_loops_collapsed`.
A re-synthesis is costed with `record_tts_usage` like the first pass.

**Modes.** `tts.spoken_text_gate: enforce` network-wide in
`_defaults.yaml`; `shadow` pinned on Финансы Просто and Привет, Русский!
and forced by code for any non-English transcript
(`resolve_gate_mode`), because a gate that blocks on its own
instrument's noise costs a show its episode. A missing transcript never
blocks — it records `no_transcript` and a `::warning::` that the audio
is unverified.

**Grok `text_normalization` is now configurable.** `tts.apply_text_normalization`
(the existing ElevenLabs-style "auto/on/off" field) now also drives the
Grok request's boolean (`engine.tts.grok_text_normalization_flag`);
before, the Grok path was hard-wired `True` and no show could switch the
normalizer off. **It stays ON by default** (byte-identical requests):
residual digits still reach the TTS text every day (version strings
like 14.3.8, booster tails like B1081, "845km", 146 digit characters
across Tesla's last 15 scripts), and switching the normalizer off would
change how every one of them is spoken on every show — landmine #17. The
gate, not the switch, is the guarantee. If the leak recurs on a show,
`apply_text_normalization: "off"` on that show is a one-line,
A/B-listened experiment.

## What was NOT done, and why

* **Ep605's audio was not repaired from this session.** There is no
  TTS key or Whisper here. The repair is a re-run of the committed
  `_tts.txt` through TTS + mix + the same R2 key
  (`tesla/Tesla_Shorts_Time_Pod_Ep605_20260914.mp3` — same enclosure
  URL, so subscribers are not re-pointed), plus a YouTube delete +
  re-upload of long-form `J9ENRcR65sc` and Short `Cfi81jyH6Xc` (YouTube
  cannot replace a video's file), the Apple video asset, and Nerra
  Daily Ep025's Tesla segment. Operator's call whether to repair or
  pull; the Short is the strongest case for pulling — it is 35 s of
  nothing but the leak.
* **No prompt or voice change.** Nothing here touches what a healthy
  episode sounds like.
* **The whole-episode `validate_transcription` was left as is** (opt-in,
  off). It answers a different question (pronunciation drift) and its
  score cannot see a localised defect; documenting that is the fix.

## Follow-ups

1. **Dub tracks.** Extend the gate to `engine/multilingual.py` (FR/ZH
   audio tracks are never transcribed today — one Whisper pass per
   track, CPU only) and to the RU/FR dub renders (they already
   transcribe for captions; compare against the translated text).
   Calibrate per language first with `audit_spoken_text.py`.
2. **Russian shows out of shadow.** Needs a Whisper setup that handles
   the bilingual audio (language auto-detect per segment, or a
   multilingual model) before `enforce` is honest there.
3. **Review snapshot / dashboard.** Surface `spoken_text_gate` outcomes
   per show so a `retry_pass` streak (the normalizer failing often) is
   visible before it becomes a block.

## Ledger

Entry appended to `docs/reviews/ledger/tesla.yaml` (2026-09-14).
Drift guards: `tests/test_spoken_text_gate.py`.
