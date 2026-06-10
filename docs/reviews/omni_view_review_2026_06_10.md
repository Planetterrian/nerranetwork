# Omni View — quality pass (2026-06-10)

First dedicated quality pass on Omni View (the show had received only the
cross-cutting June 2026 network-pass touches — Steel Man repositioning,
hook-led X teaser, RSS description rewrite — but never a Tesla-style
per-show chapter/length/tic review). It was missed by every chapter- and
length-hardening round (Tesla #573/#576, four-show, env_intel, FP, PT).

Snapshot baseline (`scripts/review_snapshot.py omni_view`): median ~1,150
words/episode (range 900–1,566) against a 900-word YAML floor; cost
~$0.11/episode; OP3 28 downloads/7d, 126/30d; "10/10 clean chapters" — but
that check only verifies structural validity, not semantic completeness,
and it masked two real shipped chapter bugs (below).

## P0 — listener-facing bugs shipping today

### 1. 7 of the last 10 episodes shipped with NO Closing chapter
The Closing marker pattern was `That's Omni View|that.?s.*for today|until
next time`. But the **dominant** closing-pool variant in
`engine/intros.py` is *"That wraps up today's Omni View. Remember — the
best-informed people read more than one perspective…"* — which matches
none of those alternatives. Result: ep068, 069, 070, 071, 073, 076, 077
shipped with no Closing chapter (the MAB orphan-closing class). Verified
against `digests/omni_view/chapters_ep0*.json`.

### 2. Garbage chapter titles from raw deep-dive sentences
The "Understanding the Issue" pattern (`understanding the issue|deeper
look|let's understand`) never matched the actual spoken deep-dive opener
("*Now, to really understand this story, there is something most coverage
leaves out…*" / "*To understand the X more fully…*"). With only 2 markers
matching, the auto-segment fallback (`engine/chapters.py:208`) fired and
titled a chapter from the segment's first sentence:
- ep061: chapter titled **"Knowing this, when you hear claims that the
  system worked…"**
- ep068: chapter titled **"How are casualty figures verified when access
  to strike…"**

**Fix (both):** rewrote `shows/omni_view.yaml`'s `chapters` block with
positional `where` anchors (Introduction=start, Tomorrow Teaser/Closing=
end), a Closing pattern covering both closing-pool variants, a
Tomorrow-Teaser pattern covering the "Tomorrow, watch for" variant, and a
real deep-dive pattern matching the spoken opener. This restores the
deep-dive chapter AND keeps the matched-marker count at/above
`min_chapters`, so the garbage-title fallback stops firing.

**Verified** by running `parse_chapters` against the last 10 committed
`_tts.txt` scripts: every episode now yields
`Introduction → Main Stories → Understanding the Issue → Tomorrow Teaser →
Closing` (ep068 omits the deep-dive chapter — it had no matching opener —
but now correctly has Teaser + Closing and no garbage title). This is a
**metadata-only change** (chapters.json sidecar — podcast-app navigation);
it does **not** alter the audio, so no A/B listen is required.

## P1 — quality ceiling

### 3. The steel-man scaffolding tic — the June fix failed
The June 2026 network pass added a podcast-prompt instruction to "rotate
three framings" and use "the strongest case" **at most once per episode**.
The transcripts show it was **ignored**:
- ep075: "the strongest case" ×**20**
- ep070: ×**14**
- ep071: ×**12**

And in the episodes where the phrase finally dropped, it had simply
**mutated into an equally rigid, equally audible scaffold** — ep077 opened
story after story with the anonymous frame *"One side frames X as… / The
other side frames Y as… / Advocates on each side acknowledge…"* (each ×6).
That anonymous "one side / the other side" framing also **violates the
prompt's own rule** that every perspective name a specific outlet, party,
or group — the steel-man, the show's signature, had degraded into generic
unattributed both-sides-ism.

**Root cause:** the *digest* prompt prescribed the literal lead-in
`Lead each with its best supporting reason ("The strongest case for X
rests on [specific value / mechanism / evidence]…")` for every story, so
the digest produced the phrase 5–7× and the podcast inherited it. The
June fix only touched the podcast prompt's symptom, not the digest's seed.

**Fix:** removed the canned lead-in from the digest prompt and added a
CRITICAL instruction to (a) **name who holds each position** (banning
anonymous "one side / the other side / advocates on each side"), (b) vary
the lead-in structure story to story, and (c) cap "the strongest case" at
once per digest. Mirrored the anonymity ban in the podcast prompt with the
specific ep077 failure mode called out.

**Before/after (exercised live via `run_show.py omni_view --test`, $0.02):**
the regenerated ep078 test digest used **0** "the strongest case", **0**
anonymous "one side/the other side", **0** "advocates on each side" — and
attributed every position: *"The strongest argument from the leave
perspective, advanced by Rees-Mogg, rests on restored parliamentary
sovereignty…"*, *"…advanced by Campbell…"*, *"Treasury officials argue…"*,
with empirical-ground-first lead-ins ("Both sides accept that goods
trade…; they differ on whether…"). **⚠️ A/B-listen required** (it changes
generated audio).

### 4. Three contradictory length targets; chronic under-length
The podcast prompt simultaneously demanded "an 8–12 minute" episode, "at
least 2000 words", and "40–60+ sentences" — and the bottom-of-prompt
LENGTH TARGET claimed "at least 2000 words (40+ sentences)", whose own
arithmetic is broken (40 sentences ≈ 700 words, not 2,000). The YAML floor
was 900. Episodes landed ~1,150. Omni View was also **omitted** from the
June network pass that added `podcast_expand_below_target` to the eight
chronically-short shows.

**Fix:** unified the prompt to **one** target (1,700–2,000 words ≈ 11–13
min), set `min_podcast_words: 1400`, and added
`podcast_expand_below_target: true` so the one-shot "cover more stories"
retry fires whenever a first pass lands short (the digest carries ~12
stories; episodes were covering only 6–7). Soft skip floor = 1400×0.6 =
840 < the lowest recent output, so nothing newly skips. **⚠️ A/B-listen
required.** Watch week 1 for `podcast_script_too_thin` markers; fall back
to `min_podcast_words: 1200` if it skips.

## P2 — growth / discoverability

Verified already in good shape, **no change**:
- X teaser is hook-led + links the episode blog post (June network pass,
  `run_show.py:4543`).
- RSS channel description leads with the Steel Man value prop
  (`shows/omni_view.yaml` publishing block).
- `min_articles_skip: 4` is the tuned per-show value (landmine #21).

Deferred (recommendation, not shipped):
- The milder "Both sides agree X; they differ on whether Y" frame still
  recurs (3× in the ep078 test digest). The rotation instruction now
  covers it; re-evaluate next pass whether it has become the new tic.
- OP3 downloads are low (28/7d) but the X-teaser/blog SEO levers are
  already pulled; growth is a network-funnel question, not an Omni View
  editorial one.

## Tests
New drift guard `tests/test_omni_view_quality_pass.py` (11 tests) pins all
four fixes. Ran green alongside `test_prompt_fidelity.py`,
`test_chapters.py`, `test_generator.py`, `test_episode_validity.py`,
`test_schedule.py`.

## ⚠️ A/B-listen required (landmine #17)
- Digest steel-man prompt rewrite (#3).
- Podcast steel-man anonymity ban (#3).
- Podcast length-target unification + `podcast_expand_below_target` /
  `min_podcast_words: 1400` (#4).

The chapter fix (#1, #2) is metadata-only and does **not** require a
listen.
