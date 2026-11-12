# First Principles Daily and Unintended Consequences: review and changes (Nov 12 2026)

Operator-directed. The review (Nov 11) read First Principles Ep149-158 and
Unintended Consequences Ep161-170 with their digests, scripts, claims
sidecars, metrics, queues and prompts. The operator approved the ranked
proposals on Nov 12 and asked for the "Idiot Index" to be renamed because it
reads as harsh. This file records what was found, what shipped and what was
left alone.

## What the record showed

**First Principles, subject drift.** The restock prompt asked for opportunity
topics a listener "has personally paid the markup" on, and banned every
near-neighbour of the growing list. The only space left was retail and venue
pricing. Bottled water was told three times (Ep76, Ep154, Ep156) and sixteen
pending topics were rentals and counters (gym padlock, coat check, hotel
mini bar, stadium beer). Those are market-power stories: the ratio of price
to material explains nothing about them, and the show had stopped being
about engineering.

**First Principles, the tool was rarely computed.** One to three ledger
claims an episode; the floor and the ratio were asserted, hedged with the
same two qualifiers, and not built from sourced inputs.

**First Principles, the concrete arm was history.** Twelve of the last
fifteen concrete examples were before 1950.

**Unintended Consequences, cases without people.** The cases are good and
real, but Ep170 names nobody; findings arrive as "a study found".

**Unintended Consequences, repeats.** Philippine land reform aired as Ep148
and Ep164. Mexico City's driving restriction aired as Ep166 with a second
entry still queued; the cane toad was queued a third time; FOSTA twice. The
restock deduplicated on title strings only.

**Both, length the sources could not carry.** The brief prompts asked for
sentence ranges that add up to roughly 650-1,000 words and a word target of
1,500-2,200. The digest expansion retry fired on every episode, and the
script prompts then asked for 1,800-2,800 spoken words. Script fact-free
share: 78-91% on First Principles, 64-83% on Unintended Consequences. The
daily audit flagged Repetitive on 7 of 7 and 4 of 7.

**Both, the map gave away the turn.** The Oct 20 map sentence after the
identity line is right for a news show. On a one-story narrative it told the
listener the consequence before the story reached it.

## What shipped

1. **The name.** The tool is the "First Principles Ratio": the finished
   price divided by the raw-material floor, "a measurement, never a
   verdict". Renamed in the prompts, the show YAML (description, keywords,
   chapter marker), the cold-open framing, the show page copy, the topic
   hub keywords and every unproduced queue brief. The copy no longer says
   anyone coined the term. Not renamed: SpaceX's prompts (the term is the
   subject's own there), published episodes and feeds, and the books.
2. **The First Principles queue.** Sixteen venue and rental topics and six
   weak or repeated concrete topics were removed. Twenty opportunity topics
   about things that are designed and made (elevators, MRI scans, dialysis,
   chip fabs, shipbuilding, offshore wind, a highway mile, an artificial
   hip and others) and fourteen concrete examples from the last fifty years
   (lidar, lab-grown diamonds, the Starlink dish, gigacasting, the CubeSat,
   Aravind, M-Pesa, oral rehydration and others) were added by hand, with no
   figures in the briefs. Runway: 57 topics, about eight weeks.
3. **The Unintended Consequences queue.** Six unproduced duplicates of told
   stories were retired. Runway: 31 topics, 4.4 weeks, above the alarm.
4. **The restock.** The First Principles restock prompt now defines an
   opportunity as something designed and made, with a named attempt to
   rebuild it, and excludes venue prices, rentals and brand markups. One
   concrete example in three is after 1980. Both restock prompts say a new
   angle on a told case is a repeat. `scripts/restock_topic_queues.py`
   gained `story_too_similar`: a candidate whose distinctive title words
   overlap an entry's title words and brief names is rejected. Replayed on
   the committed queues it flags fifteen entries, among them the Montreal
   Protocol, Nile perch, No Child Left Behind and rotary kiln retellings. It
   does not catch a retelling whose title shares no word with the first
   (the second Mexico City entry), which is why the prompt carries the rule
   too.
5. **Length.** Brief sentence ranges and word guidance now agree (about
   1,000-1,300 words when the sources are rich). `min_digest_words` 1,200 to
   900 on both shows, so the expansion retry is a thin-pass rescue again.
   The script prompts say the brief sets the length (at most about one and a
   third times the brief). `min_podcast_words` 1,400 to 1,200 (First
   Principles) and 1,300 to 1,100 (Unintended Consequences), with
   `min_podcast_publish_words` pinned at the old skip lines (840 and 780).
   The fact floor (`llm.min_digest_facts`) is switched off for narrative
   shows in code, so it was not used.
6. **The numbers.** The First Principles brief has a block, THE NUMBERS,
   that builds the floor from two to five sourced inputs, puts each in the
   claims ledger, gives a range where a source is missing and accounts for
   the gap. The stock qualifiers are described by shape and no longer
   quoted in any prompt.
7. **People.** Both shows' prompts require the people the sources name, by
   full name and role, and the script keeps them. The one research search
   (`engine.fetcher.fetch_topic_research_articles`) now asks, in the same
   call, for a source that names the people and, for a cost topic, one that
   carries prices and quantities.
8. **No map.** `engine.intros.build_cold_open_spec(narrative=True)` states
   that the show has no map and the story simply begins. News shows are
   unchanged.
9. **Removed from the prompts:** the quoted "ideal narrative tone" passage
   in the Unintended Consequences script prompt (a seeded specimen), the
   four quoted cross-promo sentences in the First Principles script prompt
   (the block now describes the sentence, as the network guard requires a
   block to exist), and the per-segment minute targets.

## Left alone, on purpose

- **The closing block's asks.** It is assembled network-wide with two
  experiments still reading; one ask at the close is a network decision.
- **The brief's model.** A grok-4.7 trial on the brief follows the model
  upgrade playbook and is its own change.
- **Lints for "names a person" and "computes the ratio".** The prompt and
  research route goes first; a lint is worth building once a week of
  episodes shows whether it is still needed.
- **Cadence and the French track.** Operator decisions.

## Predictions (scored at the next review of either show)

| Metric | Baseline | Expected by Nov 26 |
|---|---|---|
| `digest_expansion_fired` share, both shows | 7 of 7 | at most 3 of 7 |
| Script fact-free share (script audit), median | FPD 0.84, UC 0.72 | FPD at most 0.65, UC at most 0.55 |
| Daily audit Repetitive flags per 7 episodes | FPD 7, UC 4 | FPD at most 3, UC at most 2 |
| Claims ledger entries per episode, First Principles | 1-3 | at least 5 |
| First Principles opportunity episodes on a venue, rental or brand price | 6 of the last 10 | 0 |
| Unintended Consequences episodes naming at least two people | 3 of 10 | at least 8 of 10 |
| Episodes skipped for length | 0 | 0 |

Every prompt change here is an audio change. Each show is rehearsed on the
branch and listened to before the merge.
