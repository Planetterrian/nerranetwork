# The Oct 28-30 slate: a timeout that cost an episode, a silent edition, cut links (Oct 30 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The Oct 28-30 slate: a timeout that cost an episode, a silent edition, cut links (Oct 30 2026)

Review [`docs/reviews/slate_review_2026_10_30.md`](docs/reviews/slate_review_2026_10_30.md);
register `slate-2026-10-30`; guards `tests/test_slate_2026_10_30.py`. Rules
that bind:

- **A finished episode never fails on one transport error.** Post-run
  validation retries an enclosure that times out or answers 5xx (8, 20 and
  45 s); a 4xx fails at once. AI Chips Ep037 was in its feed when one 8 s
  timeout on its new MP3 failed the run; nothing was pushed and the fallback
  cron made it again at 17:01.
- **A published file is pulled back down through `engine/http_download.py`.**
  It has a wall clock per attempt, a 60 s read timeout, 3 attempts, a `.part`
  file and one log line per file. Nerra Daily (with a 20-minute loop budget)
  and Nerra Personal both use it, and their ffmpeg calls time out at 600 s.
  Ep069 sat 81 silent minutes behind a read-timeout-only `requests.get`.
- **A Google News link keeps its query string.**
  `url_utils._garturlres_url` parses the batchexecute reply as JSON. The old
  regex stopped at the `\u003d` that encodes `=`, so every resolved
  `?id=`/`?news_id=` link lost its value, about one a day since Sep 23.
- **An unreadable 2xx is `unverified_unreachable`, never `not_found`.** A PDF
  source is not a fabrication. A claim that verified is never flagged by its
  own duplicate entry.
- A Peptides card slot is its label at the start of a line, bold or plain.
- Prediction Markets' Week's Board reads "that date" as Yes and reports a new
  leader as a change, never as a price move.
- Nerra Daily's opener memory collapses spelled dates. The handoff revision
  also sends back a handoff that restates the next headline (60% of its
  salient words), and no handoff ends on ", <Show> examines".
- UC's script runs at most about 1.5x its brief. Tesla names Also Today in
  its required sections.

⚠️ AUDIO: the UC, Tesla and Nerra Daily prompts. A/B-listen the first
episode of each.
