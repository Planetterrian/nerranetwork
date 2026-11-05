"""Nov 5 2026 — audio that stops before the script does.

Peptides Weekly Ep008's Grok TTS derailed at "sodium
N-[8-(2-hydroxybenzoyl) amino caprylate", re-read its own opening for a
few seconds and stopped. The last ~40% of the script, the sign-off and the
AI disclosure never reached the audio. The spoken-text gate passed it
(opening 0.93, longest foreign run 19): neither measure looks at how much
of the script was spoken. ``script_coverage`` does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.spoken_text_gate import (
    DEFAULT_MIN_SCRIPT_COVERAGE,
    check_spoken_text,
    check_transcript_files,
    script_coverage,
)

ROOT = Path(__file__).resolve().parent.parent
EP008 = ROOT / "digests/peptides/Peptides_Weekly_Ep008_20261105"

SCRIPT = " ".join(f"sentence {i} carries word{i} and more{i}." for i in range(200))


def test_full_read_covers_the_script():
    assert script_coverage(SCRIPT.split(), SCRIPT.split()) == 1.0
    report = check_spoken_text(SCRIPT, transcript_text=SCRIPT,
                               min_script_coverage=DEFAULT_MIN_SCRIPT_COVERAGE)
    assert report.passed, report.summary()


def test_audio_that_stops_early_fails_only_when_the_floor_is_passed():
    words = SCRIPT.split()
    spoken = " ".join(words[: int(len(words) * 0.55)])
    enforced = check_spoken_text(SCRIPT, transcript_text=spoken,
                                 min_script_coverage=DEFAULT_MIN_SCRIPT_COVERAGE)
    assert not enforced.passed
    assert "script_not_spoken" in enforced.reasons
    # The dub gate never passes the floor (French reaches 0.65 legitimately).
    legacy = check_spoken_text(SCRIPT, transcript_text=spoken)
    assert legacy.passed
    assert legacy.script_coverage == enforced.script_coverage


def test_peptides_ep008_is_caught():
    json_path = EP008.with_name(EP008.name + "_transcript.json")
    script = EP008.with_name(EP008.name + "_tts.txt")
    if not json_path.exists() or not script.exists():
        pytest.skip("Ep008 not committed")
    report = check_transcript_files(
        script.read_text(encoding="utf-8"), json_path,
        min_script_coverage=DEFAULT_MIN_SCRIPT_COVERAGE,
    )
    if report.script_coverage >= DEFAULT_MIN_SCRIPT_COVERAGE:
        pytest.skip("Ep008 has been re-synthesized")
    assert "script_not_spoken" in report.reasons
    assert report.script_coverage < 0.6


@pytest.mark.parametrize("path", ["run_show.py", "scripts/resynthesize_episode.py"])
def test_english_master_callers_pass_the_floor(path):
    src = (ROOT / path).read_text(encoding="utf-8")
    assert "spoken_text_gate_min_script_coverage" in src
    assert "min_script_coverage=" in src


def test_config_default_matches_the_module():
    from engine.config import TTSConfig  # noqa: WPS433
    assert TTSConfig().spoken_text_gate_min_script_coverage == DEFAULT_MIN_SCRIPT_COVERAGE
