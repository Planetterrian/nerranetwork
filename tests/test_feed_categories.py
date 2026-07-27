"""Drift guards for Apple category emission.

Apple allows a primary and a secondary category, each with a subcategory
where the taxonomy has one. Two facts this pins, both of which were
previously got wrong in this repo:

* Technology has NO subcategories. The five Technology shows were not
  misconfigured — a comment in engine/config.py said they were, and a May
  2026 audit was logged on that basis. What they lacked was a secondary
  category, a different field entirely.
* A subcategory is only valid under its own parent, so "Tech News" can
  only appear under "News" — never as a sub of Technology.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from engine.feed_categories import category_payload  # noqa: E402

# Apple's taxonomy, July 2026. Only the parents relevant to this network.
SUBCATEGORIES = {
    "Technology": set(),
    "News": {"Business News", "Daily News", "Entertainment News",
             "News Commentary", "Politics", "Sports News", "Tech News"},
    "Science": {"Astronomy", "Chemistry", "Earth Sciences", "Life Sciences",
                "Mathematics", "Natural Sciences", "Nature", "Physics",
                "Social Sciences"},
    "Business": {"Careers", "Entrepreneurship", "Investing", "Management",
                 "Marketing", "Non-Profit"},
    "Education": {"Courses", "How To", "Language Learning", "Self-Improvement"},
    "Health & Fitness": {"Alternative Health", "Fitness", "Medicine",
                         "Mental Health", "Nutrition", "Sexuality"},
    "Society & Culture": {"Documentary", "Personal Journals", "Philosophy",
                          "Places & Travel", "Relationships"},
}


class TestPayloadShape:
    def test_primary_only_stays_a_bare_string(self):
        """Preserves the historic shape so rebuilding an existing feed is
        byte-identical and churn suppression keeps it out of the commit."""
        assert category_payload("Technology") == "Technology"

    def test_primary_with_sub_is_a_dict(self):
        assert category_payload("Science", "Astronomy") == {
            "cat": "Science", "sub": "Astronomy"}

    def test_secondary_produces_a_two_entry_list(self):
        assert category_payload("Technology", "", "News", "Tech News") == [
            {"cat": "Technology"}, {"cat": "News", "sub": "Tech News"}]

    def test_duplicate_secondary_is_dropped(self):
        assert category_payload("Technology", "", "Technology", "") == "Technology"

    def test_empty_primary_yields_nothing(self):
        assert category_payload("") is None
        assert category_payload("  ") is None


class TestRealShowConfigs:
    """Every configured pair must be legal in Apple's taxonomy — an invalid
    pair is silently dropped by Apple, so it fails quietly in production."""

    @pytest.mark.parametrize("slug", [
        "tesla", "spacex", "models_agents", "models_agents_beginners",
        "first_principles", "dp_pod", "omni_view", "modern_investing",
        "planetterrian", "env_intel", "fascinating_frontiers",
        "unintended_consequences", "finansy_prosto", "privet_russian",
        "age_of_ai",
    ])
    def test_categories_are_valid_apple_pairs(self, slug):
        from engine.config import load_config

        pub = load_config(ROOT / "shows" / f"{slug}.yaml").publishing
        for cat, sub in (
            (pub.rss_category, pub.rss_subcategory),
            (getattr(pub, "rss_category2", ""), getattr(pub, "rss_subcategory2", "")),
        ):
            if not cat:
                continue
            assert cat in SUBCATEGORIES, f"{slug}: unknown category {cat!r}"
            if sub:
                assert sub in SUBCATEGORIES[cat], (
                    f"{slug}: {sub!r} is not a subcategory of {cat!r}")

    def test_technology_shows_declare_no_subcategory(self):
        """Technology has no children — a sub here would be rejected."""
        from engine.config import load_config

        for slug in ("tesla", "spacex", "models_agents",
                     "models_agents_beginners", "first_principles"):
            pub = load_config(ROOT / "shows" / f"{slug}.yaml").publishing
            if pub.rss_category == "Technology":
                assert not pub.rss_subcategory, (
                    f"{slug}: Technology has no subcategories")

    def test_secondary_never_duplicates_primary(self):
        from engine.config import load_config

        for path in sorted((ROOT / "shows").glob("*.yaml")):
            if path.stem.startswith("_"):
                continue
            try:
                pub = load_config(path).publishing
            except Exception:  # noqa: BLE001 — non-show yaml
                continue
            c2 = getattr(pub, "rss_category2", "")
            if c2:
                assert c2 != pub.rss_category, f"{path.stem}: duplicate category"
