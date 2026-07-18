# Omni View — editorial realignment (2026-07-18)

Operator-directed repositioning: "a great daily news program from top news
around the world … balanced perspective versus the general news clickbait and
sensationalism … teenagers all the way up to seniors … informative and
encouraging … seeking out other perspectives." Operator decisions confirmed
before implementation: replace the gossip/popular-media slots with a daily
progress story (+ culture only when genuinely significant), remove the Daily
Mail entirely, update the public branding, and keep the 11-13-minute envelope
with 6-8 deeper stories.

## Evidence (Ep105-114 window)

- The digest prompt MANDATED 12 slots including daily "Top popular media
  stories (1)" and "Top gossip stories (1)" — structurally forcing tabloid
  filler (Rita Ora's premiere dress, the etymology of "gossip", a sheikh's
  60-car convoy, avocado-oil adulteration) into every episode. Two episodes
  LED with tabloid items (Ep111: Ibiza waterslide death + Yellowstone bison
  attack; Ep112: Sam Neill's death).
- ~12 stories × ~115-150 words each = a skim, and the root cause of the
  chronic under-length (Ep114 shipped 1,177 words against a 1,400 floor).
- Balance was simulated by a formula: the "Both sides agree / Both accept /
  Both recognize" family appeared ~38× across 10 episodes, including on
  non-controversies ("Both sides agree the death was accidental" — a
  waterslide accident; organizers-vs-attendees "sides" on a red-carpet
  dress). Named two-outlet attribution was rare; the literal Steel Man
  device shipped 0×.
- The Daily Mail was the single most-cited outlet (10×/10 eps, framing hard
  news); Reuters, AP, AFP, NYT, FT: 0×. Heavy UK skew (3-6 UK items/ep);
  LatAm/Africa/Asia domestic politics thin.
- The podcast prompt's own EXAMPLE story seeded the two dominant tics
  ("What is interesting is…", "The question worth considering:" — 23×/10
  eps); the system prompt seeded two more that the podcast prompt bans.
- Strengths preserved: sober consequence-led hooks/titles, the
  "Understanding the Issue" media-literacy deep dive, the "read more than
  one perspective" outro coaching, the cross-spectrum source concept.

## Shipped

1. **7-slot architecture** (digest + podcast prompts): Today's lead story
   (1) + Major world stories (3) + Economy, science & technology (2) +
   Progress watch (1) + Understanding the Issue + media-literacy note.
   Gossip/popular-media slots deleted; culture allowed only on a
   significance bar. Lead importance test (year test / scale /
   development), anti-tabloid bar, celebrity-death policy, geographic
   breadth rule (≥3 regions, ≤2 stories/country, UK ≤1), per-story depth
   targets (digest ~1,700-2,100w — the under-length fix at its root).
2. **Balance mechanics 2.0**: ≥2 named outlets per lead/world story;
   steel-man CONDITIONAL (2-3 genuinely contested stories, named
   advocates); NO sides framing on disasters/accidents/deaths/science/
   culture (context + "what happens next" instead); questions ≤2 per
   episode, forward-looking; "the question worth considering" banned; the
   tic-seeding EXAMPLE story rewritten; system-prompt seeded tics removed.
3. **Accessibility**: teen-to-senior comprehension target in every prompt;
   define-every-institution-in-one-clause rule; the podcast AUDIENCE
   contradiction fixed.
4. **Encouraging without false positivity**: Progress watch segment with a
   rigor bar (named actors, ≥1 number, complication acknowledged; skip to
   a 4th world story when nothing clears it); response-and-agency sentence
   after heavy stories; calibrating historical context in the deep dive;
   new closing pool pairing perspective coaching with one encouraging
   line; a per-episode "go deeper: compare outlet A vs outlet B" pointer.
5. **Sources**: Daily Mail, duplicate-BBC, and r/news removed; added
   Reuters + AP (Google News site: proxies — no public RSS exists), WSJ
   World, BBC Africa/Asia/Latin America, AllAfrica, SCMP, Nikkei Asia,
   The Hindu International, Japan Times, MercoPress (live-verified:
   10/12 delivering on fetch day; Reuters proxy 50 articles at 72h).
   Conservative celebrity/tabloid `exclude_title_patterns` added
   (live-verified zero false drops). Regional web-search queries replace
   "breaking news today". `crime` dropped from keywords.
6. **Engine**: `podcast_expansion_style: deepen` (new LLMConfig field +
   generator flavor) — the default "cover more stories" retry would fight
   the fixed slate; OV now expands by deepening existing stories.
   `digest_expand_below_target: true` + `min_digest_words: 1500`.
   `ov_validation_config` + `OV_SECTION_PATTERNS` updated to the new
   headers (the old validation pattern would have fired a full digest
   regenerate on every episode — the Ep068 class; the tracker pattern was
   already stale). Progress Watch chapter marker added (anchored on three
   seeded transitions).
7. **Positioning**: rss_description, page about/audience/meta copy updated
   to the broader identity (tagline "See every side. Decide for yourself."
   kept — the DNA is unchanged); source_highlights now lists outlets
   actually subscribed; weekly newsletter prompt gains "Progress This
   Week" + plain-language + no-sides-on-tragedy rules.

Drift guards: `tests/test_omni_view_quality_pass.py::TestEditorialRealignmentJuly18`
(21 tests — slate shape, bans, sources, engine flavor, closing-marker
compatibility, post-Ep115 transcript tic ceilings), updated
`tests/test_validation.py` (new-format digest validates; missing sections
still flag), `tests/test_config.py` source count, duplicate-feed allowance
removed from `tests/test_network_quality_pass.py`.

## A/B (landmine #17)

Every prompt, the closing pool, the source list, and the retry flavor
change shipped audio. No API key was available in the implementation
environment, so the A/B legs are: **before** = Ep114 (2026-07-16, on
disk); **after** = the first post-merge episode. Listen for: hook style
(consequence-led, not drama), story depth (~2 min each), named two-outlet
attribution, NO "Both sides agree"/"the question worth considering",
Progress watch tone (rigorous, not saccharine), jargon defined in-flow,
the new closing warmth, the go-deeper pointer. Revert per segment via git
if quality dips; the Progress Watch chapter marker is the dead-marker
risk to watch (broaden the pattern if the LLM rewrites the transitions).

## Predictions (next review must score)

| metric | baseline (Ep105-114) | expected (Ep115+) |
|---|---|---|
| tabloid/gossip/celebrity items per episode | 2+ (structural) | 0 |
| "Both sides agree" family per 10 episodes | ~38 | 0-2 |
| "the question worth considering" per 10 episodes | 23 | 0 |
| median `_tts.txt` words | <1,600 | ≥1,700 |
| Daily Mail citations per 10 episodes | 10 | 0 |
| distinct regions per episode (lead+world) | often 1-2 | ≥3 |
| UK items per episode | 3-6 | ≤2 |
| episodes with a Progress Watch chapter | 0 | ≥8/10 |
