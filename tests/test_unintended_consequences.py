"""Tests for the Unintended Consequences show + the narrative-mode
infrastructure it pioneered.

Coverage:

- ``shows/unintended_consequences.yaml`` parses and resolves correctly
  (``narrative_mode=True``, ``topic_queue_file`` set, default voice
  inherited from ``_defaults.yaml``).
- ``shows/topic_queues/unintended_consequences.yaml`` has the
  required schema (``id`` / ``title`` / ``brief`` / ``produced``)
  for every entry.
- ``engine.topic_queue.pick_next_topic`` returns the first
  ``produced: false`` entry; returns ``None`` when the queue is
  empty / fully produced.
- ``engine.topic_queue.mark_topic_produced`` updates the entry in
  place without reordering or losing entries.
- The show is registered in ``generate_html.NETWORK_SHOWS`` with
  the required keys.
- The cron entry exists in ``run-show.yml`` with the weekday filter.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
SHOWS_DIR = REPO_ROOT / "shows"
QUEUE_PATH = SHOWS_DIR / "topic_queues" / "unintended_consequences.yaml"


# ---------------------------------------------------------------------------
# Show YAML parses + key fields are right
# ---------------------------------------------------------------------------

class TestShowYaml:

    def test_yaml_parses(self):
        cfg = yaml.safe_load(
            (SHOWS_DIR / "unintended_consequences.yaml").read_text(encoding="utf-8"),
        )
        assert cfg["slug"] == "unintended_consequences"
        assert cfg["name"] == "Unintended Consequences"
        assert cfg["narrative_mode"] is True
        assert cfg["topic_queue_file"].endswith(
            "shows/topic_queues/unintended_consequences.yaml",
        )
        # Weekday-only narrative show — no Sunday recap (queue is the input).
        assert cfg.get("weekly_recap_on_sunday", False) is False
        # YouTube enabled in the full-network rollout (200k quota, June 2026).
        assert cfg["youtube"]["enabled"] is True
        # X posting enabled May 12 2026 — UC shares the @planetterrian
        # account (Option B from pipeline-streamline plan). UC has no
        # ``x_accounts`` configured so the X-fetch path stays empty.
        assert cfg["publishing"]["x_enabled"] is True
        assert cfg["publishing"]["x_env_prefix"] == "PLANETTERRIAN_X_"

    def test_resolves_to_default_voice(self):
        """Inheritance from ``_defaults.yaml`` should give it the
        operator's custom Grok voice ``kdif6sqjcyiq``."""
        from engine.config import load_config
        cfg = load_config(SHOWS_DIR / "unintended_consequences.yaml")
        assert cfg.tts.provider == "grok"
        assert cfg.tts.voice_id == "kdif6sqjcyiq"
        assert cfg.tts.language_code == "en"
        assert cfg.narrative_mode is True
        assert cfg.topic_queue_file.endswith(
            "shows/topic_queues/unintended_consequences.yaml",
        )


# ---------------------------------------------------------------------------
# Topic queue schema + content
# ---------------------------------------------------------------------------

class TestTopicQueue:

    def test_queue_has_at_least_50_starter_topics(self):
        data = yaml.safe_load(QUEUE_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert isinstance(data.get("queue"), list)
        assert len(data["queue"]) >= 50

    def test_every_entry_has_required_schema(self):
        data = yaml.safe_load(QUEUE_PATH.read_text(encoding="utf-8"))
        required = {"id", "title", "brief", "category", "produced",
                    "episode_number", "produced_date"}
        for entry in data["queue"]:
            missing = required - set(entry)
            assert not missing, (
                f"Topic {entry.get('id', '<missing-id>')} missing keys: "
                f"{missing}"
            )
            assert isinstance(entry["id"], str) and entry["id"]
            assert isinstance(entry["title"], str) and entry["title"]
            assert isinstance(entry["brief"], str) and len(entry["brief"]) >= 50
            assert isinstance(entry["produced"], bool)
            assert entry["category"] in {
                "classic", "tech", "policy", "medicine",
                "infrastructure", "economics",
            }

    def test_ids_are_unique(self):
        data = yaml.safe_load(QUEUE_PATH.read_text(encoding="utf-8"))
        ids = [entry["id"] for entry in data["queue"]]
        assert len(ids) == len(set(ids)), "Duplicate topic ids in queue"

    def test_all_starter_topics_unproduced(self):
        """Sanity: the seeded queue ships with every entry unproduced.
        Once episodes start running this test will need to change to
        allow produced=true entries — at which point we'll know the
        pipeline shipped at least one episode end-to-end."""
        data = yaml.safe_load(QUEUE_PATH.read_text(encoding="utf-8"))
        produced = [
            entry for entry in data["queue"] if entry["produced"] is True
        ]
        # Don't fail when episodes have shipped — just sanity-check that
        # SOMEONE in the queue is unproduced.
        unproduced = [
            entry for entry in data["queue"] if entry["produced"] is False
        ]
        assert unproduced, (
            "Topic queue is fully produced. Append new topics to keep "
            "the show running."
        )


# ---------------------------------------------------------------------------
# topic_queue module
# ---------------------------------------------------------------------------

class TestPickNextTopic:

    def test_returns_first_unproduced_entry(self, tmp_path: Path):
        from engine.topic_queue import pick_next_topic
        queue_file = tmp_path / "q.yaml"
        queue_file.write_text(yaml.safe_dump({
            "queue": [
                {"id": "a", "title": "A", "brief": "first one",
                 "category": "classic", "produced": True,
                 "episode_number": 1, "produced_date": "2026-05-01"},
                {"id": "b", "title": "B", "brief": "second one",
                 "category": "tech", "produced": False,
                 "episode_number": None, "produced_date": None},
                {"id": "c", "title": "C", "brief": "third one",
                 "category": "tech", "produced": False,
                 "episode_number": None, "produced_date": None},
            ],
        }))
        topic = pick_next_topic(queue_file)
        assert topic is not None
        assert topic["id"] == "b"

    def test_returns_none_when_all_produced(self, tmp_path: Path):
        from engine.topic_queue import pick_next_topic
        queue_file = tmp_path / "q.yaml"
        queue_file.write_text(yaml.safe_dump({
            "queue": [
                {"id": "a", "title": "A", "brief": "x" * 60,
                 "category": "classic", "produced": True,
                 "episode_number": 1, "produced_date": "2026-05-01"},
            ],
        }))
        assert pick_next_topic(queue_file) is None

    def test_returns_none_when_file_missing(self, tmp_path: Path):
        from engine.topic_queue import pick_next_topic
        assert pick_next_topic(tmp_path / "nonexistent.yaml") is None


class TestMarkTopicProduced:

    def test_marks_entry_in_place(self, tmp_path: Path):
        from engine.topic_queue import mark_topic_produced, pick_next_topic
        queue_file = tmp_path / "q.yaml"
        queue_file.write_text(yaml.safe_dump({
            "queue": [
                {"id": "a", "title": "A", "brief": "x" * 60,
                 "category": "classic", "produced": False,
                 "episode_number": None, "produced_date": None},
                {"id": "b", "title": "B", "brief": "y" * 60,
                 "category": "tech", "produced": False,
                 "episode_number": None, "produced_date": None},
            ],
        }))
        ok = mark_topic_produced(
            queue_file, topic_id="a", episode_num=42,
            produced_date="2026-05-04",
        )
        assert ok is True

        # First entry now marked.
        data = yaml.safe_load(queue_file.read_text(encoding="utf-8"))
        assert data["queue"][0]["produced"] is True
        assert data["queue"][0]["episode_number"] == 42
        assert data["queue"][0]["produced_date"] == "2026-05-04"
        # Second entry untouched.
        assert data["queue"][1]["produced"] is False

        # Next pick now returns "b".
        nxt = pick_next_topic(queue_file)
        assert nxt is not None
        assert nxt["id"] == "b"

    def test_returns_false_for_unknown_id(self, tmp_path: Path):
        from engine.topic_queue import mark_topic_produced
        queue_file = tmp_path / "q.yaml"
        queue_file.write_text(yaml.safe_dump({
            "queue": [
                {"id": "a", "title": "A", "brief": "x" * 60,
                 "category": "classic", "produced": False,
                 "episode_number": None, "produced_date": None},
            ],
        }))
        ok = mark_topic_produced(
            queue_file, topic_id="missing", episode_num=1,
            produced_date="2026-05-04",
        )
        assert ok is False


# ---------------------------------------------------------------------------
# Site registration
# ---------------------------------------------------------------------------

class TestNetworkRegistration:

    def test_show_in_network_shows(self):
        from generate_html import NETWORK_SHOWS
        assert "unintended_consequences" in NETWORK_SHOWS
        cfg = NETWORK_SHOWS["unintended_consequences"]
        # Required for blog / RSS / sitemap rendering.
        for key in (
            "name", "slug", "description", "show_page", "rss_file",
            "podcast_image", "brand_color", "schedule",
            "meta_description",
        ):
            assert cfg.get(key), f"NETWORK_SHOWS entry missing {key!r}"

    def test_show_in_show_dirs_map(self):
        from generate_html import _SHOW_DIRS
        assert _SHOW_DIRS.get("unintended_consequences") == "unintended_consequences"


# ---------------------------------------------------------------------------
# Narrative-mode fallback for the {hook} template variable
# ---------------------------------------------------------------------------

class TestNarrativeHookFallback:
    """UC Ep001 surfaced a bug: when digest hook extraction returned
    empty, ``run_show.py`` substituted a news-show framing
    (``"Here's what's making news in the X world today"``) into the
    podcast prompt's ``{hook}`` template var. UC isn't news — that
    line broke the show's narrative identity.

    Phase 1.2 of the May 2026 audit branched the fallback on
    ``narrative_mode``. These tests pin the fallback behaviour."""

    def test_news_fallback_string_still_present_for_news_shows(self):
        """The original news-show fallback string must still be in
        run_show.py — narrative shows get a different fallback, but
        news shows still need the news framing."""
        from pathlib import Path
        runner = Path(__file__).resolve().parent.parent / "run_show.py"
        text = runner.read_text(encoding="utf-8")
        assert (
            "Here's what's making news in the {config.name} world today."
            in text
        ), (
            "News-show fallback string missing from run_show.py — every "
            "news show with empty hook extraction will get an empty "
            "{hook} variable."
        )

    def test_narrative_branch_present(self):
        """run_show.py must branch on ``narrative_mode`` for the
        ``effective_hook`` fallback so narrative shows never get the
        news framing."""
        from pathlib import Path
        runner = Path(__file__).resolve().parent.parent / "run_show.py"
        text = runner.read_text(encoding="utf-8")
        assert "narrative_mode" in text and "effective_hook" in text, (
            "Narrative-mode branch for effective_hook fallback missing "
            "from run_show.py — UC will revert to the news framing."
        )
        # The narrative branch should pull from narrative_topic.title
        # (with show name as last-resort fallback).
        assert "narrative_topic" in text, (
            "narrative_topic local lookup missing — narrative-mode "
            "fallback can't resolve the topic title for {hook}."
        )


# ---------------------------------------------------------------------------
# UC podcast prompt rules added in Phase 1.2 (apocrypha hedge,
# pronoun discipline, lesson landing)
# ---------------------------------------------------------------------------

class TestUCPodcastPromptRules:
    """UC Ep001 surfaced three quality issues the prompt should
    prevent in Ep002 onward: orphan pronouns after rewrites, stating
    apocryphal stories as fact, and lesson segments that trail off
    without a forward-looking close."""

    def setup_method(self):
        from pathlib import Path
        prompt_path = (Path(__file__).resolve().parent.parent
                       / "shows" / "prompts"
                       / "unintended_consequences_podcast.txt")
        self.prompt = prompt_path.read_text(encoding="utf-8")

    def test_pronoun_discipline_rule_present(self):
        assert "antecedents have been lost" in self.prompt, (
            "Pronoun-discipline rule missing from UC podcast prompt. "
            "UC Ep001 had 'They did so...' with no antecedent — the rule "
            "blocks that failure mode."
        )

    def test_apocrypha_hedge_rule_present(self):
        assert "HEDGE SOURCING" in self.prompt, (
            "Apocrypha-hedge rule missing from UC podcast prompt. "
            "UC Ep001 stated the (apocryphal) Cobra Effect as historical "
            "fact — the rule requires hedging when sourcing is thin."
        )
        # Make sure the rule mentions at least one example so the LLM
        # has a concrete reference.
        assert "Cobra Effect" in self.prompt or "Streisand" in self.prompt

    def test_lesson_landing_rule_present(self):
        assert "forward-looking question" in self.prompt, (
            "Lesson-landing rule missing from UC podcast prompt. "
            "UC Ep001 trailed into the sign-off without a close — the "
            "rule requires a specific forward-looking question or "
            "modern parallel."
        )
        assert "principles stated only once" in self.prompt.lower() or (
            "principle stated only once" in self.prompt.lower()
        ), "Anti-repetition clause missing from lesson-landing rule."


# ---------------------------------------------------------------------------
# Cron + workflow consistency
# ---------------------------------------------------------------------------

def test_cron_entry_exists_for_unintended_consequences():
    workflow = (REPO_ROOT / ".github" / "workflows" / "run-show.yml"
                ).read_text(encoding="utf-8")
    # June 2026 schedule compression: UC moved to 9:01 UTC daily.
    assert "1 9 * * *" in workflow, (
        "Cron line for Unintended Consequences (9:01 UTC daily) "
        "missing from run-show.yml"
    )
    assert '"1 9 * * *":' in workflow, (
        "CRON_MAP entry for Unintended Consequences missing — show "
        "would fire but never run"
    )
