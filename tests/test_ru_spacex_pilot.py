"""Drift guards for the RU SpaceX funnel pilot (July 2026).

The pilot is three promises to one audience, and each one can break
silently:

  1. Every @NerraRU SpaceX Short points at ``ru/spacex.html``. If the
     page moves or stops being generated, the highest-reach surface in
     the network points at a 404 and nothing in the pipeline notices.
  2. The page asks for an email in Russian, in exchange for one clearly
     named letter. If English copy leaks in, the ask stops working.
  3. That letter actually gets sent. A capture form whose newsletter
     never arrives is worse than no form.
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

    def test_it_has_exactly_one_capture_form(self, landing_html):
        # A second call to action is how a landing page stops converting.
        # In particular the site footer's show-picker must be suppressed:
        # it offers fifteen ENGLISH show names and would tag a Russian
        # visitor onto English dailies.
        assert landing_html.count('id="ru-capture-form"') == 1
        assert len(re.findall(r'<input\s+type="email"', landing_html)) == 1
        assert "nn-footer-subscribe" not in landing_html

    def test_other_pages_keep_the_footer_subscribe(self):
        # The suppression flag defaults to false — no other page changed.
        other = ROOT / "spacex.html"
        if not other.exists():
            pytest.skip("spacex.html not generated in this checkout")
        assert "nn-footer-subscribe" in other.read_text(encoding="utf-8")

    def test_the_form_names_the_pilot_list(self, landing_html):
        # Must match shows/spacex.yaml funnel.capture_tag and the
        # Worker's SUBSCRIBE_LISTS key, or captures land untagged.
        assert '"ru-spacex"' in landing_html

    def test_it_posts_to_the_subscribe_worker(self, landing_html):
        assert '/api/subscribe' in landing_html

    def test_it_fires_a_conversion_event(self, landing_html):
        # The only place the funnel learns a visit became a capture.
        assert "newsletter_signup" in landing_html

    def test_the_cta_copy_is_russian(self, landing_html):
        for phrase in ("Подписаться", "Хроника SpaceX", "выпуск"):
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
