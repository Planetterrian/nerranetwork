"""Guards for the capture-measurement pass (2026-09-21).

Phase 1 made CLICKS traceable — four campaigns in `api/funnel.json` that
`parse_campaign_id` reads. The capture end stayed dark: 5 subscribers,
`tag_counts: {}`, `by_source: {}`, and `attribution_coverage_pct` 3.5%. The
audit found the cause was not the part everyone suspected:

* ``resolveSubscribeTags`` was fine and always put tags in the request body;
* but the Worker applied them on **CREATE only** — a duplicate returned early,
  so an address already on the list could never acquire a tag; and
* **no first-party form sent ``source`` at all**, so ``capture.by_source`` was
  structurally incapable of holding a row no matter how long we waited. The
  pre-existing guard checked only that the Worker *accepts* every source tag,
  never that a page *emits* one — which is exactly how this survived.

Plus a fourth instance of the "a result key is not a metric" class:
``select_personal_upsell`` had been firing from the network's only on-site
upsell since 2026-09-19 and was read by nothing.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestTheUpsellEventIsRead:
    """An event a template fires is not a metric until a fetcher asks for it."""

    def test_engagement_event_is_in_the_ga4_filter(self):
        from scripts.fetch_ga4_stats import CONVERSION_EVENTS, ENGAGEMENT_EVENTS

        assert "select_personal_upsell" in ENGAGEMENT_EVENTS
        assert "soft_personal_interest_submit" in ENGAGEMENT_EVENTS
        # It must NOT ride in the conversions list: build_funnel sums every
        # row of that report into signup_events_total, so an engagement event
        # there would report an intention as a subscriber.
        assert "select_personal_upsell" not in CONVERSION_EVENTS
        assert "soft_personal_interest_submit" not in CONVERSION_EVENTS
        assert "newsletter_signup" in CONVERSION_EVENTS

    def test_the_two_reports_stay_separate(self):
        src = (ROOT / "scripts" / "fetch_ga4_stats.py").read_text()
        assert '"site_events": site_events' in src
        assert '"conversions": conversions' in src
        # Both filters read from the named constants, not inline literals.
        assert '"values": CONVERSION_EVENTS' in src
        assert '"values": ENGAGEMENT_EVENTS' in src

    def test_the_event_the_template_fires_is_the_event_we_ask_for(self):
        """The fired name and the requested name cannot drift apart."""
        from scripts.fetch_ga4_stats import ENGAGEMENT_EVENTS

        tpl = (ROOT / "templates" / "show_page.html.j2").read_text()
        fired = set(re.findall(r"gtag\('event',\s*'([a-z_]+)'", tpl))
        assert "select_personal_upsell" in fired, (
            "the upsell band stopped firing the event this fetcher reads"
        )
        for name in fired:
            if name.startswith("select_"):
                assert name in ENGAGEMENT_EVENTS, (
                    f"{name} is fired by show_page.html.j2 but no fetcher "
                    "reads it — it will record nothing, like "
                    "grok_image_px_max and caption_track_uploaded before it"
                )

    def test_funnel_exposes_upsell_clicks_null_when_unmeasured(self):
        from scripts.build_funnel import _upsell_clicks

        # Not measured: null, never 0.
        assert _upsell_clicks({})["total"] is None
        assert _upsell_clicks({"site_events": None})["total"] is None
        assert _upsell_clicks(None)["configured"] is False
        # Measured and empty: 0, which is a fact.
        assert _upsell_clicks({"site_events": []}) == {
            "configured": True, "total": 0, "by_page": {},
        }

    def test_funnel_counts_upsell_clicks_by_page(self):
        from scripts.build_funnel import _upsell_clicks

        got = _upsell_clicks({"site_events": [
            {"eventName": "select_personal_upsell",
             "pagePath": "/nerra-daily.html", "eventCount": "7"},
            {"eventName": "something_else",
             "pagePath": "/index.html", "eventCount": "99"},
        ]})
        assert got["total"] == 7
        assert got["by_page"] == {"/nerra-daily.html": 7}


class TestEverySignupFormEmitsASource:
    """The other half of the guard that let this ship."""

    FORMS = (
        ("templates/base.html.j2", "footer subscribe"),
        ("templates/join_page.html.j2", "join free"),
        ("templates/network_page.html.j2", "homepage subscribe"),
    )

    @pytest.mark.parametrize("rel,label", FORMS)
    def test_form_sends_a_source(self, rel, label):
        src = (ROOT / rel).read_text()
        assert "/api/subscribe" in src, f"{label}: no subscribe call"
        assert "source:" in src, (
            f"{label} posts to the Worker without a `source`, so its captures "
            "can never appear in api/funnel.json capture.by_source"
        )

    @pytest.mark.parametrize("rel,label", FORMS)
    def test_source_comes_from_the_owning_module(self, rel, label):
        """Never a hardcoded 'src-...' literal: engine.funnel owns the tag."""
        src = (ROOT / rel).read_text()
        assert "capture_source_site" in src, (
            f"{label} should render the tag from the Jinja global fed by "
            "engine.funnel, per CLAUDE.md's funnel-vocabulary rule"
        )
        assert "src-nerranetwork" not in src, (
            f"{label} hardcodes the capture tag instead of importing it"
        )

    def test_the_global_resolves_to_a_tag_the_worker_accepts(self):
        from engine.funnel import SOURCE_SITE, source_tag

        tag = source_tag(SOURCE_SITE)
        assert tag == "src-nerranetwork"
        handlers = (
            ROOT / "workers" / "gallery" / "src" / "handlers.ts"
        ).read_text()
        assert f'"{tag}"' in handlers

    def test_generate_html_registers_the_global(self):
        src = (ROOT / "generate_html.py").read_text()
        assert 'env.globals["capture_source_site"]' in src
        assert "F.source_tag(F.SOURCE_SITE)" in src


class TestTagsReachAnExistingSubscriber:
    """A subscriber already on the list could never acquire a tag."""

    def test_worker_merges_tags_on_a_duplicate(self):
        src = (ROOT / "workers" / "gallery" / "src" / "buttondown.ts").read_text()
        assert "mergeTags" in src
        assert "PATCH" in src, "no PATCH means create-only tagging"
        # The merge must be a union, not a replace: PATCH overwrites the tag
        # array, so sending only the wanted tags would strip a member's show
        # subscriptions on their next footer signup.
        assert "[...existing, ...added]" in src, (
            "tags must be merged with what the subscriber already has"
        )

    def test_merge_failure_never_fails_the_signup(self):
        src = (ROOT / "workers" / "gallery" / "src" / "buttondown.ts").read_text()
        merge = src.split("async function mergeTags(")[1].split("\nasync function")[0]
        assert "return null" in merge and "catch" in merge, (
            "an attribution tag is not worth a 502 on someone's signup"
        )
        # The duplicate path still reports success.
        assert "alreadySubscribed: true" in src


class TestTheTagParseSaysWhichFailureItIs:
    """"No tags" and "tags without counts" produced identical output."""

    def _run(self, monkeypatch, rows):
        import scripts.fetch_buttondown_stats as m

        class _Resp:
            status_code = 200

            @staticmethod
            def json():
                return {"results": rows}

        monkeypatch.setattr(m.requests, "get", lambda *a, **k: _Resp())
        return m

    def test_counts_are_read(self, monkeypatch, caplog):
        m = self._run(monkeypatch, [{"name": "nerra-member",
                                     "subscriber_count": 4}])
        assert m.fetch_tag_counts("k") == {"nerra-member": 4}

    def test_tags_without_counts_warn_incomplete_not_empty(
            self, monkeypatch, caplog):
        m = self._run(monkeypatch, [{"name": "nerra-member"},
                                    {"name": "src-nerranetwork"}])
        with caplog.at_level("WARNING"):
            got = m.fetch_tag_counts("k")
        assert got == {}
        joined = " ".join(r.getMessage() for r in caplog.records)
        assert "INCOMPLETE" in joined, (
            "an endpoint that stopped returning subscriber_count must not be "
            "reported as 'this account has no tags'"
        )

    def test_no_tags_at_all_does_not_warn_incomplete(self, monkeypatch, caplog):
        m = self._run(monkeypatch, [])
        with caplog.at_level("WARNING"):
            assert m.fetch_tag_counts("k") == {}
        joined = " ".join(str(r.message) for r in caplog.records)
        assert "INCOMPLETE" not in joined

    def test_the_warning_no_longer_blames_the_innocent_function(self):
        src = (ROOT / "scripts" / "fetch_buttondown_stats.py").read_text()
        block = src.split("ZERO tags.")[1][:1200]
        assert "NOT the suspect" in block
        assert "list-all" in block, (
            "the warning should name the read-only way to tell the two "
            "causes apart"
        )


class TestMemberMetricsCarryNoPII:
    """The file is committed to a public repo; a name plus a city at this
    scale identifies a person."""

    SPECS = [{
        "token": "feedtok", "tier": "personal_local",
        "shows": ["spacex", "tesla"], "first_name": "Alex",
        "city": "Vancouver, BC", "cities": ["Vancouver, BC"],
        "addons": ["weather"], "default_lineup": False,
    }]

    def test_summary_omits_every_identifying_field(self):
        from scripts.build_member_metrics import summarise

        blob = json.dumps(summarise(self.SPECS))
        for leak in ("Alex", "Vancouver", "feedtok", "@"):
            assert leak not in blob, f"{leak!r} reached the committed metrics"

    def test_summary_reports_the_counts_that_matter(self):
        from scripts.build_member_metrics import summarise

        got = summarise(self.SPECS)
        assert got["paid_active_total"] == 1
        assert got["by_tier"] == {"personal_local": 1}
        assert got["with_city_brief"] == 1
        assert got["shows_chosen"] == {"spacex": 1, "tesla": 1}

    def test_unmeasured_sources_are_null_never_zero(self):
        from scripts.build_member_metrics import summarise

        got = summarise(self.SPECS)
        # Stripe is not wired and free accounts are not in this endpoint.
        assert got["mrr_usd"] is None
        assert got["trialing"] is None
        assert got["free_accounts"] is None

    def test_no_token_is_a_clean_noop_that_never_clobbers(self, tmp_path,
                                                          monkeypatch):
        monkeypatch.delenv("PERSONAL_ADMIN_TOKEN", raising=False)
        out = tmp_path / "member_metrics.json"
        out.write_text('{"configured": true, "paid_active_total": 9}\n')
        from scripts.build_member_metrics import main

        assert main(["--out", str(out)]) == 0
        # Real counts survive a run with no credentials.
        assert json.loads(out.read_text())["paid_active_total"] == 9

    def test_no_token_and_no_file_writes_an_honest_placeholder(
            self, tmp_path, monkeypatch):
        monkeypatch.delenv("PERSONAL_ADMIN_TOKEN", raising=False)
        out = tmp_path / "member_metrics.json"
        from scripts.build_member_metrics import main

        assert main(["--out", str(out)]) == 0
        got = json.loads(out.read_text())
        assert got["configured"] is False
        assert "paid_active_total" not in got, (
            "an unconfigured run must not imply a member count"
        )


class TestMemberMetricsAreWiredEndToEnd:
    def test_nightly_builds_and_commits_the_file(self):
        wf = (ROOT / ".github" / "workflows"
              / "nightly-maintenance.yml").read_text()
        assert "scripts/build_member_metrics.py" in wf
        # The silent-drop class: rebuilt every night and discarded.
        assert "api/member_metrics.json" in wf.split("add-paths:")[1]

    def test_member_metrics_run_before_the_funnel_and_dashboard(self):
        wf = (ROOT / ".github" / "workflows"
              / "nightly-maintenance.yml").read_text()
        assert (wf.index("build_member_metrics.py")
                < wf.index("build_funnel.py")), (
            "a metrics file built after its readers reports yesterday's "
            "numbers — the July 24 content-lake ordering bug"
        )

    def test_dashboard_reads_it(self):
        src = (ROOT / "scripts" / "generate_dashboard.py").read_text()
        assert "member_metrics.json" in src
        assert 'section["membership"]' in src


class TestBlogRelatedPicksAreReproducible:
    def test_same_post_same_picks(self):
        import generate_html as g

        posts = [{"show_slug": "other", "n": i} for i in range(20)]
        first = g._pick_cross_show_related("tesla", posts, seed="ep604")
        again = g._pick_cross_show_related("tesla", posts, seed="ep604")
        assert first == again, (
            "an unseeded draw rewrites every blog post on every regen, so no "
            "refactor can be proven output-neutral"
        )

    def test_different_posts_still_differ(self):
        import generate_html as g

        posts = [{"show_slug": "other", "n": i} for i in range(20)]
        a = g._pick_cross_show_related("tesla", posts, seed="ep604")
        b = g._pick_cross_show_related("tesla", posts, seed="ep605")
        assert a != b, (
            "seeding on the show instead of the post would give every episode "
            "the identical three recommendations"
        )

    def test_the_call_site_passes_the_post_stem(self):
        src = (ROOT / "generate_html.py").read_text()
        assert 'seed=meta["_md_path"].stem' in src


class TestOneButtondownHostPerLanguage:
    def test_python_clients_agree(self):
        """Three Python clients, one host — the writer used to differ."""
        hosts = set()
        for rel in ("engine/newsletter.py",
                    "scripts/fetch_buttondown_stats.py",
                    "scripts/buttondown_tag_subscriber.py"):
            src = (ROOT / rel).read_text()
            hosts |= set(re.findall(
                r"BUTTONDOWN_API_BASE = \"(https://[^\"]+)\"", src))
        assert hosts == {"https://api.buttondown.com/v1"}, hosts
