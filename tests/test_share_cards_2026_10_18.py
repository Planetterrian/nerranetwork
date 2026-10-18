"""Share cards (Oct 18 2026) — engine/share_cards.py.

Every link preview on the site had been the old network image (which still
carried the no-advertising promise the Oct 11 sponsor policy retired) or a 3000x3000 podcast cover
cropped to a strip by every platform. Now: a 1200x630 card for the network,
every show, the site pages and the topic hubs (committed, rebuilt nightly),
one per episode on R2, and ONE resolver every page goes through.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import share_cards as S  # noqa: E402


def _jpeg_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=S.JPEG_QUALITY, optimize=True, progressive=True)
    return buf.getvalue()


class TestRenderers:
    def test_every_card_is_1200x630(self):
        cards = [
            S.render_network_card(show_count=31),
            S.render_show_card(name="Models & Agents", tagline="Daily AI.", schedule="Daily",
                               cover=None, brand_color="#7C3AED"),
            S.render_page_card(kicker="Topic", title="Space", subtitle="Two shows"),
            S.render_episode_card(show_name="SpaceX Daily", hook="A hook", episode_num=130,
                                  date_str="2026-10-14"),
        ]
        for img in cards:
            assert img.size == (S.WIDTH, S.HEIGHT) == (1200, 630)
            assert img.mode == "RGB"

    def test_rendering_is_deterministic(self):
        """A rebuild must not rewrite an unchanged committed card."""
        a = S.render_episode_card(show_name="Tesla Shorts Time", hook="Same hook twice",
                                  episode_num=600, date_str="2026-10-01", brand_color="#E31937")
        b = S.render_episode_card(show_name="Tesla Shorts Time", hook="Same hook twice",
                                  episode_num=600, date_str="2026-10-01", brand_color="#E31937")
        assert _jpeg_bytes(a) == _jpeg_bytes(b)

    def test_save_jpeg_leaves_an_identical_card_alone(self, tmp_path):
        img = S.render_page_card(kicker="X", title="Y")
        path = tmp_path / "c.jpg"
        assert S.save_jpeg(img, path) is True
        assert S.save_jpeg(img, path) is False

    def test_cyrillic_gets_a_font_that_draws_it(self):
        """DM Sans has no Cyrillic; the bundled Golos Text must take over —
        a system font would make a runner's card differ from a laptop's."""
        picked = S._pick(S._SANS_MEDIUM, "Финансы — просто", S._FALLBACK_REGULAR)
        assert picked == S._FALLBACK_REGULAR
        assert picked.is_file() and picked.parent == S.FONTS_DIR
        assert S._covers(picked, "Финансы — просто")
        assert S._pick(S._SANS_MEDIUM, "Hello", S._FALLBACK_REGULAR) == S._SANS_MEDIUM
        # Headlines: Source Serif 4 draws Cyrillic itself.
        assert S._covers(S._SERIF_BOLD, "Как разделить RRSP")

    def test_russian_meta_line(self):
        assert S.episode_meta_line(58, "2026-10-13", "ru") == "Выпуск 58 · 13 октября 2026"
        assert S.episode_meta_line(130, "2026-10-14") == "Episode 130 · October 14, 2026"

    def test_brand_colour_is_lifted_to_read_as_text(self):
        for hex_ in ("#334155", "#0B3C5D", "#E31937", "#1B5E20"):
            lifted = S.readable_on_dark(S._hex(hex_))
            assert S.contrast(lifted, S.BG) >= 4.5


class TestTitlesOwnTheLimit:
    def test_limit_lives_in_engine_titles(self):
        from engine import titles
        assert titles.SHARE_CARD_HOOK_MAX >= titles.SPOKEN_HOOK_MAX_CHARS

    def test_no_slice_of_its_own(self):
        """CLAUDE.md: never truncate a title outside engine/titles.py."""
        src = (ROOT / "engine" / "share_cards.py").read_text(encoding="utf-8")
        assert "clip_words" in src
        assert not re.search(r"(hook|text|title)\[:\s*\w", src)

    def test_an_overlong_hook_ends_on_a_whole_word(self):
        hook = ("An extraordinarily long headline " * 12).strip()
        block = S._fit(hook, S._SERIF_BOLD, max_width=780, max_lines=4, start=60, floor=36,
                       max_height=322)
        assert len(block.lines) <= 4
        last = block.lines[-1]
        assert last.endswith("…")
        assert last[:-1].split()[-1] in hook.split()


class TestResolver:
    SHOWS = {"models_agents": {"name": "Models & Agents",
                               "podcast_image": "assets/covers/models-agents.jpg"}}

    def test_a_square_cover_becomes_the_show_card(self):
        for og in ("https://nerranetwork.com/assets/covers/models-agents.jpg",
                   "https://raw.githubusercontent.com/x/y/main/assets/covers/models-agents.jpg",
                   "https://nerranetwork.com/assets/covers/models-agents-800.webp"):
            r = S.resolve_og_image(og, shows=self.SHOWS)
            assert r["url"].endswith("/assets/share/shows/models_agents.jpg"), og
            assert (r["width"], r["height"]) == (1200, 630)
            assert "Models & Agents" in r["alt"]

    def test_nothing_becomes_the_page_card_then_the_network_card(self):
        r = S.resolve_og_image("", "https://nerranetwork.com/mira.html", shows=self.SHOWS)
        assert r["url"].endswith("/assets/share/pages/mira.jpg")
        assert "Mira" in r["alt"]
        r = S.resolve_og_image("", "https://nerranetwork.com/", shows=self.SHOWS)
        assert r["url"].endswith("/assets/share/network.jpg")
        r = S.resolve_og_image("https://nerranetwork.com/assets/og-preview.png",
                               "https://nerranetwork.com/blog/index.html", shows=self.SHOWS)
        assert r["url"].endswith("/assets/share/pages/blog.jpg")

    def test_an_episode_card_passes_through_with_its_size(self):
        url = "https://audio.nerranetwork.com/share/spacex/ep130-scene.jpg"
        r = S.resolve_og_image(url, shows=self.SHOWS, alt="SpaceX Daily, episode 130")
        assert r == {"url": url, "width": 1200, "height": 630,
                     "alt": "SpaceX Daily, episode 130"}

    def test_a_landscape_scene_passes_through_without_a_claimed_size(self):
        url = "https://gallery.nerranetwork.com/x/y.thumb.webp"
        r = S.resolve_og_image(url, shows=self.SHOWS)
        assert r["url"] == url and r["width"] is None

    def test_page_keys(self):
        assert S.page_key_for_path("/topics/ai.html") == "topics-ai"
        assert S.page_key_for_path("/blog/index.html") == "blog"
        assert S.page_key_for_path("/topics/index.html") == "topics"
        assert S.page_key_for_path("/") == ""


class TestCommittedCards:
    def test_network_card_and_legacy_default_exist_at_card_size(self):
        from PIL import Image
        for p in (S.network_card_path(), ROOT / "assets" / "og-preview.png"):
            assert p.is_file(), p
            with Image.open(p) as im:
                assert im.size == (1200, 630)

    def test_every_page_card_named_by_the_builder_is_committed(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_share_cards as B
        for key in B._page_cards(31):
            assert S.page_card_path(key).is_file(), key

    def test_every_card_has_alt_text(self):
        alts = json.loads(S.MANIFEST_PATH.read_text(encoding="utf-8"))["alt"]
        for card in sorted((ROOT / "assets" / "share").rglob("*.jpg")):
            rel = card.relative_to(ROOT).as_posix()
            assert alts.get(rel), rel

    def test_fonts_are_bundled_with_their_licences(self):
        fonts = ROOT / "assets" / "fonts"
        for name in ("DMSans-Bold.ttf", "DMSans-Medium.ttf", "SourceSerif4-Bold.ttf",
                     "GolosText-Bold.ttf", "GolosText-Medium.ttf"):
            assert (fonts / name).is_file(), name
        for lic in ("DMSans-OFL.txt", "SourceSerif4-OFL.txt", "GolosText-OFL.txt"):
            assert "Open Font License" in (fonts / lic).read_text(encoding="utf-8")


class TestEpisodeCards:
    def _config(self, tmp_path, mode="public"):
        return SimpleNamespace(
            slug="models_agents", name="Models & Agents",
            access=SimpleNamespace(mode=mode),
            episode=SimpleNamespace(output_dir=str(tmp_path / "digests")),
            storage=SimpleNamespace(provider="r2", bucket="podcast-audio",
                                    endpoint_env="E", access_key_env="A", secret_key_env="K",
                                    public_base_url="https://audio.nerranetwork.com"))

    def test_upload_records_the_card_and_the_blog_reads_it(self, tmp_path, monkeypatch):
        import engine.storage as storage
        seen = {}

        def fake_upload(local, key, **kw):
            seen.update(key=key, **kw)
            return f"https://audio.nerranetwork.com/{key}"

        monkeypatch.setattr(storage, "upload_to_r2", fake_upload)
        for name in ("E", "A", "K"):
            monkeypatch.setenv(name, "x")
        monkeypatch.setattr(S, "ROOT", tmp_path)
        cfg = self._config(tmp_path)
        url = S.episode_card_for(cfg, episode_num=212, hook="**HOOK:** A [model](https://x) ships",
                                 date_str="2026-10-18", out_dir=tmp_path / "out")
        assert url == "https://audio.nerranetwork.com/share/models_agents/ep212-art.jpg"
        assert seen["content_type"] == "image/jpeg"
        digest_dir = tmp_path / "digests"
        assert S.episode_card_url(digest_dir, 212) == url

        from engine.blog import _episode_og_image, _episode_og_alt
        meta = {"_md_path": str(digest_dir / "x.md"), "hook": "A model ships"}
        assert _episode_og_image(meta, {"podcast_image": "assets/covers/m.jpg"}, 212) == url
        assert _episode_og_image(meta, {"podcast_image": "assets/covers/m.jpg"}, 211).endswith(
            "assets/covers/m.jpg")
        assert _episode_og_alt(meta, {"name": "Models & Agents"}, 212) == \
            "Models & Agents, episode 212: A model ships"

    def test_a_scene_card_takes_a_new_key(self):
        assert S.episode_r2_key("spacex", 130, "scene") == "share/spacex/ep130-scene.jpg"
        assert S.episode_r2_key("spacex", 130, "art") != S.episode_r2_key("spacex", 130, "scene")

    def test_a_members_only_episode_gets_no_public_card(self, tmp_path):
        cfg = self._config(tmp_path, mode="members_only")
        assert S.episode_card_for(cfg, episode_num=5, hook="Desk", upload=False) == ""

    def test_without_credentials_nothing_is_recorded(self, tmp_path, monkeypatch):
        for k in ("E", "A", "K"):
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setattr(S, "ROOT", tmp_path)
        cfg = self._config(tmp_path)
        assert S.episode_card_for(cfg, episode_num=7, hook="A hook",
                                  out_dir=tmp_path / "o") == ""
        assert not S.episode_record_path(tmp_path / "digests").exists()


class TestWiring:
    def test_base_template_goes_through_the_resolver(self):
        src = (ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8")
        assert "resolve_og_image(" in src
        assert 'property="og:image:width"' in src and 'name="twitter:image:alt"' in src
        assert "_og.alt | e" in src  # the env does not autoescape

    def test_no_other_base_template_writes_its_own_og_image(self):
        """A template that writes og:image itself bypasses the resolver."""
        allowed = {"base.html.j2"}
        for t in (ROOT / "templates").glob("*.j2"):
            if t.name in allowed:
                continue
            assert 'property="og:image"' not in t.read_text(encoding="utf-8"), t.name

    def test_a_rendered_show_page_carries_its_card(self, tmp_path):
        import generate_html as g
        g.generate_show_page("models_agents", output_dir=tmp_path)
        html = (tmp_path / "models-agents.html").read_text(encoding="utf-8")
        assert 'og:image" content="https://nerranetwork.com/assets/share/shows/models_agents.jpg"' in html
        assert '<meta property="og:image:width" content="1200">' in html
        assert "Models &amp; Agents" in re.search(r'og:image:alt" content="([^"]*)"', html).group(1)

    def test_nightly_builds_and_commits_the_cards(self):
        wf = (ROOT / ".github" / "workflows" / "nightly-maintenance.yml").read_text(encoding="utf-8")
        assert "scripts/build_share_cards.py" in wf
        assert "assets/share/**" in wf
        assert wf.index("build_share_cards.py") < wf.index("generate_html.py --network")

    def test_run_show_draws_both_episode_cards(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert src.count("episode_card_for") >= 2
        assert src.index("12a-share.") < src.index("    _write_blog_post()\n")
        pipe = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'metrics.record("share_card"' in pipe

    def test_no_dangling_og_default(self):
        assert "og-default.png" not in (ROOT / "generate_html.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("slug", ["finansy_prosto", "privet_russian"])
def test_russian_show_cards_are_committed(slug):
    assert S.show_card_path(slug).is_file()
