# The voice marks a story change; the music swell is gone (Oct 20 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The voice marks a story change; the music swell is gone (Oct 20 2026)

Operator listen: the Oct 14 music interludes between stories are not wanted
(register `story-tags-and-map-2026-10-20`; guards
`tests/test_story_tags_2026_10_20.py`). Measured first, on Tesla Ep639 and
Vancouver Ep027 against NPR's hourly newscast and Up First with the same
pitch-and-pause analysis: **a human newsreader does not pause longer between
stories than between sentences** (0.5-0.7 s either way on NPR; one pause over
0.7 s in the whole cast) and marks the change with the VOICE — a +2..+8 Hz
lift opening an ordinary sentence against **+34 Hz** opening a new segment,
and a firmer landing on a segment's last words (−30 vs −18 Hz). Grok TTS on
the custom voice lifts ~+20 Hz at every sentence and the same at a story
change, and lands identically at both — so nothing in the audio told a
listener a story had changed, and the Oct 13 pause and the Oct 14 swell
(**13 swells** in nine minutes on Tesla, 5-10 dB under the voice after
loudnorm, 11 of 13 between items inside one section) were treating the
symptom. Post-processed pitch shaping (rubberband on the first second of
each story) was rendered and REJECTED by the operator: it robotises the
onset. A separate TTS request per story was measured on UC Ep143 and gives
no fresh start (+23 Hz onset, −11 landing — a sentence's numbers). Rules
that bind: **`audio.story_break_cue` is false network-wide** (the code
stays for a per-show opt-in; the 1.0 s beat is unchanged); **the voice
marks the boundary with Grok's own tags, inserted in code before synthesis
at the SAME boundaries `story_breaks` finds** (`engine/story_tags.py`,
`tts.story_tags` / `story_tag_open` `[breath]` / `story_tag_close`) so the
committed `*_tts.txt` is what was spoken; **the landing tag ships EMPTY until
Actions "Probe TTS tags" (`scripts/probe_tts_tags.py`, read-only, attaches
the WAVs) shows which pitch tag this voice consumes without speaking it** —
xAI's own tag tables did not render, the code's May list says `<low>`,
Telnyx says `<lower-pitch>`, and an unknown tag is spoken aloud; **every
Whisper match reads the tag-stripped script** (story_breaks anchors, chapter
alignment, the spoken-text gate — a `[breath]` at a line's opening is not in
the audio); **THE MAP**: `build_cold_open_spec` asks for ONE sentence after
the identity line giving the shape of the episode (the two or three stories
after the lead in order, then recurring segments by name; no count, no
number, no promise language, never the lead again, never yesterday's
shape) — a map, not a tease, de-seeded by shape. `script_hook_leads_body_pct`
reads lower by design on map shows (the map sits in its three-sentence
window). ⚠️ AUDIO on every English show — A/B-listen the first slate; read
`story_tags_inserted` beside `story_breaks_inserted` and
`tag_leaks_by_pattern` for `breath` / `pitch-tag`.

**Oct 20 2026, the first slate — the breath is OUT.** The operator heard the
`[breath]` at every story start as "way too prominent" on the custom voice
(the probe had measured it as the cleanest tag; a measurement is not a
listen). Now `tts.story_tags: false` with an empty opener, **no
breath-family tag reaches synthesis whoever wrote it**
(`engine.utils.strip_breath_tags` — `[breath]` / `[inhale]` / `[exhale]` /
`[sigh]` — in run_show before the `*_tts.txt` save, in
`scripts/resynthesize_episode.py` on the committed script, and on the
multilingual stage's translation input), and `[breath]` left the delivery
spec's sanctioned set. The 14 episodes that aired with it are repaired by
re-synthesis from their committed scripts through Actions "Re-synthesize
Episode" (same R2 key, feed item kept; the tool strips the tags from the
script first); their long-form videos and the Nerra Daily edition of the
day keep the old audio. The map sentence and the no-music beat stay.
**A chapter marker never fires on the identity line or the map sentence
after it** unless it is a `start` marker (`engine/chapters.py` — the map
speaks the segments' anchor phrases, and SpaceX Ep136's "later the
engineering angle" titled The Engineering Angle at 11 s while the real
deep dive fell back to its digest heading). `engine/story_tags.py` and the
probe remain for the next candidate, and a candidate is LISTENED to on a
shipped episode before it ships to a slate. **The repair tool never moves a
feed item** (same day, found on the first fourteen repairs): it had rebuilt
the enclosure from `publishing.base_url` — the SITE, a 404 on every repaired
feed — put the MP3 in `<link>` where the blog page belongs, and minted a new
GUID, which every app reads as a new episode to download again. Now
`read_published_item` carries the enclosure URL, link and GUID and
`refresh_rss_item` writes them back verbatim (`keep_existing_guid`); the
workflow commits the stripped `*_tts.txt` and the shifted `.vtt` too. The
audio at the R2 key was right the whole time (the edge cache serves the old
object for a while — read `cf-cache-status` before calling an upload
missing); guard `TestRepairNeverMovesTheFeedItem`.
