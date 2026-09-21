"""Guards for the promo-rotation change (2026-09-21, operator-directed).

The network's two newest properties were advertised NOWHERE on air: no rotation
entry existed for `/mira.html` — which carries the sharpest and most contestable
claim the network makes — or for the `/topics/` hubs, which are the whole of its
search surface. Meanwhile the free image gallery held 3 of 12 slots, a quarter of
every spoken outro, X reply and YouTube description.

Now: gallery 2, plus a `mira` and a `topics` surface. Pool 12 -> 13.

**These lines are prompt text, not deterministic insertion.** `spoken` is
concatenated into `pod_vars["closing_block"]` (`engine/pipeline.py:628-638`) and
rendered into each show's LLM prompt under "Use this exact closing (do not
rewrite it)". Nothing verifies it afterwards, and the model has dropped a
sentence of it before (`engine/daily_edition.py:448-452`, MIT Ep171). So the copy
is written to survive paraphrase and to stay inside the claim's narrow form.
"""

from __future__ import annotations

import datetime as dt
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_DAY = dt.date(2026, 9, 22)


class TestTheTwoNewestPropertiesAreOnAir:
    def test_both_surfaces_exist_in_the_pool(self):
        from engine.network_promo import _weighted_surface_pool

        ids = {s["id"] for s in _weighted_surface_pool()}
        assert {"mira", "topics"} <= ids

    def test_both_point_at_a_file_that_exists(self):
        """The `blog.html` class of bug: a rotation that ships a 404."""
        from engine.network_promo import NETWORK_SURFACES

        for sid in ("mira", "topics"):
            surface = next(s for s in NETWORK_SURFACES if s["id"] == sid)
            assert not surface["url"].startswith("/"), "url is root-relative"
            assert (ROOT / surface["url"]).exists(), surface["url"]

    def test_topics_points_at_the_index_not_the_directory(self):
        """A bare `topics/` passes an exists() check as a directory while
        breaking the spoken and X URL shape."""
        from engine.network_promo import NETWORK_SURFACES

        topics = next(s for s in NETWORK_SURFACES if s["id"] == "topics")
        assert topics["url"] == "topics/index.html"

    def test_both_rotate_within_a_fortnight(self):
        from engine.network_promo import ENGLISH_ORDER, pick_featured_surface

        seen = set()
        for offset in range(14):
            day = _DAY + dt.timedelta(days=offset)
            for slug in ENGLISH_ORDER:
                surface = pick_featured_surface(slug, day)
                if surface:
                    seen.add(surface["id"])
        assert {"mira", "topics"} <= seen


class TestTheMiraLineStaysInsideTheClaim:
    """`engine/brand.py` owns the claim and its narrowness is load-bearing: the
    broad shape ("an AI host interviews people") is not ours to claim, and an
    on-air line is the easiest place to widen it by accident."""

    def _mira(self):
        from engine.network_promo import NETWORK_SURFACES

        return next(s for s in NETWORK_SURFACES if s["id"] == "mira")

    def test_it_names_the_term_that_is_actually_ours(self):
        spoken = self._mira()["spoken"].lower()
        assert "guest" in spoken
        assert "publish" in spoken or "published" in spoken, (
            "the claim rests on the guest holding the publish decision — a "
            "line that drops it is advertising the general shape instead"
        )

    def test_it_claims_no_superlative_on_air(self):
        """A superlative needs its basis and its correction invitation beside
        it (the /mira.html contract). A spoken outro can carry neither, so it
        does not carry the superlative either."""
        for field in ("spoken", "x_line"):
            text = self._mira()[field].lower()
            for banned in ("first", "only ", "world", "never been", "unique"):
                assert banned not in text, (
                    f"{field} widens the claim with {banned!r}; the narrow "
                    "form is the one that survives a journalist's search"
                )

    def test_it_says_mira_is_an_ai(self):
        """Every surface that mentions the host discloses the host."""
        assert "ai" in self._mira()["spoken"].lower().split()


class TestGalleryWasReducedNotRemoved:
    def test_gallery_still_outweighs_every_peer(self):
        from engine.network_promo import _weighted_surface_pool

        counts = Counter(s["id"] for s in _weighted_surface_pool())
        assert counts["gallery"] == 2
        peers = {k: v for k, v in counts.items() if k != "gallery"}
        assert all(v == 1 for v in peers.values())
        assert counts["gallery"] > max(peers.values())

    def test_gallery_still_never_airs_on_consecutive_days(self):
        """Weight must SPREAD a surface, not cluster it — the July invariant."""
        from engine.network_promo import _weighted_surface_pool

        ids = [s["id"] for s in _weighted_surface_pool()]
        positions = [i for i, sid in enumerate(ids) if sid == "gallery"]
        size = len(ids)
        gaps = [(positions[(i + 1) % len(positions)] - positions[i]) % size
                for i in range(len(positions))]
        assert all(gap > 1 for gap in gaps), (positions, gaps)


class TestSameDayShowsDoNotEchoEachOther:
    """The reason this pass is an improvement and not just churn.

    `pick_featured_surface` offsets each show by its index in ENGLISH_ORDER
    times THREE, so when the pool length shares a factor with 3 the shows
    collapse into a few phase classes. At pool length 12 the thirteen English
    shows spoke only FOUR distinct surfaces on any given day — four shows in a
    row plugging Nerra Daily. At 13 they land on thirteen distinct slots.

    This is pinned because it is invisible: nothing about a weight edit
    announces that it has re-collapsed the rotation.
    """

    def test_a_days_slate_speaks_many_different_surfaces(self):
        from engine.network_promo import ENGLISH_ORDER, pick_featured_surface

        for offset in range(7):
            day = _DAY + dt.timedelta(days=offset)
            spoken = Counter()
            for slug in ENGLISH_ORDER:
                surface = pick_featured_surface(slug, day)
                if surface:
                    spoken[surface["id"]] += 1
            assert len(spoken) >= 10, (
                f"{day}: {len(ENGLISH_ORDER)} shows collapsed to "
                f"{len(spoken)} surfaces {dict(spoken)} — the pool length "
                "has picked up a common factor with the offset stride of 3"
            )

    def test_the_offset_stride_and_pool_length_stay_coprime(self):
        from math import gcd

        from engine.network_promo import _weighted_surface_pool

        assert gcd(3, len(_weighted_surface_pool())) == 1, (
            "pool length shares a factor with the stride, so shows will "
            "cluster onto the same surface on the same day"
        )


class TestTheExclusionsAreUntouched:
    def test_offshore_north_still_speaks_no_surface(self):
        from engine.network_promo import NETWORK_SURFACES, build_network_promo

        promo = build_network_promo("offshore_north", _DAY, 6)
        for surface in NETWORK_SURFACES:
            assert surface["spoken"] not in promo

    def test_russian_shows_still_get_no_surface(self):
        from engine.network_promo import pick_featured_surface

        for slug in ("finansy_prosto", "privet_russian"):
            assert pick_featured_surface(slug, _DAY) is None

    def test_a_new_surface_needs_no_funnel_change(self):
        """`network_link` already carries the surface id in the campaign's
        variant slot, which is what makes "which plug earns clicks"
        answerable. A hand-rolled query string here would fail the
        no-new-utm-builders guard."""
        from engine.funnel import parse_campaign_id
        from engine.network_promo import build_surface_x_reply

        reply = build_surface_x_reply("tesla", _DAY, 610)
        assert reply, "tesla should get a surface reply on this date"
        assert "utm_campaign=" in reply
        campaign = reply.split("utm_campaign=", 1)[1].split("&", 1)[0]
        parsed = parse_campaign_id(campaign)
        assert parsed is not None, campaign
