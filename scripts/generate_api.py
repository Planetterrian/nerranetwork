#!/usr/bin/env python3
"""
Nerra Network API Generator
Generates static JSON API files for the Nerra Network mobile app.

This script produces:
- api/shows.json: Metadata for all 11 shows
- api/episodes.json: Aggregated feed of recent episodes (last 100)
- api/articles.json: All blog articles for news reader (last 100)
- api/shows/{show_id}.json: Detailed show info with full episode list

Prerequisites:
- Existing RSS feeds: models_agents_podcast.rss, etc.
- JSON digest files: digests/{show_slug}/summaries_{show_slug}.json
- Blog posts: blog/{show_slug}/ep{number}.html
- Cover art: assets/covers/{slug}.jpg

Usage:
    python3 generate_api.py
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import xml.etree.ElementTree as ET


# Show configuration with all metadata
SHOWS = [
    {
        "id": "models_agents",
        "name": "Models & Agents",
        "tagline": "Daily AI models, agents, and practical developments",
        "description": "Stay current with the latest developments in AI models and agents. "
                       "We cover breakthroughs in large language models, agent frameworks, and practical AI applications.",
        "schedule": "Daily",
        "duration": "~15 min",
        "category": "Technology",
        "brand_color": "#8B5CF6",
        "cover_slug": "models-agents",
        "rss_file": "models_agents_podcast.rss",
        "digest_slug": "models_agents",
    },
    {
        "id": "planetterrian",
        "name": "Planetterrian Daily",
        "tagline": "World news and geopolitical analysis",
        "description": "Global news coverage with in-depth analysis of geopolitical developments, "
                       "international affairs, and world events.",
        "schedule": "Daily",
        "duration": "~15 min",
        "category": "News",
        "brand_color": "#0B6FD6",
        "cover_slug": "planetterrian",
        "rss_file": "planetterrian_podcast.rss",
        "digest_slug": "planetterrian",
    },
    {
        "id": "omni_view",
        "name": "Omni View",
        "tagline": "Multi-perspective deep dives into complex topics",
        "description": "Explore complex issues from multiple angles. Each episode provides comprehensive analysis "
                       "from diverse perspectives.",
        "schedule": "Daily",
        "duration": "~20 min",
        "category": "Analysis",
        "brand_color": "#7C5CFF",
        "cover_slug": "omni-view",
        "rss_file": "omni_view_podcast.rss",
        "digest_slug": "omni_view",
    },
    {
        "id": "models_agents_beginners",
        "name": "Models & Agents for Beginners",
        "tagline": "AI explained simply for everyone",
        "description": "Make AI accessible. Complex AI concepts broken down for beginners without sacrificing accuracy. "
                       "Perfect for anyone new to artificial intelligence.",
        "schedule": "Daily",
        "duration": "~10 min",
        "category": "Technology",
        "brand_color": "#018DB1",
        "cover_slug": "models-agents-beginners",
        "rss_file": "models_agents_beginners_podcast.rss",
        "digest_slug": "models_agents_beginners",
    },
    {
        "id": "fascinating_frontiers",
        "name": "Fascinating Frontiers",
        "tagline": "Space exploration and scientific breakthroughs",
        "description": "Discover the frontiers of space exploration, scientific research, and technological innovation. "
                       "From Mars missions to quantum computing.",
        "schedule": "Daily",
        "duration": "~15 min",
        "category": "Science",
        "brand_color": "#16A34A",
        "cover_slug": "fascinating-frontiers",
        "rss_file": "fascinating_frontiers_podcast.rss",
        "digest_slug": "fascinating_frontiers",
    },
    {
        "id": "modern_investing",
        "name": "Modern Investing Techniques",
        "tagline": "Canadian investing strategies and market analysis",
        "description": "Investment insights tailored for Canadian investors. Modern portfolio strategies, "
                       "market analysis, and financial planning.",
        "schedule": "Weekdays",
        "duration": "~12 min",
        "category": "Finance",
        "brand_color": "#059669",
        "cover_slug": "modern-investing",
        "rss_file": "modern_investing_podcast.rss",
        "digest_slug": "modern_investing",
    },
    {
        "id": "tesla",
        "name": "Tesla Shorts Time",
        "tagline": "Tesla news, analysis, and industry insights",
        "description": "In-depth coverage of Tesla news, products, market position, and the broader EV and tech landscape. "
                       "For Tesla enthusiasts and investors.",
        "schedule": "Daily",
        "duration": "~15 min",
        "category": "Business",
        "brand_color": "#E31937",
        "cover_slug": "tesla-shorts",
        "rss_file": "tesla_podcast.rss",
        "digest_slug": "tesla",
    },
    {
        "id": "env_intel",
        "name": "Environmental Intelligence",
        "tagline": "Environmental compliance and sustainability insights",
        "description": "Critical insights for environmental compliance, sustainability practices, and regulatory developments. "
                       "Essential for businesses and environmental professionals.",
        "schedule": "Weekdays",
        "duration": "~10 min",
        "category": "Environment",
        "brand_color": "#16A34A",
        "cover_slug": "env-intel",
        "rss_file": "env_intel_podcast.rss",
        "digest_slug": "env_intel",
    },
    {
        "id": "finansy_prosto",
        "name": "Финансы Просто",
        "tagline": "Финансы и инвестиции на русском языке",
        "description": "Доступное объяснение финансовых концепций, инвестиционных стратегий и экономических новостей "
                       "для русскоговорящей аудитории.",
        "schedule": "Daily",
        "duration": "~12 min",
        "category": "Finance",
        "brand_color": "#EC4899",
        "cover_slug": "finansy-prosto",
        "rss_file": "finansy_prosto_podcast.rss",
        "digest_slug": "finansy_prosto",
    },
    {
        "id": "privet_russian",
        "name": "Привет, Русский!",
        "tagline": "Learn Russian language and culture",
        "description": "Russian language learning with cultural insights. Designed for learners of all levels, "
                       "combining grammar, vocabulary, and cultural context.",
        "schedule": "Daily",
        "duration": "~10 min",
        "category": "Education",
        "brand_color": "#6366F1",
        "cover_slug": "privet-russian",
        "rss_file": "privet_russian_podcast.rss",
        "digest_slug": "privet_russian",
    },
    {
        "id": "unintended_consequences",
        "name": "Unintended Consequences",
        "tagline": "Good intentions. Surprising results. Real lessons.",
        "description": "A daily narrative podcast profiling inventions, policies, and systems that were "
                       "designed with good intentions — but triggered surprising, unintended consequences. "
                       "From the Cobra Effect to social media algorithms, every episode follows a single "
                       "case study through good intentions, implementation, unexpected fallout, and the "
                       "lessons we can learn.",
        "schedule": "Weekdays",
        "duration": "~15-18 min",
        "category": "Education",
        "brand_color": "#B45309",
        "cover_slug": "unintended-consequences",
        "rss_file": "unintended_consequences_podcast.rss",
        "digest_slug": "unintended_consequences",
    },
]

# Base URL for the Nerra Network website
BASE_URL = "https://nerranetwork.com"
# The repository root where RSS feeds, blog posts, and digests are located
REPO_ROOT = Path(__file__).parent.parent  # api/generate_api.py -> api -> nerra-app (repo root)


class APIGenerator:
    """Generates JSON API files for the Nerra Network mobile app."""

    def __init__(self, repo_root: Path):
        """Initialize the generator with the repository root path.

        Args:
            repo_root: Root directory of the Nerra Networks repository
        """
        self.repo_root = repo_root
        self.api_dir = repo_root / "api"
        self.shows_dir = repo_root / "shows"
        self.api_dir.mkdir(parents=True, exist_ok=True)
        self.generated_files = []
        self.generated_count = {
            "shows": 0,
            "episodes": 0,
            "articles": 0,
            "show_details": 0,
        }

    def get_timestamp(self) -> str:
        """Get current timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def parse_rss_episodes(self, show: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse episodes from RSS feed.

        Args:
            show: Show configuration dictionary

        Returns:
            List of episode dictionaries
        """
        episodes = []
        rss_path = self.repo_root / show["rss_file"]

        if not rss_path.exists():
            print(f"  Warning: RSS file not found: {show['rss_file']}")
            return episodes

        try:
            tree = ET.parse(rss_path)
            root = tree.getroot()

            # Handle RSS namespaces
            namespaces = {
                'content': 'http://purl.org/rss/1.0/modules/content/',
                'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
            }

            for item in root.findall('.//item'):
                title_elem = item.find('title')
                pub_date_elem = item.find('pubDate')
                link_elem = item.find('link')
                description_elem = item.find('description')
                duration_elem = item.find('itunes:duration', namespaces)

                if title_elem is not None and pub_date_elem is not None:
                    # Extract episode number from title if present
                    episode_number = self._extract_episode_number(title_elem.text or "")

                    # Parse publish date
                    try:
                        # Handle RFC 2822 date format from RSS
                        date_str = pub_date_elem.text or ""
                        date_obj = self._parse_rss_date(date_str)
                        date_iso = date_obj.strftime("%Y-%m-%d")
                    except Exception as e:
                        print(f"    Warning: Could not parse date '{pub_date_elem.text}': {e}")
                        continue

                    # Get audio URL from enclosure
                    audio_url = ""
                    enclosure = item.find('enclosure')
                    if enclosure is not None:
                        audio_url = enclosure.get('url', '')

                    # Get summary from description
                    summary = ""
                    if description_elem is not None:
                        summary = (description_elem.text or "")[:300]

                    # Get duration
                    duration = show.get("duration", "~15 min")
                    if duration_elem is not None and duration_elem.text:
                        duration = f"~{duration_elem.text} min"

                    episodes.append({
                        "show_id": show["id"],
                        "show_name": show["name"],
                        "brand_color": show["brand_color"],
                        "episode_number": episode_number,
                        "title": title_elem.text or "Untitled",
                        "date": date_iso,
                        "summary": summary,
                        "audio_url": audio_url,
                        "blog_url": f"{BASE_URL}/blog/{show['digest_slug']}/ep{episode_number}.html",
                        "duration": duration,
                    })

        except ET.ParseError as e:
            print(f"  Error parsing RSS file {show['rss_file']}: {e}")

        return episodes

    def _extract_episode_number(self, title: str) -> str:
        """Extract episode number from title.

        Args:
            title: Episode title

        Returns:
            Episode number as string (zero-padded), or empty string if not found
        """
        # Look for patterns like "Episode 123", "Ep. 123", "#123", etc.
        patterns = [
            r'[Ee]pisode\s+(\d+)',
            r'[Ee]p\.?\s+(\d+)',
            r'#(\d+)',
            r'^\d+',
        ]

        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                num = match.group(1)
                return num.zfill(3)

        return ""

    def _parse_rss_date(self, date_str: str) -> datetime:
        """Parse RFC 2822 date from RSS feed.

        Args:
            date_str: Date string in RFC 2822 format

        Returns:
            Datetime object
        """
        # Handle common RSS date formats
        date_formats = [
            "%a, %d %b %Y %H:%M:%S %z",  # Mon, 01 Jan 2024 12:00:00 +0000
            "%a, %d %b %Y %H:%M:%S %Z",  # Mon, 01 Jan 2024 12:00:00 GMT
            "%Y-%m-%dT%H:%M:%S%z",       # 2024-01-01T12:00:00+00:00
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Fallback: try basic parsing
        raise ValueError(f"Could not parse date: {date_str}")

    def load_digest_summaries(self, show: Dict[str, Any]) -> Dict[str, str]:
        """Load episode summaries from digest JSON file.

        Args:
            show: Show configuration dictionary

        Returns:
            Dictionary mapping episode numbers to summaries
        """
        summaries = {}
        digest_path = self.repo_root / "digests" / show["digest_slug"] / f"summaries_{show['digest_slug']}.json"

        if not digest_path.exists():
            return summaries

        try:
            with open(digest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "summaries" in data:
                    for item in data["summaries"]:
                        if "episode_number" in item and "summary" in item:
                            summaries[item["episode_number"]] = item["summary"]
        except (json.JSONDecodeError, IOError) as e:
            print(f"  Warning: Could not load digest for {show['digest_slug']}: {e}")

        return summaries

    def scan_blog_articles(self, show: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scan blog directory for article files.

        Args:
            show: Show configuration dictionary

        Returns:
            List of article dictionaries
        """
        articles = []
        blog_dir = self.repo_root / "blog" / show["digest_slug"]

        if not blog_dir.exists():
            return articles

        try:
            for html_file in sorted(blog_dir.glob("ep*.html"), reverse=True):
                # Extract episode number from filename
                match = re.search(r'ep(\d+)\.html', html_file.name)
                if not match:
                    continue

                episode_number = match.group(1)

                try:
                    with open(html_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Extract title from <h1> or <title> tag
                    title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', content)
                    title = title_match.group(1) if title_match else f"Episode {episode_number}"

                    # Extract first 160 chars as hook
                    text_match = re.search(r'<article[^>]*>(.*?)</article>', content, re.DOTALL)
                    if text_match:
                        # Remove HTML tags
                        text = re.sub(r'<[^>]+>', '', text_match.group(1))
                        # Clean up whitespace
                        text = re.sub(r'\s+', ' ', text).strip()
                        hook = text[:160]
                    else:
                        hook = ""

                    # Estimate read time (150 words per minute)
                    word_count = len(content.split())
                    read_time = max(1, round(word_count / 150))

                    # Get file modification time as article date
                    mod_time = datetime.fromtimestamp(html_file.stat().st_mtime)
                    date_str = mod_time.strftime("%Y-%m-%d")

                    articles.append({
                        "show_id": show["id"],
                        "show_name": show["name"],
                        "brand_color": show["brand_color"],
                        "episode_number": episode_number,
                        "title": title,
                        "date": date_str,
                        "read_time": f"{read_time} min",
                        "hook": hook,
                        "url": f"{BASE_URL}/blog/{show['digest_slug']}/ep{episode_number}.html",
                    })

                except IOError as e:
                    print(f"    Warning: Could not read {html_file.name}: {e}")

        except Exception as e:
            print(f"  Error scanning blog directory for {show['digest_slug']}: {e}")

        return articles

    def generate_shows_json(self) -> bool:
        """Generate shows.json with metadata for all shows.

        Returns:
            True if successful, False otherwise
        """
        print("Generating api/shows.json...")

        shows_data = {
            "network": "Nerra Network",
            "updated": self.get_timestamp(),
            "shows": [],
        }

        for show in SHOWS:
            show_obj = {
                "id": show["id"],
                "name": show["name"],
                "tagline": show["tagline"],
                "description": show["description"],
                "schedule": show["schedule"],
                "duration": show["duration"],
                "language": "en" if show["id"] not in ["finansy_prosto", "privet_russian"] else
                           ("ru" if show["id"] != "privet_russian" else "en"),
                "brand_color": show["brand_color"],
                "cover_url": f"{BASE_URL}/assets/covers/{show['cover_slug']}.jpg",
                "rss_url": f"{BASE_URL}/{show['rss_file']}",
                "blog_url": f"{BASE_URL}/blog/{show['digest_slug']}/",
                "page_url": f"{BASE_URL}/{show['id'].replace('_', '-')}.html",
                "category": show["category"],
            }
            shows_data["shows"].append(show_obj)

        output_file = self.api_dir / "shows.json"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(shows_data, f, indent=2, ensure_ascii=False)
            self.generated_files.append(str(output_file))
            self.generated_count["shows"] = 1
            print(f"  Created {output_file.name} with {len(shows_data['shows'])} shows")
            return True
        except IOError as e:
            print(f"  Error writing shows.json: {e}")
            return False

    def generate_episodes_json(self) -> bool:
        """Generate episodes.json with aggregated recent episodes.

        Returns:
            True if successful, False otherwise
        """
        print("Generating api/episodes.json...")

        all_episodes = []

        for show in SHOWS:
            print(f"  Scanning {show['name']}...")
            episodes = self.parse_rss_episodes(show)
            all_episodes.extend(episodes)

        # Sort by date descending, limit to last 100
        all_episodes.sort(key=lambda x: x["date"], reverse=True)
        all_episodes = all_episodes[:100]

        episodes_data = {
            "updated": self.get_timestamp(),
            "episodes": all_episodes,
        }

        output_file = self.api_dir / "episodes.json"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(episodes_data, f, indent=2, ensure_ascii=False)
            self.generated_files.append(str(output_file))
            self.generated_count["episodes"] = len(all_episodes)
            print(f"  Created {output_file.name} with {len(all_episodes)} episodes")
            return True
        except IOError as e:
            print(f"  Error writing episodes.json: {e}")
            return False

    def generate_articles_json(self) -> bool:
        """Generate articles.json with all blog articles.

        Returns:
            True if successful, False otherwise
        """
        print("Generating api/articles.json...")

        all_articles = []

        for show in SHOWS:
            print(f"  Scanning blog articles for {show['name']}...")
            articles = self.scan_blog_articles(show)
            all_articles.extend(articles)

        # Sort by date descending, limit to last 100
        all_articles.sort(key=lambda x: x["date"], reverse=True)
        all_articles = all_articles[:100]

        articles_data = {
            "updated": self.get_timestamp(),
            "articles": all_articles,
        }

        output_file = self.api_dir / "articles.json"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(articles_data, f, indent=2, ensure_ascii=False)
            self.generated_files.append(str(output_file))
            self.generated_count["articles"] = len(all_articles)
            print(f"  Created {output_file.name} with {len(all_articles)} articles")
            return True
        except IOError as e:
            print(f"  Error writing articles.json: {e}")
            return False

    def generate_show_detail_json(self, show: Dict[str, Any]) -> bool:
        """Generate detailed JSON for a specific show.

        Args:
            show: Show configuration dictionary

        Returns:
            True if successful, False otherwise
        """
        episodes = self.parse_rss_episodes(show)
        articles = self.scan_blog_articles(show)

        # Sort by date descending
        episodes.sort(key=lambda x: x["date"], reverse=True)
        articles.sort(key=lambda x: x["date"], reverse=True)

        show_detail = {
            "id": show["id"],
            "name": show["name"],
            "tagline": show["tagline"],
            "description": show["description"],
            "schedule": show["schedule"],
            "duration": show["duration"],
            "language": "en" if show["id"] not in ["finansy_prosto", "privet_russian"] else
                       ("ru" if show["id"] != "privet_russian" else "en"),
            "brand_color": show["brand_color"],
            "cover_url": f"{BASE_URL}/assets/covers/{show['cover_slug']}.jpg",
            "rss_url": f"{BASE_URL}/{show['rss_file']}",
            "blog_url": f"{BASE_URL}/blog/{show['digest_slug']}/",
            "page_url": f"{BASE_URL}/{show['id'].replace('_', '-')}.html",
            "category": show["category"],
            "updated": self.get_timestamp(),
            "episode_count": len(episodes),
            "episodes": episodes,
            "articles": articles,
        }

        output_file = self.api_dir / f"{show['id']}.json"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(show_detail, f, indent=2, ensure_ascii=False)
            self.generated_files.append(str(output_file))
            self.generated_count["show_details"] += 1
            return True
        except IOError as e:
            print(f"  Error writing {show['id']}.json: {e}")
            return False

    def generate_all(self) -> None:
        """Generate all API files."""
        print("\n" + "="*70)
        print("Nerra Network API Generator")
        print("="*70 + "\n")

        # Generate main API files
        self.generate_shows_json()
        self.generate_episodes_json()
        self.generate_articles_json()

        # Generate per-show detail files
        print("\nGenerating per-show JSON files...")
        for show in SHOWS:
            print(f"  Generating {show['id']}.json...")
            self.generate_show_detail_json(show)

        # Print summary
        self._print_summary()

    def _print_summary(self) -> None:
        """Print generation summary."""
        print("\n" + "="*70)
        print("Generation Summary")
        print("="*70)
        print(f"Shows metadata file:        {self.generated_count['shows']} file")
        print(f"Aggregated episodes:        {self.generated_count['episodes']} episodes")
        print(f"Blog articles:              {self.generated_count['articles']} articles")
        print(f"Per-show detail files:      {self.generated_count['show_details']} files")
        print(f"Total files created:        {len(self.generated_files)} files")
        print("\nGenerated files:")
        for file_path in self.generated_files:
            rel_path = Path(file_path).relative_to(self.repo_root) if self.repo_root in Path(file_path).parents else Path(file_path)
            print(f"  - {rel_path}")
        print("\n" + "="*70 + "\n")


def main():
    """Main entry point."""
    try:
        generator = APIGenerator(REPO_ROOT)
        generator.generate_all()
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
