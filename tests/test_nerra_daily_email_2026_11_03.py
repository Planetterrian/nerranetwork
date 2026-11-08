"""Nov 3 2026 — the Nerra Daily email reads as a briefing.

A sourced deck under every card (``engine.landing_test.story_deck``), the
first phone screen carries news (compact masthead, the edition's card after
the reader's shows, no paragraph about the layout), "Also on Nerra today" as
a sectioned run of short headlines, every headline whole (interview hooks and
the Sunday most-played rows), and a size guard that knows Buttondown's
wrapper. Nothing here calls a model.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from engine import landing_test as lt  # noqa: E402
from engine import nerra_daily_email as nde  # noqa: E402
from engine import newsletter_template as nt  # noqa: E402
from engine.titles import ELLIPSIS, EMAIL_ALSO_LINE_MAX  # noqa: E402

DAY = dt.date(2026, 11, 2)
NOW = dt.datetime(2026, 11, 2, 11, 40, tzinfo=dt.timezone.utc)

HOOK = ("Tesla registrations in Sweden rose 248 percent in October while Norway "
        "climbed 131 percent even as Chinese rivals expanded.")
DECK_SENTENCE_2 = ("Sweden jumped 248 percent from a year earlier, Norway climbed 131 "
                   "percent, and Denmark increased 34 percent.")
DIGEST = f"""# Tesla Shorts Time
**REAL-TIME TSLA price:** $399.81 ▼ $3.49 (0.9%)

> **{HOOK}**

### Top 12 News Items

1. **Tesla Norway Sales Hit 130.7% YoY Growth And Best October Ever** — TSLAming (X)
   Tesla posted 130.7 percent year-over-year sales growth in Norway for October and recorded its best October ever. Source: [x.com](https://x.com/tslaming/status/1)

2. **Tesla's October Registrations Surge in Northern Europe, Sweden Jumps 248%** — BigGo Finance
   Tesla registrations rose across Northern Europe in October. {DECK_SENTENCE_2} The rebound came from a low prior-year base and higher fuel prices. Source: [finance.biggo.com](https://finance.biggo.com/news/1) · [reuters.com](https://www.reuters.com/x)

3. **Texas Family Finds Missing Cat Inside Their Own Tesla** — KHOU
   A Texas family in Houston found their cat inside the Tesla after a forty-minute search. Source: [khou.com](https://khou.com/x)
"""


def _story(slug, name, ep, day, hook, headlines=(), hub="", deck=""):
    return {
        "slug": slug, "show_name": name, "hook": hook, "episode_num": ep,
        "date_raw": day.isoformat(), "post_url": f"blog/{slug}/ep{ep:03d}.html",
        "headlines": list(headlines), "duration_s": 600, "guest": "",
        "hub_heading": hub, "deck": deck,
    }


SHOWS = (
    ("spacex", "SpaceX Daily", "Space"),
    ("tesla", "Tesla Shorts Time", "Tesla"),
    ("mag7", "MAG 7 Daily", "Artificial intelligence"),
    ("models_agents", "Models & Agents", "Artificial intelligence"),
    ("vancouver", "Vancouver Daily News", "Local news"),
    ("omni_view", "Omni View", "World news"),
    ("omni_view_world", "Omni View Top World News", "World news"),
)


def _front(day=DAY):
    shows = {}
    for slug, name, hub in SHOWS:
        shows[slug] = {"name": name, "brand_color": "#336699", "show_page": f"{slug}.html",
                       "members_only": False, "schedule": "Daily",
                       "stories": [_story(slug, name, 100, day,
                                          f"{name} lead story that runs long enough to need a clip "
                                          f"at one hundred and ten characters when the line is printed in the email, says the digest",
                                          [f"{name} second item", f"{name} third item", f"{name} fourth"],
                                          hub=hub, deck=f"{name} deck sentence one. Deck sentence two.")]}
    shows["nerra_daily"] = {"name": "Nerra Daily", "members_only": False,
                            "stories": [dict(_story("nerra_daily", "Nerra Daily", 74, day,
                                                    "Monday edition — the morning in one listen"),
                                             duration_s=9360)]}
    return {"shows": shows}


@pytest.fixture
def composed(monkeypatch):
    monkeypatch.setattr(nde, "already_sent", lambda day, root=None, **k: {})
    monkeypatch.setattr(nde, "video_links", lambda *a: {})
    monkeypatch.setattr(nde, "week_records", lambda slug, day, root=None: [])
    return nde.compose(DAY, now=NOW, front=_front(), trial_days=7)


def _also_section(copy: str) -> str:
    return copy.split("Also on Nerra today", 1)[1].split("Hear this as your own", 1)[0]


# ---------------------------------------------------------------------------
# The deck
# ---------------------------------------------------------------------------


class TestEveryCardCarriesADeck:
    def test_the_deck_is_the_hook_storys_own_sentences(self):
        deck = lt.story_deck(DIGEST, HOOK)
        assert deck == "Tesla registrations rose across Northern Europe in October. " + DECK_SENTENCE_2
        for token in ("###", ">", "**", "Source:", "["):
            assert token not in deck

    def test_a_flagged_sentence_is_never_printed(self):
        flagged = {lt._norm_sentence(DECK_SENTENCE_2)}
        deck = lt.story_deck(DIGEST, HOOK, flagged=flagged)
        assert DECK_SENTENCE_2 not in deck
        assert deck.startswith("Tesla registrations rose across Northern Europe in October.")
        # A clause of the sentence (the gate records the claim's span) flags it too.
        clause = lt._norm_sentence("Sweden jumped 248 percent from a year earlier, Norway climbed 131 percent")
        assert DECK_SENTENCE_2 not in lt.story_deck(DIGEST, HOOK, flagged={clause})

    def test_the_sidecar_beside_the_digest_supplies_the_flags(self, tmp_path):
        side = tmp_path / "Tesla_Shorts_Time_Pod_Ep653_20261102_claims.json"
        side.write_text(json.dumps({"gate": {"policy_version": 2, "passed": True,
                                             "flagged_sentences": [DECK_SENTENCE_2]},
                                    "claims": []}), encoding="utf-8")
        record = {"episode_num": "653", "content": DIGEST, "date": "2026-11-02",
                  "audio_url": "https://audio.nerranetwork.com/tesla/Tesla_Shorts_Time_Pod_Ep653_20261102.mp3"}
        assert lt._norm_sentence(DECK_SENTENCE_2) in lt.flagged_sentences_for(tmp_path, record)
        row = lt.story_json({"slug": "tesla", "hook": HOOK}, record=record, show_dir=tmp_path)
        assert DECK_SENTENCE_2 not in row["deck"] and row["deck"]
        assert "deck" not in lt._STORY_JSON_KEYS  # computed, never copied
        # No sidecar: nothing flagged, the deck is whole.
        assert lt.flagged_sentences_for(tmp_path / "elsewhere", record) == frozenset()
        assert DECK_SENTENCE_2 in lt.story_json({"slug": "tesla", "hook": HOOK}, record=record)["deck"]

    def test_the_hook_story_headline_is_absent_from_the_headlines(self):
        heads = lt.more_headlines(DIGEST, HOOK)
        assert not any("Sweden Jumps 248%" in h for h in heads)
        assert any("Norway" in h for h in heads) and any("Cat" in h for h in heads)

    def test_a_record_with_no_matching_item_gets_an_empty_deck(self):
        digest = ("> **The US Treasury's record auction signals yield pressure on rate-sensitive holdings.**\n\n"
                  "### Tools & Techniques\n\n"
                  "1. **Unusual Whales Options Flow** — Tools\n   This tool tracks options activity "
                  "across the market every day. Source: [x.com](https://x.com/a)\n")
        assert lt.story_deck(digest, "The US Treasury's record auction signals yield pressure on rate-sensitive holdings.") == ""

    def test_a_narrative_episode_opens_on_its_cold_open(self):
        digest = ("> **Wolves entering 29 Wisconsin counties cut deer-vehicle collisions by about 24 percent.**\n"
                  "---\n### Segment 1 — The Cold Open\n"
                  "In the winter of 2009, a radio-collared wolf crossed a county road in northern Wisconsin. "
                  "Within two years, local deer began shifting their movement patterns away from that stretch. "
                  "The change registered in the county sheriff's reduced stack of collision reports.\n\n"
                  "### Sources\n- [Raynor et al.](https://example.org/paper) — the study\n")
        deck = lt.story_deck(digest, "Wolves entering 29 Wisconsin counties cut deer-vehicle collisions by about 24 percent.")
        assert deck.startswith("In the winter of 2009, a radio-collared wolf")
        assert "Segment" not in deck and "Raynor" not in deck

    def test_no_sentence_is_ever_cut(self):
        long_sentence = "Tesla " + "registrations rose across Northern Europe in October and in November " * 6 + "again."
        digest = f"> **{HOOK}**\n\n### Top News\n\n1. **Sweden Jumps 248% As Tesla Registrations Surge** — X\n   {long_sentence} Short tail.\n"
        deck = lt.story_deck(digest, HOOK)
        # The first sentence overran the budget past its grace: nothing is printed mid-sentence.
        assert deck in ("", long_sentence) and "…" not in deck

    def test_replay_over_the_committed_nov_2_records(self):
        """The records of the Nov 2 send (every one older than a day) give
        at least 15 decks; a data guard reads committed data and tolerates
        today's by judging only the marker's episodes."""
        from generate_html import NETWORK_SHOWS
        marker = json.loads((ROOT / "digests" / "nerra_daily" / "email" / "2026-11-02.json").read_text())
        decks = []
        for slug, eps in marker["included"].items():
            cfg = NETWORK_SHOWS.get(slug) or {}
            if slug == "nerra_daily" or not cfg.get("json_path"):
                continue
            rec = lt.record_by_number(ROOT / cfg["json_path"], max(eps))
            if not rec:
                continue
            content = rec.get("content") or rec.get("summary") or ""
            hook = lt.hook_from_markdown(content) or (rec.get("hook") or "")
            deck = lt.story_deck(content, hook, flagged=lt.flagged_sentences_for(
                ROOT / Path(cfg["json_path"]).parent, rec))
            for token in ("###", ">", "**", "Source:", "["):
                assert token not in deck, (slug, deck)
            decks.append(deck)
        assert len(decks) >= 18 and sum(1 for d in decks if d) >= 15

    def test_the_card_renders_the_deck_under_the_hook_and_two_headlines(self, composed):
        copy = nde.render_for(composed.body, ["nerra-member", "Tesla Shorts Time"])
        # Nov 8 2026: the kicker carries the show; the headlines come under
        # "More in this episode" (plain when the front carries no links).
        card = copy.split("Your shows today", 1)[1].split("▶ Listen", 1)[0]
        assert "Tesla Shorts Time</span>" in card
        assert nde.HEADLINES_PER_CARD == 2
        assert 'deck"' in card and "Tesla Shorts Time deck sentence one." in card
        assert "More in this episode" in card
        assert "Tesla Shorts Time second item" in card and "Tesla Shorts Time third item" in card
        assert "Tesla Shorts Time fourth" not in card
        assert card.index("deck sentence one") < card.index("More in this episode")


class TestHeadlineWithinHook:
    def test_a_composite_hook_owns_each_half(self):
        from engine.newsroom import headline_within_hook, same_story
        head = "Tesla's October Registrations Surge in Northern Europe, Sweden Jumps 248%"
        assert not same_story(head, HOOK)  # 4 of 9 against the 0.5 floor
        assert headline_within_hook(head, HOOK)

    def test_a_product_family_digit_is_never_the_story(self):
        from engine.newsroom import headline_within_hook
        assert not headline_within_hook(
            "Tesla Cybercab Inverter Tech to Debut in Model 3 This Year",
            "Tesla is updating its Canadian Model 3 page with Fremont Long Range RWD specs after Shanghai units hit quota limits.")
        assert not headline_within_hook(
            "Mistral Large 4 drops from 38 to 25 on new Artificial Analysis index",
            "Gemini 4 Carbon scores 88.2 percent on vulnerability finding and leads the Artificial Analysis Intelligence Index at 59.")

    def test_same_story_still_counts(self):
        from engine.newsroom import headline_within_hook
        assert headline_within_hook(
            "SpaceX plans 10,000 annual Starship launches from Louisiana site",
            "SpaceX planning 10,000 Starship launches a year at its Louisiana site")
        assert not headline_within_hook(
            "Tesla spent $4.73 billion on capital expenditures last quarter",
            "Canadian variable-rate borrowers should watch the Fed decision")


class TestSentenceCase:
    def test_title_case_becomes_sentence_case_with_names_kept(self):
        out = lt.sentence_case_headline("Tesla Norway Sales Hit 130.7% YoY Growth And Best October Ever", DIGEST)
        assert out == "Tesla Norway sales hit 130.7% YoY growth and best October ever"

    def test_sentence_case_and_acronyms_pass_untouched(self):
        for h in ("Texas family finds missing cat inside their own Tesla",
                  "Bypoll results LIVE: BJP widens lead in West Bengal",
                  "SpaceX to launch USSF-432 Tuesday"):
            assert lt.sentence_case_headline(h, DIGEST) == h

    def test_it_never_clips(self):
        h = "Gary Black Says Tesla Is Losing EV Share to ‘No-Name’ Rivals Despite ‘Huge First-Mover Advantage’"
        out = lt.sentence_case_headline(h, "Investor Gary Black says Tesla is losing share to rivals despite its first-mover advantage.")
        assert len(out) == len(h) and out.lower() == h.lower()
        assert out.startswith("Gary Black says Tesla is losing EV share")

    def test_the_json_rows_carry_sentence_case(self):
        row = lt.story_json({"slug": "tesla", "hook": HOOK}, record={"content": DIGEST, "episode_num": "653"})
        assert "Tesla Norway sales hit 130.7% YoY growth and best October ever" in row["headlines"]


# ---------------------------------------------------------------------------
# The first screen
# ---------------------------------------------------------------------------


class TestTheFirstScreenIsTheNews:
    def test_the_first_card_precedes_the_edition_card(self, composed):
        src = composed.body
        assert src.index('class="nn card"') < src.index("🎧 Hear all of it")
        assert "Today's edition carries every show" not in src
        assert "Below: your shows" not in src

    def test_no_body_paragraph_precedes_the_first_heading(self, composed):
        for tags, subscriber in ((["nerra-member", "Tesla Shorts Time"], True),
                                 (["nerra-member"], True), ([], False)):
            copy = nde.render_for(composed.body, tags, subscriber=subscriber)
            body = copy.split("padding:16px 24px 24px;", 1)[1]
            assert body.index("<h2") < body.index("<p")

    def test_the_masthead(self, composed):
        # Nov 8 2026: the landing page's masthead (see
        # tests/test_nerra_daily_email_2026_11_08.py) replaced the compact one.
        from engine.brand import NETWORK_TAGLINE
        src = composed.body
        head = src.split("padding:16px 24px 24px;", 1)[0]
        assert "<h1" not in head and "<img" not in head
        assert NETWORK_TAGLINE in head
        assert "Hear all of it · 2 h 36 min" in head
        assert "Monday, November 2, 2026" in head and "7 shows published this morning" in head

    def test_the_archive_copy_opens_on_the_masthead_line_not_a_heading(self, composed):
        archive = nde.render_for(composed.body, [], subscriber=False)
        assert archive.index("shows published this morning") < archive.index("<h2")
        # The "Your shows today" heading is a reader's: never on the archive,
        # which carries the default set under "Today on Nerra".
        assert "Your shows today" not in archive and "Today on Nerra" in archive

    def test_dark_mode_keeps_a_headline_a_headline(self, composed):
        src = composed.body
        media = src.split("@media (prefers-color-scheme: dark)", 1)[1].split("</style>")[0]
        assert media.index(".nn a, .nn a span") < media.index(".nn .card-title a { color:#ffffff !important; }")
        assert 'card-title"' in src

    def test_the_per_show_emails_keep_the_full_hero(self):
        body = "## Top Stories\n\nTesla **moved**. [link](https://x.com)"
        kwargs = dict(daily_label="Ep 505", daily_date=dt.date(2026, 6, 9), preheader="p",
                      featured_episode={"episode_num": 505, "hook": "A hook", "date": "Jun 9"},
                      issue_number=505)
        default = nt.wrap_with_branding("finansy_prosto", body, **kwargs)
        explicit = nt.wrap_with_branding("finansy_prosto", body, hero="full",
                                         featured_position="top", **kwargs)
        assert default == explicit
        assert "<h1" in default
        assert default.index("Today's episode") < default.index("Top Stories")
        with pytest.raises(ValueError):
            nt.wrap_with_branding("finansy_prosto", body, hero="tiny", **kwargs)

    def test_contrast_holds_on_every_copy(self, composed):
        from engine.contrast_validator import assert_contrast_ok
        tags = [s.tag for s in nde.eligible_shows(_front())]
        for sample in (["nerra-member"], ["Tesla Shorts Time"], tags + [nde.PAID_TAG], []):
            assert_contrast_ok(nde.render_for(composed.body, sample, subscriber=bool(sample)))


# ---------------------------------------------------------------------------
# Also on Nerra today
# ---------------------------------------------------------------------------


class TestAlsoTodayReadsAsSections:
    def test_the_heading_is_a_heading_not_escaped_text(self, composed):
        # The Nov 1 and Nov 2 sends printed "<h2 …>Also on Nerra today</h2>"
        # as text: the line opened on {% if %} and the body renderer read it
        # as markdown. Every conditional block is wrapped in <div>.
        copy = nde.render_for(composed.body, ["nerra-member", "Tesla Shorts Time"])
        assert ">Also on Nerra today</h2>" in copy and "&lt;h2" not in copy
        for line in composed.body.splitlines():
            if line.startswith("{%"):
                raise AssertionError(f"a block opening on a template tag is escaped by the renderer: {line[:80]}")

    def test_no_line_exceeds_the_limit_and_the_show_is_a_label(self, composed):
        copy = nde.render_for(composed.body, ["nerra-member", "Tesla Shorts Time"])
        also = _also_section(copy)
        lines = re.findall(r'text-decoration:none;font-weight:700;font-size:17px;">([^<]+)</a>', also)
        assert len(lines) >= 5
        for line in lines:
            assert len(line) <= EMAIL_ALSO_LINE_MAX + len(ELLIPSIS)
        assert "when the line is printed in the email, says the digest" not in also
        assert 'text-decoration:underline' not in also.split("Elsewhere on Nerra", 1)[0]

    def test_a_fragment_clip_falls_back_to_the_digests_headline(self):
        story = _story("tesla", "Tesla Shorts Time", 1, DAY,
                       "iPhone Duo preorders open while the rest of Apple's lineup slips to next spring and the "
                       "Pro models move to the autumn, Gurman says",
                       ["Apple opens iPhone Duo preorders as the rest of the lineup slips"])
        assert nde.also_headline(story) == "Apple opens iPhone Duo preorders as the rest of the lineup slips"
        story["headlines"] = []
        assert nde.also_headline(story).startswith("iPhone Duo preorders")
        short = _story("tesla", "Tesla Shorts Time", 1, DAY, "Short hook stays whole.")
        assert nde.also_headline(short) == "Short hook stays whole."

    def test_labels_only_over_two_or_more_lines(self, composed):
        archive = nde.render_for(composed.body, [], subscriber=False)
        also = _also_section(archive)
        labels = re.findall(r'<p class="nn text-muted"[^>]*>([^<]+)</p>', also)
        # engine.landing_test.SECTION_ORDER: world news before AI; singletons last.
        assert labels == ["World news", "Artificial intelligence", "Elsewhere on Nerra"]
        assert "Space" not in labels and "Local news" not in labels
        assert also.index("World news") < also.index("Omni View lead story") < also.index("Artificial intelligence")
        assert also.index("Artificial intelligence") < also.index("MAG 7 Daily")
        assert also.index("Elsewhere on Nerra") < also.index("Vancouver Daily News")

    def test_a_label_renders_only_when_a_line_follows_it(self, composed):
        # Follows both AI shows: their lines and their label are gone.
        copy = nde.render_for(composed.body, ["nerra-member", "MAG 7 Daily", "Models & Agents"])
        also = _also_section(copy)
        assert "Artificial intelligence" not in also and "World news" in also
        # Follows nothing: the default cards cover SpaceX, Tesla, Top World and
        # Models & Agents, whose lines are therefore absent; each group still
        # has a line (Omni View, MAG 7, Vancouver), so each label stays.
        nobody = _also_section(nde.render_for(composed.body, ["nerra-member"]))
        assert "World news" in nobody and "Omni View lead story" in nobody
        assert "Omni View Top World News lead story" not in nobody
        assert "Artificial intelligence" in nobody and "Models &amp; Agents lead story" not in nobody
        assert "Elsewhere on Nerra" in nobody and "Vancouver Daily News lead story" in nobody
        assert "SpaceX Daily lead story" not in nobody and "Tesla Shorts Time lead story" not in nobody
        # Follows every show of every group: no label, no heading.
        every = nde.render_for(composed.body, ["nerra-member"] + [n for _, n, _ in SHOWS])
        assert "Also on Nerra today" not in every and "Elsewhere on Nerra" not in every

    def test_groups_follow_section_order_and_gather_singletons(self):
        picks = [nde.Pick(nde.EmailShow(slug=s, name=n, tag=n, brand="#000", brand_text="#000"),
                          _story(s, n, 1, DAY, "x", hub=h), [1]) for s, n, h in SHOWS]
        groups = nde.also_groups(picks)
        assert [g[0] for g in groups] == ["World news", "Artificial intelligence", "Elsewhere on Nerra"]
        assert [p.show.slug for p in groups[-1][1]] == ["spacex", "tesla", "vancouver"]
        # All singletons: no labels at all.
        assert nde.also_groups(picks[:2]) == [("", picks[:2])]


# ---------------------------------------------------------------------------
# Every headline whole
# ---------------------------------------------------------------------------


class TestEveryHeadlineIsWhole:
    def test_most_played_speaks_the_records_hook(self, tmp_path, monkeypatch):
        data = tmp_path / "site" / "data"
        data.mkdir(parents=True)
        (data / "popular_episodes.json").write_text(json.dumps([
            {"title": "Ep 142: SpaceX fired all 33 Raptor engines on the Super Heavy booster for a full-duration static…",
             "show_slug": "spacex", "show_name": "SpaceX Daily", "blog_url": "blog/spacex/ep142.html"},
            {"title": "Ep 9: A show with no record", "show_slug": "mag7", "show_name": "MAG 7 Daily"},
        ]))
        full = "SpaceX fired all 33 Raptor engines on the Super Heavy booster for a full-duration static fire at Starbase."
        monkeypatch.setattr(nde, "record_hook", lambda slug, ep, root=tmp_path: full if slug == "spacex" else "")
        rows = nde.most_played(tmp_path)
        assert rows[0]["title"] == full
        assert rows[1]["title"] == "A show with no record"

    def test_an_interview_story_carries_the_whole_hook(self):
        from generate_html import NETWORK_SHOWS
        for slug in ("age_of_ai",):
            cfg = NETWORK_SHOWS[slug]
            for rec in lt.recent_records(ROOT / cfg["json_path"], 3):
                story = lt.build_story({"slug": slug, "name": cfg["name"], "show_page": cfg["show_page"]},
                                       rec, blog_url_for=lambda s, n: "", audio_url_for=lambda u: u,
                                       gallery=None, hub=None)
                assert story and story["hook"] == (rec.get("hook") or "").strip()
                assert not story["hook"].endswith(ELLIPSIS)

    def test_news_records_are_unchanged_by_the_hook_fallback(self):
        rec = {"content": DIGEST, "episode_title": "Ep 653: clipped…", "hook": "ignored", "date": "2026-11-02"}
        story = lt.build_story({"slug": "tesla", "name": "Tesla", "show_page": "tesla.html"}, rec,
                               blog_url_for=lambda s, n: "", audio_url_for=lambda u: u, gallery=None, hub=None)
        assert story["hook"] == HOOK


# ---------------------------------------------------------------------------
# The size guard
# ---------------------------------------------------------------------------


class TestTheSizeGuardKnowsTheWrapper:
    def test_the_budget_is_derived_from_the_measured_wrapper(self):
        assert nde.size_warning_bytes() == 102_000 - nde.BUTTONDOWN_WRAPPER_BYTES - 2_000
        assert nde.BUTTONDOWN_WRAPPER_BYTES > 0 and "2026-11-03" in nde.BUTTONDOWN_WRAPPER_MEASURED

    def test_the_script_reads_it_and_records_the_archive_url(self, composed):
        src = (ROOT / "scripts" / "send_nerra_daily_email.py").read_text(encoding="utf-8")
        assert "nde.size_warning_bytes()" in src and "95_000" not in src
        assert '"archive_url": composed.archive_url' in src
        assert composed.archive_url.endswith(f"/archive/{composed.archive_slug}/")
        assert composed.archive_url in composed.body

    def test_titles_owns_the_also_line_limit(self):
        src = (ROOT / "engine" / "nerra_daily_email.py").read_text(encoding="utf-8")
        assert "EMAIL_ALSO_LINE_MAX" in src
        assert not re.search(r"hook\)?\[:\d+\]", src)
