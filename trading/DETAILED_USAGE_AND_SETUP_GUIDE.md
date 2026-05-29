# Detailed Setup & Usage Guide: MIT Webull Trading System

**Goal**: Use the MIT (Modern Investing Techniques) recursive learning system to trade on Webull, starting with paper money, with the long-term objective of beating the NASDAQ.

**IMPORTANT DISCLAIMER**  
This system is experimental. Trading involves substantial risk of loss. The MIT podcast uses simulated trades. There is no guarantee that adapting this logic to real capital will be profitable. You are fully responsible for any financial losses. Start with paper trading only.

---

## Table of Contents
1. Prerequisites
2. Creating a Webull Paper Trading Account
3. Installing Dependencies
4. Setting Up Credentials Securely
5. Understanding the Module Structure
6. Configuration
7. First Run (Dry Run)
8. Running Paper Trades
9. Monitoring Performance
10. Interpreting Output and Logs
11. Validation Checklist Before Going Live
12. Transitioning to Small Live Money
13. Daily/Weekly Workflow
14. Troubleshooting
15. Safety Best Practices

---

## 1. Prerequisites

- Python 3.9+
- A Webull account (you will need to open a **separate paper trading account** first)
- Basic understanding of the MIT podcast's concepts (lessons learned, investment tracker, etc.)
- Comfort with command line / terminal

---

## 2. Creating a Webull Paper Trading Account

1. Go to [https://www.webull.com](https://www.webull.com)
2. Create or log into your main account.
3. Navigate to **Paper Trading** (usually in the menu or under "Trade" → "Paper Trading").
4. Open a paper trading account if you haven't already. This gives you virtual money (usually $100,000 or more) to practice with.
5. **Strongly recommended**: Use a completely separate email or a dedicated Webull login for paper trading experiments.

**Note**: The unofficial `webull` Python library has some quirks with paper accounts. You may need to log in via the web/paper interface first before using the API.

---

## 3. Installing Dependencies

```bash
cd /path/to/Tesla-shorts-time

# Install the required unofficial Webull library
pip install webull

# (Optional but recommended) Create a virtual environment first
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install webull
```

---

## 4. Setting Up Credentials Securely

The system reads credentials from environment variables.

**Recommended approach** (do **not** hardcode passwords):

### On macOS / Linux

Add to your `~/.zshrc` or `~/.bash_profile`:

```bash
export WEBULL_EMAIL="your_paper_account@email.com"
export WEBULL_PASSWORD="your_password"
export WEBULL_PAPER="true"          # Set to "false" only when ready for live
```

Then reload:

```bash
source ~/.zshrc
```

### On Windows (PowerShell)

```powershell
$env:WEBULL_EMAIL = "your_paper_account@email.com"
$env:WEBULL_PASSWORD = "your_password"
$env:WEBULL_PAPER = "true"
```

For permanent storage on Windows, use the System Environment Variables dialog or a `.env` file + `python-dotenv`.

**Security Note**: Never commit credentials to git.

---

## 5. Understanding the Module Structure

Key files you will interact with:

| File                        | Purpose |
|----------------------------|---------|
| `runner.py`                | Main daily trading script |
| `config.py`                | Risk parameters and settings (loaded from env + defaults) |
| `webull_client.py`         | Interface to Webull (quotes, orders, account) |
| `mit_context.py`           | Loads your existing MIT recursive data |
| `paper_tracker.py`         | Records your actual paper trades (separate from podcast) |
| `performance_reporter.py`  | Shows how your paper trading is doing vs NASDAQ |
| `risk.py` + `position_sizing.py` | Risk and sizing logic |
| `validation.py`            | Checks whether you're ready for live trading |

---

## 6. Configuration

Most configuration lives in `trading/config.py` and is overridable via environment variables.

Important settings (with safe defaults):

- `max_position_pct`: 6% of equity per position (hard cap)
- `max_daily_loss_pct`: 1.2% — stops new trades if breached
- `live_size_multiplier`: 0.4 (live positions are 40% the size of paper)
- `require_manual_confirmation`: True (you must type confirmation for live trades)
- `symbols`: List of tickers the strategy will consider

You can override many of these via environment variables if desired.

---

## 7. First Run – Always Use Dry Run

**Never place real orders on your first few runs.**

```bash
# Recommended first command
python -m trading.runner --paper --dry-run --symbols AAPL,TSLA,NVDA,AMD,META
```

What this does:
- Loads your current MIT lessons and tracker
- Generates trade ideas using the recursive logic
- Shows you the sizing it *would* use
- Does **not** place any orders

Review the output carefully. Look at:
- Which lessons are being referenced
- What the system is avoiding (due to cooldowns)
- The proposed position sizes

---

## 8. Running Actual Paper Trades

Once you're comfortable with the dry-run output:

```bash
python -m trading.runner --paper --symbols AAPL,TSLA,NVDA,AMD,META
```

The system will:
1. Log into Webull paper trading
2. Load MIT context
3. Generate ideas
4. Apply risk rules (including Kelly + volatility sizing)
5. Place paper orders on Webull
6. Record the trades in `trading/paper_tracker.json`

---

## 9. Monitoring Performance

After running for a while:

```bash
python -m trading.performance_reporter
```

This shows:
- Win rate, P&L, approximate alpha vs NASDAQ
- Which MIT lessons are being used most often in your actual trades

Use this to see if the recursive loop is working in real market conditions.

---

## 10. Interpreting Output

Look for these key sections in the logs:

- `MIT Context loaded` → Shows how many trades and what alpha the system currently has.
- `APPROVED` / `REJECTED` → Why the risk system allowed or blocked a trade.
- `Sizing for XXX` → Shows Kelly + volatility + regime adjustments.
- `Paper order placed` → Successful paper execution.

---

## 11. Validation Checklist Before Going Live

**Do NOT switch to live money until all of these are true:**

- [ ] At least 40–50 closed paper trades
- [ ] Positive alpha vs NASDAQ over the full period
- [ ] Win rate meaningfully above 50% with decent sample
- [ ] Maximum drawdown stayed reasonable (< 8–10%)
- [ ] You have manually reviewed the last 15–20 trades and agree with the reasoning
- [ ] You have survived at least one difficult market period (e.g. sharp selloff)
- [ ] The `validation.py` gate would allow live trading
- [ ] You are emotionally prepared to lose the entire small live allocation

---

## 12. Transitioning to Live (Very Small Size)

When ready:

1. Edit or override:
   - `live_size_multiplier = 0.3` or lower
   - `require_manual_confirmation = True`
   - Consider reducing `max_position_pct`

2. Run with:
   ```bash
   python -m trading.runner --paper=false   # or set WEBULL_PAPER=false
   ```

3. Start extremely small (e.g. $500–$2000 risk per trade max).

4. Keep running the paper version in parallel for comparison.

---

## 13. Recommended Daily / Weekly Workflow

**Daily:**
- Morning dry-run review
- Decide whether to let it trade that day
- Quick look at open positions

**Weekly:**
- Run `performance_reporter`
- Review all trades from the week against the MIT lessons
- Note any patterns the system is missing

**Monthly:**
- Deep review of alpha, drawdowns, and lesson effectiveness
- Decide whether to adjust risk parameters

---

## 14. Troubleshooting

**Login fails / MFA issues**
- Log into the Webull web/paper platform manually first.
- The unofficial library sometimes needs you to have an active session.

**No trades being generated**
- The strategy is very conservative by design when there isn't strong MIT edge.
- Check the MIT data – if alpha is negative, it will be very picky.

**"Everything up-to-date" or no output**
- Make sure you're in the project root when running `python -m trading.runner`

---

## 15. Safety Best Practices

- Never risk money you cannot afford to lose.
- Paper trade for a long time (minimum 3–6 months of consistent use).
- Keep the paper version running even after going live.
- Have a written plan for when you will reduce size or stop (e.g. 3 consecutive losing months, drawdown > 12%, etc.).
- Review every single live trade against the MIT reasoning for the first 3–6 months.

---

**Final Advice**

The power of this system comes from the *recursive loop*, not from any single trade. Treat the first 6–12 months primarily as data collection and validation, not as profit generation.

Start small. Stay disciplined. Let the data (and the lessons) speak.

Good luck.
