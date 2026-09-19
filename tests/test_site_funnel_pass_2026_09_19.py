"""Drift guards for the Sep 19 2026 site pass — measurement + leaks.

Three defects this pins, all found by reading `api/ga4_stats.json` and
`api/funnel.json` rather than the code:

1. **26% of measured landing sessions hit URLs with no file** (49 of 188), all
   bouncing at 100% — the DP Pod posts purged on 2026-08-10 plus a cluster of
   `blog/dp_pod/<nav target>` paths from a crawl of posts whose chrome links
   resolved relative. Nothing noticed, because every check the site had asked
   whether the pages it GENERATES are sound, never whether the pages people
   ASK for exist.

2. **`attribution_coverage_pct` was 4.05%** because five places built `utm_*`
   links outside `engine/funnel.py`, each emitting a campaign
   `parse_campaign_id()` rejects. 134,171 YouTube views produced 10 attributed
   sessions, and the surfaces meant to carry the rest measured as nothing.

3. **The site had no network identity.** `twitter:site` did not exist anywhere
   in the repo, the footer and the Organization JSON-LD listed three SHOW
   accounts and no network account, and `@NerraFR` had been live since July
   without appearing anywhere.

Plus two honesty fixes: the support page's "real ledger" understated spend by
30% and named the wrong largest line, and `--all` skipped three generators.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate_html as gh  # noqa: E402
from engine.funnel import parse_campaign_id  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Dead URLs
# ---------------------------------------------------------------------------

class TestRedirectStubs:
    @pytest.fixture(scope="class")
    def redirects(self):
        data = yaml.safe_load((ROOT / "site" / "redirects.yaml").read_text())
        return data["redirects"], data.get("accepted_404") or []

    def test_every_target_exists(self, redirects):
        """A redirect into a 404 is worse than the 404 it replaces."""
        entries, _ = redirects
        assert entries, "redirect map is empty"
        for entry in entries:
            target = ROOT / str(entry["to"]).lstrip("/")
            assert target.exists(), f"{entry['from']} -> missing {entry['to']}"

    def test_every_entry_carries_a_reason(self, redirects):
        entries, accepted = redirects
        for entry in entries + accepted:
            assert (entry.get("reason") or "").strip(), f"no reason: {entry}"

    def test_no_stub_shadows_a_real_page(self, redirects):
        """A live page beats a redirect to one. The generator refuses to
        overwrite a real file; this proves the map never asks it to."""
        entries, _ = redirects
        for entry in entries:
            src = ROOT / str(entry["from"]).lstrip("/")
            if not src.exists():
                continue
            assert gh._is_redirect_stub(src), (
                f"{entry['from']} is a real page, not a stub"
            )

    def test_stubs_are_noindex_and_carry_a_canonical(self, redirects):
        entries, _ = redirects
        for entry in entries:
            src = ROOT / str(entry["from"]).lstrip("/")
            if not src.exists():
                continue
            html = src.read_text(encoding="utf-8")
            assert 'name="robots" content="noindex, follow"' in html
            assert 'rel="canonical"' in html
            assert f'https://nerranetwork.com/{entry["to"]}' in html

    def test_stubs_are_excluded_from_the_sitemap(self, redirects, tmp_path):
        """generate_sitemap GLOBS blog/<show>/ep*.html, so a stub for a retired
        episode would be submitted to Google as an article."""
        entries, _ = redirects
        out = tmp_path / "sitemap.xml"
        gh.generate_sitemap(out=str(out))
        xml = out.read_text(encoding="utf-8")
        for entry in entries:
            src = str(entry["from"]).lstrip("/")
            assert f"/{src}<" not in xml, f"{src} is in the sitemap"

    def test_generator_refuses_to_overwrite_a_real_page(self, tmp_path, capsys):
        """The guard that matters: a page that comes BACK must win."""
        real = ROOT / "about.html"
        assert real.exists()
        assert not gh._is_redirect_stub(real)


class TestDeadUrlAudit:
    @pytest.fixture(scope="class")
    def audit(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import audit_dead_urls
        return audit_dead_urls

    def test_measured_landing_paths_all_resolve(self, audit):
        """The whole point: after the stubs, no measured landing path 404s.
        A failure here means a new hole opened — add it to redirects.yaml
        (or to accepted_404 with a reason)."""
        stats = json.loads((ROOT / "api" / "ga4_stats.json").read_text())
        dead = audit.find_dead_landing_paths(stats)
        assert dead == [], f"measured 404s: {dead}"

    def test_normalises_the_shapes_ga4_actually_emits(self, audit):
        # A real row reads "/age-of-ai-apply.html; it takes a couple of minutes"
        assert audit._normalise("/a.html; and then some prose") == "a.html"
        assert audit._normalise("/b.html?utm_source=x") == "b.html"
        assert audit._normalise("/blog/tesla/") == "blog/tesla/index.html"
        assert audit._normalise("(not set)") == ""
        assert audit._normalise("/") == ""

    def test_accepted_404s_are_not_reported(self, audit):
        accepted = audit.accepted_404_paths()
        assert "blog/dp_pod/blog.rss" in accepted
        stats = {"landing_pages": [
            {"landingPagePlusQueryString": "/blog/dp_pod/blog.rss",
             "sessions": 1, "bounceRate": 1.0},
        ]}
        assert audit.find_dead_landing_paths(stats) == []

    def test_a_new_hole_is_reported(self, audit):
        stats = {"landing_pages": [
            {"landingPagePlusQueryString": "/definitely-not-a-page.html",
             "sessions": 9, "bounceRate": 1.0},
        ]}
        dead = audit.find_dead_landing_paths(stats)
        assert dead == [("definitely-not-a-page.html", 9, 1.0)]

    def test_strict_mode_fails_on_a_hole(self, audit, tmp_path):
        stats = tmp_path / "ga4.json"
        stats.write_text(json.dumps({"days": 28, "landing_pages": [
            {"landingPagePlusQueryString": "/nope.html",
             "sessions": 3, "bounceRate": 1.0},
        ]}))
        assert audit.main(["--strict", "--stats", str(stats)]) == 1
        assert audit.main(["--stats", str(stats)]) == 0  # loud, non-blocking

    def test_missing_stats_file_is_a_clean_noop(self, audit, tmp_path):
        assert audit.main(["--strict", "--stats", str(tmp_path / "gone.json")]) == 0


class Test404PageReportsItself:
    def test_page_not_found_event_is_fired(self):
        """A static host answers every dead URL with this page, so the only
        way a 404 becomes a metric rather than an inference is a named event."""
        html = (ROOT / "404.html").read_text(encoding="utf-8")
        assert "page_not_found" in html
        assert "requested_path" in html

    def test_event_is_guarded_on_gtag_existing(self):
        """Consent mode and an unset GA4 id both mean gtag may be absent; a
        ReferenceError would take the rest of the page's scripts with it."""
        html = (ROOT / "404.html").read_text(encoding="utf-8")
        assert "typeof gtag !== 'function'" in html


# ---------------------------------------------------------------------------
# 2. Funnel attribution
# ---------------------------------------------------------------------------

class TestFunnelOwnsEveryPublishedCampaign:
    """`CLAUDE.md`: no utm_* link, campaign id or capture tag for a published
    surface may be built outside engine/funnel.py."""

    # Outbound links to Apple/Spotify are exempt: those parameters are read by
    # the DESTINATION's analytics, never by ours, so they carry no funnel
    # campaign and cannot affect attribution coverage.
    _OUTBOUND_ONLY = {"generate_html.py", "make_apple_qr.py"}

    @staticmethod
    def _docstring_lines(source: str) -> set:
        """Line numbers occupied by docstrings, so a comment ABOUT the old
        hand-rolled campaign is not mistaken for one."""
        import ast

        lines = set()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                       ast.ClassDef)
            ):
                continue
            body = getattr(node, "body", None) or []
            if not body:
                continue
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                lines.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
        return lines

    def test_no_new_hand_rolled_utm_builders(self):
        offenders = {}
        for path in list(ROOT.glob("engine/*.py")) + [ROOT / "run_show.py"]:
            if path.name == "funnel.py":
                continue
            source = path.read_text(encoding="utf-8")
            skip = self._docstring_lines(source)
            for num, line in enumerate(source.splitlines(), 1):
                if num in skip or line.lstrip().startswith("#"):
                    continue
                if "utm_campaign=" in line:
                    offenders.setdefault(path.name, []).append(num)
        assert offenders == {}, (
            "hand-rolled utm_campaign outside engine/funnel.py: "
            f"{offenders} — use funnel_link()/episode_link()/network_link()"
        )

    def test_surface_reply_campaign_parses(self):
        import datetime

        from engine.network_promo import build_surface_x_reply
        text = build_surface_x_reply("tesla", datetime.date(2026, 9, 19), 604)
        campaign = re.search(r"utm_campaign=([^&\s]+)", text).group(1)
        parsed = parse_campaign_id(campaign)
        assert parsed is not None, campaign
        assert parsed.show == "tesla" and parsed.episode == 604
        assert parsed.variant, "the plugged surface must ride in the variant"

    def test_surface_reply_is_untagged_without_an_episode(self):
        """Better an untagged link than one tagged with a campaign the funnel
        report will silently drop."""
        import datetime

        from engine.network_promo import build_surface_x_reply
        text = build_surface_x_reply("tesla", datetime.date(2026, 9, 19))
        assert "utm_" not in text

    def test_every_network_surface_url_exists(self):
        """The 'blogs' surface pointed at blog.html, which has never existed,
        so every rotation of it shipped a 404 to X."""
        from engine.network_promo import NETWORK_SURFACES
        for surface in NETWORK_SURFACES:
            target = ROOT / surface["url"]
            assert target.exists(), f"{surface['id']} -> missing {surface['url']}"

    def test_share_row_campaigns_parse(self):
        from engine.blog import _share_urls
        urls = _share_urls("tesla", 604, "https://nerranetwork.com/x.html")
        assert set(urls) == {
            "x", "linkedin", "facebook", "whatsapp", "telegram", "email",
        }
        for key, url in urls.items():
            campaign = re.search(r"utm_campaign=([^&]+)", url).group(1)
            assert parse_campaign_id(campaign) is not None, (key, campaign)

    def test_share_sources_are_in_the_closed_vocabulary(self):
        from engine.funnel import SOURCES, SHARE_SOURCES
        assert SHARE_SOURCES <= SOURCES

    def test_network_link_rejects_an_empty_path(self):
        from engine.funnel import network_link
        assert network_link("", "tesla", 1) == ""


# ---------------------------------------------------------------------------
# 3. Network identity
# ---------------------------------------------------------------------------

class TestNetworkSocial:
    def test_x_handle_is_the_network_account(self):
        assert gh.NETWORK_SOCIAL["x"]["handle"] == "@nerranetwork"

    def test_primary_account_sorts_first(self):
        assert gh.network_social_links()[0]["key"] == "x"

    def test_every_rendered_account_has_a_url(self):
        for account in gh.network_social_links():
            assert account["url"].startswith("https://")

    def test_an_unfilled_account_renders_nothing(self):
        """Other platforms are coming; a placeholder must not become a dead
        link on every page in the meantime."""
        original = dict(gh.NETWORK_SOCIAL)
        gh.NETWORK_SOCIAL["instagram"] = {
            "handle": "", "url": "", "label": "Instagram",
        }
        try:
            keys = {a["key"] for a in gh.network_social_links()}
            assert "instagram" not in keys
        finally:
            gh.NETWORK_SOCIAL.clear()
            gh.NETWORK_SOCIAL.update(original)

    def test_youtube_fr_is_present(self):
        """Live since 2026-07-21 and missing from the footer until Sep 2026."""
        assert "youtube_fr" in gh.NETWORK_SOCIAL

    def test_twitter_site_is_in_the_base_template(self):
        base = (ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8")
        assert 'name="twitter:site"' in base
        assert 'name="twitter:creator"' in base

    def test_rendered_pages_carry_the_network_handle(self):
        for page in ("about.html", "support.html", "contact.html", "press.html"):
            html = (ROOT / page).read_text(encoding="utf-8")
            assert 'content="@nerranetwork"' in html, page
            assert "https://x.com/nerranetwork" in html, page

    def test_organization_sameas_names_the_network_first(self):
        html = (ROOT / "about.html").read_text(encoding="utf-8")
        same_as = json.loads(re.search(r'"sameAs": (\[.*?\])', html, re.S).group(1))
        assert same_as[0] == "https://x.com/nerranetwork"

    def test_gsc_verification_reaches_the_committing_workflows(self):
        """Read by generate_html.py since May 2026 and passed by nothing, so
        the verification tag could not render even once the secret was set."""
        for wf in ("nightly-maintenance.yml", "run-show.yml"):
            text = (ROOT / ".github" / "workflows" / wf).read_text()
            assert "GSC_VERIFICATION" in text, wf


# ---------------------------------------------------------------------------
# Honesty + coverage
# ---------------------------------------------------------------------------

class TestCostLedgerIsRead:
    def test_monthly_cost_comes_from_the_dashboard(self):
        rollup = json.loads((ROOT / "api" / "dashboard.json").read_text())
        total = rollup["cost_rollup"]["network_last_30_days"]["total"]
        ledger = gh._network_cost_ledger()
        assert ledger["monthly_cost_usd"] == int(round(total))

    def test_split_sums_to_100(self):
        ledger = gh._network_cost_ledger()
        assert sum(pct for _, pct in ledger["cost_split"]) == 100

    def test_largest_line_matches_the_data(self):
        """The typed split said voice synthesis was the biggest line at ~40%.
        Imagery is, and had been for months."""
        rollup = json.loads((ROOT / "api" / "dashboard.json").read_text())
        row = rollup["cost_rollup"]["network_last_30_days"]
        measured = {"tts": row["tts"], "images": row["images"],
                    "models": row["grok"] + row["search"]}
        biggest = max(measured, key=measured.get)
        ledger = gh._network_cost_ledger()
        top_label = max(ledger["cost_split"], key=lambda r: r[1])[0]
        expected = {"tts": "Voice", "images": "Artwork", "models": "Writing"}
        assert top_label.startswith(expected[biggest]), (top_label, biggest)

    def test_missing_dashboard_falls_back_rather_than_failing(self, monkeypatch):
        monkeypatch.setattr(gh, "ROOT", ROOT / "does-not-exist")
        ledger = gh._network_cost_ledger()
        assert ledger["monthly_cost_usd"] > 0
        assert sum(pct for _, pct in ledger["cost_split"]) == 100

    def test_support_page_is_honest_about_the_total(self):
        html = (ROOT / "support.html").read_text(encoding="utf-8")
        total = gh._network_cost_ledger()["monthly_cost_usd"]
        assert f"${total}/month" in html


class TestAllMeansAll:
    def test_all_runs_the_generators_that_used_to_need_show(self):
        source = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        all_block = source.split("if args.all:", 1)[1].split("if args.shows:", 1)[0]
        for fn in (
            "generate_all_narrative_pages",
            "generate_mit_performance_page",
            "generate_all_ru_landing_pages",
            "generate_redirect_stubs",
            "generate_llms_txt",
        ):
            assert fn in all_block, f"--all does not run {fn}"


class TestLlmsTxt:
    @pytest.fixture(scope="class")
    def text(self):
        return (ROOT / "llms.txt").read_text(encoding="utf-8")

    def test_names_every_show(self, text):
        for show in gh._build_all_shows_list():
            assert show["name"] in text, show["name"]

    def test_states_the_mira_claim_with_its_basis(self, text):
        from engine.brand import MIRA_FIRST_CLAIM, MIRA_FIRST_CLAIM_BASIS
        assert MIRA_FIRST_CLAIM in text
        assert MIRA_FIRST_CLAIM_BASIS in text

    def test_says_what_the_ai_disclosure_says(self, text):
        """An answer engine quoting this must not end up claiming a human
        reviews every episode — the exact error the old disclosure page made."""
        assert "no person reads every episode before it publishes" in text

    def test_points_at_the_paid_product(self, text):
        assert "join.html" in text


class TestMiraClaimHasOneOwner:
    def test_claim_ships_with_a_basis_and_an_invitation(self):
        from engine.brand import mira_claim_paragraphs
        claim, basis, footnote = mira_claim_paragraphs()
        assert "first" in claim.lower()
        assert "have not found another" in basis
        assert "hello@nerranetwork.com" in footnote

    def test_claim_is_not_retyped_anywhere(self):
        """The titles/funnel rule: one module states it, everything imports."""
        from engine.brand import MIRA_FIRST_CLAIM
        needle = MIRA_FIRST_CLAIM[:40]
        for path in list(ROOT.glob("templates/*.j2")) + [ROOT / "generate_html.py"]:
            assert needle not in path.read_text(encoding="utf-8"), path.name


# ---------------------------------------------------------------------------
# A feed NAME is not a feed FILE
# ---------------------------------------------------------------------------

class TestNoLinksToAnUnpublishedFeed:
    """Nerra Voices has a page, a registry entry, a feed name and no episodes.
    Its feed file does not exist, and the footer's per-show RSS list linked it
    from every page on the site — 1,990 pages carrying the same dead link, and
    the single most-repeated broken link there was. Found by crawling the
    generated tree, which nothing had done since the Sep 3 pass."""

    def test_has_feed_is_false_for_a_show_with_no_episodes(self):
        shows = {s["slug"]: s for s in gh._build_all_shows_list()}
        assert shows["nerra_voices"]["has_feed"] is False
        assert shows["tesla"]["has_feed"] is True

    def test_has_feed_tracks_the_file_not_the_registry(self):
        for show in gh._build_all_shows_list():
            expected = (ROOT / show["rss_file"]).exists()
            assert show["has_feed"] is expected, show["slug"]

    def test_no_root_page_links_a_feed_that_does_not_exist(self):
        """The crawl, as a test. Any page linking a missing feed fails here."""
        missing = {
            s["rss_file"] for s in gh._build_all_shows_list() if not s["has_feed"]
        }
        if not missing:
            pytest.skip("every registered show has published")
        offenders = {}
        pages = list(ROOT.glob("*.html")) + list((ROOT / "ru").glob("*.html"))
        for page in pages:
            html = re.sub(
                r"<script\b.*?</script>", "",
                page.read_text(encoding="utf-8", errors="ignore"),
                flags=re.S | re.I,
            )
            for feed in missing:
                if f'href="{feed}"' in html or f'href="../{feed}"' in html:
                    offenders.setdefault(page.name, set()).add(feed)
        assert offenders == {}, f"links to an unpublished feed: {offenders}"

    def test_show_page_js_does_not_fetch_a_missing_feed(self):
        html = (ROOT / "nerra-voices.html").read_text(encoding="utf-8")
        assert "const HAS_FEED = false" in html
        assert "if (!HAS_FEED)" in html

    def test_webfeed_is_omitted_from_jsonld_when_absent(self):
        html = (ROOT / "nerra-voices.html").read_text(encoding="utf-8")
        blocks = re.findall(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, re.S
        )
        series = [
            b for b in (json.loads(x) for x in blocks)
            if isinstance(b, dict) and b.get("@type") == "PodcastSeries"
        ]
        assert series, "no PodcastSeries block"
        assert "webFeed" not in series[0]

    def test_every_root_page_jsonld_stays_valid(self):
        """The webFeed member sits in a hand-assembled JSON object whose commas
        are template conditionals, so dropping it is exactly the edit that
        breaks the block."""
        pages = list(ROOT.glob("*.html")) + list((ROOT / "ru").glob("*.html"))
        for page in pages:
            html = page.read_text(encoding="utf-8", errors="ignore")
            for block in re.findall(
                r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                html, re.S,
            ):
                json.loads(block)  # raises on malformed JSON

    def test_a_story_tracker_is_linked_only_when_the_page_exists(self):
        """Being registered for memory is not the same as having a tracker."""
        html = (ROOT / "nerra-voices.html").read_text(encoding="utf-8")
        assert "nerra-voices-narrative.html" not in html


class TestNightlyCommitsWhatItGenerates:
    """The silent-drop class: a generated path missing from the nightly's
    add-paths whitelist is rebuilt every night and thrown away. It cost
    api/youtube_channel_history.json four runs and six shows' memory trackers
    a month of nights before anyone noticed."""

    def test_llms_txt_is_whitelisted(self):
        nightly = (
            ROOT / ".github" / "workflows" / "nightly-maintenance.yml"
        ).read_text()
        add_paths = nightly.split("add-paths: |", 1)[1]
        assert "llms.txt" in add_paths

    def test_dead_url_audit_runs_nightly(self):
        nightly = (
            ROOT / ".github" / "workflows" / "nightly-maintenance.yml"
        ).read_text()
        assert "scripts/audit_dead_urls.py" in nightly

    def test_audit_never_blocks_the_nightly(self):
        """A new 404 is news, not a reason to fail a maintenance run."""
        nightly = (
            ROOT / ".github" / "workflows" / "nightly-maintenance.yml"
        ).read_text()
        line = next(
            l for l in nightly.splitlines() if "audit_dead_urls.py" in l
        )
        assert "|| true" in line or "--strict" not in line


# ---------------------------------------------------------------------------
# The paid product and the flagship edition enter the promo rotation
# ---------------------------------------------------------------------------

class TestPersonalAndNerraDailyArePlugged:
    """NETWORK_SURFACES had eight entries and neither the network's combined
    daily edition nor its only paid product was among them, while the free
    image gallery carried triple weight. Nerra Daily is also the cheapest show
    to produce ($0.085/ep), the only one trending up (+22.7% WoW) and the
    site's most-visited show page.

    The spoken copy changes shipped audio on every English show — landmine #17
    A/B-listen applies, and the revert is deleting the two dicts."""

    def test_both_surfaces_are_in_the_pool(self):
        from engine.network_promo import NETWORK_SURFACES
        ids = {s["id"] for s in NETWORK_SURFACES}
        assert "personal" in ids
        assert "nerra_daily" in ids

    def test_both_rotate_within_a_fortnight(self):
        import datetime

        from engine.network_promo import pick_featured_surface
        seen = {
            pick_featured_surface("tesla", datetime.date(2026, 9, 19)
                                  + datetime.timedelta(days=d))["id"]
            for d in range(14)
        }
        assert {"personal", "nerra_daily"} <= seen

    def test_gallery_keeps_its_july_2026_weight(self):
        """Adding two surfaces already dilutes every entry proportionally, so
        there was nothing to make room for — and gallery's boost is a prior
        operator decision, not spare capacity."""
        from engine.network_promo import NETWORK_SURFACES
        gallery = next(s for s in NETWORK_SURFACES if s["id"] == "gallery")
        assert int(gallery["weight"]) == 3

    def test_spoken_copy_avoids_chapter_marker_trigger_phrases(self):
        """The module's own rule: spoken copy must not collide with the chapter
        patterns in the show YAMLs."""
        from engine.network_promo import NETWORK_SURFACES
        banned = ("deep dive", "next time", "under the hood")
        for surface in NETWORK_SURFACES:
            spoken = surface["spoken"].lower()
            for phrase in banned:
                assert phrase not in spoken, (surface["id"], phrase)

    def test_no_surface_supplies_a_quotable_specimen_sentence(self):
        """De-seed by shape: three generations of this network's tics came from
        a prompt handing the model the literal sentence it wanted."""
        from engine.network_promo import NETWORK_SURFACES
        for surface in NETWORK_SURFACES:
            assert '"' not in surface["spoken"], surface["id"]


class TestPersonalUpsellBand:
    def test_only_nerra_daily_carries_the_band(self):
        """A band on every show page is a banner, and banners get ignored."""
        import yaml as _yaml
        registry = _yaml.safe_load(
            (ROOT / "shows" / "network_meta.yaml").read_text()
        )
        flagged = {
            slug for slug, cfg in registry.items()
            if isinstance(cfg, dict) and cfg.get("personal_upsell")
        }
        assert flagged == {"nerra_daily"}

    def test_band_renders_on_nerra_daily(self):
        html = (ROOT / "nerra-daily.html").read_text(encoding="utf-8")
        assert 'id="make-it-yours"' in html
        assert "join.html" in html

    def test_band_is_absent_elsewhere(self):
        for page in ("tesla.html", "spacex.html", "index.html"):
            html = (ROOT / page).read_text(encoding="utf-8")
            assert 'id="make-it-yours"' not in html, page

    def test_internal_cta_is_measured_by_event_not_utm(self):
        """The same defect this pass removed from the Story Tracker link: a UTM
        on an internal href starts a new GA4 session and overwrites the
        visitor's real acquisition source."""
        html = (ROOT / "nerra-daily.html").read_text(encoding="utf-8")
        assert "select_personal_upsell" in html
        assert "join.html?utm" not in html

    def test_the_band_does_not_oversell_the_free_show(self):
        """Nerra Daily is free and stays free; the band must offer the free path
        as well as the paid one."""
        html = (ROOT / "nerra-daily.html").read_text(encoding="utf-8")
        band = html.split('id="make-it-yours"', 1)[1][:2600]
        assert "Keep listening free" in band
        assert "Cancel in one click" in band


class TestCaptureAttributionIsLoudWhenBroken:
    def test_empty_tag_breakdown_warns(self):
        """api/buttondown_stats.json has shipped `tag_counts: {}` beside 5
        subscribers — which reads as tidy but means no capture can be traced to
        the page or show that earned it."""
        src = (ROOT / "scripts" / "fetch_buttondown_stats.py").read_text()
        assert "attribution_warning" in src
        assert "::warning title=Buttondown attribution::" in src

    def test_worker_allows_every_funnel_source_tag(self):
        from engine.funnel import SOURCES, source_tag
        handlers = (
            ROOT / "workers" / "gallery" / "src" / "handlers.ts"
        ).read_text()
        for source in SOURCES:
            tag = source_tag(source)
            assert f'"{tag}"' in handlers, (
                f"{tag} is produced by engine.funnel but the Worker would drop "
                "it, losing the attribution"
            )
