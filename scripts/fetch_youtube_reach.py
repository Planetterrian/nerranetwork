#!/usr/bin/env python3
"""Thumbnail impressions and click-through, read nightly (Nov 14 2026).

Browse ("SUBSCRIBER" in the Analytics traffic sources: home and the
subscriptions feed) is the EN channel's largest source, 45-55% of its views
every day in the Nov 14 review, and what decides how much of it a video gets
is whether its thumbnail and title are clicked when shown. Nothing in the
repo could see that: ``fetch_youtube_analytics.py`` reads the Analytics API,
which has no impressions metric ("Studio-only"), so every title or thumbnail
change the network made was judged on views alone, which mixes how often a
video was SHOWN with how often it was CHOSEN.

The YouTube **Reporting** API carries both in its reach report
(:data:`REACH_REPORT_TYPE`: ``video_thumbnail_impressions`` and
``video_thumbnail_impressions_ctr`` per video per day). It is a bulk API: a
reporting JOB is created once per channel, YouTube then writes one CSV a day
(the first about two days after the job exists, never backfilled), and this
script downloads the ones it has not read yet into ``api/youtube_reach.json``.

Honesty rules, as everywhere in the analytics files:

* a video with no row is ABSENT, never 0 impressions;
* a channel whose read failed keeps its previous days and says so in
  ``channels.<ch>.status``; a failed night never shrinks the file;
* a click-through rate is printed only over at least :data:`CTR_MIN_IMPRESSIONS`
  impressions, null below it.

The consumer is the YouTube review (the Nov 29 readout of
``long-form-rundown-subscribe-2026-11-08`` and every title or thumbnail
change after it); the summary block is shaped for that read.

Same credentials and scope as the Analytics fetch
(``yt-analytics.readonly``); a clean no-op without them.

Usage::

    python scripts/fetch_youtube_reach.py              # read and write
    python scripts/fetch_youtube_reach.py --dry-run    # read, print, no write
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import io
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch_youtube_reach")

SCHEMA_VERSION = 1
OUT_PATH = Path("api/youtube_reach.json")
STATS_PATH = Path("api/youtube_stats.json")
CHANNELS = ("en", "ru", "fr")
#: The Reporting API's reach report (thumbnail impressions + CTR per video
#: per day). Checked against ``reportTypes.list`` before a job is created.
REACH_REPORT_TYPE = "channel_reach_basic_a1"
JOB_NAME = "nerra-reach"
#: Daily rows kept per video.
KEEP_DAYS = 60
#: Reports downloaded per channel per night (a new job has none; a missed
#: week of nights catches up in one run).
MAX_REPORTS_PER_RUN = 30
#: A click-through rate is printed only over at least this many impressions.
CTR_MIN_IMPRESSIONS = 100
#: The summary reads each video's first week, so every video is compared at
#: the same age (the Sep 12 rule: never against a rolling peak).
SUMMARY_AGE_DAYS = 7
SUMMARY_WINDOW_DAYS = 28

_IMPR_COL = "video_thumbnail_impressions"
_CTR_COL = "video_thumbnail_impressions_ctr"


# --------------------------------------------------------------------------
# Pure parts (tested without the API)
# --------------------------------------------------------------------------

def _report_day(value: str) -> Optional[str]:
    """``20261112`` or ``2026-11-12`` → ``2026-11-12``; None when unreadable."""
    v = (value or "").strip()
    try:
        if len(v) == 8 and v.isdigit():
            return _dt.date(int(v[:4]), int(v[4:6]), int(v[6:])).isoformat()
        return _dt.date.fromisoformat(v[:10]).isoformat()
    except ValueError:
        return None


def parse_reach_csv(text: str) -> Optional[Dict[str, Dict[str, List[float]]]]:
    """``{video_id: {day: [impressions, clicks]}}`` from one report CSV.

    Rows are split by subscribed status, country and so on, so a video's
    impressions are SUMMED and its clicks are the impression-weighted CTR.
    ``None`` when the header lacks the columns this file is built on (the
    report changed shape: say so, write nothing from it).
    """
    reader = csv.DictReader(io.StringIO(text or ""))
    fields = set(reader.fieldnames or [])
    if not {"date", "video_id", _IMPR_COL} <= fields:
        logger.warning("reach report header has no %s/date/video_id: %s",
                       _IMPR_COL, sorted(fields))
        return None
    rows: List[Tuple[str, str, float, Optional[float]]] = []
    for r in reader:
        day = _report_day(r.get("date", ""))
        vid = (r.get("video_id") or "").strip()
        if not day or not vid:
            continue
        try:
            impr = float(r.get(_IMPR_COL) or 0)
        except ValueError:
            continue
        ctr: Optional[float]
        try:
            ctr = float(r[_CTR_COL]) if r.get(_CTR_COL) not in (None, "") else None
        except ValueError:
            ctr = None
        rows.append((vid, day, impr, ctr))
    # The CTR column is a ratio; read a file whose values run past 1 as
    # percent rather than guess per row.
    percent = any(c is not None and c > 1.0 for _v, _d, _i, c in rows)
    out: Dict[str, Dict[str, List[float]]] = {}
    for vid, day, impr, ctr in rows:
        cell = out.setdefault(vid, {}).setdefault(day, [0.0, 0.0])
        cell[0] += impr
        if ctr is not None:
            cell[1] += impr * (ctr / 100.0 if percent else ctr)
    for days in out.values():
        for cell in days.values():
            cell[0] = int(round(cell[0]))
            cell[1] = round(cell[1], 2)
    return out


def merge_days(existing: Dict[str, dict], channel: str,
               parsed: Dict[str, Dict[str, List[float]]]) -> None:
    """Fold one report into ``existing`` (``videos`` block) in place.

    A day a report carries REPLACES that day's cell (a re-issued report is
    YouTube's correction); other days are untouched.
    """
    for vid, days in parsed.items():
        entry = existing.setdefault(vid, {"channel": channel, "days": {}})
        entry["channel"] = entry.get("channel") or channel
        entry.setdefault("days", {}).update(days)


def prune(videos: Dict[str, dict], today: _dt.date, keep_days: int = KEEP_DAYS) -> None:
    cutoff = (today - _dt.timedelta(days=keep_days)).isoformat()
    for vid in list(videos):
        days = videos[vid].get("days", {})
        for d in [d for d in days if d < cutoff]:
            del days[d]
        if not days:
            del videos[vid]


def _ctr(impressions: float, clicks: float) -> Optional[float]:
    if impressions < CTR_MIN_IMPRESSIONS:
        return None
    return round(100.0 * clicks / impressions, 2)


def _video_meta(stats: Optional[dict]) -> Dict[str, dict]:
    meta: Dict[str, dict] = {}
    for slug, block in ((stats or {}).get("shows") or {}).items():
        for v in block.get("videos") or []:
            vid = v.get("video_id")
            if vid:
                meta[vid] = {"show": slug, "kind": v.get("kind"),
                             "channel": v.get("channel"),
                             "published": v.get("published")}
    return meta


def summarise(videos: Dict[str, dict], stats: Optional[dict],
              today: _dt.date) -> dict:
    """First-week impressions and CTR by channel, kind and show.

    Only videos published in the last :data:`SUMMARY_WINDOW_DAYS` whose
    first :data:`SUMMARY_AGE_DAYS` days have passed and whose reach rows
    reach the end of that week are counted, so every video is read at the
    same age. Each group carries ``videos`` (the count read); its CTR is
    null under :data:`CTR_MIN_IMPRESSIONS`.
    """
    meta = _video_meta(stats)
    since = (today - _dt.timedelta(days=SUMMARY_WINDOW_DAYS)).isoformat()
    groups: Dict[Tuple[str, str, str], List[float]] = {}
    for vid, entry in videos.items():
        m = meta.get(vid)
        if not m or not m.get("published") or m["published"] < since:
            continue
        try:
            pub = _dt.date.fromisoformat(m["published"][:10])
        except ValueError:
            continue
        end = pub + _dt.timedelta(days=SUMMARY_AGE_DAYS - 1)
        if end >= today:
            continue
        days = entry.get("days", {})
        if not days or max(days) < end.isoformat():
            continue
        impr = clicks = 0.0
        for d, (i, c) in days.items():
            if pub.isoformat() <= d <= end.isoformat():
                impr += i
                clicks += c
        ch = m.get("channel") or entry.get("channel") or "en"
        kind = m.get("kind") or "?"
        for key in ((ch, kind, "_all"), (ch, kind, m["show"])):
            g = groups.setdefault(key, [0, 0.0, 0.0])
            g[0] += 1
            g[1] += impr
            g[2] += clicks
    out: Dict[str, dict] = {}
    for (ch, kind, show), (n, impr, clicks) in sorted(groups.items()):
        out.setdefault(ch, {}).setdefault(kind, {})[show] = {
            "videos": int(n),
            "impressions_week1": int(round(impr)),
            "impressions_week1_per_video": int(round(impr / n)) if n else None,
            "ctr_week1_pct": _ctr(impr, clicks),
        }
    return {"age_days": SUMMARY_AGE_DAYS, "window_days": SUMMARY_WINDOW_DAYS,
            "ctr_min_impressions": CTR_MIN_IMPRESSIONS, "groups": out}


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("schema_version") == SCHEMA_VERSION:
            return data
    except (OSError, ValueError):
        pass
    return {"schema_version": SCHEMA_VERSION, "channels": {}, "videos": {}}


# --------------------------------------------------------------------------
# The API (one channel at a time)
# --------------------------------------------------------------------------

def _service(credentials):
    try:
        from googleapiclient.discovery import build
    except Exception as exc:  # pragma: no cover - import guard
        logger.info("googleapiclient unavailable (%s) — skipping", exc)
        return None
    try:
        return build("youtubereporting", "v1", credentials=credentials,
                     cache_discovery=False)
    except Exception as exc:
        logger.warning("Could not build the reporting service: %s", exc)
        return None


def ensure_job(service) -> Tuple[Optional[str], str]:
    """``(job_id, status)``: the channel's reach job, created when absent.

    status is ``ok`` (a job exists), ``job_created`` (made tonight: the first
    report comes in about two days) or ``unavailable`` (YouTube does not
    offer the report type to this channel).
    """
    jobs = service.jobs().list().execute().get("jobs") or []
    for job in jobs:
        if job.get("reportTypeId") == REACH_REPORT_TYPE:
            return job.get("id"), "ok"
    types = service.reportTypes().list().execute().get("reportTypes") or []
    if REACH_REPORT_TYPE not in {t.get("id") for t in types}:
        logger.warning("report type %s not offered (have: %s)", REACH_REPORT_TYPE,
                       sorted(t.get("id") for t in types)[:40])
        return None, "unavailable"
    job = service.jobs().create(
        body={"reportTypeId": REACH_REPORT_TYPE, "name": JOB_NAME}).execute()
    logger.info("created reach job %s; the first report arrives in ~48 h", job.get("id"))
    return job.get("id"), "job_created"


def list_reports(service, job_id: str) -> List[dict]:
    reports: List[dict] = []
    token = None
    while True:
        kwargs = {"jobId": job_id}
        if token:
            kwargs["pageToken"] = token
        resp = service.jobs().reports().list(**kwargs).execute()
        reports.extend(resp.get("reports") or [])
        token = resp.get("nextPageToken")
        if not token:
            return reports


def download(service, url: str) -> str:
    from googleapiclient.http import MediaIoBaseDownload

    request = service.media().download_media(resourceName="")
    request.uri = url
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _status, done = downloader.next_chunk()
    return buf.getvalue().decode("utf-8")


def pending_reports(reports: Iterable[dict], read_ids: Iterable[str]) -> List[dict]:
    """Reports not read yet, oldest first, at most :data:`MAX_REPORTS_PER_RUN`."""
    seen = set(read_ids)
    todo = [r for r in reports if r.get("id") and r["id"] not in seen
            and r.get("downloadUrl")]
    todo.sort(key=lambda r: (r.get("startTime") or "", r.get("createTime") or ""))
    return todo[:MAX_REPORTS_PER_RUN]


def read_channel(channel: str, credentials, data: dict) -> None:
    """Read one channel into ``data`` in place; its status says what happened."""
    block = data["channels"].setdefault(channel, {})
    block.pop("error", None)
    service = _service(credentials)
    if service is None:
        block["status"] = "error"
        block["error"] = "no reporting client"
        return
    try:
        job_id, status = ensure_job(service)
        block["status"] = status
        if not job_id:
            return
        if block.get("job_id") != job_id:
            block["job_id"] = job_id
            block["read_report_ids"] = []
        reports = list_reports(service, job_id)
        todo = pending_reports(reports, block.get("read_report_ids") or [])
        read = list(block.get("read_report_ids") or [])
        for rep in todo:
            parsed = parse_reach_csv(download(service, rep["downloadUrl"]))
            if parsed is None:
                block["status"] = "report_shape_changed"
                break
            merge_days(data["videos"], channel, parsed)
            read.append(rep["id"])
            day = _report_day(rep.get("startTime") or "")
            if day and day > (block.get("last_report_day") or ""):
                block["last_report_day"] = day
        # Report ids are kept for KEEP_DAYS-ish nights; older ones can never
        # reappear in a listing (YouTube keeps 60 days of reports).
        block["read_report_ids"] = read[-(KEEP_DAYS + MAX_REPORTS_PER_RUN):]
        block["reports_read_tonight"] = len(todo)
    except Exception as exc:
        block["status"] = "error"
        block["error"] = str(exc)[:200]
        logger.warning("reach read failed on %s: %s", channel, exc)


def run(out_path: Path = OUT_PATH, *, dry_run: bool = False,
        today: Optional[_dt.date] = None) -> Optional[dict]:
    try:
        from engine.youtube import get_channel_credentials_from_env
    except Exception as exc:
        logger.info("engine.youtube unavailable (%s) — skipping", exc)
        return None
    today = today or _dt.date.today()
    data = load(out_path)
    any_creds = False
    for channel in CHANNELS:
        creds = get_channel_credentials_from_env(channel)
        if creds is None:
            logger.info("No credentials for channel=%s — skipped", channel)
            continue
        any_creds = True
        read_channel(channel, creds, data)
    if not any_creds:
        return None
    prune(data["videos"], today)
    stats = None
    try:
        stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    data["schema_version"] = SCHEMA_VERSION
    data["report_type"] = REACH_REPORT_TYPE
    data["updated"] = today.isoformat()
    data["summary"] = summarise(data["videos"], stats, today)
    if dry_run:
        print(json.dumps({k: v for k, v in data.items() if k != "videos"}, indent=2))
        return data
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8")
    logger.info("wrote %s (%d videos)", out_path, len(data["videos"]))
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--out", default=str(OUT_PATH))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(Path(args.out), dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
