# MIT Webull Trading System (Separate Module)

**Goal**: Use the exact same recursive learning loop developed for the "Modern Investing Techniques" podcast to trade real capital (starting with paper) on Webull, with the explicit objective of beating the NASDAQ over time.

## Philosophy

The MIT podcast has built one of the most sophisticated public recursive improvement systems in retail investing:

- Live investment tracker with P&L, alpha, sector exposure
- 30+ active lessons learned from real simulated trades
- Taught lessons with cooldowns (prevents repeating recent mistakes)
- Derived operating principles
- Confidence calibration data

This module treats that system as **prior art / training data** and applies it to actual (paper then live) trading.

## Current State (Functional Paper Trading)

You can now:

1. Load the full MIT recursive context
2. Generate trade ideas that respect past lessons
3. Apply strict risk rules
4. Execute paper trades on Webull
5. Record results in a dedicated `paper_tracker.json`

## Quick Start (Paper Trading)

```bash
# 1. Install dependency
pip install webull

# 2. Set credentials (use a dedicated paper account!)
export WEBULL_EMAIL="your@email.com"
export WEBULL_PASSWORD="yourpassword"

# 3. Dry run first (highly recommended)
python -m trading.runner --paper --dry-run --symbols AAPL,TSLA,NVDA

# 4. Actually place paper trades
python -m trading.runner --paper --symbols AAPL,TSLA,NVDA
```

## Recommended Path to Live Trading

### Phase 1: Paper Validation (Minimum 30-60 trading days)
- Run the system daily on paper
- Manually review every decision against the MIT lessons
- Track performance vs NASDAQ in `paper_tracker.json`
- Only proceed when you have statistical confidence (e.g. 30+ trades with positive alpha)

### Phase 2: Small Live Money
- Start with very small position sizes (1-2% risk per trade max)
- Use the most conservative settings in `config.py`
- Require "very high" confidence only
- Keep detailed journal comparing paper vs live behavior

### Phase 3: Scale
- Only after consistent outperformance over many months
- Gradually increase size while monitoring drawdowns

## Key Files

| File                    | Purpose |
|-------------------------|---------|
| `config.py`             | Risk parameters, symbols, Webull settings |
| `webull_client.py`      | Clean interface to Webull (paper + live) |
| `mit_context.py`        | Loads all MIT recursive data |
| `paper_tracker.py`      | Records actual executed paper trades |
| `strategy.py`           | Decision engine (currently basic - improve this) |
| `risk.py`               | Hard risk gates |
| `runner.py`             | Main daily trading loop |

## Important Safety Features (Already Implemented)

- Paper trading is the default
- Position size limits as % of equity
- Daily loss circuit breaker
- Minimum confidence gates
- MIT lesson references attached to every idea

## Documentation

For **detailed, step-by-step instructions**, please read:

→ **`trading/DETAILED_USAGE_AND_SETUP_GUIDE.md`**

This is the primary guide covering:
- Webull paper account setup
- Secure credential management
- First run workflow (dry-run → paper trading)
- Monitoring and performance review
- Validation checklist before going live
- Recommended daily/weekly process
- Troubleshooting

## Current Capabilities (as of latest updates)

- Edge-based position sizing (Kelly + volatility adjusted)
- Regime awareness and drawdown de-risking
- Strong use of MIT lessons, taught lessons cooldowns, and winning patterns
- Separate paper trading tracker
- Performance + lesson attribution reporting
- Statistical go-live validation gates
- Position reconciliation framework

## Disclaimer

This is experimental. The MIT podcast trades are simulated. Adapting the logic to real capital carries significant risk of loss. You are fully responsible for all outcomes. Start exclusively with paper trading and validate rigorously.
