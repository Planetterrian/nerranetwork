"""Oct 28 2026 — sitemap lastmod from content dates, never build time.

The nightly finalize job rewrites every generated page, so mtime-based
``lastmod`` (and the missing-file ``today`` fallback) stamped every
non-episode URL with the build date forever. Episode pages already read
``datePublished`` from JSON-LD; this pass extends that precedent and
omits ``<lastmod>`` where no content date exists.

Assert against ``generate_sitemap(out=...)`` writing a temp path — never
regenerate the committed ``sitemap.xml`` outside the pipeline.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

import generate_html as G

ROOT = Path(__file__).resolve().parent.parent
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
BASE = "https://nerranetwork.com"
_EP_LOC_RE = re.compile(r"/blog/[^/]+/ep\d+\.html$")
_DP_RE = re.compile(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})"')
_EP_NUM_RE = re.compile(r"^ep(\d+)\.html$", re.I)


def _url_entries(xml: str) -> list[tuple[str, str | None]]:
    """Return (loc, lastmod_or_None) for every <url> in document order."""
    root = ET.fromstring(xml)
    out: list[tuple[str, str | None]] = []
    for url in root.findall("sm:url", NS):
        loc = url.findtext("sm:loc", default="", namespaces=NS)
        lm_el = url.find("sm:lastmod", NS)
        if lm_el is None:
            out.append((loc, None))
        else:
            out.append((loc, lm_el.text))
    return out


def _lastmod_map(xml: str) -> dict[str, str | None]:
    return {loc: lm for loc, lm in _url_entries(xml)}


def _is_episode(loc: str) -> bool:
    return bool(_EP_LOC_RE.search(loc))


def _newest_episode_datepublished(slug: str) -> str:
    show_dir = ROOT / "blog" / slug
    best_num = -1
    best_file = None
    for ep_file in show_dir.glob("ep*.html"):
        m = _EP_NUM_RE.match(ep_file.name)
        if not m:
            continue
        num = int(m.group(1))
        if num > best_num:
            best_num = num
            best_file = ep_file
    assert best_file is not None, f"no episodes for {slug}"
    head = best_file.read_text(encoding="utf-8", errors="ignore")[:20000]
    m = _DP_RE.search(head)
    assert m, f"no datePublished in {best_file}"
    return m.group(1)


@pytest.fixture(scope="module")
def sitemap_xml(tmp_path_factory):
    out = tmp_path_factory.mktemp("sm") / "sitemap.xml"
    G.generate_sitemap(out=out)
    return out.read_text(encoding="utf-8")


class TestSitemapLastmodContentDates:
    def test_determinism_non_episode_lastmods(self, tmp_path):
        a = tmp_path / "a.xml"
        b = tmp_path / "b.xml"
        G.generate_sitemap(out=a)
        G.generate_sitemap(out=b)
        ma = _lastmod_map(a.read_text(encoding="utf-8"))
        mb = _lastmod_map(b.read_text(encoding="utf-8"))
        non_ep_a = {k: v for k, v in ma.items() if not _is_episode(k)}
        non_ep_b = {k: v for k, v in mb.items() if not _is_episode(k)}
        assert non_ep_a == non_ep_b
        assert non_ep_a, "expected non-episode URLs in the sitemap"

    def test_no_non_episode_url_carries_build_date(self, sitemap_xml):
        """Build-date stamping is gone: omit surfaces have no lastmod, and
        every remaining non-episode lastmod matches independently-read
        page/episode content (datePublished / Last updated / ISO dates).
        A content date may equal today; the clock must not be the source.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        by_loc = _lastmod_map(sitemap_xml)

        # Surfaces that must omit lastmod entirely (rule 5).
        for suffix in (
            "/",
            "/blog/index.html",
            "/about.html",
            "/privacy-policy.html",
            "/faq.html",
            "/tesla-dashboard.html",
            "/join.html",
            "/topics/index.html",
        ):
            loc = f"{BASE}{suffix}" if suffix != "/" else f"{BASE}/"
            if loc in by_loc:
                assert by_loc[loc] is None, f"{loc} must omit lastmod, got {by_loc[loc]}"

        # Language hub indexes (not per-show pages under /ru/ — those can
        # be show hubs with episode-derived lastmod).
        for hub in (f"{BASE}/ru/index.html", f"{BASE}/fr/index.html"):
            if hub in by_loc:
                assert by_loc[hub] is None, f"{hub} must omit lastmod"

        # Every non-episode lastmod must equal a content-derived value.
        narr_re = re.compile(r"Last updated\s+(\d{4}-\d{2}-\d{2})")
        iso_re = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
        show_by_page = {
            cfg["show_page"]: slug for slug, cfg in G.NETWORK_SHOWS.items()
        }
        show_by_summaries = {
            cfg["summaries_page"]: slug for slug, cfg in G.NETWORK_SHOWS.items()
        }

        for loc, lm in by_loc.items():
            if _is_episode(loc) or lm is None:
                continue
            path = loc[len(BASE) + 1:]  # strip https://host/
            expected = None
            if path in show_by_page:
                expected = _newest_episode_datepublished(show_by_page[path])
            elif path in show_by_summaries:
                expected = _newest_episode_datepublished(show_by_summaries[path])
            elif path.startswith("blog/") and path.endswith("/index.html"):
                slug = path.split("/")[1]
                expected = _newest_episode_datepublished(slug)
            elif re.match(r"blog/[^/]+/page\d+\.html$", path):
                slug = path.split("/")[1]
                expected = _newest_episode_datepublished(slug)
            elif path.endswith("-narrative.html"):
                text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")
                m = narr_re.search(text)
                expected = m.group(1) if m else None
            elif path == "claims.html" or path.startswith("claims/"):
                text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")
                dates = iso_re.findall(text)
                # Match generator: cap at newest episode datePublished so
                # future market-resolution dates in claim text are ignored.
                if path.startswith("claims/") and path.endswith(".html"):
                    slug = path[len("claims/"):-len(".html")]
                    ceiling = (
                        _newest_episode_datepublished(slug)
                        if slug in G.NETWORK_SHOWS
                        else ""
                    )
                else:
                    ceiling = ""
                if not ceiling:
                    ceiling = max(
                        (
                            _newest_episode_datepublished(s)
                            for s in G.NETWORK_SHOWS
                            if (ROOT / "blog" / s).exists()
                        ),
                        default="",
                    )
                if ceiling:
                    dates = [d for d in dates if d <= ceiling]
                expected = max(dates) if dates else None
            assert expected is not None, (
                f"{loc} has lastmod={lm} but no content rule explains it "
                f"(would be a build-date stamp; today={today})"
            )
            assert lm == expected, f"{loc}: lastmod {lm} != content date {expected}"

    def test_no_non_episode_lastmod_newer_than_newest_episode(self, sitemap_xml):
        entries = _url_entries(sitemap_xml)
        ep_dates = [lm for loc, lm in entries if _is_episode(loc) and lm]
        assert ep_dates, "expected episode lastmods"
        newest_ep = max(ep_dates)
        for loc, lm in entries:
            if _is_episode(loc) or lm is None:
                continue
            assert lm <= newest_ep, (
                f"{loc} lastmod={lm} is newer than newest episode {newest_ep}"
            )

    def test_show_page_and_blog_index_match_newest_episode(self, sitemap_xml):
        expected = _newest_episode_datepublished("tesla")
        by_loc = _lastmod_map(sitemap_xml)
        assert by_loc[f"{BASE}/tesla.html"] == expected
        assert by_loc[f"{BASE}/blog/tesla/index.html"] == expected

    def test_url_with_no_derivable_date_has_no_lastmod_element(self, sitemap_xml):
        # Homepage and network blog hub omit <lastmod> entirely.
        root = ET.fromstring(sitemap_xml)
        for want in (f"{BASE}/", f"{BASE}/blog/index.html"):
            matched = False
            for url in root.findall("sm:url", NS):
                loc = url.findtext("sm:loc", default="", namespaces=NS)
                if loc != want:
                    continue
                matched = True
                assert url.find("sm:lastmod", NS) is None, (
                    f"{want} must have no <lastmod> element"
                )
            assert matched, f"{want} missing from sitemap"

    def test_at_least_one_url_keeps_a_lastmod(self, sitemap_xml):
        entries = _url_entries(sitemap_xml)
        with_lm = [(loc, lm) for loc, lm in entries if lm]
        assert with_lm, "blanket lastmod removal — at least one URL must keep one"
        # Prefer a non-episode guard so we know show/claims/narrative path works.
        non_ep = [p for p in with_lm if not _is_episode(p[0])]
        assert non_ep, "expected at least one non-episode lastmod (show or claims)"
