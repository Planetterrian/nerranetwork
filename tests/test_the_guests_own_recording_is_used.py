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
    assert 'LOCAL_SIDE = (LOCAL_DENOISE + "highpass=f=70,adeclick=w=75:t=2,volume={gain:.1f}dB,"' in ASSEMBLE
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


def _tones(path, spans, sr=48000, total=6.0):
    """Steady tones, one per ``(start, end, hz)``."""
    import wave
    import numpy as np
    x = np.zeros(int(total * sr), dtype=np.float32)
    for a, b, hz in spans:
        t = np.arange(int((b - a) * sr)) / sr
        x[int(a * sr):int(a * sr) + len(t)] += 6000 * np.sin(2 * np.pi * hz * t)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(np.clip(x, -32768, 32767).astype(np.int16).tobytes())
    return path


def test_the_hold_does_not_carry_the_room_into_the_take(tmp_path):
    """Oct 7 2026, Vincent Rylan: no echo cancellation on his take, so the
    hold after each of his sentences carried the start of Mira's reply."""
    from audio.local_tracks import _log_env, _pcm, gate_to_reference
    # He speaks 1.0-2.0 and again 3.0-4.0; Mira replies at 2.0 and talks
    # over his second turn from 3.2 to 3.6. His speakers put her in his take
    # a fifth of a second late.
    local = _tones(tmp_path / "local.wav", [(1.0, 2.0, 220), (2.2, 2.9, 330),
                                             (3.0, 4.0, 220), (3.4, 3.8, 330)])
    call = _tones(tmp_path / "call.wav", [(1.0, 2.0, 220), (3.0, 4.0, 220)])
    heard = _tones(tmp_path / "heard.wav", [(2.0, 2.7, 330), (3.2, 3.6, 330)])
    plain = _log_env(_pcm(gate_to_reference(local, call, tmp_path / "a.wav")[0]))
    out, stats = gate_to_reference(local, call, tmp_path / "b.wav", heard_wav=heard)
    e = _log_env(_pcm(out))
    assert plain[int(2.23 * 100)] > 7            # the old hold kept her echo
    assert e[int(2.23 * 100)] < 1                # the new one does not
    assert e[int(1.5 * 100)] > 7                 # his words are kept
    assert e[int(3.5 * 100)] > 7                 # including over the top of her
    assert stats["room_playing_sec"] > 0


def test_post_production_tells_the_gate_what_the_guest_heard():
    assert "heard_wav=guest_r" in POST


def test_a_stereo_recording_can_carry_the_guests_own_take():
    """The run's per-speaker tracks are not on the room's clock, so the
    rebuild keeps the stereo recording's right side and swaps the left."""
    assert 'cut.get("left_source") == "local"' in ASSEMBLE
    assert "left_chain = (LOCAL_SIDE.format(gain=gl)" in ASSEMBLE


def test_a_rebuilt_leg_still_ends_on_the_last_word():
    """A URL source with balance is a conversation cut, so the episode's last
    cut is measured from the audio rather than trusted from the transcript."""
    assert "or bool(c.get(\"balance\"))" in ASSEMBLE
    assert "if i == last_conversation and _is_conversation(cut):" in ASSEMBLE


def test_a_published_episode_keeps_its_address_when_its_audio_is_rebuilt():
    sys.path.insert(0, str(ROOT))
    from replace_published_audio import _key, rewrite_feed_item
    rss = ("<rss><channel><item><title>Ep6</title><enclosure url=\"https://op3.dev/e/"
           "audio.nerranetwork.com/age_of_ai/raw/a_edit_1.mp3\" length=\"10\" type=\"audio/mpeg\" />"
           "<itunes:duration>40:00</itunes:duration></item>"
           "<item><title>Ep7</title><enclosure url=\"https://op3.dev/e/"
           "audio.nerranetwork.com/age_of_ai/raw/b_edit_2.mp3\" length=\"44250285\" type=\"audio/mpeg\" />"
           "<itunes:duration>46:05</itunes:duration></item></channel></rss>")
    key = _key("https://audio.nerranetwork.com/age_of_ai/raw/b_edit_2.mp3")
    assert key == "age_of_ai/raw/b_edit_2.mp3"
    out = rewrite_feed_item(rss, key, 43000000, "45:30")
    assert 'b_edit_2.mp3" length="43000000"' in out and "<itunes:duration>45:30<" in out
    assert 'a_edit_1.mp3" length="10"' in out and "<itunes:duration>40:00<" in out
    assert out.count("<item>") == 2


def test_talking_over_the_room_comes_from_the_call_leg(tmp_path):
    """Where a take that hears the room overlaps someone else, the
    echo-cancelled call leg stands in for those frames only."""
    import numpy as np
    from audio.local_tracks import _pcm, gate_to_reference
    spans_room = [(a, a + 0.6, 330) for a in np.arange(6.0, 14.0, 1.0)]
    his = [(a, a + 0.6, 220) for a in np.arange(0.5, 5.5, 1.0)]
    # The take hears every room phrase a fifth of a second late, as loud as him,
    # and he says one word (5.6-6.2) over the first of them.
    local = _tones(tmp_path / "local.wav", his + [(5.6, 6.2, 220)]
                   + [(a + 0.2, b + 0.2, hz) for a, b, hz in spans_room], total=16.0)
    call = _tones(tmp_path / "call.wav", his + [(5.6, 6.2, 220)], total=16.0)
    heard = _tones(tmp_path / "heard.wav", spans_room, total=16.0)
    out, stats = gate_to_reference(local, call, tmp_path / "g.wav", heard_wav=heard)
    assert stats["talk_over_from_call_sec"] >= 0.25         # 5.9-6.2: the overlap
    x, c = _pcm(out).astype(float), _pcm(call).astype(float)
    seg = slice(int(6.0 * 48000), int(6.15 * 48000))      # his word, over her echo
    assert np.corrcoef(x[seg], c[seg])[0, 1] > 0.95        # it is the call leg's word
    room = slice(int(8.3 * 48000), int(8.6 * 48000))       # only the room: muted
    assert np.abs(x[room]).max() < 1


def test_a_take_with_headphones_keeps_its_own_audio_over_the_room(tmp_path):
    from audio.local_tracks import gate_to_reference
    import numpy as np
    spans_room = [(a, a + 0.6, 330) for a in np.arange(6.0, 14.0, 1.0)]
    his = [(a, a + 0.6, 220) for a in np.arange(0.5, 5.5, 1.0)]
    local = _tones(tmp_path / "local.wav", his + [(5.6, 6.2, 220)], total=16.0)
    call = _tones(tmp_path / "call.wav", his + [(5.6, 6.2, 220)], total=16.0)
    heard = _tones(tmp_path / "heard.wav", spans_room, total=16.0)
    out, stats = gate_to_reference(local, call, tmp_path / "g.wav", heard_wav=heard)
    assert stats["talk_over_from_call_sec"] == 0


def test_a_browser_take_is_lightly_denoised_with_the_model_we_ship():
    import assemble_edit as A
    assert A._RNNOISE_MODEL.exists(), A._RNNOISE_MODEL
    assert A.LOCAL_SIDE.startswith(f"arnndn=m={A._RNNOISE_MODEL}:mix=0.7,highpass=f=70,")
    assert "{gain:.1f}" in A.LOCAL_SIDE and "{" not in str(A._RNNOISE_MODEL)


def test_the_stereo_fallback_uses_the_guests_own_take_when_there_is_one():
    """Oct 7 2026, Scott Pulcini: Mira could not be placed, so the edit was cut
    from his leg, and that path never looked at his browser take."""
    auto = (V / "auto_edit.py").read_text(encoding="utf-8")
    body = auto[auto.index("def build("):]
    body = body[:body.index("\ndef ", 1)]
    assert '.get("leg_local") or {}).get("url")' in body
    assert '"left_source": "local"} if leg_local else' in body
    assert '{"from": "run:guest", "balance": True, "voice_match": "right"})' in body
    assert 'session_log["tracks"]["leg_local"] = leg_local' in POST
    assert 'if tracks["sources"].get("guest") == "local":' in POST


def test_the_leg_file_puts_the_take_left_and_the_room_right(tmp_path):
    import subprocess
    import numpy as np
    from post_interview import build_leg_local
    from audio.local_tracks import _pcm
    take = _tones(tmp_path / "take.wav", [(0.5, 1.5, 220)], total=3.0)
    left = _tones(tmp_path / "callmic.wav", [(0.5, 1.5, 230)], total=3.0)
    right = _tones(tmp_path / "heard.wav", [(1.8, 2.6, 330)], total=3.0)
    leg = tmp_path / "leg.mp3"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(left), "-i", str(right),
                    "-filter_complex", "[0:a][1:a]join=inputs=2:channel_layout=stereo[a]",
                    "-map", "[a]", "-c:a", "libmp3lame", "-b:a", "192k", str(leg)], check=True)
    out = build_leg_local(take, leg, tmp_path / "leg_local.flac")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=channels,sample_rate",
                            "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    assert probe == "48000,2"
    l = _pcm_side(out, 0, tmp_path); r = _pcm_side(out, 1, tmp_path)
    t = _pcm(take).astype(float)
    assert np.corrcoef(l[24000:72000], t[24000:72000])[0, 1] > 0.99   # the take, not the call mic
    assert np.abs(r[int(2.0 * 48000):int(2.4 * 48000)]).max() > 1000   # the room as heard
    assert np.abs(r[int(0.8 * 48000):int(1.2 * 48000)]).max() < 300


def _pcm_side(path, ch, tmp_path):
    import subprocess
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-af",
                          f"pan=mono|c0=c{ch}", "-ar", "48000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(float)
