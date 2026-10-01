"""The credibility surfaces a reader uses to decide whether to trust an AI-made
news show (Oct 1 2026).

Four things, one pass:

1. **The verified-claims panel.** The source-integrity gate has committed a
   ``<stem>_claims.json`` beside every digest since Aug 2026 and no reader
   surface rendered it. Every news post now lists the verified claims with a
   link to each source, says in words when the ledger holds none, and carries
   a one-line provenance (sources, claims checked, sentences removed, who
   voices it) from ``engine.brand`` — the episode's own numbers, never typed.
2. **Corrections.** The policy pages promised "noted in the next episode's
   show notes" with nothing behind the sentence. ``engine/corrections.py``
   reads one YAML per show; the blog prints a dated box, the show notes carry
   the line on the corrected episode AND the next one.
3. **One contact address.** Three trust pages named two mailboxes.
   ``engine.brand.CONTACT_EMAIL`` is the one, and the templates render it.
4. **The gate copy tells the truth.** Two pages said a failed claim blocks the
   episode "on our narrative shows"; since 2026-09-12 the gate is enforced on
   every show and strips. The guard reads ``shows/_defaults.yaml`` so the copy
   and the config fail together.

Every render goes into ``tmp_path`` or a scratch copy of the digest — a
committed page carries the previous chrome (Sep 22 2026 rule).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
import yaml

import generate_html as G
from engine import brand
from engine import corrections as C
from engine import show_notes as SN
from engine.blog import (
    extract_blog_metadata, generate_blog_post_html, load_verified_claims,
    report_error_mailto,
)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"

WITH_CLAIMS = ("mag7", "MAG7_Daily_Ep009_20261001.md")
ZERO_CLAIMS = ("spacex", "SpaceX_Daily_Ep117_20261001.md")

#: The three pages that disagreed with each other, plus the disclosure page
#: that now names the address too.
CONTACT_TEMPLATES = (
    "editorial.html.j2", "faq.html.j2", "contact.html.j2", "ai_disclosure.html.j2",
)
#: The address the site must no longer give a reader anywhere a listener
#: reads (it stays a legitimate RSS owner / operator address elsewhere).
RETIRED_READER_ADDRESS = "patrick@planetterrian.com"


def _markup_only(html: str) -> str:
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S)
    return re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.S)


def _digest(slug: str, name: str) -> Path:
    return ROOT / "digests" / G._SHOW_DIRS.get(slug, slug) / name


def _render(slug: str, md_path: Path) -> str:
    """The real entry point: extract_blog_metadata + generate_blog_post_html
    on the real registry entry and the real Jinja environment."""
    cfg = G.NETWORK_SHOWS[slug]
    text = md_path.read_text(encoding="utf-8")
    meta = extract_blog_metadata(text, slug, md_path.name, file_path=md_path)
    meta["_md_path"] = md_path
    return generate_blog_post_html(text, meta, cfg, G._get_jinja_env())


def _scratch_copy(tmp_path: Path, slug: str, name: str) -> Path:
    """Copy one episode's digest + sidecars into a scratch digest dir so a
    test can add a corrections.yaml beside it without touching the repo."""
    src = _digest(slug, name)
    dst_dir = tmp_path / "digests" / G._SHOW_DIRS.get(slug, slug)
    dst_dir.mkdir(parents=True)
    for f in src.parent.glob(src.stem + "*"):
        shutil.copy(f, dst_dir / f.name)
    return dst_dir / name


# ---------------------------------------------------------------------------
# 1. Provenance: the shape of the line
# ---------------------------------------------------------------------------

class TestEpisodeProvenance:
    def test_full_line(self):
        assert brand.episode_provenance(14, 6, 1) == (
            "Written from 14 sources · 6 claims checked against their sources · "
            "1 unverified sentence removed before publication · voiced with Grok TTS"
        )

    def test_zero_clauses_are_omitted_except_sources(self):
        line = brand.episode_provenance(10, 0, 0)
        assert line == "Written from 10 sources · voiced with Grok TTS"
        assert "0 claims" not in line and "0 unverified" not in line

    def test_no_sources_is_said_not_hidden(self):
        parts = brand.episode_provenance_parts(0)
        assert parts[0] == "No sources listed for this episode"

    def test_singulars(self):
        assert "1 source ·" in brand.episode_provenance(1, 1, 1)
        assert "1 claim checked against its source" in brand.episode_provenance(1, 1, 1)
        assert "1 unverified sentence removed" in brand.episode_provenance(1, 1, 1)

    def test_ai_host_says_so(self):
        line = brand.episode_provenance(5, 2, 0, host_kind="ai")
        assert line.endswith("hosted by an AI, voiced with Grok TTS")
        assert "hosted by an AI" not in brand.episode_provenance(5, 2, 0, host_kind="human")

    def test_the_sidecar_reads_as_the_panel_expects(self):
        claims, summary = load_verified_claims(_digest(*WITH_CLAIMS))
        assert summary["present"] and summary["total"] == 25
        assert summary["verified"] == len(claims) == 23
        assert {"claim", "source_url", "source_domain", "source_title"} <= set(claims[0])
        assert claims[0]["source_domain"] == "macrumors.com"
        claims0, summary0 = load_verified_claims(_digest(*ZERO_CLAIMS))
        assert claims0 == [] and summary0 == {
            "present": True, "total": 0, "verified": 0, "stripped": 0}

    def test_a_missing_sidecar_is_not_an_error(self, tmp_path):
        assert load_verified_claims(tmp_path / "nope.md") == (
            [], {"present": False, "total": 0, "verified": 0, "stripped": 0})
        assert load_verified_claims(None)[0] == []


# ---------------------------------------------------------------------------
# 1b. The rendered panel + line
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def post_with_claims():
    return _markup_only(_render(WITH_CLAIMS[0], _digest(*WITH_CLAIMS)))


@pytest.fixture(scope="module")
def post_zero_claims():
    return _markup_only(_render(ZERO_CLAIMS[0], _digest(*ZERO_CLAIMS)))


class TestVerifiedClaimsPanel:
    def test_the_panel_is_a_collapsed_details_with_the_count(self, post_with_claims):
        m = re.search(r'<section class="blog-claims"[^>]*>(.*?)</section>',
                      post_with_claims, re.S)
        assert m, "no verified-claims section on a post whose ledger holds 23 claims"
        panel = m.group(1)
        assert "<details>" in panel and "<details open" not in panel
        assert "Verified claims (23)" in panel

    def test_every_row_is_the_claim_with_a_link_to_its_source(self, post_with_claims):
        claims, _ = load_verified_claims(_digest(*WITH_CLAIMS))
        panel = re.search(r'<section class="blog-claims".*?</section>',
                          post_with_claims, re.S).group(0)
        for c in claims:
            assert c["claim"] in panel
            assert f'href="{c["source_url"]}"' in panel
            assert f">{c['source_domain']}</a>" in panel
        assert panel.count("<li>") == len(claims)

    def test_it_sits_under_the_sources_section(self, post_with_claims):
        assert post_with_claims.index('class="blog-sources"') \
            < post_with_claims.index('class="blog-claims"')

    def test_zero_claims_renders_the_honest_line_not_nothing(self, post_zero_claims):
        assert "No individual claims were ledger-verified for this episode; " \
               "every item above links its source." in post_zero_claims
        assert "Verified claims (" not in post_zero_claims

    def test_the_provenance_line_sits_under_the_badge(self, post_with_claims, post_zero_claims):
        for html, expect in (
            (post_with_claims, "23 claims checked against their sources"),
            (post_zero_claims, "Written from 10 sources"),
        ):
            m = re.search(r'<p class="nn-iv-provenance nn-ep-provenance">(.*?)</p>', html, re.S)
            assert m, "no provenance line"
            line = re.sub(r"<[^>]+>", "", m.group(1))
            assert expect in line
            assert "voiced with Grok TTS" in line
            assert html.index('class="nn-ai-badge"') < m.start()
        assert "claims checked" not in post_zero_claims

    def test_the_report_an_error_link_prefills_show_and_episode(self, post_with_claims):
        m = re.search(r'<a href="(mailto:[^"]+)">Report an error</a>', post_with_claims)
        assert m, "no Report an error link"
        href = m.group(1)
        assert href.startswith(f"mailto:{brand.CONTACT_EMAIL}?subject=")
        assert "MAG%207%20Daily%20Ep9" in href
        assert "blog/mag7/ep009.html" in href
        assert href == report_error_mailto(
            "MAG 7 Daily", 9, "https://nerranetwork.com/blog/mag7/ep009.html")

    def test_the_feedback_row_uses_the_one_address(self, post_with_claims):
        assert RETIRED_READER_ADDRESS not in post_with_claims
        assert post_with_claims.count(f"mailto:{brand.CONTACT_EMAIL}") >= 3


# ---------------------------------------------------------------------------
# 2. Corrections
# ---------------------------------------------------------------------------

def _write_corrections(show_dir: Path, entries: list) -> Path:
    path = C.corrections_path(show_dir)
    path.write_text(yaml.safe_dump(entries, allow_unicode=True), encoding="utf-8")
    return path


def _touch_digest(show_dir: Path, ep: int, ymd: str) -> None:
    (show_dir / f"Show_Ep{ep:03d}_{ymd}.md").write_text("# Show\n", encoding="utf-8")


class TestCorrectionsRecord:
    def test_round_trip(self, tmp_path):
        _write_corrections(tmp_path, [
            {"episode": 117, "date": "2026-10-01",
             "text": "The booster flew its 23rd mission, not its 32nd.", "where": "both"},
            {"episode": 110, "date": "2026-09-28", "text": "Wrong date.", "where": "digest"},
        ])
        rows = C.load_corrections(tmp_path)
        assert [r["episode"] for r in rows] == [110, 117]  # oldest filing first
        assert C.corrections_for(tmp_path, 117) == [{
            "episode": 117, "date": "2026-10-01",
            "text": "The booster flew its 23rd mission, not its 32nd.", "where": "both"}]
        assert C.corrections_for(tmp_path, 5) == []

    def test_a_yaml_date_is_accepted(self, tmp_path):
        C.corrections_path(tmp_path).write_text(
            "- episode: 3\n  date: 2026-10-01\n  text: t\n", encoding="utf-8")
        assert C.corrections_for(tmp_path, 3)[0]["date"] == "2026-10-01"

    def test_bad_entries_are_skipped_never_raised(self, tmp_path, caplog):
        _write_corrections(tmp_path, [
            {"episode": "x", "date": "2026-10-01", "text": "t"},
            {"episode": 1, "date": "yesterday", "text": "t"},
            {"episode": 2, "date": "2026-10-01", "text": ""},
            {"episode": 3, "date": "2026-10-01", "text": "ok", "where": "somewhere"},
            "not a mapping",
        ])
        rows = C.load_corrections(tmp_path)
        assert [(r["episode"], r["where"]) for r in rows] == [(3, "digest")]
        C.corrections_path(tmp_path).write_text("just: a: broken: yaml: [", encoding="utf-8")
        assert C.load_corrections(tmp_path) == []

    def test_missing_file_is_empty(self, tmp_path):
        assert C.load_corrections(tmp_path) == []
        assert C.corrections_for(tmp_path, 1) == []
        assert C.corrections_to_carry(tmp_path, 1) == []

    def test_recent_window(self, tmp_path):
        from datetime import date
        _write_corrections(tmp_path, [
            {"episode": 1, "date": "2026-08-01", "text": "old"},
            {"episode": 2, "date": "2026-09-25", "text": "new"},
        ])
        rows = C.recent_corrections(tmp_path, days=30, today=date(2026, 10, 1))
        assert [r["episode"] for r in rows] == [2]

    def test_where_values_are_the_closed_set(self):
        assert C.WHERE_VALUES == ("digest", "audio", "both")


class TestNextEpisodeCarriesTheCorrection:
    """A correction filed on D against episode E is carried by the FIRST
    episode above E that publishes on or after D — once, and never by E."""

    def test_the_next_episode_carries_it(self, tmp_path):
        _touch_digest(tmp_path, 117, "20261001")
        _write_corrections(tmp_path, [
            {"episode": 117, "date": "2026-10-02", "text": "The booster flew its 23rd mission."}])
        assert C.corrections_to_carry(tmp_path, 117) == []  # never the episode itself
        carried = C.corrections_to_carry(tmp_path, 118, "2026-10-02")
        assert [c["episode"] for c in carried] == [117]

    def test_only_once(self, tmp_path):
        _touch_digest(tmp_path, 117, "20261001")
        _touch_digest(tmp_path, 118, "20261002")
        _write_corrections(tmp_path, [
            {"episode": 117, "date": "2026-10-02", "text": "t"}])
        assert [c["episode"] for c in C.corrections_to_carry(tmp_path, 118)] == [117]
        assert C.corrections_to_carry(tmp_path, 119, "2026-10-03") == []

    def test_an_episode_that_went_out_before_the_filing_does_not_carry_it(self, tmp_path):
        _touch_digest(tmp_path, 117, "20261001")
        _touch_digest(tmp_path, 118, "20261002")
        _write_corrections(tmp_path, [
            {"episode": 117, "date": "2026-10-03", "text": "t"}])
        assert C.corrections_to_carry(tmp_path, 118) == []
        assert [c["episode"] for c in C.corrections_to_carry(tmp_path, 119, "2026-10-03")] == [117]

    def test_noted_in_pins_it(self, tmp_path):
        _touch_digest(tmp_path, 117, "20261001")
        _write_corrections(tmp_path, [
            {"episode": 117, "date": "2026-10-02", "text": "t", "noted_in": 120}])
        assert C.corrections_to_carry(tmp_path, 118, "2026-10-02") == []
        assert [c["episode"] for c in C.corrections_to_carry(tmp_path, 120, "2026-10-04")] == [117]

    def test_digest_dates_read_the_committed_filenames(self):
        dates = C.digest_dates(_digest(*ZERO_CLAIMS).parent)
        assert dates[117] == "2026-10-01"


class TestShowNotesExtras:
    def test_nothing_filed_means_an_unchanged_description(self, tmp_path):
        assert SN.build_show_notes_extras(tmp_path, 117) == ""
        assert SN.append_show_notes_extras("desc", tmp_path, 117) == "desc"
        # And on the real tree, today: no show has a corrections file yet.
        assert SN.build_show_notes_extras(_digest(*ZERO_CLAIMS).parent, 117) == ""

    def test_the_corrected_episode_and_the_next_one(self, tmp_path):
        _touch_digest(tmp_path, 117, "20261001")
        _write_corrections(tmp_path, [
            {"episode": 117, "date": "2026-10-02",
             "text": "The booster flew its 23rd mission, not its 32nd."}])
        own = SN.build_show_notes_extras(tmp_path, 117)
        assert own == "**Correction (2026-10-02):** The booster flew its 23rd mission, not its 32nd."
        nxt = SN.build_show_notes_extras(tmp_path, 118, episode_date="2026-10-02")
        assert nxt == "**Correction to episode 117:** The booster flew its 23rd mission, not its 32nd."
        assert SN.append_show_notes_extras("Body.", tmp_path, 118, episode_date="2026-10-02") \
            == "Body.\n\n" + nxt

    def test_the_line_survives_the_rss_markdown_renderer(self, tmp_path):
        from engine.publisher import _markdown_to_rss_html
        _touch_digest(tmp_path, 117, "20261001")
        _write_corrections(tmp_path, [{"episode": 117, "date": "2026-10-02", "text": "Fixed."}])
        html = _markdown_to_rss_html(SN.build_show_notes_extras(tmp_path, 118, episode_date="2026-10-02"))
        assert html == "<b>Correction to episode 117:</b> Fixed."

    def test_russian_labels(self, tmp_path):
        _touch_digest(tmp_path, 117, "20261001")
        _write_corrections(tmp_path, [{"episode": 117, "date": "2026-10-02", "text": "Исправлено."}])
        assert SN.build_show_notes_extras(tmp_path, 117, language="ru").startswith("**Исправление (2026-10-02):**")
        assert SN.build_show_notes_extras(tmp_path, 118, language="ru", episode_date="2026-10-02") \
            .startswith("**Исправление к выпуску 117:**")


class TestCorrectionBoxOnThePost:
    def test_a_dated_box_at_the_top_of_the_affected_post(self, tmp_path):
        md = _scratch_copy(tmp_path, *ZERO_CLAIMS)
        _write_corrections(md.parent, [
            {"episode": 117, "date": "2026-10-02",
             "text": "The booster flew its 23rd mission, not its 32nd.", "where": "audio"},
            {"episode": 116, "date": "2026-10-02", "text": "Not this post."},
        ])
        html = _markup_only(_render(ZERO_CLAIMS[0], md))
        m = re.search(r'<aside class="nn-correction".*?</aside>', html, re.S)
        assert m, "no correction box"
        box = m.group(0)
        assert "2026-10-02" in box
        assert "The booster flew its 23rd mission, not its 32nd." in box
        assert "the spoken episode carried this error" in box
        assert "Not this post." not in html
        # Above the article body, below the hero.
        assert html.index('class="blog-hero"') < m.start() < html.index('class="blog-body-lang"')

    def test_no_box_when_nothing_is_filed(self, post_zero_claims):
        assert 'class="nn-correction"' not in post_zero_claims


# ---------------------------------------------------------------------------
# 3. One contact address, one owner
# ---------------------------------------------------------------------------

class TestOneContactAddress:
    def test_brand_owns_it(self):
        assert brand.CONTACT_EMAIL == "hello@nerranetwork.com"
        assert brand.CONTACT_EMAIL in brand.MIRA_FIRST_CLAIM_FOOTNOTE

    @pytest.mark.parametrize("name", CONTACT_TEMPLATES)
    def test_no_trust_page_names_the_retired_address(self, name):
        src = (TEMPLATES / name).read_text(encoding="utf-8")
        assert RETIRED_READER_ADDRESS not in src, f"{name} still names {RETIRED_READER_ADDRESS}"

    @pytest.mark.parametrize("name", CONTACT_TEMPLATES)
    def test_every_address_renders_from_the_context_var(self, name):
        """The literal appears ONLY as the ``default`` of the ``contact_email``
        variable (the generators do not thread it yet; the one-line global
        registration in generate_html.py removes the need), and that default
        is pinned to the brand constant so the fallback cannot drift either."""
        src = (TEMPLATES / name).read_text(encoding="utf-8")
        # The listener address only: contact.html.j2 also lists a press
        # mailbox, which is a different address for a different reader.
        pattern = re.escape(brand.CONTACT_EMAIL)
        assert re.search(pattern, src), f"{name} names no contact address"
        for m in re.finditer(pattern, src):
            window = src[max(0, m.start() - 40):m.start()]
            assert "contact_email | default('" in window, (
                f"{name}: {m.group(0)} is a literal, not the contact_email variable")
            assert m.group(0) == brand.CONTACT_EMAIL

    def test_the_blog_post_threads_it_from_the_engine(self):
        src = (TEMPLATES / "blog_post.html.j2").read_text(encoding="utf-8")
        assert RETIRED_READER_ADDRESS not in src
        assert "@nerranetwork.com" not in src  # no literal at all: engine.blog passes it
        assert "mailto:{{ contact_email }}" in src
        assert "report_error_mailto" in src

    def test_the_pages_still_render(self, tmp_path, capsys):
        G.generate_legal_page("ai_disclosure", dry_run=True)
        G.generate_editorial_page(dry_run=True, output_dir=tmp_path)
        G.generate_faq_page(dry_run=True)
        G.generate_contact_page(dry_run=True)
        capsys.readouterr()


# ---------------------------------------------------------------------------
# 4. The verification copy matches the configured gate
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def gate_config():
    data = yaml.safe_load((ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
    return data["source_integrity"]


class TestGateCopyTellsTheTruth:
    def test_the_network_default_is_enforce_strip(self, gate_config):
        assert gate_config["enabled"] is True
        assert gate_config["enforce"] is True
        assert gate_config["on_failure"] == "strip"

    @pytest.mark.parametrize("name", ["ai_disclosure.html.j2", "editorial.html.j2"])
    def test_the_copy_says_every_show_and_removed(self, name, gate_config):
        src = (TEMPLATES / name).read_text(encoding="utf-8")
        passage = re.search(r"Source-integrity gate.*?</(?:li|p)>", src, re.S).group(0)
        flat = " ".join(passage.split())
        if gate_config["enforce"] and gate_config["on_failure"] == "strip":
            assert "every show" in flat, f"{name}: the gate is enforced on every show"
            assert "removed" in flat, f"{name}: strip mode removes the sentence"
        # The Sep 12 state, exactly: one repair pass, unreachable = failure,
        # item coverage, reviewer notes, narrative shows block.
        for phrase in ("repair pass", "cannot reach", "covered by a verified claim",
                       "note", "narrative shows"):
            assert phrase in flat, f"{name}: missing '{phrase}'"
        # And no more than that.
        assert "narrative shows a failed claim blocks" not in flat
        assert "On our narrative shows a failed claim blocks the episode" not in flat
        assert "reviewed by a human" not in flat
        assert "every episode is reviewed" not in flat

    @pytest.mark.parametrize("name", ["ai_disclosure.html.j2", "editorial.html.j2", "faq.html.j2"])
    def test_the_corrections_promise_names_every_surface(self, name):
        flat = " ".join((TEMPLATES / name).read_text(encoding="utf-8").split())
        assert "next episode's show notes" in flat or "following episode's show notes" in flat
        assert "top of the episode's page" in flat
        assert "never edited silently" in flat
