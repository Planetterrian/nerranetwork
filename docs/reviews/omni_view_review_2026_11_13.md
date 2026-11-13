# Omni View review — November 13, 2026

Operator ask (Patrick, Nov 13): a thorough review of Omni View and dramatic
improvements to the show, its content and the videos that go with it.
Scope: the main show (`shows/omni_view.yaml`, Patrick's voice). The five
members-only desks and Top World are read only as the comparison.

## The numbers that framed it

| | Omni View (main) | Top World (sibling, same day's news) |
|---|---|---|
| Daily audit, last 14 | mean 5.7, Repetitive 12/14, Incoherent on Ep233-234 | 8 on Ep051 |
| Script fact-free sentences (Ep226-234) | 39-68%, median 53% | 10-43%, median 19% (Ep043-051) |
| Digest expansion retry | 9 of 9 episodes (drafts 944-1,216 w vs a 1,500 floor) | 4 of 9 |
| Full text read | 8-12 of 60 prompt articles | 12-23 |
| Digest model | grok-4.3 (script grok-4.6, two-pass) | grok-4.7 low, combined |
| OP3 downloads | 123 in the 7 days to Nov 11 (329 / 104 / 142 / 123 by window) | |
| YouTube | long 3.1 views/day; Shorts on the weekly probe since Nov 12 (hook Short d3 median 3) | (YouTube off) |

## What a listener heard (Ep234, Nov 12)

The lead was Starshield speed caps; then a single-source Ebola paragraph, a
Pakistan ambush, a Bundeswehr study, a Hong Kong industry body's AI guide, a
Reuters column about public funds and AI, and a UK envoy appointment as
"progress". Nearly every story closed on a next step no article named
("Health authorities will monitor…", "Local authorities will investigate…",
"The ministry will review…", "Companies will be encouraged…") and carried a
sentence about the coverage rather than the event ("The coverage centers
on…", "the event is presented as…"). The deep dive re-told the lead; the
teaser re-told a fact from the lead. Top World the same morning told
Ethiopia's conscription drive, the Nasser Hospital strike, the European
Parliament's vote on deported Ukrainian children and the Mississippi Senate
result, each with names, numbers and quotes.

## Findings

### P1 — the show was steered off the day's biggest stories
1. **The digest prompt told it to "change course"** whenever a sibling had
   told a story (`omni_view_digest.txt`, the CROSS-NETWORK paragraph). Since
   Oct 21 the engine block itself says "cover any of them on their merits"
   (`engine/cross_show.py`); the prompt contradicted it, and with six Omni
   View siblings plus Nerra Daily telling the big stories, the main show was
   pushed to the leftovers: `cross_show_matches` 1-6 a day.
2. **The feed list crowded the newsrooms out.** run_show keeps the 150
   NEWEST of ~430 fetched articles before anything ranks them
   (`run_show.py`, `MAX_RAW_BEFORE_DEDUP`), and relevance is 0 for every RSS
   article except the preferred domains. Bloomberg Markets, Wired, Ars
   Technica and two Reddit feeds publish all day; the Nov 5-12 slates
   carried a Turkish appliance maker, a Nissan strategy note and a Reuters
   fund column, while Spain's first general strike in 14 years went to Also
   Today — three times, once per outlet (Ep233).
3. **"Use ONLY the information in the provided story list (titles + short
   descriptions)"** survived the Sep 24 full-text pass, so the prompt told
   the model it had no text to work from.

### P1 — the writing rules produced filler
4. **"Name each outlet… two or more with genuinely different vantage
   points"** on every lead and world story, when most stories have one
   article, produced sentences about framing ("CNBC presents…", "the
   reports diverge on…").
5. **"What happens next"** became a required closing line, invented when no
   article named one.
6. **The podcast prompt still carried a worked EXAMPLE** (removed network-wide
   Sep 5; it had already bled verbatim into Ep145), **a 1,700-word "must"
   plus "DEEPEN the slate"** (a podcast-side length lever — network
   `do_not_retry`), and quotable cross-promo lines.
7. **The deep dive was fixed to "today's biggest story"**, so it re-told the
   lead (the audit's Repetitive quote on Ep234).
8. **The 1,500-word digest floor fired on every episode** and padded — the
   Nov 3 review's best predictor of a Repetitive flag.

### P2 — surfaces (recommendations, not shipped here)
9. **Podcast-app titles are a clipped spoken hook** ("Ep 234: New speed
   limits on Ukraine's Starshield network are hindering drone interceptions
   as US…") while YouTube gets a written headline ("Starshield Caps Ukraine
   at 161 km/h as Envoys Meet Putin"). Network-wide shape, so it belongs to a
   network pass: the feed title could take the YouTube headline.
10. **Feed descriptions open on "Omni View — Omni‑View Briefing" and
    "Today's lead story (1)"** — the digest's scaffolding in Apple's show
    notes.
11. **Video imagery is AI "documentary photojournalism"** of real events. A
    news show that promises every story is sourced should not show a
    photorealistic picture of an event no camera recorded; an illustrative
    style is the operator's call.
12. **run_show's pre-dedup cap drops X posts and web-search articles** for
    any show fetching over 150 articles (they are appended after the
    newest-first RSS list and sliced off). Shared engine; filed for a network
    pass rather than changed here.

## Shipped in this PR

- **Digest prompt** (`shows/prompts/omni_view_digest.txt`): the big stories
  first, a story several outlets carry outranks one, a sibling's coverage is
  never a reason to skip; NOT A STORY (analysis pieces, guides, appointments,
  market moves); full text named as the source; depth targets are ceilings
  and a story with under four facts goes to Also Today; SENTENCES THAT ARE
  NEVER WRITTEN (coverage-about-coverage, restated headlines, invented next
  steps, "what it means"); a second outlet only when it adds a fact or a
  reading, said aloud; Progress watch a measured result, never an
  appointment, proposal or a story told elsewhere; the deep dive explains
  any of today's stories and never re-tells it; one Also Today item per
  story; `interesting_first` and `hook_supported` included. ⚠️ AUDIO.
- **Podcast prompt** (`shows/prompts/omni_view_podcast.txt`): the worked
  example replaced by a described shape; length follows the briefing's
  facts; NEVER A SENTENCE ABOUT THE COVERAGE; NEVER AN INVENTED NEXT STEP;
  the two-outlet demand and the cross-promo lines removed; chapter anchors
  kept. ⚠️ AUDIO.
- **Config** (`shows/omni_view.yaml`): `min_digest_words` 1500 -> 1000 (the
  audit the ledger's deferred length item asked for: 9 of 9 fired, and the
  padding is the Repetitive predictor); `fetch_full_text: 24` at 4,000
  characters; NYT World, Globe and Mail World and CBC World in (and
  preferred, France 24 leaving the preferred list to hold the cap of 8);
  Bloomberg Markets, Wired, Ars Technica and both Reddit feeds out; Top
  World's live-blog, gallery, quiz and obituary exclusions. The spectrum
  outlets stay. Models are unchanged (digest grok-4.3, script grok-4.6).

## Operator decisions

- **Move Omni View to grok-4.7 like its six siblings.** Top World and the
  five desks run grok-4.7 at low effort on the combined call; that is the
  largest difference left between a 6 and an 8. The staging guard
  (`test_grok_47_migration_2026_09_21::test_no_show_digest_left_the_network_default`)
  forbids an established show pinning its own digest model, so it is the
  operator's call: two lines in the YAML (`model: grok-4.7`,
  `reasoning_effort: low`, and drop `podcast_model`), with the guard's
  arm widened in the same PR. Recommended after one week of these prompts,
  so the two changes read separately.
- **The digest fact floor** (`min_digest_facts`) stays on Planetterrian
  alone until its Nov 17 readout.
- Guards `tests/test_omni_view_review_2026_11_13.py`; register
  `omni-view-review-2026-11-13` (metric `editorial_score_14d_omni_view`,
  readout Nov 27).

## Predictions (scored by the next review)

- Daily audit mean over Nov 14-27 at or above 7.0; Repetitive on at most 4
  of 14 (baseline 12 of 14).
- `digest_expansion_fired` on at most 4 of 14 (baseline 9 of 9).
- Zero scripts closing a story on "will monitor / will review / will
  investigate" (baseline 4 in Ep234).
- Successor tic to watch: with "the coverage presents" banned, the next
  framing shape may become "X says" stacks or "the reporting shows"; the
  next review greps for both.

## Video

Every video surface follows the lead: the long-form title, the thumbnail,
the hook Short and the X clip are all built from the hook. The Shorts are on
the weekly probe because the hook Short's day-3 median is 3 views; a lead
like "EU proposes rules on online shopping traps" was never going to move a
feed. The content change is the video change. Items 9 and 11 above are the
video-side decisions left for the operator.
