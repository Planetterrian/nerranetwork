# Slate review: Thursday 2026-10-08

The operator asked for three things: a review of every show and run from the last 24 hours, how Nerra Daily ran on its first 8am Pacific day, and the failing Voices tests on main. Register entry: `slate-2026-10-08`. Guards: `tests/test_transcripts_pyav_2026_10_08.py` and `tests/test_youtube_session_restart_2026_10_08.py`.

## Verdict

- **All 21 episodes published, with no skips.** The weekday roster was complete, and Nerra Daily carried every one of them.
- **No episode had a transcript.** That is the P0, and it was self-inflicted: a dependency bump re-admitted the PyAV release that broke transcription on Sep 30. The bump was Dependabot #1365, merged in the Oct 7 "merge all open PRs" batch.
- **Three flagship long-form videos were lost** to an expired YouTube upload session (HTTP 410).
- **Five workflow runs died** while installing ffmpeg.

All three defects are fixed in this PR. What the missing transcripts cost is listed below.

## 1. P0: no transcripts on any episode (0 of 21)

**Cause.** Dependabot opened #1365, "update av requirement from <19,>=11 to >=19.0.1,<20", on Oct 6. The line directly above that pin explains why the ceiling exists: PyAV 19 removed the `metadata_errors` keyword that faster-whisper 1.2.1 passes to `av.open`, and every episode of Sep 30 shipped without a transcript because of it. The Sep 30 guard (`test_pyav_is_pinned_below_19`) failed on the PR. #1365 was merged anyway, in a batch at 00:25 UTC on Oct 7 under the instruction to merge all open PRs, and main's `Run Tests` had been red for an unrelated reason since Oct 7. Every run on Oct 8 logged:

    transcription failed for SpaceX_Daily_Ep124_20261008: TypeError: open() got an unexpected keyword argument 'metadata_errors'

**What it cost on Oct 8:**

- **Spoken-text gate.** It recorded `no_transcript` on all 21 episodes, so the audio shipped unverified (landmine #25). The post-hoc audit in §4 checks it now.
- **Nerra Daily Ep049** shipped all 21 segments whole (`cut_kind: none` ×21). Every show's outro plug and AI disclosure stayed in, and the edition ran 180 minutes against 136–175 on the last five days. It is published; a `--force` rebuild refuses an already-published date, and re-cutting it would mean hand-editing a live feed. **Left as is.**
- **Shorts** went out with no burned-in captions and no fact cards (Tesla, SpaceX and FF all recorded `fact_cards_rendered: 0`). No long-form video got a caption track.
- **Feeds.** No VTT transcript tag in the RSS items and no `#transcript` section on the blog posts. The backfill in §4 restores both.

**Fix, three layers:**

1. **Whisper never decodes through PyAV now.** `engine.transcripts.load_whisper_audio` decodes with ffmpeg to 16 kHz mono and hands `transcribe` an array. Both call sites use it: `generate_transcript` and `engine/tts_validation.py`. The samples match faster-whisper's own decoder exactly; on SpaceX Ep124 the maximum absolute difference was 0.0, so timestamps do not move. Under a patched `av.open` that rejects the keyword, the way PyAV 19 does, the old path reproduces the runner error and the new one transcribes.
2. **The ceiling is restored** to `av>=11,<19`, and the comment names both outages.
3. **Dependabot ignores PyAV 19 and later** (`.github/dependabot.yml`), so the bump is not proposed again.

## 2. YouTube: three long-form videos lost to HTTP 410

**What happened.** Tesla Ep628, SpaceX Ep124 and Omni View Ep199 lost their long-form video to `HttpError 410 "Gone"` from the resumable upload endpoint. Four other long-form uploads on the same token succeeded that morning (FF, M&A, MAB, MIT), and the 410 appears on no other day in the last week. A 404 or 410 on a resumable upload means YouTube discarded the upload session, and Google's documented remedy is to start the upload again.

**Why the existing retry didn't help.** The tenacity retry around `_execute_resumable_upload` does not retry a 410. Even if it did, it would reuse the dead session URI.

**Fix.** `upload_video` restarts once with a new session on 404 or 410. A second expiry raises, and any other client error (400 and the like) is never restarted. The Shorts uploads were unaffected.

## 3. Runner setup: five runs died installing ffmpeg

**What happened.** Four multilingual runs (Tesla twice, M&A and FPD) and one Nerra Daily gate check exited with code 124 inside `.github/actions/setup-python`. About 10.5 minutes is two 300-second `apt-get install` timeouts: a stalled mirror connection.

**Why the timeouts didn't save the runs.** apt's own per-connection timeout is 120 s and it does not retry a stalled fetch, so one hung connection used the whole budget.

**Fix.** apt now runs with `Acquire::http(s)::Timeout=30` and `Acquire::Retries=4`. The ffmpeg source is unchanged: a different build changes the render, and the Ubuntu 26 runner migration on Oct 19 will change it anyway (see the operator list).

## 4. Transcript backfill and the post-hoc gate audit

Every Oct 8 episode was transcribed from its published MP3 with the pipeline's `base` model, written beside the digest under the pipeline's file names (`*_transcript.json`, `.txt`, `.vtt`), and run through `engine.spoken_text_gate.check_transcript_files` against the committed `_tts.txt`. Because `voice_intro_delay` is 0, the voice starts at t=0 in the published mix, so these timings match what the raw-track transcript would have recorded.

_Results are added with the backfilled transcripts in the next commit on this branch._

## 5. Nerra Daily on its first 8am Pacific day

| | |
|---|---|
| Built | 16:04–16:10 UTC (09:04–09:10 PDT) |
| Segments | 21 of 21 expected; nothing missing, nothing skipped |
| Handoffs | 20, none led by a show name; Mira's links and title written by the LLM; field note included |
| Length | 180 min, all segments untrimmed (§1) |

**Why it went out at 9:10, not 7:50.** First Principles' 08:31 UTC run lost its runner 53 minutes into the pipeline ("The hosted runner lost communication with the server"; its normal run is ~10 min). GitHub's fallback cron re-ran it, and it landed at 16:01 UTC (9:01 PT), one minute after the hold ended. Its `workflow_run` event built the edition with the full slate. That is the gate doing what it was built to do; without FPD's fault it would have built at the first gate check after 07:50 PT.

**The scheduler Worker is not deployed yet.** The edition was dispatched at 12:07 UTC (the old slot) and not at 07:50/09:01 PT. The GitHub fallback crons for the edition have historically fired 5–8 hours late (19:24–22:04 UTC for slots meant for the morning), so until `wrangler deploy` the release depends on show runs happening to trigger a gate check after 07:50 PT. It did today; nothing guarantees it.

## 6. The shows

| Show | Ep | Words / target | Digest overlap % | Coverage % | Claims verified | Notes |
|---|---|---|---|---|---|---|
| AI Chips | 17 | 1205/1300 | 2 | 72 | 11/13 | |
| Fascinating Frontiers | 216 | 1304/1700 | 68 | 93 | 8/10 | reads the digest |
| First Principles | 124 | 1285/1400 | 87 | 100 | 0/0 | runner lost on first run; reads the digest |
| MAG 7 | 16 | 1430/1100 | 8 | 83 | 20/20 | |
| Models & Agents | 197 | 1300/1500 | 33 | 78 | 12/12 | |
| M&A for Beginners | 190 | 1218/1200 | 17 | 73 | 5/6 | script on grok-4.6 |
| Modern Investing | 194 | 1284/1800 | 53 | 88 | 4/4 | disclaimers still precede the first story |
| Omni View | 199 | 1334/1400 | 48 | 82 | 8/8 | 4.6 script call dropped (`APIConnectionError`) → 4.3; long-form lost (410) |
| OV Africa & Middle East | 16 | 1025/1300 | 2 | 58 | 20/20 | |
| OV Asia Pacific | 16 | 1041/1300 | 9 | 70 | 14/14 | |
| OV Europe | 16 | 1096/1300 | 4 | 51 | 19/19 | |
| OV Latin America | 16 | 830/1300 | 15 | 89 | 13/14 | short |
| OV North America | 15 | 932/1300 | 13 | 72 | 14/15 | |
| OV Top World | 16 | 1344/1150 | 7 | 69 | 27/27 | |
| Peptides | 4 | 1133/1200 | 4 | 68 | 14/14 | |
| Planetterrian | 207 | 1084/1600 | 68 | 79 | 8/9 | cold open sells the smoke logger; body opens on the tortoise |
| Prediction Markets | 16 | 1543/1100 | 11 | 80 | 20/20 | |
| SpaceX | 124 | 1178/1300 | 64 | 93 | 3/4 | long-form lost (410); three sections read aloud |
| Tesla | 628 | 1092/1400 | 3 | 80 | 4/4 | long-form lost (410) |
| Unintended Consequences | 136 | 889/1300 | 71 | 88 | 0/2 | narrative ledger still verifies nothing |
| Vancouver | 16 | 1036/1200 | 8 | 89 | 14/14 | |

**What the table says, which has held all week.** The quality split in the network is the script model, not the show:

- **The grok-4.3 shows read the digest aloud:** FPD 87%, UC 71%, FF 68%, Planetterrian 68%, SpaceX 64%, MIT 53%.
- **The grok-4.6/4.7 scripts write:**
  - The cohort runs 2–15%.
  - MAB on grok-4.6 runs 17%.
  - Omni View ran 11% and 23% on its last two grok-4.6 days, and 48% today when the call fell back to 4.3.
- **The model is also why the claims gap exists:** the cohort records 13–27 claims an episode, the 4.3 flagships 3–12, and the narrative shows 0–2.

This is the next staged model trial (operator item 4), not a prompt problem. Prompt passes have not moved it since September.

## Main was red

The Voices tests named in the Oct 7 note pass once ffmpeg is installed: 355 passed and 1 skipped across `test_it_produces_itself.py`, `test_the_guests_own_recording_is_used.py` and `test_nerra_voices_pipeline.py`. `test.yml` installs ffmpeg and runs `pytest -x`, so main's red was the first failure the run reached. That was `test_pyav_is_pinned_below_19`, the guard #1365 broke. One Voices guard pinned the old `model.transcribe(str(audio_path), …)` string and was updated with the decoder change. The full-suite result is in the PR.

## Operator items, in order

See the PR description for step-by-step instructions.

1. Deploy the scheduler Worker.
2. Don't merge Dependabot PRs on a red `Run Tests`, and check pins with a comment above them.
3. Decide on the Ubuntu 26 runner migration before Oct 19.
4. Stage the grok-4.6 script trial on one flagship.
5. Set `PERSONAL_BATCH_DISPATCH_TOKEN`.
6. Delete the two stale recovery branches.
7. Review dp_pod PR #1381.
