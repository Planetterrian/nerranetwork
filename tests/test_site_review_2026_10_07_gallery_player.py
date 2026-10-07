"""Oct 7 2026 site review — gallery and network player page weight.

Measured before the fix: ``gallery.html`` parsed the 22 MB gallery manifest
before its first card (6.7 MB of it prompts the lightbox hides by default),
``age-of-ai.html`` fetched the same 22 MB to say "no images yet" because its
per-show slice did not exist and the embed fell back to the whole manifest,
Tesla's page fetched a 2.4 MB slice on load for a gallery ~17,000 px down,
and ``player.html`` moved ~16 MB: every show's summaries JSON (full digests)
plus 31 covers at 3000 px for 48 px slots.

What binds now:

* The grid reads a slim index (``site/data/gallery/<slug>.index.json``,
  ``_network.index.json``) derived from the manifest in the same run; the
  prompt is read from the show's full slice only when a visitor asks.
* A per-show embed never falls back to the manifest, starts its fetch when
  it nears the viewport, and is only mounted when its index has an image.
* The network gallery's first page is one image per episode, round-robin.
* The player renders from a compact episode index built into the page:
  every summaries shape (Age of AI's ``{"episodes": [...]}`` too), audio
  through the OP3 prefix, the 400 px cover, chips only for shows with an
  episode, previews that keep their hyphens.
* Player controls are keyboard- and phone-usable, and the nav follows the
  base contract (no "Home", no inline onclick).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.gallery_uploader import GalleryConfig  # noqa: E402
from scripts import build_gallery_manifest as bgm  # noqa: E402

GALLERY_JS = ROOT / "assets" / "js" / "gallery.js"
PLAYER_TEMPLATE = ROOT / "templates" / "player_page.html.j2"


def _strip_jinja_comments(text: str) -> str:
    return re.sub(r"\{#.*?#\}", "", text, flags=re.S)


@pytest.fixture
def config() -> GalleryConfig:
    return GalleryConfig(
        bucket="nerra-gallery",
        endpoint_url="https://acct.r2.cloudflarestorage.com",
        access_key="fake",
        secret_key="fake",
        public_base_url="https://gallery.example.com",
    )


def _sidecar(image_id, slug="tesla", episode_id="ep001", date="2026-10-01",
             title="Ep 1: A hook", generated_at="2026-10-01T10:00:00+00:00",
             fmt="jpeg", prompt="a prompt, clean photographic composition",
             caption="", name=None):
    return {
        "image_id": image_id, "show_slug": slug,
        "show_name": name or slug.title(), "episode_id": episode_id,
        "episode_title": title, "episode_date": date,
        "generated_at": generated_at, "format": fmt, "prompt": prompt,
        "intended_use": "segment_card", "caption": caption,
        "tags": [slug], "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "attribution": "Nerra Network",
    }


def _hydrate(index: dict) -> list:
    """Python mirror of gallery.js ``hydrateIndex`` (the node test below
    runs the real one against the same expectations)."""
    ef, imf = index["episode_fields"], index["image_fields"]
    names = {s["slug"]: s["name"] for s in index["shows"]}
    out = []
    for n, row in enumerate(index["images"]):
        ep = index["episodes"][row[imf.index("episode")]]
        slug = ep[ef.index("show_slug")]
        stem = "/".join([slug, ep[ef.index("episode_date")],
                         ep[ef.index("episode_id")], row[imf.index("image_id")]])
        img = {
            "image_id": row[imf.index("image_id")],
            "show_slug": slug, "show_name": names.get(slug, slug),
            "episode_id": ep[ef.index("episode_id")],
            "episode_date": ep[ef.index("episode_date")],
            "episode_title": ep[ef.index("episode_title")],
            "caption": row[imf.index("caption")],
            "thumbnail_url": f"{index['base_url']}/{stem}.thumb.webp",
            "original_key": f"{stem}.{row[imf.index('format')]}",
            "license": index["license"], "license_url": index["license_url"],
            "attribution": index["attribution"],
        }
        img.update(index["overrides"].get(str(n), {}))
        out.append(img)
    return out


_GRID_FIELDS = ("image_id", "show_slug", "show_name", "episode_id",
                "episode_date", "episode_title", "caption", "thumbnail_url",
                "original_key", "license", "license_url", "attribution")


# ---------------------------------------------------------------------------
# The slim index
# ---------------------------------------------------------------------------


class TestGalleryIndex:
    def _manifest(self, config):
        return bgm.build_manifest([
            _sidecar("a1", generated_at="2026-10-01T10:00:00+00:00"),
            _sidecar("a2", generated_at="2026-10-01T10:01:00+00:00", fmt="png",
                     caption="Cover art"),
            _sidecar("b1", slug="spacex", episode_id="ep122", date="2026-10-06",
                     title="Ep 122: Dragon", name="SpaceX Daily",
                     generated_at="2026-10-06T09:00:00+00:00"),
        ], config=config)

    def test_index_rebuilds_every_record_the_grid_and_lightbox_read(self, config):
        manifest = self._manifest(config)
        index = bgm.build_gallery_index(manifest)
        assert index["image_count"] == manifest["image_count"] == 3
        rebuilt = _hydrate(index)
        for orig, new in zip(manifest["images"], rebuilt):
            for field in _GRID_FIELDS:
                assert new[field] == orig[field], field
        assert index["overrides"] == {}

    def test_index_carries_no_prompt_and_no_derivable_url(self, config):
        index = bgm.build_gallery_index(self._manifest(config))
        text = json.dumps(index)
        for absent in ("a prompt", "sidecar_url", "original_url", ".thumb.webp"):
            assert absent not in text, absent

    def test_a_record_that_breaks_the_url_rule_is_carried_verbatim(self, config):
        manifest = self._manifest(config)
        odd = manifest["images"][1]
        odd["thumbnail_url"] = "https://elsewhere.example/x.thumb.webp"
        odd["license"] = "CC0"
        same_episode = manifest["images"][2]
        same_episode["episode_title"] = "Ep 1: retitled"
        index = bgm.build_gallery_index(manifest)
        rebuilt = _hydrate(index)
        for orig, new in zip(manifest["images"], rebuilt):
            for field in _GRID_FIELDS:
                assert new[field] == orig[field], field

    def test_per_show_index_holds_only_that_show(self, config):
        index = bgm.build_gallery_index(self._manifest(config), "spacex")
        assert index["image_count"] == 1
        assert {e[0] for e in index["episodes"]} == {"spacex"}
        assert [s["slug"] for s in index["shows"]] == ["spacex"]

    def test_writer_slices_and_indexes_share_a_directory_safely(self, tmp_path, config):
        manifest = self._manifest(config)
        out = tmp_path / "gallery-manifest.json"
        bgm.write_show_slices(manifest, out)
        written = {p.name for p in bgm.write_gallery_indexes(manifest, out)}
        assert written == {"_network.index.json", "tesla.index.json", "spacex.index.json"}
        # Rewriting the slices never deletes an index, and vice versa.
        bgm.write_show_slices(manifest, out)
        assert (tmp_path / "gallery" / "tesla.index.json").exists()
        assert (tmp_path / "gallery" / "tesla.json").exists()
        # Idempotent; a vanished show's index goes.
        assert bgm.write_gallery_indexes(manifest, out) == []
        (tmp_path / "gallery" / "gone.index.json").write_text("{}", encoding="utf-8")
        bgm.write_gallery_indexes(manifest, out)
        assert not (tmp_path / "gallery" / "gone.index.json").exists()

    def test_failed_walk_keeps_the_committed_indexes(self, tmp_path, monkeypatch, config):
        out = tmp_path / "gallery-manifest.json"
        manifest = self._manifest(config)
        out.write_text(json.dumps(manifest), encoding="utf-8")
        bgm.write_gallery_indexes(manifest, out)
        before = (tmp_path / "gallery" / "_network.index.json").read_text(encoding="utf-8")
        for var, value in (("R2_GALLERY_BUCKET", "b"), ("R2_ENDPOINT_URL", "https://r2"),
                           ("R2_ACCESS_KEY_ID", "k"), ("R2_SECRET_ACCESS_KEY", "s")):
            monkeypatch.setenv(var, value)

        def _boom(cfg):
            raise RuntimeError("R2 hiccup")
        monkeypatch.setattr(bgm, "_make_s3_client", _boom)
        assert bgm.main(["--out", str(out)]) == 0
        after = (tmp_path / "gallery" / "_network.index.json").read_text(encoding="utf-8")
        assert after == before

    def test_offline_rebuild_refuses_an_empty_manifest(self, tmp_path):
        out = tmp_path / "gallery-manifest.json"
        assert bgm.main(["--indexes-only", "--out", str(out)]) == 1
        out.write_text(json.dumps({"images": []}), encoding="utf-8")
        assert bgm.main(["--indexes-only", "--out", str(out)]) == 1
        assert not (tmp_path / "gallery").exists()

    def test_offline_rebuild_derives_from_the_manifest(self, tmp_path, config):
        out = tmp_path / "gallery-manifest.json"
        out.write_text(json.dumps(self._manifest(config)), encoding="utf-8")
        assert bgm.main(["--indexes-only", "--out", str(out)]) == 0
        index = json.loads((tmp_path / "gallery" / "_network.index.json").read_text(encoding="utf-8"))
        assert index["image_count"] == 3

    def test_committed_network_index_is_populated(self):
        """The site works before the next nightly: the indexes are committed."""
        path = ROOT / "site" / "data" / "gallery" / "_network.index.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["images"] and data["episodes"] and data["base_url"].startswith("https://")


class TestIndexIsCommittedWhereverTheManifestIs:
    def test_glob_whitelists_cover_the_indexes(self):
        for wf in ("build-gallery-manifest.yml", "nightly-maintenance.yml"):
            text = (ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8")
            assert "site/data/gallery/*.json" in text, wf
        finalize = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
        assert "git add site/data/gallery/*.json" in finalize
        assert bgm.NETWORK_INDEX_NAME.endswith(".json")
        assert bgm.INDEX_SUFFIX.endswith(".json")


# ---------------------------------------------------------------------------
# gallery.js
# ---------------------------------------------------------------------------


def _js_function(src: str, name: str) -> str:
    """The text of ``function <name>(...) {...}`` by brace matching."""
    start = src.index(f"function {name}(")
    depth = 0
    for i in range(src.index("{", start), len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError(name)


class TestGalleryClient:
    def test_no_fallback_to_the_full_manifest(self):
        js = GALLERY_JS.read_text(encoding="utf-8")
        assert "load(MANIFEST_URL)" not in js
        assert "fetch(MANIFEST_URL" not in js
        assert ".index.json'" in js
        assert "'_network'" in js

    def test_per_show_embed_waits_for_the_viewport(self):
        js = GALLERY_JS.read_text(encoding="utf-8")
        assert "IntersectionObserver" in js and "rootMargin" in js
        # Falls back to an immediate fetch where IO is missing.
        assert re.search(r"'IntersectionObserver' in window\)[\s\S]*?else \{\s*start\(\);", js)

    def test_prompt_reveal_is_actually_visible(self):
        js = GALLERY_JS.read_text(encoding="utf-8")
        assert '<details class="nn-lb-prompt" open hidden>' in js

    def test_section_sets_the_data_base(self):
        src = (ROOT / "templates" / "_gallery_section.html.j2").read_text(encoding="utf-8")
        assert "window.NN_GALLERY_DATA_BASE" in _strip_jinja_comments(src)

    @pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
    def test_real_hydrate_and_round_robin(self, config):
        js = GALLERY_JS.read_text(encoding="utf-8")
        manifest = bgm.build_manifest(
            [_sidecar(f"s{i}", slug="spacex", episode_id="ep122", date="2026-10-06",
                      generated_at=f"2026-10-06T09:{i:02d}:00+00:00") for i in range(13)]
            + [_sidecar(f"u{i}", slug="uc", episode_id="ep134", date="2026-10-06",
                        generated_at=f"2026-10-06T08:{i:02d}:00+00:00") for i in range(5)]
            + [_sidecar(f"t{i}", episode_id="ep626", date="2026-10-05",
                        generated_at=f"2026-10-05T08:{i:02d}:00+00:00") for i in range(5)],
            config=config,
        )
        index = bgm.build_gallery_index(manifest)
        script = (
            _js_function(js, "hydrateIndex") + "\n" + _js_function(js, "diversifyHead")
            + "\nconst idx = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
            + "\nconst imgs = hydrateIndex(idx);"
            + "\nconst page = diversifyHead(imgs, 6);"
            + "\nconsole.log(JSON.stringify({imgs, page: page.map(i => i.image_id), n: page.length}));"
        )
        res = subprocess.run(["node", "-e", script], input=json.dumps(index),
                             capture_output=True, text=True, check=True)
        out = json.loads(res.stdout)
        for orig, new in zip(manifest["images"], out["imgs"]):
            for field in _GRID_FIELDS:
                assert new[field] == orig[field], field
        head = out["page"][:6]
        # Three episodes, round-robin: two from each in the first six.
        assert [h[0] for h in head] == ["s", "u", "t", "s", "u", "t"]
        assert out["n"] == 23 and len(set(out["page"])) == 23


class TestGalleryMountDecision:
    def test_mount_needs_an_index_with_images(self, tmp_path, monkeypatch):
        import generate_html as gh
        monkeypatch.setattr(gh, "ROOT", tmp_path)
        assert gh._gallery_index_has_images("tesla") is False
        d = tmp_path / "site" / "data" / "gallery"
        d.mkdir(parents=True)
        (d / "tesla.index.json").write_text(json.dumps({"images": []}), encoding="utf-8")
        assert gh._gallery_index_has_images("tesla") is False
        (d / "tesla.index.json").write_text(json.dumps({"images": [["a", 0, "png", "", ""]]}),
                                            encoding="utf-8")
        assert gh._gallery_index_has_images("tesla") is True

    def test_show_page_decision_uses_it(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        block = src[src.index("gallery_enabled = ("):]
        block = block[:block.index("\n    )\n")]
        assert "_gallery_index_has_images(slug)" in block

    def test_age_of_ai_has_no_index_and_no_mount(self):
        import generate_html as gh
        assert gh._gallery_index_has_images("age_of_ai") is False


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_network(tmp_path, monkeypatch):
    """Three shows on disk: a daily, an interview-shaped file, an empty one."""
    import generate_html as gh

    (tmp_path / "digests").mkdir()
    (tmp_path / "assets" / "covers").mkdir(parents=True)
    (tmp_path / "assets" / "covers" / "daily-400.webp").write_bytes(b"x")
    (tmp_path / "assets" / "covers" / "daily-800.webp").write_bytes(b"x")
    (tmp_path / "digests" / "daily.json").write_text(json.dumps({"summaries": [
        {"episode_num": 7, "date": "2026-10-06", "episode_title": "Ep 7: Lead story",
         "audio_url": "https://audio.nerranetwork.com/daily/D_Ep007.mp3",
         "content": "# Daily\n> **Lead story**\n"},
        {"episode_num": 6, "date": "2026-10-05", "episode_title": "Ep 6: Other",
         "audio_url": "https://op3.dev/e/audio.nerranetwork.com/daily/D_Ep006.mp3",
         "content": "> **A $6.9-billion deal for thirty-two satellites is a well-known first-of-its-kind thing.**"},
    ]}), encoding="utf-8")
    (tmp_path / "digests" / "iv.json").write_text(json.dumps({"episodes": [
        {"episode": "3", "date": "2026-09-27", "title": "Ep3: Jane Doe",
         "hook": "A guest talks about storms", "audio_url": "https://audio.nerranetwork.com/iv/raw/x.mp3"},
    ]}), encoding="utf-8")
    (tmp_path / "digests" / "none.json").write_text(json.dumps({"summaries": []}), encoding="utf-8")
    (tmp_path / "daily.rss").write_text(
        '<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel>'
        "<item><title>Ep 7</title><itunes:episode>7</itunes:episode>"
        "<itunes:duration>08:09</itunes:duration></item></channel></rss>",
        encoding="utf-8")
    shows = {
        "daily": {"slug": "daily", "name": "Daily", "json_path": "digests/daily.json",
                  "podcast_image": "assets/covers/daily.jpg", "brand_color": "#123456",
                  "rss_file": "daily.rss"},
        "iv": {"slug": "iv", "name": "Interviews", "json_path": "digests/iv.json",
               "podcast_image": "assets/covers/iv.jpg", "brand_color": "#654321"},
        "none": {"slug": "none", "name": "No Feed", "json_path": "digests/none.json",
                 "podcast_image": "assets/covers/none.jpg", "brand_color": "#000000"},
    }
    monkeypatch.setattr(gh, "ROOT", tmp_path)
    monkeypatch.setattr(gh, "NETWORK_SHOWS", shows)
    return gh


class TestPlayerIndex:
    def test_every_summaries_shape_and_no_empty_show(self, fake_network):
        index = fake_network._player_episode_index()
        assert [s["slug"] for s in index["shows"]] == ["daily", "iv"]
        ids = [e["id"] for e in index["episodes"]]
        assert ids == ["daily::7", "daily::6", "iv::3"]

    def test_audio_is_routed_through_op3_once(self, fake_network):
        audio = {e["id"]: e["audio"] for e in fake_network._player_episode_index()["episodes"]}
        assert audio["daily::7"] == "https://op3.dev/e/audio.nerranetwork.com/daily/D_Ep007.mp3"
        assert audio["daily::6"] == "https://op3.dev/e/audio.nerranetwork.com/daily/D_Ep006.mp3"
        assert audio["iv::3"].startswith("https://op3.dev/e/audio.nerranetwork.com/iv/")

    def test_small_cover_with_jpeg_fallback(self, fake_network):
        shows = {s["slug"]: s for s in fake_network._player_episode_index()["shows"]}
        assert shows["daily"]["cover"] == "assets/covers/daily-400.webp"
        assert shows["daily"]["artwork"] == "assets/covers/daily-800.webp"
        assert shows["daily"]["cover_fallback"] == "assets/covers/daily.jpg"
        assert shows["iv"]["cover"] == "assets/covers/iv.jpg"
        assert shows["daily"]["audio_dir"] == "daily"

    def test_previews_keep_hyphens_and_never_repeat_the_title(self, fake_network):
        eps = {e["id"]: e for e in fake_network._player_episode_index()["episodes"]}
        assert eps["daily::7"]["preview"] == ""  # the title already says it
        assert "6.9-billion" in eps["daily::6"]["preview"]
        assert "thirty-two" in eps["daily::6"]["preview"]
        assert "first-of-its-kind" in eps["daily::6"]["preview"]
        assert eps["iv::3"]["preview"] == "A guest talks about storms"

    def test_duration_comes_from_the_feed(self, fake_network):
        eps = {e["id"]: e for e in fake_network._player_episode_index()["episodes"]}
        assert eps["daily::7"]["duration"] == 489
        assert eps["daily::6"]["duration"] is None


@pytest.fixture(scope="module")
def player_html(tmp_path_factory):
    import generate_html as gh
    out = tmp_path_factory.mktemp("player")
    gh.generate_player_page(output_dir=out)
    return (out / "player.html").read_text(encoding="utf-8")


def _embedded_index(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="player-index">(.*?)</script>', html, re.S)
    assert m, "player index not embedded"
    return json.loads(m.group(1))


class TestPlayerPage:
    def test_no_summaries_json_is_fetched(self, player_html):
        assert "jsonPath" not in player_html
        assert "summaries_" not in player_html.split('id="player-index"')[0].split("<script")[-1]
        assert not re.search(r"fetch\([^)]*summaries", player_html)

    def test_chips_are_exactly_the_shows_with_episodes(self, player_html):
        index = _embedded_index(player_html)
        with_eps = {e["show"] for e in index["episodes"]}
        chips = set(re.findall(r'class="nn-filter-btn" data-filter="([^"]+)"', player_html))
        assert chips == with_eps == {s["slug"] for s in index["shows"]}
        assert "nerra_voices" not in chips
        assert "age_of_ai" in with_eps
        desc = re.search(r'<meta name="description" content="Listen to (\d+) ', player_html)
        assert desc and int(desc.group(1)) == len(chips)

    def test_audio_is_measured(self, player_html):
        for ep in _embedded_index(player_html)["episodes"]:
            if "audio.nerranetwork.com" in ep["audio"]:
                assert ep["audio"].startswith("https://op3.dev/e/audio.nerranetwork.com/"), ep["id"]
                assert ep["audio"].count("op3.dev") == 1

    def test_covers_are_small(self, player_html):
        for show in _embedded_index(player_html)["shows"]:
            if (ROOT / show["cover_fallback"].replace(".jpg", "-400.webp")).exists():
                assert show["cover"].endswith("-400.webp"), show["slug"]

    def test_nav_follows_the_base_contract(self, player_html):
        nav = player_html[player_html.index('<ul class="nn-nav-links">'):]
        nav = nav[:nav.index("</ul>")]
        menu = player_html[player_html.index('id="mobileMenu"'):]
        menu = menu[:menu.index("nn-mobile-shows")]
        for block in (nav, menu):
            assert ">Home<" not in block
            assert 'aria-current="page"' in block
        assert "onclick=" not in menu

    def test_controls_are_keyboard_and_phone_usable(self, player_html):
        assert re.search(r'<input type="range" class="nn-progress-range" id="progress-range"[^>]*aria-label="Seek"', player_html)
        assert 'role="slider"' not in player_html
        assert len(re.findall(r'class="nn-speed-btn[^"]*" data-speed="[^"]+" aria-pressed=', player_html)) == 5
        assert 'id="queue-toggle" aria-label="Queue, ' in player_html
        assert "'Queue, ' + queue.length" in player_html
        css = player_html[player_html.index("@media (max-width: 480px)"):]
        css = css[:css.index("}\n@media")]
        assert ".nn-progress-wrap { display: none; }" not in css
        assert re.search(r"\.nn-player-chips \{[^}]*flex-wrap: nowrap;[^}]*overflow-x: auto;", player_html)

    def test_in_queue_button_is_readable(self, player_html):
        rule = re.search(r"\.nn-add-queue-btn\.in-queue,[^{]*\{([^}]*)\}", player_html)
        assert rule and "opacity" not in rule.group(1)
        assert "#9B85FF" in rule.group(1)

    def test_no_hyphen_stripping_preview_code(self):
        src = _strip_jinja_comments(PLAYER_TEMPLATE.read_text(encoding="utf-8"))
        assert r"[>\-]\s*" not in src
        assert "data.summaries || data" not in src


def _relative_luminance(hex_color: str) -> float:
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def test_in_queue_colour_clears_aa_on_the_card():
    # --nn-card is 5% white over --nn-bg #0B0F1A -> ~#161A24.
    card = _relative_luminance("#161A24")
    fg = _relative_luminance("#9B85FF")
    assert (fg + 0.05) / (card + 0.05) >= 4.5
