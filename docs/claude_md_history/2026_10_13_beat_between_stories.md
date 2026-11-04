# A beat between stories (Oct 13 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### A beat between stories (Oct 13 2026)

Operator listen: stories ran into each other. Measured: the gap at a story
change (~0.55 s) equalled the gap between two sentences, and the shared
content-discipline rule told every script to move on "with the next story's
first fact". Now: **`engine/story_breaks.py` splices
`audio.story_break_seconds` (1.2 in `_defaults.yaml`, 0 = off, never on a
dialogue show) of silence where a new story starts**, before the music mix.
Story starts come from the DIGEST (numbered and sourced items are stories;
an essay section is one unit; a one-line detour or a run of one-liners is
not a break); each cut sits in the voice track's own silence
(`silencedetect`, never between Whisper word times, which abut across real
pauses); the splice is lossless WAV and the committed transcript is shifted
with it, so captions, Shorts and the Nerra Daily cut stay aligned. Grok's
`[pause]` tag was measured and rejected (0.0-2.4 s). Scores sum in sorted
order — set iteration follows the hash seed and flipped near-ties. The prompt
rule became "The listener hears every story change": a new story's first
sentence names its subject before any figure. ⚠️ AUDIO — A/B-listen. Register
`story-breaks-2026-10-13`; guards `tests/test_story_breaks_2026_10_13.py`.
