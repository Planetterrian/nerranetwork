"""The site as an app (Oct 28 2026, later): one player, a watch page, the
installable shell, a join page that builds a lineup, the add-to-app page.

Guards the contracts the pieces depend on: the service worker never touches
audio or another origin, the feed token never reaches a server log, every
event the new scripts send is read, every page the homepage build writes is
committed, and the drafts a visitor builds land in My Nerra.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

import generate_html as gh

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "assets" / "js"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("rel", ["assets/js/nn-player.js", "assets/js/nn-app.js",
                                 "assets/js/for-you.js", "sw.js"])
def test_scripts_parse(rel):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    res = subprocess.run([node, "--check", str(ROOT / rel)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


class TestServiceWorker:
    def test_never_answers_audio_another_origin_or_a_range(self):
        sw = _read("sw.js")
        assert "url.origin !== self.location.origin" in sw
        assert "req.headers.has('range')" in sw
        assert "mp3|m4a|m4b|mp4" in sw

    def test_pages_are_network_first(self):
        sw = _read("sw.js")
        assert "if (req.mode === 'navigate')" in sw
        assert "networkFirst(req, PAGES, '/offline.html')" in sw

    def test_precache_files_exist(self):
        sw = _read("sw.js")
        for path in re.findall(r"'(/[^']+)'", sw.split("var PRECACHE = [", 1)[1].split("];", 1)[0]):
            assert (ROOT / path.lstrip("/")).is_file(), path

    def test_registered_from_the_root_scope(self):
        assert "navigator.serviceWorker.register('/sw.js', { scope: '/' })" in _read("assets/js/nn-app.js")


class TestManifest:
    def test_manifest_is_valid_and_icons_exist(self):
        m = json.loads(_read("manifest.webmanifest"))
        assert m["display"] == "standalone" and m["start_url"].startswith("/")
        assert any(i.get("purpose") == "maskable" for i in m["icons"])
        for icon in m["icons"]:
            assert (ROOT / icon["src"].lstrip("/")).is_file(), icon["src"]
        for sc in m["shortcuts"]:
            assert (ROOT / sc["url"].split("?")[0].lstrip("/")).is_file(), sc["url"]

    def test_every_page_links_it_and_loads_the_player(self):
        base = _read("templates/base.html.j2")
        assert 'rel="manifest"' in base and "apple-touch-icon" in base
        assert "assets/js/nn-player.js" in base and "assets/js/nn-app.js" in base
        assert "window.nnAccount = fetch(" in base


class TestThePlayer:
    def test_reports_plays_once_with_tracking_js_parameters(self):
        js = _read("assets/js/nn-player.js")
        assert "track('episode_play', { src: String(it.url).split('?')[0], location: location.pathname })" in js
        assert "if (!it || reported[it.url]) { return; }" in js

    def test_keeps_my_nerras_storage_keys(self):
        js = _read("assets/js/nn-player.js")
        assert "load('nnMe.pos')" in js and "'nnMe.played'" in js

    def test_video_is_privacy_enhanced_and_only_on_a_press(self):
        js = _read("assets/js/nn-player.js")
        assert "https://www.youtube-nocookie.com/embed/" in js
        assert "host: 'https://www.youtube-nocookie.com'" in js
        # The IFrame API loads only inside loadYT, which only a playlist
        # video (a press) calls; nothing YouTube runs at page load.
        assert js.count("https://www.youtube.com/iframe_api") == 1
        assert js.count("loadYT().then") == 1
        assert "loadYT().then" in js.split("function playVideo", 1)[1].split("function playMira", 1)[0]
        init = js.split("function init()", 1)[1]
        assert "openList" not in init and "loadYT" not in init

    def test_my_nerra_uses_it_and_has_no_player_of_its_own(self):
        src = _read("templates/account_page.html.j2")
        assert "window.NNPlayer" in src
        assert "new Audio()" not in src
        assert 'id="nn-player"' not in src


class TestWatchMyLineup:
    def test_my_nerra_builds_the_list_from_the_lineup(self):
        src = _read("templates/account_page.html.j2")
        assert 'id="nn-watch-all"' in src and "NN.watchLineup()" in src
        body = src.split("function lineupVideos()", 1)[1].split("function renderWatch", 1)[0]
        assert "lineup().forEach" in body and "e.members_only" in body

    def test_mira_card_is_written_and_disclosed(self):
        src = _read("templates/account_page.html.j2")
        card = src.split("watchLineup: function ()", 1)[1].split("playLineup:", 1)[0]
        assert "kind: 'mira'" in card and "assets/mira/mira-studio.mp4" in card
        assert "Mira is an AI host" in card
        assert (ROOT / "assets" / "mira" / "mira-studio.mp4").is_file()

    def test_the_playlist_advances_on_end_and_by_hand(self):
        js = _read("assets/js/nn-player.js")
        assert "e.data === 0" in js and "showItem(listAt + 1)" in js
        assert "api.watchList = function" in js
        assert "placement: list.length > 1 ? 'lineup' : 'single'" in js

    def test_greeting_reaches_the_card_as_text(self):
        mira = _read("assets/js/nn-player.js").split("function playMira", 1)[1].split("function showItem", 1)[0]
        assert "h.textContent = item.greeting" in mira and "p.textContent = line" in mira


class TestEveryEventIsRead:
    def test_new_events_are_in_the_engagement_report(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("fga4", ROOT / "scripts" / "fetch_ga4_stats.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sources = "".join(_read(p) for p in (
            "assets/js/nn-player.js", "assets/js/nn-app.js", "assets/js/for-you.js",
            "templates/join_page.html.j2", "templates/add_feed_page.html.j2"))
        sent = set(re.findall(r"(?:track|gtag)\(\s*'(?:event',\s*')?([a-z_]+)'", sources))
        sent.discard("event")
        assert sent, "found no events"
        missing = sent - set(mod.ENGAGEMENT_EVENTS) - set(mod.CONVERSION_EVENTS)
        assert not missing, missing


@pytest.fixture(scope="module")
def payload():
    return gh.personal_front_payload(
        gh._build_all_shows_list(), gallery_root=ROOT / "site" / "data" / "gallery",
        now=datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc))


class TestWatchPage:

    def test_rows_are_youtube_urls_newest_first(self, payload):
        shows, shorts, longs = gh.watch_page_rows(payload)
        for rows in (shorts, longs):
            assert [r["iso"] for r in rows] == sorted((r["iso"] for r in rows), reverse=True)
            assert all(r["url"].startswith(("https://www.youtube.com/", "https://youtu.be/")) for r in rows)

    def test_page_renders_and_is_in_the_sitemap_list(self, payload, tmp_path):
        out = gh.generate_watch_page(payload=payload, output_dir=tmp_path)
        html = Path(out).read_text(encoding="utf-8")
        assert "data-nn-watch=" in html
        assert "<main" not in html.split('id="main-content"', 1)[1].split("</main>", 1)[0][:200]
        assert '"watch.html"' in _read("generate_html.py")

    def test_payload_carries_videos(self, payload):
        rows = [s for e in payload["shows"].values() for s in e["stories"]]
        assert rows and all("videos" in s for s in rows)

    @pytest.mark.parametrize("wf", ["nerra-daily.yml", "nightly-maintenance.yml",
                                    "render-video.yml", "run-show.yml"])
    def test_each_homepage_commit_includes_it(self, wf):
        assert "watch.html" in _read(f".github/workflows/{wf}")


class TestDraftsReachMyNerra:
    def test_both_builders_write_the_draft_my_nerra_reads(self):
        assert "var DRAFT = 'nnMe.draft'" in _read("assets/js/for-you.js")
        assert "var DRAFT = 'nnMe.draft'" in _read("templates/join_page.html.j2")
        acct = _read("templates/account_page.html.j2")
        assert "store('nnMe.draft')" in acct and "takeDraft()" in acct
        # Only into an account with no lineup, and only known slugs.
        assert "if (!state.shows.length && draft.length)" in acct
        assert "state.all.indexOf(x) !== -1" in acct

    def test_homepage_band_is_not_an_email_form(self):
        tpl = _read("templates/network_page.html.j2")
        band = tpl.split('id="for-you"', 1)[1].split("</section>", 1)[0]
        assert "<form" not in band

    def test_member_text_reaches_the_page_as_text(self):
        js = _read("assets/js/for-you.js")
        assert "innerHTML" not in js


class TestAddToAppPage:
    def test_the_token_leaves_the_address_bar_before_analytics(self):
        tpl = _read("templates/add_feed_page.html.j2")
        early = tpl.split("{% block head_early %}", 1)[1].split("{% endblock %}", 1)[0]
        assert "history.replaceState(null, '', location.pathname)" in early
        assert 'name="referrer" content="no-referrer"' in early
        assert "noindex" in early

    def test_never_in_the_sitemap(self, tmp_path):
        src = _read("generate_html.py")
        extras = src.split('for extra in ["modern-investing-resources.html"', 1)[1].split("]:", 1)[0]
        assert "add.html" not in extras and "offline.html" not in extras

    def test_every_app_link_is_built_from_the_feed(self):
        tpl = _read("templates/add_feed_page.html.j2")
        for scheme in ("podcast://", "overcast://x-callback-url/add?url=", "pktc://subscribe/",
                       "castros://subscribe/", "antennapod-subscribe://", "podcastaddict://"):
            assert scheme in tpl, scheme

    def test_my_nerra_and_the_welcome_email_link_it(self):
        assert "add.html#' + tok[1]" in _read("templates/account_page.html.j2")
        assert "https://nerranetwork.com/add.html#${tokenMatch[1]}" in _read("workers/gallery/src/magic-email.ts")

    def test_generated_with_the_static_pages(self):
        body = gh.generate_static_pages.__code__.co_names
        assert "generate_add_feed_page" in body and "generate_offline_page" in body
        nightly = _read(".github/workflows/nightly-maintenance.yml")
        assert "            add.html\n" in nightly and "            offline.html\n" in nightly


class TestJoinPage:
    def test_builder_and_preview_render(self, tmp_path):
        html = Path(gh.generate_join_page(output_dir=tmp_path)).read_text(encoding="utf-8")
        assert 'id="builder"' in html and "data-jn-preview" in html
        assert html.count("data-jn-toggle=") == len(gh._personal_shows_list())

    def test_preview_lengths_are_measured(self, tmp_path):
        html = Path(gh.generate_join_page(output_dir=tmp_path)).read_text(encoding="utf-8")
        preview = html.split("data-jn-preview", 1)[1].split("</ol>", 1)[0]
        # No typed m:ss lengths (the old mockup's 9:41 / 8:12 / 9:56 / 10:03).
        assert not re.search(r"\b\d{1,2}:\d{2}\b", preview)
