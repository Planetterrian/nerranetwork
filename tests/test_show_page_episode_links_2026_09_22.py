"""The page's script must read the same summaries the server read.

The Age of AI show page shipped a card whose left half said *"No episodes
available yet"* beside a right half showing the episode, its summary and a
link to its article. Both halves were correct about what they could see: the
server renders the card through ``engine.summaries_ssr``, which reads every
committed summaries shape, while the page's own script read
``data.summaries || data`` and the Nerra Voices pipeline writes
``{"episodes": [...]}``. The script got an object, found no ``.length``,
declared the show empty and overwrote the server's work.

The per-record keys differ too — ``episode`` not ``episode_num``, ``title``
not ``episode_title``, ``summary`` not ``content`` — so fixing only the
container key would have produced a card with no title and no audio.

That is the parity rule this pass exists to enforce: the server renders the
card and the script replaces it, so a narrower reader in the script does not
degrade gracefully, it contradicts the page.

The second half of the file covers the archive cards, which now carry the
same "Article & transcript" link the latest card does. The URL is resolved
at BUILD time and handed to the script as a map, because only the server can
tell an article from a redirect stub — a stub IS a file at
``blog/<slug>/epNNN.html``, which is how Age of AI's retired Ep001 kept
turning up as a link.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

import generate_html as G
from engine.summaries_ssr import summary_cards

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "show_page.html.j2"


def _template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _js_reader() -> str:
    """The script's record readers, lifted out of the template.

    They are plain JavaScript with no Jinja inside, which is what makes this
    guard possible: the assertion runs the SHIPPED code rather than a
    restatement of it.
    """
    src = _template()
    out = []
    for name in ("recordsFrom", "epNumber", "epTitle", "epSummary"):
        match = re.search(r"\n        function %s\(.*?\n        \}\n" % name,
                          src, re.S)
        assert match, f"{name} is gone from the show page script"
        out.append(match.group(0))
    return "".join(out)


def _run_reader(json_path: Path) -> dict:
    harness = _js_reader() + """
const data = JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));
const recs = recordsFrom(data);
recs.sort((a,b) => new Date(b.date) - new Date(a.date));
const l = recs[0] || {};
console.log(JSON.stringify({
  n: recs.length, num: epNumber(l), title: epTitle(l),
  audio: l.audio_url || '', summary: epSummary(l),
}));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(harness)
        script = Path(fh.name)
    try:
        proc = subprocess.run(
            ["node", str(script), str(json_path)],
            capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr[:400]
        return json.loads(proc.stdout)
    finally:
        script.unlink(missing_ok=True)


def _shows_with_summaries():
    for slug, cfg in G.NETWORK_SHOWS.items():
        path = ROOT / (cfg.get("json_path") or "")
        if cfg.get("json_path") and path.exists():
            yield slug, path


needs_node = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is not installed; the JS parity guard cannot run")


@needs_node
class TestTheScriptReadsWhatTheServerRead:
    @pytest.mark.parametrize("slug,path", list(_shows_with_summaries()),
                             ids=lambda v: v if isinstance(v, str) else "")
    def test_both_readers_agree_on_the_latest_episode(self, slug, path):
        """Not "the script finds something" — the SAME something."""
        js = _run_reader(path)
        py = summary_cards(path, slug, limit=1)
        if not py:
            assert js["n"] == 0
            return
        server = py[0]
        assert js["num"] == server["episode_num"], f"{slug}: episode number"
        assert js["title"] == server["title"], f"{slug}: title"
        assert js["audio"] == server["audio_url"], f"{slug}: audio url"

    def test_the_interview_shape_is_readable_at_all(self):
        """The regression: {"episodes": [...]} read as an empty show."""
        path = ROOT / "digests" / "age_of_ai" / "summaries_age_of_ai.json"
        js = _run_reader(path)
        assert js["n"] > 0, "the interview summaries still read as empty"
        assert js["title"] and js["audio"], "title and audio must resolve"

    def test_a_bare_list_and_an_unknown_wrapper_still_work(self, tmp_path):
        bare = tmp_path / "bare.json"
        bare.write_text(json.dumps(
            [{"episode": 1, "date": "2026-01-01", "title": "A",
              "audio_url": "u"}]), encoding="utf-8")
        assert _run_reader(bare)["n"] == 1

        odd = tmp_path / "odd.json"
        odd.write_text(json.dumps({"whatever": [
            {"episode": 2, "date": "2026-01-02", "title": "B",
             "audio_url": "u"}]}), encoding="utf-8")
        assert _run_reader(odd)["n"] == 1

    def test_junk_is_empty_not_an_exception(self, tmp_path):
        """An unreadable file must render the honest empty state, not throw."""
        for payload in ("{}", "null", '"a string"', "42"):
            bad = tmp_path / "bad.json"
            bad.write_text(payload, encoding="utf-8")
            assert _run_reader(bad)["n"] == 0


class TestEveryEpisodeCardOffersItsArticle:
    @pytest.fixture(scope="class")
    def pages(self, tmp_path_factory):
        out = tmp_path_factory.mktemp("cardlinks")
        return {
            slug: Path(G.generate_show_page(slug, output_dir=out)).read_text(
                encoding="utf-8")
            for slug in ("tesla", "age_of_ai", "nerra_daily", "spacex")
        }

    def _map(self, html: str) -> dict:
        match = re.search(r"const EPISODE_POST_URLS = (\{.*?\});", html, re.S)
        assert match, "the article-URL map is gone from the page"
        return json.loads(match.group(1))

    def test_the_archive_cards_render_the_link(self, pages):
        for slug, html in pages.items():
            assert "episode-card-article" in html, slug

    def test_the_rss_fallback_cards_get_it_too(self, pages):
        """Otherwise the link vanishes exactly when the JSON path failed."""
        assert "epNumberFromTitle" in _template()
        for html in pages.values():
            assert html.count("episode-card-article") >= 2

    def test_the_map_covers_the_archive_the_page_shows(self, pages):
        """The grid shows twelve cards past the latest; a map shorter than
        that leaves later cards silently linkless."""
        for slug in ("tesla", "spacex", "nerra_daily"):
            assert len(self._map(pages[slug])) >= 13, slug

    def test_every_mapped_url_is_a_real_article(self, pages):
        stubs = G.redirect_stub_paths()
        for slug, html in pages.items():
            for num, url in self._map(html).items():
                assert url not in stubs, f"{slug} ep{num} maps to a stub"
                assert (ROOT / url).exists(), f"{slug} ep{num} maps to a 404"

    def test_an_episode_with_no_article_is_simply_absent(self, pages):
        """Age of AI Ep001 predates the digest shape: its page is a redirect
        stub, so it gets no link rather than a link that bounces the reader
        back to where they clicked."""
        mapped = self._map(pages["age_of_ai"])
        assert "1" not in mapped
        assert mapped, "the other interviews must still be linked"

    def test_a_show_with_no_episodes_maps_nothing(self, tmp_path):
        html = Path(G.generate_show_page(
            "nerra_voices", output_dir=tmp_path)).read_text(encoding="utf-8")
        assert self._map(html) == {}

    def test_the_latest_link_is_looked_up_not_guessed(self):
        """It used to hide itself when the feed had moved past the build.
        Now the map answers, and hiding is only for a genuine absence."""
        src = _template()
        assert "articleEl.href = href;" in src
        assert "postUrlFor(epNumber(latest))" in src
