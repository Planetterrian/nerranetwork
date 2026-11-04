# Current Refactoring Goal — extracting the show scripts into engine/ (Phases 1–3)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

## Current Refactoring Goal

**Extract duplicated code from the show scripts into `engine/` modules.**

Phase 1 (complete):
- `engine/utils.py` — `number_to_words`, `_env_float/int/bool`,
  `calculate_similarity`, `remove_similar_items`, `deduplicate_by_entity`
- `engine/tts.py` — `validate_elevenlabs_auth`, `speak`, `_speak_chunk`,
  `_chunk_text_for_elevenlabs`
- `engine/audio.py` — `get_audio_duration`, `format_duration`,
  `mix_with_music` (standard / delayed-intro / dual-music modes),
  `normalize_voice`

Phase 2 (complete):
- `engine/publisher.py` — `update_rss_feed`, `get_next_episode_number`,
  `save_summary_to_github_pages`, `post_to_x`, `format_digest_for_x`,
  `format_tst_digest_for_x`, `apply_op3_prefix`
- `engine/content_tracker.py` — `ContentTracker` with per-show section patterns
  (TST, FF, PT, OV, EI, M&A)
- `engine/fetcher.py` — `fetch_rss_articles`
- `engine/generator.py` — `generate_digest`, `generate_podcast_script`
- `engine/tracking.py` — `create_tracker`, `record_llm_usage`,
  `record_tts_usage`, `record_x_post`, `save_usage`

Phase 3 (current):
- All 13 shows now run via `run_show.py` + YAML configs in production (CI/CD).
- Legacy scripts (`digests/{tesla_shorts_time,omni_view,fascinating_frontiers,
  planetterrian}.py`) are **deprecated** — retained for reference only.
- `run_show.py` is the canonical entry point; legacy scripts are not called
  by any workflow or cron job.
