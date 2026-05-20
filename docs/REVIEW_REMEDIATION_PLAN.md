# Review Remediation Plan (May 2026)

Tracking implementation of the full-network audit.

**Merged to `main`:** PR #389 (P0/P1). **P2 branch:** `cursor/review-p2-db26`.

## P0 — Subscriber-facing ✅

| # | Item | Status |
|---|------|--------|
| 1 | Wire `update_blog_rss()` into daily pipeline + `generate_all_blogs` | Done |
| 2 | Generate `blog_unintended_consequences.rss` | Done |
| 3 | Run `scripts/generate_api.py` in CI finalize | Done |
| 4 | Publish-complete checkpoint (not MP3-only) | Done |
| 5 | Gate newsletter/X on successful MP3 | Done |
| 6 | Scrub invalid TSLA price lines before publish | Done |

## P1 — Reliability & ops ✅

| # | Item | Status |
|---|------|--------|
| 7 | `min_audio_duration` reads `audio:` block in YAML | Done |
| 8 | Single `notify_directories` (pipeline only) | Done |
| 9 | Smoke pytest in production matrix | Done |
| 10 | Health-check includes UC RSS | Done |
| 11 | Post-run validation before newsletter | Done |
| 12 | YouTube disclosure → Grok TTS | Done |
| 13 | UC YAML comment matches code | Done |

## P2 — Follow-ups

| Item | Status |
|------|--------|
| Schema.org absolute URLs on show pages | Done |
| Blog post template RSS `<link rel="alternate">` | Done |
| Refresh `docs/env_var_inventory.md` | Done |
| `run_show.py` resume-publish-only path | Done |
| New show scaffold (`scripts/scaffold_show.py`) | Done — see `docs/NEW_SHOW.md` |
| Episode 1 debut LLM guidance | Done — `engine/first_episode.py` |
| RSS historical show-notes backfill | Deferred |
| Git history MP3 purge | Deferred (needs operator + `git filter-repo`) |
| YouTube quota / enable more shows | Deferred (ops / quota request) |
| Light-mode site option | Deferred |

## Verification

```bash
pytest tests/test_review_remediation.py tests/test_config.py -q
python -m engine.blog  # N/A — use regenerate via generate_html --blogs
```
