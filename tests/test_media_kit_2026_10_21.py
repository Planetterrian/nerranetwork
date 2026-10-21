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

Same day, operator follow-up: the kit carries growth on every channel
(complete OP3 weeks, nightly YouTube snapshots, followers wherever a platform
reports them), what the network is building next (stated as work, never a
forecast), the landing page's tagline and promise word for word, and a
"Share Nerra" section of downloadable show art, page images, copy-ready posts
and usage rules.
"""

from __future__ import annotations

import datetime as dt
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
    SECTIONS = ("at-a-glance", "audience", "growth-next", "book-a-guest", "mira", "shows",
                "trust", "founders", "boilerplate", "brand", "marketing", "questions", "contact")

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
        assert "— subscribers and followers on the channels that report them" in text
        assert "— YouTube views in" in text

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


class TestGrowth:
    def test_the_chart_reads_complete_weeks_only(self):
        hist = json.loads((ROOT / "api" / "op3_history.json").read_text(encoding="utf-8"))
        updated = dt.date.fromisoformat(hist["updated_at"][:10])
        g = G._media_kit_growth(G._public_shows(G._build_all_shows_list()))
        for w in g["weekly_downloads"]:
            assert dt.date.fromisoformat(w["iso"]) + dt.timedelta(days=7) <= updated, w

    def test_a_rate_needs_a_real_denominator(self):
        # @NerraFR went from 2 to 26 subscribers in its first weeks: that is
        # never printed as "+1,200%".
        assert G._pct(26, 2) is None
        assert G._pct(73, 48) == 52

    def test_subscriber_total_is_the_latest_snapshot(self, kit):
        rows = json.loads((ROOT / "api" / "youtube_channel_history.json")
                          .read_text(encoding="utf-8"))["rows"]
        last = max(r["date"] for r in rows)
        total = sum(r["subscribers"] for r in rows if r["date"] == last)
        assert f"{total:,} now" in _text(kit)

    def test_every_bar_has_a_hover_title_and_a_table(self, kit):
        g = G._media_kit_growth(G._public_shows(G._build_all_shows_list()))
        for chart, series in ((g["downloads_chart"], g["weekly_downloads"][-G.MEDIA_KIT_CHART_WEEKS:]),
                              (g["subs_chart"], g["weekly_subs"])):
            assert chart.count("<title>") == len(series)
        assert kit.count("Show the numbers") == 2

    def test_plans_are_never_a_forecast(self):
        for heading, body in B.GROWTH_NEXT:
            assert not re.search(r"\b(will reach|projected|forecast|expect(ed)? to)\b", body, re.I), heading

    def test_plan_counts_are_filled_from_the_data(self, kit):
        shows = G._public_shows(G._build_all_shows_list())
        apple = sum(1 for s in shows
                    if G._apple_links_for(s["slug"], s.get("apple_podcasts_url")).get("apple_podcasts_url"))
        assert f"{apple} of {len(shows)} free shows are listed on Apple Podcasts" in _text(kit)
        assert "{" not in _text(kit)


class TestMessagingMatchesTheLandingPage:
    def test_the_hero_is_the_landing_promise(self, kit):
        assert B.NETWORK_TAGLINE in kit
        assert B.network_promise_visitor() in kit.replace("&#39;", "'")

    def test_the_landing_page_renders_the_same_promise(self):
        env = G._get_jinja_env()
        assert env.globals["network_promise"]() == B.network_promise_visitor()

    def test_boilerplate_leads_with_the_tagline_and_carries_the_promise(self):
        bp = B.network_boilerplate(26, ["en", "fr", "ru"])
        for text in bp.values():
            assert text.startswith(B.NETWORK_TAGLINE)
        promise_tail = ("Every story is sourced, every claim is checked against its source, "
                        "and you can read the article or hear the episode it came from.")
        assert promise_tail in bp["medium"] and promise_tail in bp["long"]


class TestShareNerra:
    def test_every_download_exists(self, kit):
        for rel in re.findall(r'href="(assets/[^"]+)" download', kit):
            assert (ROOT / rel).is_file(), rel

    def test_every_public_show_has_its_art(self):
        art = G._media_kit_marketing(G._public_shows(G._build_all_shows_list()))["show_art"]
        assert len(art) == G._public_show_count_cached()
        for a in art:
            assert a["cover"] and a["card"], a["name"]

    def test_stale_site_screenshots_are_not_offered(self, kit):
        # The committed captures predate the Oct 18 homepage and still show
        # the retired "ad-free / 0 ads" hero; they feed the video outro card,
        # never the kit.
        assert "assets/site_screens/" not in kit
        assert not re.search(r"ad-free|\b0 ads\b", _text(kit), re.I)

    def test_posts_fit_their_platforms_and_say_no_more_than_the_site(self):
        posts = {p["key"]: p for p in B.marketing_posts()}
        assert len(posts["post-short"]["text"]) <= 280
        for p in posts.values():
            if p["key"] != "post-guest":
                assert B.NETWORK_TAGLINE in p["text"]
            assert "https://nerranetwork.com" in p["text"] or p["key"] == "post-guest"
            assert "utm_" not in p["text"]

    def test_usage_rules_render(self, kit):
        for rule in B.BRAND_USAGE["yes"] + B.BRAND_USAGE["no"]:
            assert rule.replace("'", "&#39;") in kit or rule in kit
