"""Drift guards for the Offshore North round-1 fixes (18 September 2026).

The operator's twelve-item list on Ep005 (14 Sep 2026) — the core
problems only; host voice and the incident-driven Fleet rewrite come
later. Items 1, 2 and 6 had landed on 14 Sep (full text, Scott's Notes,
last-known position); this pass adds:

* fix 5 — the campaign's own channels are read on a 30-day window
  (``window_hours`` per source); the wider press keeps the ladder;
* fix 8 — nothing older than ten days is news: the page's own publish
  date (read during the full-text fetch) or the feed date drops an
  article before the prompt sees it (``stale_article_days``), campaign
  feeds exempt;
* fixes 3, 4, 7, 9-12 — prompt rules: no timestamp sentences, no
  background block or labels, a race-state check, Plain Sailing capped
  at 300 words / one point once / never the lead's subject, class names
  from the official race site (six classes: ULTIM, Ocean Fifty, IMOCA,
  Class40, Vintage Multi, Vintage Mono).
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.config import load_config  # noqa: E402

_SHOW_YAML = _ROOT / "shows" / "offshore_north.yaml"


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _digest():
    return _read("shows/prompts/offshore_north_digest.txt")


def _podcast():
    return _read("shows/prompts/offshore_north_podcast.txt")


def _system():
    return _read("shows/prompts/offshore_north_system.txt")


# ---------------------------------------------------------------------------
# Fix 5 — 30-day campaign window
# ---------------------------------------------------------------------------

class TestCampaignWindow:
    def test_every_campaign_feed_reads_thirty_days(self):
        cfg = load_config(str(_SHOW_YAML))
        campaign = [s for s in cfg.sources if s.freshness_report]
        assert campaign, "the campaign feeds are the flagged ones"
        for src in campaign:
            assert src.window_hours >= 30 * 24, src.label
        # and ONLY the campaign feeds — the wider press keeps the ladder
        for src in cfg.sources:
            if not src.freshness_report:
                assert src.window_hours == 0, src.label

    def test_no_other_show_uses_window_hours(self):
        offenders = []
        for path in sorted((_ROOT / "shows").glob("*.yaml")):
            if path.stem.startswith("_") or path.stem == "offshore_north":
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for src in (data.get("sources") or []) if isinstance(data, dict) else []:
                if isinstance(src, dict) and src.get("window_hours"):
                    offenders.append(path.stem)
        assert not offenders, f"per-feed windows are opt-in: {offenders}"

    def test_dataclass_default_is_off(self):
        from engine.config import SourceConfig

        assert SourceConfig(url="https://x").window_hours == 0

    def test_run_show_passes_the_window_to_the_fetcher(self):
        src = _read("run_show.py")
        assert '"window_hours": int(getattr(s, "window_hours", 0) or 0)' in src
        fetcher = _read("engine/fetcher.py")
        assert "url_cutoffs" in fetcher and 'fd.get("window_hours")' in fetcher

    def test_fetcher_widens_only_the_flagged_feed(self, monkeypatch):
        """The per-feed cutoff is min(ladder cutoff, now - window_hours):
        a feed may look further back than the ladder, never less far."""
        import engine.fetcher as f

        seen = {}

        def fake_single(url, cutoff_time, *args, **kwargs):
            seen[url] = cutoff_time
            return None

        monkeypatch.setattr(f, "_fetch_single_feed", fake_single)
        f.fetch_rss_articles(
            [{"url": "https://team/feed", "label": "Team", "window_hours": 720},
             {"url": "https://press/feed", "label": "Press"}],
            cutoff_hours=168,
        )
        now = dt.datetime.now(dt.timezone.utc)
        assert (now - seen["https://team/feed"]).days >= 29
        assert (now - seen["https://press/feed"]).days <= 7


# ---------------------------------------------------------------------------
# Fix 8 — nothing older than ten days is news
# ---------------------------------------------------------------------------

class TestStaleArticleGate:
    def test_show_sets_ten_days_and_others_are_off(self):
        cfg = load_config(str(_SHOW_YAML))
        assert cfg.stale_article_days == 10
        from engine.config import ShowConfig

        assert ShowConfig().stale_article_days == 0
        offenders = []
        for path in sorted((_ROOT / "shows").glob("*.yaml")):
            if path.stem.startswith("_") or path.stem == "offshore_north":
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict) and data.get("stale_article_days"):
                offenders.append(path.stem)
        assert not offenders, offenders

    def test_page_publish_date_is_read_from_meta_jsonld_and_time(self):
        from engine.article_text import extract_published_date

        meta = '<html><head><meta property="article:published_time" content="2026-09-02T10:15:00+02:00"></head></html>'
        assert extract_published_date(meta).date() == dt.date(2026, 9, 2)
        jsonld = '<html><script type="application/ld+json">{"@type":"Article","datePublished":"2026-09-01T18:00:00Z"}</script></html>'
        assert extract_published_date(jsonld).date() == dt.date(2026, 9, 1)
        timetag = '<html><body><time datetime="2026-08-30">30 Aug</time></body></html>'
        assert extract_published_date(timetag).date() == dt.date(2026, 8, 30)
        assert extract_published_date("<html><body><p>no date</p></body></html>") is None

    def test_page_date_outranks_the_feed_date_and_campaign_is_exempt(self):
        """The Ep005 case: a 2 September start story re-surfaced by Google
        News with a 12 September feed date is dropped on the 14th; a
        three-week-old Scott's Notes post is kept."""
        from engine.article_text import drop_stale_articles

        now = dt.datetime(2026, 9, 14, tzinfo=dt.timezone.utc)
        arts = [
            {"title": "Malizia first across the line as the race begins", "source_name": "team-malizia.com",
             "published_date": "2026-09-12T00:00:00+00:00", "page_published_date": "2026-09-02T10:00:00+00:00"},
            {"title": "Golden Globe sets sail", "source_name": "Sailorz", "published_date": "2026-09-06T00:00:00+00:00"},
            {"title": "Thank you, Canada", "source_name": "Canada Ocean Racing — Scott's Notes",
             "published_date": "2026-08-20T00:00:00+00:00"},
            {"title": "undated", "source_name": "Sail-World"},
        ]
        kept, dropped = drop_stale_articles(
            arts, max_age_days=10, now=now, exempt_sources=["Canada Ocean Racing — Scott's Notes"],
        )
        assert [a["title"] for a in dropped] == ["Malizia first across the line as the race begins"]
        assert {a["title"] for a in kept} == {"Golden Globe sets sail", "Thank you, Canada", "undated"}

    def test_gate_is_a_noop_when_off(self):
        from engine.article_text import drop_stale_articles

        arts = [{"title": "old", "published_date": "2020-01-01T00:00:00+00:00"}]
        kept, dropped = drop_stale_articles(arts, max_age_days=0)
        assert kept == arts and dropped == []

    def test_enrichment_records_the_page_date(self):
        from engine.article_text import enrich_articles_with_full_text

        arts = [{"title": "t", "description": "short", "url": "https://x.example/p", "source_name": "S"}]
        html = ('<html><head><meta property="article:published_time" content="2026-09-02T10:00:00Z"></head>'
                '<body><article><p>' + ("A real sentence about the race start. " * 20) + '</p></article></body></html>')
        enrich_articles_with_full_text(arts, max_articles=1, fetch=lambda u: (200, html))
        assert arts[0]["page_published_date"].startswith("2026-09-02")
        assert "race start" in arts[0]["full_text"]

    def test_run_show_wires_the_gate_after_enrichment(self):
        src = _read("run_show.py")
        assert 'getattr(config, "stale_article_days", 0)' in src
        assert "drop_stale_articles(" in src
        assert 'metrics.record("articles_dropped_stale"' in src
        # exemption = the feeds that carry their own window
        assert 'int(getattr(src, "window_hours", 0) or 0) > 0' in src


# ---------------------------------------------------------------------------
# Fixes 3, 4, 7 — the Canadian Boat and accuracy rules
# ---------------------------------------------------------------------------

class TestCanadianBoatRules:
    def test_timestamp_sentences_are_banned_everywhere(self):
        d, p, s = _digest(), _podcast(), _system()
        assert 'NEVER WRITE A "LAST UPDATED" SENTENCE' in d
        assert "no new posts inside the seven-day window" in d and "no new posts inside the seven-day window" in p
        assert "NEVER REPORT A TIMESTAMP INSTEAD OF CONTENT" in p
        assert "never report a timestamp instead of content" in s
        # the old instruction that PRODUCED the timestamps is gone
        for src in (d, p, s):
            assert "the date of each channel's most recent post" not in src
            assert "date and subject of each channel's most recent post" not in src

    def test_background_block_and_labels_are_gone(self):
        d, p = _digest(), _podcast()
        assert "**Standing item:**" not in d
        assert "**Background (writer-only" not in d
        assert "NO BACKGROUND BLOCK, NO LABELS" in d
        assert "NO LABELS, NO BACKGROUND RECITAL" in p

    def test_thirty_day_window_is_explained_to_the_writer(self):
        assert "THE CAMPAIGN WINDOW IS THIRTY DAYS" in _digest()
        assert "thirty-day window" in _podcast()
        assert "thirty-day window" in _system()

    def test_race_state_check(self):
        assert "RACE STATE CHECK" in _digest()
        assert "NOT STARTED, is RUNNING, or has FINISHED" in _digest()
        assert "Confirm a race's state before writing about it" in _system()

    def test_ten_day_rule_in_the_prompts(self):
        assert "NOTHING OLDER THAN TEN DAYS IS NEWS" in _digest()
        assert "Nothing older than about ten days is news" in _system()


# ---------------------------------------------------------------------------
# Fixes 9-12 — Plain Sailing
# ---------------------------------------------------------------------------

class TestPlainSailingRound1:
    def test_hard_cap_300_in_both_prompts(self):
        assert "HARD CAP 300 WORDS" in _digest()
        assert "HARD CAP 300 SPOKEN WORDS" in _podcast()
        assert "never exceeds 300 spoken words" in _podcast()
        assert "450" not in _podcast().split("[Plain Sailing]")[1].split("[The Countdown]")[0]

    def test_no_longer_a_length_lever(self):
        assert "THIS IS THE LENGTH LEVER" not in _podcast()
        assert "NOT a length lever" in _podcast()
        assert "the show's length lever" not in _digest()

    def test_one_point_once_and_never_the_lead(self):
        d, p = _digest(), _podcast()
        assert "ONE POINT, MADE ONCE" in d and "ONE POINT, MADE ONCE" in p
        assert "NEVER THE SAME SUBJECT AS THE LEAD STORY" in d and "NEVER THE SAME SUBJECT AS THE LEAD STORY" in p

    def test_class_names_from_the_official_site(self):
        d = _digest()
        assert "CLASS AND CATEGORY NAMES COME FROM THE OFFICIAL RACE SITE" in d
        guide = _read("shows/prompts/offshore_north_field_guide.txt")
        for cls in ("ULTIM", "Ocean Fifty", "IMOCA", "Class40", "Vintage Multi", "Vintage Mono"):
            assert cls in guide, cls
        assert 'there is no "Class 50"' in guide
        assert "Rhum Mono" in guide  # the former name is mapped, not invented
        facts = _read("shows/prompts/offshore_north_standing_facts.txt")
        assert "listed the Route du Rhum classes wrongly" in facts
