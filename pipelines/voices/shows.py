"""Show registry for the Mira-hosted interview shows (September 2026).

The voices pipeline used to hardcode ``age_of_ai`` everywhere. With Nerra
Voices as a sister show, every script threads a ``show`` slug (from the
``guest_applications.show`` / ``interviews.show`` columns) and asks this
module for the show-specific settings instead.

Everything here is read from ``shows/<slug>.yaml``: the ``publishing:``
block (feed, page, paths) and a ``voices:`` block (studio/apply pages,
brand colour, R2 prefix, music bed, cover, Mira's premise/opening/closing
for that show). Nothing show-specific should be hardcoded in the pipeline
scripts any more; if you need a new per-show value, add it to the yaml
and expose it on :class:`VoiceShow`.

Pure and dependency-free (yaml + pathlib) so tests and the Worker-side
docs can rely on it without Supabase or network access.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
SHOWS_DIR = ROOT / "shows"

# LANDMINE GUARD. This file is called ``shows.py`` and lives in a directory
# that is ``sys.path[0]`` whenever a pipeline script runs (or a test does
# ``sys.path.insert(0, PIPELINES)``). A ``.py`` module anywhere on sys.path
# beats the repo's top-level ``shows/`` namespace package (PEP 420), so a
# bare ``import shows`` in that process resolves HERE and every
# ``from shows.hooks import ...`` (run_show, engine.pipeline_resume, the
# hook tests) fails with "'shows' is not a package". Giving this module a
# ``__path__`` pointing at the real directory makes it double as that
# package: ``shows.hooks.tesla`` keeps resolving to shows/hooks/tesla.py.
# Importers of the registry itself should use the unambiguous
# ``from pipelines.voices.shows import ...`` (see common.py).
if __name__ == "shows":  # only when we are the one shadowing
    __path__ = [str(SHOWS_DIR)]  # noqa: F841 — read by the import system

DEFAULT_SHOW = "age_of_ai"
VOICE_SHOW_SLUGS: tuple[str, ...] = ("age_of_ai", "nerra_voices")

# Defaults for the original show so an older age_of_ai.yaml without a
# ``voices:`` block still resolves exactly as the July 2026 pipeline did.
_AGE_OF_AI_VOICES_DEFAULTS: Dict[str, Any] = {
    "short_label": "Age of AI",
    "brand_color": "#7C3AED",
    "apply_page": "age-of-ai-apply.html",
    "studio_page": "age-of-ai-studio.html",
    "r2_prefix": "age_of_ai",
    "music_bed": "assets/music/age_of_ai.mp3",
    "cover": "assets/covers/age-of-ai.jpg",
    "prompt_dir": None,
    "sign_off": "— The Age of AI, Nerra Network",
    "premise": (
        "The Age of AI is a documentary podcast about artificial "
        "intelligence's emergence and impact. Mira, an AI, interviews real "
        "people live about what the AI transition actually feels like from "
        "inside a life and a livelihood."
    ),
    "opening_line": "Welcome to The Age of AI. I'm Mira. I'm an AI, and my guests never are.",
    "closing_question": (
        "What's the one bet you're making for the next twelve months that "
        "you cannot prove yet?"
    ),
}


@dataclass(frozen=True)
class VoiceShow:
    slug: str
    name: str                 # "The Age of AI"
    short_label: str          # "Age of AI" — Slack prefixes, subjects
    brand_color: str
    page: str                 # "age-of-ai.html"
    summaries_page: str
    apply_page: str
    studio_page: str
    rss_file: str
    rss_link: str
    rss_description: str
    rss_summary: str
    rss_author: str
    rss_email: str
    rss_image: str
    rss_category: str
    rss_subcategory: str
    rss_keywords: str
    guid_prefix: str
    base_url: str
    audio_subdir: str         # "digests/age_of_ai"
    summaries_json: str       # "digests/age_of_ai/summaries_age_of_ai.json"
    episode_prefix: str       # "Age_of_AI"
    r2_prefix: str            # "age_of_ai"
    music_bed: str
    cover: str
    prompt_dir: Optional[str]  # subdir under pipelines/voices/prompts/, or None
    sign_off: str
    premise: str
    opening_line: str
    closing_question: str

    # -- derived -----------------------------------------------------------
    @property
    def page_url(self) -> str:
        return f"{self.base_url}/{self.page}"

    @property
    def apply_url(self) -> str:
        return f"{self.base_url}/{self.apply_page}"

    def studio_url(self, interview_id: str = "") -> str:
        q = f"?interview={interview_id}" if interview_id else "?"
        sep = "&" if interview_id else ""
        return f"{self.base_url}/{self.studio_page}{q}{sep}show={self.slug}"

    @property
    def summaries_path(self) -> Path:
        return ROOT / self.summaries_json

    @property
    def rss_path(self) -> Path:
        return ROOT / self.rss_file

    @property
    def music_bed_path(self) -> Path:
        return ROOT / self.music_bed

    @property
    def cover_path(self) -> Path:
        return ROOT / self.cover

    def prompt_path(self, template: str) -> Path:
        """Per-show prompt override with fallback to the shared prompt.

        ``pipelines/voices/prompts/<prompt_dir>/<template>`` wins when it
        exists; otherwise the shared ``pipelines/voices/prompts/<template>``.
        """
        base = ROOT / "pipelines" / "voices" / "prompts"
        if self.prompt_dir:
            candidate = base / self.prompt_dir / template
            if candidate.exists():
                return candidate
        return base / template

    def r2_key(self, *parts: str) -> str:
        return "/".join([self.r2_prefix, *[p.strip("/") for p in parts]])

    def slack(self, text: str) -> str:
        """Prefix a Slack/ops line with the show label."""
        return f"{self.short_label}: {text}"


def _load_yaml(slug: str) -> Dict[str, Any]:
    path = SHOWS_DIR / f"{slug}.yaml"
    if not path.exists():
        raise KeyError(f"unknown voices show {slug!r} (no {path.name})")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=None)
def get_show(slug: Optional[str] = None) -> VoiceShow:
    """Resolve a show slug (``None``/"" → :data:`DEFAULT_SHOW`)."""
    slug = (slug or DEFAULT_SHOW).strip()
    if slug not in VOICE_SHOW_SLUGS:
        raise KeyError(f"{slug!r} is not a voices show; known: {VOICE_SHOW_SLUGS}")
    cfg = _load_yaml(slug)
    pub = cfg.get("publishing") or {}
    ep = cfg.get("episode") or {}
    voices = dict(_AGE_OF_AI_VOICES_DEFAULTS) if slug == DEFAULT_SHOW else {}
    voices.update(cfg.get("voices") or {})
    missing = [k for k in ("short_label", "brand_color", "apply_page", "studio_page",
                           "r2_prefix", "music_bed", "cover", "sign_off",
                           "premise", "opening_line", "closing_question")
               if not voices.get(k)]
    if missing:
        raise ValueError(f"shows/{slug}.yaml voices: block is missing {missing}")
    return VoiceShow(
        slug=slug,
        name=cfg.get("name") or pub.get("rss_title") or slug,
        short_label=voices["short_label"],
        brand_color=voices["brand_color"],
        page=pub.get("player_html", f"{slug}.html"),
        summaries_page=pub.get("summaries_html", f"{slug}-summaries.html"),
        apply_page=voices["apply_page"],
        studio_page=voices["studio_page"],
        rss_file=pub.get("rss_file", f"{slug}_podcast.rss"),
        rss_link=pub.get("rss_link", ""),
        rss_description=(pub.get("rss_description") or cfg.get("description") or "").strip(),
        rss_summary=pub.get("rss_summary", ""),
        rss_author=pub.get("rss_author", "Nerra Network"),
        rss_email=pub.get("rss_email", "patrick@planetterrian.com"),
        rss_image=pub.get("rss_image", ""),
        rss_category=pub.get("rss_category", "Society & Culture"),
        rss_subcategory=pub.get("rss_subcategory", "Personal Journals"),
        rss_keywords=pub.get("rss_keywords", ""),
        guid_prefix=pub.get("guid_prefix", slug.replace("_", "-")),
        base_url=(pub.get("base_url") or "https://nerranetwork.com").rstrip("/"),
        audio_subdir=pub.get("audio_subdir", f"digests/{slug}"),
        summaries_json=pub.get("summaries_json", f"digests/{slug}/summaries_{slug}.json"),
        episode_prefix=ep.get("prefix", slug.title().replace("_", "_")),
        r2_prefix=voices["r2_prefix"],
        music_bed=voices["music_bed"],
        cover=voices["cover"],
        prompt_dir=voices.get("prompt_dir") or None,
        sign_off=voices["sign_off"],
        premise=" ".join(str(voices["premise"]).split()),
        opening_line=" ".join(str(voices["opening_line"]).split()),
        closing_question=" ".join(str(voices["closing_question"]).split()),
    )


def all_shows() -> Iterable[VoiceShow]:
    return tuple(get_show(s) for s in VOICE_SHOW_SLUGS)


def show_for(row: Optional[Dict[str, Any]], *fallbacks: Optional[Dict[str, Any]]) -> VoiceShow:
    """Pick the show for a Supabase row (interview, application, run).

    Looks at ``row["show"]`` then each fallback row in turn (e.g. the
    application joined to an interview); rows written before the
    September 2026 migration have no ``show`` and resolve to the default.
    """
    for candidate in (row, *fallbacks):
        if candidate and candidate.get("show"):
            return get_show(str(candidate["show"]))
    return get_show(DEFAULT_SHOW)


def is_voice_show(slug: Any) -> bool:
    return isinstance(slug, str) and slug in VOICE_SHOW_SLUGS
