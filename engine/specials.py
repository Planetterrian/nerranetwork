"""Members-only limited series: research, writing, checks and the catalog.

Oct 18 2026 (operator-directed). A limited series is a set of long, sourced
episodes on one subject, produced once, delivered to every paying Nerra
Personal member, and teased on the free surfaces of the shows it belongs to.
It does not run through ``run_show.py``: a daily show's deep-dive path is
single-episode, skips the digest lints, hands the claims gate no local texts
and is blocked by the per-date publish marker, so a series gets its own small
pipeline the way Nerra Daily and Nerra Voices have theirs.

* ``specials/series/<id>.yaml`` — the series (episodes, briefs, research
  questions, host show, teaser shows). Briefs are research instructions,
  never facts to repeat.
* ``scripts/produce_special.py`` — per episode: many web searches, only the
  pages actually fetched become sources (``min_sources`` or the episode does
  not produce); a sourced dossier with its claims ledger; the claims gate in
  flag mode (publish and mark, network policy since Oct 1 2026); the series'
  blocking lints (Peptides: no dose terms); a 25-35 minute script written
  only from the dossier; TTS in the host show's voice, the spoken-text gate,
  the host's music; upload to the PRIVATE bucket. Nothing public happens.
* ``scripts/release_special.py`` — after the operator has listened: marks the
  series released (every paying member's Personal feed carries it from the
  next builder run), puts the trailer in each teaser show's free feed, and
  posts the X teaser. The newsletters and the site read the released
  catalog.

``specials/catalog.json`` is the record every consumer reads. The episode
TEXT (dossier, script, sources, claims) is committed like the gated shows'
text (operator choice, Oct 13 2026); only audio is private.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
SPECIALS_DIR = ROOT / "specials"
SERIES_DIR = SPECIALS_DIR / "series"
CATALOG_PATH = SPECIALS_DIR / "catalog.json"
PROMPTS_DIR = ROOT / "shows" / "prompts" / "specials"

#: Keyspace in the private bucket (``engine.access.private_bucket``).
PRIVATE_PREFIX = "specials"
#: Keyspace in the PUBLIC audio bucket for trailers (new; touches no
#: published enclosure).
PUBLIC_TRAILER_PREFIX = "specials"

STANCES = ("neutral", "for", "against")

#: Spoken words per minute for the host voices (measured network median,
#: Oct 14 2026 review); 25-35 minutes is the operator's target.
WORDS_PER_MINUTE = 150
TARGET_MINUTES = (25, 35)
#: A script under this many words does not produce. There is no expansion
#: retry: length comes from the dossier (network rule, length levers are
#: digest-side).
MIN_SCRIPT_WORDS = 3300
TARGET_SCRIPT_WORDS = "3,900 to 5,000"

#: Domains whose pages are never a source for a special: social posts are
#: leads, not evidence (the @grok rule, Oct 11 2026).
SOCIAL_DOMAINS = (
    "x.com", "twitter.com", "reddit.com", "youtube.com", "youtu.be",
    "facebook.com", "instagram.com", "tiktok.com", "threads.net",
    "linkedin.com", "quora.com", "pinterest.com",
)
#: A fetched page shorter than this is a stub, a paywall or an error page.
MIN_SOURCE_CHARS = 600
SOURCE_TEXT_CHARS = 3500
MAX_SOURCES = 30
RESULTS_PER_QUESTION = 6

DEFAULT_MODEL = "grok-4.7"
FALLBACK_MODEL = "grok-4.3"
DOSSIER_MAX_TOKENS = 16000
SCRIPT_MAX_TOKENS = 14000
LLM_TIMEOUT_S = 1500.0


#: The spoken disclosure every Patrick-voice episode closes on — the same
#: words as ``run_show._AI_DISCLOSURE`` (a test keeps them identical).
AI_DISCLOSURE = (
    "This episode used AI voice synthesis of my voice — "
    "editorial selection and analysis are my own."
)


class SpecialsError(RuntimeError):
    """A series file is invalid or an episode cannot be produced."""


class ThinResearch(SpecialsError):
    """Fewer readable sources were fetched than the series requires."""


# ---------------------------------------------------------------------------
# Series model
# ---------------------------------------------------------------------------

@dataclass
class Episode:
    id: str
    part: int
    title: str
    brief: str
    questions: List[str]
    stance: str = "neutral"
    peptide: Optional[str] = None


@dataclass
class Series:
    id: str
    title: str
    host_show: str
    tease_shows: List[str]
    episodes: List[Episode]
    subtitle: str = ""
    summary: str = ""
    teaser: str = ""
    x_env_prefixes: List[str] = field(default_factory=list)
    min_sources: int = 10
    rules_file: str = ""
    episode_template: str = ""
    model: str = DEFAULT_MODEL
    blocking_lints: List[str] = field(default_factory=list)
    path: Optional[Path] = None

    @property
    def total_parts(self) -> int:
        return len(self.episodes)

    def episode(self, episode_id: str) -> Episode:
        for ep in self.episodes:
            if ep.id == episode_id:
                return ep
        raise SpecialsError(f"{self.id}: no episode {episode_id!r}")

    def rules_text(self) -> str:
        if not self.rules_file:
            return ""
        path = ROOT / self.rules_file
        return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def _host_slugs() -> set:
    return {p.stem for p in (ROOT / "shows").glob("*.yaml") if not p.stem.startswith("_")}


def load_series(path: Path) -> Series:
    """Parse and validate one series file. Raises :class:`SpecialsError`."""
    import yaml

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    sid = str(raw.get("id") or "").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", sid):
        raise SpecialsError(f"{path}: id must be lowercase letters, digits and hyphens")
    host = str(raw.get("host_show") or "")
    hosts = _host_slugs()
    if host not in hosts:
        raise SpecialsError(f"{sid}: host_show {host!r} has no shows/<slug>.yaml")
    tease = [str(s) for s in (raw.get("tease_shows") or [host])]
    for slug in tease:
        if slug not in hosts:
            raise SpecialsError(f"{sid}: tease show {slug!r} has no shows/<slug>.yaml")
    episodes: List[Episode] = []
    seen: set = set()
    for i, e in enumerate(raw.get("episodes") or [], start=1):
        eid = str(e.get("id") or "").strip()
        if not eid or eid in seen:
            raise SpecialsError(f"{sid}: episode {i} has a missing or duplicate id")
        seen.add(eid)
        part = int(e.get("part") or 0)
        if part != i:
            raise SpecialsError(f"{sid}: episode {eid} is part {part}, expected {i}")
        stance = str(e.get("stance") or "neutral")
        if stance not in STANCES:
            raise SpecialsError(f"{sid}: episode {eid} has stance {stance!r}")
        questions = [str(q).strip() for q in (e.get("questions") or []) if str(q).strip()]
        if len(questions) < 3:
            raise SpecialsError(f"{sid}: episode {eid} needs at least 3 research questions")
        brief = str(e.get("brief") or "").strip()
        title = str(e.get("title") or "").strip()
        if not (brief and title):
            raise SpecialsError(f"{sid}: episode {eid} needs a title and a brief")
        episodes.append(Episode(
            id=eid, part=part, title=title, brief=brief, questions=questions,
            stance=stance, peptide=e.get("peptide") or None))
    if not episodes:
        raise SpecialsError(f"{sid}: no episodes")
    lints = [str(x) for x in (raw.get("blocking_lints") or [])]
    if host == "peptides" and "dose_terms" not in lints:
        # Peptides Weekly's blocking rule binds every special it hosts.
        lints.append("dose_terms")
    return Series(
        id=sid, title=str(raw.get("title") or sid), host_show=host,
        tease_shows=tease, episodes=episodes,
        subtitle=str(raw.get("subtitle") or ""), summary=str(raw.get("summary") or "").strip(),
        teaser=str(raw.get("teaser") or "").strip(),
        x_env_prefixes=[str(p) for p in (raw.get("x_env_prefixes") or [])],
        min_sources=int(raw.get("min_sources") or 10),
        rules_file=str(raw.get("rules_file") or ""),
        episode_template=str(raw.get("episode_template") or "").strip(),
        model=str(raw.get("model") or DEFAULT_MODEL),
        blocking_lints=lints, path=Path(path),
    )


def all_series() -> List[Series]:
    return [load_series(p) for p in sorted(SERIES_DIR.glob("*.yaml"))]


def find_series(series_id: str) -> Series:
    for s in all_series():
        if s.id == series_id:
            return s
    raise SpecialsError(f"no series {series_id!r} in {SERIES_DIR}")


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

def load_catalog(path: Path = CATALOG_PATH) -> Dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"series": {}}
    data.setdefault("series", {})
    return data


def save_catalog(catalog: Dict[str, Any], path: Path = CATALOG_PATH) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")


def series_entry(catalog: Dict[str, Any], series: Series) -> Dict[str, Any]:
    entry = catalog["series"].setdefault(series.id, {})
    entry.update({
        "title": series.title, "subtitle": series.subtitle,
        "summary": series.summary, "teaser": series.teaser,
        "host_show": series.host_show, "tease_shows": series.tease_shows,
        "total_parts": series.total_parts,
    })
    entry.setdefault("status", "planned")
    entry.setdefault("episodes", {})
    return entry


def released_series(catalog: Optional[Dict[str, Any]] = None) -> List[Tuple[str, Dict[str, Any]]]:
    """``(series_id, entry)`` for every released series, newest release first."""
    catalog = catalog if catalog is not None else load_catalog()
    out = [(sid, e) for sid, e in catalog.get("series", {}).items()
           if e.get("status") == "released"]
    return sorted(out, key=lambda x: str(x[1].get("released_date") or ""), reverse=True)


def released_for_show(slug: str, *, within_days: Optional[int] = None,
                      today: Optional[dt.date] = None,
                      catalog: Optional[Dict[str, Any]] = None) -> List[Tuple[str, Dict[str, Any]]]:
    """Released series a show teases (optionally only recent releases)."""
    today = today or dt.date.today()
    out = []
    for sid, entry in released_series(catalog):
        if slug not in (entry.get("tease_shows") or []):
            continue
        if within_days is not None:
            try:
                released = dt.date.fromisoformat(str(entry.get("released_date")))
            except ValueError:
                continue
            if (today - released).days > within_days:
                continue
        out.append((sid, entry))
    return out


def episode_dir(series: Series, episode: Episode) -> Path:
    return SPECIALS_DIR / series.id / f"{episode.part:02d}-{episode.id}"


def audio_filename(series: Series, episode: Episode) -> str:
    return f"{series.id}-part{episode.part:02d}-{episode.id}.mp3"


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------

def _domain(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_social(url: str) -> bool:
    host = _domain(url)
    return any(host == d or host.endswith("." + d) for d in SOCIAL_DOMAINS)


def _norm_url(url: str) -> str:
    from engine.claims import normalize_source_url
    return normalize_source_url(url or "")


def research_episode(
    episode: Episode,
    *,
    search: Optional[Callable[..., List[dict]]] = None,
    enrich: Optional[Callable[..., int]] = None,
    per_question: int = RESULTS_PER_QUESTION,
    max_sources: int = MAX_SOURCES,
) -> List[dict]:
    """Run every research question, keep only pages actually read.

    A search result is a lead: its ``description`` is the search model's
    summary and never evidence (``engine.claims.build_local_texts``). Each
    result's page is fetched; only results whose page text was read and is
    longer than :data:`MIN_SOURCE_CHARS` are kept, deduplicated by URL,
    social posts excluded.
    """
    if search is None:
        from engine.fetcher import fetch_topic_research_articles as search
    if enrich is None:
        from engine.article_text import enrich_articles_with_full_text as enrich
    by_url: Dict[str, dict] = {}
    for question in episode.questions:
        try:
            results = search(question, episode.brief, max_results=per_question) or []
        except Exception as exc:  # noqa: BLE001 — one failed search is not the episode
            logger.warning("specials: search failed for %r: %s", question, exc)
            continue
        for art in results:
            url = str(art.get("url") or "")
            key = _norm_url(url)
            if not key or is_social(url) or key in by_url:
                continue
            art = dict(art)
            art.setdefault("source_kind", "research")
            art["research_question"] = question
            by_url[key] = art
    candidates = list(by_url.values())
    if candidates:
        enrich(candidates, max_articles=len(candidates), max_chars=SOURCE_TEXT_CHARS * 2)
    kept = [a for a in candidates
            if a.get("full_text_source") == "page"
            and len(str(a.get("full_text") or "")) >= MIN_SOURCE_CHARS]
    return kept[:max_sources]


def format_sources(articles: Sequence[dict]) -> str:
    blocks = []
    for n, art in enumerate(articles, start=1):
        text = " ".join(str(art.get("full_text") or "").split())[:SOURCE_TEXT_CHARS]
        date = str(art.get("published_date") or "").strip()
        blocks.append(
            f"[{n}] {art.get('title') or _domain(str(art.get('url')))}"
            f"{' (' + date + ')' if date else ''}\n"
            f"URL: {art.get('url')}\n"
            f"TEXT: {text}")
    return "\n\n".join(blocks)


def sources_record(articles: Sequence[dict]) -> List[dict]:
    return [{"n": n, "title": a.get("title") or "", "url": a.get("url") or "",
             "domain": _domain(str(a.get("url") or "")),
             "published_date": a.get("published_date") or "",
             "question": a.get("research_question") or ""}
            for n, a in enumerate(articles, start=1)]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def previous_parts_text(series: Series, episode: Episode,
                        catalog: Optional[Dict[str, Any]] = None) -> str:
    """What earlier parts covered: their titles and the questions their
    dossiers answered (section headings), from the committed dossiers."""
    lines = []
    for ep in series.episodes:
        if ep.part >= episode.part:
            break
        heads: List[str] = []
        dossier = episode_dir(series, ep) / "dossier.md"
        if dossier.is_file():
            heads = [m.group(1).strip() for m in re.finditer(
                r"^##\s+(.+)$", dossier.read_text(encoding="utf-8"), re.M)]
        lines.append(f"- Part {ep.part}, \"{ep.title}\""
                     + (f": {'; '.join(heads)}" if heads else ""))
    return "\n".join(lines) or "This is the first part."


def stance_note(episode: Episode) -> str:
    if episode.stance == "for":
        return ("STANCE: this part argues the case FOR, by design. Say so in the "
                "first minute, make the strongest honest version of the case "
                "from the dossier, and answer the strongest objection to it.")
    if episode.stance == "against":
        return ("STANCE: this part argues the case AGAINST, by design. Say so in "
                "the first minute, make the strongest honest version of the case "
                "from the dossier, and answer the strongest point for the other side.")
    return ("STANCE: neutral. Present every material argument at its strongest "
            "and take no side.")


def _render(name: str, **values: Any) -> str:
    from engine.generator import load_prompt
    return load_prompt(PROMPTS_DIR / name, {k: v for k, v in values.items()})


def dossier_prompt(series: Series, episode: Episode, articles: Sequence[dict],
                   *, today: dt.date, catalog: Optional[Dict[str, Any]] = None) -> str:
    from engine.claims import claims_prompt_appendix

    template = ""
    if series.episode_template and episode.peptide:
        template = (f"\nTHE PEPTIDE: {episode.peptide}\nANSWER THESE IN ORDER "
                    f"(each is a section or part of one):\n{series.episode_template}\n")
    return _render(
        "dossier.txt", series_title=series.title, today=today.isoformat(),
        part=episode.part, total_parts=series.total_parts,
        episode_title=episode.title, brief=episode.brief,
        episode_template=template,
        previous_parts=previous_parts_text(series, episode, catalog),
        series_rules=series.rules_text(), sources=format_sources(articles),
        claims_appendix=claims_prompt_appendix(),
    )


def script_prompt(series: Series, episode: Episode, dossier: str, *,
                  today: dt.date, host_name: str, show_name: str,
                  catalog: Optional[Dict[str, Any]] = None) -> str:
    nxt = next((e for e in series.episodes if e.part == episode.part + 1), None)
    next_clause = (f" (part {nxt.part}, \"{nxt.title}\")" if nxt
                   else " — this is the final part, so close the series instead")
    sign_off = (f"This has been {series.title}, part {episode.part} of "
                f"{series.total_parts}, for Nerra Personal members. I'm {host_name}.")
    return _render(
        "script.txt", host_name=host_name, show_name=show_name,
        part=episode.part, total_parts=series.total_parts,
        series_title=series.title, episode_title=episode.title,
        today=today.isoformat(), series_rules=series.rules_text(),
        stance_note=stance_note(episode), dossier=dossier,
        previous_parts=previous_parts_text(series, episode, catalog),
        next_part_clause=next_clause, target_words=TARGET_SCRIPT_WORDS,
        min_words=MIN_SCRIPT_WORDS, sign_off=sign_off,
    )


def trailer_prompt(series: Series, *, host_name: str, show_name: str) -> str:
    episode_list = "\n".join(f"- Part {e.part}: {e.title}. {e.brief.splitlines()[0]}"
                             for e in series.episodes)
    return _render(
        "trailer.txt", host_name=host_name, show_name=show_name,
        series_title=series.title, summary=series.summary,
        total_parts=series.total_parts, episode_list=episode_list,
        series_rules=series.rules_text(),
    )


# ---------------------------------------------------------------------------
# Generation and checks
# ---------------------------------------------------------------------------

def call_model(prompt: str, *, model: str, max_tokens: int,
               system_prompt: Optional[str] = None,
               caller: Optional[Callable[..., Tuple[str, Dict[str, Any]]]] = None,
               ) -> Tuple[str, Dict[str, Any]]:
    """One streamed call on the series' model, once more on the network
    default if it fails. Returns ``(text, meta)`` with the served model."""
    from engine.utils import strip_model_special_tokens

    if caller is None:
        from engine.generator import _call_grok as caller
    last_exc: Optional[Exception] = None
    for m in dict.fromkeys([model, FALLBACK_MODEL]):
        try:
            text, meta = caller(prompt, model=m, system_prompt=system_prompt,
                                max_tokens=max_tokens, timeout=LLM_TIMEOUT_S,
                                temperature=0.5, stream=True)
        except Exception as exc:  # noqa: BLE001 — try the fallback model
            logger.warning("specials: %s failed (%s)", m, exc)
            last_exc = exc
            continue
        if (text or "").strip():
            meta = dict(meta or {})
            meta["served_model"] = m
            return strip_model_special_tokens(text), meta
    raise SpecialsError(f"no model answered: {last_exc}")


def blocking_lint_findings(text: str, series: Series) -> List[str]:
    """Human-readable findings for the series' blocking lints."""
    out = []
    if "dose_terms" in series.blocking_lints:
        from engine.digest_lint import dose_terms
        hits = dose_terms(text)
        if hits:
            out.append("the text states a dose, route, preparation or protocol "
                       f"({', '.join(hits[:6])}) — this series never does, in any framing")
    return out


def check_claims(dossier: str, claims: Optional[List[dict]], articles: Sequence[dict],
                 *, fetch=None) -> Dict[str, Any]:
    """The claims gate in flag mode: every entry gets a status, nothing is
    removed but reviewer notes. Returns the sidecar dict."""
    from engine.claims import build_local_texts, flag_unverified, run_source_integrity_gate

    gate = run_source_integrity_gate(dossier, claims, fetch=fetch,
                                     local_texts=build_local_texts(list(articles)))
    flagged = flag_unverified(dossier, gate, list(claims or []), fetch=fetch)
    ledger = list(flagged.claims or [])
    statuses: Dict[str, int] = {}
    for entry in ledger:
        s = str(entry.get("status") or "")
        statuses[s] = statuses.get(s, 0) + 1
    verified = sum(v for k, v in statuses.items() if k.startswith("verified"))
    return {
        "claims_total": len(claims or []),
        "claims_verified": verified,
        "statuses": statuses,
        "flagged_sentences": list(flagged.flagged_sentences or []),
        "removed_notes": list(flagged.removed_notes or []),
        "ledger": ledger,
        "text": flagged.text or dossier,
    }


def clean_script(text: str) -> str:
    """Spoken text only: no markdown, headings, speech tags or labels."""
    from engine.utils import strip_speech_tags

    text = strip_speech_tags(text or "")
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            if not s:
                lines.append("")
            continue
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
        s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
        s = re.sub(r"^(?:[*_>•]+|-(?=\s))\s*", "", s)
        lines.append(s)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'’-]+\b", text or ""))


# ---------------------------------------------------------------------------
# Release surfaces
# ---------------------------------------------------------------------------

SITE = "https://nerranetwork.com"
SPECIALS_PAGE = "specials.html"
JOIN_PAGE = "join.html"


def series_page_url(series_id: str) -> str:
    return f"{SITE}/{SPECIALS_PAGE}#{series_id}"


def trailer_guid(show_slug: str, series_id: str) -> str:
    """No ``ep<digits>`` anywhere: ``get_next_episode_number`` reads that
    shape out of every GUID, and a trailer is not a numbered episode."""
    guid = f"{show_slug}-members-special-{series_id}-trailer"
    assert not re.search(r"ep\d", guid), guid
    return guid


def x_teaser_text(entry: Dict[str, Any], series_id: str) -> str:
    from engine.x_post import teaser_text

    head = (f"New members-only series: {entry.get('title')}. "
            f"{entry.get('teaser') or entry.get('summary') or ''}")
    return teaser_text(head, series_page_url(series_id))


def _xml(text: str) -> str:
    from xml.sax.saxutils import escape
    return escape(str(text or ""), {'"': "&quot;"})


def trailer_item_xml(*, guid: str, title: str, description: str, audio_url: str,
                     length: int, duration_seconds: float, pub_date: dt.datetime,
                     link: str) -> str:
    from email.utils import format_datetime

    secs = int(round(duration_seconds or 0))
    return (
        "<item>"
        f"<title>{_xml(title)}</title>"
        f"<link>{_xml(link)}</link>"
        f"<description>{_xml(description)}</description>"
        f"<guid isPermaLink=\"false\">{_xml(guid)}</guid>"
        f"<pubDate>{format_datetime(pub_date)}</pubDate>"
        f"<enclosure url=\"{_xml(audio_url)}\" length=\"{int(length or 0)}\" type=\"audio/mpeg\"/>"
        f"<itunes:title>{_xml(title)}</itunes:title>"
        f"<itunes:duration>{secs // 60}:{secs % 60:02d}</itunes:duration>"
        "<itunes:episodeType>trailer</itunes:episodeType>"
        "<itunes:explicit>no</itunes:explicit>"
        "</item>"
    )


def insert_trailer_item(rss_path: Path, item_xml: str, guid: str) -> bool:
    """Put a trailer item at the top of a show's free feed, once.

    Inserted as text before the first ``<item>`` (or before ``</channel>``)
    so nothing else in the feed is re-serialised. ``update_rss_feed``
    keeps it on every later rebuild (``_unnumbered_trailer_items`` lifts
    the block out before the numbered rebuild and puts it back after), and
    the numbering ignores a GUID with no ``ep<digits>``. Returns False when
    the GUID is already present.
    """
    text = Path(rss_path).read_text(encoding="utf-8")
    if f">{guid}<" in text:
        return False
    i = text.find("<item>")
    if i < 0:
        i = text.find("<item ")
    if i < 0:
        i = text.find("</channel>")
    if i < 0:
        raise SpecialsError(f"{rss_path}: not an RSS feed")
    Path(rss_path).write_text(text[:i] + item_xml + "\n" + text[i:], encoding="utf-8")
    return True


#: How long after release a teaser show's emails carry the P.S.
NEWSLETTER_MENTION_DAYS = 14


def newsletter_ps(slug: str, today: Optional[dt.date] = None,
                  catalog: Optional[Dict[str, Any]] = None) -> str:
    """The P.S. a teaser show's daily email carries for 14 days after a
    series is released; ``""`` otherwise. Plain text (the template
    escapes it)."""
    rows = released_for_show(slug, within_days=NEWSLETTER_MENTION_DAYS,
                             today=today, catalog=catalog)
    if not rows:
        return ""
    sid, entry = rows[0]
    return (f"New for Nerra Personal members: {entry.get('title')}, "
            f"{entry.get('total_parts')} episodes, all out now. "
            f"{entry.get('teaser') or ''} Details: {series_page_url(sid)}").strip()


def member_feed_rows(catalog: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """One row per produced episode of every released series, in part
    order — what a paying member's Personal feed carries
    (``engine.personal_edition.build_personal_feed_xml(specials=…)``)."""
    rows: List[Dict[str, Any]] = []
    for sid, entry in released_series(catalog):
        eps = sorted(entry.get("episodes", {}).items(), key=lambda kv: int(kv[1].get("part", 0)))
        for eid, ep in eps:
            if ep.get("status") != "produced" or not ep.get("audio_ref"):
                continue
            rows.append({
                "series_id": sid, "episode_id": eid,
                "series_title": entry.get("title") or sid,
                "part": int(ep.get("part", 0)), "total_parts": int(entry.get("total_parts") or 0),
                "title": f"{entry.get('title')}, Part {ep.get('part')}: {ep.get('title')}",
                "description": str(entry.get("summary") or ""),
                "date": str(entry.get("released_date") or ""),
                "filename": str(ep.get("filename") or ""),
                "audio_ref": str(ep.get("audio_ref") or ""),
                "bytes": int(ep.get("bytes") or 0),
                "duration_seconds": float(ep.get("duration_seconds") or 0),
            })
    return rows


def private_key_from_ref(ref: str) -> Tuple[str, str]:
    """``r2-private://<bucket>/<key>`` -> ``(bucket, key)``."""
    from engine.access import PRIVATE_URL_SCHEME
    if not ref.startswith(PRIVATE_URL_SCHEME):
        raise SpecialsError(f"not a private audio reference: {ref!r}")
    bucket, _, key = ref[len(PRIVATE_URL_SCHEME):].partition("/")
    return bucket, key


__all__ = [
    "Episode", "Series", "SpecialsError", "ThinResearch",
    "load_series", "all_series", "find_series",
    "load_catalog", "save_catalog", "series_entry", "released_series",
    "released_for_show", "episode_dir", "audio_filename",
    "research_episode", "format_sources", "sources_record", "is_social",
    "previous_parts_text", "stance_note",
    "dossier_prompt", "script_prompt", "trailer_prompt",
    "call_model", "blocking_lint_findings", "check_claims", "clean_script",
    "word_count", "series_page_url", "trailer_guid", "x_teaser_text",
    "trailer_item_xml", "insert_trailer_item", "member_feed_rows",
    "private_key_from_ref",
]
