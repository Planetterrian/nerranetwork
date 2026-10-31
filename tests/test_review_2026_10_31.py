"""Oct 31 2026 — the 24-hour review of shows, YouTube, the website and
Nerra Personal, acted on.

Four reviewers read the Oct 30-31 slate: the episodes, the video pipeline,
the front page through the day, and Nerra Personal / My Nerra. Each fix
below is pinned to what it fixed.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------- episodes
class TestUnitsNeedAQuantity:
    def test_a_lone_letter_is_never_a_unit(self):
        from assets.pronunciation import replace_units

        for text in ("h n t p plus equals h m t p detached", "the letter m is",
                     "two a m", "eleven forty seven p m", "l mm underscore"):
            assert replace_units(text) == text, text

    def test_real_units_still_expand(self):
        from assets.pronunciation import replace_units

        assert replace_units("ninety m tall") == "ninety meters tall"
        assert replace_units("Three km") == "Three kilometers"
        assert replace_units("five hundred thousand km") == "five hundred thousand kilometers"
        assert replace_units("per kWh") == "per kilowatt hours"
        assert replace_units("in MW") == "in megawatts"
        assert replace_units("a 500 km run") == "a 500 kilometers run"


class TestNoPlatformAskOnAMembersShow:
    def test_members_only_desks_never_ask(self):
        from engine.intros import platform_ask_for

        day = dt.date(2026, 10, 31)
        assert not any(platform_ask_for("omni_view_north_america", day + dt.timedelta(d))
                       for d in range(8))
        assert any(platform_ask_for("tesla", day + dt.timedelta(d)) for d in range(8))


class TestReactionSentences:
    def test_reaction_only_sentences_are_removed(self):
        from engine.listener_noise import clean_sentence

        for s in ("Elon Musk replied to the post with “Cool” and a heart emoji.",
                  "Commenters speculated on whether it was a recovered Dragon capsule or a test article.",
                  "The post received immediate engagement but offered no additional details."):
            assert clean_sentence(s) == ("", True), s

    def test_news_carried_by_a_reply_stays(self):
        from engine.listener_noise import clean_sentence

        for s in ("Musk replied that the factory would open in May.",
                  "Users reported outages across Europe."):
            assert clean_sentence(s) == (s, False), s


class TestPlanetterrianAstronomyPlurals:
    def test_plural_forms_are_filtered(self):
        import re

        import yaml

        pats = yaml.safe_load(_read("shows/planetterrian.yaml"))["exclude_title_patterns"]
        title = "Heriot-Watt links telescopes across continents"
        assert any(re.search(p, title, re.IGNORECASE) for p in pats)
        for word in ("rovers", "orbiters"):
            assert any(re.search(p, f"New {word} planned", re.IGNORECASE) for p in pats), word


# ----------------------------------------------------------------- YouTube
class TestDubShortsKeepTheirScenes:
    def test_probe_cap_never_starves_a_dub_channel(self):
        from engine.youtube_policy import portrait_scene_count

        class _Yt:
            short_scenes_per_episode = 5
            ru_dub_enabled = True
            dub_languages = ["fr"]
            multi_platform_enabled = False

        assert portrait_scene_count(_Yt(), shorts_planned=0, shorts_probe=True) == 5

    def test_a_shorts_only_day_keeps_its_one_landscape_scene(self):
        src = _read("run_show.py")
        assert "if len(long_scene_paths) >= (2 if _long_form_produced else 1) else []" in src
        assert "if len(long_scene_paths) < (2 if _long_form_produced else 1):" in src


class TestTheLivePolicyAfterTheReset:
    def test_dub_long_forms_turned_on_by_two_probes_are_off(self):
        policy = json.loads(_read("api/youtube_policy.json"))
        for ch, slugs in (("ru", ("spacex", "tesla", "fascinating_frontiers")),
                          ("fr", ("tesla", "fascinating_frontiers"))):
            for slug in slugs:
                assert policy["channels"][ch][slug]["publish_long_form"] is False, (ch, slug)

    def test_the_breakout_shows_are_back_to_a_daily_short(self):
        en = json.loads(_read("api/youtube_policy.json"))["channels"]["en"]
        for slug in ("fascinating_frontiers", "first_principles", "models_agents", "omni_view"):
            assert en[slug]["shorts_probe_weekly"] is False, slug


# ----------------------------------------------------------------- website
class TestScheduledVideosShowAtRelease:
    def _index(self, tmp_path, rows):
        p = tmp_path / "youtube_videos.json"
        p.write_text(json.dumps({"schema_version": 1, "videos": rows}), encoding="utf-8")
        return p

    def test_a_scheduled_video_is_kept_with_its_release(self, tmp_path):
        from engine.youtube_index import episode_video_links

        now = dt.datetime(2026, 10, 31, 10, 0, tzinfo=dt.timezone.utc)
        p = self._index(tmp_path, [
            {"episode": 5, "kind": "long", "watch_url": "https://www.youtube.com/watch?v=aaaaaaaaaaa",
             "publish_at": "2026-10-31T11:45:00Z"},
            {"episode": 5, "kind": "short", "window": "hook_open",
             "watch_url": "https://www.youtube.com/shorts/bbbbbbbbbbb", "publish_at": ""},
        ])
        assert episode_video_links(p, now=now) == {5: {"short": "https://www.youtube.com/shorts/bbbbbbbbbbb"}}
        got = episode_video_links(p, now=now, include_scheduled=True)[5]
        assert got["long_at"] == "2026-10-31T11:45:00Z" and "short_at" not in got

    def test_the_post_hides_it_until_then(self):
        tpl = _read("templates/blog_post.html.j2")
        assert 'hidden data-nn-release="{{ youtube_release | e }}"' in tpl
        js = _read("assets/js/nn-app.js")
        assert "function releaseScheduled()" in js and "releaseScheduled();" in js
        assert "include_scheduled=True" in _read("generate_html.py")


class TestLanguageFrontPagesFollowTheHomepage:
    def test_homepage_flag_rebuilds_the_hubs_and_every_commit_carries_them(self):
        src = _read("generate_html.py")
        i = src.index("    if args.homepage:\n")
        assert "generate_language_hub_pages(" in src[i:i + 600]
        assert "git add ru/index.html fr/index.html" in _read(".github/workflows/run-show.yml")
        assert "index.html ru/index.html fr/index.html" in _read(".github/workflows/render-video.yml")
        nd = _read(".github/workflows/nerra-daily.yml")
        assert "ru/index.html" in nd and "fr/index.html" in nd

    def test_every_site_language_has_its_page_committed(self):
        import generate_html as g
        from engine.show_lang import site_languages

        for lang in site_languages(g.NETWORK_SHOWS):
            if lang != "en":
                assert f"{lang}/index.html" in _read(".github/workflows/run-show.yml"), lang


class TestUpdatedIsTheNewestStory:
    def test_masthead_uses_the_story_time_never_the_future(self):
        from engine.newsroom import masthead

        now = dt.datetime(2026, 10, 31, 12, 34, tzinfo=dt.timezone.utc)
        story = dt.datetime(2026, 10, 31, 10, 24, tzinfo=dt.timezone.utc)
        assert masthead(now, story)["updated_iso"] == "2026-10-31T10:24:00Z"
        assert masthead(now, now + dt.timedelta(hours=1))["updated_iso"] == "2026-10-31T12:34:00Z"
        assert masthead(now)["updated_iso"] == "2026-10-31T12:34:00Z"

    def test_newest_story_time_reads_only_timed_stamps(self):
        from engine.newsroom import newest_story_time

        a = {"stamp": {"iso": "2026-10-31T09:55:15Z", "has_time": True}}
        b = {"stamp": {"iso": "2026-10-31", "has_time": False}}
        assert newest_story_time(a, [b], []) == dt.datetime(2026, 10, 31, 9, 55, 15,
                                                           tzinfo=dt.timezone.utc)
        assert newest_story_time([b]) is None


class TestTheLeadIsToday:
    def test_newest_day_beats_an_older_landscape_lead(self):
        src = _read("engine/landing_test.py")
        i = src.index("newest = pool[0].get(\"date_obj\")")
        block = src[i:i + 700]
        assert block.index('s.get("date_obj") == newest and s["image_url"]') < block.index(
            'next((s for s in pool if s["image_orientation"] == "landscape"), pool[0])')


class TestColumnBylinesAreNotAThread:
    def test_byline_is_stripped(self):
        from engine.newsroom import _strip_column_byline

        assert _strip_column_byline("Vaughn Palmer: Lorne Doerkson pledges a review") == \
            "Lorne Doerkson pledges a review"
        assert _strip_column_byline("SpaceX: Starship flies") == "SpaceX: Starship flies"


# ------------------------------------------------------- Nerra Personal
class TestSavedStocksAreSpoken:
    def test_markets_minute_on_when_stocks_saved_and_toggles_untouched(self):
        from engine.personal_edition import PersonalSpec

        assert "markets" in PersonalSpec(token="t", shows=["tesla"], tickers=["NVDA"]).effective_addons()
        assert "markets" not in PersonalSpec(token="t", shows=["tesla"]).effective_addons()
        chosen = PersonalSpec(token="t", shows=["tesla"], tickers=["NVDA"], addons=["weather"])
        assert chosen.effective_addons() == ["weather"]

    def test_the_page_reads_the_same_rule(self):
        tpl = _read("templates/account_page.html.j2")
        assert "function chosenAddons()" in tpl
        assert "state.tickers && state.tickers.length && d.indexOf('markets') === -1" in tpl


class TestMyNerraTellsEachStoryOnce:
    def test_cards_carry_only_the_rail_overflow(self):
        tpl = _read("templates/account_page.html.j2")
        assert "var rest = rail.slice(8);" in tpl
        assert "var rest = latest.filter(function (s) { return s !== lead; });" not in tpl

    def test_one_video_card_per_episode(self):
        tpl = _read("templates/account_page.html.j2")
        assert "else if (safeUrl(v.long)) { rows.push" in tpl


class TestTopicsMatchWords:
    def test_no_bare_prefix_match(self):
        tpl = _read("templates/account_page.html.j2")
        assert "var ENDINGS = /^(s|es|ed|d|ing|er|ers|ian|ians|ite|ites|al|ic|ics)$/;" in tpl
        assert "w.indexOf(k) === 0); });" not in tpl

    def test_shows_carry_their_subjects(self):
        src = _read("generate_html.py")
        assert '"topics": [str(t).replace("-", " ")' in src
        assert "(entry.topics || []).some(function (tag) { return hits(keys, tag); })" in _read(
            "templates/account_page.html.j2")


class TestMembersOnlyDesksAreNeverFree:
    def test_join_never_says_hear_it_free_on_a_desk(self):
        tpl = _read("templates/join_page.html.j2")
        assert '{% if not s.access_note %}<a class="jn-hear"' in tpl
        assert "Every public show &amp; episode, always free" in tpl
        assert "Every public show stays free to hear either way" in _read("templates/network_page.html.j2")


class TestPersonalFrontIsNotRewrittenForATimestamp:
    def test_identical_rows_skip_the_write(self, tmp_path, monkeypatch):
        import generate_html as g

        payload = {"generated_at": "2026-10-31T10:00:00Z", "per_show": 3, "shows": {"x": {}}}
        monkeypatch.setattr(g, "personal_front_payload",
                            lambda *a, **k: dict(payload, generated_at="2026-10-31T11:00:00Z"))
        called = []
        monkeypatch.setattr(g, "generate_watch_page", lambda **k: called.append(1))
        out = tmp_path / "api" / "personal_front.json"
        out.parent.mkdir(parents=True)
        out.write_text(json.dumps(payload), encoding="utf-8")
        g.write_personal_front([], gallery_root=tmp_path, now=dt.datetime.now(dt.timezone.utc),
                               output_dir=tmp_path)
        assert json.loads(out.read_text())["generated_at"] == "2026-10-31T10:00:00Z"
        assert called == []
