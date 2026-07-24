"""Drift guards for the July 24 2026 memory-expansion + content-lake pass.

Memory: MIT / DP Pod / Age of AI joined the narrative-memory registry
(MIT's bespoke investment tracker untouched; Age of AI's memory feeds the
Nerra Voices interview pipeline since it never runs through run_show), and
the theme miner gained the doubled-word / junk-bigram filters plus the
[label](url) strip that had never been ported back to Tesla's bespoke
module ("google google" ranked #1 on Tesla at count 109).

Content lake: the engine was healthy but the orchestration was not — the
finalize job rebuilt the public search index from an EMPTY (gitignored,
un-backfilled) lake after every episode (~13x/day committed a zero-episode
search-index.json; site search served 0 results most of every day), and
nightly built the dashboard BEFORE the backfill so api/dashboard.json
always reported "lake: 0 episodes". Shows that don't run through run_show
(Age of AI) never entered the lake at all.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import show_memory as sm  # noqa: E402
from engine.tesla_memory import _JUNK_BIGRAMS, _extract_bigrams  # noqa: E402


# ---------------------------------------------------------------------------
# Memory expansion — registry + wiring
# ---------------------------------------------------------------------------

class TestNewMemoryShows:
    @pytest.mark.parametrize("slug", ["modern_investing", "dp_pod", "age_of_ai"])
    def test_registered(self, slug):
        cfg = sm.get_config(slug)
        assert cfg is not None
        assert cfg.default_programs
        assert cfg.theme_keywords
        assert cfg.file_prefix == slug

    @pytest.mark.parametrize("slug", ["modern_investing", "dp_pod", "age_of_ai"])
    def test_seeded_tracker_committed(self, slug):
        p = ROOT / "digests" / slug / f"{slug}_narrative_tracker.json"
        assert p.exists(), f"seeded narrative tracker missing for {slug}"
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data.get("programs")

    def test_mit_prompts_carry_placeholder(self):
        digest = (ROOT / "shows/prompts/modern_investing_digest.txt").read_text()
        podcast = (ROOT / "shows/prompts/modern_investing_podcast.txt").read_text()
        assert "{narrative_memory_section}" in digest
        assert "{narrative_memory_section}" in podcast

    def test_dp_pod_prompts_carry_placeholder(self):
        digest = (ROOT / "shows/prompts/dp_pod_digest.txt").read_text()
        podcast = (ROOT / "shows/prompts/dp_pod_podcast.txt").read_text()
        assert "{narrative_memory_section}" in digest
        assert "{narrative_memory_section}" in podcast

    def test_mit_hook_wires_memory(self):
        src = (ROOT / "shows/hooks/modern_investing.py").read_text()
        assert 'memory_pre_fetch(config, "modern_investing")' in src
        assert 'memory_post_generate(' in src

    def test_dp_pod_hook_wires_memory(self):
        src = (ROOT / "shows/hooks/dp_pod.py").read_text()
        assert 'memory_pre_fetch(config, "dp_pod")' in src
        assert "def post_generate" in src

    def test_podcast_stage_setdefaults_memory_key(self):
        # A hook-load failure on a memory show must degrade to an empty
        # section, never a KeyError in podcast prompt substitution (the
        # digest stage already had this; the podcast stage did not).
        src = (ROOT / "run_show.py").read_text()
        assert src.count('setdefault("narrative_memory_section", "")') >= 2

    def test_mit_keeps_bespoke_investment_tracker(self):
        # The narrative layer must not replace the trade ledger.
        src = (ROOT / "shows/hooks/modern_investing.py").read_text()
        assert "investment_tracker" in src or "TRACKER_FILENAME" in src


class TestAgeOfAiVoicesMemory:
    def test_common_exposes_memory_block(self):
        src = (ROOT / "pipelines/voices/common.py").read_text()
        assert "def episode_memory_block" in src

    @pytest.mark.parametrize("prompt", [
        "question_generation.txt", "episode_thesis.txt", "mira_narration.txt",
    ])
    def test_prompts_carry_show_memory_token(self, prompt):
        text = (ROOT / "pipelines/voices/prompts" / prompt).read_text()
        assert "{{show_memory}}" in text

    def test_call_sites_pass_show_memory(self):
        # load_prompt does literal {{token}} replacement — an unpassed
        # token ships VERBATIM into the LLM prompt, so every call site of
        # the three templates must pass show_memory.
        briefs = (ROOT / "pipelines/voices/generate_briefs.py").read_text()
        produce = (ROOT / "pipelines/voices/produce_episode.py").read_text()
        assert briefs.count("show_memory=") == 2
        assert "show_memory=episode_memory_block()" in produce

    def test_memory_block_reads_real_summaries(self):
        from pipelines.voices.common import episode_memory_block
        block = episode_memory_block()
        # Ep1 (Patrick Novak, 2026-07-20) is committed — the block must
        # surface it and carry the no-retread instruction.
        assert "Ep1" in block
        assert "do not retread" in block.lower() or "not retread" in block.lower()


# ---------------------------------------------------------------------------
# Theme-mining hygiene (the "google google" / "need know" class)
# ---------------------------------------------------------------------------

class TestThemeMiningHygiene:
    def test_doubled_word_bigrams_skipped(self):
        # "Google News … Google News" with "news" stopworded used to
        # produce "google google" (count 109 on Tesla).
        bigrams = _extract_bigrams("google google google nvidia robotaxi")
        assert "google google" not in bigrams
        assert "google nvidia" in bigrams

    def test_junk_bigrams_skipped(self):
        assert "need know" in _JUNK_BIGRAMS
        bigrams = _extract_bigrams("everything need know about agents")
        assert "need know" not in bigrams

    def test_tesla_miner_strips_markdown_source_labels(self):
        # The June 13 [label](url) strip landed in show_memory but was
        # never ported to the bespoke Tesla module.
        src = (ROOT / "engine/tesla_memory.py").read_text()
        assert r"\[[^\]]*\]\([^)]*\)" in src

    @pytest.mark.parametrize("path", [
        "digests/tesla_shorts_time/tesla_theme_history.json",
        "digests/models_agents/models_agents_theme_history.json",
        "digests/planetterrian/planetterrian_theme_history.json",
    ])
    def test_committed_histories_scrubbed(self, path):
        themes = json.loads((ROOT / path).read_text())["recurring_themes"]
        for key in themes:
            words = key.split()
            assert not (len(words) == 2 and words[0] == words[1]), \
                f"doubled-word junk theme survived: {key!r}"
            assert key not in _JUNK_BIGRAMS, f"junk bigram survived: {key!r}"


# ---------------------------------------------------------------------------
# Content lake orchestration
# ---------------------------------------------------------------------------

class TestLakeOrchestration:
    def test_finalize_backfills_before_search_index(self):
        wf = (ROOT / ".github/workflows/run-show.yml").read_text()
        # The finalize job's regen block must backfill the (gitignored)
        # lake before rebuilding the public search index — otherwise it
        # commits a zero-episode index after every episode.
        finalize = wf.split("finalize:")[1]
        backfill_pos = finalize.find("backfill_content_lake.py")
        index_pos = finalize.find("build_search_index.py")
        assert backfill_pos != -1, "finalize job lost the lake backfill"
        assert index_pos != -1
        assert backfill_pos < index_pos, \
            "backfill must run BEFORE build_search_index in finalize"

    def test_nightly_backfills_before_dashboard(self):
        wf = (ROOT / ".github/workflows/nightly-maintenance.yml").read_text()
        backfill_pos = wf.find("backfill_content_lake.py")
        dash_pos = wf.find("generate_dashboard.py")
        index_pos = wf.find("build_search_index.py")
        assert -1 not in (backfill_pos, dash_pos, index_pos)
        assert backfill_pos < dash_pos, \
            "nightly must backfill the lake BEFORE the dashboard build " \
            "(or the dashboard reports 'lake: 0 episodes' every night)"
        assert backfill_pos < index_pos

    def test_search_index_refuses_empty_over_good(self, tmp_path, monkeypatch):
        import importlib
        sys.path.insert(0, str(ROOT / "scripts"))
        bsi = importlib.import_module("build_search_index")
        out = tmp_path / "search-index.json"
        out.write_text(json.dumps({
            "schema_version": 1, "episode_count": 42,
            "shows": [{"slug": "tesla"}], "episodes": [{"show_slug": "tesla"}],
        }), encoding="utf-8")
        monkeypatch.setattr(bsi, "get_all_search_docs", lambda: [])
        monkeypatch.setattr(sys, "argv", ["build_search_index.py", "--out", str(out)])
        rc = bsi.main()
        assert rc == 0  # non-blocking
        kept = json.loads(out.read_text(encoding="utf-8"))
        assert kept["episode_count"] == 42, \
            "an empty lake must never overwrite a populated search index"

    def test_backfill_summaries_fallback_present(self):
        src = (ROOT / "scripts/backfill_content_lake.py").read_text()
        assert "summaries fallback" in src.lower() or "summaries_json" in src
