# The Oct 23 slate: a billing stop, a dead mirror, and the catalog's aired flag (Oct 23 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The Oct 23 slate: a billing stop, a dead mirror, and the catalog's aired flag (Oct 23 2026)

Review [`docs/reviews/slate_review_2026_10_23.md`](docs/reviews/slate_review_2026_10_23.md);
register `slate-2026-10-23`; guards `tests/test_slate_2026_10_23.py`. 4 of 21
shows published: the xAI account ran out of credit at ~09:45 UTC (11 runs,
every producer-inbox run) and the Ubuntu mirror served nothing for 15 minutes
to six setups. Rules that bind:

- **The mirror is the last resort** (`.github/actions/setup-python`). The
  .debs a run downloads are cached per runner image and every later run
  installs them `--no-download`. When apt still cannot finish, ffmpeg comes
  from the pinned BtbN 8.1.3 build `test.yml` runs on (the guard keeps the
  tags equal). `setup-ffmpeg` has the same fallback.
- **A lake re-store keeps the story ids it did not change**, and run_show
  re-assigns after its second write. A catalog article is aired when an
  aired item carries its URL, story id or not (essays included). It had
  read 0 on every run.
- **A query string that names the page stays in the dedup key** (`id`, `v`,
  `p`, `prid`, `doi`, …). Every PLOS One paper had shared one key.
- **Mira's T-2h reminder checks the xAI account**
  (`fire_interviews.xai_credit_stop`, the `engine.provider_quota` matcher). A
  billing stop alerts Patrick by Slack and email with the guest and the time.
- **The video sweep restarts a handoff whose one run died before "Render and
  publish the video" started** (`scripts/video_job.retryable_titles`). Any
  other failed run is still re-run by a person.
- **Past the hold, the Nerra Daily gate waits for a re-run.** Ep064 shipped
  6 of 15 segments: the first re-run to land woke the gate while nine were
  still generating. A missing roster show whose run started after the hold
  and has not reached its own `if: always()` wake step is waited for
  (`engine.daily_edition.rerunning_shows`); the last re-run builds the
  edition. A morning straggler is not, so 7:00 ET is unchanged; an
  unreadable Actions API decides as before.
- The Cloudflare account is on Workers Paid (operator, Oct 23).
