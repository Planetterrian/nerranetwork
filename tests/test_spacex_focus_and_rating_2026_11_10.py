"""Nov 10 2026 growth review, item 5: SpaceX Daily's Top News leads on a
SpaceX program, and a two-week Apple rating push in the show notes."""
from __future__ import annotations

import glob
import re
from pathlib import Path

import yaml

from engine import digest_lint as L
from engine.episode_ask import episode_ask_for, episode_ask_markdown

ROOT = Path(__file__).resolve().parents[1]


def _digest(lead_title: str, lead_body: str, extra: str = "") -> str:
    return (
        "# SpaceX Daily\n\n> **Hook.**\n\n### Top News\n\n"
        f"1. **{lead_title}**\n   {lead_body} Source: https://example.com/a\n\n"
        "2. **Starlink adds a country**\n   Starlink service opens. Source: https://example.com/b\n\n"
        f"{extra}### Market Watch\nText.\n"
    )


class TestTopNewsOnBeat:
    def test_registered_and_opted_in_on_spacex_only(self):
        assert "top_news_on_beat" in L.LINTS
        cfg = yaml.safe_load((ROOT / "shows/spacex.yaml").read_text())
        assert "top_news_on_beat" in cfg["digest_lints"]
        for p in (ROOT / "shows").glob("*.yaml"):
            if p.name == "spacex.yaml":
                continue
            assert "top_news_on_beat" not in p.read_text(), p.name

    def test_fires_on_a_non_spacex_lead(self):
        d = _digest("NASA alters its lunar spacesuit design",
                    "The agency changes the suit for Artemis IV.")
        f = L.lint_top_news_on_beat(d)
        assert f.note and f.metrics["top_news_lead_on_beat"] == 0

    def test_quiet_on_a_spacex_lead_and_on_a_crew_flight(self):
        for title, body in (("Falcon 9 targets Monday liftoff", "B1103 flies again."),
                            ("NASA names four astronauts for Crew-14", "They fly in 2027.")):
            f = L.lint_top_news_on_beat(_digest(title, body))
            assert f.note == "" and f.metrics["top_news_lead_on_beat"] == 1

    def test_ai_items_are_counted_never_fired(self):
        extra = ("3. **Cursor integrates a new model**\n   Benchmarks rise. "
                 "Source: https://example.com/c\n\n")
        f = L.lint_top_news_on_beat(_digest("Starship stacks", "Booster rolls out.", extra))
        assert f.note == ""
        assert f.metrics["top_news_ai_thread_items"] == 1

    def test_note_carries_no_quotable_specimen(self):
        f = L.lint_top_news_on_beat(_digest("NASA picks a rover", "It flies on Blue Moon."))
        assert "“" not in f.note and '"' not in f.note

    def test_replay_fires_only_on_the_nasa_leads(self):
        fs = sorted(glob.glob(str(ROOT / "digests/spacex/SpaceX_Daily_Ep*.md")),
                    key=lambda f: int(re.search(r"Ep(\d+)", f).group(1)))
        fired = set()
        for f in fs:
            n = int(re.search(r"Ep(\d+)", f).group(1))
            if not 98 <= n <= 157:
                continue
            r = L.lint_top_news_on_beat(Path(f).read_text(encoding="utf-8"))
            if r and r.note:
                fired.add(n)
        assert fired == {155, 156}


class TestSpacexRatingPush:
    def test_window_only(self):
        assert "rate_url" not in (episode_ask_for("spacex", 157) or {})
        assert "rate_url" not in (episode_ask_for("spacex", 172) or {})
        for ep in (158, 171):
            ask = episode_ask_for("spacex", ep)
            assert ask["rate_url"].startswith("https://podcasts.apple.com/")
            assert ask["paragraphs"][0].startswith("Apple Podcasts")

    def test_outside_the_window_is_byte_identical(self):
        before = episode_ask_markdown("spacex", 157)
        assert before == episode_ask_markdown("spacex", 172)
        assert "](" not in before

    def test_markdown_links_the_show_page(self):
        md = episode_ask_markdown("spacex", 160)
        assert "[Rate SpaceX Daily on Apple Podcasts](https://podcasts.apple.com/podcast/id1896920957)" in md

    def test_apple_id_matches_the_show_yaml(self):
        cfg = yaml.safe_load((ROOT / "shows/spacex.yaml").read_text())
        assert str(cfg["apple_show_id"]) in episode_ask_for("spacex", 160)["rate_url"]

    def test_push_states_no_rating_count(self):
        para = episode_ask_for("spacex", 160)["paragraphs"][0]
        assert not re.search(r"\d", para)

    def test_other_shows_untouched(self):
        assert "rate_url" not in (episode_ask_for("tesla", 700) or {})
