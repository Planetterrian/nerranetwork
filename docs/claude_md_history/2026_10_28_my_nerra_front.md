# My Nerra is the member's own front page (Oct 28 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### My Nerra is the member's own front page (Oct 28 2026)

Operator-directed: make the member page personal and as good-looking as the
front page (guards `tests/test_my_nerra_2026_10_28.py`; register
`my-nerra-front-page-2026-10-28`). `account.html` stays static and
personalizes in the browser. Rules that bind:

- **The stories come from `api/personal_front.json`**, written with every
  homepage build (`generate_html.personal_front_payload` /
  `write_personal_front`, called at the end of `generate_network_page`; it
  never raises). Per show: name, colour, cover, schedule and the newest
  `PERSONAL_FRONT_PER_SHOW` (3) episodes as `engine.landing_test.story_json`
  rows: the full hook (never the clipped feed title in `api/episodes.json`),
  the scene, up to eight of the episode's other headlines, the feed's
  measured duration and the homepage stamp. **A members-only show is listed
  with no episodes**: its digests live in `members/` and no public file reads
  them. The file is committed by run-show's finalize (`api/*.json`),
  nerra-daily, render-video and nightly; a new workflow that runs
  `--homepage` and commits `index.html` must commit it too.
  `landing_test.recent_records` keeps `latest_record`'s ordering rule
  (summaries files are not in date order).
- **The page borrows the front page's stylesheet** (`_landing_styles.html.j2`,
  `lt-*`) for the masthead, lead, Latest rail and cards; its own classes are
  `me-*`. It lays out the member's lineup in their order (the starter lineup
  under two picks), the stories on their topics and city from every show
  (word match, inflections folded, one "+ Add to my shows" per show per
  topic), and earlier episodes to catch up.
- **One detached `Audio` plays everything** (Play today's lineup queues
  today's episodes in the member's order; the edition and the sample play
  there too), so the page sends `episode_play` and `play_personal_sample`
  itself with `tracking.js`'s parameters; positions and "Played" are
  per-viewer `localStorage` conveniences only.
- **Topics are open to every account.** The Worker stores them whatever the
  plan and the builder researches them only on Personal News Network; the
  page says so. No Worker change.
- **The studio's preview is an estimate and says so**: each show's median of
  its last three durations, a weekly show only on its day, Mira's segments as
  lines without minutes. Active members never see a checkout (the Oct 28
  rule).
