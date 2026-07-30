"""Drift guards for the July 18 2026 YouTube growth pass.

Workstreams pinned here:
  - title bundle (one Grok call → long titles + thumbnail punch + Short
    titles) with graceful parsing fallbacks
  - punch-text thumbnails (legacy rendering when punch is empty)
  - auto-comments (post_video_comment contract + config gates)
  - analytics schema v2 (subscriber metrics + channel history)
  - channel-specific RU long-form floor in the adaptive policy
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ---------------------------------------------------------------------------
# Title bundle
# ---------------------------------------------------------------------------

class TestTitleBundle:
    def _patch_grok(self, monkeypatch, text):
        import engine.generator as gen
        monkeypatch.setattr(gen, "_call_grok",
                            lambda *a, **k: (text, {}))

    def test_bundle_happy_path(self, monkeypatch):
        from engine.youtube_titles import generate_title_bundle
        self._patch_grok(monkeypatch, (
            "TITLE: Tesla Robotaxi Fleet Grows 50% in One Day\n"
            "TITLE: Why Tesla Just Scaled Robotaxis Overnight\n"
            "TITLE: Robotaxi Expansion Hits Texas Streets\n"
            "PUNCH: ROBOTAXI FLEET +50%\n"
            "SHORT1: Robotaxi fleet up 50% overnight\n"
            "SHORT2: The unsupervised-miles milestone\n"
        ))
        out = generate_title_bundle(
            hook="h", digest_text="d", show_name="S", episode_num=1,
            short_window_texts=["window one text", "window two text"],
        )
        assert len(out["titles"]) == 3
        assert out["punch_text"] == "ROBOTAXI FLEET +50%"
        assert out["short_titles"] == [
            "Robotaxi fleet up 50% overnight",
            "The unsupervised-miles milestone",
        ]

    def test_bundle_malformed_output_returns_empty_fields(self, monkeypatch):
        from engine.youtube_titles import generate_title_bundle
        self._patch_grok(monkeypatch, "complete nonsense with no labels")
        out = generate_title_bundle(
            hook="h", digest_text="d", show_name="S", episode_num=1,
            short_window_texts=["w"],
        )
        assert out["titles"] == []
        assert out["punch_text"] == ""
        assert out["short_titles"] == [""]

    def test_bundle_call_failure_never_raises(self, monkeypatch):
        import engine.generator as gen
        from engine.youtube_titles import generate_title_bundle
        def _boom(*a, **k):
            raise RuntimeError("api down")
        monkeypatch.setattr(gen, "_call_grok", _boom)
        out = generate_title_bundle(
            hook="h", digest_text="d", show_name="S", episode_num=1,
        )
        assert out == {"titles": [], "punch_text": "", "short_titles": []}

    def test_punch_cleaning_rejects_junk(self):
        from engine.youtube_titles import _clean_punch
        assert _clean_punch("robotaxi fleet +50%") == "ROBOTAXI FLEET +50%"
        assert _clean_punch("BREAKING") == ""            # single hype word
        assert _clean_punch("BREAKING NEWS") == ""       # generic hype
        assert _clean_punch("A" * 40) == ""              # too long
        assert _clean_punch(
            "ONE TWO THREE FOUR FIVE") == ""             # too many words

    def test_bundle_prompt_exists_and_has_labels(self):
        text = (_ROOT / "shows/prompts/_shared/youtube_title_bundle.txt"
                ).read_text(encoding="utf-8")
        for label in ("TITLE:", "PUNCH:", "SHORT1:", "{short_windows}",
                      "{performance_hint}"):
            assert label in text

    def test_legacy_titles_function_untouched(self, monkeypatch):
        # The old single-purpose call must keep working as the fallback.
        from engine.youtube_titles import generate_youtube_titles
        self._patch_grok(monkeypatch, "Great Title About Things\n")
        out = generate_youtube_titles(
            hook="h", digest_text="d", show_name="S", episode_num=1, n=1,
        )
        assert out == ["Great Title About Things"]


# ---------------------------------------------------------------------------
# Punch-text thumbnails
# ---------------------------------------------------------------------------

class TestPunchThumbnail:
    def _base_image(self, tmp_path):
        from PIL import Image
        p = tmp_path / "base.jpg"
        Image.new("RGB", (1280, 720), (30, 60, 90)).save(p)
        return p

    def test_punch_uses_larger_font_than_hook(self, tmp_path):
        from engine.publisher import generate_episode_thumbnail
        base = self._base_image(tmp_path)
        _, hook_font = generate_episode_thumbnail(
            base, 1, "Jul 18", tmp_path / "hook.jpg",
            hook="Tesla's robotaxi fleet grew fifty percent in a single day",
            show_name="Show",
        )
        _, punch_font = generate_episode_thumbnail(
            base, 1, "Jul 18", tmp_path / "punch.jpg",
            hook="Tesla's robotaxi fleet grew fifty percent in a single day",
            show_name="Show",
            punch_text="ROBOTAXI +50%",
        )
        assert punch_font is not None and hook_font is not None
        assert punch_font > hook_font

    def test_empty_punch_is_exact_legacy_path(self, tmp_path):
        from engine.publisher import generate_episode_thumbnail
        base = self._base_image(tmp_path)
        p1, f1 = generate_episode_thumbnail(
            base, 1, "Jul 18", tmp_path / "a.jpg", hook="Some hook",
            show_name="Show",
        )
        p2, f2 = generate_episode_thumbnail(
            base, 1, "Jul 18", tmp_path / "b.jpg", hook="Some hook",
            show_name="Show", punch_text="",
        )
        assert f1 == f2
        assert p1.read_bytes() == p2.read_bytes()

    def test_config_flag_default_true(self):
        from engine.config import YouTubeConfig
        assert YouTubeConfig().thumbnail_punch_text is True


# ---------------------------------------------------------------------------
# Auto-comments
# ---------------------------------------------------------------------------

class TestAutoComment:
    def test_post_video_comment_never_raises_on_failure(self):
        from engine.youtube import post_video_comment
        # No credentials → build() blows up internally → None, no raise.
        assert post_video_comment(
            credentials=None, video_id="abc", text="hi") is None

    def test_empty_text_or_video_is_noop(self):
        from engine.youtube import post_video_comment
        assert post_video_comment(
            credentials=None, video_id="", text="hi") is None
        assert post_video_comment(
            credentials=None, video_id="abc", text="  ") is None

    def test_config_flag_default_true(self):
        from engine.config import YouTubeConfig
        assert YouTubeConfig().auto_comment is True

    def test_pinned_comment_helper_shared_with_description(self):
        from types import SimpleNamespace
        from engine.video_metadata import build_pinned_comment_text
        cfg = SimpleNamespace(youtube=SimpleNamespace(
            pinned_comment_template="Ep {episode_num}: {hook} — {full_episode_url}",
        ))
        out = build_pinned_comment_text(
            cfg, hook="Big story", episode_num=7,
            audio_url="https://x/audio.mp3",
        )
        assert out == "Ep 7: Big story — https://x/audio.mp3"

    def test_run_show_wires_comments(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "post_video_comment" in src
        assert "build_pinned_comment_text" in src
        assert "auto_comment" in src

    def test_ru_dub_comment_never_links_an_english_video(self):
        """The original invariant, re-expressed after the July 2026 pilot.

        This used to pin the literal line
        ``if long_url and bool(getattr(yt, "auto_comment"`` — i.e. post a
        comment ONLY when a RU long-form shipped. That gate was doing
        two jobs: keeping English URLs out of Russian Shorts (correct,
        and still enforced below) and, accidentally, suppressing the
        comment entirely — @NerraRU sits on a shorts-only tier for most
        shows, so ``long_url`` was empty on nearly every run and the
        network's highest-reach surface posted nothing at all.

        The comment now falls back to the show's RUSSIAN landing page.
        What must never happen is the English video, so that is what is
        asserted: the English ``long_url`` is used only inside the
        ``if long_url`` branch.
        """
        src = (_ROOT / "engine/ru_dub.py").read_text(encoding="utf-8")
        assert "post_video_comment" in src
        assert "Полный выпуск" in src
        # The RU comment block must still branch on long_url...
        assert "if long_url:" in src
        # ...and the fallback must resolve a RU destination, not a URL
        # from any other channel.
        assert 'channel="ru"' in src
        assert "destination_for(" in src


# ---------------------------------------------------------------------------
# Analytics v2 + channel history
# ---------------------------------------------------------------------------

class TestAnalyticsV2:
    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fya", _ROOT / "scripts/fetch_youtube_analytics.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_metrics_include_subscribers(self):
        m = self._mod()
        assert "subscribersGained" in m._METRICS
        assert "subscribersLost" in m._METRICS

    def test_channel_history_append_idempotent(self, tmp_path):
        m = self._mod()
        path = tmp_path / "hist.json"
        snap = {"en": {"subscribers": 10, "total_views": 100}}
        m.append_channel_history(snap, path)
        m.append_channel_history(snap, path)  # same day re-run
        rows = json.loads(path.read_text())["rows"]
        assert len(rows) == 1
        assert rows[0]["subscribers"] == 10

    def test_performance_hint_blends_subscribers(self):
        src = (_ROOT / "scripts/update_youtube_performance.py"
               ).read_text(encoding="utf-8")
        assert "subscribers_gained" in src

    def test_dashboard_has_youtube_channels_block(self):
        src = (_ROOT / "scripts/generate_dashboard.py"
               ).read_text(encoding="utf-8")
        assert "youtube_channel_history.json" in src
        assert "top_subscriber_videos" in src


# ---------------------------------------------------------------------------
# Channel-specific long-form floor
# ---------------------------------------------------------------------------

class TestChannelLongFloor:
    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "uyp", _ROOT / "scripts/update_youtube_policy.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_floors(self):
        m = self._mod()
        assert m.LONG_VPD_FLOOR["en"] == 1.0
        assert m.LONG_VPD_FLOOR["ru"] == 2.0

    def test_ru_needs_higher_velocity_for_long(self):
        m = self._mod()
        vpds = [1.5] * 6  # 1.5 vpd across 6 videos
        tier_en, *_ = m.compute_tier(vpds, [3.0] * 6, "C", "en")
        tier_ru, *_ = m.compute_tier(vpds, [3.0] * 6, "C", "ru")
        assert tier_en in ("A", "B")   # 1.5 >= 1.0 → long on
        assert tier_ru in ("C", "D")   # 1.5 < 2.0 → long stays off

    def test_ru_clears_higher_bar(self):
        m = self._mod()
        tier_ru, *_ = m.compute_tier([2.5] * 6, [5.0] * 6, "C", "ru")
        assert tier_ru == "A"


# ---------------------------------------------------------------------------
# Smart Shorts start network-wide (July 22 2026)
# ---------------------------------------------------------------------------

class TestSmartShortsNetworkWide:
    """Every YouTube-enabled show uses the smart Shorts selector.

    July 22 2026 finding: 7 enabled shows still resolved ``voice`` mode, so
    every Short opened on the 10 s intro/branding beat — the weakest
    possible Shorts opening — and the adaptive policy could never raise
    them to 2 Shorts (the raise requires smart mode). MAB + FPD had smart
    mode but the 5.0 default threshold fell back 6/6 episodes; 3.5 is the
    proven fleet setting (Tesla/SpaceX/FF).
    """

    def _yaml(self, path):
        import yaml
        return yaml.safe_load((_ROOT / "shows" / path).read_text(
            encoding="utf-8"))

    def test_every_enabled_show_uses_smart_mode(self):
        for path in sorted((_ROOT / "shows").glob("*.yaml")):
            if path.name.startswith("_"):
                continue
            data = self._yaml(path.name)
            yt = (data or {}).get("youtube") or {}
            if not yt.get("enabled"):
                continue
            assert yt.get("shorts_start_mode") == "smart", path.name

    def test_enabled_shows_pin_fleet_threshold(self):
        # The 5.0 dataclass default causes chronic fallback on
        # non-numeric transcript styles — enabled shows pin 3.5.
        for path in sorted((_ROOT / "shows").glob("*.yaml")):
            if path.name.startswith("_"):
                continue
            data = self._yaml(path.name)
            yt = (data or {}).get("youtube") or {}
            if not yt.get("enabled"):
                continue
            assert float(yt.get("shorts_min_score_threshold", 5.0)) <= 3.5, \
                path.name
