# SpaceX Daily — quality review (2026-06-19)

Third scheduled review, one day after the 2026-06-18 pass. One new episode
has shipped (Ep8, 2026-06-19, a normal daily), which is enough to score the
prior predictions and surfaces a new P0 spoken-audio garble.

Evidence: `scripts/review_snapshot.py spacex`, `shows/spacex.yaml`, the four
prompts, `shows/hooks/spacex.py`, `assets/pronunciation.py`, Ep8's digest
`.md` + `_tts.txt` + Whisper transcript + `chapters_ep008.json`, the prior
two review docs, the ledger, and `tests/test_spacex_show.py` /
`tests/test_pronunciation.py`. OP3 holds at **31 downloads / 7d**.

## Scoring the 2026-06-18 predictions

- **Closing chapter on dailies + next weekly recap — PARTIAL (daily HIT;
  recap not yet observed).** Every daily Ep4–Ep8 has both a `Market Watch`
  and a `Closing` chapter (`chapters_ep008.json` ends on `Closing`,
  endTime 506.6). The next weekly recap is Sunday 2026-06-21 — not yet
  shipped — so the recap half of the prediction stays pending and is carried
  forward.
- **Engineering Deep Dive still <250w unless the floor ships — HIT.** The
  deep-dive floor was not shipped (still deferred), and Ep8's deep dive runs
  **139 words** (lines 17–27 of the `_tts.txt`). This re-confirms the
  digest-ceiling thesis: Ep8 totals 988 words, under the 1300 floor.

## P0 — listener-facing bug shipping today

### Launch-time strings with seconds ship as spoken garble — SHIPPED FIX
Ep8's `_tts.txt` line 5 reads
`"…at Vandenberg Space Force Base at one fifty A M:45 a.m. Pacific Daylight
Time…"` and line 9 `"Liftoff occurred at 0850:45 U T C…"`. The **Whisper
transcript confirms this shipped in the audio**: `"…at 1.50am 45am Pacific
Daylight Time…"` and `"Lift off occurred at 0.850 45 UTC…"` — both garbled.

The digest was clean: `"…at 1:50:45 a.m. PDT…"` / `"Liftoff occurred at
0850:45 UTC…"` (`SpaceX_Daily_Ep008_20260619.md:6`). The bug is in the shared
TTS normalizer `assets/pronunciation.py:replace_times`. Its matcher was
`(\d{1,2}):(\d{2})\s*(AM|PM|…)?` — seconds-blind:

- For `1:50:45 a.m.` it matched only `1:50`. With no AM/PM directly after
  `:50` (a colon follows), it fell into the 24-hour branch → `"one fifty A
  M"`, leaving `:45 a.m.` stranded → `"one fifty A M:45 a.m."`.
- For `0850:45 UTC` the matcher can't parse `0850` as `HH:MM` (no colon), so
  it tried the inner `50:45` → hour 50 > 12 → bailed out unchanged, shipping
  `"0850:45"` as raw digits.

This is the exact spoken-garble class the Whisper transcripts keep catching
(cf. the `tf`→`T F` thrust-unit garble fixed in the 2026-06-13 pass). It is
**latent network-wide** but surfaces on SpaceX because spaceflight reporting
(spaceflightnow, NASASpaceflight) routinely gives launch T-0 to the second
in both local and UTC.

**Fix** (`assets/pronunciation.py:replace_times`):
1. Seconds-tolerant main pattern `(\d{1,2}):(\d{2})(?::\d{2})?…` — seconds are
   **dropped** (no host reads launch seconds aloud); `1:50:45 a.m.` →
   `"one fifty A M"`.
2. A narrow compact-UTC handler `\b(\d{2})(\d{2})(?::\d{2})?\s+(UTC|GMT)\b`
   that runs *before* the HH:MM matcher and renders 24-hour spoken form with
   the zone left literal for `replace_timezones`; `0850:45 UTC` →
   `"oh eight fifty U T C"`.
3. Tightened the trailing whitespace so an absent AM/PM no longer eats the
   space and glues the next word (`14:30:00 UTC` → `"two thirty P M U T C"`,
   not `"P MUTC"`) — a pre-existing latent defect exposed by the seconds fix.

Verified against the exact Ep8 strings and all existing time cases (`03:08
AM`, `2:30 PM`, `00:00`, `2:59 a.m.` unchanged); `15000 satellites` and
`In 2026` are correctly **not** treated as times. Deterministic
number-normalization correctness fix (same accepted class as `replace_dates`
/ `replace_currency` / the `tf` unit expansion), not a phonetic respelling —
but it changes spoken output, so it is listed under **A/B-listen** out of
caution. Drift guards: `tests/test_pronunciation.py::TestReplaceTimes` (6 new)
+ `tests/test_spacex_show.py::TestLaunchTimePronunciation` (2, at the real
shipped strings).

## P1 — quality ceiling (carried forward, deferred)

### Engineering Deep Dive under-length → chronic under-length
Unchanged from the 2026-06-18 pass and re-confirmed by Ep8 (deep dive 139w;
episode 988w < 1300 floor). The lever — an explicit ~280–340w deep-dive floor
in the digest + podcast prompts — stays **deferred pending the operator's
network four-show length A/B** (the reason `CLAUDE.md` records; it still
holds). This remains the single highest-value lever the moment the A/B
settles.

### SPCX price number spoken twice every episode
Still 7/7→8/8 (Ep8: `"SPCX is at one hundred eighty-five dollars, minus five
point two percent"` in Market Watch **and** `"S P C X is trading at one
hundred eighty-five dollars, down five point two percent"` in the closing).
The 2026-06-18 reorder cleared the chapter blocker, so a future pass can make
the Market Watch note qualitative (direction + why, single precise quote in
the closing). Audio-affecting → deferred to its own A/B pass; observe a few
more episodes first.

## P2 / monitor

- **Tomorrow-teaser frame "watch for the [first/next] <test>"** is now **6/8**
  (Ep1, 2, 4, 6, 7, 8; refueling/hot-fire/static-fire/post-flight-inspection).
  Content varies but the opener is hardening into a template across two
  reviews. Not shipped (audio-affecting, low severity). If it becomes a dead
  rotation, rotate the teaser opener in the podcast prompt (low risk — no
  chapter dependency keys off it).

## Resolved / not findings (verified)

- The 2026-06-18 Closing/Market-Watch reorder is in place
  (`shows/spacex.yaml:204–230`) and Ep4–Ep8 dailies all keep both chapters.
- AI & Compute lumping and hook-jargon (earlier deferrals) did **not** recur
  in Ep8.
- `"i'm patrick and vancouver"` remains a Whisper mishear of `"…in
  Vancouver"` — no bug.

## Hard guardrails honored
No R2/RSS-enclosure changes, no MP3s, no `min_articles_skip` default change,
no TTS-coupled-field flips, no voice/provider changes, no phonetic
respellings, no posting/sending/uploading/paid APIs. The shipped fix is a
deterministic time-normalization correctness change in the shared
pronunciation pipeline.

## Tests
`tests/test_pronunciation.py`, `tests/test_spacex_show.py`,
`tests/test_network_quality_pass.py`, `tests/test_chapters.py`,
`tests/test_prompt_fidelity.py`, `tests/test_episode_validity.py`,
`tests/test_generator.py`, `tests/test_utils.py` — all pass (392 + 87).
