# Podcast Music Assets

Centralized directory for all podcast intro/outro music files across the
network. Each show has its own music file(s) referenced by the show's YAML
config under `audio.music_file` and optionally `audio.background_music_file`.

## Directory Layout

```
assets/music/
├── tesla_shorts_time.mp3          # TST — energetic tech/financial news theme
├── fascinatingfrontiers.mp3       # FF — short cosmic intro jingle (~5 s)
├── fascinatingfrontiers_bg.mp3    # FF — longer ambient space background/outro
├── oilers-pride.mp3               # PT — science/discovery theme
├── OmniView.mp3                   # OV — balanced news theme (May 2026; replaced LubechangeOilers.mp3)
├── EnvIntel.mp3                   # EI — Canadian environmental-policy theme (May 2026)
├── ModelsAgents.mp3               # M&A and M&AB — AI/agents theme (shared across both shows)
├── ModernInvesting.mp3            # MIT — financial/market intelligence theme (May 2026)
├── Финансы Просто.mp3             # FP — Russian financial-literacy theme (May 2026)
├── ПриветРусский.mp3              # PR — Russian language-learning theme (May 2026; on-disk filename
│                                  #       is in Unicode NFD form — keep YAML music_file in sync if
│                                  #       the file is ever renamed; see shows/privet_russian.yaml)
├── LubechangeOilers.mp3           # ORPHANED (May 2026) — OV moved to OmniView.mp3; kept on disk
│                                  #   for rollback. Safe to delete after a few clean OV runs.
└── README.md                      # This file
```

## How Music Integrates with the Pipeline

The `engine/audio.py` module provides `mix_with_music()` which is called by
`run_show.py` during episode generation. Each show's YAML config (`shows/*.yaml`)
controls the music behaviour:

```yaml
audio:
  # Primary music file (intro + overlap + fadeout + outro)
  music_file: assets/music/your_show.mp3

  # Optional: separate file for outro/background (dual-music mode)
  background_music_file: assets/music/your_show_bg.mp3

  # Delay voice start so intro music plays alone (seconds, 0 = no delay)
  voice_intro_delay: 0.0

  # Timing parameters (seconds)
  intro_duration: 5.0       # Music plays alone before voice
  overlap_duration: 3.0     # Music + voice overlap
  fade_duration: 18.0       # Music fades out under voice
  outro_duration: 30.0      # Music plays after voice ends

  # Volume levels (0.0–1.0)
  intro_volume: 0.6
  overlap_volume: 0.5
  fade_volume: 0.4
  outro_volume: 0.4
```

### Mixing Modes

**Standard mode** (`voice_intro_delay: 0`, no `background_music_file`):
Used by TST, PT. One music file provides intro, overlap, fadeout, and outro.
```
0–5 s:      music intro alone
5–8 s:      music + voice overlap
8–26 s:     music fadeout (logarithmic)
26 s–end:   voice alone (silence on music track)
after voice: 30 s outro with fade-in/out
```

**Delayed-intro mode** (`voice_intro_delay: N`):
Music plays alone for N seconds, then voice begins with overlap/fadeout.

**Dual-music mode** (`background_music_file` set):
Used by FF. Primary file for intro section, secondary file for
background/outro. The background track fades in near the end of voice and
continues through the outro.

## Creating Music for New Shows

### Recommended Tools

1. **Suno** (suno.com) — AI music generation, best for full tracks
2. **Udio** (udio.com) — AI music generation with fine-grained control
3. **AIVA** (aiva.ai) — AI composer for cinematic/atmospheric music

### Guidelines Per Show Type

| Show Type | Mood | Tempo | Instruments | Duration |
|-----------|------|-------|-------------|----------|
| Tech/Financial (TST) | Energetic, confident | 110–130 BPM | Synths, electric guitar, driving beat | 30–60 s |
| Space/Science (FF) | Wonder, cinematic | 80–100 BPM | Orchestral, pads, ethereal textures | 30–60 s |
| Science/Health (PT) | Curious, optimistic | 90–110 BPM | Acoustic + electronic, warm pads | 30–60 s |
| Balanced News (OV) | Authoritative, neutral | 100–120 BPM | Piano, strings, clean percussion | 30–60 s |
| Professional/Regulatory (EI) | Professional, serious | 80–100 BPM | Clean piano, minimal strings | 20–40 s |
| Financial/Investing (MIT) | Confident, precise | 110–120 BPM | Piano, subtle electronics, clean beat | 30–45 s |

### Prompt Templates for AI Music Tools

**TST (Tesla Shorts Time):**
> Energetic tech news podcast intro. Driving electronic beat with synth pads
> and a confident, forward-moving feel. Think stock market opening bell meets
> Silicon Valley. 30–45 seconds, clean ending for loop.

**FF (Fascinating Frontiers):**
> Cinematic space exploration podcast theme. Ethereal pads, orchestral swells,
> sense of wonder and cosmic discovery. Gentle but building, suitable for
> astronomy and space news. 30–45 seconds.

**PT (Planetterrian Daily):**
> Uplifting science discovery podcast theme. Warm, curious tone blending
> acoustic and electronic elements. Think breakthrough moments in medicine and
> health research. Hopeful and human. 30–45 seconds.

**OV (Omni View):**
> Balanced news podcast intro. Authoritative and neutral, conveying trust and
> breadth. Clean piano with subtle strings and light percussion. Professional
> and welcoming. 30–45 seconds.

**EI (Environmental Intelligence):**
> Professional environmental briefing theme. Clean, serious, and focused.
> Minimal piano with subtle ambient texture. Conveys expertise and regulatory
> authority. Short and purposeful. 20–30 seconds.

**MIT (Modern Investing Techniques):**
> Confident financial podcast intro. Clean, modern production with subtle
> electronic beats and piano. Conveys intelligence, precision, and controlled
> energy — think Bloomberg terminal meets algorithmic trading. Professional but
> not corporate. Emerald green energy. 110–120 BPM. 30–45 seconds, clean ending.

### Audio Specifications

All music files must meet these specifications for compatibility:
- **Format:** MP3
- **Sample rate:** 44100 Hz
- **Channels:** Stereo
- **Bitrate:** 192 kbps or higher
- **Duration:** 30–60 seconds (loops via `-stream_loop` for outro)
- **Clean endings** preferred (avoid abrupt cuts)

### Adding Music to a New Show

1. Generate or source a music file following the guidelines above
2. Save it as `assets/music/<show_slug>.mp3`
3. Add the audio config to your show's YAML:
   ```yaml
   audio:
     music_file: assets/music/<show_slug>.mp3
     intro_duration: 5.0
     overlap_duration: 3.0
     fade_duration: 18.0
     outro_duration: 30.0
     intro_volume: 0.6
     overlap_volume: 0.5
     fade_volume: 0.4
     outro_volume: 0.4
   ```
4. Run the show — `mix_with_music()` handles the rest automatically
5. If the music file is missing at runtime, the show gracefully falls back to
   voice-only output with a warning log
