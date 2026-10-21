"""Oct 21 2026 — the media kit (``press.html``; ``media-kit.html`` forwards).

A publicist pitching a guest for Nerra Voices asked Mira for a media kit and
the network had a thin press page: no audience figures, two hand-typed
guest names, a language list naming a track that had been switched off, one
logo, and an address nobody had confirmed reads mail. The kit is now
generated from committed data on every ``--static-pages`` run, so it grows
with the network. These guards keep it honest:

* every figure comes from a committed file, and an unmeasured one is a dash,
  never a zero;
* every sentence about the network comes from ``engine.brand``;
* the guest list, the episode counts and where an interview is distributed
  are read from the data and the show YAML, never typed;
* the brand zip is byte-identical across builds and carries a PNG beside
  every SVG (the SVGs set words in DM Sans, which a reader may not have);
* the two wordmark logos contain their own artwork (both had cut it off).
"""

from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate_html as G  # noqa: E402
from engine import brand as B  # noqa: E402

TEMPLATE = (ROOT / "templates" / "press.html.j2").read_text(encoding="utf-8")


def _text(html: str) -> str:
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", body)


@pytest.fixture(scope="module")
def kit(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("kit")
    return G.generate_press_page(output_dir=out).read_text(encoding="utf-8")


class TestTheKitIsComplete:
    SECTIONS = ("at-a-glance", "audience", "book-a-guest", "mira", "shows", "trust",
                "founders", "boilerplate", "brand", "questions", "contact")

    def test_every_section_renders(self, kit):
        for sid in self.SECTIONS:
            assert f'id="{sid}"' in kit, sid

    def test_the_short_address_forwards_to_the_kit(self):
        data = yaml.safe_load((ROOT / "site" / "redirects.yaml").read_text(encoding="utf-8"))
        assert {"from": "media-kit.html", "to": "press.html"} in [
            {"from": r["from"], "to": r["to"]} for r in data["redirects"]]

    def test_the_kit_regenerates_with_the_static_pages(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        body = src.split("def generate_static_pages(")[1].split("\ndef ")[0]
        assert "generate_press_page(" in body


class TestNumbersComeFromTheData:
    def test_downloads_are_the_audience_headline(self, kit):
        net = json.loads((ROOT / "api" / "audience_headline.json").read_text(encoding="utf-8"))["network"]
        assert f"{net['downloads_30d']:,}" in _text(kit)

    def test_youtube_subscribers_are_the_sum_of_the_channels(self, kit):
        yt = json.loads((ROOT / "api" / "youtube_stats.json").read_text(encoding="utf-8"))
        total = sum(int(c.get("subscribers") or 0) for c in yt["channels"].values())
        assert f"{total:,}" in _text(kit)

    def test_an_unmeasured_figure_is_a_dash_never_a_zero(self, tmp_path, monkeypatch):
        real = G._load_json_quiet
        monkeypatch.setattr(G, "_load_json_quiet",
                            lambda p: None if Path(p).parent.name == "api" else real(p))
        text = _text(G.generate_press_page(output_dir=tmp_path).read_text(encoding="utf-8"))
        assert "— podcast downloads in the last 30 days" in text
        assert "0 podcast downloads" not in text
        assert "— YouTube subscribers" in text

    def test_gender_is_never_printed(self, kit):
        # YouTube suppresses small cells, so the English channel reads 100%
        # one gender: an artifact, never a fact for a media kit.
        assert not re.search(r"\b(male|female|men|women)\b", _text(kit), re.I)

    def test_no_language_the_network_does_not_produce(self, kit):
        langs = G._listening_languages()
        if "zh" not in langs:
            assert "Chinese" not in _text(kit) and "中文" not in kit

    def test_the_trust_record_matches_the_claims_page(self, kit):
        totals = G._claims_network_ledger(G._build_all_shows_list())["totals"]
        if isinstance(totals.get("claims"), int) and totals["claims"]:
            assert f"{totals['claims']:,} claims checked in the last" in _text(kit)


class TestTheGuestListIsTheRecord:
    def test_no_guest_is_typed_into_the_template(self):
        for slug in ("age_of_ai", "nerra_voices"):
            data = json.loads((ROOT / "digests" / slug / f"summaries_{slug}.json")
                              .read_text(encoding="utf-8"))
            for ep in data.get("episodes") or []:
                guest = ep.get("guest") or ""
                if guest and guest != "Patrick Novak":
                    assert guest not in TEMPLATE, guest

    def test_the_newest_guests_are_listed(self, kit):
        for show in G._media_kit_interview_shows():
            cards = G._interview_episode_cards(show["slug"], G.NETWORK_SHOWS[show["slug"]])
            for c in cards[:3]:
                assert c["guest"] in kit, (show["slug"], c["guest"])

    def test_a_distribution_flag_that_is_off_is_never_promised(self):
        for show in G._media_kit_interview_shows():
            cfg = yaml.safe_load((ROOT / "shows" / f"{show['slug']}.yaml").read_text(encoding="utf-8"))
            yt = bool((cfg.get("youtube") or {}).get("enabled"))
            nl = bool((cfg.get("newsletter") or {}).get("enabled"))
            where = " ".join(show["where"])
            assert ("YouTube" in where) == yt, show["slug"]
            assert ("newsletter" in where) == nl, show["slug"]

    def test_booking_links_are_the_ones_mira_sends(self):
        from pipelines.voices.shows import get_show
        for show in G._media_kit_interview_shows():
            assert show["booking_url"] == get_show(show["slug"]).booking_url


class TestCopyHasOneOwner:
    def test_boilerplate_and_founders_come_from_brand(self, kit):
        bp = B.network_boilerplate(G._public_show_count_cached(), G._listening_languages())
        for text in bp.values():
            assert text in kit.replace("&#39;", "'")
        for f in B.FOUNDERS:
            assert f["bio"] in kit.replace("&#39;", "'")
        assert "independent podcast network based" not in TEMPLATE

    def test_the_kit_names_the_one_inbox(self, kit):
        assert B.PRESS_EMAIL == B.CONTACT_EMAIL
        assert f"mailto:{B.PRESS_EMAIL}" in kit
        assert "press@nerranetwork.com" not in kit

    def test_boilerplate_states_only_the_free_count(self):
        bp = B.network_boilerplate(26, ["en", "fr", "ru"])
        assert "26 free podcasts" in bp["short"] and "26 free shows" in bp["medium"]
        assert "English, French and Russian" in bp["medium"]
        # Not every show publishes to YouTube (env_intel, finansy_prosto and
        # Nerra Voices do not), so the long form never says every episode is there.
        assert "most shows publish to YouTube" in bp["long"]

    def test_the_mira_sentence_stays_narrow(self):
        medium = B.network_boilerplate(26)["medium"]
        assert "decide whether their conversation is published at all" in medium
        assert "first" not in medium.lower()


class TestBrandAssets:
    def test_the_zip_is_byte_identical_across_builds(self, tmp_path):
        a = G.build_media_kit_zip(tmp_path / "a.zip").read_bytes()
        b = G.build_media_kit_zip(tmp_path / "b.zip").read_bytes()
        assert a == b

    def test_the_zip_carries_a_png_beside_every_svg(self, tmp_path):
        names = set(zipfile.ZipFile(io.BytesIO(
            G.build_media_kit_zip(tmp_path / "k.zip").read_bytes())).namelist())
        for rel, _label, _bg in G.MEDIA_KIT_LOGOS:
            stem = Path(rel).stem
            assert f"{stem}.svg" in names and f"{stem}.png" in names, stem
        assert "README.txt" in names

    def test_every_logo_has_a_committed_png(self):
        for rel, _label, _bg in G.MEDIA_KIT_LOGOS:
            assert (ROOT / G._media_kit_png(rel)).is_file(), rel

    @pytest.mark.parametrize("name,min_width,min_x", [
        ("nerra-logo-horizontal.svg", 632, 0),
        ("nerra-logo-horizontal-light.svg", 632, 0),
        ("nerra-logo-stacked.svg", 460, -40),
    ])
    def test_the_wordmark_frames_hold_their_artwork(self, name, min_width, min_x):
        # "Network" ends at x=611.8 and the stacked wordmark spans
        # -23..406; the old 600 and 0..380 frames cut both.
        for root in (ROOT / "assets", ROOT / "brand-refresh-2026" / "assets"):
            svg = (root / name).read_text(encoding="utf-8")
            x, _y, w, _h = (float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split())
            assert w >= min_width and x <= min_x, (root, name)
