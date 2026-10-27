"""Oct 16 2026, Patrick, after Meridan Zerner's interview on Oct 15.

She never opened her studio link. Nothing reached her in the last two hours
before the start, and nothing reached Patrick until the no-show email forty
minutes in, too late to call her. Two things now happen on the fire job's
five-minute ticks (pipelines/voices/fire_interviews.py):

* T-5: the guest gets a text and an email with the way in;
* T+5: if the guest still hasn't opened the studio, Patrick gets a text and
  an email with their number and a one-click "have Mira call them" link.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re
import sys
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))

import fire_interviews as F  # noqa: E402

NOW = dt.datetime(2026, 10, 15, 20, 26, 10, tzinfo=dt.timezone.utc)   # 1:26 PM Pacific
START = "2026-10-15T20:30:00+00:00"                                       # 1:30 PM Pacific


class DB:
    def __init__(self, *, start=START, run_status="staged", joined=None, phone="+12145550100",
                 call_mode="webrtc", setup_check=None, seen=None):
        self.iv = {"id": "iv-mz", "application_id": "app-mz", "show": "nerra_voices",
                   "status": "briefed", "scheduled_at": start, "call_mode": call_mode,
                   "start_notice_at": None, "late_alert_at": None, "guest_timezone": None,
                   "setup_check": setup_check, "caller_id": "+16045550000",
                   "studio_seen_at": seen}
        self.app = {"id": "app-mz", "name": "Meridan Zerner", "email": "meridan@example.com",
                    "phone": phone, "show": "nerra_voices"}
        self.run = {"id": "run-1", "status": run_status, "guest_joined_at": joined} if run_status else None
        self.updates: List[tuple] = []

    def select(self, table, query=""):
        q = unquote(query)
        if table == "interviews":
            iv = self.iv
            if iv["status"] not in re.search(r"status=in\.\(([^)]*)\)", q).group(1).split(","):
                return []
            if "call_mode=eq.webrtc" in q and iv["call_mode"] != "webrtc":
                return []
            for col in ("start_notice_at", "late_alert_at"):
                if f"{col}=is.null" in q and iv[col]:
                    return []
            lo = re.search(r"scheduled_at=gte\.([^&]+)", q).group(1)
            hi = re.search(r"scheduled_at=lte\.([^&]+)", q).group(1)
            at = F._parse(iv["scheduled_at"])
            return [dict(iv)] if F._parse(lo) <= at <= F._parse(hi) else []
        if table == "interview_runs":
            return [dict(self.run)] if self.run else []
        if table == "guest_applications":
            return [dict(self.app)]
        return []

    def update(self, table, query, patch):
        q = unquote(query)
        self.updates.append((table, q, patch))
        if table == "interviews":
            for col in ("start_notice_at", "late_alert_at"):
                if f"{col}=is.null" in q and self.iv[col]:
                    return []
            self.iv.update(patch)
            return [dict(self.iv)]
        return [patch]


@pytest.fixture
def world(monkeypatch):
    state: Dict[str, Any] = {"db": DB(), "mail": [], "sms": [], "now": NOW}

    def use(db):
        state["db"] = db
        monkeypatch.setattr(F, "sb_select", db.select)
        monkeypatch.setattr(F, "sb_update", db.update)

    use(state["db"])
    state["use"] = use
    monkeypatch.setattr(F, "_now", lambda: state["now"])
    monkeypatch.setattr(F, "send_email", lambda to, subject, html, *a, **k:
                        state["mail"].append({"to": to, "subject": subject, "html": html, **k}))
    monkeypatch.setattr(F, "notify_operator", lambda *a, **k: None)
    monkeypatch.setattr(F, "operator_phone", lambda: "+16045550199")
    from voximplant.api_clients import voximplant_client
    monkeypatch.setattr(voximplant_client, "send_sms", lambda to, text, source_number=None:
                        state["sms"].append({"to": to, "text": text, "from": source_number}) or {})
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    return state


def _at(minutes_from_start: float) -> dt.datetime:
    return F._parse(START) + dt.timedelta(minutes=minutes_from_start)


class TestFiveMinutesBefore:
    def test_the_guest_gets_a_text_and_an_email(self, world):
        world["now"] = _at(-4)
        assert F.send_start_notices() == 1
        mail = world["mail"][0]
        assert mail["to"] == "meridan@example.com"
        assert "5 minutes" in mail["subject"] and "studio is open" in mail["subject"]
        assert "interview=iv-mz" in mail["html"] and "Check my microphone" in mail["html"]
        assert "1:30 PM Pacific Time" in mail["html"]
        assert "Sincerely" in mail["html"]
        sms = world["sms"][0]
        assert sms["to"] == "+12145550100" and "about 5 minutes" in sms["text"]
        assert "interview=iv-mz" in sms["text"] and sms["from"] == "+16045550000"

    def test_only_once(self, world):
        world["now"] = _at(-4)
        F.send_start_notices()
        world["now"] = _at(-2)
        F.send_start_notices()
        assert len(world["mail"]) == 1 and len(world["sms"]) == 1

    def test_not_ten_minutes_out(self, world):
        world["now"] = _at(-9)
        assert F.send_start_notices() == 0 and world["sms"] == []

    def test_not_to_a_guest_already_in_the_room(self, world):
        world["use"](DB(run_status="in_progress", joined="2026-10-15T20:24:00+00:00"))
        world["now"] = _at(-4)
        assert F.send_start_notices() == 0 and world["mail"] == [] and world["sms"] == []

    def test_no_phone_still_gets_the_email(self, world):
        world["use"](DB(phone=None))
        world["now"] = _at(-4)
        assert F.send_start_notices() == 1
        assert world["mail"] and world["sms"] == []

    def test_a_row_still_marked_phone_gets_the_studio(self, world):
        # Oct 27 2026: phone-call interviews were retired; nobody is told
        # to expect a call.
        world["use"](DB(call_mode="pstn"))
        world["now"] = _at(-4)
        F.send_start_notices()
        assert "studio is open" in world["mail"][0]["subject"]
        assert "call you" not in world["sms"][0]["text"] and "studio" in world["sms"][0]["text"]

    def test_the_text_has_no_em_dash(self, world):
        world["now"] = _at(-4)
        F.send_start_notices()
        assert "—" not in world["sms"][0]["text"]
        assert "—" not in world["mail"][0]["html"]


class TestFiveMinutesAfter:
    def test_patrick_hears_when_the_studio_was_never_opened(self, world):
        world["now"] = _at(5.5)
        assert F.send_late_alerts() == 1
        mail = world["mail"][0]
        assert mail["to"] == F.OPERATOR_EMAIL
        assert "Meridan Zerner hasn't opened the studio" in mail["subject"]
        assert "tel:+12145550100" in mail["html"] and "meridan@example.com" in mail["html"]
        assert "Send them their studio link for their phone" in mail["html"]
        assert "/voices/admin/text-guest?interview=iv-mz" in mail["html"]
        assert "call-guest" not in mail["html"] and "by phone" not in mail["html"]
        sms = world["sms"][0]
        assert sms["to"] == "+16045550199" and "Meridan Zerner" in sms["text"]

    def test_the_phone_link_is_the_one_the_worker_checks(self, world):
        sig = hmac.new(b"test-admin-token", b"text-guest:iv-mz", hashlib.sha256).hexdigest()[:40]
        assert F.text_guest_link("iv-mz").endswith(f"interview=iv-mz&sig={sig}")
        assert "/voices/admin/text-guest?" in F.text_guest_link("iv-mz")
        worker = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text()
        assert "adminSig(env, `text-guest:${interviewId}`)" in worker
        assert ".slice(0, 40)" in worker

    def test_only_once(self, world):
        world["now"] = _at(5.5)
        F.send_late_alerts()
        world["now"] = _at(10.5)
        F.send_late_alerts()
        assert len(world["mail"]) == 1 and len(world["sms"]) == 1

    def test_not_before_the_start(self, world):
        world["now"] = _at(1)
        assert F.send_late_alerts() == 0

    def test_not_when_the_guest_is_in(self, world):
        world["use"](DB(run_status="in_progress", joined="2026-10-15T20:31:00+00:00"))
        world["now"] = _at(5.5)
        assert F.send_late_alerts() == 0 and world["mail"] == []

    def test_not_twice_when_the_page_already_raised_it(self, world):
        world["use"](DB(run_status="awaiting_guest", setup_check={"stuck_alerted_at": "2026-10-15T20:34:00Z"}))
        world["now"] = _at(5.5)
        assert F.send_late_alerts() == 0

    def test_a_row_still_marked_phone_is_alerted_like_any_other(self, world):
        # Oct 27 2026: every interview is the studio, so none is skipped.
        world["use"](DB(call_mode="pstn"))
        world["now"] = _at(5.5)
        assert F.send_late_alerts() == 1

    def test_not_while_the_page_is_open(self, world):
        # Oct 27 2026: the page polls every ten seconds and the Worker stamps
        # studio_seen_at; an open page's own stuck alert covers it.
        world["use"](DB(run_status="awaiting_guest", seen="2026-10-15T20:35:00+00:00"))
        world["now"] = _at(5.5)
        assert F.send_late_alerts() == 0

    def test_a_page_opened_once_and_closed_is_alerted(self, world):
        # A tab opened at T-10 (which turned the run awaiting_guest) and then
        # closed used to silence the alert for good.
        world["use"](DB(run_status="awaiting_guest", seen="2026-10-15T20:20:00+00:00"))
        world["now"] = _at(5.5)
        assert F.send_late_alerts() == 1


class TestWiring:
    def test_every_tick_runs_both(self):
        src = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text()
        main = src[src.index("def main() -> int:"):]
        assert "send_start_notices" in main and "send_late_alerts" in main
        assert main.index("fire_due_interviews()") < main.index("send_start_notices")

    def test_the_columns_exist(self):
        sql = (ROOT / "supabase" / "migrations" / "20261016_interview_start_alerts.sql").read_text()
        assert "start_notice_at" in sql and "late_alert_at" in sql

    def test_the_fire_job_has_what_it_needs(self):
        wf = (ROOT / ".github" / "workflows" / "nerra_voices_fire_interview.yml").read_text()
        for key in ("ADMIN_TOKEN", "OPERATOR_PHONE", "VOXIMPLANT_CALLER_ID", "RESEND_API_KEY"):
            assert key in wf, key
