# YouTube + show review — 2026-10-03

Operator brief: review every show's latest episodes for quality, content and
streamlining; improve the YouTube videos to win viewers and subscribers; and
explain why views and subscribers were much higher in August, then fell after
changes were made — and get back to what worked.

Method: every nightly `api/youtube_stats.json` snapshot since 07-10 (94
snapshots, read from git history) rebuilt into a daily per-channel series;
per-video stats by publish day, channel, format, Short window and show;
matched-age reads from the stored snapshots; the per-episode metrics files;
the commit history of every dub, render, prompt and policy path; and two
read-only content reviews of the latest episodes (15 established shows,
13 launch-cohort shows). Guards: `tests/test_show_review_2026_10_03.py`,
`tests/test_dub_short_titles_2026_10_03.py`.

## TL;DR

1. **The August peak was the Russian channel.** RU Shorts were ~75% of all
   network views. Weekly views (all channels): ~44k in the weeks of 08-03
   and 08-10, ~20k in the weeks of 09-14 and 09-21. RU fell ~31k → ~9k a
   week; EN is about where it was in early August (it fell only against
   its own 09-04..06 breakout); FR fell modestly.
2. **It is reach per video, not volume, and not the videos getting worse.**
   RU uploads stayed at ~10 Shorts a day until 09-21 while the median RU
   Short fell from 260–400 views (early Aug) to ~50 (from 09-14). The
   viewers who did see them watched as much as before (average view
   percentage ~50% throughout); every audience country fell together (the
   country mix is unchanged — not a Russia-side block); and no change to
   the RU videos lines up with either drop (§2). Same reading as the 09-22
   review: YouTube distributed @NerraRU less.
3. **Our own volume cuts cost ~6% of the loss.** EN Shorts went from ~15 to
   ~6 a day (one-Short cap + dead-Shorts tier, operator decisions 09-22)
   and RU from ~10 to ~7 (the ladder lowered Tesla/SpaceX from 3 to 2 as
   their reach fell). Priced at what the cut Shorts earned: ~200 views a
   day of a ~3,500/day fall.
4. **Two things we did own, both fixed now.** (a) English long-form lost
   viewers in the first minute after 09-21 on Tesla/FF/M&A/MAB/MIT: the
   body stopped opening on the story the cold open sold (Tesla 82% of
   episodes since 09-22, MAB 92%); SpaceX, whose body follows its hook,
   held. (b) RU/FR extra Shorts shipped transcript fragments as titles
   («2026 года», «в 2026 года» on 10-03).
5. **Subscribers fell with views.** Conversion barely moved (RU Shorts
   ~0.85 per 1,000 views, EN long-form 1.4–3). All 15 top subscriber-
   earning videos are space content (FF, SpaceX) on all three channels.

## 1. Where the views went

| week | EN views | EN subs | RU views | RU subs | FR views | FR subs |
|---|---|---|---|---|---|---|
| 07-27 | 7,782 | 55 | 18,810 | 19 | 21 | 1 |
| 08-03 | 8,629 | 26 | 33,845 | 29 | 1,393 | 7 |
| 08-10 | 11,095 | 48 | 28,789 | 32 | 3,448 | 12 |
| 08-17 | 8,216 | 31 | 9,097 | 12 | 3,358 | 16 |
| 08-24 | 11,778 | 42 | 20,060 | 17 | 2,686 | 5 |
| 08-31 | 19,379 | 30 | 23,900 | 27 | 3,280 | 8 |
| 09-07 | 16,023 | 21 | 19,236 | 22 | 3,193 | 10 |
| 09-14 | 8,754 | 15 | 11,205 | 12 | 2,565 | 4 |
| 09-21 | 9,960 | 31 | 7,849 | 11 | 1,876 | 5 |

Median RU Short views by publish week: 190 (07-20), 267, 260, **398
(08-10)**, **16 (08-17)**, 172, 224, 185, **60 (09-14)**, 50 (09-21). A
Short earns its views on day one, so a channel's daily views ≈ uploads per
day × views per upload; the uploads held, the second factor fell.

**The 08-18..21 blackout.** Every RU Short published on those four days —
hook Shorts included — got 1–8 views, then reach came back on 08-22 with no
change to anything on the dub path. EN and FR were not affected. That is a
channel-level hold; Studio may show why (operator item).

## 2. Hypotheses tested and rejected

| hypothesis | evidence against |
|---|---|
| Dubs lost their scene images (Sep 13 incremental manifest) | Every recent episode has 8+ 16:9 and 5+ 9:16 scenes in the manifest |
| A Russia-side block or throttling | Country shares on the RU channel steady (RU ~35%, UA ~16%, KZ ~9%) while all fell |
| The Sep 15 TTS request change | Default unchanged, request byte-identical; landed after the drop began |
| Staggered publishing | Launched 08-06; RU had its best ten days after it |
| Publish time of day | The dub workflow's schedule has not changed since August |
| The 13 new shows crowding the EN channel | None of them uploads to YouTube |
| Fragment titles cost the reach | Fragment-titled RU Shorts: median 149 views; clean titles: 161 |
| The Sep 22 own-scene library change hurt long-form | SpaceX got the same change and held |

## 3. What shipped in this pass

- **Body opens on the hook's story** (`engine/intros.build_cold_open_spec`,
  one shape-only bullet; ⚠️ prompt — A/B-listen Tesla and MAB). New
  read-only metric `script_hook_leads_body_pct` (`engine/script_audit`).
  Register `hook-leads-body-2026-10-03`.
- **Dub Shorts never titled with a fragment** (`ScoredWindow.window_text`,
  `engine.titles.is_fragment_title`, `_window_short_headline` in both dub
  paths; the fallback's tag-in-the-middle bug fixed before it could ship);
  the dashboard's fragment metric now sees digit/capital-start fragments.
  `scripts/retitle_youtube_videos.py --channel ru|fr` proposes repairs for
  the 70 live ones (dry run by default). Register
  `dub-titles-never-a-fragment-2026-10-03`.
- **The sibling plug says "weekly" for a weekly show** (`engine/network_promo`
  via `engine.cadence`; daily plugs byte-identical). ⚠️ spoken text.
- **Pronunciation formatting** (`assets/pronunciation.py`; ⚠️ spoken text):
  "UN" is case-sensitive ("Kim Jong-U N", "U N American"); NT$/HK$/S$/SG$/
  A$/AU$/NZ$ name their currency ("NTsix hundred million"); no "subreddit
  subreddit"; a zero-padded code is not a range.
- **Self-narration**: "…is in the item / material / note", "supplied note",
  "today's pile" (absence-flavoured, end of clause — "defects in the
  material" stays). Cohort shows only (where the filter is on).
- **De-seeds by shape** (⚠️ A/B): Omni View's go-deeper sentence (aired 8/8)
  and teaser lead-in; SpaceX skips the AI segment when its section is empty
  instead of re-telling Top News (empty on 6 of the last 9 days).
- **Length targets that fit the format**: Top World 1,400 → 1,150 (median
  ~1,040; 10-03 skipped at 821 < 840); Collingwood 1,000 → 900 (Ep002 told
  ~25% of its sentences twice).
- `tests/test_pronunciation.py` timezone corpus guard re-pinned to its
  meaning (main was red on it: Vancouver's "PST" is a sales tax).

## 4. Episode review findings not shipped (operator / A-B decisions)

Established shows:
- **Headline-less item bodies** (P0, prompt): the script drops the bold
  headline, which is often the only place the subject is named ("The
  protein blocks…", "The crew supported…"). Shape rule: an item's first
  spoken sentence names its subject.
- **Stories told 2–4 times** (Tesla Ep623 deliveries ×3, SpaceX Ep118
  Suncatcher ×4, FF Ep211 launches ×3). `digest_overlap` could also match
  items sharing an exact distinctive figure.
- **Raw social text on air**: view counts, Reddit usernames, press-release
  booth numbers; FF had 9 of 16 sources on x.com despite `secondary`.
  Strip counts/usernames at fetch; cap X items on `secondary` shows.
- **MIT spends ~45 of its first 30 s on the disclaimer** in every episode —
  moving it before the practice segment is a compliance call.
- Tics: PT "keep an eye on further", Env Intel "if you only note one thing
  today", Offshore North "the campaign's next concrete milestone".
- **Offshore North** led two episodes with the same 2 September position —
  the record needs a new dated fix.
- Closings are 10–17% of runtime on several shows.

Launch cohort:
- Top World retells the desks (4 of 10–11 sources shared, Both Sides on the
  same question a day after Europe).
- AI Chips / MAG 7 say the calendar date three times (teaser rule).
- "In France, in Europe," (Top World first-sentence rule) ×5 in one episode.
- Longevity Ep002 ran on the 4.3 fallback with a 2021 meta-analysis as its
  hook; Peptides' spotlight had no peptide material. Merging Peptides and
  Longevity into one weekly pools two thin supplies (no shared sources).
- North America's 10-02 episode exists only on two recovery branches —
  merging both would double-publish the day.

## 5. Recommendations, by expected effect

1. **Studio check on @NerraRU** for 08-17..22 and 09-13..16: Channel
   dashboard notices, Content → Restrictions column, any email about
   reused/inauthentic content. If a restriction exists, it is the cause and
   the fix is an appeal, not code.
2. **Put the RU supply where the RU audience is.** FF-RU's hook Short still
   earns a median 315 views (age 3, last 21 days) and its extras 113;
   Tesla-RU earns 31 / 38, SpaceX-RU 50 / 32. A 4th FF-RU Short (+~100
   views/day) is worth more than restoring Tesla/SpaceX's 3rd (+~70).
3. **Retitle the 70 fragment-titled dub Shorts** (Actions "Retitle YouTube
   Videos", channel ru then fr, dry run first).
4. **A/B-listen** the first post-merge Tesla, MAB, Omni View and SpaceX
   episodes, and one weekly-show plug.
5. Keep EN at one Short per episode: the cut Shorts earned a median 6
   views and ~0 subscribers; the cap is not what cost the views.
