"""The voice chain's compressor is a NAMED stage, and the 2:1 glue is on
trial on two shows (Nov 3 2026, six-month review, audio-3).

Every show sounds pressed: a loudness range of 1.6-3.0 LU against 4.9-5.2 on
NPR News Now and Up First, and 90-99% of a show's 3-second windows within
2 LU of the integrated value against 75% on NPR. One stage is the cause —
the chain's ``acompressor=threshold=-20dB:ratio=4`` (NPR's own file keeps
LRA 4.7 through the final loudnorm alone, 4.8 through the chain with no
compressor, 2.8 through the 4:1 and 4.1 through the 2:1 soft knee on the
same pre-stages). The operator has heard this stage as a defect once
already ("crushing voice dynamics", May 8 2026 — attack and makeup moved;
threshold and ratio never did).

Rules these tests pin:

* ``engine.audio.VOICE_DYNAMICS`` names the stage; ``DEFAULT_VOICE_DYNAMICS``
  is what the network ships; ``voice_chain_filters()`` with no ``dynamics``
  is the pinned LEGACY chain byte for byte.
* Every surface with no setting of its own follows the module default —
  Nerra Daily's Mira pieces and the translated tracks change only when the
  constant does. The network flips by one constant, never per surface.
* The trial is ``audio.voice_dynamics: glue`` on Tesla (Patrick, music) and
  Top World (Mira, music) ONLY — no ``_defaults.yaml`` change until the
  operator's A/B listen; every other show resolves ``""``.
* run_show, the repair tool and the specials pass the show's value; an
  unknown name raises at load, never ships the legacy chain under the
  trial's label.
* Through the real ffmpeg, a speech-shaped signal keeps LRA >= 4.0 through
  the glue chain and <= 3.0 through the legacy one.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")

#: The chain every show shipped from the May 8 2026 retune to Nov 3 2026.
LEGACY_CHAIN = (
    "afade=t=in:st=0:d=0.05:curve=tri,"
    "highpass=f=80,lowpass=f=15000,"
    "adeclick,afftdn=nr=9:nf=-42:tn=1,"
    "loudnorm=I=-18:TP=-1.5:LRA=11:linear=true,"
    "acompressor=threshold=-20dB:ratio=4:attack=10:release=100:makeup=1,"
    "alimiter=level_in=1:level_out=0.95:limit=0.95"
)
TRIAL_SHOWS = ("tesla", "omni_view_world")


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _show_yamls():
    for path in sorted((ROOT / "shows").glob("*.yaml")):
        if path.name.startswith("_") or path.stem in ("age_of_ai", "nerra_voices"):
            continue
        yield path


# ---------------------------------------------------------------------------
# The stage is named
# ---------------------------------------------------------------------------

class TestTheStageIsNamed:
    def test_the_vocabulary_is_closed_and_the_default_is_legacy(self):
        from engine.audio import DEFAULT_VOICE_DYNAMICS, VOICE_DYNAMICS

        assert set(VOICE_DYNAMICS) == {"legacy", "glue"}
        assert DEFAULT_VOICE_DYNAMICS == "legacy"
        assert VOICE_DYNAMICS["legacy"] == (
            "acompressor=threshold=-20dB:ratio=4:attack=10:release=100:makeup=1")

    def test_no_argument_is_the_legacy_chain_byte_for_byte(self):
        from engine.audio import voice_chain_filters

        assert voice_chain_filters() == LEGACY_CHAIN
        assert voice_chain_filters(dynamics=None) == LEGACY_CHAIN
        assert voice_chain_filters(dynamics="") == LEGACY_CHAIN
        assert voice_chain_filters(dynamics="legacy") == LEGACY_CHAIN

    def test_the_glue_is_two_to_one_with_a_soft_knee(self):
        from engine.audio import VOICE_DYNAMICS, voice_chain_filters

        glue = voice_chain_filters(dynamics="glue")
        stage = VOICE_DYNAMICS["glue"]
        assert stage in glue
        for part in ("threshold=-12dB", "ratio=2", "knee=6"):
            assert part in stage
        assert "ratio=4" not in glue and "makeup" not in glue
        # The two chains differ in the compressor and nowhere else.
        assert glue.replace(stage, VOICE_DYNAMICS["legacy"]) == LEGACY_CHAIN

    @pytest.mark.parametrize("dynamics", ["legacy", "glue"])
    def test_the_order_holds_for_both(self, dynamics):
        from engine.audio import voice_chain_filters

        af = voice_chain_filters(dynamics=dynamics)
        assert af.count("acompressor=") == 1
        assert af.index("afftdn") < af.index("loudnorm") < af.index("acompressor")
        assert af.index("acompressor") < af.index("alimiter")

    def test_declick_and_denoise_compose_with_dynamics(self):
        from engine.audio import VOICE_DYNAMICS, voice_chain_filters

        af = voice_chain_filters(denoise=False, declick="strong", dynamics="glue")
        assert "adeclick" not in af and "afftdn" not in af
        assert VOICE_DYNAMICS["glue"] in af
        af = voice_chain_filters(declick="strong", dynamics="glue")
        assert "adeclick=w=75:t=2" in af and VOICE_DYNAMICS["glue"] in af

    def test_an_unknown_name_raises(self):
        from engine.audio import VOICE_DYNAMICS, voice_chain_filters, voice_dynamics_filter

        assert voice_dynamics_filter() == voice_dynamics_filter(None) == VOICE_DYNAMICS["legacy"]
        assert voice_dynamics_filter("") == VOICE_DYNAMICS["legacy"]
        with pytest.raises(ValueError):
            voice_dynamics_filter("gluee")
        with pytest.raises(ValueError):
            voice_chain_filters(dynamics="Glue")


# ---------------------------------------------------------------------------
# Every surface reads the module default
# ---------------------------------------------------------------------------

class TestEverySurfaceReadsTheModuleDefault:
    def _mira_af(self) -> str:
        from engine.daily_edition import mira_piece_cmd

        cmd = mira_piece_cmd(Path("in.wav"), Path("out.flac"))
        return cmd[cmd.index("-af") + 1]

    def _master_af(self, monkeypatch, tmp_path, **kw) -> str:
        from engine import audio

        seen = {}
        monkeypatch.setattr(audio.subprocess, "run", lambda cmd, **k: seen.setdefault("cmd", cmd))
        monkeypatch.setattr(audio, "get_audio_duration", lambda p: 60.0)
        audio.master_voice_track(tmp_path / "in.wav", tmp_path / "out.mp3", **kw)
        return seen["cmd"][seen["cmd"].index("-af") + 1]

    def test_mira_pieces_follow_the_constant(self, monkeypatch):
        from engine import audio

        assert audio.VOICE_DYNAMICS["legacy"] in self._mira_af()
        monkeypatch.setattr(audio, "DEFAULT_VOICE_DYNAMICS", "glue")
        af = self._mira_af()
        assert audio.VOICE_DYNAMICS["glue"] in af
        assert audio.VOICE_DYNAMICS["legacy"] not in af
        # Her piece carries the chain, then the published loudness, unchanged.
        assert af.startswith(audio.voice_chain_filters(declick="strong"))
        assert ",loudnorm=I=-16:TP=-1.5:LRA=11,adelay" in af

    def test_the_master_follows_the_constant_and_takes_an_override(self, monkeypatch, tmp_path):
        from engine import audio

        legacy = self._master_af(monkeypatch, tmp_path)
        assert legacy == LEGACY_CHAIN + "," + audio.PUBLISHED_LOUDNESS
        glue = self._master_af(monkeypatch, tmp_path, dynamics="glue")
        assert glue == audio.voice_chain_filters(dynamics="glue") + "," + audio.PUBLISHED_LOUDNESS
        monkeypatch.setattr(audio, "DEFAULT_VOICE_DYNAMICS", "glue")
        assert self._master_af(monkeypatch, tmp_path) == glue

    def test_the_translated_tracks_pass_no_setting_of_their_own(self):
        src = _read("engine/multilingual.py")
        assert "master_voice_track(raw, out_path)" in src
        src = _read("engine/daily_edition.py")
        body = src[src.index("def mira_piece_cmd"):src.index("# Chapters")]
        assert 'voice_chain_filters(declick="strong")' in body
        assert "dynamics" not in body

    def test_normalize_voice_forwards_it_to_the_command(self, monkeypatch, tmp_path):
        from engine import audio

        seen = []
        monkeypatch.setattr(audio.subprocess, "run", lambda cmd, **k: seen.append(cmd))
        monkeypatch.setattr(audio, "get_audio_duration", lambda p: 60.0)
        audio.normalize_voice(tmp_path / "in.wav", tmp_path / "out.wav", dynamics="glue")
        af = seen[0][seen[0].index("-af") + 1]
        assert af == audio.voice_chain_filters(dynamics="glue")
        seen.clear()
        audio.normalize_voice(tmp_path / "in.wav", tmp_path / "out.wav")
        assert seen[0][seen[0].index("-af") + 1] == LEGACY_CHAIN

    def test_mix_with_music_forwards_it(self, monkeypatch, tmp_path):
        from engine import audio

        seen = {}

        def fake_normalize(voice_path, output_path, **kw):
            seen.update(kw)
            return output_path

        monkeypatch.setattr(audio, "normalize_voice", fake_normalize)
        voice = tmp_path / "voice.mp3"
        voice.write_bytes(b"x")
        audio.mix_with_music(voice, tmp_path / "no_such_music.mp3", tmp_path / "out.mp3",
                             dynamics="glue")
        assert seen["dynamics"] == "glue"
        seen.clear()
        audio.mix_with_music(voice, tmp_path / "no_such_music.mp3", tmp_path / "out.mp3")
        assert seen["dynamics"] is None


# ---------------------------------------------------------------------------
# The trial is two shows' YAML
# ---------------------------------------------------------------------------

class TestTheTrialIsTwoShows:
    def test_tesla_and_top_world_and_no_other(self):
        from engine.audio import VOICE_DYNAMICS
        from engine.config import load_config

        seen = {}
        for path in _show_yamls():
            cfg = load_config(str(path))
            seen[path.stem] = cfg.audio.voice_dynamics
            assert cfg.audio.voice_dynamics in ("", *VOICE_DYNAMICS), path.stem
        for slug in TRIAL_SHOWS:
            assert seen[slug] == "glue", slug
        others = {s: v for s, v in seen.items() if s not in TRIAL_SHOWS}
        assert others and all(v == "" for v in others.values()), {
            s: v for s, v in others.items() if v}
        # The DP Pod is upstream of _match_turn_levels and NOT a trial show.
        assert seen["dp_pod"] == ""

    def test_the_network_default_is_untouched_until_the_listen(self):
        from engine.audio import DEFAULT_VOICE_DYNAMICS
        from engine.config import AudioConfig

        defaults = yaml.safe_load(_read("shows/_defaults.yaml")) or {}
        assert "voice_dynamics" not in (defaults.get("audio") or {})
        assert AudioConfig().voice_dynamics == ""
        assert DEFAULT_VOICE_DYNAMICS == "legacy"

    def test_an_unknown_value_raises_at_load(self, tmp_path):
        from engine.config import load_config

        show = tmp_path / "trial.yaml"
        show.write_text(yaml.safe_dump({"name": "T", "slug": "t",
                                        "audio": {"voice_dynamics": "gluee"}}),
                        encoding="utf-8")
        with pytest.raises(ValueError, match="voice_dynamics"):
            load_config(str(show))
        show.write_text(yaml.safe_dump({"name": "T", "slug": "t",
                                        "audio": {"voice_dynamics": "Glue"}}),
                        encoding="utf-8")
        assert load_config(str(show)).audio.voice_dynamics == "glue"

    def test_run_show_and_the_repair_tool_and_the_specials_pass_it(self):
        assert _read("run_show.py").count("dynamics=config.audio.voice_dynamics or None") == 3
        assert _read("scripts/resynthesize_episode.py").count(
            "dynamics=config.audio.voice_dynamics or None") == 2
        assert _read("scripts/produce_special.py").count(
            'dynamics=getattr(a, "voice_dynamics", "") or None') == 2


# ---------------------------------------------------------------------------
# Through the real ffmpeg
# ---------------------------------------------------------------------------

def _speech_shaped_fixture(path: Path) -> None:
    """A read, not a tone: pink noise (a speech-like crest factor) gated into
    0.3 s words with 0.1 s gaps, ten 3 s sentences each opening on a 0.6 s
    pause, at sentence levels spanning 10 dB. Its loudness range is ~7 LU,
    the shape of an expressive read; through the chain's loudnorm alone it
    keeps ~5.8 (the stepped-tone fixtures the review tried were flattened
    by the loudnorm itself and said nothing about the compressor)."""
    levels_db = [0, -6, -2, -10, -3, -8, -1, -9, -5, -4]
    sent, pause, word, gap = 3.0, 0.6, 0.4, 0.1
    gains = [10 ** (db / 20) for db in levels_db]
    env = f"{gains[-1]:.4f}"
    for i in range(len(gains) - 2, -1, -1):
        env = f"if(lt(t,{(i + 1) * sent}),{gains[i]:.4f},{env})"
    gate = f"gt(mod(t,{word}),{gap})*gt(mod(t,{sent}),{pause})"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         f"anoisesrc=d={len(levels_db) * sent}:c=pink:a=0.8:r=48000:s=5",
         "-af", f"volume='({env})*({gate})':eval=frame,volume=0.5",
         "-ac", "1", "-c:a", "pcm_s16le", str(path)],
        check=True)


@needs_ffmpeg
class TestTheGlueKeepsTheRange:
    def test_glue_keeps_four_lu_and_legacy_presses_under_three(self, tmp_path):
        from engine.audio import (
            LOUDNESS_TOLERANCE_LU, PUBLISHED_LOUDNESS_LUFS, master_voice_track, measure_loudness,
        )

        src = tmp_path / "read.wav"
        _speech_shaped_fixture(src)
        raw = measure_loudness(src)
        assert raw and raw["LRA"] and raw["LRA"] >= 5.0, raw

        glue = measure_loudness(master_voice_track(src, tmp_path / "glue.wav", dynamics="glue"))
        legacy = measure_loudness(master_voice_track(src, tmp_path / "legacy.wav",
                                                     dynamics="legacy"))
        assert glue and legacy and glue["LRA"] is not None and legacy["LRA"] is not None
        assert glue["LRA"] >= 4.0, glue
        assert legacy["LRA"] <= 3.0, legacy
        assert glue["LRA"] - legacy["LRA"] >= 1.0, (glue, legacy)
        # Both land in the published band; the glue never pushes the peak.
        for m in (glue, legacy):
            assert abs(m["I"] - PUBLISHED_LOUDNESS_LUFS) <= LOUDNESS_TOLERANCE_LU, m
            assert m["TP"] is not None and m["TP"] <= -1.0, m
