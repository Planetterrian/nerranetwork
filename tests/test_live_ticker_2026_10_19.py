"""Oct 19 2026 — the front page's ticker is live (operator-directed).

The markets strip was printed once per build from committed files, so on a
Monday at noon it still showed Friday's closes, and the Latest headline row
only changed when the page was rebuilt. Now:

* ``GET /api/markets`` on the gallery Worker (workers/gallery/src/markets.ts)
  answers live quotes for a closed list of symbols, cached a minute.
* ``assets/js/live-ticker.js`` updates the strip and the flagship quote lines
  from it, re-reads the page's newest build for the Latest headlines, and
  moves an overflowing row as a tape that pauses (hover, focus, touch, a
  button, a hidden tab) and never moves under reduced motion.
* The printed values stay whenever the Worker does not answer.
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
from engine import newsroom as N  # noqa: E402

UTC = dt.timezone.utc


def _render_clock() -> dt.datetime:
    """13:30 ET on the newest bar in the committed closes file.

    The strip drops any value older than ``MARKET_MAX_AGE_DAYS`` or dated
    AFTER the render clock, and the nightly commits newer bars every day: a
    fixed date rendered the strip on Oct 19 and nothing on Oct 21 (a guard
    that reads committed data must tolerate today — the brand-messaging
    guard's idiom). Falls back to the pass's own date when the file is
    unreadable, so the fixture never raises before the test can say why.
    """
    fallback = dt.datetime(2026, 10, 19, 16, 21, tzinfo=UTC)
    try:
        import json
        quotes = json.loads((ROOT / "api" / "mag7_quotes.json").read_text(encoding="utf-8"))
        newest = max(q["bar_date"] for q in quotes.get("quotes", []) if q.get("bar_date"))
        y, m, d = (int(x) for x in newest.split("-"))
        return dt.datetime(y, m, d, 17, 30, tzinfo=UTC)
    except Exception:  # noqa: BLE001
        return fallback


NOW = _render_clock()
WORKER = ROOT / "workers" / "gallery" / "src"
JS = ROOT / "assets" / "js" / "live-ticker.js"


def _strip_comments(ts: str) -> str:
    ts = re.sub(r"/\*.*?\*/", "", ts, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", ts)


@pytest.fixture(scope="module")
def home(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("home")
    return G.generate_network_page(output_dir=out, now=NOW).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def hubs(tmp_path_factory):
    out = tmp_path_factory.mktemp("hubs")
    return {p.parent.name: p.read_text(encoding="utf-8")
            for p in G.generate_language_hub_pages(output_dir=out)}


class TestTheWorkerRoute:
    def test_symbols_mirror_the_strip(self):
        ts = (WORKER / "markets.ts").read_text(encoding="utf-8")
        block = re.search(r"MARKET_SYMBOLS\s*=\s*\[(.*?)\]", ts, re.S).group(1)
        symbols = re.findall(r'"([A-Z]+)"', block)
        assert symbols == list(N.MARKET_TICKERS) + [
            s for s in N.SHOW_TICKERS.values() if s not in N.MARKET_TICKERS]

    def test_the_router_serves_it(self):
        index = (WORKER / "index.ts").read_text(encoding="utf-8")
        assert 'case "GET /api/markets":' in index
        assert 'import { handleMarkets } from "./markets";' in index

    def test_previous_close_is_never_the_range_close(self):
        # CLAUDE.md landmine #22: chartPreviousClose is the close before the
        # RANGE ($445.27 for a $404.11 day).
        code = _strip_comments((WORKER / "markets.ts").read_text(encoding="utf-8"))
        assert "chartPreviousClose" not in code

    def test_a_short_public_cache_and_the_site_cors(self):
        code = _strip_comments((WORKER / "markets.ts").read_text(encoding="utf-8"))
        assert "public, max-age=${maxAge}" in code
        assert "corsHeaders(request)" in code
        assert "no-store" not in code
        assert "LIVE_TTL_S = 60" in code

    def test_an_old_quote_is_never_live(self):
        code = _strip_comments((WORKER / "markets.ts").read_text(encoding="utf-8"))
        assert 'quotes.push({ ...old, state: "close" })' in code

    def test_the_worker_has_its_own_tests(self):
        assert (ROOT / "workers" / "gallery" / "test" / "markets.test.ts").is_file()


class TestThePage:
    def test_the_strip_names_the_route_and_each_symbol(self, home):
        aside = home[home.index('id="markets"') - 80:]
        aside = aside[:aside.index("</aside>")]
        assert f'data-live-markets="{N.LIVE_MARKETS_API}"' in aside
        assert f'data-every="{N.LIVE_QUOTES_REFRESH_S}"' in aside
        quotes = re.findall(r'class="lt-quote is-\w+" data-symbol="([A-Z]+)"', aside)
        assert quotes, "the strip printed no quotes to update"
        assert '<button type="button" class="lt-tape-pause" hidden' in aside

    def test_the_flagship_quotes_are_marked(self, home):
        for line in re.findall(r'<p class="lt-flag-quote[^"]*"[^>]*>', home):
            assert 'data-symbol="' in line

    def test_the_latest_row_refreshes_and_loads_the_script(self, home):
        assert f'data-live-headlines data-every="{N.LIVE_HEADLINES_REFRESH_S}"' in home
        assert re.search(r'assets/js/live-ticker\.js(\?v=[0-9a-f]{8})?" defer></script>', home)

    def test_the_language_hubs_refresh_in_their_own_words(self, hubs):
        assert hubs, "no language hub rendered"
        for lang, html in hubs.items():
            assert "data-live-headlines" in html, lang
            assert "assets/js/live-ticker.js" in html, lang
        assert 'data-pause="Пауза" data-play="Пуск">Пауза</button>' in hubs["ru"]
        assert 'data-pause="Pause" data-play="Lecture">Pause</button>' in hubs["fr"]


class TestTheScript:
    @pytest.fixture(scope="class")
    def js(self):
        return JS.read_text(encoding="utf-8")

    def test_network_data_never_becomes_markup(self, js):
        assert "innerHTML" not in js
        assert "insertAdjacentHTML" not in js
        assert "textContent" in js

    def test_motion_respects_the_reader(self, js):
        assert "prefers-reduced-motion: reduce" in js
        for ev in ("mouseenter", "focusin", "touchstart", "visibilitychange"):
            assert ev in js, ev
        assert "aria-pressed" in js

    def test_copies_are_hidden_from_assistive_tech_and_the_tab_order(self, js):
        assert "copy.setAttribute('aria-hidden', 'true')" in js
        assert "setAttribute('tabindex', '-1')" in js

    def test_a_quote_is_live_only_when_the_worker_says_so(self, js):
        assert "q.state === 'live' ? 'Live' : 'Close'" in js

    def test_headlines_come_from_the_page_itself(self, js):
        assert "fetch(window.location.pathname, {cache: 'no-cache'" in js

    def test_css_has_the_pause_button_and_no_snap_while_moving(self):
        css = (ROOT / "templates" / "_landing_styles.html.j2").read_text(encoding="utf-8")
        assert ".lt-tape-pause[hidden] { display: none; }" in css
        assert ".is-moving > ul { scroll-snap-type: none; }" in css
