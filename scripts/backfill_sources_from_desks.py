#!/usr/bin/env python3
"""Backfill ``Source:`` lines on a Top World digest from the desks' digests.

Sep 24 2026: Omni View Top World News Ep2 shipped with NO Source line at all
— the grok-4.3 structural retry that replaced its grok-4.7 digest wrote
eleven items and cited nothing, the blog page's Sources list was empty, and
the launch-cohort guard went red on main. Every one of those items is a
desk story from the same day, and the desks' committed digests carry the
publisher URL the hook handed Top World in the first place — so the record
can be repaired from the record, never from memory.

For each headline item without a Source line, the script finds the same
story among two committed records of that day — the five desks' digests
(their items carry ``Source:`` lines) and the show's OWN content tracker
(``<slug>_content_tracker.json`` stores the headline and URL of every
article the run fetched) — by normalised title (exact match first, then the
best token overlap at or above ``MIN_OVERLAP``) and appends that article's
``Source: [domain](url)`` line. Items with no confident match are left alone
and listed. Nothing is ever looked up on the network or supplied from
memory: a Source line here is one the pipeline held on the day. **Dry run by default** — pass
``--apply`` to write the digest and the ``summaries_<slug>.json`` entry, then
regenerate the post with ``python generate_html.py --show <slug> --blogs``.

    python scripts/backfill_sources_from_desks.py --episode 2
    python scripts/backfill_sources_from_desks.py --episode 2 --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.resource_x_citations import strip_tracking  # noqa: E402 — drops at_*/utm_* params

DESKS = ["omni_view_europe", "omni_view_asia_pacific", "omni_view_africa_mideast",
         "omni_view_latam", "omni_view_north_america"]
MIN_OVERLAP = 0.5

# A full-line bold headline, optionally numbered inside the bold ("**1. Title: Outlet**").
HEADLINE_RE = re.compile(r"^\*\*(?:\d+\.\s*)?(.+?)\*\*\s*$")
SOURCE_RE = re.compile(r"Source:\s*\[([^\]]+)\]\((https?://[^)\s]+)\)")
_STOP = {"the", "a", "an", "of", "in", "on", "to", "for", "as", "and", "at", "by", "with",
         "from", "its", "it", "is", "says", "say", "after", "over", "lead"}


def _host(url: str) -> str:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def split_title(headline: str) -> Tuple[str, str]:
    """'Title: Outlet' -> (title, outlet); a headline with no outlet tail keeps it all."""
    head = headline.strip()
    if ": " in head:
        title, outlet = head.rsplit(": ", 1)
        if 0 < len(outlet) <= 40:
            return title.strip(), outlet.strip()
    return head, ""


def norm_tokens(title: str) -> frozenset:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return frozenset(w for w in words if w not in _STOP and len(w) > 1)


def parse_items(text: str) -> List[dict]:
    """Every headline item: title, outlet, body line indexes and its Source url if any."""
    lines = text.split("\n")
    items: List[dict] = []
    i = 0
    while i < len(lines):
        m = HEADLINE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        title, outlet = split_title(m.group(1))
        j = i + 1
        body_idx: List[int] = []
        while j < len(lines) and lines[j].strip() and not HEADLINE_RE.match(lines[j]) \
                and not lines[j].startswith("#"):
            body_idx.append(j)
            j += 1
        body = "\n".join(lines[k] for k in body_idx)
        sm = SOURCE_RE.search(body)
        items.append({"title": title, "outlet": outlet, "headline_idx": i, "body": body,
                      "body_idx": body_idx, "url": sm.group(2) if sm else ""})
        i = j
    return items


def desk_candidates(date_yyyymmdd: str, root: Path = ROOT) -> List[dict]:
    out: List[dict] = []
    for slug in DESKS:
        for p in sorted((root / "digests" / slug).glob(f"*_{date_yyyymmdd}.md")):
            if "_reader" in p.name:
                continue
            for it in parse_items(p.read_text(encoding="utf-8")):
                if it["url"]:
                    out.append({"title": it["title"], "outlet": it["outlet"], "host": _host(it["url"]),
                                "url": it["url"], "desk": slug})
    return out


_SLUG_STOP = {"news", "articles", "article", "world", "live", "video", "en", "story", "politics",
              "view", "stories", "html", "rss",
              "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}


def slug_title(url: str) -> str:
    """The words a publisher put in the URL path — the article's own headline
    for most publishers (france24, the Guardian, bgov, O Globo); empty for an
    id-only path (BBC, AllAfrica, Yonhap), which needs ``resolve_title``."""
    from urllib.parse import urlparse
    path = urlparse(url).path
    words = [w for w in re.split(r"[/\-_.]+", path) if w and not w.isdigit()
             and not re.fullmatch(r"\d{6,}|[a-z]{1,2}\d+[a-z0-9]*|[a-z0-9]{12,14}", w)]
    words = [w for w in words if w.lower() not in _SLUG_STOP]
    return " ".join(words)


def resolve_title(url: str, timeout: float = 20.0) -> str:
    """Read an id-only URL's headline from its page (og:title / <title>).
    Network, opt-in (``--resolve``); a failure returns '' and the item stays
    unsourced rather than guessed."""
    try:
        import requests
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (compatible; NerraBot/1.0)"})
        if r.status_code != 200:
            return ""
        m = re.search(r'property="og:title"\s+content="([^"]+)"', r.text) or \
            re.search(r"<title>([^<]+)</title>", r.text)
        return re.sub(r"\s*[-|–]\s*(BBC News|BBC|Yonhap News Agency|allAfrica\.com)\s*$", "", m.group(1)).strip() if m else ""
    except Exception:  # noqa: BLE001 — a network failure is "unknown", never a match
        return ""


def tracker_candidates(slug: str, date_yyyymmdd: str, root: Path = ROOT,
                       resolve: bool = False) -> List[dict]:
    """The run's own fetch record: every article URL the ContentTracker
    stored for that date. The tracker's ``headlines`` are the DIGEST's
    headlines and its ``urls`` the fetched articles — two lists that are not
    index-aligned — so the title comes from the URL's own slug, or from the
    page when ``resolve`` is on and the path is id-only."""
    path = root / "digests" / slug / f"{slug}_content_tracker.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    iso = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:]}"
    out: List[dict] = []
    seen: set = set()
    for ep in data.get("episodes") or []:
        if not isinstance(ep, dict) or str(ep.get("date")) != iso:
            continue
        for url in ep.get("urls") or []:
            if not (isinstance(url, str) and url.startswith("http")) or url in seen:
                continue
            seen.add(url)
            title = slug_title(url)
            if len(norm_tokens(title)) < 3 and resolve:
                title = resolve_title(url) or title
            out.append({"title": title, "outlet": "", "host": _host(url), "url": url,
                        "desk": f"{slug} tracker"})
    return out


def outlet_fits_host(outlet: str, host: str) -> bool:
    """'BBC World' fits bbc.co.uk; 'The Guardian World' fits theguardian.com;
    'Bloomberg Government News' fits news.bgov.com. An item that names an
    outlet is never sourced to another publisher's page."""
    if not outlet or not host:
        return True
    words = [w for w in re.findall(r"[a-z0-9]+", outlet.lower())
             if w not in {"the", "news", "world", "media", "government", "global", "daily", "agency"}]
    h = host.replace("-", "").replace(".", " ")
    for w in words:
        if w in h or (w == "bloomberg" and "bgov" in h) or (w == "yonhap" and "yna" in h) \
                or (w == "globo" and "globo" in h):
            return True
    return False


MIN_SHARED_TOKENS = 3


def best_match(title: str, outlet: str, candidates: Iterable[dict], body: str = "") -> Optional[dict]:
    """Exact normalised title first; then the candidate whose title (or URL
    slug) shares the most words with the item — at least MIN_SHARED_TOKENS,
    covering at least MIN_OVERLAP of the shorter of the two titles, or of
    the candidate's title against the item's title AND body (a publisher
    re-headlines a live story; the facts in the body do not move) — among
    the candidates whose publisher fits the outlet the item names. Two
    candidates scoring alike is 'no confident match'."""
    want = norm_tokens(title)
    if not want:
        return None
    want_all = want | norm_tokens(body)
    pool = [c for c in candidates
            if outlet_fits_host(outlet, c.get("host") or _host(c["url"]))]
    exact = [c for c in pool if norm_tokens(c["title"]) == want]
    if exact:
        return exact[0]
    scored = []
    for c in pool:
        have = norm_tokens(c["title"])
        shared = len(want & have)
        shared_all = len(want_all & have)
        if max(shared, shared_all) < MIN_SHARED_TOKENS:
            continue
        score = max(shared / max(1, min(len(want), len(have))),
                    shared_all / max(1, len(have)) if have else 0.0)
        scored.append((score, shared_all, c))
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    if not scored or scored[0][0] < MIN_OVERLAP:
        return None
    if len(scored) > 1 and scored[1][0] == scored[0][0] and scored[1][2]["url"] != scored[0][2]["url"]:
        return None
    return scored[0][2]


def backfill(text: str, candidates: List[dict]) -> Tuple[str, List[dict]]:
    """Return (new_text, rows). A row per source-less item: matched url or ''."""
    lines = text.split("\n")
    rows: List[dict] = []
    # Walk from the bottom so inserted lines never shift earlier indexes.
    for it in reversed(parse_items(text)):
        if it["url"] or not it["body_idx"]:
            continue
        if it["title"].lower().startswith(("both sides", "progress watch")):
            continue  # analysis beats, not story items
        hit = best_match(it["title"], it["outlet"], candidates, body=it.get("body", ""))
        rows.append({"title": it["title"], "outlet": it["outlet"],
                     "url": hit["url"] if hit else "", "desk": hit["desk"] if hit else ""})
        if hit:
            last = it["body_idx"][-1]
            url = strip_tracking(hit["url"])
            lines[last] = lines[last].rstrip() + f" Source: [{_host(url)}]({url})"
    rows.reverse()
    return "\n".join(lines), rows


def _digest_path(slug: str, episode: int, root: Path) -> Optional[Path]:
    hits = [p for p in sorted((root / "digests" / slug).glob(f"*_Ep{episode:03d}_*.md"))
            if "_reader" not in p.name]
    return hits[-1] if hits else None


def process(slug: str, episode: int, apply: bool, root: Path = ROOT,
            resolve: bool = False) -> List[dict]:
    path = _digest_path(slug, episode, root)
    if path is None:
        raise SystemExit(f"no digest for {slug} episode {episode}")
    date = re.search(r"_(\d{8})\.md$", path.name).group(1)
    candidates = desk_candidates(date, root) + tracker_candidates(slug, date, root, resolve=resolve)
    text = path.read_text(encoding="utf-8")
    new_text, rows = backfill(text, candidates)
    added = sum(1 for r in rows if r["url"])
    print(f"{path.name}: {len(candidates)} desk + tracker items dated {date}; "
          f"{len(rows)} source-less item(s), {added} matched")
    for r in rows:
        print(f"  {'OK ' if r['url'] else '-- '} {r['title'][:70]!r:74} -> {r['url'] or '(no confident match)'}")
    if apply and added:
        path.write_text(new_text, encoding="utf-8")
        summ_hits = sorted((root / "digests" / slug).glob("summaries_*.json"))
        if summ_hits:
            summ = json.loads(summ_hits[0].read_text(encoding="utf-8"))
            entries = summ.get("summaries") if isinstance(summ, dict) else summ
            for e in entries or []:
                if isinstance(e, dict) and int(e.get("episode_num") or -1) == episode and e.get("content"):
                    e["content"], _ = backfill(e["content"], candidates)
            summ_hits[0].write_text(json.dumps(summ, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
        print(f"APPLIED — now: python generate_html.py --show {slug} --blogs")
    elif not apply:
        print("DRY RUN (pass --apply to write)")
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--show", default="omni_view_world")
    ap.add_argument("--episode", type=int, required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--resolve", action="store_true",
                    help="fetch the headline of id-only URLs (BBC, AllAfrica, Yonhap) from the page")
    args = ap.parse_args(argv)
    process(args.show, args.episode, args.apply, resolve=args.resolve)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
