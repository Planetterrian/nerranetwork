"""Every show page has a job that re-renders it.

A show page is a COMMITTED artifact. Templates are source; the HTML the site
serves is written by a job and committed, so a template change reaches a
page only when some job re-renders it. For fifteen shows that job is
run-show's per-show finalize, and for Nerra Daily it is that show's own
build.

**The interview shows had no such job.** The Age of AI and Nerra Voices
bypass ``run_show.py``; their only re-render was
``pipelines/voices/publish_episode.py``, which fires when a new interview
publishes. So on 2026-09-22, hours after a template change shipped, the Age
of AI page and all six interview posts were still serving the previous
chrome — and would have kept serving it until the next guest aired.

That is the third instance of one class: a show that bypasses ``run_show``
gets none of ``run_show``'s surface. The first cost Age of AI its OP3
prefix, so its downloads were invisible; the second left
``newsletter.enabled`` and ``youtube.enabled`` read by nothing for months.
Each was fixed for the one symptom that surfaced it. These guards fix the
class: a show with no owner fails CI, whatever the symptom would have been.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

import generate_html as G
from scripts.list_unowned_show_pages import (
    committed_paths,
    run_show_slugs,
    scheduled_owners,
    unowned_slugs,
)

ROOT = Path(__file__).resolve().parent.parent
NIGHTLY = ROOT / ".github" / "workflows" / "nightly-maintenance.yml"


def _nightly_text() -> str:
    return NIGHTLY.read_text(encoding="utf-8")


def _nightly_add_paths() -> set:
    """The pathspecs the nightly commit step stages.

    Read from the rendered YAML, not by grepping the file, so a pathspec
    that only appears inside a comment cannot satisfy the guard.
    """
    data = yaml.safe_load(_nightly_text())
    found = set()
    for job in data.get("jobs", {}).values():
        for step in job.get("steps", []) or []:
            with_ = step.get("with") or {}
            raw = with_.get("add-paths")
            if raw:
                found.update(
                    line.strip() for line in str(raw).splitlines() if line.strip())
    return found


class TestEveryShowPageHasAnOwner:
    """The property the three instances of this class all violated."""

    def test_no_show_page_is_unowned_and_unrefreshed(self):
        owners = scheduled_owners()
        nightly = _nightly_text()
        for slug in G.NETWORK_SHOWS:
            if slug in owners:
                continue
            assert "scripts/list_unowned_show_pages.py" in nightly, (
                f"{slug} has no scheduled job that re-renders its page, and "
                "the nightly refresh that would cover it is gone — a "
                "template change can no longer reach that page at all")

    def test_the_nightly_step_regenerates_what_the_script_names(self):
        nightly = _nightly_text()
        assert "list_unowned_show_pages.py" in nightly
        # It must actually rebuild each one, not merely list them.
        assert re.search(
            r'generate_html\.py --show "\$slug" --blogs', nightly), (
            "the nightly names the unowned shows but never rebuilds them")

    def test_every_unowned_page_is_also_committed(self):
        """Rebuilt and not staged is the silent-drop class: the work runs
        every night and is thrown away. It cost youtube_channel_history four
        runs and six shows' memory trackers a month of nights."""
        staged = _nightly_add_paths()
        for slug in unowned_slugs():
            for path in committed_paths(slug):
                assert path in staged, (
                    f"{slug} is regenerated nightly but {path!r} is not in "
                    "the commit step's add-paths, so the rebuild is "
                    "discarded every night")

    def test_no_stale_pathspec_outlives_its_show(self):
        """A show that gains an owner should lose its nightly pathspec, or
        the list grows a line nobody can explain."""
        staged = _nightly_add_paths()
        expected = {p for slug in unowned_slugs() for p in committed_paths(slug)}
        orphans = {
            p for p in staged
            if (p.startswith("blog/") and p.endswith("/**")
                and p not in expected)
        }
        assert not orphans, (
            f"nightly stages {sorted(orphans)} for shows that now have their "
            "own regeneration owner")


class TestTheDerivationIsReal:
    """A hardcoded list here would drift the first time a cadence moved."""

    def test_the_run_show_set_is_read_from_the_workflow(self):
        slugs = run_show_slugs()
        assert len(slugs) >= 10, "CRON_MAP parsed to almost nothing"
        assert slugs <= set(G.NETWORK_SHOWS), (
            f"CRON_MAP names shows the registry does not: "
            f"{sorted(slugs - set(G.NETWORK_SHOWS))}")

    def test_a_scheduled_show_is_never_called_unowned(self):
        assert not (set(unowned_slugs()) & run_show_slugs())

    def test_nerra_daily_counts_as_owned_because_its_build_rebuilds_it(self):
        """Not an exception for its own sake: build_daily_edition runs the
        same generate_html command before committing the page."""
        assert "nerra_daily" in scheduled_owners()
        build = (ROOT / "scripts" / "build_daily_edition.py").read_text(
            encoding="utf-8")
        assert '"generate_html.py", "--show", spec.slug, "--blogs"' in build

    def test_committed_paths_point_at_real_artifacts(self):
        for slug in unowned_slugs():
            page, *_rest = committed_paths(slug)
            assert (ROOT / page).exists(), f"{slug} names a page that is not there"

    def test_it_says_nothing_when_every_show_is_owned(self, monkeypatch):
        """A detector that cannot return empty is not a detector."""
        import scripts.list_unowned_show_pages as mod

        monkeypatch.setattr(
            mod, "scheduled_owners", lambda: {s: "x" for s in G.NETWORK_SHOWS})
        assert mod.unowned_slugs() == []


class TestTheInterviewShowsAreTheOnesThisWasWrittenFor:
    """Scored against the two shows whose pages went stale, so the guard is
    anchored to a real failure rather than to whatever the code does."""

    @pytest.mark.parametrize("slug", ["age_of_ai", "nerra_voices"])
    def test_they_have_no_scheduled_publish_job(self, slug):
        assert slug not in run_show_slugs()

    @pytest.mark.parametrize("slug", ["age_of_ai", "nerra_voices"])
    def test_and_so_the_nightly_covers_them(self, slug):
        assert slug in unowned_slugs()
        staged = _nightly_add_paths()
        assert G.NETWORK_SHOWS[slug]["show_page"] in staged
