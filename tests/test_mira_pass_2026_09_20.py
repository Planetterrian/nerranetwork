"""Drift guards for the Mira pass (2026-09-20).

Three shows share an AI host, they are the network's cheapest, best-trending
and most-visited properties, and they had: no shared page, no claim anywhere on
the site saying why they are unusual, no link between each other, and — for the
two interview shows — no distribution beyond RSS.

What these tests protect, in order of how badly it hurt when it was wrong:

1. **The claim is narrow and has one owner.** The first version claimed the
   general shape ("an AI host interviews people"), which other people did
   first, and rested on a basis ("she places the call") that stopped being true
   on 2026-09-09. A superlative on the press page is worse than no superlative
   if one search disproves it.
2. **A flag that is read by nothing is not a feature.** The interview shows
   bypass ``run_show.py``, so ``newsletter.enabled`` / ``youtube.enabled``
   meant nothing until the Voices publisher read them.
3. **No surface advertises something that does not exist** — a feed with no
   file, an episode count that is stale, a page missing from the sitemap.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
MIRA_SLUGS = ("nerra_daily", "age_of_ai", "nerra_voices")


def _render_mira(tmp_path):
    import generate_html
    generate_html.generate_mira_page(output_dir=str(tmp_path))
    return (tmp_path / "mira.html").read_text(encoding="utf-8")


class TestTheClaimHasOneOwner:
    def test_engine_brand_is_the_only_python_owner(self):
        from engine import brand
        claim = brand.MIRA_FIRST_CLAIM
        offenders = []
        for path in ROOT.rglob("*.py"):
            if "/.git/" in str(path) or path.name == "brand.py":
                continue
            if path.is_relative_to(ROOT / "tests"):
                continue
            if claim[:60] in path.read_text(encoding="utf-8", errors="ignore"):
                offenders.append(str(path.relative_to(ROOT)))
        assert not offenders, (
            "the Mira claim is retyped in "
            f"{offenders} — engine/brand.py owns it; import it"
        )

    def test_no_template_hardcodes_the_claim(self):
        from engine import brand
        offenders = [
            str(p.relative_to(ROOT)) for p in TEMPLATES.rglob("*.j2")
            if brand.MIRA_FIRST_CLAIM[:60] in p.read_text(encoding="utf-8")
        ]
        assert not offenders, (
            f"{offenders} hardcode the claim — render the mira_claim macro"
        )

    def test_claim_is_the_narrow_one(self):
        """The claim must rest on the guest's veto, not on 'an AI interviews'.

        Other platforms had an AI host interviewing real guests first, at least
        one since 2024. What has not been found elsewhere is the guest holding
        the publish decision — so that clause is the claim, and a future edit
        that widens it back is the failure this test exists to catch.
        """
        from engine import brand
        claim = brand.MIRA_FIRST_CLAIM.lower()
        assert "first" in claim, "the operator asked for an explicit claim"
        assert any(w in claim for w in ("decides whether", "approve", "publish")), (
            "the claim must name the guest's control over publication — that "
            "is the part that is actually ours"
        )

    def test_basis_does_not_rest_on_placing_a_phone_call(self):
        """2026-09-09 made the browser room the default and PSTN the fallback.

        ``voximplant/scenarios/age_of_ai_interview.js`` is the record. Any
        basis clause that says Mira places the call is describing the fallback
        as if it were the show.
        """
        from engine import brand
        blob = " ".join(brand.mira_claim_paragraphs()).lower()
        for phrase in ("places the call", "phones", "over the phone",
                       "calls you on the phone"):
            assert phrase not in blob, (
                f"{phrase!r} is the pre-2026-09-09 flow: the default is now a "
                "browser studio room and the outbound call is the fallback"
            )
        scenario = (ROOT / "voximplant" / "scenarios"
                    / "age_of_ai_interview.js").read_text(encoding="utf-8")
        assert "the fallback mode" in scenario, (
            "if the outbound PSTN leg stops being the fallback, revisit the "
            "claim's basis — this test is the tripwire"
        )

    def test_basis_and_footnote_always_ship_together(self):
        from engine import brand
        paras = brand.mira_claim_paragraphs()
        assert len(paras) == 3
        assert paras[0] == brand.MIRA_FIRST_CLAIM
        assert paras[1] == brand.MIRA_FIRST_CLAIM_BASIS
        assert "hello@nerranetwork.com" in paras[2], (
            "the correction invitation is what keeps a superlative inside the "
            "network's own honesty rules"
        )


class TestMiraPageIsGeneratedAndTrue:
    def test_page_renders_with_real_episode_counts(self, tmp_path):
        html = _render_mira(tmp_path)
        for slug in MIRA_SLUGS:
            meta = yaml.safe_load(
                (ROOT / "shows" / "network_meta.yaml").read_text(encoding="utf-8"))
            name = meta[slug]["name"]
            assert name in html, f"{name} missing from the hub"
        import generate_html
        for slug in MIRA_SLUGS:
            cfg = generate_html.NETWORK_SHOWS[slug]
            count = generate_html._mira_episode_count(cfg)
            path = ROOT / cfg["json_path"]
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                records = (data.get("summaries") or data.get("episodes") or []
                           if isinstance(data, dict) else data)
                assert count == len(records), (
                    f"{slug}: the page would claim {count} episodes, the "
                    f"committed record has {len(records)}"
                )

    def test_a_show_with_no_episodes_says_so(self, tmp_path):
        html = _render_mira(tmp_path)
        assert "Not published yet" in html, (
            "Nerra Voices has published nothing; the hub must say so rather "
            "than imply a catalogue"
        )

    def test_never_links_a_feed_that_has_no_file(self, tmp_path):
        html = _render_mira(tmp_path)
        import generate_html
        for slug in MIRA_SLUGS:
            rss = generate_html.NETWORK_SHOWS[slug]["rss_file"]
            if not (ROOT / rss).exists():
                assert f'href="{rss}"' not in html, (
                    f"{rss} does not exist — linking it is the broken-link "
                    "class the Sep 19 pass removed from 1,956 pages"
                )

    def test_registered_in_the_one_static_pages_list(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        body = src.split("def generate_static_pages(")[1].split("\ndef ")[0]
        assert "generate_mira_page(dry_run=dry_run)" in body, (
            "a page absent from generate_static_pages() silently stops "
            "refreshing between --all runs (the Sep 3 lesson)"
        )

    def test_in_all_and_in_the_sitemap(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        all_block = src.split("    if args.all:")[1].split("        return")[0]
        assert "generate_mira_page" in all_block
        sitemap = src.split("def generate_sitemap(")[1].split("\ndef ")[0]
        assert '"mira.html"' in sitemap
        assert '"age-of-ai-apply.html"' in sitemap, (
            "the guest-application page was reachable from two show pages and "
            "absent from the sitemap, so the acquisition surface for the "
            "network's most differentiated shows could not be found by search"
        )

    def test_both_apply_forms_are_in_the_sitemap(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        sitemap = src.split("def generate_sitemap(")[1].split("\ndef ")[0]
        assert '"nerra-voices-apply.html"' in sitemap
        for page in ("age-of-ai-apply.html", "nerra-voices-apply.html"):
            assert (ROOT / page).exists(), page

    def test_each_interview_show_links_its_own_form(self, tmp_path):
        """There are TWO application pages, and the endpoint files an
        application against the show whose form posted it. Sending a Nerra
        Voices reader to the Age of AI form files them against the wrong show
        and leaves Patrick to reassign it by hand."""
        import generate_html
        for slug, expected in (("age_of_ai", "age-of-ai-apply.html"),
                               ("nerra_voices", "nerra-voices-apply.html")):
            assert generate_html.NETWORK_SHOWS[slug]["apply_page"] == expected
        html = _render_mira(tmp_path)
        for page in ("age-of-ai-apply.html", "nerra-voices-apply.html"):
            assert f'href="{page}"' in html, f"the hub does not link {page}"

    def test_the_apply_pages_do_not_promise_a_phone_call(self):
        """These are the pages an applicant reads before agreeing, and they
        described the pre-2026-09-09 dialled-out flow as the default."""
        for page in ("age-of-ai-apply.html", "nerra-voices-apply.html"):
            html = (ROOT / page).read_text(encoding="utf-8")
            assert "calls you at a time you book" not in html, page
            assert "join from your browser" in html, page

    def test_the_apply_pages_point_at_each_other(self):
        aoai = (ROOT / "age-of-ai-apply.html").read_text(encoding="utf-8")
        voices = (ROOT / "nerra-voices-apply.html").read_text(encoding="utf-8")
        assert "nerra-voices-apply.html" in aoai
        assert "age-of-ai-apply.html" in voices
        assert "mira.html" in aoai and "mira.html" in voices

    def test_the_private_studio_link_stays_out_of_the_sitemap(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        sitemap = src.split("def generate_sitemap(")[1].split("\ndef ")[0]
        # Code only: the function's prose explains why the studio page is
        # excluded, and a comment naming it is not an entry.
        code = "\n".join(line for line in sitemap.splitlines()
                         if not line.lstrip().startswith("#"))
        assert "age-of-ai-studio.html" not in code, (
            "the studio page is a private join link for a scheduled "
            "interview, not content"
        )


class TestStrandGrouping:
    def test_every_mira_show_declares_the_strand(self):
        meta = yaml.safe_load(
            (ROOT / "shows" / "network_meta.yaml").read_text(encoding="utf-8"))
        for slug in MIRA_SLUGS:
            assert meta[slug].get("strand") == "mira", slug

    def test_strand_reaches_the_templates(self):
        import generate_html
        shows = {s["slug"]: s for s in generate_html._build_all_shows_list()}
        assert {s for s, v in shows.items() if v["strand"] == "mira"} == set(MIRA_SLUGS)

    def test_nav_and_mobile_menu_group_by_strand(self):
        """Asserts the property, not a literal count.

        This counted ``nav_hosted_by_mira`` occurrences until 2026-09-21, when
        the grouping became a single ``show_groups`` shared by four surfaces —
        after which the count was 2 only because the ``t``-dict key and the
        group tuple both spell it, i.e. it passed for the wrong reason.
        """
        base = (TEMPLATES / "base.html.j2").read_text(encoding="utf-8")
        assert base.count("in show_groups") >= 2, (
            "the desktop dropdown and the mobile menu must group the same way"
        )
        assert "'nav_hosted_by_mira'" in base, "the group label is gone"
        assert 'href="{{ path_prefix }}mira.html"' in base, "no nav entry"

    def test_show_pages_carry_the_band_only_for_the_strand(self):
        tmpl = (TEMPLATES / "show_page.html.j2").read_text(encoding="utf-8")
        assert "{% if strand == 'mira' %}" in tmpl
        assert "mira_claim(" in tmpl

    def test_footer_show_links_nest_only_where_the_accordion_collapses(self):
        """Corrected 2026-09-21. This test used to require the footer show list
        to stay FLAT, on the premise that any nesting breaks the phone
        accordion. The premise was incomplete: the CSS hides
        ``.nn-footer-col > ul`` as well as ``> a``, so a direct-child list
        collapses correctly. What does not collapse is a direct child of any
        other kind — a group label written as a heading would stay visible above
        an emptied column. The footer is grouped now, with its labels inside the
        ``<ul>``; the full set of assertions is in
        ``tests/test_chrome_pass_2026_09_21.py``.
        """
        import re as _re
        base = (TEMPLATES / "base.html.j2").read_text(encoding="utf-8")
        # Jinja comments are stripped FIRST. Without this the check reads the
        # comment that explains the rule ("the group label lives INSIDE the
        # <ul>") as markup and passes no matter where the label actually is —
        # verified by hoisting the label out and watching this still pass.
        markup = _re.sub(r"\{#.*?#\}", "", base, flags=_re.S)
        footer = markup.split('<h4>{{ t.footer_shows }}</h4>')[1][:1200]
        assert "nn-footer-showlist" in footer, "the footer list is no longer grouped"
        label_at = footer.find("nn-footer-grouplabel")
        assert label_at != -1
        before = footer[:label_at]
        assert before.rfind("<ul") > before.rfind("</ul>"), (
            "the group label escaped the <ul> and would not collapse"
        )


class TestMiraIsOnTheSurfacesThatMatter:
    def test_press_kit_has_a_mira_section(self):
        press = (TEMPLATES / "press.html.j2").read_text(encoding="utf-8")
        assert "mira_claim" in press, (
            "the press kit is the artifact a journalist works from and had "
            "zero mentions of the host"
        )
        assert "mira_shows" in press

    def test_editorial_page_states_the_two_gates(self):
        ed = (TEMPLATES / "editorial.html.j2").read_text(encoding="utf-8")
        assert "two gates" in ed.lower()
        assert "approves their own transcript" in ed

    def test_every_orphaned_surface_now_links_the_hub(self):
        for name in ("press.html.j2", "editorial.html.j2", "about.html.j2",
                     "start_here.html.j2", "how_to_listen.html.j2"):
            text = (TEMPLATES / name).read_text(encoding="utf-8")
            assert "mira.html" in text, f"{name} does not link the Mira hub"

    def test_llms_txt_names_her(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        block = src.split("def generate_llms_txt(")[1].split("\ndef ")[0]
        assert "mira.html" in block
        assert "MIRA_FIRST_CLAIM" in block


class TestVoicesDistributionIsWired:
    def test_waveform_video_url_follows_the_produce_step_key(self):
        import sys
        sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
        import publish_episode as pe
        assert pe.waveform_video_url(
            "https://audio.nerranetwork.com/age_of_ai/AOAI_Ep004_20260917.mp3"
        ) == (
            "https://audio.nerranetwork.com/age_of_ai/video/AOAI_Ep004_20260917.mp4"
        )

    def test_a_non_mp3_yields_nothing_rather_than_a_guess(self):
        import sys
        sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
        import publish_episode as pe
        assert pe.waveform_video_url("https://x/y.wav") == ""
        assert pe.waveform_video_url("") == ""

    def test_distribution_never_blocks_the_episode(self):
        src = (ROOT / "pipelines" / "voices"
               / "publish_episode.py").read_text(encoding="utf-8")
        for fn in ("def maybe_send_newsletter", "def maybe_publish_youtube"):
            body = src.split(fn)[1].split("\ndef ")[0]
            assert "except Exception" in body, (
                f"{fn} must swallow its own failure — the episode is already "
                "in the feed by then"
            )

    def test_the_publish_workflow_passes_the_secrets_the_code_reads(self):
        """A flag with no secret behind it is the same no-op it replaced.

        engine.youtube reads YOUTUBE_REFRESH_TOKEN_<CHANNEL-UPPERCASED>, so
        the unsuffixed name would silently never upload.
        """
        wf = (ROOT / ".github" / "workflows"
              / "nerra_voices_publish.yml").read_text(encoding="utf-8")
        assert "BUTTONDOWN_API_KEY:" in wf
        assert "YOUTUBE_REFRESH_TOKEN_EN:" in wf
        assert not re.search(r"YOUTUBE_REFRESH_TOKEN:\s", wf), (
            "unsuffixed YOUTUBE_REFRESH_TOKEN is not read by anything"
        )

    def test_both_interview_shows_commit_their_output(self):
        """publish_episode.py resolves the show per row; the workflow's
        add-paths named only Age of AI, so a Nerra Voices episode would have
        been generated and thrown away."""
        wf = (ROOT / ".github" / "workflows"
              / "nerra_voices_publish.yml").read_text(encoding="utf-8")
        for path in ("nerra_voices_podcast.rss", "digests/nerra_voices/",
                     "nerra-voices.html", "blog/nerra_voices/"):
            assert path in wf, f"{path} is not committed by the publish workflow"

    def test_the_video_index_shape_matches_what_analytics_globs(self):
        src = (ROOT / "pipelines" / "voices"
               / "publish_episode.py").read_text(encoding="utf-8")
        body = src.split("def _record_youtube_video")[1].split("\ndef ")[0]
        for key in ('"video_id"', '"show_slug"', '"episode"', '"kind"',
                    '"channel"', '"watch_url"'):
            assert key in body, f"{key} missing from the recorded video"
        assert "youtube_videos.json" in body


class TestNerraVoicesPreLaunchHonesty:
    def test_show_page_has_a_pre_launch_band(self):
        tmpl = (TEMPLATES / "show_page.html.j2").read_text(encoding="utf-8")
        assert "{% if not has_feed %}" in tmpl
        assert "not-yet-published" in tmpl

    def test_nerra_voices_has_no_feed_file_yet(self):
        """If this starts failing, Nerra Voices has published — good. Remove
        the pre-launch expectations here and check the page reads right."""
        import generate_html
        rss = generate_html.NETWORK_SHOWS["nerra_voices"]["rss_file"]
        assert not (ROOT / rss).exists(), (
            f"{rss} now exists — the pre-launch band will disappear on its "
            "own; confirm the page reads correctly and update this guard"
        )


class TestStyleTokensExist:
    def test_claim_and_badge_styles_are_in_the_shared_stylesheet(self):
        css = (ROOT / "styles" / "main.css").read_text(encoding="utf-8")
        for token in (".nn-mira-claim", ".nn-nav-group-label",
                      ".show-card-badge--strand"):
            assert token in css, (
                f"{token} is rendered on several pages; its styles belong in "
                "the shared stylesheet, not in one page's <style> block"
            )

    def test_macro_reads_the_registered_global(self):
        macros = (TEMPLATES / "_macros.html.j2").read_text(encoding="utf-8")
        body = macros.split("macro mira_claim(")[1]
        assert "mira.claim" in body and "mira.basis" in body
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert 'env.globals["mira"]' in src
        assert 'env.globals["mira_shows"]' in src
