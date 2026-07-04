"""Drift guards for the SnapTrade execution layer (Phase 1, July 2026).

Pins the isolation + privacy contract from
docs/mit_snaptrade_live_trading_plan.md:

* the podcast path never imports ``execution/`` (the trade-signal
  artifact is the only bridge);
* Phase 1 is read-only — no order-placing code exists in the package;
* the account mirror masks account numbers and its output file is
  gitignored (public repo: balances are never committed);
* everything is a clean no-op until the SNAPTRADE_* env vars are set.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest  # noqa: F401 (used by the Phase-2 tests below)

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution import mirror as mirror_mod  # noqa: E402
from execution import snaptrade_client as st  # noqa: E402


class TestIsolationContract:
    def test_podcast_path_never_imports_execution(self):
        # The signal artifact is the ONLY bridge between the podcast
        # pipeline and the execution layer.
        offenders = []
        for path in ["run_show.py", "engine", "shows"]:
            p = _ROOT / path
            files = [p] if p.is_file() else sorted(p.rglob("*.py"))
            for f in files:
                text = f.read_text(encoding="utf-8")
                if "from execution" in text or "import execution" in text:
                    offenders.append(str(f.relative_to(_ROOT)))
        assert offenders == [], (
            f"podcast-path files import execution/: {offenders}")

    def test_phase1_has_no_order_placement_code(self):
        # Trading code arrives in a later phase behind its own risk layer.
        for f in sorted((_ROOT / "execution").rglob("*.py")):
            text = f.read_text(encoding="utf-8").lower()
            assert "place_order" not in text and "placeforceorder" not in text, (
                f"{f.name} contains order-placement code — Phase 1 is "
                f"read-only by contract")

    def test_mirror_output_is_gitignored(self):
        # Public repo: balances/positions must never be committable.
        result = subprocess.run(
            ["git", "check-ignore",
             "digests/modern_investing/live_account_mirror.json"],
            cwd=_ROOT, capture_output=True, text=True)
        assert result.returncode == 0, (
            "live_account_mirror.json is not gitignored — a mirror run "
            "would commit account balances to a public repo")


class TestConfigGating:
    def test_unconfigured_env_reports_missing(self, monkeypatch):
        for key in ("SNAPTRADE_CLIENT_ID", "SNAPTRADE_CONSUMER_KEY",
                    "SNAPTRADE_USER_ID", "SNAPTRADE_USER_SECRET"):
            monkeypatch.delenv(key, raising=False)
        assert st.is_configured() is False
        assert len(st.missing_config()) == 4

    def test_configured_when_all_set(self, monkeypatch):
        for key in ("SNAPTRADE_CLIENT_ID", "SNAPTRADE_CONSUMER_KEY",
                    "SNAPTRADE_USER_ID", "SNAPTRADE_USER_SECRET"):
            monkeypatch.setenv(key, "x")
        assert st.is_configured() is True

    def test_mirror_script_noop_without_config(self, monkeypatch):
        for key in ("SNAPTRADE_CLIENT_ID", "SNAPTRADE_CONSUMER_KEY",
                    "SNAPTRADE_USER_ID", "SNAPTRADE_USER_SECRET"):
            monkeypatch.delenv(key, raising=False)
        result = subprocess.run(
            [sys.executable, "scripts/snaptrade_mirror.py"],
            cwd=_ROOT, capture_output=True, text=True, env={
                "PATH": "/usr/bin:/bin:/usr/local/bin",
            })
        assert result.returncode == 0
        assert "no-op" in (result.stdout + result.stderr)


class TestMirrorBuilder:
    _ACCOUNTS = [{
        "id": "acc-1",
        "name": "Margin",
        "institution_name": "Webull",
        "number": "U87654321",
        "balance": {"total": {"amount": 1234.56, "currency": "USD"}},
        "sync_status": {"holdings": {"initial_sync_completed": True}},
    }]
    _POSITIONS = {"acc-1": [{
        "symbol": {"symbol": {"symbol": "NVDA", "description": "NVIDIA"}},
        "units": 2, "price": 200.0,
    }]}
    _BALANCES = {"acc-1": [{"currency": {"code": "USD"}, "cash": 100.5}]}

    def test_masks_account_numbers(self):
        mirror = mirror_mod.build_mirror(
            self._ACCOUNTS, self._POSITIONS, self._BALANCES,
            now_iso="2026-07-03T14:00:00+00:00")
        acct = mirror["accounts"][0]
        assert acct["number_masked"] == "***321"
        assert "U87654321" not in str(mirror)

    def test_normalizes_positions_and_totals(self):
        mirror = mirror_mod.build_mirror(
            self._ACCOUNTS, self._POSITIONS, self._BALANCES,
            now_iso="2026-07-03T14:00:00+00:00")
        acct = mirror["accounts"][0]
        assert acct["total_value"] == 1234.56
        pos = acct["positions"][0]
        assert pos["symbol"] == "NVDA"
        assert pos["value"] == 400.0
        assert acct["cash"] == [{"currency": "USD", "cash": 100.5}]

    def test_summary_line_is_privacy_safe(self):
        mirror = mirror_mod.build_mirror(
            self._ACCOUNTS, self._POSITIONS, self._BALANCES,
            now_iso="2026-07-03T14:00:00+00:00")
        line = mirror_mod.mirror_summary_line(mirror)
        assert "Webull" in line and "1 account" in line
        # No dollar amounts in the notification line.
        assert "1234" not in line and "400" not in line

    def test_empty_accounts_yield_empty_mirror(self):
        mirror = mirror_mod.build_mirror([], {}, {}, now_iso="t")
        assert mirror["account_count"] == 0
        assert mirror["accounts"] == []


# ---------------------------------------------------------------------------
# Risk gates + shadow executor (Phase 2)
# ---------------------------------------------------------------------------

import datetime  # noqa: E402

from execution import shadow  # noqa: E402
from execution.risk import RiskConfig, validate_signal  # noqa: E402

_TODAY = datetime.date(2026, 7, 4)


def _signal(**overrides):
    trade = {
        "symbol": "NVDA", "market": "NASDAQ", "snaptrade_symbol": "NVDA",
        "side": "BUY", "trade_type": "flash", "confidence": "High",
        "strategy": "momentum", "target_range": "", "sector": "tech",
        "pick_date": "2026-07-04", "pick_reference_price": 200.0,
        "pick_validated": True, "currency": "USD",
        "suggested_account": "webull",
        "client_order_id": "11111111-2222-3333-4444-555555555555",
    }
    trade.update(overrides.pop("trade_overrides", {}))
    signal = {
        "schema_version": 1, "generated_at": "2026-07-04",
        "episode_num": 96, "show": "modern_investing",
        "simulated_position_size_usd": 1000,
        "action": "new_trade", "reason": None, "trade": trade,
    }
    signal.update(overrides)
    return signal


class TestRiskGates:
    def test_valid_signal_passes(self):
        ok, reasons = validate_signal(_signal(), RiskConfig(), today=_TODAY)
        assert ok and reasons == []

    def test_no_trade_signal_fails_closed(self):
        ok, reasons = validate_signal(
            _signal(action="no_trade", trade=None), RiskConfig(), today=_TODAY)
        assert not ok
        assert any("nothing to trade" in r for r in reasons)

    def test_stale_signal_rejected(self):
        ok, reasons = validate_signal(
            _signal(generated_at="2026-06-30"), RiskConfig(), today=_TODAY)
        assert not ok
        assert any("stale" in r for r in reasons)

    def test_unvalidated_pick_rejected(self):
        ok, reasons = validate_signal(
            _signal(trade_overrides={"pick_validated": False,
                                     "pick_reference_price": None}),
            RiskConfig(), today=_TODAY)
        assert not ok
        assert any("not validated" in r for r in reasons)

    def test_penny_stock_rejected(self):
        ok, reasons = validate_signal(
            _signal(trade_overrides={"pick_reference_price": 0.85}),
            RiskConfig(), today=_TODAY)
        assert not ok
        assert any("floor" in r for r in reasons)

    def test_duplicate_order_id_rejected(self):
        sig = _signal()
        ok, reasons = validate_signal(
            sig, RiskConfig(), today=_TODAY,
            prior_order_ids={sig["trade"]["client_order_id"]})
        assert not ok
        assert any("duplicate" in r for r in reasons)

    def test_kill_switch_defaults_off(self, monkeypatch):
        monkeypatch.delenv("LIVE_TRADING_ENABLED", raising=False)
        assert RiskConfig.from_env().live_trading_enabled is False


class TestShadowExecutor:
    _NOW = datetime.datetime(2026, 7, 4, 13, 50,
                             tzinfo=datetime.timezone.utc)

    def test_valid_signal_logs_would_place_order(self):
        ledger = shadow.load_ledger(Path("/nonexistent/ledger.json"))
        entry = shadow.run_shadow(
            _signal(), ledger, RiskConfig(),
            quote_fn=lambda s: 201.0, now=self._NOW)
        assert entry["decision"] == "would_place"
        assert entry["order_type"] == "Limit"
        assert entry["limit_price"] == pytest.approx(201.0 * 1.005, abs=0.01)
        assert entry["units"] == pytest.approx(250.0 / entry["limit_price"],
                                               abs=0.001)
        assert ledger["orders"] == [entry]

    def test_rerun_is_idempotent(self):
        ledger = shadow.load_ledger(Path("/nonexistent/ledger.json"))
        shadow.run_shadow(_signal(), ledger, RiskConfig(),
                          quote_fn=lambda s: 201.0, now=self._NOW)
        second = shadow.run_shadow(_signal(), ledger, RiskConfig(),
                                   quote_fn=lambda s: 201.0, now=self._NOW)
        assert second["decision"] == "duplicate"
        assert len(ledger["orders"]) == 1  # not re-logged

    def test_gated_signal_logged_as_skipped_with_reasons(self):
        ledger = shadow.load_ledger(Path("/nonexistent/ledger.json"))
        entry = shadow.run_shadow(
            _signal(generated_at="2026-06-01"), ledger, RiskConfig(),
            quote_fn=lambda s: 201.0, now=self._NOW)
        assert entry["decision"] == "skipped"
        assert any("stale" in r for r in entry["skip_reasons"])
        assert ledger["orders"] == [entry]

    def test_quote_failure_falls_back_to_reference(self):
        ledger = shadow.load_ledger(Path("/nonexistent/ledger.json"))
        entry = shadow.run_shadow(
            _signal(), ledger, RiskConfig(),
            quote_fn=lambda s: None, now=self._NOW)
        assert entry["decision"] == "would_place"
        assert entry["quote_source"] == "pick_reference_fallback"
        assert entry["quote"] == 200.0

    def test_ledger_roundtrip(self, tmp_path):
        path = tmp_path / "shadow_ledger.json"
        ledger = shadow.load_ledger(path)
        shadow.run_shadow(_signal(), ledger, RiskConfig(),
                          quote_fn=lambda s: 201.0, now=self._NOW)
        shadow.save_ledger(ledger, path)
        reloaded = shadow.load_ledger(path)
        assert len(reloaded["orders"]) == 1
        assert reloaded["orders"][0]["snaptrade_symbol"] == "NVDA"

    def test_shadow_executor_script_fails_closed_without_signal(self):
        # The script uses ROOT-relative paths, so pin the fail-closed
        # branch in source (a missing signal must be a clean no-op).
        src = (_ROOT / "scripts/mit_shadow_executor.py").read_text()
        assert "nothing to do (fail-closed)" in src
        assert "return 0" in src
