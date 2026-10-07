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


def _tone_bursts(path, starts, sr=48000, total=20.0, hz=220.0, noise=0.0):
    import wave
    import numpy as np
    x = np.random.RandomState(1).randn(int(total * sr)).astype(np.float32) * noise
    for i, s in enumerate(starts):
        n = int((0.8 + 0.1 * (i % 3)) * sr)
        t = np.arange(n) / sr
        a = int(s * sr)
        x[a:a + n] += 8000 * np.sin(2 * np.pi * (hz + 40 * i) * t) * np.hanning(n)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(np.clip(x, -32768, 32767).astype(np.int16).tobytes())
    return path


def test_each_phrase_lands_where_the_call_has_it(tmp_path):
    """The call leg's delay wanders; one offset cannot fit every phrase."""
    import numpy as np
    from audio.local_tracks import _log_env, _pcm, place_phrases
    local_starts = [1.0, 4.0, 7.0, 10.0, 13.0]
    shifts = [0.0, 0.3, 0.3, 0.1, 0.45]          # the call is late, by varying amounts
    local = _tone_bursts(tmp_path / "local.wav", local_starts, noise=30)
    call = _tone_bursts(tmp_path / "call.wav", [s + d for s, d in zip(local_starts, shifts)], noise=30)
    out, stats = place_phrases(local, call, tmp_path / "placed.wav")
    env_out, env_call = _log_env(_pcm(out)), _log_env(_pcm(call))
    for s, d in zip(local_starts, shifts):
        i = int((s + d + 0.4) * 100)
        assert env_out[i] > 5 and env_call[i] > 5, (s, d)
        j = int((s + d - 0.15) * 100)            # just before the call's phrase
        assert env_out[j] < env_call[i] - 3, (s, d)


def test_the_room_is_kept_out_between_turns(tmp_path):
    import numpy as np
    from audio.local_tracks import _log_env, _pcm, gate_to_reference
    local = _tone_bursts(tmp_path / "local.wav", [2.0, 9.0], noise=300)   # a mic that hears the room
    call = _tone_bursts(tmp_path / "call.wav", [2.0, 9.0], noise=0)       # echo-cancelled
    out, stats = gate_to_reference(local, call, tmp_path / "gated.wav")
    e = _log_env(_pcm(out))
    assert e[int(2.4 * 100)] > 7                 # the speaker is kept
    assert e[int(6.0 * 100)] < 1                 # the room between turns is not


def test_post_production_places_and_gates_a_local_take():
    assert "place_phrases(guest, guest_vox" in POST
    assert "gate_to_reference(guest, guest_vox" in POST
