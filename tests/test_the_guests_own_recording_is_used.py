"""Oct 7 2026 (Scott Pulcini). His browser recorded the whole interview at
192 kbps straight off his microphone and every chunk reached R2, but the page
never sent upload-done, so the episode was built from the compressed call
audio: noisy and thin. Viktor Popovic's and Vincent Rylan's takes were orphaned
the same way. And the call-audio chain, applied to a clean recording, made it
worse."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
POST = (V / "post_interview.py").read_text(encoding="utf-8")
ASSEMBLE = (V / "assemble_edit.py").read_text(encoding="utf-8")


def _keys(sid, n, skip=()):
    return [f"nerra_voices/local/r1/guest/{sid}/{i:05d}.webm" for i in range(n) if i not in skip]


def test_an_orphan_take_becomes_a_manifest():
    from audio.local_tracks import manifest_is_complete, orphan_manifest
    m = orphan_manifest(_keys("abc", 540) + _keys("zzz", 12), "r1", "guest", "nerra_voices")
    assert m["sid"] == "abc" and len(m["chunks"]) == 540 and m["missing"] == []
    assert m["chunks"][0].endswith("/00000.webm") and m["chunks"][-1].endswith("/00539.webm")
    assert manifest_is_complete(m)


def test_a_gap_is_reported_not_decoded():
    from audio.local_tracks import manifest_is_complete, orphan_manifest
    m = orphan_manifest(_keys("abc", 20, skip={7}), "r1", "guest", "nerra_voices")
    assert m["missing"] == [7] and not manifest_is_complete(m)


def test_nothing_recorded_is_nothing():
    from audio.local_tracks import orphan_manifest
    assert orphan_manifest([], "r1", "guest", "nerra_voices") is None
    assert orphan_manifest(["nerra_voices/local/r1/guest/abc/manifest.json"], "r1", "guest", "x") is None


def test_post_production_adopts_before_building_tracks():
    i = POST.index("adopt_orphan_take(run, show, role)")
    assert i < POST.index("tracks = build_tracks(run, raw, workdir")
    assert 'if run.get(f"local_{role}_url"):' in POST


def test_a_clean_recording_gets_the_light_chain():
    assert 'LOCAL_SIDE = ("highpass=f=70,adeclick=w=75:t=2,volume={gain:.1f}dB,"' in ASSEMBLE
    assert '_TRACK_SOURCE.get(str(_src)) == "local"' in ASSEMBLE
    assert 'BALANCE_GLUE = "acompressor=threshold=-16dB:ratio=1.8' in ASSEMBLE
