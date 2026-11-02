"""Nov 2 2026: the MAG 7 review's two real findings, and the interview
shows' transcript promise stated as built on every surface.

MAG 7 (review 2026-11-01, carried in the ledger):

* The Tomorrow Teaser spec said "name one specific thing ... to watch
  next", and 5 of Ep027-041 opened "Before we go, watch…". The fix removes
  the word from the spec (the cause) instead of banning a phrase.
* The digest floor sat under the script target it feeds.

The Age of AI and Nerra Voices: gate 2 auto-approves after seven days of
silence (workers/voices/src/index.ts), so no surface may say the guest
"approves the transcript before it publishes". The Sep 22 guard
(tests/test_age_of_ai_truth_2026_09_22.py) swept the site copy; the feed
description, the registry, the terms of service, the guest-picks page and
Mira's producer replies to guests still said it.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from engine.config import load_config

ROOT = Path(__file__).resolve().parent.parent
WORKER_TS = ROOT / "workers" / "voices" / "src" / "index.ts"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return " ".join(text.lower().split())


# ---------------------------------------------------------------------------
# MAG 7
# ---------------------------------------------------------------------------

def _teaser_line() -> str:
    for line in _read("shows/prompts/mag7_podcast.txt").splitlines():
        if line.startswith("[Tomorrow Teaser"):
            return line
    raise AssertionError("mag7_podcast.txt has no Tomorrow Teaser line")


class TestMag7Teaser:
    def test_the_spec_no_longer_supplies_the_verb(self):
        assert "watch" not in _teaser_line().lower(), (
            "the teaser spec says 'watch' again; 5 of Ep027-041 opened "
            "'Before we go, watch…' when it did"
        )

    def test_the_spec_quotes_no_frame_to_avoid(self):
        """De-seed by shape: a ban that quotes the phrase hands it back."""
        line = _teaser_line()
        quoted = re.findall(r'"([^"]+)"', line)
        assert quoted == ["Before we go"], quoted

    def test_the_next_step_is_a_fact_not_an_instruction(self):
        low = _teaser_line().lower()
        assert "subject of the sentence" in low
        assert "never an instruction to the listener" in low

    def test_the_older_rules_survive(self):
        line = _teaser_line()
        assert "never an earnings date" in line.lower()
        assert "never an item the calendar just read" in line

    def test_the_chapter_marker_still_finds_the_teaser(self):
        cfg = load_config(ROOT / "shows" / "mag7.yaml")
        markers = [m for m in cfg.chapters.section_markers
                   if getattr(m, "title", "") == "Tomorrow Teaser"]
        assert markers and re.search(markers[0].pattern, "Before we go, the court rules",
                                     re.IGNORECASE)


class TestMag7DigestFloor:
    def test_the_floor_is_at_or_above_the_script_target(self):
        cfg = load_config(ROOT / "shows" / "mag7.yaml")
        assert cfg.llm.min_digest_words >= cfg.llm.min_podcast_words
        assert cfg.llm.min_digest_words == 1300

    def test_the_floor_is_still_a_digest_lever(self):
        cfg = load_config(ROOT / "shows" / "mag7.yaml")
        assert cfg.llm.digest_expand_below_target is True
        assert cfg.llm.podcast_expand_below_target is False

    def test_the_skip_floor_did_not_move(self):
        cfg = load_config(ROOT / "shows" / "mag7.yaml")
        assert cfg.llm.min_podcast_publish_words == 660


class TestMag7LedgerRecordsTheVerdict:
    def test_the_review_lands_with_what_shipped(self):
        ledger = yaml.safe_load(_read("docs/reviews/ledger/mag7.yaml"))
        entry = next(r for r in ledger["reviews"] if r["date"] == "2026-11-01")
        assert len(entry["shipped"]) == 2
        withdrawn = [p["metric"] for p in entry["predictions"]
                     if p["verdict"] == "withdrawn"]
        assert any("Patrick and Vancouver" in m for m in withdrawn)

    def test_the_whisper_finding_is_not_retried(self):
        ledger = yaml.safe_load(_read("docs/reviews/ledger/mag7.yaml"))
        assert any("Patrick and Vancouver" in d for d in ledger["do_not_retry"])


# ---------------------------------------------------------------------------
# The interview shows: the transcript promise as built
# ---------------------------------------------------------------------------

OVERCLAIMS = (
    "approves the transcript before",
    "approves their transcript before",
    "approve their transcript before",
    "approves their own transcript before",
    "reviews the transcript before",
    "guest-approved transcript",
    "see the transcript before anything",
    "and approve it before it publishes",
)

SURFACES = (
    "shows/age_of_ai.yaml",
    "shows/nerra_voices.yaml",
    "shows/network_meta.yaml",
    "age_of_ai_podcast.rss",
    "templates/terms_of_service.html.j2",
    "templates/guest_picks.html.j2",
    "pipelines/producer/prompts/followup_reply.txt",
    "pipelines/producer/guest_reply.py",
    "pipelines/voices/publish_episode.py",
)


class TestTranscriptPromiseAsBuilt:
    def test_the_worker_still_auto_approves(self):
        """The guard's premise, read from the code that does it."""
        ts = WORKER_TS.read_text(encoding="utf-8")
        assert "auto-approve" in ts.lower() and "guest_review_deadline" in ts

    def test_no_surface_claims_the_guest_approves_before_publication(self):
        for rel in SURFACES:
            path = ROOT / rel
            if not path.exists():
                continue
            low = _flat(path.read_text(encoding="utf-8"))
            for phrase in OVERCLAIMS:
                assert phrase not in low, (
                    f"{rel} says {phrase!r}; gate 2 publishes after seven days "
                    "without a reply (workers/voices/src/index.ts)"
                )

    def test_the_feed_states_the_week_and_the_takedown(self):
        cfg = yaml.safe_load(_read("shows/age_of_ai.yaml"))
        desc = _flat(_find(cfg, "rss_description"))
        assert "week to approve" in desc and "takedown" in desc

    def test_the_committed_feed_carries_the_same_text(self):
        """Apple and Spotify read the feed, not the YAML; the next episode
        rebuilds it, but the correction should not wait for one."""
        cfg = yaml.safe_load(_read("shows/age_of_ai.yaml"))
        expected = " ".join(_find(cfg, "rss_description").split())
        channel = ET.parse(ROOT / "age_of_ai_podcast.rss").getroot().find("channel")
        assert " ".join(channel.findtext("description").split()) == expected
        summary = channel.findtext("{http://www.itunes.com/dtds/podcast-1.0.dtd}summary")
        assert " ".join(summary.split()) == expected

    def test_the_registry_states_the_week_for_both_shows(self):
        meta = yaml.safe_load(_read("shows/network_meta.yaml"))
        shows = meta.get("shows", meta)
        for slug in ("age_of_ai", "nerra_voices"):
            entry = shows[slug]
            for key in ("about_host",):
                assert "week to approve" in _flat(entry[key]), (slug, key)

    def test_the_terms_state_the_week_and_the_takedown(self):
        low = _flat(_read("templates/terms_of_service.html.j2"))
        assert "week to approve" in low and "takedown" in low
        assert "seven days without a reply" in low

    def test_mira_tells_guests_what_silence_does(self):
        low = _flat(_read("pipelines/producer/prompts/followup_reply.txt"))
        assert "week to approve" in low
        assert "publishes as sent" in low and "takedown" in low


def _find(obj, key):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                return v
            found = _find(v, key)
            if found is not None:
                return found
    return None
