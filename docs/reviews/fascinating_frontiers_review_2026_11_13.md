# Fascinating Frontiers — end-to-end review (2026-11-13)

Operator ask (Nov 13): make Fascinating Frontiers the best show on its topic,
one a newcomer would recommend. Read: the 22 daily audits Ep230-251 (from
`api/daily-review.json` history), every digest, script and claims ledger
Ep231-251, `metrics_ep*.json`, the Nov 8 feed audit, the feed and YouTube
records, both prompts, and the Nov 8 Grok review and ledger.

## What a listener got

Downloads slid 202, 142, 157, 129 over the four OP3 weeks to Nov 11
(`engine/op3_weeks.py`); YouTube held. The audit scored 6.3 on average and
flagged FACTUAL_ERRORS on 12 of 22 episodes (Ep230-251) and REPETITIVE on 12 of the last
14. Ep251, read whole, is a fair picture of the show this month:

- the lead (white-dwarf pairs and LISA) was the previous day's lead too, and
  it was told three times in one episode: hook, item 6, and again as the
  Cosmic Deep Dive;
- the Cosmic Spotlight was an August eclipse photo from a picture-of-the-day
  page, which also ran as an Also Today line;
- items included NASA's APOD caption, a student profile, an NBC video page
  with no text, a Senate hearing with no nominee named, and a Global Times
  piece; the Also Today run carried a Reddit astrophoto.

## Root causes, with evidence

**1. Most factual errors were written by the deep dive's brief.** The digest
prompt asked the Cosmic Deep Dive to "open with a jaw-dropping scale
comparison", map a cosmic number onto an everyday object, and "include at
least one specific, surprising number", while calling the section a
"licensed-knowledge length lever". The audit's errors trace there: Ep238's
tidal gradient "a factor of thousands" (it is a tiny fraction), Ep248's dwarf
galaxy "thousands of times" a coast-to-coast run (about a trillion), Ep235's
magnetosphere scale, plus history from memory (Ep234's Iapetus telescope,
Ep237's NEEMO length). The digest's `.md` carries each one before the script
does, so the sources were not the problem.

**2. The word-floor retry padded every episode.** `digest_expansion_fired`
on 9 of 9 episodes Ep243-251; it roughly doubled thin digests (Ep250 815 →
1,653 words) and its word branch tells the model to lengthen the deep dive
first "in general terms". The deep dive then carried 55-76% of a body item's
vocabulary on 7 of 9 days (`deep_dive_contains_body_item`), the same story
told twice.

**3. The script was asked for 1,900-2,200 words from a 1,200-1,600-word
digest.** It wrote 1,184-1,771 and restated to get there: the REPETITIVE
flags quote restatements inside one story.

**4. Sourcing.** In Ep231-251 reddit.com was the second most cited source
(36 Source lines, behind phys.org's 51); x.com 9, YouTube 2, plus content
farms and press wires through Google News. The Nov 8 feed audit had all three
ESA feeds at 404, Sky & Telescope at 403 every week and science.nasa.gov/feed
returning zero entries, so the agencies a space show is judged by were barely
read. JPL, ESO, ESA/Webb, ESA/Hubble and AAS Nova were not on the list.

**5. Titles.** The hook spec allowed 120 characters; the feed title is
`Ep N: <hook>` under 100, so 6 of the last 8 feed titles end mid-sentence.

The Spica "triple" claim the Ep251 audit doubted is in NASA's own caption
("earlier this year it was reported ... a triple system"), so that flag was
the auditor's memory, not the show's.

## Shipped (draft PR)

| Change | Where | Listen? |
|---|---|---|
| Feed list rebuilt: dead and Reddit feeds out; JPL, ESO, ESA/Webb, ESA/Hubble, AAS Nova, Planetary Society, ScienceDaily space, NASASpaceflight, Ars space in | `shows/fascinating_frontiers.yaml` | no |
| `exclude_sources`: Reddit, YouTube, press wires, content farms, Global Times | same | no |
| Picture-of-the-day pages dropped (APOD, "picture/photo/image of the day", "night sky highlights", and the `/picture-of-the-day/` URL path network-wide; only FF has ever cited one) | same; `engine/utils.py` | no |
| `hook_repeats_past_lead` lint: fires 1 in 52 replayed digests, exactly Ep251 | same | no |
| `min_digest_facts: 18` (joins Planetterrian's fact floor): the retry adds sourced facts, never deep-dive prose | same | ⚠️ |
| Deep dive: comparisons only as stated arithmetic on two given figures, units as given, no history from memory, its article never also a Top item; the scale-comparison seed and length-lever lines removed | digest prompt | ⚠️ |
| "One telling per story": deep dive and Spotlight chosen first and kept out of the list | digest prompt | ⚠️ |
| Script: no word target (the digest's facts told once), "accuracy on air" rules (no unit conversion, no ratios, no merged dates), the quotable Artemis example removed, section names never spoken | podcast prompt | ⚠️ |
| `min_podcast_words` 1,700 → 1,400 (the below-target line); skip floor pinned at 850 | YAML | no |
| Hook under 90 characters so the feed and video title carry it whole | digest prompt | ⚠️ |

Run "Run show" with `rehearse: true` for one episode and listen before
merging (landmine #17). Thin days will ship shorter and denser.

## Not shipped, and why

- `deep_dive_distinct` (the firing form): FF's structural-regen share is
  about 0.29, over the 0.22 ceiling the rule requires. The fact floor removes
  the retry that grew the deep dive; read `deep_dive_contains_body_item` for
  a week, then decide.
- `item_figures_sourced`: right idea, but the fetched articles of past runs
  are not committed, so it cannot be replayed to see how often it would fire.
- Tomorrow Teaser chapter pattern (Nov 8 proposal A): metadata only, lower
  value than the above; left for the next pass.
- Video: no change. The long-form and Shorts are built from the same hook
  and script, so they inherit every fix here. Long-form views at day 3 run
  9.5 against the channel's 18 (`api/youtube_policy.json`); revisit once the
  content changes have run two weeks.

## Predictions (scored by the next review)

Over the first 14 audited episodes after merge:
1. FACTUAL_ERRORS on at most 3 (was 12 of 22).
2. REPETITIVE on at most 6 (was 12 of 14).
3. No reddit.com Source line.
4. `digest_expansion_fired` on at most 5 of 14 (was 9 of 9).
5. `deep_dive_contains_body_item` median under 0.5 (was 0.58 over Ep243-251).

Register: `ff-review-2026-11-13`; guards
`tests/test_fascinating_frontiers_review_2026_11_13.py`.
