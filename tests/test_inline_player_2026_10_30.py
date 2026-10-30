"""Oct 30 2026 — every episode player on the site is the site's own player.

Patrick, on an iPhone: the blog post's "Listen to this episode" box was "a
whited out box", and the show pages' players looked missing. Two causes:

* The blog box was ``<section class="nn-listen">`` — the class of the site
  player's Listen button (``nn-player.js``), so the button's pill rules
  (``display:inline-flex``, a 999px radius, ``width:auto``) collapsed the box.
* Every other episode player was the browser's native ``<audio controls>``,
  which iOS Safari draws as a light-grey pill on the dark pages, with no
  title, artwork or speed, and outside the site's queue and resume memory.

Now ``nn-player.js`` replaces each native player with an episode card (the
page's one player: cover, show, title, state) or a compact row (archive
cards), all driven by the one shared audio element, and the Listen pill's
rules are scoped to ``button.nn-listen``.
"""

from __future__ import annotations

import functools
import http.server
import re
import shutil
import socketserver
import subprocess
import threading
from pathlib import Path

import pytest

from tests.test_site_review_2026_10_07_blog import _latest_digest, _render, _template

ROOT = Path(__file__).resolve().parent.parent
PLAYER_JS = (ROOT / "assets" / "js" / "nn-player.js").read_text(encoding="utf-8")
CSS = (ROOT / "styles" / "main.css").read_text(encoding="utf-8")


class TestTheListenBoxIsNotTheListenButton:
    def test_the_pill_rules_are_scoped_to_the_button(self):
        """A bare ``.nn-listen`` selector is how the blog box collapsed."""
        bare = [m.group(0) for m in re.finditer(r"(?m)^[^{}\n]*(?<!button)\.nn-listen\b[^{}\n]*\{", CSS)]
        assert not bare, f"unscoped .nn-listen rules: {bare}"
        assert "button.nn-listen" in CSS

    def test_the_blog_box_has_its_own_class(self):
        src = _template("blog_post.html.j2")
        assert 'class="nn-listen"' not in src
        assert '<section class="nn-episode-listen" id="listen"' in src

    def test_css_braces_balance(self):
        assert CSS.count("{") == CSS.count("}")

    def test_the_box_steps_aside_for_the_card_on_committed_posts_too(self):
        """The rules live in the shared stylesheet so posts built before
        Oct 30 (``section.nn-listen``) lose the frame as well."""
        assert ".nn-i18n-inner:has(.nn-ip)" in CSS
        assert "section.nn-listen .nn-i18n-inner:has(.nn-ip) .nn-i18n-row" in CSS


@pytest.fixture(scope="module")
def post():
    return _render("dp_pod", _latest_digest("dp_pod"), keep_audio=True)


class TestThePlayersCarryTheirEpisode:
    def test_the_blog_player_is_a_card_with_its_episode(self, post):
        m = re.search(r'<audio id="nn-i18n-audio"[^>]*>', post)
        assert m, "no player on the post"
        tag = m.group(0)
        for attr in ("data-nn-card", 'data-title="', 'data-show="', 'data-cover="'):
            assert attr in tag, f"{attr} missing on the post's player"
        title = re.search(r'data-title="([^"]*)"', tag).group(1)
        assert title.strip(), "the player's title is empty"

    def test_the_show_page_latest_player_reads_its_title(self):
        src = _template("show_page.html.j2")
        tag = re.search(r'<audio id="latest-audio"[^>]*>', src).group(0)
        assert "data-nn-card" in tag
        assert 'data-nn-title-from="#latest-title"' in tag

    def test_interview_player_is_a_card(self):
        src = _template("blog_post.html.j2")
        block = src.split('class="nn-iv-player"', 1)[1][:800]
        assert "data-nn-card" in block


class TestThePlayerScript:
    def test_every_native_player_is_taken_over(self):
        assert "function enhanceInline()" in PLAYER_JS
        assert "document.querySelectorAll('audio[controls]')" in PLAYER_JS
        # The Listen pill, the player bar and the summaries page's sticky
        # player keep their own controls.
        assert ".lt-lead-audio" in PLAYER_JS and ".nn-gp" in PLAYER_JS
        assert "nn-sticky-audio" in PLAYER_JS
        assert "data-nn-native" in PLAYER_JS

    def test_committed_pages_get_a_card_without_new_attributes(self):
        """Pages built before Oct 30 are fixed by the shared script alone."""
        assert "'nn-i18n-audio':" in PLAYER_JS and "'latest-audio': '#latest-title'" in PLAYER_JS

    def test_a_chapter_link_plays_through_the_site_player(self):
        assert "playElement: function (el, seconds)" in PLAYER_JS
        assert "window.NNPlayer.playElement(audio, at)" in _template("blog_post.html.j2")

    def test_its_own_clock_is_not_new_content(self):
        """The body observer re-scans for players; the players' own text
        updates (4 a second while playing) must not count."""
        assert "tg.closest('.nn-ip, .nn-gp')" in PLAYER_JS

    def test_sync_writes_only_on_change(self):
        assert "p.ui.title.textContent !== it.title" in PLAYER_JS

    def test_the_script_parses(self):
        node = shutil.which("node")
        if not node:
            pytest.skip("node not installed")
        res = subprocess.run([node, "--check", str(ROOT / "assets/js/nn-player.js")],
                             capture_output=True, text=True)
        assert res.returncode == 0, res.stderr


_BROWSER_CHECK = r"""
const { chromium, devices } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const c = await b.newContext({ ...devices['iPhone 13'] });
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.route(/googletagmanager|google-analytics|op3\.dev|audio\.nerranetwork|youtube/, r => r.abort());
  await p.goto(process.argv[2], { waitUntil: 'domcontentloaded' });
  await p.waitForSelector('.nn-ip', { timeout: 8000 });
  const out = await p.evaluate(() => {
    const ip = document.querySelector('.nn-ip');
    const box = document.getElementById('listen').getBoundingClientRect();
    return {
      cards: document.querySelectorAll('.nn-ip--card').length,
      nativeShown: Array.from(document.querySelectorAll('audio[controls]'))
        .filter(a => getComputedStyle(a).display !== 'none').length,
      title: ip.querySelector('.nn-ip-title').textContent,
      boxWidth: box.width, viewport: innerWidth,
    };
  });
  out.errors = errs.filter(e => !/route/i.test(e));
  console.log(JSON.stringify(out));
  await b.close();
})();
"""


class TestInABrowser:
    """A committed post (built before Oct 30, so without the new data
    attributes) on an iPhone-sized page."""

    def test_the_committed_post_shows_a_card_and_no_native_player(self, tmp_path):
        node = shutil.which("node")
        if not node:
            pytest.skip("node not installed")
        if subprocess.run([node, "-e", "require('playwright')"], capture_output=True).returncode:
            pytest.skip("playwright not installed")
        # The newest committed post that loads the site player (posts built
        # before Oct 28 do not, until their show rebuilds them).
        posts = [p for p in sorted((ROOT / "blog").glob("*/ep*.html"),
                                   key=lambda p: p.stat().st_mtime, reverse=True)
                 if "nn-player.js" in (t := p.read_text(encoding="utf-8", errors="ignore"))
                 and 'id="nn-i18n-audio"' in t]
        if not posts:
            pytest.skip("no committed post loads the site player")
        rel = posts[0].relative_to(ROOT).as_posix()
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
        handler.log_message = lambda *a, **k: None
        with socketserver.TCPServer(("127.0.0.1", 0), handler) as srv:
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            script = tmp_path / "check.js"
            script.write_text(_BROWSER_CHECK, encoding="utf-8")
            url = f"http://127.0.0.1:{srv.server_address[1]}/{rel}"
            try:
                res = subprocess.run([node, str(script), url], capture_output=True, text=True,
                                     timeout=90, cwd=str(ROOT))
            finally:
                srv.shutdown()
        if res.returncode and "Executable doesn't exist" in res.stderr:
            pytest.skip("no chromium for playwright")
        assert res.returncode == 0, res.stderr[-2000:]
        import json
        out = json.loads(res.stdout.strip().splitlines()[-1])
        assert out["cards"] == 1
        assert out["nativeShown"] == 0
        assert out["title"].strip()
        # The box spans the column again, not a collapsed pill.
        assert out["boxWidth"] > out["viewport"] * 0.8
        assert not out["errors"], out["errors"]
