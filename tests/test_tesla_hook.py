"""Tests for ``shows/hooks/tesla.py:_fetch_tsla_price``.

The fetcher uses a multi-source fallback chain to survive any single
upstream source failing:

  1. ``yfinance.Ticker.history(period="5d")`` — proven reliable on
     GitHub Actions runners (same library + endpoint Modern Investing
     uses successfully every weekday).
  2. ``yfinance.Ticker.fast_info`` — adds live pre/post-market price
     when history only returns end-of-day closes.
  3. Direct HTTP to Yahoo Finance v8 chart API — last-resort source
     for environments where it does work.

Each source is wrapped so a failure in one doesn't take down the chain.
Validation (sanity band + deviation guard) is applied uniformly.

History of why this is multi-source:

  - yfinance fast_info only (early 2026): returned ``$0.00`` on bad
    days because the ``or`` chain treated ``0.0`` as falsy and fell
    through to no data.
  - Grok x_search (May 2026): returned hallucinated prices from
    stale X posts; rejected by 25% deviation guard but slow to recover.
  - Direct Yahoo HTTP only (PR #385): worked locally but failed on
    GitHub Actions egress IPs because the bare ``requests.get`` call
    doesn't carry Yahoo's cookie + crumb session — both Ep477 and
    Ep478 shipped ``(price unavailable)``.

These tests pin the contract:
* Each source independently produces a valid quote (with all field
  shapes including ``marketState: None``).
* The chain falls through gracefully — if source 1 fails, source 2
  is tried; if 1 and 2 fail, source 3 is tried.
* If ALL sources fail or every source returns out-of-band data the
  fetcher returns ``(0.0, "(price unavailable)")``.

External calls (``yfinance.Ticker``, ``requests.get``) are monkey-
patched out — these are pure-function tests, never hit the network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "shows" / "hooks"))

import tesla as tesla_hook  # noqa: E402  (sys.path manipulation needed)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeYfHistory:
    """Stand-in for the DataFrame returned by ``Ticker.history()``.

    Real yfinance returns a pandas DataFrame; the production code only
    accesses ``.empty``, ``len()``, and ``["Close"].iloc[idx]``, so
    this minimal shim is enough."""

    def __init__(self, closes: list[float]):
        self._closes = list(closes)

    @property
    def empty(self) -> bool:
        return len(self._closes) == 0

    def __len__(self) -> int:
        return len(self._closes)

    def __getitem__(self, key: str):
        assert key == "Close"
        closes = self._closes

        class _ColumnAccessor:
            class _Iloc:
                def __getitem__(self, idx: int) -> float:
                    return closes[idx]

            iloc = _Iloc()

        return _ColumnAccessor()


class _FakeFastInfo:
    """Stand-in for ``Ticker.fast_info``."""

    def __init__(
        self, *,
        last_price=None, previous_close=None, market_state=None,
        regular_market_previous_close=None,
    ):
        self.last_price = last_price
        self.previous_close = previous_close
        self.regular_market_previous_close = regular_market_previous_close
        self.market_state = market_state


class _FakeTicker:
    """Stand-in for ``yfinance.Ticker(...)``."""

    def __init__(self, *, history=None, fast_info=None,
                 history_raises=None, fast_info_raises=None):
        self._history = history
        self._fast_info = fast_info
        self._history_raises = history_raises
        self._fast_info_raises = fast_info_raises

    def history(self, **kwargs):
        if self._history_raises is not None:
            raise self._history_raises
        return self._history if self._history is not None else _FakeYfHistory([])

    @property
    def fast_info(self):
        if self._fast_info_raises is not None:
            raise self._fast_info_raises
        return self._fast_info or _FakeFastInfo()


def _install_yfinance_stub(monkeypatch, ticker: _FakeTicker):
    """Patch ``yfinance.Ticker`` so both yfinance sources see the same
    fake ticker (the dispatcher creates a fresh ``Ticker("TSLA")``
    inside each source function)."""
    import yfinance as yf
    monkeypatch.setattr(yf, "Ticker", lambda symbol: ticker)


def _install_yfinance_broken(monkeypatch, exc: Exception | None = None):
    """Patch ``yfinance.Ticker`` so BOTH yfinance sources fail.
    Pass an exception to raise on call, or leave None for the
    "empty data" failure mode."""
    if exc is not None:
        def _ctor(symbol):
            raise exc
    else:
        def _ctor(symbol):
            return _FakeTicker(history=_FakeYfHistory([]), fast_info=_FakeFastInfo())
    import yfinance as yf
    monkeypatch.setattr(yf, "Ticker", _ctor)


class _FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(self, *, status_code: int = 200, payload: dict | None = None,
                 text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no payload")
        return self._payload


def _make_yahoo_payload(
    *,
    price: float = 444.57,
    prev_close: float = 445.00,
    market_state: str | None = "REGULAR",
    chart_previous_close: float | None = None,
) -> dict:
    """Build a Yahoo v8 chart response with the requested fields.

    The fetcher prefers the bar before the latest from
    ``indicators.quote[0].close`` (which mirrors what
    ``yfinance.Ticker.history()`` returns).  The bar array here
    contains [prev_close, price] so the dispatcher picks ``prev_close``
    as the previous bar's close.

    ``chart_previous_close`` defaults to a value WAY OFF from
    ``prev_close`` (445.27 — the production bug we caught: the
    close from BEFORE the 5-day window) so any test that
    accidentally falls back to it produces an obviously wrong
    answer instead of coincidentally matching.
    """
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": price,
                        "chartPreviousClose": (
                            chart_previous_close
                            if chart_previous_close is not None
                            else 99999.0
                        ),
                        "previousClose": prev_close,
                        "marketState": market_state,
                    },
                    "indicators": {
                        "quote": [
                            {"close": [prev_close, price]},
                        ],
                    },
                },
            ],
        },
    }


def _install_yahoo_http(monkeypatch, *, response: _FakeResponse | None = None,
                       raises: Exception | None = None):
    """Patch ``requests.get`` (the third source).  By default the
    direct HTTP source is NOT exercised — yfinance succeeds before
    we get there — but tests that drop into it install a real response."""
    import requests

    def _fake_get(url, **kwargs):
        if raises is not None:
            raise raises
        return response

    monkeypatch.setattr(requests, "get", _fake_get)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_persist_and_cache(monkeypatch):
    """Default stubs so each test starts clean:
      - ``api/tsla.json`` write is a no-op (no repo pollution).
      - Last-cached price is ``None`` (deviation guard skipped).
      - Both yfinance sources fail by default — tests that exercise
        them re-patch them in their own bodies.
      - Direct HTTP raises ``RuntimeError`` by default — same reason.
    """
    monkeypatch.setattr(
        tesla_hook, "_persist_tsla_price_json", lambda **kwargs: None,
    )
    monkeypatch.setattr(
        tesla_hook, "_load_last_cached_tsla_price", lambda: None,
    )
    _install_yfinance_broken(monkeypatch, exc=RuntimeError("yfinance stubbed off"))
    _install_yahoo_http(monkeypatch, raises=RuntimeError("requests stubbed off"))


# ---------------------------------------------------------------------------
# Source 1: yfinance history
# ---------------------------------------------------------------------------


class TestYfinanceHistorySource:
    """Source 1 is the primary path — proven reliable in GHA."""

    def test_clean_history_response(self, monkeypatch):
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([400.0, 410.0, 405.0, 411.82]),
            fast_info=_FakeFastInfo(),  # not consulted on history hit
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 411.82
        # 411.82 vs prev 405.0 → up $6.82, 1.7%
        assert "▲" in change_str
        assert "$6.82" in change_str

    def test_history_with_single_bar_uses_price_as_prev(self, monkeypatch):
        """``history(period='5d')`` can return a single row on the
        first trading day after a long holiday.  The source treats
        prev_close as equal to price in that case so the change line
        renders as ``▲ $0.00`` rather than crashing."""
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([411.82]),
            fast_info=_FakeFastInfo(),
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 411.82
        assert "$0.00" in change_str

    def test_empty_history_falls_through_to_fast_info(self, monkeypatch):
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([]),
            fast_info=_FakeFastInfo(
                last_price=411.82, previous_close=405.0,
                market_state="REGULAR",
            ),
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 411.82  # fast_info won
        assert "▲" in change_str

    def test_history_raise_falls_through_to_fast_info(self, monkeypatch):
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history_raises=RuntimeError("Yahoo session lost"),
            fast_info=_FakeFastInfo(
                last_price=420.00, previous_close=400.00,
                market_state="POST",
            ),
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 420.00
        assert "(After-hours)" in change_str


# ---------------------------------------------------------------------------
# Source 2: yfinance fast_info
# ---------------------------------------------------------------------------


class TestYfinanceFastInfoSource:
    """Source 2 fills in pre/post-market live price when history
    alone only gives day-level closes."""

    def test_pre_market_marker(self, monkeypatch):
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([]),  # force fallthrough
            fast_info=_FakeFastInfo(
                last_price=405.00, previous_close=411.82,
                market_state="PRE",
            ),
        ))
        _, change_str = tesla_hook._fetch_tsla_price()
        assert "(Pre-market)" in change_str
        assert "▼" in change_str

    def test_after_hours_marker(self, monkeypatch):
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([]),
            fast_info=_FakeFastInfo(
                last_price=415.00, previous_close=411.82,
                market_state="POST",
            ),
        ))
        _, change_str = tesla_hook._fetch_tsla_price()
        assert "(After-hours)" in change_str

    def test_fast_info_zero_falls_through_to_http(self, monkeypatch):
        """Historical fast_info bug: ``last_price`` comes back as
        ``0.0`` on a degraded response.  The ``or`` chain must treat
        ``0.0`` as falsy so the source returns None and the dispatcher
        moves on (rather than reporting ``$0.00`` as a real price)."""
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([]),
            fast_info=_FakeFastInfo(
                last_price=0.0, previous_close=411.82,
                market_state="REGULAR",
            ),
        ))
        # And source 3 (direct HTTP) succeeds.
        _install_yahoo_http(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=411.19, prev_close=445.27, market_state="REGULAR",
            ),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 411.19  # source 3 won

    def test_fast_info_missing_prev_falls_through(self, monkeypatch):
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([]),
            fast_info=_FakeFastInfo(
                last_price=411.82, previous_close=None,
                market_state="REGULAR",
            ),
        ))
        _install_yahoo_http(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=412.00, prev_close=410.00, market_state="REGULAR",
            ),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 412.00


# ---------------------------------------------------------------------------
# Source 3: direct HTTP to Yahoo v8 chart
# ---------------------------------------------------------------------------


class TestYahooHttpSource:

    def test_drops_in_when_both_yfinance_sources_fail(self, monkeypatch):
        """Both yfinance sources empty/failing — direct HTTP picks up."""
        # Default fixture already breaks yfinance; only install Yahoo HTTP.
        _install_yahoo_http(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=411.19, prev_close=445.27, market_state="REGULAR",
            ),
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 411.19
        assert "▼" in change_str
        assert "$34.08" in change_str

    def test_null_market_state_renders_as_regular(self, monkeypatch):
        """Yahoo returns ``marketState: null`` mid-session at times
        (observed live 2026-05-18).  Must render as a regular session
        rather than mislabel as After-hours."""
        payload = _make_yahoo_payload(
            price=411.19, prev_close=445.27, market_state=None,
        )
        _install_yahoo_http(monkeypatch, response=_FakeResponse(payload=payload))
        _, change_str = tesla_hook._fetch_tsla_price()
        assert "(After-hours)" not in change_str
        assert "(Pre-market)" not in change_str

    def test_unknown_market_state_collapses_to_post(self, monkeypatch):
        """``POSTPOST`` is a real Yahoo state; renders as After-hours
        rather than crashing."""
        payload = _make_yahoo_payload(
            price=411.19, prev_close=445.27, market_state="POSTPOST",
        )
        _install_yahoo_http(monkeypatch, response=_FakeResponse(payload=payload))
        _, change_str = tesla_hook._fetch_tsla_price()
        assert "(After-hours)" in change_str

    def test_http_non_200_falls_through(self, monkeypatch):
        """When direct HTTP returns 401/429 (Yahoo blocking GHA egress
        IP) the chain returns unavailable rather than ship garbage."""
        _install_yahoo_http(monkeypatch, response=_FakeResponse(
            status_code=401, text="Unauthorized",
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_http_network_error_falls_through(self, monkeypatch):
        _install_yahoo_http(monkeypatch, raises=RuntimeError("network down"))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_bar_close_array_is_authoritative(self, monkeypatch):
        """The fetcher uses ``indicators.quote[0].close[-2]`` for
        previous close — NOT the meta ``chartPreviousClose`` field,
        which anchors before the chart's range window (the production
        bug caught after PR #385 shipped, where ``chartPreviousClose``
        was 445.27 = May 13 close instead of 404.11 = yesterday).

        This payload deliberately puts ``chart_previous_close=99999``
        (the default in the test helper); if the fetcher fell back to
        it, the deviation guard or sanity band would catch it.  The
        ``indicators.quote`` close array is the source of truth."""
        payload = _make_yahoo_payload(
            price=412.01, prev_close=404.11,
            chart_previous_close=445.27,  # tempting but WRONG
            market_state="REGULAR",
        )
        _install_yahoo_http(monkeypatch, response=_FakeResponse(payload=payload))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 412.01
        # If we'd used chartPreviousClose the change would be ~-$33.
        # With the bar close array we get the correct +$7.90.
        assert "▲" in change_str
        assert "$7.90" in change_str

    def test_null_bar_close_falls_back_to_meta_previous_close(self, monkeypatch):
        """If the close-bar array contains nulls (early pre-market on
        a fresh trading day), fall back to ``meta.previousClose``."""
        payload = _make_yahoo_payload(price=400.00, prev_close=395.00)
        # Break the bar array so the fallback fires.
        payload["chart"]["result"][0]["indicators"]["quote"][0]["close"] = [None, None]
        _install_yahoo_http(monkeypatch, response=_FakeResponse(payload=payload))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 400.00
        assert "$5.00" in change_str

    def test_all_prev_close_sources_null_returns_unavailable(self, monkeypatch):
        """If every previous-close source is null, the chain returns
        unavailable — we don't make up a change."""
        payload = _make_yahoo_payload(price=400.00, prev_close=395.00)
        payload["chart"]["result"][0]["indicators"]["quote"][0]["close"] = [None, None]
        payload["chart"]["result"][0]["meta"]["chartPreviousClose"] = None
        payload["chart"]["result"][0]["meta"]["previousClose"] = None
        _install_yahoo_http(monkeypatch, response=_FakeResponse(payload=payload))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"


# ---------------------------------------------------------------------------
# Chain semantics
# ---------------------------------------------------------------------------


class TestChainFallthrough:

    def test_all_sources_fail_returns_unavailable(self, monkeypatch):
        # Default fixture already breaks all 3 sources.
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_first_source_wins_skips_rest(self, monkeypatch):
        """Source 1 succeeds → source 2 + 3 are not consulted."""
        history_calls = {"n": 0}

        def _counting_history(**kwargs):
            history_calls["n"] += 1
            return _FakeYfHistory([400.0, 410.0, 411.82])

        ticker = _FakeTicker(fast_info=_FakeFastInfo(last_price=999.99))
        ticker.history = _counting_history
        import yfinance as yf
        monkeypatch.setattr(yf, "Ticker", lambda symbol: ticker)

        # Source 3 would return a totally different price if reached.
        _install_yahoo_http(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(price=300.00, prev_close=300.00),
        ))

        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 411.82  # source 1's price
        assert history_calls["n"] == 1

    def test_out_of_band_source_1_falls_through(self, monkeypatch):
        """If source 1 returns a price outside the sanity band (e.g.
        a stale split-adjusted figure), the validator rejects it and
        source 2 / 3 get a chance."""
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([5.0, 5.0, 5.0]),  # bad data
            fast_info=_FakeFastInfo(
                last_price=411.82, previous_close=405.0,
                market_state="REGULAR",
            ),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 411.82  # source 2 won after source 1 was rejected


# ---------------------------------------------------------------------------
# Validation: sanity band + deviation guard
# ---------------------------------------------------------------------------


class TestSanityBand:

    def test_rejects_price_below_floor(self, monkeypatch):
        """May 15 2026: floor raised from $50 to $200."""
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([150.0, 150.0]),
            fast_info=_FakeFastInfo(last_price=150.0, previous_close=150.0,
                                    market_state="REGULAR"),
        ))
        _install_yahoo_http(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(price=150.0, prev_close=150.0),
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0  # every source rejected by sanity band

    def test_rejects_price_above_ceiling(self, monkeypatch):
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([1600.0, 1600.0]),
            fast_info=_FakeFastInfo(last_price=1600.0, previous_close=1600.0,
                                    market_state="REGULAR"),
        ))
        _install_yahoo_http(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(price=1600.0, prev_close=1600.0),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 0.0


class TestDeviationGuard:
    """Caught the May 15 2026 ``$444 → $250`` Grok regression.  Still
    a load-bearing guard on the multi-source chain — if any source
    returns a wildly different price than the cache, reject it."""

    def test_rejects_44pct_drop(self, monkeypatch):
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: 444.57,
        )
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([250.0, 250.0]),
            fast_info=_FakeFastInfo(last_price=250.0, previous_close=250.0,
                                    market_state="REGULAR"),
        ))
        _install_yahoo_http(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(price=250.0, prev_close=250.0),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 0.0

    def test_rejects_50pct_spike(self, monkeypatch):
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: 400.00,
        )
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([600.0, 600.0]),
            fast_info=_FakeFastInfo(last_price=600.0, previous_close=600.0,
                                    market_state="REGULAR"),
        ))
        _install_yahoo_http(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(price=600.0, prev_close=600.0),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 0.0

    def test_accepts_within_band(self, monkeypatch):
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: 440.00,
        )
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([425.0, 420.0]),
            fast_info=_FakeFastInfo(),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 420.00

    def test_accepts_at_exact_boundary(self, monkeypatch):
        """``> cap`` rejects, ``== cap`` accepts."""
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: 400.00,
        )
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([498.0, 500.0]),  # exactly +25%
            fast_info=_FakeFastInfo(),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 500.00

    def test_no_cache_skips_check(self, monkeypatch):
        """First-ever run has no cached price — deviation guard skipped."""
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: None,
        )
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([400.0, 444.57]),
            fast_info=_FakeFastInfo(),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 444.57

    def test_zero_cache_treated_as_none(self, monkeypatch):
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: 0.0,
        )
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([400.0, 444.57]),
            fast_info=_FakeFastInfo(),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 444.57


# ---------------------------------------------------------------------------
# Persistence cache (api/tsla.json)
# ---------------------------------------------------------------------------


class TestTslaJsonCache:
    """The cache file is the website's same-origin source of truth.
    Every successful fetch persists it; failed fetches do NOT
    overwrite the previous-good value."""

    def test_writes_payload_on_success(self, monkeypatch, tmp_path):
        import json
        captured: dict = {}

        def fake_persist(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(tesla_hook, "_persist_tsla_price_json", fake_persist)
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([445.00, 444.57]),
            fast_info=_FakeFastInfo(),
        ))

        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 444.57
        assert captured["price"] == 444.57
        assert captured["prev_close"] == 445.00
        assert captured["market_state"] == "REGULAR"
        assert captured["source"] == "yfinance_history"

    def test_failure_does_not_overwrite_cache(self, monkeypatch):
        """If every source fails the persist helper is NOT called —
        the previous-good cached value stays intact."""
        called = {"n": 0}

        def fake_persist(**kwargs):
            called["n"] += 1

        monkeypatch.setattr(tesla_hook, "_persist_tsla_price_json", fake_persist)
        # All sources broken via the autouse fixture.
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert called["n"] == 0

    def test_source_field_records_which_path_won(self, monkeypatch):
        """The cached ``source`` string distinguishes which path in
        the chain produced the value — the management dashboard
        surfaces this so the operator can spot a degraded primary."""
        captured: dict = {}

        def fake_persist(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(tesla_hook, "_persist_tsla_price_json", fake_persist)
        # History empty → fast_info should win.
        _install_yfinance_stub(monkeypatch, _FakeTicker(
            history=_FakeYfHistory([]),
            fast_info=_FakeFastInfo(
                last_price=411.82, previous_close=405.00,
                market_state="REGULAR",
            ),
        ))
        tesla_hook._fetch_tsla_price()
        assert captured["source"] == "yfinance_fast_info"

    def test_persistence_failure_is_non_fatal(self, monkeypatch):
        """If ``api/tsla.json`` can't be written (disk full, permission)
        the pipeline still gets a usable ``(price, change_str)``."""
        from pathlib import Path as _Path

        original_write = _Path.write_text

        def explosive_write(self, *args, **kwargs):
            if self.name == "tsla.json":
                raise OSError("simulated disk-full")
            return original_write(self, *args, **kwargs)

        monkeypatch.setattr(_Path, "write_text", explosive_write)
        # Restore the REAL persistence helper (autouse stubbed it).
        from shows.hooks import tesla as _tesla
        import importlib
        importlib.reload(_tesla)
        # Re-stub the cache load since reload reset it
        monkeypatch.setattr(
            _tesla, "_load_last_cached_tsla_price", lambda: None,
        )
        import yfinance as yf
        monkeypatch.setattr(yf, "Ticker", lambda symbol: _FakeTicker(
            history=_FakeYfHistory([400.00, 400.00]),
            fast_info=_FakeFastInfo(),
        ))
        # Must NOT raise — best-effort wraps the write in try/except.
        price, change_str = _tesla._fetch_tsla_price()
        assert price == 400.00
        assert change_str.startswith("▲")
