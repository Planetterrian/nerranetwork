"""Cross-episode content tracking for all podcast shows.

Prevents story repetition, quote reuse, and topic clustering across episodes
by maintaining a per-show JSON tracker file.

Each show provides its own section_patterns dict so the tracker can extract
and record section content from generated digests.

Usage:
    from engine.content_tracker import ContentTracker

    tracker = ContentTracker("fascinating_frontiers", output_dir)
    tracker.load()

    # Before generation: get prompt context about recently used content
    summary = tracker.get_summary_for_prompt()

    # Before generation: filter articles already covered recently
    articles = tracker.filter_recent_articles(articles)

    # After generation: extract and record sections from the new digest
    tracker.record_episode(digest_text, section_patterns)
    tracker.save()
"""

import datetime
import fcntl
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from engine.utils import calculate_similarity, norm_headline_for_similarity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default section patterns per show
# ---------------------------------------------------------------------------

TST_SECTION_PATTERNS: Dict[str, str] = {
    "headlines": (
        r"(?:📰 \*\*Top (?:10 )?News(?: Items)?\*\*|### Top (?:10 )?News(?: Items)?)"
        r"(.*?)"
        r"(?=━━|## Short Spot|📉|### Tesla First Principles|## Tesla X Takeover|🎙️ \*\*Tesla X Takeover)"
    ),
    "takeover_headlines": (
        r"(?:## Tesla X Takeover|🎙️ \*\*Tesla X Takeover[^\n]*)"
        r"(.*?)"
        r"(?=━━|## Short Spot|📉|### Tesla First Principles|$)"
    ),
    "short_spot": (
        r"(?:## Short Spot|📉 \*\*Short Spot\*\*)"
        r"(.*?)"
        r"(?=━━|### Short Squeeze|📈|### Daily Challenge|💪|✨|### Tesla First Principles|🧠|$)"
    ),
    "first_principles": (
        r"(?:### Tesla First Principles|🧠 Tesla First Principles)"
        r"(.*?)"
        r"(?=━━|### Daily Challenge|💪|## Tesla Market Movers|$)"
    ),
    "daily_challenge": (
        r"(?:### Daily Challenge|💪 \*\*Daily Challenge\*\*)"
        r"(.*?)"
        r"(?=━━|✨|\*\*Inspiration Quote\*\*|$)"
    ),
    "inspiration_quote": (
        r"(?:✨ \*\*Inspiration Quote:\*\*|\*\*Inspiration Quote:\*\*|Inspiration Quote:)"
        r"\s*\"([^\"]+)\"\s*[–-]\s*([^,\n]+)"
    ),
    # Deep dive tracking (alias for first_principles)
    "deep_dive": (
        r"(?:### Tesla First Principles|🧠 Tesla First Principles)"
        r"(.*?)"
        r"(?=━━|### Daily Challenge|💪|## Tesla Market Movers|$)"
    ),
}

FF_SECTION_PATTERNS: Dict[str, str] = {
    "headlines": (
        r"(?:### Top 15 Space|### Top \d+ Space)"
        r"(.*?)"
        r"(?=━━|### Cosmic Spotlight|### Cosmic Deep Dive|$)"
    ),
    "cosmic_spotlight": (
        r"(?:### Cosmic Spotlight)"
        r"(.*?)"
        r"(?=━━|### Cosmic Deep Dive|### Daily Inspiration|$)"
    ),
    "deep_dive": (
        r"(?:### Cosmic Deep Dive)"
        r"(.*?)"
        r"(?=━━|### Daily Inspiration|$)"
    ),
    "daily_inspiration": (
        r"(?:### Daily Inspiration)"
        r"(.*?)"
        r"(?=━━|$)"
    ),
}

PT_SECTION_PATTERNS: Dict[str, str] = {
    "headlines": (
        r"(?:### Top 15 Science|### Top \d+ Science)"
        r"(.*?)"
        r"(?=━━|### Planetterrian Spotlight|### Science Deep Dive|$)"
    ),
    "planetterrian_spotlight": (
        r"(?:### Planetterrian Spotlight)"
        r"(.*?)"
        r"(?=━━|### Science Deep Dive|### Daily Inspiration|$)"
    ),
    "deep_dive": (
        r"(?:### Science Deep Dive)"
        r"(.*?)"
        r"(?=━━|### Daily Inspiration|$)"
    ),
    "daily_inspiration": (
        r"(?:### Daily Inspiration)"
        r"(.*?)"
        r"(?=━━|$)"
    ),
}

OV_SECTION_PATTERNS: Dict[str, str] = {
    "headlines": (
        r"(?:### Top \d+|### Today's Top)"
        r"(.*?)"
        r"(?=━━|### (?:Deep Dive|Understanding the Issue|Closing)|$)"
    ),
    "deep_dive": (
        r"(?:### Understanding the Issue|## Understanding the Issue)"
        r"(.*?)"
        r"(?=━━|## Media-literacy note|$)"
    ),
}

EI_SECTION_PATTERNS: Dict[str, str] = {
    "headlines": (
        r"(?:### Lead Story|## Lead Story)"
        r"(.*?)"
        r"(?=━━|### Regulatory|## Regulatory|$)"
    ),
    "regulatory_watch": (
        r"(?:### Regulatory & Policy Watch|## Regulatory & Policy Watch)"
        r"(.*?)"
        r"(?=━━|### Science|## Science|$)"
    ),
    "science_technical": (
        r"(?:### Science & Technical|## Science & Technical)"
        r"(.*?)"
        r"(?=━━|### Industry|## Industry|$)"
    ),
    "industry_practice": (
        r"(?:### Industry & Practice|## Industry & Practice)"
        r"(.*?)"
        r"(?=━━|### Practitioner|## Practitioner|### Action Items|## Action Items|$)"
    ),
    "deep_dive": (
        r"(?:### Practitioner Deep Dive|## Practitioner Deep Dive)"
        r"(.*?)"
        r"(?=━━|### Action Items|## Action Items|$)"
    ),
}

MA_SECTION_PATTERNS: Dict[str, str] = {
    "headlines": (
        r"(?:### Top Story|## Top Story)"
        r"(.*?)"
        r"(?=━━|### Model Updates|## Model Updates|$)"
    ),
    "model_updates": (
        r"(?:### Model Updates|## Model Updates)"
        r"(.*?)"
        r"(?=━━|### Agent|## Agent|$)"
    ),
    "agent_developments": (
        r"(?:### Agent & Tool Developments|## Agent & Tool Developments)"
        r"(.*?)"
        r"(?=━━|### Practical|## Practical|$)"
    ),
    "practical_community": (
        r"(?:### Practical & Community|## Practical & Community)"
        r"(.*?)"
        r"(?=━━|### Under the Hood|## Under the Hood|### Things to Try|## Things to Try|$)"
    ),
    "deep_dive": (
        r"(?:### Under the Hood|## Under the Hood)"
        r"(.*?)"
        r"(?=━━|### Things to Try|## Things to Try|$)"
    ),
}

MAB_SECTION_PATTERNS: Dict[str, str] = {
    "headlines": (
        r"(?:### The Big Story|## The Big Story)"
        r"(.*?)"
        r"(?=━━|### Explain Like|## Explain Like|$)"
    ),
    "explain_like_14": (
        r"(?:### Explain Like I'm 14|## Explain Like I'm 14)"
        r"(.*?)"
        r"(?=━━|### Cool Stuff|## Cool Stuff|### Cool Tools|## Cool Tools|$)"
    ),
    "cool_stuff": (
        r"(?:### Cool Stuff|## Cool Stuff|### Cool Tools|## Cool Tools)"
        r"(.*?)"
        r"(?=━━|### Quick Bits|## Quick Bits|$)"
    ),
    "quick_bits": (
        r"(?:### Quick Bits|## Quick Bits)"
        r"(.*?)"
        r"(?=━━|### Closing|## Closing|$)"
    ),
    # Deep dive tracking (alias for explain_like_14)
    "deep_dive": (
        r"(?:### Explain Like I'm 14|## Explain Like I'm 14)"
        r"(.*?)"
        r"(?=━━|### Cool Stuff|## Cool Stuff|### Cool Tools|## Cool Tools|$)"
    ),
}

FP_SECTION_PATTERNS: Dict[str, str] = {
    "headlines": (
        r"(?:### Главная тема|## Главная тема|главная новость)"
        r"(.*?)"
        r"(?=━━|### Объясни как подруге|## Объясни как подруге|### Как это работает|## Как это работает|### Коротко|## Коротко|$)"
    ),
    "deep_dive": (
        r"(?:### Объясни как подруге|## Объясни как подруге)"
        r"(.*?)"
        r"(?=━━|### Практические советы|## Практические советы|### Коротко|## Коротко|$)"
    ),
    "practical_tips": (
        r"(?:### Практические советы|## Практические советы|попробуйте сами)"
        r"(.*?)"
        r"(?=━━|### Коротко|## Коротко|### Завершение|## Завершение|$)"
    ),
    "quick_news": (
        r"(?:### Коротко и ясно|## Коротко и ясно|быстрые новости)"
        r"(.*?)"
        r"(?=━━|### Завершение|## Завершение|на сегодня всё|$)"
    ),
}

PR_SECTION_PATTERNS: Dict[str, str] = {
    "headlines": (
        r"(?:### Main Topic|## Main Topic|### Главная тема)"
        r"(.*?)"
        r"(?=━━|### Practice|## Practice|### Практика|$)"
    ),
    "deep_dive": (
        r"(?:### Word Origins|## Word Origins|### Происхождение слов)"
        r"(.*?)"
        r"(?=━━|### Cultural Corner|## Cultural Corner|### Practice|## Practice|$)"
    ),
}

MI_SECTION_PATTERNS: Dict[str, str] = {
    "headlines": (
        r"(?:### Strategy Spotlight|## Strategy Spotlight)"
        r"(.*?)"
        r"(?=━━|### Practice Investment|## Practice Investment|$)"
    ),
    # Deep dive tracking (alias for strategy_spotlight / investor_education)
    "deep_dive": (
        r"(?:### Investor Education|## Investor Education|### Strategy Spotlight|## Strategy Spotlight)"
        r"(.*?)"
        r"(?=━━|### Practice Investment|## Practice Investment|### Tools|$)"
    ),
    "market_pulse": (
        r"(?:\*\*Market Pulse:\*\*|### Market Pulse)"
        r"(.*?)"
        r"(?=━━|### Strategy|## Strategy|$)"
    ),
    "practice_investment": (
        r"(?:### Practice Investment|## Practice Investment)"
        r"(.*?)"
        r"(?=━━|### Yesterday|## Yesterday|### Tools|$)"
    ),
    "tools_techniques": (
        r"(?:### Tools & Techniques|## Tools & Techniques)"
        r"(.*?)"
        r"(?=━━|### Quick Hits|## Quick Hits|$)"
    ),
    "quick_hits": (
        r"(?:### Quick Hits|## Quick Hits)"
        r"(.*?)"
        r"(?=━━|### Portfolio|## Portfolio|### TONE|$)"
    ),
}


# Unintended Consequences — narrative show, six segments per episode.
# Each segment header (Hook / Good Intention / Implementation /
# Unintended Consequences / Aftermath / Lesson) lives in the episode
# brief produced by the digest stage; podcast script weaves them into
# flowing narration without literal headers, but the brief itself
# carries the markers below for cross-episode dedup tracking.
UC_SECTION_PATTERNS: Dict[str, str] = {
    "hook": (
        r"(?:### Segment 1 — The Hook|### The Hook)"
        r"(.*?)"
        r"(?=### Segment|### The Good|━━|$)"
    ),
    "good_intention": (
        r"(?:### Segment 2 — The Good Intention|### The Good Intention)"
        r"(.*?)"
        r"(?=### Segment|### The Implementation|━━|$)"
    ),
    "consequences": (
        r"(?:### Segment 4 — The Unintended Consequences|### The Unintended Consequences)"
        r"(.*?)"
        r"(?=### Segment|### The Aftermath|━━|$)"
    ),
    "aftermath": (
        r"(?:### Segment 5 — The Aftermath|### The Aftermath)"
        r"(.*?)"
        r"(?=### Segment|### The Lesson|━━|$)"
    ),
    "lesson": (
        r"(?:### Segment 6 — The Lesson|### The Lesson)"
        r"(.*?)"
        r"(?=━━|$)"
    ),
}


# SpaceX Daily digest sections (June 2026 launch). "deep_dive" keys feed
# the cross-episode deep-dive topic tracker, which backs the digest
# prompt's "Engineering Angle topic differs from recent essays" rule;
# "counterpoint" backs the matching no-repeat rule for The Counterpoint.
SPACEX_SECTION_PATTERNS: Dict[str, str] = {
    "headlines": (
        r"(?:### Top News)"
        r"(.*?)"
        r"(?=━━|### Market Watch|### Engineering Deep Dive|## Community Buzz|$)"
    ),
    "counterpoint": (
        r"(?:## The Counterpoint)"
        r"(.*?)"
        # June 2026 engineering rebalance renamed the flagship essay
        # "Engineering Deep Dive"; keep the old name as a fallback so
        # historical digests still parse. The AI & Compute section was
        # inserted between Counterpoint and the deep dive.
        r"(?=━━|### AI & Compute|### Engineering Deep Dive|### The Engineering Angle|$)"
    ),
    "ai_compute": (
        r"(?:### AI & Compute)"
        r"(.*?)"
        r"(?=━━|### Engineering Deep Dive|### The Engineering Angle|$)"
    ),
    "deep_dive": (
        r"(?:### Engineering Deep Dive|### The Engineering Angle)"
        r"(.*?)"
        r"(?=━━|### Market Watch|$)"
    ),
}


# Registry mapping show slugs to their section patterns.
# New shows should be added here to enable cross-episode content tracking.
SHOW_SECTION_PATTERNS: Dict[str, Dict[str, str]] = {
    "tesla": TST_SECTION_PATTERNS,
    "tesla_shorts_time": TST_SECTION_PATTERNS,
    "fascinating_frontiers": FF_SECTION_PATTERNS,
    "planetterrian": PT_SECTION_PATTERNS,
    "omni_view": OV_SECTION_PATTERNS,
    "env_intel": EI_SECTION_PATTERNS,
    "models_agents": MA_SECTION_PATTERNS,
    "models_agents_beginners": MAB_SECTION_PATTERNS,
    "finansy_prosto": FP_SECTION_PATTERNS,
    "privet_russian": PR_SECTION_PATTERNS,
    "modern_investing": MI_SECTION_PATTERNS,
    "unintended_consequences": UC_SECTION_PATTERNS,
    "spacex": SPACEX_SECTION_PATTERNS,
}


# Slur/profanity fragments that must never enter the tracker: recorded
# headlines are committed to git, publicly fetchable via GitHub Pages,
# and re-injected into every digest prompt as "recently covered stories".
_TITLE_BLOCKLIST = ("retard", "nigger", "faggot", "tranny", "kike", "spic")


def _is_dedupe_worthy_title(title: str) -> bool:
    """Filter junk out of titles recorded for cross-episode dedup.

    June 2026: raw fetched X/Reddit post titles like "Laughing Emojis
    🤣🤣", "Video post", and worse ("NY is full of liberal retards 🤣")
    were being merged into the tracker via ``source_titles`` — polluting
    a public JSON and the daily prompt. A title needs at least three
    alphabetic words to carry any dedup signal, and slurs are dropped
    unconditionally.
    """
    if not title:
        return False
    if len(re.findall(r"[A-Za-z]{2,}", title)) < 3:
        return False
    lowered = title.lower()
    if any(p in lowered for p in _TITLE_BLOCKLIST):
        return False
    return True


def _extract_bold_headlines(text: str, max_items: int = 20) -> List[str]:
    """Extract headlines from a digest section.

    Tries bold-formatted headlines first (``**text**``).  Falls back to
    numbered list items (``1. text``) and markdown header lines
    (``### text``) so that cross-episode dedup works regardless of the
    LLM's formatting choices.
    """
    headlines: List[str] = []

    # Primary: bold-formatted headlines
    for m in re.finditer(r"\*{2}([^*]{10,})\*{2}", text):
        t = m.group(1).strip()
        if t and len(t) > 15 and t not in headlines:
            headlines.append(t)
        if len(headlines) >= max_items:
            return headlines

    # Fallback 1: numbered list items  (e.g. "1. Some headline text")
    if not headlines:
        for m in re.finditer(r"^\s*\d{1,2}\.\s+(.{15,})", text, re.MULTILINE):
            t = m.group(1).strip().rstrip(".")
            # Strip residual markdown bold if partially formatted
            t = re.sub(r"\*{1,2}", "", t).strip()
            if t and t not in headlines:
                headlines.append(t)
            if len(headlines) >= max_items:
                return headlines

    # Fallback 2: markdown sub-headers  (### Headline)
    if not headlines:
        for m in re.finditer(r"^#{2,4}\s+(.{15,})", text, re.MULTILINE):
            t = m.group(1).strip()
            if t and t not in headlines:
                headlines.append(t)
            if len(headlines) >= max_items:
                return headlines

    # Fallback 3: pure prose sections (e.g. MAB's "The Big Story" — no
    # bold, no numbered list, no sub-headers, just a paragraph). Use
    # the first substantive sentence as a topic signature so cross-
    # episode dedup catches "we covered this story yesterday" via
    # proper-noun overlap. Operator caught (MAB Ep031, May 7 2026)
    # the LLM retelling the Perplexity Personal Computer story in
    # blocks 2 AND 4 of the same episode — cross-episode dedup
    # silently missed yesterday's mention because The Big Story
    # extracts to zero headlines.
    if not headlines:
        # Strip leading list markers / metadata lines that aren't real
        # prose; first sentence ending in . ! ? wins.
        cleaned = re.sub(r"^\s*(\d+\.\s+|[-*]\s+)", "", text, flags=re.MULTILINE)
        sentence_match = re.search(r"([A-ZА-Я][^.!?\n]{30,200}[.!?])", cleaned)
        if sentence_match:
            t = sentence_match.group(1).strip()
            # Strip inline markdown that survived (bold, italic, code).
            t = re.sub(r"[*_`]+", "", t).strip()
            if t and t not in headlines:
                headlines.append(t)

    if not headlines:
        logger.warning(
            "Could not extract any headlines from digest section (%d chars). "
            "Cross-episode dedup may miss repeated stories.",
            len(text),
        )

    return headlines


def _normalize_url_for_dedup(url: str) -> str:
    """Strip query params, fragments, trailing slashes, and protocol for URL-based dedup.

    Different sources may syndicate the same story under different UTM
    parameters, http vs https, or with/without trailing slashes.
    We compare netloc + path only, lowercased and normalized.
    """
    from urllib.parse import urlparse

    p = urlparse(url.strip().lower())
    # Strip 'www.' prefix so www.example.com and example.com match
    netloc = p.netloc.removeprefix("www.")
    return (netloc + p.path).rstrip("/")


def _extract_deep_dive_topic(text: str) -> Optional[str]:
    """Extract the topic from a deep-dive section for cross-episode dedup.

    Looks for common patterns like:
    - "### Deep Dive: Topic Name"
    - "### Explain Like I'm 14: How X Works"
    - "**The Fundamental Question:** ..."
    - First meaningful header or bold text after the section marker
    """
    # Pattern 1: "### Section Title: Topic" or "## Section Title: Topic"
    m = re.search(
        r"#{2,4}\s+[^:\n]+:\s*(.{10,120})",
        text,
    )
    if m:
        topic = m.group(1).strip().rstrip(".")
        # Strip trailing source references
        topic = re.sub(r"\s*Source:.*$", "", topic, flags=re.IGNORECASE)
        if len(topic) > 10:
            return topic

    # Pattern 2: "**The Fundamental Question:**" (TST First Principles style)
    m = re.search(r"\*\*(?:The )?Fundamental Question:\*\*\s*(.{10,200})", text)
    if m:
        return m.group(1).strip().rstrip("?").strip()[:120]

    # Pattern 3: First bold text in the section (likely the topic name)
    m = re.search(r"\*\*([^*]{10,100})\*\*", text)
    if m:
        candidate = m.group(1).strip()
        # Skip generic labels
        if not re.match(r"(?:HOOK|Date|Source|What|Why|How)\b", candidate, re.IGNORECASE):
            return candidate[:120]

    return None


def _extract_quote_author(text: str) -> Optional[str]:
    """Extract the author from a quote section."""
    # Match: "quote text" – Author Name  or  quote text – Author Name
    m = re.search(r'["""]?[^"""\n]+["""]?\s*[–—-]\s*([A-Z][^\n,]{2,40})', text)
    if m:
        return m.group(1).strip()
    return None


class ContentTracker:
    """Per-show cross-episode content tracker.

    Maintains a JSON file tracking:
    - headlines: news story headlines from recent episodes
    - section content: spotlight topics, short spots, quotes, challenges
    - quote authors: to enforce author diversity
    """

    def __init__(
        self,
        show_slug: str,
        output_dir: Path,
        max_days: int = 14,
        quote_author_cooldown_days: int = 30,
    ):
        self.show_slug = show_slug
        self.output_dir = Path(output_dir)
        self.max_days = max_days
        self.quote_author_cooldown_days = quote_author_cooldown_days
        self.tracker_file = self.output_dir / f"{show_slug}_content_tracker.json"
        self.data: Dict = {
            "show": show_slug,
            "last_updated": None,
            "episodes": [],
        }

    def load(self) -> None:
        """Load tracker from JSON file with shared lock."""
        if self.tracker_file.exists():
            try:
                with open(self.tracker_file, "r", encoding="utf-8") as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    try:
                        loaded = json.load(f)
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                if isinstance(loaded, dict) and "episodes" in loaded:
                    self.data = loaded
                    self._prune_old_episodes()
                    ep_count = len(self.data["episodes"])
                    logger.info(
                        "Loaded content tracker for '%s': %d episodes tracked",
                        self.show_slug,
                        ep_count,
                    )
                    if ep_count == 0:
                        logger.warning(
                            "Content tracker for '%s' has ZERO episodes — "
                            "cross-episode dedup is effectively DISABLED. "
                            "All articles will pass through without "
                            "repetition checks.",
                            self.show_slug,
                        )
                    return
            except Exception as e:
                logger.warning("Failed to load content tracker for %s: %s", self.show_slug, e)
        logger.info("Starting fresh content tracker for '%s'", self.show_slug)

    def save(self) -> None:
        """Persist tracker to JSON file with file locking.

        Uses ``fcntl.flock()`` to prevent concurrent writes from
        parallel show runs corrupting the tracker JSON.
        """
        self._prune_old_episodes()
        self.data["last_updated"] = datetime.date.today().isoformat()
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            with open(self.tracker_file, "w", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(self.data, f, indent=2, ensure_ascii=False)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            logger.info("Saved content tracker to %s", self.tracker_file)
        except Exception as e:
            logger.error("Failed to save content tracker: %s", e)

    def _prune_old_episodes(self) -> None:
        """Remove episodes older than max_days."""
        cutoff = (datetime.date.today() - datetime.timedelta(days=self.max_days)).isoformat()
        self.data["episodes"] = [
            ep for ep in self.data["episodes"]
            if ep.get("date", "") >= cutoff
        ]

    # ----- Querying recent content -----

    def get_recent_headlines(self, days: Optional[int] = None) -> List[str]:
        """Return headlines from recent episodes for cross-day dedup."""
        cutoff = (
            datetime.date.today() - datetime.timedelta(days=days or self.max_days)
        ).isoformat()
        headlines = []
        for ep in self.data["episodes"]:
            if ep.get("date", "") >= cutoff:
                headlines.extend(ep.get("headlines", []))
        return headlines

    def get_recent_urls(self, days: Optional[int] = None) -> set:
        """Return normalized article URLs from recent episodes."""
        cutoff = (
            datetime.date.today() - datetime.timedelta(days=days or self.max_days)
        ).isoformat()
        urls: set = set()
        for ep in self.data["episodes"]:
            if ep.get("date", "") >= cutoff:
                for u in ep.get("urls", []):
                    norm = _normalize_url_for_dedup(u)
                    if norm:
                        urls.add(norm)
        return urls

    def get_recent_quote_authors(self, window_days: int = 30) -> List[str]:
        """Return quote authors used within the window."""
        cutoff = (datetime.date.today() - datetime.timedelta(days=window_days)).isoformat()
        authors = []
        for ep in self.data["episodes"]:
            if ep.get("date", "") >= cutoff:
                author = ep.get("quote_author")
                if author:
                    authors.append(author)
        return authors

    def get_recent_section_content(self, section_key: str, max_items: int = 7) -> List[str]:
        """Return recent content for a named section (e.g., 'cosmic_spotlight')."""
        items = []
        for ep in reversed(self.data["episodes"]):
            content = ep.get("sections", {}).get(section_key)
            if content:
                items.append(content[:500])
            if len(items) >= max_items:
                break
        return items

    def get_recent_deep_dive_topics(self, max_items: int = 14) -> List[str]:
        """Return deep dive topics from recent episodes for freshness enforcement.

        Looks for a ``deep_dive_topic`` field on each episode record (set by
        ``record_episode`` when a deep-dive section pattern matches).
        """
        topics: List[str] = []
        for ep in reversed(self.data["episodes"]):
            topic = ep.get("deep_dive_topic")
            if topic:
                topics.append(topic)
            if len(topics) >= max_items:
                break
        return topics

    def get_recent_segment_ids(self, days: Optional[int] = None) -> List[str]:
        """Return slow-news segment IDs used in recent episodes.

        IDs are returned in chronological order (oldest first) so that
        ``select_segments()`` can pick least-recently-used when all are
        on cooldown.
        """
        cutoff = (
            datetime.date.today()
            - datetime.timedelta(days=days or self.max_days)
        ).isoformat()
        ids: List[str] = []
        for ep in self.data["episodes"]:
            if ep.get("date", "") >= cutoff:
                ids.extend(ep.get("slow_news_segments", []))
        return ids

    def get_segment_history(
        self, segment_id: str, limit: int = 3
    ) -> List[Dict]:
        """Return past usages of a specific evergreen segment.

        Each entry is ``{"date": "...", "summary": "..."}``, ordered
        most-recent-first.  Used by ``build_slow_news_prompt_context()``
        to inform the LLM of previous angles so it generates fresh content.
        """
        results: List[Dict] = []
        for ep in reversed(self.data["episodes"]):
            seg_ids = ep.get("slow_news_segments", [])
            if segment_id in seg_ids:
                summaries = ep.get("slow_news_segment_summaries", {})
                summary = summaries.get(segment_id, "")
                results.append({
                    "date": ep.get("date", ""),
                    "summary": summary,
                })
                if len(results) >= limit:
                    break
        return results

    def get_summary_for_prompt(self, limits: Optional[Dict[str, int]] = None) -> str:
        """Generate a 'RECENTLY USED...' block for inclusion in the Grok prompt.

        This tells Grok what was used recently so it can avoid repetition.
        """
        if not limits:
            limits = {}

        parts = []

        # Recent headlines
        recent_headlines = self.get_recent_headlines(days=3)
        if recent_headlines:
            hl_limit = limits.get("headlines", 40)
            hl_text = "\n".join(f"- {h[:120]}" for h in recent_headlines[-hl_limit:])
            parts.append(
                f"RECENTLY COVERED NEWS STORIES (DO NOT repeat these — pick DIFFERENT stories):\n{hl_text}"
            )

        # Recent quote authors
        recent_authors = self.get_recent_quote_authors(window_days=self.quote_author_cooldown_days)
        if recent_authors:
            auth_text = ", ".join(set(recent_authors))
            parts.append(
                f"RECENTLY USED QUOTE AUTHORS (use a DIFFERENT author): {auth_text}"
            )

        # Section-specific content
        section_labels = {
            "short_spot": "SHORT SPOTS",
            "first_principles": "FIRST PRINCIPLES TOPICS",
            "daily_challenge": "DAILY CHALLENGES",
            "cosmic_spotlight": "COSMIC SPOTLIGHT TOPICS",
            "planetterrian_spotlight": "PLANETTERRIAN SPOTLIGHT TOPICS",
            "regulatory_watch": "REGULATORY & POLICY WATCH TOPICS",
            "science_technical": "SCIENCE & TECHNICAL TOPICS",
            "industry_practice": "INDUSTRY & PRACTICE TOPICS",
            "explain_like_14": "EXPLAIN LIKE I'M 14 TOPICS",
            "counterpoint": "COUNTERPOINT TOPICS",
            "ai_compute": "AI & COMPUTE TOPICS",
        }
        for key, label in section_labels.items():
            items = self.get_recent_section_content(key, max_items=limits.get(key, 7))
            if items:
                items_text = "\n".join(f"- {item[:200]}..." for item in items)
                parts.append(
                    f"RECENTLY USED {label} (DO NOT REPEAT — create something COMPLETELY DIFFERENT):\n{items_text}"
                )

        # Deep dive topic tracking (applies to all shows with a deep dive section)
        deep_dive_topics = self.get_recent_deep_dive_topics(max_items=14)
        if deep_dive_topics:
            topics_text = "\n".join(f"- {t}" for t in deep_dive_topics)
            parts.append(
                f"RECENTLY USED DEEP DIVE TOPICS (DO NOT REPEAT — choose a COMPLETELY DIFFERENT topic):\n{topics_text}"
            )

        # Recently used evergreen segments (slow-news mode)
        recent_segs = self.get_recent_segment_ids(days=30)
        if recent_segs:
            segs_text = ", ".join(recent_segs)
            parts.append(
                f"RECENTLY USED EVERGREEN SEGMENTS (DO NOT REPEAT): {segs_text}"
            )

        if parts:
            return (
                "\n\n".join(parts)
                + "\n\nCRITICAL: Generate COMPLETELY NEW, FRESH content for ALL sections. "
                "Avoid ANY similarity to the above.\n"
            )
        return ""

    def filter_recent_articles(
        self,
        articles: List[Dict],
        similarity_threshold: float = 0.65,
        days: Optional[int] = None,
        url_days: Optional[int] = None,
    ) -> List[Dict]:
        """Filter out articles that are too similar to recently covered stories.

        Uses two complementary checks:
        1. **URL match** — exact normalized-URL match means the *same article*
           was re-fetched (publishers keep stories in their RSS feed for days,
           so the same URL re-surfaces). This has zero false-positive risk, so
           it uses a WIDER window (``url_days``, default 7 — matching the
           validation-time cross-episode check ``get_recent_headlines(days=7)``).
           Previously this used the same narrow 3-day window as title
           similarity, so a story lingering in a feed for 4-7 days re-shipped
           and was only caught (non-blocking) at validation. (FF Ep087.)
        2. **Title similarity** — fuzzy, so it stays on the narrower ``days``
           window to avoid dropping legitimately-distinct follow-up stories.

        More aggressive than the in-episode dedup (0.85 threshold) because
        cross-episode repetition is more noticeable to listeners.
        """
        day_window = days or 3
        url_window = url_days or max(day_window, 7)
        recent_headlines = self.get_recent_headlines(days=day_window)
        recent_urls = self.get_recent_urls(days=url_window)

        if (not recent_headlines and not recent_urls) or not articles:
            return articles

        recent_norm = [norm_headline_for_similarity(h) for h in recent_headlines if h]
        filtered = []
        url_dropped = 0
        title_dropped = 0
        for article in articles:
            # URL-based check (exact path match ignoring query params)
            article_url = (article.get("url") or "").strip()
            if article_url and recent_urls:
                norm_url = _normalize_url_for_dedup(article_url)
                if norm_url and norm_url in recent_urls:
                    url_dropped += 1
                    logger.debug(
                        "Filtering article by URL match: %s...", article_url[:80]
                    )
                    continue

            title = (article.get("title") or "").strip()
            if not title:
                filtered.append(article)
                continue
            norm_title = norm_headline_for_similarity(title)
            is_repeat = False
            for r in recent_norm:
                if not r:
                    continue
                if calculate_similarity(norm_title, r) >= similarity_threshold:
                    is_repeat = True
                    title_dropped += 1
                    logger.debug(
                        "Filtering recently-covered article: %s...", title[:60]
                    )
                    break
            if not is_repeat:
                filtered.append(article)

        dropped = url_dropped + title_dropped
        if dropped:
            logger.info(
                "Filtered %d articles similar to recently covered stories "
                "(%d by URL ≤%dd, %d by title ≤%dd)",
                dropped, url_dropped, url_window, title_dropped, day_window,
            )
        return filtered

    # ----- Recording new episodes -----

    def record_episode(
        self,
        digest_text: str,
        section_patterns: Dict[str, str],
        date: Optional[str] = None,
        source_urls: Optional[List[str]] = None,
        source_titles: Optional[List[str]] = None,
    ) -> None:
        """Extract and record content from a generated digest.

        Multiple episodes on the same date are supported: headlines are
        *merged* (not replaced) so that same-day re-runs don't lose the
        earlier episode's dedup context.

        Args:
            digest_text: The full digest markdown text.
            section_patterns: Dict mapping section names to regex patterns.
            date: Episode date (ISO format). Defaults to today.
            source_urls: Original article URLs from RSS/X fetcher (optional).
                Supplements URLs extracted from the digest text, ensuring
                URL-based dedup works even when the LLM omits source links.
            source_titles: Original article titles from RSS/X fetcher (optional).
                Supplements headlines extracted from the digest, ensuring
                title-based dedup works even when the LLM reformats headlines.
        """
        ep_date = date or datetime.date.today().isoformat()

        episode_record: Dict = {
            "date": ep_date,
            "headlines": [],
            "urls": [],
            "quote_author": None,
            "sections": {},
        }

        # Extract source URLs from the digest for URL-based dedup
        for url_match in re.finditer(r"Source:\s*(https?://[^\s)\]]+)", digest_text):
            url = url_match.group(1).strip().rstrip(",.")
            if url:
                episode_record["urls"].append(url)

        # Merge in original article URLs from the fetcher (more reliable
        # than extracting from digest text, which depends on LLM formatting).
        if source_urls:
            existing = set(episode_record["urls"])
            for u in source_urls:
                if u and u not in existing:
                    episode_record["urls"].append(u)
                    existing.add(u)

        # Extract headlines
        headlines_pattern = section_patterns.get("headlines")
        if headlines_pattern:
            m = re.search(headlines_pattern, digest_text, re.DOTALL | re.IGNORECASE)
            if m:
                episode_record["headlines"] = _extract_bold_headlines(m.group(1))

        # Also extract takeover headlines (TST-specific)
        takeover_pattern = section_patterns.get("takeover_headlines")
        if takeover_pattern:
            m = re.search(takeover_pattern, digest_text, re.DOTALL | re.IGNORECASE)
            if m:
                episode_record["headlines"].extend(_extract_bold_headlines(m.group(1)))

        # Merge in original RSS article titles for more reliable title-based
        # cross-episode dedup (LLM-extracted headlines can be reformatted or
        # include timestamps, making similarity matching unreliable).
        if source_titles:
            existing_norm = {
                norm_headline_for_similarity(h)
                for h in episode_record["headlines"] if h
            }
            for t in source_titles:
                if not _is_dedupe_worthy_title(t):
                    continue
                if norm_headline_for_similarity(t) not in existing_norm:
                    episode_record["headlines"].append(t)
                    existing_norm.add(norm_headline_for_similarity(t))

        # Extract named sections
        for key, pattern in section_patterns.items():
            if key in ("headlines", "takeover_headlines"):
                continue

            m = re.search(pattern, digest_text, re.DOTALL | re.IGNORECASE)
            if m:
                content = m.group(0).strip()[:500]
                episode_record["sections"][key] = content

                # Special handling for quote/inspiration sections
                if "quote" in key or "inspiration" in key:
                    author = _extract_quote_author(m.group(0))
                    if author:
                        episode_record["quote_author"] = author

                # Extract deep dive topic from deep-dive-style sections
                if "deep_dive" in key or "first_principles" in key or "explain_like" in key:
                    topic = _extract_deep_dive_topic(m.group(0))
                    if topic:
                        episode_record["deep_dive_topic"] = topic

        # Merge with existing same-date entry instead of replacing it.
        # This ensures multiple same-day runs accumulate headlines for
        # cross-episode dedup rather than losing earlier episodes' data.
        existing = [ep for ep in self.data["episodes"] if ep.get("date") == ep_date]
        if existing:
            prev = existing[0]
            prev_headlines = set(prev.get("headlines", []))
            for h in episode_record["headlines"]:
                if h not in prev_headlines:
                    prev["headlines"].append(h)
            # Merge URLs
            prev_urls = set(prev.get("urls", []))
            if "urls" not in prev:
                prev["urls"] = list(prev_urls)
            for u in episode_record.get("urls", []):
                if u not in prev_urls:
                    prev["urls"].append(u)
            # Keep sections from the latest run (most current)
            prev["sections"].update(episode_record["sections"])
            if episode_record["quote_author"]:
                prev["quote_author"] = episode_record["quote_author"]
            logger.info(
                "Merged same-day episode %s: now %d headlines, %d urls, %d sections",
                ep_date,
                len(prev["headlines"]),
                len(prev.get("urls", [])),
                len(prev["sections"]),
            )
        else:
            self.data["episodes"].append(episode_record)
            logger.info(
                "Recorded episode %s: %d headlines, %d sections, quote by %s",
                ep_date,
                len(episode_record["headlines"]),
                len(episode_record["sections"]),
                episode_record["quote_author"] or "unknown",
            )

    def check_quote_reuse(self, quote_text: str, window_days: int = 30) -> bool:
        """Check if a quote's author has been used within the window.

        Returns True if the author has been used recently (i.e., it's a repeat).
        """
        author = _extract_quote_author(quote_text)
        if not author:
            return False

        recent_authors = self.get_recent_quote_authors(window_days)
        for recent_author in recent_authors:
            if calculate_similarity(author.lower(), recent_author.lower()) >= 0.8:
                logger.debug("Quote author '%s' reused (similar to '%s')", author, recent_author)
                return True
        return False
