"""Drift guards for the safe-commit-push composite action.

Jul 16 2026 incident: the composite's `git pull --rebase --autostash ||
true` hit an autostash-pop conflict in the nightly job and the conflicted
`site/data/gallery-manifest.json` — complete with `<<<<<<<` markers — was
staged and committed to main. Every JSON consumer (gallery-library blend,
RU dubs, gallery page) silently no-opped on the corrupt file. The action
now refuses to commit any staged file containing an unresolved conflict
marker; these tests pin that guard.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_ACTION = _ROOT / ".github" / "actions" / "safe-commit-push" / "action.yml"


class TestConflictMarkerGuard:
    def test_action_exists(self):
        assert _ACTION.exists()

    def test_guard_scans_staged_files_for_conflict_markers(self):
        text = _ACTION.read_text(encoding="utf-8")
        assert "git diff --cached --name-only" in text
        assert "^<<<<<<< " in text, (
            "safe-commit-push must scan staged files for unresolved "
            "conflict markers before committing (Jul 16 2026 "
            "gallery-manifest incident)")

    def test_guard_restores_conflicted_files_and_warns(self):
        text = _ACTION.read_text(encoding="utf-8")
        assert "git restore --source=origin/main" in text
        assert "::warning::" in text
