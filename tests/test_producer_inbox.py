"""Nerra Producer inbox job (September 2026) — end-to-end with a fake Gmail
service, a fake Grok and an in-memory Supabase.

Pins: routing (AI pitch -> age_of_ai, everything else -> nerra_voices), the
in-thread reply shape, the guest_applications row, every hard exclusion in
shows/_producer_policy.yaml, PRODUCER_MODE semantics, the never-double-reply
rule, the plain-text template wording, the strict classification schema,
the workflow's secret wiring, and the operator rule that the Producer never
calls Grok with a version-pinned model.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.producer import classify, inbox, policy as policy_mod  # noqa: E402
from pipelines.producer.gmail_client import (  # noqa: E402
    GmailClient, build_reply_mime, parse_message,
)

OWNER = "patrick@planetterrian.com"
AGE_OF_AI_APPLY = "https://nerranetwork.com/age-of-ai-apply.html"
VOICES_APPLY = "https://nerranetwork.com/nerra-voices-apply.html"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")


def gmail_message(mid: str, thread_id: str, sender: str, body: str, subject: str,
                  ts: int, to: str = OWNER) -> Dict[str, Any]:
    return {
        "id": mid, "threadId": thread_id, "labelIds": ["INBOX"],
        "internalDate": str(ts), "snippet": body[:80],
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": sender},
                {"name": "To", "value": to},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Fri, 5 Sep 2026 09:00:00 -0700"},
                {"name": "Message-ID", "value": f"<{mid}@example.com>"},
            ],
            "body": {"data": _b64(body)},
        },
    }


class _Call:
    def __init__(self, fn, **kw):
        self._fn, self._kw = fn, kw

    def execute(self):
        return self._fn(**self._kw)


class FakeGmailService:
    """Enough of the googleapiclient resource chain for the client."""

    def __init__(self, threads: List[Dict[str, Any]]):
        self.thread_data = {t["id"]: t for t in threads}
        self.label_ids: Dict[str, str] = {"INBOX": "INBOX"}   # name -> id
        self.thread_labels: Dict[str, List[str]] = {}
        self.sent: List[Dict[str, Any]] = []
        self.drafted: List[Dict[str, Any]] = []
        self.list_queries: List[str] = []

    # resource chain --------------------------------------------------
    def users(self):
        return self

    def labels(self):
        return _Labels(self)

    def threads(self):
        return _Threads(self)

    def messages(self):
        return _Messages(self)

    def drafts(self):
        return _Drafts(self)


class _Labels:
    def __init__(self, svc):
        self.svc = svc

    def list(self, userId):
        return _Call(lambda: {"labels": [{"id": i, "name": n}
                                         for n, i in self.svc.label_ids.items()]})

    def create(self, userId, body):
        def _do():
            lid = f"Label_{len(self.svc.label_ids)}"
            self.svc.label_ids[body["name"]] = lid
            return {"id": lid, "name": body["name"]}
        return _Call(_do)


class _Threads:
    def __init__(self, svc):
        self.svc = svc

    def list(self, userId, q, maxResults, pageToken=None):
        def _do():
            self.svc.list_queries.append(q)
            processed = self.svc.label_ids.get("Producer/Processed")
            ids = [tid for tid in self.svc.thread_data
                   if not (processed and processed in self.svc.thread_labels.get(tid, []))]
            return {"threads": [{"id": t} for t in ids[:maxResults]]}
        return _Call(_do)

    def get(self, userId, id, format):
        return _Call(lambda: self.svc.thread_data[id])

    def modify(self, userId, id, body):
        def _do():
            self.svc.thread_labels.setdefault(id, []).extend(body.get("addLabelIds") or [])
            return {"id": id}
        return _Call(_do)


class _Messages:
    def __init__(self, svc):
        self.svc = svc

    def send(self, userId, body):
        def _do():
            self.svc.sent.append(body)
            return {"id": f"sent{len(self.svc.sent)}", "threadId": body.get("threadId")}
        return _Call(_do)


class _Drafts:
    def __init__(self, svc):
        self.svc = svc

    def create(self, userId, body):
        def _do():
            self.svc.drafted.append(body["message"])
            return {"id": f"draft{len(self.svc.drafted)}"}
        return _Call(_do)


def decode_raw(body: Dict[str, Any]) -> str:
    raw = body["raw"]
    raw += "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw).decode("utf-8")


def _classification(**over) -> Dict[str, Any]:
    base = {
        "category": "guest_pitch", "confidence": 0.93,
        "guest_name": "Dr. Lena Ortiz", "guest_title_org": "CTO, Fieldwork AI",
        "publicist_name": "Sam Reyes", "publicist_email": "sam@reyespr.com",
        "topic_summary": "AI agents in construction site management",
        "is_ai_related": True, "recommended_show": "age_of_ai",
        "pitched_show": "models_agents", "mentions_money_or_legal": False,
    }
    base.update(over)
    return base


class FakeDB:
    def __init__(self):
        self.applications: List[Dict[str, Any]] = []
        self.runs: List[Dict[str, Any]] = []
        self.updates: List[Any] = []

    def select(self, table, query=""):
        assert table == "guest_applications"
        tid = query.split("email_thread_id=eq.", 1)[1].split("&", 1)[0]
        return [r for r in self.applications if r.get("email_thread_id") == tid]

    def insert(self, table, row):
        if table == "guest_applications":
            assert not any(r["email_thread_id"] == row["email_thread_id"]
                           for r in self.applications), "unique index violated"
            self.applications.append(row)
            return dict(row, id=f"app{len(self.applications)}")
        self.runs.append(row)
        return dict(row, id=f"run{len(self.runs)}")

    def update(self, table, query, patch):
        self.updates.append((table, query, patch))
        return [patch]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "k")
    monkeypatch.setenv("GMAIL_DELEGATED_USER", OWNER)
    monkeypatch.delenv("PRODUCER_MODE", raising=False)
    monkeypatch.delenv("PRODUCER_MAX_SENDS", raising=False)
    policy_mod._load_yaml.cache_clear()


@pytest.fixture
def db(monkeypatch, env):
    fake = FakeDB()
    monkeypatch.setattr(inbox, "sb_select", fake.select)
    monkeypatch.setattr(inbox, "sb_insert", fake.insert)
    monkeypatch.setattr(inbox, "sb_update", fake.update)
    return fake


@pytest.fixture
def slack(monkeypatch):
    notes: List[str] = []
    monkeypatch.setattr(inbox, "notify_operator",
                        lambda text, critical=False: notes.append(text))
    return notes


@pytest.fixture
def grok(monkeypatch):
    """Fake grok_generate_text: answers by subject keyword, records calls."""
    calls: List[Dict[str, Any]] = []
    answers: Dict[str, Any] = {}

    def fake(*, prompt, **kw):
        calls.append({"prompt": prompt, **kw})
        for key, value in answers.items():
            if key in prompt:
                if callable(value):
                    value = value(len([c for c in calls if key in c["prompt"]]))
                return (value if isinstance(value, str) else json.dumps(value)), {}
        return json.dumps(_classification(category="newsletter_or_noise",
                                          is_ai_related=False)), {}

    import digests.xai_grok as xg
    monkeypatch.setattr(xg, "grok_generate_text", fake)
    fake.calls = calls  # type: ignore[attr-defined]
    fake.answers = answers  # type: ignore[attr-defined]
    return fake


def make_thread(tid: str, sender: str, subject: str, body: str,
                own_reply: bool = False) -> Dict[str, Any]:
    msgs = [gmail_message(f"{tid}m1", tid, sender, body, subject, 1000)]
    if own_reply:
        msgs.append(gmail_message(f"{tid}m2", tid, f"Patrick Novak <{OWNER}>",
                                  "Thanks, will look.", f"Re: {subject}", 2000, to=sender))
    return {"id": tid, "messages": msgs}


def run(threads, grok, answers, dry_run=False, limit=50):
    grok.answers.update(answers)
    svc = FakeGmailService(threads)
    client = GmailClient(svc, OWNER, dry_run=dry_run)
    summary = inbox.run_inbox(gmail=client, dry_run=dry_run, limit=limit)
    return svc, summary


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------

class TestGuestPitchFlow:
    def test_ai_pitch_routes_to_age_of_ai_and_replies_in_thread(self, db, slack, grok):
        t = make_thread("t1", "Sam Reyes <sam@reyespr.com>",
                        "Guest pitch: Lena Ortiz for Models & Agents",
                        "Hi Patrick, I represent Dr. Lena Ortiz...")
        svc, summary = run([t], grok, {"Lena Ortiz": _classification()})

        assert summary["sent"] == 1 and summary["drafted"] == 0
        assert summary["by_show"] == {"age_of_ai": 1}
        assert len(svc.sent) == 1 and not svc.drafted
        sent = svc.sent[0]
        assert sent["threadId"] == "t1"
        mime = decode_raw(sent)
        assert "To: Sam Reyes <sam@reyespr.com>" in mime
        assert f"From: {OWNER}" in mime
        assert "Subject: Re: Guest pitch: Lena Ortiz for Models & Agents" in mime
        assert "In-Reply-To: <t1m1@example.com>" in mime
        assert "Hi Sam," in mime
        assert "The Age of AI, our show on how AI is changing people's work" in mime
        assert AGE_OF_AI_APPLY in mime
        assert "on the Models & Agents channel" in mime
        assert "Sincerely," in mime and "Patrick" in mime
        # labelled processed
        assert svc.label_ids["Producer/Processed"] in svc.thread_labels["t1"]
        # application row
        assert len(db.applications) == 1
        row = db.applications[0]
        assert row["status"] == "invited" and row["source"] == "email"
        assert row["show"] == "age_of_ai" and row["pitched_show"] == "models_agents"
        assert row["email_thread_id"] == "t1"
        assert row["name"] == "Dr. Lena Ortiz" and row["email"] == "sam@reyespr.com"
        assert row["publicist_name"] == "Sam Reyes"
        assert row["producer_action"] == "sent"
        assert row["producer_classification"]["category"] == "guest_pitch"
        # run log + slack summary
        assert db.runs and db.runs[0]["job"] == "inbox"
        assert any("Producer inbox: 1 seen, 1 invited (age_of_ai 1 / nerra_voices 0)" in s
                   for s in slack)

    def test_non_ai_pitch_routes_to_nerra_voices(self, db, slack, grok):
        t = make_thread("t2", "Jo Park <jo@wellnesspr.com>", "Weight loss coach guest",
                        "Would love to get Coach Dana Hill on your show...")
        cls = _classification(guest_name="Dana Hill", publicist_name="Jo Park",
                              publicist_email="jo@wellnesspr.com",
                              topic_summary="weight loss coaching for busy parents",
                              is_ai_related=False, recommended_show="nerra_voices",
                              pitched_show=None)
        svc, summary = run([t], grok, {"Dana Hill": cls})
        mime = decode_raw(svc.sent[0])
        assert "Nerra Voices, our show on people and the work they've chosen" in mime
        assert VOICES_APPLY in mime
        assert "channel, since that's the audience" not in mime
        assert db.applications[0]["show"] == "nerra_voices"
        assert summary["by_show"] == {"nerra_voices": 1}

    def test_routing_rule_overrides_model_recommendation(self):
        out = classify.validate_classification(
            _classification(is_ai_related=False, recommended_show="age_of_ai"))
        assert out["recommended_show"] == "nerra_voices"
        out = classify.validate_classification(
            _classification(is_ai_related=True, recommended_show=None))
        assert out["recommended_show"] == "age_of_ai"

    def test_sponsor_mail_is_drafted_not_sent(self, db, slack, grok):
        t = make_thread("t3", "ads@sponsorco.com", "Sponsorship opportunity",
                        "We pay $2k per episode...")
        cls = _classification(category="sponsor_or_sales", guest_name=None,
                              publicist_name=None, publicist_email=None,
                              is_ai_related=False, recommended_show=None,
                              pitched_show=None, mentions_money_or_legal=True)
        svc, summary = run([t], grok, {"Sponsorship opportunity": cls})
        assert not svc.sent
        assert summary["drafted"] == 1 and summary["sent"] == 0
        assert svc.label_ids["Producer/Hold"] in svc.thread_labels["t3"]
        assert svc.label_ids["Producer/Processed"] in svc.thread_labels["t3"]
        assert any("held a thread" in s and "sponsor_or_sales" in s for s in slack)
        assert not db.applications  # nothing to invite

    def test_low_confidence_pitch_is_drafted(self, db, slack, grok):
        t = make_thread("t4", "maybe@example.org", "possible guest?", "hey")
        svc, summary = run([t], grok, {"possible guest?": _classification(confidence=0.5)})
        assert not svc.sent and len(svc.drafted) == 1
        assert svc.drafted[0]["threadId"] == "t4"
        assert AGE_OF_AI_APPLY in decode_raw(svc.drafted[0])
        assert any("confidence 0.50" in s for s in slack)
        assert db.applications[0]["producer_action"] == "drafted"

    def test_money_or_legal_pitch_is_drafted(self, db, slack, grok):
        t = make_thread("t5", "sam@reyespr.com", "Paid guest slot", "we can pay")
        svc, _ = run([t], grok, {"Paid guest slot": _classification(mentions_money_or_legal=True)})
        assert not svc.sent and len(svc.drafted) == 1

    def test_never_auto_reply_domain(self, db, slack, grok):
        t = make_thread("t6", "Podcasts <noreply@apple.com>", "A guest for you", "...")
        svc, _ = run([t], grok, {"A guest for you": _classification(publicist_email=None)})
        assert not svc.sent and len(svc.drafted) == 1
        assert any("apple.com is never auto-replied" in s for s in slack)

    def test_duplicate_thread_is_skipped(self, db, slack, grok):
        db.applications.append({"email_thread_id": "t7", "id": "x"})
        t = make_thread("t7", "sam@reyespr.com", "Lena again", "...")
        svc, summary = run([t], grok, {"Lena again": _classification()})
        assert not svc.sent and not svc.drafted
        assert summary["skipped"] == 1
        assert len(db.applications) == 1
        assert not grok.calls, "duplicates must not cost an LLM call"
        assert svc.label_ids["Producer/Processed"] in svc.thread_labels["t7"]

    def test_platform_notice_gets_label_only(self, db, slack, grok):
        t = make_thread("t8", "Spotify <no-reply@spotify.com>", "Your episode is live", "...")
        cls = _classification(category="platform_notice", guest_name=None,
                              is_ai_related=False, recommended_show=None, pitched_show=None)
        svc, summary = run([t], grok, {"Your episode is live": cls})
        assert not svc.sent and not svc.drafted and not db.applications
        assert svc.label_ids["Producer/Processed"] in svc.thread_labels["t8"]
        assert svc.label_ids.get("Producer/Hold") is None
        assert summary["skipped"] == 1
        assert not any("held" in s for s in slack)

    def test_never_double_reply(self, db, slack, grok):
        t = make_thread("t9", "sam@reyespr.com", "Lena pitch", "...", own_reply=True)
        svc, summary = run([t], grok, {"Lena pitch": _classification()})
        assert not svc.sent
        assert len(svc.drafted) == 1
        assert any("never double-reply" in s for s in slack)

    def test_followup_on_answered_thread_is_skipped(self, db, slack, grok):
        t = make_thread("t10", "sam@reyespr.com", "Re: Lena pitch", "Any update?", own_reply=True)
        t["messages"].append(gmail_message("t10m3", "t10", "sam@reyespr.com",
                                           "Any update?", "Re: Lena pitch", 3000))
        svc, summary = run([t], grok, {"Lena pitch": _classification(category="guest_followup")})
        assert not svc.sent and not svc.drafted
        assert not any("held" in s for s in slack)
        assert summary["skipped"] == 1
        assert svc.label_ids["Producer/Processed"] in svc.thread_labels["t10"]

    def test_mode_draft_only_drafts(self, db, slack, grok, monkeypatch):
        monkeypatch.setenv("PRODUCER_MODE", "draft")
        t = make_thread("t11", "sam@reyespr.com", "Lena pitch", "...")
        svc, summary = run([t], grok, {"Lena pitch": _classification()})
        assert not svc.sent and len(svc.drafted) == 1
        assert summary["mode"] == "draft"
        assert db.applications[0]["producer_action"] == "drafted"
        assert not any("held a thread" in s for s in slack)  # mode=draft is not a hold

    def test_mode_off_does_nothing_at_all(self, db, slack, grok, monkeypatch):
        monkeypatch.setenv("PRODUCER_MODE", "off")
        t = make_thread("t12", "sam@reyespr.com", "Lena pitch", "...")
        svc, summary = run([t], grok, {"Lena pitch": _classification()})
        assert summary["seen"] == 0 and summary["mode"] == "off"
        assert not svc.sent and not svc.drafted and not svc.thread_labels
        assert not svc.list_queries, "off mode must not even read Gmail"
        assert not grok.calls and not db.applications and not db.runs and not slack

    def test_dry_run_reads_but_never_writes(self, db, slack, grok):
        t = make_thread("t13", "sam@reyespr.com", "Lena pitch", "...")
        svc, summary = run([t], grok, {"Lena pitch": _classification()}, dry_run=True)
        assert summary["sent"] == 1 and grok.calls, "dry run still classifies"
        assert not svc.sent and not svc.drafted and not svc.thread_labels
        assert "Producer/Processed" not in svc.label_ids
        assert not db.applications and not db.runs and not slack

    def test_max_sends_circuit_breaker(self, db, slack, grok, monkeypatch):
        monkeypatch.setenv("PRODUCER_MAX_SENDS", "1")
        threads = [make_thread(f"t2{i}", "sam@reyespr.com", "Lena pitch", "...") for i in range(3)]
        svc, summary = run(threads, grok, {"Lena pitch": _classification()})
        # Past the cap the threads are left untouched for the next tick:
        # no draft, no label, no DB row, no Slack noise.
        assert len(svc.sent) == 1 and len(svc.drafted) == 0
        assert summary["deferred"] == 2
        assert len(db.applications) == 1
        assert not any("max_sends_per_run" in s for s in slack)
        assert sum(1 for labels in svc.thread_labels.values() for l in labels) <= 1

    def test_one_failing_thread_does_not_abort_the_run(self, db, slack, grok, monkeypatch):
        threads = [make_thread("bad", "sam@reyespr.com", "Lena pitch", "..."),
                   make_thread("good", "sam@reyespr.com", "Lena pitch", "...")]
        svc = FakeGmailService(threads)
        real_get = svc.threads().get

        def boom(userId, id, format):
            if id == "bad":
                raise RuntimeError("gmail 500")
            return real_get(userId=userId, id=id, format=format)
        monkeypatch.setattr(_Threads, "get", lambda self, userId, id, format: boom(userId, id, format))
        grok.answers["Lena pitch"] = _classification()
        summary = inbox.run_inbox(gmail=GmailClient(svc, OWNER), limit=10)
        assert summary["failed"] == 1 and summary["sent"] == 1
        assert summary["errors"][0]["thread_id"] == "bad"
        assert any("1 FAILED" in s for s in slack)

    def test_exit_code_only_when_majority_fail(self, monkeypatch):
        monkeypatch.setattr(inbox, "run_inbox",
                            lambda **kw: {"seen": 4, "failed": 3, "errors": []})
        assert inbox.main([]) == 1
        monkeypatch.setattr(inbox, "run_inbox",
                            lambda **kw: {"seen": 4, "failed": 2, "errors": []})
        assert inbox.main([]) == 0


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

class TestInviteTemplate:
    def _policy(self):
        policy_mod._load_yaml.cache_clear()
        return policy_mod.load_policy(env={})

    def test_unknown_publicist_greets_there_and_signs_patrick(self):
        text = inbox.render_invite(
            _classification(publicist_name=None, guest_name="Ana Silva",
                            is_ai_related=False, recommended_show="nerra_voices",
                            pitched_show=None),
            sender_name="Ana Silva", policy=self._policy())
        assert text.startswith("Hi There,\n\n")
        assert text.rstrip().endswith("Sincerely,\n\nPatrick")
        assert "Thanks for the note about Ana Silva." in text
        assert "Nerra Voices, our show on people and the work they've chosen." in text
        assert "—" not in text and "\n- " not in text and "•" not in text
        assert "&#39;" not in text and "&amp;" not in text, "plain text must not be HTML-escaped"

    def test_sender_display_name_used_when_publicist_unnamed(self):
        text = inbox.render_invite(_classification(publicist_name=None),
                                   sender_name="Sam Reyes", policy=self._policy())
        assert text.startswith("Hi Sam,")

    def test_exact_structure(self):
        text = inbox.render_invite(_classification(), sender_name="", policy=self._policy())
        expected = (
            "Hi Sam,\n\n"
            "Thanks for the note about Dr. Lena Ortiz. The Nerra Network's daily shows are "
            "automated news programs and don't take guests, but we do run live interviews, "
            "and I'd like to have Dr. Lena Ortiz on. Our interview host, Mira, is an AI. She "
            "calls real people and interviews them live, every episode says so plainly, and "
            "guests approve their transcript before anything publishes. I sit in on the "
            "sessions as co-host.\n\n"
            "For Dr. Lena Ortiz the right home is The Age of AI, our show on how AI is "
            "changing people's work. The fastest path is the application form at "
            f"{AGE_OF_AI_APPLY}; it takes a couple of minutes, and once I've reviewed it "
            "you'll get a booking link. I'd also feature the finished interview on the "
            "Models & Agents channel, since that's the audience you had in mind.\n\n"
            "Let me know if you have any questions.\n\n"
            "Sincerely,\n\n"
            "Patrick\n"
        )
        assert text == expected

    def test_hold_note_template_exists_and_renders(self):
        note = inbox.render_text("producer_hold_note.j2", reason="r", category="c",
                                 confidence=0.5, guest_name="G", recommended_show_name="",
                                 sender="s", subject="sub", topic_summary="t",
                                 draft_created=True, thread_url="https://mail.google.com/x")
        assert "https://mail.google.com/x" in note and "drafts" in note


# ---------------------------------------------------------------------------
# Classification schema + model rule
# ---------------------------------------------------------------------------

class TestClassify:
    @pytest.mark.parametrize("bad", [
        "not a dict",
        {},
        _classification(category="spam"),
        _classification(confidence="high"),
        _classification(confidence=1.5),
        _classification(is_ai_related="yes"),
        _classification(recommended_show="tesla"),
        _classification(pitched_show="nonexistent_show"),
        {k: v for k, v in _classification().items() if k != "topic_summary"},
    ])
    def test_validator_rejects_bad_shapes(self, bad):
        with pytest.raises(classify.ClassificationError):
            classify.validate_classification(bad)

    def test_validator_normalises(self):
        out = classify.validate_classification(_classification(
            topic_summary="x" * 500, pitched_show="Models_Agents", publicist_email="nope"))
        assert len(out["topic_summary"]) == 200
        assert out["pitched_show"] == "models_agents"
        assert out["publicist_email"] is None

    def test_prompt_file_exists_with_tokens(self):
        assert classify.PROMPT_PATH.exists()
        text = classify.PROMPT_PATH.read_text(encoding="utf-8")
        for tok in ("{{sender}}", "{{subject}}", "{{body}}", "{{daily_show_slugs}}"):
            assert tok in text
        assert "age_of_ai" in text and "nerra_voices" in text

    def test_prompt_truncates_body(self):
        t = make_thread("p", "a@b.com", "s", "x" * 10000)
        parsed = {"id": "p", "subject": "s",
                  "messages": [parse_message(m) for m in t["messages"]]}
        prompt = classify.build_prompt(parsed, OWNER)
        assert "[... truncated ...]" in prompt
        assert prompt.count("x") < 3200
        assert "{{" not in prompt

    def test_always_grok_latest_never_pinned(self, grok):
        t = make_thread("m", "a@b.com", "Lena pitch", "...")
        parsed = {"id": "m", "subject": "Lena pitch",
                  "messages": [parse_message(m) for m in t["messages"]]}
        grok.answers["Lena pitch"] = _classification()
        classify.classify_thread(parsed, OWNER)
        assert grok.calls and all(c["model"] == "grok-latest" for c in grok.calls)
        assert classify.PRODUCER_MODEL == "grok-latest"
        src = (ROOT / "pipelines" / "producer").rglob("*.py")
        import re
        for p in src:
            assert not re.search(r"grok-\d", p.read_text(encoding="utf-8")), (
                f"{p.name} references a version-pinned Grok model")

    def test_invalid_json_retries_once_then_low_confidence(self, grok):
        t = make_thread("m", "a@b.com", "Lena pitch", "...")
        parsed = {"id": "m", "subject": "Lena pitch",
                  "messages": [parse_message(m) for m in t["messages"]]}
        grok.answers["Lena pitch"] = lambda n: "garbage" if n == 1 else '{"category": "guest_pitch"}'
        out = classify.classify_thread(parsed, OWNER)
        assert len(grok.calls) == 2
        assert "not valid JSON" in grok.calls[1]["prompt"]
        assert out["confidence"] == 0.0 and out["_attempts"] == 2

    def test_fenced_json_is_accepted(self, grok):
        t = make_thread("m", "a@b.com", "Lena pitch", "...")
        parsed = {"id": "m", "subject": "Lena pitch",
                  "messages": [parse_message(m) for m in t["messages"]]}
        grok.answers["Lena pitch"] = "```json\n" + json.dumps(_classification()) + "\n```"
        assert classify.classify_thread(parsed, OWNER)["category"] == "guest_pitch"


# ---------------------------------------------------------------------------
# Policy + config
# ---------------------------------------------------------------------------

class TestPolicy:
    def test_yaml_defaults(self):
        policy_mod._load_yaml.cache_clear()
        p = policy_mod.load_policy(env={})
        assert p.mode == "auto"
        assert p.min_confidence == 0.75 and p.max_sends_per_run == 25
        for d in ("apple.com", "spotify.com", "google.com", "github.com",
                  "voximplant.com", "supabase.com", "cloudflare.com"):
            assert d in p.never_auto_reply_domains
        assert p.processed_label == "Producer/Processed"
        assert set(p.show_blurbs) == {"age_of_ai", "nerra_voices"}
        assert len(p.pitched_show_names) == 13

    def test_env_overrides_mode_and_rejects_garbage(self):
        policy_mod._load_yaml.cache_clear()
        assert policy_mod.load_policy(env={"PRODUCER_MODE": "Draft"}).mode == "draft"
        with pytest.raises(ValueError):
            policy_mod.load_policy(env={"PRODUCER_MODE": "yolo"})

    def test_subdomain_blocking(self):
        assert policy_mod.domain_blocked("mail.apple.com", ("apple.com",))
        assert not policy_mod.domain_blocked("notapple.com", ("apple.com",))


class TestGmailClient:
    def test_parse_message_html_fallback(self):
        m = gmail_message("x", "t", "A <a@b.com>", "", "s", 1)
        m["payload"] = {"mimeType": "multipart/alternative", "headers": m["payload"]["headers"],
                        "parts": [{"mimeType": "text/html",
                                   "body": {"data": _b64("<p>Hello <b>there</b></p><p>Bye &amp; thanks</p>")}}]}
        parsed = parse_message(m)
        assert parsed["body"] == "Hello there\nBye & thanks"
        assert parsed["from_email"] == "a@b.com" and parsed["from_name"] == "A"

    def test_reply_mime_threads_headers(self):
        raw = build_reply_mime(sender=OWNER, to="x@y.com", subject="Hello",
                               body_text="hi", in_reply_to="<1@x>", references="<0@x>")
        mime = decode_raw({"raw": raw})
        assert "Subject: Re: Hello" in mime
        assert "References: <0@x> <1@x>" in mime
        assert "Content-Type: text/plain" in mime

    def test_list_excludes_processed_label(self):
        svc = FakeGmailService([])
        GmailClient(svc, OWNER).list_unprocessed_threads("newer_than:30d in:inbox", 5)
        assert svc.list_queries == ["-label:Producer/Processed newer_than:30d in:inbox"]

    def test_label_created_once(self):
        svc = FakeGmailService([make_thread("t", "a@b.com", "s", "b")])
        c = GmailClient(svc, OWNER)
        c.add_label("t", "Producer/Processed")
        c.add_label("t", "Producer/Processed")
        assert list(svc.label_ids) == ["INBOX", "Producer/Processed"]


class TestWorkflow:
    def test_workflow_parses_and_wires_secrets(self):
        path = ROOT / ".github" / "workflows" / "nerra_producer_inbox.yml"
        wf = yaml.safe_load(path.read_text(encoding="utf-8"))
        on = wf.get("on") or wf.get(True)
        assert on["schedule"][0]["cron"] == "*/30 * * * *"
        assert {"dry_run", "limit"} <= set(on["workflow_dispatch"]["inputs"])
        assert wf["concurrency"]["group"] == "nerra-producer-inbox"
        step = next(s for s in wf["jobs"]["inbox"]["steps"] if "pipelines.producer.inbox" in s.get("run", ""))
        env = step["env"]
        assert env["GMAIL_SERVICE_ACCOUNT_JSON"] == "${{ secrets.GMAIL_SERVICE_ACCOUNT_JSON }}"
        assert env["GMAIL_DELEGATED_USER"] == "${{ secrets.GMAIL_DELEGATED_USER }}"
        assert env["SUPABASE_URL"] == "${{ secrets.VOICES_SUPABASE_URL }}"
        assert env["SUPABASE_SERVICE_KEY"] == "${{ secrets.VOICES_SUPABASE_SERVICE_KEY }}"
        assert env["GROK_API_KEY"] == "${{ secrets.GROK_API_KEY }}"
        assert env["SLACK_WEBHOOK"] == "${{ secrets.SLACK_WEBHOOK }}"
        assert env["PRODUCER_MODE"] == "${{ vars.PRODUCER_MODE }}"
        assert "--dry-run" in step["run"]

    def test_docs_exist(self):
        doc = (ROOT / "docs" / "nerra_producer.md").read_text(encoding="utf-8")
        assert "gmail.modify" in doc and "GMAIL_SERVICE_ACCOUNT_JSON" in doc
        assert "Producer/Processed" in doc
