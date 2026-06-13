# Unintended Consequences — quality pass (June 12, 2026)

First dedicated review of **Unintended Consequences** (UC). Prior coverage was
only the June 2026 network pass (hook-led X teaser, `podcast_expand_below_target`,
UC closer-tic ban, topic-queue restock) — no per-show review or ledger existed.

Method: `scripts/review_snapshot.py unintended_consequences`, then read the
config, all four prompts, the intro generator, the chapter engine, and the
last 10 episodes' digests / `_tts.txt` / transcripts / chapter JSONs / metrics.
Audio was verified through transcripts and the chapter parser run against the
real committed scripts.

## TLDR

- **P0/P1 — chapters were broken on every recent episode (0/10 correct).** UC
  was missed by the Tesla/four-show/First-Principles chapter hardening: no
  positional `where` anchors, and seven keyword markers that assume the spoken
  prose contains literal section words — which the podcast prompt explicitly
  forbids ("flow naturally between them"). Worse, the show's own brand name
  *Unintended Consequences* (contains "consequence") collided with the body
  "consequence" marker on both the intro and the sign-off. Result: out-of-order
  semantic labels, the closing brand mention titling a body chapter, and missing
  Introduction/Closing (ep024 opened on "The Lesson"; ep028 ended on "The
  Unintended Consequences"). **Fixed** — anchored Introduction (`where: start`) +
  Closing (`where: end`), dropped the unreliable middle markers, let
  auto-segmentation fill the middle with in-order content titles. Verified
  **10/10** recent episodes now parse Introduction-first / Closing-last / 4-6
  chapters. Code-only (YAML), no audio change.
- **P1 — the closing pool contradicts the prompt.** The podcast prompt's WHAT
  TO AVOID block bans "That wraps today's case" as a recurring close, but that
  exact line is one of only **two** entries in the `intros.py` closing pool —
  and the closing block is supplied verbatim (the LLM can't vary it). It shipped
  on 5 of 10 recent episodes, and the 2-entry pool repeated the same closing 3
  episodes in a row (Ep026-028). **Fixed** — grew the pool 2→4, removed the
  banned phrase, and re-pointed the prompt bullet at the LLM-controlled lesson
  close. Audio-affecting → A/B-listen.
- **P1 (documented, deferred) — chronic under-length.** All 10 recent episodes
  ran 857-1211 spoken words (≈ 6-8 min) against a 1,300-word floor and a
  2,200-2,800-word (15-18 min) prompt target. Root cause is the **digest**: the
  briefs are 700-960 words against the digest prompt's 1,500-2,200 target, and
  the podcast prompt says "use ONLY information from the brief," so a thin brief
  caps the script. The narrative-aware expansion retry already fires every
  episode but can only deepen what's in the brief. This is the same finding the
  First Principles review reached and **deferred** (operator confirmed grok-4.3
  plateaus on narrative length and resists escalation); the digest-expansion
  lever it named is carried forward here, not implemented — a generator change
  affecting all shows that changes shipped audio is out of scope for a single
  show review.
- **P2 (documented) — the supplied intro is dropped ~30% of the time.** The
  podcast prompt says "use this exact intro," but on ep023/ep024/ep027 the LLM
  rewrote it, dropping the brand name *and* "episode N" from the spoken open.
  The new Introduction chapter anchor is robust to this (generic opening-word
  fallback), but listeners on those episodes never hear the show name at the
  top. Not fixed — a missing-intro guard analogous to the Planetterrian
  missing-closing guard risks a double-greeting; documented for the operator.

## Findings + evidence

### P0/P1 — chapters (FIXED)

`shows/unintended_consequences.yaml:96-112` (old) had no `where` anchors and
seven markers. Running the **old** markers through `engine.chapters.parse_chapters`
on the 10 committed `_tts.txt` scripts:

```
ep023: ['The Lesson', 'Closing']                              # no Introduction
ep024: ['The Lesson', 'The Aftermath', 'The Unintended Consequences', 'Closing']  # reversed arc
ep027: ['The Good Intention', ..., 'Introduction']            # closing brand → "Introduction" at end
ep028: ['Introduction', <3 raw sentences>, 'The Unintended Consequences']  # closing brand → body title
```

`chapters_ep024.json`, `chapters_ep026.json`, `chapters_ep028.json` (committed)
confirm the shipped breakage. Two root causes:

1. **No positional anchors** + the brand name. "Welcome.*Unintended
   Consequences|Unintended Consequences.*episode" and the body
   "unintended|...|consequence" marker both fire on the brand, which appears in
   the intro AND the sign-off.
2. **Middle markers depend on words the prompt forbids.** "good intention",
   "rolled out", "aftermath", "lesson" rarely appear verbatim in label-free
   narration, so 4 of 7 markers never matched and the rest fired wherever a
   keyword happened to land — out of arc order.

**Fix** (`shows/unintended_consequences.yaml`): keep only Introduction
(`where: start`) and Closing (`where: end`) — the two markers that *can* match
reliably on a label-free narrative show — and let the engine's
auto-segmentation fallback fill the middle with in-order, content-derived
titles (the path other shows already use when their semantic markers
under-fire). The Introduction pattern ORs the intro/closing-pool vocabulary +
brand + spelled episode number + date + a **generic opening-word fallback**, so
the first chapter is "Introduction" even on the ~30% of episodes where the LLM
rewrites the supplied intro. The Closing pattern covers both closing-pool
variants + the appended network promo.

Verified against all 10 committed scripts (loaded from the YAML, so escaping is
exercised): **10/10** parse Introduction-first, Closing-last, exactly one
Introduction, 4-6 chapters.

### P1 — closing pool vs prompt (FIXED, A/B)

`shows/prompts/unintended_consequences_podcast.txt:52` bans "That wraps today's
case"; `engine/intros.py:587-597` (old) had it as 1 of 2 pool entries. Which
closing actually shipped:

```
Ep019/020/023/024/025: "That wraps today's case"            (the banned phrase)
Ep021/022/026/027/028:  "That's Unintended Consequences for today"
```

Ep026-028 used the same closing three episodes running — the 2-entry pool + the
date-seeded `_pick` makes repeats-in-a-row common. **Fix** (`engine/intros.py`):
pool grown 2→4, banned phrase removed, every variant ends on a "tomorrow" signal
so the Closing chapter marker still matches. The prompt bullet (52) was
re-pointed at the LLM-controlled lesson close (the supplied sign-off can't be
varied by the model). A/B over 14 calendar days: 4 distinct closings (was 2),
banned phrase gone.

### P1 — chronic under-length (DEFERRED, carried forward)

Snapshot: ep019-028 ran 857-1211 words; `metrics_ep028.json` shows
`script_below_target: true`, `podcast_script_word_count: 1192`,
`audio_duration_s: 495.9` (~8.3 min). Digest bodies (the `.md` briefs) ran
703-958 words against the digest prompt's 1,500-2,200 target
(`unintended_consequences_episode.txt`). The podcast prompt forbids inventing
facts not in the brief, so the brief is the ceiling. The expansion retry is
already narrative-aware and fires every episode (`engine/generator.py:1853`),
but it can only deepen the thin brief.

**The lever is the digest, not the podcast.** A digest word-floor +
expansion-retry (mirroring the podcast one) is the same "next lever" the First
Principles review named and deferred. It's a generator change that touches all
shows and changes shipped audio — deferred to a network pass, not litigated in a
single-show review, and consistent with the operator's accepted grok-4.3
narrative-length plateau.

### P2 — supplied intro dropped ~30% (DOCUMENTED)

The first content line of ep023 ("Good to have you here. We're looking at a
case today…"), ep024 ("It's June fifth, two thousand twenty-six. Friday — let's
wrap the week…"), and ep027 ("It's June tenth… Today's case study…") contain no
brand name and no "episode N", despite the prompt's "use this exact intro (do
not rewrite it)". The brand-at-open is a minor consistency/discovery loss. Not
fixed: a missing-intro guard (prepend the resolved intro when absent) risks a
double-greeting because the LLM still writes *a* greeting. Documented for the
operator.

## Shipped

- Chapter markers rewritten (anchored + middle markers dropped) — **code-only,
  verified 10/10**. `shows/unintended_consequences.yaml`.
- Closing pool 2→4, banned phrase removed — **audio, A/B**. `engine/intros.py`.
- Prompt closing bullet re-pointed at the lesson close — **prompt, A/B**.
  `shows/prompts/unintended_consequences_podcast.txt`.
- Drift guards: `tests/test_unintended_consequences_quality_pass.py` (9 tests),
  and the superseded "That wraps today's case" needle updated in
  `tests/test_network_quality_pass.py`.

## ⚠️ A/B-listen required (landmine #17)

- **Closing pool wording** (`engine/intros.py`) — 3 new closing variants. Listen
  that each reads naturally on the custom voice `kdif6sqjcyiq`.
- **Podcast prompt closing bullet** (`unintended_consequences_podcast.txt`) —
  re-pointed guidance for the lesson's final beat. Renders clean
  (`test_prompt_fidelity.py`); listen that lesson closes still land.

The chapter-marker change is metadata-only and does **not** affect audio.

## Tests

```
tests/test_unintended_consequences_quality_pass.py  9 passed
tests/test_network_quality_pass.py                 30 passed (needle updated)
tests/test_chapters.py / test_episode_validity.py / test_generator.py /
  test_config.py / test_schedule.py / test_prompt_fidelity.py / test_intros.py / 
  test_unintended_consequences.py                  all passed
```

## Deferred recommendations (for the next pass)

1. **Digest-expansion retry** (the under-length lever) — add a digest word-floor
   + retry mirroring the podcast one. Network-scope, audio-affecting.
2. **Missing-intro guard** — only if the brand-at-open consistency proves to
   matter; needs a design that doesn't double-greet.
3. Once length improves, re-examine whether the podcast prompt's 2,200-2,800
   target should be lowered toward the real ~8-12 min plateau (avoid lowering it
   before the digest lever lands — it can only shrink output).
