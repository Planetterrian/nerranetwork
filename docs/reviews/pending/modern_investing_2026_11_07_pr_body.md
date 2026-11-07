Oct 24 stop/options/confidence levers partially landed (stops readable, first covered call on air in Ep224, Low grades appearing) while Market Pulse is still missing from chapters, lifetime history still rides in Portfolio Performance, and volume>20-day remains a multi-segment tic.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.2249**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| mit_stop_stated_share_10ep (dashboard) on 2026-11-14 | partial | Ep221–224 speak readable 8% stops with $80 cap on air; dashboard series not in this packet |
| mit_non_medium_share_10ep (dashboard) on 2026-11-14 | partial | Ep224 IBM Low; Ep221–223 Medium — variety started, not yet ≥0.2 sustained |
| options structures among the first 15 picks after merge | hit | Ep224 IBM covered call on air with structure + early-assignment caveat (first options hit after 0/103 baseline) |
| spoken trade-review alpha equal to the tracker's alpha_pct (hand-check 5 episodes) | partial | Ep221 TD +3.25%, Ep223 PEY.TO −2.16%, Ep224 KMP.UN +7.33% sound tracker-shaped; full 5-ep JSON diff not in context |
| era closed trades carrying entry_volume_ratio_20d and sessions_held on 2026-11-01 | partial | five-session / sessions_held framing on air; factor columns not visible in this packet |
| Portfolio Performance airings that lead with the lifetime 87-trade figures or recite best/worst (hand-check 5) | miss | Ep221–224 every PP still recites full March-2026 history (95→98 trades, cumulative $) beside era alpha |
| episodes whose chapters jump Practice Investment earlier than Market Pulse (disclaimer match) | hit | Ep215–224 Practice no longer opens off the disclaimer; Sep/Oct pattern fix held |
| segments per episode that teach volume>20-day confirmation | miss | Ep221/222/224 still spread 20-day/20-session volume across Strategy+Practice+Education |
| mit_new_trade_share_10ep | hit | Ep221–224 each carry a new weekly hold (PLTR, EFX, CP.TO, IBM); drought not re-tripped |
| median script words last-10 after digest floor bump (if applied) | hit | Ep215–224 all 1933–2440w; 10/10 clear 1800 floor under grok-4.6 script stage |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/modern_investing_podcast.txt`** (prompt) — P0: Oct 24 PP lifetime prediction missed — Ep221–224 still air 95–98-trade March history beside era alpha every episode. Third miss class on blend leakage; tighten the spoken contract.
```diff
- Report the record ONCE, in Portfolio Performance: the matched-window alpha, average per trade, with its trade count in the same sentence.
+ Report the record ONCE, in Portfolio Performance: the ERA matched-window alpha and era trade count only, in one breath. Do NOT recite the full March-2026 lifetime trade count, lifetime cumulative P&L, or pre-era best/worst as scoreboard color. If history is mentioned at all, it is one short clause explicitly labelled as history that cannot test this method — never adjacent numbers that listeners can fuse with the era alpha.
```

**`shows/prompts/modern_investing_digest.txt`** (prompt) — P1: Ep224 finally selected a covered call (options prediction HIT) but deferred the premium to the listener — half the demonstration the live-quote path exists for. Keep zero-estimated-premium constraint; require the quote on air.
```diff
- Use an options structure ONLY when the setup genuinely calls for one: a covered call when you want income on a name you would be content to have called away near the strike, a cash-secured put when you would be content to own the name lower.
+ Use an options structure ONLY when the setup genuinely calls for one: a covered call when you want income on a name you would be content to have called away near the strike, a cash-secured put when you would be content to own the name lower. When Structure is Covered Call or Cash-Secured Put, the digest MUST state the live listed strike, listed expiry, and bid/ask mid premium quoted at pick time (or record option_quote_failed and degrade to shares). Never omit the premium and tell the listener to look it up; never estimate a premium.
```

**`shows/prompts/modern_investing_podcast.txt`** (prompt) — P1: Ep222 Interflex/inner flex, Ep224 XVI and Error 2, Ep221 SNP-TSX and 'of 0.4%' — listener-facing garble without phonetic hacks (landmine #17).
```diff
- Keep ALL proper nouns in their standard spelling (Starmer, Qwen, Xi Jinping, Musk, etc.)
+ Keep ALL proper nouns in their standard spelling (Starmer, Qwen, Xi Jinping, Musk, etc.). On first mention of a ticker, say the letter names when the spoken form is ambiguous (E-F-X for EFX / Enerflex; X-E-I for XEI). Always say 'Era 2' or 'rules-based era', never 'Error 2'. Never substitute a near-homophone company name (Enerflex not Interflex). Index labels stay 'S&P TSX' / 'S&P 500' / 'NASDAQ' — never 'SNP-TSX'. Direction words on index moves are mandatory ('up 0.4 percent', never bare 'of 0.4 percent').
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/modern_investing.yaml`** (config): P0: Ep215–224 never emit a Market Pulse chapter because spoken pulse leads with index tape ('Wall Street finished', 'Friday's closes left', 'S&P TSX composite fell') not the lexicon 'market pulse'. Widen the matcher only — no audio change.

## Deferred (carried forward)
- Operator: run scripts/recompute_mit_benchmarks.py --apply after adjudicating 8 unreconciled pre-era trades (history cleanup; era on-air alpha already isolated)
- Operator: significance-qualifier accept-or-abandon (third miss; no fourth mechanism — do_not_retry)
- Operator: SnapTrade Phase-0 verification; keep LIVE_TRADING_ENABLED dormant until clean shadow+sim record
- Operator decision: volume>20-day multi-segment tic after three miss windows — data-side recent-episode MEMORY vs accept as house style (do not file a third prompt-only de-seed)
- Confidence mechanical grade only if forced High/Low variation carries no information after ~20 post-budget picks
- Listener feedback loop (inbox + triage) — product decision from Aug 20
- Feed measured shadow slippage into sim cost model once ~20 matched round trips
- HPS.A Ep150 flash open with no entry bar since 08-26 — needs void path
- Long-form YouTube retention ~8.4% — network video problem, not MIT-only prompt tweak
- Closing-price lesson family — already filtered as hygiene; leave retired
- Podcast-side length expand/retries — permanent do_not_retry network-wide

<sub>tokens: 97481 in / 4998 out</sub>