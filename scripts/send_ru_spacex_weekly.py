#!/usr/bin/env python3
"""Send «Хроника SpaceX» — the Russian weekly letter the RU pilot promises.

The landing page at ``ru/spacex.html`` asks for an email address in
exchange for exactly one thing: a Russian letter every Sunday with the
week's episodes and the next launch window. This script is what keeps
that promise. Without it the pilot's only asset would be a form that
collects addresses and never writes to them, which is worse than no
form at all.

Everything it needs already exists in the repo — no new data source:

  * ``digests/spacex/summaries_spacex.json`` -> each episode's Russian
    title, description and audio URL (produced by the multilingual
    stage; only episodes that actually have a ``translations.ru`` track
    are eligible, so the letter can never link English audio).
  * ``api/spacex_launches.json`` -> the next launch window (the same
    file the site's data hub and the landing page's countdown read).

Audience: the Buttondown tag ``ru-spacex`` and nothing else. These
subscribers are deliberately NOT on the English "SpaceX Daily" tag —
see ``workers/gallery/src/handlers.ts``.

Safety rails, in the order they fire:

  1. ``BUTTONDOWN_API_KEY`` unset -> clean no-op, exit 0 (the repo-wide
     convention for optional integrations).
  2. No Russian episodes in the window -> no send. An empty letter
     spends the one piece of attention this pilot has.
  3. A send already recorded for this ISO week -> refused, so a retried
     workflow run cannot mail the list twice.

Usage::

    python scripts/send_ru_spacex_weekly.py --dry-run   # print, send nothing
    python scripts/send_ru_spacex_weekly.py             # send
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
log = logging.getLogger("ru_spacex_weekly")

SHOW_SLUG = "spacex"
CAPTURE_TAG = "ru-spacex"
LANDING_URL = "https://nerranetwork.com/ru/spacex.html"
FEED_URL = "https://nerranetwork.com/spacex_podcast.ru.rss"
YOUTUBE_URL = "https://www.youtube.com/@NerraRU"
SEND_MARKER = _ROOT / "digests" / SHOW_SLUG / "_ru_weekly_lastsend.txt"

_AI_DISCLOSURE_RU = (
    "Раскрытие: выпуски готовит Патрик, озвучка создаётся ИИ-синтезом "
    "голоса. Отбор материалов и анализ — человеческая работа "
    "по первоисточникам."
)

_RU_MONTHS_GEN = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def _ru_date(value: str) -> str:
    """``2026-07-30`` -> ``30 июля``. Falls back to the raw string."""
    try:
        d = dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return value or ""
    return f"{d.day} {_RU_MONTHS_GEN[d.month - 1]}"


def _tagged(url: str, placement: str) -> str:
    """UTM-tag an outbound link so the newsletter's clicks land in the
    same funnel report as YouTube's (see ``engine.funnel``)."""
    from engine import funnel

    return funnel.funnel_link(
        url,
        source=funnel.SOURCE_NEWSLETTER,
        medium=funnel.MEDIUM_EMAIL,
        # Built, not hand-written: the funnel rule (CLAUDE.md) exists
        # because literal campaign strings drift silently when the
        # format changes. ep000 = the weekly letter, not one episode.
        campaign=funnel.campaign_id(
            SHOW_SLUG, 0, channel="ru", kind="email"),
        placement=placement,
    )


def recent_ru_episodes(days: int = 7,
                       today: Optional[dt.date] = None) -> List[Dict]:
    """Episodes from the last *days* that have a Russian audio track."""
    today = today or dt.date.today()
    # days-1: `cutoff <= when <= today` is inclusive on both ends, so a
    # plain `days` span covered 8 calendar days and re-included last
    # Sunday's episode in this Sunday's letter.
    cutoff = today - dt.timedelta(days=max(0, days - 1))
    path = _ROOT / "digests" / SHOW_SLUG / f"summaries_{SHOW_SLUG}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        log.warning("cannot read %s: %s", path, exc)
        return []

    out: List[Dict] = []
    for rec in (payload.get("summaries") or []):
        try:
            when = dt.date.fromisoformat(rec.get("date", ""))
        except (TypeError, ValueError):
            continue
        if not (cutoff <= when <= today):
            continue
        track = ((rec.get("translations") or {}).get("ru") or {})
        audio = (track.get("audio_url") or "").strip()
        if not audio:
            continue
        out.append({
            "episode": rec.get("episode_num"),
            "date": rec.get("date", ""),
            "title": (track.get("title") or "").strip(),
            "description": (track.get("description") or "").strip(),
            "audio_url": audio,
        })
    out.sort(key=lambda e: (e["date"], e["episode"] or 0))
    return out


def next_launch() -> Optional[Dict]:
    """The next scheduled launch, or ``None`` when the cache is stale."""
    path = _ROOT / "api" / "spacex_launches.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    nxt = (data or {}).get("next") or None
    if not isinstance(nxt, dict) or not nxt.get("net"):
        return None
    try:
        when = dt.datetime.fromisoformat(
            str(nxt["net"]).replace("Z", "+00:00"))
    except ValueError:
        return None
    # A launch window already in the past is stale data, not news.
    if when < dt.datetime.now(dt.timezone.utc):
        return None
    return {
        "name": nxt.get("name") or nxt.get("mission") or "Запуск SpaceX",
        "when": when,
        "location": nxt.get("location") or "",
        "orbit": nxt.get("orbit") or "",
        "status": nxt.get("status_name") or nxt.get("status") or "",
    }


def build_subject(episodes: List[Dict],
                  week_ending: dt.date) -> str:
    """Lead with the week's strongest line, not with the brand.

    A subject that says only "Хроника SpaceX · 30 июля" tells a reader
    nothing they don't already know; the last episode's Russian hook
    tells them whether to open it.
    """
    lead = ""
    if episodes:
        lead = (episodes[-1].get("description")
                or episodes[-1].get("title") or "").strip()
    # One limit module owns every title cut in this repo (CLAUDE.md).
    from engine.titles import clip_words, NEWSLETTER_SUBJECT_MAX

    brand = " · Хроника SpaceX 🚀"
    if not lead:
        return f"Хроника SpaceX · {_ru_date(week_ending.isoformat())} 🚀"
    body = clip_words(lead, max(20, NEWSLETTER_SUBJECT_MAX - len(brand)))
    return f"{body}{brand}"


def build_body(episodes: List[Dict], launch: Optional[Dict],
               week_ending: dt.date) -> str:
    """Compose the Russian markdown body Buttondown will render."""
    lines: List[str] = []
    lines.append(
        f"**Хроника SpaceX** — неделя по {_ru_date(week_ending.isoformat())}"
    )
    lines.append("")
    lines.append(
        f"Главное за семь дней: {len(episodes)} "
        f"{'выпуск' if len(episodes) == 1 else 'выпуска' if len(episodes) < 5 else 'выпусков'}"
        " на русском, окно следующего запуска и ссылки на аудио."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Что было на неделе")
    lines.append("")
    for ep in episodes:
        headline = ep["description"] or ep["title"] or f"Выпуск {ep['episode']}"
        lines.append(
            f"**{_ru_date(ep['date'])} · Выпуск {ep['episode']}**  \n"
            f"{headline}  \n"
            f"[Слушать]({ep['audio_url']})"
        )
        lines.append("")

    if launch:
        when = launch["when"].astimezone(dt.timezone.utc)
        where = " · ".join([p for p in (launch["location"], launch["orbit"]) if p])
        lines.append("---")
        lines.append("")
        lines.append("## Следующий запуск")
        lines.append("")
        lines.append(f"**{launch['name']}**  ")
        lines.append(
            f"{when.strftime('%d.%m.%Y %H:%M')} UTC"
            + (f" · {where}" if where else "")
            + (f" · {launch['status']}" if launch["status"] else "")
        )
        lines.append("")
        lines.append(
            "Время окна может сдвинуться — актуальные данные всегда на "
            f"[странице подкаста]({_tagged(LANDING_URL, 'body')})."
        )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Слушать каждый день")
    lines.append("")
    lines.append(
        f"- [Подкаст на русском — RSS для любого приложения]({FEED_URL})"
    )
    lines.append(f"- [YouTube · @NerraRU]({YOUTUBE_URL})")
    lines.append(
        f"- [Все выпуски по-русски]({_tagged(LANDING_URL, 'shownotes')})"
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"_{_AI_DISCLOSURE_RU}_")
    lines.append("")
    lines.append(
        "_Не является инвестиционной рекомендацией. SPCX упоминается "
        "в информационных целях._"
    )
    return "\n".join(lines)


def _already_sent_this_week(week_ending: dt.date) -> bool:
    """True when the marker records a send in the same ISO week.

    Compared by ISO (year, week), not exact date: the marker stores the
    date the letter went out, and a delayed cron / Monday re-dispatch
    lands on a DIFFERENT date in the SAME week — an exact-date compare
    would double-mail the list, which is the one unrecoverable failure
    for a 'one letter a week' promise.
    """
    try:
        recorded = dt.date.fromisoformat(
            SEND_MARKER.read_text(encoding="utf-8").strip()
        )
    except (OSError, ValueError):
        return False
    return recorded.isocalendar()[:2] == week_ending.isocalendar()[:2]


def _record_send(week_ending: dt.date) -> None:
    try:
        SEND_MARKER.parent.mkdir(parents=True, exist_ok=True)
        SEND_MARKER.write_text(week_ending.isoformat() + "\n", encoding="utf-8")
    except OSError as exc:
        log.warning("could not record the send marker: %s", exc)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the composed email, send nothing")
    parser.add_argument("--days", type=int, default=7,
                        help="lookback window in days (default 7)")
    parser.add_argument("--force", action="store_true",
                        help="ignore the same-week send guard")
    args = parser.parse_args(argv)

    today = dt.date.today()
    episodes = recent_ru_episodes(days=args.days, today=today)
    if not episodes:
        log.warning(
            "No Russian episodes in the last %d days — no letter sent. "
            "An empty issue spends the only attention this pilot has.",
            args.days,
        )
        return 0

    launch = next_launch()
    subject = build_subject(episodes, today)
    body = build_body(episodes, launch, today)

    if args.dry_run:
        print("=" * 72)
        print("SUBJECT:", subject)
        print("TAGS:", [CAPTURE_TAG])
        print("=" * 72)
        print(body)
        return 0

    api_key = (os.getenv("BUTTONDOWN_API_KEY") or "").strip()
    if not api_key:
        log.info("BUTTONDOWN_API_KEY unset — skipping (clean no-op)")
        return 0

    if not args.force and _already_sent_this_week(today):
        log.warning("A letter is already recorded for the week ending %s — "
                    "refusing to double-send. Use --force to override.",
                    today.isoformat())
        return 0

    from engine.newsletter import send_newsletter

    email_id = send_newsletter(
        subject,
        body,
        api_key=api_key,
        status="about_to_send",
        tags=[CAPTURE_TAG],
        # Buttondown derives archive slugs from the subject, which is
        # Cyrillic here and comes back percent-escaped — an unreadable
        # public URL. Force an ASCII one (same fix the Russian shows use).
        slug=f"ru-spacex-{today.isoformat()}",
    )
    if not email_id:
        log.error("Buttondown send failed — see the log above")
        return 1
    _record_send(today)
    log.info("Sent «Хроника SpaceX» (%d episode(s), id=%s)",
             len(episodes), email_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
