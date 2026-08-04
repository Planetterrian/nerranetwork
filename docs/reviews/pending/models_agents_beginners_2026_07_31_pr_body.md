Eight of ten episodes still under the 1200-word floor (digest ceiling—escalate, do not re-litigate podcast levers); live tics are the Deep Dive handoff “okay now for my favorite part… under the hood” (8/10), the third-generation closer “stops/less like magic” (5/10), and the opener-menu echo “Here’s something that…change/reshape” (4/10); ep112/ep119 ship without a Closing chapter and ep119’s cold open drops the identity line entirely.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1045**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| "not so scary, right?" / verbatim three-sentence Deep Dive closer (last 10) | hit | 0/10 in ep110–119 transcripts; replaced by magic/mysterious closer successor |
| Big Story openers using "Something [adj] just happened", last 10 | hit | 0/10; model converged on "Here's something that…change/reshape" (4/10) instead |
| median _tts.txt words, last 10 eps (June 25 no-regression) | hit | median ≈1089 on ep110–119; still under floor but no further regression |
| episodes with a "The Big Story" chapter, last 10 | hit | still 0/10 as the documented deferral predicted |
| episodes with a double-spoken closing (guard false-fire) | hit | 0/10 ep110–119; each ep has a single wrap/that's-it-for-today |
| episodes with repeated boilerplate outro phrases (last 10) after de-seed | miss | still 10/10 — July 30 de-seed never applied; strings are intentional network outro+AI disclosure anyway |
| median _tts.txt words (last 10) no-regression (July 30) | hit | median ≈1089 vs baseline ~1050; 8/10 still under 1200 floor |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/mab_podcast.txt`** (prompt) — 8/10 transcripts share the same Deep Dive handoff; de-seed by shape + verbatim ban + MEMORY per July 2026 meta-review (never seed a replacement example).
```diff
- Any seeded handoff into Deep Dive that looks like: "Okay, now for my favorite part of the show" / "where we look under the hood" / "the deep dive where we unpack…" (exact prompt lines vary; ban the spoken shape that 8/10 transcripts converge on).
+ Deep Dive handoff — shape only, zero quotable stems:
+ - Transition from Big Story into the explainer with a FRESH one-sentence bridge each episode (name the concept you are about to open, or pose the listener question the explainer answers).
+ - BANNED as verbatim (overused across recent episodes — do not reuse, do not lightly rephrase): "okay now for my favorite part of the show", "my favorite part of the show", "where we look under the hood", "look under the hood", "slow down and see how one piece of this technology actually works under the hood".
+ - Do NOT substitute a new stock phrase (no "let's pop the hood", "time to open it up", "here's the fun part"). If a stem appeared in recent episodes' MEMORY do-not-reuse list, pick a different bridge.
```

**`shows/prompts/mab_podcast.txt`** (prompt) — June-25 de-seed HIT but spawned the magic/mysterious closer in 5/10 recent eps (July-2 caveat confirmed); ban the successor shape and predict the next tic.
```diff
- Deep Dive closer guidance that still permits the reassuring-payoff template to collapse into magic/mysterious wording (post June-25 'not so scary' ban).
+ Deep Dive closer — keep the method (analogy lands; listener could restate the idea), ban the third-generation tic:
+ - End the explainer by connecting the analogy back to the real system in one fresh sentence, then one beat of earned reassurance.
+ - BANNED as verbatim / near-paraphrase: "not so scary, right?", "so next time someone says… you can tell them", "stops feeling like magic", "stops feeling mysterious", "less like magic and more like", "starts feeling like magic".
+ - Do not end on a stock "once you see it…" sentence. Reach the payoff with wording that could only fit THIS episode's analogy.
```

**`shows/prompts/mab_podcast.txt`** (prompt) — 4/10 eps now open on the prompt-menu echo 'Here's something that…change/reshape'; third consecutive opener tic from quotable examples — rewrite with zero quotable strings.
```diff
- Big Story opener rotation menu that still contains quotable stems the model elects (prior menus produced 'So imagine' → 'Something [adj] just happened' → 'Here's something that…change').
+ Big Story opener — SHAPE menu only, zero quotable example strings:
+ - Pick one shape per episode and write a fresh line that could only open THIS story: (a) cold concrete fact with a number or named system, (b) named-person or named-lab beat, (c) listener-moment the audience has lived, (d) contrast with how the same task worked last year.
+ - BANNED as verbatim / light rephrase (recent-episode overuse): "So imagine…", "Something [adj] just happened", "Here's something that's going to change…", "Here's something that could change…", "Here's something that could reshape…", "that's going to change how you", "could change how you".
+ - Never paste an example opener into the prompt body. If MEMORY lists a stem from recent episodes, do not reuse it.
```

**`shows/prompts/mab_podcast.txt`** (prompt) — July 31 cold-open (`voice_intro_delay: 0.0`) correctly kills the 10s wait, but ep119 dropped identity entirely and lost the Welcome chapter; prompt must require the anchor the YAML already matches on.
```diff
- Cold-open / intro guidance that allows a pure hook with no show identity line (ep119 shipped with neither 'Welcome to' nor 'This is Models and Agents for Beginners').
+ Cold open (hook first, music under):
+ - Sentence 1–3: the episode hook (no greeting, no 'welcome').
+ - Then EXACTLY one identity line before the Big Story body, matching a Welcome chapter anchor, e.g. shape: state the show name + episode number + date. Required every episode so chapters and new listeners can orient.
+ - BANNED: skipping the identity line; rewriting it into a joke or paraphrase that drops the show name.
```

**`shows/prompts/mab_digest.txt`** (prompt) — June 25 root cause was double-seeding from digest+podcast; keep both prompts aligned when de-seeding.
```diff
- Any Deep Dive closer / handoff example strings that still mirror the podcast bans ('under the hood', 'not so scary', 'stops feeling like magic', 'so next time someone says').
+ Mirror the podcast bans in the digest Deep Dive section: no verbatim handoff stems, no magic/mysterious closer, no 'not so scary' / 'so next time someone says' formulas. Digest feeds the podcast explainer — double-seeding is how the June-25 tic locked in 9/10.
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_mab_quality_pass.py`** (code): Every behavioral prompt fix needs a drift-guard per playbook; pins the three new de-seeds + identity-line requirement.
- **`shows/models_agents_beginners.yaml`** (config): ep119 is post-pattern-widen and still has no Closing chapter; guessing more regex synonyms is how this file accreted. Verify the path first (code/config diagnosis, not audio change).

## Deferred (carried forward)
- Chronic under-length: ESCALATE to operator — raise min_digest_words / licensed-knowledge floors / full-text fetch, OR lower min_podcast_words to accept ~1000–1100-word beginner eps. Do NOT re-propose podcast_expand or word-floor pressure (network do_not_retry; June 25 miss + July 30 still under).
- "The Big Story" chapter missing every episode — dead big-story|biggest news marker; needs network digest-driven / position-aware chapter titles.
- Auto-segment raw-sentence chapter titles (ep110/113/116/119) — same digest-driven-titles lever.
- MAB pronunciation hook phonetic respellings (SOTA/LoRA/ONNX/…) — 0 transcript impact; align with sister M&A (letter-spellings only) on an A/B slot; landmine #17.
- "Try this" items ineligible unless the tool is NAMED in the source (July 2; still intermittent).
- Quick Bits ≤3 sentences / every sentence a new fact (July 2 A/B, not applied).
- Light "think of it like" / "another way to picture it" analogy-stem overuse (6/10) — only after the three harder tics clear.

<sub>tokens: 34464 in / 5929 out</sub>