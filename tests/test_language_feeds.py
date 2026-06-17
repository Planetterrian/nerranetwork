"""Drift guards for the per-language podcast RSS feeds (June 2026).

The multilingual stage records FR/RU/ES/ZH tracks on each episode's
summaries record; ``engine.language_feeds`` turns those into standalone
Apple/Spotify-subscribable feeds (``<show>_podcast.<lang>.rss``). These
tests pin the contract without spending Grok credits or hitting the network.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"

pytest.importorskip("feedgen", reason="feedgen required to build feeds")


def _write_summaries(path: Path, records) -> None:
    path.write_text(
        json.dumps({"podcast": "demo", "summaries": records}, ensure_ascii=False),
        encoding="utf-8",
    )


def _two_lang_records():
    return [
        {
            "date": "2026-06-15",
            "episode_num": 4,
            "episode_title": "Ep 4: English title",
            "audio_url": "https://audio.nerranetwork.com/demo/Ep004.mp3",
            "translations": {
                "fr": {
                    "audio_url": "https://audio.nerranetwork.com/demo/Ep004.fr.mp3",
                    "title": "Ép 4 : titre français",
                    "description": "description française",
                    "duration_sec": 347.7,
                },
            },
        },
        {
            "date": "2026-06-14",
            "episode_num": 3,
            "episode_title": "Ep 3: English title",
            "audio_url": "https://audio.nerranetwork.com/demo/Ep003.mp3",
            "translations": {
                "fr": {
                    "audio_url": "https://audio.nerranetwork.com/demo/Ep003.fr.mp3",
                    "title": "Ép 3 : titre français",
                    "description": "description française 3",
                    "duration_sec": 493.1,
                    "bytes": 15000000,
                },
                # An English-only language (no track) must be skipped.
            },
        },
        {
            "date": "2026-06-13",
            "episode_num": 2,
            "episode_title": "Ep 2: English only",
            "audio_url": "https://audio.nerranetwork.com/demo/Ep002.mp3",
            # No translations at all.
        },
    ]


def _build(tmp_path, lang="fr"):
    from engine import language_feeds

    summaries = tmp_path / "summaries_demo.json"
    _write_summaries(summaries, _two_lang_records())
    out = tmp_path / language_feeds.feed_filename("demo_podcast.rss", lang)
    result = language_feeds.build_language_feed(
        slug="demo",
        lang=lang,
        summaries_path=summaries,
        out_path=out,
        guid_prefix="demo",
        channel_title="Demo Show (Français)",
        channel_description="desc",
        channel_link="https://nerranetwork.com/demo.html",
        channel_author="Patrick",
        channel_email="patrick@planetterrian.com",
        channel_image="https://nerranetwork.com/cover.jpg",
    )
    return out, result


# ---------------------------------------------------------------------------
# Naming + locale helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_feed_filename_inserts_lang(self):
        from engine.language_feeds import feed_filename

        assert feed_filename("spacex_podcast.rss", "fr") == "spacex_podcast.fr.rss"
        assert feed_filename("podcast.rss", "zh") == "podcast.zh.rss"

    def test_supported_languages(self):
        from engine.language_feeds import supported_feed_languages

        assert set(supported_feed_languages()) == {"fr", "ru", "es", "zh"}

    def test_locale_is_region_qualified(self):
        from engine.language_feeds import feed_locale

        assert feed_locale("fr") == "fr-fr"
        assert feed_locale("zh") == "zh-cn"


# ---------------------------------------------------------------------------
# Feed construction
# ---------------------------------------------------------------------------

class TestBuildFeed:
    def test_builds_and_returns_count(self, tmp_path):
        out, result = _build(tmp_path)
        assert result is not None
        path, count = result
        # Ep4 + Ep3 have FR tracks; Ep2 has none.
        assert count == 2
        assert out.exists()

    def test_only_translated_episodes_listed(self, tmp_path):
        out, _ = _build(tmp_path)
        root = ET.parse(out).getroot()
        items = root.find("channel").findall("item")
        assert len(items) == 2
        titles = [it.find("title").text for it in items]
        assert all("français" in t.lower() for t in titles)

    def test_newest_episode_first(self, tmp_path):
        out, _ = _build(tmp_path)
        root = ET.parse(out).getroot()
        eps = [
            int(it.find(f"{{{ITUNES}}}episode").text)
            for it in root.find("channel").findall("item")
        ]
        assert eps == [4, 3]

    def test_enclosure_points_at_lang_track(self, tmp_path):
        out, _ = _build(tmp_path)
        root = ET.parse(out).getroot()
        for it in root.find("channel").findall("item"):
            url = it.find("enclosure").get("url")
            assert url.endswith(".fr.mp3"), url

    def test_channel_language_is_locale(self, tmp_path):
        out, _ = _build(tmp_path)
        root = ET.parse(out).getroot()
        assert root.find("channel/language").text == "fr-fr"

    def test_guid_is_deterministic_across_rebuilds(self, tmp_path):
        out, _ = _build(tmp_path)
        guids_a = [
            it.find("guid").text for it in ET.parse(out).getroot().find("channel").findall("item")
        ]
        _build(tmp_path)  # rebuild
        guids_b = [
            it.find("guid").text for it in ET.parse(out).getroot().find("channel").findall("item")
        ]
        assert guids_a == guids_b
        assert guids_a[0] == "demo-fr-ep004-20260615"

    def test_enclosure_length_uses_bytes_when_present(self, tmp_path):
        out, _ = _build(tmp_path)
        root = ET.parse(out).getroot()
        # Ep3 carries an explicit bytes field.
        ep3 = [
            it for it in root.find("channel").findall("item")
            if it.find(f"{{{ITUNES}}}episode").text == "3"
        ][0]
        assert ep3.find("enclosure").get("length") == "15000000"

    def test_no_feed_for_language_without_tracks(self, tmp_path):
        from engine import language_feeds

        summaries = tmp_path / "summaries_demo.json"
        _write_summaries(summaries, _two_lang_records())
        out = tmp_path / "demo_podcast.zh.rss"
        result = language_feeds.build_language_feed(
            slug="demo",
            lang="zh",
            summaries_path=summaries,
            out_path=out,
            guid_prefix="demo",
            channel_title="x",
            channel_description="y",
            channel_link="https://nerranetwork.com/demo.html",
            channel_author="Patrick",
            channel_email="patrick@planetterrian.com",
        )
        assert result is None
        assert not out.exists()

    def test_feed_is_valid_xml_with_locked_tag(self, tmp_path):
        out, _ = _build(tmp_path)
        root = ET.parse(out).getroot()  # raises on invalid XML
        PODCAST = "https://podcastindex.org/namespace/1.0"
        assert root.find(f"channel/{{{PODCAST}}}locked") is not None


# ---------------------------------------------------------------------------
# Channel i18n cache
# ---------------------------------------------------------------------------

class TestChannelI18n:
    def test_fallback_when_no_cache_no_translate(self, tmp_path):
        from engine import language_feeds

        summaries = tmp_path / "summaries_demo.json"
        _write_summaries(summaries, [])
        title, desc = language_feeds.resolve_channel_i18n(
            summaries, "fr", "Demo Show", "English description",
        )
        assert title == "Demo Show (Français)"
        assert desc == "English description"

    def test_uses_cache_without_calling_translate(self, tmp_path):
        from engine import language_feeds

        summaries = tmp_path / "summaries_demo.json"
        _write_summaries(summaries, [])
        language_feeds.save_channel_i18n(
            summaries, {"fr": {"title": "Démo", "description": "desc fr"}}
        )

        def _boom(*a, **k):  # must NOT be called when cache hits
            raise AssertionError("translate_fn called despite cache hit")

        title, desc = language_feeds.resolve_channel_i18n(
            summaries, "fr", "Demo Show", "English", translate_fn=_boom,
        )
        assert title == "Démo"
        assert desc == "desc fr"

    def test_translate_fn_populates_cache(self, tmp_path):
        from engine import language_feeds

        summaries = tmp_path / "summaries_demo.json"
        _write_summaries(summaries, [])
        calls = []

        def _fake(t, d, lang):
            calls.append(lang)
            return f"{t}-{lang}", f"{d}-{lang}"

        title, desc = language_feeds.resolve_channel_i18n(
            summaries, "es", "Demo", "Desc", translate_fn=_fake,
        )
        assert title == "Demo-es"
        assert calls == ["es"]
        # Second call hits the now-populated cache (no second translate).
        title2, _ = language_feeds.resolve_channel_i18n(
            summaries, "es", "Demo", "Desc", translate_fn=_fake,
        )
        assert title2 == "Demo-es"
        assert calls == ["es"]
