"""Guards for the Oct 18 2026 24-hour review (shows, distribution, site,
workflows, code). Each test names the episode or surface that failed."""

import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestBoardFlagsSurviveTheHookMerge:
    """PM Ep023-026: the Board's recurrence_exempt / board_venue flags were
    dropped by normalize_hook_articles, so the Oct 17 exemption and the
    venue-mix lint read nothing."""

    def test_flags_are_carried(self):
        from engine.hook_articles import normalize_hook_articles
        out = normalize_hook_articles([{
            "title": "Will X happen?", "url": "https://kalshi.com/m/x",
            "description": "d", "recurrence_exempt": True,
            "board_venue": "Kalshi", "board_new": True, "exempt_stale": True}])
        assert out[0]["recurrence_exempt"] is True
        assert out[0]["board_venue"] == "Kalshi"
        assert out[0]["board_new"] is True

    def test_venue_lint_sees_supplied_venues(self):
        from engine.hook_articles import normalize_hook_articles
        from engine.prediction_board import supplied_board_venues
        arts = normalize_hook_articles([
            {"title": "A?", "url": "https://kalshi.com/a", "board_venue": "Kalshi"},
            {"title": "B?", "url": "https://polymarket.com/b", "board_venue": "Polymarket"}])
        assert supplied_board_venues(arts) == {"Kalshi", "Polymarket"}

    def test_personal_manifold_market_is_not_a_forecast(self):
        from engine.prediction_board import is_personal_market
        assert is_personal_market("Will the poster think all AI hell broke loose in 2026?")
        assert is_personal_market("Will I get a job by December?")
        assert not is_personal_market("Will OpenAI release GPT-6 in 2026?")
        assert not is_personal_market("Will Apple be worth more than Microsoft?")


class TestCoverageFloorSeesEveryItemLayout:
    """Tesla Ep638 counted 0 sourced items against 16 (one-line items) and
    SpaceX Ep134 0 against 13 (numbered items with no blank lines)."""

    def test_committed_flagship_digests_count_their_items(self):
        from engine.claims import item_source_coverage
        tesla = (ROOT / "digests/tesla_shorts_time/Tesla_Shorts_Time_Pod_Ep638_20261018.md").read_text()
        spacex = (ROOT / "digests/spacex/SpaceX_Daily_Ep134_20261018.md").read_text()
        assert item_source_coverage(tesla, [])[0] >= 12
        assert item_source_coverage(spacex, [])[0] >= 8

    def test_one_line_item_prose_is_the_text_after_the_title(self):
        from engine.claims import _coverage_item_prose
        block = ("3. **Cybercab spotted in Salt Lake City** — Owners noted the vehicle "
                 "in Utah. Source: [x.com](https://x.com/a)")
        assert _coverage_item_prose(block).startswith("Owners noted the vehicle in Utah.")

    def test_outlet_head_is_not_prose(self):
        from engine.claims import _coverage_item_prose
        block = ("**KHL Foundation Reports Treatments:** Fight Aging!\n"
                 "This is an uncontrolled, unpublished use of the therapy in people. "
                 "Source: [fightaging.org](https://www.fightaging.org/a)")
        assert _coverage_item_prose(block).startswith("This is an uncontrolled")

    def test_read_more_lists_are_not_items(self):
        from engine.claims import _digest_items_with_source
        md = ("### 1) A story\n**What happened:** A long enough sentence about what happened today.\n\n"
              "**Read more (sources):**\n- [BBC](https://www.bbc.co.uk/a) — details\n")
        assert all("BBC" not in first for first, _ in _digest_items_with_source(md))


class TestArchiveUrlsVerifyAgainstTheOriginal:
    """UC Ep146: invented Wayback snapshots of real PNAS pages read as
    'not found' on the public record."""

    def test_unwrap(self):
        from engine.claims import unwrap_archive_url
        url = "https://web.archive.org/web/20220315000000/https://www.pnas.org/doi/10.1/x"
        assert unwrap_archive_url(url) == "https://www.pnas.org/doi/10.1/x"
        assert unwrap_archive_url("https://www.pnas.org/x") == "https://www.pnas.org/x"


class TestTrailerSurvivesTheNextEpisode:
    def test_trailer_block_is_reinserted(self, tmp_path):
        from engine.publisher import _reinsert_trailer_items, _unnumbered_trailer_items
        feed = tmp_path / "f.rss"
        feed.write_text(
            '<rss><channel><title>x</title>'
            '<item><guid>s-members-special-x-trailer</guid>'
            '<itunes:episodeType>trailer</itunes:episodeType></item>'
            '<item><guid>s-ep001-1</guid><itunes:episode>1</itunes:episode></item>'
            '</channel></rss>')
        kept = _unnumbered_trailer_items(feed)
        assert [g for g, _ in kept] == ["s-members-special-x-trailer"]
        out = tmp_path / "o.rss"
        out.write_text('<rss><channel><title>x</title><item><guid>s-ep002-1</guid></item></channel></rss>')
        _reinsert_trailer_items(out, kept)
        _reinsert_trailer_items(out, kept)  # once only
        assert out.read_text().count("members-special-x-trailer") == 1


class TestScheduledVideosAreNotLinked:
    def test_still_scheduled(self):
        from engine.release_schedule import is_still_scheduled
        now = dt.datetime(2026, 10, 18, 14, tzinfo=dt.timezone.utc)
        assert is_still_scheduled("2026-10-18T16:30:00Z", now=now)
        assert not is_still_scheduled("2026-10-18T11:15:00Z", now=now)
        assert not is_still_scheduled("", now=now)

    def test_homepage_skips_a_private_video(self):
        from engine.landing_test import pick_videos
        now = dt.datetime(2026, 10, 18, 14, tzinfo=dt.timezone.utc)
        rows = [
            {"show_slug": "tesla", "kind": "long", "channel": "en", "episode": 637,
             "published": "2026-10-17", "title": "Old public",
             "watch_url": "https://www.youtube.com/watch?v=a"},
            {"show_slug": "tesla", "kind": "long", "channel": "en", "episode": 638,
             "published": "2026-10-18", "publish_at": "2026-10-18T16:30:00Z",
             "title": "New private", "watch_url": "https://www.youtube.com/watch?v=b"},
        ]
        picked = pick_videos(rows, kind="long", public_slugs=["tesla"], limit=3, now=now)
        assert [v["watch_url"] for v in picked] == ["https://www.youtube.com/watch?v=a"]

    def test_run_show_keeps_scheduled_long_off_x_and_the_blog(self):
        src = (ROOT / "run_show.py").read_text()
        assert "youtube_long_scheduled = _still_scheduled(" in src
        assert "if youtube_long_url and not youtube_long_scheduled:" in src
        # Oct 31 2026: the post carries a scheduled long-form hidden, with
        # its release instant, instead of leaving it out.
        assert ("long_release=(youtube_urls.get(\"long_publish_at\") or \"\") "
                "if youtube_long_scheduled else \"\"") in src


class TestCheckpointPostCarriesItsPanels:
    def test_blog_meta_gets_the_digest_path(self):
        src = (ROOT / "run_show.py").read_text()
        assert '_blog_meta["_md_path"] = Path(digest_md)' in src


class TestEmptySectionsAreNotPublished:
    def test_drops_bare_heading_keeps_parent(self):
        from engine.absence_sentences import drop_empty_sections
        md = ("## Short Spot\n---\n### Tesla First Principles\nBody.\n\n"
              "## Today's lead story (1)\n### 1) Title\nText.\n\n### AI & Compute\n\n### Market Watch\nUp.\n")
        out, n = drop_empty_sections(md)
        assert n == 2
        assert "## Short Spot" not in out and "### AI & Compute" not in out
        assert "## Today's lead story (1)" in out and "### Tesla First Principles" in out

    def test_runs_after_validation_before_the_save(self):
        src = (ROOT / "run_show.py").read_text()
        i = src.index("drop_empty_sections as _drop_empty")
        assert i < src.index('digest_md.write_text(_scrub(x_thread)', i)


class TestInstructionLeaks:
    def test_shapes_from_the_oct_18_slate(self):
        from engine.absence_sentences import is_self_narration_sentence as f
        for s in ("Set the week in order, using only what these reports name.",
                  "What it changes, and for whom, follows from those named claims.",
                  "What changes follows from which figure touches which company.",
                  "Walk only the figures iTWire prints."):
            assert f(s), s
        assert not f("The walk only took ten minutes.")


class TestOutcomeLeads:
    """Vancouver Ep026: the result of the election was sent back as a
    re-telling of four days of campaign coverage."""

    def test_outcome_hook_is_not_a_retelling(self):
        from engine.story_recurrence import RecurrenceIndex
        eps = [{"date": f"2026-10-1{d}", "headlines": [
            "Ken Sim Wants to Be Re-Elected Mayor of Vancouver",
            "Ken Sim and Pete Fry trade jabs in mayoral debate",
            "Another unrelated transit story here",
            "Vancouver budget vote on parks"]} for d in range(4, 8)]
        idx = RecurrenceIndex(eps)
        assert idx.hook_match("Pete Fry unseats Ken Sim to become Vancouver's next mayor") is None
        assert idx.hook_match("Ken Sim Wants to Be Re-Elected Mayor of Vancouver again")


class TestStructuralRetryDeadline:
    def test_deadline_call(self):
        import time
        import pytest
        import run_show
        assert run_show._call_with_deadline(lambda: 7, 1) == 7
        with pytest.raises(TimeoutError):
            run_show._call_with_deadline(lambda: time.sleep(2), 0.1)

    def test_deadline_is_bounded(self):
        import run_show
        d = run_show._structural_retry_deadline()
        assert run_show._STRUCTURAL_RETRY_MIN_S <= d <= run_show._STRUCTURAL_RETRY_MAX_S


class TestSmallFixes:
    def test_ai6_is_spelled(self):
        from assets.pronunciation import prepare_text_for_tts
        assert "A I six" in prepare_text_for_tts("AI5 and AI6 chips")

    def test_queued_comments_are_a_metric(self):
        src = (ROOT / "engine/pipeline.py").read_text()
        assert 'metrics.record("yt_comments_queued"' in src
