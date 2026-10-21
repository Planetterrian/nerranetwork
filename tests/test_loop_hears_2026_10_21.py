"""A loop that can hear (Oct 21 2026 review, §7.4).

Thirteen scorecards did not move while the grading pass adopted and retired
about a hundred lessons on numbers estimated from transcript line starts,
and one guest in thirteen was ever asked. Now: the craft is measured from
each speaker's own recording, the grading pass proposes, a weekly pass
adopts with the audio numbers in front of it and retires by metric, every
guest gets a three-question email a day after the room, and the review
snapshot reads what the interview shows actually write.
"""

from __future__ import annotations

import datetime as dt
import importlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))

POST = (V / "post_interview.py").read_text(encoding="utf-8")
LEARNING = (V / "learning.py").read_text(encoding="utf-8")
RETRO = (V / "prompts" / "editorial_passes" / "09_interview_retro.txt").read_text(encoding="utf-8")
MIGRATION = (ROOT / "supabase" / "migrations" / "20261021_mira_hears_and_asks.sql").read_text(encoding="utf-8")
FIRE_WF = (ROOT / ".github" / "workflows" / "nerra_voices_fire_interview.yml").read_text(encoding="utf-8")
WEEKLY_WF = (ROOT / ".github" / "workflows" / "nerra_voices_weekly_lessons.yml").read_text(encoding="utf-8")


def _fresh(name: str):
    sys.modules.pop(name, None)
    return importlib.import_module(name)


class TestTheMeasurementReachesTheRecord:
    def test_post_interview_collects_words_and_measures_audio(self):
        assert "words_out=words_by_label" in POST
        assert "audio_metrics.measure_audio(" in POST
        assert "metrics.update(audio_metrics.columns(audio))" in POST
        # The raw-stereo path has no per-speaker words: the row says so.
        assert 'metrics["metrics_basis"] = "transcript"' in POST

    def test_the_migration_carries_every_contract_column(self):
        for col in ("overlap_sec", "overlap_events", "turn_gap_ms_median", "turn_gap_ms_p10",
                    "turn_gap_ms_p90", "mira_turn_sec_median", "mira_turn_sec_p90",
                    "guest_words_per_answer_median", "guest_words_trend", "self_answered_turns",
                    "echo_open_rate", "closing_round_complete", "seams", "metrics_basis"):
            assert f"add column if not exists {col}" in MIGRATION, col
        for col in ("survey_token", "survey_sent_at", "survey_rating", "survey_change",
                    "survey_recommend", "survey_answered_at", "guest_redaction_windows",
                    "edit_transcript", "thanks_sent_at", "publish_package_sent_at"):
            assert f"add column if not exists {col}" in MIGRATION, col
        assert "add column if not exists metric text" in MIGRATION
        assert "add column if not exists reasoning_effort text" in MIGRATION

    def test_the_old_estimates_are_still_written(self):
        """A month of comparison: the transcript estimates stay beside the
        audio numbers rather than vanishing the day the basis changed."""
        assert '"interruptions": count_interruptions(' in LEARNING
        assert '"dead_air_sec":' in LEARNING
        assert "measure(run, package.get" in POST

    def test_words_are_mapped_to_roles_by_label(self, monkeypatch):
        import post_interview as PI
        monkeypatch.setattr(PI, "cohost_label", lambda: "Patrick")
        out = PI.words_by_role({"Mira": [{"start": 1, "end": 2, "word": "a"}],
                                "Patrick": [{"start": 3, "end": 4, "word": "b"}],
                                "Jon": [{"start": 5, "end": 6, "word": "c"}]}, {})
        assert set(out) == {"mira", "host", "guest"}
        assert out["guest"][0]["word"] == "c"

    def test_the_room_clock_starts_at_the_first_trace_line(self):
        import post_interview as PI
        run = {"scenario_trace": [{"t": "2026-10-21T15:00:00.000Z", "e": "room", "d": "opened"}]}
        assert PI.room_opened_at(run) == dt.datetime(2026, 10, 21, 15, tzinfo=dt.timezone.utc)
        assert PI.room_opened_at({}) is None


class TestTheGraderIsToldTheBasis:
    def test_retro_prompt_receives_and_explains_the_audio_basis(self):
        assert "{{audio_basis}}" in RETRO
        assert "audio_basis=audio_metrics_basis_text(metrics)" in POST
        assert "turn_gap_ms_median is how long after the guest's last" in " ".join(RETRO.split())
        assert "leave turn_taking and pacing\nat five" in RETRO or "leave turn_taking and pacing at five" in " ".join(RETRO.split())

    def test_a_transcript_only_room_withholds_turn_taking(self):
        import post_interview as PI
        text = PI.audio_metrics_basis_text({"metrics_basis": "transcript"})
        assert "TRANSCRIPT ONLY" in text and "Do not grade turn_taking or pacing" in text
        text = PI.audio_metrics_basis_text({"metrics_basis": "audio"})
        assert text.startswith("AUDIO.")

    def test_the_grader_proposes_with_a_metric_and_never_a_quoted_tic(self):
        flat = " ".join(RETRO.split())
        assert '"metric": "the measure that will show it worked' in flat
        assert "never quote the line, never list its instances" in flat
        assert "a fault the room now enforces in code" in flat
        assert "WHAT YOU DECIDE HERE IS APPLIED" not in RETRO


class TestThePassProposesAndTheWeekAdopts:
    def test_post_interview_no_longer_adopts_or_retires(self):
        block = POST[POST.index("# Learning loop"):]
        block = block[:block.index('if package.get("topical_show_fits")')]
        assert "save_proposed_lessons(" in block
        assert "adopt_lessons(" not in block and "retire_lessons(" not in block
        assert "save_grade(show.slug, interview[\"id\"], graded, [], 0)" in block

    def test_a_closing_session_is_measured_and_not_graded(self):
        block = POST[POST.index("# Learning loop"):]
        block = block[:block.index('if package.get("topical_show_fits")')]
        assert "closing_session = is_closing_session(interview)" in block
        assert "raise _NotAnInterview()" in block
        assert block.index("save_metrics(") < block.index("raise _NotAnInterview()")
        assert block.index("raise _NotAnInterview()") < block.index("09_interview_retro.txt")

    def test_proposals_carry_their_metric_and_scope(self, monkeypatch):
        L = _fresh("learning")
        seen = []
        monkeypatch.setattr(L, "sb_insert", lambda t, row: seen.append(row) or row)
        n = L.save_proposed_lessons("age_of_ai", "iv1", [
            {"lesson": "React to one specific thing before the next question.",
             "category": "listening", "metric": "echo_open_rate", "scope": "all_shows"},
            {"lesson": "Ask the show's question only after a bet of their own.",
             "category": "questions", "metric": "not a metric", "scope": "this_show"},
        ])
        assert n == 2
        assert seen[0]["metric"] == "echo_open_rate" and seen[0]["show"] == "network"
        assert seen[1]["metric"] is None and seen[1]["show"] == "age_of_ai"
        assert all(r["status"] == "proposed" for r in seen)

    def test_weekly_triage_drops_room_enforced_and_merges_duplicates(self, monkeypatch):
        W = _fresh("adopt_lessons_weekly")
        standing = [{"lesson": "React to one specific thing the guest said before the next question."}]
        split = W.triage([
            {"id": "a", "lesson": "Ask one question per turn and stop talking."},
            {"id": "b", "lesson": "Never give a second sign-off."},
            {"id": "c", "lesson": "React to one specific thing the guest said before you ask the next question."},
            {"id": "d", "lesson": "Open with their own word for the work, then one step down."},
        ], standing)
        assert [i["id"] for i in split["drop"]] == ["a", "b"]
        assert [i["id"] for i in split["merge"]] == ["c"]
        assert [i["id"] for i in split["candidates"]] == ["d"]

    def test_choose_makes_no_model_call_when_everything_fits(self, monkeypatch):
        W = _fresh("adopt_lessons_weekly")
        called = []
        monkeypatch.setattr(W, "llm", lambda *a, **k: called.append(1) or "[]")
        cands = [{"id": str(i), "lesson": f"Do the thing {i}."} for i in range(4)]
        assert W.choose(cands, []) == cands
        assert called == []

    def test_choose_caps_at_six_and_keeps_positive_wording(self, monkeypatch):
        W = _fresh("adopt_lessons_weekly")
        cands = [{"id": str(i), "lesson": f"Do the thing {i}."} for i in range(9)]
        monkeypatch.setattr(W, "llm", lambda *a, **k: json.dumps(
            [{"id": str(i), "lesson": ("Never do it" if i == 0 else f"Do it better {i}.")} for i in range(9)]))
        chosen = W.choose(cands, [])
        assert len(chosen) == W.MAX_ADOPT_PER_WEEK
        assert chosen[0]["lesson"] == "Do the thing 0."      # the ban was not accepted
        assert chosen[1]["lesson"] == "Do it better 1."

    def test_a_lesson_is_retired_by_its_metric_going_green_three_rooms(self):
        W = _fresh("adopt_lessons_weekly")
        standing = [{"id": "x", "lesson": "...", "metric": "self_answered_turns"},
                    {"id": "y", "lesson": "...", "metric": "echo_open_rate"},
                    {"id": "z", "lesson": "...", "metric": None}]
        green = {"self_answered_turns": 0, "echo_open_rate": 0.3}
        latest = [green, green, green]
        out = W.retire_by_metric("age_of_ai", standing, latest)
        assert [r["id"] for r in out] == ["x"]
        assert W.retire_by_metric("age_of_ai", standing, latest[:2]) == []

    def test_the_weekly_workflow_exists_and_defaults_to_a_dry_run(self):
        assert "adopt_lessons_weekly.py" in WEEKLY_WF
        assert "cron: '51 14 * * 1'" in WEEKLY_WF
        assert "default: true" in WEEKLY_WF


class TestEveryGuestIsAsked:
    def _fake_sb(self, monkeypatch, G, packages, interview, app):
        def select(table, query=""):
            if table == "editorial_packages":
                return packages
            if table == "interviews":
                return [interview]
            if table == "guest_applications":
                return [app]
            return []
        monkeypatch.setattr(G, "sb_select", select)

    def test_a_package_a_day_old_gets_one_email_and_one_stamp(self, monkeypatch):
        G = _fresh("guest_survey")
        now = dt.datetime(2026, 10, 22, 12, tzinfo=dt.timezone.utc)
        self._fake_sb(monkeypatch, G,
                      [{"id": "p1", "interview_id": "i1", "status": "in_review",
                        "created_at": "2026-10-21T03:46:19+00:00"}],
                      {"id": "i1", "session_kind": "interview", "application_id": "a1", "show": "age_of_ai"},
                      {"id": "a1", "name": "Jon Cheney", "email": "jon@example.com"})
        writes, mails = [], []
        monkeypatch.setattr(G, "sb_update", lambda t, q, patch: writes.append(patch) or [patch])
        monkeypatch.setattr(G, "send_email", lambda to, subject, html, **k: mails.append((to, subject, html)))
        assert G.send_due_surveys(now) == 1
        assert mails[0][0] == "jon@example.com"
        assert "one to five" in mails[0][2] and "/voices/survey/" in mails[0][2]
        assert "Hi Jon" in mails[0][2]
        assert "survey_token" in writes[0] and "survey_sent_at" in writes[1]

    def test_a_closing_session_and_a_killed_room_are_not_asked(self, monkeypatch):
        G = _fresh("guest_survey")
        now = dt.datetime(2026, 10, 22, 12, tzinfo=dt.timezone.utc)
        self._fake_sb(monkeypatch, G,
                      [{"id": "p1", "interview_id": "i1", "status": "killed",
                        "created_at": "2026-10-21T03:46:19+00:00"},
                       {"id": "p2", "interview_id": "i1", "status": "archived",
                        "created_at": "2026-10-21T03:46:19+00:00"}],
                      {"id": "i1", "session_kind": "closing", "application_id": "a1"},
                      {"id": "a1", "name": "Piper", "email": "piper@example.com"})
        assert G.due_packages(now) == []

    def test_the_stamp_is_not_written_when_the_send_fails(self, monkeypatch):
        G = _fresh("guest_survey")
        now = dt.datetime(2026, 10, 22, 12, tzinfo=dt.timezone.utc)
        self._fake_sb(monkeypatch, G,
                      [{"id": "p1", "interview_id": "i1", "status": "in_review",
                        "created_at": "2026-10-21T03:46:19+00:00"}],
                      {"id": "i1", "session_kind": "interview", "application_id": "a1"},
                      {"id": "a1", "name": "Jon", "email": "jon@example.com"})
        writes = []
        monkeypatch.setattr(G, "sb_update", lambda t, q, patch: writes.append(patch) or [patch])

        def boom(*a, **k):
            raise RuntimeError("resend down")
        monkeypatch.setattr(G, "send_email", boom)
        assert G.send_due_surveys(now) == 0
        assert all("survey_sent_at" not in w for w in writes)

    def test_the_fire_tick_runs_the_surveys_as_a_step_that_cannot_fail_it(self):
        i = FIRE_WF.index("Guest surveys due today")
        step = FIRE_WF[i:i + 400]
        assert "continue-on-error: true" in step
        assert "python pipelines/voices/guest_survey.py" in step


class TestTheSnapshotSeesTheInterviewShows:
    def _snapshot(self):
        spec = importlib.util.spec_from_file_location("review_snapshot", ROOT / "scripts" / "review_snapshot.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_an_interview_show_never_reports_tts_scripts(self, tmp_path, monkeypatch):
        snap = self._snapshot()
        out_dir = tmp_path / "digests" / "age_of_ai"
        out_dir.mkdir(parents=True)
        (out_dir / "Age_of_AI_Ep011_20261010.md").write_text(
            "# The Age of AI\n\n> **A CEO weighs the tools.**\n\n"
            "**What You Need to Know:** Jason said so.\n", encoding="utf-8")
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("VOICES_SUPABASE_URL", raising=False)
        monkeypatch.setattr(snap, "ROOT", tmp_path)
        report = snap.interview_show_section("age_of_ai", out_dir, 10)
        assert "interview show" in report
        assert "_tts.txt`)" not in report and "Script length" not in report
        assert "Ep011" in report and "A CEO weighs the tools." in report
        assert "no graded rooms read" in report

    def test_build_snapshot_routes_the_two_interview_shows(self):
        snap = self._snapshot()
        assert set(snap.INTERVIEW_SHOW_SLUGS) == {"age_of_ai", "nerra_voices"}
        report = snap.build_snapshot("age_of_ai", episodes=2)
        assert "Published episodes" in report and "0 `_tts.txt`" not in report
