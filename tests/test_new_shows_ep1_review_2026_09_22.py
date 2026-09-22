"""Guards from the four new shows' Episode 1 runs (Sep 22 2026).

AI Chips and Longevity published; MAG 7 generated a complete episode that
never reached main; Peptides skipped on a thin script. Each guard below pins
one fix, named for the failure it answers.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
NEW_SHOWS = ("ai_chips", "mag7", "peptides", "longevity")
WEEKLY = ("peptides", "longevity")


def _registry_slugs() -> set[str]:
    from generate_html import NETWORK_SHOWS

    return set(NETWORK_SHOWS)


# ---------------------------------------------------------------------------
# MAG 7: the quote cache collided with the per-show public API file
# ---------------------------------------------------------------------------

class TestHookCachesNeverShadowTheShowApi:
    """generate_html writes api/<slug>.json for every registry show. A hook
    cache at the same path sat untracked on the show runner while finalize
    committed the API file, and every rebase of MAG 7 Ep1's commit aborted."""

    _API_PATH_RE = re.compile(r"""["']api["']\s*/\s*["']([\w.-]+)\.json["']|api/([\w.-]+)\.json""")

    def test_no_hook_writes_api_slug_json(self):
        slugs = _registry_slugs()
        offenders = []
        for hook in sorted((ROOT / "shows" / "hooks").glob("*.py")):
            code = "\n".join(line.split("#", 1)[0]
                              for line in hook.read_text(encoding="utf-8").splitlines())
            for m in self._API_PATH_RE.finditer(code):
                name = m.group(1) or m.group(2)
                if name in slugs:
                    offenders.append(f"{hook.name}: api/{name}.json")
        assert not offenders, offenders

    def test_mag7_cache_path_and_commit_whitelist(self):
        from shows.hooks import mag7

        assert mag7.CACHE_PATH.name == "mag7_quotes.json"
        wf = (ROOT / ".github/workflows/run-show.yml").read_text(encoding="utf-8")
        assert "git add api/mag7_quotes.json" in wf


def test_tape_percent_has_no_trailing_zero():
    from engine.market_quotes import Quote, tape_block

    block = tape_block([Quote("TSLA", 378.9, 375.15, "2026-09-22")],
                       {"TSLA": "Tesla"}, ["TSLA"])
    assert "(+1%)" in block and "1.0%" not in block


# ---------------------------------------------------------------------------
# Chapters: the opening belonged to no chapter
# ---------------------------------------------------------------------------

class TestOpeningAlwaysChaptered:
    MARKERS = [
        {"pattern": "This is Example Show", "title": "Introduction", "where": "start"},
        {"pattern": "take (it|this|that) apart", "title": "The Teardown"},
        {"pattern": "that's Example Show", "title": "Closing", "where": "end"},
    ]

    @staticmethod
    def _script(opening: str) -> str:
        body = "\n\n".join(
            f"Story {i} sentence about silicon and power with a number {i}." * 3
            for i in range(12)
        )
        return (
            f"{opening}\n\n{body}\n\nLet's take it apart: the mechanism.\n\n"
            + "Mechanism words here. " * 40
            + "\n\nAnd that's Example Show for today."
        )

    def test_unmatched_start_gets_a_synthetic_opening(self):
        from engine.chapters import parse_chapters

        ch = parse_chapters(self._script("Welcome to the very first episode!"),
                            self.MARKERS, show_name="x")
        assert ch[0].word_start == 0
        assert ch[0].title == "Introduction"
        assert "The Teardown" in [c.title for c in ch]

    def test_matched_start_is_unchanged(self):
        from engine.chapters import parse_chapters

        ch = parse_chapters(self._script("This is Example Show, episode 2."),
                            self.MARKERS, show_name="x")
        assert ch[0].title == "Introduction" and ch[0].word_start == 0
        assert [c.title for c in ch].count("Introduction") == 1

    @pytest.mark.parametrize("slug", ("ai_chips", "longevity"))
    def test_real_ep1_scripts_are_chaptered_from_the_top(self, slug):
        from engine.chapters import parse_chapters
        from engine.config import load_config
        from engine.grok_imagine import extract_story_headlines

        tts = sorted((ROOT / "digests" / slug).glob("*_Ep001_*_tts.txt"))
        digest = [p for p in sorted((ROOT / "digests" / slug).glob("*_Ep001_*.md"))]
        if not tts or not digest:
            pytest.skip("Episode 1 not committed")
        cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
        ch = parse_chapters(
            tts[0].read_text(encoding="utf-8"), cfg.chapters.section_markers,
            show_name=slug,
            story_headlines=extract_story_headlines(
                digest[0].read_text(encoding="utf-8"), max_count=12),
        )
        # The debut line now matches the Introduction marker right after
        # the hook (the network's normal shape); before the fix the first
        # chapter began at word 733 / 656.
        assert ch[0].word_start <= 60
        assert len(ch) >= 5

    @pytest.mark.parametrize("slug", NEW_SHOWS)
    def test_debut_opening_matches_the_intro_marker(self, slug):
        from engine.config import load_config

        cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
        start = [m for m in cfg.chapters.section_markers if m.where == "start"]
        assert start and re.search(start[0].pattern,
                                   "Welcome to the very first episode of the show",
                                   re.IGNORECASE)


# ---------------------------------------------------------------------------
# Absence sentences
# ---------------------------------------------------------------------------

EP1_ABSENCE = [
    "No energization date was stated in the announcement.",
    "No specific customer names or shipment volumes were disclosed.",
    "Construction timing and exact power arrangements were not specified.",
    "No year-by-year breakdown or specific technology nodes were detailed.",
    "Regulatory review status has not been detailed in the report.",
    "Current reporting supplies no release date for the redesign.",
    "Alphabet has not yet released additional information on the timing or scope.",
    "No new capabilities received mention alongside the update.",
    "No energization date appears in the release.",
    "No release date or specific design elements have been confirmed in the current reporting.",
]

# What science has not established is CONTENT on the health shows.
HEALTH_CAVEATS = [
    "No regulatory body has approved intermittent fasting for any aging indication.",
    "No hallmark-targeted therapy has received regulatory approval for an aging indication.",
    "Human outcome data remain limited to the ongoing TAME trial, whose results are not yet available.",
    "Whether this works in people remains unknown.",
    "The finding has not been tested in a randomized human trial.",
    "The mechanism is not established in humans.",
    "Meta confirmed design overlap between its new Muse agent and OpenClaw.",
    "The analysis does not establish causation.",
]


class TestAbsenceSentences:
    @pytest.mark.parametrize("sentence", EP1_ABSENCE)
    def test_ep1_absence_sentences_match(self, sentence):
        from engine.absence_sentences import is_absence_sentence

        assert is_absence_sentence(sentence)

    @pytest.mark.parametrize("sentence", HEALTH_CAVEATS)
    def test_caveats_and_facts_survive(self, sentence):
        from engine.absence_sentences import is_absence_sentence

        assert not is_absence_sentence(sentence)

    def test_strip_keeps_structure(self):
        from engine.absence_sentences import strip_absence_sentences

        digest = (
            "### Silicon\n"
            "**GUC Announces 2nm HBM4E IP: EE Times**\n"
            "GUC announced a 2 nm HBM4E PHY at 16 Gbps. No customer names were "
            "disclosed. Source: [eetimes.com](https://eetimes.com/x)\n"
            "- No year-by-year breakdown was detailed.\n"
            "```claims\n[{\"claim\": \"No price was disclosed.\"}]\n```\n"
        )
        out, n = strip_absence_sentences(digest)
        assert n == 1
        assert "No customer names" not in out
        assert "Source: [eetimes.com](https://eetimes.com/x)" in out
        assert "- No year-by-year breakdown was detailed." in out  # list item
        assert "No price was disclosed." in out                      # fenced
        assert "**GUC Announces 2nm HBM4E IP: EE Times**" in out

    def test_script_line_removed_whole(self):
        from engine.absence_sentences import strip_absence_sentences

        script = ("Google removed the age limit.\n\n"
                  "No further details were provided in the announcement.\n\n"
                  "Apple clarified its camera controls.")
        out, n = strip_absence_sentences(script)
        assert n == 1
        assert out == "Google removed the age limit.\n\nApple clarified its camera controls."

    def test_opt_in_only(self):
        from engine.config import load_config

        assert load_config(ROOT / "shows" / "tesla.yaml").absence_sentence_filter is False
        for slug in NEW_SHOWS:
            assert load_config(ROOT / "shows" / f"{slug}.yaml").absence_sentence_filter

    def test_wired_before_the_gate_and_on_the_script(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        gate = src.index("# --- Source-integrity gate (Aug 2026, engine/claims.py) ---")
        digest_filter = src.index("x_thread, _absent_n = strip_absence_sentences(x_thread)")
        assert digest_filter < gate
        assert "podcast_script, _absent_s = strip_absence_sentences(podcast_script)" in src


# ---------------------------------------------------------------------------
# X accounts + full text
# ---------------------------------------------------------------------------

class TestXSourcing:
    @pytest.mark.parametrize("slug", NEW_SHOWS)
    def test_x_accounts_are_a_source_never_a_post_target(self, slug):
        from engine.config import load_config

        cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
        assert cfg.x_fetch_enabled is True
        assert len(cfg.x_accounts) >= 5
        assert cfg.publishing.x_enabled is False
        handles = [a.handle.lower() for a in cfg.x_accounts]
        assert len(handles) == len(set(handles))
        assert all(not h.startswith("@") for h in handles)

    def test_weeklies_read_their_week(self):
        from engine.config import load_config

        for slug in WEEKLY:
            assert load_config(ROOT / "shows" / f"{slug}.yaml").x_lookback_hours == 192
        assert load_config(ROOT / "shows" / "tesla.yaml").x_lookback_hours == 24

    @pytest.mark.parametrize("hours,expected", [(24, "in the last 24 hours."),
                                                (192, "in the last 192 hours.")])
    def test_x_prompt_window(self, monkeypatch, hours, expected):
        import digests.xai_grok as xg
        from engine.config import XAccountConfig
        from engine.fetcher import fetch_x_posts

        seen = []

        def fake(prompt, **kw):
            seen.append(prompt)
            return "NO_RECENT_POSTS", {}

        monkeypatch.setenv("GROK_API_KEY", "x")
        monkeypatch.setattr(xg, "grok_generate_text", fake)
        fetch_x_posts([XAccountConfig(handle="nvidia")], lookback_hours=hours)
        assert expected in seen[0]
        assert f"- Only posts from the last {hours} hours" in seen[0]

    @pytest.mark.parametrize("slug", NEW_SHOWS)
    def test_full_text_on(self, slug):
        from engine.config import load_config

        assert load_config(ROOT / "shows" / f"{slug}.yaml").fetch_full_text >= 10


# ---------------------------------------------------------------------------
# Prompt rules from the Ep1 transcripts
# ---------------------------------------------------------------------------

def _prompt(name: str) -> str:
    return (ROOT / "shows" / "prompts" / name).read_text(encoding="utf-8")


def test_mag7_thread_never_rereads_the_tape():
    p = _prompt("mag7_digest.txt")
    assert "Never repeat a closing price or a percentage move from The Tape" in p
    assert "from today's articles or the tape" not in p


def test_mag7_counterpoint_is_an_argument_and_ta_is_filtered():
    assert "technical-analysis piece is never the Counterpoint" in _prompt("mag7_digest.txt")
    pats = yaml.safe_load((ROOT / "shows/mag7.yaml").read_text())["exclude_title_patterns"]
    title = "Google (GOOG) Stock Fails at Resistance as Gemini Growth Meets Spending Concerns"
    assert any(re.search(p, title, re.IGNORECASE) for p in pats)


def test_ai_chips_teardown_numbers_come_from_articles():
    p = _prompt("ai_chips_digest.txt")
    assert "comes from an article above" in p
    assert "Carry at least four numbers." not in p


def test_longevity_scope_and_keywords():
    assert "SCOPE: an item belongs here only when it concerns aging itself" in _prompt(
        "longevity_digest.txt")
    kws = yaml.safe_load((ROOT / "shows/longevity.yaml").read_text())["keywords"]
    assert "trial" not in kws


@pytest.mark.parametrize("slug", WEEKLY)
def test_weekly_spotlight_is_the_centre(slug):
    assert "550-700 words" in _prompt(f"{slug}_digest.txt")
    podcast = _prompt(f"{slug}_podcast.txt")
    assert "at least a third of the script" in podcast
    assert "COVERAGE: every item in the briefing is told" in podcast
