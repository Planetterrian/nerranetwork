"""Smoke tests for the Phase 2 gallery rendering pipeline.

These don't exercise the JS — they just verify the template wiring
produces the right HTML (mount-point present when gallery is enabled,
absent when it isn't) and that the gallery_page template renders.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, select_autoescape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = PROJECT_ROOT / "templates"


@pytest.fixture
def env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


@pytest.fixture
def base_context() -> dict:
    return {
        "path_prefix": "",
        "show_slug": "tesla",
        "show_name": "Tesla Shorts Time",
        "section_id": "gallery",
        "section_title": "Episode gallery",
        "section_intro": "AI-generated visuals from recent episodes.",
        "page_size": 24,
        "hide_controls": True,
    }


def test_gallery_section_partial_renders_mount_point(env, base_context):
    template = env.get_template("_gallery_section.html.j2")
    html = template.render(**base_context)
    assert "data-nn-gallery" in html
    assert 'data-show-slug="tesla"' in html
    assert 'data-page-size="24"' in html
    assert 'data-controls="hide"' in html
    assert "assets/js/gallery.js" in html
    assert "site/data/gallery-manifest.json" in html
    assert "Episode gallery" in html


def test_gallery_section_omits_show_slug_when_not_given(env, base_context):
    ctx = dict(base_context)
    ctx.pop("show_slug")
    template = env.get_template("_gallery_section.html.j2")
    html = template.render(**ctx)
    assert "data-nn-gallery" in html
    assert "data-show-slug=" not in html


def test_gallery_section_hides_title_when_blank(env, base_context):
    ctx = dict(base_context)
    ctx["section_title"] = ""
    template = env.get_template("_gallery_section.html.j2")
    html = template.render(**ctx)
    # No <h2> for the section header when title is empty.
    assert "nn-section-title" not in html


def test_show_page_includes_gallery_when_enabled():
    """When ``gallery_enabled`` is True the show_page template must
    emit the gallery mount point and the JS bootstrap."""
    # Build a stub jinja env that overrides base + macros so we don't
    # need to render the entire 958-line show_page template — only the
    # gallery-relevant fragment.
    env = Environment(
        loader=ChoiceLoader([
            DictLoader({
                "fragment.html.j2": (
                    "{% if gallery_enabled %}"
                    '{% include "_gallery_section.html.j2" with context %}'
                    "{% endif %}"
                ),
            }),
            FileSystemLoader(str(TEMPLATES_DIR)),
        ]),
        autoescape=select_autoescape(["html", "xml"]),
    )
    ctx = {
        "gallery_enabled": True,
        "path_prefix": "",
        "show_slug": "models_agents_beginners",
        "section_id": "gallery",
        "section_title": "Episode gallery",
        "section_intro": "",
        "page_size": 24,
        "hide_controls": True,
    }
    html = env.get_template("fragment.html.j2").render(**ctx)
    assert "data-nn-gallery" in html

    ctx["gallery_enabled"] = False
    html = env.get_template("fragment.html.j2").render(**ctx)
    assert "data-nn-gallery" not in html


def test_gallery_page_template_renders():
    """End-to-end render of the gallery page template via the project's
    real Jinja env (which registers custom filters like ``with_utm``)
    — fails loudly if any block reference goes stale."""
    import sys
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from generate_html import _get_jinja_env

    env = _get_jinja_env()
    template = env.get_template("gallery_page.html.j2")
    html = template.render(
        path_prefix="",
        page_title="Gallery — Nerra Network",
        page_description="x",
        meta_description="x",
        meta_keywords="x",
        theme_color="#6B47FF",
        og_image="",
        canonical_url="https://nerranetwork.com/gallery.html",
        show_color="",
        show_color_dark="",
        all_shows=[],
        section_id="gallery",
        section_title="",
        section_intro="",
        show_slug="",
        page_size=60,
        hide_controls=False,
    )
    assert "<h1>Gallery</h1>" in html
    assert "data-nn-gallery" in html
    assert "gallery.js" in html


def test_gallery_manifest_placeholder_is_valid_json():
    """The committed placeholder manifest must always be parseable —
    if a future edit corrupts it, the JS gallery fetch fails on every
    page load."""
    import json
    manifest_path = PROJECT_ROOT / "site" / "data" / "gallery-manifest.json"
    assert manifest_path.exists(), "placeholder manifest missing"
    data = json.loads(manifest_path.read_text())
    assert data["schema_version"] == 1
    assert isinstance(data["images"], list)
    assert isinstance(data["shows"], list)
    assert "image_count" in data


def test_gallery_enabled_requires_grok_image_provider():
    """A show that uses Pexels for its YouTube slideshow must NOT
    have the gallery section embedded — the gallery uploader is
    wired only into the Grok Imagine path, so a Pexels show would
    render an empty gallery forever."""
    import sys
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from generate_html import (
        _read_show_image_provider, _read_show_youtube,
    )

    tesla_yt = _read_show_youtube("tesla")
    tesla_provider = _read_show_image_provider("tesla")
    tesla_enabled = (
        bool(tesla_yt.get("youtube_enabled"))
        and tesla_provider in ("grok", "hybrid")
    )
    assert tesla_provider == "grok", \
        f"Tesla expected on grok provider, got {tesla_provider!r}"
    assert tesla_enabled, "Tesla should have gallery_enabled=True"

    # June 14 2026 — SpaceX Daily took MAB's YouTube slot (full format on Grok),
    # so SpaceX is now the gallery-enabled show and MAB's gallery auto-hides
    # (YouTube paused). SpaceX keeps Grok imagery so its gallery embed populates.
    spacex_yt = _read_show_youtube("spacex")
    spacex_provider = _read_show_image_provider("spacex")
    spacex_enabled = (
        bool(spacex_yt.get("youtube_enabled"))
        and spacex_provider in ("grok", "hybrid")
    )
    assert spacex_provider == "grok", \
        f"SpaceX expected on grok provider, got {spacex_provider!r}"
    assert spacex_enabled is True, "SpaceX gallery_enabled must be True"

    # MAB's YouTube is paused — its gallery must auto-hide (no uploads → empty
    # embed otherwise). The image_provider stays 'grok' in the YAML so
    # re-enabling MAB later is a one-line flip that restores the gallery.
    mab_yt = _read_show_youtube("models_agents_beginners")
    mab_enabled = (
        bool(mab_yt.get("youtube_enabled"))
        and _read_show_image_provider("models_agents_beginners") in ("grok", "hybrid")
    )
    assert mab_enabled is False, "MAB gallery must auto-hide while YouTube is paused"


def test_read_show_image_provider_defaults_to_pexels_for_unknown_show():
    """An unknown / missing show YAML must default to 'pexels' so the
    gallery section auto-disables rather than breaking the render."""
    import sys
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from generate_html import _read_show_image_provider
    assert _read_show_image_provider("__nonexistent__") == "pexels"


def test_all_grok_youtube_shows_are_gallery_enabled():
    """June 14 2026 (operator request): every YouTube-enabled Grok show must
    embed the per-show gallery section (like Tesla), so its generated imagery
    is browsable on the show page — especially SpaceX Daily + Fascinating
    Frontiers. Guards against a regeneration that drops the section."""
    import sys
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from generate_html import _read_show_image_provider, _read_show_youtube
    for slug in ("tesla", "spacex", "fascinating_frontiers", "modern_investing",
                 "finansy_prosto", "privet_russian"):
        yt = _read_show_youtube(slug)
        provider = _read_show_image_provider(slug)
        gallery_enabled = (
            bool(yt.get("youtube_enabled")) and provider in ("grok", "hybrid")
        )
        assert gallery_enabled, (
            f"{slug} should embed the per-show gallery (youtube_enabled + grok), "
            f"got youtube_enabled={yt.get('youtube_enabled')} provider={provider!r}"
        )


def test_committed_show_pages_have_gallery_mount():
    """The regenerated show pages for the Grok shows carry the gallery mount
    so the section is live on the site now (not only after the next nightly)."""
    pages = {
        "spacex.html": "spacex",
        "fascinating-frontiers.html": "fascinating_frontiers",
        "modern-investing.html": "modern_investing",
        "ru/finansy-prosto.html": "finansy_prosto",
        "ru/privet-russian.html": "privet_russian",
    }
    for rel, slug in pages.items():
        p = PROJECT_ROOT / rel
        if not p.exists():
            continue
        html = p.read_text(encoding="utf-8")
        assert "data-nn-gallery" in html, f"{rel} missing gallery mount"
        assert f'data-show-slug="{slug}"' in html, f"{rel} wrong/absent show slug"
