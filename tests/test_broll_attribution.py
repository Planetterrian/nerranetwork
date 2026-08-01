"""Drift guards for the SpaceX CC-footage path + b-roll attribution chain.

The chain (August 2026): ``scripts/fetch_spacex_broll.py`` downloads ONLY
from YouTube videos whose own metadata says Creative Commons (per-video
gate — SpaceX's Flickr went CC BY-NC in Dec 2019 and its 2024+ streams
live on X with no license grant, so the CC-marked YouTube back-catalog is
the one legally usable slice for a monetized channel). Each download
records an ``attribution`` line in ``_provenance.json``;
``build_broll_pool.py`` copies it into ``broll.json``;
``engine.gallery_library.broll_attributions_for`` maps the clips a render
used back to credit lines; and ``build_long_form_metadata`` appends them
as a "Footage:" description block. CC BY makes that block a license
obligation, not garnish — these tests pin every link.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_SCRIPTS = PROJECT_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import fetch_spacex_broll as fsb  # noqa: E402
from engine import gallery_library as gl  # noqa: E402
from engine import video_metadata as vm  # noqa: E402


# ---------------------------------------------------------------------------
# fetch_spacex_broll — the CC license gate
# ---------------------------------------------------------------------------


class TestCcLicenseGate:
    def test_youtube_cc_string_passes(self):
        # Exact string yt-dlp reports for CC-marked videos.
        assert fsb.is_cc_license(
            "Creative Commons Attribution license (reuse allowed)")

    def test_standard_license_and_none_fail(self):
        assert not fsb.is_cc_license("Standard YouTube License")
        assert not fsb.is_cc_license(None)
        assert not fsb.is_cc_license("")

    def test_cc_by_40_wording_passes(self):
        # YouTube switched its CC option to 4.0 wording on 2025-08-01;
        # the gate must not be pinned to the 3.0 phrasing.
        assert fsb.is_cc_license("Creative Commons Attribution 4.0")

    def test_short_label_tracks_youtube_version_switch(self):
        cc = "Creative Commons Attribution license (reuse allowed)"
        assert fsb.cc_short_label(cc, "20240301") == "CC BY 3.0"
        assert fsb.cc_short_label(cc, "20250801") == "CC BY 4.0"
        assert fsb.cc_short_label("Standard YouTube License", "20240301") == ""

    def test_download_refuses_non_cc_video(self, monkeypatch, tmp_path):
        monkeypatch.setattr(fsb, "_probe", lambda url: {
            "id": "abc123", "title": "Starship Flight",
            "license": "Standard YouTube License", "duration": 300,
        })
        monkeypatch.setattr(fsb, "_require_ytdlp", lambda: "yt-dlp")
        assert fsb._download_clip(
            "https://youtu.be/abc123", "0:10-0:40", tmp_path) is None
        assert list(tmp_path.iterdir()) == []

    def test_download_refuses_full_webcast_without_section(
            self, monkeypatch, tmp_path):
        monkeypatch.setattr(fsb, "_probe", lambda url: {
            "id": "abc123", "title": "Launch Webcast",
            "license": "Creative Commons Attribution license (reuse allowed)",
            "duration": 4 * 3600,
        })
        monkeypatch.setattr(fsb, "_require_ytdlp", lambda: "yt-dlp")
        assert fsb._download_clip(
            "https://youtu.be/abc123", "full", tmp_path) is None

    def test_no_override_flag_exists(self):
        # The whole point is that non-CC SpaceX video cannot be fetched.
        # An --allow-non-cc style escape hatch must not appear.
        src = (_SCRIPTS / "fetch_spacex_broll.py").read_text(encoding="utf-8")
        assert "allow-non-cc" not in src
        assert "allow_non_cc" not in src


class TestScanUsability:
    """The Aug 1 scan looked like a hang and hid yt-dlp's real error.

    Serial probing of a deep scan (the CC-marked SpaceX material is
    mostly old, so a useful scan is hundreds of videos) gave no output
    for minutes, and ``check=True`` surfaced only "exit status 1" — a
    YouTube bot-challenge was indistinguishable from a deleted video.
    """

    def test_probe_failure_surfaces_ytdlp_stderr(self, monkeypatch):
        class _Proc:
            returncode = 1
            stdout = ""
            stderr = "ERROR: Sign in to confirm you're not a bot"

        monkeypatch.setattr(fsb, "_require_ytdlp", lambda: "yt-dlp")
        monkeypatch.setattr(fsb.subprocess, "run", lambda *a, **k: _Proc())
        with pytest.raises(RuntimeError) as exc:
            fsb._run_ytdlp(["-J"], timeout=10)
        assert "not a bot" in str(exc.value)

    def test_cookie_args_passed_through_or_absent(self):
        assert fsb._cookie_args("chrome") == ["--cookies-from-browser",
                                              "chrome"]
        assert fsb._cookie_args(None) == []

    def test_scan_is_concurrent_and_keeps_channel_order(self, monkeypatch,
                                                        capsys):
        ids = [f"vid{i}" for i in range(6)]
        monkeypatch.setattr(fsb, "_list_channel_ids", lambda *a, **k: ids)
        cc = "Creative Commons Attribution license (reuse allowed)"

        def _probe(url, cookies=None):
            vid = url.rsplit("=", 1)[-1]
            n = int(vid[-1])
            return {"id": vid, "title": f"T{n}", "duration": 60,
                    "upload_date": "20240101",
                    # Odd ones CC, even ones not — output must still be
                    # in channel order, not completion order.
                    "license": cc if n % 2 else "Standard YouTube License"}

        monkeypatch.setattr(fsb, "_probe", _probe)
        assert fsb._list_cc("chan", 6, workers=4) == 0
        printed = [l for l in capsys.readouterr().out.splitlines()
                   if l.startswith("CC ")]
        assert [l.split()[1] for l in printed] == ["vid1", "vid3", "vid5"]

    def test_scan_survives_individual_probe_failures(self, monkeypatch,
                                                     capsys):
        monkeypatch.setattr(fsb, "_list_channel_ids",
                            lambda *a, **k: ["good", "bad"])
        cc = "Creative Commons Attribution license (reuse allowed)"

        def _probe(url, cookies=None):
            if url.endswith("bad"):
                raise RuntimeError("yt-dlp exit 1: video unavailable")
            return {"title": "ok", "duration": 30, "license": cc,
                    "upload_date": "20240101"}

        monkeypatch.setattr(fsb, "_probe", _probe)
        assert fsb._list_cc("chan", 2, workers=2) == 0
        assert "CC  good" in capsys.readouterr().out

    def test_empty_channel_listing_is_an_error(self, monkeypatch):
        monkeypatch.setattr(fsb, "_list_channel_ids", lambda *a, **k: [])
        assert fsb._list_cc("chan", 10) == 1


class TestSectionParsing:
    def test_valid_sections(self):
        assert fsb.parse_section("19:45-20:40") == "*19:45-20:40"
        assert fsb.parse_section("1:02:10-1:03:00") == "*1:02:10-1:03:00"

    def test_full_and_none(self):
        assert fsb.parse_section("full") is None
        assert fsb.parse_section("FULL") is None
        assert fsb.parse_section(None) is None

    def test_garbage_raises(self):
        with pytest.raises(ValueError):
            fsb.parse_section("liftoff")
        with pytest.raises(ValueError):
            fsb.parse_section("19:45")


class TestAttributionLine:
    def test_shape_carries_source_license_and_link(self):
        line = fsb.build_attribution(
            "Starship's Third Flight Test", "vid42",
            "Creative Commons Attribution license (reuse allowed)",
            "20240314")
        assert "SpaceX" in line
        assert "Starship's Third Flight Test" in line
        assert "CC BY 3.0" in line
        assert "https://youtu.be/vid42" in line

    def test_long_titles_are_bounded(self):
        line = fsb.build_attribution("T" * 200, "vid42",
                                     "Creative Commons Attribution", "20240101")
        assert len(line) < 160

    def test_provenance_merge_preserves_earlier_runs(self, tmp_path):
        (tmp_path / "_provenance.json").write_text(json.dumps(
            [{"file": "old.mp4", "attribution": "SpaceX — old"}]),
            encoding="utf-8")
        fsb._merge_provenance(tmp_path, [
            {"file": "new.mp4", "attribution": "SpaceX — new"}])
        rows = json.loads(
            (tmp_path / "_provenance.json").read_text(encoding="utf-8"))
        assert {r["file"] for r in rows} == {"old.mp4", "new.mp4"}


# ---------------------------------------------------------------------------
# build_broll_pool — attribution into broll.json
# ---------------------------------------------------------------------------


class TestPoolBuilderAttribution:
    def _mod(self):
        import build_broll_pool
        return build_broll_pool

    def test_explicit_flag_wins(self, tmp_path):
        clip = tmp_path / "a.mp4"
        clip.write_bytes(b"x")
        (tmp_path / "_provenance.json").write_text(json.dumps(
            [{"file": "a.mp4", "attribution": "from provenance"}]),
            encoding="utf-8")
        assert self._mod().attribution_for(clip, "explicit") == "explicit"

    def test_provenance_lookup_by_file_name(self, tmp_path):
        clip = tmp_path / "a.mp4"
        clip.write_bytes(b"x")
        (tmp_path / "_provenance.json").write_text(json.dumps([
            {"file": "other.mp4", "attribution": "wrong"},
            {"file": "a.mp4", "attribution": "SpaceX — right"},
        ]), encoding="utf-8")
        assert self._mod().attribution_for(clip, None) == "SpaceX — right"

    def test_missing_provenance_is_empty(self, tmp_path):
        clip = tmp_path / "a.mp4"
        clip.write_bytes(b"x")
        assert self._mod().attribution_for(clip, None) == ""

    def test_nasa_fetcher_writes_attribution(self):
        src = (_SCRIPTS / "fetch_nasa_broll.py").read_text(encoding="utf-8")
        assert '"attribution"' in src


# ---------------------------------------------------------------------------
# gallery_library — used clips → credit lines
# ---------------------------------------------------------------------------


def _write_pool(digests_dir: Path, entries):
    (digests_dir / "broll.json").write_text(
        json.dumps({"clips": entries}), encoding="utf-8")


class TestBrollAttributionsFor:
    def test_matches_used_clips_by_basename(self, tmp_path):
        _write_pool(tmp_path, [
            {"url": "https://r2/broll/spacex/aaa.mp4",
             "attribution": "SpaceX — launch (CC BY 3.0, https://youtu.be/x)"},
            {"url": "https://r2/broll/spacex/bbb.mp4",
             "attribution": "NASA (public domain)"},
            {"url": "https://r2/broll/spacex/ccc.mp4",
             "attribution": "unused clip"},
        ])
        got = gl.broll_attributions_for(
            [Path("/cache/aaa.mp4"), Path("/cache/bbb.mp4")],
            digests_dir=tmp_path)
        assert got == [
            "SpaceX — launch (CC BY 3.0, https://youtu.be/x)",
            "NASA (public domain)",
        ]

    def test_unattributed_entries_contribute_nothing(self, tmp_path):
        # The recovered Grok Video clips are network-owned — no credit.
        _write_pool(tmp_path, [{"url": "https://r2/broll/tesla/aaa.mp4"}])
        assert gl.broll_attributions_for(
            [Path("/cache/aaa.mp4")], digests_dir=tmp_path) == []

    def test_dedupes_repeated_credits(self, tmp_path):
        _write_pool(tmp_path, [
            {"url": "https://r2/x/a.mp4", "attribution": "SpaceX — same"},
            {"url": "https://r2/x/b.mp4", "attribution": "SpaceX — same"},
        ])
        assert gl.broll_attributions_for(
            [Path("a.mp4"), Path("b.mp4")], digests_dir=tmp_path
        ) == ["SpaceX — same"]

    def test_none_and_missing_pool_are_clean(self, tmp_path):
        assert gl.broll_attributions_for(None, digests_dir=tmp_path) == []
        assert gl.broll_attributions_for([], digests_dir=tmp_path) == []
        assert gl.broll_attributions_for(
            [Path("a.mp4")], digests_dir=tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# video_metadata — the Footage description block
# ---------------------------------------------------------------------------


def _make_config(**overrides):
    publishing = SimpleNamespace(
        rss_title="SpaceX Daily",
        base_url="https://nerranetwork.com",
        rss_link="https://nerranetwork.com/spacex.html",
    )
    youtube_cfg = SimpleNamespace(
        tags=["spacex"], category_id=28, default_language="en",
        synthetic_disclosure="AI Disclosure: synthesized voice.",
        description_prompt_file="", pinned_comment_template="",
        enabled=True, channel="en",
    )
    return SimpleNamespace(
        name="SpaceX Daily", slug="spacex", publishing=publishing,
        youtube=youtube_cfg, keywords=["spacex"],
        **overrides,
    )


class TestFootageDescriptionBlock:
    def _meta(self, **kwargs):
        return vm.build_long_form_metadata(
            _make_config(), episode_num=53, today_str="2026-08-01",
            hook="Starship stacks for Flight 12",
            digest_text="body", audio_url="https://x/ep.mp3", **kwargs)

    def test_block_renders_credit_lines(self):
        meta = self._meta(footage_attribution=[
            "SpaceX — \"Flight Test\" (CC BY 3.0, https://youtu.be/x)",
            "NASA (public domain)",
        ])
        desc = meta["description"]
        assert "Footage:" in desc
        assert "CC BY 3.0" in desc
        assert "NASA (public domain)" in desc

    def test_absent_or_empty_is_byte_identical(self):
        base = self._meta()["description"]
        assert self._meta(footage_attribution=[])["description"] == base
        assert self._meta(footage_attribution=None)["description"] == base
        assert "Footage:" not in base

    def test_run_show_passes_footage_attribution(self):
        src = (PROJECT_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "footage_attribution=_broll_credits" in src
        assert "broll_attributions_for" in src
