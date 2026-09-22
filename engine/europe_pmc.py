"""Europe PMC abstracts as hook articles (Sep 2026, health weeklies).

The spotlight on Peptides Weekly / Longevity Weekly is an evidence story,
and the network's claims gate (engine/claims.py, enforce + strip) removes
every sentence it cannot trace to a source. A spotlight written from the
model's memory would therefore be stripped to nothing — correctly. This
module fetches real abstracts for the spotlight subject from the Europe PMC
REST API (free, no key, answers GitHub runners) and hands them to run_show
as hook articles (engine/hook_articles.py), so every claim can cite a paper
whose abstract the pipeline already holds (verification ``via:
fetched_copy``, no second HTTP call).

Two slices per subject: the most-cited papers (the landmark evidence) and
the most recent (what changed). Best-effort: any failure is an empty list.
"""

from __future__ import annotations

import logging
import re
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
TIMEOUT = 20
_TAG_RE = re.compile(r"<[^>]+>")


def _get(params: Dict[str, str]) -> Optional[dict]:
    import requests

    r = requests.get(API, params=params, timeout=TIMEOUT,
                     headers={"User-Agent": "NerraNetwork/1.0 (podcast research)"})
    if r.status_code != 200:
        logger.info("Europe PMC HTTP %s for %s", r.status_code, params.get("query"))
        return None
    return r.json()


def _article(rec: dict) -> Optional[dict]:
    abstract = _TAG_RE.sub(" ", str(rec.get("abstractText") or "")).strip()
    title = _TAG_RE.sub(" ", str(rec.get("title") or "")).strip().rstrip(".")
    if len(abstract) < 200 or not title:
        return None
    source = str(rec.get("source") or "MED")
    ident = str(rec.get("pmid") or rec.get("id") or "")
    if not ident:
        return None
    journal = str((rec.get("journalInfo") or {}).get("journal", {}).get("title")
                  or rec.get("journalTitle") or "").strip()
    year = str(rec.get("pubYear") or "")
    label = f"{journal} ({year})" if journal else f"Europe PMC ({year})"
    return {
        "title": title,
        "url": f"https://europepmc.org/article/{source}/{ident}",
        "description": abstract[:600],
        "content_text": abstract,
        "source_name": label,
        "published_date": str(rec.get("firstPublicationDate") or ""),
        # A 1997 landmark paper is evidence, not stale news.
        "exempt_stale": True,
    }


def abstracts_for(
    query: str,
    *,
    per_slice: int = 4,
    get: Callable[[Dict[str, str]], Optional[dict]] = _get,
) -> List[dict]:
    """Most-cited + most-recent abstracts for *query*, de-duplicated."""
    if not query:
        return []
    out: List[dict] = []
    seen: set[str] = set()
    # Europe PMC sort keys: CITED (citation count) and P_PDATE_D (publication
    # date) — "FIRST_PDATE" is rejected by the API.
    for sort in ("CITED desc", "P_PDATE_D desc"):
        try:
            data = get({"query": f"({query}) AND HAS_ABSTRACT:y", "format": "json",
                        "resultType": "core", "pageSize": str(per_slice), "sort": sort})
        except Exception as exc:  # noqa: BLE001 — research never blocks an episode
            logger.info("Europe PMC query failed (%s): %s", sort, exc)
            continue
        for rec in ((data or {}).get("resultList") or {}).get("result", []) or []:
            art = _article(rec)
            if art and art["url"] not in seen:
                seen.add(art["url"])
                out.append(art)
    return out
