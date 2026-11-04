# The dub hook Shorts skip the map too (Nov 1 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The dub hook Shorts skip the map too (Nov 1 2026)

Register `dub-shorts-skip-map-2026-11-01`; guards
`tests/test_dub_shorts_skip_map_2026_11_01.py`. The @NerraRU (`engine/ru_dub.py`)
and @NerraFR (`engine/lang_dub.py`) hook Shorts kept the translated map, a
median 10.5 s (RU) / 10.3 s (FR) of a ~32 s Short. Rules that bind: **the dub
map is found by POSITION, never by language cues** — the translation keeps the
English script's lines one for one (every mapped RU/FR script of Oct 20-Nov 1),
so the dub line at `map_line_range`'s index on the English `_tts.txt` is the
map; a dub whose line count differs gets no cut. **Its edges come from the dub
track's own Whisper words, matched by letters** (`dub_norm`: Cyrillic
transliterated, accents folded, digits dropped because the script spells numbers
and Whisper writes digits; `story_breaks._norm` drops every Cyrillic letter and
cannot be used). An edge prefers a sentence start, steps back over a number
Whisper wrote in digits ("15 -й полёт"), and snaps into the track's own silence;
the span between the edges must read as the map's text. Any refusal renders the
Short from the dub track as before (`dub_short_source`, Short #1 `hook_open`
only, behind the same `youtube.shorts_skip_map`; result key `shorts_map_cut_s`,
index row `map_cut_s`). **The dub long-form, the language feeds and the episode
keep the map.** Replay on 172 Whispered dub openings: RU 40/41, FR 57/58 mapped
openings cut, 0 of 73 without a map; the two misses are Whisper holes over the
map (refused). The dub's word JSON is gitignored, so the committed fixture
`tests/fixtures/dub_openings_2026_11_01.json` carries seven real openings and
the VTTs carry the rest.
