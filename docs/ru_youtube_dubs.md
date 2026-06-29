# Russian-dubbed YouTube videos (@NerraRU) — June 2026

Publishes Russian-language videos of the English shows to the **@NerraRU**
channel, built from the Russian **audio** track the multilingual pipeline
already generates for every English show. No new audio, no new images — it
reuses both.

## What it does

For a show with `youtube.ru_dub_enabled: true`, the decoupled multilingual
workflow, after generating the episode's `ru` audio track, also:

1. Pulls the episode's **already-generated Grok scene images** from the gallery
   manifest's public R2 URLs (`segment_card` = 16:9 long-form, `social` = 9:16
   Short) — **zero extra image-generation cost**.
2. Renders a long-form video (RU audio + those scenes) and a 1 Short.
3. Uploads both to **@NerraRU** (`channel: ru` token) with the Russian
   title/description from the translation record + the Russian AI-voice
   disclosure, and adds them to the show's @NerraRU playlist.
4. Records each upload in a **per-show** `digests/<slug>/youtube_videos.ru.json`
   index (per-show → no cross-show push contention; also feeds the analytics
   loop).

```
multilingual.yml (decoupled — off the episode critical path)
  generate_translations.py  → digests/<slug>/…​.ru.mp3 + summaries `ru` track
  publish_ru_dubs.py        → engine.ru_dub.publish_ru_dub
        gallery images (R2)  +  ru.mp3  →  long-form + Short  →  @NerraRU
```

### Why the decoupled workflow, not the episode pipeline

The English episode pipeline is timeout-bounded; adding RU TTS + a second
render there is exactly what caused the partial-publish landmine that pushed
multilingual into its own workflow. The RU dub lives in that same off-critical
workflow, so it can never delay or break an English publish.

### Why reuse gallery images instead of regenerating

Every Grok scene is already uploaded to the `nerra-gallery` R2 bucket with a
committed manifest keyed by `show_slug` + `episode_id`. Fetching those public
URLs costs nothing and keeps the RU video visually identical to the English
one. If the manifest hasn't been rebuilt for the newest episode yet, the dub
falls back to the cover-only slideshow and a later idempotent sweep picks up
the real scenes.

## Enabled shows (June 2026)

`tesla`, `spacex`, `fascinating_frontiers`, `modern_investing` —
long-form + 1 Short each. Every other show is `ru_dub_enabled: false`
(byte-for-byte no-op).

## Operator one-time setup

1. **@NerraRU OAuth token** — `YOUTUBE_REFRESH_TOKEN_RU` must be set (run
   `scripts/youtube_oauth_bootstrap.py` signed into the @NerraRU account; the
   token now includes `yt-analytics.readonly` too). Until it's set, the dub
   step logs `no_ru_credentials` and no-ops.
2. **Playlists** (optional but recommended, landmine #15) — create one playlist
   per show on @NerraRU in Studio, flag it as a podcast, and put its ID in the
   show YAML's `youtube.ru_podcast_playlist_id`. Uploads still publish without
   it (a warning is logged); they just aren't added to a playlist.

## Cost & cadence

- Incremental cost per episode ≈ the RU translation+TTS that **already runs**
  today (~$0.18) + a cheap slideshow render. Image cost is **$0** (reused).
- @NerraRU gains 4 long-form + 4 Shorts/day on top of the 2 native RU shows —
  well under the channel's 200k quota and the ~30/day authenticity soft-cap.

## Verifying

```bash
# Dry-run (resolves the RU track + title, renders/uploads nothing):
python scripts/publish_ru_dubs.py all --dry-run

# One episode for real (needs YOUTUBE_REFRESH_TOKEN_RU + ffmpeg):
python scripts/publish_ru_dubs.py tesla --episode <N>
```

Idempotent: an episode already in `youtube_videos.ru.json` is skipped unless
`--force`.

## Deliberately left for later

- **Russian chapters / burned-in captions** — the English chapter markers don't
  match the Russian script, so v1 ships without chapters on the RU long-form.
  A Russian-aware chapter pass (or a Whisper transcript of the RU audio) is the
  follow-up.
- **Smart Shorts window** — without a Russian transcript the Short starts at the
  configured offset rather than the most-engaging beat.

Drift guards: `tests/test_ru_dub.py`.
