# Nerra Daily — quality review, 2026-09-03

Second pass on the combined daily edition, fourteen editions in
(Ep1 2026-08-21 → Ep14 2026-09-03). Operator-directed ("review the show
in deep detail and determine improvements to make the show, podcast and
blog significantly better on a daily basis"). Nerra Daily is a virtual
show, so `review_snapshot.py` cannot run on it; the ears for this pass
were the 14 committed rundowns (Mira's actual spoken words, committed
since the Aug 25 pass), the 9 committed `metrics_ep*.json` records, all
210 lineup transcripts from Aug 15 onward re-run through the shipped
promo-cut detector, the feed, the blog posts, the OP3 record, and the
git timeline of the shows the edition missed.

## Verdict up front

The splice is sound and the Aug 25 fixes all landed (scored below). What
this pass found is one **P0 listener-facing cut error** the metrics file
made visible for the first time, a **three-way tic convergence** in
Mira's only original words that the first rotation memory could not
see, and a **growth-surface gap**: every edition is titled with SpaceX
Daily's headline, so the all-network product reads as a SpaceX show in
every directory listing, and the show notes for a ~2 h, 13-segment
episode gave the listener no way to jump to a show.

## Scoring the 2026-08-25 predictions

| Prediction | Verdict | Evidence |
|---|---|---|
| Distinct blog `<title>` per post, no byline titles | **hit** | Eps 6–14 all titled `<Weekday> edition — <hook> — EpN \| Nerra Daily`; zero byline titles. |
| No two consecutive editions share opening words (10 eps) | **partial** | Literally true — the first word is now the date, which differs daily. But 5 of the 9 post-fix intros are the SAME sentence: "<date> opens Nerra Daily with me, Mira" (Eps 8, 9, 10, 12, 13, 14 variants). The memory compared raw words; the date defeated it. |
| 0 field-note topic repeats in 10 notes | **hit** | 13 notes, 13 distinct subjects (shingles vaccine, sperm whales, snake embryos, bat immunity, Spirulina B12, shoe sizing, PAH chemistry…). |
| Successor tic after the opener de-seed | **hit (found)** | Sign-off: "Across these segments / the reports…" 7/9 post-fix (9/14 overall), "thread" in 7/14, "I will be back tomorrow" 11/14. Field note closer: "It is the kind / sort of X that **quietly** Y" — "quietly" in 10 of 13 notes. |
| `nerra_daily` present in `api/op3_stats.json` | **hit** | Entry exists (show_uuid resolved); 21 downloads/30d as of 2026-09-01, all in the last week — the feed is still unsubmitted to Apple/Spotify. |
| `missing_expected` measured | **measured** | 4 of 9 metric'd editions incomplete. Classified below. |

## P0 — shipped

### 1. The DP Pod's Dispatch and sign-off were cut out of Ep10

`metrics_ep010.json` recorded DP Pod Ep52 with `cut_kind:
network_mention` — the only non-`promo` cut in 92 metric'd segments.
Re-running the detector on the committed transcript
(`digests/dp_pod/DP_Pod_Ep052_20260830_transcript.json`) shows the cut
at 692.5 s of 761.7 s: it removed **69 s** — the Dispatch invitation
("reply to the daily email or hit the dispatch button…"), Patrick's
own lever for the week, "That's it for today, positive vibes, positive
science…", both hosts' names and the "Do something about it" sign-off.
The edition shipped that way on 2026-08-30.

Two causes, both fixed in `engine/daily_edition.py`:

- **Whisper pluralises the frame.** The network promo says "our sister
  show SpaceX Daily is worth a spot in your feed"; Whisper committed it
  as "our sister **shows** spacex daily" (DP Pod Ep52, First Principles
  Ep75) and "our **sisters show** space x daily" (DP Pod Ep39). The frame
  regex required the singular, so the primary matcher missed and the cut
  fell to the weak brand-mention fallback. Now `sisters?\s+shows?`.
- **The fallback trusted any brand mention in the last 150 s.** The DP
  Pod's Dispatch segment says "the show page at nerranetwork.com" every
  day — body content, ~70 s from the end. `WEAK_EVIDENCE_MAX_TAIL_SECONDS
  = 60` now bounds a weak-evidence cut (the real outro block measures
  17–45 s on all 207 frame-matched cuts, median 36.8 s, p90 45.4 s); a
  mention further up is treated as body and the detector drops to the
  disclosure-only trim.

After the fix: all 210 lineup transcripts since Aug 15 trim on frame
evidence (`promo` 210/210, previously 207 + 3 weak); the three formerly
weak cuts now remove 32.6 / 33.3 / 40.1 s. Guards:
`TestPromoCutHardening` (the three real transcripts pinned, the Whisper
variants, the ceiling, and a network-wide sweep that FAILS on any new
weak-evidence cut so the next Whisper spelling is caught in CI, not on
air).

## P1 — shipped

### 2. Rotation memory v2 — the skeleton, the sign-off, the closer

The Aug 25 memory injected the first 8 words of recent intros. Mira's
first words are the date, so the model saw ten different lines and
wrote the same sentence ten times. Three data-side changes
(`recent_intro_openers` / `recent_signoff_openers` /
`recent_field_note_closers`):

- Intro openers are **date-normalized** before injection —
  `normalize_date_tokens` collapses weekday/month/day/year to `[date]`,
  so the block now reads `[date] opens Nerra Daily with me, Mira.` five
  times over and the prompt explains what `[date]` stands for.
- A new `{recent_signoffs}` block carries the opening words of the last
  10 sign-offs (all "Across these segments…" today).
- The find prompt's memory block now also lists the **closing sentence**
  of each recent field note — the sentence where the register is
  performed, and where 10/13 converged.

Prompt changes (⚠️ A/B-listen, landmine #17):
`shows/prompts/nerra_daily_links.txt` — sign-off may not open by
surveying the set or reach for a thread/through-line/pattern metaphor;
vary the feed reminder and the farewell; **at most one handoff in three
may begin with the show name** (83 of 83 handoffs in Eps 6–14 opened
"<Show> follows / turns next / steps back…" — the existing "do not open
every handoff by naming the show" was instruction-only and unmeasured;
`handoffs_show_name_led` is now a per-build metric).
`shows/prompts/nerra_daily_find.txt` — the register line no longer
seeds "quietly" (it appeared in BOTH prompts: "quietly witty", "quietly
delighted", and became the closer's adverb in 10 of 13 notes); the
closing sentence must not be a generalising verdict on the item.
De-seeded by shape, verbatim bans only, no quotable replacement.

Guards: `TestRotationMemoryV2`. No `GROK_API_KEY` in this session, so
the prompts were rendered against today's real lineup (`build_links_prompt`
/ `build_find_prompt`, 14.4 k chars) but not exercised — the operator
listens to the first post-merge edition.

## P2 — shipped

### 3. The edition is titled after SpaceX every day

`edition_hook` used the lead show's hook, and the lead is always SpaceX
Daily: "Thursday edition — FAA clearance for a wider Starship flight
corridor…", "Friday edition — Spectrum rules at the FCC…", 14 for 14.
In Apple/Spotify/OP3 listings — and in the blog `<title>`, the chapters
JSON title and the OG card — the network's whole-network product
presented as a SpaceX podcast.

The links call now also writes a **`title`**: one line naming the two
or three threads across the day, 20–72 chars, no date/weekday/"Nerra
Daily"/"edition" (the template carries those); `validate_edition_title`
rejects fragments, over-length lines and label-shaped text, and the
lead hook stays the fallback (`edition_title_source` metric records
which shipped). Written metadata only — nothing Mira speaks changed.
Guards: `TestEditionTitle`. Registered as experiment
`nerra-daily-edition-titles` (readout 2026-09-24).

### 4. Show notes: chapter timestamps + the field note

The item description was a bullet list of hooks. For a 1.5–1.85 h
episode with 11–13 segments that leaves a listener in any app that
does not render `podcast:chapters` with no way in. `feed_description`
now writes every chapter with its start time (`H:MM:SS` — the shape
Apple Podcasts, Overcast, Pocket Casts and Castro linkify to seek) and
quotes Mira's field note in full (it had aired and then reached no
written surface but the blog). The chapters dict is built once and
shared by the JSON file and the notes, so they cannot disagree.
`podcast:person role="host"` now credits Mira on the channel (the
funding tag was there, the host was not — Aug 25 deferred item).
Guards: `TestShowNotes`.

### 5. Stale show-page copy

`network_meta.yaml` `description_long` still described the pre-Ep1
order ("flagships first: Tesla Shorts Time, Models & Agents, SpaceX
Daily and Modern Investing…"). Rewritten to the operator's fixed
rundown and to mention the field note. Guard: `TestRegistryCopy`.

## Measured, not fixed — operator items

### Which shows the edition misses, and why

Every `missing_expected` entry since metrics began, classified against
the show's own summaries timestamp:

| Edition | Built (UTC) | Missing | What actually happened |
|---|---|---|---|
| Ep6 Wed 08-26 | 13:22 | UC, FPD | neither published that day (skipped) |
| Ep7 Thu 08-27 | 15:29 | SpaceX, Tesla, OV, UC, FPD | GitHub-cron outage day: SpaceX 15:30, OV 15:33, FPD 16:27 **published minutes after the force-build**; Tesla + UC never published |
| Ep10 Sun 08-30 | 12:41 | UC | did not publish (skipped) |
| Ep14 Thu 09-03 | 12:09 | UC | claims gate blocked UC at 07:25 (`Gate-block skip state` commit); the retry published Ep105 at **13:26**, 77 min after the edition shipped |

So of the misses, three are "published after the build" (Ep7's three,
Ep14's UC) and the rest are genuine skips the edition handled correctly.
The Aug 25 ledger said to escalate the force hour only if Monday
weeklies missed twice more — they did not (Offshore North 07:34 on
08-31). The new shape is **UC's claims-gate retry**: a gate-blocked
narrative episode reruns via the daily-audit path after 12:00 UTC, so
it can never make the edition on a blocked day. Decision needed — one of:
(a) accept (UC is absent from the edition on gate-blocked days, ~1 in
10); (b) move UC's retry earlier than the 12:00 force hour; (c) add a
narrow "late-segment addendum" (a second, clearly-labelled short
episode) — I recommend (a) or (b); (c) doubles the feed's item count
for a corner case. Not a code change here.

### Intro length

Post-fix intros run 75–131 words against the prompt's 110–170 ask (7 of
9 under the floor). Deliberately **not** attacked: shorter is better for
a cold open, podcast-side length levers are banned network-wide, and
the intro chapter already lands the first segment inside 35 s.

### Still deferred (carried from Aug 25)

- Apple/Spotify submission (`apple_podcasts_url` / `spotify_url` still
  null) — 21 downloads/30d with zero directory presence is the
  distribution gap the launch experiment cannot read through.
- Content lake: `backfill_content_lake.import_virtual_shows` now exists
  (shipped elsewhere since Aug 25) — no longer deferred.

## What did NOT change

- No audio pipeline / TTS / voice settings. Mira stays on `ara`.
- No R2 paths, no enclosure URLs, no chapters-JSON schema.
- The force hour, the lineup order, the min-segment floor.
- No new podcast-side length lever (the intro-length shortfall is
  recorded, not chased).
