"""Tests for entity-level deduplication and weekend/low-news detection in engine/utils.py."""



from engine.utils import (
    extract_primary_entity,
    deduplicate_by_entity,
    is_low_news_day,
    adaptive_cutoff_hours,
)


class TestExtractPrimaryEntity:
    def test_simple_entity(self):
        entity = extract_primary_entity("SpaceX Launches Starship from Texas")
        assert "SpaceX" in entity or "Starship" in entity

    def test_mission_designator(self):
        entity = extract_primary_entity("USSF-87 Mission Launches Successfully")
        # Should capture something meaningful
        assert len(entity) > 0

    def test_proper_noun(self):
        entity = extract_primary_entity("Tesla Cybertruck Production Ramps Up")
        assert "Tesla" in entity or "Cybertruck" in entity

    def test_empty_title(self):
        entity = extract_primary_entity("")
        assert entity == ""

    def test_no_capitals(self):
        entity = extract_primary_entity("something about space exploration news")
        assert len(entity) > 0  # Should still return something


class TestDeduplicateByEntity:
    def test_caps_per_entity(self):
        # Use titles where the primary entity is consistent enough to trigger dedup
        articles = [
            {"title": "Crew Dragon Mission Launch Succeeds", "url": "a"},
            {"title": "Crew Dragon Mission Gets Green Light", "url": "b"},
            {"title": "Crew Dragon Mission Delayed by Weather", "url": "c"},
            {"title": "NASA Mars Rover Finds Water", "url": "d"},
        ]
        result = deduplicate_by_entity(articles, max_per_entity=2)
        # Should keep max 2 "Crew Dragon Mission" + 1 NASA
        assert len(result) <= 3
        # NASA article should always survive
        nasa_titles = [a["title"] for a in result if "NASA" in a["title"]]
        assert len(nasa_titles) == 1

    def test_url_dedup(self):
        articles = [
            {"title": "Story A", "url": "https://example.com/1"},
            {"title": "Story B", "url": "https://example.com/1"},  # Same URL
            {"title": "Story C", "url": "https://example.com/2"},
        ]
        result = deduplicate_by_entity(articles, max_per_entity=10)
        assert len(result) == 2

    def test_empty_list(self):
        assert deduplicate_by_entity([]) == []

    def test_all_unique_entities(self):
        articles = [
            {"title": "Tesla Cybertruck Deliveries Start", "url": "a"},
            {"title": "NASA Artemis Mission Update", "url": "b"},
            {"title": "SpaceX Falcon Heavy Launch", "url": "c"},
        ]
        result = deduplicate_by_entity(articles, max_per_entity=2)
        assert len(result) == 3

    def test_articles_without_url(self):
        articles = [
            {"title": "Story Without URL One"},
            {"title": "Story Without URL Two"},
        ]
        result = deduplicate_by_entity(articles, max_per_entity=2)
        assert len(result) == 2


class TestIsLowNewsDay:
    def test_returns_bool(self):
        result = is_low_news_day()
        assert isinstance(result, bool)


class TestAdaptiveCutoffHours:
    def test_enough_articles_returns_base(self):
        articles = [{"title": f"Article {i}"} for i in range(10)]
        assert adaptive_cutoff_hours(articles, base_hours=24) == 24

    def test_few_articles_expands(self):
        articles = [{"title": "Only one"}]
        assert adaptive_cutoff_hours(articles, base_hours=24) == 48

    def test_very_few_articles_expands_to_72(self):
        articles = [{"title": "Only one"}]
        assert adaptive_cutoff_hours(articles, base_hours=48) == 72

    def test_empty_expands(self):
        assert adaptive_cutoff_hours([], base_hours=24) == 48
