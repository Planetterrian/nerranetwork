"""Drift guards for the Sep 13 2026 YouTube pass (first slate after the
Sep 12 review + simplification pass).

Four things this pins, each measured on the 2026-09-13 slate:

* The x264 render-speed TRIAL is wired: run-show.yml carries
  ``NERRA_X264_PRESET`` with a ``faster`` default (operator-directed),
  the register names the live metric, and the dub workflow does NOT
  carry it (the RU/FR credit files stay a same-week control).
* ``wall_duration_s`` no longer double-counts the long-form render (MAB
  Ep165: 3,257 s reported on a 2,225 s step).
* The Shorts price-line guard covers the RU/FR shapes the dub channels
  pick their windows on ("рост на 2,3%" / "151 dollars et 21 cents en
  hausse de 2,3 %" both opened a SpaceX dub Short on 09-13).
* The gallery manifest rebuild is incremental + parallel, keeps the
  committed manifest on a failed walk, and the nightly is the one full
  re-read (the serial walk cost 38 of finalize's 39 minutes, ~13x/day).
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.gallery_uploader import GalleryConfig  # noqa: E402
from scripts import build_gallery_manifest as bgm  # noqa: E402


# ---------------------------------------------------------------------------
# Render-speed trial
# ---------------------------------------------------------------------------


class TestRenderSpeedTrial:
    def _env_lines(self, name: str):
        wf = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        return [ln.strip() for ln in wf.splitlines()
                if ln.strip().startswith("NERRA_X264_PRESET:")]

    def test_run_show_carries_the_preset_with_a_faster_default(self):
        lines = self._env_lines("run-show.yml")
        assert len(lines) == 1, lines
        assert "vars.NERRA_X264_PRESET" in lines[0], (
            "the repo variable must be able to end the trial without a commit")
        assert "'faster'" in lines[0]

    def test_dub_workflow_stays_on_the_code_default(self):
        """The metric reads EN credit files; the dubs are the control."""
        assert self._env_lines("multilingual.yml") == []

    def test_trial_is_registered_on_the_live_metric(self):
        data = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text())
        rows = {e["id"]: e for e in data["experiments"]}
        e = rows["x264-preset-faster-2026-09-13"]
        assert e["metric"] == "long_form_render_median_s_7d"
        assert e["status"] == "decide" and str(e["readout"]) == "2026-09-20"
        assert e["baseline"] == 1024


# ---------------------------------------------------------------------------
# wall_duration_s
# ---------------------------------------------------------------------------


class TestWallDurationNoDoubleCount:
    def test_nested_render_timer_is_not_added_twice(self):
        from engine.metrics import PipelineMetrics, _NESTED_DURATION_COUNTERS
        assert "long_form_render_duration_s" in _NESTED_DURATION_COUNTERS
        m = PipelineMetrics("models_agents_beginners", 165)
        m.record("tts_duration_s", 92.0)
        m.record("audio_mix_duration_s", 65.2)
        m.record("youtube_publish_duration_s", 1720.5)   # contains the render
        m.record("long_form_render_duration_s", 1273.3)  # nested in the above
        m.record("audio_duration_s", 655.3)
        d = m.to_dict()
        assert 1877.0 <= d["wall_duration_s"] <= 1878.0, d["wall_duration_s"]
        assert d["wall_duration_s"] < 3000, "must not read as a watchdog breach"


# ---------------------------------------------------------------------------
# Price line on the dub channels
# ---------------------------------------------------------------------------


class TestPriceLineCoversTheDubs:
    @pytest.mark.parametrize("text", [
        # The two titles that shipped on 2026-09-13.
        "рост на 2,3%",
        "151 dollars et 21 cents en hausse de 2,3 %",
        # The translated close line as the TTS stage writes it.
        "Эс-Пи-Си-Экс закрылась на уровне ста пятидесяти одного доллара и "
        "двадцати одного цента, рост на два и три десятых процента.",
        "S-P-C-X clôture à cent cinquante et un dollars et vingt et un "
        "cents, en hausse de deux virgule trois pour cent.",
        "S-P-C-X a clôturé à 151 dollars et 21 cents.",
        "up 2.3%.",
        "SPCX closed at $151.21, up 2.3%.",
    ])
    def test_quote_shapes_are_never_openers(self, text):
        from engine.shorts_selector import is_price_line
        assert is_price_line(text)

    @pytest.mark.parametrize("text", [
        "Старлинк вырос на 40% за год, и это меняет расчёт.",
        "Le lanceur a coûté 15 dollars par kilo.",
        "En hausse de 40 % sur un an, les revenus dépassent les prévisions.",
        "The booster is slotted for Flight Twelve at $15 billion.",
        "Три тысячи сверхновых проверяют модели расширения Вселенной.",
    ])
    def test_ordinary_numbers_still_qualify(self, text):
        from engine.shorts_selector import is_price_line
        assert not is_price_line(text)


# ---------------------------------------------------------------------------
# Gallery manifest: incremental walk
# ---------------------------------------------------------------------------


def _sidecar(slug: str, ep: str, image_id: str, **extra):
    d = {
        "image_id": image_id, "show_slug": slug, "show_name": slug.title(),
        "episode_id": ep, "episode_title": f"{slug} {ep}",
        "episode_date": "2026-09-13", "format": "jpeg",
        "generated_at": f"2026-09-13T08:00:0{image_id[-1]}+00:00",
    }
    d.update(extra)
    return d


def _key(sc):
    return f"{sc['show_slug']}/{sc['episode_date']}/{sc['episode_id']}/{sc['image_id']}.json"


class _FakeS3:
    def __init__(self, sidecars):
        self.objects = {_key(sc): sc for sc in sidecars}
        self.fetched = []

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        objects = self.objects

        class _P:
            def paginate(self, Bucket):
                keys = sorted(objects)
                for i in range(0, len(keys), 2):
                    yield {"Contents": [{"Key": k} for k in keys[i:i + 2]]}
        return _P()

    def get_object(self, Bucket, Key):
        self.fetched.append(Key)
        return {"Body": io.BytesIO(json.dumps(self.objects[Key]).encode())}


@pytest.fixture
def cfg():
    return GalleryConfig(
        bucket="nerra-gallery", endpoint_url="https://r2.example",
        access_key="k", secret_key="s", public_base_url="https://gallery.example",
    )


class TestIncrementalManifestWalk:
    def test_only_new_sidecars_are_downloaded(self, cfg, monkeypatch):
        old = [_sidecar("tesla", "ep603", "aaa1"), _sidecar("tesla", "ep603", "aaa2")]
        new = _sidecar("tesla", "ep604", "bbb1")
        existing = bgm.build_manifest(old, config=cfg)
        fake = _FakeS3(old + [new])
        monkeypatch.setattr(bgm, "_make_s3_client", lambda config: fake)
        sidecars = bgm.walk_bucket(cfg, existing=existing, workers=2)
        assert fake.fetched == [_key(new)]
        assert {sc["image_id"] for sc in sidecars} == {"aaa1", "aaa2", "bbb1"}

    def test_vanished_sidecars_drop_out(self, cfg, monkeypatch):
        old = [_sidecar("tesla", "ep603", "aaa1"), _sidecar("tesla", "ep603", "aaa2")]
        existing = bgm.build_manifest(old, config=cfg)
        fake = _FakeS3(old[:1])
        monkeypatch.setattr(bgm, "_make_s3_client", lambda config: fake)
        sidecars = bgm.walk_bucket(cfg, existing=existing)
        assert fake.fetched == []
        assert [sc["image_id"] for sc in sidecars] == ["aaa1"]

    def test_full_rebuild_ignores_the_cache(self, cfg, monkeypatch):
        old = [_sidecar("tesla", "ep603", "aaa1"), _sidecar("tesla", "ep603", "aaa2")]
        existing = bgm.build_manifest(old, config=cfg)
        fake = _FakeS3(old)
        monkeypatch.setattr(bgm, "_make_s3_client", lambda config: fake)
        bgm.walk_bucket(cfg, existing=existing, full=True)
        assert sorted(fake.fetched) == sorted(_key(sc) for sc in old)

    def test_excluded_composites_are_never_cached(self, cfg, monkeypatch):
        """Thumbnail composites are filtered out of the manifest, so the
        cache cannot hold them; they are re-read (cheaply) each pass and
        stay excluded."""
        keep = _sidecar("tesla", "ep603", "aaa1")
        thumb = _sidecar("tesla", "ep603", "ttt1", intended_use="thumbnail_variant")
        existing = bgm.build_manifest([keep, thumb], config=cfg)
        assert existing["image_count"] == 1
        fake = _FakeS3([keep, thumb])
        monkeypatch.setattr(bgm, "_make_s3_client", lambda config: fake)
        sidecars = bgm.walk_bucket(cfg, existing=existing)
        assert fake.fetched == [_key(thumb)]
        assert bgm.build_manifest(sidecars, config=cfg)["image_count"] == 1

    def test_cached_records_rebuild_byte_identical_manifest(self, cfg, monkeypatch):
        old = [_sidecar("spacex", "ep099", "ccc1"), _sidecar("tesla", "ep604", "aaa1")]
        existing = bgm.build_manifest(old, config=cfg)
        fake = _FakeS3(old)
        monkeypatch.setattr(bgm, "_make_s3_client", lambda config: fake)
        rebuilt = bgm.build_manifest(bgm.walk_bucket(cfg, existing=existing), config=cfg)
        assert bgm._without_timestamp(rebuilt) == bgm._without_timestamp(existing)

    def test_failed_walk_keeps_the_committed_manifest(self, cfg, tmp_path, monkeypatch):
        out = tmp_path / "gallery-manifest.json"
        existing = bgm.build_manifest([_sidecar("tesla", "ep603", "aaa1")], config=cfg)
        out.write_text(json.dumps(existing))
        (tmp_path / "gallery").mkdir()
        (tmp_path / "gallery" / "tesla.json").write_text("{}")
        monkeypatch.setenv("R2_GALLERY_BUCKET", "nerra-gallery")
        monkeypatch.setenv("R2_ENDPOINT_URL", "https://r2.example")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "k")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "s")

        def _boom(config):
            raise RuntimeError("R2 hiccup")
        monkeypatch.setattr(bgm, "_make_s3_client", _boom)
        assert bgm.main(["--out", str(out)]) == 0
        assert json.loads(out.read_text())["image_count"] == 1
        assert (tmp_path / "gallery" / "tesla.json").exists(), "slices must survive too"


class TestManifestWorkflowWiring:
    def _cmd(self, name):
        wf = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        return [ln.strip() for ln in wf.splitlines()
                if "scripts/build_gallery_manifest.py" in ln and not ln.strip().startswith("#")
                and not ln.strip().startswith("- '")]

    def test_finalize_runs_the_incremental_pass(self):
        cmds = self._cmd("run-show.yml")
        assert len(cmds) == 1 and "--full" not in cmds[0], cmds

    def test_nightly_and_standalone_are_full_rebuilds(self):
        for name in ("nightly-maintenance.yml", "build-gallery-manifest.yml"):
            cmds = self._cmd(name)
            assert cmds and all("--full" in c for c in cmds), (name, cmds)
