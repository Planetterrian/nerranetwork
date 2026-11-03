"""Drift guards for the back-catalogue re-master (Nov 3 2026).

``scripts/remaster_episodes.py`` brings PUBLISHED episodes to the network's
-16 LUFS in place — a static gain through a limiter on the file that
shipped, uploaded to the SAME R2 key with the feed item's GUID kept. It
touches 208 published files (Unintended Consequences, Vancouver,
Collingwood), so the properties that matter are the ones that keep it
from doing harm:

* the render is a gain through a limiter, never a two-pass loudnorm
  with its linear option — on files at -4.8 dBTP a +9 dB linear pass
  falls back SILENTLY to dynamic mode, so "pure gain" would be false on
  exactly these files;
* the upload is refused unless the rendered file reads inside
  -16 ± 1.5 LUFS with a true peak at or under -1 dBTP;
* the feed item keeps its enclosure, link and GUID — never rebuilt from
  ``publishing.base_url`` (the Oct 20 2026 regression: fourteen repaired
  feeds pointed at the site and every app saw a new episode);
* a file already in the band is skipped unchanged;
* a dry run writes nothing.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.remaster_episodes as rm  # noqa: E402
import scripts.resynthesize_episode as rs  # noqa: E402
from engine.audio import (  # noqa: E402
    JOIN_MP3_ENCODE_ARGS,
    LOUDNESS_TOLERANCE_LU,
    PUBLISHED_LOUDNESS_LUFS,
)

UC_YAML = ROOT / "shows" / "unintended_consequences.yaml"
SLUG = "unintended_consequences"
EP161 = "Unintended_Consequences_Ep161_20261102.mp3"
EP093 = "Unintended_Consequences_Ep093_20260818.mp3"
ENCLOSURE_161 = f"https://op3.dev/e/audio.nerranetwork.com/{SLUG}/{EP161}"
GUID_161 = "unintended-consequences-ep161-20261102-090915381961"
HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

FEED = f"""<?xml version='1.0' encoding='UTF-8'?>
<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:podcast="https://podcastindex.org/namespace/1.0" version="2.0">
  <channel>
    <title>Unintended Consequences</title>
    <link>https://nerranetwork.com/unintended-consequences.html</link>
    <description>d</description>
    <item>
      <title>Ep 161: Hook</title>
      <link>https://nerranetwork.com/blog/{SLUG}/ep161.html</link>
      <description>body</description>
      <guid isPermaLink="false">{GUID_161}</guid>
      <enclosure url="{ENCLOSURE_161}" length="10120715" type="audio/mpeg"/>
      <itunes:episode>161</itunes:episode>
      <pubDate>Mon, 02 Nov 2026 08:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Ep 93: Hook</title>
      <link>https://nerranetwork.com/blog/{SLUG}/ep093.html</link>
      <description>body</description>
      <guid isPermaLink="false">unintended-consequences-ep093-20260818-090000000000</guid>
      <enclosure url="https://op3.dev/e/audio.nerranetwork.com/{SLUG}/{EP093}" length="9000000" type="audio/mpeg"/>
      <itunes:episode>93</itunes:episode>
      <pubDate>Tue, 18 Aug 2026 08:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Ep 7: elsewhere</title>
      <link>https://nerranetwork.com/blog/{SLUG}/ep007.html</link>
      <description>body</description>
      <guid isPermaLink="false">unintended-consequences-ep007-20260601-090000000000</guid>
      <enclosure url="https://op3.dev/e/audio.nerranetwork.com/tesla/Unintended_Consequences_Ep007_20260601.mp3" length="1" type="audio/mpeg"/>
      <itunes:episode>7</itunes:episode>
      <pubDate>Mon, 01 Jun 2026 08:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
"""

QUIET = {"I": -25.6, "LRA": 2.1, "TP": -4.8}
IN_BAND = {"I": -16.4, "LRA": 2.1, "TP": -3.0}
GOOD_AFTER = {"I": -16.3, "LRA": 2.2, "TP": -1.5}


@pytest.fixture(scope="module")
def uc_config():
    from engine.config import load_config
    return load_config(UC_YAML)


@pytest.fixture
def repo(tmp_path, monkeypatch, uc_config):
    """A repo root under tmp: the show's feed at its rss_file, an empty
    digests dir. Both scripts resolve repo paths through rs.ROOT."""
    monkeypatch.setattr(rs, "ROOT", tmp_path)
    (tmp_path / uc_config.publishing.rss_file).write_text(FEED, encoding="utf-8")
    (tmp_path / uc_config.episode.output_dir).mkdir(parents=True)
    return tmp_path


def _files(root: Path):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


class _Stubs:
    """Every side effect the apply path has, faked and recorded."""

    def __init__(self, monkeypatch, *, before=QUIET, after=GOOD_AFTER):
        self.downloads: list = []
        self.renders: list = []
        self.uploads: list = []
        self.feed_writes: list = []
        self.before = before
        self.after = after

        def fake_download(url, dest, *, label="", **kw):
            self.downloads.append(url)
            Path(dest).write_bytes(b"\0" * 8192)
            return 8192

        def fake_measure(path, **kw):
            path = Path(path)
            return self.after if path.name.startswith("remastered_") else self.before

        def fake_run(cmd, **kw):
            self.renders.append(list(cmd))
            Path(cmd[-1]).write_bytes(b"\1" * 4096)
            return subprocess.CompletedProcess(cmd, 0, b"", b"")

        def fake_upload(local_path, config):
            self.uploads.append(Path(local_path))
            return f"{config.storage.public_base_url}/{config.slug}/{Path(local_path).name}"

        monkeypatch.setattr("engine.http_download.download_to", fake_download)
        monkeypatch.setattr(rm, "measure_loudness", fake_measure)
        monkeypatch.setattr(rm.subprocess, "run", fake_run)
        monkeypatch.setattr(rm, "get_audio_duration", lambda p, **kw: 421.7)
        monkeypatch.setattr("engine.storage.upload_episode", fake_upload)
        monkeypatch.setattr("engine.publisher.update_rss_feed",
                            lambda **kw: self.feed_writes.append(kw))
        monkeypatch.setattr(rm, "check_edge",
                            lambda url: {"status": 200, "cf_cache_status": "HIT",
                                         "content_length": 8192, "cache_control": "max-age=14400"})


# ---------------------------------------------------------------------------
# The render is a gain through a limiter — never a linear loudnorm
# ---------------------------------------------------------------------------

class TestTheRenderIsAGain:
    def test_command_is_volume_through_a_limiter_with_the_master_encode(self, tmp_path):
        cmd = rm.render_cmd(tmp_path / "in.mp3", tmp_path / "out.mp3", 9.6)
        joined = " ".join(cmd)
        af = cmd[cmd.index("-af") + 1]
        assert af.startswith("volume=+9.6dB,")
        assert "alimiter=limit=" in af
        assert "loudnorm" not in joined
        assert "linear=true" not in joined
        # The shows' one master setting, contiguous, never a CBR cap.
        idx = cmd.index(JOIN_MP3_ENCODE_ARGS[0])
        assert cmd[idx:idx + len(JOIN_MP3_ENCODE_ARGS)] == JOIN_MP3_ENCODE_ARGS
        assert "-b:a" not in cmd

    def test_the_module_never_spells_the_linear_option(self):
        src = (ROOT / "scripts" / "remaster_episodes.py").read_text(encoding="utf-8")
        assert "linear=true" not in src

    def test_limiter_ceiling_sits_under_the_true_peak_refusal_line(self):
        """Calibrated on the published UC Ep161: a -1.0 dBFS ceiling
        re-measured at -0.5 dBTP after the encode, -1.5 dBFS landed on
        the line. The ceiling needs room for the overshoot."""
        assert rm.TRUE_PEAK_MAX_DBTP == -1.0
        assert rm.LIMITER_CEILING_DBFS <= -2.0
        assert rm.LIMITER_CEILING_LINEAR == pytest.approx(10 ** (rm.LIMITER_CEILING_DBFS / 20), abs=0.001)
        cmd = rm.render_cmd(Path("a"), Path("b"), 1.0)
        assert f"limit={rm.LIMITER_CEILING_LINEAR}" in cmd[cmd.index("-af") + 1]

    def test_band_is_the_audio_modules(self):
        assert rm.TARGET_LUFS == PUBLISHED_LOUDNESS_LUFS == -16.0
        assert rm.TOLERANCE_LU == LOUDNESS_TOLERANCE_LU == 1.5


class TestTheGainIsTheSharedOne:
    def test_in_band_is_no_gain(self):
        assert rm.plan_gain(IN_BAND) == 0.0
        assert rm.plan_gain({"I": -14.6, "TP": -1}) == 0.0

    def test_quiet_file_takes_the_personal_builders_gain(self):
        from engine.personal_edition import segment_gain_db
        assert rm.plan_gain(QUIET) == segment_gain_db(QUIET["I"]) == 9.6

    def test_unmeasured_is_no_gain(self):
        assert rm.plan_gain(None) == 0.0
        assert rm.plan_gain({"I": None}) == 0.0

    def test_in_band_accepts_only_the_band_and_the_peak(self):
        assert rm.in_band(GOOD_AFTER) is None
        assert rm.in_band({"I": -14.0, "LRA": 2, "TP": -2.0})
        assert rm.in_band({"I": -17.6, "LRA": 2, "TP": -2.0})
        assert rm.in_band({"I": -16.0, "LRA": 2, "TP": -0.5})
        assert rm.in_band({"I": -16.0, "LRA": 2, "TP": None})
        assert rm.in_band(None)


# ---------------------------------------------------------------------------
# The feed item never moves
# ---------------------------------------------------------------------------

class TestTheFeedIsTheRecord:
    def test_items_carry_enclosure_link_and_guid(self, repo, uc_config):
        items = rm.feed_items(repo / uc_config.publishing.rss_file)
        assert [i["episode"] for i in items] == [161, 93, 7]
        assert items[0]["enclosure_url"] == ENCLOSURE_161
        assert items[0]["guid"] == GUID_161
        assert items[0]["link"].endswith("/ep161.html")
        assert items[0]["filename"] == EP161
        assert set(items[0]) >= {"title", "description", "enclosure_url", "link", "guid"}

    def test_the_download_never_goes_through_op3(self, repo, uc_config):
        item = rm.feed_items(repo / uc_config.publishing.rss_file)[0]
        url = rm.download_url(item)
        assert "op3.dev" not in url
        assert url == f"https://audio.nerranetwork.com/{SLUG}/{EP161}"

    def test_select_one_all_and_since(self, repo, uc_config):
        items = rm.feed_items(repo / uc_config.publishing.rss_file)
        assert [i["episode"] for i in rm.select_items(items, episode=93)] == [93]
        assert [i["episode"] for i in rm.select_items(items, all_items=True)] == [161, 93, 7]
        assert [i["episode"] for i in rm.select_items(items, since="20260701")] == [161, 93]
        assert rm.select_items(items, episode=999) == []

    def test_artifacts_from_the_feed_match_resolve_artifacts(self, uc_config):
        """Two resolvers, one shape: the gain path starts from the
        enclosure, the repair path from the script. They must agree on
        every path or the feed refresh describes a different file."""
        items = rm.feed_items(ROOT / uc_config.publishing.rss_file)
        item = next((i for i in items if i["episode"] == 161), None)
        if item is None:
            pytest.skip("UC Ep161 not on the committed feed")
        try:
            expected = rs.resolve_artifacts(uc_config, 161)
        except FileNotFoundError:
            pytest.skip("UC Ep161 script not committed")
        assert rm.artifacts_from_item(uc_config, item) == expected

    def test_an_episode_with_no_committed_script_still_resolves(self, uc_config):
        """UC Ep093 is on the feed with no _tts.txt — a gain needs the
        file, not the text."""
        item = {"episode": 93, "filename": EP093, "enclosure_url": ENCLOSURE_161}
        art = rm.artifacts_from_item(uc_config, item)
        assert art.r2_key == f"{SLUG}/{EP093}"
        assert art.date_str == "20260818"
        assert art.chapters_path.name == "chapters_ep093.json"

    def test_the_module_never_builds_an_enclosure_from_the_site(self):
        """Read the CODE, not the docstring that names the trap."""
        import ast
        tree = ast.parse((ROOT / "scripts" / "remaster_episodes.py").read_text(encoding="utf-8"))
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert "base_url" not in attrs, (
            "the enclosure is the published one; publishing.base_url is the SITE"
        )
        assert "update_rss_feed" not in attrs | names, (
            "every feed write goes through resynthesize_episode.refresh_rss_item, "
            "which keeps the GUID"
        )
        assert "refresh_rss_item" in attrs


class TestApplyKeepsTheFeedItem:
    def test_apply_uploads_to_the_same_key_and_keeps_guid_link_and_enclosure(
            self, repo, uc_config, monkeypatch):
        stubs = _Stubs(monkeypatch)
        rc = rm.main(["--show", SLUG, "--episode", "161", "--apply"])
        assert rc == 0
        assert stubs.downloads == [f"https://audio.nerranetwork.com/{SLUG}/{EP161}"]
        assert [p.name for p in stubs.uploads] == [EP161]
        assert stubs.uploads[0].parent == repo / uc_config.episode.output_dir
        assert len(stubs.feed_writes) == 1
        seen = stubs.feed_writes[0]
        assert seen["keep_existing_guid"] is True
        assert seen["audio_url"] == ENCLOSURE_161
        assert "nerranetwork.com/digests/" not in seen["audio_url"]
        assert seen["episode_page_url"] == f"https://nerranetwork.com/blog/{SLUG}/ep161.html"
        assert seen["episode_title"] == "Ep 161: Hook"
        assert seen["mp3_duration"] == 421.7

    def test_apply_writes_the_log_and_a_second_pass_skips_it(self, repo, uc_config, monkeypatch, caplog):
        stubs = _Stubs(monkeypatch)
        assert rm.main(["--show", SLUG, "--episode", "161", "--apply"]) == 0
        log = repo / uc_config.episode.output_dir / rm.LOG_NAME
        entries = json.loads(log.read_text(encoding="utf-8"))
        assert len(entries) == 1
        e = entries[0]
        assert e["episode"] == 161 and e["file"] == EP161 and e["r2_key"] == f"{SLUG}/{EP161}"
        assert e["before"]["I"] == QUIET["I"] and e["after"]["I"] == GOOD_AFTER["I"]
        assert e["gain_db"] == 9.6 and e["applied"] is True
        assert e["guid"] == GUID_161
        assert e["remastered_at"].endswith("Z")
        assert e["edge"]["cf_cache_status"] == "HIT"
        caplog.set_level(logging.INFO, logger="remaster")
        assert rm.main(["--show", SLUG, "--since", "20260701", "--apply"]) == 0
        assert "Ep161: already re-mastered" in caplog.text
        assert len(stubs.uploads) == 2  # Ep161 once, then Ep093 on the second pass
        assert stubs.uploads[1].name == EP093
        assert len(json.loads(log.read_text(encoding="utf-8"))) == 2

    def test_an_enclosure_at_another_key_is_refused_before_download(self, repo, monkeypatch):
        stubs = _Stubs(monkeypatch)
        rc = rm.main(["--show", SLUG, "--episode", "7", "--apply"])
        assert rc == 1
        assert stubs.downloads == [] and stubs.uploads == [] and stubs.feed_writes == []


class TestRefusals:
    @pytest.mark.parametrize("after", [
        {"I": -14.0, "LRA": 2.2, "TP": -2.0},   # too loud
        {"I": -17.6, "LRA": 2.2, "TP": -2.0},   # still too quiet
        {"I": -16.0, "LRA": 2.2, "TP": -0.5},   # peak over the line
        None,                                    # unmeasured is not a pass
    ])
    def test_out_of_band_render_is_never_uploaded(self, repo, uc_config, monkeypatch, after):
        stubs = _Stubs(monkeypatch, after=after)
        rc = rm.main(["--show", SLUG, "--episode", "161", "--apply"])
        assert rc == 1
        assert len(stubs.renders) == 1
        assert stubs.uploads == [] and stubs.feed_writes == []
        assert not (repo / uc_config.episode.output_dir / rm.LOG_NAME).exists()
        assert not (repo / uc_config.episode.output_dir / EP161).exists()

    def test_in_band_file_is_skipped_unchanged(self, repo, uc_config, monkeypatch, caplog):
        stubs = _Stubs(monkeypatch, before=IN_BAND)
        caplog.set_level(logging.INFO, logger="remaster")
        rc = rm.main(["--show", SLUG, "--episode", "161", "--apply"])
        assert rc == 0
        assert len(stubs.downloads) == 1
        assert stubs.renders == [] and stubs.uploads == [] and stubs.feed_writes == []
        assert "skipped unchanged" in caplog.text

    def test_a_failed_upload_leaves_the_feed_alone(self, repo, monkeypatch):
        stubs = _Stubs(monkeypatch)
        monkeypatch.setattr("engine.storage.upload_episode", lambda p, c: None)
        assert rm.main(["--show", SLUG, "--episode", "161", "--apply"]) == 1
        assert stubs.feed_writes == []


class TestDryRunWritesNothing:
    def test_dry_run_prints_the_plan_and_touches_no_file(self, repo, uc_config, monkeypatch, caplog):
        stubs = _Stubs(monkeypatch)
        before = _files(repo)
        caplog.set_level(logging.INFO, logger="remaster")
        rc = rm.main(["--show", SLUG, "--episode", "161"])
        assert rc == 0
        assert _files(repo) == before
        assert stubs.renders == [] and stubs.uploads == [] and stubs.feed_writes == []
        text = caplog.text
        assert "before:  I=-25.6 LUFS" in text
        assert "planned gain: +9.6 dB" in text
        assert f"would upload to r2://{uc_config.storage.bucket}/{SLUG}/{EP161} (same key)" in text
        assert "volume=+9.6dB" in text and "alimiter" in text
        assert "linear=true" not in text
        assert "DRY RUN" in text

    def test_limit_caps_the_batch(self, repo, monkeypatch, caplog):
        stubs = _Stubs(monkeypatch)
        caplog.set_level(logging.INFO, logger="remaster")
        rc = rm.main(["--show", SLUG, "--all", "--limit", "1"])
        assert rc == 0
        assert len(stubs.downloads) == 1
        assert "Limit of 1" in caplog.text

    def test_default_limit_is_a_listenable_batch(self):
        assert rm.DEFAULT_LIMIT == 20


# ---------------------------------------------------------------------------
# With ffmpeg: a -25 fixture comes out in band, a -16.4 one is untouched
# ---------------------------------------------------------------------------

def _noise_at(tmp_path: Path, name: str, target_lufs: float) -> Path:
    """Pink noise rendered to *target_lufs* (two passes: render, measure,
    correct) — a crest factor near a voice's and a stable integrated reading."""
    base = tmp_path / f"{name}_base.mp3"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i",
                    "anoisesrc=color=pink:seed=7:duration=6:sample_rate=44100:amplitude=0.3",
                    "-ac", "1", "-c:a", "libmp3lame", "-q:a", "0", str(base)],
                   check=True, capture_output=True, timeout=120)
    first = rm.measure_loudness(base)
    assert first and first["I"] is not None
    out = tmp_path / f"{name}.mp3"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(base),
                    "-af", f"volume={target_lufs - first['I']:+.1f}dB",
                    "-c:a", "libmp3lame", "-q:a", "0", str(out)],
                   check=True, capture_output=True, timeout=120)
    got = rm.measure_loudness(out)
    assert got and abs(got["I"] - target_lufs) < 0.6, got
    return out


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not on PATH")
class TestWithFfmpeg:
    def test_a_minus_25_file_comes_out_in_band_under_the_peak_line(self, tmp_path):
        src = _noise_at(tmp_path, "quiet", -25.0)
        before = rm.measure_loudness(src)
        gain = rm.plan_gain(before)
        assert gain > 0
        dst = tmp_path / "remastered_quiet.mp3"
        after = rm.remaster_file(src, dst, gain)
        assert dst.exists()
        assert abs(after["I"] - rm.TARGET_LUFS) <= rm.TOLERANCE_LU, after
        assert after["TP"] is not None and after["TP"] <= rm.TRUE_PEAK_MAX_DBTP, after
        # No sample moved in time: the chapters and transcript still describe it.
        assert rm.get_audio_duration(dst) == pytest.approx(rm.get_audio_duration(src), abs=0.1)

    def test_a_minus_16_4_file_is_skipped_unchanged(self, tmp_path, uc_config, monkeypatch):
        src = _noise_at(tmp_path, "fine", -16.4)
        assert rm.plan_gain(rm.measure_loudness(src)) == 0.0
        monkeypatch.setattr(rs, "ROOT", tmp_path)
        (tmp_path / uc_config.episode.output_dir).mkdir(parents=True)
        monkeypatch.setattr("engine.http_download.download_to",
                            lambda url, dest, **kw: shutil.copyfile(src, dest) and Path(dest).stat().st_size)
        item = {"episode": 161, "filename": EP161, "enclosure_url": ENCLOSURE_161,
                "title": "t", "description": "d", "link": "", "guid": GUID_161}
        work = tmp_path / "work"
        work.mkdir()
        result = rm.process_item(uc_config, item, apply=True, skip_upload=False, workdir=work)
        assert result["status"] == rm.STATUS_SKIPPED
        assert result["gain_db"] == 0.0
        assert not list(work.glob("remastered_*"))

    def test_a_render_measuring_minus_14_is_refused_and_removed(self, tmp_path, monkeypatch):
        src = _noise_at(tmp_path, "quiet2", -25.0)
        gain = rm.plan_gain(rm.measure_loudness(src))
        real = rm.measure_loudness
        monkeypatch.setattr(rm, "measure_loudness",
                            lambda p, **kw: {"I": -14.0, "LRA": 2.0, "TP": -2.0}
                            if Path(p).name.startswith("remastered_") else real(p, **kw))
        dst = tmp_path / "remastered_quiet2.mp3"
        with pytest.raises(rm.OutOfBand):
            rm.remaster_file(src, dst, gain)
        assert not dst.exists()


# ---------------------------------------------------------------------------
# The workflow
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def wf():
    import yaml
    path = ROOT / ".github" / "workflows" / "remaster-episodes.yml"
    assert path.exists(), "the re-master is run from Actions; the R2 credentials live there"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class TestWorkflow:
    def test_dry_run_is_the_default(self, wf):
        inputs = wf[True]["workflow_dispatch"]["inputs"]
        assert inputs["apply"]["default"] is False
        assert inputs["episodes"]["required"] is True

    def test_concurrency_is_per_show(self, wf):
        assert "inputs.show" in wf["concurrency"]["group"]
        assert wf["concurrency"]["cancel-in-progress"] is False

    def test_commit_only_the_feed_and_the_log_and_only_when_something_was_applied(self, wf):
        step = wf["jobs"]["remaster"]["steps"][-1]
        assert "safe-commit-push" in step["uses"]
        cond = step["if"]
        assert "inputs.apply" in cond
        assert "remaster_applied != '0'" in cond, (
            "a batch where one episode was refused still commits the feed for "
            "the ones whose objects already changed"
        )
        paths = step["with"]["add-paths"]
        assert ".mp3" not in paths, "episode audio never enters git history (landmine #1)"
        assert "*.rss" in paths
        assert "remaster_log.json" in paths

    def test_r2_credentials_present_and_no_tts_key(self, wf):
        steps = wf["jobs"]["remaster"]["steps"]
        assert any("setup-ffmpeg" in (s.get("uses") or "") for s in steps)
        env = next(s for s in steps if s.get("name") == "Re-master")["env"]
        for key in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            assert key in env
        assert "GROK_API_KEY" not in env and "XAI_API_KEY" not in env, (
            "a gain never spends a synthesis call"
        )

    def test_the_runner_is_pinned(self, wf):
        assert wf["jobs"]["remaster"]["runs-on"] == "ubuntu-26.04"
