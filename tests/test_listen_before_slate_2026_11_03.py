"""Listen before the slate (Nov 3 2026).

"Ship to the whole slate, then repair" was the network's audio pattern: the
Oct 13 beat and the Oct 14 music swell each shipped network-wide and were
reversed within a day; the Oct 20 ``[breath]`` tag reached 14 episodes before
the operator heard it and every one was re-voiced; 11 commits to
``shows/_defaults.yaml`` in October, five between Oct 13 and 20. CLAUDE.md's
Oct 20 rule — a candidate is LISTENED to on a shipped episode before it
ships to a slate — had no mechanism. ``run_show.py --rehearse`` existed and no
workflow exposed it; the audio probe rendered one made-up passage, never a
real script; nothing recorded a listen.

Now:

* ``run-show.yml`` has a ``rehearse`` input: the run calls ``--rehearse``,
  uploads the ``rehearsal_*`` MP3 and TTS text as a 3-day artifact, and
  reaches no commit or publish step (every ``test_mode`` guard reads it too).
* ``scripts/probe_audio_chain.py --script <committed _tts.txt>`` voices a
  real minute on the show's voice and renders named chain variants through
  the REAL builders with the show's own theme; ``--dry-run`` prints the
  commands with no key. Nothing lands under ``digests/`` or the feeds.
* ``tests/fixtures/defaults_audio_snapshot.yaml`` holds ``_defaults.yaml``'s
  ``audio:`` and ``tts:`` sections; a changed value fails here until the
  snapshot is regenerated AND ``docs/listens.md`` gains a line carrying the
  new values' fingerprint — a reminder with teeth, not proof.

Regenerate the snapshot and print the line to add::

    python tests/test_listen_before_slate_2026_11_03.py --write

The canary layer both proposals asked for was dropped on purpose: a show's
YAML already overrides ``_defaults.yaml`` (``engine.config.load_config``),
so a trial IS the value in that show's YAML; a third place a value could
live is against the one-owner rule.
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULTS = ROOT / "shows" / "_defaults.yaml"
SNAPSHOT = ROOT / "tests" / "fixtures" / "defaults_audio_snapshot.yaml"
LISTENS = ROOT / "docs" / "listens.md"
RUN_SHOW_WF = ROOT / ".github" / "workflows" / "run-show.yml"
PROBE_WF = ROOT / ".github" / "workflows" / "probe-audio-chain.yml"
PROBE = ROOT / "scripts" / "probe_audio_chain.py"
SECTIONS = ("audio", "tts")

SNAPSHOT_HEADER = """\
# tests/fixtures/defaults_audio_snapshot.yaml — the audio: and tts: sections of
# shows/_defaults.yaml as last listened to (Nov 3 2026, listen before the slate).
# tests/test_listen_before_slate_2026_11_03.py fails when a value here differs
# from _defaults.yaml. Regenerate with
#     python tests/test_listen_before_slate_2026_11_03.py --write
# and add the docs/listens.md line that command prints. Never edit by hand.
"""

#: The one line form docs/listens.md must carry for the current snapshot:
#: "<key> — listened by <who> on <date>, episode <show> Ep<N> · snapshot <fp>".
LISTEN_LINE_RE = re.compile(
    r"^(?P<key>(audio|tts)\.[a-z0-9_]+) — listened by (?P<who>.+?) on "
    r"(?P<date>\d{4}-\d{2}-\d{2}), episode (?P<show>[a-z0-9_]+) Ep(?P<ep>\d+)"
    r" · snapshot (?P<fp>[0-9a-f]{12})\s*$"
)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def snapshot_sections(path: Path | None = None) -> dict:
    """The ``audio:`` and ``tts:`` sections of ``_defaults.yaml`` as data —
    comments and key order are not values, so neither asks for a listen."""
    data = yaml.safe_load((path or DEFAULTS).read_text(encoding="utf-8")) or {}
    return {k: data.get(k) for k in SECTIONS}


def fingerprint(sections: dict) -> str:
    """Twelve hex characters over the canonical JSON of the two sections."""
    canon = json.dumps(sections, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]


def listen_line_for(fp: str, text: str):
    for line in text.splitlines():
        m = LISTEN_LINE_RE.match(line.strip())
        if m and m.group("fp") == fp:
            return m
    return None


def write_snapshot(path: Path | None = None) -> str:
    path = path or SNAPSHOT
    sections = snapshot_sections()
    body = yaml.safe_dump(sections, sort_keys=True, allow_unicode=True,
                          default_flow_style=False, width=100)
    path.write_text(SNAPSHOT_HEADER + body, encoding="utf-8")
    return fingerprint(sections)


def _load_probe():
    spec = importlib.util.spec_from_file_location("probe_audio_chain", PROBE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_job_steps() -> list:
    wf = yaml.safe_load(RUN_SHOW_WF.read_text(encoding="utf-8"))
    return wf["jobs"]["run"]["steps"]


def _step(name: str) -> dict:
    for step in _run_job_steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"run-show.yml has no step named {name!r}")


# ------------------------------------------------------- the rehearsal --
class TestRehearseInputOnRunShow:
    """The Sep 21 pattern: the workflow is read as text and as YAML."""

    def test_the_input_exists_and_is_a_boolean(self):
        wf = yaml.safe_load(RUN_SHOW_WF.read_text(encoding="utf-8"))
        inputs = wf[True]["workflow_dispatch"]["inputs"]
        assert inputs["rehearse"]["type"] == "boolean"
        assert inputs["rehearse"]["default"] is False
        desc = inputs["rehearse"]["description"]
        assert "--rehearse" in desc and "artifact" in desc

    def test_the_run_step_calls_rehearse_and_test_mode_wins(self):
        run = _step("Run show pipeline")["run"]
        assert 'elif [ "${{ github.event.inputs.rehearse }}" = "true" ]; then' in run
        assert 'EXTRA_FLAGS="--rehearse"' in run
        # test_mode stops before TTS: both set is a warning, never two flags.
        assert run.index('EXTRA_FLAGS="--test"') < run.index('EXTRA_FLAGS="--rehearse"')
        assert "rehearse=true ignored" in run
        # the same-day re-check never skips a rehearsal
        assert re.search(r'\[ "\$\{\{ github\.event\.inputs\.rehearse \}\}" != "true" \]; then\s+'
                         r'RECHECK="true"', run)

    def test_the_audio_first_push_and_the_video_job_are_off(self):
        env = _step("Run show pipeline")["env"]
        for key in ("NERRA_AUDIO_FIRST_PUSH", "NERRA_VIDEO_JOB"):
            assert "github.event.inputs.rehearse == 'true'" in env[key], key
            assert "'0'" in env[key]

    def test_the_rehearsal_is_uploaded_for_three_days(self):
        step = _step("Upload the rehearsal")
        assert step["if"] == ("github.event.inputs.rehearse == 'true' "
                              "&& steps.pipeline.outputs.skipped != 'true'")
        assert step["uses"].startswith("actions/upload-artifact@")
        with_ = step["with"]
        assert "digests/**/rehearsal_*.mp3" in with_["path"]
        assert "digests/**/rehearsal_*_tts.txt" in with_["path"]
        assert with_["retention-days"] == 3
        assert with_["if-no-files-found"] == "error"

    def test_the_working_tree_is_discarded_after_the_upload(self):
        names = [s.get("name") for s in _run_job_steps()]
        assert names.index("Upload the rehearsal") < names.index(
            "Discard the rehearsal's working tree")
        step = _step("Discard the rehearsal's working tree")
        assert "always() && github.event.inputs.rehearse == 'true'" == step["if"]
        assert "git checkout -- digests/" in step["run"]

    def test_every_test_mode_guard_also_reads_rehearse(self):
        guarded = [s for s in _run_job_steps()
                   if "test_mode != 'true'" in str(s.get("if", ""))]
        assert len(guarded) >= 7, [s.get("name") for s in guarded]
        for step in guarded:
            assert "github.event.inputs.rehearse != 'true'" in step["if"], step.get("name")

    def test_no_commit_or_publish_step_runs_in_a_rehearsal(self):
        for name in ("Commit skip state (queue cooldown + skip marker)",
                     "Commit and push output", "Start the video job",
                     "Start the multilingual sweep", "Wake the Nerra Daily gate"):
            assert "github.event.inputs.rehearse != 'true'" in _step(name)["if"], name
        wf = yaml.safe_load(RUN_SHOW_WF.read_text(encoding="utf-8"))
        assert "github.event.inputs.rehearse != 'true'" in wf["jobs"]["finalize"]["if"]

    def test_the_artifact_glob_matches_what_run_show_renames(self):
        src = _read("run_show.py")
        assert '"--rehearse",' in src
        stop = src[src.index("# === Rehearsal stop (--rehearse) ==="):]
        assert '_dest = _f.with_name(f"rehearsal_{_f.name}")' in stop
        assert 'f"{config.episode.prefix}_Ep{episode_num:03d}_{today:%Y%m%d}*"' in stop
        # the MP3 and the _tts.txt both carry that stem, so both are renamed
        assert '_tts.txt"' in src[src.index("tts_script_path = digests_dir /"):][:200]


# ------------------------------------------------------------ the probe --
@pytest.fixture(scope="module")
def probe():
    return _load_probe()


class TestTheProbeRendersARealMinute:
    TESLA = "digests/tesla_shorts_time/Tesla_Shorts_Time_Pod_Ep653_20261102_tts.txt"
    DP = "digests/dp_pod/DP_Pod_Ep082_20261102_tts.txt"
    VAN = "digests/vancouver/Vancouver_Daily_Ep041_20261102_tts.txt"

    def test_the_rate_is_the_measured_one(self, probe):
        # Nov 3 2026, len(_tts.txt) / audio_duration_s on six shows:
        # Patrick 15.3-16.0, Mira 16.5-18.1, the DP Pod at 1.05 17.8.
        assert probe.CHARS_PER_SECOND == 16.0
        assert probe.DIALOGUE_SPEEDS == (1.0, 1.05)

    def test_clip_cuts_on_a_boundary_never_mid_word(self, probe):
        text = ("First paragraph sentence one. Sentence two.\n\n"
                "Second paragraph is here. It has two sentences.\n\n"
                "Third paragraph closes it out.")
        clip = probe.clip_script(text, 1000)
        assert clip == text
        clip = probe.clip_script(text, 60 / probe.CHARS_PER_SECOND)  # 60 chars
        assert clip == "First paragraph sentence one. Sentence two."
        one = "A single long paragraph with several words in it and no break at all here."
        clip = probe.clip_script(one, 30 / probe.CHARS_PER_SECOND)
        assert len(clip) <= 30 and one.startswith(clip)
        assert one[len(clip)] == " "  # the next character is a space: no split word
        # the first paragraph always ships whole
        assert probe.clip_script(text, 0.1) == "First paragraph sentence one. Sentence two."

    def test_a_dialogue_clip_ends_on_a_whole_turn(self, probe):
        clip = probe.clip_script(_read(self.DP), 75)
        turns = [t for t in clip.split("\n\n") if t.strip()]
        assert all(re.match(r"^(PATRICK|DAN): ", t) for t in turns), turns[-1][:60]
        assert len(clip) <= 75 * probe.CHARS_PER_SECOND

    def test_the_show_is_found_from_the_scripts_directory(self, probe):
        slug, config = probe.show_for_script(ROOT / self.TESLA)
        assert slug == "tesla" and config.audio.music_file == "assets/music/tesla_shorts_time.mp3"
        slug, config = probe.show_for_script(ROOT / self.DP)
        assert slug == "dp_pod" and config.tts.dialogue_mode is True
        with pytest.raises(SystemExit):
            probe.show_for_script(ROOT / "digests" / "nope" / "x_tts.txt")

    def test_variants_are_the_real_builders_arguments(self, probe):
        from engine import audio

        _, config = probe.show_for_script(ROOT / self.TESLA)
        resolved = {n: (kw, note) for n, kw, note in
                    probe.resolve_variants(["legacy", "glue", "nope", "strong_declick"], config)}
        kw, chain = resolved["legacy"]
        assert kw == {"denoise": config.audio.voice_denoise,
                      "declick": config.audio.voice_declick}
        assert chain == audio.voice_chain_filters(**kw)
        assert resolved["nope"][0] is None and "unknown variant" in resolved["nope"][1]
        assert resolved["strong_declick"][0]["declick"] == "strong"
        # glue lights up exactly when every builder accepts `dynamics` — never approximated
        offered = all("dynamics" in inspect.signature(fn).parameters for fn in
                      (audio.voice_chain_filters, audio.master_voice_track, audio.mix_with_music))
        assert (resolved["glue"][0] is not None) is offered
        if not offered:
            assert "not a chain engine.audio offers on this tree" in resolved["glue"][1]

    def test_mix_kwargs_are_the_ones_run_show_passes(self, probe):
        src = _read("run_show.py")
        call = src[src.index("                        mix_with_music(\n"):]
        call = call[:call.index(")\n") + 1]
        named = set(re.findall(r"\b([a-z_]+)=", call))
        # the variant's own (denoise / declick, and since Nov 3 2026 the
        # dynamics stage name), and the cues
        named -= {"denoise", "declick", "dynamics", "breathers"}
        _, config = probe.show_for_script(ROOT / self.TESLA)
        assert set(probe.mix_kwargs(config)) == named

    def test_a_dry_run_builds_the_real_mix_and_writes_nothing_under_digests(
            self, probe, tmp_path, capsys):
        digests = ROOT / "digests" / "tesla_shorts_time"
        before = sorted(p.name for p in digests.iterdir())
        feeds = {p: p.stat().st_mtime_ns for p in ROOT.glob("*.rss")}
        rc = probe.main(["--script", self.TESLA, "--seconds", "75",
                         "--variants", "legacy,glue", "--dry-run", "--out", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert sorted(p.name for p in digests.iterdir()) == before
        assert {p: p.stat().st_mtime_ns for p in ROOT.glob("*.rss")} == feeds
        # the real builders, with the show's theme: the voice-only master and
        # the ducked final mix of mix_with_music
        assert "assets/music/tesla_shorts_time.mp3" in out
        assert "sidechaincompress" in out and "legacy_mix.mp3" in out
        assert "loudnorm=I=-16:TP=-1.5:LRA=11" in out and "legacy_voice.wav" in out
        plan = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
        assert plan["show"] == "tesla" and plan["dry_run"] is True
        assert plan["theme"] == "assets/music/tesla_shorts_time.mp3"
        assert 1000 <= plan["clip_chars"] <= 75 * probe.CHARS_PER_SECOND
        assert (tmp_path / "clip.txt").read_text(encoding="utf-8").startswith(
            _read(self.TESLA)[:200])
        assert not (tmp_path / "dry_run_voice.mp3").exists()
        assert not list(tmp_path.glob("*.wav")) and not list(tmp_path.glob("*.mp3"))

    def test_a_no_theme_show_masters_the_voice_alone(self, probe, tmp_path, capsys):
        rc = probe.main(["--script", self.VAN, "--seconds", "30", "--variants", "legacy",
                         "--dry-run", "--out", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        cmds = [ln for ln in out.splitlines() if ln.startswith("ffmpeg ")]
        assert len(cmds) == 1 and "legacy_voice.wav" in cmds[0]
        assert json.loads((tmp_path / "plan.json").read_text())["theme"] is None

    def test_the_dp_pod_renders_both_speeds(self, probe, tmp_path, capsys):
        rc = probe.main(["--script", self.DP, "--dry-run", "--out", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        plan = json.loads((tmp_path / "plan.json").read_text())
        assert plan["dialogue_speeds"] == [1.0, 1.05]
        assert plan["voice"].startswith("dialogue:PATRICK=")
        assert "# s100_legacy:" in out and "# s105_legacy:" in out
        assert "assets/music/dp_pod.mp3" in out

    def test_the_recorder_restores_engine_audio(self, probe):
        from engine import audio
        import subprocess as real

        before = (audio.subprocess, audio.get_audio_duration)
        with probe.recording_builders(5.0) as recorded:
            assert audio.subprocess is not real
            audio.subprocess.run(["ffmpeg", "-i", "x"])
        assert recorded == [["ffmpeg", "-i", "x"]]
        assert (audio.subprocess, audio.get_audio_duration) == before
        assert audio.subprocess is real

    def test_the_fixture_passage_mode_is_unchanged(self, probe):
        assert probe.SHOW_TEXT.startswith("The city council voted seven to two")
        assert probe.MIRA_TEXT.startswith("Good morning. It's Thursday")
        src = PROBE.read_text(encoding="utf-8")
        assert "def probe_fixture()" in src and "return probe_fixture()" in src


class TestTheProbeIsReadOnly:
    """Moved here from tests/test_audio_quality_2026_10_29.py (that file keeps
    to the dynamics item). The probe publishes nothing and pushes nothing."""

    def test_workflow(self):
        wf = PROBE_WF.read_text(encoding="utf-8")
        assert "contents: read" in wf and "scripts/probe_audio_chain.py" in wf
        assert "upload-artifact" in wf and "git push" not in wf

    def test_the_workflow_takes_the_four_inputs_and_passes_them(self):
        wf = yaml.safe_load(PROBE_WF.read_text(encoding="utf-8"))
        inputs = wf[True]["workflow_dispatch"]["inputs"]
        assert set(inputs) == {"script", "seconds", "variants", "voice"}
        assert inputs["seconds"]["default"] == "75" and inputs["variants"]["default"] == "legacy"
        step = [s for s in wf["jobs"]["probe"]["steps"] if s.get("name") == "Probe the audio chain"][0]
        for name in ("script", "seconds", "variants", "voice"):
            assert f"${{{{ github.event.inputs.{name} }}}}" in str(step["env"]), name
        assert '--script "$PROBE_SCRIPT"' in step["run"] and "--voice" in step["run"]
        assert 'if [ -n "$PROBE_SCRIPT" ]' in step["run"]  # no script = the fixture passage

    def test_the_probe_never_writes_under_digests_or_the_feeds(self):
        src = PROBE.read_text(encoding="utf-8")
        assert "update_rss_feed" not in src and "upload_to_r2" not in src
        assert 'digests' not in re.sub(r'"""[\s\S]*?"""', "", src).replace("digests/<dir>", "")


# ---------------------------------------------------------- the snapshot --
class TestTheSnapshotAsksForAListen:
    def test_the_fixture_is_the_two_sections(self):
        text = SNAPSHOT.read_text(encoding="utf-8")
        assert text.startswith(SNAPSHOT_HEADER.splitlines()[0])
        assert "--write" in text
        data = yaml.safe_load(text)
        assert set(data) == set(SECTIONS)

    def test_the_defaults_match_the_snapshot(self):
        live = snapshot_sections()
        snap = yaml.safe_load(SNAPSHOT.read_text(encoding="utf-8"))
        if live == snap:
            return
        changed = []
        for section in SECTIONS:
            keys = set(live[section] or {}) | set((snap.get(section) or {}))
            for key in sorted(keys):
                a, b = (snap.get(section) or {}).get(key), (live[section] or {}).get(key)
                if a != b:
                    changed.append(f"{section}.{key}: {a!r} -> {b!r}")
        pytest.fail(
            "shows/_defaults.yaml's audio:/tts: differ from the listened-to snapshot:\n  "
            + "\n  ".join(changed)
            + "\nA value a listener hears changed. In this PR: (1) regenerate the snapshot — "
            "python tests/test_listen_before_slate_2026_11_03.py --write — and (2) add the "
            "docs/listens.md line it prints (who listened, when, on which episode; snapshot "
            f"{fingerprint(live)}). See docs/model_upgrade_playbook.md, 'Audio changes'."
        )

    def test_docs_listens_vouches_for_the_current_values(self):
        fp = fingerprint(snapshot_sections())
        text = LISTENS.read_text(encoding="utf-8")
        m = listen_line_for(fp, text)
        assert m is not None, (
            f"docs/listens.md has no line for snapshot {fp}. Add one in the form\n"
            f"  <key> — listened by <who> on <date>, episode <show> Ep<N> · snapshot {fp}"
        )
        assert f"{m.group('key').split('.')[0]}" in SECTIONS
        section, key = m.group("key").split(".", 1)
        assert key in (snapshot_sections()[section] or {}), m.group("key")

    def test_every_snapshot_line_keeps_the_form(self):
        text = LISTENS.read_text(encoding="utf-8")
        entries = text[text.index("## Lines"):]  # the form's own description sits above
        lines = [ln.strip() for ln in entries.splitlines() if "· snapshot " in ln]
        assert lines, "docs/listens.md carries no snapshot line"
        for line in lines:
            assert LISTEN_LINE_RE.match(line), line

    def test_a_changed_value_would_need_a_new_line(self):
        live = snapshot_sections()
        changed = json.loads(json.dumps(live))
        changed["audio"]["story_break_cue"] = not changed["audio"]["story_break_cue"]
        fp_new = fingerprint(changed)
        assert fp_new != fingerprint(live)
        assert listen_line_for(fp_new, LISTENS.read_text(encoding="utf-8")) is None
        # a comment or key order is not a value
        reordered = {k: dict(reversed(list(v.items()))) for k, v in live.items()}
        assert fingerprint(reordered) == fingerprint(live)

    def test_write_snapshot_reproduces_the_committed_fixture(self, tmp_path):
        out = tmp_path / "snap.yaml"
        fp = write_snapshot(out)
        assert fp == fingerprint(snapshot_sections())
        assert yaml.safe_load(out.read_text(encoding="utf-8")) == yaml.safe_load(
            SNAPSHOT.read_text(encoding="utf-8"))


# ---------------------------------------------- the template and the doc --
class TestThePlaybookAndTheTemplate:
    def test_the_pr_template_carries_the_three_fields(self):
        tpl = _read(".github/pull_request_template.md")
        assert "Changes audio or a prompt?" in tpl
        for field in ("Rehearsal artifact", "Listened by/when", "Trial show(s)"):
            assert field in tpl, field
        assert "docs/listens.md" in tpl
        # the migrations line stays
        assert "Migrations in this PR are NOT applied to prod" in tpl

    def test_the_playbook_has_an_audio_changes_section(self):
        doc = _read("docs/model_upgrade_playbook.md")
        sec = doc[doc.index("## Audio changes"):doc.index("## The instrument")]
        for needle in ("One show first", "rehearse: true", "Probe audio chain",
                       "docs/listens.md", "defaults_audio_snapshot.yaml", "one line",
                       "NPR", "Top World", "Collingwood", "`listen:` note"):
            assert needle in sec, needle
        assert "canary layer" in sec and "must\nnot be one" in sec
        assert 'The count of "Re-synthesize Episode" runs is NOT the readout' in sec

    def test_docs_listens_explains_its_own_form(self):
        text = _read("docs/listens.md")
        assert "listened by <who> on <date>, episode <show> Ep<N>" in text
        assert "--write" in text


if __name__ == "__main__":
    if "--write" in sys.argv[1:]:
        fp = write_snapshot()
        print(f"wrote {SNAPSHOT.relative_to(ROOT)}")
    else:
        fp = fingerprint(snapshot_sections())
    print(f"snapshot fingerprint: {fp}")
    print("docs/listens.md line to add:")
    print(f"  <key> — listened by <who> on <date>, episode <show> Ep<N> · snapshot {fp}")
