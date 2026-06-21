"""Drift guards for show-count consistency (June 11 2026 sweep).

The network grew 10 → 11 → 12 shows and public surfaces fossilized at
"Eleven shows" / "11 daily podcasts" in seven templates, the homepage
metas, the newsletter footer, the network RSS description, and README.
Living surfaces now either compute the count from ``all_shows`` /
``NETWORK_SHOWS`` (templates + generate_html metas) or hardcode the
current count and are pinned here, so adding show #13 fails CI with a
list of every spot to update. Dated historical docs (docs/reviews/*,
CLAUDE.md pass narratives) are deliberately NOT covered — they describe
the network as it was.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _show_count() -> int:
    import generate_html
    return len(generate_html.NETWORK_SHOWS)


def test_network_has_thirteen_shows():
    """When this fails you've added/removed a show — update the
    hardcoded-count surfaces listed in the other tests, then bump this."""
    assert _show_count() == 13


def test_no_stale_count_phrases_in_templates():
    stale = re.compile(
        r"\b(?:eleven|ten|nine)\s+(?:ad-free\s+|daily\s+)?(?:shows|podcasts)\b"
        r"|\b(?:9|10|11)\s+(?:daily\s+)?(?:shows|podcasts)\b"
        r"|Одиннадцать подкаст",
        re.IGNORECASE,
    )
    offenders = []
    for f in (_ROOT / "templates").glob("*.j2"):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if stale.search(line):
                offenders.append(f"{f.name}:{i}: {line.strip()[:80]}")
    assert not offenders, "stale show counts in templates:\n" + "\n".join(offenders)


def test_templates_use_dynamic_count():
    # After the June 2026 brand refresh, about.html.j2 and base.html.j2 are
    # intentionally count-agnostic. The remaining templates still compute
    # show counts dynamically to remain forward-compatible with network growth.
    for name in ("editorial.html.j2", "how_to_listen.html.j2",
                 "start_here.html.j2", "player_page.html.j2"):
        src = (_ROOT / "templates" / name).read_text(encoding="utf-8")
        assert "all_shows|length" in src, f"{name} no longer computes the show count"


def test_hardcoded_count_surfaces_match():
    n = str(_show_count())
    # After the June 2026 brand refresh, README.md was made count-agnostic.
    # These surfaces remain hardcoded and must match the current show count:
    surfaces = {
        "engine/newsletter.py": f"{n} daily podcasts, ad-free",
        "CLAUDE.md": f"running {n} shows via a unified",
    }
    for rel, needle in surfaces.items():
        src = (_ROOT / rel).read_text(encoding="utf-8")
        assert needle in src, f"{rel}: expected {needle!r} (show count changed?)"


def test_generate_html_metas_are_computed():
    src = (_ROOT / "generate_html.py").read_text(encoding="utf-8")
    assert src.count("{len(NETWORK_SHOWS)}") >= 4
    assert "11 Daily Shows" not in src
    assert "Eleven daily podcasts" not in src
