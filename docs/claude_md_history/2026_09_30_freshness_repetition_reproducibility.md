# Freshness, repetition and reproducibility (Sep 30 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Freshness, repetition and reproducibility (Sep 30 2026)

Operator-directed network review (review:
[`docs/reviews/network_review_2026_09_30.md`](docs/reviews/network_review_2026_09_30.md);
ledger `network` 2026-09-30; register `freshness-dating-2026-09-30`,
`frame-memory-2026-09-30`, `whisper-av-pin-2026-09-30`; guards
`tests/test_freshness_pass_2026_09_30.py`,
`tests/test_repetition_pass_2026_09_30.py`). The operator heard
months-old stories and repetition; both confirmed, one cause each.

**An article's date has ONE owner: `engine/article_dates.py`.** Every path
that could not date an article used to stamp it with the RUN CLOCK —
undated feed entries, every web-search result, every X post, every Google
News item (whose feed date is the INDEX date) — so it sorted to the top of
the prompt and printed today's date beside a headline the prompt called
"FRESH". A 2013 Teslarati page aired on Tesla three times (08-17, 09-08,
09-23), a 2021 Mashable story and a January-2025 Starlink deal on SpaceX,
every one behind an UNDATED URL whose page carried its real date; not one
of 691 URL-dated items was stale. Now: `date_source` on every article
(`feed` / `url_path` / `page` trusted; `index` / `model` / `x_post` /
`unknown` not), an unknown date is `""` (sorts LAST, renders no date —
never write `now` into `published_date` again), `probe_page_dates` opens
up to `date_probe_max` pages (default 12, YAML; 0 = off) for the untrusted
ones and the page date replaces the index date or the model's claim, and
`stale_article_days: 3` is on the twelve established news shows. The xAI
search helper raises `SearchUnavailable` instead of falling back to a
tool-less call (an answer from memory parsed as search results — the
route a thin day took to a months-old lead). The tracker's URL-dedup
window is its RETENTION (45 days, `content_tracking.max_days`, now
actually passed to the tracker); X posts and web results pass
`filter_recent_articles` like the RSS ladder. The Sep 23 "credit the
linked article" X fix had shipped into `_parse_x_posts`, which the live
path never calls — `_x_post_entry` is the one builder both parsers use.

**Repetition is frames and second tellings, never exact duplicates**
(`script_duplicate_sentences` 0 everywhere). Combined generation writes
PART 2 from the UN-deduped PART 1, so a dropped cross-section duplicate
was still told twice (SpaceX 2–3× per episode); `strip_second_tellings`
keeps the FIRST telling and `amend_combined_script` rewrites the stash.
Sentence FRAMES ("Before we go, keep an eye on…" FF 15/15, "If you want
to go deeper" OV 15/15, "The case on both sides" every desk 7/8) are
handled the way the ledger says works — data-side rotation memory, never
a prompt-only de-seed (five straight misses on FF): `engine/frame_memory.py`
mines the last six scripts for openers that recur with different tails
(verbatim furniture and chapter anchors exempt; a proper noun, digit or
spelled ticker in the opener is content) and the two shared podcast
snippets render `{recent_frames_block}`; opt-in `frame_memory: true` on 17
shows, MIT off (its ledger lines dominated). ⚠️ A/B-listen: the digest
input on the 12 shows, the 45-day recurrence notes, and the frame block.

**Reproducibility.** PyAV 19.0.0 (PyPI 09-29) removed a keyword
faster-whisper passes; every one of the 23 episodes of 09-30 shipped with
NO transcript and the spoken-text gate ran blind — `av>=11,<19` (floor 18.1 since Oct 9) in
requirements, and `engine/transcripts.py` retries without VAD only on a
VAD-shaped error and prints a `::error::` otherwise. Main had been red
since 09-26 on a FIXTURE (an interview transcript with no 200-char line)
with four data-driven guards behind it: a guard that reads today's
committed data must tolerate today (judge episodes ≥ 1 day old, floors as
runways, fixtures on what they mean — playbook rule). The daily health
check's word floors are the YAML's (`scripts/grok_show_check.py`; it had
flagged Tesla "66% of target" daily against 2,000 words the pipeline
never used). **The model reading that binds the next migration question:**
on the same combined path and snippet, the grok-4.7 cohort writes (4–17%
digest-verbatim, 13–19 verified claims) where the 4.3 flagships copy
(49–78%, 0–3); overlap moved with the model, not with three passes of
prompts and gates, so a script-density threshold is no longer a review
prediction. Operator items: UC skipped 4 of its last 7 days on its own
claims gate; Tesla Ep617's 17 unsourced items passed the lint; a runner
lockfile.
