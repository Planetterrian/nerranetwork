# "Eyes on the Horizon" — Offshore North theme (Suno brief + lyrics)

To be operator-produced in Suno (the dp_pod pattern: one full song whose
track doubles as the intro/outro bed on every episode). Save the final
track as `assets/music/offshore_north.mp3` — the show YAML already points
at that path and the pipeline engages the full broadcast chain (sidechain
ducking, -16 LUFS master) the moment the file exists. Nothing else to
configure.

**CRITICAL STRUCTURE REQUIREMENT:** the song must open with **35–45
seconds of purely instrumental build — no vocals** — because the mixer
uses the file from t=0 as the episode's intro bed (music alone, then
ducked under Dan's cold open through the first ~26 seconds). Vocals in
that window would sit under speech. Verse one starts after the
instrumental open. Clean, resolved ending — no fade-out.

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

- MP3, 44100 Hz, stereo, 192 kbps+ · total length flexible (2–3 min is
  fine — the mixer uses the opening ~26 s as the bed and loops the tail
  for the outro) · clean resolved ending.
- After saving the file, nothing else is needed: `shows/offshore_north.yaml`
  already carries `audio.music_file: assets/music/offshore_north.mp3`
  (a clean no-op until the file exists).
- Optional debut flourish (the dp_pod Episode-1 pattern): if the track is
  ready BEFORE the Episode 1 regeneration is dispatched, we can also wire
  `audio.debut_song_file` so the premiere plays the full song after the
  closing, introduced on air. Say the word before merging and it gets
  wired; after Ep1 ships, the moment has passed.
