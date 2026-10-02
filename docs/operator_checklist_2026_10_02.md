# Operator checklist — 2026-10-02

Everything that needs a human hand, sorted by what it does for the shows
and the network. Each item says what, why, how, and how you will know it
worked. Items are grouped: **P0** is publishing integrity today, **P1** is
audience growth and the listen set, **P2** is cost, **P3** is standing
debt. Within a group the order is the order to do them in.

---

## P0 — publishing integrity (today)

### 1. Merge #1346 — main is red without it

**Why.** #1345 put the launch cohort into the Nerra Daily lineup; one
guard (`tests/test_network_sourcing_pass_2026_09_24.py`) still pinned the
cohort as excluded, so the test workflow fails on main. #1346 re-pins it
and carries the cost-rollup wiring (item 12 reads from it).
**How.** Review, mark ready, merge
[#1346](https://github.com/Planetterrian/nerranetwork/pull/1346).
**Done when.** The `Run Tests` workflow on the merge commit is green.

### 2. Recovery PRs from this morning — three to merge, eight to close

**Why.** Every show run that hit the `claims.html` conflict landed in a
recovery branch instead of main (incident:
`docs/reviews/incident_2026_10_02_claims_page_conflict.md`). Three shows'
episodes for 2026-10-02 exist ONLY on those branches; the others were
later produced again by the cron fallback and are already on main, so
merging their recovery PR would add duplicate feed entries.

**Merge (the episode is on main nowhere):**

| PR | Show | Note |
|---|---|---|
| [#1342](https://github.com/Planetterrian/nerranetwork/pull/1342) | Tesla Ep623 | the later of the two Tesla runs; its RSS entry matches the audio now on R2 |
| [#1341](https://github.com/Planetterrian/nerranetwork/pull/1341) | Fascinating Frontiers Ep211 | the morning run skipped (thin script); the afternoon run produced it |
| [#1343](https://github.com/Planetterrian/nerranetwork/pull/1343) | Omni View North America Ep010 | the later of two runs |

**Close without merging (main already carries the episode):** #1335
(Tesla, earlier run), #1337 (North America, earlier run), #1331 (Europe),
#1332 (Omni View), #1333 (MAB), #1334 (MIT), #1336 (SpaceX).
#1344 (MIT multilingual sweep): merge if GitHub shows it clean; otherwise
close — the next sweep regenerates the tracks.

**How.** Each recovery PR body has the merge instructions. If GitHub
reports a conflict on `claims.html`, `index.html` or a `blog*.rss`, take
main's copy: they are regenerated nightly.
**Done when.** `podcast.rss`, `fascinating_frontiers_podcast.rss` and the
North America feed each carry a 2026-10-02 item.

### 3. Delete the duplicate YouTube uploads

**Why.** The shows whose morning commit never landed were produced twice;
each pair is the same episode number, and the first-run audio no longer
matches what the feed serves (the second run overwrote the R2 object).
**How.** YouTube Studio → Content → delete the FIRST-run set:

| Show | Ep | Delete (first run) | Keep (second run) |
|---|---|---|---|
| SpaceX Daily | 118 | `URusYUpURHA`, `qgEj0DZdGCY` | `MCinhcrFzcE`, `NE8yIptD0Ag` |
| Omni View | 193 | `wd1GI1PUaL4` | `8nZqwM2a9-Q` |
| Modern Investing | 188 | `A-IFmrF-hjI`, `zous257_wlc` | `5_ZohSj5SvM`, `vt7WYCwkBD0` |
| MAB | 184 | `0pidkDS1Jho` | `cNg5zjZvUZk` |
| Tesla | 623 | `jhzRkuROmO8`, `VvqCtm_62N0` | `hCCjB85spgg`, `WEx76pLRgho` |

Europe Ep010 and North America Ep010 were also produced twice; their ids
are in `digests/<show>/youtube_videos.json` on the recovery branches
(#1331 vs main; #1337 vs #1343). The pipeline has no delete path by
design.
**Done when.** Each channel shows one upload per episode number for
2026-10-02.

### 4. Redeploy the scheduler Worker

**Why.** The Nerra Daily dispatch moved from 12:07 to 13:07 UTC with the
force hour (#1345). What fires is what was last deployed (landmine #24),
so until this runs the Worker fires at 12:07, the gate says "wait", and
the build waits for GitHub's 13:23 cron, which is often late.
**How.** From `workers/scheduler/`: `wrangler deploy`. Then open the
Worker's `GET /` status page and confirm `edition_dispatch` reads
`13:07`. `scripts/check_scheduler_deploy.py` diffs it nightly if the
repo variable `SCHEDULER_STATUS_URL` is set (item 20).
**Done when.** Tomorrow's `metrics_ep044.json` for Nerra Daily shows a
build between 13:07 and 13:30 UTC with `missing_expected: []`.

### 5. Redeploy the gallery Worker

**Why.** `workers/gallery/src/handlers.ts` gained the thirteen cohort
newsletter tags plus `DP Pod` and `Nerra Voices` on 10-01, and the
Personal picker vocabulary. Until deployed, a signup on any cohort show
page is accepted and its show tag dropped.
**How.** From `workers/gallery/`: `npx vitest` (the suite is not in CI),
then `wrangler deploy`.
**Done when.** A test signup from `ai-chips.html` shows the show tag in
Buttondown.

---

## P1 — audience growth and the listen set

### 6. Submit the thirteen cohort feeds to the directories

**Why.** None of the thirteen launch-cohort shows is listed anywhere. OP3
resolves feeds through Podcast Index, so nothing they publish is counted
until that submission; Apple and Spotify are where the ratings asks point.
This is the largest audience lever on the list and costs nothing.
**How.** `docs/podcast_directories.md` carries one row per show with the
feed URL, in submission order: Podcast Index first
(podcastindex.org/add), then Apple Podcasts Connect, Spotify for
Creators, Amazon Music, and YouTube Music via RSS. Paste each show's
Apple and Spotify URL back into `shows/network_meta.yaml`
(`apple_podcasts_url`, `spotify_url`) so the rating asks on the posts,
newsletters and closings link the real pages.
**Done when.** `api/op3_stats.json` shows `resolved: true` for the
thirteen and Mission Control's audience card stops reading "not indexed".

### 7. Decide the unmeasurable language tracks (about $24 a month)

**Why.** Chinese tracks on Tesla, SpaceX and Fascinating Frontiers
(~$13/mo) have no channel, no directory listing and zero measured
downloads in two months; French tracks on First Principles, Models &
Agents and Env Intel (~$11/mo) have feeds OP3 has never indexed. Either
is fine; paying for an unmeasured one is not.
**How, to keep them.** Submit the per-language feeds
(`<show>_podcast.zh.rss`, `<show>_podcast.fr.rss`) to Podcast Index and
read `multilingual.by_language` on the dashboard in four weeks.
**How, to stop them.** Remove `zh` (or `fr`) from `multilingual.languages`
in the show's YAML. The committed feed files stay as they are; nothing a
subscriber holds changes.
**Done when.** The dashboard's multilingual card shows no language with
`measured: false`.

### 8. The five video-podcast feeds: submit or switch off

**Why.** Tesla, SpaceX, Fascinating Frontiers, M&A and MAB upload a
~230 MB MP4 per episode to R2 for Apple video feeds that appear never to
have been submitted (no video show in `api/apple_stats.json`). Small
money now, growing every month, serving nobody.
**How.** Either submit each `*.video.rss` as a NEW show in Apple Podcasts
Connect (checklist in `docs/video_podcasts.md`), or set
`video_podcast.enabled: false` in each show's YAML.
**Done when.** Apple lists the video shows, or the uploads stop.

### 9. The A/B listen set (landmine #17)

Every one of these changed shipped audio or Mira's spoken links; listen
to one episode each and revert by git if any sounds wrong.

- **Nerra Daily** (first 26-show edition after #1345): Mira's handoff
  count triples. Listen for handoffs that repeat a headline or open on
  the show's name more than one in three.
- **Platform ask closings** (any show, alternate days since 10-01): one
  follow-or-rate sentence before the YouTube call-out.
- **Flag-mode episodes** (every show since 10-01): nothing is removed
  any more; listen for a sentence that should not have aired and, if you
  find one, file a correction (`docs/corrections.md`) rather than
  reverting the policy.
- **Frame memory and story clusters** (17 and 22 shows, since 09-30):
  fewer repeated openers and fewer same-story retellings.

### 10. Read the first flag-mode week

**Why.** The policy trades removal for marking; the readout decides
whether it holds.
**How.** Mission Control → the claim-ledger card, and `claims.html` on
the site after the nightly. Per show, the numbers are
`source_integrity_stripped_sentences` (must be 0) and
`source_integrity_flagged_claims` in `metrics_ep*.json`. UC should
publish every day again (it skipped 11 of 28 on the old gate).
**Done when.** 21 days with zero strips and no claims-gate skips; the
register entry `claims-flag-policy-2026-10-01` has the targets.

### 11. Three show-review PRs await your decision

[#1326](https://github.com/Planetterrian/nerranetwork/pull/1326) Tesla,
[#1322](https://github.com/Planetterrian/nerranetwork/pull/1322)
Unintended Consequences,
[#1321](https://github.com/Planetterrian/nerranetwork/pull/1321)
Longevity. Merging advances the review rotation; closing unmerged is
recorded as a rejection in the ledger's `do_not_retry`. Prompt changes in
them are A/B-listen items.

---

## P2 — cost (after the measurement lands)

### 12. Read the corrected cost rollup

After #1346 merges and the nightly runs, the Mission Control cost card
shows multilingual, motion clips and the reviewer as lines of their own.
Expect roughly $245 a month against the $192 shown before. Two lines
start at zero and fill in: the reviewer after the next daily audit
(`digests/_review/`), motion clips after the next Tesla, SpaceX or FF
episode (`services.motion_api` in its credit file).

### 13. Hook-Short motion clips — readout 2026-10-13 (about $25 a month)

**How.** Compare `variant: motion_open` against the earlier stills on
the early-reach card (`api/youtube_early_reach.json`, EN, Tesla / SpaceX
/ FF). If the clip does not lift the hook Short's age-3 median, set
`youtube.hook_short_motion: false` on those three YAMLs.

### 14. Long-form on Omni View and Modern Investing (optional)

Six to nine views per long video at age 3. The adaptive policy keeps
them because `long_vpd` sits above the 1.0 floor. Raising
`LONG_VPD_FLOOR["en"]` in `engine/youtube_policy.py` to about 3 would
drop both and save roughly $10 a month in images and render time. Real
viewers are on the other side of that one, so it is your call, not a
free saving.

---

## P3 — standing debt (none urgent, all real)

15. **Age of AI chapter lists.** Three episodes' Supabase
    `editorial_packages.chapter_markers` rows still hold the fabricated
    lists removed from the site on 09-22; there is no chapters-only
    re-run yet. Ask for one when you want the rows clean.
16. **Offshore North cover art** (open since the Sep 19 pass).
17. **09-30 transcripts.** The 23 episodes of 09-30 shipped with no
    transcript (the PyAV break). Backfilling needs Whisper on the R2
    audio; ask for the script when you want them.
18. **SpaceX Ep117 recorded zero claims** on 10-01 — a read of its
    digest against its sources, or let the flag-mode week answer it.
19. **Buttondown tag audit.** Dispatch `buttondown-tag-subscriber.yml`
    in `list-all` mode once to settle which subscribers carry which
    tags; the `/tags` endpoint cannot say.
20. **Two secrets/variables to confirm:** `PERSONAL_BATCH_DISPATCH_TOKEN`
    (so the Nerra Personal build follows the edition instead of waiting
    for its late cron) and the repo variable `SCHEDULER_STATUS_URL` (so
    the nightly can diff the deployed Worker against the committed one).
21. **YouTube Studio playlists** for any show you later enable on
    YouTube: flag the playlist as a podcast once (landmine #15).
22. **Russian spoken AI disclosure** is still English on the Olya voice
    (A/B-listen item, one line in `run_show.py`).
23. **X handles** for Omni View, Models & Agents and Modern Investing so
    the cross-promo reply can name them.
24. **MIT:** `scripts/recompute_mit_benchmarks.py --apply` (rewrites
    published performance numbers; needs market data) and the SnapTrade
    Phase-0 verification.
25. **Git history** (2.2 GB of MP3s in history, HEAD clean) — the
    `git filter-repo` rewrite needs a paused-cron window; playbook in
    `docs/workflow_review_2026_06_10.md`. Not urgent.
