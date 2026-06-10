"""Drift guards for the June 2026 Tesla show quality pass.

Pins the fixes from the flagship review:

* theme history mines the DIGEST, never the narrative template (the old
  code re-counted template phrases like "open questions" every episode,
  drowning real topics 112-to-single-digits);
* the narrative tracker auto-advances per-program ``last_mentioned``
  freshness from each digest (it had sat 13 days stale on a daily show)
  without ever touching the operator-curated status text;
* the listener-value score includes a length-substance component (nine
  of ten episodes shipped 15-35% under the 1600-word target while all
  clustering at the same 3.2 score);
* the podcast expansion retry fires on ANY below-target script when
  ``llm.podcast_expand_below_target`` is set (Tesla opts in);
* the X teaser leads with the episode hook and links the episode blog
  post (it previously carried zero episode-specific content);
* the prompts ban the "Taking a step back from today's headlines"
  boilerplate that opened every First Principles segment.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine import tesla_memory  # noqa: E402


class TestThemeExtractionFromDigestOnly:
    DIGEST = (
        "Tesla expanded robotaxi testing today. The wireless bms patent "
        "surfaced alongside shanghai exports data. Optimus actuators "
        "remain the open production question."
    )

    def test_no_template_phrases_counted(self, tmp_path):
        tesla_memory.update_theme_history_from_digest(tmp_path, self.DIGEST, 500)
        history = json.loads(
            (tmp_path / tesla_memory.THEME_HISTORY_FILENAME).read_text())
        themes = history["recurring_themes"]
        for noise in ("open questions", "questions show", "show following",
                      "mentioned current"):
            assert noise not in themes, (
                f"template phrase {noise!r} leaked back into theme history"
            )

    def test_digest_bigrams_and_program_keywords_counted(self, tmp_path):
        tesla_memory.update_theme_history_from_digest(tmp_path, self.DIGEST, 500)
        themes = json.loads(
            (tmp_path / tesla_memory.THEME_HISTORY_FILENAME).read_text()
        )["recurring_themes"]
        assert themes.get("robotaxi") == 1
        assert themes.get("optimus") == 1
        assert "wireless" in " ".join(themes)  # digest bigram surfaced

    def test_legacy_noise_scrubbed_from_existing_history(self, tmp_path):
        polluted = {
            "version": 1,
            "recurring_themes": {
                "open questions": 112, "questions show": 84,
                "giga texas": 41,
            },
            "theme_evolution": [],
        }
        (tmp_path / tesla_memory.THEME_HISTORY_FILENAME).write_text(
            json.dumps(polluted))
        tesla_memory.update_theme_history_from_digest(tmp_path, self.DIGEST, 501)
        themes = json.loads(
            (tmp_path / tesla_memory.THEME_HISTORY_FILENAME).read_text()
        )["recurring_themes"]
        assert "open questions" not in themes
        assert "questions show" not in themes
        assert themes.get("giga texas") == 41  # real topic preserved


class TestNarrativeAutoFreshness:
    def test_mentions_recorded_without_touching_status(self, tmp_path):
        digest = "Optimus actuators hit a milestone; Cybercab spotted in Austin."
        mentioned = tesla_memory.auto_update_narrative_from_digest(
            tmp_path, digest, 505, "2026-06-09")
        assert "optimus" in mentioned
        assert "cybercab_robotaxi" in mentioned
        tracker = tesla_memory.load_narrative_tracker(tmp_path)
        prog = tracker["programs"]["optimus"]
        assert prog["last_mentioned_episode"] == 505
        assert prog["last_mentioned_date"] == "2026-06-09"
        # Operator-curated fields untouched.
        assert prog["status"].startswith("Early production ramp")
        assert prog["last_major_update_episode"] is None

    def test_no_mentions_writes_nothing(self, tmp_path):
        mentioned = tesla_memory.auto_update_narrative_from_digest(
            tmp_path, "A quiet day with generic stock commentary.", 506,
            "2026-06-10")
        assert mentioned == []
        assert not (tmp_path / tesla_memory.NARRATIVE_TRACKER_FILENAME).exists()

    def test_block_renders_last_covered_freshness(self, tmp_path):
        tesla_memory.auto_update_narrative_from_digest(
            tmp_path, "FSD unsupervised rollout expands.", 505, "2026-06-09")
        tracker = tesla_memory.load_narrative_tracker(tmp_path)
        block = tesla_memory.build_narrative_status_block(tracker)
        assert "last covered on air: Ep505, 2026-06-09" in block
        assert "MAKE THE CONTINUITY AUDIBLE" in block

    def test_run_show_wires_auto_update(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "auto_update_narrative_from_digest" in src


class TestListenerValueLengthComponent:
    def _script(self, words):
        return " ".join(["tesla word"] * (words // 2))

    def test_short_script_scores_lower_than_full(self):
        from engine.listener_value_scorer import score_script

        short = score_script(self._script(1000), target_words=1600)
        full = score_script(self._script(1600), target_words=1600)
        assert short["length_substance"] < full["length_substance"]
        assert short["overall"] < full["overall"]
        assert full["length_substance"] == 10.0

    def test_legacy_callers_unchanged(self):
        from engine.listener_value_scorer import score_script

        result = score_script(self._script(1000))
        assert "length_substance" not in result

    def test_run_show_passes_target_words(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "target_words=getattr(config.llm" in src


class TestExpansionRetryThresholdFlag:
    def test_default_keeps_soft_floor_band(self):
        from engine.generator import _podcast_expansion_retry_threshold

        assert _podcast_expansion_retry_threshold(1600) == int(1600 * 0.6 * 1.1)

    def test_flag_raises_threshold_to_full_target(self):
        from engine.generator import _podcast_expansion_retry_threshold

        assert _podcast_expansion_retry_threshold(
            1600, expand_below_target=True) == 1600

    def test_tesla_opts_in(self):
        from engine.config import load_config

        cfg = load_config("shows/tesla.yaml")
        assert cfg.llm.podcast_expand_below_target is True

    def test_dataclass_default_off(self):
        from engine.config import LLMConfig

        assert LLMConfig().podcast_expand_below_target is False


class TestTeslaTeaserHasHookAndBlogLink:
    def _config(self):
        return SimpleNamespace(
            slug="tesla", name="Tesla Shorts Time",
            publishing=SimpleNamespace(x_teaser_template=""),
        )

    def test_hook_leads_and_blog_linked(self):
        import run_show

        teaser = run_show._build_teaser(
            self._config(), 505, "June 09, 2026",
            {"price": "416.22",
             "hook": "Multiple Cybercabs at an Atlanta service center."},
        )
        assert "Multiple Cybercabs at an Atlanta service center." in teaser
        assert "blog/tesla/ep505.html" in teaser
        assert "TSLA $416.22" in teaser
        assert "tesla-summaries.html" not in teaser

    def test_long_hook_truncated(self):
        import run_show

        teaser = run_show._build_teaser(
            self._config(), 505, "June 09, 2026", {"hook": "x" * 300},
        )
        assert "…" in teaser
        # Effective X length stays within budget (URL counts as 23).
        import re
        assert len(re.sub(r"https?://\S+", "x" * 23, teaser)) <= 280

    def test_no_hook_still_posts(self):
        import run_show

        teaser = run_show._build_teaser(
            self._config(), 505, "June 09, 2026", {},
        )
        assert "Ep 505" in teaser
        assert "blog/tesla/ep505.html" in teaser


class TestPromptBoilerplateBans:
    def test_digest_prompt_bans_step_back_opener(self):
        text = (_ROOT / "shows/prompts/tesla_digest.txt").read_text(
            encoding="utf-8")
        assert "BANNED OPENER" in text
        assert "VARY THE ANALYTICAL FRAMEWORK" in text

    def test_podcast_prompt_bans_step_back_transition(self):
        text = (_ROOT / "shows/prompts/tesla_podcast.txt").read_text(
            encoding="utf-8")
        assert "BANNED TRANSITION" in text
        assert "CONSECUTIVE-DAY RULE" in text

    def test_digest_prompt_enforces_takeover_overlap_check(self):
        text = (_ROOT / "shows/prompts/tesla_digest.txt").read_text(
            encoding="utf-8")
        assert "ENFORCEMENT" in text and "re-read your 5 Takeover items" in text

    def test_digest_prompt_has_attribution_tiers(self):
        text = (_ROOT / "shows/prompts/tesla_digest.txt").read_text(
            encoding="utf-8")
        assert "ATTRIBUTION DISCIPLINE" in text
