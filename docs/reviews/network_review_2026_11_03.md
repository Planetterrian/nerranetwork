# Nerra Network — the six-month review (Nov 3 2026)

Operator brief, verbatim: *"Please do a thorough review of Nerra Network versus all the changes and improvements that we have done over the last 6 months and see what is working and great versus what still needs improvements. Ideally I am looking to have the best, most interesting, most informative, most trustworthy, best sounding shows, best landing page, best youtube pipeline and video creation process, best website and landing page, best newsletter of any news network, delivered in the most efficient and effective way possible. I also want to continue to build an amazing service in Mira's age of AI interview show and pipeline … a compelling and interesting alternative to traditional news networks which also is designed to grow and offer different languages and diverse and interesting content. I also want an amazingly beautiful design for all surfaces that anyone sees. From this review make changes to improve the Nerra Network wherever you see areas for significant and meaningful improvement."*

## How the review was done

Fourteen readers, each with one surface and one standard (the best in that surface's industry), read the committed record at `47499151b` (== `origin/main` that morning): every spoken script of Oct 27–Nov 2 (113 episodes), the Oct 1–10 window as the pre-script-arm comparison (206 episodes), every claims ledger, 124 committed versions of the daily audit, 113 stored YouTube snapshots, 99 GA4 snapshots, 131 Buttondown snapshots, the OP3 history, 7,212 Actions runs, 26 pages screenshotted at 1440×900 and 390×844, ten shipped MP3s measured against two NPR files, the Nov 2 email rendered for five tag sets and its public archive, and the Voices rooms' numbers-only Supabase record. Every number in the reader reports is marked MEASURED or INFERRED and carries its file path. The reports, the scorecard and the proposals are the session's scratch record; this document carries what binds.

A second pass (a synthesis editor, one proposer per goal area, one skeptic per area judging every proposal on three lenses, a prioritiser) turned the findings into the ranked plan in §4. Defects the readers proved in code were fixed the same day, each with a guard in `tests/test_six_month_review_2026_11_03.py` (§3).

## 1. What the record says worked (six months, one page)

- **The factory.** 100% run success on every 30-episode window; the spoken-text gate 113/113 on the week measured; transcripts, VTTs and chapters on every episode; 26 runs dispatched to the minute by the Eastern scheduler; Nerra Daily complete at 7:00 ET on every day since Oct 23.
- **Trust as a public record.** From 92 empty claims ledgers in August to 5,478 entries in October at 95.5% verified; every post carries its Verified-claims panel; 30 corrections filed in October with a mechanism behind them; the Nov 2 truth pass aligned every surface on the guest's real terms.
- **Downloads compounded.** Network RSS downloads 665/week (w/c Jun 29) → 3,760/week (w/c Oct 26), 5.7×; SpaceX 88 → 1,190; a network-wide step in the week of Sep 28 that held for five complete weeks. Cost per download $0.03.
- **The script stage writes.** On the grok-4.6 arms digest-verbatim overlap fell from 27–61% to 7–35% with coverage held at 76–87% (Tesla 26.7 → 13.8, SpaceX 47.5 → 7.1, MIT 56.2 → 7.1); wording-level repetition is gone (3 strict near-duplicate pairs in 113 episodes).
- **The grok-4.7 cohort is the in-house proof** that the same pipeline can write dense digests: 11–22% fact-free story sentences against 34–62% on the grok-4.3 flagship digests.
- **Measurement honesty is institutional.** Null never 0; rates refused under a 30 denominator; a degraded snapshot never overwrites a clean one; "same episode, different channels" settled the Sep 15 YouTube fall as distribution, not content; reach is read at a fixed age.
- **The one-email decision** (Nov 1) was the first distribution change in six months that removed surfaces instead of adding one.
- **The Age of AI's room** went from 14–17 interruptions a room to 0–1 in a fortnight, with a rehearsal harness that found four faults from room logs none of the medians showed, and the guest's terms are the best in the business and kept in code.

## 2. What the record says did not work

- **Everything that grew is consumed inside a subscription a listener already holds** (a podcast app, a YouTube channel). Everything flat asks a person to come to nerranetwork.com: ~10 human sessions a day since late September (733 of the headline 999 were sub-10-second hits on one page), organic search 19 sessions in 28 days six weeks after the topic hubs, 14 newsletter subscribers, 2 paying members after eight Personal passes, 0 captures on the RU pilot in three months.
- **The register is written and not read**: 71 of 189 entries past readout, 64% of the distribution-area entries with no live metric, 70 of 94 network-ledger predictions pending.
- **Render levers never moved the open.** Five entries on one flat retention metric closed INCONCLUSIVE; the one lever that moved it (the cold open, +2.1 pp) was spoken.
- **Three shows shipped 9 LU under spec for 208 episodes** and nothing read the number; the opening music bed had been 12 s of music and 18 s of silence since February; every music show was dual-mono; no fade ever reached silence. Audio was checked for loudness and clicks, never for envelope or image.
- **Padding is manufactured digest-side**: the expansion retry fired on 7/7 episodes of every flagship in the week to Nov 2 and 0/7 on the cohort; the deep dive is a second pass on a body item on 3–5 of 7 days on six shows; the daily audit graded TTS spellings as garbles (12 of 75 "incoherent" criticals in 16 days).
- **The closing is 12–15% of every episode and asks four to six things** — three readers independently named it the single most audible automated signal left on shows that otherwise write well.

## 3. Fixed the same day (28 items, each with a guard)

Branch `claude/gifted-albattani-m71t3f`; guards in `tests/test_six_month_review_2026_11_03.py` unless named. ⚠️ AUDIO marks a change to shipped sound — A/B-listen per landmine #17.

**Trust and the record**
1. 13 `*_short_source.flac` (571 MB) and their word JSON untracked and ignored (`digests/*/youtube_tmp/*_short_source.*`, `digests/**/*.flac`) — landmine #1's third recurrence, ridden in by the video job's `git add -A digests/` since Oct 31. The history still carries them (operator: the filter-repo playbook).
2. `assets/pronunciation.replace_dates` expands a month abbreviation only when a day or a year follows it — Nerra Daily aired "March-a-Lago" and "January Ferrigan".
3. The gate-2 email and review page told a guest "nothing goes out until you have heard it and said yes" beside the seven-day auto-approve; the Worker's five strings and the template state the real terms, and the Nov 2 guard sweeps the "nothing … until you" shape across the Worker and the Voices email templates.
4. Peptides Weekly and Longevity Weekly still ran `on_failure: strip`; `claims.html` read every one of their claims as "malformed" (138 of 138 on the last six episodes each). Both move to flag (the network policy since Oct 1) and `engine/claims_ledger` labels a status-less policy-2 entry from the gate's own lists.
5. The daily audit's AI review reads the reader prose (never the TTS spellings), lists the digest's publishers and item titles as real names, defines REPETITIVE as restatement and INCOHERENT as referent-less, and reads 24,000 characters (17 of a week's 113 scripts had been scored on a 12,000-character excerpt).
6. Nerra Daily posts say "By Mira" and carry the AI-host provenance (`engine.blog` read a show YAML Nerra Daily does not have and fell back to "Patrick" on all 74 posts).
7. The Tesla digest prompt's bracketed sign-off placeholder (reproduced verbatim in seven digests since July and on the blog) is described by shape; the sanitizer scrubs a bracketed instruction line; the seven digests are cleaned.
8. Top World's intake line names the desks it read ("also draws on the Omni View North America desk") instead of "1 of the 5" — four of the five are members-only by design; the registry no longer promises five desks "which publish earlier each morning".
9. `AIS` is spelled letter by letter (Offshore North aired "A I's").

**Audience and measurement**
10. `scripts/fetch_buttondown_stats.fetch_recent_emails` reads the committed send records first and follows the `/emails` list through `next`, newest-first, inside the window — the night after the first Nerra Daily send it had reported no sends.
11. GA4 `engagedSessions` is fetched and totalled (null, never 0, when absent) and Mission Control prints engaged sessions and their share beside raw sessions.
12. The digest expansion retry is a metric (`digest_expansion_fired`, `_attempts`, `_words_before`, `_words_after`, `_floor`).
13. Nerra Voices is a section and a follow in the one email (its exclusion called it "the interview room with no feed"; it has four episodes), in the Python map and the Worker's `EMAIL_SHOW_TAGS` together.

**Audio** ⚠️ AUDIO
14. Unintended Consequences, Vancouver and Collingwood — the shows with no music file — master to the published −16 LUFS through `engine.audio.master_voice_track`; they had shipped at −25 for 208 episodes and stepped 9.7 LU inside Nerra Daily. Every edition segment is levelled in `segment_trim_cmd`.
15. `_music_fadeout_cmd` trims the opening bed at the INPUT (`-ss`/`-t` before `-i`): the 30 s bed under the opening had been 12 s of music and 18 s of digital silence on every music show since Feb 2026.
16. Fades to silence use `FADE_CURVE = "qsin"` (`log` holds within 2 dB for 97% of a fade); the outro's fade-in keeps `log` on purpose.
17. The voice branch of `_final_mix_cmd` is stereo before `amix` — every shipped music show had been dual-mono.
18. Nerra Daily's promo cut lands before the platform ask (ten rating asks a day in Ep074) and the handoff-variety revision runs on REALIGNED handoffs (and realigns the revision).
19. SpaceX says "closed Friday at" before Monday's 09:30 open.

**Site and YouTube**
20. The front page's lead picture is the story's own scene: stemmed matching, one unique shared word suffices, and no scene (the show's cover) when the episode's prompts are known and none depicts the headline — never `candidates[0]`. The Nov 2 lead (coral reef under a protein-engineering headline) replays to the robotic-pipetting lab scene.
21. `tesla.html`, `spacex.html` and the SpaceX dashboard ask the network's own markets route instead of Yahoo through two free CORS proxies.
22. A compact cookie bar: heading and text in one two-line block, equal-weight actions in one row (147 px on a phone before).
23. A dub channel with no destination of its own lands on its language's front page (`ru/index.html`, `fr/index.html`) instead of the English show page (every FF and MIT dub Short; every French Tesla and SpaceX Short).
24. YouTube descriptions label imagery by source ("Imagery:" for Grok; "Photos via Pexels:" only when a Pexels line exists) and say each credit once.
25. The explore page no longer nests a second `<main>`; `tracking.js` loses the Buttondown embed tracker for a form gone since August.
26. A correction's amended headline and a translated feed title are clipped through `engine.titles`.

**Efficiency**
27. The Voices Worker's unconditional fire-tick catch-all is hourly (48 of the day's 83 fire-tick runs were the :00/:30 ticks; the schedule gate is fail-open). Operator: `wrangler deploy` in `workers/voices`.

**Newsletter**
28. The Nerra Daily email's archive copy carries the news (`not subscriber or` / `subscriber and` conditions; the Nov 2 archive had carried the hero, an empty heading and the footer); the "Also" heading only over lines; the subject drops the podcast app's "<Weekday> edition — " prefix; the preheader is two more stories; release notes are judged at the send; Sunday lists show 3; the signup button says when the email arrives.

## 4. The ranked plan

_(Filled from the synthesis: SCORECARD.md, the proposals and the skeptics' verdicts.)_

## 5. Operator items

_(Filled with the review's operator-only steps.)_

## 6. Open questions

_(Filled from the readers' open questions that the operator can answer and the readers could not.)_
