"""Oct 5 2026. Mira's learning loop, widened, and the guest experience
around it.

* Craft lessons are the whole network's: Nerra Voices kept relearning what
  The Age of AI had already taught her.
* The edit reports back: Thor Hesselberg's episode needed five cuts of her
  own voice and the grading pass, which runs before anyone edits, saw none.
* Guests are asked about the experience on the review page, after listening.
* She is never told to stop saying the words she is required to say.
* An early closing round is caught as it starts (Thor: lightning round at 25
  of 45 minutes).
* Cal.com's own Reschedule and Cancel links move or cancel the interview.
* A missed two-hour reminder is sent by the Worker.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")
RETRO = (V / "prompts" / "editorial_passes" / "09_interview_retro.txt").read_text(encoding="utf-8")
POST = (V / "post_interview.py").read_text(encoding="utf-8")
ASSEMBLE = (V / "assemble_edit.py").read_text(encoding="utf-8")


def _learning(monkeypatch, rows_by_query):
    import learning
    monkeypatch.setattr(learning, "sb_select",
                        lambda table, q="": [r for k, rs in rows_by_query.items() if k in q for r in rs])
    return learning


class TestCraftIsSharedAcrossShows:
    def test_both_scopes_reach_the_prompt_once_each(self, monkeypatch):
        L = _learning(monkeypatch, {
            "show=eq.network": [{"id": "n1", "show": "network", "lesson": "Ask one question at a time."}],
            "show=eq.nerra_voices": [{"id": "s1", "show": "nerra_voices", "lesson": "Ask one question at a time."},
                                     {"id": "s2", "show": "nerra_voices", "lesson": "Ask what the work feels like."}],
        })
        block = L.lessons_block("nerra_voices")
        assert block.count("Ask one question at a time.") == 1
        assert "Ask what the work feels like." in block
        listing = L.lessons_for_prompt("nerra_voices")
        assert "(all shows, " in listing and "(this show, " in listing

    def test_a_lesson_is_the_networks_unless_it_is_about_the_show(self, monkeypatch):
        L = _learning(monkeypatch, {})
        stored = []
        monkeypatch.setattr(L, "sb_insert", lambda t, row: stored.append(row) or row)
        L.adopt_lessons("age_of_ai", "iv1", [
            {"lesson": "Wait two seconds after the guest stops before asking the next question.",
             "category": "listening"},
            {"lesson": "Ask the twelve-month bet only once the guest has named a bet of their own.",
             "category": "questions", "scope": "this_show"},
        ])
        assert [r["show"] for r in stored] == ["network", "age_of_ai"]

    def test_the_grader_is_told_about_scope(self):
        assert '"scope": "all_shows | this_show"' in RETRO
        assert "A lesson marked all_shows reaches every show" in " ".join(RETRO.split())

    def test_gate_one_lists_both(self):
        assert "show_lessons?show=in.(${show.slug},network)" in WORKER


class TestTheEditTeachesHer:
    SPEC = {"cuts": [
        {"from": "mix:clean", "start": 47.6, "end": 740.6},
        {"from": "mix:clean", "start": 743.8, "end": 1126.5},
        {"from": "mix:clean", "start": 1136.4, "end": 1204.0,
         "mute": [{"from": 1154.3, "to": 1155.48, "role": "mira"}]},
        {"from": "mix:clean", "start": 1222.95, "end": 1512.4},
        {"from": "narration:outro"},
    ]}
    TAPE = "\n".join([
        "[12:17] Mira: What does one of those methods look like?",
        "[12:21] Mira: Fair enough.",
        "[12:23] Thor: It's not like that.",
        "[18:47] Mira: What part of DECA people's process has changed the most",
        "[19:14] Mira: Take your time.",
        "[20:04] Mira: What's one specific win that shows this",
        "[20:08] Mira: in action?",
        "[20:22] Mira: What's one specific win that shows this in action?",
    ])

    def test_cut_lines_are_found_and_the_resumed_line_is_kept(self):
        import learning
        got = learning.editor_cut_lines(self.SPEC, self.TAPE)
        lines = [l for _, l, _ in got]
        assert "Fair enough." in lines
        assert "What part of DECA people's process has changed the most" in lines
        assert "What's one specific win that shows this in action?" not in lines
        assert ("Take your time.", "talkover") in [(l, k) for _, l, k in got]

    def test_only_short_lines_cut_for_themselves_are_retired(self, monkeypatch):
        import learning
        monkeypatch.setattr(learning, "sb_select", lambda *a, **k: [])
        monkeypatch.setattr(learning, "sb_insert", lambda t, row: row)
        retired = []
        monkeypatch.setattr(learning, "save_host_phrases",
                            lambda show, iid, phrases: retired.extend(phrases) or len(phrases))
        assert learning.record_editor_cuts("age_of_ai", "iv1", self.SPEC, self.TAPE) >= 4
        assert "Fair enough" in retired
        assert "Take your time" not in retired          # right words, wrong moment
        assert "in action?" not in retired               # the tail of a sentence

    def test_the_warm_up_trim_is_not_a_verdict(self):
        import learning
        spec = {"cuts": [{"from": "mix:clean", "start": 0, "end": 38.0},
                         {"from": "mix:clean", "start": 45.0, "end": 300.0}]}
        assert learning.editor_cut_lines(spec, "[00:40] Mira: Where are you calling from?") == []

    def test_assembly_reports_and_grading_reads(self):
        assert "record_editor_cuts(show.slug, iid, spec," in ASSEMBLE
        assert "transcript_raw" in ASSEMBLE[ASSEMBLE.index("record_editor_cuts"):][:600] or \
            "select=transcript_raw" in ASSEMBLE
        assert "{{editor_cuts}}" in RETRO and "editor_cuts=recent_editor_cuts()" in POST


class TestTheGuestIsAskedAfterListening:
    def test_review_page_asks_and_stores(self):
        assert "One question from Mira (optional)" in WORKER
        assert "episode_grades?interview_id=eq.${pkg.interview_id}&select=ask_the_guest" in WORKER
        assert "guest_experience: experience, guest_experience_at: now" in WORKER

    def test_grading_reads_it(self):
        assert "{{guest_experience}}" in RETRO
        assert "guest_experience=recent_guest_experience()" in POST


class TestSheIsNeverForbiddenHerOwnLines:
    def test_the_sign_off_is_not_a_reflex(self):
        from learning import host_formulas
        rows = [(0.0, "Mira", "That's the end of the recording."),
                (5.0, "Mira", "That's a sharp distinction.")]
        got = host_formulas(rows, "Mira")
        assert "That's a sharp distinction" in got
        assert not any("end of the recording" in g for g in got)

    def test_an_old_entry_is_filtered_out_of_the_prompt(self, monkeypatch):
        import learning
        monkeypatch.setattr(learning, "sb_select", lambda *a, **k: [
            {"phrase": "That's the end of the recording"}, {"phrase": "Fair enough"}])
        block = learning.variety_block("age_of_ai")
        assert "Fair enough" in block and "end of the recording" not in block


class TestTheClosingRoundWaitsItsTurn:
    def test_an_early_round_is_caught_as_it_starts(self):
        assert "function catchEarlyClosingRound(text)" in SCENARIO
        assert "try { catchEarlyClosingRound(text); }" in SCENARIO
        assert "lightning round" in SCENARIO[SCENARIO.index("const CLOSING_ROUND_RE"):][:200]
        assert "if (roomEnded || !grokAgent || closingPermitted || isClosingSession()) return;" in SCENARIO


class TestCalComsOwnLinksWork:
    def test_cancel_and_reschedule_are_handled(self):
        assert 'if (trigger === "BOOKING_CANCELLED") return handleCalComCancelled(env, p);' in WORKER
        assert "status=in.(staged,awaiting_guest,pending)" in WORKER
        assert 'if (p.rescheduled === true || p.fromReschedule)' in WORKER

    def test_manage_offers_the_guests_own_show(self):
        assert "const booking = bookingUrl(env, show) || \"\";" in WORKER
        assert WORKER.count("env.CALCOM_BOOKING_URL || \"\"") == 0


class TestNothingDependsOnGitHubOnTheDay:
    def test_the_worker_sends_a_missed_reminder(self):
        assert "async function reminderFallback(env: Env)" in WORKER
        assert "interviews?id=eq.${iv.id}&reminder_sent_at=is.null" in WORKER
        assert "try { await reminderFallback(env); }" in WORKER

    def test_a_dead_interview_never_opens(self):
        assert "const dead = DEAD_INTERVIEW_STATUSES.has(String(iv.status));" in WORKER


class TestAClosingSessionFinishesTheEpisode:
    """Oct 5 2026 (Piper Martz). Her closing session is booked for Friday; it
    must land on the end of her first episode, not become a ten-minute
    episode of its own that she is asked to approve."""

    def test_the_cut_step_splices_instead_of_cutting(self, monkeypatch, tmp_path):
        import json
        import auto_edit as ae
        monkeypatch.setattr(ae, "EDL_DIR", tmp_path / "edl")
        monkeypatch.setattr(ae, "NARRATION_DIR", tmp_path / "narr")
        parent_edl = {"run_id": "r1", "interview_id": "iv1", "show": "age_of_ai", "note": "n",
                      "cuts": [{"from": "narration:intro"}, {"gap": 0.7},
                               {"from": "mix:clean", "start": 20.0, "end": 2987.2, "exact_end": True},
                               {"gap": 1.4}, {"from": "narration:outro"}]}
        writes = []
        monkeypatch.setattr(ae, "sb_select", lambda t, q="": (
            [{"id": "e1", "slug": "piper_x", "edl": parent_edl, "narration": {"segments": []}}]
            if t == "episode_edits" else
            [{"id": "p1", "transcript_cleaned": "[00:10] Mira: Welcome."}] if t == "editorial_packages" else []))
        monkeypatch.setattr(ae, "sb_update", lambda t, q, patch: writes.append((t, patch)))
        monkeypatch.setattr(ae, "_leg_offset", lambda run: 0.0)
        ctx = {"run": {"id": "r2", "duration_sec": 700, "created_at": "2026-10-09T18:00:00Z"},
               "interview": {"id": "iv2", "session_kind": "closing", "continues_interview_id": "iv1"},
               "app": {}, "package": {"transcript_raw": "\n".join([
                   "[00:05] Mira: Welcome back, Piper. How are you?",
                   "[00:09] Piper: Good, thanks.",
                   "[00:40] Mira: We're back in the quick lightning round. You were telling me about a book.",
                   "[00:48] Piper: The Art of Gathering.",
                   "[09:50] Mira: That's the end of the recording."])}}
        out = ae.splice_closing(ctx)
        assert out == {"slug": "piper_x", "spliced": True}
        cuts = json.loads((tmp_path / "edl" / "piper_x.json").read_text())["cuts"]
        piece = [c for c in cuts if c.get("run_id") == "r2"][0]
        assert piece["start"] == 39.6                          # the welcome back stays out
        assert cuts[-1] == {"from": "narration:outro"}         # Mira's close still ends it
        assert cuts.index(piece) < len(cuts) - 1
        assert "exact_end" not in cuts[2]                       # the first session no longer ends it
        ae.splice_closing(ctx)                                  # twice is the same as once
        again = json.loads((tmp_path / "edl" / "piper_x.json").read_text())["cuts"]
        assert again == cuts
        assert any(t == "editorial_packages" and "[Closing session]" in p["transcript_cleaned"]
                   for t, p in writes)

    def test_assembly_takes_a_piece_from_another_run(self):
        assert 'if cut.get("run_id") and str(cut["run_id"]) != str(run.get("id")):' in ASSEMBLE
        assert "_clean_sources(src_run, show)" in ASSEMBLE

    def test_no_package_of_its_own_reaches_anyone(self):
        i = POST.index('if (interview.get("session_kind") or "interview") == "closing":')
        block = POST[i:i + 900]
        assert '"status": "archived"' in block and "return 0" in block
        assert i < POST.index("is ready for your review")

    def test_the_booking_is_recognised(self):
        assert "p.event_type_slug ?? p.type ??" in WORKER
        assert "finishing our conversation" in WORKER


class TestARescheduleMovesTheInterview:
    def test_found_from_the_booking_not_the_application(self):
        assert "async function interviewForBooking(" in WORKER
        assert "cal_booking_uid=eq.${encodeURIComponent(uid)}" in WORKER
        assert 'if (trigger === "BOOKING_RESCHEDULED") {' in WORKER
        assert "Moved: our ${show.name} interview is now" in WORKER
        assert WORKER.count('cal_booking_uid: String(p.uid ?? "") || null,') >= 3
