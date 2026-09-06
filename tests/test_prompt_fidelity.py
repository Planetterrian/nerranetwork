"""Prompt-fidelity drift guards across every show.

These don't grade prose — they pin the *mechanical contract* every show's
prompts must satisfy so a bad edit (a malformed brace, a deleted prompt file, a
broken shared-snippet include) is caught in CI instead of at 6 AM UTC mid-run.

Rendering safety is the key check: ``engine.generator.load_prompt`` runs
``str.format_map`` on every prompt, which raises on an unescaped/malformed
brace.  We render each prompt with a forgiving mapping (every placeholder ->
"") so any brace problem surfaces here regardless of which vars a given show
supplies at runtime.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.config import discover_show_slugs, load_config
from engine.generator import load_prompt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "shows" / "prompts"
SHARED_DIR = PROMPTS_DIR / "_shared"


class _Forgiving(dict):
    """format_map mapping that yields '' for any key but still raises on
    malformed/unescaped braces — exactly the production failure mode."""

    def __missing__(self, key):  # noqa: D401
        return ""


SLUGS = discover_show_slugs()


@pytest.fixture(params=SLUGS)
def show_cfg(request):
    slug = request.param
    return slug, load_config(PROJECT_ROOT / "shows" / f"{slug}.yaml")


def _prompt_paths(cfg):
    out = {}
    for label in ("digest_prompt_file", "podcast_prompt_file", "system_prompt_file"):
        val = getattr(cfg.llm, label, "")
        if val:
            out[label] = Path(val)
    return out


class TestPromptFilesExist:
    def test_digest_and_podcast_prompts_configured_and_present(self, show_cfg):
        slug, cfg = show_cfg
        assert cfg.llm.digest_prompt_file, f"{slug}: no digest_prompt_file configured"
        assert cfg.llm.podcast_prompt_file, f"{slug}: no podcast_prompt_file configured"
        for label in ("digest_prompt_file", "podcast_prompt_file"):
            p = Path(getattr(cfg.llm, label))
            assert p.exists(), f"{slug}: {label} missing on disk: {p}"
            assert p.read_text(encoding="utf-8").strip(), f"{slug}: {label} is empty"

    def test_system_prompt_present_when_configured(self, show_cfg):
        slug, cfg = show_cfg
        if cfg.llm.system_prompt_file:
            p = Path(cfg.llm.system_prompt_file)
            assert p.exists(), f"{slug}: system_prompt_file missing: {p}"


class TestPromptsRenderSafely:
    def test_prompts_render_without_brace_errors(self, show_cfg):
        slug, cfg = show_cfg
        for label, path in _prompt_paths(cfg).items():
            try:
                rendered = load_prompt(str(path), _Forgiving())
            except (ValueError, IndexError) as exc:
                pytest.fail(f"{slug}: {label} has a malformed brace and would crash a live run: {exc}")
            except KeyError as exc:  # pragma: no cover - _Forgiving prevents this
                pytest.fail(f"{slug}: {label} KeyError despite forgiving map: {exc}")
            assert isinstance(rendered, str)


class TestSharedSnippets:
    def test_shared_dir_exists(self):
        assert SHARED_DIR.is_dir(), "shows/prompts/_shared is missing"

    def test_shared_snippets_are_includable(self):
        # Every shared .txt must resolve through the include mechanism.
        for snippet in SHARED_DIR.glob("*.txt"):
            rel = snippet.name
            probe = PROMPTS_DIR / "__fidelity_probe__.txt"
            probe.write_text(f"<<include: _shared/{rel}>>", encoding="utf-8")
            try:
                out = load_prompt(str(probe), None)
                assert out.strip(), f"_shared/{rel} resolved empty"
            finally:
                probe.unlink(missing_ok=True)


class TestWeeklyNewsletterPromptPlaceholders:
    """2026-08-30: first_principles_weekly.txt carried {episodes_block} —
    a placeholder synthesize_weekly_newsletter never supplies — so the
    Sunday weekly-newsletter run crashed mid-loop and every show after it
    got no newsletter that week (spacex/UC carried the same class of
    bug, masked behind the first crash). Every weekly template must
    format with EXACTLY the kwargs the synthesizer passes."""

    SYNTH_KWARGS = dict(
        show_name="Show", episode_count=3, start_date="2026-08-24",
        end_date="2026-08-30", episodes_text="episodes", entities="a, b",
    )

    def test_every_weekly_prompt_formats_with_synth_kwargs(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        files = sorted((root / "shows" / "prompts").glob("*_weekly.txt"))
        assert files, "expected weekly newsletter prompt templates"
        bad = []
        for f in files:
            try:
                f.read_text(encoding="utf-8").format(**self.SYNTH_KWARGS)
            except (KeyError, IndexError, ValueError) as exc:
                bad.append((f.name, repr(exc)))
        assert not bad, f"weekly prompts with unsupplied placeholders: {bad}"

    def test_kwargs_pin_matches_synthesizer(self):
        # If the synthesizer's format call gains/loses kwargs, this pin
        # must be updated in the same change.
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent
               / "engine" / "synthesizer.py").read_text(encoding="utf-8")
        call = src.split("body_prompt = prompt_template.format(", 1)[1]
        call = call.split("\n    )", 1)[0]
        import re
        supplied = set(re.findall(r"^\s*(\w+)=", call, re.MULTILINE))
        assert supplied == set(self.SYNTH_KWARGS), (supplied,
                                                    set(self.SYNTH_KWARGS))

    def test_runner_isolates_per_show_crashes(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "scripts"
               / "run_weekly_newsletters.py").read_text(encoding="utf-8")
        head, _, tail = src.partition("envelope = synthesize_weekly_newsletter(")
        assert tail, "synthesize call moved"
        assert head.rstrip().endswith("try:"), (
            "the synthesize call must be wrapped so one show's crash "
            "cannot sink every show after it in the loop")
        assert 'st.startswith("failed")' in src, (
            "crashed shows must still fail the JOB at the end")


class TestWeeklyNewsletterSameWeekGuard:
    """Sep 6 2026: the Sunday 14:00 UTC cron arrives hours late (or never)
    during the GitHub cron outage, so the operator dispatches the workflow
    by hand — and a late cron firing afterwards would re-send every show's
    weekly. A per-show, per-week marker written after a real send makes the
    second run a no-op. The marker lives in outputs/newsletters/, which the
    workflow commits — but only if add-paths is a block scalar (the
    composite uses --pathspec-from-file, so a space-separated single line
    is one pathspec that matches nothing)."""

    def _load_runner(self, monkeypatch):
        import importlib.util
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location(
            "run_weekly_newsletters", root / "scripts" / "run_weekly_newsletters.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        monkeypatch.setattr(mod, "get_lake_stats",
                            lambda: {"total_episodes": 0, "total_words": 0})
        return mod

    def test_marker_skips_synthesis_and_send(self, monkeypatch, tmp_path):
        import datetime as dt
        mod = self._load_runner(monkeypatch)
        week = dt.date(2026, 9, 6)
        mod.sent_marker_path(tmp_path, "tesla", week).write_text("{}")

        def boom(**kw):
            raise AssertionError("synthesis must not run for an already-sent week")
        monkeypatch.setattr(mod, "synthesize_weekly_newsletter", boom)
        monkeypatch.setattr("sys.argv", ["x", "--show", "tesla", "--date",
                                         "2026-09-06", "--output-dir", str(tmp_path)])
        mod.main()  # no SystemExit: an already-sent show is not a failure

    def test_dry_run_ignores_marker(self, monkeypatch, tmp_path):
        import datetime as dt
        mod = self._load_runner(monkeypatch)
        week = dt.date(2026, 9, 6)
        mod.sent_marker_path(tmp_path, "tesla", week).write_text("{}")
        calls = []
        monkeypatch.setattr(mod, "synthesize_weekly_newsletter",
                            lambda **kw: calls.append(kw) or None)
        monkeypatch.setattr("sys.argv", ["x", "--show", "tesla", "--date",
                                         "2026-09-06", "--output-dir",
                                         str(tmp_path), "--dry-run"])
        mod.main()
        assert calls, "dry run must still generate"

    def test_marker_written_after_send_only(self, tmp_path):
        import importlib.util, json
        from pathlib import Path
        import datetime as dt
        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location(
            "run_weekly_newsletters", root / "scripts" / "run_weekly_newsletters.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        marker = mod.sent_marker_path(tmp_path, "spacex", dt.date(2026, 9, 6))
        assert marker.name == "spacex_weekly_2026-09-06.sent.json"
        mod.record_sent(marker, email_id="em_123", subject="Hello")
        data = json.loads(marker.read_text())
        assert data["email_id"] == "em_123" and data["sent_at"]
        src = (root / "scripts" / "run_weekly_newsletters.py").read_text()
        assert src.index("email_id = send_newsletter(") < src.index("record_sent(sent_marker")

    def test_workflow_syncs_to_live_main_before_running(self):
        # A queued run checks out the SHA fixed at TRIGGER time; the
        # same-week guard reads committed markers, so the workspace must
        # be moved to the live tip before the runner (2026-09-06: six
        # shows double-sent because the late cron ran on a stale tree).
        from pathlib import Path
        import yaml
        wf = yaml.safe_load((Path(__file__).resolve().parent.parent
                             / ".github" / "workflows" / "weekly-newsletter.yml").read_text())
        steps = wf["jobs"]["generate"]["steps"]
        names = [str(s.get("name", s.get("uses", ""))) for s in steps]
        sync = next(i for i, s in enumerate(steps)
                    if "git reset --hard origin/main" in str(s.get("run", "")))
        run = next(i for i, n in enumerate(names) if n == "Run weekly newsletters")
        assert sync < run, names
        assert "git fetch" in steps[sync]["run"]

    def test_workflow_add_paths_is_block_scalar(self):
        from pathlib import Path
        import yaml
        wf = yaml.safe_load((Path(__file__).resolve().parent.parent
                             / ".github" / "workflows" / "weekly-newsletter.yml").read_text())
        steps = wf["jobs"]["generate"]["steps"]
        commit = next(s for s in steps if str(s.get("uses", "")).endswith("safe-commit-push"))
        paths = commit["with"]["add-paths"]
        assert "\n" in paths.strip(), "add-paths must be one path per line"
        assert all(" " not in line.strip() for line in paths.splitlines()), paths
        assert "outputs/newsletters/" in paths

