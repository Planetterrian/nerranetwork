"""A DOM error is not evidence about the data.

The Age of AI card said *"No episodes available yet"* above a player with no
duration, beside a summary and an article link that were both correct. Nothing
was wrong with the data: ``summaries_age_of_ai.json`` had all six episodes and
the server had rendered the card from them.

``#episodes-grid`` is what broke it. An interview show renders a GUEST rail
server-side (``interview_episodes``) and the generic archive grid is in the
``{% else %}`` branch, so on those pages the element does not exist. The script
did ``document.getElementById('episodes-grid').innerHTML = ''`` unconditionally
at the END of ``renderEpisodes`` — after it had already written the correct
title, date, audio and summary. The throw landed in the fetch handler's
``catch``, which read it as "the JSON did not load", fell back to RSS, threw
there on the same line, and ended in ``showNoEpisodes()`` — which overwrote a
true title with a false one.

Two properties keep it from coming back, and both are behavioural: the script
runs here, it is not restated.

1. Nothing dereferences the grid without checking it exists, so a page without
   one renders its card in full.
2. ``showNoEpisodes`` may only claim a show is empty where nothing has claimed
   otherwise. A failure that arrives after a success cannot un-say it.

And one structural property behind them: the fetch ``try`` covers fetching and
parsing, never rendering, so a render bug can never again be announced to a
reader as an empty show.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

import generate_html as G

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "show_page.html.j2"

# An interview show: its recent-episode rail is the server-rendered guest grid,
# so the page carries no #episodes-grid at all.
INTERVIEW_SLUG = "age_of_ai"
# An ordinary show, which does carry one. Without this the guards above could
# pass by the element having quietly disappeared everywhere.
FEED_SLUG = "tesla"


def _template() -> str:
    """The template with Jinja comments stripped.

    A guard that reads source as text can otherwise be satisfied by the prose
    explaining the rule rather than by the code obeying it.
    """
    return re.sub(r"\{#.*?#\}", "", TEMPLATE.read_text(encoding="utf-8"), flags=re.S)


def _js(*names: str) -> str:
    """Lift named functions out of the script, verbatim.

    They are plain JavaScript with no Jinja inside, which is what lets these
    assertions run the SHIPPED code.
    """
    src = _template()
    out = []
    for name in names:
        match = re.search(r"\n        (?:async )?function %s\(.*?\n        \}\n" % name, src, re.S)
        assert match, f"{name} is gone from the show page script"
        out.append(match.group(0))
    return "".join(out)


def _node(script: str) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as fh:
        fh.write(script)
        path = Path(fh.name)
    try:
        proc = subprocess.run(
            ["node", str(path)], capture_output=True, text=True, timeout=60
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout.strip().splitlines()[-1])
    finally:
        path.unlink(missing_ok=True)


_DOM = """
function el(props) {
    return Object.assign({textContent: '', dataset: {}, style: {}}, props || {});
}
function makeDoc(ids) {
    return {getElementById: (id) => (id in ids ? ids[id] : null)};
}
"""


class TestAPageWithoutAnArchiveGridStillRendersItsCard:
    """Property 1: no unguarded dereference of #episodes-grid."""

    def test_show_no_episodes_survives_a_missing_grid(self):
        out = _node(
            _DOM
            + _js("episodeGrid", "showNoEpisodes")
            + """
            const title = el({textContent: 'Loading...'});
            global.document = makeDoc({'latest-title': title});
            const HAS_FEED = true;
            globalThis.HAS_FEED = HAS_FEED;
            let threw = null;
            try { showNoEpisodes(); } catch (e) { threw = e.message; }
            console.log(JSON.stringify({threw, title: title.textContent}));
            """
        )
        assert out["threw"] is None
        # With nothing rendered, the empty state is the honest answer.
        assert out["title"] == "No episodes available yet"

    def test_render_episodes_completes_without_a_grid(self):
        """The exact line that broke: the archive loop runs LAST.

        Everything the reader sees in the card is written before it, so a
        throw there kept the writes and then had them undone by the fallback.
        """
        out = _node(
            _DOM
            + _js("episodeGrid", "setLatestTitle", "renderEpisodes")
            + """
            const title = el({textContent: 'Loading...'});
            const summary = el({});
            const audio = el({});
            const date = el({});
            global.document = makeDoc({
                'latest-title': title, 'latest-summary': summary,
                'latest-audio': audio, 'latest-date': date,
            });
            globalThis.formatDate = (d) => 'Mon, Sep 21, 2026';
            globalThis.escapeHtml = (s) => s;
            globalThis.getPreviewText = (s) => s;
            globalThis.epTitle = (r) => r.title || '';
            globalThis.epSummary = (r) => r.summary || '';
            globalThis.epNumber = (r) => r.episode;
            globalThis.postUrlFor = () => '';
            globalThis.renderLatestLangs = () => {};
            globalThis.loadFromRSS = () => { throw new Error('must not fall back'); };
            let threw = null;
            try {
                renderEpisodes([{episode: 6, date: '2026-09-21', title: 'Ep6: Matt Davis', summary: 'S', audio_url: 'https://a/b.mp3'}]);
            } catch (e) { threw = e.message; }
            console.log(JSON.stringify({
                threw, title: title.textContent, audio: audio.src,
                summary: summary.textContent,
            }));
            """
        )
        assert out["threw"] is None
        assert out["title"] == "Ep6: Matt Davis"
        assert out["audio"] == "https://a/b.mp3"
        assert out["summary"] == "S"

    def test_the_interview_page_really_has_no_grid(self, tmp_path):
        """Otherwise the guard above passes for the wrong reason."""
        G.generate_show_page(INTERVIEW_SLUG, output_dir=str(tmp_path))
        html = (tmp_path / "age-of-ai.html").read_text(encoding="utf-8")
        assert 'id="episodes-grid"' not in html
        assert "nn-guest-card" in html

    def test_an_ordinary_show_still_has_one(self, tmp_path):
        G.generate_show_page(FEED_SLUG, output_dir=str(tmp_path))
        html = (tmp_path / "tesla.html").read_text(encoding="utf-8")
        assert 'id="episodes-grid"' in html


class TestTheEmptyStateNeverContradictsARenderedCard:
    """Property 2: a later failure cannot un-say a rendered episode."""

    def test_a_rendered_title_is_left_alone(self):
        out = _node(
            _DOM
            + _js("episodeGrid", "setLatestTitle", "showNoEpisodes")
            + """
            const title = el({textContent: 'Loading...'});
            const grid = el({innerHTML: ''});
            global.document = makeDoc({'latest-title': title, 'episodes-grid': grid});
            globalThis.HAS_FEED = true;
            setLatestTitle('Ep6: Matt Davis');
            showNoEpisodes();
            console.log(JSON.stringify({title: title.textContent}));
            """
        )
        assert out["title"] == "Ep6: Matt Davis"

    def test_the_server_rendered_title_counts_as_rendered(self, tmp_path):
        """The flag the script reads is written by the server, not only by JS.

        The Age of AI card was correct in the HTML before any script ran; that
        is the state the empty state was destroying.
        """
        G.generate_show_page(INTERVIEW_SLUG, output_dir=str(tmp_path))
        html = (tmp_path / "age-of-ai.html").read_text(encoding="utf-8")
        match = re.search(r'<div class="latest-episode-title" id="latest-title"([^>]*)>([^<]*)', html)
        assert match, "the latest-episode title is gone from the show page"
        assert 'data-rendered="1"' in match.group(1)
        assert match.group(2).strip() not in ("", "Loading...")


class TestARenderFailureIsNotAFetchFailure:
    """A throw inside renderEpisodes must not be reported as missing data."""

    def test_render_errors_do_not_trigger_the_rss_fallback(self):
        out = _node(
            _js("loadEpisodes")
            + """
            const JSON_URL = 'x.json', JSON_FORMAT = 'wrapped', SHOW_NAME = 'T';
            globalThis.JSON_URL = JSON_URL;
            globalThis.JSON_FORMAT = JSON_FORMAT;
            globalThis.SHOW_NAME = SHOW_NAME;
            globalThis.recordsFrom = (d) => d.episodes || [];
            let fellBack = false;
            globalThis.loadFromRSS = () => { fellBack = true; };
            globalThis.renderEpisodes = () => { throw new TypeError("Cannot set properties of null (setting 'innerHTML')"); };
            globalThis.fetch = async () => ({ok: true, json: async () => ({episodes: [{date: '2026-09-21'}]})});
            let threw = null;
            loadEpisodes().catch((e) => { threw = e.constructor.name; })
                .then(() => console.log(JSON.stringify({fellBack, threw})));
            """
        )
        # The render bug surfaces as a page error, where it can be seen and
        # fixed -- it does not become a claim that the show has no episodes.
        assert out["fellBack"] is False
        assert out["threw"] == "TypeError"

    def test_a_real_fetch_failure_still_falls_back(self):
        out = _node(
            _js("loadEpisodes")
            + """
            globalThis.JSON_URL = 'x.json';
            globalThis.JSON_FORMAT = 'wrapped';
            globalThis.SHOW_NAME = 'T';
            globalThis.recordsFrom = (d) => d.episodes || [];
            let fellBack = false;
            globalThis.loadFromRSS = () => { fellBack = true; };
            globalThis.renderEpisodes = () => {};
            globalThis.fetch = async () => ({ok: false});
            loadEpisodes().then(() => console.log(JSON.stringify({fellBack})));
            """
        )
        assert out["fellBack"] is True
