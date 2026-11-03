# Landmine 15 — YouTube Podcasts surface requires manual Studio setup, not API

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

15. **YouTube Podcasts surface requires manual Studio setup, not API**
    — the pipeline correctly creates per-show playlists and adds each
    upload via `engine/youtube.add_video_to_playlist()`, and every show
    YAML carries a `podcast_playlist_id:` (verified live in CI). But a
    playlist only appears under "YouTube Podcasts" once it's been
    flagged as a podcast in YouTube Studio: open
    `Studio > Content > Podcasts > "Set existing playlist as a podcast"`
    on each channel (`@NerraNetwork` for English shows, `@NerraRU` for
    Финансы Просто / Привет, Русский!) once per playlist. The YouTube
    Data API has no endpoint for this flag. Once flagged once, every
    future video added via the API automatically becomes a podcast
    episode. **One-time setup per playlist — not a code change.**
