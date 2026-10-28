# The Oct 27 slate (review of Oct 28 2026)

Window: Oct 27 06:00 UTC to Oct 28 01:30 UTC. Every show, every workflow run
(525), and the shipped transcripts, digests, claims ledgers and chapter files
of the day. Guards: `tests/test_slate_2026_10_28.py`. Register:
`slate-2026-10-28`.

## 1. What ran

- 21 shows dispatched on time. 16 published, the four regional desks skipped
  on `no_member_demand` (by design), and North America was produced
  members-only. The 19 GitHub fallback-cron runs were dropped by the
  duplicate guard.
- Every push landed on its first attempt: no recovery branches, no conflicts.
- 10 of 10 videos published. Multilingual: every track landed (FR on FPD and
  M&A, FR + RU on FF, SpaceX, Tesla and MIT).
- Nerra Daily Ep068: 14 segments, none missing, none uncut; X post at 11:06.
- X queue: 13 posts and 6 full-episode replies, 0 failed; 21 scheduled
  YouTube comments posted.
- Run Tests failed 5 times on the branch work of the day; main stayed green.

## 2. Hidden failures (fixed)

**Guest surveys and hello invites have never sent.** Both steps of "Fire
scheduled interviews" are `continue-on-error`, so all 236 runs read green
while both returned HTTP 400:

- `guest_survey.py` put `created_at=gte.2026-10-13T16:27:13+00:00` in the
  query string. The unencoded `+` reaches PostgREST as a space. This is the
  same bug `fire_interviews._iso` fixed on July 17.
- `hello_sessions.py` had the same bug. It also filtered `interviews` on
  `scheduled_for`, which is a column of `interview_runs`; the live schema
  (checked) has `scheduled_at`.

`survey_rating`, the interview show's headline number, has had no input since
the survey shipped. Both scripts now write `Z` instants, and the hello query
reads `scheduled_at`.

On the first fire run after merge, **7 owed surveys go out** (packages 1 to 14
days old, `survey_sent_at` null). No hello invite is due today.

**The system-package cache never installed.** All 50 cache hits warned "the
cached system packages did not install; falling back to the mirror".

- The cached `.deb` files are good: after `apt-get update` they install with
  "Need to get 0 B".
- What fails is `apt-get install --no-download`. It resolves the request
  against the image's stale package lists, which name older versions, and then
  asks for archives the cache does not hold. On a dead-mirror day the cache
  would not have helped.
- A hit now installs the cached set with `dpkg -i`. The mirror path adds `-f`,
  so a half-finished dpkg install never blocks it.

**The page-date probe stopped short of the list.** Tesla had 38 articles with
no trusted date and SpaceX 43, and each probed 12. Tesla Ep647 aired a 4 Oct
2022 IEEE Spectrum article as item 10 of its news. The article had an undated
URL and carried an X post's date. `DEFAULT_MAX_PROBES` is now 40, with 8 page
GETs at a time.

## 3. Mechanical fixes

| Defect | Episode | Fix |
|---|---|---|
| Nerra Daily aired ~20 s of SpaceX's network plug. Whisper wrote "this show is part of the \| cast…" and lost the network's name, so the weak fallback cut 20 s late. | SpaceX Ep142 in Nerra Daily (Oct 26) | Frame 1's opening clause, "before you go, this show is part of", is a frame-grade anchor. Ep142 now cuts at 437.3 s on `frame`. "Before we go" (the body teaser) is not. |
| A stray "Engineering Deep Dive" chapter at 0:42, inside the lead, beside the real "The Engineering Angle". | SpaceX Ep143 | A digest heading that a marker's spoken pattern matches *as a whole heading* takes that marker's title, never a second one. On a replay of 140 episodes only two changed: Ep143 lost the stray chapter, and Tesla Ep646 gained a correct "The Counterpoint". The committed Ep143 chapter file is repaired. |
| Chapter titles opened "1.", "3.", "11." | FF Ep235 (also Top World Ep002, Ep030) | A number inside the bold (`**1. Title — Source**`) is dropped. On the replay only FF Ep235 changed. Three committed chapter files are repaired (titles only). |
| "HLA-DRB1\*01:03" aired as "one oh three A M". | Planetterrian Ep226 | A clock time never starts glued to a letter, a digit, or a `*` glued to one. Bold `**07:30**` is still a time. |
| "4K video" aired as "four thousand video". "Apple TV 4K" became "Apple TV four thousand". | MAG 7 Ep035 | A capital K on one digit, next to a screen or video word or after "TV", is a resolution. "$4K bonus" and "4K subscribers" stay quantities. |

## 4. Corrections filed

Each was checked against the episode's own cited source. Six are `where: both`.

| Show | Ep | Error | Source says |
|---|---|---|---|
| SpaceX | 143 | The Air Force test "showed cargo could reach a battlefield within one hour", on a "Dragon-derived vehicle" after a "deorbit burn". Telesat's 14 launches all in 2026, on a "70-degree inclination". | One-hour delivery is the program's goal. The capsule (Starfall) has no engine and used cold-gas attitude control. Telesat's launches *begin* in 2026. No source gives the inclination. |
| Modern Investing | 213 | Cenovus thesis: "26-year payout growth streak". Hook: TSX energy stocks "doubled". | Cenovus raised its base dividend at a double-digit rate for six years; the 26 years are TC Energy's. Cenovus more than doubled; the sector did not. |
| First Principles | 143 | Madder at fifteen dollars a pound, alizarin at fifty-five cents, imports to near zero. | Perkin 1879: madder at 45–50 shillings a hundredweight (pence a pound), alizarin at most a third of madder's price, and imports down to a third by 1875 and a tenth by 1878. The "Idiot Index of fifteen" rested on the wrong price. |
| Unintended Consequences | 155 | Eastland "rolled the opposite way" into fifteen feet of water; concrete poured in 1915 for the davits. | She lurched to port and lay in about 20 feet. The concrete went in during 1914 (dining-room floor and aft gangway, 15–20 tons). |
| Fascinating Frontiers | 235 | A gamma-ray burst "remained active for 27 days". | GRB 220706A (2022): X-ray flaring for about 51 days observed, 27 in the rest frame; the gamma-ray emission did not last 27 days. |
| MAB | 209 | Try ChatGPT's dots "on the website or app". | Pro tier or higher ($100/month plans), desktop and mobile apps, released in late September. |
| Prediction Markets | 35 | The map said Louisiana sued an exchange (audio only). | Kalshi sued Louisiana, as the body said. |
| Tesla | 647 | An Optimus expert roundup run as current news. | IEEE Spectrum, 4 Oct 2022, on the AI Day prototype. |

Two more were checked:

- **M&A Ep216**, the hook's "half the prior price", matches the body. No correction.
- **The North America desk, Ep029 (members-only)**, said "charges are being pursued" in the Alberta RCMP probe. The Globe says the prosecutor would prosecute *any* charges, and none have been laid. `engine.corrections` reads only a show's top-level episodes, so a members-only correction has no mechanism. This is an operator item.

Audio is never edited silently. The `where: both` corrections are text plus
show notes until re-synthesized (Actions "Re-synthesize Episode", same R2 key).

## 5. Open: not fixed here

- **The fire tick ran every five minutes all day. Fixed in a follow-up
  (Oct 28).** The gate read `interview_runs` created in the last 48 hours,
  and every run is staged about a day before its slot, so each booking held
  it open for two days. Run d0cdb835 (staged Oct 26 for Oct 27 18:00) and
  then run 35cdf6f4 (staged Oct 27 for Oct 28 17:30) kept it open all of
  Oct 27: 232 dispatches, almost all "already has an active run —
  skipping". The gate now reads a run by its `scheduled_for`, in the same
  window as the interview (140 minutes ahead to 3 hours behind). Replayed
  on Oct 27's rows, 65 five-minute ticks open instead of 288, plus the
  half-hour catch-alls. Operator: `wrangler deploy` in `workers/voices`.
- **The Mira prompt is over budget**: 17,946 and 18,525 characters against
  16,000 for the two upcoming guests. Two lessons say they should not be in
  the prompt. This is a room change and needs a rehearsal PASS plus a listen.
- **Modern Investing Ep213 lost the `<fast>` wrap.** The script was 14,234
  characters, 234 over the single-call ceiling (⚠️ AUDIO). MIT runs long
  every day.
- **Nerra Daily handoffs:**
  - Ep067's `realign_handoffs` kept a wrong handoff, a Planetterrian story
    before M&A, on one shared word.
  - Ep068's revised handoffs share one passive skeleton ("… is covered by
    <Show>").
  - Neither was changed without a replay on committed editions.
- **Buttondown refuses the five public cohort shows' daily newsletters** (no
  tag exists until someone subscribes). It is logged every day; preflight
  before synthesis, as the weekly run does, is the shape of a fix.
- **Apple Podcasts Connect cookies expired** on July 25. `api/apple_stats.json`
  is three months stale. Operator.
- **The Producer inbox Slack webhook is unset**; email alerts still go.
  Operator.
- **Listener-facing tics** (prompt items, ⚠️ AUDIO): Tesla's Also Today was
  empty on 5 of 5 episodes; Vancouver had eight attribution-only sentences;
  Planetterrian read its digest aloud (59% near-verbatim); PM's digest
  narrates its own method ("walk that coefficient as the paper states it");
  "7.3 million Israelis vote" (the source says *eligible*) on Top World, Omni
  View and Nerra Daily; closings carry four to six asks.
