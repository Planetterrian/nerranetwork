"""Nov 24 2026: MAG 7 Ep063 omitted NVDA from the tape on the day it closed
165.05 after 125.53 (+31.5%) — a real move the 30% deviation guard rejected.
The omitted ticker then vanished from the cache, so the next run would have
validated it against nothing."""
import json

from engine import market_quotes as mq


def _cache(tmp_path, quotes, last_verified=None):
    p = tmp_path / "mag7_quotes.json"
    data = {"quotes": quotes}
    if last_verified:
        data["last_verified"] = last_verified
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


NVDA_CACHED = {"ticker": "NVDA", "close": 125.53, "bar_date": "2026-11-20"}


class TestCorroboratedMove:
    def test_the_nov_23_close_is_accepted(self, tmp_path):
        p = _cache(tmp_path, [NVDA_CACHED])
        got = mq.fetch_daily_closes(
            ["NVDA"], cache_path=p, fetch=lambda t: (165.05, 125.53, "2026-11-23"))
        assert [q.close for q in got] == [165.05]

    def test_a_jump_the_series_does_not_carry_is_still_rejected(self, tmp_path, capsys):
        # previous bar disagrees with the record: a stale or garbled source
        p = _cache(tmp_path, [NVDA_CACHED])
        got = mq.fetch_daily_closes(
            ["NVDA"], cache_path=p, fetch=lambda t: (165.05, 160.0, "2026-11-23"))
        assert got == []
        assert "::warning::" in capsys.readouterr().out

    def test_no_previous_bar_is_still_rejected(self, tmp_path):
        p = _cache(tmp_path, [NVDA_CACHED])
        assert mq.fetch_daily_closes(
            ["NVDA"], cache_path=p, fetch=lambda t: (165.05, None, "2026-11-23")) == []

    def test_the_corroborated_band_is_bounded(self):
        assert not mq.valid_close(125.53 * 1.7, 125.53, 125.53)
        assert mq.valid_close(125.53 * 1.5, 125.53, 125.6)

    def test_ordinary_moves_are_unchanged(self):
        assert mq.valid_close(130.0, 125.53)
        assert not mq.valid_close(165.05, 125.53)
        assert not mq.valid_close(2.0, None)


class TestTheGuardKeepsItsMemory:
    def test_an_omitted_ticker_keeps_its_last_verified_close(self, tmp_path):
        p = _cache(tmp_path, [NVDA_CACHED,
                              {"ticker": "AAPL", "close": 342.56, "bar_date": "2026-11-20"}])
        mq.persist([mq.Quote("AAPL", 349.08, 342.56, "2026-11-23")], p)
        data = json.loads(p.read_text())
        assert [q["ticker"] for q in data["quotes"]] == ["AAPL"]   # pages read this
        assert data["last_verified"] == [NVDA_CACHED]
        assert mq.load_cache(p)["NVDA"]["close"] == 125.53
        # and it survives a second day of omission
        mq.persist([mq.Quote("AAPL", 350.0, 349.08, "2026-11-24")], p)
        assert mq.load_cache(p)["NVDA"]["close"] == 125.53

    def test_a_returning_ticker_leaves_last_verified(self, tmp_path):
        p = _cache(tmp_path, [], [NVDA_CACHED])
        mq.persist([mq.Quote("NVDA", 130.0, 125.53, "2026-11-23")], p)
        data = json.loads(p.read_text())
        assert "last_verified" not in data
        assert data["quotes"][0]["close"] == 130.0

    def test_a_stale_record_cannot_lock_a_ticker_out(self, tmp_path):
        # weeks without a validated close: the fetch's own previous bar judges
        p = _cache(tmp_path, [], [NVDA_CACHED])
        got = mq.fetch_daily_closes(
            ["NVDA"], cache_path=p, fetch=lambda t: (190.0, 188.0, "2026-12-15"))
        assert [q.close for q in got] == [190.0]
        assert mq.fetch_daily_closes(
            ["NVDA"], cache_path=p, fetch=lambda t: (190.0, 100.0, "2026-12-15")) == []
