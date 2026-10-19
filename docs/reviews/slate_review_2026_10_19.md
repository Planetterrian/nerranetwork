# Slate review — Oct 19 2026 (first day on the Eastern schedule; first live video job)

Window: 2026-10-18 14:40 UTC to 2026-10-19 12:30 UTC. One read-only reviewer over
the runs and the Oct 18 launch-cohort episodes, then the Oct 19 slate read from the
committed metrics; every finding below was verified against the committed data
before it was acted on.

## The day

- **26 show runs between 04:00 and 06:10 ET, every one dispatched by the scheduler
  Worker to the minute** (the Oct 17 Eastern table went live with this morning's
  `wrangler deploy`). 21 shows published; the five regional desks skipped on
  `no_member_demand` (the gate working). Spoken-text gate 21/21 pass. No model
  fallback anywhere. Vancouver at 08:15 ET.
- **Nerra Daily Ep060 built at 06:35 ET with all 17 expected segments** and queued
  its X post for 7:00 ET. The Worker's two edition dispatches did the work; the
  28 `workflow_run` wake-ups of the day all exited on the fast gate.
- **The video job's first live day: 12 handoffs, 11 renders published, 0 lost.**
  Long-forms rendered in 558–1,436 s against needs of 600–1,545 s; a Short on
  every show whose policy allows one (28.7–35.0 s); caption tracks uploaded;
  X posts carried the Short on FF, M&A, MIT, OV, PT, SpaceX, Tesla, UC. SpaceX's
  `homepage` job was superseded in its concurrency group (the next show's
  rebuilt the page); UC and DP Pod published no video by policy (shorts-only /
  probe tier). Planetterrian lost one scene to content moderation and fell back.
- Runs that failed: the two members-only series runs (fixed in #1491). Cancelled:
  one Tesla finalize (concurrency) and the SpaceX homepage job (same).

## Defects found and fixed in this PR

1. **A bold `**Title: Outlet**` line and its paragraph counted as two blocks**
   (`engine.digest_lint.items`), so MAG 7 Ep026 recorded
   `items_without_source_shipped = 3` on seven sourced items. The title-only
   block now absorbs the paragraph after it.
2. **Every one of the 20 IMOCA boat pages failed to parse in the nightly**
   ("page carried no ProfileCard facts"): imoca.org dropped the ProfileCard
   spans and the facts now sit in a plain `<th>` table. The parser reads both.
3. **Fascinating Frontiers Ep227 shipped three stories from 44 articles**
   (6.5 min, 1,206 prose words under a 1,400 floor). The log shows three
   generations, three stories each, each padded to the word floor by the
   expansion retry, which tells the model to "prefer fewer items at full depth";
   the validator's `min_items 8` never got a retry of its own. The retry now
   names a story section under its item floor and asks for stories from the
   material, ranked above the depth rule (`engine.generator.digest_item_shortfalls`).
   FF's last ten episodes carried 15, 7, 2, 7, 0, 12, 7, 8, 5, 3 items.
4. **Models & Agents Ep208's hook blockquote was `> **# Models & Agents**`** —
   the model bold-wrapped the title line, `promote_hook_to_blockquote` took it
   as the hook, and 337 related cards across the blog read "# Models & Agents" as
   the episode's headline. The promotion skips a heading; the committed digest
   and summaries record were repaired by hand (the nightly regen re-renders the
   cards).
5. **AI Chips Ep027 said RTX Spark laptops start at $2,599 three times**, from an
   iTWire report; Nvidia's own announcement says $2,399 and MAG 7 aired that
   figure the same day. Correction filed (`digests/ai_chips/corrections.yaml`,
   `where: both`) and applied to every text surface. The audio still says
   $2,599 — operator: Actions "Re-synthesize Episode" for ai_chips Ep027.
6. **The Voices fire tick dispatched 148 runners in twelve hours** with two
   interviews whose runs had already fired ("already has an active run —
   skipping"): the gate's 48-hour lookback on INTERVIEWS held it open all day.
   Interviews are now read in a three-hour window around their slot; the
   no-show sweep's two-day read of the run table is unchanged.
7. **The producer inbox spent a Grok call per GitHub-notification thread** (7–8
   threads, 48 ticks a day). A known platform sender is a `platform_notice`
   without a model call.
8. **The video job's multilingual dispatch rode the `homepage` job**, which the
   concurrency group supersedes (SpaceX today); it now rides the render job's
   own push.

## Found and not fixed here (operator or next review)

- **Nerra Daily Ep059 (Oct 18) shipped 8 of 14 segments**: the edition was built
  at 12:40 UTC and six shows' re-runs landed 12:42–13:15 after the morning's
  smoke-step failures. There is no `--replace`; rebuilding would re-publish the
  R2 object under the live enclosure URL (every subscriber re-downloads). Your
  call.
- **The Sunday week-in-review segment aired garbled sentences on MAG 7, Top World
  and Omni View** ("House House kept August's Big Walk off Xbox", "locked in an
  El Niño without precedent"): compressions of true earlier items, outside the
  claims gate because they cite nothing in the day's digest. ⚠️ AUDIO; the
  second review to flag the segment. A gate-side fix (the recap's sentences must
  trace to the lake's committed digests) is the next step.
- **Top World ran 6.8 and 7.6 minutes against a twelve-minute promise** two days
  running: digests over their 1,900-word floor, scripts of 1,053 and 1,236 words
  on grok-4.7, coverage 50–65%. Prediction Markets read 49% coverage. The
  script-side lever is a prompt change (A/B); the honest alternative is to state
  the length the show actually runs.
- **MAG 7 Ep026 self-narration** ("Microsoft appears here as one of the laptop
  brands", "Apple's figure in this set is a device price") and a lost forced
  review: the Show Review Agent wrote `mag7_review_2026_10_18.md`, its push
  failed with unreadable stderr (fixed in #1488 after the fact), and the review
  is on no branch. Re-dispatch "Show Review Agent" with `FORCED=mag7`.
- **Vancouver Ep026's WYNTK names a new mayor in Richmond** that no item reports
  (the Richmond item was lost in the hook-recurrence regeneration). True per
  the first draft's CBC claim, but unsourced on the page.
- PR #1476 was merged with its Run Tests red and two PRs merged onto red main
  (14:57–15:15 UTC); fixed by #1479. Check the conclusion before merging.
- The scheduled multilingual sweeps rewrite ~1,100 blog pages across seven
  commits a pass with no new audio (the afternoon's chrome changes). Churn, not
  breakage.
