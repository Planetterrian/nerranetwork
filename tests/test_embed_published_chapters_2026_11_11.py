"""The back catalogue gets its chapters (Nov 11 2026).

``scripts/embed_published_chapters.py`` re-tags MP3s already on R2 and
edits their feed items. These guards pin what it may and may not change:
the same key, bit-identical audio, and a feed item whose only edits are the
enclosure length and the chapter lines in its notes.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import scripts.embed_published_chapters as E

ROOT = Path(__file__).resolve().parent.parent
HAVE_FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")

CHAPTERS = {"version": "1.2.0", "chapters": [
    {"startTime": 0.0, "title": "Introduction"},
    {"startTime": 15.0, "title": "Lead & story"},
    {"startTime": 40.0, "title": "Closing"},
]}

ITEM = """<item>
      <title>Ep 7: A hook</title>
      <link>https://nerranetwork.com/blog/x/ep7.html</link>
      <description>Show
&lt;b&gt;A hook&lt;/b&gt;

Sources: &lt;a href="https://a.example/1"&gt;a.example&lt;/a&gt;

AI Disclosure: voices are synthetic.</description>
      <guid isPermaLink="false">x-ep7</guid>
      <enclosure url="https://op3.dev/e/audio.nerranetwork.com/x/X_Ep007_20261101.mp3" length="1000" type="audio/mpeg" />
      <itunes:summary>Show
&lt;b&gt;A hook&lt;/b&gt;

Sources: &lt;a href="https://a.example/1"&gt;a.example&lt;/a&gt;

AI Disclosure: voices are synthetic.</itunes:summary>
      <itunes:episode>7</itunes:episode>
    </item>"""


def _feed(tmp_path: Path, items=(ITEM,)) -> E.Feed:
    rss = tmp_path / "x_podcast.rss"
    rss.write_text("<rss><channel>\n    " + "\n    ".join(items) + "\n</channel></rss>\n",
                   encoding="utf-8")
    d = tmp_path / "digests"
    d.mkdir()
    (d / "chapters_ep007.json").write_text(json.dumps(CHAPTERS), encoding="utf-8")
    return E.Feed("x", rss, d, "en")


class TestTheFeedIsTheRecord:
    def test_key_comes_from_the_bare_enclosure(self):
        (item,) = E.feed_items(ITEM)
        assert item["key"] == "x/X_Ep007_20261101.mp3"
        assert item["download_url"].startswith("https://audio.nerranetwork.com/")
        assert "op3.dev" not in item["download_url"]

    def test_an_enclosure_off_the_public_host_is_never_ours(self):
        other = ITEM.replace("audio.nerranetwork.com", "cdn.example.com")
        assert E.feed_items(other)[0]["key"] == ""

    def test_every_show_feed_and_the_edition_are_listed_never_a_translation(self):
        feeds = E.show_feeds()
        names = {f.rss_path.name for f in feeds}
        assert "podcast.rss" in names and "nerra_daily_podcast.rss" in names
        assert not any(re.search(r"\.[a-z]{2}\.rss$", n) for n in names)


class TestTheItemEdit:
    def test_length_and_both_notes_change_nothing_else(self):
        block = E.chapter_timestamp_block(CHAPTERS)
        new = E.edit_item(ITEM, block=block, length=1234)
        assert 'length="1234"' in new
        assert new.count("0:00 Introduction") == 2  # description + itunes:summary
        assert "0:15 Lead &amp; story" in new       # escaped like the rest
        # The block sits after Sources and before the disclosure.
        d = re.search(r"<description>(.*?)</description>", new, re.S).group(1)
        assert d.index("Sources:") < d.index("Chapters:") < d.index("AI Disclosure")
        # Strip the two edits and the item is the original byte for byte.
        undone = new.replace("\n\n" + block.replace("&", "&amp;"), "").replace(
            'length="1234"', 'length="1000"')
        assert undone == ITEM

    def test_a_second_run_adds_nothing(self):
        block = E.chapter_timestamp_block(CHAPTERS)
        once = E.edit_item(ITEM, block=block, length=None)
        assert E.edit_item(once, block=block, length=None) == once

    def test_a_clock_time_in_the_notes_is_not_a_chapter_list(self):
        item = ITEM.replace("A hook&lt;/b&gt;", "A hook at 10:00 AM&lt;/b&gt;", 1)
        new = E.edit_item(item, block=E.chapter_timestamp_block(CHAPTERS), length=None)
        assert "0:00 Introduction" in new


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")
class TestTheAudioPass:
    @staticmethod
    def _mp3(path: Path) -> Path:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "sine=f=220:d=60", "-c:a", "libmp3lame", "-q:a", "2", str(path)],
                       check=True)
        return path

    def test_a_refused_retag_is_never_uploaded(self, tmp_path, monkeypatch):
        feed = _feed(tmp_path)
        src = self._mp3(tmp_path / "published.mp3")
        uploads = []
        monkeypatch.setattr("engine.http_download.download_to",
                            lambda url, dest, **k: shutil.copyfile(src, dest))
        monkeypatch.setattr(E, "_upload", lambda local, key: uploads.append(key))
        md5s = iter(["aaa", "bbb"])
        monkeypatch.setattr(E, "pcm_md5", lambda p: next(md5s))
        for k in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            monkeypatch.setenv(k, "x")
        rc = E.embed_pass([feed], apply=True, limit=0, episode=None,
                          results_path=tmp_path / "r.json")
        assert rc == 1 and uploads == []

    def test_end_to_end_same_key_identical_audio_then_the_feed(self, tmp_path, monkeypatch):
        feed = _feed(tmp_path)
        src = self._mp3(tmp_path / "published.mp3")
        uploaded = {}

        def _upload(local, key):
            uploaded[key] = local.read_bytes()

        monkeypatch.setattr("engine.http_download.download_to",
                            lambda url, dest, **k: shutil.copyfile(src, dest))
        monkeypatch.setattr(E, "_upload", _upload)
        for k in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            monkeypatch.setenv(k, "x")
        results = tmp_path / "r.json"
        assert E.embed_pass([feed], apply=True, limit=0, episode=None,
                            results_path=results) == 0
        assert list(uploaded) == ["x/X_Ep007_20261101.mp3"]
        out = tmp_path / "out.mp3"
        out.write_bytes(uploaded["x/X_Ep007_20261101.mp3"])
        assert E.pcm_md5(out) == E.pcm_md5(src)
        assert [c["title"] for c in E.read_mp3_chapters(out)] == [
            "Introduction", "Lead & story", "Closing"]

        assert E.feeds_pass([feed], apply=True, results_path=results) == 0
        text = feed.rss_path.read_text(encoding="utf-8")
        assert f'length="{out.stat().st_size}"' in text
        assert "x-ep7" in text and "X_Ep007_20261101.mp3" in text
        log = json.loads((feed.digests_dir / E.LOG_NAME).read_text(encoding="utf-8"))
        assert log[0]["guid"] == "x-ep7" and log[0]["status"] == "embedded"

        # The next run skips it.
        uploaded.clear()
        E.embed_pass([feed], apply=True, limit=0, episode=None, results_path=results)
        assert uploaded == {}


class TestTheWorkflow:
    def test_the_feed_pass_runs_on_the_live_tip_and_dry_run_is_default(self):
        wf = (ROOT / ".github/workflows/embed-published-chapters.yml").read_text(encoding="utf-8")
        assert "default: false" in wf
        feeds = wf.index("name: Pass 2")
        assert wf.index("git reset --hard origin/main", feeds) < wf.index("--feeds", feeds)
        assert "R2_SECRET_ACCESS_KEY" not in wf[feeds:]
