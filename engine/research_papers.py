"""Economics and computer-science abstracts as hook articles (Sep 2026).

Prediction Markets Daily's How It Works segment (docs/new_shows_plan_2026_09_22.md
§4.11) explains one mechanism a day from a curriculum — information
aggregation, calibration, market making, manipulation, resolution, futarchy,
the law. Written from memory, every figure and every named study in it would
be stripped by the claims gate, correctly. This module is the health shows'
Europe PMC pattern (engine/europe_pmc.py) for a field Europe PMC does not
index: real abstracts become hook ARTICLES, so the explainer can cite a paper
whose text the pipeline already holds (verification ``via: fetched_copy``).

Two free, keyless indexes, probed 2026-09-23:

* **Crossref** (``api.crossref.org/works``) — the journal literature
  (Journal of Economic Perspectives, Management Science, The Journal of
  Prediction Markets). Its citation sort is useless for a subject query —
  "prediction markets" sorted by citations returns AlphaFold and the Kalman
  filter — so results come back in relevance order and a TITLE check keeps
  only papers about the subject; the survivors are then ranked by citations.
* **arXiv** (``export.arxiv.org/api/query``) — mechanism design, scoring
  rules and market-maker papers, in relevance order. OpenAlex and Semantic
  Scholar answered HTTP 429 to this session and are not used.

Best-effort: any failure is an empty list and a log line.
"""

from __future__ import annotations

import html
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

USER_AGENT = "NerraNetwork/1.0 (podcast research; mailto:patrick@planetterrian.com)"
TIMEOUT_S = 20

CROSSREF_URL = "https://api.crossref.org/works"
ARXIV_URL = "https://export.arxiv.org/api/query"

#: Abstracts shorter than this carry no mechanism worth citing.
MIN_ABSTRACT_CHARS = 250
#: Journal papers kept per subject (highest-cited first), then arXiv papers.
MAX_CROSSREF, MAX_ARXIV = 4, 2
#: Crossref rows read before the title check; most are off-subject.
CROSSREF_ROWS = 40

_TAG_RE = re.compile(r"<[^>]+>")
_ATOM = "{http://www.w3.org/2005/Atom}"

#: ``get(url, params) -> response`` with ``.status_code``, ``.json()`` and
#: ``.text`` (a requests.Response). Injectable for tests.
Get = Callable[[str, Dict[str, str]], Any]


def _get(url: str, params: Dict[str, str]) -> Any:
    import requests

    return requests.get(url, params=params, timeout=TIMEOUT_S,
                        headers={"User-Agent": USER_AGENT})


def _clean(text: Any) -> str:
    text = html.unescape(_TAG_RE.sub(" ", str(text or "")))
    text = re.sub(r"^\s*(abstract|summary)\s*[:.]?\s*", "", text.strip(), flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def _title_ok(title: str, require: Sequence[str], exclude: Sequence[str]) -> bool:
    """Every ``require`` element must match; an element matches when any of
    its ``|``-separated alternatives is in the title (``"futarch|decision
    market"``). Any ``exclude`` term disqualifies."""
    low = title.lower()
    for element in require:
        alternatives = [a.strip().lower() for a in str(element).split("|") if a.strip()]
        if alternatives and not any(a in low for a in alternatives):
            return False
    return not any(term.lower() in low for term in exclude)


def crossref_abstracts(query: str, *, require: Sequence[str] = (),
                       exclude: Sequence[str] = (), keep: int = MAX_CROSSREF,
                       get: Get = _get) -> List[Dict[str, Any]]:
    if not query:
        return []
    try:
        resp = get(CROSSREF_URL, {
            "query.title": query,
            "filter": "has-abstract:true,type:journal-article",
            "rows": str(CROSSREF_ROWS),
            "select": "DOI,title,abstract,container-title,issued,is-referenced-by-count",
        })
        if resp.status_code != 200:
            logger.info("Crossref HTTP %s for %r", resp.status_code, query)
            return []
        items = (resp.json().get("message") or {}).get("items") or []
    except Exception as exc:  # noqa: BLE001 — research never blocks an episode
        logger.info("Crossref query failed for %r: %s", query, exc)
        return []
    rows = []
    for it in items:
        title = _clean((it.get("title") or [""])[0]).rstrip(".")
        abstract = _clean(it.get("abstract"))
        doi = str(it.get("DOI") or "").strip()
        if not title or not doi or len(abstract) < MIN_ABSTRACT_CHARS:
            continue
        if not _title_ok(title, require, exclude):
            continue
        journal = _clean((it.get("container-title") or [""])[0])
        year = ""
        parts = ((it.get("issued") or {}).get("date-parts") or [[None]])[0]
        if parts and parts[0]:
            year = str(parts[0])
        rows.append((int(it.get("is-referenced-by-count") or 0), {
            "title": title,
            "url": f"https://doi.org/{doi}",
            "description": abstract[:600],
            "content_text": abstract,
            "source_name": f"{journal} ({year})" if journal else f"Crossref ({year})",
            "published_date": f"{year}-01-01" if year else "",
            # A 2004 survey is evidence, not stale news.
            "exempt_stale": True,
        }))
    rows.sort(key=lambda r: -r[0])
    return [art for _cites, art in rows[:keep]]


def arxiv_abstracts(query: str, *, require: Sequence[str] = (),
                    exclude: Sequence[str] = (), keep: int = MAX_ARXIV,
                    get: Get = _get) -> List[Dict[str, Any]]:
    if not query:
        return []
    try:
        resp = get(ARXIV_URL, {"search_query": query, "sortBy": "relevance",
                               "max_results": str(max(keep * 4, 8))})
        if resp.status_code != 200:
            logger.info("arXiv HTTP %s for %r", resp.status_code, query)
            return []
        root = ET.fromstring(resp.text)
    except Exception as exc:  # noqa: BLE001
        logger.info("arXiv query failed for %r: %s", query, exc)
        return []
    out: List[Dict[str, Any]] = []
    for entry in root.findall(f"{_ATOM}entry"):
        title = _clean(entry.findtext(f"{_ATOM}title")).rstrip(".")
        abstract = _clean(entry.findtext(f"{_ATOM}summary"))
        url = (entry.findtext(f"{_ATOM}id") or "").strip().replace("http://", "https://")
        published = (entry.findtext(f"{_ATOM}published") or "")[:10]
        if not title or not url or len(abstract) < MIN_ABSTRACT_CHARS:
            continue
        if not _title_ok(title, require, exclude):
            continue
        out.append({
            "title": title,
            "url": url,
            "description": abstract[:600],
            "content_text": abstract,
            "source_name": f"arXiv ({published[:4]})" if published else "arXiv",
            "published_date": published,
            "exempt_stale": True,
        })
        if len(out) >= keep:
            break
    return out


def papers_for(topic: Optional[Dict[str, Any]], *, get: Get = _get) -> List[Dict[str, Any]]:
    """Journal then arXiv abstracts for one curriculum entry, de-duplicated.

    The entry carries ``search`` (a Crossref title query), optional
    ``arxiv`` (an arXiv ``search_query``), ``require`` (words every kept
    title must contain) and ``exclude`` (words that disqualify a title).
    """
    if not topic:
        return []
    require = [str(t) for t in topic.get("require") or []]
    exclude = [str(t) for t in topic.get("exclude") or []]
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    batches = (
        crossref_abstracts(str(topic.get("search") or ""), require=require,
                           exclude=exclude, get=get),
        arxiv_abstracts(str(topic.get("arxiv") or ""), require=require,
                        exclude=exclude, get=get),
    )
    for batch in batches:
        for art in batch:
            if art["url"] not in seen:
                seen.add(art["url"])
                out.append(art)
    return out
