"""Nov 3 2026 — loudness, range and true peak are numbers the pipeline reads
(six-month review, audio-1).

Three shows shipped 208 episodes at -25 LUFS against the published -16 and
nothing read the number: ``audio_duration_s`` was the only thing the
pipeline recorded about its audio, ``validate_mp3`` looked at bytes and
duration, and the one loudness reader lived in the Personal builder. Now
``engine.audio.measure_loudness`` is the one reader, run_show and the
edition record its three figures, post-run validation says when a file is
out of the band (log-only for the first week of readings), and the
dashboard carries ``audio_loudness_in_spec_share_7d`` and
``audio_loudness_range_median_7d``.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

# ffmpeg 6.1's stderr for ``-af ebur128=peak=true -f null -`` (captured on a
# real file, figures edited to an in-spec episode).
FIXTURE_STDERR = """ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers
Input #0, mp3, from 'ep.mp3':
  Duration: 00:31:02.00, start: 0.000000, bitrate: 245 kb/s
[Parsed_ebur128_0 @ 0x558672d9f000] t: 0.1         TARGET:-23 LUFS    M: -120.7 S:-120.7     I: -70.0 LUFS       LRA:   0.0 LU  FTPK: -91.3 -91.3 dBFS  TPK: -91.3 -91.3 dBFS
[Parsed_ebur128_0 @ 0x558672d9f000] Summary:

  Integrated loudness:
    I:         -16.4 LUFS
    Threshold: -26.9 LUFS

  Loudness range:
    LRA:         6.1 LU
    Threshold: -36.9 LUFS
    LRA low:   -20.3 LUFS
    LRA high:  -14.2 LUFS

  True peak:
    Peak:       -1.5 dBFS
"""

SILENT_STDERR = FIXTURE_STDERR.replace("Peak:       -1.5 dBFS", "Peak:       -inf dBFS")


def _fake_run(stderr: str, calls: list):
    def run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(stderr=stderr, stdout="", returncode=0)
    return run


# --------------------------------------------------------- the one reader --
class TestMeasureLoudnessIsTheOneReader:
    def test_parses_the_summary_block_from_one_decode(self, monkeypatch):
        from engine import audio

        calls: list = []
        monkeypatch.setattr(audio.subprocess, "run", _fake_run(FIXTURE_STDERR, calls))
        out = audio.measure_loudness(Path("ep.mp3"))
        assert out == {"I": -16.4, "LRA": 6.1, "TP": -1.5}
        assert len(calls) == 1, "one ffmpeg pass measures all three"
        cmd = calls[0]
        assert cmd[0] == "ffmpeg"
        assert cmd[cmd.index("-af") + 1] == "ebur128=peak=true"
        assert cmd[-3:] == ["-f", "null", "-"]
        assert "ep.mp3" in cmd

    def test_none_when_ffmpeg_cannot_run(self, monkeypatch):
        from engine import audio

        def missing(cmd, **kwargs):
            raise FileNotFoundError("ffmpeg")
        monkeypatch.setattr(audio.subprocess, "run", missing)
        assert audio.measure_loudness(Path("ep.mp3")) is None

        def slow(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 1)
        monkeypatch.setattr(audio.subprocess, "run", slow)
        assert audio.measure_loudness(Path("ep.mp3"), timeout=1) is None

    def test_none_without_a_summary_never_zero(self, monkeypatch):
        from engine import audio

        monkeypatch.setattr(audio.subprocess, "run",
                            _fake_run("ep.mp3: Invalid data found when processing input\n", []))
        out = audio.measure_loudness(Path("ep.mp3"))
        assert out is None
        assert out != 0 and out != {"I": 0.0}

    def test_a_silent_peak_is_none_not_zero(self, monkeypatch):
        from engine import audio

        monkeypatch.setattr(audio.subprocess, "run", _fake_run(SILENT_STDERR, []))
        out = audio.measure_loudness(Path("ep.mp3"))
        assert out is not None
        assert out["I"] == -16.4 and out["LRA"] == 6.1
        assert out["TP"] is None

    def test_the_personal_wrapper_keeps_its_float_or_none_shape(self, monkeypatch):
        from engine import audio, personal_edition

        monkeypatch.setattr(audio, "measure_loudness",
                            lambda p, **k: {"I": -16.4, "LRA": 6.1, "TP": -1.5})
        assert personal_edition.measure_lufs(Path("seg.flac")) == -16.4
        monkeypatch.setattr(audio, "measure_loudness", lambda p, **k: None)
        assert personal_edition.measure_lufs(Path("seg.flac")) is None

    def test_the_personal_module_has_no_reader_of_its_own(self):
        src = (ROOT / "engine" / "personal_edition.py").read_text(encoding="utf-8")
        assert "ebur128" not in src
        assert "_LUFS_RE" not in src
        assert "from engine.audio import measure_loudness" in src
        feeds = (ROOT / "scripts" / "build_personal_feeds.py").read_text(encoding="utf-8")
        assert "measure_lufs(target)" in feeds, "the builder's caller is unchanged"

    def test_the_numeric_target_agrees_with_the_filter_and_the_builder(self):
        from engine import audio, personal_edition

        m = re.search(r"\bI=(-?\d+(?:\.\d+)?)", audio.PUBLISHED_LOUDNESS)
        assert m and float(m.group(1)) == audio.PUBLISHED_LOUDNESS_LUFS
        assert personal_edition.SEGMENT_TARGET_LUFS == audio.PUBLISHED_LOUDNESS_LUFS
        assert personal_edition.SEGMENT_LOUDNESS_TOLERANCE_LU == audio.LOUDNESS_TOLERANCE_LU


# ------------------------------------------------------ the three records --
class TestThePipelineRecordsTheThreeKeys:
    KEYS = ("audio_integrated_lufs", "audio_loudness_range_lu", "audio_true_peak_dbtp")

    def test_run_show_records_them_from_the_finished_mp3(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        for key in self.KEYS:
            assert f'metrics.record("{key}"' in src, key
        assert "measure_loudness(final_mp3)" in src
        # The read follows every edit that changes the file (the debut song
        # is appended after the mix), so the figure is the shipped file's.
        assert src.index("append_full_song(final_mp3") < src.index("measure_loudness(final_mp3)")

    def test_the_repair_tool_logs_them(self):
        src = (ROOT / "scripts" / "resynthesize_episode.py").read_text(encoding="utf-8")
        assert "measure_loudness(art.final_mp3)" in src
        for key in self.KEYS:
            assert key in src, key

    def test_the_edition_record_carries_them_and_null_when_unmeasured(self):
        from engine.daily_edition import build_edition_metrics

        measured = build_edition_metrics(
            80, dt.date(2026, 11, 3), 7000.0, [],
            links_source="llm", field_note_included=False,
            missing_expected=[], dropped=[],
            loudness={"I": -16.2, "LRA": 5.5, "TP": -1.6})
        assert measured["audio_integrated_lufs"] == -16.2
        assert measured["audio_loudness_range_lu"] == 5.5
        assert measured["audio_true_peak_dbtp"] == -1.6

        unmeasured = build_edition_metrics(
            80, dt.date(2026, 11, 3), 7000.0, [],
            links_source="llm", field_note_included=False,
            missing_expected=[], dropped=[])
        for key in self.KEYS:
            assert key in unmeasured and unmeasured[key] is None, key

        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        assert "loudness = measure_loudness(final_mp3)" in src
        assert "loudness=loudness," in src


# ------------------------------------------------- validation says, never fails --
class TestValidateLoudnessWarnsAndNeverFails:
    @pytest.fixture
    def prv(self):
        import importlib
        return importlib.import_module("engine.post_run_validation")

    def test_out_of_band_warns_and_passes(self, prv, monkeypatch, caplog):
        monkeypatch.setattr(prv, "measure_loudness",
                            lambda p, **k: {"I": -25.0, "LRA": 3.1, "TP": -8.0})
        caplog.set_level(logging.INFO, logger="engine.post_run_validation")
        assert prv.validate_loudness(Path("uc_ep161.mp3")) is True
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings and "::warning::" in warnings[0].getMessage()
        assert "-25.0 LUFS" in warnings[0].getMessage()
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]

    def test_in_band_passes_quietly(self, prv, monkeypatch, caplog):
        monkeypatch.setattr(prv, "measure_loudness",
                            lambda p, **k: {"I": -16.4, "LRA": 6.1, "TP": -1.5})
        caplog.set_level(logging.INFO, logger="engine.post_run_validation")
        assert prv.validate_loudness(Path("ep.mp3")) is True
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("Loudness validated" in r.getMessage() for r in caplog.records)

    def test_unmeasured_is_a_pass_with_a_log_line(self, prv, monkeypatch, caplog):
        monkeypatch.setattr(prv, "measure_loudness", lambda p, **k: None)
        caplog.set_level(logging.INFO, logger="engine.post_run_validation")
        assert prv.validate_loudness(Path("ep.mp3")) is True
        assert any("not measured" in r.getMessage() for r in caplog.records)
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_the_band_is_the_published_target(self, prv):
        import inspect
        from engine import audio

        sig = inspect.signature(prv.validate_loudness)
        assert sig.parameters["target"].default == audio.PUBLISHED_LOUDNESS_LUFS == -16.0
        assert sig.parameters["tolerance"].default == audio.LOUDNESS_TOLERANCE_LU == 1.5

    def test_the_runner_calls_it_after_the_mp3_check_without_gating(self, prv, monkeypatch, tmp_path):
        src = (ROOT / "engine" / "post_run_validation.py").read_text(encoding="utf-8")
        body = src[src.index("def run_post_validation("):]
        assert "validate_loudness(mp3_path)" in body
        assert "if not validate_loudness" not in body, "log-only for the first week"
        assert body.index("validate_mp3(mp3_path)") < body.index("validate_loudness(mp3_path)")
        # Functionally: a -30 LUFS file still passes the runner.
        monkeypatch.setattr(prv, "validate_mp3", lambda p, **k: True)
        monkeypatch.setattr(prv, "measure_loudness",
                            lambda p, **k: {"I": -30.0, "LRA": 2.0, "TP": -12.0})
        assert prv.run_post_validation(mp3_path=tmp_path / "ep.mp3",
                                       show_name="t", episode_num=1) is True


# ------------------------------------------------------- the dashboard reads --
class TestTheDashboardReadsTheLoudness:
    ANCHOR = dt.date(2026, 11, 3)

    def _root(self, tmp_path, readings):
        show = tmp_path / "digests" / "showa"
        show.mkdir(parents=True)
        for n, (lufs, lra) in enumerate(readings, start=1):
            (show / f"showa_Ep{n:03d}_{self.ANCHOR:%Y%m%d}.md").write_text("# x\n", encoding="utf-8")
            counters = {"audio_duration_s": 1800.0}
            if lufs is not None:
                counters["audio_integrated_lufs"] = lufs
            if lra is not None:
                counters["audio_loudness_range_lu"] = lra
            (show / f"metrics_ep{n:03d}.json").write_text(
                json.dumps({"counters": counters}), encoding="utf-8")
        return tmp_path

    def test_share_in_band_and_median_range(self, tmp_path):
        import scripts.generate_dashboard as gd

        root = self._root(tmp_path, [(-16.0, 4.0), (-16.4, 5.0), (-15.2, 6.0),
                                     (-25.0, 7.0), (-17.8, 8.0), (-16.1, 9.0)])
        out = gd._episode_counter_shares(root, self.ANCHOR)
        assert out["audio_loudness_in_spec_share_7d"] == 0.67   # 4 of 6 within -16 ± 1.5
        assert out["audio_loudness_range_median_7d"] == 7.0

    def test_null_under_min_n_and_unmeasured_episodes_do_not_count(self, tmp_path):
        import scripts.generate_dashboard as gd

        # Five episodes, three measured: the share is null, never a zero,
        # and the two files without the key are absent, not quiet.
        root = self._root(tmp_path, [(-16.0, 4.0), (-16.2, 5.0), (-16.1, 6.0),
                                     (None, None), (None, None)])
        out = gd._episode_counter_shares(root, self.ANCHOR)
        assert out["audio_loudness_in_spec_share_7d"] is None
        assert out["audio_loudness_range_median_7d"] is None
        assert gd._episode_counter_shares(root, self.ANCHOR, min_n=3)[
            "audio_loudness_in_spec_share_7d"] == 1.0

    def test_the_live_metrics_carry_both_keys(self):
        import scripts.generate_dashboard as gd

        live = gd._experiment_live_metrics(ROOT)
        assert "audio_loudness_in_spec_share_7d" in live
        assert "audio_loudness_range_median_7d" in live
        for key in ("audio_loudness_in_spec_share_7d", "audio_loudness_range_median_7d"):
            assert live[key] is None or isinstance(live[key], (int, float))

    def test_the_register_names_the_share(self):
        data = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8"))
        entry = next(e for e in data["experiments"]
                     if e["id"] == "audio-published-loudness-2026-11-03")
        assert entry["metric"] == "audio_loudness_in_spec_share_7d"
