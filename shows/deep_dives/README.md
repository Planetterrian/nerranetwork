# Deep-dive episodes

A **deep dive** is a special, standalone, single-subject episode of an
otherwise news-driven show. Unlike `narrative_mode` (which permanently turns a
show into a topic-queue show, e.g. Unintended Consequences), a deep dive is a
**per-episode override**: the show stays a daily news show, and only a
scheduled or forced episode runs as a deep dive — then it auto-reverts to the
normal daily pipeline.

When a deep dive fires, that one run:

- **bypasses** the RSS/X news fetch, slow-news fallback, and the daily-format
  digest validation,
- feeds the queued topic (`title` + `brief`) into the show's deep-dive prompts,
- runs the normal digest → outline → podcast → TTS → publish pipeline,
- marks the topic `produced` in the queue, and
- skips the show's `post_generate` hook (so a standalone deep dive doesn't try
  to advance, e.g., Modern Investing's simulated-trade tracker).

## How a deep dive is triggered

For a show with a `deep_dive:` block, the runner checks its `queue_file` at the
start of **every** run and fires a deep dive when one of these is true:

1. **`when: next`** on an unproduced entry — fires on the very next run.
2. **`date: YYYY-MM-DD`** equals the run date — a scheduled deep dive.
   (A `date` match for today wins over a generic `when: next`.)
3. **Forced**: `python run_show.py <show> --deep-dive <id>` — produces that
   entry now, regardless of schedule. (Skips the episode with a clear message
   if the id is unknown or already produced.)

If none match, it's a normal news episode.

## Adding a deep dive (existing deep-dive show, e.g. Modern Investing)

Append an entry to `shows/deep_dives/<show>.yaml`:

```yaml
  - id: my-topic-slug              # unique; also the --deep-dive argument
    title: "Episode Title Phrase"  # → {topic_title}
    brief: >                        # → {topic_brief}: EXACTLY what to cover
      Spell out precisely what the episode must explain. The more concrete the
      brief (specific angles, the framework to teach, what to hedge as
      speculative), the better the episode. Two-part briefs ("PART ONE … PART
      TWO …") work well for a specific case + a reusable technique.
    when: next                      # OR: date: 2026-06-15
    produced: false
    episode_number: null            # runner fills these in
    produced_date: null
```

Leave `produced: false` until it runs. The next matching run produces it and
flips `produced: true` with the episode number and date.

## Enabling deep dives for another show

1. Add a `deep_dive:` block to the show's YAML:

   ```yaml
   deep_dive:
     enabled: true
     queue_file: shows/deep_dives/<show>.yaml
     digest_prompt_file: shows/prompts/<show>_deep_dive.txt
     podcast_prompt_file: shows/prompts/<show>_deep_dive_podcast.txt
     # system_prompt_file: optional override
   ```

2. Create `shows/deep_dives/<show>.yaml` with a `queue:` list (schema above).

3. Create the two prompts. Model them on
   `shows/prompts/modern_investing_deep_dive*.txt`:
   - the **digest/brief** prompt must consume `{topic_title}` / `{topic_brief}`
     / `{topic_category}` and emit a `**HOOK:**` line (it becomes the episode
     title), and
   - the **podcast** prompt must consume `{digest}` (the brief) + `{hook}` and
     produce the spoken script in the show's host voice.

Both prompt files are required overrides — a deep dive has a different shape
than a daily news episode, so falling back to the show's normal prompts is
almost never what you want.

## Notes

- Deep dives still publish normally (RSS, newsletter, X if enabled). YouTube
  follows the show's existing `youtube.enabled`.
- Chapter markers are best-effort; a deep-dive script won't match the show's
  news-format section patterns, so it may produce only Introduction/Closing
  chapters. That's expected.
- The `deep_dive_mode` / `deep_dive_topic_id` metrics fire per episode so the
  dashboard can tell deep dives apart from daily episodes.
