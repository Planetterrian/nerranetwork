"""``api/member_metrics.json`` reports real revenue, and still names nobody.

``mrr_usd``, ``trialing`` and ``free_accounts`` were hardcoded ``null``
because nothing in the repo read Stripe. They are computed now, and the two
things that can go wrong with a committed revenue file are both guarded here.

**The arithmetic fails silently.** CLAUDE.md's own lesson: loops over TEXT
fail loudly, loops over NUMBERS fail silently, because a wrong number looks
exactly like a right one. The interval conversion is the place this happens —
written the wrong way round, a yearly plan reports at 144x and no downstream
surface looks broken. So the conversions are pinned against each other rather
than against a magic constant.

**The file is public and there are about five members.** One first name plus
one city identifies a person. The PII guard walks the whole serialised
payload rather than checking the keys the writer happens to set today.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_member_metrics as B  # noqa: E402


def _sub(currency="usd", unit=499, interval="month", interval_count=1,
         quantity=1, discounts=None, cancel=False):
    return {
        "currency": currency,
        "cancel_at_period_end": cancel,
        "discounts": discounts or [],
        "items": {"data": [{
            "quantity": quantity,
            "price": {
                "unit_amount": unit,
                "recurring": {"interval": interval,
                              "interval_count": interval_count},
            },
        }]},
    }


class TestMrrArithmetic:
    def test_a_monthly_plan_is_its_own_price(self):
        assert B._subscription_mrr_cents(_sub(unit=499)) == 499

    def test_a_yearly_plan_is_a_twelfth_not_twelve_times(self):
        """The inversion that would report 144x, pinned against monthly.

        Stated as a relationship rather than a literal: a year of the yearly
        plan must cost the same as twelve months of the monthly one.
        """
        yearly = B._subscription_mrr_cents(_sub(unit=9900, interval="year"))
        monthly_equivalent = B._subscription_mrr_cents(_sub(unit=9900 // 12))
        assert yearly == pytest.approx(monthly_equivalent, abs=1)
        assert yearly < 9900, (
            "a yearly plan is contributing MORE than its annual price to "
            "MONTHLY recurring revenue — the interval map is inverted")

    def test_a_weekly_plan_is_more_than_its_price(self):
        """The other direction of the same inversion."""
        weekly = B._subscription_mrr_cents(_sub(unit=1000, interval="week"))
        assert weekly > 1000
        assert weekly == pytest.approx(1000 * 52 / 12, abs=1)

    def test_interval_count_divides(self):
        """$30 every 3 months is $10 a month."""
        assert B._subscription_mrr_cents(
            _sub(unit=3000, interval="month", interval_count=3)) == 1000

    def test_quantity_multiplies(self):
        assert B._subscription_mrr_cents(_sub(unit=499, quantity=3)) == 1497

    def test_percentage_and_fixed_discounts_are_applied(self):
        """A discounted subscription is not worth its list price."""
        assert B._subscription_mrr_cents(
            _sub(discounts=[{"coupon": {"percent_off": 50}}])) == 250
        assert B._subscription_mrr_cents(
            _sub(discounts=[{"coupon": {"amount_off": 200,
                                        "currency": "usd"}}])) == 299

    def test_a_discount_can_never_make_revenue_negative(self):
        assert B._subscription_mrr_cents(
            _sub(discounts=[{"coupon": {"amount_off": 99900,
                                        "currency": "usd"}}])) == 0

    def test_a_fixed_discount_in_another_currency_is_ignored(self):
        """Subtracting 200 CAD cents from a USD price would invent a rate."""
        assert B._subscription_mrr_cents(
            _sub(discounts=[{"coupon": {"amount_off": 200,
                                        "currency": "cad"}}])) == 499


class TestUnconvertibleIsExcludedNotGuessed:
    @pytest.mark.parametrize("sub", [
        _sub(currency="cad"),
        _sub(currency="eur"),
        _sub(interval="fortnight"),
        {"currency": "usd", "items": {"data": [
            {"price": {"unit_amount": None,
                       "recurring": {"interval": "month"}}}]}},
    ])
    def test_it_returns_none_rather_than_a_number(self, sub):
        """None is "we are deliberately not counting this"."""
        assert B._subscription_mrr_cents(sub) is None

    def test_no_currency_conversion_table_exists(self):
        """A made-up rate in a committed file is indistinguishable from a
        real one, so there must be nothing to make one up with."""
        assert B.MRR_CURRENCY == "usd"
        source = (ROOT / "scripts" / "build_member_metrics.py").read_text(
            encoding="utf-8")
        for token in ("exchange_rate", "fx_rate", "USD_PER_", "_TO_USD"):
            assert token not in source, (
                f"a currency conversion appeared: {token!r}")


class TestNullNeverBecomesZero:
    def test_summarise_leaves_revenue_unmeasured(self):
        """The Worker knows nothing about revenue; it must not claim zero."""
        result = B.summarise([{"tier": "personal", "shows": ["tesla"]}])
        assert result["mrr_usd"] is None
        assert result["trialing"] is None
        assert result["free_accounts"] is None

    def test_free_accounts_is_none_when_the_source_is_missing(self, tmp_path,
                                                              monkeypatch):
        monkeypatch.setattr(B, "REPO_ROOT", tmp_path)
        assert B.derive_free_accounts(1) is None

    def test_free_accounts_subtracts_paid_members_and_says_so(self, tmp_path,
                                                             monkeypatch):
        api = tmp_path / "api"
        api.mkdir()
        (api / "buttondown_stats.json").write_text(
            json.dumps({"subscriber_count": 5}), encoding="utf-8")
        monkeypatch.setattr(B, "REPO_ROOT", tmp_path)
        result = B.derive_free_accounts(2)
        assert result["free_accounts"] == 3
        assert result["newsletter_subscribers"] == 5
        assert "derived" in result["free_accounts_source"]

    def test_free_accounts_never_goes_negative(self, tmp_path, monkeypatch):
        api = tmp_path / "api"
        api.mkdir()
        (api / "buttondown_stats.json").write_text(
            json.dumps({"subscriber_count": 2}), encoding="utf-8")
        monkeypatch.setattr(B, "REPO_ROOT", tmp_path)
        assert B.derive_free_accounts(9)["free_accounts"] == 0

    def test_a_missing_stripe_key_leaves_the_numbers_alone(self, tmp_path,
                                                          monkeypatch,
                                                          capsys):
        """An unconfigured host must not look like a business with no revenue."""
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("STRIPE_API_KEY", raising=False)
        specs = tmp_path / "specs.json"
        specs.write_text(json.dumps({"specs": [{"tier": "personal"}]}),
                         encoding="utf-8")
        out = tmp_path / "member_metrics.json"
        assert B.main(["--specs", str(specs), "--out", str(out)]) == 0
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["mrr_usd"] is None
        assert payload["trialing"] is None
        assert payload["stripe_configured"] is False


class TestNoPii:
    """The output is committed to a public repo and names about five people."""

    #: Fields Stripe and the Worker return that could identify a member.
    FORBIDDEN_KEYS = (
        "email", "name", "first_name", "last_name", "city", "cities",
        "customer", "customer_id", "token", "feed_token", "phone",
        "address", "postal_code", "ip", "payment_method", "last4",
        "subscription", "invoice", "receipt",
    )

    @pytest.fixture
    def payload(self, tmp_path, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("STRIPE_API_KEY", raising=False)
        stripe_file = tmp_path / "stripe.json"
        stripe_file.write_text(json.dumps({
            "mrr_usd": 4.99, "trialing": 0, "active_subscriptions": 1,
            "canceling_at_period_end": 0,
            "subscriptions_by_interval": {"month": 1},
            "mrr_excluded_subscriptions": 0, "mrr_excluded_currencies": {},
            "mrr_currency": "usd",
        }), encoding="utf-8")
        specs = tmp_path / "specs.json"
        specs.write_text(json.dumps({"specs": [{
            "tier": "personal",
            "first_name": "Dana",
            "city": "Kelowna",
            "feed_token": "tok_secret",
            "shows": ["tesla", "spacex"],
            "addons": ["city_brief"],
        }]}), encoding="utf-8")
        out = tmp_path / "member_metrics.json"
        assert B.main(["--specs", str(specs), "--stripe", str(stripe_file),
                       "--out", str(out)]) == 0
        return out.read_text(encoding="utf-8")

    def test_no_identifying_value_survives(self, payload):
        """The real values from the fixture must be absent from the file."""
        for value in ("Dana", "Kelowna", "tok_secret"):
            assert value not in payload, (
                f"{value!r} reached the committed member metrics file")

    def test_no_identifying_key_survives(self, payload):
        """Walk the whole structure, not the keys the writer sets today."""
        data = json.loads(payload)

        def walk(node, path=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    lowered = key.lower()
                    assert lowered not in self.FORBIDDEN_KEYS, (
                        f"PII-shaped key {key!r} at {path}")
                    walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    walk(item, f"{path}[{i}]")

        walk(data)

    def test_the_counts_still_got_through(self, payload):
        """PII-light must not mean information-free."""
        data = json.loads(payload)
        assert data["paid_active_total"] == 1
        assert data["with_city_brief"] == 1
        assert data["shows_chosen"] == {"tesla": 1, "spacex": 1}
        assert data["mrr_usd"] == 4.99

    def test_the_committed_file_is_clean(self):
        """Whatever is on disk right now, checked the same way."""
        path = ROOT / "api" / "member_metrics.json"
        if not path.exists():
            pytest.skip("no committed member metrics file")
        data = json.loads(path.read_text(encoding="utf-8"))

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    assert key.lower() not in self.FORBIDDEN_KEYS, (
                        f"committed member metrics carries {key!r}")
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(data)
