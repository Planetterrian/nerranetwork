"""
RSS feed regression tests.

Parses each existing RSS file and captures:
  - Episode counts (must match known values)
  - Channel metadata structure
  - Item field completeness
  - Enclosure URL patterns

This becomes our baseline: after refactoring RSS generation into a shared
engine, these tests verify the output is structurally equivalent.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Constants (must match conftest.py — duplicated here because conftest is
# auto-loaded by pytest but not directly importable as a module).
# ---------------------------------------------------------------------------

RSS_FEEDS = {
    "tesla": PROJECT_ROOT / "podcast.rss",
    "omni": PROJECT_ROOT / "omni_view_podcast.rss",
    "planetterrian": PROJECT_ROOT / "planetterrian_podcast.rss",
    "frontiers": PROJECT_ROOT / "fascinating_frontiers_podcast.rss",
    "env_intel": PROJECT_ROOT / "env_intel_podcast.rss",
    "models_agents": PROJECT_ROOT / "models_agents_podcast.rss",
}

# Minimum episode counts — tests use >= so new episodes don't break CI.
# Update these only when episodes are removed.
EXPECTED_EPISODE_COUNTS = {
    "tesla": 49,
    "omni": 4,
    "frontiers": 22,
    "planetterrian": 13,
    "env_intel": 2,
    "models_agents": 2,
}

# ---------------------------------------------------------------------------
# Namespace helpers (RSS feeds use different namespace prefixes)
# ---------------------------------------------------------------------------

ITUNES_NAMESPACES = [
    "http://www.itunes.com/dtds/podcast-1.0.dtd",
]


def _find_itunes(element, tag):
    """Find an iTunes-namespaced child element, trying all known prefixes."""
    for ns in ITUNES_NAMESPACES:
        found = element.find(f"{{{ns}}}{tag}")
        if found is not None:
            return found
    return None


def _findall_itunes(element, tag):
    """Find all iTunes-namespaced child elements."""
    results = []
    for ns in ITUNES_NAMESPACES:
        results.extend(element.findall(f"{{{ns}}}{tag}"))
    return results


def _parse_rss(rss_path: Path):
    """Parse an RSS file and return (channel_element, list_of_item_elements)."""
    tree = ET.parse(str(rss_path))
    root = tree.getroot()
    channel = root.find("channel")
    items = channel.findall("item")
    return channel, items


# ===================================================================
# TEST: Episode counts match expected values
# ===================================================================

class TestEpisodeCounts:

    @pytest.mark.parametrize("show,min_count", list(EXPECTED_EPISODE_COUNTS.items()))
    def test_episode_count(self, show, min_count):
        """Verify RSS feed has at least the expected number of episodes.

        Uses >= instead of == because new episodes are auto-generated daily
        and committed to main.  A strict == check breaks CI whenever the
        show pipeline runs between conftest updates.
        """
        rss_path = RSS_FEEDS[show]
        assert rss_path.exists(), f"RSS file not found: {rss_path}"
        _, items = _parse_rss(rss_path)
        actual = len(items)
        assert actual >= min_count, (
            f"{show}: expected at least {min_count} episodes, found {actual}"
        )


# ===================================================================
# TEST: Channel metadata structure
# ===================================================================

EXPECTED_CHANNEL_METADATA = {
    "tesla": {
        # Aligned with shows/tesla.yaml:rss_title in PR #326 (Phase 2 RSS
        # metadata polish, May 6 2026). Apple Podcasts shows the channel
        # title verbatim; "Daily" was redundant with the cadence already
        # set by ``itunes_type=episodic``.
        "title": "Tesla Shorts Time",
        "language": "en-us",
        "generator": "python-feedgen",
        "itunes_category": "Technology",
        "itunes_explicit": "no",
    },
    "omni": {
        "title": "Omni View - Balanced News Perspectives",
        "language": "en-us",
        "generator": "python-feedgen",
        "itunes_category": "News",
        "itunes_explicit": "no",
    },
    "planetterrian": {
        "title": "Planetterrian Daily",
        "language": "en-us",
        "generator": "python-feedgen",
        "itunes_category": "Science",
        "itunes_explicit": "no",
    },
    "frontiers": {
        "title": "Fascinating Frontiers",
        "language": "en-us",
        "generator": "python-feedgen",
        "itunes_category": "Science",
        "itunes_explicit": "no",
    },
    "env_intel": {
        "title": "Environmental Intelligence",
        "language": "en-us",
        "generator": "python-feedgen",
        "itunes_category": "Science",
        "itunes_explicit": "no",
    },
    "models_agents": {
        "title": "Models & Agents",
        "language": "en-us",
        "generator": "python-feedgen",
        "itunes_category": "Technology",
        "itunes_explicit": "no",
    },
}


class TestChannelMetadata:

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_channel_title(self, show):
        channel, _ = _parse_rss(RSS_FEEDS[show])
        title = channel.find("title").text
        assert title == EXPECTED_CHANNEL_METADATA[show]["title"]

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_channel_language(self, show):
        channel, _ = _parse_rss(RSS_FEEDS[show])
        lang = channel.find("language").text
        assert lang == EXPECTED_CHANNEL_METADATA[show]["language"]

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_channel_generator(self, show):
        channel, _ = _parse_rss(RSS_FEEDS[show])
        gen = channel.find("generator").text
        assert gen == EXPECTED_CHANNEL_METADATA[show]["generator"]

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_itunes_category(self, show):
        channel, _ = _parse_rss(RSS_FEEDS[show])
        cat = _find_itunes(channel, "category")
        assert cat is not None, f"{show}: missing itunes:category"
        assert cat.get("text") == EXPECTED_CHANNEL_METADATA[show]["itunes_category"]

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_itunes_explicit(self, show):
        channel, _ = _parse_rss(RSS_FEEDS[show])
        explicit = _find_itunes(channel, "explicit")
        assert explicit is not None, f"{show}: missing itunes:explicit"
        assert explicit.text == EXPECTED_CHANNEL_METADATA[show]["itunes_explicit"]

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_has_itunes_image(self, show):
        channel, _ = _parse_rss(RSS_FEEDS[show])
        img = _find_itunes(channel, "image")
        assert img is not None, f"{show}: missing itunes:image"
        href = img.get("href")
        assert href and href.startswith("https://"), f"{show}: bad image href: {href}"

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_has_itunes_owner(self, show):
        channel, _ = _parse_rss(RSS_FEEDS[show])
        owner = _find_itunes(channel, "owner")
        assert owner is not None, f"{show}: missing itunes:owner"
        name = _find_itunes(owner, "name")
        email = _find_itunes(owner, "email")
        assert name is not None and name.text, f"{show}: missing owner name"
        assert email is not None and email.text, f"{show}: missing owner email"

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_has_channel_link(self, show):
        channel, _ = _parse_rss(RSS_FEEDS[show])
        link = channel.find("link")
        assert link is not None and link.text, f"{show}: missing channel <link>"

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_has_description(self, show):
        channel, _ = _parse_rss(RSS_FEEDS[show])
        desc = channel.find("description")
        assert desc is not None and desc.text, f"{show}: missing channel <description>"


# ===================================================================
# TEST: Item / Episode structure
# ===================================================================

BASE_URL = "https://raw.githubusercontent.com/Planetterrian/nerranetwork/main"
R2_BASE_URL = "https://audio.nerranetwork.com"
OP3_PREFIX = "https://op3.dev/e/"

ENCLOSURE_URL_PATTERNS = {
    "tesla": (f"{BASE_URL}/digests/", f"{R2_BASE_URL}/tesla/", f"{R2_BASE_URL}/digests/tesla_shorts_time/", f"{R2_BASE_URL}/digests/"),
    "omni": (f"{BASE_URL}/digests/", f"{R2_BASE_URL}/omni_view/", f"{R2_BASE_URL}/digests/omni_view/", f"{R2_BASE_URL}/digests/"),
    "planetterrian": (f"{BASE_URL}/digests/planetterrian/", f"{R2_BASE_URL}/planetterrian/", f"{R2_BASE_URL}/digests/planetterrian/"),
    "frontiers": (f"{BASE_URL}/digests/fascinating_frontiers/", f"{R2_BASE_URL}/fascinating_frontiers/", f"{R2_BASE_URL}/digests/fascinating_frontiers/"),
    "env_intel": (f"{BASE_URL}/digests/env_intel/", f"{R2_BASE_URL}/env_intel/", f"{R2_BASE_URL}/digests/env_intel/"),
    "models_agents": (f"{BASE_URL}/digests/models_agents/", f"{R2_BASE_URL}/models_agents/", f"{R2_BASE_URL}/digests/models_agents/"),
}


class TestItemStructure:
    """Every episode item must have the required RSS and iTunes fields."""

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_all_items_have_title(self, show):
        _, items = _parse_rss(RSS_FEEDS[show])
        for i, item in enumerate(items):
            title = item.find("title")
            assert title is not None and title.text, (
                f"{show} item {i}: missing <title>"
            )

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_all_items_have_guid(self, show):
        _, items = _parse_rss(RSS_FEEDS[show])
        guids = set()
        for i, item in enumerate(items):
            guid = item.find("guid")
            assert guid is not None and guid.text, (
                f"{show} item {i}: missing <guid>"
            )
            # GUIDs must be unique
            assert guid.text not in guids, (
                f"{show} item {i}: duplicate GUID '{guid.text}'"
            )
            guids.add(guid.text)

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_all_items_have_enclosure(self, show):
        _, items = _parse_rss(RSS_FEEDS[show])
        expected_prefixes = ENCLOSURE_URL_PATTERNS[show]
        for i, item in enumerate(items):
            enc = item.find("enclosure")
            assert enc is not None, f"{show} item {i}: missing <enclosure>"
            url = enc.get("url")
            assert url, f"{show} item {i}: empty enclosure url"
            # Strip OP3 analytics prefix before matching
            check_url = url
            if check_url.startswith(OP3_PREFIX):
                check_url = "https://" + check_url[len(OP3_PREFIX):]
            assert any(check_url.startswith(p) for p in expected_prefixes), (
                f"{show} item {i}: enclosure URL doesn't match expected pattern.\n"
                f"  expected prefixes: {expected_prefixes}\n"
                f"  actual URL: {url}"
            )
            assert enc.get("type") == "audio/mpeg", (
                f"{show} item {i}: enclosure type should be audio/mpeg"
            )
            assert url.endswith(".mp3"), (
                f"{show} item {i}: enclosure URL should end with .mp3"
            )

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_all_items_have_pubdate(self, show):
        _, items = _parse_rss(RSS_FEEDS[show])
        for i, item in enumerate(items):
            pubdate = item.find("pubDate")
            assert pubdate is not None and pubdate.text, (
                f"{show} item {i}: missing <pubDate>"
            )

    # Minimum expected itunes:duration counts per show.
    # Uses >= because new episodes are auto-generated daily.
    MIN_DURATION_COUNTS = {
        "tesla": 49,
        "omni": 4,
        "planetterrian": 2,
        "frontiers": 2,
        "env_intel": 2,
        "models_agents": 2,
    }

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_itunes_duration_counts(self, show):
        """Verify itunes:duration coverage meets minimum per feed."""
        _, items = _parse_rss(RSS_FEEDS[show])
        with_duration = sum(
            1 for item in items
            if _find_itunes(item, "duration") is not None
            and _find_itunes(item, "duration").text
        )
        minimum = self.MIN_DURATION_COUNTS[show]
        assert with_duration >= minimum, (
            f"{show}: expected at least {minimum} items with itunes:duration, found {with_duration}"
        )

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_all_items_have_itunes_episode(self, show):
        _, items = _parse_rss(RSS_FEEDS[show])
        for i, item in enumerate(items):
            ep = _find_itunes(item, "episode")
            assert ep is not None and ep.text, (
                f"{show} item {i}: missing itunes:episode"
            )

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_all_items_have_itunes_explicit(self, show):
        _, items = _parse_rss(RSS_FEEDS[show])
        for i, item in enumerate(items):
            expl = _find_itunes(item, "explicit")
            assert expl is not None and expl.text == "no", (
                f"{show} item {i}: missing or wrong itunes:explicit"
            )

    @pytest.mark.parametrize("show", list(RSS_FEEDS.keys()))
    def test_all_items_have_description(self, show):
        _, items = _parse_rss(RSS_FEEDS[show])
        for i, item in enumerate(items):
            desc = item.find("description")
            assert desc is not None and desc.text, (
                f"{show} item {i}: missing <description>"
            )


# ===================================================================
# TEST: Sample RSS fixture parsing
# ===================================================================

class TestSampleRSSFixture:
    """Tests against the minimal sample_rss_xml fixture from conftest."""

    def test_parse_fixture(self, sample_rss_xml):
        root = ET.fromstring(sample_rss_xml)
        channel = root.find("channel")
        assert channel is not None
        assert channel.find("title").text == "Test Podcast"

    def test_fixture_has_two_items(self, sample_rss_xml):
        root = ET.fromstring(sample_rss_xml)
        items = root.find("channel").findall("item")
        assert len(items) == 2

    def test_fixture_enclosure_urls(self, sample_rss_xml):
        root = ET.fromstring(sample_rss_xml)
        items = root.find("channel").findall("item")
        urls = [item.find("enclosure").get("url") for item in items]
        assert urls == [
            "https://example.com/ep001.mp3",
            "https://example.com/ep002.mp3",
        ]
