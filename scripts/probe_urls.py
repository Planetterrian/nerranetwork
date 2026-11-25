#!/usr/bin/env python3
"""Fetch a list of URLs from a GitHub runner and print what each answers.

Nov 25 2026. A feed that is dead from the runners' addresses (Reddit's 429,
a government site's renamed path) cannot be diagnosed or replaced from a
development machine whose network differs: a candidate URL has to be read
from where the shows read it. ``data/probe_urls.txt`` lists one URL a line,
optionally followed by a regular expression; the "Probe URLs" workflow runs
this on any pull request that changes that file and prints, per URL:

* the status, content type and size;
* for a feed: the entry count, the newest entry's date and three titles;
* for a page: the RSS/Atom ``<link rel="alternate">`` addresses it declares
  and up to ``MAX_MATCHES`` matches of the line's regular expression.

It reads public pages with the fetcher's own headers, needs no secret and
writes nothing.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

DEFAULT_LIST = _ROOT / "data" / "probe_urls.txt"
MAX_MATCHES = 40
MATCH_CHARS = 300
TIMEOUT_S = 25
_ALT_RE = re.compile(
    r"<link[^>]+type=[\"']application/(?:rss|atom)\+xml[\"'][^>]*>", re.I)
_HREF_RE = re.compile(r"href=[\"']([^\"']+)[\"']", re.I)


def read_list(path: Path) -> List[Tuple[str, Optional[str]]]:
    rows: List[Tuple[str, Optional[str]]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        url, _, pattern = line.partition(" ")
        rows.append((url, pattern.strip() or None))
    return rows


def describe(url: str, status: int, ctype: str, body: bytes, pattern: Optional[str]) -> List[str]:
    """The printed lines for one answered URL (pure: no network)."""
    import feedparser

    lines = [f"{status}  {ctype or '?'}  {len(body)} bytes"]
    text = body.decode("utf-8", errors="replace")
    feed = feedparser.parse(body) if body else None
    if feed is not None and feed.entries:
        dates = []
        for e in feed.entries:
            t = e.get("published_parsed") or e.get("updated_parsed")
            if t:
                dates.append(time.strftime("%Y-%m-%d", t))
        lines.append(f"feed: {len(feed.entries)} entries, newest {max(dates) if dates else 'undated'}")
        for e in feed.entries[:3]:
            lines.append("  - " + str(e.get("title", "")).strip()[:120])
    else:
        alts = [m.group(1) for tag in _ALT_RE.findall(text) for m in [_HREF_RE.search(tag)] if m]
        for href in alts[:10]:
            lines.append(f"declares feed: {href}")
    if pattern:
        try:
            found = re.findall(pattern, text, flags=re.S)
        except re.error as exc:
            lines.append(f"bad pattern ({exc})")
            found = []
        seen = []
        for m in found:
            s = m if isinstance(m, str) else " | ".join(m)
            s = re.sub(r"\s+", " ", s).strip()[:MATCH_CHARS]
            if s and s not in seen:
                seen.append(s)
            if len(seen) >= MAX_MATCHES:
                break
        lines.append(f"pattern matches: {len(found)}")
        lines.extend("  > " + s for s in seen)
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", default=str(DEFAULT_LIST))
    args = parser.parse_args(argv)

    import requests
    from engine.fetcher import _headers_for_url

    rows = read_list(Path(args.list))
    for i, (url, pattern) in enumerate(rows):
        print(f"\n=== {url}")
        try:
            resp = requests.get(url, headers=_headers_for_url(url), timeout=TIMEOUT_S)
            for line in describe(url, resp.status_code, resp.headers.get("content-type", ""),
                                 resp.content, pattern):
                print(line)
            if resp.history:
                print(f"redirected to: {resp.url}")
        except Exception as exc:  # noqa: BLE001 - a probe reports, it never fails
            print(f"ERROR {type(exc).__name__}: {str(exc)[:200]}")
        if i + 1 < len(rows):
            time.sleep(1.5)
    print(f"\nProbed {len(rows)} URL(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
