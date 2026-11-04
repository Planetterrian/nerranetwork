# Nerra Daily — show notes and passes (Aug 2026 – Oct 8 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

- **NDaily** (Nerra Daily) — the network's **combined daily edition**
  (Aug 2026): one ~2 h episode/day that SPLICES the day's already-published
  English episode MP3s (pulled back from R2) with short Mira host links
  (Grok voice `ara`) between them — operator-set fixed rundown (SpaceX →
  Tesla → FF → M&A → Planetterrian → Omni View → the rest), DP Pod
  closes; Monday adds EI + Offshore North. Mira also speaks a midpoint
  **field note** — one web-search-grounded item of her own, own chapter,
  honest-SKIP on unverifiable days (`shows/prompts/nerra_daily_find.txt`). **Not a run_show show and it
  must never become one**: registry entry in `shows/network_meta.yaml`
  only (no `shows/nerra_daily.yaml`, deliberately — that keeps it out of
  the review rotation and every shows-glob consumer), assembled by
  `scripts/build_daily_edition.py` + `engine/daily_edition.py`, workflow
  `.github/workflows/nerra-daily.yml` (workflow_run after each Run Podcast
  Show + ready gate: builds minutes after the last expected show lands;
  ≥12:00 UTC sweeps build with whatever published (12:00 force hour +
  the scheduler Worker's 12:07 dispatch land straggler days ~5:40am PT
  — Aug 2026 pass); committed summaries
  entry per date = idempotency key). **Each segment's baked-in outro tail
  (network sibling plug → surface plug → AI disclosure) is trimmed via
  the committed Whisper word timestamps** (`find_promo_cut` — fuzzy on
  Whisper's brand spellings, anchored on the four `network_promo` frames;
  no match = segment ships whole, never a guessed cut) and Mira speaks ONE
  network-level AI disclosure at the end — the standalone feeds keep their
  plugs untouched. Marginal cost ≈ one small Grok call (links, grok-4.3) +
  ~4k TTS chars + one R2 upload (`nerra_daily/` keyspace) — no content
  regenerated. Mira's link LLM output is JSON-validated with a
  deterministic titles-based fallback; her Age of AI self-reference
  rotates by date and a new AOAI episode is plugged, never spliced.
  Editions are language-parameterized (`EditionSpec`) for future RU/FR.
  Surfaces at launch: own RSS (`nerra_daily_podcast.rss`, exact spliced
  chapter markers), show page, daily rundown blog (links into each show's
  post — never duplicates their digests). Docs:
  [`docs/nerra_daily.md`](docs/nerra_daily.md). Drift guards:
  `tests/test_daily_edition.py`.
  **Sep 3 2026 second pass** (review:
  [`docs/reviews/nerra_daily_review_2026_09_03.md`](docs/reviews/nerra_daily_review_2026_09_03.md)):
  the metrics file caught a **P0** — the one non-`promo` cut it ever
  recorded was DP Pod Ep52 losing its Dispatch and sign-off (69 s) in
  Ep10: Whisper writes "sister shows"/"sisters show", the frame regex
  wanted the singular, and the weak brand-mention fallback matched the
  Dispatch's own "show page at nerranetwork.com". Fixed (`sisters?
  shows?` + `WEAK_EVIDENCE_MAX_TAIL_SECONDS` 60 s ceiling on any
  non-frame cut; 210/210 recent transcripts trim on frame evidence and
  `TestPromoCutHardening` sweeps them all in CI — **extend the matcher
  for a new Whisper spelling, never lean on the fallback**). **Sep 17 2026:** the scripted YouTube call-out ("rather watch
  than listen", `engine.intros`) is a frame-grade anchor when the outro
  follows it (`anchor: youtube_lead`, 60 s ceiling) — MIT Ep171's model
  dropped frame 2's sibling sentence and Whisper wrote nothing for 22 s
  of DP Pod Ep069's plug; the edition metrics record `cut_anchor`. Rotation
  memory v2: the date defeated the Aug 25 opener memory (5/9 intros were
  "<date> opens Nerra Daily…"), so openers are date-normalized, and the
  sign-off ("Across these segments" 7/9) and field-note closer
  ("quietly" 10/13 — seeded by BOTH prompts' register lines) got their
  own memory blocks + shape de-seeds (A/B-listen). Every edition had
  been titled with SpaceX's hook (lead show) — the links call now writes
  a validated whole-day `title` (metadata only; experiment
  `nerra-daily-edition-titles`); show notes carry chapter timestamps +
  the field note; `podcast:person` credits Mira. Same-day follow-up: the
  ready gate reads the committed `.skip_<date>.json` marker
  (`discover_lineup` → `skipped`, metrics `skipped_today`) and no
  longer waits for a show that skipped — a UC gate-block had held the
  edition to the 12:00 force hour (12:09 / 12:41 vs ~08:13 on complete
  days). Open operator item: UC's claims-gate retry lands after the
  edition, so a gate-blocked UC never makes that day's edition.
  **Oct 2 2026 — every English show, and a gate that waits.** Ep043
  shipped at 39 min with FOUR segments: the morning flagship wave had been
  diverted into recovery branches (every show run rewrote the new
  `claims.html`; the commit step cannot three-way merge generated HTML —
  P0 fixed the same day: the per-show regen writes only its own
  `claims/<slug>.html`, the network page belongs to `--network` /
  `--static-pages`, and `push_show_artifacts.sh` lists both as
  regenerable). Operator direction: the thirteen launch-cohort shows are
  IN the lineup (26 shows; `weekday_only` for Longevity/Peptides/
  Collingwood; a weekday roster is 21–23; Nerra Personal's vocabulary is
  the roster again). The ready gate is `engine.daily_edition.ready_decision`
  (pure, tested); its 13:00 UTC force hour was replaced on Oct 8 (below).
  The links `max_tokens` scales with the handoff count. ⚠️ AUDIO:
  Mira's handoffs triple — A/B-listen the first edition. Register
  `nerra-daily-full-lineup-2026-10-02`; guards
  `tests/test_nerra_daily_full_lineup_2026_10_02.py`.
  **Oct 8 2026 — the edition goes out at 8:00 AM Pacific, after every
  show (operator-directed).** `ready_decision` reads PACIFIC wall time
  (`RELEASE_PACIFIC` 07:50 — a build takes 6-7 min — and
  `HOLD_UNTIL_PACIFIC` 09:00, `release_window()`): before 07:50 it waits
  whatever has landed; then it builds once every expected show has
  published or skipped; a straggler is held for until 09:00 (it builds the
  edition itself through `workflow_run`), then the edition builds with what
  exists. No 80% floor — the point is a full slate. Never express the
  release as a UTC hour: 07:50 PT is 14:50 UTC under PDT and 15:50 under
  PST. The Worker's `EDITION_DISPATCH` fires at 07:50 and 09:01 Pacific
  from the Worker's ONE cron trigger (`"1,7,16,31,37,46,50 6-17 * * *"`,
  shared with the show slots — Oct 9 2026: the Cloudflare account was then
  on Workers Free, five cron triggers in total, Voices held three, and the
  deploy with a second scheduler trigger was refused with code 10072, so
  the edition dispatch had never gone live; the account is on Workers Paid
  since, see the Oct 9 runner note) and converts to Pacific
  in the handler; GitHub fallbacks 14:55/15:55/16:05/17:05 UTC. Every
  lineup slot lands by ~12:40 UTC, two hours ahead (guarded). Nerra
  Personal follows the edition to ~8am. **A show run's push resolves a
  `blog/<show>/*.html` conflict by keeping its own render**
  (`push_show_artifacts.sh`): on Oct 7 the multilingual sweep re-rendered
  Fascinating Frontiers' posts mid-run, FF / First Principles / SpaceX went
  to recovery PRs #1376-#1378, the late GitHub cron produced FF and FPD a
  second time, and the edition shipped without all three. Operator:
  `wrangler deploy` in `workers/scheduler`. Register
  `nerra-daily-8am-pacific-2026-10-08`; guards
  `tests/test_nerra_daily_8am_pacific_2026_10_08.py`,
  `tests/test_push_show_artifacts.py::TestTheBlogCollision`.
  **Aug 25 2026 first quality pass** (review:
  [`docs/reviews/nerra_daily_review_2026_08_25.md`](docs/reviews/nerra_daily_review_2026_08_25.md);
  ledger `docs/reviews/ledger/nerra_daily.yaml`): audio core verified
  healthy (promo cut 44/44 segments, all `kind=promo`), but the
  periphery wasn't — every blog post titled itself with the italic
  byline (fixed: the rundown now emits the `> **<hook>**` blockquote
  via `edition_hook()`, `engine/blog.py` skips full-italic bylines,
  four rundowns backfilled), and **being a virtual show made it
  invisible to every shows-glob loop**: OP3 never resolved its feed
  (fetcher now reads registry-only shows from `network_meta.yaml` —
  `_virtual_show_targets`), the dashboard cost rollup missed its
  credit files (`_VIRTUAL_COST_SLUGS`), and no per-build record
  existed (now `metrics_ep*.json`: cut kinds, `missing_expected` —
  Offshore North published 17:04 on Monday 2026-08-24, after the
  15:07 force-build, and the miss was uncountable). A new virtual
  show must be added to those two lists or it repeats the hole.
  Mira's handoffs now commit into the rundown .md (tic-detection
  substrate + unique blog prose), and both prompts gained data-side
  rotation memory (`{recent_openers}` / `{recent_field_notes}` — all
  four intros had opened "Good morning."). Launch registered as
  experiment `nerra-daily-launch` (readout 2026-09-22; needs the
  Apple/Spotify submission from the operator checklist).
