# Nerra Daily — the combined daily edition

One episode a day carrying the whole English network, anchored by Mira
(the Age of AI host, Grok voice `ara`). Launched August 2026,
operator-directed. This doc is the operational contract; the design
rationale lives in the `engine/daily_edition.py` module docstring, and
`tests/test_daily_edition.py` pins the load-bearing shapes.

## What it is (and is not)

- **A repackage, not a re-generation.** Segments are the exact MP3s the
  standalone feeds shipped, downloaded back from R2. Marginal cost per
  episode: one small Grok call to write Mira's links (grok-4.3), a few
  thousand characters of Grok TTS, ffmpeg CPU, one R2 upload
  (`nerra_daily/` keyspace — never a show's audio prefix). No images, no
  YouTube, no newsletter, no multilingual at launch.
- **A virtual show** (the Age of AI precedent): registered in
  `shows/network_meta.yaml` only. There is deliberately **no
  `shows/nerra_daily.yaml`** — that keeps it out of `run_show.py`, the
  review rotation (`tests/test_review_agent.py` derives from
  `shows/*.yaml`), multilingual auto-discovery, and every other
  shows-glob consumer. Do not add one.
- **Fixed, consistent rundown** (operator-set 2026-08-21, revised after
  hearing Ep1): spacex, tesla, fascinating_frontiers, models_agents,
  planetterrian, omni_view, then modern_investing,
  unintended_consequences, first_principles, models_agents_beginners,
  the Monday weeklies (env_intel, offshore_north), and dp_pod as the
  deliberate good-news close. Shows that skipped their day are simply
  absent; Mira's rundown adapts. Every English show is included (MAB
  too — completeness over the M&A overlap, operator's call). Age of AI
  is **plugged, never spliced** (interviews run 40+ min).

## The outro trim

Every English episode's spoken tail is: show sign-off → network sibling
plug (`engine.network_promo`, baked into the voice audio) → website
surface plug → AI disclosure. Inside the combined edition those plugs
are noise, so each segment is trimmed:

- `find_promo_cut` searches the episode's **committed Whisper
  word-timestamp transcript** (last 150 s only), anchored on the four
  promo frame shapes with the brand token fuzzy (Whisper renders "Nerra"
  as Nera / Narra / Narrow / NERA — all observed). The "rather watch
  than listen" YouTube CTA directly before the plug is folded into the
  cut. The cut lands in the natural pause after the sign-off's final
  word (padded from the match, clamped to the previous word's end).
- **No match = no trim.** The segment ships whole, plug included, with a
  loud log line — never a guessed cut. A cut before 50% of the episode
  is refused outright.
- Because the trim removes every per-segment AI disclosure, **Mira
  speaks one network-level disclosure at the end of the edition**
  (`MIRA_AI_DISCLOSURE`). Never remove it.
- The standalone shows keep their plugs untouched — nothing here writes
  outside the edition's own paths.

Transcript times are raw-voice-track times; the final-MP3 cut adds the
show's `voice_intro_delay` ONLY (0.0 network-wide since the July 2026
cold-open pass — `intro_duration` is music under the opening line, not
before it, so it shifts nothing). Verified against Ep578: final 563.1 s
= raw 533.1 s + 30 s music outro + 0 s shift.

## Audio assembly

All pieces (trimmed segments + Mira links) are re-encoded uniformly
(44.1 kHz stereo, libmp3lame `-q:a 2`) so the final join is a lossless
stream-copy concat (`engine.audio.concatenate_audio`). Mira's TTS is
loudness-normalized to the network's −16 LUFS spec with padding either
side. Chapter markers are **exact** (we performed the splice): each
show's chapter opens on the handoff that introduces it, so skipping to a
chapter always lands on Mira setting the show up.

## Mira's links

One Grok call writes intro + per-gap handoffs + sign-off as strict JSON
(`shows/prompts/nerra_daily_links.txt` — de-seeded by shape, facts only
from the day's digest excerpts). Her Age of AI self-reference rotates
deterministically by date (opening mention / sign-off reflection /
none), and a new Age of AI episode published that day is always plugged
in the opening. Any LLM failure falls back to deterministic
titles-based announcer lines — the edition never fails for want of
links, and even the fallback is never two days identical.

## Mira's field note

Operator-directed (2026-08-21): a short segment of Mira's OWN at the
episode midpoint, under its own chapter — one verifiable item from
today's wider world that the lineup did not cover, found via a single
`web_search`-grounded Grok call (`shows/prompts/nerra_daily_find.txt`).
Rules that bind: the source is named aloud, the item must not duplicate
the lineup (titles are injected), and **any failure or unverifiable day
skips the segment entirely** — the model's `SKIP` escape and
`parse_find_text`'s length bounds mean filler is never aired. Adds
~$0.01/day (one search call + ~500 TTS chars). This is the beat that
develops Mira's editorial voice beyond announcing.

## Orchestration

`.github/workflows/nerra-daily.yml`:

- `workflow_run` after every "Run Podcast Show" completion + the
  `--when-ready` gate in `scripts/build_daily_edition.py`: the edition
  assembles minutes after the LAST show expected that weekday lands.
- Scheduled sweeps (14:23 / 17:23 UTC) are idempotent fallbacks; past
  14:00 UTC the gate stops waiting for stragglers (a show that
  legitimately skipped would otherwise block the edition forever) and
  builds with whatever published, refusing below 4 segments.
- Idempotency key: the committed summaries entry for the edition date.
  Re-runs after a failed commit rebuild cleanly (the MP3 re-uploads to
  the same R2 key).
- Publish surface: `nerra_daily_podcast.rss` (OP3-prefixed enclosures,
  `podcast:chapters` link), `digests/nerra_daily/` (summaries JSON,
  chapters JSON, daily rundown .md, credit file, `metrics_ep*.json`),
  blog post via `generate_html.py --show nerra_daily --blogs`. The
  rundown blog links into each show's own episode post rather than
  duplicating digests — and carries Mira's actual spoken prose (intro,
  each handoff under its show's section, field note, sign-off) plus a
  `> **<Weekday> edition — <lead hook>**` blockquote that
  `engine/blog.py` needs for per-day blog titles (without it every
  post titled itself with the italic byline — Aug 25 2026 review).
- **Observability (Aug 25 2026):** each build commits
  `metrics_ep*.json` — per-segment `cut_kind`/`cut_final_seconds`,
  `segments_shipped_whole`, `missing_expected` (a show that published
  AFTER the force-build, like Offshore North at 17:04 on Monday
  2026-08-24), `segments_dropped`, `links_source` (llm vs fallback)
  and the field-note flag. A trim that silently stops matching or a
  chronic Monday miss is countable now instead of a lost log line.
  Virtual-show registration: the OP3 fetcher (`_virtual_show_targets`
  reads `network_meta.yaml`) and the dashboard cost rollup
  (`_VIRTUAL_COST_SLUGS`) both had to learn about registry-only shows —
  a future edition must be picked up by both or its audience and cost
  are invisible.
- **Rotation memory (Aug 25 2026):** `build_links_prompt` injects the
  opening words of the last 10 committed intros (`{recent_openers}`)
  and `build_find_prompt` the last 10 field-note topics
  (`{recent_field_notes}`) as do-not-repeat blocks — data-side, the DP
  Pod lever-memory pattern (all four launch intros opened "Good
  morning.", and nothing stopped the field note from re-finding a
  recently covered item).

## Operator checklist (one-time)

1. Add the `nerra-daily.yml` workflow's secrets — none new: it reuses
   `GROK_API_KEY` + the `R2_*` set already in Actions.
2. Submit `https://nerranetwork.com/nerra_daily_podcast.rss` to Apple
   Podcasts / Spotify once the first episode has published.
3. Listen to Ep1 end-to-end (landmine-#17 habit): cut points, Mira's
   pacing, handoff levels vs segment levels.
4. Optional later: `podcast_playlist_id` if it ever goes to YouTube;
   `display_order` promotion on the homepage (launched at 102).

## Future editions

Everything show-specific lives in `EditionSpec` (`EDITIONS` registry).
A Russian or French edition is: a new spec (lineup, feed file, prompt
file, voice) + a prompt translation — not a fork. The RU shows publish
Mondays/even-days only, so an RU edition would likely splice the RU
dub tracks of the English shows instead; decide when the EN edition
has a few weeks of OP3 data.
