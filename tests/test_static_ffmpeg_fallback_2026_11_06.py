"""Nov 6 2026: the pinned static ffmpeg went 404.

BtbN keeps about two weeks of dated autobuilds. The Oct 22 build every
apt-stall fallback pointed at was pruned by Nov 6, so a stalled Ubuntu mirror
failed the run with curl exit 22 instead of falling back (the Nerra Personal
batch sweep at 20:03 UTC that day). ``scripts/fetch_static_ffmpeg.sh`` is now
the one downloader: the pinned build first, then BtbN's rolling ``latest`` of
the same 8.1 branch, each verified against its own release's checksums.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (ROOT / "scripts" / "fetch_static_ffmpeg.sh").read_text()
CALLERS = [
    ".github/actions/setup-ffmpeg/action.yml",
    ".github/actions/setup-python/action.yml",
    ".github/workflows/test.yml",
    ".github/workflows/nerra_voices_rehearsal.yml",
]


def _pins(text):
    tags = set(re.findall(r"BTBN_TAG[=:] ?(autobuild-[\w-]+)", text))
    assets = set(re.findall(r"BTBN_ASSET[=:] ?(\S+\.tar\.xz)", text))
    return tags, assets


class TestOneDownloader:
    def test_every_static_ffmpeg_goes_through_the_script(self):
        for rel in CALLERS:
            text = (ROOT / rel).read_text()
            assert "scripts/fetch_static_ffmpeg.sh" in text, rel
            assert "releases/download/" not in text, f"{rel} downloads ffmpeg itself"

    def test_every_caller_pins_the_same_build(self):
        pins = [_pins((ROOT / rel).read_text()) for rel in CALLERS]
        assert all(p == pins[0] and len(p[0]) == 1 for p in pins), pins

    def test_the_test_cache_key_names_the_pinned_build(self):
        text = (ROOT / ".github/workflows/test.yml").read_text()
        (tag,), (asset,) = _pins(text)
        key = re.search(r"key: (ffmpeg-btbn-\S+)", text).group(1)
        assert key == f"ffmpeg-btbn-{tag}-{asset.removeprefix('ffmpeg-').removesuffix('.tar.xz')}"


class TestAPrunedPinFallsBack:
    def test_pinned_first_then_latest_of_the_same_branch(self):
        assert SCRIPT.index('fetch "$BTBN_TAG"') < SCRIPT.index("fetch latest")
        assert 'LATEST_ASSET="ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz"' in SCRIPT
        assert "::warning::" in SCRIPT, "a used fallback says to refresh the pin"

    def test_every_download_is_checksum_verified(self):
        assert "sha256sum -c -" in SCRIPT
        assert "set -euo pipefail" in SCRIPT
        assert "--max-time 240" in SCRIPT
