"""Tests for new-show scaffolding."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engine.first_episode import (
    first_episode_digest_appendix,
    first_episode_podcast_appendix,
)
from engine.show_scaffold import (
    ScaffoldSpec,
    build_show_yaml,
    default_episode_prefix,
    scaffold_show,
    validate_slug,
)

REPO = Path(__file__).resolve().parent.parent


class TestFirstEpisode:
    def test_appendix_empty_after_ep1(self):
        assert first_episode_digest_appendix(2, "Test") == ""
        assert first_episode_podcast_appendix(2, "Test") == ""

    def test_appendix_present_on_ep1(self):
        d = first_episode_digest_appendix(1, "Ocean Weekly")
        assert "FIRST EPISODE" in d
        assert "Ocean Weekly" in d


class TestScaffold:
    def test_validate_slug(self):
        validate_slug("ocean_tech")
        with pytest.raises(ValueError):
            validate_slug("Ocean-Tech")

    def test_default_prefix(self):
        assert default_episode_prefix("ocean_tech") == "OT"

    def test_build_show_yaml(self):
        spec = ScaffoldSpec(
            show_name="Ocean Tech",
            slug="ocean_tech",
            description="Ocean news.",
            audience="marine pros",
            keywords=["ocean", "marine"],
        )
        text = build_show_yaml(spec)
        assert "slug: ocean_tech" in text
        assert "shows/prompts/ocean_tech_digest.txt" in text
        assert "image_queries:" in text

    def test_scaffold_dry_run(self, tmp_path):
        spec = ScaffoldSpec(
            show_name="Test Show",
            slug="test_show_x",
            description="A test show for scaffold.",
            audience="testers",
        )
        lines = scaffold_show(tmp_path, spec, dry_run=True)
        assert any("dry-run" in ln for ln in lines)
        assert not (tmp_path / "shows" / "test_show_x.yaml").exists()

    def test_scaffold_writes_files(self, tmp_path):
        spec = ScaffoldSpec(
            show_name="Scaffold Me",
            slug="scaffold_me",
            description="Scaffold integration test show.",
            audience="developers",
            sources=[{"url": "https://example.com/feed", "label": "Example"}],
        )
        scaffold_show(tmp_path, spec, dry_run=False)
        yaml_path = tmp_path / "shows" / "scaffold_me.yaml"
        assert yaml_path.exists()
        data = yaml.safe_load(yaml_path.read_text())
        assert data["slug"] == "scaffold_me"
        assert (tmp_path / "shows" / "prompts" / "scaffold_me_digest.txt").exists()
        meta = yaml.safe_load((tmp_path / "shows" / "network_meta.yaml").read_text())
        assert "scaffold_me" in meta


def test_generate_registration_patch_contains_key_sections():
    """Medium item: The scaffold now emits a rich registration patch that covers
    cron, health-check, Buttondown tag, and cover art to reduce manual onboarding steps.
    """
    from engine.show_scaffold import ScaffoldSpec, generate_registration_patch

    spec = ScaffoldSpec(
        show_name="Ocean Tech Weekly",
        slug="ocean_tech",
        description="Daily ocean technology news.",
        audience="marine researchers",
        cron="45 10 * * *",
        cron_day_filter="weekday",
    )

    patch = generate_registration_patch(spec)

    assert "REGISTRATION PATCH" in patch
    assert "run-show.yml" in patch
    assert "health-check.yml" in patch
    assert "Buttondown tag" in patch
    assert "ocean-tech.jpg" in patch or "ocean_tech" in patch
    assert "test_medium_podcast.rss" not in patch  # sanity: this is for the test show only
