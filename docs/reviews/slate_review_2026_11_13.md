# 48-hour slate review (Nov 11 12:00 UTC to Nov 13 12:30 UTC)

Scope: every show episode, video job and workflow run in the window. 36
episodes (the Nov 12 and Nov 13 slates, Vancouver Nov 11-12, Peptides,
Collingwood), 30 video renders, 2 Nerra Daily editions and emails, and every
Actions run (read through the REST API). Inputs: `digests/*/metrics_ep*.json`,
the committed scripts and transcripts, `api/daily-review.json` (Nov 12 audit;
the Nov 13 audit runs at 22:15 UTC), and the run logs.

## What is healthy

- Every scheduled show published on both days; the four members-only desks
  skipped by design (`no_member_demand`). No missed or failed show run.
- Loudness is in spec on every episode (-15.7 to -16.6 LUFS, true peak under
  -0.9 dBTP); the spoken-text gate passed all 36.
- Video: 30 of 30 render jobs green, long-forms and hook Shorts uploaded
  where the policy asked, caption tracks on every long. Render time runs
  1.4-2.1x the audio, inside the 2.1x budget (AI Chips sits at the edge).
- Nerra Daily Ep084/085: 15 segments, none dropped, emails sent.
- Omni View Ep235 (first episode on PR #1697): no "coverage presents" /
  "will monitor" filler (Ep234 had four), cross-episode repeat ratio 0.43 ->
  0.35.

## Findings, ranked

1. **Whole segments were silently cut from two episodes (fixed here).**
   Vancouver Ep051's script was 1,997 words and 1,618 were spoken; its Both
   Sides segment on the density rules is missing, though the map promised it
   (the audit scored the episode INCOMPLETE). North America Ep045 lost its
   Closer Look the same way (1,528 -> 1,112). Cause: the model opened the
   paragraph with the prompt's own `[Both Sides]` label, and
   `run_show._clean_podcast_script` drops any line that starts with `[`.
   Now the label goes and the prose stays; a bare note (`[Intro music]`) is
   still dropped. Signature for the readout: `podcast_script_word_count`
   more than 100 above `script_words` (only these two episodes, plus the DP
   Pod's speaker labels, in the whole metrics history).
2. **@nerranetwork is locked again, and the queue's own drain probably did
   it (paced here; the unlock is Patrick's).** After the Nov 12 unlock
   (~13:00 UTC) the queue posted two teasers plus one full-episode video
   every half hour for six hours, many for episodes three days old (LOCKED_MAX_AGE
   is seven days); at 19:07 a Worker dispatch and the GitHub fallback cron
   ran 80 s apart, four media posts went out in 80 s, and the account was
   locked at 19:08. Every run since is red. Now a run that meets backlog
   (a row queued 18 h+ ago) posts one post, a run within 20 min of the
   account's last post posts nothing, and a full-episode reply queued over
   36 h ago is cancelled instead of uploaded. Not proven to be X's trigger,
   but it is the only burst-shaped thing in the logs.
3. **Run Tests is red on main again (fixed here).** #1699 cleared the Omni
   View prompt failure, then `test_personal_deep_2026_10_18::test_the_gemini_launch_told_by_two_shows_is_found`
   failed on the merge because summaries files keep 30 entries and Oct 14
   rolled off Models & Agents and MAG 7 today. The entries those tests read
   are frozen in `tests/fixtures/personal_summaries_2026_10.json` and stand
   in only for a date the live file no longer carries (the Oct 17 test
   would have failed on Nov 16).
4. **Repetition is still the network's main defect.** Nov 12 audit: mean
   6.81, REPETITIVE grounded on 11 of 16 episodes, INCOHERENT on 4 (SpaceX
   Ep160 "a little over two percent lower" with no subject; Vancouver
   Ep051 "both"; AI Chips "him"; MAG 7). The FF, Omni View, FPD/UC and memory
   passes are aimed at this and read out Nov 26-27, so nothing new here.
5. **The grok-4.7 cohort overshoots its length targets.** Prediction Markets
   Ep052 2,286 words against 1,400 (14.8 min; too long for one TTS call, so
   the `<fast>` wrap was dropped and the episode played slower), Peptides
   Ep009 2,108/1,200, Vancouver Ep050 2,253/1,450, Collingwood Ep008
   1,766/1,150. The audit did not flag them. A decision, not a fix.
6. **Fascinating Frontiers Ep252 (first on PR #1698) ran 6.8 min** (938
   words, was 10.6 min on Ep251); the second half is a list of one- and
   two-sentence items and there is no deep dive. Planetterrian also ran
   short on both days (1,133 and 949 words, target 1,600; its fact-floor
   trial reads out Nov 17). Watch, owned by those threads.
7. **Offshore North's ~1 download in 30 days is distribution.** It is the
   only show with no Apple or Spotify id; Apple is still a draft and the feed
   is not in Podcast Index (`docs/outstanding.md` rows 37-38, open since
   Nov 4). The feed itself is valid (13 items, OP3-prefixed).
8. Minor: "Embed Chapters in Published Episodes" stays red on nine old
   episodes whose chapter file yields fewer than two ID3 chapters (safe,
   nothing uploaded); one Show Review run lost its push to a GitHub 500;
   the Nov 11 rehearsal failures belong to the Mira thread.

## Decisions for the operator

- Unlock @nerranetwork at x.com. With this PR merged first, the backlog
  drains at one post per half hour and stale full-episode replies are dropped.
- Whether to put a hard word ceiling on the grok-4.7 cohort (finding 5).
- Publish Offshore North on Apple and add it to Podcast Index (finding 7).
