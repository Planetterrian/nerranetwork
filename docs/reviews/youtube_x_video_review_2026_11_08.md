# YouTube and X video review — the long-form's first 30 seconds, and a clean X clip (2026-11-08)

Operator ask: review the full YouTube and X video pipeline and analytics, keep
growing viewers and subscribers on both, and make the videos a better
complement to the audio. Follows
[`youtube_audit_2026_11_04.md`](youtube_audit_2026_11_04.md) (AI Chips and
MAG 7 joined the channel) and the Shorts cover-card fix of Nov 4. Read from
`api/youtube_stats.json` (Nov 7 20:39 UTC, analytics through Nov 5), the
committed transcripts, `_tts.txt` / `_reader.txt` scripts, chapters and
metrics of every episode since Oct 20.

## TL;DR

1. **The channel is growing again, slowly.** EN 560 subscribers (+68 net in
   28 days), views up 16% on the last 14 days against the 14 before (17.9k vs
   15.4k). RU 272 (+36), views up 11%. FR 79 (+12), views down 16%.
2. **Long-forms are the subscriber engine and they lose viewers at one
   identifiable moment.** EN long-forms published Oct 8 - Nov 5: ~20.3k views
   and 28 subscribers; Shorts ~5.4k and 6. Across the 74 EN longs that now
   carry a retention curve, the median share still watching is 91% at 6 s,
   82% at 10 s, 57% at 20 s and 42% at 30 s. The steepest part of the fall
   (6-20 s) is exactly where every English episode since Oct 20 speaks its
   **map** (the one-sentence list of what follows; measured at 7-25 s on the
   Nov 4-8 slate), and the picture during it was only the scene image.
3. **Shipped (render only):** a "Coming up" card that puts the map's own
   stories on screen as they are spoken; a subscribe pill on the long-form at
   45 s and at the midpoint; and an X copy of the hook Short without the
   YouTube subscribe pill and end card.

## 1. Where the views and subscribers come from (EN, 28 days to Nov 5)

| Source | Views | Watch per view |
|---|---|---|
| Browse (home, subscriptions) | 16,734 | 15 s |
| YouTube search | 7,866 | 17 s |
| Shorts feed | 3,250 | 8 s |
| Suggested videos | 2,852 | 72 s |
| External | 631 | 57 s |
| End screens | 1 | — |

Suggested traffic watches five times longer than anything else; end screens
send nothing because the long-forms have none (Studio-only, open since the
Nov 3 review). Search terms are topical ("tesla trick or treat mode", "starship
flight 15", "roberts bank terminal 2"), so the titles are being found for the
news they carry.

Long-forms by show, Oct 8 - Nov 5 (views / subscribers): SpaceX 9,140 / 10,
Tesla 4,270 / 2, Models & Agents 2,623 / 9, MAB 1,374 / 6, FF 1,340 / 1,
Omni View 657 / 0, MIT 635 / 0. SpaceX alone is 45% of long-form views.

The channel also carries 302 RSS-ingested copies of the long-forms in 35
days (`unindexed_recent`, kind `rss_copy`); the Nov 16 Studio removal is the
operator's (landmine #15).

## 2. The long-form's first 30 seconds

Retention, median of 74 EN long-form curves: 3 s 97.5%, 6 s 90.9%, 10 s
82.2%, 15 s 68.1%, 20 s 56.5%, 30 s 42.4%, 60 s 26.3%, 2 min 16.7%, 5 min 8%.
Per show at 30 s: Omni View 0.45, SpaceX 0.45, FF 0.43, Tesla 0.42, M&A 0.42,
MIT 0.42, MAB 0.33.

What plays in that window: 0-4 s the hook is spoken and shown as a title;
4-8 s the identity line; 8-20 s the map; then the lead story. On screen from
4 s to the first chapter card there was nothing but the scene picture.

**Shipped: the "Coming up" card** (`engine/long_form_cards.py`,
`engine.video._long_form_overlays_stage`). The map sentence is split at its
list commas and "then" into items, taken from the `*_reader.txt` display
copy (so "SpaceX" and "xAI", never the TTS respellings "Space X" and
"ex A I"), each line appearing as it is spoken, timed by the same Whisper
locator the hook Short uses to cut the map. A card is shown whole or not at
all: 2-6 items, none narrating the host's own moves ("we screen ..."), no
lowercase one-word fragments, each within `engine.titles.RUNDOWN_ITEM_MAX`.
Replay on the 235 episodes since Oct 20 with a map: 181 get a card.
SpaceX Ep154 renders:

> COMING UP
> Heat-shield data from the latest orbital reentry
> Jet generators in Mississippi
> The Counterpoint and an engineering deep dive

**Shipped: the long-form subscribe pill.** The same red "Subscribe · <cadence>
episodes" pill the Shorts carry since Oct 25, top-right under the site pill,
for 8 s at 45 s and at the midpoint (one window under 3 minutes, none in the
last 30 s where the outro card asks). Long-forms convert at ~1.4 subscribers
per 1,000 views and the outro card is reached by under a tenth of viewers.

Both are `youtube.long_form_rundown_card` / `long_form_subscribe_pill`
(dataclass off, `_defaults.yaml` on); the dub long-forms pass neither and are
the control. Register `long-form-rundown-subscribe-2026-11-08`, readout Nov 29.

## 3. X

Every @nerranetwork clip post since Oct 10 was the YouTube Short as uploaded:
a red YouTube "Subscribe" pill from 3 s and a SUBSCRIBE / "Never miss an
episode" end card, asking for a button X does not have (open since the Oct
24 review). **Shipped:** the X copy is re-rendered from the same inputs
without either (`run_show._render_x_clean_clip`); a failure posts the YouTube
copy as before. Metric `x_clip_variant`. Register
`x-clip-without-youtube-asks-2026-11-08`.

Not measurable yet: there is no read-back of X impressions
(`api/x_posts.json` was never built), and the account has been API-locked
since Nov 7, so X growth cannot be scored from the repo today.

## 4. Open, not shipped here

- **End screens and the RSS copies** (Studio): the single largest suggested-
  traffic lever, and the 302 duplicate long-forms. Operator.
- **The long-form link under the X post** (the Oct 24 cost decision: about
  $24 a month for the four YouTube flagships). Operator.
- **An X metrics read-back** once the account is unlocked: public metrics on
  the queued posts, nightly, to `api/x_posts.json`, null when unread.
- **Content seen while reading chapters:** SpaceX Ep154's chapters include a
  "Cursor Rules Linter: 12 Steps, 75 Min" item from shattered.io — off-topic
  for the show and now a seek-bar chapter and an on-screen chapter card. An
  editorial item for the SpaceX review, not a render fix.
