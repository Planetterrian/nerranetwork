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

**Added after the propose phase was briefed**
29. The consent bar is `role="region"`, never a modal dialog (template and `consent.js`).
30. `engine/video_feed.py` item titles clip through `engine.titles`.
31. `engine/script_audit.py` measures the attribution tail (`script_attribution_tail_pct`: sentences ending ", X reported." / ", according to X.") and the short-sentence share (`script_short_sentence_pct`, nine words or fewer) as read-only baselines, with two columns in the review snapshot. Calibrated on the committed scripts: Tesla 0.0% → 10.4% tail between Oct 1–10 and Oct 27–Nov 2, SpaceX 0.6 → 5.2, FF 0 → 6.2, the grok-4.7 cohort under 3% both windows; the short-sentence share FELL on every flagship (Tesla 32.9 → 17.7). The prompt-side shape rewrite waits on this baseline.
32. Mira's spoken self-description has one owner, `engine.brand.MIRA_SPOKEN_CLAIM` ("on this show an AI asks the questions, and the guest decides whether the conversation is published at all"), rendered into the live brief, the narration prompt and the editor's brief through `{{mira_spoken_claim}}`. Since Sep 14 all three had said "the first podcast researched, hosted and produced end to end by an AI" — the broad shape `engine.brand` refused on Sep 20 — on every cold open and live to every guest. ⚠️ The live brief changed one clause: candidate rehearsal PASS plus one listen before a booked room. Past narration files keep what aired.
33. The daily audit's AI review receives the episode's verified claims from the committed ledger ("do not dispute these from memory") and splits FACTUAL_ERRORS (the episode contradicts itself or a source it cites) from FACTUAL_DOUBT (contradicts the reviewer's own memory only), which is recorded as a note and never a finding.

## 4. The ranked plan

How it was built: eight proposers (one per goal area) wrote 78 proposals from the readers' reports and the scorecard; eight skeptics judged every one on three lenses (real and significant, safe under the rules that bind, feasible as written in this codebase), re-computing at least one number per proposal from the committed data; 73 stand with amendments and 5 were refuted. A managing editor folded the amendments in, merged duplicates across areas, and ranked by impact on the eight goals times confidence over effort. Groups A and B are the 21 items one engineering session ships; C is the operator's list (section 5 carries it); D is right but not now, each with the trigger that promotes it.

**A. Ship now (code, config, copy; a guard test; no spoken-audio change)**
1. `funnel-denominator`: the site's headline number is wrong by three to four times because an untagged Google Ads campaign lands on one page and bounces (492 of 999 sessions). Ads tagged through `engine.funnel` (a new `ad` kind), landing anomalies excluded and printed beside the raw total, email rows in the funnel.
2. `youtube-measurement`: half the English channel is RSS-ingested podcast copies the repo cannot see (4,822 channel videos against 2,434 indexed), and retention curves exist for five longs a night. A nightly channel-versus-index reconciliation, a curve for every long, hold-at-5% by age, RU/FR reach keys.
3. `review-loop-closes`: 74 register entries past readout, 756 unscored ledger predictions, the network ledger never scored, four grok-4.6 script arms over the playbook's latency gate that nobody read. A nightly readout with CI on stale entries, a network slot the rotation reaches, labels on closed review PRs, the latency gate read nightly.
4. `youtube-brand-surfaces`: the outro card on every long-form and the Shorts end-card strip render from data instead of an Aug 9 screenshot that still reads "0 ADS"; the capture workflow fails loudly; channel copy for EN/RU/FR written from `engine.brand`.
5. `voices-spend-and-metrics`: the operator's priority show records $0.00 while rehearsals burned ~870 Voice Agent minutes; a credit file per room, Voice Agent minutes priced, survey, grades, yield and cost per room in a file and a card; the xAI balance read by the Worker tick.
6. `email-redesign`: a sourced deck under every card (deterministic, no model call), the first phone screen carries news, "Also on Nerra today" as a sectioned run of short headlines, every headline whole, the size guard knows Buttondown's wrapper.
7. `email-measurement`: a nightly subscriber and tag series, open, click and recipient counts, a Mission Control tile that is never hidden, a register metric.
8. `audit-instrument`: every YES in the daily audit quotes a sentence found in the text, the score persists per show beside the audience headline, a SpaceX ledger row, and every show's promised length is computed from its last 14 episodes.
9. `interview-publish-parity`: the interview feeds gain VTT transcripts, person and funding tags, titles fitted whole, a real About; the waveform upload gets a title bundle, thumbnail and chapters; `video_kind` recorded.
10. `repo-hygiene`: "You might also like" from the post's own week (so old posts stop being rewritten daily: 4,698 pages a day), an incremental render on every show run, the 39 KB inline blog stylesheet becomes one shared file, a 2 MB blob guard under `digests/`.
11. `long-form-policy-instrument`: the long-form policy reads the Shorts tier's ruler (fixed-age reach, long-versus-hook ratio, pooled subscribers per 1,000); RU/FR entries carry their hook-Short reach; the overlay stays off until the operator decides (C17).
12. `listen-before-slate`: a `rehearse` input on the show workflow that produces the MP3 as an artifact and commits nothing; the audio probe renders a real minute of a committed script through the real builders; a playbook section for audio changes (one show first, listen, slate).
13. `findability`: Organization `sameAs` and logo, NewsArticle schema on news posts, `dateModified`, titles at the 60-character lead, a 48-hour news sitemap.
14. `ru-fr-audience-surfaces`: the RU pilot's dead Sunday letter retired and the landers ask for the YouTube subscribe; the language fronts ranked by their own channel's views and led from their own subjects, never a Canadian tax story for an audience 90% in France.

**B. Ship now, audio-gated (⚠️ AUDIO, landmine #17: A/B-listen the first episode)**
1. `env-intel-sourced-deep-dive`: the Practitioner Deep Dive is built from a fetched guidance document; the prompt's quotable specimen ("The mistake I see most often…", aired verbatim in 5 of 6 episodes) goes; invented first-person experience is filtered in code; Reddit leaves the source list.
2. `flagship-prompts-by-shape`: the shared sentence paragraph rewritten by shape (the outlet inside the sentence, never a trailing tag), the "1 to 2 sentences per line" rule and the quotable "according to Teslarati" out, the "at least two sentences" item floors out, X-post items get a shape and SpaceX's Community Buzz loses its quota; scored on the attribution-tail instrument shipped today.
3. `digest-fact-floor`: the digest's expansion floor counts facts, not words, on Planetterrian first (with the operator's nod, C15), since it partly reverses the Oct 14 length direction.
4. `digest-lints-pass`: a `deep_dive_distinct` lint (measure-only for a week, then regenerating) and a hook-figure-sourced lint for the narrative shows, both riding the existing one-shot regeneration.
5. `voice-dynamics-glue`: the voice chain's 4:1 compressor becomes a gentle 2:1 glue on two shows first (loudness range 2.8 → about 4 LU, NPR 4.9–5.2), behind a YAML key like `voice_declick`.
6. `remaster-voice-only-back-catalogue`: a dry-run-default tool and workflow that pulls each of the 208 −25 LUFS episodes back, applies gain plus a limiter (never a two-pass loudnorm, whose linear mode falls back to dynamic on these peaks), uploads to the same key and keeps the feed item.
7. `mira-beat-before-the-question`: the beat ("after a real answer, one sentence of what it changes, then the question") as the critical rule in Mira's brief, measured as `bare_question_rate`; candidate rehearsal plus a listen before a booked room.

**D. Deferred, with the trigger that promotes each:** one-ask closing behind a flag (the operator's yes on C14); the close's steady bar and level (after B5 is listened to); room tone in every pad; Mira's one chain, pace trial and clicks metric; source tiers (the operator's nod on narrowing the Sep 24 X-primary exemption); the narrative shows' restock dedupe and specimen removal; the Russian shows' data-side gates (a named Russian listener); Personal's repositioning (Stripe read first); the chronicle moved to the written close; first-audio latency per room turn; a guest-hour panel on the gate-1 page; stage-2 interview video; outbound guest sourcing (C20d); Nerra Daily po-russki and a Russian email (Nov 15 readouts, a listen to Mira in Russian); the RU dub voice by ear; a geography series before any German trial; X read-back or closing both X experiments; French chrome (a native reader); the distribution coverage row (after C11–13); a welcome email (after C25).

**Refuted (dropped):** a sonic identity sting under the identity line (audio-7; re-filed as an operator asset item); a weekly release slot for the interview shows (voices-5; a next-morning option would stand); the adaptive end-of-turn wait as written (voices-6; measure first-audio latency first); the guest-experience column (voices-10; a panel under a new field name would stand); a hook-only rewrite instead of the digest regeneration (efficiency-10; it would leave the combined stash stale).

The full ranking with each item's merges, confidence and one-line reasoning, and every skeptic's verdict, are the session's scratch record (`RANKING.md`, `verdicts.json`); the work items as implemented are listed in the pull request.

## 5. Operator items

Deploys and settings:
- `wrangler deploy` in `workers/voices` (hourly fire-tick catch-all; the gate-2 copy on the review page and email).
- `wrangler deploy` in `workers/gallery` (Nerra Voices in `EMAIL_SHOW_TAGS`).
- The 571 MB of FLAC stays in git HISTORY; only the landmine-#1 filter-repo playbook (`docs/workflow_review_2026_06_10.md`) removes it.
- Rotate `PERSONAL_ADMIN_TOKEN` (it was pasted into a chat session on Nov 2).

Listens (⚠️ AUDIO changes shipped in this branch — A/B-listen one each before trusting the slate):
- Unintended Consequences, Vancouver or Collingwood: the first episode mastered to −16 LUFS (was −25).
- Tesla or any music show: the opening bed now lasts its 30 s and the outro fades to silence; on headphones, the stereo image under the voice.
- Nerra Daily: the next edition (handoffs realigned before revision; the promo cut before the platform ask; every segment levelled).
- SpaceX on a Monday: "closed Friday at".

YouTube Studio and the channels:
- Upload the Oct 18 banner on @NerraNetwork (the live one reads "100% AD-FREE · EN · FR · RU · ZH"); write RU and FR channel descriptions that lead with Starship, astronomy and Tesla.
- Every EN long-form exists twice on the channel: the render and an RSS-ingested copy YouTube made from the podcast feed (40 of the 80 newest videos). Remove the RSS-ingested podcast where a render exists and flag the API playlist as the podcast (landmine #15's route). A Studio read confirms it in one click.
- Actions "Capture Site Screenshots" (the outro card on every long-form renders the Aug 9 homepage with "0 ADS").
- An end-screen template on the flagship long-forms for a week (END_SCREEN delivered 1 view in 90 days).

Directories and listings (`docs/podcast_directories.md` gives the order; Podcast Index first because OP3 resolves feeds through it):
- Fifteen feeds are not in Podcast Index (the cohort, Offshore North, Nerra Daily); thirteen Apple rows have read PENDING since Oct 3; Amazon 0 live; Pocket Casts 0 of 32.
- Nerra Daily: Apple and Spotify ids still null ten weeks after the Sep 3 ledger asked.
- Nerra Voices, Offshore North, Omni View North America: unindexed on OP3.
- The three French-only feeds (env_intel, first_principles, models_agents): submit to Podcast Index or switch the FR track off (about $19 a month unmeasured since Sep 4).

Product decisions the review asks for:
- The closing block (12–15% of every episode, four to seven asks on MIT and FPD): one ask per episode on the rotation that already picks the surface, about 30 s. Read the `platform-ask-2026-10-01` readout (due Nov 1) first.
- The four dark desks (72 skipped episodes since Oct 16): `access.mode: public_weekly` (one free weekday each, daily for members, about $0.29 an episode) or retire them honestly; Top World's copy and the lineup follow either way.
- The Planetterrian and FF Spotlight and Omni View's Understanding the Issue are second passes BY DESIGN (their prompts require it): a second story built from a fetched page, or keep the pass and say so.
- `/personal-interest.html` writes a Buttondown tag (`personal-interest`, 4 people) that nothing sends to while the page promises "occasional Personal tips by email": include them in Nerra Daily, send them something, or change the copy. Read the Google Ads account for the Oct 15 and Oct 22–24 spend days: 492 landing sessions, 98.8% bounce, 2 submits.
- Nerra Personal: freeze feature work until Stripe is read (`mrr_usd`, trials and churn are null) and the free list passes a floor; two paying members after eight passes.
- The RU SpaceX pilot: 0 captures in three months and a Sunday letter whose tag (`ru-spacex`) no subscriber carries. Close `spacex-ru` and `tesla-ru` as MISS, retire `ru-spacex-weekly.yml`, give @NerraRU the subscribe pill.
- Age of AI: run the camera test room (Patrick on camera, Actions "Cut the video version of an interview" with `preview`), watch it, then `local_video: true`; stop uploading the waveform meanwhile (27 views on 3 videos, 1.5% watched). The guest mix: 15 of 18 guests are founders pitching, against a premise of teachers, artists, tradespeople and skeptics.
- Env Intel's Practitioner Deep Dive invents consulting experience by instruction (`env_intel_digest.txt:171`); Models & Agents for Beginners sources a death to "SSB Crack News" and ships 3 of 51 fetched articles; SpaceX has the lowest daily audit score of any daily show for three months and 30% of the network's downloads. Each needs a show pass of its own.
- Финансы Просто and Привет, Русский!: invest (a Russian listener, a vocabulary gate, an arithmetic lint, the spoken-text gate out of shadow) or state plainly that they are five-to-seven-minute shows and align every surface. FP Ep090's mortgage arithmetic was wrong by two to three times and the show has no `corrections.yaml`.
- The grok-4.6 script arms fail the model-upgrade playbook's latency gate on committed data (script p95 SpaceX 487 s, Tesla 558 s, M&A 448 s against 300 s) while winning on quality. Both numbers are now on the record; the decision is the operator's.

Reads only a person can do:
- What caused the Sep 28 download step (eleven shows +37% to +2,200% in one week, held five weeks) — the one growth event of the six months with no cause in any document.
- The Studio read on the Sep 15 and Oct 19 Shorts-feed steps (restrictions, reused-content notices) asked for on Oct 3 and Oct 24 and recorded nowhere.
- Is a welcome email configured at the Buttondown account level? The signup button now says when the email arrives instead of "Check your email".
- Verify the email's archive copy on the next real send (Actions "Nerra Daily email", mode `draft`): the Django "no subscriber" behaviour is inferred from the Nov 2 archive, not documented.
- Listen: a Patrick minute against an NPR minute at equal loudness (the chain's LRA 1.6–3.0 against NPR's 4.9–5.2 is the compressor; a listen decides whether it is a defect); the Olya voice reading the English half of a Russian lesson; the English-trained clone reading Russian and French to a native ear.

## 6. Open questions

Questions the readers could not settle from the committed record and the operator can:

1. **Who is the network for?** SpaceX and Tesla are 48% of downloads, the EN YouTube audience is 99.7% male and 0.3% under 25, and there is no culture, sport or lifestyle beat. The alternative to traditional news networks the brief describes is built for one audience today. Is that the plan, or is the regional-desk and language work the direction?
2. **Is the explainer minute inside the trust promise?** Omni View's Understanding the Issue, Tesla's First Principles essay and SpaceX's deep dive are written from model knowledge by design and the ledger holds no claim from them; the provenance line does not say so. On Nov 2 one was wrong.
3. **How long is Nerra Daily?** 141 minutes a day, weekly downloads 139 → 85 while the network grew 10%, completion unmeasured (Spotify PENDING since Oct 3, Apple Reporter null). A 45-to-60-minute core edition with the full splice as a second feed is the readers' proposal; the instrument (Apple Connect consumption) comes first.
4. **Does the Russian audience get its own voice?** Nothing in Russian or French is the network's own: the RU channel is 94% male searching rocket, Starship and telescope; the native Russian shows are a Canadian women's finance show and a language lesson. A Nerra Daily po-russki over the four RU dubs costs about $5 a month.
5. **Light theme?** Every reference product Patrick named defaults to light for reading; the site is dark-only, which reads as an app and makes the kits unprintable. A brand decision.
6. **What did the two paying members choose, and why?** Both picked nearly the whole network. The PII rules keep the answer out of the repo on purpose; only the operator's Stripe and KV reads can say.
7. **Why are Korea 11% and Germany 10% of EN YouTube views?** Unread, and relevant to which language comes next.
