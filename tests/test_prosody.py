"""Tests for ``engine.prosody.inject_prosody_tags``.

The injector replaces the May 2026 DELIVERY prompt block: instead of
asking the LLM to insert ``<emphasis>...</emphasis>`` around news-anchor
emphasis points (currency amounts, percentages, stock cashtags), the
pipeline does it deterministically at script-save time.

These tests pin every shape the regex must catch — and every shape it
must NOT catch (matching the wrong thing here puts garbage into the TTS
input which Grok voices aloud).
"""

from __future__ import annotations

import pytest

from engine.prosody import inject_prosody_tags


class TestCurrencyEmphasis:

    def test_plain_dollar_amount(self):
        out = inject_prosody_tags("TSLA closed at $390.82 today.")
        assert out == "TSLA closed at <emphasis>$390.82</emphasis> today."

    def test_dollar_with_commas(self):
        out = inject_prosody_tags("Revenue hit $1,234,567 last quarter.")
        assert out == "Revenue hit <emphasis>$1,234,567</emphasis> last quarter."

    def test_dollar_with_sign_prefix(self):
        out = inject_prosody_tags("Up +$5.50 and down -$2.30 today.")
        assert "<emphasis>+$5.50</emphasis>" in out
        assert "<emphasis>-$2.30</emphasis>" in out

    def test_whole_dollar(self):
        out = inject_prosody_tags("It costs $200 per unit.")
        assert out == "It costs <emphasis>$200</emphasis> per unit."

    def test_dollar_followed_by_word_not_wrapped(self):
        """``$5usd`` should NOT match — that's not a clean money token."""
        out = inject_prosody_tags("Pay $5usd or skip.")
        assert "<emphasis>" not in out


class TestPercentageEmphasis:

    def test_simple_pct(self):
        out = inject_prosody_tags("Margins improved 5%.")
        assert out == "Margins improved <emphasis>5%</emphasis>."

    def test_decimal_pct(self):
        out = inject_prosody_tags("CPI came in at 2.5% year-over-year.")
        assert out == "CPI came in at <emphasis>2.5%</emphasis> year-over-year."

    def test_100_pct(self):
        out = inject_prosody_tags("100% of trades closed green.")
        assert out == "<emphasis>100%</emphasis> of trades closed green."


class TestCashtagEmphasis:

    def test_tsla_cashtag(self):
        out = inject_prosody_tags("$TSLA was the volume leader.")
        assert out == "<emphasis>$TSLA</emphasis> was the volume leader."

    def test_multiple_cashtags(self):
        out = inject_prosody_tags("$NVDA outpaced $AAPL on revenue growth.")
        assert "<emphasis>$NVDA</emphasis>" in out
        assert "<emphasis>$AAPL</emphasis>" in out

    def test_cashtag_with_trailing_letter_not_matched(self):
        """``$TSLAish`` is not a real cashtag — shouldn't match."""
        out = inject_prosody_tags("$TSLAish is not a thing.")
        assert "<emphasis>" not in out

    def test_lowercase_after_dollar_not_a_cashtag(self):
        """``$tsla`` (lowercase) is not a cashtag pattern."""
        out = inject_prosody_tags("Random $tsla string.")
        assert "<emphasis>" not in out


class TestIdempotenceAndSafety:

    def test_idempotent_double_application(self):
        """Calling twice produces the same output — the function must
        never double-wrap an already-emphasised token."""
        once = inject_prosody_tags("TSLA at $390.82, up 2.5%.")
        twice = inject_prosody_tags(once)
        assert once == twice

    def test_existing_emphasis_preserved_untouched(self):
        """Pre-existing ``<emphasis>...</emphasis>`` regions pass through
        without modification — even when they contain tokens the regex
        would otherwise match."""
        text = "Open at <emphasis>$390.82</emphasis> please."
        assert inject_prosody_tags(text) == text

    def test_pre_existing_emphasis_around_unrelated_word(self):
        """Emphasis on a word, currency outside: only the currency wraps."""
        out = inject_prosody_tags(
            "It went <emphasis>parabolic</emphasis> at $500."
        )
        assert "<emphasis>parabolic</emphasis>" in out
        assert "<emphasis>$500</emphasis>" in out

    def test_empty_input_returns_empty(self):
        assert inject_prosody_tags("") == ""

    def test_none_input_passthrough(self):
        # Defensive: callers must never pass None, but the function
        # should not crash if they do.
        assert inject_prosody_tags(None) is None

    def test_plain_prose_unchanged(self):
        text = "Tesla announced new Cybertruck shipments today."
        assert inject_prosody_tags(text) == text


class TestRealEpisodeShape:
    """Smoke-check the function against the actual line shapes we
    see in our digests today — ``**REAL-TIME TSLA price:** $390.82 ▲
    $9.44 (2.5%)`` is the canonical Tesla shape, and the May 2026
    review newsletter often quotes percentages mid-sentence."""

    def test_tesla_realtime_price_line(self):
        out = inject_prosody_tags(
            "**REAL-TIME TSLA price:** $390.82 ▲ $9.44 (2.5%)"
        )
        assert "<emphasis>$390.82</emphasis>" in out
        assert "<emphasis>$9.44</emphasis>" in out
        assert "<emphasis>2.5%</emphasis>" in out

    def test_mit_trade_summary_sentence(self):
        out = inject_prosody_tags(
            "NVDA gained 3.2% on the day, closing at $145.20."
        )
        assert "<emphasis>3.2%</emphasis>" in out
        assert "<emphasis>$145.20</emphasis>" in out
