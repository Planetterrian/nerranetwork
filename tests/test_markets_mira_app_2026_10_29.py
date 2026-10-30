"""My Nerra's markets, member tickers, Mira's personal context and the app
(Oct 29 2026).

My Nerra printed TSLA and SPCX from the committed api/tsla.json /
api/spcx.json, which the morning show run writes before the market opens:
after the bell the card showed the previous day's close under today's date.
Quotes now come from the markets route for the stocks the member chose, the
markets minute speaks the same list, and Mira's links call is told where
today's episodes name them. Guards the mirrors (one ticker shape in Python,
the Worker and the page), the privacy of the member's feed token, and the
pages the app needs.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pytest

import generate_html as gh
from engine import personal_edition as pe
from engine.daily_edition import Segment

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _seg(slug, name, content, num=1):
    return Segment(slug=slug, show_name=name, episode_num=num, episode_title=name,
                   hook=f"{name} hook", date="2026-10-28", audio_url="https://x/a.mp3",
                   content=content, digest_dir=ROOT, transcript_path=None,
                   music_intro_offset=0.0)


class TestOneTickerShape:
    def test_python_worker_and_page_agree(self):
        ts = _read("workers/gallery/src/markets.ts")
        worker = re.search(r"MEMBER_SYMBOL_RE = (/.*?/);", ts).group(1)
        page = re.search(r"var SHAPE = (/.*?/);", _read("assets/js/nn-markets.js")).group(1)
        assert worker == page
        assert worker.strip("/") == pe.TICKER_RE.pattern.replace("\\\\", "\\")
        assert f"export const TICKERS_MAX = {pe.TICKERS_MAX};" in _read("workers/gallery/src/personal.ts")
        assert f"var MAX = {pe.TICKERS_MAX};" in _read("assets/js/nn-markets.js")

    @pytest.mark.parametrize("sym,ok", [("NVDA", True), ("SHOP.TO", True), ("BTC-USD", True),
                                        ("^GSPC", True), ("EURUSD=X", True), ("GC=F", True),
                                        ("shop", False), ("<b>", False), ("A" * 14, False)])
    def test_shapes(self, sym, ok):
        assert bool(pe.TICKER_RE.match(sym)) is ok

    def test_spec_carries_clean_tickers(self):
        spec = pe.validate_spec({"token": "a" * 32, "shows": ["spacex", "tesla"],
                                 "tickers": ["nvda", "NVDA", "<x>", "shop.to"] + [f"T{i}" for i in range(12)]})
        assert spec.tickers[:2] == ["NVDA", "SHOP.TO"] and len(spec.tickers) == pe.TICKERS_MAX
        assert pe.validate_spec({"token": "a" * 32, "shows": ["spacex", "tesla"]}).tickers is None
        assert pe.member_tickers(pe.validate_spec({"token": "a" * 32, "shows": ["spacex", "tesla"]})) == list(pe.DEFAULT_TICKERS)

    def test_the_network_list_mirrors_the_worker(self):
        ts = _read("workers/gallery/src/markets.ts")
        block = re.search(r"MARKET_SYMBOLS\s*=\s*\[(.*?)\]", ts, re.S).group(1)
        assert tuple(re.findall(r'"([A-Z]+)"', block)) == pe._NETWORK_SYMBOLS
        js = re.search(r"var NETWORK = \[(.*?)\];", _read("assets/js/nn-markets.js")).group(1)
        assert tuple(re.findall(r"'([A-Z]+)'", js)) == pe._NETWORK_SYMBOLS


class TestMyNerraQuotesAreLive:
    def test_no_committed_price_file_on_the_page(self):
        src = _read("templates/account_page.html.j2")
        assert "api/tsla.json" not in src and "api/spcx.json" not in src
        assert "NNMarkets.get(myTickers())" in src
        assert 'id="nn-markets"' in src and 'id="nn-mkt-form"' in src

    def test_tickers_are_saved_with_the_preferences(self):
        src = _read("templates/account_page.html.j2")
        assert "if (state.tickers !== null) { body.tickers = state.tickers; }" in src
        assert "NNMarkets.stored()" in src

    def test_network_text_is_never_markup(self):
        js = _read("assets/js/nn-markets.js")
        assert "innerHTML" not in js
        render = _read("templates/account_page.html.j2").split("function renderMarkets()", 1)[1].split("var mktTimer", 1)[0]
        # The cards are built with textContent; only the header strip uses
        # markup, through esc().
        assert "nm.textContent = q ? NNMarkets.name(q)" in render
        assert "esc(NNMarkets.price(q))" in render

    def test_front_page_strip_adds_your_stocks(self):
        js = _read("assets/js/live-ticker.js")
        assert "'&extra=' + encodeURIComponent(extra.join(','))" in js
        assert "'Your stocks · '" in js
        assert "document.addEventListener('DOMContentLoaded', start, {once: true})" in js


class TestTheMarketsMinute:
    def test_member_stocks_in_their_order(self):
        quotes = {"SHOP.TO": {"symbol": "SHOP.TO", "price": 212.4, "change_pct": 3.12, "currency": "CAD",
                              "name": "Shopify Inc.", "state": "close"},
                  "NVDA": {"symbol": "NVDA", "price": 215.38, "change_pct": -1.17, "state": "close"}}
        line = pe.build_markets_line(ROOT / "nowhere", ["SHOP.TO", "NVDA", "AMD"], quotes)
        assert line == ("Your markets minute: Shopify at C$212.40, up 3.1 percent; Nvidia at $215.38, "
                        "down 1.2 percent. As always, prices are from the last market close.")

    def test_never_spaced_letters(self):
        assert "S P C X" not in pe.quote_phrase("SPCX", {"price": 1, "change_pct": 0})
        assert pe.quote_phrase("XYZW", {"price": 12, "change_pct": 0.01, "currency": "USD"}).startswith(
            "ticker Ex Why Zee Double-you at $12.00, unchanged")

    def test_a_live_quote_says_trading(self):
        q = {"price": 10, "change_pct": 1, "state": "live", "currency": "USD", "name": "X Corp"}
        assert pe.quote_phrase("XX", q).startswith("X trading at $10.00")
        assert "Prices move through the day." in pe.build_markets_line(ROOT / "nowhere", ["XX"], {"XX": q})

    def test_no_quote_no_line(self):
        assert pe.build_markets_line(ROOT / "nowhere", ["ZZZZ"], {}) == ""

    def test_the_builder_asks_once_for_every_member(self):
        src = _read("scripts/build_personal_feeds.py")
        assert "quotes = fetch_market_quotes(wanted) if wanted else {}" in src
        assert "build_markets_line(ROOT, member_tickers(spec), quotes)" in src


class TestMirasPersonalContext:
    def test_stock_notes_name_the_shows(self):
        segs = [_seg("ai_chips", "AI Chips", "Nvidia shipped racks to a new cloud."),
                _seg("mag7", "MAG 7", "Apple fell; Advanced packaging rose.")]
        notes = pe.market_notes(["NVDA", "AMD"], {
            "NVDA": {"symbol": "NVDA", "price": 1, "change_pct": -1.2},
            "AMD": {"symbol": "AMD", "price": 1, "change_pct": 2.0, "name": "Advanced Micro Devices, Inc."}}, segs)
        assert notes[0] == "Nvidia (NVDA): down 1.2 percent at the last close — named in today's AI Chips."
        # "Advanced" alone never stands in for Advanced Micro Devices.
        assert notes[1].endswith("not in today's episodes.")

    def test_connections_are_names_two_episodes_share(self):
        segs = [_seg("a", "Show A", "The deal with Microsoft closed, and analysts noted Pakistan."),
                _seg("b", "Show B", "Separately, shares of Microsoft rose. The weather was calm.")]
        out = pe.cross_show_connections(segs)
        assert out == ["Microsoft — in Show A and Show B."]

    def test_absent_shows_say_why(self):
        spec = pe.validate_spec({"token": "a" * 32, "shows": ["spacex", "peptides", "tesla"]})
        segs = [_seg("spacex", "SpaceX Daily", ""), _seg("tesla", "Tesla Shorts Time", "")]
        notes = pe.absent_show_notes(spec, segs, dt.date(2026, 10, 28),
                                     names={"peptides": "Peptides Weekly"},
                                     schedules={"peptides": "Thursday"})
        assert notes == ["Peptides Weekly is not in today's edition: it publishes on Thursdays."]

    def test_blocks_reach_the_prompt(self):
        tpl = _read("shows/prompts/nerra_personal_links.txt")
        assert "{markets_block}" in tpl and "{connections_block}" in tpl
        assert '"title": "..."' in tpl
        spec = pe.validate_spec({"token": "a" * 32, "shows": ["spacex", "tesla"]})
        ctx = pe.EditionContext(edition_number=50, markets=["Nvidia (NVDA): up"], connections=["X — in A and B."],
                                absent=["P has no new episode in today's edition."])
        b = pe.personal_context_blocks(spec, ctx)
        assert "THE STOCKS THEY FOLLOW" in b["markets_block"] and "Never explain a move" in b["markets_block"]
        assert "NAMES THAT TURN UP" in b["connections_block"]
        assert "50th edition" in b["edition_block"] and "do not announce" not in b["edition_block"]
        assert "WITH NO EPISODE TODAY" in b["edition_block"]

    def test_memory_never_claims_they_heard_it(self):
        src = _read("engine/personal_stories.py") + _read("engine/personal_edition.py")
        assert "this listener heard" not in src
        assert "Never claim they heard or" in _read("engine/personal_edition.py")

    def test_edition_title_is_mira_s_when_valid(self):
        seg = _seg("spacex", "SpaceX Daily", "")
        assert pe.personal_episode_title(dt.date(2026, 10, 28), [seg], "Rockets and chips set the pace") == \
            "Wednesday — Rockets and chips set the pace"
        assert pe.personal_episode_title(dt.date(2026, 10, 28), [seg]) == "Wednesday — SpaceX Daily hook"
        assert 'links.get("title") or ""' in _read("scripts/build_personal_feeds.py")


class TestTheFeedTokenStaysPrivate:
    def test_analytics_gets_the_file_name_only(self):
        js = _read("assets/js/nn-player.js")
        assert "track('episode_play', { src: analyticsSrc(it.url)" in js
        assert "return m ? 'personal_edition/' + m[1] : u;" in js

    def test_sign_out_forgets_private_items(self):
        assert "forgetPrivate: function" in _read("assets/js/nn-player.js")
        logout = _read("templates/account_page.html.j2").split("logout: function", 1)[1].split("portal: function", 1)[0]
        assert "NNPlayer.forgetPrivate()" in logout and "'nnMe.tickers'" in logout


class TestThePlayerOnAPhone:
    def test_controls_stay_and_the_lock_screen_seeks(self):
        js = _read("assets/js/nn-player.js")
        for action in ("previoustrack", "seekto", "setPositionState", "aria-valuetext"):
            assert action in js, action
        assert "nnPlay.rate" in js
        css = _read("styles/main.css")
        block = css.split("@media (max-width: 560px) {\n  .nn-gp-inner", 1)[1].split("}\n.nn-gp-bar", 1)[0]
        assert ".nn-gp-bar { display: none; }" not in block


class TestSignInInsideTheApp:
    def test_the_email_carries_a_code_and_the_worker_checks_it(self):
        h = _read("workers/gallery/src/handlers.ts")
        assert "export async function handleLoginCode(" in h and "issueLoginCode(env, email)" in h
        assert 'case "POST /api/login-code":' in _read("workers/gallery/src/index.ts")
        assert "Type this code there instead" in _read("workers/gallery/src/magic-email.ts")

    def test_my_nerra_takes_the_code(self):
        src = _read("templates/account_page.html.j2")
        assert 'autocomplete="one-time-code"' in src and "API + '/api/login-code'" in src


class TestTheApp:
    def test_page_renders_and_is_listed(self, tmp_path):
        html = Path(gh.generate_app_page(output_dir=tmp_path)).read_text(encoding="utf-8")
        for marker in ("data-nn-install", "data-nn-install-ios", "data-nn-install-mac", "data-nn-installed",
                       "six-digit code"):
            assert marker in html, marker
        src = _read("generate_html.py")
        assert '"app.html"' in src and "generate_app_page(dry_run=dry_run)" in src
        assert "            app.html\n" in _read(".github/workflows/nightly-maintenance.yml")

    def test_manifest_screenshots_and_edition_shortcut(self):
        m = json.loads(_read("manifest.webmanifest"))
        assert {s["form_factor"] for s in m["screenshots"]} == {"narrow", "wide"}
        for s in m["screenshots"]:
            assert (ROOT / s["src"].lstrip("/")).is_file()
        assert m["shortcuts"][0]["url"].endswith("#nn-edition")

    def test_the_sheet_waits_for_a_reason_and_snoozes(self):
        js = _read("assets/js/nn-app.js")
        assert "var SHEET_SNOOZE_DAYS = 14;" in js
        assert "if (member || days >= 2)" in js
        assert "nn-consent-needed" in js
        assert "setAppBadge" in js and "nnMe.editionDone" in js

    def test_scripts_are_versioned(self):
        base = _read("templates/base.html.j2")
        assert '{{ asset_v("assets/js/nn-player.js") }}' in base
        assert "viewport-fit=cover" in base
        url = gh._asset_version("assets/js/nn-player.js")
        assert re.fullmatch(r"assets/js/nn-player\.js\?v=[0-9a-f]{8}", url)


class TestJoinPage:
    def test_checkout_carries_the_account_and_members_manage(self):
        src = _read("templates/join_page.html.j2")
        assert src.count("data-checkout data-plan=") == 2
        assert "api/account/checkout-ref" in src
        assert "account.html#nn-membership" in src


class TestEveryPageIsTheApp:
    """Oct 29 2026: the tab bar vanished on 1,479 of 3,042 pages, generated
    before the app layer existed; the service worker adds it as they load."""

    def test_the_worker_adds_the_app_layer_to_older_pages(self):
        sw = _read("sw.js")
        assert "event.respondWith(networkFirst(req, PAGES, '/offline.html').then(withAppLayer));" in sw
        assert "if (html.indexOf('assets/js/nn-app.js') !== -1) { return res; }" in sw
        for js in ("nn-markets.js", "nn-player.js", "nn-app.js"):
            assert f'<script src="/assets/js/{js}" defer></script>' in sw
        # Bumped (never reset) whenever an injected script changes, so an
        # installed app drops the cached copy: nn-2026-10-29b added Read,
        # nn-2026-10-30 made styles and scripts network first.
        m = re.search(r"var VERSION = 'nn-(\d{4}-\d{2}-\d{2})", sw)
        assert m and m.group(1) >= "2026-10-29", "the cache version went back"

    def test_the_bar_has_back_and_lights_the_section(self):
        js = _read("assets/js/nn-app.js")
        assert "data-nn-back" in js and "window.history.back()" in js
        shows = re.search(r"label: 'Shows', match: (/.*?/),", js).group(1)
        for path in ("/blog/omni_view/ep003.html", "/topics/space.html", "/tesla.html", "/explore.html"):
            assert re.search(shows.strip("/").replace("\\/", "/"), path), path
        assert "keepLinksInApp();" in js

    def test_nothing_loads_the_player_twice(self):
        assert "if (window.NNPlayer) { return; }" in _read("assets/js/nn-player.js")
        assert "if (window.NNMarkets) { return; }" in _read("assets/js/nn-markets.js")
        assert "if (document.querySelector('.nn-tabbar')) { return; }" in _read("assets/js/nn-app.js")
