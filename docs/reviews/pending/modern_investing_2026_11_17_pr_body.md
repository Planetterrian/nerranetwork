Market Pulse is still missing from every chapter rail, lifetime March-2026 totals still ride inside every Portfolio Performance (third miss), and EN scripts keep garbling Nerra/win-rate/names—while length, stops, and pick cadence hold.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.2264**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes whose chapter JSON includes a Market Pulse (or equivalent tape) chapter | miss | Ep225–234 chapter JSON: 0/10 title Market Pulse; index tape sits under Introduction or a cold-open headline |
| Portfolio Performance airings that recite full March-2026 lifetime trade count or cumulative $ as live scoreboard color | miss | Ep231–234 every PP speaks 104 trades and ~$221.12 beside era ~53-trade alpha |
| options picks that state live strike, expiry, and quoted premium on air (or option_quote_failed) | miss | No options structures in Ep231–234 (all Shares); quote-on-air path unexercised after Ep224 deferred premium |
| ticker/name garble incidents in EN _tts.txt (Interflex/XVI/Error 2/SNP-TSX class) | miss | Ep231 wind rate/Narin; Ep232 Andthropic/atheists/Narin; Ep233 Narrow/Karnie/President-G; Ep234 neodymium mangle/Narin |
| mit_non_medium_share_10ep sustained | partial | Ep232 COST Low; Ep231 STT / Ep233 ED / Ep234 MP Medium — not yet ≥0.2 sustained in packet |
| mit_stop_stated_share_10ep (dashboard) on 2026-11-14 | hit | Ep231–234 all speak percent-first stops with dollar caps (8%/$80 or 6%/$60) on air |
| Portfolio Performance airings that lead with the lifetime 87-trade figures or recite best/worst (hand-check 5) | miss | Lifetime 104-trade /$221 block still inside every Ep231–234 PP (best/worst quieter, blend remains) |
| spoken trade-review alpha equal to the tracker's alpha_pct (hand-check 5 episodes) | partial | Ep231 AMD +11.37% and Ep232 ESNT +0.27% matched-window alphas sound tracker-shaped; full ledger diff not in packet |
| segments per episode that teach volume>20-day confirmation | partial | Still in Practice setups (Ep231–233) but snapshot has no cross-ep exact tic; quieter than Ep221–224 multi-segment peak |
| mit_new_trade_share_10ep | hit | Ep231–234 each name a new weekly hold (STT, COST, ED, MP); drought machinery not re-tripped |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/modern_investing_podcast.txt`** (prompt) — P0 companion to hook strip: spoken contract so residual lifetime lines cannot be paraphrased back in. A/B-listen required (landmine #17).
```diff
- Report the record ONCE, in Portfolio Performance: the matched-window alpha, average per trade, with its trade count in the same sentence.
+ Report the record ONCE, in Portfolio Performance only: the era matched-window alpha and average per trade with the era trade count in the same sentence (rules-based restart). Do NOT speak lifetime totals since March, cumulative dollar P&L across the full history, pre-era best/worst, or any trade count other than the era n. If the briefing still contains lifetime figures, ignore them on air — they are not for the scoreboard sentence.
```

**`shows/prompts/modern_investing_podcast.txt`** (prompt) — P1: Ep231–234 repeatedly garble Nerra Network and occasional metrics/names. Verbatim locks + shape ban; no phonetic hacks (landmine #17). A/B-listen.
```diff
- PRONUNCIATION GUIDE:
- - Keep ALL acronyms in their standard written form (NASA, NATO, FBI, AI, EV, FSD, TFSA, RRSP, LLM, TSX, S&P, etc.)
- - Keep ALL proper nouns in their standard spelling (Starmer, Qwen, Xi Jinping, Musk, etc.)
- - DO NOT attempt phonetic spellings
+ PRONUNCIATION GUIDE:
+ - Keep ALL acronyms in their standard written form (NASA, NATO, FBI, AI, EV, FSD, TFSA, RRSP, LLM, TSX, S&P, etc.)
+ - Keep ALL proper nouns in their standard spelling (Starmer, Qwen, Xi Jinping, Musk, etc.)
+ - The network name is exactly "Nerra Network" every time — never Narin, Narrow, Naren, or Nerain.
+ - Say "win rate" not "wind rate" when reporting portfolio results.
+ - Chemical and multi-part material names (e.g. neodymium praseodymium) must match the briefing spelling; do not invent hyphenation.
+ - DO NOT attempt phonetic spellings
```

**`shows/prompts/modern_investing_digest.txt`** (prompt) — P1: Ep224 selected a covered call but deferred the premium; Ep231–234 returned to shares only. Require quote fields when options is chosen; zero estimated premium constraint unchanged. A/B-listen.
```diff
- **Structure:** [Shares / Covered Call / Cash-Secured Put — see THE TRADING RULES above. Use an options structure ONLY when the setup genuinely calls for one:
+ **Structure:** [Shares / Covered Call / Cash-Secured Put — see THE TRADING RULES above. When Structure is Covered Call or Cash-Secured Put, the briefing MUST include the live quoted strike, expiry, and bid/ask mid premium (or the exact token option_quote_failed if the chain could not be quoted). Never invent or estimate a premium. Use an options structure ONLY when the setup genuinely calls for one:
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/modern_investing.yaml`** (config): P0: Ep225–234 never emit Market Pulse because spoken tape leads with index closes, not the lexicon 'market pulse'. Widen matcher only — no audio change.
- **`shows/modern_investing.yaml`** (config): P0: Ep233 opens Trade Review at 60s on a 14-day narrative callback before Strategy. Require review-owned phrasing so callbacks cannot steal the chapter.
- **`shows/hooks/modern_investing.py`** (code): P0: Third consecutive miss on prompt-only PP lifetime bans (Oct 24, Nov 7, Ep231–234). Playbook escalate: strip the numbers from the prompt substrate so the model cannot recite them.

## Deferred (carried forward)
- Operator: run scripts/recompute_mit_benchmarks.py --apply after adjudicating 8 unreconciled pre-era trades (history cleanup; era on-air alpha already isolated)
- Operator: significance-qualifier accept-or-abandon (third miss; no fourth mechanism — do_not_retry)
- Operator: SnapTrade Phase-0 verification; keep LIVE_TRADING_ENABLED dormant until clean shadow+sim record
- Operator decision: volume>20-day multi-segment tic — data-side recent-episode MEMORY vs accept as house style (do not file a third prompt-only de-seed)
- Confidence mechanical grade only if forced High/Low variation carries no information after ~20 post-budget picks
- Listener feedback loop (inbox + triage) — product decision from Aug 20
- Feed measured shadow slippage into sim cost model once ~20 matched round trips
- HPS.A Ep150 flash open with no entry bar since 08-26 — needs void path
- Long-form YouTube retention ~7.8% and −59% WoW downloads — network video/discovery problem, not MIT-only prompt tweak
- Closing-price lesson family — already filtered as hygiene; leave retired
- Podcast-side length expand/retries — permanent do_not_retry network-wide
- Elevated fact-free script share (38–60%) — attack via denser digest substrate only, not podcast word pressure

<sub>tokens: 95572 in / 5870 out</sub>