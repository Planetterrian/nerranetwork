"""Drift guards for the evergreen topic hubs (2026-09-20, phase 4).

The site had 1,952 sitemap URLs and earned 20 organic sessions in 28 days,
because 1,880 of those URLs are dated news articles. These pages answer the
durable query instead. What the tests below protect, in the order it would hurt:

1. **A hub is never written empty or thin.** The episode lists come from the
   COMMITTED search index; an empty index must produce NO pages, because that
   is exactly how the public search index shipped zero episodes ~13x a day
   until July 2026.
2. **A hub the generator skipped is never linked or advertised** — not from a
   blog post, not from the sitemap. An internal link to a page that was not
   written is the broken-link class the Sep 19 pass removed from ~1,990 pages.
3. **The vocabulary stays curated.** The index's auto-mined ``topics`` put
   "regulation" on 91% of episodes; a hub named for that is a keyword artifact,
   not a subject.
4. **The pages are committed.** A generated path missing from nightly's
   add-paths is rebuilt and thrown away every night.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

import sys  # noqa: E402

sys.path.insert(0, str(ROOT))

from engine import topic_hubs as hubs  # noqa: E402


@pytest.fixture(scope="module")
def all_shows():
    import generate_html
    return generate_html._build_all_shows_list()


@pytest.fixture(scope="module")
def index():
    idx = hubs.load_search_index()
    assert idx is not None, "site/data/search-index.json is missing or malformed"
    return idx


class TestHubDefinitions:
    def test_every_hub_is_complete(self):
        for hub in hubs.TOPIC_HUBS:
            for key in ("id", "title", "heading", "picker_topics", "intro",
                        "angle", "meta_description", "keywords"):
                assert hub.get(key), f"{hub.get('id')}: missing {key}"

    def test_ids_are_unique_and_filename_safe(self):
        ids = [h["id"] for h in hubs.TOPIC_HUBS]
        assert len(ids) == len(set(ids))
        for hub_id in ids:
            assert re.fullmatch(r"[a-z0-9-]+", hub_id), hub_id

    def test_intros_are_written_prose_not_a_label(self):
        """A hub whose text is assembled from its own listing is thin content.

        The floor is deliberately high enough that a placeholder cannot pass.
        """
        for hub in hubs.TOPIC_HUBS:
            assert len(hub["intro"]) >= 120, f"{hub['id']}: intro too thin"
            assert len(hub["angle"]) >= 40, f"{hub['id']}: angle too thin"
            assert hub["intro"] != hub["angle"]

    def test_every_hub_topic_is_claimed_by_a_show(self, all_shows):
        claimed = set()
        for show in all_shows:
            for topic in (show.get("picker_tags") or {}).get("topics", []):
                claimed.add(str(topic).lower())
        for hub in hubs.TOPIC_HUBS:
            wanted = {t.lower() for t in hub["picker_topics"]}
            assert wanted & claimed, (
                f"{hub['id']} names {sorted(wanted)}, which no show claims in "
                "its registry picker_tags — the hub would be empty"
            )

    def test_the_mined_index_topics_are_not_the_vocabulary(self, index):
        """"regulation" is on 91% of episodes. It is not a subject."""
        mined = {}
        for rec in index["episodes"]:
            for topic in rec.get("topics") or []:
                mined[topic] = mined.get(topic, 0) + 1
        total = len(index["episodes"])
        overbroad = {t for t, c in mined.items() if c > total * 0.5}
        hub_ids = {h["id"] for h in hubs.TOPIC_HUBS}
        assert not (hub_ids & overbroad), (
            f"hub named for an over-broad mined topic: {hub_ids & overbroad}"
        )


class TestThinHubsAreSkipped:
    def test_a_hub_under_the_bar_is_not_built(self, all_shows, index):
        thin = {"episodes": index["episodes"][:1]}
        assert hubs.renderable_hubs(all_shows, thin) == []

    def test_an_empty_index_yields_no_hubs(self, all_shows):
        assert hubs.renderable_hubs(all_shows, {"episodes": []}) == []

    def test_the_generator_writes_nothing_without_an_index(self, tmp_path, monkeypatch):
        import generate_html
        monkeypatch.setattr(hubs, "load_search_index", lambda *a, **k: None)
        written = generate_html.generate_topic_hub_pages(output_dir=str(tmp_path))
        assert written == []
        assert not (tmp_path / hubs.HUB_DIR).exists(), (
            "an index-less run must write no hub pages at all — an empty hub "
            "is worse than no hub"
        )

    def test_skipped_hubs_name_an_alternative_page(self, all_shows, index):
        """Nothing silently disappears from the site's own map."""
        live = {c["hub"]["id"] for c in hubs.renderable_hubs(all_shows, index)}
        for hub in hubs.TOPIC_HUBS:
            if hub["id"] in live:
                continue
            alt = hub.get("alternative")
            assert alt and alt.get("href"), (
                f"{hub['id']} is below the bar and names no alternative page"
            )
            assert (ROOT / alt["href"]).exists(), alt["href"]

    def test_a_skipped_hub_is_never_linked_from_a_post(self, all_shows, index):
        live = {c["hub"]["id"] for c in hubs.renderable_hubs(all_shows, index)}
        for show in all_shows:
            for hub in hubs.hubs_for_show(show["slug"], all_shows, index):
                assert hub["id"] in live, (
                    f"{show['slug']} would link {hub['id']}, which is not built"
                )


class TestRenderedPages:
    def test_every_built_hub_exists_on_disk(self, all_shows, index):
        for ctx in hubs.renderable_hubs(all_shows, index):
            path = ROOT / hubs.hub_page_path(ctx["hub"]["id"])
            assert path.exists(), f"{path} was not generated"

    def test_the_index_page_covers_every_built_hub(self, all_shows, index):
        html = (ROOT / hubs.HUB_DIR / "index.html").read_text(encoding="utf-8")
        for ctx in hubs.renderable_hubs(all_shows, index):
            assert f'topics/{ctx["hub"]["id"]}.html' in html, ctx["hub"]["id"]

    def test_hub_pages_have_no_broken_internal_links(self, all_shows, index):
        broken = []
        for ctx in hubs.renderable_hubs(all_shows, index):
            rel = hubs.hub_page_path(ctx["hub"]["id"])
            html = (ROOT / rel).read_text(encoding="utf-8")
            for target in re.findall(r'href="([^"#?:]+?)"', html):
                if target.startswith(("http", "mailto", "//", "#")):
                    continue
                if not ((ROOT / hubs.HUB_DIR) / target).resolve().exists():
                    broken.append(f"{rel} -> {target}")
        assert not broken, broken[:8]

    def test_each_hub_page_carries_its_own_written_copy(self, all_shows, index):
        for ctx in hubs.renderable_hubs(all_shows, index):
            html = (ROOT / hubs.hub_page_path(ctx["hub"]["id"])).read_text(
                encoding="utf-8")
            assert ctx["hub"]["intro"][:60] in html
            assert ctx["hub"]["angle"][:40] in html


class TestWiring:
    def test_in_the_one_static_pages_list_and_in_all(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        body = src.split("def generate_static_pages(")[1].split("\ndef ")[0]
        assert "generate_topic_hub_pages(dry_run=dry_run)" in body
        all_block = src.split("    if args.all:")[1].split("        return")[0]
        assert "generate_topic_hub_pages" in all_block

    def test_sitemap_lists_hubs_from_the_module_not_a_glob(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        sitemap = src.split("def generate_sitemap(")[1].split("\ndef ")[0]
        assert "topic_hubs" in sitemap, "hubs are missing from the sitemap"
        assert "renderable_hubs" in sitemap, (
            "the sitemap must list only hubs that were BUILT — a glob would "
            "advertise a page the generator skipped"
        )
        xml = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        assert f"/{hubs.HUB_DIR}/index.html" in xml

    def test_sitemap_never_lists_a_hub_that_is_not_on_disk(self):
        xml = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        for rel in re.findall(r"<loc>https://nerranetwork\.com/(topics/[^<]+)</loc>", xml):
            assert (ROOT / rel).exists(), rel

    def test_nightly_commits_the_hubs(self):
        wf = (ROOT / ".github" / "workflows"
              / "nightly-maintenance.yml").read_text(encoding="utf-8")
        assert f"{hubs.HUB_DIR}/*.html" in wf, (
            "a generated path missing from nightly's add-paths is rebuilt and "
            "thrown away every night"
        )

    def test_chrome_and_llms_txt_link_the_topics_map(self):
        base = (ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8")
        assert base.count("topics/index.html") >= 3, (
            "nav, mobile menu and footer should all reach the topics map"
        )
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        block = src.split("def generate_llms_txt(")[1].split("\ndef ")[0]
        assert "topics/index.html" in block

    def test_blog_posts_link_their_subjects(self):
        tmpl = (ROOT / "templates" / "blog_post.html.j2").read_text(encoding="utf-8")
        assert "topic_hubs" in tmpl
        assert "topics/{{ hub.id }}.html" in tmpl
        blog = (ROOT / "engine" / "blog.py").read_text(encoding="utf-8")
        assert '"topic_hubs": _topic_hubs_for(show_slug)' in blog


class TestTitleLimitHasOneOwner:
    def test_the_blog_title_lead_is_not_a_magic_number(self):
        """engine/titles.py exports WEB_TITLE_LEAD_MAX; a literal 62 here is
        exactly the drift that standing rule exists to prevent."""
        blog = (ROOT / "engine" / "blog.py").read_text(encoding="utf-8")
        assert "_web_title_lead_max()" in blog
        assert "_clip_words(metadata['title'], 62)" not in blog
        from engine.titles import WEB_TITLE_LEAD_MAX
        import engine.blog as _blog
        assert _blog._web_title_lead_max() == WEB_TITLE_LEAD_MAX

    def test_blog_titles_are_per_episode_and_within_budget(self):
        """The Sep 3 review's deferred item turns out to be shipped already —
        this pins it so it cannot regress."""
        from engine.titles import WEB_TITLE_LEAD_MAX
        seen = []
        for path in sorted((ROOT / "blog" / "tesla").glob("ep*.html"))[-12:]:
            m = re.search(r"<title>(.*?)</title>",
                          path.read_text(encoding="utf-8", errors="ignore"), re.S)
            if m:
                seen.append(m.group(1).strip())
        assert len(seen) >= 6, "not enough committed Tesla posts to judge"
        assert len(set(seen)) == len(seen), "blog <title>s are not unique"
        for title in seen:
            lead = title.split(" — Ep")[0]
            assert len(lead) <= WEB_TITLE_LEAD_MAX, (lead, len(lead))


class TestTheMemoIsKeyedOnContent:
    """``hubs_for_show`` runs once per blog post, so the live-hub set is
    memoized — and the key must be the index's CONTENT, not ``id(index)``.
    CPython reuses an address once the old object is collected, so an identity
    key can serve a later index the earlier one's answer: a wrong hub list that
    looks exactly like a right one, which is the silent-number class."""

    def test_two_different_indexes_do_not_share_an_answer(self, all_shows, index):
        full = hubs._live_hub_ids(all_shows, index)
        thin = hubs._live_hub_ids(all_shows, {"episodes": index["episodes"][:1],
                                              "generated_at": "thin"})
        assert full and not thin, (full, thin)
        # And the full answer survives the second call (no key collision).
        assert hubs._live_hub_ids(all_shows, index) == full

    def test_the_key_is_not_an_identity(self):
        src = (ROOT / "engine" / "topic_hubs.py").read_text(encoding="utf-8")
        body = src.split("def _live_hub_ids(")[1].split("\ndef ")[0]
        assert "id(index)" not in body, (
            "an identity key can be reused after garbage collection"
        )
        assert "generated_at" in body
