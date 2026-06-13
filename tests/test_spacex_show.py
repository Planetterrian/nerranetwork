"""Launch drift guards for SpaceX Daily (June 2026).

The show was scaffolded with every June 2026 lesson baked in at launch;
these pins keep them from regressing:

* chapter markers carry positional ``where`` anchors (Introduction=start,
  Closing=end) — the Tesla/FP chapter-bug class where the closing's brand
  mention re-opened an "Introduction" chapter on the sign-off.
* every closing-pool variant in engine/intros.py is matched by the YAML
  Closing chapter pattern, so no episode ships without a Closing chapter
  (the MAB orphan-closing class).
* ONE unified length target: min_podcast_words floor sits just under the
  prompt's stated 1,900-2,200w target, with the digest-carrying expansion
  retry opted in.
* show memory is registered + enabled so the narrative tracker runs from
  episode 1.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.chapters import parse_chapters  # noqa: E402
from engine.config import load_config  # noqa: E402
from engine.intros import _SHOW_PERSONALITIES, build_closing_block  # noqa: E402
from engine.show_memory import SHOW_MEMORY_CONFIGS  # noqa: E402


def _spacex_markers():
    cfg = yaml.safe_load((_ROOT / "shows/spacex.yaml").read_text(encoding="utf-8"))
    return cfg["chapters"]["section_markers"]


def _closing_pattern():
    return next(m["pattern"] for m in _spacex_markers() if m["title"] == "Closing")


class TestConfigLoads:
    def test_full_config_loads(self):
        cfg = load_config(_ROOT / "shows/spacex.yaml")
        assert cfg.name == "SpaceX Daily"
        assert cfg.slug == "spacex"

    def test_one_length_target_with_expand_retry(self):
        cfg = load_config(_ROOT / "shows/spacex.yaml")
        assert cfg.llm.min_podcast_words == 1700
        assert cfg.llm.podcast_expand_below_target is True

    def test_memory_enabled_and_registered(self):
        cfg = load_config(_ROOT / "shows/spacex.yaml")
        assert cfg.memory_enabled is True
        assert "spacex" in SHOW_MEMORY_CONFIGS
        mem = SHOW_MEMORY_CONFIGS["spacex"]
        assert "starship" in mem.default_programs
        assert "starlink" in mem.default_programs


class TestChapterPositionalAnchors:
    def test_introduction_anchored_to_start(self):
        by_title = {m["title"]: m for m in _spacex_markers()}
        assert by_title["Introduction"].get("where") == "start"

    def test_closing_anchored_to_end(self):
        by_title = {m["title"]: m for m in _spacex_markers()}
        assert by_title["Closing"].get("where") == "end"

    def test_teaser_anchored_to_end(self):
        by_title = {m["title"]: m for m in _spacex_markers()}
        assert by_title["Tomorrow Teaser"].get("where") == "end"


class TestClosingPoolMatchesChapterPattern:
    def test_every_closing_variant_matched(self):
        regex = re.compile(_closing_pattern(), re.IGNORECASE)
        for variant in _SHOW_PERSONALITIES["spacex"]["closings"]:
            assert regex.search(variant), (
                "SpaceX closing-pool variant not matched by the Closing chapter "
                f"pattern — episodes using it ship without a Closing chapter: "
                f"{variant[:80]!r}"
            )

    def test_resolved_closing_block_matched(self):
        regex = re.compile(_closing_pattern(), re.IGNORECASE)
        block = build_closing_block(
            "spacex", episode_num=1, today_str="June 12, 2026",
        )
        assert regex.search(block), block[:120]


class TestRealScriptParsesCleanly:
    """The closing variants mention 'SpaceX' heavily; without the positional
    anchors the Introduction pattern ('SpaceX Daily|welcome to SpaceX') could
    re-open an Introduction chapter on the sign-off."""

    def _build_script(self, closing_idx: int):
        intro = "Hey, welcome to SpaceX Daily, episode one. I'm Patrick in Vancouver."
        body_lines = [
            "Here's what's happening at SpaceX today.",
            "Starship's next flight test is stacking at Starbase this week.",
        ]
        for i in range(36):
            body_lines.append(
                f"This is body sentence number {i} carrying launch detail and "
                f"named hardware forward."
            )
        body_lines.append("From an engineering standpoint, the math favors reuse.")
        body_lines.append("Before we go, tomorrow we watch the static fire window.")
        closing = _SHOW_PERSONALITIES["spacex"]["closings"][closing_idx]
        return "\n".join([intro, "", *body_lines, "", closing])

    def test_single_introduction_first_and_closing_last(self):
        for idx in range(len(_SHOW_PERSONALITIES["spacex"]["closings"])):
            chapters = parse_chapters(
                self._build_script(idx), _spacex_markers(), show_name="SpaceX Daily",
            )
            titles = [c.title for c in chapters]
            assert titles, "no chapters parsed"
            assert titles[0] == "Introduction", titles
            assert titles.count("Introduction") == 1, (
                f"closing brand mention re-opened Introduction: {titles}"
            )
            assert titles[-1] == "Closing", (idx, titles)


class TestPromptContracts:
    def test_prompts_carry_memory_placeholder(self):
        for fname in ("spacex_digest.txt", "spacex_podcast.txt"):
            text = (_ROOT / "shows/prompts" / fname).read_text(encoding="utf-8")
            assert "{narrative_memory_section}" in text, fname

    def test_podcast_prompt_states_one_length_target(self):
        text = (_ROOT / "shows/prompts/spacex_podcast.txt").read_text(encoding="utf-8")
        assert text.count("1,900") == 1, (
            "ONE unified length target: the prompt must state the word target "
            "exactly once"
        )

    def test_system_prompt_length_agrees_with_podcast_prompt(self):
        # The scaffolded system prompt said 10-12 min while the podcast
        # prompt demanded 12-14 — the contradictory-length class every
        # June 2026 review fixed. Both must state the same window.
        system = (_ROOT / "shows/prompts/spacex_system.txt").read_text(encoding="utf-8")
        assert "12–14 minutes" in system
        assert "10-12" not in system and "10–12" not in system


class TestIpoPositioning:
    """June 13 2026 repositioning: the show launched on SpaceX's IPO day
    (Nasdaq: SPCX, June 12 2026) and is the daily companion for following
    the now-public company."""

    def test_prompts_carry_hook_placeholders(self):
        digest = (_ROOT / "shows/prompts/spacex_digest.txt").read_text(encoding="utf-8")
        podcast = (_ROOT / "shows/prompts/spacex_podcast.txt").read_text(encoding="utf-8")
        assert "{spcx_market_block}" in digest
        assert "{ipo_debut_section}" in digest
        assert "{ipo_debut_section}" in podcast

    def test_debut_section_fires_on_episode_one_only(self):
        from shows.hooks.spacex import _ipo_debut_section
        ep1 = _ipo_debut_section(1)
        assert "IPO" in ep1 and "subscribe" in ep1.lower()
        assert _ipo_debut_section(2) == ""
        assert _ipo_debut_section(None) == ""

    def test_market_block_empty_on_invalid_quote(self):
        # Failed/invalid quote must render an EMPTY block — the prompts
        # then omit the price line entirely (never "price unavailable",
        # the Tesla Ep4xx failure mode).
        from shows.hooks.spacex import _build_market_block
        assert _build_market_block(0.0, "") == ""
        block = _build_market_block(161.0, "+19.3%")
        assert "$161.00" in block and "verbatim" in block

    def test_quote_validation_band_and_deviation_guard(self):
        from shows.hooks import spacex as hook
        assert not hook._validate(5.0)       # below band
        assert not hook._validate(5000.0)    # above band
        assert hook._validate(161.0)         # day-one close passes

    def test_market_watch_chapter_marker(self):
        by_title = {m["title"]: m for m in _spacex_markers()}
        assert "Market Watch" in by_title

    def test_public_markets_program_seeded(self):
        prog = SHOW_MEMORY_CONFIGS["spacex"].default_programs["public_markets"]
        assert "SPCX" in prog["status"]
        assert any("earnings" in q.lower() for q in prog["key_open_questions"])

    def test_descriptions_state_public_company(self):
        cfg = yaml.safe_load((_ROOT / "shows/spacex.yaml").read_text(encoding="utf-8"))
        assert "SPCX" in cfg["description"]
        assert "SPCX" in cfg["publishing"]["rss_description"]


class TestStockClosing:
    """TST-parity spoken closing: date-rotated variants carrying the SPCX
    price, with the price sentence OMITTED when the quote failed
    validation — never 'price unavailable' (Tesla Ep4xx failure mode)."""

    def test_every_hook_closing_variant_matches_closing_pattern(self):
        from shows.hooks.spacex import _CLOSING_VARIANTS
        regex = re.compile(_closing_pattern(), re.IGNORECASE)
        for variant in _CLOSING_VARIANTS:
            rendered = variant.format(price_sentence="")
            assert regex.search(rendered), rendered[:90]

    def test_price_sentence_omitted_on_invalid_quote(self):
        from shows.hooks.spacex import _pick_closing
        import datetime
        closing = _pick_closing(0.0, "", "", date=datetime.date(2026, 6, 13))
        assert "S P C X" not in closing
        assert "unavailable" not in closing.lower()

    def test_price_sentence_phrasing_by_source(self):
        from shows.hooks.spacex import _price_sentence
        closed = _price_sentence(161.0, "+19.2%", "yfinance_history")
        assert closed.startswith("S P C X closed at")
        assert "percent" in closed
        live = _price_sentence(161.0, "+19.2%", "yfinance_fast_info")
        assert "is trading at" in live and "closed" not in live

    def test_closing_rotates_by_date(self):
        from shows.hooks.spacex import _pick_closing
        import datetime
        days = [datetime.date(2026, 6, 13) + datetime.timedelta(days=i) for i in range(4)]
        closings = {_pick_closing(161.0, "+1.0%", "yfinance_history", date=d) for d in days}
        assert len(closings) == 4, "closing must rotate daily, not fossilize"

    def test_tone_hint_mapping(self):
        from shows.hooks.spacex import _tone_from_change
        assert "upbeat" in _tone_from_change(161.0, "+19.2%")
        assert "thoughtful" in _tone_from_change(150.0, "-3.1%")
        assert "natural" in _tone_from_change(0.0, "")

    def test_spcx_ticker_letter_spelled_for_tts(self):
        pron = yaml.safe_load(
            (_ROOT / "shows/pronunciation_map.yaml").read_text(encoding="utf-8")
        )
        assert pron["corrections"].get("SPCX") == "S P C X"


class TestEp001RegressionChapters:
    """Ep001 lesson: chapters parse the POST-pronunciation script, where
    assets/pronunciation.py renders 'SpaceX' as 'Space X' — Ep001 shipped
    with NO Introduction chapter because the pattern only knew the written
    form. The patterns must match the real shipped script."""

    def test_real_ep001_script_parses_with_intro_and_closing(self):
        script_path = (
            _ROOT / "digests/spacex/SpaceX_Daily_Ep001_20260613_tts.txt"
        )
        if not script_path.exists():
            import pytest
            pytest.skip("Ep001 artifact not present")
        chapters = parse_chapters(
            script_path.read_text(encoding="utf-8"),
            _spacex_markers(),
            show_name="SpaceX Daily",
        )
        titles = [c.title for c in chapters]
        assert titles[0] == "Introduction", titles
        assert titles[-1] == "Closing", titles
        assert "Market Watch" in titles

    def test_podcast_prompt_requires_chapter_entry_phrases(self):
        # Ep001 spoke the Counterpoint and Engineering Angle content but
        # never used the entry phrases, so those chapters were lost. The
        # prompt now REQUIRES them.
        text = (_ROOT / "shows/prompts/spacex_podcast.txt").read_text(encoding="utf-8")
        assert 'REQUIRED: open the segment with the words "One thing worth watching"' in text
        assert '"from an engineering standpoint" or "the engineering angle"' in text
