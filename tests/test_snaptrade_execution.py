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

    def test_order_placement_confined_to_live_path(self):
        # Phase 3 (operator-directed) supersedes the Phase-1/2 no-placement
        # contract with a narrower one: the SDK trading call exists ONLY in
        # the snaptrade_client wrapper, and the only module invoking that
        # wrapper is execution/live.py — whose first gate is the
        # LIVE_TRADING_ENABLED kill switch. Shadow/mirror stay order-free.
        for f in sorted((_ROOT / "execution").rglob("*.py")):
            text = f.read_text(encoding="utf-8")
            if f.name == "snaptrade_client.py":
                assert "place_force_order" in text  # the single SDK call site
                continue
            assert "place_force_order" not in text.lower(), (
                f"{f.name} calls the SDK trading endpoint directly — only "
                f"the snaptrade_client wrapper may")
            if f.name == "live.py":
                continue
            assert "place_limit_order" not in text, (
                f"{f.name} places orders — only execution/live.py may")

    def test_live_entry_first_gate_is_the_kill_switch(self):
        # With the switch off, run_live_entry must return 'disabled' BEFORE
        # touching credentials, accounts, or quotes.
        import datetime as _dt

        class _Boom:
            def __getattr__(self, name):
                raise AssertionError(
                    "live layer touched the client while disabled")

        decision = __import__("execution.live", fromlist=["live"]).run_live_entry(
            {"schema_version": 1, "action": "new_trade", "trade": {}},
            {"orders": []}, {"orders": []},
            RiskConfig(live_trading_enabled=False),
            client=_Boom(),
            now=_dt.datetime(2026, 7, 6, 13, 52,
                             tzinfo=_dt.timezone.utc),
        )
        assert decision["decision"] == "disabled"

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


class TestShadowExits:
    _NOW = datetime.datetime(2026, 7, 10, 13, 50,
                             tzinfo=datetime.timezone.utc)  # Friday

    def _ledger_with_entry(self, pick_date="2026-07-06", trade_type="weekly"):
        ledger = shadow.load_ledger(Path("/nonexistent/ledger.json"))
        ledger["orders"].append({
            "logged_at": f"{pick_date}T13:50:00+00:00", "mode": "shadow",
            "decision": "would_place", "episode_num": 99,
            "client_order_id": "aaaa-bbbb", "symbol": "NVDA",
            "snaptrade_symbol": "NVDA", "trade_type": trade_type,
            "quote": 200.0, "limit_price": 201.0, "units": 1.24,
            "pick_date": pick_date,
        })
        return ledger

    def test_weekly_exit_is_a_fixed_session_horizon(self):
        """SUPERSEDED 2026-08-18: exits follow the session horizon in
        shows/_trading_policy.yaml, not the Friday calendar. A Monday pick
        still lands on Friday because that IS five sessions; a Friday pick
        now lands on the following Thursday for the same reason, instead
        of waiting a full extra week."""
        # Monday pick → Friday (Mon,Tue,Wed,Thu,Fri = 5 sessions).
        assert shadow._exit_due_date(
            datetime.date(2026, 7, 6), "weekly") == datetime.date(2026, 7, 10)
        # Friday pick → next Thursday (Fri,Mon,Tue,Wed,Thu = 5 sessions).
        assert shadow._exit_due_date(
            datetime.date(2026, 7, 10), "weekly") == datetime.date(2026, 7, 16)

    def test_flash_exit_due_next_weekday(self):
        assert shadow._exit_due_date(
            datetime.date(2026, 7, 8), "flash") == datetime.date(2026, 7, 9)
        # Friday flash → Monday.
        assert shadow._exit_due_date(
            datetime.date(2026, 7, 10), "flash") == datetime.date(2026, 7, 13)

    def test_due_position_gets_would_sell_with_round_trip(self):
        ledger = self._ledger_with_entry()
        exits = shadow.run_shadow_exits(
            ledger, RiskConfig(), quote_fn=lambda s: 210.0, now=self._NOW)
        assert len(exits) == 1
        x = exits[0]
        assert x["decision"] == "would_sell"
        assert x["shadow_return_pct"] == pytest.approx(5.0, abs=0.01)
        assert x["exit_client_order_id"] == "aaaa-bbbb-exit"
        assert len(ledger["orders"]) == 2

    def test_exit_is_idempotent(self):
        ledger = self._ledger_with_entry()
        shadow.run_shadow_exits(ledger, RiskConfig(),
                                quote_fn=lambda s: 210.0, now=self._NOW)
        again = shadow.run_shadow_exits(ledger, RiskConfig(),
                                        quote_fn=lambda s: 210.0, now=self._NOW)
        assert again == []
        assert len(ledger["orders"]) == 2

    def test_not_yet_due_position_stays_open(self):
        ledger = self._ledger_with_entry(pick_date="2026-07-09")  # Thu weekly
        exits = shadow.run_shadow_exits(
            ledger, RiskConfig(), quote_fn=lambda s: 210.0,
            now=datetime.datetime(2026, 7, 9, 13, 50,
                                  tzinfo=datetime.timezone.utc))
        assert exits == []

    def test_no_quote_leaves_position_open_for_retry(self):
        ledger = self._ledger_with_entry()
        exits = shadow.run_shadow_exits(
            ledger, RiskConfig(), quote_fn=lambda s: None, now=self._NOW)
        assert exits == []
        assert len(ledger["orders"]) == 1  # nothing logged; retried later


# ---------------------------------------------------------------------------
# Live executor (Phase 3 — dormant by default)
# ---------------------------------------------------------------------------

from execution import live  # noqa: E402


class _FakeClient:
    """Configured SnapTrade client with scriptable placement results."""

    def __init__(self, *, accounts=None, positions=None,
                 place_result=None, place_raises=None):
        self.accounts = accounts if accounts is not None else [{
            "id": "acct-webull", "institution_name": "Webull",
            "balance": {"total": {"amount": 5000.0, "currency": "USD"}},
        }]
        self.positions = positions or []
        self.place_result = place_result or {
            "brokerage_order_id": "bo-1", "status": "ACCEPTED"}
        self.place_raises = place_raises
        self.placed = []

    def is_configured(self):
        return True

    def list_accounts(self):
        return self.accounts

    def account_positions(self, account_id):
        return self.positions

    def place_limit_order(self, **kwargs):
        if self.place_raises:
            raise self.place_raises
        self.placed.append(kwargs)
        return dict(self.place_result)


_LIVE_NOW = datetime.datetime(2026, 7, 6, 13, 52,
                              tzinfo=datetime.timezone.utc)  # Monday


def _live_config(**kw):
    return RiskConfig(live_trading_enabled=True, **kw)


def _live_signal(**overrides):
    sig = _signal(**overrides)
    sig["generated_at"] = "2026-07-06"
    sig["trade"]["pick_date"] = "2026-07-06"
    return sig


class TestLiveEntry:
    def test_places_integer_share_marketable_limit(self, monkeypatch):
        monkeypatch.delenv("NOTIFICATION_WEBHOOK_URL", raising=False)
        client = _FakeClient()
        state, ledger = live.load_state(Path("/nope")), live.load_ledger(Path("/nope"))
        decision = live.run_live_entry(
            _live_signal(), state, ledger, _live_config(),
            client=client, quote_fn=lambda s: 100.0, now=_LIVE_NOW)
        assert decision["decision"] == "placed"
        order = client.placed[0]
        assert order["action"] == "BUY"
        assert order["symbol"] == "NVDA"
        assert order["units"] == 2            # int(250 // 100.5)
        assert order["limit_price"] == 100.5  # quote * 1.005
        assert order["client_order_id"] == _live_signal()["trade"]["client_order_id"]
        # Committed index carries ids/status only — no dollar amounts.
        idx = state["orders"][0]
        assert "limit_price" not in idx and "units" not in idx
        # Full ledger carries the audit detail.
        assert ledger["orders"][0]["units"] == 2
        assert ledger["orders"][0]["account_id"] == "acct-webull"

    def test_duplicate_signal_not_replaced(self, monkeypatch):
        monkeypatch.delenv("NOTIFICATION_WEBHOOK_URL", raising=False)
        client = _FakeClient()
        state, ledger = live.load_state(Path("/nope")), live.load_ledger(Path("/nope"))
        live.run_live_entry(_live_signal(), state, ledger, _live_config(),
                            client=client, quote_fn=lambda s: 100.0, now=_LIVE_NOW)
        second = live.run_live_entry(
            _live_signal(), state, ledger, _live_config(),
            client=client, quote_fn=lambda s: 100.0, now=_LIVE_NOW)
        assert second["decision"] == "skipped"
        assert any("duplicate" in r for r in second["skip_reasons"])
        assert len(client.placed) == 1

    def test_price_above_cap_skips(self, monkeypatch):
        monkeypatch.delenv("NOTIFICATION_WEBHOOK_URL", raising=False)
        client = _FakeClient()
        state, ledger = live.load_state(Path("/nope")), live.load_ledger(Path("/nope"))
        decision = live.run_live_entry(
            _live_signal(), state, ledger, _live_config(),
            client=client, quote_fn=lambda s: 1200.0, now=_LIVE_NOW)
        assert decision["decision"] == "skipped"
        assert any("position cap" in r for r in decision["skip_reasons"])
        assert client.placed == []

    def test_no_quote_never_places_blind(self, monkeypatch):
        monkeypatch.delenv("NOTIFICATION_WEBHOOK_URL", raising=False)
        client = _FakeClient()
        state, ledger = live.load_state(Path("/nope")), live.load_ledger(Path("/nope"))
        decision = live.run_live_entry(
            _live_signal(), state, ledger, _live_config(),
            client=client, quote_fn=lambda s: None, now=_LIVE_NOW)
        assert decision["decision"] == "skipped"
        assert client.placed == []

    def test_no_matching_account_skips(self, monkeypatch):
        monkeypatch.delenv("NOTIFICATION_WEBHOOK_URL", raising=False)
        client = _FakeClient(accounts=[{
            "id": "a", "institution_name": "Questrade",
            "balance": {"total": {"amount": 1.0, "currency": "CAD"}}}])
        state, ledger = live.load_state(Path("/nope")), live.load_ledger(Path("/nope"))
        decision = live.run_live_entry(
            _live_signal(), state, ledger, _live_config(),
            client=client, quote_fn=lambda s: 100.0, now=_LIVE_NOW)
        assert decision["decision"] == "skipped"
        assert any("no matching account" in r for r in decision["skip_reasons"])

    def test_two_consecutive_rejects_halt_the_layer(self, monkeypatch):
        monkeypatch.delenv("NOTIFICATION_WEBHOOK_URL", raising=False)
        state, ledger = live.load_state(Path("/nope")), live.load_ledger(Path("/nope"))
        client = _FakeClient(place_result={"status": "REJECTED"})
        sig1 = _live_signal()
        live.run_live_entry(sig1, state, ledger, _live_config(),
                            client=client, quote_fn=lambda s: 100.0, now=_LIVE_NOW)
        assert state["halted"] is False
        sig2 = _live_signal(
            trade_overrides={"client_order_id": "22222222-3333-4444-5555-666666666666"})
        # Second reject on a fresh day (daily cap would otherwise block).
        later = _LIVE_NOW + datetime.timedelta(days=1)
        sig2["generated_at"] = "2026-07-07"
        live.run_live_entry(sig2, state, ledger, _live_config(),
                            client=client, quote_fn=lambda s: 100.0, now=later)
        assert state["halted"] is True
        # Third attempt: refused outright.
        sig3 = _live_signal(
            trade_overrides={"client_order_id": "33333333-4444-5555-6666-777777777777"})
        sig3["generated_at"] = "2026-07-08"
        decision = live.run_live_entry(
            sig3, state, ledger, _live_config(), client=client,
            quote_fn=lambda s: 100.0,
            now=_LIVE_NOW + datetime.timedelta(days=2))
        assert decision["decision"] == "halted"

    def test_open_position_cap_blocks_second_entry(self, monkeypatch):
        monkeypatch.delenv("NOTIFICATION_WEBHOOK_URL", raising=False)
        client = _FakeClient()
        state, ledger = live.load_state(Path("/nope")), live.load_ledger(Path("/nope"))
        live.run_live_entry(_live_signal(), state, ledger, _live_config(),
                            client=client, quote_fn=lambda s: 100.0, now=_LIVE_NOW)
        sig2 = _live_signal(
            trade_overrides={"client_order_id": "22222222-3333-4444-5555-666666666666"})
        sig2["generated_at"] = "2026-07-07"
        decision = live.run_live_entry(
            sig2, state, ledger, _live_config(), client=client,
            quote_fn=lambda s: 100.0,
            now=_LIVE_NOW + datetime.timedelta(days=1))
        assert decision["decision"] == "skipped"
        assert any("open-position cap" in r for r in decision["skip_reasons"])


class TestLiveExits:
    def _state_with_entry(self, pick_date="2026-07-06"):
        state = live.load_state(Path("/nope"))
        ledger = live.load_ledger(Path("/nope"))
        state["orders"].append({
            "kind": "entry", "client_order_id": "e1", "symbol": "NVDA",
            "trade_type": "flash", "pick_date": pick_date,
            "status": "EXECUTED", "logged_at": f"{pick_date}T13:52:00+00:00",
        })
        ledger["orders"].append({
            "kind": "entry", "client_order_id": "e1", "symbol": "NVDA",
            "mode": "live", "account_id": "acct-webull", "units": 2,
            "limit_price": 100.5,
        })
        return state, ledger

    def _position(self, units):
        return [{"symbol": {"symbol": {"symbol": "NVDA"}}, "units": units}]

    def test_due_exit_sells_held_units(self, monkeypatch):
        monkeypatch.delenv("NOTIFICATION_WEBHOOK_URL", raising=False)
        state, ledger = self._state_with_entry()
        client = _FakeClient(positions=self._position(2))
        exits = live.run_live_exits(
            state, ledger, _live_config(), client=client,
            quote_fn=lambda s: 110.0,
            now=datetime.datetime(2026, 7, 7, 19, 45,
                                  tzinfo=datetime.timezone.utc))
        assert len(exits) == 1
        order = client.placed[0]
        assert order["action"] == "SELL"
        assert order["units"] == 2
        assert order["limit_price"] == round(110.0 * 0.995, 2)
        assert order["client_order_id"] == "e1-exit"

    def test_unfilled_entry_marks_flat_instead_of_selling(self, monkeypatch):
        monkeypatch.delenv("NOTIFICATION_WEBHOOK_URL", raising=False)
        state, ledger = self._state_with_entry()
        client = _FakeClient(positions=self._position(0))
        exits = live.run_live_exits(
            state, ledger, _live_config(), client=client,
            quote_fn=lambda s: 110.0,
            now=datetime.datetime(2026, 7, 7, 19, 45,
                                  tzinfo=datetime.timezone.utc))
        assert exits == []
        assert client.placed == []
        assert state["orders"][0]["exited"] is True
        assert "no position" in state["orders"][0]["exit_note"]

    def test_not_due_yet_no_sell(self, monkeypatch):
        monkeypatch.delenv("NOTIFICATION_WEBHOOK_URL", raising=False)
        state, ledger = self._state_with_entry()
        client = _FakeClient(positions=self._position(2))
        exits = live.run_live_exits(
            state, ledger, _live_config(), client=client,
            quote_fn=lambda s: 110.0,
            now=datetime.datetime(2026, 7, 6, 19, 45,
                                  tzinfo=datetime.timezone.utc))
        assert exits == [] and client.placed == []

    def test_disabled_layer_never_sells(self):
        state, ledger = self._state_with_entry()
        client = _FakeClient(positions=self._position(2))
        exits = live.run_live_exits(
            state, ledger, RiskConfig(live_trading_enabled=False),
            client=client, quote_fn=lambda s: 110.0,
            now=datetime.datetime(2026, 7, 7, 19, 45,
                                  tzinfo=datetime.timezone.utc))
        assert exits == [] and client.placed == []


class TestLiveStatePrivacy:
    def test_live_ledger_is_gitignored(self):
        result = subprocess.run(
            ["git", "check-ignore",
             "digests/modern_investing/live_ledger.json"],
            cwd=_ROOT, capture_output=True, text=True)
        assert result.returncode == 0, (
            "live_ledger.json must never be committable (real account "
            "activity, public repo)")

    def test_executor_script_dormant_without_kill_switch(self):
        src = (_ROOT / "scripts/mit_live_executor.py").read_text()
        assert "live layer dormant" in src
        assert "return 0" in src
