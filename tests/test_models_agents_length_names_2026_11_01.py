"""Nov 1 2026: the two operator decisions on the Models & Agents review of
Oct 31 (PR #1593).

- Length, option C: 1,200-1,400 words is the show's natural length. The
  target drops to 1,300 and the skip floor stays at 900 (60 % of the old
  1,500), pinned so the lower target never lowers it.
- Names, the data-side lever: the two-pass script prompt gets the names the
  digest carries (engine/names_to_keep.py) instead of a fourth prose
  instruction to keep them.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from engine.config import load_config
from engine.names_to_keep import build_names_block, names_to_keep

ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / "shows/prompts/models_agents_podcast.txt"

DIGEST = """# Models & Agents

> **Hook line about a release.**

**What You Need to Know:** Mistral AI shipped Mistral Large 4 and Anthropic updated Claude Opus 5.5.

### Model Updates

**Kyutai CADRE: Video Autoencoders That Cut World Model Lag Below Two Hundred Milliseconds**
Kyutai released CADRE, a video autoencoder. The New York Times reported on the CPU cost of AI-assisted coding. A user ran Qwen3.8-27B in 16 GB MLX on an M4 Max. Space is tight in memory, the post says. Source: [kyutai.org](https://kyutai.org/cadre)

### Also Today
- At 164 k tokens the LM Studio engine used 48 GB of memory.
"""


class TestNamesToKeep:
    def test_names_come_from_the_item_bodies_as_written(self):
        names = names_to_keep(DIGEST)
        for expected in ("Mistral Large 4", "Claude Opus 5.5", "Kyutai",
                         "CADRE", "New York Times", "Qwen3.8-27B",
                         "M4 Max", "LM Studio"):
            assert expected in names, (expected, names)

    def test_title_case_headlines_labels_and_furniture_are_not_names(self):
        names = names_to_keep(DIGEST)
        joined = " | ".join(names)
        # The headline capitalises every word; its words are not names.
        assert "Video Autoencoders" not in joined
        assert "World Model" not in joined
        # The bold "What You Need to Know:" label opens a line.
        assert "You Need" not in joined and "Know" not in names
        # Units and numbers alone, short acronyms, compound adjectives and
        # a word the digest also writes in lower case are not names.
        for bad in ("GB MLX", "164", "CPU", "AI-assisted", "Space"):
            assert bad not in names, (bad, names)

    def test_a_shorter_name_inside_a_longer_one_is_dropped(self):
        names = names_to_keep("Mistral AI said Mistral Large 4 beats Mistral Medium.")
        assert "Mistral Large 4" in names
        assert "Mistral" not in names

    def test_order_is_first_appearance_and_the_list_is_capped(self):
        text = " ".join(f"Then Zorblax{i} Corp shipped it." for i in range(60))
        names = names_to_keep(text)
        assert names[0] == "Zorblax0 Corp"
        assert len(names) == 40

    def test_empty_and_nameless_digests_render_nothing(self):
        assert names_to_keep("") == []
        assert build_names_block("") == ""
        assert build_names_block("nothing capitalised here at all.") == ""

    def test_the_block_is_data_with_no_specimen_sentence(self):
        block = build_names_block(DIGEST)
        assert block.startswith("NAMES TO KEEP")
        assert "never read this list aloud" in block
        # The only names in it are today's; no quoted example line.
        assert '"' not in block and "“" not in block

    def test_real_digests_give_a_usable_list(self):
        mds = sorted(
            p for p in (ROOT / "digests/models_agents").glob("Models_Agents_Ep*_*.md")
            if "_claims" not in p.name
        )[-5:]
        if not mds:
            pytest.skip("no committed M&A digests")
        for md in mds:
            names = names_to_keep(md.read_text(encoding="utf-8"))
            assert len(names) >= 10, (md.name, names)
            assert not any(n in ("You Need", "Know", "What") for n in names), md.name


class TestModelsAgentsDecisions:
    def test_length_option_c_with_the_old_skip_floor_pinned(self):
        cfg = load_config(str(ROOT / "shows/models_agents.yaml"))
        assert cfg.llm.min_podcast_words == 1300
        # 60 % of the old 1,500: the lower target never lowers the floor.
        assert cfg.llm.min_podcast_publish_words == 900

    def test_prompt_states_the_natural_length_and_carries_the_names(self):
        text = PROMPT.read_text(encoding="utf-8")
        assert "at least 1500 words" not in text
        assert "10–12 minute" not in text and "10-12 minute" not in text
        assert "1,200 to 1,400 words" in text
        assert "{names_to_keep_block}" in text
        # The block sits with the briefing, after it.
        assert text.index("{digest}") < text.index("{names_to_keep_block}")

    def test_only_models_agents_opts_in(self):
        assert load_config(str(ROOT / "shows/models_agents.yaml")).names_to_keep is True
        assert load_config(str(ROOT / "shows/tesla.yaml")).names_to_keep is False

    def test_the_script_stage_receives_the_block(self, monkeypatch):
        import engine.generator as G
        import engine.pipeline as P

        logging.disable(logging.CRITICAL)
        try:
            cfg = load_config(str(ROOT / "shows/models_agents.yaml"))
            seen = {}

            def fake(tv, config, tracker=None):
                seen.update(tv)
                return "A script sentence about the news. " * 200

            monkeypatch.setattr(G, "generate_podcast_script", fake)
            monkeypatch.setattr(G, "take_combined_script", lambda: None)
            P.run_generation_phase(
                cfg, episode_num=999, today_str="November 1, 2026",
                hook="A hook", x_thread=DIGEST, template_vars={},
                args=None, tracker=None,
            )
        finally:
            logging.disable(logging.NOTSET)
        assert seen["names_to_keep_block"].startswith("NAMES TO KEEP")
        assert "Mistral Large 4" in seen["names_to_keep_block"]

    def test_a_show_that_has_not_opted_in_renders_an_empty_block(self):
        from engine.pipeline import build_podcast_template_vars

        cfg = load_config(str(ROOT / "shows/tesla.yaml"))
        logging.disable(logging.CRITICAL)
        try:
            tv = build_podcast_template_vars(
                cfg, episode_num=1, today_str="November 1, 2026",
                effective_hook="A hook", template_vars={},
            )
        finally:
            logging.disable(logging.NOTSET)
        assert tv["names_to_keep_block"] == ""
