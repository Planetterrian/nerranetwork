"""Phase 2 co-host — pipeline side (docs/cohost_phase2_contract.md).

Pins the Python half of "Patrick in the room": local browser-recording
reassembly + alignment (pipelines/voices/audio/local_tracks.py), the
three-track mix, per-track diarization with speaker names, track-selection
precedence (local vs Voximplant), Mira's co-host prompt block, the host
link + SMS the fire step sends Patrick, the migration columns and the two
email templates. Audio tests use synthetic numpy signals and ffmpeg
(skipped when ffmpeg is not installed).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
PIPELINES = ROOT / "pipelines" / "voices"
MIGRATION = ROOT / "supabase" / "migrations" / "20260906_cohost_conference.sql"
EMAIL_TEMPLATES = ROOT / "templates" / "email"

sys.path.insert(0, str(PIPELINES))

FFMPEG = shutil.which("ffmpeg") is not None
needs_ffmpeg = pytest.mark.skipif(not FFMPEG, reason="ffmpeg not installed")

SR = 48000


# ---------------------------------------------------------------------------
# Synthetic audio helpers
# ---------------------------------------------------------------------------

def tone_bursts(seconds: float = 20.0, sr: int = SR, seed: int = 7) -> np.ndarray:
    """A speech-like pattern: irregular tone bursts at varying pitch with
    silence between them (an envelope with real structure to correlate)."""
    rng = np.random.default_rng(seed)
    out = np.zeros(int(seconds * sr), dtype=np.float32)
    t = 0.0
    while t < seconds - 0.5:
        dur = float(rng.uniform(0.15, 0.6))
        gap = float(rng.uniform(0.1, 0.5))
        f = float(rng.uniform(150, 900))
        n0, n1 = int(t * sr), min(int((t + dur) * sr), len(out))
        tt = np.arange(n1 - n0) / sr
        out[n0:n1] = 0.5 * np.sin(2 * np.pi * f * tt) * np.hanning(n1 - n0)
        t += dur + gap
    return out


def write_wav(path: Path, samples: np.ndarray, sr: int = SR,
              channels: int = 1) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(samples, -1, 1)
    if channels == 1:
        data = (pcm * 32767).astype("<i2").tobytes()
    else:
        data = (pcm * 32767).astype("<i2").tobytes()  # already interleaved
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data)
    return path


def read_wav(path: Path) -> tuple[np.ndarray, int, int]:
    with wave.open(str(path), "rb") as wf:
        sr, ch = wf.getframerate(), wf.getnchannels()
        data = np.frombuffer(wf.readframes(wf.getnframes()), dtype="<i2")
    return data.astype(np.float32) / 32768.0, sr, ch


def shift(samples: np.ndarray, seconds: float, sr: int = SR) -> np.ndarray:
    """Positive = prepend silence (track starts EARLIER than reference);
    negative = drop the head (track starts LATER)."""
    n = int(round(abs(seconds) * sr))
    if seconds >= 0:
        return np.concatenate([np.zeros(n, dtype=np.float32), samples])
    return samples[n:]


# ---------------------------------------------------------------------------
# local_tracks: alignment
# ---------------------------------------------------------------------------

@needs_ffmpeg
class TestAlignment:
    def test_offset_when_local_started_early(self, tmp_path):
        from audio.local_tracks import estimate_offset, align_to_reference
        ref = tone_bursts()
        ref_wav = write_wav(tmp_path / "ref.wav", ref)
        local_wav = write_wav(tmp_path / "local.wav", shift(ref, 1.3))
        offset, corr = estimate_offset(local_wav, ref_wav)
        assert abs(offset - 1.3) < 0.05, (offset, corr)
        assert corr > 0.5
        aligned = align_to_reference(local_wav, ref_wav, tmp_path / "al")
        a, sr, ch = read_wav(aligned)
        assert sr == 48000 and ch == 1
        # After alignment the burst pattern lines up with the reference.
        n = min(len(a), len(ref))
        lag = int(np.argmax(np.correlate(a[:SR * 5], ref[:SR * 5 - SR // 4],
                                         mode="valid")))
        assert lag < SR * 0.05, "aligned track still offset"
        assert abs(len(a) - len(ref)) < SR * 0.05

    def test_offset_when_local_started_late_pads(self, tmp_path):
        from audio.local_tracks import estimate_offset, align_to_reference
        ref = tone_bursts(seed=3)
        ref_wav = write_wav(tmp_path / "ref.wav", ref)
        local_wav = write_wav(tmp_path / "local.wav", shift(ref, -1.3))
        offset, _ = estimate_offset(local_wav, ref_wav)
        assert abs(offset + 1.3) < 0.05, offset
        aligned = align_to_reference(local_wav, ref_wav, tmp_path / "al")
        a, _, _ = read_wav(aligned)
        # Padded head is silence, then the pattern resumes on time.
        assert np.abs(a[:int(1.2 * SR)]).max() < 1e-3
        assert abs(len(a) - len(ref)) < SR * 0.05

    def test_low_correlation_falls_back_to_no_offset(self, tmp_path):
        from audio.local_tracks import align_to_reference
        ref_wav = write_wav(tmp_path / "ref.wav", tone_bursts(seed=1))
        rng = np.random.default_rng(0)
        noise = (rng.normal(0, 0.05, SR * 20)).astype(np.float32)
        local_wav = write_wav(tmp_path / "local.wav", noise)
        aligned = align_to_reference(local_wav, ref_wav, tmp_path / "al",
                                     min_correlation=0.9)
        a, _, _ = read_wav(aligned)
        assert abs(len(a) - SR * 20) < 10, "no offset must leave the length alone"

    def test_offset_is_clamped(self, tmp_path):
        from audio.local_tracks import estimate_offset, MAX_OFFSET_SEC
        ref = tone_bursts(seed=5)
        ref_wav = write_wav(tmp_path / "ref.wav", ref)
        local_wav = write_wav(tmp_path / "local.wav", shift(ref, 2.0))
        offset, _ = estimate_offset(local_wav, ref_wav, max_offset_sec=1.0)
        assert abs(offset) <= 1.0 + 1e-6
        assert MAX_OFFSET_SEC == 30.0


# ---------------------------------------------------------------------------
# local_tracks: manifest → concatenated WAV
# ---------------------------------------------------------------------------

def _encode_webm(wav: Path, out: Path) -> bytes:
    subprocess.run(["ffmpeg", "-y", "-i", str(wav), "-c:a", "libopus",
                    "-b:a", "96k", str(out)], check=True, capture_output=True)
    return out.read_bytes()


class TestFetchLocalTrack:
    def test_missing_manifest_returns_none(self, tmp_path):
        from audio.local_tracks import fetch_local_track
        assert fetch_local_track("aoa/local/run/guest/manifest.json", tmp_path,
                                 read_json=lambda k: None,
                                 download=lambda k, d: d) is None
        assert fetch_local_track("", tmp_path) is None

    def test_missing_chunk_returns_none_without_downloading(self, tmp_path):
        from audio.local_tracks import fetch_local_track
        manifest = {"role": "guest", "chunks": ["a/00000.webm", "a/00001.webm"],
                    "missing": ["a/00001.webm"]}
        calls = []
        out = fetch_local_track("k", tmp_path, read_json=lambda k: manifest,
                                download=lambda k, d: calls.append(k))
        assert out is None and calls == []

    def test_unreadable_manifest_returns_none(self, tmp_path):
        from audio.local_tracks import fetch_local_track

        def boom(k):
            raise RuntimeError("R2 down")
        assert fetch_local_track("k", tmp_path, read_json=boom) is None

    @needs_ffmpeg
    def test_concat_chunks_in_order_decodes_to_48k_mono(self, tmp_path):
        from audio.local_tracks import fetch_local_track
        src = write_wav(tmp_path / "src.wav", tone_bursts(seconds=6.0))
        blob = _encode_webm(src, tmp_path / "src.webm")
        # MediaRecorder timeslices are consecutive byte ranges of one
        # stream: slice the file into uneven chunks and hand them out by key.
        cuts = [0, len(blob) // 5, len(blob) // 2, (3 * len(blob)) // 4, len(blob)]
        chunks = {f"p/local/r/guest/{i:05d}.webm": blob[cuts[i]:cuts[i + 1]]
                  for i in range(4)}
        manifest = {"role": "guest", "chunks": list(chunks), "missing": [],
                    "mime": "audio/webm;codecs=opus", "duration_ms": 6000,
                    "started_at": "2026-09-06T17:00:00Z", "bytes": len(blob)}
        order = []

        def download(key, dest):
            order.append(key)
            Path(dest).write_bytes(chunks[key])
            return Path(dest)

        wav = fetch_local_track("p/local/r/guest/manifest.json", tmp_path,
                                read_json=lambda k: manifest, download=download)
        assert wav is not None and wav.exists()
        assert order == list(chunks)
        a, sr, ch = read_wav(wav)
        assert sr == 48000 and ch == 1
        assert abs(len(a) / SR - 6.0) < 0.2


# ---------------------------------------------------------------------------
# mix_three / split_left
# ---------------------------------------------------------------------------

@needs_ffmpeg
class TestMix:
    def test_mix_three_is_mono_48k_max_length(self, tmp_path):
        from audio.mix_tracks import mix_three
        g = write_wav(tmp_path / "g.wav", tone_bursts(seconds=4.0, seed=1))
        h = write_wav(tmp_path / "h.wav", tone_bursts(seconds=7.0, seed=2))
        m = write_wav(tmp_path / "m.wav", tone_bursts(seconds=5.0, seed=3))
        out = mix_three(g, h, m, tmp_path / "mix" / "mixed.wav")
        a, sr, ch = read_wav(out)
        assert sr == 48000 and ch == 1
        assert abs(len(a) / SR - 7.0) < 0.3, "longest input wins"
        assert np.abs(a).max() > 0.05

    def test_split_left_takes_left_channel(self, tmp_path):
        from audio.mix_tracks import split_left
        left = tone_bursts(seconds=3.0, seed=4)
        right = np.zeros_like(left)
        inter = np.empty(len(left) * 2, dtype=np.float32)
        inter[0::2], inter[1::2] = left, right
        stereo = write_wav(tmp_path / "s.wav", inter, channels=2)
        out = split_left(stereo, tmp_path / "l.wav")
        a, sr, ch = read_wav(out)
        assert sr == 48000 and ch == 1
        assert np.abs(a).max() > 0.3
        # mono input is passed through, not upmixed
        mono = write_wav(tmp_path / "m.wav", left)
        b, _, ch2 = read_wav(split_left(mono, tmp_path / "m_l.wav"))
        assert ch2 == 1 and abs(len(b) - len(left)) < 10


# ---------------------------------------------------------------------------
# post_interview: diarization + track selection (fakes, no ffmpeg/whisper)
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, json_path):
        self.json_path = json_path


def _fake_whisper(tmp_path, segments_by_stem):
    def generate_transcript(wav, out_dir, prefix, **kw):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / f"{prefix}.json"
        p.write_text(json.dumps({"segments": segments_by_stem[Path(wav).stem]}))
        return _FakeResult(p)
    return generate_transcript


class TestDiarization:
    def test_three_track_labels_and_header(self, tmp_path, monkeypatch):
        import engine.transcripts as et
        import post_interview as pi
        monkeypatch.setenv("COHOST_NAME", "Patrick Novak")
        monkeypatch.setattr(et, "generate_transcript", _fake_whisper(tmp_path, {
            "mira": [{"start": 0.5, "text": "Welcome to the show.", "avg_logprob": -0.2}],
            "host": [{"start": 12.0, "text": "Quick clarification.", "avg_logprob": -0.3}],
            "guest": [{"start": 4.0, "text": "Thanks for having me.", "avg_logprob": -0.1},
                      {"start": 70.0, "text": "", "avg_logprob": -0.9}],
        }))
        tracks = {"guest": tmp_path / "guest.wav", "host": tmp_path / "host.wav",
                  "mira": tmp_path / "mira.wav"}
        text, conf = pi.diarized_transcript_three(tracks, {"name": "Jane Doe"}, tmp_path)
        lines = text.splitlines()
        assert lines[0] == "Speakers: Mira (AI host), Patrick (co-host), Jane (guest)"
        assert lines[1:] == [
            "[00:00] Mira: Welcome to the show.",
            "[00:04] Jane: Thanks for having me.",
            "[00:12] Patrick: Quick clarification.",
        ]
        assert 0.7 < conf < 0.9

    def test_two_track_path_keeps_old_labels(self, tmp_path, monkeypatch):
        import engine.transcripts as et
        import post_interview as pi
        monkeypatch.setattr(et, "generate_transcript", _fake_whisper(tmp_path, {
            "guest": [{"start": 3.0, "text": "Hello."}],
            "mira": [{"start": 1.0, "text": "Hi there."}],
        }))
        monkeypatch.setattr(pi, "split_channels",
                            lambda raw, d: (tmp_path / "guest.wav", tmp_path / "mira.wav"))
        text, conf = pi.diarized_transcript(tmp_path / "raw.mp4", tmp_path)
        assert text == "[00:01] MIRA: Hi there.\n[00:03] GUEST: Hello."
        assert conf == 1.0


class TestTrackSelection:
    @pytest.fixture
    def fakes(self, tmp_path, monkeypatch):
        import post_interview as pi
        vox = {"guest_l": tmp_path / "ch" / "guest.wav",
               "guest_r": tmp_path / "ch" / "mira.wav"}
        monkeypatch.setattr(pi, "split_channels",
                            lambda raw, d: (vox["guest_l"], vox["guest_r"]))
        monkeypatch.setattr(pi, "split_left",
                            lambda src, out: Path(out))
        aligned = []

        def align(track, ref, workdir):
            aligned.append((Path(track).name, Path(ref).name))
            return Path(workdir) / (Path(track).stem + "_aligned.wav")
        monkeypatch.setattr(pi, "align_to_reference", align)
        local = {}
        monkeypatch.setattr(pi, "fetch_local_track",
                            lambda key, wd: local.get(key))
        return pi, vox, local, aligned

    def test_local_wins_and_is_aligned_to_voximplant_channel(self, fakes, tmp_path):
        pi, vox, local, aligned = fakes
        local["p/local/r/guest/manifest.json"] = tmp_path / "local_guest.wav"
        local["p/local/r/host/manifest.json"] = tmp_path / "local_host.wav"
        run = {"local_guest_url": "p/local/r/guest/manifest.json",
               "local_host_url": "p/local/r/host/manifest.json"}
        t = pi.build_tracks(run, tmp_path / "raw.mp4", tmp_path,
                            host_raw=tmp_path / "raw_host.mp3",
                            mira_raw=tmp_path / "raw_mira.mp3")
        assert t["sources"] == {"guest": "local", "host": "local", "mira": "voximplant"}
        assert t["guest"].name == "local_guest_aligned.wav"
        assert t["host"].name == "local_host_aligned.wav"
        assert t["mira"].name == "mira_leg.wav"
        assert ("local_guest.wav", "guest.wav") in aligned
        assert ("local_host.wav", "host.wav") in aligned

    def test_voximplant_fallback_per_track(self, fakes, tmp_path):
        pi, vox, local, aligned = fakes
        local["p/local/r/guest/manifest.json"] = tmp_path / "local_guest.wav"
        run = {"local_guest_url": "p/local/r/guest/manifest.json",
               "local_host_url": "p/local/r/host/manifest.json"}  # incomplete
        t = pi.build_tracks(run, tmp_path / "raw.mp4", tmp_path,
                            host_raw=tmp_path / "raw_host.mp3", mira_raw=None)
        assert t["sources"] == {"guest": "local", "host": "voximplant", "mira": "guest_r"}
        assert t["host"].name == "host.wav"
        assert t["mira"] == vox["guest_r"]

    def test_no_host_anywhere_means_two_track_path(self, fakes, tmp_path):
        pi, vox, local, aligned = fakes
        t = pi.build_tracks({}, tmp_path / "raw.mp4", tmp_path)
        assert t["host"] is None
        assert t["guest"] == vox["guest_l"] and t["mira"] == vox["guest_r"]
        assert t["sources"] == {"guest": "voximplant", "mira": "guest_r"}
        assert aligned == []

    def test_local_host_without_host_leg_aligns_to_guest_r(self, fakes, tmp_path):
        pi, vox, local, aligned = fakes
        local["h"] = tmp_path / "local_host.wav"
        t = pi.build_tracks({"local_host_url": "h"}, tmp_path / "raw.mp4", tmp_path)
        assert t["sources"]["host"] == "local"
        assert aligned == [("local_host.wav", "mira.wav")]

    def test_leg_recording_fetch_is_best_effort(self, tmp_path, monkeypatch):
        import post_interview as pi
        assert pi.fetch_leg_recording("", tmp_path, "host") is None

        def small(url, dest, timeout=600):
            Path(dest).write_bytes(b"x" * 100)
            return Path(dest)
        monkeypatch.setattr(pi, "_download", small)
        assert pi.fetch_leg_recording("https://x/host.mp3", tmp_path, "host") is None

        def boom(url, dest, timeout=600):
            raise RuntimeError("404")
        monkeypatch.setattr(pi, "_download", boom)
        assert pi.fetch_leg_recording("https://x/host.mp3", tmp_path, "host") is None

        def ok(url, dest, timeout=600):
            Path(dest).write_bytes(b"x" * 60_000)
            return Path(dest)
        monkeypatch.setattr(pi, "_download", ok)
        got = pi.fetch_leg_recording("https://x/mira.mp3?sig=1", tmp_path, "mira")
        assert got is not None and got.name == "raw_mira.mp3"

    def test_editorial_passes_get_cohost_name(self):
        src = (PIPELINES / "post_interview.py").read_text(encoding="utf-8")
        assert "cohost_name=cohost_name()" in src
        for f in ("01_clean_transcript.txt", "02_chapter_markers.txt",
                  "03_episode_notes.txt", "05_suggest_clips.txt"):
            assert "{{cohost_name}}" in (
                PIPELINES / "prompts" / "editorial_passes" / f).read_text(encoding="utf-8")

    def test_main_uploads_three_raw_tracks_and_mixes_three(self):
        src = (PIPELINES / "post_interview.py").read_text(encoding="utf-8")
        assert 'f"{run[\'id\']}_{speaker}.wav"' in src
        assert "mix_three(tracks[\"guest\"], tracks[\"host\"], tracks[\"mira\"]" in src
        assert "mix_interview(raw, workdir / \"mixed.wav\")" in src, "two-track fallback"


# ---------------------------------------------------------------------------
# Mira prompt co-host block
# ---------------------------------------------------------------------------

_APP = {"name": "Jane Doe", "title": "Welder", "organization": "Doe Fabrication"}
_BRIEF = {"bio_research": "BRIEF-X", "likely_questions": ["Q-ONE?"]}


class TestCohostPrompt:
    def test_template_has_token(self):
        text = (PIPELINES / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
        assert "{{cohost_block}}" in text

    def test_block_present_by_default(self, monkeypatch):
        monkeypatch.delenv("COHOST_NAME", raising=False)
        from fire_interviews import compile_mira_prompt
        prompt = compile_mira_prompt({"episode_thesis": "T"}, _APP, _BRIEF)
        assert "CO-HOST: Patrick Novak, the network's founder, is in the room as your co-host." in prompt
        assert "never interview Patrick, never ask him the lightning round" in prompt
        assert "If Patrick says 'let's pause' or 'hold on', stop talking and wait for him." in prompt
        assert "{{" not in prompt

    def test_block_present_when_host_mode_true(self):
        from fire_interviews import compile_mira_prompt
        prompt = compile_mira_prompt({"episode_thesis": "T", "host_mode": True}, _APP, _BRIEF)
        assert "CO-HOST:" in prompt and "{{" not in prompt

    def test_block_absent_when_host_mode_false(self):
        from fire_interviews import compile_mira_prompt
        prompt = compile_mira_prompt({"episode_thesis": "T", "host_mode": False}, _APP, _BRIEF)
        assert "CO-HOST:" not in prompt and "Patrick" not in prompt
        assert "{{" not in prompt

    def test_cohost_name_from_env(self, monkeypatch):
        monkeypatch.setenv("COHOST_NAME", "Pat Example")
        from fire_interviews import compile_mira_prompt
        prompt = compile_mira_prompt({"episode_thesis": "T"}, _APP, _BRIEF)
        assert "CO-HOST: Pat Example," in prompt and "never interview Pat," in prompt

    def test_load_prompt_fills_cohost_name_everywhere(self):
        from common import load_prompt
        from pipelines.voices.shows import VOICE_SHOW_SLUGS, get_show
        for slug in VOICE_SHOW_SLUGS:
            for t in ("editorial_passes/01_clean_transcript.txt",
                      "editorial_passes/03_episode_notes.txt",
                      "mira_system_prompt.txt"):
                text = load_prompt(t, show=get_show(slug))
                assert "{{cohost_name}}" not in text and "{{cohost_block}}" not in text


# ---------------------------------------------------------------------------
# Fire: host link, run row, notifications
# ---------------------------------------------------------------------------

class TestFireHostLink:
    def test_host_link_shape(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "sekrit")
        from fire_interviews import host_link
        from pipelines.voices.shows import get_show
        show = get_show("age_of_ai")
        url = host_link(show, "abc-123")
        assert url == show.studio_url("abc-123") + "&role=host&token=sekrit"
        assert "interview=abc-123" in url and "show=age_of_ai" in url

    def test_host_link_requires_admin_token(self, monkeypatch):
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        from fire_interviews import host_link
        from pipelines.voices.shows import get_show
        with pytest.raises(RuntimeError):
            host_link(get_show("age_of_ai"), "x")

    def test_notify_host_sends_email_and_sms(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "tok")
        monkeypatch.setenv("OPERATOR_PHONE", "+16045551234")
        monkeypatch.setenv("VOXIMPLANT_CALLER_ID", "+16045550000")
        monkeypatch.delenv("COHOST_NAME", raising=False)
        import fire_interviews as fi
        from pipelines.voices.shows import get_show
        emails, smss = [], []
        monkeypatch.setattr(fi, "send_email", lambda to, subj, html: emails.append((to, subj, html)))
        import voximplant.api_clients.voximplant_client as vc
        monkeypatch.setattr(vc, "send_sms",
                            lambda dest, text, source_number=None: smss.append((dest, text, source_number)))
        show = get_show("nerra_voices")
        interview = {"id": "iv-1", "scheduled_at": "2026-09-10T17:00:00Z"}
        fi.notify_host(interview, {"name": "Jane Doe"}, show, when="in 2 min")
        assert len(emails) == 1 and len(smss) == 1
        to, subj, html = emails[0]
        assert to == fi.OPERATOR_EMAIL
        assert "Jane Doe" in subj and "co-host" in subj
        assert "&amp;role=host&amp;token=tok" in html  # jinja autoescape
        assert "Ready" in html and "hold on" in html
        dest, text, src = smss[0]
        assert dest == "+16045551234" and src == "+16045550000"
        assert text == ("Nerra Voices: Jane Doe in 2 min. Your co-host link: "
                        + show.studio_url("iv-1") + "&role=host&token=tok")

    def test_notify_host_skips_sms_without_phone(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "tok")
        monkeypatch.delenv("OPERATOR_PHONE", raising=False)
        import fire_interviews as fi
        from pipelines.voices.shows import get_show
        emails = []
        monkeypatch.setattr(fi, "send_email", lambda to, subj, html: emails.append(to))
        import voximplant.api_clients.voximplant_client as vc
        monkeypatch.setattr(vc, "send_sms", lambda *a, **k: pytest.fail("no SMS expected"))
        fi.notify_host({"id": "iv", "scheduled_at": ""}, {"name": "J"},
                       get_show("age_of_ai"), when="in about 2 hours")
        assert emails == [fi.OPERATOR_EMAIL]

    def test_notify_host_never_raises(self, monkeypatch):
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        import fire_interviews as fi
        pings = []
        monkeypatch.setattr(fi, "notify_operator", lambda t, critical=False: pings.append(t))
        from pipelines.voices.shows import get_show
        fi.notify_host({"id": "iv"}, {"name": "J"}, get_show("age_of_ai"), when="in 2 min")
        assert pings and "NOT sent" in pings[0]

    def test_run_row_and_reminder_wiring(self):
        src = (PIPELINES / "fire_interviews.py").read_text(encoding="utf-8")
        assert '"host_mode": host_mode,' in src
        assert '"host_user": os.environ.get("VOX_HOST_USER", "").strip() or "host",' in src
        assert 'notify_host(interview, app, show, when="in 2 min")' in src
        assert 'notify_host(interview, app, show, when="in about 2 hours")' in src
        assert "ADMIN_TOKEN" in src

    def test_host_mode_enabled_semantics(self):
        from fire_interviews import host_mode_enabled
        assert host_mode_enabled({}) is True
        assert host_mode_enabled({"host_mode": None}) is True
        assert host_mode_enabled({"host_mode": False}) is False
        assert host_mode_enabled({"host_mode": True}, {"host_mode": False}) is False


# ---------------------------------------------------------------------------
# Migration + templates + common
# ---------------------------------------------------------------------------

class TestMigrationAndTemplates:
    def test_migration_columns(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        for col in ("host_mode", "host_user", "recording_host_url",
                    "recording_mira_url", "local_guest_url", "local_host_url",
                    "guest_joined_at", "host_joined_at", "host_left_at",
                    "host_attempts"):
            assert f"add column if not exists {col}" in sql, col
        assert "host_user text not null default 'host'" in sql

    def test_host_link_template_renders(self):
        from common import render_email
        html = render_email("voices_host_link.j2", show="nerra_voices",
                            host_url="https://x/studio?interview=1&show=nerra_voices&role=host&token=t",
                            guest_name="Jane <Doe>", scheduled_at="Thu 10 Sep, 10:00 PT",
                            cohost_name="Patrick Novak", when="in 2 min")
        assert "{{" not in html and "}}" not in html
        assert "Jane &lt;Doe&gt;" in html
        assert "role=host&amp;token=t" in html
        assert "#0F766E" in html and "Nerra Voices" in html
        for needle in ("few minutes early", "Ready", "hold on", "20 s"):
            assert needle in html, needle

    def test_prep_brief_mentions_cohost_only_when_given(self):
        from common import render_email
        base = dict(guest_name="J", scheduled_at="soon", thesis="T",
                    questions=["Q?"], closing_question="C?")
        with_host = render_email("voices_prep_brief.j2", show="age_of_ai",
                                 cohost_name="Patrick Novak", **base)
        without = render_email("voices_prep_brief.j2", show="age_of_ai", **base)
        assert "Patrick Novak" in with_host and "co-host" in with_host
        assert "co-host" not in without
        assert "{{" not in with_host

    def test_common_accessors(self, monkeypatch):
        import common
        monkeypatch.delenv("COHOST_NAME", raising=False)
        monkeypatch.delenv("OPERATOR_PHONE", raising=False)
        assert common.cohost_name() == "Patrick Novak"
        assert common.cohost_label() == "Patrick"
        assert common.operator_phone() == ""
        monkeypatch.setenv("OPERATOR_PHONE", " +1604 ")
        assert common.operator_phone() == "+1604"
        assert callable(common.r2_download) and callable(common.r2_read_json)

    def test_r2_read_json_returns_none_on_missing_key(self, monkeypatch):
        import common

        class _Exc(Exception):
            response = {"Error": {"Code": "NoSuchKey"}}

        class _S3:
            def get_object(self, Bucket, Key):
                raise _Exc("missing")
        monkeypatch.setattr(common, "_r2_client", lambda: (_S3(), "b"))
        assert common.r2_read_json("nope.json") is None

    def test_docs_updated(self):
        res = (ROOT / "docs" / "age_of_ai_resilience.md").read_text(encoding="utf-8")
        assert "re-dials the `host` user every 20 s" in res
        assert "Fallback is PER TRACK" in res
        plan = (ROOT / "docs" / "age_of_ai_plan.md").read_text(encoding="utf-8")
        for needle in ("add_user", "VOX_HOST_USER", "VOICES_R2", "ADMIN_TOKEN",
                       "OPERATOR_PHONE", "20260906_cohost_conference.sql",
                       "Three dry runs"):
            assert needle in plan, needle
        nv = (ROOT / "docs" / "nerra_voices.md").read_text(encoding="utf-8")
        assert "co-host flow" in nv
