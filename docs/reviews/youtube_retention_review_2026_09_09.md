# YouTube retention review — Grok's plan checked against the data — 2026-09-09

Operator brief: "I had grok review the pipeline … review and make a plan to
execute any of the suggestions that are of value and improve Nerra Network
and the audience growth and subscription numbers."

Method: every numeric claim in the Grok review was recomputed from the
committed instruments (`api/youtube_stats.json` 30-day window, generated
2026-09-08; `api/funnel.json` 28-day; `api/youtube_policy.json`;
`api/gallery_retention.json`) before any item was accepted. Items are
scored on three things: does the data support the diagnosis, is the change
inside the rules that bind (render/metadata only; audio and prompts are
landmine-#17 A/B; distribution changes are an operator decision), and can
the outcome be read from an existing metric.

## What the data says (2026-09-08 snapshot)

| Claim in the Grok review | Recomputed | Verdict |
|---|---|---|
| RU is ~60% of views | RU 65% / EN 29% / FR 6% of 245,754 views | supported |
| "143k views → 8 site sessions" | 246k views/28d → 151 sessions, 8 attributed (`reach_to_click_pct` 0.006) | supported in shape; the number differs but the conclusion is the same: the off-platform funnel is ~0 |
| Shorts drive subscribers | EN long 106 subs / 540 videos (0.20 per video); EN hook Short 59 / 375 (0.16); RU hook Short 62 / 156 (0.40); RU filled 42 / 221 (0.19); EN filled 4 / 101 (0.04) | supported for RU; on EN the LONG is still the best per-video subscriber source |
| Keep fill-to-requested | EN `filled` Shorts: median 3 views, 0.04 subs/video → `en-shorts-no-fill` shipped 09-09. RU filled Shorts earn 0.19 subs/video → RU fill stays | rejected for EN, kept for RU |
| gallery_retention tags show which imagery retains | `api/gallery_retention.json` has zero top/bottom tags on every show (min-3-video threshold never met) | unsupported — no data |
| env_intel / FPD / UC / FP are dead weight | 14-day views per upload: env_intel 10, finansy_prosto 6, MIT-RU 10, MIT-FR 6, UC 15, privet_russian 27, **first_principles 34** (827 views from 24 Shorts — more per upload than Omni View at 25) | partly wrong: FPD is not dead. The genuinely dead uploads are env_intel, finansy_prosto and the MIT RU/FR dubs |
| Long-form open cliff | `long_open_hold_5pct_en` 0.48 (baseline 0.51); EN long median AVP 13.3%, median view duration 70 s, median 41 views | supported — long-form is the weakest surface and the largest EN subscriber source at once |
| `youtube.long_form_max_seconds` | no such knob exists anywhere in the pipeline | the "90–120 s lead cut" is a new format, not a setting |

Two more facts that shape the plan: EN Shorts earned 22 subscribers from
198 uploads in 14 days (0.11 per Short), and the 14-day EN long-form
picture is Tesla 3,420 / MAB 2,603 / SpaceX 2,083 / M&A 1,749 views — the
long is not a dead format, it is an under-retained one.

## Decisions

### Shipped in this PR (render/metadata only — outside landmine #17)

1. **Subscribe CTA on every Shorts end card (Grok 1B, adapted).**
   `WATCH FULL EPISODE / Tap Subscribe ↗` → **`SUBSCRIBE / Never miss an
   episode ↓`**, localized on the dub paths (RU `ПОДПИШИСЬ / Не пропусти
   новый выпуск ↓`, FR `ABONNEZ-VOUS / Ne manquez aucun épisode ↓`) and in
   the two native-RU show YAMLs. The old headline asked for a surface the
   burned-in card cannot link (the long-form URL lives in the comment and
   description) and the site funnel it fed is measured at ~0; the
   subscribe is the operator's stated goal and YouTube reports it per
   video. The end card also gained shrink-to-fit on the headline — an
   18-character headline at 88 px ran off both edges of the 1080 px card,
   which means `WATCH FULL EPISODE` had been clipped since May. The
   site-showcase strip on the card and the long-form outro card (operator-
   directed, Aug 2026) are **kept** — Grok's suggestion to drop the site
   outro is not taken without an operator decision. Metric:
   `short_subs_per_video_14d_en` (new; baseline 0.11). Register:
   `shorts-subscribe-cta`.
2. **The opening slot of every long-form is this episode's imagery
   (Grok 1D, long-form half).** `scene_scheduler._pick_scene` scores one
   token of title overlap above the 0.25 fresh bonus, so a library scene
   from an older episode could open the video. The first slot now draws
   from the fresh pool only; later slots keep overlap-first. Shorts already
   open on a fresh scene (`short_visual_extras` orders fresh first, ranked
   against the window text since Sep 2). Metric: `long_open_hold_5pct_en`
   (baseline 0.48). Register: `fresh-open-long-form`.
3. **Fact cards on long-form (Grok 1A).** New `engine/fact_cards.py`:
   the spoken figures ($, %, million/billion/thousand, counts ≥ 100) become
   timed on-screen cards (figure 72 px in Nerra cyan, a ≤36-character label
   from the sentence, lower-left, 4 s, ≤8 per episode, ≥40 s apart, clear
   of the hook window and chapter cards) driven by the Whisper word
   transcript the pipeline already has. Whisper writes spoken figures as
   digits split across tokens (`$368` `.16,` / `4` `,000`), so runs are
   merged first; tokens with letters (`V3`, `B1081`, `1990s`) and the
   episode number are never figures. On Tesla Ep600 the cards are
   `v14.3.9 — Introduces automatic collision` and `$368.16 — Up $14.08 or
   4%`; on SpaceX Ep095 `$450 million — In a round backed by new` and
   `$220 — Target`. Labels are heuristic and sometimes clumsy; the figure
   is the card. Per-show gate `youtube.fact_cards_enabled` — **on for
   tesla, spacex, fascinating_frontiers; M&A, MAB, OV are the control arm.**
   Metric: `long_form_median_avp_en_14d` (baseline 12.6), read per show
   against the control. Register: `long-form-fact-cards`.

### Not taken, with the reason

- **Grok 1C — replace the long-form with a 90–120 s "lead cut".** The
  long-form is the Apple video-podcast asset for Tesla and SpaceX, carries
  the chapter track and the outro, and is the largest EN subscriber source
  per video. Replacing it trades a known surface for an unmeasured one; the
  knob Grok names does not exist. If the open-cliff and fact-card readouts
  (09-30) do not move long-form retention, the next experiment is an
  ADDITIONAL 16:9 lead-story cut on one show with its own `kind` in the
  video index — never a replacement.
- **Grok 1E — pause YouTube on env_intel / FPD / UC / FP.** FPD is the
  wrong target (34 views per Short, above Omni View). The dead uploads are
  env_intel (10/video), finansy_prosto (6), and MIT's RU/FR dubs (10 / 6).
  Quota is not the constraint (200k) and the policy already holds each at
  one Short; the only real cost is daily-cadence dilution on
  @NerraNetwork (~24 uploads/day against the 30/day safe line). This is a
  distribution decision for the operator: one line per show
  (`youtube.enabled: false` for env_intel; `youtube.dub_languages: []` +
  `ru_dub_enabled: false` on modern_investing; finansy_prosto is Monday-only
  and costs one upload a week). Not done here.
- **Grok "keep fill-to-requested".** Contradicted by the EN numbers above;
  `en-shorts-no-fill` stands. RU keeps fill.
- **Any spoken-open or prompt change** (Grok's "do not do without a
  spoken-open A/B" list) — correct, and not done; landmine #17.
- **Wave 2 identity/habit items** are Studio work the API cannot do:
  flag the podcast playlists (landmine #15), a channel trailer, pin the
  auto-posted comment (the API cannot pin), consistent slots (already
  staggered per channel). Operator checklist, not code.
- **Wave 3 code quality** — no audience effect; not this PR.

## How to read it (2026-09-30 readout)

| Experiment | Metric | Baseline 09-08 | Hit |
|---|---|---|---|
| shorts-subscribe-cta | `short_subs_per_video_14d_en` | 0.11 | ≥ 0.16 (the hook Short's 30-day rate) with EN Short views/video not down |
| fresh-open-long-form | `long_open_hold_5pct_en` | 0.48 | ≥ 0.52 |
| long-form-fact-cards | `long_form_median_avp_en_14d`, per show vs control | 12.6 (tesla/spacex/FF vs M&A/MAB/OV) | treatment shows ≥ +2 points over control; `fact_cards_rendered` ≥ 3 on most episodes |

A miss on the fact cards is a one-line revert per show (`fact_cards_enabled:
false`). A miss on the CTA is a text change back in `_defaults.yaml` and
the two dub modules. The fresh-open rule has no downside case worth
reverting for.
