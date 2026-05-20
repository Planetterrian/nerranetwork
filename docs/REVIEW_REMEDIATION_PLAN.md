# Review Remediation Plan (May 2026)

Tracking implementation of the full-network audit. Status: **in progress on branch `cursor/review-remediation-db26`**.

## P0 — Subscriber-facing

| # | Item | Status |
|---|------|--------|
| 1 | Wire `update_blog_rss()` into daily pipeline + `generate_all_blogs` | Done |
| 2 | Generate `blog_unintended_consequences.rss` | Done (on next UC/blog run) |
| 3 | Run `scripts/generate_api.py` in CI finalize | Done |
| 4 | Publish-complete checkpoint (not MP3-only) | Done |
| 5 | Gate newsletter/X on successful MP3 | Done |
| 6 | Scrub invalid TSLA price lines before publish | Done |

## P1 — Reliability & ops

| # | Item | Status |
|---|------|--------|
| 7 | `min_audio_duration` reads `audio:` block in YAML | Done |
| 8 | Single `notify_directories` (pipeline only) | Done |
| 9 | Smoke pytest in production matrix | Done |
| 10 | Health-check includes UC RSS | Done |
| 11 | Post-run validation before newsletter | Done |
| 12 | YouTube disclosure → Grok TTS | Done |
| 13 | UC YAML comment matches code | Done |

## P2 — Follow-ups (not in this PR)

- Schema.org absolute URLs on show pages
- Blog post template RSS `<link rel="alternate">`
- RSS historical show-notes backfill
- Refresh `docs/env_var_inventory.md`
- Git history MP3 purge
- YouTube quota / enable more shows
- `run_show.py` phase extraction / resume-publish-only path
- Light-mode site option

## Verification

```bash
pytest tests/test_review_remediation.py tests/test_config.py -q
python -m engine.blog  # N/A — use regenerate via generate_html --blogs
```
