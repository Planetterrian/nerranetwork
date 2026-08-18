# "Eyes on the Horizon" — Offshore North theme (Suno brief + lyrics)

**STATUS: PRODUCED AND INSTALLED (Aug 2026).** The operator generated the
track in Suno from the brief below; it lives at
`assets/music/offshore_north.mp3` and is wired in `shows/offshore_north.yaml`
as both the every-episode bed (`audio.music_file`) and the Episode 1
play-out (`audio.debut_song_file` / `debut_song_episode: 1`, the DP Pod
pattern — Dan introduces it on air before the closing).

**Verified on install** (ffmpeg/ebur128): 3:03, 48 kHz stereo, ~191 kbps,
integrated loudness **-13.7 LUFS** — dead centre of the network music
library (-12.9 to -14.7 LUFS), so no level correction was applied and the
shared `_defaults.yaml` volume parameters work as designed.

**Note on the instrumental-intro request below:** the delivered track
starts at full weight rather than building from a lone drone. That turned
out not to matter — since the July 2026 cold-open change the network plays
only ~3 seconds of music alone before the first spoken line, and the mixer
applies a 50 ms click-guard fade, so a full-weight start reads as an
immediate hit of theme. Vocals under speech are handled the same way The
DP Pod handles its anthem: sidechain ducking pulls the bed down 8 dB
whenever Dan is talking. Keep the requirement in the brief for any future
re-generation, but do not treat it as a blocker.

The lyrics below remain the canonical reference — on-air quotes must match
this file exactly.

---

## Suno style prompt

> Epic cinematic maritime anthem, 95 BPM. Vast and windswept: deep low
> strings moving like ocean swell, huge slow drums like waves on a hull,
> a driving acoustic pulse underneath, and a cold bright topline —
> subtle fiddle and whistle colour, more North Atlantic than pirate.
> Determined, not triumphant; the sound of one small light moving across
> an enormous dark sea. Opens with 40 seconds of purely instrumental
> build — no vocals — from a lone low drone to full weight, then lifts
> into soaring verses and a massive singalong chorus. Warm weathered
> male vocal. Modern widescreen production, broadcast-clean. Ends
> resolved and clean, no fade.

**Tags/genre field:** epic cinematic folk, maritime, orchestral,
anthemic, 95 BPM, male vocal, instrumental intro

---

## Lyrics (canonical reference — on-air quotes must match this file)

**[Instrumental — 40 seconds, builds from a lone low drone to full weight]**

**[Verse 1]**
One sail on a world of water
One light where the charts run out
Every mile that the night can offer
Is a mile I can live without doubt

**[Verse 2]**
They said the sea speaks French out here
And maybe that was true
But the cold came down from the north one year
And it's coming back with the new

**[Pre-Chorus]**
Alone is just a word for
Everything I carry on

**[Chorus]**
Fair winds — and eyes on the horizon
Whatever the ocean sends
Fair winds — and eyes on the horizon
Around the world and home again
Around the world and home again

**[Verse 3]**
Ninety-eight seconds of thunder
Twenty-three days in the spray
The ones who went down and the ones who went under
Are the ones who are showing the way

**[Pre-Chorus]**
Alone is just a word for
Everyone who sails along

**[Chorus]**
Fair winds — and eyes on the horizon
Whatever the ocean sends
Fair winds — and eyes on the horizon
Around the world and home again

**[Bridge — quiet, almost spoken, over low strings]**
Nobody from the north has closed the circle
Nobody's flown that flag around alone
So point the bow where the world gets bigger
And bring it home
Bring it home

**[Final Chorus — full weight]**
Fair winds — and eyes on the horizon
Whatever the ocean sends
Fair winds — and eyes on the horizon
Around the world and home again
Around the world and home again

**[Outro — instrumental, resolves clean, no fade]**

---

## Why the lyrics say what they say

- **"Fair winds — and eyes on the horizon"** is Dan's fixed spoken
  sign-off; making it the chorus ties the show's audio brand into one
  loop (the dp_pod "Do something about it" pattern).
- **"Ninety-eight seconds… twenty-three days"** is Mike Birch's 1978
  Route du Rhum win — verified show canon (field guide).
- **"The ones who went down"** carries Gerry Roufs without naming him —
  the lineage is in the song the way it's in the show.
- **"Nobody from the north has closed the circle"** is the spine: no
  Canadian has completed the Vendée Globe.
- Nothing in the lyrics states a fact the show hasn't verified;
  everything else is licence.

## Delivery specs (network standard)

- MP3, 48 kHz, stereo, ~190 kbps, clean resolved ending — the delivered
  track meets all of it (3:03).
- Both wirings are live in `shows/offshore_north.yaml`: `audio.music_file`
  (every-episode bed) and `audio.debut_song_file` + `debut_song_episode: 1`
  (the Episode 1 play-out). Nothing further to configure.
- If the track is ever replaced, keep the loudness near -13 to -14 LUFS so
  the shared volume parameters keep working, and re-check that the closing
  still resolves cleanly (the debut appends the song after the sign-off).
