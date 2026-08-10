# The DP Pod — Quality, Performance & Mission Review (August 10, 2026)

**Target:** `dp_pod` (operator-directed: performance, the "spread positive
intentionality" mission, narrative quality, and listener/reader/site-visitor
experience for current and future supporters).
**Method:** `scripts/review_snapshot.py dp_pod` + all 30 committed episodes
(digests, `_tts.txt`, Whisper transcripts), `shows/dp_pod.yaml` +
`_defaults.yaml` deep-merge, all three prompts, `shows/hooks/dp_pod.py`,
`thedppod.html`, `dispatches.json`, `api/dashboard.json` / `op3_stats.json` /
`spotify_stats.json` / `apple_stats.json`, prior review
(`dp_pod_review_2026_07_09.md`) + ledger.
**Drift guards added:** `tests/test_dp_pod_show.py::TestLeverRotationMemory`.

## Verdict

The factory is healthy (30/30 episodes, 100% pipeline success, $0.10/episode
all-in) and the July 9 de-gimmick pass landed — but **the show's central
promise is currently being broken on air**: The Lever, "one concrete action a
day," aired the *same action seven episodes straight* (Ep24–30), and roughly
half of episode airtime is the written brief read aloud in dialogue costume.
A listener who joined "the antidote to doomscrolling that actually asks
something of you" got asked the identical thing for a week by hosts speaking
without a single exclamation point. The mission — every little bit of
positivity, whatever *you* can do — is exactly what lever variety proves;
repetition tells the audience the show ran out of ideas for doing positive.

Audience is small and plateaued (37 downloads/30d, ~15/week for three weeks,
2.8/episode — below network median; Spotify 0 followers), but the show's two
growth surfaces (newsletter, YouTube Shorts) are both switched off, so this
is a distribution ceiling at least as much as a content problem.

**Scorecard (1–10, July 9 in parens):** Fit 8 (8) · Interest 5 (6) ·
Content 5 (6) · Positioning 7 (7) · Engagement loop 3 (3).

## Previous predictions (ledger scored)

1. **Phantom prior-lever callbacks: HIT.** Every Dispatch callback in
   Ep5–30 references the real aired lever (Ep30's callback quotes Ep29's
   actual heat-pump assessment). The hook injection works — too well; see P0.
2. **Club page CTA is join/membership, not oath: HIT.** "Sign the pledge"
   is gone; the CTA reads "Join free — get the daily briefing" with "No oath
   required" (`thedppod.html` join section). Only CSS class names still say
   "pledge".
3. **≥1 real Dispatch within 2 weeks: MISS.** `dispatches.json` is still
   empty a month later; the on-air invitation runs daily against a wall that
   renders its how-to-send empty state. Reopened below as an escalated
   operator item (second filing).

## P0 — The Lever is stuck in repetition loops (listener-facing, mission-critical)

The daily action segment shipped in consecutive near-identical runs:

| Episodes | Lever | Run |
|---|---|---|
| Ep4–8 | free home **solar assessment** | ×5 |
| Ep10–13 | free home **energy assessment + seal 3 air leaks** | ×4 |
| Ep14–15 | citizen science | ×2 |
| Ep17–19 | **plug-in solar panel** | ×3 |
| Ep20–23 | **wetland monitoring** sign-up | ×4 |
| Ep24–30 | **heat-pump assessment** | **×7 — every episode for a week** |

The last 15 episodes contain only **4 distinct actions**; the last 10 only 2.
On a daily show this is the single most listener-visible defect it has.

**Root cause — three mutually reinforcing seeds** (all verified in tree):

1. The digest prompt's Lever spec supplied a **quotable example** — *"get a
   free home heat-loss assessment and seal the top three leaks"* — which
   aired nearly verbatim as Ep10–13's lever (the playbook's de-seed rule,
   violated in-house).
2. The anti-phantom bans **named their own example**: "never invent a
   different past lever (heat pumps, filters…)" appeared in the digest
   prompt, the podcast prompt, and the hook's injected PREVIOUS LEVER
   string. Heat pumps then became the longest-running lever (Ep24–30).
3. The July 9 phantom-callback fix injects the previous lever into every
   prompt — after which it was **the only lever the model could see**, and
   with no rotation memory it became an attractor (the exact dynamic the
   July 31 Network-pick fix diagnosed: filter/supply the data, don't just
   instruct the output).

**Shipped:**

- `shows/hooks/dp_pod.py:_recent_levers()` — rotation memory mined from the
  last 15 committed digests, injected as a "RECENT LEVERS … never repeat or
  lightly rephrase" block (the same data-side pattern that fixed the Network
  pick and Think Positive thinkers — the pick now rotates cleanly:
  PT→FPD→FF across Ep24–30).
- PREVIOUS LEVER injection reframed: "for the Dispatch callback ONLY …
  today's Lever must NOT reuse this action — it is yesterday's."
- Both prompts + hook **de-seeded by shape**: the quotable heat-loss example
  and every "heat pumps, filters" mention removed; Lever spec gains
  "ROTATION IS MANDATORY" + a domain-rotation rule + a validation-checklist
  line. (⚠️ A/B-listen — prompt changes.)
- Drift guards: `TestLeverRotationMemory` (memory mined from real digests
  with a data-independent no-invented-lever check; clean no-op on empty
  history; prompts keep the rotation rule and stay seed-free).

## P1 — Quality ceiling

### 1. Half the show is the brief read aloud (narrative quality)

Measured across all 30 episodes (10-word shingle overlap between digest and
script; exact digest sentences ≥8 words appearing verbatim in the script):

- Ep22: **65% overlap, 31 verbatim sentences**. Ep29: **42%, 44 sentences**.
  Ep14: 44%/26. Ep26: 44%/12. Ep30: 27%/24.
- Episodes are bimodal: real-dialogue days (Ep8/11/15/24/25: 0–8% overlap,
  57–75% one-sentence turns) alternate with paste days (long unlabeled
  paragraphs of brief prose — Ep29 had 17 unlabeled paragraphs — that air
  as one host suddenly reading wire copy).
- **Delivery spec is ignored wholesale on grok-4.3:** 27 of 30 episodes
  shipped **zero exclamation points** (3 total across the entire run against
  a spec asking "several per episode"); ~5 voice-direction tags used in 30
  episodes against a budget of 10 *per episode*; the July-18 comedy block
  (2–3 beats, running callback) fires only partially.

The instruction route has now been tried twice (July 9 "ban digest
re-reads" prompt block; July 18 banter/delivery enforcement moved into the
segment specs) — both shipped, both violated. Per the playbook's
escalate-with-a-different-approach rule, the escalation is the July-31
network review's purpose-built knob, unused until now:

**Shipped (⚠️ A/B-listen):** `llm.podcast_model: grok-4.5` on dp_pod — the
script stage only. Grok-4.5 writes markedly better prose but hallucinates
more confidently; dp_pod is the network's safest host for the trade because
the facts are locked into the digest by grok-4.3 *before* the script model
runs, and the script prompt forbids new facts. Empty default = byte-identical
revert (delete one line). Registered in `docs/experiments.yaml`
(`dp-pod-script-model-45`, readout 2026-08-24). Drift guard pins the digest
stage never following it.

### 2. Chronic under-length: the digest format spec contradicted the digest floor

8 of the last 10 scripts are below the 1,550-word target — and the
sanctioned digest-side lever was already on (`min_digest_words: 1100`,
expansion retry firing) yet digests shipped 667–1,240 words. Root cause: the
**format spec itself caps the digest at ~750–900 words** (2–3 items × 4–6
sentences + fixed segments), so the one-shot expansion retry was asked to
exceed the format it was told to keep. Same contradiction class as MIT's
"at least 2500 words" (June 2026).

**Shipped (⚠️ A/B-listen):** Positive Papers items raised to 6–8 sentences
(with an explicit "extract MORE of what the source says, never significance
padding" rule + the open question the hosts can argue about), Lever to 6–9
sentences. Format now arithmetically reaches ~1,100–1,300 words.

### 3. Config hygiene (shipped, behavior-neutral)

`shows/dp_pod.yaml` declared `min_digest_words` twice (900 from the Aug 1
patch, 1100 pre-existing — YAML last-wins meant 1100 was always effective)
and `digest_expand_below_target` twice. Deduplicated; guard asserts one
declaration each.

### 4. Minor (watch, no change)

- Think Positive thinker rotation works overall but repeated Simon Sinek on
  consecutive days once (Ep23→24) despite the do-not-reuse list.
- "The main barrier is…" opens the barrier line in 7/10 episodes — a
  template echo of the prompt's "One real barrier" bullet; expected to soften
  with the script-model A/B, re-check next pass before de-seeding further.

## P2 — Growth & supporter experience

1. **The club promises a daily briefing nobody sends (escalated operator
   decision, second filing).** `thedppod.html`'s join form says "Free email
   membership. Daily briefing when it drops." while `newsletter.enabled:
   false` — a new supporter's first experience of the club is silence. July 9
   deferred this; it is now the top of the funnel gap. Decide: flip
   `newsletter.enabled: true`, or soften the page copy to "episode alerts
   when we turn them on." Leaving the mismatch is the one option that costs
   trust.
2. **Empty Dispatch wall (operator, second filing).** The accountability
   loop the show sells still has zero receipts; the hosts' on-air
   commitments ("I'm going to call my local utility this week…", Ep30) have
   no follow-through anywhere. One real seeded dispatch
   (`scripts/add_dp_dispatch.py`) converts the loop from aspiration to proof.
3. **Both discovery surfaces are off.** YouTube is disabled (launch
   decision) while Shorts are the network's best-performing surface, and the
   show's disagreement beats are exactly the 35-second clips that travel.
   With the 200k quota there is no budget reason to wait; recommend
   Shorts-only enable once the operator has A/B-listened the current PR's
   changes (one YAML flip, `image_provider: grok` already pre-set).
4. **Performance read:** 37 downloads/30d, weekly 0→6→16→15 (plateau ~15),
   $2.61/30d total cost, $0.07/download. Cheap enough that patience is free
   — but with zero email, zero video, and X off, the only acquisition path
   is the network's own cross-promo, and the plateau reflects that. The
   content fixes above make the product worth pointing new listeners at;
   items 1–3 are what will actually point them.

## Shipped in this PR

- `shows/hooks/dp_pod.py`: `_recent_levers()` rotation memory + reframed
  PREVIOUS LEVER injection (de-seeded).
- `shows/prompts/dp_pod_digest.txt`: Lever de-seed + mandatory rotation +
  domain rotation + checklist line; Positive Papers 6–8 sentences; Lever 6–9.
- `shows/prompts/dp_pod_podcast.txt`: de-seeded phantom-callback ban.
- `shows/dp_pod.yaml`: duplicate llm keys removed; `podcast_model: grok-4.5`
  script-stage A/B.
- `tests/test_dp_pod_show.py::TestLeverRotationMemory` (7 guards).
- `docs/experiments.yaml`: `dp-pod-script-model-45` entry.

## ⚠️ A/B-listen required (landmine #17)

Every prompt/model change above alters shipped audio. Listen to the first
1–2 post-merge episodes end-to-end, checking specifically: (1) today's Lever
is a NEW action in a new domain; (2) the Positive Papers sound like two
friends arguing, not the brief read aloud; (3) grok-4.5's energy (are the
exclamations real or performed?); (4) no new hallucinated facts relative to
the digest — that is the specific risk grok-4.5 adds, contained but not
zero. Revert paths: delete `podcast_model` line; `git revert` the prompt
edits.

## Deferred / not done (with reasons)

- **Deterministic verbatim-paste retry** (regenerate the script when digest
  overlap exceeds a threshold): wait for the grok-4.5 readout first — if the
  model change fixes it, the retry is dead weight; if not, this is the next
  escalation (mirrors the publication-floor re-roll shape).
- **Weekly Lever-of-the-Week + collective counter, Shorts clips of
  disagreements:** still the right bigger bets, still blocked on the loop
  having real receipts (P2 items 1–2).
- **De-seeding "the main barrier is…"** — watch one cycle first (P1.4).

## Operator checklist

- [ ] A/B-listen the first post-merge episode (lever novelty, dialogue vs
      paste, grok-4.5 energy and factuality)
- [ ] Decide the newsletter mismatch: enable it or soften the join copy
- [ ] Seed ONE real dispatch (`scripts/add_dp_dispatch.py`)
- [ ] Consider Shorts-only YouTube enable after the A/B settles
- [ ] Read out `dp-pod-script-model-45` by 2026-08-24 (keep grok-4.5 or
      revert the line)
