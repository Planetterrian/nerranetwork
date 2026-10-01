"""Transcripts a podcast app can read + channel identity tags (Oct 1 2026).

Every feed item carried one ``<podcast:transcript>`` pointing at the raw
faster-whisper JSON dump — not the Podcasting 2.0 JSON shape, and Apple
ingests only SRT/VTT — so the in-app transcript was absent on every show.
Now ``engine.transcripts`` writes a WebVTT beside the JSON (same segments,
same timebase), the feed carries a ``text/vtt`` tag FIRST and the JSON tag
unchanged, and every rebuilt channel states ``itunes:type``, the spec
UUIDv5 ``podcast:guid`` and a branded ``itunes:author``.
"""

from __future__ import annotations

import datetime
import importlib.util
import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import publisher  # noqa: E402
from engine.transcripts import segments_to_vtt  # noqa: E402

PODCAST_NS = "https://podcastindex.org/namespace/1.0"
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM_NS = "http://www.w3.org/2005/Atom"


def _load_backfill():
    spec = importlib.util.spec_from_file_location(
        "backfill_transcript_vtt", ROOT / "scripts" / "backfill_transcript_vtt.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# WebVTT rendering
# ---------------------------------------------------------------------------

class TestSegmentsToVtt:
    def test_header_and_cue_timestamps(self):
        out = segments_to_vtt([
            {"start": 0.0, "end": 8.94, "text": " first "},
            {"start": 3700.5, "end": 3701.25, "text": "an hour in"},
        ])
        assert out.startswith("WEBVTT\n\n")
        assert "00:00:00.000 --> 00:00:08.940\nfirst\n" in out
        assert "01:01:40.500 --> 01:01:41.250\nan hour in\n" in out
        assert out.endswith("\n")

    def test_empty_text_segments_are_skipped(self):
        out = segments_to_vtt([
            {"start": 0, "end": 1, "text": "   "},
            {"start": 1, "end": 2, "text": ""},
            {"start": 2, "end": 3, "text": "kept"},
        ])
        assert out.count("-->") == 1
        assert "kept" in out

    def test_cue_text_never_contains_the_arrow(self):
        out = segments_to_vtt([{"start": 0, "end": 1, "text": "a --> b & <c>"}])
        body = out.split("\n\n", 1)[1]
        cue_text = body.splitlines()[1]
        assert "-->" not in cue_text
        assert cue_text == "a --&gt; b &amp; &lt;c&gt;"

    def test_zero_length_segment_is_held_open_not_dropped(self):
        out = segments_to_vtt([{"start": 9.0, "end": 9.0, "text": "x"}])
        assert "00:00:09.000 --> 00:00:09.100\nx\n" in out

    def test_no_segments_is_a_valid_header_only_file(self):
        assert segments_to_vtt([]) == "WEBVTT\n"


class TestGenerateTranscriptWritesVtt:
    def test_vtt_written_beside_json_from_the_same_segments(self, monkeypatch, tmp_path):
        from engine import transcripts as tr

        class Word:
            def __init__(self, word, start, end):
                self.word, self.start, self.end, self.probability = word, start, end, 0.9

        class Seg:
            def __init__(self, start, end, text):
                self.start, self.end, self.text = start, end, text
                self.words = [Word(w, start, end) for w in text.split()]

        class Info:
            language = "en"
            language_probability = 0.99
            duration = 12.0

        class Model:
            def __init__(self, *a, **k):
                pass

            def transcribe(self, path, **kw):
                return [Seg(0.0, 4.5, " Hello there. "), Seg(4.5, 12.0, "Second cue.")], Info()

        fake = types.ModuleType("faster_whisper")
        fake.WhisperModel = Model
        monkeypatch.setitem(sys.modules, "faster_whisper", fake)
        audio = tmp_path / "ep.mp3"
        audio.write_bytes(b"\x00" * 16)

        result = tr.generate_transcript(audio, tmp_path, "Show_Ep001_20261001")
        assert result is not None
        vtt = tmp_path / "Show_Ep001_20261001_transcript.vtt"
        assert result.vtt_path == vtt
        assert vtt.exists()
        text = vtt.read_text(encoding="utf-8")
        assert text.startswith("WEBVTT\n\n")
        assert "00:00:00.000 --> 00:00:04.500\nHello there.\n" in text
        assert "00:00:04.500 --> 00:00:12.000\nSecond cue.\n" in text
        # Same timebase as the JSON the chapters key on — never shifted.
        import json
        seg0 = json.loads(result.json_path.read_text(encoding="utf-8"))["segments"][0]
        assert (seg0["start"], seg0["end"]) == (0.0, 4.5)


# ---------------------------------------------------------------------------
# Feed tags
# ---------------------------------------------------------------------------

class _FrozenDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        base = cls(2026, 10, 1, 9, 0, 0, 123456)
        return base.replace(tzinfo=tz) if tz else base


@pytest.fixture
def frozen_clock(monkeypatch):
    """``update_rss_feed`` stamps the guid and lastBuildDate from the
    clock; freeze it so two renders can be compared byte for byte."""
    shim = types.SimpleNamespace(
        datetime=_FrozenDateTime, date=datetime.date, time=datetime.time,
        timezone=datetime.timezone, timedelta=datetime.timedelta,
    )
    monkeypatch.setattr(publisher, "datetime", shim)


BASE = "https://nerranetwork.com"
JSON_URL = f"{BASE}/digests/demo/Demo_Ep001_20261001_transcript.json"
VTT_URL = f"{BASE}/digests/demo/Demo_Ep001_20261001_transcript.vtt"


def _render(tmp_path: Path, name: str = "demo_podcast.rss", *, episode_num: int = 1,
            author: str = "Patrick", **extra) -> Path:
    mp3 = tmp_path / f"Demo_Ep{episode_num:03d}.mp3"
    mp3.write_bytes(b"\x00" * 100)
    rss = tmp_path / name
    publisher.update_rss_feed(
        rss, episode_num, f"Ep {episode_num}: a title", "A description.",
        datetime.date(2026, 10, 1), mp3.name, 600.0, mp3,
        base_url=BASE, audio_subdir="digests/demo", channel_title="Demo",
        channel_link=f"{BASE}/demo.html", channel_description="Demo show.",
        channel_author=author, channel_email="demo@example.com",
        guid_prefix="demo", chapters_url=None, **extra,
    )
    return rss


def _channel(rss: Path) -> ET.Element:
    return ET.parse(str(rss)).getroot().find("channel")


def _item(rss: Path, guid_contains: str) -> ET.Element:
    for item in _channel(rss).findall("item"):
        if guid_contains in (item.findtext("guid") or ""):
            return item
    raise AssertionError(f"no item with guid containing {guid_contains!r}")


class TestTranscriptTags:
    def test_both_tags_emitted_vtt_first_json_unchanged(self, frozen_clock, tmp_path):
        rss = _render(tmp_path, transcript_url=JSON_URL, transcript_vtt_url=VTT_URL)
        tags = _item(rss, "demo-ep001").findall(f"{{{PODCAST_NS}}}transcript")
        assert [(t.get("type"), t.get("url")) for t in tags] == [
            ("text/vtt", VTT_URL),
            ("application/json", JSON_URL),
        ]

    def test_default_kwarg_is_byte_identical(self, frozen_clock, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        without = _render(tmp_path / "a", transcript_url=JSON_URL)
        with_vtt = _render(tmp_path / "b", transcript_url=JSON_URL, transcript_vtt_url=VTT_URL)
        a = without.read_bytes()
        b = with_vtt.read_bytes()
        assert a != b
        vtt_tag = f'<podcast:transcript url="{VTT_URL}" type="text/vtt" />'.encode()
        assert vtt_tag in b
        assert b.replace(vtt_tag, b"", 1) == a, "the VTT url changes exactly one tag"
        # And the no-VTT render is the single JSON tag the feed carried before.
        tags = _item(without, "demo-ep001").findall(f"{{{PODCAST_NS}}}transcript")
        assert [(t.get("type"), t.get("url")) for t in tags] == [("application/json", JSON_URL)]

    def test_rebuild_preserves_both_tags_in_order(self, frozen_clock, tmp_path):
        rss = _render(tmp_path, transcript_url=JSON_URL, transcript_vtt_url=VTT_URL)
        # Next episode has no VTT (a Whisper-less day); ep001 keeps both.
        _render(tmp_path, episode_num=2, transcript_url=JSON_URL.replace("Ep001", "Ep002"))
        tags = _item(rss, "demo-ep001").findall(f"{{{PODCAST_NS}}}transcript")
        assert [t.get("type") for t in tags] == ["text/vtt", "application/json"]
        assert tags[0].get("url") == VTT_URL
        assert len(_channel(rss).findall("item")) == 2

    def test_validation_logs_no_error_when_both_present(self, frozen_clock, tmp_path, caplog):
        import logging
        with caplog.at_level(logging.ERROR, logger="engine.publisher"):
            _render(tmp_path, transcript_url=JSON_URL, transcript_vtt_url=VTT_URL)
        assert not [r for r in caplog.records if "RSS validation" in r.getMessage()]


class TestChannelIdentityTags:
    def test_spec_example_uuid(self):
        # The Podcasting 2.0 spec's own worked example for <podcast:guid>.
        assert publisher.podcast_guid_for_feed_url("https://podnews.net/rss") == \
            "9b024349-ccf0-5f69-a609-6b82873eab3c"
        # Scheme and trailing slash are stripped before hashing.
        assert publisher.podcast_guid_for_feed_url("http://podnews.net/rss/") == \
            "9b024349-ccf0-5f69-a609-6b82873eab3c"

    def test_rebuilt_feed_carries_type_and_guid(self, frozen_clock, tmp_path):
        rss = _render(tmp_path, "demo_podcast.rss")
        ch = _channel(rss)
        assert ch.findtext(f"{{{ITUNES_NS}}}type") == "episodic"
        assert ch.findtext(f"{{{PODCAST_NS}}}guid") == publisher.podcast_guid_for_feed_url(
            f"{BASE}/demo_podcast.rss")
        assert ch.findtext(f"{{{PODCAST_NS}}}guid") == "068c4752-ee55-537e-aa23-814b9c07bd08"

    def test_existing_guid_is_never_rewritten(self, frozen_clock, tmp_path):
        rss = _render(tmp_path)
        text = rss.read_text(encoding="utf-8")
        text = text.replace(
            f"<podcast:guid>{publisher.podcast_guid_for_feed_url(f'{BASE}/demo_podcast.rss')}</podcast:guid>",
            "<podcast:guid>keep-me-0000</podcast:guid>")
        rss.write_text(text, encoding="utf-8")
        _render(tmp_path, episode_num=2)
        assert _channel(rss).findtext(f"{{{PODCAST_NS}}}guid") == "keep-me-0000"
        assert len(_channel(rss).findall(f"{{{PODCAST_NS}}}guid")) == 1
        assert len(_channel(rss).findall(f"{{{ITUNES_NS}}}type")) == 1

    @pytest.mark.parametrize("author,expected", [
        ("Patrick", "Patrick · Nerra Network"),
        ("Omni View", "Omni View · Nerra Network"),
        ("Mira (AI host), Nerra Network", "Mira (AI host), Nerra Network"),
        ("Nerra Network", "Nerra Network"),
        ("nerra network", "nerra network"),
        ("", "Nerra Network"),
    ])
    def test_brand_author_rule(self, author, expected):
        assert publisher.brand_author(author) == expected

    def test_rendered_author_carries_the_brand(self, frozen_clock, tmp_path):
        rss = _render(tmp_path, author="Patrick")
        assert _channel(rss).findtext(f"{{{ITUNES_NS}}}author") == "Patrick · Nerra Network"

    def test_already_branded_author_untouched(self, frozen_clock, tmp_path):
        rss = _render(tmp_path, author="Mira (AI host), Nerra Network")
        assert _channel(rss).findtext(f"{{{ITUNES_NS}}}author") == "Mira (AI host), Nerra Network"

    def test_injector_reads_the_self_link_when_no_url_given(self, tmp_path):
        rss = tmp_path / "x_podcast.rss"
        rss.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<rss xmlns:atom="{ATOM_NS}" xmlns:itunes="{ITUNES_NS}" version="2.0"><channel>'
            '<title>X</title><atom:link href="https://nerranetwork.com/x_podcast.rss" rel="self"/>'
            '<itunes:author>Patrick</itunes:author><item><guid>g1</guid></item>'
            '</channel></rss>', encoding="utf-8")
        assert publisher.inject_channel_identity_tags(rss) is True
        ch = _channel(rss)
        assert ch.findtext(f"{{{PODCAST_NS}}}guid") == publisher.podcast_guid_for_feed_url(
            "https://nerranetwork.com/x_podcast.rss")
        assert ch.findtext(f"{{{ITUNES_NS}}}type") == "episodic"
        assert ch.findtext(f"{{{ITUNES_NS}}}author") == "Patrick · Nerra Network"
        # Channel tags land before the first item, and a second pass is a no-op.
        assert [c.tag for c in ch][-1] == "item"
        assert publisher.inject_channel_identity_tags(rss) is False


# ---------------------------------------------------------------------------
# Backfill script
# ---------------------------------------------------------------------------

class TestBackfillScript:
    def _seed(self, root: Path):
        d = root / "digests" / "demo"
        d.mkdir(parents=True)
        import json
        (d / "Demo_Ep001_20261001_transcript.json").write_text(json.dumps({
            "language": "en", "segments": [
                {"start": 0.0, "end": 2.0, "text": "Hello."},
                {"start": 2.0, "end": 4.0, "text": "World."},
            ]}), encoding="utf-8")
        # A language-track JSON is never rendered (gitignored, never linked).
        (d / "Demo_Ep001_20261001.ru_transcript.json").write_text("{}", encoding="utf-8")
        feed = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<rss xmlns:atom="{ATOM_NS}" xmlns:itunes="{ITUNES_NS}" '
            f'xmlns:podcast="{PODCAST_NS}" version="2.0"><channel><title>Demo</title>'
            '<atom:link href="https://nerranetwork.com/demo_podcast.rss" rel="self"/>'
            '<itunes:author>Patrick</itunes:author>'
            '<item><title>Ep 1</title><guid>demo-ep001</guid>'
            '<enclosure url="https://audio.example/ep1.mp3" length="1" type="audio/mpeg"/>'
            f'<podcast:transcript url="{JSON_URL}" type="application/json"/></item>'
            '<item><title>Ep 0</title><guid>demo-ep000</guid>'
            '<enclosure url="https://audio.example/ep0.mp3" length="1" type="audio/mpeg"/>'
            f'<podcast:transcript url="{JSON_URL.replace("Ep001", "Ep000")}" type="application/json"/></item>'
            '</channel></rss>'
        )
        (root / "demo_podcast.rss").write_text(feed, encoding="utf-8")
        # Language / video / blog feeds are never touched.
        (root / "demo_podcast.fr.rss").write_text(feed, encoding="utf-8")
        (root / "demo_podcast.video.rss").write_text(feed, encoding="utf-8")
        (root / "blog_demo.rss").write_text(feed, encoding="utf-8")

    def test_dry_run_writes_nothing_but_counts(self, tmp_path, capsys):
        bf = _load_backfill()
        self._seed(tmp_path)
        before = (tmp_path / "demo_podcast.rss").read_bytes()
        assert bf.main(["--root", str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert "1 written" in out
        assert "+1 text/vtt tag(s)" in out
        assert not (tmp_path / "digests/demo/Demo_Ep001_20261001_transcript.vtt").exists()
        assert (tmp_path / "demo_podcast.rss").read_bytes() == before

    def test_apply_is_idempotent_and_keeps_the_feed_parseable(self, tmp_path, capsys):
        import feedparser
        bf = _load_backfill()
        self._seed(tmp_path)
        assert bf.main(["--apply", "--root", str(tmp_path)]) == 0
        vtt = tmp_path / "digests/demo/Demo_Ep001_20261001_transcript.vtt"
        assert vtt.read_text(encoding="utf-8").startswith("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello.\n")
        assert not (tmp_path / "digests/demo/Demo_Ep001_20261001.ru_transcript.vtt").exists()

        feed = tmp_path / "demo_podcast.rss"
        parsed = feedparser.parse(str(feed))
        assert len(parsed.entries) == 2 and not parsed.bozo
        ep1 = _item(feed, "demo-ep001")
        tags = ep1.findall(f"{{{PODCAST_NS}}}transcript")
        assert [(t.get("type"), t.get("url")) for t in tags] == [
            ("text/vtt", VTT_URL), ("application/json", JSON_URL)]
        # Ep 0 has no VTT on disk — left alone.
        assert [t.get("type") for t in _item(feed, "demo-ep000").findall(
            f"{{{PODCAST_NS}}}transcript")] == ["application/json"]
        ch = _channel(feed)
        assert ch.findtext(f"{{{ITUNES_NS}}}type") == "episodic"
        assert ch.findtext(f"{{{PODCAST_NS}}}guid") == publisher.podcast_guid_for_feed_url(
            "https://nerranetwork.com/demo_podcast.rss")
        assert ch.findtext(f"{{{ITUNES_NS}}}author") == "Patrick · Nerra Network"
        for untouched in ("demo_podcast.fr.rss", "demo_podcast.video.rss", "blog_demo.rss"):
            assert "text/vtt" not in (tmp_path / untouched).read_text(encoding="utf-8")

        snapshot = feed.read_bytes()
        assert bf.main(["--apply", "--root", str(tmp_path)]) == 0
        assert feed.read_bytes() == snapshot
        assert "1 already present" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# The committed feeds
# ---------------------------------------------------------------------------

def _root_audio_feeds():
    return _load_backfill().root_audio_feeds(ROOT)


class TestCommittedFeeds:
    @pytest.mark.parametrize("feed", _root_audio_feeds(), ids=lambda p: p.name)
    def test_channel_identity_tags(self, feed):
        ch = _channel(feed)
        assert ch.findtext(f"{{{ITUNES_NS}}}type") == "episodic", feed.name
        self_url = next(
            (ln.get("href") for ln in ch.findall(f"{{{ATOM_NS}}}link") if ln.get("rel") == "self"),
            f"https://nerranetwork.com/{feed.name}")
        assert ch.findtext(f"{{{PODCAST_NS}}}guid") == publisher.podcast_guid_for_feed_url(self_url)
        author = ch.findtext(f"{{{ITUNES_NS}}}author") or ""
        assert "nerra network" in author.lower(), f"{feed.name}: {author!r}"

    @pytest.mark.parametrize("feed", _root_audio_feeds(), ids=lambda p: p.name)
    def test_newest_item_has_a_vtt_transcript(self, feed):
        items = _channel(feed).findall("item")
        if not items:
            pytest.skip(f"{feed.name}: no items")
        tags = items[0].findall(f"{{{PODCAST_NS}}}transcript")
        if not any((t.get("url") or "").endswith("_transcript.json") for t in tags):
            # A show that publishes no Whisper transcript at all (the Voices
            # pipeline, Nerra Daily) or an episode whose transcription
            # failed has nothing to render a VTT from.
            pytest.skip(f"{feed.name}: newest item carries no JSON transcript")
        assert any(t.get("type") == "text/vtt" for t in tags), (
            f"{feed.name}: newest item has the JSON transcript tag but no text/vtt — "
            "run scripts/backfill_transcript_vtt.py --apply")
        assert tags[0].get("type") == "text/vtt", "text/vtt comes first"
