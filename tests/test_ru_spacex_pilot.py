"""Drift guards for the RU SpaceX funnel pilot (July 2026; the ask rewritten
Nov 3 2026).

The pilot is promises to one audience, and each one can break silently:

  1. Every @NerraRU SpaceX Short points at ``ru/spacex.html``. If the
     page moves or stops being generated, the highest-reach surface in
     the network points at a 404 and nothing in the pipeline notices.
  2. The page asks, in Russian, for the thing a Shorts-feed audience can
     act on — subscribe to @NerraRU, add the Russian RSS — and promises
     nothing it cannot deliver. The email form and its Sunday letter
     captured nobody in three months (register ``ru-spacex-pilot-2026-07-30``:
     MISS) and are gone; no copy may promise a letter again.
  3. The retired letter's rules stay pinned (``TestWeeklyLetter``) for the
     one release the script survives — remove both together.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LANDING = ROOT / "ru" / "spacex.html"


@pytest.fixture(scope="module")
def landing_html():
    if not LANDING.exists():
        pytest.skip("ru/spacex.html not generated in this checkout")
    return LANDING.read_text(encoding="utf-8")


class TestLandingPage:
    def test_it_is_generated(self):
        assert LANDING.exists(), (
            "ru/spacex.html is the destination every @NerraRU SpaceX "
            "description points at — if it stops being generated those "
            "links 404")

    def test_it_declares_russian(self, landing_html):
        assert '<html lang="ru"' in landing_html

    def test_it_has_no_email_form(self, landing_html):
        # Nov 3 2026: the capture form captured nobody in three months. No
        # form, no email input, no post to the subscribe Worker and no
        # conversion event — a surface that measures nothing must not
        # pretend to. The site footer's show-picker stays suppressed: it
        # offers fifteen ENGLISH show names and would tag a Russian
        # visitor onto English dailies (one ask per landing page).
        assert "<form" not in landing_html
        assert not re.findall(r'<input\s+type="email"', landing_html)
        assert "/api/subscribe" not in landing_html
        assert "newsletter_signup" not in landing_html
        assert "nn-footer-subscribe" not in landing_html

    def test_other_pages_keep_the_footer_subscribe(self):
        # The suppression flag defaults to false — no other page changed.
        other = ROOT / "spacex.html"
        if not other.exists():
            pytest.skip("spacex.html not generated in this checkout")
        assert "nn-footer-subscribe" in other.read_text(encoding="utf-8")

    def test_it_asks_for_the_channel_subscribe_and_the_rss(self, landing_html):
        # The ask a Shorts-feed audience (89% of @NerraRU's views) can act
        # on: the channel's subscribe URL (one owner,
        # engine.video_metadata) and the show's own Russian feed.
        from engine.video_metadata import channel_subscribe_url

        ask = landing_html.split('id="ru-ask"', 1)[1].split("</div>", 1)[0]
        assert f'href="{channel_subscribe_url("ru")}"' in ask
        assert 'data-ask="subscribe"' in ask
        assert 'href="../spacex_podcast.ru.rss"' in ask
        assert 'data-ask="rss"' in ask
        assert (ROOT / "spacex_podcast.ru.rss").is_file()

    def test_the_hub_link_is_internal_and_carries_no_utm(self, landing_html):
        # One line to the Russian front page; an internal link never
        # carries a utm_* tag (engine.funnel's rule).
        hub = re.findall(r'href="(\.\./ru/index\.html[^"]*)"[^>]*hreflang="ru"', landing_html)
        assert hub, "the ask block links ru/index.html"
        assert all("utm_" not in h for h in hub)
        assert "utm_" not in landing_html.split('id="ru-ask"', 1)[1].split("</section>", 1)[0]

    def test_it_promises_no_letter(self, landing_html):
        # The Sunday letter is retired; the copy must not promise one
        # (the register entry closes it as a MISS).
        for phrase in ("Хроника", "письмо", "воскресень", "Электронная почта"):
            assert phrase not in landing_html, phrase

    def test_the_cta_copy_is_russian(self, landing_html):
        for phrase in ("Подписаться на @NerraRU", "Добавить RSS", "выпуск"):
            assert phrase in landing_html

    def test_it_links_the_russian_apple_show_not_the_english_one(
            self, landing_html):
        import yaml

        data = yaml.safe_load(
            (ROOT / "shows" / "spacex.yaml").read_text(encoding="utf-8"))
        ru_id = str(data["apple_show_ids"]["ru"])
        en_id = str(data["apple_show_id"])
        assert f"id{ru_id}" in landing_html
        assert f"id{en_id}" not in landing_html

    def test_it_discloses_the_ai_voice_in_russian(self, landing_html):
        assert "ИИ" in landing_html

    def test_the_sitemap_generator_includes_it(self, tmp_path):
        # Asserted against the GENERATOR writing to a temp path, not
        # against the committed sitemap.xml: `lastmod` is derived from
        # local file state, so regenerating the real file outside the
        # pipeline rewrites dozens of unrelated dates (the sitemap
        # landmine at the top of CLAUDE.md). The pipeline's finalize
        # step rebuilds the committed file correctly on every run.
        import generate_html

        out = tmp_path / "sitemap.xml"
        generate_html.generate_sitemap(out=out)
        assert "/ru/spacex.html" in out.read_text(encoding="utf-8")


class TestGeneratorWiring:
    def test_the_generated_path_matches_the_configured_destination(self):
        import generate_html

        target = generate_html._ru_landing_target("spacex")
        assert target == "ru/spacex.html"

    def test_a_show_without_a_russian_destination_generates_nothing(self):
        import generate_html

        assert generate_html._ru_landing_target("omni_view") == ""
        assert generate_html.generate_ru_landing_page(
            "omni_view", dry_run=True) is None

    def test_an_offsite_destination_is_never_treated_as_a_local_page(self,
                                                                     tmp_path,
                                                                     monkeypatch):
        # Guards against generating (and sitemapping) a file for a
        # destination that lives on someone else's domain.
        import generate_html

        yaml_text = (
            "funnel:\n"
            "  destinations:\n"
            "    ru: https://example.com/elsewhere.html\n"
        )
        shows = tmp_path / "shows"
        shows.mkdir()
        (shows / "fake.yaml").write_text(yaml_text, encoding="utf-8")
        monkeypatch.setattr(generate_html, "SHOWS_DIR", shows)
        assert generate_html._ru_landing_target("fake") == ""


class TestRetiredLetter:
    """Nov 3 2026: the Sunday letter never had a reader. The workflow is
    gone; the script says so and survives one release for the rules below."""

    def test_the_sunday_workflow_is_gone(self):
        assert not (ROOT / ".github" / "workflows" / "ru-spacex-weekly.yml").exists()
        for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
            assert "send_ru_spacex_weekly" not in wf.read_text(encoding="utf-8"), wf.name

    def test_the_script_says_it_is_retired(self):
        src = (ROOT / "scripts" / "send_ru_spacex_weekly.py").read_text(encoding="utf-8")
        assert "RETIRED 2026-11-03" in src.split('"""', 2)[1]

    def test_the_lander_copy_cannot_promise_a_letter(self):
        import generate_html

        for slug, copy in generate_html._RU_LANDING_COPY.items():
            text = " ".join(str(v) for v in copy.values())
            assert "Хроника" not in text and "письмо" not in text, slug
            assert "magnet_title" not in copy, slug
        assert "письм" not in " ".join(generate_html._RU_LANDING_ASK.values())


class TestWeeklyLetter:
    def test_it_only_includes_episodes_with_a_russian_track(self, monkeypatch,
                                                            tmp_path):
        import scripts.send_ru_spacex_weekly as weekly

        today = dt.date(2026, 7, 30)
        payload = {
            "summaries": [
                {"episode_num": 1, "date": "2026-07-29",
                 "translations": {"ru": {
                     "audio_url": "https://a/ep1.ru.mp3",
                     "description": "Русский текст"}}},
                # English-only: including it would send a Russian
                # audience English audio.
                {"episode_num": 2, "date": "2026-07-29", "translations": {}},
                # Outside the window.
                {"episode_num": 3, "date": "2026-06-01",
                 "translations": {"ru": {"audio_url": "https://a/ep3.ru.mp3"}}},
            ]
        }
        import json
        d = tmp_path / "digests" / "spacex"
        d.mkdir(parents=True)
        (d / "summaries_spacex.json").write_text(json.dumps(payload))
        monkeypatch.setattr(weekly, "_ROOT", tmp_path)

        episodes = weekly.recent_ru_episodes(days=7, today=today)
        assert [e["episode"] for e in episodes] == [1]

    def test_no_episodes_means_no_send(self, monkeypatch):
        import scripts.send_ru_spacex_weekly as weekly

        monkeypatch.setattr(weekly, "recent_ru_episodes", lambda **_k: [])
        sent = []
        monkeypatch.setattr(
            "engine.newsletter.send_newsletter",
            lambda *a, **k: sent.append(a) or "id")
        assert weekly.main([]) == 0
        assert not sent, "an empty issue spends the pilot's only attention"

    def test_the_body_is_russian_and_links_the_audio(self):
        import scripts.send_ru_spacex_weekly as weekly

        episodes = [{"episode": 49, "date": "2026-07-30",
                     "title": "Заголовок",
                     "description": "Описание выпуска",
                     "audio_url": "https://a/ep49.ru.mp3"}]
        body = weekly.build_body(episodes, None, dt.date(2026, 7, 30))
        assert "Что было на неделе" in body
        assert "https://a/ep49.ru.mp3" in body
        assert "Выпуск 49" in body

    def test_a_stale_launch_window_is_dropped(self, monkeypatch, tmp_path):
        import json

        import scripts.send_ru_spacex_weekly as weekly

        api = tmp_path / "api"
        api.mkdir()
        (api / "spacex_launches.json").write_text(json.dumps(
            {"next": {"name": "Old", "net": "2020-01-01T00:00:00Z"}}))
        monkeypatch.setattr(weekly, "_ROOT", tmp_path)
        # A launch window in the past is stale data, not news.
        assert weekly.next_launch() is None

    def test_the_subject_leads_with_the_week_not_the_brand(self):
        import scripts.send_ru_spacex_weekly as weekly
        from engine.titles import NEWSLETTER_SUBJECT_MAX

        episodes = [{"episode": 49, "date": "2026-07-30", "title": "T",
                     "description": "Новая награда Пентагона на $1,6 млрд",
                     "audio_url": "u"}]
        subject = weekly.build_subject(episodes, dt.date(2026, 7, 30))
        assert subject.startswith("Новая награда")
        # One module owns every title limit in this repo (CLAUDE.md).
        assert len(subject) <= NEWSLETTER_SUBJECT_MAX + len("Хроника SpaceX 🚀") + 3

    def test_it_sends_only_to_the_pilot_tag(self, monkeypatch, tmp_path):
        import scripts.send_ru_spacex_weekly as weekly

        captured = {}

        def _fake_send(subject, body, **kwargs):
            captured.update(kwargs)
            captured["subject"] = subject
            return "email_1"

        monkeypatch.setattr(weekly, "recent_ru_episodes", lambda **_k: [
            {"episode": 1, "date": "2026-07-30", "title": "T",
             "description": "D", "audio_url": "u"}])
        monkeypatch.setattr(weekly, "next_launch", lambda: None)
        monkeypatch.setattr(weekly, "SEND_MARKER", tmp_path / "marker.txt")
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "test")
        monkeypatch.setattr("engine.newsletter.send_newsletter", _fake_send)

        assert weekly.main([]) == 0
        # These subscribers asked for a Russian weekly — adding them to
        # the English daily tag is the fastest way to lose them.
        assert captured["tags"] == ["ru-spacex"]
        assert captured["slug"].isascii()

    def test_the_same_week_guard_blocks_a_double_send(self, monkeypatch,
                                                      tmp_path):
        import scripts.send_ru_spacex_weekly as weekly

        marker = tmp_path / "marker.txt"
        marker.write_text(dt.date.today().isoformat())
        calls = []
        monkeypatch.setattr(weekly, "recent_ru_episodes", lambda **_k: [
            {"episode": 1, "date": "2026-07-30", "title": "T",
             "description": "D", "audio_url": "u"}])
        monkeypatch.setattr(weekly, "next_launch", lambda: None)
        monkeypatch.setattr(weekly, "SEND_MARKER", marker)
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "test")
        monkeypatch.setattr("engine.newsletter.send_newsletter",
                            lambda *a, **k: calls.append(a) or "id")
        assert weekly.main([]) == 0
        assert not calls


class TestWorkerListsStayInSyncWithTheShowConfig:
    def test_the_worker_knows_the_pilot_list(self):
        import yaml

        handlers = (ROOT / "workers" / "gallery" / "src"
                    / "handlers.ts").read_text(encoding="utf-8")
        tag = yaml.safe_load(
            (ROOT / "shows" / "spacex.yaml").read_text(encoding="utf-8")
        )["funnel"]["capture_tag"]
        assert f'"{tag}"' in handlers, (
            f"shows/spacex.yaml captures to {tag!r} but the Worker's "
            "SUBSCRIBE_LISTS has no such list — signups would silently "
            "fall back to the gallery tag")

    def test_the_worker_source_tags_match_engine_funnel(self):
        from engine import funnel

        handlers = (ROOT / "workers" / "gallery" / "src"
                    / "handlers.ts").read_text(encoding="utf-8")
        for source in sorted(funnel.SOURCES):
            tag = funnel.source_tag(source)
            assert f'"{tag}"' in handlers, (
                f"{tag} is produced by engine.funnel but the Worker's "
                "allow-list would drop it, losing the attribution")
