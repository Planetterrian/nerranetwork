"""Oct 8 2026 (Patrick). Two asks about guest mail.

1. Dan Perra is copied on guest correspondence, and a guest's publicist on
   the mail about their booking and their episode. Scott Pulcini's publicist
   booked him and never saw his review link.
2. Booking mail says, in a line, what the interview is about, for the guest
   and in what Patrick receives.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT))
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")


def _block(src: str, start: str, end: str = "miraSignature(show)") -> str:
    i = src.index(start)
    return src[i:src.index(end, i) + 200]


class TestTheSubjectLine:
    def test_the_guest_reads_their_own_topics(self):
        from common import interview_subject
        app = {"topics": ["Moving past the hype", "People over tools", "Agentic systems", "Fourth"],
               "pitch_summary": "Jon on AI adoption"}
        iv = {"episode_thesis": "A founder who built his firm in a weekend."}
        assert interview_subject(iv, app, for_guest=True) == \
            "Moving past the hype; People over tools; Agentic systems"

    def test_patrick_reads_the_thesis_first(self):
        from common import interview_subject
        app = {"topics": ["Moving past the hype"], "pitch_summary": "Jon on AI adoption"}
        iv = {"episode_thesis": "A founder who built his firm in a weekend."}
        assert interview_subject(iv, app, for_guest=False) == \
            "A founder who built his firm in a weekend."
        assert interview_subject({}, app, for_guest=False) == "Jon on AI adoption"

    def test_odd_shapes_do_not_leak_into_mail(self):
        from common import interview_subject
        assert interview_subject(None, {"topics": '["a", "b"]'}) == "a; b"
        assert interview_subject(None, {"topics": ["[object Object]"]}) == ""
        assert interview_subject(None, None) == ""

    def test_a_long_one_is_cut_on_a_word(self):
        from common import interview_subject
        out = interview_subject(None, {"pitch_summary": "word " * 120}, limit=50)
        assert len(out) <= 51 and out.endswith("…") and "  " not in out


class TestWhoIsCopied:
    def _capture(self, monkeypatch):
        import common
        sent = []

        class R:
            status_code = 200
            text = "{}"

            def raise_for_status(self):
                return None

            def json(self):
                return {}
        monkeypatch.setenv("RESEND_API_KEY", "x")
        monkeypatch.setattr(common.requests, "post",
                            lambda url, headers=None, json=None, timeout=None: sent.append(json) or R())
        return common, sent

    def test_guest_mail_copies_dan(self, monkeypatch):
        common, sent = self._capture(monkeypatch)
        common.send_email("guest@example.com", "s", "<p>x</p>", cc_operator=True,
                          cc=["pub@example.com"])
        cc = [c.lower() for c in sent[-1]["cc"]]
        assert "perra.dan@gmail.com" in cc and "pub@example.com" in cc
        assert common.OPERATOR_EMAIL.lower() in cc

    def test_the_producers_pitch_threads_do_not(self, monkeypatch):
        common, sent = self._capture(monkeypatch)
        common.send_email("publicist@example.com", "s", "", cc_operator=True,
                          text_body="hi", cc_guest_team=False)
        assert "perra.dan@gmail.com" not in [c.lower() for c in sent[-1].get("cc", [])]
        assert "cc_guest_team=False" in (ROOT / "pipelines" / "producer" / "mira_mail.py").read_text()

    def test_the_worker_copies_the_guest_team_with_patrick(self):
        assert 'env.GUEST_CC ?? "perra.dan@gmail.com"' in WORKER
        assert "[...operatorCc(env), ...guestTeamCc(env)]" in WORKER

    def test_the_publicist_sees_the_review_link_and_the_booking(self):
        review = _block(WORKER, "your ${show.shortLabel} episode is ready for you")
        assert "true, publicistCc(app));" in review
        reminder = _block(WORKER, "episode is waiting for you")
        assert "publicistCc(app)" in reminder
        booked = _block(WORKER, "You're booked on ${show.name}", "return json({ ok: true, show: show.slug, interview_id: interviewId })")
        assert "publicistCc(apps[0])" in booked
        for start in ("Moved: our interview on", "Our interview on ${show.name} is coming up"):
            assert "publicistCc(app)" in _block(WORKER, start)
        assert 'cc=[str(app.get("publicist_email") or "")]' in (V / "generate_briefs.py").read_text()


class TestBookingMailSaysWhatItIsAbout:
    def test_the_guest_mail(self):
        assert "subjectHtml(interviewSubject(null, apps[0], true))" in \
            _block(WORKER, "You're booked on ${show.name}")
        assert "subjectHtml(interviewSubject(iv, app, true))" in _block(WORKER, "Moved: our interview on")
        assert "subjectHtml(interviewSubject(iv, app, true))" in \
            _block(WORKER, "Our interview on ${show.name} is coming up")

    def test_what_patrick_receives(self):
        assert 'subjectHtml(interviewSubject(iv, app, false), "The interview")' in WORKER
        digest = (ROOT / "pipelines" / "producer" / "digest.py").read_text()
        assert '"subject": interview_subject(b, app, for_guest=False' in digest
        assert "{{ b.subject }}" in (ROOT / "templates" / "email" / "producer_daily_digest.j2").read_text()
        assert 'f"{_subject_line(interview, app)}"' in (V / "post_interview.py").read_text()

    def test_the_worker_and_the_pipeline_pick_the_same_way(self):
        assert "[fromTopics, pitch, thesis] : [thesis, pitch, fromTopics]" in WORKER


def test_an_empty_booking_note_is_not_object_object():
    i = WORKER.index("function bookingNotes(p: any): string {")
    body = WORKER[i:WORKER.index("\n}\n", i)]
    assert 'typeof n === "string"' in body and "String(n" not in body
