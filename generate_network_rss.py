#!/usr/bin/env python3
"""Generate a combined Nerra Network RSS feed from all show feeds."""

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime, format_datetime
from datetime import datetime, timezone
from pathlib import Path

FEEDS = [
    "podcast.rss",
    "omni_view_podcast.rss",
    "fascinating_frontiers_podcast.rss",
    "planetterrian_podcast.rss",
    "env_intel_podcast.rss",
    "models_agents_podcast.rss",
    "models_agents_beginners_podcast.rss",
    "finansy_prosto_podcast.rss",
    "privet_russian_podcast.rss",
    "modern_investing_podcast.rss",
    "unintended_consequences_podcast.rss",
]

MAX_EPISODES = 50
OUTPUT = "network.rss"

NETWORK_TITLE = "Nerra Network"
NETWORK_DESCRIPTION = (
    "Daily podcasts keeping you informed about exciting changes in the world. "
    "Unbiased, multi-perspective coverage of Tesla, world news, space, science, AI, "
    "the environment, modern investing, financial literacy, Russian language learning, "
    "and the unintended consequences of well-meant ideas."
)
NETWORK_LINK = "https://nerranetwork.com/"
NETWORK_IMAGE = "https://nerranetwork.com/assets/covers/svg/Nerra-Network-Logo.svg"


def parse_pub_date(text: str) -> datetime:
    """Parse an RFC-2822 pubDate string to a timezone-aware datetime."""
    try:
        return parsedate_to_datetime(text)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def main() -> None:
    # Register namespaces BEFORE parsing so they serialize with proper prefixes
    ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
    ET.register_namespace("podcast", "https://podcastindex.org/namespace/1.0")
    ET.register_namespace("atom", "http://www.w3.org/2005/Atom")

    project_root = Path(__file__).resolve().parent
    episodes = []

    for feed_file in FEEDS:
        feed_path = project_root / feed_file
        if not feed_path.exists():
            print(f"SKIP: {feed_file} not found")
            continue

        try:
            tree = ET.parse(feed_path)
            root = tree.getroot()
            for item in root.findall(".//item"):
                # Store the raw XML element and its parsed date for sorting
                pub_el = item.find("pubDate")
                pub_date = parse_pub_date(pub_el.text if pub_el is not None else "")
                episodes.append((pub_date, item))
        except Exception as e:
            print(f"ERROR parsing {feed_file}: {e}")
            continue

    # Sort newest first and limit
    episodes.sort(key=lambda x: x[0], reverse=True)
    episodes = episodes[:MAX_EPISODES]

    print(f"Merged {len(episodes)} episodes from {len(FEEDS)} feeds")

    # Build the combined RSS — namespace declarations are handled by
    # ET.register_namespace above; no need for manual xmlns:* attributes.
    rss = ET.Element("rss", version="2.0")

    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = NETWORK_TITLE
    ET.SubElement(channel, "description").text = NETWORK_DESCRIPTION
    ET.SubElement(channel, "link").text = NETWORK_LINK
    ET.SubElement(channel, "language").text = "en"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(
        datetime.now(timezone.utc)
    )

    image = ET.SubElement(channel, "image")
    ET.SubElement(image, "url").text = NETWORK_IMAGE
    ET.SubElement(image, "title").text = NETWORK_TITLE
    ET.SubElement(image, "link").text = NETWORK_LINK

    itunes_image = ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}image")
    itunes_image.set("href", NETWORK_IMAGE)

    for _, item in episodes:
        channel.append(item)

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    tree.write(
        project_root / OUTPUT,
        xml_declaration=True,
        encoding="unicode",
        method="xml",
    )
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
