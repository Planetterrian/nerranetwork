"""Nerra Producer autonomy (September 2026): follow-up replies, chase job,
daily digest, pitch-derived bio/topics/links, and the Worker/workflow
wiring that makes the inbox tick punctual.

Reuses the fakes from test_producer_inbox (Gmail service, Grok, DB).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_producer_inbox import (  # noqa: E402
    OWNER, FakeGmailService, _classification, decode_raw, db, env, gmail_message,  # noqa: F401
    grok, make_thread, slack,
)
from pipelines.producer import chase, classify, digest, followup, inbox  # noqa: E402
from pipelines.producer.gmail_client import GmailClient, parse_message  # noqa: E402
from pipelines.producer.policy import load_policy  # noqa: E402

BOOKING_AOA = "https://cal.com/patrick-novak-lkcqo4/age-of-ai-interview"
BOOKING_NV = "https://cal.com/patrick-novak-lkcqo4/nerra-voices-interview"


def _plan(**over) -> Dict[str, Any]:
    base = {"intent": "question", "confidence": 0.9,
            "reply_text": "Hi Sam,\n\nIt runs about 45 minutes, remote, from a browser.\n\nBest,\nPatrick",
            "summary": "asked about format"}
    base.update(over)
    return base


def _app(**over) -> Dict[str, Any]:
    base = {"id": "app1", "name": "Dr. Lena Ortiz", "email": "sam@reyespr.com",
            "show": "age_of_ai", "status": "invited", "source": "email",
            "pitched_show": "models_agents", "publicist_name": "Sam Reyes",
            "publicist_email": "sam@reyespr.com", "producer_followup_count": 0,
            "producer_action": "sent", "producer_acted_at": "2026-09-01T16:00:00+00:00",
            "email_thread_id": "t1"}
    base.update(over)
    return base


def replied_thread(tid="t1", reply="Yes, Lena is keen. How do we book?", subject="Re: Lena pitch"):
    t = make_thread(tid, "Sam Reyes <sam@reyespr.com>", "Lena pitch", "pitching Lena", own_reply=True)
    t["messages"].append(gmail_message(f"{tid}m3", tid, "Sam Reyes <sam@reyespr.com>",
                                       reply, subject, 3000))
    return t


@pytest.fixture
def booking(monkeypatch):
    monkeypatch.setenv("CALCOM_BOOKING_URL", BOOKING_AOA)
    monkeypatch.setenv("CALCOM_BOOKING_URL_NERRA_VOICES", BOOKING_NV)


@pytest.fixture
def fdb(monkeypatch, db):
    monkeypatch.setattr(followup, "sb_update", db.update)
    return db


# ---------------------------------------------------------------------------
# Voice guard + booking link
# ---------------------------------------------------------------------------

class TestVoice:
    def test_sign_off_is_normalised_and_em_dashes_removed(self):
        out = followup.normalise_voice("Hi Sam,\n\nIt runs 45 minutes — remote.\n\nBest regards,\nPatrick Novak")
        assert out.endswith("\n\nSincerely,\n\nPatrick\n")
        assert "—" not in out and out.count("Patrick") == 1
        assert "45 minutes, remote." in out

    def test_booking_link_is_appended_when_model_forgot_it(self):
        body = followup.normalise_voice("Hi Sam,\n\nGreat, here is how to book.")
        out = followup.ensure_booking_link(body, BOOKING_AOA)
        assert BOOKING_AOA in out and out.endswith("Sincerely,\n\nPatrick\n")
        assert out.count("Sincerely") == 1
        # Present already → untouched.
        assert followup.ensure_booking_link(out, BOOKING_AOA) == out

    def test_booking_url_per_show(self, booking):
        assert followup.booking_url("age_of_ai") == BOOKING_AOA
        assert followup.booking_url("nerra_voices") == BOOKING_NV

    def test_booking_url_falls_back(self, monkeypatch):
        monkeypatch.setenv("CALCOM_BOOKING_URL", BOOKING_AOA)
        monkeypatch.delenv("CALCOM_BOOKING_URL_NERRA_VOICES", raising=False)
        assert followup.booking_url("nerra_voices") == BOOKING_AOA


# ---------------------------------------------------------------------------
# Decision (pure)
# ---------------------------------------------------------------------------

class TestFollowupDecision:
    def test_ready_to_book_sends_and_approves(self):
        d = followup.decide_followup(_plan(intent="ready_to_book"), _app(), mode="auto", inbound_auto=False)
        assert d["action"] == "send" and d["status_patch"] == {"status": "approved"}

    def test_decline_closes_row(self):
        d = followup.decide_followup(_plan(intent="decline"), _app(), mode="auto", inbound_auto=False)
        assert d["action"] == "send"
        assert d["status_patch"]["status"] == "declined"
        assert d["status_patch"]["producer_closed_reason"] == "declined"

    def test_later_pushes_the_chase_clock(self):
        d = followup.decide_followup(_plan(intent="later"), _app(), mode="auto", inbound_auto=False)
        assert d["action"] == "send" and "chased_at" in d["status_patch"]

    def test_needs_patrick_drafts(self):
        d = followup.decide_followup(_plan(intent="needs_patrick", reply_text=None), _app(),
                                     mode="auto", inbound_auto=False)
        assert d["action"] == "draft"

    def test_low_confidence_drafts(self):
        d = followup.decide_followup(_plan(confidence=0.5), _app(), mode="auto", inbound_auto=False)
        assert d["action"] == "draft" and "0.50" in d["reason"]

    def test_autoresponder_only_labels(self):
        d = followup.decide_followup(_plan(), _app(), mode="auto", inbound_auto=True)
        assert d["action"] == "label"
        d = followup.decide_followup(_plan(intent="auto_reply", reply_text=None), _app(),
                                     mode="auto", inbound_auto=False)
        assert d["action"] == "label"

    def test_cap_after_four_replies(self):
        d = followup.decide_followup(_plan(), _app(producer_followup_count=4), mode="auto", inbound_auto=False)
        assert d["action"] == "draft" and "4 Producer replies" in d["reason"]

    def test_draft_mode_never_sends(self):
        d = followup.decide_followup(_plan(intent="ready_to_book"), _app(), mode="draft", inbound_auto=False)
        assert d["action"] == "draft"

    def test_declined_row_reopen_needs_patrick_unless_booking(self):
        d = followup.decide_followup(_plan(intent="question"), _app(status="declined"),
                                     mode="auto", inbound_auto=False)
        assert d["action"] == "draft"
        d = followup.decide_followup(_plan(intent="ready_to_book"), _app(status="lapsed"),
                                     mode="auto", inbound_auto=False)
        assert d["action"] == "send" and d["status_patch"]["status"] == "approved"


class TestFollowupSchema:
    def test_validate_accepts_and_trims(self):
        out = followup.validate_followup({"intent": "question", "confidence": 0.8,
                                          "reply_text": "  Hi  ", "summary": "x " * 200})
        assert out["reply_text"] == "Hi" and len(out["summary"]) <= 160

    @pytest.mark.parametrize("bad", [
        {"intent": "book", "confidence": 0.8, "reply_text": "x", "summary": "s"},
        {"intent": "question", "confidence": 1.5, "reply_text": "x", "summary": "s"},
        {"intent": "question", "confidence": 0.8, "reply_text": None, "summary": "s"},
        {"intent": "question", "confidence": 0.8, "reply_text": "x"},
        [],
    ])
    def test_validate_rejects(self, bad):
        with pytest.raises(followup.FollowupError):
            followup.validate_followup(bad)

    def test_prompt_carries_facts_and_thread(self, booking):
        t = GmailClient(FakeGmailService([replied_thread()]), OWNER).get_thread("t1")
        p = followup.build_prompt(t, _app(), OWNER, load_policy())
        assert BOOKING_AOA in p and "The Age of AI" in p and "Models & Agents" in p
        assert "OURS (Patrick)" in p and "How do we book?" in p
        assert "{{" not in p and "{%" not in p
        assert "no fee" in p.lower() and "Sincerely," in p

    def test_prompt_without_pitched_show(self, booking):
        t = GmailClient(FakeGmailService([replied_thread()]), OWNER).get_thread("t1")
        p = followup.build_prompt(t, _app(pitched_show=None), OWNER, load_policy())
        assert "featured on the" not in p and "{%" not in p

    def test_quoted_history_is_stripped(self):
        body = "Sounds good.\n\nOn Fri, Sep 5, 2026 at 9:00 AM Patrick Novak <p@x.com> wrote:\n> long quote\n> more"
        assert followup._strip_quoted(body) == "Sounds good."
        assert followup._strip_quoted("> only quote\nreal line") == "real line"


# ---------------------------------------------------------------------------
# End to end through the inbox job
# ---------------------------------------------------------------------------

def _run(threads, grok, answers, dry_run=False):
    grok.answers.update(answers)
    svc = FakeGmailService(threads)
    client = GmailClient(svc, OWNER, dry_run=dry_run)
    return svc, inbox.run_inbox(gmail=client, dry_run=dry_run, limit=50)


class TestFollowupFlow:
    def test_yes_reply_gets_booking_link_and_approval(self, fdb, slack, grok, booking):
        fdb.applications.append(_app())
        t = replied_thread()
        plan = _plan(intent="ready_to_book",
                     reply_text="Hi Sam,\n\nWonderful. Lena can pick a time here:\n" + BOOKING_AOA +
                                "\n\nPlease book with her own email.\n\nSincerely,\n\nPatrick")
        svc, summary = _run([t], grok, {"THREAD (oldest first": plan})
        assert len(svc.sent) == 1 and not svc.drafted
        text = decode_raw(svc.sent[0])
        assert BOOKING_AOA in text and text.rstrip().endswith("Sincerely,\n\nPatrick")
        assert "In-Reply-To: <t1m3@example.com>" in text
        assert summary["followups_sent"] == 1 and summary["approved"] == 1 and summary["sent"] == 0
        (_, q, patch), = [u for u in fdb.updates if u[0] == "guest_applications"]
        assert q == "id=eq.app1" and patch["status"] == "approved"
        assert patch["producer_followup_count"] == 1 and patch["producer_action"] == "followup_sent"
        assert svc.label_ids["Producer/Processed"] in svc.thread_labels["t1"]
        assert len(fdb.applications) == 1, "no second row for the same thread"
        # The classifier was never called — only the follow-up planner.
        assert all("THREAD (oldest first" in c["prompt"] for c in grok.calls)

    def test_question_is_answered_in_thread(self, fdb, slack, grok, booking):
        fdb.applications.append(_app())
        t = replied_thread(reply="Is there a fee for guests?")
        svc, summary = _run([t], grok, {"THREAD (oldest first": _plan(
            reply_text="Hi Sam,\n\nNo fee either way.\n\nBest,\nPatrick")})
        assert len(svc.sent) == 1
        assert "No fee either way." in decode_raw(svc.sent[0])
        patch = [u for u in fdb.updates if u[0] == "guest_applications"][-1][2]
        assert "status" not in patch and patch["producer_followup_count"] == 1

    def test_needs_patrick_is_drafted_and_held(self, fdb, slack, grok, booking):
        fdb.applications.append(_app())
        t = replied_thread(reply="We'd need a $2,000 appearance fee.")
        svc, summary = _run([t], grok, {"THREAD (oldest first": _plan(
            intent="needs_patrick", reply_text=None, summary="asks for a fee")})
        assert not svc.sent and not svc.drafted  # nothing to draft without text
        assert svc.label_ids["Producer/Hold"] in svc.thread_labels["t1"]
        assert summary["followups_held"] == 1
        patch = [u for u in fdb.updates if u[0] == "guest_applications"][-1][2]
        assert patch["producer_action"] == "followup_held"

    def test_out_of_office_is_ignored(self, fdb, slack, grok, booking):
        fdb.applications.append(_app())
        t = replied_thread(reply="I am away until Sept 20.", subject="Automatic reply: Lena pitch")
        svc, summary = _run([t], grok, {})
        assert not svc.sent and not svc.drafted and not grok.calls
        assert svc.label_ids["Producer/Processed"] in svc.thread_labels["t1"]
        assert summary.get("followups_sent", 0) == 0 and summary.get("followups_held", 0) == 0

    def test_drafted_invite_never_treated_as_followup(self, fdb, slack, grok, booking):
        # Row exists (held draft) but we never wrote in the thread → old skip path.
        fdb.applications.append(_app(producer_action="drafted"))
        t = make_thread("t1", "sam@reyespr.com", "Lena pitch", "pitching Lena")
        svc, summary = _run([t], grok, {})
        assert not svc.sent and not svc.drafted and not grok.calls
        assert summary["skipped"] == 1

    def test_form_sourced_row_is_left_alone(self, fdb, slack, grok, booking):
        fdb.applications.append(_app(source="form"))
        svc, summary = _run([replied_thread()], grok, {})
        assert not svc.sent and not grok.calls and summary["skipped"] == 1

    def test_invalid_model_output_holds(self, fdb, slack, grok, booking):
        fdb.applications.append(_app())
        svc, summary = _run([replied_thread()], grok, {"THREAD (oldest first": "not json"})
        assert not svc.sent and summary["followups_held"] == 1
        assert len(grok.calls) == 2  # one strict retry

    def test_dry_run_writes_nothing(self, fdb, slack, grok, booking):
        fdb.applications.append(_app())
        svc, summary = _run([replied_thread()], grok,
                            {"THREAD (oldest first": _plan(intent="ready_to_book",
                                                           reply_text="Hi Sam,\n\nBook here.\n\nSincerely,\n\nPatrick")},
                            dry_run=True)
        assert not svc.sent and not fdb.updates and not svc.thread_labels


# ---------------------------------------------------------------------------
# Pitch-derived application fields
# ---------------------------------------------------------------------------

class TestPitchFields:
    def test_bio_topics_links_are_validated(self):
        obj = _classification(bio="Lena runs Fieldwork AI.  She built X.",
                              topics=["Agents on site", "Agents on site", "", 7],
                              links=["https://fieldwork.ai", "http://x.com/unsubscribe?u=1",
                                     "javascript:alert(1)", "https://linkedin.com/in/lena"])
        out = classify.validate_classification(obj)
        assert out["bio"] == "Lena runs Fieldwork AI. She built X."
        assert out["topics"] == ["Agents on site"]
        assert out["links"] == ["https://fieldwork.ai", "https://linkedin.com/in/lena"]

    def test_missing_fields_tolerated(self):
        out = classify.validate_classification(_classification())
        assert out["bio"] is None and out["topics"] == [] and out["links"] == []

    def test_row_carries_them(self, db, slack, grok):
        t = make_thread("t2", "sam@reyespr.com", "Lena pitch", "pitching Lena")
        svc, _ = _run([t], grok, {"Lena pitch": _classification(
            bio="Lena runs Fieldwork AI.", topics=["Agents on site"], links=["https://fieldwork.ai"])})
        row = db.applications[0]
        assert row["bio"] == "Lena runs Fieldwork AI."
        assert row["topics"] == ["Agents on site"]
        assert row["links"] == {"urls": ["https://fieldwork.ai"]}
        assert "reply to this email and I'll send a booking link" in decode_raw(svc.sent[0])

    def test_prompt_asks_for_them(self):
        text = classify.PROMPT_PATH.read_text()
        assert '"bio": string or null' in text and '"topics": array' in text and '"links": array' in text


class TestAutoSubmitted:
    def test_header_and_subject_detection(self):
        m = gmail_message("m", "t", "a@b.com", "away", "Automatic reply: hi", 1)
        assert parse_message(m)["auto_submitted"] is True
        m = gmail_message("m", "t", "a@b.com", "hi", "Re: hi", 1)
        m["payload"]["headers"].append({"name": "Auto-Submitted", "value": "auto-replied"})
        assert parse_message(m)["auto_submitted"] is True
        m = gmail_message("m", "t", "a@b.com", "hi", "Re: hi", 1)
        assert parse_message(m)["auto_submitted"] is False


# ---------------------------------------------------------------------------
# Chase job
# ---------------------------------------------------------------------------

NOW = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)


def _days_ago(n: float) -> str:
    return (NOW - timedelta(days=n)).isoformat()


class TestChaseTiming:
    def test_schedule(self):
        assert chase.next_step(_app(producer_acted_at=_days_ago(4)), NOW) is None
        assert chase.next_step(_app(producer_acted_at=_days_ago(5)), NOW) == "chase1"
        assert chase.next_step(_app(producer_acted_at=_days_ago(30), chase_count=1,
                                    chased_at=_days_ago(6)), NOW) is None
        assert chase.next_step(_app(producer_acted_at=_days_ago(30), chase_count=1,
                                    chased_at=_days_ago(7)), NOW) == "chase2"
        assert chase.next_step(_app(chase_count=2, chased_at=_days_ago(9)), NOW) is None
        assert chase.next_step(_app(chase_count=2, chased_at=_days_ago(10)), NOW) == "lapse"

    def test_only_sent_email_invites(self):
        assert chase.next_step(_app(producer_action="drafted", producer_acted_at=_days_ago(9)), NOW) is None
        assert chase.next_step(_app(source="form", producer_acted_at=_days_ago(9)), NOW) is None
        assert chase.next_step(_app(status="approved", producer_acted_at=_days_ago(9)), NOW) is None

    def test_reply_after_our_last_message_stops_the_chase(self):
        app = _app(producer_acted_at=_days_ago(9), producer_last_inbound_at=_days_ago(8))
        assert chase.next_step(app, NOW) is None
        # ...but a reply we already answered restarts the clock from our answer.
        app = _app(producer_acted_at=_days_ago(20), producer_last_inbound_at=_days_ago(8),
                   producer_last_outbound_at=_days_ago(6))
        assert chase.next_step(app, NOW) == "chase1"

    def test_later_intent_waits_a_full_cycle(self):
        app = _app(producer_acted_at=_days_ago(20), producer_last_inbound_at=_days_ago(3),
                   chased_at=_days_ago(3))
        assert chase.next_step(app, NOW) is None


class TestChaseRun:
    @pytest.fixture
    def cdb(self, monkeypatch, env):
        class DB:
            def __init__(self):
                self.rows: List[Dict[str, Any]] = []
                self.updates: List[Any] = []
                self.runs: List[Dict[str, Any]] = []

            def select(self, table, query=""):
                assert table == "guest_applications"
                return list(self.rows)

            def insert(self, table, row):
                self.runs.append(row)
                return dict(row, id="run1")

            def update(self, table, query, patch):
                self.updates.append((table, query, patch))
                return [patch]
        d = DB()
        monkeypatch.setattr(chase, "sb_select", d.select)
        monkeypatch.setattr(chase, "sb_insert", d.insert)
        monkeypatch.setattr(chase, "sb_update", d.update)
        monkeypatch.setattr(chase, "_now", lambda: NOW)
        return d

    def test_first_nudge_goes_in_thread(self, cdb):
        cdb.rows.append(_app(producer_acted_at=_days_ago(6)))
        t = make_thread("t1", "Sam Reyes <sam@reyespr.com>", "Lena pitch", "pitching", own_reply=True)
        svc = FakeGmailService([t])
        summary = chase.run_chase(gmail=GmailClient(svc, OWNER), policy=load_policy())
        assert summary["sent"] == 1 and len(svc.sent) == 1
        text = decode_raw(svc.sent[0])
        assert "Hi Sam," in text and "Dr. Lena Ortiz joining The Age of AI" in text
        assert text.rstrip().endswith("Sincerely,\n\nPatrick")
        assert "In-Reply-To: <t1m2@example.com>" in text
        assert svc.sent[0]["threadId"] == "t1"
        patch = [u for u in cdb.updates if u[0] == "guest_applications"][-1][2]
        assert patch["chase_count"] == 1 and patch["producer_action"] == "chase_sent"
        assert cdb.runs[0]["job"] == "chase"

    def test_second_nudge_wording(self, cdb):
        cdb.rows.append(_app(producer_acted_at=_days_ago(30), chase_count=1, chased_at=_days_ago(8),
                             show="nerra_voices"))
        t = make_thread("t1", "Sam Reyes <sam@reyespr.com>", "Lena pitch", "pitching", own_reply=True)
        svc = FakeGmailService([t])
        chase.run_chase(gmail=GmailClient(svc, OWNER), policy=load_policy())
        text = decode_raw(svc.sent[0])
        assert "One last note" in text and "Nerra Voices" in text
        assert [u for u in cdb.updates if u[0] == "guest_applications"][-1][2]["chase_count"] == 2

    def test_lapse_writes_status_only(self, cdb):
        cdb.rows.append(_app(chase_count=2, chased_at=_days_ago(11)))
        t = make_thread("t1", "sam@reyespr.com", "Lena pitch", "pitching", own_reply=True)
        svc = FakeGmailService([t])
        summary = chase.run_chase(gmail=GmailClient(svc, OWNER), policy=load_policy())
        assert summary["lapsed"] == 1 and not svc.sent
        app_updates = [u for u in cdb.updates if u[0] == "guest_applications"]
        assert app_updates[-1][2] == {"status": "lapsed", "producer_closed_reason": "no_reply",
                                      "producer_acted_at": NOW.isoformat()}

    def test_unprocessed_reply_in_thread_blocks_the_nudge(self, cdb):
        cdb.rows.append(_app(producer_acted_at=_days_ago(6)))
        t = replied_thread()
        svc = FakeGmailService([t])
        summary = chase.run_chase(gmail=GmailClient(svc, OWNER), policy=load_policy())
        assert not svc.sent and summary["sent"] == 0
        assert not [u for u in cdb.updates if u[0] == "guest_applications"]

    def test_draft_mode_drafts(self, cdb, monkeypatch):
        monkeypatch.setenv("PRODUCER_MODE", "draft")
        cdb.rows.append(_app(producer_acted_at=_days_ago(6)))
        t = make_thread("t1", "sam@reyespr.com", "Lena pitch", "pitching", own_reply=True)
        svc = FakeGmailService([t])
        summary = chase.run_chase(gmail=GmailClient(svc, OWNER), policy=load_policy())
        assert summary["drafted"] == 1 and len(svc.drafted) == 1 and not svc.sent

    def test_dry_run(self, cdb):
        cdb.rows.append(_app(producer_acted_at=_days_ago(6)))
        t = make_thread("t1", "sam@reyespr.com", "Lena pitch", "pitching", own_reply=True)
        svc = FakeGmailService([t])
        chase.run_chase(gmail=GmailClient(svc, OWNER, dry_run=True), policy=load_policy(), dry_run=True)
        assert not svc.sent and not cdb.updates and not cdb.runs


# ---------------------------------------------------------------------------
# Daily digest
# ---------------------------------------------------------------------------

class TestDigest:
    @pytest.fixture
    def ddb(self, monkeypatch, env):
        runs = [{
            "job": "inbox", "started_at": "2026-09-06T15:00:00+00:00", "errors": [
                {"thread_id": "tX", "error": "HttpError: 429"}],
            "notes": json.dumps({"summary": {}, "decisions": [
                {"thread_id": "t1", "kind": "followup", "action": "send", "intent": "ready_to_book",
                 "guest_name": "Dr. Lena Ortiz", "subject": "Re: Lena pitch"},
                {"thread_id": "t2", "action": "draft", "reason": "confidence 0.40 < 0.50",
                 "guest_name": "Bob", "subject": "possible guest?", "from": "maybe@example.org"},
            ]}),
        }, {
            "job": "chase", "started_at": "2026-09-06T16:00:00+00:00", "errors": None,
            "notes": json.dumps({"summary": {}, "decisions": [
                {"application_id": "a3", "action": "sent", "step": "chase1"},
                {"application_id": "a4", "action": "lapse", "step": "lapse"},
            ]}),
        }]
        apps = [
            {"id": "a1", "name": "Dr. Lena Ortiz", "show": "age_of_ai", "status": "approved",
             "producer_action": "followup_sent", "email_thread_id": "t1"},
            {"id": "a5", "name": "New Person", "show": "nerra_voices", "status": "invited",
             "producer_action": "sent", "pitched_show": "planetterrian", "email_thread_id": "t5"},
        ]
        booked = [{"id": "i1", "scheduled_at": "2026-09-10T17:00:00+00:00", "show": "age_of_ai",
                   "guest_applications": {"name": "Dr. Lena Ortiz"}}]

        def select(table, query=""):
            if table == "producer_runs":
                return runs
            if table == "interviews":
                return booked if "created_at" in query else [{"id": "i1"}, {"id": "i2"}]
            if "producer_acted_at" in query:
                return apps
            return [{"id": "x"}] * (3 if "invited" in query else 1)
        sent: List[Any] = []
        monkeypatch.setattr(digest, "sb_select", select)
        monkeypatch.setattr(digest, "sb_insert", lambda t, r: dict(r, id="r"))
        monkeypatch.setattr(digest, "send_email", lambda to, subject, html: sent.append((to, subject, html)))
        return sent

    def test_digest_content_and_recipient(self, ddb):
        out = digest.run_digest(hours=24)
        (to, subject, html), = ddb
        assert to == "patricknovak1@gmail.com"
        assert subject == "Nerra Producer daily: 1 invited, 1 booking links, 1 booked, 1 waiting on you, 1 errors"
        assert "Waiting on you (1)" in html and "possible guest?" in html
        assert "https://mail.google.com/mail/u/0/#all/t2" in html
        assert "Dr. Lena Ortiz" in html and "2026-09-10 17:00 UTC" in html
        assert "New Person" in html and "pitched planetterrian" in html
        assert "HttpError: 429" in html
        assert "3 invited and waiting, 1 approved and not yet booked, 2 interviews scheduled" in html
        assert "Nudges sent</td><td" in html
        s = out["stats"]
        assert s["chased"] == 1 and s["lapsed"] == 1 and s["followups"] == 1

    def test_html_escapes(self, ddb, monkeypatch):
        html = digest.render({"stats": {k: 0 for k in ("invited", "followups", "approved", "booked",
                                                       "chased", "lapsed", "held", "errors", "runs",
                                                       "invited_total", "approved_total", "scheduled_total")},
                              "invited": [], "approved": [], "booked": [],
                              "held": [{"subject": "<script>x</script>", "guest": "", "sender": "s",
                                        "reason": "r", "url": "u"}],
                              "errors": [], "until": NOW})
        assert "<script>" not in html and "&lt;script&gt;" in html

    def test_dry_run_sends_nothing(self, ddb):
        digest.run_digest(hours=24, dry_run=True)
        assert not ddb


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

class TestWiring:
    def test_worker_dispatches_producer_tick(self):
        ts = (ROOT / "workers/voices/src/index.ts").read_text()
        assert 'event.cron === "*/30 * * * *"' in ts
        assert 'dispatch(env, "producer-tick"' in ts
        toml = (ROOT / "workers/voices/wrangler.toml").read_text()
        assert '"*/30 * * * *"' in toml
        assert 'producer_tick: "*/30 * * * * -> repository_dispatch producer-tick"' in ts

    def test_worker_matches_publicist_email_on_booking(self):
        ts = (ROOT / "workers/voices/src/index.ts").read_text()
        assert "publicist_email.eq." in ts
        assert "matched ${emailAddr} via publicist_email" in ts

    def test_inbox_workflow_listens_and_has_booking_urls(self):
        wf = yaml.safe_load((ROOT / ".github/workflows/nerra_producer_inbox.yml").read_text())
        assert wf[True]["repository_dispatch"]["types"] == ["producer-tick"]
        env = wf["jobs"]["inbox"]["steps"][-1]["env"]
        assert env["CALCOM_BOOKING_URL"] == "${{ secrets.CALCOM_BOOKING_URL }}"
        assert env["CALCOM_BOOKING_URL_NERRA_VOICES"] == "${{ secrets.CALCOM_BOOKING_URL_NERRA_VOICES }}"

    def test_daily_workflow(self):
        wf = yaml.safe_load((ROOT / ".github/workflows/nerra_producer_daily.yml").read_text())
        assert wf[True]["schedule"] == [{"cron": "0 1 * * *"}]
        steps = {s["name"]: s for s in wf["jobs"]["daily"]["steps"] if "name" in s}
        chase_step = steps["Chase invites with no reply"]
        assert "pipelines.producer.chase" in chase_step["run"]
        assert chase_step["env"]["GMAIL_SERVICE_ACCOUNT_JSON"] == "${{ secrets.GMAIL_SERVICE_ACCOUNT_JSON }}"
        dig = steps["Daily summary email"]
        assert "pipelines.producer.digest" in dig["run"]
        assert dig["env"]["OPERATOR_EMAIL"] == "patricknovak1@gmail.com"
        assert dig["env"]["RESEND_API_KEY"] == "${{ secrets.RESEND_API_KEY }}"
        assert dig["if"] == "${{ always() }}"
        assert wf["concurrency"]["group"] == "nerra-producer-inbox"

    def test_policy_gate_lowered(self):
        pol = yaml.safe_load((ROOT / "shows/_producer_policy.yaml").read_text())
        assert pol["min_confidence"] == 0.5
        assert pol["inbox_query"] == "newer_than:45d in:inbox"

    def test_migration_columns(self):
        sql = (ROOT / "supabase/migrations/20260907_producer_autonomy.sql").read_text()
        for col in ("producer_followup_count", "producer_last_inbound_at", "producer_last_outbound_at",
                    "chase_count", "chased_at", "producer_closed_reason"):
            assert f"add column if not exists {col}" in sql

    def test_followup_model_is_grok_latest(self):
        src = (ROOT / "pipelines/producer/followup.py").read_text()
        assert "_classify.PRODUCER_MODEL" in src
        assert not re.search(r"grok-\d", src)
