"""Prompt-fidelity drift guards across every show.

These don't grade prose — they pin the *mechanical contract* every show's
prompts must satisfy so a bad edit (a malformed brace, a deleted prompt file, a
broken shared-snippet include) is caught in CI instead of at 6 AM UTC mid-run.

Rendering safety is the key check: ``engine.generator.load_prompt`` runs
``str.format_map`` on every prompt, which raises on an unescaped/malformed
brace.  We render each prompt with a forgiving mapping (every placeholder ->
"") so any brace problem surfaces here regardless of which vars a given show
supplies at runtime.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.config import discover_show_slugs, load_config
from engine.generator import load_prompt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "shows" / "prompts"
SHARED_DIR = PROMPTS_DIR / "_shared"


class _Forgiving(dict):
    """format_map mapping that yields '' for any key but still raises on
    malformed/unescaped braces — exactly the production failure mode."""

    def __missing__(self, key):  # noqa: D401
        return ""


SLUGS = discover_show_slugs()


@pytest.fixture(params=SLUGS)
def show_cfg(request):
    slug = request.param
    return slug, load_config(PROJECT_ROOT / "shows" / f"{slug}.yaml")


def _prompt_paths(cfg):
    out = {}
    for label in ("digest_prompt_file", "podcast_prompt_file", "system_prompt_file"):
        val = getattr(cfg.llm, label, "")
        if val:
            out[label] = Path(val)
    return out


class TestPromptFilesExist:
    def test_digest_and_podcast_prompts_configured_and_present(self, show_cfg):
        slug, cfg = show_cfg
        assert cfg.llm.digest_prompt_file, f"{slug}: no digest_prompt_file configured"
        assert cfg.llm.podcast_prompt_file, f"{slug}: no podcast_prompt_file configured"
        for label in ("digest_prompt_file", "podcast_prompt_file"):
            p = Path(getattr(cfg.llm, label))
            assert p.exists(), f"{slug}: {label} missing on disk: {p}"
            assert p.read_text(encoding="utf-8").strip(), f"{slug}: {label} is empty"

    def test_system_prompt_present_when_configured(self, show_cfg):
        slug, cfg = show_cfg
        if cfg.llm.system_prompt_file:
            p = Path(cfg.llm.system_prompt_file)
            assert p.exists(), f"{slug}: system_prompt_file missing: {p}"


class TestPromptsRenderSafely:
    def test_prompts_render_without_brace_errors(self, show_cfg):
        slug, cfg = show_cfg
        for label, path in _prompt_paths(cfg).items():
            try:
                rendered = load_prompt(str(path), _Forgiving())
            except (ValueError, IndexError) as exc:
                pytest.fail(f"{slug}: {label} has a malformed brace and would crash a live run: {exc}")
            except KeyError as exc:  # pragma: no cover - _Forgiving prevents this
                pytest.fail(f"{slug}: {label} KeyError despite forgiving map: {exc}")
            assert isinstance(rendered, str)


class TestSharedSnippets:
    def test_shared_dir_exists(self):
        assert SHARED_DIR.is_dir(), "shows/prompts/_shared is missing"

    def test_shared_snippets_are_includable(self):
        # Every shared .txt must resolve through the include mechanism.
        for snippet in SHARED_DIR.glob("*.txt"):
            rel = snippet.name
            probe = PROMPTS_DIR / "__fidelity_probe__.txt"
            probe.write_text(f"<<include: _shared/{rel}>>", encoding="utf-8")
            try:
                out = load_prompt(str(probe), None)
                assert out.strip(), f"_shared/{rel} resolved empty"
            finally:
                probe.unlink(missing_ok=True)
