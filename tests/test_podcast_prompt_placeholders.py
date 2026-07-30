"""Every podcast prompt placeholder must be supplied by the LIVE path.

The bug this exists to prevent, in full, because it took the whole
network down:

The July 30 2026 retention pass added ``{cold_open_spec}`` to all 14
podcast prompts and ``{delivery_spec}`` to 17, and wired both into the
``pod_vars`` dict in ``run_show.py``. But ``run_show.py`` builds that
dict and never passes it to ``run_generation_phase`` — the live path
rebuilds its own ``pod_vars`` inside ``engine/pipeline.py`` (there is a
comment there saying exactly this, from the *previous* time someone was
caught by it). So nothing supplied either key, and the next run of every
show died in ``load_prompt`` with ``KeyError: 'cold_open_spec'``.
SpaceX Ep50 was the first to tick over, 2026-07-30 20:54 UTC.

``tests/test_prompt_fidelity.py`` could not catch this: it renders each
prompt with "a forgiving mapping (every placeholder -> '')", which by
construction can never notice a key the pipeline fails to provide.

So this test drives the REAL ``run_generation_phase`` with the LLM calls
stubbed and asserts the prompt formats. Testing the live function rather
than re-deriving its variable set is the point — a reimplementation
would drift from the thing it is supposed to guard.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.config import discover_show_slugs, load_config  # noqa: E402
from engine.generator import load_prompt  # noqa: E402
from engine import pipeline  # noqa: E402


# Placeholders that a per-show pre-fetch hook injects through
# ``extra_context`` rather than the pipeline. These are legitimately
# absent when the hook doesn't run.
#
# ADDING A PLACEHOLDER TO A PODCAST PROMPT? It must either be supplied by
# engine/pipeline.py's pod_vars (the live path) or be listed here with
# the hook that provides it. Wiring it into run_show.py's pod_vars is NOT
# enough — that dict is discarded.
_HOOK_SUPPLIED = {
    "narrative_memory_section",          # shows/hooks/<slug>.py via show_memory
    "vocab_review_section",              # shows/hooks/privet_russian.py
    "ipo_debut_section",                 # shows/hooks/spacex.py
    "tesla_narrative_status_block",      # shows/hooks/tesla.py
    "tesla_performance_signals_block",   # shows/hooks/tesla.py
    "tesla_theme_context_block",         # shows/hooks/tesla.py
}


def _podcast_shows():
    out = []
    for slug in discover_show_slugs():
        try:
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
        except Exception:  # noqa: BLE001
            continue
        if cfg.llm.podcast_prompt_file:
            out.append(slug)
    return out


def _missing_placeholders(slug: str) -> list:
    """Run the live generation path; return placeholders it failed to fill."""
    cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
    missing: list = []

    def _fake_podcast(vars_dict, config, tracker=None):
        try:
            load_prompt(config.llm.podcast_prompt_file, vars_dict)
        except KeyError as exc:
            missing.append(str(exc).strip("'"))
        # Long enough to clear the runner's word-count gates.
        return "word " * 400

    logging.disable(logging.CRITICAL)
    try:
        with mock.patch("engine.generator.generate_podcast_script",
                        _fake_podcast), \
             mock.patch("engine.generator.generate_digest",
                        lambda *a, **k: "# Digest\nbody"):
            try:
                pipeline.run_generation_phase(
                    cfg,
                    episode_num=50,
                    today_str="2026-07-30",
                    hook="A representative episode hook.",
                    x_thread="# Show\nbody text",
                    # Deliberately EMPTY so hook-supplied keys surface and
                    # get checked against the registry above.
                    extra_context={},
                    template_vars={"digest": "body"},
                    args=SimpleNamespace(show=slug),
                )
            except KeyError as exc:
                missing.append(str(exc).strip("'"))
            except Exception:  # noqa: BLE001 — only KeyError is in scope
                pass
    finally:
        logging.disable(logging.NOTSET)
    return missing


@pytest.mark.parametrize("slug", _podcast_shows())
def test_live_path_supplies_every_podcast_placeholder(slug):
    unexpected = [k for k in _missing_placeholders(slug)
                  if k not in _HOOK_SUPPLIED]
    assert not unexpected, (
        f"{slug}'s podcast prompt references {unexpected}, which "
        "engine/pipeline.py does not supply. Wiring it into run_show.py's "
        "pod_vars does NOT count — that dict is never passed to "
        "run_generation_phase. Either add it to pod_vars in "
        "engine/pipeline.py, or add it to _HOOK_SUPPLIED in this test with "
        "the hook that provides it."
    )


def test_run_show_does_not_rebuild_a_discarded_pod_vars():
    """The trap itself, removed 2026-07-30 — keep it removed.

    ``run_show.py`` used to build a second, complete set of podcast
    template variables into a local ``pod_vars`` dict and then never pass
    it to ``run_generation_phase``. It read as the authoritative place to
    wire a prompt variable, and twice it wasn't: the DP Pod Ep001
    truncated closing, and the network-wide ``KeyError: 'cold_open_spec'``.

    Guarding the symptom (the test above) is not enough while the trap is
    still sitting there looking authoritative.
    """
    import ast

    tree = ast.parse((ROOT / "run_show.py").read_text(encoding="utf-8"))
    # Structural, not a substring match: the comment left behind at the
    # removal site names `pod_vars` on purpose, and that comment is the
    # thing telling the next person where prompt variables belong.
    assigned = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    assert "pod_vars" not in assigned, (
        "run_show.py is building podcast template variables again. That "
        "dict is not what formats the prompt — engine/pipeline.py's "
        "run_generation_phase is. Put prompt variables there, or pass "
        "per-show values through extra_context."
    )


def test_the_two_specs_from_the_retention_pass_are_wired():
    """Pin the exact regression: SpaceX Ep50, 2026-07-30 20:54 UTC."""
    import inspect

    src = inspect.getsource(pipeline.run_generation_phase)
    for key in ("cold_open_spec", "delivery_spec"):
        assert f'"{key}"' in src, (
            f"{key} is referenced by the podcast prompts but no longer "
            "supplied by the live generation path — this is the exact "
            "shape that broke every show on 2026-07-30."
        )
