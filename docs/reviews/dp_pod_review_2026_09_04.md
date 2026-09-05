# The DP Pod — Naturalness, Mission & Performance Review (September 4, 2026)

**Target:** `dp_pod` (operator-directed: performance, spreading positive
intentionality, a more natural narrative between Patrick and Dan, and the
listener / reader / site-visitor experience for current and future
supporters).
**Method:** all 26 episodes shipped since the Aug-10 renewal (Ep31–56:
digests, `_tts.txt`, Whisper transcripts, chapters, metrics), the 11 kept
pre-renewal episodes as the control, `shows/dp_pod.yaml`, all prompts, the
hook, `engine/intros.py`, `thedppod.html` + blog + API surfaces,
`api/dashboard.json` / `op3_stats.json` / `buttondown_stats.json`, the Aug-10
ledger predictions, the experiments register (`dp-pod-script-model-45`,
`staged-grok-46-trial`).
**Drift guards added:** `tests/test_dp_pod_show.py::TestSep4NaturalnessPass`.

## Verdict

**The renewal worked.** Verbatim briefing paste collapsed from ~30% to ~3%
median; digests reach their floor; the grok-4.6 script stage was adopted for
good on Sep 1 (14/14 days, no factual-flag elevation); and Ep56 reads like
two friends — real volleys, steel-manned disagreement, concessions in the
other's words, a running callback, jokes built from the day's facts.
Downloads tripled (37 → 113 per 30 days) on the same cost order (~$6.6/month).

**But the show has grown three successor habits, each the predicted
second-generation form of a fixed first-generation one:**

1. **The Lever converged on a shape instead of a phrase.** Rotation memory
   stopped exact repeats; the model then wrote *"Open your \<website\> today,
   enter your postcode, and note …"* — "Open" opened 13 of 26 levers and
   **21 of 26 were screen lookups**. A show whose sign-off is "do something
   about it" was telling listeners to open a browser four days in five, and
   the mission — every little bit of real-world positivity — was not what
   the segment modelled.
2. **The comedy examples became the comedy.** The prompt says "no
   catchphrases, ever" and then supplied its own: "checklist" appeared in
   23/26 episodes, "steel-man" in 23/26, "I'll concede" 17/26, "preflight"
   10/26, "chemist brain" 8/26. Listeners hear the same three bits daily.
3. **Episodes outgrew the promise.** On 4.6 the scripts run 1,850–2,400
   words → **11–14 minutes** against "ten minutes a day" on the club page
   (and an API field that said "~15 min").

Plus: the founders' real material went almost unused (Yukon 0/26, WestJet
0/26, Dan's own solar once), so Dan in particular sounds like an archetype
rather than a person; two of four closings asked for dispatches seconds
after the Dispatch segment had asked, and one claimed "we read every
dispatch on the show" with zero dispatches ever received.

**Scorecard (1–10, Aug 10 in parens):** Fit 8 (8) · Interest 7 (5) ·
Content 7 (5) · Positioning 7 (7) · Engagement loop 3 (3).

## Aug-10 predictions scored (ledger)

| Prediction | Result | Evidence |
|---|---|---|
| ≥6 distinct levers in next 10, none >2× | **hit** | 8 distinct in Ep31–40 (two pairs) |
| Median digest↔script shingle overlap ≤15% | **hit** | 4.5% (Ep31–40); ~3% across Ep31–56 |
| ≥6/10 episodes with ≥2 exclamation points | **miss** | 2/10 on the grok-4.5 window (6/10 had ≥1, up from 0). The 4.6 arm that replaced it hits: 9/13 in Ep44–56 |
| Median digest ≥1,050 words | **hit** | ~1,095 |

## P1 — The Lever's second-generation convergence (mission-critical)

- Fuzzy near-duplicate groups across Ep31–56: conservation-group contact
  ×3 (Ep31/37/44), utility-postcode ×2 (+2 close variants), citizen-science
  app ×2, clinic-portal ×2, ClinicalTrials.gov ×2 — the exact-string memory
  saw all of these as new because a word or two changed.
- Root cause is my own Aug-10 de-seed: *"a named first step, the place or
  tool to do it with … start today"* is a shape, and the model wrote the
  shape. The playbook's successor-tic rule, confirmed in-house.

**Shipped (data-side + shape de-seed):**

- `_recent_levers()` now collapses re-skins (content-word Jaccard ≥ 0.34)
  so a variant is listed once and banned as a class; computes **BANNED
  OPENING VERBS** (any verb opening ≥2 of the last six levers) and
  **REAL-WORLD ACTION DUE** (fires when ≥half the last six were screen
  lookups — today it fires at 6/6) from the data, not from instruction.
- Digest Lever spec rewritten by shape: *something a listener could
  photograph having done — hands, feet, voice, or wallet; a screen step
  qualifies only when it ENDS in a thing booked, sent, signed up for,
  planted, fixed, cooked, or bought.* Obeys the two data lines. (⚠️ A/B.)

## P1 — Catchphrases: the prompt's examples elected as the bits

**Shipped:** `_recent_banter_phrases()` mines 2–3-word content phrases that
recur in ≥3 of the last six scripts, excluding anything that is fixed
furniture (segment names, intro/closing pools, the AI disclosure, the
dispatch channel line, and any phrase present in the prompts themselves —
so a phrase the prompt asks for can never be banned), and injects them as
**RETIRED BITS**. On today's data the list is exactly the calcified set:
*checklist again; there's your checklist; I'll concede; I'll steel-man;
I'll give; I'm opening; rounding error; fifty listeners …*. The podcast
prompt's comedy and dynamic examples ("preflight checklist", "chemist
brain", "there's your checklist again", "seal my own windows", "steel-man")
were removed and described by shape, with an explicit rule that a bit that
would work on any episode is a catchphrase, not a joke. (⚠️ A/B.)

## P1 — Length vs the ten-minute promise

Ep44–56 audio: 11.1–14.1 min (median 12.2). The prompt's "1,500–1,700
words" was a target grok-4.3 never reached and 4.6 sails past. **Shipped:**
a HARD CEILING of 1,750 words with a cut rule (weakest exchange or third
example — never a caveat, a number, or the disagreement) (⚠️ A/B), and the
API duration corrected to "~12 min" (it had defaulted to "~15 min").

## P1 — Two friends, not two archetypes

- **Founders' notes unused.** `_founders_detail_nudge()` fires only when
  no real host material has aired in five episodes and asks for ONE
  genuine detail, in one or two turns, exactly as the notes state it —
  the notes stay the only sanctioned source; nothing is invented. The
  prompt's dynamic block now says a real memory beats a generic joke.
- **Dan's section is four bullets.** Added a comment block (never reaches
  the prompt) with five concrete questions for Dan — his solar numbers, a
  cockpit moment, a house/car thing that didn't pay off, what his daughters
  ask about the future, the outdoor sport that taught him patience. Real
  answers are the single biggest naturalness lever left that code cannot
  supply.

## P2 — Listener, reader, and supporter experience

- **Closings.** The two dispatch-asking closings now carry the mission line
  instead ("whatever you do about today — however small — counts"; "Nobody
  fixes the world in a day. Everybody nudges it. Pick your nudge."). The
  Dispatch segment keeps the single ask, and the show stops claiming a
  reading habit it has never had the chance to exercise. (⚠️ A/B.)
- **Reach: YouTube ON, Shorts-only.** Held at launch and on Aug 10 pending
  the script-model A/B; that condition is now met. Short #1 clips the
  hook, the smart selector finds the disagreement beats — the network's
  best-performing surface, the show's best material. Long-form waits on
  the adaptive policy. Experiment `dp-pod-youtube-shorts` (readout
  Sep 25). Operator one-time: create + flag the podcast playlist in Studio
  (landmine #15). Quota preflight after the change: EN 46,900/200,000
  units, 25 uploads/day.
- **Newsletter is real.** 26/26 renewed episodes recorded `newsletter_sent`
  with a Buttondown email id. The list is still tiny (Buttondown reports 4
  subscribers network-wide), so email cannot yet drive dispatches — the
  Shorts surface is what feeds the list.
- **Blog + club page** render cleanly: labelled dialogue transcript, Lever
  and Dispatch sections, mailto CTA, no speech-tag leaks; the club page
  carries the "two honest sentences count" copy and the reply-to-email
  channel from Aug 10.
- **Dispatch wall: still zero after 56 episodes** (third filing). The hosts
  commit on air nightly ("Tonight I'm opening ClinicalTrials.gov…") with no
  follow-through anywhere. Dan's solar install in the founders' notes is
  honest, ready material for the first receipt — one command
  (`scripts/add_dp_dispatch.py`).

## Performance read

| | Aug 10 | Sep 4 |
|---|---|---|
| OP3 downloads / 30d | 37 | 113 |
| Weekly downloads | 0 → 6 → 16 → 15 | 18 → 37 → 24 → 28 |
| Per-episode (7d) | 2.8 | 3.5 (below median) |
| Cost / 30d | $2.61 | $6.58 |
| Spotify followers | 0 | 0 |

Growth tracks the content fix, then plateaus at ~27/week — the same shape
as July's plateau at a higher level, and the same cause: no discovery
surface. Shorts is the first one.

## Also fixed

- `scripts/review_snapshot.py` crashed with `UnboundLocalError` on any show
  without `exclude_title_patterns` (dp_pod, the narrative shows) — the
  scheduled review agent's Phase-0 numbers were silently unavailable for
  them. `digest_files` hoisted; guard runs the snapshot for dp_pod.

## ⚠️ A/B-listen required (landmine #17)

Prompt and closing changes alter shipped audio: the Lever spec (physical
actions), the comedy/dynamic de-seed + RETIRED BITS, the 1,750-word
ceiling, the two rewritten closings, and the founders' nudge when it
fires. Listen for: a lever you could photograph having done; a joke built
from today's story rather than the checklist; an episode that lands near
eleven minutes; and, when a founders' detail airs, that it matches the
notes exactly. Revert paths: `git revert` the prompt/intros edits;
`youtube.enabled: false` for the reach change.

## Operator listen item (not a code change)

Whisper transcribed "that brings us to the **liver**" in both Ep30 and
Ep56. Either the announcement is being spoken as "LEE-ver" or Whisper is
mishearing — it is the segment name, spoken daily, so worth one listen.

## Deferred (with reasons)

- **Deterministic script re-roll on bad-service days.** Ep41 and Ep43
  (both 4.6) shipped the old shape — ~1,150 words, 46–50% digest overlap,
  Ep43 with 9 unlabeled paragraphs. 2 of 26 days; the trigger (<1,250
  words AND >30% overlap) is precise, but a re-roll is engine work and the
  rate is low. Revisit if it rises.
- Weekly Lever-of-the-Week + collective counter — still blocked on real
  receipts.

## Operator checklist

- [ ] A/B-listen the first two post-merge episodes (lever, comedy, length)
- [ ] Answer the five questions in `shows/dp_pod_founders_notes.md` (Dan)
- [ ] Seed the first real dispatch (Dan's solar numbers qualify)
- [ ] Create + flag the DP Pod podcast playlist in YouTube Studio
- [ ] One listen for "lever" vs "liver"
- [ ] Readouts: `dp-pod-lever-shape-v2` Sep 18, `dp-pod-youtube-shorts` Sep 25
