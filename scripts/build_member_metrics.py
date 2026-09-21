#!/usr/bin/env python3
"""Aggregate paid-member counts into ``api/member_metrics.json``.

Nerra Personal has been sellable since Aug 2026 — real Stripe Payment Links,
a Worker that mints and revokes feed tokens, a working sample edition — and
paid conversion has been measured NOWHERE. There is no committed Stripe,
member or MRR artifact anywhere in the repo, so "is anyone paying for this"
could not be answered from the record, which also means no change to the
Personal funnel could be scored. That is what this closes.

**Counts only, never a record.** The Worker's ``/api/admin/personal-specs``
returns each active member's ``first_name``, ``city`` and chosen shows. With
a handful of members a name plus a city identifies a person, and this file is
committed to a public repository, so nothing here writes a name, a city, an
email or a feed token. The output is integers and histograms of SHOW SLUGS.
Same rule as ``scripts/build_personal_feeds.py``: PII-light by construction,
not by reviewer vigilance.

**What it can and cannot see.** The admin endpoint lists only records with
``status == "active"`` and a feed token — i.e. paying members. Free Nerra
accounts (every newsletter signup creates one) are NOT in that list.

**Stripe (Sep 21 2026).** The account is the operator's "Lil Learning"
Stripe account (confirmed 2026-09-21), which carries the ``Nerra Personal
monthly`` price alongside its own products — so ``mrr_usd`` here is Nerra's
share of a SHARED account, not the account's total. Today every recurring
price on it is Nerra Personal, so the two are the same number; if that stops
being true, filter by product before this figure is quoted anywhere.

``mrr_usd`` and ``trialing`` were hardcoded ``null``
because nothing in this repo read Stripe. They are real now, computed from
live subscriptions over plain HTTP — no new dependency, and no ``stripe``
package on the runner. Three rules the arithmetic follows:

* **MRR is normalised, never guessed.** A yearly price contributes a twelfth
  of itself, a weekly one 52/12ths. Percentage and fixed discounts are
  applied because a discounted subscription is not worth its list price.
* **Currency is never converted.** Only USD subscriptions are summed. A
  subscription in another currency is counted in
  ``mrr_excluded_subscriptions`` and its currency named, so the figure is
  understated in a way the file declares rather than wrong in a way it hides.
* **Nothing identifies anybody.** Stripe hands back customer ids, emails and
  payment methods; none of it is written. The output is integers.

``free_accounts`` is DERIVED, not fetched — Stripe has no concept of a free
account, and the Worker's admin list returns paid records only. Every
newsletter signup creates a Nerra account, so the free tier is the committed
Buttondown subscriber count minus the paid members, and
``free_accounts_source`` says so on the record. Null still means unmeasured
and is never written as ``0``.

Clean no-op without ``PERSONAL_ADMIN_TOKEN``: an existing file is left
untouched rather than overwritten with nulls, because a host that cannot
authenticate must not look like a network with no members — the failure mode
``build_personal_feeds`` documents at its own fetch path.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(message)s",
                    stream=sys.stdout)
log = logging.getLogger("build_member_metrics")

API_BASE = os.environ.get("PERSONAL_API_BASE", "https://api.nerranetwork.com")
DEFAULT_OUT = REPO_ROOT / "api" / "member_metrics.json"
HTTP_TIMEOUT = 60


def fetch_specs(token: str) -> Optional[list]:
    """Return the admin endpoint's ``specs`` list, or None on any failure."""
    import requests

    try:
        resp = requests.get(
            f"{API_BASE}/api/admin/personal-specs",
            headers={"Authorization": f"Bearer {token}"},
            timeout=HTTP_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 — never break the nightly job
        log.warning("member metrics: request failed: %s", exc)
        return None
    if resp.status_code == 503:
        # The Worker answers 503 until the operator provisions KV and the
        # bucket. That is "not set up yet", not "nobody subscribed".
        log.info("member metrics: Worker reports not configured (503)")
        return None
    if resp.status_code != 200:
        log.warning("member metrics: HTTP %s from /api/admin/personal-specs",
                    resp.status_code)
        return None
    try:
        payload = resp.json() or {}
    except Exception as exc:  # noqa: BLE001
        log.warning("member metrics: unreadable JSON: %s", exc)
        return None
    specs = payload.get("specs")
    if not isinstance(specs, list):
        log.warning("member metrics: no 'specs' list in response")
        return None
    return specs



# ---------------------------------------------------------------------------
# Stripe
# ---------------------------------------------------------------------------

STRIPE_API_BASE = os.environ.get("STRIPE_API_BASE", "https://api.stripe.com")

#: MONTHS PER ONE BILLING INTERVAL — the divisor that turns a price into a
#: monthly figure. A year is 12 months, so a $99/year plan contributes
#: 9900/12 = $8.25; a week is 12/52 of a month, so a $10/week plan
#: contributes 1000/(12/52) = $43.33.
#:
#: The direction matters and is easy to invert. Written the other way round
#: (intervals per month, year = 1/12) the same division reports a yearly plan
#: at 144x its real value, and nothing downstream would look wrong — a wrong
#: revenue number looks exactly like a right one. ``_INTERVAL_MONTHS`` is
#: pinned by a test that checks a yearly plan against a monthly one.
#:
#: An interval absent from this map is NOT guessed. The subscription is
#: excluded and counted, because inventing a conversion factor is how a
#: revenue figure becomes confidently wrong.
_INTERVAL_MONTHS = {
    "day": 12.0 / 365.0,
    "week": 12.0 / 52.0,
    "month": 1.0,
    "year": 12.0,
}

#: MRR is reported in this currency and no other. Stripe does not convert and
#: neither do we: a rate we made up would be indistinguishable from a real
#: one in the committed file.
MRR_CURRENCY = "usd"

#: The Stripe products that are NERRA revenue.
#:
#: The Stripe account is SHARED (confirmed by the operator 2026-09-21): it is
#: the "Lil Learning" account, and alongside Nerra Personal it carries the
#: Lil Words products — Coins, Learn, and Learn Family. Summing every
#: subscription on the account would put Lil Words revenue into a file
#: labelled Nerra's MRR, and it would look completely normal: one number,
#: no error, just wrong. Today there is a single active subscription and it
#: IS Nerra Personal, so the filtered and unfiltered totals agree — which is
#: exactly why this has to go in NOW rather than the first month someone
#: subscribes to Lil Words.
#:
#: Override with ``NERRA_STRIPE_PRODUCT_IDS`` (comma-separated) when a new
#: Nerra product ships; anything not listed is counted under
#: ``mrr_excluded_other_product`` and named, never silently dropped.
NERRA_PRODUCT_IDS = frozenset({
    "prod_V7zECn362K80w6",  # Nerra Personal
    "prod_V7zEuA2JJCwZXR",  # Personal News Network (Personal + city brief)
    "prod_V7zEfCjuVbaS38",  # Support the Nerra Network (monthly)
})


def _nerra_product_ids() -> frozenset:
    raw = os.environ.get("NERRA_STRIPE_PRODUCT_IDS", "").strip()
    if not raw:
        return NERRA_PRODUCT_IDS
    return frozenset(p.strip() for p in raw.split(",") if p.strip())


def _subscription_products(sub: dict) -> set:
    """Every product id billed by this subscription."""
    out = set()
    for item in ((sub.get("items") or {}).get("data")) or []:
        product = (item.get("price") or {}).get("product")
        if isinstance(product, dict):
            product = product.get("id")
        if product:
            out.add(str(product))
    return out


def _is_nerra_subscription(sub: dict) -> bool:
    """True when every product on the subscription is a Nerra one.

    A mixed subscription is NOT counted: splitting it would need per-item
    arithmetic this does not do, and guessing is how a revenue figure becomes
    confidently wrong. It is reported as excluded instead.
    """
    products = _subscription_products(sub)
    return bool(products) and products <= _nerra_product_ids()


def _stripe_get(path: str, key: str, params: Optional[dict] = None) -> Optional[dict]:
    """One Stripe GET, or None on any failure.

    Plain HTTP on purpose: ``requests`` is already a dependency and the
    ``stripe`` package is not, so this adds nothing to the runner's install.
    """
    import requests

    try:
        resp = requests.get(
            f"{STRIPE_API_BASE}{path}",
            headers={"Authorization": f"Bearer {key}",
                     "Stripe-Version": "2024-06-20"},
            params=params or {},
            timeout=HTTP_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 — never break the nightly job
        log.warning("stripe: request to %s failed: %s", path, exc)
        return None
    if resp.status_code != 200:
        # Never log the body: Stripe error payloads can echo request params.
        log.warning("stripe: HTTP %s from %s", resp.status_code, path)
        return None
    try:
        return resp.json() or {}
    except Exception as exc:  # noqa: BLE001
        log.warning("stripe: unreadable JSON from %s: %s", path, exc)
        return None


def _iter_subscriptions(key: str, status: str):
    """Yield every subscription with *status*, following pagination.

    Stops on the first failed page rather than returning a short list that
    would silently understate MRR.
    """
    starting_after = ""
    for _ in range(100):  # 10k subscriptions; a hard stop, never a loop
        params = {"status": status, "limit": 100}
        if starting_after:
            params["starting_after"] = starting_after
        page = _stripe_get("/v1/subscriptions", key, params)
        if page is None:
            raise RuntimeError(f"stripe: subscription page failed ({status})")
        data = page.get("data") or []
        for sub in data:
            yield sub
        if not page.get("has_more") or not data:
            return
        starting_after = data[-1].get("id", "")
        if not starting_after:
            return


def _discount_multiplier(sub: dict) -> float:
    """What fraction of list price this subscription actually bills.

    A percentage coupon scales the price; a fixed-amount coupon is handled by
    the caller, which needs the cents. A subscription with neither bills in
    full.
    """
    multiplier = 1.0
    for discount in (sub.get("discounts") or []):
        if not isinstance(discount, dict):
            continue
        coupon = discount.get("coupon") or {}
        percent = coupon.get("percent_off")
        if isinstance(percent, (int, float)) and 0 < percent <= 100:
            multiplier *= (100.0 - float(percent)) / 100.0
    return multiplier


def _fixed_discount_cents(sub: dict) -> int:
    """Fixed-amount coupon value in cents, USD only."""
    total = 0
    for discount in (sub.get("discounts") or []):
        if not isinstance(discount, dict):
            continue
        coupon = discount.get("coupon") or {}
        amount = coupon.get("amount_off")
        if (isinstance(amount, int)
                and str(coupon.get("currency", "")).lower() == MRR_CURRENCY):
            total += amount
    return total


def _subscription_mrr_cents(sub: dict) -> Optional[int]:
    """Monthly value of one subscription in cents, or None if unconvertible.

    None means "this subscription exists and we are deliberately not counting
    it" — a non-USD currency or an interval outside ``_INTERVAL_MONTHS``. The
    caller records the exclusion rather than dropping it silently.
    """
    if str(sub.get("currency", "")).lower() != MRR_CURRENCY:
        return None

    cents = 0.0
    items = ((sub.get("items") or {}).get("data")) or []
    for item in items:
        price = item.get("price") or {}
        unit_amount = price.get("unit_amount")
        if not isinstance(unit_amount, int):
            # Metered or tiered pricing has no flat unit amount; it cannot be
            # turned into MRR without usage data this script does not fetch.
            return None
        recurring = price.get("recurring") or {}
        months = _INTERVAL_MONTHS.get(str(recurring.get("interval", "")))
        if not months:
            return None
        interval_count = recurring.get("interval_count") or 1
        quantity = item.get("quantity") or 1
        # unit_amount is per interval_count intervals.
        cents += (unit_amount * quantity) / (months * float(interval_count))

    cents *= _discount_multiplier(sub)
    cents -= _fixed_discount_cents(sub)
    return max(0, int(round(cents)))


def fetch_stripe_metrics(key: str) -> Optional[Dict[str, Any]]:
    """Revenue and trial state from live Stripe subscriptions.

    Returns None on any failure so the caller leaves the previous numbers
    alone — the same rule the Worker fetch follows. Nothing that could
    identify a customer is read out of the response.
    """
    try:
        active = list(_iter_subscriptions(key, "active"))
        trialing = list(_iter_subscriptions(key, "trialing"))
    except RuntimeError as exc:
        log.warning("%s — leaving revenue figures untouched", exc)
        return None

    mrr_cents = 0
    excluded = 0
    excluded_currencies: Counter = Counter()
    canceling = 0
    by_interval: Counter = Counter()

    other_product = 0
    for sub in active:
        if not _is_nerra_subscription(sub):
            # A shared Stripe account: Lil Words revenue is not Nerra's.
            other_product += 1
            continue
        if sub.get("cancel_at_period_end"):
            canceling += 1
        for item in ((sub.get("items") or {}).get("data")) or []:
            interval = ((item.get("price") or {}).get("recurring")
                        or {}).get("interval")
            if interval:
                by_interval[str(interval)] += 1
        value = _subscription_mrr_cents(sub)
        if value is None:
            excluded += 1
            currency = str(sub.get("currency", "") or "unknown").lower()
            excluded_currencies[currency] += 1
            continue
        mrr_cents += value

    nerra_active = [s for s in active if _is_nerra_subscription(s)]
    return {
        "mrr_usd": round(mrr_cents / 100.0, 2),
        "trialing": len([s for s in trialing if _is_nerra_subscription(s)]),
        "active_subscriptions": len(nerra_active),
        # Declared, not hidden: subscriptions on the shared account that
        # belong to another product line. A non-zero value here is normal
        # and means the account is doing more than Nerra.
        "mrr_excluded_other_product": other_product,
        # Subscriptions the member has asked to end. A paid_active_total that
        # is flat while this rises is churn the headline number cannot see.
        "canceling_at_period_end": canceling,
        "subscriptions_by_interval": dict(sorted(by_interval.items())),
        # Declared, not hidden: MRR is understated by exactly these.
        "mrr_excluded_subscriptions": excluded,
        "mrr_excluded_currencies": dict(sorted(excluded_currencies.items())),
        "mrr_currency": MRR_CURRENCY,
    }


def derive_free_accounts(paid_active_total: int) -> Optional[Dict[str, Any]]:
    """Free accounts, from the committed Buttondown count minus paid members.

    Stripe has no concept of a free account and the Worker's admin list
    returns paid records only, so this is the one source there is: every
    newsletter signup creates a Nerra account (``workers/gallery`` mints the
    JWT on subscribe), and paid members are a subset of those.

    Returns None when the Buttondown file is missing or unreadable — null is
    unmeasured, and a missing file must never render as "no free accounts".
    """
    path = REPO_ROOT / "api" / "buttondown_stats.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    total = data.get("subscriber_count")
    if not isinstance(total, int):
        return None
    return {
        "free_accounts": max(0, total - max(0, paid_active_total)),
        "free_accounts_source": (
            "derived: api/buttondown_stats.json subscriber_count minus "
            "paid_active_total — every newsletter signup creates a Nerra "
            "account and paid members are a subset of them"
        ),
        "newsletter_subscribers": total,
    }


def summarise(specs: list) -> Dict[str, Any]:
    """Counts and show histograms — no field that could name a person."""
    tiers: Counter = Counter()
    shows: Counter = Counter()
    addons: Counter = Counter()
    with_city_brief = 0
    on_default_lineup = 0

    for rec in specs:
        if not isinstance(rec, dict):
            continue
        tiers[str(rec.get("tier") or "unknown")] += 1
        for slug in (rec.get("shows") or []):
            if isinstance(slug, str) and slug:
                shows[slug] += 1
        for name in (rec.get("addons") or []):
            if isinstance(name, str) and name:
                addons[name] += 1
        # The COUNT of members who have a city brief, never which city:
        # a city plus a first name identifies someone at this scale.
        if rec.get("city") or (rec.get("cities") or []):
            with_city_brief += 1
        if rec.get("default_lineup"):
            on_default_lineup += 1

    return {
        "paid_active_total": len(specs),
        "by_tier": dict(sorted(tiers.items())),
        "by_addon": dict(sorted(addons.items())),
        "with_city_brief": with_city_brief,
        # Members who never chose 2+ shows and are being served the starter
        # lineup. A product signal: high here means the picker is not landing.
        "on_default_lineup": on_default_lineup,
        "shows_chosen": dict(shows.most_common()),
        # Revenue, trial state and the free tier are filled by the caller
        # from Stripe and the committed Buttondown count. They stay null when
        # unreachable — null is unmeasured, and it is never written as 0.
        "free_accounts": None,
        "mrr_usd": None,
        "trialing": None,
    }


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--specs", default="",
                        help="Read a local specs JSON instead of the Worker "
                             "(testing only; must not contain real members).")
    parser.add_argument("--stripe", default="",
                        help="Read a pre-computed Stripe metrics JSON instead "
                             "of calling the API (testing only).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    out_path = Path(args.out)

    if args.specs:
        raw = json.loads(Path(args.specs).read_text(encoding="utf-8"))
        specs = raw.get("specs", raw) if isinstance(raw, dict) else raw
    else:
        token = os.environ.get("PERSONAL_ADMIN_TOKEN", "").strip()
        if not token:
            log.info("PERSONAL_ADMIN_TOKEN unset — skipping member metrics "
                     "(clean no-op)")
            if out_path.exists():
                # Never replace real counts with nulls.
                return 0
            payload = {
                "generated_at": datetime.now(timezone.utc).isoformat(
                    timespec="seconds"),
                "configured": False,
                "note": "PERSONAL_ADMIN_TOKEN not set — membership is "
                        "unmeasured, which is not the same as zero members",
            }
            if args.dry_run:
                print(json.dumps(payload, indent=2))
                return 0
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(payload, indent=2) + "\n",
                                encoding="utf-8")
            log.info("wrote %s (unconfigured placeholder)", out_path)
            return 0
        specs = fetch_specs(token)
        if specs is None:
            log.warning("member metrics: no data this run — leaving %s as is",
                        out_path)
            return 0

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "configured": True,
        **summarise(specs),
    }

    # Revenue and trial state. A missing key or an unreachable Stripe leaves
    # the nulls in place — a dashboard tile reading "unmeasured" is correct,
    # a tile reading "$0" is a lie about a business that has customers.
    stripe_key = os.environ.get(
        "STRIPE_SECRET_KEY", os.environ.get("STRIPE_API_KEY", "")).strip()
    if args.stripe:
        payload.update(json.loads(
            Path(args.stripe).read_text(encoding="utf-8")))
        payload["stripe_configured"] = True
    elif stripe_key:
        metrics = fetch_stripe_metrics(stripe_key)
        payload["stripe_configured"] = metrics is not None
        if metrics:
            payload.update(metrics)
    else:
        log.info("STRIPE_SECRET_KEY unset — revenue stays unmeasured (null)")
        payload["stripe_configured"] = False

    # The free tier, derived from the committed newsletter count.
    free = derive_free_accounts(payload.get("paid_active_total") or 0)
    if free:
        payload.update(free)

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    log.info("wrote %s (paid_active=%s, mrr_usd=%s, trialing=%s, tiers=%s)",
             out_path, payload["paid_active_total"], payload.get("mrr_usd"),
             payload.get("trialing"), payload["by_tier"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
