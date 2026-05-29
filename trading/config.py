"""
Configuration for the MIT Webull Trading System.

This is separate from all podcast configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class TradingConfig:
    # Webull
    webull_email: str = ""
    webull_password: str = ""
    use_paper: bool = True

    # MIT Data Source (read-only)
    mit_data_dir: Path = Path("digests/modern_investing")

    # Risk Management (very conservative defaults)
    max_position_pct: float = 0.06          # Max 6% of equity per position
    max_daily_loss_pct: float = 0.012       # Stop trading if down 1.2% in a day
    max_open_positions: int = 4
    min_confidence: str = "high"            # Only trade high/very-high confidence

    # Live Trading Extra Guardrails (only matter when use_paper=False)
    live_size_multiplier: float = 0.4       # Use 40% of normal paper size in live
    require_manual_confirmation: bool = True
    max_live_daily_loss_pct: float = 0.008  # Even stricter in live

    # Strategy
    symbols: List[str] = field(default_factory=lambda: ["AAPL", "TSLA", "NVDA", "AMD", "META", "MSFT"])
    max_ideas_per_day: int = 2

    # Paper Trading Tracker (separate from podcast)
    paper_tracker_path: Path = Path("trading/paper_tracker.json")

    # Logging
    log_level: str = "INFO"


def load_config() -> TradingConfig:
    """Load from environment variables with sensible defaults."""
    import os
    from pathlib import Path as _Path

    cfg = TradingConfig()

    cfg.webull_email = os.getenv("WEBULL_EMAIL", "")
    cfg.webull_password = os.getenv("WEBULL_PASSWORD", "")
    cfg.use_paper = os.getenv("WEBULL_PAPER", "true").lower() != "false"

    # Allow override of MIT data directory
    mit_dir = os.getenv("MIT_DATA_DIR")
    if mit_dir:
        cfg.mit_data_dir = _Path(mit_dir)

    return cfg
