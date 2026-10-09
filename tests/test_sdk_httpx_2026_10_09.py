"""Oct 9 2026 — the streaming reader imports the SDK's own HTTP module.

``openai`` 3.26+ is built on ``httpx2`` (a different import name from
``httpx``) and nothing in requirements named ``httpx``; it arrived only as
a transitive dependency until ``tokenizers`` 0.23.3 (10:00 UTC) let
``huggingface-hub`` 2.x resolve, after which no package pulled it in and
every ``llm.stream`` show from 10:08 died at its first digest call on
``ModuleNotFoundError: No module named 'httpx'`` — seven shows, and the
Nerra Daily edition held for them. ``engine.generator.sdk_httpx`` returns
whichever module the SDK imported; no production module may ``import
httpx`` by name again.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import generator as gen  # noqa: E402


def test_sdk_httpx_is_the_module_openai_imported():
    import openai  # noqa: F401
    mod = gen.sdk_httpx()
    assert mod.__name__ in ("httpx2", "httpx")
    assert mod.__name__ in sys.modules, "the SDK must have imported it already"
    # It is usable for what the stream reader needs from it.
    req = mod.Request("POST", "https://api.x.ai/v1/chat/completions")
    assert req.method == "POST"
    assert mod.Timeout(5.0, connect=30.0) is not None


def test_no_production_module_imports_httpx_by_name():
    bare = re.compile(r"^\s*(?:import httpx\b|from httpx\b)", re.M)
    offenders = []
    for path in list((ROOT / "engine").rglob("*.py")) + [ROOT / "run_show.py"] \
            + list((ROOT / "scripts").glob("*.py")) + list((ROOT / "pipelines").rglob("*.py")) \
            + list((ROOT / "shows" / "hooks").glob("*.py")) + [ROOT / "digests" / "xai_grok.py"]:
        if bare.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], offenders


def test_stream_reader_uses_the_helper():
    src = (ROOT / "engine" / "generator.py").read_text(encoding="utf-8")
    body = src[src.index("def _stream_completion("):]
    assert "httpx = sdk_httpx()" in body.split("def ", 2)[1]
