"""Oct 28 2026 — the Oct 27 slate review.

Guards for what the review found and fixed. Each test names the episode it
came from.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ------------------------------------------------- a heading's marker title --
class TestHeadingNamedByMarkerPattern:
    """SpaceX Ep143 shipped a chapter titled "Engineering Deep Dive" at 0:42,
    inside the lead (the deep dive explained the lead's Raptor 4 story),
    beside the real "The Engineering Angle" chapter at 6:58: the digest
    heading matched neither the marker's title nor a digest_section, so the
    heading became a second title."""

    MARKERS = [
        {"pattern": "engineering deep dive|engineering angle|from an engineering standpoint",
         "title": "The Engineering Angle"},
        {"pattern": "on the market side|market watch", "title": "Market Watch"},
        {"pattern": "regulatory|policy watch", "title": "Regulatory & Policy Watch"},
    ]

    def test_a_heading_the_pattern_matches_whole_takes_the_marker_title(self):
        from engine.chapters import _section_marker_title
        assert _section_marker_title("Engineering Deep Dive", self.MARKERS) == "The Engineering Angle"
        assert _section_marker_title("### Market Watch", self.MARKERS) == "Market Watch"

    def test_a_word_inside_a_heading_is_not_enough(self):
        # A search mapped Env Intel's "Regulatory Calendar — Next 30 Days"
        # onto "Regulatory & Policy Watch" in the replay.
        from engine.chapters import _section_marker_title
        assert _section_marker_title("Regulatory Calendar — Next 30 Days", self.MARKERS) == ""

    def test_opening_and_closing_markers_never_name_a_section(self):
        from engine.chapters import _section_marker_title
        markers = [{"pattern": "engineering deep dive", "title": "X", "where": "end"}]
        assert _section_marker_title("Engineering Deep Dive", markers) == ""

    def test_spacex_ep143_replays_without_the_stray_chapter(self):
        md = ROOT / "digests/spacex/SpaceX_Daily_Ep143_20261027.md"
        tts = ROOT / "digests/spacex/SpaceX_Daily_Ep143_20261027_tts.txt"
        if not (md.exists() and tts.exists()):
            pytest.skip("Ep143 not committed")
        from engine.chapters import parse_chapters
        from engine.config import load_config
        from engine.grok_imagine import extract_story_headlines
        cfg = load_config(str(ROOT / "shows/spacex.yaml"))
        digest = md.read_text(encoding="utf-8")
        chapters = parse_chapters(
            tts.read_text(encoding="utf-8"), cfg.chapters.section_markers,
            show_name=cfg.name,
            story_headlines=extract_story_headlines(digest, max_count=12),
            digest_text=digest, known_sections_only=True)
        titles = [c.title for c in chapters]
        assert "Engineering Deep Dive" not in titles
        assert titles.count("The Engineering Angle") == 1

    def test_the_committed_ep143_file_is_repaired(self):
        p = ROOT / "digests/spacex/chapters_ep143.json"
        if not p.exists():
            pytest.skip("not committed")
        chapters = json.loads(p.read_text(encoding="utf-8"))["chapters"]
        assert "Engineering Deep Dive" not in [c["title"] for c in chapters]
        for a, b in zip(chapters, chapters[1:]):
            assert a["endTime"] == b["startTime"]


# ------------------------------------------------------ frame-1 promo anchor --
class TestFrameOneOpeningClause:
    """SpaceX Ep142: Whisper wrote "And before you go, this show is part of
    the | cast on tech, science, and markets" — the network's name lost —
    and the weak fallback cut 20 s late, so the Oct 26 edition aired the
    plug."""

    def _t(self, sentences, duration):
        segs, t = [], duration - 0.4 * sum(len(s.split()) for s in sentences) - 1
        for s in sentences:
            toks = s.split()
            words = [{"word": w, "start": t + 0.4 * k, "end": t + 0.4 * k + 0.3}
                     for k, w in enumerate(toks)]
            segs.append({"start": words[0]["start"], "end": words[-1]["end"],
                         "text": s, "words": words})
            t = words[-1]["end"] + 0.1
        return {"duration": duration, "segments": segs}

    def test_the_clause_alone_is_frame_grade(self):
        from engine.daily_edition import find_promo_cut
        t = self._t(["real content " * 40,
                     "and before you go this show is part of the",
                     "cast on tech science and markets",
                     "this episode used ai voice synthesis of my voice"], 600.0)
        hit = find_promo_cut(t)
        assert hit and hit["kind"] == "promo" and hit["anchor"] == "frame"

    def test_the_body_teaser_is_not_the_frame(self):
        from engine.daily_edition import find_promo_cut
        t = self._t(["real content " * 40,
                     "before we go this show is part of a bigger story about launch cadence",
                     "this episode used ai voice synthesis of my voice"], 600.0)
        hit = find_promo_cut(t)
        assert not hit or hit["kind"] != "promo"


# --------------------------------------------- an item number is not a title --
class TestItemNumberInsideTheBold:
    """Fascinating Frontiers Ep235 wrote its items "**1. Title — r/space**"
    and every story chapter opened "1.", "3.", "11." (Top World Ep002/Ep030
    the same with ": Outlet")."""

    def test_the_number_inside_the_bold_is_dropped(self):
        from engine.chapters import _digest_item_titles
        digest = ("**1. Satellites close to jogging-pace rendezvous in Space Force test — r/space**\n"
                  "Body.\n"
                  "**11. Possible Jupiter-sized exomoon detected for first time — NASA**\n"
                  "Body.\n"
                  "**3. Russian strikes hit Kyiv after Witkoff meets Putin: Al Jazeera**\n")
        assert _digest_item_titles(digest) == [
            "Satellites close to jogging-pace rendezvous in Space Force test",
            "Possible Jupiter-sized exomoon detected for first time",
            "Russian strikes hit Kyiv after Witkoff meets Putin",
        ]

    def test_a_number_that_is_the_title_stays(self):
        from engine.chapters import _digest_item_titles
        # "2026" is not an item number (more than two digits, no period).
        assert _digest_item_titles("**2026 budget lands with a deficit — CBC**\n") == [
            "2026 budget lands with a deficit"]

    @pytest.mark.parametrize("path", [
        "digests/fascinating_frontiers/chapters_ep235.json",
        "digests/omni_view_world/chapters_ep002.json",
        "digests/omni_view_world/chapters_ep030.json",
    ])
    def test_the_committed_files_are_repaired(self, path):
        import re
        p = ROOT / path
        if not p.exists():
            pytest.skip("not committed")
        titles = [c["title"] for c in json.loads(p.read_text(encoding="utf-8"))["chapters"]]
        assert not [t for t in titles if re.match(r"^\d{1,2}[.)]\s", t)]


# ------------------------------------------------ an allele is not a clock --
class TestTimeInsideAToken:
    """Planetterrian Ep226 aired "HLA-DRB1*01:03" as "one oh three A M"."""

    def test_an_allele_is_left_alone(self):
        from assets.pronunciation import replace_times
        assert "A M" not in replace_times("carriers of HLA-DRB1*01:03 were protected")
        assert "01:03" in replace_times("carriers of HLA-DRB1*01:03 were protected")

    def test_a_bold_time_is_still_a_time(self):
        from assets.pronunciation import replace_times
        assert replace_times("**07:30**") == "**seven thirty A M**"

    def test_a_token_glued_time_is_not(self):
        from assets.pronunciation import replace_times
        for s in ("phi4:14b", "2026-10-27T00:27:57"):
            assert replace_times(s) == s


# ------------------------------------------- a display resolution is a name --
class TestDisplayResolution:
    """MAG 7 Ep035 aired "four thousand video at up to sixty frames a
    second" for 4K video."""

    @pytest.mark.parametrize("text", [
        "4K video at up to 60 frames", "a new Apple TV 4K", "an 8K TV", "records 4K at 60 fps",
    ])
    def test_a_resolution_is_never_a_thousand(self, text):
        from assets.pronunciation import prepare_text_for_tts
        assert "thousand" not in prepare_text_for_tts(text)

    @pytest.mark.parametrize("text", ["a $4K bonus", "4K subscribers", "2.5k downloads"])
    def test_a_quantity_still_is(self, text):
        from assets.pronunciation import prepare_text_for_tts
        assert "thousand" in prepare_text_for_tts(text)


# ---------------------------------------------------- the page-date probe --
class TestDateProbeReachesTheList:
    """Tesla Ep647: 38 articles needed a date, 12 were probed, and a 2022
    IEEE Spectrum article aired among the news."""

    def test_the_default_covers_a_flagship_day(self):
        from engine import article_dates as ad
        from engine.config import load_config
        assert ad.DEFAULT_MAX_PROBES >= 40
        for slug in ("tesla", "spacex"):
            assert load_config(str(ROOT / f"shows/{slug}.yaml")).date_probe_max >= 40

    def test_forty_candidates_are_all_opened(self):
        from engine import article_dates as ad
        arts = [{"url": f"https://example.com/story-{i}", "title": f"t{i}",
                 "date_source": "x_post", "published_date": "2026-10-27"} for i in range(40)]
        opened = []

        def fake(url):
            opened.append(url)
            return 200, "<html></html>"
        counters = ad.probe_page_dates(arts, max_probes=ad.DEFAULT_MAX_PROBES, fetch=fake)
        assert counters["probed"] == counters["candidates"] == len(opened)


# ------------------------------------- the guest survey and hello invites --
class TestVoicesQueriesReachPostgREST:
    """Every "Fire scheduled interviews" run on Oct 27 logged HTTP 400 from
    both steps (continue-on-error kept them green): the timestamps carried an
    unencoded "+00:00", and the hello query filtered ``interviews`` on
    ``scheduled_for``, a column of ``interview_runs``. No guest had been
    surveyed or invited since the steps shipped."""

    NOW = None

    @staticmethod
    def _voices():
        sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
        import guest_survey as gs
        import hello_sessions as hs
        return gs, hs

    def test_the_hello_query_uses_the_interviews_column_and_a_safe_instant(self, monkeypatch):
        import datetime as dt
        _gs, hs = self._voices()
        seen = []
        monkeypatch.setattr(hs, "sb_select", lambda table, q: seen.append((table, q)) or [])
        hs.send_hello_invites(now=dt.datetime(2026, 10, 27, 16, 27, tzinfo=dt.timezone.utc))
        table, q = seen[0]
        assert table == "interviews"
        assert "scheduled_at=gte.2026-10-29T16:27:00Z" in q
        assert "scheduled_for" not in q and "+" not in q

    def test_the_survey_query_carries_no_plus(self, monkeypatch):
        import datetime as dt
        gs, _hs = self._voices()
        seen = []
        monkeypatch.setattr(gs, "sb_select", lambda table, q: seen.append((table, q)) or [])
        gs.due_packages(now=dt.datetime(2026, 10, 27, 16, 27, tzinfo=dt.timezone.utc))
        table, q = seen[0]
        assert table == "editorial_packages"
        assert "+" not in q and "created_at=gte.2026-10-13T16:27:00Z" in q

    def test_the_interviews_table_has_no_scheduled_for(self):
        sql = (ROOT / "supabase/migrations/20260704_nerra_voices_schema.sql").read_text()
        block = sql[sql.index("create table if not exists interviews"):]
        block = block[:block.index(");")]
        assert "scheduled_at" in block and "scheduled_for" not in block


# ------------------------------------------------ the system-package cache --
class TestThePackageCacheInstalls:
    """All 50 cache hits on Oct 27 warned "the cached system packages did not
    install; falling back to the mirror": apt resolved the request against the
    image's stale lists and asked for archives the cache did not hold."""

    COMPOSITE = (ROOT / ".github/actions/setup-python/action.yml").read_text(encoding="utf-8")

    def test_a_hit_installs_with_dpkg(self):
        hit = self.COMPOSITE[self.COMPOSITE.index('if [ "$CACHE_HIT" = "true" ]'):]
        hit = hit[:hit.index("falling back to the mirror")]
        assert 'dpkg --force-confold -i "$APT_DEBS"/*.deb' in hit
        commands = [ln for ln in hit.splitlines() if not ln.strip().startswith("#")]
        assert not [ln for ln in commands if "--no-download" in ln]

    def test_the_mirror_install_repairs_a_half_done_cache_install(self):
        assert "apt-get $APT_OPTS install -y -q -f ${{ inputs.system-packages }}" in self.COMPOSITE
