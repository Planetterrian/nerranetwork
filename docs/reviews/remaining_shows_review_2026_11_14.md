# The remaining shows and the pipeline — end-to-end review (2026-11-14)

Operator ask (Nov 14): review every show that has not had this month's
end-to-end pass, the way First Principles, Unintended Consequences and
Fascinating Frontiers were reviewed; fix what holds up; and check that the
pipeline is efficient, effective and on the latest tools.

Already reviewed this month and left alone here: Tesla (Nov 11), First
Principles and Unintended Consequences (Nov 12, readout Nov 26), Fascinating
Frontiers (Nov 13, readout Nov 27), Omni View (Nov 13, readout Nov 27), Offshore
North (Nov 13), The Age of AI and Nerra Voices (Nov 11; PR #1710 is live
there). Video, YouTube and X are other threads' work.

Read: the 17 daily audits Oct 29-Nov 13 (every version of
`api/daily-review.json` in that window) and `api/editorial_score_history.json`,
the last 7-14 `metrics_ep*.json` and credit files per show, the latest scripts
and digests, every podcast prompt touched below, `api/op3_stats.json`,
`api/model_trial.json` and the Nov 8 feed audit.

## The network at a glance

Audit = mean of the last 14 daily-audit scores; flags count those 14.
Downloads are OP3, 30 days to Nov 12. Words are the median script against the
show's target over its last 7 episodes.

| Show | Downloads 30d | Audit | Factual | Repetitive | Incoherent | Words / target | Model (digest / script) |
|---|---|---|---|---|---|---|---|
| SpaceX Daily | 5,197 | 6.2 | 9 | 7 | 10 | 1,453 / 1,300 | 4.3 / 4.6 |
| Models & Agents | 1,164 | 6.8 | 4 | 3 | 5 | 1,334 / 1,200 | 4.3 / 4.6 |
| M&A for Beginners | 907 | 6.4 | 0 | 9 | 0 | 1,198 / 1,200 | 4.3 / 4.6 |
| Modern Investing | 738 | 6.6 | 8 | 6 | 3 | 2,075 / 1,800 | 4.3 / 4.6 |
| Nerra Daily | 504 | — | — | — | — | splice | — |
| Planetterrian | 498 | 6.3 | 2 | 11 | 1 | 1,152 / 1,600 | 4.3 / 4.6 |
| AI Chips | 238 | 6.9 | 4 | 4 | 4 | 2,081 / 1,400 | 4.7 combined |
| Privet, Russkiy (weekly) | 235 | 6.8 | 8* | 1 | 1 | 608 / 800 | 4.3 / 4.3 |
| Finansy Prosto (weekly) | 209 | 5.5 | 5 | 9 | 6 | 736 / 1,000 | 4.3 / 4.3 |
| MAG 7 | 205 | 6.5 | 2 | 10 | 4 | 1,557 / 1,250 | 4.7 combined |
| Peptides (weekly) | 167 | 7.5 | 1 | 1 | 1 | 1,532 / 1,200 | 4.7 combined |
| Vancouver | 140 | 6.9 | 7 | 3 | 7 | 1,618 / 1,450 | 4.7 combined |
| Top World | 133 | 6.6 | 4 | 3 | 5 | 1,737 / 1,750 | 4.7 combined |
| Prediction Markets | 129 | 6.9 | 6 | 8 | 6 | 1,522 / 1,400 | 4.7 combined |
| DP Pod (weekly) | 84 | 7.6 | 4 | 1 | 0 | 1,722 / 1,550 | 4.3 / 4.6 |
| Env Intel (weekly) | 76 | 5.2 | 1 | 13 | 1 | 851 / 900 | 4.3 / 4.3 |
| Longevity (weekly) | 48 | 7.4 | 1 | 1 | 1 | 1,767 / 1,200 | 4.7 combined |
| Collingwood (weekly) | 24 | 6.4 | 2 | 3 | 1 | 1,193 / 1,150 | 4.7 combined |
| The five desks | 11-14 each | 5.8-6.4 | — | — | — | ~1,050 / 1,300 | 4.7 combined |

\* Privet's factual flags are mostly non-critical Russian-grammar notes in the
reviewer's own memory (a singular «молодец» with a plural verb); worth a
language pass, not a pipeline fix.

Three patterns run across the network, and most of what follows is one of them:

1. **Restatement is the most common flag** (124 Repetitive findings in 17 days).
   It comes from prompts that ask for more than the facts carry: sentence
   quotas, "at least 8 analogies", a word floor the briefing cannot fill, or a
   section whose job is to repeat (a teaser, an action list, a market note).
2. **The closing teaser restates the body** on 21 of those 124 (Planetterrian 5,
   MAG 7 4, Prediction Markets 3, SpaceX, M&A, AI Chips and First Principles 2
   each): "Before we go — <an item already told>". MAG 7 and AI Chips read a
   dated calendar immediately before it, so the teaser had nothing new to say.
3. **The newer shows run long.** AI Chips' median is 1,797 words against 1,400
   (9 of 14 over 1.25x), Longevity 1,708 against 1,200, Vancouver 1,682 against
   1,450. Past ~2,200 words the script no longer fits one TTS request and the
   `<fast>` wrap drops (landmine #17): that happened on AI Chips once, Prediction
   Markets twice, Models & Agents three times and Modern Investing four times
   in the last 14 episodes, so those episodes read at a different pace.

## SpaceX Daily — 30% of the network's downloads, its weakest audit

SpaceX holds steady at ~1,200 downloads a week, more than every other show
combined bar Tesla, and its audit is 6.2 with INCOHERENT on 10 of 14 and
FACTUAL_ERRORS on 9. The flags have four causes:

**1. The market note is a fragment.** The prompt asked for a mid-episode
Market Watch note with "direction and rough magnitude only", gave the specimen
"up a little over two percent", and forbade the price, the tense and the
subject's clock. The model copied the specimen and dropped the subject: "Away
from the hardware, a little over two percent lower" (Ep160), "For SPCX, a
modest gain of under one percent" spliced into the solar deep dive (Ep159),
"Shares sat about nine percent lower" (Ep153), "For the listing, up a little
over three percent" (Ep151). The closing block already carries the exact quote,
so the note also told the move twice, with conflicting numbers on Ep152
($135.92 −3.8% against $133.22 −1.99%). Six of the 17 audits flag one of these.

**2. The deep dive was the length lever.** The podcast prompt called it "the
length lever" on thin days, licensed it to use the model's own knowledge, and
demanded "at least five numbers NOT spoken earlier". Its arithmetic is where
the factual flags land: PUE 1.3 called 30% overhead (it is 23%, Ep151), 7.8 km/s
called "near Mach 25" (about 23, Ep153), energy called heat flux (Ep150), the
"Idiot Index" applied to a path-loss gap (Ep146). The digest's word-floor
expansion also "lengthens that licensed section first" and fired on 6 of 7.

**3. Content farms reach Top News through Google News.** Ep149-162 cited
shattered.io 4 times (including a Cursor "rules linter" how-to the audit called
off-topic), ad-hoc-news.de 4, finance.biggo.com 3, basenor.com 2 — the same
farms Tesla excluded on Nov 11.

**4. Cursor is in scope, but the listener is never told why.** SpaceX agreed
to buy Cursor (Anysphere) this year (`shows/deep_dives/spacex.yaml`, the Q2
earnings special), so Cursor product news is company news, which the operator
put in the show's description. The audit, which does not know about the
acquisition, called it off-topic five times because the script never says the
tie. Narrowing the scope would be wrong; naming the tie is the fix.

Efficiency: the script stage's p95 is 903 s against a 600 s request timeout
(`api/model_trial.json` gate failure). Part of that is the phrase-loop retry:
the prompt requires the stage on every landing or catch, "super heavy booster"
ran 24 times in Ep158, the detector read it as a loop, and a second full
grok-4.6 script call ran on 3 of 8 episodes (~6 minutes each) without being
able to remove a name the prompt demands.

**Shipped for SpaceX:**

| Change | Where | Listen? |
|---|---|---|
| No mid-episode market note; the closing block speaks the one quote; no percentage without its company; the copied specimen removed | podcast prompt | ⚠️ |
| Deep dive is never a length lever; a derived number is spoken with the two figures it comes from or not at all; "at least five numbers" floor removed | podcast + system prompts | ⚠️ |
| Length line 1,500-1,900 words / 11-14 min → 1,300-1,700 / 9-12 min (the show ran 1,453 median; the old line pushed the deep dive to fill) | podcast + system prompts | ⚠️ |
| A Cursor item names the acquisition in its first sentence; a third-party how-to guide is never an item | both prompts | ⚠️ |
| `exclude_sources`: the Tesla farm list | YAML | no |
| `repetition_exempt_terms`: stage and vehicle names never fire the phrase-loop retry | YAML, `engine/validation.py`, `engine/generator.py`, `engine/config.py` | no |
| Teaser: only a next step no earlier sentence spoke, or none | podcast prompt | ⚠️ |

Not shipped for SpaceX: the digest fact floor (`min_digest_facts`) is the same
cure FF and Planetterrian took for the word-floor expansion, but Planetterrian's
readout is Nov 17; take it after that. The script model is discussed below.

## The newer shows: a word ceiling

AI Chips, MAG 7, Prediction Markets, Peptides, Longevity, Vancouver,
Collingwood and Models & Agents now state a hard ceiling in their podcast
prompt, about 1.25x the target and always under 2,000 words, so the single TTS
request and its `<fast>` wrap hold:

| Show | Target | Ceiling | Over it in the last 14 |
|---|---|---|---|
| AI Chips | 1,400 | 1,750 | 9 |
| MAG 7 | 1,250 | 1,600 | 3 |
| Prediction Markets | 1,400 | 1,750 | 3 |
| Peptides | 1,200 | 1,500 | 4 of 9 |
| Longevity | 1,200 | 1,500 | 5 of 8 |
| Vancouver | 1,450 | 1,800 | 6 |
| Collingwood | 1,150 | 1,450 | 1 of 8 |
| Models & Agents | 1,200 | 1,600 | 6 |

When the briefing carries more than fits, the strongest items keep every fact
and the others drop to one sentence each. The number lives in
`llm.max_podcast_words` and the prompt; run_show records
`podcast_script_ceiling_words` and `script_over_ceiling` and never trims or
retries (a podcast-side length lever is `do_not_retry`). Every committed
episode whose wrap dropped ran past its show's ceiling (guarded by replay).
This answers the open question from the Nov 13 slate review. Omni View gets the same kind of ceiling (about 1,900 words) in its own draft PR #1713, after Ep236 on grok-4.7 ran 2,990 words. These shows score
well (Peptides 7.5, Longevity 7.4); the ceiling is about pace and promise, not
quality, and it is the change most likely to need a listen.

## The closing teaser: one next step, or none

SpaceX, AI Chips, MAG 7, Prediction Markets and Models & Agents: the teaser
names only a next step, with its date, that no earlier sentence of the episode
spoke, and is left out when there is none. The "Before we go" chapter marker is
an ordinary `where: end` marker, so a missing teaser costs nothing.
Planetterrian has the most teaser flags (5) but is inside its Nov 17 fact-floor
readout; apply the same line there after it.

## Models & Agents for Beginners

REPETITIVE on 9 of 14, every one the same shape: an idea explained, then
explained again with a new metaphor ("the kitchen, flipbook and next-picture
lines say it again", Ep221), and the deep dive retelling the lead (Ep223, 225,
226). The prompt caused it: "at LEAST 8 analogies ... layer them ... try a
different angle", "2-3 vivid analogies" in the lead, sentence quotas (8-10, 6-8,
35-45+), "at least 1300 words" — from a three-story briefing of 700-900 words.
It also carried a quotable example story in which the host says "I tried it
this morning".

Shipped: one analogy per idea, then the facts; no sentence quotas; the
briefing's facts set the length (about 1,000-1,400 words); the deep dive
explains an idea the lead did not; the example replaced by a described shape,
and the host never claims to have tried anything. `min_podcast_words` 1200 →
1000 with the skip floor pinned at 720 (unchanged). ⚠️ AUDIO.

Not changed: the digest word floor (1,000) still fires on 7 of 7 and adds
150-300 words to the briefing. If Repetitive does not fall, the fact floor is
the next lever, after Nov 17.

## Finansy Prosto

Steady at 5 (13 audits), the same template as Beginners in Russian: "МИНИМУМ 8
аналогий", sentence quotas, "не менее 1300 слов" against a 1,000 target, and a
practical step required in every block, which aired as the same "check your
bank's rates and open online" advice two and three times (Ep90, Ep91). Ep90
also computed a mortgage payment change the briefing did not give, and got it
wrong ($30-50 a month for a quarter point on $500,000; it is about $70).
Shipped, in Russian: one analogy per idea; no quotas; 900-1,200 words set by
the facts; each action once; a derived dollar figure spoken with the numbers
it comes from or not at all; the deep dive on an idea the lead did not
explain. ⚠️ AUDIO (Olya), Mondays.

## Environmental Intelligence

The lowest audit in the network (5.2) and REPETITIVE on 13 of 13. The episode
structure says the same thing three times: the Compliance Brief gives "the one
immediate action and the deadline", Action Items reads the briefing's actions
again, Week Ahead repeats the dates, and the teaser closes on one of them. The
prompt also seeded padding by quoting it ("What this signals is...", "In
practice, this means...", "This ties into what Alberta did last month") and
still told the host the show runs "every other weekday" (it is weekly).
Shipped: Action Items and Week Ahead carry only what no earlier sentence said,
and are skipped otherwise; the padding block is described by shape; the
invented-cross-reference and "what practitioners suspected" lines are gone; the
teaser is weekly and may be left out. ⚠️ AUDIO, Mondays.

Not changed: the intake is thin (21 articles in the prompt, 2 items shipped);
YouTube stays paused. Downloads are 76 in 30 days. If the next four Mondays
stay under 6, the question is the show's format or cadence, which is the
operator's call.

## Shows left as they are, and why

- **Models & Agents** (6.8, 7-8 since Nov 4): the Nov 1 length pass is working.
  It gets the ceiling and the teaser rule only.
- **Modern Investing** (6.6): reviewed Nov 7; its Factual flags are mostly
  date arithmetic and 2026 market levels the reviewer doubts from memory.
  Its scripts break the TTS wrap on 4 of 14; a 2,150-word ceiling belongs
  there once its readout is in.
- **Planetterrian** (6.3, Repetitive 11): inside the Nov 17 fact-floor readout.
  After it: the teaser rule and the deep-dive-not-the-lead rule.
- **Top World, the five desks, Peptides, Longevity, Collingwood, DP Pod,
  Privet**: 6.4-7.6 with no dominant failure. The desks are members-only and
  their audits stopped on Oct 15.
- **Nerra Daily** is built from the shows' own audio, so it inherits every fix
  above; nothing of its own failed in this window.

## The pipeline: efficient, effective, on the latest tools?

**Cost is not the constraint.** LLM spend runs $0.04-0.23 an episode (credit
files, Nov 7-13): Nerra Daily $0.01, the 4.3/4.6 flagships $0.13-0.15, the
grok-4.7 cohort $0.12-0.13, Peptides and Longevity ~$0.22. Moving a show from
4.3+4.6 (two calls) to 4.7 (one combined call) costs about the same.

**Latency is.** `api/model_trial.json` fails three script stages on headroom:
SpaceX p95 903 s (150% of the 600 s timeout), Tesla 558 s (93%), Models & Agents
441 s (73%). All three run the script on grok-4.6 after a 4.3 digest. Streaming
keeps them alive past the timeout, but a stall now costs an episode. The
repetition fix above removes SpaceX's avoidable second call; the rest is the
model.

**The model question.** Thirteen shows still write their digest on grok-4.3
while Omni View moved both stages to grok-4.7 on Nov 13. The audit scores do
not settle it: the 4.7 cohort scores 6.4-7.5, the 4.3 shows 5.2-6.8, but the
shows differ in every other way too. The playbook (one show first, a latency
gate, then the next) is the right tool, and Omni View is the one show in
flight. Recommendation: read Omni View on Nov 27, and if it passes, move
SpaceX next (its script stage is the one at risk), then Tesla and Models &
Agents. Flipping more shows now would mean no show could tell us what 4.7
did.

**Other tools.** The pipeline already uses the current xAI stack (streaming,
pinned models with fallback, Grok TTS, Grok Imagine, x_search, the claims gate
with verified-from-fetched), so nothing is behind. Two cheap wins remain for
later passes: the digest fact floor for the flagships (after Nov 17), and
Planetterrian's digest stage (p95 151 s, +51% on its baseline) is worth a look
when its readout is read.

## Not shipped, and why

- The digest fact floor on SpaceX and Beginners: waits for Planetterrian's
  Nov 17 readout, as Omni View's did.
- Any model change: waits for Omni View's Nov 27 readout (above).
- A Modern Investing ceiling: waits for its own readout.
- Offshore North's minimum length: that show was reviewed yesterday and is
  outside this pass.
- Privet's Russian-grammar slips: real, but a language review needs a
  native-speaker read, not a prompt line.

## Predictions (scored by the next review)

Over the first 14 audited episodes of each show after merge:

1. SpaceX: no subject-less market sentence ("percent lower/higher" with no
   company in the sentence) in any script, and INCOHERENT on at most 5 of 14
   (was 10).
2. SpaceX: no `podcast_script_anti_repetition_retry` in a credit file whose
   only critical phrases are stage names; script stage p95 under 600 s in
   `api/model_trial.json`.
3. SpaceX: no Source line from shattered.io, ad-hoc-news.de, finance.biggo.com
   or basenor.com.
4. The ceiling shows: `script_over_ceiling` on at most 3 of 14 per show and
   `tts_speech_wrap_dropped` on none.
5. Teaser restatements: at most 5 Repetitive findings quoting a "Before we go"
   line across the five teaser shows (was 13 in 17 days).
6. Beginners: REPETITIVE on at most 5 of 14 (was 9). Env Intel and Finansy:
   REPETITIVE on at most half their next 4 audits (both were on nearly all).

Register `remaining-shows-review-2026-11-14`; guards
`tests/test_remaining_shows_review_2026_11_14.py`. Run "Run show" with
`rehearse: true` on SpaceX, AI Chips and Beginners and listen before merging
(landmine #17).
