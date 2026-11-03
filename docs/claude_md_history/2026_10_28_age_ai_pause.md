# The Age of AI: her pause explained, the guest on video, research she starts herself (Oct 28 – Nov 1 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The Age of AI: her pause explained, the guest on video, research she starts herself (Oct 28 2026)

Operator-directed after the Oct 28 test room (median 4.4 s from the guest's
last word to Mira's first; Mira said she cannot look anything up). Guards
`tests/test_what_viktors_episode_taught.py::TestEachShowHasItsOwnRoomClips`,
`tests/test_guest_video_2026_10_28.py`,
`tests/test_mira_researches_on_her_own_2026_10_28.py`,
`tests/test_turn_cues_2026_10_28.py`, `workers/voices/test/guest_video.test.ts`.
Rules that bind:

- **The pause is explained before the guest enters.** Each show's consent
  notice (`pipelines/voices/narration/<show>_room_2026_10_28.json`, voiced to
  `<show>/narration/<show>_room_2026_10_28/disclosure.mp3`) asks consent
  FIRST, then says her wait after an answer is on purpose and is taken out of
  the published episode. The prompt, the studio tips, the booking mail and
  the prep brief say the same. The edit's `close_gaps` (MAX_GAP_SEC ≤ 1.0)
  is what keeps that promise; the guard pins both.
- **The guest's camera is recorded in the browser, never through the call.**
  The Voximplant recorder is not a source (Glenn Broder: ~16 kbps of 1080p,
  502 gaps over 2 s; the Oct 28 test room: no packets). The studio (section
  4b) records 720p/2.5 Mbps with the raw mic in 5 s chunks to the Worker's
  `kind=video` lane (`<prefix>/local/<run>/guest-video/<sid>/`), listed on
  the run as `grok_session_log.local_video_takes.guest`. **A video take never
  touches `local_<role>_url`** (the audio pointer the mix is built from).
  The page records only when studio-state says `video_take` (the guest, on a
  run whose `grok_session_log.local_video` is true); it then sends no video
  to the call. `video_take.py` assembles each take and places it on the
  guest leg's clock by its own microphone (`room_pieces`, same as an audio
  take) into `tracks.video`; best-effort, an audio episode either way.
- **The switch.** `voices.local_video` (shows.py default and
  `shows/nerra_voices.yaml`) is **false until a test room with a person on
  camera passes and the operator has watched it**; every rehearsal/test-room
  run row carries `local_video: true` regardless.
- **The video version is cut exactly as the sound was**
  (`render_video.py`): the edit's `clock` (`[room_from, room_to, edit_from(,
  scale)]`, room times carry `tracks.edit.room_offset_sec`) gives every
  frame; a stretch with a scale (pauses closed blind) or one the camera did
  not see shows the guest's name card; 1920x1080, guest left, Mira's studio
  loop right, the speaker's tile bordered in the show colour. Stored as
  `tracks.edit.video_url` with `video_of` = the edit URL; **publish uses it
  only while `video_of` is still the edit being published** and never when
  the guest ticked audio only (`editorial_packages.guest_video_ok = false`,
  migration `20261028_guest_video_choice.sql`, offered on the review page only
  when a picture exists). YouTube gets the video instead of the waveform, X a
  ≤140 s clip of the first clip suggestion (moved to the edit's clock; the
  first vertical Short since later that day), the
  episode page a `<video>` player (our own `audio.nerranetwork.com/*.mp4`
  only). Workflows: a `video` job after post-interview and assemble-edit
  (`continue-on-error`), and **Cut the video version of an interview** by
  hand (`preview` for a test room).
- **Research the room starts on its own.** `fact_check_claim` has been off
  her tool list since Oct 21, so nothing searched. Now the room starts the
  lookups (`maybeAutoResearch`, on each of her remembered lines): one on the
  guest after her first line (recent news, never the biography), then one
  per answer of ≥ 30 words at most every 150 s, eight a room, two in flight.
  Same xAI Responses call (grok-latest, web + X search). A finding reaches
  her as ONE sourced note (`researchNoteText`) that never starts a turn,
  never corrects the guest, and is let go when the moment has passed; a
  finding that would contradict the guest is `found: false`. Never in a
  hello or closing session, a hold or the closing round (a late finding is
  kept back). **The trace never carries the guest's words** (an answer is
  "an answer of N words"); findings go to the webhook as `research_notes` /
  `research_lookups` (Worker `roomCountersOf`, bounded) and to the rehearsal
  room log. Off for one room: `grok_session_log.auto_research = false`.
- **When has the guest finished? Measured, not guessed**
  (`pipelines/voices/turn_cues.py`, report in
  [`docs/reviews/turn_cues_2026_10_28.md`](docs/reviews/turn_cues_2026_10_28.md)).
  Every pause in the guest's speech is labelled by what happened next (they
  went on; they stopped ≥ 1 s and waited; or the room decided for them, set
  aside) and scored against the voice, the last words (faster-whisper,
  `--words`) and the camera (`--video`; a test room's takes are placed on the
  fly from its stereo recording). On 22 rooms (10,433 holds, 643 ends): the
  voice at the pause (pitch slope, final pitch, energy fade, lengthening)
  does NOT tell done from thinking (held-out AUC 0.55-0.61), so no prosody
  rule goes into the room; how long a guest pauses mid-answer is a property
  of the guest (most rooms ≤ 11 pauses over 2 s an hour, run c868dac8 80),
  which is why one fixed timer interrupted some guests and not others; the
  words barely help either (the room's own clause rule reads every real end
  as finished and catches 11% of long thinking pauses — guests think between
  sentences). What the data supports is a wait learned from the guest's own
  pauses (`adaptive_policy`: same safety as 3 s, 0.2 s sooner on average,
  1.5-2 s for a guest who never pauses long) — a room change, so candidate
  rehearsal and a listen first. No room has had a usable picture yet; run
  `turn_cues.py --run <test room> --video --words` on the first test rooms
  with the camera on (`render_video.py --preview` shows the operator that
  camera, uncut) before any camera cue is built. ⚠️ Nothing here changes the
  room's timing.

**Same day, the second test room and Michael Kamins' room** (guards
`tests/test_second_test_room_2026_10_28.py`, `workers/voices/test/guest_video.test.ts`):

- **A take is appended in the database, never read-and-written.** The page
  finishes its audio and camera takes together; both upload-dones rewrote
  `grok_session_log` and the camera take's listing was lost (its 42 chunks
  safe in R2). `voices_append_take` (migration
  `20261028_voices_append_take.sql`, applied) appends under the row lock,
  deduplicated by manifest; the Worker falls back to read-and-write only on
  a database without it. Post-production and the preview also find an
  unlisted take in R2 (`video_take.discover_takes`), and adopt one whose page
  never finished (a manifest written up to the first gap).
- **Asked to look something up, she does.** A guest's request
  (`RESEARCH_ASK_RE`) starts a lookup at once (inside the cap, outside the
  answer gap, one per 45 s); her next turn says in a few words that she will
  bring it in (`takeResearchAsk`, a one-turn instruction after any guest
  steer); the finding comes as a `request` note to bring in on her next turn;
  nothing reliable is said only if they ask again. Her brief says the room
  looks things up as she talks (she had told Patrick she cannot browse).
- **A test room plays the show's own notice** (`rehearsal.build_run_row`
  carries `room_clips(show)`).
- **A typed wrap-up is a stop.** The whole typed message must be the request
  (`TYPED_WRAP_UP_RE`, anchored: "how we wrap up a launch" stays a topic):
  in the closing round it closes with her thanks; before it, the closing round
  begins. Michael's "we can wrap up now" had been held as a topic for five
  minutes. Stored as `guest_feedback[].wrap_up`.
- **The studio follows the headset the guest puts on** (section 4c): new
  headphones get Mira's voice (the call's `outputId`); a wired or USB
  microphone is switched to at once, in setup and mid-call; a Bluetooth
  headset's microphone is offered with one click, never taken, because it
  drops to phone-call quality (the reason phone calls left the show); a
  "Default" selection is pinned to the device it meant before the list is
  rebuilt; an unplugged microphone falls back. Run by
  `tests/fixtures/studio_devices_sim.js`. (Later the same day the studio
  ranks microphones; see below.)
- **Background blur** (section 4d): MediaPipe's selfie segmenter
  (`@mediapipe/tasks-vision@0.10.14`, loaded only when a guest turns blur on)
  on a 256x144 copy of each frame, the person drawn sharp over a blurred
  frame; Chrome/Edge transform the camera's own frames
  (`MediaStreamTrackProcessor`, keeps recording in a background tab), other
  browsers draw through a canvas. **What is recorded is what they see**: the
  take records the blurred track, never the raw camera. A failure leaves the
  camera as it was and says so.

Operator: push; `wrangler deploy` in `workers/voices` (video lane, studio
`video_take`, review-page choice, booking copy, research counters, the take
append); both migrations are applied. Scenario (research): the candidate rehearsal, a listen,
then "Deploy Voximplant scenario". Video: a test room with the camera on, the
workflow "Cut the video version of an interview" on that run with `preview`
ticked (a test room is never post-processed, so the preview is the room
uncut, emailed, published nowhere), watch it, then set `local_video: true`
for the show. ⚠️ AUDIO (the new notice) and ⚠️ the room (research).

**Later the same day, Patrick on the first video preview** (guards
`tests/test_video_sync_and_shorts_2026_10_28.py`,
`tests/test_second_test_room_2026_10_28.py::TestTheStudioFollowsTheHeadset`,
`tests/test_mira_researches_on_her_own_2026_10_28.py`):

- **Mira moves only while she speaks** ("it had her talking when she was not,
  and that looks really bad": the loop had played the whole hour). Who
  speaks when is MEASURED from the audio, never the transcript
  (`speech_on_edit`): her processed track's speech runs moved onto the edit's
  clock (through `tracks.edit.clock` and `room_offset_sec`), plus speech in
  the edit itself where it plays her narration (`tracks.edit.pieces`, which
  `assemble_edit.pieces_of` now records: narration / mira / guest / room /
  gap; an older edit reads narration as whatever the clock does not cover);
  a cut of the guest's own track silences her, one of hers silences the
  guest. Her face: rest, the loop from its first frame while she talks
  (pauses under 0.45 s are breaths), five frames easing back to rest when she
  stops (`mira_plan`, `render_mira_track`; every part all-keyframe, joined
  exactly). On the test room: 87% of her talking frames move, 0.6% of her
  quiet ones. The speaker's border uses the same measurement (1 s floor
  hold); the transcript is the fallback only when the tracks cannot be read.
  Her tile is head-and-shoulders from her portrait (`mira_crop`), like a
  camera.
- **Two shapes from one edit.** The long form stays 1920x1080 side by side
  (YouTube, the episode page). **Shorts**: up to three 1080x1920 clips, the
  guest stacked over Mira, show name on top, word-by-word captions
  (`engine.transcripts` + `engine.captions.transcript_to_ass_window`, the
  network's Shorts style) clear of the phone apps' bottom furniture, cut from
  the clip pass's moments moved to the edit's clock (`clip_windows`: 15-90 s,
  none overlapping). Stored as `tracks.edit.shorts` with `shorts_of`; publish
  uses them only for that edit and never for an audio-only guest
  (`episode_shorts`). YouTube: the first public with the episode, the rest at
  the channel's next Shorts slots (`engine.shorts_stagger`), `kind: short`
  in the video index, each linking the long video and saying the host is an
  AI. X posts the first Short (the 16:9 cut is the fallback). The test-room
  preview renders both shapes (a first-minute Short).
- **The best microphone** (studio 4c, `micScore`): a dedicated microphone >
  a wired/USB headset > an unnamed USB device > the computer's own > a
  webcam's > Bluetooth (phone-call quality); software devices (Zoom, Teams,
  BlackHole, Krisp, OBS, Continuity) are never chosen for anyone. On opening
  the page takes the best one unless the person picked (a step only to a
  known better kind, or off Bluetooth/webcam); a device plugged in later is
  taken when it ranks at least as high as the one in use, else offered; an
  unplugged one falls back to the best left. AirPods already on: the
  computer's microphone is taken, Mira stays in the AirPods.
- **Research answers in seconds and knows the guest.** Live: at default effort
  a lookup took 60-70 s; `reasoning.effort: "low"` 8-12 s, same findings (a
  model that refuses the setting is asked again without it). The fire step
  seeds the run with the guest's own pages (`room_log_seed`:
  `grok_session_log.guest_links`, ≤ 5 http(s) URLs) and the guest lookup
  names them; with them the lookup found Michael Kamins' podcast of six days
  earlier, without them nothing.
- **Does the camera tell when the guest has finished?** Not yet known. The
  room never sees the picture (the camera is recorded in the browser), so
  any cue would have to be computed in the studio page and sent to the room.
  On the one test room with a placed camera (17 pauses) motion at the pause
  separates nothing; `turn_cues.py --video` needs ~5 rooms with the camera on
  (~100 long pauses) before a cue is worth building. ⚠️ Nothing changes the
  room's timing.

- **Post-production never loops on a line** (Michael Kamins' room, run
  35cdf6f4; guard `tests/test_michaels_post_production_2026_10_28.py`).
  `tidy_lines` (Oct 27) moved a stub of a few unfinished words to its
  speaker's next line with a `for ... else`; a stub whose speaker did not
  come back within `TIDY_REACH_SEC` left by `break`, skipped the `else` that
  moves on, and looked at the same line forever. His post-production hung
  silently after both transcripts, twice, until the two-hour limit, and
  nothing reached the run row. Every pass now removes a line or moves on.

- **Michael's episode, re-cut by hand, and what the review found in the
  pipeline** (Oct 29 2026; guard `tests/test_michaels_post_production_2026_10_28.py`).
  The auto cut kept the whole room. The re-cut (EDL stored in
  `episode_edits`, every removal listed with its reason under `removed`)
  takes out the two questions he skipped ("let's skip that"), the assertion
  he called incorrect, every repeat of a question he asked her to repeat
  (her clearest ask is kept), the echo openers that restated his answer
  (one kept wherever the question needs it as an antecedent), his repeat of
  his first answer, his first version of the scoring answer (Mira's own
  question gets the full one at 21:03), and "that's the end of the
  recording, you can hang up now"; his "you cut out" is muted under her
  question. 40.5 -> about 36 minutes. Pipeline faults it found, fixed:
  `split_on_pauses` joined the stripped JSON words with nothing
  ("That'sareallysolidquestion", 47 lines; parts are now sliced from the
  segment's own text); `strip_echo_lines` dropped his "Does that make sense?"
  as her echo (summed character blocks; an echo now also needs her words in
  her order, `_words_in_order`); the transcript of the edit printed lines
  under a `mute`; the post printed the ROOM's transcript, cut lines and all
  (it prints `edit_transcript` now); and the guest's shareable moment
  linked the room's second into the published file (`clip_link` moves it to
  the edit's clock). The Voximplant video of his room is not usable: 19 kbps
  of 1080p, 38% of frames frozen, corrupt blocks, motion separates nothing
  (talking vs listening AUC 0.48; at a pause 0.52). His audio says what the
  camera cannot: mid-answer pauses p99 1.6 s, three over 2 s in 43 answers,
  while Mira waited a median 4.3 s at every real end.
- **Published as Ep15 (Nov 1 2026), reviewed** (guard
  `tests/test_michaels_publish_2026_11_01.py`). Feed, post, transcript,
  chapters, links and YouTube were right. Three faults, fixed: the publish
  mail told him "February 2027" (the three-month default) after he chose
  "about six months" on the review page (`return_invitation_html` reads
  `guest_followup`: 6 or 12 months from the day he chose, no date for
  "nothing for now"); the note above an EDIT transcript said "as it was
  recorded" (`EDIT_TRANSCRIPT_NOTE` says it is edited for length and flow);
  chapter titles lifted from mid-question kept their lower case
  (`_chapter_case`; `refresh_post` now rewrites the record's chapters too).

Operator: push (the studio page and the pipeline go live with it; the Worker
is unchanged); "Nerra Voices — rehearsal" with `candidate_scenario` for the
research changes, then "Deploy Voximplant scenario"; no new secret (Shorts go
up with the publish workflow's YouTube credentials).
