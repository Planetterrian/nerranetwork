Chapters collapse because the Practice Investment marker matches the disclaimer; scripts stay under-length on the digest ceiling (9/10 < 1800); Portfolio Performance still fuses unreproducible pre-era best/worst with the era alpha every episode; volume-confirmation remains the multi-segment tic; options structures still never selected.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1962**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| alpha figures spoken on air that come from the blended window (either block) | hit | Ep178–181 speak era −8.04% across 10 rules-based trades; no +9.28%/45 blend |
| index-sweep legs scored from different trade counts | hit | No multi-index sweep on air in Ep178–181; single NASDAQ matched-window leg only |
| median script words, last-10 snapshot (grok-4.6 readout) | miss | 4.6 reverted; median ~1588w, 9/10 scripts under 1800 floor |
| trades whose entry bar predates their pick date after a recompute dry run | hit | Matcher on/after-pick fix stands; dry run 0 backdated; --apply still not run |
| era trades whose hold is not exactly the policy horizon (or earlier stop-out) | partial | On-air framing is five-session horizon; occasional calendar-day wording remains |
| alpha figures spoken on air sourced from pre-era trades | partial | Headline alpha is era; pre-era best +20.11% / worst −11.80% still recited every PP |
| distinct confidence ratings used across the era's picks | partial | Ep180 Low + Ep179/181 Medium; High still absent, Medium dominates |
| picks carrying an Invalidation line | hit | Ep178 GOOGL, Ep179 Dollarama, Ep181 AEM state checkable invalidations |
| sim vs shadow exit-date disagreements | partial | Shared policy horizon shipped; no disagreement sample in this window |
| simulated trades using an options structure | miss | Still 0 options positions through Ep181; Structure remains Shares/monitoring |
| rules with enough evidence to be scored (>=5 trades on both arms) | partial | Era ~10 closed; both-arm floor not reached; scoreboard correctly stays unmeasured |
| episodes carrying the methodology correction | hit | Self-retired after 3 stamped airings; 0 in Ep178–181 |
| visits to modern-investing-performance.html in the 14 days after the correction airs | miss | No analytics evidence in review context; cannot confirm non-zero |
| episodes reading cumulative P&L / alpha in two segments (manual) | partial | Ep178–181 mostly single PP block; lifetime extremes still fused into that block every episode |
| script_repeated_facts per episode | miss | facts×2 still 0–8 in density audit (target ≤1) |
| a mechanic taught in two segments of one episode (manual) | miss | Volume>20-day still spans Strategy+Education+Practice+Tools (Ep178–180) |
| duplicate tail line around the disclosure | hit | Ep178–181 single close/gallery path; no doubled AI-voice gallery plug |
| verbatim airing of any of the three de-seeded lines, next 10 episodes | hit | None of cost-me-money / what-this-teaches-us / exactly-how-you-would-check in Ep178–181 EN |
| segments explaining the same mechanic (hand-count), 3 episodes | miss | Volume confirmation still ≥3 segments post Sep-6 fix |
| 'US' glued to a number word in any _tts.txt | partial | Bare $ amounts remain (Ep179 $4.48); fewer US$-glued forms than Ep162 |
| mit_new_trade_share_10ep (dashboard) on 2026-10-02 | partial | Ep178–181: 3 new picks + 1 none; improved vs 0.1 baseline, full 10-ep share not in snapshot |
| closed era trades added between 09-19 and 10-02 | partial | On-air era n=10 vs 9 at 09-18 (+1); behind ≥8 closed expectation mid-window |
| picks with an invalidation level and a confidence rating that is not Medium, first 10 picks after the merge | partial | Invalidations yes; non-Medium yes (Ep180 Low) but not yet ≥3/10 visible |
| sources on x.com per episode | partial | network-sourcing-pass-2026-09-24 just shipped; re-score next review |
| source_integrity_claims median | partial | Too early post fetch_full_text/preferred_domains; baseline was 0 |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/modern_investing_podcast.txt`** (prompt) — P0/P1: Ep178–181 still fuse disowned pre-era extremes into every PP beside honest era −8.04%/10; undoes the methodology honesty the show already taught.
```diff
- The portfolio-versus-NASDAQ record is REPORTED, not dramatized: the numbers, the trade count, the window — spoken once, in the Portfolio Performance segment.
+ The portfolio-versus-NASDAQ record is REPORTED, not dramatized: speak the ERA scoreboard only (matched-window alpha, era trade count, window start date) once, in Portfolio Performance. Do NOT recite lifetime cumulative P&L, lifetime win rate, or pre-era best/worst trades (+20.11% / −11.80% class) as if they were the live scoreboard — those are HISTORY ONLY and were removed from the on-air record because some cannot be tied to market bars. If history is mentioned at all, one short labelled clause max, never the extremes.
```

**`shows/prompts/modern_investing_system.txt`** (prompt) — System prompt still demands cumulative+alpha 'in the same breath' and fights the Sep 5 podcast discipline + era-scoped record; align instructions so the model stops fusing scoreboards.
```diff
- **BENCHMARK OBSESSION — NASDAQ COMPOSITE (^IXIC):**
- The single metric that matters for this show is whether the simulated portfolio is beating the NASDAQ Composite. The S&P 500 and the TSX Composite are context only. Every episode MUST:
- - State the NASDAQ Composite level in the Market Pulse segment and name the YTD move. (The cold open belongs to the day's hook — never open the episode on index levels.)
- - Report the portfolio's cumulative return and YTD return in the same breath.
- - Name the alpha — portfolio return MINUS NASDAQ return — in both YTD and since-inception windows. Be honest when the alpha is negative; that's when listeners learn the most.
- - Judge trades against the NASDAQ over the same holding window. A +4% pick during a +6% NASDAQ week is a LOSS in alpha terms — acknowledge it.
- If the pre-fetched ``benchmark_state`` block says data is unavailable, say so on air instead of inventing numbers.
+ **BENCHMARK OBSESSION — NASDAQ COMPOSITE (^IXIC):**
+ The single metric that matters for this show is whether the ERA simulated portfolio is beating the NASDAQ Composite over matched hold windows. The S&P 500 and the TSX Composite are context only. Every episode MUST:
+ - State the NASDAQ Composite level in the Market Pulse segment and name the YTD index move only. (Cold open = day's hook — never open on index levels. Market Pulse does NOT read portfolio P&L or alpha.)
+ - Report era matched-window alpha ONCE, in Portfolio Performance only, with the era trade count in the same sentence. Be honest when alpha is negative.
+ - Never present lifetime/inception blended totals or pre-era best/worst as the live scoreboard.
+ - Judge individual trades against the NASDAQ over the same holding window. A +4% pick during a +6% NASDAQ window is a LOSS in alpha terms — acknowledge it.
+ If the pre-fetched ``benchmark_state`` block says data is unavailable, say so on air instead of inventing numbers.
```

**`shows/prompts/modern_investing_podcast.txt`** (prompt) — P1: Sep 5/6 one-mechanic predictions missed; Ep178–180 still teach volume>20-day across ≥3 segments. De-seed by shape + ban, not a new example sentence (ledger lesson).
```diff
- - TEACH ONE THING per episode, once. One mechanic is taught in one segment; no other segment re-teaches it from a different angle.
+ - TEACH ONE THING per episode, once. One mechanic is taught in one segment; no other segment re-teaches it from a different angle.
+ - VOLUME CONFIRMATION SHAPE BAN: do not re-explain 'require volume above the 20-day average before entry' outside the single segment that owns today's lesson. Paraphrases count (same-day volume check, 20-day line, volume filter on catalyst entries). If that rule is already stated in Strategy Spotlight, Practice/Tools/Education must not restate it — apply it in one clause max without re-teaching. Ban rotating the same volume lecture through five segments.
```

**`shows/modern_investing.yaml`** (config) — P1 length: 9/10 scripts under 1800 with high digest coverage — substrate ceiling. Podcast expand stays false (network ban). Bump digest floor only; A/B-listen resulting episodes for padding/duplication.
```diff
-   digest_expand_below_target: true
-   min_digest_words: 1500
+   digest_expand_below_target: true
+   min_digest_words: 1700
```

**`shows/prompts/modern_investing_digest.txt`** (prompt) — Options prediction missed through 36+ episodes with zero option_quote_failed — model never attempts structure. Soft should-when-fits nudge; premium still never estimated.
```diff
- **Structure:** [Shares / Covered Call / Cash-Secured Put — see THE TRADING RULES above. Use an options structure ONLY when the setup genuinely calls for one: a covered call when you want income on a name you would be content to have called away near the strike, a cash-secured put when you would be content to own the name lower. Do not reach for options to look sophisticated, and do not use one when a directional view is the actual thesis — a covered call caps exactly the upside a momentum thesis is trying to capture. Default to Shares.]
+ **Structure:** [Shares / Covered Call / Cash-Secured Put — see THE TRADING RULES above. Default to Shares for directional momentum/catalyst theses. When today's thesis is income, neutral-to-slightly-bullish ownership, or 'willing to own lower', you SHOULD prefer Covered Call or Cash-Secured Put and quote a real live chain (strike, expiry 21–45d, premium) — if the chain cannot be quoted, degrade to Shares and record option_quote_failed. Do not reach for options to look sophisticated; do not use a covered call when the actual thesis needs uncapped upside.]
```

**`shows/prompts/modern_investing_podcast.txt`** (prompt) — P1: Ep181 shipped 'current street is 1 win' and 'fold at the open'; Ep178 'RRSNP' — listener-facing garble without phonetic hacks (landmine #17).
```diff
- - Spell out ticker-related numbers: "trading at two hundred fifteen dollars" not "trading at $215"
+ - Spell out ticker-related numbers: "trading at two hundred fifteen dollars" not "trading at $215"
+ - Homophone hygiene: write "streak" not "street" for win/loss streaks; "filled" not "fold" for order fills; "RRSP" never "RRSNP"; never leave a stray label word like "image" before "Imagine".
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/modern_investing.yaml`** (config): P0: bare 'simulated trade' / early 'practice investment' match the financial disclaimer, so chapters mark Practice Investment immediately after Introduction and swallow Market Pulse/Strategy/Education (Ep172–176 chapter files).

## Deferred (carried forward)
- Operator: run scripts/recompute_mit_benchmarks.py --apply after adjudicating 8 unreconciled pre-era trades (history cleanup; no longer contaminates era on-air alpha)
- Operator: significance-qualifier accept-or-abandon (third miss; no fourth mechanism per playbook)
- Operator: SnapTrade Phase-0 verification; keep LIVE_TRADING_ENABLED dormant until clean shadow+sim record
- Confidence calibration redesign if High remains 0 after no-trade budget matures (~25 era trades)
- HPS.A Ep150 flash open with no entry bar since 08-26 — needs void path
- Listener feedback loop (inbox + triage) — product decision from Aug-20
- Feed measured shadow slippage into sim cost model once ~20 matched round trips
- Long-form YouTube retention ~15% — network video problem, not MIT-only prompt tweak
- Closing-price lesson family — already filtered as hygiene; leave retired
- Podcast-side length expand/retries — permanent do_not_retry network-wide

<sub>tokens: 77943 in / 6724 out</sub>