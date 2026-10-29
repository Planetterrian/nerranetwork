"""Read buttons everywhere an episode plays, and a My Nerra page that ships
what its template says (Oct 29 2026).

Operator: My Nerra still showed the wrong stock quotes after PR #1577, and
every surface should carry a "Read" button to the written story. The quotes
were wrong because the template change never reached the committed
``account.html``: the page the site served still read the morning's
``api/tsla.json``. A template change to a static page commits the page it
renders, and these guards read the committed file as well as the template.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class TestMyNerraShipsLiveQuotes:
    def test_committed_account_page_reads_no_morning_quote_file(self):
        html = _read("account.html")
        assert "api/tsla.json" not in html and "api/spcx.json" not in html
        assert "NNMarkets" in html and "assets/js/nn-markets.js" in html

    def test_template_reads_no_morning_quote_file(self):
        src = _read("templates/account_page.html.j2")
        assert "api/tsla.json" not in src and "api/spcx.json" not in src

    def test_committed_account_page_carries_the_read_buttons(self):
        html = _read("account.html")
        assert "function readBtn" in html and "data-ed-notes" in html


class TestReadButtonEverywhere:
    def test_one_shared_style(self):
        css = _read("styles/main.css")
        assert re.search(r"^\.nn-read \{", css, re.M)
        assert ".nn-gp-read" in css

    def test_my_nerra_cards_rail_and_catch_up(self):
        src = _read("templates/account_page.html.j2")
        assert src.count("readBtn(s, false)") >= 2      # card meta + Latest rail
        assert "readBtn(s, true)" in src                # catch-up row
        # The bare text link it replaces is gone.
        assert "esc(storyHref(s)) + '\">Read</a>'" not in src

    def test_front_page_and_language_hubs(self):
        for rel in ("templates/network_page.html.j2", "templates/language_hub.html.j2"):
            src = _read(rel)
            assert 'class="nn-read"' in src, rel
            # The lead keeps its own "Read the full story" button, not two.
            assert "meta(s, listen=false, read=false)" in src, rel

    def test_watch_cards(self):
        src = _read("templates/watch_page.html.j2")
        assert 'class="wt-item"' in src and 'class="nn-read"' in src
        assert "querySelectorAll('.wt-item')" in src   # the filter hides the pair

    def test_for_you_cards(self):
        src = _read("assets/js/for-you.js")
        assert "nn-read is-round" in src
        # A link never sits inside the play button.
        assert "li.appendChild(read)" in src

    def test_player_bar(self):
        src = _read("assets/js/nn-player.js")
        assert "nn-gp-read" in src
        assert "ui.read.hidden = !safeUrl(it.post)" in src


class TestEditionNotesAreRebuiltNotPasted:
    def test_notes_come_from_an_allow_list(self):
        src = _read("templates/account_page.html.j2")
        assert "var NOTE_TAGS" in src and "var NOTE_DROP" in src
        assert "SCRIPT: 1" in src
        # The feed item's markup is never written as-is.
        body = src[src.index("function noteNodes"):src.index("function editionNotes")]
        assert "innerHTML" not in body
        assert "/^https:\\/\\//i.test(h)" in body
