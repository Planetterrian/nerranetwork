"""Drift guards for the June 2026 network-wide show quality pass.

Covers the ten non-flagship shows (Tesla/MIT had their own passes):
* every chronically-short show opts into podcast_expand_below_target;
* the generalized show_memory engine inherited (and now has fixed) the
  Tesla theme-pollution + narrative-freshness bugs;
* the hardcoded + fallback X teasers are hook-led network-wide;
* boilerplate-tic bans landed in the prompts;
* the narrative shows' topic queues have real runway.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _yaml(slug):
    return yaml.safe_load((_ROOT / "shows" / f"{slug}.yaml").read_text(
        encoding="utf-8")) or {}


class TestExpandBelowTargetOptIns:
    # Shows the review found chronically below target (>=50% of recent eps).
    EXPECTED = [
        "models_agents", "fascinating_frontiers", "planetterrian",
        "models_agents_beginners", "env_intel", "finansy_prosto",
        "unintended_consequences", "first_principles",
    ]

    @pytest.mark.parametrize("slug", EXPECTED)
    def test_show_opts_in(self, slug):
        llm = _yaml(slug).get("llm") or {}
        assert llm.get("podcast_expand_below_target") is True, (
            f"{slug} ships chronically below target — it must opt into "
            f"podcast_expand_below_target"
        )

    def test_models_agents_has_explicit_target(self):
        # Was relying on the implicit 1500 default; made explicit.
        assert (_yaml("models_agents").get("llm") or {}).get(
            "min_podcast_words") == 1500


class TestShowMemoryFixesPorted:
    def test_theme_mining_is_digest_only(self, tmp_path):
        from engine import show_memory as sm

        cfg = sm.get_config("models_agents")
        assert cfg is not None
        digest = "OpenAI shipped a new frontier model with agentic tool use."
        sm.update_theme_history_from_digest(tmp_path, cfg, digest, 80)
        import json
        themes = json.loads(
            (tmp_path / cfg.theme_filename).read_text())["recurring_themes"]
        # Template phrases must never appear.
        for noise in ("open questions", "questions show", "narrative memory"):
            assert noise not in themes

    def test_theme_mining_strips_source_attribution_labels(self, tmp_path):
        """Markdown source links ("Source: [Google News](url)") must be
        stripped LABEL-and-all before mining. The bare-URL strip alone left
        the label, so the repeated source name paired with the next story's
        first word into junk bigrams — "google spacex" ranked #1 on SpaceX
        Daily (June 2026 review); "science nasa" / "reddit localllama" on the
        sibling memory shows.
        """
        from engine import show_memory as sm
        import json

        cfg = sm.get_config("spacex")
        assert cfg is not None
        digest = (
            "SpaceX flew a Falcon mission today.\n"
            "Source: [Google News](https://news.google.com/rss/articles/abc)\n\n"
            "Starship static-fired at Starbase.\n"
            "Source: [Google News](https://news.google.com/rss/articles/def)\n"
        )
        sm.update_theme_history_from_digest(tmp_path, cfg, digest, 3)
        themes = json.loads(
            (tmp_path / cfg.theme_filename).read_text())["recurring_themes"]
        # No theme may contain a source-label token from a stripped link.
        for key in themes:
            assert "google" not in key.split(), f"source-label leak: {key!r}"

    def test_auto_narrative_freshness_exists_and_runs(self, tmp_path):
        from engine import show_memory as sm

        cfg = sm.get_config("fascinating_frontiers")
        mentioned = sm.auto_update_narrative_from_digest(
            tmp_path, cfg, "Starship completed another Mars-bound test.",
            96, "2026-06-09")
        assert "starship_mars" in mentioned
        tracker = sm.load_narrative_tracker(tmp_path, cfg)
        assert tracker["programs"]["starship_mars"]["last_mentioned_episode"] == 96

    def test_status_block_has_continuity_instruction(self):
        from engine import show_memory as sm

        cfg = sm.get_config("planetterrian")
        tracker = sm.load_narrative_tracker(
            _ROOT / "digests" / "planetterrian", cfg)
        block = sm.build_narrative_status_block(tracker, cfg.label)
        assert "MAKE THE CONTINUITY AUDIBLE" in block


class TestHookLedTeasersNetworkWide:
    @pytest.mark.parametrize("slug,name", [
        ("omni_view", "Omni View"),
        ("fascinating_frontiers", "Fascinating Frontiers"),
        ("planetterrian", "Planetterrian Daily"),
        ("models_agents", "Models & Agents"),
        ("unintended_consequences", "Unintended Consequences"),
    ])
    def test_teaser_leads_with_hook_and_links_blog(self, slug, name):
        import run_show

        cfg = SimpleNamespace(
            slug=slug, name=name,
            publishing=SimpleNamespace(x_teaser_template=""))
        teaser = run_show._build_teaser(
            cfg, 80, "June 10, 2026",
            {"hook": "A distinctive hook for this episode."})
        assert "A distinctive hook for this episode." in teaser
        assert f"blog/{slug}/ep080.html" in teaser
        assert "summaries.html" not in teaser

    def test_no_hook_no_blog_falls_back_gracefully(self):
        import run_show

        cfg = SimpleNamespace(
            slug="some_unknown_show", name="Unknown Show",
            publishing=SimpleNamespace(x_teaser_template=""))
        teaser = run_show._build_teaser(cfg, 5, "June 10, 2026", {})
        assert teaser  # never empty


class TestPromptTicBans:
    CASES = [
        ("models_agents_podcast.txt", "This development sits within the ongoing"),
        ("fascinating_frontiers_podcast.txt", "blew my mind"),
        ("planetterrian_podcast.txt", "this development fits the tracked program"),
        ("omni_view_podcast.txt", "VARY HOW YOU INTRODUCE THE SIDES"),
        # June 12 2026 UC pass: the "That wraps today's case" ban was
        # superseded — that phrase is the supplied sign-off (LLM can't vary
        # it), so it was removed from the closing pool instead. The prompt
        # bullet now targets the LLM-controlled lesson close.
        ("unintended_consequences_podcast.txt", "stale final beat in the Lesson"),
        ("mab_podcast.txt", "go do this right now"),
        ("env_intel_digest.txt", "REQUIRED EVERY EPISODE"),
    ]

    @pytest.mark.parametrize("fname,needle", CASES)
    def test_prompt_mentions_the_ban_or_requirement(self, fname, needle):
        text = (_ROOT / "shows" / "prompts" / fname).read_text(
            encoding="utf-8")
        assert needle in text, f"{fname} missing expected guidance: {needle!r}"


class TestNarrativeQueueRunway:
    # NOTE: topic-queue restocks are MANUAL (no auto-generation), and a breach
    # here fails the full -x suite and thus blocks unrelated PRs — restock the
    # shows/topic_queues/ YAML before the runway runs out.
    # unintended_consequences runs 7 days/week (cron "1 9 * * *", a daily
    # narrative show per DAILY_NARRATIVE_SHOWS in test_schedule.py); per_week
    # was corrected 5→7 July 2026 to match the real cadence.
    @pytest.mark.parametrize("slug,per_week,min_weeks", [
        ("unintended_consequences", 7, 4.0),
        ("first_principles", 7, 3.0),
    ])
    def test_queue_has_runway(self, slug, per_week, min_weeks):
        q = yaml.safe_load(
            (_ROOT / "shows" / "topic_queues" / f"{slug}.yaml").read_text(
                encoding="utf-8"))["queue"]
        unproduced = [e for e in q if not e.get("produced")]
        weeks = len(unproduced) / per_week
        assert weeks >= min_weeks, (
            f"{slug} queue runway is only {weeks:.1f} weeks — restock it "
            f"(min {min_weeks})"
        )

    def test_queue_ids_unique(self):
        for slug in ("unintended_consequences", "first_principles"):
            q = yaml.safe_load(
                (_ROOT / "shows" / "topic_queues" / f"{slug}.yaml").read_text(
                    encoding="utf-8"))["queue"]
            ids = [e["id"] for e in q]
            assert len(ids) == len(set(ids)), f"{slug} has duplicate queue ids"

    def test_first_principles_alternation_stocked(self):
        q = yaml.safe_load(
            (_ROOT / "shows" / "topic_queues" / "first_principles.yaml").read_text(
                encoding="utf-8"))["queue"]
        unproduced = [e for e in q if not e.get("produced")]
        cats = {e.get("category") for e in unproduced}
        # Both arms of the alternation must remain available.
        assert "concrete_example" in cats
        assert "opportunity_area" in cats

    def test_first_principles_unproduced_alternates(self):
        """July 2 2026 hygiene pass: the unproduced FP queue was
        re-sequenced to alternate concrete_example / opportunity_area.

        The original assertion hardcoded ``seq[0] == "concrete_example"``,
        which was only true on the day it was written — FP produces one
        topic per day, so the expected head category flips daily and the
        test broke the same afternoon (the 08:31 UTC episode consumed the
        next concrete_example). The durable invariant is that alternation
        CONTINUES from the produced tail: the first unproduced entry
        differs from the last produced entry's category, and adjacent
        same-category pairs stay at the theoretical minimum (the |#C - #O|
        overflow that can't be interleaved away)."""
        q = yaml.safe_load(
            (_ROOT / "shows" / "topic_queues" / "first_principles.yaml").read_text(
                encoding="utf-8"))["queue"]
        seq = [e.get("category") for e in q if not e.get("produced")]
        produced_cats = [e.get("category") for e in q if e.get("produced")]
        if produced_cats and seq:
            assert seq[0] != produced_cats[-1], (
                f"FP alternation broken at the produced/unproduced boundary: "
                f"last produced was {produced_cats[-1]!r}, next up is {seq[0]!r}"
            )
        n_c = seq.count("concrete_example")
        n_o = seq.count("opportunity_area")
        same_adj = sum(1 for a, b in zip(seq, seq[1:]) if a == b)
        assert same_adj <= abs(n_c - n_o), (
            f"FP unproduced queue not minimally alternated: {same_adj} "
            f"adjacent same-category pairs (C={n_c}, O={n_o}): {seq}"
        )

    def test_no_duplicate_topics_reintroduced(self):
        """FP had true-duplicate unproduced entries — aluminum-electrolysis
        (a second Hall-Héroult story), a second LED entry, and a second
        heat-pump entry. They were removed; guard against re-adding them."""
        q = yaml.safe_load(
            (_ROOT / "shows" / "topic_queues" / "first_principles.yaml").read_text(
                encoding="utf-8"))["queue"]
        ids = {e["id"] for e in q}
        for removed in ("aluminum-electrolysis", "led-lighting-cost-per-lumen",
                        "heat-pumps-space-heating"):
            assert removed not in ids, f"{removed} duplicate re-introduced"
        # The kept canonical entries survive.
        for kept in ("aluminum-hall-heroult", "lighthouse-led-efficiency",
                     "air-conditioning-heat-pumps"):
            assert kept in ids

    def test_uc_biofuels_category_accurate(self):
        """biofuels-deforestation was mislabeled category: medicine; it's a
        policy-mandate backfire."""
        q = yaml.safe_load(
            (_ROOT / "shows" / "topic_queues" / "unintended_consequences.yaml").read_text(
                encoding="utf-8"))["queue"]
        b = next(e for e in q if e["id"] == "biofuels-deforestation")
        assert b["category"] == "policy"

    def test_uc_unproduced_interleaved_not_clustered(self):
        """The window shipped 8 consecutive medicine then 5 consecutive
        infrastructure episodes. The unproduced queue is now round-robin
        interleaved — no long single-category run at the head."""
        q = yaml.safe_load(
            (_ROOT / "shows" / "topic_queues" / "unintended_consequences.yaml").read_text(
                encoding="utf-8"))["queue"]
        seq = [e.get("category") for e in q if not e.get("produced")]
        # No 3-in-a-row of the same category anywhere before the dominant
        # category's unavoidable tail overflow (economics = 10 of 33).
        from collections import Counter
        counts = Counter(seq)
        dominant = counts.most_common(1)[0][0]
        head = seq[: len(seq) - counts[dominant]]  # region before overflow can bite
        runs = [sum(1 for _ in g) for _, g in __import__("itertools").groupby(head)]
        assert max(runs, default=0) <= 1, f"clustered head: {seq}"


class TestNoDuplicateFeedUrls:
    """July 2 2026: Models & Agents subscribed arXiv cs.CL twice —
    ``https://arxiv.org/rss/cs.CL`` (label "arXiv NLP") and
    ``http://export.arxiv.org/rss/cs.CL`` (label "arXiv cs.CL"). Same feed,
    double-weighted preprints (root cause of the arXiv flood that crowded
    out Codex Record Replay / Gemini Computer Use). This guard normalizes
    scheme + the export.arxiv.org host alias so a re-subscribed feed under a
    different scheme/host can't slip back in.
    """

    # Pre-existing, out-of-scope duplicate on a show not owned by this pass
    # (omni_view subscribes BBC News over both http and https). Recorded so
    # this guard is meaningful network-wide without failing on a file this
    # pass may not touch; the omni_view owner should collapse it. Any NEW
    # duplicate — including a second one on omni_view — still fails.
    _ALLOWED = {
        "omni_view": {"feeds.bbci.co.uk/news/rss.xml"},
    }

    @staticmethod
    def _norm(url: str) -> str:
        import re
        u = (url or "").strip().lower()
        u = re.sub(r"^https?://", "", u)
        u = u.replace("export.arxiv.org", "arxiv.org")
        return u.rstrip("/")

    def test_no_show_subscribes_the_same_feed_twice(self):
        import glob
        offenders = {}
        for f in glob.glob(str(_ROOT / "shows" / "*.yaml")):
            slug = Path(f).stem
            cfg = yaml.safe_load(Path(f).read_text(encoding="utf-8")) or {}
            seen = {}
            for src in cfg.get("sources") or []:
                if not isinstance(src, dict):
                    continue
                n = self._norm(src.get("url", ""))
                if not n:
                    continue
                seen.setdefault(n, 0)
                seen[n] += 1
            allowed = self._ALLOWED.get(slug, set())
            dups = [n for n, c in seen.items() if c > 1 and n not in allowed]
            if dups:
                offenders[slug] = dups
        assert not offenders, f"duplicate feed URLs found: {offenders}"

    def test_models_agents_has_single_cs_cl_feed(self):
        cfg = _yaml("models_agents")
        cs_cl = [
            s for s in (cfg.get("sources") or [])
            if isinstance(s, dict) and "cs.cl" in self._norm(s.get("url", ""))
        ]
        assert len(cs_cl) == 1, (
            f"arXiv cs.CL must be subscribed exactly once; got {cs_cl}"
        )


class TestFinansyProstoCategoryFix:
    def test_youtube_category_is_education(self):
        yt = _yaml("finansy_prosto").get("youtube") or {}
        # Was 25 (News & Politics) — a financial-literacy education show.
        assert yt.get("category_id") == 27
