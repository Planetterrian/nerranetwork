"""Oct 9 2026 — the verify workflow lost the FR channel from the stats file.

``verify-youtube-analytics.yml`` runs on any push that touches it (the
runner upgrade did) and writes ``api/youtube_stats.json`` through
``scripts/verify_youtube_analytics.py``. It carried EN and RU tokens only,
and the verify script wrote whatever the fetch returned: run 37889558043
(05:38 UTC) replaced the committed file with one that had no ``channels.fr``
block and 474 fewer videos, while the dashboard built from the earlier
file still reported @NerraFR. The nightly's ``snapshot_regression`` would
have refused it ("channel 'fr' lost its day series"); the verify script
never asked.

What binds: the verify workflow carries every channel token the nightly
carries, and the verify script applies the same refusal before writing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _tokens(workflow: str) -> set[str]:
    text = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
    return set(re.findall(r"(YOUTUBE_REFRESH_TOKEN_[A-Z]+):", text))


def test_verify_workflow_carries_every_channel_token_the_nightly_does():
    nightly = _tokens("nightly-maintenance.yml")
    verify = _tokens("verify-youtube-analytics.yml")
    assert {"YOUTUBE_REFRESH_TOKEN_EN", "YOUTUBE_REFRESH_TOKEN_RU",
            "YOUTUBE_REFRESH_TOKEN_FR"} <= nightly
    assert nightly <= verify, nightly - verify


def test_verify_script_refuses_a_regressed_snapshot(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "verify_youtube_analytics", ROOT / "scripts" / "verify_youtube_analytics.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    out = tmp_path / "api" / "youtube_stats.json"
    out.parent.mkdir()
    committed = {"channels": {"en": {"day_series": [1]}, "fr": {"day_series": [1]}},
                 "shows": {"tesla": {"videos": [{"id": "a"}, {"id": "b"}]}}}
    out.write_text(json.dumps(committed), encoding="utf-8")

    partial = {"channels": {"en": {"day_series": [1]}},
               "shows": {"tesla": {"videos": [{"id": "a"}, {"id": "b"}]}}}

    class _FYA:
        @staticmethod
        def fetch(_digests, _days):
            return partial

        @staticmethod
        def snapshot_regression(new, old, min_video_share=0.6):
            from scripts.fetch_youtube_analytics import snapshot_regression
            return snapshot_regression(new, old, min_video_share)

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "x")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "x")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN_EN", "x")
    monkeypatch.setitem(sys.modules, "scripts.fetch_youtube_analytics_stub", _FYA)
    import scripts  # noqa: F401
    monkeypatch.setattr("scripts.fetch_youtube_analytics.fetch", _FYA.fetch, raising=False)
    monkeypatch.setattr(sys, "argv", ["verify", "--out", "api/youtube_stats.json"])

    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.main()
    printed = buf.getvalue()
    assert "Refusing to overwrite" in printed and "lost its day series" in printed
    assert "STATUS=fail" in printed
    assert json.loads(out.read_text(encoding="utf-8")) == committed, "the committed file must survive"
