"""Guards for Phase 3 (Omni View regional desks) and the Mira Ep1 review
fixes of 2026-09-23. Plan: docs/new_shows_plan_2026_09_22.md §4.7-4.8."""

from pathlib import Path

import pytest

from engine.config import load_config
from engine.pipeline import build_podcast_template_vars


class TestMiraDebutKeepsIdentity:
    """Vancouver and Collingwood Ep1 never said Mira's name until the
    closing: the generic debut line replaced the identity line."""

    def _intro(self, slug, ep):
        cfg = load_config(f"shows/{slug}.yaml")
        from types import SimpleNamespace
        v = build_podcast_template_vars(cfg, episode_num=ep, today_str="September 23, 2026",
                                        effective_hook="A hook.", args=SimpleNamespace(show=slug))
        return v["intro_line"]

    @pytest.mark.parametrize("slug", ["vancouver", "collingwood"])
    def test_ai_host_debut_names_mira_and_the_ai(self, slug):
        line = self._intro(slug, 1)
        assert "very first episode" in line
        # Sep 23 2026: the tail also says Mira does not live there.
        assert "I'm Mira, the Nerra Network's AI host" in line
        assert "don't live in" in line

    def test_human_host_debut_unchanged(self):
        line = self._intro("prediction_markets", 1)
        assert line == ("Welcome to the very first episode of Prediction Markets Daily! "
                        "Today is September 23, 2026.")

    def test_ai_host_later_episode_unchanged_shape(self):
        assert "I'm Mira" in self._intro("vancouver", 2)


# ---------------------------------------------------------------------------
# Phase 3: the Omni View regional desks + Top World (plan §4.7-4.8)
# ---------------------------------------------------------------------------

import datetime as _dt  # noqa: E402
import re  # noqa: E402

import yaml  # noqa: E402

from engine.omni_desks import (  # noqa: E402
    ALL_OMNI_MIRA_SLUGS, ANTI_TABLOID_PATTERNS, DESKS, WORLD_SLUG,
    balance_note, desk, desk_items, sub_regions_in, under_covered,
)

ROOT = Path(__file__).resolve().parents[1]


class TestOneDefinition:
    def test_six_shows(self):
        assert len(DESKS) == 5 and len(ALL_OMNI_MIRA_SLUGS) == 6
        assert WORLD_SLUG == "omni_view_world"

    def test_every_registry_has_every_show(self):
        from engine import content_tracker, first_episode, intros, validation
        for slug in ALL_OMNI_MIRA_SLUGS:
            assert slug in intros._SHOW_PERSONALITIES, slug
            assert slug in validation.SHOW_VALIDATION_CONFIGS, slug
            assert slug in content_tracker.SHOW_SECTION_PATTERNS, slug
            assert slug in first_episode._SHOW_DIGEST_EP1, slug
            assert slug in first_episode._SHOW_PODCAST_EP1, slug

    def test_memory_on_desks_off_on_top_world(self):
        from engine.show_memory import SHOW_MEMORY_CONFIGS
        for d in DESKS:
            cfg = SHOW_MEMORY_CONFIGS[d.slug]
            assert 3 <= len(cfg.default_programs) <= 4
        assert WORLD_SLUG not in SHOW_MEMORY_CONFIGS
        assert load_config("shows/omni_view_world.yaml").memory_enabled is False

    def test_identity_line_discloses_the_ai_every_episode(self):
        from engine.intros import build_intro_line
        for slug in ALL_OMNI_MIRA_SLUGS:
            line = build_intro_line(slug, episode_num=7, today_str="x")
            assert line.startswith("Mira: This is Omni View")
            assert "I'm Mira, the Nerra Network's AI host." in line
            assert "&" not in line   # spoken form


@pytest.mark.parametrize("slug", ALL_OMNI_MIRA_SLUGS)
class TestDeskConfig:
    def test_shape(self, slug):
        c = load_config(f"shows/{slug}.yaml")
        assert c.publishing.host_kind == "ai" and c.publishing.host_name == "Mira"
        assert c.tts.voice_id == "ara" and c.tts.speech_wrap_open == ""
        assert c.llm.model == "grok-4.7" and c.llm.reasoning_effort == "low"
        assert c.absence_sentence_filter and c.fetch_full_text >= 12
        assert c.stale_article_days == 3 and c.min_articles_skip == 4
        assert not c.youtube.enabled and not c.newsletter.enabled
        assert c.publishing.rss_link == f"https://nerranetwork.com/{slug.replace('_', '-')}.html"

    def test_no_keyword_filter(self, slug):
        # Regional feeds are on-region by construction; a title keyword
        # filter would drop stories whose titles name no country.
        assert not load_config(f"shows/{slug}.yaml").keywords

    def test_anti_tabloid_filters_come_from_the_module(self, slug):
        c = load_config(f"shows/{slug}.yaml")
        assert tuple(c.exclude_title_patterns) == ANTI_TABLOID_PATTERNS
        ov = yaml.safe_load((ROOT / "shows/omni_view.yaml").read_text())["exclude_title_patterns"]
        for p in ov:
            assert p.replace("(?i)", "") in ANTI_TABLOID_PATTERNS

    def test_segment_anchors_never_in_the_opening(self, slug):
        c = load_config(f"shows/{slug}.yaml")
        for m in c.chapters.section_markers:
            if m.title not in ("Introduction", "Closing"):
                assert m.where == "body", (slug, m.title)

    def test_prompts_render_and_carry_the_anchor_phrases(self, slug):
        from collections import defaultdict
        from engine.generator import load_prompt

        class _D(defaultdict):
            def __missing__(self, k):
                return "{" + k + "}"
        dig = load_prompt(f"shows/prompts/{slug}_digest.txt", _D(str))
        pod = load_prompt(f"shows/prompts/{slug}_podcast.txt", _D(str))
        assert "<<include" not in dig and "<<include" not in pod
        name = load_config(f"shows/{slug}.yaml").name
        assert f"# {name}" in dig
        for phrase in ("the case on both sides", "a sign of progress"):
            assert phrase in pod
        if slug != WORLD_SLUG:
            assert "REGION RULE" in dig and "REGION RULE" in pod
            assert "across the region" in pod and "the wider world" in pod

    def test_pages_covers_and_launched(self, slug):
        page = slug.replace("_", "-")
        assert (ROOT / f"{page}.html").exists()
        assert (ROOT / f"assets/covers/{page}.jpg").exists()
        # Launch-cohort PR C (2026-09-23): out of the pre-launch set, on the clock.
        import review_episodes
        assert slug not in review_episodes.PRELAUNCH_SLUGS
        assert review_episodes.SHOW_REGISTRY[slug]["schedule"] == "daily"
        wf = (ROOT / ".github/workflows/run-show.yml").read_text()
        assert f"          - {slug}\n" in wf
        cron_block = wf.split("CRON_MAP", 1)[1][:6000] if "CRON_MAP" in wf else ""
        assert f'"{slug}"' in cron_block
        nightly = (ROOT / ".github/workflows/nightly-maintenance.yml").read_text()
        assert f"blog/{slug}/**" in nightly and f"{page}.html" in nightly
        meta = yaml.safe_load((ROOT / "shows/network_meta.yaml").read_text())[slug]
        assert meta["strand"] == "world" and meta["host"] == "mira"
        assert meta["picker_tags"]["topics"] == ["world-news"]


class TestSubRegionBalance:
    def test_word_start_match(self):
        eu = desk("omni_view_europe")
        assert sub_regions_in("Talks in Kyiv; Polish farmers protest", eu) == [
            "central and eastern Europe", "Ukraine, Russia and Belarus"]
        # "uk " needs a word boundary on both sides
        assert "the UK and Ireland" not in sub_regions_in("Ukulele festival", eu)

    def test_under_covered_and_note(self):
        eu = desk("omni_view_europe")
        recent = ["Starmer in London", "Brussels summit", "Paris strike", "Rome vote",
                  "Sweden budget", "Poland election", "Serbia protest", "Kyiv talks", "Ankara"]
        assert under_covered(recent, eu) == []
        assert balance_note(recent, eu) == ""
        assert balance_note([], eu) == ""
        note = balance_note(["Kyiv talks"], eu)
        assert "never invent" in note.lower() and "the Balkans" in note

    def test_hook_reads_the_last_ten(self, tmp_path):
        from types import SimpleNamespace
        from shows.hooks import _omni_desk
        for i in range(12):
            (tmp_path / f"Omni_View_Europe_Ep{i:03d}_202609{i + 1:02d}.md").write_text(f"digest {i}")
        cfg = SimpleNamespace(episode=SimpleNamespace(output_dir=str(tmp_path), prefix="Omni_View_Europe"))
        texts = _omni_desk.recent_digests(cfg)
        assert len(texts) == 10 and texts[-1] == "digest 11"


DESK_DIGEST = """# Omni View Europe
**Date:** September 23, 2026

> **Germany's coalition agrees a budget.**

### Lead
**Germany's coalition agrees a 2027 budget:** DW. The coalition agreed on Tuesday. Source: [dw.com](https://www.dw.com/en/budget/a-1)

### Across the Region
**Poland extends border checks:** Notes from Poland
> **Checks run to March.** Source: [notesfrompoland.com](https://notesfrompoland.com/2026/09/23/checks/)

**An item with no source line:** Euronews. It says something.

### The Region and the World
**EU and India close a trade chapter:** Politico Europe. Talks ended. Source: [politico.eu](https://www.politico.eu/article/eu-india/)

### Both Sides: Border checks
**Supporters:** a paragraph. Source: [x.com](https://x.com/a/1)

### Progress Watch
**Rail line reopens:** BBC. Source: [bbc.co.uk](https://www.bbc.co.uk/news/1)
"""


class TestTopWorldReadsTheDesks:
    def test_desk_items_are_the_news_sections_with_publisher_urls(self):
        items = desk_items(DESK_DIGEST)
        assert [i["section"] for i in items] == ["Lead", "Across the Region", "The Region and the World"]
        assert items[0]["url"] == "https://www.dw.com/en/budget/a-1"
        assert items[0]["outlet"] == "DW"
        assert items[1]["url"].startswith("https://notesfrompoland.com/")
        assert all("Source:" not in i["summary"] for i in items)

    def _root(self, tmp_path, *, skip=False):
        d = tmp_path / "digests" / "omni_view_europe"
        d.mkdir(parents=True)
        (d / "Omni_View_Europe_Ep004_20260923.md").write_text(DESK_DIGEST)
        if skip:
            (d / ".skip_20260923.json").write_text("{}")
        return tmp_path

    def test_hook_articles_carry_no_desk_prose(self, tmp_path):
        from shows.hooks import omni_view_world as h
        out = h.build_payload(self._root(tmp_path), _dt.date(2026, 9, 23))
        arts = out["articles"]
        assert len(arts) == h.ARTICLES_PER_DESK
        for a in arts:
            assert set(a) == {"title", "url", "source_name", "published_date"}
            assert "nerranetwork" not in a["url"]
        assert "Every fact you write comes from the numbered articles" in out["hook_context"]

    def test_skip_marker_and_other_dates_are_absent(self, tmp_path):
        from shows.hooks import omni_view_world as h
        assert h.build_payload(self._root(tmp_path, skip=True), _dt.date(2026, 9, 23))["articles"] == []
        root = self._root(tmp_path / "b")
        # Sep 23 2026: an empty day still carries the intake line + edition
        # note (data-side honesty about how many desks were live), never
        # desk items.
        payload = h.build_payload(root, _dt.date(2026, 9, 24))
        assert payload["articles"] == []
        assert payload["metrics"]["desks_live_at_publish"] == 0
        assert "No regional desk had published" in payload["hook_context"]
        assert "Europe:" not in payload["hook_context"]

    def test_hook_articles_stay_under_the_prompt_cap(self):
        from shows.hooks import omni_view_world as h
        assert h.ARTICLES_PER_DESK * len(DESKS) <= 12

    def test_textless_hook_articles_are_fetched_first(self):
        from engine.article_text import enrich_articles_with_full_text
        seen = []

        def fetch(url):
            seen.append(url)
            return 200, "<html><body><p>" + "Publisher text. " * 40 + "</p></body></html>"
        arts = [{"title": f"Feed {i}", "url": f"https://feed/{i}", "source_name": "Feed"} for i in range(5)]
        arts.append({"title": "Desk lead", "url": "https://publisher/lead", "source_name": "DW",
                     "source_kind": "hook"})
        enrich_articles_with_full_text(arts, max_articles=1, fetch=fetch, workers=1)
        assert seen == ["https://publisher/lead"]


class TestLedgerHasRoom:
    """Prediction Markets Ep1 used 5,384 of a 5,500-token digest budget on
    grok-4.7 (reasoning shares it) and its claims ledger never arrived."""

    NEW_47 = ("ai_chips", "mag7", "peptides", "longevity", "vancouver", "collingwood",
              "prediction_markets") + ALL_OMNI_MIRA_SLUGS

    @pytest.mark.parametrize("slug", NEW_47)
    def test_digest_budget(self, slug):
        c = load_config(f"shows/{slug}.yaml")
        if c.llm.model.startswith("grok-4.7"):
            assert c.llm.max_tokens >= 8000


class TestNoHeadlinePadding:
    """PM Ep1 padded headline-only items ("The report is about the end of
    that partnership") because the prompt demanded two sentences minimum."""

    @pytest.mark.parametrize("path", [
        "shows/prompts/prediction_markets_digest.txt",
        "shows/prompts/_shared/omni_desk_digest_body.txt",
        "shows/prompts/omni_view_world_digest.txt",
    ])
    def test_one_fact_one_sentence(self, path):
        text = (ROOT / path).read_text()
        assert "restates the headline" in text
        assert not re.search(r"\b(two|Two) to (five|six)\b", text)


class TestBoardVolumesForTheEar:
    """PM Ep1 read "eight hundred ten thousand seven hundred fifty-three
    dollars" aloud; a minute-by-minute figure is rounded."""

    def test_rounding(self):
        from engine.prediction_board import _amount, _money
        assert _money(810_753) == "$811,000"
        assert _amount(1_624_335) == "1.6 million"
        assert _amount(2_000_000) == "2 million"
        assert _amount(950) == "950"
