#!/usr/bin/env python3
"""Print a funnel-tagged URL for a link the operator places BY HAND.

Every link the pipeline publishes is tagged by ``engine.funnel``; the links
a person pastes into a Google Ads final URL, a boosted post or a house ad
were not, and arrived as Direct traffic (Nov 3 2026: 492 of 999 sessions
in 28 days were an untagged ad campaign landing on one page). This is the
habit that closes the gap — the URL comes from the one owner, never from
a hand-rolled query string.

Usage::

    # a paid placement: campaign NUMBER from the Ads account, ad-group slug
    python scripts/funnel_link.py ad --campaign 1 --variant personal-tips \\
        --to personal-interest.html [--product personal|network]

    # a post about one episode (X, LinkedIn, ...); --to defaults to the
    # show's own funnel destination
    python scripts/funnel_link.py post --show spacex --episode 150 --source x \\
        [--to blog/spacex/ep150.html] [--surface gallery]

    # what the funnel would read from any URL
    python scripts/funnel_link.py parse "https://nerranetwork.com/?utm_campaign=..."

Prints the URL alone on stdout so it can be piped or copied; ``parse``
prints the campaign's fields, or says the URL is not a Nerra campaign.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qs, urlparse

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine import funnel as F  # noqa: E402


def _destination(to: str) -> str:
    to = (to or "").strip()
    if not to:
        return ""
    if "://" in to:
        return to
    return f"{F.NETWORK_BASE_URL}/{to.lstrip('/')}"


def _show_destination(show: str) -> str:
    """The show's own funnel destination, from its YAML (the show page)."""
    from engine.config import load_config

    path = _ROOT / "shows" / f"{show}.yaml"
    if not path.exists():
        raise SystemExit(f"no show YAML at {path}")
    return F.destination_for(load_config(path), channel="en")


def ad_url(campaign: int, variant: str, to: str, product: str) -> str:
    return F.ad_link(_destination(to), campaign, variant, product=product)


def post_url(show: str, episode: int, source: str, to: str = "",
             surface: str = "", placement: str = F.PLACEMENT_BODY) -> str:
    dest = _destination(to) or _show_destination(show)
    return F.episode_link(dest, show, episode, channel="en", kind="post",
                          source=source, placement=placement, variant=surface)


def parse_url(url: str) -> Optional[F.Campaign]:
    query = parse_qs(urlparse(url).query)
    campaign = (query.get("utm_campaign") or [""])[0]
    return F.parse_campaign_id(campaign)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    ad = sub.add_parser("ad", help="a paid placement (Google Ads final URL)")
    ad.add_argument("--campaign", type=int, required=True,
                    help="the Ads account's campaign number")
    ad.add_argument("--variant", default="", help="the ad-group slug")
    ad.add_argument("--to", required=True,
                    help="site path or full URL the ad lands on")
    ad.add_argument("--product", default=F.AD_PRODUCT_PERSONAL,
                    choices=sorted(F.AD_PRODUCTS),
                    help="what the ad sells (default: personal)")

    post = sub.add_parser("post", help="a hand-written post about one episode")
    post.add_argument("--show", required=True, help="show slug (shows/<slug>.yaml)")
    post.add_argument("--episode", type=int, required=True)
    post.add_argument("--source", default=F.SOURCE_X, choices=sorted(F.SOURCES),
                      help="where the link is placed (default: x)")
    post.add_argument("--to", default="",
                      help="site path or URL; default: the show's funnel destination")
    post.add_argument("--surface", default="",
                      help="optional variant (which plug / surface this is)")
    post.add_argument("--placement", default=F.PLACEMENT_BODY,
                      choices=sorted(F.PLACEMENTS))

    parse = sub.add_parser("parse", help="read a URL the way the funnel does")
    parse.add_argument("url")

    args = parser.parse_args(argv)
    if args.command == "ad":
        print(ad_url(args.campaign, args.variant, args.to, args.product))
        return 0
    if args.command == "post":
        print(post_url(args.show, args.episode, args.source, args.to,
                       args.surface, args.placement))
        return 0
    campaign = parse_url(args.url)
    if campaign is None:
        print("not a Nerra campaign: this URL would land in `unattributed`")
        return 1
    for key, value in campaign.as_dict().items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
