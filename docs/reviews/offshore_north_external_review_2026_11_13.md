# Offshore North — an external review's five suggestions, judged (Nov 13 2026)

Register `offshore-north-external-review-2026-11-13` (readout Dec 14); guards
`tests/test_offshore_north_external_review_2026_11_13.py`; ledger
`docs/reviews/ledger/offshore_north.yaml`.

Patrick relayed five suggestions from an external review. Each was checked
against the prompts, `shows/offshore_north.yaml` and the committed Ep010-013
(Oct 19 - Nov 9), and against what the Nov 8 Ep012 pass already changed.

## What Ep013 showed

- **Running order.** The Canadian Boat led every episode by rule (450-650
  words in the brief) while EMIRA IV sat alongside in Gosport. Ep011 led on
  the 23 October RORC Transatlantic announcement; Ep012 and Ep013 told it
  again. Ep013 filled the rest of the segment with the Notice of Race rules.
- **Ranking.** Ep013's Fleet told the Ultim podium and Alexia Barrier's torn
  mainsail, and left out the IMOCA race its own sources reported (podium
  settled, a course record in view) — the class the show exists for.
- **Repetition.** Plain Sailing re-told the Canadian Boat's qualification
  paragraph (43% of its salient words); Laperche's record was said three
  times. Ep012 opened Plain Sailing on Ep006's sentence word for word while
  Ep006 sat in the "already aired" list the prompt shows.
- **Times.** "on 8 November at 1430 local time" — no place, no colon.
- Scripts ran 980-1,034 words for four weeks against a 1,400-1,800 target;
  the 1,300-word digest floor fired on Ep013 (908 → 1,144 words) and its
  padding is where the repeats came from.

## The five suggestions

| # | Suggestion | Verdict | What shipped |
|---|---|---|---|
| 1 | Lead with the week's biggest story, ranked across all offshore racing; never lead with something already covered | **Partly in place, extended.** The hook already had to be this week's news and `hook_repeats_past_lead` gates past leads, but the Canadian Boat ran first by rule. | RANK THE WEEK FIRST (all classes, IMOCA wins a tie); The Fleet runs first in rank order; a covered story enters only as a new dated development. |
| 2 | Every race fact against a dated source; local time with the date; no source, leave it out | **Mostly in place** (claims gate, ten-day staleness, race-state check, sourced figures). Missing: the date on each incident and a rule for clock times. | EVERY RACE FACT IS DATED: finish, stop, retirement, damage, rescue with the date it happened; a clock time as hours:minutes with the place whose time it is and the date, else left out. |
| 3 | Each story its own why-it-matters; the Canadian boat only on a real connection | **Already in place** ("why it matters" on every item since August; "Canadian relevance is a bonus"). | Tightened wording: an item's OWN consequence, two items never share one, the Canadian boat named in a Fleet item only on a stated connection. |
| 4 | A Canadian boat segment every week, short and dated; when nothing happened, say so in one line | **Suitable with one change.** The show cannot tell an empty week from one it could not see, and the Sep 18 absence ban exists because Ep002-005 said "nothing" while the team's own post said where the boat was going. | Short (100-220 words in the brief) and every week; first only when the campaign has the week's biggest story. A quiet week is the position report plus ONE dated sentence on the team's newest post — a fact, never "nothing happened". |
| 5 | Tell each story once, end on a hook; Plain Sailing new each week; close on one story to watch | **Partly in place** (zero-overlap rule, past-explainer list), and failing in the text (Ep012, Ep013). | `explainer_distinct` lint (below); Plain Sailing never re-tells another section; the countdown ends on ONE dated event in the coming week from a fetched article — a calendar fact, never a promise of coverage. |

The review's closing line offered to brief Mira with these and to announce
Ocean Race coverage. Mira is the network's interview host, not this show's,
so nothing was drafted to her and nothing was announced.

## `explainer_distinct`

Two checks on the `## Plain Sailing` section, one finding, riding the
existing one-shot structural regeneration:

- **Within the episode:** the share of any other section's paragraph that the
  explainer's salient vocabulary carries; fires at 0.4. Replay on Ep001-013:
  fires on Ep001/003/004/005 (the early recaps the Sep 18 round-1 fixes
  named) and Ep013; Ep006-012 max 0.28.
- **Across episodes:** the opening sentence against the last 12 openings;
  fires when 80% of the shorter opening's salient words and at least six are
  shared. Fires on Ep012 only (1.0 against Ep006; next highest 0.5). A
  whole-body overlap does not separate a paraphrased repeat from a
  neighbour on this show (repeats 0.27-0.54, distinct explainers up to 0.32),
  so this half catches the copy, not the paraphrase.

## Not changed

- The 1,400-1,800 word target and the 1,300-word digest floor. A shorter
  Canadian segment and 3-5 Fleet items should give the brief real material;
  if the floor keeps firing, lowering it is the next lever (Patrick's call).
- Distribution: the near-zero downloads are the Apple draft and the missing
  Podcast Index listing (`docs/outstanding.md`), not content.
- The digest model (grok-4.3).
