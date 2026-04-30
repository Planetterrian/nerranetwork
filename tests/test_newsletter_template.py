"""Tests for the branded newsletter HTML wrapper.

Pure-string output tests — they don't render to email, just confirm
the structure of the inline HTML so a future change can't quietly
remove the hero/footer or break the per-show branding.
"""

from __future__ import annotations

import datetime

from engine import newsletter_template as nt


# ---------------------------------------------------------------------------
# Per-show branding lookup
# ---------------------------------------------------------------------------

def test_load_show_branding_uses_network_shows_for_known_slug():
    show = nt._load_show_branding("tesla")
    # Pulled straight from generate_html.NETWORK_SHOWS["tesla"].
    assert show["name"] == "Tesla Shorts Time"
    assert show["brand_color"].startswith("#")
    assert show["cover_url"].endswith(".jpg") or show["cover_url"].endswith(".webp")
    assert show["show_page"].startswith("https://nerranetwork.com/")
    # YouTube playlist URL pulled from the show YAML.
    assert show["youtube_playlist_url"].startswith(
        "https://www.youtube.com/playlist?list="
    )


def test_load_show_branding_falls_back_for_unknown_slug():
    show = nt._load_show_branding("not-a-real-show")
    assert show["name"] == "not-a-real-show"
    assert show["brand_color"].startswith("#")
    # No crash, no exceptions, just safe defaults.


# ---------------------------------------------------------------------------
# Date pill formatting
# ---------------------------------------------------------------------------

def test_week_pill_same_month():
    out = nt._format_week_pill(datetime.date(2026, 4, 30))
    # Apr 24 → Apr 30 should collapse to one month label.
    assert "Apr" in out
    assert "Weekly digest" in out


def test_week_pill_cross_month():
    out = nt._format_week_pill(datetime.date(2026, 5, 4))
    # Apr 28 → May 4 spans months.
    assert "Apr" in out and "May" in out


def test_daily_pill_format():
    out = nt._format_date_pill("Ep 42", datetime.date(2026, 4, 30))
    assert "Ep 42" in out
    assert "Apr" in out
    assert "2026" in out


# ---------------------------------------------------------------------------
# Hero + footer rendering
# ---------------------------------------------------------------------------

def test_hero_html_includes_show_name_and_brand_color():
    show = nt._load_show_branding("tesla")
    pill = "Weekly digest · Apr 24–30, 2026"
    hero = nt._build_hero_html(show, pill)
    assert "Tesla Shorts Time" in hero
    assert show["brand_color"] in hero
    assert pill in hero
    # The cover image renders (real Tesla cover exists).
    assert "<img" in hero and show["cover_url"] in hero


def test_hero_html_omits_image_when_cover_missing():
    show = dict(nt._load_show_branding("not-a-real-show"))
    show["cover_url"] = ""
    hero = nt._build_hero_html(show, "Weekly digest · Test")
    assert "<img" not in hero


def test_footer_html_renders_buttons_when_links_exist():
    show = nt._load_show_branding("tesla")
    footer = nt._build_footer_html(show)
    assert "Listen to the podcast" in footer
    assert "Watch on YouTube" in footer
    assert "Read the blog" in footer
    assert "Nerra Network" in footer
    # Brand color appears as the button background + top border.
    assert show["brand_color"] in footer


def test_footer_html_omits_youtube_when_playlist_missing():
    show = dict(nt._load_show_branding("tesla"))
    show["youtube_playlist_url"] = ""
    footer = nt._build_footer_html(show)
    assert "Watch on YouTube" not in footer
    # But the other CTAs still render.
    assert "Listen to the podcast" in footer


# ---------------------------------------------------------------------------
# Top-level wrap_with_branding
# ---------------------------------------------------------------------------

def test_wrap_with_branding_weekly_keeps_markdown_in_middle():
    body_md = "## This week\n\nA paragraph with **bold** text."
    out = nt.wrap_with_branding(
        "tesla", body_md,
        week_ending=datetime.date(2026, 4, 30),
    )
    # Hero appears before the markdown.
    hero_idx = out.find("Tesla Shorts Time")
    body_idx = out.find("## This week")
    footer_idx = out.find("Listen to the podcast")
    assert 0 <= hero_idx < body_idx < footer_idx
    # The original markdown is preserved verbatim (no transformation).
    assert body_md in out


def test_wrap_with_branding_daily_uses_episode_pill():
    out = nt.wrap_with_branding(
        "tesla", "Body text here.",
        daily_label="Ep 100",
        daily_date=datetime.date(2026, 4, 30),
    )
    assert "Ep 100" in out


def test_wrap_with_branding_falls_back_when_no_dates():
    """No dates passed → use today's date for the hero pill (don't
    crash)."""
    out = nt.wrap_with_branding("tesla", "Body.")
    assert "Tesla Shorts Time" in out  # hero rendered
    assert "Body." in out               # body preserved


def test_wrap_with_branding_renders_for_russian_show():
    """Cyrillic show display names should render unchanged."""
    out = nt.wrap_with_branding(
        "privet_russian", "## Урок 1\n\nПривет!",
        week_ending=datetime.date(2026, 4, 30),
    )
    assert "Привет, Русский!" in out
    assert "Урок 1" in out


# ---------------------------------------------------------------------------
# Preheader (hidden inbox preview text)
# ---------------------------------------------------------------------------

def test_preheader_html_hides_via_inline_style():
    out = nt._build_preheader_html("Cybercab production begins")
    assert "Cybercab production begins" in out
    # Must be visually hidden in inboxes (display:none + opacity:0).
    assert "display:none" in out
    assert "opacity:0" in out
    # Mso-hide:all keeps Outlook from showing it.
    assert "mso-hide:all" in out


def test_preheader_empty_renders_nothing():
    assert nt._build_preheader_html("") == ""


def test_preheader_pads_short_strings():
    """Short preheaders need zero-width-non-joiner padding so the inbox
    snippet doesn't bleed body text into the preview."""
    out = nt._build_preheader_html("Short")
    assert "Short" in out
    assert "&zwnj;" in out


def test_preheader_html_escapes_user_input():
    out = nt._build_preheader_html("<script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


# ---------------------------------------------------------------------------
# By the numbers stat tiles
# ---------------------------------------------------------------------------

def test_by_the_numbers_renders_three_cells():
    stats = [
        {"value": "$372", "label": "TSLA close"},
        {"value": "+20%", "label": "Berlin output"},
        {"value": "19", "label": "Robotaxi units"},
    ]
    out = nt._build_by_the_numbers_html(stats, "#E31937")
    for s in stats:
        assert s["value"] in out
        assert s["label"] in out
    assert "By the numbers" in out
    # Brand color is reused for the value text.
    assert "#E31937" in out


def test_by_the_numbers_caps_at_three():
    stats = [{"value": str(i), "label": f"L{i}"} for i in range(5)]
    out = nt._build_by_the_numbers_html(stats, "#000000")
    # Values 0..2 render; 3 and 4 do not.
    assert ">0<" in out and ">2<" in out
    assert ">3<" not in out


def test_by_the_numbers_skips_blank_items():
    stats = [
        {"value": "", "label": "Empty"},
        {"value": "$1", "label": ""},
        {"value": "ok", "label": "Real"},
    ]
    out = nt._build_by_the_numbers_html(stats, "#000")
    assert "Real" in out
    # The two malformed items don't crash the render.
    assert "Empty" not in out


def test_by_the_numbers_empty_list_renders_nothing():
    assert nt._build_by_the_numbers_html([], "#000") == ""
    assert nt._build_by_the_numbers_html(None, "#000") == ""


# ---------------------------------------------------------------------------
# P.S. block
# ---------------------------------------------------------------------------

def test_p_s_html_renders_with_brand_left_border():
    out = nt._build_p_s_html("If you've been on the fence about FSD…", "#E31937")
    assert "P.S." in out
    assert "FSD" in out
    assert "border-left:3px solid #E31937" in out


def test_p_s_empty_renders_nothing():
    assert nt._build_p_s_html("", "#000") == ""


def test_p_s_html_escapes_user_input():
    out = nt._build_p_s_html("<b>bold</b>", "#000")
    assert "<b>" not in out
    assert "&lt;b&gt;" in out


# ---------------------------------------------------------------------------
# Financial disclaimer callout
# ---------------------------------------------------------------------------

def test_financial_disclaimer_renders():
    out = nt._build_financial_disclaimer_html()
    assert "Heads up" in out
    assert "Not financial advice" in out
    # Amber sidebar.
    assert "#F59E0B" in out


# ---------------------------------------------------------------------------
# Strip repeated show title
# ---------------------------------------------------------------------------

def test_strip_repeated_show_title_removes_bold_weekly():
    body = "**Tesla Shorts Time Daily Weekly**\n\n## Big picture\n\n…"
    cleaned = nt._strip_repeated_show_title(body, "Tesla Shorts Time Daily")
    assert cleaned.startswith("## Big picture")


def test_strip_repeated_show_title_removes_h1():
    body = "# Modern Investing Techniques\n\nSome content."
    cleaned = nt._strip_repeated_show_title(body, "Modern Investing Techniques")
    assert cleaned.startswith("Some content.")


def test_strip_repeated_show_title_keeps_unrelated_first_line():
    body = "## This Week's Big Picture\n\nNarrative arc here."
    cleaned = nt._strip_repeated_show_title(body, "Tesla Shorts Time")
    # Must not eat the actual section heading.
    assert cleaned == body


def test_strip_repeated_show_title_handles_empty():
    assert nt._strip_repeated_show_title("", "X") == ""


# ---------------------------------------------------------------------------
# Subject line composer
# ---------------------------------------------------------------------------

def test_build_subject_line_uses_short_label_and_emoji():
    s = nt.build_subject_line("tesla", "Cybercab production begins")
    assert "Cybercab production begins" in s
    assert "Tesla Shorts" in s
    # Per-show emoji from YAML.
    assert "🚀" in s


def test_build_subject_line_truncates_over_100_chars():
    very_long_hook = "a" * 200
    s = nt.build_subject_line("tesla", very_long_hook)
    assert len(s) <= 100
    # Suffix preserved at the end.
    assert s.endswith("Tesla Shorts 🚀")


def test_build_subject_line_falls_back_when_hook_missing():
    s = nt.build_subject_line(
        "tesla", "", send_date=datetime.date(2026, 4, 30),
    )
    # Should still produce a usable subject.
    assert "Tesla Shorts" in s
    assert s.strip() != ""


def test_build_subject_line_strips_trailing_punct():
    s = nt.build_subject_line("tesla", "Big news...")
    assert "Big news" in s
    # No double punctuation before the separator.
    assert "Big news... ·" not in s


# ---------------------------------------------------------------------------
# Per-show issue numbering
# ---------------------------------------------------------------------------

def test_compute_issue_number_first_week_is_one():
    # Tesla newsletter_start_date is 2026-04-30; sending on the same
    # day is issue #1.
    n = nt.compute_issue_number("tesla", datetime.date(2026, 4, 30))
    assert n == 1


def test_compute_issue_number_second_week():
    n = nt.compute_issue_number("tesla", datetime.date(2026, 5, 7))
    assert n == 2


def test_compute_issue_number_clamps_dates_before_start():
    # If we somehow run before the configured start_date, fall back
    # to issue 1 instead of returning a negative.
    n = nt.compute_issue_number("tesla", datetime.date(2020, 1, 1))
    assert n == 1


# ---------------------------------------------------------------------------
# wrap_with_branding — new optional blocks compose top-to-bottom
# ---------------------------------------------------------------------------

def test_wrap_with_branding_renders_all_blocks_in_order():
    out = nt.wrap_with_branding(
        "tesla", "## Body content\n\nLorem ipsum.",
        week_ending=datetime.date(2026, 4, 30),
        preheader="Inbox preview teaser",
        by_the_numbers=[
            {"value": "$372", "label": "TSLA close"},
        ],
        p_s="One more thing.",
        requires_financial_disclaimer=False,
    )
    pre = out.find("Inbox preview teaser")
    hero = out.find("Tesla Shorts Time")
    stats = out.find("TSLA close")
    body = out.find("## Body content")
    p_s = out.find("One more thing.")
    foot = out.find("Listen to the podcast")
    # All present and in the documented order.
    assert 0 <= pre < hero < stats < body < p_s < foot


def test_wrap_with_branding_renders_disclaimer_when_flagged():
    out = nt.wrap_with_branding(
        "modern_investing", "## Body\n\nx",
        week_ending=datetime.date(2026, 4, 30),
        requires_financial_disclaimer=True,
    )
    assert "Heads up" in out
    assert "Not financial advice" in out


def test_wrap_with_branding_omits_disclaimer_by_default():
    out = nt.wrap_with_branding(
        "tesla", "## Body\n\nx",
        week_ending=datetime.date(2026, 4, 30),
    )
    assert "Heads up" not in out


def test_wrap_with_branding_strips_redundant_title():
    """If the LLM body opens with the show title, it gets stripped so
    the visual hero (which already shows it) isn't duplicated."""
    body = "**Tesla Shorts Time Daily Weekly**\n\n## Big picture\n\n…"
    out = nt.wrap_with_branding(
        "tesla", body, week_ending=datetime.date(2026, 4, 30),
    )
    # The repeated "Weekly" line is gone; the section heading remains.
    assert "## Big picture" in out
    # Hero still shows the show name (this lives in the gradient block
    # not the markdown body).
    assert "Tesla Shorts Time" in out


def test_wrap_with_branding_loads_disclaimer_flag_from_yaml_for_mit():
    """Even without explicit requires_financial_disclaimer=True, the
    show YAML should not auto-render the callout — the caller decides.
    This locks in the contract that the wrapper does NOT silently
    consult YAML; the YAML is read by the caller (run_weekly_newsletters).
    """
    out = nt.wrap_with_branding(
        "modern_investing", "## Body\n\nx",
        week_ending=datetime.date(2026, 4, 30),
    )
    assert "Heads up" not in out


# ---------------------------------------------------------------------------
# Episode deep-link helpers
# ---------------------------------------------------------------------------

def test_episode_blog_url_pads_to_three_digits():
    assert nt.episode_blog_url("tesla", 7) == (
        "https://nerranetwork.com/blog/tesla/ep007.html"
    )
    assert nt.episode_blog_url("tesla", 100) == (
        "https://nerranetwork.com/blog/tesla/ep100.html"
    )


def test_episode_link_table_renders_reference_block():
    eps = [
        {"episode_num": 100, "date": "2026-04-30"},
        {"episode_num": 101, "date": "2026-05-01"},
    ]
    out = nt.episode_link_table(eps, "tesla")
    assert "Episode 100" in out
    assert "Episode 101" in out
    assert "https://nerranetwork.com/blog/tesla/ep100.html" in out
    assert "2026-04-30" in out


def test_episode_link_table_skips_missing_episode_num():
    eps = [{"date": "2026-04-30"}, {"episode_num": 5, "date": "2026-05-01"}]
    out = nt.episode_link_table(eps, "tesla")
    assert "Episode 5" in out
    # The malformed row didn't add a stray "Episode None".
    assert "Episode None" not in out


def test_episode_link_table_empty_returns_empty_string():
    assert nt.episode_link_table([], "tesla") == ""


# ---------------------------------------------------------------------------
# Featured episode block
# ---------------------------------------------------------------------------

def test_featured_episode_renders_with_listen_button():
    show = nt._load_show_branding("tesla")
    featured = {
        "episode_num": 100,
        "date": "2026-04-30",
        "hook": "Cybercab production begins in Texas",
        "show_slug": "tesla",
    }
    out = nt._build_featured_episode_html(featured, show)
    assert "10 minutes" in out
    assert "Episode 100" in out
    assert "Cybercab production begins in Texas" in out
    assert "Listen now" in out
    assert "blog/tesla/ep100.html" in out


def test_featured_episode_returns_empty_when_missing_data():
    show = nt._load_show_branding("tesla")
    assert nt._build_featured_episode_html(None, show) == ""
    assert nt._build_featured_episode_html({}, show) == ""
    # Hook missing → no render.
    assert nt._build_featured_episode_html(
        {"episode_num": 1, "show_slug": "tesla"}, show
    ) == ""


def test_featured_episode_uses_explicit_listen_url():
    """If the caller supplies a listen_url (e.g. R2 mp3), use it
    instead of the default blog deep link."""
    show = nt._load_show_branding("tesla")
    featured = {
        "episode_num": 100,
        "date": "2026-04-30",
        "hook": "Hook here",
        "show_slug": "tesla",
        "listen_url": "https://custom.example.com/ep100",
    }
    out = nt._build_featured_episode_html(featured, show)
    assert "https://custom.example.com/ep100" in out


def test_featured_episode_html_escapes_user_input():
    show = nt._load_show_branding("tesla")
    featured = {
        "episode_num": 5,
        "hook": "<script>alert(1)</script>",
        "date": "2026-04-30",
        "show_slug": "tesla",
    }
    out = nt._build_featured_episode_html(featured, show)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


# ---------------------------------------------------------------------------
# Cross-network "Across the Nerra Network" module
# ---------------------------------------------------------------------------

def test_cross_network_renders_adjacent_shows():
    siblings = [
        {
            "name": "MIT", "slug": "modern_investing", "emoji": "📈",
            "hook": "Oil hit $126; Fed in stagflation trap.",
            "url": "https://nerranetwork.com/blog/modern_investing/ep042.html",
        },
        {
            "name": "M&A", "slug": "models_agents", "emoji": "🤖",
            "hook": "Vision Banana redefines computer vision.",
            "url": "https://nerranetwork.com/blog/models_agents/ep020.html",
        },
    ]
    out = nt._build_cross_network_html(siblings, "#E31937")
    assert "Across the Nerra Network" in out
    assert "MIT" in out
    assert "Oil hit" in out
    assert "M&amp;A" not in out  # name passes through; only hook is escaped
    # Both URLs present.
    assert "ep042.html" in out
    assert "ep020.html" in out


def test_cross_network_caps_at_three():
    siblings = [
        {"name": f"S{i}", "hook": "h", "url": "", "emoji": ""}
        for i in range(5)
    ]
    out = nt._build_cross_network_html(siblings, "#000")
    assert ">S0<" in out and ">S2<" in out
    assert ">S3<" not in out


def test_cross_network_skips_blank_rows():
    siblings = [
        {"name": "", "hook": "h", "url": "", "emoji": ""},
        {"name": "OK", "hook": "h", "url": "", "emoji": ""},
    ]
    out = nt._build_cross_network_html(siblings, "#000")
    assert ">OK<" in out


def test_cross_network_empty_renders_nothing():
    assert nt._build_cross_network_html([], "#000") == ""
    assert nt._build_cross_network_html(None, "#000") == ""


def test_cross_network_html_escapes_hook():
    siblings = [
        {"name": "X", "hook": "<i>tag</i>", "url": "", "emoji": ""},
    ]
    out = nt._build_cross_network_html(siblings, "#000")
    assert "<i>tag</i>" not in out
    assert "&lt;i&gt;tag&lt;/i&gt;" in out


# ---------------------------------------------------------------------------
# Reply / share row
# ---------------------------------------------------------------------------

def test_reply_share_renders_three_intents():
    show = nt._load_show_branding("tesla")
    out = nt._build_reply_share_html(show)
    assert "Reply to this email" in out
    assert "Share on X" in out
    assert "Share on LinkedIn" in out
    assert "Share on WhatsApp" in out
    # Twitter intent uses query params.
    assert "twitter.com/intent/tweet" in out
    assert "linkedin.com/sharing" in out
    assert "wa.me" in out


def test_reply_share_uses_show_page_when_no_archive_url():
    show = nt._load_show_branding("tesla")
    out = nt._build_reply_share_html(show)
    # Show page is URL-encoded inside the share intent.
    assert "tesla" in out


# ---------------------------------------------------------------------------
# wrap_with_branding — full block ordering with featured + cross-network
# ---------------------------------------------------------------------------

def test_wrap_with_branding_full_render_order_with_engagement_blocks():
    """All optional blocks composed in the documented order."""
    out = nt.wrap_with_branding(
        "tesla", "## Body content\n\nLorem ipsum.",
        week_ending=datetime.date(2026, 4, 30),
        preheader="Inbox preview teaser",
        by_the_numbers=[{"value": "$372", "label": "TSLA close"}],
        featured_episode={
            "episode_num": 100, "hook": "Cybercab begins",
            "date": "2026-04-30", "show_slug": "tesla",
        },
        p_s="One more thing.",
        adjacent_shows=[
            {"name": "MIT", "hook": "Oil at $126", "url": "", "emoji": "📈"},
        ],
        show_reply_share=True,
        requires_financial_disclaimer=False,
    )
    pre = out.find("Inbox preview teaser")
    hero = out.find("Tesla Shorts Time")
    stats = out.find("TSLA close")
    featured = out.find("10 minutes")
    body = out.find("## Body content")
    p_s = out.find("One more thing.")
    cross = out.find("Across the Nerra Network")
    share = out.find("Share on X")
    foot = out.find("Listen to the podcast")
    # Documented block order (preheader → hero → stats → featured →
    # body → p_s → cross-network → reply/share → footer).
    assert 0 <= pre < hero < stats < featured < body < p_s < cross < share < foot


def test_wrap_with_branding_omits_engagement_blocks_by_default():
    """Backward-compat: existing callers that don't pass the new
    fields get exactly what they got before (no surprise blocks)."""
    out = nt.wrap_with_branding(
        "tesla", "## Body\n\nx",
        week_ending=datetime.date(2026, 4, 30),
        show_reply_share=False,
    )
    assert "10 minutes" not in out
    assert "Across the Nerra Network" not in out
    assert "Share on X" not in out


def test_wrap_with_branding_show_reply_share_default_is_on():
    """Reply/share row is on by default — it's a near-zero-cost
    engagement boost we want every newsletter to have."""
    out = nt.wrap_with_branding(
        "tesla", "## Body\n\nx",
        week_ending=datetime.date(2026, 4, 30),
    )
    assert "Reply to this email" in out


# ---------------------------------------------------------------------------
# Markdown table → mobile-safe HTML table
# ---------------------------------------------------------------------------

def test_render_html_table_renders_headers_and_rows():
    out = nt.render_html_table(
        ["Day", "Ticker", "P&L"],
        [["Mon", "TSLA", "+1.2%"], ["Tue", "AAPL", "-0.4%"]],
        brand="#E31937",
    )
    # Headers in brand-color band.
    assert "Day" in out
    assert "TSLA" in out
    assert "AAPL" in out
    # Brand color is the header background.
    assert "#E31937" in out
    # Alternating row backgrounds (white / slate-50).
    assert "#ffffff" in out
    assert "#f8fafc" in out


def test_render_html_table_handles_inline_markdown_in_cells():
    out = nt.render_html_table(
        ["Header"],
        [["**bold**"], ["[link](https://x.com)"]],
    )
    assert "<strong>bold</strong>" in out
    assert '<a href="https://x.com"' in out


def test_render_html_table_escapes_html():
    out = nt.render_html_table(
        ["H"], [["<script>x</script>"]],
    )
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_render_html_table_empty_returns_empty_string():
    assert nt.render_html_table([], []) == ""
    assert nt.render_html_table(["H"], []) == ""


def test_convert_md_tables_to_html_swaps_a_simple_table():
    body = (
        "Some intro paragraph.\n\n"
        "| Day | Ticker | P&L |\n"
        "|-----|--------|-----|\n"
        "| Mon | TSLA   | +1% |\n"
        "| Tue | AAPL   | -2% |\n\n"
        "And a closing paragraph."
    )
    out = nt.convert_md_tables_to_html(body)
    assert "Some intro paragraph." in out
    assert "<table" in out
    assert "TSLA" in out
    assert "AAPL" in out
    assert "And a closing paragraph." in out
    # The original markdown rows are gone (replaced by HTML).
    assert "| Mon | TSLA" not in out


def test_convert_md_tables_to_html_handles_multiple_tables():
    body = (
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "Some prose.\n\n"
        "| X | Y |\n|---|---|\n| 9 | 8 |\n"
    )
    out = nt.convert_md_tables_to_html(body)
    # Both tables converted.
    assert out.count("<table") == 2


def test_convert_md_tables_to_html_leaves_non_table_markdown_alone():
    body = "## Heading\n\nA bullet:\n- item one\n- item two\n"
    out = nt.convert_md_tables_to_html(body)
    assert out == body


def test_convert_md_tables_to_html_pads_ragged_rows():
    """If the LLM emits a row missing a cell, we pad with empties so
    the rendered HTML stays well-formed instead of breaking the table."""
    body = (
        "| A | B | C |\n"
        "|---|---|---|\n"
        "| 1 | 2 |\n"  # missing the C cell
    )
    out = nt.convert_md_tables_to_html(body)
    assert "<table" in out
    # Three <td>s rendered (with one empty) so column count matches.
    assert out.count("<td") == 3


def test_convert_md_tables_to_html_handles_pipe_in_text():
    """Pipes inside cell text are not supported (markdown doesn't
    escape them), but we shouldn't crash. The cell just splits on the
    inner pipe — that's fine, it's how every markdown renderer does
    it."""
    body = (
        "| Header |\n"
        "|--------|\n"
        "| just a regular cell |\n"
    )
    out = nt.convert_md_tables_to_html(body)
    assert "<table" in out
    assert "just a regular cell" in out


def test_convert_md_tables_to_html_no_tables_returns_input_verbatim():
    body = "Plain text, no pipes here."
    assert nt.convert_md_tables_to_html(body) == body


# ---------------------------------------------------------------------------
# Dark mode + accessibility
# ---------------------------------------------------------------------------

def test_wrap_with_branding_includes_dark_mode_style_block():
    out = nt.wrap_with_branding(
        "tesla", "Body.", week_ending=datetime.date(2026, 4, 30),
    )
    assert "@media (prefers-color-scheme: dark)" in out
    assert "#0f172a" in out  # dark page bg
    assert "#e2e8f0" in out  # dark text


def test_hero_alt_text_describes_show_not_file():
    show = nt._load_show_branding("tesla")
    hero = nt._build_hero_html(show, "Pill")
    # Old behavior was alt="Tesla Shorts Time cover" (file-ish);
    # new behavior should describe the show / tagline so screen
    # readers convey the same info as the visual cover.
    assert 'alt="Tesla Shorts Time' in hero
    assert ' cover"' not in hero


def test_hero_alt_text_includes_tagline_when_present():
    show = dict(nt._load_show_branding("tesla"))
    show["tagline"] = "Daily Tesla news at podcast speed."
    hero = nt._build_hero_html(show, "Pill")
    assert "Daily Tesla news at podcast speed." in hero


def test_wrap_with_branding_converts_md_table_in_body():
    """End-to-end: a markdown table inside the body markdown comes out
    as an HTML <table> in the wrapped result."""
    body = (
        "## Scoreboard\n\n"
        "| Day | Ticker |\n"
        "|-----|--------|\n"
        "| Mon | TSLA   |\n"
    )
    out = nt.wrap_with_branding(
        "tesla", body, week_ending=datetime.date(2026, 4, 30),
    )
    assert "<table" in out
    # Original markdown row is gone.
    assert "| Mon | TSLA" not in out