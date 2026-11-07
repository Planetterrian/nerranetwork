#!/usr/bin/env bash
# Put a checksum-verified static ffmpeg + ffprobe in DEST (arg 1).
#
# Reads BTBN_TAG / BTBN_ASSET from the environment: the dated BtbN autobuild
# the test suite runs on. Nov 6 2026: BtbN keeps only about two weeks of
# dated autobuilds, so a pin goes 404 on its own (the Oct 22 build was gone
# by Nov 6 and every apt-stall fallback in the network failed with curl
# exit 22). When the pinned release is gone this takes BtbN's rolling
# `latest` release of the SAME 8.1 branch, verified against that release's
# own checksums.sha256, and says so loudly. Refresh the pin in test.yml,
# the two composites and the rehearsal workflow when the warning appears.
set -euo pipefail
dest="${1:?usage: fetch_static_ffmpeg.sh DEST}"
: "${BTBN_TAG:?}" "${BTBN_ASSET:?}"
LATEST_ASSET="ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz"
work="$(mktemp -d)"
mkdir -p "$dest"

fetch() {  # tag asset -> 0 when downloaded and verified in $work
  local base="https://github.com/BtbN/FFmpeg-Builds/releases/download/$1"
  (cd "$work" && rm -f checksums.sha256 "$2" &&
    timeout 300 curl -fsSL --retry 2 --retry-delay 2 --connect-timeout 20 --max-time 240 \
      -o checksums.sha256 "$base/checksums.sha256" &&
    timeout 300 curl -fsSL --retry 2 --retry-delay 2 --connect-timeout 20 --max-time 240 \
      -o "$2" "$base/$2" &&
    grep -F " $2" checksums.sha256 | sha256sum -c -)
}

asset="$BTBN_ASSET"
if ! fetch "$BTBN_TAG" "$asset"; then
  echo "::warning::the pinned static ffmpeg ($BTBN_TAG) could not be fetched; BtbN prunes dated builds after about two weeks. Using BtbN's latest 8.1 build — refresh the pin."
  asset="$LATEST_ASSET"
  fetch latest "$asset"
fi
tar -xJf "$work/$asset" -C "$work"
cp "$work/${asset%.tar.xz}/bin/ffmpeg" "$work/${asset%.tar.xz}/bin/ffprobe" "$dest/"
chmod +x "$dest/ffmpeg" "$dest/ffprobe"
rm -rf "$work"
"$dest/ffmpeg" -version | head -1
