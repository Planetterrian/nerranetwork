# Multilingual audio (FR / RU / ES / ZH)

A post-hoc stage that produces alternate-language **audio** versions of an
already-finalized English episode, voiced by the operator's cloned Grok voice,
and surfaces a language switcher on the website. English stays the canonical
master and the fallback everywhere; translations are derived artifacts.

The English generation pipeline is untouched — this is an additive branch.

## One-time setup

1. Paste the cloned Grok voice ID into `.env`:
   ```
   GROK_CLONED_VOICE_ID=<your cloned voice id>
   ```
   The same voice is used for all four languages. The driver fails loud if it's
   unset (it is never hardcoded or committed).
2. Reuses existing secrets: `GROK_API_KEY`/`XAI_API_KEY` (translation +
   TTS) and `R2_*` (track upload). No new credentials beyond the voice ID.

## Automatic generation (default)

As of June 2026 every English show has `multilingual.auto: true` in
`shows/_defaults.yaml`, so the daily pipeline generates **all four languages**
for each newly published episode automatically:

- `run_show.py` calls `engine.multilingual.auto_generate_after_publish()` right
  after the episode's summaries record is written and **before** the blog post,
  so today's post + index immediately show the language switcher and badges.
- It is **best-effort and non-blocking** — a translation failure (or an unset
  `GROK_CLONED_VOICE_ID`) can never break the English publish.
- Requires the `GROK_CLONED_VOICE_ID` secret in the `run-show.yml` workflow
  (already wired in the step env). Until that secret is set, the auto step
  no-ops with a warning and episodes ship English-only.
- Cost: ~$0.18/episode (≈4× the English TTS character volume + translation
  tokens) — roughly **$50–55/month** network-wide. See the cost note below.

Disable for a single show by setting `multilingual.auto: false` (or
`enabled: false`) in its YAML. The manual driver below still works regardless,
for back-fill or one-offs.

## Generate (manual / back-fill)

```bash
# 1) STOP-and-listen: one short Chinese sample, then it stops.
python scripts/generate_translations.py tesla --languages zh --episode <N> --sample-zh
#    A cloned English voice can mis-handle Mandarin tones — listen first.

# 2) A single full track end to end (proving run):
python scripts/generate_translations.py tesla --languages fr --latest 1

# 3) The first-pass batch once ZH is approved:
python scripts/generate_translations.py <show> --languages fr,ru,es,zh --latest 3 --zh-approved

# 4) Re-render the site so the switcher appears:
python generate_html.py --shows <show>     # or --all on the nightly job
```

Flags: `--latest N` (default 3) or `--episode N`; `--force` to regenerate an
existing track; `--dry-run` to translate + project cost without TTS/upload;
`--zh-approved` (required to batch Chinese after the sample); `--sample-chars`
(length of the `--sample-zh` clip).

## What each run does, per (episode, language)

1. **Translate** the finalized English `_tts.txt` script + title/description
   via `grok-latest` (`engine/translate.py`) — spoken-delivery, proper
   nouns/tickers preserved, per-language phonetic overrides applied.
2. **Validate** the result (`validate_translation`) — rejects an empty output,
   a model refusal, an untranslated English echo, a too-short stub, or a
   wrong-script result (e.g. ZH that came back in Latin). A rejected track is
   skipped and logged; the rest of the batch continues.
3. **TTS** with the cloned voice, BCP-47 pinned, MP3 out (existing
   chunk+concat path).
4. **Upload** to R2 next to the English file as `…/<file>.<lang>.mp3`.
5. **Record** the track + translated title/description on the episode's
   summaries record under `translations.<lang>`, checkpointed after each
   episode (a crash mid-batch keeps finished work).

## Idempotency & cost

- Re-running skips any `(episode, language)` already recorded unless `--force`.
- Each run logs a rough character + `$` projection up front (`--dry-run` to see
  it without spending). Grok TTS is ~$4.20 / 1M chars; a 4-language batch is
  ~4× the English character volume per episode plus translation tokens.

## Operator notes (length & quality)

- The first track per language logs its **runtime delta vs the English track**
  — RU/FR commonly run long. Informational only; no length is forced.
- **A/B-listen** new tracks before trusting them, per landmine #17 — especially
  the ZH sample.

## Per-language phonetic overrides

`shows/translation_overrides.yaml` maps `<term> -> { fr:, ru:, es:, zh: }`. Add
an entry when you hear a ticker/brand mispronounced in a target language; the
spelling is written into that language's script only (never the English path).

## Configuration

`multilingual:` in a show YAML (declared on `MultilingualConfig`):

```yaml
multilingual:
  enabled: true
  languages: [fr, ru, es, zh]
  cloned_voice_env: GROK_CLONED_VOICE_ID
```

Enabled network-wide in `shows/_defaults.yaml`; the two Russian shows opt out
(`enabled: false`). A disabled show needs an explicit `--languages` to run.

## Website behavior

The per-episode blog page renders an inline `<audio>` player + language pills
**only when a translation track exists** (English-only episodes show nothing
new). It defaults to the visitor's `Accept-Language`, remembers the session
choice, and swaps the audio + translated title/description on selection. Vanilla
JS, no build step. The podcast RSS feed is unchanged (English remains canonical).

## Scope (this pass)

Newest episodes first; the back-catalog stays English-only until generated. Out
of scope: YouTube multi-language upload, back-catalog bulk generation, and any
change to the English generation pipeline.

Drift guards: `tests/test_multilingual.py`.
