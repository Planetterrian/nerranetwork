"""
Shared pytest fixtures for Tesla Shorts Time test suite.

These fixtures provide sample data for testing the pure functions
that exist across the podcast generation scripts.
"""

import os
import sys
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIGESTS_DIR = PROJECT_ROOT / "digests"

# Ensure the digests package is importable (scripts live there today).
sys.path.insert(0, str(DIGESTS_DIR))


# ---------------------------------------------------------------------------
# Sample digest / transcript text
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_tesla_text():
    """A representative snippet of Tesla digest text with acronyms, numbers,
    currencies, dates, times, and percentages."""
    return textwrap.dedent("""\
        Tesla's TSLA stock surged +3.59% to $430.17 on November 19, 2025,
        as FSD v13.2 rolled out via OTA update. The new AI-powered system
        handles 4680 battery EVs and ICE vehicle detection with improved
        HW4 sensors.  SpaceX launched its Starship at 02:30 PM PST.
        NASA confirmed the EPA rating of 350 MPGe for the refreshed
        Model 3 LFP variant.  Robotaxis are expected to begin V2G
        integration by Q2 2026, with DC fast-charging at 250 kW.
        The $3 Trillion milestone is within reach.
    """)


@pytest.fixture
def sample_omni_text():
    """Text typical of the Omni View show — multi-topic with currencies,
    percentages, dates, and ordinals."""
    return textwrap.dedent("""\
        The Federal Reserve held rates steady at 5.25% on February 10th,
        while the EU proposed a €500 billion infrastructure plan.
        Meanwhile, UK inflation fell to 3.2%, bringing the £1.27 exchange
        rate into focus.  Markets reacted: $AAPL rose $12.50 and the
        S&P 500 gained 1.4%.  The 3rd quarter GDP revision is due at
        10:30 AM EST on March 1, 2026.
    """)


@pytest.fixture
def sample_rss_xml():
    """Minimal but structurally complete podcast RSS feed for testing
    the RSS parser without touching real files."""
    return textwrap.dedent("""\
        <?xml version='1.0' encoding='UTF-8'?>
        <rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
             xmlns:atom="http://www.w3.org/2005/Atom"
             version="2.0">
          <channel>
            <title>Test Podcast</title>
            <link>https://example.com</link>
            <description>A test podcast feed.</description>
            <language>en-us</language>
            <copyright>Copyright 2025</copyright>
            <generator>python-feedgen</generator>
            <lastBuildDate>Sun, 15 Feb 2026 11:15:50 +0000</lastBuildDate>
            <itunes:author>Tester</itunes:author>
            <itunes:category text="Technology"/>
            <itunes:image href="https://example.com/image.jpg"/>
            <itunes:explicit>no</itunes:explicit>
            <itunes:owner>
              <itunes:name>Tester</itunes:name>
              <itunes:email>test@example.com</itunes:email>
            </itunes:owner>
            <itunes:summary>A test summary.</itunes:summary>
            <item>
              <title>Episode 1</title>
              <description>First episode.</description>
              <guid isPermaLink="false">test-ep001</guid>
              <enclosure url="https://example.com/ep001.mp3"
                         length="1234567" type="audio/mpeg"/>
              <pubDate>Mon, 01 Jan 2026 08:00:00 +0000</pubDate>
              <itunes:duration>05:00</itunes:duration>
              <itunes:episode>1</itunes:episode>
              <itunes:season>1</itunes:season>
              <itunes:episodeType>full</itunes:episodeType>
              <itunes:explicit>no</itunes:explicit>
            </item>
            <item>
              <title>Episode 2</title>
              <description>Second episode.</description>
              <guid isPermaLink="false">test-ep002</guid>
              <enclosure url="https://example.com/ep002.mp3"
                         length="2345678" type="audio/mpeg"/>
              <pubDate>Tue, 02 Jan 2026 08:00:00 +0000</pubDate>
              <itunes:duration>07:30</itunes:duration>
              <itunes:episode>2</itunes:episode>
              <itunes:season>1</itunes:season>
              <itunes:episodeType>full</itunes:episodeType>
              <itunes:explicit>no</itunes:explicit>
            </item>
          </channel>
        </rss>
    """)


# ---------------------------------------------------------------------------
# RSS feed file paths (real files in the repo)
# ---------------------------------------------------------------------------

RSS_FEEDS = {
    "tesla": PROJECT_ROOT / "podcast.rss",
    "omni": PROJECT_ROOT / "omni_view_podcast.rss",
    "planetterrian": PROJECT_ROOT / "planetterrian_podcast.rss",
    "frontiers": PROJECT_ROOT / "fascinating_frontiers_podcast.rss",
    "env_intel": PROJECT_ROOT / "env_intel_podcast.rss",
    "models_agents": PROJECT_ROOT / "models_agents_podcast.rss",
}

# Minimum episode counts — tests use >= to avoid breaking when new episodes
# are published.  Update these only when episodes are removed.
EXPECTED_EPISODE_COUNTS = {
    "tesla": 49,
    "omni": 4,
    "frontiers": 22,
    "planetterrian": 13,
    "env_intel": 2,
    "models_agents": 2,
}


@pytest.fixture(params=list(RSS_FEEDS.keys()))
def rss_feed_info(request):
    """Parametrized fixture that yields (show_name, rss_path, expected_count)
    for each of the four podcast RSS feeds."""
    name = request.param
    return name, RSS_FEEDS[name], EXPECTED_EPISODE_COUNTS[name]


# ---------------------------------------------------------------------------
# Mock API responses (for future integration tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_openai_digest_response():
    """Shape of a typical OpenAI/xAI digest generation response."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Here is today's Tesla news digest...",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 5000,
            "completion_tokens": 2000,
            "total_tokens": 7000,
        },
    }


@pytest.fixture
def mock_yfinance_data():
    """Shape of typical yfinance stock data."""
    return {
        "symbol": "TSLA",
        "regularMarketPrice": 430.17,
        "regularMarketChange": 14.92,
        "regularMarketChangePercent": 3.59,
        "regularMarketVolume": 125_000_000,
        "regularMarketOpen": 416.50,
        "regularMarketDayHigh": 432.00,
        "regularMarketDayLow": 415.10,
        "regularMarketPreviousClose": 415.25,
    }


# ---------------------------------------------------------------------------
# A registered show that has published nothing
# ---------------------------------------------------------------------------

#: The show the "nothing published yet" guards render. Until 2026-10-08 these
#: guards used Nerra Voices itself, which had no feed; its first episode went
#: out that day and ten guards about the PRE-launch page failed at once on
#: main. The behaviour they protect is for the next show that launches, so
#: they now render a registered show with its feed and summaries pointed at
#: files that do not exist — the exact state a scaffolded show is in.
UNPUBLISHED_SLUG = "nerra_voices"


@pytest.fixture
def unpublished_show(monkeypatch):
    """Make ``UNPUBLISHED_SLUG`` look like a show with no episodes.

    Returns the slug. Everything that derives "has a feed" or "has episodes"
    reads the registry entry at call time, so patching the entry is enough.
    """
    import generate_html as G

    cfg = dict(G.NETWORK_SHOWS[UNPUBLISHED_SLUG])
    cfg["rss_file"] = "unpublished_show_podcast.rss"
    cfg["json_path"] = "digests/_unpublished_show/summaries_unpublished.json"
    assert not (PROJECT_ROOT / cfg["rss_file"]).exists()
    assert not (PROJECT_ROOT / cfg["json_path"]).exists()
    monkeypatch.setitem(G.NETWORK_SHOWS, UNPUBLISHED_SLUG, cfg)
    return UNPUBLISHED_SLUG
