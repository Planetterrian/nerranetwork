"""Per-show episode-validity drift guards.

Validates the most recent *committed* digest for every show against structural
floors.  This catches the failure modes that infra tests miss: a prompt or
model change that starts emitting empty, truncated, or garbage digests.  Floors
are deliberately conservative (well below every show's current output) so the
guard fires on real regressions, not on a legitimately short news day.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine.config import discover_show_slugs, load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Hard floor: a real digest is hundreds of words. The lowest observed recent
# digest across the network is ~400 words; 150 catches truncation/empty/refusal
# output without flaking on a quiet news day.
MIN_DIGEST_WORDS = 150

SLUGS = discover_show_slugs()


_EP_DATE_RE = re.compile(r"_Ep(\d+)_(\d{8})", re.IGNORECASE)


def _sort_key(path: Path):
    """Deterministic 'recency' key parsed from the filename.

    Digest files are named ``Show_Ep<NN>_<YYYYMMDD>.md``. Sorting by
    (date, episode_num) is stable across machines — unlike mtime, which is
    identical for every file in a fresh CI checkout and would make the choice
    of "latest" nondeterministic.
    """
    m = _EP_DATE_RE.search(path.stem)
    if m:
        return (1, m.group(2), int(m.group(1)))
    # Files that don't match the episode pattern sort last (and are filtered
    # out below anyway) — fall back to the name for total ordering.
    return (0, path.stem, 0)


def _latest_digest(cfg):
    out_dir = Path(cfg.episode.output_dir)
    if not out_dir.exists():
        return None
    # Only true episode digests (Ep<NN>_<date>), never _tts scripts or stray .md.
    mds = [
        p for p in out_dir.glob("*.md")
        if "_tts" not in p.stem and _EP_DATE_RE.search(p.stem)
    ]
    if not mds:
        return None
    mds.sort(key=_sort_key)
    return mds[-1]


@pytest.fixture(params=SLUGS)
def show_cfg(request):
    slug = request.param
    return slug, load_config(PROJECT_ROOT / "shows" / f"{slug}.yaml")


class TestLatestEpisodeValidity:
    def test_latest_digest_meets_word_floor(self, show_cfg):
        slug, cfg = show_cfg
        digest = _latest_digest(cfg)
        if digest is None:
            pytest.skip(f"{slug}: no committed digest yet")
        words = len(digest.read_text(encoding="utf-8", errors="replace").split())
        assert words >= MIN_DIGEST_WORDS, (
            f"{slug}: latest digest {digest.name} is only {words} words "
            f"(floor {MIN_DIGEST_WORDS}) — possible truncation/refusal regression"
        )

    def test_latest_digest_not_a_refusal(self, show_cfg):
        slug, cfg = show_cfg
        digest = _latest_digest(cfg)
        if digest is None:
            pytest.skip(f"{slug}: no committed digest yet")
        # Reuse the production refusal gate so committed output and live output
        # are held to the same standard.
        from engine.generator import LLMRefusalError, _validate_llm_output
        text = digest.read_text(encoding="utf-8", errors="replace")
        try:
            _validate_llm_output(text, stage="digest", show_name=slug)
        except LLMRefusalError as exc:
            pytest.fail(f"{slug}: committed digest {digest.name} reads as a refusal: {exc}")


class TestOutputDirsResolve:
    def test_every_show_output_dir_is_configured(self, show_cfg):
        slug, cfg = show_cfg
        assert cfg.episode.output_dir, f"{slug}: no episode.output_dir configured"
