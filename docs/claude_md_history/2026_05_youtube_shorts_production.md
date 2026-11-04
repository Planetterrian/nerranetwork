# YouTube Shorts production (May 2026 retune)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### YouTube Shorts production (May 2026 retune)

Two Shorts-quality fixes shipped after the operator caught issues
with the first wave of episodes:

* **Thumbnail title auto-shrink-to-fit.**
  [`engine/publisher.py:generate_episode_thumbnail`](engine/publisher.py)
  iteratively shrinks the hook font (start at the YouTube-spec max,
  step down by 8 px) until the wrapped block fits inside 60 % of the
  frame height AND ≤ max-lines (3 on Shorts 1080×1920, 4 on long-form
  1280×720). Floor at ~32 px. Replaces the legacy fixed-size
  rendering that clipped long Tesla hooks against the safe area.
  Drift guard: `tests/test_thumbnail_autofit.py`.
* **Shorts burn-in caption upgrade.** Bumped from outline-only
  FontSize=34 to FontSize=48 bold on a 50 %-opaque box
  (`BorderStyle=3` + `BackColour=&H80000000`) in
  `engine.video._SHORTS_SUBTITLES_FORCE_STYLE` — TikTok-style
  "subtitle card" that stays readable over Grok-Imagine backgrounds.
  Position shifted to `MarginV=340` to keep the larger card clear of
  the URL pill (y ≈ 1820) and below the hook overlay (y ≈ 1056).
  Caption wrap tightened to 24 chars / 2 lines (was 32 / 3) to match
  the larger font; see
  `engine.captions.transcript_to_srt_window`. Drift guard:
  `tests/test_video_commands.py::test_short_form_filter_graph_burns_subtitles_when_path_provided`.

`shows/models_agents_beginners.yaml` also flipped from
`image_provider: pexels` to `grok` in May 2026 — Pexels A/B was
inconclusive and the gallery pipeline (Phase 1) requires Grok
Imagine. Cost: ~$0.16/episode added.

**Per-word caption highlighting (TikTok / Reels look).** Shorts now
ship with per-word "current word" highlighting instead of static
segment cards.
[`engine.captions.transcript_to_ass_window`](engine/captions.py)
generates an ASS file (the modern subtitle format the ffmpeg
`subtitles` filter accepts identically to SRT — no `video.py` change
needed) with one `Dialogue` line per word; each line shows the full
chunk text with the active word colour-flipped to Nerra cyan
(`#00D4FF` / ASS `&H00FFD400`). Word timestamps come from
`faster-whisper` which already runs with `word_timestamps=True` in
`engine.transcripts` — no new transcription cost. Words are chunked
to ≤24 chars / ≤8 words per chunk to match the FontSize=48 caption
card. `run_show.py` tries the ASS path first; if the transcript has
no word data (older episodes) or no overlap with the Shorts window,
it falls back to the legacy segment-level SRT so the Short always
has captions of some kind. Drift guards in
`tests/test_captions_ass.py`.

**Smart Shorts segment selection.** Tesla + MAB now use
`shorts_start_mode: smart` in their YAML, which calls
[`engine.shorts_selector.pick_engaging_window`](engine/shorts_selector.py)
to scan the Whisper transcript and start the Shorts clip at the
most engaging beat (numeric reveal, hook framing like "the kicker
is…", surprise / question / superlative). Pure heuristic — no LLM
call, no per-episode cost. Falls back to the legacy
`voice_intro_delay` start when no segment scores above the noise
threshold (5.0). The chosen offset + the resolved mode are recorded
as metrics (`shorts_start_offset`, `shorts_start_mode_resolved`) per
episode so the dashboard can show smart-vs-fallback rates. New shows
opt in by setting `youtube.shorts_start_mode: smart` in their YAML.
Drift guards in `tests/test_shorts_selector.py`.

**Multiple Shorts per episode.** Setting `youtube.shorts_per_episode`
to N (default 1; cap at 2-3 for YouTube quota safety on the
@NerraNetwork channel — see landmine #20) makes the runner publish
N Shorts per episode instead of one. Each Short comes from one of
the top-N non-overlapping windows the smart selector
([`pick_top_n_engaging_windows`](engine/shorts_selector.py)) picks
from the transcript; each gets a distinct headline (the window's
opening text), a distinct thumbnail (cycled through the available
Grok-Imagine scene images), and a distinct filename
(`_short_1.mp4`, `_short_2.mp4`, …). Uploads are sequential; one
failure doesn't block the others. Per-Short error captures land in
`result["short_errors"][i]` and the aggregate
`shorts_count_requested` / `shorts_count_uploaded` metrics fire on
every episode so the dashboard can plot the multi-Shorts hit rate.
Requires `shorts_start_mode: smart` (the voice / first_chapter
modes only know about one offset). Default 1 preserves legacy
single-Short behaviour byte-for-byte. Drift guards in
`tests/test_shorts_selector.py` under the
`pick_top_n_engaging_windows` block.

**Staggered Shorts publishing (Aug 2026, operator-directed).** Short #1
publishes with the episode; the 2nd/3rd upload PRIVATE with
`status.publishAt` at the channel's next optimal UTC slots
(`youtube.shorts_stagger_slots_utc` in `_defaults.yaml` — EN 17/21/23,
RU 15/18/20, FR 17/19/21; audience-timezone priors, hand-tuned because
the Analytics API has no hour-of-day dimension), so one episode's Shorts
spread through the day on every channel, manual runs included. YouTube's
own scheduler flips them public — no new infra, dead runners can't
strand a Short. Engine: [`engine/shorts_stagger.py`](engine/shorts_stagger.py);
wired in `run_show._publish_youtube`, `engine/ru_dub.py`,
`engine/lang_dub.py`. The video index records the **publishAt** date so
policy vpd math stays honest. Funnel comments can't be posted on a
private video, so they queue to `digests/<slug>/scheduled_comments.json`
and `scripts/post_scheduled_short_comments.py` (multilingual sweep +
nightly, which hold the channel tokens; sidecar is in nightly's
add-paths whitelist) posts them once public. `shorts_stagger_enabled:
false` per show reverts to publish-all-now. Drift guards:
`tests/test_shorts_stagger.py`.

**Auto-hashtag injection on Shorts descriptions.** Every Shorts
upload now carries entity-derived hashtags in its description
(via [`engine.shorts_hashtags.extract_hashtags`](engine/shorts_hashtags.py)).
YouTube renders the **first 3** hashtags as clickable topic-tag
links above the video title — biggest discovery lever on Shorts
after the title itself. Heuristic-only parser, no LLM call:
multi-word Title-Case entities (`Tesla Cybercab` →
`#TeslaCybercab`) outrank single proper nouns (`Tesla` →
`#Tesla`) which outrank all-caps acronyms (`TSLA` → `#TSLA`),
with the show's YAML `keywords` blended in at the tail to fill
remaining slots. Substring de-dupe across bands prevents
"#Tesla" eating a slot when "#TeslaCybercab" already covers the
entity. Caps at 5 hashtags + the static `#Shorts #podcast`
suffix. Real-hook probes: Tesla wireless-BMS hook →
`#BatteryManagementSystem #Tesla #Cybercab`; Modern Investing
TFSA/RRSP hook → `#ModernInvestingTechniques #TFSA #RRSP`. Drift
guards in `tests/test_shorts_hashtags.py`.

**Hook overlay auto-shrink-to-fit.** The 0–3 s static hook
overlay on the Shorts MP4 used to render at a fixed
fontsize=44 with a conservative char-based wrap (26 chars × 4
lines = 104-char budget) that truncated longer Tesla hooks with
"...". `engine.video.autofit_hook_overlay` now applies the same
shrink-to-fit pattern the thumbnail uses: start at 44 px, drop
in 4-px steps (44 → 40 → 36 → 32) only if the wrapped text
would truncate at the larger size. Pixel-accurate wrap via PIL
`ImageFont.getbbox` uses the actual 1080-px Shorts frame width
instead of the char-budget approximation, so a 110-char hook
(Tesla Ep461 Cybercab wireless-BMS) now fits at 44 px without
truncation, and runaway 170+-char hooks shrink to 32 px and
still fit. Drift guards in `tests/test_video_commands.py` under
the "Shorts hook overlay auto-shrink-to-fit" header.

**End-screen CTA card.** The last
`youtube.shorts_end_card_duration_seconds` (default 3 s) of every
Short overlays a PNG end card composited at run time by
[`engine.publisher.generate_shorts_end_card`](engine/publisher.py).
The card shows the long-form 1280×720 thumbnail in the upper third
(framed with a thin white border so it reads as a tap target),
a big white headline ("WATCH FULL EPISODE"), a cyan sub-line
("Tap Subscribe ↗", matching the per-word caption highlight from
PR #415), and a small `nerranetwork.com` footer. The
`engine.video._short_form_filter_graph` overlays the PNG via a
single `overlay=enable='between(t,END-3,END)'` filter. When PNG
generation fails (or the long-form thumbnail upstream failed),
the chain falls back to the drawtext-only version originally
shipped in PR #417 — soft degradation, never blocks the Shorts
publish. Implemented as a drawbox + 2 drawtext
filters in the existing filter graph — zero filesystem dependency,
no per-episode asset generation. YAML knobs to customise:
`shorts_end_card_enabled` (default true network-wide), plus
`shorts_end_card_main_text` / `shorts_end_card_sub_text` /
`shorts_end_card_duration_seconds` for per-show overrides (useful
for Russian-language shows when they migrate to YouTube). Drift
guards in `tests/test_video_commands.py` under the "Shorts end-
screen CTA card" header.
