"""Drift guards for Nerra Personal (accounts + personalized feeds +
support surface).

Pins: spec validation (the closed show vocabulary and token/name/city
trust boundary), the private-feed XML contract (deterministic GUIDs,
Worker-gated enclosures, itunes:block), the prune depth, the honest
local-brief contract, the Worker/engine vocabulary sync, page + prompt
registration, and the funding-tag repoint.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from engine.daily_edition import EDITIONS, Segment
from engine.personal_edition import (
    PERSONAL_FEED_MAX_EPISODES,
    PERSONAL_SHOW_SLUGS,
    PersonalSpec,
    build_personal_feed_xml,
    build_personal_links_prompt,
    fallback_personal_links,
    format_weather_line,
    parse_local_brief,
    personal_episode_title,
    prune_episode_state,
    validate_spec,
)

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "ab" * 16


def _segment(slug="spacex", name="SpaceX Daily", n=76):
    return Segment(
        slug=slug, show_name=name, episode_num=n,
        episode_title=f"Ep {n}: A hook for {name}", hook=f"A hook for {name}",
        date="2026-08-21", audio_url="", content="Body text. " * 30,
        digest_dir=Path("."), transcript_path=None, music_intro_offset=0.0)


class TestSpecValidation:
    def test_happy_path_preserves_user_order(self):
        spec = validate_spec({
            "token": TOKEN,
            "shows": ["dp_pod", "spacex", "tesla"],
            "tier": "personal_local",
            "first_name": "Sam", "city": "Vancouver",
        })
        assert spec is not None
        assert spec.shows == ["dp_pod", "spacex", "tesla"]  # THEIR order
        assert spec.tier == "personal_local"

    def test_unknown_shows_dropped_never_guessed(self):
        spec = validate_spec({
            "token": TOKEN,
            "shows": ["tesla", "not_a_show", "spacex", "tesla"],
        })
        assert spec is not None
        assert spec.shows == ["tesla", "spacex"]

    def test_too_few_shows_rejected(self):
        assert validate_spec({"token": TOKEN, "shows": ["tesla"]}) is None

    def test_bad_token_rejected(self):
        assert validate_spec({"token": "../evil", "shows": ["tesla", "spacex"]}) is None
        assert validate_spec({"token": "ZZZZ" * 8, "shows": ["tesla", "spacex"]}) is None

    def test_hostile_name_dropped_city_capped(self):
        spec = validate_spec({
            "token": TOKEN, "shows": ["tesla", "spacex"],
            "first_name": "<script>x</script>", "city": "y" * 500,
        })
        assert spec is not None
        assert spec.first_name == ""
        assert len(spec.city) == 80

    def test_vocabulary_is_the_en_lineup(self):
        assert PERSONAL_SHOW_SLUGS == EDITIONS["en"].lineup

    def test_worker_vocabulary_stays_in_sync(self):
        # The Worker validates preferences against its own copy of the
        # closed set — a drift means saved lineups silently lose shows.
        ts = (ROOT / "workers" / "gallery" / "src" / "personal.ts"
              ).read_text(encoding="utf-8")
        for slug in PERSONAL_SHOW_SLUGS:
            assert f'"{slug}"' in ts, f"{slug} missing from worker PERSONAL_SHOWS"


class TestPersonalFeed:
    def _spec(self):
        return PersonalSpec(token=TOKEN, shows=["spacex", "tesla"],
                            first_name="Sam")

    def _episodes(self, n=2):
        return [{
            "episode_num": i, "date": f"2026-08-{10 + i:02d}",
            "title": f"Edition {i}", "description": "d",
            "filename": f"Nerra_Personal_202608{10 + i:02d}.mp3",
            "duration_seconds": 3000, "bytes": 1000,
        } for i in range(1, n + 1)]

    def test_feed_contract(self):
        xml = build_personal_feed_xml(self._spec(), self._episodes())
        # Worker-gated enclosures: revocable, never a public bucket URL.
        assert "https://api.nerranetwork.com/api/feed/" + TOKEN in xml
        # Deterministic GUIDs — rebuilds never re-notify podcast apps.
        assert f"personal-{TOKEN[:8]}-ep002-20260812" in xml
        # Private: directories must never index a personal feed.
        assert "<itunes:block>yes</itunes:block>" in xml
        assert "Sam's Nerra Daily" in xml

    def test_feed_depth_capped(self):
        xml = build_personal_feed_xml(self._spec(), self._episodes(12))
        assert xml.count("<item>") == PERSONAL_FEED_MAX_EPISODES

    def test_prune_returns_filenames_to_delete(self):
        kept, dropped = prune_episode_state(self._episodes(10))
        assert len(kept) == PERSONAL_FEED_MAX_EPISODES
        assert len(dropped) == 10 - PERSONAL_FEED_MAX_EPISODES
        # Newest survive.
        assert kept[0]["episode_num"] == 10
        assert "Nerra_Personal_20260811.mp3" in dropped

    def test_title_clipped_and_unlabeled(self):
        seg = _segment()
        seg.hook = "very long words " * 30
        title = personal_episode_title(dt.date(2026, 8, 21), [seg])
        assert len(title) <= 100
        assert not title.startswith("Ep ")


class TestPersonalLinks:
    def test_prompt_carries_name_and_order(self):
        spec = PersonalSpec(token=TOKEN, shows=["dp_pod", "spacex"],
                            first_name="Sam")
        segs = [_segment("dp_pod", "The DP Pod", 41), _segment()]
        prompt = build_personal_links_prompt(ROOT, spec, segs,
                                             dt.date(2026, 8, 21))
        assert "Sam" in prompt
        assert prompt.index("The DP Pod") < prompt.index("SpaceX Daily")

    def test_fallback_greets_and_covers_gaps(self):
        spec = PersonalSpec(token=TOKEN, shows=["spacex", "tesla"],
                            first_name="Sam")
        segs = [_segment(), _segment("tesla", "Tesla Shorts Time", 579)]
        links = fallback_personal_links(spec, segs, dt.date(2026, 8, 21))
        assert "Sam" in links["intro"]
        assert len(links["handoffs"]) == 1
        assert "nerranetwork.com" in links["signoff"]

    def test_prompt_files_registered(self):
        for name in ("nerra_personal_links.txt", "nerra_personal_local.txt"):
            text = (ROOT / "shows" / "prompts" / name).read_text(encoding="utf-8")
            assert "{date_spoken}" in text
        local = (ROOT / "shows" / "prompts" / "nerra_personal_local.txt"
                 ).read_text(encoding="utf-8")
        assert "SKIP" in local  # the honest no-content escape


class TestLocalBrief:
    def test_skip_and_bounds(self):
        assert parse_local_brief("SKIP") is None
        assert parse_local_brief("too short") is None
        good = ("According to the city of Vancouver, the seawall reopens "
                "this weekend after repairs. " * 3)
        assert parse_local_brief(good)

    def test_weather_line_is_measured_data_only(self):
        line = format_weather_line("Vancouver", {
            "temperature_2m_max": [21.6], "temperature_2m_min": [13.2],
            "weather_code": [2],
        })
        assert "Vancouver" in line and "22" in line and "13" in line
        assert "partly cloudy" in line
        assert format_weather_line("Vancouver", {}) == ""


class TestSurfaces:
    def test_pages_registered(self):
        import generate_html as gh

        for fn in ("generate_join_page", "generate_support_page",
                   "generate_account_page"):
            assert hasattr(gh, fn), fn
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert '"join.html", "support.html"' in src  # sitemap

    def test_templates_exist(self):
        for name in ("join_page.html.j2", "account_page.html.j2",
                     "support_page.html.j2"):
            assert (ROOT / "templates" / name).exists(), name

    def test_funding_tag_points_at_support(self):
        # Aug 2026: podcast:funding is the donations surface now — every
        # 2.0 app renders it as the show's Support button.
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'funding_url=f"{config.publishing.base_url}/support.html"' in src
        assert "/#newsletter\",\n            funding_label" not in src

    def test_footer_newsletter_posts_to_account_worker(self):
        # Newsletter signups create accounts: the footer form must go
        # through /api/subscribe (list "member"), not Buttondown's embed.
        base = (ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8")
        assert "embed-subscribe" not in base
        assert "api.nerranetwork.com/api/subscribe" in base
        assert "list:'member'" in base

    def test_missing_admin_token_fails_loudly(self):
        """A host that cannot authenticate must not look idle.

        load_specs used to return [] when PERSONAL_ADMIN_TOKEN was unset.
        That flows into main()'s "no active subscribers — nothing to do"
        and exits 0, so a misconfigured batch host produces a green run
        with zero output — indistinguishable from a healthy day with no
        subscribers, every day, forever. The batch repo's first three
        scheduled runs (2026-08-24 through 08-26) were green exactly that
        way, logging ERROR and succeeding anyway.
        """
        src = (ROOT / "scripts" / "build_personal_feeds.py"
               ).read_text(encoding="utf-8")
        head, _, tail = src.partition('token = os.environ.get("PERSONAL_ADMIN_TOKEN"')
        assert tail, "the --fetch token lookup vanished"
        guard = tail[:600]
        assert "raise SystemExit" in guard, (
            "a missing PERSONAL_ADMIN_TOKEN must abort the run, not "
            "return an empty spec list that reads as 'no subscribers'"
        )
        code = "\n".join(
            line for line in guard.split("raise SystemExit")[0].splitlines()
            if not line.lstrip().startswith("#")
        )
        assert "return []" not in code, "the silent empty-list path is back"

    def test_batch_builder_importable_and_piiless_logging(self):
        src = (ROOT / "scripts" / "build_personal_feeds.py"
               ).read_text(encoding="utf-8")
        # Tokens are logged truncated; names/cities never logged.
        assert "token[:8]" in src
        assert not re.search(r'logger\.\w+\([^)]*spec\.first_name', src)
        assert not re.search(r'logger\.\w+\([^)]*spec\.city', src)


class TestLandingAndConsoleSurfaces:
    """Aug 27 2026 website pass drift guards."""

    def test_join_template_shows_the_pickable_lineup(self):
        src = _read("templates/join_page.html.j2")
        assert "personal_shows" in src, (
            "the landing page must SHOW the closed show vocabulary it sells")
        assert "How Personal works" in src

    def test_join_generator_passes_the_vocabulary(self):
        src = _read("generate_html.py")
        assert "PERSONAL_SHOW_SLUGS" in src

    def test_homepage_carries_personal_promo(self):
        src = _read("templates/network_page.html.j2")
        assert "personal-promo" in src

    def test_account_console_is_state_aware(self):
        src = _read("templates/account_page.html.j2")
        for marker in ("nn-feed-cancelled", "nn-starter-note",
                       "nn-city-nudge", "nn-tier-badge"):
            assert marker in src, marker

    def test_worker_starter_lineup_within_vocabulary(self):
        # A paying member with <2 shows now gets DEFAULT_LINEUP instead of
        # silent exclusion; the starter must stay inside the closed set.
        import re as _re
        src = _read("workers/gallery/src/personal.ts")
        assert "DEFAULT_LINEUP" in src
        block = src.split("DEFAULT_LINEUP = [", 1)[1].split("]", 1)[0]
        slugs = _re.findall(r'"([a-z_]+)"', block)
        from engine.personal_edition import PERSONAL_SHOW_SLUGS
        assert len(slugs) >= 2
        for s in slugs:
            assert s in PERSONAL_SHOW_SLUGS, s


def _read(rel):
    from pathlib import Path
    return (Path(__file__).resolve().parent.parent / rel).read_text(
        encoding="utf-8")
