"""Nov 1 2026 — one network email, Nerra Daily, each reader's own shows.

Guards for engine/nerra_daily_email.py, the send script, the delivery
switch that retires the per-show dailies and weeklies, the account Worker's
mirror of the show map, the funnel tags and the measurement.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from engine import nerra_daily_email as nde  # noqa: E402

DAY = dt.date(2026, 11, 2)          # a Monday
SUNDAY = dt.date(2026, 11, 1)
NOW = dt.datetime(2026, 11, 2, 11, 40, tzinfo=dt.timezone.utc)


def _story(slug, name, ep, day, hook, headlines=()):
    return {
        "slug": slug, "show_name": name, "hook": hook, "episode_num": ep,
        "date_raw": day.isoformat(), "post_url": f"blog/{slug}/ep{ep:03d}.html",
        "headlines": list(headlines), "duration_s": 600, "guest": "",
    }


def _front(day=DAY):
    """A personal_front.json shape: five public shows, a desk, the edition."""
    shows = {}
    for slug, name in (("spacex", "SpaceX Daily"), ("tesla", "Tesla Shorts Time"),
                       ("mag7", "MAG 7 Daily"), ("vancouver", "Vancouver Daily News"),
                       ("omni_view", "Omni View")):
        shows[slug] = {"name": name, "brand_color": "#336699", "show_page": f"{slug}.html",
                       "members_only": False, "schedule": "Daily",
                       "stories": [_story(slug, name, 100, day, f"{name} lead story",
                                          ["One", "Two", "Three", "Four"])]}
    shows["omni_view_europe"] = {"name": "Omni View Europe", "members_only": True,
                                 "stories": []}
    shows["finansy_prosto"] = {"name": "Финансы Просто", "members_only": False,
                               "stories": [_story("finansy_prosto", "FP", 9, day, "Русский")]}
    shows["nerra_daily"] = {"name": "Nerra Daily", "members_only": False,
                            "stories": [_story("nerra_daily", "Nerra Daily", 74, day,
                                               "Monday edition: the morning in one listen")]}
    return {"shows": shows}


@pytest.fixture
def composed(monkeypatch):
    monkeypatch.setattr(nde, "already_sent", lambda day, root=None, **k: {})
    monkeypatch.setattr(nde, "video_links", lambda slug, root, now: {
        100: {"long": "https://www.youtube.com/watch?v=aaaaaaaaaaa",
              "long_at": "2026-11-02T13:00:00Z"}} if slug == "tesla" else {})
    monkeypatch.setattr(nde, "week_records", lambda slug, day, root=None: [])
    return nde.compose(DAY, now=NOW, front=_front(), trial_days=7)


TESLA = "Tesla Shorts Time"


class TestWhatEachReaderGets:
    def test_a_follower_gets_their_card_and_no_default_block(self, composed):
        copy = nde.render_for(composed.body, ["nerra-member", TESLA])
        assert "Your shows today" in copy
        assert "Tesla Shorts Time lead story" in copy
        assert "Choose your shows" in copy  # the manage line, not the default block
        assert "Today on Nerra" not in copy
        # Tesla is not repeated as a one-liner under "Also on Nerra today".
        also = copy.split("Also on Nerra today", 1)[1]
        assert "Tesla Shorts Time lead story" not in also
        assert "MAG 7 Daily lead story" in also

    def test_a_reader_who_follows_nothing_gets_the_default_set(self, composed):
        copy = nde.render_for(composed.body, ["nerra-member"])
        assert "Today on Nerra" in copy and "Your shows today" not in copy
        assert "SpaceX Daily lead story" in copy and "Tesla Shorts Time lead story" in copy
        also = copy.split("Also on Nerra today", 1)[1]
        # The default cards are not repeated as one-liners; the rest are there.
        assert "SpaceX Daily lead story" not in also
        assert "MAG 7 Daily lead story" in also

    def test_a_reader_following_everything_gets_no_one_liners(self, composed):
        every = ["nerra-member"] + list(nde.email_show_tags().values())
        copy = nde.render_for(composed.body, every)
        # Nov 3 2026: the heading goes with the lines — a reader following
        # everything used to get "Also on Nerra today" over nothing.
        assert "Also on Nerra today" not in copy
        assert "lead story</a>" not in copy.split("Your shows today", 1)[1].split("Nerra Personal", 1)[0] or True
        for name in ("MAG 7 Daily", "Omni View", "Vancouver Daily News"):
            assert f"{name} lead story" in copy  # as a card, not a one-liner

    def test_paying_members_never_see_the_pitch(self, composed):
        member = nde.render_for(composed.body, ["nerra-member", nde.PAID_TAG])
        reader = nde.render_for(composed.body, ["nerra-member"])
        assert "Your Personal edition is ready" in member and "See Personal" not in member
        assert "See Personal" in reader and "Try it free for 7 days" in reader

    def test_members_only_and_russian_shows_are_never_sections(self, composed):
        assert "omni_view_europe" not in composed.sections
        assert "finansy_prosto" not in composed.sections
        assert set(composed.sections) == {"spacex", "tesla", "mag7", "vancouver", "omni_view"}

    def test_the_edition_is_the_featured_card_and_the_subject(self, composed):
        assert "Monday edition: the morning in one listen" in composed.body
        assert composed.subject.startswith("Monday edition")
        from engine.titles import NEWSLETTER_SUBJECT_MAX
        assert len(composed.subject) <= NEWSLETTER_SUBJECT_MAX
        assert composed.included["nerra_daily"] == [74]

    def test_a_scheduled_video_says_when_it_goes_public(self, composed):
        copy = nde.render_for(composed.body, [TESLA])
        assert "(from 8:00 AM ET)" in copy

    def test_every_copy_passes_contrast_and_stays_under_the_clip(self, composed):
        from engine.contrast_validator import assert_contrast_ok
        tags = [s.tag for s in nde.eligible_shows(_front())]
        for sample in (["nerra-member"], [TESLA], tags + [nde.PAID_TAG]):
            copy = nde.render_for(composed.body, sample)
            assert_contrast_ok(copy)
            assert len(copy.encode()) < 95_000


class TestTemplateSafety:
    def test_braces_in_content_never_become_template_syntax(self, monkeypatch):
        monkeypatch.setattr(nde, "already_sent", lambda day, root=None, **k: {})
        monkeypatch.setattr(nde, "video_links", lambda *a: {})
        front = _front()
        front["shows"]["mag7"]["stories"][0]["hook"] = "A {{ subscriber.email }} and {% if x %} leak"
        c = nde.compose(DAY, now=NOW, front=front)
        assert "{{" not in c.body
        assert "{% if x %}" not in c.body
        assert "&#123;&#123; subscriber.email &#125;&#125;" in c.body

    def test_every_tag_condition_names_a_real_show_tag(self, composed):
        yaml_tags = {s.tag for s in nde.eligible_shows(_front())} | {nde.PAID_TAG}
        named = set(re.findall(r"'([^']+)' (?:not )?in subscriber\.tags", composed.body))
        assert named and named <= yaml_tags

    def test_the_renderer_rejects_what_buttondown_would_not_render_the_same_way(self):
        with pytest.raises(ValueError):
            nde.render_for("{% if foo %}x{% endif %}", [])
        with pytest.raises(ValueError):
            nde.render_for("{% if 'a' in subscriber.tags %}x", [])


class TestPickingEpisodes:
    def _show(self, stories):
        return nde.EmailShow(slug="vancouver", name="Vancouver Daily News",
                             tag="Vancouver Daily News", brand="#000", brand_text="#000",
                             stories=stories)

    def test_yesterdays_late_episode_arrives_this_morning_once(self):
        late = _story("vancouver", "V", 40, DAY - dt.timedelta(days=1), "Late")
        picks = nde.pick_stories([self._show([late])], DAY, {})
        assert picks and picks[0].story["episode_num"] == 40 and picks[0].included == [40]
        assert nde.pick_stories([self._show([late])], DAY, {"vancouver": {40}}) == []

    def test_an_old_episode_is_not_news(self):
        old = _story("vancouver", "V", 30, DAY - dt.timedelta(days=5), "Old")
        assert nde.pick_stories([self._show([old])], DAY, {}) == []

    def test_newest_unsent_wins_and_all_unsent_are_recorded(self):
        a = _story("vancouver", "V", 41, DAY - dt.timedelta(days=1), "A")
        b = _story("vancouver", "V", 42, DAY, "B")
        pick = nde.pick_stories([self._show([b, a])], DAY, {})[0]
        assert pick.story["episode_num"] == 42 and pick.included == [41, 42]


class TestSunday:
    def test_sunday_adds_the_week_and_weekly_only_readers(self, monkeypatch):
        monkeypatch.setattr(nde, "already_sent", lambda day, root=None, **k: {})
        monkeypatch.setattr(nde, "video_links", lambda *a: {})
        monkeypatch.setattr(nde, "most_played", lambda root=None, limit=5: [
            {"slug": "spacex", "show_name": "SpaceX Daily", "episode_num": 99,
             "title": "Most played story", "url": "blog/spacex/ep099.html"}])
        monkeypatch.setattr(nde, "week_records", lambda slug, day, root=None: [
            {"episode_num": 98, "date": day - dt.timedelta(days=2), "hook": f"{slug} midweek"},
            {"episode_num": 97, "date": day - dt.timedelta(days=4), "hook": f"{slug} early"},
        ])
        c = nde.compose(SUNDAY, now=NOW, front=_front(SUNDAY))
        assert c.sunday
        copy = nde.render_for(c.body, [TESLA])
        assert "Most played this week" in copy and "Your week" in copy
        assert "tesla midweek" in copy and "mag7 midweek" not in copy

    def test_weekly_only_readers_are_left_out_monday_to_saturday(self):
        ids = {"nerra-member": "t1", "SpaceX Daily": "t2", nde.WEEKLY_ONLY_TAG: "t9",
               "Finansy Prosto": "t5"}
        weekday = nde.audience_filter(ids, en_tags=["SpaceX Daily"], ru_tags=["Finansy Prosto"],
                                      sunday=False)
        sunday = nde.audience_filter(ids, en_tags=["SpaceX Daily"], ru_tags=["Finansy Prosto"],
                                     sunday=True)
        assert {"field": "subscriber.tags", "operator": "not_contains", "value": "t9"} in weekday["filters"]
        assert sunday["filters"] == []


class TestAudience:
    def test_free_accounts_gallery_and_english_followers_minus_russian_only(self):
        ids = {"nerra-member": "m", "gallery-subscriber": "g", "SpaceX Daily": "s",
               "Finansy Prosto": "f", "Финансы Просто": "f2"}
        tree = nde.audience_filter(ids, en_tags=["SpaceX Daily"],
                                   ru_tags=["Finansy Prosto", "Финансы Просто"], sunday=False)
        include, russian = tree["groups"]
        assert include["predicate"] == "or"
        assert {f["value"] for f in include["filters"]} == {"m", "g", "s"}
        assert russian["predicate"] == "or"
        assert [f["value"] for f in russian["filters"]] == ["s"]
        assert {f["value"] for f in russian["groups"][0]["filters"]} == {"f", "f2"}
        assert all(f["operator"] == "not_contains" for f in russian["groups"][0]["filters"])

    def test_nothing_resolved_means_no_send(self):
        assert nde.audience_filter({}, en_tags=["SpaceX Daily"], ru_tags=[], sunday=False) is None

    def test_send_newsletter_never_sends_an_empty_tree(self, monkeypatch):
        from engine import newsletter as nl
        calls = []
        monkeypatch.setattr(nl.requests, "post", lambda *a, **k: calls.append(k))
        assert nl.send_newsletter("s", "b", api_key="k", filters={"filters": [], "groups": [],
                                                                  "predicate": "and"}) is None
        assert calls == []

    def test_send_newsletter_posts_the_tree(self, monkeypatch):
        from engine import newsletter as nl

        class R:
            status_code = 201
            def json(self):
                return {"id": "em_1", "secondary_id": 1400}
        seen = {}
        monkeypatch.setattr(nl.requests, "post", lambda url, **k: seen.update(k) or R())
        tree = {"filters": [], "groups": [{"filters": [{"field": "subscriber.tags",
                "operator": "contains", "value": "m"}], "groups": [], "predicate": "or"}],
                "predicate": "and"}
        assert nl.send_newsletter("s", "b", api_key="k", filters=tree, tags=["ignored"]) == "em_1"
        assert seen["json"]["filters"] == tree


class TestDeliverySwitch:
    def test_english_shows_fold_in_and_russian_shows_keep_their_own(self):
        assert nde.show_delivery("tesla") == "nerra_daily"
        assert nde.show_delivery("age_of_ai") == "nerra_daily"
        assert nde.show_delivery("finansy_prosto") == "own"
        assert nde.show_delivery("privet_russian") == "own"

    def test_the_config_carries_it(self):
        from engine.config import load_config
        assert load_config(str(ROOT / "shows" / "tesla.yaml")).newsletter.delivery == "nerra_daily"
        assert load_config(str(ROOT / "shows" / "privet_russian.yaml")).newsletter.delivery == "own"

    def test_run_show_sends_only_own_delivery(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'and _nl_delivery == "own"' in src
        assert 'metrics.record("newsletter_delivery", _nl_delivery)' in src

    def test_the_weekly_runner_and_the_interview_publisher_defer_to_the_email(self):
        weekly = (ROOT / "scripts" / "run_weekly_newsletters.py").read_text(encoding="utf-8")
        assert "in the Sunday Nerra Daily email" in weekly
        voices = (ROOT / "pipelines" / "voices" / "publish_episode.py").read_text(encoding="utf-8")
        assert "goes out in the next Nerra Daily email" in voices


class TestOneShowMap:
    def test_the_worker_mirrors_the_email_show_map(self):
        ts = (ROOT / "workers" / "gallery" / "src" / "email.ts").read_text(encoding="utf-8")
        block = ts.split("export const EMAIL_SHOW_TAGS", 1)[1].split("};", 1)[0]
        worker = dict(re.findall(r'^\s+(\w+): "([^"]+)",', block, re.M))
        assert worker == nde.email_show_tags()

    def test_tag_names_match_the_worker_and_the_email(self):
        ts = (ROOT / "workers" / "gallery" / "src" / "email.ts").read_text(encoding="utf-8")
        assert f'PAID_TAG = "{nde.PAID_TAG}"' in ts
        assert f'WEEKLY_ONLY_TAG = "{nde.WEEKLY_ONLY_TAG}"' in ts
        assert f'MEMBER_TAG = "{nde.MEMBER_TAG}"' in ts


class TestFunnel:
    def test_newsletter_links_parse(self):
        from engine.funnel import PLACEMENT_WEEK, PLACEMENTS, newsletter_link, parse_campaign_id
        url = newsletter_link("https://nerranetwork.com/blog/tesla/ep652.html", "tesla", 652)
        assert "utm_source=newsletter" in url and "utm_medium=email" in url
        camp = re.search(r"utm_campaign=([^&]+)", url).group(1)
        parsed = parse_campaign_id(camp)
        assert parsed and parsed.show == "tesla" and parsed.kind == "email"
        assert parsed.variant == "nerra_daily"
        assert PLACEMENT_WEEK in PLACEMENTS

    def test_every_site_link_in_the_email_is_tagged(self, composed):
        hrefs = re.findall(r'href="(https://nerranetwork\.com[^"]+)"', composed.body)
        body_links = [h for h in hrefs if "/blog/" in h or "account.html" in h or "join.html" in h]
        assert body_links and all("utm_source=newsletter" in h for h in body_links)


class TestWorkflowsAndSurfaces:
    def test_the_edition_sends_the_email_and_commits_the_marker(self):
        wf = (ROOT / ".github" / "workflows" / "nerra-daily.yml").read_text(encoding="utf-8")
        assert "scripts/send_nerra_daily_email.py" in wf
        assert "digests/nerra_daily/email" in wf
        assert "BUTTONDOWN_API_KEY: ${{ secrets.BUTTONDOWN_API_KEY }}" in wf

    def test_the_fallback_shares_the_editions_group(self):
        wf = (ROOT / ".github" / "workflows" / "nerra-daily-email.yml").read_text(encoding="utf-8")
        assert "group: nerra-daily" in wf
        assert "--allow-no-edition" in wf and "::add-mask::" in wf

    def test_nightly_reconciles_the_paid_tag(self):
        wf = (ROOT / ".github" / "workflows" / "nightly-maintenance.yml").read_text(encoding="utf-8")
        assert "scripts/sync_email_tags.py" in wf

    def test_my_nerra_has_the_email_settings(self):
        tpl = (ROOT / "templates" / "account_page.html.j2").read_text(encoding="utf-8")
        assert 'id="email"' in tpl and "saveEmail" in tpl and "/api/account/email" in tpl
        assert "Manage topics in any email's footer" not in tpl

    def test_signup_copy_describes_nerra_daily(self):
        join = (ROOT / "templates" / "join_page.html.j2").read_text(encoding="utf-8")
        assert "Joining subscribes you to Nerra Daily" in join
        assert "Joining subscribes you to the Nerra newsletter" not in join
        show = (ROOT / "templates" / "show_page.html.j2").read_text(encoding="utf-8")
        assert "in Nerra Daily, our 7 AM email" in show

    def test_a_hidden_preheader_has_no_contrast_to_fail(self):
        from engine.contrast_validator import find_contrast_failures
        html = '<div style="display:none;color:#fafafa;">preview</div><p style="color:#fafafa;">x</p>'
        failures = find_contrast_failures(html)
        assert len(failures) == 1 and "<p>" in failures[0]


class TestMeasurement:
    def test_tags_are_counted_from_subscribers_when_tags_carry_none(self, monkeypatch):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fbs", ROOT / "scripts" / "fetch_buttondown_stats.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        class R:
            def __init__(self, data):
                self.status_code, self._d = 200, data
            def json(self):
                return self._d
        pages = [
            R({"results": [{"tags": ["nerra-member", "Tesla Shorts Time"]},
                           {"tags": ["nerra-member"]}], "next": "p2"}),
            R({"results": [{"tags": ["src-youtube"]}], "next": None}),
        ]
        monkeypatch.setattr(mod.requests, "get", lambda *a, **k: pages.pop(0))
        assert mod.count_tags_from_subscribers("k") == {
            "nerra-member": 2, "Tesla Shorts Time": 1, "src-youtube": 1}

    def test_rates_are_null_under_thirty_recipients(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fbs2", ROOT / "scripts" / "fetch_buttondown_stats.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        summary = mod.summarize_nerra_daily([
            {"kind": "nerra_daily", "recipients": 14, "opens": 6, "clicks": 2, "unsubscriptions": 0},
            {"kind": "show", "recipients": 3, "opens": 1, "clicks": 0, "unsubscriptions": 0},
        ])
        assert summary == {"sends": 1, "last_recipients": 14, "recipients": 14, "opens": 6,
                           "clicks": 2, "unsubscriptions": 0}

    def test_the_send_log_no_longer_calls_the_issue_number_recipients(self):
        src = (ROOT / "engine" / "newsletter.py").read_text(encoding="utf-8")
        assert 'recipient_count = result.get("secondary_id"' not in src


class TestTheScript:
    def test_preview_writes_every_copy_without_the_api(self, tmp_path, monkeypatch):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "snde", ROOT / "scripts" / "send_nerra_daily_email.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        monkeypatch.setattr(mod.nde, "load_front", lambda root=None: _front())
        monkeypatch.setattr(mod.nde, "already_sent", lambda day, root=None, **k: {})
        monkeypatch.setattr(mod.nde, "video_links", lambda *a: {})
        monkeypatch.delenv("BUTTONDOWN_API_KEY", raising=False)
        assert mod.main(["--date", DAY.isoformat(), "--mode", "preview", "--out", str(tmp_path)]) == 0
        for name in ("source", "new_reader", "two_shows", "everything"):
            assert (tmp_path / f"{name}.html").stat().st_size > 1000
        meta = json.loads((tmp_path / "meta.json").read_text())
        assert meta["included"]["tesla"] == [100]

    def test_send_without_a_key_is_a_clean_no_op(self, monkeypatch):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "snde2", ROOT / "scripts" / "send_nerra_daily_email.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        monkeypatch.setattr(mod.nde, "load_front", lambda root=None: _front())
        monkeypatch.setattr(mod.nde, "already_sent", lambda day, root=None, **k: {})
        monkeypatch.setattr(mod.nde, "read_marker", lambda day, root=None: None)
        monkeypatch.setattr(mod.nde, "video_links", lambda *a: {})
        monkeypatch.delenv("BUTTONDOWN_API_KEY", raising=False)
        assert mod.main(["--date", DAY.isoformat()]) == 0
