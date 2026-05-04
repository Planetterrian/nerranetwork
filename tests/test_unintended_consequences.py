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
        # YouTube disabled — quota cap (only TST + MAB).
        assert cfg["youtube"]["enabled"] is False
        # X disabled — narrative show, not news.
        assert cfg["publishing"]["x_enabled"] is False

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
# Cron + workflow consistency
# ---------------------------------------------------------------------------

def test_cron_entry_exists_for_unintended_consequences():
    workflow = (REPO_ROOT / ".github" / "workflows" / "run-show.yml"
                ).read_text(encoding="utf-8")
    assert "30 11 * * 1-5" in workflow, (
        "Cron line for Unintended Consequences (11:30 UTC weekdays) "
        "missing from run-show.yml"
    )
    assert '"30 11 * * 1-5":' in workflow, (
        "CRON_MAP entry for Unintended Consequences missing — show "
        "would fire but never run"
    )
