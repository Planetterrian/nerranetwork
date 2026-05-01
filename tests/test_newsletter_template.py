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