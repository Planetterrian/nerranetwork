"""Newsroom signals for the homepage (Oct 18 2026).

The homepage became the network's news front page on 2026-10-18 (operator
direction: "updating and containing timely news information and updates as
any successful news and information site would be expected to have"). A news
front shows WHEN each story went out, what is still developing, the dated
market and launch numbers its stories lean on, its corrections, and when the
day's editions arrive. This module computes each of those from committed
files; ``generate_html.generate_network_page`` reads the files and passes them
in, so every function here is pure (no I/O, no clock — the caller passes
*now*).

Honesty rules, each guarded in ``tests/test_homepage_landing_2026_10_18.py``:

* **A story's time is the moment its summary record was written**
  (``record["datetime"]``, written by ``engine.publisher`` /
  ``build_daily_edition`` from the runner clock, which is UTC). The feed's
  ``pubDate`` is NOT that time: every item carries ``08:00:00 +0000``. A record
  without a time prints its date only — never an invented hour.
* **Eastern time** is the network's clock (the scheduler and the release
  schedule run on it), so every stamp is America/New_York wall time, labelled
  "ET".
* **A developing story is found, never written**: salient-word overlap between
  the digests' own headlines and hooks over the last seven days, the
  ``engine.story_recurrence`` matcher widened from one show's window to the
  network's. No LLM. A thread needs two or more days, a recent last update,
  and real overlap; a section label the same show prints every day is
  furniture, not a story. Better few true threads than many weak ones.
* **A number without its date is not shown.** Each market or launch value
  carries the as-of date of the file it came from; a value older than
  ``MARKET_MAX_AGE_DAYS`` (or a launch whose NET has passed) renders nothing.
* **Corrections** are ``engine.corrections`` records, newest filing first.
* **The day's schedule** is read from ``engine.release_schedule`` and
  ``engine.daily_edition`` constants — never typed times.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence
from zoneinfo import ZoneInfo

from engine.story_recurrence import salient_tokens

EASTERN = ZoneInfo("America/New_York")
UTC = dt.timezone.utc


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------


def _aware(now: dt.datetime) -> dt.datetime:
    return now if now.tzinfo else now.replace(tzinfo=UTC)


def _parse_iso(value: Any) -> Optional[dt.datetime]:
    """An ISO timestamp as an aware UTC datetime; a naive one is UTC (the
    runner clock). ``None`` for anything unparseable."""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        when = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _aware(when).astimezone(UTC)


def _parse_day(value: Any) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(str(value or "").strip()[:10])
    except ValueError:
        return None


def published_at(record: dict) -> Optional[dt.datetime]:
    """When the episode's summary record was written, as aware UTC.

    ``None`` when the record carries no time, or when its time disagrees with
    its own ``date`` by more than a day (a hand-edited record) — a date-only
    stamp is honest, a wrong hour is not.
    """
    if not isinstance(record, dict):
        return None
    when = _parse_iso(record.get("datetime"))
    if when is None:
        return None
    day = _parse_day(record.get("date"))
    if day is not None and abs((when.date() - day).days) > 1:
        return None
    return when


def _clock(t: dt.datetime) -> str:
    """``5:47 AM`` — no leading zero, the AP style."""
    hour = t.hour % 12 or 12
    return f"{hour}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def eastern_label(when: dt.datetime, *, with_date: bool = True) -> str:
    """``Oct 17, 5:47 AM ET`` (or ``5:47 AM ET``) for an aware datetime."""
    t = _aware(when).astimezone(EASTERN)
    clock = f"{_clock(t)} ET"
    return f"{t.strftime('%b')} {t.day}, {clock}" if with_date else clock


def date_label(day: dt.date) -> str:
    """``Oct 14``."""
    return f"{day.strftime('%b')} {day.day}"


def stamp(record_date: Any, when: Optional[dt.datetime], now: dt.datetime) -> Dict[str, Any]:
    """Template-ready publication stamp for one story.

    ``iso`` goes in ``<time datetime>`` (a UTC instant ``…Z`` when the time is
    known, else the bare date); ``label`` is the server-rendered absolute text
    the page script upgrades to "2 hours ago"; ``day`` is the Eastern date the
    "Today" marker compares against; ``is_today`` is that comparison at build
    time. Everything is empty when nothing is known.
    """
    today = _aware(now).astimezone(EASTERN).date()
    if when is not None:
        t = _aware(when).astimezone(EASTERN)
        return {"iso": _aware(when).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "label": eastern_label(when), "short": date_label(t.date()),
                "day": t.date().isoformat(), "is_today": t.date() == today,
                "has_time": True}
    day = _parse_day(record_date)
    if day is None:
        return {"iso": "", "label": "", "short": "", "day": "", "is_today": False,
                "has_time": False}
    return {"iso": day.isoformat(), "label": date_label(day), "short": date_label(day),
            "day": day.isoformat(), "is_today": day == today, "has_time": False}


def masthead(now: dt.datetime) -> Dict[str, str]:
    """The masthead's dateline and "Updated" stamp, from the build clock."""
    t = _aware(now).astimezone(EASTERN)
    return {
        "date": f"{t.strftime('%A, %B')} {t.day}, {t.year}",
        "date_iso": t.date().isoformat(),
        "updated_iso": _aware(now).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated": f"{_clock(t)} ET",
    }


# ---------------------------------------------------------------------------
# Developing stories
# ---------------------------------------------------------------------------

#: The window a thread is looked for in, and how recent its last update must
#: be to still read as developing on today's front page.
DEVELOPING_WINDOW_DAYS = 7
DEVELOPING_MAX_SILENCE_DAYS = 3
DEVELOPING_MIN_DAYS = 2
DEVELOPING_LIMIT = 5

#: Two headlines are one story when they share at least this many salient
#: words AND those words are at least this share of the shorter headline's.
#: Calibrated on the committed digests, Oct 10-17 2026 (docs/landing_test.md,
#: v3): 3 / 0.5 found 3-9 threads per window, every one a real thread; 2 /
#: 0.5 doubled the count and let in "Google releases an AI detection tool"
#: beside "Google releases Gemini 4" and two unrelated dinosaur finds.
DEVELOPING_MIN_SHARED = 3
DEVELOPING_MIN_SHARE = 0.5

#: A word in more than this share of the window's headlines is a beat word
#: ("tesla", "spacex", "launch"), never evidence that two headlines match —
#: the same document-frequency idea as ``engine.story_recurrence``.
DEVELOPING_COMMON_SHARE = 0.015
#: ... and never fewer than this many headlines: a short window (a quiet
#: week, a test fixture) would otherwise call a word common at two uses.
DEVELOPING_COMMON_MIN_COUNT = 8

#: Two headlines from the SAME show whose salient tokens differ by at most
#: this many (symmetric difference) are one recurring segment label.
#: Replayed on Oct 12-18 2026: the real same-show threads (iPhone Duo,
#: Booster 23, Perseverance) differ by five or more.
FURNITURE_MAX_SWAP = 2

#: Generic headline words, on top of story_recurrence's stopwords: verbs and
#: quantities every beat uses, and the spelled-out numbers the TTS-ready
#: digests print ("seven point four nine"). Without them "Canucks visit the
#: Hurricanes tonight" matched "Canucks visit the Islanders tonight". The
#: product-news verbs (release / launch / unveil / announce) joined Oct 18
#: 2026: "Google releases a $100 Home Speaker for Gemini" threaded with
#: "Google Releases Gemini 4 Argon API" on {google, releases, gemini}.
GENERIC_WORDS = frozenset("""
coming soon exec execs says said new upgrades upgrade cool very few hundred
hundreds thousand thousands dollars dollar several only contain contains cost
costs held sell sells million billion percent per week weeks day days year
years month months today tomorrow yesterday first second third last next latest
more most less than about around nearly almost over under after before while
during amid could would should will may might can just still also now back big
small major minor key top high low plans plan set sets get gets got make makes
made take takes took show shows episode story stories update updates report
reports news what why how where when who which tonight visit visits fall falls
rise rises hit hits record records share shares face faces reach reaches
reached one two three four five six seven eight nine ten eleven twelve thirteen
fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty
sixty seventy eighty ninety point
release releases released launch launches launched unveil unveils unveiled
announce announces announced
""".split())


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").lower()).strip()


def _tokens(text: str) -> frozenset:
    return frozenset(salient_tokens(text) - GENERIC_WORDS)


def developing_stories(episodes: Iterable[Dict[str, Any]], now: dt.datetime, *,
                       window_days: int = DEVELOPING_WINDOW_DAYS,
                       max_silence_days: int = DEVELOPING_MAX_SILENCE_DAYS,
                       min_days: int = DEVELOPING_MIN_DAYS,
                       limit: int = DEVELOPING_LIMIT) -> List[Dict[str, Any]]:
    """Threads the network covered on *min_days* or more days in the window.

    *episodes* are dicts with ``slug``, ``show_name``, ``show_page``,
    ``brand_color``, ``day`` (``date``, Eastern), ``stamp`` (``stamp()``),
    ``post_url`` and ``headlines`` (the hook first, then the digest's story
    headlines). Returns, newest update first, at most *limit* threads::

        {"days": 2, "shows": [{"name", "show_page", "brand_color"}],
         "latest": {"headline", "url", "show_name", "stamp"},
         "earlier": [{"headline", "url", "show_name", "stamp"}, ...]}

    An item's ``url`` is its episode article when one exists, else '' (the
    template then links the show page).
    """
    today = _aware(now).astimezone(EASTERN).date()
    window = [e for e in episodes
              if isinstance(e.get("day"), dt.date)
              and 0 <= (today - e["day"]).days < window_days]

    # Furniture: a line the same show prints on two or more days, a
    # one-word variant of it ("Unusual Whales Options Flow" / "… API"), or a
    # one-word SWAP of it ("Interactive Brokers Volume Scanner" / "… TWS
    # Scanner" — MIT's recurring tool segment, Oct 18 2026: salient-token
    # symmetric difference of at most FURNITURE_MAX_SWAP) is a segment label,
    # not a story that developed.
    by_show: Dict[str, List[tuple]] = defaultdict(list)
    for ep in window:
        for text in ep.get("headlines") or []:
            by_show[ep["slug"]].append((ep["day"], _norm(text), _tokens(text)))
    furniture = set()
    for slug, rows in by_show.items():
        for i, (d1, n1, t1) in enumerate(rows):
            for d2, n2, t2 in rows[i + 1:]:
                if d1 == d2 or not t1 or not t2:
                    continue
                small, big = (t1, t2) if len(t1) <= len(t2) else (t2, t1)
                if (n1 == n2 or (small <= big and len(big - small) <= 1)
                        or (len(t1 & t2) >= 2
                            and len(t1 ^ t2) <= FURNITURE_MAX_SWAP)):
                    furniture.add((slug, n1))
                    furniture.add((slug, n2))

    items = []
    for ep in window:
        seen = set()
        for text in ep.get("headlines") or []:
            key = _norm(text)
            if not key or key in seen or (ep["slug"], key) in furniture:
                continue
            seen.add(key)
            items.append({"ep": ep, "text": text.strip(), "tokens": _tokens(text)})
    if not items:
        return []

    freq = Counter(t for it in items for t in it["tokens"])
    floor = max(DEVELOPING_COMMON_SHARE * len(items), DEVELOPING_COMMON_MIN_COUNT)
    common = {t for t, c in freq.items() if c > floor}
    for it in items:
        it["tokens"] = it["tokens"] - common

    parent = list(range(len(items)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, ia in enumerate(items):
        if len(ia["tokens"]) < 2:
            continue
        for b in range(a + 1, len(items)):
            ib = items[b]
            if len(ib["tokens"]) < 2 or ia["ep"] is ib["ep"]:
                continue
            shared = len(ia["tokens"] & ib["tokens"])
            if (shared >= DEVELOPING_MIN_SHARED and shared
                    / min(len(ia["tokens"]), len(ib["tokens"])) >= DEVELOPING_MIN_SHARE):
                parent[find(a)] = find(b)

    groups: Dict[int, List[dict]] = defaultdict(list)
    for n, it in enumerate(items):
        groups[find(n)].append(it)

    threads = []
    for members in groups.values():
        days = {m["ep"]["day"] for m in members}
        last_day = max(days)
        if len(days) < min_days or (today - last_day).days > max_silence_days:
            continue
        # One entry per episode (the hook and the same story's numbered
        # headline are one telling), newest first.
        per_ep: Dict[int, dict] = {}
        for m in members:
            per_ep.setdefault(id(m["ep"]), m)
        tellings = sorted(per_ep.values(), key=lambda m: (
            m["ep"]["day"], m["ep"]["stamp"].get("iso") or "", m["ep"]["slug"]), reverse=True)

        def _row(m: dict) -> Dict[str, Any]:
            ep = m["ep"]
            return {"headline": m["text"], "url": ep.get("post_url") or "",
                    "show_name": ep["show_name"], "show_page": ep["show_page"],
                    "brand_color": ep.get("brand_color") or "", "stamp": ep["stamp"],
                    "lang": ep.get("lang") or ""}

        shows, seen_shows = [], set()
        for m in tellings:
            ep = m["ep"]
            if ep["slug"] not in seen_shows:
                seen_shows.add(ep["slug"])
                shows.append({"name": ep["show_name"], "show_page": ep["show_page"],
                              "brand_color": ep.get("brand_color") or ""})
        threads.append({
            "days": len(days),
            "first_day": min(days).isoformat(),
            "last_day": last_day.isoformat(),
            "shows": shows,
            "latest": _row(tellings[0]),
            "earlier": [_row(m) for m in tellings[1:3]],
        })
    threads.sort(key=lambda t: (t["last_day"], t["days"], len(t["shows"]),
                                t["latest"]["stamp"].get("iso") or ""), reverse=True)
    return threads[:limit]


# ---------------------------------------------------------------------------
# Markets & launches
# ---------------------------------------------------------------------------

#: A market value older than this many days (by its own date) is not shown.
MARKET_MAX_AGE_DAYS = 3

#: The quotes the strip prints, in order, from ``api/mag7_quotes.json``.
MARKET_TICKERS = ("TSLA", "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META")

#: Oct 19 2026: the page updates the strip from this Worker route
#: (workers/gallery/src/markets.ts). The build-time values stay on screen
#: until it answers, and whenever it does not.
LIVE_MARKETS_API = "https://api.nerranetwork.com/api/markets"

#: Seconds between live refreshes while the page is visible: quotes, and the
#: Latest headlines (re-read from the page's own latest build).
LIVE_QUOTES_REFRESH_S = 60
LIVE_HEADLINES_REFRESH_S = 300

#: The flagship shows' own tickers (engine.brand.FLAGSHIP_SHOW_SLUGS): the
#: front page's flagship band prints each show's line from the strip.
SHOW_TICKERS = {"spacex": "SPCX", "tesla": "TSLA"}


def _num(value) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _pct(value: Optional[float]) -> str:
    if value is None:
        return ""
    if round(value, 1) == 0:
        return "unchanged"
    return f"{'+' if value > 0 else '−'}{abs(value):.1f}%"


def _direction(value: Optional[float]) -> str:
    if value is None or round(value, 1) == 0:
        return "flat"
    return "up" if value > 0 else "down"


def _fresh(day: Optional[dt.date], today: dt.date) -> bool:
    return day is not None and 0 <= (today - day).days <= MARKET_MAX_AGE_DAYS


def market_strip(*, mag7: Optional[dict], spcx: Optional[dict], tsla: Optional[dict],
                 launches: Optional[dict], now: dt.datetime) -> Dict[str, Any]:
    """The markets & launches strip, every value with its as-of date.

    * Regular-session closes come from ``api/mag7_quotes.json`` (each quote
      carries its own ``bar_date``) and are labelled as closes.
    * TSLA falls back to ``api/tsla.json`` only when the closes file lacks it;
      that value is labelled a last quote with its fetch time, never "trading
      at" (a weekend fetch returns Friday's close — CLAUDE.md, the
      SpaceX/Tesla quote-verb rule).
    * SPCX comes from ``api/spcx.json`` as a last quote with its fetch time.
    * The next SpaceX launch is ``api/spacex_launches.json`` ``next``, shown
      only while its NET is still ahead of *now*.

    Returns ``{"quotes": [...], "groups": [...], "launch": {...} | None}``
    (``groups`` are the quotes under one as-of label each); every part is
    empty when its data is missing or stale.
    """
    now = _aware(now)
    today = now.astimezone(EASTERN).date()
    quotes: List[Dict[str, Any]] = []

    rows = (mag7 or {}).get("quotes") if isinstance(mag7, dict) else None
    by_ticker = {str(q.get("ticker") or "").upper(): q
                 for q in rows or [] if isinstance(q, dict)}
    for ticker in MARKET_TICKERS:
        q = by_ticker.get(ticker)
        if not q:
            continue
        close, pct, day = _num(q.get("close")), _num(q.get("change_pct")), _parse_day(q.get("bar_date"))
        if close is None or close <= 0 or not _fresh(day, today):
            continue
        quotes.append({"symbol": ticker, "price": f"${close:,.2f}", "change": _pct(pct),
                       "direction": _direction(pct), "basis": "close",
                       "as_of": date_label(day), "as_of_iso": day.isoformat()})

    def _quote(symbol: str, data: Optional[dict], time_key: str) -> None:
        if not isinstance(data, dict):
            return
        price, prev = _num(data.get("price")), _num(data.get("prev_close"))
        when = _parse_iso(data.get(time_key))
        if price is None or price <= 0 or when is None or not _fresh(
                when.astimezone(EASTERN).date(), today):
            return
        pct = _num(data.get("change_pct"))
        if pct is None and prev:
            pct = (price - prev) / prev * 100
        quotes.append({"symbol": symbol, "price": f"${price:,.2f}", "change": _pct(pct),
                       "direction": _direction(pct), "basis": "last quote",
                       "as_of": eastern_label(when),
                       "as_of_iso": when.strftime("%Y-%m-%dT%H:%M:%SZ")})

    if "TSLA" not in by_ticker or not any(q["symbol"] == "TSLA" for q in quotes):
        _quote("TSLA", tsla, "fetched_at")
        # Keep TSLA first, where the closes put it.
        quotes.sort(key=lambda q: 0 if q["symbol"] == "TSLA" else 1)
    _quote("SPCX", spcx, "updated_at")

    launch = None
    nxt = launches.get("next") if isinstance(launches, dict) else None
    updated = _parse_iso((launches or {}).get("updated_at")) if isinstance(launches, dict) else None
    if isinstance(nxt, dict) and updated is not None:
        net = _parse_iso(nxt.get("net"))
        mission = str(nxt.get("mission") or "").strip()
        if net is not None and mission and net > now and _fresh(
                updated.astimezone(EASTERN).date(), today):
            launch = {
                "mission": mission,
                "rocket": str(nxt.get("rocket") or "").strip(),
                "pad": str(nxt.get("location") or nxt.get("pad") or "").strip(),
                "net": eastern_label(net),
                "net_iso": net.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": str(nxt.get("status_name") or "").strip(),
                "as_of": eastern_label(updated),
                "as_of_short": date_label(updated.astimezone(EASTERN).date()),
                "as_of_iso": updated.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
    # One label per as-of date on the strip: "Closes · Oct 16", then each
    # last quote with its own fetch time.
    groups: List[Dict[str, Any]] = []
    for q in quotes:
        label = "Close" if q["basis"] == "close" else "Last quote"
        if groups and groups[-1]["basis"] == q["basis"] and groups[-1]["as_of"] == q["as_of"]:
            groups[-1]["quotes"].append(q)
            groups[-1]["label"] = "Closes"
        else:
            groups.append({"basis": q["basis"], "label": label, "as_of": q["as_of"],
                           "as_of_iso": q["as_of_iso"], "quotes": [q]})
    return {"quotes": quotes, "groups": groups, "launch": launch}


def quote_line(quote):
    """One strip quote as a line for another card, with the SAME basis and
    as-of date the strip prints ("TSLA close: $354.72 · Oct 16").

    Oct 18 2026: the homepage's Tesla dashboard card labelled the close a
    "last quote on record" dated by its weekend FETCH time (Oct 18) while the
    strip beside it said "Close · Oct 16". ``''`` when there is no quote.
    """
    if not quote:
        return ""
    label = "close" if quote.get("basis") == "close" else "last quote"
    return f"{quote['symbol']} {label}: {quote['price']} · {quote['as_of']}"


# ---------------------------------------------------------------------------
# Corrections
# ---------------------------------------------------------------------------

#: Corrections shown on the front page.
CORRECTIONS_LIMIT = 3


def recent_corrections(rows: Iterable[Dict[str, Any]], *,
                       limit: int = CORRECTIONS_LIMIT) -> List[Dict[str, Any]]:
    """The newest filed corrections across the network, newest first.

    *rows* are ``engine.corrections.load_corrections`` records with
    ``show_name``, ``show_page`` and ``post_url`` added by the caller. Each
    keeps its full text: a correction is never shortened.
    """
    out = [r for r in rows if isinstance(r, dict) and _parse_day(r.get("date"))
           and (r.get("text") or "").strip()]
    out.sort(key=lambda r: (str(r["date"]), int(r.get("episode") or 0)), reverse=True)
    for r in out:
        r["date_label"] = date_label(_parse_day(r["date"]))
    return out[:limit]


# ---------------------------------------------------------------------------
# Today's schedule
# ---------------------------------------------------------------------------


def todays_schedule(now: dt.datetime) -> List[Dict[str, str]]:
    """When the day's surfaces go out, from the constants that time them.

    Read from ``engine.daily_edition`` (the edition's release gate) and
    ``engine.release_schedule`` (newsletters, YouTube Shorts and long-form),
    so a schedule change there moves this copy too. Each row carries the
    instant (``iso``) for the build's Eastern date so the page script can mark
    what has already gone out.
    """
    from engine import daily_edition as _edition
    from engine import release_schedule as _rs

    day = _aware(now).astimezone(EASTERN).date()

    def _at(wall: dt.time) -> dt.datetime:
        return dt.datetime.combine(day, wall, tzinfo=EASTERN)

    def _row(label: str, detail: str, wall: dt.time, lead: str = "From") -> Dict[str, str]:
        t = _at(wall)
        return {"when": f"{lead} {_clock(t)} ET", "time": f"{_clock(t)} ET",
                "label": label, "detail": detail,
                "iso": t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}

    edition = dt.time(*_edition.RELEASE_EASTERN)
    short_gap = int(_rs.SHORT_SPACING.total_seconds() // 60)
    return [
        _row("Nerra Daily", "The day's English shows in one episode, hosted by Mira.", edition),
        _row("Newsletters", "Each show's daily email.", _rs.NEWSLETTER_SLOT, lead="At"),
        _row("Shorts", f"Each show's hook Short on YouTube, one every {short_gap} minutes.",
             _rs.SHORT_FIRST),
        _row("Full episodes on YouTube", "The first wave of long-form videos.",
             _rs.LONG_FIRST_WAVE),
        _row("Evening wave", "The rest of the long-form videos.", _rs.LONG_SECOND_WAVE),
    ]


def schedule_is_clean(rows: Sequence[Dict[str, str]]) -> bool:
    """The rows are in time order (a sanity gate before rendering)."""
    isos = [r["iso"] for r in rows]
    return bool(isos) and isos == sorted(isos)
