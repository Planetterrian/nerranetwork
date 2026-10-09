"""Homepage Soft-only + ban on \"when you're ready\" (Oct 9 2026).

A) On / only: keep Soft Personal (data-nn-subscribe=soft-personal),
   remove the per-show newsletter form (data-nn-subscribe=homepage),
   suppress the footer newsletter form while keeping the Personal tips
   link. #subscribe (RSS/Apple/Spotify) stays.

B) No user-facing \"when you're ready\" (curly or straight apostrophe)
   in the Soft Personal title / H1 surfaces this pass owns.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BANNED_READY = re.compile(r"when you[\u2019']re ready", re.I)
TITLE_EXACT = "Nerra Personal tips by email, no charge, no card | Nerra"
H1_EXACT = "Occasional Personal tips by email — no charge, no card"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _scrub(src: str) -> str:
    return re.sub(r"\{#.*?#\}", "", src, flags=re.S)


class _FormCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms: list[dict[str, str | None]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            self.forms.append(dict(attrs))


class TestHomepageSoftOnly:
    def test_network_page_has_soft_not_homepage_newsletter(self):
        raw = _read("templates/network_page.html.j2")
        src = _scrub(raw)
        assert "soft_personal_hero_band" in src
        assert 'data-nn-subscribe="homepage"' not in src
        assert 'id="newsletter"' not in src
        assert 'id="subscribe"' in src

    def test_generator_sets_suppress_footer_flag(self):
        src = _read("generate_html.py")
        start = src.index("def generate_network_page")
        end = src.index("\ndef ", start + 1)
        body = src[start:end]
        assert '"suppress_footer_newsletter_form": True' in body

    def test_base_suppresses_footer_form_keeps_tips_link(self):
        src = _scrub(_read("templates/base.html.j2"))
        assert "suppress_footer_newsletter_form" in src
        # Form only in the else branch of the suppress flag.
        footer = src.split("nn-footer-subscribe", 1)[1].split(
            "nn-footer-bottom", 1
        )[0]
        assert "Personal tips by email — no charge →" in footer
        assert 'data-nn-subscribe="footer"' in footer
        assert "suppress_footer_newsletter_form" in footer

    def test_rendered_homepage_soft_only_no_layout_reserve(self, tmp_path, monkeypatch):
        import generate_html as G

        monkeypatch.setattr(G, "ROOT", tmp_path)
        (tmp_path / "api").mkdir()
        (tmp_path / "site" / "data").mkdir(parents=True)
        (tmp_path / "digests").mkdir()
        written = G.generate_network_page()
        html = Path(written).read_text(encoding="utf-8")

        parser = _FormCollector()
        parser.feed(html)
        kinds = [f.get("data-nn-subscribe") for f in parser.forms]
        assert "soft-personal" in kinds
        assert "homepage" not in kinds
        assert "footer" not in kinds

        assert 'id="soft-personal-hero"' in html
        assert 'id="subscribe"' in html
        assert 'id="newsletter"' not in html
        assert "Personal tips by email — no charge →" in html
        assert 'href="personal-interest.html"' in html
        # Omitted markup, not display:none / visibility / min-height reserve.
        assert "nn-footer-subscribe" in html
        footer_block = html.split('class="nn-footer-subscribe"', 1)[1].split(
            'class="nn-footer-bottom"', 1
        )[0]
        assert "data-nn-subscribe" not in footer_block
        # Form omitted (not a hidden empty form / height reserve).
        assert "<form" not in footer_block.lower()
        assert "min-height" not in footer_block.lower()
        assert "visibility:hidden" not in footer_block.lower()

    def test_other_pages_keep_footer_newsletter_form(self, tmp_path):
        import generate_html as G

        out = G.generate_explore_page(output_dir=str(tmp_path))
        html = Path(out).read_text(encoding="utf-8")
        parser = _FormCollector()
        parser.feed(html)
        kinds = [f.get("data-nn-subscribe") for f in parser.forms]
        assert "footer" in kinds
        assert "Personal tips by email — no charge →" in html


class TestBannedWhenYoureReady:
    def test_personal_interest_title_and_h1(self):
        gen = _read("generate_html.py")
        start = gen.index("def generate_personal_interest_page")
        body = gen[start : start + 900]
        assert f'"{TITLE_EXACT}"' in body
        assert BANNED_READY.search(body) is None

        tpl = _read("templates/personal_interest_page.html.j2")
        assert f'id="spi-title">{H1_EXACT}</h1>' in tpl
        assert BANNED_READY.search(tpl) is None

    def test_owned_surfaces_have_no_banned_phrase(self):
        """Surfaces this PR owns (not _macros — hotspot on #1392)."""
        for rel in (
            "generate_html.py",
            "templates/personal_interest_page.html.j2",
            "templates/network_page.html.j2",
            "templates/base.html.j2",
            "templates/about.html.j2",
            "templates/join_page.html.j2",
            "templates/show_page.html.j2",
            "templates/contact.html.j2",
            "templates/faq.html.j2",
            "templates/how_to_listen.html.j2",
        ):
            src = _read(rel)
            # join/show may mention "ready" in other senses; ban the phrase.
            match = BANNED_READY.search(src)
            assert match is None, f"{rel} still has {match.group(0)!r}"


class TestBrandQaPathPrefixAndContactConsent:
    """Brand QA follow-up on #1393: contact consent + path_prefix hrefs."""

    _PAGES = (
        "templates/contact.html.j2",
        "templates/faq.html.j2",
        "templates/how_to_listen.html.j2",
    )
    _CONTACT_CONSENT = (
        "for marketing unless you've explicitly opted in to our emails "
        '(episode briefings or <a href="{{ path_prefix }}personal-interest.html" '
        'style="color:var(--nn-cyan);">Personal tips by email</a>).'
    )

    def test_contact_consent_copy_exact(self):
        src = _scrub(_read("templates/contact.html.j2"))
        assert self._CONTACT_CONSENT in src

    def test_templates_use_path_prefix_not_home_url(self):
        for rel in self._PAGES:
            src = _scrub(_read(rel))
            assert "{{ path_prefix }}personal-interest.html" in src, rel
            assert "{{ home_url }}personal-interest.html" not in src, rel

    def test_rendered_en_and_nested_locale_hrefs_resolve(self, tmp_path):
        """EN at site root + nested locale (path_prefix=../) both resolve."""
        import generate_html as G
        from html.parser import HTMLParser

        class _HrefGrab(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.hrefs: list[str] = []

            def handle_starttag(self, tag, attrs):
                if tag != "a":
                    return
                d = dict(attrs)
                href = d.get("href") or ""
                if href.endswith("personal-interest.html"):
                    self.hrefs.append(href)

        # Target file the hrefs must resolve to (never committed from here).
        (tmp_path / "personal-interest.html").write_text(
            "<html><title>Soft</title></html>", encoding="utf-8"
        )

        # EN — generators write at path_prefix "".
        en_dir = tmp_path / "en"
        en_dir.mkdir()
        (en_dir / "personal-interest.html").write_text(
            (tmp_path / "personal-interest.html").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        written = [
            G.generate_contact_page(output_dir=str(en_dir)),
            G.generate_faq_page(output_dir=str(en_dir)),
            G.generate_how_to_listen_page(output_dir=str(en_dir)),
        ]
        en_hrefs: list[str] = []
        for path in written:
            html = Path(path).read_text(encoding="utf-8")
            grab = _HrefGrab()
            grab.feed(html)
            assert grab.hrefs, f"no Soft Personal link in {path}"
            for href in grab.hrefs:
                en_hrefs.append(href)
                resolved = (Path(path).parent / href).resolve()
                assert resolved.exists(), f"EN href {href!r} from {path} -> {resolved}"
                assert resolved.name == "personal-interest.html"

        # Nested locale (RU-shaped): same templates with path_prefix="../".
        ru_dir = tmp_path / "ru"
        ru_dir.mkdir()
        env = G._get_jinja_env()
        shows = G._build_all_shows_list()
        for name, out_name, extra in (
            ("contact.html.j2", "contact.html", {}),
            ("faq.html.j2", "faq.html", {"cadence_answer": G._cadence_answer()}),
            ("how_to_listen.html.j2", "how-to-listen.html", {}),
        ):
            ctx = {
                "path_prefix": "../",
                "page_title": "probe",
                "page_description": "",
                "meta_description": "",
                "meta_keywords": "",
                "theme_color": "#6B47FF",
                "og_image": "",
                "canonical_url": "https://nerranetwork.com/ru/" + out_name,
                "show_color": "",
                "show_color_dark": "",
                "all_shows": shows,
                **extra,
            }
            html = env.get_template(name).render(**ctx)
            out = ru_dir / out_name
            out.write_text(html, encoding="utf-8")
            grab = _HrefGrab()
            grab.feed(html)
            assert grab.hrefs, f"no Soft Personal link in ru/{out_name}"
            for href in grab.hrefs:
                assert href.startswith("../"), f"nested locale needs ../ got {href!r}"
                resolved = (out.parent / href).resolve()
                assert resolved.exists(), (
                    f"RU href {href!r} from {out} -> {resolved}"
                )
                assert resolved.name == "personal-interest.html"

        # Sanity: EN used relative (or empty-prefix) personal-interest.html.
        assert any(h == "personal-interest.html" for h in en_hrefs)
