"""Guards for the Oct 28 2026 review of the front page, Nerra Personal and
the YouTube pipeline (docs/reviews/landing_personal_youtube_2026_10_28.md).

What these pin, each a defect found on the day's committed data:

* Front page: a story another show already told is ONE card naming both
  shows; the "Also in this episode" list never repeats the hook; two papers
  with different names are never one developing thread; the lead headline
  comes before its picture; the Personal band names its price and plays the
  sample.
* Measurement: the events tracking.js sends are the events the fetcher asks
  for (episode plays, directory clicks, the Personal sample, checkout starts,
  clicks to YouTube); every Personal Payment Link carries ``data-nn-tier``.
* Personal copy: the privacy policy names xAI for members and what it
  receives; no surface says an edition is never cut, that the shows have
  "human editorial oversight", or that a feed stops the moment a member
  cancels; the gated desks are marked in the lineup.
* YouTube: every blog rebuild links the episode's public videos; the dub
  Shorts open on their own story, end on a sentence and get their custom
  thumbnail; long-form retention is read at a fixed age.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _strip_jinja_comments(text: str) -> str:
    return re.sub(r"\{#.*?#\}", "", text, flags=re.S)


# ---------------------------------------------------------------------------
# Front page
# ---------------------------------------------------------------------------


class TestSameStory:
    def test_inflections_are_one_story(self):
        from engine.newsroom import same_story
        assert same_story(
            "SpaceX plans 10,000 annual Starship launches from Louisiana site",
            "SpaceX planning 10,000 Starship launches a year at its Louisiana site",
        )

    def test_unrelated_headlines_are_not(self):
        from engine.newsroom import same_story
        assert not same_story(
            "Tesla spent $4.73 billion on capital expenditures last quarter",
            "Canadian variable-rate borrowers should watch the Fed decision",
        )

    def test_two_named_papers_are_two_stories(self):
        from engine.newsroom import _different_papers
        assert _different_papers(
            "AlphaFold3: protein structures predicted for every enzyme family",
            "RoseTTAFold2: protein structures predicted for every enzyme family",
        )
        assert not _different_papers(
            "AlphaFold3: protein structures predicted", "Protein structures predicted")


class TestMergeRetellings:
    def _story(self, slug, hook):
        return {"slug": slug, "hook": hook, "show_name": slug.title(),
                "show_page": f"{slug}.html", "post_url": f"blog/{slug}/ep001.html",
                "brand_color": "#123456"}

    def test_the_later_telling_folds_into_the_first(self):
        from engine.landing_test import merge_retellings
        a = self._story("planetterrian", "Inulin fiber supplement eased knee osteoarthritis pain in a trial")
        b = self._story("longevity", "Inulin fiber supplement eased knee osteoarthritis pain, a trial found")
        c = self._story("spacex", "SpaceX plans 10,000 annual Starship launches from Louisiana")
        out = merge_retellings([a, b, c])
        assert [s["slug"] for s in out] == ["planetterrian", "spacex"]
        assert out[0]["also_by"][0]["show_name"] == "Longevity"

    def test_one_show_is_never_merged_with_itself(self):
        from engine.landing_test import merge_retellings
        a = self._story("tesla", "Tesla Semi enters volume production in Nevada")
        b = self._story("tesla", "Tesla Semi enters volume production in Nevada plant")
        assert len(merge_retellings([a, b])) == 2

    def test_assemble_keeps_the_record_of_what_published(self):
        src = _read("engine/landing_test.py")
        body = src.split("def assemble(", 1)[1]
        assert "merge_retellings(ordered)" in body
        assert "published = ordered" in body

    def test_the_template_names_the_other_show(self):
        tpl = _read("templates/network_page.html.j2")
        assert "lt-also-by" in tpl and "Also told on" in tpl


class TestMoreHeadlines:
    def test_the_hook_is_never_listed_again(self):
        from engine.landing_test import more_headlines
        content = (
            "**1. SpaceX plans 10,000 annual Starship launches from Louisiana site**\n"
            "Body.\n\n"
            "**2. Falcon 9 lifts the Starlink Group 15-18 batch**\n"
            "Body.\n"
        )
        out = more_headlines(content, "SpaceX planning 10,000 Starship launches a year from Louisiana")
        assert all("Louisiana" not in h for h in out)


class TestFrontPageMarkup:
    def test_lead_headline_precedes_its_picture(self):
        for rel in ("templates/network_page.html.j2", "templates/language_hub.html.j2"):
            tpl = _strip_jinja_comments(_read(rel))
            lead = tpl.split('<article class="lt-lead"', 1)[1].split("</article>", 1)[0]
            assert lead.index('class="lt-lead-head"') < lead.index("media(s, eager=true)"), rel
            assert lead.index("<h2 class=\"lt-hl\"") < lead.index("media(s, eager=true)"), rel

    def test_model_written_launch_and_fact_strings_are_escaped(self):
        tpl = _read("templates/network_page.html.j2")
        assert "{{ l.mission | e }}" in tpl and "{{ l.rocket | e }}" in tpl
        assert "{{ d.fact | e }}" in tpl
        assert "{{ l.mission }}" not in tpl and "{{ d.fact }}" not in tpl

    def test_personal_band_names_its_price_and_plays_the_sample(self):
        tpl = _read("templates/network_page.html.j2")
        band = tpl.split('id="personal-promo"', 1)[1].split("</section>", 1)[0]
        assert 'data-nn-sample="homepage"' in band
        assert "$4.99 a month" in band
        assert "personal.sample_url" in band

    def test_the_sample_has_one_owner(self):
        src = _read("generate_html.py")
        assert src.count("personal/sample/vancouver.mp3") == 1
        assert '"sample_url": PERSONAL_SAMPLE_URL' in src

    def test_today_label_never_claims_a_stale_day(self):
        tpl = _read("templates/network_page.html.j2")
        assert "data-today-day=" in tpl and "data-stale-text=" in tpl


# ---------------------------------------------------------------------------
# Measurement: what the page sends is what the fetcher asks for
# ---------------------------------------------------------------------------


class TestEventsAreRead:
    SENT = ("episode_play", "subscribe_click", "play_personal_sample",
            "begin_checkout", "watch_on_youtube")

    def test_every_sent_event_is_asked_for(self):
        js = _read("assets/js/tracking.js")
        from fetch_ga4_stats import CONVERSION_EVENTS, ENGAGEMENT_EVENTS
        for name in self.SENT:
            assert f"'{name}'" in js, name
            assert name in ENGAGEMENT_EVENTS, name
            assert name not in CONVERSION_EVENTS, name

    def test_funnel_reports_them_null_when_unread(self):
        import build_funnel as bf
        out = bf._visits({}, {})
        for key in ("episode_plays", "directory_clicks", "personal_sample_plays",
                    "checkout_starts", "youtube_watch_clicks"):
            assert out[key]["total"] is None, key

    def test_funnel_counts_by_page(self):
        import build_funnel as bf
        ga4 = {"site_events": [
            {"eventName": "begin_checkout", "pagePath": "/join.html", "eventCount": "3"},
            {"eventName": "begin_checkout", "pagePath": "/account.html", "eventCount": "1"},
            {"eventName": "watch_on_youtube", "pagePath": "/blog/tesla/ep648.html", "eventCount": "2"},
        ]}
        assert bf._checkout_starts(ga4)["total"] == 4
        assert bf._site_event_counts(ga4, "watch_on_youtube")["by_page"] == {
            "/blog/tesla/ep648.html": 2}

    def test_every_payment_link_carries_its_tier(self):
        for rel in ("templates/join_page.html.j2", "templates/account_page.html.j2"):
            tpl = _read(rel)
            for m in re.finditer(r'<a [^>]*href="\{\{ stripe_personal(_local)?_url \}\}"[^>]*>', tpl):
                assert "data-nn-tier=" in m.group(0), (rel, m.group(0))


# ---------------------------------------------------------------------------
# Personal: the copy tells the truth about the product
# ---------------------------------------------------------------------------


class TestPersonalCopy:
    def test_privacy_policy_names_xai_for_members(self):
        tpl = _read("templates/privacy_policy.html.j2")
        assert "Nerra Personal members: xAI" in tpl
        section = tpl.split("Nerra Personal members: xAI", 1)[1].split("</ul>", 1)[0]
        for item in ("first name", "city", "subjects", "note to Mira"):
            assert item in section, item
        assert "never receives your email" in section
        assert "xAI for Nerra Personal members" in tpl

    def test_membership_details_list_what_is_stored(self):
        tpl = _read("templates/privacy_policy.html.j2")
        assert "Tell Mira about you" in tpl
        assert "for the morning-brief tier, the city you choose" not in tpl

    def test_no_surface_says_an_edition_is_never_cut(self):
        for rel in ("templates/join_page.html.j2", "templates/faq.html.j2"):
            assert "Nothing is summarized or cut down" not in _read(rel), rel
        assert "Skip repeats" in _read("templates/join_page.html.j2")

    def test_no_human_oversight_claim(self):
        assert "human editorial\n           oversight" not in _read("templates/join_page.html.j2")
        assert "AI-assisted productions with human editorial" not in _read("templates/join_page.html.j2")

    def test_a_cancel_never_cuts_the_paid_period(self):
        for rel in ("templates/show_page.html.j2", "templates/join_page.html.j2"):
            assert "stops working the moment you do" not in _read(rel), rel

    def test_faq_tiers_match_the_join_page(self):
        assert "$8.99 with a city morning brief" not in _read("templates/faq.html.j2")

    def test_gated_shows_are_marked_in_the_lineup(self):
        import generate_html as g
        cards = g._personal_shows_list()
        gated = [c["slug"] for c in cards if c["access_note"]]
        from engine.omni_desks import DESKS  # noqa: F401 — the desks are the gated shows
        assert gated, "no gated show in the Personal lineup"
        assert all(slug.startswith("omni_view_") for slug in gated)
        tpl = _read("templates/join_page.html.j2")
        assert "nn-showcard-access" in tpl and "s.access_note" in tpl
        assert ", all free" in tpl  # only when no show is gated

    def test_hero_states_the_price(self):
        tpl = _read("templates/join_page.html.j2")
        hero = tpl.split('class="np-hero"', 1)[1].split("</section>", 1)[0]
        assert "$4.99/mo" in hero


class TestPersonalBuilderDate:
    def test_edition_date_is_eastern(self):
        import build_personal_feeds as bpf
        from zoneinfo import ZoneInfo
        assert bpf._eastern_today() == dt.datetime.now(ZoneInfo("America/New_York")).date()

    def test_available_count(self):
        import build_personal_feeds as bpf

        class Spec:
            shows = ["tesla", "spacex", "omni_view"]
        assert bpf._available_count(Spec(), {"tesla": object(), "omni_view": object()}) == 2


class TestMemberMetricsFromDemand:
    def test_counts_only_and_nulls_for_the_rest(self):
        import build_member_metrics as bmm
        out = bmm.summarise_demand({"members": 3, "demand": {"spacex": 2, "tesla": 3}})
        assert out["paid_active_total"] == 3
        assert list(out["shows_chosen"]) == ["tesla", "spacex"]
        for key in ("by_tier", "mrr_usd", "free_accounts", "trialing"):
            assert out[key] is None, key

    def test_the_nightly_passes_the_demand_token(self):
        wf = _read(".github/workflows/nightly-maintenance.yml")
        step = wf.split("Aggregate paid-member counts", 1)[1].split("- name:", 1)[0]
        assert "PERSONAL_DEMAND_TOKEN: ${{ secrets.PERSONAL_DEMAND_TOKEN }}" in step


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------


def _index(tmp_path: Path, rows) -> Path:
    path = tmp_path / "youtube_videos.json"
    path.write_text(json.dumps({"schema_version": 1, "videos": rows}), encoding="utf-8")
    return path


class TestEpisodeVideoLinks:
    NOW = dt.datetime(2026, 10, 28, 15, 0, tzinfo=dt.timezone.utc)

    def test_public_long_and_hook_short(self, tmp_path):
        from engine.youtube_index import episode_video_links
        rows = [
            {"video_id": "s2", "episode": 7, "kind": "short", "window": "qualified",
             "watch_url": "https://www.youtube.com/watch?v=s2"},
            {"video_id": "s1", "episode": 7, "kind": "short", "window": "hook_open",
             "watch_url": "https://www.youtube.com/watch?v=s1"},
            {"video_id": "l1", "episode": 7, "kind": "long",
             "watch_url": "https://www.youtube.com/watch?v=l1"},
        ]
        links = episode_video_links(_index(tmp_path, rows), now=self.NOW)
        assert links[7] == {"long": "https://www.youtube.com/watch?v=l1",
                            "short": "https://www.youtube.com/watch?v=s1"}

    def test_a_scheduled_video_is_never_linked(self, tmp_path):
        from engine.youtube_index import episode_video_links
        rows = [{"video_id": "l1", "episode": 8, "kind": "long",
                 "watch_url": "https://www.youtube.com/watch?v=l1",
                 "publish_at": "2026-10-28T16:00:00Z"},
                {"video_id": "s1", "episode": 8, "kind": "short", "window": "hook_open",
                 "watch_url": "https://www.youtube.com/watch?v=s1",
                 "publish_at": "2026-10-28T11:00:00Z"}]
        links = episode_video_links(_index(tmp_path, rows), now=self.NOW)
        assert links[8] == {"short": "https://www.youtube.com/watch?v=s1"}

    def test_bad_rows_and_missing_file(self, tmp_path):
        from engine.youtube_index import episode_video_links
        rows = [{"episode": "9", "kind": "long", "watch_url": "https://x"},
                {"episode": 9, "kind": "long", "watch_url": "javascript:alert(1)"},
                "junk"]
        assert episode_video_links(_index(tmp_path, rows), now=self.NOW) == {}
        assert episode_video_links(tmp_path / "missing.json") == {}

    def test_the_committed_indexes_link_most_episodes(self):
        from engine.youtube_index import episode_video_links
        links = episode_video_links(ROOT / "digests" / "tesla_shorts_time" / "youtube_videos.json")
        assert sum(1 for v in links.values() if v.get("long")) >= 50


class TestBlogLinksItsVideos:
    def test_every_rebuild_passes_the_links(self):
        src = _read("generate_html.py")
        body = src.split("def generate_blog_posts(", 1)[1].split("\ndef ", 1)[0]
        assert "episode_video_links(" in body
        assert "youtube_url=(_video_links.get(" in body
        assert "youtube_short_url=(_video_links.get(" in body

    def test_the_run_gates_the_short_on_its_release(self):
        src = _read("run_show.py")
        assert '_still_scheduled(youtube_urls.get("short_publish_at") or "")' in src

    @pytest.mark.parametrize("long_url,short_url,label", [
        ("https://www.youtube.com/watch?v=L", "https://www.youtube.com/watch?v=S", "Watch on YouTube"),
        ("", "https://www.youtube.com/watch?v=S", "Watch the Short"),
    ])
    def test_the_post_renders_the_button(self, long_url, short_url, label):
        import generate_html as g
        from engine.blog import extract_blog_metadata, generate_blog_post_html
        md = sorted((ROOT / "digests" / "tesla_shorts_time").glob("*Ep64*.md"))[-1]
        text = md.read_text(encoding="utf-8")
        meta = extract_blog_metadata(text, "tesla", md.name, file_path=md)
        meta["_md_path"] = md
        html = generate_blog_post_html(text, meta, g.NETWORK_SHOWS["tesla"], g._get_jinja_env(),
                                       youtube_url=long_url, youtube_short_url=short_url)
        assert label in html
        assert 'data-nn-watch=' in html


class TestDubShorts:
    @pytest.mark.parametrize("rel", ["engine/ru_dub.py", "engine/lang_dub.py"])
    def test_window_shorts_open_on_their_own_story(self, rel):
        src = _read(rel)
        assert "hook=_overlay," in src
        assert "_overlay = " in src and "if short_idx == 0 else (_window_body or None)" in src

    @pytest.mark.parametrize("rel", ["engine/ru_dub.py", "engine/lang_dub.py"])
    def test_dub_shorts_end_on_a_sentence(self, rel):
        src = _read(rel)
        assert "end_on_sentence(" in src
        assert "duration=this_dur," in src
        assert "window_duration_seconds=this_dur," in src

    @pytest.mark.parametrize("rel", ["engine/ru_dub.py", "engine/lang_dub.py"])
    def test_the_thumbnail_call_matches_the_signature(self, rel):
        import inspect
        from engine.publisher import generate_shorts_thumbnail
        params = inspect.signature(generate_shorts_thumbnail).parameters
        src = _read(rel)
        call = src.split("generate_shorts_thumbnail(\n", 1)[1].split(")\n", 1)[0]
        for name in ("episode_num", "date_str", "output_path"):
            assert f"{name}=" in call, (rel, name)
            assert name in params

    def test_the_thumbnail_renders_cyrillic(self, tmp_path):
        from engine.publisher import generate_shorts_thumbnail
        out = tmp_path / "t.jpg"
        generate_shorts_thumbnail(ROOT / "assets" / "covers" / "age-of-ai.jpg",
                                  episode_num=648, date_str="2026-10-28", output_path=out,
                                  hook="Tesla потратила 4,73 млрд долларов",
                                  show_name="Tesla Shorts Time")
        assert out.exists() and out.stat().st_size > 10_000


class TestShortsThumbnailPunch:
    def test_punch_text_moves_to_the_upper_band(self):
        src = _read("engine/publisher.py")
        body = src.split("def generate_shorts_thumbnail(", 1)[1].split("\ndef ", 1)[0]
        assert 'text_band="upper" if (punch_text or "").strip() else "lower"' in body

    def test_only_the_hook_short_carries_the_episode_punch(self):
        src = re.sub(r"\s+", " ", _read("run_show.py"))
        assert 'punch_text=(yt_punch_text if _fill_mode == "hook_open" else "")' in src


class TestHashtagAcronyms:
    def test_keywords_keep_their_acronyms(self):
        from engine.shorts_hashtags import extract_hashtags
        tags = extract_hashtags("", show_keywords=["TSLA", "llm", "ai model"], max_hashtags=5)
        assert "TSLA" in tags and "LLM" in tags and "AIModel" in tags


class TestRetentionAtAFixedAge:
    def test_longs_are_followed_past_the_shorts_feed_taps(self):
        import track_early_reach as ter
        assert ter.LONG_MAX_AGE_DAYS >= 14 and ter.MAX_AGE_DAYS == 7

    def _stats(self, gen: str, rows):
        return {"generated": gen, "shows": {"tesla_shorts_time": {"videos": rows}},
                "channels": {"en": {"day_series": [{"date": gen, "views": 1}]}}}

    def test_a_zero_with_no_watch_time_is_unmeasured(self):
        import track_early_reach as ter
        reach = {"videos": {}}
        stats = self._stats("2026-10-28", [
            {"video_id": "v", "published": "2026-10-26", "kind": "long", "channel": "en",
             "views": 4, "average_view_percentage": 0.0, "average_view_duration_s": 0}])
        ter.merge_snapshot(reach, stats)
        rec = reach["videos"]["v"]
        assert rec["views_by_age"] == {"2": 4}
        assert "avp_by_age" not in rec or rec["avp_by_age"].get("2") is None

    def test_a_long_is_recorded_at_day_14(self):
        import track_early_reach as ter
        reach = {"videos": {}}
        stats = self._stats("2026-10-28", [
            {"video_id": "l", "published": "2026-10-14", "kind": "long", "channel": "en",
             "views": 40, "average_view_percentage": 12.5, "average_view_duration_s": 70},
            {"video_id": "s", "published": "2026-10-14", "kind": "short", "channel": "en",
             "views": 40, "average_view_percentage": 60.0, "average_view_duration_s": 20}])
        ter.merge_snapshot(reach, stats)
        assert reach["videos"]["l"]["avp_by_age"]["14"] == 12.5
        assert "s" not in reach["videos"]

    def test_dashboard_reads_the_fixed_age(self, tmp_path):
        import generate_dashboard as gd
        (tmp_path / "api").mkdir()
        vids = {f"v{i}": {"kind": "long", "channel": "en", "published": "2026-10-15",
                          "avp_by_age": {"7": 5.0 + i}} for i in range(9)}
        (tmp_path / "api" / "youtube_early_reach.json").write_text(
            json.dumps({"videos": vids}), encoding="utf-8")
        assert gd._long_avp_at_age(tmp_path, dt.date(2026, 10, 27)) == 9.0
        assert gd._long_avp_at_age(tmp_path, dt.date(2026, 10, 27), min_n=10) is None
        assert "long_form_avp_en_age7_median" in gd._experiment_live_metrics(ROOT)
