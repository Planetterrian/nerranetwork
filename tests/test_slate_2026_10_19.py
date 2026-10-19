"""The Oct 19 2026 slate, reviewed (first day on the Eastern schedule and the
first live day of the video job).

What binds (each verified against the committed data of the day):

* a bold ``**Title: Outlet**`` line and its paragraph are ONE story item in
  ``engine.digest_lint`` (MAG 7 Ep026 read 3 unsourced items on 7 sourced);
* the IMOCA boat page is parsed from its plain ``<th>`` facts table (every
  one of the 20 fleet pages had failed since the site dropped ProfileCard);
* the digest expansion retry names a story section under its item floor and
  asks for STORIES, not longer items (FF Ep227: three generations, three
  stories each from 44 articles, padded with 'treble clef' ×5);
* a known platform sender is classified without a model call;
* the fire-tick gate reads interviews only around their slot;
* the video job dispatches the multilingual sweep from the render job;
* a bold-wrapped heading is never promoted to the hook blockquote (M&A
  Ep208: ``> **# Models & Agents**`` on 337 related cards);
* AI Chips Ep027 carries its price correction on every text surface.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from engine import digest_lint as L  # noqa: E402
from engine import generator as G  # noqa: E402
from engine.newsletter_body import promote_hook_to_blockquote  # noqa: E402


class TestHeadlineItemsKeepTheirBody:
    DIGEST = (
        "### Top News\n\n"
        "**Gurman says iPhone Duo walk-in calls are premature: Bloomberg**\n\n"
        "Mark Gurman wrote that retail stores he has talked to are still sorting: how many units.\n"
        "Source: [bloomberg.com](https://www.bloomberg.com/x)\n\n"
        "**Google releases a $100 Home Speaker for Gemini: New York Post**\n"
        "The New York Post's reporter saw it. Source: [nypost.com](https://nypost.com/y)\n"
    )

    def test_title_then_blank_then_body_is_one_item(self):
        total, missing = L.items_without_source(self.DIGEST)
        assert (total, missing) == (2, 0)

    def test_the_committed_mag7_digest_reads_zero(self):
        text = (ROOT / "digests" / "mag7" / "MAG7_Daily_Ep026_20261018.md").read_text(encoding="utf-8")
        assert L.items_without_source(text) == (7, 0)


class TestImocaFactsTable:
    def test_plain_th_rows_carry_the_profile(self):
        import fetch_offshore_north_dashboard as f
        html = ('<h2 class="x">FRA 3</h2><div class="BoatSpecs-sheet">'
                '<table class="Table"><tr><th>Baptismal name</th><td>Charal</td></tr>'
                '<tr><th>Architect</th><td>Sam Manuard</td></tr>'
                '<tr><th>Construction</th><td>2022, CDK Technologies, Lorient</td></tr>'
                '<tr><th>Launch date</th><td>7/11/22</td></tr><tr><th>Foils</th><td>Yes</td></tr></table></div>')
        out = f.parse_imoca_boat_page(html)
        assert out["architect"] == "Sam Manuard" and out["launch_date"] == "7/11/22"
        assert out["baptismal_name"] == "Charal" and out["foils"] == "Yes"

    def test_the_old_profilecard_markup_still_wins(self):
        import fetch_offshore_north_dashboard as f
        html = ('<table><tr><th><span class="ProfileCard-label">Architect</span></th><td>Old</td></tr></table>'
                '<table><tr><th>Architect</th><td>New</td></tr></table>')
        assert f.parse_imoca_boat_page(html)["architect"] == "Old"


class TestExpansionAsksForStories:
    FF = (ROOT / "digests" / "fascinating_frontiers" / "Fascinating_Frontiers_Ep227_20261019.md")

    def test_ff_ep227_is_under_its_item_floor(self):
        text = self.FF.read_text(encoding="utf-8")
        assert G.digest_item_shortfalls(text, "fascinating_frontiers") == [("Space Stories", 3, 8)]

    def test_unknown_show_is_empty(self):
        assert G.digest_item_shortfalls("### Top News\n1. **x**", "no_such_show") == []

    def test_the_prompt_names_the_floor_and_ranks_it_first(self):
        prompt = G._build_digest_expansion_retry_prompt(
            600, 1400, "draft", sections=[("Space Stories", 500)],
            item_shortfalls=[("Space Stories", 3, 8)])
        assert "ITEM FLOOR" in prompt
        assert "- Space Stories: 3 items, the floor is 8" in prompt
        assert "ADDING stories from the material" in prompt
        assert prompt.index("ITEM FLOOR") < prompt.index("DEPTH RULES")
        # The narrative branch never asks for more stories.
        assert "ITEM FLOOR" not in G._build_digest_expansion_retry_prompt(
            600, 1400, "draft", narrative=True, item_shortfalls=[("x", 1, 3)])


class TestPlatformSendersSkipTheModel:
    def test_github_notifications_are_a_platform_notice(self, monkeypatch):
        from pipelines.producer import classify as C
        monkeypatch.setattr(C, "_call_grok", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("model called")))
        thread = {"id": "t", "messages": [{"from_email": "notifications@github.com",
                                             "subject": "[Planetterrian/nerranetwork] Run failed",
                                             "body": "x", "internal_ts": 1}]}
        out = C.classify_thread(thread, "patrick@avvizo.com")
        assert out["category"] == "platform_notice" and out["_attempts"] == 0

    def test_a_publicist_still_reaches_the_model(self):
        from pipelines.producer import classify as C
        assert not C.platform_sender("sam@reyespr.com")
        assert C.platform_sender("MAILER-DAEMON@googlemail.com")


class TestFireTickWindow:
    TS = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")

    def test_interviews_are_read_around_their_slot_only(self):
        assert "const FIRE_TICK_INTERVIEW_LOOKBACK_MS = 3 * 3600000;" in self.TS
        i = self.TS.index("async function fireTickDue(")
        body = self.TS[i:i + 1500]
        assert "scheduled_at=gte.${ilo}" in body
        # The no-show sweep's two-day read of the RUN table is untouched.
        assert "created_at=gte.${lo}" in body


class TestVideoJobDispatchesTheSweep:
    def test_from_the_render_job_after_its_push(self):
        wf = yaml.safe_load((ROOT / ".github" / "workflows" / "render-video.yml").read_text(encoding="utf-8"))
        render = [s for s in wf["jobs"]["render"]["steps"] if s.get("name") == "Start the multilingual sweep"]
        assert len(render) == 1
        assert "steps.commit.outputs.pushed == 'true'" in render[0]["if"]
        assert "--after-video" in render[0]["run"]
        homepage = [s for s in wf["jobs"]["homepage"]["steps"] if "followup_dispatch" in str(s.get("run", ""))]
        assert homepage == []


class TestBoldHeadingIsNotAHook:
    def test_promotion_walks_past_a_bold_wrapped_title(self):
        out = promote_hook_to_blockquote(
            "**# Models & Agents**\nFrozen tables let ternary models fly on laptops.\n\n**What You Need to Know:** x\n")
        lines = out.splitlines()
        assert lines[0] == "**# Models & Agents**"
        assert lines[1] == "> **Frozen tables let ternary models fly on laptops.**"

    def test_no_committed_record_opens_on_a_heading_blockquote(self):
        for path in ROOT.glob("digests/*/summaries_*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            rows = data.get("summaries", []) if isinstance(data, dict) else data
            for row in rows:
                if isinstance(row, dict):
                    assert not str(row.get("content", "")).startswith("> **#"), (path.name, row.get("episode_num"))

    def test_models_agents_ep208_carries_its_hook(self):
        text = (ROOT / "digests" / "models_agents" / "Models_Agents_Ep208_20261019.md").read_text(encoding="utf-8")
        assert text.startswith("# Models & Agents\n> **Frozen 16 MB embedding tables")


class TestAiChipsPriceCorrection:
    def test_filed_and_applied(self):
        from engine.corrections import corrections_for
        entries = corrections_for(ROOT / "digests" / "ai_chips", 27)
        assert entries and entries[0]["where"] == "both"
        for name in ("AI_Chips_Ep027_20261018.md", "AI_Chips_Ep027_20261018_tts.txt",
                     "AI_Chips_Ep027_20261018_transcript.txt"):
            text = (ROOT / "digests" / "ai_chips" / name).read_text(encoding="utf-8")
            assert "2,599" not in text and "five hundred ninety-nine" not in text, name
        digest = (ROOT / "digests" / "ai_chips" / "AI_Chips_Ep027_20261018.md").read_text(encoding="utf-8")
        assert re.search(r"start at \$2,399", digest)
