"""Oct 15 2026, Patrick: the closing round of every interview is worth keeping,
and the people guests name for Mira to interview next are leads.

pipelines/voices/referrals.py reads each published interview's closing round
(a book, the best advice, who inspires them, the show's own question, who to
interview next), stores it on the episode's record, and turns every named
person into a referral. Mira invites them, crediting the guest, when an
address is printed on a public page. Oct 16 (Patrick): she never asks the guest
for an introduction and never waits a day; no address means no invitation, and
the name goes on Patrick's list. guest-picks.html shows the answers.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))

import referrals as R  # noqa: E402

VINCENT_IV = "iv-vincent"
JASON_IV = "iv-jason"
HINTON_PAGE = "https://media.utoronto.ca/"
HINTON_MAIL = "media.relations@utoronto.ca"


def _ago(hours: float) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).isoformat()


VINCENT_PICKS = {
    "book": None,
    "advice": {"text": "Write every day.", "source": ""},
    "inspiration": None,
    "bet": "Fiction will explain AI risk better than papers.",
    "interview_next": [{"name": "Geoffrey Hinton", "organization": "University of Toronto",
                        "role": "Professor emeritus", "why": "He understands the risk better than anyone.",
                        "note": "Heard as 'Jeffrey Henson'; corrected."}],
    "note": "",
}
JASON_PICKS = {
    "book": {"title": "The E-Myth", "author": "Michael E. Gerber", "why": "Work on the business."},
    "advice": {"text": "Never give up.", "source": ""},
    "inspiration": {"who": "My dad", "why": ""},
    "bet": None,
    "interview_next": [{"name": "Tim Martinez", "organization": "", "role": "", "why": "",
                        "note": "Name was hard to make out in the recording."}],
    "note": "",
}


class FakeDB:
    """Just enough PostgREST for referrals.py."""

    def __init__(self):
        self.interviews = [
            {"id": VINCENT_IV, "application_id": "app-vincent", "show": "age_of_ai",
             "episode_number": 7, "scheduled_at": "2026-09-22T16:00:00+00:00", "status": "published"},
            {"id": JASON_IV, "application_id": "app-jason", "show": "age_of_ai",
             "episode_number": 11, "scheduled_at": "2026-10-09T16:00:00+00:00", "status": "published"},
        ]
        self.apps = [
            {"id": "app-vincent", "name": "Vincent Rylan", "email": "vincent@example.com",
             "status": "approved", "publicist_email": None},
            {"id": "app-jason", "name": "Jason Fishman", "email": "jason@example.com",
             "status": "approved", "publicist_email": "pr@example.com"},
        ]
        self.records = [{"id": "rec-v", "interview_id": VINCENT_IV, "picks": None},
                        {"id": "rec-j", "interview_id": JASON_IV, "picks": None}]
        self.packages = {VINCENT_IV: "Mira: Who should I interview next?\nVincent: Jeffrey Henson.",
                         JASON_IV: "Mira: Who should I interview next?\nJason: Tim Martinez."}
        self.referrals: List[Dict[str, Any]] = []
        self.log: List[tuple] = []

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _eq(q, field):
        m = re.search(rf"(?:^|&){field}=eq\.([^&]+)", q)
        return m.group(1) if m else None

    def select(self, table, query=""):
        q = unquote(query)
        self.log.append(("select", table, q))
        if table == "interviews":
            if q.startswith("status=eq.published"):
                return [dict(i) for i in self.interviews if i["status"] == "published"]
            m = re.search(r"application_id=in\.\(([^)]*)\)", q)
            ids = m.group(1).split(",") if m else []
            return [{"status": i["status"]} for i in self.interviews if i["application_id"] in ids]
        if table == "guest_applications":
            if self._eq(q, "id"):
                return [dict(a) for a in self.apps if a["id"] == self._eq(q, "id")]
            m = re.search(r"name=ilike\.\*([^*]+)\*", q)
            if m:
                return [dict(a) for a in self.apps if m.group(1).lower() in a["name"].lower()]
            return []
        if table == "episode_records":
            iid = self._eq(q, "interview_id")
            return [dict(r) for r in self.records if r["interview_id"] == iid][:1]
        if table == "editorial_packages":
            iid = self._eq(q, "interview_id")
            return [{"transcript_cleaned": self.packages[iid]}] if iid in self.packages else []
        if table == "guest_referrals":
            rows = self.referrals
            if q.startswith("or=(status.eq.new"):
                return [dict(r) for r in rows if r["status"] == "new" or (
                    r["status"] in ("asked_recommender", "no_contact") and r.get("contact_email")
                    and not r.get("invited_at"))]
            if "asked_recommender_at=not.is.null" in q:
                iid = self._eq(q, "recommender_interview_id")
                return [r for r in rows if r["recommender_interview_id"] == iid
                        and r.get("asked_recommender_at")][:1]
            if self._eq(q, "recommender_interview_id"):
                iid = self._eq(q, "recommender_interview_id")
                return [dict(r) for r in rows if r["recommender_interview_id"] == iid]
            if q.startswith("status=in."):
                wanted = re.match(r"status=in\.\(([^)]*)\)", q).group(1).split(",")
                return [dict(r) for r in rows if r["status"] in wanted]
            if q.startswith("status=neq.skipped"):
                return [dict(r) for r in rows if r["status"] != "skipped"]
            return [dict(r) for r in rows]
        return []

    def insert(self, table, row):
        self.log.append(("insert", table, row))
        row = dict(row)
        if table == "guest_referrals":
            row.setdefault("id", f"ref-{len(self.referrals) + 1}")
            row.setdefault("created_at", _ago(0))
            row.setdefault("attempts", 0)
            self.referrals.append(row)
        elif table == "guest_applications":
            row.setdefault("id", f"app-new-{len(self.apps) + 1}")
            self.apps.append(row)
        elif table == "episode_records":
            row.setdefault("id", f"rec-{len(self.records) + 1}")
            self.records.append(row)
        return row

    def update(self, table, query, patch):
        self.log.append(("update", table, unquote(query), patch))
        rid = self._eq(unquote(query), "id")
        rows = {"guest_referrals": self.referrals, "episode_records": self.records,
                "guest_applications": self.apps}.get(table, [])
        for r in rows:
            if r["id"] == rid:
                r.update(patch)
        return [patch]


@pytest.fixture
def world(monkeypatch):
    db = FakeDB()
    sent: List[Dict[str, Any]] = []
    searched: List[str] = []
    monkeypatch.setattr(R, "sb_select", db.select)
    monkeypatch.setattr(R, "sb_insert", db.insert)
    monkeypatch.setattr(R, "sb_update", db.update)
    monkeypatch.setattr(R, "send_email", lambda to, subject, html, cc_operator=False, cc=None,
                        **kw: sent.append({"to": to, "subject": subject, "html": html,
                                           "cc_operator": cc_operator, "cc": cc or [], **kw}))
    picks = {"Vincent Rylan": VINCENT_PICKS, "Jason Fishman": JASON_PICKS}
    monkeypatch.setattr(R, "extract_picks", lambda transcript, guest, show: R.normalize_picks(picks[guest]))

    def fake_contact(ref):
        searched.append(ref["name"])
        if ref["name"] == "Geoffrey Hinton":
            return {"email": HINTON_MAIL, "via": "University of Toronto Media Relations",
                    "source": HINTON_PAGE, "route": "", "topic": "Why he left Google to speak about AI risk."}
        return {"email": "", "via": "", "source": "", "route": "", "topic": ""}

    monkeypatch.setattr(R, "find_contact", fake_contact)
    monkeypatch.setattr(R, "_summaries", lambda show: {})
    monkeypatch.setenv("PRODUCER_MODE", "auto")
    monkeypatch.setenv("CALCOM_BOOKING_URL", "https://cal.com/nerra/age-of-ai")
    return {"db": db, "sent": sent, "searched": searched}


def _guest_mail(sent):
    return [m for m in sent if m["to"] != R.OPERATOR_EMAIL]


def _report(sent):
    return [m for m in sent if m["to"] == R.OPERATOR_EMAIL]


# ---------------------------------------------------------------------------
# What is read from a transcript
# ---------------------------------------------------------------------------

class TestPicks:
    def test_the_show_s_own_people_are_never_leads(self):
        out = R.normalize_picks({"interview_next": [{"name": "Patrick Novak"}, {"name": "Dan Perra"},
                                                    {"name": "Brian Shannon", "why": "A great trader."}]})
        assert [p["name"] for p in out["interview_next"]] == ["Brian Shannon"]

    def test_an_unanswered_question_is_null_not_an_empty_card(self):
        out = R.normalize_picks({"book": {"title": "", "author": "x"}, "advice": {}, "bet": "  "})
        assert out["book"] is None and out["advice"] is None and out["bet"] is None
        assert R.normalize_picks("not json at all")["interview_next"] == []

    def test_the_closing_session_is_what_is_read(self):
        text = "x" * 20000 + "\n[Closing session]\nMira: A book?\nGuest: Zero to One."
        part = R.closing_part(text)
        assert "[Closing session]" in part and part.endswith("Zero to One.")

    def test_names_compare_without_titles(self):
        assert R.name_key("Dr. Michael Brandt") == R.name_key("michael brandt")
        assert R.first_name("Dr. Michael Brandt") == "Michael"
        assert R.name_key("Madonna") == ""

    def test_dashes_read_as_commas(self):
        out = R.normalize_picks({"bet": "We charge merchants nothing\u2014no fees at all.",
                                 "advice": {"text": "Keep going \u2014 always.", "source": ""}})
        assert out["bet"] == "We charge merchants nothing, no fees at all."
        assert out["advice"]["text"] == "Keep going, always."
        assert R._clean("2020\u20132024") == "2020\u20132024"   # a range keeps its dash

    def test_how_the_guest_knows_them_is_kept(self):
        out = R.normalize_picks({"interview_next": [{"name": "Tim Martinez", "relationship": "my co-founder"}]})
        assert out["interview_next"][0]["relationship"] == "my co-founder"
        prompt = (ROOT / "pipelines/voices/prompts/guest_picks.txt").read_text()
        assert '"relationship"' in prompt

    def test_the_prompt_forbids_invention(self):
        prompt = (ROOT / "pipelines/voices/prompts/guest_picks.txt").read_text()
        assert "Never invent" in prompt and "Patrick Novak and Dan Perra" in prompt
        assert R.MODEL == "grok-latest"


# ---------------------------------------------------------------------------
# An address is used only when it is printed where it was found
# ---------------------------------------------------------------------------

class TestContact:
    def _grok(self, monkeypatch, out):
        monkeypatch.setattr(R, "_grok", lambda prompt, web=False, max_tokens=0: json.dumps(out))

    def _page(self, monkeypatch, text, ok=True):
        class Resp:
            pass
        r = Resp()
        r.ok, r.text = ok, text
        monkeypatch.setattr(R.requests, "get", lambda url, timeout=0, headers=None: r)

    def test_an_address_on_its_page_is_used(self, monkeypatch):
        self._grok(monkeypatch, {"email": HINTON_MAIL, "source_url": HINTON_PAGE,
                                 "via": "University of Toronto Media Relations", "confidence": "high"})
        self._page(monkeypatch, f"<a href='mailto:{HINTON_MAIL}'>Media relations</a>")
        found = R.find_contact({"name": "Geoffrey Hinton", "show": "age_of_ai"})
        assert found["email"] == HINTON_MAIL and found["via"]

    def test_an_address_not_on_the_page_is_not(self, monkeypatch):
        self._grok(monkeypatch, {"email": "geoff@utoronto.ca", "source_url": HINTON_PAGE,
                                 "confidence": "high"})
        self._page(monkeypatch, f"Contact {HINTON_MAIL}")
        assert R.find_contact({"name": "Geoffrey Hinton", "show": "age_of_ai"})["email"] == ""

    def test_a_guess_is_not(self, monkeypatch):
        self._grok(monkeypatch, {"email": HINTON_MAIL, "source_url": HINTON_PAGE, "confidence": "medium"})
        self._page(monkeypatch, HINTON_MAIL)
        assert R.find_contact({"name": "Geoffrey Hinton", "show": "age_of_ai"})["email"] == ""

    def test_nor_a_page_that_cannot_be_read(self, monkeypatch):
        self._grok(monkeypatch, {"email": HINTON_MAIL, "source_url": HINTON_PAGE, "confidence": "high"})
        self._page(monkeypatch, HINTON_MAIL, ok=False)
        assert R.find_contact({"name": "Geoffrey Hinton", "show": "age_of_ai"})["email"] == ""

    def test_the_search_prompt_rules_out_guessing(self):
        prompt = (ROOT / "pipelines/voices/prompts/referral_contact.txt").read_text()
        assert "never guess" in prompt and "data broker" in prompt


# ---------------------------------------------------------------------------
# The messages
# ---------------------------------------------------------------------------

class TestMessages:
    REF = {"name": "Geoffrey Hinton", "show": "age_of_ai", "recommender_name": "Vincent Rylan",
           "why": "He understands the risk better than anyone."}
    IV = {"id": VINCENT_IV, "episode_number": 7, "show": "age_of_ai"}

    def test_the_invitation_credits_the_guest_and_points_at_everything(self, monkeypatch):
        monkeypatch.setenv("CALCOM_BOOKING_URL", "https://cal.com/nerra/age-of-ai")
        subject, html = R.render_invite(self.REF, {"via": "", "topic": "AI risk"}, self.IV)
        import html as _h
        html = _h.unescape(html)
        assert subject == "Vincent Rylan named you as my next guest on The Age of AI"
        for must in ("Hi Geoffrey,", "I'm Mira, and I'm an AI.", "no script", "Vincent Rylan",
                     "a different kind of interview", "the transcript comes first", "He understands the risk better than anyone.",
                     "https://nerranetwork.com/blog/age_of_ai/ep007.html",
                     "https://nerranetwork.com/age-of-ai.html",
                     "https://nerranetwork.com/nerra-voices.html",
                     "https://cal.com/nerra/age-of-ai", "AI risk", "Sincerely",
                     "our show on how AI is changing people's work",
                     "our show on people and the work they've chosen"):
            assert must in html, must
        assert "\u2014" not in html and "\u2014" not in subject

    def test_the_shows_come_from_the_registry_not_the_template(self):
        body = (ROOT / "templates" / "email" / "referral_invite.j2").read_text()
        assert "Age of AI" not in body and "Nerra Voices" not in body
        assert "{% for s in shows %}" in body

    def test_an_office_is_greeted_as_an_office(self):
        subject, html = R.render_invite(self.REF, {"via": "University of Toronto Media Relations"}, self.IV)
        assert "Hi There," in html and "pass this invitation on to Geoffrey Hinton" in html
        assert "Hi Geoffrey" not in html
        assert subject == "Vincent Rylan named Geoffrey Hinton as my next guest on The Age of AI"
        assert "Geoffrey Hinton also gets" in html

    def test_no_template_uses_an_em_dash(self):
        for name in ("referral_invite.j2",):
            body = (ROOT / "templates" / "email" / name).read_text()
            assert "\u2014" not in body.split("#}", 1)[1], name


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

class TestRun:
    def test_a_preview_sends_nothing_to_anyone_but_patrick(self, world):
        R.run(dry_run=True)
        assert _guest_mail(world["sent"]) == []
        report = _report(world["sent"])
        assert len(report) == 1 and report[0]["subject"].startswith("Preview:")
        html = report[0]["html"]
        assert HINTON_MAIL in html and "Tim Martinez" in html
        assert "The E-Myth" in html          # the picks, for Patrick to check
        assert world["db"].referrals == []   # no referral state from a preview

    def test_an_invitation_goes_on_the_run_that_finds_the_address(self, world):
        R.run()
        invite = next(m for m in _guest_mail(world["sent"]) if m["to"] == HINTON_MAIL)
        assert invite["cc_operator"] is True
        assert "Why he left Google" in invite["html"]       # the topic was kept
        app = next(a for a in world["db"].apps if a["name"] == "Geoffrey Hinton")
        assert app["status"] == "approved" and app["source"] == "referral"
        assert app["referrer"] == "Vincent Rylan" and app["publicist_email"] == HINTON_MAIL
        statuses = {r["name"]: r["status"] for r in world["db"].referrals}
        assert statuses == {"Geoffrey Hinton": "invited", "Tim Martinez": "no_contact"}
        world["sent"].clear()
        R.run()
        assert _guest_mail(world["sent"]) == []
        assert world["searched"].count("Geoffrey Hinton") == 1   # searched once, kept

    def test_the_guest_who_named_them_is_never_asked(self, world):
        R.run()
        R.run()
        to = [m["to"] for m in world["sent"]]
        assert "jason@example.com" not in to and "vincent@example.com" not in to
        assert "pr@example.com" not in str([m["cc"] for m in world["sent"]])
        assert not (ROOT / "templates" / "email" / "voices_referral_ask.j2").exists()
        assert not hasattr(R, "ask_recommender")

    def test_an_uncertain_name_is_still_looked_up(self, world):
        R.run()
        assert "Tim Martinez" in world["searched"]

    def test_no_address_means_no_invitation_and_a_line_for_patrick(self, world, monkeypatch):
        monkeypatch.setattr(R, "find_contact", lambda ref: (world["searched"].append(ref["name"]) or
                            {"email": "", "via": "", "source": "",
                             "route": "https://www.cs.toronto.edu/~hinton/", "topic": ""}))
        R.run()
        hinton = next(r for r in world["db"].referrals if r["name"] == "Geoffrey Hinton")
        assert hinton["status"] == "no_contact"
        assert _guest_mail(world["sent"]) == []
        report = _report(world["sent"])[-1]["html"]
        assert "Not invited: no public address found" in report and "cs.toronto.edu/~hinton" in report
        hinton["contact_email"] = HINTON_MAIL          # Patrick (or Claude) finds one
        world["sent"].clear()
        R.run()
        assert HINTON_MAIL in [m["to"] for m in world["sent"]]
        assert hinton["status"] == "invited"

    def test_it_is_marked_before_it_is_sent(self, world):
        order = []
        real_update = world["db"].update

        def update(table, query, patch):
            if table == "guest_referrals" and patch.get("status") == "invited":
                order.append("marked")
            return real_update(table, query, patch)

        R.sb_update = update
        try:
            send = R.send_email
            R.send_email = lambda to, *a, **k: (order.append(f"sent:{to}"), send(to, *a, **k))
            R.run()
        finally:
            R.sb_update = real_update
        assert order.index("marked") < order.index(f"sent:{HINTON_MAIL}")

    def test_a_held_name_never_goes(self, world):
        world["db"].referrals.append({
            "id": "ref-held", "show": "age_of_ai", "recommender_interview_id": VINCENT_IV,
            "recommender_name": "Vincent Rylan", "name": "Geoffrey Hinton", "status": "held",
            "contact_email": HINTON_MAIL, "created_at": _ago(1), "attempts": 0})
        R.run()
        assert HINTON_MAIL not in [m["to"] for m in world["sent"]]

    def test_producer_mode_off_sends_nothing(self, world, monkeypatch):
        monkeypatch.setenv("PRODUCER_MODE", "off")
        R.run()
        R.run()
        assert world["sent"] == []

    def test_someone_already_on_file_is_never_contacted(self, world):
        world["db"].apps.append({"id": "app-hinton", "name": "Geoffrey Hinton",
                                 "email": "x@example.com", "status": "approved"})
        R.run()
        hinton = next(r for r in world["db"].referrals if r["name"] == "Geoffrey Hinton")
        assert hinton["status"] == "known"
        assert "Geoffrey Hinton" not in world["searched"]

    def test_nothing_happens_until_the_guest_s_episode_is_out(self, world):
        for iv in world["db"].interviews:
            iv["status"] = "guest_review"
        R.run()
        assert world["sent"] == [] and world["db"].referrals == []

    def test_picks_are_kept_and_feed_the_page(self, world, tmp_path):
        R.run()
        assert world["db"].records[0]["picks"]["advice"]["text"] == "Write every day."
        data = R.export_page_data(tmp_path / "guest_picks.json")
        assert {e["guest"] for e in data["episodes"]} == {"Vincent Rylan", "Jason Fishman"}
        statuses = {r["name"]: r["status"] for r in data["referrals"]}
        assert statuses == {"Geoffrey Hinton": "recommended", "Tim Martinez": "recommended"}  # never "invited"
        assert json.loads((tmp_path / "guest_picks.json").read_text())["episodes"]

    def test_an_invitation_is_never_public(self, world, tmp_path):
        R.run()
        for r in world["db"].referrals:
            r["status"] = "invited"
        data = R.export_page_data(tmp_path / "g.json")
        assert {r["status"] for r in data["referrals"]} == {"recommended"}

    def test_two_rows_for_one_episode_keep_the_listed_guest(self, world, monkeypatch):
        db = world["db"]
        db.interviews = [
            {"id": "iv-test", "application_id": "app-patrick", "show": "age_of_ai", "episode_number": 2,
             "scheduled_at": "2026-07-17T20:30:00+00:00", "status": "published"},
            {"id": "iv-dan", "application_id": "app-dan", "show": "age_of_ai", "episode_number": 2,
             "scheduled_at": "2026-09-15T13:45:00+00:00", "status": "published"},
        ]
        db.apps += [{"id": "app-patrick", "name": "Patrick Novak"}, {"id": "app-dan", "name": "Dan Perra"}]
        monkeypatch.setattr(R, "_summaries", lambda show: {2: {"guest": "Dan Perra"}})
        assert [i["id"] for i in R.published_interviews()] == ["iv-dan"]


# ---------------------------------------------------------------------------
# The Producer picks up a guest's introduction
# ---------------------------------------------------------------------------

class TestIntroductions:
    def _setup(self, monkeypatch, waiting):
        from pipelines.producer import guest_reply as G
        updates = []

        def select(table, query=""):
            if table == "interviews":
                return [{"id": JASON_IV}]
            if table == "guest_referrals":
                return waiting
            return []

        monkeypatch.setattr(G, "sb_select", select)
        monkeypatch.setattr(G, "sb_update", lambda t, q, p: updates.append((t, q, p)) or [p])
        return G, updates

    def test_an_address_in_the_reply_becomes_the_contact(self, monkeypatch):
        G, updates = self._setup(monkeypatch, [{"id": "ref-1", "name": "Tim Martinez"}])
        app = {"id": "app-jason", "name": "Jason Fishman", "email": "jason@example.com"}
        inbound = {"body": "Sure! Tim is at tim@martinez.co, he'd love it.\n\nOn Oct 16 Mira wrote:\n> mira@nerranetwork.com",
                   "cc": "Patrick <patricknovak1@gmail.com>, perra.dan@gmail.com", "to": "mira@nerranetwork.com"}
        assert G.introductions(app, inbound) == ["Tim Martinez"]
        assert updates[0][2]["contact_email"] == "tim@martinez.co"
        assert updates[0][2]["contact_source"] == "introduced by Jason Fishman"

    def test_a_person_copied_in_counts(self, monkeypatch):
        G, updates = self._setup(monkeypatch, [{"id": "ref-1", "name": "Brian Shannon"}])
        app = {"id": "app-scott", "name": "Scott Pulcini", "email": "scott@example.com"}
        inbound = {"body": "Brian, meet Mira.", "cc": "Brian Shannon <brian@alphatrends.net>",
                   "to": "mira@nerranetwork.com"}
        assert G.introductions(app, inbound) == ["Brian Shannon"]
        assert updates[0][2]["contact_email"] == "brian@alphatrends.net"

    def test_with_several_asked_about_an_address_goes_only_to_its_owner(self, monkeypatch):
        G, updates = self._setup(monkeypatch, [{"id": "r1", "name": "Paige Kehoe"},
                                               {"id": "r2", "name": "Sarah Madden"}])
        app = {"id": "app-piper", "name": "Piper Martz", "email": "piper@example.com"}
        inbound = {"body": "Paige: paige@audaciousaf.com. I'll ask Sarah.", "cc": "", "to": ""}
        assert G.introductions(app, inbound) == ["Paige Kehoe"]
        assert [u[1] for u in updates] == ["id=eq.r1"]

    def test_our_own_addresses_are_not_introductions(self, monkeypatch):
        G, updates = self._setup(monkeypatch, [{"id": "ref-1", "name": "Tim Martinez"}])
        app = {"id": "app-jason", "name": "Jason Fishman", "email": "jason@example.com"}
        inbound = {"body": "Write to me at jason@example.com or patrick@planetterrian.com",
                   "cc": "mira@nerranetwork.com", "to": ""}
        assert G.introductions(app, inbound) == [] and updates == []

    def test_mira_has_a_way_to_answer_one(self):
        from pipelines.producer import guest_reply as G
        assert "introduction" in G.INTENTS and "introduction" in G.REPLY_INTENTS
        prompt = (ROOT / "pipelines/producer/prompts/guest_reply.txt").read_text()
        assert '"introduction":' in prompt and '"introduction" |' in prompt


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

PAGE_DATA = {
    "updated": "2026-10-15",
    "episodes": [
        {"show": "age_of_ai", "episode": 8, "guest": "Sameer Ranjan",
         "url": "https://nerranetwork.com/blog/age_of_ai/ep008.html", "date": "2026-09-23",
         "picks": {"book": {"title": "Zero to One", "author": "Peter Thiel", "why": "Build what is new."},
                   "advice": {"text": "Ship it <script>alert(1)</script>", "source": ""},
                   "inspiration": None, "bet": "Mines will run on agents.", "interview_next": []}},
        {"show": "nerra_voices", "episode": 3, "guest": "Scott Pulcini",
         "url": "https://nerranetwork.com/blog/nerra_voices/ep003.html", "date": "2026-10-15",
         "picks": {"book": None, "advice": {"text": "Lose your head, lose your ass.", "source": "my grandfather"},
                   "inspiration": {"who": "Brett Steenbarger", "why": ""},
                   "bet": "Trading is a performance discipline.", "interview_next": []}},
    ],
    "referrals": [
        {"name": "Brian Shannon", "organization": "AlphaTrends", "why": "The best teacher of trading.",
         "recommended_by": "Scott Pulcini", "show": "nerra_voices", "show_name": "Nerra Voices",
         "episode": 3, "episode_url": "https://nerranetwork.com/blog/nerra_voices/ep003.html",
         "status": "interviewed"},
    ],
}


class TestPage:
    def _render(self, tmp_path, data):
        import generate_html as G
        src = tmp_path / "guest_picks.json"
        src.write_text(json.dumps(data))
        out = G.generate_guest_picks_page(output_dir=tmp_path, data_path=src)
        return Path(out).read_text(encoding="utf-8")

    def test_every_kind_of_answer_is_on_it(self, tmp_path):
        html = self._render(tmp_path, PAGE_DATA)
        for must in ("Zero to One", "Peter Thiel", "Lose your head, lose your ass.", "my grandfather",
                     "Brett Steenbarger", "Mines will run on agents.",
                     "Trading is a performance discipline.", "Brian Shannon",
                     "Recommended by Scott Pulcini", "Interviewed",
                     "The bets they can&#39;t prove yet", "What they wish more people understood",
                     "age-of-ai-apply.html", "nerra-voices-apply.html", 'data-filter="nerra_voices"'):
            assert must in html, must

    def test_what_a_guest_said_cannot_inject_markup(self, tmp_path):
        html = self._render(tmp_path, PAGE_DATA)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_an_invitation_never_shows(self, tmp_path):
        html = self._render(tmp_path, PAGE_DATA)
        assert not re.search(r"\binvited\b", html, re.I)

    def test_no_data_is_a_friendly_page(self, tmp_path):
        html = self._render(tmp_path, {})
        assert "will appear here soon" in html and "Should Mira interview you" in html

    def test_both_show_pages_link_to_it(self):
        tpl = (ROOT / "templates" / "show_page.html.j2").read_text()
        assert "guest-picks.html?show={{ show_slug }}" in tpl

    def test_it_is_in_the_sitemap_and_the_static_rebuild(self):
        src = (ROOT / "generate_html.py").read_text()
        assert '"guest-picks.html"' in src
        static = src[src.index("def generate_static_pages"):src.index("def claims_page_slugs")]
        assert "generate_guest_picks_page(" in static


class TestWorkflow:
    WF = (ROOT / ".github" / "workflows" / "nerra_voices_guest_picks.yml").read_text()

    def test_daily_with_a_preview_by_hand(self):
        assert re.search(r"cron: '\d+ 17 \* \* \*'", self.WF)
        assert "dry_run:" in self.WF and "default: true" in self.WF
        assert "--dry-run" in self.WF

    def test_a_preview_publishes_nothing(self):
        commit = self.WF[self.WF.index("- name: Commit the page"):]
        assert "inputs.dry_run" in commit.split("uses:")[0]

    def test_it_has_what_it_needs(self):
        for key in ("GROK_API_KEY", "SUPABASE_SERVICE_KEY", "RESEND_API_KEY", "PRODUCER_MODE",
                    "CALCOM_BOOKING_URL_NERRA_VOICES", "guest-picks.html", "site/data/guest_picks.json"):
            assert key in self.WF, key
