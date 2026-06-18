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
        # Recalibrated 1700 -> 1300 after Ep2 skipped on a thin day (grok-4.3
        # plateau + digest ceiling); the Engineering Deep Dive length lever
        # is the quality-preserving fix in the podcast prompt.
        assert cfg.llm.min_podcast_words == 1300
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


class TestClosingBeforeMarketWatch:
    """The code-supplied closing block appends the SPCX price, which the
    Market Watch pattern also matches. Closing MUST be listed before Market
    Watch so it wins the sign-off line — otherwise weekly-recap episodes
    (no separate Market Watch segment) ship with the sign-off mis-titled
    'Market Watch' and NO Closing chapter (Ep3 2026-06-14 orphan-closing)."""

    def test_closing_listed_before_market_watch(self):
        titles = [m["title"] for m in _spacex_markers()]
        assert titles.index("Closing") < titles.index("Market Watch"), (
            "Closing must precede Market Watch so the price-carrying sign-off "
            "line is titled Closing, not Market Watch"
        )

    def test_recap_signoff_with_price_gets_closing_chapter(self):
        # Weekly-recap shape: no separate Market Watch segment; the closing
        # carries the SPCX price (the exact Ep3 failure).
        script = (
            "Welcome to SpaceX Daily, episode 3. Let's get into it.\n\n"
            "From an engineering standpoint, the booster catch geometry is "
            "the whole game this week.\n\n"
            "Before we go, the static-fire attempt is the item to watch next week.\n\n"
            "And that's a wrap on today's SpaceX developments. S P C X closed "
            "at one hundred sixty dollars and ninety-five cents. See you next time."
        )
        titles = [c.title for c in parse_chapters(
            script, _spacex_markers(), show_name="SpaceX Daily")]
        assert "Closing" in titles, titles
        assert "Market Watch" not in titles, (
            "no Market Watch segment in a recap — the price-only sign-off must "
            f"not create a spurious Market Watch chapter: {titles}")

    def test_daily_keeps_both_market_watch_and_closing(self):
        # Daily shape: a real Market Watch segment AND a price-carrying close.
        script = (
            "Welcome to SpaceX Daily. Let's get into today's developments.\n\n"
            "From an engineering standpoint, Raptor 3's plumbing is the story.\n\n"
            "And a quick market note: S P C X is at two hundred one dollars, "
            "down two percent.\n\n"
            "That's a wrap on today's SpaceX developments. S P C X is trading "
            "at two hundred one dollars, down two percent. See you tomorrow."
        )
        titles = [c.title for c in parse_chapters(
            script, _spacex_markers(), show_name="SpaceX Daily")]
        assert "Market Watch" in titles and "Closing" in titles, titles


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
        # The system + podcast prompts must state the SAME length window
        # (the contradictory-length class every June 2026 review fixed).
        # Recalibrated to 11-14 min after the Ep2 thin-day skip.
        system = (_ROOT / "shows/prompts/spacex_system.txt").read_text(encoding="utf-8")
        assert "11–14 minutes" in system
        assert "10-12" not in system and "10–12" not in system and "12–14" not in system


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
        # June 2026 rebalance: lively/engineering-forward by DEFAULT, with
        # only a mild stock flavor — energy never hinges on the ticker.
        from shows.hooks.spacex import _tone_from_change
        for args in [(161.0, "+19.2%"), (150.0, "-3.1%"), (0.0, "")]:
            assert "energy" in _tone_from_change(*args).lower()
        assert "upbeat" in _tone_from_change(161.0, "+19.2%")
        assert "down market day" in _tone_from_change(150.0, "-3.1%")

    def test_spcx_ticker_letter_spelled_for_tts(self):
        pron = yaml.safe_load(
            (_ROOT / "shows/pronunciation_map.yaml").read_text(encoding="utf-8")
        )
        assert pron["corrections"].get("SPCX") == "S P C X"

    def test_tf_thrust_unit_expanded_for_tts(self):
        """Ep2 lesson: "thrust now exceeds 280 tf" was spoken as "280 T F"
        (Whisper transcribed letters, twice). The hook's pronunciation
        override expands the rocket-thrust unit so it reads as a unit, not
        spelled letters. A unit expansion (km→kilometers class), NOT a
        phonetic respelling (landmine #17)."""
        from shows.hooks.spacex import pronunciation_overrides
        from assets.pronunciation import prepare_text_for_tts

        ov = pronunciation_overrides()
        assert ov["extra_words"]["tf"] == "tons-force"
        out = prepare_text_for_tts(
            "Thrust now exceeds 280 tf today.",
            extra_words=ov["extra_words"],
        )
        assert "tons-force" in out
        assert "280 tf " not in out + " "
        # Must not maul real words that merely contain the letters.
        assert "software" in prepare_text_for_tts(
            "the software shipped", extra_words=ov["extra_words"])


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


class TestLaunchDashboard:
    """SpaceX Launch Dashboard data + page."""

    def test_fetcher_pure_helpers(self):
        import importlib.util, datetime as dt
        spec = importlib.util.spec_from_file_location(
            "fetch_spacex_launches", _ROOT / "scripts" / "fetch_spacex_launches.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # _slim_launch reduces a raw record
        raw = {
            "id": "x", "name": "Falcon 9 | Starlink", "net": "2026-06-15T14:00:00Z",
            "status": {"abbrev": "Go", "name": "Go for Launch"},
            "rocket": {"configuration": {"name": "Falcon 9"}},
            "pad": {"name": "SLC-40", "location": {"name": "Cape Canaveral"}},
            "mission": {"name": "Starlink", "description": "d"},
            "launch_service_provider": {"id": 121, "name": "SpaceX"},
        }
        slim = mod._slim_launch(raw)
        assert slim["rocket"] == "Falcon 9" and slim["pad"] == "SLC-40"
        assert mod._is_spacex(raw) is True
        assert mod._is_spacex({"launch_service_provider": {"id": 1}}) is False
        # cadence: 12 month buckets, counts by YYYY-MM
        now = dt.datetime(2026, 6, 13, tzinfo=dt.timezone.utc)
        prev = [{"net": "2026-06-01T00:00:00Z"}, {"net": "2026-06-10T00:00:00Z"},
                {"net": "2026-05-02T00:00:00Z"}]
        cad = mod._monthly_cadence(prev)
        assert len(cad) == 12
        assert cad[-1] == {"month": "2026-06", "count": 2}
        # stats
        st = mod._stats(prev, now)
        assert st["launches_ytd"] == 3
        assert st["launches_last_30d"] >= 2

    def test_dashboard_page_renders(self):
        import generate_html as g
        g.generate_spacex_dashboard(dry_run=True)  # smoke

    def test_dashboard_in_sitemap_and_show_page_links_it(self):
        import generate_html as g
        # show page hero links the dashboard
        html = (_ROOT / "spacex.html").read_text(encoding="utf-8") if (_ROOT / "spacex.html").exists() else ""
        if html:
            assert "spacex-dashboard.html" in html


class TestComprehensiveCoverageAndAISection:
    """June 13 2026: broaden coverage to the whole SpaceX business + a
    dedicated AI section (SpaceX↔xAI/Grok/X), per operator direction."""

    def test_keywords_cover_business_breadth_and_ai(self):
        cfg = yaml.safe_load((_ROOT / "shows/spacex.yaml").read_text(encoding="utf-8"))
        kw = {k.lower() for k in cfg["keywords"]}
        for needed in ("xai", "grok", "raptor", "starship", "starlink",
                       "gigabay", "ai satellite", "orbital data center"):
            assert needed in kw, needed

    def test_ai_x_accounts_present(self):
        cfg = yaml.safe_load((_ROOT / "shows/spacex.yaml").read_text(encoding="utf-8"))
        handles = {a["handle"].lower() for a in cfg["x_accounts"]}
        assert "xai" in handles and "grok" in handles

    def test_digest_and_podcast_have_ai_section(self):
        digest = (_ROOT / "shows/prompts/spacex_digest.txt").read_text(encoding="utf-8")
        podcast = (_ROOT / "shows/prompts/spacex_podcast.txt").read_text(encoding="utf-8")
        assert "### AI & Compute" in digest
        assert "AI & Compute" in podcast and "On the AI front" in podcast
        # business-breadth instruction present
        assert "COVER THE WHOLE BUSINESS" in digest

    def test_ai_chapter_marker_and_tracker(self):
        cfg = yaml.safe_load((_ROOT / "shows/spacex.yaml").read_text(encoding="utf-8"))
        titles = {m["title"] for m in cfg["chapters"]["section_markers"]}
        assert "AI & Compute" in titles
        from engine.content_tracker import SPACEX_SECTION_PATTERNS
        assert "ai_compute" in SPACEX_SECTION_PATTERNS

    def test_ai_section_chapter_parses(self):
        # The marker must match BOTH "AI" and the post-pronunciation "A I"
        # form (the TTS layer spaces acronyms) — Ep2 shipped the AI segment
        # with no chapter because the marker only knew "ai".
        for ai in ("AI", "A I"):
            script = "\n".join([
                "Hey, welcome to SpaceX Daily, episode five. I'm Patrick in Vancouver.",
                "Here's what's happening at SpaceX today.",
                *[f"Body sentence {i} with launch detail." for i in range(20)],
                "One thing worth watching is the FAA timeline.",
                f"On the {ai} front, the orbital data center plan ties into the compute push.",
                "From an engineering standpoint, reuse drives the cost curve.",
                "Before we go, watch the static fire window.",
                "That's a wrap on today's SpaceX developments. See you tomorrow.",
            ])
            chapters = parse_chapters(script, _spacex_markers(), show_name="SpaceX Daily")
            titles = [c.title for c in chapters]
            assert "AI & Compute" in titles, (ai, titles)


class TestResourcesAndDashboardStatsExpansion:
    """June 13 2026: xAI/Cursor/partnership resources + dashboard fleet stats."""

    def test_resources_include_xai_cursor_partnerships(self):
        import generate_html as g
        cats = {c["title"]: c for c in g.NETWORK_SHOWS["spacex"]["resource_categories"]}
        ai = next((c for t, c in cats.items() if "AI" in t and "Compute" in t), None)
        assert ai, list(cats)
        names = {r["name"] for r in ai["resources"]}
        assert "Cursor" in names and any("xAI" in n for n in names)
        assert "Partnerships & Customers" in cats
        part_names = {r["name"] for r in cats["Partnerships & Customers"]["resources"]}
        assert any("NASA" in n for n in part_names)
        for c in g.NETWORK_SHOWS["spacex"]["resource_categories"]:
            for r in c["resources"]:
                assert r["url"].startswith("https://"), r

    def test_fleet_payload_computes(self):
        import importlib.util, datetime as dt
        spec = importlib.util.spec_from_file_location(
            "fetch_spacex_launches", _ROOT / "scripts" / "fetch_spacex_launches.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        now = dt.datetime(2026, 6, 13, tzinfo=dt.timezone.utc)
        prev = [
            {"net": "2026-06-01T00:00:00Z", "rocket": "Falcon 9", "name": "Starlink Group 1-1", "status": "Success"},
            {"net": "2026-05-20T00:00:00Z", "rocket": "Falcon 9", "name": "NROL-1", "status": "Success"},
            {"net": "2026-04-10T00:00:00Z", "rocket": "Falcon Heavy", "name": "USSF-1", "status": "Success"},
            {"net": "2026-03-01T00:00:00Z", "rocket": "Starship", "name": "Flight 12", "status": "Failure"},
        ]
        f = mod._fleet_payload(prev, now)
        assert f["by_vehicle"]["Falcon 9"] == 2
        assert f["starlink_launches"] == 1
        assert f["est_satellites_deployed"] == 23  # 1 starlink x 23
        # mass: F9 starlink 17 + F9 other 9 + FH 26 + starship 0 = 52
        assert f["est_mass_to_orbit_tonnes"] == 52
        assert f["success_rate_pct"] == 75.0  # 3/4
        assert f["estimated"] is True


class TestGrowingMetricsDataset:
    """June 13 2026: mass-to-orbit chart + a growing metrics time-series;
    the dashboard's AI 'Musk stack' card moved to the show page."""

    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fetch_spacex_launches", _ROOT / "scripts" / "fetch_spacex_launches.py")
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m

    def test_monthly_breakdown_has_mass_and_sats(self):
        import datetime as dt
        mod = self._mod()
        now = dt.datetime.now(dt.timezone.utc)
        ym = now.strftime("%Y-%m")
        prev = [{"net": f"{ym}-01T00:00:00Z", "rocket": "Falcon 9", "name": "Starlink Group 1-1", "status": "Success"}]
        mb = mod._monthly_breakdown(prev)
        assert len(mb) == 12
        last = mb[-1]
        assert last["month"] == ym
        assert last["launches"] == 1 and last["satellites"] == 23 and last["mass_t"] == 17

    def test_timeseries_accumulates(self, tmp_path):
        import datetime as dt
        mod = self._mod()
        now = dt.datetime.now(dt.timezone.utc)
        path = tmp_path / "spacex_metrics.json"
        # seed an old month that must survive a refresh of the recent window
        path.write_text('{"months": {"2020-01": {"launches": 5, "mass_t": 80, "satellites": 100, "vehicles": {}}}}')
        mb = mod._monthly_breakdown([{"net": now.strftime("%Y-%m") + "-01T00:00:00Z",
                                      "rocket": "Falcon 9", "name": "Starlink", "status": "Success"}])
        cum, series = mod._update_metrics_timeseries(mb, now, path=path)
        assert isinstance(series, list) and series and "total" in series[-1]
        import json
        data = json.loads(path.read_text())
        assert "2020-01" in data["months"], "old month must persist"
        assert now.strftime("%Y-%m") in data["months"]
        assert cum >= 100  # cumulative includes the seeded old month

    def test_dashboard_has_mass_chart_no_ai_card(self):
        tmpl = (_ROOT / "templates/spacex_dashboard.html.j2").read_text(encoding="utf-8")
        assert 'id="spxMass"' in tmpl
        assert "Mass to orbit" in tmpl
        assert "the Musk stack" not in tmpl  # AI card removed from dashboard

    def test_show_narrative_mentions_ai_compute(self):
        import yaml as y
        meta = y.safe_load((_ROOT / "shows/network_meta.yaml").read_text(encoding="utf-8"))
        about = meta["spacex"]["about_text"].lower()
        assert "ai" in about and ("xai" in about or "compute" in about)


class TestDashboardV2Visuals:
    """June 13 2026 dashboard build-out: cumulative growth area chart,
    recently-flown panel, vehicle-mix segmented bar, animated count-ups."""

    def test_dashboard_template_has_new_panels(self):
        t = (_ROOT / "templates/spacex_dashboard.html.j2").read_text(encoding="utf-8")
        for needle in ('id="spxArea"', 'id="spxRecent"', "Constellation growth",
                       "Recently flown", "function renderArea", "function renderRecent",
                       "function countUp", "spx-mixbar"):
            assert needle in t, needle

    def test_payload_exposes_growth_and_recent(self):
        # _monthly_breakdown + timeseries feed the cumulative series the
        # area chart reads; recent list feeds the recently-flown panel.
        import importlib.util, datetime as dt
        spec = importlib.util.spec_from_file_location(
            "fetch_spacex_launches", _ROOT / "scripts" / "fetch_spacex_launches.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        import tempfile, pathlib
        now = dt.datetime.now(dt.timezone.utc)
        mb = mod._monthly_breakdown([
            {"net": now.strftime("%Y-%m") + "-01T00:00:00Z", "rocket": "Falcon 9",
             "name": "Starlink", "status": "Success"}])
        with tempfile.TemporaryDirectory() as d:
            cum, series = mod._update_metrics_timeseries(
                mb, now, path=pathlib.Path(d) / "m.json")
        assert series and series[-1]["total"] == cum
