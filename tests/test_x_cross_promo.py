"""Drift guards for the X cross-promo reply tweet (June 2026 growth pass).

The daily teaser gains a flag-gated follow-up reply ("Follow @handle" +
one sibling-show plug from the network_promo rotation). Pinned here:

* every X-enabled show × many dates stays within X's 280-char budget
  (URLs counted as t.co's 23 chars);
* Russian shows produce an empty reply (rotation is English-only and
  they have no handle);
* ``publishing.x_cross_promo: false`` keeps the pipeline teaser-only;
* ``post_to_x`` passes ``in_reply_to_tweet_id`` through to tweepy.
"""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import run_show  # noqa: E402
from engine.config import load_config  # noqa: E402

_X_ENABLED = [
    "tesla", "omni_view", "fascinating_frontiers", "planetterrian",
    "models_agents", "modern_investing", "unintended_consequences",
]
_RUSSIAN = ["finansy_prosto", "privet_russian"]


def _effective_x_len(text: str) -> int:
    """X counts every URL as 23 chars (t.co)."""
    return len(re.sub(r"https?://\S+", "x" * 23, text))


class TestReplyText:
    @pytest.mark.parametrize("slug", _X_ENABLED)
    @pytest.mark.parametrize("day", range(1, 15))
    def test_within_280_chars_across_dates(self, slug, day):
        cfg = load_config(f"shows/{slug}.yaml")
        text = run_show._build_cross_promo_reply(
            cfg, datetime.date(2026, 6, day))
        assert _effective_x_len(text) <= 280, (
            f"{slug} {day}: reply too long ({_effective_x_len(text)})"
        )

    @pytest.mark.parametrize("slug", _X_ENABLED)
    def test_plug_links_a_sibling_with_utm(self, slug):
        cfg = load_config(f"shows/{slug}.yaml")
        text = run_show._build_cross_promo_reply(
            cfg, datetime.date(2026, 6, 10))
        assert "More from the Nerra Network:" in text
        assert "utm_campaign=cross_promo" in text
        assert cfg.name not in text.split("More from the Nerra Network:")[1], (
            "the plug must feature a SIBLING show, not the show itself"
        )

    def test_follow_line_present_when_handle_set(self):
        cfg = load_config("shows/tesla.yaml")
        text = run_show._build_cross_promo_reply(
            cfg, datetime.date(2026, 6, 10))
        assert text.startswith("Follow @teslashortstime")

    def test_follow_line_omitted_when_no_handle(self):
        cfg = load_config("shows/omni_view.yaml")
        text = run_show._build_cross_promo_reply(
            cfg, datetime.date(2026, 6, 10))
        assert "Follow @" not in text
        assert text.startswith("More from the Nerra Network:")

    @pytest.mark.parametrize("slug", _RUSSIAN)
    def test_russian_shows_produce_empty_reply(self, slug):
        cfg = load_config(f"shows/{slug}.yaml")
        assert run_show._build_cross_promo_reply(
            cfg, datetime.date(2026, 6, 10)) == ""

    def test_rotation_varies_across_days(self):
        cfg = load_config("shows/tesla.yaml")
        texts = {
            run_show._build_cross_promo_reply(cfg, datetime.date(2026, 6, d))
            for d in range(1, 9)
        }
        assert len(texts) >= 4, "daily rotation should vary the featured show"


class TestConfigGating:
    def test_network_default_enables_cross_promo(self):
        cfg = load_config("shows/tesla.yaml")
        assert cfg.publishing.x_cross_promo is True

    def test_dataclass_default_is_off(self):
        """Callers that bypass YAML (legacy scripts) must stay teaser-only."""
        from engine.config import PublishingConfig
        assert PublishingConfig().x_cross_promo is False
        assert PublishingConfig().x_handle == ""

    def test_pipeline_gates_on_flag(self):
        """The call site must check publishing.x_cross_promo before posting."""
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        wiring = src.split("_build_cross_promo_reply(config, today)")[0]
        assert 'x_cross_promo' in wiring.rsplit("def ", 1)[-1] or \
            'getattr(config.publishing, "x_cross_promo"' in wiring, (
                "cross-promo reply must be gated on publishing.x_cross_promo"
            )


class TestPostToXReplySupport:
    def test_in_reply_to_passed_to_tweepy(self):
        from engine.publisher import post_to_x

        fake_client = MagicMock()
        fake_client.create_tweet.return_value = MagicMock(
            data={"id": "12345"})
        fake_tweepy = MagicMock()
        fake_tweepy.Client.return_value = fake_client

        with patch.dict(sys.modules, {"tweepy": fake_tweepy}):
            url = post_to_x(
                "reply text",
                consumer_key="k", consumer_secret="s",
                access_token="t", access_token_secret="ts",
                in_reply_to_tweet_id="999",
            )

        assert url == "https://x.com/i/status/12345"
        fake_client.create_tweet.assert_called_once_with(
            text="reply text", in_reply_to_tweet_id="999",
        )

    def test_no_reply_id_keeps_legacy_call_shape(self):
        from engine.publisher import post_to_x

        fake_client = MagicMock()
        fake_client.create_tweet.return_value = MagicMock(
            data={"id": "12345"})
        fake_tweepy = MagicMock()
        fake_tweepy.Client.return_value = fake_client

        with patch.dict(sys.modules, {"tweepy": fake_tweepy}):
            post_to_x(
                "teaser",
                consumer_key="k", consumer_secret="s",
                access_token="t", access_token_secret="ts",
            )

        fake_client.create_tweet.assert_called_once_with(text="teaser")
