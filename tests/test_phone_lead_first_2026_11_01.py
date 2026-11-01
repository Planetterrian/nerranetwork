"""Nov 1 2026 (operator decision): on a phone the front page's lead story
comes before the promise.

No story was on a phone's first screen: the lead headline started below
the masthead, the promise, its buttons, the markets strip, the section rail
and the headline tape (y = 732 on a 390 x 844 screen). The top of the front
page is now one group (``.lt-front-top``) that a phone reorders: date line,
brand line, the lead story, then the promise and everything after it.
Desktop is unchanged (measured before and after at 1440 px: the same
positions to the pixel).

Every render goes to ``tmp_path``: never read a committed generated page.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate_html as G  # noqa: E402

NOW = dt.datetime(2026, 10, 17, 13, 30, tzinfo=dt.timezone.utc)
STYLES = ROOT / "templates/_landing_styles.html.j2"


@pytest.fixture(scope="module")
def home(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("home")
    return G.generate_network_page(output_dir=out, now=NOW).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def hubs(tmp_path_factory):
    out = tmp_path_factory.mktemp("hubs")
    return {p.parent.name: p.read_text(encoding="utf-8")
            for p in G.generate_language_hub_pages(output_dir=out)}


def _phone_block() -> str:
    css = STYLES.read_text(encoding="utf-8")
    start = css.index("@media (max-width: 640px) {")
    depth, i = 0, start
    while True:
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[start:i]
        i += 1


class TestTheTopIsOneGroup:
    def _check(self, html: str):
        body = html.split('<main id="main-content">', 1)[1]
        start = body.index('<div class="lt-front-top">')
        header = body.index('<header class="lt-masthead container">')
        promise = body.index('class="lt-standfirst-wrap"')
        lead = body.index('<section class="lt-top container"')
        lead_end = body.index("</section>", lead)
        # masthead, promise and lead all sit inside the group, in that order
        assert start < header < promise < lead
        # the group closes right after the lead section
        after = body[lead_end + len("</section>"):].lstrip()
        assert after.startswith("</div>"), after[:80]
        # and only one group per page
        assert body.count('class="lt-front-top"') == 1

    def test_homepage(self, home):
        self._check(home)

    def test_language_front_pages(self, hubs):
        assert hubs, "no language front pages rendered"
        for lang, html in hubs.items():
            self._check(html)

    def test_the_masthead_is_inside_main_so_it_is_no_landmark(self, home):
        main = home.split('<main id="main-content">', 1)[1]
        assert '<header class="lt-masthead container">' in main


class TestPhoneOrder:
    def test_the_phone_block_reorders_the_group(self):
        block = _phone_block()
        assert re.search(r"\.lt-front-top\s*\{\s*display:\s*flex;\s*flex-direction:\s*column;", block)
        assert "display: contents" in block
        for sel in (".lt-front-top .lt-masthead,", ".lt-front-top .lt-masthead-inner,",
                    ".lt-front-top .lt-masthead-row"):
            assert sel in block, sel

        def order(sel: str) -> int:
            m = re.search(re.escape(sel) + r"\s*\{[^}]*?order:\s*(\d+)", block)
            assert m, sel
            return int(m.group(1))

        assert (order(".lt-front-top .lt-masthead-meta")
                < order(".lt-front-top .lt-brandline")
                < order(".lt-front-top > .lt-top")
                < order(".lt-front-top .lt-standfirst-wrap")
                < order(".lt-front-top > *"))

    def test_centred_containers_keep_the_full_width(self):
        # A .container centres itself with auto margins; in a flex column
        # that shrinks it to its content and the tapes overflow the phone.
        block = _phone_block()
        assert re.search(r"\.lt-front-top > \*\s*\{[^}]*width:\s*100%", block)

    def test_desktop_rules_never_reorder(self):
        css = STYLES.read_text(encoding="utf-8")
        outside = css.replace(_phone_block(), "")
        assert ".lt-front-top" not in outside
