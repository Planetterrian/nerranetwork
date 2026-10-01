# Corrections

How a factual error in a published episode is recorded, where the record
reaches, and what never happens to the audio.

The AI-disclosure, editorial and FAQ pages have promised since May 2026 that
"substantive corrections are noted in the next episode's show notes". Until
2026-10-01 nothing in the repository could make that true — there was no
place to file a correction. Now there is one file per show, and every surface
that promises a correction renders it from that file. Nothing is typed twice.

## Filing a correction

Edit (or create) `digests/<show_dir>/corrections.yaml` — the show's digest
directory, the one that holds its `*.md` episodes, e.g.
`digests/spacex/corrections.yaml` or `digests/tesla_shorts_time/corrections.yaml`.
It is a plain list:

```yaml
- episode: 117
  date: 2026-10-01          # the day the correction was filed, YYYY-MM-DD
  text: >-
    The booster flew its 23rd mission, not its 32nd as stated in the
    Launch Log item.
  where: digest             # digest | audio | both
```

| Field | Meaning |
|---|---|
| `episode` | The episode number the correction is **about** (integer). |
| `date` | Filing date. It decides which later episode carries the "Correction to episode N" line (below). |
| `text` | What was wrong and what is right, in one or two sentences. Written for a listener; it is printed verbatim. |
| `where` | `digest` — the article / show notes were wrong and the audio did not carry it; `audio` — the spoken episode was wrong; `both`. Defaults to `digest`. |
| `noted_in` | Optional. Pin the episode whose show notes carry the next-episode line, instead of deriving it from the dates. |

Entries are validated on read (`engine/corrections.py`): a bad entry is logged
and skipped, never raised, because a build or a feed update must not fail
over a trust annotation. Commit the file with the usual output commit; the
nightly regeneration picks it up.

## Where a correction reaches

1. **The episode's page** (`engine.blog`): a dated "Correction" box at the top
   of the article, before the reader meets the sentence that was wrong,
   saying whether the audio carried the error. Rendered on the next blog
   regeneration (`generate_html.py --show <slug> --blogs`, or the nightly).
2. **The corrected episode's show notes** (`engine.show_notes.corrections_footer`):
   a `Correction (date): …` line in the RSS description — on the next feed
   write for that episode.
3. **The next episode's show notes** (`engine.show_notes.carried_corrections_footer`):
   the line the policy pages promise, `Correction to episode N: …`. A
   correction filed on date D against episode E is carried by the first
   episode numbered above E that publishes on or after D, decided from the
   committed digest filenames; it is carried once, and never by the episode
   it corrects. `engine.show_notes.build_show_notes_extras(show_dir, episode)`
   returns both (2) and (3) for the episode being published, and `""` on an
   ordinary day, so the description is byte-identical until a correction is
   filed.
4. **Any trust surface** that wants the recent record:
   `engine.corrections.recent_corrections(show_dir, days=30)`.

The reader-facing address for reporting an error is
`engine.brand.CONTACT_EMAIL`, rendered on every episode page as a
"Report an error" link with the show and episode prefilled in the subject.

## What never happens: audio is not edited silently

A correction entry describes the error. It does not clip, overdub or
re-cut the published MP3, and `where: audio` records that the spoken
episode was wrong — it changes nothing in the file.

If the spoken episode has to change, the repair tool is the one CLAUDE.md
landmine #25 describes: `scripts/resynthesize_episode.py` (Actions
"Re-synthesize Episode"). It re-runs the corrected `_tts.txt` through the
same synthesis, uploads to the **same** R2 key so no subscriber is
re-pointed, refuses to upload audio the spoken-text gate has not passed, and
corrects the feed item's duration and byte length. Never clip: a defect
replaces content, so cutting it ships an episode that opens on a fragment
for the same downstream cost as a re-run. Either the whole episode is
replaced that way and the correction entry says so, or the audio is left as
aired and the correction entry tells the listener what was wrong.

## Guards

`tests/test_web_trust_2026_10_01.py` round-trips the YAML, pins the
next-episode rule, renders the correction box and the show-notes lines, and
checks that the policy pages describe the gate as it is configured in
`shows/_defaults.yaml` (`source_integrity.enforce: true`, `on_failure: strip`).
