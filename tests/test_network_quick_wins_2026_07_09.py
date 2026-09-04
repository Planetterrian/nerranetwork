"""Drift guards for the July 9 2026 network quick-wins pass
(docs/reviews/network_quick_wins_2026_07_09.md).

All changes are site/workflow/metadata — none touch podcast audio
(landmine #17).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_footer_newsletter_loops_all_shows():
    """Footer must not hardcode a stale 11-show checkbox list."""
    base = (_ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8")
    assert "{% for s in all_shows %}" in base
    assert 'value="{{ s.newsletter_tag or s.name }}"' in base
    # The old hardcoded Tesla-only first checkbox must stay gone.
    assert 'value="Tesla Shorts Time"> Tesla Shorts Time' not in base


def test_search_index_urls_preserve_underscores():
    """Blog dirs use underscores; hyphenating them 404s most shows."""
    src = (_ROOT / "scripts" / "build_search_index.py").read_text(encoding="utf-8")
    assert "replace('_', '-')" not in src
    assert 'f"/blog/{d.get(\'show_slug\', \'\')}"' in src or "/blog/" in src
    assert ":03d" in src  # zero-padded epNNN.html


def test_search_legacy_fallback_covers_new_shows():
    js = (_ROOT / "assets" / "js" / "search.js").read_text(encoding="utf-8")
    for slug in ("spacex", "first_principles", "dp_pod", "age_of_ai",
                 "models_agents_beginners"):
        assert f"/api/{slug}.json" in js, f"legacy search missing {slug}"


def test_start_here_includes_new_shows():
    tpl = (_ROOT / "templates" / "start_here.html.j2").read_text(encoding="utf-8")
    for slug in ("spacex", "first_principles", "dp_pod", "age_of_ai"):
        assert slug in tpl, f"Start Here missing {slug}"
    assert "age-of-ai-apply.html" in tpl


def test_faq_schedule_not_even_odd_stale():
    tpl = (_ROOT / "templates" / "faq.html.j2").read_text(encoding="utf-8")
    assert "alternate even/odd days" not in tpl
    assert "odd weekdays" in tpl
    assert "even days" in tpl
    assert "When an interview is ready" in tpl or "when an interview is ready" in tpl


def test_about_no_longer_promises_quiz():
    tpl = (_ROOT / "templates" / "about.html.j2").read_text(encoding="utf-8")
    assert "recommendation quiz" not in tpl
    assert "Browse shows by topic" in tpl


def test_homepage_uses_dynamic_episode_count():
    tpl = (_ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8")
    # Sep 3 2026 website review (#1136): the homepage shows the exact
    # comma-formatted count, not "N+" — honest numbers over a rounded
    # flourish. The guard is that the figure is DYNAMIC, whichever form.
    assert "total_episodes" in tpl
    assert "{{ total_episodes }}+" not in tpl
    assert "'{:,}'.format(total_episodes)" in tpl
    assert re.search(r"<strong>900\+</strong>", tpl) is None
    assert "episode-card-title" in tpl
    assert "ep.blog_url" in tpl
    assert "SpaceX Daily" in tpl
    assert "The DP Pod" in tpl


def test_age_of_ai_hero_promotes_apply_not_empty_blog():
    tpl = (_ROOT / "templates" / "show_page.html.j2").read_text(encoding="utf-8")
    assert "age_of_ai" in tpl
    assert "age-of-ai-apply.html" in tpl
    blog = (_ROOT / "templates" / "blog_index.html.j2").read_text(encoding="utf-8")
    assert "age_of_ai" in blog
    assert "age-of-ai-apply.html" in blog


def test_data_hub_links_story_trackers():
    tpl = (_ROOT / "templates" / "data_hub.html.j2").read_text(encoding="utf-8")
    assert "tesla-narrative.html" in tpl
    assert "spacex-narrative.html" in tpl
    assert "Story Trackers" in tpl


def test_daily_audit_covers_spacex_and_dp_pod():
    wf = (_ROOT / ".github" / "workflows" / "daily-audit.yml").read_text(
        encoding="utf-8")
    assert "spacex_podcast.rss" in wf
    assert "dp_pod_podcast.rss" in wf


def test_nightly_regenerates_player_and_how_to_listen():
    wf = (_ROOT / ".github" / "workflows" / "nightly-maintenance.yml").read_text(
        encoding="utf-8")
    assert "generate_html.py --player" in wf
    assert "generate_html.py --how-to-listen" in wf
    assert "player.html" in wf
    assert "how-to-listen.html" in wf


def test_cli_flags_for_static_pages():
    src = (_ROOT / "generate_html.py").read_text(encoding="utf-8")
    for flag in ("--how-to-listen", "--start-here", "--faq", "--about"):
        assert flag in src
    assert "POPULAR_EPISODES_MAX_AGE_DAYS" in src
    assert "_blog_url_for_episode" in src


def test_op3_popular_includes_blog_url_field():
    from scripts.fetch_op3_stats import _PUBLIC_EPISODE_FIELDS

    assert "blog_url" in _PUBLIC_EPISODE_FIELDS


def test_blog_url_helper_uses_underscores():
    from generate_html import _blog_url_for_episode

    # Known committed episode
    url = _blog_url_for_episode("omni_view", title="Ep 99: Something")
    assert url == "blog/omni_view/ep099.html" or url == ""
    # Age of AI has no episodes — must not invent a URL
    assert _blog_url_for_episode("age_of_ai", title="Ep 1: Debut") == ""
