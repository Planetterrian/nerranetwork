"""Drift guards for Nerra Personal (accounts + personalized feeds +
support surface).

Pins: spec validation (the closed show vocabulary and token/name/city
trust boundary), the private-feed XML contract (deterministic GUIDs,
Worker-gated enclosures, itunes:block), the prune depth, the honest
local-brief contract, the Worker/engine vocabulary sync, page + prompt
registration, and the funding-tag repoint.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from engine.daily_edition import EDITIONS, Segment
from engine.personal_edition import (
    PERSONAL_FEED_MAX_EPISODES,
    PERSONAL_SHOW_SLUGS,
    PersonalSpec,
    build_personal_feed_xml,
    chapters_filename_for,
    build_personal_links_prompt,
    fallback_personal_links,
    format_weather_line,
    parse_local_brief,
    personal_episode_title,
    prune_episode_state,
    validate_spec,
)

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "ab" * 16


def _segment(slug="spacex", name="SpaceX Daily", n=76):
    return Segment(
        slug=slug, show_name=name, episode_num=n,
        episode_title=f"Ep {n}: A hook for {name}", hook=f"A hook for {name}",
        date="2026-08-21", audio_url="", content="Body text. " * 30,
        digest_dir=Path("."), transcript_path=None, music_intro_offset=0.0)


class TestSpecValidation:
    def test_happy_path_preserves_user_order(self):
        spec = validate_spec({
            "token": TOKEN,
            "shows": ["dp_pod", "spacex", "tesla"],
            "tier": "personal_local",
            "first_name": "Sam", "city": "Vancouver",
        })
        assert spec is not None
        assert spec.shows == ["dp_pod", "spacex", "tesla"]  # THEIR order
        assert spec.tier == "personal_local"

    def test_unknown_shows_dropped_never_guessed(self):
        spec = validate_spec({
            "token": TOKEN,
            "shows": ["tesla", "not_a_show", "spacex", "tesla"],
        })
        assert spec is not None
        assert spec.shows == ["tesla", "spacex"]

    def test_too_few_shows_rejected(self):
        assert validate_spec({"token": TOKEN, "shows": ["tesla"]}) is None

    def test_bad_token_rejected(self):
        assert validate_spec({"token": "../evil", "shows": ["tesla", "spacex"]}) is None
        assert validate_spec({"token": "ZZZZ" * 8, "shows": ["tesla", "spacex"]}) is None

    def test_hostile_name_dropped_city_capped(self):
        spec = validate_spec({
            "token": TOKEN, "shows": ["tesla", "spacex"],
            "first_name": "<script>x</script>", "city": "y" * 500,
        })
        assert spec is not None
        assert spec.first_name == ""
        assert len(spec.city) == 80

    def test_vocabulary_is_the_en_lineup(self):
        assert PERSONAL_SHOW_SLUGS == EDITIONS["en"].lineup

    def test_worker_vocabulary_stays_in_sync(self):
        # The Worker validates preferences against its own copy of the
        # closed set — a drift means saved lineups silently lose shows.
        ts = (ROOT / "workers" / "gallery" / "src" / "personal.ts"
              ).read_text(encoding="utf-8")
        for slug in PERSONAL_SHOW_SLUGS:
            assert f'"{slug}"' in ts, f"{slug} missing from worker PERSONAL_SHOWS"


class TestPersonalFeed:
    def _spec(self):
        return PersonalSpec(token=TOKEN, shows=["spacex", "tesla"],
                            first_name="Sam")

    def _episodes(self, n=2):
        return [{
            "episode_num": i, "date": f"2026-08-{10 + i:02d}",
            "title": f"Edition {i}", "description": "d",
            "filename": f"Nerra_Personal_202608{10 + i:02d}.mp3",
            "duration_seconds": 3000, "bytes": 1000,
        } for i in range(1, n + 1)]

    def test_feed_contract(self):
        xml = build_personal_feed_xml(self._spec(), self._episodes())
        # Worker-gated enclosures: revocable, never a public bucket URL.
        assert "https://api.nerranetwork.com/api/feed/" + TOKEN in xml
        # Deterministic GUIDs — rebuilds never re-notify podcast apps.
        assert f"personal-{TOKEN[:8]}-ep002-20260812" in xml
        # Private: directories must never index a personal feed.
        assert "<itunes:block>yes</itunes:block>" in xml
        assert "Sam's Nerra Daily" in xml

    def test_feed_advertises_chapters(self):
        # The builder uploads chapters_YYYYMMDD.json beside every edition;
        # the first paid subscriber's feed (2026-09-06) never pointed at
        # it, so apps showed one flat 24-minute block. Every item must
        # carry a Podcasting 2.0 tag at the Worker-gated URL.
        xml = build_personal_feed_xml(self._spec(), self._episodes())
        assert 'xmlns:podcast="https://podcastindex.org/namespace/1.0"' in xml
        assert xml.count("<podcast:chapters") == 2
        assert (f'url="https://api.nerranetwork.com/api/feed/{TOKEN}/'
                f'chapters_20260812.json" type="application/json+chapters"') in xml
        # The post-processing must not drop anything the contract relies on.
        assert "<itunes:block>yes</itunes:block>" in xml
        assert f"personal-{TOKEN[:8]}-ep002-20260812" in xml
        assert chapters_filename_for("2026-08-12") == "chapters_20260812.json"

    def test_feed_depth_capped(self):
        xml = build_personal_feed_xml(self._spec(), self._episodes(12))
        assert xml.count("<item>") == PERSONAL_FEED_MAX_EPISODES

    def test_prune_returns_filenames_to_delete(self):
        kept, dropped = prune_episode_state(self._episodes(10))
        assert len(kept) == PERSONAL_FEED_MAX_EPISODES
        assert len(dropped) == 10 - PERSONAL_FEED_MAX_EPISODES
        # Newest survive.
        assert kept[0]["episode_num"] == 10
        assert "Nerra_Personal_20260811.mp3" in dropped

    def test_title_clipped_and_unlabeled(self):
        seg = _segment()
        seg.hook = "very long words " * 30
        title = personal_episode_title(dt.date(2026, 8, 21), [seg])
        assert len(title) <= 100
        assert not title.startswith("Ep ")


class TestPersonalLinks:
    def test_prompt_carries_name_and_order(self):
        spec = PersonalSpec(token=TOKEN, shows=["dp_pod", "spacex"],
                            first_name="Sam")
        segs = [_segment("dp_pod", "The DP Pod", 41), _segment()]
        prompt = build_personal_links_prompt(ROOT, spec, segs,
                                             dt.date(2026, 8, 21))
        assert "Sam" in prompt
        assert prompt.index("The DP Pod") < prompt.index("SpaceX Daily")

    def test_fallback_greets_and_covers_gaps(self):
        spec = PersonalSpec(token=TOKEN, shows=["spacex", "tesla"],
                            first_name="Sam")
        segs = [_segment(), _segment("tesla", "Tesla Shorts Time", 579)]
        links = fallback_personal_links(spec, segs, dt.date(2026, 8, 21))
        assert "Sam" in links["intro"]
        assert len(links["handoffs"]) == 1
        assert "nerranetwork.com" in links["signoff"]

    def test_prompt_files_registered(self):
        for name in ("nerra_personal_links.txt", "nerra_personal_local.txt"):
            text = (ROOT / "shows" / "prompts" / name).read_text(encoding="utf-8")
            assert "{date_spoken}" in text
        local = (ROOT / "shows" / "prompts" / "nerra_personal_local.txt"
                 ).read_text(encoding="utf-8")
        assert "SKIP" in local  # the honest no-content escape


class TestLocalBrief:
    def test_skip_and_bounds(self):
        assert parse_local_brief("SKIP") is None
        assert parse_local_brief("too short") is None
        good = ("According to the city of Vancouver, the seawall reopens "
                "this weekend after repairs. " * 3)
        assert parse_local_brief(good)

    def test_weather_line_is_measured_data_only(self):
        line = format_weather_line("Vancouver", {
            "temperature_2m_max": [21.6], "temperature_2m_min": [13.2],
            "weather_code": [2],
        })
        assert "Vancouver" in line and "22" in line and "13" in line
        assert "partly cloudy" in line
        assert format_weather_line("Vancouver", {}) == ""


class TestSurfaces:
    def test_pages_registered(self):
        import generate_html as gh

        for fn in ("generate_join_page", "generate_support_page",
                   "generate_account_page"):
            assert hasattr(gh, fn), fn
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert '"join.html", "support.html"' in src  # sitemap

    def test_templates_exist(self):
        for name in ("join_page.html.j2", "account_page.html.j2",
                     "support_page.html.j2"):
            assert (ROOT / "templates" / name).exists(), name

    def test_funding_tag_points_at_support(self):
        # Aug 2026: podcast:funding is the donations surface now — every
        # 2.0 app renders it as the show's Support button.
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'funding_url=f"{config.publishing.base_url}/support.html"' in src
        assert "/#newsletter\",\n            funding_label" not in src

    def test_footer_newsletter_posts_to_account_worker(self):
        # Newsletter signups create accounts: the footer form must go
        # through /api/subscribe (list "member"), not Buttondown's embed.
        base = (ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8")
        assert "embed-subscribe" not in base
        assert "api.nerranetwork.com/api/subscribe" in base
        assert "list:'member'" in base

    def test_missing_admin_token_fails_loudly(self):
        """A host that cannot authenticate must not look idle.

        load_specs used to return [] when PERSONAL_ADMIN_TOKEN was unset.
        That flows into main()'s "no active subscribers — nothing to do"
        and exits 0, so a misconfigured batch host produces a green run
        with zero output — indistinguishable from a healthy day with no
        subscribers, every day, forever. The batch repo's first three
        scheduled runs (2026-08-24 through 08-26) were green exactly that
        way, logging ERROR and succeeding anyway.
        """
        src = (ROOT / "scripts" / "build_personal_feeds.py"
               ).read_text(encoding="utf-8")
        head, _, tail = src.partition('token = os.environ.get("PERSONAL_ADMIN_TOKEN"')
        assert tail, "the --fetch token lookup vanished"
        guard = tail[:600]
        assert "raise SystemExit" in guard, (
            "a missing PERSONAL_ADMIN_TOKEN must abort the run, not "
            "return an empty spec list that reads as 'no subscribers'"
        )
        code = "\n".join(
            line for line in guard.split("raise SystemExit")[0].splitlines()
            if not line.lstrip().startswith("#")
        )
        assert "return []" not in code, "the silent empty-list path is back"

    def test_batch_builder_importable_and_piiless_logging(self):
        src = (ROOT / "scripts" / "build_personal_feeds.py"
               ).read_text(encoding="utf-8")
        # Tokens are logged truncated; names/cities never logged.
        assert "token[:8]" in src
        assert not re.search(r'logger\.\w+\([^)]*spec\.first_name', src)
        assert not re.search(r'logger\.\w+\([^)]*spec\.city', src)


class TestLandingAndConsoleSurfaces:
    """Aug 27 2026 website pass drift guards."""

    def test_join_template_shows_the_pickable_lineup(self):
        src = _read("templates/join_page.html.j2")
        assert "personal_shows" in src, (
            "the landing page must SHOW the closed show vocabulary it sells")
        assert "How Personal works" in src

    def test_join_generator_passes_the_vocabulary(self):
        src = _read("generate_html.py")
        assert "PERSONAL_SHOW_SLUGS" in src

    def test_homepage_carries_personal_promo(self):
        src = _read("templates/network_page.html.j2")
        assert "personal-promo" in src

    def test_account_console_is_state_aware(self):
        src = _read("templates/account_page.html.j2")
        for marker in ("nn-feed-cancelled", "nn-starter-note",
                       "nn-city-nudge", "nn-tier-badge"):
            assert marker in src, marker

    def test_plan_switching_surfaces(self):
        """Sep 13 2026: an existing subscriber must switch plans inside
        Stripe's portal, never through a fresh Payment Link (that created a
        SECOND subscription). Every checkout link carries the opaque
        client_reference_id so the webhook attaches the purchase to the
        signed-in account, not the wallet's email."""
        src = _read("templates/account_page.html.j2")
        assert "nn-switch-portal" in src and "NN.portal()" in src
        assert "/api/account/portal" in src and "/api/account/checkout-ref" in src
        assert "nn-portal-btn" in src and "nn-ends-note" in src
        # Every Stripe link is tagged for the ref injector.
        import re as _re
        for m in _re.finditer(r'<a href="\{\{ stripe_personal(?:_local)?_url \}\}"([^>]*)>', src):
            assert "data-checkout" in m.group(1), m.group(0)
        assert "Personal + Local" not in src
        assert "Personal + Local" not in _read("templates/join_page.html.j2")
        # Worker side of the same contract.
        ts = _read("workers/gallery/src/personal.ts")
        for marker in ("customer.subscription.updated", "client_reference_id",
                       "billing_portal/sessions", "handleCheckoutRef", "handlePortal"):
            assert marker in ts, marker

    def test_login_page_registered(self):
        assert (ROOT / "templates" / "login_page.html.j2").exists()
        src = _read("generate_html.py")
        assert "def generate_login_page" in src
        assert src.count("generate_login_page(dry_run=args.dry_run)") == 2
        tpl = _read("templates/login_page.html.j2")
        assert 'name="robots" content="noindex' in tpl
        assert "password" in tpl.lower()   # says why there isn't one
        assert "/api/login?email=" in tpl

    def test_worker_starter_lineup_within_vocabulary(self):
        # A paying member with <2 shows now gets DEFAULT_LINEUP instead of
        # silent exclusion; the starter must stay inside the closed set.
        import re as _re
        src = _read("workers/gallery/src/personal.ts")
        assert "DEFAULT_LINEUP" in src
        block = src.split("DEFAULT_LINEUP = [", 1)[1].split("]", 1)[0]
        slugs = _re.findall(r'"([a-z_]+)"', block)
        from engine.personal_edition import PERSONAL_SHOW_SLUGS
        assert len(slugs) >= 2
        for s in slugs:
            assert s in PERSONAL_SHOW_SLUGS, s


def _read(rel):
    from pathlib import Path
    return (Path(__file__).resolve().parent.parent / rel).read_text(
        encoding="utf-8")


class TestAddons:
    """Aug 30 2026 — member add-ons (operator-directed): location news /
    weather / events / traffic researched by Mira, plus a zero-LLM
    markets minute. Closed vocabulary, tier-gated, defaults preserve the
    pre-add-on behavior exactly."""

    def _spec(self, **over):
        from engine.personal_edition import validate_spec
        raw = {"token": "a" * 32, "shows": ["tesla", "spacex"],
               "tier": "personal_local", "city": "Vancouver"}
        raw.update(over)
        return validate_spec(raw)

    def test_vocabulary_mirrored_in_worker(self):
        import re as _re
        from engine.personal_edition import PERSONAL_ADDONS
        src = _read("workers/gallery/src/personal.ts")
        block = src.split("PERSONAL_ADDONS = [", 1)[1].split("]", 1)[0]
        worker_ids = _re.findall(r'"([a-z_]+)"', block)
        assert sorted(worker_ids) == sorted(PERSONAL_ADDONS), (
            "workers/gallery/src/personal.ts PERSONAL_ADDONS must mirror "
            "engine.personal_edition.PERSONAL_ADDONS exactly")

    def test_defaults_are_the_full_taster(self):
        # Sep 13 2026 (Personal News Network launch): never-saved (None)
        # on EITHER paid tier = the full taster, weather + one of each
        # researched section. Markets stays opt-in. It only bites once a
        # member sets a location, so nobody's edition changes silently.
        from engine.personal_edition import DEFAULT_ADDONS
        assert tuple(DEFAULT_ADDONS) == ("weather", "local_news", "events", "traffic")
        assert "markets" not in DEFAULT_ADDONS
        local = self._spec()
        assert local.addons is None
        assert local.effective_addons() == list(DEFAULT_ADDONS)
        base = self._spec(tier="personal")
        assert base.effective_addons() == list(DEFAULT_ADDONS)

    def test_validation_drops_unknown_and_tier_gates(self):
        s = self._spec(addons=["weather", "junk", "markets", "weather"])
        assert s.addons == ["weather", "markets"]
        # Every add-on runs on the base tier now; what the tiers gate is
        # depth, city count and topics (TestTiers below).
        base = self._spec(tier="personal",
                          addons=["weather", "traffic", "markets"])
        assert base.effective_addons() == ["weather", "traffic", "markets"]

    def test_empty_list_is_a_real_choice(self):
        s = self._spec(addons=[])
        assert s.addons == []
        assert s.effective_addons() == []
        from engine.personal_edition import wants_local_brief
        assert not wants_local_brief(s)

    def test_prompt_covers_only_selected_sections(self):
        import datetime as dt
        from pathlib import Path
        from engine.personal_edition import build_local_brief_prompt
        root = Path(__file__).resolve().parent.parent
        s = self._spec(addons=["weather", "traffic"])
        p = build_local_brief_prompt(root, s, dt.date(2026, 8, 31),
                                     "Today in Vancouver: a high of 21.")
        assert "traffic or transit disruption" in p
        assert "local news item" not in p
        assert "notable local event" not in p
        assert "Open-Meteo" in p
        no_weather = self._spec(addons=["local_news"])
        p2 = build_local_brief_prompt(root, no_weather, dt.date(2026, 8, 31),
                                      "Today in Vancouver: a high of 21.")
        assert "no weather section" in p2
        assert "local news item" in p2

    def test_weather_only_skips_the_llm(self):
        from engine.personal_edition import needs_research_call, wants_local_brief
        s = self._spec(addons=["weather"])
        assert wants_local_brief(s)
        assert not needs_research_call(s)

    def test_markets_line_is_deterministic_and_ticker_safe(self, tmp_path):
        import json
        from engine.personal_edition import build_markets_line
        api = tmp_path / "api"
        api.mkdir()
        (api / "tsla.json").write_text(json.dumps(
            {"price": 350.0, "prev_close": 340.0}))
        (api / "spcx.json").write_text(json.dumps(
            {"price": 140.0, "prev_close": 141.0}))
        line = build_markets_line(tmp_path)
        assert "Tesla at $350.00, up 2.9 percent" in line
        assert "Ess Pee See Ex" in line
        # Grok TTS text normalization merges an "S P" bigram into "S&P"
        # (the Aug 29 SPCX pronunciation landmine) — the letter-name
        # spelling must never regress to spaced letters.
        assert "S P C X" not in line
        assert build_markets_line(tmp_path / "nowhere") == ""

    def test_prompt_template_carries_the_new_placeholders(self):
        src = _read("shows/prompts/nerra_personal_local.txt")
        assert "{weather_block}" in src
        assert "{research_requests}" in src
        assert "{weather_line}" not in src

    def test_dashboard_renders_the_catalog(self):
        src = _read("templates/account_page.html.j2")
        for marker in ("nn-addons", "personal_addons | tojson",
                       "nn-addon-upsell", "nn-editions-list"):
            assert marker in src, marker
        gen = _read("generate_html.py")
        assert "personal_addons" in gen
        # Every addon id must have display copy or the dashboard silently
        # drops it.
        from engine.personal_edition import PERSONAL_ADDONS
        for aid in PERSONAL_ADDONS:
            assert f'"{aid}":' in gen, f"_ADDON_DISPLAY missing {aid}"

    def test_builder_wires_markets_and_gating(self):
        src = _read("scripts/build_personal_feeds.py")
        assert "wants_local_brief(spec)" in src
        assert "needs_research_call(spec)" in src
        assert "build_markets_line(ROOT)" in src
        assert 'if "markets" in spec.effective_addons()' in src


class TestTiers:
    """Sep 13 2026: Personal News Network. Same add-ons on both paid
    tiers; the tiers differ on depth, city count and topics — enforced
    in validate_spec, the builder's trust boundary, never in the Worker."""

    def _raw(self, tier, **kw):
        d = {"token": TOKEN, "shows": ["spacex", "tesla"], "tier": tier}
        d.update(kw); return d

    def test_limits_table(self):
        from engine.personal_edition import TIER_LIMITS, tier_limits
        assert TIER_LIMITS["personal"] == {"depth": 1, "cities": 1, "topics": 0}
        assert TIER_LIMITS["personal_local"] == {"depth": 3, "cities": 3, "topics": 5}
        assert tier_limits("nonsense") == TIER_LIMITS["personal"]

    def test_personal_is_one_city_no_topics(self):
        from engine.personal_edition import validate_spec
        s = validate_spec(self._raw("personal", cities=["Vancouver, BC", "Kelowna"],
                                    topics=["Starship"]))
        assert s.cities == ["Vancouver, BC"] and s.city == "Vancouver, BC"
        assert s.topics == []
        assert s.depth == 1 and s.is_taster

    def test_pnn_caps_at_three_cities_five_topics(self):
        from engine.personal_edition import validate_spec
        s = validate_spec(self._raw(
            "personal_local",
            cities=["Vancouver, BC", "kelowna", "Kelowna", "Victoria", "Calgary"],
            topics=[f"t{i}" for i in range(9)]))
        assert s.cities == ["Vancouver, BC", "kelowna", "Victoria"]  # dedupe, cap
        assert len(s.topics) == 5
        assert s.depth == 3 and not s.is_taster

    def test_legacy_single_city_still_works(self):
        from engine.personal_edition import validate_spec
        s = validate_spec(self._raw("personal_local", city="Kelowna"))
        assert s.cities == ["Kelowna"] and s.city == "Kelowna"

    def test_free_text_is_scrubbed_before_a_prompt(self):
        from engine.personal_edition import validate_spec, TOPIC_MAX_CHARS
        s = validate_spec(self._raw("personal_local",
                                    topics=["<b>rates</b>", "  Mars   rovers ", "x" * 200,
                                            "{date_spoken}"]))
        assert s.topics[0] == "rates" and s.topics[1] == "Mars rovers"
        assert len(s.topics[2]) == TOPIC_MAX_CHARS
        # Braces stripped so member text can never hit str.format.
        assert "{" not in s.topics[3]

    def test_depth_shapes_the_prompt(self):
        import datetime as dt
        from pathlib import Path
        from engine.personal_edition import build_local_brief_prompt, validate_spec
        root = Path(__file__).resolve().parent.parent
        d = dt.date(2026, 9, 14)
        taster = validate_spec(self._raw("personal", city="Vancouver, BC"))
        full = validate_spec(self._raw("personal_local", cities=["Vancouver, BC", "Kelowna"]))
        pt = build_local_brief_prompt(root, taster, d, "")
        pf = build_local_brief_prompt(root, full, d, "", city="Kelowna")
        assert "ONE local news item" in pt and "At most one item" in pt
        assert "Up to THREE local news items" in pf and "Up to 3 items" in pf
        assert "location: Kelowna" in pf and "location: Vancouver" in pt
        assert "60-160 words" in pt and "120-320 words" in pf

    def test_named_sources_rule_in_both_prompts(self):
        # The Vancouver dry run on 13 Sep cited "local event guides".
        for name in ("nerra_personal_local.txt", "nerra_personal_topics.txt"):
            src = _read(f"shows/prompts/{name}")
            assert "A generic attribution is not a source" in src, name
            assert "BY NAME" in src, name
            # The intro already greeted them; the 13 Sep dry run opened
            # the full brief with a second "Good morning, Patrick".
            assert "do not greet again" in src, name
        from engine.personal_edition import generic_attributions, parse_local_brief
        assert generic_attributions("as listed in local event guides") == ["local event guides"]
        assert generic_attributions("TransLink says the 9 is detoured") == []
        # Warn-only: a real item with a lazy attribution still ships.
        assert parse_local_brief("word " * 40 + "according to reports.") is not None

    def test_topics_prompt(self):
        import datetime as dt
        from pathlib import Path
        from engine.personal_edition import build_topics_prompt, validate_spec, wants_topics_brief
        root = Path(__file__).resolve().parent.parent
        s = validate_spec(self._raw("personal_local", topics=["Starship", "BC housing"]))
        assert wants_topics_brief(s)
        p = build_topics_prompt(root, s, dt.date(2026, 9, 14))
        assert "- Starship\n- BC housing" in p and "the 2 things they named" in p
        assert "80-180 words" in p
        assert not wants_topics_brief(validate_spec(self._raw("personal", topics=["Starship"])))

    def test_nudge_is_monday_only_personal_only_taster_only(self):
        import datetime as dt
        from engine.personal_edition import upgrade_nudge_line, validate_spec
        mon, tue = dt.date(2026, 9, 14), dt.date(2026, 9, 15)
        p = validate_spec(self._raw("personal", city="Vancouver, BC"))
        n = validate_spec(self._raw("personal_local", city="Vancouver, BC"))
        line = upgrade_nudge_line(p, mon, True)
        assert "Personal News Network" in line and "Vancouver, BC" in line
        assert upgrade_nudge_line(p, tue, True) == ""
        assert upgrade_nudge_line(p, mon, False) == ""
        assert upgrade_nudge_line(n, mon, True) == ""

    def test_chapters_per_city_and_topics(self):
        from engine.personal_edition import personal_chapter_pieces, validate_spec
        s = validate_spec(self._raw("personal_local", cities=["Vancouver, BC", "Kelowna"],
                                    topics=["Starship"]))
        segs = [_segment(), _segment("tesla", "Tesla Shorts Time", 5)]
        titles = [t for t, _ in personal_chapter_pieces(
            s, segs, {"intro": 10, "local_1": 60, "local_2": 50, "topics": 40,
                      "seg_spacex": 500, "seg_tesla": 500, "signoff": 8})]
        assert titles[:4] == ["Good morning from Mira", "Your Vancouver, BC brief",
                              "Your Kelowna brief", "Your topics"]

    def test_builder_wires_briefs_topics_and_nudge(self):
        src = _read("scripts/build_personal_feeds.py")
        for marker in ("generate_local_briefs", "generate_topics_brief",
                       "upgrade_nudge_line", "brief_max_words(spec.depth)"):
            assert marker in src, marker
        # The nudge is spoken BEFORE the disclosure, never after it.
        assert 'links["signoff"], nudge,' in src
        assert src.index('links["signoff"], nudge,') < src.index('MIRA_PERSONAL_DISCLOSURE) if x)')

    def test_worker_mirrors_the_limits(self):
        ts = _read("workers/gallery/src/personal.ts")
        assert "CITIES_MAX = 3" in ts and "TOPICS_MAX = 5" in ts
        assert "TOPIC_MAX = 60" in ts

    def test_library_surfaces(self):
        """Sep 14 2026: books included with PNN. The page lists public
        metadata only and links to the Worker's gated route; the r2://
        master refs never reach the page."""
        src = _read("templates/account_page.html.j2")
        assert "nn-library-card" in src and "/api/books/" in src
        assert "r2://" not in src
        import generate_html as gh
        rows = gh.account_library_volumes(gh.books_page_volumes(
            ROOT / "books" / "catalog.json", ROOT / "books" / "volumes"))
        assert rows, "no downloadable volumes found in the catalog"
        for r in rows:
            assert r["epub"].endswith(".epub") and r["epub"].startswith(r["volume_id"])
            assert "r2://" not in r["cover"]
        html = _read("account.html")
        assert "r2://" not in html and "nerra-books" not in html
        ts = _read("workers/gallery/src/personal.ts")
        for marker in ("handleBookDownload", "BOOKS_BUCKET", 'member.tier === "personal_local"'):
            assert marker in ts, marker
        assert 'bucket_name = "nerra-books"' in _read("workers/gallery/wrangler.toml")


# ---------------------------------------------------------------------------
# Sep 17 2026 polish: notes, transcripts, artwork, levelling, on-demand
# ---------------------------------------------------------------------------

class TestPolish:
    def _spec(self):
        return PersonalSpec(token=TOKEN, shows=["spacex", "tesla"],
                            first_name="Sam", city="Vancouver, BC")

    def test_named_sources_keeps_outlets_drops_generic(self):
        from engine.personal_edition import named_sources

        text = ("CBC News reports a tentative deal. The convention opens "
                "today, according to Global News. TransLink says detours "
                "continue on the 9. Local reports say rain. Officials "
                "confirmed it. The City of Vancouver notes a closure. Per "
                "Castanet, the festival runs Friday. Today in Vancouver, BC, "
                "residents are looking at a high of 18.")
        assert named_sources(text) == [
            "CBC News", "Global News", "TransLink", "The City of Vancouver",
            "Castanet"]
        assert named_sources("") == []

    def test_episode_notes_carry_running_order_and_sources(self):
        from engine.personal_edition import episode_notes

        chapters = [{"startTime": 0.0, "title": "Good morning from Mira"},
                    {"startTime": 33.1, "title": "Your Vancouver, BC brief"},
                    {"startTime": 92.3, "title": "SpaceX Daily — Falcon 9"},
                    {"startTime": 3413.4, "title": "Sign-off"}]
        plain, html = episode_notes(
            self._spec(), chapters,
            sources_by_chapter={"Your Vancouver, BC brief": ["CBC News", "TransLink"]},
            segments=[_segment()])
        assert plain.startswith("Sam's edition, in your order.")
        assert "0:33 Your Vancouver, BC brief (sources: CBC News, TransLink)" in plain
        assert "56:53 Sign-off" in plain
        assert "<ol>" in html and "Sources named: CBC News, TransLink" in html
        assert "nerranetwork.com/account.html" in html
        assert "<script" not in html
        # HTML-unsafe text is escaped, never injected.
        _, html2 = episode_notes(self._spec(), [{"startTime": 0, "title": "<b>x</b>"}])
        assert "&lt;b&gt;x&lt;/b&gt;" in html2

    def test_feed_carries_notes_transcripts_and_own_cover(self):
        from engine.personal_edition import (
            COVER_FILENAME, NETWORK_COVER_URL, transcript_filenames_for)

        rows = TestPersonalFeed()._episodes(1)
        rows[0]["notes_html"] = "<p><strong>Sam's</strong> edition</p>"
        rows[0]["transcripts"] = list(transcript_filenames_for("2026-08-11"))
        xml = build_personal_feed_xml(self._spec(), rows, cover=True)
        # feedgen writes CDATA; the chapter/transcript post-pass re-serializes
        # through ElementTree, which escapes instead — equivalent to a reader,
        # and the prefix must stay `content:` (apps key on it).
        assert ("<content:encoded>&lt;p&gt;&lt;strong&gt;Sam's&lt;/strong&gt; "
                "edition&lt;/p&gt;</content:encoded>") in xml
        assert (f'<podcast:transcript url="https://api.nerranetwork.com/api/feed/{TOKEN}/'
                f'transcript_20260811.json" type="application/json"') in xml
        assert (f'<podcast:transcript url="https://api.nerranetwork.com/api/feed/{TOKEN}/'
                f'transcript_20260811.vtt" type="text/vtt"') in xml
        assert f'href="https://api.nerranetwork.com/api/feed/{TOKEN}/{COVER_FILENAME}"' in xml
        assert NETWORK_COVER_URL not in xml
        # Chapters survive alongside; without a cover the network art stays.
        assert "<podcast:chapters" in xml
        assert NETWORK_COVER_URL in build_personal_feed_xml(self._spec(), rows)

    def test_transcript_cues_follow_the_splice_and_stop_at_the_cut(self):
        from engine.personal_edition import (
            transcript_entries, transcript_json, transcript_vtt)

        whisper = {"segments": [
            {"start": 0.0, "end": 4.0, "text": "First line."},
            {"start": 4.0, "end": 9.0, "text": "Second line."},
            {"start": 9.5, "end": 14.0, "text": "Promo that was cut."},
        ]}
        cues = transcript_entries([
            ("Mira", 10.0, "Good morning, Sam.", None, None),
            ("SpaceX Daily", 9.2, None, whisper, 9.2),
            ("Mira", 5.0, "That's your edition.", None, None),
        ])
        assert [c["speaker"] for c in cues] == ["Mira", "SpaceX Daily", "SpaceX Daily", "Mira"]
        assert cues[1]["startTime"] == 10.0 and cues[2]["endTime"] == 19.0
        assert cues[3]["startTime"] == pytest.approx(19.2)
        assert all("Promo" not in c["body"] for c in cues)
        assert transcript_json(cues)["segments"] == cues
        vtt = transcript_vtt(cues)
        assert vtt.startswith("WEBVTT\n\n1\n00:00:00.000 --> 00:00:10.000\n<v Mira>Good morning, Sam.")
        assert "00:00:19.200 -->" in vtt

    def test_cover_renders_1400_square_and_signature_tracks_identity(self, tmp_path):
        from engine.personal_edition import cover_signature, render_cover

        spec = self._spec()
        out = tmp_path / "cover.jpg"
        base = Path(__file__).resolve().parent.parent / "assets/covers/nerra-daily.jpg"
        assert render_cover(spec, base, out) is True
        from PIL import Image

        im = Image.open(out)
        assert im.size == (1400, 1400) and im.format == "JPEG"
        assert cover_signature(spec) != cover_signature(
            PersonalSpec(token=TOKEN, shows=["spacex", "tesla"], first_name="Pat",
                         city="Vancouver, BC"))
        # A missing base image never raises — the feed keeps the network art.
        assert render_cover(spec, tmp_path / "nope.jpg", tmp_path / "c2.jpg") is False

    def test_segment_levelling_is_static_and_bounded(self):
        from engine.personal_edition import (
            segment_gain_cmd, segment_gain_db, sting_cmd)

        assert segment_gain_db(-16.4) == 0.0          # in spec: untouched
        assert segment_gain_db(-25.3) == 9.3          # UC on 2026-09-17
        assert segment_gain_db(-2.0) == -12.0         # clamped
        assert segment_gain_db(None) == 0.0 and segment_gain_db(-70.0) == 0.0
        cmd = segment_gain_cmd(Path("in.mp3"), Path("out.mp3"), 9.3)
        assert "volume=+9.3dB,alimiter=limit=0.891:level=false" in " ".join(cmd)
        assert cmd[-1] == "out.mp3" and "-q:a" in cmd
        sting = " ".join(sting_cmd(Path("sting.mp3")))
        assert "channel_layouts=stereo" in sting and "volume=-18dB" in sting

    def test_builder_exposes_only_and_replace(self):
        src = (Path(__file__).resolve().parent.parent
               / "scripts/build_personal_feeds.py").read_text(encoding="utf-8")
        assert '"--only"' in src and '"--replace"' in src
        assert "revision" in src and "built_at" in src
        # A replaced day keeps its episode number (no duplicate in the app)
        # and the superseded MP3 is deleted.
        assert 'int(previous[0].get("episode_num", 0))' in src
        assert "dropped.extend(" in src
        wf = (Path(__file__).resolve().parent.parent
              / "docs/nerra_personal.md").read_text(encoding="utf-8")
        assert "GITHUB_DISPATCH_TOKEN" in wf

    def test_weather_opener_is_enforced(self):
        from engine.personal_edition import ensure_weather_opener

        w = "Today in Vancouver, BC: a high of 21 and a low of 12 degrees with clear skies."
        # Model kept it (numbers present): untouched.
        kept = "Expect 21 by afternoon after a low of 12. CBC News reports a deal."
        assert ensure_weather_opener(kept, w) == kept
        # Model dropped it: spoken first, verbatim.
        dropped = "Vancouver Sun reports one-quarter of candidates are women."
        assert ensure_weather_opener(dropped, w) == f"{w} {dropped}"
        # "21" inside "2021" doesn't count as the high.
        assert ensure_weather_opener("Founded in 2021, 12 people.", w).startswith(w)
        assert ensure_weather_opener(None, w) == w
        assert ensure_weather_opener("x", "") == "x"

    def test_trial_copy_is_gated_and_sample_is_wired(self):
        root = Path(__file__).resolve().parent.parent
        join = (root / "templates/join_page.html.j2").read_text(encoding="utf-8")
        # Every mention of a free trial sits behind trial_days, so a page
        # built without the var (or with 0) never promises what the Stripe
        # links don't carry.
        assert "{% if trial_days %}" in join
        for line in join.splitlines():
            if re.search(r"free for \d|days are free|free trial", line) and "trial_days" not in line:
                raise AssertionError(f"ungated trial copy: {line.strip()}")
        assert 'src="{{ sample_url }}"' in join and 'id="sample"' in join
        gen = (root / "generate_html.py").read_text(encoding="utf-8")
        assert '"trial_days": _env_int("STRIPE_TRIAL_DAYS")' in gen
        assert "personal/sample/vancouver.mp3" in gen
        sample = (root / "scripts/build_personal_sample.py").read_text(encoding="utf-8")
        assert 'SAMPLE_SLUG = "vancouver"' in sample and "personal/sample/" in sample
        for wf in ("nightly-maintenance.yml", "run-show.yml"):
            text = (root / ".github/workflows" / wf).read_text(encoding="utf-8")
            assert "STRIPE_TRIAL_DAYS: ${{ vars.STRIPE_TRIAL_DAYS || '7' }}" in text
        acct = (root / "templates/account_page.html.j2").read_text(encoding="utf-8")
        assert "trial_ends_at" in acct and "nn-build-btn" in acct
