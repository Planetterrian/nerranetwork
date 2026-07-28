"""Drift guards for publisher attribution on source cards (July 28 2026, P0-2).

Google-News-fed shows cited every aggregated story as
``Source: [Google News](https://news.google.com/rss/articles/CBMi...)``.
The blog rendered that as a card reading "news.google.com" with Google's
favicon — so the reader never learned who did the reporting, and the
card implied Google was the publisher.

The plan proposed resolving the redirect to the publisher URL. That was
tried and does not work: Google serves a JS interstitial, and
``resolve_google_news_url`` (which has been wired into the fetcher for
months) fails on 100% of current-format URLs. Both fixes here take the
publisher from data we already hold instead:

  * forward — ``relabel_aggregator_links`` rewrites the link label from
    the article record's ``source_name``, which the fetcher already
    reads from the feed's ``<source>`` element.
  * retroactively — ``_publisher_labels_by_url`` recovers the outlet
    from the headline line of already-committed digests.

Every string below is taken from a digest shipped this week.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.blog import (  # noqa: E402
    _is_aggregator_url,
    _publisher_from_headline,
    _publisher_labels_by_url,
)
from engine.url_utils import relabel_aggregator_links  # noqa: E402

GOOGLE = "https://news.google.com/rss/articles/CBMiABC?oc=5"


class TestHeadlineFormats:
    """All four item shapes in live use across the network."""

    @pytest.mark.parametrize(
        "line,expected",
        [
            # A — dash after the bold (SpaceX, Fascinating Frontiers).
            (
                "1. **FAA weighs new SpaceX Starship flight path** — San Antonio Express-News",
                "San Antonio Express-News",
            ),
            # A' — dash inside the bold (SpaceX Ep045).
            (
                "1. **SpaceX Targets First Starship Upper Stage Tower Catch for Flight 14 — satnews.com**",
                "satnews.com",
            ),
            # A' — outlet name contains its own hyphen; must not be truncated.
            (
                "2. **Starship Flight 13 Heat Shield Test: What SpaceX Learned — BASENOR - Tesla Accessories**",
                "BASENOR - Tesla Accessories",
            ),
            # B — publisher inside the bold, after the final colon
            #     (Env Intel, DP Pod, Models & Agents).
            (
                "**KEAN Requests Kincardine Council Implement More Steadfast Procedures: 97.9 the Bruce**",
                "97.9 the Bruce",
            ),
            (
                "2. **Thailand Cuts Botulism Drug Cost by 90% in Major Breakthrough: Nation Thailand**",
                "Nation Thailand",
            ),
            # C — trailing date line, publisher last (Tesla).
            (
                "2. **Tesla sues Cybertruck supplier over parts standoff:** July 28, 2026, Electrek",
                "Electrek",
            ),
            (
                "4. **Tesla signs long-term solar PPA with Zelestra in Texas:** July 28, 2026, bastillepost.com",
                "bastillepost.com",
            ),
        ],
    )
    def test_publisher_recovered(self, line, expected):
        assert _publisher_from_headline(line) == expected

    @pytest.mark.parametrize(
        "line",
        [
            # Genuinely unattributed headline (SpaceX Ep046) — must stay
            # empty rather than invent an outlet.
            "1. **Starship Flight 13 completed a flawless ascent and Ship water landing**",
            "**Chat with any book like it's sitting right next to you**",
            # Body prose, not a headline.
            "The FAA is evaluating an updated Starship trajectory.",
            "",
            # A dash inside a short bold phrase is not an attribution.
            "**Q3 - Q4**",
        ],
    )
    def test_no_attribution_returns_empty(self, line):
        assert _publisher_from_headline(line) == ""


class TestLabelScoping:
    def test_publisher_applies_to_its_own_item(self):
        md = (
            "1. **FAA weighs new Starship flight path** — San Antonio Express-News\n"
            f"   Body text. Source: [Google News]({GOOGLE})\n"
        )
        assert _publisher_labels_by_url(md)[GOOGLE] == "San Antonio Express-News"

    def test_publisher_does_not_leak_across_a_heading(self):
        """SpaceX Ep047 labelled its Counterpoint source "Tech Times".

        A wrong publisher is worse than an honest "news.google.com", so
        a structural break must clear the current attribution.
        """
        other = "https://news.google.com/rss/articles/CBMiXYZ?oc=5"
        md = (
            "8. **Orbital Data Centers Need Inspection Too** — Tech Times\n"
            f"   Body. Source: [Google News]({GOOGLE})\n"
            "\n"
            "## The Counterpoint\n"
            f"Scientists have warned. Source: [Google News]({other})\n"
        )
        labels = _publisher_labels_by_url(md)
        assert labels[GOOGLE] == "Tech Times"
        assert other not in labels

    def test_horizontal_rule_also_clears_attribution(self):
        other = "https://news.google.com/rss/articles/CBMiXYZ?oc=5"
        md = (
            "1. **Something newsworthy happened today** — Reuters\n"
            f"   Body. Source: [Google News]({GOOGLE})\n"
            "---\n"
            f"Unattributed follow-up. Source: [Google News]({other})\n"
        )
        labels = _publisher_labels_by_url(md)
        assert labels[GOOGLE] == "Reuters"
        assert other not in labels


class TestAggregatorDetection:
    @pytest.mark.parametrize(
        "url",
        [
            "https://news.google.com/rss/articles/CBMiABC?oc=5",
            "https://www.news.google.com/rss/articles/CBMiABC",
            "https://news.google.ca/rss/articles/CBMiABC",
        ],
    )
    def test_aggregator_urls_flagged(self, url):
        assert _is_aggregator_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.nasaspaceflight.com/2026/07/launch-preview/",
            "https://www.theverge.com/ai/971750/perplexity",
            "https://x.com/emollick/status/2081261849543070181",
            # Not the news aggregator — a normal Google property.
            "https://blog.google/technology/ai/",
        ],
    )
    def test_publisher_urls_not_flagged(self, url):
        assert _is_aggregator_url(url) is False


class TestForwardRelabelling:
    """The fetcher already knows the outlet; this carries it into the digest."""

    def test_google_news_label_replaced_with_outlet(self):
        md = f"Body text. Source: [Google News]({GOOGLE})"
        articles = [{"url": GOOGLE, "source_name": "San Antonio Express-News"}]
        out, count = relabel_aggregator_links(md, articles)
        assert count == 1
        assert f"[San Antonio Express-News]({GOOGLE})" in out
        assert "[Google News]" not in out

    def test_href_is_preserved(self):
        """The Google URL is the only link we have that reaches the article."""
        md = f"Source: [Google News]({GOOGLE})"
        out, _ = relabel_aggregator_links(
            md, [{"url": GOOGLE, "source_name": "Reuters"}]
        )
        assert GOOGLE in out

    def test_specific_label_is_never_overwritten(self):
        md = f"Source: [Reuters exclusive]({GOOGLE})"
        out, count = relabel_aggregator_links(
            md, [{"url": GOOGLE, "source_name": "Somewhere Else"}]
        )
        assert count == 0
        assert out == md

    def test_unmatched_url_left_alone(self):
        md = f"Source: [Google News]({GOOGLE})"
        out, count = relabel_aggregator_links(
            md, [{"url": "https://news.google.com/rss/articles/OTHER", "source_name": "X"}]
        )
        assert count == 0
        assert out == md

    def test_direct_publisher_links_untouched(self):
        md = "Source: [nasaspaceflight.com](https://www.nasaspaceflight.com/2026/07/x/)"
        out, count = relabel_aggregator_links(
            md, [{"url": "https://www.nasaspaceflight.com/2026/07/x/",
                  "source_name": "NASASpaceflight"}]
        )
        assert count == 0
        assert out == md

    @pytest.mark.parametrize("articles", [[], None])
    def test_no_articles_is_a_noop(self, articles):
        md = f"Source: [Google News]({GOOGLE})"
        out, count = relabel_aggregator_links(md, articles)
        assert (out, count) == (md, 0)

    def test_article_without_publisher_is_skipped(self):
        md = f"Source: [Google News]({GOOGLE})"
        out, count = relabel_aggregator_links(md, [{"url": GOOGLE, "source_name": ""}])
        assert (out, count) == (md, 0)

    def test_idempotent(self):
        md = f"Source: [Google News]({GOOGLE})"
        articles = [{"url": GOOGLE, "source_name": "Reuters"}]
        once, _ = relabel_aggregator_links(md, articles)
        twice, count = relabel_aggregator_links(once, articles)
        assert twice == once
        assert count == 0


class TestPipelineWiring:
    def test_run_show_relabels_before_writing_the_digest(self):
        source = (
            Path(__file__).resolve().parent.parent / "run_show.py"
        ).read_text(encoding="utf-8")
        assert "relabel_aggregator_links(" in source
        # Must run before the digest is persisted, or the published file
        # keeps the Google label.
        assert source.index("relabel_aggregator_links(") < source.index(
            "digest_md.write_text("
        )


class TestBackCatalogueRecovery:
    """Real committed digests must yield real publishers."""

    def test_recent_digests_name_publishers(self):
        digests = Path(__file__).resolve().parent.parent / "digests"
        recovered = aggregated = 0
        for show in sorted(digests.glob("*/")):
            for md_path in sorted(show.glob("*_Ep*.md"))[-3:]:
                md = md_path.read_text(encoding="utf-8", errors="ignore")
                labels = _publisher_labels_by_url(md)
                for url in labels:
                    if _is_aggregator_url(url):
                        aggregated += 1
                        if labels[url]:
                            recovered += 1
        # Guards the extractor against silently regressing to zero. The
        # remaining gap is digests whose headlines carry no outlet at
        # all; those are closed going forward by relabel_aggregator_links,
        # not retroactively.
        assert aggregated > 0, "no aggregated sources found — fixture drift"
        assert recovered == aggregated
