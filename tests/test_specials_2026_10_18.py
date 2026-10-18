"""Members-only limited series (Oct 18 2026, operator-directed).

engine/specials.py, scripts/produce_special.py, scripts/release_special.py,
specials/series/*.yaml. What binds:

* a series file is validated (contiguous parts, research questions, real
  host and teaser shows) and both shipped series load;
* only pages the run actually READ become sources, social posts never do,
  and an episode with fewer than ``min_sources`` does not produce;
* a series hosted by Peptides Weekly carries the blocking dose-terms lint;
* a trailer item survives every later rebuild of a show's free feed and
  never moves the episode numbering;
* every paying member's Personal feed carries every released episode, as
  bonus items outside the 7-edition window; nothing before release;
* a teaser show's email carries the P.S. for 14 days after release.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import specials as S  # noqa: E402


class TestSeries:
    def test_both_series_load(self):
        ids = {s.id: s for s in S.all_series()}
        assert {"spacex-tesla-merger", "peptides-deep-dives"} <= set(ids)
        merger = ids["spacex-tesla-merger"]
        assert merger.total_parts == 7
        stances = [e.stance for e in merger.episodes]
        assert stances[-2:] == ["for", "against"]
        assert set(merger.tease_shows) == {"spacex", "tesla"}
        peptides = ids["peptides-deep-dives"]
        assert 10 <= peptides.total_parts - 1 <= 20  # an opener + 10-20 peptides
        assert "dose_terms" in peptides.blocking_lints

    def test_every_episode_is_researchable(self):
        for s in S.all_series():
            for e in s.episodes:
                assert len(e.questions) >= 3, e.id
                assert e.brief and e.title

    def test_invalid_series_is_refused(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("id: x\nhost_show: spacex\nepisodes:\n"
                       "  - {id: a, part: 2, title: T, brief: B, questions: [q, r, s]}\n")
        with pytest.raises(S.SpecialsError):
            S.load_series(bad)

    def test_prompts_render_for_every_episode(self):
        today = dt.date(2026, 10, 18)
        src = [{"title": "T", "url": "https://example.org/a", "full_text": "x" * 900}]
        for s in S.all_series():
            for e in s.episodes:
                p = S.dossier_prompt(s, e, src, today=today)
                q = S.script_prompt(s, e, "DOSSIER", today=today,
                                    host_name="Patrick", show_name="Show")
                for text in (p, q):
                    assert not re.search(r"\{[a-z_]+\}", text), (s.id, e.id)
                assert "```claims" in p
                assert f"part {e.part} of {s.total_parts}" in q
            assert not re.search(r"\{[a-z_]+\}", S.trailer_prompt(s, host_name="P", show_name="S"))

    def test_no_quotable_specimen_in_series_rules(self):
        # De-seed by shape: a rules file never supplies a sentence in quotes
        # longer than a few words for the model to reproduce.
        for s in S.all_series():
            for quoted in re.findall(r"\"([^\"]+)\"", s.rules_text()):
                assert len(quoted.split()) <= 4, (s.id, quoted)


class TestResearch:
    def _ep(self):
        return S.Episode(id="e", part=1, title="T", brief="B", questions=["q1", "q2", "q3"])

    def test_only_read_pages_become_sources(self):
        def search(question, brief, max_results):
            return [
                {"title": "A", "url": "https://journal.org/a"},
                {"title": "A dup", "url": "https://journal.org/a?utm_source=x"},
                {"title": "Post", "url": "https://x.com/someone/status/1"},
                {"title": "Stub", "url": "https://stub.org/" + question},
                {"title": "Good " + question, "url": "https://news.org/" + question},
            ]

        def enrich(arts, max_articles, max_chars):
            for a in arts:
                if "stub.org" in a["url"]:
                    a["full_text"], a["full_text_source"] = "too short", "page"
                else:
                    a["full_text"], a["full_text_source"] = "y" * 900, "page"
            return len(arts)

        kept = S.research_episode(self._ep(), search=search, enrich=enrich)
        urls = [a["url"] for a in kept]
        assert not any("x.com" in u or "stub.org" in u for u in urls)
        assert len([u for u in urls if "journal.org" in u]) == 1
        assert len(kept) == 4  # journal + three news pages

    def test_thin_research_never_writes(self, monkeypatch, tmp_path):
        sys.path.insert(0, str(ROOT / "scripts"))
        import produce_special as P

        series = S.find_series("spacex-tesla-merger")
        monkeypatch.setattr(S, "SPECIALS_DIR", tmp_path)
        monkeypatch.setattr(S, "research_episode", lambda ep: [])
        called = []
        monkeypatch.setattr(S, "call_model", lambda *a, **k: called.append(1))
        with pytest.raises(S.ThinResearch):
            P.write_episode_text(series, series.episodes[0], P._host_config(series),
                                 {"series": {}}, dt.date(2026, 10, 18))
        assert not called


class TestLints:
    def test_dose_terms_block_peptides(self):
        s = S.find_series("peptides-deep-dives")
        assert S.blocking_lint_findings("Users reconstitute 5 mg vials.", s)
        assert not S.blocking_lint_findings("A randomised trial of 300 adults.", s)

    def test_clean_script_is_spoken_text(self):
        out = S.clean_script("## Heading\n**Bold** line with [a link](https://x.org).\n- bullet\n")
        assert "#" not in out and "**" not in out and "https" not in out
        assert "Bold line with a link." in out and "bullet" in out


@pytest.fixture()
def released_catalog():
    return {"series": {"spacex-tesla-merger": {
        "title": "SpaceX and Tesla: The Merger Question", "summary": "Seven episodes.",
        "teaser": "Should they merge?", "total_parts": 2, "host_show": "spacex",
        "tease_shows": ["spacex", "tesla"], "status": "released",
        "released_date": "2026-10-20",
        "trailer": {"audio_url": "https://audio.nerranetwork.com/specials/x/t.mp3",
                    "bytes": 1000, "duration_seconds": 95},
        "episodes": {
            "a": {"part": 1, "title": "One", "status": "produced", "filename": "a.mp3",
                  "audio_ref": "r2-private://nerra-personal/specials/x/a.mp3",
                  "bytes": 10, "duration_seconds": 1800},
            "b": {"part": 2, "title": "Two", "status": "written"},
        }}}}


class TestReleaseSurfaces:
    def test_trailer_survives_a_feed_rebuild(self, tmp_path):
        from engine.publisher import get_next_episode_number
        feed = tmp_path / "spacex_podcast.rss"
        shutil.copy(ROOT / "spacex_podcast.rss", feed)
        before = get_next_episode_number(feed, tmp_path)
        guid = S.trailer_guid("spacex", "spacex-tesla-merger")
        item = S.trailer_item_xml(
            guid=guid, title="Members-only series: X", description="D",
            audio_url="https://op3.dev/e/audio.nerranetwork.com/specials/x/t.mp3",
            length=1000, duration_seconds=95,
            pub_date=dt.datetime(2026, 10, 20, 11, tzinfo=dt.timezone.utc),
            link="https://nerranetwork.com/specials.html#spacex-tesla-merger")
        assert S.insert_trailer_item(feed, item, guid)
        assert not S.insert_trailer_item(feed, item, guid)  # once only
        assert get_next_episode_number(feed, tmp_path) == before
        import xml.etree.ElementTree as ET
        root = ET.parse(feed).getroot()
        items = root.find("channel").findall("item")
        mine = [i for i in items if (i.findtext("guid") or "") == guid]
        assert len(mine) == 1
        ns = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
        assert mine[0].findtext(f"{ns}episodeType") == "trailer"

    def test_member_rows_are_released_and_produced_only(self, released_catalog):
        rows = S.member_feed_rows(released_catalog)
        assert [r["episode_id"] for r in rows] == ["a"]
        released_catalog["series"]["spacex-tesla-merger"]["status"] = "produced"
        assert S.member_feed_rows(released_catalog) == []

    def test_member_feed_carries_specials_as_bonus(self, released_catalog):
        from engine.personal_edition import PersonalSpec, build_personal_feed_xml
        spec = PersonalSpec(token="a" * 32, shows=["spacex", "tesla"])
        xml = build_personal_feed_xml(spec, [], specials=S.member_feed_rows(released_catalog))
        assert "special-spacex-tesla-merger-a" in xml
        assert "<itunes:episodeType>bonus</itunes:episodeType>" in xml
        assert f"personal/{'a' * 32}/a.mp3" in xml or "/a.mp3" in xml

    def test_newsletter_ps_runs_for_fourteen_days(self, released_catalog):
        on = S.newsletter_ps("tesla", dt.date(2026, 10, 25), catalog=released_catalog)
        assert "Nerra Personal members" in on and "specials.html#spacex-tesla-merger" in on
        assert S.newsletter_ps("tesla", dt.date(2026, 11, 10), catalog=released_catalog) == ""
        assert S.newsletter_ps("peptides", dt.date(2026, 10, 25), catalog=released_catalog) == ""

    def test_no_page_before_release(self, tmp_path, monkeypatch):
        import generate_html as G
        monkeypatch.setattr(S, "load_catalog", lambda path=S.CATALOG_PATH: {"series": {}})
        assert G.generate_specials_page(output_dir=tmp_path) is None
        assert not (tmp_path / "specials.html").exists()

    def test_page_lists_a_released_series(self, tmp_path, monkeypatch, released_catalog):
        import generate_html as G
        monkeypatch.setattr(S, "load_catalog", lambda path=S.CATALOG_PATH: released_catalog)
        out = G.generate_specials_page(output_dir=tmp_path)
        html = Path(out).read_text(encoding="utf-8")
        assert 'id="spacex-tesla-merger"' in html and "join.html" in html
        assert "Part 1: One" in html

    def test_newsletter_and_pages_read_the_catalog(self):
        src = (ROOT / "engine" / "newsletter.py").read_text(encoding="utf-8")
        assert "p_s=_special_ps(slug, _today)" in src
        assert "member_specials" in (ROOT / "templates" / "show_page.html.j2").read_text(encoding="utf-8")
        assert "member_specials" in (ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8")


def test_release_is_a_separate_confirmed_step():
    src = (ROOT / "scripts" / "release_special.py").read_text(encoding="utf-8")
    assert '"--confirm"' in src and "dry run" in src
    wf = (ROOT / ".github" / "workflows" / "produce-special.yml").read_text(encoding="utf-8")
    assert "release_special.py --series \"$SERIES\" --confirm" in wf
    produce = (ROOT / "scripts" / "produce_special.py").read_text(encoding="utf-8")
    # Production never touches a public feed, X or a newsletter.
    for public in ("insert_trailer_item", "post_teaser", "send_newsletter", "update_rss_feed"):
        assert public not in produce, public


def test_catalog_file_is_valid_json_when_present():
    if S.CATALOG_PATH.exists():
        json.loads(S.CATALOG_PATH.read_text(encoding="utf-8"))


def test_specials_close_on_the_network_disclosure():
    src = (ROOT / "run_show.py").read_text(encoding="utf-8")
    m = re.search(r'_AI_DISCLOSURE = \(\n\s+"([^"]+)"\n\s+"([^"]+)"\n\)', src)
    assert m and m.group(1) + m.group(2) == S.AI_DISCLOSURE
    produce = (ROOT / "scripts" / "produce_special.py").read_text(encoding="utf-8")
    assert produce.count("S.AI_DISCLOSURE") >= 2  # every episode and the trailer


def test_builder_copies_specials_into_each_member_keyspace(monkeypatch, released_catalog):
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_personal_feeds as B
    from engine.personal_edition import PersonalSpec

    monkeypatch.setattr(S, "load_catalog", lambda path=S.CATALOG_PATH: released_catalog)

    class FakeClient:
        def __init__(self):
            self.copies, self.puts, self.objects = [], {}, {}

        def copy_object(self, **kw):
            self.copies.append(kw)

        def put_object(self, Bucket, Key, Body, ContentType):  # noqa: N803
            self.puts[Key] = Body

        def get_object(self, Bucket, Key):  # noqa: N803
            raise KeyError(Key)

    client = FakeClient()
    spec = PersonalSpec(token="b" * 32, shows=["tesla"])
    assert B.ensure_specials(spec, client) is True
    assert client.copies[0]["Key"] == f"personal/{'b' * 32}/a.mp3"
    assert client.copies[0]["CopySource"] == {"Bucket": "nerra-personal", "Key": "specials/x/a.mp3"}
    feed = client.puts[f"personal/{'b' * 32}/feed.rss"].decode("utf-8")
    assert "special-spacex-tesla-merger-a" in feed
    # A second pass with the state on R2 copies nothing and leaves the feed.
    state = json.loads(client.puts[f"personal/{'b' * 32}/episodes.json"])
    client.get_object = lambda Bucket, Key: {"Body": __import__("io").BytesIO(json.dumps(state).encode())}  # noqa: N803
    client.copies.clear()
    assert B.ensure_specials(spec, client) is False and not client.copies
