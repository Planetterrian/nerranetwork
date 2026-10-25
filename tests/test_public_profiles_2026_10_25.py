"""Oct 25 2026: a public profile on every application, and its photo on the post.

Patrick: guests fill in an X account, a LinkedIn profile, or a link to their
public profile on their company's site, at least one of them mandatory, so
the application can be verified; and the episode post, when it publishes,
carries the image from that public profile and the link or links.

The Worker half (the form's rule, the 400, the links column) is proven in
workers/voices/test/public_profiles.test.ts. This file proves the rest: the
pages ask for it, the Python side reads the profiles back, the photo is found,
squared, kept and never forced over one set by hand, the Producer does not
send a booking link without a profile, the post shows the photo and the
links, and the X post tags the guest.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))

from pipelines.voices import common  # noqa: E402
import profile_photo as pp  # noqa: E402


# ---------------------------------------------------------------------------
# The apply pages
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("page", ["nerra-voices-apply.html", "age-of-ai-apply.html"])
class TestTheFormAsks:

    def test_three_boxes_in_one_required_group(self, page):
        html = (ROOT / page).read_text(encoding="utf-8")
        assert '<fieldset class="profiles"' in html
        for box in ("x_profile", "linkedin_profile", "company_profile"):
            assert f'id="{box}"' in html
        assert "Where can we see you in public? *" in html
        assert "At least one of these three" in html

    def test_it_says_what_the_profile_is_for(self, page):
        html = (ROOT / page).read_text(encoding="utf-8")
        assert "confirm who" in html
        assert "public profile photo" in html
        assert "tag your account" in html

    def test_the_payload_carries_each_box_under_its_own_key(self, page):
        html = (ROOT / page).read_text(encoding="utf-8")
        assert "x: val('x_profile')" in html
        assert "linkedin: val('linkedin_profile')" in html
        assert "company_profile: val('company_profile')" in html
        assert "raw: val('links')" in html

    def test_it_stops_before_sending_when_all_three_are_empty_and_shows_the_servers_words(self, page):
        html = (ROOT / page).read_text(encoding="utf-8")
        assert "!val('x_profile') && !val('linkedin_profile') && !val('company_profile')" in html
        assert "resp.status === 400" in html and "data.error" in html


# ---------------------------------------------------------------------------
# Reading the profiles back
# ---------------------------------------------------------------------------

class TestPublicProfiles:

    def test_the_forms_keys(self):
        app = {"links": {"x": "https://x.com/pipermartz",
                         "linkedin": "https://www.linkedin.com/in/piper-martz",
                         "company_profile": "https://aampe.com/team/piper", "raw": "aampe.com"}}
        assert common.public_profiles(app) == {
            "x": "https://x.com/pipermartz",
            "linkedin": "https://www.linkedin.com/in/piper-martz",
            "company_profile": "https://aampe.com/team/piper"}
        assert common.has_public_profile(app)
        assert common.x_handle(app) == "pipermartz"

    def test_older_rows_and_pitches_count_when_a_profile_is_in_the_text(self):
        assert common.public_profiles({"links": {"raw": "aampe.com, https://twitter.com/pipermartz"}}) \
            == {"x": "https://x.com/pipermartz"}
        assert common.public_profiles(
            {"links": {"urls": ["https://ca.linkedin.com/in/piper-martz/?trk=x"]}}) \
            == {"linkedin": "https://www.linkedin.com/in/piper-martz"}

    def test_a_bare_company_site_is_not_a_profile(self):
        app = {"links": {"urls": ["https://aampe.com"], "raw": "https://www.linkedin.com/company/aampe"}}
        assert common.public_profiles(app) == {}
        assert not common.has_public_profile(app)
        assert common.x_handle(app) == ""

    def test_profiles_written_in_an_email(self):
        text = ("Sure, here is her LinkedIn: linkedin.com/in/lena-ortiz. "
                "She's also @lena on X (https://x.com/lenaortiz).")
        assert common.profile_links_in(text) == {
            "x": "https://x.com/lenaortiz", "linkedin": "https://www.linkedin.com/in/lena-ortiz"}
        assert common.profile_links_in("see https://x.com/home and aampe.com") == {}

    def test_the_company_page_is_labelled_by_its_site(self):
        links = common.guest_links({"links": {"company_profile": "https://aampe.com/team/piper",
                                              "linkedin": "https://www.linkedin.com/in/piper"}})
        assert links[0] == {"label": "aampe.com", "url": "https://aampe.com/team/piper"}
        assert {"label": "LinkedIn", "url": "https://www.linkedin.com/in/piper"} in links


# ---------------------------------------------------------------------------
# The photo
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, text="", content=b"", ctype="text/html", url=""):
        self.text, self.content, self.url = text, content, url
        self.headers = {"Content-Type": ctype}
        self.status_code = 200


def _png(w=600, h=800, colour=(200, 40, 40)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(buf, "PNG")
    return buf.getvalue()


class TestFindingThePhoto:

    def test_names_person(self):
        assert pp.names_person("Piper Martz, CEO", "Piper Martz")
        assert pp.names_person("piper-martz-headshot.jpg", "Dr. Piper Martz, PhD")
        assert not pp.names_person("Jane Martz", "Piper Martz")
        assert not pp.names_person("Our team", "Piper Martz")

    def test_the_headshot_on_a_team_page(self, monkeypatch):
        page = """<html><head><meta property="og:image" content="/og-company.png">
          <title>Team | Aampe</title></head><body>
          <img src="/logo.svg" alt="Aampe">
          <img src="/img/jon.jpg" alt="Jon Smith">
          <img srcset="/img/piper-400.jpg 400w, /img/piper-800.jpg 800w" alt="Piper Martz">
        </body></html>"""
        monkeypatch.setattr(pp, "_get", lambda url, **k: _Resp(page, url="https://aampe.com/team"))
        assert pp.from_company_page("https://aampe.com/team", "Piper Martz") \
            == "https://aampe.com/img/piper-800.jpg"

    def test_a_page_about_them_gives_its_share_image_and_a_company_page_gives_nothing(self, monkeypatch):
        about = ('<html><head><meta property="og:title" content="Piper Martz | Aampe">'
                 '<meta property="og:image" content="https://aampe.com/p.jpg"></head><body></body></html>')
        monkeypatch.setattr(pp, "_get", lambda url, **k: _Resp(about, url=url))
        assert pp.from_company_page("https://aampe.com/piper", "Piper Martz") == "https://aampe.com/p.jpg"
        company = ('<html><head><meta property="og:title" content="Aampe">'
                   '<meta property="og:image" content="https://aampe.com/og.jpg"></head></html>')
        monkeypatch.setattr(pp, "_get", lambda url, **k: _Resp(company, url=url))
        assert pp.from_company_page("https://aampe.com", "Piper Martz") is None

    def test_linkedin_only_gives_the_persons_own_photo(self, monkeypatch):
        own = ('<meta property="og:image" content="https://media.licdn.com/dms/image/v2/D56/'
               'profile-displayphoto-shrink_800_800/0/1?e=1&v=beta">')
        monkeypatch.setattr(pp, "_get", lambda url, **k: _Resp(own))
        assert "profile-displayphoto" in pp.from_linkedin("https://www.linkedin.com/in/p", "P M")
        ghost = '<meta property="og:image" content="https://static.licdn.com/aero-v1/sc/h/ghost.png">'
        monkeypatch.setattr(pp, "_get", lambda url, **k: _Resp(ghost))
        assert pp.from_linkedin("https://www.linkedin.com/in/p", "P M") is None
        monkeypatch.setattr(pp, "_get", lambda url, **k: None)   # LinkedIn's 999
        assert pp.from_linkedin("https://www.linkedin.com/in/p", "P M") is None

    def test_the_order_is_linkedin_then_the_company_page_then_x(self, monkeypatch):
        seen = []
        monkeypatch.setattr(pp, "from_linkedin", lambda u, n: seen.append("li") or None)
        monkeypatch.setattr(pp, "from_company_page", lambda u, n: seen.append("co") or "https://a/co.jpg")
        monkeypatch.setattr(pp, "from_x", lambda h: seen.append(("x", h)) or "https://a/x.jpg")
        app = {"name": "Piper Martz", "links": {"x": "https://x.com/pipermartz",
               "linkedin": "https://www.linkedin.com/in/p", "company_profile": "https://aampe.com/t"}}
        assert pp.candidates(app) == [("https://a/co.jpg", "https://aampe.com/t"),
                                      ("https://a/x.jpg", "https://x.com/pipermartz")]
        assert seen == ["li", "co", ("x", "pipermartz")]

    def test_x_asks_for_the_big_picture(self, monkeypatch):
        class _User:
            data = type("D", (), {"profile_image_url":
                                  "https://pbs.twimg.com/profile_images/1/abc_normal.jpg"})()

        class _Client:
            def __init__(self, **kw):
                assert set(kw) == {"consumer_key", "consumer_secret", "access_token",
                                   "access_token_secret"}

            def get_user(self, **kw):
                assert kw["username"] == "pipermartz" and kw["user_auth"] is True
                return _User()

        import types
        monkeypatch.setitem(sys.modules, "tweepy", types.SimpleNamespace(Client=_Client))
        for k in ("CONSUMER_KEY", "CONSUMER_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET"):
            monkeypatch.setenv(f"NERRANETWORK_X_{k}", "v")
        assert pp.from_x("pipermartz") == "https://pbs.twimg.com/profile_images/1/abc_400x400.jpg"


class TestKeepingThePhoto:

    def test_square_jpeg(self):
        from PIL import Image
        out = pp.square_jpeg(_png(600, 900))
        with Image.open(io.BytesIO(out)) as img:
            assert img.format == "JPEG" and img.size == (400, 400)
        with Image.open(io.BytesIO(pp.square_jpeg(_png(200, 260)))) as img:
            assert img.size == (200, 200)   # never enlarged
        with pytest.raises(ValueError):
            pp.square_jpeg(_png(48, 48))   # an icon, not a photo

    def test_stored_on_r2_and_recorded_on_the_application(self, monkeypatch):
        uploads, updates = [], []
        monkeypatch.setattr(pp, "candidates", lambda app: [("https://bad/x.jpg", "https://x.com/p"),
                                                           ("https://ok/p.png", "https://aampe.com/t")])
        monkeypatch.setattr(pp, "download_image",
                            lambda url: _png() if "ok" in url else (_ for _ in ()).throw(ValueError("nope")))

        def fake_upload(local, key, content_type=""):
            uploads.append((key, content_type, Path(local).read_bytes()[:3]))
            return f"https://audio.nerranetwork.com/{key}"
        monkeypatch.setattr(pp, "r2_upload", fake_upload)
        monkeypatch.setattr(pp, "sb_update", lambda t, q, patch: updates.append((t, q, patch)))
        app = {"id": "app-1", "name": "Piper Martz"}
        url = pp.store_photo(app)
        assert re.fullmatch(r"https://audio\.nerranetwork\.com/voices/guests/app-1/photo-[0-9a-f]{10}\.jpg", url)
        assert uploads[0][1] == "image/jpeg" and uploads[0][2] == b"\xff\xd8\xff"
        table, query, patch = updates[0]
        assert table == "guest_applications" and query == "id=eq.app-1"
        assert patch["profile_photo_url"] == url
        assert patch["profile_photo_source"] == "https://aampe.com/t"
        assert app["profile_photo_url"] == url

    def test_one_already_there_is_kept_unless_asked(self, monkeypatch):
        monkeypatch.setattr(pp, "candidates", lambda app: pytest.fail("looked again"))
        app = {"id": "a", "profile_photo_url": "https://audio.nerranetwork.com/voices/guests/a/photo-1.jpg"}
        assert pp.store_photo(app) == app["profile_photo_url"]

    def test_by_hand_wins(self, monkeypatch):
        monkeypatch.setattr(pp, "candidates", lambda app: pytest.fail("looked instead of using the URL"))
        monkeypatch.setattr(pp, "download_image", lambda url: _png())
        monkeypatch.setattr(pp, "r2_upload", lambda local, key, content_type="": f"https://r2/{key}")
        patches = []
        monkeypatch.setattr(pp, "sb_update", lambda t, q, patch: patches.append(patch))
        app = {"id": "a", "profile_photo_url": "https://r2/old.jpg"}
        assert pp.store_photo(app, image_url="https://me/photo.jpg").startswith("https://r2/voices/guests/a/")
        assert patches[0]["profile_photo_source"] == "set by hand"

    def test_nothing_here_can_stop_a_screen_or_a_publish(self, monkeypatch):
        monkeypatch.setattr(pp, "store_photo", lambda app: (_ for _ in ()).throw(RuntimeError("R2 down")))
        assert pp.ensure_photo({"id": "a"}) is None


# ---------------------------------------------------------------------------
# Patrick sees it before he approves
# ---------------------------------------------------------------------------

class TestTheScreen:

    def test_the_prompt_is_given_the_profiles_and_told_to_check_them(self):
        import screen_applications as sa
        prompt = (ROOT / "pipelines/voices/prompts/screen_application.txt").read_text()
        assert "Public profiles: {{public_profiles}}" in prompt
        assert "first concern" in prompt
        assert sa.profiles_text({"links": {"linkedin": "https://www.linkedin.com/in/p"}}) \
            == "LinkedIn: https://www.linkedin.com/in/p"
        assert sa.profiles_text({}) == "(none given)"

    def test_the_assessment_email_shows_the_photo_and_the_links_or_says_none(self):
        import screen_applications as sa
        app = {"name": "Piper Martz", "show": "nerra_voices",
               "links": {"x": "https://x.com/pipermartz"},
               "profile_photo_url": "https://audio.nerranetwork.com/voices/guests/a/photo-1.jpg"}
        result = {"verdict": "strong", "summary": "s", "specifics": [], "concerns": [], "ask_first": ""}
        _, body = sa.assessment_email(app, result)
        assert "photo-1.jpg" in body and 'href="https://x.com/pipermartz"' in body
        assert "wrong person" in body
        _, body = sa.assessment_email({"name": "R", "show": "nerra_voices"}, result)
        assert "No public profile given" in body

    def test_the_photo_is_found_when_the_application_is_screened(self):
        src = (ROOT / "pipelines/voices/screen_applications.py").read_text()
        assert "ensure_photo(app)" in src
        assert src.index("ensure_photo(app)") < src.index("assessment_email(app, result)\n        try")

    def test_the_screen_and_publish_jobs_can_reach_r2(self):
        import yaml
        for name in ("nerra_voices_screen_applications.yml", "nerra_voices_publish.yml"):
            wf = yaml.safe_load((ROOT / ".github/workflows" / name).read_text())
            env = next(s for s in next(iter(wf["jobs"].values()))["steps"] if "env" in s)["env"]
            for key in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_PUBLIC_BASE_URL"):
                assert env[key] == "${{ secrets.%s }}" % key, (name, key)


# ---------------------------------------------------------------------------
# The Producer's email path
# ---------------------------------------------------------------------------

class TestNoBookingLinkWithoutAProfile:

    def _plan(self, intent="ready_to_book"):
        return {"intent": intent, "confidence": 0.95, "reply_text": "Hi Sam,\n\nHere is the link.",
                "summary": "wants to book"}

    def _app(self, **over):
        base = {"id": "app1", "name": "Dr. Lena Ortiz", "status": "invited", "source": "email",
                "producer_followup_count": 0}
        base.update(over)
        return base

    def test_held_without_one_sent_with_one(self):
        from pipelines.producer import followup
        held = followup.decide_followup(self._plan(), self._app(), mode="auto", inbound_auto=False)
        assert held["action"] == "draft" and "public profile" in held["reason"]
        ok = followup.decide_followup(
            self._plan(), self._app(links={"urls": ["https://www.linkedin.com/in/lena"]}),
            mode="auto", inbound_auto=False)
        assert ok["action"] == "send" and ok["status_patch"]["status"] == "approved"

    def test_a_profile_in_their_reply_is_taken_before_mira_decides(self):
        from pipelines.producer import followup
        app = self._app(links={"urls": ["https://reyespr.com"]})
        new = followup.take_profiles_from(
            {"body": "Here's her LinkedIn: https://www.linkedin.com/in/lena-ortiz\n\n"
                     "On Mon, Sam wrote:\n> https://x.com/someoneelse"}, app)
        assert new == {"linkedin": "https://www.linkedin.com/in/lena-ortiz"}
        assert app["links"] == {"urls": ["https://reyespr.com"],
                                "linkedin": "https://www.linkedin.com/in/lena-ortiz"}
        assert followup.profile_on_file(app) == "LinkedIn https://www.linkedin.com/in/lena-ortiz"
        assert followup.profile_on_file(self._app()) == "none"

    def test_the_prompt_tells_mira_to_ask_for_one(self):
        prompt = (ROOT / "pipelines/producer/prompts/followup_reply.txt").read_text()
        assert "{{public_profile_on_file}}" in prompt
        assert "asks for one of the three instead" in prompt

    def test_a_pitch_without_one_is_asked_for_it_instead_of_given_the_link(self, monkeypatch):
        from pipelines.producer import inbox, followup
        monkeypatch.setattr(followup, "booking_url", lambda slug: "https://cal.com/nerra/45")

        class _Policy:
            def blurb(self, slug):
                return "a show"

            def pitched_show_name(self, s):
                return ""
        bare = {"guest_name": "Lena Ortiz", "publicist_name": "Sam Reyes",
                "recommended_show": "nerra_voices", "links": ["https://reyespr.com"]}
        ctx = inbox.invite_context(bare, "Sam Reyes", _Policy())
        assert ctx["needs_profile"] is True and ctx["booking_url"] == ""
        text = inbox.render_text(inbox.INVITE_TEMPLATE, ctx["show_slug"], **ctx)
        assert "one public profile for Lena" in text and "cal.com" not in text
        with_li = dict(bare, links=["https://www.linkedin.com/in/lena-ortiz"])
        ctx = inbox.invite_context(with_li, "Sam Reyes", _Policy())
        assert ctx["needs_profile"] is False and ctx["booking_url"] == "https://cal.com/nerra/45"


# ---------------------------------------------------------------------------
# The post and the X post
# ---------------------------------------------------------------------------

class TestThePost:

    def test_the_record_carries_the_photo_and_publish_looks_for_one(self):
        src = (ROOT / "pipelines/voices/publish_episode.py").read_text()
        assert '"guest_photo": photo,' in src
        assert "photo = ensure_photo(app)" in src
        assert "mention=x_handle(app)" in src

    def test_interview_context_reads_the_photo(self, tmp_path):
        from engine.interviews import interview_context, parse_interview_digest
        assert parse_interview_digest("")["guest_photo"] == ""
        rec = tmp_path / "s.json"
        rec.write_text(json.dumps({"episodes": [{"episode": 3, "guest": "Piper Martz",
            "guest_photo": "https://audio.nerranetwork.com/voices/guests/a/photo-1.jpg",
            "guest_links": [{"label": "X", "url": "https://x.com/pipermartz"}]}]}))
        ctx = interview_context("", "nerra_voices", 3, summaries_path=str(rec))
        assert ctx["guest_photo"].endswith("photo-1.jpg")
        rec.write_text(json.dumps({"episodes": [{"episode": 3, "guest_photo": "javascript:x"}]}))
        assert interview_context("", "nerra_voices", 3, summaries_path=str(rec))["guest_photo"] == ""

    def test_the_rendered_post_shows_the_photo_beside_the_name_and_the_links(self, monkeypatch):
        import generate_html as G
        from engine import blog
        from engine.blog import extract_blog_metadata, generate_blog_post_html
        real = blog.interview_context

        def with_photo(*a, **k):
            ctx = real(*a, **k)
            ctx["guest_photo"] = "https://audio.nerranetwork.com/voices/guests/a/photo-1.jpg"
            ctx["guest_links"] = [{"label": "X", "url": "https://x.com/pipermartz"},
                                  {"label": "LinkedIn", "url": "https://www.linkedin.com/in/piper"}]
            return ctx
        monkeypatch.setattr(blog, "interview_context", with_photo)
        path = sorted((ROOT / "digests" / "age_of_ai").glob("Age_of_AI_Ep0*.md"))[-1]
        md = path.read_text(encoding="utf-8")
        meta = extract_blog_metadata(md, "age_of_ai", path.name, file_path=path)
        meta["_md_path"] = path
        html = generate_blog_post_html(md, meta, G.NETWORK_SHOWS["age_of_ai"], G._get_jinja_env())
        hero = html[html.index('<header class="nn-iv-hero">'):]
        hero = hero[:hero.index("</header>")]
        assert 'class="nn-iv-photo" src="https://audio.nerranetwork.com/voices/guests/a/photo-1.jpg"' in hero
        assert hero.index("nn-iv-photo") < hero.index('class="nn-iv-name"')
        assert 'href="https://x.com/pipermartz"' in hero and 'href="https://www.linkedin.com/in/piper"' in hero
        ld = json.loads(re.search(r'<script type="application/ld\+json">\s*(\[.*?\])\s*</script>',
                                  html, re.S).group(1))
        person = ld[0]["about"]
        assert person["image"].endswith("photo-1.jpg")
        assert "https://x.com/pipermartz" in person["sameAs"]

    def test_a_post_without_a_photo_renders_as_before(self):
        import generate_html as G
        from engine.blog import extract_blog_metadata, generate_blog_post_html
        path = sorted((ROOT / "digests" / "age_of_ai").glob("Age_of_AI_Ep0*.md"))[-1]
        md = path.read_text(encoding="utf-8")
        meta = extract_blog_metadata(md, "age_of_ai", path.name, file_path=path)
        meta["_md_path"] = path
        html = generate_blog_post_html(md, meta, G.NETWORK_SHOWS["age_of_ai"], G._get_jinja_env())
        assert 'class="nn-iv-photo"' not in html and 'class="nn-iv-name"' in html


class TestTheXPostTagsTheGuest:

    def test_teaser_with_and_without_a_mention(self):
        from engine.x_post import teaser_text
        assert teaser_text("Ep14: Piper Martz", "https://n.com/x") == "Ep14: Piper Martz\n\nhttps://n.com/x"
        assert teaser_text("Ep14: Piper Martz", "https://n.com/x", "@pipermartz") \
            == "Ep14: Piper Martz\n\nWith @pipermartz\n\nhttps://n.com/x"

    def test_the_title_gives_way_to_the_tag(self):
        from engine.titles import X_TEASER_TEXT_MAX
        from engine.x_post import teaser_text
        text = teaser_text("word " * 200, "L", "pipermartz")
        head = text.split("\n\n")[0]
        assert len(head) <= X_TEASER_TEXT_MAX - len("With @pipermartz") - 2
        assert "With @pipermartz" in text
