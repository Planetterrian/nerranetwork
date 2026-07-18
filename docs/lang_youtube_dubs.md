# Generalized language-dubbed YouTube channels (July 2026 — first: @NerraFR)

`engine/lang_dub.py` turns each episode's existing translated audio track
(the multilingual system's `.fr.mp3` / `.es.mp3` / … on R2) into videos on a
language-specific YouTube channel, reusing the episode's Grok gallery scenes
(zero extra image cost). It is the generalized sibling of `engine/ru_dub.py`,
which keeps serving @NerraRU untouched (the show-memory precedent: bespoke
proven engine kept, generalized engine for everything after it — fold RU in
later once parity is proven in production).

## Why a separate channel per language

Language-clean audience signals are why @NerraRU works (RU Shorts are the
network's best-performing surface). YouTube's native multi-audio-track
feature — one video, switchable audio — is not available via the public API,
so per-language channels are the only clean structure.

## Architecture

```
multilingual.yml (decoupled sweep, per show)
  translate step  → .fr.mp3 on R2 + summaries translations.fr
  RU dub step     → engine.ru_dub (bespoke, unchanged)     → @NerraRU
  FR dub step     → scripts/publish_lang_dubs.py --lang fr → @NerraFR
                     └─ engine.lang_dub.publish_lang_dub(config, ep, "fr")
```

`publish_lang_dub` mirrors `publish_ru_dub` exactly, parameterized by a
`DubLanguage` spec: EN-optimized-title lookup → Grok translation (echo
rejected — an untranslated title never ships), adaptive-policy gate
(channel-specific; FR seeded **shorts-only** with a 2.0 long_vpd floor, the
RU lesson), scene-availability deferral (`no_scenes_yet`), long render +
upload when the policy allows, up to 2 Shorts with smart windows +
fill-to-requested + per-word French ASS captions + French end-card +
funnel comment (only when a French long exists this run). Per-show index:
`digests/<dir>/youtube_videos.fr.json` — picked up automatically by the
analytics fetch, the adaptive policy, and subscriber tracking (all
channel-keyed).

Language-NEUTRAL machinery (manifest refresh, scene lookup/download, cover
resolution, title-index lookup, word trimming) is imported from
`engine.ru_dub` — one implementation, no drift.

## Adding a future language (e.g. Spanish)

1. Add a `DubLanguage` entry to `engine.lang_dub.DUB_LANGUAGES` (native
   disclosure/end-card/comment strings, Whisper language, episode-prefix
   regex).
2. Seed the channel in `scripts/update_youtube_policy.py` `SEED_TIERS`
   (shorts-only) + `LONG_VPD_FLOOR`.
3. Add a publish step to `multilingual.yml` with
   `YOUTUBE_REFRESH_TOKEN_<CH>` (+ Grok key + R2 creds — the FR step is the
   template).
4. Per show: `youtube.dub_languages: [fr, es]` and make sure the language
   is in `multilingual.languages` (the audio track is the dub's input).
5. Operator: create the channel, run
   `scripts/youtube_oauth_bootstrap.py` signed in as it, add the secret,
   create + "Set as podcast"-flag the playlists (landmine #15), then set
   `youtube.dub_playlist_ids: {es: PL...}`.

Credentials resolve generically: channel `xx` →
`YOUTUBE_REFRESH_TOKEN_XX` (`engine.youtube.get_channel_credentials_from_env`).

## Operator checklist to activate @NerraFR

The FR pipeline is **dormant** until these are done (every run before that
is a clean `no_fr_credentials` no-op):

1. Create the @NerraFR channel; add French channel art + description.
2. `python scripts/youtube_oauth_bootstrap.py <client_secrets.json>` signed
   in as @NerraFR → paste into the `YOUTUBE_REFRESH_TOKEN_FR` repo secret.
3. Create the four show playlists on @NerraFR, flag each "Set as podcast"
   in Studio, then add `dub_playlist_ids: {fr: PL...}` to each show's
   `youtube:` block (uploads publish without it — just no playlist).
4. Optional: `YOUTUBE_DAILY_QUOTA_FR` env if the channel's quota differs.

Enabled shows at launch: tesla, spacex, fascinating_frontiers,
modern_investing (`youtube.dub_languages: [fr]`; modern_investing's
multilingual `languages` gained `fr` in the same change — the track is the
dub's input). FR long-form will NOT render at first (shorts-only seed);
the Monday probe + velocity data let it earn in, exactly like RU.

Drift guards: `tests/test_lang_dub.py` (28 tests — registry, no-op paths,
credentials generalization with EN/RU pinned unchanged, policy seeds,
YAML wiring incl. the track-exists invariant, workflow env, sweep-index
semantics, RU-engine-untouched pins).
