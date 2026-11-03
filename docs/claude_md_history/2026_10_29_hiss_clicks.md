# Hiss and clicks: joins, Mira's voice, story pauses (Oct 29 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Hiss and clicks: joins, Mira's voice, story pauses (Oct 29 2026)

Operator listen: hiss and clicks on Nerra Daily, on Mira's intro and on the
first show (register `audio-clean-joins-2026-10-29`; guards
`tests/test_audio_quality_2026_10_29.py`). Measured on Ep070: 86 click
events, 11 of them in Mira's 35 s intro. Rules that bind:

- **A join is never an MP3 stream copy.** `engine.audio.concatenate_audio`
  decodes every input, puts a 6 ms fade on both edges and encodes once. The
  concat demuxer with `-c copy` kept each file's encoder padding: ~39 ms of
  digital silence and a hard step at every handoff. A decoded join adds
  0.0 ms. Every caller goes through it (edition, Personal, the sample,
  section TTS).
- **Pieces are lossless, the finished file is encoded once.**
  `SEGMENT_ENCODE_ARGS` is FLAC (`PIECE_SUFFIX`) for segments, Mira's links,
  Personal's stings, levels and trims. `EDITION_ENCODE_ARGS` (`-q:a 0`, the
  shows' master setting) is passed to the final join. Mira's Grok audio is
  requested as WAV (`engine.tts._tts_output_codec_args`). A segment had
  three MP3 generations; it now has two (its show's master, the edition).
- **Mira goes through the shows' voice chain.**
  `engine.audio.voice_chain_filters` is the one owner. `normalize_voice`
  and `mira_piece_cmd` both use it, and the -16 LUFS loudnorm follows it.
  Her pieces had loudness only (clicks 11 → 1, pause hiss −67.3 → −71.5 dB
  on the Ep070 intro).
- **A story pause carries the voice's own room tone, never digital zero.**
  `engine.story_breaks.room_tone_spans` loops the quietest 120 ms of the
  pause the voice already left (the quietest, so a breath never repeats);
  `insert_silences_cmd(room_tone=)`; metric `story_break_room_tone`. The
  hiss used to switch off and on at every story change, and the denoiser
  re-learned its floor from zeros.
- **Actions "Probe audio chain"** (`scripts/probe_audio_chain.py`, read-only)
  synthesizes fresh Grok audio on the show voice and Mira, runs every stage
  old and new, prints clicks, floor and hiss, and attaches the files. It
  also renders a stronger denoise (`afftdn=nr=14:nf=-50`) that is NOT
  shipped. That is a listen decision.

Also: the promo-cut frame "this show comes to you from … network" no longer
needs the article (AI Chips Ep038: "from Narin Network").
⚠️ AUDIO on Nerra Daily, Personal and every story pause: listen to the probe
and the first edition.

**Same day, the other shows** (register `audio-tracks-and-mira-declick-2026-10-29`):
- **A translated track is mastered like the English episode**
  (`engine.multilingual.render_mastered_track` → `engine.audio.master_voice_track`:
  the voice chain, then `PUBLISHED_LOUDNESS` -16 LUFS). The FR/RU/ES tracks
  had shipped Grok's raw audio at -26 LUFS with no declick or denoise, into
  the language feeds and both dub channels.
- **Mira's voice gets the strong declick** (`engine.audio.DECLICK_FILTERS`,
  `"strong"` = `adeclick=w=75:t=2`, the Voices restore setting). It is set by
  `audio.voice_declick: strong` in the eight show YAMLs she hosts, and in
  `mira_piece_cmd`. A new Mira show sets it too: a guard compares the setting
  with the `ara` voice. The standard declick left her ~1 click a minute; the
  Patrick shows read 0-1 an episode and stay on it.
- Not changed: audiobook chapter tracks are raw Grok audio already submitted
  to stores. Mastering them is the operator's call.
