"""Nov 8 2026 — a listener review of Offshore North Ep012 (2 Nov), acted on.

The reviewer's five points, and what each became:

* Lead with this week's news: Ep012's hook was Thomas Ruyant withdrawing
  from the Route du Rhum, Ep006's lead six weeks earlier. The digest prompt
  now carries the dated list of past leads ({recent_leads}) and
  ``hook_repeats_past_lead`` enforces it.
* Race status: "contraint de stopper" became Marchand "out of a race";
  Dorange diverting to repair became "removed from contention". The prompt
  carries a stop-vs-retirement vocabulary, the standing facts carry a dated
  race record, and ``stop_told_as_retirement`` checks each item against its
  own source. (Checked Nov 8 against the race reports: both skippers DID
  retire afterwards, Marchand on 4 Nov and Dorange on 6 Nov, so the record
  says what was true on which date rather than the reviewer's Nov 2-3 state.)
* The team's 31 October video was a start preview, told as coverage:
  ``preview_told_as_result``.
* Unsourced numbers (115 boats; the Plain Sailing budget and insurance
  share): ``item_figures_sourced`` and ``explainer_figures_sourced``.
* Alan Roberts' background and the 2023 class win on the earlier IMOCA,
  whenever the RORC Transatlantic is mentioned.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from engine import digest_lint as dl

ROOT = Path(__file__).resolve().parent.parent
ON = ROOT / "digests" / "offshore_north"
EP012 = ON / "Offshore_North_Ep012_20261102.md"
PROMPTS = ROOT / "shows" / "prompts"

NEW_LINTS = (
    "hook_repeats_past_lead", "stop_told_as_retirement",
    "preview_told_as_result", "explainer_figures_sourced",
    "item_figures_sourced",
)


def _ep012() -> str:
    return EP012.read_text(encoding="utf-8")


def _yaml() -> dict:
    return yaml.safe_load((ROOT / "shows" / "offshore_north.yaml").read_text(encoding="utf-8"))


def _beat() -> list:
    return [t.strip() for t in _yaml()["publishing"]["rss_keywords"].split(",")]


# Source excerpts the Ep012 items were built from (abridged from the pages).
MARCHAND_URL = ("https://voilesetvoiliers.ouest-france.fr/course-au-large/route-du-rhum/"
                "route-du-rhum-avarie-de-safran-pour-anthony-marchand-contraint-de-stopper-"
                "son-actual-ultim-4-98201796-d698-11f1-84f3-5611f158a658")
DORANGE_URL = ("https://www.ouest-france.fr/route-du-rhum/route-du-rhum-violette-dorange-file-"
               "vers-roscoff-pour-reparer-son-imoca-7b12e3da-d62b-11f1-84f3-5611f158a658")
RUYANT_URL = ("https://www.franceinfo.fr/sports/voile/route-du-rhum/je-suis-dans-le-milieu-depuis-"
              "douze-ans-et-je-n-ai-jamais-connu-ca-le-monde-de-la-voile-est-il-dans-le-creux-de-"
              "la-vague-economiquement_8221336.html")
VIDEO_URL = "https://www.youtube.com/watch?v=TJHCn-f4CWY"
FILLER = " Le skipper fait le point avec son équipe technique à terre." * 6


def _articles() -> list:
    return [
        {"url": MARCHAND_URL, "published_date": "2026-11-02",
         "title": "Avarie de safran pour Anthony Marchand, contraint de stopper son Actual Ultim 4",
         "full_text": "Anthony Marchand a été contraint de stopper Actual Ultim 4 après une "
                      "avarie de safran central. L'équipe évalue les dégâts et une réparation "
                      "est à l'étude." + FILLER},
        {"url": DORANGE_URL, "published_date": "2026-11-01",
         "title": "Violette Dorange file vers Roscoff pour réparer son Imoca",
         "full_text": "Violette Dorange a percuté le trimaran Use It Again de Romain Pilliard au "
                      "large de Bréhat. Son foil tribord est endommagé et elle se déroute vers "
                      "Roscoff pour réparer." + FILLER},
        {"url": RUYANT_URL, "published_date": "2026-11-02",
         "title": "Le monde de la voile est-il dans le creux de la vague économiquement ?",
         "full_text": "Thomas Ruyant a renoncé à la Route du Rhum faute de budget. Un projet "
                      "Imoca coûte désormais dix millions d'euros." + FILLER},
        {"url": VIDEO_URL, "published_date": "2026-10-31",
         "title": "Route du Rhum 2026 start breakdown",
         "description": "Scott Shawyer breaks down the Route du Rhum start: weather routing, "
                        "wind patterns and the tactical choices facing the fleet." + FILLER},
    ]


def _ctx(**extra) -> dict:
    ctx = {"articles": _articles(), "beat_terms": _beat(),
           "past_hooks": dl.past_hooks(ON, before_episode=12)}
    ctx.update(extra)
    return ctx


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

class TestWiring:
    def test_lints_registered_and_context_aware(self):
        for name in NEW_LINTS:
            assert name in dl.LINTS
        for name in ("hook_repeats_past_lead", "stop_told_as_retirement",
                     "preview_told_as_result", "item_figures_sourced"):
            assert name in dl.CONTEXT_LINTS

    def test_offshore_north_opts_in(self):
        assert list(_yaml()["digest_lints"]) == list(NEW_LINTS)

    def test_config_loader_keeps_the_list(self):
        from engine.config import load_config

        cfg = load_config(str(ROOT / "shows" / "offshore_north.yaml"))
        assert list(cfg.digest_lints) == list(NEW_LINTS)

    def test_run_show_builds_the_lint_context(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "def _digest_lint_context(" in src
        assert src.count("context=_lint_ctx") == 3

    def test_lint_context_reads_past_hooks_and_briefing(self):
        import run_show
        from engine.config import load_config

        cfg = load_config(str(ROOT / "shows" / "offshore_north.yaml"))
        ctx = run_show._digest_lint_context(cfg, [], {"campaign_status": "STATUS 741"}, 13)
        assert ctx["past_hooks"] and ctx["past_hooks"][0][0] == "2026-11-02"
        assert "Scott Shawyer" in ctx["beat_terms"]
        assert "118 solo skippers" in ctx["reference_text"]  # field guide, includes resolved
        assert "STATUS 741" in ctx["reference_text"]


# ---------------------------------------------------------------------------
# 1. Lead with this week's news
# ---------------------------------------------------------------------------

class TestHookRepeatsPastLead:
    def test_ep012_fires_on_ep006(self):
        f = dl.lint_hook_repeats_past_lead(_ep012(), _ctx())
        assert f is not None and f.note
        assert "2026-09-21" in f.note

    def test_replay_on_the_whole_show(self):
        """Ep012 (Ruyant, Ep006) and Ep010 (alongside in Gosport, Ep008)
        only — never the race followed from start to leader (Ep003/Ep004),
        and never a skipper's name alone (Ep009 vs Ep001)."""
        fired = []
        for path in sorted(ON.glob("Offshore_North_Ep*_2026*.md")):
            n = int(path.name.split("_Ep")[1][:3])
            hook = dl.hook_line(path.read_text(encoding="utf-8"))
            if dl.hook_repeat_match(hook, dl.past_hooks(ON, before_episode=n), _beat()):
                fired.append(n)
        assert fired == [10, 12]

    def test_no_past_hooks_is_silent(self):
        assert dl.lint_hook_repeats_past_lead(_ep012(), {"articles": []}) is None

    def test_prompt_carries_recent_leads(self):
        digest = (PROMPTS / "offshore_north_digest.txt").read_text(encoding="utf-8")
        assert "{recent_leads}" in digest
        assert "THE HOOK IS THIS WEEK'S NEWS" in digest

    def test_recent_leads_block(self):
        from engine.offshore_north_status import recent_leads

        block = recent_leads(before_episode=13)
        assert block.splitlines()[0].startswith("- 2 November 2026: ")
        assert "Ruyant" in block


# ---------------------------------------------------------------------------
# 2. Race status: a stop is not a retirement
# ---------------------------------------------------------------------------

class TestStopToldAsRetirement:
    def test_ep012_marchand_and_dorange_fire_ruyant_does_not(self):
        bad = dl.stop_retirement_items(_ep012(), _articles())
        # The note quotes the sentence that makes the claim.
        assert len(bad) == 2
        assert any("single collision" in b for b in bad)    # Dorange's item
        assert any("mechanical issues" in b for b in bad)   # Marchand's item
        assert not any("withdrew" in b for b in bad)        # Ruyant: the source says "renoncé"

    def test_unread_source_is_not_judged(self):
        arts = [dict(a, full_text="", description="", title="") for a in _articles()]
        assert dl.stop_retirement_items(_ep012(), arts) == []

    def test_retirement_the_source_reports_passes(self):
        arts = _articles()
        arts[0]["full_text"] += " Le 4 novembre, il a pris la décision de renoncer."
        bad = dl.stop_retirement_items(_ep012(), arts)
        assert not any("mechanical issues" in b for b in bad)

    def test_prompt_vocabulary(self):
        digest = (PROMPTS / "offshore_north_digest.txt").read_text(encoding="utf-8")
        assert "RACE STATUS IS THE SOURCE'S WORD" in digest
        assert "contraint de stopper" in digest


# ---------------------------------------------------------------------------
# 3. A preview is not coverage
# ---------------------------------------------------------------------------

class TestPreviewToldAsResult:
    def test_ep012_video_item_fires(self):
        bad = dl.preview_result_items(_ep012(), _articles())
        assert len(bad) == 1
        subject, date = bad[0]
        assert "31 October" in subject or "YouTube" in subject
        assert date == "1 November 2026"

    def test_forward_looking_sentence_passes(self):
        digest = ("## The Canadian Boat\n"
                  "Canada Ocean Racing, 31 October: Scott previews the race, which starts "
                  "on 1 November from Saint-Malo. Source: [youtube.com](" + VIDEO_URL + ")\n")
        assert dl.preview_result_items(digest, _articles()) == []


# ---------------------------------------------------------------------------
# 4. Every number has a source
# ---------------------------------------------------------------------------

class TestFiguresSourced:
    def test_ep012_plain_sailing_fires(self):
        bad = dl.explainer_unsourced_amounts(_ep012())
        assert "four and five million" in bad
        assert "nine to ten percent" in bad

    def test_sourced_explainer_passes(self):
        digest = ("## Plain Sailing\nA campaign runs four to five million euros a year. "
                  "Source: [lequipe.fr](https://www.lequipe.fr/x)\n")
        assert dl.explainer_unsourced_amounts(digest) == []

    def test_ep012_115_boats_fires(self):
        ref = (PROMPTS / "offshore_north_field_guide.txt").read_text(encoding="utf-8")
        missing = dl.item_unsourced_figures(_ep012(), {"articles": _articles(), "reference_text": ref})
        assert "115" in missing
        assert "2027" not in missing  # a year
        assert "1" not in missing     # a day of the month
        assert "4" not in missing     # "Ultim 4" is a name

    def test_briefing_figures_pass(self):
        digest = ("### The Fleet\nThe race has 118 skippers. Source: [x](https://example.com/a)\n")
        ref = "118 solo skippers"
        assert dl.item_unsourced_figures(digest, {"articles": _articles(), "reference_text": ref}) == []

    def test_nothing_read_is_silent(self):
        assert dl.item_unsourced_figures(_ep012(), {"articles": []}) is None


# ---------------------------------------------------------------------------
# 5. The record: race status and Alan Roberts
# ---------------------------------------------------------------------------

class TestRecord:
    def _facts(self) -> str:
        return (PROMPTS / "offshore_north_standing_facts.txt").read_text(encoding="utf-8")

    def test_race_record_is_dated(self):
        facts = self._facts()
        assert "## The 2026 Route du Rhum — the race record" in facts
        assert "3 December 2026" in facts
        assert "contraint de stopper" in facts
        assert "On 4 November" in facts and "On 6 November" in facts
        assert "Ep006 led with it" in facts

    def test_roberts_named_with_every_rorc_mention(self):
        facts = self._facts()
        assert "Whenever an episode mentions the RORC Transatlantic" in facts
        assert "class win" in facts
        pod = (PROMPTS / "offshore_north_podcast.txt").read_text(encoding="utf-8")
        assert "Whenever the RORC Transatlantic is mentioned, Alan Roberts is named" in pod

    def test_standing_corrections_list_ep012(self):
        facts = self._facts()
        for s in ("Ep012 (2 Nov 2026) led with old news", "Ep012 called stopped skippers",
                  "Ep012 told the team's 31 October video", "Ep012 aired unsourced numbers",
                  "Ep012 mentioned the RORC Transatlantic"):
            assert s in facts

    def test_field_guide_finish_line(self):
        guide = (PROMPTS / "offshore_north_field_guide.txt").read_text(encoding="utf-8")
        assert "The finish line closes on 3 December 2026" in guide
