"""Oct 21 2026: what a guest hears from Mira around the hour.

* A thank-you within the hour of the room ending, in the guest's own words,
  once, and never into the pipeline.
* A publish-day package: the episode, a moment to share, the card, and a
  date to come back.
* A five-minute hello two days before, whose one product is the agenda.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))

import guest_thanks as gt  # noqa: E402
import hello_sessions as hs  # noqa: E402
import publish_episode as pe  # noqa: E402

POST = (ROOT / "pipelines" / "voices" / "post_interview.py").read_text(encoding="utf-8")

TRANSCRIPT = """[00:10] Mira: Hello, can you hear me?
[00:14] Jane Doe: I can hear you fine, are you on headphones?
[00:20] Mira: What did the first year teach you?
[00:25] Jane Doe: The first year taught us that pricing is a story, and we told it badly for eleven months before Acme Corp walked.
[00:50] Mira: That's a sharp distinction.
[00:55] Jane Doe: Yes.
[01:05] Mira: What about hiring?
[01:08] Jane Doe: We hired forty people in a year and kept thirty-one of them, which I am told is good for a company in Toronto.
[02:00] Patrick Novak: I remember 2019 being the year everyone in Toronto hired forty people and kept none.
[02:20] Jane Doe: The thing nobody says about a seed round is that the money is the least useful thing in the room.
[03:00] Mira: That's the end of the recording.
"""


class _Show:
    slug = "age_of_ai"
    name = "The Age of AI"
    short_label = "Age of AI"
    base_url = "https://nerranetwork.com"
    page_url = "https://nerranetwork.com/age-of-ai.html"
    apple_url = ""
    spotify_url = ""
    audio_subdir = "digests/age_of_ai"
    closing_booking_url = "https://cal.com/x/age-of-ai-closing"

    def post_url(self, n):
        return f"https://nerranetwork.com/blog/age_of_ai/ep{n:03d}.html"


class TestTheThankYou:
    def test_the_moments_are_the_guests_own_answers_with_a_name(self):
        moments = gt.memorable_moments(TRANSCRIPT, "Jane Doe")
        texts = [t for _at, t in moments]
        # Oct 22 2026: only answers to Mira's questions, whole sentences.
        assert len(texts) == 2
        assert "Acme Corp" in texts[0] and "Toronto" in texts[1]
        assert all(t in TRANSCRIPT for t in texts)                  # verbatim
        assert not any("sharp distinction" in t for t in texts)      # never Mira's
        assert not any("everyone in Toronto hired" in t for t in texts)  # never the co-host's
        assert not any("headphones" in t for t in texts)             # never housekeeping
        assert [at for at, _t in moments] == sorted(at for at, _t in moments)

    def test_the_email_names_the_date_and_what_they_will_approve(self):
        now = dt.datetime(2026, 10, 21, 18, 0, tzinfo=dt.timezone.utc)
        subject, body = gt.thank_you_email(_Show(), {"name": "Jane Doe"}, TRANSCRIPT, now=now)
        assert subject.startswith("Thank you for today, Jane")
        assert "Wednesday October 28" in body                        # now + 7 days
        assert "approve it, cut anything from it, or refuse it" in body
        assert "already out of the edit" in body
        assert "Acme Corp" in body and "Sincerely" in body

    def test_it_is_sent_once_and_stamped(self, monkeypatch):
        sent, writes = [], []
        monkeypatch.setattr(gt, "send_email", lambda to, s, b, **kw: sent.append((to, s)))
        monkeypatch.setattr(gt, "sb_update", lambda t, q, patch: writes.append((t, q, patch)))
        monkeypatch.setattr(gt, "show_for", lambda i, a: _Show())
        iv, app, pkg = {"session_kind": "interview"}, {"name": "Jane Doe", "email": "j@x.io"}, {"id": "p1"}
        assert gt.send_thank_you({}, iv, app, TRANSCRIPT, pkg) is True
        assert sent == [("j@x.io", "Thank you for today, Jane, and what happens next")]
        assert writes[0][0] == "editorial_packages" and "thanks_sent_at" in writes[0][2]
        assert gt.send_thank_you({}, iv, app, TRANSCRIPT, {"id": "p1", "thanks_sent_at": "x"}) is False
        assert len(sent) == 1

    def test_a_closing_session_gets_no_note(self, monkeypatch):
        monkeypatch.setattr(gt, "send_email", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
        assert gt.send_thank_you({}, {"session_kind": "closing"}, {"email": "j@x.io"}, TRANSCRIPT, {"id": "p"}) is False

    def test_after_room_never_raises(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("mail is down")
        monkeypatch.setattr(gt, "send_thank_you", boom)
        gt.after_room({}, {"session_kind": "interview"}, {}, TRANSCRIPT, {"id": "p"})

    def test_post_interview_makes_the_call_after_the_transcript_is_final(self):
        assert 'after_room(run, interview, app, package.get("transcript_cleaned") or transcript, pkg)' in POST
        assert POST.index("after_room(") > POST.index("Retrospective failed (non-fatal)")


class TestThePublishDayPackage:
    def test_the_return_month_is_a_date(self):
        assert pe.return_month(dt.date(2026, 10, 21)) == "January 2027"
        assert pe.return_month(dt.date(2026, 1, 15)) == "April 2026"

    def test_the_clip_is_a_deep_link_into_the_post_or_the_upload(self, tmp_path, monkeypatch):
        show = _Show()
        pkg = {"clip_suggestions": [{"start": 95.4, "end": 150, "title": "The seed round", "why": "x"}]}
        monkeypatch.setattr(pe, "ROOT", tmp_path)
        url, title = pe.clip_link(pkg, show, 12)
        assert url == "https://nerranetwork.com/blog/age_of_ai/ep012.html#t=95" and title == "The seed round"
        index = tmp_path / "digests" / "age_of_ai" / "youtube_videos.json"
        index.parent.mkdir(parents=True)
        index.write_text('{"videos": [{"episode": 12, "video_id": "abc"}]}')
        assert pe.clip_link(pkg, show, 12)[0] == "https://www.youtube.com/watch?v=abc&t=95s"
        assert pe.clip_link({}, show, 12) == ("", "")

    def test_the_email_carries_the_clip_the_card_and_the_date(self, monkeypatch):
        monkeypatch.setattr(pe, "clip_link", lambda p, s, n, **kw: ("https://y/t", "A moment"))
        monkeypatch.setattr(pe, "share_card_link", lambda s, n: "https://cdn/share/ep12.jpg")
        monkeypatch.setattr(pe, "guest_links", lambda app: [])
        _subject, body = pe.published_email(_Show(), {"name": "Jane Doe"}, {}, 12,
                                            when=dt.date(2026, 10, 21))
        assert "https://y/t" in body and "A moment" in body
        assert "https://cdn/share/ep12.jpg" in body
        assert "January 2027" in body and "second conversation" in body

    def test_it_is_sent_once(self, monkeypatch):
        sent, writes = [], []
        monkeypatch.setattr(pe, "published_email", lambda *a, **k: ("s", "b"))
        monkeypatch.setattr(pe, "send_email", lambda to, s, b, **kw: sent.append(to))
        monkeypatch.setattr(pe, "sb_update", lambda t, q, patch: writes.append(patch))
        pe.tell_the_guest(_Show(), {"email": "j@x.io"}, {"id": "p1"}, 12)
        assert sent == ["j@x.io"] and "publish_package_sent_at" in writes[0]
        pe.tell_the_guest(_Show(), {"email": "j@x.io"}, {"id": "p1", "publish_package_sent_at": "t"}, 12)
        assert sent == ["j@x.io"]


class TestThePreCallHello:
    def test_the_booking_page_is_derived_from_the_closing_one(self, monkeypatch):
        monkeypatch.delenv("CALCOM_BOOKING_URL_HELLO", raising=False)
        monkeypatch.delenv("CALCOM_BOOKING_URL_CLOSING", raising=False)
        monkeypatch.setattr(hs, "booking_url", lambda show, closing=False: "https://cal.com/x/age-of-ai-closing")
        assert hs.hello_booking_url(_Show()) == "https://cal.com/x/age-of-ai-hello"

    def test_invites_go_to_guests_without_an_agenda_once(self, monkeypatch):
        now = dt.datetime(2026, 10, 21, 12, 0, tzinfo=dt.timezone.utc)
        rows = [{"id": "i1", "application_id": "a1"}, {"id": "i2", "application_id": "a2"}]
        apps = {"a1": {"id": "a1", "name": "Jane Doe", "email": "j@x.io"},
                "a2": {"id": "a2", "name": "Sam", "email": "s@x.io",
                       "guest_agenda": {"topic": "pricing", "points": ["x"]}}}
        sent, writes = [], []
        monkeypatch.setattr(hs, "sb_select", lambda t, q="": rows if t == "interviews"
                            else [apps[q.split("eq.")[1]]])
        monkeypatch.setattr(hs, "sb_update", lambda t, q, patch: writes.append((q, patch)))
        monkeypatch.setattr(hs, "send_email", lambda to, s, b, **kw: sent.append(to))
        monkeypatch.setattr(hs, "show_for", lambda i, a: _Show())
        monkeypatch.setattr(hs, "booking_url", lambda show, closing=False: "https://cal.com/x/age-of-ai-closing")
        assert hs.send_hello_invites(now) == 1
        assert sent == ["j@x.io"]
        assert {q for q, _ in writes} == {"id=eq.i1", "id=eq.i2"}
        assert writes[1][1]["hello_skipped_reason"] == "agenda already set"

    def test_the_prompt_is_a_hello_not_an_interview(self):
        text = (ROOT / "pipelines" / "voices" / "prompts" / "mira_hello_session.txt").read_text()
        assert "NOT the interview" in text and "headphones" in text
        assert "what is the one thing you most want it to have reached" in text
        assert "Five minutes, no more" in text

    def test_after_hello_writes_the_agenda_and_archives_the_hello(self, monkeypatch):
        writes = []
        monkeypatch.setattr(hs, "llm", lambda *a, **k: '{"topic": "pricing as a story", "points": ["why Acme walked", "usage pricing"]}')
        monkeypatch.setattr(hs, "sb_update", lambda t, q, patch: writes.append((t, patch)))
        agenda = hs.after_hello({"id": "h1", "session_kind": "hello"}, {"id": "a1", "name": "Jane"},
                                TRANSCRIPT, {"id": "p1"})
        assert agenda == {"topic": "pricing as a story", "points": ["why Acme walked", "usage pricing"]}
        app_write = [p for t, p in writes if t == "guest_applications"][0]
        assert app_write["guest_agenda"]["source"] == "hello"
        assert [p["status"] for t, p in writes if t in ("editorial_packages", "interviews")] == ["archived", "archived"]

    def test_the_room_routes_a_hello_to_it(self):
        src = (ROOT / "pipelines" / "voices" / "guest_thanks.py").read_text()
        assert 'if kind == "hello":' in src and "after_hello(" in src

    def test_the_migration_names_the_columns(self):
        sql = (ROOT / "supabase" / "migrations" / "20261021_pre_call_hello.sql").read_text()
        for col in ("hello_for_interview_id", "hello_invited_at", "hello_skipped_reason", "hello_agenda"):
            assert col in sql
