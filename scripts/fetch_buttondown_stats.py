#!/usr/bin/env python3
"""Fetch the Buttondown newsletter subscriber count, tags and email results.

Writes ``api/buttondown_stats.json`` for the operator dashboard and the
homepage "Join N readers" social proof. Clean no-op when
``BUTTONDOWN_API_KEY`` is unset (logs one line, exits 0, leaves any
previously committed output untouched) — same convention as every other
optional integration in this repo.

Buttondown API: ``GET /v1/subscribers?page_size=1`` returns a paginated
envelope whose ``count`` field is the total number of subscribers. If the
field is ever missing we skip rather than guess (no page-walking — a
wrong number shown publicly is worse than none).

Usage::

    python scripts/fetch_buttondown_stats.py                 # write api/buttondown_stats.json
    python scripts/fetch_buttondown_stats.py --dry-run       # print, write nothing
    python scripts/fetch_buttondown_stats.py --out /tmp/b.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests  # noqa: E402  (after sys.path fix)

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
log = logging.getLogger("buttondown_stats")

BUTTONDOWN_API_BASE = "https://api.buttondown.com/v1"
HTTP_TIMEOUT = 15


def fetch_subscriber_count(api_key: str) -> Optional[int]:
    """Return the total subscriber count, or None on any failure."""
    try:
        resp = requests.get(
            f"{BUTTONDOWN_API_BASE}/subscribers",
            headers={"Authorization": f"Token {api_key}"},
            params={"page_size": "1", "type": "regular"},
            timeout=HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            log.warning("buttondown: HTTP %s from /subscribers", resp.status_code)
            return None
        data = resp.json() or {}
        count = data.get("count")
        if isinstance(count, int) and count >= 0:
            return count
        log.warning("buttondown: no usable 'count' field in response "
                    "(keys: %s)", sorted(data.keys()))
        return None
    except Exception as exc:  # noqa: BLE001 — never break the nightly job
        log.warning("buttondown: fetch failed: %s", exc)
        return None


def fetch_tag_counts(api_key: str) -> Optional[dict]:
    """Return ``{tag_name: subscriber_count}``, or None on any failure.

    The network-wide total answers "how big is the list"; it cannot
    answer "which surface produced this subscriber", which is the only
    question a funnel needs. Buttondown exposes a per-tag
    ``subscriber_count`` on ``GET /v1/tags``, so the breakdown costs one
    extra request rather than a page-walk of the whole roster.

    Two families matter downstream (see ``engine.funnel``):
      * list tags (``ru-spacex``, ``gallery-subscriber``, show tags) —
        WHAT the subscriber signed up for;
      * ``src-*`` tags — WHERE they came from.
    """
    try:
        resp = requests.get(
            f"{BUTTONDOWN_API_BASE}/tags",
            headers={"Authorization": f"Token {api_key}"},
            params={"page_size": "200"},
            timeout=HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            log.warning("buttondown: HTTP %s from /tags", resp.status_code)
            return None
        data = resp.json() or {}
        results = data.get("results")
        if not isinstance(results, list):
            log.warning("buttondown: no 'results' list on /tags "
                        "(keys: %s)", sorted(data.keys()))
            return None
        counts = {}
        uncounted = []
        for row in results:
            name = (row or {}).get("name")
            count = (row or {}).get("subscriber_count")
            if not (isinstance(name, str) and name):
                continue
            if isinstance(count, int):
                counts[name] = count
            else:
                uncounted.append(name)
        # "This account has no tags" and "the tags endpoint stopped
        # returning subscriber_count" produced byte-identical output before
        # this branch — an empty dict either way — while the warning
        # downstream asserted the first. They need different fixes, so say
        # which one it is. The repo's other client of this endpoint reads
        # only `name` and `id` (engine/newsletter.py), so the count field is
        # not a safe assumption.
        if uncounted:
            log.warning(
                "buttondown: %s of %s tag(s) carried no integer "
                "subscriber_count (e.g. %s) — the per-tag breakdown is "
                "INCOMPLETE, not empty",
                len(uncounted), len(results), ", ".join(uncounted[:5]),
            )
        return counts
    except Exception as exc:  # noqa: BLE001 — never break the nightly job
        log.warning("buttondown: tag fetch failed: %s", exc)
        return None


#: Subscribers read at most when /tags carries no counts (Nov 2026). The
#: list is 14 people today; the cap only stops a runaway walk.
SUBSCRIBER_WALK_MAX = 5000


def count_tags_from_subscribers(api_key: str) -> Optional[dict]:
    """``{tag: subscribers}`` from the subscriber list itself, or None.

    ``GET /v1/tags`` on this account returns every tag WITHOUT a
    ``subscriber_count`` (23 tags, 0 counts on Oct 31 2026), which is why
    ``tag_counts`` read ``{}`` for weeks. Each subscriber row carries its own
    ``tags`` array, so counting them is exact. Only tag names and integers
    leave this function: no address is stored or logged.
    """
    counts: dict = {}
    seen = 0
    url: Optional[str] = f"{BUTTONDOWN_API_BASE}/subscribers"
    params: Optional[dict] = {"page_size": "100", "type": "regular"}
    try:
        while url and seen < SUBSCRIBER_WALK_MAX:
            resp = requests.get(url, headers={"Authorization": f"Token {api_key}"},
                                params=params, timeout=HTTP_TIMEOUT)
            if resp.status_code != 200:
                log.warning("buttondown: HTTP %s walking /subscribers", resp.status_code)
                return None
            data = resp.json() or {}
            for row in data.get("results") or []:
                seen += 1
                for tag in (row or {}).get("tags") or []:
                    if isinstance(tag, str) and tag:
                        counts[tag] = counts.get(tag, 0) + 1
            url = data.get("next") or None
            params = None
    except Exception as exc:  # noqa: BLE001
        log.warning("buttondown: subscriber walk failed: %s", exc)
        return None
    return counts


#: A rate is reported only over at least this many recipients (the funnel's
#: honesty floor); below it the counts are the honest number.
RATE_FLOOR = 30


#: How many ``/emails`` pages the list read follows (50 rows each). The
#: account holds hundreds of emails and the endpoint's order is not a
#: contract, so one page could hold none of the recent ones (Nov 2 2026:
#: the night after the first Nerra Daily send, this read returned ``[]``).
EMAIL_LIST_MAX_PAGES = 8
#: Where the network's one email records each send (``email_id`` per day).
SEND_RECORDS_DIR = _ROOT / "digests" / "nerra_daily" / "email"


def _email_row(row: dict, when: _dt.datetime, api_key: str, *,
               kind: Optional[str] = None) -> dict:
    """One analytics row for a sent email (recipients, opens, clicks ...)."""
    from engine.newsletter import email_analytics

    slug = str(row.get("slug") or "")
    stats = email_analytics(str(row.get("id") or ""), api_key) or {}

    def _n(key):
        value = stats.get(key)
        return value if isinstance(value, int) else None

    recipients = _n("recipients")
    entry = {
        "id": row.get("id"),
        "subject": row.get("subject") or "",
        "slug": slug,
        "kind": kind or ("nerra_daily" if slug.startswith("nerra-daily-") else "show"),
        "publish_date": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "recipients": recipients,
        "deliveries": _n("deliveries"),
        "opens": _n("opens"),
        "clicks": _n("clicks"),
        "unsubscriptions": _n("unsubscriptions"),
    }
    for key in ("opens", "clicks"):
        value = entry[key]
        entry[f"{key[:-1]}_rate"] = (round(value / recipients, 3)
                                     if recipients and recipients >= RATE_FLOOR
                                     and value is not None else None)
    return entry


def _parse_when(raw: str) -> Optional[_dt.datetime]:
    try:
        when = _dt.datetime.fromisoformat(str(raw or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=_dt.timezone.utc)


def committed_sends(cutoff: _dt.datetime, *, records_dir: Path = SEND_RECORDS_DIR) -> list:
    """The Nerra Daily sends the repository itself recorded since *cutoff*
    (``digests/nerra_daily/email/<date>.json`` — ``email_id``, ``created_at``,
    ``subject``). The committed record is the primary read: it cannot miss a
    send the way a list page can."""
    out = []
    for path in sorted(records_dir.glob("*.json"), reverse=True):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        email_id = str(rec.get("email_id") or "").strip()
        when = _parse_when(rec.get("created_at") or rec.get("scheduled_for") or "")
        if not email_id or when is None or when < cutoff:
            continue
        out.append({"id": email_id, "subject": rec.get("subject") or "",
                    "slug": rec.get("slug") or f"nerra-daily-{rec.get('date') or path.stem}",
                    "when": when})
    return out


def fetch_recent_emails(api_key: str, *, days: int = 30, limit: int = 40,
                        records_dir: Path = SEND_RECORDS_DIR) -> Optional[list]:
    """The sent emails of the last *days*, newest first, with their analytics.

    Two reads, merged by id: the committed Nerra Daily send records (never
    missed — the record carries the ``email_id``), then Buttondown's
    ``/emails`` list followed page by page through ``next`` (up to
    :data:`EMAIL_LIST_MAX_PAGES`) for the per-show emails and anything the
    record does not hold. One row per email: id, subject, slug, kind
    (``nerra_daily`` or ``show``), publish date, and Buttondown's counts
    (recipients, deliveries, opens, clicks, unsubscriptions). Rates are null
    under :data:`RATE_FLOOR` recipients. ``None`` only when neither read
    produced a row and the list could not be read at all.
    """
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)
    out: list = []
    seen: set = set()
    for rec in committed_sends(cutoff, records_dir=records_dir):
        if rec["id"] in seen:
            continue
        seen.add(rec["id"])
        out.append(_email_row(rec, rec["when"], api_key, kind="nerra_daily"))

    url: Optional[str] = f"{BUTTONDOWN_API_BASE}/emails"
    # Newest first, inside the window, sent only — the OpenAPI accepts all
    # three (the default order had put the window's rows past page 8).
    params: Optional[dict] = {"page_size": "50", "ordering": "-publish_date",
                              "publish_date__start": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
                              "status": "sent"}
    list_ok = False
    pages = 0
    while url and pages < EMAIL_LIST_MAX_PAGES and len(out) < limit:
        pages += 1
        try:
            resp = requests.get(url, headers={"Authorization": f"Token {api_key}"},
                                params=params, timeout=HTTP_TIMEOUT)
            if resp.status_code != 200:
                log.warning("buttondown: HTTP %s from /emails (page %d)", resp.status_code, pages)
                break
            payload = resp.json() or {}
        except Exception as exc:  # noqa: BLE001
            log.warning("buttondown: email list failed (page %d): %s", pages, exc)
            break
        list_ok = True
        rows = payload.get("results") or []
        for row in rows:
            if (row or {}).get("status") not in ("sent", "imported"):
                continue
            when = _parse_when(row.get("publish_date") or row.get("creation_date") or "")
            if when is None or when < cutoff:
                continue
            email_id = str(row.get("id") or "")
            if not email_id or email_id in seen:
                continue
            seen.add(email_id)
            out.append(_email_row(row, when, api_key))
            if len(out) >= limit:
                break
        url = payload.get("next") or None
        params = None  # ``next`` carries its own query string
    if pages >= EMAIL_LIST_MAX_PAGES and url:
        log.warning("buttondown: /emails list stopped after %d pages with more to read",
                    EMAIL_LIST_MAX_PAGES)
    if not out and not list_ok:
        return None
    out.sort(key=lambda e: e["publish_date"], reverse=True)
    return out


def summarize_nerra_daily(emails: list) -> dict:
    """Last seven Nerra Daily sends: how many, to how many, opened, clicked."""
    recent = [e for e in emails if e.get("kind") == "nerra_daily"][:7]

    def total(key):
        values = [e.get(key) for e in recent if isinstance(e.get(key), int)]
        return sum(values) if values else None

    return {
        "sends": len(recent),
        "last_recipients": recent[0].get("recipients") if recent else None,
        "recipients": total("recipients"),
        "opens": total("opens"),
        "clicks": total("clicks"),
        "unsubscriptions": total("unsubscriptions"),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="api/buttondown_stats.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="print JSON to stdout, write nothing")
    args = parser.parse_args(argv)

    api_key = (os.getenv("BUTTONDOWN_API_KEY") or "").strip()
    if not api_key:
        log.info("buttondown: BUTTONDOWN_API_KEY unset — skipping (clean no-op)")
        return 0

    count = fetch_subscriber_count(api_key)
    if count is None:
        log.warning("buttondown: leaving existing stats untouched")
        return 0

    stats = {
        "fetched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "subscriber_count": count,
    }
    # Per-tag breakdown. Omitted (not zeroed) when the call fails, so a
    # bad night reads as "unknown" rather than "everyone unsubscribed".
    tag_counts = fetch_tag_counts(api_key)
    if count > 0 and not tag_counts:
        walked = count_tags_from_subscribers(api_key)
        if walked:
            tag_counts = walked
            stats["tag_counts_source"] = "subscribers"
    if tag_counts is not None:
        stats["tag_counts"] = dict(sorted(tag_counts.items()))
        stats["source_counts"] = {
            name: n for name, n in sorted(tag_counts.items())
            if name.startswith("src-")
        }
        # An empty breakdown beside a non-zero total is not "no news": it means
        # the tags the Worker is supposed to apply are not arriving, so no
        # capture can be traced to the page or the show that earned it. That is
        # the difference between a funnel and a subscriber count, and it read as
        # a pair of tidy empty objects for weeks. Say it out loud.
        if count > 0 and not tag_counts:
            log.warning(
                "::warning title=Buttondown attribution::%d subscriber(s) and "
                "ZERO tags. resolveSubscribeTags is NOT the suspect — it was "
                "audited Sep 2026 and does put tags in the request body. The "
                "two known causes are (1) an address already on the list when "
                "tagging shipped, which until Sep 2026 could never acquire "
                "tags because the Worker applied them on CREATE only, and (2) "
                "a /tags response without subscriber_count, which looks "
                "identical from here (see the INCOMPLETE warning above). To "
                "tell them apart read-only, dispatch "
                ".github/workflows/buttondown-tag-subscriber.yml in list-all "
                "mode: it prints each subscriber's real tags array.", count,
            )
            stats["attribution_warning"] = (
                "subscribers exist but no tags were returned — captures cannot "
                "be attributed to a surface"
            )
        elif count > 0 and not stats["source_counts"]:
            log.warning(
                "::warning title=Buttondown attribution::tags exist but none "
                "are src-* — captures can be traced to a LIST but not to the "
                "surface that earned them."
            )

    emails = fetch_recent_emails(api_key)
    if emails is not None:
        stats["emails"] = emails
        stats["nerra_daily"] = summarize_nerra_daily(emails)

    if args.dry_run:
        print(json.dumps(stats, indent=2))
        return 0

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    log.info("buttondown: wrote %s (%d subscribers)", out_path, count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
