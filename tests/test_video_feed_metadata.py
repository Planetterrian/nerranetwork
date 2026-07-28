"""Drift guards for the video feeds' episode-level metadata.

Until July 2026 the five video feeds carried exactly one image (the
channel cover), no transcripts, no chapters, no keywords and no
``<itunes:type>`` — while the *audio* feed for the same show had
advertised transcripts and chapters since day one and the artifacts sat
committed in ``digests/<slug>/``, publicly served. The video feed simply
never pointed at them.

Two failure modes this pins:

* **A sidecar URL that 404s is worse than none.** Apple and Podcast
  Index both fetch ``<podcast:transcript>`` and ``<podcast:chapters>``;
  a dead URL is a validation error against the show. So the tags are
  emitted only when the file exists on disk at build time.
* **feedgen has no ``itunes_keywords`` setter.** ``engine.publisher``
  called it inside a bare ``except: pass`` from May to July 2026, so
  every feed in the network shipped without keywords while the code
  claimed otherwise. The tag is now injected as XML, and this file
  asserts it actually lands.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from engine.video_feed import (  # noqa: E402
    PODCAST_NS,
    _episode_stem,
    _sidecar_assets,
    build_video_feed,
)

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


def _write_summaries(path: Path, *, episodes: int = 2, image: str = "") -> None:
    records = []
    for i in range(1, episodes + 1):
        track = {
            "url": f"https://audio.nerranetwork.com/video/demo/Demo_Ep{i:03d}_20260727.mp4",
            "bytes": 1234567,
            "duration_sec": 600.0,
            "filename": f"Demo_Ep{i:03d}_20260727.mp4",
        }
        if image:
            track["image_url"] = image
        records.append({
            "episode_num": i,
            "date": "2026-07-27",
            "episode_title": f"Episode {i}",
            "summary": "Body text.",
            "video": track,
        })
    path.write_text(json.dumps({"summaries": records}), encoding="utf-8")


def _build(tmp_path: Path, **kwargs):
    summaries = tmp_path / "summaries.json"
    _write_summaries(summaries, **kwargs.pop("summaries_kwargs", {}))
    out = tmp_path / "demo.video.rss"
    result = build_video_feed(
        slug="demo",
        summaries_path=summaries,
        out_path=out,
        guid_prefix="demo",
        channel_title="Demo — Video Edition",
        channel_description="A demo.",
        channel_link="https://nerranetwork.com/demo.html",
        channel_author="Nerra Network",
        channel_email="patrick@planetterrian.com",
        channel_image="https://nerranetwork.com/assets/covers/demo.jpg",
        **kwargs,
    )
    assert result is not None
    return out, ET.parse(out).getroot().find("channel")


class TestEpisodeStem:
    """The stem is what every sidecar URL is built from."""

    def test_prefers_the_stored_filename(self):
        assert _episode_stem({"filename": "Demo_Ep046_20260727.mp4",
                              "url": "https://x/other.mp4"}) == "Demo_Ep046_20260727"

    def test_falls_back_to_the_enclosure_basename(self):
        """Index-synthesised records predate the filename field."""
        assert _episode_stem(
            {"url": "https://audio.nerranetwork.com/video/spacex/"
                    "SpaceX_Daily_Ep046_20260727.mp4"}) == "SpaceX_Daily_Ep046_20260727"

    def test_strips_a_query_string(self):
        assert _episode_stem({"url": "https://x/A_Ep001.mp4?v=2"}) == "A_Ep001"

    def test_empty_track_is_empty_not_an_error(self):
        assert _episode_stem({}) == ""


class TestSidecarsOnlyWhenTheFileExists:
    """A transcript URL that 404s is a validation error against the show."""

    def test_nothing_emitted_without_an_assets_root(self, tmp_path):
        assert _sidecar_assets(
            num=1, track={"filename": "Demo_Ep001_20260727.mp4"},
            base_url="https://nerranetwork.com", audio_subdir="digests/demo",
            assets_root=None) == []

    def test_nothing_emitted_when_the_files_are_absent(self, tmp_path):
        assert _sidecar_assets(
            num=1, track={"filename": "Demo_Ep001_20260727.mp4"},
            base_url="https://nerranetwork.com", audio_subdir="digests/demo",
            assets_root=tmp_path) == []

    def test_json_transcript_wins_over_txt(self, tmp_path):
        d = tmp_path / "digests" / "demo"
        d.mkdir(parents=True)
        (d / "Demo_Ep001_20260727_transcript.json").write_text("{}")
        (d / "Demo_Ep001_20260727_transcript.txt").write_text("hi")
        tags = dict((t, a) for t, a in _sidecar_assets(
            num=1, track={"filename": "Demo_Ep001_20260727.mp4"},
            base_url="https://nerranetwork.com", audio_subdir="digests/demo",
            assets_root=tmp_path))
        assert tags["transcript"]["type"] == "application/json"
        assert tags["transcript"]["url"].endswith("_transcript.json")

    def test_txt_transcript_is_the_fallback(self, tmp_path):
        d = tmp_path / "digests" / "demo"
        d.mkdir(parents=True)
        (d / "Demo_Ep001_20260727_transcript.txt").write_text("hi")
        tags = dict(_sidecar_assets(
            num=1, track={"filename": "Demo_Ep001_20260727.mp4"},
            base_url="https://nerranetwork.com", audio_subdir="digests/demo",
            assets_root=tmp_path))
        assert tags["transcript"]["type"] == "text/plain"

    def test_chapters_url_uses_the_episode_number(self, tmp_path):
        d = tmp_path / "digests" / "demo"
        d.mkdir(parents=True)
        (d / "chapters_ep007.json").write_text("[]")
        tags = dict(_sidecar_assets(
            num=7, track={"filename": "Demo_Ep007_20260727.mp4"},
            base_url="https://nerranetwork.com", audio_subdir="digests/demo",
            assets_root=tmp_path))
        assert tags["chapters"] == {
            "url": "https://nerranetwork.com/digests/demo/chapters_ep007.json",
            "type": "application/json+chapters"}


class TestRenderedFeed:
    def test_channel_declares_episodic_type(self, tmp_path):
        _, channel = _build(tmp_path)
        assert channel.findtext(f"{{{ITUNES_NS}}}type") == "episodic"

    def test_keywords_land_despite_feedgen_having_no_setter(self, tmp_path):
        """The regression this guards: publisher.py called a method that
        does not exist, inside a bare except, for two months."""
        _, channel = _build(tmp_path, channel_keywords="alpha, beta ,, gamma")
        assert channel.findtext(f"{{{ITUNES_NS}}}keywords") == "alpha, beta, gamma"

    def test_no_keywords_tag_when_none_configured(self, tmp_path):
        _, channel = _build(tmp_path)
        assert channel.find(f"{{{ITUNES_NS}}}keywords") is None

    def test_item_artwork_emitted_when_recorded(self, tmp_path):
        art = "https://gallery.nerranetwork.com/demo/2026-07-27/ep001/abc.jpg"
        _, channel = _build(tmp_path, summaries_kwargs={"image": art})
        images = [it.findtext(f"{{{ITUNES_NS}}}image") or
                  (it.find(f"{{{ITUNES_NS}}}image").get("href")
                   if it.find(f"{{{ITUNES_NS}}}image") is not None else None)
                  for it in channel.findall("item")]
        assert all(i == art for i in images), images

    def test_items_inherit_the_cover_when_no_artwork_recorded(self, tmp_path):
        """Every episode published before engine.episode_art existed —
        must reproduce the old behaviour, not emit an empty tag."""
        _, channel = _build(tmp_path)
        for item in channel.findall("item"):
            assert item.find(f"{{{ITUNES_NS}}}image") is None

    def test_sidecars_appear_on_every_item(self, tmp_path):
        digests = tmp_path / "digests" / "demo"
        digests.mkdir(parents=True)
        for i in (1, 2):
            (digests / f"Demo_Ep{i:03d}_20260727_transcript.json").write_text("{}")
            (digests / f"chapters_ep{i:03d}.json").write_text("[]")
        _, channel = _build(tmp_path, audio_subdir="digests/demo",
                            assets_root=tmp_path)
        items = channel.findall("item")
        assert len(items) == 2
        for item in items:
            assert item.find(f"{{{PODCAST_NS}}}transcript") is not None
            assert item.find(f"{{{PODCAST_NS}}}chapters") is not None

    def test_feed_stays_well_formed_after_every_injection(self, tmp_path):
        digests = tmp_path / "digests" / "demo"
        digests.mkdir(parents=True)
        (digests / "Demo_Ep001_20260727_transcript.json").write_text("{}")
        out, _ = _build(tmp_path, channel_keywords="a, b",
                        audio_subdir="digests/demo", assets_root=tmp_path,
                        summaries_kwargs={"image": "https://x/a.jpg"})
        # Four separate passes rewrite this file; a malformed feed would
        # de-list the show, so parse it end to end.
        root = ET.parse(out).getroot()
        assert root.tag == "rss"
        assert root.find("channel/item/enclosure").get("type") == "video/mp4"


class TestRealShowsProduceTheMetadata:
    """The real show configs and the real committed artifacts.

    Deliberately rebuilds each feed into ``tmp_path`` rather than
    asserting on the committed ``*.video.rss``. Those files are build
    output: they are regenerated by the nightly run, so a test that
    reads them fails on a fresh checkout until the pipeline has run once
    — and passes for the wrong reason afterwards. Building here proves
    the config plus the committed transcripts and chapters are enough,
    which is the property that actually matters.
    """

    @pytest.mark.parametrize("slug", [
        "tesla", "spacex", "models_agents",
        "models_agents_beginners", "fascinating_frontiers",
    ])
    def test_every_item_gets_a_transcript_and_chapters(self, slug, tmp_path):
        from engine.config import load_config
        from engine.video_index import index_path

        config = load_config(ROOT / "shows" / f"{slug}.yaml")
        vp = getattr(config, "video_podcast", None)
        if not (vp and vp.enabled):
            pytest.skip(f"{slug} has no video edition")

        pub = config.publishing
        summaries = ROOT / pub.summaries_json
        if not summaries.exists():
            pytest.skip(f"{slug} has no summaries file")

        result = build_video_feed(
            slug=slug,
            summaries_path=summaries,
            out_path=tmp_path / "out.video.rss",
            guid_prefix=pub.guid_prefix or slug,
            channel_title=f"{pub.rss_title or config.name}{vp.title_suffix}",
            channel_description=pub.rss_description or config.description,
            channel_link=pub.rss_link or pub.base_url,
            channel_author=pub.rss_author or "Nerra Network",
            channel_email=pub.rss_email or "patrick@planetterrian.com",
            channel_image=vp.channel_image or pub.rss_image or "",
            channel_keywords=getattr(pub, "rss_keywords", "") or "",
            base_url=pub.base_url or "https://nerranetwork.com",
            max_episodes=vp.max_episodes,
            index_path=index_path(config, ROOT),
            audio_subdir=getattr(pub, "audio_subdir", "digests") or "digests",
            assets_root=ROOT,
        )
        if result is None:
            pytest.skip(f"{slug} has no video episodes yet")

        channel = ET.parse(result[0]).getroot().find("channel")
        items = channel.findall("item")
        assert items, f"{slug} built a feed with no items"
        for item in items:
            guid = item.findtext("guid")
            assert item.find(f"{{{PODCAST_NS}}}transcript") is not None, (
                f"{slug} {guid}: no transcript — is the committed "
                f"*_transcript.json missing for this episode?")
            assert item.find(f"{{{PODCAST_NS}}}chapters") is not None, (
                f"{slug} {guid}: no chapters")

