"""Oct 5 2026 slate review — guards for what the Monday slate exposed.

* Omni View's grok-4.7 script override never ran: the credit files show
  grok-4.3 served the script on all 14 episodes from 09-22 (Ep183-196),
  every 4.7 call timing out, while ``llm_script_model`` recorded the
  CONFIGURED model. The served model and any fallback are recorded now,
  and the show is back on grok-4.6.
* Nerra Daily Ep046's sign-off aired "When I phone people for The Age of
  AI" — the links prompt and the reflection rotation both still said Mira
  phones guests, five sites in all, past a guard that swept only the promo
  rotation.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_TEMPLATE_VARS = {
    "episode_num": 50, "digest": "body", "today_str": "x", "hook": "h",
    "intro_line": "i", "closing_block": "c", "tone_hint": "t",
    "cold_open_spec": "", "delivery_spec": "", "narrative_memory_section": "",
    "nerra_network_context": "", "tesla_narrative_status_block": "",
    "tesla_performance_signals_block": "", "tesla_theme_context_block": "",
}


def _tesla_config(podcast_model: str):
    from engine.config import load_config
    cfg = load_config(ROOT / "shows" / "tesla.yaml")
    cfg.llm.podcast_model = podcast_model
    cfg.llm.podcast_chain = False
    return cfg


class TestScriptModelIsTheServedOne:
    def test_a_failed_override_records_the_fallback(self, monkeypatch):
        from engine import generator
        cfg = _tesla_config("grok-4.7")
        seen = []

        def _fake_call(prompt, model=None, **kwargs):
            seen.append(model)
            if model == "grok-4.7":
                raise TimeoutError("Request timed out.")
            return "word " * 500, {"finish_reason": "stop"}

        monkeypatch.setattr(generator, "_call_grok", _fake_call)
        monkeypatch.setattr(generator, "_validate_llm_output", lambda *a, **k: 0)
        generator.generate_podcast_script(dict(_TEMPLATE_VARS), cfg)
        assert seen[0] == "grok-4.7" and seen[-1] == cfg.llm.model
        assert cfg.llm._script_model_served == cfg.llm.model
        assert cfg.llm._script_model_fallback.startswith("grok-4.7 -> ")
        assert "TimeoutError" in cfg.llm._script_model_fallback

    def test_a_working_override_is_recorded_as_served(self, monkeypatch):
        from engine import generator
        cfg = _tesla_config("grok-4.6")
        monkeypatch.setattr(generator, "_call_grok",
                            lambda prompt, model=None, **k: ("word " * 500, {"finish_reason": "stop"}))
        monkeypatch.setattr(generator, "_validate_llm_output", lambda *a, **k: 0)
        generator.generate_podcast_script(dict(_TEMPLATE_VARS), cfg)
        assert cfg.llm._script_model_served == "grok-4.6"
        assert not getattr(cfg.llm, "_script_model_fallback", "")

    def test_run_show_records_the_served_model_and_the_fallback(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        i = src.index('"llm_script_model",')
        assert "_script_model_served" in src[i:i + 300]
        assert 'metrics.record("llm_script_model_fallback"' in src


class TestOmniViewScriptStage:
    def test_omni_view_is_back_on_the_model_that_served(self):
        from engine.config import load_config
        cfg = load_config(ROOT / "shows" / "omni_view.yaml")
        assert cfg.llm.podcast_model == "grok-4.6"
        assert cfg.llm.model == "grok-4.3"


# Phrases that describe The Age of AI as a phone-call show. The studio room
# has been the default since 2026-09-09 and the phone is the fallback; an
# accurate mention of the phone AS the fallback is fine and not matched.
_PHONE_CLAIM = re.compile(
    r"\bphones? real people\b|\bphone (?:real )?people\b|"
    r"interviewed live over the phone",
    re.IGNORECASE,
)


def _code_text(path: Path) -> str:
    """Source without comment lines — a comment recording the history of
    the claim is not a surface."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(ln for ln in lines if not ln.lstrip().startswith("#"))


class TestNoSurfaceSaysMiraPhonesGuests:
    def test_prompts(self):
        hits = [p.name for p in sorted((ROOT / "shows" / "prompts").rglob("*.txt"))
                if _PHONE_CLAIM.search(p.read_text(encoding="utf-8"))]
        assert not hits, hits

    def test_registry_and_edition_code(self):
        for rel in ("shows/network_meta.yaml", "engine/daily_edition.py",
                    "engine/brand.py", "engine/network_promo.py",
                    "engine/personal_edition.py", "generate_html.py"):
            path = ROOT / rel
            if path.exists():
                assert not _PHONE_CLAIM.search(_code_text(path)), rel

    def test_templates(self):
        hits = [p.name for p in sorted((ROOT / "templates").glob("*.j2"))
                if _PHONE_CLAIM.search(p.read_text(encoding="utf-8"))]
        assert not hits, hits

    def test_the_guard_matches_what_aired(self):
        assert _PHONE_CLAIM.search("where she, an AI, phones real people")
        assert _PHONE_CLAIM.search("When I phone people for The Age of AI")
        assert not _PHONE_CLAIM.search(
            "join from a studio link in their browser, or by phone if they prefer")


class TestPageDatesReadWhatThePagePrints:
    """Offshore North Ep008 aired IMOCA's February Charal refit story as this
    week's news: the page carries no meta date, prints "2/10/26" (US order)
    under its headline, and xAI's search read it as 2 October."""

    IMOCA = ('<h1 class="Article-title">Charal: A massive refit</h1>'
             '<div class="Subtitle Subtitle--left"> 2/10/26 <div class="tag">Skipper</div></div>'
             '<span class="Card-surtitle-date">10.1.26</span>')

    def test_imoca_header_date_is_month_first(self):
        from engine.article_text import extract_published_date
        d = extract_published_date(self.IMOCA, "https://www.imoca.org/en/news/news/charal")
        assert (d.year, d.month, d.day) == (2026, 2, 10)

    def test_a_numeric_date_needs_a_known_publisher(self):
        from engine.article_text import extract_published_date
        assert extract_published_date(self.IMOCA, "https://example.com/x") is None

    def test_arxiv_and_sciencedaily_labels(self):
        from engine.article_text import extract_published_date
        d = extract_published_date('<div class="dateline">[Submitted on 1 Oct 2026 (v1)]</div>')
        assert (d.month, d.day) == (10, 1)
        d = extract_published_date('<dt>Date:</dt>\n\t<dd id="date_posted">October 4, 2026</dd>')
        assert (d.month, d.day) == (10, 4)

    def test_an_update_date_is_not_a_publish_date(self):
        from engine.article_text import extract_published_date
        assert extract_published_date("<p>Updated: October 4, 2026</p>") is None

    def test_structured_dates_past_200k_characters_are_read(self):
        from engine.article_text import extract_published_date
        html = "<div>" + "x" * 300_000 + '</div><time datetime="2026-10-05T07:00:00.425-03:00">'
        d = extract_published_date(html)
        assert (d.month, d.day, d.hour) == (10, 5, 10)

    def test_structured_fields_still_win(self):
        from engine.article_text import extract_published_date
        html = ('<meta property="article:published_time" content="2026-09-30T08:00:00Z">'
                "<p>Published: October 4, 2026</p>")
        assert extract_published_date(html).day == 30

    def test_the_probe_passes_the_url(self):
        src = (ROOT / "engine" / "article_dates.py").read_text(encoding="utf-8")
        assert 'extract_published_date(html, art.get("url", ""))' in src


class TestNewsletterEyebrowContrast:
    """Финансы Просто's newsletter was refused by the contrast check on every
    episode since at least Ep079: its brand_color_dark (#DB2777) was LIGHTER
    than its brand colour and read 4.39:1 on the #f8fafc card, while the
    template's own comment says every dark variant clears 5.5:1."""

    @staticmethod
    def _lum(hex_color):
        h = hex_color.lstrip("#")
        rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    def test_every_show_eyebrow_clears_aa_on_the_card(self):
        import generate_html
        card = self._lum("#f8fafc")
        bad = {}
        for slug, cfg in generate_html.NETWORK_SHOWS.items():
            colour = cfg.get("brand_color_dark") or cfg.get("brand_color")
            if not colour:
                continue
            ratio = (card + 0.05) / (self._lum(colour) + 0.05)
            if ratio < 4.5:
                bad[slug] = (colour, round(ratio, 2))
        assert not bad, bad


class TestMitUnpricedPicks:
    """Ep150's HPS.A (TSX class A) went to Yahoo verbatim, 404'd every day
    and sat open for forty days on a one-session horizon; Ep186's BMWYY has
    no Yahoo data at all. Neither could ever close or enter any record."""

    def test_share_classes_map_to_yahoo_form(self):
        from shows.hooks.modern_investing import _yf_symbol_candidates as c
        assert c("HPS.A", "TSX") == ["HPS-A.TO", "HPS.A"]
        assert c("BAM.A", "TSX-V")[0] == "BAM-A.V"
        assert c("BRK.B", "NYSE") == ["BRK-B", "BRK.B"]
        # Exchange suffixes and plain symbols are untouched.
        assert c("CNR.TO", "TSX") == ["CNR.TO"]
        assert c("VOD.L", "") == ["VOD.L"]
        assert c("CNR", "TSX") == ["CNR.TO", "CNR"]

    def _run(self, monkeypatch, pick_date, bars):
        import shows.hooks.modern_investing as mit
        trade = {"symbol": "BMWYY", "status": "open", "trade_type": "weekly",
                 "date": pick_date.isoformat(), "episode_num": 186}
        tracker = {"trades": [trade]}
        monkeypatch.setattr(mit, "_fetch_bars_for_trade", lambda t, **k: bars)
        monkeypatch.setattr(mit, "_snapshot_trade", lambda t, s: None)
        monkeypatch.setattr(mit, "_recompute_summary", lambda t: None)
        monkeypatch.setattr(mit, "_maybe_record_monthly_snapshot", lambda t, d: None)
        monkeypatch.setattr(mit, "_save_tracker", lambda t, p: None)
        mit._evaluate_open_trade(tracker, None)
        return trade

    def test_a_pick_with_no_bars_for_two_weeks_is_voided(self, monkeypatch):
        import datetime
        trade = self._run(monkeypatch, datetime.date.today() - datetime.timedelta(days=20), [])
        assert trade["status"] == "voided"
        assert trade["void_reason"] == "market_data_unavailable"

    def test_a_fresh_unpriced_pick_still_holds(self, monkeypatch):
        import datetime
        trade = self._run(monkeypatch, datetime.date.today() - datetime.timedelta(days=3), [])
        assert trade["status"] == "open"


class TestEnvIntelThinDays:
    """Env Intel Ep071 (a thin Monday) used the prompt's own low-content
    format, failed the validator for having no "Lead Story" heading, spent
    its structural regeneration, then narrated three empty sections for
    ~200 words."""

    DIGEST = ("**HOOK:** BC funds industrial emissions cuts.\n\n━━━━\n"
              "### Deep Dive: BC Industrial Emissions Funding\n"
              "1. **BC funds cuts: Energi**\nThe province is directing funds to industry. Source: x\n\n"
              "━━━━\n### Regulatory Calendar — Next 30 Days\n- Oct 20: comment period closes\n")

    def test_the_low_content_deep_dive_counts_as_the_lead(self):
        from engine import validation as v
        _ok, issues, _ = v.validate_digest(self.DIGEST, v.ei_validation_config())
        assert not any("Lead Story" in i for i in issues), issues

    def test_the_absence_filter_is_on_for_env_intel_and_offshore_north(self):
        from engine.config import load_config
        for slug in ("env_intel", "offshore_north"):
            assert load_config(ROOT / "shows" / f"{slug}.yaml").absence_sentence_filter is True

    def test_the_prompt_leaves_an_empty_section_out(self):
        text = (ROOT / "shows" / "prompts" / "env_intel_digest.txt").read_text(encoding="utf-8")
        assert "a section with no qualifying item is LEFT OUT" in text
        assert "The Compliance Brief is still required in this format" in text


class TestReviewHardening:
    def test_a_future_labelled_date_is_not_a_publish_date(self):
        from engine.article_text import extract_published_date
        assert extract_published_date("<p>Date: November 1, 2099</p>") is None

    def test_an_option_or_a_priced_pick_is_never_voided_for_a_missing_day(self, monkeypatch):
        import datetime
        import shows.hooks.modern_investing as mit
        old = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        trades = [
            {"symbol": "AAA", "status": "open", "date": old, "option": {"expiry": "2099-01-01"}},
            {"symbol": "BBB", "status": "open", "date": old, "pick_reference_price": 12.5},
        ]
        monkeypatch.setattr(mit, "_fetch_bars_for_trade", lambda t, **k: [])
        monkeypatch.setattr(mit, "_snapshot_trade", lambda t, s: None)
        monkeypatch.setattr(mit, "_recompute_summary", lambda t: None)
        monkeypatch.setattr(mit, "_maybe_record_monthly_snapshot", lambda t, d: None)
        monkeypatch.setattr(mit, "_save_tracker", lambda t, p: None)
        mit._evaluate_open_trade({"trades": trades}, None)
        assert [t["status"] for t in trades] == ["open", "open"]


class TestLateEvaluatedPicksPriceTheirOwnWindow:
    def test_the_fetch_window_reaches_the_pick(self):
        import datetime
        from shows.hooks.modern_investing import _period_covering
        today = datetime.date.today()
        assert _period_covering(today - datetime.timedelta(days=3)) == "15d"
        assert _period_covering(today - datetime.timedelta(days=40)) == "3mo"
        assert _period_covering(None) == "15d"

    def test_a_bar_weeks_after_the_pick_is_never_priced(self):
        import datetime
        import shows.hooks.modern_investing as mit
        pick = datetime.date.today() - datetime.timedelta(days=9)
        late = [(pick + datetime.timedelta(days=8), 236.4, 231.1, 230.2)]
        trade = {"symbol": "HPS.A", "market": "TSX", "status": "open",
                 "trade_type": "flash", "date": pick.isoformat()}
        mit._close_trade(trade, {"trades": [trade]}, bars=late)
        assert trade["status"] == "open" and trade.get("entry_price") is None

    def test_a_listing_that_never_traded_after_the_pick_voids(self):
        import datetime
        import shows.hooks.modern_investing as mit
        pick = datetime.date.today() - datetime.timedelta(days=30)
        late = [(pick + datetime.timedelta(days=20), 236.4, 231.1, 230.2)]
        trade = {"symbol": "HALT", "market": "NYSE", "status": "open",
                 "trade_type": "flash", "date": pick.isoformat()}
        mit._close_trade(trade, {"trades": [trade]}, bars=late)
        assert trade["status"] == "voided"
        assert trade["void_reason"] == "no_trading_data_after_pick"
        assert trade.get("entry_price") is None
