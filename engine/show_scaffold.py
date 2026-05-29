"""Scaffold a new Nerra Network show — YAML, prompts, dirs, registry snippets."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "shows" / "templates"
DEFAULT_MUSIC = "assets/music/tesla_shorts_time.mp3"


@dataclass
class ScaffoldSpec:
    show_name: str
    slug: str
    description: str
    audience: str
    host_role: str = ""
    content_approach: str = ""
    include_criteria: str = ""
    reject_criteria: str = ""
    value_proposition: str = ""
    host_voice: str = ""
    cadence: str = "daily"
    episode_length: str = "10-12"
    story_count: str = "4-6"
    word_min: int = 1200
    word_max: int = 1600
    analogy_count: int = 4
    episode_prefix: str = ""
    brand_color: str = "#6B47FF"
    brand_color_dark: str = ""
    emoji: str = "🎙️"
    rss_category: str = "Technology"
    schedule_label: str = "Daily"
    weekly_recap: bool = True
    min_articles: int = 3
    min_articles_skip: int = 3
    digest_temperature: float = 0.5
    podcast_temperature: float = 0.7
    max_tokens: int = 4000
    podcast_max_tokens: int = 8000
    min_podcast_words: int = 1200
    length_target_words: int = 1200
    x_enabled: bool = False
    x_env_prefix: str = ""
    related_show: str = "omni_view"
    related_reason: str = ""
    display_order: int = 99
    sources: list[dict[str, str]] = field(default_factory=list)
    web_search_queries: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    image_queries: list[str] = field(default_factory=list)
    cron: str = ""
    cron_day_filter: str | None = None
    youtube_category_id: str = "28"


def slug_to_page(slug: str) -> str:
    return slug.replace("_", "-") + ".html"


def default_episode_prefix(slug: str) -> str:
    parts = slug.split("_")
    if len(parts) == 1:
        return parts[0][:4].upper()
    return "".join(p[:1] for p in parts).upper()[:4]


def default_guid_prefix(slug: str) -> str:
    return slug.replace("_", "")[:12]


def default_short_label(name: str) -> str:
    words = name.split()
    if len(words) <= 3:
        return name
    return " ".join(words[:3])


def _render_percent_template(path: Path, mapping: dict[str, str]) -> str:
    text = path.read_text(encoding="utf-8")
    for key, value in mapping.items():
        text = text.replace(f"%{key}%", value)
    return text


def _format_sources_block(sources: list[dict[str, str]]) -> str:
    if not sources:
        return (
            '  - url: "https://news.google.com/rss/search?q=TOPIC+news&hl=en-US&gl=US&ceid=US:en"\n'
            '    label: Google News (replace query before first run)'
        )
    lines = []
    for s in sources:
        url = s.get("url", "").strip()
        label = s.get("label", "Source")
        if url:
            lines.append(f'  - url: "{url}"')
            lines.append(f"    label: {label}")
    return "\n".join(lines)


def _format_list_block(items: list[str], indent: int = 2) -> str:
    pad = " " * indent
    if not items:
        items = ["topic keyword", "industry news"]
    return "\n".join(f"{pad}- {q}" for q in items)


def _format_image_queries(queries: list[str]) -> str:
    if not queries:
        queries = [
            "technology workspace",
            "professional news",
            "modern office",
        ]
    lines = [f"    - {q}" for q in queries[:8]]
    return "\n".join(lines)


def build_show_yaml(spec: ScaffoldSpec) -> str:
    slug = spec.slug
    show_page = slug_to_page(slug)
    summaries_page = show_page.replace(".html", "-summaries.html")
    prefix = spec.episode_prefix or default_episode_prefix(slug)
    spoken = spec.show_name.replace("&", "and")

    mapping = {
        "show_name": spec.show_name,
        "slug": slug,
        "description": spec.description.replace('"', '\\"'),
        "weekly_recap": "true" if spec.weekly_recap else "false",
        "sources_block": _format_sources_block(spec.sources),
        "web_search_block": _format_list_block(spec.web_search_queries),
        "keywords_block": _format_list_block(spec.keywords),
        "min_articles": str(spec.min_articles),
        "min_articles_skip": str(spec.min_articles_skip),
        "digest_temperature": str(spec.digest_temperature),
        "podcast_temperature": str(spec.podcast_temperature),
        "max_tokens": str(spec.max_tokens),
        "podcast_max_tokens": str(spec.podcast_max_tokens),
        "min_podcast_words": str(spec.min_podcast_words),
        "music_file": DEFAULT_MUSIC,
        "rss_file": f"{slug}_podcast.rss",
        "rss_description": spec.description[:300],
        "show_page": show_page,
        "cover_file": f"{slug.replace('_', '-')}.jpg",
        "rss_category": spec.rss_category,
        "rss_keywords": ", ".join(spec.keywords[:8]) or slug.replace("_", " "),
        "guid_prefix": default_guid_prefix(slug),
        "x_enabled": "true" if spec.x_enabled else "false",
        "x_env_prefix": spec.x_env_prefix,
        "episode_prefix": prefix,
        "show_name_spoken": spoken.lower(),
        "short_label": default_short_label(spec.show_name),
        "emoji": spec.emoji,
        "newsletter_start_date": date.today().isoformat(),
        "length_target_words": str(spec.length_target_words),
        "youtube_category_id": spec.youtube_category_id,
        "image_queries_block": _format_image_queries(spec.image_queries),
        "summaries_page": summaries_page,
    }
    raw = (TEMPLATES_DIR / "show.yaml.template").read_text(encoding="utf-8")
    return raw.format(**mapping)


def build_network_meta_entry(spec: ScaffoldSpec) -> dict[str, Any]:
    slug = spec.slug
    show_page = slug_to_page(slug)
    rel = spec.related_show
    rel_name = rel.replace("_", " ").title()
    return {
        slug: {
            "name": spec.show_name,
            "slug": slug,
            "display_order": spec.display_order,
            "description": spec.description[:120],
            "show_page": show_page,
            "summaries_page": show_page.replace(".html", "-summaries.html"),
            "json_path": f"digests/{slug}/summaries_{slug}.json",
            "json_format": "wrapped",
            "rss_file": f"{slug}_podcast.rss",
            "podcast_image": f"assets/covers/{slug.replace('_', '-')}.jpg",
            "x_account": None,
            "brand_color": spec.brand_color,
            "brand_color_dark": spec.brand_color_dark or spec.brand_color,
            "tagline": spec.description[:80],
            "hero_tagline": spec.description[:80],
            "schedule": spec.schedule_label,
            "episode_length": f"~{spec.episode_length} min",
            "about_text": spec.description,
            "about_host": "Hosted by Patrick in Vancouver.",
            "description_long": spec.description,
            "related_show": rel,
            "related_reason": spec.related_reason or (
                f"If you enjoy {spec.show_name}, you might also like {rel_name}."
            ),
            "apple_podcasts_url": None,
            "spotify_url": None,
            "theme_color": spec.brand_color,
            "meta_description": f"{spec.show_name} — {spec.description[:140]}",
            "meta_keywords": ", ".join(spec.keywords[:10]) or slug.replace("_", ", "),
            "audience": spec.audience,
            "source_highlights": ["Curated RSS", "Google News"],
            "resource_categories": [],
            "picker_tags": {
                "topics": spec.keywords[:5] or [slug.replace("_", "-")],
                "audience": ["general"],
                "language": ["english"],
            },
        }
    }


def merge_network_meta(root: Path, entry: dict[str, Any], *, dry_run: bool) -> None:
    path = root / "shows" / "network_meta.yaml"
    existing: dict[str, Any] = {}
    if path.exists():
        existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    existing.update(entry)
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(existing, allow_unicode=True, sort_keys=True),
        encoding="utf-8",
    )


def append_cron_snippet(
    root: Path,
    spec: ScaffoldSpec,
    *,
    dry_run: bool,
) -> str:
    if not spec.cron:
        return ""
    filt = spec.cron_day_filter
    filt_repr = "None" if filt is None else f'"{filt}"'
    line = f'                  "{spec.cron}":       ("{spec.slug}",{" " * (27 - len(spec.slug))}{filt_repr}),'
    registry = root / "shows" / "scaffold_pending.yaml"
    pending: dict[str, Any] = {"cron_entries": []}
    if registry.exists():
        pending = yaml.safe_load(registry.read_text(encoding="utf-8")) or pending
    pending.setdefault("cron_entries", []).append({
        "cron": spec.cron,
        "slug": spec.slug,
        "day_filter": spec.cron_day_filter,
        "line": line.strip(),
    })
    if not dry_run:
        registry.write_text(
            yaml.safe_dump(pending, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    return line


def generate_registration_patch(spec: ScaffoldSpec) -> str:
    """Return a copy-paste friendly 'Registration Patch' block for the operator.

    This is the core of the medium-term onboarding automation improvement.
    It reduces the number of manual edits required after running the scaffold.
    """
    slug = spec.slug
    rss_file = f"{slug}_podcast.rss"
    cover = f"assets/covers/{slug.replace('_', '-')}.jpg"

    # Reasonable staleness threshold based on cadence
    if spec.cadence == "daily" or spec.weekly_recap:
        health_hours = 48
    elif "weekday" in (spec.cron_day_filter or ""):
        health_hours = 120
    else:
        health_hours = 96

    cron_line = ""
    if spec.cron:
        filt = spec.cron_day_filter
        filt_repr = "None" if filt is None else f'"{filt}"'
        cron_line = (
            f'                  "{spec.cron}":       ("{slug}",{" " * (27 - len(slug))}{filt_repr}),'
        )

    health_line = f'              "{rss_file}": ("{spec.show_name}", {health_hours}),'

    buttondown_tag = spec.slug.replace("_", "-")

    lines = [
        "\n" + "=" * 60,
        "REGISTRATION PATCH — copy/paste the relevant parts",
        "=" * 60,
        "",
        "1. Add to .github/workflows/run-show.yml  (inside CRON_MAP)",
    ]
    if cron_line:
        lines.append(f"   {cron_line}")
    else:
        lines.append("   (No --cron was provided — add manually)")

    lines.extend([
        "",
        "2. Add to .github/workflows/health-check.yml  (inside FEEDS)",
        f"   {health_line}",
        "",
        "3. Buttondown tag (create in Buttondown dashboard if missing):",
        f"   {buttondown_tag}",
        "",
        "4. Cover art:",
        f"   {cover}   (recommended 1200×1200)",
        "",
        "5. After first episode ships, run:",
        f"   python generate_html.py --show {slug} --blogs",
        "",
        "6. (Optional) Music:",
        f"   Update shows/{slug}.yaml → audio.music_file if you have a dedicated track.",
        "",
        "=" * 60,
    ])
    return "\n".join(lines)


def validate_slug(slug: str) -> None:
    if not re.match(r"^[a-z][a-z0-9_]{1,40}$", slug):
        raise ValueError(
            f"Invalid slug {slug!r} — use lowercase letters, digits, underscores; "
            "must start with a letter.",
        )


def scaffold_show(root: Path, spec: ScaffoldSpec, *, dry_run: bool = False) -> list[str]:
    """Create all artifacts for a new show. Returns human-readable log lines."""
    validate_slug(spec.slug)
    log: list[str] = []
    shows_dir = root / "shows"
    prompts_dir = shows_dir / "prompts"
    digest_dir = root / "digests" / spec.slug
    blog_dir = root / "blog" / spec.slug

    if (shows_dir / f"{spec.slug}.yaml").exists() and not dry_run:
        raise FileExistsError(f"shows/{spec.slug}.yaml already exists")

    pct = {
        "SHOW_NAME": spec.show_name,
        "AUDIENCE": spec.audience,
        "HOST_ROLE": spec.host_role or (
            f"Translate today's developments for {spec.audience}."
        ),
        "CONTENT_APPROACH": spec.content_approach or (
            "Lead with what changed, why it matters, and what to do this week."
        ),
        "INCLUDE_CRITERIA": spec.include_criteria or (
            "1. High-impact news with a clear 'so what'\n"
            "2. Actionable updates listeners can use\n"
            "3. Credible sources with working links"
        ),
        "REJECT_CRITERIA": spec.reject_criteria or (
            "- Pure opinion without news value\n"
            "- Duplicate angles already in the digest structure\n"
            "- Thin press releases with no substance"
        ),
        "VALUE_PROPOSITION": spec.value_proposition or spec.description,
        "HOST_VOICE": spec.host_voice or (
            "Warm, clear, and confident — respects the listener's intelligence."
        ),
        "CADENCE": spec.cadence,
        "EPISODE_LENGTH": spec.episode_length,
        "STORY_COUNT": spec.story_count,
        "WORD_MIN": str(spec.word_min),
        "WORD_MAX": str(spec.word_max),
        "ANALOGY_COUNT": str(spec.analogy_count),
    }

    if dry_run:
        log.append(f"[dry-run] Would write shows/{spec.slug}.yaml")
        log.append(f"[dry-run] Would write prompts {spec.slug}_*.txt")
        log.append(f"[dry-run] Would create {digest_dir}/ and {blog_dir}/")
    else:
        shows_dir.mkdir(parents=True, exist_ok=True)
        prompts_dir.mkdir(parents=True, exist_ok=True)
        shows_dir.joinpath(f"{spec.slug}.yaml").write_text(
            build_show_yaml(spec), encoding="utf-8",
        )
        log.append(f"Wrote shows/{spec.slug}.yaml")

        for stem, tmpl in [
            (f"{spec.slug}_system.txt", "system.txt.template"),
            (f"{spec.slug}_digest.txt", "digest.txt.template"),
            (f"{spec.slug}_podcast.txt", "podcast.txt.template"),
            (f"{spec.slug}_weekly.txt", "weekly.txt.template"),
        ]:
            out = prompts_dir / stem
            out.write_text(
                _render_percent_template(TEMPLATES_DIR / tmpl, pct),
                encoding="utf-8",
            )
            log.append(f"Wrote {out.relative_to(root)}")

        digest_dir.mkdir(parents=True, exist_ok=True)
        (digest_dir / ".gitkeep").write_text("", encoding="utf-8")
        blog_dir.mkdir(parents=True, exist_ok=True)
        (blog_dir / ".gitkeep").write_text("", encoding="utf-8")
        log.append("Created output dirs under digests/ and blog/")

    merge_network_meta(root, build_network_meta_entry(spec), dry_run=dry_run)
    log.append(
        "[dry-run] Would update shows/network_meta.yaml"
        if dry_run
        else "Updated shows/network_meta.yaml (website registry)"
    )

    cron_line = append_cron_snippet(root, spec, dry_run=dry_run)
    if cron_line:
        log.append(
            "Cron line (paste into .github/workflows/run-show.yml CRON_MAP):\n"
            f"  {cron_line}"
        )

    log.append(
        "\nNext steps:\n"
        f"  1. python scripts/validate_show.py {spec.slug}\n"
        f"  2. python run_show.py {spec.slug} --test\n"
        f"  3. python run_show.py {spec.slug}  # first real episode (Ep1 gets debut prompts)\n"
        f"  4. Add cover art: assets/covers/{spec.slug.replace('_', '-')}.jpg\n"
        f"  5. Paste cron line + run generate_html.py --show {spec.slug}\n"
    )

    # Medium item: emit a much richer registration patch to reduce manual steps
    patch = generate_registration_patch(spec)
    log.append(patch)

    return log
