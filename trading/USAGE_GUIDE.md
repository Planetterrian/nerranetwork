# MIT Webull Trading - Usage & Validation Guide

## Daily Paper Trading Workflow

1. **Morning (before market open)**
   ```bash
   python -m trading.runner --paper --dry-run
   ```

2. **Review the ideas** the system generated using current MIT lessons.

3. **Run for real (paper execution)**
   ```bash
   python -m trading.runner --paper
   ```

4. **End of day / next morning**
   ```bash
   python -m trading.performance_reporter
   ```

## Moving from Paper to Live (Validation Checklist)

Only consider live money when ALL of the following are true:

- [ ] Minimum 40 closed paper trades
- [ ] Positive alpha vs NASDAQ over the full period
- [ ] Win rate ≥ 52% with reasonable sample size
- [ ] Max drawdown in paper book stayed under 8%
- [ ] You have manually reviewed the last 15 trades and agree with the MIT reasoning
- [ ] You have run the system through at least one full market regime change (e.g. correction or strong rally)
- [ ] You are emotionally comfortable losing the entire small live allocation

## Recommended Live Parameters (when ready)

In `config.py`:
- `max_position_pct = 0.03` (3%)
- `live_size_multiplier = 0.35`
- `require_manual_confirmation = True`
- `min_confidence = "very high"` (if you add that level)

## Emergency Commands

```python
from trading.webull_client import WebullClient
client = WebullClient(paper=False)  # or True
client.login(...)
client.close_all_paper_positions()   # or implement live version
```

Start small. Validate relentlessly. The goal is not to trade — the goal is to prove the recursive loop works in real conditions before risking meaningful capital.
