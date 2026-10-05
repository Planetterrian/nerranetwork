"""Oct 1 2026 — trust and retention surfaces (the operator brief: shows people
keep listening to, subscribe to and review on the platforms they use).

* On-air platform ask (engine/intros.py) — AUDIO, A/B-listen per landmine #17.
* The promo rotation's Age of AI line no longer calls the show a phone call.
* Every newsletter carries a rating line; the AI-host branch no longer
  raises on its share text.
* Cadence words come from the registry schedule (engine/cadence.py).
* YouTube descriptions carry the channel subscribe link, a Sources line and
  a disclosure that names the AI host when the host is an AI.
* Show notes carry a network-default rating ask from each show's next
  episode on; thirteen launch-cohort shows have their newsletter enabled.
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import intros  # noqa: E402

COHORT = ["ai_chips", "mag7", "peptides", "longevity", "vancouver", "collingwood",
          "prediction_markets", "omni_view_world", "omni_view_north_america",
          "omni_view_europe", "omni_view_asia_pacific", "omni_view_africa_mideast",
          "omni_view_latam"]


class TestPlatformAsk:
    def test_a_silent_closing_gains_one_ask_on_alternate_days(self):
        seen = set()
        for day in range(2, 10):
            c = intros.build_closing_block("ai_chips", episode_num=10, today_str="x",
                                           date=datetime.date(2026, 10, day))
            seen.add(intros.closing_has_ask(c))
        assert seen == {True, False}

    def test_both_shapes_air_and_never_the_same_twice_running(self):
        shapes = []
        for day in range(1, 30):
            ask = intros.platform_ask_for("ai_chips", datetime.date(2026, 10, day))
            if ask:
                shapes.append(ask)
        assert len(set(shapes)) == 2
        assert all(a != b for a, b in zip(shapes, shapes[1:]))

    def test_a_closing_that_already_asks_is_untouched(self):
        for day in range(1, 8):
            c = intros.build_closing_block("spacex", episode_num=117, today_str="x",
                                           date=datetime.date(2026, 10, day))
            assert c.count("Apple Podcasts") <= 1 and "podcast app" not in c

    def test_the_russian_speaking_show_hears_russian(self):
        asks = {intros.platform_ask_for("finansy_prosto", datetime.date(2026, 10, d), is_ru=True)
                for d in range(1, 8)} - {""}
        assert asks and all("Apple Podcasts" in a or "подпишитесь" in a for a in asks)
        assert not any("follow it in your podcast app" in a for a in asks)

    def test_the_ask_names_no_specimen_a_model_could_copy_into_the_body(self):
        # Shape only: the sentences are furniture in the fixed closing, never
        # a quotable line inside the prompt body.
        for ask in intros._PLATFORM_ASKS:
            assert ask.endswith(".") and "for example" not in ask.lower()


class TestPromoRotationTruth:
    def test_no_surface_calls_the_age_of_ai_a_phone_call(self):
        from engine.network_promo import NETWORK_SURFACES
        for s in NETWORK_SURFACES:
            text = " ".join(str(s.get(k, "")) for k in ("spoken", "x_line")).lower()
            assert "phone" not in text, s.get("id")

    def test_the_age_of_ai_line_carries_the_narrow_basis(self):
        from engine.network_promo import NETWORK_SURFACES
        line = next(s["spoken"] for s in NETWORK_SURFACES if s["id"] == "age_of_ai")
        assert "guest decides" in line and "AI host" in line


class TestNewsletterRetention:
    def _row(self, show, slug):
        from engine.newsletter_template import _build_reply_share_html
        return _build_reply_share_html(show, slug=slug, episode_num=5, archive_url="")

    def test_a_rating_line_links_the_shows_own_pages(self):
        html = self._row({"name": "Tesla Shorts Time", "show_page": "https://nerranetwork.com/tesla.html",
                          "apple_podcasts_url": "https://podcasts.apple.com/x/id1",
                          "spotify_url": "https://open.spotify.com/show/a", "host_kind": "human"}, "tesla")
        assert "Rate the show:" in html and "podcasts.apple.com/x/id1" in html and "open.spotify.com/show/a" in html

    def test_no_directory_page_means_no_line_not_a_search_link(self):
        html = self._row({"name": "AI Chips", "show_page": "https://nerranetwork.com/ai-chips.html",
                          "apple_podcasts_url": None, "spotify_url": None, "host_kind": "human"}, "ai_chips")
        assert "Rate the show" not in html and "search" not in html.lower()

    def test_the_ai_host_branch_renders(self):
        html = self._row({"name": "Vancouver Daily News", "show_page": "https://nerranetwork.com/vancouver.html",
                          "host_kind": "ai"}, "vancouver")
        assert "Share:" in html and "run the Nerra Network" in html

    @pytest.mark.parametrize("slug", COHORT)
    def test_the_launch_cohort_newsletter_is_enabled(self, slug):
        from engine.config import load_config
        assert load_config(ROOT / "shows" / f"{slug}.yaml").newsletter.enabled is True


class TestCadenceWords:
    def test_the_adjective_follows_the_registry_schedule(self):
        from engine.cadence import cadence_adjective, episodes_phrase
        assert cadence_adjective("Daily") == "daily"
        assert cadence_adjective("Weekly (Thursday)") == "weekly"
        assert cadence_adjective("Monday") == "weekly"
        assert cadence_adjective("When an interview is ready") == "new"
        assert episodes_phrase("dp_pod") == "weekly episodes"
        assert episodes_phrase("tesla") == "daily episodes"

    def test_run_show_no_longer_promises_daily_on_every_show(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "Subscribe for daily" not in src and "for daily episodes" not in src


class TestYouTubeDescriptionTrust:
    def test_the_channel_subscribe_link_per_channel(self):
        from engine.video_metadata import channel_subscribe_url
        assert channel_subscribe_url("en").endswith("@NerraNetwork?sub_confirmation=1")
        assert "@NerraRU" in channel_subscribe_url("ru") and "@NerraFR" in channel_subscribe_url("fr")

    def test_an_ai_host_show_discloses_the_ai_host_not_a_curator(self):
        from engine.config import load_config
        from engine.video_metadata import video_disclosure_for
        assert video_disclosure_for(load_config(ROOT / "shows" / "vancouver.yaml")).startswith(
            "AI Disclosure: Mira is an AI host")
        assert "curated by Patrick" in video_disclosure_for(load_config(ROOT / "shows" / "tesla.yaml"))

    def test_the_long_form_description_carries_subscribe_and_sources(self):
        from engine.config import load_config
        from engine.video_metadata import build_long_form_metadata
        cfg = load_config(ROOT / "shows" / "tesla.yaml")
        digest = ("# Tesla Shorts Time\n\n### Top News\n\n1. **A headline here**\n"
                  "Body. Source: [electrek.co](https://electrek.co/2026/10/01/x)\n")
        meta = build_long_form_metadata(cfg, episode_num=623, today_str="October 2, 2026",
                                        hook="Tesla did a thing today.", digest_text=digest,
                                        audio_url="https://audio.nerranetwork.com/x.mp3")
        desc = meta["description"]
        assert "sub_confirmation=1" in desc
        assert "electrek.co" in desc.split("AI Disclosure")[0]


class TestShowNotesAsk:
    def test_the_default_ask_starts_at_the_next_episode_and_spares_older_posts(self):
        from engine.episode_ask import DEFAULT_ASK_FROM_EPISODE, episode_ask_markdown
        assert episode_ask_markdown("tesla", DEFAULT_ASK_FROM_EPISODE["tesla"] - 1) == ""
        assert "Apple Podcasts" in episode_ask_markdown("tesla", DEFAULT_ASK_FROM_EPISODE["tesla"])
        assert "Spotify" in episode_ask_markdown("finansy_prosto", 86) and "подписка" in episode_ask_markdown("finansy_prosto", 86)
        assert episode_ask_markdown("age_of_ai", 99) == ""

    def test_spacex_keeps_its_own_ask(self):
        from engine.episode_ask import episode_ask_markdown
        assert episode_ask_markdown("spacex", 117).startswith("Enjoyed this episode?")


class TestTopicHubsForTheCohort:
    def test_two_new_hubs_and_their_registry_tags(self):
        import yaml
        from engine.topic_hubs import TOPIC_HUBS
        ids = {h["id"] for h in TOPIC_HUBS}
        assert {"prediction-markets", "ai-infrastructure"} <= ids
        meta = yaml.safe_load((ROOT / "shows" / "network_meta.yaml").read_text(encoding="utf-8"))
        shows = meta.get("shows", meta)
        assert "prediction-markets" in shows["prediction_markets"]["picker_tags"]["topics"]
        assert "ai-infrastructure" in shows["ai_chips"]["picker_tags"]["topics"]
