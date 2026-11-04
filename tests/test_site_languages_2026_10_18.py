"""The other-languages system (Oct 18 2026).

Operator: the English landing page carried the two Russian shows and their
headlines; other-language content should be reached through the header's
language selector or dedicated pages. What binds now:

* ``engine.show_lang`` owns the SITE LANGUAGES: English, plus every language
  a show renders its pages in or produces an audio track in — derived from
  the show YAMLs, never typed. ``es`` and ``zh`` have neither today and get
  no row, no hub, no menu entry.
* The English homepage reads English shows only (stories, grid, picker,
  Organization JSON-LD); the free-show COUNT stays network-wide.
* The chrome lists the shows of the page's language and links the other
  languages' hubs (header Language menu, footer, mobile menu); the footer
  newsletter picker offers the same shows.
* ``<lang>/index.html`` is generated for every non-English site language
  (``ru/index.html`` replaces the hand-written page; ``fr/index.html`` is
  new) and every hub and the homepage carry the same hreflang group.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

import generate_html as G
from engine import show_lang as L

ROOT = Path(__file__).resolve().parent.parent
NOW = dt.datetime(2026, 10, 17, 13, 30, tzinfo=dt.timezone.utc)
CYRILLIC_WORD = re.compile(r"[А-Яа-яЁё]{3,}")


@pytest.fixture(scope="module")
def home(tmp_path_factory):
    out = tmp_path_factory.mktemp("home")
    return G.generate_network_page(output_dir=out, now=NOW).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def hubs(tmp_path_factory):
    out = tmp_path_factory.mktemp("hubs")
    paths = G.generate_language_hub_pages(output_dir=out)
    return {p.parent.name: p.read_text(encoding="utf-8") for p in paths}


def _body(html):
    return html.split('<main id="main-content">', 1)[1]


def _chrome(html):
    return html.split('<main id="main-content">', 1)[0]


# ---------------------------------------------------------------------------
# The vocabulary has one owner
# ---------------------------------------------------------------------------

class TestVocabulary:
    def test_site_languages_are_derived_from_the_yamls(self):
        langs = L.site_languages(G.NETWORK_SHOWS)
        assert langs[0] == "en"
        assert "ru" in langs, "two shows render their pages in Russian"
        assert "fr" in langs, "seven shows produce a French track"
        # No show produces these today; a typed list would still show them.
        assert "zh" not in langs and "es" not in langs

    def test_track_languages_follow_the_show_yaml(self):
        assert L.track_languages("tesla") == frozenset({"fr", "ru"})
        assert L.track_languages("finansy_prosto") == frozenset()
        assert L.track_languages("nerra_daily") is None  # registry-only

    def test_hub_path_is_the_committed_ru_root_shape(self):
        assert L.language_hub_path("en") == ""
        assert L.language_hub_path("ru") == "ru/index.html"
        assert L.language_hub_path("fr") == "fr/index.html"

    def test_generate_html_reads_the_same_vocabulary(self):
        assert G._listening_languages() == L.site_languages(G.NETWORK_SHOWS)
        assert G._producing_track_languages("tesla") == set(L.track_languages("tesla"))
        rows = G._site_language_links()
        assert [r["lang"] for r in rows] == L.site_languages(G.NETWORK_SHOWS)
        assert {r["label"] for r in rows} >= {"English", "Русский", "Français"}

    def test_every_show_dict_carries_its_page_language(self):
        shows = G._build_all_shows_list()
        by_slug = {s["slug"]: s["page_lang"] for s in shows}
        assert by_slug["finansy_prosto"] == "ru" and by_slug["privet_russian"] == "ru"
        assert by_slug["tesla"] == "en"
        assert all(lang == "ru" for slug, lang in by_slug.items()
                   if slug in ("finansy_prosto", "privet_russian"))


# ---------------------------------------------------------------------------
# The English homepage carries English shows only
# ---------------------------------------------------------------------------

class TestEnglishHomepage:
    def test_no_russian_show_runs_in_the_body(self, home):
        body = _body(home)
        for name in ("Финансы Просто", "Привет, Русский!"):
            assert name not in body, name
        for page in ("ru/finansy-prosto.html", "ru/privet-russian.html"):
            assert f'href="{page}"' not in body, page
        # No Russian headline anywhere in the body: the one Cyrillic word
        # allowed is the hub's own name on the "In other languages" chip.
        assert set(CYRILLIC_WORD.findall(body)) <= {"Русский"}

    def test_grid_and_json_ld_are_the_english_public_shows(self, home):
        english = G._english_shows(G._public_shows())
        grid = home.split('id="shows"', 1)[1].split("</section>", 1)[0]
        for s in english:
            assert f'href="{s["show_page"]}" class="show-card' in grid, s["slug"]
        assert grid.count('class="show-card glass-card"') == len(english)
        import json
        blocks = [json.loads(b) for b in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', home.split("</head>")[0], re.S)]
        org = next(b for b in blocks if b.get("@type") == "Organization")
        assert {p["name"] for p in org["hasPart"]} == {s["name"] for s in english}

    def test_free_show_count_stays_network_wide(self, home):
        # The promise counts every free show, Russian ones included; only the
        # page's LISTS are English (26 vs 24 today).
        total = len(G._public_shows())
        assert len(G._english_shows(G._public_shows())) < total
        assert G._public_show_count_cached() == total
        # The visitor copy is count-free (Oct 18); the count the share card
        # and the stats pages read is the network-wide one.
        from engine import brand as B
        assert f"{total} free shows" in B.network_promise(G._public_show_count_cached())

    def test_other_languages_are_linked_as_hubs(self, home):
        body = _body(home)
        chips = re.findall(r'class="lt-chip" href="([^"]+)" lang="(\w+)" hreflang="\w+">([^<]+)<', body)
        assert ("ru/index.html", "ru", "Русский") in chips
        assert ("fr/index.html", "fr", "Français") in chips
        # The About copy points at the Russian page instead of listing the shows.
        about = body.split('id="about"', 1)[1]
        assert 'href="ru/index.html" hreflang="ru"' in about


# ---------------------------------------------------------------------------
# The chrome follows the page language
# ---------------------------------------------------------------------------

class TestChrome:
    def test_english_chrome_lists_english_shows_and_links_the_hubs(self, home):
        chrome = _chrome(home)
        assert "Финансы Просто" not in chrome and "Привет, Русский!" not in chrome
        # Header Language menu: a Site link per language, the current marked,
        # and audio radios for the same set — no 中文 (no Chinese track).
        site = re.findall(r'class="nn-lang-site"[^>]*hreflang="(\w+)"\s+href="([^"]+)"(.*?)>', chrome, re.S)
        assert [(a, b) for a, b, _ in site] == [("en", "/"), ("fr", "fr/index.html"), ("ru", "ru/index.html")]
        assert 'aria-current="page"' in site[0][2]
        assert re.findall(r'data-lang="(\w+)" class="nn-lang-opt"', chrome) == ["en", "fr", "ru"]
        assert "中文" not in chrome
        # Footer and mobile menu link the hubs.
        footer = home.split("<footer", 1)[1]
        assert 'href="ru/index.html" lang="ru" hreflang="ru">Русский</a>' in footer
        assert 'href="fr/index.html" lang="fr" hreflang="fr">Français</a>' in footer
        assert 'class="nn-mobile-shows nn-mobile-langs"' in chrome
        assert 'href="ru/index.html" class="nn-mobile-show-link" lang="ru" hreflang="ru">Русский</a>' in chrome

    def test_footer_picker_offers_the_chrome_shows(self, tmp_path):
        G.generate_about_page(output_dir=tmp_path)
        html = (tmp_path / "about.html").read_text(encoding="utf-8")
        tags = re.findall(r'<label><input type="checkbox" name="tag" value="[^"]*"> ([^<]+)</label>', html)
        assert tags and "Финансы Просто" not in tags and "Привет, Русский!" not in tags
        english = [s["name"] for s in G._english_shows(G._build_all_shows_list())]
        assert set(tags) == set(english)

    def test_russian_page_chrome_lists_russian_shows(self, hubs):
        chrome = _chrome(hubs["ru"])
        names = re.findall(r'role="menuitem">\s*<picture>.*?</picture>\s*([^<\n]+)', chrome, re.S)
        assert [n.strip() for n in names] == ["Финансы Просто", "Привет, Русский!"]
        # The Language menu is in Russian and links the English site and the
        # French hub; the footer names the other languages in Russian.
        assert ">Язык<" in chrome or 'aria-label="Язык"' in chrome
        assert 'href="../fr/index.html"' in chrome
        assert "Другие языки" in hubs["ru"].split("<footer", 1)[1]

    def test_a_language_with_no_native_show_falls_back_to_english_chrome(self, hubs):
        chrome = _chrome(hubs["fr"])
        assert "Tesla Shorts Time" in chrome and "Финансы Просто" not in chrome

    def test_homepage_hreflang_group_is_every_site_language(self, home):
        head = home.split("</head>")[0]
        found = re.findall(r'hreflang="([^"]+)" href="([^"]+)"', head)
        assert found == [
            ("en", "https://nerranetwork.com/"),
            ("fr", "https://nerranetwork.com/fr/index.html"),
            ("ru", "https://nerranetwork.com/ru/index.html"),
            ("x-default", "https://nerranetwork.com/"),
        ]


# ---------------------------------------------------------------------------
# The hubs
# ---------------------------------------------------------------------------

class TestHubs:
    def test_one_hub_per_non_english_language(self, hubs):
        assert set(hubs) == set(L.site_languages(G.NETWORK_SHOWS)) - {"en"} == {"ru", "fr"}

    def test_ru_hub_has_native_shows_dubs_landers_and_channel(self, hubs):
        h = hubs["ru"]
        assert '<html lang="ru">' in h
        body = _body(h)
        assert 'href="../ru/finansy-prosto.html" class="show-card' in body
        assert 'href="../ru/privet-russian.html" class="show-card' in body
        assert body.count("По понедельникам") >= 2
        for feed in ("spacex_podcast.ru.rss", "podcast.ru.rss", "fascinating_frontiers_podcast.ru.rss",
                     "modern_investing_podcast.ru.rss"):
            assert f'href="../{feed}"' in body, feed
        assert 'href="../ru/spacex.html"' in body and 'href="../ru/tesla.html"' in body
        assert "https://www.youtube.com/@NerraRU" in body
        assert "ai-disclosure.html" in body  # the AI note, in Russian
        assert "семь подкастов" not in h

    def test_fr_hub_lists_every_show_with_a_french_feed(self, hubs):
        h = hubs["fr"]
        assert '<html lang="fr">' in h
        body = _body(h)
        producing = [s for s in G._english_shows(G._public_shows())
                     if "fr" in (L.track_languages(s["slug"]) or ())
                     and (ROOT / f"{Path(s['rss_file']).stem}.fr.rss").exists()]
        assert len(producing) >= 5
        for s in producing:
            assert f'href="../{Path(s["rss_file"]).stem}.fr.rss"' in body, s["slug"]
        assert "https://www.youtube.com/@NerraFR" in body
        assert 'class="show-card glass-card"' not in body  # no native French show
        # No letter to offer in French: the footer form is omitted (one ask).
        assert 'data-nn-subscribe="footer"' not in h
        assert 'data-nn-subscribe="footer"' in hubs["ru"]

    def test_hubs_carry_the_same_hreflang_group_and_their_canonical(self, hubs):
        for lang, h in hubs.items():
            head = h.split("</head>")[0]
            assert f'rel="canonical" href="https://nerranetwork.com/{lang}/index.html"' in head
            found = re.findall(r'hreflang="([^"]+)" href="([^"]+)"', head)
            assert found == [
                ("en", "https://nerranetwork.com/"),
                ("fr", "https://nerranetwork.com/fr/index.html"),
                ("ru", "https://nerranetwork.com/ru/index.html"),
                ("x-default", "https://nerranetwork.com/"),
            ]

    def test_every_reader_string_is_hand_written_per_language(self):
        for lang in L.site_languages(G.NETWORK_SHOWS):
            if lang != "en":
                assert lang in G._LANGUAGE_HUB_COPY, (
                    f"a show produces '{lang}' — add its hub copy")
        assert G.generate_language_hub_page("zh", output_dir=Path("/nonexistent")) is None

    def test_committed_hubs_exist_and_are_wired(self):
        for lang in ("ru", "fr"):
            assert (ROOT / lang / "index.html").is_file()
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        static = src.split("def generate_static_pages(", 1)[1].split("\n\n\n", 1)[0]
        assert "generate_language_hub_pages(dry_run=dry_run)" in static
        nightly = (ROOT / ".github/workflows/nightly-maintenance.yml").read_text(encoding="utf-8")
        assert "ru/index.html" in nightly and "fr/index.html" in nightly

    def test_sitemap_lists_every_hub(self, tmp_path):
        out = tmp_path / "sitemap.xml"
        G.generate_sitemap(out=out)
        xml = out.read_text(encoding="utf-8")
        for lang in ("ru", "fr"):
            assert f"<loc>https://nerranetwork.com/{lang}/index.html</loc>" in xml


class TestHubAppleLinks:
    def test_dubbed_show_never_links_the_english_apple_show(self, hubs):
        # The RU/FR edition is a separate Apple show (apple_show_ids.<lang>);
        # the English id would send the reader to English audio.
        english_ids = set()
        for s in G._english_shows(G._build_all_shows_list()):
            raw = G._load_yaml_quiet(ROOT / "shows" / f"{s['slug']}.yaml")
            for key in ("apple_show_id",):
                if raw.get(key):
                    english_ids.add(str(raw[key]))
            url = s.get("apple_podcasts_url") or ""
            m = re.search(r"id(\d+)", url)
            if m:
                english_ids.add(m.group(1))
        for lang, h in hubs.items():
            dubbed = h.split('id="dubbed"', 1)[1].split("</section>", 1)[0] if 'id="dubbed"' in h else ""
            for found in re.findall(r"podcasts\.apple\.com/podcast/id(\d+)", dubbed):
                assert found not in english_ids, (lang, found)


# ---------------------------------------------------------------------------
# The hubs are front pages (Oct 19 2026)
# ---------------------------------------------------------------------------

LATIN_WORD = re.compile(r"[A-Za-z]{4,}")


class TestLanguageFrontPages:
    """ru/index.html and fr/index.html are news front pages like index.html:
    the same stylesheet and assembler over the stories that exist in the
    language — a lead, the flagship band, top stories, the latest rail,
    sections — with every reader string in the language."""

    def test_the_three_front_pages_share_one_stylesheet(self):
        home_src = (ROOT / "templates/network_page.html.j2").read_text(encoding="utf-8")
        hub_src = (ROOT / "templates/language_hub.html.j2").read_text(encoding="utf-8")
        assert '{% include "_landing_styles.html.j2" %}' in home_src
        assert '{% include "_landing_styles.html.j2" %}' in hub_src
        assert (ROOT / "templates/_landing_styles.html.j2").is_file()

    def test_each_hub_has_the_front_page_shape(self, hubs):
        for lang, h in hubs.items():
            body = _body(h)
            assert 'class="lt-masthead' in body and 'class="lt-wordmark"' in body, lang
            assert 'class="lt-lead"' in body, lang
            assert 'id="latest"' in body and 'class="lt-ticker' in body, lang
            assert 'id="top-stories"' in body, lang
            assert 'id="flagships"' in body, lang
            assert 'id="shows"' in body and 'id="listen"' in body and 'id="about"' in body, lang

    def test_flagship_band_is_one_card_per_show(self, hubs):
        for lang, h in hubs.items():
            band = h.split('id="flagships"', 1)[1].split("</section>", 1)[0]
            names = re.findall(r'class="lt-flag-name"><a href="[^"]+">([^<]+)<', band)
            assert names == ["SpaceX Daily", "Tesla Shorts Time"], (lang, names)

    def test_headlines_are_translated_and_audio_is_the_translated_track(self, hubs):
        ru = _body(hubs["ru"])
        lead = re.search(r'<h2 class="lt-hl"[^>]*><a href="[^"]+">([^<]+)<', ru).group(1)
        assert CYRILLIC_WORD.search(lead), lead
        # Every dubbed story plays the language's own MP3.
        for src in re.findall(r'<audio controls preload="none" src="([^"]+)"', ru):
            assert ".ru.mp3" in src or "finansy_prosto" in src or "privet_russian" in src, src
        fr = _body(hubs["fr"])
        for src in re.findall(r'<audio controls preload="none" src="([^"]+)"', fr):
            assert src.endswith(".fr.mp3"), src
        # Russian headlines carry no lang attribute; an English one (Привет's
        # hooks are written in English) is marked.
        assert ' lang="en"' in ru

    def test_masthead_dates_and_section_headings_are_in_the_language(self, hubs):
        from engine import language_front as LF
        ru, fr = _body(hubs["ru"]), _body(hubs["fr"])
        assert re.search(r'lt-dateline" datetime="\d{4}-\d{2}-\d{2}">[а-я]+, \d+ [а-я]+ \d{4}<', ru)
        assert re.search(r'lt-dateline" datetime="\d{4}-\d{2}-\d{2}">[a-z]+ \d+ [a-zéû]+ \d{4}<', fr)
        english = {h["heading"] for h in __import__("engine.topic_hubs", fromlist=["TOPIC_HUBS"]).TOPIC_HUBS}
        for h in (ru, fr):
            for heading in re.findall(r'id="lt-sec-[^"]+">([^<]+)<', h):
                assert heading not in english, heading
        assert LF.long_date(__import__("datetime").date(2026, 10, 18), "ru") == "воскресенье, 18 октября 2026"
        assert LF.long_date(__import__("datetime").date(2026, 10, 18), "fr") == "dimanche 18 octobre 2026"

    def test_translated_hook_prefers_the_complete_description(self):
        from engine import language_front as LF
        track = {"title": "Ep 134 : L'Ukraine négocie directement avec SpaceX et le",
                 "description": "L'Ukraine négocie directement avec SpaceX et le Pentagone pour "
                                "lever les plafonds de vitesse. Deuxième phrase."}
        assert LF.translated_hook(track) == (
            "L'Ukraine négocie directement avec SpaceX et le Pentagone pour lever les plafonds de vitesse.")
        assert LF.translated_record({"translations": {"fr": {"title": "x"}}}, "fr") is None
        assert LF.translated_record({}, "ru") is None

    def test_no_english_reader_copy_leaks_into_the_russian_chrome_free_body(self, hubs):
        # The body's typed strings come from the copy dict; the only Latin in
        # the Russian page's non-headline copy is a show or product name.
        body = _body(hubs["ru"]).split("</main>", 1)[0]
        body = re.sub(r"<(script|style)\b.*?</\1>", "", body, flags=re.S)
        # Headlines (model text, in whatever language the show writes), the
        # native cards' latest-episode line and anything marked lang= are
        # content, not the page's own copy.
        body = re.sub(r"<(h2|h3|p) class=\"lt-hl\".*?</\1>", "", body, flags=re.S)
        body = re.sub(r"<li style=\"--show-color[^\"]*\"><a href=\"[^\"]+\">.*?</a></li>", "", body, flags=re.S)
        body = re.sub(r"<div class=\"lh-latest\">.*?</div>", "", body, flags=re.S)
        body = re.sub(r"<(a|span|p)\b[^>]*\blang=\"[a-z]{2}\"[^>]*>.*?</\1>", "", body, flags=re.S)
        body = re.sub(r"<[^>]+>", " ", body)
        words = set(LATIN_WORD.findall(body))
        allowed = {"Nerra", "Network", "SpaceX", "Daily", "Tesla", "Shorts", "Time",
                   "Fascinating", "Frontiers", "Modern", "Investing", "Techniques",
                   "Apple", "Podcasts", "YouTube", "NerraRU", "English", "Français", "RSS",
                   "Starship", "Falcon", "Starlink", "Dragon", "SPCX", "TSLA", "Optimus",
                   "Cybercab", "Models", "Agents", "Beginners", "Привет"}
        leaked = {w for w in words if w not in allowed and not w.isupper()}
        assert not leaked, sorted(leaked)[:20]


# ---------------------------------------------------------------------------
# The hubs are their audiences' front pages (Nov 3 2026)
# ---------------------------------------------------------------------------

def _shows(*slugs):
    """Show dicts in display order; ``slug:lang`` marks a native show."""
    out = []
    for n, item in enumerate(slugs):
        slug, _, lang = item.partition(":")
        out.append({"slug": slug, "name": slug, "display_order": n,
                    "page_lang": lang or "en"})
    return out


def _funnel_file(tmp_path, by_show):
    """A fixture api/funnel.json carrying only the reach rows."""
    import json
    f = tmp_path / "funnel.json"
    f.write_text(json.dumps({"stages": {"reach": {"by_show": by_show}}}), encoding="utf-8")
    return f


#: FF-RU out-views SpaceX-RU and Tesla-RU; MIT has no ru row and no fr row.
FIXTURE_REACH = {
    "fascinating_frontiers": {"by_channel": {"en": {"views": 3185},
                                             "fr": {"views": 3819}, "ru": {"views": 20074}}},
    "spacex": {"by_channel": {"en": {"views": 10357}, "fr": {"views": 2680}, "ru": {"views": 5966}}},
    "tesla": {"by_channel": {"en": {"views": 6553}, "fr": {"views": 3613}, "ru": {"views": 4901}}},
    "modern_investing": {"by_channel": {"en": {"views": 769}}},
    "models_agents": {"by_channel": {"en": {"views": 900}, "fr": {"views": 0}}},
}


class TestLanguageFrontsServeTheirAudience:
    """Nov 2 2026: both hubs led with Modern Investing's Treasury-auction /
    TFSA story and ranked their shows by ENGLISH downloads. The channel's own
    views rank the page, the lead rotates only through subjects a show the
    channel watches (or a native show) has a story in, and the hubs share
    with a card in the language."""

    def test_ranked_by_the_channels_own_views_then_display_order(self, tmp_path):
        f = _funnel_file(tmp_path, FIXTURE_REACH)
        shows = _shows("tesla", "spacex", "modern_investing", "finansy_prosto:ru",
                       "fascinating_frontiers", "privet_russian:ru")
        ru = [s["slug"] for s in G._rank_shows_by_channel_views(shows, "ru", path=f)]
        # Ranked by RU views (FF > SpaceX > Tesla); a show with no ru row
        # (MIT, the natives) keeps its display order AFTER every ranked show.
        assert ru == ["fascinating_frontiers", "spacex", "tesla", "modern_investing",
                      "finansy_prosto", "privet_russian"]
        assert ru.index("modern_investing") > max(ru.index(s) for s in ("fascinating_frontiers", "spacex", "tesla"))
        fr = [s["slug"] for s in G._rank_shows_by_channel_views(
            _shows("tesla", "spacex", "modern_investing", "models_agents", "fascinating_frontiers"),
            "fr", path=f)]
        # 0 views is no row (never ranked as 0); MIT after every show with an fr row.
        assert fr == ["fascinating_frontiers", "tesla", "spacex", "modern_investing", "models_agents"]
        assert G._channel_views_by_show("fr", path=f) == {
            "fascinating_frontiers": 3819, "spacex": 2680, "tesla": 3613}

    def test_a_missing_or_empty_funnel_file_falls_back_to_the_english_ranking(
            self, tmp_path, monkeypatch):
        import json
        audience = tmp_path / "audience.json"
        audience.write_text(json.dumps({"shows": {"spacex": {"downloads_30d": 50},
                                                  "tesla": {"downloads_30d": 20}}}))
        monkeypatch.setattr(G, "AUDIENCE_HEADLINE_PATH", audience)
        shows = _shows("tesla", "fascinating_frontiers", "spacex")
        english = [s["slug"] for s in G._rank_shows_by_audience(shows)]
        assert english == ["spacex", "tesla", "fascinating_frontiers"]
        assert [s["slug"] for s in G._rank_shows_by_channel_views(
            shows, "ru", path=tmp_path / "nope.json")] == english
        assert G._channel_views_by_show("ru", path=tmp_path / "nope.json") is None
        bad = tmp_path / "bad.json"
        bad.write_text("{not json")
        assert [s["slug"] for s in G._rank_shows_by_channel_views(shows, "ru", path=bad)] == english
        # Readable, but no show has a row on this channel: the English ranking too.
        f = _funnel_file(tmp_path, {"spacex": {"by_channel": {"en": {"views": 5}}}})
        assert G._channel_views_by_show("zh", path=f) == {}
        assert [s["slug"] for s in G._rank_shows_by_channel_views(shows, "zh", path=f)] == english

    def test_only_the_language_hub_reads_the_channel_ranking(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        hub = src.split("def generate_language_hub_page(", 1)[1].split("\ndef ", 1)[0]
        assert "ranked = _rank_shows_by_channel_views(in_language, lang)" in hub
        assert "_rank_shows_by_audience(in_language)" not in hub
        assert "lead_shows=lead_shows" in hub
        home = src.split("def generate_network_page(", 1)[1].split("\ndef ", 1)[0]
        assert "ranked = _rank_shows_by_audience(public)" in home
        assert "_rank_shows_by_channel_views" not in home

    def _story(self, slug, day, hub, lang=""):
        return {"slug": slug, "date_obj": dt.date.fromisoformat(day), "image_url": "u",
                "image_orientation": "landscape", "hub_id": hub, "lang": lang}

    def test_the_lead_comes_from_a_show_the_channel_watches_or_a_native_show(self):
        from engine import language_front as LF
        from engine import landing_test as LT
        from engine import brand as B

        order = ["fascinating_frontiers", "spacex", "tesla", "modern_investing", "finansy_prosto"]
        lead_shows = ["fascinating_frontiers", "spacex", "tesla", "finansy_prosto"]  # no MIT row
        for k in range(14):
            day = (dt.date(2026, 11, 2) + dt.timedelta(days=k)).isoformat()
            stories = [self._story("modern_investing", day, "markets"),
                       self._story("fascinating_frontiers", day, "space"),
                       self._story("spacex", day, "space"), self._story("tesla", day, "tesla"),
                       self._story("finansy_prosto", "2026-10-26", "markets")]
            page = LF.assemble(stories, lang="ru", audience_order=order,
                               flagships=B.FLAGSHIP_SHOW_SLUGS, lead_shows=lead_shows)
            # Never the markets story whose only candidate has no ru row,
            # whatever the day's index — and never a flagship (its own band).
            assert page["lead"]["slug"] == "fascinating_frontiers", day
            # MIT still runs on the page: a top story, never dropped.
            assert "modern_investing" in {s["slug"] for s in page["top"]}
        # lead_shows=None keeps the English rotation over every show: on a
        # "markets" day MIT leads as before (the behaviour this replaced).
        day = next(d for d in (dt.date(2026, 11, 2) + dt.timedelta(days=k) for k in range(7))
                   if LT.LEAD_ROTATION[d.toordinal() % len(LT.LEAD_ROTATION)] == "markets")
        stories = [self._story("modern_investing", day.isoformat(), "markets"),
                   self._story("fascinating_frontiers", day.isoformat(), "space")]
        assert LF.assemble(stories, lang="ru", audience_order=order,
                           flagships=B.FLAGSHIP_SHOW_SLUGS)["lead"]["slug"] == "modern_investing"
        assert LF.lead_rotation_for(stories, lead_shows) == ["space"]
        assert LF.lead_rotation_for(stories, []) == []

    def test_no_eligible_story_leaves_the_fallbacks_to_the_assembler(self):
        from engine import language_front as LF
        from engine import brand as B
        # The only story of the day is MIT's: the newest day still leads
        # (Oct 31 rule) rather than nothing — the restriction is on the
        # rotation, never on whether the page has a lead.
        stories = [self._story("modern_investing", "2026-11-02", "markets")]
        page = LF.assemble(stories, lang="fr", audience_order=["modern_investing"],
                           flagships=B.FLAGSHIP_SHOW_SLUGS, lead_shows=[])
        assert page["lead"]["slug"] == "modern_investing"

    def test_the_rendered_ru_hub_leads_from_the_channels_top_three(self, tmp_path, monkeypatch):
        # Rendered through the real generator and template, with the funnel
        # file replaced by the fixture (FF-RU out-views SpaceX-RU; MIT has no
        # ru row) and every collected story moved onto one day with a
        # landscape picture, so the lead is decided by the rule and not by
        # which show happened to publish last.
        from engine import language_front as LF
        real = LF.collect_stories
        top3 = sorted(FIXTURE_REACH, key=lambda s: -FIXTURE_REACH[s]["by_channel"].get("ru", {}).get("views", 0))[:3]

        def pinned(*a, **k):
            stories = real(*a, **k)
            newest = max(s["date_obj"] for s in stories)
            for s in stories:
                s["date_obj"] = newest
                s["image_url"] = s["image_url"] or "https://example.invalid/scene.jpg"
                s["image_orientation"] = "landscape"
            return stories

        monkeypatch.setattr(G, "FUNNEL_PATH", _funnel_file(tmp_path, FIXTURE_REACH))
        monkeypatch.setattr(LF, "collect_stories", pinned)
        html = G.generate_language_hub_page("ru", output_dir=tmp_path, now=NOW).read_text(encoding="utf-8")
        lead = html.split('<article class="lt-lead"', 1)[1].split("</article>", 1)[0]
        show_page = re.search(r'<p class="lt-kicker">.*?<a href="\.\./([^"]+)">', lead, re.S).group(1)
        slug = next(s["slug"] for s in G._build_all_shows_list() if s["show_page"] == show_page)
        assert slug != "modern_investing"
        assert slug in top3 or slug in ("finansy_prosto", "privet_russian"), slug

    def test_the_hubs_share_with_a_card_in_their_language(self, hubs):
        import json
        from engine import share_cards as S
        from engine import brand as B
        alts = json.loads(S.MANIFEST_PATH.read_text(encoding="utf-8"))["alt"]
        for lang, tagline in (("ru", B.NETWORK_TAGLINE_RU), ("fr", B.NETWORK_TAGLINE_FR)):
            key = S.page_key_for_path(L.language_hub_path(lang))
            assert key == lang
            card = S.page_card_path(key)
            assert card.is_file(), card
            head = hubs[lang].split("</head>")[0]
            assert f'property="og:image" content="https://nerranetwork.com/assets/share/pages/{lang}.jpg"' in head
            alt = alts[card.relative_to(ROOT).as_posix()]
            assert tagline in alt and B.NETWORK_TAGLINE not in alt, alt
        assert CYRILLIC_WORD.search(alts["assets/share/pages/ru.jpg"])
        assert "français" in alts["assets/share/pages/fr.jpg"]
        # The card builder composes the alt from engine.brand's taglines; a
        # typed copy of either sentence is the one-owner failure.
        builder = (ROOT / "scripts" / "build_share_cards.py").read_text(encoding="utf-8")
        assert B.NETWORK_TAGLINE_RU not in builder and B.NETWORK_TAGLINE_FR not in builder
