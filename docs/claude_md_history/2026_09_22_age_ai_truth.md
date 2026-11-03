# Sep 22 2026 — The Age of AI: the pages say only what the record supports

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 22 2026 — The Age of AI: the pages say only what the record supports,
and a publish that renders the page before the post.** Guards:
`tests/test_age_of_ai_truth_2026_09_22.py`; register
`age-of-ai-truth-pass-2026-09-22`. What binds:

- **`generate_html.py --show <slug> --blogs` writes the POSTS first.** Every
  article link on a show page is a file-exists check (`_blog_url_for_episode`),
  and the Nerra Voices publisher writes only the digest `.md` and then calls
  exactly that command — so the page rendered with no link to the episode it
  had just published, every publish (Ep6 and Ep7 both), repaired only by the
  nightly. run_show never hit it because it writes the post HTML itself. The
  guard runs the real `main()` with recorders and asserts the call ORDER.
- **A chapter list is shown only when the transcript vouches for it**
  (`engine.interviews.supported_chapters`, the same shape as the claims
  gate). Ep5–7 shipped chapter lists about a film studio banning AI
  storyboards — for a network-automation builder, a propulsion founder and a
  novelist — because `02_chapter_markers.txt` supplied that exact title as
  its example and the model reproduced it (de-seed by shape applies to the
  Voices editorial passes too; the specimen is gone). Calibrated on all seven
  episodes: the real lists (Ep2–4) pass every title, the fabricated ones pass
  at most one in six; the guest's name and "ai" vouch for nothing on this
  show. The three lists were REMOVED from the committed digests and
  summaries; the Supabase `editorial_packages.chapter_markers` rows still
  hold them, and there is no chapters-only re-run yet (operator item).
- **Run time comes from the feed's `itunes:duration`, never from chapters.**
  `_run_time` used to read the last chapter's `end`, so it was wrong on
  EVERY episode, not only the fabricated ones — Ep2 "23 min" beside a player
  reading 44:52. `feed_durations(rss_path)` is threaded through both the
  show-page cards and the post context.
- **The co-host is read from the transcript, in both directions.** The
  credit said Patrick "is not in the room while Mira is talking to a guest";
  he co-hosted five of the first seven episodes (every one but Ep4 — Ep6
  labels him `PATRICK:` in capitals, which is how a case-sensitive count once
  read it as zero). `cohost_label` reports a label with ≥ 5 lines that is
  neither Mira nor the guest; the show page and the post say "with Patrick
  Novak" on exactly those episodes. The credit now states the arrangement in
  Mira's own prompt: she conducts every interview, he joins as co-host when a
  guest has asked for him, he never answers for the guest afterwards. The
  old guard PINNED the false sentence; the new one checks the copy against
  the committed transcripts. A guard that pins a claim is only as good as
  the claim.
- **Gate 2 is described as built.** `MIRA_FIRST_CLAIM_BASIS`, the interview
  steps, `about.html.j2` and the topic-hub copy all said nothing publishes
  "until the guest has approved it"; `gate2Housekeeping` auto-approves after
  seven days of silence (operator-confirmed to keep the timer, 2026-09-22).
  The copy now says: a week to approve, cut from or refuse the transcript;
  cuts removed from the audio, not bleeped; takedown available afterwards.
  The narrow claim (the guest holds the final say) survives on those terms.
  The guard reads `workers/voices/src/index.ts` for the auto-approve and
  fails any surface that claims the stronger gate while it exists.
  **Nov 2 2026:** the feed description Apple and Spotify show, the
  registry (`about_host`, meta descriptions), the terms of service, the
  guest-picks page and Mira's producer replies to guests still said "the
  guest approves the transcript before it publishes". All of them were
  corrected, and the guard now sweeps them
  (`tests/test_review_followups_2026_11_02.py`).
- Every blog post on the site printed `\ud83d\udc4d` where a thumbs-up
  belonged — JSON escapes pasted into `blog_post.html.j2`. A guard sweeps
  every template for surrogate escapes.
