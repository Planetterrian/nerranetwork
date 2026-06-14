"""Guards for the Sunday weekly-recap body sanitizer.

June 2026: the Tesla Sunday recap newsletter shipped with raw source HTML
(`<a href=...>Google News</a>`), markdown source links, "Read more (sources)"
lines, and "REAL-TIME TSLA price:" headers leaking out of the per-episode
bodies that ``build_weekly_recap_digest`` stitches together. These pin the
scrub so the regression can't return.
"""

from engine.weekly_recap import _sanitize_recap_body


def test_strips_raw_html_anchor_keeps_text():
    src = (
        'Volvo expands Supercharger access. Source: '
        '<a href="https://news.google.com/rss/articles/CBMihwFBVV" '
        'target="_blank" rel="noopener">Google News</a>'
    )
    out = _sanitize_recap_body(src)
    assert "<a" not in out and "</a>" not in out
    assert "target=" not in out and "rel=" not in out
    assert "news.google.com" not in out
    assert "Google News" in out  # link text is preserved


def test_drops_realtime_tsla_price_header():
    src = "**REAL-TIME TSLA price:** $415.50\nTesla launched a sunshade for the Model Y."
    out = _sanitize_recap_body(src)
    assert "TSLA price" not in out
    assert "Tesla launched a sunshade" in out


def test_markdown_links_preserved_by_default():
    # June 14 2026: the recap must stay transparently sourced — proper markdown
    # source citations are PRESERVED so the blog/summary render clickable links
    # (the prior collapse-to-text was the cause of the unsourced Sunday blog).
    src = "Detail. Source: [space.com](https://www.space.com/x)."
    out = _sanitize_recap_body(src)
    assert "[space.com](https://www.space.com/x)" in out  # link intact


def test_markdown_links_collapse_when_keep_links_false():
    # Plain-text contexts (e.g. a story title line) still collapse links.
    src = "See [Google News](https://news.google.com/x) and [EVChargingStations.com](https://ev.com)."
    out = _sanitize_recap_body(src, keep_links=False)
    assert "](http" not in out and "https://" not in out
    assert "Google News" in out and "EVChargingStations.com" in out


def test_bare_urls_dropped_but_markdown_link_urls_kept():
    # A bare URL reads badly aloud and is dropped; a markdown-link URL is part
    # of a citation and must survive (the bare-URL strip must not corrupt it).
    src = "Body https://bare.example.com more. Source: [nasa.gov](https://nasa.gov/r)."
    out = _sanitize_recap_body(src)
    assert "https://bare.example.com" not in out
    assert "[nasa.gov](https://nasa.gov/r)" in out


def test_drops_read_more_sources_line():
    src = "Real story body here.\nRead more (sources): https://a.com, https://b.com"
    out = _sanitize_recap_body(src)
    assert "Read more" not in out
    assert "https://" not in out
    assert "Real story body here." in out


def test_empty_input_is_safe():
    assert _sanitize_recap_body("") == ""
    assert _sanitize_recap_body(None) is None
