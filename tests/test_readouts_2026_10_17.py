"""Oct 17 2026 — the code actions from six experiment readouts
(docs/reviews/readouts_2026_10_17.md).

* freshness-dating-2026-09-30 (PARTIAL): one Source older than three days
  shipped — Planetterrian 2026-10-07 cited
  ``bjo.bmj.com/content/early/2026/09/18/…`` under a fresh feed date. The
  stale gate read the page and feed dates and never the URL path, which
  only the fetch-window filter checked. ``article_age_days`` now reads the
  path date, older-only, from the one owner of article dates.
* story-clusters-2026-10-01 (PARTIAL): Tesla told a clustered story as
  more than one digest item on 12 of its first 14 post-merge episodes —
  the criteria's "majority" branch. The rule moves into the one-shot
  structural regeneration on the show that missed (opt-in
  ``story_clusters_regen``), and a retry that retells MORE is rejected.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import story_clusters as sc  # noqa: E402
from engine.article_dates import url_path_date  # noqa: E402
from engine.article_text import article_age_days, drop_stale_articles  # noqa: E402

BMJ = "https://bjo.bmj.com/content/early/2026/09/18/bjo-2026-330339"
RUN = dt.datetime(2026, 10, 7, 9, 0, tzinfo=dt.timezone.utc)


class TestUrlPathDate:
    def test_a_day_path_is_the_end_of_that_day(self):
        assert url_path_date(BMJ) == dt.datetime(2026, 9, 18, 23, 59, 59, tzinfo=dt.timezone.utc)

    def test_a_month_path_is_the_last_second_of_the_month(self):
        got = url_path_date("https://example.com/2026/09/some-story/")
        assert got == dt.datetime(2026, 9, 30, 23, 59, 59, tzinfo=dt.timezone.utc)
        got = url_path_date("https://example.com/2025/12/x")
        assert got == dt.datetime(2025, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc)

    def test_no_path_date_is_none(self):
        for url in ("", "https://example.com/story", "https://x.com/a/status/2099993953219105119",
                    "https://example.com/2026/13/01/x"):
            assert url_path_date(url) is None, url

    def test_the_fetch_filter_reads_the_same_date(self):
        from engine.fetcher import _url_path_date
        for url in (BMJ, "https://example.com/2026/09/x", "https://example.com/x", ""):
            assert _url_path_date(url) == url_path_date(url), url


class TestStaleGateReadsThePath:
    def test_the_bmj_online_first_paper_is_nineteen_days_old(self):
        art = {"title": "Statins and glaucoma", "url": BMJ,
               "published_date": "2026-10-06T00:00:00+00:00"}
        age = article_age_days(art, RUN)
        assert age is not None and 18 < age < 19

    def test_the_gate_drops_it_on_a_three_day_show(self):
        art = {"title": "Statins and glaucoma", "url": BMJ,
               "published_date": "2026-10-06T00:00:00+00:00"}
        kept, dropped = drop_stale_articles([art], max_age_days=3, now=RUN)
        assert dropped == [art] and kept == []

    def test_a_path_date_never_makes_an_article_younger(self):
        art = {"title": "x", "url": "https://example.com/2026/10/06/story",
               "published_date": "2026-09-01T00:00:00+00:00"}
        assert article_age_days(art, RUN) > 30

    def test_todays_path_is_fresh(self):
        art = {"title": "x", "url": "https://example.com/2026/10/07/story",
               "published_date": "2026-10-07T06:00:00+00:00"}
        kept, dropped = drop_stale_articles([art], max_age_days=3, now=RUN)
        assert kept == [art] and dropped == []

    def test_an_exempt_article_is_still_kept(self):
        art = {"title": "x", "url": BMJ, "exempt_stale": True}
        kept, _ = drop_stale_articles([art], max_age_days=3, now=RUN)
        assert kept == [art]


CREDIT = [
    {"title": "Tesla Locks in $30 Billion in New Credit as It Scales Up Optimus, Cybercab and Joint Solar Plan"},
    {"title": "Tesla Lines Up $30 Billion Credit Backup Ahead Of Heavy Capex Years"},
    {"title": "Tesla Secures $30 Billion in Credit Lines to Fund AI, Solar and Chip Ambitions"},
    {"title": "Tesla Patents 'Electric Fan Car' Weeks Before Roadster Reveal"},
]
RETOLD = ("### Top News\n\n1. **Tesla secures $30 billion in credit lines for AI and solar**\n"
          "body. Source: https://a\n\n2. **Tesla lines up $30 billion credit backup ahead of capex**\n"
          "body. Source: https://b\n\n3. **Electric fan car patent lands before Roadster reveal**\nbody\n")
TOLD_ONCE = ("### Top News\n\n1. **Tesla secures $30 billion in credit lines for AI, solar and chips**\n"
             "body. Source: https://a\n\n2. **Electric fan car patent lands before Roadster reveal**\nbody\n")


class TestRetoldClusters:
    def test_retold_clusters_names_the_items(self):
        got = sc.retold_clusters(RETOLD, CREDIT, [[0, 1, 2]])
        assert len(got) == 1 and len(got[0]) == 2
        assert got[0][0].startswith("Tesla secures $30 billion")

    def test_the_count_is_the_list_length(self):
        assert sc.cluster_retold_in_digest(RETOLD, CREDIT, [[0, 1, 2]]) == 1
        assert sc.cluster_retold_in_digest(TOLD_ONCE, CREDIT, [[0, 1, 2]]) == 0
        assert sc.retold_clusters(TOLD_ONCE, CREDIT, [[0, 1, 2]]) == []

    def test_an_out_of_range_index_is_ignored(self):
        assert sc.retold_clusters(RETOLD, CREDIT, [[0, 1, 99]]) != []

    def test_the_note_names_items_and_asks_for_one(self):
        note = sc.retold_cluster_note(sc.retold_clusters(RETOLD, CREDIT, [[0, 1, 2]]))
        assert "ONE item" in note and "Source URL" in note
        assert "Tesla secures $30 billion" in note
        assert sc.retold_cluster_note([]) == ""


class TestClusterRegenWiring:
    def test_only_tesla_opts_in(self):
        from engine.config import load_config
        on = []
        for path in sorted((ROOT / "shows").glob("*.yaml")):
            if path.name.startswith("_"):
                continue
            try:
                cfg = load_config(path)
            except Exception:  # noqa: BLE001 — registry-only YAMLs
                continue
            if getattr(cfg, "story_clusters_regen", False):
                on.append(path.stem)
                assert cfg.story_clusters is True, path.stem
        assert on == ["tesla"]

    def test_run_show_rides_the_structural_regeneration(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        i_flag = src.index('getattr(config, "story_clusters_regen", False)')
        i_gate = src.index("if (_val_factory or _hook_too_long or _lint_findings) and not is_deep_dive:")
        assert i_flag < i_gate, "the finding must join _lint_findings before the gate reads it"
        assert '"story_cluster_retold", retold_cluster_note(_retold_clusters)' in src
        assert 'metrics.record("story_clusters_retold_after_retry", after)' in src
        assert "_cluster_regen and not _new_lints and _cluster_retry_worse(" in src
        assert 'metrics.record("story_clusters_retold_in_digest", _retold)' in src

    def test_a_retry_that_retells_more_is_worse(self):
        import importlib
        rs = importlib.import_module("run_show")

        class _M:
            def __init__(self):
                self.rec = {}

            def record(self, k, v):
                self.rec[k] = v
        m = _M()
        before = sc.retold_clusters(TOLD_ONCE, CREDIT, [[0, 1, 2]])
        assert rs._cluster_retry_worse(RETOLD, CREDIT, [[0, 1, 2]], before, m) is True
        assert m.rec["story_clusters_retold_after_retry"] == 1
        before = sc.retold_clusters(RETOLD, CREDIT, [[0, 1, 2]])
        assert rs._cluster_retry_worse(TOLD_ONCE, CREDIT, [[0, 1, 2]], before, m) is False
        assert m.rec["story_clusters_retold_after_retry"] == 0
