# Adding a New Nerra Network Show

Use the scaffold tool to generate a production-ready show in one command. Episode **1** automatically receives extra LLM guidance for a strong series debut.

## Quick start

```bash
python scripts/scaffold_show.py \
  --name "Ocean Tech Weekly" \
  --slug ocean_tech \
  --description "Daily ocean technology, marine science, and blue-economy news for professionals." \
  --audience "marine researchers, ocean-tech founders, and coastal policy readers" \
  --source "https://www.science.org/rss/news_current.xml,Science AAAS" \
  --keyword "ocean technology" \
  --keyword "marine science" \
  --web-search "ocean technology news today" \
  --cron "45 10 * * *" \
  --brand-color "#0EA5E9"
```

## Validate before going live

```bash
python scripts/validate_show.py ocean_tech
python run_show.py ocean_tech --test          # digest only
python run_show.py ocean_tech                 # Ep1 (debut prompts apply)
```

## What gets created

| Artifact | Path |
|----------|------|
| Show config | `shows/<slug>.yaml` |
| Prompts | `shows/prompts/<slug>_system.txt`, `_digest.txt`, `_podcast.txt`, `_weekly.txt` |
| Output dirs | `digests/<slug>/`, `blog/<slug>/` |
| Website registry | `shows/network_meta.yaml` (merged into `generate_html.py`) |
| Cron reminder | `shows/scaffold_pending.yaml` + printed CRON_MAP line |

## Manual steps (still required)

1. **Cron** — Paste the printed line into `.github/workflows/run-show.yml` `CRON_MAP` and add a matching `schedule:` cron entry.
2. **Cover art** — Add `assets/covers/<slug-with-dashes>.jpg` (1200×1200 recommended).
3. **Health check** — Add `shows/<slug>_podcast.rss` to `.github/workflows/health-check.yml` `FEEDS` (or extend auto-discovery in a future PR).
4. **Music** (optional) — Point `audio.music_file` at a dedicated MP3 in `assets/music/`.
5. **Buttondown** — Create a tag matching `newsletter.tag` in the show YAML.
6. **HTML** — `python generate_html.py --show <slug> --blogs` after the first episode commits.

## First-episode quality

`engine/first_episode.py` appends debut instructions when `episode_num == 1`:

- Digest: welcome, strongest stories only, no "last week" references
- Podcast: series premiere framing, extra depth on one anchor story

No prompt edits needed — works for all shows.

## Narrative / topic-queue shows

For evergreen story-driven shows (like Unintended Consequences), scaffold with `--no-weekly-recap` and then add manually:

```yaml
narrative_mode: true
topic_queue_file: shows/topic_queues/<slug>.yaml
```

Use `shows/unintended_consequences.yaml` as the reference.

## Tips for a great Ep1

- Add **5–10 real RSS feeds** (not just Google News) before the first run.
- Run `--test` and read the digest; tune `shows/prompts/<slug>_digest.txt` if the tone is off.
- Set `min_articles_skip` to `4` if the beat needs density; `2` for sparse beats.
- Pin `min_podcast_words` in YAML if episodes run short.

## Templates

Customize defaults in `shows/templates/` before scaffolding, or edit generated prompts after.
