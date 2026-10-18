#!/usr/bin/env python3
"""Start the separate video job (Oct 18 2026).

The audio job (run-show.yml) writes ``digests/<dir>/.video_pending_<date>.json``
and hands the episode's video to ``.github/workflows/render-video.yml``:

  dispatch  run by the audio job after its final push: starts the video job
            for one show, once the handoff marker is on main.
  sweep     run on a schedule: starts the video job for a handoff whose
            dispatch never arrived (a failed API call, an audio commit that
            reached main through a recovery PR). A handoff that already has a
            video run of any outcome is left alone — a failed run may have
            uploaded before it died, so it is re-run by a person, never by the
            sweep (a second upload would be a duplicate public video).

Both need GH_TOKEN (actions: write) and GITHUB_REPOSITORY.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WORKFLOW = "render-video.yml"
PENDING_PREFIX = ".video_pending_"
DONE_PREFIX = ".video_done_"
#: A handoff younger than this is the audio job's own dispatch in flight.
SWEEP_MIN_AGE_MINUTES = 20
#: Handoffs older than this are reported, never started (a day-old video
#: would publish into tomorrow's release slots).
SWEEP_MAX_AGE_HOURS = 30
SWEEP_MAX_DISPATCHES = 8
API = "https://api.github.com"


def run_title(show: str, date: str) -> str:
    """The video run's name — render-video.yml's ``run-name`` builds the same."""
    return f"Render video: {show} {date}"


def _session() -> requests.Session:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    s = requests.Session()
    s.headers.update({"Accept": "application/vnd.github+json",
                      "X-GitHub-Api-Version": "2022-11-28"})
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


def _repo() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repo:
        raise SystemExit("GITHUB_REPOSITORY is not set")
    return repo


def show_output_dir(show: str) -> Path:
    from engine.config import load_config
    cfg = load_config(ROOT / "shows" / f"{show}.yaml")
    return ROOT / cfg.episode.output_dir


def pending_marker(show: str, date: str) -> Path:
    return show_output_dir(show) / f"{PENDING_PREFIX}{date.replace('-', '')}.json"


def marker_on_main(session, repo: str, marker: Path) -> bool:
    rel = marker.relative_to(ROOT).as_posix()
    r = session.get(f"{API}/repos/{repo}/contents/{rel}", params={"ref": "main"},
                    timeout=30)
    return r.status_code == 200


def dispatch(session, repo: str, show: str, date: str, attempts: int = 3) -> bool:
    url = f"{API}/repos/{repo}/actions/workflows/{WORKFLOW}/dispatches"
    body = {"ref": "main", "inputs": {"show": show, "date": date}}
    for attempt in range(1, attempts + 1):
        try:
            r = session.post(url, json=body, timeout=30)
            if r.status_code in (201, 204):
                print(f"Started the video job for {show} {date}")
                return True
            print(f"::warning::Video job dispatch for {show} {date} answered "
                  f"{r.status_code}: {r.text[:200]}")
        except requests.RequestException as exc:
            print(f"::warning::Video job dispatch for {show} {date} failed: {exc}")
        time.sleep(5 * attempt)
    return False


def existing_run_titles(session, repo: str) -> set:
    """Titles of the recent video runs, any status."""
    r = session.get(f"{API}/repos/{repo}/actions/workflows/{WORKFLOW}/runs",
                    params={"per_page": 100, "event": "workflow_dispatch"}, timeout=30)
    r.raise_for_status()
    return {str(run.get("display_title") or "") for run in r.json().get("workflow_runs", [])}


#: The audio job's dispatch starts only a handoff it wrote itself.
DISPATCH_MAX_AGE_HOURS = 6


def cmd_dispatch(args) -> int:
    if args.date:
        dates = [args.date]
    else:
        dates = [date for show, date, age in due_handoffs()
                 if show == args.show and age <= DISPATCH_MAX_AGE_HOURS * 60]
    if not dates:
        print(f"No new video handoff for {args.show}: nothing to start.")
        return 0
    return max(_dispatch_one(args.show, date) for date in dates)


def _dispatch_one(show: str, date: str) -> int:
    marker = pending_marker(show, date)
    if not marker.exists():
        print(f"No video handoff for {show} {date}: nothing to start.")
        return 0
    session, repo = _session(), _repo()
    # The video job checks out main. A handoff that only reached a recovery
    # branch is picked up by the sweep once that branch is merged.
    for _ in range(6):
        if marker_on_main(session, repo, marker):
            break
        time.sleep(10)
    else:
        print(f"::warning::The video handoff for {show} {date} is not on main "
              "yet; the scheduled sweep starts the video job once it is.")
        return 0
    return 0 if dispatch(session, repo, show, date) else 1


def due_handoffs(now: dt.datetime | None = None) -> list:
    """(show, date, age_minutes) for every pending handoff with no done marker."""
    now = now or dt.datetime.now(dt.timezone.utc)
    out = []
    for path in sorted((ROOT / "digests").glob(f"*/{PENDING_PREFIX}*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        show, date = str(data.get("show") or ""), str(data.get("date") or "")
        if not show or not date:
            continue
        if (path.parent / f"{DONE_PREFIX}{date.replace('-', '')}.json").exists():
            continue
        try:
            created = dt.datetime.fromisoformat(str(data.get("created_at")))
        except ValueError:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=dt.timezone.utc)
        out.append((show, date, (now - created).total_seconds() / 60.0))
    return out


def plan_sweep(handoffs, titles, *, max_dispatches: int = SWEEP_MAX_DISPATCHES):
    """Which handoffs the sweep starts, and which it reports as stale."""
    start, stale = [], []
    for show, date, age in handoffs:
        if run_title(show, date) in titles:
            continue
        if age > SWEEP_MAX_AGE_HOURS * 60:
            stale.append((show, date))
        elif age >= SWEEP_MIN_AGE_MINUTES and len(start) < max_dispatches:
            start.append((show, date))
    return start, stale


def cmd_sweep(_args) -> int:
    handoffs = due_handoffs()
    if not handoffs:
        print("No video handoffs waiting.")
        return 0
    session, repo = _session(), _repo()
    start, stale = plan_sweep(handoffs, existing_run_titles(session, repo))
    for show, date in stale:
        print(f"::warning::The video handoff for {show} {date} never started and is "
              f"over {SWEEP_MAX_AGE_HOURS} h old; start it by hand if it should still "
              "publish (Actions → Render Episode Video).")
    failed = 0
    for show, date in start:
        print(f"::notice::Starting the video job for {show} {date} (its dispatch "
              "never arrived)")
        failed += 0 if dispatch(session, repo, show, date) else 1
    return 1 if failed else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dispatch", help="start the video job for one show")
    d.add_argument("--show", required=True)
    d.add_argument("--date", default=None, help="YYYY-MM-DD (default today, UTC)")
    sub.add_parser("sweep", help="start any handoff whose dispatch never arrived")
    args = parser.parse_args(argv)
    return cmd_dispatch(args) if args.cmd == "dispatch" else cmd_sweep(args)


if __name__ == "__main__":
    sys.exit(main())
