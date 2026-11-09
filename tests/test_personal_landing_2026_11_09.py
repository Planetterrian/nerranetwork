"""Nov 9 2026 — the ad landing page ships what its template says.

Operator: "Rework the ad landing page". Found on the way: nightly-maintenance
rebuilt ``personal-interest.html`` with ``--static-pages`` every night, but the
commit step's add-paths never listed it (nor ``sponsor.html`` or
``explore.html``), so each night's render was thrown away. The Oct 28 sample
section never reached the page that takes the paid traffic.

The guard derives the pages from ``generate_static_pages`` itself: every
root-level page one of its callees writes, and that is committed, must be in
the nightly's add-paths.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = (ROOT / "generate_html.py").read_text(encoding="utf-8")
NIGHTLY = (ROOT / ".github/workflows/nightly-maintenance.yml").read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    start = GEN.index(f"def {name}(")
    nxt = re.search(r"^def \w+\(", GEN[start + 1:], flags=re.M)
    return GEN[start:start + 1 + nxt.start()] if nxt else GEN[start:]


def _static_page_files() -> set[str]:
    body = _function_body("generate_static_pages")
    files: set[str] = set()
    for callee in set(re.findall(r"\b(generate_\w+)\(", body)):
        if callee == "generate_static_pages" or f"def {callee}(" not in GEN:
            continue
        files.update(re.findall(r'ROOT\s*\)?\s*/\s*"([\w.-]+\.html)"',
                                _function_body(callee)))
    return files


def _add_paths() -> set[str]:
    block = NIGHTLY.split("add-paths: |", 1)[1]
    return {ln.strip() for ln in block.splitlines() if ln.startswith("            ")
            and ln.strip() and not ln.strip().startswith("#")}


def test_the_derivation_finds_the_pages():
    files = _static_page_files()
    assert {"personal-interest.html", "sponsor.html", "explore.html"} <= files


def test_every_committed_static_page_is_committed_nightly():
    paths = _add_paths()
    missing = sorted(f for f in _static_page_files()
                     if (ROOT / f).exists() and f not in paths)
    assert not missing, f"rebuilt nightly, never committed: {missing}"


def test_the_committed_landing_page_carries_the_sample():
    html = (ROOT / "personal-interest.html").read_text(encoding="utf-8")
    main = html.split('class="spi-hero"', 1)[1].split("<script>", 1)[0]
    assert 'data-nn-sample="personal-interest"' in main
    assert "Build yours →" in main
    assert "Personal tips" not in main
