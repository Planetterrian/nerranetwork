"""Guards for the advertising and sponsorship kit (Oct 21 2026).

Operator: build a sponsorship kit beside the media kit, in the same voice and
from the same numbers, priced as flat monthly packages a growing network can
hold for its first partners; then put the press and sponsorship kits in the
messages guests and publicists get. What binds:

* the rates, packages, terms and reasons have ONE owner (engine.brand); the
  template never types a price, a package or a rule;
* every package's reach is MEASURED (a dash when not), never a forecast, and
  only free shows are for sale: the interview shows carry no sponsor;
* the guest-facing mail and the producer's facts read the two kit URLs from
  engine.brand, and the producer may link them;
* a would-be advertiser gets a reply drafted for Patrick, never one sent;
* no page still says the network does not take sponsorships.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import brand  # noqa: E402

FREE_COUNT_RE = re.compile(
    r"\b(\d{1,3})\s+(?:free\s+|independent\s+)?(?:shows|podcasts)\b|Shows:\s*(\d{1,3})")


def _render(tmp_path):
    import generate_html
    generate_html.generate_sponsor_page(output_dir=tmp_path)
    return (tmp_path / "sponsor.html").read_text(encoding="utf-8")


class TestTheRateCardHasOneOwner:
    def test_packages_are_well_formed(self):
        ids = [p["id"] for p in brand.SPONSOR_PACKAGES]
        assert len(ids) == len(set(ids))
        assert sum(1 for p in brand.SPONSOR_PACKAGES if p.get("featured")) == 1
        for p in brand.SPONSOR_PACKAGES:
            assert isinstance(p["price"], int) and p["price"] > 0, p["id"]
            assert p["name"] and p["summary"] and p["includes"] and p["term"]
            for text in (p["name"], p["summary"], p["term"], *p["includes"]):
                assert "—" not in text and "ad-free" not in text.lower()

    def test_only_free_shows_are_for_sale(self):
        import generate_html
        public = {s["slug"] for s in generate_html._public_shows(generate_html._build_all_shows_list())}
        for p in brand.SPONSOR_PACKAGES:
            for slug in p["shows"]:
                assert slug in public, f"{p['id']} sells {slug}, which is not a free show"
                assert slug not in brand.HUMAN_REVIEW_SHOW_SLUGS, f"{p['id']} sells an interview show"

    def test_the_interview_rule_is_a_policy_rule(self):
        titles = [t for t, _b in brand.SPONSOR_POLICY_RULES]
        assert "Never on an interview" in titles

    def test_template_never_types_a_rate_or_a_package(self):
        body = (ROOT / "templates" / "sponsor_page.html.j2").read_text(encoding="utf-8")
        body = re.sub(r"\{#.*?#\}", "", body, flags=re.S)
        assert not re.search(r"\$\s?\d", body), "a price is typed in the template"
        for p in brand.SPONSOR_PACKAGES:
            assert p["name"] not in body, f"package {p['name']!r} is typed in the template"
        for title, _b in brand.SPONSOR_TERMS + brand.SPONSOR_REASONS:
            assert title not in body

    def test_kit_urls(self):
        assert brand.SPONSOR_KIT_URL == "https://nerranetwork.com/sponsor.html"
        assert brand.MEDIA_KIT_URL == "https://nerranetwork.com/press.html"
        assert brand.SPONSOR_KIT_URL in brand.kits_sentence()
        assert brand.MEDIA_KIT_URL in brand.kits_sentence()


class TestTheKitPage:
    def test_renders_every_package_term_step_and_rule(self, tmp_path):
        html = _render(tmp_path)
        for p in brand.sponsor_packages():
            assert p["name"].replace("&", "&amp;") in html
            assert p["price_text"] in html
        for t, _b in brand.SPONSOR_TERMS + brand.SPONSOR_STEPS + brand.SPONSOR_REASONS:
            assert t in html
        for t, _b in brand.SPONSOR_POLICY_RULES:
            assert t in html
        assert brand.network_promise_visitor() in html
        assert brand.NETWORK_TAGLINE in html
        assert f"mailto:{brand.SPONSOR_EMAIL}" in html
        assert 'href="press.html"' in html
        assert "editorial.html#sponsors" in html
        assert "The audience, measured" in html  # the Oct 11 guard's heading

    def test_measured_reach_and_the_interview_shows(self, tmp_path):
        html = _render(tmp_path)
        assert "not for sale" in html and "The Age of AI" in html
        assert "ad-free" not in html.lower()
        for m in FREE_COUNT_RE.finditer(re.sub(r"<[^>]+>", " ", html)):
            n = int(m.group(1) or m.group(2))
            import generate_html
            assert n == generate_html._public_show_count_cached(), m.group(0)

    def test_unmeasured_reach_is_a_dash(self, tmp_path, monkeypatch):
        import generate_html
        data = {"as_of": "2026-10-20",
                "shows": {"spacex": {"downloads_30d": None, "youtube": {"views": 0}}}}
        monkeypatch.setattr(generate_html, "_load_json_quiet", lambda path: data)
        pkgs = generate_html._sponsor_package_reach(brand.sponsor_packages())
        spacex = next(p for p in pkgs if p["id"] == "spacex")
        assert spacex["reach"]["downloads_30d"] == "—"
        assert spacex["reach"]["youtube_views"] == "—"
        single = next(p for p in pkgs if not p["shows"])
        assert single["reach"] is None
        names = {s["name"] for s in single["show_links"]}
        assert "The Age of AI" not in names and "SpaceX Daily" not in names

    def test_reach_sums_the_packages_shows(self, tmp_path, monkeypatch):
        import generate_html
        data = {"shows": {"spacex": {"downloads_30d": 100, "youtube": {"views": 50}},
                          "tesla": {"downloads_30d": 20, "youtube": {"views": 5}},
                          "nerra_daily": {"downloads_30d": 3, "youtube": {"views": 0}}}}
        monkeypatch.setattr(generate_html, "_load_json_quiet", lambda path: data)
        pkgs = generate_html._sponsor_package_reach(brand.sponsor_packages())
        founding = next(p for p in pkgs if p["id"] == "founding")
        assert founding["reach"]["downloads_30d"] == "123"
        assert founding["reach"]["youtube_views"] == "55"
        assert founding["reach"]["measured"] == founding["reach"]["count"] == 3

    def test_aliases_forward_to_the_kit(self):
        entries = yaml.safe_load((ROOT / "site" / "redirects.yaml").read_text(encoding="utf-8"))
        rows = entries["redirects"] if isinstance(entries, dict) else entries
        targets = {r["from"]: r["to"] for r in rows}
        assert targets.get("advertise.html") == "sponsor.html"
        assert targets.get("sponsorship-kit.html") == "sponsor.html"

    def test_the_media_kit_points_to_the_sponsorship_kit(self):
        body = (ROOT / "templates" / "press.html.j2").read_text(encoding="utf-8")
        assert "Advertising and sponsorship kit" in body
        base = (ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8")
        assert "Advertise & Sponsor" in base and "Media Kit" in base


class TestNoPageStillRefusesSponsors:
    def test_about_and_contact(self):
        for name in ("about.html.j2", "contact.html.j2"):
            body = (ROOT / "templates" / name).read_text(encoding="utf-8")
            assert "take sponsorships" not in body, name
            assert "sponsor.html" in body, name


class TestGuestMailCarriesTheKits:
    def test_producer_facts_and_links(self):
        from pipelines.producer import guest_reply
        facts = guest_reply.facts_for({"app": {"name": "Jane Doe", "show": "age_of_ai"},
                                       "interviews": []})
        assert brand.MEDIA_KIT_URL in facts["facts"]
        assert brand.SPONSOR_KIT_URL in facts["facts"]
        assert brand.MEDIA_KIT_URL in facts["links"] and brand.SPONSOR_KIT_URL in facts["links"]
        reply = f"Hi Jane,\nOur media kit is here: {brand.MEDIA_KIT_URL}."
        assert guest_reply.guard(reply, facts["links"]) == ""

    def test_followup_prompt_points_at_the_media_kit(self):
        text = (ROOT / "pipelines" / "producer" / "prompts" / "followup_reply.txt").read_text()
        assert "{{media_kit_url}}" in text and "{{sponsor_kit_url}}" in text
        assert "we do not publish or promise listener numbers" not in text
        src = (ROOT / "pipelines" / "producer" / "followup.py").read_text()
        assert '"media_kit_url": _brand.MEDIA_KIT_URL' in src

    def test_publish_day_note(self, monkeypatch):
        sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
        import publish_episode as pe

        class _Show:
            name = "The Age of AI"
            short_label = "Age of AI"
            slug = "age_of_ai"
            page_url = "https://nerranetwork.com/age-of-ai.html"
            base_url = "https://nerranetwork.com"
            apple_url = ""
            spotify_url = ""
            audio_subdir = "digests/age_of_ai"

            def post_url(self, n):
                return f"https://nerranetwork.com/blog/age_of_ai/ep{n:03d}.html"

        monkeypatch.setattr(pe, "clip_link", lambda p, s, n: ("", ""))
        monkeypatch.setattr(pe, "share_card_link", lambda s, n: "")
        monkeypatch.setattr(pe, "mira_signature_html", lambda show=None: "<p>Mira</p>")
        _subject, body = pe.published_email(_Show(), {"name": "Jane Doe"}, {}, 12)
        assert brand.MEDIA_KIT_URL in body and brand.SPONSOR_KIT_URL in body
        assert "never carry a sponsor" in body
        assert body.rindex(brand.SPONSOR_KIT_URL) < body.index("Thank you again")

    def test_would_be_advertiser_reply_is_miras_and_names_patrick(self):
        from pipelines.producer import inbox
        body = inbox.render_sponsor_reply({"from_name": "Dana Lee"})
        assert body.startswith("Hi Dana,")
        assert "Sincerely,\n\nMira" in body
        assert "Patrick Novak" in body and "handles sponsorship himself" in body
        assert "—" not in body
        assert brand.SPONSOR_KIT_URL in body and brand.MEDIA_KIT_URL in body
        assert inbox.render_sponsor_reply({"from_name": ""}).startswith("Hi There,")

    def test_classifier_and_policy_know_the_category(self):
        from pipelines.producer import classify, policy
        assert "sponsor_inquiry" in classify.CATEGORIES
        pol = policy.load_policy()
        assert "sponsor_inquiry" in pol.hold_categories
        d = policy.decide({"category": "sponsor_inquiry", "confidence": 0.95},
                          policy=pol, sender_email="dana@brandco.com",
                          already_replied=False, already_in_db=False, sends_so_far=0)
        assert d.action == "draft" and d.notify
