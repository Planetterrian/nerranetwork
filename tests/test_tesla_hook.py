"""Tests for ``shows/hooks/tesla.py:_fetch_tsla_price``.

The fetcher was flipped from Grok ``x_search`` to a direct HTTP call
against Yahoo Finance's v8 chart API in May 2026 after operator caught
Grok returning bad data on two consecutive days (Ep473: $250 vs real
$444; Ep474: price == prev_close).  X posts are not an authoritative
quote source.

These tests pin the contract:

* Happy-path Yahoo response produces the canonical ``▲ $X.XX (X.X%)``
  change string the existing pipeline expects.
* HTTP errors, non-200 status, missing fields, out-of-range or
  deviated prices all fall back to ``(0.0, "(price unavailable)")``
  so we never ship a wrong number to the digest.

The ``requests.get`` call is monkey-patched out — these are pure-
function tests, never hit the network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "shows" / "hooks"))

import tesla as tesla_hook  # noqa: E402  (sys.path manipulation needed)


class _FakeResponse:
    """Minimal stand-in for ``requests.Response`` that the fetcher
    needs: ``status_code``, ``.json()``, ``.text``.
    """

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
    market_state: str = "REGULAR",
) -> dict:
    """Build a Yahoo-shaped chart response with the requested fields."""
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": price,
                        "chartPreviousClose": prev_close,
                        "previousClose": prev_close,
                        "marketState": market_state,
                    },
                },
            ],
        },
    }


def _patch_yahoo(monkeypatch, *, response: _FakeResponse | None = None,
                 raises: Exception | None = None):
    """Stub ``requests.get`` (as imported inside ``_fetch_tsla_price``)
    so the test never touches the network."""
    import requests

    def _fake_get(url, **kwargs):
        if raises is not None:
            raise raises
        return response

    monkeypatch.setattr(requests, "get", _fake_get)


@pytest.fixture(autouse=True)
def _stub_persist(monkeypatch):
    """Default-stub the api/tsla.json write so the test suite doesn't
    pollute the repo's ``api/`` directory every run, AND default-stub
    the cache LOAD so tests with no explicit deviation-guard setup
    get a clean ``no cache`` state (deviation check skipped).  Tests
    that need to exercise the real persistence or specific cache
    values re-patch these in their own bodies."""
    monkeypatch.setattr(
        tesla_hook, "_persist_tsla_price_json", lambda **kwargs: None,
    )
    monkeypatch.setattr(
        tesla_hook, "_load_last_cached_tsla_price", lambda: None,
    )


class TestHappyPath:

    def test_clean_response_regular_session(self, monkeypatch):
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=411.82, prev_close=402.38, market_state="REGULAR",
            ),
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 411.82
        # Up $9.44, ~2.3% — direction triangle ▲, no after-hours marker.
        assert "▲" in change_str
        assert "$9.44" in change_str
        assert "2.3%" in change_str
        assert "After-hours" not in change_str
        assert "Pre-market" not in change_str

    def test_negative_change_uses_down_arrow(self, monkeypatch):
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=380.00, prev_close=400.00, market_state="REGULAR",
            ),
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 380.00
        assert "▼" in change_str
        assert "$20.00" in change_str
        assert "5.0%" in change_str

    def test_after_hours_marker(self, monkeypatch):
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=415.00, prev_close=411.82, market_state="POST",
            ),
        ))
        _, change_str = tesla_hook._fetch_tsla_price()
        assert "(After-hours)" in change_str

    def test_pre_market_marker(self, monkeypatch):
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=405.00, prev_close=411.82, market_state="PRE",
            ),
        ))
        _, change_str = tesla_hook._fetch_tsla_price()
        assert "(Pre-market)" in change_str

    def test_closed_state_renders_as_after_hours(self, monkeypatch):
        """Yahoo uses ``CLOSED`` outside trading hours on
        weekends/holidays.  The downstream rendering doesn't have a
        dedicated 'closed' visual treatment so we collapse it into
        the after-hours bucket (which is what the operator sees on
        an 8 AM ET podcast publish anyway)."""
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=415.00, prev_close=411.82, market_state="CLOSED",
            ),
        ))
        _, change_str = tesla_hook._fetch_tsla_price()
        assert "(After-hours)" in change_str

    def test_falls_back_to_previous_close_when_chart_close_missing(self, monkeypatch):
        """``chartPreviousClose`` is the primary close field but Yahoo
        occasionally returns null for it (early pre-market on a fresh
        trading day); fall back to ``previousClose`` so we don't
        unnecessarily ship a price-unavailable."""
        payload = _make_yahoo_payload(
            price=400.00, prev_close=400.00, market_state="REGULAR",
        )
        payload["chart"]["result"][0]["meta"]["chartPreviousClose"] = None
        payload["chart"]["result"][0]["meta"]["previousClose"] = 395.00
        _patch_yahoo(monkeypatch, response=_FakeResponse(payload=payload))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 400.00
        assert "▲" in change_str
        assert "$5.00" in change_str


class TestFailureModes:
    """Every path that can't yield a trustworthy quote must return
    ``(0.0, "(price unavailable)")`` so the digest template renders
    a graceful placeholder rather than a wrong number."""

    def test_network_error_raises(self, monkeypatch):
        _patch_yahoo(monkeypatch, raises=RuntimeError("network down"))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_http_non_200(self, monkeypatch):
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            status_code=429, text="Rate limited",
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_yahoo_401_unauthorized(self, monkeypatch):
        """If Yahoo starts rejecting our User-Agent the call returns
        401; fall back gracefully rather than ship garbage."""
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            status_code=401, text="Unauthorized",
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_unparseable_body(self, monkeypatch):
        _patch_yahoo(monkeypatch, response=_FakeResponse(payload=None))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_missing_meta(self, monkeypatch):
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload={"chart": {"result": []}},
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_missing_price_field(self, monkeypatch):
        payload = _make_yahoo_payload()
        del payload["chart"]["result"][0]["meta"]["regularMarketPrice"]
        _patch_yahoo(monkeypatch, response=_FakeResponse(payload=payload))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_price_below_sanity_band(self, monkeypatch):
        """``$5`` is impossible for TSLA — likely a malformed payload
        or a stale split-adjusted figure. Fall back gracefully."""
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=5.00, prev_close=400.00, market_state="REGULAR",
            ),
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_price_above_sanity_band(self, monkeypatch):
        """``$5000`` is impossibly high; fall back."""
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=5000.00, prev_close=400.00, market_state="REGULAR",
            ),
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_prev_close_out_of_band_fails(self, monkeypatch):
        """A plausible price with an impossible prev_close would compute
        a misleading change %; reject the whole response."""
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=400.00, prev_close=0.05, market_state="REGULAR",
            ),
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"


class TestTslaJsonCache:
    """``_fetch_tsla_price`` persists each successful fetch to
    ``api/tsla.json`` so the public website (tesla.html) can render
    a same-origin price without depending on its own client-side
    Yahoo fetch (which can fail behind browser CORS / public proxies)."""

    def test_writes_api_tsla_json_on_success(self, monkeypatch, tmp_path):
        """Successful price fetch writes api/tsla.json with the
        full payload."""
        import json
        captured: dict = {}

        def fake_persist(**kwargs):
            captured.update(kwargs)
            out = tmp_path / "tsla.json"
            payload = {
                "price": round(kwargs["price"], 2),
                "prev_close": round(kwargs["prev_close"], 2),
                "change": round(kwargs["change"], 2),
                "change_pct": round(kwargs["pct"], 2),
                "change_str": kwargs["change_str"],
                "market_state": kwargs["market_state"],
            }
            out.write_text(json.dumps(payload), encoding="utf-8")

        monkeypatch.setattr(tesla_hook, "_persist_tsla_price_json", fake_persist)
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=444.57, prev_close=445.00, market_state="REGULAR",
            ),
        ))

        price, change_str = tesla_hook._fetch_tsla_price()

        assert price == 444.57
        assert captured["price"] == 444.57
        assert captured["prev_close"] == 445.00
        assert captured["market_state"] == "REGULAR"
        assert "$0.43" in captured["change_str"]
        out_path = tmp_path / "tsla.json"
        assert out_path.exists()
        payload = json.loads(out_path.read_text())
        assert payload["price"] == 444.57
        assert payload["prev_close"] == 445.00

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
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=400.00, prev_close=400.00, market_state="REGULAR",
            ),
        ))

        # Must NOT raise — best-effort wraps the write in try/except.
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 400.00
        assert change_str.startswith("▲")

    def test_persisted_source_field_is_yahoo(self, monkeypatch):
        """The cache file records its provenance so the dashboard /
        operator can tell at a glance which fetcher produced the
        last value."""
        captured: dict = {}

        def fake_persist(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(tesla_hook, "_persist_tsla_price_json", fake_persist)
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=444.57, prev_close=445.00, market_state="REGULAR",
            ),
        ))

        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 444.57

        # The persistence helper hard-codes ``source: "yahoo_finance_v8"``;
        # the contract guard lives separately because the kwargs the
        # fetcher passes don't include ``source``.
        import inspect
        from shows.hooks import tesla
        src = inspect.getsource(tesla._persist_tsla_price_json)
        assert '"source": "yahoo_finance_v8"' in src


class TestDeviationGuard:
    """Defence-in-depth: reject prices that swing more than 25% from
    the last cached close.  Yahoo is unlikely to return a 25%+ off
    price, but the guard was load-bearing under the previous Grok
    fetcher (caught the May 15 2026 ``$444 → $250`` regression) and
    is cheap to keep in place."""

    def test_rejects_price_more_than_25pct_below_cached(self, monkeypatch):
        """Cached at $444, new price $250 = 44% drop → reject."""
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: 444.57,
        )
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=250.35, prev_close=248.12, market_state="PRE",
            ),
        ))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_rejects_price_more_than_25pct_above_cached(self, monkeypatch):
        """Cached at $400, new price $600 = 50% spike → reject."""
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: 400.00,
        )
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=600.00, prev_close=595.00, market_state="REGULAR",
            ),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 0.0

    def test_accepts_price_within_25pct_band(self, monkeypatch):
        """Cached at $440, new price $420 = 4.5% drop → accept."""
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: 440.00,
        )
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=420.00, prev_close=425.00, market_state="REGULAR",
            ),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 420.00

    def test_accepts_price_at_exactly_25pct_boundary(self, monkeypatch):
        """At exactly 25% deviation the check is inclusive ( ``> cap``
        rejects, ``== cap`` accepts) so a 12.5%-up / 12.5%-down day
        with subsequent volatility doesn't trip the guard on a
        recovery candle."""
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: 400.00,
        )
        # 400 * 1.25 = 500 — exactly at the upper boundary
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=500.00, prev_close=498.00, market_state="REGULAR",
            ),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 500.00

    def test_no_cache_skips_deviation_check(self, monkeypatch):
        """First-ever run has no cached price — the deviation guard
        is skipped (would otherwise block the network's first
        Tesla run after deploy).  Hard sanity band still applies."""
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: None,
        )
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=444.57, prev_close=445.00, market_state="REGULAR",
            ),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 444.57

    def test_zero_cache_treated_as_no_cache(self, monkeypatch):
        """A degraded cache (``price: 0.0``) is treated as missing —
        deviation check skipped."""
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: 0.0,
        )
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=444.57, prev_close=445.00, market_state="REGULAR",
            ),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 444.57


class TestHardSanityBand:
    """The hard sanity band ($200-$1500) catches first-run bad data
    and any price wildly outside TSLA's historical range."""

    def test_rejects_price_below_hard_floor(self, monkeypatch):
        """May 15 2026: floor raised from $50 to $200.  TSLA hasn't
        traded below $200 in over a year and is structurally unlikely
        to in the near term."""
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: None,
        )
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=150.00, prev_close=152.00, market_state="REGULAR",
            ),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 0.0

    def test_rejects_price_above_hard_ceiling(self, monkeypatch):
        """Ceiling lowered from $2000 to $1500."""
        monkeypatch.setattr(
            tesla_hook, "_load_last_cached_tsla_price", lambda: None,
        )
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=1600.00, prev_close=1580.00, market_state="REGULAR",
            ),
        ))
        price, _ = tesla_hook._fetch_tsla_price()
        assert price == 0.0


class TestMarketStateDefaulting:
    """Yahoo's ``marketState`` values map onto the three states the
    rendering layers know about (PRE / REGULAR / POST); unknown
    values collapse to POST so we never crash on a new state Yahoo
    adds (e.g. ``POSTPOST``)."""

    def test_missing_market_state_defaults_to_regular(self, monkeypatch):
        payload = _make_yahoo_payload(price=411.82, prev_close=411.82)
        del payload["chart"]["result"][0]["meta"]["marketState"]
        _patch_yahoo(monkeypatch, response=_FakeResponse(payload=payload))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 411.82
        assert "(After-hours)" not in change_str
        assert "(Pre-market)" not in change_str

    def test_null_market_state_defaults_to_regular(self, monkeypatch):
        """Yahoo occasionally returns ``marketState: null`` mid-session
        (observed live on 2026-05-18 against TSLA at $409.99).  A
        null value must NOT render as 'After-hours' on a real
        regular-session quote — default to REGULAR (no suffix)."""
        payload = _make_yahoo_payload(price=411.82, prev_close=411.82)
        payload["chart"]["result"][0]["meta"]["marketState"] = None
        _patch_yahoo(monkeypatch, response=_FakeResponse(payload=payload))
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 411.82
        assert "(After-hours)" not in change_str
        assert "(Pre-market)" not in change_str

    def test_unknown_market_state_collapses_to_post(self, monkeypatch):
        """``POSTPOST`` is a real Yahoo state (late after-hours session);
        any unknown state should render as 'After-hours' rather than
        crash."""
        _patch_yahoo(monkeypatch, response=_FakeResponse(
            payload=_make_yahoo_payload(
                price=411.82, prev_close=411.82, market_state="POSTPOST",
            ),
        ))
        _, change_str = tesla_hook._fetch_tsla_price()
        assert "(After-hours)" in change_str
