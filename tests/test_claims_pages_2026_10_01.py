"""The public claims-and-corrections ledger (Oct 1 2026).

Operator direction: a public, transparent claims-and-corrections process
for every show, so the network can publish timely news — the model's
training data lags the 24-hour cycle, so a story newer than the model is
verified against its source, never against memory — and SHOW each claim's
verification status instead of removing sentences. The gate's failure
policy moved from ``strip`` to ``flag`` the same day (``shows/_defaults.yaml``).

What this file pins:

1. ``generate_claims_pages`` renders for real: ``claims.html`` and one
   ``claims/<slug>.html`` per show with a YAML; mag7's page shows Ep009's
   verified badges; a registry-only show is "not applicable".
2. A flag-era sidecar (``policy_version: 2``, every entry with a status)
   renders the amber badge, the reason in plain words, and the
   verified-later clock — on the ledger page AND on the blog post's panel.
3. The process copy has ONE owner (``engine.brand.CLAIMS_PROCESS_STEPS``,
   the ``claims_process`` Jinja global): no template types a step title.
4. The policy-truth guard reads ``_defaults.yaml``: the trust pages may not
   claim removal while the default is ``flag``, nor publish-and-mark while
   it is ``strip``. Both branches are exercised against a scratch YAML.
5. The sitemap lists exactly the pages the generator writes (never a glob);
   nav + footer carry the link; no ``utm_`` on any of these internal links.

Every render goes into ``tmp_path`` (the Sep 22 2026 rule: a committed page
carries the previous chrome).
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

import pytest
import yaml

import generate_html as G
from engine import brand
from engine import claims_ledger as L
from engine.blog import (
    extract_blog_metadata, generate_blog_post_html, load_verified_claims,
)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"

#: The window is pinned to the day the pass shipped so the committed
#: episodes asserted on below stay inside it (2026-10-01).
TODAY = date(2026, 10, 1)

MAG7 = ("mag7", "MAG7_Daily_Ep009_20261001.md")

#: A flag-era sidecar: every entry carries a status, two of them marked,
#: one upgraded by the nightly re-check.
FLAG_ERA_SIDECAR = {
    "version": 1,
    "gate": {
        "passed": True, "ledger_present": True, "policy_version": 2,
        "claims_total": 4, "verified_count": 2, "flagged_count": 2,
        "flagged_sentences": [
            "The regulator gazetted the rule on Tuesday.",
            "Researchers found the birds were three times more likely to carry parasites.",
        ],
        "stripped_sentences": [],
    },
    "claims": [
        {"id": "c1", "claim": "Microsoft began disabling Exchange Web Services by default.",
         "source_url": "https://www.macrumors.com/2026/10/01/x/", "status": "verified"},
        {"id": "c2", "claim": "Crew-13 entered quarantine on Monday.",
         "source_url": "https://www.wesh.com/article/crew-13/", "status": "verified_later",
         "verified_at": "2026-10-03T02:11:00Z", "first_status": "unverified_quote_mismatch"},
        {"id": "c3", "claim": "The regulator gazetted the rule on Tuesday.",
         "source_url": "https://www.officialgazette.gov.ph/2026/09/30/rule/",
         "status": "unverified_unreachable", "reason": "HTTP 403"},
        {"id": "c4", "claim": "Researchers found the birds were three times more likely to carry parasites.",
         "status": "unverified_uncovered"},
    ],
}


def _markup_only(html: str) -> str:
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S)
    return re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.S)


def _badges(html: str, status: str) -> int:
    return len(re.findall(rf'class="nn-claims-badge nn-claims-badge--{status}"', html))


def _write_flag_era_tree(tmp_path: Path) -> Path:
    """A scratch ``digests/`` tree holding one flag-era mag7 sidecar."""
    root = tmp_path / "digests"
    show_dir = root / "mag7"
    show_dir.mkdir(parents=True)
    (show_dir / "MAG7_Daily_Ep900_20261001.md").write_text("# MAG 7 Daily\n", encoding="utf-8")
    (show_dir / "MAG7_Daily_Ep900_20261001_claims.json").write_text(
        json.dumps(FLAG_ERA_SIDECAR, indent=1), encoding="utf-8")
    (show_dir / "corrections.yaml").write_text(yaml.safe_dump([
        {"episode": 900, "date": "2026-10-01",
         "text": "The rule was gazetted on Wednesday, not Tuesday.", "where": "digest"},
    ]), encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# 1. The pages render for real
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    out = tmp_path_factory.mktemp("claims_pages")
    written = G.generate_claims_pages(output_dir=out, today=TODAY)
    return out, written


class TestPagesRender:
    def test_the_network_page_and_one_page_per_yaml_show(self, rendered):
        out, written = rendered
        assert written[0] == "claims.html"
        assert (out / "claims.html").is_file()
        yaml_shows = [s for s in G.NETWORK_SHOWS if (G.SHOWS_DIR / f"{s}.yaml").is_file()]
        assert yaml_shows, "no show has a YAML?"
        for slug in yaml_shows:
            assert (out / "claims" / f"{slug}.html").is_file(), f"no page for {slug}"
            assert f"claims/{slug}.html" in written
        assert written == G.claims_page_paths()
        # Nerra Daily is registry-only: no page, a not-applicable row.
        assert "nerra_daily" not in yaml_shows
        assert not (out / "claims" / "nerra_daily.html").exists()

    def test_mag7_ep009_shows_its_verified_badges(self, rendered):
        out, _ = rendered
        html = _markup_only((out / "claims" / "mag7.html").read_text(encoding="utf-8"))
        block = re.search(r"<details class=\"nn-claims-episode\"[^>]*>\s*<summary>\s*"
                          r"<span class=\"nn-claims-episode-title\">Episode 9</span>.*?</details>",
                          html, re.S)
        assert block, "no Episode 9 block on mag7's page"
        assert _badges(block.group(0), "verified") >= 20
        assert "macrumors.com" in block.group(0)
        assert 'href="../blog/mag7/ep009.html"' in block.group(0)

    def test_the_network_page_carries_the_process_the_totals_and_every_show(self, rendered):
        out, _ = rendered
        html = _markup_only((out / "claims.html").read_text(encoding="utf-8"))
        for title, _text in brand.CLAIMS_PROCESS_STEPS:
            assert title in html, f"step '{title}' missing from claims.html"
        for slug, cfg in G.NETWORK_SHOWS.items():
            assert cfg["name"] in html, f"{cfg['name']} missing from the show table"
        assert 'href="claims/mag7.html"' in html
        assert "Not applicable" in html
        assert L.NOT_APPLICABLE["nerra_daily"][:40] in html
        assert "<title>Claims &amp; corrections | Nerra Network</title>" in html \
            or "<title>Claims & corrections | Nerra Network</title>" in html

    def test_the_voices_show_page_says_why_it_has_no_ledger(self, rendered):
        out, _ = rendered
        html = (out / "claims" / "age_of_ai.html").read_text(encoding="utf-8")
        assert L.NOT_APPLICABLE["age_of_ai"][:40] in html
        assert 'class="nn-claims-episode"' not in html

    def test_no_internal_link_carries_a_utm(self, rendered):
        out, _ = rendered
        for p in [out / "claims.html", out / "claims" / "mag7.html"]:
            html = p.read_text(encoding="utf-8")
            for href in re.findall(r'href="([^"]+)"', html):
                if "nerranetwork.com" in href or not href.startswith("http"):
                    assert "utm_" not in href, f"{p.name}: internal link with utm: {href}"

    def test_dry_run_writes_nothing(self, tmp_path, capsys):
        assert G.generate_claims_pages(dry_run=True, output_dir=tmp_path, today=TODAY)
        assert not (tmp_path / "claims.html").exists()
        capsys.readouterr()


# ---------------------------------------------------------------------------
# 2. A flag-era sidecar renders every status
# ---------------------------------------------------------------------------

class TestFlagEraSidecar:
    @pytest.fixture()
    def page(self, tmp_path):
        root = _write_flag_era_tree(tmp_path)
        out = tmp_path / "site"
        G.generate_claims_pages(output_dir=out, digests_root=root, today=TODAY, slugs=["mag7"])
        return _markup_only((out / "claims" / "mag7.html").read_text(encoding="utf-8"))

    def test_the_reader_reads_every_status(self, tmp_path):
        root = _write_flag_era_tree(tmp_path)
        ledger = L.show_ledger("mag7", today=TODAY, digests_root=root,
                               blog_url_for=lambda s, e: "")
        assert ledger["applicable"] and len(ledger["rows"]) == 1
        row = ledger["rows"][0]
        assert row["episode"] == 900 and row["policy_version"] == 2
        assert row["counts"] == {
            "total": 4, "verified": 2, "verified_later": 1, "flagged": 2,
            "by_status": {"verified": 1, "verified_later": 1,
                          "unverified_unreachable": 1, "unverified_uncovered": 1}}
        statuses = {c["id"]: c for c in row["claims"]}
        assert statuses["c2"]["verified_at"] == "2026-10-03"
        assert statuses["c2"]["first_label"] == "Published, quote not matched"
        assert statuses["c3"]["reason"] == "HTTP 403"
        assert statuses["c4"]["source_url"] == "" and statuses["c4"]["is_flagged"]
        assert [c["episode"] for c in row["corrections"]] == [900]
        t = ledger["totals"]
        assert (t["claims"], t["verified"], t["flagged"], t["verified_later"]) == (4, 2, 2, 1)
        assert t["verified_share_pct"] == 50.0 and t["flagged_share_pct"] == 50.0
        assert t["flagged_by_reason"]["unverified_unreachable"]["count"] == 1
        assert t["corrections"] == 1

    def test_amber_badge_reason_and_the_later_verified_clock(self, page):
        assert _badges(page, "unverified_unreachable") >= 1
        assert _badges(page, "unverified_uncovered") >= 1
        assert _badges(page, "verified_later") >= 1
        # The reason in plain words, from the one owner, plus the gate's own.
        assert brand.CLAIMS_STATUS_LABELS["unverified_unreachable"][1] in page
        assert "(HTTP 403)" in page
        assert "Published, not yet verified" in page
        # The later-verified entry carries the clock icon and its date.
        later = re.search(r'nn-claims-badge--verified_later"[^>]*>(.*?)</span>', page, re.S)
        assert later and "<svg" in later.group(1) and "<circle" in later.group(1)
        assert "verified 2026-10-03, first published, quote not matched" in page
        # Corrections, dated and badged blue.
        assert _badges(page, "correction") >= 1
        assert "The rule was gazetted on Wednesday, not Tuesday." in page
        assert "2026-10-01" in page

    def test_the_status_colours_are_tokens_not_inline(self, page):
        css = (ROOT / "styles" / "main.css").read_text(encoding="utf-8")
        for token in ("--nn-claims-verified", "--nn-claims-later", "--nn-claims-unverified",
                      "--nn-claims-failed", "--nn-claims-correction"):
            assert f"{token}:" in css, f"{token} not defined in main.css"
        assert ".nn-claims-badge--verified_later { color: var(--nn-claims-later); }" in css
        assert ".nn-claims-badge--correction { color: var(--nn-claims-correction); }" in css
        assert re.search(r'class="nn-claims-badge[^"]*"[^>]*style=', page) is None


# ---------------------------------------------------------------------------
# 3. The blog post's panel renders status badges + the ledger link
# ---------------------------------------------------------------------------

def _digest(slug: str, name: str) -> Path:
    return ROOT / "digests" / G._SHOW_DIRS.get(slug, slug) / name


def _render_post(slug: str, md_path: Path) -> str:
    cfg = G.NETWORK_SHOWS[slug]
    text = md_path.read_text(encoding="utf-8")
    meta = extract_blog_metadata(text, slug, md_path.name, file_path=md_path)
    meta["_md_path"] = md_path
    return _markup_only(generate_blog_post_html(text, meta, cfg, G._get_jinja_env()))


class TestBlogPanel:
    def test_a_legacy_sidecar_still_reads_as_all_verified(self):
        claims, summary = load_verified_claims(_digest(*MAG7))
        assert summary["verified"] == len(claims) == 23
        assert summary["flagged"] == 0 and summary["verified_later"] == 0
        assert {c["status"] for c in claims} == {"verified"}
        assert all(c["is_verified"] for c in claims)

    def test_the_panel_renders_badges_from_a_flag_era_sidecar(self, tmp_path):
        src = _digest(*MAG7)
        dst_dir = tmp_path / "digests" / "mag7"
        dst_dir.mkdir(parents=True)
        for f in src.parent.glob(src.stem + "*"):
            shutil.copy(f, dst_dir / f.name)
        (dst_dir / (src.stem + "_claims.json")).write_text(
            json.dumps(FLAG_ERA_SIDECAR), encoding="utf-8")
        html = _render_post("mag7", dst_dir / src.name)
        panel = re.search(r'<section class="blog-claims".*?</section>', html, re.S)
        assert panel, "no claims panel"
        panel = panel.group(0)
        assert "Verified claims (2)" in panel
        assert "2 published, not yet verified" in panel
        assert _badges(panel, "verified") == 1
        assert _badges(panel, "verified_later") == 1
        assert _badges(panel, "unverified_unreachable") == 1
        assert _badges(panel, "unverified_uncovered") == 1
        assert panel.count("<li>") == 4
        assert brand.CLAIMS_STATUS_LABELS["unverified_uncovered"][1] in panel
        assert "Verified 2026-10-03 (first: published, quote not matched)" in panel
        # The marked claim with no source has no link; the others do.
        assert 'href="https://www.officialgazette.gov.ph/2026/09/30/rule/"' in panel
        assert 'href="../../claims/mag7.html">Full ledger for this show →</a>' in panel
        assert "utm_" not in panel
        # And the provenance line counts what was marked.
        m = re.search(r'<p class="nn-iv-provenance nn-ep-provenance">(.*?)</p>', html, re.S)
        line = re.sub(r"<[^>]+>", "", m.group(1))
        assert "2 claims checked against their sources" in line
        assert "2 claims published and marked not yet verified" in line

    def test_the_committed_post_links_the_ledger(self):
        html = _render_post("mag7", _digest(*MAG7))
        assert 'href="../../claims/mag7.html">Full ledger for this show →</a>' in html
        assert "Verified claims (23)" in html
        assert _badges(html, "verified") == 23

    def test_provenance_omits_a_zero_flag_clause(self):
        assert "published and marked" not in brand.episode_provenance(10, 5, 0)
        assert brand.episode_provenance(10, 5, 0, flagged=1).count("1 claim published and marked not yet verified") == 1


# ---------------------------------------------------------------------------
# 4. One owner for the process copy
# ---------------------------------------------------------------------------

class TestTheProcessHasOneOwner:
    def test_the_global_is_registered_from_brand(self):
        env = G._get_jinja_env()
        assert env.globals["claims_process"] == list(brand.CLAIMS_PROCESS_STEPS)
        assert env.globals["claims_status_labels"] == brand.CLAIMS_STATUS_LABELS
        assert env.globals["claims_recheck_days"] == brand.CLAIMS_RECHECK_DAYS == 7
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert 'env.globals["claims_process"]' in src

    def test_the_steps_say_what_the_policy_is(self):
        titles = [t for t, _ in brand.CLAIMS_PROCESS_STEPS]
        assert len(titles) == len(set(titles)) == 7
        flat = " ".join(t + " " + x for t, x in brand.CLAIMS_PROCESS_STEPS)
        for phrase in ("published and marked", "never against memory", "re-check",
                       "Corrections are filed in the open", "never edited silently",
                       brand.CONTACT_EMAIL, "No human reads every episode"):
            assert phrase in flat, f"missing '{phrase}'"
        assert str(brand.CLAIMS_RECHECK_DAYS) in flat

    @pytest.mark.parametrize("name", [
        "claims_page.html.j2", "ai_disclosure.html.j2", "editorial.html.j2",
        "faq.html.j2", "blog_post.html.j2", "_macros.html.j2",
    ])
    def test_no_template_types_a_step_title_or_a_status_label(self, name):
        src = (TEMPLATES / name).read_text(encoding="utf-8")
        src = re.sub(r"\{#.*?#\}", "", src, flags=re.S)
        for title, _ in brand.CLAIMS_PROCESS_STEPS:
            assert title not in src, f"{name} types the step title {title!r}"
        for status, (label, meaning) in brand.CLAIMS_STATUS_LABELS.items():
            # One-word labels ("Verified", "Correction") are ordinary words
            # on these pages; the multi-word labels and every meaning are
            # the copy that must come through the badge macro.
            if len(label.split()) > 1:
                assert label not in src, f"{name} types the status label {label!r}"
            assert meaning not in src, f"{name} types the status meaning for {status}"

    def test_every_status_the_gate_writes_has_a_label(self):
        from engine import claims as C
        gate_statuses = set(C.VERIFIED_STATUSES) | set(C.UNVERIFIED_STATUSES)
        assert gate_statuses <= set(brand.CLAIMS_STATUS_LABELS)
        assert set(brand.CLAIMS_VERIFIED_STATUSES) == set(C.VERIFIED_STATUSES)
        assert set(L.FLAGGED_STATUSES) == set(C.UNVERIFIED_STATUSES)

    def test_the_badge_macro_reads_the_global(self):
        src = (TEMPLATES / "_macros.html.j2").read_text(encoding="utf-8")
        assert "macro claims_badge(" in src
        assert "claims_status_labels.get(" in src


# ---------------------------------------------------------------------------
# 5. The policy copy matches the configured gate
# ---------------------------------------------------------------------------

def _gate_policy(path: Path | None = None) -> dict:
    data = yaml.safe_load((path or ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
    return data["source_integrity"]


def _gate_passage(name: str) -> str:
    src = (TEMPLATES / name).read_text(encoding="utf-8")
    passage = re.search(r"Source-integrity gate.*?</(?:li|p)>", src, re.S).group(0)
    return " ".join(passage.split())


def _assert_copy_matches(flat: str, policy: dict, name: str) -> None:
    """The contract: under ``flag`` the copy says publish-and-mark and never
    claims removal; under ``strip`` the reverse. Anything else is a config
    this copy has no words for and fails loudly."""
    assert policy["enforce"] is True, f"{name}: the copy says the gate is enforced"
    assert "every show" in flat, f"{name}: the gate is enforced on every show"
    mode = policy["on_failure"]
    if mode == "flag":
        assert "published and marked, not removed" in flat, (
            f"{name}: _defaults.yaml says flag; the copy must say publish-and-mark")
        assert "cannot vouch for is removed" not in flat, (
            f"{name}: _defaults.yaml says flag but the copy still claims removal")
        assert "re-checked nightly" in flat and "claims.html" in flat
    elif mode == "strip":
        assert "removed from the episode" in flat, (
            f"{name}: _defaults.yaml says strip; the copy must say removal")
        assert "published and marked, not removed" not in flat, (
            f"{name}: _defaults.yaml says strip but the copy claims publish-and-mark")
    else:
        raise AssertionError(f"{name}: no copy exists for on_failure={mode!r}")


class TestPolicyCopyTellsTheTruth:
    def test_the_network_default_is_enforce_flag(self):
        policy = _gate_policy()
        assert policy["enabled"] is True and policy["enforce"] is True
        assert policy["on_failure"] == "flag"

    @pytest.mark.parametrize("name", ["ai_disclosure.html.j2", "editorial.html.j2"])
    def test_the_trust_pages_match_the_configured_gate(self, name):
        _assert_copy_matches(_gate_passage(name), _gate_policy(), name)

    @pytest.mark.parametrize("name", ["ai_disclosure.html.j2", "editorial.html.j2"])
    def test_the_guard_fails_when_the_default_is_strip(self, name, tmp_path):
        """Mutation: the same copy against a scratch _defaults.yaml that says
        strip must FAIL — otherwise the guard could never catch drift."""
        scratch = tmp_path / "_defaults.yaml"
        scratch.write_text(yaml.safe_dump({"source_integrity": {
            "enabled": True, "enforce": True, "on_failure": "strip"}}), encoding="utf-8")
        with pytest.raises(AssertionError):
            _assert_copy_matches(_gate_passage(name), _gate_policy(scratch), name)

    def test_strip_era_copy_would_fail_under_flag(self):
        old = ("Source-integrity gate. The gate is enforced on every show and any "
               "sentence the gate still cannot vouch for is removed from the episode "
               "before publication.</li>")
        with pytest.raises(AssertionError):
            _assert_copy_matches(old, {"enforce": True, "on_failure": "flag"}, "old")
        _assert_copy_matches(old, {"enforce": True, "on_failure": "strip"}, "old")

    @pytest.mark.parametrize("name", ["ai_disclosure.html.j2", "editorial.html.j2", "faq.html.j2"])
    def test_the_corrections_promise_links_the_ledger(self, name):
        src = (TEMPLATES / name).read_text(encoding="utf-8")
        assert "claims.html" in src, f"{name} does not link the ledger"

    def test_the_pages_still_render(self, tmp_path, capsys):
        G.generate_legal_page("ai_disclosure", dry_run=True)
        G.generate_editorial_page(dry_run=True, output_dir=tmp_path)
        G.generate_faq_page(dry_run=True)
        capsys.readouterr()


# ---------------------------------------------------------------------------
# 6. Sitemap, chrome, static-pages contract, show-page links
# ---------------------------------------------------------------------------

class TestSitemapAndContracts:
    def test_the_sitemap_lists_exactly_the_generated_pages(self, tmp_path):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        sitemap_src = src.split("def generate_sitemap(")[1].split("\ndef ")[0]
        assert "claims_page_paths()" in sitemap_src
        assert 'glob("claims' not in sitemap_src and "claims/*.html" not in sitemap_src
        out = tmp_path / "sitemap.xml"
        G.generate_sitemap(out=out)
        xml = out.read_text(encoding="utf-8")
        listed = set(re.findall(r"<loc>https://nerranetwork\.com/(claims(?:/[^<]+)?\.html)</loc>", xml))
        expected = {p for p in G.claims_page_paths() if (ROOT / p).exists()}
        assert listed == expected
        assert G.claims_page_paths()[0] == "claims.html"
        assert all(p.startswith("claims/") for p in G.claims_page_paths()[1:])

    def test_static_pages_all_and_show_regenerate_the_ledger(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        static = src.split("def generate_static_pages(")[1].split("\ndef ")[0]
        assert "generate_claims_pages(dry_run=dry_run)" in static
        main = src.split("def main():")[1]
        all_branch = main.split("if args.all:")[1].split("generate_sitemap(")[0]
        assert "generate_claims_pages(dry_run=args.dry_run)" in all_branch
        assert all_branch.index("generate_claims_pages(") < all_branch.index("generate_all_show_pages(")
        show_branch = main.split("if args.show:")[1].split("return")[0]
        assert "generate_claims_pages(dry_run=args.dry_run, slugs=[args.show])" in show_branch
        assert show_branch.index("generate_claims_pages(") < show_branch.index("generate_show_page(")

    def test_nav_and_footer_carry_the_link(self, tmp_path):
        base = (TEMPLATES / "base.html.j2").read_text(encoding="utf-8")
        more = base.split("nn-nav-dropdown-menu--compact")[1][:1200]
        assert 'href="{{ path_prefix }}claims.html"' in more
        mobile = base.split('<div class="nn-mobile-shows-title">{{ t.nav_more }}</div>')[1][:1200]
        assert 'href="{{ path_prefix }}claims.html"' in mobile
        about = base.split("<h4>{{ t.footer_about }}</h4>")[1][:2500]
        assert '<a href="{{ path_prefix }}claims.html">{{ t.nav_claims }}</a>' in about
        # Rendered fresh, with the link where a reader looks, and no UTM.
        page = Path(G.generate_explore_page(output_dir=str(tmp_path))).read_text(encoding="utf-8")
        hrefs = re.findall(r'href="(claims\.html[^"]*)"', page)
        assert len(hrefs) >= 3 and all("utm_" not in h for h in hrefs)
        assert "Claims &amp; corrections" in page

    def test_show_pages_link_their_ledger(self, tmp_path):
        for slug in ("tesla", "dp_pod"):
            out = G.generate_show_page(slug, output_dir=tmp_path)
            html = Path(out).read_text(encoding="utf-8")
            assert f'href="claims/{slug}.html"' in html, f"{slug}'s page has no ledger link"
            assert "Claims &amp; corrections" in html
        src = (TEMPLATES / "show_page_dp_pod.html.j2").read_text(encoding="utf-8")
        assert "claims_page_url" in src, "the bespoke DP Pod page needs every generic change twice"

    def test_the_corrections_doc_names_the_pages(self):
        doc = (ROOT / "docs" / "corrections.md").read_text(encoding="utf-8")
        assert "claims/<slug>.html" in doc and "claims.html" in doc
        assert "on_failure: flag" in doc


# ---------------------------------------------------------------------------
# 7. Reader edge cases: null never 0, legacy, not applicable
# ---------------------------------------------------------------------------

class TestReader:
    def test_a_show_with_no_sidecar_in_the_window_is_null_not_zero(self, tmp_path):
        (tmp_path / "digests" / "mag7").mkdir(parents=True)
        ledger = L.show_ledger("mag7", today=TODAY, digests_root=tmp_path / "digests",
                               blog_url_for=lambda s, e: "")
        assert ledger["applicable"] and ledger["rows"] == []
        t = ledger["totals"]
        assert t["claims"] is None and t["verified_share_pct"] is None
        assert t["flagged"] is None and t["episodes"] == 0 and t["corrections"] == 0
        net = L.network_ledger(["mag7", "nerra_daily"], today=TODAY,
                               digests_root=tmp_path / "digests")
        assert net["totals"]["claims"] is None and net["totals"]["shows_measured"] == 0
        assert net["totals"]["shows_not_applicable"] == 1

    def test_a_legacy_sidecar_reads_as_verified_with_its_stripped_sentences(self):
        side = L.read_sidecar(ROOT / "digests" / "planetterrian" /
                              "Planetterrian_Daily_Ep174_20260905_claims.json")
        assert side["policy_version"] == 1
        assert all(c["status"] == "verified" for c in side["claims"])
        mag7 = L.read_sidecar(_digest(*MAG7).with_name(_digest(*MAG7).stem + "_claims.json"))
        assert len(mag7["claims"]) == 23 and mag7["stripped_sentences"] == []

    def test_not_applicable_shows(self):
        assert set(L.NOT_APPLICABLE) == {"nerra_daily", "age_of_ai", "nerra_voices"}
        for slug in L.NOT_APPLICABLE:
            ledger = L.show_ledger(slug, today=TODAY)
            assert ledger["applicable"] is False and ledger["note"]
            assert ledger["totals"]["claims"] is None

    def test_an_unreadable_sidecar_is_skipped_never_raised(self, tmp_path):
        d = tmp_path / "digests" / "mag7"
        d.mkdir(parents=True)
        (d / "MAG7_Daily_Ep901_20261001_claims.json").write_text("{not json", encoding="utf-8")
        assert L.show_ledger("mag7", today=TODAY, digests_root=tmp_path / "digests",
                             blog_url_for=lambda s, e: "")["rows"] == []
        assert L.read_sidecar(d / "MAG7_Daily_Ep901_20261001_claims.json") is None

    def test_window_and_stem_parsing(self):
        assert L.parse_stem("MAG7_Daily_Ep009_20261001") == {
            "prefix": "MAG7_Daily", "episode": 9, "date": "2026-10-01"}
        assert L.parse_stem("nope") is None
        assert L.show_episode_config("mag7")["prefix"] == "MAG7_Daily"
        assert L.show_episode_config("nerra_daily") is None
        assert L.show_dir_for("mag7", digests_root="/x/digests") == Path("/x/digests/mag7")
