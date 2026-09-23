#!/usr/bin/env python3
"""Which show pages nothing regenerates on a schedule.

A show page on this site is a COMMITTED artifact. It is re-rendered by the
job that publishes that show, and by nothing else — so a template change
reaches a page only when that show next publishes. For the fifteen shows in
run-show.yml's CRON_MAP that is within a day, and Nerra Daily's own build
runs the same command after each edition.

**The interview shows have no such job.** The Age of AI and Nerra Voices
bypass ``run_show.py`` entirely; their only re-render is
``pipelines/voices/publish_episode.py``, which fires when a new interview
publishes. No guest, no re-render. On 2026-09-22 that left the Age of AI
page and all six interview posts serving the previous chrome with no path
to the current one — the same class as the missing OP3 prefix and the
unread ``newsletter.enabled`` flag, both of which were also "a show that
bypasses run_show gets none of run_show's surface".

So the nightly job refreshes exactly the pages nobody owns. This script
names them, rather than the workflow hardcoding two slugs: a show
scaffolded tomorrow that skips run_show joins the list by existing, and
``tests/test_page_regen_ownership_2026_09_22.py`` fails if the workflow's
commit list stops covering it.

Prints one slug per line, or with ``--paths`` the committed artifacts each
one owns. Exit 0 with no output when every show has an owner.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

_CRON_MAP_RE = re.compile(r"CRON_MAP = \{(.*?)\n              \}", re.S)
# Slugs may carry digits ("mag7"): [a-z_]+ read MAG 7 as unscheduled.
_SLOT_RE = re.compile(r'"[^"]+":\s*\("([a-z0-9_]+)"')

#: Shows whose page is re-rendered by a scheduled job OTHER than run-show.
#: Nerra Daily is assembled by its own workflow, and
#: ``scripts/build_daily_edition.py`` runs ``generate_html.py --show
#: nerra_daily --blogs`` before committing the page — so it is owned.
_OTHER_SCHEDULED_OWNERS = {"nerra_daily": ".github/workflows/nerra-daily.yml"}


def run_show_slugs() -> set:
    """The slugs run-show.yml schedules, read from the workflow itself.

    Read rather than listed, because CRON_MAP is the production source of
    truth for what publishes daily and a second copy of it here would drift
    the first time a show's cadence moved.
    """
    workflow = (REPO_ROOT / ".github" / "workflows" / "run-show.yml").read_text(
        encoding="utf-8")
    block = _CRON_MAP_RE.search(workflow)
    if not block:
        raise SystemExit(
            "could not find CRON_MAP in run-show.yml — the schedule gate "
            "moved, and this script cannot tell owned pages from unowned "
            "ones without it")
    return set(_SLOT_RE.findall(block.group(1)))


def scheduled_owners() -> dict:
    """slug -> the file whose scheduled job re-renders that show's page."""
    owners = {slug: ".github/workflows/run-show.yml" for slug in run_show_slugs()}
    owners.update(_OTHER_SCHEDULED_OWNERS)
    return owners


def unowned_slugs() -> list:
    """Registry shows with no scheduled re-render, in registry order."""
    from generate_html import NETWORK_SHOWS

    owners = scheduled_owners()
    return [slug for slug in NETWORK_SHOWS if slug not in owners]


def committed_paths(slug: str) -> list:
    """Every committed artifact ``generate_html.py --show <slug> --blogs``
    writes: the show page, its summaries page, its Story Tracker page where
    the show has one, and its blog directory.

    Returned as repo-relative pathspecs so the nightly commit step and its
    guard read the same strings. The Story Tracker is here because it is
    easy to forget and free to include: rebuilt-but-unstaged is the silent
    drop that cost ``youtube_channel_history.json`` four runs and six shows'
    memory trackers a month of nights, and Age of AI has a 67 KB one.
    """
    from engine import show_memory
    from generate_html import NETWORK_SHOWS

    cfg = NETWORK_SHOWS[slug]
    page = cfg["show_page"]
    paths = [page]
    summaries = cfg.get("summaries_page")
    if summaries:
        paths.append(summaries)
    # Mirrors generate_narrative_page's own condition and filename. A
    # pathspec matching nothing is harmless; a missing one is not.
    if show_memory.get_config(slug) is not None:
        paths.append(page.replace(".html", "-narrative.html"))
    paths.append(f"blog/{slug}/**")
    return paths


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths", action="store_true",
        help="print the committed artifacts instead of the slugs")
    args = parser.parse_args(argv)

    for slug in unowned_slugs():
        if args.paths:
            for path in committed_paths(slug):
                print(path)
        else:
            print(slug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
