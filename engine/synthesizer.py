"""Content Synthesizer — Produces derivative content products from the Content Lake.

Weekly newsletters, monthly reports, cross-show briefings, and topic guides.
All synthesis uses the existing ``_call_grok()`` LLM interface from
``engine.generator``.
"""

from __future__ import annotations

import calendar
import json
import logging
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.content_lake import query_all_shows_range, query_show_range
from engine.generator import _call_grok

logger = logging.getLogger(__name__)


# Envelope schema returned by synthesize_weekly_newsletter:
#
#   {
#       "subject_hook": str,             # <=50 char one-liner for subject prefix
#       "preheader": str,                # 90-110 char inbox preview teaser
#       "by_the_numbers": [              # 0-3 stat tiles, optional per show
#           {"value": "$372.80", "label": "TSLA close"},
#           ...
#       ],
#       "body_md": str,                  # the full markdown digest body
#       "p_s": str,                      # one-sentence P.S. closer
#   }
#
# Callers (run_weekly_newsletters.py) consume this dict directly and pass each
# field into the email template. If the LLM call fails or returns malformed
# JSON, _parse_envelope falls back to wrapping the raw text in body_md and
# synthesizing the other fields from show metadata so the send still goes out.

_ENVELOPE_INSTRUCTIONS = """\

## OUTPUT FORMAT (REQUIRED)

Return your response as a single JSON object with exactly this schema. Do \
NOT wrap it in markdown code fences. Do NOT include any prose outside the \
JSON. Output the JSON object and nothing else.

{{
  "subject_hook": "<=50 chars; the single most newsworthy hook of the week, \
no clickbait, no show name (we add it). Example: 'Cybercab production begins'>",
  "preheader": "<90-110 chars; inbox preview teaser, complete sentence, \
gives the reader a reason to open. Example: 'Cybercab rolls off the line in \
Texas, Semi hits mass production, and the FSD v14 wave is coming.'>",
  "by_the_numbers": [
    {{"value": "<short stat>", "label": "<label>"}},
    {{"value": "<short stat>", "label": "<label>"}},
    {{"value": "<short stat>", "label": "<label>"}}
  ],
  "body_md": "<the full weekly newsletter markdown — all sections required \
above, formatted as markdown. Do NOT repeat the show title at the top \
(the email template already shows it). Start the body directly with the \
first content section. Target word count: {target_words} words.>",
  "p_s": "<one sentence; a personal aside, recommendation, or call to \
action. Example: 'If you've been on the fence about FSD v14, this is \
the week to grab the trial.'>"
}}

If you have fewer than 3 quantitative stats worth surfacing, return an empty \
array for by_the_numbers (do not invent numbers). All other fields are required.
"""


def _strip_repeated_show_title(body_md: str, show_name: str) -> str:
    """Drop a leading ``**<Show> Weekly**`` / ``# <Show>`` line if the LLM
    repeats the show title at the top of the body.

    The branded hero already shows the title in big text, so a body that
    opens with the title again is visual duplication. We only strip the
    very first non-empty line if it matches the show name pattern.
    """
    if not body_md:
        return body_md
    lines = body_md.lstrip().split("\n")
    # The first non-blank line is what we examine.
    first = lines[0].strip()
    show_lower = show_name.lower().strip()
    # Patterns: "# <Show>", "## <Show>", "**<Show> Weekly**", etc.
    norm = re.sub(r"^[#*\s_]+|[#*\s_]+$", "", first).lower().strip()
    norm = re.sub(r"\s+(weekly|weekly digest|digest)$", "", norm).strip()
    if norm == show_lower or norm.startswith(show_lower + " "):
        return "\n".join(lines[1:]).lstrip()
    return body_md


def _parse_envelope(
    raw_text: str, *, show_name: str, week_ending: date
) -> Dict[str, Any]:
    """Parse the LLM JSON envelope; fall back to wrapping raw markdown.

    Robust against:
      - extra prose before/after the JSON
      - markdown ``` fences around the JSON
      - the LLM returning plain markdown (no JSON at all)
    """
    fallback_subject = f"This week on {show_name}"
    fallback_preheader = (
        f"Your weekly digest from {show_name} — top stories, trends, and "
        f"what to watch next week."
    )[:160]
    fallback_p_s = ""

    if not raw_text or not raw_text.strip():
        return {
            "subject_hook": fallback_subject,
            "preheader": fallback_preheader,
            "by_the_numbers": [],
            "body_md": "",
            "p_s": fallback_p_s,
        }

    text = raw_text.strip()
    # Strip ```json ... ``` fences if the model added them despite instructions.
    fence_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL
    )
    if fence_match:
        text = fence_match.group(1)

    # Try direct parse, then a fallback that grabs the first {...} block.
    parsed: Optional[Dict[str, Any]] = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            try:
                parsed = json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                parsed = None

    if not isinstance(parsed, dict) or "body_md" not in parsed:
        # The LLM ignored the envelope instruction and returned plain
        # markdown. Wrap it so the send still works; downstream code
        # only ever reads keys, so missing optional fields are fine.
        logger.warning(
            "[Synthesizer] LLM did not return JSON envelope, wrapping "
            "raw markdown (len=%d)", len(raw_text),
        )
        return {
            "subject_hook": fallback_subject,
            "preheader": fallback_preheader,
            "by_the_numbers": [],
            "body_md": _strip_repeated_show_title(raw_text, show_name),
            "p_s": fallback_p_s,
        }

    # Coerce + sanitize each field.
    subject_hook = str(parsed.get("subject_hook") or fallback_subject).strip()
    # Hard cap at 60 chars even though we ask for 50; subject lines have
    # client-level limits and the template appends show short + emoji.
    subject_hook = subject_hook[:60].rstrip(" .,;:")

    preheader = str(parsed.get("preheader") or fallback_preheader).strip()
    preheader = preheader[:160]

    btn_raw = parsed.get("by_the_numbers") or []
    by_the_numbers: List[Dict[str, str]] = []
    if isinstance(btn_raw, list):
        # Filter malformed items first so a sloppy LLM that emits
        # ``[{}, {}, {}, {real}]`` still surfaces the real one;
        # then cap at 3.
        for item in btn_raw:
            if len(by_the_numbers) >= 3:
                break
            if not isinstance(item, dict):
                continue
            value = str(item.get("value") or "").strip()
            label = str(item.get("label") or "").strip()
            if value and label:
                by_the_numbers.append({"value": value[:24], "label": label[:32]})

    body_md = str(parsed.get("body_md") or "").strip()
    body_md = _strip_repeated_show_title(body_md, show_name)

    p_s = str(parsed.get("p_s") or "").strip()
    # Strip a leading "P.S." if the LLM added one — the template
    # renders the label itself.
    p_s = re.sub(r"^p\.?\s*s\.?\s*[—–\-:]?\s*", "", p_s, flags=re.IGNORECASE)
    p_s = p_s[:280]

    return {
        "subject_hook": subject_hook,
        "preheader": preheader,
        "by_the_numbers": by_the_numbers,
        "body_md": body_md,
        "p_s": p_s,
    }


def _load_config_safe(show_slug: str, config_path: Optional[Path] = None):
    """Load a show config, returning None on failure."""
    from engine.config import load_config

    try:
        path = str(config_path) if config_path else f"shows/{show_slug}.yaml"
        return load_config(path)
    except Exception as e:
        logger.warning("Failed to load config for %s: %s", show_slug, e)
        return None


def _network_synth_defaults() -> tuple[str, int, float]:
    """Return (model, max_tokens, temperature) for network-level synthesis.

    Reads ``shows/_defaults.yaml`` directly — this path is network-wide
    (cross-show briefing), not tied to any single show.
    """
    import yaml

    model = "grok-4.20-reasoning"
    max_tokens = 8000
    temperature = 0.4
    defaults_path = Path("shows/_defaults.yaml")
    if defaults_path.exists():
        try:
            with open(defaults_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            llm = data.get("llm") or {}
            model = llm.get("synth_model") or llm.get("model") or model
            max_tokens = int(llm.get("synth_max_tokens") or max_tokens)
            temperature = float(llm.get("synth_temperature") or temperature)
        except Exception as exc:
            logger.warning("Failed to read synth defaults: %s", exc)
    return model, max_tokens, temperature


def _cfg_synth_params(cfg, default_max_tokens: int, default_temperature: float) -> tuple[str, int, float]:
    """Return the per-show synthesiser params, falling back to show's model."""
    llm = getattr(cfg, "llm", None)
    model = getattr(llm, "synth_model", "") or getattr(llm, "model", "") or "grok-4.20-reasoning"
    max_tokens = getattr(llm, "synth_max_tokens", 0) or default_max_tokens
    temperature = getattr(llm, "synth_temperature", 0.0) or default_temperature
    return model, max_tokens, temperature


# ---------------------------------------------------------------------------
# Weekly newsletter
# ---------------------------------------------------------------------------

_DEFAULT_WEEKLY_PROMPT = """\
You are the weekly newsletter editor for {show_name}, part of the Nerra Network.

Synthesize this week's {episode_count} episodes (from {start_date} to \
{end_date}) into a compelling weekly newsletter.

## This Week's Episodes:

{episodes_text}

## Key Entities This Week:
{entities}

## Instructions:

Write a weekly newsletter in markdown format with these sections:

1. **This Week's Big Picture** — 2-3 paragraphs summarizing the most \
important themes and developments from the week. Connect the dots between \
stories. What's the narrative arc?

2. **Top Stories** — The 5 most important stories from the week, each with \
a 2-3 sentence summary and why it matters.

3. **Trend Watch** — 2-3 emerging trends you noticed across this week's \
coverage. What patterns are forming?

4. **Quick Hits** — 5-8 smaller stories worth knowing about, each in one \
sentence.

5. **What to Watch Next Week** — 2-3 things to keep an eye on based on \
this week's developments.

Write in an engaging, informed tone. This is for subscribers who want the \
week's highlights without listening to every episode. Keep the total length \
under 1500 words.

End with a brief sign-off that encourages the reader to share the newsletter \
with someone who would enjoy it, and remind them they can listen to full \
episodes at nerranetwork.com. Keep it natural and brief — one sentence, \
not a hard sell."""


def synthesize_weekly_newsletter(
    show_slug: str,
    week_ending: date,
    *,
    config_path: Optional[Path] = None,
    prompt_file: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Generate a weekly newsletter for a show from the past 7 days.

    Returns an envelope dict (see module docstring) with ``subject_hook``,
    ``preheader``, ``by_the_numbers``, ``body_md``, and ``p_s`` keys, or
    ``None`` if insufficient data.

    Older callers that expect a plain markdown string should read
    ``envelope["body_md"]``.
    """
    start_date = (week_ending - timedelta(days=6)).isoformat()
    end_date = week_ending.isoformat()

    episodes = query_show_range(show_slug, start_date, end_date)
    if len(episodes) < 2:
        logger.warning(
            "[Synthesizer] Only %d episodes for %s week of %s, skipping",
            len(episodes), show_slug, end_date,
        )
        return None

    cfg = _load_config_safe(show_slug, config_path)
    if not cfg:
        return None

    # Build context from episodes
    episode_summaries = []
    all_entities: set[str] = set()

    for ep in episodes:
        episode_summaries.append(
            f"### Episode {ep['episode_num']} — {ep['date']}\n"
            f"**Hook:** {ep.get('hook', 'N/A')}\n\n"
            f"{ep.get('digest_md', '')[:2000]}"
        )
        all_entities.update(ep.get("entities", []))

    episodes_text = "\n\n---\n\n".join(episode_summaries)

    # Cross-show highlights: top stories from OTHER shows this week that
    # subscribers of THIS show might find interesting. This is a key
    # cross-promotion mechanism for the network.
    cross_show_section = ""
    try:
        all_shows_eps = query_all_shows_range(start_date, end_date)
        other_shows = [
            ep for ep in all_shows_eps
            if ep.get("show_slug") != show_slug and ep.get("hook")
        ]
        if other_shows:
            highlights = other_shows[:5]
            cross_lines = []
            for ep in highlights:
                show_label = ep.get("show_name") or ep.get("show_slug", "")
                hook = (ep.get("hook") or "")[:120]
                cross_lines.append(f"- **{show_label}**: {hook}")
            cross_show_section = (
                "\n\n## From the Nerra Network This Week\n"
                "Other shows in the network covered these notable stories:\n"
                + "\n".join(cross_lines)
            )
    except Exception as exc:
        logger.debug("Cross-show highlights failed: %s", exc)

    # Load show-specific or default prompt
    if prompt_file and prompt_file.exists():
        prompt_template = prompt_file.read_text(encoding="utf-8")
    else:
        prompt_template = _DEFAULT_WEEKLY_PROMPT

    show_name = getattr(cfg.publishing, "rss_title", show_slug)

    # Per-show length target (defaults to 1300 — see _defaults.yaml).
    nl_cfg = getattr(cfg, "newsletter", None)
    target_words = int(getattr(nl_cfg, "length_target_words", 0) or 1300)

    body_prompt = prompt_template.format(
        show_name=show_name,
        episode_count=len(episodes),
        start_date=start_date,
        end_date=end_date,
        episodes_text=episodes_text + cross_show_section,
        entities=", ".join(sorted(all_entities)[:30]),
    )
    # Append the JSON envelope output instructions. We do this after
    # the per-show prompt so the editorial guidance still drives the
    # body content; the envelope is a shape constraint, not a rewrite.
    prompt = body_prompt + _ENVELOPE_INSTRUCTIONS.format(
        target_words=target_words
    )

    system_prompt = (
        f"You are the weekly newsletter editor for {show_name}, "
        f"part of the Nerra Network podcast network. You always return "
        f"output as a single valid JSON object matching the schema in "
        f"the user prompt."
    )

    synth_model, synth_max_tokens, synth_temperature = _cfg_synth_params(
        cfg, default_max_tokens=cfg.llm.max_tokens, default_temperature=0.5,
    )
    try:
        text, meta = _call_grok(
            prompt=prompt,
            model=synth_model,
            temperature=synth_temperature,
            max_tokens=synth_max_tokens,
            system_prompt=system_prompt,
        )
        envelope = _parse_envelope(
            text, show_name=show_name, week_ending=week_ending
        )
        logger.info(
            "[Synthesizer] Weekly newsletter for %s: subject=%r body=%d chars "
            "p_s=%d chars stats=%d (model=%s)",
            show_slug, envelope["subject_hook"], len(envelope["body_md"]),
            len(envelope["p_s"]), len(envelope["by_the_numbers"]), synth_model,
        )
        return envelope
    except Exception as e:
        logger.error(
            "[Synthesizer] Weekly newsletter failed for %s: %s",
            show_slug, e,
        )
        return None


# ---------------------------------------------------------------------------
# Monthly report
# ---------------------------------------------------------------------------

def synthesize_monthly_report(
    show_slug: str,
    month: int,
    year: int,
    *,
    config_path: Optional[Path] = None,
) -> Optional[str]:
    """Generate a monthly "State of..." report for a show.

    Returns markdown text, or ``None`` if insufficient data.
    """
    last_day = calendar.monthrange(year, month)[1]
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{last_day:02d}"

    episodes = query_show_range(show_slug, start_date, end_date)
    if len(episodes) < 5:
        logger.warning(
            "[Synthesizer] Only %d episodes for %s in %d-%02d, skipping",
            len(episodes), show_slug, year, month,
        )
        return None

    cfg = _load_config_safe(show_slug, config_path)
    if not cfg:
        return None

    # Aggregate content
    all_entities: list[str] = []
    all_topics: list[str] = []
    all_hooks: list[str] = []
    episode_digests: list[str] = []

    for ep in episodes:
        all_entities.extend(ep.get("entities", []))
        all_topics.extend(ep.get("topics", []))
        all_hooks.append(
            f"Ep{ep['episode_num']} ({ep['date']}): {ep.get('hook', 'N/A')}"
        )
        episode_digests.append(
            f"**Ep{ep['episode_num']} ({ep['date']}):** "
            f"{ep.get('digest_md', '')[:800]}"
        )

    entity_counts = Counter(all_entities).most_common(20)
    topic_counts = Counter(all_topics).most_common(10)
    month_name = calendar.month_name[month]
    show_name = getattr(cfg.publishing, "rss_title", show_slug)

    next_month = month % 12 + 1
    next_year = year if month < 12 else year + 1
    next_month_name = calendar.month_name[next_month]

    prompt = f"""\
You are writing the monthly report for {show_name}, part of the Nerra Network.

Generate a comprehensive "State of {show_name} — {month_name} {year}" \
report based on {len(episodes)} daily episodes.

## Episode Hooks (chronological):
{chr(10).join(all_hooks)}

## Most Mentioned Entities:
{chr(10).join(f"- {entity}: {count} mentions" for entity, count in entity_counts)}

## Top Topics:
{chr(10).join(f"- {topic}: {count} episodes" for topic, count in topic_counts)}

## Episode Digests (truncated):
{chr(10).join(episode_digests[:15])}

## Instructions:

Write a comprehensive monthly report in markdown with these sections:

# State of {show_name} — {month_name} {year}

## Executive Summary
2-3 paragraphs capturing the month's most important developments and themes.

## Key Events Timeline
A chronological list of the month's most significant events with dates and \
brief descriptions (10-15 events).

## Trend Analysis
3-4 major trends with supporting evidence from the month's coverage. Each \
trend should be 2-3 paragraphs with specific examples and data points.

## Most Active Players
Brief profiles of the entities that dominated the month's news and what \
they did.

## By the Numbers
Key statistics, metrics, and data points from the month's coverage.

## What to Watch in {next_month_name} {next_year}
3-5 things to watch based on the month's developments.

Keep the tone authoritative and analytical. Target 2500-3500 words."""

    system_prompt = (
        f"You are the monthly report editor for {show_name}. "
        f"Write comprehensive, data-driven analysis."
    )

    synth_model, synth_max_tokens, synth_temperature = _cfg_synth_params(
        cfg, default_max_tokens=8000, default_temperature=0.4,
    )
    try:
        text, meta = _call_grok(
            prompt=prompt,
            model=synth_model,
            temperature=synth_temperature,
            max_tokens=synth_max_tokens,
            system_prompt=system_prompt,
        )
        logger.info(
            "[Synthesizer] Monthly report for %s %d-%02d: %d chars (model=%s)",
            show_slug, year, month, len(text), synth_model,
        )
        return text
    except Exception as e:
        logger.error(
            "[Synthesizer] Monthly report failed for %s: %s", show_slug, e,
        )
        return None


# ---------------------------------------------------------------------------
# Cross-show intelligence briefing
# ---------------------------------------------------------------------------

def synthesize_cross_show_briefing(
    week_ending: date,
) -> Optional[str]:
    """Generate a cross-network weekly intelligence briefing.

    Finds connections and themes across all shows.
    """
    start_date = (week_ending - timedelta(days=6)).isoformat()
    end_date = week_ending.isoformat()

    episodes = query_all_shows_range(start_date, end_date)
    if len(episodes) < 10:
        logger.warning(
            "[Synthesizer] Only %d total episodes for cross-show briefing, "
            "skipping", len(episodes),
        )
        return None

    # Group by show and find cross-show entities
    by_show: Dict[str, list] = {}
    entity_show_map: Dict[str, set[str]] = {}

    for ep in episodes:
        show = ep.get("show_name", ep["show_slug"])
        by_show.setdefault(show, []).append(ep)
        for entity in ep.get("entities", []):
            entity_show_map.setdefault(entity, set()).add(show)

    cross_entities = {
        e: shows for e, shows in entity_show_map.items() if len(shows) >= 2
    }

    # Build per-show summaries
    show_sections = []
    for show_name, eps in sorted(by_show.items()):
        hooks = [f"- {ep.get('hook', 'N/A')}" for ep in eps[:5]]
        show_sections.append(
            f"### {show_name} ({len(eps)} episodes)\n{chr(10).join(hooks)}"
        )

    cross_lines = [
        f"- **{entity}** appeared in: {', '.join(sorted(shows))}"
        for entity, shows in sorted(
            cross_entities.items(), key=lambda x: -len(x[1])
        )[:15]
    ]

    prompt = f"""\
You are the editor-in-chief of the Nerra Network, a podcast network with 9 \
daily shows covering AI, Tesla/energy, space, biotech, environmental policy, \
world news, Russian finance, and Russian language learning.

Write the weekly cross-network intelligence briefing for the week of \
{start_date} to {end_date}.

## This Week's Coverage by Show:
{chr(10).join(show_sections)}

## Cross-Show Entity Connections:
{chr(10).join(cross_lines) if cross_lines else "No cross-show entities this week."}

## Instructions:

Write a "Nerra Network Weekly Intelligence" briefing in markdown:

# Nerra Network Weekly Intelligence — Week of {end_date}

## The Big Connections
2-3 paragraphs identifying the most interesting cross-domain threads this \
week. Where do AI developments intersect with energy? How do space \
discoveries relate to biotech? What regulatory moves affect multiple domains?

## Domain Roundup
A brief (3-4 sentence) summary of each show's week, focusing on the single \
most important development per domain.

## Cross-Domain Watch
3-5 emerging stories that span multiple shows' coverage areas.

## The Week Ahead
What to watch across all domains next week.

Keep it under 1200 words. The tone should be sharp, insightful, and focused \
on connections that no single-domain publication would catch."""

    synth_model, synth_max_tokens, synth_temperature = _network_synth_defaults()
    try:
        text, meta = _call_grok(
            prompt=prompt,
            model=synth_model,
            temperature=synth_temperature,
            max_tokens=synth_max_tokens,
            system_prompt=(
                "You are the editor-in-chief of the Nerra Network, an "
                "independent podcast network. You specialize in finding "
                "cross-domain connections."
            ),
        )
        logger.info(
            "[Synthesizer] Cross-show briefing: %d chars (model=%s)",
            len(text), synth_model,
        )
        return text
    except Exception as e:
        logger.error("[Synthesizer] Cross-show briefing failed: %s", e)
        return None
