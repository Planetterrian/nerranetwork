"""Verified website findings, fixed (Oct 18 2026, after the front-page merge).

What these pin:

* every "N shows … free" / network-size sentence on about, support, sponsor,
  explore, how-to-listen and press says the FREE count the homepage says
  (``_public_shows``) — the five members-only Omni View desks had made it 31
  beside the homepage's 26; a page that lists those desks says how many are
  members-only instead of calling the whole set free;
* Developing stories: the product-news verbs are generic, and a same-show
  pair that differs by one swapped word is a segment label (MIT's
  "Interactive Brokers … Scanner"), with the three real threads of the
  Oct 18 window kept;
* every rendered page's share image is a file that exists (data.html carried
  the dead assets/og-default.png from a render older than the share cards);
* the homepage's Tesla dashboard card states the strip's own close and date;
* a show page advertises only the translated tracks the show produces today
  (the frozen ZH feeds kept a 中文 chip on tesla / spacex);
* the landing-test.html stub's canonical is the bare origin;
* both "Find your show" links on the homepage go to explore.html.

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
from engine import newsroom as N  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 18, 15, 0, tzinfo=UTC)

#: "26 shows", "26 free shows", "26 independent shows", "26 podcasts", and
#: the press kit's "Shows: 26 free".
_COUNT_RE = re.compile(
    r"\b(\d{1,3})\s+(?:free\s+|independent\s+)?(?:shows|podcasts)\b|Shows:\s*(\d{1,3})", re.I)


def _text(html: str) -> str:
    """Visible text plus every meta content (Google prints the meta)."""
    metas = " ".join(re.findall(r'<meta[^>]+content="([^"]*)"', html))
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", f"{metas} {body}")


# ---------------------------------------------------------------------------
# 1. One free-show count
# ---------------------------------------------------------------------------

_COUNT_PAGES = [
    ("about.html", G.generate_about_page),
    ("support.html", G.generate_support_page),
    ("sponsor.html", G.generate_sponsor_page),
    ("explore.html", G.generate_explore_page),
    ("how-to-listen.html", G.generate_how_to_listen_page),
    ("press.html", G.generate_press_page),
]


class TestOneFreeShowCount:
    def test_the_registry_has_members_only_shows(self):
        """The finding only exists while gated shows exist; if this ever
        fails the count guard below is checking nothing interesting."""
        assert G._members_show_count() > 0
        assert G._public_show_count_cached() + G._members_show_count() <= len(G.NETWORK_SHOWS)

    @pytest.mark.parametrize("name,generator", _COUNT_PAGES, ids=[n for n, _ in _COUNT_PAGES])
    def test_every_show_count_is_the_free_count(self, tmp_path, name, generator):
        generator(output_dir=tmp_path)
        text = _text((tmp_path / name).read_text(encoding="utf-8"))
        counts = [int(a or b) for a, b in _COUNT_RE.findall(text)]
        assert counts, f"{name}: no show count rendered"
        public = G._public_show_count_cached()
        assert set(counts) == {public}, f"{name}: {counts} vs {public} free shows"

    @pytest.mark.parametrize("name,generator", [
        ("explore.html", G.generate_explore_page),
        ("how-to-listen.html", G.generate_how_to_listen_page),
    ])
    def test_a_page_that_lists_members_shows_never_calls_them_all_free(
            self, tmp_path, name, generator):
        generator(output_dir=tmp_path)
        text = _text((tmp_path / name).read_text(encoding="utf-8"))
        assert not re.search(r"all free|every show is free|all nerra network shows are free",
                             text, re.I), name
        assert f"{G._members_show_count()} for" in text, name

    def test_no_generator_counts_the_registry_as_free(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        for fn in ("generate_about_page", "generate_support_page", "generate_press_page",
                   "generate_sponsor_page"):
            body = src.split(f"def {fn}(")[1].split("\ndef ")[0]
            assert "len(NETWORK_SHOWS)" not in body, fn
            assert "len(_published_show_ids())" not in body, fn


# ---------------------------------------------------------------------------
# 2. Developing stories: no false threads
# ---------------------------------------------------------------------------

def _ep(slug, day, headlines, hour=10):
    d = dt.date.fromisoformat(day)
    when = dt.datetime(d.year, d.month, d.day, hour, tzinfo=UTC)
    return {"slug": slug, "show_name": slug.title(), "show_page": f"{slug}.html",
            "brand_color": "#123456", "day": d, "stamp": N.stamp(day, when, NOW),
            "post_url": f"blog/{slug}/ep{d.day:03d}.html", "headlines": headlines}


FILLER = [_ep(f"s{n}", "2026-10-1" + str(n % 7 + 2), [f"Unrelated filler headline number {n} about item{n} widget{n}"])
          for n in range(40)]


class TestDevelopingFalseThreads:
    def test_release_verbs_never_make_a_thread(self):
        eps = [_ep("mag7", "2026-10-18", ["Google releases a $100 Home Speaker for Gemini"]),
               _ep("models_agents", "2026-10-14",
                   ["Google Releases Gemini 4 Argon API With 1M Token Output Limit"])]
        assert N.developing_stories(eps + FILLER, NOW) == []
        for verb in ("release", "releases", "launch", "launches", "unveils", "announces"):
            assert verb in N.GENERIC_WORDS, verb

    def test_a_one_word_swap_of_a_segment_label_is_furniture(self):
        eps = [_ep("modern_investing", "2026-10-16", ["Interactive Brokers TWS Scanner"]),
               _ep("modern_investing", "2026-10-18", ["Interactive Brokers Volume Scanner"])]
        assert N.developing_stories(eps + FILLER, NOW) == []

    def test_the_real_threads_survive(self):
        eps = [
            _ep("mag7", "2026-10-16", ["Apple calls iPhone Duo demand extraordinary as new orders slip into 2027"]),
            _ep("mag7", "2026-10-18", ["Gurman says iPhone Duo walk-in calls are premature"]),
            _ep("spacex", "2026-10-15", ["Super Heavy Booster 23 moved to Massey for initial cryogenic proof testing"]),
            _ep("spacex", "2026-10-18", ["Super Heavy Booster 23 completed cryogenic proof testing at Starbase"]),
            _ep("fascinating_frontiers", "2026-10-16", [
                "Perseverance rover just added another 91 meters to its Mars record in one day, "
                "pushing the total distance past prior benchmarks."]),
            _ep("fascinating_frontiers", "2026-10-18", ["Perseverance Sets New Distance Record on Mars"]),
        ]
        heads = {t["latest"]["headline"] for t in N.developing_stories(eps + FILLER, NOW)}
        assert heads == {
            "Gurman says iPhone Duo walk-in calls are premature",
            "Super Heavy Booster 23 completed cryogenic proof testing at Starbase",
            "Perseverance Sets New Distance Record on Mars",
        }

    def test_committed_window_has_no_false_thread(self):
        """Replay on the homepage's own inputs (the Oct 18 2026 window)."""
        threads = N.developing_stories(G._newsroom_episodes(G._public_shows(), NOW), NOW)
        if not threads:
            pytest.skip("the committed digests have moved past the calibration window")
        heads = " | ".join(t["latest"]["headline"] for t in threads)
        assert "Home Speaker" not in heads
        assert "Interactive Brokers" not in heads


# ---------------------------------------------------------------------------
# 3. Every share image exists
# ---------------------------------------------------------------------------

_OG_PAGES = [
    ("data.html", G.generate_data_hub_page),
    *_COUNT_PAGES,
]


class TestShareImagesExist:
    @pytest.mark.parametrize("name,generator", _OG_PAGES, ids=[n for n, _ in _OG_PAGES])
    def test_og_and_twitter_image_are_committed_files(self, tmp_path, name, generator):
        generator(output_dir=tmp_path)
        html = (tmp_path / name).read_text(encoding="utf-8")
        urls = re.findall(r'<meta (?:property="og:image"|name="twitter:image") content="([^"]+)"', html)
        assert len(urls) == 2, name
        for url in urls:
            assert url.startswith("https://nerranetwork.com/"), url
            rel = url[len("https://nerranetwork.com/"):]
            assert (ROOT / rel).is_file(), f"{name}: {url} does not exist"

    def test_no_source_names_the_dead_default(self):
        hits = [p.name for p in [*(ROOT / "templates").glob("*.j2"), *(ROOT / "engine").glob("*.py")]
                if "og-default.png" in p.read_text(encoding="utf-8")]
        assert not hits, hits


# ---------------------------------------------------------------------------
# 4. The Tesla dashboard card says what the strip says
# ---------------------------------------------------------------------------

class TestTeslaCardMatchesStrip:
    def test_quote_line_uses_the_close_basis_and_bar_date(self):
        strip = N.market_strip(
            mag7={"quotes": [{"ticker": "TSLA", "close": 354.72, "change_pct": -2.1,
                              "bar_date": "2026-10-16"}]},
            spcx=None,
            tsla={"price": 354.72, "prev_close": 362.44, "fetched_at": "2026-10-18T08:50:02Z"},
            launches=None, now=NOW)
        q = next(q for q in strip["quotes"] if q["symbol"] == "TSLA")
        assert N.quote_line(q) == "TSLA close: $354.72 · Oct 16"
        assert N.quote_line(None) == ""

    def test_a_fetch_only_quote_is_a_last_quote(self):
        strip = N.market_strip(
            mag7=None, spcx=None,
            tsla={"price": 354.72, "prev_close": 362.44, "fetched_at": "2026-10-18T08:50:02Z"},
            launches=None, now=NOW)
        q = next(q for q in strip["quotes"] if q["symbol"] == "TSLA")
        assert N.quote_line(q).startswith("TSLA last quote: $354.72 · ")

    def test_the_homepage_card_reads_the_strip(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        v2 = src.split("def _front_page_sections(")[1].split("\ndef ")[0]
        assert "last quote on record" not in v2
        assert "_nr.quote_line(" in v2
        page = src.split("def generate_network_page(")[1].split("\ndef ")[0]
        assert page.index("_nr.market_strip(") < page.index("_front_page_sections(")


# ---------------------------------------------------------------------------
# 5. Language chips only for tracks the show produces
# ---------------------------------------------------------------------------

class TestLanguageChips:
    @pytest.mark.parametrize("slug", ["tesla", "spacex", "fascinating_frontiers"])
    def test_switched_off_zh_is_not_advertised(self, slug):
        langs = G._producing_track_languages(slug)
        assert "zh" not in langs
        feeds = G._collect_language_feeds(G.NETWORK_SHOWS[slug]["rss_file"], "", slug)
        assert "zh" not in {f["lang"] for f in feeds}
        assert {f["lang"] for f in feeds} <= langs

    def test_zh_needs_approval(self, monkeypatch):
        from types import SimpleNamespace as NS
        cfg = NS(multilingual=NS(enabled=True, languages=["fr", "zh"], zh_approved=False))
        monkeypatch.setattr(G, "_registry_show_config", lambda slug: cfg)
        assert G._producing_track_languages("x") == {"fr"}
        cfg.multilingual.zh_approved = True
        assert G._producing_track_languages("x") == {"fr", "zh"}
        cfg.multilingual.enabled = False
        assert G._producing_track_languages("x") == set()

    def test_tesla_page_has_no_chinese_chip(self, tmp_path):
        G.generate_show_page("tesla", output_dir=tmp_path)
        html = (tmp_path / G.NETWORK_SHOWS["tesla"]["show_page"]).read_text(encoding="utf-8")
        chips = re.findall(r'class="nn-chip"[^>]*data-lang="([a-z]+)"', html)
        assert "zh" not in chips


# ---------------------------------------------------------------------------
# 6. The landing-test stub's canonical
# ---------------------------------------------------------------------------

def test_homepage_stub_canonical_is_the_bare_origin(tmp_path):
    G.generate_redirect_stubs(output_dir=tmp_path)
    stub = (tmp_path / "landing-test.html").read_text(encoding="utf-8")
    assert '<link rel="canonical" href="https://nerranetwork.com/">' in stub
    assert "nerranetwork.com/index.html" not in stub


# ---------------------------------------------------------------------------
# 7. "Find your show" goes to one place
# ---------------------------------------------------------------------------

def test_every_find_your_show_link_goes_to_explore(tmp_path):
    path = G.generate_network_page(output_dir=tmp_path, now=NOW)
    html = Path(path).read_text(encoding="utf-8")
    targets = re.findall(r'<a [^>]*href="([^"]+)"[^>]*>\s*Find your show\s*</a>', html)
    assert len(targets) >= 2, targets
    assert {t.rsplit("/", 1)[-1] for t in targets} == {"explore.html"}, targets
