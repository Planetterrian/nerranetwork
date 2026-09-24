#!/usr/bin/env python3
"""Re-source published digest citations that credit x.com to the article
the post actually linked (launch-cohort follow-up, Sep 23 2026).

Before ``fetch_x_posts`` learned to carry the outbound link (PR #1286), a
newsroom's own post about its own article was credited as ``x.com`` — Omni
View Africa & Middle East Ep1 shipped 6 of 6 items that way (BBC Africa,
Al Jazeera, Arab News). The pipeline is fixed forward; this repairs the
committed record.

For every ``Source: [x.com](https://x.com/<handle>/status/<id>)`` line in a
digest the script resolves the post through X's public syndication endpoint
(no API key), follows the post's first outbound short link to the publisher
URL, strips tracking parameters, and rewrites the line to
``Source: [<domain>](<url>)`` — the shape ``engine.blog`` already renders.
The same substitution is written into the ``content`` field of the show's
``summaries_<slug>.json`` entry. A post with no outbound link is left as it
is and listed.

It never touches ``_tts.txt``, transcripts, ``_claims.json`` (the gate's
record of what was verified at publish time), RSS or audio. **Dry run by
default** — pass ``--apply`` to write, then regenerate the blog posts with
``python generate_html.py --show <slug> --blogs`` for each touched show.

Usage::

    python scripts/resource_x_citations.py                 # the launch cohort, dry run
    python scripts/resource_x_citations.py omni_view_africa_mideast --apply
    python scripts/resource_x_citations.py vancouver --episode 1 --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.url_utils import sanitize_url  # noqa: E402

logger = logging.getLogger("resource_x_citations")

#: The 13 shows launched 2026-09-22/23.
COHORT = (
    "ai_chips", "mag7", "peptides", "longevity", "prediction_markets",
    "vancouver", "collingwood", "omni_view_europe", "omni_view_asia_pacific",
    "omni_view_africa_mideast", "omni_view_latam", "omni_view_north_america",
    "omni_view_world",
)

X_SOURCE_RE = re.compile(
    r"Source: \[x\.com\]\((https?://(?:www\.)?(?:x|twitter)\.com/[^/\s)]+/status/(\d+)[^)\s]*)\)"
)
SYNDICATION_URL = "https://cdn.syndication.twimg.com/tweet-result?id={id}&token=a"
_SELF_HOSTS = ("x.com", "twitter.com", "t.co")
_TRACKING_PREFIXES = ("utm_", "at_")
_TRACKING_KEYS = {"ito", "ref", "ref_src", "ref_url", "cmpid", "dgcid", "ns_mchannel",
                  "ns_source", "ns_campaign", "ns_linkname", "ns_fee", "s", "fbclid", "gclid"}
#: A resolved link that lands on a listing rather than an article is not a
#: citation (Arab News's Gaza post resolved to backup.arabnews.com/tags/gaza-war).
_LISTING_PATH_RE = re.compile(r"/(?:tags?|topics?|category|categories|search)(?:/|$)", re.I)
_LISTING_HOST_PREFIXES = ("backup.",)
USER_AGENT = "Mozilla/5.0 (compatible; NerraNetwork/1.0; +https://nerranetwork.com)"


def strip_tracking(url: str) -> str:
    """Drop utm_* / at_* / known tracking query keys; keep everything else."""
    try:
        parts = urlparse(url)
    except Exception:  # noqa: BLE001
        return url
    kept = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(_TRACKING_PREFIXES) and k.lower() not in _TRACKING_KEYS
    ]
    return urlunparse(parts._replace(query=urlencode(kept), fragment=""))


def _host(url: str) -> str:
    host = (urlparse(url).netloc or "").lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def is_listing_page(url: str) -> bool:
    """True for a tag / topic / search page or a mirror host — never a citation."""
    try:
        parts = urlparse(url)
    except Exception:  # noqa: BLE001
        return True
    host = (parts.netloc or "").lower()
    if any(host.startswith(pfx) for pfx in _LISTING_HOST_PREFIXES):
        return True
    return bool(_LISTING_PATH_RE.search(parts.path or ""))


def outbound_links_from_payload(payload: dict) -> List[str]:
    """The post's outbound URLs from a syndication payload, x.com links excluded."""
    out: List[str] = []
    for ent in (payload.get("entities") or {}).get("urls") or []:
        u = (ent or {}).get("expanded_url") or (ent or {}).get("url") or ""
        if u and _host(u) not in _SELF_HOSTS and u not in out:
            out.append(u)
    card = (payload.get("card") or {}).get("url")
    if card and _host(card) not in _SELF_HOSTS and card not in out:
        out.append(card)
    return out


def fetch_post_payload(status_id: str, timeout: float = 20.0) -> Optional[dict]:
    import requests

    try:
        r = requests.get(SYNDICATION_URL.format(id=status_id), timeout=timeout,
                         headers={"User-Agent": USER_AGENT})
        if r.status_code != 200 or not r.text.strip():
            logger.warning("syndication %s -> HTTP %s", status_id, r.status_code)
            return None
        return r.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("syndication %s failed: %s", status_id, exc)
        return None


def follow_redirects(url: str, timeout: float = 20.0) -> str:
    """Resolve a short link to its final URL; the input on any failure."""
    import requests

    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout,
                          headers={"User-Agent": USER_AGENT})
        final = r.url or url
        if r.status_code >= 400:
            r = requests.get(url, allow_redirects=True, timeout=timeout, stream=True,
                             headers={"User-Agent": USER_AGENT})
            final = r.url or final
            r.close()
        return final
    except Exception as exc:  # noqa: BLE001
        logger.warning("redirect follow failed for %s: %s", url, exc)
        return url


def resolve_post(status_id: str) -> Optional[str]:
    """The publisher URL a post links, tracking stripped; None when it links nothing."""
    payload = fetch_post_payload(status_id)
    if not payload:
        return None
    for link in outbound_links_from_payload(payload):
        final = strip_tracking(follow_redirects(link))
        if _host(final) in _SELF_HOSTS or is_listing_page(final):
            logger.info("post %s links %s — not an article, left as is", status_id, final)
            continue
        clean = sanitize_url(final) or final
        return clean
    return None


def rewrite_text(text: str, resolved: Dict[str, str]) -> Tuple[str, int]:
    """Replace every x.com Source whose status id is in *resolved*. Returns (text, n)."""
    n = 0

    def _sub(m: re.Match) -> str:
        nonlocal n
        url = resolved.get(m.group(2))
        if not url:
            return m.group(0)
        n += 1
        return f"Source: [{_host(url)}]({url})"

    return X_SOURCE_RE.sub(_sub, text), n


def digest_paths(slug: str, episode: Optional[int]) -> List[Path]:
    d = ROOT / "digests" / slug
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*_Ep*.md")):
        if "_reader" in p.name:
            continue
        if episode is not None:
            m = re.search(r"_Ep(\d+)_", p.name)
            if not m or int(m.group(1)) != episode:
                continue
        out.append(p)
    return out


def _episode_of(path: Path) -> Optional[int]:
    m = re.search(r"_Ep(\d+)_", path.name)
    return int(m.group(1)) if m else None


def _summaries_path(slug: str) -> Optional[Path]:
    d = ROOT / "digests" / slug
    hits = sorted(d.glob("summaries_*.json"))
    return hits[0] if hits else None


def process_show(slug: str, episode: Optional[int], apply: bool,
                 resolver=resolve_post) -> List[dict]:
    rows: List[dict] = []
    touched_summaries = False
    summ_path = _summaries_path(slug)
    summ = json.loads(summ_path.read_text(encoding="utf-8")) if summ_path else None

    for path in digest_paths(slug, episode):
        text = path.read_text(encoding="utf-8")
        ids = [m.group(2) for m in X_SOURCE_RE.finditer(text)]
        if not ids:
            continue
        resolved: Dict[str, str] = {}
        for sid in dict.fromkeys(ids):
            url = resolver(sid)
            rows.append({"show": slug, "file": path.name, "status_id": sid,
                         "resolved": url or "", "ok": bool(url)})
            if url:
                resolved[sid] = url
        new_text, n = rewrite_text(text, resolved)
        if n and apply:
            path.write_text(new_text, encoding="utf-8")
            ep = _episode_of(path)
            if summ and ep is not None:
                entries = summ.get("summaries") if isinstance(summ, dict) else summ
                for e in entries or []:
                    if isinstance(e, dict) and int(e.get("episode_num") or -1) == ep and e.get("content"):
                        e["content"], _ = rewrite_text(e["content"], resolved)
                        touched_summaries = True
    if apply and touched_summaries and summ_path:
        summ_path.write_text(json.dumps(summ, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rows


def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shows", nargs="*", help="show slugs (default: the 13-show launch cohort)")
    ap.add_argument("--episode", type=int, default=None, help="only this episode number")
    ap.add_argument("--apply", action="store_true", help="write the digests and summaries (default: dry run)")
    args = ap.parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)

    shows = args.shows or list(COHORT)
    all_rows: List[dict] = []
    for slug in shows:
        all_rows.extend(process_show(slug, args.episode, args.apply))

    if not all_rows:
        print("No x.com Source lines found.")
        return 0
    width = max(len(r["file"]) for r in all_rows)
    for r in all_rows:
        flag = "OK " if r["ok"] else "-- "
        print(f"{flag}{r['show']:26} {r['file']:{width}} {r['status_id']} -> {r['resolved'] or '(no outbound link; left as is)'}")
    ok = sum(1 for r in all_rows if r["ok"])
    mode = "APPLIED" if args.apply else "DRY RUN (pass --apply to write)"
    print(f"\n{ok}/{len(all_rows)} resolved — {mode}")
    if args.apply and ok:
        touched = sorted({r["show"] for r in all_rows if r["ok"]})
        print("Now regenerate the posts: " + "; ".join(f"python generate_html.py --show {s} --blogs" for s in touched))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
