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
