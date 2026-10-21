"""Dossiers from the content lake: what the network aired about a story or a
subject, with sources and verified claims (Oct 21 2026).

Shared by ``scripts/catalog_dossier.py`` (books, story pages, research) and
the members-only specials producer (``prior_coverage.md`` beside each
episode's dossier — orientation for the operator, never a source).
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional

_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_SOURCE_RE = re.compile(r"^\s*Source:.*$", re.MULTILINE)


def _plain(body: str) -> str:
    text = _SOURCE_RE.sub("", body or "")
    text = _LINK_RE.sub(r"\1", text).replace("**", "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def find_story(text: str, *, db_path=None) -> Optional[str]:
    """The story id whose items best match *text* (salient-token matching,
    over the whole lake)."""
    from engine import content_lake
    from engine.story_catalog import item_tokens

    kwargs = {"db_path": db_path} if db_path else {}
    probe = item_tokens(text)
    best = None
    for it in content_lake.query_items("2000-01-01", "2999-12-31", **kwargs):
        if not it.get("story_id") or it.get("kind") == "essay":
            continue
        ov = len(probe & set(it.get("tokens") or []))
        if ov >= 2 and (best is None or (ov, it["date"]) > best[:2]):
            best = (ov, it["date"], it["story_id"])
    return best[2] if best else None


def _claims_for(item: dict, cache: Dict[str, list], dirs: Dict[str, Path]) -> List[dict]:
    from engine.catalog import _ledger_for

    key = f"{item['show_slug']}:{item['episode_num']}"
    if key not in cache:
        cache[key] = []
        d = dirs.get(item["show_slug"])
        ledger = _ledger_for(d, item["episode_num"], item["date"]) if d else None
        if ledger:
            try:
                data = json.loads(ledger.read_text(encoding="utf-8"))
                cache[key] = [c for c in (data.get("claims") or [])
                              if str(c.get("status") or "verified").startswith("verified")]
            except (OSError, ValueError):
                pass
    from engine.story_recurrence import salient_tokens

    urls = set(item.get("urls") or [])
    # A roundup page backs several stories (SpaceX's daily brief): a claim
    # belongs to this item only when it also shares words with it.
    words = salient_tokens(f"{item.get('title') or ''} {item.get('body') or ''}")
    return [c for c in cache[key] if c.get("source_url") in urls
            and len(salient_tokens(c.get("claim") or "") & words) >= 3]


def build(items: List[dict], *, heading: str) -> dict:
    from engine.catalog import _show_dirs

    dirs = _show_dirs()
    cache: Dict[str, list] = {}
    stories: "OrderedDict[str, list]" = OrderedDict()
    for it in sorted(items, key=lambda i: (i["date"], i["show_slug"], i["position"])):
        stories.setdefault(it.get("story_id") or it["item_key"], []).append({
            "date": it["date"], "show": it.get("show_name") or it["show_slug"],
            "show_slug": it["show_slug"], "episode": it["episode_num"],
            "title": it["title"], "text": _plain(it.get("body") or ""),
            "sources": it.get("urls") or [],
            "verified_claims": [
                {"claim": c.get("claim"), "source_url": c.get("source_url"),
                 "quote": c.get("supporting_quote")}
                for c in _claims_for(it, cache, dirs)],
        })
    return {"heading": heading,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "stories": [{"story_id": sid, "items": members} for sid, members in stories.items()]}


def to_markdown(d: dict) -> str:
    out = [f"# {d['heading']}", "",
           f"_Exported {d['generated_at']} from the Nerra Network content lake. "
           "Every item below aired; sources are the item's own links and the "
           "claims are the episode ledger's verified entries for those links._", ""]
    for s in d["stories"]:
        first = s["items"][0]
        out += [f"## {first['title']}", "", f"Story `{s['story_id']}` — "
                f"{len(s['items'])} telling(s), {first['date']} to {s['items'][-1]['date']}", ""]
        for it in s["items"]:
            out += [f"### {it['date']} — {it['show']} Ep{it['episode']}: {it['title']}", "",
                    it["text"], ""]
            if it["sources"]:
                out += ["Sources: " + ", ".join(it["sources"]), ""]
            for c in it["verified_claims"]:
                out += [f"- Verified: {c['claim']} — {c['source_url']}"]
            if it["verified_claims"]:
                out.append("")
    return "\n".join(out).rstrip() + "\n"




def prior_coverage_markdown(text: str, *, limit: int = 40, db_path=None) -> str:
    """A dossier of aired items matching *text* (full-text, any of its salient
    words), or ``""`` when the lake has none or cannot be read."""
    from engine import content_lake
    from engine.story_recurrence import salient_tokens

    words = sorted(salient_tokens(text))[:12]
    if not words:
        return ""
    query = " OR ".join(f'"{w}"' for w in words)
    kwargs = {"db_path": db_path} if db_path else {}
    try:
        items = content_lake.search_items(query, limit=limit, **kwargs)
    except Exception:  # noqa: BLE001 — orientation only
        return ""
    if not items:
        return ""
    return to_markdown(build(items, heading=f"What the network has already aired: {text[:80]}"))


__all__ = ["find_story", "build", "to_markdown", "prior_coverage_markdown"]
