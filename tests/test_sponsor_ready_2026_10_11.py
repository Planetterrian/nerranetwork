"""Guards for the Oct 11 2026 sponsor-readiness pass.

The network promised "ad-free" / "no ads" on every surface while the
operator moved to sponsorship. The promise is gone, the sponsor policy has
ONE owner (``engine.brand``), ``sponsor.html`` renders measured numbers, and
the same pass made signups measurable, grounded the narrative queues in
sources, enforced the FR dub gate, backfilled Age of AI videos and fixed
Prediction Markets' Friday Week's Board.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_AD_FREE_RE = re.compile(
    r"\bad[- ]free\b|\bno ads\b|\bzero ads\b|\bwithout ads\b|\bnever (?:any )?ads\b",
    re.IGNORECASE)
# An outside site's own description (generate_html's health resource list)
# is not a claim about this network.
_ALLOWED = ("Examine.com",)


def _source_files():
    yield from (ROOT / "templates").glob("*.j2")
    yield from (p for p in (ROOT / "engine").glob("*.py") if p.name != "brand.py")
    yield from (ROOT / "shows" / "prompts").rglob("*.txt")
    yield from (ROOT / "shows" / "hooks").glob("*.py")
    yield ROOT / "generate_html.py"
    yield ROOT / "assets" / "js" / "footer-subscribe.js"


class TestNoAdFreePromise:
    def test_no_surface_promises_no_ads(self):
        hits = []
        for path in _source_files():
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if _AD_FREE_RE.search(line) and not any(a in line for a in _ALLOWED):
                    hits.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:100]}")
        assert not hits, "ad-free promise still on a surface:\n" + "\n".join(hits)


class TestSponsorPolicyHasOneOwner:
    def test_policy_shape(self):
        from engine import brand
        policy = brand.sponsor_policy()
        assert policy["summary"] == brand.SPONSOR_POLICY_SUMMARY
        assert policy["email"] == brand.CONTACT_EMAIL
        assert len(policy["rules"]) >= 4
        text = " ".join(r["title"] + " " + r["body"] for r in policy["rules"]).lower()
        assert "labelled" in text and "free" in text

    def test_templates_render_the_policy_never_type_it(self):
        from engine import brand
        for path in (ROOT / "templates").glob("*.j2"):
            body = path.read_text(encoding="utf-8")
            assert brand.SPONSOR_POLICY_SUMMARY not in body, path.name
            for title, _b in brand.SPONSOR_POLICY_RULES:
                assert title not in body, f"{path.name} types rule {title!r}"


class TestSponsorPage:
    def test_renders_numbers_rules_and_contact(self, tmp_path):
        import generate_html
        from engine import brand
        generate_html.generate_sponsor_page(output_dir=tmp_path)
        html = (tmp_path / "sponsor.html").read_text(encoding="utf-8")
        assert "The audience, measured" in html
        for title, _b in brand.SPONSOR_POLICY_RULES:
            assert title in html
        assert f"mailto:{brand.SPONSOR_EMAIL}" in html
        assert "editorial.html#sponsors" in html

    def test_unmeasured_is_a_dash_never_zero(self, tmp_path, monkeypatch):
        import json
        import generate_html
        api = tmp_path / "api"
        api.mkdir()
        (api / "audience_headline.json").write_text(json.dumps({
            "as_of": "2026-10-11",
            "network": {"downloads_30d": None, "downloads_7d": 120},
        }))
        monkeypatch.setattr(generate_html, "ROOT", tmp_path)
        aud = generate_html._sponsor_audience()
        assert aud["downloads_30d"] == "—"
        assert aud["downloads_7d"] == "120"

    def test_sitemap_footer_and_static_pages_carry_it(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert '"sponsor.html"' in src
        assert "generate_sponsor_page(" in src.split("def generate_static_pages", 1)[1]
        base = (ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8")
        assert "sponsor.html" in base

    def test_editorial_page_carries_the_rules(self):
        body = (ROOT / "templates" / "editorial.html.j2").read_text(encoding="utf-8")
        assert 'id="sponsors"' in body and "sponsor_policy.rules" in body


class TestSignupMeasurement:
    def test_footer_form_fires_the_conversion(self):
        js = (ROOT / "assets" / "js" / "footer-subscribe.js").read_text(encoding="utf-8")
        assert "fireGa('newsletter_signup'" in js
        assert "transport_type: 'beacon'" in js

    def test_fetcher_reads_every_conversion_event(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import fetch_ga4_stats
        assert "newsletter_signup" in fetch_ga4_stats.CONVERSION_EVENTS
        assert "gallery_subscribe" in fetch_ga4_stats.CONVERSION_EVENTS
        assert "select_personal_upsell" not in fetch_ga4_stats.CONVERSION_EVENTS


class TestRestockGrounding:
    def _load(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import restock_topic_queues
        return restock_topic_queues

    def test_keeps_only_sourced_candidates(self):
        mod = self._load()
        results = {
            "A": [{"url": "https://a.org/1"}, {"url": "https://b.org/2"}],
            "B": [{"url": "https://x.com/someone/status/1"}, {"url": "https://c.org/3"}],
            "C": RuntimeError("search down"),
        }

        def research(title, brief, max_results=6):
            r = results[title]
            if isinstance(r, Exception):
                raise r
            return r

        entries = [{"title": t, "brief": "b"} for t in ("A", "B", "C")]
        kept = mod.ground_candidates(entries, 3, research=research)
        assert [e["title"] for e in kept] == ["A"]
        assert kept[0]["sources"] == ["https://a.org/1", "https://b.org/2"]

    def test_stops_at_needed(self):
        mod = self._load()
        entries = [{"title": str(i), "brief": "b"} for i in range(5)]
        kept = mod.ground_candidates(
            entries, 2, research=lambda *a, **k: [{"url": "https://a.org"}, {"url": "https://b.org"}])
        assert len(kept) == 2


class TestQueueSourceAudit:
    @pytest.mark.parametrize("name", ["unintended_consequences", "first_principles"])
    def test_audited_entries_carry_their_sources(self, name):
        data = yaml.safe_load((ROOT / "shows" / "topic_queues" / f"{name}.yaml").read_text())
        topics = data["queue"] if isinstance(data, dict) else data
        audited = [t for t in topics if t.get("source_audit")]
        assert audited, f"{name}: no audited entries"
        for t in audited:
            assert t["source_audit"] in ("keep", "fix"), t["id"]
            assert t.get("sources"), t["id"]
            if t["source_audit"] == "fix":
                assert "SOURCE AUDIT (2026-10-11)" in t["brief"], t["id"]

    def test_restock_prompts_ban_unsourced_figures(self):
        for name in ("unintended_consequences_restock.txt", "first_principles_restock.txt"):
            body = (ROOT / "shows" / "prompts" / name).read_text(encoding="utf-8").lower()
            assert "never invent" in body


class TestDubGateEnforce:
    def test_only_calibrated_languages_enforce(self):
        from engine.spoken_text_gate import CALIBRATED_LANGUAGES, resolve_gate_mode
        assert "fr" in CALIBRATED_LANGUAGES
        assert "ru" not in CALIBRATED_LANGUAGES
        assert resolve_gate_mode("enforce", "fr") == "enforce"
        assert resolve_gate_mode("enforce", "ru") == "shadow"


class TestAgeOfAiVideoBackfill:
    def test_plan_skips_recorded_episodes(self, tmp_path, monkeypatch):
        sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
        import json
        import backfill_videos as bv

        class Show:
            slug = "age_of_ai"
            name = "The Age of AI"
            audio_subdir = "digests/age_of_ai"
            summaries_path = tmp_path / "summaries.json"

        Show.summaries_path.write_text(json.dumps({"episodes": [
            {"episode": 1, "date": "2026-09-01", "guest": "A", "audio_url": "https://x/1.mp3"},
            {"episode": 2, "date": "2026-09-08", "guest": "B", "audio_url": "https://x/2.mp3"},
            {"episode": 3, "date": "2026-09-15", "guest": "C"},
        ]}))
        (tmp_path / "digests" / "age_of_ai").mkdir(parents=True)
        (tmp_path / "digests" / "age_of_ai" / "youtube_videos.json").write_text(
            json.dumps([{"episode": 1}]))
        monkeypatch.setattr(bv, "ROOT", tmp_path)
        rows = bv.plan(Show)
        assert [r["episode"] for r in rows] == [2]

    def test_dry_run_is_the_default(self):
        wf = (ROOT / ".github" / "workflows" / "nerra_voices_backfill_videos.yml").read_text()
        assert "--apply" in wf and "inputs.apply" in wf


class TestWeekBoard:
    """Prediction Markets' Friday Week's Board was empty on 10-02 and 10-09:
    the parser wanted ``Question: NN% implied probability`` and the Board is
    written as prose."""

    def test_prose_board_lines_parse(self):
        from engine.board_week import board_lines
        md = (
            "### The Board\n"
            "1. Which party wins the Senate: Democrats at a 62 percent implied "
            "probability, down 3 points; Kalshi; 1.6 million contracts.\n"
            "2. Will one party sweep both chambers? On Polymarket, a sweep was "
            "priced at 61 cents, a 61 percent implied probability.\n"
        )
        rows = board_lines(md)
        assert [(r["prob"], r["venue"]) for r in rows] == [(62.0, "Kalshi"), (61.0, "Polymarket")]

    @pytest.mark.parametrize("friday", ["2026-10-02", "2026-10-09"])
    def test_committed_fridays_have_a_board(self, friday):
        from engine.board_week import week_board_block
        out = week_board_block(ROOT / "digests" / "prediction_markets",
                               dt.date.fromisoformat(friday), [])
        assert out.count("\n- ") >= 4
