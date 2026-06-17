# Multilingual audio (FR / RU / ES / ZH)

A post-hoc stage that produces alternate-language **audio** versions of an
already-finalized English episode, voiced by the operator's cloned Grok voice,
and surfaces a language switcher on the website. English stays the canonical
master and the fallback everywhere; translations are derived artifacts.

The English generation pipeline is untouched — this is an additive branch.

## One-time setup

Nothing required beyond what the network already has. The translated tracks
reuse each show's **existing Grok voice** (`tts.voice_id`, `kdif6sqjcyiq`) and
existing secrets (`GROK_API_KEY`/`XAI_API_KEY` for translation + TTS, `R2_*`
for upload). No new credentials.

**Optional:** to voice the translations with a *different* cloned voice, set
`GROK_CLONED_VOICE_ID` (in `.env` locally, or as a GitHub secret for CI). When
unset, the show's existing voice is used.

## Automatic generation (default)

As of June 2026 every English show has `multilingual.auto: true` in
`shows/_defaults.yaml`, so the daily pipeline generates **all four languages**
for each newly published episode automatically:

- `run_show.py` calls `engine.multilingual.auto_generate_after_publish()` right
  after the episode's summaries record is written and **before** the blog post,
  so today's post + index immediately show the language switcher and badges.
- It is **best-effort and non-blocking** — a translation failure can never
  break the English publish.
- **Voice:** the translated tracks reuse the show's **existing Grok voice**
  (`tts.voice_id`, e.g. `kdif6sqjcyiq`) by default — Grok carries one voice
  across languages, so the host sounds like the operator in every language with
  no extra setup or secret. `GROK_CLONED_VOICE_ID` is only an **optional
  override** to point translations at a different cloned voice.
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
JS, no build step. The **canonical English** podcast RSS feed
(`<show>_podcast.rss`) is unchanged — English stays the master.

## Per-language podcast feeds (Apple / Spotify)

Each translation track is also published as a real, subscribable podcast in a
**dedicated per-language feed** next to the English one:

```
spacex_podcast.rss        # English, canonical (untouched)
spacex_podcast.fr.rss     # French tracks only
spacex_podcast.es.rss     # Spanish tracks only  …
```

- Built by [`engine/language_feeds.py`](../engine/language_feeds.py) via
  [`scripts/build_language_feeds.py`](../scripts/build_language_feeds.py),
  **fresh from the canonical `summaries_<slug>.json`** each run (idempotent —
  never depends on the prior feed file). A feed is written **only** for a
  language that has at least one track (no empty feeds).
- The channel **title + description are translated once** (via
  `engine.translate.translate_metadata`) and cached in
  `digests/<slug>/channel_i18n.json`, so nightly rebuilds cost no Grok credits.
  With no key + no cache it degrades to an autonym-suffixed English title
  (`SpaceX Daily (Français)`) so the build always ships a valid feed.
- The channel `<language>` is region-qualified (`fr-fr`, `ru-ru`, `es-es`,
  `zh-cn`) so directories shelve each feed in the right locale.
- Per-episode **GUIDs are deterministic** (`<guid_prefix>-<lang>-ep<NNN>-<date>`)
  so a rebuild never re-notifies subscribers or double-lists an episode.
- Enclosure byte length comes from the track's `bytes` field (captured at
  render time in `engine/multilingual.py`); older records fall back to a
  duration estimate.

**Pipeline wiring:** the multilingual sweep
(`.github/workflows/multilingual.yml`) rebuilds + commits the feeds right after
it generates tracks; the nightly maintenance workflow rebuilds them again as a
regenerable safety net. Show pages and the How-to-Listen table link the
available language feeds (`generate_html._collect_language_feeds`).

**Operator:** submit each per-language feed URL
(`https://nerranetwork.com/<show>_podcast.<lang>.rss`) to Apple Podcasts Connect
and Spotify for Podcasters once, the same as the English feed. Run
`python scripts/build_language_feeds.py --all` to print the full list.

Drift guards: `tests/test_language_feeds.py`.

## Scope (this pass)

Newest episodes first; the back-catalog stays English-only until generated. Out
of scope: YouTube multi-language upload, back-catalog bulk generation, and any
change to the English generation pipeline.

Drift guards: `tests/test_multilingual.py`.
