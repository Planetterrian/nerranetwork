#!/usr/bin/env python3
"""Generate and publish the Modern Investing monthly recap episode.

Fires on the last trading day of each month via
``.github/workflows/monthly-report.yml``. The script:
  1. Calls ``engine.synthesizer.synthesize_monthly_report`` for the base
     month-in-review markdown (reused — do not rewrite).
  2. Appends MIT-specific sections derived from
     ``digests/modern_investing/investment_tracker.json`` and
     ``digests/modern_investing/lessons_learned.json``:
       - Monthly NASDAQ Showdown
       - Sector Heatmap
       - Rules Adopted / Rules Retired
       - Areas of Improvement for Next Month
  3. Generates a podcast-ready script via the LLM using
     ``shows/prompts/modern_investing_monthly_podcast.txt``.
  4. Runs TTS via ``engine.tts.speak`` (same voice as the daily show).
  5. Mixes intro/outro music via ``engine.audio.mix_with_music``.
  6. Uploads to R2 via ``engine.storage.upload_episode``.
  7. Appends an episode entry to the existing daily RSS feed via
     ``engine.publisher.update_rss_feed`` (same guid_prefix so
     subscribers pick it up in the same app).
  8. Records the episode in
     ``digests/modern_investing/monthly_episodes.json``.

Usage::

    python scripts/run_monthly_mit_episode.py             # previous calendar month
    python scripts/run_monthly_mit_episode.py --month 3 --year 2026
    python scripts/run_monthly_mit_episode.py --dry-run   # markdown + script only
    python scripts/run_monthly_mit_episode.py --require-last-trading-day
                                            # exit 0 silently unless today qualifies
"""

from __future__ import annotations

import argparse
import calendar
import datetime as _dt
import json
import logging
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.config import load_config  # noqa: E402
from engine.synthesizer import synthesize_monthly_report  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("monthly_mit")

SHOW_SLUG = "modern_investing"
TRACKER_FILENAME = "investment_tracker.json"
LESSONS_FILENAME = "lessons_learned.json"
MONTHLY_EPISODES_FILENAME = "monthly_episodes.json"

# US market holidays that fall on a Mon-Fri and push the "last trading
# day" back. Covers 2026 explicitly; add more years as the show runs.
# Source: NYSE holiday calendar.
_US_MARKET_HOLIDAYS_MONDAY_FRIDAY = {
    _dt.date(2026, 1, 1),   # New Year's Day (Thu)
    _dt.date(2026, 1, 19),  # MLK Day (Mon)
    _dt.date(2026, 2, 16),  # Presidents' Day (Mon)
    _dt.date(2026, 4, 3),   # Good Friday
    _dt.date(2026, 5, 25),  # Memorial Day (Mon)
    _dt.date(2026, 6, 19),  # Juneteenth (Fri)
    _dt.date(2026, 7, 3),   # Independence Day observed (Fri)
    _dt.date(2026, 9, 7),   # Labor Day (Mon)
    _dt.date(2026, 11, 26), # Thanksgiving (Thu)
    _dt.date(2026, 12, 25), # Christmas (Fri)
    _dt.date(2027, 1, 1),
    _dt.date(2027, 1, 18),
    _dt.date(2027, 2, 15),
    _dt.date(2027, 3, 26),  # Good Friday
    _dt.date(2027, 5, 31),
    _dt.date(2027, 6, 18),
    _dt.date(2027, 7, 5),
    _dt.date(2027, 9, 6),
    _dt.date(2027, 11, 25),
    _dt.date(2027, 12, 24),
}


def is_last_trading_day_of_month(today: _dt.date | None = None) -> bool:
    """Return True if *today* is the last Mon-Fri of its month that is
    NOT a US market holiday. Used as the cron gate in the workflow.
    """
    today = today or _dt.date.today()
    if today.weekday() > 4 or today in _US_MARKET_HOLIDAYS_MONDAY_FRIDAY:
        return False
    last_day = calendar.monthrange(today.year, today.month)[1]
    candidate = _dt.date(today.year, today.month, last_day)
    while candidate.weekday() > 4 or candidate in _US_MARKET_HOLIDAYS_MONDAY_FRIDAY:
        candidate -= _dt.timedelta(days=1)
    return candidate == today


# ---------------------------------------------------------------------------
# MIT-specific section builders
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return {}


def _month_window(month: int, year: int) -> tuple[_dt.date, _dt.date]:
    start = _dt.date(year, month, 1)
    last = calendar.monthrange(year, month)[1]
    return start, _dt.date(year, month, last)


def _filter_trades_for_month(trades: Iterable[dict], month: int, year: int) -> list[dict]:
    start, end = _month_window(month, year)
    out: list[dict] = []
    for t in trades or []:
        d = t.get("date")
        if not isinstance(d, str):
            continue
        try:
            td = _dt.date.fromisoformat(d)
        except ValueError:
            continue
        if start <= td <= end:
            out.append(t)
    return out


def _mean(vals: list[float]) -> float:
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def build_monthly_snapshot(tracker: dict, month: int, year: int) -> dict:
    """Return the month's portfolio vs NASDAQ numbers.

    Reused by both the markdown section and the monthly_snapshots
    entry appended to ``investment_tracker.json``.
    """
    trades = _filter_trades_for_month(tracker.get("trades", []), month, year)
    closed = [t for t in trades if t.get("status") == "closed"]
    wins = [t for t in closed if (t.get("pnl_pct") or 0) > 0]
    pnl_pct_values = [float(t.get("pnl_pct") or 0) for t in closed]
    nasdaq_pct_values = [float(t.get("nasdaq_return_pct") or 0)
                         for t in closed if t.get("nasdaq_return_pct") is not None]
    alpha_values = [float(t.get("alpha_pct") or 0)
                    for t in closed if t.get("alpha_pct") is not None]
    total_pnl = round(sum((t.get("pnl_dollars") or 0) for t in closed), 2)

    return {
        "month": f"{year:04d}-{month:02d}",
        "trades": len(closed),
        "win_rate": round((len(wins) / len(closed)) * 100, 1) if closed else 0.0,
        "portfolio_pct": _mean(pnl_pct_values),
        "nasdaq_pct": _mean(nasdaq_pct_values),
        "alpha_pct": _mean(alpha_values),
        "portfolio_pnl": total_pnl,
    }


def build_sector_heatmap(trades: list[dict]) -> list[tuple[str, int, float, float]]:
    """Return [(sector, count, cumulative_pct, cumulative_pnl)] rows."""
    by_sector: dict[str, list[dict]] = {}
    for t in trades:
        sector = t.get("sector") or "other"
        by_sector.setdefault(sector, []).append(t)
    rows = []
    for sector, items in by_sector.items():
        count = len(items)
        pct = _mean([float(x.get("pnl_pct") or 0) for x in items])
        dollars = round(sum((x.get("pnl_dollars") or 0) for x in items), 2)
        rows.append((sector, count, pct, dollars))
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


def build_mit_sections(tracker: dict, lessons: dict, month: int, year: int) -> str:
    """Return the MIT-specific markdown appended to the base report."""
    snapshot = build_monthly_snapshot(tracker, month, year)
    trades = _filter_trades_for_month(tracker.get("trades", []), month, year)
    closed = [t for t in trades if t.get("status") == "closed"]
    heatmap = build_sector_heatmap(closed)

    entries = (lessons.get("entries") or [])
    start, end = _month_window(month, year)
    adopted = [e for e in entries
               if _parse_date_safe(e.get("date")) and start <= _parse_date_safe(e["date"]) <= end]
    active = [e for e in entries if e.get("status") == "active"]

    # Areas of improvement: pick the rules adopted this month + the two
    # most recent active rules as carry-forward focus.
    carry = [e for e in active if e not in adopted][-2:]

    lines: list[str] = []
    lines.append("")
    lines.append("## Monthly NASDAQ Showdown")
    lines.append("")
    lines.append(
        f"- **Portfolio average per trade:** {snapshot['portfolio_pct']:+.2f}% over {snapshot['trades']} closed trades"
    )
    lines.append(
        f"- **NASDAQ ^IXIC average over same windows:** {snapshot['nasdaq_pct']:+.2f}%"
    )
    alpha_icon = "BEATING" if snapshot["alpha_pct"] >= 0 else "TRAILING"
    lines.append(
        f"- **Monthly alpha:** {snapshot['alpha_pct']:+.2f}% — {alpha_icon} the benchmark"
    )
    lines.append(
        f"- **Cumulative P&L this month:** ${snapshot['portfolio_pnl']:+.2f} "
        f"on $1,000 simulated positions"
    )
    lines.append(
        f"- **Win rate:** {snapshot['win_rate']:.0f}%"
    )
    lines.append("")

    lines.append("## Sector Heatmap")
    lines.append("")
    if heatmap:
        lines.append("| Sector | Trades | Avg return | Cumulative P&L |")
        lines.append("| ------ | ------ | ---------- | -------------- |")
        for sector, count, pct, dollars in heatmap:
            lines.append(f"| {sector} | {count} | {pct:+.2f}% | ${dollars:+.2f} |")
    else:
        lines.append("_No closed trades this month._")
    lines.append("")

    lines.append("## Rules Adopted This Month")
    lines.append("")
    if adopted:
        for e in adopted:
            lines.append(
                f"- **{e.get('id', '?')}** ({e.get('date', '?')}): "
                f"{e.get('observation', '').strip()} "
                f"→ Rule: {e.get('adjustment', '').strip()}"
            )
    else:
        lines.append("_No new rules adopted this month — the show held to the existing playbook._")
    lines.append("")

    retired = [e for e in entries if e.get("status") == "retired"
               and _parse_date_safe(e.get("date")) and start <= _parse_date_safe(e["date"]) <= end]
    lines.append("## Rules Retired This Month")
    lines.append("")
    if retired:
        for e in retired:
            lines.append(f"- **{e.get('id', '?')}**: {e.get('adjustment', '')}")
    else:
        lines.append("_No rules retired this month._")
    lines.append("")

    lines.append("## Areas of Improvement for Next Month")
    lines.append("")
    focus = (adopted + carry)[:3]
    if focus:
        for e in focus:
            lines.append(f"- {e.get('adjustment', '').strip()}")
    else:
        lines.append("- Hold the current playbook; continue tracking NASDAQ alpha weekly.")
    lines.append("")

    return "\n".join(lines)


def _parse_date_safe(value: Any) -> _dt.date | None:
    if not isinstance(value, str):
        return None
    try:
        return _dt.date.fromisoformat(value)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Podcast script generation
# ---------------------------------------------------------------------------

def generate_monthly_podcast_script(report_md: str, config, *, month: int, year: int) -> str | None:
    """Ask the LLM to turn the monthly report markdown into a podcast script."""
    from engine.generator import _call_grok, load_prompt

    prompt_path = PROJECT_ROOT / "shows" / "prompts" / "modern_investing_monthly_podcast.txt"
    template = load_prompt(str(prompt_path), template_vars={
        "month_name": calendar.month_name[month],
        "year": str(year),
        "host_name": config.publishing.host_name or "Patrick",
        "report": report_md,
    })

    model = getattr(config.llm, "synth_model", "") or config.llm.model
    max_tokens = getattr(config.llm, "synth_max_tokens", 0) or 8000
    temperature = getattr(config.llm, "synth_temperature", 0.0) or 0.5

    try:
        text, _meta = _call_grok(
            prompt=template,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=(
                "You are the host of Modern Investing Techniques delivering "
                "the monthly recap episode. Be honest, specific, and accountable."
            ),
        )
        return text
    except Exception as exc:
        logger.error("Monthly podcast-script generation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Episode ledger
# ---------------------------------------------------------------------------

def _append_monthly_ledger(ledger_path: Path, entry: dict) -> None:
    data = _load_json(ledger_path) or {
        "metadata": {"schema_version": 1, "last_updated": _dt.date.today().isoformat()},
        "entries": [],
    }
    data.setdefault("entries", []).append(entry)
    data.setdefault("metadata", {})["last_updated"] = _dt.date.today().isoformat()
    ledger_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _next_monthly_episode_num(tracker: dict, existing_ledger: dict, daily_rss_path: Path) -> int:
    """Return the next episode number for the monthly recap.

    Continues the existing RSS numbering so the monthly episode slots
    into the same feed order as the daily show.
    """
    # Pull the highest episode number from the RSS feed if present.
    max_rss = 0
    if daily_rss_path.exists():
        try:
            text = daily_rss_path.read_text(encoding="utf-8")
            import re
            for m in re.finditer(r"itunes:episode>\s*(\d+)", text):
                max_rss = max(max_rss, int(m.group(1)))
        except Exception:
            pass
    max_tracker = max((t.get("episode_num") or 0) for t in (tracker.get("trades") or [])) if tracker.get("trades") else 0
    max_ledger = 0
    for e in (existing_ledger.get("entries") or []):
        max_ledger = max(max_ledger, int(e.get("episode_num") or 0))
    return max(max_rss, max_tracker, max_ledger) + 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _previous_month_window(today: _dt.date) -> tuple[int, int]:
    first = today.replace(day=1)
    prev_last = first - _dt.timedelta(days=1)
    return prev_last.month, prev_last.year


def run(
    *,
    month: int,
    year: int,
    dry_run: bool = False,
    skip_audio: bool = False,
    skip_rss: bool = False,
) -> int:
    config = load_config(str(PROJECT_ROOT / "shows" / f"{SHOW_SLUG}.yaml"))
    mit_dir = PROJECT_ROOT / "digests" / SHOW_SLUG

    tracker = _load_json(mit_dir / TRACKER_FILENAME)
    lessons = _load_json(mit_dir / LESSONS_FILENAME)

    logger.info("Generating monthly recap for %d-%02d …", year, month)

    base_md = synthesize_monthly_report(SHOW_SLUG, month, year)
    if not base_md:
        base_md = (
            f"# State of Modern Investing Techniques — "
            f"{calendar.month_name[month]} {year}\n\n"
            f"_Insufficient daily episodes in the content lake for this month._\n"
        )
        logger.warning("No content-lake data; using minimal base report.")

    mit_sections = build_mit_sections(tracker, lessons, month, year)
    full_md = base_md.rstrip() + "\n\n" + mit_sections

    out_md = mit_dir / f"Modern_Investing_Monthly_{year:04d}-{month:02d}.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(full_md, encoding="utf-8")
    logger.info("Wrote monthly markdown: %s (%d bytes)", out_md, len(full_md))

    # Snapshot the month into the tracker's monthly_snapshots[] list.
    snapshot = build_monthly_snapshot(tracker, month, year)
    tracker.setdefault("monthly_snapshots", [])
    existing_months = {s.get("month") for s in tracker["monthly_snapshots"]}
    if snapshot["month"] not in existing_months:
        tracker["monthly_snapshots"].append(snapshot)
        (mit_dir / TRACKER_FILENAME).write_text(
            json.dumps(tracker, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info("Appended monthly snapshot %s to tracker", snapshot["month"])

    if dry_run:
        logger.info("--dry-run: skipping LLM script, TTS, mix, upload, RSS.")
        return 0

    # Podcast script
    script = generate_monthly_podcast_script(full_md, config, month=month, year=year)
    if not script:
        logger.error("Monthly podcast-script generation failed — aborting.")
        return 1

    script_path = mit_dir / f"Modern_Investing_Monthly_{year:04d}-{month:02d}_script.txt"
    script_path.write_text(script, encoding="utf-8")
    logger.info("Wrote monthly podcast script: %s (%d chars)", script_path, len(script))

    if skip_audio:
        logger.info("--skip-audio: skipping TTS + mix + upload + RSS.")
        return 0

    # TTS -> audio mix -> upload -> RSS update
    from engine.tts import speak
    from engine.audio import mix_with_music, get_audio_duration
    from engine.storage import upload_episode
    from engine.publisher import (
        update_rss_feed,
        apply_op3_prefix,
    )

    today = _dt.date.today()
    existing_ledger = _load_json(mit_dir / MONTHLY_EPISODES_FILENAME)
    episode_num = _next_monthly_episode_num(tracker, existing_ledger, PROJECT_ROOT / config.publishing.rss_file)
    mp3_basename = f"Modern_Investing_Pod_Ep{episode_num:03d}_{today:%Y%m%d}_MONTHLY"
    voice_mp3 = mit_dir / f"{mp3_basename}_voice.mp3"
    final_mp3 = mit_dir / f"{mp3_basename}.mp3"

    speak(
        text=script,
        output_path=voice_mp3,
        voice_id=config.tts.voice_id,
        model=config.tts.model,
        stability=config.tts.stability,
        similarity_boost=config.tts.similarity_boost,
        style=config.tts.style,
        use_speaker_boost=config.tts.use_speaker_boost,
        max_chars=config.tts.max_chars,
    )
    logger.info("Voice synthesised: %s", voice_mp3)

    music_file = (PROJECT_ROOT / config.audio.music_file) if config.audio.music_file else None
    if music_file and music_file.exists():
        mix_with_music(
            voice_path=voice_mp3,
            music_path=music_file,
            output_path=final_mp3,
            intro_duration=config.audio.intro_duration,
            overlap_duration=config.audio.overlap_duration,
            fade_duration=config.audio.fade_duration,
            outro_duration=config.audio.outro_duration,
            intro_volume=config.audio.intro_volume,
            overlap_volume=config.audio.overlap_volume,
            fade_volume=config.audio.fade_volume,
            outro_volume=config.audio.outro_volume,
            voice_intro_delay=config.audio.voice_intro_delay,
            outro_crossfade=config.audio.outro_crossfade,
        )
        logger.info("Mixed with music: %s", final_mp3)
    else:
        final_mp3 = voice_mp3
        logger.info("No music file configured — voice-only monthly episode")

    audio_duration = get_audio_duration(final_mp3)

    # Upload to R2
    r2_audio_url = upload_episode(final_mp3, config)
    if r2_audio_url:
        logger.info("R2 audio URL: %s", r2_audio_url)
    feed_audio_url = r2_audio_url
    if config.analytics.enabled and feed_audio_url:
        feed_audio_url = apply_op3_prefix(feed_audio_url, config.analytics.prefix_url)

    if skip_rss:
        logger.info("--skip-rss: leaving RSS feed untouched.")
    else:
        rss_path = PROJECT_ROOT / config.publishing.rss_file
        episode_title = (
            f"Modern Investing Techniques — Monthly Recap "
            f"({calendar.month_name[month]} {year})"
        )
        episode_desc = (
            f"The {calendar.month_name[month]} {year} recap. "
            f"Portfolio return, NASDAQ alpha, sector heatmap, rules "
            f"adopted and retired, and the improvement focus for next "
            f"month. Simulated trades only — this is not financial advice."
        )
        update_rss_feed(
            rss_path=rss_path,
            episode_num=episode_num,
            episode_title=episode_title,
            episode_description=episode_desc,
            episode_date=today,
            mp3_filename=final_mp3.name,
            mp3_duration=audio_duration,
            mp3_path=final_mp3,
            base_url=config.publishing.base_url,
            audio_subdir=config.publishing.audio_subdir,
            channel_title=config.publishing.rss_title,
            channel_link=config.publishing.rss_link,
            channel_description=config.publishing.rss_description,
            channel_language=config.publishing.rss_language,
            channel_author=config.publishing.rss_author,
            channel_email=config.publishing.rss_email,
            channel_image=config.publishing.rss_image,
            channel_category=config.publishing.rss_category,
            guid_prefix=config.publishing.guid_prefix,
            audio_url=feed_audio_url,
        )
        logger.info("RSS feed updated: %s (ep %d)", rss_path, episode_num)

    # Ledger
    _append_monthly_ledger(mit_dir / MONTHLY_EPISODES_FILENAME, {
        "episode_num": episode_num,
        "month": f"{year:04d}-{month:02d}",
        "date": today.isoformat(),
        "markdown_path": str(out_md.relative_to(PROJECT_ROOT)),
        "script_path": str(script_path.relative_to(PROJECT_ROOT)),
        "audio_path": str(final_mp3.relative_to(PROJECT_ROOT)),
        "audio_url": feed_audio_url,
        "snapshot": snapshot,
    })
    logger.info("Recorded monthly episode in monthly_episodes.json")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the MIT monthly recap pipeline.")
    today = _dt.date.today()
    default_month, default_year = _previous_month_window(today)
    parser.add_argument("--month", type=int, default=default_month)
    parser.add_argument("--year", type=int, default=default_year)
    parser.add_argument("--dry-run", action="store_true",
                        help="Write the markdown only; skip LLM/TTS/R2/RSS.")
    parser.add_argument("--skip-audio", action="store_true",
                        help="Skip TTS + mix + upload + RSS; keeps script + snapshot.")
    parser.add_argument("--skip-rss", action="store_true",
                        help="Skip RSS feed update (still writes audio + uploads).")
    parser.add_argument("--require-last-trading-day", action="store_true",
                        help="Exit 0 silently if today is not the last trading day of the month.")
    args = parser.parse_args()

    if args.require_last_trading_day and not is_last_trading_day_of_month():
        logger.info("Not the last trading day of the month — exiting without work.")
        return 0

    return run(
        month=args.month,
        year=args.year,
        dry_run=args.dry_run,
        skip_audio=args.skip_audio,
        skip_rss=args.skip_rss,
    )


if __name__ == "__main__":
    sys.exit(main())
