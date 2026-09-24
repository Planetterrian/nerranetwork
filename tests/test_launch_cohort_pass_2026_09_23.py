"""Guards for the launch-cohort quality pass, PR A (2026-09-23).

Thirteen new shows shipped Episode 1 and the per-show review found rules the
prompts state and the model breaks. This network enforces those in code:
digest lints that ride the one-shot structural regeneration, an X-source
policy that credits a newsroom's post to the article it links, a claims
coverage floor for the grok-4.3 arm's empty ledgers, a region allow-list on
the local shows, and the parser fix that gave Top World its five-desk
intake. The replay tests below run the lints over the COMMITTED Episode 1
digests and must flag exactly the defects the review named.
"""

from __future__ import annotations

import glob
from pathlib import Path

import pytest
import yaml

from engine import digest_lint as dl

ROOT = Path(__file__).resolve().parent.parent

NEW13 = [
    "ai_chips", "mag7", "peptides", "longevity", "vancouver", "collingwood",
    "prediction_markets", "omni_view_europe", "omni_view_asia_pacific",
    "omni_view_africa_mideast", "omni_view_latam", "omni_view_north_america",
    "omni_view_world",
]
DESKS = [s for s in NEW13 if s.startswith("omni_view_") and s != "omni_view_world"]


def _ep1(slug: str) -> str:
    hits = sorted(glob.glob(str(ROOT / "digests" / slug / "*Ep001_2026092*.md")))
    if not hits:
        pytest.skip(f"no committed Ep1 for {slug}")
    return Path(hits[-1]).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Lint replays against the committed Episode 1s
# ---------------------------------------------------------------------------

class TestLintReplays:
    def test_mag7_wyntk_opened_on_a_different_story(self):
        # The brief's first fix: H1 = Epic/SCOTUS, WYNTK sentence 1 = iOS betas.
        assert dl.wyntk_hook_match(_ep1("mag7")) < dl.WYNTK_HOOK_MIN_MATCH

    @pytest.mark.parametrize("slug", ["omni_view_asia_pacific", "omni_view_africa_mideast",
                                      "omni_view_north_america", "collingwood"])
    def test_a_matching_wyntk_passes(self, slug):
        assert dl.wyntk_hook_match(_ep1(slug)) >= dl.WYNTK_HOOK_MIN_MATCH

    # Africa & Middle East Ep1's Lead exactly as it was published (the
    # committed digest was re-sourced to the BBC article on 2026-09-23 by
    # scripts/resource_x_citations.py, so the replay keeps the original).
    AFRICA_EP1_LEAD_AS_PUBLISHED = (
        "# Omni View Africa & Middle East\n"
        "> **At least 11 people were killed in a mass shooting near Durban.**\n\n"
        "### Lead\n"
        "**11 killed in mass shooting near Durban, South Africa: BBC News Africa**\n"
        "Gunmen stormed a house in the KwaMakhutha township, near the South African "
        "city of Durban, late on Tuesday and opened fire on 14 people. At least 11 "
        "people were killed in that residential building. "
        "Source: [x.com](https://x.com/BBCAfrica/status/2102729744491950571)\n\n"
        "### Across the Region\n"
    )

    def test_africa_mideast_lead_was_sourced_only_to_x(self):
        assert dl.x_only_lead_items(self.AFRICA_EP1_LEAD_AS_PUBLISHED)
        # ...and the committed record no longer is.
        assert dl.x_only_lead_items(_ep1("omni_view_africa_mideast")) == []

    @pytest.mark.parametrize("slug", ["omni_view_north_america", "omni_view_latam", "mag7"])
    def test_a_newsroom_sourced_lead_passes(self, slug):
        assert dl.x_only_lead_items(_ep1(slug)) == []

    def test_latam_progress_watch_was_a_fragment(self):
        f = dl.lint_progress_watch_thin(_ep1("omni_view_latam"))
        assert f is not None and f.note

    def test_an_explicit_none_progress_watch_passes(self):
        # Asia Pacific and North America wrote the one honest sentence.
        for slug in ("omni_view_asia_pacific", "omni_view_north_america"):
            f = dl.lint_progress_watch_thin(_ep1(slug))
            assert f is not None and f.note == "", slug

    def test_hook_is_read_in_both_forms(self):
        raw = "**HOOK:** Italy's Senate approved a plan to restart nuclear power.\n\n**What You Need to Know:** Italy's Senate approved the nuclear restart plan. More.\n"
        rendered = "# Show\n> **Italy's Senate approved a plan to restart nuclear power.**\n\n**What You Need to Know:** Italy's Senate approved the nuclear restart plan. More.\n"
        assert dl.wyntk_hook_match(raw) == dl.wyntk_hook_match(rendered) >= 0.5

    def test_counterpoint_ignores_url_tokens(self):
        d = ("### Top News\n**Apple loses Epic appeal: Reuters**\nApple's App Store commission "
             "ruling stands. Source: [reuters.com](https://www.reuters.com/a)\n\n"
             "### The Counterpoint\n**GPU futures stall at the CFTC: The Information**\nThe commission "
             "delayed the contracts. Source: [theinformation.com](https://www.theinformation.com/b)\n")
        f = dl.lint_counterpoint_keyed_to_lead(d)
        assert f is not None and f.note, "URL and Source tokens must not count as shared"

    def test_evidence_rung_is_judged_per_item_not_per_sentence(self):
        d = ("### The Week in Peptides\n**Semaglutide misses in Alzheimer's: STAT**\nA pair of "
             "randomized trials of 3,800 participants found no slowing. Neither trial showed slowing "
             "of disease progression. Source: [statnews.com](https://www.statnews.com/x)\n")
        assert dl.evidence_rung_missing(d) == []
        d2 = ("### The Week in Peptides\n**A study found benefits: X**\nA study found the peptide "
              "helped. The findings suggest promise. Source: [x.com](https://x.com/a/status/1)\n")
        assert len(dl.evidence_rung_missing(d2)) == 1

    def test_dose_terms_never_match_consumer_protection_vials(self):
        assert dl.dose_terms("Regulators seized counterfeit vials at the border.") == []
        assert dl.dose_terms("Participants received 2.4 mg weekly.") == ["2.4 mg"]

    def test_runner_records_metrics_for_every_lint_and_notes_only_for_fired(self):
        fired, metrics = dl.run_digest_lints(_ep1("mag7"), ["wyntk_hook_match", "x_only_lead", "nope"])
        assert "wyntk_hook_match" in metrics and "sources_x_only_lead_items" in metrics
        assert [f.lint for f in fired] == ["wyntk_hook_match"]
        assert all(f.note for f in fired)

    def test_no_lint_note_quotes_a_specimen_sentence(self):
        src = (ROOT / "engine" / "digest_lint.py").read_text(encoding="utf-8")
        # Notes describe a shape; none carries a quoted example line.
        for line in src.splitlines():
            if "note" in line and '"' in line and ("e.g." in line or "for example" in line):
                pytest.fail(line)


# ---------------------------------------------------------------------------
# Top World intake: the desk-item parser
# ---------------------------------------------------------------------------

class TestTopWorldIntake:
    def test_desk_items_parse_the_desks_own_item_shape(self):
        from engine.omni_desks import desk_items
        d = ("### Lead\n**Trump settles for a Greenland security deal: The New York Times**\n"
             "The deal expands the U.S. footprint. Source: [nytimes.com](https://www.nytimes.com/a)\n\n"
             "### Across the Region\n**Missouri map back at the Supreme Court: Reuters**\nChallengers "
             "returned on Tuesday. Source: [reuters.com](https://www.reuters.com/b)\n")
        its = desk_items(d)
        assert [(i["section"], i["outlet"]) for i in its] == [
            ("Lead", "The New York Times"), ("Across the Region", "Reuters")]
        assert its[0]["url"].startswith("https://www.nytimes.com")

    def test_every_desk_ep1_with_a_publisher_source_yields_items(self):
        # Africa & Middle East Ep1 sourced every item to x.com, so it
        # correctly yields nothing: Top World never inherits an X source.
        from engine.omni_desks import desk_items
        for slug in DESKS:
            text = _ep1(slug)
            if "Source: [x.com]" in text and "Source: [" not in text.replace("Source: [x.com]", ""):
                assert desk_items(text) == [], slug
            else:
                assert desk_items(text), slug

    def test_top_world_hook_supplies_articles_from_the_committed_desks(self):
        import datetime as dt
        from shows.hooks.omni_view_world import build_payload
        payload = build_payload(ROOT, dt.date(2026, 9, 23))
        assert len(payload["articles"]) >= 8
        assert all(not a["url"].startswith("https://x.com") for a in payload["articles"])
        assert "REGIONAL DESKS" in payload["hook_context"]


# ---------------------------------------------------------------------------
# X posts credit the article they link; the show decides how posts may serve
# ---------------------------------------------------------------------------

class TestXSourcePolicy:
    RAW = ("POST_TITLE: Eleven killed near Durban\nPOST_TEXT: Gunmen killed 11 people.\n"
           "POST_URL: https://x.com/BBCAfrica/status/1\nPOST_LINK: https://www.bbc.com/news/articles/abc\n\n"
           "POST_TITLE: A bare post\nPOST_TEXT: No link here.\nPOST_URL: https://x.com/BBCAfrica/status/2\n"
           "POST_LINK: none\n\n"
           "POST_TITLE: Quote of another post\nPOST_TEXT: t\nPOST_URL: https://x.com/BBCAfrica/status/3\n"
           "POST_LINK: https://x.com/someone/status/9\n")

    def _posts(self):
        from engine.fetcher import _parse_x_posts
        return _parse_x_posts(self.RAW, "BBCAfrica", "BBC Africa", "2026-09-23T00:00:00Z")

    def test_a_linked_post_is_credited_to_the_article(self):
        p = self._posts()
        assert p[0]["url"] == "https://www.bbc.com/news/articles/abc"
        assert p[0]["x_url"] == "https://x.com/BBCAfrica/status/1"
        assert p[0]["source_name"] == "BBC Africa" and p[0]["x_linked"] is True

    def test_an_unlinked_post_and_a_link_to_x_keep_the_post_url(self):
        p = self._posts()
        assert p[1]["url"].startswith("https://x.com") and p[1]["x_linked"] is False
        assert p[2]["url"].startswith("https://x.com/BBCAfrica") and p[2]["x_linked"] is False

    def test_linked_only_drops_unlinked_posts_and_secondary_demotes(self):
        from engine.fetcher import apply_x_source_policy
        rss = {"title": "r", "url": "https://www.reuters.com/z", "source_name": "Reuters"}
        arts = self._posts() + [rss]
        kept, dropped = apply_x_source_policy(arts, "linked_only")
        assert dropped == 2 and [a["source_name"] for a in kept] == ["BBC Africa", "Reuters"]
        ordered, dropped2 = apply_x_source_policy(arts, "secondary")
        assert dropped2 == 0 and ordered[0] is rss
        same, d3 = apply_x_source_policy(arts, "any")
        assert same == arts and d3 == 0

    def test_the_fetch_prompt_asks_for_the_link(self):
        src = (ROOT / "engine" / "fetcher.py").read_text(encoding="utf-8")
        assert "POST_LINK:" in src

    def test_every_new_show_declares_a_policy_and_desks_are_linked_only(self):
        for slug in NEW13:
            data = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            assert data.get("x_posts_as_sources") in ("linked_only", "secondary"), slug
            if slug in DESKS or slug in ("vancouver", "collingwood", "omni_view_world"):
                assert data["x_posts_as_sources"] == "linked_only", slug

    def test_own_voice_shows_keep_the_legacy_x_policy(self):
        # Sep 24 2026: the network sourcing pass put the policy on every news
        # show that does not own its story; Tesla's and SpaceX's own posts are
        # primary sources, so they stay on the legacy policy with no lint.
        for slug in ("tesla", "spacex"):
            data = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            assert "x_posts_as_sources" not in data and "digest_lints" not in data, slug
        for slug in ("omni_view", "models_agents"):
            data = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            assert data["x_posts_as_sources"] == "secondary", slug


# ---------------------------------------------------------------------------
# Wire credit, region guard, number capitalisation, config
# ---------------------------------------------------------------------------

class TestSmallFixes:
    def test_a_dateline_credits_the_wire(self):
        from engine.fetcher import credit_wire_datelines
        arts = [{"source_name": "The Mighty 790 KFGO",
                 "content_text": "ROME (Reuters) — Italy's Senate gave final approval on Wednesday."},
                {"source_name": "BBC Europe", "content_text": "Berlin published a roadmap."}]
        assert credit_wire_datelines(arts) == 1
        assert arts[0]["source_name"] == "Reuters" and arts[0]["syndicated_via"] == "The Mighty 790 KFGO"
        assert arts[1]["source_name"] == "BBC Europe"

    def test_a_sentence_initial_number_word_is_capitalised(self):
        from assets.pronunciation import prepare_text_for_tts
        out = prepare_text_for_tts("Customers can order a unit. 1,152 NVIDIA chips are specified.")
        assert ". One thousand one hundred fifty-two" in out

    def test_local_shows_carry_a_region_allowlist_with_no_generic_words(self):
        for slug in ("vancouver", "collingwood"):
            data = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            terms = data["region_allowlist"]
            assert len(terms) >= 15
            for bad in ("City", "Local", "Town", "BC"):
                assert bad not in terms, (slug, bad)

    def test_config_parses_the_three_new_fields(self):
        from engine.config import load_config
        cfg = load_config(ROOT / "shows" / "vancouver.yaml")
        assert "wyntk_hook_match" in cfg.digest_lints
        assert cfg.x_posts_as_sources == "linked_only"
        assert "Burnaby" in cfg.region_allowlist
        tesla = load_config(ROOT / "shows" / "tesla.yaml")
        assert tesla.digest_lints == [] and tesla.x_posts_as_sources == "any" and tesla.region_allowlist == []

    def test_run_show_is_wired(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "run_digest_lints(x_thread, _lint_names)" in src
        assert "or _lint_findings) and not is_deep_dive" in src
        assert "apply_x_source_policy(articles, _x_policy)" in src
        assert 'metrics.record("articles_dropped_off_region"' in src
        assert "attempt_item_coverage_repair(" in src
        assert "credit_wire_datelines(articles)" in src
        # The coverage floor needs the repair LLM defined OUTSIDE the
        # enforce-repair branch.
        assert src.index("def _repair_llm(") < src.index("# One bounded repair pass before an enforce-mode block")


# ---------------------------------------------------------------------------
# Claims: the item coverage floor
# ---------------------------------------------------------------------------

class TestItemCoverageFloor:
    DIGEST = ("# Show\n**HOOK:** Hook.\n\n### Top News\n**Item one about the plant: Reuters**\n"
              "The plant in Ohio will add two hundred megawatts by March, the company said on Tuesday. "
              "Source: [reuters.com](https://www.reuters.com/a)\n\n"
              "**Item two about the vote: AP**\nThe council voted seven to two to approve the levy on "
              "Monday night. Source: [apnews.com](https://apnews.com/b)\n")

    def test_coverage_counts_items_a_verified_entry_anchors(self):
        from engine.claims import item_source_coverage
        verified = [{"id": "1", "claim": "The Ohio plant adds 200 MW by March",
                     "episode_span": "The plant in Ohio will add two hundred megawatts by March"}]
        total, covered, uncovered = item_source_coverage(self.DIGEST, verified)
        assert (total, covered) == (2, 1)
        assert uncovered and uncovered[0].startswith("The council voted")

    def test_floor_only_ever_adds_verified_entries(self):
        from engine.claims import GateResult, attempt_item_coverage_repair
        gate = GateResult(passed=True, claims_total=0, claims_verified=0)
        calls = []

        def bad_llm(prompt):
            calls.append(prompt)
            return "[]"  # the model offers nothing
        g2, c2, info = attempt_item_coverage_repair(self.DIGEST, gate, [], bad_llm,
                                                    fetch=lambda u: (404, ""), local_texts={})
        assert g2 is gate and c2 == [] and info["coverage_repair_attempted"] is True
        assert info["items_with_source"] == 2 and info["item_coverage_pct"] == 0.0
        assert calls, "the repair pass was spent"

    def test_a_covered_digest_spends_no_call(self):
        from engine.claims import GateResult, attempt_item_coverage_repair
        verified = [
            {"id": "1", "claim": "Ohio plant adds 200 MW by March",
             "episode_span": "The plant in Ohio will add two hundred megawatts by March"},
            {"id": "2", "claim": "Council approved the levy 7-2",
             "episode_span": "The council voted seven to two to approve the levy"},
        ]
        gate = GateResult(passed=True, claims_total=2, claims_verified=2, verified_claims=verified)
        g2, _, info = attempt_item_coverage_repair(self.DIGEST, gate, verified,
                                                   lambda p: pytest.fail("no call expected"))
        assert g2 is gate and info["item_coverage_pct"] == 100.0

    def test_the_appendix_no_longer_calls_an_empty_ledger_normal(self):
        from engine.claims import claims_prompt_appendix
        text = claims_prompt_appendix()
        assert "valid and normal" not in text
        assert "a news item that carries a Source line asserts at least one" in text
